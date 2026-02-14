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
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Any, Optional, Dict, List

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


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


@dataclass
class WorkerJob:
    """Represents a single job in the queue"""
    job_type: JobType
    params: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1-10, 10 = highest


def _compress_single_file(task: Dict) -> Dict:
    """Compress a single file (top-level for ProcessPoolExecutor pickling)."""
    import os
    try:
        filepath = task['filepath']
        src_ext = task['src_ext']
        basename = task['basename']
        out_dir = task['out_dir']
        profile_name = task['profile_name']
        output_format = task.get('output_format', 'xisf')  # xisf, fz, fits
        delete_source = task['delete_source']

        os.makedirs(out_dir, exist_ok=True)

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
        if result.get('status') == 'success':
            if delete_source and result.get('output') and os.path.exists(result['output']):
                if os.path.abspath(filepath) != os.path.abspath(result['output']):
                    os.remove(filepath)
            return {'success': True, 'file': filepath}
        else:
            return {'success': False, 'file': filepath, 'error': result.get('message', 'Conversion failed')}

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

        old_stdout = sys.stdout
        sys.stdout = OutputCapture(self.output_signal)

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
            sys.stdout.flush()
            sys.stdout = old_stdout

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

        # Clear stale duplicate data from previous runs
        if hasattr(fag, 'clear_detected_duplicates'):
            fag.clear_detected_duplicates()

        # Propagate language setting to legacy engine
        try:
            from core.config import get_config
            config = get_config()
            lang = config.get('application.language', 'auto')
            if lang == 'auto':
                import locale
                loc = locale.getdefaultlocale()[0]
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
                print("\n🗜️ Compressing FITS → XISF...")
                self.progress_signal.emit(0, 1, "Compressing FITS files...")
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
                            self.progress_signal.emit(i + 1, len(fits_files),
                                f"Compressing: {os.path.basename(fp)}")
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

            return {
                'data_by_target': data_by_target,
                'global_data': global_data,
                'output_folder': output_folder,
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
        target_folder = params.get('target_folder', '')
        profile_name = params.get('profile', 'zlib_6')
        output_format = params.get('output_format', 'xisf')
        delete_source = params.get('delete_source', False)
        verify_integrity = params.get('verify_integrity', True)

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
            print("No files found to compress.")
            return {'processed': 0, 'errors': 0}

        # Auto-detect worker count for compression (CPU-bound)
        workers = params.get('workers', 0)
        if workers <= 0:
            cpu_count = multiprocessing.cpu_count()
            workers = max(2, min(cpu_count - 1, 8))

        fmt_label = {'xisf': 'XISF', 'fz': 'FITS.FZ', 'fits': 'FITS'}
        print(f"🗜️ Converting {total} files → {fmt_label.get(output_format, output_format)} "
              f"with {profile_name} ({workers} workers)...")

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

            if target_folder:
                rel_path = os.path.relpath(filepath, source_folder) if source_folder else os.path.basename(filepath)
                out_dir = os.path.join(target_folder, os.path.dirname(rel_path))
            else:
                out_dir = os.path.dirname(filepath)

            tasks.append({
                'filepath': filepath,
                'src_ext': src_ext,
                'basename': basename,
                'out_dir': out_dir,
                'profile_name': profile_name,
                'output_format': output_format,
                'delete_source': delete_source,
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

                self.progress_signal.emit(processed + errors, total,
                                          f"Compressing: {os.path.basename(filepath)}")

        result = {'processed': processed, 'errors': errors, 'total': total}
        print(f"\n✅ Compression complete: {processed}/{total} files, {errors} errors")
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
        """Handle disk space analysis job"""
        import os
        folder = params.get('folder', '')

        print(f"💾 Analyzing disk space in: {folder}")

        stats = {
            'fits_count': 0, 'fits_size': 0,
            'xisf_count': 0, 'xisf_size': 0,
            'fz_count': 0, 'fz_size': 0,
            'other_count': 0, 'other_size': 0,
            'total_count': 0, 'total_size': 0,
        }

        all_files = []
        for root, _, filenames in os.walk(folder):
            for fn in filenames:
                fp = os.path.join(root, fn)
                all_files.append(fp)

        total = len(all_files)
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
                elif ext.endswith('.xisf'):
                    stats['xisf_count'] += 1
                    stats['xisf_size'] += size
                elif ext.endswith('.fz'):
                    stats['fz_count'] += 1
                    stats['fz_size'] += size
                else:
                    stats['other_count'] += 1
                    stats['other_size'] += size
            except OSError:
                pass

        print(f"\n✅ Disk analysis complete: {stats['total_count']} files, "
              f"{stats['total_size'] / (1024**3):.1f} GB total")
        return stats

    def stop(self):
        """Stop worker gracefully"""
        self.should_stop = True
