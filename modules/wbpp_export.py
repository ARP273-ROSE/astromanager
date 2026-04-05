#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - WBPP EXPORT MODULE
================================================================================
Organizes FITS/XISF/FITS.FZ files into a folder structure ready for
PixInsight's Weighted Batch PreProcessing (WBPP) script.

Output structure:
  Target_Name/
  +-- LIGHT/
  |   +-- Ha/
  |   +-- OIII/
  |   +-- L/
  +-- DARK/
  |   +-- 300s_-10C/
  |   +-- 120s_-10C/
  +-- FLAT/
  |   +-- Ha/
  |   +-- L/
  +-- BIAS/
      +-- bias_001.fits

Features:
  - Scan source folders for FITS/XISF/FZ files, read headers
  - Classify by IMAGETYP (Light, Dark, Flat, Bias, DarkFlat)
  - Group Lights by target + filter, Darks by exposure + temp, Flats by filter
  - Match calibration frames to lights (temp tolerance, filter, instrument)
  - Configurable template system for output folder structure
  - Export modes: copy, symlink, move, list-only
  - Export plan preview, progress callbacks, JSON report, validation warnings

Pure logic module -- no GUI code. Uses pathlib.Path for all file operations.
================================================================================
"""

import json
import logging
import os
import platform
import shutil
import tempfile
import uuid
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Supported file extensions (lowercase)
SUPPORTED_EXTENSIONS = {'.fits', '.fit', '.fts', '.xisf', '.fz'}

# Default template for WBPP folder structure
DEFAULT_TEMPLATE = "{OBJECT}/{IMAGETYP}/{FILTER}"

# Template for darks: uses exposure + temperature instead of filter
DARK_TEMPLATE = "{OBJECT}/{IMAGETYP}/{EXPTIME}s_{TEMP}C"

# Template for biases: no filter, no exposure
BIAS_TEMPLATE = "{OBJECT}/{IMAGETYP}"

# Characters forbidden in folder names on Windows/macOS/Linux
_FORBIDDEN_CHARS = '<>:"|?*\x00'

# Maximum path length safety margin (Windows MAX_PATH = 260)
_MAX_PATH_LEN = 250


# =============================================================================
# Data classes
# =============================================================================

@dataclass
class FileInfo:
    """Metadata extracted from a single FITS/XISF file header."""
    path: str
    image_type: str       # LIGHT, DARK, FLAT, BIAS, DARKFLAT
    target: str           # OBJECT keyword value
    filter_name: str      # FILTER keyword value
    exposure: float       # EXPTIME in seconds
    temperature: float    # CCD-TEMP in Celsius
    camera: str           # INSTRUME
    telescope: str        # TELESCOP
    gain: int             # GAIN
    offset: int           # OFFSET
    binning: int          # XBINNING
    date_obs: str         # DATE-OBS (ISO string)
    dimensions: tuple     # (NAXIS1, NAXIS2)


@dataclass
class ExportPlan:
    """A single file mapping from source to destination."""
    source: str
    destination: str
    image_type: str
    group: str            # Grouping key for display


@dataclass
class CalibrationMatch:
    """Calibration frames matched to a light group."""
    light_target: str
    light_filter: str
    darks: List[FileInfo] = field(default_factory=list)
    flats: List[FileInfo] = field(default_factory=list)
    biases: List[FileInfo] = field(default_factory=list)
    dark_temp_delta: float = 0.0    # Actual temperature difference for darks
    warnings: List[str] = field(default_factory=list)


@dataclass
class ExportResult:
    """Summary of an export execution."""
    total_files: int
    copied_files: int
    failed_files: int
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    groups: Dict[str, int] = field(default_factory=dict)
    export_path: str = ""
    duration_seconds: float = 0.0


# =============================================================================
# IMAGETYP normalization
# =============================================================================

# Map of known IMAGETYP string variants to canonical names
_IMAGETYP_MAP = {
    # Lights
    'light': 'LIGHT',
    'light frame': 'LIGHT',
    'science': 'LIGHT',
    'science frame': 'LIGHT',
    'object': 'LIGHT',
    # Darks
    'dark': 'DARK',
    'dark frame': 'DARK',
    # Flats
    'flat': 'FLAT',
    'flat frame': 'FLAT',
    'flat field': 'FLAT',
    'flatfield': 'FLAT',
    'skyflat': 'FLAT',
    'sky flat': 'FLAT',
    'twilight flat': 'FLAT',
    # Biases
    'bias': 'BIAS',
    'bias frame': 'BIAS',
    'offset': 'BIAS',
    'offset frame': 'BIAS',
    'zero': 'BIAS',
    'zero frame': 'BIAS',
    # Dark flats
    'darkflat': 'DARKFLAT',
    'dark flat': 'DARKFLAT',
    'dark flat frame': 'DARKFLAT',
}


def _normalize_image_type(raw: str) -> str:
    """Normalize IMAGETYP keyword value to canonical form."""
    if not raw:
        return 'LIGHT'
    cleaned = raw.strip().lower()
    if cleaned in _IMAGETYP_MAP:
        return _IMAGETYP_MAP[cleaned]
    # Fallback: partial matching
    upper = cleaned.upper()
    if 'LIGHT' in upper or 'SCIENCE' in upper:
        return 'LIGHT'
    if 'DARKFLAT' in upper:
        return 'DARKFLAT'
    if 'DARK' in upper:
        return 'DARK'
    if 'FLAT' in upper:
        return 'FLAT'
    if 'BIAS' in upper or 'OFFSET' in upper or 'ZERO' in upper:
        return 'BIAS'
    logger.warning("Unknown IMAGETYP '%s', defaulting to LIGHT", raw)
    return 'LIGHT'


# =============================================================================
# Path sanitation
# =============================================================================

def _sanitize_name(name: str) -> str:
    """Sanitize a string for use as a folder or file name component."""
    if not name or name.strip() == '':
        return 'Unknown'
    # Strip leading/trailing whitespace
    name = name.strip()
    # Replace forbidden characters
    for ch in _FORBIDDEN_CHARS:
        name = name.replace(ch, '_')
    # Replace path separators
    name = name.replace('/', '_').replace('\\', '_')
    # Collapse multiple underscores
    while '__' in name:
        name = name.replace('__', '_')
    # Strip leading/trailing dots and spaces (Windows restriction)
    name = name.strip('. ')
    return name if name else 'Unknown'


def _validate_path_safe(path: Path, root: Path) -> bool:
    """
    Validate that a path does not escape the export root.
    Rejects path traversal via '..', null bytes, and backslash tricks.
    """
    path_str = str(path)
    # Reject null bytes
    if '\x00' in path_str:
        return False
    # Reject '..' components
    for part in path.parts:
        if part == '..':
            return False
        if '..' in part:
            return False
    # Resolve and verify containment
    try:
        resolved = path.resolve()
        root_resolved = root.resolve()
        # Check that resolved path starts with root (use separator suffix
        # to prevent /root_path matching /root_path_evil)
        root_str = str(root_resolved)
        if not root_str.endswith(os.sep):
            root_str += os.sep
        resolved_str = str(resolved)
        return resolved_str.startswith(root_str) or resolved_str == str(root_resolved)
    except (OSError, ValueError):
        return False


def _check_path_length(path: Path) -> bool:
    """Check if path exceeds safe maximum length."""
    return len(str(path)) <= _MAX_PATH_LEN


# =============================================================================
# Header reading (delegates to existing header_editor module)
# =============================================================================

def _read_file_info(filepath: str) -> Optional[FileInfo]:
    """
    Read FITS/XISF header and extract all fields needed for WBPP organization.
    Returns None if file cannot be read or is not a supported format.
    """
    try:
        from .header_editor import read_header, get_header_value
    except ImportError:
        logger.error("header_editor module not available")
        return None

    try:
        header = read_header(filepath)
        if not header:
            return None

        # Image type
        raw_type = get_header_value(header, 'IMAGETYP') or ''
        image_type = _normalize_image_type(str(raw_type))

        # Target
        target = str(get_header_value(header, 'OBJECT') or 'Unknown').strip()
        if not target:
            target = 'Unknown'

        # Filter
        filter_name = str(get_header_value(header, 'FILTER') or 'NoFilter').strip()
        if not filter_name:
            filter_name = 'NoFilter'

        # Exposure time
        exp_val = get_header_value(header, 'EXPTIME')
        try:
            exposure = float(exp_val) if exp_val is not None else 0.0
        except (ValueError, TypeError):
            exposure = 0.0

        # CCD temperature
        temp_val = get_header_value(header, 'CCD-TEMP')
        try:
            temperature = float(temp_val) if temp_val is not None else 0.0
        except (ValueError, TypeError):
            temperature = 0.0

        # Camera (instrument)
        camera = str(get_header_value(header, 'INSTRUME') or 'Unknown').strip()

        # Telescope
        telescope = str(get_header_value(header, 'TELESCOP') or 'Unknown').strip()

        # Gain
        gain_val = get_header_value(header, 'GAIN')
        try:
            gain = int(gain_val) if gain_val is not None else 0
        except (ValueError, TypeError):
            gain = 0

        # Offset
        offset_val = get_header_value(header, 'OFFSET')
        try:
            offset = int(offset_val) if offset_val is not None else 0
        except (ValueError, TypeError):
            offset = 0

        # Binning
        bin_val = get_header_value(header, 'XBINNING')
        try:
            binning = int(bin_val) if bin_val is not None else 1
        except (ValueError, TypeError):
            binning = 1

        # Date
        date_obs = str(get_header_value(header, 'DATE-OBS') or '')

        # Dimensions
        naxis1 = get_header_value(header, 'NAXIS1')
        naxis2 = get_header_value(header, 'NAXIS2')
        try:
            dimensions = (int(naxis1) if naxis1 else 0,
                          int(naxis2) if naxis2 else 0)
        except (ValueError, TypeError):
            dimensions = (0, 0)

        return FileInfo(
            path=str(filepath),
            image_type=image_type,
            target=target,
            filter_name=filter_name,
            exposure=exposure,
            temperature=temperature,
            camera=camera,
            telescope=telescope,
            gain=gain,
            offset=offset,
            binning=binning,
            date_obs=date_obs,
            dimensions=dimensions,
        )

    except Exception as e:
        logger.warning("Failed to read header for %s: %s", filepath, e)
        return None


# =============================================================================
# Scanning
# =============================================================================

def scan_files(folders: List[str],
               recursive: bool = True,
               callback: Optional[Callable] = None) -> List[FileInfo]:
    """
    Scan one or more folders for FITS/XISF/FZ files and read their headers.

    Args:
        folders: List of directory paths to scan.
        recursive: Whether to recurse into subdirectories.
        callback: Optional progress callback(current, total, message).

    Returns:
        List of FileInfo objects for every successfully read file.
    """
    # Phase 1: Collect all file paths
    all_paths = []
    for folder in folders:
        folder_path = Path(folder)
        if not folder_path.is_dir():
            logger.warning("Folder does not exist or is not a directory: %s", folder)
            continue

        iterator = folder_path.rglob('*') if recursive else folder_path.glob('*')
        for f in iterator:
            if not f.is_file():
                continue
            name_lower = f.name.lower()
            # Check for .fits.fz compound extension first
            if name_lower.endswith('.fits.fz') or name_lower.endswith('.fit.fz'):
                all_paths.append(str(f))
            elif f.suffix.lower() in SUPPORTED_EXTENSIONS:
                all_paths.append(str(f))

    total = len(all_paths)
    if total == 0:
        return []

    if callback:
        callback(0, total, "Scanning files...")

    # Phase 2: Read headers in parallel for performance
    results = []
    num_workers = min(os.cpu_count() or 4, total, 8)

    if num_workers > 1 and total > 5:
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = {executor.submit(_read_file_info, fp): fp
                       for fp in all_paths}
            for i, future in enumerate(as_completed(futures)):
                try:
                    info = future.result(timeout=30)
                    if info is not None:
                        results.append(info)
                except Exception as e:
                    fp = futures[future]
                    logger.debug("Worker failed for %s: %s", fp, e)
                if callback and (i % 25 == 0 or i == total - 1):
                    callback(i + 1, total, f"Reading headers ({i + 1}/{total})")
    else:
        for i, fp in enumerate(all_paths):
            info = _read_file_info(fp)
            if info is not None:
                results.append(info)
            if callback and (i % 25 == 0 or i == total - 1):
                callback(i + 1, total, f"Reading headers ({i + 1}/{total})")

    if callback:
        callback(total, total, f"Scan complete: {len(results)} files")

    return results


# =============================================================================
# Calibration matching
# =============================================================================

def match_calibrations(lights: List[FileInfo],
                       darks: List[FileInfo],
                       flats: List[FileInfo],
                       biases: List[FileInfo],
                       temp_tolerance: float = 2.0) -> Dict[str, CalibrationMatch]:
    """
    Match calibration frames (darks, flats, biases) to light frame groups.

    Matching criteria:
      - Darks: same exposure time, closest temperature within tolerance, same camera.
      - Flats: same filter, same camera.
      - Biases: same camera.

    Args:
        lights: List of LIGHT FileInfo objects.
        darks: List of DARK FileInfo objects.
        flats: List of FLAT FileInfo objects.
        biases: List of BIAS FileInfo objects.
        temp_tolerance: Maximum temperature difference in Celsius for dark matching.

    Returns:
        Dict keyed by "target|filter" with CalibrationMatch objects.
    """
    matches = {}

    # Group lights by target + filter
    light_groups = defaultdict(list)
    for lf in lights:
        key = f"{lf.target}|{lf.filter_name}"
        light_groups[key].append(lf)

    for group_key, group_lights in light_groups.items():
        target, filt = group_key.split('|', 1)
        match = CalibrationMatch(light_target=target, light_filter=filt)

        # Representative light for matching criteria
        ref = group_lights[0]

        # --- Match Darks ---
        # Same exposure, same camera, closest temperature within tolerance
        candidate_darks = [
            d for d in darks
            if abs(d.exposure - ref.exposure) < 0.01
            and d.camera == ref.camera
        ]
        if candidate_darks:
            # Sort by temperature proximity to light frames
            avg_temp = sum(l.temperature for l in group_lights) / len(group_lights)
            candidate_darks.sort(key=lambda d: abs(d.temperature - avg_temp))
            best_temp = candidate_darks[0].temperature
            temp_delta = abs(best_temp - avg_temp)
            if temp_delta <= temp_tolerance:
                # Accept all darks at this temperature (within 0.5 deg of best)
                match.darks = [
                    d for d in candidate_darks
                    if abs(d.temperature - best_temp) <= 0.5
                ]
                match.dark_temp_delta = temp_delta
            else:
                match.warnings.append(
                    f"Closest dark temperature is {best_temp:.1f}C "
                    f"(delta={temp_delta:.1f}C > tolerance={temp_tolerance:.1f}C)"
                )
        else:
            match.warnings.append(
                f"No darks found for exposure={ref.exposure:.1f}s, "
                f"camera={ref.camera}"
            )

        # --- Match Flats ---
        # Same filter, same camera
        match.flats = [
            f for f in flats
            if f.filter_name == ref.filter_name
            and f.camera == ref.camera
        ]
        if not match.flats:
            match.warnings.append(
                f"No flats found for filter={ref.filter_name}, "
                f"camera={ref.camera}"
            )

        # --- Match Biases ---
        # Same camera
        match.biases = [b for b in biases if b.camera == ref.camera]
        if not match.biases:
            match.warnings.append(f"No biases found for camera={ref.camera}")

        matches[group_key] = match

    return matches


# =============================================================================
# Template expansion
# =============================================================================

def _expand_template(template: str, info: FileInfo) -> str:
    """
    Expand a template string using file info fields.

    Supported tokens:
      {OBJECT}    - Target name
      {IMAGETYP}  - Image type (LIGHT, DARK, FLAT, BIAS)
      {FILTER}    - Filter name
      {DATE}      - Observation date (YYYY-MM-DD)
      {CAMERA}    - Camera/instrument name
      {TELESCOPE} - Telescope name
      {EXPTIME}   - Exposure time in seconds (integer)
      {TEMP}      - CCD temperature in Celsius (integer, negative sign preserved)
      {GAIN}      - Gain value
      {BINNING}   - Binning value (e.g. 1, 2)
    """
    # Extract date portion (YYYY-MM-DD)
    date_str = info.date_obs[:10] if info.date_obs and len(info.date_obs) >= 10 else 'Unknown_Date'

    # Temperature: round to integer, preserve negative sign
    temp_int = int(round(info.temperature))
    temp_str = str(temp_int)  # e.g. "-10" or "20"

    # Exposure: integer if whole number, else one decimal
    if info.exposure == int(info.exposure):
        exp_str = str(int(info.exposure))
    else:
        exp_str = f"{info.exposure:.1f}"

    token_map = {
        '{OBJECT}': _sanitize_name(info.target),
        '{IMAGETYP}': info.image_type,
        '{FILTER}': _sanitize_name(info.filter_name),
        '{DATE}': _sanitize_name(date_str),
        '{CAMERA}': _sanitize_name(info.camera),
        '{TELESCOPE}': _sanitize_name(info.telescope),
        '{EXPTIME}': exp_str,
        '{TEMP}': temp_str,
        '{GAIN}': str(info.gain),
        '{BINNING}': str(info.binning),
    }

    result = template
    for token, value in token_map.items():
        result = result.replace(token, value)
    return result


def _get_template_for_type(image_type: str, user_template: Optional[str] = None) -> str:
    """
    Get the appropriate template for a given image type.
    If user_template is provided, use it. Otherwise, use smart defaults.
    """
    if user_template:
        return user_template
    if image_type == 'DARK':
        return DARK_TEMPLATE
    if image_type == 'BIAS':
        return BIAS_TEMPLATE
    if image_type == 'DARKFLAT':
        return "{OBJECT}/{IMAGETYP}/{FILTER}"
    # LIGHT, FLAT, and anything else
    return DEFAULT_TEMPLATE


# =============================================================================
# Export plan building
# =============================================================================

def build_export_plan(files: List[FileInfo],
                      export_root: str,
                      template: Optional[str] = None,
                      include_calibrations: bool = True,
                      group_darks_by_temp: bool = True) -> List[ExportPlan]:
    """
    Build a list of (source, destination) mappings for the WBPP export.

    Args:
        files: List of FileInfo from scan_files().
        export_root: Root directory for the export output.
        template: Optional custom template string. If None, uses smart defaults
                  per image type (lights/flats use filter, darks use exp+temp).
        include_calibrations: Include Dark/Flat/Bias in the plan.
        group_darks_by_temp: Sub-group darks by exposure+temperature.

    Returns:
        List of ExportPlan entries, one per file.
    """
    root_path = Path(export_root).resolve()
    plan = []
    # Track destination filenames for conflict resolution
    used_destinations = set()

    for info in files:
        # Skip calibration frames if not requested
        if not include_calibrations and info.image_type != 'LIGHT':
            continue

        # Select template for this image type
        tmpl = _get_template_for_type(info.image_type, template)

        # Expand template
        rel_dir = _expand_template(tmpl, info)
        dest_dir = root_path / rel_dir

        # Build destination filename (preserve original name)
        dest_file = dest_dir / Path(info.path).name

        # Path traversal validation
        if not _validate_path_safe(dest_file, root_path):
            logger.warning("Path traversal detected, skipping: %s", info.path)
            continue

        # Path length check
        if not _check_path_length(dest_file):
            logger.warning("Path too long (%d chars), skipping: %s",
                           len(str(dest_file)), info.path)
            continue

        # Handle destination conflicts (same filename in same folder)
        dest_str = str(dest_file)
        if dest_str in used_destinations:
            stem = dest_file.stem
            suffix = dest_file.suffix
            # Handle compound extensions like .fits.fz
            name_lower = dest_file.name.lower()
            if name_lower.endswith('.fits.fz') or name_lower.endswith('.fit.fz'):
                # Split at the first .fits or .fit
                base_name = dest_file.name
                for ext_marker in ('.fits.fz', '.fit.fz', '.FITS.fz', '.FIT.fz'):
                    if base_name.endswith(ext_marker):
                        stem = base_name[:-len(ext_marker)]
                        suffix = ext_marker
                        break

            counter = 2
            while dest_str in used_destinations:
                dest_file = dest_dir / f"{stem}_{counter}{suffix}"
                dest_str = str(dest_file)
                counter += 1

        used_destinations.add(dest_str)

        # Build grouping key for UI display
        group_key = f"{info.image_type}"
        if info.image_type == 'LIGHT':
            group_key = f"LIGHT / {info.target} / {info.filter_name}"
        elif info.image_type == 'DARK':
            group_key = f"DARK / {int(info.exposure)}s / {int(round(info.temperature))}C"
        elif info.image_type == 'FLAT':
            group_key = f"FLAT / {info.filter_name}"
        elif info.image_type == 'BIAS':
            group_key = "BIAS"

        plan.append(ExportPlan(
            source=info.path,
            destination=dest_str,
            image_type=info.image_type,
            group=group_key,
        ))

    return plan


# =============================================================================
# Export execution
# =============================================================================

def execute_export(plan: List[ExportPlan],
                   mode: str = 'copy',
                   callback: Optional[Callable] = None) -> ExportResult:
    """
    Execute an export plan by copying, symlinking, or moving files.

    Args:
        plan: Export plan from build_export_plan().
        mode: One of 'copy', 'symlink', 'move', 'list'.
              'list' performs no file operations (dry run).
        callback: Optional progress callback(current, total, message).

    Returns:
        ExportResult with counts and diagnostics.
    """
    valid_modes = ('copy', 'symlink', 'move', 'list')
    if mode not in valid_modes:
        raise ValueError(f"Invalid export mode '{mode}'. Must be one of {valid_modes}")

    start_time = datetime.now()
    total = len(plan)
    result = ExportResult(
        total_files=total,
        copied_files=0,
        failed_files=0,
        export_path=str(Path(plan[0].destination).parent) if plan else "",
    )

    # Count by image type
    type_counts = defaultdict(int)
    for entry in plan:
        type_counts[entry.image_type] += 1
    result.groups = dict(type_counts)

    # List mode: no file operations
    if mode == 'list':
        result.copied_files = total
        if callback:
            callback(total, total, "List-only mode: no files written")
        return result

    for i, entry in enumerate(plan):
        src = Path(entry.source)
        dst = Path(entry.destination)

        if callback and (i % 10 == 0 or i == total - 1):
            callback(i + 1, total, f"{mode.capitalize()}: {src.name}")

        try:
            # Create destination directory
            dst.parent.mkdir(parents=True, exist_ok=True)

            if mode == 'copy':
                _atomic_copy(src, dst)
            elif mode == 'symlink':
                _create_symlink(src, dst)
            elif mode == 'move':
                _atomic_move(src, dst)

            result.copied_files += 1

        except OSError as e:
            result.failed_files += 1
            msg = f"Failed to {mode} {src.name}: {e}"
            result.errors.append(msg)
            logger.warning(msg)
        except Exception as e:
            result.failed_files += 1
            msg = f"Unexpected error {mode} {src.name}: {e}"
            result.errors.append(msg)
            logger.error(msg)

    elapsed = (datetime.now() - start_time).total_seconds()
    result.duration_seconds = elapsed

    if callback:
        callback(total, total,
                 f"Export complete: {result.copied_files}/{total} files "
                 f"({elapsed:.1f}s)")

    return result


def _atomic_copy(src: Path, dst: Path) -> None:
    """Copy a file atomically: write to temp, then rename."""
    tmp_path = dst.parent / f".tmp_{uuid.uuid4().hex}_{dst.name}"
    try:
        shutil.copy2(str(src), str(tmp_path))
        # Atomic rename (same filesystem)
        tmp_path.replace(dst)
    except BaseException:
        # Clean up temp file on any failure
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _atomic_move(src: Path, dst: Path) -> None:
    """Move a file, using rename if same filesystem, else copy+delete."""
    try:
        src.rename(dst)
    except OSError:
        # Cross-filesystem: copy then delete
        _atomic_copy(src, dst)
        src.unlink()


def _create_symlink(src: Path, dst: Path) -> None:
    """
    Create a symbolic link. Falls back to copy on Windows if symlink
    creation requires elevated privileges.
    """
    try:
        dst.symlink_to(src.resolve())
    except OSError as e:
        if platform.system() == 'Windows':
            logger.info("Symlink failed on Windows (privileges?), falling back to copy")
            _atomic_copy(src, dst)
        else:
            raise


# =============================================================================
# Validation
# =============================================================================

def validate_export(files: List[FileInfo],
                    temp_tolerance: float = 2.0) -> List[str]:
    """
    Validate file groups and return a list of warnings about potential issues.

    Checks:
      - Missing calibration frames for each light group
      - Temperature mismatches between lights and darks
      - Incomplete filter sets
      - Mixed cameras or telescopes within a target
      - Very few frames in a group (< 5 lights)
      - Missing OBJECT on light frames

    Args:
        files: List of FileInfo from scan_files().
        temp_tolerance: Temperature tolerance for dark matching.

    Returns:
        List of human-readable warning strings.
    """
    warnings_list = []

    # Separate by type
    lights = [f for f in files if f.image_type == 'LIGHT']
    darks = [f for f in files if f.image_type == 'DARK']
    flats = [f for f in files if f.image_type == 'FLAT']
    biases = [f for f in files if f.image_type == 'BIAS']

    if not lights:
        warnings_list.append("No LIGHT frames found in the scanned files")
        return warnings_list

    # Group lights by target + filter
    light_groups = defaultdict(list)
    for lf in lights:
        light_groups[f"{lf.target}|{lf.filter_name}"].append(lf)

    for key, group in light_groups.items():
        target, filt = key.split('|', 1)
        ref = group[0]
        prefix = f"[{target}/{filt}]"

        # Warn about unknown targets
        if target == 'Unknown':
            warnings_list.append(
                f"{prefix} {len(group)} light frames have no OBJECT keyword"
            )

        # Warn about small groups
        if len(group) < 5:
            warnings_list.append(
                f"{prefix} Only {len(group)} light frame(s) "
                f"(minimum 5 recommended for stacking)"
            )

        # Check for matching darks
        matching_darks = [
            d for d in darks
            if abs(d.exposure - ref.exposure) < 0.01
            and d.camera == ref.camera
        ]
        if not matching_darks:
            warnings_list.append(
                f"{prefix} No matching darks "
                f"(need {ref.exposure:.0f}s, camera={ref.camera})"
            )
        else:
            avg_light_temp = sum(l.temperature for l in group) / len(group)
            closest_dark_temp = min(matching_darks,
                                    key=lambda d: abs(d.temperature - avg_light_temp))
            delta = abs(closest_dark_temp.temperature - avg_light_temp)
            if delta > temp_tolerance:
                warnings_list.append(
                    f"{prefix} Dark temperature mismatch: "
                    f"lights avg {avg_light_temp:.1f}C, "
                    f"closest dark {closest_dark_temp.temperature:.1f}C "
                    f"(delta={delta:.1f}C > {temp_tolerance:.1f}C tolerance)"
                )

        # Check for matching flats
        matching_flats = [
            f for f in flats
            if f.filter_name == ref.filter_name
            and f.camera == ref.camera
        ]
        if not matching_flats:
            warnings_list.append(
                f"{prefix} No matching flats "
                f"(need filter={ref.filter_name}, camera={ref.camera})"
            )

        # Check for matching biases
        matching_biases = [b for b in biases if b.camera == ref.camera]
        if not matching_biases:
            warnings_list.append(
                f"{prefix} No matching biases (camera={ref.camera})"
            )

    # Check for mixed setups within a target
    targets = defaultdict(list)
    for lf in lights:
        targets[lf.target].append(lf)
    for target, target_lights in targets.items():
        cameras = set(l.camera for l in target_lights)
        if len(cameras) > 1:
            warnings_list.append(
                f"[{target}] Mixed cameras detected: {', '.join(sorted(cameras))}"
            )
        telescopes = set(l.telescope for l in target_lights)
        if len(telescopes) > 1:
            warnings_list.append(
                f"[{target}] Mixed telescopes detected: {', '.join(sorted(telescopes))}"
            )

    return warnings_list


# =============================================================================
# Report generation
# =============================================================================

def generate_report(result: ExportResult,
                    export_root: str,
                    plan: Optional[List[ExportPlan]] = None,
                    validation_warnings: Optional[List[str]] = None) -> dict:
    """
    Generate a JSON-serializable report dictionary summarizing the export.

    Args:
        result: ExportResult from execute_export().
        export_root: Root export directory path.
        plan: Optional export plan for detailed breakdown.
        validation_warnings: Optional pre-export validation warnings.

    Returns:
        Dict suitable for JSON serialization.
    """
    report = {
        'timestamp': datetime.now().isoformat(),
        'export_root': str(export_root),
        'summary': {
            'total_files': result.total_files,
            'copied_files': result.copied_files,
            'failed_files': result.failed_files,
            'duration_seconds': round(result.duration_seconds, 2),
        },
        'groups': result.groups,
        'warnings': result.warnings + (validation_warnings or []),
        'errors': result.errors,
    }

    # Detailed breakdown by group if plan is provided
    if plan:
        group_details = defaultdict(lambda: {'count': 0, 'files': []})
        for entry in plan:
            grp = group_details[entry.group]
            grp['count'] += 1
            grp['files'].append({
                'source': entry.source,
                'destination': entry.destination,
            })
        report['group_details'] = dict(group_details)

    return report


def save_report(report: dict, filepath: str) -> None:
    """
    Save a report dictionary to a JSON file (atomic write).

    Args:
        report: Report dict from generate_report().
        filepath: Output JSON file path.
    """
    path = Path(filepath)
    # Validate path
    if '..' in path.parts:
        raise ValueError("Path traversal detected in report path")

    path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write: temp file + rename
    tmp_path = path.parent / f".tmp_{uuid.uuid4().hex}.json"
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        tmp_path.replace(path)
    except BaseException:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


# =============================================================================
# Folder tree preview (for UI display)
# =============================================================================

def get_folder_preview(plan: List[ExportPlan]) -> dict:
    """
    Build a nested dictionary representing the folder tree of the export plan.
    Useful for displaying a tree view in the GUI.

    Args:
        plan: Export plan from build_export_plan().

    Returns:
        Nested dict structure. Leaf nodes have key '_files' with a list of
        filenames. Example:
        {
            'NGC7000': {
                'LIGHT': {
                    'Ha': {'_files': ['frame_001.fits', 'frame_002.fits']},
                    'OIII': {'_files': ['frame_001.fits']},
                },
                'DARK': {
                    '300s_-10C': {'_files': ['dark_001.fits']},
                },
                '_files': [],
            }
        }
    """
    if not plan:
        return {}

    # Find common root prefix
    all_dests = [Path(e.destination) for e in plan]
    try:
        common_root = Path(os.path.commonpath([str(d) for d in all_dests]))
    except ValueError:
        # Different drives on Windows
        common_root = all_dests[0].parent

    tree = {}
    for entry in plan:
        dest = Path(entry.destination)
        try:
            rel = dest.relative_to(common_root)
        except ValueError:
            rel = Path(dest.name)

        parts = list(rel.parts)
        filename = parts[-1]
        folder_parts = parts[:-1]

        # Navigate/create tree structure
        node = tree
        for part in folder_parts:
            if part not in node:
                node[part] = {}
            node = node[part]

        # Add file to leaf node
        if '_files' not in node:
            node['_files'] = []
        node['_files'].append(filename)

    return tree


def get_plan_statistics(plan: List[ExportPlan]) -> dict:
    """
    Compute statistics from an export plan for display purposes.

    Args:
        plan: Export plan from build_export_plan().

    Returns:
        Dict with counts per image type, per group, total size estimate, etc.
    """
    stats = {
        'total_files': len(plan),
        'by_type': defaultdict(int),
        'by_group': defaultdict(int),
        'unique_destinations': set(),
        'total_size_bytes': 0,
    }

    for entry in plan:
        stats['by_type'][entry.image_type] += 1
        stats['by_group'][entry.group] += 1
        stats['unique_destinations'].add(str(Path(entry.destination).parent))

        # Estimate size from source file
        try:
            stats['total_size_bytes'] += os.path.getsize(entry.source)
        except OSError:
            pass

    stats['by_type'] = dict(stats['by_type'])
    stats['by_group'] = dict(stats['by_group'])
    stats['unique_folders'] = len(stats['unique_destinations'])
    stats['total_size_gb'] = round(stats['total_size_bytes'] / (1024 ** 3), 2)
    del stats['unique_destinations']  # Not JSON-serializable

    return stats


# =============================================================================
# Convenience / high-level workflow
# =============================================================================

def wbpp_export(source_folders: List[str],
                export_root: str,
                mode: str = 'copy',
                template: Optional[str] = None,
                recursive: bool = True,
                include_calibrations: bool = True,
                temp_tolerance: float = 2.0,
                save_report_path: Optional[str] = None,
                progress_callback: Optional[Callable] = None) -> ExportResult:
    """
    High-level convenience function: scan, validate, plan, execute, report.

    This is the main entry point for programmatic use and GUI integration.

    Args:
        source_folders: Directories to scan for FITS/XISF files.
        export_root: Root directory for the WBPP folder structure output.
        mode: Export mode ('copy', 'symlink', 'move', 'list').
        template: Optional custom folder template (uses smart defaults if None).
        recursive: Recurse into subdirectories when scanning.
        include_calibrations: Include calibration frames in the export.
        temp_tolerance: Temperature tolerance for dark matching (Celsius).
        save_report_path: Optional path to save the JSON report.
        progress_callback: Optional callback(current, total, message).

    Returns:
        ExportResult with counts, warnings, and errors.
    """
    # Validate export root
    root_path = Path(export_root)
    if '..' in root_path.parts:
        raise ValueError("Export root contains path traversal ('..') components")

    # Phase 1: Scan
    if progress_callback:
        progress_callback(0, 100, "Phase 1/4: Scanning files...")
    files = scan_files(source_folders, recursive=recursive, callback=progress_callback)

    if not files:
        return ExportResult(
            total_files=0, copied_files=0, failed_files=0,
            warnings=["No supported files found in the specified folders"],
            export_path=str(export_root),
        )

    # Phase 2: Validate
    if progress_callback:
        progress_callback(0, 100, "Phase 2/4: Validating calibration sets...")
    validation_warnings = validate_export(files, temp_tolerance=temp_tolerance)

    # Phase 3: Build plan
    if progress_callback:
        progress_callback(0, 100, "Phase 3/4: Building export plan...")
    plan = build_export_plan(
        files, export_root, template=template,
        include_calibrations=include_calibrations,
    )

    # Phase 4: Execute
    if progress_callback:
        progress_callback(0, len(plan), "Phase 4/4: Exporting files...")
    result = execute_export(plan, mode=mode, callback=progress_callback)
    result.warnings = validation_warnings
    result.export_path = str(export_root)

    # Save report if requested
    if save_report_path:
        try:
            report = generate_report(result, export_root, plan, validation_warnings)
            save_report(report, save_report_path)
            logger.info("Export report saved to %s", save_report_path)
        except Exception as e:
            logger.warning("Failed to save export report: %s", e)
            result.errors.append(f"Report save failed: {e}")

    return result
