#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - MOUNT TRACKING ANALYZER
================================================================================
Analyzes MountMonitor tracking data: stats, target segments, periodic error,
time stability, environment correlation, and quality rating.
================================================================================
"""

import math
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def _get_db():
    from core.database import get_db
    return get_db()


def get_mount_sessions() -> List[Dict[str, Any]]:
    """Get all mount sessions for selection."""
    db = _get_db()
    results = []
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, session_id, log_file_path, mount_source, mount_version,
                   mount_name, mount_location, mount_firmware,
                   total_samples, tracking_samples, num_segments, created_at
            FROM mount_sessions
            ORDER BY created_at DESC
        """)
        for row in cursor.fetchall():
            results.append(dict(row))
    return results


def get_tracking_stats(session_id: int) -> Dict[str, Any]:
    """Get global tracking statistics for a session."""
    db = _get_db()
    result = {
        'total_samples': 0,
        'tracking_samples': 0,
        'tracking_pct': 0.0,
        'ra_stdev_mean': None,
        'dec_stdev_mean': None,
        'ra_dev_rms': None,
        'dec_dev_rms': None,
        'ra_dev_min': None,
        'ra_dev_max': None,
        'dec_dev_min': None,
        'dec_dev_max': None,
    }

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Total samples
        cursor.execute(
            "SELECT COUNT(*) FROM mount_tracking_data WHERE session_id = ?",
            (session_id,))
        result['total_samples'] = cursor.fetchone()[0]

        if result['total_samples'] == 0:
            return result

        # Tracking samples only
        cursor.execute("""
            SELECT COUNT(*),
                   AVG(ra_stdev), AVG(dec_stdev),
                   MIN(ra_dev_arcsec), MAX(ra_dev_arcsec),
                   MIN(dec_dev_arcsec), MAX(dec_dev_arcsec)
            FROM mount_tracking_data
            WHERE session_id = ? AND status = 'TRACKING'
        """, (session_id,))
        row = cursor.fetchone()
        if row and row[0]:
            result['tracking_samples'] = row[0]
            result['tracking_pct'] = (row[0] / result['total_samples']) * 100.0
            result['ra_stdev_mean'] = _round(row[1], 3)
            result['dec_stdev_mean'] = _round(row[2], 3)
            result['ra_dev_min'] = _round(row[3], 3)
            result['ra_dev_max'] = _round(row[4], 3)
            result['dec_dev_min'] = _round(row[5], 3)
            result['dec_dev_max'] = _round(row[6], 3)

        # RMS of deviations
        cursor.execute("""
            SELECT AVG(ra_dev_arcsec * ra_dev_arcsec),
                   AVG(dec_dev_arcsec * dec_dev_arcsec)
            FROM mount_tracking_data
            WHERE session_id = ? AND status = 'TRACKING'
        """, (session_id,))
        row = cursor.fetchone()
        if row and row[0] is not None:
            result['ra_dev_rms'] = _round(math.sqrt(row[0]), 3)
            result['dec_dev_rms'] = _round(math.sqrt(row[1]), 3) if row[1] else None

    return result


def get_target_segments(session_id: int) -> List[Dict[str, Any]]:
    """Get per-target-segment statistics."""
    db = _get_db()
    results = []

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT target_segment,
                   COUNT(*) as total,
                   SUM(CASE WHEN status = 'TRACKING' THEN 1 ELSE 0 END) as tracking,
                   AVG(CASE WHEN status = 'TRACKING' THEN ra_hours END) as avg_ra,
                   AVG(CASE WHEN status = 'TRACKING' THEN dec_degrees END) as avg_dec,
                   AVG(CASE WHEN status = 'TRACKING' THEN ra_stdev END) as avg_ra_stdev,
                   AVG(CASE WHEN status = 'TRACKING' THEN dec_stdev END) as avg_dec_stdev,
                   AVG(CASE WHEN status = 'TRACKING' THEN ra_dev_arcsec * ra_dev_arcsec END) as ra_dev_sq,
                   AVG(CASE WHEN status = 'TRACKING' THEN dec_dev_arcsec * dec_dev_arcsec END) as dec_dev_sq,
                   MIN(CASE WHEN status = 'TRACKING' THEN ra_dev_arcsec END) as ra_min,
                   MAX(CASE WHEN status = 'TRACKING' THEN ra_dev_arcsec END) as ra_max,
                   MIN(CASE WHEN status = 'TRACKING' THEN dec_dev_arcsec END) as dec_min,
                   MAX(CASE WHEN status = 'TRACKING' THEN dec_dev_arcsec END) as dec_max,
                   MIN(timestamp) as first_ts,
                   MAX(timestamp) as last_ts
            FROM mount_tracking_data
            WHERE session_id = ?
            GROUP BY target_segment
            ORDER BY target_segment
        """, (session_id,))

        for row in cursor.fetchall():
            tracking = row['tracking'] or 0
            seg = {
                'segment': row['target_segment'],
                'total_samples': row['total'],
                'tracking_samples': tracking,
                'avg_ra_hours': _round(row['avg_ra'], 4),
                'avg_dec_degrees': _round(row['avg_dec'], 4),
                'ra_stdev_mean': _round(row['avg_ra_stdev'], 3),
                'dec_stdev_mean': _round(row['avg_dec_stdev'], 3),
                'ra_rms': _round(math.sqrt(row['ra_dev_sq']), 3) if row['ra_dev_sq'] else None,
                'dec_rms': _round(math.sqrt(row['dec_dev_sq']), 3) if row['dec_dev_sq'] else None,
                'ra_range': _round((row['ra_max'] or 0) - (row['ra_min'] or 0), 3),
                'dec_range': _round((row['dec_max'] or 0) - (row['dec_min'] or 0), 3),
                'first_timestamp': row['first_ts'],
                'last_timestamp': row['last_ts'],
            }

            # Format RA/DEC for display
            if seg['avg_ra_hours'] is not None:
                seg['ra_display'] = _format_ra(seg['avg_ra_hours'])
            else:
                seg['ra_display'] = '-'
            if seg['avg_dec_degrees'] is not None:
                seg['dec_display'] = _format_dec(seg['avg_dec_degrees'])
            else:
                seg['dec_display'] = '-'

            results.append(seg)

    return results


def get_periodic_error(session_id: int) -> List[Dict[str, Any]]:
    """Get FFT periodic error peaks, latest per axis."""
    db = _get_db()
    results = []

    with db.get_connection() as conn:
        cursor = conn.cursor()
        # Get latest FFT entry per axis
        cursor.execute("""
            SELECT axis, sample_rate, num_bins,
                   peak1_freq, peak1_period, peak1_amp,
                   peak2_freq, peak2_period, peak2_amp,
                   peak3_freq, peak3_period, peak3_amp,
                   timestamp
            FROM mount_fft_data
            WHERE session_id = ?
            ORDER BY timestamp DESC
        """, (session_id,))

        seen_axes = set()
        for row in cursor.fetchall():
            axis = row['axis']
            if axis in seen_axes:
                continue
            seen_axes.add(axis)
            results.append({
                'axis': axis,
                'sample_rate': _round(row['sample_rate'], 2),
                'num_bins': row['num_bins'],
                'peak1_freq': row['peak1_freq'],
                'peak1_period': _round(row['peak1_period'], 1),
                'peak1_amp': _round(row['peak1_amp'], 3),
                'peak2_freq': row['peak2_freq'],
                'peak2_period': _round(row['peak2_period'], 1),
                'peak2_amp': _round(row['peak2_amp'], 3),
                'peak3_freq': row['peak3_freq'],
                'peak3_period': _round(row['peak3_period'], 1),
                'peak3_amp': _round(row['peak3_amp'], 3),
                'timestamp': row['timestamp'],
            })

    return results


def get_time_stability(session_id: int) -> Dict[str, Any]:
    """Get PC-Mount time synchronization statistics."""
    db = _get_db()
    result = {
        'samples': 0,
        'pc_mount_diff_mean': None,
        'pc_mount_diff_stdev': None,
        'pc_loop_mean': None,
        'pc_loop_max': None,
        'mount_loop_mean': None,
        'mount_loop_max': None,
    }

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*),
                   AVG(pc_mount_diff_ms),
                   AVG(pc_loop_ms), MAX(pc_loop_ms),
                   AVG(mount_loop_ms), MAX(mount_loop_ms)
            FROM mount_time_data
            WHERE session_id = ?
        """, (session_id,))
        row = cursor.fetchone()
        if row and row[0]:
            result['samples'] = row[0]
            result['pc_mount_diff_mean'] = _round(row[1], 1)
            result['pc_loop_mean'] = _round(row[2], 1)
            result['pc_loop_max'] = _round(row[3], 1)
            result['mount_loop_mean'] = _round(row[4], 1)
            result['mount_loop_max'] = _round(row[5], 1)

    return result


def get_environment_data(session_id: int) -> List[Dict[str, Any]]:
    """Get environment data for correlation analysis."""
    db = _get_db()
    results = []

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, temp_ext, pressure, temp_int,
                   tracking_rate, meridian_flip_min, pier_side,
                   align_stars, align_rms, polar_error
            FROM mount_environment_data
            WHERE session_id = ?
            ORDER BY timestamp
        """, (session_id,))
        for row in cursor.fetchall():
            results.append(dict(row))

    return results


def get_tracking_timeline(session_id: int, tracking_only: bool = True) -> Dict[str, List]:
    """Get tracking data for timeline chart. Returns lists for plotting."""
    db = _get_db()
    data = {
        'timestamps': [],
        'ra_dev': [],
        'dec_dev': [],
        'segments': [],
    }

    with db.get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT timestamp, ra_dev_arcsec, dec_dev_arcsec, target_segment
            FROM mount_tracking_data
            WHERE session_id = ?
        """
        if tracking_only:
            query += " AND status = 'TRACKING'"
        query += " ORDER BY timestamp"

        cursor.execute(query, (session_id,))
        for row in cursor.fetchall():
            data['timestamps'].append(row['timestamp'])
            data['ra_dev'].append(row['ra_dev_arcsec'])
            data['dec_dev'].append(row['dec_dev_arcsec'])
            data['segments'].append(row['target_segment'])

    return data


def get_quality_rating(session_id: int) -> Dict[str, Any]:
    """
    Compute overall tracking quality rating (A-F).
    Based on RMS deviation thresholds:
      A: < 0.5"    (excellent)
      B: < 1.0"    (good)
      C: < 2.0"    (fair)
      D: < 5.0"    (poor)
      F: >= 5.0"   (very poor)
    """
    stats = get_tracking_stats(session_id)

    ra_rms = stats.get('ra_dev_rms')
    dec_rms = stats.get('dec_dev_rms')

    if ra_rms is None or dec_rms is None:
        return {'grade': '-', 'total_rms': None, 'description_en': 'No data', 'description_fr': 'Aucune donnée'}

    total_rms = math.sqrt(ra_rms ** 2 + dec_rms ** 2)

    if total_rms < 0.5:
        grade = 'A'
        desc_en = 'Excellent tracking'
        desc_fr = 'Suivi excellent'
    elif total_rms < 1.0:
        grade = 'B'
        desc_en = 'Good tracking'
        desc_fr = 'Bon suivi'
    elif total_rms < 2.0:
        grade = 'C'
        desc_en = 'Fair tracking'
        desc_fr = 'Suivi correct'
    elif total_rms < 5.0:
        grade = 'D'
        desc_en = 'Poor tracking'
        desc_fr = 'Suivi médiocre'
    else:
        grade = 'F'
        desc_en = 'Very poor tracking'
        desc_fr = 'Très mauvais suivi'

    return {
        'grade': grade,
        'total_rms': _round(total_rms, 3),
        'ra_rms': ra_rms,
        'dec_rms': dec_rms,
        'description_en': desc_en,
        'description_fr': desc_fr,
    }


# =============================================================================
# Formatting helpers
# =============================================================================

def _round(value, digits):
    """Safe rounding."""
    if value is None:
        return None
    return round(value, digits)


def _format_ra(hours: float) -> str:
    """Format RA in hours to HH:MM:SS string."""
    if hours is None:
        return '-'
    h = int(hours)
    m = int((hours - h) * 60)
    s = (hours - h - m / 60.0) * 3600.0
    return f"{h:02d}h{m:02d}m{s:04.1f}s"


def _format_dec(degrees: float) -> str:
    """Format DEC in degrees to +DD:MM:SS string."""
    if degrees is None:
        return '-'
    sign = '+' if degrees >= 0 else '-'
    d_abs = abs(degrees)
    d = int(d_abs)
    m = int((d_abs - d) * 60)
    s = (d_abs - d - m / 60.0) * 3600.0
    return f"{sign}{d:02d}°{m:02d}'{s:04.1f}\""
