#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - MOSAIC PANEL DETECTION & COMPOSITE PREVIEW MODULE
================================================================================
Detects mosaic panels from file naming patterns and FITS/XISF WCS headers,
computes spatial layout via gnomonic (TAN) projection, and generates a
composite preview image.  Inspired by GalactiLog.

Features:
  - Filename-based panel detection (Panel N, tile N, Row/Col, grid notation)
  - WCS header-based panel grouping (RA/DEC proximity within 1 FOV)
  - Gnomonic projection layout with camera rotation and pier-side flip
  - Composite preview rendering with labeled panel thumbnails
  - Per-panel and aggregate mosaic statistics

Feature-gated: gracefully degrades when optional dependencies are absent.
  - numpy (required)
  - astropy.io.fits / astropy.wcs (optional, for WCS-based detection/layout)

Pure logic module — no GUI code.
================================================================================
"""

import logging
import math
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature gates — optional dependencies
# ---------------------------------------------------------------------------

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from astropy.io import fits as astropy_fits
    HAS_ASTROPY_FITS = True
except ImportError:
    HAS_ASTROPY_FITS = False

try:
    from astropy.wcs import WCS as AstropyWCS
    HAS_ASTROPY_WCS = True
except ImportError:
    HAS_ASTROPY_WCS = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Panel naming patterns (case-insensitive)
_PANEL_PATTERNS = [
    # "Panel 3", "panneau 3", "P3", "tile 3", "section 3", "Mosaic_Panel3"
    re.compile(
        r"(?:Panel|panneau|tile|section|mosaic[_\s]?panel)\s*(\d+)",
        re.IGNORECASE,
    ),
    # Shorthand "P3" — only match isolated P+digit (not inside a word)
    re.compile(r"(?<![A-Za-z])P\s*(\d+)(?![A-Za-z])", re.IGNORECASE),
]

_GRID_PATTERNS = [
    # "Row1_Col2", "Row 1 Col 2"
    re.compile(
        r"(?:Row|R)\s*(\d+)[_\s]*(?:Col|C)\s*(\d+)",
        re.IGNORECASE,
    ),
    # "1x2" grid notation (row x col) — only match isolated digit×digit
    re.compile(r"(?<!\d)(\d+)\s*x\s*(\d+)(?!\d)", re.IGNORECASE),
]

# Header keywords for rotation and pier side
_ROTATION_KEYWORDS = ("OBJCTROT", "ROTANGLE", "CROTA2", "POSANGLE")
_PIERSIDE_KEYWORDS = ("PIERSIDE", "PIER-SIDE", "PIER_SIDE")

# Default thumbnail size for composite preview
_DEFAULT_CANVAS = 2048

# Angular proximity threshold (degrees) for grouping frames into one mosaic
# Typically ~2x the diagonal FOV of a single frame (conservative default)
_DEFAULT_PROXIMITY_DEG = 5.0

# Minimum number of panels to consider a detection valid
_MIN_PANELS = 1


# ---------------------------------------------------------------------------
# Helper — gnomonic (TAN) projection
# ---------------------------------------------------------------------------

def _gnomonic_project(
    ra_deg: float,
    dec_deg: float,
    ra0_deg: float,
    dec0_deg: float,
) -> Tuple[float, float]:
    """Project (RA, Dec) onto a tangent plane at (ra0, dec0) using gnomonic
    (TAN) projection.

    Parameters
    ----------
    ra_deg, dec_deg : float
        Celestial coordinates of the point (degrees).
    ra0_deg, dec0_deg : float
        Reference point (tangent point) coordinates (degrees).

    Returns
    -------
    (xi, eta) : tuple of float
        Standard coordinates on the tangent plane (radians).
        xi  = East-West offset (positive West for RA increasing).
        eta = North-South offset (positive North).
    """
    ra = math.radians(ra_deg)
    dec = math.radians(dec_deg)
    ra0 = math.radians(ra0_deg)
    dec0 = math.radians(dec0_deg)

    cos_dec = math.cos(dec)
    sin_dec = math.sin(dec)
    cos_dec0 = math.cos(dec0)
    sin_dec0 = math.sin(dec0)
    delta_ra = ra - ra0
    cos_dra = math.cos(delta_ra)

    denom = sin_dec0 * sin_dec + cos_dec0 * cos_dec * cos_dra
    if abs(denom) < 1e-12:
        logger.warning(
            "Gnomonic projection: point near 90° from tangent point, "
            "clamping denominator."
        )
        denom = 1e-12

    xi = cos_dec * math.sin(delta_ra) / denom
    eta = (cos_dec0 * sin_dec - sin_dec0 * cos_dec * cos_dra) / denom

    return (xi, eta)


def _angular_separation_deg(
    ra1: float, dec1: float, ra2: float, dec2: float
) -> float:
    """Great-circle angular separation between two points (all in degrees)."""
    ra1_r = math.radians(ra1)
    dec1_r = math.radians(dec1)
    ra2_r = math.radians(ra2)
    dec2_r = math.radians(dec2)
    cos_sep = (
        math.sin(dec1_r) * math.sin(dec2_r)
        + math.cos(dec1_r) * math.cos(dec2_r) * math.cos(ra1_r - ra2_r)
    )
    cos_sep = max(-1.0, min(1.0, cos_sep))
    return math.degrees(math.acos(cos_sep))


# ---------------------------------------------------------------------------
# Helper — read FITS/XISF header
# ---------------------------------------------------------------------------

def _read_header(filepath: str) -> Optional[Dict[str, Any]]:
    """Read relevant header keywords from a FITS or XISF file.

    Returns a dict with uppercase keyword keys, or None on failure.
    Reads header only (no pixel data loaded).
    """
    ext = Path(filepath).suffix.lower()
    header_dict: Dict[str, Any] = {}

    if ext in (".fits", ".fit", ".fts"):
        if not HAS_ASTROPY_FITS:
            return None
        try:
            with astropy_fits.open(filepath, memmap=True) as hdul:
                hdr = hdul[0].header
                for key in hdr:
                    if key:
                        header_dict[key.upper()] = hdr[key]
        except Exception as exc:
            logger.debug("Failed to read FITS header for %s: %s", filepath, exc)
            return None

    elif ext == ".fz":
        if not HAS_ASTROPY_FITS:
            return None
        try:
            with astropy_fits.open(filepath, memmap=True) as hdul:
                # CompImageHDU stores the real header in extension 1
                idx = 1 if len(hdul) > 1 else 0
                hdr = hdul[idx].header
                for key in hdr:
                    if key:
                        header_dict[key.upper()] = hdr[key]
        except Exception as exc:
            logger.debug("Failed to read FITS.FZ header for %s: %s", filepath, exc)
            return None

    elif ext == ".xisf":
        # Attempt lightweight XISF header read via xml parsing
        try:
            # Safe XML parsing: prefer defusedxml for XXE protection
            try:
                from defusedxml.ElementTree import fromstring as _safe_xml_fromstring
            except ImportError:
                from xml.etree.ElementTree import fromstring as _safe_xml_fromstring
            import xml.etree.ElementTree as ET

            with open(filepath, "rb") as f:
                # XISF header is XML embedded in the first ~64KB
                raw = f.read(65536)
            # Find XML region
            xml_start = raw.find(b"<?xml")
            xml_end = raw.find(b"</xisf:XISF>")
            if xml_end < 0:
                xml_end = raw.find(b"</XISF>")
            if xml_start >= 0 and xml_end > xml_start:
                xml_bytes = raw[xml_start: xml_end + 20]
                try:
                    root = _safe_xml_fromstring(xml_bytes)
                except ET.ParseError:
                    # Try extending the read
                    return None
                # Walk all FITSKeyword elements
                for elem in root.iter():
                    tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    if tag == "FITSKeyword":
                        name = elem.get("name", "").upper()
                        value = elem.get("value", "")
                        if name:
                            # Try numeric conversion
                            try:
                                header_dict[name] = float(value)
                                if header_dict[name] == int(header_dict[name]):
                                    header_dict[name] = int(header_dict[name])
                            except (ValueError, TypeError):
                                # Strip FITS string quotes
                                header_dict[name] = value.strip("' ")
        except Exception as exc:
            logger.debug("Failed to read XISF header for %s: %s", filepath, exc)
            return None
    else:
        return None

    return header_dict if header_dict else None


# ---------------------------------------------------------------------------
# MosaicComposite class
# ---------------------------------------------------------------------------

class MosaicComposite:
    """Mosaic panel detection, layout computation, and composite preview
    generation for astrophotography multi-panel mosaics."""

    # ------------------------------------------------------------------
    # Panel detection — filename patterns
    # ------------------------------------------------------------------

    @staticmethod
    def detect_panels(file_list: List[str]) -> Dict[str, Any]:
        """Detect mosaic panels from file naming patterns.

        Scans file names for mosaic-related naming conventions (Panel N,
        Row/Col, grid notation, etc.) and groups files accordingly.

        Parameters
        ----------
        file_list : list of str
            Absolute or relative paths to image files.

        Returns
        -------
        dict
            {
                "panels": [
                    {
                        "panel_id": str,
                        "row": int,
                        "col": int,
                        "files": [str, ...],
                    },
                    ...
                ],
                "grid_shape": (rows, cols),
                "target_name": str or None,
            }
        """
        # Map (row, col) → list of files
        panel_files: Dict[Tuple[int, int], List[str]] = defaultdict(list)
        target_candidates: List[str] = []

        for fpath in file_list:
            basename = Path(fpath).stem
            matched = False

            # Try grid patterns first (more specific)
            for pat in _GRID_PATTERNS:
                m = pat.search(basename)
                if m:
                    row = int(m.group(1))
                    col = int(m.group(2))
                    panel_files[(row, col)].append(fpath)
                    # Extract target name: text before the pattern
                    prefix = basename[: m.start()].strip("_- ")
                    if prefix:
                        target_candidates.append(prefix)
                    matched = True
                    break

            if matched:
                continue

            # Try panel ID patterns
            for pat in _PANEL_PATTERNS:
                m = pat.search(basename)
                if m:
                    panel_num = int(m.group(1))
                    # Single-index panel → assign to row 0, col = panel_num
                    panel_files[(0, panel_num)].append(fpath)
                    prefix = basename[: m.start()].strip("_- ")
                    if prefix:
                        target_candidates.append(prefix)
                    matched = True
                    break

        # If no patterns matched, return empty result
        if not panel_files:
            return {"panels": [], "grid_shape": (0, 0), "target_name": None}

        # Determine grid shape
        all_rows = [rc[0] for rc in panel_files]
        all_cols = [rc[1] for rc in panel_files]
        min_row, max_row = min(all_rows), max(all_rows)
        min_col, max_col = min(all_cols), max(all_cols)
        grid_rows = max_row - min_row + 1
        grid_cols = max_col - min_col + 1

        # Normalise row/col to 0-based
        panels = []
        for (row, col), files in sorted(panel_files.items()):
            norm_row = row - min_row
            norm_col = col - min_col
            panel_id = f"R{norm_row + 1}C{norm_col + 1}"
            panels.append({
                "panel_id": panel_id,
                "row": norm_row,
                "col": norm_col,
                "files": sorted(files),
            })

        # Most common target prefix
        target_name = None
        if target_candidates:
            from collections import Counter
            counts = Counter(target_candidates)
            target_name = counts.most_common(1)[0][0]

        return {
            "panels": panels,
            "grid_shape": (grid_rows, grid_cols),
            "target_name": target_name,
        }

    # ------------------------------------------------------------------
    # Panel detection — WCS headers
    # ------------------------------------------------------------------

    @staticmethod
    def detect_panels_from_headers(
        file_list: List[str],
        proximity_deg: float = _DEFAULT_PROXIMITY_DEG,
    ) -> Dict[str, Any]:
        """Detect mosaic panels by reading FITS/XISF WCS headers.

        Groups frames whose RA/DEC centres fall within ``proximity_deg`` of
        each other (single-linkage clustering).  Then determines grid
        positions from RA/DEC offsets.

        Parameters
        ----------
        file_list : list of str
            Paths to FITS/XISF image files.
        proximity_deg : float
            Maximum angular separation (degrees) to consider frames part of
            the same mosaic tile.

        Returns
        -------
        dict
            Same structure as :meth:`detect_panels`, plus per-panel
            ``ra_center`` and ``dec_center`` (degrees).
        """
        if not HAS_NUMPY:
            logger.warning("numpy is required for WCS-based panel detection.")
            return {"panels": [], "grid_shape": (0, 0), "target_name": None}

        # Collect RA/DEC per file
        file_coords: List[Tuple[str, float, float, Dict]] = []  # (path, ra, dec, hdr)
        for fpath in file_list:
            hdr = _read_header(fpath)
            if hdr is None:
                continue

            ra = hdr.get("CRVAL1") or hdr.get("RA") or hdr.get("OBJCTRA")
            dec = hdr.get("CRVAL2") or hdr.get("DEC") or hdr.get("OBJCTDEC")
            if ra is None or dec is None:
                continue

            # Convert RA from hours to degrees if needed (< 24 → likely hours)
            try:
                ra_f = float(ra)
                dec_f = float(dec)
            except (ValueError, TypeError):
                # Might be sexagesimal string — skip for now
                continue

            if ra_f < 24.0 and ra_f >= 0.0 and "CRVAL1" not in hdr:
                ra_f *= 15.0  # hours → degrees

            file_coords.append((fpath, ra_f, dec_f, hdr))

        if not file_coords:
            return {"panels": [], "grid_shape": (0, 0), "target_name": None}

        # Single-linkage clustering by angular proximity
        n = len(file_coords)
        labels = list(range(n))  # Union-Find labels

        def find(i: int) -> int:
            while labels[i] != i:
                labels[i] = labels[labels[i]]
                i = labels[i]
            return i

        def union(i: int, j: int) -> None:
            ri, rj = find(i), find(j)
            if ri != rj:
                labels[ri] = rj

        for i in range(n):
            for j in range(i + 1, n):
                sep = _angular_separation_deg(
                    file_coords[i][1], file_coords[i][2],
                    file_coords[j][1], file_coords[j][2],
                )
                if sep < proximity_deg:
                    union(i, j)

        # Group by cluster
        clusters: Dict[int, List[int]] = defaultdict(list)
        for i in range(n):
            clusters[find(i)].append(i)

        # Pick the largest cluster as the mosaic
        main_indices = max(clusters.values(), key=len)

        # Compute median RA/DEC for grid assignment
        ras = np.array([file_coords[i][1] for i in main_indices])
        decs = np.array([file_coords[i][2] for i in main_indices])

        # Determine unique panel positions by rounding to nearest half-FOV
        # Estimate FOV from pixel scale if available, else use median separation
        unique_positions: Dict[Tuple[int, int], List[Tuple[str, Dict]]] = defaultdict(list)

        if len(main_indices) > 1:
            # Compute pairwise separations to estimate tile spacing
            seps = []
            for i_idx in range(len(main_indices)):
                for j_idx in range(i_idx + 1, len(main_indices)):
                    ii = main_indices[i_idx]
                    jj = main_indices[j_idx]
                    seps.append(_angular_separation_deg(
                        file_coords[ii][1], file_coords[ii][2],
                        file_coords[jj][1], file_coords[jj][2],
                    ))

            if seps:
                # Tile spacing ~ minimum non-zero separation
                nonzero_seps = [s for s in seps if s > 0.01]
                tile_spacing = np.median(nonzero_seps) if nonzero_seps else 1.0
            else:
                tile_spacing = 1.0

            half_spacing = tile_spacing / 2.0
        else:
            tile_spacing = 1.0
            half_spacing = 0.5

        median_ra = float(np.median(ras))
        median_dec = float(np.median(decs))

        for idx in main_indices:
            fpath, ra_f, dec_f, hdr = file_coords[idx]
            # Project onto tangent plane
            xi, eta = _gnomonic_project(ra_f, dec_f, median_ra, median_dec)
            xi_deg = math.degrees(xi)
            eta_deg = math.degrees(eta)

            # Quantize to grid cells
            if tile_spacing > 0.001:
                col = round(xi_deg / tile_spacing)
                row = round(eta_deg / tile_spacing)
            else:
                col, row = 0, 0

            unique_positions[(row, col)].append((fpath, hdr))

        # Build panels list
        all_rows = [rc[0] for rc in unique_positions]
        all_cols = [rc[1] for rc in unique_positions]
        min_row = min(all_rows) if all_rows else 0
        min_col = min(all_cols) if all_cols else 0

        panels = []
        for (row, col), file_hdr_list in sorted(unique_positions.items()):
            norm_row = row - min_row
            norm_col = col - min_col
            panel_id = f"R{norm_row + 1}C{norm_col + 1}"

            # Compute panel RA/DEC center (median of files in this cell)
            p_ras = [file_coords[main_indices[0]][1]]  # fallback
            p_decs = [file_coords[main_indices[0]][2]]
            for fpath, hdr in file_hdr_list:
                for idx in main_indices:
                    if file_coords[idx][0] == fpath:
                        p_ras.append(file_coords[idx][1])
                        p_decs.append(file_coords[idx][2])
                        break

            panels.append({
                "panel_id": panel_id,
                "row": norm_row,
                "col": norm_col,
                "files": sorted([fh[0] for fh in file_hdr_list]),
                "ra_center": float(np.median(p_ras)),
                "dec_center": float(np.median(p_decs)),
            })

        max_row = max(all_rows) if all_rows else 0
        max_col = max(all_cols) if all_cols else 0
        grid_rows = max_row - min_row + 1
        grid_cols = max_col - min_col + 1

        # Attempt to find target name from OBJECT keyword
        target_name = None
        for idx in main_indices:
            obj = file_coords[idx][3].get("OBJECT")
            if obj and str(obj).strip():
                target_name = str(obj).strip()
                break

        return {
            "panels": panels,
            "grid_shape": (grid_rows, grid_cols),
            "target_name": target_name,
        }

    # ------------------------------------------------------------------
    # Layout computation
    # ------------------------------------------------------------------

    @staticmethod
    def compute_layout(
        panels: List[Dict[str, Any]],
        headers_dict: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Compute the spatial layout of mosaic panels for rendering.

        If WCS information is available (via ``headers_dict``), uses gnomonic
        projection for precise positioning.  Otherwise falls back to the
        row/col grid positions with equal spacing.

        Parameters
        ----------
        panels : list of dict
            Panel dicts as returned by :meth:`detect_panels` or
            :meth:`detect_panels_from_headers`.
        headers_dict : dict, optional
            Mapping ``filepath → header_dict`` for WCS-based layout.
            If provided, must contain CRVAL1/CRVAL2, NAXIS1/NAXIS2, and
            ideally CDELT1/CDELT2 or CD matrix.

        Returns
        -------
        dict
            {
                "canvas_width": int,
                "canvas_height": int,
                "placements": [
                    {
                        "panel_id": str,
                        "x": float,
                        "y": float,
                        "width": float,
                        "height": float,
                        "rotation": float,   # degrees, CCW
                    },
                    ...
                ],
            }
        """
        if not panels:
            return {"canvas_width": 0, "canvas_height": 0, "placements": []}

        # Attempt WCS-based layout
        if headers_dict:
            result = MosaicComposite._layout_from_wcs(panels, headers_dict)
            if result is not None:
                return result

        # Fallback: grid-based equal-spacing layout
        return MosaicComposite._layout_from_grid(panels, headers_dict)

    @staticmethod
    def _layout_from_wcs(
        panels: List[Dict],
        headers_dict: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Compute layout from WCS headers using gnomonic projection.

        Returns None if insufficient WCS information is available.
        """
        # Gather RA/DEC and pixel dimensions per panel
        panel_wcs: List[Dict[str, Any]] = []
        for panel in panels:
            # Use the first file in each panel for WCS info
            if not panel.get("files"):
                continue
            representative = panel["files"][0]
            hdr = headers_dict.get(representative)
            if hdr is None:
                continue

            ra = hdr.get("CRVAL1")
            dec = hdr.get("CRVAL2")
            if ra is None or dec is None:
                # Try panel-level RA/DEC (from header-based detection)
                ra = panel.get("ra_center")
                dec = panel.get("dec_center")
            if ra is None or dec is None:
                return None  # Insufficient WCS → fall back to grid

            try:
                ra_f = float(ra)
                dec_f = float(dec)
            except (ValueError, TypeError):
                return None

            naxis1 = hdr.get("NAXIS1", 1)
            naxis2 = hdr.get("NAXIS2", 1)

            # Pixel scale (degrees/pixel)
            cdelt1 = hdr.get("CDELT1")
            cdelt2 = hdr.get("CDELT2")
            if cdelt1 is None or cdelt2 is None:
                # Try CD matrix
                cd1_1 = hdr.get("CD1_1", 0)
                cd1_2 = hdr.get("CD1_2", 0)
                cd2_1 = hdr.get("CD2_1", 0)
                cd2_2 = hdr.get("CD2_2", 0)
                if cd1_1 or cd1_2:
                    cdelt1 = math.sqrt(cd1_1 ** 2 + cd1_2 ** 2)
                    cdelt2 = math.sqrt(cd2_1 ** 2 + cd2_2 ** 2)
                else:
                    cdelt1 = None
                    cdelt2 = None

            # Rotation angle (degrees)
            rotation = 0.0
            for rkey in _ROTATION_KEYWORDS:
                if rkey in hdr:
                    try:
                        rotation = float(hdr[rkey])
                    except (ValueError, TypeError):
                        pass
                    break

            # Pier side flip (East vs West → 180° rotation)
            for pkey in _PIERSIDE_KEYWORDS:
                if pkey in hdr:
                    ps_val = str(hdr[pkey]).strip().upper()
                    if ps_val in ("WEST", "W"):
                        rotation += 180.0
                    break

            # Normalise rotation to [0, 360)
            rotation = rotation % 360.0

            # FOV in degrees (per axis)
            if cdelt1 is not None and cdelt2 is not None:
                fov_w = abs(float(cdelt1)) * int(naxis1)
                fov_h = abs(float(cdelt2)) * int(naxis2)
            else:
                fov_w = None
                fov_h = None

            panel_wcs.append({
                "panel_id": panel["panel_id"],
                "ra": ra_f,
                "dec": dec_f,
                "naxis1": int(naxis1),
                "naxis2": int(naxis2),
                "fov_w_deg": fov_w,
                "fov_h_deg": fov_h,
                "rotation": rotation,
            })

        if not panel_wcs:
            return None

        # Reference point: median RA/DEC
        ra0 = float(np.median([p["ra"] for p in panel_wcs])) if HAS_NUMPY else \
            sum(p["ra"] for p in panel_wcs) / len(panel_wcs)
        dec0 = float(np.median([p["dec"] for p in panel_wcs])) if HAS_NUMPY else \
            sum(p["dec"] for p in panel_wcs) / len(panel_wcs)

        # Determine a common pixel scale (use median FOV / median pixel count)
        fov_ws = [p["fov_w_deg"] for p in panel_wcs if p["fov_w_deg"] is not None]
        fov_hs = [p["fov_h_deg"] for p in panel_wcs if p["fov_h_deg"] is not None]
        nax1s = [p["naxis1"] for p in panel_wcs]
        nax2s = [p["naxis2"] for p in panel_wcs]

        if fov_ws and fov_hs:
            median_fov_w = float(np.median(fov_ws)) if HAS_NUMPY else sorted(fov_ws)[len(fov_ws) // 2]
            median_fov_h = float(np.median(fov_hs)) if HAS_NUMPY else sorted(fov_hs)[len(fov_hs) // 2]
        else:
            # No pixel scale available — cannot do precise WCS layout
            return None

        median_nax1 = float(np.median(nax1s)) if HAS_NUMPY else sorted(nax1s)[len(nax1s) // 2]
        median_nax2 = float(np.median(nax2s)) if HAS_NUMPY else sorted(nax2s)[len(nax2s) // 2]

        # Pixel scale: degrees per output pixel (using median panel as reference)
        deg_per_px_x = median_fov_w / median_nax1
        deg_per_px_y = median_fov_h / median_nax2

        # Project each panel center onto the tangent plane
        placements = []
        for pw in panel_wcs:
            xi, eta = _gnomonic_project(pw["ra"], pw["dec"], ra0, dec0)
            # Convert radians → degrees → pixels
            x_px = math.degrees(xi) / deg_per_px_x
            y_px = -math.degrees(eta) / deg_per_px_y  # Flip Y (image coords)

            # Panel pixel dimensions
            pw_w = pw["naxis1"]
            pw_h = pw["naxis2"]

            placements.append({
                "panel_id": pw["panel_id"],
                "x": x_px,
                "y": y_px,
                "width": pw_w,
                "height": pw_h,
                "rotation": pw["rotation"],
            })

        # Normalise positions so minimum is at (0, 0), with half-panel padding
        if placements:
            min_x = min(p["x"] - p["width"] / 2.0 for p in placements)
            min_y = min(p["y"] - p["height"] / 2.0 for p in placements)
            for p in placements:
                p["x"] -= min_x
                p["y"] -= min_y

            canvas_w = int(max(p["x"] + p["width"] / 2.0 for p in placements) + 1)
            canvas_h = int(max(p["y"] + p["height"] / 2.0 for p in placements) + 1)
        else:
            canvas_w, canvas_h = 0, 0

        return {
            "canvas_width": canvas_w,
            "canvas_height": canvas_h,
            "placements": placements,
        }

    @staticmethod
    def _layout_from_grid(
        panels: List[Dict],
        headers_dict: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Compute layout from grid row/col positions with equal spacing.

        Uses median image dimensions if headers are available, otherwise
        assumes square panels.
        """
        if not panels:
            return {"canvas_width": 0, "canvas_height": 0, "placements": []}

        # Determine panel pixel dimensions from headers (use median)
        panel_w = 1000
        panel_h = 1000
        if headers_dict:
            widths = []
            heights = []
            for panel in panels:
                for fpath in panel.get("files", []):
                    hdr = headers_dict.get(fpath)
                    if hdr and "NAXIS1" in hdr and "NAXIS2" in hdr:
                        widths.append(int(hdr["NAXIS1"]))
                        heights.append(int(hdr["NAXIS2"]))
            if widths and heights and HAS_NUMPY:
                panel_w = int(np.median(widths))
                panel_h = int(np.median(heights))
            elif widths and heights:
                panel_w = sorted(widths)[len(widths) // 2]
                panel_h = sorted(heights)[len(heights) // 2]

        # Small gap between panels (2% of panel size)
        gap_x = int(panel_w * 0.02)
        gap_y = int(panel_h * 0.02)

        placements = []
        for panel in panels:
            row = panel.get("row", 0)
            col = panel.get("col", 0)
            x = col * (panel_w + gap_x)
            y = row * (panel_h + gap_y)

            # Rotation from header if available
            rotation = 0.0
            if headers_dict and panel.get("files"):
                hdr = headers_dict.get(panel["files"][0])
                if hdr:
                    for rkey in _ROTATION_KEYWORDS:
                        if rkey in hdr:
                            try:
                                rotation = float(hdr[rkey])
                            except (ValueError, TypeError):
                                pass
                            break
                    for pkey in _PIERSIDE_KEYWORDS:
                        if pkey in hdr:
                            ps_val = str(hdr[pkey]).strip().upper()
                            if ps_val in ("WEST", "W"):
                                rotation += 180.0
                            break
                    rotation = rotation % 360.0

            placements.append({
                "panel_id": panel["panel_id"],
                "x": float(x),
                "y": float(y),
                "width": float(panel_w),
                "height": float(panel_h),
                "rotation": rotation,
            })

        if placements:
            canvas_w = int(max(p["x"] + p["width"] for p in placements))
            canvas_h = int(max(p["y"] + p["height"] for p in placements))
        else:
            canvas_w, canvas_h = 0, 0

        return {
            "canvas_width": canvas_w,
            "canvas_height": canvas_h,
            "placements": placements,
        }

    # ------------------------------------------------------------------
    # Composite preview generation
    # ------------------------------------------------------------------

    @staticmethod
    def generate_preview(
        panels: List[Dict[str, Any]],
        layout: Dict[str, Any],
        thumbnails_dict: Optional[Dict[str, "np.ndarray"]] = None,
        canvas_size: int = _DEFAULT_CANVAS,
    ) -> "np.ndarray":
        """Generate a composite mosaic preview image.

        Places panel thumbnails (or colored placeholder rectangles) on a
        black canvas, scaled to fit ``canvas_size`` while preserving
        aspect ratio.  Each panel is labeled with its ID.

        Parameters
        ----------
        panels : list of dict
            Panel dicts from detection.
        layout : dict
            Layout dict from :meth:`compute_layout`.
        thumbnails_dict : dict, optional
            Mapping ``panel_id → numpy array (H, W, 3) uint8``.
            If a panel has no thumbnail, a colored rectangle is drawn.
        canvas_size : int
            Maximum dimension (width or height) of the output canvas in
            pixels (default 2048).

        Returns
        -------
        np.ndarray
            RGB uint8 array of shape (canvas_height, canvas_width, 3).
        """
        if not HAS_NUMPY:
            raise RuntimeError("numpy is required for preview generation.")

        placements = layout.get("placements", [])
        src_w = layout.get("canvas_width", 1)
        src_h = layout.get("canvas_height", 1)

        if src_w <= 0 or src_h <= 0 or not placements:
            # Return a small blank canvas
            return np.zeros((64, 64, 3), dtype=np.uint8)

        # Compute scale factor to fit within canvas_size
        scale = min(canvas_size / src_w, canvas_size / src_h)
        out_w = max(1, int(src_w * scale))
        out_h = max(1, int(src_h * scale))

        canvas = np.zeros((out_h, out_w, 3), dtype=np.uint8)

        # Distinct colors for panels without thumbnails
        _PANEL_COLORS = [
            (70, 130, 180),   # Steel blue
            (178, 102, 60),   # Copper
            (100, 149, 80),   # Fern green
            (180, 80, 120),   # Rose
            (140, 120, 180),  # Lavender
            (180, 160, 60),   # Gold
            (60, 160, 160),   # Teal
            (200, 120, 60),   # Tangerine
            (120, 80, 160),   # Purple
            (80, 180, 120),   # Mint
        ]

        # Panel ID → index for color assignment
        panel_id_map = {p["panel_id"]: i for i, p in enumerate(placements)}

        for placement in placements:
            pid = placement["panel_id"]
            px = int(placement["x"] * scale)
            py = int(placement["y"] * scale)
            pw = max(1, int(placement["width"] * scale))
            ph = max(1, int(placement["height"] * scale))

            # Clamp to canvas bounds
            x0 = max(0, px)
            y0 = max(0, py)
            x1 = min(out_w, px + pw)
            y1 = min(out_h, py + ph)

            if x1 <= x0 or y1 <= y0:
                continue

            region_w = x1 - x0
            region_h = y1 - y0

            if thumbnails_dict and pid in thumbnails_dict:
                thumb = thumbnails_dict[pid]
                # Resize thumbnail to fit panel region
                resized = MosaicComposite._resize_thumbnail(
                    thumb, region_w, region_h
                )
                canvas[y0:y1, x0:x1] = resized[:region_h, :region_w]
            else:
                # Draw colored rectangle
                color_idx = panel_id_map.get(pid, 0) % len(_PANEL_COLORS)
                color = _PANEL_COLORS[color_idx]
                canvas[y0:y1, x0:x1] = color

                # Draw border (1-pixel darker outline)
                border = max(1, int(min(region_w, region_h) * 0.01))
                dark = tuple(max(0, c - 40) for c in color)
                # Top/bottom borders
                canvas[y0:y0 + border, x0:x1] = dark
                canvas[max(y0, y1 - border):y1, x0:x1] = dark
                # Left/right borders
                canvas[y0:y1, x0:x0 + border] = dark
                canvas[y0:y1, max(x0, x1 - border):x1] = dark

            # Draw panel ID label (simple pixel font, top-left of panel)
            MosaicComposite._draw_label(canvas, pid, x0 + 4, y0 + 4)

        return canvas

    @staticmethod
    def _resize_thumbnail(
        image: "np.ndarray", target_w: int, target_h: int
    ) -> "np.ndarray":
        """Resize an image to target dimensions using nearest-neighbor.

        Uses numpy-only interpolation (no PIL/OpenCV dependency).
        """
        src_h, src_w = image.shape[:2]
        if src_h <= 0 or src_w <= 0 or target_h <= 0 or target_w <= 0:
            return np.zeros((max(1, target_h), max(1, target_w), 3), dtype=np.uint8)

        row_indices = (np.arange(target_h) * src_h // target_h).astype(int)
        col_indices = (np.arange(target_w) * src_w // target_w).astype(int)
        row_indices = np.clip(row_indices, 0, src_h - 1)
        col_indices = np.clip(col_indices, 0, src_w - 1)

        if image.ndim == 3:
            return image[row_indices][:, col_indices]
        else:
            # Mono → expand to RGB
            mono = image[row_indices][:, col_indices]
            return np.stack([mono, mono, mono], axis=-1)

    @staticmethod
    def _draw_label(
        canvas: "np.ndarray", text: str, x: int, y: int
    ) -> None:
        """Draw a simple text label on the canvas using a minimal 5x3 font.

        This avoids any dependency on PIL or matplotlib for text rendering.
        Only uppercase letters and digits are supported.
        """
        # Minimal 5×3 bitmap font (each char is 5 rows × 3 cols, stored as
        # list of 5 integers where each integer has 3 bits).
        _FONT: Dict[str, List[int]] = {
            "0": [0b111, 0b101, 0b101, 0b101, 0b111],
            "1": [0b010, 0b110, 0b010, 0b010, 0b111],
            "2": [0b111, 0b001, 0b111, 0b100, 0b111],
            "3": [0b111, 0b001, 0b111, 0b001, 0b111],
            "4": [0b101, 0b101, 0b111, 0b001, 0b001],
            "5": [0b111, 0b100, 0b111, 0b001, 0b111],
            "6": [0b111, 0b100, 0b111, 0b101, 0b111],
            "7": [0b111, 0b001, 0b001, 0b001, 0b001],
            "8": [0b111, 0b101, 0b111, 0b101, 0b111],
            "9": [0b111, 0b101, 0b111, 0b001, 0b111],
            "R": [0b110, 0b101, 0b110, 0b101, 0b101],
            "C": [0b111, 0b100, 0b100, 0b100, 0b111],
            "P": [0b110, 0b101, 0b110, 0b100, 0b100],
            "X": [0b101, 0b101, 0b010, 0b101, 0b101],
        }

        h, w = canvas.shape[:2]
        scale = max(1, min(w, h) // 200)  # Scale font with canvas size
        cursor_x = x

        for ch in text.upper():
            glyph = _FONT.get(ch)
            if glyph is None:
                cursor_x += 2 * scale  # Space for unknown chars
                continue

            for row_idx, row_bits in enumerate(glyph):
                for col_idx in range(3):
                    if row_bits & (1 << (2 - col_idx)):
                        px = cursor_x + col_idx * scale
                        py = y + row_idx * scale
                        # Draw scaled pixel block
                        px_end = min(w, px + scale)
                        py_end = min(h, py + scale)
                        if px >= 0 and py >= 0 and px < w and py < h:
                            canvas[py:py_end, px:px_end] = (255, 255, 255)

            cursor_x += 4 * scale  # 3 cols + 1 col spacing

    # ------------------------------------------------------------------
    # Mosaic statistics
    # ------------------------------------------------------------------

    @staticmethod
    def get_mosaic_stats(
        panels: List[Dict[str, Any]],
        headers_dict: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Compute aggregate and per-panel statistics for a mosaic.

        Parameters
        ----------
        panels : list of dict
            Panel dicts from detection.
        headers_dict : dict, optional
            Mapping ``filepath → header_dict`` for extracting filter and
            exposure information.

        Returns
        -------
        dict
            {
                "total_panels": int,
                "total_files": int,
                "grid_shape": (rows, cols) or None,
                "estimated_fov_arcmin": (width, height) or None,
                "per_panel": [
                    {
                        "panel_id": str,
                        "file_count": int,
                        "filters_used": [str, ...],
                        "total_exposure_sec": float,
                    },
                    ...
                ],
            }
        """
        total_files = 0
        per_panel = []

        for panel in panels:
            files = panel.get("files", [])
            file_count = len(files)
            total_files += file_count

            filters_used = set()
            total_exposure = 0.0

            if headers_dict:
                for fpath in files:
                    hdr = headers_dict.get(fpath)
                    if hdr is None:
                        continue
                    filt = hdr.get("FILTER")
                    if filt and str(filt).strip():
                        filters_used.add(str(filt).strip())
                    exp = hdr.get("EXPTIME") or hdr.get("EXPOSURE")
                    if exp is not None:
                        try:
                            total_exposure += float(exp)
                        except (ValueError, TypeError):
                            pass

            per_panel.append({
                "panel_id": panel["panel_id"],
                "file_count": file_count,
                "filters_used": sorted(filters_used),
                "total_exposure_sec": total_exposure,
            })

        # Grid shape
        if panels:
            rows = [p.get("row", 0) for p in panels]
            cols = [p.get("col", 0) for p in panels]
            grid_shape = (max(rows) - min(rows) + 1, max(cols) - min(cols) + 1)
        else:
            grid_shape = None

        # Estimated FOV (if WCS data available in any panel header)
        estimated_fov = None
        if headers_dict and panels and grid_shape:
            # Collect pixel scales
            fov_w_samples = []
            fov_h_samples = []
            for panel in panels:
                for fpath in panel.get("files", []):
                    hdr = headers_dict.get(fpath)
                    if hdr is None:
                        continue
                    nax1 = hdr.get("NAXIS1")
                    nax2 = hdr.get("NAXIS2")
                    cdelt1 = hdr.get("CDELT1")
                    cdelt2 = hdr.get("CDELT2")
                    if cdelt1 is None or cdelt2 is None:
                        cd1_1 = hdr.get("CD1_1", 0)
                        cd1_2 = hdr.get("CD1_2", 0)
                        cd2_1 = hdr.get("CD2_1", 0)
                        cd2_2 = hdr.get("CD2_2", 0)
                        if cd1_1 or cd1_2:
                            cdelt1 = math.sqrt(cd1_1 ** 2 + cd1_2 ** 2)
                            cdelt2 = math.sqrt(cd2_1 ** 2 + cd2_2 ** 2)
                    if cdelt1 is not None and cdelt2 is not None and nax1 and nax2:
                        try:
                            fov_w_samples.append(abs(float(cdelt1)) * int(nax1))
                            fov_h_samples.append(abs(float(cdelt2)) * int(nax2))
                        except (ValueError, TypeError):
                            pass
                    break  # One sample per panel is enough

            if fov_w_samples and fov_h_samples and HAS_NUMPY:
                # Single panel FOV in degrees → full mosaic FOV in arcminutes
                single_w = float(np.median(fov_w_samples))
                single_h = float(np.median(fov_h_samples))
                mosaic_w_arcmin = single_w * grid_shape[1] * 60.0
                mosaic_h_arcmin = single_h * grid_shape[0] * 60.0
                estimated_fov = (round(mosaic_w_arcmin, 1), round(mosaic_h_arcmin, 1))

        return {
            "total_panels": len(panels),
            "total_files": total_files,
            "grid_shape": grid_shape,
            "estimated_fov_arcmin": estimated_fov,
            "per_panel": per_panel,
        }
