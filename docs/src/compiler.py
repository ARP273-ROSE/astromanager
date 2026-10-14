#!/usr/bin/env python3
"""Compile les manuels PDF d'AstroManager (format maison), FR et EN.

    python3 docs/src/compiler.py          (depuis la racine du dépôt)

Sources : docs/src/manuel-fr.tex et docs/src/manuel-en.tex ;
captures réelles : docs/captures/ (refaites par docs/captures.py). Sorties :
docs/manuel-fr.pdf et docs/manuel-en.pdf, livrés avec le programme et ouverts
par Aide > Manuel (PDF). pdflatex deux fois (table des matières), puis
suppression des fichiers temporaires.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
RACINE = SRC.parents[1]
if os.environ.get("TEXLIVE_BIN"):
    os.environ["PATH"] = os.environ["TEXLIVE_BIN"] + os.pathsep + os.environ.get("PATH", "")


def compiler(langue: str) -> None:
    version = (RACINE / "VERSION").read_text(encoding="utf-8").strip()
    (SRC / "version.tex").write_text(f"\\newcommand{{\\VERSIONAPP}}{{{version}}}\n",
                                     encoding="utf-8")
    nom = f"manuel-{langue}"
    try:
        for _ in range(2):
            r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                                f"{nom}.tex"], cwd=SRC, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            if r.returncode != 0:
                print(r.stdout[-3000:])
                raise SystemExit(f"échec de la compilation de {nom}.tex")
        journal = (SRC / f"{nom}.log").read_text(encoding="utf-8", errors="replace")
        if re.search(r"Overfull \\hbox \((\d{2,}|[5-9])\.", journal):
            print(f"  attention : ligne trop longue dans {nom} (voir le journal)")
        shutil.copy2(SRC / f"{nom}.pdf", RACINE / "docs" / f"{nom}.pdf")
    finally:
        for ext in (".aux", ".log", ".out", ".toc", ".pdf"):
            (SRC / f"{nom}{ext}").unlink(missing_ok=True)
        (SRC / "version.tex").unlink(missing_ok=True)
    info = subprocess.run(["pdfinfo", str(RACINE / "docs" / f"{nom}.pdf")],
                          capture_output=True, text=True).stdout if shutil.which("pdfinfo") else ""
    n = re.search(r"Pages:\s+(\d+)", info)
    print(f"  docs/{nom}.pdf : {n.group(1) if n else '?'} pages")


if __name__ == "__main__":
    for lg in (sys.argv[1:] or ["fr", "en"]):
        compiler(lg)
