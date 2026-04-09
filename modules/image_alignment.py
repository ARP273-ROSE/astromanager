#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - IMAGE ALIGNMENT MODULE
================================================================================
Registration and alignment utilities for astrophotography frames.
Inspired by AstroCrossSections.

Provides two alignment strategies:
  - Star-based alignment via astroalign (triangle asterism matching)
  - Phase correlation via scikit-image (subpixel shift detection)

Both methods handle mono and color images, different sizes, and return
diagnostic information about registration quality.

Feature-gated: gracefully degrades when optional dependencies are absent.
================================================================================
"""

import logging
import math
from typing import Dict, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature gates — optional dependencies
# ---------------------------------------------------------------------------

try:
    import astroalign
    HAS_ASTROALIGN = True
except ImportError:
    HAS_ASTROALIGN = False

try:
    from skimage.registration import phase_cross_correlation
    HAS_SKIMAGE = True
except ImportError:
    HAS_SKIMAGE = False

try:
    from scipy.ndimage import shift as ndimage_shift
    HAS_SCIPY_NDIMAGE = True
except ImportError:
    HAS_SCIPY_NDIMAGE = False


# ---------------------------------------------------------------------------
# Quality grade thresholds (residual RMS on normalized [0-1] data)
# ---------------------------------------------------------------------------
_GRADE_EXCELLENT = 0.02
_GRADE_GOOD = 0.05
_GRADE_FAIR = 0.10


def _to_luminance(image: np.ndarray) -> np.ndarray:
    """Convert a color image (H, W, C) to luminance (H, W).

    Uses standard ITU-R BT.601 luma coefficients.  If the image is already
    2-D (mono), it is returned unchanged.
    """
    if image.ndim == 2:
        return image
    if image.ndim == 3 and image.shape[2] >= 3:
        # Standard luminance weights: 0.2989 R + 0.5870 G + 0.1140 B
        return (
            0.2989 * image[:, :, 0]
            + 0.5870 * image[:, :, 1]
            + 0.1140 * image[:, :, 2]
        )
    # Single-channel with trailing dim (H, W, 1)
    if image.ndim == 3 and image.shape[2] == 1:
        return image[:, :, 0]
    raise ValueError(f"Unsupported image shape for luminance conversion: {image.shape}")


def _apply_transform_color(
    image: np.ndarray,
    transform_fn,
) -> np.ndarray:
    """Apply a per-channel spatial transform to a color image.

    *transform_fn* must accept a 2-D array and return a 2-D array of the
    same shape (the aligned channel).
    """
    if image.ndim == 2:
        return transform_fn(image)
    channels = []
    for c in range(image.shape[2]):
        channels.append(transform_fn(image[:, :, c]))
    return np.stack(channels, axis=-1)


class ImageAligner:
    """High-level image alignment facade.

    All public methods accept ``numpy.ndarray`` images (float or integer,
    mono or RGB) and return aligned arrays together with diagnostic dicts.
    """

    # ------------------------------------------------------------------
    # Star-based alignment (astroalign)
    # ------------------------------------------------------------------

    @staticmethod
    def align_astroalign(
        source: np.ndarray,
        target: np.ndarray,
        min_stars: int = 10,
    ) -> Tuple[Optional[np.ndarray], Union[Dict, str]]:
        """Align *source* to *target* using triangle-asterism star matching.

        Returns
        -------
        (aligned_array, transform_dict)  on success
        (None, error_string)             on failure

        *transform_dict* keys: rotation_deg, scale, translation_x,
        translation_y, n_matches.
        """
        if not HAS_ASTROALIGN:
            return None, "astroalign is not installed"

        source_f = source.astype(np.float64, copy=False)
        target_f = target.astype(np.float64, copy=False)

        source_f, target_f = ImageAligner.ensure_same_shape(source_f, target_f)

        # Alignment is computed on luminance; transform applied per-channel
        source_lum = _to_luminance(source_f)
        target_lum = _to_luminance(target_f)

        try:
            # Detect control points first so we can check star count
            transf, (s_coords, t_coords) = astroalign.find_transform(
                source_lum, target_lum
            )
        except astroalign.MaxIterError:
            return None, "Alignment failed: maximum iterations reached (too few features)"
        except astroalign.TooFewStarsError:
            return None, "Alignment failed: too few stars detected in one or both images"
        except Exception as exc:
            return None, f"Alignment failed: {exc}"

        n_matches = len(s_coords)
        if n_matches < min_stars:
            return None, (
                f"Only {n_matches} star matches found (minimum {min_stars} required)"
            )

        # Extract geometric parameters from the affine matrix
        matrix = transf.params  # 3x3 affine
        rotation_rad = math.atan2(matrix[1, 0], matrix[0, 0])
        scale = math.sqrt(matrix[0, 0] ** 2 + matrix[1, 0] ** 2)
        tx = matrix[0, 2]
        ty = matrix[1, 2]

        # Apply the transform to all channels
        # astroalign.apply_transform returns (registered, footprint)
        try:
            if source_f.ndim == 2:
                aligned, _ = astroalign.apply_transform(
                    transf, source_f, target_lum
                )
            else:
                channels = []
                for c in range(source_f.shape[2]):
                    reg_ch, _ = astroalign.apply_transform(
                        transf, source_f[:, :, c], target_lum
                    )
                    channels.append(reg_ch)
                aligned = np.stack(channels, axis=-1)
        except Exception as exc:
            return None, f"Transform application failed: {exc}"

        transform_dict = {
            "rotation_deg": math.degrees(rotation_rad),
            "scale": scale,
            "translation_x": float(tx),
            "translation_y": float(ty),
            "n_matches": n_matches,
        }
        logger.info(
            "astroalign: %d matches, rot=%.3f°, scale=%.5f, shift=(%.1f, %.1f)",
            n_matches,
            transform_dict["rotation_deg"],
            scale,
            tx,
            ty,
        )
        return aligned.astype(source.dtype), transform_dict

    # ------------------------------------------------------------------
    # Phase correlation alignment (scikit-image)
    # ------------------------------------------------------------------

    @staticmethod
    def align_phase_correlation(
        source: np.ndarray,
        target: np.ndarray,
        max_shift_fraction: float = 0.20,
    ) -> Tuple[Optional[np.ndarray], Union[Dict, str]]:
        """Align *source* to *target* using phase cross-correlation.

        Returns
        -------
        (aligned_array, diagnostic_dict)  on success
        (None, error_string)              on failure

        *diagnostic_dict* keys: shift_x, shift_y, error, diffphase.
        """
        if not HAS_SKIMAGE:
            return None, "scikit-image is not installed"

        source_f = source.astype(np.float64, copy=False)
        target_f = target.astype(np.float64, copy=False)

        source_f, target_f = ImageAligner.ensure_same_shape(source_f, target_f)

        source_lum = _to_luminance(source_f)
        target_lum = _to_luminance(target_f)

        try:
            shift_yx, error, diffphase = phase_cross_correlation(
                target_lum, source_lum, upsample_factor=10
            )
        except Exception as exc:
            return None, f"Phase correlation failed: {exc}"

        shift_y, shift_x = float(shift_yx[0]), float(shift_yx[1])

        # Sanity check: reject shifts larger than max_shift_fraction of image
        h, w = source_lum.shape
        if abs(shift_y) > h * max_shift_fraction or abs(shift_x) > w * max_shift_fraction:
            return None, (
                f"Detected shift ({shift_x:.1f}, {shift_y:.1f}) exceeds "
                f"{max_shift_fraction * 100:.0f}% of image size — likely incorrect"
            )

        # Apply subpixel shift
        def apply_shift(channel: np.ndarray) -> np.ndarray:
            if HAS_SCIPY_NDIMAGE:
                # scipy.ndimage.shift handles subpixel shifts via spline interpolation
                return ndimage_shift(channel, (shift_y, shift_x), order=3, mode="constant", cval=0.0)
            else:
                # Fallback: integer-pixel shift via numpy roll (no subpixel accuracy)
                sy = int(round(shift_y))
                sx = int(round(shift_x))
                shifted = np.roll(channel, sy, axis=0)
                shifted = np.roll(shifted, sx, axis=1)
                # Zero-fill rolled-in edges
                if sy > 0:
                    shifted[:sy, :] = 0
                elif sy < 0:
                    shifted[sy:, :] = 0
                if sx > 0:
                    shifted[:, :sx] = 0
                elif sx < 0:
                    shifted[:, sx:] = 0
                return shifted

        aligned = _apply_transform_color(source_f, apply_shift)

        diagnostic_dict = {
            "shift_x": shift_x,
            "shift_y": shift_y,
            "error": float(error) if error is not None else None,
            "diffphase": float(diffphase) if diffphase is not None else None,
        }
        logger.info(
            "Phase correlation: shift=(%.2f, %.2f), error=%.4f",
            shift_x,
            shift_y,
            diagnostic_dict["error"] or 0.0,
        )
        return aligned.astype(source.dtype), diagnostic_dict

    # ------------------------------------------------------------------
    # Registration diagnostic
    # ------------------------------------------------------------------

    @staticmethod
    def compute_registration_diagnostic(
        source: np.ndarray,
        target: np.ndarray,
        aligned: np.ndarray,
    ) -> Dict:
        """Compute quality metrics for an alignment result.

        Returns a dict with: residual_rms, overlap_fraction, quality_grade.
        """
        # Work on luminance, float64
        target_lum = _to_luminance(target.astype(np.float64, copy=False))
        aligned_lum = _to_luminance(aligned.astype(np.float64, copy=False))

        # Crop to common shape (should already match, but be safe)
        min_h = min(target_lum.shape[0], aligned_lum.shape[0])
        min_w = min(target_lum.shape[1], aligned_lum.shape[1])
        t_crop = target_lum[:min_h, :min_w]
        a_crop = aligned_lum[:min_h, :min_w]

        # Normalize both to [0, 1] for comparable RMS
        t_max = t_crop.max()
        a_max = a_crop.max()
        if t_max > 0:
            t_crop = t_crop / t_max
        if a_max > 0:
            a_crop = a_crop / a_max

        # Overlap mask: pixels that are non-zero in the aligned image
        overlap_mask = a_crop > 0
        overlap_fraction = float(overlap_mask.sum()) / overlap_mask.size if overlap_mask.size > 0 else 0.0

        # Residual RMS within the overlap region
        if overlap_mask.sum() > 0:
            residual = t_crop[overlap_mask] - a_crop[overlap_mask]
            residual_rms = float(np.sqrt(np.mean(residual ** 2)))
        else:
            residual_rms = 1.0  # No overlap at all

        # Quality grade
        if residual_rms <= _GRADE_EXCELLENT and overlap_fraction >= 0.90:
            grade = "Excellent"
        elif residual_rms <= _GRADE_GOOD and overlap_fraction >= 0.80:
            grade = "Good"
        elif residual_rms <= _GRADE_FAIR and overlap_fraction >= 0.60:
            grade = "Fair"
        else:
            grade = "Poor"

        return {
            "residual_rms": residual_rms,
            "overlap_fraction": overlap_fraction,
            "quality_grade": grade,
        }

    # ------------------------------------------------------------------
    # Shape harmonization
    # ------------------------------------------------------------------

    @staticmethod
    def ensure_same_shape(
        source: np.ndarray,
        target: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Crop both images to their minimum common dimensions.

        For 3-D (color) images the channel axis is preserved untouched;
        only spatial dimensions (H, W) are cropped from the bottom-right.
        """
        min_h = min(source.shape[0], target.shape[0])
        min_w = min(source.shape[1], target.shape[1])

        if source.ndim == 3:
            source = source[:min_h, :min_w, :]
        else:
            source = source[:min_h, :min_w]

        if target.ndim == 3:
            target = target[:min_h, :min_w, :]
        else:
            target = target[:min_h, :min_w]

        return source, target
