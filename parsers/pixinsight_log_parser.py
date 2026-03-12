#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - PIXINSIGHT LOG PARSER
================================================================================
Complete parser for PixInsight WBPP/FBP log files.
Extracts: SubframeSelector metrics, ImageIntegration data, calibration groups,
frame weights, pixel rejection stats, registration results, and timing.
================================================================================
"""

import os
import re
import logging
from typing import Optional, List, Tuple

from parsers.base_parser import (
    ParseResult, ParsedSubframeMetric, ParsedFrameWeight,
    ParsedIntegration, ParsedCalibrationGroup
)

logger = logging.getLogger(__name__)

# Regex to strip timestamp prefix: [2025-11-21 08:47:14]
_RE_TIMESTAMP = re.compile(r'^\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s*')

# LIGHT filename pattern:
# LIGHT_<Target>_<Date>_<Time>_<Filter>_<Binning>_<Duration>s_<Angle>_<Temp>_<Camera>_<Seq>
_RE_LIGHT_FILENAME = re.compile(
    r'LIGHT_'
    r'(?P<target>.+?)_'
    r'(?P<date>\d{4}-\d{2}-\d{2})_'
    r'(?P<time>\d{2}-\d{2}-\d{2})_'
    r'(?P<filter>[A-Za-z0-9]+)_'
    r'(?P<binning>\d+)x\d+_'
    r'(?P<duration>[\d.]+)s_'
    r'(?P<angle>[^_]*)_'
    r'(?P<temp>-?[\d.]+)_'
    r'(?P<camera>.+?)_'
    r'(?P<seq>\d+)'
)

# FLAT filename pattern
_RE_FLAT_FILENAME = re.compile(
    r'FLAT_+_?'
    r'(?P<date>\d{4}-\d{2}-\d{2})_'
    r'(?P<time>\d{2}-\d{2}-\d{2})_'
    r'(?P<filter>[A-Za-z0-9]+)_'
    r'(?P<binning>\d+)x\d+_'
    r'(?P<duration>[\d.]+)s_'
)


def _strip_timestamp(line: str) -> Tuple[str, Optional[str]]:
    """Strip [timestamp] prefix from log line, return (content, timestamp)."""
    m = _RE_TIMESTAMP.match(line)
    if m:
        return line[m.end():], m.group(1)
    return line, None


def _parse_light_filename(filename: str) -> dict:
    """Extract metadata from a LIGHT filename pattern."""
    basename = os.path.basename(filename)
    m = _RE_LIGHT_FILENAME.search(basename)
    if not m:
        return {}
    result = {}
    result['target_name'] = m.group('target').replace('_', ' ').strip()
    result['filter_name'] = m.group('filter')
    try:
        result['exposure_seconds'] = float(m.group('duration'))
    except (ValueError, TypeError):
        pass
    try:
        result['temperature'] = float(m.group('temp'))
    except (ValueError, TypeError):
        pass
    result['camera'] = m.group('camera').strip()
    try:
        result['binning'] = int(m.group('binning'))
    except (ValueError, TypeError):
        pass
    try:
        result['frame_index'] = int(m.group('seq'))
    except (ValueError, TypeError):
        pass
    return result


def parse_pixinsight_log(log_path: str) -> ParseResult:
    """
    Parse a PixInsight WBPP/FBP log file and extract all available data.

    Args:
        log_path: Path to the .log file

    Returns:
        ParseResult with all extracted data
    """
    result = ParseResult(log_file_path=log_path)

    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception as e:
        result.parse_errors.append(f"Failed to read file: {e}")
        logger.error(f"Failed to read {log_path}: {e}")
        return result

    # Strip all lines and extract timestamps
    stripped = []
    for line in lines:
        content, ts = _strip_timestamp(line.rstrip('\n\r'))
        stripped.append(content)
        if ts and not result.log_timestamp:
            result.log_timestamp = ts

    _parse_header(stripped, result)
    _parse_calibration_groups(stripped, result)
    _parse_subframe_selector(stripped, result)
    _parse_frame_rejection(stripped, result)
    _parse_light_integrations(stripped, result)
    _parse_registration(stripped, result)
    _parse_timing(stripped, result)

    return result


def _parse_header(lines: List[str], result: ParseResult):
    """Parse PixInsight version and script info from header."""
    for i, line in enumerate(lines[:30]):
        # PixInsight Core 1.9.3 Lockhart (x64)
        m = re.match(r'PixInsight Core\s+([\d.]+\s+\S+)', line)
        if m:
            result.pixinsight_version = m.group(1).strip()
            continue

        # Weighted Batch Preprocessing Script 2.8.9
        m = re.match(r'(Weighted Batch Preprocessing Script|Fast Batch Preprocessing)\s+([\d.]+)', line)
        if m:
            result.script_name = m.group(1).strip()
            result.script_version = m.group(2).strip()
            continue


def _parse_calibration_groups(lines: List[str], result: ParseResult):
    """Parse calibration group metadata (frame counts, dimensions, filters, masters)."""
    i = 0
    while i < len(lines):
        line = lines[i]

        # Group of N <Type> frames (M active)
        m = re.match(r'Group of (\d+) (\w+) frames?\s*\((\d+) active\)', line)
        if m:
            group = ParsedCalibrationGroup()
            group.frames_total = int(m.group(1))
            group.frame_type = m.group(2)
            group.frames_active = int(m.group(3))

            # Parse subsequent lines for this group
            j = i + 1
            while j < len(lines) and j < i + 20:
                gl = lines[j].strip()
                if not gl or gl.startswith('***'):
                    break

                # SIZE  : 9576x6388
                sm = re.match(r'SIZE\s*:\s*(\d+)x(\d+)', gl)
                if sm:
                    group.image_width = int(sm.group(1))
                    group.image_height = int(sm.group(2))
                    j += 1
                    continue

                # BINNING  : 1
                bm = re.match(r'BINNING\s*:\s*(\d+)', gl)
                if bm:
                    group.binning = int(bm.group(1))
                    j += 1
                    continue

                # Filter   : Ha
                fm = re.match(r'Filter\s*:\s*(\S+)', gl)
                if fm:
                    group.filter_name = fm.group(1)
                    j += 1
                    continue

                # Exposure : 300.00s  OR  Exposure : [120.00s, 180.00s]
                em = re.match(r'Exposure\s*:\s*\[?([^\]]+)\]?', gl)
                if em:
                    exp_str = em.group(1).strip()
                    if ',' in exp_str:
                        group.exposure_range = exp_str
                    else:
                        exp_str = exp_str.rstrip('s')
                        try:
                            group.exposure_seconds = float(exp_str)
                        except ValueError:
                            group.exposure_range = exp_str
                    j += 1
                    continue

                # Keywords : [NUIT: 4]
                km = re.match(r'Keywords\s*:\s*\[(.*)?\]', gl)
                if km:
                    group.keywords = km.group(1).strip() if km.group(1) else ''
                    j += 1
                    continue

                # Color   : mono
                cm = re.match(r'Color\s*:\s*(\S+)', gl)
                if cm:
                    group.color_mode = cm.group(1)
                    j += 1
                    continue

                # Master bias/dark/flat paths
                mb = re.match(r'Master bias:\s*(.+)', gl)
                if mb:
                    path = mb.group(1).strip()
                    if path.lower() != 'none':
                        group.master_bias_path = path
                    j += 1
                    continue

                mb = re.match(r'\s*Master dark:\s*(.+)', gl)
                if mb:
                    path = mb.group(1).strip()
                    if path.lower() != 'none':
                        group.master_dark_path = path
                    j += 1
                    continue

                mb = re.match(r'\s*Master flat:\s*(.+)', gl)
                if mb:
                    path = mb.group(1).strip()
                    if path.lower() != 'none':
                        group.master_flat_path = path
                    j += 1
                    continue

                # Applying automatic pedestal: 110 DN
                pm = re.match(r'Applying automatic pedestal:\s*([\d.]+)', gl)
                if pm:
                    group.pedestal_value = float(pm.group(1))
                    j += 1
                    continue

                j += 1

            result.calibration_groups.append(group)
        i += 1


def _parse_subframe_selector(lines: List[str], result: ParseResult):
    """
    Parse SubframeSelector per-frame metrics.

    In WBPP logs, the metric blocks appear AFTER the SubframeSelector summary,
    following [cache] entries. Format:

        A:/path/to/LIGHT_..._cc.xisf
        -----------------------------
        FWHM              :   8.349 [px]
        Eccentricity      :   0.504
        Number of stars   : 102
        PSF Signal Weight :   0.002
        PSF SNR           :   0.063
        SNR               :   0.372
        Median (ADU)      :   7.833
        MAD (ADU)         :   6.215
        Mstar (ADU)       :   4.583
        -----------------------------
    """
    i = 0

    while i < len(lines):
        line = lines[i]

        # Parse SubframeSelector summary line (can appear anywhere)
        m = re.match(r'=+\s*SubframeSelector:\s*(\d+)\s*succeeded,\s*(\d+)\s*failed,\s*(\d+)\s*skipped', line)
        if m:
            result.subframe_summary_succeeded = int(m.group(1))
            result.subframe_summary_failed = int(m.group(2))
            result.subframe_summary_skipped = int(m.group(3))
            i += 1
            continue

        # Look for filename + dashes + FWHM metrics pattern globally.
        # A file path line followed by dashes then FWHM is very specific.
        stripped = line.strip()
        if (stripped and
            i + 2 < len(lines) and
            re.match(r'^-{5,}$', lines[i + 1].strip()) and
            'FWHM' in lines[i + 2] and
            not stripped.startswith('[') and
            not stripped.startswith('*') and
            not stripped.startswith('var ') and
            not stripped.startswith('//') and
            (('/' in stripped or '\\' in stripped) or stripped.endswith('.xisf') or stripped.endswith('.fits'))):

            filename = stripped

            metric = ParsedSubframeMetric(filename=filename)

            # Parse filename for metadata
            meta = _parse_light_filename(filename)
            metric.target_name = meta.get('target_name')
            metric.filter_name = meta.get('filter_name')
            metric.exposure_seconds = meta.get('exposure_seconds')
            metric.temperature = meta.get('temperature')
            metric.camera = meta.get('camera')
            metric.binning = meta.get('binning')
            metric.frame_index = meta.get('frame_index')

            # Parse metric lines after the dashes
            j = i + 2
            while j < len(lines):
                ml = lines[j].strip()
                if not ml or re.match(r'^-{5,}$', ml):
                    break

                # FWHM              :   8.349 [px]
                vm = re.match(r'FWHM\s*:\s*([\d.]+)', ml)
                if vm:
                    metric.fwhm = float(vm.group(1))
                    j += 1
                    continue

                vm = re.match(r'Eccentricity\s*:\s*([\d.]+)', ml)
                if vm:
                    metric.eccentricity = float(vm.group(1))
                    j += 1
                    continue

                vm = re.match(r'Number of stars\s*:\s*(\d+)', ml)
                if vm:
                    metric.num_stars = int(vm.group(1))
                    j += 1
                    continue

                vm = re.match(r'PSF Signal Weight\s*:\s*([\d.]+)', ml)
                if vm:
                    metric.psf_signal_weight = float(vm.group(1))
                    j += 1
                    continue

                vm = re.match(r'PSF SNR\s*:\s*([\d.]+)', ml)
                if vm:
                    metric.psf_snr = float(vm.group(1))
                    j += 1
                    continue

                vm = re.match(r'SNR\s*:\s*([\d.]+)', ml)
                if vm:
                    metric.snr = float(vm.group(1))
                    j += 1
                    continue

                vm = re.match(r'Median \(ADU\)\s*:\s*([\d.]+)', ml)
                if vm:
                    metric.median_adu = float(vm.group(1))
                    j += 1
                    continue

                vm = re.match(r'MAD \(ADU\)\s*:\s*([\d.]+)', ml)
                if vm:
                    metric.mad_adu = float(vm.group(1))
                    j += 1
                    continue

                vm = re.match(r'Mstar \(ADU\)\s*:\s*([\d.]+)', ml)
                if vm:
                    metric.mstar_adu = float(vm.group(1))
                    j += 1
                    continue

                j += 1

            result.subframe_metrics.append(metric)
            i = j + 1
            continue

        i += 1


def _parse_frame_rejection(lines: List[str], result: ParseResult):
    """
    Parse frame rejection lines from SubframeSelector.

    Formats:
        [Frames rejection] FILENAME - WEIGHT > THRESHOLD | accepted
        [Frames rejection] FILENAME - WEIGHT < THRESHOLD | rejected
        *** Warning: frame rejected [FILENAME - WEIGHT
    """
    for line in lines:
        # Standard format: [Frames rejection] FILENAME - WEIGHT > THRESHOLD | accepted/rejected
        m = re.match(
            r'\[Frames rejection\]\s*(.+?)\s*-\s*([\d.]+)\s*[<>]?\s*([\d.]+)\s*\|\s*(\w+)',
            line
        )
        if m:
            fw = ParsedFrameWeight(
                filename=m.group(1).strip(),
                rejection_weight=float(m.group(2)),
                rejection_threshold=float(m.group(3)),
                accepted=(m.group(4).strip().lower() == 'accepted'),
            )
            result.frame_weights.append(fw)
            continue

        # Warning format: *** Warning: frame rejected [FILENAME - WEIGHT
        m = re.match(
            r'\*{3}\s*Warning:\s*frame rejected\s*\[(.+?)\s*-\s*([\d.]+)',
            line
        )
        if m:
            fw = ParsedFrameWeight(
                filename=m.group(1).strip(),
                rejection_weight=float(m.group(2)),
                accepted=False,
            )
            result.frame_weights.append(fw)


def _parse_light_integrations(lines: List[str], result: ParseResult):
    """
    Parse ImageIntegration sections for Light frames.

    Extracts: combination method, weighting mode, normalization, rejection,
    normalized weights per frame, pixel rejection counts, output estimates.
    """
    i = 0
    while i < len(lines):
        line = lines[i]

        # Detect "Begin integration of Light frames"
        if '* Begin integration of Light frames' in line:
            integration = ParsedIntegration()

            # Parse group metadata following this header
            j = i + 1
            while j < len(lines) and j < i + 15:
                gl = lines[j].strip()
                if not gl or gl.startswith('---') or gl.startswith('Rejection method'):
                    if gl.startswith('Rejection method'):
                        rm = re.match(r'Rejection method auto-selected:\s*(.+)', gl)
                        if rm:
                            integration.rejection_method = rm.group(1).strip()
                    break

                fm = re.match(r'Filter\s*:\s*(\S+)', gl)
                if fm:
                    integration.filter_name = fm.group(1)

                gm = re.match(r'Group of (\d+) Light frames?\s*\((\d+) active\)', gl)
                if gm:
                    integration.frames_total = int(gm.group(1))

                j += 1

            # Now scan forward for integration details
            k = j
            while k < len(lines) and k < j + 800:
                kl = lines[k].strip()

                # "Integration of N images:"
                im = re.match(r'Integration of (\d+) images?:', kl)
                if im:
                    integration.frames_integrated = int(im.group(1))
                    k += 1
                    # Parse integration parameters
                    while k < len(lines) and k < j + 850:
                        pl = lines[k].strip()
                        if not pl:
                            break

                        pm = re.match(r'Pixel combination\s*\.+\s*(.+)', pl)
                        if pm:
                            integration.combination_method = pm.group(1).strip()

                        pm = re.match(r'Weighting mode\s*\.+\s*(.+)', pl)
                        if pm:
                            integration.weight_mode = pm.group(1).strip()

                        pm = re.match(r'Output normalization\s*\.+\s*(.+)', pl)
                        if pm:
                            integration.normalization = pm.group(1).strip()

                        pm = re.match(r'Pixel rejection\s*\.+\s*(.+)', pl)
                        if pm:
                            integration.rejection_method = pm.group(1).strip()

                        k += 1
                    continue

                # Normalized image weights:
                if 'Normalized image weights:' in kl:
                    k += 1
                    while k < len(lines):
                        wl = lines[k].strip()
                        if not wl or (wl.startswith('Integration of') or
                                      wl.startswith('* Available')):
                            break
                        # [    1] filepath
                        wm = re.match(r'\[\s*\d+\]\s*(.+)', wl)
                        if wm:
                            fw = ParsedFrameWeight(filename=wm.group(1).strip())
                            # Next line has the weight value
                            if k + 1 < len(lines):
                                try:
                                    fw.normalized_weight = float(lines[k + 1].strip())
                                    fw.accepted = True
                                    k += 1
                                except ValueError:
                                    pass
                            integration.normalized_weights.append(fw)
                        k += 1
                    continue

                # Pixel rejection counts:
                if 'Pixel rejection counts:' in kl:
                    k += 1
                    while k < len(lines):
                        rl = lines[k].strip()

                        # Skip empty lines
                        if not rl:
                            k += 1
                            continue

                        # Parse Total line (end of section)
                        if rl.startswith('Total'):
                            tm = re.match(
                                r'Total\s*:\s*(\d+)\s+([\d.]+)%\s*\(\s*(\d+)\s*\+\s*(\d+)\s*=\s*([\d.]+)%\s*\+\s*([\d.]+)%\)',
                                rl
                            )
                            if tm:
                                integration.total_rejection_pct = float(tm.group(2))
                                integration.low_rejection_pct = float(tm.group(5))
                                integration.high_rejection_pct = float(tm.group(6))
                            k += 1
                            break

                        # End on unrelated lines
                        if rl.startswith('*') or rl.startswith('Computing') or rl.startswith('PSF'):
                            break

                        # filepath line followed by stats line
                        if not rl[0].isdigit() and not rl.startswith('['):
                            # This is a filepath
                            pr_filename = rl
                            if k + 1 < len(lines):
                                stats_line = lines[k + 1].strip()
                                # N :   1524338   2.492% (   126277 +   1398061 =   0.206% +   2.285%)
                                sm = re.match(
                                    r'\s*\d+\s*:\s*(\d+)\s+([\d.]+)%\s*\(\s*(\d+)\s*\+\s*(\d+)\s*=\s*([\d.]+)%\s*\+\s*([\d.]+)%\)',
                                    stats_line
                                )
                                if sm:
                                    pr = ParsedFrameWeight(
                                        filename=pr_filename,
                                        pixel_rejection_count=int(sm.group(1)),
                                        pixel_rejection_pct=float(sm.group(2)),
                                        low_rejection_pct=float(sm.group(5)),
                                        high_rejection_pct=float(sm.group(6))
                                    )
                                    integration.pixel_rejections.append(pr)
                                    k += 1
                        k += 1
                    continue

                # Post-integration output estimates
                # SNR estimates      : 3.9630e-01
                sm = re.match(r'SNR estimates\s*:\s*([eE\d.+-]+)', kl)
                if sm:
                    try:
                        integration.output_snr = float(sm.group(1))
                    except ValueError:
                        pass
                    k += 1
                    continue

                sm = re.match(r'PSF signal weights\s*:\s*([eE\d.+-]+)', kl)
                if sm:
                    try:
                        integration.output_psf_signal = float(sm.group(1))
                    except ValueError:
                        pass
                    k += 1
                    continue

                sm = re.match(r'Noise estimates\s*:\s*([eE\d.+-]+)', kl)
                if sm:
                    try:
                        integration.output_noise = float(sm.group(1))
                    except ValueError:
                        pass
                    k += 1
                    continue

                # PSF SNR estimates  : 2.2545e-01
                sm = re.match(r'PSF SNR estimates\s*:\s*([eE\d.+-]+)', kl)
                if sm:
                    # PSF SNR for the output — could override SNR
                    k += 1
                    continue

                # Writing master Light frame:
                if '* Writing master Light frame:' in kl:
                    if k + 1 < len(lines):
                        integration.output_file = lines[k + 1].strip()
                    k += 2
                    continue

                # End integration of Light frames
                if '* End integration of Light frames' in kl:
                    break

                k += 1

            # Compute frames_rejected
            if integration.frames_total > 0 and integration.frames_integrated > 0:
                integration.frames_rejected = (
                    integration.frames_total - integration.frames_integrated
                )

            # Only add if we have meaningful data
            if integration.frames_integrated > 0 or integration.filter_name:
                result.integrations.append(integration)

            i = k + 1
            continue

        i += 1


def _parse_registration(lines: List[str], result: ParseResult):
    """Parse StarAlignment registration summary."""
    for line in lines:
        m = re.match(r'=+\s*StarAlignment:\s*(\d+)\s*succeeded,\s*(\d+)\s*failed,\s*(\d+)\s*skipped', line)
        if m:
            result.registration_succeeded += int(m.group(1))
            result.registration_failed += int(m.group(2))
            result.registration_skipped += int(m.group(3))


def _parse_timing(lines: List[str], result: ParseResult):
    """Parse total WBPP elapsed time."""
    for line in reversed(lines):
        m = re.match(r'\*\s*WeightedBatchPreprocessing:\s*(.+)', line.strip())
        if m:
            result.total_elapsed = m.group(1).strip()
            break
        m = re.match(r'\*\s*FastBatchPreprocessing:\s*(.+)', line.strip())
        if m:
            result.total_elapsed = m.group(1).strip()
            break


def parse_log_folder(folder_path: str) -> List[ParseResult]:
    """
    Parse all PixInsight log files in a folder tree.

    Args:
        folder_path: Root folder to search for .log files

    Returns:
        List of ParseResult objects
    """
    results = []
    log_files = []

    for root, dirs, files in os.walk(folder_path):
        for f in files:
            if f.endswith('.log'):
                full_path = os.path.join(root, f)
                # Quick check: is this a PixInsight log?
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='replace') as fh:
                        head = fh.read(1024)
                        if 'PixInsight' in head:
                            log_files.append(full_path)
                except Exception:
                    continue

    logger.info(f"Found {len(log_files)} PixInsight log files in {folder_path}")

    for lf in log_files:
        try:
            result = parse_pixinsight_log(lf)
            if result.has_subframe_data or result.has_integration_data:
                results.append(result)
        except Exception as e:
            logger.error(f"Failed to parse {lf}: {e}")

    return results
