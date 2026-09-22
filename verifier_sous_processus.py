#!/usr/bin/env python3
"""Cherche les sous-processus qui feront clignoter une console.

Une application graphique Windows tourne sous `pythonw.exe`, sans console.
Chaque `subprocess` lance alors brievement une fenetre noire, qui apparait et
disparait — sauf si on passe `creationflags=CREATE_NO_WINDOW`.

Ce n'est pas qu'une question d'elegance. Le veilleur du lecteur de CD de
MusicOtheque interroge le materiel toutes les quatre secondes : cela faisait
une fenetre qui clignotait en permanence sur le bureau, toute la journee.
L'utilisateur l'a rapporte ainsi : « une sorte de fenetre de console qui
s'allume une seconde et se ferme, tout le temps ». MountMonitor avait le meme
defaut au demarrage, avec quatre appels a `wmic`.

Le drapeau n'existe que sous Windows ; ailleurs il vaut zero et ne gene pas :
    _SANS_CONSOLE = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

Ce controle est statique et volontairement simple : il lit l'appel et
regarde si `creationflags` y figure.

    python verifier_sous_processus.py            # tout le dossier
    python verifier_sous_processus.py fichier.py
"""

import ast
import pathlib
import sys

LANCEURS = {'run', 'Popen', 'call', 'check_call', 'check_output'}

# Programmes qui n'ouvrent jamais de console : les signaler serait du bruit.
# `xdotool` est un outil X11 : il n'existe pas sous Windows, il n'y a donc
# aucune console Windows a masquer.
SANS_CONSOLE_PAR_NATURE = {'explorer', 'open', 'xdg-open', 'xdotool'}

# Fichiers qui ne font pas partie de l'application graphique. Un script de
# construction tourne dans une console, sur la machine d'integration : lui
# demander de masquer une fenetre qui n'existe pas n'aurait aucun sens.
# Le motif couvre build_package.py, build_unix.py et leurs semblables : ce
# sont des outils d'integration, pas l'application.
HORS_APPLICATION = ('build_',)


def _premier_argument_texte(noeud):
    """Le programme appele, quand il se lit directement dans le code."""
    if not noeud.args:
        return ''
    premier = noeud.args[0]
    if isinstance(premier, ast.Constant) and isinstance(premier.value, str):
        return premier.value
    if isinstance(premier, (ast.List, ast.Tuple)) and premier.elts:
        tete = premier.elts[0]
        if isinstance(tete, ast.Constant) and isinstance(tete.value, str):
            return tete.value
    return ''


def _hors_windows(test: ast.AST, dans_le_sinon: bool) -> bool:
    """Cette branche est-elle inatteignable sous Windows ?

    Deux formes reviennent partout :
        if os.name == "nt": ...  else: <ici, jamais sous Windows>
        if sys.platform == "darwin" / startswith("linux"): <ici non plus>

    Sans cela, le controle signalait du code parfaitement sain — un
    `xdg-open` dans le `else` d'un test Windows, par exemple — et un
    controle qui crie au loup finit par ne plus etre lu.
    """
    texte = ast.dump(test).lower()
    windows = any(m in texte for m in ("'nt'", '"nt"', "win32", "'win'", 'startswith'))
    autre = any(m in texte for m in ("darwin", "linux"))
    if dans_le_sinon and windows and not autre:
        return True
    if not dans_le_sinon and autre and 'win' not in texte:
        return True
    return False


def _appels_atteignables(arbre):
    """Parcourt l'arbre en ecartant les branches inatteignables sous Windows."""
    def descendre(noeud):
        if isinstance(noeud, ast.If):
            for branche, dans_le_sinon in ((noeud.body, False), (noeud.orelse, True)):
                if _hors_windows(noeud.test, dans_le_sinon):
                    continue
                for enfant in branche:
                    yield from descendre(enfant)
            yield from descendre(noeud.test)
            return
        if isinstance(noeud, ast.Call):
            yield noeud
        for enfant in ast.iter_child_nodes(noeud):
            yield from descendre(enfant)

    yield from descendre(arbre)


def suspects(chemin: pathlib.Path):
    try:
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
    except (OSError, SyntaxError):
        return []

    trouves = []
    for noeud in _appels_atteignables(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        cible = noeud.func
        if not (isinstance(cible, ast.Attribute) and cible.attr in LANCEURS):
            continue
        if getattr(cible.value, 'id', '') != 'subprocess':
            continue
        if any(m.arg == 'creationflags' for m in noeud.keywords):
            continue
        programme = _premier_argument_texte(noeud).lower()
        if programme.rsplit('\\', 1)[-1].replace('.exe', '') in SANS_CONSOLE_PAR_NATURE:
            continue
        trouves.append((noeud.lineno, cible.attr, programme or '?'))
    return trouves


def main(argv):
    cibles = [pathlib.Path(a) for a in argv[1:]] or sorted(
        pathlib.Path.cwd().glob('*.py'))
    total = 0
    for chemin in cibles:
        if chemin.name == pathlib.Path(__file__).name:
            continue
        if chemin.name.startswith(
                HORS_APPLICATION + ('_', 'fix_', 'test_', 'verifier_')):
            continue
        for ligne, lanceur, programme in suspects(chemin):
            print(f"{chemin.name}:{ligne}: subprocess.{lanceur}({programme}) "
                  f"sans creationflags — une console clignotera")
            total += 1
    if total:
        print(f"\n{total} sous-processus sans CREATE_NO_WINDOW.")
        return 1
    print(f"{len(cibles)} fichier(s) verifie(s) : aucune console parasite.")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
