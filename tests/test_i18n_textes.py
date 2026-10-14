# -*- coding: utf-8 -*-
"""Aucun texte d'interface écrit en dur : tout passe par _tr(en, fr).

L'interface est bilingue (anglais / français, langue du système au premier
lancement, choix retenu dans les réglages). Un texte passé tel quel à un
widget s'affiche dans une seule langue, quelle que soit celle choisie : ce
test les attrape avant qu'ils n'arrivent chez l'utilisateur.

Méthode : analyse syntaxique (AST) des modules d'interface. Pour chaque appel
qui affiche un texte (setText, QLabel(...), QMessageBox.information...), le
texte doit être un appel de traduction, une variable, ou une chaîne purement
technique (nom de produit, unité, sigle). Les morceaux littéraux d'une
f-string sont examinés un à un, balises HTML retirées.

Un second contrôle vérifie que la partie anglaise de _tr(en, fr) ne contient
pas de français (accents) : c'est l'erreur d'inversion des arguments.

    python -m pytest -q tests/test_i18n_textes.py
"""
import ast
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

#: modules dont les textes s'affichent dans l'application. fits_analyser_gui.py
#: n'y figure pas : c'est le moteur d'analyse (plus une ancienne interface
#: autonome, FitsAnalyserGUI, que l'application n'ouvre jamais).
SOURCES = ['astromanager.py', 'shortcut_helper.py', 'gui']

METHODES = {'setText', 'setWindowTitle', 'setToolTip', 'setPlaceholderText',
            'addAction', 'addMenu', 'setTitle', 'showMessage', 'setStatusTip',
            'addTab', 'setLabelText', 'addItem', 'setInformativeText',
            'setDetailedText', 'setWhatsThis', 'insertTab', 'setTabText'}
CONSTRUCTEURS = {'QLabel', 'QPushButton', 'QCheckBox', 'QGroupBox', 'QAction',
                 'QRadioButton', 'QMenu', 'QToolButton'}
BOITES = {'information', 'warning', 'critical', 'question', 'about'}
TRADUCTIONS = {'_tr', '_T', 'tr'}

#: mots identiques dans les deux langues : noms propres, sigles, unités
TECHNIQUES = {
    'astromanager', 'fits', 'xisf', 'fz', 'fwhm', 'hfr', 'snr', 'px', 'ch',
    'ra', 'dec', 'utc', 'aitoff', 'mollweide', 'english', 'français', 'total',
    'nina', 'asiair', 'simbad', 'astap', 'pixinsight', 'zstd', 'lz4', 'zlib',
    'ngc', 'ic', 'messier', 'wcs', 'adu', 'iso', 'gb', 'mb', 'ko', 'mo', 'go',
    'kb', 'cpu', 'ram', 'os', 'python', 'csv', 'pdf', 'html', 'latex', 'v',
    'ha', 'oiii', 'sii', 'lrgb', 'rgb', 'alt', 'az', 'jd', 'mjd', 'arcsec',
    'ctrl', 'shift', 'f1', 'esc', 'ok', 'sql', 'id', 'hdr',
}
BALISE = re.compile(r'<[^>]*>|&[a-z]+;|&#\d+;')
MOT = re.compile(r"[A-Za-zÀ-ÿ]{2,}")
FRANCAIS = re.compile(r"[éèàçêôûùîïœ«»]")


def _textes_litteraux(noeud):
    """Morceaux de texte littéral d'une chaîne ou d'une f-string."""
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
        return [noeud.value]
    if isinstance(noeud, ast.JoinedStr):
        return [v.value for v in noeud.values
                if isinstance(v, ast.Constant) and isinstance(v.value, str)]
    return []


def _mots_a_traduire(texte):
    texte = BALISE.sub(' ', texte)
    return [m for m in MOT.findall(texte) if m.lower() not in TECHNIQUES]


def _fichiers():
    for nom in SOURCES:
        chemin = RACINE / nom
        if chemin.is_dir():
            yield from sorted(chemin.rglob('*.py'))
        else:
            yield chemin


def _nom_appel(appel):
    f = appel.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return ''


def _arguments_affiches(appel):
    nom = _nom_appel(appel)
    if nom in METHODES or nom in CONSTRUCTEURS:
        return appel.args[:1]
    if (nom in BOITES and isinstance(appel.func, ast.Attribute)
            and getattr(appel.func.value, 'id', '') == 'QMessageBox'):
        return appel.args[1:3]
    return []


def test_aucun_texte_en_dur():
    fautes = []
    for fichier in _fichiers():
        arbre = ast.parse(fichier.read_text(encoding='utf-8'))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            for arg in _arguments_affiches(noeud):
                mots = [m for t in _textes_litteraux(arg) for m in _mots_a_traduire(t)]
                if mots:
                    fautes.append(f"{fichier.relative_to(RACINE)}:{noeud.lineno} "
                                  f"{_nom_appel(noeud)} -> {' '.join(mots[:6])}")
    assert not fautes, ("Textes affichés sans traduction :\n  "
                        + "\n  ".join(fautes))


def test_partie_anglaise_sans_francais():
    fautes = []
    for fichier in _fichiers():
        arbre = ast.parse(fichier.read_text(encoding='utf-8'))
        for noeud in ast.walk(arbre):
            if not (isinstance(noeud, ast.Call) and _nom_appel(noeud) in TRADUCTIONS
                    and len(noeud.args) >= 2):
                continue
            # _T(fr, en) dans shortcut_helper.py, _tr(en, fr) ailleurs
            anglais = noeud.args[1] if _nom_appel(noeud) == '_T' else noeud.args[0]
            for texte in _textes_litteraux(anglais):
                if FRANCAIS.search(BALISE.sub(' ', texte)):
                    fautes.append(f"{fichier.relative_to(RACINE)}:{noeud.lineno} "
                                  f"{texte[:60]!r}")
    assert not fautes, ("Français dans la partie anglaise :\n  "
                        + "\n  ".join(fautes))


def test_detection_langue_systeme(monkeypatch):
    import sys
    sys.path.insert(0, str(RACINE))
    from core import i18n
    import locale
    # Repli sans Qt : la locale Windows « French_France » doit donner 'fr'
    monkeypatch.setitem(sys.modules, 'PyQt6.QtCore', None)
    for valeur, attendu in (('French_France', 'fr'), ('fr_FR', 'fr'),
                            ('en_US', 'en'), ('German_Germany', 'en')):
        monkeypatch.setattr(locale, 'getlocale', lambda v=valeur: (v, 'UTF-8'))
        assert i18n.detect_system_language() == attendu, valeur
