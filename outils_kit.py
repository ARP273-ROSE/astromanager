# -*- coding: utf-8 -*-
"""Outils tiers embarques dans les paquets, sur les trois systemes.

Lu par `build_package.py` (Windows) et `build_unix.py` (macOS, Linux) : rien
ici n'est propre a une application, tout ce qui varie vit dans la cle
« outils » de `kit.json`. Chaque outil est pose dans `outils/<nom>/` du paquet,
A COTE de `python/` et `app/` — comme l'interpreteur et les dependances
compilees, il arrive avec le paquet complet (installeur, .dmg, .tar.gz) et la
mise a jour automatique, qui ne remplace que `app/`, n'y touche jamais.

    "outils": [
      {"nom": "tesseract",
       "conda": ["tesseract=5.5.*"],                  # paquets conda-forge
       "executables": ["tesseract"],
       "fichiers": [{"url": "...", "sha256": "...", "vers": "tessdata/fra.traineddata"}],
       "essai": ["--tessdata-dir", "{dossier}/tessdata", "--list-langs"],
       "essai_attendu": ["fra", "eng"]},
      {"nom": "tectonic",
       "archives": {"linux-x86_64": {"url": "...", "sha256": "..."}, "windows": {...}, ...},
       "executables": ["tectonic"],
       "essai": ["--version"],
       "prechauffer": {"variable": "TECTONIC_CACHE_DIR", "cache": "cache",
                       "commande": ["-X", "compile", "--outdir", "{sortie}", "{tex}"],
                       "controle": ["-X", "compile", "--only-cached", "--outdir", "{sortie}", "{tex}"],
                       "documents": [{"tex": "docs/exemple/*.tex"},
                                     {"tex": "docs/manuel/manuel-fr.tex", "pdf": "docs/manuel-fr.pdf"}]}}
    ]

- `archives` : une archive (.zip, .tar.gz, .tar.xz) par systeme, cle
  « <systeme>-<arch> » (linux-x86_64, linux-arm64, macos-arm64, macos-x86_64,
  windows-x86_64), a defaut « <systeme> » ; empreinte SHA-256 OBLIGATOIRE.
  Deployee dans `outils/<nom>/<vers>` (« bin » par defaut) ; un dossier racine
  unique est remonte.
- `conda` : paquets conda-forge resolus par micromamba (version figee
  ci-dessous, empreinte verifiee) dans un prefixe temporaire ; on en garde
  les executables et leurs bibliotheques : `bin/` + `lib/` sous macOS et
  Linux (chemins relatifs @loader_path/$ORIGIN des binaires conda-forge),
  tout dans `bin/` sous Windows (les DLL a cote de l'executable). Puis
  (`elaguer`, vrai par defaut) seule la fermeture des dependances des
  executables reste (lue dans les binaires ELF, Mach-O, PE), symboles
  inutiles retires sous Linux.
- `fichiers` : fichiers de donnees (modeles, polices...), empreinte
  obligatoire.
- `essai` : l'outil est lance une fois pose (« {dossier} » = son dossier) ; la
  construction echoue s'il ne repond pas, ou si `essai_attendu` manque a sa
  sortie.
- `prechauffer` : documents compiles a la construction avec la variable
  `variable` pointant sur `outils/<nom>/<cache>` : un cache rempli d'avance
  pour travailler hors ligne (Tectonic ne telecharge que les paquets LaTeX
  qu'un document demande). `controle` recompile chaque document en refusant
  le reseau : la construction echoue si le cache ne suffit pas. Un document
  qui nomme un `pdf` est un PRODUIT : son PDF remplace `app/<pdf>` (manuel
  regenere a chaque construction). Le cache livre est un MODELE en lecture
  seule : l'application le recopie dans le profil avant de s'en servir (rien
  n'ecrit dans le dossier d'installation).
"""
from __future__ import annotations

import glob
import hashlib
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

#: micromamba (resolveur conda-forge autonome, un seul executable), version
#: figee : https://github.com/mamba-org/micromamba-releases
MICROMAMBA_VERSION = '2.8.1-1'
MICROMAMBA = {
    'linux-x86_64': ('micromamba-linux-64',
                     '77b7790ec97f64581118f103585b175df4306f95829b0fa6bfe4a19cc88a1182'),
    'linux-arm64': ('micromamba-linux-aarch64',
                    '49aa29008cafa6cd6027ebd643fc43ca32c20740e60b0a05378c4e5bb837c217'),
    'macos-x86_64': ('micromamba-osx-64',
                     'd6fce18e56d7c6bf2331b0ee1b372a581c70f09b509cc9e924cdd131e053b58a'),
    'macos-arm64': ('micromamba-osx-arm64',
                    '9618a2866a2ffb3d36b55e9520f64d63dcd6dc2e622a351ca3cbe8e2cc90c757'),
    'windows-x86_64': ('micromamba-win-64',
                       'b645a5259cb92b5869b0e60943390dd0d362cae45bc7e2f5ba8c7e4a4b06c7aa'),
}
DELAI_ESSAI_S = 600


class ErreurOutil(RuntimeError):
    """Un outil declare dans kit.json n'a pas pu etre pose : la construction
    s'arrete (un paquet sans son outil ne se verrait que chez l'utilisateur)."""


def _log(msg):
    print(f'  {msg}', flush=True)


def systeme_courant() -> str:
    if sys.platform == 'win32':
        return 'windows'
    return 'macos' if sys.platform == 'darwin' else 'linux'


def arch_courante() -> str:
    machine = platform.machine().lower()
    return 'arm64' if machine in ('arm64', 'aarch64') else 'x86_64'


def choisir(table: dict, systeme: str, arch: str):
    """L'entree de `table` pour ce systeme : « systeme-arch », puis « systeme »,
    puis « * ». None s'il n'y en a pas."""
    for cle in (f'{systeme}-{arch}', systeme, '*'):
        if cle in (table or {}):
            return table[cle]
    return None


def empreinte(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, 'rb') as f:
        for bloc in iter(lambda: f.read(1 << 20), b''):
            h.update(bloc)
    return h.hexdigest()


def telecharger(url: str, dest: Path, sha256: str, log=_log) -> Path:
    """Telecharge `url` dans `dest` (une seule fois : cache) et verifie
    l'empreinte. Sans empreinte declaree, refus : un outil embarque doit etre
    exactement celui qu'on a choisi."""
    if not sha256:
        raise ErreurOutil(f'empreinte SHA-256 manquante pour {url}')
    attendu = sha256.split(':', 1)[-1].lower()
    if dest.exists() and empreinte(dest) == attendu:
        log(f'deja en cache : {dest.name}')
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    log(f'telechargement : {url}')
    req = urllib.request.Request(url, headers={'User-Agent': 'kit-outils-build'})
    partiel = dest.with_name(dest.name + '.partiel')
    with urllib.request.urlopen(req, timeout=300) as r, open(partiel, 'wb') as f:
        shutil.copyfileobj(r, f)
    vue = empreinte(partiel)
    if vue != attendu:
        partiel.unlink(missing_ok=True)
        raise ErreurOutil(f'empreinte inattendue pour {url} : {vue} (attendu {attendu})')
    os.replace(partiel, dest)
    return dest


def _dans(base: Path, cible: Path) -> bool:
    base, cible = os.path.realpath(base), os.path.realpath(cible)
    return os.path.commonpath([base, cible]) == base


def deployer_archive(archive: Path, dossier: Path, log=_log) -> None:
    """Deploie une archive .zip ou .tar.* dans `dossier` en gardant les droits
    d'execution et les liens symboliques relatifs ; refuse toute entree qui
    sortirait du dossier. Un dossier racine unique est remonte d'un cran."""
    tmp = Path(tempfile.mkdtemp(prefix='outil-', dir=dossier.parent if dossier.parent.exists() else None))
    try:
        nom = archive.name.lower()
        if nom.endswith('.zip'):
            with zipfile.ZipFile(archive) as z:
                for info in z.infolist():
                    dest = tmp / info.filename
                    if not _dans(tmp, dest):
                        raise ErreurOutil(f'archive suspecte : {info.filename}')
                    mode = info.external_attr >> 16
                    if stat.S_ISLNK(mode):
                        lien = z.read(info).decode('utf-8')
                        if os.path.isabs(lien) or not _dans(tmp, dest.parent / lien):
                            raise ErreurOutil(f'lien suspect : {info.filename} -> {lien}')
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        os.symlink(lien, dest)
                        continue
                    z.extract(info, tmp)
                    if mode & 0o777 and not info.is_dir():
                        dest.chmod(mode & 0o777)
        elif '.tar' in nom or nom.endswith(('.tgz', '.txz')):
            with tarfile.open(archive) as t:
                for m in t.getmembers():
                    if os.path.isabs(m.name) or not _dans(tmp, tmp / m.name):
                        raise ErreurOutil(f'archive suspecte : {m.name}')
                    if m.issym() and (os.path.isabs(m.linkname)
                                      or not _dans(tmp, (tmp / m.name).parent / m.linkname)):
                        raise ErreurOutil(f'lien suspect : {m.name} -> {m.linkname}')
                    if m.islnk() or m.isdev():
                        raise ErreurOutil(f'entree refusee : {m.name}')
                if hasattr(tarfile, 'tar_filter'):
                    t.extractall(tmp, filter='tar')
                else:
                    t.extractall(tmp)
        else:
            raise ErreurOutil(f'format d\'archive inconnu : {archive.name}')
        entrees = list(tmp.iterdir())
        racine = entrees[0] if len(entrees) == 1 and entrees[0].is_dir() and not entrees[0].is_symlink() else tmp
        dossier.mkdir(parents=True, exist_ok=True)
        for e in racine.iterdir():
            cible = dossier / e.name
            if cible.is_dir() and not cible.is_symlink():
                shutil.rmtree(cible)
            elif cible.exists() or cible.is_symlink():
                cible.unlink()
            shutil.move(str(e), str(cible))
        log(f'archive deployee : {archive.name}')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def nom_executable(nom: str, systeme: str) -> str:
    return nom + '.exe' if systeme == 'windows' and not nom.lower().endswith('.exe') else nom


def est_bibliotheque(nom: str, systeme: str) -> bool:
    """Bibliotheque partagee a garder d'un prefixe conda."""
    if systeme == 'windows':
        return nom.lower().endswith('.dll')
    if systeme == 'macos':
        return nom.endswith('.dylib')
    return '.so' in nom and (nom.endswith('.so') or '.so.' in nom)


def copier_prefixe_conda(prefixe: Path, dossier: Path, executables, systeme: str, log=_log) -> int:
    """Garde d'un prefixe conda les executables et les bibliotheques partagees.
    macOS/Linux : `bin/<exe>` et `lib/*.so*|*.dylib` (liens symboliques gardes,
    ils sont relatifs) ; Windows : tout dans `bin/` (DLL de `Library/bin` et de
    la racine du prefixe, a cote de l'executable). Rend le nombre de fichiers."""
    bin_dest = dossier / 'bin'
    bin_dest.mkdir(parents=True, exist_ok=True)
    n = 0
    if systeme == 'windows':
        sources = [prefixe / 'Library' / 'bin', prefixe]
        for exe in executables:
            trouve = next((d / nom_executable(exe, systeme) for d in sources
                           if (d / nom_executable(exe, systeme)).is_file()), None)
            if trouve is None:
                raise ErreurOutil(f'{exe} absent du prefixe conda')
            shutil.copy2(trouve, bin_dest / trouve.name)
            n += 1
        for d in sources:
            if d.is_dir():
                for f in d.iterdir():
                    if f.is_file() and est_bibliotheque(f.name, systeme):
                        shutil.copy2(f, bin_dest / f.name)
                        n += 1
        return n
    for exe in executables:
        src = prefixe / 'bin' / exe
        if not src.is_file():
            raise ErreurOutil(f'{exe} absent du prefixe conda')
        shutil.copy2(src, bin_dest / exe)
        (bin_dest / exe).chmod(0o755)
        n += 1
    lib_dest = dossier / 'lib'
    lib_dest.mkdir(parents=True, exist_ok=True)
    for f in sorted((prefixe / 'lib').iterdir()):
        if not est_bibliotheque(f.name, systeme):
            continue
        if f.is_symlink():
            lien = os.readlink(f)
            if os.path.isabs(lien) or '/' in lien:
                shutil.copy2(f, lib_dest / f.name)          # lien hors du dossier : le fichier
            else:
                os.symlink(lien, lib_dest / f.name)
        elif f.is_file():
            shutil.copy2(f, lib_dest / f.name)
        else:
            continue
        n += 1
    return n


# ---------------------------------------------------------------- dependances des binaires
# Lecture des bibliotheques DEMANDEES par un binaire, en Python pur (aucun outil
# du systeme : ni readelf, ni otool, ni dumpbin) : ELF (Linux), Mach-O (macOS),
# PE (Windows). Sert a ne garder d'un prefixe conda que la fermeture des
# dependances des executables (le prefixe de Tesseract pesait 110 Mo sous Linux).
def _cstr(data: bytes, debut: int) -> str:
    fin = data.find(b'\0', debut)
    return data[debut:fin if fin >= 0 else len(data)].decode('utf-8', 'replace')


def _elf_needed(data: bytes) -> list:
    import struct
    if data[:4] != b'\x7fELF':
        return []
    bits64 = data[4] == 2
    e = '<' if data[5] == 1 else '>'
    if bits64:
        shoff, = struct.unpack_from(e + 'Q', data, 0x28)
        shentsize, shnum = struct.unpack_from(e + 'HH', data, 0x3A)
    else:
        shoff, = struct.unpack_from(e + 'I', data, 0x20)
        shentsize, shnum = struct.unpack_from(e + 'HH', data, 0x2E)
    sections = []
    for i in range(shnum):
        o = shoff + i * shentsize
        if bits64:
            _nom, typ, _fl, _addr, off, taille, lien, _info, _al, entsize = struct.unpack_from(
                e + 'IIQQQQIIQQ', data, o)
        else:
            _nom, typ, _fl, _addr, off, taille, lien, _info, _al, entsize = struct.unpack_from(
                e + 'IIIIIIIIII', data, o)
        sections.append((typ, off, taille, lien, entsize))
    sortie = []
    for typ, off, taille, lien, entsize in sections:
        if typ != 6 or lien >= len(sections):           # SHT_DYNAMIC
            continue
        strtab = sections[lien][1]
        pas = entsize or (16 if bits64 else 8)
        for o in range(off, off + taille, pas):
            tag, val = struct.unpack_from(e + ('qQ' if bits64 else 'iI'), data, o)
            if tag == 0:
                break
            if tag == 1:                                 # DT_NEEDED
                sortie.append(_cstr(data, strtab + val))
    return sortie


def _macho_needed(data: bytes) -> list:
    import struct
    magie = data[:4]
    if magie in (b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe'):
        e = '<'
    elif magie in (b'\xfe\xed\xfa\xcf', b'\xfe\xed\xfa\xce'):
        e = '>'
    else:
        return []
    bits64 = magie in (b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf')
    ncmds, = struct.unpack_from(e + 'I', data, 16)
    o = 32 if bits64 else 28
    sortie = []
    for _ in range(ncmds):
        cmd, taille = struct.unpack_from(e + 'II', data, o)
        if cmd in (0xC, 0x80000018, 0x8000001F, 0x20, 0x80000023):   # LOAD, WEAK, REEXPORT, LAZY, UPWARD
            nom_off, = struct.unpack_from(e + 'I', data, o + 8)
            sortie.append(_cstr(data, o + nom_off).rsplit('/', 1)[-1])
        o += taille
    return sortie


def _pe_needed(data: bytes) -> list:
    import struct
    if data[:2] != b'MZ':
        return []
    pe, = struct.unpack_from('<I', data, 0x3C)
    if data[pe:pe + 4] != b'PE\0\0':
        return []
    coff = pe + 4
    nsec, = struct.unpack_from('<H', data, coff + 2)
    taille_opt, = struct.unpack_from('<H', data, coff + 16)
    opt = coff + 20
    magie, = struct.unpack_from('<H', data, opt)
    dirs = opt + (112 if magie == 0x20B else 96)
    secs = []
    for i in range(nsec):
        o = opt + taille_opt + i * 40
        vtaille, vaddr, rtaille, rptr = struct.unpack_from('<IIII', data, o + 8)
        secs.append((vaddr, max(vtaille, rtaille), rptr))

    def hors(rva):
        for vaddr, taille, rptr in secs:
            if vaddr <= rva < vaddr + taille:
                return rva - vaddr + rptr
        return None
    sortie = []
    for index, pas, champ in ((1, 20, 12), (13, 32, 4)):            # imports, imports differes
        rva, taille = struct.unpack_from('<II', data, dirs + index * 8)
        o = hors(rva) if rva else None
        while o is not None and o + pas <= len(data):
            bloc = data[o:o + pas]
            if not any(bloc):
                break
            nom_rva, = struct.unpack_from('<I', data, o + champ)
            no = hors(nom_rva)
            if no is not None:
                sortie.append(_cstr(data, no))
            o += pas
    return sortie


def dependances(chemin: Path) -> list:
    """Noms (sans chemin) des bibliotheques demandees par un binaire ELF,
    Mach-O ou PE ; [] pour tout autre fichier."""
    try:
        data = Path(chemin).read_bytes()
    except OSError:
        return []
    return _elf_needed(data) or _macho_needed(data) or _pe_needed(data)


def fermeture(executables, dossiers, systeme: str) -> set:
    """Fichiers (chemins reels) de `dossiers` dont dependent les executables,
    de proche en proche ; les bibliotheques du systeme (absentes) sont ignorees."""
    def cle(nom):
        return nom.lower() if systeme == 'windows' else nom
    index = {}
    for d in dossiers:
        if d.is_dir():
            for f in d.iterdir():
                index.setdefault(cle(f.name), f)
    gardes, a_voir = set(), [Path(x) for x in executables]
    while a_voir:
        f = a_voir.pop()
        if f in gardes:
            continue
        gardes.add(f)
        cible = f.resolve() if f.is_symlink() else f
        for nom in dependances(cible):
            g = index.get(cle(nom))
            if g is not None and g not in gardes:
                a_voir.append(g)
    return gardes


def elaguer_dependances(dossier: Path, executables, systeme: str, log=_log) -> int:
    """Ne garde dans bin/ et lib/ de l'outil que les executables et la fermeture
    de leurs dependances (plus les fichiers que vise un lien garde) ; sous
    Linux, retire aussi les symboles inutiles (strip --strip-unneeded : la
    libstdc++ de conda-forge pesait 24 Mo). Rend le nombre d'octets liberes."""
    bin_d, lib_d = dossier / 'bin', dossier / 'lib'
    exes = [executable(dossier, e, systeme) for e in executables]
    gardes = fermeture(exes, [bin_d, lib_d], systeme)
    for g in list(gardes):
        x = g
        while x.is_symlink():                       # libfoo.so.5 -> libfoo.so.5.0.5 : la cible aussi
            x = x.parent / os.readlink(x)
            gardes.add(x)
    libere = 0
    for d in (bin_d, lib_d):
        if not d.is_dir():
            continue
        for f in list(d.iterdir()):
            if f in gardes or f.is_dir():
                continue
            libere += f.lstat().st_size
            f.unlink()
    if systeme == 'linux' and shutil.which('strip'):
        for f in gardes:
            if f.is_file() and not f.is_symlink():
                avant = f.stat().st_size
                if subprocess.run(['strip', '--strip-unneeded', str(f)], capture_output=True).returncode == 0:
                    libere += avant - f.stat().st_size
    log(f'dependances : {len(gardes)} fichier(s) gardes, {libere / 1e6:.1f} Mo liberes')
    return libere


def micromamba(cache: Path, systeme: str, arch: str, log=_log) -> Path:
    choix = MICROMAMBA.get(f'{systeme}-{arch}')
    if not choix:
        raise ErreurOutil(f'micromamba indisponible pour {systeme}-{arch}')
    nom, sha = choix
    url = f'https://github.com/mamba-org/micromamba-releases/releases/download/{MICROMAMBA_VERSION}/{nom}'
    exe = telecharger(url, cache / (f'{MICROMAMBA_VERSION}-{nom}' + ('.exe' if systeme == 'windows' else '')), sha, log)
    if systeme != 'windows':
        exe.chmod(0o755)
    return exe


def poser_conda(entree: dict, dossier: Path, cache: Path, systeme: str, arch: str, log=_log) -> None:
    mm = micromamba(cache, systeme, arch, log)
    travail = Path(tempfile.mkdtemp(prefix='conda-'))
    try:
        prefixe = travail / 'p'
        env = dict(os.environ, MAMBA_ROOT_PREFIX=str(travail / 'racine'))
        cmd = [str(mm), 'create', '-y', '--no-rc', '--no-env', '-r', str(travail / 'racine'),
               '-p', str(prefixe), '--override-channels', '-c', 'conda-forge', *entree['conda']]
        log('micromamba : ' + ' '.join(entree['conda']))
        r = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if r.returncode != 0:
            raise ErreurOutil('micromamba a echoue :\n' + (r.stdout + r.stderr)[-3000:])
        n = copier_prefixe_conda(prefixe, dossier, entree.get('executables') or [], systeme, log)
        log(f"{entree['nom']} : {n} fichier(s) gardes du prefixe conda")
        if entree.get('elaguer', True):
            elaguer_dependances(dossier, entree.get('executables') or [], systeme, log)
    finally:
        shutil.rmtree(travail, ignore_errors=True)


def executable(dossier: Path, nom: str, systeme: str) -> Path:
    """Chemin de l'executable `nom` d'un outil pose (bin/, sinon la racine)."""
    for d in (dossier / 'bin', dossier):
        p = d / nom_executable(nom, systeme)
        if p.is_file():
            return p
    raise ErreurOutil(f'executable {nom} introuvable dans {dossier}')


def _remplacer(args, valeurs: dict) -> list:
    sortie = []
    for a in args:
        for k, v in valeurs.items():
            a = a.replace('{' + k + '}', str(v))
        sortie.append(a)
    return sortie


def _executer(cmd, cwd=None, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, timeout=DELAI_ESSAI_S,
                          **({'creationflags': 0x08000000} if sys.platform == 'win32' else {}))


def essayer(entree: dict, dossier: Path, systeme: str, log=_log) -> str:
    """Lance l'essai declare ; rend sa sortie. ErreurOutil s'il echoue."""
    args = entree.get('essai')
    if not args:
        return ''
    exe = executable(dossier, (entree.get('executables') or [entree['nom']])[0], systeme)
    r = _executer([str(exe), *_remplacer(args, {'dossier': dossier})])
    sortie = (r.stdout + r.stderr).decode('utf-8', 'replace')
    if r.returncode != 0:
        raise ErreurOutil(f"essai de {entree['nom']} en echec ({r.returncode}) :\n{sortie[-2000:]}")
    manque = [m for m in entree.get('essai_attendu') or [] if m not in sortie]
    if manque:
        raise ErreurOutil(f"essai de {entree['nom']} : {', '.join(manque)} absent(s) de la sortie :\n{sortie[-2000:]}")
    log(f"essai de {entree['nom']} : ok ({sortie.strip().splitlines()[0][:80] if sortie.strip() else 'muet'})")
    return sortie


def documents_a_prechauffer(spec: dict, racine_depot: Path) -> list:
    """[(chemin .tex, pdf produit ou None)] dans l'ordre declare."""
    liste = []
    for d in spec.get('documents') or []:
        trouves = sorted(glob.glob(str(racine_depot / d['tex'])))
        if not trouves:
            raise ErreurOutil(f"aucun document pour {d['tex']}")
        for t in trouves:
            liste.append((Path(t), d.get('pdf')))
    return liste


def prechauffer(entree: dict, dossier: Path, racine_depot: Path, app: Path | None,
                systeme: str, log=_log) -> int:
    """Compile les documents declares pour remplir le cache de l'outil, puis
    les recompile SANS reseau (« controle ») ; recopie les PDF produits dans
    app/. Rend la taille du cache en octets."""
    spec = entree.get('prechauffer')
    if not spec:
        return 0
    cache = dossier / spec.get('cache', 'cache')
    cache.mkdir(parents=True, exist_ok=True)
    exe = executable(dossier, (entree.get('executables') or [entree['nom']])[0], systeme)
    env = dict(os.environ, **{spec['variable']: str(cache)})
    for etape in ('commande', 'controle'):
        if not spec.get(etape):
            continue
        for tex, pdf in documents_a_prechauffer(spec, racine_depot):
            with tempfile.TemporaryDirectory(prefix='prechauffe-') as sortie:
                cmd = [str(exe), *_remplacer(spec[etape], {'tex': tex.name, 'sortie': sortie,
                                                            'dossier': dossier})]
                r = _executer(cmd, cwd=tex.parent, env=env)
                produit = Path(sortie) / (tex.stem + '.pdf')
                if r.returncode != 0 or not produit.is_file():
                    texte = (r.stdout + r.stderr).decode('utf-8', 'replace')
                    raise ErreurOutil(f"{entree['nom']} ({etape}) : echec sur {tex.name}\n{texte[-3000:]}")
                if etape == 'controle' and pdf and app is not None:
                    cible = app / pdf
                    cible.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(produit, cible)
                    log(f'produit : {pdf} ({produit.stat().st_size / 1e6:.1f} Mo)')
            log(f"{entree['nom']} ({etape}) : {tex.relative_to(racine_depot)} ok")
    taille = sum(f.stat().st_size for f in cache.rglob('*') if f.is_file())
    log(f"cache de {entree['nom']} : {taille / 1e6:.1f} Mo")
    return taille


def poser_outil(entree: dict, racine_outils: Path, cache: Path, racine_depot: Path,
                app: Path | None = None, systeme: str | None = None, arch: str | None = None,
                log=_log) -> Path:
    systeme = systeme or systeme_courant()
    arch = arch or arch_courante()
    dossier = racine_outils / entree['nom']
    if dossier.exists():
        shutil.rmtree(dossier)
    dossier.mkdir(parents=True)
    if entree.get('archives'):
        choix = choisir(entree['archives'], systeme, arch)
        if not choix:
            raise ErreurOutil(f"{entree['nom']} : aucune archive pour {systeme}-{arch}")
        nom = choix['url'].rsplit('/', 1)[-1].replace('%40', '@')
        archive = telecharger(choix['url'], cache / 'outils' / nom, choix.get('sha256', ''), log)
        deployer_archive(archive, dossier / choix.get('vers', entree.get('vers', 'bin')), log)
    if entree.get('conda'):
        poser_conda(entree, dossier, cache / 'outils', systeme, arch, log)
    if not entree.get('archives') and not entree.get('conda'):
        raise ErreurOutil(f"{entree['nom']} : ni « archives » ni « conda »")
    for f in entree.get('fichiers') or []:
        nom = f['url'].rsplit('/', 1)[-1]
        src = telecharger(f['url'], cache / 'outils' / (f.get('sha256', '')[:12] + '-' + nom), f.get('sha256', ''), log)
        cible = dossier / f.get('vers', nom)
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, cible)
    if systeme != 'windows':
        for exe in entree.get('executables') or []:
            p = executable(dossier, exe, systeme)
            p.chmod(p.stat().st_mode | 0o755)
    essayer(entree, dossier, systeme, log)
    prechauffer(entree, dossier, racine_depot, app, systeme, log)
    taille = sum(f.stat().st_size for f in dossier.rglob('*') if f.is_file() and not f.is_symlink())
    log(f"outil {entree['nom']} pose ({taille / 1e6:.1f} Mo)")
    return dossier


def poser_tous(kit: dict, racine_paquet: Path, cache: Path, racine_depot: Path,
               app: Path | None = None, systeme: str | None = None, arch: str | None = None,
               log=_log) -> list:
    """Pose tous les outils de kit.json dans <racine_paquet>/outils/."""
    outils = kit.get('outils') or []
    if not outils:
        log('aucun outil embarque')
        return []
    racine = racine_paquet / 'outils'
    racine.mkdir(parents=True, exist_ok=True)
    return [poser_outil(e, racine, cache, racine_depot, app, systeme, arch, log) for e in outils]
