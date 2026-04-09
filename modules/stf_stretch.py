#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - STF AUTOSTRETCH MODULE
================================================================================
PixInsight-style Screen Transfer Function (STF) autostretch for astrophotography
image previews.  Applies a non-linear Midtones Transfer Function (MTF) to map
the narrow dynamic range of a linear astro frame into a visually appealing
uint8 display image.

Algorithm (mirrors PixInsight's STF):
  1. Clip extreme outliers (percentile 0.05% / 99.95%)
  2. Normalize to [0, 1]
  3. Compute median and MAD (Median Absolute Deviation)
  4. Shadow clipping at  median - shadow_clip_mad * MAD
  5. Solve midtone transfer value so that the median maps to target_median
  6. Apply the MTF:  f(x, m) = (m-1)*x / ((2m-1)*x - m)
  7. Scale to uint8

Pure logic module — no GUI code.  Uses only numpy.
================================================================================
"""

import logging
from typing import Dict, Optional

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SHADOW_CLIP_MAD = 2.8      # PixInsight default: clip shadows at median - 2.8*MAD
DEFAULT_TARGET_MEDIAN = 0.25       # Target brightness for the median after stretch
CLIP_LOW_PERCENTILE = 0.05         # Bottom percentile for outlier rejection
CLIP_HIGH_PERCENTILE = 99.95       # Top percentile for outlier rejection


class STFAutostretch:
    """PixInsight-style Screen Transfer Function autostretch."""

    # ------------------------------------------------------------------
    # Midtones Transfer Function
    # ------------------------------------------------------------------

    @staticmethod
    def mtf_function(x, m):
        """
        Midtones Transfer Function (PixInsight formula).

        MTF(x, m) = (m - 1) * x / ((2*m - 1) * x - m)

        Parameters
        ----------
        x : float or ndarray
            Input value(s) in [0, 1].
        m : float
            Midtone balance parameter in (0, 1).  Lower values brighten
            the image more aggressively.

        Returns
        -------
        float or ndarray
            Stretched value(s) in [0, 1].
        """
        if not HAS_NUMPY:
            raise ImportError("numpy is required for STF autostretch")

        x = np.asarray(x, dtype=np.float64)
        m = float(m)

        # Edge cases: m == 0 or m == 1 degenerate the function
        if m <= 0.0 or m >= 1.0:
            return np.clip(x, 0.0, 1.0)

        numerator = (m - 1.0) * x
        denominator = (2.0 * m - 1.0) * x - m

        # Avoid division by zero (denominator == 0 when x == m / (2m - 1))
        with np.errstate(divide="ignore", invalid="ignore"):
            result = np.where(
                np.abs(denominator) < 1e-15,
                0.5,  # At the singularity, MTF approaches 0.5
                numerator / denominator,
            )

        return np.clip(result, 0.0, 1.0)

    # ------------------------------------------------------------------
    # STF parameter computation
    # ------------------------------------------------------------------

    @staticmethod
    def compute_stf_params(
        data,
        shadow_clip_mad: float = DEFAULT_SHADOW_CLIP_MAD,
        target_median: float = DEFAULT_TARGET_MEDIAN,
    ) -> Dict[str, float]:
        """
        Compute STF stretch parameters from image data.

        Parameters
        ----------
        data : ndarray
            2-D image array (any dtype).
        shadow_clip_mad : float
            Number of MADs below the median for shadow clipping.
        target_median : float
            Desired median brightness after stretch (0-1).

        Returns
        -------
        dict
            Keys: shadow, midtone, highlight, median_norm, mad_norm.
        """
        if not HAS_NUMPY:
            raise ImportError("numpy is required for STF autostretch")

        data = np.asarray(data, dtype=np.float64).ravel()

        # Remove NaN / Inf
        data = data[np.isfinite(data)]

        if data.size == 0:
            logger.warning("STF: empty or all-NaN data — returning neutral params")
            return {"shadow": 0.0, "midtone": 0.5, "highlight": 1.0,
                    "median_norm": 0.0, "mad_norm": 0.0}

        # Constant image (all same value)
        dmin, dmax = float(np.min(data)), float(np.max(data))
        if dmax - dmin < 1e-15:
            logger.warning("STF: constant image — returning neutral params")
            return {"shadow": 0.0, "midtone": 0.5, "highlight": 1.0,
                    "median_norm": 0.0, "mad_norm": 0.0}

        # Step 1 — Clip extreme outliers
        lo = np.percentile(data, CLIP_LOW_PERCENTILE)
        hi = np.percentile(data, CLIP_HIGH_PERCENTILE)
        data_clipped = np.clip(data, lo, hi)

        # Step 2 — Normalize to [0, 1]
        clip_range = hi - lo
        if clip_range < 1e-15:
            # Degenerate after clipping
            return {"shadow": 0.0, "midtone": 0.5, "highlight": 1.0,
                    "median_norm": 0.0, "mad_norm": 0.0}
        data_norm = (data_clipped - lo) / clip_range

        # Step 3 — Median of normalized data
        med = float(np.median(data_norm))

        # Step 4 — MAD (Median Absolute Deviation)
        mad = float(np.median(np.abs(data_norm - med)))

        # Step 5 — Shadow clipping point
        shadow = max(0.0, med - shadow_clip_mad * mad)

        # Highlight is always 1.0 for autostretch
        highlight = 1.0

        # Step 6 — Solve for midtone balance
        # We want MTF((med - shadow) / (highlight - shadow), m) = target_median
        # Rearranging the MTF formula for m:
        #   m = MTF_inv(target_median, x_norm)
        #   where x_norm = (med - shadow) / (highlight - shadow)
        x_norm = (med - shadow) / (highlight - shadow) if (highlight - shadow) > 1e-15 else 0.0

        if x_norm <= 0.0 or x_norm >= 1.0:
            midtone = 0.5
        else:
            # Inverse solve:  target = (m-1)*x / ((2m-1)*x - m)
            # Rearranging for m:
            #   m = (target * x - x) / (2*target*x - target - x)
            t = target_median
            midtone = (t * x_norm - x_norm) / (2.0 * t * x_norm - t - x_norm)
            midtone = max(0.001, min(0.999, midtone))

        return {
            "shadow": shadow,
            "midtone": midtone,
            "highlight": highlight,
            "median_norm": med,
            "mad_norm": mad,
        }

    # ------------------------------------------------------------------
    # Full autostretch pipeline
    # ------------------------------------------------------------------

    def stf_autostretch(
        self,
        data,
        shadow_clip_mad: float = DEFAULT_SHADOW_CLIP_MAD,
        target_median: float = DEFAULT_TARGET_MEDIAN,
    ) -> "np.ndarray":
        """
        Apply PixInsight-style STF autostretch and return a uint8 image.

        Parameters
        ----------
        data : ndarray
            2-D image array (any numeric dtype).
        shadow_clip_mad : float
            Number of MADs below the median for shadow clipping (default 2.8).
        target_median : float
            Desired median brightness after stretch, 0-1 (default 0.25).

        Returns
        -------
        ndarray
            Stretched image as uint8 (0-255), same shape as input.
        """
        if not HAS_NUMPY:
            raise ImportError("numpy is required for STF autostretch")

        data = np.asarray(data, dtype=np.float64)
        original_shape = data.shape

        # Handle all-zero / constant / empty gracefully
        if data.size == 0:
            return np.zeros(original_shape, dtype=np.uint8)

        # Replace NaN/Inf with 0
        mask_bad = ~np.isfinite(data)
        if np.any(mask_bad):
            data = data.copy()
            data[mask_bad] = 0.0

        # Compute stretch parameters
        params = self.compute_stf_params(data, shadow_clip_mad, target_median)
        shadow = params["shadow"]
        midtone = params["midtone"]
        highlight = params["highlight"]

        # Normalize using the same clipping as compute_stf_params
        flat = data.ravel()
        lo = np.percentile(flat[np.isfinite(flat)], CLIP_LOW_PERCENTILE)
        hi = np.percentile(flat[np.isfinite(flat)], CLIP_HIGH_PERCENTILE)
        clip_range = hi - lo

        if clip_range < 1e-15:
            return np.zeros(original_shape, dtype=np.uint8)

        normalized = (np.clip(data, lo, hi) - lo) / clip_range

        # Apply shadow clipping: remap [shadow, highlight] → [0, 1]
        span = highlight - shadow
        if span < 1e-15:
            return np.zeros(original_shape, dtype=np.uint8)

        rescaled = np.clip((normalized - shadow) / span, 0.0, 1.0)

        # Apply MTF
        stretched = self.mtf_function(rescaled, midtone)

        # Convert to uint8
        result = np.clip(stretched * 255.0 + 0.5, 0, 255).astype(np.uint8)

        return result
