# -*- coding: utf-8 -*-
"""Cohérence du kit commun de publication (installeur, mise à jour, paquets).

Ces divergences ne se voient que chez l'utilisateur : un verrou nommé que
l'installeur ne reconnaît pas (installation par-dessus l'application ouverte,
sans rien remplacer), un numéro de version écrit à deux endroits, une clé de
kit.json oubliée par build_unix.py.
"""
import json
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
KIT = json.loads((RACINE / 'kit.json').read_text(encoding='utf-8'))


def test_verrou_nomme_identique_a_l_installeur():
    iss = (RACINE / 'installer.iss').read_text(encoding='utf-8')
    assert 'AppMutex={#AppName}EnCours' in iss
    attendu = KIT['nom_fichier'] + 'EnCours'
    sources = ''.join(p.read_text(encoding='utf-8') for p in
                      [RACINE / KIT['point_entree'], *(RACINE / 'gui').glob('*.py')])
    assert f"'{attendu}'" in sources or f'"{attendu}"' in sources, attendu


def test_version_unique():
    version = (RACINE / KIT['fichier_version']).read_text(encoding='utf-8').strip()
    assert re.fullmatch(r'\d+\.\d+\.\d+', version)
    import sys
    sys.path.insert(0, str(RACINE))
    from core import __version__
    assert __version__ == version


def test_kit_json_complet():
    for cle in ('nom_technique', 'nom_fichier', 'nom_affiche', 'depot_distribution',
                'point_entree', 'icone', 'appid', 'icone_png', 'description_fr',
                'description_en', 'categories_linux'):
        assert KIT.get(cle), cle
    for chemin in [KIT['point_entree'], KIT['icone_png'], *KIT['modules'],
                   *KIT['paquets'], *KIT['assets']]:
        assert (RACINE / chemin.replace('\\', '/')).exists(), chemin


def test_un_seul_workflow_de_publication():
    wf = RACINE / '.github' / 'workflows'
    publient = [p.name for p in wf.glob('*.yml')
                if 'action-gh-release' in p.read_text(encoding='utf-8')
                or 'gh release create' in p.read_text(encoding='utf-8')]
    assert publient == ['release.yml'], publient
