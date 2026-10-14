# -*- coding: utf-8 -*-
"""Interface sous Xvfb : la fenêtre s'ouvre dans les deux langues et le kit
commun (mise à jour, rapports, accord, vigie) y est branché.

    xvfb-run -a python -m pytest -q tests/test_gui.py

Le dossier personnel est remplacé par un dossier temporaire AVANT tout import
de l'application : la configuration et la base y sont créées, jamais dans le
vrai profil de la machine qui lance les tests.
"""
import os
import sys
import tempfile
from pathlib import Path

_HOME = tempfile.mkdtemp(prefix='astromanager-test-')
os.environ['HOME'] = _HOME
os.environ['APPDATA'] = _HOME
os.environ.setdefault('QT_QPA_PLATFORM', 'xcb' if os.environ.get('DISPLAY') else 'offscreen')

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import pytest  # noqa: E402

PyQt6 = pytest.importorskip('PyQt6')
from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

APP = QApplication.instance() or QApplication([])


def _fenetre(lang):
    from core.config import get_config
    get_config().set('application.language', lang)
    from gui.main_window import AstroManagerWindow
    win = AstroManagerWindow()
    assert win.lang == lang
    return win


def _textes_du_menu(win):
    textes = []
    for action in win.menuBar().actions():
        textes.append(action.text())
        if action.menu():
            textes += [a.text() for a in action.menu().actions() if a.text()]
    return textes


@pytest.mark.parametrize('lang', ['en', 'fr'])
def test_fenetre_et_menu_aide(lang):
    win = _fenetre(lang)
    win.show()
    APP.processEvents()
    textes = _textes_du_menu(win)
    attendu = 'Report a &problem...' if lang == 'en' else 'Signaler un &problème...'
    assert attendu in textes
    assert win.auto_report_action.isCheckable()
    if lang == 'en':
        # rien de français dans l'interface anglaise (menus et onglets)
        onglets = [win.tab_widget.tabText(i) for i in range(win.tab_widget.count())]
        for t in textes + onglets:
            assert not any(c in t for c in 'éèàçêôûù'), t
    win.close()


def test_resultat_de_mise_a_jour_sans_nouveaute(monkeypatch):
    win = _fenetre('en')
    vus = []
    monkeypatch.setattr(QMessageBox, 'information',
                        lambda *a, **k: vus.append(a[2]))
    win._on_update_result(None, True)
    assert vus and 'up to date' in vus[0]
    win._on_update_result(None, False)          # silencieux : aucun message
    assert len(vus) == 1
    win.close()


def test_recherche_de_mise_a_jour_passe_par_le_kit(monkeypatch):
    import updater
    appels = []
    monkeypatch.setattr(updater, 'check', lambda v: appels.append(v) or None)
    win = _fenetre('fr')
    win._check_for_updates(silent=True)
    win._update_thread.join(5)
    APP.processEvents()
    assert appels and appels[0]
    win.close()


def test_accord_rapports_et_case_du_menu(monkeypatch):
    import reporting
    reporting.init(Path(_HOME) / 'rapports', application='astromanager-test',
                   version='0')
    win = _fenetre('fr')
    reporting.definir_consentement(False)
    monkeypatch.setattr(reporting, 'signaler_demarrage', lambda **k: None)
    win._ask_report_consent()                   # déjà répondu : pas de boîte
    win.auto_report_action.setChecked(True)
    assert reporting.consentement() is True
    win.auto_report_action.setChecked(False)
    assert reporting.consentement() is False
    win.close()


def test_check_en_ligne_de_commande():
    import subprocess
    r = subprocess.run([sys.executable, '-B', str(RACINE / 'astromanager.py'), '--check'],
                       capture_output=True, text=True, timeout=180,
                       env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
    assert r.returncode == 0, r.stdout + r.stderr
    assert 'OK' in r.stdout
