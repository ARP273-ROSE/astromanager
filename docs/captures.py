"""Captures RÉELLES de la fenêtre pour le manuel, dans les deux langues.

    QT_QPA_PLATFORM=offscreen python docs/captures.py      (depuis la racine)

Même fenêtre et même style figé que le programme livré. Le dossier personnel
est détourné vers un dossier temporaire : configuration et base vides, aucun
nom ni chemin réel dans les images.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_TMP = tempfile.mkdtemp(prefix="astromanager-captures-")
os.environ["HOME"] = _TMP
os.environ["APPDATA"] = _TMP
RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
SORTIE = RACINE / "docs" / "captures"

ONGLETS = [("principal", "analysis_tab"), ("compression", "compression_tab"),
           ("qualite", "quality_tab"), ("ciel", "sky_chart_tab")]


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    from gui.main_window import AstroManagerWindow, create_application
    from core.config import get_config
    app = create_application()
    for langue in ("fr", "en"):
        get_config().set("application.language", langue)
        w = AstroManagerWindow()
        w.resize(1360, 860)
        w.show()
        app.processEvents()
        for nom, attribut in ONGLETS:
            w.tab_widget.setCurrentWidget(getattr(w, attribut))
            for _ in range(5):
                app.processEvents()
            w.grab().save(str(SORTIE / f"{langue}-{nom}.png"))
        w.close()
    print(f"captures écrites dans {SORTIE}")


if __name__ == "__main__":
    main()
