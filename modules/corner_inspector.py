#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - CORNER INSPECTOR MODULE
================================================================================
Optical quality inspection across 9 image regions (4 corners, 4 edges, center).
Inspired by Astronalyze's corner inspector feature.

Crops the image at 100% zoom into 9 regions, computes per-region FWHM
statistics from a pre-existing star list, equalizes sky backgrounds, and
produces annotated QImage overlays with color-coded star markers.

Features:
  - 9-region crop extraction (TL, T, TR, L, C, R, BL, B, BR)
  - Per-region star filtering with top-25-by-flux selection
  - FWHM statistics per region (median, mean, std, min, max, count)
  - Sky-background equalization via 10th-percentile matching
  - Annotated QImage generation with FWHM color-coded circles (QPainter)
  - Summary table with quality grading (Excellent / Good / Fair / Poor)

Requires numpy.  PyQt6 is feature-gated (annotation rendering only).
================================================================================
"""

import logging
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

# Feature-gated PyQt6 imports (only needed for annotate_crop)
HAS_PYQT = False
try:
    from PyQt6.QtCore import QPointF, QRectF, Qt
    from PyQt6.QtGui import (
        QColor,
        QFont,
        QImage,
        QPainter,
        QPen,
    )
    HAS_PYQT = True
except ImportError:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Region keys in reading order (top-left → bottom-right)
REGION_KEYS: Tuple[str, ...] = ('TL', 'T', 'TR', 'L', 'C', 'R', 'BL', 'B', 'BR')

# FWHM thresholds for quality grading (pixels)
_GRADE_EXCELLENT = 2.5
_GRADE_GOOD = 3.5
_GRADE_FAIR = 5.0

# Maximum number of stars kept per region (brightest by flux)
_MAX_STARS_PER_REGION = 25

# Percentile used for sky-background equalization
_SKY_PERCENTILE = 10.0

# Annotation defaults
_CIRCLE_RADIUS_BASE = 12       # base circle radius around each star (pixels)
_FONT_SIZE = 10                # annotation font size
_FWHM_COLOR_GOOD = 2.5        # green threshold
_FWHM_COLOR_OK = 4.0          # yellow threshold; above = red


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fwhm_to_color(fwhm: float) -> Tuple[int, int, int]:
    """Map a FWHM value to an (R, G, B) color tuple.

    Green (<= 2.5 px) → Yellow (<= 4.0 px) → Red (> 4.0 px) with smooth
    linear interpolation between thresholds.
    """
    if fwhm <= _FWHM_COLOR_GOOD:
        return (0, 220, 60)  # green
    elif fwhm <= _FWHM_COLOR_OK:
        # Interpolate green → yellow
        t = (fwhm - _FWHM_COLOR_GOOD) / (_FWHM_COLOR_OK - _FWHM_COLOR_GOOD)
        r = int(220 * t)
        g = 220
        b = int(60 * (1.0 - t))
        return (r, g, b)
    else:
        # Interpolate yellow → red (cap at fwhm=8.0 for full red)
        t = min((fwhm - _FWHM_COLOR_OK) / 4.0, 1.0)
        r = 220
        g = int(220 * (1.0 - t))
        return (r, g, 0)


def _compute_stats(stars: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute FWHM statistics from a list of star dicts.

    Returns a dict with median_fwhm, mean_fwhm, std_fwhm, min_fwhm,
    max_fwhm, star_count.  All values are 0.0 / 0 when the list is empty.
    """
    if not stars:
        return {
            'median_fwhm': 0.0,
            'mean_fwhm': 0.0,
            'std_fwhm': 0.0,
            'min_fwhm': 0.0,
            'max_fwhm': 0.0,
            'star_count': 0,
        }

    fwhm_values = np.array([s['fwhm'] for s in stars], dtype=np.float64)
    return {
        'median_fwhm': float(np.median(fwhm_values)),
        'mean_fwhm': float(np.mean(fwhm_values)),
        'std_fwhm': float(np.std(fwhm_values)),
        'min_fwhm': float(np.min(fwhm_values)),
        'max_fwhm': float(np.max(fwhm_values)),
        'star_count': len(stars),
    }


# ===========================================================================
# CornerInspector
# ===========================================================================

class CornerInspector:
    """Optical quality inspector for 9 image regions.

    Typical workflow::

        inspector = CornerInspector()
        result = inspector.analyze(image_data, stars=star_list)
        eq_result = inspector.equalize_backgrounds(result)
        for key in REGION_KEYS:
            qimg = inspector.annotate_crop(
                eq_result[key]['crop_data'],
                eq_result[key]['stars'],
            )
            # display qimg in a QLabel...
        table = inspector.get_summary_table(result)
    """

    # -----------------------------------------------------------------
    # Region geometry
    # -----------------------------------------------------------------

    @staticmethod
    def _compute_bboxes(
        width: int,
        height: int,
        crop_fraction: float,
    ) -> Dict[str, Tuple[int, int, int, int]]:
        """Compute (x0, y0, x1, y1) bounding boxes for each of the 9 regions.

        ``crop_fraction`` controls the size of each crop as a fraction of the
        full image dimensions.
        """
        f = crop_fraction
        cw = int(round(width * f))
        ch = int(round(height * f))

        # Centers of edge / center crops
        cx = (width - cw) // 2
        cy = (height - ch) // 2

        return {
            'TL': (0,           0,            cw,          ch),
            'T':  (cx,          0,            cx + cw,     ch),
            'TR': (width - cw,  0,            width,       ch),
            'L':  (0,           cy,           cw,          cy + ch),
            'C':  (cx,          cy,           cx + cw,     cy + ch),
            'R':  (width - cw,  cy,           width,       cy + ch),
            'BL': (0,           height - ch,  cw,          height),
            'B':  (cx,          height - ch,  cx + cw,     height),
            'BR': (width - cw,  height - ch,  width,       height),
        }

    # -----------------------------------------------------------------
    # Star filtering
    # -----------------------------------------------------------------

    @staticmethod
    def _filter_stars(
        stars: Sequence[Dict[str, Any]],
        bbox: Tuple[int, int, int, int],
        max_per_region: int = _MAX_STARS_PER_REGION,
    ) -> List[Dict[str, Any]]:
        """Return stars that fall inside *bbox*, sorted by flux descending
        and limited to *max_per_region*.

        Each returned star dict receives ``x_local`` / ``y_local`` keys
        giving the position relative to the crop origin.
        """
        x0, y0, x1, y1 = bbox
        contained: List[Dict[str, Any]] = []

        for s in stars:
            sx = s.get('x', 0.0)
            sy = s.get('y', 0.0)
            if x0 <= sx < x1 and y0 <= sy < y1:
                local = dict(s)
                local['x_local'] = sx - x0
                local['y_local'] = sy - y0
                contained.append(local)

        # Sort by flux descending, keep top N
        contained.sort(key=lambda s: s.get('flux', 0.0), reverse=True)
        return contained[:max_per_region]

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def analyze(
        self,
        data_2d: np.ndarray,
        stars: Optional[Sequence[Dict[str, Any]]] = None,
        crop_fraction: float = 0.15,
    ) -> Dict[str, Dict[str, Any]]:
        """Analyze an image by extracting 9 crops and computing per-region
        FWHM statistics.

        Parameters
        ----------
        data_2d : numpy.ndarray
            2-D image array (height, width).  Mono or already de-Bayered.
        stars : list of dict, optional
            Pre-detected star list, typically from ``quality_analysis.py``.
            Each dict must have at least ``x``, ``y``, ``fwhm``,
            ``eccentricity``, and ``flux`` keys.  If *None*, star-related
            outputs will be empty (the FWHM map module must be run first).
        crop_fraction : float
            Fraction of image width/height for each crop (default 0.15).

        Returns
        -------
        dict
            Mapping of region key → {crop_data, stars, stats, bbox}.
        """
        if data_2d.ndim != 2:
            raise ValueError(
                f"Expected 2-D array, got {data_2d.ndim}-D "
                f"(shape {data_2d.shape})"
            )

        h, w = data_2d.shape
        bboxes = self._compute_bboxes(w, h, crop_fraction)
        star_list: Sequence[Dict[str, Any]] = stars if stars is not None else []

        result: Dict[str, Dict[str, Any]] = {}
        for key in REGION_KEYS:
            x0, y0, x1, y1 = bboxes[key]
            crop = data_2d[y0:y1, x0:x1].copy()
            region_stars = self._filter_stars(star_list, bboxes[key])
            stats = _compute_stats(region_stars)

            result[key] = {
                'crop_data': crop,
                'stars': region_stars,
                'stats': stats,
                'bbox': bboxes[key],
            }

        logger.debug(
            "Corner inspection: %d×%d, crop_frac=%.2f, %d input stars",
            w, h, crop_fraction, len(star_list),
        )
        return result

    # -----------------------------------------------------------------

    def equalize_backgrounds(
        self,
        crops_dict: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """Return a copy of *crops_dict* where each crop's sky background
        has been shifted to match the center crop's level.

        The sky level is estimated as the 10th percentile of the crop pixels.
        Each crop is shifted additively so that its sky percentile equals the
        center crop's percentile.  Pixel values are clipped to the original
        dtype range to prevent overflow.
        """
        center = crops_dict.get('C')
        if center is None:
            raise KeyError("crops_dict must contain the 'C' (center) region")

        center_data = center['crop_data']
        ref_level = float(np.percentile(center_data, _SKY_PERCENTILE))

        equalized: Dict[str, Dict[str, Any]] = {}
        for key in REGION_KEYS:
            entry = crops_dict[key]
            crop = entry['crop_data']
            crop_level = float(np.percentile(crop, _SKY_PERCENTILE))
            shift = ref_level - crop_level

            if abs(shift) < 1e-6:
                eq_crop = crop.copy()
            else:
                # Work in float64 to avoid overflow, then clip back
                eq_float = crop.astype(np.float64) + shift
                if np.issubdtype(crop.dtype, np.integer):
                    info = np.iinfo(crop.dtype)
                    eq_float = np.clip(eq_float, info.min, info.max)
                elif np.issubdtype(crop.dtype, np.floating):
                    # For float images (0..1 or 0..65535), just clip to >= 0
                    eq_float = np.clip(eq_float, 0.0, None)
                eq_crop = eq_float.astype(crop.dtype)

            equalized[key] = {
                'crop_data': eq_crop,
                'stars': entry['stars'],       # unchanged
                'stats': entry['stats'],       # unchanged
                'bbox': entry['bbox'],         # unchanged
            }

        logger.debug(
            "Background equalization: ref_level=%.1f, shifts=%s",
            ref_level,
            {k: f"{ref_level - float(np.percentile(crops_dict[k]['crop_data'], _SKY_PERCENTILE)):+.1f}"
             for k in REGION_KEYS},
        )
        return equalized

    # -----------------------------------------------------------------

    def annotate_crop(
        self,
        crop_data: np.ndarray,
        stars: List[Dict[str, Any]],
        colormap: str = 'fwhm',
    ) -> Any:
        """Render an annotated QImage with circles around detected stars.

        Each star is circled with a color derived from its FWHM value
        (green = good, yellow = moderate, red = poor) and labelled with
        its FWHM value.

        Parameters
        ----------
        crop_data : numpy.ndarray
            2-D crop pixel array.
        stars : list of dict
            Star dicts with at least ``x_local``, ``y_local``, ``fwhm``.
        colormap : str
            Currently only ``'fwhm'`` is supported.

        Returns
        -------
        QImage or None
            Annotated QImage (Format_ARGB32).  Returns *None* if PyQt6 is
            not available.
        """
        if not HAS_PYQT:
            logger.warning("PyQt6 not available — cannot produce annotated QImage")
            return None

        # Normalize crop to 8-bit grayscale for display
        arr = crop_data.astype(np.float64)
        lo = np.percentile(arr, 1.0)
        hi = np.percentile(arr, 99.5)
        if hi - lo < 1e-6:
            hi = lo + 1.0
        stretched = np.clip((arr - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)

        h, w = stretched.shape
        # Build ARGB32 buffer: each pixel = 0xFFRRGGBB (grayscale → R=G=B)
        argb = np.zeros((h, w, 4), dtype=np.uint8)
        argb[:, :, 0] = 255          # alpha
        argb[:, :, 1] = stretched    # red
        argb[:, :, 2] = stretched    # green
        argb[:, :, 3] = stretched    # blue

        # QImage from buffer — must keep argb alive while QImage is used
        bytes_per_line = w * 4
        qimg = QImage(argb.data, w, h, bytes_per_line, QImage.Format.Format_ARGB32)
        # Force a deep copy so we don't rely on numpy buffer lifetime
        qimg = qimg.copy()

        # Draw annotations
        painter = QPainter(qimg)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        font = QFont()
        font.setFamilies(["Consolas", "Monaco", "DejaVu Sans Mono", "monospace"])
        font.setPointSize(_FONT_SIZE)
        font.setBold(True)
        painter.setFont(font)

        for s in stars:
            xl = s.get('x_local', 0.0)
            yl = s.get('y_local', 0.0)
            fwhm = s.get('fwhm', 0.0)

            r, g, b = _fwhm_to_color(fwhm)
            color = QColor(r, g, b, 200)

            # Circle
            pen = QPen(color, 2.0)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            radius = max(_CIRCLE_RADIUS_BASE, fwhm * 2.5)
            painter.drawEllipse(
                QPointF(xl, yl),
                radius,
                radius,
            )

            # Label — FWHM value, positioned above the circle
            label_text = f"{fwhm:.1f}"
            painter.setPen(QPen(color, 1.0))
            text_rect = QRectF(
                xl - 20, yl - radius - _FONT_SIZE - 4,
                40, _FONT_SIZE + 4,
            )
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label_text)

        painter.end()
        return qimg

    # -----------------------------------------------------------------

    def get_summary_table(
        self,
        analysis_result: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Build a summary table from the analysis result.

        Returns a list of dicts (one per region) suitable for display in a
        QTableWidget or export to CSV.  Each dict has:

        - ``region``: region key (TL, T, TR, …)
        - ``median_fwhm``: median FWHM in pixels
        - ``star_count``: number of stars in region
        - ``quality_grade``: 'Excellent' / 'Good' / 'Fair' / 'Poor'
        """
        table: List[Dict[str, Any]] = []

        for key in REGION_KEYS:
            entry = analysis_result.get(key)
            if entry is None:
                continue

            stats = entry.get('stats', {})
            median = stats.get('median_fwhm', 0.0)
            count = stats.get('star_count', 0)

            if count == 0:
                grade = 'N/A'
            elif median < _GRADE_EXCELLENT:
                grade = 'Excellent'
            elif median < _GRADE_GOOD:
                grade = 'Good'
            elif median < _GRADE_FAIR:
                grade = 'Fair'
            else:
                grade = 'Poor'

            table.append({
                'region': key,
                'median_fwhm': round(median, 2),
                'star_count': count,
                'quality_grade': grade,
            })

        return table
