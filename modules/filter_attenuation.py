#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - FILTER ATTENUATION ANALYSIS MODULE
================================================================================
Quantitative comparison of signal attenuation between two images taken through
different optical paths (e.g. with and without a filter, or two different
filters).  Inspired by AstroCrossSections (Brent Mantooth).

Features:
  - Background subtraction (median-based)
  - Signal attenuation (percentage and magnitude)
  - Welch's t-test for statistical significance (scipy or manual fallback)
  - Cohen's d effect size
  - Photon-noise SNR model: SNR = signal / sqrt(signal + bg + readnoise^2)
  - Flux-ratio SNR model:   SNR = (signal - bg) / bg_std
  - Exposure factor estimation (how much longer filter 2 needs)
  - Full analysis pipeline combining all metrics

Pure logic module -- no GUI code.  Requires numpy; scipy.stats optional.
================================================================================
"""

import logging
import math
from typing import Any, Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency: scipy.stats for Welch's t-test
# ---------------------------------------------------------------------------
try:
    from scipy import stats as scipy_stats
    SCIPY_STATS_AVAILABLE = True
except ImportError:
    SCIPY_STATS_AVAILABLE = False
    logger.info("scipy.stats not available -- Welch t-test will use manual fallback")


# =============================================================================
# Helpers
# =============================================================================

def _safe_float(value: Any) -> float:
    """Convert *value* to a finite float; return 0.0 on NaN / Inf / None."""
    try:
        f = float(value)
        if math.isfinite(f):
            return f
    except (TypeError, ValueError):
        pass
    return 0.0


def _basic_stats(data: np.ndarray) -> Dict[str, float]:
    """Return basic descriptive statistics for a 1-D or 2-D array."""
    flat = np.asarray(data, dtype=np.float64).ravel()
    # Filter out NaN / Inf before computing stats
    flat = flat[np.isfinite(flat)]
    if flat.size == 0:
        return {"mean": 0.0, "median": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
    return {
        "mean": float(np.mean(flat)),
        "median": float(np.median(flat)),
        "std": float(np.std(flat, ddof=1)) if flat.size > 1 else 0.0,
        "min": float(np.min(flat)),
        "max": float(np.max(flat)),
    }


def _extract_region(data: np.ndarray, region: Tuple[int, int, int, int]) -> np.ndarray:
    """Extract a rectangular region from a 2-D array.

    Parameters
    ----------
    data : 2-D ndarray
    region : (x0, y0, x1, y1) bounding box (inclusive start, exclusive end).

    Returns
    -------
    2-D ndarray slice (copy).
    """
    x0, y0, x1, y1 = region
    # Clamp to array bounds
    y_max, x_max = data.shape[:2]
    x0 = max(0, min(x0, x_max))
    x1 = max(x0, min(x1, x_max))
    y0 = max(0, min(y0, y_max))
    y1 = max(y0, min(y1, y_max))
    return np.array(data[y0:y1, x0:x1], dtype=np.float64)


# =============================================================================
# Main analyser class
# =============================================================================

class FilterAttenuationAnalyzer:
    """Compare two images to quantify filter attenuation and SNR impact.

    Typical usage::

        analyzer = FilterAttenuationAnalyzer()
        results = analyzer.analyze(
            image1_data,                        # 2-D ndarray (reference / no-filter)
            image2_data,                        # 2-D ndarray (with filter)
            signal_region=(100, 100, 400, 400), # bounding box of the signal area
            background_region=(10, 10, 80, 80), # bounding box of a blank sky area
        )
    """

    # ------------------------------------------------------------------
    # Background subtraction
    # ------------------------------------------------------------------

    @staticmethod
    def subtract_background(
        data: np.ndarray,
        bg_region: Tuple[int, int, int, int],
    ) -> np.ndarray:
        """Subtract the median of *bg_region* from the entire image.

        Parameters
        ----------
        data : 2-D ndarray
            Full image data.
        bg_region : (x0, y0, x1, y1)
            Bounding box for the background sample.

        Returns
        -------
        2-D float64 ndarray with background level removed.
        """
        img = np.asarray(data, dtype=np.float64)
        bg_patch = _extract_region(img, bg_region)
        if bg_patch.size == 0:
            logger.warning("Background region is empty -- no subtraction applied")
            return img.copy()
        bg_median = float(np.nanmedian(bg_patch))
        logger.debug("Background median = %.4f", bg_median)
        return img - bg_median

    # ------------------------------------------------------------------
    # Attenuation (percentage + magnitude)
    # ------------------------------------------------------------------

    @staticmethod
    def compute_attenuation(
        signal1: np.ndarray,
        signal2: np.ndarray,
    ) -> Dict[str, float]:
        """Compute signal attenuation between two signal regions.

        Parameters
        ----------
        signal1 : ndarray  -- reference signal region (e.g. no filter).
        signal2 : ndarray  -- attenuated signal region (e.g. with filter).

        Returns
        -------
        dict with ``attenuation_pct`` and ``attenuation_mag``.
        """
        s1 = np.asarray(signal1, dtype=np.float64).ravel()
        s2 = np.asarray(signal2, dtype=np.float64).ravel()
        s1 = s1[np.isfinite(s1)]
        s2 = s2[np.isfinite(s2)]

        med1 = float(np.median(s1)) if s1.size > 0 else 0.0
        med2 = float(np.median(s2)) if s2.size > 0 else 0.0

        # Handle division by zero / non-positive reference
        if med1 <= 0.0 or med2 <= 0.0:
            logger.warning(
                "Non-positive median(s) in attenuation calc (med1=%.4f, med2=%.4f) "
                "-- returning 0 / NaN",
                med1, med2,
            )
            return {"attenuation_pct": 0.0, "attenuation_mag": 0.0}

        ratio = med2 / med1
        attenuation_pct = (1.0 - ratio) * 100.0
        # Magnitude difference: -2.5 * log10(flux_ratio)
        try:
            attenuation_mag = -2.5 * math.log10(ratio)
        except (ValueError, ZeroDivisionError):
            attenuation_mag = 0.0

        return {
            "attenuation_pct": _safe_float(attenuation_pct),
            "attenuation_mag": _safe_float(attenuation_mag),
        }

    # ------------------------------------------------------------------
    # Welch's t-test (with manual fallback)
    # ------------------------------------------------------------------

    @staticmethod
    def welch_t_test(
        signal1: np.ndarray,
        signal2: np.ndarray,
    ) -> Dict[str, Any]:
        """Welch's t-test (unequal-variance two-sample t-test).

        Uses ``scipy.stats.ttest_ind(equal_var=False)`` when available,
        otherwise falls back to a manual implementation.

        Returns
        -------
        dict with ``t_statistic``, ``p_value``, ``df``,
        ``significant`` (p < 0.05), ``effect_size_cohen_d``.
        """
        a = np.asarray(signal1, dtype=np.float64).ravel()
        b = np.asarray(signal2, dtype=np.float64).ravel()
        a = a[np.isfinite(a)]
        b = b[np.isfinite(b)]

        n1, n2 = a.size, b.size
        if n1 < 2 or n2 < 2:
            logger.warning("Insufficient samples for Welch t-test (n1=%d, n2=%d)", n1, n2)
            return {
                "t_statistic": 0.0,
                "p_value": 1.0,
                "df": 0.0,
                "significant": False,
                "effect_size_cohen_d": 0.0,
            }

        m1, m2 = float(np.mean(a)), float(np.mean(b))
        v1 = float(np.var(a, ddof=1))
        v2 = float(np.var(b, ddof=1))

        # --- Cohen's d (pooled) ---
        pooled_std = math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
        cohen_d = abs(m1 - m2) / pooled_std if pooled_std > 0.0 else 0.0

        # --- Welch t-test ---
        if SCIPY_STATS_AVAILABLE:
            t_stat, p_val = scipy_stats.ttest_ind(a, b, equal_var=False)
            # scipy returns Welch-Satterthwaite df internally; recompute for output
            se = v1 / n1 + v2 / n2
            if se > 0.0:
                df = (se ** 2) / (
                    (v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)
                )
            else:
                df = 0.0
        else:
            # Manual Welch's t-test
            se = v1 / n1 + v2 / n2
            if se <= 0.0:
                return {
                    "t_statistic": 0.0,
                    "p_value": 1.0,
                    "df": 0.0,
                    "significant": False,
                    "effect_size_cohen_d": _safe_float(cohen_d),
                }
            t_stat = (m1 - m2) / math.sqrt(se)
            # Welch-Satterthwaite degrees of freedom
            df = (se ** 2) / (
                (v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)
            )
            # Two-tailed p-value approximation (normal for large df)
            p_val = FilterAttenuationAnalyzer._approx_two_tailed_p(t_stat, df)

        return {
            "t_statistic": _safe_float(t_stat),
            "p_value": _safe_float(p_val),
            "df": _safe_float(df),
            "significant": bool(_safe_float(p_val) < 0.05),
            "effect_size_cohen_d": _safe_float(cohen_d),
        }

    @staticmethod
    def _approx_two_tailed_p(t: float, df: float) -> float:
        """Approximate two-tailed p-value for Student's t distribution.

        Uses the regularised incomplete beta function when scipy is absent.
        Falls back to a simple normal approximation for large df.
        """
        if df <= 0.0:
            return 1.0
        # For large df (> 200), the t distribution ≈ normal
        if df > 200:
            # Normal CDF via error function (stdlib math)
            z = abs(t)
            p = math.erfc(z / math.sqrt(2.0))
            return max(0.0, min(1.0, p))
        # Beta-function based exact formula:
        # p = I_{df/(df+t^2)}(df/2, 1/2)  --  needs regularised incomplete beta
        # Without scipy we use a cruder series approximation
        x = df / (df + t * t)
        # Continued fraction / series for regularised incomplete beta is complex;
        # use a practical lookup-style bound for moderate df.
        # This is a rough approximation; for production use scipy is recommended.
        try:
            # Attempt an integration-free approximation (Abramowitz & Stegun 26.7.5)
            a_val = df / 2.0
            b_val = 0.5
            # Stirling-based log-beta
            log_beta = (
                math.lgamma(a_val) + math.lgamma(b_val) - math.lgamma(a_val + b_val)
            )
            # Power-series first term
            term = (x ** a_val) * ((1.0 - x) ** b_val) / (a_val * math.exp(log_beta))
            # Accumulate a few terms of the series
            ibeta = term
            for k in range(1, 60):
                term *= (a_val + k - 1) * x * (a_val + b_val + k - 1)
                term /= ((a_val + k) * k)
                # Avoid exploding terms
                if abs(term) < 1e-15:
                    break
                ibeta += term
            p = max(0.0, min(1.0, ibeta))
            return p
        except (OverflowError, ValueError, ZeroDivisionError):
            # Ultimate fallback: treat as normal
            z = abs(t)
            return max(0.0, min(1.0, math.erfc(z / math.sqrt(2.0))))

    # ------------------------------------------------------------------
    # SNR -- photon noise model
    # ------------------------------------------------------------------

    @staticmethod
    def compute_snr_photon(
        signal_region_data: np.ndarray,
        bg_region_data: np.ndarray,
        readnoise: float = 0.0,
    ) -> Dict[str, float]:
        """Photon-noise SNR model.

        SNR = signal_mean / sqrt(signal_mean + bg_mean + readnoise^2)

        Parameters
        ----------
        signal_region_data : ndarray -- already background-subtracted signal region.
        bg_region_data : ndarray -- background region (before subtraction).
        readnoise : float -- detector read noise in ADU (default 0, conservative).

        Returns
        -------
        dict with ``snr``, ``signal_mean``, ``bg_mean``, ``noise``.
        """
        sig = np.asarray(signal_region_data, dtype=np.float64).ravel()
        bg = np.asarray(bg_region_data, dtype=np.float64).ravel()
        sig = sig[np.isfinite(sig)]
        bg = bg[np.isfinite(bg)]

        signal_mean = float(np.mean(sig)) if sig.size > 0 else 0.0
        bg_mean = float(np.mean(bg)) if bg.size > 0 else 0.0

        # Ensure non-negative under the square root
        variance = max(0.0, signal_mean) + max(0.0, bg_mean) + readnoise ** 2
        noise = math.sqrt(variance) if variance > 0.0 else 0.0
        snr = signal_mean / noise if noise > 0.0 else 0.0

        return {
            "snr": _safe_float(snr),
            "signal_mean": _safe_float(signal_mean),
            "bg_mean": _safe_float(bg_mean),
            "noise": _safe_float(noise),
        }

    # ------------------------------------------------------------------
    # SNR -- flux ratio model
    # ------------------------------------------------------------------

    @staticmethod
    def compute_snr_flux(
        signal_region_data: np.ndarray,
        bg_region_data: np.ndarray,
    ) -> Dict[str, float]:
        """Flux-ratio SNR model.

        SNR = (signal_mean - bg_mean) / bg_std

        Parameters
        ----------
        signal_region_data : ndarray -- signal region (raw, not background-subtracted).
        bg_region_data : ndarray -- background region.

        Returns
        -------
        dict with ``snr``, ``signal_mean``, ``bg_mean``, ``bg_std``.
        """
        sig = np.asarray(signal_region_data, dtype=np.float64).ravel()
        bg = np.asarray(bg_region_data, dtype=np.float64).ravel()
        sig = sig[np.isfinite(sig)]
        bg = bg[np.isfinite(bg)]

        signal_mean = float(np.mean(sig)) if sig.size > 0 else 0.0
        bg_mean = float(np.mean(bg)) if bg.size > 0 else 0.0
        bg_std = float(np.std(bg, ddof=1)) if bg.size > 1 else 0.0

        snr = (signal_mean - bg_mean) / bg_std if bg_std > 0.0 else 0.0

        return {
            "snr": _safe_float(snr),
            "signal_mean": _safe_float(signal_mean),
            "bg_mean": _safe_float(bg_mean),
            "bg_std": _safe_float(bg_std),
        }

    # ------------------------------------------------------------------
    # Exposure factor
    # ------------------------------------------------------------------

    @staticmethod
    def compute_exposure_factor(snr1: float, snr2: float) -> float:
        """Compute how much longer image 2 needs to match image 1's SNR.

        exposure_factor = (snr1 / snr2)^2

        A factor of 4.0 means "you need 4x the exposure time with filter 2
        to reach the same SNR as filter 1 / no filter."

        Returns 0.0 when *snr2* is zero or negative.
        """
        if snr2 <= 0.0:
            logger.warning("snr2 <= 0 -- cannot compute exposure factor")
            return 0.0
        if snr1 <= 0.0:
            return 0.0
        factor = (snr1 / snr2) ** 2
        return _safe_float(factor)

    # ------------------------------------------------------------------
    # Full analysis pipeline
    # ------------------------------------------------------------------

    def analyze(
        self,
        image1_data: np.ndarray,
        image2_data: np.ndarray,
        signal_region: Tuple[int, int, int, int],
        background_region: Tuple[int, int, int, int],
        readnoise: float = 0.0,
    ) -> Dict[str, Any]:
        """Run the complete attenuation analysis pipeline.

        Parameters
        ----------
        image1_data : 2-D ndarray -- reference image (e.g. no filter / filter A).
        image2_data : 2-D ndarray -- comparison image (e.g. with filter / filter B).
        signal_region : (x0, y0, x1, y1) bounding box for the signal area.
        background_region : (x0, y0, x1, y1) bounding box for the background area.
        readnoise : float -- detector read noise in ADU (default 0).

        Returns
        -------
        Comprehensive dict::

            {
                "image1_stats": {mean, median, std, min, max},
                "image2_stats": {mean, median, std, min, max},
                "attenuation": {attenuation_pct, attenuation_mag},
                "welch_test": {t_statistic, p_value, df, significant, effect_size_cohen_d},
                "snr_photon": {"image1": {...}, "image2": {...}},
                "snr_flux":   {"image1": {...}, "image2": {...}},
                "exposure_factor_photon": float,
                "exposure_factor_flux": float,
            }
        """
        img1 = np.asarray(image1_data, dtype=np.float64)
        img2 = np.asarray(image2_data, dtype=np.float64)

        # --- Background subtraction ---
        img1_bgsub = self.subtract_background(img1, background_region)
        img2_bgsub = self.subtract_background(img2, background_region)

        # --- Extract signal regions (from bg-subtracted images) ---
        sig1 = _extract_region(img1_bgsub, signal_region)
        sig2 = _extract_region(img2_bgsub, signal_region)

        # --- Extract raw regions for flux-ratio SNR (before bg subtraction) ---
        sig1_raw = _extract_region(img1, signal_region)
        sig2_raw = _extract_region(img2, signal_region)
        bg1_raw = _extract_region(img1, background_region)
        bg2_raw = _extract_region(img2, background_region)

        # --- Basic stats on signal regions (bg-subtracted) ---
        image1_stats = _basic_stats(sig1)
        image2_stats = _basic_stats(sig2)

        # --- Attenuation ---
        attenuation = self.compute_attenuation(sig1, sig2)

        # --- Welch t-test ---
        welch = self.welch_t_test(sig1, sig2)

        # --- SNR (photon noise model, uses bg-subtracted signal + raw bg) ---
        snr_phot1 = self.compute_snr_photon(sig1, bg1_raw, readnoise=readnoise)
        snr_phot2 = self.compute_snr_photon(sig2, bg2_raw, readnoise=readnoise)

        # --- SNR (flux ratio model, uses raw data) ---
        snr_flux1 = self.compute_snr_flux(sig1_raw, bg1_raw)
        snr_flux2 = self.compute_snr_flux(sig2_raw, bg2_raw)

        # --- Exposure factors ---
        exp_factor_phot = self.compute_exposure_factor(
            snr_phot1["snr"], snr_phot2["snr"]
        )
        exp_factor_flux = self.compute_exposure_factor(
            snr_flux1["snr"], snr_flux2["snr"]
        )

        return {
            "image1_stats": image1_stats,
            "image2_stats": image2_stats,
            "attenuation": attenuation,
            "welch_test": welch,
            "snr_photon": {"image1": snr_phot1, "image2": snr_phot2},
            "snr_flux": {"image1": snr_flux1, "image2": snr_flux2},
            "exposure_factor_photon": exp_factor_phot,
            "exposure_factor_flux": exp_factor_flux,
        }
