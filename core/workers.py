#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - UNIFIED WORKER ARCHITECTURE
================================================================================
Extensible worker thread with job queue for all background operations.
Replaces monolithic AnalysisWorker with plugin-based handlers.
================================================================================
"""

import sys
import traceback
import logging
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Any, Optional, Dict, List

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

# Thread-local storage for output capture
_thread_local = threading.local()


def worker_print(*args, **kwargs):
    """Print function that routes to thread-local OutputCapture if available,
    otherwise falls back to the real sys.stdout."""
    capture = getattr(_thread_local, 'output_capture', None)
    if capture is not None:
        text = ' '.join(str(a) for a in args)
        end = kwargs.get('end', '\n')
        capture.write(text + end)
    else:
        _original_stdout = sys.__stdout__ or sys.stdout
        print(*args, file=_original_stdout, **kwargs)


class JobType(Enum):
    """Types of background jobs"""
    ANALYSIS = "analysis"
    COMPRESSION = "compression"
    HEADER_EDIT = "header_edit"
    PLATE_SOLVE = "plate_solve"
    WEATHER_FETCH = "weather_fetch"
    FLAT_SCAN = "flat_scan"
    TARGET_UPDATE = "target_update"
    DISK_ANALYSIS = "disk_analysis"
    ASIAIR_IMPORT = "asiair_import"


@dataclass
class WorkerJob:
    """Represents a single job in the queue"""
    job_type: JobType
    params: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1-10, 10 = highest


def _verify_output_file(output_path: str) -> Dict:
    """Verify integrity of a compressed output file by reading its data.

    Returns {'success': True} or {'success': False, 'error': '...'}.
    On failure, deletes the corrupt file.
    """
    import os
    ext = output_path.lower()
    try:
        if ext.endswith('.xisf'):
            from modules.compression import XISFReader
            reader = XISFReader(output_path)
            reader.read_image()
        elif ext.endswith('.fits.fz') or ext.endswith('.fz'):
            from astropy.io import fits as astropy_fits
            with astropy_fits.open(output_path) as hdul:
                for hdu in hdul:
                    _ = hdu.data
        elif ext.endswith(('.fits', '.fit')):
            from astropy.io import fits as astropy_fits
            with astropy_fits.open(output_path) as hdul:
                _ = hdul[0].data
        else:
            return {'success': True}  # Unknown format, skip verification
        return {'success': True}
    except (MemoryError, PermissionError, OSError) as e:
        # Transient errors: don't delete the file, it may be valid
        return {'success': False, 'error': f'Verification error (file preserved): {e}'}
    except Exception as e:
        # Likely corruption: remove invalid output
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
        except OSError:
            pass
        return {'success': False, 'error': f'Integrity check failed: {e}'}


def _compress_single_file(task: Dict) -> Dict:
    """Compress a single file (top-level for ProcessPoolExecutor pickling).

    Workflow:
      1. Compress in-place (out_dir = same directory as source)
      2. If verify_integrity → _verify_output_file()
      3. If backup_folder → move original to backup preserving directory tree
    """
    import os
    import shutil
    try:
        filepath = task['filepath']
        src_ext = task['src_ext']
        basename = task['basename']
        out_dir = task['out_dir']
        profile_name = task['profile_name']
        output_format = task.get('output_format', 'xisf')
        backup_folder = task.get('backup_folder', '')
        source_folder = task.get('source_folder', '')
        verify_integrity = task.get('verify_integrity', True)

        os.makedirs(out_dir, exist_ok=True)

        out_path = None

        # Determine conversion based on source extension + target format
        if output_format == 'xisf':
            if src_ext in ('.fits', '.fit'):
                from modules.compression import fits_to_xisf
                out_path = os.path.join(out_dir, basename + '.xisf')
                result = fits_to_xisf(filepath, out_path, profile=profile_name)
            elif src_ext == '.xisf':
                from modules.compression import recompress_xisf
                out_path = os.path.join(out_dir, basename + '.xisf')
                if out_path == filepath:
                    out_path = filepath  # in-place recompression
                result = recompress_xisf(filepath, out_path, profile=profile_name)
            elif src_ext == '.fz':
                from modules.compression import fz_to_xisf
                out_path = os.path.join(out_dir, basename + '.xisf')
                result = fz_to_xisf(filepath, out_path, profile=profile_name)
            else:
                return {'success': False, 'file': filepath, 'error': f'Unsupported format: {src_ext}'}

        elif output_format == 'fz':
            if src_ext in ('.fits', '.fit'):
                from modules.compression import fits_to_fz
                out_path = os.path.join(out_dir, basename + '.fits.fz')
                result = fits_to_fz(filepath, out_path)
            elif src_ext == '.xisf':
                from modules.compression import xisf_to_fz
                out_path = os.path.join(out_dir, basename + '.fits.fz')
                result = xisf_to_fz(filepath, out_path)
            elif src_ext == '.fz':
                return {'success': True, 'file': filepath}  # Already FZ
            else:
                return {'success': False, 'file': filepath, 'error': f'Unsupported format: {src_ext}'}

        elif output_format == 'fits':
            if src_ext == '.xisf':
                from modules.compression import xisf_to_fits
                out_path = os.path.join(out_dir, basename + '.fits')
                result = xisf_to_fits(filepath, out_path)
            elif src_ext == '.fz':
                from modules.compression import fz_to_fits
                out_path = os.path.join(out_dir, basename + '.fits')
                result = fz_to_fits(filepath, out_path)
            elif src_ext in ('.fits', '.fit'):
                return {'success': True, 'file': filepath}  # Already FITS
            else:
                return {'success': False, 'file': filepath, 'error': f'Unsupported format: {src_ext}'}
        else:
            return {'success': False, 'file': filepath, 'error': f'Unknown output format: {output_format}'}

        # Check result from conversion function
        if result is None:
            result = {'status': 'error', 'message': 'Conversion returned None'}
        if result.get('status') != 'success':
            return {'success': False, 'file': filepath, 'error': result.get('message', 'Conversion failed')}

        actual_output = result.get('output', out_path)

        # Step 2: Verify integrity of compressed output
        if verify_integrity and actual_output and os.path.exists(actual_output):
            verify_result = _verify_output_file(actual_output)
            if not verify_result['success']:
                return {'success': False, 'file': filepath, 'error': verify_result['error']}

        # Step 3: Move original to backup folder (preserving directory tree)
        if backup_folder and source_folder:
            if os.path.abspath(filepath) != os.path.abspath(actual_output):
                rel_path = os.path.relpath(filepath, source_folder)
                backup_path = os.path.join(backup_folder, rel_path)
                # Validate against path traversal
                resolved_backup = os.path.realpath(backup_path)
                resolved_root = os.path.realpath(backup_folder)
                if not resolved_backup.startswith(resolved_root + os.sep) and resolved_backup != resolved_root:
                    return {'success': False, 'file': filepath, 'error': 'Path traversal detected in backup path'}
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                shutil.move(filepath, backup_path)

        return {'success': True, 'file': filepath}

    except Exception as e:
        return {'success': False, 'file': task.get('filepath', '?'), 'error': str(e)}


def _split_targets_by_focal(data_by_target: Dict) -> Dict:
    """
    Split targets that have files at significantly different focal lengths.

    If a target was imaged at 455mm (native) and 305mm (with 0.67x reducer),
    those are separate datasets that shouldn't be mixed. This function splits
    them into "Target (455mm)" and "Target (305mm)".

    Uses focal_length_mm from file headers, and _plate_solve_focal if available
    from a prior plate solving step.
    """
    from collections import defaultdict

    new_data = {}
    split_count = 0

    for target, info in data_by_target.items():
        files = info.get('files', [])
        if not files:
            new_data[target] = info
            continue

        # Collect focal lengths from each file
        focal_groups = defaultdict(list)
        for f in files:
            fi = f.get('info', {})
            nested = fi.get('info', {}) if isinstance(fi, dict) else {}
            fl = nested.get('focal_length_mm')
            if fl is not None:
                try:
                    fl = float(fl)
                    if fl > 0:
                        focal_groups[fl].append(f)
                        continue
                except (ValueError, TypeError):
                    pass
            # No focal length -> put in 'unknown' bucket
            focal_groups[0].append(f)

        # Cluster focal lengths with 10% tolerance
        if len(focal_groups) <= 1:
            new_data[target] = info
            continue

        sorted_focals = sorted(k for k in focal_groups.keys() if k > 0)
        if not sorted_focals:
            new_data[target] = info
            continue

        # Group close focal lengths together (within 10%)
        clusters = []  # list of (representative_focal, [files])
        for fl in sorted_focals:
            merged = False
            for cluster in clusters:
                ref = cluster[0]
                if abs(fl - ref) / ref < 0.10:
                    cluster[1].extend(focal_groups[fl])
                    merged = True
                    break
            if not merged:
                clusters.append([fl, list(focal_groups[fl])])

        # Add unknown-focal files to the largest cluster
        if 0 in focal_groups and clusters:
            largest = max(clusters, key=lambda c: len(c[1]))
            largest[1].extend(focal_groups[0])

        # If only one cluster after merging, no split needed
        if len(clusters) <= 1:
            new_data[target] = info
            continue

        # Split target into sub-targets
        split_count += 1
        for focal, cluster_files in clusters:
            sub_name = f"{target} ({focal:.0f}mm)"

            # Rebuild the sub-target data structure
            sub_info = {
                'files': cluster_files,
                'time_by_filter': defaultdict(list),
                'instruments': set(),
                'telescopes': set(),
                'dates': set(),
                'coordinates': [],
                'apertures': set(),
                'diameters': set(),
                'focal_lengths': set(),
                'files_by_date': {},
            }

            # Copy over optional keys from parent
            for key in ('simbad_info', 'received_light', 'adu_samples',
                        'adu_counter_by_filter', '_plate_solve_focal'):
                if key in info:
                    sub_info[key] = info[key]

            # Rebuild stats from the cluster files
            for f in cluster_files:
                fi = f.get('info', {})
                nested = fi.get('info', {}) if isinstance(fi, dict) else {}

                if fi.get('type') != 'LIGHT':
                    continue

                filt = fi.get('filter', 'Unknown')
                exp = fi.get('exposure_time') or 0
                sub_info['time_by_filter'][filt].append(exp)

                inst = nested.get('instrument', 'Unknown')
                tel = nested.get('telescope', 'Unknown')
                if inst != 'Unknown':
                    sub_info['instruments'].add(inst)
                if tel != 'Unknown':
                    sub_info['telescopes'].add(tel)

                date_obs = nested.get('date_obs')
                if date_obs:
                    sub_info['dates'].add(date_obs)
                sub_info['apertures'].add(nested.get('f_number'))
                sub_info['diameters'].add(nested.get('diameter_mm'))
                sub_info['focal_lengths'].add(nested.get('focal_length_mm'))

                if fi.get('ra') and fi.get('dec'):
                    sub_info['coordinates'].append((fi['ra'], fi['dec']))

                # Rebuild files_by_date
                obs_date = fi.get('observation_date', '')
                if obs_date:
                    obs_date = str(obs_date)[:10]
                    if obs_date not in sub_info['files_by_date']:
                        sub_info['files_by_date'][obs_date] = {
                            'time_by_filter': {},
                            'exposure_details': {},
                            'total_time': 0
                        }
                    date_entry = sub_info['files_by_date'][obs_date]
                    if filt not in date_entry['time_by_filter']:
                        date_entry['time_by_filter'][filt] = []
                    date_entry['time_by_filter'][filt].append(exp)
                    date_entry['total_time'] += exp

                    if filt not in date_entry['exposure_details']:
                        date_entry['exposure_details'][filt] = {}
                    if exp not in date_entry['exposure_details'][filt]:
                        date_entry['exposure_details'][filt][exp] = 0
                    date_entry['exposure_details'][filt][exp] += 1

            new_data[sub_name] = sub_info

    if split_count > 0:
        print(f"\n🔀 Split {split_count} target(s) by focal length (reducer vs native)")
        for name in new_data:
            if '(' in name and 'mm)' in name:
                files_count = len([f for f in new_data[name].get('files', [])
                                   if f.get('info', {}).get('type') == 'LIGHT'])
                print(f"    → {name}: {files_count} light frames")

    return new_data


class UnifiedWorker(QThread):
    """
    Unified worker thread supporting multiple job types.

    Signals:
        output_signal: Console text output
        progress_signal: (current, total, phase_description)
        finished_signal: (success, message, result_data)
    """

    # Core signals (backwards compatible)
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int, str)
    finished_signal = pyqtSignal(bool, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.jobs: List[WorkerJob] = []
        self.current_job: Optional[WorkerJob] = None
        self.should_stop = False

    def add_job(self, job: WorkerJob):
        """Add job to queue (sorted by priority)"""
        self.jobs.append(job)
        self.jobs.sort(key=lambda x: x.priority, reverse=True)

    def set_single_job(self, job: WorkerJob):
        """Set a single job (convenience method)"""
        self.jobs = [job]

    def run(self):
        """Main worker loop - process jobs from queue"""
        import time
        self.should_stop = False

        # Redirect stdout to capture output with buffering to avoid flooding the UI
        class OutputCapture:
            def __init__(self, signal):
                self.signal = signal
                self._buffer = []
                self._last_flush = 0

            def write(self, text):
                if not text:
                    return 0
                self._buffer.append(str(text))
                now = time.monotonic()
                if now - self._last_flush >= 0.1:
                    self._do_flush()
                return len(text)

            def _do_flush(self):
                if self._buffer:
                    import time as _t
                    combined = ''.join(self._buffer)
                    self._buffer.clear()
                    self._last_flush = _t.monotonic()
                    self.signal.emit(combined)

            def flush(self):
                self._do_flush()

        capture = OutputCapture(self.output_signal)
        # Use thread-local capture to avoid corrupting other threads' stdout
        _thread_local.output_capture = capture

        try:
            while self.jobs and not self.should_stop:
                self.current_job = self.jobs.pop(0)
                logger.info(f"Starting job: {self.current_job.job_type.value}")

                try:
                    result = self._dispatch_job(self.current_job)
                    if not self.should_stop:
                        self.finished_signal.emit(True, "Job completed", result)
                except Exception as e:
                    logger.error(f"Job failed: {e}", exc_info=True)
                    print(f"\n❌ Error: {str(e)}")
                    traceback.print_exc()
                    self.finished_signal.emit(False, str(e), None)

                self.current_job = None

            if self.should_stop:
                self.finished_signal.emit(False, "Stopped by user", None)

        finally:
            capture.flush()
            _thread_local.output_capture = None

    def _dispatch_job(self, job: WorkerJob) -> Any:
        """Dispatch job to appropriate handler"""
        handlers = {
            JobType.ANALYSIS: self._handle_analysis,
            JobType.COMPRESSION: self._handle_compression,
            JobType.HEADER_EDIT: self._handle_header_edit,
            JobType.FLAT_SCAN: self._handle_flat_scan,
            JobType.PLATE_SOLVE: self._handle_plate_solve,
            JobType.WEATHER_FETCH: self._handle_weather_fetch,
            JobType.DISK_ANALYSIS: self._handle_disk_analysis,
            JobType.ASIAIR_IMPORT: self._handle_asiair_import,
        }

        handler = handlers.get(job.job_type)
        if handler:
            return handler(job.params)
        else:
            raise ValueError(f"Unknown job type: {job.job_type}")

    # =========================================================================
    # JOB HANDLERS
    # =========================================================================

    def _handle_analysis(self, params: Dict) -> Dict:
        """Handle FITS/XISF analysis job - delegates to existing code"""
        import os
        from datetime import datetime
        import fits_analyser_gui as fag

        folder = params['folder']
        options = params.get('options', {})

        # Configure analysis settings
        fag.GENERATE_THUMBNAILS = options.get('generate_thumbnails', False)
        fag.ADU_ANALYSIS_ENABLED = False
        fag.FAST_ANALYSIS = True
        fag.DETECT_WRONG_EXTENSIONS = options.get('detect_wrong_extensions', False)

        # Clear stale duplicate data from previous runs
        if hasattr(fag, 'clear_detected_duplicates'):
            fag.clear_detected_duplicates()
        # Clear any leftover extension mismatches from previous runs
        if hasattr(fag, '_EXTENSION_MISMATCHES'):
            fag._EXTENSION_MISMATCHES = []

        # Propagate language setting to legacy engine
        lang = 'en'  # default fallback if config fails
        try:
            from core.config import get_config
            config = get_config()
            lang = config.get('application.language', 'auto')
            if lang == 'auto':
                import locale
                try:
                    loc = locale.getlocale()[0]
                except (ValueError, AttributeError):
                    loc = None
                lang = 'fr' if loc and loc.startswith('fr') else 'en'
            if hasattr(fag, 'SYSTEM_LANGUAGE'):
                fag.SYSTEM_LANGUAGE = lang
            if hasattr(fag, 'set_language'):
                fag.set_language(lang)
        except Exception:
            pass

        workers = options.get('workers', 0)
        if workers == 0:
            # Use config system which factors in CPU, RAM, and storage type
            try:
                from core.config import get_config
                config = get_config()
                workers = config.get_workers()
            except Exception:
                import multiprocessing
                workers = multiprocessing.cpu_count()

        # Set progress callback
        def progress_cb(current, total, phase):
            self.progress_signal.emit(current, total, phase)
        fag.set_progress_callback(progress_cb)

        try:
            # ── Phase 1-3: Analysis pipeline ──
            result = fag.analyze_folder_recursive(
                folder, workers, check_abort=lambda: self.should_stop
            )
            if result is None or self.should_stop:
                return None

            data_by_target, global_data = result

            if not data_by_target:
                return {'data_by_target': {}, 'global_data': global_data}

            # ── Phase 4: Target grouping ──
            self.progress_signal.emit(0, 1, "Grouping targets...")
            data_by_target = fag.group_normalized_targets(data_by_target)

            # SIMBAD resolution
            if options.get('resolve_simbad', False) and hasattr(fag, 'SIMBAD_AVAILABLE') and fag.SIMBAD_AVAILABLE:
                print("\n🔭 Resolving targets via SIMBAD...")
                unique_names = list(data_by_target.keys())
                name_to_canonical, canonical_to_info = fag.query_simbad_for_targets(
                    unique_names, check_abort=lambda: self.should_stop
                )
                if name_to_canonical and not self.should_stop:
                    data_by_target = fag.merge_targets_by_simbad(
                        data_by_target, name_to_canonical, canonical_to_info
                    )

            if self.should_stop:
                return None

            data_by_target = fag.group_mosaic_panels(data_by_target)

            # ── Plate solving (before reports, to enable focal length splitting) ──
            if options.get('plate_solve', False) and not self.should_stop:
                print("\n🔬 Running plate solving...")
                self.progress_signal.emit(0, 1, "Plate solving...")
                try:
                    import tempfile
                    from modules.plate_solving import PlateSolver
                    from core.config import get_config
                    _ps_config = get_config()
                    _ps_timeout = _ps_config.get('plate_solving.timeout_sec', 5)
                    _ps_retries = _ps_config.get('plate_solving.max_retries', 3)
                    _ps_path = _ps_config.get('plate_solving.astap_path')
                    ps = PlateSolver(timeout=_ps_timeout, executable_path=_ps_path)
                    if ps.is_available():
                        print(f"  ✓ ASTAP found: {ps.executable} (timeout={_ps_timeout}s, retries={_ps_retries})")

                        db_info = ps.check_database()
                        if db_info:
                            print(f"  ✓ Star database: {db_info['name']} ({db_info.get('count', '?')} files)")
                        else:
                            print("  ❌ No star database found!")
                            print("  💡 Download H17 from https://www.hnsky.org/astap.htm#deep_sky_databases")
                            print("  💡 Extract it into the ASTAP installation folder")

                        # Collect multiple candidate files per target for retry,
                        # preferring FITS over XISF
                        target_files = {}
                        for target, info in data_by_target.items():
                            fits_candidates = []
                            xisf_candidates = []
                            for f in info.get('files', []):
                                fp = f.get('path', '')
                                if not fp:
                                    continue
                                ext = fp.lower()
                                if ext.endswith(('.fits', '.fit', '.fz')):
                                    fits_candidates.append((fp, f))
                                elif ext.endswith(('.xisf', '.xifs', '.xif')):
                                    xisf_candidates.append((fp, f))
                            # Keep up to max_retries candidates for retry
                            all_candidates = fits_candidates + xisf_candidates
                            if all_candidates:
                                target_files[target] = all_candidates[:_ps_retries]

                        total_targets = len(target_files)
                        print(f"  📋 {total_targets} targets to solve")

                        solved_count = 0
                        failed_count = 0
                        temp_files = []

                        for idx, (target, candidates) in enumerate(target_files.items()):
                            if self.should_stop:
                                break
                            self.progress_signal.emit(idx, total_targets, f"Plate solving: {target}")

                            target_solved = False
                            for attempt, (fp, file_info) in enumerate(candidates):
                                if self.should_stop:
                                    break

                                analyze_info = file_info.get('info', {})
                                nested_info = analyze_info.get('info', {}) if isinstance(analyze_info, dict) else {}

                                # XISF -> temp FITS for ASTAP
                                solve_path = fp
                                if fp.lower().endswith(('.xisf', '.xifs', '.xif')):
                                    if attempt == 0:
                                        print(f"  📦 {target}: Converting XISF to temporary FITS...")
                                    try:
                                        from modules.compression import xisf_to_fits
                                        tmp_dir = tempfile.mkdtemp(prefix='astro_ps_')
                                        tmp_fits = os.path.join(tmp_dir, os.path.splitext(os.path.basename(fp))[0] + '.fits')
                                        conv_result = xisf_to_fits(fp, tmp_fits)
                                        if conv_result.get('status') == 'success':
                                            solve_path = tmp_fits
                                            temp_files.append(tmp_dir)
                                        else:
                                            continue
                                    except Exception:
                                        continue

                                # RA/DEC hints
                                ra_hint = dec_hint = None
                                try:
                                    ra_val = analyze_info.get('ra')
                                    dec_val = analyze_info.get('dec')
                                    if ra_val is not None and dec_val is not None:
                                        ra_hint = float(ra_val)
                                        dec_hint = float(dec_val)
                                except (ValueError, TypeError):
                                    pass

                                # FOV hint
                                fov_hint = None
                                instrument = nested_info.get('instrument', '')
                                focal_mm_val = nested_info.get('focal_length_mm')
                                try:
                                    if focal_mm_val and float(focal_mm_val) > 0:
                                        focal_mm_f = float(focal_mm_val)
                                        if instrument:
                                            from database.cameras import get_pixel_size, get_sensor_dimensions
                                            pixel_um = get_pixel_size(instrument)
                                            dims = get_sensor_dimensions(instrument)
                                            if pixel_um and dims:
                                                max_dim = max(dims[0], dims[1])
                                                fov_hint = (pixel_um * max_dim / focal_mm_f) * 206.265 / 3600.0
                                except (ValueError, TypeError):
                                    pass

                                result_ps = ps.solve_field(solve_path, ra_hint=ra_hint, dec_hint=dec_hint, fov_hint=fov_hint)
                                if result_ps.get('solved'):
                                    solved_count += 1
                                    target_solved = True
                                    scale = result_ps.get('scale', 0)
                                    fov_x = result_ps.get('fov_x', 0)
                                    fov_y = result_ps.get('fov_y', 0)
                                    rot = result_ps.get('rotation', 0)
                                    if attempt > 0:
                                        print(f"  ✅ {target}: solved on attempt {attempt + 1}/{len(candidates)} - "
                                              f"scale={scale:.2f}\"/px, FOV={fov_x:.2f}°x{fov_y:.2f}°, rot={rot:.1f}°")
                                    else:
                                        print(f"  ✅ {target}: scale={scale:.2f}\"/px, FOV={fov_x:.2f}°x{fov_y:.2f}°, rot={rot:.1f}°")

                                    # Detect focal reducer
                                    if focal_mm_val and instrument and scale > 0:
                                        try:
                                            from database.cameras import get_pixel_size as _gps
                                            pixel_um = _gps(instrument)
                                            if pixel_um:
                                                reducer = ps.detect_focal_reducer(scale, pixel_um, float(focal_mm_val))
                                                if reducer.get('detected') and reducer.get('ratio', 1.0) != 1.0:
                                                    eff_fl = reducer['effective_focal_mm']
                                                    print(f"       🔍 Reducer: {reducer['reducer_name']} "
                                                          f"(ratio={reducer['measured_ratio']:.3f}, FL={eff_fl:.0f}mm)")
                                                    data_by_target[target]['_plate_solve_focal'] = eff_fl
                                                elif reducer.get('detected'):
                                                    print(f"       🔍 No reducer (native, ratio={reducer['measured_ratio']:.3f})")
                                        except Exception:
                                            pass
                                    break  # Solved - no more retries needed
                                else:
                                    err = result_ps.get('error', 'Unknown error')
                                    if attempt < len(candidates) - 1:
                                        print(f"  ⏭️  {target}: attempt {attempt + 1} failed ({err}), trying next file...")
                                    else:
                                        print(f"  ❌ {target}: all {len(candidates)} attempts failed ({err})")

                            if not target_solved:
                                failed_count += 1

                        # Cleanup temp files
                        import shutil
                        for tmp_dir in temp_files:
                            try:
                                shutil.rmtree(tmp_dir, ignore_errors=True)
                            except Exception:
                                pass

                        print(f"  Plate solved {solved_count}/{solved_count + failed_count} targets")
                    else:
                        print("  ⚠️ ASTAP not found - skipping plate solving")
                        print("  💡 Install ASTAP from https://www.hnsky.org/astap.htm")
                except ImportError:
                    print("  ⚠️ Plate solving module not available")
                except Exception as e:
                    print(f"  ⚠️ Plate solving error: {e}")

            # ── Split targets by focal length (reducer vs native) ──
            if not self.should_stop:
                data_by_target = _split_targets_by_focal(data_by_target)

            # ── Display target statistics in console ──
            if hasattr(fag, 'display_target_statistics'):
                fag.display_target_statistics(data_by_target)

            # ── Generate output folder ──
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_folder = os.path.join(folder, f"astronomical_analysis_{timestamp}")
            os.makedirs(output_folder, exist_ok=True)

            # ── Thumbnails ──
            if options.get('generate_thumbnails', False) and not self.should_stop:
                print("\n📷 Generating thumbnails...")
                self.progress_signal.emit(0, 1, "Generating thumbnails...")
                try:
                    if hasattr(fag, 'generate_thumbnails_parallel_robust'):
                        fag.generate_thumbnails_parallel_robust(data_by_target, output_folder)
                    elif hasattr(fag, 'generate_thumbnails_sequential'):
                        fag.generate_thumbnails_sequential(data_by_target, output_folder)
                except Exception as e:
                    print(f"  ⚠️ Thumbnail generation: {e}")

            # ── Graphs ──
            if options.get('generate_graphs', True) and not self.should_stop:
                print("\n📊 Generating graphs...")
                self.progress_signal.emit(0, 1, "Generating graphs...")
                fag.generate_graphs(data_by_target, global_data, output_folder)

            # ── Reports (LaTeX/PDF + HTML) ──
            if options.get('generate_latex', True) and not self.should_stop:
                print("\n📄 Generating reports...")
                self.progress_signal.emit(0, 1, "Generating LaTeX/PDF report...")
                try:
                    fag.generate_latex_report(data_by_target, global_data, output_folder)
                except Exception as e:
                    print(f"  ⚠️ LaTeX report failed: {e}")
                    # Fallback to PDF without LaTeX (via ReportLab)
                    if hasattr(fag, 'generate_pdf_report_without_latex'):
                        print("  📄 Falling back to PDF generation without LaTeX...")
                        try:
                            fag.generate_pdf_report_without_latex(data_by_target, global_data, output_folder)
                        except Exception as e2:
                            print(f"  ⚠️ PDF fallback also failed: {e2}")

                # Clean up LaTeX temp files (.aux, .log, .toc, etc.)
                if hasattr(fag, 'cleanup_latex_temp_files'):
                    try:
                        fag.cleanup_latex_temp_files(output_folder)
                    except Exception:
                        pass

                self.progress_signal.emit(0, 1, "Generating HTML report...")
                fag.generate_html_report(data_by_target, global_data, output_folder)

            # ── CSV Export (global summary) ──
            if not self.should_stop:
                print("\n📋 Exporting CSV summaries...")
                self.progress_signal.emit(0, 1, "Exporting CSV...")
                if hasattr(fag, 'export_csv'):
                    fag.export_csv(data_by_target, global_data, output_folder)

            # ── AstroBin CSV Export ──
            if options.get('export_astrobin', False) and not self.should_stop:
                print("\n🌟 Exporting AstroBin CSV...")
                self.progress_signal.emit(0, 1, "Exporting AstroBin CSV...")
                fag.export_astrobin_csv(data_by_target, global_data, output_folder)

            # ── Post-analysis: Weather fetch ──
            if options.get('weather', False) and not self.should_stop:
                print("\n🌦️ Fetching weather data...")
                self.progress_signal.emit(0, 1, "Fetching weather data...")
                try:
                    from modules.weather_api import WeatherAPIClient
                    from core.config import get_config
                    config = get_config()
                    lat = config.get('observatory.latitude', 0)
                    lon = config.get('observatory.longitude', 0)
                    if lat != 0 or lon != 0:
                        client = WeatherAPIClient()
                        dates = set()
                        for target, info in data_by_target.items():
                            for f in info.get('files', []):
                                fi = f.get('info', {})
                                date_obs = fi.get('observation_date', '')
                                if date_obs and len(str(date_obs)) >= 10:
                                    dates.add(str(date_obs)[:10])
                        dates = sorted(dates)
                        fetched = 0
                        for i, d in enumerate(dates):
                            if self.should_stop:
                                break
                            self.progress_signal.emit(i + 1, len(dates), f"Weather: {d}")
                            w = client.fetch_weather_historical(d, lat, lon)
                            if w:
                                fetched += 1
                        print(f"  Weather data fetched for {fetched}/{len(dates)} dates")
                    else:
                        print("  ⚠️ Observatory coordinates not configured - skipping weather")
                except ImportError:
                    print("  ⚠️ Weather module not available")
                except Exception as e:
                    print(f"  ⚠️ Weather fetch error: {e}")

            # ── Post-analysis: Compress FITS → XISF ──
            if options.get('compress_fits', False) and not self.should_stop:
                _ctr = lambda en, fr: fr if lang == 'fr' else en
                print(_ctr("\n🗜️ Compressing FITS → XISF...",
                           "\n🗜️ Compression FITS → XISF..."))
                self.progress_signal.emit(0, 1, _ctr("Compression: FITS → XISF...",
                                                      "Compression : FITS → XISF..."))
                if hasattr(fag, 'compress_fits_to_xisf'):
                    # compress_fits_to_xisf(source_root, backup_folder, workers, add_to_duplicates, check_abort)
                    # It walks source_root internally to find FITS files
                    fag.compress_fits_to_xisf(
                        folder,
                        check_abort=lambda: self.should_stop
                    )
                else:
                    # Fallback: manually find and convert FITS files
                    fits_files = []
                    for target, info in data_by_target.items():
                        for f in info.get('files', []):
                            fp = f.get('path', '')
                            if fp and fp.lower().endswith(('.fits', '.fit')):
                                fits_files.append(fp)
                    if fits_files:
                        from modules.compression import fits_to_xisf
                        for i, fp in enumerate(fits_files):
                            if self.should_stop:
                                break
                            done = i + 1
                            n = len(fits_files)
                            pct = int(done * 100 / n) if n else 100
                            lbl = f"Compression : {done}/{n} ({pct}%) — {os.path.basename(fp)}" if lang == 'fr' \
                                else f"Compression: {done}/{n} ({pct}%) — {os.path.basename(fp)}"
                            self.progress_signal.emit(done, n, lbl)
                            try:
                                out_path = os.path.splitext(fp)[0] + '.xisf'
                                fits_to_xisf(fp, out_path)
                                print(f"  ✅ {os.path.basename(fp)}")
                            except Exception as e:
                                print(f"  ❌ {os.path.basename(fp)}: {e}")
                    else:
                        print("  No FITS files to compress")

            # ── Post-analysis: Extract duplicates ──
            if options.get('extract_duplicates', False) and not self.should_stop:
                print("\n📂 Extracting duplicates...")
                self.progress_signal.emit(0, 1, "Extracting duplicates...")
                if hasattr(fag, 'extract_duplicates_to_folder'):
                    # extract_duplicates_to_folder(source_root, dest_folder)
                    # It reads duplicates from the global DETECTED_DUPLICATES internally
                    dup_folder = os.path.join(folder, "duplicates_extracted")
                    fag.extract_duplicates_to_folder(folder, dup_folder)
                else:
                    print("  ⚠️ Duplicate extraction not available in legacy module")

            print(f"\n{'='*60}")
            print(f"✅ Analysis complete! Output: {output_folder}")
            print(f"{'='*60}")

            # Collect extension mismatches detected during analysis
            extension_mismatches = []
            if options.get('detect_wrong_extensions', False) and hasattr(fag, 'get_extension_mismatches'):
                extension_mismatches = fag.get_extension_mismatches()
                if extension_mismatches:
                    print(f"\n⚠️  {len(extension_mismatches)} file(s) with wrong extensions detected")

            return {
                'data_by_target': data_by_target,
                'global_data': global_data,
                'output_folder': output_folder,
                'extension_mismatches': extension_mismatches,
            }

        finally:
            fag.clear_progress_callback()
            if hasattr(fag, 'clear_header_cache'):
                fag.clear_header_cache()

    def _handle_compression(self, params: Dict) -> Dict:
        """Handle compression job - delegates to compression.py with parallel processing."""
        from modules.compression import COMPRESSION_PROFILES
        from concurrent.futures import ProcessPoolExecutor, as_completed
        import multiprocessing

        files = params.get('files', [])
        source_folder = params.get('source_folder', '')
        backup_folder = params.get('backup_folder', '')
        profile_name = params.get('profile', 'zlib_6')
        output_format = params.get('output_format', 'xisf')
        verify_integrity = params.get('verify_integrity', True)
        lang = params.get('lang', 'en')
        _tr = lambda en, fr: fr if lang == 'fr' else en

        # Validate profile exists
        if profile_name not in COMPRESSION_PROFILES:
            profile_name = 'zlib_6'

        import os
        from pathlib import Path

        # If no explicit file list, scan source folder
        if not files and source_folder:
            files = []
            for root, _, filenames in os.walk(source_folder):
                for fn in filenames:
                    ext = fn.lower()
                    if ext.endswith(('.fits', '.fit', '.xisf', '.fz')):
                        files.append(os.path.join(root, fn))

        total = len(files)
        if total == 0:
            print(_tr("No files found to compress.",
                       "Aucun fichier à compresser."))
            return {'processed': 0, 'errors': 0}

        # Auto-detect worker count for compression (CPU-bound)
        workers = params.get('workers', 0)
        if workers <= 0:
            cpu_count = multiprocessing.cpu_count()
            workers = max(2, min(cpu_count - 1, 8))

        fmt_label = {'xisf': 'XISF', 'fz': 'FITS.FZ', 'fits': 'FITS'}
        print(_tr(f"🗜️ Converting {total} files → {fmt_label.get(output_format, output_format)} "
                  f"with {profile_name} ({workers} workers)...",
                  f"🗜️ Conversion de {total} fichiers → {fmt_label.get(output_format, output_format)} "
                  f"avec {profile_name} ({workers} workers)..."))

        # Build task list with output paths
        tasks = []
        for filepath in files:
            src_ext = Path(filepath).suffix.lower()
            # Handle .fits.fz double extension
            if filepath.lower().endswith('.fits.fz'):
                src_ext = '.fz'
                basename = Path(filepath).stem  # removes .fz
                if basename.lower().endswith('.fits'):
                    basename = basename[:-5]  # remove .fits too
            else:
                basename = Path(filepath).stem

            # Always compress in-place (same directory as source)
            out_dir = os.path.dirname(filepath)

            tasks.append({
                'filepath': filepath,
                'src_ext': src_ext,
                'basename': basename,
                'out_dir': out_dir,
                'profile_name': profile_name,
                'output_format': output_format,
                'backup_folder': backup_folder,
                'source_folder': source_folder,
                'verify_integrity': verify_integrity,
            })

        processed = 0
        errors = 0

        # Parallel compression with ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {}
            for task in tasks:
                if self.should_stop:
                    break
                future = executor.submit(_compress_single_file, task)
                futures[future] = task['filepath']

            for future in as_completed(futures):
                if self.should_stop:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                filepath = futures[future]
                try:
                    result = future.result(timeout=300)
                    if result.get('success'):
                        processed += 1
                        print(f"  ✅ {os.path.basename(filepath)}")
                    else:
                        errors += 1
                        print(f"  ❌ {os.path.basename(filepath)}: {result.get('error', 'Unknown')}")
                except Exception as e:
                    errors += 1
                    print(f"  ❌ {os.path.basename(filepath)}: {e}")

                done = processed + errors
                pct = int(done * 100 / total) if total else 100
                phase = _tr(
                    f"Compression: {done}/{total} ({pct}%) — {os.path.basename(filepath)}",
                    f"Compression : {done}/{total} ({pct}%) — {os.path.basename(filepath)}"
                )
                self.progress_signal.emit(done, total, phase)

        result = {'processed': processed, 'errors': errors, 'total': total}
        print(_tr(f"\n✅ Compression complete: {processed}/{total} files, {errors} errors",
                  f"\n✅ Compression terminée : {processed}/{total} fichiers, {errors} erreurs"))
        return result

    def _handle_header_edit(self, params: Dict) -> Dict:
        """Handle mass header editing job"""
        from modules.header_editor import write_headers_batch

        files = params.get('files', [])
        changes = params.get('changes', {})

        if not files or not changes:
            return {'modified': 0}

        total = len(files)
        print(f"✏️ Editing headers for {total} files...")

        def progress_cb(i, total_count):
            self.progress_signal.emit(i, total_count, f"Editing headers...")

        results = write_headers_batch(files, changes, progress_callback=progress_cb)

        modified = sum(1 for r in results if r.get('success', False))
        errors = total - modified

        print(f"\n✅ Header editing complete: {modified}/{total} modified, {errors} errors")
        return {'modified': modified, 'errors': errors, 'total': total, 'results': results}

    def _handle_flat_scan(self, params: Dict) -> Dict:
        """Handle flat frame scanning job"""
        folder = params.get('folder', '')

        if not folder:
            return {'groups': []}

        print(f"📸 Scanning flat frames in: {folder}")

        try:
            from modules.flat_manager import FlatManager
            manager = FlatManager()
            groups = manager.scan_flats(folder, check_abort=lambda: self.should_stop,
                                       progress_callback=lambda c, t: self.progress_signal.emit(c, t, "Scanning flats..."))

            print(f"\n✅ Found {len(groups)} flat groups")
            return {
                'groups': [g.to_dict() for g in groups.values()] if isinstance(groups, dict) else [],
                'folder': folder,
            }
        except Exception as e:
            print(f"❌ Flat scan error: {e}")
            return {'groups': [], 'error': str(e)}

    def _handle_plate_solve(self, params: Dict) -> Dict:
        """Handle plate solving job"""
        import os
        files = params.get('files', [])
        solver = params.get('solver', 'astap')

        print(f"🔬 Plate solving {len(files)} files with {solver}...")

        try:
            from modules.plate_solving import PlateSolver
            ps = PlateSolver(solver=solver)

            results = []
            for i, filepath in enumerate(files):
                if self.should_stop:
                    break
                self.progress_signal.emit(i + 1, len(files), f"Solving: {os.path.basename(filepath)}")
                result = ps.solve_field(filepath)
                results.append({'file': filepath, 'result': result})

            solved = sum(1 for r in results if r.get('result', {}).get('solved', False))
            print(f"\n✅ Plate solving complete: {solved}/{len(files)} solved")
            return {'results': results, 'solved': solved}

        except ImportError:
            print("⚠️ Plate solving module not available")
            return {'results': [], 'error': 'Module not available'}

    def _handle_weather_fetch(self, params: Dict) -> Dict:
        """Handle weather data fetching job"""
        dates = params.get('dates', [])
        latitude = params.get('latitude', 0)
        longitude = params.get('longitude', 0)

        print(f"🌦️ Fetching weather for {len(dates)} dates...")

        try:
            from modules.weather_api import WeatherAPIClient
            client = WeatherAPIClient()

            results = {}
            for i, date in enumerate(dates):
                if self.should_stop:
                    break
                self.progress_signal.emit(i + 1, len(dates), f"Fetching weather: {date}")
                weather = client.fetch_weather_historical(date, latitude, longitude)
                if weather:
                    results[date] = weather

            print(f"\n✅ Weather data fetched for {len(results)}/{len(dates)} dates")
            return {'weather': results}

        except ImportError:
            print("⚠️ Weather module not available")
            return {'weather': {}, 'error': 'Module not available'}

    def _handle_disk_analysis(self, params: Dict) -> Dict:
        """Handle disk space analysis job with enriched file tracking."""
        import os
        import time as _time
        folder = params.get('folder', '')

        print(f"💾 Analyzing disk space in: {folder}")

        stats = {
            'fits_count': 0, 'fits_size': 0,
            'xisf_count': 0, 'xisf_size': 0,
            'fz_count': 0, 'fz_size': 0,
            'other_count': 0, 'other_size': 0,
            'total_count': 0, 'total_size': 0,
            # Enriched data for recommendations
            'fits_files': [],               # [(filepath, size), ...]
            'xisf_files': [],               # [(filepath, size, codec), ...]
            'xisf_pixinsight_count': 0,
            'xisf_pixinsight_size': 0,
            'xisf_recompressible_files': [], # [(filepath, size, codec), ...] PI excluded
            'xisf_recompressible_count': 0,
            'xisf_recompressible_size': 0,
            'calibration_files': [],         # [(filepath, size, mtime), ...]
        }

        # Calibration directory names (case-insensitive)
        calibration_dirs = {'dark', 'flat', 'bias', 'calibration', 'darks', 'flats',
                            'biases', 'offsets', 'offset'}

        all_files = []
        for root, _, filenames in os.walk(folder):
            for fn in filenames:
                fp = os.path.join(root, fn)
                all_files.append(fp)

        total = len(all_files)

        # ── Phase 1: Walk and collect file info ──
        for i, fp in enumerate(all_files):
            if self.should_stop:
                break
            if i % 500 == 0:
                self.progress_signal.emit(i, total, "Analyzing storage...")

            try:
                size = os.path.getsize(fp)
                ext = fp.lower()
                stats['total_count'] += 1
                stats['total_size'] += size

                if ext.endswith(('.fits', '.fit')):
                    stats['fits_count'] += 1
                    stats['fits_size'] += size
                    stats['fits_files'].append((fp, size))
                elif ext.endswith('.xisf'):
                    stats['xisf_count'] += 1
                    stats['xisf_size'] += size
                    # Read codec from XISF header (lightweight XML-only read)
                    try:
                        from modules.compression import read_xisf_compression_codec
                        codec = read_xisf_compression_codec(fp)
                    except Exception:
                        codec = ''
                    stats['xisf_files'].append((fp, size, codec))
                elif ext.endswith('.fz'):
                    stats['fz_count'] += 1
                    stats['fz_size'] += size
                else:
                    stats['other_count'] += 1
                    stats['other_size'] += size

                # Detect calibration files by parent directory name
                parent_parts = {p.lower() for p in os.path.normpath(fp).split(os.sep)[:-1]}
                if parent_parts & calibration_dirs:
                    try:
                        mtime = os.path.getmtime(fp)
                    except OSError:
                        mtime = 0
                    stats['calibration_files'].append((fp, size, mtime))

            except OSError:
                pass

        if self.should_stop:
            return stats

        # ── Phase 2: XISF classification (PixInsight exclusion) ──
        xisf_total = len(stats['xisf_files'])
        if xisf_total > 0:
            self.progress_signal.emit(0, xisf_total, "Classification des fichiers XISF...")
            from modules.compression import is_pixinsight_file_by_name, is_pixinsight_file_by_header

            for idx, (fp, size, codec) in enumerate(stats['xisf_files']):
                if self.should_stop:
                    break
                if idx % 200 == 0:
                    self.progress_signal.emit(idx, xisf_total, "Classification des fichiers XISF...")

                is_pi = False

                # Pass 1: Check by filename/path (fast, no I/O)
                if is_pixinsight_file_by_name(fp):
                    is_pi = True
                else:
                    # Pass 2: Check by header (requires reading XISF header)
                    try:
                        from modules.compression import XISFReader
                        reader = XISFReader(fp)
                        header_dict = reader.read_header_only()
                        if is_pixinsight_file_by_header(header_dict):
                            is_pi = True
                    except Exception:
                        pass

                if is_pi:
                    stats['xisf_pixinsight_count'] += 1
                    stats['xisf_pixinsight_size'] += size
                else:
                    # Non-PI file with suboptimal codec → recompressible
                    if codec in ('none', 'zlib', ''):
                        stats['xisf_recompressible_files'].append((fp, size, codec))
                        stats['xisf_recompressible_count'] += 1
                        stats['xisf_recompressible_size'] += size

        print(f"\n✅ Disk analysis complete: {stats['total_count']} files, "
              f"{stats['total_size'] / (1024**3):.1f} GB total")
        if stats['xisf_pixinsight_count'] > 0:
            print(f"   🔒 {stats['xisf_pixinsight_count']} PixInsight files detected (excluded from recompression)")
        if stats['xisf_recompressible_count'] > 0:
            print(f"   🗜️ {stats['xisf_recompressible_count']} XISF files recompressible (none/zlib → zstd)")
        return stats

    # =========================================================================
    # ASIAIR IMPORT
    # =========================================================================

    @staticmethod
    def _resolve_filter(date_obs_str: str, filter_mode: str,
                        filter_single: str, filter_ranges: list,
                        time_reference: str = 'utc',
                        site_long: float = 0.0,
                        timezone_str: str = '') -> str:
        """Resolve filter name for a file based on its DATE-OBS.

        The user enters time ranges in the reference of their choice.
        This method converts the file's DATE-OBS (always UTC) into that
        same reference before comparing.

        Args:
            date_obs_str: ISO 8601 DATE-OBS string (UTC)
            filter_mode: "single" or "timerange"
            filter_single: Filter name for single mode ("" = use header)
            filter_ranges: List of dicts {"start": "HH:MM", "end": "HH:MM", "filter": "..."}
            time_reference: How to interpret the user's time ranges:
                "utc"      — ranges are in UTC (no conversion)
                "solar"    — ranges are in local solar time (auto from longitude)
                "timezone" — ranges are in the configured timezone (DST-aware)
            site_long: Site longitude in degrees (east > 0) for solar mode
            timezone_str: IANA timezone (e.g. "Europe/Paris") for timezone mode

        Returns:
            Filter name, or "" to keep header value.
        """
        if filter_mode == 'single':
            return filter_single

        if filter_mode != 'timerange' or not filter_ranges:
            return ''

        from datetime import datetime, timedelta, timezone

        try:
            dt_utc = datetime.fromisoformat(date_obs_str.replace('Z', '+00:00'))
            # Ensure we have a naive-UTC datetime for arithmetic
            if dt_utc.tzinfo is not None:
                dt_utc = dt_utc.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            return ''

        # ── Convert UTC → local time according to chosen reference ──
        if time_reference == 'solar' and site_long != 0.0:
            # Local solar time offset = longitude / 15  hours
            # East  (+long) → ahead of UTC
            # West  (-long) → behind UTC
            offset_hours = site_long / 15.0
            dt_local = dt_utc + timedelta(hours=offset_hours)

        elif time_reference == 'timezone' and timezone_str:
            try:
                # Python 3.9+
                from zoneinfo import ZoneInfo
                tz = ZoneInfo(timezone_str)
            except ImportError:
                try:
                    # Fallback for Python 3.8 / missing tzdata
                    import pytz
                    tz = pytz.timezone(timezone_str)
                except Exception:
                    tz = None
            if tz is not None:
                try:
                    dt_aware = dt_utc.replace(tzinfo=timezone.utc)
                    dt_local = dt_aware.astimezone(tz).replace(tzinfo=None)
                except Exception:
                    dt_local = dt_utc
            else:
                dt_local = dt_utc
        else:
            # 'utc' or fallback
            dt_local = dt_utc

        obs_minutes = dt_local.hour * 60 + dt_local.minute + dt_local.second / 60.0

        for r in filter_ranges:
            try:
                sh, sm = map(int, r['start'].split(':'))
                eh, em = map(int, r['end'].split(':'))
            except (ValueError, KeyError):
                continue

            start_min = sh * 60 + sm
            end_min = eh * 60 + em

            # Skip zero-length ranges (start == end)
            if start_min == end_min:
                continue

            if end_min > start_min:
                # Same-day range (e.g. 20:00 → 23:30)
                if start_min <= obs_minutes < end_min:
                    return r.get('filter', '')
            else:
                # Crosses midnight (e.g. 23:30 → 03:00)
                if obs_minutes >= start_min or obs_minutes < end_min:
                    return r.get('filter', '')

        return ''

    @staticmethod
    def _compute_astro_night(date_obs_str: str, site_lat: float,
                             site_long: float) -> str:
        """Compute the astronomical night key from a DATE-OBS.

        The astronomical night is identified by the calendar date of the
        *evening*.  We define the boundary at local solar noon:
        noon_utc = 12:00 − longitude/15 hours.  Everything between noon(J)
        and noon(J+1) belongs to the night labelled J.

        Returns:
            Night date string "YYYY-MM-DD" (evening date).
        """
        from datetime import datetime, timedelta
        try:
            dt = datetime.fromisoformat(date_obs_str.replace('Z', '+00:00'))
            if dt.tzinfo is not None:
                # Convert to naive UTC (actual conversion, not just stripping tz)
                from datetime import timezone
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            return 'unknown'

        # Local solar noon in UTC: 12:00 minus longitude offset
        # Positive longitude = east → noon is earlier in UTC
        noon_offset_hours = site_long / 15.0
        noon_hour_utc = 12.0 - noon_offset_hours

        noon_today = dt.replace(hour=0, minute=0, second=0, microsecond=0) + \
            timedelta(hours=noon_hour_utc)

        if dt < noon_today:
            # Before today's noon → belongs to previous evening
            night_date = (dt - timedelta(days=1)).date()
        else:
            night_date = dt.date()

        return night_date.isoformat()

    def _handle_asiair_import(self, params: Dict) -> Dict:
        """Handle ASIAIR import: compress, write overrides, rename, organize."""
        import os
        import shutil
        from pathlib import Path
        from concurrent.futures import ProcessPoolExecutor, as_completed
        import multiprocessing

        source_folder = params.get('source_folder', '')
        backup_folder = params.get('backup_folder', '')
        organize = params.get('organize', False)
        output_folder = params.get('output_folder', '')
        telescope_override = params.get('telescope_override', '')
        filter_mode = params.get('filter_mode', 'single')
        filter_single = params.get('filter_single', '')
        filter_ranges = params.get('filter_ranges', [])
        time_reference = params.get('time_reference', 'utc')
        timezone_str = params.get('timezone_str', '')
        profile = params.get('profile', 'zlib_6')
        verify_integrity = params.get('verify_integrity', True)
        write_overrides = params.get('write_overrides', True)
        rename_pattern = params.get('rename_pattern', '')
        lang = params.get('lang', 'en')
        _tr = lambda en, fr: fr if lang == 'fr' else en

        if not rename_pattern:
            from modules.header_editor import DEFAULT_FILENAME_PATTERN
            rename_pattern = DEFAULT_FILENAME_PATTERN

        # ==================================================================
        # Phase 1 — Scan + resolve filters
        # ==================================================================
        print(_tr("=" * 60, "=" * 60))
        print(_tr("🔭 ASIAIR Import — Phase 1: Scanning files...",
                   "🔭 Import ASIAIR — Phase 1 : Scan des fichiers..."))
        print(_tr("=" * 60, "=" * 60))

        fits_files = []
        for root, _, filenames in os.walk(source_folder):
            for fn in filenames:
                if fn.lower().endswith(('.fits', '.fit')):
                    fits_files.append(os.path.join(root, fn))

        total = len(fits_files)
        if total == 0:
            print(_tr("No FITS files found.", "Aucun fichier FITS trouvé."))
            return {'processed': 0, 'errors': 0}

        print(_tr(f"  Found {total} FITS files",
                   f"  {total} fichiers FITS trouvés"))

        # Log time reference for filter resolution
        if filter_mode == 'timerange' and filter_ranges:
            if time_reference == 'solar':
                print(_tr(
                    "  ⏱️ Time ranges: LOCAL SOLAR TIME (auto from FITS coordinates)",
                    "  ⏱️ Plages horaires : HEURE SOLAIRE LOCALE (auto depuis coordonnées FITS)"))
            elif time_reference == 'timezone':
                print(_tr(
                    f"  ⏱️ Time ranges: TIMEZONE {timezone_str} (DST-aware)",
                    f"  ⏱️ Plages horaires : FUSEAU {timezone_str} (heure d'été gérée)"))
            else:
                print(_tr(
                    "  ⏱️ Time ranges: UTC",
                    "  ⏱️ Plages horaires : UTC"))

        # Quick header scan for DATE-OBS to resolve filters
        from astropy.io import fits as astropy_fits
        file_metadata = {}  # filepath -> {date_obs, filter, telescope, header}
        for i, fp in enumerate(fits_files):
            if self.should_stop:
                return {'processed': 0, 'errors': 0}
            try:
                with astropy_fits.open(fp, mode='readonly', memmap=True) as hdul:
                    hdr = hdul[0].header
                    date_obs = str(hdr.get('DATE-OBS', ''))
                    hdr_filter = str(hdr.get('FILTER', ''))
                    hdr_telescope = str(hdr.get('TELESCOP', ''))
                    site_lat = float(hdr.get('SITELAT', 0) or 0)
                    site_long = float(hdr.get('SITELONG', 0) or 0)

                    # Resolve filter (with local time conversion)
                    resolved_filter = self._resolve_filter(
                        date_obs, filter_mode, filter_single, filter_ranges,
                        time_reference=time_reference,
                        site_long=site_long,
                        timezone_str=timezone_str)
                    if not resolved_filter:
                        resolved_filter = hdr_filter

                    # Resolve telescope
                    resolved_telescope = telescope_override if telescope_override else hdr_telescope

                    file_metadata[fp] = {
                        'date_obs': date_obs,
                        'filter': resolved_filter,
                        'telescope': resolved_telescope,
                        'site_lat': site_lat,
                        'site_long': site_long,
                    }
            except Exception as e:
                print(f"  ⚠️ {os.path.basename(fp)}: {e}")
                file_metadata[fp] = {
                    'date_obs': '',
                    'filter': filter_single or '',
                    'telescope': telescope_override or '',
                    'site_lat': 0, 'site_long': 0,
                }

            if (i + 1) % 50 == 0 or i == total - 1:
                self.progress_signal.emit(i + 1, total,
                    _tr(f"Scanning: {i + 1}/{total}",
                         f"Scan : {i + 1}/{total}"))

        print(_tr(f"  Scan complete: {len(file_metadata)} files analyzed",
                   f"  Scan terminé : {len(file_metadata)} fichiers analysés"))

        # Display filter distribution
        filter_counts = {}
        for meta in file_metadata.values():
            f = meta['filter'] or 'N/A'
            filter_counts[f] = filter_counts.get(f, 0) + 1
        for f, c in sorted(filter_counts.items()):
            print(f"    {f}: {c} files")

        # ==================================================================
        # Phase 2 — Compression (FITS → XISF, parallel)
        # ==================================================================
        print(_tr(f"\n🗜️ Phase 2: Compressing {total} files → XISF ({profile})...",
                   f"\n🗜️ Phase 2 : Compression de {total} fichiers → XISF ({profile})..."))

        workers = max(2, min(multiprocessing.cpu_count() - 1, 8))

        tasks = []
        for fp in fits_files:
            src_ext = Path(fp).suffix.lower()
            basename = Path(fp).stem
            out_dir = os.path.dirname(fp)

            tasks.append({
                'filepath': fp,
                'src_ext': src_ext,
                'basename': basename,
                'out_dir': out_dir,
                'profile_name': profile,
                'output_format': 'xisf',
                'backup_folder': backup_folder,
                'source_folder': source_folder,
                'verify_integrity': verify_integrity,
            })

        processed = 0
        errors = 0
        xisf_files = {}  # original fits path -> resulting xisf path

        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {}
            for task in tasks:
                if self.should_stop:
                    break
                future = executor.submit(_compress_single_file, task)
                futures[future] = task['filepath']

            for future in as_completed(futures):
                if self.should_stop:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                filepath = futures[future]
                try:
                    result = future.result(timeout=300)
                    if result.get('success'):
                        processed += 1
                        # Map original to xisf path
                        xisf_path = os.path.splitext(filepath)[0] + '.xisf'
                        # After backup, the xisf is in the original dir
                        out_dir = os.path.dirname(filepath)
                        basename = Path(filepath).stem
                        expected_xisf = os.path.join(out_dir, basename + '.xisf')
                        xisf_files[filepath] = expected_xisf
                        print(f"  ✅ {os.path.basename(filepath)}")
                    else:
                        errors += 1
                        print(f"  ❌ {os.path.basename(filepath)}: {result.get('error', 'Unknown')}")
                except Exception as e:
                    errors += 1
                    print(f"  ❌ {os.path.basename(filepath)}: {e}")

                done = processed + errors
                pct = int(done * 100 / total) if total else 100
                self.progress_signal.emit(done, total,
                    _tr(f"Compression: {done}/{total} ({pct}%)",
                         f"Compression : {done}/{total} ({pct}%)"))

        print(_tr(f"  Compression: {processed}/{total} OK, {errors} errors",
                   f"  Compression : {processed}/{total} OK, {errors} erreurs"))

        if self.should_stop:
            return {'processed': processed, 'errors': errors}

        # ==================================================================
        # Phase 3 — Post-processing (sequential)
        # ==================================================================
        xisf_list = list(xisf_files.values())
        xisf_total = len(xisf_list)

        if xisf_total == 0:
            print(_tr("\n⚠️ No XISF files to post-process.",
                       "\n⚠️ Aucun fichier XISF à post-traiter."))
            return {'processed': processed, 'errors': errors}

        # --- 3a. Write overrides into XISF headers ---
        if write_overrides:
            print(_tr(f"\n✏️ Phase 3a: Writing header overrides...",
                       f"\n✏️ Phase 3a : Écriture des overrides dans les headers..."))

            from modules.header_editor import write_per_file_changes

            file_changes = {}
            for orig_fp, xisf_fp in xisf_files.items():
                if not os.path.exists(xisf_fp):
                    continue
                meta = file_metadata.get(orig_fp, {})
                changes = {}
                if meta.get('telescope'):
                    changes['TELESCOP'] = meta['telescope']
                if meta.get('filter'):
                    changes['FILTER'] = meta['filter']
                if changes:
                    file_changes[xisf_fp] = changes

            if file_changes:
                def hdr_progress(done_count, total_count):
                    self.progress_signal.emit(done_count, total_count,
                        _tr(f"Headers: {done_count}/{total_count}",
                             f"Headers : {done_count}/{total_count}"))

                results = write_per_file_changes(
                    file_changes, backup=False,
                    progress_callback=hdr_progress)
                hdr_ok = sum(1 for v in results.values() if v)
                print(_tr(f"  Headers updated: {hdr_ok}/{len(file_changes)}",
                           f"  Headers mis à jour : {hdr_ok}/{len(file_changes)}"))
            else:
                print(_tr("  No overrides to write.", "  Aucun override à écrire."))

        if self.should_stop:
            return {'processed': processed, 'errors': errors}

        # --- 3b. Rename XISF files using NINA pattern ---
        print(_tr(f"\n📝 Phase 3b: Renaming files with NINA pattern...",
                   f"\n📝 Phase 3b : Renommage selon le pattern NINA..."))

        from modules.header_editor import (
            read_header, get_header_value, build_filename, DEFAULT_FILENAME_PATTERN
        )

        renamed_files = {}  # xisf_old_path -> xisf_new_path

        # Read headers from XISF files and sort for frame numbering
        xisf_headers = {}
        for xisf_fp in xisf_list:
            if self.should_stop:
                break
            if not os.path.exists(xisf_fp):
                continue
            try:
                xisf_headers[xisf_fp] = read_header(xisf_fp)
            except Exception as e:
                print(f"  ⚠️ Cannot read header: {os.path.basename(xisf_fp)}: {e}")

        # Sort by DATE-OBS for frame numbering
        def _get_ts(fp):
            h = xisf_headers.get(fp, {})
            d = get_header_value(h, 'DATE-OBS')
            if d:
                try:
                    from datetime import datetime
                    return datetime.fromisoformat(str(d).replace('Z', '+00:00')).timestamp()
                except Exception:
                    pass
            return 0.0

        sorted_xisf = sorted(xisf_headers.keys(), key=_get_ts)

        # Group by target+filter+telescope for frame numbering
        groups = {}
        for fp in sorted_xisf:
            h = xisf_headers[fp]
            target = get_header_value(h, 'OBJECT') or 'Unknown'
            filt = get_header_value(h, 'FILTER') or ''
            scope = get_header_value(h, 'TELESCOP') or ''
            imgtype = get_header_value(h, 'IMAGETYP') or ''
            group_key = f"{target}_{filt}_{scope}_{imgtype}"
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(fp)

        # Build rename map
        rename_count = 0
        for group_key, group_files in groups.items():
            for idx, fp in enumerate(group_files, 1):
                if self.should_stop:
                    break
                h = xisf_headers.get(fp, {})
                new_name = build_filename(h, rename_pattern,
                                          frame_number=idx, extension='.xisf')
                new_path = os.path.join(os.path.dirname(fp), new_name)

                # Avoid collisions
                if new_path != fp and os.path.exists(new_path):
                    base, ext2 = os.path.splitext(new_path)
                    counter = 2
                    while os.path.exists(f"{base}_{counter}{ext2}"):
                        counter += 1
                    new_path = f"{base}_{counter}{ext2}"

                try:
                    if new_path != fp:
                        os.makedirs(os.path.dirname(new_path), exist_ok=True)
                        try:
                            os.rename(fp, new_path)
                        except OSError:
                            # Race condition: another process created the file, add timestamp suffix
                            import time as _time_mod
                            base_r, ext2_r = os.path.splitext(new_path)
                            new_path = f"{base_r}_{int(_time_mod.time())}{ext2_r}"
                            os.rename(fp, new_path)
                        rename_count += 1
                    renamed_files[fp] = new_path
                except Exception as e:
                    print(f"  ❌ Rename failed: {os.path.basename(fp)}: {e}")
                    renamed_files[fp] = fp

        print(_tr(f"  Renamed {rename_count} files",
                   f"  {rename_count} fichiers renommés"))

        if self.should_stop:
            return {'processed': processed, 'errors': errors}

        # --- 3c. Organize into directory structure (if requested) ---
        if organize and output_folder:
            print(_tr(f"\n📂 Phase 3c: Organizing into directory structure...",
                       f"\n📂 Phase 3c : Organisation en arborescence..."))

            # Get global site coordinates (from first file or config)
            global_lat = 0.0
            global_long = 0.0
            for meta in file_metadata.values():
                if meta.get('site_lat') and meta.get('site_long'):
                    global_lat = meta['site_lat']
                    global_long = meta['site_long']
                    break

            if global_lat == 0.0 and global_long == 0.0:
                try:
                    from core.config import get_config
                    cfg = get_config()
                    global_lat = cfg.get('observatory.latitude', 0)
                    global_long = cfg.get('observatory.longitude', 0)
                except Exception:
                    pass

            # Compute night keys for all files
            # Map: original fits path -> (night_key, astro_night_date)
            night_map = {}  # night_key -> set of files
            for orig_fp, xisf_new in renamed_files.items():
                meta = file_metadata.get(
                    # Find original fits path for this xisf
                    next((k for k, v in xisf_files.items()
                          if v == orig_fp), ''), {})
                if not meta:
                    # Try direct lookup
                    for fits_fp, xisf_fp in xisf_files.items():
                        if xisf_fp == orig_fp:
                            meta = file_metadata.get(fits_fp, {})
                            break

                date_obs = meta.get('date_obs', '')
                lat = meta.get('site_lat', global_lat) or global_lat
                lon = meta.get('site_long', global_long) or global_long
                night_key = self._compute_astro_night(date_obs, lat, lon)

                if night_key not in night_map:
                    night_map[night_key] = []
                night_map[night_key].append((orig_fp, xisf_new))

            # For each file, determine its destination
            moved = 0
            for orig_fp, xisf_new in renamed_files.items():
                if self.should_stop:
                    break
                if not os.path.exists(xisf_new):
                    continue

                # Find original metadata
                meta = {}
                for fits_fp, xisf_fp in xisf_files.items():
                    if xisf_fp == orig_fp:
                        meta = file_metadata.get(fits_fp, {})
                        break

                telescope = meta.get('telescope', 'Unknown') or 'Unknown'
                date_obs = meta.get('date_obs', '')
                lat = meta.get('site_lat', global_lat) or global_lat
                lon = meta.get('site_long', global_long) or global_long

                # Read target and image type from the renamed file header
                try:
                    h = read_header(xisf_new)
                    target = get_header_value(h, 'OBJECT') or 'Unknown'
                    imgtype = get_header_value(h, 'IMAGETYP') or 'LIGHT'
                    imgtype = imgtype.strip().upper()
                    if 'LIGHT' in imgtype:
                        imgtype = 'LIGHT'
                    elif 'FLAT' in imgtype:
                        imgtype = 'FLAT'
                    elif 'DARK' in imgtype:
                        imgtype = 'DARK'
                    elif 'BIAS' in imgtype or 'OFFSET' in imgtype:
                        imgtype = 'BIAS'
                except Exception:
                    target = 'Unknown'
                    imgtype = 'LIGHT'

                night_key = self._compute_astro_night(date_obs, lat, lon)

                # Determine night number (auto-increment)
                target_dir = os.path.join(output_folder, telescope, target)
                night_num = 1
                if os.path.exists(target_dir):
                    existing_nights = {}
                    for d in os.listdir(target_dir):
                        if d.startswith('Nuit_') or d.startswith('Night_'):
                            try:
                                n = int(d.split('_')[1])
                                existing_nights[n] = d
                            except (ValueError, IndexError):
                                pass
                    # Check if this night_key already has a folder
                    # We store a mapping file to track night_key -> folder
                    night_mapping_file = os.path.join(target_dir, '.night_mapping')
                    night_mapping = {}
                    if os.path.exists(night_mapping_file):
                        try:
                            with open(night_mapping_file, 'r') as mf:
                                for line in mf:
                                    parts = line.strip().split('=', 1)
                                    if len(parts) == 2:
                                        night_mapping[parts[0]] = int(parts[1])
                        except Exception:
                            pass

                    if night_key in night_mapping:
                        night_num = night_mapping[night_key]
                    else:
                        night_num = max(existing_nights.keys(), default=0) + 1
                        night_mapping[night_key] = night_num
                        os.makedirs(target_dir, exist_ok=True)
                        try:
                            with open(night_mapping_file, 'a') as mf:
                                mf.write(f"{night_key}={night_num}\n")
                        except Exception:
                            pass
                else:
                    # First night for this target
                    os.makedirs(target_dir, exist_ok=True)
                    try:
                        night_mapping_file = os.path.join(target_dir, '.night_mapping')
                        with open(night_mapping_file, 'w') as mf:
                            mf.write(f"{night_key}=1\n")
                    except Exception:
                        pass

                night_label = _tr(f"Night_{night_num}", f"Nuit_{night_num}")
                dest_dir = os.path.join(target_dir, night_label, imgtype)
                os.makedirs(dest_dir, exist_ok=True)

                dest_path = os.path.join(dest_dir, os.path.basename(xisf_new))
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(dest_path)
                    counter = 2
                    while os.path.exists(f"{base}_{counter}{ext}"):
                        counter += 1
                    dest_path = f"{base}_{counter}{ext}"

                try:
                    try:
                        shutil.move(xisf_new, dest_path)
                    except OSError:
                        # Race condition: another process created the file, add timestamp suffix
                        import time as _time_mod
                        base_r, ext_r = os.path.splitext(dest_path)
                        dest_path = f"{base_r}_{int(_time_mod.time())}{ext_r}"
                        shutil.move(xisf_new, dest_path)
                    moved += 1
                except Exception as e:
                    print(f"  ❌ Move failed: {os.path.basename(xisf_new)}: {e}")

                if moved > 0 and moved % 20 == 0:
                    self.progress_signal.emit(moved, xisf_total,
                        _tr(f"Organizing: {moved}/{xisf_total}",
                             f"Organisation : {moved}/{xisf_total}"))

            print(_tr(f"  Organized {moved} files into directory structure",
                       f"  {moved} fichiers organisés en arborescence"))

        # ==================================================================
        # Summary
        # ==================================================================
        print(_tr(f"\n{'=' * 60}", f"\n{'=' * 60}"))
        print(_tr(f"✅ ASIAIR Import complete!",
                   f"✅ Import ASIAIR terminé !"))
        print(_tr(f"   Compressed: {processed}/{total}",
                   f"   Compressés : {processed}/{total}"))
        print(_tr(f"   Errors: {errors}",
                   f"   Erreurs : {errors}"))
        if organize and output_folder:
            print(_tr(f"   Output: {output_folder}",
                       f"   Sortie : {output_folder}"))
        print(_tr(f"{'=' * 60}", f"{'=' * 60}"))

        return {'processed': processed, 'errors': errors, 'total': total}

    def stop(self):
        """Stop worker gracefully"""
        self.should_stop = True
