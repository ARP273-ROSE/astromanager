#!/usr/bin/env python3
"""Logo d'AstroManager : UNE source SVG, tout le reste en est rendu.

    QT_QPA_PLATFORM=offscreen python assets/make_logo.py      (Pillow requis)

Sorties dans assets/ : icon.svg (la source), icon.png (1024, icône de
fenêtre), icon_{16,32,64,128,256,512}.png (entrée de menu Linux, À propos,
manuel), icon.ico (installeur Windows, multi-tailles) et icon.icns (macOS).
Motif : ciel étoilé, lunette dorée sur trépied, galaxie spirale et nébuleuse
rouge — le même que l'ancienne icône matricielle, redessiné en vecteurs.
"""
import math
import random
import sys
from pathlib import Path

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

ICI = Path(__file__).resolve().parent
OR = "#c9a24e"


def etoile(x, y, r, op):
    """Étoile à quatre branches (scintillement)."""
    p = (f"M{x:.1f},{y - r:.1f} Q{x + r * .18:.1f},{y - r * .18:.1f} {x + r:.1f},{y:.1f} "
         f"Q{x + r * .18:.1f},{y + r * .18:.1f} {x:.1f},{y + r:.1f} "
         f"Q{x - r * .18:.1f},{y + r * .18:.1f} {x - r:.1f},{y:.1f} "
         f"Q{x - r * .18:.1f},{y - r * .18:.1f} {x:.1f},{y - r:.1f}Z")
    return f'<path d="{p}" fill="#f3e6bf" opacity="{op:.2f}"/>'


def spirale(cx, cy, depart):
    pts = []
    for i in range(60):
        t = i / 59
        a = depart + t * 3.4
        r = 6 + t * 56
        pts.append(f"{cx + r * math.cos(a):.1f},{cy + r * math.sin(a):.1f}")
    return f'<polyline points="{" ".join(pts)}" fill="none" stroke="#5f93ae" stroke-width="8" stroke-linecap="round" opacity="0.9"/>'


def construire_svg() -> str:
    alea = random.Random(273)                     # étoiles fixes d'un rendu à l'autre
    etoiles = []
    for _ in range(46):
        x, y = alea.uniform(60, 452), alea.uniform(60, 452)
        if 150 < x < 330 and 180 < y < 420 or (x - 372) ** 2 + (y - 132) ** 2 < 70 ** 2 or (x - 150) ** 2 + (y - 150) ** 2 < 60 ** 2:       # place de la lunette
            continue
        etoiles.append(etoile(x, y, alea.uniform(3, 9), alea.uniform(0.55, 1)))
    galaxie = "\n  ".join(spirale(372, 132, d) for d in (0, math.pi * 2 / 3, math.pi * 4 / 3))
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="512" height="512" viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="neb" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ff5a5a" stop-opacity="0.95"/>
      <stop offset="55%" stop-color="#d2343f" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="#d2343f" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="coeur" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#fff3cf"/>
      <stop offset="100%" stop-color="#f3dd9a" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect x="16" y="16" width="480" height="480" rx="104" fill="#0a1424"/>
  {chr(10).join("  " + e for e in etoiles)}
  <circle cx="150" cy="150" r="66" fill="url(#neb)"/>
  <circle cx="150" cy="150" r="13" fill="#8e1a22"/>
  <circle cx="150" cy="150" r="3.5" fill="#f29b4a"/>
  {galaxie}
  <circle cx="372" cy="132" r="20" fill="url(#coeur)"/>
  <circle cx="372" cy="132" r="10" fill="#f6e7b8"/>
  <g stroke="{OR}" stroke-width="13" stroke-linecap="round" fill="none">
    <line x1="256" y1="300" x2="212" y2="410"/>
    <line x1="256" y1="300" x2="300" y2="410"/>
    <line x1="229" y1="366" x2="283" y2="366"/>
  </g>
  <g transform="rotate(-50 256 280)">
    <rect x="168" y="262" width="168" height="36" rx="6" fill="none" stroke="{OR}" stroke-width="12"/>
    <rect x="328" y="252" width="32" height="56" rx="5" fill="{OR}"/>
    <rect x="150" y="268" width="22" height="24" rx="4" fill="{OR}"/>
    <line x1="196" y1="262" x2="250" y2="298" stroke="{OR}" stroke-width="9"/>
    <line x1="250" y1="262" x2="304" y2="298" stroke="{OR}" stroke-width="9"/>
  </g>
  <circle cx="256" cy="296" r="17" fill="{OR}"/>
</svg>
'''


def rendre(svg: Path, sortie: Path, taille: int) -> None:
    img = QImage(taille, taille, QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    QSvgRenderer(str(svg)).render(p, QRectF(0, 0, taille, taille))
    p.end()
    img.save(str(sortie), "PNG")


def main():
    app = QApplication(sys.argv)  # noqa: F841 — requis pour le rendu
    svg = ICI / "icon.svg"
    svg.write_text(construire_svg(), encoding="utf-8")
    for taille in (16, 32, 64, 128, 256, 512):
        rendre(svg, ICI / f"icon_{taille}.png", taille)
    rendre(svg, ICI / "icon.png", 1024)
    from PIL import Image
    img = Image.open(ICI / "icon.png").convert("RGBA")
    img.save(ICI / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                      (64, 64), (128, 128), (256, 256)])
    img.save(ICI / "icon.icns")
    print("icon.svg -> icon.png, icon_*.png, icon.ico, icon.icns")


if __name__ == "__main__":
    main()
