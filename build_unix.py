#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Construit le paquet macOS ou Linux.

La structure est LA MEME que celle du paquet Windows produit par
`build_package.py` :

    <NomApp>/
        python/     un CPython autonome
        app/        le code de l'application
        <NomApp>.sh (ou le bundle .app sous macOS)

C'est ce qui permet a `updater.py` de fonctionner a l'identique sur les trois
systemes : il ne remplace que le contenu de `app/`, du Python pur, et ne touche
jamais a l'interpreteur ni aux dependances compilees.

L'interpreteur vient de python-build-standalone, l'equivalent pour Unix du
Python « embeddable » de Windows. Dependre du Python du systeme serait plus
simple et plus fragile : sur macOS il peut ne pas etre installe, et sur Linux
sa version varie d'une distribution a l'autre.

Sous Linux, le dossier livre contient aussi `installer.sh` : il installe
dans le profil de l'utilisateur (~/.local/share), sans sudo, et pose l'entree
de menu. Sous macOS, le bundle `.app` se glisse dans Applications.

Usage :
    python3 build_unix.py [--version X.Y.Z]
"""

import argparse
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KIT = json.loads((ROOT / 'kit.json').read_text(encoding='utf-8'))
NOM = KIT['nom_fichier']
NOM_TECHNIQUE = KIT['nom_technique']
NOM_AFFICHE = KIT.get('nom_affiche', NOM)
POINT_ENTREE = KIT['point_entree']

PY_VERSION = '3.12.14'
PY_BUILD = '20260901'
DIST = ROOT / 'dist'
PKG = DIST / NOM
CACHE = ROOT / '.build_cache'


def _version_courante():
    return (ROOT / KIT.get('fichier_version', 'VERSION')).read_text().strip()


def log(msg):
    print(f'  {msg}', flush=True)


def cible_python():
    """Le triplet python-build-standalone de la machine courante."""
    machine = platform.machine().lower()
    if sys.platform == 'darwin':
        return 'aarch64-apple-darwin' if machine in ('arm64', 'aarch64') else 'x86_64-apple-darwin'
    if machine in ('aarch64', 'arm64'):
        return 'aarch64-unknown-linux-gnu'
    return 'x86_64-unknown-linux-gnu'


def plateforme():
    return 'macos' if sys.platform == 'darwin' else 'linux'


def architecture():
    """'arm64' ou 'x86_64' : le suffixe des paquets publies. Le Python
    embarque est propre a une architecture, le mauvais ne demarre pas."""
    machine = platform.machine().lower()
    return 'arm64' if machine in ('arm64', 'aarch64') else 'x86_64'


#: icone du programme (PNG carre), relative a la racine du depot. Facultatif :
#: sans elle, le bundle et l'entree de menu fonctionnent, sans icone.
ICONE_PNG = KIT.get('icone_png') or ''
ICONE_GRANDE = KIT.get('icone_grande') or ICONE_PNG

#: entree de menu Linux : noms et description dans les deux langues
#: (une cle vide de l'amorce vaut une cle absente)
NOM_FR = KIT.get('nom_affiche_fr') or NOM_AFFICHE
NOM_EN = KIT.get('nom_affiche_en') or NOM_AFFICHE
DESCRIPTION_FR = KIT.get('description_fr') or ''
DESCRIPTION_EN = KIT.get('description_en') or DESCRIPTION_FR
CATEGORIES = KIT.get('categories_linux') or 'Utility;'


def fetch(url, dest):
    if dest.exists() and dest.stat().st_size > 0:
        log(f'deja en cache : {dest.name}')
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    log(f'telechargement : {url}')
    with urllib.request.urlopen(url, timeout=180) as r, open(dest, 'wb') as f:
        shutil.copyfileobj(r, f)
    return dest


def step_python():
    """Pose un CPython autonome dans <PKG>/python."""
    cible = cible_python()
    nom = f'cpython-{PY_VERSION}+{PY_BUILD}-{cible}-install_only.tar.gz'
    url = (f'https://github.com/astral-sh/python-build-standalone/releases/'
           f'download/{PY_BUILD}/{nom}')
    archive = fetch(url, CACHE / nom)

    cible_dir = PKG / 'python'
    if cible_dir.exists():
        shutil.rmtree(cible_dir)
    tmp = DIST / '_py'
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    log('extraction de l\'interpreteur')
    with tarfile.open(archive) as t:
        # L'archive contient un unique dossier « python/ ».
        for membre in t.getmembers():
            if os.path.isabs(membre.name) or '..' in Path(membre.name).parts:
                raise RuntimeError(f'Archive suspecte : {membre.name}')
        # filtre « data » quand il existe (3.12+) : refuse liens et chemins
        # hors du dossier, et fait taire l'avertissement de Python 3.14
        if hasattr(tarfile, 'data_filter'):
            t.extractall(tmp, filter='data')
        else:
            t.extractall(tmp)
    shutil.move(str(tmp / 'python'), str(cible_dir))
    shutil.rmtree(tmp, ignore_errors=True)

    exe = cible_dir / 'bin' / 'python3'
    if not exe.exists():
        raise RuntimeError(f'Interpreteur introuvable : {exe}')
    sortie = subprocess.run([str(exe), '-V'], capture_output=True, text=True)
    log(f'interpreteur : {sortie.stdout.strip() or sortie.stderr.strip()}')
    return exe


def step_deps(exe):
    reqs = ROOT / (KIT.get('requirements') or 'requirements.txt')
    if not reqs.exists():
        log('aucun requirements.txt')
        return
    log(f'installation depuis {reqs.name}')
    subprocess.run([str(exe), '-m', 'pip', 'install', '-q',
                    '--no-warn-script-location', '-r', str(reqs)], check=True)


def step_app():
    """Copie le code dans <PKG>/app."""
    app = PKG / 'app'
    if app.exists():
        shutil.rmtree(app)
    app.mkdir(parents=True)
    for module in KIT.get('modules', []):
        src = ROOT / module
        if src.exists():
            shutil.copy2(src, app / src.name)
    for paquet in KIT.get('paquets', []):
        src = ROOT / paquet
        if src.exists():
            shutil.copytree(src, app / src.name,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for actif in KIT.get('assets', []):
        src = ROOT / actif
        if not src.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, app / src.name,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        else:
            shutil.copy2(src, app / src.name)
    # kit.json dit a updater.py ou chercher les versions : sans lui, le depot
    # de distribution est vide et aucune mise a jour n'est jamais trouvee.
    # build_package.py (Windows) le copiait deja ; ici, il manquait.
    shutil.copy2(ROOT / 'kit.json', app / 'kit.json')
    log(f'application copiee ({sum(1 for _ in app.rglob("*"))} entrees)')


def step_lanceur():
    """Un script shell, et sous macOS le bundle .app qui va autour."""
    sh = PKG / f'{NOM}.sh'
    sh.write_text(
        '#!/bin/sh\n'
        '# Lanceur : tout est relatif au dossier du paquet, rien n\'est\n'
        '# installe dans le systeme.\n'
        'ICI=$(cd "$(dirname "$0")" && pwd)\n'
        f'exec "$ICI/python/bin/python3" "$ICI/app/{POINT_ENTREE}" "$@"\n',
        encoding='utf-8')
    sh.chmod(sh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    log(f'lanceur : {sh.name}')

    if plateforme() == 'macos':
        # Un bundle .app : c'est ce qu'un utilisateur macOS attend de pouvoir
        # glisser dans Applications. Il enveloppe le paquet tel quel, ce qui
        # laisse `app/` a la meme place relative et l'updater inchange.
        bundle = DIST / f'{NOM}.app'
        if bundle.exists():
            shutil.rmtree(bundle)
        macos = bundle / 'Contents' / 'MacOS'
        resources = bundle / 'Contents' / 'Resources'
        macos.mkdir(parents=True)
        resources.mkdir(parents=True)
        icone = _icone_macos(resources)
        (bundle / 'Contents' / 'Info.plist').write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0"><dict>\n'
            f'  <key>CFBundleName</key><string>{NOM}</string>\n'
            f'  <key>CFBundleDisplayName</key><string>{NOM_AFFICHE}</string>\n'
            f'  <key>CFBundleIdentifier</key><string>io.github.arp273-rose.{NOM_TECHNIQUE}</string>\n'
            f'  <key>CFBundleExecutable</key><string>{NOM}</string>\n'
            f'  <key>CFBundleVersion</key><string>{_version_courante()}</string>\n'
            f'  <key>CFBundleShortVersionString</key><string>{_version_courante()}</string>\n'
            + (f'  <key>CFBundleIconFile</key><string>{icone}</string>\n'
               if icone else '') +
            '  <key>CFBundlePackageType</key><string>APPL</string>\n'
            '  <key>CFBundleDevelopmentRegion</key><string>en</string>\n'
            '  <key>CFBundleLocalizations</key><array><string>en</string>'
            '<string>fr</string></array>\n'
            '  <key>NSHighResolutionCapable</key><true/>\n'
            '  <key>LSMinimumSystemVersion</key><string>11.0</string>\n'
            '</dict></plist>\n', encoding='utf-8')
        lanceur = macos / NOM
        lanceur.write_text(
            '#!/bin/sh\n'
            'ICI=$(cd "$(dirname "$0")/../Resources" && pwd)\n'
            f'exec "$ICI/python/bin/python3" "$ICI/app/{POINT_ENTREE}" "$@"\n',
            encoding='utf-8')
        lanceur.chmod(0o755)
        for entree in ('python', 'app'):
            shutil.move(str(PKG / entree), str(resources / entree))
        shutil.rmtree(PKG, ignore_errors=True)
        log(f'bundle : {bundle.name}')

    if plateforme() == 'linux':
        # Modele d'entree de menu, rempli par installer.sh avec le dossier
        # d'installation reel (une entree .desktop exige des chemins absolus)
        (PKG / f'{NOM_TECHNIQUE}.desktop').write_text(
            '[Desktop Entry]\n'
            'Type=Application\n'
            f'Name={NOM_AFFICHE}\n'
            f'Name[fr]={NOM_FR}\n'
            f'Name[en]={NOM_EN}\n'
            + (f'Comment={DESCRIPTION_EN}\n' if DESCRIPTION_EN else '')
            + (f'Comment[fr]={DESCRIPTION_FR}\n' if DESCRIPTION_FR else '')
            + 'Exec="__ICI__/' + NOM + '.sh"\n'
            + ('Icon=__ICI__/app/' + ICONE_PNG + '\n' if ICONE_PNG else '')
            + 'Terminal=false\n'
            f'Categories={CATEGORIES}\n',
            encoding='utf-8')
        installeur = PKG / 'installer.sh'
        installeur.write_text(INSTALLER_SH.replace('__NOM__', NOM)
                              .replace('__TECH__', NOM_TECHNIQUE),
                              encoding='utf-8')
        installeur.chmod(0o755)
        log('installer.sh et entree de menu')


#: Installation sous Linux dans le profil de l'utilisateur : ni sudo, ni
#: gestionnaire de paquets, comme l'installeur Windows. Les messages sont
#: dans les deux langues, la locale n'etant pas forcement fiable en console.
INSTALLER_SH = r"""#!/bin/sh
# Installe __NOM__ dans le profil de l'utilisateur, sans sudo.
# Installs __NOM__ into the user's profile, without sudo.
set -e
ICI=$(cd "$(dirname "$0")" && pwd)
NOM_APP=__NOM__
TECH=__TECH__
DONNEES="${XDG_DATA_HOME:-$HOME/.local/share}"
CIBLE="$DONNEES/$TECH"
echo "Installation dans / Installing into: $CIBLE"
mkdir -p "$CIBLE"
# Les donnees de l'utilisateur (reglages, rapports) vivent ailleurs, dans
# $DONNEES/__NOM__ : elles ne sont jamais touchees ici.
rm -rf "$CIBLE/python" "$CIBLE/app"
cp -R "$ICI/python" "$ICI/app" "$ICI/$NOM_APP.sh" "$CIBLE/"
chmod +x "$CIBLE/$NOM_APP.sh" "$CIBLE/python/bin/"python3*
APPS="$DONNEES/applications"
mkdir -p "$APPS"
sed -e "s|__ICI__|$CIBLE|g" "$ICI/$TECH.desktop" > "$APPS/$TECH.desktop"
chmod +x "$APPS/$TECH.desktop"
command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$APPS" >/dev/null 2>&1 || true
echo "Termine. Lancez « $NOM_APP » depuis le menu des applications, ou :"
echo "Done. Start \"$NOM_APP\" from the applications menu, or run:"
echo "  $CIBLE/$NOM_APP.sh"
"""


def _icone_macos(resources: Path) -> str:
    """Construit l'icone .icns avec les outils du systeme (sips, iconutil).
    Facultatif : sans icone, le bundle fonctionne tout de meme."""
    src = ROOT / ICONE_GRANDE if ICONE_GRANDE else None
    if src is None or not src.exists() or not shutil.which('iconutil') or not shutil.which('sips'):
        return ''
    jeu = DIST / 'icone.iconset'
    shutil.rmtree(jeu, ignore_errors=True)
    jeu.mkdir(parents=True)
    try:
        for taille in (16, 32, 128, 256, 512):
            for echelle in (1, 2):
                px = taille * echelle
                if px > 1024:
                    continue
                nom = f'icon_{taille}x{taille}{"@2x" if echelle == 2 else ""}.png'
                subprocess.run(['sips', '-z', str(px), str(px), str(src),
                                '--out', str(jeu / nom)], check=True,
                               capture_output=True)
        subprocess.run(['iconutil', '-c', 'icns', str(jeu), '-o',
                        str(resources / 'icone.icns')], check=True,
                       capture_output=True)
        log('icone macOS : icone.icns')
        return 'icone.icns'
    except (subprocess.SubprocessError, OSError) as exc:
        log(f'icone macOS non construite ({exc}) : bundle sans icone')
        return ''
    finally:
        shutil.rmtree(jeu, ignore_errors=True)


def racine_paquet() -> Path:
    """Ou vivent `python/` et `app/` : le paquet, ou les Resources du bundle."""
    bundle = DIST / f'{NOM}.app' / 'Contents' / 'Resources'
    return bundle if bundle.exists() else PKG


def step_elaguer():
    """Retire ce qui ne sert pas a l'execution."""
    base = racine_paquet()
    avant = sum(f.stat().st_size for f in base.rglob('*') if f.is_file())
    for chemin in list(base.rglob('__pycache__')):
        if chemin.is_dir():
            shutil.rmtree(chemin, ignore_errors=True)
    # Bibliotheque standard seulement : un dossier « tests » de site-packages
    # peut etre un module importe par son paquet (astropy importe
    # astropy.tests a son chargement ; le retirer cassait l'application).
    for stdlib in (base / 'python' / 'lib').glob('python3*'):
        for nom in ('test', 'idlelib', 'tkinter', 'turtledemo', 'lib2to3',
                    'ensurepip'):
            shutil.rmtree(stdlib / nom, ignore_errors=True)
        # Tests de numpy : inutiles a l'execution, comme sous Windows.
        numpy = stdlib / 'site-packages' / 'numpy'
        if numpy.is_dir():
            for chemin in list(numpy.rglob('tests')):
                if chemin.is_dir():
                    shutil.rmtree(chemin, ignore_errors=True)
    for chemin in list(base.rglob('*.pyc')):
        chemin.unlink(missing_ok=True)
    # Sous Linux, libpython de python-build-standalone garde ses symboles de
    # debogage : 219 Mo, dont l'essentiel ne sert qu'a un debogueur. On ne
    # retire QUE ceux-la (--strip-debug), jamais la table des symboles
    # dynamiques dont depend le chargement des modules compiles.
    if plateforme() == 'linux' and shutil.which('strip'):
        for lib in (base / 'python' / 'lib').glob('libpython*.so*'):
            if lib.is_file() and not lib.is_symlink():
                subprocess.run(['strip', '--strip-debug', str(lib)], check=False)
    apres = sum(f.stat().st_size for f in base.rglob('*') if f.is_file())
    log(f'elagage : {avant/1e6:.0f} Mo -> {apres/1e6:.0f} Mo')


def step_verifier(version):
    """L'application doit au moins s'importer avec l'interpreteur embarque."""
    base = racine_paquet()
    exe = base / 'python' / 'bin' / 'python3'
    modules = KIT.get('verification_import', [])
    if not modules:
        return
    code = 'import sys; sys.path.insert(0, "app")\n' + \
           '\n'.join(f'import {m}' for m in modules) + '\nprint("ok")'
    # -B : sans cela la verification recree des .pyc dans app/ — apres
    # l'elagage, qui les avait retires — et ils partent dans le paquet.
    r = subprocess.run([str(exe), '-B', '-c', code], cwd=base,
                       capture_output=True, text=True,
                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    if r.returncode != 0:
        raise RuntimeError('Le paquet ne s\'importe pas :\n' + r.stderr[-2000:])
    log('verification d\'import : ok')
    # La mise a jour doit savoir ou chercher, et reconnaitre le paquet.
    controle = ('import sys; sys.path.insert(0, "app"); import updater; '
                'assert updater.REPO, "depot de distribution vide"; '
                'assert updater.is_packaged(), "paquet non reconnu"; print("ok")')
    r = subprocess.run([str(exe), '-B', '-c', controle], cwd=base, capture_output=True, text=True,
                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    if r.returncode != 0:
        raise RuntimeError('Mise a jour inoperante dans le paquet :\n' + r.stderr[-2000:])
    log('verification de la mise a jour : ok')
    # Le paquet doit annoncer la version qu'on publie : sinon il proposerait
    # sans fin une mise a jour deja installee.
    vue = (base / 'app' / KIT.get('fichier_version', 'VERSION')).read_text(
        encoding='utf-8').strip()
    if vue != version:
        raise RuntimeError(f'Le paquet annonce {vue!r}, le tag dit {version!r}')
    log(f'version annoncee : {vue}')


def step_archive(version):
    """L'archive applicative — le contenu de app/, ce que l'updater telecharge."""
    nom = f'{NOM_TECHNIQUE}-app-{version}.zip'
    sortie = ROOT / nom
    if sortie.exists():
        sortie.unlink()
    app = racine_paquet() / 'app'
    exclus = set(KIT.get('exclus_de_la_maj', []) or [])
    with zipfile.ZipFile(sortie, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(app.rglob('*')):
            rel = f.relative_to(app)
            if rel.parts and rel.parts[0] in exclus:
                continue
            if '__pycache__' in rel.parts:
                continue
            if f.is_file():
                info = zipfile.ZipInfo(str(rel))
                info.external_attr = (f.stat().st_mode & 0xFFFF) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, f.read_bytes())
    log(f'archive applicative : {nom} ({sortie.stat().st_size/1e6:.1f} Mo)')
    return sortie


def step_paquet_complet(version):
    """Le paquet complet, a telecharger la premiere fois.

    Linux : une archive .tar.gz (dossier + installer.sh). macOS : rien ici,
    l'image disque .dmg est faite par le workflow avec hdiutil.
    """
    if plateforme() == 'macos':
        return None
    nom = f'{NOM}-{version}-linux-{architecture()}.tar.gz'
    sortie = ROOT / nom
    if sortie.exists():
        sortie.unlink()
    with tarfile.open(sortie, 'w:gz') as t:
        t.add(PKG, arcname=NOM)
    log(f'paquet complet : {nom} ({sortie.stat().st_size/1e6:.0f} Mo)')
    return sortie


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', default=None)
    args = ap.parse_args()
    version = args.version or (ROOT / KIT.get('fichier_version', 'VERSION')).read_text().strip()

    print(f'== {NOM_AFFICHE} {version} — paquet {plateforme()} ==')
    if PKG.exists():
        shutil.rmtree(PKG)
    PKG.mkdir(parents=True)

    exe = step_python()
    step_deps(exe)
    step_app()
    step_lanceur()
    step_elaguer()
    step_verifier(version)
    step_archive(version)
    step_paquet_complet(version)
    print('== termine ==')


if __name__ == '__main__':
    main()
