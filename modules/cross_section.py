#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - CROSS-SECTION LINE PROFILE ANALYSIS MODULE
================================================================================
Intensity cross-section / line profile analysis for astrophotography images.
Inspired by AstroCrossSections (Brent Mantooth).

Features:
  - Bilinear interpolation sampling along an arbitrary line
  - Channel modes: luminance (BT.709), red, green, blue, rgb (all 3)
  - Profile comparison with RMSE, MAE, Pearson correlation
  - Histogram computation with per-channel support and log scaling
  - Pure numpy implementation, no hard scipy dependency

Pure logic module — no GUI code.  Uses only numpy (scipy optional).
================================================================================
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

try:
    from scipy import interpolate as scipy_interp
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# BT.709 luminance weights (ITU-R Recommendation BT.709)
BT709_R = 0.2126
BT709_G = 0.7152
BT709_B = 0.0722

VALID_MODES = ("luminance", "red", "green", "blue", "rgb")


class CrossSectionAnalyzer:
    """Cross-section line profile analyzer for 2D/3D image arrays."""

    # ------------------------------------------------------------------
    # Bilinear interpolation
    # ------------------------------------------------------------------

    @staticmethod
    def bilinear_interpolate(data: np.ndarray, x: float, y: float) -> float:
        """Bilinear interpolation at fractional pixel coordinates.

        Parameters
        ----------
        data : np.ndarray
            2D array (H, W) of pixel values.
        x : float
            Horizontal coordinate (column), 0-based.
        y : float
            Vertical coordinate (row), 0-based.

        Returns
        -------
        float
            Interpolated value, boundary-clamped to image edges.
        """
        h, w = data.shape[:2]

        # Clamp to valid range (edges inclusive)
        x = max(0.0, min(x, w - 1.0))
        y = max(0.0, min(y, h - 1.0))

        x0 = int(math.floor(x))
        y0 = int(math.floor(y))
        x1 = min(x0 + 1, w - 1)
        y1 = min(y0 + 1, h - 1)

        # Fractional part
        dx = x - x0
        dy = y - y0

        # Four neighbours
        v00 = float(data[y0, x0])
        v10 = float(data[y0, x1])
        v01 = float(data[y1, x0])
        v11 = float(data[y1, x1])

        # Weighted combination
        value = (
            v00 * (1.0 - dx) * (1.0 - dy)
            + v10 * dx * (1.0 - dy)
            + v01 * (1.0 - dx) * dy
            + v11 * dx * dy
        )
        return value

    # ------------------------------------------------------------------
    # Line profile sampling
    # ------------------------------------------------------------------

    def sample_line_profile(
        self,
        data_2d: np.ndarray,
        start_xy: Tuple[float, float],
        end_xy: Tuple[float, float],
        mode: str = "luminance",
    ) -> Dict[str, Any]:
        """Sample an intensity profile along an arbitrary line.

        Parameters
        ----------
        data_2d : np.ndarray
            Image data — 2D (H, W) grayscale or 3D (H, W, C) colour.
        start_xy : tuple of (x, y)
            Start point in pixel coordinates (column, row).
        end_xy : tuple of (x, y)
            End point in pixel coordinates (column, row).
        mode : str
            One of 'luminance', 'red', 'green', 'blue', 'rgb'.

        Returns
        -------
        dict
            profile : np.ndarray or dict of np.ndarray (for 'rgb')
            distances : np.ndarray  — distance along line in pixels
            length_px : float       — total line length in pixels
            start : (x, y)
            end : (x, y)
        """
        if mode not in VALID_MODES:
            raise ValueError(
                f"Invalid mode '{mode}'. Must be one of {VALID_MODES}"
            )

        data = np.asarray(data_2d, dtype=np.float64)
        is_color = data.ndim == 3

        x0, y0 = float(start_xy[0]), float(start_xy[1])
        x1, y1 = float(end_xy[0]), float(end_xy[1])

        length_px = math.hypot(x1 - x0, y1 - y0)
        if length_px < 1e-9:
            # Degenerate line — single point
            n_samples = 1
        else:
            n_samples = max(int(round(length_px)) + 1, 2)

        # Parametric coordinates along the line [0..1]
        t = np.linspace(0.0, 1.0, n_samples)
        xs = x0 + t * (x1 - x0)
        ys = y0 + t * (y1 - y0)
        distances = t * length_px

        if mode == "rgb":
            # Sample all 3 channels independently
            profiles: Dict[str, np.ndarray] = {}
            for ch_idx, ch_name in enumerate(("red", "green", "blue")):
                channel = data[:, :, ch_idx] if is_color else data
                values = np.array(
                    [self.bilinear_interpolate(channel, xi, yi)
                     for xi, yi in zip(xs, ys)]
                )
                profiles[ch_name] = values
            profile_out: Any = profiles
        else:
            # Build a single 2D array to sample from
            if mode == "luminance":
                if is_color:
                    plane = (
                        BT709_R * data[:, :, 0]
                        + BT709_G * data[:, :, 1]
                        + BT709_B * data[:, :, 2]
                    )
                else:
                    plane = data
            elif mode == "red":
                plane = data[:, :, 0] if is_color else data
            elif mode == "green":
                plane = data[:, :, 1] if is_color else data
            elif mode == "blue":
                plane = data[:, :, 2] if is_color else data
            else:
                plane = data  # pragma: no cover

            values = np.array(
                [self.bilinear_interpolate(plane, xi, yi)
                 for xi, yi in zip(xs, ys)]
            )
            profile_out = values

        return {
            "profile": profile_out,
            "distances": distances,
            "length_px": length_px,
            "start": (x0, y0),
            "end": (x1, y1),
        }

    # ------------------------------------------------------------------
    # Profile comparison
    # ------------------------------------------------------------------

    @staticmethod
    def compare_profiles(
        profile1: np.ndarray,
        profile2: np.ndarray,
    ) -> Dict[str, float]:
        """Compare two 1D profiles after normalizing both to [0, 1].

        If the profiles differ in length, the shorter one is linearly
        interpolated to match the longer one.

        Parameters
        ----------
        profile1, profile2 : np.ndarray
            1D intensity profiles.

        Returns
        -------
        dict
            rmse, mae, correlation, peak_diff, mean_diff
        """
        p1 = np.asarray(profile1, dtype=np.float64).ravel()
        p2 = np.asarray(profile2, dtype=np.float64).ravel()

        # Resample shorter profile to match the longer one
        if len(p1) != len(p2):
            target_len = max(len(p1), len(p2))
            if len(p1) < target_len:
                p1 = np.interp(
                    np.linspace(0, 1, target_len),
                    np.linspace(0, 1, len(p1)),
                    p1,
                )
            else:
                p2 = np.interp(
                    np.linspace(0, 1, target_len),
                    np.linspace(0, 1, len(p2)),
                    p2,
                )

        # Normalize each to [0, 1]
        def _normalize(arr: np.ndarray) -> np.ndarray:
            vmin, vmax = arr.min(), arr.max()
            span = vmax - vmin
            if span < 1e-15:
                return np.zeros_like(arr)
            return (arr - vmin) / span

        p1 = _normalize(p1)
        p2 = _normalize(p2)

        diff = p1 - p2
        rmse = float(np.sqrt(np.mean(diff ** 2)))
        mae = float(np.mean(np.abs(diff)))
        peak_diff = float(np.max(p1) - np.max(p2))
        mean_diff = float(np.mean(p1) - np.mean(p2))

        # Pearson correlation (guard against constant profiles)
        std1, std2 = p1.std(), p2.std()
        if std1 < 1e-15 or std2 < 1e-15:
            correlation = 0.0
        else:
            correlation = float(np.corrcoef(p1, p2)[0, 1])

        return {
            "rmse": rmse,
            "mae": mae,
            "correlation": correlation,
            "peak_diff": peak_diff,
            "mean_diff": mean_diff,
        }

    # ------------------------------------------------------------------
    # Histogram computation
    # ------------------------------------------------------------------

    @staticmethod
    def compute_histogram(
        data_2d: np.ndarray,
        bins: int = 256,
        log_scale: bool = True,
    ) -> Dict[str, Any]:
        """Compute histogram and basic statistics for image data.

        For a 3D colour array (H, W, C), computes per-channel histograms
        and statistics.

        Parameters
        ----------
        data_2d : np.ndarray
            2D (H, W) or 3D (H, W, C) image data.
        bins : int
            Number of histogram bins (default 256).
        log_scale : bool
            If True, apply log1p to counts for display-friendly output.

        Returns
        -------
        dict
            For grayscale:
                bin_edges, counts, median, mean, std,
                percentiles: {1, 5, 50, 95, 99}
            For colour (3D):
                channels: dict mapping 'red'/'green'/'blue' to the above
        """
        data = np.asarray(data_2d, dtype=np.float64)

        def _histogram_for_plane(plane: np.ndarray) -> Dict[str, Any]:
            flat = plane.ravel()
            counts, bin_edges = np.histogram(flat, bins=bins)
            counts = counts.astype(np.float64)
            if log_scale:
                counts = np.log1p(counts)

            pcts = np.percentile(flat, [1, 5, 50, 95, 99])
            return {
                "bin_edges": bin_edges,
                "counts": counts,
                "median": float(np.median(flat)),
                "mean": float(np.mean(flat)),
                "std": float(np.std(flat)),
                "percentiles": {
                    1: float(pcts[0]),
                    5: float(pcts[1]),
                    50: float(pcts[2]),
                    95: float(pcts[3]),
                    99: float(pcts[4]),
                },
            }

        if data.ndim == 3:
            channel_names = ("red", "green", "blue")
            channels = {}
            for idx, name in enumerate(channel_names):
                if idx < data.shape[2]:
                    channels[name] = _histogram_for_plane(data[:, :, idx])
            return {"channels": channels}
        else:
            return _histogram_for_plane(data)
