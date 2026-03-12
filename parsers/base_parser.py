#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - BASE PARSER DATACLASSES
================================================================================
Data structures for PixInsight log parsing results.
================================================================================
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class ParsedSubframeMetric:
    """Per-frame SubframeSelector metrics."""
    filename: str = ''
    fwhm: Optional[float] = None
    eccentricity: Optional[float] = None
    num_stars: Optional[int] = None
    psf_signal_weight: Optional[float] = None
    psf_snr: Optional[float] = None
    snr: Optional[float] = None
    median_adu: Optional[float] = None
    mad_adu: Optional[float] = None
    mstar_adu: Optional[float] = None
    # Extracted from filename
    target_name: Optional[str] = None
    filter_name: Optional[str] = None
    exposure_seconds: Optional[float] = None
    temperature: Optional[float] = None
    camera: Optional[str] = None
    binning: Optional[int] = None
    frame_index: Optional[int] = None


@dataclass
class ParsedFrameWeight:
    """Per-frame weight and rejection data from ImageIntegration."""
    filename: str = ''
    normalized_weight: Optional[float] = None
    accepted: Optional[bool] = None
    rejection_weight: Optional[float] = None
    rejection_threshold: Optional[float] = None
    pixel_rejection_count: Optional[int] = None
    pixel_rejection_pct: Optional[float] = None
    low_rejection_pct: Optional[float] = None
    high_rejection_pct: Optional[float] = None


@dataclass
class ParsedIntegration:
    """ImageIntegration results for one filter/group."""
    filter_name: Optional[str] = None
    combination_method: Optional[str] = None
    weight_mode: Optional[str] = None
    normalization: Optional[str] = None
    rejection_method: Optional[str] = None
    frames_total: int = 0
    frames_integrated: int = 0
    frames_rejected: int = 0
    total_rejection_pct: Optional[float] = None
    low_rejection_pct: Optional[float] = None
    high_rejection_pct: Optional[float] = None
    output_snr: Optional[float] = None
    output_psf_signal: Optional[float] = None
    output_noise: Optional[float] = None
    output_file: Optional[str] = None
    normalized_weights: List[ParsedFrameWeight] = field(default_factory=list)
    pixel_rejections: List[ParsedFrameWeight] = field(default_factory=list)


@dataclass
class ParsedCalibrationGroup:
    """Calibration group metadata."""
    filter_name: Optional[str] = None
    frame_type: Optional[str] = None
    frames_total: int = 0
    frames_active: int = 0
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    binning: Optional[int] = None
    exposure_seconds: Optional[float] = None
    exposure_range: Optional[str] = None
    color_mode: Optional[str] = None
    keywords: Optional[str] = None
    master_dark_path: Optional[str] = None
    master_flat_path: Optional[str] = None
    master_bias_path: Optional[str] = None
    pedestal_value: Optional[float] = None


@dataclass
class ParsedMountTracking:
    """Per-sample mount tracking data from MountMonitor .dat file."""
    timestamp: str = ''
    ra_hours: float = 0.0
    dec_degrees: float = 0.0
    ra_deviation_arcsec: float = 0.0
    dec_deviation_arcsec: float = 0.0
    ra_stdev: float = 0.0
    dec_stdev: float = 0.0
    status: str = ''
    ra_axis_pos: Optional[float] = None
    dec_axis_pos: Optional[float] = None
    target_segment: int = 0


@dataclass
class ParsedMountTime:
    """Per-sample time synchronization data from MountMonitor .dti file."""
    timestamp: str = ''
    pc_mount_diff_ms: Optional[float] = None
    pc_loop_ms: Optional[float] = None
    mount_loop_ms: Optional[float] = None
    ntp_diff_ms: Optional[float] = None


@dataclass
class ParsedMountFFT:
    """FFT periodic error analysis from MountMonitor .fft file."""
    timestamp: str = ''
    axis: str = ''
    sample_rate: Optional[float] = None
    num_bins: Optional[int] = None
    peak1_freq: Optional[float] = None
    peak1_period: Optional[float] = None
    peak1_amp: Optional[float] = None
    peak2_freq: Optional[float] = None
    peak2_period: Optional[float] = None
    peak2_amp: Optional[float] = None
    peak3_freq: Optional[float] = None
    peak3_period: Optional[float] = None
    peak3_amp: Optional[float] = None


@dataclass
class ParsedMountEnvironment:
    """Environment data from MountMonitor .env file."""
    timestamp: str = ''
    temp_ext: Optional[float] = None
    pressure: Optional[float] = None
    temp_int: Optional[float] = None
    tracking_rate: Optional[str] = None
    meridian_flip_min: Optional[float] = None
    pier_side: Optional[str] = None
    align_stars: Optional[int] = None
    align_rms: Optional[float] = None
    polar_error: Optional[float] = None


@dataclass
class ParseResult:
    """Complete result from parsing a PixInsight WBPP log file."""
    # Header
    log_file_path: str = ''
    pixinsight_version: Optional[str] = None
    script_name: Optional[str] = None
    script_version: Optional[str] = None
    log_timestamp: Optional[str] = None

    # SubframeSelector per-frame metrics
    subframe_metrics: List[ParsedSubframeMetric] = field(default_factory=list)
    subframe_summary_succeeded: int = 0
    subframe_summary_failed: int = 0
    subframe_summary_skipped: int = 0

    # Frame weights and rejection from ImageIntegration
    frame_weights: List[ParsedFrameWeight] = field(default_factory=list)

    # Integration results per filter
    integrations: List[ParsedIntegration] = field(default_factory=list)

    # Calibration group metadata
    calibration_groups: List[ParsedCalibrationGroup] = field(default_factory=list)

    # Registration summary
    registration_succeeded: int = 0
    registration_failed: int = 0
    registration_skipped: int = 0

    # Timing
    total_elapsed: Optional[str] = None

    # Parsing stats
    parse_errors: List[str] = field(default_factory=list)

    # MountMonitor data
    mount_tracking_data: List[ParsedMountTracking] = field(default_factory=list)
    mount_time_data: List[ParsedMountTime] = field(default_factory=list)
    mount_fft_data: List[ParsedMountFFT] = field(default_factory=list)
    mount_environment_data: List[ParsedMountEnvironment] = field(default_factory=list)
    mount_source: Optional[str] = None  # 'mountmonitor'
    mount_version: Optional[str] = None
    mount_name: Optional[str] = None
    mount_location: Optional[str] = None
    mount_firmware: Optional[str] = None
    mount_num_segments: int = 0

    @property
    def total_subframes(self) -> int:
        return len(self.subframe_metrics)

    @property
    def has_subframe_data(self) -> bool:
        return len(self.subframe_metrics) > 0

    @property
    def has_integration_data(self) -> bool:
        return len(self.integrations) > 0

    @property
    def has_mount_data(self) -> bool:
        return len(self.mount_tracking_data) > 0


def store_results(result: 'ParseResult', session_id: int):
    """Store parsed PixInsight log data into database tables."""
    from core.database import get_db
    db = get_db()

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Store subframe metrics
        for sf in result.subframe_metrics:
            cursor.execute("""
                INSERT INTO pixinsight_subframes (
                    session_id, filename, fwhm, eccentricity, num_stars,
                    psf_signal_weight, psf_snr, snr, median_adu, mad_adu,
                    mstar_adu, target_name, filter_name, exposure_seconds,
                    temperature, camera, binning, frame_index
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, sf.filename, sf.fwhm, sf.eccentricity, sf.num_stars,
                sf.psf_signal_weight, sf.psf_snr, sf.snr, sf.median_adu,
                sf.mad_adu, sf.mstar_adu, sf.target_name, sf.filter_name,
                sf.exposure_seconds, sf.temperature, sf.camera, sf.binning,
                sf.frame_index
            ))

        # Store integrations
        for integ in result.integrations:
            cursor.execute("""
                INSERT INTO pixinsight_integrations (
                    session_id, filter_name, combination_method, weight_mode,
                    normalization, rejection_method, frames_total,
                    frames_integrated, frames_rejected, total_rejection_pct,
                    low_rejection_pct, high_rejection_pct, output_snr,
                    output_psf_signal, output_noise, output_file
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, integ.filter_name, integ.combination_method,
                integ.weight_mode, integ.normalization, integ.rejection_method,
                integ.frames_total, integ.frames_integrated,
                integ.frames_rejected, integ.total_rejection_pct,
                integ.low_rejection_pct, integ.high_rejection_pct,
                integ.output_snr, integ.output_psf_signal, integ.output_noise,
                integ.output_file
            ))
            integration_id = cursor.lastrowid

            # Store normalized weights for this integration
            for fw in integ.normalized_weights:
                cursor.execute("""
                    INSERT INTO pixinsight_frame_weights (
                        integration_id, session_id, filename,
                        normalized_weight, accepted,
                        pixel_rejection_count, pixel_rejection_pct,
                        low_rejection_pct, high_rejection_pct
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    integration_id, session_id, fw.filename,
                    fw.normalized_weight, 1 if fw.accepted else 0,
                    fw.pixel_rejection_count, fw.pixel_rejection_pct,
                    fw.low_rejection_pct, fw.high_rejection_pct
                ))

            # Store pixel rejection data
            for pr in integ.pixel_rejections:
                # Update existing frame weight if present, else insert
                cursor.execute("""
                    UPDATE pixinsight_frame_weights
                    SET pixel_rejection_count = ?,
                        pixel_rejection_pct = ?,
                        low_rejection_pct = ?,
                        high_rejection_pct = ?
                    WHERE integration_id = ? AND filename LIKE ?
                """, (
                    pr.pixel_rejection_count, pr.pixel_rejection_pct,
                    pr.low_rejection_pct, pr.high_rejection_pct,
                    integration_id,
                    '%' + pr.filename.split('/')[-1] if '/' in pr.filename else pr.filename
                ))

        # Store calibration groups
        for cal in result.calibration_groups:
            cursor.execute("""
                INSERT INTO pixinsight_calibrations (
                    session_id, filter_name, frame_type, frames_total,
                    frames_active, image_width, image_height, binning,
                    exposure_seconds, color_mode, master_dark_path,
                    master_flat_path, master_bias_path, pedestal_value
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, cal.filter_name, cal.frame_type,
                cal.frames_total, cal.frames_active, cal.image_width,
                cal.image_height, cal.binning, cal.exposure_seconds,
                cal.color_mode, cal.master_dark_path, cal.master_flat_path,
                cal.master_bias_path, cal.pedestal_value
            ))

        # Store session-level log metadata
        cursor.execute("""
            INSERT OR REPLACE INTO pixinsight_sessions (
                session_id, log_file_path, pixinsight_version,
                script_name, script_version, log_timestamp,
                total_subframes, subframes_succeeded, subframes_failed,
                registration_succeeded, registration_failed,
                total_elapsed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, result.log_file_path, result.pixinsight_version,
            result.script_name, result.script_version, result.log_timestamp,
            result.total_subframes, result.subframe_summary_succeeded,
            result.subframe_summary_failed, result.registration_succeeded,
            result.registration_failed, result.total_elapsed
        ))

    logger.info(f"Stored PI log: {result.total_subframes} subframes, "
                f"{len(result.integrations)} integrations, "
                f"{len(result.calibration_groups)} calibration groups")


def store_mount_results(result: 'ParseResult', session_id: int):
    """Store parsed MountMonitor data into database tables."""
    from core.database import get_db
    db = get_db()

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Store tracking data
        for t in result.mount_tracking_data:
            cursor.execute("""
                INSERT INTO mount_tracking_data (
                    session_id, timestamp, ra_hours, dec_degrees,
                    ra_dev_arcsec, dec_dev_arcsec, ra_stdev, dec_stdev,
                    status, ra_axis_pos, dec_axis_pos, target_segment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, t.timestamp, t.ra_hours, t.dec_degrees,
                t.ra_deviation_arcsec, t.dec_deviation_arcsec,
                t.ra_stdev, t.dec_stdev, t.status,
                t.ra_axis_pos, t.dec_axis_pos, t.target_segment
            ))

        # Store time data
        for t in result.mount_time_data:
            cursor.execute("""
                INSERT INTO mount_time_data (
                    session_id, timestamp, pc_mount_diff_ms,
                    pc_loop_ms, mount_loop_ms, ntp_diff_ms
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id, t.timestamp, t.pc_mount_diff_ms,
                t.pc_loop_ms, t.mount_loop_ms, t.ntp_diff_ms
            ))

        # Store FFT data
        for f in result.mount_fft_data:
            cursor.execute("""
                INSERT INTO mount_fft_data (
                    session_id, timestamp, axis, sample_rate, num_bins,
                    peak1_freq, peak1_period, peak1_amp,
                    peak2_freq, peak2_period, peak2_amp,
                    peak3_freq, peak3_period, peak3_amp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, f.timestamp, f.axis, f.sample_rate, f.num_bins,
                f.peak1_freq, f.peak1_period, f.peak1_amp,
                f.peak2_freq, f.peak2_period, f.peak2_amp,
                f.peak3_freq, f.peak3_period, f.peak3_amp
            ))

        # Store environment data
        for e in result.mount_environment_data:
            cursor.execute("""
                INSERT INTO mount_environment_data (
                    session_id, timestamp, temp_ext, pressure, temp_int,
                    tracking_rate, meridian_flip_min, pier_side,
                    align_stars, align_rms, polar_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, e.timestamp, e.temp_ext, e.pressure,
                e.temp_int, e.tracking_rate, e.meridian_flip_min,
                e.pier_side, e.align_stars, e.align_rms, e.polar_error
            ))

        # Store mount session metadata
        cursor.execute("""
            INSERT OR REPLACE INTO mount_sessions (
                session_id, log_file_path, mount_source, mount_version,
                mount_name, mount_location, mount_firmware,
                total_samples, tracking_samples, num_segments
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, result.log_file_path, result.mount_source,
            result.mount_version, result.mount_name,
            result.mount_location, result.mount_firmware,
            len(result.mount_tracking_data),
            sum(1 for t in result.mount_tracking_data if t.status == 'TRACKING'),
            result.mount_num_segments
        ))

    logger.info(f"Stored mount data: {len(result.mount_tracking_data)} tracking, "
                f"{len(result.mount_time_data)} time, "
                f"{len(result.mount_fft_data)} FFT, "
                f"{len(result.mount_environment_data)} env samples")
