#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AstroManager - Observatory instruments (Observatoire de Haute-Provence)
=======================================================================
Professional and teaching telescopes whose images reach amateur archives,
notably through the "DU Explorer et Comprendre l'Univers" (DU ECU) of the
Observatoire de Paris, which observes remotely with two OHP telescopes:

* T120 -- 1.20 m Newtonian, f/6, measured focal length 7 232 mm
  (OHP, page "Le télescope de 120cm",
  https://ohp.osupytheas.fr/le-telescope-de-120cm/). The astrometric image
  scale of DU ECU frames gives ~7 234 mm. Cameras:
    - Andor iKon-L 936 CCD, 2048 x 2048 px of 13.5 um, read in 2x2 binning
      (27 um, 0.770"/px); one 2016 night in 1x1 (0.385"/px).
      Datasheet: https://andor.oxinst.com/products/ikon-large-ccd-series/ikon-l-936
    - Andor Marana 4.2B-11 sCMOS (2026), 2048 x 2048 px of 11 um, read in
      2x2 binning (22 um, 0.627"/px).
      Datasheet: https://andor.oxinst.com/products/scmos-camera-series/marana-scmos
* IRIS -- 0.50 m remotely operated teaching telescope at OHP, focal length
  ~4 072 mm (f/8.1). Cameras: FLI ProLine 2048 x 2048 px of 13.5 um
  (0.684"/px) and FLI ProLine 4096 x 4096 px of 9 um (0.456"/px).

Header keywords actually written at these telescopes (MaxIm DL, ACP):

    TELESCOP  'OHP T120' | 'IRIS OHP' | 'ACP->NTM' (= IRIS driven by ACP)
    OBSERVAT  'IRiS' (IRIS only)
    INSTRUME  'Andor Tech' (iKon-L) | 'Andor sCMOS (SDK3)' (Marana)
              'flipro0:PL0394113' (ProLine 2048) | 'flipro0:PL1344016'
              (ProLine 4096) | 'FLI' (either ProLine)
    APTDIA    1200 | 500        FOCALLEN  7200 (T120) | ~4072 (IRIS)
    XPIXSZ    pixel size AFTER binning (MaxIm DL convention), XBINNING
    NAXIS1    1024 (T120, bin 2) | 2048 | 4096

'ACP->NTM' is the generic telescope string of the ACP automation software:
it identifies IRIS only together with OBSERVAT = 'IRiS', never alone.
'Andor Tech' and 'FLI' are generic as well; the camera is resolved from the
telescope, the serial number, the native pixel size (XPIXSZ / XBINNING) or
the native width (NAXIS1 x XBINNING).

The module has no dependency: it reads any mapping with a ``get`` method
(astropy ``Header``, plain dict built from XISF FITSKeyword elements).
"""

from __future__ import annotations

import html
from typing import Any, Dict, Optional

ARCSEC_PER_RADIAN = 206264.80624709636

# ---------------------------------------------------------------------------
# Telescopes (same fields as TELESCOPES_DATABASE)
# ---------------------------------------------------------------------------

OBSERVATORY_TELESCOPES: Dict[str, Dict[str, float]] = {
    # Measured focal length 7 232 mm / 1 200 mm aperture
    'OHP T120': {'diameter_mm': 1200.0, 'focal_length_mm': 7232.0, 'f_number': 6.03},
    # FOCALLEN of IRIS frames: 4 070 to 4 073 mm; 4 072 / 500 = f/8.14
    'OHP IRIS': {'diameter_mm': 500.0, 'focal_length_mm': 4072.0, 'f_number': 8.14},
}

# ---------------------------------------------------------------------------
# Cameras (same fields as SENSORS_DATABASE). 'gain' is in e-/ADU.
# ---------------------------------------------------------------------------

OBSERVATORY_CAMERAS: Dict[str, Dict[str, float]] = {
    # Andor datasheet: 2048 x 2048, 13.5 um, well 100 000 e-, read noise
    # 2.9 e-, QE > 90 % (back-illuminated). Gain not published per camera:
    # estimated as well depth / 2^16.
    'Andor iKon-L 936': {'gain': 1.53, 'read_noise': 2.9, 'full_well': 100000, 'pixel_size': 13.5,
                         'quantum_efficiency': 0.9, 'width_px': 2048, 'height_px': 2048},
    # Andor datasheet: 2048 x 2048, 11 um, well 85 000 e- (16-bit HDR),
    # read noise 1.6 e- median, QE up to 95 %. Gain estimated as above.
    'Andor Marana 4.2B-11': {'gain': 1.30, 'read_noise': 1.6, 'full_well': 85000, 'pixel_size': 11.0,
                             'quantum_efficiency': 0.95, 'width_px': 2048, 'height_px': 2048},
    # IRIS cameras: geometry from the headers; EGAIN = 1.5 e-/ADU in the
    # headers of PL0394113. Noise / well: generic values of the FLI ProLine
    # entries of this database (not published per serial number).
    'FLI ProLine 2048': {'gain': 1.5, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 13.5,
                         'quantum_efficiency': 0.85, 'width_px': 2048, 'height_px': 2048},
    'FLI ProLine 4096': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 9.0,
                         'quantum_efficiency': 0.6, 'width_px': 4096, 'height_px': 4096},
}

# Exact header strings that are unambiguous on their own (serial numbers,
# telescope names). Generic strings ('Andor Tech', 'FLI', 'ACP->NTM') are
# resolved by detect_observatory_equipment() only.
OBSERVATORY_TELESCOPE_HEADER_MAPPING: Dict[str, str] = {
    'OHP T120': 'OHP T120',
    'T120 OHP': 'OHP T120',
    'IRIS OHP': 'OHP IRIS',
    'OHP IRIS': 'OHP IRIS',
}
OBSERVATORY_INSTRUMENT_HEADER_MAPPING: Dict[str, str] = {
    'FLIPRO0:PL0394113': 'FLI ProLine 2048',
    'PL0394113': 'FLI ProLine 2048',
    'FLIPRO0:PL1344016': 'FLI ProLine 4096',
    'PL1344016': 'FLI ProLine 4096',
    'ANDOR MARANA 4.2B-11': 'Andor Marana 4.2B-11',
}

SOURCES = {
    'OHP T120': 'https://ohp.osupytheas.fr/le-telescope-de-120cm/',
    'Andor iKon-L 936': 'https://andor.oxinst.com/products/ikon-large-ccd-series/ikon-l-936',
    'Andor Marana 4.2B-11': 'https://andor.oxinst.com/products/scmos-camera-series/marana-scmos',
}


# ---------------------------------------------------------------------------
# Header helpers
# ---------------------------------------------------------------------------

def _value(header: Any, key: str) -> Any:
    try:
        return header.get(key)
    except Exception:
        return None


def _text(header: Any, key: str) -> str:
    """Header string, upper-cased, without FITS quotes nor XML escapes."""
    v = _value(header, key)
    if v is None:
        return ''
    s = html.unescape(str(v)).strip()
    if len(s) >= 2 and s[0] == s[-1] == "'":
        s = s[1:-1].strip()
    return s.upper()


def _number(header: Any, key: str) -> Optional[float]:
    v = _value(header, key)
    if v is None:
        return None
    try:
        return float(str(v).strip().strip("'"))
    except (TypeError, ValueError):
        return None


def _near(value: Optional[float], target: float, tolerance: float) -> bool:
    return value is not None and abs(value - target) <= tolerance


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detect_observatory_telescope(header: Any) -> Optional[str]:
    """'OHP T120', 'OHP IRIS' or None."""
    tel = _text(header, 'TELESCOP')
    obs = _text(header, 'OBSERVAT')
    if tel in OBSERVATORY_TELESCOPE_HEADER_MAPPING:
        return OBSERVATORY_TELESCOPE_HEADER_MAPPING[tel]
    if obs == 'IRIS':                       # 'IRiS', whatever TELESCOP says ('ACP->NTM')
        return 'OHP IRIS'
    if 'OHP' in tel and 'T120' in tel.replace(' ', ''):
        return 'OHP T120'
    if 'OHP' in tel and 'IRIS' in tel:
        return 'OHP IRIS'
    # TELESCOP missing or technical: aperture and focal length of the header
    aperture = _number(header, 'APTDIA')
    focal = _number(header, 'FOCALLEN')
    if not tel or '->' in tel:
        if _near(aperture, 1200.0, 5.0) and _near(focal, 7232.0, 150.0):
            return 'OHP T120'
        if _near(aperture, 500.0, 2.0) and _near(focal, 4072.0, 40.0):
            return 'OHP IRIS'
    return None


def _native_pixel(header: Any) -> Optional[float]:
    """Unbinned pixel size: MaxIm DL writes XPIXSZ after binning."""
    pix = _number(header, 'XPIXSZ')
    binning = _number(header, 'XBINNING') or 1.0
    if pix is None or binning <= 0:
        return None
    return pix / binning


def detect_observatory_camera(header: Any, telescope: Optional[str] = None) -> Optional[str]:
    """Camera key of OBSERVATORY_CAMERAS, or None."""
    inst = _text(header, 'INSTRUME')
    for key, camera in OBSERVATORY_INSTRUMENT_HEADER_MAPPING.items():
        if key in inst:
            return camera
    telescope = telescope or detect_observatory_telescope(header)
    native = _native_pixel(header)
    binning = _number(header, 'XBINNING') or 1.0
    width = _number(header, 'NAXIS1')
    native_width = width * binning if width else None
    if telescope == 'OHP T120':
        if 'SCMOS' in inst or 'MARANA' in inst or _near(native, 11.0, 0.3):
            return 'Andor Marana 4.2B-11'
        if 'ANDOR' in inst or 'IKON' in inst or _near(native, 13.5, 0.2):
            return 'Andor iKon-L 936'
    if telescope == 'OHP IRIS':
        if _near(native, 13.5, 0.2) or (native is None and _near(native_width, 2048, 1)):
            return 'FLI ProLine 2048'
        if _near(native, 9.0, 0.2) or (native is None and _near(native_width, 4096, 1)):
            return 'FLI ProLine 4096'
    return None


def detect_observatory_equipment(header: Any) -> Optional[Dict[str, Any]]:
    """Recognise an OHP telescope / camera from a FITS or XISF header.

    Returns None when the frame does not come from a known observatory
    instrument; otherwise a dict with the canonical telescope and camera
    names, the binning, the native and effective pixel sizes and the image
    scale computed from the reference focal length.
    """
    if header is None:
        return None
    telescope = detect_observatory_telescope(header)
    if telescope is None:
        return None
    camera = detect_observatory_camera(header, telescope)
    tel = OBSERVATORY_TELESCOPES[telescope]
    binning = int(_number(header, 'XBINNING') or 1)
    result: Dict[str, Any] = {
        'observatory': 'Observatoire de Haute-Provence',
        'telescope': telescope,
        'camera': camera,
        'binning': binning,
        'diameter_mm': tel['diameter_mm'],
        'focal_length_mm': tel['focal_length_mm'],
        'f_number': tel['f_number'],
        'focal_length_header_mm': _number(header, 'FOCALLEN'),
        'pixel_size_um': None,
        'effective_pixel_um': None,
        'image_scale_arcsec': None,
    }
    if camera:
        pixel = OBSERVATORY_CAMERAS[camera]['pixel_size']
        effective = pixel * binning
        result['pixel_size_um'] = pixel
        result['effective_pixel_um'] = effective
        result['image_scale_arcsec'] = round(ARCSEC_PER_RADIAN * effective * 1e-3 / tel['focal_length_mm'], 3)
    return result
