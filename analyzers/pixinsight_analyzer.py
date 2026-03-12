#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - PIXINSIGHT PROCESSING ANALYZER
================================================================================
Analysis queries for PixInsight WBPP/FBP processing data.
Reads from pixinsight_* tables to provide quality statistics,
comparisons, and trends.
================================================================================
"""

import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def _get_db():
    from core.database import get_db
    return get_db()


def get_processing_summary(session_id: int) -> Dict[str, Any]:
    """Get a global processing summary for a session.

    Returns dict with keys: pixinsight_version, script_name, script_version,
    total_subframes, subframes_succeeded, subframes_failed,
    registration_succeeded, registration_failed, total_elapsed,
    integration_count, calibration_count.
    """
    db = _get_db()
    result = {
        'pixinsight_version': None, 'script_name': None, 'script_version': None,
        'total_subframes': 0, 'subframes_succeeded': 0, 'subframes_failed': 0,
        'registration_succeeded': 0, 'registration_failed': 0,
        'total_elapsed': None, 'integration_count': 0, 'calibration_count': 0,
    }

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Session metadata
        cursor.execute("""
            SELECT pixinsight_version, script_name, script_version,
                   total_subframes, subframes_succeeded, subframes_failed,
                   registration_succeeded, registration_failed, total_elapsed
            FROM pixinsight_sessions WHERE session_id = ?
            ORDER BY id DESC LIMIT 1
        """, (session_id,))
        row = cursor.fetchone()
        if row:
            result.update({
                'pixinsight_version': row[0], 'script_name': row[1],
                'script_version': row[2], 'total_subframes': row[3] or 0,
                'subframes_succeeded': row[4] or 0, 'subframes_failed': row[5] or 0,
                'registration_succeeded': row[6] or 0, 'registration_failed': row[7] or 0,
                'total_elapsed': row[8],
            })

        # Count integrations
        cursor.execute(
            "SELECT COUNT(*) FROM pixinsight_integrations WHERE session_id = ?",
            (session_id,))
        result['integration_count'] = cursor.fetchone()[0]

        # Count calibration groups
        cursor.execute(
            "SELECT COUNT(*) FROM pixinsight_calibrations WHERE session_id = ?",
            (session_id,))
        result['calibration_count'] = cursor.fetchone()[0]

    return result


def get_subframe_quality_by_filter(session_id: int) -> List[Dict[str, Any]]:
    """Get average subframe quality metrics grouped by filter.

    Returns list of dicts with: filter_name, count, avg_fwhm, avg_eccentricity,
    avg_snr, avg_psf_snr, avg_stars, avg_median_adu, avg_mad_adu,
    min_fwhm, max_fwhm, min_snr, max_snr.
    """
    db = _get_db()
    results = []

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT filter_name,
                   COUNT(*) as cnt,
                   AVG(fwhm) as avg_fwhm,
                   AVG(eccentricity) as avg_ecc,
                   AVG(snr) as avg_snr,
                   AVG(psf_snr) as avg_psf_snr,
                   AVG(num_stars) as avg_stars,
                   AVG(median_adu) as avg_median,
                   AVG(mad_adu) as avg_mad,
                   MIN(fwhm) as min_fwhm,
                   MAX(fwhm) as max_fwhm,
                   MIN(snr) as min_snr,
                   MAX(snr) as max_snr
            FROM pixinsight_subframes
            WHERE session_id = ?
            GROUP BY filter_name
            ORDER BY filter_name
        """, (session_id,))

        for row in cursor.fetchall():
            results.append({
                'filter_name': row[0] or 'Unknown',
                'count': row[1],
                'avg_fwhm': round(row[2], 3) if row[2] else None,
                'avg_eccentricity': round(row[3], 3) if row[3] else None,
                'avg_snr': round(row[4], 3) if row[4] else None,
                'avg_psf_snr': round(row[5], 3) if row[5] else None,
                'avg_stars': int(row[6]) if row[6] else None,
                'avg_median_adu': round(row[7], 3) if row[7] else None,
                'avg_mad_adu': round(row[8], 3) if row[8] else None,
                'min_fwhm': round(row[9], 3) if row[9] else None,
                'max_fwhm': round(row[10], 3) if row[10] else None,
                'min_snr': round(row[11], 3) if row[11] else None,
                'max_snr': round(row[12], 3) if row[12] else None,
            })

    return results


def get_subframe_quality_by_target() -> List[Dict[str, Any]]:
    """Get average subframe quality grouped by target (cross-session).

    Returns list of dicts with: target_name, session_count, frame_count,
    avg_fwhm, avg_eccentricity, avg_snr, avg_stars.
    """
    db = _get_db()
    results = []

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT target_name,
                   COUNT(DISTINCT session_id) as sessions,
                   COUNT(*) as frames,
                   AVG(fwhm) as avg_fwhm,
                   AVG(eccentricity) as avg_ecc,
                   AVG(snr) as avg_snr,
                   AVG(num_stars) as avg_stars
            FROM pixinsight_subframes
            WHERE target_name IS NOT NULL AND target_name != ''
            GROUP BY target_name
            ORDER BY frames DESC
        """)

        for row in cursor.fetchall():
            results.append({
                'target_name': row[0],
                'session_count': row[1],
                'frame_count': row[2],
                'avg_fwhm': round(row[3], 3) if row[3] else None,
                'avg_eccentricity': round(row[4], 3) if row[4] else None,
                'avg_snr': round(row[5], 3) if row[5] else None,
                'avg_stars': int(row[6]) if row[6] else None,
            })

    return results


def get_frame_rejection_analysis(session_id: int) -> Dict[str, Any]:
    """Get frame acceptance/rejection statistics for a session.

    Returns dict with: total_frames, accepted_count, rejected_count,
    acceptance_rate, avg_weight_accepted, avg_weight_rejected,
    rejected_frames (list of filenames with weights).
    """
    db = _get_db()
    result = {
        'total_frames': 0, 'accepted_count': 0, 'rejected_count': 0,
        'acceptance_rate': 0.0, 'avg_weight_accepted': None,
        'avg_weight_rejected': None, 'rejected_frames': [],
    }

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Overall counts
        cursor.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN accepted = 1 THEN 1 ELSE 0 END) as acc,
                   SUM(CASE WHEN accepted = 0 THEN 1 ELSE 0 END) as rej,
                   AVG(CASE WHEN accepted = 1 THEN normalized_weight END) as avg_w_acc,
                   AVG(CASE WHEN accepted = 0 THEN normalized_weight END) as avg_w_rej
            FROM pixinsight_frame_weights
            WHERE session_id = ?
        """, (session_id,))
        row = cursor.fetchone()
        if row and row[0]:
            total = row[0]
            acc = row[1] or 0
            rej = row[2] or 0
            result.update({
                'total_frames': total,
                'accepted_count': acc,
                'rejected_count': rej,
                'acceptance_rate': round(acc / total * 100, 1) if total > 0 else 0.0,
                'avg_weight_accepted': round(row[3], 4) if row[3] else None,
                'avg_weight_rejected': round(row[4], 4) if row[4] else None,
            })

        # Rejected frame details
        cursor.execute("""
            SELECT filename, normalized_weight, rejection_weight, rejection_threshold
            FROM pixinsight_frame_weights
            WHERE session_id = ? AND accepted = 0
            ORDER BY normalized_weight ASC
        """, (session_id,))
        for row in cursor.fetchall():
            result['rejected_frames'].append({
                'filename': row[0],
                'weight': row[1],
                'rejection_weight': row[2],
                'threshold': row[3],
            })

    return result


def get_integration_quality(session_id: int) -> List[Dict[str, Any]]:
    """Get integration quality stats per filter for a session.

    Returns list of dicts with: filter_name, combination_method, weight_mode,
    rejection_method, frames_total, frames_integrated, frames_rejected,
    total_rejection_pct, output_snr, output_psf_signal, output_noise,
    output_file, frame_weights (list).
    """
    db = _get_db()
    results = []

    with db.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, filter_name, combination_method, weight_mode,
                   normalization, rejection_method, frames_total,
                   frames_integrated, frames_rejected, total_rejection_pct,
                   low_rejection_pct, high_rejection_pct, output_snr,
                   output_psf_signal, output_noise, output_file
            FROM pixinsight_integrations
            WHERE session_id = ?
            ORDER BY filter_name
        """, (session_id,))

        for row in cursor.fetchall():
            integ_id = row[0]
            integ = {
                'id': integ_id,
                'filter_name': row[1] or 'Unknown',
                'combination_method': row[2],
                'weight_mode': row[3],
                'normalization': row[4],
                'rejection_method': row[5],
                'frames_total': row[6] or 0,
                'frames_integrated': row[7] or 0,
                'frames_rejected': row[8] or 0,
                'total_rejection_pct': round(row[9], 2) if row[9] else None,
                'low_rejection_pct': round(row[10], 2) if row[10] else None,
                'high_rejection_pct': round(row[11], 2) if row[11] else None,
                'output_snr': round(row[12], 4) if row[12] else None,
                'output_psf_signal': row[13],
                'output_noise': row[14],
                'output_file': row[15],
                'frame_weights': [],
            }

            # Get frame weights for this integration
            cursor.execute("""
                SELECT filename, normalized_weight, accepted,
                       pixel_rejection_count, pixel_rejection_pct,
                       low_rejection_pct, high_rejection_pct
                FROM pixinsight_frame_weights
                WHERE integration_id = ?
                ORDER BY normalized_weight DESC
            """, (integ_id,))

            for fw in cursor.fetchall():
                integ['frame_weights'].append({
                    'filename': fw[0],
                    'weight': round(fw[1], 4) if fw[1] else None,
                    'accepted': bool(fw[2]),
                    'pixel_rejection_count': fw[3],
                    'pixel_rejection_pct': round(fw[4], 2) if fw[4] else None,
                    'low_rejection_pct': round(fw[5], 2) if fw[5] else None,
                    'high_rejection_pct': round(fw[6], 2) if fw[6] else None,
                })

            results.append(integ)

    return results


def get_quality_comparison_by_setup() -> List[Dict[str, Any]]:
    """Compare quality metrics across cameras/setups.

    Returns list of dicts with: camera, frame_count, avg_fwhm,
    avg_eccentricity, avg_snr, avg_stars.
    """
    db = _get_db()
    results = []

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT camera,
                   COUNT(*) as frames,
                   AVG(fwhm) as avg_fwhm,
                   AVG(eccentricity) as avg_ecc,
                   AVG(snr) as avg_snr,
                   AVG(num_stars) as avg_stars
            FROM pixinsight_subframes
            WHERE camera IS NOT NULL AND camera != ''
            GROUP BY camera
            ORDER BY frames DESC
        """)

        for row in cursor.fetchall():
            results.append({
                'camera': row[0],
                'frame_count': row[1],
                'avg_fwhm': round(row[2], 3) if row[2] else None,
                'avg_eccentricity': round(row[3], 3) if row[3] else None,
                'avg_snr': round(row[4], 3) if row[4] else None,
                'avg_stars': int(row[5]) if row[5] else None,
            })

    return results


def get_quality_trends(limit: int = 50) -> List[Dict[str, Any]]:
    """Get quality metric trends across sessions over time.

    Returns list of dicts ordered by session, with: session_id,
    log_timestamp, avg_fwhm, avg_eccentricity, avg_snr, frame_count.
    """
    db = _get_db()
    results = []

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.session_id, ps.log_timestamp,
                   AVG(s.fwhm), AVG(s.eccentricity), AVG(s.snr),
                   COUNT(*) as cnt
            FROM pixinsight_subframes s
            LEFT JOIN pixinsight_sessions ps ON ps.session_id = s.session_id
            GROUP BY s.session_id
            ORDER BY ps.log_timestamp ASC
            LIMIT ?
        """, (limit,))

        for row in cursor.fetchall():
            results.append({
                'session_id': row[0],
                'log_timestamp': row[1],
                'avg_fwhm': round(row[2], 3) if row[2] else None,
                'avg_eccentricity': round(row[3], 3) if row[3] else None,
                'avg_snr': round(row[4], 3) if row[4] else None,
                'frame_count': row[5],
            })

    return results


def get_best_worst_frames(session_id: int, n: int = 10) -> Dict[str, List[Dict]]:
    """Get the best and worst frames by FWHM and SNR for a session.

    Returns dict with keys: best_fwhm, worst_fwhm, best_snr, worst_snr.
    Each is a list of dicts with: filename, filter_name, fwhm, snr,
    eccentricity, num_stars, psf_signal_weight.
    """
    db = _get_db()
    result = {'best_fwhm': [], 'worst_fwhm': [], 'best_snr': [], 'worst_snr': []}

    def _row_to_dict(row):
        return {
            'filename': row[0], 'filter_name': row[1],
            'fwhm': row[2], 'snr': row[3],
            'eccentricity': row[4], 'num_stars': row[5],
            'psf_signal_weight': row[6],
        }

    cols = "filename, filter_name, fwhm, snr, eccentricity, num_stars, psf_signal_weight"

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Best FWHM (lowest)
        cursor.execute(f"""
            SELECT {cols} FROM pixinsight_subframes
            WHERE session_id = ? AND fwhm IS NOT NULL
            ORDER BY fwhm ASC LIMIT ?
        """, (session_id, n))
        result['best_fwhm'] = [_row_to_dict(r) for r in cursor.fetchall()]

        # Worst FWHM (highest)
        cursor.execute(f"""
            SELECT {cols} FROM pixinsight_subframes
            WHERE session_id = ? AND fwhm IS NOT NULL
            ORDER BY fwhm DESC LIMIT ?
        """, (session_id, n))
        result['worst_fwhm'] = [_row_to_dict(r) for r in cursor.fetchall()]

        # Best SNR (highest)
        cursor.execute(f"""
            SELECT {cols} FROM pixinsight_subframes
            WHERE session_id = ? AND snr IS NOT NULL
            ORDER BY snr DESC LIMIT ?
        """, (session_id, n))
        result['best_snr'] = [_row_to_dict(r) for r in cursor.fetchall()]

        # Worst SNR (lowest)
        cursor.execute(f"""
            SELECT {cols} FROM pixinsight_subframes
            WHERE session_id = ? AND snr IS NOT NULL
            ORDER BY snr ASC LIMIT ?
        """, (session_id, n))
        result['worst_snr'] = [_row_to_dict(r) for r in cursor.fetchall()]

    return result


def get_filter_efficiency() -> List[Dict[str, Any]]:
    """Get integration efficiency per filter across all sessions.

    Returns list of dicts with: filter_name, total_frames, total_integrated,
    total_rejected, rejection_rate, avg_pixel_rejection_pct.
    """
    db = _get_db()
    results = []

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT filter_name,
                   SUM(frames_total) as total,
                   SUM(frames_integrated) as integrated,
                   SUM(frames_rejected) as rejected,
                   AVG(total_rejection_pct) as avg_pix_rej
            FROM pixinsight_integrations
            WHERE filter_name IS NOT NULL
            GROUP BY filter_name
            ORDER BY total DESC
        """)

        for row in cursor.fetchall():
            total = row[1] or 0
            integrated = row[2] or 0
            rejected = row[3] or 0
            results.append({
                'filter_name': row[0],
                'total_frames': total,
                'total_integrated': integrated,
                'total_rejected': rejected,
                'rejection_rate': round(rejected / total * 100, 1) if total > 0 else 0.0,
                'avg_pixel_rejection_pct': round(row[4], 2) if row[4] else None,
            })

    return results


def get_calibration_summary(session_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get calibration summary (masters used, frame counts).

    If session_id is None, returns summary across all sessions.
    Returns list of dicts with: filter_name, frame_type, frames_total,
    frames_active, image_width, image_height, binning, exposure_seconds,
    master_dark_path, master_flat_path, master_bias_path.
    """
    db = _get_db()
    results = []

    with db.get_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT filter_name, frame_type, frames_total, frames_active,
                   image_width, image_height, binning, exposure_seconds,
                   master_dark_path, master_flat_path, master_bias_path,
                   pedestal_value, session_id
            FROM pixinsight_calibrations
        """
        params = ()
        if session_id is not None:
            query += " WHERE session_id = ?"
            params = (session_id,)
        query += " ORDER BY frame_type, filter_name"

        cursor.execute(query, params)

        for row in cursor.fetchall():
            results.append({
                'filter_name': row[0],
                'frame_type': row[1],
                'frames_total': row[2],
                'frames_active': row[3],
                'image_width': row[4],
                'image_height': row[5],
                'binning': row[6],
                'exposure_seconds': row[7],
                'master_dark_path': row[8],
                'master_flat_path': row[9],
                'master_bias_path': row[10],
                'pedestal_value': row[11],
                'session_id': row[12],
            })

    return results


def get_all_subframes(session_id: int) -> List[Dict[str, Any]]:
    """Get all subframe metrics for a session (for table display).

    Returns list of dicts with all per-frame fields.
    """
    db = _get_db()
    results = []

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT filename, fwhm, eccentricity, num_stars,
                   psf_signal_weight, psf_snr, snr, median_adu,
                   mad_adu, mstar_adu, target_name, filter_name,
                   exposure_seconds, temperature, camera, binning,
                   frame_index
            FROM pixinsight_subframes
            WHERE session_id = ?
            ORDER BY frame_index, filename
        """, (session_id,))

        for row in cursor.fetchall():
            results.append({
                'filename': row[0],
                'fwhm': row[1],
                'eccentricity': row[2],
                'num_stars': row[3],
                'psf_signal_weight': row[4],
                'psf_snr': row[5],
                'snr': row[6],
                'median_adu': row[7],
                'mad_adu': row[8],
                'mstar_adu': row[9],
                'target_name': row[10],
                'filter_name': row[11],
                'exposure_seconds': row[12],
                'temperature': row[13],
                'camera': row[14],
                'binning': row[15],
                'frame_index': row[16],
            })

    return results


def get_session_list() -> List[Dict[str, Any]]:
    """Get list of all PixInsight sessions for the session selector.

    Returns list of dicts with: session_id, log_file_path, log_timestamp,
    pixinsight_version, total_subframes, script_name.
    """
    db = _get_db()
    results = []

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT session_id, log_file_path, log_timestamp,
                   pixinsight_version, total_subframes, script_name
            FROM pixinsight_sessions
            ORDER BY log_timestamp DESC
        """)

        for row in cursor.fetchall():
            results.append({
                'session_id': row[0],
                'log_file_path': row[1],
                'log_timestamp': row[2],
                'pixinsight_version': row[3],
                'total_subframes': row[4] or 0,
                'script_name': row[5],
            })

    return results


def get_seeing_estimation(session_id: int, pixel_scale: Optional[float] = None) -> Dict[str, Any]:
    """Estimate seeing from FWHM values + pixel scale.

    If pixel_scale is not given, returns FWHM in pixels only.
    Returns dict with: avg_fwhm_px, min_fwhm_px, max_fwhm_px,
    avg_seeing_arcsec, min_seeing_arcsec, max_seeing_arcsec (if pixel_scale given).
    """
    db = _get_db()
    result = {
        'avg_fwhm_px': None, 'min_fwhm_px': None, 'max_fwhm_px': None,
        'avg_seeing_arcsec': None, 'min_seeing_arcsec': None, 'max_seeing_arcsec': None,
    }

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT AVG(fwhm), MIN(fwhm), MAX(fwhm)
            FROM pixinsight_subframes
            WHERE session_id = ? AND fwhm IS NOT NULL
        """, (session_id,))
        row = cursor.fetchone()
        if row and row[0]:
            result['avg_fwhm_px'] = round(row[0], 3)
            result['min_fwhm_px'] = round(row[1], 3)
            result['max_fwhm_px'] = round(row[2], 3)

            if pixel_scale:
                result['avg_seeing_arcsec'] = round(row[0] * pixel_scale, 2)
                result['min_seeing_arcsec'] = round(row[1] * pixel_scale, 2)
                result['max_seeing_arcsec'] = round(row[2] * pixel_scale, 2)

    return result
