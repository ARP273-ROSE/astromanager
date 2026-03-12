#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - MOUNTMONITOR LOG PARSER
================================================================================
Parses MountMonitor .dat/.dti/.sei/.fft/.log/.env log files.
Extracts mount tracking data, time sync, FFT periodic error, and environment.
Supports target segmentation by RA/DEC jumps and cos(dec) correction.
================================================================================
"""

import re
import math
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from parsers.base_parser import (
    ParseResult,
    ParsedMountTracking,
    ParsedMountTime,
    ParsedMountFFT,
    ParsedMountEnvironment,
)

logger = logging.getLogger(__name__)

# Header signature for MountMonitor files
_HEADER_SIGNATURE = "MountMonitor"
_FILENAME_PATTERN = re.compile(r'^MountMonitor_\d{8}-\d{6}\.')

# Thresholds for target segmentation
_RA_JUMP_THRESHOLD_HOURS = 0.25   # 0.25h = 15 arcmin
_DEC_JUMP_THRESHOLD_DEG = 2.0     # 2 degrees


def can_parse(file_path: str) -> bool:
    """Check if file is a MountMonitor log file (.dat primary)."""
    p = Path(file_path)
    if p.suffix.lower() not in ('.dat', '.dti', '.sei', '.fft', '.log', '.env'):
        return False
    if not _FILENAME_PATTERN.match(p.name):
        return False
    # Verify header for .dat files
    if p.suffix.lower() == '.dat':
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                first_line = f.readline()
                return first_line.startswith(_HEADER_SIGNATURE)
        except Exception:
            return False
    return True


def parse_mountmonitor(dat_path: str) -> ParseResult:
    """
    Parse a MountMonitor .dat file and associated companion files.

    Args:
        dat_path: Path to the .dat file (primary mount data)

    Returns:
        ParseResult with mount tracking, time, FFT, and environment data
    """
    result = ParseResult(log_file_path=dat_path)
    result.mount_source = 'mountmonitor'
    p = Path(dat_path)

    # Parse main .dat file
    _parse_dat(p, result)

    # Find and parse companion files with same timestamp stem
    stem = p.stem  # e.g. MountMonitor_20260301-214449
    parent = p.parent

    dti_path = parent / f"{stem}.dti"
    if dti_path.exists():
        _parse_dti(dti_path, result)

    fft_path = parent / f"{stem}.fft"
    if fft_path.exists():
        _parse_fft(fft_path, result)

    env_path = parent / f"{stem}.env"
    if env_path.exists():
        _parse_env(env_path, result)

    log_path = parent / f"{stem}.log"
    if log_path.exists():
        _parse_log(log_path, result)

    return result


# =============================================================================
# Coordinate parsing helpers
# =============================================================================

def _parse_ra_hms(s: str) -> Optional[float]:
    """Parse RA string 'hh:mm:ss.dd' to decimal hours."""
    s = s.strip()
    if not s:
        return None
    try:
        parts = s.split(':')
        if len(parts) != 3:
            return None
        h = int(parts[0])
        m = int(parts[1])
        sec = float(parts[2])
        return h + m / 60.0 + sec / 3600.0
    except (ValueError, IndexError):
        return None


def _parse_dec_dms(s: str) -> Optional[float]:
    """Parse DEC string '+dd:mm:ss.d' to decimal degrees."""
    s = s.strip()
    if not s:
        return None
    try:
        sign = 1
        if s.startswith('-'):
            sign = -1
            s = s[1:]
        elif s.startswith('+'):
            s = s[1:]
        parts = s.split(':')
        if len(parts) != 3:
            return None
        d = int(parts[0])
        m = int(parts[1])
        sec = float(parts[2])
        return sign * (d + m / 60.0 + sec / 3600.0)
    except (ValueError, IndexError):
        return None


def _safe_float(s: str) -> Optional[float]:
    """Parse float, return None on failure."""
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _safe_int(s: str) -> Optional[int]:
    """Parse int, return None on failure."""
    s = s.strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


# =============================================================================
# .dat file parser (main tracking data)
# =============================================================================

def _parse_dat(path: Path, result: ParseResult):
    """Parse the main .dat tracking data file."""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception as e:
        result.parse_errors.append(f"Failed to read .dat file: {e}")
        logger.error(f"Failed to read {path}: {e}")
        return

    if not lines:
        return

    # Parse header (line 0)
    header_line = lines[0].strip()
    version_match = re.search(r'\(v\.([\d.]+)\)', header_line)
    if version_match:
        result.mount_version = version_match.group(1)

    # Parse metadata lines (Location, Mount, etc.)
    # Use raw line (not stripped) for tab-split to handle empty values
    data_start = 0
    for i, line in enumerate(lines[1:20], start=1):
        stripped = line.strip()
        parts = line.rstrip('\n\r').split('\t', 1)
        value = parts[1].strip() if len(parts) > 1 else ''
        if stripped.startswith('Location:'):
            result.mount_location = value or None
        elif stripped.startswith('Mount:') and not stripped.startswith('Mount ID:'):
            result.mount_name = value or None
        elif stripped.startswith('Firmware:'):
            result.mount_firmware = value or None
        elif stripped.startswith('RAW Mount time'):
            # This is the column header line
            data_start = i + 1
            break

    if data_start == 0:
        result.parse_errors.append("Could not find column header in .dat file")
        return

    # Parse data lines
    raw_samples = []
    for line in lines[data_start:]:
        parts = line.rstrip('\n\r').split('\t')
        if len(parts) < 8:
            continue

        timestamp = parts[1].strip()  # Mount time (column 1)
        ra_str = parts[3].strip()     # RA filtered (column 3)
        ra_stdev_str = parts[4].strip()  # RA StDev (column 4)
        dec_str = parts[6].strip()    # DEC filtered (column 6)
        dec_stdev_str = parts[7].strip()  # DEC StDev (column 7)

        # Status is the last non-empty column
        status = parts[-1].strip() if parts[-1].strip() else ''

        ra_hours = _parse_ra_hms(ra_str)
        dec_deg = _parse_dec_dms(dec_str)
        ra_stdev = _safe_float(ra_stdev_str)
        dec_stdev = _safe_float(dec_stdev_str)

        if ra_hours is None or dec_deg is None:
            continue

        # RA/DEC axis positions (columns 12, 8)
        ra_axis = _safe_float(parts[12].strip()) if len(parts) > 12 else None
        dec_axis = _safe_float(parts[8].strip()) if len(parts) > 8 else None

        sample = ParsedMountTracking(
            timestamp=timestamp,
            ra_hours=ra_hours,
            dec_degrees=dec_deg,
            ra_stdev=ra_stdev or 0.0,
            dec_stdev=dec_stdev or 0.0,
            status=status,
            ra_axis_pos=ra_axis,
            dec_axis_pos=dec_axis,
        )
        raw_samples.append(sample)

    if not raw_samples:
        return

    # Segment by target (detect RA/DEC jumps)
    _segment_targets(raw_samples)

    # Compute deviations relative to median per segment (TRACKING only)
    _compute_deviations(raw_samples)

    result.mount_tracking_data = raw_samples
    result.mount_num_segments = max(s.target_segment for s in raw_samples) + 1

    tracking_count = sum(1 for s in raw_samples if s.status == 'TRACKING')
    logger.info(f"Parsed .dat: {len(raw_samples)} samples, "
                f"{tracking_count} tracking, {result.mount_num_segments} segments")


def _segment_targets(samples: List[ParsedMountTracking]):
    """Detect target changes by RA/DEC jumps and assign segment IDs."""
    if not samples:
        return

    segment = 0
    samples[0].target_segment = segment
    prev_ra = samples[0].ra_hours
    prev_dec = samples[0].dec_degrees

    for i in range(1, len(samples)):
        s = samples[i]
        ra_diff = abs(s.ra_hours - prev_ra)
        # Handle RA wraparound (0h/24h boundary)
        if ra_diff > 12:
            ra_diff = 24 - ra_diff
        dec_diff = abs(s.dec_degrees - prev_dec)

        if ra_diff > _RA_JUMP_THRESHOLD_HOURS or dec_diff > _DEC_JUMP_THRESHOLD_DEG:
            segment += 1
        s.target_segment = segment
        prev_ra = s.ra_hours
        prev_dec = s.dec_degrees


def _compute_deviations(samples: List[ParsedMountTracking]):
    """
    Compute RA/DEC deviations in arcseconds relative to segment median.
    Applies cos(dec) correction on RA deviations.
    Only computed for TRACKING samples.
    """
    # Group tracking samples by segment
    from collections import defaultdict
    segments = defaultdict(list)
    for s in samples:
        if s.status == 'TRACKING':
            segments[s.target_segment].append(s)

    for seg_id, seg_samples in segments.items():
        if not seg_samples:
            continue

        # Compute median RA and DEC for this segment
        ra_values = sorted(s.ra_hours for s in seg_samples)
        dec_values = sorted(s.dec_degrees for s in seg_samples)
        n = len(ra_values)
        median_ra = ra_values[n // 2] if n % 2 else (ra_values[n // 2 - 1] + ra_values[n // 2]) / 2
        median_dec = dec_values[n // 2] if n % 2 else (dec_values[n // 2 - 1] + dec_values[n // 2]) / 2

        cos_dec = math.cos(math.radians(median_dec))
        if cos_dec < 0.01:
            cos_dec = 0.01  # Safety clamp near poles

        for s in seg_samples:
            # RA deviation in arcseconds with cos(dec) correction
            # 1 hour of RA = 15 degrees = 54000 arcseconds
            ra_diff_hours = s.ra_hours - median_ra
            s.ra_deviation_arcsec = ra_diff_hours * 54000.0 * cos_dec
            # DEC deviation in arcseconds
            dec_diff_deg = s.dec_degrees - median_dec
            s.dec_deviation_arcsec = dec_diff_deg * 3600.0

    # Non-tracking samples get zero deviation
    for s in samples:
        if s.status != 'TRACKING':
            s.ra_deviation_arcsec = 0.0
            s.dec_deviation_arcsec = 0.0


# =============================================================================
# .dti file parser (time synchronization data)
# =============================================================================

def _parse_dti(path: Path, result: ParseResult):
    """Parse the .dti time data file."""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception as e:
        result.parse_errors.append(f"Failed to read .dti file: {e}")
        return

    # Find data start (after column header)
    data_start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('Mount time'):
            data_start = i + 1
            break

    for line in lines[data_start:]:
        parts = line.rstrip('\n\r').split('\t')
        if len(parts) < 4:
            continue

        timestamp = parts[0].strip()
        if not timestamp:
            continue

        sample = ParsedMountTime(
            timestamp=timestamp,
            pc_mount_diff_ms=_safe_float(parts[1]) if len(parts) > 1 else None,
            pc_loop_ms=_safe_float(parts[2]) if len(parts) > 2 else None,
            mount_loop_ms=_safe_float(parts[3]) if len(parts) > 3 else None,
            ntp_diff_ms=_safe_float(parts[4]) if len(parts) > 4 else None,
        )
        result.mount_time_data.append(sample)

    logger.info(f"Parsed .dti: {len(result.mount_time_data)} time samples")


# =============================================================================
# .fft file parser (periodic error analysis)
# =============================================================================

def _parse_fft(path: Path, result: ParseResult):
    """Parse the .fft periodic error file."""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception as e:
        result.parse_errors.append(f"Failed to read .fft file: {e}")
        return

    # Find data start (after column header)
    data_start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('Timestamp'):
            data_start = i + 1
            break

    for line in lines[data_start:]:
        parts = line.rstrip('\n\r').split('\t')
        if len(parts) < 13:
            continue

        timestamp = parts[0].strip()
        if not timestamp:
            continue

        sample = ParsedMountFFT(
            timestamp=timestamp,
            axis=parts[1].strip(),
            sample_rate=_safe_float(parts[2]),
            num_bins=_safe_int(parts[3]),
            peak1_freq=_safe_float(parts[4]),
            peak1_period=_safe_float(parts[5]),
            peak1_amp=_safe_float(parts[6]),
            peak2_freq=_safe_float(parts[7]),
            peak2_period=_safe_float(parts[8]),
            peak2_amp=_safe_float(parts[9]),
            peak3_freq=_safe_float(parts[10]),
            peak3_period=_safe_float(parts[11]),
            peak3_amp=_safe_float(parts[12]),
        )
        result.mount_fft_data.append(sample)

    logger.info(f"Parsed .fft: {len(result.mount_fft_data)} FFT samples")


# =============================================================================
# .env file parser (environment data)
# =============================================================================

def _parse_env(path: Path, result: ParseResult):
    """Parse the .env environment data file."""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception as e:
        result.parse_errors.append(f"Failed to read .env file: {e}")
        return

    # Find data start (after column header)
    data_start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('Timestamp'):
            data_start = i + 1
            break

    for line in lines[data_start:]:
        parts = line.rstrip('\n\r').split('\t')
        if len(parts) < 2:
            continue

        timestamp = parts[0].strip()
        if not timestamp:
            continue

        # All fields may be empty
        sample = ParsedMountEnvironment(
            timestamp=timestamp,
            temp_ext=_safe_float(parts[1]) if len(parts) > 1 else None,
            pressure=_safe_float(parts[2]) if len(parts) > 2 else None,
            temp_int=_safe_float(parts[3]) if len(parts) > 3 else None,
            tracking_rate=parts[5].strip() if len(parts) > 5 and parts[5].strip() else None,
            meridian_flip_min=_safe_float(parts[6]) if len(parts) > 6 else None,
            pier_side=parts[7].strip() if len(parts) > 7 and parts[7].strip() else None,
            align_stars=_safe_int(parts[8]) if len(parts) > 8 else None,
            align_rms=_safe_float(parts[9]) if len(parts) > 9 else None,
            polar_error=_safe_float(parts[10]) if len(parts) > 10 else None,
        )
        result.mount_environment_data.append(sample)

    logger.info(f"Parsed .env: {len(result.mount_environment_data)} env samples")


# =============================================================================
# .log file parser (session event log)
# =============================================================================

def _parse_log(path: Path, result: ParseResult):
    """Parse the .log event file for mount metadata."""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception as e:
        result.parse_errors.append(f"Failed to read .log file: {e}")
        return

    for line in lines:
        stripped = line.strip()
        # Extract mount info from log entries
        m = re.search(r'Mount:\s*(.+?)\s*\|', stripped)
        if m and not result.mount_name:
            result.mount_name = m.group(1).strip()

        m = re.search(r'FW:\s*([\d.]+)', stripped)
        if m and not result.mount_firmware:
            result.mount_firmware = m.group(1).strip()

        m = re.search(r'Protocol:\s*(\w+)', stripped)
        if m:
            pass  # Protocol info available but not stored

    logger.info(f"Parsed .log for metadata")
