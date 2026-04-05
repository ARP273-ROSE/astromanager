#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - CALIBRATION MATCHING & QUALITY SCORING MODULE
================================================================================
Configurable scoring system for matching calibration frames (Darks, Flats,
Biases, DarkFlats) to Light frames.  Inspired by Athenaeum's calibration
matching with 8 parameters, 3 match modes, and a continuous quality score.

Features:
  - 8 matching parameters (instrument, binning, gain, offset, exposure,
    focal length, filter, temperature)
  - 3 modes per parameter: EXACT / WARNING / IGNORE
  - Default profiles for Dark, Flat, Bias, DarkFlat matching
  - Configurable fallback chains (Dark → DarkFlat → Bias, etc.)
  - Quality score 0.0–1.0 with weighted penalty curves
  - Bilingual warnings (EN/FR)
  - Batch matching with best-of-N selection
  - Coverage report summarising calibration completeness
  - Human-readable match report (bilingual)

Pure logic module — no GUI code.  Uses only stdlib + typing.
================================================================================
"""

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class MatchMode(Enum):
    """How strictly a parameter must match between light and calibration."""
    EXACT = "exact"       # Must match exactly; mismatch → rejected
    WARNING = "warning"   # Mismatch reduces score but does not reject
    IGNORE = "ignore"     # Parameter not considered at all


class Severity(Enum):
    """Warning severity level."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# =============================================================================
# Data classes
# =============================================================================

@dataclass
class CalibrationWarning:
    """A single mismatch warning produced during scoring."""
    parameter: str        # e.g. 'temperature', 'gain'
    severity: Severity
    message_en: str
    message_fr: str
    actual_value: Any
    expected_value: Any
    score_penalty: float  # absolute penalty applied (0.0–1.0)


@dataclass
class MatchRule:
    """Rule for one matching parameter inside a CalibrationProfile."""
    parameter: str          # one of PARAMETER_KEYS
    mode: MatchMode
    tolerance: float = 0.0  # numeric tolerance for EXACT (e.g. ±0.01 for floats)
    weight: float = 0.0     # weight in [0, 1] for WARNING penalty calculation


@dataclass
class CalibrationProfile:
    """
    Complete rule-set for matching one calibration type to lights.

    Attributes:
        name:            profile identifier ('dark', 'flat', 'bias', 'darkflat')
        rules:           list of MatchRule (one per parameter)
        fallback_chain:  ordered list of other profile names to try when
                         no acceptable match is found with this profile
    """
    name: str
    rules: List[MatchRule] = field(default_factory=list)
    fallback_chain: List[str] = field(default_factory=list)

    def get_rule(self, parameter: str) -> Optional[MatchRule]:
        """Return the rule for *parameter*, or None if not configured."""
        for rule in self.rules:
            if rule.parameter == parameter:
                return rule
        return None


@dataclass
class CalibrationMatch:
    """Result of scoring a single calibration frame against a light."""
    calibration_file: Any      # path string or dict with file info
    match_score: float         # 0.0 to 1.0
    warnings: List[CalibrationWarning] = field(default_factory=list)
    matched_parameters: Dict[str, bool] = field(default_factory=dict)
    is_acceptable: bool = True  # False if any EXACT parameter mismatched
    profile_used: str = ""     # which profile produced this match


# =============================================================================
# Constants
# =============================================================================

# Canonical parameter keys (order used in reports)
PARAMETER_KEYS: Tuple[str, ...] = (
    "instrument",
    "binning",
    "gain",
    "offset",
    "exposure",
    "focal_length",
    "filter",
    "temperature",
)

# Mapping from parameter key to typical FITS header keywords.
# Used as documentation and by helpers that normalise input dicts.
HEADER_MAP: Dict[str, Tuple[str, ...]] = {
    "instrument":   ("INSTRUME",),
    "binning":      ("XBINNING", "YBINNING"),
    "gain":         ("GAIN",),
    "offset":       ("OFFSET",),
    "exposure":     ("EXPTIME",),
    "focal_length": ("FOCALLEN",),
    "filter":       ("FILTER",),
    "temperature":  ("CCD-TEMP", "SET-TEMP"),
}

# Default WARNING penalty curves — maps parameter to a callable
# (delta) → similarity in [0, 1].  A similarity of 1 means perfect match,
# 0 means worst possible mismatch.  The actual penalty is
# (1 - similarity) * rule.weight.
_DEFAULT_SIMILARITY = {
    "temperature":  lambda delta: max(0.0, 1.0 - abs(delta) / 10.0),
    "gain":         lambda delta: max(0.0, 1.0 - abs(delta) / 200.0),
    "offset":       lambda delta: max(0.0, 1.0 - abs(delta) / 100.0),
    "focal_length": lambda delta: max(0.0, 1.0 - abs(delta) / 500.0),
    "exposure":     lambda delta: max(0.0, 1.0 - abs(delta) / 600.0),
}

# Bilingual parameter display names
_PARAM_NAMES: Dict[str, Dict[str, str]] = {
    "instrument":   {"en": "Camera",        "fr": "Caméra"},
    "binning":      {"en": "Binning",       "fr": "Binning"},
    "gain":         {"en": "Gain",          "fr": "Gain"},
    "offset":       {"en": "Offset",        "fr": "Offset"},
    "exposure":     {"en": "Exposure",      "fr": "Exposition"},
    "focal_length": {"en": "Focal length",  "fr": "Focale"},
    "filter":       {"en": "Filter",        "fr": "Filtre"},
    "temperature":  {"en": "Temperature",   "fr": "Température"},
}


# =============================================================================
# Default profiles
# =============================================================================

def get_default_profiles() -> Dict[str, CalibrationProfile]:
    """
    Return the four built-in calibration profiles with sensible defaults.

    Returns:
        dict mapping profile name → CalibrationProfile
    """
    dark = CalibrationProfile(
        name="dark",
        rules=[
            MatchRule("instrument",   MatchMode.EXACT),
            MatchRule("binning",      MatchMode.EXACT),
            MatchRule("gain",         MatchMode.EXACT),
            MatchRule("offset",       MatchMode.WARNING, tolerance=0.0, weight=0.10),
            MatchRule("exposure",     MatchMode.EXACT,   tolerance=0.01),
            MatchRule("focal_length", MatchMode.IGNORE),
            MatchRule("filter",       MatchMode.IGNORE),
            MatchRule("temperature",  MatchMode.WARNING, tolerance=2.0, weight=0.30),
        ],
        fallback_chain=["darkflat", "bias"],
    )

    flat = CalibrationProfile(
        name="flat",
        rules=[
            MatchRule("instrument",   MatchMode.EXACT),
            MatchRule("binning",      MatchMode.EXACT),
            MatchRule("gain",         MatchMode.WARNING, tolerance=0.0, weight=0.20),
            MatchRule("offset",       MatchMode.IGNORE),
            MatchRule("exposure",     MatchMode.IGNORE),
            MatchRule("focal_length", MatchMode.WARNING, tolerance=0.0, weight=0.10),
            MatchRule("filter",       MatchMode.EXACT),
            MatchRule("temperature",  MatchMode.IGNORE),
        ],
        fallback_chain=[],
    )

    bias = CalibrationProfile(
        name="bias",
        rules=[
            MatchRule("instrument",   MatchMode.EXACT),
            MatchRule("binning",      MatchMode.EXACT),
            MatchRule("gain",         MatchMode.EXACT),
            MatchRule("offset",       MatchMode.EXACT),
            MatchRule("exposure",     MatchMode.IGNORE),
            MatchRule("focal_length", MatchMode.IGNORE),
            MatchRule("filter",       MatchMode.IGNORE),
            MatchRule("temperature",  MatchMode.WARNING, tolerance=5.0, weight=0.15),
        ],
        fallback_chain=[],
    )

    darkflat = CalibrationProfile(
        name="darkflat",
        rules=[
            MatchRule("instrument",   MatchMode.EXACT),
            MatchRule("binning",      MatchMode.EXACT),
            MatchRule("gain",         MatchMode.WARNING, tolerance=0.0, weight=0.20),
            MatchRule("offset",       MatchMode.IGNORE),
            MatchRule("exposure",     MatchMode.WARNING, tolerance=0.0, weight=0.10),
            MatchRule("focal_length", MatchMode.IGNORE),
            MatchRule("filter",       MatchMode.IGNORE),
            MatchRule("temperature",  MatchMode.WARNING, tolerance=3.0, weight=0.20),
        ],
        fallback_chain=["bias"],
    )

    return {
        "dark": dark,
        "flat": flat,
        "bias": bias,
        "darkflat": darkflat,
    }


# =============================================================================
# Internal helpers
# =============================================================================

def _normalise_str(value: Any) -> str:
    """Lowercase-stripped string for case-insensitive comparison."""
    if value is None:
        return ""
    return str(value).strip().lower()


def _safe_float(value: Any, default: float = float("nan")) -> float:
    """Convert *value* to float, returning *default* on failure."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_param(info: dict, parameter: str) -> Any:
    """
    Pull a parameter's value out of a frame-info dict.

    Accepts dicts keyed by canonical parameter names (e.g. 'gain') **or**
    raw FITS keywords (e.g. 'GAIN').  Returns None when not found.
    """
    # Try canonical key first
    if parameter in info:
        return info[parameter]
    # Try FITS header keyword(s)
    for kw in HEADER_MAP.get(parameter, ()):
        if kw in info:
            return info[kw]
        # Case-insensitive fallback
        for k, v in info.items():
            if k.upper() == kw.upper():
                return v
    return None


def _values_match_exact(val_light: Any, val_calib: Any,
                        parameter: str, tolerance: float) -> bool:
    """
    Return True when *val_light* and *val_calib* are considered an exact match.

    For numeric parameters a configurable *tolerance* is applied.  For string
    parameters the comparison is case-insensitive and stripped.
    """
    # Both missing → match (nothing to compare)
    if val_light is None and val_calib is None:
        return True
    # One missing → mismatch
    if val_light is None or val_calib is None:
        return False

    # String parameters: instrument, filter
    if parameter in ("instrument", "filter"):
        return _normalise_str(val_light) == _normalise_str(val_calib)

    # Numeric parameters
    fl = _safe_float(val_light)
    fc = _safe_float(val_calib)
    if math.isnan(fl) or math.isnan(fc):
        # Fall back to string comparison when not parseable as numbers
        return _normalise_str(val_light) == _normalise_str(val_calib)
    return abs(fl - fc) <= tolerance


def _compute_warning_penalty(val_light: Any, val_calib: Any,
                             parameter: str, rule: MatchRule
                             ) -> Tuple[float, float]:
    """
    Compute (penalty, delta) for a WARNING-mode mismatch.

    Returns:
        penalty: absolute score deduction in [0, rule.weight]
        delta:   raw numeric difference (0.0 for string params)
    """
    # String parameters — mismatch is a flat penalty
    if parameter in ("instrument", "filter"):
        if _normalise_str(val_light) != _normalise_str(val_calib):
            return (rule.weight, 0.0)
        return (0.0, 0.0)

    fl = _safe_float(val_light, 0.0)
    fc = _safe_float(val_calib, 0.0)
    delta = fl - fc

    sim_fn = _DEFAULT_SIMILARITY.get(parameter)
    if sim_fn is not None:
        similarity = sim_fn(delta)
    else:
        # Generic fallback: exact-or-not
        similarity = 1.0 if abs(delta) <= rule.tolerance else 0.0

    penalty = (1.0 - similarity) * rule.weight
    return (penalty, delta)


def _make_warning(parameter: str, severity: Severity,
                  actual: Any, expected: Any,
                  penalty: float, delta: float) -> CalibrationWarning:
    """Build a bilingual CalibrationWarning."""
    name_en = _PARAM_NAMES.get(parameter, {}).get("en", parameter)
    name_fr = _PARAM_NAMES.get(parameter, {}).get("fr", parameter)

    if parameter == "temperature":
        msg_en = (f"{name_en} mismatch: calibration {actual}°C "
                  f"vs light {expected}°C (Δ{delta:+.1f}°C)")
        msg_fr = (f"{name_fr} différente : calibration {actual}°C "
                  f"vs lumière {expected}°C (Δ{delta:+.1f}°C)")
    elif parameter in ("gain", "offset", "exposure", "focal_length"):
        msg_en = f"{name_en} mismatch: calibration {actual} vs light {expected}"
        msg_fr = f"{name_fr} différent(e) : calibration {actual} vs lumière {expected}"
    else:
        msg_en = f"{name_en} mismatch: '{actual}' vs '{expected}'"
        msg_fr = f"{name_fr} différent(e) : « {actual} » vs « {expected} »"

    return CalibrationWarning(
        parameter=parameter,
        severity=severity,
        message_en=msg_en,
        message_fr=msg_fr,
        actual_value=actual,
        expected_value=expected,
        score_penalty=penalty,
    )


# =============================================================================
# Core scoring function
# =============================================================================

def score_calibration_match(
    light_info: dict,
    calib_info: dict,
    profile: CalibrationProfile,
) -> CalibrationMatch:
    """
    Score how well a single calibration frame matches a light frame.

    Args:
        light_info:  dict of header values for the light frame.  Keys may be
                     canonical ('gain') or raw FITS keywords ('GAIN').
        calib_info:  dict of header values for the calibration frame.
        profile:     CalibrationProfile defining match rules.

    Returns:
        CalibrationMatch with score, warnings, and acceptability flag.
    """
    score = 1.0
    warnings: List[CalibrationWarning] = []
    matched: Dict[str, bool] = {}
    acceptable = True

    for rule in profile.rules:
        param = rule.parameter
        val_light = _extract_param(light_info, param)
        val_calib = _extract_param(calib_info, param)

        if rule.mode == MatchMode.IGNORE:
            matched[param] = True
            continue

        if rule.mode == MatchMode.EXACT:
            if _values_match_exact(val_light, val_calib, param, rule.tolerance):
                matched[param] = True
            else:
                matched[param] = False
                acceptable = False
                warnings.append(_make_warning(
                    param, Severity.ERROR, val_calib, val_light, 1.0, 0.0,
                ))
                score = 0.0

        elif rule.mode == MatchMode.WARNING:
            if _values_match_exact(val_light, val_calib, param, rule.tolerance):
                matched[param] = True
            else:
                matched[param] = False
                penalty, delta = _compute_warning_penalty(
                    val_light, val_calib, param, rule,
                )
                score = max(0.0, score - penalty)
                sev = Severity.WARNING if penalty > 0.05 else Severity.INFO
                warnings.append(_make_warning(
                    param, sev, val_calib, val_light, penalty, delta,
                ))

    calib_ref = calib_info.get("path", calib_info.get("file", calib_info))
    return CalibrationMatch(
        calibration_file=calib_ref,
        match_score=round(score, 4),
        warnings=warnings,
        matched_parameters=matched,
        is_acceptable=acceptable,
        profile_used=profile.name,
    )


# =============================================================================
# Batch matching
# =============================================================================

def find_best_calibrations(
    light_info: dict,
    calibration_pool: List[dict],
    profile: CalibrationProfile,
    max_results: int = 5,
) -> List[CalibrationMatch]:
    """
    Score every calibration frame in *calibration_pool* against *light_info*
    and return the top *max_results* acceptable matches sorted by score
    (descending).

    Args:
        light_info:        header dict for the light frame.
        calibration_pool:  list of header dicts for calibration frames.
        profile:           CalibrationProfile to apply.
        max_results:       maximum matches to return.

    Returns:
        list of CalibrationMatch (may be empty if nothing acceptable).
    """
    if not calibration_pool:
        return []

    matches: List[CalibrationMatch] = []
    for calib in calibration_pool:
        try:
            m = score_calibration_match(light_info, calib, profile)
            if m.is_acceptable:
                matches.append(m)
        except Exception:
            logger.debug("Scoring failed for calibration %s",
                         calib.get("path", "?"), exc_info=True)

    # Sort by score descending, then fewest warnings
    matches.sort(key=lambda m: (-m.match_score, len(m.warnings)))
    return matches[:max_results]


def find_calibrations_with_fallback(
    light_info: dict,
    calibration_pools: Dict[str, List[dict]],
    profiles: Optional[Dict[str, CalibrationProfile]] = None,
) -> Dict[str, List[CalibrationMatch]]:
    """
    For each calibration type needed by a light frame, find the best matches
    using the primary profile.  If no acceptable match is found, walk the
    fallback chain.

    Args:
        light_info:         header dict for the light.
        calibration_pools:  mapping of calibration type ('dark', 'flat', …)
                            to lists of header dicts.
        profiles:           mapping of profile name → CalibrationProfile.
                            Defaults to get_default_profiles().

    Returns:
        dict mapping calibration type → list of CalibrationMatch.
        The key is the **profile that actually produced** the matches,
        which may differ from the primary type when a fallback was used.

    Example::

        results = find_calibrations_with_fallback(light, pools)
        dark_matches = results.get('dark', [])
    """
    if profiles is None:
        profiles = get_default_profiles()

    results: Dict[str, List[CalibrationMatch]] = {}

    for calib_type, pool in calibration_pools.items():
        profile = profiles.get(calib_type)
        if profile is None:
            logger.warning("No profile for calibration type '%s'", calib_type)
            continue

        # Try primary profile
        matches = find_best_calibrations(light_info, pool, profile)
        if matches:
            results[calib_type] = matches
            continue

        # Walk fallback chain
        found_fallback = False
        for fallback_name in profile.fallback_chain:
            fb_profile = profiles.get(fallback_name)
            fb_pool = calibration_pools.get(fallback_name, [])
            if fb_profile is None or not fb_pool:
                continue
            fb_matches = find_best_calibrations(light_info, fb_pool, fb_profile)
            if fb_matches:
                results[calib_type] = fb_matches
                found_fallback = True
                logger.info(
                    "No direct %s match; using fallback '%s' (score %.2f)",
                    calib_type, fallback_name, fb_matches[0].match_score,
                )
                break

        if not found_fallback:
            results[calib_type] = []

    return results


# =============================================================================
# Coverage analysis
# =============================================================================

def get_calibration_coverage(
    lights: List[dict],
    calibrations: Dict[str, List[dict]],
    profiles: Optional[Dict[str, CalibrationProfile]] = None,
) -> dict:
    """
    Analyse how well a set of calibration frames covers a set of lights.

    Args:
        lights:        list of header dicts for light frames.
        calibrations:  mapping of calibration type → list of header dicts.
        profiles:      optional custom profiles (defaults to built-in).

    Returns:
        dict with keys:
          - 'total_lights':    int
          - 'per_type':        dict[calib_type → {covered, missing, avg_score,
                               min_score, warnings_count}]
          - 'fully_covered':   int  (lights with all calib types matched)
          - 'partially_covered': int
          - 'uncovered':       int  (lights with no calibrations at all)
          - 'details':         list of per-light dicts (optional, for reporting)
    """
    if profiles is None:
        profiles = get_default_profiles()

    calib_types = list(calibrations.keys())
    per_type: Dict[str, Dict[str, Any]] = {
        ct: {"covered": 0, "missing": 0, "avg_score": 0.0,
             "min_score": 1.0, "scores": [], "warnings_count": 0}
        for ct in calib_types
    }
    fully_covered = 0
    partially_covered = 0
    uncovered = 0
    details: List[dict] = []

    for light in lights:
        matches = find_calibrations_with_fallback(light, calibrations, profiles)
        light_ref = light.get("path", light.get("file", "?"))
        all_matched = True
        any_matched = False
        light_detail: dict = {"light": light_ref, "matches": {}}

        for ct in calib_types:
            ct_matches = matches.get(ct, [])
            if ct_matches:
                best = ct_matches[0]
                per_type[ct]["covered"] += 1
                per_type[ct]["scores"].append(best.match_score)
                per_type[ct]["min_score"] = min(
                    per_type[ct]["min_score"], best.match_score,
                )
                per_type[ct]["warnings_count"] += len(best.warnings)
                any_matched = True
                light_detail["matches"][ct] = {
                    "score": best.match_score,
                    "file": best.calibration_file,
                    "profile": best.profile_used,
                    "warnings": len(best.warnings),
                }
            else:
                per_type[ct]["missing"] += 1
                all_matched = False
                light_detail["matches"][ct] = None

        if all_matched and calib_types:
            fully_covered += 1
        elif any_matched:
            partially_covered += 1
        else:
            uncovered += 1

        details.append(light_detail)

    # Compute averages
    for ct in calib_types:
        scores = per_type[ct].pop("scores")
        per_type[ct]["avg_score"] = (
            round(sum(scores) / len(scores), 4) if scores else 0.0
        )
        if not scores:
            per_type[ct]["min_score"] = 0.0

    return {
        "total_lights": len(lights),
        "per_type": per_type,
        "fully_covered": fully_covered,
        "partially_covered": partially_covered,
        "uncovered": uncovered,
        "details": details,
    }


# =============================================================================
# Reporting
# =============================================================================

def format_match_report(
    matches: Dict[str, List[CalibrationMatch]],
    lang: str = "en",
) -> str:
    """
    Produce a human-readable text summary of calibration matches.

    Args:
        matches:  dict mapping calibration type → list of CalibrationMatch
                  (as returned by find_calibrations_with_fallback).
        lang:     'en' or 'fr'.

    Returns:
        Multi-line formatted string suitable for console or log output.
    """
    lines: List[str] = []

    header = ("=== Calibration Match Report ===" if lang == "en"
              else "=== Rapport de correspondance des calibrations ===")
    lines.append(header)
    lines.append("")

    if not matches:
        lines.append("No matches found." if lang == "en"
                      else "Aucune correspondance trouvée.")
        return "\n".join(lines)

    for calib_type, match_list in matches.items():
        type_label = calib_type.upper()
        count = len(match_list)

        if lang == "en":
            lines.append(f"--- {type_label}: {count} match(es) ---")
        else:
            lines.append(f"--- {type_label} : {count} correspondance(s) ---")

        if not match_list:
            lines.append(
                "  No acceptable match found." if lang == "en"
                else "  Aucune correspondance acceptable."
            )
            lines.append("")
            continue

        for i, m in enumerate(match_list, 1):
            score_pct = f"{m.match_score * 100:.0f}%"
            fb_note = ""
            if m.profile_used != calib_type:
                fb_note = (f" (fallback: {m.profile_used})" if lang == "en"
                           else f" (repli : {m.profile_used})")

            lines.append(f"  #{i}  Score: {score_pct}{fb_note}")
            lines.append(f"       File: {m.calibration_file}")

            if m.warnings:
                for w in m.warnings:
                    msg = w.message_fr if lang == "fr" else w.message_en
                    icon = "⚠" if w.severity == Severity.WARNING else "ℹ"
                    if w.severity == Severity.ERROR:
                        icon = "✖"
                    lines.append(f"       {icon} {msg}")

        lines.append("")

    return "\n".join(lines)


def format_coverage_report(
    coverage: dict,
    lang: str = "en",
) -> str:
    """
    Produce a human-readable text summary of calibration coverage.

    Args:
        coverage:  dict as returned by get_calibration_coverage().
        lang:      'en' or 'fr'.

    Returns:
        Multi-line formatted string.
    """
    lines: List[str] = []

    if lang == "en":
        lines.append("=== Calibration Coverage Report ===")
        lines.append(f"Total lights: {coverage['total_lights']}")
        lines.append(f"Fully covered:     {coverage['fully_covered']}")
        lines.append(f"Partially covered: {coverage['partially_covered']}")
        lines.append(f"Uncovered:         {coverage['uncovered']}")
    else:
        lines.append("=== Rapport de couverture des calibrations ===")
        lines.append(f"Total lumières : {coverage['total_lights']}")
        lines.append(f"Entièrement couvertes : {coverage['fully_covered']}")
        lines.append(f"Partiellement couvertes : {coverage['partially_covered']}")
        lines.append(f"Non couvertes :          {coverage['uncovered']}")

    lines.append("")

    for ct, info in coverage.get("per_type", {}).items():
        avg = f"{info['avg_score'] * 100:.0f}%"
        mn = f"{info['min_score'] * 100:.0f}%"
        if lang == "en":
            lines.append(
                f"  {ct.upper():10s}  covered: {info['covered']:4d}  "
                f"missing: {info['missing']:4d}  "
                f"avg score: {avg}  min: {mn}  "
                f"warnings: {info['warnings_count']}"
            )
        else:
            lines.append(
                f"  {ct.upper():10s}  couvertes : {info['covered']:4d}  "
                f"manquantes : {info['missing']:4d}  "
                f"score moy : {avg}  min : {mn}  "
                f"avertissements : {info['warnings_count']}"
            )

    return "\n".join(lines)
