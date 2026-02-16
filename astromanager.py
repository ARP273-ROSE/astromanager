#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - COMPREHENSIVE ASTROPHOTOGRAPHY FILE MANAGER
================================================================================
AstroManager is a professional-grade file management suite for astrophotography,
combining FITS/XISF analysis, compression, header editing, flat management,
target tracking, and storage optimization.

Features:
- Universal file analysis (FITS, XISF, FITS.FZ)
- Multi-codec compression (zlib, zstd, lz4, lz4_hc)
- Mass header editing with NINA compatibility
- Flat frame management and master flat tracking
- Target tracking over time with SIMBAD integration
- Plate solving for focal reducer detection (ASTAP/Astrometry.net)
- Historical weather data integration
- Storage optimization and duplicate detection
- Cosmic-themed modern UI
- Bilingual support (English/French)
- Anonymous bug reporting
- Handles 200,000+ files efficiently

Usage:
    python astromanager.py              # Launch GUI
    python astromanager.py --help       # Show help

Author: Claude Code (Anthropic)
Version: 1.0.0
License: MIT
================================================================================
"""

import sys
import os
import subprocess
import importlib.util
import multiprocessing
from pathlib import Path
import argparse

# OBLIGATOIRE: freeze_support() must be called before any ProcessPoolExecutor
# usage when packaged as a Windows .exe with PyInstaller.
multiprocessing.freeze_support()


def _get_base_dir():
    """Return base directory (works in dev and frozen .exe)."""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


# Add current directory to Python path (append to avoid hijacking stdlib modules) [SEC]
sys.path.append(str(_get_base_dir()))

from core import __version__

# ============================================================================
# AUTOMATIC DEPENDENCY INSTALLATION
# ============================================================================

# Check Python version
if sys.version_info < (3, 8):
    print(f"WARNING: AstroManager requires Python 3.8+. Current: {sys.version}")

def _check_and_install(package_name, import_name=None, pip_name=None):
    """Check if a package is installed, install it if not."""
    if import_name is None:
        import_name = package_name
    if pip_name is None:
        pip_name = package_name

    spec = importlib.util.find_spec(import_name.split('.')[0])
    if spec is not None:
        return True

    print(f"  Installing {package_name}...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--user", "--quiet", pip_name],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode != 0:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet", pip_name],
                capture_output=True, text=True, timeout=180
            )

        if result.returncode == 0:
            print(f"  -> {package_name} OK")
            try:
                import site
                user_site = site.getusersitepackages()
                if user_site and user_site not in sys.path:
                    sys.path.insert(0, user_site)
            except Exception:
                pass
            importlib.invalidate_caches()
            return True
        else:
            print(f"  -> FAILED: {package_name}")
            if result.stderr:
                print(f"     {result.stderr.strip()[:200]}")
            return False
    except Exception as e:
        print(f"  -> ERROR: {package_name}: {e}")
        return False


def _setup_dependencies():
    """Auto-install all required dependencies."""
    # Skip when running as a frozen .exe — everything is already bundled
    if getattr(sys, 'frozen', False):
        return True

    # Only run in main process (not in ProcessPoolExecutor workers)
    if multiprocessing.current_process().name != 'MainProcess':
        return True

    # Detect language for messages
    lang = 'en'
    try:
        import locale
        loc = locale.getlocale()[0]
        if loc and loc.lower().startswith('fr'):
            lang = 'fr'
    except Exception:
        pass

    title = "ASTROMANAGER - CONFIGURATION AUTOMATIQUE" if lang == 'fr' else "ASTROMANAGER - AUTOMATIC SETUP"
    checking = "Verification des dependances..." if lang == 'fr' else "Checking dependencies..."

    # Dependencies: (display_name, import_name, pip_name, required)
    deps = [
        ("NumPy", "numpy", "numpy", True),
        ("Astropy", "astropy", "astropy", True),
        ("Matplotlib", "matplotlib", "matplotlib", True),
        ("Pandas", "pandas", "pandas", True),
        ("Pillow", "PIL", "Pillow", True),
        ("PyQt6", "PyQt6", "PyQt6", True),
        ("tqdm", "tqdm", "tqdm", True),
        ("requests", "requests", "requests", True),
        ("ReportLab", "reportlab", "reportlab", True),
        ("xisf", "xisf", "xisf", True),
        ("psutil", "psutil", "psutil", False),
        ("scipy", "scipy", "scipy", False),
        ("astroquery", "astroquery", "astroquery", False),
        ("zstandard", "zstandard", "zstandard", False),
        ("lz4", "lz4", "lz4", False),
        ("defusedxml", "defusedxml", "defusedxml", False),
        ("PyYAML", "yaml", "PyYAML", False),
    ]

    # Cache find_spec results to avoid repeated filesystem lookups [PERF]
    _spec_cache = {}

    def _cached_find_spec(import_name):
        root = import_name.split('.')[0]
        if root not in _spec_cache:
            _spec_cache[root] = importlib.util.find_spec(root)
        return _spec_cache[root]

    # Quick check: are all required deps already installed?
    all_present = True
    for name, import_name, pip_name, required in deps:
        if required:
            spec = _cached_find_spec(import_name)
            if spec is None:
                all_present = False
                break

    if all_present:
        return True  # Skip verbose output if everything is ready

    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")
    print(f"  Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print(f"  {checking}\n")

    failed_required = []
    total_deps = len(deps)
    for idx, (name, import_name, pip_name, required) in enumerate(deps, 1):
        spec = _cached_find_spec(import_name)
        if spec is not None:
            print(f"  [{idx}/{total_deps}] {name} ... OK")
        else:
            print(f"  [{idx}/{total_deps}] {name} ... installing")
            if not _check_and_install(name, import_name, pip_name):
                if required:
                    failed_required.append(name)

    if failed_required:
        msg = "Dependances manquantes" if lang == 'fr' else "Missing dependencies"
        print(f"\n  {msg}: {', '.join(failed_required)}")
        print(f"  pip install {' '.join(n.lower() for n in failed_required)}")
    else:
        msg = "Toutes les dependances sont installees !" if lang == 'fr' else "All dependencies installed!"
        print(f"\n  {msg}")

    print(f"{'=' * 60}\n")
    return len(failed_required) == 0


_DEPS_OK = _setup_dependencies()

# ============================================================================
# STANDARD IMPORTS (after dependency check)
# ============================================================================

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_environment():
    """Setup application environment"""
    try:
        # Initialize core modules
        from core.config import get_config
        from core.database import get_db
        from core.signals import get_signals

        config = get_config()
        db = get_db()
        signals = get_signals()

        logger.info(f"AstroManager v{__version__} starting...")
        logger.info(f"System: {config.get_system_info()}")

        # Create database backup
        backup_path = db.backup_database()
        if backup_path:
            logger.info(f"Database backup created: {backup_path}")

        return config, db, signals

    except Exception as e:
        logger.error(f"Failed to initialize core modules: {e}")
        raise


def auto_detect_workers(folder_path=None):
    """Auto-detect optimal worker count based on system capabilities."""
    import multiprocessing

    try:
        cpu_count = multiprocessing.cpu_count()
        if cpu_count <= 0:
            cpu_count = 1
    except (OSError, NotImplementedError):
        cpu_count = 1

    try:
        import psutil
        memory_gb = psutil.virtual_memory().total / (1024**3)
        memory_info = f"{memory_gb:.1f}GB RAM"
    except (ImportError, OSError, AttributeError):
        import platform
        system = platform.system().lower()
        memory_gb = cpu_count * (2 if system == "windows" else 4 if system == "darwin" else 3)
        memory_info = f"~{memory_gb:.0f}GB RAM (estimated)"

    # Detect storage type
    is_ssd = True
    storage_info = "SSD (assumed)"
    if folder_path:
        try:
            import fits_analyser_gui as fag
            if hasattr(fag, 'detect_storage_type'):
                is_ssd, storage_info = fag.detect_storage_type(Path(folder_path).resolve())
        except Exception:
            pass

    # Select workers based on system tier
    if cpu_count >= 16 and memory_gb >= 16:
        workers = cpu_count if is_ssd else max(4, min(8, cpu_count // 2))
        tier = "High-end"
    elif cpu_count >= 8 and memory_gb >= 8:
        workers = max(4, int(cpu_count * 0.75)) if is_ssd else max(2, int(cpu_count * 0.5))
        tier = "Mid-range"
    elif cpu_count >= 4 and memory_gb >= 4:
        workers = max(2, int(cpu_count * 0.5)) if is_ssd else max(1, int(cpu_count * 0.25))
        tier = "Entry-level"
    else:
        workers = min(2, cpu_count)
        tier = "Low-end"

    print(f"  Auto-detected {cpu_count} CPU cores, {memory_info}, {storage_info} ({tier} system)")
    print(f"  Optimal workers: {workers}")
    return workers


def run_cli(args):
    """Run analysis in CLI mode (headless)."""
    import time
    from datetime import datetime

    start_time = time.time()

    # Import the analysis engine
    try:
        import fits_analyser_gui as fag
    except ImportError as e:
        print(f"ERROR: Cannot import analysis engine: {e}")
        print("Ensure fits_analyser_gui.py is in the same directory.")
        return 1

    # Auto-detect workers
    if args.workers is None:
        args.workers = auto_detect_workers(args.folder)

    # Random seed
    if args.seed is not None:
        try:
            import numpy as np
            np.random.seed(args.seed)
            print(f"Random seed set: {args.seed}")
        except Exception as e:
            print(f"WARNING: Cannot set seed: {e}")

    # Resolve folder
    if args.folder:
        folder = Path(args.folder).resolve()
    else:
        folder = Path.cwd()
    print(f"Analysis folder: {folder}")

    if not folder.exists():
        print(f"ERROR: Folder does not exist: {folder}")
        return 1
    if not folder.is_dir():
        print(f"ERROR: Not a directory: {folder}")
        return 1

    # Region size
    region_size = max(16, int(args.region_size))

    # Force Mode 1 (fast analysis)
    if hasattr(fag, 'ADU_ANALYSIS_ENABLED'):
        fag.ADU_ANALYSIS_ENABLED = False
    if hasattr(fag, 'FAST_ANALYSIS'):
        fag.FAST_ANALYSIS = True
    if hasattr(fag, 'DEFAULT_REGION_SIZE'):
        fag.DEFAULT_REGION_SIZE = region_size

    print(f"\n{'=' * 80}")
    print(f"STARTING ANALYSIS")
    print(f"{'=' * 80}")

    # Create output folder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_name = f"astronomical_analysis_{timestamp}"
    if args.output:
        output_folder = str(Path(args.output).resolve())
    else:
        output_folder = str(folder / output_name)
    os.makedirs(output_folder, exist_ok=True)
    print(f"Output folder: {output_folder}")

    try:
        # Phase 1: Analyze FITS files
        print("Starting FITS analysis...")
        try:
            data_by_target, global_data = fag.analyze_folder_recursive(str(folder), args.workers)
        except Exception as e:
            print(f"Error during analysis: {e}")
            import traceback
            traceback.print_exc()
            return 1

        if not data_by_target:
            files_after_dedup = global_data.get('files_after_dedup', 0)
            if args.optimize_storage and files_after_dedup > 0:
                print(f"No LIGHT files found among {files_after_dedup} file(s).")
                print("Proceeding with storage optimization (all file types)...")
                if hasattr(fag, 'optimize_storage'):
                    fag.optimize_storage(
                        str(folder), args.optimize_storage,
                        prefer_format=args.prefer_format,
                        compress_fits=not args.no_compress,
                        workers=args.workers or 1
                    )
            else:
                if files_after_dedup > 0:
                    print(f"No LIGHT files among {files_after_dedup} file(s) (all calibration).")
                    print("Use --optimize-storage FOLDER to optimize storage for all file types.")
                else:
                    print("No FITS/XISF files found")
            return 0

        # Phase 2: Group normalized targets
        print("Grouping normalized targets...")
        original_count = len(data_by_target)
        if hasattr(fag, 'group_normalized_targets'):
            data_by_target = fag.group_normalized_targets(data_by_target)
        if len(data_by_target) != original_count:
            print(f"  Target normalization: {original_count} -> {len(data_by_target)} targets")

        # Phase 3: SIMBAD resolution
        if args.resolve_simbad:
            simbad_available = getattr(fag, 'SIMBAD_AVAILABLE', False)
            if simbad_available and hasattr(fag, 'query_simbad_for_targets'):
                print("Resolving targets via SIMBAD...")
                unique_names = list(data_by_target.keys())
                name_to_canonical, canonical_to_info = fag.query_simbad_for_targets(unique_names)
                if name_to_canonical and hasattr(fag, 'merge_targets_by_simbad'):
                    before = len(data_by_target)
                    data_by_target = fag.merge_targets_by_simbad(data_by_target, name_to_canonical, canonical_to_info)
                    after = len(data_by_target)
                    if before != after:
                        print(f"  SIMBAD merge: {before} -> {after} targets")
            else:
                print("  SIMBAD not available (install astroquery)")

        # Phase 4: Group mosaic panels
        if hasattr(fag, 'group_mosaic_panels'):
            print("Grouping mosaic panels...")
            mosaic_before = len(data_by_target)
            data_by_target = fag.group_mosaic_panels(data_by_target)
            if len(data_by_target) != mosaic_before:
                print(f"  Mosaic grouping: {mosaic_before} -> {len(data_by_target)} targets")

        # Phase 5: Display statistics
        if hasattr(fag, 'display_target_statistics'):
            fag.display_target_statistics(data_by_target)

        # Phase 6: Generate outputs
        if not args.no_graphs:
            if hasattr(fag, 'generate_graphs'):
                print("Generating graphs...")
                fag.generate_graphs(data_by_target, global_data, output_folder)

        if not args.no_latex:
            if hasattr(fag, 'generate_latex_report'):
                print("Generating LaTeX report...")
                try:
                    fag.generate_latex_report(data_by_target, global_data, output_folder)
                except Exception as e:
                    print(f"  LaTeX report failed: {e}")
                    if hasattr(fag, 'generate_pdf_report_without_latex'):
                        print("  Falling back to PDF generation without LaTeX...")
                        try:
                            fag.generate_pdf_report_without_latex(data_by_target, global_data, output_folder)
                        except Exception as e2:
                            print(f"  PDF fallback also failed: {e2}")
                # Clean up LaTeX temp files
                if hasattr(fag, 'cleanup_latex_temp_files'):
                    try:
                        fag.cleanup_latex_temp_files(output_folder)
                    except Exception:
                        pass
            if hasattr(fag, 'generate_html_report'):
                print("Generating HTML report...")
                fag.generate_html_report(data_by_target, global_data, output_folder)

        if args.export_csv:
            if hasattr(fag, 'export_csv'):
                print("Exporting CSV summaries...")
                fag.export_csv(data_by_target, global_data, output_folder)

        # Phase 7: Storage optimization
        if args.optimize_storage:
            if hasattr(fag, 'optimize_storage'):
                print("Optimizing storage...")
                fag.optimize_storage(
                    str(folder), args.optimize_storage,
                    prefer_format=args.prefer_format,
                    compress_fits=not args.no_compress,
                    workers=args.workers or 1
                )

        # Performance statistics
        end_time = time.time()
        total_time = end_time - start_time
        total_files = global_data.get('total_files', 0)
        files_per_second = total_files / total_time if total_time > 0 else 0

        hours = int(total_time // 3600)
        minutes = int((total_time % 3600) // 60)
        seconds = int(total_time % 60)
        if hours > 0:
            time_str = f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            time_str = f"{minutes}m {seconds}s"
        else:
            time_str = f"{seconds}s"

        print(f"\nAnalysis completed successfully!")
        print(f"Results saved in: {output_folder}")
        print(f"\n{'=' * 80}")
        print(f"TOTAL EXECUTION TIME: {time_str}")
        print(f"{'=' * 80}")
        print(f"Total files processed: {total_files:,}")
        print(f"Processing speed: {files_per_second:.2f} files/second")

        # File type breakdown
        file_types = global_data.get('file_types', {})
        if file_types and any(file_types.values()):
            print(f"\nFile type breakdown:")
            for ft, count in sorted(file_types.items()):
                if count > 0:
                    print(f"  .{ft}: {count:,} file(s)")

        # Performance rating
        if files_per_second >= 1000:
            print(f"Performance: Excellent")
        elif files_per_second >= 500:
            print(f"Performance: Very Good")
        elif files_per_second >= 100:
            print(f"Performance: Good")
        else:
            print(f"Performance: Slow")

        return 0

    except KeyboardInterrupt:
        print(f"\nAnalysis interrupted by user")
        return 130
    except Exception as e:
        print(f"\nAnalysis failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='AstroManager - Astrophotography File Management Suite',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python astromanager.py                                    # Launch GUI
  python astromanager.py --folder /path/to/fits             # CLI analysis
  python astromanager.py --folder /path --resolve-simbad    # With SIMBAD
  python astromanager.py --folder /path --export-csv        # Export CSV
  python astromanager.py --folder /path --no-graphs --no-latex  # Minimal output
  python astromanager.py --optimize-storage /backup --folder /data  # Optimize storage
  python astromanager.py --version                          # Show version
  python astromanager.py --reset-config                     # Reset configuration

For more information, visit: https://github.com/ARP273-ROSE/astromanager
        """
    )

    parser.add_argument('--version', action='version', version=f'AstroManager {__version__}')

    # Maintenance commands
    maint_group = parser.add_argument_group('Maintenance')
    maint_group.add_argument('--reset-config', action='store_true',
                             help='Reset configuration to defaults')
    maint_group.add_argument('--vacuum-db', action='store_true',
                             help='Optimize database (VACUUM)')
    maint_group.add_argument('--debug', action='store_true',
                             help='Enable debug logging')

    # CLI analysis arguments
    cli_group = parser.add_argument_group('CLI Analysis')
    cli_group.add_argument('--folder', type=str, default=None,
                           help='FITS folder to analyze (enables CLI mode)')
    cli_group.add_argument('--output', type=str, default=None,
                           help='Output folder for results')
    cli_group.add_argument('--workers', type=int, default=None,
                           help='Number of parallel workers (default: auto-detect)')
    cli_group.add_argument('--region-size', type=int, default=100,
                           help='Size (px) of SNR analysis regions (default: 100)')
    cli_group.add_argument('--seed', type=int, default=None,
                           help='Random seed for sampling reproducibility')

    # Output options
    out_group = parser.add_argument_group('Output Options')
    out_group.add_argument('--no-graphs', action='store_true',
                           help='Do not generate graphs')
    out_group.add_argument('--no-latex', action='store_true',
                           help='Do not generate LaTeX/HTML reports')
    out_group.add_argument('--export-csv', action='store_true',
                           help='Export CSV summaries')
    out_group.add_argument('--resolve-simbad', action='store_true',
                           help='Resolve targets via SIMBAD to merge duplicates and get object details')

    # Storage optimization
    stor_group = parser.add_argument_group('Storage Optimization')
    stor_group.add_argument('--optimize-storage', type=str, default=None, metavar='FOLDER',
                            help='Optimize storage: compress FITS->XISF, extract duplicates to FOLDER')
    stor_group.add_argument('--prefer-format', type=str, choices=['fits', 'xisf', 'fz'],
                            default='xisf',
                            help='Preferred format to keep (default: xisf)')
    stor_group.add_argument('--no-compress', action='store_true',
                            help='With --optimize-storage: only extract duplicates, skip compression')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Detect CLI mode: --folder or --optimize-storage triggers headless analysis
    cli_mode = args.folder is not None or args.optimize_storage is not None

    try:
        # Initialize environment
        config, db, signals = setup_environment()

        # Handle maintenance commands
        if args.reset_config:
            logger.info("Resetting configuration to defaults...")
            config.config = config._get_default_config()
            config.save_config()
            print("Configuration reset successfully.")
            return 0

        if args.vacuum_db:
            logger.info("Optimizing database...")
            db.vacuum()
            print("Database optimized successfully.")
            return 0

        if cli_mode:
            # Run headless CLI analysis
            logger.info("Running in CLI mode...")
            return run_cli(args)

        # Launch GUI
        logger.info("Launching graphical interface...")

        from gui.main_window import main as gui_main
        return gui_main()

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
