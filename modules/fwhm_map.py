#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - FWHM HEATMAP ANALYSIS MODULE
================================================================================
Spatial FWHM analysis with star detection, 2D Moffat fitting, Nadaraya-Watson
kernel regression heatmap, and 9-region corner statistics.

Inspired by Astronalyze (ricksastro) but adapted to AstroManager's architecture
and conventions. Provides an objective, spatially-resolved view of the optical
quality across the field of view — useful for diagnosing tilt, spacing errors,
coma, and field curvature.

Features:
  - Star detection via photutils DAOStarFinder (fallback: scipy peak detection)
  - 2D elliptical Moffat PSF fitting with eccentricity and SNR
  - 7x7 grid selection for uniform spatial coverage (max ~147 stars)
  - Spatial outlier rejection via cKDTree local neighbors
  - Nadaraya-Watson kernel regression for smooth 300x300 heatmap
  - 9-region corner statistics (3x3 grid: TL/T/TR/L/C/R/BL/B/BR)
  - Contour level computation for overlay rendering
  - Feature-gated imports: numpy (required), scipy, photutils, matplotlib

Pure logic module — no GUI code. Thread-safe (stateless analyzer).
================================================================================
"""

import logging
import math
import warnings
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature gates
# ---------------------------------------------------------------------------

HAS_NUMPY = False
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    logger.error("numpy not available — FWHMMapAnalyzer disabled")

HAS_SCIPY = False
try:
    from scipy import ndimage, optimize
    from scipy.spatial import cKDTree
    HAS_SCIPY = True
except ImportError:
    logger.warning("scipy not available — star detection limited to photutils, "
                   "Moffat fitting and spatial outlier rejection disabled")

HAS_PHOTUTILS = False
try:
    from photutils.detection import DAOStarFinder
    HAS_PHOTUTILS = True
except ImportError:
    logger.info("photutils not available — using scipy fallback for star detection")

HAS_MATPLOTLIB = False
try:
    import matplotlib
    HAS_MATPLOTLIB = True
except ImportError:
    logger.info("matplotlib not available — contour computation will use "
                "numpy percentile fallback")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Star detection
DEFAULT_THRESHOLD_SIGMA = 5.0
DEFAULT_EDGE_MARGIN = 30           # pixels from edge to exclude
DEFAULT_PEAK_SEP = 10              # min separation between detected peaks (px)
DEFAULT_MAX_STARS_PER_CELL = 3     # brightest stars kept per grid cell
DEFAULT_GRID_CELLS = 7             # 7x7 spatial grid for selection

# Moffat fitting
DEFAULT_BOX_SIZE = 21              # cutout size for PSF fitting
DEFAULT_BETA = 4.0                 # Moffat beta (fixed, typical for astro)
DEFAULT_BLEND_RATIO_MAX = 2.0      # max alpha_x/alpha_y before rejection
DEFAULT_MIN_SNR = 3.0              # minimum SNR for a valid star fit

# Heatmap
DEFAULT_GRID_SIZE = 300            # output heatmap resolution
DEFAULT_N_CONTOURS = 5             # number of contour levels

# Sigma clipping for background
SIGMA_CLIP_SIGMA = 3.0
SIGMA_CLIP_ITERS = 5

# Spatial outlier rejection
OUTLIER_K_NEIGHBORS = 6
OUTLIER_MAD_FACTOR = 3.0

# Corner stats region names
REGION_NAMES = ['TL', 'T', 'TR', 'L', 'C', 'R', 'BL', 'B', 'BR']


# ---------------------------------------------------------------------------
# FWHMMapAnalyzer
# ---------------------------------------------------------------------------

class FWHMMapAnalyzer:
    """
    Spatially-resolved FWHM analysis for astrophotography frames.

    Workflow:
      1. Detect stars across the full field
      2. Fit 2D Moffat PSF to each candidate
      3. Select up to 3 brightest valid stars per 7x7 grid cell
      4. Reject spatial outliers via local neighbor comparison
      5. Build smooth 300x300 FWHM heatmap (Nadaraya-Watson regression)
      6. Compute contour levels and 9-region corner statistics
    """

    def __init__(self):
        """Initialize the analyzer. No state is stored between calls."""
        if not HAS_NUMPY:
            raise RuntimeError("numpy is required for FWHMMapAnalyzer")

    # -----------------------------------------------------------------------
    # Main entry point
    # -----------------------------------------------------------------------

    def analyze(self, data_2d: np.ndarray,
                pixel_scale: Optional[float] = None) -> Dict[str, Any]:
        """
        Run full FWHM heatmap analysis on a 2D image array.

        Args:
            data_2d: 2D numpy array (float or int), already debayered/luminance.
            pixel_scale: Plate scale in arcsec/pixel. If None, fwhm_arcsec
                         will be 0.0 for all stars.

        Returns:
            dict with keys:
              - stars: list of dicts (x, y, fwhm, fwhm_arcsec, eccentricity,
                       flux, snr)
              - heatmap: 2D numpy array (grid_size x grid_size) interpolated
                         FWHM surface, or empty array if too few stars
              - contour_levels: list of float contour level values
              - stats: dict with median_fwhm, mean_fwhm, std_fwhm, min_fwhm,
                       max_fwhm, star_count, corner_stats
        """
        if data_2d.ndim != 2:
            raise ValueError(f"Expected 2D array, got shape {data_2d.shape}")

        h, w = data_2d.shape
        ps = pixel_scale if pixel_scale and pixel_scale > 0 else 0.0

        # Step 1: detect star candidates
        raw_stars = self.detect_stars(data_2d, threshold_sigma=DEFAULT_THRESHOLD_SIGMA)
        logger.info("FWHM map: %d raw star candidates detected", len(raw_stars))

        if len(raw_stars) == 0:
            return self._empty_result(data_2d.shape)

        # Step 2: fit Moffat PSF to each candidate
        fitted_stars = []
        for star in raw_stars:
            result = self.fit_moffat_2d(data_2d, star['x'], star['y'],
                                        box_size=DEFAULT_BOX_SIZE)
            if result is not None:
                result['fwhm_arcsec'] = result['fwhm'] * ps if ps > 0 else 0.0
                fitted_stars.append(result)

        logger.info("FWHM map: %d stars with valid Moffat fits", len(fitted_stars))

        if len(fitted_stars) < 3:
            return self._empty_result(data_2d.shape)

        # Step 3: grid selection — uniform spatial coverage
        selected = self._grid_select(fitted_stars, (h, w),
                                     n_cells=DEFAULT_GRID_CELLS,
                                     max_per_cell=DEFAULT_MAX_STARS_PER_CELL)
        logger.info("FWHM map: %d stars after grid selection", len(selected))

        if len(selected) < 3:
            return self._empty_result(data_2d.shape)

        # Step 4: spatial outlier rejection
        cleaned = self._reject_spatial_outliers(selected)
        logger.info("FWHM map: %d stars after spatial outlier rejection",
                    len(cleaned))

        if len(cleaned) < 3:
            return self._empty_result(data_2d.shape)

        # Step 5: build heatmap
        heatmap = self.build_heatmap(cleaned, (h, w),
                                     grid_size=DEFAULT_GRID_SIZE)

        # Step 6: contour levels
        contour_levels = self.compute_contours(heatmap, n_levels=DEFAULT_N_CONTOURS)

        # Step 7: corner stats
        corner_stats = self.get_corner_stats(cleaned, (h, w))

        # Aggregate stats
        fwhm_values = np.array([s['fwhm'] for s in cleaned])
        stats = {
            'median_fwhm': float(np.median(fwhm_values)),
            'mean_fwhm': float(np.mean(fwhm_values)),
            'std_fwhm': float(np.std(fwhm_values)),
            'min_fwhm': float(np.min(fwhm_values)),
            'max_fwhm': float(np.max(fwhm_values)),
            'star_count': len(cleaned),
            'corner_stats': corner_stats,
        }

        # Add arcsec stats if plate scale is available
        if ps > 0:
            stats['median_fwhm_arcsec'] = float(np.median(fwhm_values) * ps)
            stats['mean_fwhm_arcsec'] = float(np.mean(fwhm_values) * ps)

        # Build output star list (serializable dicts)
        star_dicts = []
        for s in cleaned:
            star_dicts.append({
                'x': s['x'],
                'y': s['y'],
                'fwhm': s['fwhm'],
                'fwhm_arcsec': s.get('fwhm_arcsec', 0.0),
                'eccentricity': s['eccentricity'],
                'flux': s['flux'],
                'snr': s['snr'],
            })

        return {
            'stars': star_dicts,
            'heatmap': heatmap,
            'contour_levels': contour_levels,
            'stats': stats,
        }

    # -----------------------------------------------------------------------
    # Star detection
    # -----------------------------------------------------------------------

    def detect_stars(self, data: np.ndarray,
                     threshold_sigma: float = DEFAULT_THRESHOLD_SIGMA
                     ) -> List[Dict[str, float]]:
        """
        Detect star candidates in the image.

        Uses photutils DAOStarFinder if available, otherwise falls back to
        scipy.ndimage peak detection. Applies 2x subsampling for better
        centroid accuracy on undersampled data.

        Args:
            data: 2D image array (float or int).
            threshold_sigma: Detection threshold in units of background sigma.

        Returns:
            List of dicts with keys: x, y, flux, peak.
            Coordinates are in the original (non-subsampled) pixel frame.
        """
        h, w = data.shape

        # Background estimation: sigma-clipped median
        background, bg_std = self._estimate_background(data)

        threshold = bg_std * threshold_sigma

        if threshold <= 0:
            logger.warning("Background noise is zero — cannot detect stars")
            return []

        # Try photutils first
        if HAS_PHOTUTILS:
            return self._detect_stars_photutils(data, background, bg_std,
                                                threshold_sigma)

        # Fallback to scipy peak detection
        if HAS_SCIPY:
            return self._detect_stars_scipy(data, background, threshold)

        logger.error("Neither photutils nor scipy available — "
                     "cannot detect stars")
        return []

    def _detect_stars_photutils(self, data: np.ndarray,
                                background: float, bg_std: float,
                                threshold_sigma: float
                                ) -> List[Dict[str, float]]:
        """Star detection using photutils DAOStarFinder."""
        h, w = data.shape
        edge = DEFAULT_EDGE_MARGIN

        # 2x upsample for better centroid accuracy on undersampled data
        try:
            from scipy.ndimage import zoom as ndimage_zoom
            data_2x = ndimage_zoom(data, 2.0, order=3)
            scale_factor = 2.0
        except (ImportError, MemoryError):
            data_2x = data
            scale_factor = 1.0

        bg_2x = background  # scalar — no rescaling needed
        std_2x = bg_std

        # DAOStarFinder expects FWHM estimate — use 3.0 pixels as default
        # (scaled by subsample factor)
        fwhm_estimate = 3.0 * scale_factor

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            finder = DAOStarFinder(
                fwhm=fwhm_estimate,
                threshold=threshold_sigma * std_2x,
                sharplo=0.2,
                sharphi=1.0,
                roundlo=-1.0,
                roundhi=1.0,
                peakmax=None,
            )
            sources = finder(data_2x - bg_2x)

        if sources is None or len(sources) == 0:
            return []

        stars = []
        for row in sources:
            # Convert back to original pixel coordinates
            x = float(row['xcentroid']) / scale_factor
            y = float(row['ycentroid']) / scale_factor
            flux = float(row['flux'])
            peak = float(row['peak'])

            # Edge exclusion
            if x < edge or x >= w - edge or y < edge or y >= h - edge:
                continue

            stars.append({
                'x': x,
                'y': y,
                'flux': flux,
                'peak': peak,
            })

        # Sort by flux descending
        stars.sort(key=lambda s: s['flux'], reverse=True)
        return stars

    def _detect_stars_scipy(self, data: np.ndarray,
                            background: float, threshold: float
                            ) -> List[Dict[str, float]]:
        """Fallback star detection using scipy.ndimage local maxima."""
        h, w = data.shape
        edge = DEFAULT_EDGE_MARGIN

        # 2x upsample for better centroid accuracy
        try:
            data_2x = ndimage.zoom(data, 2.0, order=3)
            scale_factor = 2.0
        except MemoryError:
            data_2x = data
            scale_factor = 1.0

        bg_sub = data_2x - background
        threshold_2x = threshold  # same sigma level

        # Local maximum detection
        neighborhood_size = 2 * int(DEFAULT_PEAK_SEP * scale_factor) + 1
        local_max = ndimage.maximum_filter(bg_sub, size=neighborhood_size)
        is_peak = (bg_sub == local_max) & (bg_sub > threshold_2x)

        # Edge exclusion (in 2x space)
        edge_2x = int(edge * scale_factor)
        h2, w2 = data_2x.shape
        if 2 * edge_2x < min(h2, w2):
            edge_mask = np.zeros((h2, w2), dtype=bool)
            edge_mask[edge_2x:h2 - edge_2x, edge_2x:w2 - edge_2x] = True
            is_peak = is_peak & edge_mask

        rows, cols = np.where(is_peak)
        if len(rows) == 0:
            return []

        # Compute flux in 5x5 aperture (in 2x space)
        aperture_r = int(2 * scale_factor)
        stars = []
        for r, c in zip(rows, cols):
            y0 = max(0, r - aperture_r)
            y1 = min(h2, r + aperture_r + 1)
            x0 = max(0, c - aperture_r)
            x1 = min(w2, c + aperture_r + 1)
            cutout = bg_sub[y0:y1, x0:x1]
            flux = float(np.sum(cutout[cutout > 0]))
            peak = float(bg_sub[r, c])

            # Convert back to original coordinates
            orig_x = c / scale_factor
            orig_y = r / scale_factor

            stars.append({
                'x': orig_x,
                'y': orig_y,
                'flux': flux,
                'peak': peak,
            })

        # Sort by flux descending
        stars.sort(key=lambda s: s['flux'], reverse=True)
        return stars

    # -----------------------------------------------------------------------
    # Background estimation
    # -----------------------------------------------------------------------

    def _estimate_background(self, data: np.ndarray
                             ) -> Tuple[float, float]:
        """
        Estimate global background level and noise via sigma-clipped median.

        Uses iterative sigma clipping (3-sigma, 5 iterations) on the full
        image (flattened). Returns (background_median, background_std).
        """
        flat = data.ravel().astype(np.float64)

        # Downsample if very large (>10M pixels) for speed
        if flat.size > 10_000_000:
            rng = np.random.default_rng(42)
            indices = rng.choice(flat.size, size=10_000_000, replace=False)
            flat = flat[indices]

        clipped = flat.copy()
        for _ in range(SIGMA_CLIP_ITERS):
            if len(clipped) < 100:
                break
            med = np.median(clipped)
            mad = np.median(np.abs(clipped - med))
            sigma_est = mad * 1.4826  # MAD to sigma conversion
            if sigma_est <= 0:
                break
            lo = med - SIGMA_CLIP_SIGMA * sigma_est
            hi = med + SIGMA_CLIP_SIGMA * sigma_est
            mask = (clipped >= lo) & (clipped <= hi)
            if mask.sum() < 100:
                break
            clipped = clipped[mask]

        bg_median = float(np.median(clipped)) if len(clipped) > 0 else 0.0
        mad_val = float(np.median(np.abs(clipped - bg_median))) if len(clipped) > 0 else 0.0
        bg_std = mad_val * 1.4826

        return bg_median, bg_std

    # -----------------------------------------------------------------------
    # Moffat 2D fitting
    # -----------------------------------------------------------------------

    def fit_moffat_2d(self, data: np.ndarray,
                      x0: float, y0: float,
                      box_size: int = DEFAULT_BOX_SIZE
                      ) -> Optional[Dict[str, float]]:
        """
        Fit a 2D elliptical Moffat profile to a star at (x0, y0).

        The Moffat profile has 7 parameters:
          amplitude, x_center, y_center, alpha_x, alpha_y, beta, theta

        Beta is fixed at 4.0 (typical for well-sampled astronomical images).

        Args:
            data: Full 2D image array.
            x0: Star x-coordinate (column, can be fractional).
            y0: Star y-coordinate (row, can be fractional).
            box_size: Size of the fitting cutout (odd number recommended).

        Returns:
            dict with keys: x, y, fwhm, eccentricity, beta, flux, snr
            or None if the fit fails or is rejected.
        """
        if not HAS_SCIPY:
            logger.debug("scipy not available — cannot fit Moffat PSF")
            return None

        h, w = data.shape
        half = box_size // 2
        ix0 = int(round(x0))
        iy0 = int(round(y0))

        # Bounds check — reject stars too close to edges
        if (iy0 - half < 0 or iy0 + half + 1 > h or
                ix0 - half < 0 or ix0 + half + 1 > w):
            return None

        cutout = data[iy0 - half:iy0 + half + 1,
                      ix0 - half:ix0 + half + 1].copy().astype(np.float64)

        size = cutout.shape[0]

        # Local background from cutout border (2-pixel ring)
        border_mask = np.ones_like(cutout, dtype=bool)
        if size > 6:
            border_mask[2:-2, 2:-2] = False
        bg_local = float(np.median(cutout[border_mask]))
        cutout_sub = cutout - bg_local

        # Noise estimate from border
        border_values = cutout[border_mask]
        noise = float(np.median(np.abs(border_values - np.median(border_values)))) * 1.4826
        noise = max(noise, 1e-10)

        # Peak amplitude and centroid refinement from cutout
        peak_amp = float(np.max(cutout_sub))
        if peak_amp <= 0:
            return None

        # Centroid via intensity-weighted center of mass
        yy, xx = np.mgrid[0:size, 0:size]
        positive = np.maximum(cutout_sub, 0)
        total_flux = float(np.sum(positive))
        if total_flux <= 0:
            return None

        cx = float(np.sum(xx * positive)) / total_flux
        cy = float(np.sum(yy * positive)) / total_flux

        # Initial parameter estimates
        # Parameters: amplitude, x_center, y_center, alpha_x, alpha_y, theta
        # Beta is fixed at DEFAULT_BETA
        alpha_init = 1.5  # ~ FWHM/2 for beta=4
        p0 = [peak_amp, cx, cy, alpha_init, alpha_init, 0.0]

        # Parameter bounds
        # amplitude: [0, 2*peak], center: [0, size], alpha: [0.3, size/2],
        # theta: [-pi, pi]
        lower = [0.0, 0.0, 0.0, 0.3, 0.3, -math.pi]
        upper = [peak_amp * 3.0, float(size), float(size),
                 float(size) / 2.0, float(size) / 2.0, math.pi]

        # Build coordinate grid
        yg, xg = np.mgrid[0:size, 0:size]
        xy = (xg.ravel().astype(np.float64), yg.ravel().astype(np.float64))

        beta = DEFAULT_BETA

        def moffat_fixed_beta(xy_pair, amp, xc, yc, ax, ay, theta):
            """2D elliptical Moffat with fixed beta."""
            x_arr, y_arr = xy_pair
            cos_t = math.cos(theta)
            sin_t = math.sin(theta)
            dx = x_arr - xc
            dy = y_arr - yc
            xr = cos_t * dx + sin_t * dy
            yr = -sin_t * dx + cos_t * dy
            ax_safe = max(ax, 1e-6)
            ay_safe = max(ay, 1e-6)
            r_sq = (xr / ax_safe) ** 2 + (yr / ay_safe) ** 2
            return amp * (1.0 + r_sq) ** (-beta)

        # Fit
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                popt, pcov = optimize.curve_fit(
                    moffat_fixed_beta, xy, cutout_sub.ravel(),
                    p0=p0, bounds=(lower, upper),
                    maxfev=2000, method='trf',
                )
        except (RuntimeError, ValueError, optimize.OptimizeWarning):
            return None

        amp_fit, xc_fit, yc_fit, alpha_x, alpha_y, theta_fit = popt

        # Validate: reject if center drifted too far from cutout center
        center = size / 2.0
        if abs(xc_fit - center) > size * 0.35 or abs(yc_fit - center) > size * 0.35:
            return None

        # Reject blends: elongation ratio > max
        alpha_max = max(alpha_x, alpha_y)
        alpha_min = min(alpha_x, alpha_y)
        if alpha_min < 1e-6:
            return None
        blend_ratio = alpha_max / alpha_min
        if blend_ratio > DEFAULT_BLEND_RATIO_MAX:
            return None

        # Compute FWHM from alpha: fwhm = 2 * alpha * sqrt(2^(1/beta) - 1)
        fwhm_factor = 2.0 * math.sqrt(2.0 ** (1.0 / beta) - 1.0)
        fwhm_x = alpha_x * fwhm_factor
        fwhm_y = alpha_y * fwhm_factor
        fwhm = math.sqrt(fwhm_x * fwhm_y)  # geometric mean

        # Eccentricity from alpha ratio
        if alpha_max > 0:
            ratio = alpha_min / alpha_max
            eccentricity = math.sqrt(1.0 - ratio ** 2)
        else:
            eccentricity = 0.0

        # Flux: integrate the fitted profile analytically
        # For Moffat: total_flux = pi * amp * alpha_x * alpha_y / (beta - 1)
        if beta > 1.0:
            flux = math.pi * amp_fit * alpha_x * alpha_y / (beta - 1.0)
        else:
            flux = total_flux  # fallback to aperture flux

        # SNR: peak amplitude / noise
        snr = amp_fit / noise

        # Reject low SNR
        if snr < DEFAULT_MIN_SNR:
            return None

        # Reject unphysical FWHM (too small or too large)
        if fwhm < 0.5 or fwhm > box_size * 0.8:
            return None

        # Convert cutout-local coordinates back to image coordinates
        star_x = float(ix0 - half + xc_fit)
        star_y = float(iy0 - half + yc_fit)

        return {
            'x': star_x,
            'y': star_y,
            'fwhm': float(fwhm),
            'fwhm_x': float(fwhm_x),
            'fwhm_y': float(fwhm_y),
            'eccentricity': float(eccentricity),
            'beta': float(beta),
            'flux': float(flux),
            'snr': float(snr),
            'theta': float(theta_fit),
        }

    # -----------------------------------------------------------------------
    # Grid selection for uniform spatial coverage
    # -----------------------------------------------------------------------

    def _grid_select(self, stars: List[Dict[str, float]],
                     shape: Tuple[int, int],
                     n_cells: int = DEFAULT_GRID_CELLS,
                     max_per_cell: int = DEFAULT_MAX_STARS_PER_CELL
                     ) -> List[Dict[str, float]]:
        """
        Select up to max_per_cell brightest valid stars per grid cell.

        Divides the image into n_cells x n_cells cells and picks the
        brightest stars from each, ensuring even spatial coverage.

        Args:
            stars: List of fitted star dicts (must have x, y, flux keys).
            shape: Image (height, width).
            n_cells: Number of grid divisions per axis.
            max_per_cell: Maximum stars to keep per cell.

        Returns:
            Filtered list of star dicts.
        """
        h, w = shape
        cell_h = h / n_cells
        cell_w = w / n_cells

        # Group stars into grid cells
        cells: Dict[Tuple[int, int], List[Dict]] = {}
        for star in stars:
            ci = min(int(star['x'] / cell_w), n_cells - 1)
            cj = min(int(star['y'] / cell_h), n_cells - 1)
            key = (ci, cj)
            if key not in cells:
                cells[key] = []
            cells[key].append(star)

        # Select brightest per cell
        selected = []
        for key in cells:
            cell_stars = sorted(cells[key], key=lambda s: s['flux'],
                                reverse=True)
            selected.extend(cell_stars[:max_per_cell])

        return selected

    # -----------------------------------------------------------------------
    # Spatial outlier rejection
    # -----------------------------------------------------------------------

    def _reject_spatial_outliers(self, stars: List[Dict[str, float]]
                                 ) -> List[Dict[str, float]]:
        """
        Reject stars whose FWHM deviates significantly from local neighbors.

        Uses a cKDTree to find k nearest neighbors for each star, then
        rejects if the star's FWHM deviates by more than 3*MAD from the
        local median.

        Args:
            stars: List of fitted star dicts.

        Returns:
            Filtered list with outliers removed.
        """
        if not HAS_SCIPY:
            # Without scipy, skip spatial rejection
            return stars

        n = len(stars)
        if n < OUTLIER_K_NEIGHBORS + 1:
            # Too few stars for meaningful spatial outlier rejection
            return stars

        # Build coordinate array and FWHM array
        coords = np.array([[s['x'], s['y']] for s in stars])
        fwhm_arr = np.array([s['fwhm'] for s in stars])

        # Build KD-tree
        tree = cKDTree(coords)

        # Query k+1 neighbors (includes self)
        k = min(OUTLIER_K_NEIGHBORS, n - 1)
        distances, indices = tree.query(coords, k=k + 1)

        keep = []
        for i in range(n):
            # Neighbor indices (exclude self — index 0 is always self)
            neighbor_idx = indices[i, 1:k + 1]
            neighbor_fwhm = fwhm_arr[neighbor_idx]

            local_median = float(np.median(neighbor_fwhm))
            local_mad = float(np.median(np.abs(neighbor_fwhm - local_median)))

            # MAD to sigma
            local_sigma = local_mad * 1.4826
            if local_sigma < 1e-6:
                # All neighbors have near-identical FWHM — keep star if close
                local_sigma = 0.1 * local_median if local_median > 0 else 1.0

            deviation = abs(fwhm_arr[i] - local_median)
            if deviation <= OUTLIER_MAD_FACTOR * local_sigma:
                keep.append(stars[i])

        return keep

    # -----------------------------------------------------------------------
    # Heatmap: Nadaraya-Watson kernel regression
    # -----------------------------------------------------------------------

    def build_heatmap(self, stars: List[Dict[str, float]],
                      shape: Tuple[int, int],
                      grid_size: int = DEFAULT_GRID_SIZE
                      ) -> np.ndarray:
        """
        Build a smooth FWHM heatmap using Nadaraya-Watson kernel regression
        with a Gaussian kernel and adaptive bandwidth.

        The bandwidth is set to 2x the median nearest-neighbor distance
        among the input stars, ensuring smooth interpolation while
        preserving spatial trends.

        Args:
            stars: List of star dicts (must have x, y, fwhm keys).
            shape: Original image (height, width).
            grid_size: Output heatmap resolution (grid_size x grid_size).

        Returns:
            2D numpy array of shape (grid_size, grid_size) with interpolated
            FWHM values. If computation fails, returns zeros.
        """
        n = len(stars)
        if n < 3:
            return np.zeros((grid_size, grid_size), dtype=np.float64)

        h, w = shape

        # Star positions and FWHM values
        sx = np.array([s['x'] for s in stars], dtype=np.float64)
        sy = np.array([s['y'] for s in stars], dtype=np.float64)
        sf = np.array([s['fwhm'] for s in stars], dtype=np.float64)

        # Compute adaptive bandwidth: 2 * median nearest-neighbor distance
        if HAS_SCIPY and n >= 2:
            coords = np.column_stack([sx, sy])
            tree = cKDTree(coords)
            # Query 2 nearest (self + 1 neighbor)
            dists, _ = tree.query(coords, k=2)
            nn_distances = dists[:, 1]  # nearest neighbor distances
            bandwidth = float(np.median(nn_distances)) * 2.0
        else:
            # Fallback: estimate bandwidth from image size and star count
            avg_spacing = math.sqrt(h * w / max(n, 1))
            bandwidth = avg_spacing * 1.5

        # Ensure minimum bandwidth
        min_bw = max(h, w) / (grid_size * 0.5)
        bandwidth = max(bandwidth, min_bw)

        # Build output grid coordinates (center of each heatmap pixel)
        gx = np.linspace(0, w, grid_size, endpoint=False) + w / (2.0 * grid_size)
        gy = np.linspace(0, h, grid_size, endpoint=False) + h / (2.0 * grid_size)
        grid_xx, grid_yy = np.meshgrid(gx, gy)

        # Flatten grid for vectorized computation
        gx_flat = grid_xx.ravel()
        gy_flat = grid_yy.ravel()
        n_grid = len(gx_flat)

        # Nadaraya-Watson: heatmap[j] = sum(w_i * fwhm_i) / sum(w_i)
        # where w_i = exp(-d_i^2 / (2 * h^2))
        # Process in chunks to limit memory usage
        heatmap_flat = np.zeros(n_grid, dtype=np.float64)
        h_sq_2 = 2.0 * bandwidth * bandwidth

        # Chunk size chosen to limit memory to ~200 MB for star arrays
        # Each chunk needs n_stars * chunk_size * 8 bytes for distance matrix
        max_chunk = max(1, min(n_grid, int(200_000_000 / (n * 8))))

        for start in range(0, n_grid, max_chunk):
            end = min(start + max_chunk, n_grid)
            chunk_gx = gx_flat[start:end]
            chunk_gy = gy_flat[start:end]

            # Distance squared from each grid point to each star
            # Shape: (chunk_size, n_stars)
            dx = chunk_gx[:, np.newaxis] - sx[np.newaxis, :]
            dy = chunk_gy[:, np.newaxis] - sy[np.newaxis, :]
            dist_sq = dx * dx + dy * dy

            # Gaussian kernel weights
            weights = np.exp(-dist_sq / h_sq_2)

            # Weighted average
            w_sum = np.sum(weights, axis=1)
            f_sum = np.sum(weights * sf[np.newaxis, :], axis=1)

            # Avoid division by zero
            valid = w_sum > 1e-30
            heatmap_flat[start:end] = np.where(valid, f_sum / w_sum, 0.0)

        heatmap = heatmap_flat.reshape((grid_size, grid_size))

        # Fill any remaining zeros with global median
        global_median = float(np.median(sf))
        zero_mask = heatmap < 1e-10
        if np.any(zero_mask):
            heatmap[zero_mask] = global_median

        return heatmap

    # -----------------------------------------------------------------------
    # Contour levels
    # -----------------------------------------------------------------------

    def compute_contours(self, heatmap: np.ndarray,
                         n_levels: int = DEFAULT_N_CONTOURS
                         ) -> List[float]:
        """
        Compute contour level values for the FWHM heatmap.

        Uses matplotlib's contour algorithm if available, otherwise falls
        back to evenly-spaced percentiles of the heatmap values.

        Args:
            heatmap: 2D FWHM heatmap array.
            n_levels: Number of contour levels to compute.

        Returns:
            Sorted list of float values for contour lines.
        """
        if heatmap.size == 0 or np.all(heatmap < 1e-10):
            return []

        valid = heatmap[heatmap > 1e-10]
        if len(valid) < 2:
            return []

        vmin = float(np.min(valid))
        vmax = float(np.max(valid))

        if vmax - vmin < 1e-6:
            return [float(vmin)]

        if HAS_MATPLOTLIB:
            # Use matplotlib's contour to get well-distributed levels
            try:
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots()
                levels = np.linspace(vmin, vmax, n_levels + 2)[1:-1]
                cs = ax.contour(heatmap, levels=levels)
                result = sorted([float(lv) for lv in cs.levels])
                plt.close(fig)
                return result
            except Exception:
                plt.close('all')
                # Fall through to numpy fallback

        # Numpy fallback: evenly spaced between min and max
        levels = np.linspace(vmin, vmax, n_levels + 2)[1:-1]
        return sorted([float(lv) for lv in levels])

    # -----------------------------------------------------------------------
    # Corner stats (9-region analysis)
    # -----------------------------------------------------------------------

    def get_corner_stats(self, stars: List[Dict[str, float]],
                         shape: Tuple[int, int]
                         ) -> Dict[str, Dict[str, Any]]:
        """
        Compute FWHM statistics for 9 image regions (3x3 grid).

        Regions are named:
          TL  T   TR
          L   C   R
          BL  B   BR

        For each region, computes: median_fwhm, min_fwhm, max_fwhm,
        star_count. Empty regions get None values.

        Args:
            stars: List of star dicts with x, y, fwhm keys.
            shape: Image (height, width).

        Returns:
            Dict keyed by region name (TL, T, TR, ..., BR), each containing
            a dict of statistics.
        """
        h, w = shape
        row_h = h / 3.0
        col_w = w / 3.0

        # Map region grid indices to names
        # (col_idx, row_idx) → name
        grid_to_name = {
            (0, 0): 'TL', (1, 0): 'T',  (2, 0): 'TR',
            (0, 1): 'L',  (1, 1): 'C',  (2, 1): 'R',
            (0, 2): 'BL', (1, 2): 'B',  (2, 2): 'BR',
        }

        # Collect stars per region
        regions: Dict[str, List[float]] = {name: [] for name in REGION_NAMES}

        for star in stars:
            ci = min(int(star['x'] / col_w), 2)
            ri = min(int(star['y'] / row_h), 2)
            name = grid_to_name.get((ci, ri))
            if name:
                regions[name].append(star['fwhm'])

        # Compute stats per region
        result = {}
        for name in REGION_NAMES:
            fwhm_list = regions[name]
            if len(fwhm_list) == 0:
                result[name] = {
                    'median_fwhm': None,
                    'min_fwhm': None,
                    'max_fwhm': None,
                    'star_count': 0,
                }
            else:
                arr = np.array(fwhm_list)
                result[name] = {
                    'median_fwhm': float(np.median(arr)),
                    'min_fwhm': float(np.min(arr)),
                    'max_fwhm': float(np.max(arr)),
                    'star_count': len(fwhm_list),
                }

        return result

    # -----------------------------------------------------------------------
    # Empty result helper
    # -----------------------------------------------------------------------

    def _empty_result(self, shape: Tuple[int, int]) -> Dict[str, Any]:
        """Return an empty analysis result when too few stars are found."""
        return {
            'stars': [],
            'heatmap': np.zeros((DEFAULT_GRID_SIZE, DEFAULT_GRID_SIZE),
                                dtype=np.float64),
            'contour_levels': [],
            'stats': {
                'median_fwhm': 0.0,
                'mean_fwhm': 0.0,
                'std_fwhm': 0.0,
                'min_fwhm': 0.0,
                'max_fwhm': 0.0,
                'star_count': 0,
                'corner_stats': self.get_corner_stats([], shape),
            },
        }
