#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - FRAME QUALITY ANALYSIS MODULE
================================================================================
Star detection, PSF fitting (Moffat + Gaussian), and per-frame quality scoring
for FITS/XISF/FITS.FZ astrophotography frames.

Inspired by Athenaeum's PSF analysis pipeline. Uses only scipy/numpy for star
detection (no photutils dependency).

Features:
  - Background estimation via sigma-clipped median on mesh grid
  - Peak detection using scipy.ndimage.maximum_filter
  - 2D Moffat PSF fitting with Gaussian fallback
  - Per-star metrics: FWHM, HFR, eccentricity, SNR, theta
  - Per-frame aggregated metrics + weighted quality score 0-100
  - Satellite trail detection (Rayleigh test on star angles)
  - Auto-reject suggestions with configurable thresholds
  - Batch analysis with ProcessPoolExecutor + progress callback
================================================================================
"""

import logging
import math
import os
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

try:
    from scipy import ndimage, optimize
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    from astropy.io import fits as astropy_fits
    ASTROPY_AVAILABLE = True
except ImportError:
    ASTROPY_AVAILABLE = False

try:
    from xisf import XISF
    XISF_AVAILABLE = True
except ImportError:
    XISF_AVAILABLE = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants & defaults
# ---------------------------------------------------------------------------

# Star detection defaults
DEFAULT_SNR_THRESHOLD = 5.0
DEFAULT_EDGE_MARGIN = 20          # pixels from edge to exclude
DEFAULT_SATURATION_FRACTION = 0.95  # reject peaks above this fraction of max ADU
DEFAULT_MESH_SIZE = 64            # background mesh grid cell size (pixels)
DEFAULT_SIGMA_CLIP_ITERS = 3
DEFAULT_SIGMA_CLIP_LOW = 3.0
DEFAULT_SIGMA_CLIP_HIGH = 3.0
DEFAULT_PEAK_SEP = 10             # minimum separation between detected peaks (px)
DEFAULT_CUTOUT_RADIUS = 10        # half-size of PSF fitting cutout (total = 2*r+1)
DEFAULT_MAX_STARS = 500           # keep top N stars per frame for detailed metrics
DEFAULT_FRAME_TIMEOUT = 30.0      # seconds

# Quality scoring defaults
DEFAULT_WEIGHTS = {
    'fwhm': 0.35,
    'eccentricity': 0.20,
    'snr': 0.20,
    'stars': 0.15,
    'roundness': 0.10,
}

# Normalization thresholds for quality scoring
# Format: (best_value, worst_value) — score is linearly interpolated
DEFAULT_THRESHOLDS = {
    'fwhm_arcsec': (2.0, 8.0),       # 100 at <=2", 0 at >=8"
    'eccentricity': (0.3, 0.8),       # 100 at <=0.3, 0 at >=0.8
    'snr': (50.0, 5.0),               # 100 at >=50, 0 at <=5
    'stars': (100.0, 5.0),            # 100 at >=100, 0 at <=5
    'roundness': (0.8, 0.3),          # 100 at >=0.8, 0 at <=0.3
}

# Auto-reject defaults
DEFAULT_REJECT_SCORE = 30
DEFAULT_REJECT_FWHM_FACTOR = 2.0   # reject if FWHM > factor * batch median
DEFAULT_REJECT_ECCENTRICITY = 0.7
DEFAULT_REJECT_MIN_STARS = 10

# Satellite trail detection
DEFAULT_RAYLEIGH_THRESHOLD = 0.5    # R^2 > this flags a possible trail

# FITS header keywords for plate scale computation
PIXEL_SIZE_KEYWORDS = ['XPIXSZ', 'PIXSIZE', 'PIXSIZE1', 'PIXSCALE']
FOCAL_LENGTH_KEYWORDS = ['FOCALLEN', 'FOCAL', 'FOCAL_LENGTH', 'FOCLEN', 'FL']
CDELT_KEYWORDS = ['CDELT1', 'CDELT2']  # WCS plate scale (degrees/pixel)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class StarMetrics:
    """Metrics for a single detected star after PSF fitting."""
    x: float
    y: float
    flux: float
    peak: float
    fwhm_x: float
    fwhm_y: float
    fwhm: float            # geometric mean of fwhm_x, fwhm_y
    hfr: float              # half-flux radius
    eccentricity: float
    snr: float
    theta: float            # orientation angle in degrees
    fit_method: str          # 'moffat' or 'gaussian'
    fit_residual: float


@dataclass
class FrameQualityResult:
    """Aggregated quality metrics for a single frame."""
    filepath: str
    star_count: int
    fwhm_median: float
    fwhm_std: float
    hfr_median: float
    eccentricity_median: float
    snr_median: float
    background_level: float
    background_noise: float
    trailing_detected: bool
    quality_score: float
    rejection_flag: bool
    rejection_reasons: List[str] = field(default_factory=list)
    stars: List[StarMetrics] = field(default_factory=list)
    plate_scale: float = 0.0       # arcsec/pixel from header (0 = unknown)
    analysis_time_ms: float = 0.0
    error: Optional[str] = None    # non-None if analysis failed


# ---------------------------------------------------------------------------
# File reading utilities
# ---------------------------------------------------------------------------

def _read_image_data(filepath: str) -> Tuple[np.ndarray, dict]:
    """
    Read image data and header from FITS, XISF, or FITS.FZ file.

    Returns:
        (data_2d, header_dict) — data is always 2D float64.
        For color images, luminance is computed as weighted average of channels.

    Raises:
        ValueError: if the file format is unsupported or data is unreadable.
    """
    filepath_lower = filepath.lower()
    data = None
    header = {}

    if filepath_lower.endswith('.xisf'):
        if not XISF_AVAILABLE:
            raise ValueError("xisf library not available — cannot read XISF files")
        xisf_obj = XISF(filepath)
        file_meta = xisf_obj.get_file_metadata()
        images_meta = xisf_obj.get_images_metadata()
        data = xisf_obj.read_image(0)
        # Build a flat header dict from XISF metadata
        if images_meta:
            meta = images_meta[0]
            if 'FITSKeywords' in meta:
                for key, val_list in meta['FITSKeywords'].items():
                    if val_list:
                        header[key] = val_list[0].get('value', '')

    elif filepath_lower.endswith('.fits.fz') or filepath_lower.endswith('.fz'):
        if not ASTROPY_AVAILABLE:
            raise ValueError("astropy not available — cannot read FITS.FZ files")
        with astropy_fits.open(filepath, memmap=False) as hdul:
            # Compressed FITS: data is in extension 1
            ext = 1 if len(hdul) > 1 else 0
            data = hdul[ext].data
            header = dict(hdul[ext].header)

    elif filepath_lower.endswith(('.fits', '.fit', '.fts')):
        if not ASTROPY_AVAILABLE:
            raise ValueError("astropy not available — cannot read FITS files")
        # memmap=False required for ASIAIR BZERO/BSCALE compatibility
        with astropy_fits.open(filepath, memmap=False) as hdul:
            data = hdul[0].data
            header = dict(hdul[0].header)
            # Some files store data in extension 1 when primary is empty
            if data is None and len(hdul) > 1:
                data = hdul[1].data
                header = dict(hdul[1].header)

    else:
        raise ValueError(f"Unsupported file format: {os.path.basename(filepath)}")

    if data is None:
        raise ValueError(f"No image data found in {os.path.basename(filepath)}")

    # Convert to float64 for analysis
    data = np.asarray(data, dtype=np.float64)

    # Handle 3D arrays (color images) — compute luminance
    if data.ndim == 3:
        if data.shape[0] in (1, 3, 4):
            # Channel-first: (C, H, W)
            if data.shape[0] == 1:
                data = data[0]
            elif data.shape[0] == 3:
                # ITU-R BT.601 luminance weights
                data = 0.2126 * data[0] + 0.7152 * data[1] + 0.0722 * data[2]
            else:  # 4 channels — ignore alpha
                data = 0.2126 * data[0] + 0.7152 * data[1] + 0.0722 * data[2]
        elif data.shape[2] in (1, 3, 4):
            # Channel-last: (H, W, C)
            if data.shape[2] == 1:
                data = data[:, :, 0]
            elif data.shape[2] == 3:
                data = 0.2126 * data[:, :, 0] + 0.7152 * data[:, :, 1] + 0.0722 * data[:, :, 2]
            else:
                data = 0.2126 * data[:, :, 0] + 0.7152 * data[:, :, 1] + 0.0722 * data[:, :, 2]
        else:
            # Unknown layout — take first slice
            data = data[0]

    if data.ndim != 2:
        raise ValueError(f"Cannot reduce image to 2D (shape={data.shape})")

    return data, header


def _extract_plate_scale(header: dict) -> float:
    """
    Extract plate scale in arcsec/pixel from FITS header.

    Tries:
      1. WCS CDELT1 keyword (degrees/pixel → arcsec/pixel)
      2. XPIXSZ (µm) + FOCALLEN (mm) → arcsec_per_pixel = XPIXSZ * 206.265 / FOCALLEN

    Returns:
        Plate scale in arcsec/pixel, or 0.0 if not determinable.
    """
    # Method 1: WCS plate scale from CDELT keywords
    for key in CDELT_KEYWORDS:
        val = header.get(key)
        if val is not None:
            try:
                cdelt = abs(float(val))
                if cdelt > 0:
                    return cdelt * 3600.0  # degrees → arcsec
            except (ValueError, TypeError):
                pass

    # Method 2: pixel size + focal length
    pixel_size_um = None
    for key in PIXEL_SIZE_KEYWORDS:
        val = header.get(key)
        if val is not None:
            try:
                pixel_size_um = float(val)
                if pixel_size_um > 0:
                    break
                pixel_size_um = None
            except (ValueError, TypeError):
                pixel_size_um = None

    focal_length_mm = None
    for key in FOCAL_LENGTH_KEYWORDS:
        val = header.get(key)
        if val is not None:
            try:
                focal_length_mm = float(val)
                if focal_length_mm > 0:
                    break
                focal_length_mm = None
            except (ValueError, TypeError):
                focal_length_mm = None

    if pixel_size_um and focal_length_mm:
        return pixel_size_um * 206.265 / focal_length_mm

    return 0.0


# ---------------------------------------------------------------------------
# Background estimation
# ---------------------------------------------------------------------------

def estimate_background(data: np.ndarray, mesh_size: int = DEFAULT_MESH_SIZE,
                        sigma_clip_iters: int = DEFAULT_SIGMA_CLIP_ITERS,
                        sigma_low: float = DEFAULT_SIGMA_CLIP_LOW,
                        sigma_high: float = DEFAULT_SIGMA_CLIP_HIGH
                        ) -> Tuple[np.ndarray, np.ndarray]:
    """
    Estimate spatially varying background level and noise using a mesh grid
    with sigma-clipped statistics.

    Returns:
        (background_map, noise_map) — same shape as input data.
    """
    h, w = data.shape
    ny = max(1, h // mesh_size)
    nx = max(1, w // mesh_size)

    bg_grid = np.zeros((ny, nx), dtype=np.float64)
    noise_grid = np.zeros((ny, nx), dtype=np.float64)

    for iy in range(ny):
        y0 = iy * h // ny
        y1 = (iy + 1) * h // ny
        for ix in range(nx):
            x0 = ix * w // nx
            x1 = (ix + 1) * w // nx
            cell = data[y0:y1, x0:x1].ravel()

            # Sigma-clipped median for background, MAD for noise
            clipped = cell.copy()
            for _ in range(sigma_clip_iters):
                if len(clipped) < 5:
                    break
                med = np.median(clipped)
                mad = np.median(np.abs(clipped - med))
                sigma_est = mad * 1.4826  # MAD → sigma
                if sigma_est <= 0:
                    break
                mask = (clipped >= med - sigma_low * sigma_est) & \
                       (clipped <= med + sigma_high * sigma_est)
                if mask.sum() < 5:
                    break
                clipped = clipped[mask]

            bg_grid[iy, ix] = np.median(clipped) if len(clipped) > 0 else 0.0
            mad_val = np.median(np.abs(clipped - bg_grid[iy, ix])) if len(clipped) > 0 else 0.0
            noise_grid[iy, ix] = mad_val * 1.4826

    # Bilinear interpolation to full resolution
    from scipy.ndimage import zoom
    zoom_y = h / ny
    zoom_x = w / nx
    background_map = zoom(bg_grid, (zoom_y, zoom_x), order=1)
    noise_map = zoom(noise_grid, (zoom_y, zoom_x), order=1)

    # Ensure output shape matches input exactly
    background_map = background_map[:h, :w]
    noise_map = noise_map[:h, :w]

    return background_map, noise_map


# ---------------------------------------------------------------------------
# Star detection
# ---------------------------------------------------------------------------

def detect_stars(data: np.ndarray,
                 background_map: np.ndarray,
                 noise_map: np.ndarray,
                 snr_threshold: float = DEFAULT_SNR_THRESHOLD,
                 edge_margin: int = DEFAULT_EDGE_MARGIN,
                 saturation_fraction: float = DEFAULT_SATURATION_FRACTION,
                 peak_separation: int = DEFAULT_PEAK_SEP,
                 max_stars: int = DEFAULT_MAX_STARS
                 ) -> List[Tuple[int, int, float, float]]:
    """
    Detect star candidates using local maxima on background-subtracted data.

    Returns:
        List of (x, y, flux, peak) tuples, sorted by flux descending,
        limited to max_stars entries. x/y are pixel coordinates (col, row).
    """
    if not SCIPY_AVAILABLE:
        logger.error("scipy not available — star detection disabled")
        return []

    h, w = data.shape
    bg_sub = data - background_map

    # Compute saturation threshold from raw data
    data_max = np.nanmax(data)
    sat_level = data_max * saturation_fraction

    # Local maximum filter — peaks must be the local max within a neighborhood
    neighborhood_size = 2 * peak_separation + 1
    local_max = ndimage.maximum_filter(bg_sub, size=neighborhood_size)
    is_peak = (bg_sub == local_max)

    # SNR threshold: signal / noise > threshold
    with np.errstate(divide='ignore', invalid='ignore'):
        snr_map = np.where(noise_map > 0, bg_sub / noise_map, 0.0)
    is_significant = snr_map >= snr_threshold

    # Edge exclusion
    edge_mask = np.zeros((h, w), dtype=bool)
    if edge_margin > 0 and 2 * edge_margin < min(h, w):
        edge_mask[edge_margin:h - edge_margin, edge_margin:w - edge_margin] = True
    else:
        edge_mask[:] = True

    # Saturation rejection
    not_saturated = data < sat_level

    # Combine all masks
    candidates = is_peak & is_significant & edge_mask & not_saturated

    # Extract coordinates (row, col)
    rows, cols = np.where(candidates)
    if len(rows) == 0:
        return []

    # Compute flux in a small aperture (5×5) and peak values
    aperture_r = 2
    stars = []
    for r, c in zip(rows, cols):
        y0 = max(0, r - aperture_r)
        y1 = min(h, r + aperture_r + 1)
        x0 = max(0, c - aperture_r)
        x1 = min(w, c + aperture_r + 1)
        cutout = bg_sub[y0:y1, x0:x1]
        flux = float(np.sum(cutout[cutout > 0]))
        peak_val = float(bg_sub[r, c])
        snr_val = float(snr_map[r, c])
        stars.append((int(c), int(r), flux, peak_val, snr_val))

    # Sort by flux descending, keep top N
    stars.sort(key=lambda s: s[2], reverse=True)
    stars = stars[:max_stars]

    # Return (x, y, flux, peak) — drop snr from tuple for external interface
    return [(s[0], s[1], s[2], s[3]) for s in stars]


# ---------------------------------------------------------------------------
# PSF fitting models
# ---------------------------------------------------------------------------

def _moffat_2d(xy, amplitude, x0, y0, alpha_x, alpha_y, beta, theta, offset):
    """2D elliptical Moffat function."""
    x, y = xy
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    dx = x - x0
    dy = y - y0
    # Rotated coordinates
    xr = cos_t * dx + sin_t * dy
    yr = -sin_t * dx + cos_t * dy
    # Elliptical radius squared
    r_sq = (xr / max(alpha_x, 1e-6)) ** 2 + (yr / max(alpha_y, 1e-6)) ** 2
    return (amplitude * (1.0 + r_sq) ** (-beta) + offset).ravel()


def _gaussian_2d(xy, amplitude, x0, y0, sigma_x, sigma_y, theta, offset):
    """2D elliptical Gaussian function."""
    x, y = xy
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    dx = x - x0
    dy = y - y0
    xr = cos_t * dx + sin_t * dy
    yr = -sin_t * dx + cos_t * dy
    exponent = -0.5 * ((xr / max(sigma_x, 1e-6)) ** 2 +
                        (yr / max(sigma_y, 1e-6)) ** 2)
    return (amplitude * np.exp(exponent) + offset).ravel()


def _compute_hfr(cutout: np.ndarray, cx: float, cy: float) -> float:
    """
    Compute Half-Flux Radius from a star cutout.

    The HFR is the radius enclosing half the total flux, computed by sorting
    pixels by distance from the centroid and finding the cumulative 50% point.
    """
    h, w = cutout.shape
    yy, xx = np.mgrid[0:h, 0:w]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)

    # Subtract background (use edge pixels)
    bg = np.median(cutout[0, :])
    signal = cutout - bg
    signal = np.maximum(signal, 0)

    total_flux = np.sum(signal)
    if total_flux <= 0:
        return 0.0

    # Sort by distance, accumulate flux
    flat_dist = dist.ravel()
    flat_signal = signal.ravel()
    order = np.argsort(flat_dist)
    cumflux = np.cumsum(flat_signal[order])
    half_flux = total_flux * 0.5

    idx = np.searchsorted(cumflux, half_flux)
    if idx >= len(flat_dist):
        idx = len(flat_dist) - 1
    return float(flat_dist[order[idx]])


def fit_star_psf(data: np.ndarray,
                 x: int, y: int,
                 background_map: np.ndarray,
                 noise_map: np.ndarray,
                 cutout_radius: int = DEFAULT_CUTOUT_RADIUS
                 ) -> Optional[StarMetrics]:
    """
    Fit a PSF model to a single star candidate.

    Attempts a 2D Moffat fit first; falls back to 2D Gaussian on failure.

    Args:
        data: Full 2D image array.
        x, y: Star candidate position (col, row).
        background_map: Background level map.
        noise_map: Background noise map.
        cutout_radius: Half-size of fitting cutout.

    Returns:
        StarMetrics if fit succeeds, None otherwise.
    """
    if not SCIPY_AVAILABLE:
        return None

    h, w = data.shape
    r = cutout_radius
    size = 2 * r + 1

    # Bounds check
    if y - r < 0 or y + r + 1 > h or x - r < 0 or x + r + 1 > w:
        return None

    cutout = data[y - r:y + r + 1, x - r:x + r + 1].copy()
    bg_local = background_map[y, x]
    noise_local = max(noise_map[y, x], 1e-10)

    # Background-subtracted cutout
    cutout_sub = cutout - bg_local

    # Initial parameter estimates
    peak_val = cutout_sub[r, r]
    if peak_val <= 0:
        return None

    # Create coordinate grids for the cutout
    yy, xx = np.mgrid[0:size, 0:size]
    xy = (xx.astype(np.float64), yy.astype(np.float64))

    snr_star = peak_val / noise_local

    fit_method = None
    fwhm_x = 0.0
    fwhm_y = 0.0
    theta_deg = 0.0
    fit_residual = np.inf

    # --- Attempt Moffat fit ---
    try:
        # Initial guesses: amplitude, x0, y0, alpha_x, alpha_y, beta, theta, offset
        p0_moffat = [peak_val, float(r), float(r), 2.5, 2.5, 3.0, 0.0, 0.0]
        bounds_lo = [0, r - 3, r - 3, 0.5, 0.5, 1.0, -math.pi, -peak_val * 0.5]
        bounds_hi = [peak_val * 2, r + 3, r + 3, r, r, 10.0, math.pi, peak_val * 0.5]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            popt, pcov = optimize.curve_fit(
                _moffat_2d, xy, cutout_sub.ravel(),
                p0=p0_moffat,
                bounds=(bounds_lo, bounds_hi),
                maxfev=500
            )

        amp, cx, cy, alpha_x, alpha_y, beta, theta_rad, offset = popt

        # Validate parameters
        if alpha_x < 0.3 or alpha_y < 0.3 or beta < 1.0:
            raise ValueError("Moffat parameters out of physical range")

        # FWHM from Moffat: FWHM = 2 * alpha * sqrt(2^(1/beta) - 1)
        factor = 2.0 * math.sqrt(2.0 ** (1.0 / beta) - 1.0)
        fwhm_x = alpha_x * factor
        fwhm_y = alpha_y * factor
        theta_deg = math.degrees(theta_rad) % 180.0

        # Fit residual (normalized RMS)
        model = _moffat_2d(xy, *popt)
        residual = cutout_sub.ravel() - model
        fit_residual = float(np.sqrt(np.mean(residual ** 2)) / max(amp, 1e-10))

        if fit_residual > 0.5:
            raise ValueError("Moffat fit residual too high")

        fit_method = 'moffat'

    except (RuntimeError, ValueError, TypeError):
        # --- Fallback to Gaussian ---
        try:
            p0_gauss = [peak_val, float(r), float(r), 2.0, 2.0, 0.0, 0.0]
            bounds_lo = [0, r - 3, r - 3, 0.5, 0.5, -math.pi, -peak_val * 0.5]
            bounds_hi = [peak_val * 2, r + 3, r + 3, r, r, math.pi, peak_val * 0.5]

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                popt, pcov = optimize.curve_fit(
                    _gaussian_2d, xy, cutout_sub.ravel(),
                    p0=p0_gauss,
                    bounds=(bounds_lo, bounds_hi),
                    maxfev=500
                )

            amp, cx, cy, sigma_x, sigma_y, theta_rad, offset = popt

            if sigma_x < 0.3 or sigma_y < 0.3:
                return None

            # FWHM from Gaussian: FWHM = 2 * sqrt(2 * ln(2)) * sigma ≈ 2.3548 * sigma
            fwhm_factor = 2.0 * math.sqrt(2.0 * math.log(2.0))
            fwhm_x = sigma_x * fwhm_factor
            fwhm_y = sigma_y * fwhm_factor
            theta_deg = math.degrees(theta_rad) % 180.0

            model = _gaussian_2d(xy, *popt)
            residual = cutout_sub.ravel() - model
            fit_residual = float(np.sqrt(np.mean(residual ** 2)) / max(amp, 1e-10))

            if fit_residual > 0.5:
                return None

            fit_method = 'gaussian'

        except (RuntimeError, ValueError, TypeError):
            return None

    # Geometric mean FWHM
    fwhm_geom = math.sqrt(max(fwhm_x * fwhm_y, 0.0))

    # Eccentricity: e = sqrt(1 - (minor/major)^2)
    fwhm_major = max(fwhm_x, fwhm_y)
    fwhm_minor = min(fwhm_x, fwhm_y)
    if fwhm_major > 0:
        ratio = fwhm_minor / fwhm_major
        eccentricity = math.sqrt(1.0 - ratio * ratio)
    else:
        eccentricity = 0.0

    # HFR from the cutout
    hfr = _compute_hfr(cutout, cx, cy)

    # Flux: sum of background-subtracted cutout within 2*FWHM radius
    flux_radius = max(fwhm_geom, 2.0)
    yy_f, xx_f = np.mgrid[0:size, 0:size]
    dist_sq = (xx_f - cx) ** 2 + (yy_f - cy) ** 2
    flux_mask = dist_sq <= flux_radius ** 2
    flux = float(np.sum(cutout_sub[flux_mask]))

    return StarMetrics(
        x=float(x),
        y=float(y),
        flux=max(flux, 0.0),
        peak=float(peak_val),
        fwhm_x=fwhm_x,
        fwhm_y=fwhm_y,
        fwhm=fwhm_geom,
        hfr=hfr,
        eccentricity=eccentricity,
        snr=snr_star,
        theta=theta_deg,
        fit_method=fit_method,
        fit_residual=fit_residual,
    )


# ---------------------------------------------------------------------------
# Satellite trail detection (Rayleigh test)
# ---------------------------------------------------------------------------

def detect_satellite_trail(stars: List[StarMetrics],
                           rayleigh_threshold: float = DEFAULT_RAYLEIGH_THRESHOLD
                           ) -> bool:
    """
    Detect possible satellite trails using the Rayleigh test on star angles.

    If stars are randomly oriented, their angles (theta) are uniformly distributed.
    A satellite trail creates many stars (or elongated PSFs) aligned in one direction,
    producing a strong directional clustering.

    The Rayleigh test statistic R^2 = (sum(cos(2*theta))^2 + sum(sin(2*theta))^2) / n^2
    where the factor 2 accounts for 180° periodicity of angles.

    Returns:
        True if trailing is detected (R^2 > threshold).
    """
    if len(stars) < 5:
        return False

    # Use 2*theta to handle 180° symmetry of elongation angles
    angles_rad = [math.radians(s.theta * 2.0) for s in stars]
    n = len(angles_rad)

    sum_cos = sum(math.cos(a) for a in angles_rad)
    sum_sin = sum(math.sin(a) for a in angles_rad)

    r_squared = (sum_cos ** 2 + sum_sin ** 2) / (n * n)
    return r_squared > rayleigh_threshold


# ---------------------------------------------------------------------------
# Quality scoring
# ---------------------------------------------------------------------------

def _normalize_metric(value: float, best: float, worst: float) -> float:
    """
    Normalize a metric value to a 0-100 quality score.

    Args:
        value: The measured metric value.
        best: The metric value that corresponds to score 100.
        worst: The metric value that corresponds to score 0.

    Returns:
        Score in [0, 100].
    """
    if abs(best - worst) < 1e-10:
        return 50.0

    score = (value - worst) / (best - worst) * 100.0
    return max(0.0, min(100.0, score))


def compute_quality_score(fwhm_arcsec: float,
                          eccentricity: float,
                          snr: float,
                          star_count: int,
                          roundness: float,
                          weights: Optional[Dict[str, float]] = None,
                          thresholds: Optional[Dict[str, Tuple[float, float]]] = None
                          ) -> float:
    """
    Compute a weighted composite quality score (0-100) from frame metrics.

    Args:
        fwhm_arcsec: Median FWHM in arcseconds (0 if plate scale unknown → uses pixels).
        eccentricity: Median eccentricity (0=round, 1=elongated).
        snr: Median signal-to-noise ratio.
        star_count: Number of detected stars.
        roundness: 1 - eccentricity.
        weights: Override default weights dict.
        thresholds: Override default normalization thresholds.

    Returns:
        Quality score in [0, 100].
    """
    w = weights or DEFAULT_WEIGHTS
    t = thresholds or DEFAULT_THRESHOLDS

    # Normalize each metric
    scores = {
        'fwhm': _normalize_metric(fwhm_arcsec, *t['fwhm_arcsec']),
        'eccentricity': _normalize_metric(eccentricity, *t['eccentricity']),
        'snr': _normalize_metric(snr, *t['snr']),
        'stars': _normalize_metric(float(star_count), *t['stars']),
        'roundness': _normalize_metric(roundness, *t['roundness']),
    }

    # Weighted sum
    total_weight = sum(w.values())
    if total_weight <= 0:
        return 0.0

    composite = sum(scores[k] * w.get(k, 0) for k in scores) / total_weight
    return round(max(0.0, min(100.0, composite)), 1)


# ---------------------------------------------------------------------------
# Auto-reject logic
# ---------------------------------------------------------------------------

def check_rejection(result: FrameQualityResult,
                    score_threshold: float = DEFAULT_REJECT_SCORE,
                    eccentricity_max: float = DEFAULT_REJECT_ECCENTRICITY,
                    min_stars: int = DEFAULT_REJECT_MIN_STARS
                    ) -> Tuple[bool, List[str]]:
    """
    Check if a frame should be flagged for rejection.

    Returns:
        (should_reject, list_of_reasons)
    """
    reasons = []

    if result.quality_score < score_threshold:
        reasons.append(f"Quality score {result.quality_score:.1f} < {score_threshold}")

    if result.eccentricity_median > eccentricity_max:
        reasons.append(f"Eccentricity {result.eccentricity_median:.3f} > {eccentricity_max}")

    if result.star_count < min_stars:
        reasons.append(f"Star count {result.star_count} < {min_stars}")

    if result.trailing_detected:
        reasons.append("Possible satellite trail detected")

    return len(reasons) > 0, reasons


def check_batch_rejection(results: List[FrameQualityResult],
                          fwhm_factor: float = DEFAULT_REJECT_FWHM_FACTOR,
                          score_threshold: float = DEFAULT_REJECT_SCORE,
                          eccentricity_max: float = DEFAULT_REJECT_ECCENTRICITY,
                          min_stars: int = DEFAULT_REJECT_MIN_STARS
                          ) -> None:
    """
    Apply rejection checks across a batch, including FWHM-relative rejection.

    Mutates each FrameQualityResult in place (sets rejection_flag, rejection_reasons).
    """
    # Compute batch FWHM median (only from successful analyses)
    valid_fwhms = [r.fwhm_median for r in results if r.error is None and r.fwhm_median > 0]
    batch_fwhm_median = float(np.median(valid_fwhms)) if valid_fwhms else 0.0

    for result in results:
        if result.error is not None:
            result.rejection_flag = True
            result.rejection_reasons = [f"Analysis error: {result.error}"]
            continue

        reject, reasons = check_rejection(
            result,
            score_threshold=score_threshold,
            eccentricity_max=eccentricity_max,
            min_stars=min_stars,
        )

        # FWHM relative to batch
        if batch_fwhm_median > 0 and result.fwhm_median > fwhm_factor * batch_fwhm_median:
            reasons.append(
                f"FWHM {result.fwhm_median:.2f} > {fwhm_factor}x batch median "
                f"({batch_fwhm_median:.2f})"
            )
            reject = True

        result.rejection_flag = reject
        result.rejection_reasons = reasons


# ---------------------------------------------------------------------------
# Single frame analysis
# ---------------------------------------------------------------------------

def analyze_frame(filepath: str,
                  snr_threshold: float = DEFAULT_SNR_THRESHOLD,
                  edge_margin: int = DEFAULT_EDGE_MARGIN,
                  cutout_radius: int = DEFAULT_CUTOUT_RADIUS,
                  max_stars: int = DEFAULT_MAX_STARS,
                  weights: Optional[Dict[str, float]] = None,
                  thresholds: Optional[Dict[str, Tuple[float, float]]] = None,
                  ) -> FrameQualityResult:
    """
    Perform complete quality analysis on a single FITS/XISF/FITS.FZ frame.

    Args:
        filepath: Path to the image file.
        snr_threshold: Minimum SNR for star detection.
        edge_margin: Pixels to exclude from edges.
        cutout_radius: Half-size of PSF fitting cutout.
        max_stars: Maximum stars to keep for detailed metrics.
        weights: Quality score weights override.
        thresholds: Quality score normalization thresholds override.

    Returns:
        FrameQualityResult with all metrics, or with error field set on failure.
    """
    t0 = time.perf_counter()

    # Default error result
    def _error_result(msg: str) -> FrameQualityResult:
        elapsed = (time.perf_counter() - t0) * 1000.0
        return FrameQualityResult(
            filepath=filepath, star_count=0,
            fwhm_median=0.0, fwhm_std=0.0, hfr_median=0.0,
            eccentricity_median=0.0, snr_median=0.0,
            background_level=0.0, background_noise=0.0,
            trailing_detected=False, quality_score=0.0,
            rejection_flag=True, rejection_reasons=[msg],
            stars=[], plate_scale=0.0, analysis_time_ms=elapsed,
            error=msg,
        )

    if not SCIPY_AVAILABLE:
        return _error_result("scipy not available")

    try:
        data, header = _read_image_data(filepath)
    except Exception as e:
        logger.warning("Failed to read %s: %s", os.path.basename(filepath), e)
        return _error_result(f"Read error: {e}")

    if data.size == 0:
        return _error_result("Empty image data")

    # Extract plate scale
    plate_scale = _extract_plate_scale(header)

    # Background estimation
    try:
        bg_map, noise_map = estimate_background(data)
    except Exception as e:
        logger.warning("Background estimation failed for %s: %s",
                       os.path.basename(filepath), e)
        return _error_result(f"Background estimation error: {e}")

    bg_level = float(np.median(bg_map))
    bg_noise = float(np.median(noise_map))

    if bg_noise <= 0:
        return _error_result("Zero background noise — blank or saturated frame")

    # Star detection
    candidates = detect_stars(
        data, bg_map, noise_map,
        snr_threshold=snr_threshold,
        edge_margin=edge_margin,
        max_stars=max_stars,
    )

    if len(candidates) == 0:
        elapsed = (time.perf_counter() - t0) * 1000.0
        return FrameQualityResult(
            filepath=filepath, star_count=0,
            fwhm_median=0.0, fwhm_std=0.0, hfr_median=0.0,
            eccentricity_median=0.0, snr_median=0.0,
            background_level=bg_level, background_noise=bg_noise,
            trailing_detected=False, quality_score=0.0,
            rejection_flag=True,
            rejection_reasons=["No stars detected"],
            stars=[], plate_scale=plate_scale,
            analysis_time_ms=elapsed,
        )

    # PSF fitting for each candidate
    fitted_stars: List[StarMetrics] = []
    for (cx, cy, flux, peak) in candidates:
        star = fit_star_psf(data, cx, cy, bg_map, noise_map,
                            cutout_radius=cutout_radius)
        if star is not None:
            fitted_stars.append(star)

    if len(fitted_stars) == 0:
        elapsed = (time.perf_counter() - t0) * 1000.0
        return FrameQualityResult(
            filepath=filepath,
            star_count=len(candidates),
            fwhm_median=0.0, fwhm_std=0.0, hfr_median=0.0,
            eccentricity_median=0.0, snr_median=0.0,
            background_level=bg_level, background_noise=bg_noise,
            trailing_detected=False, quality_score=0.0,
            rejection_flag=True,
            rejection_reasons=["PSF fitting failed for all candidates"],
            stars=[], plate_scale=plate_scale,
            analysis_time_ms=elapsed,
        )

    # Aggregate metrics
    fwhms = np.array([s.fwhm for s in fitted_stars])
    hfrs = np.array([s.hfr for s in fitted_stars])
    eccs = np.array([s.eccentricity for s in fitted_stars])
    snrs = np.array([s.snr for s in fitted_stars])

    fwhm_median = float(np.median(fwhms))
    fwhm_std = float(np.std(fwhms))
    hfr_median = float(np.median(hfrs))
    ecc_median = float(np.median(eccs))
    snr_median = float(np.median(snrs))
    roundness = 1.0 - ecc_median

    # Satellite trail detection
    trailing = detect_satellite_trail(fitted_stars)

    # Quality score — convert FWHM to arcseconds if plate scale is known
    if plate_scale > 0:
        fwhm_arcsec = fwhm_median * plate_scale
    else:
        # No plate scale: assume a reasonable default (1.0 arcsec/pixel)
        # and use pixel FWHM directly with slightly relaxed thresholds
        fwhm_arcsec = fwhm_median

    score = compute_quality_score(
        fwhm_arcsec=fwhm_arcsec,
        eccentricity=ecc_median,
        snr=snr_median,
        star_count=len(fitted_stars),
        roundness=roundness,
        weights=weights,
        thresholds=thresholds,
    )

    elapsed = (time.perf_counter() - t0) * 1000.0

    result = FrameQualityResult(
        filepath=filepath,
        star_count=len(fitted_stars),
        fwhm_median=round(fwhm_median, 3),
        fwhm_std=round(fwhm_std, 3),
        hfr_median=round(hfr_median, 3),
        eccentricity_median=round(ecc_median, 4),
        snr_median=round(snr_median, 1),
        background_level=round(bg_level, 1),
        background_noise=round(bg_noise, 2),
        trailing_detected=trailing,
        quality_score=score,
        rejection_flag=False,
        rejection_reasons=[],
        stars=fitted_stars[:max_stars],
        plate_scale=round(plate_scale, 4),
        analysis_time_ms=round(elapsed, 1),
    )

    # Apply single-frame rejection checks (batch-relative checks come later)
    reject, reasons = check_rejection(result)
    result.rejection_flag = reject
    result.rejection_reasons = reasons

    return result


# ---------------------------------------------------------------------------
# Batch analysis (parallel)
# ---------------------------------------------------------------------------

def _analyze_frame_wrapper(args: tuple) -> FrameQualityResult:
    """
    Wrapper for ProcessPoolExecutor — unpacks arguments for analyze_frame.
    Must be a top-level function for pickling.
    """
    filepath, kwargs = args
    try:
        return analyze_frame(filepath, **kwargs)
    except Exception as e:
        return FrameQualityResult(
            filepath=filepath, star_count=0,
            fwhm_median=0.0, fwhm_std=0.0, hfr_median=0.0,
            eccentricity_median=0.0, snr_median=0.0,
            background_level=0.0, background_noise=0.0,
            trailing_detected=False, quality_score=0.0,
            rejection_flag=True,
            rejection_reasons=[f"Unexpected error: {e}"],
            stars=[], plate_scale=0.0, analysis_time_ms=0.0,
            error=str(e),
        )


def analyze_batch(filepaths: List[str],
                  max_workers: Optional[int] = None,
                  callback: Optional[Callable[[int, int, FrameQualityResult], None]] = None,
                  snr_threshold: float = DEFAULT_SNR_THRESHOLD,
                  edge_margin: int = DEFAULT_EDGE_MARGIN,
                  cutout_radius: int = DEFAULT_CUTOUT_RADIUS,
                  max_stars: int = DEFAULT_MAX_STARS,
                  weights: Optional[Dict[str, float]] = None,
                  thresholds: Optional[Dict[str, Tuple[float, float]]] = None,
                  fwhm_reject_factor: float = DEFAULT_REJECT_FWHM_FACTOR,
                  score_threshold: float = DEFAULT_REJECT_SCORE,
                  ) -> List[FrameQualityResult]:
    """
    Analyze a batch of frames in parallel using ProcessPoolExecutor.

    Args:
        filepaths: List of file paths to analyze.
        max_workers: Number of parallel workers (default: CPU count / 2).
        callback: Optional progress callback(current_index, total, result).
        snr_threshold: Minimum SNR for star detection.
        edge_margin: Pixels to exclude from edges.
        cutout_radius: Half-size of PSF fitting cutout.
        max_stars: Maximum stars to keep per frame.
        weights: Quality score weights override.
        thresholds: Quality score thresholds override.
        fwhm_reject_factor: Reject if FWHM > factor * batch median.
        score_threshold: Reject if quality_score < threshold.

    Returns:
        List of FrameQualityResult, one per input file, in input order.
    """
    if not filepaths:
        return []

    total = len(filepaths)

    if max_workers is None:
        cpu_count = os.cpu_count() or 4
        max_workers = max(1, cpu_count // 2)

    kwargs = {
        'snr_threshold': snr_threshold,
        'edge_margin': edge_margin,
        'cutout_radius': cutout_radius,
        'max_stars': max_stars,
        'weights': weights,
        'thresholds': thresholds,
    }

    results: Dict[str, FrameQualityResult] = {}

    # Use single-process for small batches or debugging
    if total <= 2 or max_workers <= 1:
        for i, fp in enumerate(filepaths):
            result = analyze_frame(fp, **kwargs)
            results[fp] = result
            if callback:
                try:
                    callback(i + 1, total, result)
                except Exception:
                    pass
    else:
        # Parallel execution
        tasks = [(fp, kwargs) for fp in filepaths]
        completed = 0

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {
                executor.submit(_analyze_frame_wrapper, task): task[0]
                for task in tasks
            }

            for future in as_completed(future_to_path):
                fp = future_to_path[future]
                try:
                    result = future.result(timeout=DEFAULT_FRAME_TIMEOUT)
                except Exception as e:
                    result = FrameQualityResult(
                        filepath=fp, star_count=0,
                        fwhm_median=0.0, fwhm_std=0.0, hfr_median=0.0,
                        eccentricity_median=0.0, snr_median=0.0,
                        background_level=0.0, background_noise=0.0,
                        trailing_detected=False, quality_score=0.0,
                        rejection_flag=True,
                        rejection_reasons=[f"Worker error: {e}"],
                        stars=[], plate_scale=0.0, analysis_time_ms=0.0,
                        error=str(e),
                    )

                results[fp] = result
                completed += 1

                if callback:
                    try:
                        callback(completed, total, result)
                    except Exception:
                        pass

    # Preserve input order
    ordered_results = [results[fp] for fp in filepaths]

    # Apply batch-level rejection (FWHM relative to median)
    check_batch_rejection(
        ordered_results,
        fwhm_factor=fwhm_reject_factor,
        score_threshold=score_threshold,
    )

    return ordered_results


# ---------------------------------------------------------------------------
# Utility functions for external use
# ---------------------------------------------------------------------------

def get_batch_summary(results: List[FrameQualityResult]) -> Dict:
    """
    Compute summary statistics across a batch of analyzed frames.

    Returns:
        Dict with batch-level statistics (useful for reporting/display).
    """
    valid = [r for r in results if r.error is None and r.star_count > 0]

    if not valid:
        return {
            'total_frames': len(results),
            'analyzed_frames': 0,
            'rejected_frames': sum(1 for r in results if r.rejection_flag),
            'avg_quality_score': 0.0,
            'median_fwhm': 0.0,
            'median_hfr': 0.0,
            'median_eccentricity': 0.0,
            'median_snr': 0.0,
            'median_stars': 0,
            'best_frame': None,
            'worst_frame': None,
        }

    scores = [r.quality_score for r in valid]
    fwhms = [r.fwhm_median for r in valid]
    hfrs = [r.hfr_median for r in valid]
    eccs = [r.eccentricity_median for r in valid]
    snrs = [r.snr_median for r in valid]
    star_counts = [r.star_count for r in valid]

    best_idx = int(np.argmax(scores))
    worst_idx = int(np.argmin(scores))

    return {
        'total_frames': len(results),
        'analyzed_frames': len(valid),
        'rejected_frames': sum(1 for r in results if r.rejection_flag),
        'avg_quality_score': round(float(np.mean(scores)), 1),
        'median_quality_score': round(float(np.median(scores)), 1),
        'std_quality_score': round(float(np.std(scores)), 1),
        'median_fwhm': round(float(np.median(fwhms)), 3),
        'median_hfr': round(float(np.median(hfrs)), 3),
        'median_eccentricity': round(float(np.median(eccs)), 4),
        'median_snr': round(float(np.median(snrs)), 1),
        'median_stars': int(np.median(star_counts)),
        'best_frame': valid[best_idx].filepath,
        'worst_frame': valid[worst_idx].filepath,
        'best_score': valid[best_idx].quality_score,
        'worst_score': valid[worst_idx].quality_score,
    }


def format_result_summary(result: FrameQualityResult, lang: str = 'en') -> str:
    """
    Format a single frame result as a human-readable summary string.

    Args:
        result: The analysis result to format.
        lang: 'en' or 'fr' for bilingual output.

    Returns:
        Multi-line summary string.
    """
    name = os.path.basename(result.filepath)

    if result.error:
        if lang == 'fr':
            return f"{name} — Erreur : {result.error}"
        return f"{name} — Error: {result.error}"

    ps_info = ""
    if result.plate_scale > 0:
        fwhm_arcsec = result.fwhm_median * result.plate_scale
        ps_info = f" ({fwhm_arcsec:.2f}\")"

    if lang == 'fr':
        lines = [
            f"{name} — Score : {result.quality_score:.1f}/100",
            f"  Étoiles : {result.star_count}, "
            f"FWHM : {result.fwhm_median:.2f}px{ps_info}, "
            f"HFR : {result.hfr_median:.2f}px",
            f"  Excentricité : {result.eccentricity_median:.3f}, "
            f"SNR : {result.snr_median:.1f}, "
            f"Fond : {result.background_level:.0f} ± {result.background_noise:.1f}",
        ]
        if result.trailing_detected:
            lines.append("  ⚠ Traînée satellite possible détectée")
        if result.rejection_flag:
            lines.append(f"  ✗ Rejeté : {', '.join(result.rejection_reasons)}")
    else:
        lines = [
            f"{name} — Score: {result.quality_score:.1f}/100",
            f"  Stars: {result.star_count}, "
            f"FWHM: {result.fwhm_median:.2f}px{ps_info}, "
            f"HFR: {result.hfr_median:.2f}px",
            f"  Eccentricity: {result.eccentricity_median:.3f}, "
            f"SNR: {result.snr_median:.1f}, "
            f"Background: {result.background_level:.0f} ± {result.background_noise:.1f}",
        ]
        if result.trailing_detected:
            lines.append("  ⚠ Possible satellite trail detected")
        if result.rejection_flag:
            lines.append(f"  ✗ Rejected: {', '.join(result.rejection_reasons)}")

    lines.append(f"  [{result.analysis_time_ms:.0f}ms]")
    return "\n".join(lines)
