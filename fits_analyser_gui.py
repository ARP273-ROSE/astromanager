#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
FITS ANALYSER - ASTROPHOTOGRAPHY ANALYSIS TOOL WITH INTEGRATED GUI
================================================================================
Complete Astrophotography Analysis Program
Advanced version with:
- AUTOMATIC DEPENDENCY INSTALLATION
- Modern graphical user interface (PyQt6)
- Full command-line support
- Recursive FITS/XISF analysis
- LaTeX/PDF report generation
- Statistical graphs and thumbnails

Usage:
    python fits_analyser_integrated.py              # Launch GUI
    python fits_analyser_integrated.py --cli        # Command-line mode
    python fits_analyser_integrated.py --folder /path --cli  # Analyze folder
    python fits_analyser_integrated.py --help       # Show help
================================================================================
"""

# ============================================================================
# SECTION 1: AUTO-INSTALLATION OF DEPENDENCIES
# ============================================================================

import sys
import subprocess
import importlib.util
import multiprocessing

# Check Python version
if sys.version_info < (3, 8):
    print("⚠️  WARNING: This program requires Python 3.8 or higher.")
    print(f"   Current Python version: {sys.version}")
    print("   Execution continues, but issues may occur...")
    print("   " + "=" * 60)

def _check_and_install(package_name, import_name=None, pip_name=None):
    """Check if a package is installed, install it if not."""
    if import_name is None:
        import_name = package_name
    if pip_name is None:
        pip_name = package_name
    
    # Check if module exists
    spec = importlib.util.find_spec(import_name.split('.')[0])
    if spec is not None:
        return True
    
    # Try to install
    print(f"📦 Installing {package_name}...")
    try:
        # Try with --user first
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--user", "--quiet", pip_name],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode != 0:
            # Try without --user (for virtual environments)
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet", pip_name],
                capture_output=True, text=True, timeout=180
            )
        
        if result.returncode == 0:
            print(f"   ✅ {package_name} installed successfully")
            # Re-add user site and Scripts to path so newly installed packages are available
            try:
                import site
                import os
                user_site = site.getusersitepackages()
                if user_site and user_site not in sys.path:
                    sys.path.insert(0, user_site)
                if sys.platform == 'win32':
                    user_scripts = str(__import__('pathlib').Path(user_site).parent / 'Scripts')
                else:
                    user_scripts = str(__import__('pathlib').Path(user_site).parent / 'bin')
                if user_scripts and user_scripts not in os.environ.get('PATH', ''):
                    os.environ['PATH'] = user_scripts + os.pathsep + os.environ.get('PATH', '')
            except Exception:
                pass
            importlib.invalidate_caches()
            return True
        else:
            print(f"   ❌ Failed to install {package_name}")
            return False
    except Exception as e:
        print(f"   ❌ Error installing {package_name}: {e}")
        return False

def _setup_dependencies():
    """Setup all dependencies automatically."""
    # Detect language early for setup messages
    lang = 'en'
    try:
        # Try getlocale first (Python 3.11+ recommended)
        import locale
        try:
            loc = locale.getlocale()[0]
            if loc and loc.lower().startswith('fr'):
                lang = 'fr'
        except Exception:
            pass
        
        # Fallback to environment variables
        if lang == 'en':
            import os
            for env_var in ['LC_ALL', 'LC_MESSAGES', 'LANG', 'LANGUAGE']:
                env_val = os.environ.get(env_var, '')
                if env_val and ('fr' in env_val.lower()[:5]):
                    lang = 'fr'
                    break
    except Exception:
        pass
    
    msgs = {
        'en': {
            'title': '🔧 FITS ANALYSER - AUTOMATIC CONFIGURATION',
            'checking': '📦 Checking and installing dependencies...',
            'installing': '📦 Installing',
            'ok': 'installed successfully',
            'fail': 'Failed to install',
            'all_ok': '✅ All required dependencies are installed!',
            'some_fail': '⚠️  Some required dependencies could not be installed',
        },
        'fr': {
            'title': '🔧 FITS ANALYSER - CONFIGURATION AUTOMATIQUE',
            'checking': '📦 Vérification et installation des dépendances...',
            'installing': '📦 Installation de',
            'ok': 'installé avec succès',
            'fail': 'Échec de l\'installation de',
            'all_ok': '✅ Toutes les dépendances requises sont installées !',
            'some_fail': '⚠️  Certaines dépendances n\'ont pas pu être installées',
        }
    }
    m = msgs[lang]
    
    print("\n" + "=" * 70)
    print(m['title'])
    print("=" * 70)
    print(f"🐍 Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print("-" * 70)
    
    # Add user site to path
    try:
        import site
        user_site = site.getusersitepackages()
        if user_site and user_site not in sys.path:
            sys.path.insert(0, user_site)
        # Add scripts to PATH
        if sys.platform == 'win32':
            user_scripts = str(__import__('pathlib').Path(user_site).parent / 'Scripts')
        else:
            user_scripts = str(__import__('pathlib').Path(user_site).parent / 'bin')
        import os
        if user_scripts not in os.environ.get('PATH', ''):
            os.environ['PATH'] = user_scripts + os.pathsep + os.environ.get('PATH', '')
    except Exception:
        pass
    
    # Dependencies: (display_name, import_name, pip_name, required)
    # xisf required for XISF read/write and compression
    deps = [
        ("NumPy", "numpy", "numpy", True),
        ("Matplotlib", "matplotlib", "matplotlib", True),
        ("Pandas", "pandas", "pandas", True),
        ("Astropy", "astropy", "astropy", True),
        ("Pillow", "PIL", "Pillow", True),
        ("tqdm", "tqdm", "tqdm", True),
        ("requests", "requests", "requests", True),
        ("ReportLab", "reportlab", "reportlab", True),
        ("PyQt6", "PyQt6", "PyQt6", True),
        ("xisf", "xisf", "xisf", True),
        ("psutil", "psutil", "psutil", False),
        ("scipy", "scipy", "scipy", False),
        ("astroquery", "astroquery", "astroquery", False),  # optional: SIMBAD resolution & duplicate target detection
    ]
    
    print(f"\n{m['checking']}")
    failed_required = []
    
    for name, import_name, pip_name, required in deps:
        if not _check_and_install(name, import_name, pip_name):
            if required:
                failed_required.append(name)
    
    print("-" * 70)
    if failed_required:
        print(f"{m['some_fail']}: {', '.join(failed_required)}")
    else:
        print(m['all_ok'])
    print("=" * 70 + "\n")
    
    return len(failed_required) == 0

# Run dependency setup only in the main process.
# ProcessPoolExecutor workers (phase 2) re-import this module and would otherwise
# print "Vérification des dépendances..." once per worker.
if multiprocessing.current_process().name == 'MainProcess':
    _DEPS_OK = _setup_dependencies()
else:
    _DEPS_OK = True  # Workers assume deps are already installed by main

# ============================================================================
# SECTION 2: STANDARD IMPORTS
# ============================================================================

# Configure UTF-8 encoding for Windows console compatibility
import io
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

import os
import re
import math
import shutil
try:
    import requests
except ImportError:
    requests = None
from pathlib import Path
from collections import defaultdict, Counter
from datetime import timedelta, datetime
import json
import argparse
import zipfile
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import locale
import time
import warnings
import traceback
import threading

# ============================================================================
# SECTION 3: PyQt6 GUI IMPORTS AND CLASSES
# ============================================================================

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QLineEdit, QTextEdit, QProgressBar,
        QFileDialog, QGroupBox, QCheckBox, QSpinBox, QComboBox,
        QTabWidget, QFrame, QSplitter, QMessageBox, QStatusBar,
        QScrollArea, QSizePolicy
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
    from PyQt6.QtGui import QFont, QAction, QTextCursor
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

# GUI will be defined after all functions are loaded (at end of file)

# Detect system language for bilingual support
def detect_system_language():
    """Detect system language and return 'fr' for French or 'en' for English (default)"""
    try:
        # Method 1: Try getlocale() first (recommended for Python 3.11+)
        try:
            current_locale = locale.getlocale()[0]
            if current_locale:
                lang_code = current_locale.lower()[:2]
                if lang_code == 'fr':
                    return 'fr'
        except Exception:
            pass
        
        # Method 2: Try to get locale from environment (cross-platform)
        import os
        for env_var in ['LC_ALL', 'LC_MESSAGES', 'LANG', 'LANGUAGE']:
            lang_env = os.environ.get(env_var, '')
            if lang_env:
                lang_lower = lang_env.lower()
                if lang_lower.startswith('fr') or '_fr' in lang_lower or '.fr' in lang_lower:
                    return 'fr'
        
        # Method 3: Windows-specific detection
        if sys.platform == 'win32':
            try:
                import ctypes
                windll = ctypes.windll.kernel32
                lang_id = windll.GetUserDefaultUILanguage()
                # French language IDs: 0x040c (French), 0x080c (Belgian), 0x0c0c (Canadian), etc.
                if (lang_id & 0xFF) == 0x0c:  # Primary language is French
                    return 'fr'
            except Exception:
                pass
    except Exception:
        pass
    
    # Default to English
    return 'en'

# Global language setting
SYSTEM_LANGUAGE = detect_system_language()

def set_language(lang_code):
    """Change the application language globally.
    
    Args:
        lang_code: 'fr' for French, 'en' for English, 'auto' for system detection
    """
    global SYSTEM_LANGUAGE
    if lang_code == 'auto':
        SYSTEM_LANGUAGE = detect_system_language()
    elif lang_code in ['fr', 'en']:
        SYSTEM_LANGUAGE = lang_code
    else:
        SYSTEM_LANGUAGE = 'en'
    return SYSTEM_LANGUAGE

def get_language():
    """Get the current language setting."""
    global SYSTEM_LANGUAGE
    return SYSTEM_LANGUAGE

# Translation dictionary
TRANSLATIONS = {
    'en': {
        # Common messages
        'warning': 'WARNING',
        'error': 'ERROR',
        'success': 'SUCCESS',
        'info': 'INFO',
        'platform': 'Platform',
        'generating': 'Generating',
        'completed': 'Completed',
        'failed': 'Failed',
        'processing': 'Processing',
        'analyzing': 'Analyzing',
        'files': 'files',
        'file': 'file',
        'targets': 'targets',
        'target': 'target',
        'telescope': 'Telescope',
        'instrument': 'Instrument',
        'filter': 'Filter',
        'filters': 'Filters',
        'images': 'Images',
        'total_time': 'Total time',
        'average_time': 'Average time',
        'observation_time': 'Observation time',
        'number_of_images': 'Number of images',
        'detailed_exposure_times': 'Detailed Exposure Times by Filter',
        'no_filter_info': 'No filter information available',
        'no_filter_info_night': 'No filter information available for this night',
        'thumbnail_generation': 'THUMBNAIL GENERATION OPTION',
        'thumbnail_question': 'Do you want to generate thumbnails in your LaTeX report?',
        'thumbnail_info1': '• Thumbnails show preview images of each target',
        'thumbnail_info2': '• Generation takes additional time but improves report quality',
        'thumbnail_info3': '• Default: NO (press Enter for NO, or type \'y\' for YES)',
        'thumbnail_prompt': 'Generate thumbnails? (y/N):',
        'thumbnail_yes': 'Thumbnails will be generated',
        'thumbnail_no': 'Thumbnails will NOT be generated',
        'thumbnail_no_error': 'Thumbnails will NOT be generated (input error)',
        'thumbnail_no_fallback': 'Thumbnails will NOT be generated (fallback)',
        'latex_compilation': 'LaTeX compilation',
        'first_pass': 'First pass',
        'second_pass': 'Second pass (cross-references and bookmarks)',
        'third_pass': 'Third pass (finalize bookmarks)',
        'pdf_generated': 'PDF generated successfully',
        'bookmarks_generated': 'Bookmarks generated in PDF',
        'compilation_failed': 'LaTeX compilation failed',
        'latex_file_available': 'LaTeX report file available',
        'compile_online': 'You can compile it online with Overleaf',
        'compilation_timeout': 'LaTeX compilation timed out',
        'latex_not_found': 'LaTeX executable not found in PATH',
        # Additional translations for full coverage
        'auto_config': 'AUTOMATIC CONFIGURATION',
        'checking_deps': 'Checking and installing dependencies',
        'all_deps_ok': 'All required dependencies are installed!',
        'some_deps_failed': 'Some required dependencies could not be installed',
        'installing': 'Installing',
        'installed_ok': 'installed successfully',
        'install_failed': 'Failed to install',
        'output_folder': 'Output folder',
        'analysis_folder': 'Analysis folder',
        'workers_label': 'Workers',
        'starting_analysis': 'Starting FITS analysis',
        'grouping_targets': 'Grouping targets',
        'generating_graphs': 'Generating graphs',
        'generating_latex': 'Generating LaTeX report',
        'exporting_csv': 'Exporting CSV data',
        'compressing': 'Compressing output',
        'analysis_complete': 'Analysis completed successfully',
        'no_fits_found': 'No FITS files found',
        'stopped_by_user': 'Stopped by user',
        'csv_export': 'CSV data export',
        'writing_global_csv': 'Writing global CSV file',
        'writing_targets_csv': 'Writing targets CSV file',
        'csv_files_generated': 'CSV files generated',
        'deduplication': 'Deduplication',
        'files_ignored': 'file(s) ignored (preferred version found)',
        'searching_files': 'Searching for FITS/XISF files',
        'unique_files_found': 'unique file(s) found',
        'dedup_compressed': 'Deduplication of compressed versions',
        'files_retained': 'file(s) retained',
        'duplicates_removed': 'duplicate(s) removed',
        'no_duplicates': 'no duplicates detected',
        'phase1': 'Phase 1: Searching files',
        'phase2': 'Phase 2: Reading signatures',
        'phase3': 'Phase 3: Filtering headers',
        'phase4': 'Phase 4: Full analysis',
        'phase5': 'Phase 5: Compression',
        'parallel_processing': 'Parallel processing with',
        'sequential_processing': 'Sequential processing (1 worker)',
        'system_config': 'System configuration detected',
        'cpu_cores': 'CPU cores',
        'ram': 'RAM',
        'storage': 'Storage',
        'optimized_workers': 'Optimized workers',
        'hdd_detected': 'HDD storage detected: reducing workers to avoid disk contention',
        'ssd_assumed': 'SSD (assumed)',
        'fast_mode': 'Fast mode enabled',
        'header_only': 'Header-only mode (optimized)',
        'progress_details': 'Progress Details',
        'fast_processing': 'Fast processing',
        'total_files': 'Total files',
        'processing_complete': 'File processing completed',
        'launching_gui': 'Launching graphical interface',
        'gui_not_available': 'PyQt6 is not available for GUI mode',
        'install_pyqt6': 'Install with: pip install PyQt6',
        'use_cli_mode': 'Or use CLI mode',
        'fallback_cli': 'Falling back to CLI mode',
    },
    'fr': {
        # Messages communs
        'warning': 'AVERTISSEMENT',
        'error': 'ERREUR',
        'success': 'SUCCÈS',
        'info': 'INFO',
        'platform': 'Plateforme',
        'generating': 'Génération',
        'completed': 'Terminé',
        'failed': 'Échoué',
        'processing': 'Traitement',
        'analyzing': 'Analyse',
        'files': 'fichiers',
        'file': 'fichier',
        'targets': 'cibles',
        'target': 'cible',
        'telescope': 'Télescope',
        'instrument': 'Instrument',
        'filter': 'Filtre',
        'filters': 'Filtres',
        'images': 'Images',
        'total_time': 'Temps total',
        'average_time': 'Temps moyen',
        'observation_time': 'Temps d\'observation',
        'number_of_images': 'Nombre d\'images',
        'detailed_exposure_times': 'Temps d\'exposition détaillés par filtre',
        'no_filter_info': 'Aucune information de filtre disponible',
        'no_filter_info_night': 'Aucune information de filtre disponible pour cette nuit',
        'thumbnail_generation': 'OPTION DE GÉNÉRATION DE MINIATURES',
        'thumbnail_question': 'Voulez-vous générer des miniatures dans votre rapport LaTeX ?',
        'thumbnail_info1': '• Les miniatures affichent des images d\'aperçu de chaque cible',
        'thumbnail_info2': '• La génération prend du temps supplémentaire mais améliore la qualité du rapport',
        'thumbnail_info3': '• Par défaut : NON (appuyez sur Entrée pour NON, ou tapez \'y\' pour OUI)',
        'thumbnail_prompt': 'Générer des miniatures ? (y/N) :',
        'thumbnail_yes': 'Les miniatures seront générées',
        'thumbnail_no': 'Les miniatures ne seront PAS générées',
        'thumbnail_no_error': 'Les miniatures ne seront PAS générées (erreur de saisie)',
        'thumbnail_no_fallback': 'Les miniatures ne seront PAS générées (solution de repli)',
        'latex_compilation': 'Compilation LaTeX',
        'first_pass': 'Première passe',
        'second_pass': 'Deuxième passe (références croisées et signets)',
        'third_pass': 'Troisième passe (finalisation des signets)',
        'pdf_generated': 'PDF généré avec succès',
        'bookmarks_generated': 'Signets générés dans le PDF',
        'compilation_failed': 'La compilation LaTeX a échoué',
        'latex_file_available': 'Fichier LaTeX disponible',
        'compile_online': 'Vous pouvez le compiler en ligne avec Overleaf',
        'compilation_timeout': 'La compilation LaTeX a expiré',
        'latex_not_found': 'Exécutable LaTeX introuvable dans PATH',
        # Traductions supplémentaires pour couverture complète
        'auto_config': 'CONFIGURATION AUTOMATIQUE',
        'checking_deps': 'Vérification et installation des dépendances',
        'all_deps_ok': 'Toutes les dépendances requises sont installées !',
        'some_deps_failed': 'Certaines dépendances n\'ont pas pu être installées',
        'installing': 'Installation de',
        'installed_ok': 'installé avec succès',
        'install_failed': 'Échec de l\'installation de',
        'output_folder': 'Dossier de sortie',
        'analysis_folder': 'Dossier d\'analyse',
        'workers_label': 'Workers',
        'starting_analysis': 'Démarrage de l\'analyse FITS',
        'grouping_targets': 'Regroupement des cibles',
        'generating_graphs': 'Génération des graphiques',
        'generating_latex': 'Génération du rapport LaTeX',
        'exporting_csv': 'Export des données CSV',
        'compressing': 'Compression de la sortie',
        'analysis_complete': 'Analyse terminée avec succès',
        'no_fits_found': 'Aucun fichier FITS trouvé',
        'stopped_by_user': 'Arrêté par l\'utilisateur',
        'csv_export': 'Export des données en CSV',
        'writing_global_csv': 'Écriture du fichier CSV global',
        'writing_targets_csv': 'Écriture du fichier CSV des cibles',
        'csv_files_generated': 'Fichiers CSV générés',
        'deduplication': 'Déduplication',
        'files_ignored': 'fichier(s) ignoré(s) (version préférée trouvée)',
        'searching_files': 'Recherche des fichiers FITS/XISF',
        'unique_files_found': 'fichier(s) unique(s) trouvé(s)',
        'dedup_compressed': 'Déduplication des versions compressées',
        'files_retained': 'fichier(s) retenu(s)',
        'duplicates_removed': 'doublon(s) supprimé(s)',
        'no_duplicates': 'aucun doublon détecté',
        'phase1': 'Phase 1 : Recherche des fichiers',
        'phase2': 'Phase 2 : Lecture des signatures',
        'phase3': 'Phase 3 : Filtrage des headers',
        'phase4': 'Phase 4 : Analyse complète',
        'phase5': 'Phase 5 : Compression',
        'parallel_processing': 'Traitement parallèle avec',
        'sequential_processing': 'Traitement séquentiel (1 worker)',
        'system_config': 'Configuration système détectée',
        'cpu_cores': 'Cœurs CPU',
        'ram': 'RAM',
        'storage': 'Stockage',
        'optimized_workers': 'Workers optimisés',
        'hdd_detected': 'Stockage HDD détecté : réduction des workers pour éviter la contention disque',
        'ssd_assumed': 'SSD (supposé)',
        'fast_mode': 'Mode rapide activé',
        'header_only': 'Mode header uniquement (optimisé)',
        'progress_details': 'Détails de progression',
        'fast_processing': 'Traitement rapide',
        'total_files': 'Total fichiers',
        'processing_complete': 'Traitement des fichiers terminé',
        'launching_gui': 'Lancement de l\'interface graphique',
        'gui_not_available': 'PyQt6 n\'est pas disponible pour le mode GUI',
        'install_pyqt6': 'Installez avec : pip install PyQt6',
        'use_cli_mode': 'Ou utilisez le mode CLI',
        'fallback_cli': 'Basculement vers le mode CLI',
    }
}

def _(key):
    """Translation function - returns translated string or key if not found"""
    return TRANSLATIONS.get(SYSTEM_LANGUAGE, TRANSLATIONS['en']).get(key, key)

try:
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("WARNING: Matplotlib/NumPy/Pandas not installed. Charts disabled.")
    print("   Install with: pip install matplotlib numpy pandas")

try:
    from astropy.io import fits
    from astropy import units as u
    from astropy.coordinates import SkyCoord
    import astropy.units as units
    ASTROPY_AVAILABLE = True
except ImportError:
    ASTROPY_AVAILABLE = False
    print("WARNING: Astropy not installed. Cannot read FITS headers.")
    print("   Install with: pip install astropy")

import sys
import subprocess

def _ensure_xisf_installed():
    """
    Ensure that the 'xisf' parser library is available.
    If not installed, tries to install it automatically with pip.
    Falls back gracefully if installation fails.
    """
    global XISF_AVAILABLE
    try:
        from xisf import XISF  # noqa: F401
        XISF_AVAILABLE = True
        return
    except ImportError:
        pass

    print("INFO: 'xisf' library not found, attempting automatic installation (pip install xisf)...")
    try:
        # Use the same Python interpreter that runs this script
        subprocess.check_call([sys.executable, "-m", "pip", "install", "xisf"])
        from xisf import XISF  # noqa: F401
        XISF_AVAILABLE = True
        print("INFO: 'xisf' library installed successfully.")
    except Exception as e:
        XISF_AVAILABLE = False
        print("WARNING: automatic installation of 'xisf' failed. XISF files will be handled with fallback parser only.")
        print(f"   Error: {e}")
        print("   You can install it manually with: pip install xisf")

try:
    from xisf import XISF
    XISF_AVAILABLE = True
except ImportError:
    # Try to install xisf automatically, then re-import
    XISF_AVAILABLE = False
    _ensure_xisf_installed()

try:
    from astroquery.simbad import Simbad
    SIMBAD_AVAILABLE = True
except ImportError:
    SIMBAD_AVAILABLE = False

# Suppress common FITS warnings to reduce noise (only if astropy is available)
if ASTROPY_AVAILABLE:
    try:
        import warnings
        
        # Suppress all astropy.io.fits warnings comprehensively
        try:
            from astropy.io.fits.verify import VerifyWarning
            # Suppress all VerifyWarning messages
            warnings.filterwarnings('ignore', category=VerifyWarning)
        except ImportError:
            pass
        
        try:
            from astropy.io.fits.util import UserWarning as FitsUserWarning
            # Suppress all FitsUserWarning messages
            warnings.filterwarnings('ignore', category=FitsUserWarning)
        except ImportError:
            pass
        
        # Also filter by module name as a catch-all
        warnings.filterwarnings('ignore', module='astropy.io.fits')
        warnings.filterwarnings('ignore', module='astropy.io.fits.card')
        warnings.filterwarnings('ignore', module='astropy.io.fits.util')
        warnings.filterwarnings('ignore', module='astropy.io.fits.verify')
        
        # Filter specific warning messages by pattern (more specific patterns)
        warnings.filterwarnings('ignore', message='.*non-ASCII characters.*')
        warnings.filterwarnings('ignore', message='.*null bytes.*')
        warnings.filterwarnings('ignore', message='.*Header block contains null bytes.*')
        warnings.filterwarnings('ignore', message='.*FITS-compliant.*')
        warnings.filterwarnings('ignore', message='.*Keyword name.*is greater than 8 characters.*')
        warnings.filterwarnings('ignore', message='.*contains characters not allowed by the FITS standard.*')
        warnings.filterwarnings('ignore', message='.*HIERARCH card will be created.*')
        warnings.filterwarnings('ignore', message='.*COMMENT_.*')
        warnings.filterwarnings('ignore', message='.*COMMENT_1.*')
        warnings.filterwarnings('ignore', message='.*COMMENT_2.*')
        warnings.filterwarnings('ignore', message='.*COMMENT_3.*')
        
    except Exception:
        # If anything fails, continue silently
        pass

try:
    from tqdm import tqdm
    import os
    # Force tqdm to use colors and disable dynamic columns
    os.environ['TQDM_DISABLE'] = '0'
    os.environ['TQDM_COLOUR'] = '#00FF00'
    # Disable dynamic columns to prevent bar from disappearing
    os.environ['TQDM_DYNAMIC_NCOLS'] = '0'
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("WARNING: tqdm not available, progress bars disabled.")
    print("   Install with: pip install tqdm")

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("WARNING: reportlab not available, PDF generation without LaTeX disabled.")
    print("   Install with: pip install reportlab")

# Recognized filters with their central wavelengths (nm)
FILTERS_INFO = {
    'HA': {'name': 'Hydrogen Alpha', 'lambda': 656.3, 'width': 4.5},
    'Ha': {'name': 'Hydrogen Alpha', 'lambda': 656.3, 'width': 4.5},  # Alternative spelling
    'OIII': {'name': 'Oxygen III', 'lambda': 500.7, 'width': 4.5},
    'O3': {'name': 'Oxygen III', 'lambda': 500.7, 'width': 4.5},  # Alternative spelling
    'SII': {'name': 'Sulfur II', 'lambda': 672.4, 'width': 4.5},
    'S2': {'name': 'Sulfur II', 'lambda': 672.4, 'width': 4.5},  # Alternative spelling
    'L': {'name': 'Luminance', 'lambda': 550.0, 'width': 400.0},
    'LUM': {'name': 'Luminance', 'lambda': 550.0, 'width': 400.0},  # Alternative spelling
    'R': {'name': 'Red', 'lambda': 650.0, 'width': 100.0},
    'G': {'name': 'Green', 'lambda': 550.0, 'width': 100.0},
    'B': {'name': 'Blue', 'lambda': 450.0, 'width': 100.0},
    'RGB': {'name': 'Color (OSC RGB)', 'lambda': 550.0, 'width': 400.0},
    'OSC': {'name': 'One-Shot Color', 'lambda': 550.0, 'width': 400.0},
    # Additional narrowband filters
    'HBETA': {'name': 'Hydrogen Beta', 'lambda': 486.1, 'width': 4.5},
    'HB': {'name': 'Hydrogen Beta', 'lambda': 486.1, 'width': 4.5},
    'H-BETA': {'name': 'Hydrogen Beta', 'lambda': 486.1, 'width': 4.5},
    'HGAMMA': {'name': 'Hydrogen Gamma', 'lambda': 434.0, 'width': 4.5},
    'HG': {'name': 'Hydrogen Gamma', 'lambda': 434.0, 'width': 4.5},
    'H-GAMMA': {'name': 'Hydrogen Gamma', 'lambda': 434.0, 'width': 4.5},
    'HDELTA': {'name': 'Hydrogen Delta', 'lambda': 410.2, 'width': 4.5},
    'HD': {'name': 'Hydrogen Delta', 'lambda': 410.2, 'width': 4.5},
    'H-DELTA': {'name': 'Hydrogen Delta', 'lambda': 410.2, 'width': 4.5},
    'HEPSILON': {'name': 'Hydrogen Epsilon', 'lambda': 397.0, 'width': 4.5},
    'HZETA': {'name': 'Hydrogen Zeta', 'lambda': 388.9, 'width': 4.5},
    'HETA': {'name': 'Hydrogen Eta', 'lambda': 383.5, 'width': 4.5},
    'HTHETA': {'name': 'Hydrogen Theta', 'lambda': 379.8, 'width': 4.5},
    'HIOTA': {'name': 'Hydrogen Iota', 'lambda': 377.1, 'width': 4.5},
    'HKAPPA': {'name': 'Hydrogen Kappa', 'lambda': 375.0, 'width': 4.5},
    'HLAMBDA': {'name': 'Hydrogen Lambda', 'lambda': 373.4, 'width': 4.5},
    'HMU': {'name': 'Hydrogen Mu', 'lambda': 371.2, 'width': 4.5},
    'HNU': {'name': 'Hydrogen Nu', 'lambda': 369.7, 'width': 4.5},
    'HXI': {'name': 'Hydrogen Xi', 'lambda': 368.3, 'width': 4.5},
    'HOMICRON': {'name': 'Hydrogen Omicron', 'lambda': 367.1, 'width': 4.5},
    'HPI': {'name': 'Hydrogen Pi', 'lambda': 366.0, 'width': 4.5},
    'HRHO': {'name': 'Hydrogen Rho', 'lambda': 365.0, 'width': 4.5},
    'HSIGMA': {'name': 'Hydrogen Sigma', 'lambda': 364.1, 'width': 4.5},
    'HTAU': {'name': 'Hydrogen Tau', 'lambda': 363.3, 'width': 4.5},
    'HUPSILON': {'name': 'Hydrogen Upsilon', 'lambda': 362.6, 'width': 4.5},
    'HPHI': {'name': 'Hydrogen Phi', 'lambda': 361.9, 'width': 4.5},
    'HCHI': {'name': 'Hydrogen Chi', 'lambda': 361.3, 'width': 4.5},
    'HPSI': {'name': 'Hydrogen Psi', 'lambda': 360.7, 'width': 4.5},
    'HOMEGA': {'name': 'Hydrogen Omega', 'lambda': 360.1, 'width': 4.5},
    'NII': {'name': 'Nitrogen II', 'lambda': 658.4, 'width': 4.5},
    'N2': {'name': 'Nitrogen II', 'lambda': 658.4, 'width': 4.5},
    'OI': {'name': 'Oxygen I', 'lambda': 630.0, 'width': 4.5},
    'OII': {'name': 'Oxygen II', 'lambda': 372.7, 'width': 4.5},
    'SIII': {'name': 'Sulfur III', 'lambda': 906.9, 'width': 10.0},
    'S3': {'name': 'Sulfur III', 'lambda': 906.9, 'width': 10.0},
    'HEII': {'name': 'Helium II', 'lambda': 468.6, 'width': 4.5},
    # Broadband photometric (Johnson-Cousins)
    'U': {'name': 'Ultraviolet (Johnson U)', 'lambda': 365.0, 'width': 60.0},
    'V': {'name': 'Visual (Johnson V)', 'lambda': 551.0, 'width': 88.0},
    'I': {'name': 'Infrared (Cousins I)', 'lambda': 806.0, 'width': 149.0},
    'RC': {'name': 'Red (Cousins R)', 'lambda': 658.0, 'width': 138.0},
    'IC': {'name': 'Infrared (Cousins I)', 'lambda': 806.0, 'width': 149.0},
    # Sloan/SDSS
    'U_SDSS': {'name': 'Sloan u′', 'lambda': 355.1, 'width': 59.0},
    'G_SDSS': {'name': 'Sloan g′', 'lambda': 475.9, 'width': 138.0},
    'R_SDSS': {'name': 'Sloan r′', 'lambda': 622.3, 'width': 138.0},
    'I_SDSS': {'name': 'Sloan i′', 'lambda': 763.2, 'width': 152.0},
    'Z_SDSS': {'name': 'Sloan z′', 'lambda': 905.5, 'width': 94.0},
    'U_SLOAN': {'name': 'Sloan u′', 'lambda': 355.1, 'width': 59.0},
    'G_SLOAN': {'name': 'Sloan g′', 'lambda': 475.9, 'width': 138.0},
    'R_SLOAN': {'name': 'Sloan r′', 'lambda': 622.3, 'width': 138.0},
    'I_SLOAN': {'name': 'Sloan i′', 'lambda': 763.2, 'width': 152.0},
    'Z_SLOAN': {'name': 'Sloan z′', 'lambda': 905.5, 'width': 94.0},
    # Utility/clear filters
    'CLEAR': {'name': 'Clear', 'lambda': 550.0, 'width': 400.0},
    'IRCUT': {'name': 'IR Cut', 'lambda': 550.0, 'width': 400.0},
    'UVIR': {'name': 'UV/IR Block', 'lambda': 550.0, 'width': 400.0},
    'UV-IR': {'name': 'UV/IR Block', 'lambda': 550.0, 'width': 400.0},
    # Rare noble gas lines (Argon)
    'ARIII': {'name': 'Argon III', 'lambda': 713.6, 'width': 10.0},
    'ARIV': {'name': 'Argon IV', 'lambda': 474.0, 'width': 10.0},
    'ARV': {'name': 'Argon V', 'lambda': 700.0, 'width': 10.0},
    'ARGON': {'name': 'Argon (generic)', 'lambda': 706.7, 'width': 10.0},
    # Other rare/line filters
    'NEON': {'name': 'Neon (generic)', 'lambda': 640.2, 'width': 10.0},
    'KR': {'name': 'Krypton (generic)', 'lambda': 758.7, 'width': 10.0},
    'KRYPTON': {'name': 'Krypton (generic)', 'lambda': 758.7, 'width': 10.0},
    'XE': {'name': 'Xenon (generic)', 'lambda': 823.2, 'width': 10.0},
    'XENON': {'name': 'Xenon (generic)', 'lambda': 823.2, 'width': 10.0},
    'HEI': {'name': 'Helium I', 'lambda': 587.6, 'width': 10.0},
    'NA': {'name': 'Sodium D', 'lambda': 589.3, 'width': 6.0},
    'SODIUM': {'name': 'Sodium D', 'lambda': 589.3, 'width': 6.0},
    'K': {'name': 'Potassium', 'lambda': 769.9, 'width': 6.0},
    'CAK': {'name': 'Calcium K', 'lambda': 393.4, 'width': 2.0},
    'CAH': {'name': 'Calcium H', 'lambda': 396.8, 'width': 2.0},
    'OI_5577': {'name': 'Oxygen I (airglow)', 'lambda': 557.7, 'width': 3.0},
    'OI_6300': {'name': 'Oxygen I', 'lambda': 630.0, 'width': 3.0},
    'OI_6364': {'name': 'Oxygen I', 'lambda': 636.4, 'width': 3.0},
    'SIII_9531': {'name': 'Sulfur III', 'lambda': 953.1, 'width': 10.0},
    'CH4': {'name': 'Methane', 'lambda': 889.0, 'width': 10.0},
    # Light pollution suppression and multiband filters (typical central bands ref.)
    'CLS': {'name': 'City Light Suppression (CLS)', 'lambda': 550.0, 'width': 200.0},
    'UHC': {'name': 'Ultra High Contrast (UHC)', 'lambda': 500.0, 'width': 200.0},
    'LPRO': {'name': 'Optolong L-Pro', 'lambda': 550.0, 'width': 300.0},
    'LPRO_OPTOLONG': {'name': 'Optolong L-Pro', 'lambda': 550.0, 'width': 300.0},
    'LEHNANCE': {'name': 'Optolong L-eNhance (dual-band)', 'lambda': 600.0, 'width': 20.0},
    'LEXTREME': {'name': 'Optolong L-eXtreme (dual-band)', 'lambda': 600.0, 'width': 14.0},
    'LULTIMATE': {'name': 'Optolong L-Ultimate (dual-band)', 'lambda': 600.0, 'width': 7.0},
    'IDAS_LPS': {'name': 'IDAS LPS', 'lambda': 550.0, 'width': 200.0},
    'IDAS_LPS_D1': {'name': 'IDAS LPS D1', 'lambda': 550.0, 'width': 200.0},
    'IDAS_LPS_D2': {'name': 'IDAS LPS D2', 'lambda': 550.0, 'width': 200.0},
    'IDAS_LPS_NBZ': {'name': 'IDAS NBZ (dual-band)', 'lambda': 600.0, 'width': 20.0},
    'NBZ': {'name': 'IDAS NBZ (dual-band)', 'lambda': 600.0, 'width': 20.0},
    # IDAS NBZ II: dual-band H-alpha (9.5 nm) + OIII (8 nm) for OSC
    'IDAS_NBZ_II': {'name': 'IDAS NBZ II (dual-band)', 'lambda': 578.0, 'width': 9.5},
    # IDAS NB3: dual-band OIII + SII for OSC (nebula booster)
    'IDAS_NB3': {'name': 'IDAS NB3 (dual-band)', 'lambda': 586.0, 'width': 12.0},
    'TRIBAND': {'name': 'Tri-band', 'lambda': 600.0, 'width': 30.0},
    'QUAD_BAND': {'name': 'Quad-band', 'lambda': 600.0, 'width': 40.0}
}

def create_enhanced_progress_bar(iterable, total, desc, unit="file"):
    """Create an enhanced progress bar with better visibility and formatting"""
    if not TQDM_AVAILABLE:
        return iterable
    
    return tqdm(
        iterable,
        total=total,
        desc=desc,
        unit=unit,
        bar_format='{l_bar}🟢{bar}🟢| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
        colour='green',
        leave=True,
        position=0,
        ncols=100,
        mininterval=0.05,
        maxinterval=0.5,
        dynamic_ncols=False,
        ascii=False,
        smoothing=0.1
    )

def print_progress_info(adu_tasks, non_adu_tasks, total_tasks):
    """Print detailed progress information"""
    if SYSTEM_LANGUAGE == 'fr':
        print(f"📊 Détails du traitement:")
        if total_tasks > 0:
            print(f"   ⚡ Traitement rapide: {total_tasks} fichiers (100.0%)")
        else:
            print(f"   ⚡ Traitement rapide: {total_tasks} fichiers (0.0%)")
        print(f"   📁 Total: {total_tasks} fichiers")
        print(f"   🎯 La barre de progression affichera le statut en temps réel...")
    else:
        print(f"📊 Progress Details:")
        if total_tasks > 0:
            print(f"   ⚡ Fast processing: {total_tasks} files (100.0%)")
        else:
            print(f"   ⚡ Fast processing: {total_tasks} files (0.0%)")
        print(f"   📁 Total: {total_tasks} files")
        print(f"   🎯 Progress bar will show real-time status...")
    print()

def print_progress_completion():
    """Print completion message for progress"""
    print()
    if SYSTEM_LANGUAGE == 'fr':
        print("✅ Traitement des fichiers terminé!")
        print("   📈 La barre de progression restera visible jusqu'à la fin de l'analyse.")
    else:
        print("✅ File processing completed!")
        print("   📈 Progress bar will remain visible until analysis is finished.")
    print()

def parse_args():
    parser = argparse.ArgumentParser(description="Complete Astrophotography Analysis (CLI)")
    parser.add_argument("--folder", type=str, default=None, help="FITS folder to analyze (default: script folder)")
    parser.add_argument("--mode", type=int, choices=[1], default=1, help="Analysis mode: 1=fast (theoretical calculation only)")
    parser.add_argument("--region-size", type=int, default=100, help="Size (px) of advanced SNR regions")
    parser.add_argument("--output", type=str, default=None, help="Output folder")
    parser.add_argument("--no-graphs", action="store_true", help="Do not generate graphs")
    parser.add_argument("--no-latex", action="store_true", help="Do not generate LaTeX files")
    parser.add_argument("--auto-install", action="store_true", help="Automatically install missing Python packages")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for sampling")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers (default: auto-detect CPU cores)")
    parser.add_argument("--export-csv", action="store_true", help="Export CSV summaries")
    parser.add_argument("--resolve-simbad", action="store_true",
                        help="Resolve targets via SIMBAD to merge duplicate names (e.g. M31 = NGC 224) and get object details")
    parser.add_argument("--zip-output", action="store_true", help="Compress output folder to .zip")
    # Storage optimization options
    parser.add_argument("--optimize-storage", type=str, default=None, metavar="FOLDER",
                        help="Optimize storage: compress FITS→XISF, extract duplicates to FOLDER")
    parser.add_argument("--prefer-format", type=str, choices=['fits', 'xisf', 'fz'], default='xisf',
                        help="Preferred format to keep: xisf (default), fits, or fz")
    parser.add_argument("--no-compress", action="store_true",
                        help="With --optimize-storage: don't compress FITS to XISF, only extract duplicates")
    return parser.parse_args()

def export_csv(data_by_target, global_data, output_folder):
    if SYSTEM_LANGUAGE == 'fr':
        print(f"📊 Export des données en CSV...")
    else:
        print(f"📊 Exporting data to CSV...")
    import csv
    global_path = os.path.join(output_folder, "global_summary.csv")
    if SYSTEM_LANGUAGE == 'fr':
        print(f"   📝 Écriture du fichier CSV global...")
    else:
        print(f"   📝 Writing global CSV file...")
    with open(global_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["total_files","targets","instruments","telescopes","total_time"])
        w.writerow([
            global_data.get('total_files', 0),
            len(global_data.get('found_targets', [])),
            len(global_data.get('used_instruments', [])),
            len(global_data.get('used_telescopes', [])),
            global_data.get('total_time', 0)
        ])
    targets_path = os.path.join(output_folder, "targets_summary.csv")
    if SYSTEM_LANGUAGE == 'fr':
        print(f"   📝 Écriture du fichier CSV des cibles...")
    else:
        print(f"   📝 Writing targets CSV file...")
    with open(targets_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["target","nb_files","filters","instruments","telescopes","total_duration_s"])
        for target, d in data_by_target.items():
            nb = len(d.get('files', []))
            filters = ",".join(sorted(d.get('time_by_filter', {}).keys()))
            # time_by_filter values are lists of exposure times per filter
            total_duration_s = sum(sum(times) if isinstance(times, list) else times for times in d.get('time_by_filter', {}).values())
            w.writerow([
                target, nb, filters,
                len(d.get('instruments', [])), len(d.get('telescopes', [])),
                total_duration_s
            ])
    if SYSTEM_LANGUAGE == 'fr':
        print(f"   ✓ Fichiers CSV générés: {os.path.basename(global_path)}, {os.path.basename(targets_path)}")
    else:
        print(f"   ✓ CSV files generated: {os.path.basename(global_path)}, {os.path.basename(targets_path)}")


def export_astrobin_csv(data_by_target, global_data, output_folder):
    """
    Export acquisition data in AstroBin-compatible CSV format.
    Creates a subfolder structure: astrobin_exports/<equipment>/<target>/<equipment>_<target>_acquisition.csv
    Telescope and instrument are treated as one concept (équipement / lunette).

    AstroBin CSV format (for long exposure):
    date,filter,number,duration,binning,gain,sensorCooling,bortle,meanFwhm,temperature

    Required fields: number, duration
    Optional fields: all others

    Each unique combination of (date, filter, duration, binning, gain, sensorCooling) produces
    a separate row, ensuring multi-night sessions with varying parameters are fully detailed.
    """
    if SYSTEM_LANGUAGE == 'fr':
        print(f"🌟 Export des données pour AstroBin...")
    else:
        print(f"🌟 Exporting data for AstroBin...")

    import csv
    from collections import defaultdict

    # AstroBin filter name → numeric ID mapping (common astrophotography filters)
    # These IDs come from the AstroBin filter database
    ASTROBIN_FILTER_IDS = {
        'luminance': '2906', 'lum': '2906', 'l': '2906', 'clear': '2906',
        'red': '4649', 'r': '4649',
        'green': '4643', 'g': '4643',
        'blue': '4637', 'b': '4637',
        'ha': '4663', 'h-alpha': '4663', 'halpha': '4663',
        'oiii': '4752', 'o-iii': '4752', 'o3': '4752',
        'sii': '4844', 's-ii': '4844', 's2': '4844',
        'nii': '4846', 'n-ii': '4846', 'n2': '4846',
    }

    def _filter_to_astrobin(name):
        """Convert filter name to AstroBin numeric ID if known, else keep name."""
        if not name or name == 'Unknown':
            return ''
        key = str(name).strip().lower().replace(' ', '').replace('_', '')
        return ASTROBIN_FILTER_IDS.get(key, name)

    def _clean_date(obs_date):
        """Normalize observation date to YYYY-MM-DD format."""
        if not obs_date:
            return ''
        obs_date = str(obs_date).strip()
        if 'T' in obs_date:
            obs_date = obs_date.split('T')[0]
        obs_date = obs_date.replace('/', '-').replace(' night', '').strip()
        if len(obs_date) == 8 and obs_date.isdigit():
            obs_date = f"{obs_date[:4]}-{obs_date[4:6]}-{obs_date[6:8]}"
        return obs_date

    def _clean_binning(binning):
        """Normalize binning to integer (1-4)."""
        if not binning:
            return ''
        b = str(binning).strip()
        if 'x' in b.lower():
            b = b.lower().split('x')[0]
        try:
            val = int(float(b))
            return str(val) if 1 <= val <= 4 else ''
        except (ValueError, TypeError):
            return ''

    def _clean_gain(gain):
        """Normalize gain to up to 2 decimal places."""
        if gain is None or gain == '':
            return ''
        try:
            val = float(gain)
            return f"{val:.2f}" if val != int(val) else str(int(val))
        except (ValueError, TypeError):
            return ''

    def _clean_temp(temp):
        """Normalize sensor cooling temperature to integer °C."""
        if temp is None or temp == '':
            return ''
        try:
            return str(int(round(float(temp))))
        except (ValueError, TypeError):
            return ''

    # Create main AstroBin export folder
    astrobin_folder = os.path.join(output_folder, "astrobin_exports")
    os.makedirs(astrobin_folder, exist_ok=True)

    # Reorganize by equipment -> target
    # Each acquisition row is keyed by (date, filter, duration, binning, gain, temp) for accurate multi-night detail
    # Structure: {setup_name: {target: {acq_key: count}}}
    data_by_setup = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    for target, data in data_by_target.items():
        # Skip calibration targets
        target_upper = target.upper()
        if any(cal in target_upper for cal in ['BIAS', 'DARK', 'FLAT', 'CALIBRATION']):
            continue

        files = data.get('files', [])
        files_by_date = data.get('files_by_date', {})

        telescopes = list(data.get('telescopes', ['Unknown']))
        instruments = list(data.get('instruments', ['Unknown']))

        if files:
            for file_item in files:
                if not isinstance(file_item, dict):
                    continue
                info = file_item.get('info')
                if not info:
                    continue
                if info.get('type') not in (None, 'LIGHT'):
                    continue
                inner = info.get('info') or {}
                telescope = (inner.get('telescope') or info.get('telescope') or 'Unknown')
                if isinstance(telescope, str):
                    telescope = telescope.strip() or 'Unknown'
                instrument = (inner.get('instrument') or info.get('instrument') or 'Unknown')
                if isinstance(instrument, str):
                    instrument = instrument.strip() or 'Unknown'
                setup_name = get_equipment_name(telescope, instrument)

                obs_date = _clean_date(info.get('observation_date') or info.get('date_obs') or inner.get('date_obs') or '')
                if not obs_date:
                    continue

                filter_name = (info.get('filter') or 'Unknown')
                if isinstance(filter_name, str):
                    filter_name = filter_name.strip() or 'Unknown'

                exposure = info.get('exposure_time') or info.get('exptime') or 0
                try:
                    exposure = float(exposure) if exposure is not None else 0
                except (TypeError, ValueError):
                    exposure = 0
                if exposure <= 0:
                    continue

                # Extract per-file acquisition parameters
                binning = _clean_binning(inner.get('binning') or info.get('binning', ''))
                gain = _clean_gain(inner.get('gain') or info.get('gain', ''))
                temp = _clean_temp(inner.get('sensor_temp') or inner.get('temperature') or info.get('sensor_temp') or info.get('ccd_temp', ''))

                # Key: unique combination = unique CSV row
                acq_key = (obs_date, filter_name, exposure, binning, gain, temp)
                data_by_setup[setup_name][target][acq_key] += 1

        elif files_by_date:
            telescope = telescopes[0] if telescopes else 'Unknown'
            instrument = instruments[0] if instruments else 'Unknown'
            setup_name = get_equipment_name(telescope, instrument)

            for date_str, date_data in files_by_date.items():
                obs_date = _clean_date(date_str)
                if not obs_date:
                    continue

                exposure_details = date_data.get('exposure_details', {})
                time_by_filter = date_data.get('time_by_filter', {})

                if exposure_details:
                    for filter_name, exp_counts in exposure_details.items():
                        for duration, count in exp_counts.items():
                            try:
                                duration = float(duration)
                            except (TypeError, ValueError):
                                continue
                            if duration > 0 and count > 0:
                                acq_key = (obs_date, filter_name, duration, '', '', '')
                                data_by_setup[setup_name][target][acq_key] += count
                elif time_by_filter:
                    for filter_name, time_list in time_by_filter.items():
                        if isinstance(time_list, list):
                            for exp_time in time_list:
                                try:
                                    exp_time = float(exp_time)
                                except (TypeError, ValueError):
                                    continue
                                if exp_time > 0:
                                    acq_key = (obs_date, filter_name, exp_time, '', '', '')
                                    data_by_setup[setup_name][target][acq_key] += 1

    # Export by equipment
    exported_count = 0
    setup_count = 0

    def _setup_sort_key(item):
        setup_name, _ = item
        return (str(setup_name).strip().upper() == 'UNKNOWN',)

    for setup_name, targets in sorted(data_by_setup.items(), key=_setup_sort_key):
        if not targets:
            continue

        safe_setup = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in str(setup_name))
        safe_setup = safe_setup.strip().replace(' ', '_')[:50]
        if not safe_setup or safe_setup.upper() == 'UNKNOWN':
            setup_folder_name = "Unknown_Setup"
        else:
            setup_folder_name = safe_setup

        setup_folder = os.path.join(astrobin_folder, setup_folder_name)
        os.makedirs(setup_folder, exist_ok=True)
        setup_count += 1

        for target, acq_data in targets.items():
            if not acq_data:
                continue

            safe_target = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in target)
            safe_target = safe_target.strip().replace(' ', '_')

            target_folder = os.path.join(setup_folder, safe_target)
            os.makedirs(target_folder, exist_ok=True)

            # Build rows from acq_key tuples
            acquisitions = []
            for acq_key, count in acq_data.items():
                obs_date, filter_name, duration, binning, gain, temp = acq_key
                if count > 0 and duration > 0:
                    acquisitions.append({
                        'date': obs_date,
                        'filter': _filter_to_astrobin(filter_name),
                        'number': count,
                        'duration': duration,
                        'binning': binning,
                        'gain': gain,
                        'sensorCooling': temp,
                    })

            if not acquisitions:
                continue

            # Sort: by date, then filter, then duration
            acquisitions.sort(key=lambda x: (x['date'] or '', x['filter'] or '', x['duration']))

            csv_basename = f"{safe_setup}_{safe_target}_acquisition.csv"
            csv_path = os.path.join(target_folder, csv_basename)
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(['date', 'filter', 'number', 'duration', 'binning', 'gain', 'sensorCooling'])

                for acq in acquisitions:
                    w.writerow([
                        acq['date'],
                        acq['filter'],
                        acq['number'],
                        f"{acq['duration']:.4f}" if isinstance(acq['duration'], float) else acq['duration'],
                        acq['binning'],
                        acq['gain'],
                        acq['sensorCooling'],
                    ])

            exported_count += 1
            if SYSTEM_LANGUAGE == 'fr':
                print(f"   ✓ {setup_folder_name}/{safe_target}/ ({len(acquisitions)} lignes)")
            else:
                print(f"   ✓ {setup_folder_name}/{safe_target}/ ({len(acquisitions)} rows)")
    
    # Create README file
    readme_path = os.path.join(astrobin_folder, "README.txt")
    with open(readme_path, "w", encoding="utf-8") as f:
        if SYSTEM_LANGUAGE == 'fr':
            f.write("EXPORT ASTROBIN - GUIDE D'IMPORTATION\n")
            f.write("=" * 45 + "\n\n")
            f.write("Structure des dossiers:\n")
            f.write("  astrobin_exports/\n")
            f.write("    ├── <equipement>/\n")
            f.write("    │   ├── <cible1>/<equipement>_<cible1>_acquisition.csv\n")
            f.write("    │   └── <cible2>/<equipement>_<cible2>_acquisition.csv\n")
            f.write("    ├── <autre_equipement>/\n")
            f.write("    │   └── <cible1>/<equipement>_<cible1>_acquisition.csv\n")
            f.write("    └── README.txt\n\n")
            f.write("IMPORTANT: La meme cible photographiee avec differents\n")
            f.write("instruments produit des images differentes sur AstroBin.\n")
            f.write("Les CSV sont donc organises par setup d'abord.\n\n")
            f.write("Comment importer dans AstroBin:\n")
            f.write("1. Allez sur votre image dans AstroBin\n")
            f.write("2. Cliquez sur 'Edit' puis 'Acquisition'\n")
            f.write("3. Cliquez sur 'Import from CSV'\n")
            f.write("4. Copiez-collez le contenu du fichier *_acquisition.csv\n")
            f.write("   correspondant a votre setup et cible\n")
            f.write("5. Cliquez sur 'Import'\n\n")
            f.write("Format CSV:\n")
            f.write("date,filter,number,duration,binning,gain,sensorCooling\n\n")
            f.write("Colonnes:\n")
            f.write("  date          - Date observation (AAAA-MM-JJ)\n")
            f.write("  filter        - ID numerique du filtre AstroBin (ou nom)\n")
            f.write("  number        - Nombre de poses\n")
            f.write("  duration      - Duree de pose en secondes\n")
            f.write("  binning       - Binning (1-4)\n")
            f.write("  gain          - Gain camera\n")
            f.write("  sensorCooling - Temperature capteur en degres C\n\n")
            f.write("Chaque combinaison unique de date + filtre + duree +\n")
            f.write("binning + gain + temperature produit une ligne separee.\n")
            f.write("Les sessions multi-nuits sont donc detaillees par nuit.\n\n")
            f.write(f"Setups exportes: {setup_count}\n")
            f.write(f"Fichiers CSV generes: {exported_count}\n")
        else:
            f.write("ASTROBIN EXPORT - IMPORT GUIDE\n")
            f.write("=" * 45 + "\n\n")
            f.write("Folder structure:\n")
            f.write("  astrobin_exports/\n")
            f.write("    ├── <equipment>/\n")
            f.write("    │   ├── <target1>/<equipment>_<target1>_acquisition.csv\n")
            f.write("    │   └── <target2>/<equipment>_<target2>_acquisition.csv\n")
            f.write("    ├── <other_equipment>/\n")
            f.write("    │   └── <target1>/<equipment>_<target1>_acquisition.csv\n")
            f.write("    └── README.txt\n\n")
            f.write("IMPORTANT: The same target photographed with different\n")
            f.write("instruments produces different images on AstroBin.\n")
            f.write("That's why CSVs are organized by setup first.\n\n")
            f.write("How to import into AstroBin:\n")
            f.write("1. Go to your image on AstroBin\n")
            f.write("2. Click 'Edit' then 'Acquisition'\n")
            f.write("3. Click 'Import from CSV'\n")
            f.write("4. Copy-paste the content of the *_acquisition.csv file\n")
            f.write("   corresponding to your setup and target\n")
            f.write("5. Click 'Import'\n\n")
            f.write("CSV Format:\n")
            f.write("date,filter,number,duration,binning,gain,sensorCooling\n\n")
            f.write("Columns:\n")
            f.write("  date          - Observation date (YYYY-MM-DD)\n")
            f.write("  filter        - AstroBin numeric filter ID (or name)\n")
            f.write("  number        - Number of frames\n")
            f.write("  duration      - Exposure time in seconds\n")
            f.write("  binning       - Binning (1-4)\n")
            f.write("  gain          - Camera gain\n")
            f.write("  sensorCooling - Sensor temperature in degrees C\n\n")
            f.write("Each unique combination of date + filter + duration +\n")
            f.write("binning + gain + temperature produces a separate row.\n")
            f.write("Multi-night sessions are fully detailed per night.\n\n")
            f.write(f"Setups exported: {setup_count}\n")
            f.write(f"CSV files generated: {exported_count}\n")
    
    if SYSTEM_LANGUAGE == 'fr':
        print(f"\n   📊 Résumé: {setup_count} setup(s), {exported_count} fichier(s) CSV")
        print(f"   📋 Structure: <équipement>/<cible>/<équipement>_<cible>_acquisition.csv")
        print(f"   💡 Voir README.txt pour les instructions d'importation")
    else:
        print(f"\n   📊 Summary: {setup_count} setup(s), {exported_count} CSV file(s)")
        print(f"   📋 Structure: <equipment>/<target>/<equipment>_<target>_acquisition.csv")
        print(f"   💡 See README.txt for import instructions")


# ============================================================================
# DUPLICATE MANAGEMENT AND XISF COMPRESSION
# ============================================================================

# Global storage for detected duplicates (populated during deduplication)
DETECTED_DUPLICATES = {
    'name_based': [],      # (duplicate_path, kept_path, reason)
    'content_based': [],   # (duplicate_path, kept_path, signature_info)
    'compressed': [],      # (original_fits_path, new_xisf_path, 'compressed')
}

# Global preference for format priority
PREFER_FORMAT = 'xisf'  # Default: prefer XISF (best compression)

def set_prefer_format(fmt):
    """Set the preferred format for deduplication priority"""
    global PREFER_FORMAT
    if fmt in ['fits', 'xisf', 'fz']:
        PREFER_FORMAT = fmt
        # Also set on the function for backward compatibility
        remove_compressed_duplicates.prefer_format = fmt

def get_prefer_format():
    """Get the current preferred format"""
    global PREFER_FORMAT
    return PREFER_FORMAT

def clear_detected_duplicates():
    """Clear the detected duplicates storage"""
    global DETECTED_DUPLICATES
    DETECTED_DUPLICATES = {
        'name_based': [],
        'content_based': [],
        'compressed': [],
    }

def add_detected_duplicate(duplicate_path, kept_path, reason, dup_type='name_based', signature_info=None):
    """Add a detected duplicate to the global storage"""
    global DETECTED_DUPLICATES
    if dup_type == 'name_based':
        DETECTED_DUPLICATES['name_based'].append((str(duplicate_path), str(kept_path), reason))
    elif dup_type == 'content_based':
        DETECTED_DUPLICATES['content_based'].append((str(duplicate_path), str(kept_path), signature_info))
    elif dup_type == 'compressed':
        DETECTED_DUPLICATES['compressed'].append((str(duplicate_path), str(kept_path), reason))

def get_detected_duplicates():
    """Get all detected duplicates"""
    global DETECTED_DUPLICATES
    return DETECTED_DUPLICATES


def optimize_storage(source_root, extraction_folder, prefer_format='xisf', compress_fits=True, workers=1):
    """
    Complete storage optimization workflow:
    
    1. Detect all files (FITS, XISF, FZ)
    2. Group by content signature (identifies true duplicates)
    3. For each group, keep only ONE file in preferred format
    4. Compress uncompressed FITS to XISF if no compressed version exists
    5. Extract all redundant files (duplicates + originals after compression)
    
    Args:
        source_root: Root folder containing astronomical files
        extraction_folder: External folder for extracted duplicates (preserves structure)
        prefer_format: Format to keep ('xisf', 'fits', 'fz')
        compress_fits: If True, compress uncompressed FITS to XISF
        workers: Number of parallel workers
    
    Returns:
        dict with statistics
    """
    global DETECTED_DUPLICATES
    
    if SYSTEM_LANGUAGE == 'fr':
        print("\n" + "=" * 70)
        print("🗜️ OPTIMISATION DU STOCKAGE")
        print("=" * 70)
        print(f"   📁 Dossier source: {source_root}")
        print(f"   📦 Dossier extraction: {extraction_folder}")
        print(f"   🎯 Format préféré: {prefer_format.upper()}")
        print(f"   🗜️ Compression FITS→XISF: {'Oui' if compress_fits else 'Non'}")
    else:
        print("\n" + "=" * 70)
        print("🗜️ STORAGE OPTIMIZATION")
        print("=" * 70)
        print(f"   📁 Source folder: {source_root}")
        print(f"   📦 Extraction folder: {extraction_folder}")
        print(f"   🎯 Preferred format: {prefer_format.upper()}")
        print(f"   🗜️ Compress FITS→XISF: {'Yes' if compress_fits else 'No'}")
    
    stats = {
        'total_files': 0,
        'unique_observations': 0,
        'duplicates_found': 0,
        'compressed': 0,
        'compression_errors': 0,
        'extracted': 0,
        'extraction_errors': 0,
        'space_saved_bytes': 0,
    }
    
    # Extension priority based on preference
    if prefer_format == 'fits':
        priority_order = ['.fits', '.fit', '.xisf', '.xifs', '.xif', '.fits.fz']
    elif prefer_format == 'fz':
        priority_order = ['.fits.fz', '.xisf', '.xifs', '.xif', '.fits', '.fit']
    else:  # xisf (default)
        priority_order = ['.xisf', '.xifs', '.xif', '.fits.fz', '.fits', '.fit']
    
    def get_extension(file_path):
        file_lower = str(file_path).lower()
        if file_lower.endswith('.fits.fz'):
            return '.fits.fz'
        for ext in ['.fits', '.fit', '.xisf', '.xifs', '.xif']:
            if file_lower.endswith(ext):
                return ext
        return ''
    
    def get_priority(ext):
        try:
            return priority_order.index(ext.lower())
        except ValueError:
            return 999
    
    def get_base_path(file_path):
        """Get path without extension for finding related files"""
        file_str = str(file_path)
        file_lower = file_str.lower()
        for ext in ['.fits.fz', '.fits', '.fit', '.xisf', '.xifs', '.xif']:
            if file_lower.endswith(ext):
                return file_str[:-len(ext)]
        return file_str
    
    # Create extraction folder
    os.makedirs(extraction_folder, exist_ok=True)
    
    # ========== STEP 1: Find all files ==========
    if SYSTEM_LANGUAGE == 'fr':
        print(f"\n📂 Étape 1: Recherche des fichiers...")
    else:
        print(f"\n📂 Step 1: Finding files...")
    
    all_files = []
    fits_extensions = ('.fit', '.fits', '.fits.fz', '.xisf', '.xifs', '.xif')
    skip_folders = ['astronomical_analysis_', 'duplicates_', 'fits_originals_', os.path.basename(extraction_folder)]
    
    for root, dirs, files in os.walk(source_root):
        dirs[:] = [d for d in dirs if not any(d.startswith(skip) for skip in skip_folders)]
        for file in files:
            if file.lower().endswith(fits_extensions):
                all_files.append(os.path.join(root, file))
    
    stats['total_files'] = len(all_files)
    
    if SYSTEM_LANGUAGE == 'fr':
        print(f"   ✓ {len(all_files)} fichier(s) trouvé(s)")
    else:
        print(f"   ✓ {len(all_files)} file(s) found")
    
    if not all_files:
        return stats
    
    # ========== STEP 2: Group by content signature ==========
    if SYSTEM_LANGUAGE == 'fr':
        print(f"\n📋 Étape 2: Analyse des signatures...")
    else:
        print(f"\n📋 Step 2: Analyzing signatures...")
    
    signature_groups = {}  # signature -> [(path, ext, info), ...]
    
    for file_path in all_files:
        signature, info = get_file_signature(file_path)
        ext = get_extension(file_path)
        
        if signature and (signature[0] or signature[1]):  # Has date or object
            if signature not in signature_groups:
                signature_groups[signature] = []
            signature_groups[signature].append((file_path, ext, info))
        else:
            # No signature, treat as unique
            unique_sig = (file_path,)  # Use path as unique key
            signature_groups[unique_sig] = [(file_path, ext, info)]
    
    stats['unique_observations'] = len(signature_groups)
    
    if SYSTEM_LANGUAGE == 'fr':
        print(f"   ✓ {len(signature_groups)} observation(s) unique(s) identifiée(s)")
    else:
        print(f"   ✓ {len(signature_groups)} unique observation(s) identified")
    
    # ========== STEP 3: Identify files to keep vs extract ==========
    if SYSTEM_LANGUAGE == 'fr':
        print(f"\n🔍 Étape 3: Identification des fichiers à garder/extraire...")
    else:
        print(f"\n🔍 Step 3: Identifying files to keep/extract...")
    
    files_to_keep = []
    files_to_extract = []  # (path, reason, kept_path)
    files_to_compress = []  # Uncompressed FITS that need compression
    
    for signature, files in signature_groups.items():
        if len(files) == 1:
            # Single file - check if it needs compression
            file_path, ext, info = files[0]
            if compress_fits and ext in ['.fits', '.fit']:
                # Check if XISF version exists
                base = get_base_path(file_path)
                xisf_exists = any(os.path.exists(base + x) for x in ['.xisf', '.xifs', '.xif'])
                if not xisf_exists:
                    files_to_compress.append(file_path)
                else:
                    # XISF exists, this FITS is redundant
                    xisf_path = base + '.xisf' if os.path.exists(base + '.xisf') else base + '.xifs'
                    files_to_extract.append((file_path, f"XISF exists: {os.path.basename(xisf_path)}", xisf_path))
                    stats['duplicates_found'] += 1
            files_to_keep.append(file_path)
        else:
            # Multiple files with same signature = duplicates
            stats['duplicates_found'] += len(files) - 1
            
            # Sort by priority (best format first)
            files_sorted = sorted(files, key=lambda x: (get_priority(x[1]), len(str(x[0]))))
            
            # Keep the best one
            best_file, best_ext, best_info = files_sorted[0]
            files_to_keep.append(best_file)
            
            # Mark others for extraction
            for file_path, ext, info in files_sorted[1:]:
                reason = f"Duplicate of {os.path.basename(best_file)}"
                files_to_extract.append((file_path, reason, best_file))
            
            # If best file is uncompressed FITS and we want to compress
            if compress_fits and best_ext in ['.fits', '.fit']:
                # Check if any version is already compressed
                has_compressed = any(e in ['.xisf', '.xifs', '.xif', '.fits.fz'] for _, e, _ in files)
                if not has_compressed:
                    files_to_compress.append(best_file)
    
    if SYSTEM_LANGUAGE == 'fr':
        print(f"   ✓ {len(files_to_keep)} fichier(s) à garder")
        print(f"   ✓ {len(files_to_extract)} fichier(s) à extraire")
        print(f"   ✓ {len(files_to_compress)} fichier(s) à compresser")
    else:
        print(f"   ✓ {len(files_to_keep)} file(s) to keep")
        print(f"   ✓ {len(files_to_extract)} file(s) to extract")
        print(f"   ✓ {len(files_to_compress)} file(s) to compress")
    
    # ========== STEP 4: Compress uncompressed FITS ==========
    if compress_fits and files_to_compress:
        if SYSTEM_LANGUAGE == 'fr':
            print(f"\n🗜️ Étape 4: Compression FITS → XISF...")
        else:
            print(f"\n🗜️ Step 4: Compressing FITS → XISF...")
        
        try:
            from astropy.io import fits as astropy_fits
            import numpy as np
        except ImportError:
            if SYSTEM_LANGUAGE == 'fr':
                print("   ⚠️ astropy/numpy non disponibles, compression ignorée")
            else:
                print("   ⚠️ astropy/numpy not available, skipping compression")
            files_to_compress = []
        
        for fits_path in files_to_compress:
            try:
                # Read FITS
                with astropy_fits.open(fits_path, memmap=False) as hdul:
                    data = hdul[0].data
                    header = hdul[0].header
                    if data is None and len(hdul) > 1:
                        data = hdul[1].data
                        header = hdul[1].header
                
                if data is None:
                    stats['compression_errors'] += 1
                    continue
                
                # Compute original SHA256
                original_sha256 = hashlib.sha256(data.tobytes()).hexdigest()
                original_size = os.path.getsize(fits_path)
                
                # Create XISF
                xisf_path = get_base_path(fits_path) + '.xisf'
                success = write_xisf_file(xisf_path, data, header, compression='zlib',
                                         compression_level=6, byte_shuffling=True)
                
                if not success:
                    stats['compression_errors'] += 1
                    if os.path.exists(xisf_path):
                        os.remove(xisf_path)
                    continue
                
                # Verify XISF
                verified_data, _ = read_xisf_file(xisf_path)
                if verified_data is None:
                    stats['compression_errors'] += 1
                    os.remove(xisf_path)
                    continue
                
                verified_sha256 = hashlib.sha256(verified_data.tobytes()).hexdigest()
                
                if original_sha256 != verified_sha256:
                    stats['compression_errors'] += 1
                    os.remove(xisf_path)
                    if SYSTEM_LANGUAGE == 'fr':
                        print(f"   ❌ {os.path.basename(fits_path)}: Échec vérification SHA-256")
                    else:
                        print(f"   ❌ {os.path.basename(fits_path)}: SHA-256 verification failed")
                    continue
                
                # Success! Mark FITS for extraction
                stats['compressed'] += 1
                xisf_size = os.path.getsize(xisf_path)
                stats['space_saved_bytes'] += original_size - xisf_size
                
                files_to_extract.append((fits_path, f"Compressed to {os.path.basename(xisf_path)}", xisf_path))
                
                compression_ratio = (1 - xisf_size / original_size) * 100 if original_size > 0 else 0
                if SYSTEM_LANGUAGE == 'fr':
                    print(f"   ✓ {os.path.basename(fits_path)} → .xisf ({compression_ratio:.1f}% réduction)")
                else:
                    print(f"   ✓ {os.path.basename(fits_path)} → .xisf ({compression_ratio:.1f}% reduction)")
                    
            except Exception as e:
                stats['compression_errors'] += 1
                if SYSTEM_LANGUAGE == 'fr':
                    print(f"   ❌ {os.path.basename(fits_path)}: {e}")
                else:
                    print(f"   ❌ {os.path.basename(fits_path)}: {e}")
    
    # ========== STEP 5: Extract redundant files ==========
    if files_to_extract:
        if SYSTEM_LANGUAGE == 'fr':
            print(f"\n📦 Étape 5: Extraction des fichiers redondants...")
        else:
            print(f"\n📦 Step 5: Extracting redundant files...")
        
        for file_path, reason, kept_path in files_to_extract:
            try:
                if not os.path.exists(file_path):
                    continue
                
                # Compute relative path
                try:
                    rel_path = os.path.relpath(file_path, source_root)
                except ValueError:
                    rel_path = os.path.basename(file_path)
                
                # Create destination
                dest_path = os.path.join(extraction_folder, rel_path)
                dest_dir = os.path.dirname(dest_path)
                os.makedirs(dest_dir, exist_ok=True)
                
                # Get file size before moving
                file_size = os.path.getsize(file_path)
                
                # Move file
                shutil.move(file_path, dest_path)
                stats['extracted'] += 1
                stats['space_saved_bytes'] += file_size
                
                if SYSTEM_LANGUAGE == 'fr':
                    print(f"   ✓ {os.path.basename(file_path)} → extraction ({reason})")
                else:
                    print(f"   ✓ {os.path.basename(file_path)} → extracted ({reason})")
                    
            except Exception as e:
                stats['extraction_errors'] += 1
                if SYSTEM_LANGUAGE == 'fr':
                    print(f"   ❌ {os.path.basename(file_path)}: {e}")
                else:
                    print(f"   ❌ {os.path.basename(file_path)}: {e}")
    
    # ========== SUMMARY ==========
    space_saved_mb = stats['space_saved_bytes'] / (1024 * 1024)
    space_saved_gb = stats['space_saved_bytes'] / (1024 * 1024 * 1024)
    
    if SYSTEM_LANGUAGE == 'fr':
        print(f"\n" + "=" * 70)
        print(f"📊 RÉSUMÉ DE L'OPTIMISATION")
        print(f"=" * 70)
        print(f"   📁 Fichiers analysés: {stats['total_files']}")
        print(f"   🔬 Observations uniques: {stats['unique_observations']}")
        print(f"   🔗 Doublons détectés: {stats['duplicates_found']}")
        print(f"   🗜️ Fichiers compressés: {stats['compressed']}")
        print(f"   📦 Fichiers extraits: {stats['extracted']}")
        if space_saved_gb >= 1:
            print(f"   💾 Espace libéré: {space_saved_gb:.2f} Go")
        else:
            print(f"   💾 Espace libéré: {space_saved_mb:.1f} Mo")
        if stats['compression_errors'] or stats['extraction_errors']:
            print(f"   ⚠️ Erreurs: {stats['compression_errors'] + stats['extraction_errors']}")
    else:
        print(f"\n" + "=" * 70)
        print(f"📊 OPTIMIZATION SUMMARY")
        print(f"=" * 70)
        print(f"   📁 Files analyzed: {stats['total_files']}")
        print(f"   🔬 Unique observations: {stats['unique_observations']}")
        print(f"   🔗 Duplicates found: {stats['duplicates_found']}")
        print(f"   🗜️ Files compressed: {stats['compressed']}")
        print(f"   📦 Files extracted: {stats['extracted']}")
        if space_saved_gb >= 1:
            print(f"   💾 Space freed: {space_saved_gb:.2f} GB")
        else:
            print(f"   💾 Space freed: {space_saved_mb:.1f} MB")
        if stats['compression_errors'] or stats['extraction_errors']:
            print(f"   ⚠️ Errors: {stats['compression_errors'] + stats['extraction_errors']}")
    
    return stats


def extract_duplicates_to_folder(source_root, dest_folder):
    """
    Extract detected duplicates to an external folder, preserving directory structure.
    Includes: name-based duplicates, content-based duplicates, and compressed originals.
    
    Args:
        source_root: Root folder of the original files
        dest_folder: Destination folder for duplicates
    
    Returns:
        dict with statistics about moved files
    """
    global DETECTED_DUPLICATES
    
    if SYSTEM_LANGUAGE == 'fr':
        print(f"\n📦 Extraction des doublons vers: {dest_folder}")
    else:
        print(f"\n📦 Extracting duplicates to: {dest_folder}")
    
    stats = {
        'moved': 0,
        'errors': 0,
        'skipped': 0,
        'by_type': {
            'name_based': 0,
            'content_based': 0,
            'compressed': 0,
        }
    }
    
    # Create destination folder
    os.makedirs(dest_folder, exist_ok=True)
    
    # Combine all duplicates
    all_duplicates = (
        [(d[0], d[1], d[2], 'name') for d in DETECTED_DUPLICATES.get('name_based', [])] +
        [(d[0], d[1], d[2], 'content') for d in DETECTED_DUPLICATES.get('content_based', [])] +
        [(d[0], d[1], d[2], 'compressed') for d in DETECTED_DUPLICATES.get('compressed', [])]
    )
    
    if not all_duplicates:
        if SYSTEM_LANGUAGE == 'fr':
            print("   ℹ️ Aucun doublon détecté à extraire")
        else:
            print("   ℹ️ No duplicates detected to extract")
        return stats
    
    if SYSTEM_LANGUAGE == 'fr':
        print(f"   📋 {len(all_duplicates)} fichier(s) à extraire")
    else:
        print(f"   📋 {len(all_duplicates)} file(s) to extract")
    
    # Map tuple dup_type to stats key
    dup_type_to_key = {'name': 'name_based', 'content': 'content_based', 'compressed': 'compressed'}
    
    for dup_info in all_duplicates:
        duplicate_path = dup_info[0]
        kept_path = dup_info[1]
        dup_type = dup_info[3] if len(dup_info) > 3 else 'unknown'
        type_key = dup_type_to_key.get(dup_type, 'name_based')
        
        try:
            # Normalize to absolute path so exists() works regardless of how path was stored
            duplicate_path_abs = os.path.abspath(duplicate_path)
            source_root_abs = os.path.abspath(source_root)
            
            # Compute relative path from source root
            try:
                rel_path = os.path.relpath(duplicate_path_abs, source_root_abs)
            except ValueError:
                # On Windows, relpath fails if paths are on different drives
                rel_path = os.path.basename(duplicate_path_abs)
            
            # Create destination path preserving structure
            dest_path = os.path.join(dest_folder, rel_path)
            dest_dir = os.path.dirname(dest_path)
            
            # Create directory structure
            os.makedirs(dest_dir, exist_ok=True)
            
            # Move the file
            if os.path.exists(duplicate_path_abs):
                shutil.move(duplicate_path_abs, dest_path)
                stats['moved'] += 1
                stats['by_type'][type_key] = stats['by_type'].get(type_key, 0) + 1
                
                # Show type indicator
                type_icon = {'name': '📄', 'content': '🔗', 'compressed': '🗜️'}.get(dup_type, '📄')
                if SYSTEM_LANGUAGE == 'fr':
                    print(f"   {type_icon} Déplacé: {os.path.basename(duplicate_path_abs)}")
                else:
                    print(f"   {type_icon} Moved: {os.path.basename(duplicate_path_abs)}")
            else:
                stats['skipped'] += 1
                
        except Exception as e:
            stats['errors'] += 1
            if SYSTEM_LANGUAGE == 'fr':
                print(f"   ❌ Erreur: {os.path.basename(duplicate_path_abs)}: {e}")
            else:
                print(f"   ❌ Error: {os.path.basename(duplicate_path_abs)}: {e}")
    
    # Summary
    if SYSTEM_LANGUAGE == 'fr':
        print(f"\n   📊 Résumé extraction:")
        print(f"      📄 Doublons par nom: {stats['by_type'].get('name_based', 0)}")
        print(f"      🔗 Doublons par contenu: {stats['by_type'].get('content_based', 0)}")
        print(f"      🗜️ Originaux compressés: {stats['by_type'].get('compressed', 0)}")
        print(f"      ✓ Total déplacés: {stats['moved']}")
        print(f"      ❌ Erreurs: {stats['errors']}")
    else:
        print(f"\n   📊 Extraction summary:")
        print(f"      📄 Name-based duplicates: {stats['by_type'].get('name_based', 0)}")
        print(f"      🔗 Content-based duplicates: {stats['by_type'].get('content_based', 0)}")
        print(f"      🗜️ Compressed originals: {stats['by_type'].get('compressed', 0)}")
        print(f"      ✓ Total moved: {stats['moved']}")
        print(f"      ❌ Errors: {stats['errors']}")
    
    return stats


def compute_file_sha256(file_path):
    """Compute SHA-256 hash of a file"""
    import hashlib
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def compress_fits_to_xisf(source_root, backup_folder=None, workers=1, add_to_duplicates=True, check_abort=None):
    """
    Compress uncompressed FITS files to XISF format (zlib-6, byte-shuffle, monolithic).
    Skips FITS that already have a corresponding .xisf file.
    After successful compression and SHA-256 verification, either:
    - Add to duplicates list for later extraction (if add_to_duplicates=True)
    - Move directly to backup folder (if backup_folder specified and add_to_duplicates=False)
    
    Args:
        source_root: Root folder containing FITS files
        backup_folder: Folder to move original FITS after successful compression (optional)
        workers: Number of parallel workers
        add_to_duplicates: If True, add compressed originals to DETECTED_DUPLICATES for batch extraction
        check_abort: Optional callable(); if it returns True, compression stops (e.g. user clicked Stop)
    
    Returns:
        dict with statistics
    """
    if SYSTEM_LANGUAGE == 'fr':
        print(f"\n🗜️ Compression FITS → XISF (zlib-6, byte-shuffle, monolithique)")
        print(f"   📁 Dossier source: {source_root}")
        if backup_folder and not add_to_duplicates:
            print(f"   📦 Dossier backup: {backup_folder}")
        elif add_to_duplicates:
            print(f"   📋 Les originaux seront ajoutés à la liste d'extraction")
    else:
        print(f"\n🗜️ Compressing FITS → XISF (zlib-6, byte-shuffle, monolithic)")
        print(f"   📁 Source folder: {source_root}")
        if backup_folder and not add_to_duplicates:
            print(f"   📦 Backup folder: {backup_folder}")
        elif add_to_duplicates:
            print(f"   📋 Originals will be added to extraction list")
    
    stats = {
        'found': 0,
        'compressed': 0,
        'verified': 0,
        'queued_for_extraction': 0,
        'moved': 0,
        'errors': 0,
        'skipped_has_xisf': 0,
        'skipped_already_compressed': 0,
    }
    
    # Check if we have the necessary libraries
    try:
        from astropy.io import fits as astropy_fits
        import numpy as np
    except ImportError:
        if SYSTEM_LANGUAGE == 'fr':
            print("   ❌ Erreur: astropy et numpy sont requis pour la compression")
        else:
            print("   ❌ Error: astropy and numpy are required for compression")
        return stats
    
    # Find all uncompressed FITS files
    fits_files = []
    for root, dirs, files in os.walk(source_root):
        # Skip backup, analysis and extraction folders
        skip_folders = ['astronomical_analysis_', 'duplicates_', 'fits_originals_', 'extracted_']
        if backup_folder:
            skip_folders.append(os.path.basename(backup_folder))
        dirs[:] = [d for d in dirs if not any(d.startswith(skip) for skip in skip_folders)]
        
        for file in files:
            file_lower = file.lower()
            if file_lower.endswith(('.fits', '.fit')) and not file_lower.endswith('.fits.fz'):
                full_path = os.path.join(root, file)
                fits_files.append(full_path)
    
    stats['found'] = len(fits_files)
    
    # Build a map of FITS files that ALREADY have an equivalent XISF version
    # detected during content-based deduplication (even if the names differ).
    fits_with_xisf_by_content = set()
    try:
        global DETECTED_DUPLICATES  # populated by remove_compressed_duplicates
        content_dups = DETECTED_DUPLICATES.get('content_based', [])
        for dup_path, kept_path, _info in content_dups:
            d = str(dup_path).lower()
            k = str(kept_path).lower()
            
            def _is_fits(p: str) -> bool:
                return p.endswith('.fits') or p.endswith('.fit') or p.endswith('.fits.fz')
            
            def _is_xisf(p: str) -> bool:
                return p.endswith('.xisf') or p.endswith('.xifs') or p.endswith('.xif')
            
            # If a FITS has an XISF counterpart in the same signature group,
            # there is no point recompressing it: it is already present as XISF.
            if _is_fits(d) and _is_xisf(k):
                fits_with_xisf_by_content.add(os.path.abspath(dup_path))
            elif _is_fits(k) and _is_xisf(d):
                fits_with_xisf_by_content.add(os.path.abspath(kept_path))
    except Exception:
        # In case DETECTED_DUPLICATES is not defined/initialized, just ignore
        fits_with_xisf_by_content = set()
    
    # Keep only FITS that do NOT already have a .xisf version:
    #  - either by simple base-name (.fit ↔ .xisf),
    #  - or by content-based duplicate detection.
    fits_to_compress = []
    for f in fits_files:
        base = f.rsplit('.', 1)[0]
        abs_f = os.path.abspath(f)
        has_xisf_same_name = os.path.exists(base + '.xisf')
        has_xisf_by_content = abs_f in fits_with_xisf_by_content
        
        if not has_xisf_same_name and not has_xisf_by_content:
            fits_to_compress.append(f)
        else:
            stats['skipped_has_xisf'] += 1
    
    if stats['skipped_has_xisf'] > 0:
        if SYSTEM_LANGUAGE == 'fr':
            print(f"   ⏭️ {stats['skipped_has_xisf']} fichier(s) déjà en XISF ignoré(s)")
        else:
            print(f"   ⏭️ {stats['skipped_has_xisf']} file(s) already in XISF skipped")
    
    if not fits_to_compress:
        if SYSTEM_LANGUAGE == 'fr':
            print("   ℹ️ Aucun fichier FITS à compresser (tous ont déjà une version XISF ou aucun FITS trouvé)")
        else:
            print("   ℹ️ No FITS files to compress (all already have XISF version or none found)")
        return stats
    
    if SYSTEM_LANGUAGE == 'fr':
        print(f"   🔍 {len(fits_to_compress)} fichier(s) FITS à compresser")
    else:
        print(f"   🔍 {len(fits_to_compress)} FITS file(s) to compress")
    
    # Create backup folder only if needed
    if backup_folder:
        os.makedirs(backup_folder, exist_ok=True)
    
    # Phase 5: compression progress (for GUI) — only files that need compression
    total_to_process = len(fits_to_compress)
    report_progress(0, total_to_process, "phase5")
    
    # Process each file
    processed_count = 0
    for fits_path in fits_to_compress:
        if check_abort and callable(check_abort) and check_abort():
            if SYSTEM_LANGUAGE == 'fr':
                print("\n   ⚠️ Compression interrompue par l'utilisateur")
            else:
                print("\n   ⚠️ Compression stopped by user")
            break
        try:
            base_path = fits_path.rsplit('.', 1)[0]
            xisf_path = base_path + '.xisf'
            
            # Read FITS file
            with astropy_fits.open(fits_path, memmap=False) as hdul:
                # Get primary data and header
                data = hdul[0].data
                header = hdul[0].header
                
                if data is None:
                    # Try first extension
                    if len(hdul) > 1 and hdul[1].data is not None:
                        data = hdul[1].data
                        header = hdul[1].header
                    else:
                        stats['errors'] += 1
                        processed_count += 1
                        report_progress(processed_count, total_to_process, "phase5")
                        continue
            
            # Compute SHA-256 of original data
            original_sha256 = hashlib.sha256(data.tobytes()).hexdigest()
            
            # Create XISF file
            success = write_xisf_file(xisf_path, data, header, compression='zlib', 
                                      compression_level=6, byte_shuffling=True)
            
            if not success:
                stats['errors'] += 1
                if os.path.exists(xisf_path):
                    os.remove(xisf_path)
                processed_count += 1
                report_progress(processed_count, total_to_process, "phase5")
                continue
            
            stats['compressed'] += 1
            
            # Verify XISF by reading it back
            try:
                verified_data, _ = read_xisf_file(xisf_path)
                if verified_data is not None:
                    verified_sha256 = hashlib.sha256(verified_data.tobytes()).hexdigest()
                    
                    if original_sha256 == verified_sha256:
                        stats['verified'] += 1
                        
                        if add_to_duplicates:
                            # Add original FITS to duplicates list for later batch extraction
                            add_detected_duplicate(fits_path, xisf_path, 
                                "FITS compressé en XISF" if SYSTEM_LANGUAGE == 'fr' 
                                else "FITS compressed to XISF", 'compressed')
                            stats['queued_for_extraction'] += 1
                            
                            if SYSTEM_LANGUAGE == 'fr':
                                print(f"   ✓ {os.path.basename(fits_path)} → .xisf (vérifié, marqué pour extraction)")
                            else:
                                print(f"   ✓ {os.path.basename(fits_path)} → .xisf (verified, queued for extraction)")
                        elif backup_folder:
                            # Move original to backup folder
                            try:
                                rel_path = os.path.relpath(fits_path, source_root)
                            except ValueError:
                                rel_path = os.path.basename(fits_path)
                            
                            backup_path = os.path.join(backup_folder, rel_path)
                            backup_dir = os.path.dirname(backup_path)
                            os.makedirs(backup_dir, exist_ok=True)
                            
                            shutil.move(fits_path, backup_path)
                            stats['moved'] += 1
                            
                            if SYSTEM_LANGUAGE == 'fr':
                                print(f"   ✓ {os.path.basename(fits_path)} → .xisf (vérifié, original déplacé)")
                            else:
                                print(f"   ✓ {os.path.basename(fits_path)} → .xisf (verified, original moved)")
                        else:
                            # No backup folder and no add_to_duplicates: just report
                            if SYSTEM_LANGUAGE == 'fr':
                                print(f"   ✓ {os.path.basename(fits_path)} → .xisf (vérifié)")
                            else:
                                print(f"   ✓ {os.path.basename(fits_path)} → .xisf (verified)")
                    else:
                        # SHA mismatch - delete XISF and keep original
                        os.remove(xisf_path)
                        stats['errors'] += 1
                        if SYSTEM_LANGUAGE == 'fr':
                            print(f"   ❌ {os.path.basename(fits_path)}: Erreur de vérification SHA-256")
                        else:
                            print(f"   ❌ {os.path.basename(fits_path)}: SHA-256 verification failed")
                else:
                    os.remove(xisf_path)
                    stats['errors'] += 1
            except Exception as verify_error:
                if os.path.exists(xisf_path):
                    os.remove(xisf_path)
                stats['errors'] += 1
                if SYSTEM_LANGUAGE == 'fr':
                    print(f"   ❌ {os.path.basename(fits_path)}: Erreur de vérification: {verify_error}")
                else:
                    print(f"   ❌ {os.path.basename(fits_path)}: Verification error: {verify_error}")
                    
        except Exception as e:
            stats['errors'] += 1
            if SYSTEM_LANGUAGE == 'fr':
                print(f"   ❌ {os.path.basename(fits_path)}: {e}")
            else:
                print(f"   ❌ {os.path.basename(fits_path)}: {e}")
        
        processed_count += 1
        report_progress(processed_count, total_to_process, "phase5")
    
    # Summary
    if SYSTEM_LANGUAGE == 'fr':
        print(f"\n   📊 Résumé compression:")
        print(f"      🔍 Trouvés: {stats['found']}")
        print(f"      🗜️ Compressés: {stats['compressed']}")
        print(f"      ✓ Vérifiés: {stats['verified']}")
        if stats['queued_for_extraction'] > 0:
            print(f"      📋 Marqués pour extraction: {stats['queued_for_extraction']}")
        if stats['moved'] > 0:
            print(f"      📦 Déplacés: {stats['moved']}")
        print(f"      ⏭️ Ignorés (XISF existe): {stats['skipped_has_xisf']}")
        if stats['errors'] > 0:
            print(f"      ❌ Erreurs: {stats['errors']}")
    else:
        print(f"\n   📊 Compression summary:")
        print(f"      🔍 Found: {stats['found']}")
        print(f"      🗜️ Compressed: {stats['compressed']}")
        print(f"      ✓ Verified: {stats['verified']}")
        if stats['queued_for_extraction'] > 0:
            print(f"      📋 Queued for extraction: {stats['queued_for_extraction']}")
        if stats['moved'] > 0:
            print(f"      📦 Moved: {stats['moved']}")
        print(f"      ⏭️ Skipped (XISF exists): {stats['skipped_has_xisf']}")
        if stats['errors'] > 0:
            print(f"      ❌ Errors: {stats['errors']}")
    
    return stats


def write_xisf_file(output_path, data, header, compression='zlib', compression_level=6, byte_shuffling=True):
    """
    Write data to XISF format (monolithic, PixInsight compatible).
    
    Uses the 'xisf' library (pip install xisf) as primary method for guaranteed 
    PixInsight compatibility. Falls back to manual implementation if unavailable.
    
    Args:
        output_path: Path for output XISF file
        data: numpy array with image data
        header: FITS header or dict with metadata
        compression: 'zlib', 'lz4', 'lz4hc', 'zstd' or None
        compression_level: 1-9 for zlib (6 is good balance)
        byte_shuffling: Enable byte shuffling for better compression
    
    Returns:
        True if successful, False otherwise
    """
    import numpy as np
    
    try:
        # Ensure data is in correct format
        if data is None:
            return False
        if data.dtype == np.float64:
            data = data.astype(np.float32)
        
        # Try using the xisf library (proven PixInsight compatible)
        try:
            return _write_xisf_with_library(output_path, data, header, compression, 
                                            compression_level, byte_shuffling)
        except ImportError:
            pass
        except Exception as e:
            print(f"   ⚠️  xisf library failed ({e}), using built-in encoder")
        
        # Fallback: manual XISF writer (corrected to match XISF 1.0 spec)
        return _write_xisf_manual(output_path, data, header, compression, 
                                  compression_level, byte_shuffling)
        
    except Exception as e:
        print(f"Error writing XISF: {e}")
        import traceback
        traceback.print_exc()
        return False


def _write_xisf_with_library(output_path, data, header, compression='zlib', 
                              compression_level=6, byte_shuffling=True):
    """Write XISF using the xisf library (pip install xisf)"""
    from xisf import XISF
    import numpy as np
    
    # Prepare data in channels-last format expected by xisf library
    if len(data.shape) == 2:
        # 2D grayscale -> (height, width, 1)
        im_data = data[:, :, np.newaxis]
    elif len(data.shape) == 3:
        if data.shape[0] in [1, 3]:
            # channels-first (channels, height, width) -> channels-last (height, width, channels)
            im_data = np.transpose(data, (1, 2, 0))
        else:
            im_data = data
    else:
        return False
    
    # Convert FITS header to xisf FITSKeywords format
    fits_keywords = {}
    if header is not None:
        for key in header:
            if key in ['', 'COMMENT', 'HISTORY', 'END', 'SIMPLE', 'EXTEND']:
                continue
            try:
                value = header[key]
                comment = ''
                if hasattr(header, 'comments'):
                    try:
                        comment = header.comments[key] or ''
                    except (KeyError, IndexError, TypeError):
                        comment = ''
                
                # Format value as FITS card value (strings in single quotes)
                if isinstance(value, str):
                    formatted_value = f"'{value}'"
                elif isinstance(value, bool):
                    formatted_value = 'T' if value else 'F'
                elif isinstance(value, int):
                    formatted_value = str(value)
                elif isinstance(value, float):
                    formatted_value = str(value)
                else:
                    formatted_value = str(value) if value is not None else ''
                
                kw_name = str(key).strip()[:8]
                if kw_name not in fits_keywords:
                    fits_keywords[kw_name] = []
                fits_keywords[kw_name].append({
                    'value': formatted_value,
                    'comment': str(comment)
                })
            except Exception:
                pass
    
    image_metadata = {'FITSKeywords': fits_keywords}
    
    # Map compression parameters
    codec = compression if compression else None
    level = compression_level if compression_level else None
    
    XISF.write(str(output_path), im_data, 
               creator_app="FITS Analyser (Python)",
               image_metadata=image_metadata,
               codec=codec, shuffle=byte_shuffling, level=level)
    return True


def _write_xisf_manual(output_path, data, header, compression='zlib', 
                        compression_level=6, byte_shuffling=True):
    """
    Manual XISF writer - fallback when xisf library is unavailable.
    Follows XISF 1.0 specification for PixInsight compatibility.
    
    File structure (monolithic):
      - Signature: 8 bytes "XISF0100"
      - Header length: 4 bytes (uint32 LE)
      - Reserved: 4 bytes (zeros)
      - XML header (UTF-8, with XML declaration)
      - Zero padding to block alignment (4096 bytes)
      - Image data block
    """
    import struct
    import zlib
    import numpy as np
    import xml.etree.ElementTree as ET
    
    BLOCK_ALIGNMENT = 4096
    
    # Get data properties
    if len(data.shape) == 2:
        height, width = data.shape
        channels = 1
    elif len(data.shape) == 3:
        channels, height, width = data.shape
    else:
        return False
    
    # Determine sample format
    dtype_map = {
        'uint8': ('UInt8', 8),
        'uint16': ('UInt16', 16),
        'uint32': ('UInt32', 32),
        'float32': ('Float32', 32),
        'float64': ('Float64', 64),
    }
    dtype_str = str(data.dtype)
    if dtype_str not in dtype_map:
        data = data.astype(np.float32)
        dtype_str = 'float32'
    sample_format, bits_per_sample = dtype_map[dtype_str]
    item_size = bits_per_sample // 8
    
    # Prepare raw data (planar format)
    raw_data = data.tobytes()
    uncompressed_size = len(raw_data)
    
    # Apply byte shuffling if enabled (before compression)
    if byte_shuffling and item_size > 1:
        shuffled_data = shuffle_bytes(raw_data, item_size)
    else:
        shuffled_data = raw_data
    
    # Compress data
    if compression == 'zlib':
        level = compression_level if compression_level else 6
        compressed_data = zlib.compress(shuffled_data, level)
        # Only use compression if it actually reduces size
        if len(compressed_data) < uncompressed_size:
            data_block = compressed_data
            if byte_shuffling and item_size > 1:
                compression_attr = f'zlib+sh:{uncompressed_size}:{item_size}'
            else:
                compression_attr = f'zlib:{uncompressed_size}'
        else:
            data_block = raw_data
            compression_attr = None
    else:
        data_block = raw_data
        compression_attr = None
    
    data_block_size = len(data_block)
    
    # Build XML header following XISF 1.0 spec
    xisf_attrs = {
        'xmlns': 'http://www.pixinsight.com/xisf',
        'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'version': '1.0',
        'xsi:schemaLocation': 'http://www.pixinsight.com/xisf http://pixinsight.com/xisf/xisf-1.0.xsd',
    }
    xisf = ET.Element('xisf', xisf_attrs)
    
    # Image element
    image_attrs = {
        'geometry': f'{width}:{height}:{channels}',
        'sampleFormat': sample_format,
        'colorSpace': 'Gray' if channels == 1 else 'RGB',
        'location': 'attachment:PLACEHOLDER:' + str(data_block_size),  # placeholder for position
    }
    if sample_format.startswith('Float'):
        image_attrs['bounds'] = '0:1'
    if compression_attr:
        image_attrs['compression'] = compression_attr
    
    image = ET.SubElement(xisf, 'Image', image_attrs)
    
    # Add FITS keywords as direct children of Image (NOT wrapped in FITSKeywords)
    if header:
        for key in header:
            if key in ['', 'COMMENT', 'HISTORY', 'END', 'SIMPLE', 'EXTEND']:
                continue
            try:
                value = header[key]
                comment = ''
                if hasattr(header, 'comments'):
                    try:
                        comment = header.comments[key] or ''
                    except (KeyError, IndexError, TypeError):
                        comment = ''
                
                # Format value as FITS card value
                if isinstance(value, str):
                    formatted_value = f"'{value}'"
                elif isinstance(value, bool):
                    formatted_value = 'T' if value else 'F'
                elif isinstance(value, int):
                    formatted_value = str(value)
                elif isinstance(value, float):
                    formatted_value = str(value)
                else:
                    formatted_value = str(value) if value is not None else ''
                
                kw_elem = ET.SubElement(image, 'FITSKeyword')
                kw_elem.set('name', str(key).strip()[:8])
                kw_elem.set('value', formatted_value)
                kw_elem.set('comment', str(comment))
            except Exception:
                pass
    
    # Add Metadata element
    metadata = ET.SubElement(xisf, 'Metadata')
    
    creator_prop = ET.SubElement(metadata, 'Property')
    creator_prop.set('id', 'XISF:CreatorApplication')
    creator_prop.set('type', 'String')
    creator_prop.text = 'FITS Analyser (Python)'
    
    from datetime import datetime
    time_prop = ET.SubElement(metadata, 'Property')
    time_prop.set('id', 'XISF:CreationTime')
    time_prop.set('type', 'String')
    time_prop.text = datetime.utcnow().isoformat()
    
    blk_prop = ET.SubElement(metadata, 'Property')
    blk_prop.set('id', 'XISF:BlockAlignmentSize')
    blk_prop.set('type', 'UInt16')
    blk_prop.set('value', str(BLOCK_ALIGNMENT))
    
    # Generate provisional XML to calculate sizes
    # Use encoding='utf8' to get proper XML declaration (<?xml ... ?>)
    xml_bytes_prov = ET.tostring(xisf, encoding='utf-8', xml_declaration=True)
    
    # Fixed header prefix: signature(8) + headerlength(4) + reserved(4) = 16
    HEADER_PREFIX_SIZE = 16
    
    # Iteratively compute data block position (since position digits affect header size)
    prev_pos_str_len = 0
    while True:
        header_total_size = HEADER_PREFIX_SIZE + len(xml_bytes_prov)
        # Align data block position to BLOCK_ALIGNMENT
        data_position = ((header_total_size + BLOCK_ALIGNMENT - 1) // BLOCK_ALIGNMENT) * BLOCK_ALIGNMENT
        
        pos_str_len = len(str(data_position))
        if pos_str_len == prev_pos_str_len:
            break
        prev_pos_str_len = pos_str_len
        
        # Update location with new position
        image.set('location', f'attachment:{data_position}:{data_block_size}')
        xml_bytes_prov = ET.tostring(xisf, encoding='utf-8', xml_declaration=True)
    
    # Final XML with correct position
    image.set('location', f'attachment:{data_position}:{data_block_size}')
    xml_bytes = ET.tostring(xisf, encoding='utf-8', xml_declaration=True)
    header_length = len(xml_bytes)
    
    # Write file
    with open(output_path, 'wb') as f:
        # XISF signature (8 bytes)
        f.write(b'XISF0100')
        # Header length (4 bytes, uint32 LE)
        f.write(struct.pack('<I', header_length))
        # Reserved (4 bytes, zeros)
        f.write(struct.pack('<I', 0))
        # XML header
        f.write(xml_bytes)
        # Zero padding to data block position
        current_pos = f.tell()
        if current_pos < data_position:
            f.write(b'\x00' * (data_position - current_pos))
        # Image data block
        f.write(data_block)
    
    return True


def shuffle_bytes(data, item_size):
    """Apply byte shuffling for better compression"""
    import numpy as np
    
    arr = np.frombuffer(data, dtype=np.uint8)
    n_items = len(arr) // item_size
    
    if n_items * item_size != len(arr):
        return data  # Can't shuffle if not aligned
    
    # Reshape to (n_items, item_size) and transpose
    reshaped = arr[:n_items * item_size].reshape(n_items, item_size)
    shuffled = reshaped.T.flatten()
    
    return shuffled.tobytes()


def unshuffle_bytes(data, item_size):
    """Reverse byte shuffling"""
    import numpy as np
    
    arr = np.frombuffer(data, dtype=np.uint8)
    n_items = len(arr) // item_size
    
    if n_items * item_size != len(arr):
        return data
    
    # Reshape to (item_size, n_items) and transpose back
    reshaped = arr[:n_items * item_size].reshape(item_size, n_items)
    unshuffled = reshaped.T.flatten()
    
    return unshuffled.tobytes()


def read_xisf_file(file_path):
    """
    Read XISF file and return data and header.
    Uses the 'xisf' library as primary method, manual parser as fallback.
    
    Returns:
        (data, header_dict) tuple, or (None, None) on error
    """
    # Try using the xisf library first (most reliable)
    try:
        from xisf import XISF
        xisf_obj = XISF(str(file_path))
        meta = xisf_obj.get_images_metadata()
        if meta:
            import numpy as np
            im = xisf_obj.read_image(0)
            # Convert from channels-last to channels-first if needed
            if len(im.shape) == 3 and im.shape[2] == 1:
                im = im[:, :, 0]  # (H, W, 1) -> (H, W)
            elif len(im.shape) == 3 and im.shape[2] > 1:
                im = np.transpose(im, (2, 0, 1))  # (H, W, C) -> (C, H, W)
            
            # Extract header info from FITSKeywords
            header_dict = {}
            fk = meta[0].get('FITSKeywords', {})
            for kw_name, kw_values in fk.items():
                if kw_values:
                    val = kw_values[0].get('value', '')
                    # Parse FITS value format
                    if val.startswith("'") and val.endswith("'"):
                        val = val[1:-1].rstrip()
                    elif val == 'T':
                        val = True
                    elif val == 'F':
                        val = False
                    else:
                        try:
                            if '.' in val or 'E' in val.upper():
                                val = float(val)
                            else:
                                val = int(val)
                        except (ValueError, TypeError):
                            pass
                    header_dict[kw_name] = val
            
            return im, header_dict
    except ImportError:
        pass
    except Exception:
        pass
    
    # Fallback: manual XISF reader
    return _read_xisf_manual(file_path)


def _read_xisf_manual(file_path):
    """Manual XISF reader - fallback when xisf library unavailable."""
    import struct
    import zlib
    import numpy as np
    import xml.etree.ElementTree as ET
    
    try:
        with open(file_path, 'rb') as f:
            # Read signature
            signature = f.read(8)
            if signature != b'XISF0100':
                return None, None
            
            # Read header length (4 bytes, uint32 LE)
            header_length = struct.unpack('<I', f.read(4))[0]
            
            # Skip reserved field (4 bytes only - NOT 8!)
            f.read(4)
            
            # Read XML header
            xml_bytes = f.read(header_length)
            xml_string = xml_bytes.rstrip(b'\x00').decode('utf-8')
            
            # Parse XML (handle with or without XML declaration)
            if xml_string.startswith('<?xml'):
                xml_string = xml_string[xml_string.index('?>')+2:].strip()
            
            root = ET.fromstring(xml_string)
            
            # Find Image element (with or without namespace)
            ns = {'xisf': 'http://www.pixinsight.com/xisf'}
            image = root.find('xisf:Image', ns) or root.find('Image')
            
            if image is None:
                return None, None
            
            # Get geometry
            geometry = image.get('geometry', '0:0:1')
            parts = geometry.split(':')
            width = int(parts[0])
            height = int(parts[1])
            channels = int(parts[2]) if len(parts) > 2 else 1
            
            # Get sample format
            sample_format = image.get('sampleFormat', 'Float32')
            dtype_map = {
                'UInt8': np.uint8, 'UInt16': np.uint16, 'UInt32': np.uint32,
                'Float32': np.float32, 'Float64': np.float64,
            }
            dtype = dtype_map.get(sample_format, np.float32)
            item_size = np.dtype(dtype).itemsize
            
            # Get compression attribute
            compression = image.get('compression', '')
            # Parse compression: "zlib+sh:uncompressed_size:item_size" or "zlib:uncompressed_size"
            uses_shuffle = '+sh' in compression or 'byte-shuffling' in compression
            
            # Get data location - format is "attachment:position:size" (colons)
            location = image.get('location', '')
            if location.startswith('attachment:'):
                loc_str = location[11:]  # remove 'attachment:'
                # XISF 1.0 spec uses colons: attachment:position:size
                loc_parts = loc_str.split(':')
                data_offset = int(loc_parts[0])
                compressed_size = int(loc_parts[1]) if len(loc_parts) > 1 else 0
            else:
                return None, None
            
            # Read data
            f.seek(data_offset)
            raw_read = f.read(compressed_size)
            
            # Decompress
            if 'zlib' in compression:
                raw_data = zlib.decompress(raw_read)
            elif 'lz4' in compression:
                try:
                    import lz4.block
                    # Parse uncompressed size from compression attribute
                    comp_parts = compression.replace('+sh', '').split(':')
                    uncompressed_size = int(comp_parts[1]) if len(comp_parts) > 1 else width * height * channels * item_size
                    raw_data = lz4.block.decompress(raw_read, uncompressed_size=uncompressed_size)
                except ImportError:
                    return None, None
            elif 'zstd' in compression:
                try:
                    import zstandard
                    raw_data = zstandard.decompress(raw_read)
                except ImportError:
                    return None, None
            else:
                raw_data = raw_read
            
            # Unshuffle if needed
            if uses_shuffle:
                raw_data = unshuffle_bytes(raw_data, item_size)
            
            # Convert to numpy array
            data = np.frombuffer(raw_data, dtype=dtype)
            
            # Reshape
            if channels == 1:
                data = data.reshape(height, width)
            else:
                data = data.reshape(channels, height, width)
            
            # Extract FITSKeywords
            header_dict = {}
            for kw in image.findall('xisf:FITSKeyword', ns) or image.findall('FITSKeyword'):
                name = kw.get('name', '')
                val = kw.get('value', '')
                if val.startswith("'") and val.endswith("'"):
                    val = val[1:-1].rstrip()
                elif val == 'T':
                    val = True
                elif val == 'F':
                    val = False
                else:
                    try:
                        if '.' in val or 'E' in val.upper():
                            val = float(val)
                        else:
                            val = int(val)
                    except (ValueError, TypeError):
                        pass
                header_dict[name] = val
            
            return data, header_dict
            
    except Exception as e:
        print(f"Error reading XISF: {e}")
        return None, None


# Import hashlib at module level for compression functions
import hashlib


# Recognized image types
RECOGNIZED_TYPES = ['LIGHT', 'DARK', 'BIAS', 'FLAT']

# Configuration to optimize analysis speed
FAST_ANALYSIS = True  # Fast mode enabled
ADU_SAMPLE_PER_FILTER = 0  # No advanced analysis in fast mode
ADU_ANALYSIS_ENABLED = True  # New variable to control advanced analysis

# Path to calibration files (no personal default)
BIAS_DARK_PATH = None

# Configuration file to save parameters
CONFIG_FILE = "astro_config.json"
DEFAULT_REGION_SIZE = 100

# ============================================================================
# GUI Progress Callback System
# ============================================================================
# Callback de progression pour l'interface graphique
# Format: callback(current, total, phase_name)
GUI_PROGRESS_CALLBACK = None

# Cache pour stocker les infos de header lues pendant la déduplication
# Cela évite de relire les headers dans Phase 1
HEADER_INFO_CACHE = {}

def set_progress_callback(callback):
    """Définit le callback de progression pour l'interface graphique"""
    global GUI_PROGRESS_CALLBACK
    GUI_PROGRESS_CALLBACK = callback

def clear_progress_callback():
    """Efface le callback de progression"""
    global GUI_PROGRESS_CALLBACK
    GUI_PROGRESS_CALLBACK = None

def clear_header_cache():
    """Efface le cache des headers"""
    global HEADER_INFO_CACHE
    HEADER_INFO_CACHE = {}

def get_cached_header_info(file_path):
    """Récupère les infos de header du cache si disponibles"""
    global HEADER_INFO_CACHE
    return HEADER_INFO_CACHE.get(str(file_path))

def cache_header_info(file_path, info):
    """Stocke les infos de header dans le cache"""
    global HEADER_INFO_CACHE
    HEADER_INFO_CACHE[str(file_path)] = info

def report_progress(current, total, phase=""):
    """Rapporte la progression à l'interface graphique si disponible"""
    global GUI_PROGRESS_CALLBACK
    if GUI_PROGRESS_CALLBACK is not None:
        try:
            GUI_PROGRESS_CALLBACK(current, total, phase)
        except Exception:
            pass

# ============================================================================

# Cache for displayed warnings to avoid repetition
_displayed_warnings = set()

# Alternative cache using a simple flag file
_warning_cache_file = "telescope_warning_shown.txt"

def has_warning_been_shown(warning_type="telescope_unknown"):
    """Check if a warning has already been shown using file-based cache"""
    try:
        if os.path.exists(_warning_cache_file):
            with open(_warning_cache_file, 'r') as f:
                content = f.read()
                return warning_type in content
    except Exception:
        pass
    return False

def mark_warning_as_shown(warning_type="telescope_unknown"):
    """Mark a warning as shown using file-based cache"""
    try:
        with open(_warning_cache_file, 'a') as f:
            f.write(f"{warning_type}\n")
    except Exception:
        pass

def open_xisf_file(file_path, header_only=False):
    """Opens a XISF file and converts it to a FITS-like HDUList structure.
    Returns an HDUList ready for .data and .header reading.
    Extracts all FITS keywords from FITSKeywords and geometry information.
    
    Args:
        file_path: Path to the XISF file
        header_only: If True, skip reading image data for faster header-only access
    """
    if not XISF_AVAILABLE:
        raise ImportError("xisf library is not installed. Install with: pip install xisf")
    
    try:
        xisf_file = XISF(file_path)
        images_metadata = xisf_file.get_images_metadata()
    except Exception as e:
        # If XISF library fails (e.g., "file doesn't have a xisf signature"),
        # it might be a FITS file with wrong extension - re-raise with clearer message
        error_msg = str(e).lower()
        if 'signature' in error_msg or 'xisf' in error_msg:
            raise Exception(f"File does not appear to be a valid XISF file (missing XISF signature). "
                          f"It might be a FITS file with a .xisf extension. Error: {str(e)}")
        raise
    
    if not images_metadata:
        raise ValueError("No images found in XISF file")
    
    # Use the first image's metadata
    metadata = images_metadata[0]
    
    # Only read image data if header_only is False (optimization for header-only access)
    image_data = None
    if not header_only:
        # Try to read the image data
        try:
            image_data = xisf_file.read_image(0)  # Read first image
            # Convert to numpy array if needed
            if MATPLOTLIB_AVAILABLE:
                if not isinstance(image_data, np.ndarray):
                    image_data = np.array(image_data)
            else:
                # If numpy not available, try to import it
                try:
                    import numpy as np
                    if not isinstance(image_data, np.ndarray):
                        image_data = np.array(image_data)
                except ImportError:
                    # If numpy is not available, we can't process the data
                    image_data = None
        except Exception as e:
            # If we can't read the data, set it to None (header-only mode)
            image_data = None
    
    # Create a FITS header from XISF metadata
    header = fits.Header()
    
    # First, extract all FITS keywords from FITSKeywords (most important)
    if 'FITSKeywords' in metadata:
        fits_keywords = metadata['FITSKeywords']
        for fits_key, value_list in fits_keywords.items():
            if isinstance(value_list, list) and len(value_list) > 0:
                # Extract value and comment from the first entry
                entry = value_list[0]
                if isinstance(entry, dict):
                    value = entry.get('value', None)
                    comment = entry.get('comment', '')
                    
                    # Add to header with proper formatting
                    try:
                        if value is not None:
                            # Convert value to appropriate type
                            if isinstance(value, str):
                                # Try to convert numeric strings
                                try:
                                    if '.' in value:
                                        value = float(value)
                                    else:
                                        value = int(value)
                                except ValueError:
                                    pass  # Keep as string
                            
                            # Add to header (skip NAXIS1/NAXIS2 from FITSKeywords as they may not be correct)
                            # We'll add them from geometry instead
                            if fits_key not in ['NAXIS1', 'NAXIS2']:
                                if comment:
                                    header[fits_key] = (value, comment)
                                else:
                                    header[fits_key] = value
                    except Exception:
                        pass  # Skip problematic keywords
    
    # Also add other XISF metadata as additional keywords (if not already in header)
    for key, value in metadata.items():
        if key not in ['FITSKeywords', 'geometry', 'location', 'compression', 'dtype', 'sampleFormat', 'colorSpace']:
            # Convert key to uppercase FITS format
            fits_key = key.upper().replace('-', '_').replace(' ', '_')
            # Truncate to 8 characters for FITS standard
            if len(fits_key) > 8:
                fits_key = fits_key[:8]
            
            # Only add if not already in header and not NAXIS1/NAXIS2 (we'll add them from geometry)
            if fits_key not in header and fits_key not in ['NAXIS1', 'NAXIS2']:
                try:
                    if isinstance(value, (int, float)):
                        header[fits_key] = value
                    elif isinstance(value, str):
                        # Truncate string values to 68 characters (FITS limit)
                        header[fits_key] = value[:68] if len(value) > 68 else value
                    else:
                        header[fits_key] = str(value)[:68]
                except Exception:
                    pass  # Skip problematic keywords
    
    # Add geometry information (NAXIS1, NAXIS2) - do this LAST to ensure it's not overwritten
    # Always add from geometry (it's more reliable than FITSKeywords for dimensions)
    # This must be done after all other metadata extraction to ensure NAXIS1/NAXIS2 are set
    if 'geometry' in metadata:
        geom = metadata['geometry']
        if isinstance(geom, (tuple, list)) and len(geom) >= 2:
            # geometry is typically (width, height, channels)
            header['NAXIS1'] = int(geom[0])
            header['NAXIS2'] = int(geom[1])
            if len(geom) >= 3:
                header['NAXIS'] = 2 if geom[2] == 1 else 3
        elif isinstance(geom, dict):
            if 'width' in geom:
                header['NAXIS1'] = int(geom['width'])
            if 'height' in geom:
                header['NAXIS2'] = int(geom['height'])
    
    # Fallback: Use image dimensions if geometry not available
    if ('NAXIS1' not in header or 'NAXIS2' not in header) and image_data is not None:
        try:
            if len(image_data.shape) >= 2:
                header['NAXIS1'] = int(image_data.shape[1])
                header['NAXIS2'] = int(image_data.shape[0])
                header['NAXIS'] = len(image_data.shape)
        except Exception:
            pass  # Skip if image data extraction fails
    
    # Ensure NAXIS is set if we have dimensions
    if 'NAXIS1' in header and 'NAXIS2' in header and 'NAXIS' not in header:
        header['NAXIS'] = 2
    
    # Create a PrimaryHDU with the header and data
    # Note: When creating PrimaryHDU with data, astropy automatically sets NAXIS1/NAXIS2 from data shape
    # So we need to ensure the header is set correctly after HDU creation
    try:
        if image_data is not None:
            primary_hdu = fits.PrimaryHDU(data=image_data, header=header)
            # Ensure NAXIS1/NAXIS2 are set from geometry if available (geometry is more reliable)
            if 'geometry' in metadata:
                geom = metadata['geometry']
                if isinstance(geom, (tuple, list)) and len(geom) >= 2:
                    primary_hdu.header['NAXIS1'] = int(geom[0])
                    primary_hdu.header['NAXIS2'] = int(geom[1])
                    if len(geom) >= 3:
                        primary_hdu.header['NAXIS'] = 2 if geom[2] == 1 else 3
                elif isinstance(geom, dict):
                    if 'width' in geom:
                        primary_hdu.header['NAXIS1'] = int(geom['width'])
                    if 'height' in geom:
                        primary_hdu.header['NAXIS2'] = int(geom['height'])
        else:
            primary_hdu = fits.PrimaryHDU(header=header)
            # For header-only mode, geometry should already be in header, but ensure it's there
            if 'geometry' in metadata and ('NAXIS1' not in primary_hdu.header or 'NAXIS2' not in primary_hdu.header):
                geom = metadata['geometry']
                if isinstance(geom, (tuple, list)) and len(geom) >= 2:
                    primary_hdu.header['NAXIS1'] = int(geom[0])
                    primary_hdu.header['NAXIS2'] = int(geom[1])
                    if len(geom) >= 3:
                        primary_hdu.header['NAXIS'] = 2 if geom[2] == 1 else 3
        
        # Ensure NAXIS is set if we have dimensions
        if 'NAXIS1' in primary_hdu.header and 'NAXIS2' in primary_hdu.header and 'NAXIS' not in primary_hdu.header:
            primary_hdu.header['NAXIS'] = 2
        
        hdul = fits.HDUList([primary_hdu])
        
        return hdul
    except Exception as e:
        raise Exception(f"Error reading XISF file: {str(e)}")

def get_file_signature(file_path):
    """
    Extract a unique signature from a FITS/XISF file based on header metadata.
    This allows detecting duplicates even across different folders or with different names.
    
    The signature is based on:
    - DATE-OBS: Exact observation timestamp
    - OBJECT: Target name
    - EXPTIME: Exposure duration
    - FILTER: Filter used
    - INSTRUMENT: Camera/instrument
    - NAXIS1/NAXIS2: Image dimensions
    - CCD-TEMP: Sensor temperature (if available)
    - GAIN/EGAIN: Camera gain setting
    - FRAME/IMAGENUM: Frame number if available
    
    Two files with identical signatures are considered duplicates (same observation).
    
    Returns: (signature_tuple, header_info_dict) or (None, None) if unreadable
    """
    try:
        # Check cache first to avoid re-reading headers
        cached_info = get_cached_header_info(file_path)
        if cached_info:
            # Reconstruct signature from cached info
            # IMPORTANT: Keep this in sync with the signature tuple built below.
            # Pour tous les types (LIGHT/BIAS/DARK/FLAT), on utilise:
            #   - date_obs normalisée
            #   - type d'image
            #   - temps de pose arrondi
            #   - résolution
            #   - binning
            #   - et pour les poses < 1s: un numéro de frame si disponible
            try:
                exptime_val = cached_info.get('exptime', 0)
                exptime_rounded = round(float(exptime_val), 2) if exptime_val else 0
            except Exception:
                exptime_rounded = 0

            image_type = cached_info.get('type', 'LIGHT') or 'LIGHT'
            naxis1 = cached_info.get('naxis1', 0)
            naxis2 = cached_info.get('naxis2', 0)
            binning = cached_info.get('binning', '') or ''
            frame_no = cached_info.get('frame_no', '') or ''
            # Default binning to 1x1 when dimensions are known but no bin info
            if not binning and naxis1 and naxis2:
                binning = '1x1'

            if exptime_rounded < 1.0 and frame_no:
                signature = (
                    cached_info.get('date_obs', ''),
                    image_type,
                    exptime_rounded,
                    naxis1,
                    naxis2,
                    binning,
                    frame_no,
                )
            else:
                signature = (
                    cached_info.get('date_obs', ''),
                    image_type,
                    exptime_rounded,
                    naxis1,
                    naxis2,
                    binning,
                )
            return signature, cached_info
        
        file_path_str = str(file_path).lower()
        header = None
        
        # Read header based on file type
        if file_path_str.endswith('.xisf'):
            # Primary method: dedicated XISF → FITS-like converter (uses xisf library when available)
            if XISF_AVAILABLE:
                try:
                    hdul = open_xisf_file(file_path, header_only=True)
                    if hdul and len(hdul) > 0:
                        header = hdul[0].header
                except Exception:
                    # Fall through to other strategies below
                    header = None
            
            # Robust fallback: manual XISF parser (works even without xisf library)
            if header is None:
                try:
                    # _read_xisf_manual returns (data, header_dict)
                    _, header_dict = _read_xisf_manual(str(file_path))
                    if header_dict:
                        # For the rest of this function we only need a dict-like object
                        header = header_dict
                except Exception:
                    header = None
            
            # Last resort: try reading as FITS (for rare "FITS in .xisf" files)
            if header is None and ASTROPY_AVAILABLE:
                try:
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter('ignore')
                        try:
                            with fits.open(str(file_path), memmap=True, ignore_missing_simple=True, output_verify='ignore') as hdul:
                                header = get_best_header(hdul)
                        except TypeError:
                            with fits.open(str(file_path), memmap=True, ignore_missing_simple=True) as hdul:
                                header = get_best_header(hdul)
                except Exception:
                    try:
                        header = fits.getheader(str(file_path))
                    except Exception:
                        header = None
        elif file_path_str.endswith(('.xifs', '.xif')):
            # .xifs and .xif are FITS files with non-standard extensions
            if ASTROPY_AVAILABLE:
                try:
                    with fits.open(str(file_path), memmap=True) as hdul:
                        header = get_best_header(hdul)
                except Exception:
                    try:
                        header = fits.getheader(str(file_path))
                    except Exception:
                        pass
        else:
            # FITS files (.fits, .fit, .fits.fz)
            if ASTROPY_AVAILABLE:
                try:
                    # For .fits.fz, check both primary and extension 1
                    with fits.open(str(file_path), memmap=True) as hdul:
                        header = get_best_header(hdul)
                except Exception:
                    try:
                        header = fits.getheader(str(file_path))
                        # For .fits.fz, try extension 1 if primary is minimal
                        if file_path_str.endswith('.fits.fz') and len(header) < 20:
                            try:
                                header = fits.getheader(str(file_path), ext=1)
                            except Exception:
                                pass
                    except Exception:
                        pass
        
        if header is None:
            return None, None
        
        # Extract key metadata for signature
        # These fields together uniquely identify an observation
        
        # Date/time of observation (most important for uniqueness)
        # Normalisation robuste pour que FITS et XISF qui décrivent le même instant
        # (DATE-OBS, JD, MJD-OBS, etc.) produisent exactement la même valeur.
        date_obs = ''
        
        def _normalize_time_value(val, kind='fits'):
            """Return a canonical ISO time string when possible, else a stripped string."""
            if not val:
                return ''
            # Try to use astropy for robust parsing when available
            if ASTROPY_AVAILABLE:
                try:
                    from astropy.time import Time
                    if kind == 'jd':
                        t = Time(float(val), format='jd')
                    elif kind == 'mjd':
                        t = Time(float(val), format='mjd')
                    else:
                        # 'fits' format is tolerant and supports many DATE-OBS variants
                        t = Time(val, format='fits')
                    # Use high precision isot representation to unify formats
                    return t.isot
                except Exception:
                    pass
            # Fallback: raw string
            try:
                return str(val).strip()
            except Exception:
                return ''
        
        # 1) Prefer explicit DATE-OBS/DATE-BEG/DATE
        for key in ['DATE-OBS', 'DATE-BEG', 'DATE']:
            val = header.get(key, '')
            if val:
                norm = _normalize_time_value(val, kind='fits')
                if norm:
                    date_obs = norm
                    break
        
        # 2) If not found, try JD
        if not date_obs:
            val = header.get('JD', '')
            if val not in ['', None]:
                norm = _normalize_time_value(val, kind='jd')
                if norm:
                    date_obs = norm
        
        # 3) If still not found, try MJD-OBS
        if not date_obs:
            val = header.get('MJD-OBS', '')
            if val not in ['', None]:
                norm = _normalize_time_value(val, kind='mjd')
                if norm:
                    date_obs = norm
        
        # 4) Last resort: combine UT-DATE and UT-TIME if present
        if not date_obs:
            ut_date = header.get('UT-DATE', '')
            ut_time = header.get('UT-TIME', '')
            if ut_date or ut_time:
                combined = f"{str(ut_date).strip()}T{str(ut_time).strip()}" if ut_time else str(ut_date).strip()
                norm = _normalize_time_value(combined, kind='fits')
                date_obs = norm or combined
        
        # Object/target name
        obj_name = ''
        for key in ['OBJECT', 'TARGET', 'OBJNAME', 'TARGNAME', 'OBJCTNAM']:
            val = header.get(key, '')
            if val:
                obj_name = str(val).strip().upper()
                break
        
        # Exposure time
        exptime = 0
        for key in ['EXPTIME', 'EXPOSURE', 'EXPOTIME', 'EXPTIME1', 'EXP-TIME', 'INTTIME']:
            val = header.get(key, None)
            if val is not None:
                try:
                    exptime = float(val)
                    break
                except Exception:
                    pass
        
        # Image type (LIGHT, FLAT, DARK, BIAS) - needed for Phase 3 filtering
        image_type = 'LIGHT'  # Default
        imagetyp = header.get('IMAGETYP', '')
        if isinstance(imagetyp, str):
            imagetyp_upper = imagetyp.upper()
            if 'FLAT' in imagetyp_upper:
                image_type = 'FLAT'
            elif 'DARK' in imagetyp_upper:
                image_type = 'DARK'
            elif 'BIAS' in imagetyp_upper:
                image_type = 'BIAS'
        # Also check FRAME keyword (some software uses this)
        if image_type == 'LIGHT':
            frame_type = header.get('FRAME', '')
            if isinstance(frame_type, str):
                frame_upper = frame_type.upper()
                if 'FLAT' in frame_upper:
                    image_type = 'FLAT'
                elif 'DARK' in frame_upper:
                    image_type = 'DARK'
                elif 'BIAS' in frame_upper:
                    image_type = 'BIAS'
        
        # Filter
        filter_name = ''
        for key in ['FILTER', 'FILTER1', 'FILTER2', 'FILTNAM', 'FWHEEL', 'FLTWHEEL']:
            val = header.get(key, '')
            if val and str(val).strip():
                # Normalise Greek Unicode chars (e.g. Hα → Ha) before upper()
                from gui.theme import normalize_filter_name
                filter_name = normalize_filter_name(str(val).strip()).upper()
                break
        
        # Instrument/camera and telescope (multiple FITS keywords)
        inst_raw = get_instrument_from_header(header)
        telescope = get_telescope_from_header(header)
        instrument = (inst_raw.upper() if inst_raw and inst_raw != 'Unknown' else '')
        
        # Image dimensions
        naxis1 = header.get('NAXIS1', 0)
        naxis2 = header.get('NAXIS2', 0)
        try:
            naxis1 = int(naxis1) if naxis1 else 0
            naxis2 = int(naxis2) if naxis2 else 0
        except Exception:
            naxis1, naxis2 = 0, 0
        
        # CCD temperature (useful for distinguishing calibration frames)
        ccd_temp = None
        for key in ['CCD-TEMP', 'CCDTEMP', 'TEMPERAT', 'TEMP', 'SET-TEMP']:
            val = header.get(key, None)
            if val is not None:
                try:
                    ccd_temp = round(float(val), 1)
                    break
                except Exception:
                    pass
        
        # Gain setting
        gain = None
        for key in ['GAIN', 'EGAIN', 'CCDGAIN', 'ISOSPEED', 'ISO']:
            val = header.get(key, None)
            if val is not None:
                try:
                    gain = round(float(val), 2)
                    break
                except Exception:
                    pass
        
        # Frame number if available (helps distinguish sequential frames)
        frame_no = ''
        for key in ['FRAMENUM', 'FRAME', 'IMAGENUM', 'EXPNUM', 'FRAMENO', 'IMGNUM', 'SEQNUM']:
            val = header.get(key, '')
            if val:
                frame_no = str(val).strip()
                break
        # For very short exposures, try to extract an index from the filename if header is missing it
        if (not frame_no) and exptime is not None:
            try:
                exptime_val = float(exptime)
            except Exception:
                exptime_val = None
            if exptime_val is not None and exptime_val < 1.0:
                import re, os as _os
                fname = _os.path.basename(str(file_path))
                # Common patterns: _0001, -0001, (1), ending with digits before extension
                m = re.search(r'(?:[_\-])(\d{3,5})(?=\.[^.]+$)', fname)
                if not m:
                    m = re.search(r'\((\d{1,5})\)(?=\.[^.]+$)', fname)
                if not m:
                    m = re.search(r'(\d{1,5})(?=\.[^.]+$)', fname)
                if m:
                    frame_no = m.group(1)
        
        # Binning (some duplicates differ only by binning value in filename)
        binning = ''
        xbin = header.get('XBINNING', header.get('XBIN', header.get('BINX', '')))
        ybin = header.get('YBINNING', header.get('YBIN', header.get('BINY', '')))
        if xbin and ybin:
            try:
                binning = f"{int(xbin)}x{int(ybin)}"
            except Exception:
                pass
        
        # If binning is missing but dimensions are known, assume 1x1 by default
        if not binning and naxis1 and naxis2:
            binning = '1x1'

        # Create signature tuple (immutable for hashing)
        # Round exptime to avoid floating point comparison issues
        try:
            exptime_rounded = round(float(exptime), 2) if exptime else 0
        except Exception:
            exptime_rounded = 0
        
        # Signature definition (tous types):
        #   - date_obs normalisée
        #   - image_type (LIGHT/BIAS/DARK/FLAT)
        #   - exptime_rounded
        #   - naxis1/naxis2
        #   - binning
        #   - et pour les poses < 1s: frame_no si disponible (pour distinguer les rafales)
        if exptime_rounded < 1.0 and frame_no:
            signature = (
                date_obs,
                image_type,
                exptime_rounded,
                naxis1,
                naxis2,
                binning,
                frame_no,
            )
        else:
            signature = (
                date_obs,
                image_type,
                exptime_rounded,
                naxis1,
                naxis2,
                binning,
            )
        
        # Also return useful info for reporting
        info = {
            'date_obs': date_obs,
            'object': obj_name,
            'exptime': exptime_rounded,
            'filter': filter_name,
            'instrument': inst_raw if inst_raw else 'Unknown',
            'telescope': telescope,
            'dimensions': f"{naxis1}x{naxis2}",
            'ccd_temp': ccd_temp,
            'gain': gain,
            'frame_no': frame_no,
            'binning': binning,
            # Additional info for Phase 3 cache (to avoid re-reading headers)
            'target': obj_name,  # Normalized target name
            'naxis1': naxis1,
            'naxis2': naxis2,
            'type': image_type,  # LIGHT, FLAT, DARK, BIAS - for Phase 3 filtering
        }
        
        # Cache the info for later use in Phase 3
        cache_header_info(file_path, info)
        
        return signature, info
        
    except Exception as e:
        return None, None


def remove_compressed_duplicates(file_list, check_abort=None):
    """
    Remove duplicate files using TWO-LEVEL intelligent deduplication:
    
    LEVEL 1 - Name-based deduplication:
        Files with same base name but different extensions are duplicates.
        Example: image001.fits and image001.fits.fz are the same image.
        Priority: .fits > .fit > .xisf > .xifs > .xif > .fits.fz
    
    LEVEL 2 - Content-based deduplication (cross-folder):
        Files with identical FITS headers are duplicates, even if:
        - They have different names (e.g., renamed copies)
        - They are in different folders (e.g., backup copies)
        - They have different extensions (e.g., compressed versions)
        
        Signature is based on: DATE-OBS, OBJECT, EXPTIME, FILTER, INSTRUMENT,
        NAXIS1, NAXIS2, CCD-TEMP, GAIN, FRAME, BINNING
    
    This ensures NO duplicate observations are counted in statistics,
    while preserving the highest quality version of each file.
    
    Returns: deduplicated list of file paths
    """
    if not file_list:
        return []
    
    # Extension priority (lower index = higher priority = preferred)
    # Default: XISF preferred (best compression), then fits.fz, then uncompressed
    # This can be customized via prefer_format parameter
    default_priority = ['.xisf', '.xifs', '.xif', '.fits.fz', '.fits', '.fit']
    
    # Allow customization of priority based on user preference
    if hasattr(remove_compressed_duplicates, 'prefer_format'):
        pref = remove_compressed_duplicates.prefer_format
        if pref == 'fits':
            priority_order = ['.fits', '.fit', '.xisf', '.xifs', '.xif', '.fits.fz']
        elif pref == 'fz':
            priority_order = ['.fits.fz', '.fits', '.fit', '.xisf', '.xifs', '.xif']
        elif pref == 'xisf':
            priority_order = ['.xisf', '.xifs', '.xif', '.fits.fz', '.fits', '.fit']
        else:
            priority_order = default_priority
    else:
        priority_order = default_priority
    
    def get_extension(file_path):
        """Get normalized extension"""
        file_lower = str(file_path).lower()
        if file_lower.endswith('.fits.fz'):
            return '.fits.fz'
        elif file_lower.endswith('.fits'):
            return '.fits'
        elif file_lower.endswith('.fit'):
            return '.fit'
        elif file_lower.endswith('.xisf'):
            return '.xisf'
        elif file_lower.endswith('.xifs'):
            return '.xifs'
        elif file_lower.endswith('.xif'):
            return '.xif'
        return ''
    
    def get_base_name(file_path):
        """Get base name without extension (case-insensitive)"""
        file_str = str(file_path)
        file_lower = file_str.lower()
        
        if file_lower.endswith('.fits.fz'):
            return file_str[:-8]
        elif file_lower.endswith('.fits'):
            return file_str[:-5]
        elif file_lower.endswith('.fit'):
            return file_str[:-4]
        elif file_lower.endswith('.xisf'):
            return file_str[:-5]
        elif file_lower.endswith('.xifs'):
            return file_str[:-5]
        elif file_lower.endswith('.xif'):
            return file_str[:-4]
        return file_str
    
    def get_priority(ext):
        """Get priority index (lower = better)"""
        try:
            return priority_order.index(ext.lower())
        except ValueError:
            return 999
    
    # ========== PHASE 1: Name-based deduplication (same folder) ==========
    # Group files by base name (without extension)
    base_name_groups = {}
    
    for file_path in file_list:
        base_name = get_base_name(file_path).lower()
        ext = get_extension(file_path)
        
        if base_name not in base_name_groups:
            base_name_groups[base_name] = []
        base_name_groups[base_name].append((file_path, ext))
    
    # Select best file from each name group
    phase1_files = []
    phase1_skipped = []
    # Map kept_file -> list of skipped alternatives (for fallback if kept file is unreadable)
    phase1_alternatives = {}
    
    for base_name, files in base_name_groups.items():
        if len(files) == 1:
            phase1_files.append(files[0][0])
        else:
            # Sort by priority
            files_sorted = sorted(files, key=lambda x: get_priority(x[1]))
            selected = files_sorted[0]
            phase1_files.append(selected[0])
            
            # Store alternatives for fallback (in case preferred format is unreadable)
            phase1_alternatives[str(selected[0]).lower()] = [(f, ext) for f, ext in files_sorted[1:]]
            
            # Track skipped and store as duplicates
            for f, ext in files_sorted[1:]:
                phase1_skipped.append((f, ext, selected[1]))
                # Store for extraction feature
                add_detected_duplicate(f, selected[0], f"Format {ext} remplacé par {selected[1]}", 'name_based')
    
    # Report Phase 1 results
    if phase1_skipped:
        if SYSTEM_LANGUAGE == 'fr':
            print(f"ℹ️  Déduplication par nom: {len(phase1_skipped)} fichier(s) ignoré(s) (version préférée trouvée)")
        else:
            print(f"ℹ️  Name-based deduplication: {len(phase1_skipped)} file(s) ignored (preferred version found)")
        
        # Group by extension for cleaner output
        by_ext = {}
        for f, ext, preferred in phase1_skipped:
            if ext not in by_ext:
                by_ext[ext] = 0
            by_ext[ext] += 1
        
        for ext, count in by_ext.items():
            print(f"   - {count} fichier(s) {ext}")
    
    # ========== PHASE 2: Content-based deduplication (across folders) ==========
    # This detects files with same content but different names/locations
    
    if SYSTEM_LANGUAGE == 'fr':
        print("")
        print("=" * 60)
        print("📋 PHASE 2 : DÉDUPLICATION")
        print("=" * 60)
        print(f"🔍 Analyse des signatures de fichiers pour détecter les doublons...")
    else:
        print("")
        print("=" * 60)
        print("📋 PHASE 2: DEDUPLICATION")
        print("=" * 60)
        print(f"🔍 Analyzing file signatures to detect duplicates...")
    
    signature_groups = {}  # signature -> list of (file_path, ext, info)
    unreadable_files = []
    
    # Phase 2: Read signatures - parallelized with ThreadPoolExecutor (I/O bound)
    total_files = len(phase1_files)

    if SYSTEM_LANGUAGE == 'fr':
        print(f"   📋 Phase 2: Lecture des signatures de {total_files} fichiers...")
    else:
        print(f"   📋 Phase 2: Reading signatures of {total_files} files...")

    # Track files that were swapped from preferred to alternative format
    swapped_count = 0

    # Parallel signature reading for large file counts
    _sig_results = {}  # file_path -> (signature, info)
    if total_files > 100:
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            try:
                from core.config import get_config
                _sig_workers = max(2, min(get_config().get_workers(), 8))
            except Exception:
                import multiprocessing
                _sig_workers = max(2, min(multiprocessing.cpu_count(), 8))

            def _read_sig(fp):
                return fp, get_file_signature(fp)

            with ThreadPoolExecutor(max_workers=_sig_workers) as _sig_ex:
                _sig_futures = [_sig_ex.submit(_read_sig, fp) for fp in phase1_files]
                _sig_done = 0
                desc_text = "📋 Phase 2: Signatures"
                if TQDM_AVAILABLE:
                    _sig_iter = tqdm(as_completed(_sig_futures), total=total_files, desc=desc_text, unit="file")
                else:
                    _sig_iter = as_completed(_sig_futures)
                for future in _sig_iter:
                    if check_abort and callable(check_abort) and check_abort():
                        _sig_ex.shutdown(wait=False, cancel_futures=True)
                        return None
                    fp, (sig, info) = future.result()
                    _sig_results[fp] = (sig, info)
                    _sig_done += 1
                    report_progress(_sig_done, total_files, "phase2")
        except Exception:
            _sig_results = {}  # Fallback to sequential

    processed = 0
    for file_path in phase1_files:
        if check_abort and callable(check_abort) and check_abort():
            return None  # Signal abort to caller
        if file_path in _sig_results:
            signature, info = _sig_results[file_path]
        else:
            signature, info = get_file_signature(file_path)
        ext = get_extension(file_path)

        processed += 1
        if not _sig_results:
            report_progress(processed, total_files, "phase2")
        
        if signature is None:
            # Can't read this file's signature - try Phase 1 alternatives (fallback)
            # This handles the case where XISF is preferred but unreadable,
            # while the FITS version is perfectly fine
            file_key = str(file_path).lower()
            alternatives = phase1_alternatives.get(file_key, [])
            fallback_found = False
            
            for alt_path, alt_ext in alternatives:
                alt_signature, alt_info = get_file_signature(alt_path)
                if alt_signature is not None:
                    # Alternative is readable! Use it instead
                    if alt_signature[0] or alt_signature[1]:
                        if alt_signature not in signature_groups:
                            signature_groups[alt_signature] = []
                        signature_groups[alt_signature].append((alt_path, alt_ext, alt_info))
                    else:
                        unreadable_files.append(alt_path)
                    
                    # Update duplicate tracking: swap kept/skipped
                    # Remove the old duplicate entry and add new one
                    add_detected_duplicate(file_path, alt_path, 
                        f"Format {ext} illisible, remplacé par {alt_ext}" if SYSTEM_LANGUAGE == 'fr' 
                        else f"Format {ext} unreadable, replaced by {alt_ext}", 'name_based')
                    
                    fallback_found = True
                    swapped_count += 1
                    if SYSTEM_LANGUAGE == 'fr':
                        print(f"   ⚠️  {Path(file_path).name} illisible → utilisation de {Path(alt_path).name}")
                    else:
                        print(f"   ⚠️  {Path(file_path).name} unreadable → using {Path(alt_path).name}")
                    break
            
            if not fallback_found:
                # No readable alternative found, keep original anyway
                unreadable_files.append(file_path)
        else:
            # Only consider as duplicate if signature has meaningful content
            # (not just empty/default values)
            if signature[0] or signature[1]:  # Has date or object name
                if signature not in signature_groups:
                    signature_groups[signature] = []
                signature_groups[signature].append((file_path, ext, info))
            else:
                # No meaningful signature, keep file
                unreadable_files.append(file_path)
    
    # Select best file from each signature group
    final_files = list(unreadable_files)  # Start with unreadable files
    phase2_skipped = []
    
    for signature, files in signature_groups.items():
        if len(files) == 1:
            final_files.append(files[0][0])
        else:
            # Multiple files with same signature = duplicates!
            # Sort by: 1) extension priority, 2) path length (shorter = likely better organized)
            files_sorted = sorted(files, key=lambda x: (get_priority(x[1]), len(str(x[0]))))
            selected = files_sorted[0]
            final_files.append(selected[0])
            
            # Track duplicates and store for extraction
            for f, ext, info in files_sorted[1:]:
                phase2_skipped.append((f, ext, selected[0], info))
                # Store for extraction feature
                add_detected_duplicate(f, selected[0], "Contenu identique", 'content_based', info)
    
    # Report Phase 2 results
    if phase2_skipped:
        if SYSTEM_LANGUAGE == 'fr':
            print(f"⚠️  Doublons détectés par contenu: {len(phase2_skipped)} fichier(s) identique(s) dans des dossiers différents")
        else:
            print(f"⚠️  Content-based duplicates: {len(phase2_skipped)} identical file(s) in different folders")
        
        # Show some examples
        shown = 0
        for f, ext, selected, info in phase2_skipped:
            if shown < 5:
                fname = Path(f).name
                selected_name = Path(selected).name
                if SYSTEM_LANGUAGE == 'fr':
                    print(f"   - '{fname}' identique à '{selected_name}'")
                    if info.get('date_obs'):
                        print(f"     (Date: {info['date_obs']}, Objet: {info.get('object', 'N/A')})")
                else:
                    print(f"   - '{fname}' identical to '{selected_name}'")
                    if info.get('date_obs'):
                        print(f"     (Date: {info['date_obs']}, Object: {info.get('object', 'N/A')})")
                shown += 1
        
        if len(phase2_skipped) > 5:
            if SYSTEM_LANGUAGE == 'fr':
                print(f"   ... et {len(phase2_skipped) - 5} autre(s)")
            else:
                print(f"   ... and {len(phase2_skipped) - 5} more")
    
    total_removed = len(phase1_skipped) + len(phase2_skipped)
    if swapped_count > 0:
        if SYSTEM_LANGUAGE == 'fr':
            print(f"ℹ️  {swapped_count} fichier(s) remplacé(s) par une version alternative lisible")
        else:
            print(f"ℹ️  {swapped_count} file(s) replaced by readable alternative version")
    if total_removed > 0:
        if SYSTEM_LANGUAGE == 'fr':
            print(f"✓ Total: {len(file_list)} → {len(final_files)} fichiers ({total_removed} doublon(s) éliminé(s))")
        else:
            print(f"✓ Total: {len(file_list)} → {len(final_files)} files ({total_removed} duplicate(s) removed)")
    
    return final_files

def _safe_subprocess_run(cmd, timeout=5):
    """
    Run a subprocess command safely with proper encoding handling.
    Returns (returncode, stdout, stderr) with stdout/stderr as strings.
    On encoding errors, returns empty strings instead of crashing.
    """
    import subprocess
    try:
        # Use errors='replace' to handle encoding issues gracefully
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            # Don't use text=True, handle encoding manually
        )
        # Decode with error handling
        try:
            stdout = result.stdout.decode('utf-8', errors='replace')
        except Exception:
            try:
                stdout = result.stdout.decode('latin-1', errors='replace')
            except Exception:
                stdout = ''
        try:
            stderr = result.stderr.decode('utf-8', errors='replace')
        except Exception:
            try:
                stderr = result.stderr.decode('latin-1', errors='replace')
            except Exception:
                stderr = ''
        return result.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        return -1, '', 'timeout'
    except Exception as e:
        return -1, '', str(e)


def detect_storage_type(folder_path):
    """
    Detect storage type (HDD vs SSD) for a given folder path.
    Handles network paths (NAS) and local paths.
    Returns: (is_ssd: bool, storage_info: str)
    """
    is_ssd = True  # Default assumption (optimistic)
    storage_info = "SSD (assumed)"
    
    try:
        import platform
        folder_str = str(folder_path)
        
        # Check if folder is on a network share/NAS (UNC path on Windows, mount point on Linux/Mac)
        is_network_path = False
        if platform.system() == "Windows":
            # Check for UNC path (\\server\share) or mapped network drive
            if folder_str.startswith('\\\\') or (len(folder_str) > 2 and folder_str[0].isalpha() and folder_str[1] == ':'):
                try:
                    # Check if it's a network drive
                    drive_letter = folder_str[0] if len(folder_str) > 2 and folder_str[1] == ':' else None
                    if drive_letter:
                        retcode, stdout, stderr = _safe_subprocess_run(
                            ["net", "use", f"{drive_letter}:"],
                            timeout=2
                        )
                        if "Remote" in stdout or "\\\\" in stdout:
                            is_network_path = True
                    elif folder_str.startswith('\\\\'):
                        is_network_path = True
                except Exception:
                    if folder_str.startswith('\\\\'):
                        is_network_path = True
        else:
            # Linux/Mac: check if path is on a network mount
            try:
                # Use findmnt or mount to check if path is on network filesystem
                retcode, stdout, stderr = _safe_subprocess_run(
                    ["findmnt", "-n", "-o", "FSTYPE", folder_str],
                    timeout=2
                )
                if retcode == 0:
                    fstype = stdout.strip().upper()
                    if any(net_fs in fstype for net_fs in ['NFS', 'CIFS', 'SMB', 'SMBFS', 'CIFS']):
                        is_network_path = True
            except Exception:
                pass
        
        # If it's a network path/NAS, assume HDD (most NAS use HDD)
        if is_network_path:
            is_ssd = False
            storage_info = "HDD (NAS/Network - assumed)"
        else:
            # Try to detect actual storage type for local paths
            try:
                import psutil
                # Get the disk partition where the folder is located
                folder_abs = str(Path(folder_path).resolve())
                
                # Try to detect SSD on Windows
                if platform.system() == "Windows":
                    try:
                        # Use WMI module if available (preferred, no deprecated wmic)
                        try:
                            import wmi
                            c = wmi.WMI()
                            for disk in c.Win32_DiskDrive():
                                model = disk.Model.upper()
                                if 'SSD' in model or 'NVME' in model or 'SOLID STATE' in model:
                                    is_ssd = True
                                    storage_info = "SSD (detected)"
                                    break
                                elif 'HDD' in model or 'HARD DISK' in model:
                                    is_ssd = False
                                    storage_info = "HDD (detected)"
                                    break
                        except ImportError:
                            # WMI not available, try config manager
                            try:
                                from core.config import get_config
                                config = get_config()
                                stype = config.system_caps.get('storage_type', 'ssd')
                                is_ssd = (stype == 'ssd')
                                storage_info = f"{'SSD' if is_ssd else 'HDD'} (auto-detected)"
                            except Exception:
                                pass
                    except Exception:
                        pass
                
                # Try to detect SSD on Linux
                elif platform.system() == "Linux":
                    try:
                        # Get the mount point and check rotational attribute
                        retcode, stdout, stderr = _safe_subprocess_run(
                            ["df", "-P", folder_abs],
                            timeout=2
                        )
                        if retcode == 0:
                            device = stdout.split('\n')[1].split()[0] if len(stdout.split('\n')) > 1 else None
                            if device and not device.startswith('//'):
                                # Check if device is rotational (HDD) or not (SSD)
                                device_name = device.split('/')[-1].rstrip('0123456789')
                                retcode2, stdout2, stderr2 = _safe_subprocess_run(
                                    ["cat", f"/sys/block/{device_name}/queue/rotational"],
                                    timeout=1
                                )
                                if retcode2 == 0:
                                    rotational = stdout2.strip()
                                    if rotational == "0":
                                        is_ssd = True
                                        storage_info = "SSD (detected)"
                                    else:
                                        is_ssd = False
                                        storage_info = "HDD (detected)"
                    except Exception:
                        pass
                
                # macOS: try to detect, but assume SSD for local paths
                elif platform.system() == "Darwin":
                    # For macOS, assume SSD for local paths (most Macs have SSD)
                    is_ssd = True
                    storage_info = "SSD (macOS - assumed local)"
            except Exception:
                pass
    except Exception:
        pass
    
    return is_ssd, storage_info

def get_best_header(hdul):
    """Gets the best header from HDUList, checking extensions if primary header is minimal.
    For .fits.fz files, metadata is often in extension HDU 1.
    Returns the header with the most metadata.
    """
    if len(hdul) == 0:
        return None
    
    primary_header = hdul[0].header
    
    # Check if primary header has essential keywords
    essential_keys = ['EXPTIME', 'EXPOSURE', 'IMAGETYP', 'FILTER', 'INSTRUME', 'TELESCOP']
    has_essential = any(key in primary_header for key in essential_keys)
    
    # If primary header has essential keys, use it
    if has_essential or len(primary_header) > 20:
        return primary_header
    
    # Otherwise, check extensions for a better header
    best_header = primary_header
    best_key_count = len(primary_header)
    
    for i in range(1, len(hdul)):
        ext_header = hdul[i].header
        key_count = len(ext_header)
        
        # Prefer extension with more keys and essential metadata
        if key_count > best_key_count:
            ext_has_essential = any(key in ext_header for key in essential_keys)
            if ext_has_essential or key_count > best_key_count * 2:
                best_header = ext_header
                best_key_count = key_count
    
    return best_header

def open_fits_for_data(file_path, header_only=False):
    """Opens a FITS file (including .fits.fz, .xifs, .xif) or XISF file choosing memmap according to header.
    If BZERO/BSCALE/BLANK are present, uses memmap=False (required by astropy).
    Returns an HDUList ready for .data and .header reading.
    
    Args:
        file_path: Path to the FITS or XISF file
        header_only: If True, for XISF files, skip reading image data for faster header-only access
    """
    file_path_str = str(file_path).lower()
    
    # Handle XISF files (.xisf only - .xifs/.xif are treated as FITS files)
    if file_path_str.endswith('.xisf'):
        try:
            return open_xisf_file(file_path, header_only=header_only)
        except Exception as e:
            # If XISF fails but error suggests it might be a FITS file, try opening as FITS
            error_msg = str(e).lower()
            if 'signature' in error_msg or 'does not appear to be a valid xisf' in error_msg:
                # Try opening as FITS file (might be misnamed)
                try:
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter('ignore')
                        try:
                            hdul = fits.open(file_path, memmap=True, ignore_missing_simple=True, output_verify='ignore')
                        except TypeError:
                            hdul = fits.open(file_path, memmap=True, ignore_missing_simple=True)
                        header = hdul[0].header
                        if ('BZERO' in header) or ('BSCALE' in header) or ('BLANK' in header):
                            hdul.close()
                            with warnings.catch_warnings():
                                warnings.simplefilter('ignore')
                                try:
                                    return fits.open(file_path, memmap=False, ignore_missing_simple=True, output_verify='ignore')
                                except TypeError:
                                    return fits.open(file_path, memmap=False, ignore_missing_simple=True)
                        return hdul
                except Exception:
                    # Re-raise original XISF error if FITS also fails
                    raise e
            raise
    
    # Handle FITS files (including .fits.fz, .xifs, .xif - astropy handles these automatically)
    try:
        # Suppress warnings when opening FITS files
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            # Try with output_verify parameter (if supported)
            try:
                hdul = fits.open(file_path, memmap=True, ignore_missing_simple=True, output_verify='ignore')
            except TypeError:
                # Fallback if output_verify not supported
                hdul = fits.open(file_path, memmap=True, ignore_missing_simple=True)
            header = hdul[0].header
            if ('BZERO' in header) or ('BSCALE' in header) or ('BLANK' in header):
                hdul.close()
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    try:
                        return fits.open(file_path, memmap=False, ignore_missing_simple=True, output_verify='ignore')
                    except TypeError:
                        return fits.open(file_path, memmap=False, ignore_missing_simple=True)
            return hdul
    except Exception as e:
        # Handle specific FITS file issues
        if "Header missing END card" in str(e):
            raise Exception(f"Header missing END card")
        elif "non-ASCII characters" in str(e):
            raise Exception(f"Non-ASCII characters in header")
        elif "null bytes" in str(e):
            raise Exception(f"Non-compliant FITS header (null bytes)")
        else:
            # Safe fallback for other errors
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                try:
                    return fits.open(file_path, memmap=False, ignore_missing_simple=True, output_verify='ignore')
                except TypeError:
                    return fits.open(file_path, memmap=False, ignore_missing_simple=True)

# CCD/CMOS sensor database with their characteristics
SENSORS_DATABASE = {
    # ZWO Cameras
    'ASI1600MM': {'gain': 139, 'read_noise': 1.2, 'full_well': 20000, 'pixel_size': 3.8, 'quantum_efficiency': 0.6, 'width_px': 4656, 'height_px': 3520},
    'ASI1600MM-Pro': {'gain': 139, 'read_noise': 1.2, 'full_well': 20000, 'pixel_size': 3.8, 'quantum_efficiency': 0.6, 'width_px': 4656, 'height_px': 3520},
    'ASI2600MM': {'gain': 100, 'read_noise': 1.0, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 6248, 'height_px': 4176},
    'ASI2600MM-Pro': {'gain': 100, 'read_noise': 1.0, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 6248, 'height_px': 4176},
    'ASI6200MM': {'gain': 100, 'read_noise': 1.0, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 9576, 'height_px': 6388},
    'ASI6200MM-Pro': {'gain': 100, 'read_noise': 1.0, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 9576, 'height_px': 6388},
    'ASI294MM': {'gain': 120, 'read_noise': 1.2, 'full_well': 42000, 'pixel_size': 4.63, 'quantum_efficiency': 0.75, 'width_px': 4144, 'height_px': 2822},
    'ASI294MM-Pro': {'gain': 120, 'read_noise': 1.2, 'full_well': 42000, 'pixel_size': 4.63, 'quantum_efficiency': 0.75, 'width_px': 4144, 'height_px': 2822},
    'ASI533MM': {'gain': 100, 'read_noise': 1.0, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 3008, 'height_px': 3008},
    'ASI533MM-Pro': {'gain': 100, 'read_noise': 1.0, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 3008, 'height_px': 3008},
    'ASI183MM': {'gain': 111, 'read_noise': 1.1, 'full_well': 15000, 'pixel_size': 2.4, 'quantum_efficiency': 0.54, 'width_px': 5496, 'height_px': 3672},
    'ASI183MM-Pro': {'gain': 111, 'read_noise': 1.1, 'full_well': 15000, 'pixel_size': 2.4, 'quantum_efficiency': 0.54, 'width_px': 5496, 'height_px': 3672},
    'ASI178MM': {'gain': 139, 'read_noise': 1.2, 'full_well': 20000, 'pixel_size': 2.4, 'quantum_efficiency': 0.6, 'width_px': 1920, 'height_px': 1080},
    'ASI178MM-Pro': {'gain': 139, 'read_noise': 1.2, 'full_well': 20000, 'pixel_size': 2.4, 'quantum_efficiency': 0.6, 'width_px': 1920, 'height_px': 1080},
    'ASI174MM': {'gain': 139, 'read_noise': 1.2, 'full_well': 20000, 'pixel_size': 5.86, 'quantum_efficiency': 0.6, 'width_px': 1920, 'height_px': 1200},
    'ASI174MM-Pro': {'gain': 139, 'read_noise': 1.2, 'full_well': 20000, 'pixel_size': 5.86, 'quantum_efficiency': 0.6, 'width_px': 1920, 'height_px': 1200},
    'ASI290MM': {'gain': 139, 'read_noise': 1.2, 'full_well': 20000, 'pixel_size': 2.9, 'quantum_efficiency': 0.6, 'width_px': 1920, 'height_px': 1080},
    'ASI290MM-Pro': {'gain': 139, 'read_noise': 1.2, 'full_well': 20000, 'pixel_size': 2.9, 'quantum_efficiency': 0.6, 'width_px': 1920, 'height_px': 1080},
    'ASI224MC': {'gain': 139, 'read_noise': 1.2, 'full_well': 20000, 'pixel_size': 3.75, 'quantum_efficiency': 0.6, 'width_px': 1280, 'height_px': 960},
    'ASI224MC-Pro': {'gain': 139, 'read_noise': 1.2, 'full_well': 20000, 'pixel_size': 3.75, 'quantum_efficiency': 0.6, 'width_px': 1280, 'height_px': 960},
    'ASI385MC': {'gain': 139, 'read_noise': 1.2, 'full_well': 20000, 'pixel_size': 3.75, 'quantum_efficiency': 0.6, 'width_px': 1280, 'height_px': 960},
    'ASI385MC-Pro': {'gain': 139, 'read_noise': 1.2, 'full_well': 20000, 'pixel_size': 3.75, 'quantum_efficiency': 0.6, 'width_px': 1280, 'height_px': 960},
    
    # QHY Cameras
    'QHY600M': {'gain': 100, 'read_noise': 1.0, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 9576, 'height_px': 6388},
    'QHY600M-P': {'gain': 100, 'read_noise': 1.0, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 9576, 'height_px': 6388},
    'QHY268M': {'gain': 100, 'read_noise': 1.0, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 6248, 'height_px': 4176},
    'QHY268M-P': {'gain': 100, 'read_noise': 1.0, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 6248, 'height_px': 4176},
    'QHY163M': {'gain': 111, 'read_noise': 1.1, 'full_well': 15000, 'pixel_size': 3.8, 'quantum_efficiency': 0.54, 'width_px': 4656, 'height_px': 3520},
    'QHY163M-P': {'gain': 111, 'read_noise': 1.1, 'full_well': 15000, 'pixel_size': 3.8, 'quantum_efficiency': 0.54, 'width_px': 4656, 'height_px': 3520},
    'QHY367C': {'gain': 100, 'read_noise': 1.0, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 6240, 'height_px': 4160},
    'QHY367C-P': {'gain': 100, 'read_noise': 1.0, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 6240, 'height_px': 4160},
    
    # FLI Cameras
    'FLI-ML16200': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 6.0, 'quantum_efficiency': 0.6, 'width_px': 4096, 'height_px': 4096},
    'FLI-ML8300': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 5.4, 'quantum_efficiency': 0.6, 'width_px': 3326, 'height_px': 2504},
    'FLI-ML11002': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 9.0, 'quantum_efficiency': 0.6, 'width_px': 4008, 'height_px': 2672},
    'FLI-ML16803': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 9.0, 'quantum_efficiency': 0.6, 'width_px': 4096, 'height_px': 4096},
    
    # SBIG Cameras
    'STF-8300M': {'gain': 0.37, 'read_noise': 9.3, 'full_well': 25000, 'pixel_size': 5.4, 'quantum_efficiency': 0.6, 'width_px': 3326, 'height_px': 2504},
    'STF-8300C': {'gain': 0.37, 'read_noise': 9.3, 'full_well': 25000, 'pixel_size': 5.4, 'quantum_efficiency': 0.6, 'width_px': 3326, 'height_px': 2504},
    'STT-8300M': {'gain': 0.37, 'read_noise': 9.3, 'full_well': 25000, 'pixel_size': 5.4, 'quantum_efficiency': 0.6, 'width_px': 3326, 'height_px': 2504},
    'STT-8300C': {'gain': 0.37, 'read_noise': 9.3, 'full_well': 25000, 'pixel_size': 5.4, 'quantum_efficiency': 0.6, 'width_px': 3326, 'height_px': 2504},
    
    # Atik Cameras
    'ATIK460EXM': {'gain': 0.26, 'read_noise': 6.5, 'full_well': 18000, 'pixel_size': 4.54, 'quantum_efficiency': 0.6, 'width_px': 1280, 'height_px': 1024},
    'ATIK460EXC': {'gain': 0.26, 'read_noise': 6.5, 'full_well': 18000, 'pixel_size': 4.54, 'quantum_efficiency': 0.6, 'width_px': 1280, 'height_px': 1024},
    'ATIK383L+': {'gain': 0.26, 'read_noise': 6.5, 'full_well': 18000, 'pixel_size': 5.4, 'quantum_efficiency': 0.6, 'width_px': 3326, 'height_px': 2504},
    'ATIK383L+ Mono': {'gain': 0.26, 'read_noise': 6.5, 'full_well': 18000, 'pixel_size': 5.4, 'quantum_efficiency': 0.6, 'width_px': 3326, 'height_px': 2504},
    
    # Moravian Cameras
    'G3-16200': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 6.0, 'quantum_efficiency': 0.6, 'width_px': 4096, 'height_px': 4096},
    'G3-8300': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 5.4, 'quantum_efficiency': 0.6, 'width_px': 3326, 'height_px': 2504},
    'G3-11002': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 9.0, 'quantum_efficiency': 0.6, 'width_px': 4008, 'height_px': 2672},
    'G3-16803': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 9.0, 'quantum_efficiency': 0.6, 'width_px': 4096, 'height_px': 4096},
    
    # Moravian G1 series (representative models)
    'G1-0300': {'gain': 1.0, 'read_noise': 7.0, 'full_well': 20000, 'pixel_size': 5.6, 'quantum_efficiency': 0.5, 'width_px': 640, 'height_px': 480},
    'G1-1200': {'gain': 1.0, 'read_noise': 7.0, 'full_well': 20000, 'pixel_size': 3.75, 'quantum_efficiency': 0.5, 'width_px': 1280, 'height_px': 960},

    # Moravian G4 series (large CCDs)
    'G4-16000': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 9.0, 'quantum_efficiency': 0.6, 'width_px': 4096, 'height_px': 4096},
    'G4-9000': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 120000, 'pixel_size': 12.0, 'quantum_efficiency': 0.55, 'width_px': 3056, 'height_px': 3056},
    'G4-11000': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 80000, 'pixel_size': 9.0, 'quantum_efficiency': 0.55, 'width_px': 4008, 'height_px': 2672},

    # Moravian G5 series (modern large-format)
    'G5-16200': {'gain': 1.4, 'read_noise': 8.5, 'full_well': 90000, 'pixel_size': 6.0, 'quantum_efficiency': 0.6, 'width_px': 4500, 'height_px': 3600},
    'G5-16803': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 9.0, 'quantum_efficiency': 0.6, 'width_px': 4096, 'height_px': 4096},

    # Additional ZWO Cameras
    'ASI6200MM': {'gain': 0.1, 'read_noise': 0.8, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.91, 'width_px': 9576, 'height_px': 6388},
    'ASI6200MC': {'gain': 0.1, 'read_noise': 0.8, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.91, 'width_px': 9576, 'height_px': 6388},
    'ASI2600MM': {'gain': 0.1, 'read_noise': 0.8, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.91, 'width_px': 6240, 'height_px': 4160},
    'ASI2600MC': {'gain': 0.1, 'read_noise': 0.8, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.91, 'width_px': 6240, 'height_px': 4160},
    'ASI2400MM': {'gain': 0.1, 'read_noise': 0.8, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.91, 'width_px': 6240, 'height_px': 4160},
    'ASI2400MC': {'gain': 0.1, 'read_noise': 0.8, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.91, 'width_px': 6240, 'height_px': 4160},
    'ASI533MM': {'gain': 0.1, 'read_noise': 0.8, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.91, 'width_px': 3008, 'height_px': 3008},
    'ASI533MC': {'gain': 0.1, 'read_noise': 0.8, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.91, 'width_px': 3008, 'height_px': 3008},
    'ASI462MM': {'gain': 0.5, 'read_noise': 1.8, 'full_well': 20000, 'pixel_size': 2.9, 'quantum_efficiency': 0.84, 'width_px': 1920, 'height_px': 1080},
    'ASI462MC': {'gain': 0.5, 'read_noise': 1.8, 'full_well': 20000, 'pixel_size': 2.9, 'quantum_efficiency': 0.84, 'width_px': 1920, 'height_px': 1080},
    'ASI482MM': {'gain': 0.5, 'read_noise': 1.8, 'full_well': 20000, 'pixel_size': 2.9, 'quantum_efficiency': 0.84, 'width_px': 1920, 'height_px': 1080},
    'ASI482MC': {'gain': 0.5, 'read_noise': 1.8, 'full_well': 20000, 'pixel_size': 2.9, 'quantum_efficiency': 0.84, 'width_px': 1920, 'height_px': 1080},
    'ASI485MM': {'gain': 0.5, 'read_noise': 1.8, 'full_well': 20000, 'pixel_size': 2.9, 'quantum_efficiency': 0.84, 'width_px': 1920, 'height_px': 1080},
    'ASI485MC': {'gain': 0.5, 'read_noise': 1.8, 'full_well': 20000, 'pixel_size': 2.9, 'quantum_efficiency': 0.84, 'width_px': 1920, 'height_px': 1080},
    'ASI678MC': {'gain': 0.5, 'read_noise': 0.7, 'full_well': 16000, 'pixel_size': 2.0, 'quantum_efficiency': 0.85, 'width_px': 3840, 'height_px': 2160},
    'ASI662MC': {'gain': 0.5, 'read_noise': 0.8, 'full_well': 18000, 'pixel_size': 2.9, 'quantum_efficiency': 0.85, 'width_px': 1920, 'height_px': 1080},
    'ASI585MC': {'gain': 0.5, 'read_noise': 1.2, 'full_well': 30000, 'pixel_size': 2.9, 'quantum_efficiency': 0.9, 'width_px': 3840, 'height_px': 2160},
    
    # Additional QHY Cameras
    'QHY8L': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 5.4, 'quantum_efficiency': 0.75, 'width_px': 1536, 'height_px': 1024},
    'QHY9M': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 5.4, 'quantum_efficiency': 0.75, 'width_px': 1536, 'height_px': 1024},
    'QHY10': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 4.65, 'quantum_efficiency': 0.75, 'width_px': 1280, 'height_px': 1024},
    'QHY11': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 4.65, 'quantum_efficiency': 0.75, 'width_px': 1280, 'height_px': 1024},
    'QHY12': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 4.65, 'quantum_efficiency': 0.75, 'width_px': 1280, 'height_px': 1024},
    'QHY168M': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 3.8, 'quantum_efficiency': 0.75, 'width_px': 1920, 'height_px': 1080},
    'QHY168C': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 3.8, 'quantum_efficiency': 0.75, 'width_px': 1920, 'height_px': 1080},
    'QHY183M': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 2.4, 'quantum_efficiency': 0.75, 'width_px': 5496, 'height_px': 3672},
    'QHY183C': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 2.4, 'quantum_efficiency': 0.75, 'width_px': 5496, 'height_px': 3672},
    'QHY294M': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 4.63, 'quantum_efficiency': 0.75, 'width_px': 4144, 'height_px': 2822},
    'QHY294C': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 4.63, 'quantum_efficiency': 0.75, 'width_px': 4144, 'height_px': 2822},
    'QHY533M': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 3008, 'height_px': 3008},
    'QHY533C': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 3008, 'height_px': 3008},
    'QHY268M': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 6248, 'height_px': 4176},
    'QHY268C': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 6248, 'height_px': 4176},
    'QHY410C': {'gain': 1.0, 'read_noise': 1.1, 'full_well': 80000, 'pixel_size': 5.94, 'quantum_efficiency': 0.8, 'width_px': 6000, 'height_px': 4000},
    'QHY367C': {'gain': 1.0, 'read_noise': 1.5, 'full_well': 60000, 'pixel_size': 4.88, 'quantum_efficiency': 0.75, 'width_px': 7376, 'height_px': 4928},
    'QHY247C': {'gain': 1.0, 'read_noise': 1.8, 'full_well': 45000, 'pixel_size': 3.91, 'quantum_efficiency': 0.7, 'width_px': 6000, 'height_px': 4000},
    
    # Additional FLI Cameras
    'FLI-PL16803': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 9.0, 'quantum_efficiency': 0.85, 'width_px': 4096, 'height_px': 4096},
    'FLI-PL11002': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 9.0, 'quantum_efficiency': 0.85, 'width_px': 4008, 'height_px': 2672},
    'FLI-PL09000': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 12.0, 'quantum_efficiency': 0.85, 'width_px': 3056, 'height_px': 3056},
    'FLI-PL4710': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 4.65, 'quantum_efficiency': 0.85, 'width_px': 1024, 'height_px': 1024},
    'FLI-PL230': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 4.65, 'quantum_efficiency': 0.85, 'width_px': 1024, 'height_px': 1024},
    'FLI-ML16803': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 9.0, 'quantum_efficiency': 0.85, 'width_px': 4096, 'height_px': 4096},
    'FLI-ML11002': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 9.0, 'quantum_efficiency': 0.85, 'width_px': 4008, 'height_px': 2672},
    'FLI-ML09000': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 12.0, 'quantum_efficiency': 0.85, 'width_px': 3056, 'height_px': 3056},
    'FLI-ML4710': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 4.65, 'quantum_efficiency': 0.85, 'width_px': 1024, 'height_px': 1024},
    'FLI-ML230': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 4.65, 'quantum_efficiency': 0.85, 'width_px': 1024, 'height_px': 1024},
    
    # Additional Moravian Cameras
    'G2-8300': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 5.4, 'quantum_efficiency': 0.85, 'width_px': 3326, 'height_px': 2504},
    'G2-1600': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 4.4, 'quantum_efficiency': 0.85, 'width_px': 1536, 'height_px': 1024},
    'G2-4000': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 7.4, 'quantum_efficiency': 0.85, 'width_px': 2048, 'height_px': 2048},
    'G2-8300M': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 5.4, 'quantum_efficiency': 0.85, 'width_px': 3326, 'height_px': 2504},
    'G2-1600M': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 4.4, 'quantum_efficiency': 0.85, 'width_px': 1536, 'height_px': 1024},
    'G2-4000M': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 7.4, 'quantum_efficiency': 0.85, 'width_px': 2048, 'height_px': 2048},
    'G3-8300': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 5.4, 'quantum_efficiency': 0.85, 'width_px': 3326, 'height_px': 2504},
    'G3-1600': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 4.4, 'quantum_efficiency': 0.85, 'width_px': 1536, 'height_px': 1024},
    'G3-4000': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 7.4, 'quantum_efficiency': 0.85, 'width_px': 2048, 'height_px': 2048},
    'G3-8300M': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 5.4, 'quantum_efficiency': 0.85, 'width_px': 3326, 'height_px': 2504},
    'G3-1600M': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 4.4, 'quantum_efficiency': 0.85, 'width_px': 1536, 'height_px': 1024},
    'G3-4000M': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 7.4, 'quantum_efficiency': 0.85, 'width_px': 2048, 'height_px': 2048},
    
    # Touptek Cameras
    'Touptek IMX178': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 2.4, 'quantum_efficiency': 0.75, 'width_px': 1920, 'height_px': 1080},
    'Touptek IMX183': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 2.4, 'quantum_efficiency': 0.75, 'width_px': 5496, 'height_px': 3672},
    'Touptek IMX294': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 4.63, 'quantum_efficiency': 0.75, 'width_px': 4144, 'height_px': 2822},
    'Touptek IMX533': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 3008, 'height_px': 3008},
    'Touptek IMX571': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 6248, 'height_px': 4176},
    'Touptek IMX455': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 9576, 'height_px': 6388},
    'Touptek IMX461': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 2.9, 'quantum_efficiency': 0.75, 'width_px': 1920, 'height_px': 1080},
    'Touptek IMX485': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 2.9, 'quantum_efficiency': 0.75, 'width_px': 1920, 'height_px': 1080},
    'Touptek IMX482': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 2.9, 'quantum_efficiency': 0.75, 'width_px': 1920, 'height_px': 1080},
    # Player One (examples)
    'PLAYER ONE NEPTUNE-C II': {'gain': 1.0, 'read_noise': 0.8, 'full_well': 20000, 'pixel_size': 2.9, 'quantum_efficiency': 0.85, 'width_px': 1920, 'height_px': 1080},
    'PLAYER ONE URANUS-C': {'gain': 1.0, 'read_noise': 1.0, 'full_well': 20000, 'pixel_size': 2.9, 'quantum_efficiency': 0.85, 'width_px': 1920, 'height_px': 1080},
    'PLAYER ONE APOLLO-MINI C': {'gain': 1.0, 'read_noise': 0.9, 'full_well': 18000, 'pixel_size': 2.4, 'quantum_efficiency': 0.85, 'width_px': 5496, 'height_px': 3672},
    # SVBONY
    'SVBONY SV305': {'gain': 1.0, 'read_noise': 2.0, 'full_well': 15000, 'pixel_size': 2.9, 'quantum_efficiency': 0.7, 'width_px': 1920, 'height_px': 1080},
    'SVBONY SV405CC': {'gain': 1.0, 'read_noise': 1.2, 'full_well': 45000, 'pixel_size': 4.63, 'quantum_efficiency': 0.75, 'width_px': 4144, 'height_px': 2822},
    'SVBONY SV605CC': {'gain': 1.0, 'read_noise': 1.2, 'full_well': 50000, 'pixel_size': 3.76, 'quantum_efficiency': 0.8, 'width_px': 6248, 'height_px': 4176},
    # ATIK/FLI (color variants)
    'ATIK-ONE C': {'gain': 0.26, 'read_noise': 6.5, 'full_well': 18000, 'pixel_size': 4.54, 'quantum_efficiency': 0.5, 'width_px': 3352, 'height_px': 2532},
    'FLI-ML8300C': {'gain': 1.4, 'read_noise': 9.0, 'full_well': 100000, 'pixel_size': 5.4, 'quantum_efficiency': 0.5, 'width_px': 3326, 'height_px': 2504},
    # DSLR / Mirrorless (approximate typical values)
    'CANON 600D': {'gain': 0.9, 'read_noise': 2.7, 'full_well': 25000, 'pixel_size': 4.3, 'quantum_efficiency': 0.5, 'width_px': 5184, 'height_px': 3456},
    'CANON 750D': {'gain': 0.9, 'read_noise': 2.6, 'full_well': 24000, 'pixel_size': 3.7, 'quantum_efficiency': 0.5, 'width_px': 6000, 'height_px': 4000},
    'CANON 5D MARK III': {'gain': 0.9, 'read_noise': 2.5, 'full_well': 60000, 'pixel_size': 6.25, 'quantum_efficiency': 0.5, 'width_px': 5760, 'height_px': 3840},
    'CANON R6': {'gain': 0.9, 'read_noise': 1.5, 'full_well': 70000, 'pixel_size': 6.56, 'quantum_efficiency': 0.6, 'width_px': 5472, 'height_px': 3648},
    'NIKON D5300': {'gain': 0.9, 'read_noise': 1.8, 'full_well': 24000, 'pixel_size': 3.9, 'quantum_efficiency': 0.5, 'width_px': 6000, 'height_px': 4000},
    'NIKON D750': {'gain': 0.9, 'read_noise': 1.7, 'full_well': 60000, 'pixel_size': 5.95, 'quantum_efficiency': 0.5, 'width_px': 6016, 'height_px': 4016},
    'NIKON D850': {'gain': 0.9, 'read_noise': 2.2, 'full_well': 45000, 'pixel_size': 4.35, 'quantum_efficiency': 0.5, 'width_px': 8256, 'height_px': 5504},
    'NIKON Z6': {'gain': 0.9, 'read_noise': 1.4, 'full_well': 70000, 'pixel_size': 5.94, 'quantum_efficiency': 0.6, 'width_px': 6048, 'height_px': 4024},
    'SONY A7S': {'gain': 0.9, 'read_noise': 1.0, 'full_well': 80000, 'pixel_size': 8.4, 'quantum_efficiency': 0.65, 'width_px': 4240, 'height_px': 2832},
    'SONY A7III': {'gain': 0.9, 'read_noise': 1.2, 'full_well': 70000, 'pixel_size': 5.9, 'quantum_efficiency': 0.6, 'width_px': 6000, 'height_px': 4000},
    'SONY A7RIII': {'gain': 0.9, 'read_noise': 1.5, 'full_well': 60000, 'pixel_size': 4.5, 'quantum_efficiency': 0.55, 'width_px': 7952, 'height_px': 5304},
    'SIGMA FP': {'gain': 0.9, 'read_noise': 1.5, 'full_well': 60000, 'pixel_size': 5.97, 'quantum_efficiency': 0.5, 'width_px': 6000, 'height_px': 4000},
    # More Canon
    'CANON 1100D': {'gain': 0.9, 'read_noise': 3.0, 'full_well': 22000, 'pixel_size': 5.2, 'quantum_efficiency': 0.45, 'width_px': 4272, 'height_px': 2848},
    'CANON 700D': {'gain': 0.9, 'read_noise': 2.7, 'full_well': 24000, 'pixel_size': 4.3, 'quantum_efficiency': 0.48, 'width_px': 5184, 'height_px': 3456},
    'CANON 80D': {'gain': 0.9, 'read_noise': 2.4, 'full_well': 25000, 'pixel_size': 3.7, 'quantum_efficiency': 0.5, 'width_px': 6000, 'height_px': 4000},
    'CANON 90D': {'gain': 0.9, 'read_noise': 2.3, 'full_well': 23000, 'pixel_size': 3.2, 'quantum_efficiency': 0.5, 'width_px': 6960, 'height_px': 4640},
    'CANON 6D': {'gain': 0.9, 'read_noise': 2.1, 'full_well': 65000, 'pixel_size': 6.55, 'quantum_efficiency': 0.5, 'width_px': 5472, 'height_px': 3648},
    'CANON 6D MARK II': {'gain': 0.9, 'read_noise': 2.0, 'full_well': 65000, 'pixel_size': 5.76, 'quantum_efficiency': 0.5, 'width_px': 6240, 'height_px': 4160},
    'CANON R5': {'gain': 0.9, 'read_noise': 1.4, 'full_well': 65000, 'pixel_size': 4.4, 'quantum_efficiency': 0.6, 'width_px': 8192, 'height_px': 5464},
    'CANON R7': {'gain': 0.9, 'read_noise': 1.6, 'full_well': 26000, 'pixel_size': 3.2, 'quantum_efficiency': 0.55, 'width_px': 6960, 'height_px': 4640},
    # More Nikon
    'NIKON D3200': {'gain': 0.9, 'read_noise': 2.4, 'full_well': 22000, 'pixel_size': 3.9, 'quantum_efficiency': 0.45, 'width_px': 6016, 'height_px': 4000},
    'NIKON D5600': {'gain': 0.9, 'read_noise': 1.7, 'full_well': 24000, 'pixel_size': 3.9, 'quantum_efficiency': 0.5, 'width_px': 6000, 'height_px': 4000},
    'NIKON D610': {'gain': 0.9, 'read_noise': 1.7, 'full_well': 65000, 'pixel_size': 5.95, 'quantum_efficiency': 0.5, 'width_px': 6016, 'height_px': 4016},
    'NIKON D780': {'gain': 0.9, 'read_noise': 1.5, 'full_well': 70000, 'pixel_size': 5.94, 'quantum_efficiency': 0.55, 'width_px': 6048, 'height_px': 4024},
    'NIKON Z7': {'gain': 0.9, 'read_noise': 1.9, 'full_well': 60000, 'pixel_size': 4.35, 'quantum_efficiency': 0.55, 'width_px': 8256, 'height_px': 5504},
    'NIKON D810': {'gain': 0.9, 'read_noise': 2.2, 'full_well': 45000, 'pixel_size': 4.88, 'quantum_efficiency': 0.5, 'width_px': 7360, 'height_px': 4912},
    'NIKON D810A': {'gain': 0.9, 'read_noise': 2.1, 'full_well': 45000, 'pixel_size': 4.88, 'quantum_efficiency': 0.52, 'width_px': 7360, 'height_px': 4912},
    'NIKON Z8': {'gain': 0.9, 'read_noise': 1.8, 'full_well': 60000, 'pixel_size': 4.35, 'quantum_efficiency': 0.58, 'width_px': 8256, 'height_px': 5504},
    'NIKON Z9': {'gain': 0.9, 'read_noise': 1.8, 'full_well': 60000, 'pixel_size': 4.35, 'quantum_efficiency': 0.58, 'width_px': 8256, 'height_px': 5504},
    # More Sony
    'SONY A6000': {'gain': 0.9, 'read_noise': 1.5, 'full_well': 24000, 'pixel_size': 3.9, 'quantum_efficiency': 0.5, 'width_px': 6000, 'height_px': 4000},
    'SONY A6400': {'gain': 0.9, 'read_noise': 1.4, 'full_well': 26000, 'pixel_size': 3.9, 'quantum_efficiency': 0.55, 'width_px': 6000, 'height_px': 4000},
    'SONY A6500': {'gain': 0.9, 'read_noise': 1.3, 'full_well': 26000, 'pixel_size': 3.9, 'quantum_efficiency': 0.55, 'width_px': 6000, 'height_px': 4000},
    'SONY A7IV': {'gain': 0.9, 'read_noise': 1.3, 'full_well': 65000, 'pixel_size': 5.1, 'quantum_efficiency': 0.6, 'width_px': 7008, 'height_px': 4672},
    
    # SONY IMX Sensors (Direct sensor references)
    'IMX178': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 2.4, 'quantum_efficiency': 0.75, 'width_px': 1920, 'height_px': 1080},
    'IMX183': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 2.4, 'quantum_efficiency': 0.75, 'width_px': 5496, 'height_px': 3672},
    'IMX294': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 4.63, 'quantum_efficiency': 0.75, 'width_px': 4144, 'height_px': 2822},
    'IMX533': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 3008, 'height_px': 3008},
    'IMX571': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 6248, 'height_px': 4176},
    'IMX455': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 3.76, 'quantum_efficiency': 0.75, 'width_px': 9576, 'height_px': 6388},
    'IMX461': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 2.9, 'quantum_efficiency': 0.75, 'width_px': 1920, 'height_px': 1080},
    'IMX485': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 2.9, 'quantum_efficiency': 0.75, 'width_px': 1920, 'height_px': 1080},
    'IMX482': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 2.9, 'quantum_efficiency': 0.75, 'width_px': 1920, 'height_px': 1080},
    'IMX224': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 3.75, 'quantum_efficiency': 0.75, 'width_px': 1280, 'height_px': 960},
    'IMX290': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 2.9, 'quantum_efficiency': 0.75, 'width_px': 1920, 'height_px': 1080},
    'IMX174': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 5.86, 'quantum_efficiency': 0.75, 'width_px': 1920, 'height_px': 1200},
    'IMX462': {'gain': 1.0, 'read_noise': 3.5, 'full_well': 15000, 'pixel_size': 2.9, 'quantum_efficiency': 0.75, 'width_px': 1920, 'height_px': 1080},
    
    # Default values for unknown sensors
    'default': {'gain': 100, 'read_noise': 1.0, 'full_well': 20000, 'pixel_size': 3.8, 'quantum_efficiency': 0.6, 'width_px': 1920, 'height_px': 1080}
}

# Messier objects database with common names in English
MESSIER_DATABASE = {
    'M1': 'M 1 (Crab Nebula)',
    'M2': 'M 2 (Globular Cluster)',
    'M3': 'M 3 (Globular Cluster)',
    'M4': 'M 4 (Globular Cluster)',
    'M5': 'M 5 (Globular Cluster)',
    'M6': 'M 6 (Butterfly Cluster)',
    'M7': 'M 7 (Ptolemy Cluster)',
    'M8': 'M 8 (Lagoon Nebula)',
    'M9': 'M 9 (Globular Cluster)',
    'M10': 'M 10 (Globular Cluster)',
    'M11': 'M 11 (Wild Duck Cluster)',
    'M12': 'M 12 (Globular Cluster)',
    'M13': 'M 13 (Hercules Cluster)',
    'M14': 'M 14 (Globular Cluster)',
    'M15': 'M 15 (Globular Cluster)',
    'M16': 'M 16 (Eagle Nebula)',
    'M17': 'M 17 (Omega Nebula)',
    'M18': 'M 18 (Open Cluster)',
    'M19': 'M 19 (Globular Cluster)',
    'M20': 'M 20 (Trifid Nebula)',
    'M21': 'M 21 (Open Cluster)',
    'M22': 'M 22 (Globular Cluster)',
    'M23': 'M 23 (Open Cluster)',
    'M24': 'M 24 (Sagittarius Star Cloud)',
    'M25': 'M 25 (Open Cluster)',
    'M26': 'M 26 (Open Cluster)',
    'M27': 'M 27 (Dumbbell Nebula)',
    'M28': 'M 28 (Globular Cluster)',
    'M29': 'M 29 (Open Cluster)',
    'M30': 'M 30 (Globular Cluster)',
    'M31': 'M 31 (Andromeda Galaxy)',
    'M32': 'M 32 (Andromeda Satellite Galaxy)',
    'M33': 'M 33 (Triangulum Galaxy)',
    'M34': 'M 34 (Open Cluster)',
    'M35': 'M 35 (Open Cluster)',
    'M36': 'M 36 (Open Cluster)',
    'M37': 'M 37 (Open Cluster)',
    'M38': 'M 38 (Open Cluster)',
    'M39': 'M 39 (Open Cluster)',
    'M40': 'M 40 (Double Star)',
    'M41': 'M 41 (Open Cluster)',
    'M42': 'M 42 (Orion Nebula)',
    'M43': 'M 43 (De Mairan Nebula)',
    'M44': 'M 44 (Beehive Cluster)',
    'M45': 'M 45 (Pleiades Cluster)',
    'M46': 'M 46 (Open Cluster)',
    'M47': 'M 47 (Open Cluster)',
    'M48': 'M 48 (Open Cluster)',
    'M49': 'M 49 (Elliptical Galaxy)',
    'M50': 'M 50 (Open Cluster)',
    'M51': 'M 51 (Whirlpool Galaxy)',
    'M52': 'M 52 (Open Cluster)',
    'M53': 'M 53 (Globular Cluster)',
    'M54': 'M 54 (Globular Cluster)',
    'M55': 'M 55 (Globular Cluster)',
    'M56': 'M 56 (Globular Cluster)',
    'M57': 'M 57 (Ring Nebula)',
    'M58': 'M 58 (Spiral Galaxy)',
    'M59': 'M 59 (Elliptical Galaxy)',
    'M60': 'M 60 (Elliptical Galaxy)',
    'M61': 'M 61 (Spiral Galaxy)',
    'M62': 'M 62 (Globular Cluster)',
    'M63': 'M 63 (Sunflower Galaxy)',
    'M64': 'M 64 (Black Eye Galaxy)',
    'M65': 'M 65 (Spiral Galaxy)',
    'M66': 'M 66 (Spiral Galaxy)',
    'M67': 'M 67 (Open Cluster)',
    'M68': 'M 68 (Globular Cluster)',
    'M69': 'M 69 (Globular Cluster)',
    'M70': 'M 70 (Globular Cluster)',
    'M71': 'M 71 (Globular Cluster)',
    'M72': 'M 72 (Globular Cluster)',
    'M73': 'M 73 (Asterism)',
    'M74': 'M 74 (Spiral Galaxy)',
    'M75': 'M 75 (Globular Cluster)',
    'M76': 'M 76 (Little Dumbbell Nebula)',
    'M77': 'M 77 (Cetus Galaxy)',
    'M78': 'M 78 (Nebula)',
    'M79': 'M 79 (Globular Cluster)',
    'M80': 'M 80 (Globular Cluster)',
    'M81': 'M 81 (Bode Galaxy)',
    'M82': 'M 82 (Cigar Galaxy)',
    'M83': 'M 83 (Southern Pinwheel Galaxy)',
    'M84': 'M 84 (Elliptical Galaxy)',
    'M85': 'M 85 (Elliptical Galaxy)',
    'M86': 'M 86 (Elliptical Galaxy)',
    'M87': 'M 87 (Elliptical Galaxy)',
    'M88': 'M 88 (Spiral Galaxy)',
    'M89': 'M 89 (Elliptical Galaxy)',
    'M90': 'M 90 (Spiral Galaxy)',
    'M91': 'M 91 (Spiral Galaxy)',
    'M92': 'M 92 (Globular Cluster)',
    'M93': 'M 93 (Open Cluster)',
    'M94': 'M 94 (Spiral Galaxy)',
    'M95': 'M 95 (Spiral Galaxy)',
    'M96': 'M 96 (Spiral Galaxy)',
    'M97': 'M 97 (Owl Nebula)',
    'M98': 'M 98 (Spiral Galaxy)',
    'M99': 'M 99 (Spiral Galaxy)',
    'M100': 'M 100 (Spiral Galaxy)',
    'M101': 'M 101 (Pinwheel Galaxy)',
    'M102': 'M 102 (Spiral Galaxy)',
    'M103': 'M 103 (Open Cluster)',
    'M104': 'M 104 (Sombrero Galaxy)',
    'M105': 'M 105 (Elliptical Galaxy)',
    'M106': 'M 106 (Spiral Galaxy)',
    'M107': 'M 107 (Globular Cluster)',
    'M108': 'M 108 (Spiral Galaxy)',
    'M109': 'M 109 (Spiral Galaxy)',
    'M110': 'M 110 (Andromeda Satellite Galaxy)'
}

# Extended astronomical objects database with common names
# Clés normalisées : NGC N, IC N, Sh2-N, RCW N, LBN N, PGC N, Abell N
EXTENDED_ASTRONOMICAL_DATABASE = {
    # IC Objects
    'IC 1396': 'IC 1396 (Elephant Trunk Nebula)',
    'IC 1805': 'IC 1805 (Heart Nebula)',
    'IC 405': 'IC 405 (Flaming Star Nebula)',
    'IC 410': 'IC 410 (Tadpole Nebula)',
    'IC 434': 'IC 434 (Horsehead Nebula)',
    'IC 5070': 'IC 5070 (Pelican Nebula)',
    'IC 5146': 'IC 5146 (Cocoon Nebula)',
    'IC 1848': 'IC 1848 (Soul Nebula)',
    'IC 2118': 'IC 2118 (Witch Head Nebula)',
    'IC 443': 'IC 443 (Jellyfish Nebula)',
    'IC 1318': 'IC 1318 (Butterfly Nebula / Gamma Cygni Nebula)',
    'IC 1795': 'IC 1795 (Fish Head Nebula)',
    'IC 2169': 'IC 2169 (Nebula in Orion)',
    'IC 4628': 'IC 4628 (Prawn Nebula)',
    
    # NGC Objects (nébuleuses, galaxies)
    'NGC 1499': 'NGC 1499 (California Nebula)',
    'NGC 1514': 'NGC 1514 (Crystal Ball Nebula)',
    'NGC 2174': 'NGC 2174 (Monkey Head Nebula)',
    'NGC 281': 'NGC 281 (Pacman Nebula)',
    'NGC 1097': 'NGC 1097 (Barred Spiral Galaxy)',
    'NGC 1300': 'NGC 1300 (Barred Spiral Galaxy)',
    'NGC 1365': 'NGC 1365 (Barred Spiral Galaxy)',
    'NGC 2024': 'NGC 2024 (Flame Nebula)',
    'NGC 2392': 'NGC 2392 (Eskimo Nebula)',
    'NGC 3132': 'NGC 3132 (Eight-Burst Nebula)',
    'NGC 3242': 'NGC 3242 (Ghost of Jupiter)',
    'NGC 3628': 'NGC 3628 (Hamburger Galaxy)',
    'NGC 4038': 'NGC 4038 (Antennae Galaxies)',
    'NGC 4039': 'NGC 4039 (Antennae Galaxies)',
    'NGC 4214': 'NGC 4214 (IrrII Galaxy)',
    'NGC 4559': 'NGC 4559 (Spiral Galaxy)',
    'NGC 4565': 'NGC 4565 (Needle Galaxy)',
    'NGC 4631': 'NGC 4631 (Whale Galaxy)',
    'NGC 4697': 'NGC 4697 (Elliptical Galaxy)',
    'NGC 4736': 'NGC 4736 (Messier 94)',
    'NGC 5033': 'NGC 5033 (Spiral Galaxy)',
    'NGC 5128': 'NGC 5128 (Centaurus A)',
    'NGC 5194': 'NGC 5194 (Whirlpool Galaxy / M51)',
    'NGC 5195': 'NGC 5195 (M51 Companion)',
    'NGC 5457': 'NGC 5457 (Pinwheel Galaxy / M101)',
    'NGC 5474': 'NGC 5474 (Dwarf Galaxy)',
    'NGC 6357': 'NGC 6357 (War and Peace Nebula)',
    'NGC 6523': 'NGC 6523 (Lagoon Nebula)',
    'NGC 6543': 'NGC 6543 (Cat\'s Eye Nebula)',
    'NGC 6611': 'NGC 6611 (Eagle Nebula / M16)',
    'NGC 6720': 'NGC 6720 (Ring Nebula / M57)',
    'NGC 6820': 'NGC 6820 (Emission Nebula)',
    'NGC 6826': 'NGC 6826 (Blinking Planetary)',
    'NGC 6888': 'NGC 6888 (Crescent Nebula)',
    'NGC 6914': 'NGC 6914 (Reflection Nebula)',
    'NGC 6946': 'NGC 6946 (Fireworks Galaxy)',
    'NGC 6960': 'NGC 6960 (Western Veil Nebula)',
    'NGC 6979': 'NGC 6979 (Pickering\'s Triangle)',
    'NGC 6992': 'NGC 6992 (Eastern Veil Nebula)',
    'NGC 6995': 'NGC 6995 (Network Nebula)',
    'NGC 7000': 'NGC 7000 (North America Nebula)',
    'NGC 7023': 'NGC 7023 (Iris Nebula)',
    'NGC 7293': 'NGC 7293 (Helix Nebula)',
    'NGC 7331': 'NGC 7331 (Deer Lick Galaxy)',
    'NGC 7380': 'NGC 7380 (Wizard Nebula)',
    'NGC 7538': 'NGC 7538 (Star-Forming Region)',
    'NGC 7635': 'NGC 7635 (Bubble Nebula)',
    'NGC 7822': 'NGC 7822 (Emission Nebula)',
    'NGC 891': 'NGC 891 (Silver Sliver Galaxy)',
    
    # Sharpless (Sh2) Objects
    'Sh2-101': 'Sh2-101 (Tulip Nebula)',
    'Sh2-105': 'Sh2-105 (Pelican Nebula region)',
    'Sh2-106': 'Sh2-106 (Sharpless 106)',
    'Sh2-108': 'Sh2-108 (Sadr Region)',
    'Sh2-112': 'Sh2-112 (Emission Nebula)',
    'Sh2-115': 'Sh2-115 (Butterfly Nebula region)',
    'Sh2-125': 'Sh2-125 (Soul Nebula region)',
    'Sh2-129': 'Sh2-129 (Bat Nebula)',
    'Sh2-132': 'Sh2-132 (Lion Nebula)',
    'Sh2-140': 'Sh2-140 (Star-Forming Region)',
    'Sh2-142': 'Sh2-142 (Wizard Nebula region)',
    'Sh2-155': 'Sh2-155 (Cave Nebula)',
    'Sh2-171': 'Sh2-171 (NGC 7822 region)',
    'Sh2-199': 'Sh2-199 (Soul Nebula)',
    'Sh2-235': 'Sh2-235 (Star-Forming Region)',
    'Sh2-240': 'Sh2-240 (Simeis 147)',
    'Sh2-261': 'Sh2-261 (Lower\'s Nebula)',
    'Sh2-276': 'Sh2-276 (Barnard\'s Loop)',
    
    # RCW (Rodgers-Campbell-Whiteoak) - nébuleuses australe
    'RCW 38': 'RCW 38 (Star-Forming Region)',
    'RCW 49': 'RCW 49 (Gum 29)',
    'RCW 57': 'RCW 57 (Gum 35)',
    'RCW 79': 'RCW 79 (Bubble Nebula)',
    'RCW 86': 'RCW 86 (Supernova Remnant)',
    'RCW 104': 'RCW 104 (Stingray Nebula region)',
    'RCW 108': 'RCW 108 (Ara OB1)',
    'RCW 117': 'RCW 117 (Emission Nebula)',
    'RCW 120': 'RCW 120 (Space Blob)',
    'RCW 127': 'RCW 127 (Star-Forming Region)',
    
    # LBN (Lynds Bright Nebula)
    'LBN 437': 'LBN 437 (California Nebula region)',
    'LBN 537': 'LBN 537 (Emission Nebula)',
    'LBN 552': 'LBN 552 (Heart Nebula region)',
    'LBN 675': 'LBN 675 (North America region)',
    'LBN 999': 'LBN 999 (Emission Nebula)',
    
    # PGC (Principal Galaxy Catalog) - objets célèbres
    'PGC 50779': 'PGC 50779 (Sombrero Galaxy / M104)',
    'PGC 48282': 'PGC 48282 (M86)',
    'PGC 45349': 'PGC 45349 (M87)',
    
    # Abell (amas de galaxies / nébuleuses planétaires)
    'Abell 39': 'Abell 39 (Planetary Nebula)',
    'Abell 33': 'Abell 33 (Planetary Nebula)',
    'Abell 21': 'Abell 21 (Medusa Nebula)',
    'Abell 31': 'Abell 31 (Planetary Nebula)',
    'Abell 1656': 'Abell 1656 (Coma Cluster)',
    'Abell 2199': 'Abell 2199 (Galaxy Cluster)',
    'Abell 262': 'Abell 262 (Galaxy Cluster)',
}

# Arp catalog database with common names for peculiar galaxies (Atlas of Peculiar Galaxies, 338 entries)
ARP_DATABASE = {
    # Spiral galaxies with companions
    'Arp 16': 'Arp 16 (M66 / NGC 3627)',
    'Arp 26': 'Arp 26 (M101 Pinwheel Galaxy)',
    'Arp 29': 'Arp 29 (NGC 6946 Fireworks Galaxy)',
    'Arp 37': 'Arp 37 (M77 / NGC 1068)',
    'Arp 59': 'Arp 59 (NGC 341 / Leo Triplet)',
    'Arp 76': 'Arp 76 (M90 / NGC 4569)',
    'Arp 77': 'Arp 77 (NGC 1097)',
    'Arp 78': 'Arp 78 (NGC 772)',
    'Arp 81': 'Arp 81 (NGC 6621/6622)',
    'Arp 82': 'Arp 82 (NGC 2535/2536)',
    'Arp 84': 'Arp 84 (NGC 5394/5395)',
    'Arp 85': 'Arp 85 (M51 Whirlpool Galaxy)',
    'Arp 86': 'Arp 86 (The Mice / NGC 7752/7753)',
    'Arp 87': 'Arp 87 (NGC 3808)',
    'Arp 90': 'Arp 90 (NGC 5929/5930)',
    'Arp 91': 'Arp 91 (NGC 5953/5954)',
    'Arp 94': 'Arp 94 (NGC 3226/3227)',
    # Elliptical / perturbed
    'Arp 104': 'Arp 104 (NGC 5216/5218)',
    'Arp 105': 'Arp 105 (NGC 3561)',
    'Arp 116': 'Arp 116 (M60 / NGC 4647)',
    'Arp 118': 'Arp 118 (NGC 1143/1144)',
    'Arp 120': 'Arp 120 (NGC 4435/4438 The Eyes)',
    'Arp 134': 'Arp 134 (M49 / NGC 4472)',
    'Arp 135': 'Arp 135 (NGC 1023)',
    'Arp 140': 'Arp 140 (NGC 274/275)',
    'Arp 142': 'Arp 142 (NGC 2936/2937)',
    'Arp 152': 'Arp 152 (M87)',
    'Arp 168': 'Arp 168 (M32)',
    # Galaxies with rings
    'Arp 146': 'Arp 146 (PGC 509/510)',
    'Arp 147': 'Arp 147 (Ring Galaxy / IC 298)',
    'Arp 148': 'Arp 148 (Mayall\'s Object)',
    # Disturbed / jets
    'Arp 149': 'Arp 149 (IC 803)',
    'Arp 153': 'Arp 153 (Centaurus A / NGC 5128)',
    'Arp 154': 'Arp 154 (Fornax A / NGC 1316)',
    'Arp 155': 'Arp 155 (NGC 3656)',
    'Arp 157': 'Arp 157 (NGC 520)',
    'Arp 158': 'Arp 158 (NGC 523)',
    'Arp 160': 'Arp 160 (NGC 4194)',
    # Amorphous / filaments
    'Arp 186': 'Arp 186 (NGC 1614)',
    'Arp 189': 'Arp 189 (NGC 4651)',
    'Arp 192': 'Arp 192 (NGC 3303)',
    'Arp 193': 'Arp 193 (IC 883)',
    'Arp 199': 'Arp 199 (NGC 5544/5545)',
    'Arp 205': 'Arp 205 (NGC 3448)',
    'Arp 206': 'Arp 206 (NGC 3432)',
    'Arp 209': 'Arp 209 (NGC 6052)',
    'Arp 210': 'Arp 210 (NGC 1569)',
    'Arp 214': 'Arp 214 (NGC 3718)',
    'Arp 215': 'Arp 215 (NGC 2782)',
    'Arp 217': 'Arp 217 (NGC 3310)',
    'Arp 220': 'Arp 220 (IC 1127)',
    'Arp 222': 'Arp 222 (NGC 7727)',
    'Arp 224': 'Arp 224 (NGC 3921)',
    'Arp 225': 'Arp 225 (NGC 2655)',
    'Arp 226': 'Arp 226 (NGC 7252 Atoms for Peace)',
    # Concentric rings
    'Arp 227': 'Arp 227 (NGC 474)',
    'Arp 228': 'Arp 228 (IC 162)',
    'Arp 229': 'Arp 229 (NGC 507)',
    # Mergers / fission
    'Arp 234': 'Arp 234 (NGC 3738)',
    'Arp 236': 'Arp 236 (IC 1623)',
    'Arp 239': 'Arp 239 (NGC 5278/5279)',
    'Arp 240': 'Arp 240 (NGC 5257/5258)',
    'Arp 242': 'Arp 242 (NGC 4676 The Mice)',
    'Arp 243': 'Arp 243 (NGC 2623)',
    'Arp 244': 'Arp 244 (Antennae Galaxies / NGC 4038/4039)',
    'Arp 245': 'Arp 245 (NGC 2992/2993)',
    'Arp 259': 'Arp 259 (NGC 1741)',
    'Arp 263': 'Arp 263 (NGC 3239)',
    'Arp 264': 'Arp 264 (NGC 3104)',
    'Arp 266': 'Arp 266 (NGC 4861)',
    # Double / interacting
    'Arp 269': 'Arp 269 (NGC 4490/4485)',
    'Arp 270': 'Arp 270 (NGC 3395/3396)',
    'Arp 271': 'Arp 271 (NGC 5426/5427)',
    'Arp 272': 'Arp 272 (NGC 6050)',
    'Arp 273': 'Arp 273 (Rose Galaxy)',
    'Arp 274': 'Arp 274 (NGC 5679)',
    'Arp 276': 'Arp 276 (NGC 935/IC 1801)',
    'Arp 278': 'Arp 278 (NGC 7253)',
    'Arp 281': 'Arp 281 (Whale Galaxy / NGC 4631/4627)',
    'Arp 283': 'Arp 283 (NGC 2798/2799)',
    'Arp 286': 'Arp 286 (NGC 5560/5566/5569)',
    'Arp 287': 'Arp 287 (NGC 2735)',
    'Arp 290': 'Arp 290 (IC 195/196)',
    'Arp 292': 'Arp 292 (IC 575)',
    'Arp 293': 'Arp 293 (NGC 6285/6286)',
    'Arp 299': 'Arp 299 (NGC 3690/IC 694)',
    'Arp 303': 'Arp 303 (IC 563/564)',
    'Arp 304': 'Arp 304 (NGC 1241/1242)',
    'Arp 305': 'Arp 305 (NGC 4016/4017)',
    'Arp 307': 'Arp 307 (NGC 2872/2874)',
    # Tadpole and long filaments
    'Arp 188': 'Arp 188 (Tadpole Galaxy)',
    # Miscellaneous
    'Arp 337': 'Arp 337 (Cigar Galaxy)',
}

# Telescope database with their characteristics
TELESCOPES_DATABASE = {
    'default': {
        'diameter_mm': 200.0,
        'focal_length_mm': 1600.0,
        'f_number': 8.0
    },
    'FSQ-85EDP': {
        'diameter_mm': 85.0,
        'focal_length_mm': 455.0,
        'f_number': 5.35
    },
    'FSQ85EDP': {
        'diameter_mm': 85.0,
        'focal_length_mm': 455.0,
        'f_number': 5.35
    },
    'FSQ-85': {
        'diameter_mm': 85.0,
        'focal_length_mm': 455.0,
        'f_number': 5.35
    },
    'FSQ85': {
        'diameter_mm': 85.0,
        'focal_length_mm': 455.0,
        'f_number': 5.35
    },
    
    # Takahashi Telescopes
    'FSQ-106': {'diameter_mm': 106.0, 'focal_length_mm': 530.0, 'f_number': 5.0},
    'FSQ106': {'diameter_mm': 106.0, 'focal_length_mm': 530.0, 'f_number': 5.0},
    'FSQ-130': {'diameter_mm': 130.0, 'focal_length_mm': 650.0, 'f_number': 5.0},
    'FSQ130': {'diameter_mm': 130.0, 'focal_length_mm': 650.0, 'f_number': 5.0},
    'TOA-130': {'diameter_mm': 130.0, 'focal_length_mm': 1000.0, 'f_number': 7.7},
    'TOA-150': {'diameter_mm': 150.0, 'focal_length_mm': 1100.0, 'f_number': 7.3},
    'TOA-160': {'diameter_mm': 160.0, 'focal_length_mm': 1200.0, 'f_number': 7.5},
    'TSA-102': {'diameter_mm': 102.0, 'focal_length_mm': 816.0, 'f_number': 8.0},
    'TSA-120': {'diameter_mm': 120.0, 'focal_length_mm': 900.0, 'f_number': 7.5},
    'Epsilon-130': {'diameter_mm': 130.0, 'focal_length_mm': 430.0, 'f_number': 3.3},
    'Epsilon-160': {'diameter_mm': 160.0, 'focal_length_mm': 530.0, 'f_number': 3.3},
    'Epsilon-180': {'diameter_mm': 180.0, 'focal_length_mm': 600.0, 'f_number': 3.3},
    # Takahashi FC-76 series (fluorite doublet 76 mm, 570 mm f/7.5)
    'FC76-DCU': {'diameter_mm': 76.0, 'focal_length_mm': 570.0, 'f_number': 7.5},
    'FC-76DCU': {'diameter_mm': 76.0, 'focal_length_mm': 570.0, 'f_number': 7.5},
    'FC76DCU': {'diameter_mm': 76.0, 'focal_length_mm': 570.0, 'f_number': 7.5},
    'FC-76': {'diameter_mm': 76.0, 'focal_length_mm': 570.0, 'f_number': 7.5},
    'FC76': {'diameter_mm': 76.0, 'focal_length_mm': 570.0, 'f_number': 7.5},
    
    # Celestron Telescopes
    'C8': {'diameter_mm': 203.2, 'focal_length_mm': 2032.0, 'f_number': 10.0},
    'C9': {'diameter_mm': 235.0, 'focal_length_mm': 2350.0, 'f_number': 10.0},
    'C9.25': {'diameter_mm': 235.0, 'focal_length_mm': 2350.0, 'f_number': 10.0},
    'C11': {'diameter_mm': 279.4, 'focal_length_mm': 2794.0, 'f_number': 10.0},
    'C14': {'diameter_mm': 355.6, 'focal_length_mm': 3911.6, 'f_number': 11.0},
    'EDGEHD8': {'diameter_mm': 203.2, 'focal_length_mm': 2032.0, 'f_number': 10.0},
    'EDGEHD9.25': {'diameter_mm': 235.0, 'focal_length_mm': 2350.0, 'f_number': 10.0},
    'EDGEHD11': {'diameter_mm': 279.4, 'focal_length_mm': 2794.0, 'f_number': 10.0},
    'EDGEHD14': {'diameter_mm': 355.6, 'focal_length_mm': 3911.6, 'f_number': 11.0},
    'RASA8': {'diameter_mm': 203.2, 'focal_length_mm': 400.0, 'f_number': 2.0},
    'RASA11': {'diameter_mm': 279.4, 'focal_length_mm': 620.0, 'f_number': 2.2},
    'RASA14': {'diameter_mm': 355.6, 'focal_length_mm': 650.0, 'f_number': 1.8},
    'STARIZON': {'diameter_mm': 130.0, 'focal_length_mm': 650.0, 'f_number': 5.0},
    'STARIZON-130': {'diameter_mm': 130.0, 'focal_length_mm': 650.0, 'f_number': 5.0},
    'STARIZON-150': {'diameter_mm': 150.0, 'focal_length_mm': 750.0, 'f_number': 5.0},
    'STARIZON-180': {'diameter_mm': 180.0, 'focal_length_mm': 900.0, 'f_number': 5.0},
    
    # PlaneWave Telescopes
    'CDK12': {'diameter_mm': 304.8, 'focal_length_mm': 2438.4, 'f_number': 8.0},
    'CDK14': {'diameter_mm': 355.6, 'focal_length_mm': 2844.8, 'f_number': 8.0},
    'CDK16': {'diameter_mm': 406.4, 'focal_length_mm': 3251.2, 'f_number': 8.0},
    'CDK17': {'diameter_mm': 431.8, 'focal_length_mm': 3454.4, 'f_number': 8.0},
    'CDK20': {'diameter_mm': 508.0, 'focal_length_mm': 4064.0, 'f_number': 8.0},
    'CDK24': {'diameter_mm': 609.6, 'focal_length_mm': 4876.8, 'f_number': 8.0},
    'L-350': {'diameter_mm': 350.0, 'focal_length_mm': 2450.0, 'f_number': 7.0},
    'L-500': {'diameter_mm': 500.0, 'focal_length_mm': 3500.0, 'f_number': 7.0},
    'L-600': {'diameter_mm': 600.0, 'focal_length_mm': 4200.0, 'f_number': 7.0},
    
    # CFF Telescopes (Classical Cassegrain)
    'CFF160': {'diameter_mm': 160.0, 'focal_length_mm': 1280.0, 'f_number': 8.0},
    'CFF185': {'diameter_mm': 185.0, 'focal_length_mm': 1480.0, 'f_number': 8.0},
    'CFF200': {'diameter_mm': 200.0, 'focal_length_mm': 1600.0, 'f_number': 8.0},
    'CFF250': {'diameter_mm': 250.0, 'focal_length_mm': 2000.0, 'f_number': 8.0},
    'CFF300': {'diameter_mm': 300.0, 'focal_length_mm': 2400.0, 'f_number': 8.0},
    'CFF350': {'diameter_mm': 350.0, 'focal_length_mm': 2800.0, 'f_number': 8.0},
    'CFF400': {'diameter_mm': 400.0, 'focal_length_mm': 3200.0, 'f_number': 8.0},
    'CFF500': {'diameter_mm': 500.0, 'focal_length_mm': 4000.0, 'f_number': 8.0},
    
    # TS-Optics Telescopes
    'TS-APO65Q': {'diameter_mm': 65.0, 'focal_length_mm': 420.0, 'f_number': 6.5},
    'TS-APO80Q': {'diameter_mm': 80.0, 'focal_length_mm': 480.0, 'f_number': 6.0},
    'TS-APO102Q': {'diameter_mm': 102.0, 'focal_length_mm': 714.0, 'f_number': 7.0},
    'TS-APO115Q': {'diameter_mm': 115.0, 'focal_length_mm': 805.0, 'f_number': 7.0},
    'TS-APO130Q': {'diameter_mm': 130.0, 'focal_length_mm': 910.0, 'f_number': 7.0},
    'TS-APO140Q': {'diameter_mm': 140.0, 'focal_length_mm': 980.0, 'f_number': 7.0},
    'TS-APO150Q': {'diameter_mm': 150.0, 'focal_length_mm': 1050.0, 'f_number': 7.0},
    'TS-APO160Q': {'diameter_mm': 160.0, 'focal_length_mm': 1120.0, 'f_number': 7.0},
    'TS-APO180Q': {'diameter_mm': 180.0, 'focal_length_mm': 1260.0, 'f_number': 7.0},
    'TS-APO200Q': {'diameter_mm': 200.0, 'focal_length_mm': 1400.0, 'f_number': 7.0},
    'TS-APO250Q': {'diameter_mm': 250.0, 'focal_length_mm': 1750.0, 'f_number': 7.0},
    'TS-APO300Q': {'diameter_mm': 300.0, 'focal_length_mm': 2100.0, 'f_number': 7.0},
    'TS-APO350Q': {'diameter_mm': 350.0, 'focal_length_mm': 2450.0, 'f_number': 7.0},
    'TS-APO400Q': {'diameter_mm': 400.0, 'focal_length_mm': 2800.0, 'f_number': 7.0},
    'TS-APO500Q': {'diameter_mm': 500.0, 'focal_length_mm': 3500.0, 'f_number': 7.0},
    'TS-APO600Q': {'diameter_mm': 600.0, 'focal_length_mm': 4200.0, 'f_number': 7.0},
    'TS-APO700Q': {'diameter_mm': 700.0, 'focal_length_mm': 4900.0, 'f_number': 7.0},
    'TS-APO800Q': {'diameter_mm': 800.0, 'focal_length_mm': 5600.0, 'f_number': 7.0},
    'TS-APO900Q': {'diameter_mm': 900.0, 'focal_length_mm': 6300.0, 'f_number': 7.0},
    'TS-APO1000Q': {'diameter_mm': 1000.0, 'focal_length_mm': 7000.0, 'f_number': 7.0},
    
    # Askar Telescopes
    'ASKAR-50PHQ': {'diameter_mm': 50.0, 'focal_length_mm': 250.0, 'f_number': 5.0},
    'ASKAR-60PHQ': {'diameter_mm': 60.0, 'focal_length_mm': 300.0, 'f_number': 5.0},
    'ASKAR-70PHQ': {'diameter_mm': 70.0, 'focal_length_mm': 350.0, 'f_number': 5.0},
    'ASKAR-80PHQ': {'diameter_mm': 80.0, 'focal_length_mm': 400.0, 'f_number': 5.0},
    'ASKAR-90PHQ': {'diameter_mm': 90.0, 'focal_length_mm': 450.0, 'f_number': 5.0},
    'ASKAR-100PHQ': {'diameter_mm': 100.0, 'focal_length_mm': 500.0, 'f_number': 5.0},
    'ASKAR-120PHQ': {'diameter_mm': 120.0, 'focal_length_mm': 600.0, 'f_number': 5.0},
    'ASKAR-130PHQ': {'diameter_mm': 130.0, 'focal_length_mm': 650.0, 'f_number': 5.0},
    'ASKAR-150PHQ': {'diameter_mm': 150.0, 'focal_length_mm': 750.0, 'f_number': 5.0},
    'ASKAR-180PHQ': {'diameter_mm': 180.0, 'focal_length_mm': 900.0, 'f_number': 5.0},
    'ASKAR-200PHQ': {'diameter_mm': 200.0, 'focal_length_mm': 1000.0, 'f_number': 5.0},
    'ASKAR-250PHQ': {'diameter_mm': 250.0, 'focal_length_mm': 1250.0, 'f_number': 5.0},
    'ASKAR-300PHQ': {'diameter_mm': 300.0, 'focal_length_mm': 1500.0, 'f_number': 5.0},
    'ASKAR-350PHQ': {'diameter_mm': 350.0, 'focal_length_mm': 1750.0, 'f_number': 5.0},
    'ASKAR-400PHQ': {'diameter_mm': 400.0, 'focal_length_mm': 2000.0, 'f_number': 5.0},
    'ASKAR-500PHQ': {'diameter_mm': 500.0, 'focal_length_mm': 2500.0, 'f_number': 5.0},
    'ASKAR-600PHQ': {'diameter_mm': 600.0, 'focal_length_mm': 3000.0, 'f_number': 5.0},
    'ASKAR-700PHQ': {'diameter_mm': 700.0, 'focal_length_mm': 3500.0, 'f_number': 5.0},
    
    # William Optics Telescopes
    'REDCAT51': {'diameter_mm': 51.0, 'focal_length_mm': 250.0, 'f_number': 4.9},
    'REDCAT 51': {'diameter_mm': 51.0, 'focal_length_mm': 250.0, 'f_number': 4.9},
    'RADIAN 61': {'diameter_mm': 61.0, 'focal_length_mm': 275.0, 'f_number': 4.5},
    'RADIAN61': {'diameter_mm': 61.0, 'focal_length_mm': 275.0, 'f_number': 4.5},
    'GT81': {'diameter_mm': 81.0, 'focal_length_mm': 478.0, 'f_number': 5.9},
    'GT102': {'diameter_mm': 102.0, 'focal_length_mm': 714.0, 'f_number': 7.0},
    'GT103': {'diameter_mm': 103.0, 'focal_length_mm': 618.0, 'f_number': 6.0},
    'GT105': {'diameter_mm': 105.0, 'focal_length_mm': 735.0, 'f_number': 7.0},
    'GT110': {'diameter_mm': 110.0, 'focal_length_mm': 770.0, 'f_number': 7.0},
    'GT120': {'diameter_mm': 120.0, 'focal_length_mm': 840.0, 'f_number': 7.0},
    'GT130': {'diameter_mm': 130.0, 'focal_length_mm': 910.0, 'f_number': 7.0},
    'GT150': {'diameter_mm': 150.0, 'focal_length_mm': 1050.0, 'f_number': 7.0},
    'GT180': {'diameter_mm': 180.0, 'focal_length_mm': 1260.0, 'f_number': 7.0},
    'GT200': {'diameter_mm': 200.0, 'focal_length_mm': 1400.0, 'f_number': 7.0},
    'GT250': {'diameter_mm': 250.0, 'focal_length_mm': 1750.0, 'f_number': 7.0},
    'GT300': {'diameter_mm': 300.0, 'focal_length_mm': 2100.0, 'f_number': 7.0},
    'GT350': {'diameter_mm': 350.0, 'focal_length_mm': 2450.0, 'f_number': 7.0},
    'GT400': {'diameter_mm': 400.0, 'focal_length_mm': 2800.0, 'f_number': 7.0},
    'GT500': {'diameter_mm': 500.0, 'focal_length_mm': 3500.0, 'f_number': 7.0},
    'GT600': {'diameter_mm': 600.0, 'focal_length_mm': 4200.0, 'f_number': 7.0},
    'GT700': {'diameter_mm': 700.0, 'focal_length_mm': 4900.0, 'f_number': 7.0},
    'GT800': {'diameter_mm': 800.0, 'focal_length_mm': 5600.0, 'f_number': 7.0},
    'GT900': {'diameter_mm': 900.0, 'focal_length_mm': 6300.0, 'f_number': 7.0},
    'GT1000': {'diameter_mm': 1000.0, 'focal_length_mm': 7000.0, 'f_number': 7.0},
    
    # Explore Scientific Telescopes
    'ES80': {'diameter_mm': 80.0, 'focal_length_mm': 480.0, 'f_number': 6.0},
    'ES102': {'diameter_mm': 102.0, 'focal_length_mm': 714.0, 'f_number': 7.0},
    'ES127': {'diameter_mm': 127.0, 'focal_length_mm': 952.0, 'f_number': 7.5},
    'ES152': {'diameter_mm': 152.0, 'focal_length_mm': 1209.0, 'f_number': 8.0},
    'ES203': {'diameter_mm': 203.0, 'focal_length_mm': 1624.0, 'f_number': 8.0},
    'ES254': {'diameter_mm': 254.0, 'focal_length_mm': 2032.0, 'f_number': 8.0},
    'ES305': {'diameter_mm': 305.0, 'focal_length_mm': 2438.0, 'f_number': 8.0},
    'ES356': {'diameter_mm': 356.0, 'focal_length_mm': 2848.0, 'f_number': 8.0},
    'ES406': {'diameter_mm': 406.0, 'focal_length_mm': 3248.0, 'f_number': 8.0},
    'ES457': {'diameter_mm': 457.0, 'focal_length_mm': 3656.0, 'f_number': 8.0},
    'ES508': {'diameter_mm': 508.0, 'focal_length_mm': 4064.0, 'f_number': 8.0},
    'ES610': {'diameter_mm': 610.0, 'focal_length_mm': 4880.0, 'f_number': 8.0},
    'ES711': {'diameter_mm': 711.0, 'focal_length_mm': 5688.0, 'f_number': 8.0},
    'ES813': {'diameter_mm': 813.0, 'focal_length_mm': 6504.0, 'f_number': 8.0},
    'ES914': {'diameter_mm': 914.0, 'focal_length_mm': 7312.0, 'f_number': 8.0},
    'ES1016': {'diameter_mm': 1016.0, 'focal_length_mm': 8128.0, 'f_number': 8.0},
    'ES1118': {'diameter_mm': 1118.0, 'focal_length_mm': 8944.0, 'f_number': 8.0},
    'ES1219': {'diameter_mm': 1219.0, 'focal_length_mm': 9752.0, 'f_number': 8.0},
    'ES1321': {'diameter_mm': 1321.0, 'focal_length_mm': 10568.0, 'f_number': 8.0},
    'ES1422': {'diameter_mm': 1422.0, 'focal_length_mm': 11376.0, 'f_number': 8.0},
    'ES1524': {'diameter_mm': 1524.0, 'focal_length_mm': 12192.0, 'f_number': 8.0},
    'ES1625': {'diameter_mm': 1625.0, 'focal_length_mm': 13000.0, 'f_number': 8.0},
    'ES1727': {'diameter_mm': 1727.0, 'focal_length_mm': 13816.0, 'f_number': 8.0},
    'ES1828': {'diameter_mm': 1828.0, 'focal_length_mm': 14624.0, 'f_number': 8.0},
    'ES1930': {'diameter_mm': 1930.0, 'focal_length_mm': 15440.0, 'f_number': 8.0},
    'ES2032': {'diameter_mm': 2032.0, 'focal_length_mm': 16256.0, 'f_number': 8.0},
    
    # Sky-Watcher Telescopes
    'EQ80': {'diameter_mm': 80.0, 'focal_length_mm': 400.0, 'f_number': 5.0},
    'EQ100': {'diameter_mm': 100.0, 'focal_length_mm': 500.0, 'f_number': 5.0},
    'EQ120': {'diameter_mm': 120.0, 'focal_length_mm': 600.0, 'f_number': 5.0},
    'EQ150': {'diameter_mm': 150.0, 'focal_length_mm': 750.0, 'f_number': 5.0},
    'EQ200': {'diameter_mm': 200.0, 'focal_length_mm': 1000.0, 'f_number': 5.0},
    'EQ250': {'diameter_mm': 250.0, 'focal_length_mm': 1250.0, 'f_number': 5.0},
    'EQ300': {'diameter_mm': 300.0, 'focal_length_mm': 1500.0, 'f_number': 5.0},
    'EQ350': {'diameter_mm': 350.0, 'focal_length_mm': 1750.0, 'f_number': 5.0},
    'EQ400': {'diameter_mm': 400.0, 'focal_length_mm': 2000.0, 'f_number': 5.0},
    'EQ500': {'diameter_mm': 500.0, 'focal_length_mm': 2500.0, 'f_number': 5.0},
    'EQ600': {'diameter_mm': 600.0, 'focal_length_mm': 3000.0, 'f_number': 5.0},
    'EQ700': {'diameter_mm': 700.0, 'focal_length_mm': 3500.0, 'f_number': 5.0},
    'EQ800': {'diameter_mm': 800.0, 'focal_length_mm': 4000.0, 'f_number': 5.0},
    'EQ900': {'diameter_mm': 900.0, 'focal_length_mm': 4500.0, 'f_number': 5.0},
    'EQ1000': {'diameter_mm': 1000.0, 'focal_length_mm': 5000.0, 'f_number': 5.0},
    
    # Sky-Watcher Esprit Series
    'ESPRIT80': {'diameter_mm': 80.0, 'focal_length_mm': 400.0, 'f_number': 5.0},
    'ESPRIT100': {'diameter_mm': 100.0, 'focal_length_mm': 550.0, 'f_number': 5.5},
    'ESPRIT120': {'diameter_mm': 120.0, 'focal_length_mm': 840.0, 'f_number': 7.0},
    'ESPRIT150': {'diameter_mm': 150.0, 'focal_length_mm': 1050.0, 'f_number': 7.0},
    'ESPRIT200': {'diameter_mm': 200.0, 'focal_length_mm': 1400.0, 'f_number': 7.0},
    'ESPRIT250': {'diameter_mm': 250.0, 'focal_length_mm': 1750.0, 'f_number': 7.0},
    'ESPRIT300': {'diameter_mm': 300.0, 'focal_length_mm': 2100.0, 'f_number': 7.0},
    'ESPRIT350': {'diameter_mm': 350.0, 'focal_length_mm': 2450.0, 'f_number': 7.0},
    'ESPRIT400': {'diameter_mm': 400.0, 'focal_length_mm': 2800.0, 'f_number': 7.0},
    'ESPRIT500': {'diameter_mm': 500.0, 'focal_length_mm': 3500.0, 'f_number': 7.0},
    'ESPRIT600': {'diameter_mm': 600.0, 'focal_length_mm': 4200.0, 'f_number': 7.0},
    'ESPRIT700': {'diameter_mm': 700.0, 'focal_length_mm': 4900.0, 'f_number': 7.0},
    'ESPRIT800': {'diameter_mm': 800.0, 'focal_length_mm': 5600.0, 'f_number': 7.0},
    'ESPRIT900': {'diameter_mm': 900.0, 'focal_length_mm': 6300.0, 'f_number': 7.0},
    'ESPRIT1000': {'diameter_mm': 1000.0, 'focal_length_mm': 7000.0, 'f_number': 7.0},
    
    # Sky-Watcher Quattro Series
    'QUATTRO80': {'diameter_mm': 80.0, 'focal_length_mm': 400.0, 'f_number': 5.0},
    'QUATTRO100': {'diameter_mm': 100.0, 'focal_length_mm': 500.0, 'f_number': 5.0},
    'QUATTRO120': {'diameter_mm': 120.0, 'focal_length_mm': 600.0, 'f_number': 5.0},
    'QUATTRO150': {'diameter_mm': 150.0, 'focal_length_mm': 750.0, 'f_number': 5.0},
    'QUATTRO200': {'diameter_mm': 200.0, 'focal_length_mm': 1000.0, 'f_number': 5.0},
    'QUATTRO250': {'diameter_mm': 250.0, 'focal_length_mm': 1250.0, 'f_number': 5.0},
    'QUATTRO300': {'diameter_mm': 300.0, 'focal_length_mm': 1500.0, 'f_number': 5.0},
    'QUATTRO350': {'diameter_mm': 350.0, 'focal_length_mm': 1750.0, 'f_number': 5.0},
    'QUATTRO400': {'diameter_mm': 400.0, 'focal_length_mm': 2000.0, 'f_number': 5.0},
    'QUATTRO500': {'diameter_mm': 500.0, 'focal_length_mm': 2500.0, 'f_number': 5.0},
    'QUATTRO600': {'diameter_mm': 600.0, 'focal_length_mm': 3000.0, 'f_number': 5.0},
    'QUATTRO700': {'diameter_mm': 700.0, 'focal_length_mm': 3500.0, 'f_number': 5.0},
    'QUATTRO800': {'diameter_mm': 800.0, 'focal_length_mm': 4000.0, 'f_number': 5.0},
    'QUATTRO900': {'diameter_mm': 900.0, 'focal_length_mm': 4500.0, 'f_number': 5.0},
    'QUATTRO1000': {'diameter_mm': 1000.0, 'focal_length_mm': 5000.0, 'f_number': 5.0},
    
    # Sky-Watcher Newton Series
    'NEWTON80': {'diameter_mm': 80.0, 'focal_length_mm': 400.0, 'f_number': 5.0},
    'NEWTON100': {'diameter_mm': 100.0, 'focal_length_mm': 500.0, 'f_number': 5.0},
    'NEWTON120': {'diameter_mm': 120.0, 'focal_length_mm': 600.0, 'f_number': 5.0},
    'NEWTON150': {'diameter_mm': 150.0, 'focal_length_mm': 750.0, 'f_number': 5.0},
    'NEWTON200': {'diameter_mm': 200.0, 'focal_length_mm': 1000.0, 'f_number': 5.0},
    'NEWTON250': {'diameter_mm': 250.0, 'focal_length_mm': 1250.0, 'f_number': 5.0},
    'NEWTON300': {'diameter_mm': 300.0, 'focal_length_mm': 1500.0, 'f_number': 5.0},
    'NEWTON350': {'diameter_mm': 350.0, 'focal_length_mm': 1750.0, 'f_number': 5.0},
    'NEWTON400': {'diameter_mm': 400.0, 'focal_length_mm': 2000.0, 'f_number': 5.0},
    'NEWTON500': {'diameter_mm': 500.0, 'focal_length_mm': 2500.0, 'f_number': 5.0},
    'NEWTON600': {'diameter_mm': 600.0, 'focal_length_mm': 3000.0, 'f_number': 5.0},
    'NEWTON700': {'diameter_mm': 700.0, 'focal_length_mm': 3500.0, 'f_number': 5.0},
    'NEWTON800': {'diameter_mm': 800.0, 'focal_length_mm': 4000.0, 'f_number': 5.0},
    'NEWTON900': {'diameter_mm': 900.0, 'focal_length_mm': 4500.0, 'f_number': 5.0},
    'NEWTON1000': {'diameter_mm': 1000.0, 'focal_length_mm': 5000.0, 'f_number': 5.0},
    
    # ZWO Telescopes
    'ZWO80': {'diameter_mm': 80.0, 'focal_length_mm': 400.0, 'f_number': 5.0},
    'ZWO100': {'diameter_mm': 100.0, 'focal_length_mm': 500.0, 'f_number': 5.0},
    'ZWO120': {'diameter_mm': 120.0, 'focal_length_mm': 600.0, 'f_number': 5.0},
    'ZWO150': {'diameter_mm': 150.0, 'focal_length_mm': 750.0, 'f_number': 5.0},
    'ZWO200': {'diameter_mm': 200.0, 'focal_length_mm': 1000.0, 'f_number': 5.0},
    'ZWO250': {'diameter_mm': 250.0, 'focal_length_mm': 1250.0, 'f_number': 5.0},
    'ZWO300': {'diameter_mm': 300.0, 'focal_length_mm': 1500.0, 'f_number': 5.0},
    'ZWO350': {'diameter_mm': 350.0, 'focal_length_mm': 1750.0, 'f_number': 5.0},
    'ZWO400': {'diameter_mm': 400.0, 'focal_length_mm': 2000.0, 'f_number': 5.0},
    'ZWO500': {'diameter_mm': 500.0, 'focal_length_mm': 2500.0, 'f_number': 5.0},
    'ZWO600': {'diameter_mm': 600.0, 'focal_length_mm': 3000.0, 'f_number': 5.0},
    'ZWO700': {'diameter_mm': 700.0, 'focal_length_mm': 3500.0, 'f_number': 5.0},
    'ZWO800': {'diameter_mm': 800.0, 'focal_length_mm': 4000.0, 'f_number': 5.0},
    'ZWO900': {'diameter_mm': 900.0, 'focal_length_mm': 4500.0, 'f_number': 5.0},
    'ZWO1000': {'diameter_mm': 1000.0, 'focal_length_mm': 5000.0, 'f_number': 5.0},
    
    # ZWO APO Series
    'ZWO-APO80': {'diameter_mm': 80.0, 'focal_length_mm': 480.0, 'f_number': 6.0},
    'ZWO-APO100': {'diameter_mm': 100.0, 'focal_length_mm': 600.0, 'f_number': 6.0},
    'ZWO-APO120': {'diameter_mm': 120.0, 'focal_length_mm': 720.0, 'f_number': 6.0},
    'ZWO-APO150': {'diameter_mm': 150.0, 'focal_length_mm': 900.0, 'f_number': 6.0},
    'ZWO-APO200': {'diameter_mm': 200.0, 'focal_length_mm': 1200.0, 'f_number': 6.0},
    'ZWO-APO250': {'diameter_mm': 250.0, 'focal_length_mm': 1500.0, 'f_number': 6.0},
    'ZWO-APO300': {'diameter_mm': 300.0, 'focal_length_mm': 1800.0, 'f_number': 6.0},
    'ZWO-APO350': {'diameter_mm': 350.0, 'focal_length_mm': 2100.0, 'f_number': 6.0},
    'ZWO-APO400': {'diameter_mm': 400.0, 'focal_length_mm': 2400.0, 'f_number': 6.0},
    'ZWO-APO500': {'diameter_mm': 500.0, 'focal_length_mm': 3000.0, 'f_number': 6.0},
    'ZWO-APO600': {'diameter_mm': 600.0, 'focal_length_mm': 3600.0, 'f_number': 6.0},
    'ZWO-APO700': {'diameter_mm': 700.0, 'focal_length_mm': 4200.0, 'f_number': 6.0},
    'ZWO-APO800': {'diameter_mm': 800.0, 'focal_length_mm': 4800.0, 'f_number': 6.0},
    'ZWO-APO900': {'diameter_mm': 900.0, 'focal_length_mm': 5400.0, 'f_number': 6.0},
    'ZWO-APO1000': {'diameter_mm': 1000.0, 'focal_length_mm': 6000.0, 'f_number': 6.0},
    
    # ASA Telescopes (Astro Systeme Austria)
    'ASA-80': {'diameter_mm': 80.0, 'focal_length_mm': 480.0, 'f_number': 6.0},
    'ASA-100': {'diameter_mm': 100.0, 'focal_length_mm': 600.0, 'f_number': 6.0},
    'ASA-120': {'diameter_mm': 120.0, 'focal_length_mm': 720.0, 'f_number': 6.0},
    'ASA-150': {'diameter_mm': 150.0, 'focal_length_mm': 900.0, 'f_number': 6.0},
    'ASA-200': {'diameter_mm': 200.0, 'focal_length_mm': 1200.0, 'f_number': 6.0},
    'ASA-250': {'diameter_mm': 250.0, 'focal_length_mm': 1500.0, 'f_number': 6.0},
    'ASA-300': {'diameter_mm': 300.0, 'focal_length_mm': 1800.0, 'f_number': 6.0},
    'ASA-350': {'diameter_mm': 350.0, 'focal_length_mm': 2100.0, 'f_number': 6.0},
    'ASA-400': {'diameter_mm': 400.0, 'focal_length_mm': 2400.0, 'f_number': 6.0},
    'ASA-500': {'diameter_mm': 500.0, 'focal_length_mm': 3000.0, 'f_number': 6.0},
    'ASA-600': {'diameter_mm': 600.0, 'focal_length_mm': 3600.0, 'f_number': 6.0},
    'ASA-700': {'diameter_mm': 700.0, 'focal_length_mm': 4200.0, 'f_number': 6.0},
    'ASA-800': {'diameter_mm': 800.0, 'focal_length_mm': 4800.0, 'f_number': 6.0},
    'ASA-900': {'diameter_mm': 900.0, 'focal_length_mm': 5400.0, 'f_number': 6.0},
    'ASA-1000': {'diameter_mm': 1000.0, 'focal_length_mm': 6000.0, 'f_number': 6.0},
    
    # ASA Newton Series
    'ASA-NEWTON80': {'diameter_mm': 80.0, 'focal_length_mm': 400.0, 'f_number': 5.0},
    'ASA-NEWTON100': {'diameter_mm': 100.0, 'focal_length_mm': 500.0, 'f_number': 5.0},
    'ASA-NEWTON120': {'diameter_mm': 120.0, 'focal_length_mm': 600.0, 'f_number': 5.0},
    'ASA-NEWTON150': {'diameter_mm': 150.0, 'focal_length_mm': 750.0, 'f_number': 5.0},
    'ASA-NEWTON200': {'diameter_mm': 200.0, 'focal_length_mm': 1000.0, 'f_number': 5.0},
    'ASA-NEWTON250': {'diameter_mm': 250.0, 'focal_length_mm': 1250.0, 'f_number': 5.0},
    'ASA-NEWTON300': {'diameter_mm': 300.0, 'focal_length_mm': 1500.0, 'f_number': 5.0},
    'ASA-NEWTON350': {'diameter_mm': 350.0, 'focal_length_mm': 1750.0, 'f_number': 5.0},
    'ASA-NEWTON400': {'diameter_mm': 400.0, 'focal_length_mm': 2000.0, 'f_number': 5.0},
    'ASA-NEWTON500': {'diameter_mm': 500.0, 'focal_length_mm': 2500.0, 'f_number': 5.0},
    'ASA-NEWTON600': {'diameter_mm': 600.0, 'focal_length_mm': 3000.0, 'f_number': 5.0},
    'ASA-NEWTON700': {'diameter_mm': 700.0, 'focal_length_mm': 3500.0, 'f_number': 5.0},
    'ASA-NEWTON800': {'diameter_mm': 800.0, 'focal_length_mm': 4000.0, 'f_number': 5.0},
    'ASA-NEWTON900': {'diameter_mm': 900.0, 'focal_length_mm': 4500.0, 'f_number': 5.0},
    'ASA-NEWTON1000': {'diameter_mm': 1000.0, 'focal_length_mm': 5000.0, 'f_number': 5.0},
    
    # ASA APO Series
    'ASA-APO80': {'diameter_mm': 80.0, 'focal_length_mm': 480.0, 'f_number': 6.0},
    'ASA-APO100': {'diameter_mm': 100.0, 'focal_length_mm': 600.0, 'f_number': 6.0},
    'ASA-APO120': {'diameter_mm': 120.0, 'focal_length_mm': 720.0, 'f_number': 6.0},
    'ASA-APO150': {'diameter_mm': 150.0, 'focal_length_mm': 900.0, 'f_number': 6.0},
    'ASA-APO200': {'diameter_mm': 200.0, 'focal_length_mm': 1200.0, 'f_number': 6.0},
    'ASA-APO250': {'diameter_mm': 250.0, 'focal_length_mm': 1500.0, 'f_number': 6.0},
    'ASA-APO300': {'diameter_mm': 300.0, 'focal_length_mm': 1800.0, 'f_number': 6.0},
    'ASA-APO350': {'diameter_mm': 350.0, 'focal_length_mm': 2100.0, 'f_number': 6.0},
    'ASA-APO400': {'diameter_mm': 400.0, 'focal_length_mm': 2400.0, 'f_number': 6.0},
    'ASA-APO500': {'diameter_mm': 500.0, 'focal_length_mm': 3000.0, 'f_number': 6.0},
    'ASA-APO600': {'diameter_mm': 600.0, 'focal_length_mm': 3600.0, 'f_number': 6.0},
    'ASA-APO700': {'diameter_mm': 700.0, 'focal_length_mm': 4200.0, 'f_number': 6.0},
    'ASA-APO800': {'diameter_mm': 800.0, 'focal_length_mm': 4800.0, 'f_number': 6.0},
    'ASA-APO900': {'diameter_mm': 900.0, 'focal_length_mm': 5400.0, 'f_number': 6.0},
    'ASA-APO1000': {'diameter_mm': 1000.0, 'focal_length_mm': 6000.0, 'f_number': 6.0},
    
    # Ritchey-Chrétien Series (generic and TS-Optics)
    'RC10': {'diameter_mm': 254.0, 'focal_length_mm': 2032.0, 'f_number': 8.0},
    'RC 10': {'diameter_mm': 254.0, 'focal_length_mm': 2032.0, 'f_number': 8.0},
    'TS RC10': {'diameter_mm': 254.0, 'focal_length_mm': 2032.0, 'f_number': 8.0},
    'TS-RC10': {'diameter_mm': 254.0, 'focal_length_mm': 2032.0, 'f_number': 8.0},
    'TS RC 10': {'diameter_mm': 254.0, 'focal_length_mm': 2032.0, 'f_number': 8.0},
    'TS-RC 10': {'diameter_mm': 254.0, 'focal_length_mm': 2032.0, 'f_number': 8.0},
    
    # ASA Ritchey-Chrétien Series
    'ASA-RC80': {'diameter_mm': 80.0, 'focal_length_mm': 640.0, 'f_number': 8.0},
    'ASA-RC100': {'diameter_mm': 100.0, 'focal_length_mm': 800.0, 'f_number': 8.0},
    'ASA-RC120': {'diameter_mm': 120.0, 'focal_length_mm': 960.0, 'f_number': 8.0},
    'ASA-RC150': {'diameter_mm': 150.0, 'focal_length_mm': 1200.0, 'f_number': 8.0},
    'ASA-RC200': {'diameter_mm': 200.0, 'focal_length_mm': 1600.0, 'f_number': 8.0},
    'ASA-RC250': {'diameter_mm': 250.0, 'focal_length_mm': 2000.0, 'f_number': 8.0},
    'ASA-RC300': {'diameter_mm': 300.0, 'focal_length_mm': 2400.0, 'f_number': 8.0},
    'ASA-RC350': {'diameter_mm': 350.0, 'focal_length_mm': 2800.0, 'f_number': 8.0},
    'ASA-RC400': {'diameter_mm': 400.0, 'focal_length_mm': 3200.0, 'f_number': 8.0},
    'ASA-RC500': {'diameter_mm': 500.0, 'focal_length_mm': 4000.0, 'f_number': 8.0},
    'ASA-RC600': {'diameter_mm': 600.0, 'focal_length_mm': 4800.0, 'f_number': 8.0},
    'ASA-RC700': {'diameter_mm': 700.0, 'focal_length_mm': 5600.0, 'f_number': 8.0},
    'ASA-RC800': {'diameter_mm': 800.0, 'focal_length_mm': 6400.0, 'f_number': 8.0},
    'ASA-RC900': {'diameter_mm': 900.0, 'focal_length_mm': 7200.0, 'f_number': 8.0},
    'ASA-RC1000': {'diameter_mm': 1000.0, 'focal_length_mm': 8000.0, 'f_number': 8.0},
    
    # ASA Cassegrain Series
    'ASA-CASSEGRAIN80': {'diameter_mm': 80.0, 'focal_length_mm': 640.0, 'f_number': 8.0},
    'ASA-CASSEGRAIN100': {'diameter_mm': 100.0, 'focal_length_mm': 800.0, 'f_number': 8.0},
    'ASA-CASSEGRAIN120': {'diameter_mm': 120.0, 'focal_length_mm': 960.0, 'f_number': 8.0},
    'ASA-CASSEGRAIN150': {'diameter_mm': 150.0, 'focal_length_mm': 1200.0, 'f_number': 8.0},
    'ASA-CASSEGRAIN200': {'diameter_mm': 200.0, 'focal_length_mm': 1600.0, 'f_number': 8.0},
    'ASA-CASSEGRAIN250': {'diameter_mm': 250.0, 'focal_length_mm': 2000.0, 'f_number': 8.0},
    'ASA-CASSEGRAIN300': {'diameter_mm': 300.0, 'focal_length_mm': 2400.0, 'f_number': 8.0},
    'ASA-CASSEGRAIN350': {'diameter_mm': 350.0, 'focal_length_mm': 2800.0, 'f_number': 8.0},
    'ASA-CASSEGRAIN400': {'diameter_mm': 400.0, 'focal_length_mm': 3200.0, 'f_number': 8.0},
    'ASA-CASSEGRAIN500': {'diameter_mm': 500.0, 'focal_length_mm': 4000.0, 'f_number': 8.0},
    'ASA-CASSEGRAIN600': {'diameter_mm': 600.0, 'focal_length_mm': 4800.0, 'f_number': 8.0},
    'ASA-CASSEGRAIN700': {'diameter_mm': 700.0, 'focal_length_mm': 5600.0, 'f_number': 8.0},
    'ASA-CASSEGRAIN800': {'diameter_mm': 800.0, 'focal_length_mm': 6400.0, 'f_number': 8.0},
    'ASA-CASSEGRAIN900': {'diameter_mm': 900.0, 'focal_length_mm': 7200.0, 'f_number': 8.0},
    'ASA-CASSEGRAIN1000': {'diameter_mm': 1000.0, 'focal_length_mm': 8000.0, 'f_number': 8.0},
    
    # Omegon Telescopes
    'OMEGON-80': {'diameter_mm': 80.0, 'focal_length_mm': 400.0, 'f_number': 5.0},
    'OMEGON-100': {'diameter_mm': 100.0, 'focal_length_mm': 500.0, 'f_number': 5.0},
    'OMEGON-120': {'diameter_mm': 120.0, 'focal_length_mm': 600.0, 'f_number': 5.0},
    'OMEGON-150': {'diameter_mm': 150.0, 'focal_length_mm': 750.0, 'f_number': 5.0},
    'OMEGON-200': {'diameter_mm': 200.0, 'focal_length_mm': 1000.0, 'f_number': 5.0},
    'OMEGON-250': {'diameter_mm': 250.0, 'focal_length_mm': 1250.0, 'f_number': 5.0},
    'OMEGON-300': {'diameter_mm': 300.0, 'focal_length_mm': 1500.0, 'f_number': 5.0},
    'OMEGON-350': {'diameter_mm': 350.0, 'focal_length_mm': 1750.0, 'f_number': 5.0},
    'OMEGON-400': {'diameter_mm': 400.0, 'focal_length_mm': 2000.0, 'f_number': 5.0},
    'OMEGON-500': {'diameter_mm': 500.0, 'focal_length_mm': 2500.0, 'f_number': 5.0},
    'OMEGON-600': {'diameter_mm': 600.0, 'focal_length_mm': 3000.0, 'f_number': 5.0},
    'OMEGON-700': {'diameter_mm': 700.0, 'focal_length_mm': 3500.0, 'f_number': 5.0},
    'OMEGON-800': {'diameter_mm': 800.0, 'focal_length_mm': 4000.0, 'f_number': 5.0},
    'OMEGON-900': {'diameter_mm': 900.0, 'focal_length_mm': 4500.0, 'f_number': 5.0},
    'OMEGON-1000': {'diameter_mm': 1000.0, 'focal_length_mm': 5000.0, 'f_number': 5.0},
    
    # Omegon APO Series
    'OMEGON-APO80': {'diameter_mm': 80.0, 'focal_length_mm': 480.0, 'f_number': 6.0},
    'OMEGON-APO100': {'diameter_mm': 100.0, 'focal_length_mm': 600.0, 'f_number': 6.0},
    'OMEGON-APO120': {'diameter_mm': 120.0, 'focal_length_mm': 720.0, 'f_number': 6.0},
    'OMEGON-APO150': {'diameter_mm': 150.0, 'focal_length_mm': 900.0, 'f_number': 6.0},
    'OMEGON-APO200': {'diameter_mm': 200.0, 'focal_length_mm': 1200.0, 'f_number': 6.0},
    'OMEGON-APO250': {'diameter_mm': 250.0, 'focal_length_mm': 1500.0, 'f_number': 6.0},
    'OMEGON-APO300': {'diameter_mm': 300.0, 'focal_length_mm': 1800.0, 'f_number': 6.0},
    'OMEGON-APO350': {'diameter_mm': 350.0, 'focal_length_mm': 2100.0, 'f_number': 6.0},
    'OMEGON-APO400': {'diameter_mm': 400.0, 'focal_length_mm': 2400.0, 'f_number': 6.0},
    'OMEGON-APO500': {'diameter_mm': 500.0, 'focal_length_mm': 3000.0, 'f_number': 6.0},
    'OMEGON-APO600': {'diameter_mm': 600.0, 'focal_length_mm': 3600.0, 'f_number': 6.0},
    'OMEGON-APO700': {'diameter_mm': 700.0, 'focal_length_mm': 4200.0, 'f_number': 6.0},
    'OMEGON-APO800': {'diameter_mm': 800.0, 'focal_length_mm': 4800.0, 'f_number': 6.0},
    'OMEGON-APO900': {'diameter_mm': 900.0, 'focal_length_mm': 5400.0, 'f_number': 6.0},
    'OMEGON-APO1000': {'diameter_mm': 1000.0, 'focal_length_mm': 6000.0, 'f_number': 6.0},
    
    # Omegon Newton Series
    'OMEGON-NEWTON80': {'diameter_mm': 80.0, 'focal_length_mm': 400.0, 'f_number': 5.0},
    'OMEGON-NEWTON100': {'diameter_mm': 100.0, 'focal_length_mm': 500.0, 'f_number': 5.0},
    'OMEGON-NEWTON120': {'diameter_mm': 120.0, 'focal_length_mm': 600.0, 'f_number': 5.0},
    'OMEGON-NEWTON150': {'diameter_mm': 150.0, 'focal_length_mm': 750.0, 'f_number': 5.0},
    'OMEGON-NEWTON200': {'diameter_mm': 200.0, 'focal_length_mm': 1000.0, 'f_number': 5.0},
    'OMEGON-NEWTON250': {'diameter_mm': 250.0, 'focal_length_mm': 1250.0, 'f_number': 5.0},
    'OMEGON-NEWTON300': {'diameter_mm': 300.0, 'focal_length_mm': 1500.0, 'f_number': 5.0},
    'OMEGON-NEWTON350': {'diameter_mm': 350.0, 'focal_length_mm': 1750.0, 'f_number': 5.0},
    'OMEGON-NEWTON400': {'diameter_mm': 400.0, 'focal_length_mm': 2000.0, 'f_number': 5.0},
    'OMEGON-NEWTON500': {'diameter_mm': 500.0, 'focal_length_mm': 2500.0, 'f_number': 5.0},
    'OMEGON-NEWTON600': {'diameter_mm': 600.0, 'focal_length_mm': 3000.0, 'f_number': 5.0},
    'OMEGON-NEWTON700': {'diameter_mm': 700.0, 'focal_length_mm': 3500.0, 'f_number': 5.0},
    'OMEGON-NEWTON800': {'diameter_mm': 800.0, 'focal_length_mm': 4000.0, 'f_number': 5.0},
    'OMEGON-NEWTON900': {'diameter_mm': 900.0, 'focal_length_mm': 4500.0, 'f_number': 5.0},
    'OMEGON-NEWTON1000': {'diameter_mm': 1000.0, 'focal_length_mm': 5000.0, 'f_number': 5.0},
    
    # Omegon Ritchey-Chrétien Series
    'OMEGON-RC80': {'diameter_mm': 80.0, 'focal_length_mm': 640.0, 'f_number': 8.0},
    'OMEGON-RC100': {'diameter_mm': 100.0, 'focal_length_mm': 800.0, 'f_number': 8.0},
    'OMEGON-RC120': {'diameter_mm': 120.0, 'focal_length_mm': 960.0, 'f_number': 8.0},
    'OMEGON-RC150': {'diameter_mm': 150.0, 'focal_length_mm': 1200.0, 'f_number': 8.0},
    'OMEGON-RC200': {'diameter_mm': 200.0, 'focal_length_mm': 1600.0, 'f_number': 8.0},
    'OMEGON-RC250': {'diameter_mm': 250.0, 'focal_length_mm': 2000.0, 'f_number': 8.0},
    'OMEGON-RC300': {'diameter_mm': 300.0, 'focal_length_mm': 2400.0, 'f_number': 8.0},
    'OMEGON-RC350': {'diameter_mm': 350.0, 'focal_length_mm': 2800.0, 'f_number': 8.0},
    'OMEGON-RC400': {'diameter_mm': 400.0, 'focal_length_mm': 3200.0, 'f_number': 8.0},
    'OMEGON-RC500': {'diameter_mm': 500.0, 'focal_length_mm': 4000.0, 'f_number': 8.0},
    'OMEGON-RC600': {'diameter_mm': 600.0, 'focal_length_mm': 4800.0, 'f_number': 8.0},
    'OMEGON-RC700': {'diameter_mm': 700.0, 'focal_length_mm': 5600.0, 'f_number': 8.0},
    'OMEGON-RC800': {'diameter_mm': 800.0, 'focal_length_mm': 6400.0, 'f_number': 8.0},
    'OMEGON-RC900': {'diameter_mm': 900.0, 'focal_length_mm': 7200.0, 'f_number': 8.0},
    'OMEGON-RC1000': {'diameter_mm': 1000.0, 'focal_length_mm': 8000.0, 'f_number': 8.0},
    
    # Omegon Cassegrain Series
    'OMEGON-CASSEGRAIN80': {'diameter_mm': 80.0, 'focal_length_mm': 640.0, 'f_number': 8.0},
    'OMEGON-CASSEGRAIN100': {'diameter_mm': 100.0, 'focal_length_mm': 800.0, 'f_number': 8.0},
    'OMEGON-CASSEGRAIN120': {'diameter_mm': 120.0, 'focal_length_mm': 960.0, 'f_number': 8.0},
    'OMEGON-CASSEGRAIN150': {'diameter_mm': 150.0, 'focal_length_mm': 1200.0, 'f_number': 8.0},
    'OMEGON-CASSEGRAIN200': {'diameter_mm': 200.0, 'focal_length_mm': 1600.0, 'f_number': 8.0},
    'OMEGON-CASSEGRAIN250': {'diameter_mm': 250.0, 'focal_length_mm': 2000.0, 'f_number': 8.0},
    'OMEGON-CASSEGRAIN300': {'diameter_mm': 300.0, 'focal_length_mm': 2400.0, 'f_number': 8.0},
    'OMEGON-CASSEGRAIN350': {'diameter_mm': 350.0, 'focal_length_mm': 2800.0, 'f_number': 8.0},
    'OMEGON-CASSEGRAIN400': {'diameter_mm': 400.0, 'focal_length_mm': 3200.0, 'f_number': 8.0},
    'OMEGON-CASSEGRAIN500': {'diameter_mm': 500.0, 'focal_length_mm': 4000.0, 'f_number': 8.0},
    'OMEGON-CASSEGRAIN600': {'diameter_mm': 600.0, 'focal_length_mm': 4800.0, 'f_number': 8.0},
    'OMEGON-CASSEGRAIN700': {'diameter_mm': 700.0, 'focal_length_mm': 5600.0, 'f_number': 8.0},
    'OMEGON-CASSEGRAIN800': {'diameter_mm': 800.0, 'focal_length_mm': 6400.0, 'f_number': 8.0},
    'OMEGON-CASSEGRAIN900': {'diameter_mm': 900.0, 'focal_length_mm': 7200.0, 'f_number': 8.0},
    'OMEGON-CASSEGRAIN1000': {'diameter_mm': 1000.0, 'focal_length_mm': 8000.0, 'f_number': 8.0},
    
    # Telescope Live Telescopes (from https://app.telescope.live/en/telescopes)
    # Chile Telescopes
    'CHI-1': {'diameter_mm': 610.0, 'focal_length_mm': 3965.0, 'f_number': 6.5},
    'CHI-1-CMOS': {'diameter_mm': 610.0, 'focal_length_mm': 3965.0, 'f_number': 6.5},
    'CHI-1-CCD': {'diameter_mm': 610.0, 'focal_length_mm': 3965.0, 'f_number': 6.5},
    'CHI-2-CCD': {'diameter_mm': 500.0, 'focal_length_mm': 1900.0, 'f_number': 3.8},
    'CHI-3-CCD': {'diameter_mm': 1000.0, 'focal_length_mm': 6800.0, 'f_number': 6.8},
    'CHI-4-CCD': {'diameter_mm': 500.0, 'focal_length_mm': 1900.0, 'f_number': 3.8},
    'CHI-5-CCD': {'diameter_mm': 100.0, 'focal_length_mm': 200.0, 'f_number': 2.0},
    'CHI-6-CCD': {'diameter_mm': 200.0, 'focal_length_mm': 600.0, 'f_number': 3.0},
    
    # Spain Telescopes
    'SPA-1': {'diameter_mm': 106.0, 'focal_length_mm': 381.6, 'f_number': 3.6},
    'SPA-1-CCD': {'diameter_mm': 106.0, 'focal_length_mm': 381.6, 'f_number': 3.6},
    'SPA-1-CMOS': {'diameter_mm': 106.0, 'focal_length_mm': 381.6, 'f_number': 3.6},
    'SPA-2': {'diameter_mm': 710.0, 'focal_length_mm': 5680.0, 'f_number': 8.0},
    'SPA-2-CCD': {'diameter_mm': 710.0, 'focal_length_mm': 5680.0, 'f_number': 8.0},
    'SPA-2-CMOS': {'diameter_mm': 710.0, 'focal_length_mm': 5680.0, 'f_number': 8.0},
    'SPA-3': {'diameter_mm': 106.0, 'focal_length_mm': 382.0, 'f_number': 3.6},
    'SPA-3-CCD': {'diameter_mm': 106.0, 'focal_length_mm': 382.0, 'f_number': 3.6},
    'SPA-3-CMOS': {'diameter_mm': 106.0, 'focal_length_mm': 382.0, 'f_number': 3.6},
    
    # Australia Telescopes
    'AUS-2': {'diameter_mm': 106.0, 'focal_length_mm': 381.6, 'f_number': 3.6},
    'AUS-2-CCD': {'diameter_mm': 106.0, 'focal_length_mm': 381.6, 'f_number': 3.6},
    'AUS-2-CMOS': {'diameter_mm': 106.0, 'focal_length_mm': 381.6, 'f_number': 3.6}
}

# Mapping: header value (uppercase) -> canonical TELESCOPES_DATABASE key (exact match for recognition)
TELESCOPE_HEADER_MAPPING = {
    # Takahashi
    'TAKAHASHI FC76-DCU': 'FC76-DCU', 'TAKAHASHI FC-76DCU': 'FC76-DCU', 'TAKAHASHI FC-76 DCU': 'FC76-DCU',
    'FC76-DCU': 'FC76-DCU', 'FC-76DCU': 'FC76-DCU', 'FC76DCU': 'FC76-DCU', 'FC-76': 'FC76-DCU', 'FC76': 'FC76-DCU',
    'TAKAHASHI FSQ-85EDP': 'FSQ-85EDP', 'TAKAHASHI FSQ85EDP': 'FSQ85EDP', 'FSQ-85EDP': 'FSQ-85EDP', 'FSQ85EDP': 'FSQ85EDP',
    'TAKAHASHI FSQ-106': 'FSQ-106', 'TAKAHASHI FSQ106': 'FSQ106', 'TAKAHASHI FSQ-130': 'FSQ-130', 'TAKAHASHI FSQ130': 'FSQ130',
    'TAKAHASHI TOA-130': 'TOA-130', 'TAKAHASHI TOA-150': 'TOA-150', 'TAKAHASHI TOA-160': 'TOA-160',
    'TAKAHASHI TSA-102': 'TSA-102', 'TAKAHASHI TSA-120': 'TSA-120',
    'TAKAHASHI EPSILON-130': 'Epsilon-130', 'TAKAHASHI EPSILON-160': 'Epsilon-160', 'TAKAHASHI EPSILON-180': 'Epsilon-180',
    # Celestron
    'CELESTRON C8': 'C8', 'CELESTRON C9': 'C9', 'CELESTRON C9.25': 'C9.25', 'CELESTRON C11': 'C11', 'CELESTRON C14': 'C14',
    'CELESTRON EDGE HD 8': 'EDGEHD8', 'CELESTRON EDGEHD 8': 'EDGEHD8', 'CELESTRON EDGE HD 9.25': 'EDGEHD9.25',
    'CELESTRON EDGE HD 11': 'EDGEHD11', 'CELESTRON EDGE HD 14': 'EDGEHD14',
    'CELESTRON RASA 8': 'RASA8', 'CELESTRON RASA 11': 'RASA11', 'CELESTRON RASA 14': 'RASA14',
    'CELESTRON STARIZON 130': 'STARIZON-130', 'CELESTRON STARIZON-130': 'STARIZON-130',
    # Explore Scientific
    'EXPLORE SCIENTIFIC 80': 'ES80', 'EXPLORE SCIENTIFIC 102': 'ES102', 'EXPLORE SCIENTIFIC 127': 'ES127',
    'EXPLORE SCIENTIFIC 152': 'ES152', 'EXPLORE SCIENTIFIC 203': 'ES203',
    'ES 80': 'ES80', 'ES 102': 'ES102', 'ES 127': 'ES127',
    # William Optics
    'WILLIAM OPTICS REDCAT 51': 'REDCAT 51', 'REDCAT 51': 'REDCAT 51', 'REDCAT51': 'REDCAT 51',
    'RADIAN 61': 'RADIAN 61', 'RADIAN61': 'RADIAN 61', 'RADIAN RT-RAD61APO': 'RADIAN 61',
    'WILLIAM OPTICS GT81': 'GT81', 'WILLIAM OPTICS GT102': 'GT102', 'WO GT81': 'GT81', 'WO GT102': 'GT102',
    'WILLIAM OPTICS GT103': 'GT103', 'WILLIAM OPTICS GT150': 'GT150', 'WILLIAM OPTICS GT130': 'GT130',
    # Sky-Watcher
    'SKY-WATCHER ESPRIT 80': 'ESPRIT80', 'SKY-WATCHER ESPRIT 100': 'ESPRIT100', 'SKY-WATCHER ESPRIT 120': 'ESPRIT120',
    'SKY-WATCHER ESPRIT 150': 'ESPRIT150', 'SKY-WATCHER ESPRIT 200': 'ESPRIT200',
    'SKY-WATCHER QUATTRO 200': 'QUATTRO200', 'SKY-WATCHER QUATTRO 250': 'QUATTRO250',
    # Askar
    'ASKAR 80PHQ': 'ASKAR-80PHQ', 'ASKAR 100PHQ': 'ASKAR-100PHQ', 'ASKAR 50PHQ': 'ASKAR-50PHQ',
    'ASKAR 60PHQ': 'ASKAR-60PHQ', 'ASKAR 120PHQ': 'ASKAR-120PHQ', 'ASKAR 130PHQ': 'ASKAR-130PHQ',
    # TS-Optics
    'TS APO80Q': 'TS-APO80Q', 'TS APO102Q': 'TS-APO102Q', 'TS APO130Q': 'TS-APO130Q',
    'TS-APO80Q': 'TS-APO80Q', 'TS-APO102Q': 'TS-APO102Q', 'TS-APO130Q': 'TS-APO130Q',
    'TS OPTICS APO80Q': 'TS-APO80Q', 'TS OPTICS APO102Q': 'TS-APO102Q',
    'TS RC 10': 'RC10', 'TS RC10': 'RC10', 'TS-RC10': 'TS-RC10', 'TS-RC 10': 'TS-RC10',
    # PlaneWave
    'PLANEWAVE CDK12': 'CDK12', 'PLANEWAVE CDK14': 'CDK14', 'PLANEWAVE CDK16': 'CDK16',
    'PLANEWAVE CDK17': 'CDK17', 'PLANEWAVE CDK20': 'CDK20', 'PLANEWAVE CDK24': 'CDK24',
    # CFF
    'CFF 160': 'CFF160', 'CFF 185': 'CFF185', 'CFF 200': 'CFF200', 'CFF 250': 'CFF250',
    'CFF 300': 'CFF300', 'CFF 350': 'CFF350', 'CFF 400': 'CFF400',
    # ASA
    'ASA 80': 'ASA-80', 'ASA 100': 'ASA-100', 'ASA 120': 'ASA-120', 'ASA 150': 'ASA-150',
    'ASA 200': 'ASA-200', 'ASA 300': 'ASA-300', 'ASA 400': 'ASA-400',
    'ASA RC 300': 'ASA-RC300', 'ASA RC 400': 'ASA-RC400',
    # Telescope Live
    'CHI-1': 'CHI-1', 'CHI-1-CMOS': 'CHI-1-CMOS', 'CHI-1-CCD': 'CHI-1-CCD',
    'CHI-2-CCD': 'CHI-2-CCD', 'CHI-3-CCD': 'CHI-3-CCD', 'SPA-1': 'SPA-1', 'SPA-2': 'SPA-2',
    'AUS-2': 'AUS-2',
}

# Mapping: INSTRUME header value (uppercase) -> canonical SENSORS_DATABASE key
# Les valeurs sont normalisées en majuscules avant lookup. Inclure toutes variantes courantes des headers FITS.
INSTRUMENT_HEADER_MAPPING = {
    # ZWO (exact header strings often include "ZWO" and model name)
    'ZWO ASI6200MM PRO': 'ASI6200MM', 'ZWO ASI6200MM': 'ASI6200MM', 'ZWO ASI6200MC PRO': 'ASI6200MC', 'ZWO ASI6200MC': 'ASI6200MC',
    'ZWO ASI2600MC AIR': 'ASI2600MC', 'ZWO ASI2600MC PRO': 'ASI2600MC', 'ZWO ASI2600MC': 'ASI2600MC', 'ASI2600MC AIR': 'ASI2600MC',
    'ZWO ASI2600MM PRO': 'ASI2600MM', 'ZWO ASI2600MM': 'ASI2600MM',
    'ZWO ASI2400MM': 'ASI2400MM', 'ZWO ASI2400MC': 'ASI2400MC',
    'ZWO ASI533MM PRO': 'ASI533MM', 'ZWO ASI533MM': 'ASI533MM', 'ZWO ASI533MC PRO': 'ASI533MC', 'ZWO ASI533MC': 'ASI533MC',
    'ZWO ASI294MM PRO': 'ASI294MM', 'ZWO ASI294MM': 'ASI294MM', 'ZWO ASI294MC PRO': 'ASI294MM', 'ZWO ASI294MC': 'ASI294MM',
    'ZWO ASI183MM PRO': 'ASI183MM', 'ZWO ASI183MM': 'ASI183MM', 'ZWO ASI183MC PRO': 'ASI183MM', 'ZWO ASI183MC': 'ASI183MM',
    'ZWO ASI1600MM PRO': 'ASI1600MM', 'ZWO ASI1600MM': 'ASI1600MM', 'ZWO ASI1600MC PRO': 'ASI1600MM', 'ZWO ASI1600MC': 'ASI1600MM',
    'ZWO ASI178MM PRO': 'ASI178MM', 'ZWO ASI178MM': 'ASI178MM', 'ZWO ASI174MM PRO': 'ASI174MM', 'ZWO ASI174MM': 'ASI174MM',
    'ZWO ASI290MM PRO': 'ASI290MM', 'ZWO ASI290MM': 'ASI290MM', 'ZWO ASI224MC PRO': 'ASI224MC', 'ZWO ASI224MC': 'ASI224MC',
    'ZWO ASI385MC PRO': 'ASI385MC', 'ZWO ASI385MC': 'ASI385MC',
    'ZWO ASI585MC': 'ASI585MC', 'ZWO ASI462MC': 'ASI462MC', 'ZWO ASI462MM': 'ASI462MM',
    'ZWO ASI482MC': 'ASI482MC', 'ZWO ASI482MM': 'ASI482MM', 'ZWO ASI485MC': 'ASI485MC', 'ZWO ASI485MM': 'ASI485MM',
    'ZWO ASI678MC': 'ASI678MC', 'ZWO ASI662MC': 'ASI662MC',
    # QHY
    'QHY600M PRO': 'QHY600M', 'QHY600M-P': 'QHY600M', 'QHY600M': 'QHY600M',
    'QHY268M PRO': 'QHY268M', 'QHY268M-P': 'QHY268M', 'QHY268M': 'QHY268M', 'QHY268C': 'QHY268C',
    'QHY410C': 'QHY410C', 'QHY367C': 'QHY367C', 'QHY367C-P': 'QHY367C', 'QHY247C': 'QHY247C',
    'QHY294M': 'QHY294M', 'QHY294C': 'QHY294C', 'QHY183M': 'QHY183M', 'QHY183C': 'QHY183C',
    'QHY533M': 'QHY533M', 'QHY533C': 'QHY533C', 'QHY163M': 'QHY163M', 'QHY163M-P': 'QHY163M',
    'QHY8L': 'QHY8L', 'QHY9M': 'QHY9M', 'QHY10': 'QHY10', 'QHY11': 'QHY11', 'QHY12': 'QHY12',
    'QHY168M': 'QHY168M', 'QHY168C': 'QHY168C',
    # FLI
    'FLI ML16200': 'FLI-ML16200', 'FLI-ML16200': 'FLI-ML16200', 'FLI ML8300': 'FLI-ML8300', 'FLI-ML8300': 'FLI-ML8300',
    'FLI ML11002': 'FLI-ML11002', 'FLI-ML11002': 'FLI-ML11002', 'FLI ML16803': 'FLI-ML16803', 'FLI-ML16803': 'FLI-ML16803',
    'FLI PL16803': 'FLI-PL16803', 'FLI-PL16803': 'FLI-PL16803', 'FLI PL11002': 'FLI-PL11002', 'FLI-PL11002': 'FLI-PL11002',
    'FLI ML8300C': 'FLI-ML8300C', 'FLI-ML8300C': 'FLI-ML8300C',
    # SBIG
    'STF-8300M': 'STF-8300M', 'STF-8300C': 'STF-8300C', 'STT-8300M': 'STT-8300M', 'STT-8300C': 'STT-8300C',
    # Moravian
    'MORAVIAN G3-16200': 'G3-16200', 'G3-16200': 'G3-16200', 'MORAVIAN G3-8300': 'G3-8300', 'G3-8300': 'G3-8300',
    'MORAVIAN G3-11002': 'G3-11002', 'G3-11002': 'G3-11002', 'MORAVIAN G3-16803': 'G3-16803', 'G3-16803': 'G3-16803',
    'MORAVIAN G4-16000': 'G4-16000', 'G4-16000': 'G4-16000', 'MORAVIAN G5-16200': 'G5-16200', 'G5-16200': 'G5-16200',
    # Atik
    'ATIK 460EXM': 'ATIK460EXM', 'ATIK460EXM': 'ATIK460EXM', 'ATIK 460EXC': 'ATIK460EXC', 'ATIK460EXC': 'ATIK460EXC',
    'ATIK 383L+': 'ATIK383L+', 'ATIK383L+': 'ATIK383L+', 'ATIK ONE C': 'ATIK-ONE C', 'ATIK-ONE C': 'ATIK-ONE C',
    # Touptek
    'TOUPTEK IMX571': 'Touptek IMX571', 'TOUPTEK IMX533': 'Touptek IMX533', 'TOUPTEK IMX294': 'Touptek IMX294',
    'TOUPTEK IMX183': 'Touptek IMX183', 'TOUPTEK IMX178': 'Touptek IMX178', 'TOUPTEK IMX455': 'Touptek IMX455',
    'TOUPTEK IMX461': 'Touptek IMX461', 'TOUPTEK IMX485': 'Touptek IMX485', 'TOUPTEK IMX482': 'Touptek IMX482',
    # Player One
    'PLAYER ONE NEPTUNE-C II': 'PLAYER ONE NEPTUNE-C II', 'PLAYER ONE URANUS-C': 'PLAYER ONE URANUS-C',
    'PLAYER ONE APOLLO-MINI C': 'PLAYER ONE APOLLO-MINI C',
    # SVBONY
    'SVBONY SV305': 'SVBONY SV305', 'SVBONY SV405CC': 'SVBONY SV405CC', 'SVBONY SV605CC': 'SVBONY SV605CC',
    # Canon (EOS / INSTRUME typical values)
    'CANON EOS 600D': 'CANON 600D', 'CANON EOS REBEL T3I': 'CANON 600D', 'CANON 600D': 'CANON 600D',
    'CANON EOS 750D': 'CANON 750D', 'CANON EOS REBEL T6I': 'CANON 750D', 'CANON 750D': 'CANON 750D',
    'CANON EOS 5D MARK III': 'CANON 5D MARK III', 'CANON 5D MARK III': 'CANON 5D MARK III', 'CANON EOS 5D III': 'CANON 5D MARK III',
    'CANON EOS R6': 'CANON R6', 'CANON R6': 'CANON R6', 'CANON EOS R5': 'CANON R5', 'CANON R5': 'CANON R5',
    'CANON EOS RA': 'CANON R6', 'CANON EOS R7': 'CANON R7', 'CANON R7': 'CANON R7',
    'CANON EOS 1100D': 'CANON 1100D', 'CANON 1100D': 'CANON 1100D',
    'CANON EOS 700D': 'CANON 700D', 'CANON 700D': 'CANON 700D',
    'CANON EOS 80D': 'CANON 80D', 'CANON 80D': 'CANON 80D',
    'CANON EOS 90D': 'CANON 90D', 'CANON 90D': 'CANON 90D',
    'CANON EOS 6D': 'CANON 6D', 'CANON 6D': 'CANON 6D',
    'CANON EOS 6D MARK II': 'CANON 6D MARK II', 'CANON 6D MARK II': 'CANON 6D MARK II',
    # Nikon
    'NIKON D5300': 'NIKON D5300', 'NIKON D750': 'NIKON D750', 'NIKON D850': 'NIKON D850',
    'NIKON D3200': 'NIKON D3200', 'NIKON D5600': 'NIKON D5600', 'NIKON D610': 'NIKON D610',
    'NIKON D780': 'NIKON D780', 'NIKON D810': 'NIKON D810', 'NIKON D810A': 'NIKON D810A',
    'NIKON Z6': 'NIKON Z6', 'NIKON Z7': 'NIKON Z7', 'NIKON Z8': 'NIKON Z8', 'NIKON Z9': 'NIKON Z9',
    # Sony
    'SONY ILCE-7S': 'SONY A7S', 'SONY A7S': 'SONY A7S',
    'SONY ILCE-7M3': 'SONY A7III', 'SONY A7III': 'SONY A7III', 'SONY ILCE-7RM3': 'SONY A7RIII', 'SONY A7RIII': 'SONY A7RIII',
    'SONY ILCE-6000': 'SONY A6000', 'SONY A6000': 'SONY A6000',
    'SONY ILCE-6400': 'SONY A6400', 'SONY A6400': 'SONY A6400',
    'SONY ILCE-6500': 'SONY A6500', 'SONY A6500': 'SONY A6500',
    'SONY ILCE-7M4': 'SONY A7IV', 'SONY A7IV': 'SONY A7IV',
    # Sony IMX sensor refs (headers sometimes use sensor only)
    'IMX571': 'IMX571', 'IMX455': 'IMX455', 'IMX533': 'IMX533', 'IMX294': 'IMX294',
    'IMX183': 'IMX183', 'IMX178': 'IMX178', 'IMX461': 'IMX461', 'IMX485': 'IMX485', 'IMX482': 'IMX482',
    'IMX224': 'IMX224', 'IMX290': 'IMX290', 'IMX174': 'IMX174', 'IMX462': 'IMX462',
    # Sigma
    'SIGMA FP': 'SIGMA FP', 'SIGMA FP L': 'SIGMA FP',
}

def format_time(seconds):
    """Converts seconds to hours:minutes:seconds format"""
    time = timedelta(seconds=int(seconds))
    return str(time)

def format_time_hours_minutes(seconds):
    """Converts seconds to hours:minutes format without days"""
    total_hours = int(seconds // 3600)
    total_minutes = int((seconds % 3600) // 60)
    return f"{total_hours}:{total_minutes:02d}"

def format_time_with_details(seconds):
    """Converts seconds to hours:minutes format with full duration in parentheses"""
    time = timedelta(seconds=int(seconds))
    
    # Calculate hours and minutes
    total_hours = int(seconds // 3600)
    total_minutes = int((seconds % 3600) // 60)
    
    # Format as HhMM
    time_str = f"{total_hours}h{total_minutes:02d}"
    
    # Add full duration in parentheses
    full_duration = str(time)
    return f"{time_str} ({full_duration})"

def ensure_catalog_uppercase(text):
    """Ensures catalog names are uppercase in object names"""
    if not text:
        return ""
    
    import re
    
    # Common astronomical catalogs to convert to uppercase
    catalogs = ['ngc', 'messier', 'm ', 'ic ', 'ugc', 'hd', 'hip', 'tyc', 'gsc', 'usno', '2mass', 'pgc', 'arp', 'c ']
    
    result = text
    
    # Convert catalog names to uppercase
    for catalog in catalogs:
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(catalog) + r'\b'
        result = re.sub(pattern, catalog.upper(), result, flags=re.IGNORECASE)
    
    return result

def get_astronomical_sort_key(target_name):
    """Create a sort key that handles astronomical object names properly for alphabetical sorting"""
    import re
    import unicodedata
    
    # Extract main name by removing parenthetical information
    # Example: "Andromeda Galaxy (M 31)" -> "Andromeda Galaxy"
    main_name = re.sub(r'\s*\([^)]*\)', '', target_name).strip()
    
    # Normalize unicode characters (remove accents, etc.)
    normalized = unicodedata.normalize('NFD', main_name.lower())
    
    # Remove accents but keep special characters that are important for astronomical names
    clean_name = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    
    # For astronomical objects, we want to sort by the main name first
    # Handle common prefixes like "NGC", "M", "IC", etc.
    parts = clean_name.split()
    
    # If it starts with a catalog prefix, sort by catalog number
    if len(parts) > 0:
        first_part = parts[0]
        
        # Handle special case where catalog name contains a dash (e.g., "sh2-101")
        if '-' in first_part:
            # Split on dash and check if first part is a catalog prefix
            dash_parts = first_part.split('-')
            if len(dash_parts) >= 2 and dash_parts[0] in ['ngc', 'm', 'ic', 'ugc', 'arp', 'messier', 'abell', 'sh2', 'rcw', 'pgc', 'cl', 'hd', 'barnard', 'c', 'gc']:
                catalog_prefix = dash_parts[0]
                # Extract number from the part after the dash
                number_match = re.search(r'(\d+)', dash_parts[1])
                if number_match:
                    number = int(number_match.group(1))
                    return (catalog_prefix, number, clean_name)
        
        if first_part in ['ngc', 'm', 'ic', 'ugc', 'arp', 'messier', 'abell', 'sh2', 'rcw', 'pgc', 'cl', 'hd', 'barnard', 'c', 'gc']:
            # Extract number for proper numerical sorting
            number_match = re.search(r'(\d+)', first_part + ' '.join(parts[1:]))
            if number_match:
                number = int(number_match.group(1))
                # Return a tuple for consistent sorting
                return (first_part, number, clean_name)
    
    # For common names, sort alphabetically by the main name
    # Return a tuple for consistent sorting (catalog type, 0, name)
    return ('other', 0, clean_name)

def escape_latex(text):
    """Escapes special characters for LaTeX"""
    if not text:
        return ""
    
    # First ensure catalog names are uppercase
    text = ensure_catalog_uppercase(text)
    
    # Replace special characters
    replacements = {
        '\\': '\\textbackslash{}',
        '{': '\\{',
        '}': '\\}',
        '$': '\\$',
        '&': '\\&',
        '#': '\\#',
        '^': '\\textasciicircum{}',
        '_': '\\_',
        '~': '\\textasciitilde{}',
        '%': '\\%',
        '<': '\\textless{}',
        '>': '\\textgreater{}',
        '|': '\\textbar{}',
        '[': '{[}',
        ']': '{]}',
    }
    
    result = text
    for char, replacement in replacements.items():
        result = result.replace(char, replacement)
    
    return result

def format_filter_name_latex(filter_name):
    """Format filter name for LaTeX display with Greek letters"""
    if not filter_name:
        return ""
    
    # Convert common filter names to LaTeX format with Greek letters
    filter_mapping = {
        'HA': 'H$\\alpha$',
        'H-ALPHA': 'H$\\alpha$',
        'HALPHA': 'H$\\alpha$',
        'H_ALPHA': 'H$\\alpha$',
        'H-ALPHA': 'H$\\alpha$',
        'HB': 'H$\\beta$',
        'H-BETA': 'H$\\beta$',
        'HBETA': 'H$\\beta$',
        'H_BETA': 'H$\\beta$',
        'H-BETA': 'H$\\beta$',
        'OIII': 'O\\textsc{iii}',
        'O-III': 'O\\textsc{iii}',
        'O_III': 'O\\textsc{iii}',
        'SII': 'S\\textsc{ii}',
        'S-II': 'S\\textsc{ii}',
        'S_II': 'S\\textsc{ii}',
        'NII': 'N\\textsc{ii}',
        'N-II': 'N\\textsc{ii}',
        'N_II': 'N\\textsc{ii}',
    }
    
    # Check for exact match first
    if filter_name.upper() in filter_mapping:
        return filter_mapping[filter_name.upper()]
    
    # Check for partial matches (case insensitive)
    filter_upper = filter_name.upper()
    for key, value in filter_mapping.items():
        if key in filter_upper or filter_upper in key:
            return value
    
    # If no match, return the original filter name escaped
    return escape_latex(filter_name)

def convert_filter_name_to_greek_matplotlib(filter_name):
    """Convert filter names to Greek characters for matplotlib display"""
    if not filter_name:
        return filter_name
    
    # Mapping of filter codes to Greek matplotlib representations
    greek_mapping = {
        'HA': 'Hα',
        'Ha': 'Hα',
        'H-ALPHA': 'Hα',
        'HALPHA': 'Hα',
        'SII': 'S II',
        'OIII': 'O III'
    }
    
    return greek_mapping.get(filter_name, filter_name)

def convert_filter_name_to_greek_latex(filter_name):
    """Convert filter names to Greek characters for LaTeX display"""
    if not filter_name:
        return filter_name
    
    # Mapping of filter codes to Greek LaTeX representations
    greek_mapping = {
        'HA': 'H$\\alpha$',
        'Ha': 'H$\\alpha$',
        'H-ALPHA': 'H$\\alpha$',
        'HALPHA': 'H$\\alpha$',
        'HBETA': 'H$\\beta$',
        'HB': 'H$\\beta$',
        'H-BETA': 'H$\\beta$',
        'HGAMMA': 'H$\\gamma$',
        'HG': 'H$\\gamma$',
        'H-GAMMA': 'H$\\gamma$',
        'HDELTA': 'H$\\delta$',
        'HD': 'H$\\delta$',
        'H-DELTA': 'H$\\delta$',
        'HEPSILON': 'H$\\epsilon$',
        'HE': 'H$\\epsilon$',
        'H-EPSILON': 'H$\\epsilon$',
        'HZETA': 'H$\\zeta$',
        'HZ': 'H$\\zeta$',
        'H-ZETA': 'H$\\zeta$',
        'HETA': 'H$\\eta$',
        'HET': 'H$\\eta$',
        'H-ETA': 'H$\\eta$',
        'HTHETA': 'H$\\theta$',
        'HTH': 'H$\\theta$',
        'H-THETA': 'H$\\theta$',
        'HIOTA': 'H$\\iota$',
        'HI': 'H$\\iota$',
        'H-IOTA': 'H$\\iota$',
        'HKAPPA': 'H$\\kappa$',
        'HK': 'H$\\kappa$',
        'H-KAPPA': 'H$\\kappa$',
        'HLAMBDA': 'H$\\lambda$',
        'HL': 'H$\\lambda$',
        'H-LAMBDA': 'H$\\lambda$',
        'HMU': 'H$\\mu$',
        'HM': 'H$\\mu$',
        'H-MU': 'H$\\mu$',
        'HNU': 'H$\\nu$',
        'HN': 'H$\\nu$',
        'H-NU': 'H$\\nu$',
        'HXI': 'H$\\xi$',
        'HX': 'H$\\xi$',
        'H-XI': 'H$\\xi$',
        'HOMICRON': 'H$\\omicron$',
        'HO': 'H$\\omicron$',
        'H-OMICRON': 'H$\\omicron$',
        'HPI': 'H$\\pi$',
        'HP': 'H$\\pi$',
        'H-PI': 'H$\\pi$',
        'HRHO': 'H$\\rho$',
        'HR': 'H$\\rho$',
        'H-RHO': 'H$\\rho$',
        'HSIGMA': 'H$\\sigma$',
        'HS': 'H$\\sigma$',
        'H-SIGMA': 'H$\\sigma$',
        'HTAU': 'H$\\tau$',
        'HT': 'H$\\tau$',
        'H-TAU': 'H$\\tau$',
        'HUPSILON': 'H$\\upsilon$',
        'HU': 'H$\\upsilon$',
        'H-UPSILON': 'H$\\upsilon$',
        'HPHI': 'H$\\phi$',
        'HPH': 'H$\\phi$',
        'H-PHI': 'H$\\phi$',
        'HCHI': 'H$\\chi$',
        'HCH': 'H$\\chi$',
        'H-CHI': 'H$\\chi$',
        'HPSI': 'H$\\psi$',
        'HPS': 'H$\\psi$',
        'H-PSI': 'H$\\psi$',
        'HOMEGA': 'H$\\omega$',
        'HOM': 'H$\\omega$',
        'H-OMEGA': 'H$\\omega$',
    }
    
    # Check if the filter name matches any of our Greek mappings
    if filter_name in greek_mapping:
        return greek_mapping[filter_name]
    
    # If no Greek mapping found, return the original name (escaped for LaTeX)
    return escape_latex(filter_name)

def convert_astronomical_object_to_full_name(target_name):
    """Convert astronomical objects to full names with common names"""
    if not target_name:
        return target_name
    
    import re
    
    # Check if the target name already contains a common name (already processed by normalize_target_name)
    # This prevents duplication for objects like "Crab Nebula (M 1)"
    if '(' in target_name and ')' in target_name:
        # Check if it's already a formatted name like "Crab Nebula (M 1)" or "Andromeda Galaxy (M 31)"
        if re.search(r'[A-Za-z\s]+\([A-Z]+\s*\d+\)', target_name):
            return target_name  # Already formatted, don't process further
    
    # Additional check: if the name contains common astronomical terms, it's likely already processed
    common_terms = ['Nebula', 'Galaxy', 'Cluster', 'Star', 'Cloud', 'Object', 'Heart', 'Elephant', 'Flaming', 'Tadpole', 'Horsehead', 'Pelican', 'Cocoon', 'California', 'Crystal', 'Monkey', 'Pacman', 'Hamburger', 'Needle', 'Cat\'s Eye', 'Crescent', 'Fireworks', 'Western Veil', 'Pickering\'s Triangle', 'North America', 'Iris', 'Deer Lick', 'Wizard', 'Bubble', 'Silver Sliver', 'Tulip']
    if any(term in target_name for term in common_terms) and '(' in target_name:
        return target_name  # Already processed, don't modify further
    
    # First check Messier objects
    messier_match = re.search(r'\bM\s*(\d{1,3})\b', target_name, re.IGNORECASE)
    if messier_match:
        messier_num = messier_match.group(1)
        messier_key = f'M{messier_num}'
        
        if messier_key in MESSIER_DATABASE:
            full_name = MESSIER_DATABASE[messier_key]
            original_text = target_name.replace(messier_match.group(0), '').strip()
            if original_text:
                return f"{full_name} {original_text}"
            else:
                return full_name
    
    # Check extended astronomical database
    # Try exact match first
    if target_name in EXTENDED_ASTRONOMICAL_DATABASE:
        return EXTENDED_ASTRONOMICAL_DATABASE[target_name]
    
    # Try to match with various formats
    # NGC objects
    ngc_match = re.search(r'\bNGC\s*(\d+)\b', target_name, re.IGNORECASE)
    if ngc_match:
        ngc_num = ngc_match.group(1)
        ngc_key = f'NGC {ngc_num}'
        if ngc_key in EXTENDED_ASTRONOMICAL_DATABASE:
            full_name = EXTENDED_ASTRONOMICAL_DATABASE[ngc_key]
            original_text = target_name.replace(ngc_match.group(0), '').strip()
            if original_text:
                return f"{full_name} {original_text}"
            else:
                return full_name
    
    # IC objects
    ic_match = re.search(r'\bIC\s*(\d+)\b', target_name, re.IGNORECASE)
    if ic_match:
        ic_num = ic_match.group(1)
        ic_key = f'IC {ic_num}'
        if ic_key in EXTENDED_ASTRONOMICAL_DATABASE:
            full_name = EXTENDED_ASTRONOMICAL_DATABASE[ic_key]
            original_text = target_name.replace(ic_match.group(0), '').strip()
            if original_text:
                return f"{full_name} {original_text}"
            else:
                return full_name
    
    # Sh2 objects
    sh2_match = re.search(r'\bSh2[-\s]*(\d+)\b', target_name, re.IGNORECASE)
    if sh2_match:
        sh2_num = sh2_match.group(1)
        sh2_key = f'Sh2-{sh2_num}'
        if sh2_key in EXTENDED_ASTRONOMICAL_DATABASE:
            full_name = EXTENDED_ASTRONOMICAL_DATABASE[sh2_key]
            original_text = target_name.replace(sh2_match.group(0), '').strip()
            if original_text:
                return f"{full_name} {original_text}"
            else:
                return full_name
    
    # LBN objects
    lbn_match = re.search(r'\bLBN\s*(\d+)\b', target_name, re.IGNORECASE)
    if lbn_match:
        lbn_num = lbn_match.group(1)
        lbn_key = f'LBN {lbn_num}'
        if lbn_key in EXTENDED_ASTRONOMICAL_DATABASE:
            full_name = EXTENDED_ASTRONOMICAL_DATABASE[lbn_key]
            original_text = target_name.replace(lbn_match.group(0), '').strip()
            if original_text:
                return f"{full_name} {original_text}"
            else:
                return full_name
    
    # PGC objects
    pgc_match = re.search(r'\bPGC\s*(\d+)\b', target_name, re.IGNORECASE)
    if pgc_match:
        pgc_num = pgc_match.group(1)
        pgc_key = f'PGC {pgc_num}'
        if pgc_key in EXTENDED_ASTRONOMICAL_DATABASE:
            full_name = EXTENDED_ASTRONOMICAL_DATABASE[pgc_key]
            original_text = target_name.replace(pgc_match.group(0), '').strip()
            if original_text:
                return f"{full_name} {original_text}"
            else:
                return full_name
    
    # RCW objects
    rcw_match = re.search(r'\bRCW[-\s]*(\d+)\b', target_name, re.IGNORECASE)
    if rcw_match:
        rcw_num = rcw_match.group(1)
        rcw_key = f'RCW {rcw_num}'
        if rcw_key in EXTENDED_ASTRONOMICAL_DATABASE:
            full_name = EXTENDED_ASTRONOMICAL_DATABASE[rcw_key]
            original_text = target_name.replace(rcw_match.group(0), '').strip()
            if original_text:
                return f"{full_name} {original_text}"
            else:
                return full_name
    
    # Abell objects
    abell_match = re.search(r'\bAbell[-\s]*(\d+)\b', target_name, re.IGNORECASE)
    if abell_match:
        abell_num = abell_match.group(1)
        abell_key = f'Abell {abell_num}'
        if abell_key in EXTENDED_ASTRONOMICAL_DATABASE:
            full_name = EXTENDED_ASTRONOMICAL_DATABASE[abell_key]
            original_text = target_name.replace(abell_match.group(0), '').strip()
            if original_text:
                return f"{full_name} {original_text}"
            else:
                return full_name
    
    # Arp objects
    arp_match = re.search(r'\bArp\s*(\d+)\b', target_name, re.IGNORECASE)
    if arp_match:
        arp_num = arp_match.group(1)
        arp_key = f'Arp {arp_num}'
        if arp_key in ARP_DATABASE:
            full_name = ARP_DATABASE[arp_key]
            original_text = target_name.replace(arp_match.group(0), '').strip()
            if original_text:
                return f"{full_name} {original_text}"
            else:
                return full_name
    
    return target_name

def convert_messier_to_full_name(target_name):
    """Convert Messier numbers to full names with common names (legacy function)"""
    return convert_astronomical_object_to_full_name(target_name)

def normalize_sharpless_name(target_name):
    """Normalize Sharpless catalog names to proper format"""
    if not target_name:
        return target_name
    
    import re
    
    # Pattern to match various Sharpless formats:
    # - SH2, Sh2, sh2 (with or without space before number)
    # - SH 2, Sh 2, sh 2 (with space between SH and number)
    # This pattern captures the catalog prefix and number, and any following text
    sharpless_pattern = r'\b(SH|Sh|sh)\s*2\s*(\d+)([A-Za-z]*)'
    match = re.search(sharpless_pattern, target_name, re.IGNORECASE)
    
    if match:
        # Replace with proper format: Sh2-XXX (always use "Sh2" format)
        number = match.group(2)
        following_text = match.group(3)
        
        # Get any additional text after the match
        remaining_text = target_name[match.end():].strip()
        
        # Build the result with correct capitalization
        result = f"Sh2-{number}"
        
        # Add following text (like "Squib") with proper spacing
        if following_text:
            result += f" {following_text}"
        
        # Add any remaining text, but clean up isolated parentheses
        if remaining_text:
            # Remove isolated closing parentheses like " )" at the end
            remaining_text = re.sub(r'\s*\)\s*$', '', remaining_text)
            # Remove isolated opening parentheses like "( " at the beginning
            remaining_text = re.sub(r'^\s*\(\s*', '', remaining_text)
            # Remove any remaining isolated parentheses
            remaining_text = re.sub(r'\s*\(\s*\)\s*', '', remaining_text)
            
            if remaining_text.strip():
                result += f" {remaining_text.strip()}"
        
        return result
    
    return target_name

def format_target_name_for_latex(target_name):
    """Format target names for LaTeX display with proper capitalization"""
    if not target_name:
        return target_name
    
    # First, normalize Sharpless catalog names
    target_name = normalize_sharpless_name(target_name)
    
    # Then, normalize the target name (this handles multi-catalog objects and common names)
    target_name = normalize_target_name(target_name)
    
    # Finally, convert astronomical objects to full names (only for objects not handled by normalize_target_name)
    target_name = convert_astronomical_object_to_full_name(target_name)
    
    # Special handling for LMC to ensure it's always displayed as LMC in uppercase
    if 'Large Magellanic Cloud' in target_name:
        # Replace any lowercase lmc with uppercase LMC in the display
        formatted_name = target_name.replace('(lmc)', '(LMC)')
        formatted_name = formatted_name.replace('(Lmc)', '(LMC)')
        formatted_name = formatted_name.replace('(lMc)', '(LMC)')
        formatted_name = formatted_name.replace('(LmC)', '(LMC)')
        return escape_latex(formatted_name)
    
    # Special handling for Wolf-Rayet stars to ensure they're always displayed as WR in uppercase
    # This handles cases where "Wr" might appear instead of "WR"
    import re
    # Replace "Wr " with "WR " (Wolf-Rayet stars)
    formatted_name = re.sub(r'\bWr\s+(\d+)', r'WR \1', target_name)
    # Also handle cases without space: "Wr134" -> "WR 134"
    formatted_name = re.sub(r'\bWr(\d+)', r'WR \1', formatted_name)
    
    # For other targets, just escape for LaTeX
    return escape_latex(formatted_name)

def detect_mosaic_panel(target_name):
    """Detects if a target name is a mosaic panel and extracts the base object name"""
    if not target_name:
        return None, None
    
    import re
    
    # Patterns for mosaic panels in various languages and formats
    mosaic_patterns = [
        # French patterns
        r'^(.+?)[-_]panneau[-_](\d+)$',
        r'^(.+?)\s+panneau\s+(\d+)$',
        r'^(.+?)\s+panneau\s+panneau\s+(\d+)$',
        # English patterns  
        r'^(.+?)[-_]panel[-_](\d+)$',
        r'^(.+?)\s+panel\s+(\d+)$',
        r'^(.+?)\s+panel\s+panel\s+(\d+)$',
        # Generic patterns
        r'^(.+?)[-_]part[-_](\d+)$',
        r'^(.+?)\s+part\s+(\d+)$',
        r'^(.+?)[-_]section[-_](\d+)$',
        r'^(.+?)\s+section\s+(\d+)$',
        r'^(.+?)[-_]tile[-_](\d+)$',
        r'^(.+?)\s+tile\s+(\d+)$'
    ]
    
    target_clean = target_name.strip()
    
    for pattern in mosaic_patterns:
        match = re.match(pattern, target_clean, re.IGNORECASE)
        if match:
            base_object = match.group(1).strip()
            panel_number = match.group(2)
            return base_object, panel_number
    
    return None, None

def get_mosaic_name(base_object):
    """Gets the appropriate mosaic name for a base object"""
    if not base_object:
        return None
    
    # Normalize the base object name
    base_normalized = normalize_target_name(base_object)
    
    # If it's a known object, use the proper name with "Mosaic" suffix
    if base_normalized and base_normalized != base_object:
        # Extract the catalog part if present
        if '(' in base_normalized and ')' in base_normalized:
            # Keep the catalog designation
            return f"{base_normalized.replace(')', ' Mosaic)')}"
        else:
            return f"{base_normalized} Mosaic"
    else:
        # For unknown objects, just add "Mosaic" to the base name
        return f"{base_object} Mosaic"

def group_normalized_targets(data_by_target):
    """Groups targets that have the same normalized name (e.g., LMC and lmc)"""
    normalized_groups = {}
    
    for target_name, target_data in data_by_target.items():
        # Get the normalized name for this target
        normalized_name = normalize_target_name(target_name)
        
        if normalized_name not in normalized_groups:
            # First occurrence of this normalized name
            normalized_groups[normalized_name] = target_data.copy()
            # Keep track of original names for reference
            normalized_groups[normalized_name]['original_names'] = [target_name]
        else:
            # Merge with existing group
            existing_data = normalized_groups[normalized_name]
            
            # Merge files
            existing_data['files'].extend(target_data['files'])
            
            # Merge time_by_filter
            for filter_name, time_list in target_data['time_by_filter'].items():
                if filter_name in existing_data['time_by_filter']:
                    existing_data['time_by_filter'][filter_name].extend(time_list)
                else:
                    existing_data['time_by_filter'][filter_name] = time_list.copy()
            
            # Merge telescopes and instruments
            if isinstance(existing_data['telescopes'], set):
                existing_data['telescopes'].update(target_data['telescopes'])
            else:
                existing_data['telescopes'] = list(set(existing_data['telescopes'] + target_data['telescopes']))
            
            if isinstance(existing_data['instruments'], set):
                existing_data['instruments'].update(target_data['instruments'])
            else:
                existing_data['instruments'] = list(set(existing_data['instruments'] + target_data['instruments']))
            
            # Merge dates
            if isinstance(existing_data['dates'], set):
                existing_data['dates'].update(target_data['dates'])
            else:
                existing_data['dates'] = list(set(existing_data['dates'] + target_data['dates']))
            
            # Merge files_by_date
            if 'files_by_date' in target_data:
                if 'files_by_date' not in existing_data:
                    existing_data['files_by_date'] = {}
                
                for date, date_data in target_data['files_by_date'].items():
                    if date in existing_data['files_by_date']:
                        # Merge existing date data
                        existing_date_data = existing_data['files_by_date'][date]
                        existing_date_data['files'].extend(date_data['files'])
                        existing_date_data['total_time'] += date_data['total_time']
                        
                        # Merge time_by_filter for this date
                        for filter_name, time_list in date_data['time_by_filter'].items():
                            if filter_name in existing_date_data['time_by_filter']:
                                existing_date_data['time_by_filter'][filter_name].extend(time_list)
                            else:
                                existing_date_data['time_by_filter'][filter_name] = time_list.copy()
                        
                        # Merge exposure_details
                        for filter_name, exp_details in date_data['exposure_details'].items():
                            if filter_name in existing_date_data['exposure_details']:
                                for exp_time, count in exp_details.items():
                                    if exp_time in existing_date_data['exposure_details'][filter_name]:
                                        existing_date_data['exposure_details'][filter_name][exp_time] += count
                                    else:
                                        existing_date_data['exposure_details'][filter_name][exp_time] = count
                            else:
                                existing_date_data['exposure_details'][filter_name] = exp_details.copy()
                    else:
                        # New date, just copy the data
                        existing_data['files_by_date'][date] = date_data.copy()
            
            # Merge other data structures
            if 'received_light' in target_data:
                if 'received_light' not in existing_data:
                    existing_data['received_light'] = {}
                for filter_name, light_list in target_data['received_light'].items():
                    if filter_name in existing_data['received_light']:
                        existing_data['received_light'][filter_name].extend(light_list)
                    else:
                        existing_data['received_light'][filter_name] = light_list.copy()
            
            if 'adu_samples' in target_data:
                if 'adu_samples' not in existing_data:
                    existing_data['adu_samples'] = {}
                for filter_name, samples in target_data['adu_samples'].items():
                    if filter_name in existing_data['adu_samples']:
                        existing_data['adu_samples'][filter_name].extend(samples)
                    else:
                        existing_data['adu_samples'][filter_name] = samples.copy()
            
            if 'adu_counter_by_filter' in target_data:
                if 'adu_counter_by_filter' not in existing_data:
                    existing_data['adu_counter_by_filter'] = {}
                for filter_name, count in target_data['adu_counter_by_filter'].items():
                    if filter_name in existing_data['adu_counter_by_filter']:
                        existing_data['adu_counter_by_filter'][filter_name] += count
                    else:
                        existing_data['adu_counter_by_filter'][filter_name] = count
            
            # Add to original names
            existing_data['original_names'].append(target_name)
    
    # Convert sets to lists for JSON serialization
    for target_data in normalized_groups.values():
        if isinstance(target_data['telescopes'], set):
            target_data['telescopes'] = list(target_data['telescopes'])
        if isinstance(target_data['instruments'], set):
            target_data['instruments'] = list(target_data['instruments'])
        if isinstance(target_data['dates'], set):
            target_data['dates'] = list(target_data['dates'])
    
    return normalized_groups


# Base de données bilingue (FR/EN) des types d'objets SIMBAD — exhaustive, d'après
# https://simbad.cds.unistra.fr/guide/otypes.labels.txt (liste officielle, ~199 codes).
# Format: code -> (libellé français, libellé anglais).
SIMBAD_OTYPE_LABELS = {
    # Étoiles et systèmes stellaires
    '*': ('Étoile', 'Star'),
    '**': ('Étoile double', 'Double star'),
    'V*': ('Étoile variable', 'Variable star'),
    'Ir*': ('Étoile variable irrégulière', 'Irregular variable star'),
    'RR*': ('Étoile RR Lyrae', 'RR Lyrae star'),
    'Ce*': ('Céphéide', 'Cepheid'),
    'cC*': ('Céphéide classique', 'Classical Cepheid'),
    'WV*': ('Céphéide de type II', 'Type II Cepheid'),
    'dS*': ('Étoile delta Scuti', 'Delta Scuti variable'),
    'SX*': ('Étoile variable SX Phénicis', 'SX Phoenicis variable'),
    'gD*': ('Étoile gamma Doradus', 'Gamma Doradus variable'),
    'RV*': ('Étoile RV Tauri', 'RV Tauri variable'),
    'Mi*': ('Mira', 'Mira variable'),
    'LP*': ('Variable à longue période', 'Long-period variable'),
    'Pu*': ('Étoile pulsante', 'Pulsating star'),
    'bC*': ('Étoile bêta Céphéi', 'Beta Cephei variable'),
    'a2*': ('Étoile alpha² Canum Venaticorum', 'Alpha² CVn variable'),
    'Ro*': ('Étoile variable de rotation', 'Rotating variable star'),
    'BY*': ('Étoile BY Draconis', 'BY Draconis variable'),
    'RS*': ('Étoile RS Canum Venaticorum', 'RS CVn variable'),
    'El*': ('Variable elliptoïdale', 'Ellipsoidal variable'),
    'EB*': ('Binaire à éclipse', 'Eclipsing binary'),
    'SB*': ('Binaire spectroscopique', 'Spectroscopic binary'),
    'Sy*': ('Étoile symbiotique', 'Symbiotic star'),
    'CV*': ('Variable cataclysmique', 'Cataclysmic variable'),
    'No*': ('Nova', 'Nova'),
    'XB*': ('Binaire X', 'X-ray binary'),
    'LXB': ('Binaire X à faible masse', 'Low-mass X-ray binary'),
    'HXB': ('Binaire X à haute masse', 'High-mass X-ray binary'),
    'Psr': ('Pulsar', 'Pulsar'),
    'N*': ('Étoile à neutrons', 'Neutron star'),
    'WD*': ('Naine blanche', 'White dwarf'),
    'BD*': ('Naine brune', 'Brown dwarf'),
    'LM*': ('Étoile de faible masse', 'Low-mass star'),
    'HS*': ('Sous-naine chaude', 'Hot subdwarf'),
    'HB*': ('Étoile de branche horizontale', 'Horizontal-branch star'),
    'RG*': ('Étoile de la branche des géantes rouges', 'Red giant branch star'),
    'AB*': ('Étoile AGB', 'AGB star'),
    'pA*': ('Étoile post-AGB', 'Post-AGB star'),
    'sg*': ('Supergéante', 'Supergiant'),
    's*r': ('Supergéante rouge', 'Red supergiant'),
    's*y': ('Supergéante jaune', 'Yellow supergiant'),
    's*b': ('Supergéante bleue', 'Blue supergiant'),
    'WR*': ('Étoile Wolf-Rayet', 'Wolf-Rayet star'),
    'C*': ('Étoile carbone', 'Carbon star'),
    'S*': ('Étoile S', 'S-type star'),
    'Pe*': ('Étoile à particularités chimiques', 'Chemically peculiar star'),
    'Be*': ('Étoile Be', 'Be star'),
    'Ae*': ('Étoile Ae', 'Ae star'),
    'TT*': ('Étoile T Tauri', 'T Tauri star'),
    'Y*O': ('Objet stellaire jeune', 'Young stellar object'),
    'Or*': ('Étoile d\'Orion', 'Orion variable'),
    'RC*': ('Étoile R Coronae Borealis', 'R CrB variable'),
    'OH*': ('Étoile OH/IR', 'OH/IR star'),
    'Em*': ('Étoile à raies d\'émission', 'Emission-line star'),
    'PM*': ('Étoile à fort propre mouvement', 'High proper-motion star'),
    'HV*': ('Étoile à haute vitesse', 'High-velocity star'),
    'BS*': ('Traînarde bleue', 'Blue straggler'),
    'Ev*': ('Étoile en évolution', 'Evolved star'),
    'Er*': ('Étoile éruptive', 'Eruptive variable star'),
    'Ir*': ('Étoile variable irrégulière', 'Irregular variable star'),
    # Amas et associations
    'Cl*': ('Amas d\'étoiles', 'Star cluster'),
    'OpC': ('Amas ouvert', 'Open cluster'),
    'GlC': ('Amas globulaire', 'Globular cluster'),
    'As*': ('Association stellaire', 'Stellar association'),
    'St*': ('Courant stellaire', 'Stellar stream'),
    'MGr': ('Groupe mouvant', 'Moving group'),
    # Milieu interstellaire et nébuleuses
    'ISM': ('Milieu interstellaire', 'Interstellar medium'),
    'SFR': ('Région de formation stellaire', 'Star-forming region'),
    'HII': ('Région HII', 'HII region'),
    'Cld': ('Nuage', 'Cloud'),
    'GNe': ('Nébuleuse galactique', 'Galactic nebula'),
    'RNe': ('Nébuleuse par réflexion', 'Reflection nebula'),
    'MoC': ('Nuage moléculaire', 'Molecular cloud'),
    'DNe': ('Nébuleuse obscure', 'Dark nebula'),
    'glb': ('Globule', 'Globule'),
    'cor': ('Cœur dense', 'Dense core'),
    'bub': ('Bulle', 'Bubble'),
    'CGb': ('Globule cométaire', 'Cometary globule'),
    'HVC': ('Nuage à haute vitesse', 'High-velocity cloud'),
    'SNR': ('Rémanent de supernova', 'Supernova remnant'),
    'sh': ('Coquille HI', 'HI shell'),
    'flt': ('Filament', 'Filament'),
    'PN': ('Nébuleuse planétaire', 'Planetary nebula'),
    'HH': ('Objet Herbig-Haro', 'Herbig-Haro object'),
    'out': ('Écoulement', 'Outflow'),
    'PoC': ('Partie de nuage', 'Part of cloud'),
    # Galaxies et ensembles
    'G': ('Galaxie', 'Galaxy'),
    'LSB': ('Galaxie à faible brillance de surface', 'Low surface brightness galaxy'),
    'bCG': ('Galaxie compacte bleue', 'Blue compact galaxy'),
    'SBG': ('Galaxie à sursaut stellaire', 'Starburst galaxy'),
    'H2G': ('Galaxie HII', 'HII galaxy'),
    'EmG': ('Galaxie à émission', 'Emission-line galaxy'),
    'AGN': ('Noyau actif de galaxie', 'Active galactic nucleus'),
    'SyG': ('Galaxie de Seyfert', 'Seyfert galaxy'),
    'Sy1': ('Seyfert de type 1', 'Seyfert type 1'),
    'Sy2': ('Seyfert de type 2', 'Seyfert type 2'),
    'rG': ('Galaxie radio', 'Radio galaxy'),
    'LIN': ('Galaxie LINER', 'LINER galaxy'),
    'QSO': ('Quasar', 'Quasar'),
    'Bla': ('Blazar', 'Blazar'),
    'BLL': ('Objet BL Lac', 'BL Lac object'),
    'BiC': ('Galaxie la plus brillante d\'amas', 'Brightest cluster galaxy'),
    'GiP': ('Galaxie dans une paire', 'Galaxy in pair'),
    'GiG': ('Galaxie dans un groupe', 'Galaxy in group'),
    'GiC': ('Galaxie dans un amas', 'Galaxy in cluster'),
    'IG': ('Galaxie en interaction', 'Interacting galaxy'),
    'PaG': ('Paire de galaxies', 'Pair of galaxies'),
    'GrG': ('Groupe de galaxies', 'Group of galaxies'),
    'CGG': ('Groupe compact de galaxies', 'Compact group of galaxies'),
    'ClG': ('Galaxie d\'amas', 'Cluster galaxy'),
    'SCG': ('Galaxie de superamas', 'Supercluster galaxy'),
    'vid': ('Vide', 'Void'),
    'PoG': ('Partie de galaxie', 'Part of galaxy'),
    # Lentilles gravitationnelles
    'gLe': ('Lentille gravitationnelle', 'Gravitational lens'),
    'LeG': ('Galaxie lentillée', 'Lensed galaxy'),
    'Lev': ('Événement de microlentille', 'Lensing event'),
    'LeQ': ('Quasar lentillé', 'Lensed quasar'),
    'LeI': ('Image lentillée', 'Lensed image'),
    'gLS': ('Système de lentille gravitationnelle', 'Gravitational lens system'),
    'GWE': ('Événement d\'onde gravitationnelle', 'Gravitational wave event'),
    'grv': ('Source gravitationnelle', 'Gravitational source'),
    # Supernovae et transients
    'SN*': ('Supernova', 'Supernova'),
    'gB': ('Sursaut gamma', 'Gamma-ray burst'),
    'ULX': ('Source X ultra-lumineuse', 'Ultra-luminous X-ray source'),
    # Sources par domaine spectral
    'FIR': ('Infrarouge lointain', 'Far infrared'),
    'NIR': ('Infrarouge proche', 'Near infrared'),
    'IR': ('Source infrarouge', 'Infrared source'),
    'UV': ('Source UV', 'UV source'),
    'X': ('Source X', 'X-ray source'),
    'gam': ('Source gamma', 'Gamma-ray source'),
    'Rad': ('Source radio', 'Radio source'),
    'mR': ('Source radio (métrique)', 'Metric radio source'),
    'cm': ('Source radio (cm)', 'Centimetre radio source'),
    'mm': ('Source radio (mm)', 'Millimetre radio source'),
    'smm': ('Source sub-mm', 'Sub-millimetre source'),
    'HI': ('Source HI', 'HI source'),
    'rB': ('Sursaut radio', 'Radio burst'),
    'Mas': ('Maser', 'Maser'),
    'EmO': ('Objet à émission', 'Emission object'),
    'ev': ('Transient', 'Transient'),
    'blu': ('Source bleue', 'Blue source'),
    'mul': ('Objet multiple / mélange', 'Blend'),
    'err': ('Inexistant', 'Inexistent'),
    '?': ('Inconnu', 'Unknown'),
    'reg': ('Région', 'Region'),
    # Candidats et types possibles
    'Q?': ('Candidat quasar', 'QSO candidate'),
    'Bz?': ('Candidat blazar', 'Blazar candidate'),
    'BL?': ('Candidat BL Lac', 'BL Lac candidate'),
    'HS?': ('Candidat sous-naine chaude', 'Hot subdwarf candidate'),
    'Gl?': ('Candidat amas globulaire', 'Globular cluster candidate'),
    'G?': ('Candidat galaxie', 'Galaxy candidate'),
    'BD?': ('Candidat naine brune', 'Brown dwarf candidate'),
    'LM?': ('Candidat étoile de faible masse', 'Low-mass star candidate'),
    'SN?': ('Candidat supernova', 'Supernova candidate'),
    'BH?': ('Candidat trou noir', 'Black hole candidate'),
    'N*?': ('Candidat étoile à neutrons', 'Neutron star candidate'),
    'SR?': ('Candidat rémanent de supernova', 'SNR candidate'),
    'WD?': ('Candidat naine blanche', 'White dwarf candidate'),
    'of?': ('Candidat écoulement', 'Outflow candidate'),
    'BS?': ('Candidat traînarde bleue', 'Blue straggler candidate'),
    'pA?': ('Candidat post-AGB', 'Post-AGB candidate'),
    'Mi?': ('Candidat Mira', 'Mira candidate'),
    'V*?': ('Candidat étoile variable', 'Variable star candidate'),
    'LP?': ('Candidat variable longue période', 'Long-period variable candidate'),
    'AB?': ('Candidat AGB', 'AGB candidate'),
    's?b': ('Candidat supergéante bleue', 'Blue supergiant candidate'),
    's?y': ('Candidat supergéante jaune', 'Yellow supergiant candidate'),
    's?r': ('Candidat supergéante rouge', 'Red supergiant candidate'),
    'sg?': ('Candidat supergéante', 'Supergiant candidate'),
    'RB?': ('Candidat géante rouge', 'Red giant candidate'),
    'Ce?': ('Candidat céphéide', 'Cepheid candidate'),
    'RR?': ('Candidat RR Lyrae', 'RR Lyrae candidate'),
    'HB?': ('Candidat branche horizontale', 'Horizontal-branch candidate'),
    'Ae?': ('Candidat Ae', 'Ae star candidate'),
    'Be?': ('Candidat Be', 'Be star candidate'),
    'WR?': ('Candidat Wolf-Rayet', 'Wolf-Rayet candidate'),
    'OH?': ('Candidat OH/IR', 'OH/IR candidate'),
    'S*?': ('Candidat étoile S', 'S-type star candidate'),
    'C*?': ('Candidat étoile carbone', 'Carbon star candidate'),
    'TT?': ('Candidat T Tauri', 'T Tauri candidate'),
    'Y*?': ('Candidat objet jeune', 'YSO candidate'),
    'HX?': ('Candidat binaire X haute masse', 'HMXB candidate'),
    'LX?': ('Candidat binaire X faible masse', 'LMXB candidate'),
    'XB?': ('Candidat binaire X', 'X-ray binary candidate'),
    'No?': ('Candidat nova', 'Nova candidate'),
    'CV?': ('Candidat variable cataclysmique', 'Cataclysmic variable candidate'),
    'Sy?': ('Candidat symbiotique', 'Symbiotic star candidate'),
    'EB?': ('Candidat binaire à éclipse', 'Eclipsing binary candidate'),
    '**?': ('Candidat étoile double', 'Double star candidate'),
    'Gr?': ('Candidat groupe de galaxies', 'Group of galaxies candidate'),
    'C?G': ('Candidat galaxie d\'amas', 'Cluster galaxy candidate'),
    'SC?': ('Candidat superamas', 'Supercluster candidate'),
    'PN?': ('Candidat nébuleuse planétaire', 'Planetary nebula candidate'),
    'RC?': ('Candidat R CrB', 'R CrB candidate'),
    'LI?': ('Candidat image lentillée', 'Lensed image candidate'),
    'Le?': ('Candidat lentille', 'Lens candidate'),
    'LS?': ('Candidat système de lentille', 'Lens system candidate'),
    'UX?': ('Candidat ULX', 'ULX candidate'),
    'Pl': ('Planète', 'Planet'),
    'Pl?': ('Candidat planète', 'Planet candidate'),
    'AG?': ('Candidat noyau actif', 'AGN candidate'),
    # Alias / variantes parfois renvoyées par SIMBAD
    'GxyP': ('Partie de galaxie / Galaxie en paire', 'Part of galaxy / Galaxy in pair'),
    'GCl': ('Amas de galaxies', 'Cluster of galaxies'),
    'Neb': ('Nébuleuse', 'Nebula'),
    'sgr': ('Sursaut gamma à répétition', 'Soft gamma repeater'),
}

# Brèves descriptions explicatives pour chaque type SIMBAD — utilisées dans le manuel et le tooltip HTML.
# Format: code -> (description FR, description EN)
SIMBAD_OTYPE_DESCRIPTIONS = {
    # Étoiles et systèmes stellaires
    '*': ('Étoile générique, corps céleste qui produit sa propre lumière par fusion nucléaire.', 'Generic star, celestial body producing its own light through nuclear fusion.'),
    '**': ('Système de deux étoiles liées gravitationnellement.', 'System of two stars gravitationally bound.'),
    'V*': ('Étoile dont la luminosité varie avec le temps.', 'Star whose brightness varies over time.'),
    'Ir*': ('Variable irrégulière, amplitude et période non prédictibles.', 'Irregular variable, unpredictable amplitude and period.'),
    'RR*': ('Variable pulsante utilisée comme chandelle standard (distances).', 'Pulsating variable used as a standard candle.'),
    'Ce*': ('Variable pulsante utilisée pour mesurer les distances galactiques.', 'Pulsating variable used to measure galactic distances.'),
    'cC*': ('Céphéide jeune de population I, en disque galactique.', 'Young Population I Cepheid, in galactic disk.'),
    'WV*': ('Céphéide de population II, typique du halo.', 'Population II Cepheid, typical of halo.'),
    'dS*': ('Variable pulsante de la séquence principale.', 'Pulsating variable on the main sequence.'),
    'SX*': ('Variable à courte période, type RR Lyrae nain.', 'Short-period variable, dwarf RR Lyrae type.'),
    'gD*': ('Variable gamma Doradus, pulsations non radiales.', 'Gamma Doradus variable, non-radial pulsations.'),
    'RV*': ('Variable RV Tauri, supergéante avec minima alternés.', 'RV Tauri variable, supergiant with alternating minima.'),
    'Mi*': ('Variable Mira, géante rouge à grande amplitude.', 'Mira variable, red giant with large amplitude.'),
    'LP*': ('Variable à longue période, type Mira ou semi-régulière.', 'Long-period variable, Mira or semi-regular type.'),
    'Pu*': ('Étoile pulsante générique.', 'Generic pulsating star.'),
    'bC*': ('Variable beta Cephei, oscillations à courte période.', 'Beta Cephei variable, short-period oscillations.'),
    'a2*': ('Variable alpha² CVn, champs magnétiques forts.', 'Alpha² CVn variable, strong magnetic fields.'),
    'Ro*': ('Variable de rotation, taches stellaires.', 'Rotating variable, starspots.'),
    'BY*': ('Variable BY Dra, naine avec taches et activité.', 'BY Dra variable, dwarf with spots and activity.'),
    'RS*': ('Binaire proche avec activité chromosphérique intense.', 'Close binary with intense chromospheric activity.'),
    'El*': ('Binaire dont la forme ellipsoïdale varie la luminosité.', 'Binary whose ellipsoidal shape varies brightness.'),
    'EB*': ('Binaire dont les composantes s\'éclipsent mutuellement.', 'Binary whose components eclipse each other.'),
    'SB*': ('Binaire détectée par décalage Doppler des raies spectrales.', 'Binary detected by Doppler shift of spectral lines.'),
    'Sy*': ('Système symbiotique : géante rouge + naine blanche accrétante.', 'Symbiotic system: red giant + accreting white dwarf.'),
    'CV*': ('Binaire serrée : naine blanche accrétant matière, outbursts.', 'Close binary: white dwarf accreting matter, outbursts.'),
    'No*': ('Explosion thermonucléaire à la surface d\'une naine blanche.', 'Thermonuclear explosion on white dwarf surface.'),
    'XB*': ('Binaire émettant en rayons X, accrétion compacte.', 'X-ray emitting binary, compact accretion.'),
    'LXB': ('Binaire X : donateur de faible masse, disque d\'accrétion.', 'X-ray binary: low-mass donor, accretion disk.'),
    'HXB': ('Binaire X : donneur massif, vent stellaire ou Roche-lobe.', 'X-ray binary: massive donor, wind or Roche-lobe.'),
    'Psr': ('Étoile à neutrons en rotation rapide, faisceaux radio.', 'Rapidly rotating neutron star, radio beams.'),
    'N*': ('Résidu d\'une supernova, extrêmement dense.', 'Supernova remnant, extremely dense.'),
    'WD*': ('Résidu stellaire dégénéré après épuisement du combustible.', 'Degenerate stellar remnant after fuel exhaustion.'),
    'BD*': ('Objet intermédiaire entre étoile et planète, masse < 0.08 M☉.', 'Object between star and planet, mass < 0.08 M☉.'),
    'LM*': ('Étoile de faible masse, longue durée de vie.', 'Low-mass star, long lifetime.'),
    'HS*': ('Sous-naine chaude, stade post-RGB.', 'Hot subdwarf, post-RGB stage.'),
    'HB*': ('Étoile de la branche horizontale (hélium fusion).', 'Horizontal-branch star (helium fusion).'),
    'RG*': ('Géante rouge, phase d\'expansion après séquence principale.', 'Red giant, expansion phase after main sequence.'),
    'AB*': ('Étoile AGB, géante asymptotique en fin de vie.', 'AGB star, asymptotic giant late in life.'),
    'pA*': ('Post-AGB, transition vers nébuleuse planétaire.', 'Post-AGB, transition to planetary nebula.'),
    'sg*': ('Supergéante, luminosité très élevée.', 'Supergiant, very high luminosity.'),
    's*r': ('Supergéante rouge, très grande et froide.', 'Red supergiant, very large and cool.'),
    's*y': ('Supergéante jaune, phase intermédiaire.', 'Yellow supergiant, intermediate phase.'),
    's*b': ('Supergéante bleue, chaude et massive.', 'Blue supergiant, hot and massive.'),
    'WR*': ('Étoile Wolf-Rayet, vents stellaires intenses, stade final.', 'Wolf-Rayet star, intense stellar winds, final stage.'),
    'C*': ('Étoile carbone, rapport C/O > 1.', 'Carbon star, C/O ratio > 1.'),
    'S*': ('Étoile S, enrichie en zirconium et technétium.', 'S-type star, enriched in zirconium and technetium.'),
    'Pe*': ('Étoile à particularités chimiques, abondances anormales.', 'Chemically peculiar star, anomalous abundances.'),
    'Be*': ('Étoile Be, disque circumstellaire, raies en émission.', 'Be star, circumstellar disk, emission lines.'),
    'Ae*': ('Étoile Ae/Be de Herbig, jeune et circumstellaire.', 'Herbig Ae/Be star, young and circumstellar.'),
    'TT*': ('Étoile T Tauri, pré-séquence principale, en formation.', 'T Tauri star, pre-main sequence, forming.'),
    'Y*O': ('Objet stellaire jeune, protoétoile ou disque.', 'Young stellar object, protostar or disk.'),
    'Or*': ('Variable d\'Orion, jeune dans région de formation.', 'Orion variable, young in star-forming region.'),
    'RC*': ('Variable R Coronae Borealis, géante carbone à éclipses de poussière.', 'R CrB variable, carbon giant with dust eclipses.'),
    'OH*': ('Étoile OH/IR, géante évoluée avec maser OH.', 'OH/IR star, evolved giant with OH maser.'),
    'Em*': ('Étoile à raies d\'émission (Hα, etc.).', 'Star with emission lines (Hα, etc.).'),
    'PM*': ('Mouvement propre élevé, proche ou haute vélocité.', 'High proper motion, nearby or high velocity.'),
    'HV*': ('Étoile à haute vitesse spatiale, halo galactique.', 'High-velocity star, galactic halo.'),
    'BS*': ('Traînarde bleue, plus chaude que l\'âge de l\'amas.', 'Blue straggler, hotter than cluster age.'),
    'Ev*': ('Étoile en phase évoluée.', 'Evolved star.'),
    'Er*': ('Variable éruptive, flares ou accrétion.', 'Eruptive variable, flares or accretion.'),
    # Amas et associations
    'Cl*': ('Amas d\'étoiles, groupe lié gravitationnellement.', 'Star cluster, gravitationally bound group.'),
    'OpC': ('Amas ouvert, jeune, dans le plan galactique.', 'Open cluster, young, in galactic plane.'),
    'GlC': ('Amas globulaire, ancien, sphéroïdal.', 'Globular cluster, old, spheroidal.'),
    'As*': ('Association stellaire, groupe non lié mais co-mobile.', 'Stellar association, unbound but co-moving group.'),
    'St*': ('Courant stellaire, vestige de galaxie ou amas tidally disrupté.', 'Stellar stream, remnant of tidally disrupted galaxy or cluster.'),
    'MGr': ('Groupe mouvant, étoiles partageant un mouvement commun.', 'Moving group, stars sharing common motion.'),
    # Milieu interstellaire et nébuleuses
    'ISM': ('Milieu interstellaire, gaz et poussière entre les étoiles.', 'Interstellar medium, gas and dust between stars.'),
    'SFR': ('Région de formation stellaire active.', 'Active star-forming region.'),
    'HII': ('Région HII, gaz ionisé par étoiles chaudes.', 'HII region, gas ionized by hot stars.'),
    'Cld': ('Nuage interstellaire, gaz et poussière.', 'Interstellar cloud, gas and dust.'),
    'GNe': ('Nébuleuse galactique générique.', 'Generic galactic nebula.'),
    'RNe': ('Nébuleuse par réflexion, lumière réfléchie par poussière.', 'Reflection nebula, light reflected by dust.'),
    'MoC': ('Nuage moléculaire, H2 et autres molécules.', 'Molecular cloud, H2 and other molecules.'),
    'DNe': ('Nébuleuse obscure, poussière bloquant la lumière.', 'Dark nebula, dust blocking light.'),
    'glb': ('Globule, petit nuage dense.', 'Globule, small dense cloud.'),
    'cor': ('Cœur dense, proto-étoile en formation.', 'Dense core, protostar forming.'),
    'bub': ('Bulle, cavité créée par vent stellaire ou supernova.', 'Bubble, cavity from stellar wind or supernova.'),
    'CGb': ('Globule cométaire, forme allongée.', 'Cometary globule, elongated shape.'),
    'HVC': ('Nuage à haute vitesse, non corotant avec la Galaxie.', 'High-velocity cloud, not corotating with Galaxy.'),
    'SNR': ('Rémanent de supernova, onde de choc en expansion.', 'Supernova remnant, expanding shock wave.'),
    'sh': ('Coquille HI, structure d\'hydrogène neutre.', 'HI shell, neutral hydrogen structure.'),
    'flt': ('Filament, structure allongée de gaz ou poussière.', 'Filament, elongated gas or dust structure.'),
    'PN': ('Nébuleuse planétaire, enveloppe éjectée par géante.', 'Planetary nebula, envelope ejected by giant.'),
    'HH': ('Objet Herbig-Haro, jet de jeune étoile.', 'Herbig-Haro object, young star jet.'),
    'out': ('Écoulement, vent ou jet stellaire.', 'Outflow, stellar wind or jet.'),
    'PoC': ('Partie de nuage, sous-structure.', 'Part of cloud, substructure.'),
    # Galaxies et ensembles
    'G': ('Galaxie, système d\'étoiles, gaz et matière sombre.', 'Galaxy, system of stars, gas and dark matter.'),
    'LSB': ('Galaxie à faible brillance de surface.', 'Low surface brightness galaxy.'),
    'bCG': ('Galaxie compacte bleue, formation stellaire intense.', 'Blue compact galaxy, intense star formation.'),
    'SBG': ('Galaxie à sursaut stellaire, taux de formation élevé.', 'Starburst galaxy, high star formation rate.'),
    'H2G': ('Galaxie HII, régions de formation dominantes.', 'HII galaxy, dominant star-forming regions.'),
    'EmG': ('Galaxie à émission, raies en émission dominantes.', 'Emission-line galaxy.'),
    'AGN': ('Noyau actif, accrétion sur trou noir supermassif.', 'Active nucleus, accretion onto supermassive black hole.'),
    'SyG': ('Galaxie de Seyfert, AGN de luminosité modérée.', 'Seyfert galaxy, moderate luminosity AGN.'),
    'Sy1': ('Seyfert type 1, raies larges visibles.', 'Seyfert type 1, broad lines visible.'),
    'Sy2': ('Seyfert type 2, raies étroites seulement.', 'Seyfert type 2, narrow lines only.'),
    'rG': ('Galaxie radio, jets et lobes radio.', 'Radio galaxy, jets and radio lobes.'),
    'LIN': ('Galaxie LINER, émission de faible ionisation.', 'LINER galaxy, low-ionization emission.'),
    'QSO': ('Quasar, AGN très lumineux, lointain.', 'Quasar, very luminous distant AGN.'),
    'Bla': ('Blazar, jet orienté vers nous.', 'Blazar, jet oriented toward us.'),
    'BLL': ('Objet BL Lac, blazar sans raies.', 'BL Lac object, lineless blazar.'),
    'BiC': ('Galaxie la plus brillante d\'un amas.', 'Brightest cluster galaxy.'),
    'GiP': ('Galaxie dans une paire en interaction.', 'Galaxy in interacting pair.'),
    'GiG': ('Galaxie membre d\'un groupe.', 'Galaxy in group.'),
    'GiC': ('Galaxie membre d\'un amas.', 'Galaxy in cluster.'),
    'IG': ('Galaxie en interaction avec une autre.', 'Interacting galaxy.'),
    'PaG': ('Paire de galaxies liées gravitationnellement.', 'Pair of galaxies.'),
    'GrG': ('Groupe de galaxies.', 'Group of galaxies.'),
    'CGG': ('Groupe compact de galaxies, très proches.', 'Compact group of galaxies.'),
    'ClG': ('Galaxie d\'amas, membre d\'un amas.', 'Cluster galaxy.'),
    'SCG': ('Galaxie de superamas.', 'Supercluster galaxy.'),
    'vid': ('Vide cosmique, région de faible densité.', 'Cosmic void, low-density region.'),
    'PoG': ('Partie de galaxie, sous-structure.', 'Part of galaxy.'),
    # Lentilles et gravitation
    'gLe': ('Lentille gravitationnelle, courbe la lumière.', 'Gravitational lens, bends light.'),
    'LeG': ('Galaxie dont la lumière est lentillée.', 'Lensed galaxy.'),
    'Lev': ('Événement de microlentille, amplification temporaire.', 'Microlensing event.'),
    'LeQ': ('Quasar lentillé.', 'Lensed quasar.'),
    'LeI': ('Image lentillée.', 'Lensed image.'),
    'gLS': ('Système de lentille gravitationnelle.', 'Gravitational lens system.'),
    'GWE': ('Événement d\'onde gravitationnelle.', 'Gravitational wave event.'),
    'grv': ('Source gravitationnelle.', 'Gravitational source.'),
    # Supernovae et transients
    'SN*': ('Supernova, explosion d\'étoile en fin de vie.', 'Supernova, end-of-life stellar explosion.'),
    'gB': ('Sursaut gamma, explosion très énergétique.', 'Gamma-ray burst, very energetic explosion.'),
    'ULX': ('Source X ultra-lumineuse, au-dessus d\'Eddington.', 'Ultra-luminous X-ray source.'),
    # Sources spectrales
    'FIR': ('Source infrarouge lointain (> 30 µm).', 'Far infrared source (> 30 µm).'),
    'NIR': ('Source infrarouge proche (< 10 µm).', 'Near infrared source (< 10 µm).'),
    'IR': ('Source infrarouge.', 'Infrared source.'),
    'UV': ('Source ultraviolette.', 'UV source.'),
    'X': ('Source X.', 'X-ray source.'),
    'gam': ('Source gamma.', 'Gamma-ray source.'),
    'Rad': ('Source radio.', 'Radio source.'),
    'HI': ('Source hydrogène neutre 21 cm.', 'Neutral hydrogen 21 cm source.'),
    'Mas': ('Maser, émission stimulée moléculaire.', 'Maser, stimulated molecular emission.'),
    'EmO': ('Objet à émission.', 'Emission object.'),
    'ev': ('Transient, phénomène de courte durée.', 'Transient, short-duration phenomenon.'),
    'blu': ('Source bleue.', 'Blue source.'),
    'mul': ('Mélange ou objet multiple non résolu.', 'Blend or unresolved multiple object.'),
    'err': ('Inexistant, entrée erronée.', 'Inexistent, erroneous entry.'),
    '?': ('Type inconnu.', 'Unknown type.'),
    'reg': ('Région, zone du ciel.', 'Region, sky area.'),
    'Pl': ('Planète, corps en orbite autour d\'une étoile.', 'Planet, body orbiting a star.'),
}


def get_simbad_otype_description(otype, lang=None):
    """Retourne une brève description explicative pour un code otype SIMBAD. Utilisé pour tooltip HTML et manuel."""
    if not otype or not str(otype).strip():
        return ''
    code = str(otype).strip()
    if lang is None:
        lang = SYSTEM_LANGUAGE if SYSTEM_LANGUAGE == 'fr' else 'en'
    idx = 0 if lang == 'fr' else 1
    if code in SIMBAD_OTYPE_DESCRIPTIONS:
        return SIMBAD_OTYPE_DESCRIPTIONS[code][idx]
    for n in (3, 2, 1):
        if len(code) >= n and code[:n] in SIMBAD_OTYPE_DESCRIPTIONS:
            return SIMBAD_OTYPE_DESCRIPTIONS[code[:n]][idx]
    return ''


def format_simbad_otype(otype, lang=None):
    """Return human-readable label for a SIMBAD otype code. lang: 'fr', 'en', or None (use SYSTEM_LANGUAGE)."""
    if not otype or not str(otype).strip():
        return ''
    code = str(otype).strip()
    if lang is None:
        lang = SYSTEM_LANGUAGE if SYSTEM_LANGUAGE == 'fr' else 'en'
    idx = 0 if lang == 'fr' else 1
    if code in SIMBAD_OTYPE_LABELS:
        return SIMBAD_OTYPE_LABELS[code][idx]
    # Fallback: try first 2 or 3 chars (e.g. GxyP -> try Gxy, Gx, G)
    for n in (3, 2, 1):
        if len(code) >= n and code[:n] in SIMBAD_OTYPE_LABELS:
            return SIMBAD_OTYPE_LABELS[code[:n]][idx]
    return code


def _query_simbad_single(name, timeout=10):
    """Query SIMBAD for one object; returns (main_id, info_dict) or (None, None) on failure.
    info_dict includes: main_id, otype, ra, dec, all_ids, distance_pc, common_name.
    """
    if not SIMBAD_AVAILABLE:
        return None, None
    try:
        import warnings
        import numpy.ma as ma
        
        # Helper to safely convert masked/None values to float (suppresses warnings)
        def safe_float(val):
            if val is None:
                return None
            try:
                if hasattr(val, 'mask') and ma.is_masked(val):
                    return None
                if isinstance(val, ma.core.MaskedConstant):
                    return None
                # Suppress warnings when converting masked values
                with warnings.catch_warnings():
                    warnings.filterwarnings('ignore', message='.*converting a masked element.*')
                    warnings.filterwarnings('ignore', category=UserWarning)
                    f = float(val)
                return f if f == f else None  # Return None if NaN
            except (TypeError, ValueError, AttributeError):
                return None
        
        simbad = Simbad()
        simbad.add_votable_fields('otype')
        # Use rvz_redshift instead of deprecated z_value
        # Suppress deprecation warnings when adding fields
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=DeprecationWarning, module='astroquery')
            for extra in ('parallax', 'rvz_redshift', 'velocity'):
                try:
                    simbad.add_votable_fields(extra)
                except Exception:
                    pass
        
        # Suppress NoResultsWarning and masked value warnings (normal when SIMBAD doesn't find a match or has missing data)
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='.*NoResultsWarning.*')
            warnings.filterwarnings('ignore', category=UserWarning, module='astroquery')
            warnings.filterwarnings('ignore', message='.*converting a masked element.*')
            result = simbad.query_object(name.strip())
        if result is None or len(result) == 0:
            return None, None
        row = result[0]
        col = {c.upper(): c for c in result.colnames}
        main_id = str(row[col['MAIN_ID']]).strip() if 'MAIN_ID' in col else None
        if not main_id:
            return None, None
        # Parse RA/DEC — SIMBAD may return sexagesimal strings or floats
        def _parse_ra(val):
            """Convert RA to degrees (handles 'HH MM SS.ss' or numeric)"""
            f = safe_float(val)
            if f is not None:
                return f
            try:
                s = str(val).strip()
                parts = s.split()
                if len(parts) == 3:
                    h, m, sec = float(parts[0]), float(parts[1]), float(parts[2])
                    return (h + m / 60.0 + sec / 3600.0) * 15.0  # hours → degrees
                elif len(parts) == 1 and ':' in s:
                    parts = s.split(':')
                    h, m, sec = float(parts[0]), float(parts[1]), float(parts[2])
                    return (h + m / 60.0 + sec / 3600.0) * 15.0
            except Exception:
                pass
            return None

        def _parse_dec(val):
            """Convert DEC to degrees (handles '+DD MM SS.ss' or numeric)"""
            f = safe_float(val)
            if f is not None:
                return f
            try:
                s = str(val).strip()
                sign = -1 if s.startswith('-') else 1
                s = s.lstrip('+-')
                parts = s.split()
                if len(parts) == 3:
                    d, m, sec = float(parts[0]), float(parts[1]), float(parts[2])
                    return sign * (d + m / 60.0 + sec / 3600.0)
                elif len(parts) == 1 and ':' in s:
                    parts = s.split(':')
                    d, m, sec = float(parts[0]), float(parts[1]), float(parts[2])
                    return sign * (d + m / 60.0 + sec / 3600.0)
            except Exception:
                pass
            return None

        info = {
            'main_id': main_id,
            'otype': str(row[col['OTYPE']]).strip() if 'OTYPE' in col else '',
            'ra': _parse_ra(row[col['RA']]) if 'RA' in col else None,
            'dec': _parse_dec(row[col['DEC']]) if 'DEC' in col else None,
            'all_ids': [],
            'distance_pc': None,
            'distance_ly': None,
            'common_name': None,
            'redshift': None,
            'rv_km_s': None,
        }
        # Parallax in mas -> distance in pc (d = 1000/plx for plx in mas)
        plx_col = col.get('PLX_VALUE') or col.get('PLX')
        if plx_col:
            plx = safe_float(row[plx_col])
            if plx is not None and plx > 0:
                info['distance_pc'] = 1000.0 / plx
                # 1 pc = 3.26156 ly
                info['distance_ly'] = info['distance_pc'] * 3.26156
        
        # Redshift (z) and radial velocity (km/s) — try several possible column names
        # Priority: rvz_redshift (new name) then old names
        for z_key in ('RVZ_REDSHIFT', 'Z_VALUE', 'Z', 'REDSHIFT'):
            z_col = col.get(z_key)
            if z_col is not None:
                z = safe_float(row[z_col])
                if z is not None:
                    info['redshift'] = z
                    break
        
        # If no redshift found, try radial velocity and convert
        if info.get('redshift') is None:
            rv_col = col.get('RV_VALUE') or col.get('RVZ_RADVEL') or col.get('RV') or col.get('VELOCITY')
            if rv_col:
                rv = safe_float(row[rv_col])
                if rv is not None and abs(rv) < 3e5:
                    # Radial velocity in km/s; convert to redshift for small v: z ≈ v/c (c = 299792.458 km/s)
                    info['rv_km_s'] = rv
                    info['redshift'] = rv / 299792.458
        # Suppress warnings for query_objectids too
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='.*NoResultsWarning.*')
            warnings.filterwarnings('ignore', category=UserWarning, module='astroquery')
            warnings.filterwarnings('ignore', message='.*converting a masked element.*')
            ids_table = Simbad.query_objectids(name.strip())
        if ids_table is not None and len(ids_table) > 0:
            id_col = 'ID' if 'ID' in ids_table.colnames else (ids_table.colnames[0] if ids_table.colnames else None)
            if id_col:
                all_ids = [str(x).strip() for x in ids_table[id_col]]
                info['all_ids'] = all_ids
                # Prefer "NAME ..." as common name (e.g. "NAME Whirlpool Galaxy" -> "Whirlpool Galaxy")
                for sid in all_ids:
                    if sid.upper().startswith('NAME '):
                        info['common_name'] = sid[5:].strip()
                        break
        return main_id, info
    except Exception:
        return None, None


def query_simbad_for_targets(target_names, check_abort=None):
    """
    Resolve target names via SIMBAD. Returns mappings to detect duplicate targets
    (same object, different catalog names) and to attach object type/coordinates.
    Respects SIMBAD rate limit (~1 query every 0.5–1 s).
    Returns:
        name_to_canonical: dict target_name -> main_id (SIMBAD canonical name)
        canonical_to_info: dict main_id -> {main_id, otype, ra, dec, all_ids}
    """
    name_to_canonical = {}
    canonical_to_info = {}
    if not SIMBAD_AVAILABLE or not target_names:
        return name_to_canonical, canonical_to_info
    # Skip calibration / unknown
    skip_upper = {'UNKNOWN', 'BIAS', 'DARK', 'FLAT', 'CALIBRATION', 'FLATWIZARD', ''}
    to_query = []
    for n in target_names:
        n_clean = (n or '').strip()
        if not n_clean or n_clean.upper() in skip_upper:
            continue
        to_query.append(n_clean)
    if not to_query:
        return name_to_canonical, canonical_to_info
    for i, name in enumerate(to_query):
        if check_abort and callable(check_abort) and check_abort():
            break
        main_id, info = _query_simbad_single(name, timeout=10)
        if main_id and info:
            name_to_canonical[name] = main_id
            if main_id not in canonical_to_info:
                canonical_to_info[main_id] = info
        if i < len(to_query) - 1:
            time.sleep(0.6)
    return name_to_canonical, canonical_to_info


def merge_targets_by_simbad(data_by_target, name_to_canonical, canonical_to_info):
    """
    Merge targets that resolve to the same SIMBAD object (e.g. M31 and NGC 224).
    Uses the same merge logic as group_normalized_targets. Attaches simbad_info to merged targets.
    """
    if not name_to_canonical:
        return data_by_target
    # Build groups by canonical id
    canonical_groups = {}
    unmapped = {}
    for target_name, target_data in data_by_target.items():
        canonical = name_to_canonical.get(target_name)
        if canonical is None:
            unmapped[target_name] = target_data
            continue
        if canonical not in canonical_groups:
            canonical_groups[canonical] = target_data.copy()
            canonical_groups[canonical]['original_names'] = [target_name]
            canonical_groups[canonical]['simbad_info'] = canonical_to_info.get(canonical, {})
        else:
            existing = canonical_groups[canonical]
            existing['files'].extend(target_data['files'])
            for filter_name, time_list in target_data['time_by_filter'].items():
                if filter_name in existing['time_by_filter']:
                    existing['time_by_filter'][filter_name].extend(time_list)
                else:
                    existing['time_by_filter'][filter_name] = time_list.copy()
            if isinstance(existing['telescopes'], set):
                existing['telescopes'].update(target_data['telescopes'])
            else:
                existing['telescopes'] = list(set(existing['telescopes'] + target_data['telescopes']))
            if isinstance(existing['instruments'], set):
                existing['instruments'].update(target_data['instruments'])
            else:
                existing['instruments'] = list(set(existing['instruments'] + target_data['instruments']))
            if isinstance(existing['dates'], set):
                existing['dates'].update(target_data['dates'])
            else:
                existing['dates'] = list(set(existing['dates'] + target_data['dates']))
            if 'files_by_date' in target_data:
                if 'files_by_date' not in existing:
                    existing['files_by_date'] = {}
                for date, date_data in target_data['files_by_date'].items():
                    if date in existing['files_by_date']:
                        ed = existing['files_by_date'][date]
                        ed['files'].extend(date_data['files'])
                        ed['total_time'] += date_data['total_time']
                        for fn, tl in date_data['time_by_filter'].items():
                            if fn in ed['time_by_filter']:
                                ed['time_by_filter'][fn].extend(tl)
                            else:
                                ed['time_by_filter'][fn] = tl.copy()
                        for fn, exp_details in date_data['exposure_details'].items():
                            if fn in ed['exposure_details']:
                                for et, cnt in exp_details.items():
                                    ed['exposure_details'][fn][et] = ed['exposure_details'][fn].get(et, 0) + cnt
                            else:
                                ed['exposure_details'][fn] = exp_details.copy()
                    else:
                        existing['files_by_date'][date] = date_data.copy()
            for key in ('received_light', 'adu_samples', 'adu_counter_by_filter'):
                if key not in target_data:
                    continue
                if key not in existing:
                    existing[key] = {} if key != 'adu_counter_by_filter' else {}
                if key == 'adu_counter_by_filter':
                    for fn, cnt in target_data[key].items():
                        existing[key][fn] = existing[key].get(fn, 0) + cnt
                else:
                    for fn, val in target_data[key].items():
                        if isinstance(val, list):
                            existing[key].setdefault(fn, []).extend(val)
                        else:
                            existing[key][fn] = val
            existing['original_names'].append(target_name)
    for t in canonical_groups.values():
        if isinstance(t.get('telescopes'), set):
            t['telescopes'] = list(t['telescopes'])
        if isinstance(t.get('instruments'), set):
            t['instruments'] = list(t['instruments'])
        if isinstance(t.get('dates'), set):
            t['dates'] = list(t['dates'])
    result = {}
    result.update(unmapped)
    for canonical, data in canonical_groups.items():
        result[canonical] = data
    return result


def group_mosaic_panels(data_by_target):
    """Groups mosaic panels under a unified mosaic name"""
    mosaic_groups = {}
    non_mosaic_targets = {}
    
    for target_name, target_data in data_by_target.items():
        base_object, panel_number = detect_mosaic_panel(target_name)
        
        if base_object and panel_number:
            # This is a mosaic panel
            mosaic_name = get_mosaic_name(base_object)
            
            if mosaic_name not in mosaic_groups:
                mosaic_groups[mosaic_name] = {
                    'files': [],
                    'telescopes': set(),
                    'instruments': set(),
                    'panels': {},
                    'total_time': 0
                }
            
            # Add panel information
            # Calculate total time from time_by_filter if available, otherwise from files
            panel_total_time = 0
            if 'time_by_filter' in target_data:
                for time_list in target_data['time_by_filter'].values():
                    panel_total_time += sum(time_list)
            else:
                # Fallback: try to calculate from files if they have exposure time info
                for file_info in target_data['files']:
                    if isinstance(file_info, dict) and 'info' in file_info:
                        info = file_info['info']
                        if 'exposure_time' in info and info['exposure_time'] is not None:
                            panel_total_time += info['exposure_time'] or 0
            
            mosaic_groups[mosaic_name]['panels'][panel_number] = {
                'original_name': target_name,
                'files': target_data['files'],
                'total_time': panel_total_time
            }
            
            # Merge data
            mosaic_groups[mosaic_name]['files'].extend(target_data['files'])
            mosaic_groups[mosaic_name]['telescopes'].update(target_data['telescopes'])
            mosaic_groups[mosaic_name]['instruments'].update(target_data['instruments'])
            mosaic_groups[mosaic_name]['total_time'] += panel_total_time
            
        else:
            # This is not a mosaic panel
            non_mosaic_targets[target_name] = target_data
    
    # Convert sets to lists for consistency
    for mosaic_data in mosaic_groups.values():
        mosaic_data['telescopes'] = list(mosaic_data['telescopes'])
        mosaic_data['instruments'] = list(mosaic_data['instruments'])
    
    # Combine mosaic groups and non-mosaic targets
    result = {}
    result.update(non_mosaic_targets)
    
    for mosaic_name, mosaic_data in mosaic_groups.items():
        # Create a complete data structure for the mosaic
        mosaic_result = {
            'files': mosaic_data['files'],
            'telescopes': mosaic_data['telescopes'],
            'instruments': mosaic_data['instruments'],
            'panels': mosaic_data['panels'],
            'time_by_filter': defaultdict(list),
            'received_light': defaultdict(list),
            'adu_samples': defaultdict(list),
            'dates': [],
            'apertures': [],
            'diameters': [],
            'focal_lengths': [],
            'coordinates': []
        }
        
        # Merge time_by_filter from all panels
        for panel_data in mosaic_data['panels'].values():
            for file_info in panel_data['files']:
                if isinstance(file_info, dict) and 'info' in file_info:
                    info = file_info['info']
                    if 'filter' in info and 'exposure_time' in info and info['exposure_time'] is not None:
                        mosaic_result['time_by_filter'][info['filter']].append(info['exposure_time'] or 0)
                    if 'date_obs' in info:
                        mosaic_result['dates'].append(info['date_obs'])
                    if 'f_number' in info:
                        mosaic_result['apertures'].append(info['f_number'])
                    if 'diameter_mm' in info:
                        mosaic_result['diameters'].append(info['diameter_mm'])
                    if 'focal_length_mm' in info:
                        mosaic_result['focal_lengths'].append(info['focal_length_mm'])
                    if 'ra' in info and 'dec' in info and info['ra'] and info['dec']:
                        mosaic_result['coordinates'].append((info['ra'], info['dec']))
        
        result[mosaic_name] = mosaic_result
    
    return result

def extract_date_from_file(file_info):
    """Extracts date from file information"""
    import re
    from datetime import datetime
    
    # Try to extract date from filename first
    if 'filename' in file_info:
        filename = file_info['filename']
        # Look for date patterns like 2025-08-05, 2025/08/05, 20250805
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',  # 2025-08-05
            r'(\d{4}/\d{2}/\d{2})',  # 2025/08/05
            r'(\d{4})(\d{2})(\d{2})',  # 20250805
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, filename)
            if match:
                if len(match.groups()) == 1:
                    # Format like 2025-08-05 or 2025/08/05
                    return match.group(1).replace('/', '-')
                else:
                    # Format like 20250805
                    year, month, day = match.groups()
                    return f"{year}-{month}-{day}"
    
    # Try to extract date from FITS header info
    if 'info' in file_info and 'DATE-OBS' in file_info['info']:
        date_obs = file_info['info']['DATE-OBS']
        # Extract just the date part (YYYY-MM-DD)
        if isinstance(date_obs, str):
            date_part = date_obs.split('T')[0]  # Remove time part
            return date_part
    
    # Fallback: use current date
    return datetime.now().strftime('%Y-%m-%d')

def group_files_by_date(data):
    """Groups files by date for night-by-night analysis"""
    files_by_date = {}
    
    # Check if we have files_by_date structure (new approach)
    if 'files_by_date' in data:
        # Use the new grouped data structure
        for date_str, date_data in data['files_by_date'].items():
            # Count files by summing the counts from time_by_filter
            total_files = sum(len(time_list) for time_list in date_data['time_by_filter'].values())
            
            files_by_date[date_str] = {
                'files': [],  # Don't store actual files to avoid duplication
                'total_files': total_files,  # Use calculated count
                'total_time': date_data['total_time'],
                'filters': {},
                'exposure_details': date_data.get('exposure_details', {})  # Include exposure details
            }
            
            # Populate filters from time_by_filter for this date
            for filter_name, time_list in date_data['time_by_filter'].items():
                files_by_date[date_str]['filters'][filter_name] = {
                    'time': sum(time_list),
                    'count': len(time_list)
                }
                
    else:
        # Fallback to old approach (single session)
        date_str = "All Observations"
        total_files = sum(len(time_list) for time_list in data['time_by_filter'].values())
        
        files_by_date[date_str] = {
            'files': [],  # Don't store actual files to avoid duplication
            'total_files': total_files,  # Use calculated count
            'total_time': sum(sum(times) for times in data['time_by_filter'].values()),
            'filters': {}
        }
        
        # Populate filters from time_by_filter data
        for filter_name, time_list in data['time_by_filter'].items():
            files_by_date[date_str]['filters'][filter_name] = {
                'time': sum(time_list),
                'count': len(time_list)
            }
    
    return files_by_date

def build_files_by_date_from_file_list(files_list):
    """Builds files_by_date from a list of file dicts (same logic as LaTeX).
    Each file dict has 'info' with observation_date, filter, exposure_time, type.
    Ensures one entry per normalized night (YYYY-MM-DD night) and same totals as LaTeX."""
    files_by_date = {}
    for file_data in (files_list or []):
        if not isinstance(file_data, dict):
            continue
        info = file_data.get('info')
        if not info or info.get('type') != 'LIGHT':
            continue
        file_date = info.get('observation_date') or info.get('date_obs') or ''
        file_date = normalize_night_date(file_date)
        if not file_date:
            continue
        file_filter = (info.get('filter') or '').strip() or 'Unknown'
        exposure_time = info.get('exposure_time') or info.get('exptime') or 0
        try:
            exposure_time = float(exposure_time) if exposure_time is not None else 0
        except (TypeError, ValueError):
            exposure_time = 0
        if file_date not in files_by_date:
            files_by_date[file_date] = {
                'time_by_filter': {},
                'total_time': 0,
                'exposure_details': {},
                'total_files': 0,
                'filters': {}
            }
        if file_filter not in files_by_date[file_date]['time_by_filter']:
            files_by_date[file_date]['time_by_filter'][file_filter] = []
        files_by_date[file_date]['time_by_filter'][file_filter].append(exposure_time)
        files_by_date[file_date]['total_time'] += exposure_time
        if file_filter not in files_by_date[file_date]['exposure_details']:
            files_by_date[file_date]['exposure_details'][file_filter] = {}
        exp_key = round(exposure_time, 1) if exposure_time else 0
        files_by_date[file_date]['exposure_details'][file_filter][exp_key] = \
            files_by_date[file_date]['exposure_details'][file_filter].get(exp_key, 0) + 1
    for date_str, date_data in files_by_date.items():
        date_data['total_files'] = sum(len(t) for t in date_data['time_by_filter'].values())
        date_data['filters'] = {
            fn: {'count': len(times), 'time': sum(times), 'total_time': sum(times)}
            for fn, times in date_data['time_by_filter'].items()
        }
    return files_by_date

def extract_observation_date(file_path, additional_info):
    """Extracts observation date from FITS file"""
    import re
    from datetime import datetime, timedelta
    
    # Try to extract date and time from filename first
    filename = file_path.name
    date_time_patterns = [
        r'(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})',  # 2025-08-05_20-30-15
        r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})',  # 20250805_203015
    ]
    
    for pattern in date_time_patterns:
        match = re.search(pattern, filename)
        if match:
            groups = match.groups()
            if len(groups) == 6:
                year, month, day, hour, minute, second = groups
                obs_datetime = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
                night_date = get_astronomical_night_date(obs_datetime)
                
                
                return night_date
    
    # Try to extract just date from filename
    date_patterns = [
        r'(\d{4}-\d{2}-\d{2})',  # 2025-08-05
        r'(\d{4}/\d{2}/\d{2})',  # 2025/08/05
        r'(\d{4})(\d{2})(\d{2})',  # 20250805
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, filename)
        if match:
            if len(match.groups()) == 1:
                date_str = match.group(1).replace('/', '-')
            else:
                year, month, day = match.groups()
                date_str = f"{year}-{month}-{day}"
            
            # Assume evening observation (20:00) if no time specified
            obs_datetime = datetime.strptime(date_str, '%Y-%m-%d').replace(hour=20, minute=0, second=0)
            return get_astronomical_night_date(obs_datetime)
    
    # Try to extract date and time from FITS header
    if 'DATE-OBS' in additional_info:
        date_obs = additional_info['DATE-OBS']
        if isinstance(date_obs, str):
            try:
                # Parse ISO format: 2025-08-05T20:30:15.123
                if 'T' in date_obs:
                    date_part, time_part = date_obs.split('T')
                    obs_datetime = datetime.fromisoformat(date_obs.replace('Z', ''))
                    return get_astronomical_night_date(obs_datetime)
                else:
                    # Just date
                    obs_datetime = datetime.strptime(date_obs, '%Y-%m-%d').replace(hour=20, minute=0, second=0)
                    return get_astronomical_night_date(obs_datetime)
            except Exception:
                pass
    
    # Fallback to current date
    return get_astronomical_night_date(datetime.now())

def get_astronomical_night_date(obs_datetime):
    """Determines the astronomical night date based on observation time.
    Astronomical nights are separated at noon (12:00) instead of midnight.
    A night from Aug 1 evening to Aug 2 morning is considered 'Aug 1 night'."""
    
    # Debug: Print observation datetime and resulting night
    night_date = None
    
    # If observation is before noon (12:00), it belongs to the previous night
    if obs_datetime.hour < 12:
        # This is morning observation, belongs to previous night
        previous_day = obs_datetime - timedelta(days=1)
        night_date = f"{previous_day.strftime('%Y-%m-%d')} night"
    else:
        # This is evening observation, belongs to current night
        night_date = f"{obs_datetime.strftime('%Y-%m-%d')} night"
    
    
    return night_date

def normalize_night_date(date_str):
    """Normalizes a date string to standard format 'YYYY-MM-DD night'.
    Handles various input formats and ensures consistent date representation."""
    from datetime import datetime
    
    if not date_str or str(date_str).strip() == '' or str(date_str).strip().upper() == 'UNKNOWN':
        return None
    
    date_str = str(date_str).strip()
    
    # If already in correct format "YYYY-MM-DD night", return as is
    if date_str.endswith(' night'):
        date_part = date_str.replace(' night', '').strip()
        try:
            # Validate format
            datetime.strptime(date_part, '%Y-%m-%d')
            return date_str
        except Exception:
            pass
    
    # Try to extract date part from various formats
    date_part = date_str
    
    # Remove 'night' suffix if present
    if ' night' in date_part:
        date_part = date_part.replace(' night', '').strip()
    
    # Extract date part if ISO format with time (YYYY-MM-DDTHH:MM:SS)
    if 'T' in date_part:
        date_part = date_part.split('T')[0]
    
    # Try to parse as YYYY-MM-DD
    try:
        parsed_date = datetime.strptime(date_part, '%Y-%m-%d')
        return f"{parsed_date.strftime('%Y-%m-%d')} night"
    except Exception:
        pass
    
    # Try other date formats
    date_patterns = [
        ('%Y/%m/%d', '%Y-%m-%d'),
        ('%Y%m%d', '%Y-%m-%d'),
    ]
    
    for pattern, output_format in date_patterns:
        try:
            parsed_date = datetime.strptime(date_part, pattern)
            return f"{parsed_date.strftime(output_format)} night"
        except Exception:
            continue
    
    # If all parsing fails, return None
    return None

def format_night_display(date_str):
    """Converts date string to readable night format.
    Example: '2025-04-27 night' -> 'Night 27th to 28th April 2025'"""
    from datetime import datetime
    
    # Remove 'night' suffix and parse date
    date_part = date_str.replace(' night', '')
    # Extract only the date part (handle ISO format with time)
    if 'T' in date_part:
        date_part = date_part.split('T')[0]
    night_date = datetime.strptime(date_part, '%Y-%m-%d')
    
    # Calculate next day for the "to" part
    next_day = night_date + timedelta(days=1)
    
    # Format with ordinal day (using LaTeX superscript)
    def get_ordinal(day):
        if 10 <= day % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
        return f"{day}$^{{{suffix}}}$"
    
    # Get month name
    month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
    
    return f"Night {get_ordinal(night_date.day)} to {get_ordinal(next_day.day)} {month_names[night_date.month-1]} {night_date.year}"

def extract_date_from_filename(filename):
    """Extracts date from filename"""
    import re
    
    # Look for date patterns in filename
    date_patterns = [
        r'(\d{4}-\d{2}-\d{2})',  # 2025-08-05
        r'(\d{4}/\d{2}/\d{2})',  # 2025/08/05
        r'(\d{4})(\d{2})(\d{2})',  # 20250805
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, filename)
        if match:
            if len(match.groups()) == 1:
                return match.group(1).replace('/', '-')
            else:
                year, month, day = match.groups()
                return f"{year}-{month}-{day}"
    
    # Fallback to current date
    from datetime import datetime
    return datetime.now().strftime('%Y-%m-%d')

def escape_filename_for_latex(filename):
    """Escapes specifically filenames for LaTeX"""
    if not filename:
        return ""
    
    # Replace underscores and other problematic characters
    result = filename.replace('_', '\\_')
    result = result.replace('&', '\\&')
    result = result.replace('#', '\\#')
    result = result.replace('$', '\\$')
    result = result.replace('%', '\\%')
    result = result.replace('^', '\\textasciicircum{}')
    result = result.replace('~', '\\textasciitilde{}')
    result = result.replace('{', '\\{')
    result = result.replace('}', '\\}')
    
    return result

def load_configuration():
    """Load configuration from JSON file"""
    global BIAS_DARK_PATH, SENSORS_DATABASE, TELESCOPES_DATABASE
    
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Remove personal path fields if present
                if 'chemin_bias_dark' in config:
                    pass  # Ignore deprecated personal path
                
                # Load sensor database if available
                if 'sensors_database' in config:
                    # Merge with existing database (keep default values)
                    for sensor_name, characteristics in config['sensors_database'].items():
                        if sensor_name not in SENSORS_DATABASE or sensor_name != 'default':
                            SENSORS_DATABASE[sensor_name] = characteristics
                    print(f"Sensor database loaded ({len(config['sensors_database'])} sensors)")
                
                # Load telescope database if available
                if 'telescopes_database' in config:
                    # Merge with existing database (keep default values)
                    for telescope_name, characteristics in config['telescopes_database'].items():
                        if telescope_name not in TELESCOPES_DATABASE or telescope_name != 'default':
                            TELESCOPES_DATABASE[telescope_name] = characteristics
                    print(f"Telescope database loaded ({len(config['telescopes_database'])} telescopes)")
                
                return True
    except Exception as e:
        print(f"Error loading configuration: {e}")
    
    return False

def save_configuration():
    """Save configuration to JSON file"""
    try:
        config = {
            'date_sauvegarde': datetime.now().isoformat(),
            'sensors_database': SENSORS_DATABASE,
            'telescopes_database': TELESCOPES_DATABASE
        }
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"Configuration saved to {CONFIG_FILE}")
        return True
    except Exception as e:
        print(f"Error saving configuration: {e}")
        return False

def ask_calibration_path():
    """Interactively asks for the path to calibration files"""
    global BIAS_DARK_PATH
    
    print("\n" + "="*80)
    print("CALIBRATION FILES CONFIGURATION")
    print("="*80)
    print("The program needs BIAS and DARK files for advanced SNR calculations.")
    print("These files must be in .fits/.fits.fz/.xisf/.xifs/.xif format and contain calibration images.")
    
    # Check if current path exists
    if BIAS_DARK_PATH and os.path.exists(BIAS_DARK_PATH):
        print(f"Current path: {BIAS_DARK_PATH}")
        response = input("Do you want to use this path? (y/n): ").strip().lower()
        if response in ['y', 'yes', 'o', 'oui']:
            print(f"Using existing path: {BIAS_DARK_PATH}")
            return
    
    while True:
        path = input("\nEnter the path to the folder containing your BIAS/DARK files\n   (ex: C:\\Path\\To\\Calibration or /home/username/astro/calibration): ").strip()
        
        if not path:
            print("Path cannot be empty.")
            continue
        
        # Check if path exists
        if not os.path.exists(path):
            print(f"Path '{path}' does not exist.")
            response = input("Do you want to create this folder? (y/n): ").strip().lower()
            if response in ['y', 'yes', 'o', 'oui']:
                try:
                    os.makedirs(path, exist_ok=True)
                    print(f"Folder created: {path}")
                except Exception as e:
                    print(f"Cannot create folder: {e}")
                    continue
            else:
                continue
        
        # Check if there are .fits files in the folder
        # OPTIMIZED: Use os.walk for single-pass traversal (much faster than multiple rglob calls)
        fits_extensions = ('.fit', '.fits', '.fits.fz', '.xisf', '.xifs', '.xif')
        fits_files = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.lower().endswith(fits_extensions):
                    fits_files.append(Path(root) / file)
        # Remove compressed duplicates (prefer .fits over .fits.fz)
        fits_files = remove_compressed_duplicates(fits_files)
        if not fits_files:
            print(f"No .fits/.fits.fz/.xisf/.xifs/.xif files found in '{path}'")
            response = input("Continue anyway? (y/n): ").strip().lower()
            if response not in ['y', 'yes', 'o', 'oui']:
                continue
        else:
            print(f"{len(fits_files)} .fits/.fits.fz/.xisf/.xifs/.xif files found in folder")
        
        BIAS_DARK_PATH = path
        print(f"Calibration path configured: {BIAS_DARK_PATH}")
        
        # Save configuration
        if save_configuration():
            print("Configuration saved for next use")
        
        break

def ask_sensor_characteristics(device_name):
    """Interactively asks for sensor characteristics if not found in database"""
    print(f"\n" + "="*80)
    print(f"SENSOR CONFIGURATION: {device_name}")
    print("="*80)
    print("Sensor not found in database.")
    print("Please provide its technical characteristics.")
    
    while True:
        try:
            print(f"\nSensor characteristics for '{device_name}':")
            
            gain = input("   Gain (e-/ADU, ex: 0.5): ").strip()
            if not gain:
                print("Gain is required.")
                continue
            gain = float(gain)
            
            read_noise = input("   Read noise (e-, ex: 3.5): ").strip()
            if not read_noise:
                print("Read noise is required.")
                continue
            read_noise = float(read_noise)
            
            full_well = input("   Full well (e-, ex: 50000): ").strip()
            if not full_well:
                print("Full well is required.")
                continue
            full_well = float(full_well)
            
            pixel_size = input("   Pixel size (μm, ex: 3.76): ").strip()
            if not pixel_size:
                print("Pixel size is required.")
                continue
            pixel_size = float(pixel_size)
            
            quantum_efficiency = input("   Quantum efficiency (0-1, ex: 0.85): ").strip()
            if not quantum_efficiency:
                print("Quantum efficiency is required.")
                continue
            quantum_efficiency = float(quantum_efficiency)
            
            if not (0 <= quantum_efficiency <= 1):
                print("Quantum efficiency must be between 0 and 1.")
                continue
            
            dark_current = input("   Dark current (e-/pixel/sec, ex: 0.01): ").strip()
            if not dark_current:
                dark_current = 0.01  # default value
            else:
                dark_current = float(dark_current)
            
            # Create sensor characteristics
            characteristics = {
                'gain': gain,
                'read_noise': read_noise,
                'full_well': full_well,
                'pixel_size': pixel_size,
                'quantum_efficiency': quantum_efficiency,
                'dark_current': dark_current
            }
            
            # Display summary
            print(f"\nCharacteristics summary:")
            print(f"   Gain: {gain} e-/ADU")
            print(f"   Read noise: {read_noise} e-")
            print(f"   Full well: {full_well} e-")
            print(f"   Pixel size: {pixel_size} μm")
            print(f"   Quantum efficiency: {quantum_efficiency:.2f}")
            print(f"   Dark current: {dark_current} e-/pixel/sec")
            
            confirmation = input("\nAre these values correct? (y/n): ").strip().lower()
            if confirmation in ['y', 'yes', 'o', 'oui']:
                # Add to database
                SENSORS_DATABASE[device_name] = characteristics
                print(f"✅ Sensor '{device_name}' added to database")
                
                # Save updated configuration
                save_configuration()
                
                return characteristics
            else:
                print("🔄 Entry cancelled, please start over.")
                
        except ValueError as e:
            print(f"❌ Input error: {e}")
            print("Please enter valid numeric values.")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")

def ask_telescope_characteristics(telescope_name):
    """Interactively asks for telescope characteristics if not found in database"""
    print(f"\n" + "="*80)
    print(f"TELESCOPE CONFIGURATION: {telescope_name}")
    print("="*80)
    print("Telescope not found in database.")
    print("Please provide its technical characteristics.")
    
    while True:
        try:
            print(f"\nTelescope characteristics for '{telescope_name}':")
            
            diameter = input("   Diameter (mm, ex: 200): ").strip()
            if not diameter:
                print("Diameter is required.")
                continue
            diameter = float(diameter)
            
            focal_length = input("   Focal length (mm, ex: 1600): ").strip()
            if not focal_length:
                print("Focal length is required.")
                continue
            focal_length = float(focal_length)
            
            # Calculate f-number
            f_number = focal_length / diameter if diameter > 0 else 8.0
            
            # Display summary
            print(f"\nCharacteristics summary:")
            print(f"   Diameter: {diameter} mm")
            print(f"   Focal length: {focal_length} mm")
            print(f"   Aperture: f/{f_number:.1f}")
            
            confirmation = input("\nAre these values correct? (y/n): ").strip().lower()
            if confirmation in ['y', 'yes', 'o', 'oui']:
                # Create telescope characteristics
                characteristics = {
                    'diameter_mm': diameter,
                    'focal_length_mm': focal_length,
                    'f_number': f_number
                }
                
                # Add to database
                TELESCOPES_DATABASE[telescope_name] = characteristics
                print(f"✅ Telescope '{telescope_name}' added to database")
                
                # Save updated configuration
                save_configuration()
                
                return characteristics
            else:
                print("🔄 Entry cancelled, please start over.")
                
        except ValueError as e:
            print(f"❌ Input error: {e}")
            print("Please enter valid numeric values.")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")

def get_sensor_characteristics(device_name):
    """Gets sensor characteristics from database.
    Order: 1) header mapping (exact INSTRUME string), 2) substring match (longest key first).
    """
    global _displayed_warnings
    
    if not device_name:
        return SENSORS_DATABASE['default']
    
    device_clean = str(device_name).strip().upper()
    
    # 1) Explicit header mapping (e.g. "ZWO ASI2600MC AIR" -> ASI2600MC)
    if device_clean in INSTRUMENT_HEADER_MAPPING:
        canonical = INSTRUMENT_HEADER_MAPPING[device_clean]
        if canonical in SENSORS_DATABASE:
            return SENSORS_DATABASE[canonical]
    
    # 2) Substring match: try longest DB keys first to prefer ASI2600MC over shorter matches
    for sensor_name, characteristics in sorted(SENSORS_DATABASE.items(), key=lambda x: -len(x[0])):
        if sensor_name == 'default':
            continue
        if sensor_name.upper() in device_clean:
            return characteristics
    
    return SENSORS_DATABASE['default']

def get_telescope_characteristics(telescope_name):
    """Gets telescope characteristics from database.
    Order: 1) header mapping (exact header string), 2) exact key match, 3) partial match.
    """
    global _displayed_warnings
    
    if not telescope_name:
        return TELESCOPES_DATABASE['default']
    
    telescope_clean = str(telescope_name).strip().upper()
    
    # 1) Explicit header mapping (e.g. "TAKAHASHI FC76-DCU" -> FC76-DCU)
    if telescope_clean in TELESCOPE_HEADER_MAPPING:
        canonical = TELESCOPE_HEADER_MAPPING[telescope_clean]
        if canonical in TELESCOPES_DATABASE:
            return TELESCOPES_DATABASE[canonical]
    
    # 2) Exact key match (DB keys may be mixed case; compare uppercased)
    if telescope_clean in TELESCOPES_DATABASE:
        return TELESCOPES_DATABASE[telescope_clean]
    for k, v in TELESCOPES_DATABASE.items():
        if k.upper() == telescope_clean:
            return v
    
    # 3) Partial match (e.g. "TAKAHASHI FC76-DCU" contains "FC76-DCU")
    for telescope_db_name, characteristics in TELESCOPES_DATABASE.items():
        if telescope_db_name == 'default':
            continue
        if telescope_db_name.upper() in telescope_clean or telescope_clean in telescope_db_name.upper():
            return characteristics
    
    return TELESCOPES_DATABASE['default']

def detect_sensor_from_fits_header(fits_file_path):
    """Automatically detects sensor from FITS header"""
    try:
        with open_fits_for_data(fits_file_path, header_only=True) as hdul:
            # Get best header (checks extensions for .fits.fz files)
            header = get_best_header(hdul)
            if header is None:
                header = hdul[0].header
            
            # Search in different header fields
            sensor_keywords = ['INSTRUME', 'CAMERA', 'DETECTOR', 'SENSOR', 'CCD', 'CMOS']
            detected_sensor = None
            
            for keyword in sensor_keywords:
                if keyword in header:
                    value = str(header[keyword]).strip()
                    if value and value != 'Unknown' and value != 'Inconnu':
                        detected_sensor = value
                        print(f"Sensor detected in FITS header: {keyword} = {value}")
                        break
            
            # If not found, try to deduce from filename
            if not detected_sensor:
                filename = fits_file_path.name.upper()
                for sensor_name in SENSORS_DATABASE.keys():
                    if sensor_name.upper() in filename:
                        detected_sensor = sensor_name
                        print(f"Sensor detected from filename: {sensor_name}")
                        break
            
            return detected_sensor
            
    except Exception as e:
        print(f"Error detecting sensor: {e}")
        return None

# Removed: calculate_photons_from_adu function - photon analysis disabled

# Removed: calculate_photons_from_adu_advanced function - photon analysis disabled

# Removed: calculate_light_quantity function - photon analysis disabled

def calculate_advanced_snr(fits_file_path, sensor_characteristics, dark_frame_path=None, bias_frame_path=None, region_size=None):
    if region_size is None:
        region_size = DEFAULT_REGION_SIZE
    """
    Advanced SNR calculation corrected according to astrophotography standards
    Calculates SNR with all noise components and calibration file support
    """
    try:
        with open_fits_for_data(fits_file_path) as hdul:
            data = hdul[0].data
            # Get best header (checks extensions for .fits.fz files)
            header = get_best_header(hdul)
            if header is None:
                header = hdul[0].header
            
            if data is None:
                return None
            
            # Extract exposure parameters from FITS header
            exposure_time = header.get('EXPTIME', 1.0)  # Exposure time in seconds
            gain_header = header.get('GAIN', sensor_characteristics.get('gain', 1.0))
            
            # Load calibration files
            dark_data = None
            bias_data = None
            
            if dark_frame_path and os.path.exists(dark_frame_path):
                try:
                    with open_fits_for_data(dark_frame_path) as dark_hdul:
                        dark_data = dark_hdul[0].data
                        dark_header = get_best_header(dark_hdul)
                        if dark_header is None:
                            dark_header = dark_hdul[0].header
                        dark_exposure = dark_header.get('EXPTIME', exposure_time)
                        print(f"   Dark frame loaded: {os.path.basename(dark_frame_path)} (exposure: {dark_exposure}s)")
                except Exception as e:
                    print(f"   Dark frame error: {e}")
            
            if bias_frame_path and os.path.exists(bias_frame_path):
                try:
                    with open_fits_for_data(bias_frame_path) as bias_hdul:
                        bias_data = bias_hdul[0].data
                        print(f"   Bias frame loaded: {os.path.basename(bias_frame_path)}")
                except Exception as e:
                    print(f"   Bias frame error: {e}")
            
            # CORRECTED SNR CALCULATION ACCORDING TO ASTROPHOTOGRAPHY STANDARDS
            
            # 1. DATA CALIBRATION (Standard astrophotography method)
            calibrated_data = data.copy()
            
            # Apply bias (offset) first - this is the base level
            if bias_data is not None:
                # Bias is the zero-point, we subtract it to get the signal above bias
                calibrated_data = calibrated_data - bias_data
                # Ensure no negative values after bias subtraction
                calibrated_data = np.maximum(calibrated_data, 0)
            
            # Apply dark (thermal noise) - normalize by exposure time
            if dark_data is not None:
                dark_header = get_best_header(dark_hdul)
                if dark_header is None:
                    dark_header = dark_hdul[0].header
                dark_exposure = dark_header.get('EXPTIME', exposure_time)
                if dark_exposure > 0:
                    if dark_exposure == exposure_time:
                        # Perfect match - use dark as is
                        calibrated_data = calibrated_data - dark_data
                    else:
                        # Normalize dark to match exposure time
                        dark_normalized = dark_data * (exposure_time / dark_exposure)
                        calibrated_data = calibrated_data - dark_normalized
                    
                    # Ensure no negative values after dark subtraction
                    calibrated_data = np.maximum(calibrated_data, 0)
            
            # 2. SENSOR PARAMETERS (in electrons)
            gain_electrons = sensor_characteristics.get('gain', gain_header)  # e-/ADU
            read_noise_electrons = sensor_characteristics.get('read_noise', 5.0)  # e- RMS
            quantum_efficiency = sensor_characteristics.get('quantum_efficiency', 0.6)  # 60% default
            dark_current = sensor_characteristics.get('dark_current', 0.1)  # e-/pixel/s
            
            # 3. ANALYSIS REGION SELECTION
            height, width = calibrated_data.shape
            center_y, center_x = height // 2, width // 2
            
            # Central region (signal of interest)
            y1 = max(0, center_y - region_size // 2)
            y2 = min(height, center_y + region_size // 2)
            x1 = max(0, center_x - region_size // 2)
            x2 = min(width, center_x + region_size // 2)
            
            central_region = calibrated_data[y1:y2, x1:x2]
            
            # Peripheral regions (sky background)
            background_regions = []
            for i in range(4):
                if i == 0:  # Top left corner
                    region = calibrated_data[:region_size, :region_size]
                elif i == 1:  # Top right corner
                    region = calibrated_data[:region_size, -region_size:]
                elif i == 2:  # Bottom left corner
                    region = calibrated_data[-region_size:, :region_size]
                else:  # Bottom right corner
                    region = calibrated_data[-region_size:, -region_size:]
                background_regions.append(region)
            
            # 4. SIGNAL CALCULATIONS (in ADU) - Realistic approach
            central_signal_adu = np.mean(central_region)
            background_mean_adu = np.mean([np.mean(region) for region in background_regions])
            
            # Net signal (signal - background) - this can be negative if background > signal
            net_signal_adu = central_signal_adu - background_mean_adu
            
            # If net signal is negative, it means the background is higher than the signal
            # This is normal for very faint objects or high background
            if net_signal_adu < 0:
                # Use the central signal as is (it contains the object + background)
                net_signal_adu = central_signal_adu
            
            # 5. CONVERSION TO ELECTRONS - Realistic conversion
            net_signal_electrons = net_signal_adu * gain_electrons
            background_electrons = background_mean_adu * gain_electrons
            total_signal_electrons = central_signal_adu * gain_electrons
            
            # Ensure all values are non-negative (physical constraint)
            net_signal_electrons = max(0, net_signal_electrons)
            background_electrons = max(0, background_electrons)
            total_signal_electrons = max(0, total_signal_electrons)
            
            # 6. NOISE COMPONENT CALCULATION (in electrons) - WITH PROTECTION
            
            # Read noise - per pixel
            read_noise_electrons = max(0, read_noise_electrons)
            
            # Photon noise (shot noise) - Poisson - with protection
            photon_noise_signal_electrons = np.sqrt(abs(total_signal_electrons)) if total_signal_electrons > 0 else 0
            photon_noise_background_electrons = np.sqrt(abs(background_electrons)) if background_electrons > 0 else 0
            
            # Dark current noise (thermal) - with protection
            dark_noise_electrons = np.sqrt(abs(dark_current * exposure_time)) if dark_current > 0 and exposure_time > 0 else 0
            
            # Sky background noise (spatial variation) - with protection
            background_std_adu = np.std([np.mean(region) for region in background_regions])
            spatial_background_noise_electrons = max(0, background_std_adu * gain_electrons)
            
            # 7. TOTAL NOISE (quadratic) - WITH PROTECTION
            noise_components = [
                max(0, read_noise_electrons**2),
                max(0, photon_noise_signal_electrons**2),
                max(0, photon_noise_background_electrons**2),
                max(0, dark_noise_electrons**2),
                max(0, spatial_background_noise_electrons**2)
            ]
            total_noise_electrons = np.sqrt(sum(noise_components))
            
            # Protection against NaN or infinite values
            if np.isnan(total_noise_electrons) or np.isinf(total_noise_electrons):
                print(f"   Invalid total noise detected: {total_noise_electrons}")
                print(f"      Components: {noise_components}")
                total_noise_electrons = 0
            
            # 8. FINAL SNR - WITH PROTECTION
            final_snr = net_signal_electrons / total_noise_electrons if total_noise_electrons > 0 else 0
            
            # Protection against NaN or infinite values
            if np.isnan(final_snr) or np.isinf(final_snr):
                final_snr = 0
            
            # 9. SNR BY COMPONENT FOR DIAGNOSTIC - WITH PROTECTION
            snr_read_only = net_signal_electrons / read_noise_electrons if read_noise_electrons > 0 else 0
            if np.isnan(snr_read_only) or np.isinf(snr_read_only):
                snr_read_only = 0
                
            photon_noise_squared = max(0, photon_noise_signal_electrons**2 + photon_noise_background_electrons**2)
            snr_photon_only = net_signal_electrons / np.sqrt(photon_noise_squared) if photon_noise_squared > 0 else 0
            if np.isnan(snr_photon_only) or np.isinf(snr_photon_only):
                snr_photon_only = 0
            
            # 10. ADDITIONAL METRICS - WITH PROTECTION
            contrast = net_signal_electrons / background_electrons if background_electrons > 0 else 0
            if np.isnan(contrast) or np.isinf(contrast):
                contrast = 0
                
            dynamic_range = total_signal_electrons / total_noise_electrons if total_noise_electrons > 0 else 0
            if np.isnan(dynamic_range) or np.isinf(dynamic_range):
                dynamic_range = 0
            
            # 11. NOISE COMPONENT DIAGNOSTIC - WITH PROTECTION
            total_noise_squared = max(0, total_noise_electrons**2)
            
            # Calculate contributions with protection against NaN values
            def safe_contribution(numerator, denominator):
                if denominator > 0 and not np.isnan(numerator) and not np.isinf(numerator):
                    contribution = (numerator / denominator) * 100
                    return max(0, min(100, contribution))  # Limit between 0 and 100%
                return 0
            
            noise_contributions = {
                'read': safe_contribution(read_noise_electrons**2, total_noise_squared),
                'photon_signal': safe_contribution(photon_noise_signal_electrons**2, total_noise_squared),
                'photon_background': safe_contribution(photon_noise_background_electrons**2, total_noise_squared),
                'dark': safe_contribution(dark_noise_electrons**2, total_noise_squared),
                'spatial_background': safe_contribution(spatial_background_noise_electrons**2, total_noise_squared)
            }
            
            return {
                'snr_final': final_snr,
                'snr_read_only': snr_read_only,
                'snr_photon_only': snr_photon_only,
                'signal_net_electrons': net_signal_electrons,
                'signal_net_adu': net_signal_adu,
                'signal_total_electrons': total_signal_electrons,
                'background_electrons': background_electrons,
                'noise_total_electrons': total_noise_electrons,
                'noise_read_electrons': read_noise_electrons,
                'noise_photon_signal_electrons': photon_noise_signal_electrons,
                'noise_photon_background_electrons': photon_noise_background_electrons,
                'noise_dark_electrons': dark_noise_electrons,
                'noise_spatial_background_electrons': spatial_background_noise_electrons,
                'contrast': contrast,
                'dynamic_range': dynamic_range,
                'calibrated': bias_data is not None or dark_data is not None,
                'region_size': region_size,
                'exposure_time': exposure_time,
                'gain_electrons': gain_electrons,
                'noise_contributions': noise_contributions
            }
            
    except Exception as e:
        print(f"   Advanced SNR calculation error: {e}")
        import traceback
        traceback.print_exc()
        return None

def find_calibration_files(base_path, exposure_time=None, gain=None, sensor_name=None):
    """
    Automatically finds appropriate BIAS and DARK files in all subdirectories
    Selects the best ones based on sensor, gain and exposure time
    """
    bias_files = []
    dark_files = []
    
    if not os.path.exists(base_path):
        return [], []
    
    print(f"   🔍 Searching for DARK files:")
    print(f"      Target exposure: {exposure_time}s")
    print(f"      Target gain: {gain}")
    print(f"      Target sensor: {sensor_name}")
    
    try:
        # Recursive search in all subdirectories
        for root, dirs, files in os.walk(base_path):
            for file in files:
                if file.lower().endswith(('.fits', '.fit', '.fits.fz', '.xisf', '.xifs', '.xif')):
                    file_path = os.path.join(root, file)
                    try:
                        with open_fits_for_data(file_path, header_only=True) as hdul:
                            # Get best header (checks extensions for .fits.fz files)
                            header = get_best_header(hdul)
                            if header is None:
                                header = hdul[0].header
                            
                            # Extract file information
                            imagetyp = header.get('IMAGETYP', '').upper()
                            file_gain = header.get('GAIN', None)
                            file_camera = get_instrument_from_header(header).upper()
                            file_exposure = header.get('EXPTIME', 0)
                            
                            # Compatibility score (0 = perfect, higher = less compatible)
                            score = 0
                            
                            # Check gain compatibility
                            if gain and file_gain:
                                gain_diff = abs(float(file_gain) - float(gain))
                                score += gain_diff * 10  # Penalty for gain difference
                            
                            # Check sensor compatibility
                            if sensor_name and file_camera:
                                sensor_name_upper = sensor_name.upper()
                                if sensor_name_upper not in file_camera and file_camera not in sensor_name_upper:
                                    score += 50  # Significant penalty if different sensor
                            
                            # Detect file type and add with score
                            if 'BIAS' in imagetyp or 'BIAS' in file.upper():
                                bias_files.append({
                                    'path': file_path,
                                    'score': score,
                                    'gain': file_gain,
                                    'camera': file_camera,
                                    'exposure': file_exposure
                                })
                            elif 'DARK' in imagetyp or 'DARK' in file.upper():
                                # For darks, prioritize by exposure time difference
                                if exposure_time and file_exposure > 0:
                                    time_diff = abs(file_exposure - exposure_time)
                                    # Use time difference as primary score - smaller is better
                                    score = time_diff
                                
                                print(f"      📁 Found DARK: {file} - {file_exposure}s (diff: {time_diff}s, score: {score:.1f})")
                                
                                dark_files.append({
                                    'path': file_path,
                                    'score': score,
                                    'gain': file_gain,
                                    'camera': file_camera,
                                    'exposure': file_exposure
                                })
                                
                    except Exception as e:
                        continue
        
        # Sort by score (best score first) - ensure perfect matches come first
        bias_files.sort(key=lambda x: x['score'])
        dark_files.sort(key=lambda x: x['score'])
        
        # Debug: verify sorting is correct
        if dark_files and exposure_time:
            print(f"   🔍 After sorting - Top 3 DARK files:")
            for i, dark in enumerate(dark_files[:3]):
                print(f"      {i+1}. {os.path.basename(dark['path'])} - {dark['exposure']}s (score: {dark['score']:.1f})")
        
        # Debug: show all available dark files
        if dark_files and exposure_time:
            print(f"   🔍 Available DARK files for {exposure_time}s exposure:")
            for i, dark in enumerate(dark_files[:5]):  # Show top 5
                print(f"      {i+1}. {os.path.basename(dark['path'])} - {dark['exposure']}s (score: {dark['score']:.1f})")
        
        # Return paths of the 3 best of each type
        bias_paths = [f['path'] for f in bias_files[:3]]
        dark_paths = [f['path'] for f in dark_files[:3]]
        
        # Debug: show selected dark file
        if dark_files and exposure_time:
            best_dark = dark_files[0]
            print(f"   🎯 Selected DARK: {os.path.basename(best_dark['path'])}")
            print(f"      Exposure: {best_dark['exposure']}s (target: {exposure_time}s)")
            print(f"      Score: {best_dark['score']:.1f}")
            
            # Verify this is the correct choice
            if best_dark['exposure'] == exposure_time:
                print(f"      ✅ PERFECT MATCH: Exposure times match exactly!")
            else:
                print(f"      ⚠️  WARNING: Exposure time mismatch! This may cause calibration issues.")
        
        return bias_paths, dark_paths
        
    except Exception as e:
        print(f"   Calibration file search error: {e}")
        return [], []

# Removed: calculate_human_eye_comparison function - human eye comparison disabled

def check_snr_and_suggest_exposure_time(samples, current_exposure_time):
    """
    Checks average SNR of ADU samples and suggests exposure time if necessary
    Uses advanced SNR calculation if available, otherwise classic calculation
    """
    if len(samples) < 2:
        return None, "Insufficient samples for SNR analysis"
    
    # Check if we have advanced SNR data
    advanced_snr_list = []
    classic_snr_list = []
    
    for s in samples:
        # Advanced SNR (priority)
        if 'advanced_snr' in s and s['advanced_snr']:
            advanced_snr_list.append(s['advanced_snr']['snr_final'])
        
        # Classic SNR (fallback)
        if 'adu_stats' in s and 'signal_to_noise' in s['adu_stats']:
            classic_snr_list.append(s['adu_stats']['signal_to_noise'])
    
    # Use advanced SNR if available, otherwise classic
    if advanced_snr_list:
        snr_list = advanced_snr_list
        snr_type = "advanced"
        print(f"     Using advanced SNR ({len(advanced_snr_list)}/{len(samples)} samples)")
    elif classic_snr_list:
        snr_list = classic_snr_list
        snr_type = "classic"
        print(f"     Using classic SNR ({len(classic_snr_list)}/{len(samples)} samples)")
    else:
        return None, "No SNR data available"
    
    average_snr = sum(snr_list) / len(snr_list)
    print(f"     Average {snr_type} SNR of {len(snr_list)} samples: {average_snr:.2f}")
    
    # Check if SNR is sufficient (> 3)
    if average_snr > 3:
        return average_snr, f"{snr_type.capitalize()} SNR sufficient (> 3)"
    
    # If SNR is insufficient, calculate necessary exposure time
    # SNR = signal / total_noise
    # To improve SNR, need to increase signal proportionally
    # New_time = Current_time * (3 / Current_SNR)²
    
    suggested_time = current_exposure_time * (3.0 / average_snr) ** 2
    
    # Round to practical values (30s, 60s, 120s, 300s, 600s, etc.)
    practical_times = [30, 60, 120, 180, 300, 600, 900, 1200, 1800, 3600]
    suggested_time_rounded = min(practical_times, key=lambda x: abs(x - suggested_time))
    
    return average_snr, f"{snr_type.capitalize()} SNR insufficient ({average_snr:.2f} < 3). Suggested time: {suggested_time_rounded}s (calculated: {suggested_time:.0f}s)"

def display_noise_component_details(samples):
    """Displays noise component details for advanced SNR samples"""
    if not samples:
        return
    
    advanced_snr_sources = [s for s in samples if 'advanced_snr' in s and s['advanced_snr']]
    if not advanced_snr_sources:
        return
    
    print(f"     NOISE COMPONENT DETAILS:")
    print(f"     {'Component':<20} {'Value':<12} {'% of total':<12}")
    print(f"     {'-'*20} {'-'*12} {'-'*12}")
    
    # Calculate component averages
    read_noise_avg = sum(s['advanced_snr']['noise_read_electrons'] for s in advanced_snr_sources) / len(advanced_snr_sources)
    photon_signal_noise_avg = sum(s['advanced_snr']['noise_photon_signal_electrons'] for s in advanced_snr_sources) / len(advanced_snr_sources)
    photon_background_noise_avg = sum(s['advanced_snr']['noise_photon_background_electrons'] for s in advanced_snr_sources) / len(advanced_snr_sources)
    spatial_background_noise_avg = sum(s['advanced_snr']['noise_spatial_background_electrons'] for s in advanced_snr_sources) / len(advanced_snr_sources)
    dark_noise_avg = sum(s['advanced_snr']['noise_dark_electrons'] for s in advanced_snr_sources) / len(advanced_snr_sources)
    total_noise_avg = sum(s['advanced_snr']['noise_total_electrons'] for s in advanced_snr_sources) / len(advanced_snr_sources)
    
    # Display each component with calculated percentages
    if advanced_snr_sources:
        # Use percentages calculated by advanced SNR
        noise_contributions_avg = {}
        for key in ['read', 'photon_signal', 'photon_background', 'dark', 'spatial_background']:
            values = [s['advanced_snr']['noise_contributions'].get(key, 0) for s in advanced_snr_sources]
            noise_contributions_avg[key] = sum(values) / len(values) if values else 0
        
        components = [
            ('Read noise (e-)', read_noise_avg, noise_contributions_avg.get('read', 0)),
            ('Photon signal (e-)', photon_signal_noise_avg, noise_contributions_avg.get('photon_signal', 0)),
            ('Photon background (e-)', photon_background_noise_avg, noise_contributions_avg.get('photon_background', 0)),
            ('Dark current (e-)', dark_noise_avg, noise_contributions_avg.get('dark', 0)),
            ('Spatial background (e-)', spatial_background_noise_avg, noise_contributions_avg.get('spatial_background', 0))
        ]
        
        for name, value, percentage in components:
            print(f"     {name:<20} {value:<12.2f} {percentage:<12.1f}%")
        
        print(f"     {'-'*20} {'-'*12} {'-'*12}")
        print(f"     {'Total noise (e-)':<20} {total_noise_avg:<12.2f} {'100.0':<12}%")

def calculate_adu_statistics_by_filter(data_by_target):
    """
    Calculates statistics by filter and extrapolates for all files
    """
    print(f"\nSTATISTICAL ANALYSIS BY FILTER")
    print("=" * 80)
    
    for target, data in data_by_target.items():
        print(f"\nTARGET: {target}")
        print("-" * 60)
        
        for filter_name, samples in data['adu_samples'].items():
            if len(samples) >= 2:  # At least 2 samples for reliable statistics
                print(f"   FILTER: {filter_name}")
                
                # Calculate sample statistics
                photons_list = [s['adu_photons'] for s in samples]
                exposure_list = [s.get('exposure_time') or 0 for s in samples]
                
                # Calculate photons/time ratio to normalize
                photon_time_ratios = [p/t for p, t in zip(photons_list, exposure_list)]
                
                # Ratio statistics
                average_ratio = sum(photon_time_ratios) / len(photon_time_ratios)
                ratio_std = (sum((r - average_ratio)**2 for r in photon_time_ratios) / len(photon_time_ratios))**0.5
                
                # Photon statistics
                average_photons = sum(photons_list) / len(photons_list)
                photons_std = (sum((p - average_photons)**2 for p in photons_list) / len(photons_list))**0.5
                
                print(f"     Analyzed samples: {len(samples)} files")
                print(f"     Average photons: {average_photons:.2e} ± {photons_std:.2e}")
                print(f"     Photons/time ratio: {average_ratio:.2e} ± {ratio_std:.2e}")
                
                # SNR CHECK AND EXPOSURE TIME SUGGESTION
                average_exposure_time = sum(exposure_list) / len(exposure_list)
                average_snr, snr_message = check_snr_and_suggest_exposure_time(samples, average_exposure_time)
                print(f"     {snr_message}")
                
                # Display noise component details if advanced SNR available
                display_noise_component_details(samples)
                
                # Calculate total time for this filter
                total_filter_time = sum(time for time in data['time_by_filter'][filter_name])
                filter_file_count = len(data['time_by_filter'][filter_name])
                
                # Extrapolate total photon count
                extrapolated_photons = average_ratio * total_filter_time
                
                print(f"     Extrapolation: {extrapolated_photons:.2e} photons for {filter_file_count} files")
                print(f"     Estimated precision: ±{ratio_std * total_filter_time:.2e} photons")
                
                # Update light data with extrapolation
                if filter_name in data['received_light']:
                    # Replace theoretical calculations with extrapolation
                    for light in data['received_light'][filter_name]:
                        # Calculate proportion for this file (simplified without eye comparison)
                        time_proportion = 1.0 / len(data['received_light'][filter_name])  # Equal distribution
                        extrapolated_adu_photons = extrapolated_photons * time_proportion
                        
                        # Extrapolation removed (photon analysis disabled)
                        light['source'] = 'basic_info'
                        light['adu_stats'] = {
                            'average_ratio': average_ratio,
                            'ratio_std': ratio_std,
                            'samples_used': len(samples),
                            'extrapolated_photons': extrapolated_photons,
                            'average_snr': average_snr,
                            'snr_message': snr_message
                        }
                
                print(f"     ✅ Statistics calculated for all files")
            else:
                print(f"   FILTER: {filter_name} - Insufficient samples ({len(samples)} < 2)")
                print(f"     ⚠️  Keeping theoretical calculation")
    
    return data_by_target

def extract_fits_header_info_fast(file_path):
    """Ultra-fast extraction of basic FITS header info for Phase 1 (optimized for speed)
    Uses fits.getheader() which only reads the header without loading the entire file.
    """
    try:
        file_path_str = str(file_path).lower()
        
        # For XISF and related compressed formats (.xisf, .xifs, .xif), use full open method
        # These may not work correctly with getheader() and need special handling
        if file_path_str.endswith(('.xisf', '.xifs', '.xif')):
            with open_fits_for_data(file_path, header_only=True) as hdul:
                header = get_best_header(hdul)
                if header is None:
                    header = hdul[0].header
        else:
            # For FITS files (.fits, .fit, .fits.fz), use getheader() for speed
            # This is MUCH faster than opening the entire file
            try:
                # Try primary header first (most common case)
                header = fits.getheader(file_path, ext=0)
                
                # For .fits.fz files, metadata is often in extension 1
                # Check if primary header has essential keys, if not try extension 1
                essential_keys = ['EXPTIME', 'EXPOSURE', 'IMAGETYP', 'FILTER', 'INSTRUME', 'TELESCOP']
                has_essential = any(key in header for key in essential_keys)
                
                if not has_essential and len(header) < 20:
                    # Try extension 1 (common for compressed FITS)
                    try:
                        ext_header = fits.getheader(file_path, ext=1)
                        if len(ext_header) > len(header):
                            header = ext_header
                    except (IndexError, KeyError, OSError):
                        pass  # Use primary header if extension doesn't exist
            except Exception:
                # Fallback to full open if getheader fails
                with open_fits_for_data(file_path, header_only=True) as hdul:
                    header = get_best_header(hdul)
                    if header is None:
                        header = hdul[0].header
        
        # Extract only essential info for Phase 1 (optimized for speed)
        # Use direct header access to avoid unnecessary operations
        exposure_time = None
        # Check most common keywords first
        if 'EXPTIME' in header:
            try:
                exposure_time = float(header['EXPTIME'])
            except (ValueError, TypeError):
                pass
        elif 'EXPOSURE' in header:
            try:
                exposure_time = float(header['EXPOSURE'])
            except (ValueError, TypeError):
                pass
        elif 'EXPOSURE_TIME' in header:
            try:
                exposure_time = float(header['EXPOSURE_TIME'])
            except (ValueError, TypeError):
                pass
        elif 'INT_TIME' in header:
            try:
                exposure_time = float(header['INT_TIME'])
            except (ValueError, TypeError):
                pass
        elif 'INTEGRATION' in header:
            try:
                exposure_time = float(header['INTEGRATION'])
            except (ValueError, TypeError):
                pass
        
        # If still not found, try to extract from filename (common pattern: EXPOSURE-60.00s)
        if exposure_time is None:
            import re
            filename = str(file_path.name)
            # Look for patterns like "EXPOSURE-60.00s", "60.00s", "60s", etc.
            exposure_patterns = [
                r'EXPOSURE[_-]?(\d+\.?\d*)\s*s',
                r'(\d+\.?\d*)\s*s(?!\w)',  # Number followed by 's' but not part of another word
                r'(\d+\.?\d*)\s*sec',
            ]
            for pattern in exposure_patterns:
                match = re.search(pattern, filename, re.IGNORECASE)
                if match:
                    try:
                        exposure_time = float(match.group(1))
                        break
                    except (ValueError, IndexError):
                        pass
        
        # Extract image type (simplified, check most common first)
        image_type = 'LIGHT'  # Default
        if 'IMAGETYP' in header:
            value = header['IMAGETYP']
            if isinstance(value, str):
                value_upper = value.upper()
                if 'FLAT' in value_upper:
                    image_type = 'FLAT'
                elif 'DARK' in value_upper:
                    image_type = 'DARK'
                elif 'BIAS' in value_upper:
                    image_type = 'BIAS'
        
        # Extract filter (simplified, check most common first)
        filter_found = 'Unknown'
        if 'FILTER' in header:
            filter_found = str(header['FILTER']).strip().upper()
        elif 'FILTRE' in header:
            filter_found = str(header['FILTRE']).strip().upper()
        elif 'FILT' in header:
            filter_found = str(header['FILT']).strip().upper()
        
        # Extract target (simplified)
        target = None
        if 'OBJECT' in header:
            target = str(header['OBJECT']).strip()
        elif 'TARGET' in header:
            target = str(header['TARGET']).strip()
        
        # Telescope and instrument from header (multiple keywords for compatibility)
        instrument = get_instrument_from_header(header)
        telescope = get_telescope_from_header(header)
        
        return {
            'exposure_time': exposure_time,
            'type': image_type,
            'filter': filter_found,
            'target': target,
            'info': {
                'instrument': instrument,
                'telescope': telescope,
                'date_obs': header.get('DATE-OBS', 'Unknown')
            }
        }
            
    except Exception as e:
        return None

def extract_fits_header_info(file_path, should_analyze_adu=True):
    """Extracts all information from FITS header
    Optimized: uses fits.getheader() for fast mode (should_analyze_adu=False) to avoid loading full file
    """
    # Remove debug print to avoid interfering with tqdm
    try:
        # For fast mode (no ADU analysis), use getheader() for speed
        if not should_analyze_adu:
            file_path_str = str(file_path).lower()
            
            # For XISF and related compressed formats (.xisf, .xifs, .xif), use full open method
            # These may not work correctly with getheader() and need special handling
            if file_path_str.endswith(('.xisf', '.xifs', '.xif')):
                with open_fits_for_data(file_path, header_only=True) as hdul:
                    header = get_best_header(hdul)
                    if header is None:
                        header = hdul[0].header
            else:
                # For FITS files (.fits, .fit, .fits.fz), use getheader() for speed (much faster)
                try:
                    header = fits.getheader(file_path, ext=0)
                    # For .fits.fz files, check extension 1 if primary header is minimal
                    essential_keys = ['EXPTIME', 'EXPOSURE', 'IMAGETYP', 'FILTER', 'INSTRUME', 'TELESCOP']
                    has_essential = any(key in header for key in essential_keys)
                    if not has_essential and len(header) < 20:
                        try:
                            ext_header = fits.getheader(file_path, ext=1)
                            if len(ext_header) > len(header):
                                header = ext_header
                        except (IndexError, KeyError, OSError):
                            pass
                except Exception:
                    # Fallback to full open if getheader fails
                    with open_fits_for_data(file_path, header_only=True) as hdul:
                        header = get_best_header(hdul)
                        if header is None:
                            header = hdul[0].header
            
            # Extract exposure time (for fast mode)
            exposure_time = None
            time_keywords = ['EXPTIME', 'EXPOSURE', 'EXPOSURE_TIME', 'INT_TIME', 'INTEGRATION']
            for keyword in time_keywords:
                if keyword in header:
                    try:
                        exposure_time = float(header[keyword])
                        break
                    except (ValueError, TypeError):
                        pass
            
            # If still not found, try to extract from filename (common pattern: EXPOSURE-60.00s)
            if exposure_time is None:
                import re
                filename = str(file_path.name)
                # Look for patterns like "EXPOSURE-60.00s", "60.00s", "60s", etc.
                exposure_patterns = [
                    r'EXPOSURE[_-]?(\d+\.?\d*)\s*s',
                    r'(\d+\.?\d*)\s*s(?!\w)',  # Number followed by 's' but not part of another word
                    r'(\d+\.?\d*)\s*sec',
                ]
                for pattern in exposure_patterns:
                    match = re.search(pattern, filename, re.IGNORECASE)
                    if match:
                        try:
                            exposure_time = float(match.group(1))
                            break
                        except (ValueError, IndexError):
                            pass
            
            # Extract image type (for fast mode)
            image_type = 'LIGHT'  # Default
            if 'IMAGETYP' in header:
                value = str(header['IMAGETYP']).upper().strip()
                if 'FLAT' in value:
                    image_type = 'FLAT'
                elif 'DARK' in value:
                    image_type = 'DARK'
                elif 'BIAS' in value:
                    image_type = 'BIAS'
            
            # Extract filter (for fast mode)
            filter_found = None
            filter_keywords = ['FILTER', 'FILTRE', 'FILTERS', 'FILT', 'COLOR', 'BANDPASS']
            for keyword in filter_keywords:
                if keyword in header:
                    value = str(header[keyword]).strip().upper()
                    # Simple filter mapping for fast mode
                    if value in ['L', 'LUM', 'LUMINANCE', 'LIGHT']:
                        filter_found = 'L'
                    elif value in ['R', 'RED']:
                        filter_found = 'R'
                    elif value in ['G', 'GREEN']:
                        filter_found = 'G'
                    elif value in ['B', 'BLUE']:
                        filter_found = 'B'
                    elif 'HA' in value or 'H-ALPHA' in value or 'HALPHA' in value:
                        filter_found = 'HA'
                    elif 'OIII' in value or 'O3' in value:
                        filter_found = 'OIII'
                    elif 'SII' in value or 'S2' in value:
                        filter_found = 'SII'
                    else:
                        filter_found = value  # Use as-is
                    break
            
            # Extract target (for fast mode)
            target_found = None
            if 'OBJECT' in header:
                target_found = str(header['OBJECT']).strip()
            elif 'TARGET' in header:
                target_found = str(header['TARGET']).strip()
            
            if target_found and target_found != 'Unknown':
                target_found = normalize_target_name(target_found)
            
            # Extract telescope and instrument (multiple FITS keywords)
            instrument = get_instrument_from_header(header)
            telescope = get_telescope_from_header(header)
            
            # Extract coordinates (for fast mode)
            ra, dec = None, None
            if 'RA' in header and 'DEC' in header:
                try:
                    ra = float(header['RA'])
                    dec = float(header['DEC'])
                except Exception:
                    pass
            
            # Extract diameter and focal length (simplified for fast mode)
            diameter = None
            diameter_keywords = ['APERTURE', 'TELESCOP_DIAM', 'MIRROR_DIAM', 'PRIMARY_DIAM', 'DIAMETER', 'APTDIA', 'TELDIAM']
            for keyword in diameter_keywords:
                if keyword in header:
                    try:
                        diameter = float(header[keyword])
                        break
                    except Exception:
                        pass
            
            focal_length = None
            focal_keywords = ['FOCALLEN', 'FOCAL', 'FOCAL_LENGTH', 'FOCLEN']
            for keyword in focal_keywords:
                if keyword in header:
                    try:
                        focal_length = float(header[keyword])
                        break
                    except Exception:
                        pass
            
            # If not found, try to deduce from telescope name (simplified)
            if diameter is None or focal_length is None:
                telescope_characteristics = get_telescope_characteristics(telescope)
                if diameter is None:
                    diameter = telescope_characteristics.get('diameter_mm')
                if focal_length is None:
                    focal_length = telescope_characteristics.get('focal_length_mm')
            
            # Calculate f-number
            f_number = focal_length / diameter if diameter and diameter > 0 else 8.0
            
            # Return fast mode result
            return {
                'type': image_type,
                'filter': filter_found or 'Unknown',
                'exposure_time': exposure_time,
                'target': target_found,
                'ra': ra,
                'dec': dec,
                'observation_date': header.get('DATE-OBS', 'Unknown'),
                'info': {
                    'instrument': instrument,
                    'telescope': telescope,
                    'date_obs': header.get('DATE-OBS', 'Unknown'),
                    'diameter_mm': diameter,
                    'focal_length_mm': focal_length,
                    'f_number': f_number
                },
                'adu_photons': None,
                'advanced_snr': None
            }
        else:
            # For ADU analysis, use full open method (may need data access)
            with open_fits_for_data(file_path, header_only=True) as hdul:
                # Get best header (checks extensions for .fits.fz files)
                header = get_best_header(hdul)
                if header is None:
                    header = hdul[0].header
            
            # Extract exposure time
            exposure_time = None
            time_keywords = ['EXPTIME', 'EXPOSURE', 'EXPOSURE_TIME', 'INT_TIME', 'INTEGRATION']
            for keyword in time_keywords:
                if keyword in header:
                    exposure_time = float(header[keyword])
                    break
            
            # Extract image type
            image_type = None
            # Only use dedicated type keywords (NOT OBJECT - target names like "Dark Shark Nebula" 
            # would be misclassified as DARK)
            type_keywords = ['IMAGETYP', 'IMTYPE', 'OBSTYPE', 'FRAME']
            for keyword in type_keywords:
                if keyword in header:
                    value = str(header[keyword]).upper().strip()
                    if 'LIGHT' in value or 'SCIENCE' in value or 'OBJECT' in value:
                        image_type = 'LIGHT'
                        break
                    elif 'FLAT' in value or 'FLATWIZARD' in value:
                        image_type = 'FLAT'
                        break
                    elif 'DARK' in value:
                        image_type = 'DARK'
                        break
                    elif 'BIAS' in value:
                        image_type = 'BIAS'
                        break
            
            # If no type found, try to deduce from filename
            if image_type is None:
                filename = os.path.basename(file_path).upper()
                if 'FLAT' in filename:
                    image_type = 'FLAT'
                elif 'DARK' in filename:
                    image_type = 'DARK'
                elif 'BIAS' in filename:
                    image_type = 'BIAS'
                else:
                    image_type = 'LIGHT'  # Default to LIGHT for unknown files
            
            # Extract filter
            filter_found = None
            filter_keywords = ['FILTER', 'FILTRE', 'FILTERS', 'FILT', 'COLOR', 'BANDPASS']
            for keyword in filter_keywords:
                if keyword in header:
                    value = str(header[keyword]).upper().strip()
                    
                    # First, try direct mapping for common filter names in headers
                    # Comprehensive mapping for all variants
                    header_filter_mapping = {
                        # RGB filters - all variants
                        'BLUE': 'B', 'blue': 'B', 'Blue': 'B',
                        'GREEN': 'G', 'green': 'G', 'Green': 'G',
                        'RED': 'R', 'red': 'R', 'Red': 'R',
                        
                        # Luminance - all variants
                        'LUMINANCE': 'L', 'luminance': 'L', 'Luminance': 'L',
                        'LUM': 'L', 'lum': 'L', 'Lum': 'L',
                        'LIGHT': 'L', 'light': 'L', 'Light': 'L',
                        'L': 'L', 'l': 'L',
                        
                        # Clear filter
                        'CLEAR': 'CLEAR', 'clear': 'CLEAR', 'Clear': 'CLEAR',
                        
                        # H-Alpha - all variants
                        'H-ALPHA': 'HA', 'H_ALPHA': 'HA', 'H ALPHA': 'HA',
                        'h-alpha': 'HA', 'h_alpha': 'HA', 'h alpha': 'HA',
                        'H-alpha': 'HA', 'H_alpha': 'HA', 'H alpha': 'HA',
                        'HALPHA': 'HA', 'halpha': 'HA', 'Halpha': 'HA',
                        'HA': 'HA', 'ha': 'HA', 'Ha': 'HA',
                        'H-A': 'HA', 'H_A': 'HA', 'H A': 'HA',
                        'h-a': 'HA', 'h_a': 'HA', 'h a': 'HA',
                        'H-a': 'HA', 'H_a': 'HA', 'H a': 'HA',
                        'HYDROGEN ALPHA': 'HA', 'HYDROGEN-ALPHA': 'HA', 'HYDROGEN_ALPHA': 'HA',
                        'hydrogen alpha': 'HA', 'hydrogen-alpha': 'HA', 'hydrogen_alpha': 'HA',
                        'Hydrogen Alpha': 'HA', 'Hydrogen-Alpha': 'HA', 'Hydrogen_Alpha': 'HA',
                        
                        # H-Beta - all variants
                        'H-BETA': 'HBETA', 'H_BETA': 'HBETA', 'H BETA': 'HBETA',
                        'h-beta': 'HBETA', 'h_beta': 'HBETA', 'h beta': 'HBETA',
                        'H-beta': 'HBETA', 'H_beta': 'HBETA', 'H beta': 'HBETA',
                        'HBETA': 'HBETA', 'hbeta': 'HBETA', 'Hbeta': 'HBETA',
                        'HB': 'HBETA', 'hb': 'HBETA', 'Hb': 'HBETA',
                        'H-B': 'HBETA', 'H_B': 'HBETA', 'H B': 'HBETA',
                        'h-b': 'HBETA', 'h_b': 'HBETA', 'h b': 'HBETA',
                        'H-b': 'HBETA', 'H_b': 'HBETA', 'H b': 'HBETA',
                        'HYDROGEN BETA': 'HBETA', 'HYDROGEN-BETA': 'HBETA', 'HYDROGEN_BETA': 'HBETA',
                        'hydrogen beta': 'HBETA', 'hydrogen-beta': 'HBETA', 'hydrogen_beta': 'HBETA',
                        'Hydrogen Beta': 'HBETA', 'Hydrogen-Beta': 'HBETA', 'Hydrogen_Beta': 'HBETA',
                        
                        # OIII - all variants
                        'OIII': 'OIII', 'oiii': 'OIII', 'Oiii': 'OIII',
                        'O3': 'OIII', 'o3': 'OIII', 'O3': 'OIII',
                        'O-3': 'OIII', 'O_3': 'OIII', 'O 3': 'OIII',
                        'o-3': 'OIII', 'o_3': 'OIII', 'o 3': 'OIII',
                        'O-3': 'OIII', 'O_3': 'OIII', 'O 3': 'OIII',
                        'OXYGEN III': 'OIII', 'OXYGEN-III': 'OIII', 'OXYGEN_III': 'OIII',
                        'oxygen iii': 'OIII', 'oxygen-iii': 'OIII', 'oxygen_iii': 'OIII',
                        'Oxygen III': 'OIII', 'Oxygen-III': 'OIII', 'Oxygen_III': 'OIII',
                        'OXYGEN 3': 'OIII', 'OXYGEN-3': 'OIII', 'OXYGEN_3': 'OIII',
                        'oxygen 3': 'OIII', 'oxygen-3': 'OIII', 'oxygen_3': 'OIII',
                        'Oxygen 3': 'OIII', 'Oxygen-3': 'OIII', 'Oxygen_3': 'OIII',
                        
                        # SII - all variants
                        'SII': 'SII', 'sii': 'SII', 'Sii': 'SII',
                        'S2': 'SII', 's2': 'SII', 'S2': 'SII',
                        'S-2': 'SII', 'S_2': 'SII', 'S 2': 'SII',
                        's-2': 'SII', 's_2': 'SII', 's 2': 'SII',
                        'S-2': 'SII', 'S_2': 'SII', 'S 2': 'SII',
                        'SULFUR II': 'SII', 'SULFUR-II': 'SII', 'SULFUR_II': 'SII',
                        'sulfur ii': 'SII', 'sulfur-ii': 'SII', 'sulfur_ii': 'SII',
                        'Sulfur II': 'SII', 'Sulfur-II': 'SII', 'Sulfur_II': 'SII',
                        'SULFUR 2': 'SII', 'SULFUR-2': 'SII', 'SULFUR_2': 'SII',
                        'sulfur 2': 'SII', 'sulfur-2': 'SII', 'sulfur_2': 'SII',
                        'Sulfur 2': 'SII', 'Sulfur-2': 'SII', 'Sulfur_2': 'SII',
                        
                        # NII - all variants
                        'NII': 'NII', 'nii': 'NII', 'Nii': 'NII',
                        'N2': 'NII', 'n2': 'NII', 'N2': 'NII',
                        'N-2': 'NII', 'N_2': 'NII', 'N 2': 'NII',
                        'n-2': 'NII', 'n_2': 'NII', 'n 2': 'NII',
                        'N-2': 'NII', 'N_2': 'NII', 'N 2': 'NII',
                        'NITROGEN II': 'NII', 'NITROGEN-II': 'NII', 'NITROGEN_II': 'NII',
                        'nitrogen ii': 'NII', 'nitrogen-ii': 'NII', 'nitrogen_ii': 'NII',
                        'Nitrogen II': 'NII', 'Nitrogen-II': 'NII', 'Nitrogen_II': 'NII',
                        'NITROGEN 2': 'NII', 'NITROGEN-2': 'NII', 'NITROGEN_2': 'NII',
                        'nitrogen 2': 'NII', 'nitrogen-2': 'NII', 'nitrogen_2': 'NII',
                        'Nitrogen 2': 'NII', 'Nitrogen-2': 'NII', 'Nitrogen_2': 'NII',
                        
                        # HEII - all variants
                        'HEII': 'HEII', 'heii': 'HEII', 'Heii': 'HEII',
                        'HE-II': 'HEII', 'HE_II': 'HEII', 'HE II': 'HEII',
                        'he-ii': 'HEII', 'he_ii': 'HEII', 'he ii': 'HEII',
                        'He-II': 'HEII', 'He_II': 'HEII', 'He II': 'HEII',
                        'HE-2': 'HEII', 'HE_2': 'HEII', 'HE 2': 'HEII',
                        'he-2': 'HEII', 'he_2': 'HEII', 'he 2': 'HEII',
                        'He-2': 'HEII', 'He_2': 'HEII', 'He 2': 'HEII',
                        'HELIUM II': 'HEII', 'HELIUM-II': 'HEII', 'HELIUM_II': 'HEII',
                        'helium ii': 'HEII', 'helium-ii': 'HEII', 'helium_ii': 'HEII',
                        'Helium II': 'HEII', 'Helium-II': 'HEII', 'Helium_II': 'HEII',
                        'HELIUM 2': 'HEII', 'HELIUM-2': 'HEII', 'HELIUM_2': 'HEII',
                        'helium 2': 'HEII', 'helium-2': 'HEII', 'helium_2': 'HEII',
                        'Helium 2': 'HEII', 'Helium-2': 'HEII', 'Helium_2': 'HEII',
                        # Optolong (header value is upper())
                        'OPTOLONG L-PRO': 'LPRO', 'L-PRO': 'LPRO', 'LPRO': 'LPRO',
                        'OPTOLONG L-ENHANCE': 'LEHNANCE', 'L-ENHANCE': 'LEHNANCE', 'LENHANCE': 'LEHNANCE',
                        'OPTOLONG L-EXTREME': 'LEXTREME', 'L-EXTREME': 'LEXTREME', 'LEXTREME': 'LEXTREME',
                        'OPTOLONG L-ULTIMATE': 'LULTIMATE', 'L-ULTIMATE': 'LULTIMATE', 'LULTIMATE': 'LULTIMATE',
                        # IDAS
                        'IDAS LPS': 'IDAS_LPS', 'IDAS LPS D1': 'IDAS_LPS_D1', 'IDAS LPS D2': 'IDAS_LPS_D2',
                        'IDAS LPS-D1': 'IDAS_LPS_D1', 'IDAS LPS-D2': 'IDAS_LPS_D2',
                        'IDAS NBZ': 'NBZ', 'NBZ': 'NBZ',
                        'IDAS NBZ II': 'IDAS_NBZ_II', 'IDAS NB3': 'IDAS_NB3',
                        'NBZ II': 'IDAS_NBZ_II', 'NB3': 'IDAS_NB3',
                        # Light pollution / multiband (header value is upper())
                        'CLS': 'CLS', 'UHC': 'UHC',
                        'TRI-BAND': 'TRIBAND', 'TRIBAND': 'TRIBAND', 'TRI BAND': 'TRIBAND',
                        'QUAD-BAND': 'QUAD_BAND', 'QUADBAND': 'QUAD_BAND', 'QUAD BAND': 'QUAD_BAND',
                        'IR CUT': 'IRCUT', 'IRCUT': 'IRCUT',
                        'UV/IR': 'UVIR', 'UV-IR': 'UVIR', 'UVIR': 'UVIR', 'UV IR': 'UVIR',
                        # Sloan/SDSS (header may contain full name)
                        'SLOAN U': 'U_SDSS', 'SLOAN G': 'G_SDSS', 'SLOAN R': 'R_SDSS', 'SLOAN I': 'I_SDSS', 'SLOAN Z': 'Z_SDSS',
                        'G_SDSS': 'G_SDSS', 'R_SDSS': 'R_SDSS', 'I_SDSS': 'I_SDSS', 'Z_SDSS': 'Z_SDSS', 'U_SDSS': 'U_SDSS',
                    }
                    
                    # Check direct mapping first
                    if value in header_filter_mapping:
                        filter_found = header_filter_mapping[value]
                        break
                    
                    # More precise filter detection to avoid false positives
                    for filter_name in FILTERS_INFO.keys():
                        # Check for exact match or word boundaries to avoid false positives
                        if (filter_name == value or 
                            f" {filter_name} " in f" {value} " or
                            value.startswith(f"{filter_name} ") or
                            value.endswith(f" {filter_name}") or
                            value == filter_name):
                            filter_found = filter_name
                            break
                    if filter_found:
                        break
            
            # If no filter found in header, check for Bayer pattern FIRST
            if filter_found is None:
                # Check for Bayer pattern in header to detect color cameras FIRST
                bayer_detected = False
                bayer_keywords = ['BAYERPAT', 'BAYERPATN', 'BAYERPATTERN', 'COLORTYP', 'COLORSPACE']
                for bayer_key in bayer_keywords:
                    if bayer_key in header:
                        bayer_value = str(header[bayer_key]).strip().upper()
                        # Check if it's a valid Bayer pattern
                        valid_bayer_patterns = ['RGGB', 'BGGR', 'GRBG', 'GBRG', 'RGB', 'COLOR', 'BAYER']
                        if bayer_value in valid_bayer_patterns:
                            bayer_detected = True
                            break
                
                if bayer_detected:
                    filter_found = 'OSC'  # One Shot Color with Bayer pattern
                else:
                    # If no Bayer pattern, try to extract from filename
                    filt_code, filt_info = extract_filter_from_filename(file_path.name)
                    if filt_code:
                        filter_found = filt_code
                    else:
                        # Fallback: try to detect common filter names in filename
                        filename = os.path.basename(file_path).upper()
                        if 'LUMINANCE' in filename or 'LUM' in filename:
                            filter_found = 'L'
                        elif 'RED' in filename:
                            filter_found = 'R'
                        elif 'GREEN' in filename:
                            filter_found = 'G'
                        elif 'BLUE' in filename:
                            filter_found = 'B'
                        elif 'HALPHA' in filename or 'H-ALPHA' in filename:
                            filter_found = 'HA'
                        elif 'OIII' in filename or 'O3' in filename:
                            filter_found = 'OIII'
                        elif 'SII' in filename or 'S2' in filename:
                            filter_found = 'SII'
                        else:
                            # Check if this is likely a color camera file (OSC)
                            # Look for common OSC indicators in filename or path
                            filename_lower = filename.lower()
                            path_lower = str(file_path).lower()
                            
                            # Common OSC indicators
                            osc_indicators = ['color', 'colour', 'osc', 'one shot', 'oneshot', 'rgb', 'camera', 'cam']
                            if any(indicator in filename_lower or indicator in path_lower for indicator in osc_indicators):
                                filter_found = 'OSC'  # One Shot Color
                            else:
                                filter_found = 'L'  # Default to Luminance for monochrome cameras
            
            # Extract target/object
            target_found = None
            if 'OBJECT' in header:
                target_found = str(header['OBJECT']).strip()
            elif 'TARGET' in header:
                target_found = str(header['TARGET']).strip()
            
            # Normalize target name (case-insensitive, remove extra spaces)
            if target_found and target_found != 'Unknown':
                target_found = normalize_target_name(target_found)
            
            # Extract celestial coordinates
            ra, dec = None, None
            if 'RA' in header and 'DEC' in header:
                try:
                    ra = float(header['RA'])
                    dec = float(header['DEC'])
                except Exception:
                    pass
            elif 'CRVAL1' in header and 'CRVAL2' in header:
                try:
                    ra = float(header['CRVAL1'])
                    dec = float(header['CRVAL2'])
                except Exception:
                    pass
            
            # Extract telescope and instrument (multiple FITS keywords)
            instrument = get_instrument_from_header(header)
            telescope = get_telescope_from_header(header)
            
            # Remove debug prints to avoid interfering with tqdm
            
            # Extract instrument diameter
            diameter = None
            diameter_keywords = ['APERTURE', 'TELESCOP_DIAM', 'MIRROR_DIAM', 'PRIMARY_DIAM', 'DIAMETER', 'APTDIA', 'TELDIAM', 'MIRROR_D', 'PRIMARY_D']
            for keyword in diameter_keywords:
                if keyword in header:
                    try:
                        diameter = float(header[keyword])
                        break
                    except Exception:
                        pass
            
            # If diameter not found in header, try to extract from telescope name
            if diameter is None and telescope:
                telescope_str = str(telescope).upper()
                # Look for diameter patterns in telescope name
                import re
                diameter_match = re.search(r'(\d+(?:\.\d+)?)\s*mm', telescope_str)
                if diameter_match:
                    diameter = float(diameter_match.group(1))
                else:
                    # Try to extract from telescope model names
                    diameter_match = re.search(r'(\d+(?:\.\d+)?)', telescope_str)
                    if diameter_match:
                        potential_diameter = float(diameter_match.group(1))
                        # Check if it's a reasonable telescope diameter (50mm to 2000mm)
                        if 50 <= potential_diameter <= 2000:
                            diameter = potential_diameter
            
            # If not found, try to deduce from telescope name
            if diameter is None:
                telescope_str = str(telescope).upper()
                
                # First, try to match with our database
                for telescope_name, characteristics in TELESCOPES_DATABASE.items():
                    if telescope_name.upper() in telescope_str:
                        diameter = characteristics['diameter_mm']
                        break
                
                # If still not found, try common patterns
                if diameter is None:
                    # Ritchey-Chrétien (RC)
                    if 'RC8' in telescope_str or '8"' in telescope_str:
                        diameter = 203.2  # mm
                    elif 'RC6' in telescope_str or '6"' in telescope_str:
                        diameter = 152.4  # mm
                    elif 'RC10' in telescope_str or '10"' in telescope_str:
                        diameter = 254.0  # mm
                    elif 'RC12' in telescope_str or '12"' in telescope_str:
                        diameter = 304.8  # mm
                    elif 'RC14' in telescope_str or '14"' in telescope_str:
                        diameter = 355.6  # mm
                    elif 'RC16' in telescope_str or '16"' in telescope_str:
                        diameter = 406.4  # mm
                    # Takahashi
                    elif 'FSQ-85' in telescope_str or 'FSQ85' in telescope_str or 'FSQ-85EDP' in telescope_str or 'FSQ85EDP' in telescope_str:
                        diameter = 85.0  # mm
                elif 'FSQ-106' in telescope_str or 'FSQ106' in telescope_str:
                    diameter = 106.0  # mm
                elif 'FSQ-130' in telescope_str or 'FSQ130' in telescope_str:
                    diameter = 130.0  # mm
                elif 'TOA-130' in telescope_str:
                    diameter = 130.0  # mm
                elif 'TOA-150' in telescope_str:
                    diameter = 150.0  # mm
                elif 'TOA-160' in telescope_str:
                    diameter = 160.0  # mm
                elif 'TSA-102' in telescope_str:
                    diameter = 102.0  # mm
                elif 'TSA-120' in telescope_str:
                    diameter = 120.0  # mm
                elif 'Epsilon-130' in telescope_str:
                    diameter = 130.0  # mm
                elif 'Epsilon-160' in telescope_str:
                    diameter = 160.0  # mm
                elif 'Epsilon-180' in telescope_str:
                    diameter = 180.0  # mm
                # PlaneWave
                elif 'CDK12' in telescope_str or '12"' in telescope_str:
                    diameter = 304.8  # mm
                elif 'CDK14' in telescope_str or '14"' in telescope_str:
                    diameter = 355.6  # mm
                elif 'CDK16' in telescope_str or '16"' in telescope_str:
                    diameter = 406.4  # mm
                elif 'CDK17' in telescope_str or '17"' in telescope_str:
                    diameter = 431.8  # mm
                elif 'CDK20' in telescope_str or '20"' in telescope_str:
                    diameter = 508.0  # mm
                elif 'CDK24' in telescope_str or '24"' in telescope_str:
                    diameter = 609.6  # mm
                elif 'L-350' in telescope_str:
                    diameter = 350.0  # mm
                elif 'L-500' in telescope_str:
                    diameter = 500.0  # mm
                elif 'L-600' in telescope_str:
                    diameter = 600.0  # mm
                # Celestron
                elif 'C8' in telescope_str or '8"' in telescope_str:
                    diameter = 203.2  # mm
                elif 'C9' in telescope_str or 'C9.25' in telescope_str or '9.25"' in telescope_str:
                    diameter = 235.0  # mm
                elif 'C11' in telescope_str or '11"' in telescope_str:
                    diameter = 279.4  # mm
                elif 'C14' in telescope_str or '14"' in telescope_str:
                    diameter = 355.6  # mm
                elif 'EDGEHD8' in telescope_str:
                    diameter = 203.2  # mm
                elif 'EDGEHD9.25' in telescope_str:
                    diameter = 235.0  # mm
                elif 'EDGEHD11' in telescope_str:
                    diameter = 279.4  # mm
                elif 'EDGEHD14' in telescope_str:
                    diameter = 355.6  # mm
                elif 'RASA8' in telescope_str:
                    diameter = 203.2  # mm
                elif 'RASA11' in telescope_str:
                    diameter = 279.4  # mm
                elif 'RASA14' in telescope_str:
                    diameter = 355.6  # mm
                elif 'STARIZON' in telescope_str:
                    diameter = 130.0  # mm
                elif 'STARIZON-130' in telescope_str:
                    diameter = 130.0  # mm
                elif 'STARIZON-150' in telescope_str:
                    diameter = 150.0  # mm
                elif 'STARIZON-180' in telescope_str:
                    diameter = 180.0  # mm
                # CFF (Classical Cassegrain)
                elif 'CFF160' in telescope_str:
                    diameter = 160.0  # mm
                elif 'CFF185' in telescope_str:
                    diameter = 185.0  # mm
                elif 'CFF200' in telescope_str:
                    diameter = 200.0  # mm
                elif 'CFF250' in telescope_str:
                    diameter = 250.0  # mm
                elif 'CFF300' in telescope_str:
                    diameter = 300.0  # mm
                elif 'CFF350' in telescope_str:
                    diameter = 350.0  # mm
                elif 'CFF400' in telescope_str:
                    diameter = 400.0  # mm
                elif 'CFF500' in telescope_str:
                    diameter = 500.0  # mm
                # TS-Optics Telescopes
                elif 'TS-APO65Q' in telescope_str or 'APO65Q' in telescope_str:
                    diameter = 65.0  # mm
                elif 'TS-APO80Q' in telescope_str or 'APO80Q' in telescope_str:
                    diameter = 80.0  # mm
                elif 'TS-APO102Q' in telescope_str or 'APO102Q' in telescope_str:
                    diameter = 102.0  # mm
                elif 'TS-APO115Q' in telescope_str or 'APO115Q' in telescope_str:
                    diameter = 115.0  # mm
                elif 'TS-APO130Q' in telescope_str or 'APO130Q' in telescope_str:
                    diameter = 130.0  # mm
                elif 'TS-APO140Q' in telescope_str or 'APO140Q' in telescope_str:
                    diameter = 140.0  # mm
                elif 'TS-APO150Q' in telescope_str or 'APO150Q' in telescope_str:
                    diameter = 150.0  # mm
                elif 'TS-APO160Q' in telescope_str or 'APO160Q' in telescope_str:
                    diameter = 160.0  # mm
                elif 'TS-APO180Q' in telescope_str or 'APO180Q' in telescope_str:
                    diameter = 180.0  # mm
                elif 'TS-APO200Q' in telescope_str or 'APO200Q' in telescope_str:
                    diameter = 200.0  # mm
                elif 'TS-APO250Q' in telescope_str or 'APO250Q' in telescope_str:
                    diameter = 250.0  # mm
                elif 'TS-APO300Q' in telescope_str or 'APO300Q' in telescope_str:
                    diameter = 300.0  # mm
                elif 'TS-APO350Q' in telescope_str or 'APO350Q' in telescope_str:
                    diameter = 350.0  # mm
                elif 'TS-APO400Q' in telescope_str or 'APO400Q' in telescope_str:
                    diameter = 400.0  # mm
                elif 'TS-APO500Q' in telescope_str or 'APO500Q' in telescope_str:
                    diameter = 500.0  # mm
                elif 'TS-APO600Q' in telescope_str or 'APO600Q' in telescope_str:
                    diameter = 600.0  # mm
                elif 'TS-APO700Q' in telescope_str or 'APO700Q' in telescope_str:
                    diameter = 700.0  # mm
                elif 'TS-APO800Q' in telescope_str or 'APO800Q' in telescope_str:
                    diameter = 800.0  # mm
                elif 'TS-APO900Q' in telescope_str or 'APO900Q' in telescope_str:
                    diameter = 900.0  # mm
                elif 'TS-APO1000Q' in telescope_str or 'APO1000Q' in telescope_str:
                    diameter = 1000.0  # mm
                # Askar Telescopes
                elif 'ASKAR-50PHQ' in telescope_str or '50PHQ' in telescope_str:
                    diameter = 50.0  # mm
                elif 'ASKAR-60PHQ' in telescope_str or '60PHQ' in telescope_str:
                    diameter = 60.0  # mm
                elif 'ASKAR-70PHQ' in telescope_str or '70PHQ' in telescope_str:
                    diameter = 70.0  # mm
                elif 'ASKAR-80PHQ' in telescope_str or '80PHQ' in telescope_str:
                    diameter = 80.0  # mm
                elif 'ASKAR-90PHQ' in telescope_str or '90PHQ' in telescope_str:
                    diameter = 90.0  # mm
                elif 'ASKAR-100PHQ' in telescope_str or '100PHQ' in telescope_str:
                    diameter = 100.0  # mm
                elif 'ASKAR-120PHQ' in telescope_str or '120PHQ' in telescope_str:
                    diameter = 120.0  # mm
                elif 'ASKAR-130PHQ' in telescope_str or '130PHQ' in telescope_str:
                    diameter = 130.0  # mm
                elif 'ASKAR-150PHQ' in telescope_str or '150PHQ' in telescope_str:
                    diameter = 150.0  # mm
                elif 'ASKAR-180PHQ' in telescope_str or '180PHQ' in telescope_str:
                    diameter = 180.0  # mm
                elif 'ASKAR-200PHQ' in telescope_str or '200PHQ' in telescope_str:
                    diameter = 200.0  # mm
                elif 'ASKAR-250PHQ' in telescope_str or '250PHQ' in telescope_str:
                    diameter = 250.0  # mm
                elif 'ASKAR-300PHQ' in telescope_str or '300PHQ' in telescope_str:
                    diameter = 300.0  # mm
                elif 'ASKAR-350PHQ' in telescope_str or '350PHQ' in telescope_str:
                    diameter = 350.0  # mm
                elif 'ASKAR-400PHQ' in telescope_str or '400PHQ' in telescope_str:
                    diameter = 400.0  # mm
                elif 'ASKAR-500PHQ' in telescope_str or '500PHQ' in telescope_str:
                    diameter = 500.0  # mm
                elif 'ASKAR-600PHQ' in telescope_str or '600PHQ' in telescope_str:
                    diameter = 600.0  # mm
                elif 'ASKAR-700PHQ' in telescope_str or '700PHQ' in telescope_str:
                    diameter = 700.0  # mm
                elif 'ASKAR-800PHQ' in telescope_str or '800PHQ' in telescope_str:
                    diameter = 800.0  # mm
                elif 'ASKAR-900PHQ' in telescope_str or '900PHQ' in telescope_str:
                    diameter = 900.0  # mm
                elif 'ASKAR-1000PHQ' in telescope_str or '1000PHQ' in telescope_str:
                    diameter = 1000.0  # mm
                # Askar FRA Series (f/5.5)
                elif 'ASKAR-FRA300' in telescope_str or 'FRA300' in telescope_str:
                    diameter = 300.0  # mm
                elif 'ASKAR-FRA400' in telescope_str or 'FRA400' in telescope_str:
                    diameter = 400.0  # mm
                elif 'ASKAR-FRA500' in telescope_str or 'FRA500' in telescope_str:
                    diameter = 500.0  # mm
                elif 'ASKAR-FRA600' in telescope_str or 'FRA600' in telescope_str:
                    diameter = 600.0  # mm
                elif 'ASKAR-FRA700' in telescope_str or 'FRA700' in telescope_str:
                    diameter = 700.0  # mm
                elif 'ASKAR-FRA800' in telescope_str or 'FRA800' in telescope_str:
                    diameter = 800.0  # mm
                else:
                    # Unrecognized telescope, use retrieval function
                    try:
                        telescope_characteristics = get_telescope_characteristics(telescope)
                        diameter = telescope_characteristics['diameter_mm']
                    except Exception as e:
                        print(f"Warning: Error getting telescope characteristics: {e}")
                        diameter = 200.0  # Default diameter
            
            # Extract focal length
            focal_length = None
            focal_keywords = ['FOCALLEN', 'FOCAL_LENGTH', 'FOCAL', 'FL']
            for keyword in focal_keywords:
                if keyword in header:
                    try:
                        focal_length = float(header[keyword])
                        break
                    except Exception:
                        pass
            
            # If not found, try to deduce from telescope name
            if focal_length is None:
                telescope_str = str(telescope).upper()
                # Ritchey-Chrétien (RC)
                if 'RC8' in telescope_str:
                    focal_length = 1625.6  # mm (f/8)
                elif 'RC6' in telescope_str:
                    focal_length = 1219.2  # mm (f/8)
                elif 'RC10' in telescope_str:
                    focal_length = 2032.0  # mm (f/8)
                elif 'RC12' in telescope_str:
                    focal_length = 2438.4  # mm (f/8)
                elif 'RC14' in telescope_str:
                    focal_length = 2844.8  # mm (f/8)
                elif 'RC16' in telescope_str:
                    focal_length = 3251.2  # mm (f/8)
                # Takahashi
                elif 'FSQ-85' in telescope_str or 'FSQ85' in telescope_str or 'FSQ-85EDP' in telescope_str or 'FSQ85EDP' in telescope_str:
                    focal_length = 455.0  # mm (f/5.35)
                elif 'FSQ-106' in telescope_str or 'FSQ106' in telescope_str:
                    focal_length = 530.0  # mm (f/5)
                elif 'FSQ-130' in telescope_str or 'FSQ130' in telescope_str:
                    focal_length = 650.0  # mm (f/5)
                elif 'TOA-130' in telescope_str:
                    focal_length = 1000.0  # mm (f/7.7)
                elif 'TOA-150' in telescope_str:
                    focal_length = 1100.0  # mm (f/7.3)
                elif 'TOA-160' in telescope_str:
                    focal_length = 1200.0  # mm (f/7.5)
                elif 'TSA-102' in telescope_str:
                    focal_length = 816.0  # mm (f/8)
                elif 'TSA-120' in telescope_str:
                    focal_length = 900.0  # mm (f/7.5)
                elif 'Epsilon-130' in telescope_str:
                    focal_length = 430.0  # mm (f/3.3)
                elif 'Epsilon-160' in telescope_str:
                    focal_length = 530.0  # mm (f/3.3)
                elif 'Epsilon-180' in telescope_str:
                    focal_length = 600.0  # mm (f/3.3)
                # PlaneWave
                elif 'CDK12' in telescope_str:
                    focal_length = 2438.4  # mm (f/8)
                elif 'CDK14' in telescope_str:
                    focal_length = 2844.8  # mm (f/8)
                elif 'CDK16' in telescope_str:
                    focal_length = 3251.2  # mm (f/8)
                elif 'CDK17' in telescope_str:
                    focal_length = 3454.4  # mm (f/8)
                elif 'CDK20' in telescope_str:
                    focal_length = 4064.0  # mm (f/8)
                elif 'CDK24' in telescope_str:
                    focal_length = 4876.8  # mm (f/8)
                elif 'L-350' in telescope_str:
                    focal_length = 2450.0  # mm (f/7)
                elif 'L-500' in telescope_str:
                    focal_length = 3500.0  # mm (f/7)
                elif 'L-600' in telescope_str:
                    focal_length = 4200.0  # mm (f/7)
                # Celestron
                elif 'C8' in telescope_str:
                    focal_length = 2032.0  # mm (f/10)
                elif 'C9' in telescope_str or 'C9.25' in telescope_str:
                    focal_length = 2350.0  # mm (f/10)
                elif 'C11' in telescope_str:
                    focal_length = 2794.0  # mm (f/10)
                elif 'C14' in telescope_str:
                    focal_length = 3910.0  # mm (f/11)
                elif 'EDGEHD8' in telescope_str:
                    focal_length = 2032.0  # mm (f/10)
                elif 'EDGEHD9.25' in telescope_str:
                    focal_length = 2350.0  # mm (f/10)
                elif 'EDGEHD11' in telescope_str:
                    focal_length = 2794.0  # mm (f/10)
                elif 'EDGEHD14' in telescope_str:
                    focal_length = 3910.0  # mm (f/11)
                elif 'RASA8' in telescope_str:
                    focal_length = 400.0  # mm (f/2)
                elif 'RASA11' in telescope_str:
                    focal_length = 620.0  # mm (f/2.2)
                elif 'RASA14' in telescope_str:
                    focal_length = 780.0  # mm (f/2.2)
                elif 'STARIZON' in telescope_str:
                    focal_length = 650.0  # mm (f/5)
                elif 'STARIZON-130' in telescope_str:
                    focal_length = 650.0  # mm (f/5)
                elif 'STARIZON-150' in telescope_str:
                    focal_length = 750.0  # mm (f/5)
                elif 'STARIZON-180' in telescope_str:
                    focal_length = 900.0  # mm (f/5)
                # CFF (Classical Cassegrain)
                elif 'CFF160' in telescope_str:
                    focal_length = 1280.0  # mm (f/8)
                elif 'CFF185' in telescope_str:
                    focal_length = 1480.0  # mm (f/8)
                elif 'CFF200' in telescope_str:
                    focal_length = 1600.0  # mm (f/8)
                elif 'CFF250' in telescope_str:
                    focal_length = 2000.0  # mm (f/8)
                elif 'CFF300' in telescope_str:
                    focal_length = 2400.0  # mm (f/8)
                elif 'CFF350' in telescope_str:
                    focal_length = 2800.0  # mm (f/8)
                elif 'CFF400' in telescope_str:
                    focal_length = 3200.0  # mm (f/8)
                elif 'CFF500' in telescope_str:
                    focal_length = 4000.0  # mm (f/8)
                # TS-Optics Telescopes (f/6.5 for most)
                elif 'TS-APO65Q' in telescope_str or 'APO65Q' in telescope_str:
                    focal_length = 422.5  # mm (f/6.5)
                elif 'TS-APO80Q' in telescope_str or 'APO80Q' in telescope_str:
                    focal_length = 520.0  # mm (f/6.5)
                elif 'TS-APO102Q' in telescope_str or 'APO102Q' in telescope_str:
                    focal_length = 663.0  # mm (f/6.5)
                elif 'TS-APO115Q' in telescope_str or 'APO115Q' in telescope_str:
                    focal_length = 747.5  # mm (f/6.5)
                elif 'TS-APO130Q' in telescope_str or 'APO130Q' in telescope_str:
                    focal_length = 845.0  # mm (f/6.5)
                elif 'TS-APO140Q' in telescope_str or 'APO140Q' in telescope_str:
                    focal_length = 910.0  # mm (f/6.5)
                elif 'TS-APO150Q' in telescope_str or 'APO150Q' in telescope_str:
                    focal_length = 975.0  # mm (f/6.5)
                elif 'TS-APO160Q' in telescope_str or 'APO160Q' in telescope_str:
                    focal_length = 1040.0  # mm (f/6.5)
                elif 'TS-APO180Q' in telescope_str or 'APO180Q' in telescope_str:
                    focal_length = 1170.0  # mm (f/6.5)
                elif 'TS-APO200Q' in telescope_str or 'APO200Q' in telescope_str:
                    focal_length = 1300.0  # mm (f/6.5)
                elif 'TS-APO250Q' in telescope_str or 'APO250Q' in telescope_str:
                    focal_length = 1625.0  # mm (f/6.5)
                elif 'TS-APO300Q' in telescope_str or 'APO300Q' in telescope_str:
                    focal_length = 1950.0  # mm (f/6.5)
                elif 'TS-APO350Q' in telescope_str or 'APO350Q' in telescope_str:
                    focal_length = 2275.0  # mm (f/6.5)
                elif 'TS-APO400Q' in telescope_str or 'APO400Q' in telescope_str:
                    focal_length = 2600.0  # mm (f/6.5)
                elif 'TS-APO500Q' in telescope_str or 'APO500Q' in telescope_str:
                    focal_length = 3250.0  # mm (f/6.5)
                elif 'TS-APO600Q' in telescope_str or 'APO600Q' in telescope_str:
                    focal_length = 3900.0  # mm (f/6.5)
                elif 'TS-APO700Q' in telescope_str or 'APO700Q' in telescope_str:
                    focal_length = 4550.0  # mm (f/6.5)
                elif 'TS-APO800Q' in telescope_str or 'APO800Q' in telescope_str:
                    focal_length = 5200.0  # mm (f/6.5)
                elif 'TS-APO900Q' in telescope_str or 'APO900Q' in telescope_str:
                    focal_length = 5850.0  # mm (f/6.5)
                elif 'TS-APO1000Q' in telescope_str or 'APO1000Q' in telescope_str:
                    focal_length = 6500.0  # mm (f/6.5)
                # Askar Telescopes (f/5.6 for most)
                elif 'ASKAR-50PHQ' in telescope_str or '50PHQ' in telescope_str:
                    focal_length = 280.0  # mm (f/5.6)
                elif 'ASKAR-60PHQ' in telescope_str or '60PHQ' in telescope_str:
                    focal_length = 336.0  # mm (f/5.6)
                elif 'ASKAR-70PHQ' in telescope_str or '70PHQ' in telescope_str:
                    focal_length = 392.0  # mm (f/5.6)
                elif 'ASKAR-80PHQ' in telescope_str or '80PHQ' in telescope_str:
                    focal_length = 448.0  # mm (f/5.6)
                elif 'ASKAR-90PHQ' in telescope_str or '90PHQ' in telescope_str:
                    focal_length = 504.0  # mm (f/5.6)
                elif 'ASKAR-100PHQ' in telescope_str or '100PHQ' in telescope_str:
                    focal_length = 560.0  # mm (f/5.6)
                elif 'ASKAR-120PHQ' in telescope_str or '120PHQ' in telescope_str:
                    focal_length = 672.0  # mm (f/5.6)
                elif 'ASKAR-130PHQ' in telescope_str or '130PHQ' in telescope_str:
                    focal_length = 728.0  # mm (f/5.6)
                elif 'ASKAR-150PHQ' in telescope_str or '150PHQ' in telescope_str:
                    focal_length = 840.0  # mm (f/5.6)
                elif 'ASKAR-180PHQ' in telescope_str or '180PHQ' in telescope_str:
                    focal_length = 1008.0  # mm (f/5.6)
                elif 'ASKAR-200PHQ' in telescope_str or '200PHQ' in telescope_str:
                    focal_length = 1120.0  # mm (f/5.6)
                elif 'ASKAR-250PHQ' in telescope_str or '250PHQ' in telescope_str:
                    focal_length = 1400.0  # mm (f/5.6)
                elif 'ASKAR-300PHQ' in telescope_str or '300PHQ' in telescope_str:
                    focal_length = 1680.0  # mm (f/5.6)
                elif 'ASKAR-350PHQ' in telescope_str or '350PHQ' in telescope_str:
                    focal_length = 1960.0  # mm (f/5.6)
                elif 'ASKAR-400PHQ' in telescope_str or '400PHQ' in telescope_str:
                    focal_length = 2240.0  # mm (f/5.6)
                elif 'ASKAR-500PHQ' in telescope_str or '500PHQ' in telescope_str:
                    focal_length = 2800.0  # mm (f/5.6)
                elif 'ASKAR-600PHQ' in telescope_str or '600PHQ' in telescope_str:
                    focal_length = 3360.0  # mm (f/5.6)
                elif 'ASKAR-700PHQ' in telescope_str or '700PHQ' in telescope_str:
                    focal_length = 3920.0  # mm (f/5.6)
                elif 'ASKAR-800PHQ' in telescope_str or '800PHQ' in telescope_str:
                    focal_length = 4480.0  # mm (f/5.6)
                elif 'ASKAR-900PHQ' in telescope_str or '900PHQ' in telescope_str:
                    focal_length = 5040.0  # mm (f/5.6)
                elif 'ASKAR-1000PHQ' in telescope_str or '1000PHQ' in telescope_str:
                    focal_length = 5600.0  # mm (f/5.6)
                # Askar FRA Series (f/5.5)
                elif 'ASKAR-FRA300' in telescope_str or 'FRA300' in telescope_str:
                    focal_length = 1650.0  # mm (f/5.5)
                elif 'ASKAR-FRA400' in telescope_str or 'FRA400' in telescope_str:
                    focal_length = 2200.0  # mm (f/5.5)
                elif 'ASKAR-FRA500' in telescope_str or 'FRA500' in telescope_str:
                    focal_length = 2750.0  # mm (f/5.5)
                elif 'ASKAR-FRA600' in telescope_str or 'FRA600' in telescope_str:
                    focal_length = 3300.0  # mm (f/5.5)
                elif 'ASKAR-FRA700' in telescope_str or 'FRA700' in telescope_str:
                    focal_length = 3850.0  # mm (f/5.5)
                elif 'ASKAR-FRA800' in telescope_str or 'FRA800' in telescope_str:
                    focal_length = 4400.0  # mm (f/5.5)
                else:
                    # Focal length not recognized, use telescope if already requested or ask
                    if 'telescope_characteristics' in locals():
                        focal_length = telescope_characteristics['focal_length_mm']
                    else:
                        telescope_characteristics = get_telescope_characteristics(telescope)
                        focal_length = telescope_characteristics['focal_length_mm']
            
            # Calculate aperture (f-number)
            f_number = focal_length / diameter if diameter and diameter > 0 else 8.0
            
            # Additional information
            additional_info = {
                'date_obs': header.get('DATE-OBS', header.get('DATE', 'Unknown')),
                'instrument': instrument,
                'telescope': telescope,
                'diameter_mm': diameter,
                'focal_length_mm': focal_length,
                'f_number': f_number,
                'gain': header.get('GAIN', None),
                'temperature': header.get('CCD-TEMP', None),
                'binning': f"{header.get('XBINNING', 1)}x{header.get('YBINNING', 1)}",
                'pixel_scale': header.get('PIXSCALE', None)
            }
            
            # Advanced analysis (intelligent sampling)
            photons_info = None
            advanced_snr_info = None
            
            if image_type == 'LIGHT' and filter_found and ADU_ANALYSIS_ENABLED and should_analyze_adu:
                # Automatically detect sensor from FITS header
                detected_sensor = detect_sensor_from_fits_header(file_path)
                
                # Use detected sensor or instrument one
                sensor_name = detected_sensor if detected_sensor else instrument
                
                # Get sensor characteristics
                try:
                    sensor_characteristics = get_sensor_characteristics(sensor_name)
                except Exception as e:
                    print(f"Warning: Error getting sensor characteristics: {e}")
                    sensor_characteristics = SENSORS_DATABASE['default']
                
                # Search for calibration files
                bias_files, dark_files = find_calibration_files(BIAS_DARK_PATH, exposure_time, sensor_characteristics.get('gain'), sensor_name)
                bias_path = bias_files[0] if bias_files else None
                dark_path = dark_files[0] if dark_files else None
                
                # Advanced SNR calculation with calibration
                advanced_snr_info = calculate_advanced_snr(file_path, sensor_characteristics, dark_path, bias_path)
                
                # Advanced analysis completed
            elif image_type == 'LIGHT' and filter_found and not ADU_ANALYSIS_ENABLED:
                # Fast mode: no advanced analysis
                pass
            elif image_type == 'LIGHT' and filter_found and ADU_ANALYSIS_ENABLED and not should_analyze_adu:
                # Fast mode: no advanced analysis
                pass
            else:
                # Skip files (fast mode)
                pass
            
            # Extract observation date
            observation_date = extract_observation_date(file_path, additional_info)
            
            return {
                'type': image_type,
                'filter': filter_found,
                'exposure_time': exposure_time,
                'target': target_found,
                'ra': ra,
                'dec': dec,
                'observation_date': observation_date,
                'info': additional_info,
                'adu_photons': photons_info,
                'advanced_snr': advanced_snr_info
            }
            
    except Exception as e:
        # Handle specific FITS file issues
        if "Header missing END card" in str(e):
            print(f"⚠️  Skipping {file_path.name}: Corrupted FITS header (missing END card)")
        elif "non-ASCII characters" in str(e):
            print(f"⚠️  Skipping {file_path.name}: Non-ASCII characters in header")
        elif "null bytes" in str(e):
            print(f"⚠️  Skipping {file_path.name}: Non-compliant FITS header (null bytes)")
        else:
            print(f"Error reading {file_path.name}: {e}")
        return None

def process_file_info(info, file, data_by_target, global_data, is_adu_sample=False):
    """
    Processes FITS file information and adds it to collected data
    Also counts file types for statistics
    """
    # Count file types for valid files (only count once per file)
    if 'file_types' in global_data:
        file_path_str = str(file).lower()
        if file_path_str.endswith('.fits.fz'):
            global_data['file_types']['fits.fz'] += 1
        elif file_path_str.endswith('.fits'):
            global_data['file_types']['fits'] += 1
        elif file_path_str.endswith('.fit'):
            global_data['file_types']['fit'] += 1
        elif file_path_str.endswith('.xisf'):
            global_data['file_types']['xisf'] += 1
        elif file_path_str.endswith('.xifs'):
            global_data['file_types']['xifs'] += 1
        elif file_path_str.endswith('.xif'):
            global_data['file_types']['xif'] += 1
    
    if not info or info['type'] in ['FLAT', 'BIAS', 'DARK'] or 'FLATWIZARD' in str(info['info']['instrument']).upper():
        # Silently skip calibration files (FLAT, BIAS, DARK, FLATWIZARD)
        # Accept all other files even without exposure_time
        return
    
    # Ensure filter is set (use appropriate default based on context)
    if not info['filter'] or info['filter'] == 'Unknown':
        # Check if this is a color camera file (Bayer matrix detection)
        if info.get('is_color', False):
            info['filter'] = 'RGB'  # One Shot Color
        else:
            # Check if this is likely a color camera file based on filename/path
            filename_lower = str(file).lower()
            osc_indicators = ['color', 'colour', 'osc', 'one shot', 'oneshot', 'rgb', 'camera', 'cam']
            if any(indicator in filename_lower for indicator in osc_indicators):
                info['filter'] = 'RGB'  # One Shot Color
            else:
                info['filter'] = 'L'  # Default to Luminance for monochrome cameras
    
    # Determine target with case-insensitive normalization
    target = info['target'] or file.parent.name
    if not target or target == 'Unknown':
        target = file.parent.name
    
    # Normalize target name (case-insensitive, remove extra spaces)
    target = normalize_target_name(target)
    
    # Add to target data (check for duplicates)
    file_data = {
        'name': file.name,
        'path': str(file),
        'info': info
    }
    
    # Check if file already exists to avoid duplication
    existing_files = [f.get('name', '') for f in data_by_target[target]['files']]
    if file.name not in existing_files:
        data_by_target[target]['files'].append(file_data)
    else:
        return  # Skip processing this duplicate file
    
    # Group by observation date (normalize so one key per night, same as LaTeX/HTML)
    obs_date = normalize_night_date(info.get('observation_date')) or info.get('observation_date')
    if not obs_date and info.get('observation_date'):
        obs_date = info['observation_date']
    if 'files_by_date' not in data_by_target[target]:
        data_by_target[target]['files_by_date'] = {}
    
    if obs_date not in data_by_target[target]['files_by_date']:
        data_by_target[target]['files_by_date'][obs_date] = {
            'files': [],
            'time_by_filter': {},
            'exposure_details': {},  # New: detailed exposure times per filter
            'total_time': 0
        }
    
    # Add file to date group (only for LIGHT files)
    if info['type'] == 'LIGHT':
        # Don't add file_data to files_by_date['files'] to avoid duplication
        # The file is already in data_by_target[target]['files']
        
        # Add to time_by_filter for this date
        filter_name = info['filter']
        if filter_name not in data_by_target[target]['files_by_date'][obs_date]['time_by_filter']:
            data_by_target[target]['files_by_date'][obs_date]['time_by_filter'][filter_name] = []
        
        exposure_time = info.get('exposure_time') or 0  # Use 0 if None
        data_by_target[target]['files_by_date'][obs_date]['time_by_filter'][filter_name].append(exposure_time)
        data_by_target[target]['files_by_date'][obs_date]['total_time'] += exposure_time
        
        # Store detailed exposure information
        if filter_name not in data_by_target[target]['files_by_date'][obs_date]['exposure_details']:
            data_by_target[target]['files_by_date'][obs_date]['exposure_details'][filter_name] = {}
        
        if exposure_time not in data_by_target[target]['files_by_date'][obs_date]['exposure_details'][filter_name]:
            data_by_target[target]['files_by_date'][obs_date]['exposure_details'][filter_name][exposure_time] = 0
        
        data_by_target[target]['files_by_date'][obs_date]['exposure_details'][filter_name][exposure_time] += 1
    
    # Only include LIGHT files in statistics (exclude bias, dark, flat)
    if info['type'] == 'LIGHT':
        # Add to global time_by_filter for graph generation
        filter_name = info['filter']
        if filter_name not in data_by_target[target]['time_by_filter']:
            data_by_target[target]['time_by_filter'][filter_name] = []
        exposure_time = info.get('exposure_time') or 0  # Use 0 if None
        data_by_target[target]['time_by_filter'][filter_name].append(exposure_time)
        
        if info['info']['instrument'] != 'Unknown':
            data_by_target[target]['instruments'].add(info['info']['instrument'])
        if info['info']['telescope'] != 'Unknown':
            data_by_target[target]['telescopes'].add(info['info']['telescope'])
        
        data_by_target[target]['dates'].add(info['info']['date_obs'])
        data_by_target[target]['apertures'].add(info['info']['f_number'])
        data_by_target[target]['diameters'].add(info['info']['diameter_mm'])
        data_by_target[target]['focal_lengths'].add(info['info']['focal_length_mm'])
        
        if info['ra'] and info['dec']:
            data_by_target[target]['coordinates'].append((info['ra'], info['dec']))
    
    # Calculate received light for LIGHT images
    if info['type'] == 'LIGHT' and info['filter'] in FILTERS_INFO:
        # Collect samples for statistical analysis
        if is_adu_sample and info.get('adu_photons') and info['adu_photons']:
            data_by_target[target]['adu_samples'][info['filter']].append({
                'file': file.name,
                'adu_photons': info['adu_photons']['total_photons'],
                'exposure_time': info.get('exposure_time') or 0,
                'adu_stats': info['adu_photons']
            })
            data_by_target[target]['adu_counter_by_filter'][info['filter']] += 1
            print(f"   Sample collected: {info['adu_photons']['total_photons']:.2e} photons")
            print(f"   Sample {data_by_target[target]['adu_counter_by_filter'][info['filter']]}/{ADU_SAMPLE_PER_FILTER} for filter {info['filter']}")
        
        # Light calculation removed (photon analysis disabled)
        # Store basic exposure information instead
        light = {
            'exposure_time': info.get('exposure_time') or 0,
            'filter': info['filter'],
            'diameter_mm': info['info'].get('diameter_mm', 200.0),
            'source': 'basic_info'
        }
        
        data_by_target[target]['received_light'][info['filter']].append(light)
    
    # Update global data
    global_data['found_targets'].add(target)
    global_data['used_instruments'].add(info['info']['instrument'])
    global_data['used_telescopes'].add(info['info']['telescope'])
    exposure_time = info.get('exposure_time') or 0  # Use 0 if None
    global_data['total_time'] += exposure_time
    
    if info['ra'] and info['dec']:
        global_data['sky_regions'].append((info['ra'], info['dec']))
    
    print(f"✅ {target} - {file.name}")
    exposure_time_display = info.get('exposure_time') or 0
    print(f"   📷 {info['type']} | 🎨 {info['filter']} | ⏱️  {format_time(exposure_time_display)}")
    print(f"   🔧 {info['info']['instrument']} | 🔭 {info['info']['telescope']} | 📏 f/{info['info']['f_number']:.1f}")

def _process_file_phase3(file):
    """Process single file for Phase 3 (parallelizable)
    
    Uses cached header info from Phase 2 (signature reading) if available,
    otherwise reads the header directly.
    
    Filters out calibration frames (FLAT, DARK, BIAS) using the cached type.
    """
    try:
        # Check if we have cached info from the signature reading phase
        cached_info = get_cached_header_info(file)
        
        if cached_info:
            # Use cached info - much faster!
            # Check for calibration frames using cached type
            cached_type = cached_info.get('type', 'LIGHT')
            if cached_type in ['FLAT', 'DARK', 'BIAS']:
                return None  # Skip calibration frames
            
            # Check for FLATWIZARD in instrument
            instrument = cached_info.get('instrument', '')
            if 'FLATWIZARD' in str(instrument).upper():
                return None  # Skip FlatWizard frames
            
            target = cached_info.get('object') or cached_info.get('target', '')
            filter_name = cached_info.get('filter', '')
            
            if not target:
                target = file.parent.name if hasattr(file, 'parent') else Path(file).parent.name
            
            # Normalize target name
            target = normalize_target_name(target)
            
            # Handle missing filter
            if not filter_name or filter_name == 'Unknown' or filter_name == '':
                filename_lower = str(file).lower()
                osc_indicators = ['color', 'colour', 'osc', 'one shot', 'oneshot', 'rgb', 'camera', 'cam']
                if any(indicator in filename_lower for indicator in osc_indicators):
                    filter_name = 'OSC'
                else:
                    filter_name = 'L'
            
            return {
                'target': target,
                'filter': filter_name,
                'file': file,
                'info': cached_info
            }
        
        # Fallback: read header directly (slower but complete)
        basic_info = extract_fits_header_info_fast(file)
        
        # If fast extraction fails for XISF, try reading as FITS (misnamed file)
        if basic_info is None and str(file).lower().endswith(('.xisf', '.xifs', '.xif')):
            try:
                if ASTROPY_AVAILABLE:
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter('ignore')
                        try:
                            header = fits.getheader(str(file), ext=0)
                        except Exception:
                            header = None
                    if header is not None:
                        # Extract minimal info from header
                        image_type = 'LIGHT'
                        if 'IMAGETYP' in header:
                            value = str(header['IMAGETYP']).upper()
                            if 'FLAT' in value: image_type = 'FLAT'
                            elif 'DARK' in value: image_type = 'DARK'
                            elif 'BIAS' in value: image_type = 'BIAS'
                        
                        filter_found = 'Unknown'
                        if 'FILTER' in header:
                            filter_found = str(header['FILTER']).strip().upper()
                        
                        target = None
                        if 'OBJECT' in header:
                            target = str(header['OBJECT']).strip()
                        
                        basic_info = {
                            'exposure_time': float(header.get('EXPTIME', 0) or 0),
                            'type': image_type,
                            'filter': filter_found,
                            'target': target,
                            'info': {
                                'instrument': str(header.get('INSTRUME', 'Unknown')),
                                'telescope': str(header.get('TELESCOP', 'Unknown')),
                                'date_obs': header.get('DATE-OBS', 'Unknown')
                            }
                        }
            except Exception:
                pass
        
        if basic_info and basic_info['type'] not in ['FLAT', 'DARK', 'BIAS'] and 'FLATWIZARD' not in str(basic_info['info']['instrument']).upper():
            # Ensure filter is set
            if not basic_info['filter'] or basic_info['filter'] == 'Unknown':
                if basic_info.get('is_color', False):
                    basic_info['filter'] = 'OSC'
                else:
                    # Check filename for OSC indicators
                    filename_lower = str(file).lower()
                    osc_indicators = ['color', 'colour', 'osc', 'one shot', 'oneshot', 'rgb', 'camera', 'cam']
                    if any(indicator in filename_lower for indicator in osc_indicators):
                        basic_info['filter'] = 'OSC'
                    else:
                        basic_info['filter'] = 'L'
            
            # Get target name
            target = basic_info['target'] or file.parent.name
            if not target or target == 'Unknown':
                target = file.parent.name
            
            # Normalize target name
            target = normalize_target_name(target)
            
            return {
                'target': target,
                'filter': basic_info['filter'],
                'file': file,
                'info': basic_info
            }
    except Exception as e:
        return None
    return None

def _process_file(task):
    """Process single file for Phase 2 (parallelizable)"""
    file_str, do_adu = task
    try:
        p = Path(file_str)
        # Remove debug print to avoid interfering with tqdm
        info = extract_fits_header_info(p, should_analyze_adu=do_adu)
        return (file_str, info, do_adu)
    except Exception as e:
        # Handle specific FITS file issues silently to avoid spam
        error_msg = str(e)
        if "Header missing END card" in error_msg or "non-ASCII characters" in error_msg or "null bytes" in error_msg:
            # Skip problematic files silently
            return (file_str, None, do_adu)
        elif "does not appear to be a valid" in error_msg.lower() or "signature" in error_msg.lower():
            # XISF/XIFS/XIF signature issues - try as FITS
            try:
                # Force open as FITS even if extension suggests XISF
                info = extract_fits_header_info(p, should_analyze_adu=do_adu)
                return (file_str, info, do_adu)
            except Exception:
                return (file_str, None, do_adu)
        else:
            # For other errors, return None to indicate failure
            return (file_str, None, do_adu)

def analyze_folder_recursive(root_folder, workers=1, check_abort=None):
    """Recursively analyzes all subfolders (parallelizable via workers).
    If check_abort is a callable that returns True, analysis stops and returns None."""
    global ADU_ANALYSIS_ENABLED, ADU_SAMPLE_PER_FILTER, FAST_ANALYSIS
    
    # Handle None workers (fallback to auto-detection)
    if workers is None:
        import multiprocessing
        try:
            workers = multiprocessing.cpu_count()
            if workers <= 0:
                workers = 1  # Fallback for invalid CPU count
        except (OSError, NotImplementedError):
            # Fallback for systems where CPU count detection fails
            workers = 1
    
    
    if not ASTROPY_AVAILABLE:
        print("ERROR: Astropy is not installed. Cannot continue.")
        print("   Install with: pip install astropy")
        return None
    
    folder_path = Path(root_folder)
    if not folder_path.exists():
        print(f"ERROR: Folder '{root_folder}' does not exist.")
        return None
    
    # Data structure to organize results
    data_by_target = defaultdict(lambda: {
        'files': [],
        'time_by_filter': defaultdict(list),
        'time_by_type': defaultdict(list),
        'instruments': set(),
        'telescopes': set(),
        'dates': set(),
        'coordinates': [],
        'apertures': set(),
        'diameters': set(),
        'focal_lengths': set(),
        'received_light': defaultdict(list),
        'adu_samples': defaultdict(list),  # To store ADU samples by filter
        'adu_counter_by_filter': defaultdict(int)  # To count ADU samples by filter
    })
    
    global_data = {
        'total_files': 0,
        'found_targets': set(),
        'used_instruments': set(),
        'used_telescopes': set(),
        'sky_regions': [],
        'total_time': 0,
        'total_light': 0,
        'file_types': {
            'fits': 0,
            'fit': 0,
            'fits.fz': 0,
            'xisf': 0,
            'xifs': 0,
            'xif': 0
        }
    }
    
    # Recursive traversal (case-insensitive on Windows; avoid duplicates)
    # OPTIMIZED: Use os.walk for single-pass traversal (much faster than multiple rglob calls)
    # This avoids scanning the filesystem 6 times
    # Also combine case-insensitive deduplication in the same pass for better performance
    if SYSTEM_LANGUAGE == 'fr':
        print("=" * 60)
        print("📂 PHASE 1 : RECHERCHE DES FICHIERS")
        print("=" * 60)
        print("🔍 Recherche des fichiers FITS/XISF (toutes extensions, insensible à la casse)...")
        print("   Extensions supportées: .fits .fit .fits.fz .xisf .xifs .xif (et MAJUSCULES)")
    else:
        print("=" * 60)
        print("📂 PHASE 1: SEARCHING FILES")
        print("=" * 60)
        print("🔍 Searching for FITS/XISF files (all extensions, case-insensitive)...")
        print("   Supported extensions: .fits .fit .fits.fz .xisf .xifs .xif (and UPPERCASE)")
    
    # All supported extensions (case-insensitive matching via .lower())
    # This tuple is used with str.endswith() after lowercasing the filename
    fits_extensions = ('.fit', '.fits', '.fits.fz', '.xisf', '.xifs', '.xif')
    fits_files = []
    _seen_paths = set()  # For case-insensitive deduplication
    extension_counts = {}  # Count files by original extension (preserves case)
    
    for root, dirs, files in os.walk(folder_path):
        if check_abort and callable(check_abort) and check_abort():
            return None
        for file in files:
            file_lower = file.lower()
            # Check all extensions (case-insensitive)
            if file_lower.endswith(fits_extensions):
                file_path = Path(root) / file
                # Deduplicate by lowercase absolute path in the same pass
                path_key = str(file_path).lower()
                if path_key not in _seen_paths:
                    _seen_paths.add(path_key)
                    fits_files.append(file_path)
                    
                    # Count original extension (preserves case info)
                    for ext in ['.fits.fz', '.FITS.FZ', '.fits.gz', '.FITS.GZ',
                               '.fits', '.FITS', '.Fits',
                               '.fit', '.FIT', '.Fit',
                               '.xisf', '.XISF', '.Xisf',
                               '.xifs', '.XIFS', '.Xifs',
                               '.xif', '.XIF', '.Xif']:
                        if file.endswith(ext):
                            ext_key = ext.lower()
                            extension_counts[ext_key] = extension_counts.get(ext_key, 0) + 1
                            break
    
    if SYSTEM_LANGUAGE == 'fr':
        print(f"   ✓ {len(fits_files)} fichier(s) unique(s) trouvé(s)")
        if extension_counts:
            ext_str = ", ".join([f"{ext}: {count}" for ext, count in sorted(extension_counts.items())])
            print(f"   📊 Répartition: {ext_str}")
    else:
        print(f"   ✓ {len(fits_files)} unique file(s) found")
        if extension_counts:
            ext_str = ", ".join([f"{ext}: {count}" for ext, count in sorted(extension_counts.items())])
            print(f"   📊 Distribution: {ext_str}")
    
    # Remove compressed duplicates (prefer .fits over .xisf over .xifs over .xif over .fits.fz)
    # Also detects content-based duplicates across different folders
    if SYSTEM_LANGUAGE == 'fr':
        print("🔍 Déduplication intelligente (par nom ET par contenu)...")
    else:
        print("🔍 Intelligent deduplication (by name AND content)...")
    
    if check_abort and callable(check_abort) and check_abort():
        return None
    fits_files_before = len(fits_files)
    fits_files = remove_compressed_duplicates(fits_files, check_abort=check_abort)
    if fits_files is None:
        return None  # User stopped during Phase 2
    fits_files_after = len(fits_files)
    global_data['files_after_dedup'] = fits_files_after  # pour message correct si 0 LIGHT
    if fits_files_before != fits_files_after:
        print(f"   ✓ {fits_files_after} fichier(s) retenu(s) ({fits_files_before - fits_files_after} doublon(s) supprimé(s))")
    else:
        if SYSTEM_LANGUAGE == 'fr':
            print(f"   ✓ {fits_files_after} fichier(s) (aucun doublon détecté)")
        else:
            print(f"   ✓ {fits_files_after} file(s) (no duplicates detected)")
    
    if SYSTEM_LANGUAGE == 'fr':
        print(f"ANALYSE ASTROPHOTOGRAPHIQUE COMPLÈTE")
        print("=" * 80)
        print(f"Dossier racine: {root_folder}")
        print(f"Fichiers FITS trouvés: {len(fits_files)}")
        print("-" * 80)
        if not ADU_ANALYSIS_ENABLED:
            pass
        elif ADU_SAMPLE_PER_FILTER == float('inf'):
            print("Mode COMPLET: Analyse rapide de tous les fichiers")
            print("Calcul des photons: Théorique (mode rapide)")
        else:
            print(f"Mode PARTIEL: Analyse de {ADU_SAMPLE_PER_FILTER} échantillons par filtre")
            print("Analyse: Informations d'exposition de base uniquement")
            print("Optimisations: Échantillonnage 1% des pixels")
    else:
        print(f"COMPLETE ASTROPHOTOGRAPHY ANALYSIS")
        print("=" * 80)
        print(f"Root folder: {root_folder}")
        print(f"FITS files found: {len(fits_files)}")
        print("-" * 80)
        if not ADU_ANALYSIS_ENABLED:
            pass
        elif ADU_SAMPLE_PER_FILTER == float('inf'):
            print("COMPLETE mode: Fast analysis of all files")
            print("Photon calculation: Theoretical (fast mode)")
        else:
            print(f"PARTIAL mode: Analysis of {ADU_SAMPLE_PER_FILTER} samples per filter")
            print("Analysis: Basic exposure information only (photon calculation disabled)")
            print("Optimizations: 1% pixel sampling")
    print("-" * 80)

    # Memory cleanup after Phase 2 (signature groups, dedup data no longer needed)
    import gc
    gc.collect()

    # Third pass: collect all valid files and organize by target/filter
    files_by_target_filter = defaultdict(lambda: defaultdict(list))
    
    if SYSTEM_LANGUAGE == 'fr':
        print("")
        print("=" * 60)
        print("📂 PHASE 3 : FILTRAGE DES HEADERS")
        print("=" * 60)
        print("   ⚡ Mode optimisé: lecture des headers uniquement (exclusion des calibrations)")
    else:
        print("")
        print("=" * 60)
        print("📂 PHASE 3: FILTERING HEADERS")
        print("=" * 60)
        print("   ⚡ Optimized mode: reading headers only (excluding calibrations)")
    
    # Process files in batches to reduce memory pressure
    # Adaptive batch size based on system resources
    try:
        import psutil
        memory_gb = psutil.virtual_memory().total / (1024**3)
        memory_available = True
    except (ImportError, OSError, AttributeError):
        # Fallback: estimate memory based on workers and platform
        import platform
        system = platform.system().lower()
        if system == "windows":
            memory_gb = (workers * 2) if workers else 4  # Conservative estimate for Windows
        elif system == "darwin":  # macOS
            memory_gb = (workers * 4) if workers else 8  # macOS typically has more memory
        else:  # Linux and others
            memory_gb = (workers * 3) if workers else 6  # Linux estimate
        memory_available = False
    
    cpu_count = workers if workers else 1
    
    # Detect storage type (HDD vs SSD) for optimal parallelization
    # HDD: sequential access, limit parallelism to avoid disk contention
    # SSD: random access, can handle more parallelism
    # IMPORTANT: Detect the storage type of the FOLDER being analyzed, not the script location
    is_ssd, storage_info = detect_storage_type(root_folder)
    
    # Optimize workers based on storage type
    # HDD: reduce workers to avoid disk contention (I/O bound)
    # SSD: can use more workers (CPU bound)
    if not is_ssd and workers > 1:
        # For HDD, limit to 2-4 workers to avoid disk contention
        optimal_workers = min(workers, max(2, min(4, cpu_count // 2)))
        if optimal_workers < workers:
            print(f"   💾 Stockage HDD détecté: réduction des workers de {workers} à {optimal_workers} pour éviter la contention disque")
            workers = optimal_workers
    else:
        # For SSD, use all available workers (or keep as is)
        pass
    
    # Adaptive batch size based on system resources and storage type
    if memory_gb >= 32 and cpu_count >= 16:
        batch_size = 500 if is_ssd else 200  # High-end systems
    elif memory_gb >= 16 and cpu_count >= 8:
        batch_size = 300 if is_ssd else 150  # Mid-range systems
    elif memory_gb >= 8 and cpu_count >= 4:
        batch_size = 200 if is_ssd else 100  # Entry-level systems
    else:
        batch_size = 100 if is_ssd else 50  # Low-end systems
    
    # Display system info
    if workers > 1:
        print(f"   💻 Configuration système détectée:")
        print(f"      🖥️  CPU: {cpu_count} core(s)")
        print(f"      💾 RAM: {memory_gb:.1f}GB" if memory_available else f"      💾 RAM: {memory_gb:.1f}GB (estimé)")
        print(f"      💿 Stockage: {storage_info}")
        print(f"      🧵 Workers optimisés: {workers}")
    
    processed_count = 0
    total_files_for_phase3 = len(fits_files)
    
    # Use parallel processing for Phase 3 if workers > 1
    # OPTIMIZATION: Use ThreadPoolExecutor for header reading (I/O bound, no serialization overhead)
    # This is MUCH faster than ProcessPoolExecutor for simple header reading
    if workers and workers > 1:
        if SYSTEM_LANGUAGE == 'fr':
            print(f"🧵 Traitement parallèle avec {workers} workers (ThreadPool - optimisé pour I/O)")
            print(f"   📊 Traitement de {total_files_for_phase3} fichier(s)...")
        else:
            print(f"🧵 Parallel processing with {workers} workers (ThreadPool - optimized for I/O)")
            print(f"   📊 Processing {total_files_for_phase3} file(s)...")
        
        # Use ThreadPoolExecutor for header reading (I/O bound operation)
        # Much faster than ProcessPoolExecutor because:
        # 1. No serialization overhead (just reading headers)
        # 2. I/O bound operations benefit from threading
        # 3. Lower memory overhead
        # 4. Thread-safe for fits.getheader()
        with ThreadPoolExecutor(max_workers=workers) as ex:
            # Chunked submission to limit memory for large file counts (200k+)
            # Instead of submitting all futures at once, process in chunks
            chunk_size = min(batch_size * 4, 5000)  # Balance throughput vs memory
            if SYSTEM_LANGUAGE == 'fr':
                print(f"   ⏳ Traitement par lots de {chunk_size} fichiers...")
            else:
                print(f"   ⏳ Processing in chunks of {chunk_size} files...")

            import gc

            # Create progress bar manually for chunked processing
            if TQDM_AVAILABLE:
                pbar = tqdm(
                    total=total_files_for_phase3,
                    desc="📂 Phase 3: Filtrage" if SYSTEM_LANGUAGE == 'fr' else "📂 Phase 3: Filtering",
                    unit="file",
                    bar_format='{l_bar}🟢{bar}🟢| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
                    colour='green', leave=True, position=0, ncols=100,
                    mininterval=0.05, maxinterval=0.5, smoothing=0.1
                )
            else:
                pbar = None

            for chunk_start in range(0, total_files_for_phase3, chunk_size):
                if check_abort and callable(check_abort) and check_abort():
                    if pbar: pbar.close()
                    return None

                chunk_end = min(chunk_start + chunk_size, total_files_for_phase3)
                chunk = fits_files[chunk_start:chunk_end]
                chunk_futures = [ex.submit(_process_file_phase3, f) for f in chunk]

                for future in as_completed(chunk_futures):
                    if check_abort and callable(check_abort) and check_abort():
                        if pbar: pbar.close()
                        return None
                    result = future.result()
                    processed_count += 1
                    if result:
                        files_by_target_filter[result['target']][result['filter']].append(result['file'])
                        global_data['total_files'] += 1

                    # Report progress to GUI
                    report_progress(processed_count, total_files_for_phase3, "phase3")
                    if pbar: pbar.update(1)

                # Free chunk memory after each batch
                del chunk_futures, chunk
                gc.collect()

            if pbar: pbar.close()
    else:
        # Sequential processing (original method)
        # Create progress bar only for sequential mode
        if TQDM_AVAILABLE:
            fits_files_iter = create_enhanced_progress_bar(
                fits_files, 
                total=total_files_for_phase3, 
                desc="📂 Phase 3: Filtrage" if SYSTEM_LANGUAGE == 'fr' else "📂 Phase 3: Filtering",
                unit="file"
            )
        else:
            fits_files_iter = fits_files
        
        for file in fits_files_iter:
            if check_abort and callable(check_abort) and check_abort():
                return None
            global_data['total_files'] += 1
            processed_count += 1
            
            # Report progress to GUI
            report_progress(processed_count, total_files_for_phase3, "phase3")
            
            # Extract basic info to identify target and filter (optimized for Phase 1)
            basic_info = extract_fits_header_info_fast(file)
            if basic_info and basic_info['type'] not in ['FLAT', 'DARK', 'BIAS'] and 'FLATWIZARD' not in str(basic_info['info']['instrument']).upper():
                # Ensure filter is set (use appropriate default based on context)
                if not basic_info['filter'] or basic_info['filter'] == 'Unknown':
                    # Check if this is a color camera file (Bayer matrix detection)
                    if basic_info.get('is_color', False):
                        basic_info['filter'] = 'OSC'  # One Shot Color
                    else:
                        # Check if this is likely a color camera file based on filename/path
                        filename_lower = str(file).lower()
                        osc_indicators = ['color', 'colour', 'osc', 'one shot', 'oneshot', 'rgb', 'camera', 'cam']
                        if any(indicator in filename_lower for indicator in osc_indicators):
                            basic_info['filter'] = 'OSC'  # One Shot Color
                        else:
                            basic_info['filter'] = 'L'  # Default to Luminance for monochrome cameras
                target = basic_info['target'] or file.parent.name
                if not target or target == 'Unknown':
                    target = file.parent.name
                
                # Normalize target name (case-insensitive, remove extra spaces)
                target = normalize_target_name(target)
                
                # Store file for this filter of this target
                files_by_target_filter[target][basic_info['filter']].append(file)
            
            # Periodic memory cleanup to prevent slowdown
            if processed_count % batch_size == 0:
                import gc
                gc.collect()
    
    # Print Phase 3 summary
    valid_files_count = sum(len(files) for filters in files_by_target_filter.values() for files in filters.values())
    calibration_count = total_files_for_phase3 - valid_files_count
    if SYSTEM_LANGUAGE == 'fr':
        print(f"✓ Phase 3 terminée: {valid_files_count} fichier(s) LIGHT trouvé(s) sur {total_files_for_phase3}")
        if calibration_count > 0:
            print(f"   ℹ️  {calibration_count} fichier(s) de calibration ignoré(s) (DARK/FLAT/BIAS/illisibles)")
    else:
        print(f"✓ Phase 3 complete: {valid_files_count} LIGHT file(s) found out of {total_files_for_phase3}")
        if calibration_count > 0:
            print(f"   ℹ️  {calibration_count} calibration file(s) skipped (DARK/FLAT/BIAS/unreadable)")
    
    # Memory cleanup after Phase 3 (fits_files list no longer needed, free for Phase 4)
    gc.collect()

    # Fourth pass: file processing

    def _consume_results(results_iter, total_count=0):
        processed_count = 0
        failed_count = 0
        skipped_count = 0
        for file_str, info, do_adu in results_iter:
            if info:
                # Check if file will be processed (before calling process_file_info)
                will_process = (info.get('type') not in ['FLAT', 'BIAS', 'DARK'] and
                              'FLATWIZARD' not in str(info.get('info', {}).get('instrument', '')).upper())
                
                process_file_info(info, Path(file_str), data_by_target, global_data, is_adu_sample=bool(do_adu))
                
                if will_process:
                    processed_count += 1
                else:
                    skipped_count += 1
            else:
                failed_count += 1
            
            # Report progress to GUI
            report_progress(processed_count + failed_count + skipped_count, total_count, "phase4")
        
        if failed_count > 0:
            if SYSTEM_LANGUAGE == 'fr':
                print(f"   ⚠️  {failed_count} fichier(s) n'ont pas pu être analysés")
            else:
                print(f"   ⚠️  {failed_count} file(s) could not be analyzed")
        if skipped_count > 0:
            if SYSTEM_LANGUAGE == 'fr':
                print(f"   ⚠️  {skipped_count} fichier(s) ignoré(s) (calibration)")
            else:
                print(f"   ⚠️  {skipped_count} file(s) skipped (calibration)")
        if processed_count > 0:
            if SYSTEM_LANGUAGE == 'fr':
                print(f"   ✓ {processed_count} fichier(s) traité(s) avec succès")
            else:
                print(f"   ✓ {processed_count} file(s) processed successfully")

    if ADU_ANALYSIS_ENABLED:
        if SYSTEM_LANGUAGE == 'fr':
            print("")
            print("=" * 60)
            print("⚡ PHASE 4 : ANALYSE DES FICHIERS")
            print("=" * 60)
            print("🎲 Sélection aléatoire et analyse...")
        else:
            print("")
            print("=" * 60)
            print("⚡ PHASE 4: FILE ANALYSIS")
            print("=" * 60)
            print("🎲 Random selection and analysis...")
        import random

        tasks = []
        for target, filters in files_by_target_filter.items():
            for filter_name, files in filters.items():
                if ADU_SAMPLE_PER_FILTER != float('inf'):
                    nb_files = min(ADU_SAMPLE_PER_FILTER, len(files))
                    adu_files = random.sample(files, nb_files) if nb_files > 0 else []
                    non_adu_files = [f for f in files if f not in adu_files]
                    print(f"   🎲 {target} - {filter_name}: {len(files)} files, {len(adu_files)} randomly selected for analysis")
                else:
                    adu_files = files
                    non_adu_files = []
                    print(f"   🎲 {target} - {filter_name}: All {len(files)} files selected for analysis")

                tasks.extend([(str(f), True) for f in adu_files])
                tasks.extend([(str(f), False) for f in non_adu_files])
        
        adu_tasks = sum(1 for _, do_adu in tasks if do_adu)
        non_adu_tasks = sum(1 for _, do_adu in tasks if not do_adu)
        print(f"   📊 Analysis breakdown:")
        print(f"      ⚡ Fast processing: {len(tasks)} files")
        print(f"      📁 Total: {len(tasks)} files")
        
        # Print detailed progress information
        print_progress_info(adu_tasks, non_adu_tasks, len(tasks))

        if workers and workers > 1:
            print(f"🧵 Parallel execution with {workers} workers")
            print(f"   📊 Traitement de {len(tasks)} fichier(s)...")
            # Chunked submission to limit memory for large file counts (200k+)
            p4_chunk_size = min(batch_size * 2, 2000)
            print(f"   ⏳ Traitement par lots de {p4_chunk_size} fichiers (ProcessPool)...")
            with ProcessPoolExecutor(max_workers=workers) as ex:
                def _chunked_results_gen():
                    """Generator yielding results from chunked ProcessPool submissions"""
                    import gc as _gc
                    for _cs in range(0, len(tasks), p4_chunk_size):
                        _chunk = tasks[_cs:_cs + p4_chunk_size]
                        _futures = [ex.submit(_process_file, t) for t in _chunk]
                        for _f in as_completed(_futures):
                            yield _f.result()
                        del _futures, _chunk
                        _gc.collect()

                if TQDM_AVAILABLE:
                    progress_bar = create_enhanced_progress_bar(
                        _chunked_results_gen(),
                        total=len(tasks),
                        desc=f"🔄 Processing {len(tasks)} files"
                    )
                    _consume_results(progress_bar, len(tasks))
                else:
                    _consume_results(_chunked_results_gen(), len(tasks))
        else:
            print("🧵 Sequential execution (1 worker)")
            if TQDM_AVAILABLE:
                progress_bar = create_enhanced_progress_bar(
                    (_process_file(t) for t in tasks), 
                    total=len(tasks), 
                    desc=f"🔄 Processing {len(tasks)} files"
                )
                _consume_results(progress_bar, len(tasks))
            else:
                _consume_results((_process_file(t) for t in tasks), len(tasks))
    else:
        if SYSTEM_LANGUAGE == 'fr':
            print("")
            print("=" * 60)
            print("⚡ PHASE 4 : ANALYSE DES FICHIERS")
            print("=" * 60)
            print("⚡ Analyse rapide...")
        else:
            print("")
            print("=" * 60)
            print("⚡ PHASE 4: FILE ANALYSIS")
            print("=" * 60)
            print("⚡ Fast analysis...")
        # Use files_by_target_filter instead of fits_files to only process valid files from Phase 3
        tasks = []
        for target, filters in files_by_target_filter.items():
            for filter_name, files in filters.items():
                tasks.extend([(str(f), False) for f in files])
        
        # Print progress information for fast mode
        print_progress_info(0, len(tasks), len(tasks))
        
        if workers and workers > 1:
            if SYSTEM_LANGUAGE == 'fr':
                print(f"🧵 Traitement parallèle avec {workers} workers")
                print(f"   📊 Traitement de {len(tasks)} fichier(s) valides...")
            else:
                print(f"🧵 Parallel processing with {workers} workers")
                print(f"   📊 Processing {len(tasks)} valid file(s)...")
            # Chunked submission to limit memory for large file counts (200k+)
            p4_chunk_size = min(batch_size * 2, 2000)
            with ProcessPoolExecutor(max_workers=workers) as ex:
                def _chunked_results_gen_fast():
                    """Generator yielding results from chunked ProcessPool submissions"""
                    import gc as _gc
                    for _cs in range(0, len(tasks), p4_chunk_size):
                        _chunk = tasks[_cs:_cs + p4_chunk_size]
                        _futures = [ex.submit(_process_file, t) for t in _chunk]
                        for _f in as_completed(_futures):
                            yield _f.result()
                        del _futures, _chunk
                        _gc.collect()

                if TQDM_AVAILABLE:
                    _consume_results(create_enhanced_progress_bar(
                        _chunked_results_gen_fast(),
                        total=len(tasks),
                        desc="⚡ Phase 4: Analyse" if SYSTEM_LANGUAGE == 'fr' else "⚡ Phase 4: Analysis"
                    ), len(tasks))
                else:
                    _consume_results(_chunked_results_gen_fast(), len(tasks))
        else:
            if SYSTEM_LANGUAGE == 'fr':
                print("🧵 Traitement séquentiel (1 worker)")
            else:
                print("🧵 Sequential processing (1 worker)")
            if TQDM_AVAILABLE:
                _consume_results(create_enhanced_progress_bar(
                    (_process_file(t) for t in tasks), 
                    total=len(tasks), 
                    desc="⚡ Phase 4: Analyse" if SYSTEM_LANGUAGE == 'fr' else "⚡ Phase 4: Analysis"
                ), len(tasks))
            else:
                _consume_results((_process_file(t) for t in tasks), len(tasks))
    
    # Print completion message
    print_progress_completion()

    # Memory cleanup after Phase 4 (free task lists and intermediate data)
    gc.collect()

    # Fifth pass: Statistical analysis and extrapolation
    if ADU_ANALYSIS_ENABLED and any(data_by_target[target]['adu_samples'] for target in data_by_target):
        if SYSTEM_LANGUAGE == 'fr':
            print("")
            print("=" * 60)
            print("📊 PHASE 5 : ANALYSE STATISTIQUE")
            print("=" * 60)
            print(f"   📊 Analyse statistique de {len([t for t in data_by_target.keys() if data_by_target[t].get('adu_samples')])} cible(s)...")
        else:
            print("")
            print("=" * 60)
            print("📊 PHASE 5: STATISTICAL ANALYSIS")
            print("=" * 60)
            print(f"   📊 Statistical analysis of {len([t for t in data_by_target.keys() if data_by_target[t].get('adu_samples')])} target(s)...")
        data_by_target = calculate_adu_statistics_by_filter(data_by_target)
        if SYSTEM_LANGUAGE == 'fr':
            print(f"   ✓ Analyse statistique terminée")
        else:
            print(f"   ✓ Statistical analysis completed")
    
    # Convert sets to lists for JSON serialization
    for target_data in data_by_target.values():
        target_data['instruments'] = list(target_data['instruments'])
        target_data['telescopes'] = list(target_data['telescopes'])
        target_data['dates'] = list(target_data['dates'])
        target_data['apertures'] = list(target_data['apertures'])
        target_data['diameters'] = list(target_data['diameters'])
        target_data['focal_lengths'] = list(target_data['focal_lengths'])
    
    global_data['found_targets'] = list(global_data['found_targets'])
    global_data['used_instruments'] = list(global_data['used_instruments'])
    global_data['used_telescopes'] = list(global_data['used_telescopes'])
    
    return data_by_target, global_data

def analyze_fits_files(folder_path, output_folder, num_workers=1):
    """Analyzes all FITS files in the folder and subfolders"""
    print(f"\n🔍 ANALYZING FITS FILES")
    print("=" * 80)
    print(f"📁 Folder: {folder_path}")
    print(f"👥 Workers: {num_workers}")
    
    # Find all FITS files recursively (case-insensitive)
    fits_files = []
    fits_extensions = ('.fits', '.fit', '.fits.fz', '.xisf', '.xifs', '.xif')
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(fits_extensions):
                fits_files.append(os.path.join(root, file))
    
    # Convert to Path objects for deduplication
    fits_files = [Path(f) for f in fits_files]
    
    # Remove compressed duplicates (prefer .fits over .xisf over .xifs over .xif over .fits.fz)
    fits_files = remove_compressed_duplicates(fits_files)
    
    # Convert back to strings for compatibility
    fits_files = [str(f) for f in fits_files]
    
    if not fits_files:
        print("❌ No FITS/XISF files found")
        return {}, {}
    
    if SYSTEM_LANGUAGE == 'fr':
        print(f"📊 {len(fits_files)} fichiers FITS/XISF trouvés")
    else:
        print(f"📊 Found {len(fits_files)} FITS/XISF files")
    
    # Initialize data structures
    data_by_target = {}
    global_data = {
        'total_files': 0,
        'found_targets': set(),
        'used_instruments': set(),
        'used_telescopes': set(),
        'total_time': 0
    }
    
    # Count files by type
    file_type_counts = {'LIGHT': 0, 'FLAT': 0, 'DARK': 0, 'BIAS': 0, 'OTHER': 0}
    
    # Process files
    if SYSTEM_LANGUAGE == 'fr':
        print(f"\n📋 TRAITEMENT DES FICHIERS")
    else:
        print(f"\n📋 PROCESSING FILES")
    print("-" * 60)
    
    for i, file_path in enumerate(fits_files, 1):
        print(f"📄 [{i}/{len(fits_files)}] {os.path.basename(file_path)}")
        
        try:
            # Extract header information
            header_info = analyze_fits_header(file_path)
            
            if not header_info:
                if SYSTEM_LANGUAGE == 'fr':
                    print(f"   ⚠️  Impossible de lire l'en-tête")
                else:
                    print(f"   ⚠️  Could not read header")
                continue
            
            # Check image type - only process LIGHT files
            image_type = header_info.get('image_type', 'LIGHT')
            
            # Count file types
            if image_type in file_type_counts:
                file_type_counts[image_type] += 1
            else:
                file_type_counts['OTHER'] += 1
            
            if image_type not in ['LIGHT', 'SCIENCE', 'OBJECT']:
                print(f"   ⏭️  Skipping {image_type} file")
                continue
            
            # Extract target name
            target = header_info.get('object', 'Unknown')
            if not target or target == 'Unknown':
                # Try to extract from filename
                filename = os.path.basename(file_path)
                target = filename.split('_')[0] if '_' in filename else 'Unknown'
            
            # Extract filter
            filter_name = header_info.get('filter')
            if not filter_name:
                filter_name, _confidence = extract_filter_from_filename(file_path)
                if not filter_name:
                    # Check if this is a color camera file (Bayer matrix detection)
                    if header_info.get('is_color', False):
                        filter_name = 'RGB'  # One Shot Color
                    else:
                        # Check if this is likely a color camera file based on filename/path
                        filename_lower = str(file_path).lower()
                        osc_indicators = ['color', 'colour', 'osc', 'one shot', 'oneshot', 'rgb', 'camera', 'cam']
                        if any(indicator in filename_lower for indicator in osc_indicators):
                            filter_name = 'RGB'  # One Shot Color
                        else:
                            filter_name = 'L'  # Default to Luminance for monochrome cameras
            
            # Extract exposure time
            exposure_time = header_info.get('exposure_time', 0)
            
            # Extract instrument and telescope
            instrument = header_info.get('instrument', 'Unknown')
            telescope = header_info.get('telescope', 'Unknown')
            
            # Initialize target data if not exists
            if target not in data_by_target:
                data_by_target[target] = {
                    'files': [],
                    'time_by_filter': defaultdict(list),
                    'received_light': defaultdict(list),
                    'adu_samples': defaultdict(list),
                    'instruments': set(),
                    'telescopes': set(),
                    'dates': [],
                    'apertures': [],
                    'diameters': [],
                    'focal_lengths': []
                }
            
            # Add file data
            data_by_target[target]['files'].append(file_path)
            data_by_target[target]['time_by_filter'][filter_name].append(exposure_time)
            data_by_target[target]['instruments'].add(instrument)
            data_by_target[target]['telescopes'].add(telescope)
            
            # Extract date
            date_obs = header_info.get('date_obs', '')
            if date_obs:
                data_by_target[target]['dates'].append(date_obs)
            
            # Extract telescope characteristics
            diameter = header_info.get('diameter')
            if diameter:
                print(f"   ✅ Diameter detected: {diameter}mm")
                data_by_target[target]['diameters'].append(diameter)
                data_by_target[target]['apertures'].append(diameter / 1000)  # Convert to meters
                data_by_target[target]['focal_lengths'].append(diameter * 8)  # Assume f/8
            else:
                print(f"   ⚠️  No diameter detected in header")
                
                # Try to get telescope characteristics from database using telescope name
                telescope_name = header_info.get('telescope', '')
                if telescope_name and telescope_name != 'Unknown':
                    print(f"   🔍 Looking up telescope '{telescope_name}' in database...")
                    telescope_characteristics = get_telescope_characteristics(telescope_name)
                    
                    if telescope_characteristics and telescope_characteristics != TELESCOPES_DATABASE['default']:
                        diameter = telescope_characteristics['diameter_mm']
                        focal_length = telescope_characteristics['focal_length_mm']
                        f_number = telescope_characteristics['f_number']
                        
                        print(f"   ✅ Found in database: {diameter}mm, {focal_length}mm, f/{f_number}")
                        
                        data_by_target[target]['diameters'].append(diameter)
                        data_by_target[target]['apertures'].append(f_number)
                        data_by_target[target]['focal_lengths'].append(focal_length)
                    else:
                        print(f"   ⚠️  Telescope '{telescope_name}' not found in database")
                else:
                    print(f"   ⚠️  No telescope name available for database lookup")
            
            # Calculate theoretical light quantity
            # Light calculation removed (photon analysis disabled)
            # Store basic exposure information instead
            light_data = {
                'exposure_time': exposure_time,
                'filter': filter_name,
                'diameter_mm': diameter if diameter else 200.0,
                'source': 'basic_info'
            }
            
            data_by_target[target]['received_light'][filter_name].append(light_data)
            print(f"   ✅ Basic exposure info stored: {exposure_time}s exposure, {filter_name} filter")
            
            # Update global data
            global_data['total_files'] += 1
            global_data['found_targets'].add(target)
            global_data['used_instruments'].add(instrument)
            global_data['used_telescopes'].add(telescope)
            global_data['total_time'] += exposure_time
            
            print(f"   ✅ Target: {target}, Filter: {filter_name}, Time: {format_time(exposure_time)}")
            
        except Exception as e:
            print(f"   ❌ Error processing file: {e}")
            continue
    
    # Convert sets to lists for JSON serialization
    for target_data in data_by_target.values():
        target_data['instruments'] = list(target_data['instruments'])
        target_data['telescopes'] = list(target_data['telescopes'])
    
    global_data['found_targets'] = list(global_data['found_targets'])
    global_data['used_instruments'] = list(global_data['used_instruments'])
    global_data['used_telescopes'] = list(global_data['used_telescopes'])
    
    if SYSTEM_LANGUAGE == 'fr':
        print(f"\n✅ Analyse terminée !")
        print(f"📊 Cibles trouvées: {len(data_by_target)}")
        print(f"📊 Fichiers LIGHT traités: {global_data['total_files']}")
        print(f"⏰ Temps d'observation total: {format_time(global_data['total_time'])}")
        
        print(f"\n📋 STATISTIQUES PAR TYPE:")
        print(f"   🔆 Fichiers LIGHT: {file_type_counts['LIGHT']}")
        print(f"   🔧 Fichiers FLAT: {file_type_counts['FLAT']}")
        print(f"   🌑 Fichiers DARK: {file_type_counts['DARK']}")
        print(f"   ⚡ Fichiers BIAS: {file_type_counts['BIAS']}")
        if file_type_counts['OTHER'] > 0:
            print(f"   ❓ Autres fichiers: {file_type_counts['OTHER']}")
    else:
        print(f"\n✅ Analysis completed!")
        print(f"📊 Targets found: {len(data_by_target)}")
        print(f"📊 Total LIGHT files processed: {global_data['total_files']}")
        print(f"⏰ Total observation time: {format_time(global_data['total_time'])}")
        
        print(f"\n📋 FILE TYPE STATISTICS:")
        print(f"   🔆 LIGHT files: {file_type_counts['LIGHT']}")
        print(f"   🔧 FLAT files: {file_type_counts['FLAT']}")
        print(f"   🌑 DARK files: {file_type_counts['DARK']}")
        print(f"   ⚡ BIAS files: {file_type_counts['BIAS']}")
        if file_type_counts['OTHER'] > 0:
            print(f"   ❓ OTHER files: {file_type_counts['OTHER']}")
    
    return data_by_target, global_data

def is_calibration_target(target_name):
    """Check if target name indicates calibration files"""
    target_upper = target_name.upper()
    calibration_keywords = ['BIAS', 'DARK', 'FLAT', 'CALIBRATION', 'CAL']
    return any(keyword in target_upper for keyword in calibration_keywords)

def display_target_statistics(data_by_target):
    """Displays detailed statistics by target"""
    # Defensive initializations to avoid NameError if plotting context is missing
    try:
        import matplotlib.pyplot as plt  # Ensure matplotlib is available in this scope
    except Exception:
        plt = None
    if 'fig' not in globals():
        try:
            fig = plt.figure(figsize=(16, 9)) if plt else None
        except Exception:
            fig = None
        globals()['fig'] = fig
    if 'ax3' not in globals():
        globals()['ax3'] = None
    if 'top_targets' not in globals():
        globals()['top_targets'] = []
    if 'filter_times' not in globals():
        globals()['filter_times'] = {}
    print(f"\nDETAILED STATISTICS")
    print("=" * 100)
    
    # Sort targets alphabetically with improved astronomical object handling
    sorted_targets = sorted(data_by_target.items(), key=lambda x: get_astronomical_sort_key(x[0]))
    
    for target, data in sorted_targets:
        if not data['files']:
            continue
        
        # Skip calibration targets
        if is_calibration_target(target):
            continue
            
        print(f"\n{target}")
        print("-" * 80)
        
        # General statistics
        total_files = len(data['files'])
        
        # Calculate total time from files_by_date to avoid duplication
        total_time = 0
        if 'files_by_date' in data:
            for date_data in data['files_by_date'].values():
                total_time += date_data['total_time']
        else:
            # Fallback to time_by_filter if files_by_date not available
            total_time = sum(sum(times) for times in data['time_by_filter'].values())
        
        print(f"📊 Files: {total_files}")
        print(f"⏰ Total time: {format_time(total_time)} ({total_time/3600:.2f}h)")
        print(f"🔭 Telescopes: {', '.join(data['telescopes'])}")
        
        # Display mosaic panel information if this is a mosaic
        if 'panels' in data and data['panels']:
            print(f"🧩 Mosaic panels: {len(data['panels'])}")
            for panel_num, panel_info in sorted(data['panels'].items(), key=lambda x: int(x[0])):
                panel_files = len(panel_info['files'])
                panel_time = panel_info['total_time']
                print(f"   Panel {panel_num}: {panel_files} files, {format_time(panel_time)} ({panel_time/3600:.2f}h)")
                print(f"   Original name: {panel_info['original_name']}")
        
        # Display period - use dates from files if available, otherwise show message
        if data['dates']:
            print(f"📅 Period: {min(data['dates'])} to {max(data['dates'])}")
        else:
            # Try to get dates from files
            file_dates = []
            for file_info in data['files']:
                if 'info' in file_info and 'date_obs' in file_info['info']:
                    file_dates.append(file_info['info']['date_obs'])
            if file_dates:
                print(f"📅 Period: {min(file_dates)} to {max(file_dates)}")
            else:
                print(f"📅 Period: Not available")
        
        # Display telescope characteristics if available
        if data['apertures'] or data['diameters'] or data['focal_lengths']:
            print(f"\n🔭 TELESCOPE CHARACTERISTICS:")
            
            if data['apertures']:
                # Filter out None values before sorting
                valid_apertures = [a for a in data['apertures'] if a is not None]
                if valid_apertures:
                    unique_apertures = sorted(set(valid_apertures))
                    print(f"   📏 Apertures: {', '.join([f'f/{a:.1f}' for a in unique_apertures])}")
            
            if data['diameters']:
                # Filter out None values before sorting
                valid_diameters = [d for d in data['diameters'] if d is not None]
                if valid_diameters:
                    unique_diameters = sorted(set(valid_diameters))
                    print(f"   🔍 Diameters: {', '.join([f'{d}mm' for d in unique_diameters])}")
            
            if data['focal_lengths']:
                # Filter out None values before sorting
                valid_focal_lengths = [f for f in data['focal_lengths'] if f is not None]
                if valid_focal_lengths:
                    unique_focal_lengths = sorted(set(valid_focal_lengths))
                    print(f"   📐 Focal lengths: {', '.join([f'{f}mm' for f in unique_focal_lengths])}")
        else:
            print(f"\n⚠️  No telescope characteristics detected in FITS headers")
        
        # Statistics by filter - ordered by specific sequence
        print(f"\nFILTER DISTRIBUTION:")
        
        # Aggregate filter data from files_by_date
        aggregated_filters = {}
        if 'files_by_date' in data:
            for date_data in data['files_by_date'].values():
                for filter_name, time_list in date_data['time_by_filter'].items():
                    if filter_name not in aggregated_filters:
                        aggregated_filters[filter_name] = []
                    aggregated_filters[filter_name].extend(time_list)
        else:
            # Fallback to time_by_filter if files_by_date not available
            aggregated_filters = data['time_by_filter']
        
        # Define the specific order for filters
        filter_order = ['L', 'R', 'G', 'B', 'SII', 'Ha', 'OIII']
        
        # First, add filters in the specified order
        for filter_name in filter_order:
            if filter_name in aggregated_filters:
                time_list = aggregated_filters[filter_name]
                total_time = sum(time_list)
                nb_images = len(time_list)
                average_time = total_time / nb_images
                
                # Get filter info with fallback for unknown filters
                if filter_name in FILTERS_INFO:
                    filter_display_name = FILTERS_INFO[filter_name]['name']
                else:
                    filter_display_name = f"Unknown Filter ({filter_name})"
                
                print(f"   {filter_name} ({filter_display_name}):")
                print(f"     📸 {nb_images} images | ⏱️  {format_time(total_time)} | 📊 {format_time(average_time)}/image")
        
        # Then add any remaining filters not in the specified order
        for filter_name in sorted(aggregated_filters.keys()):
            if filter_name not in filter_order:
                time_list = aggregated_filters[filter_name]
                total_time = sum(time_list)
                nb_images = len(time_list)
                average_time = total_time / nb_images
                
                # Get filter info with fallback for unknown filters
                if filter_name in FILTERS_INFO:
                    filter_display_name = FILTERS_INFO[filter_name]['name']
                else:
                    filter_display_name = f"Unknown Filter ({filter_name})"
                
                print(f"   {filter_name} ({filter_display_name}):")
                print(f"     📸 {nb_images} images | ⏱️  {format_time(total_time)} | 📊 {format_time(average_time)}/image")
                
                # Basic exposure information
                if filter_name in data['received_light']:
                    exposure_times = [l.get('exposure_time') or 0 for l in data['received_light'][filter_name]]
                    total_exposure = sum(exposure_times)
                    avg_exposure = total_exposure / len(exposure_times) if exposure_times else 0
                    
                    print(f"     📸 Total exposure: {format_time(total_exposure)} | 📊 Average: {format_time(avg_exposure)}/image")
            
            # Basic exposure information (photon analysis removed)
            if filter_name in data['received_light']:
                exposure_times = [l['exposure_time'] for l in data['received_light'][filter_name]]
                total_exposure = sum(exposure_times)
                avg_exposure = total_exposure / len(exposure_times) if exposure_times else 0
                
                print(f"     📸 Total exposure: {format_time(total_exposure)} | 📊 Average: {format_time(avg_exposure)}/image")
                
                # Advanced analysis removed

def find_latex_executable():
    """Find LaTeX executable across different platforms with comprehensive Linux support"""
    import shutil
    import platform
    import glob
    import os
    
    # Common LaTeX executable names
    latex_names = ['pdflatex', 'latex']
    
    # Try to find LaTeX in PATH first
    for name in latex_names:
        if shutil.which(name):
            return name
    
    # Platform-specific paths
    system = platform.system().lower()
    
    if system == 'windows':
        # Windows paths
        common_paths = [
            r'C:\texlive\*\bin\windows\pdflatex.exe',
            r'C:\Program Files\MiKTeX\miktex\bin\x64\pdflatex.exe',
            r'C:\Program Files (x86)\MiKTeX\miktex\bin\pdflatex.exe',
            r'C:\texlive\*\bin\windows\latex.exe'
        ]
    elif system == 'darwin':  # macOS - comprehensive paths for all Mac variants
        # Get Mac-specific paths
        mac_paths = get_mac_variants_paths()
        common_paths = []
        
        # Add all Mac variant LaTeX paths
        for variant, paths in mac_paths.items():
            common_paths.extend(paths['latex_paths'])
        
        # Additional macOS-specific paths
        additional_mac_paths = [
            # MacTeX installations
            '/Library/TeX/texbin/pdflatex',
            '/Library/TeX/texbin/latex',
            '/usr/local/texlive/*/bin/*/pdflatex',
            '/usr/local/texlive/*/bin/*/latex',
            '/usr/texbin/pdflatex',
            '/usr/texbin/latex',
            
            # Homebrew paths (both Intel and Apple Silicon)
            '/opt/homebrew/bin/pdflatex',  # Apple Silicon
            '/usr/local/bin/pdflatex',     # Intel
            '/opt/homebrew/bin/latex',
            '/usr/local/bin/latex',
            '/opt/homebrew/opt/texlive/bin/pdflatex',
            '/usr/local/opt/texlive/bin/pdflatex',
            
            # MacPorts paths
            '/opt/local/bin/pdflatex',
            '/opt/local/bin/latex',
            '/opt/local/share/texmf/bin/pdflatex',
            '/opt/local/share/texmf/bin/latex',
            
            # Xcode Command Line Tools
            '/Library/Developer/CommandLineTools/usr/bin/pdflatex',
            '/Applications/Xcode.app/Contents/Developer/usr/bin/pdflatex',
            
            # Custom installations
            '/usr/local/share/texmf/bin/pdflatex',
            '/usr/local/share/texmf/bin/latex',
            
            # Conda installations on Mac
            '/opt/conda/bin/pdflatex',
            '/usr/local/conda/bin/pdflatex',
            '/opt/miniconda3/bin/pdflatex',
            '/usr/local/miniconda3/bin/pdflatex'
        ]
        
        common_paths.extend(additional_mac_paths)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_paths = []
        for path in common_paths:
            if path not in seen:
                seen.add(path)
                unique_paths.append(path)
        common_paths = unique_paths
    else:  # Linux and others - comprehensive paths for all distributions
        # Get distribution-specific paths
        distro_paths = get_linux_distribution_paths()
        common_paths = []
        
        # Add all distribution-specific LaTeX paths
        for distro, paths in distro_paths.items():
            common_paths.extend(paths['latex_paths'])
        
        # Additional Linux-specific paths
        additional_linux_paths = [
            # TeX Live installations
            '/usr/local/texlive/*/bin/*/pdflatex',
            '/opt/texlive/*/bin/*/pdflatex',
            '/usr/share/texlive/bin/*/pdflatex',
            '/usr/share/texlive/bin/x86_64-linux/pdflatex',
            '/usr/share/texlive/bin/i386-linux/pdflatex',
            '/usr/share/texlive/bin/amd64-linux/pdflatex',
            
            # Snap packages
            '/snap/bin/pdflatex',
            '/snap/texlive/current/bin/pdflatex',
            
            # AppImage installations
            '/opt/texlive/*/bin/*/pdflatex',
            
            # Custom installations
            '/opt/tex/bin/pdflatex',
            '/usr/local/bin/pdflatex',
            '/usr/bin/pdflatex',
            
            # Container-specific paths
            '/usr/share/texmf/bin/pdflatex',
            '/var/lib/texmf/bin/pdflatex',
            
            # Homebrew on Linux
            '/home/linuxbrew/.linuxbrew/bin/pdflatex',
            '/opt/homebrew/bin/pdflatex',
            
            # Conda installations
            '/opt/conda/bin/pdflatex',
            '/usr/local/conda/bin/pdflatex'
        ]
        
        common_paths.extend(additional_linux_paths)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_paths = []
        for path in common_paths:
            if path not in seen:
                seen.add(path)
                unique_paths.append(path)
        common_paths = unique_paths
    
    # Check common paths
    for pattern in common_paths:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    
    # Final fallback: try to find any pdflatex in common directories
    if system == 'linux':
        fallback_dirs = [
            '/usr/bin', '/usr/local/bin', '/opt/bin',
            '/usr/share/bin', '/usr/local/share/bin'
        ]
        
        for directory in fallback_dirs:
            if os.path.exists(directory):
                for latex_name in latex_names:
                    latex_path = os.path.join(directory, latex_name)
                    if os.path.exists(latex_path) and os.access(latex_path, os.X_OK):
                        return latex_path
    
    # LaTeX not found - display installation suggestions
    display_latex_installation_suggestions()
    return None

def get_required_latex_packages():
    """Get list of required LaTeX packages for the report"""
    return [
        'amsmath',      # Mathematical typesetting
        'amsfonts',     # Mathematical fonts
        'amssymb',      # Mathematical symbols
        'geometry',     # Page layout
        'graphicx',     # Graphics inclusion
        'booktabs',     # Professional tables
        'longtable',    # Multi-page tables
        'hyperref',     # Hyperlinks
        'xcolor',       # Colors
        'tikz',         # Vector graphics
        'pgf',          # TikZ backend
        'siunitx',      # SI units
        'float',        # Float positioning
        'needspace',    # Space control
        'translations', # Internationalization
        'array',        # Table extensions
        'url',          # URL formatting
        'rerunfilecheck' # File checking
    ]

def get_required_python_packages():
    """Get list of required Python packages"""
    return [
        'matplotlib',   # Plotting and graphics
        'numpy',        # Numerical computing
        'pandas',       # Data manipulation
        'reportlab',    # PDF generation
        'tqdm',         # Progress bars
        'astropy',      # Astronomical calculations
        'pillow',       # Image processing
        'scipy',        # Scientific computing
        'requests'      # HTTP requests
    ]

def check_python_packages():
    """Check which Python packages are missing and provide installation instructions"""
    required_packages = get_required_python_packages()
    missing_packages = []
    available_packages = []
    
    for package in required_packages:
        try:
            if package == 'pillow':
                import PIL
            else:
                __import__(package)
            available_packages.append(package)
        except ImportError:
            missing_packages.append(package)
    
    return {
        'missing': missing_packages,
        'available': available_packages,
        'all_available': len(missing_packages) == 0
    }

def recheck_astropy_availability():
    """Re-check if astropy is available after installation"""
    global ASTROPY_AVAILABLE
    try:
        from astropy.io import fits
        ASTROPY_AVAILABLE = True
        return True
    except ImportError:
        ASTROPY_AVAILABLE = False
        return False

def get_mac_variants_paths():
    """Get comprehensive Python and LaTeX paths for all Mac variants"""
    return {
        # Intel Mac paths
        'intel': {
            'python_paths': [
                '/usr/bin/python3', '/usr/bin/python',
                '/usr/local/bin/python3', '/usr/local/bin/python',
                '/opt/homebrew/bin/python3',  # Homebrew on Intel
                '/usr/local/opt/python@3.*/bin/python3',
                '/usr/local/Cellar/python@3.*/bin/python3',
                '/opt/local/bin/python3',  # MacPorts
                '/opt/local/bin/python',
                '/Library/Frameworks/Python.framework/Versions/*/bin/python3',
                '/Applications/Python 3.*/bin/python3'
            ],
            'pip_paths': [
                '/usr/bin/pip3', '/usr/bin/pip',
                '/usr/local/bin/pip3', '/usr/local/bin/pip',
                '/opt/homebrew/bin/pip3',
                '/usr/local/opt/python@3.*/bin/pip3',
                '/usr/local/Cellar/python@3.*/bin/pip3',
                '/opt/local/bin/pip3',  # MacPorts
                '/opt/local/bin/pip',
                '/Library/Frameworks/Python.framework/Versions/*/bin/pip3',
                '/Applications/Python 3.*/bin/pip3'
            ],
            'latex_paths': [
                '/usr/bin/pdflatex', '/usr/bin/latex',
                '/usr/local/bin/pdflatex', '/usr/local/bin/latex',
                '/Library/TeX/texbin/pdflatex',  # MacTeX
                '/usr/local/texlive/*/bin/*/pdflatex',
                '/opt/homebrew/bin/pdflatex',  # Homebrew LaTeX
                '/opt/local/bin/pdflatex',  # MacPorts LaTeX
                '/opt/local/bin/latex',
                '/usr/local/opt/texlive/bin/pdflatex'
            ]
        },
        # Apple Silicon (M1/M2/M3) Mac paths
        'apple_silicon': {
            'python_paths': [
                '/usr/bin/python3', '/usr/bin/python',
                '/opt/homebrew/bin/python3',  # Homebrew on Apple Silicon
                '/opt/homebrew/bin/python',
                '/usr/local/bin/python3', '/usr/local/bin/python',
                '/opt/homebrew/opt/python@3.*/bin/python3',
                '/opt/homebrew/Cellar/python@3.*/bin/python3',
                '/opt/local/bin/python3',  # MacPorts
                '/opt/local/bin/python',
                '/Library/Frameworks/Python.framework/Versions/*/bin/python3',
                '/Applications/Python 3.*/bin/python3',
                '/System/Library/Frameworks/Python.framework/Versions/*/bin/python3'
            ],
            'pip_paths': [
                '/usr/bin/pip3', '/usr/bin/pip',
                '/opt/homebrew/bin/pip3',  # Homebrew on Apple Silicon
                '/opt/homebrew/bin/pip',
                '/usr/local/bin/pip3', '/usr/local/bin/pip',
                '/opt/homebrew/opt/python@3.*/bin/pip3',
                '/opt/homebrew/Cellar/python@3.*/bin/pip3',
                '/opt/local/bin/pip3',  # MacPorts
                '/opt/local/bin/pip',
                '/Library/Frameworks/Python.framework/Versions/*/bin/pip3',
                '/Applications/Python 3.*/bin/pip3',
                '/System/Library/Frameworks/Python.framework/Versions/*/bin/pip3'
            ],
            'latex_paths': [
                '/usr/bin/pdflatex', '/usr/bin/latex',
                '/Library/TeX/texbin/pdflatex',  # MacTeX
                '/Library/TeX/texbin/latex',
                '/opt/homebrew/bin/pdflatex',  # Homebrew LaTeX on Apple Silicon
                '/opt/homebrew/bin/latex',
                '/usr/local/bin/pdflatex', '/usr/local/bin/latex',
                '/usr/local/texlive/*/bin/*/pdflatex',
                '/opt/local/bin/pdflatex',  # MacPorts LaTeX
                '/opt/local/bin/latex',
                '/opt/homebrew/opt/texlive/bin/pdflatex'
            ]
        },
        # macOS with Xcode Command Line Tools
        'xcode_tools': {
            'python_paths': [
                '/usr/bin/python3', '/usr/bin/python',
                '/Applications/Xcode.app/Contents/Developer/usr/bin/python3',
                '/Library/Developer/CommandLineTools/usr/bin/python3',
                '/usr/local/bin/python3', '/usr/local/bin/python'
            ],
            'pip_paths': [
                '/usr/bin/pip3', '/usr/bin/pip',
                '/usr/local/bin/pip3', '/usr/local/bin/pip'
            ],
            'latex_paths': [
                '/usr/bin/pdflatex', '/usr/bin/latex',
                '/Library/TeX/texbin/pdflatex',
                '/Library/TeX/texbin/latex'
            ]
        },
        # macOS with Homebrew
        'homebrew': {
            'python_paths': [
                '/opt/homebrew/bin/python3',  # Apple Silicon
                '/usr/local/bin/python3',     # Intel
                '/opt/homebrew/bin/python',
                '/usr/local/bin/python',
                '/opt/homebrew/opt/python@3.*/bin/python3',
                '/usr/local/opt/python@3.*/bin/python3',
                '/opt/homebrew/Cellar/python@3.*/bin/python3',
                '/usr/local/Cellar/python@3.*/bin/python3'
            ],
            'pip_paths': [
                '/opt/homebrew/bin/pip3',     # Apple Silicon
                '/usr/local/bin/pip3',       # Intel
                '/opt/homebrew/bin/pip',
                '/usr/local/bin/pip',
                '/opt/homebrew/opt/python@3.*/bin/pip3',
                '/usr/local/opt/python@3.*/bin/pip3',
                '/opt/homebrew/Cellar/python@3.*/bin/pip3',
                '/usr/local/Cellar/python@3.*/bin/pip3'
            ],
            'latex_paths': [
                '/opt/homebrew/bin/pdflatex',  # Apple Silicon
                '/usr/local/bin/pdflatex',     # Intel
                '/opt/homebrew/bin/latex',
                '/usr/local/bin/latex',
                '/opt/homebrew/opt/texlive/bin/pdflatex',
                '/usr/local/opt/texlive/bin/pdflatex'
            ]
        },
        # macOS with MacPorts
        'macports': {
            'python_paths': [
                '/opt/local/bin/python3', '/opt/local/bin/python',
                '/opt/local/bin/python3.*',
                '/opt/local/Library/Frameworks/Python.framework/Versions/*/bin/python3'
            ],
            'pip_paths': [
                '/opt/local/bin/pip3', '/opt/local/bin/pip',
                '/opt/local/bin/pip3.*',
                '/opt/local/Library/Frameworks/Python.framework/Versions/*/bin/pip3'
            ],
            'latex_paths': [
                '/opt/local/bin/pdflatex', '/opt/local/bin/latex',
                '/opt/local/share/texmf/bin/pdflatex',
                '/opt/local/share/texmf/bin/latex'
            ]
        },
        # macOS with MacTeX
        'mactex': {
            'python_paths': [
                '/usr/bin/python3', '/usr/bin/python',
                '/usr/local/bin/python3', '/usr/local/bin/python'
            ],
            'pip_paths': [
                '/usr/bin/pip3', '/usr/bin/pip',
                '/usr/local/bin/pip3', '/usr/local/bin/pip'
            ],
            'latex_paths': [
                '/Library/TeX/texbin/pdflatex',
                '/Library/TeX/texbin/latex',
                '/usr/local/texlive/*/bin/*/pdflatex',
                '/usr/local/texlive/*/bin/*/latex',
                '/usr/texbin/pdflatex',
                '/usr/texbin/latex'
            ]
        }
    }

def get_linux_distribution_paths():
    """Get comprehensive Python and LaTeX paths for all major Linux distributions"""
    return {
        # Ubuntu/Debian paths
        'ubuntu': {
            'python_paths': [
                '/usr/bin/python3', '/usr/bin/python',
                '/usr/local/bin/python3', '/usr/local/bin/python',
                '/opt/python/bin/python3', '/opt/python/bin/python'
            ],
            'pip_paths': [
                '/usr/bin/pip3', '/usr/bin/pip',
                '/usr/local/bin/pip3', '/usr/local/bin/pip',
                '/opt/python/bin/pip3', '/opt/python/bin/pip'
            ],
            'latex_paths': [
                '/usr/bin/pdflatex', '/usr/bin/latex',
                '/usr/local/bin/pdflatex', '/usr/local/bin/latex',
                '/usr/share/texlive/bin/x86_64-linux/pdflatex',
                '/usr/share/texlive/bin/x86_64-linux/latex'
            ]
        },
        # Fedora/CentOS/RHEL paths
        'fedora': {
            'python_paths': [
                '/usr/bin/python3', '/usr/bin/python',
                '/usr/local/bin/python3', '/usr/local/bin/python',
                '/opt/python/bin/python3', '/opt/python/bin/python'
            ],
            'pip_paths': [
                '/usr/bin/pip3', '/usr/bin/pip',
                '/usr/local/bin/pip3', '/usr/local/bin/pip',
                '/opt/python/bin/pip3', '/opt/python/bin/pip'
            ],
            'latex_paths': [
                '/usr/bin/pdflatex', '/usr/bin/latex',
                '/usr/local/bin/pdflatex', '/usr/local/bin/latex',
                '/usr/share/texlive/bin/x86_64-linux/pdflatex',
                '/usr/share/texlive/bin/x86_64-linux/latex'
            ]
        },
        # Arch/Manjaro paths
        'arch': {
            'python_paths': [
                '/usr/bin/python3', '/usr/bin/python',
                '/usr/local/bin/python3', '/usr/local/bin/python',
                '/opt/python/bin/python3', '/opt/python/bin/python'
            ],
            'pip_paths': [
                '/usr/bin/pip3', '/usr/bin/pip',
                '/usr/local/bin/pip3', '/usr/local/bin/pip',
                '/opt/python/bin/pip3', '/opt/python/bin/pip'
            ],
            'latex_paths': [
                '/usr/bin/pdflatex', '/usr/bin/latex',
                '/usr/local/bin/pdflatex', '/usr/local/bin/latex',
                '/usr/share/texmf-dist/bin/pdflatex',
                '/usr/share/texmf-dist/bin/latex',
                '/var/lib/texmf/bin/pdflatex',
                '/var/lib/texmf/bin/latex'
            ]
        },
        # openSUSE paths
        'opensuse': {
            'python_paths': [
                '/usr/bin/python3', '/usr/bin/python',
                '/usr/local/bin/python3', '/usr/local/bin/python',
                '/opt/python/bin/python3', '/opt/python/bin/python'
            ],
            'pip_paths': [
                '/usr/bin/pip3', '/usr/bin/pip',
                '/usr/local/bin/pip3', '/usr/local/bin/pip',
                '/opt/python/bin/pip3', '/opt/python/bin/pip'
            ],
            'latex_paths': [
                '/usr/bin/pdflatex', '/usr/bin/latex',
                '/usr/local/bin/pdflatex', '/usr/local/bin/latex',
                '/usr/share/texlive/bin/x86_64-linux/pdflatex',
                '/usr/share/texlive/bin/x86_64-linux/latex'
            ]
        },
        # Gentoo paths
        'gentoo': {
            'python_paths': [
                '/usr/bin/python3', '/usr/bin/python',
                '/usr/local/bin/python3', '/usr/local/bin/python',
                '/opt/python/bin/python3', '/opt/python/bin/python'
            ],
            'pip_paths': [
                '/usr/bin/pip3', '/usr/bin/pip',
                '/usr/local/bin/pip3', '/usr/local/bin/pip',
                '/opt/python/bin/pip3', '/opt/python/bin/pip'
            ],
            'latex_paths': [
                '/usr/bin/pdflatex', '/usr/bin/latex',
                '/usr/local/bin/pdflatex', '/usr/local/bin/latex',
                '/usr/share/texlive/bin/x86_64-linux/pdflatex',
                '/usr/share/texlive/bin/x86_64-linux/latex'
            ]
        },
        # Alpine paths
        'alpine': {
            'python_paths': [
                '/usr/bin/python3', '/usr/bin/python',
                '/usr/local/bin/python3', '/usr/local/bin/python'
            ],
            'pip_paths': [
                '/usr/bin/pip3', '/usr/bin/pip',
                '/usr/local/bin/pip3', '/usr/local/bin/pip'
            ],
            'latex_paths': [
                '/usr/bin/pdflatex', '/usr/bin/latex',
                '/usr/local/bin/pdflatex', '/usr/local/bin/latex'
            ]
        }
    }

def find_pip_executable():
    """Find the correct pip executable for the current Python installation"""
    import sys
    import os
    import subprocess
    import shutil
    import platform
    
    # Get platform information
    system = platform.system().lower()
    is_linux = system == 'linux'
    
    # Try different pip locations with comprehensive Linux paths
    pip_candidates = []
    
    # 1. Direct pip commands (most common)
    pip_candidates.extend(['pip', 'pip3'])
    
    # 2. Python module approach (most reliable)
    pip_candidates.extend([
        f'{sys.executable} -m pip',
        f'python -m pip',
        f'python3 -m pip'
    ])
    
    # 3. Platform-specific paths
    if is_linux:
        # Get distribution-specific paths
        distro_paths = get_linux_distribution_paths()
        
        # Try to find python in PATH first
        for python_cmd in ['python3', 'python']:
            python_path = shutil.which(python_cmd)
            if python_path:
                pip_candidates.append(f'{python_path} -m pip')
        
        # Try all distribution-specific paths
        for distro, paths in distro_paths.items():
            for python_path in paths['python_paths']:
                if os.path.exists(python_path):
                    pip_candidates.append(f'{python_path} -m pip')
            
            for pip_path in paths['pip_paths']:
                if os.path.exists(pip_path):
                    pip_candidates.append(pip_path)
    elif system == 'darwin':  # macOS
        # Get Mac-specific paths
        mac_paths = get_mac_variants_paths()
        
        # Try to find python in PATH first
        for python_cmd in ['python3', 'python']:
            python_path = shutil.which(python_cmd)
            if python_path:
                pip_candidates.append(f'{python_path} -m pip')
        
        # Try all Mac variant paths
        for variant, paths in mac_paths.items():
            for python_path in paths['python_paths']:
                if os.path.exists(python_path):
                    pip_candidates.append(f'{python_path} -m pip')
            
            for pip_path in paths['pip_paths']:
                if os.path.exists(pip_path):
                    pip_candidates.append(pip_path)
    
    # 4. Additional common Linux locations
    if is_linux:
        additional_paths = [
            '/snap/bin/python3',  # Snap packages
            '/snap/bin/pip3',
            '/home/linuxbrew/.linuxbrew/bin/python3',  # Homebrew on Linux
            '/home/linuxbrew/.linuxbrew/bin/pip3',
            '/opt/homebrew/bin/python3',  # Homebrew on ARM Linux
            '/opt/homebrew/bin/pip3'
        ]
        
        for path in additional_paths:
            if os.path.exists(path):
                if 'python' in path:
                    pip_candidates.append(f'{path} -m pip')
                else:
                    pip_candidates.append(path)
    
    # Test each candidate
    for pip_cmd in pip_candidates:
        try:
            if ' -m ' in pip_cmd:
                # For python -m pip commands
                cmd_parts = pip_cmd.split()
                retcode, stdout, stderr = _safe_subprocess_run(cmd_parts + ['--version'], timeout=10)
            else:
                # For direct pip commands
                retcode, stdout, stderr = _safe_subprocess_run([pip_cmd, '--version'], timeout=10)
            
            if retcode == 0:
                return pip_cmd
        except (FileNotFoundError, OSError):
            continue
    
    return None

def diagnose_linux_distribution_issues(platform_info):
    """Diagnose and provide solutions for Linux distribution-specific issues"""
    if not platform_info['is_linux']:
        return
    
    distro = platform_info['linux_distro']
    print(f"\n🔧 DIAGNOSTIC {distro.upper()} - Chemins Python et LaTeX")
    print("=" * 60)
    
    python_paths = platform_info['python_paths']
    
    # Check Python executable
    if python_paths['python_executable']:
        print(f"✅ Python executable: {python_paths['python_executable']}")
    else:
        print("❌ Python executable not found")
    
    # Check Python3 in PATH
    if python_paths['python3_in_path']:
        print(f"✅ Python3 in PATH: {python_paths['python3_in_path']}")
    else:
        print("❌ Python3 not found in PATH")
    
    # Check pip3 in PATH
    if python_paths['pip3_in_path']:
        print(f"✅ Pip3 in PATH: {python_paths['pip3_in_path']}")
    else:
        print("❌ Pip3 not found in PATH")
    
    # Get distribution-specific paths
    distro_paths = get_linux_distribution_paths()
    if distro in distro_paths:
        paths = distro_paths[distro]
    else:
        # Use Ubuntu paths as default for unknown distributions
        paths = distro_paths['ubuntu']
    
    # Check Python paths
    print(f"\n🔍 Checking Python paths for {distro}:")
    for path in paths['python_paths']:
        import os
        if os.path.exists(path):
            print(f"✅ {path}")
        else:
            print(f"❌ {path}")
    
    # Check pip paths
    print(f"\n🔍 Checking Pip paths for {distro}:")
    for path in paths['pip_paths']:
        import os
        if os.path.exists(path):
            print(f"✅ {path}")
        else:
            print(f"❌ {path}")
    
    # Check LaTeX paths
    print(f"\n🔍 Checking LaTeX paths for {distro}:")
    for path in paths['latex_paths']:
        import os
        if os.path.exists(path):
            print(f"✅ {path}")
        else:
            print(f"❌ {path}")
    
    # Provide distribution-specific solutions
    print(f"\n💡 Recommended solutions for {distro.upper()}:")
    
    if distro in ['ubuntu', 'debian']:
        print("   Python: sudo apt update && sudo apt install python3 python3-pip")
        print("   LaTeX: sudo apt install texlive-full")
        print("   Packages: sudo apt install python3-astropy python3-matplotlib python3-pillow")
    elif distro in ['fedora', 'centos', 'rhel']:
        print("   Python: sudo dnf install python3 python3-pip")
        print("   LaTeX: sudo dnf install texlive-scheme-full")
        print("   Packages: sudo dnf install python3-astropy python3-matplotlib python3-pillow")
    elif distro in ['arch', 'manjaro']:
        print("   Python: sudo pacman -S python python-pip")
        print("   LaTeX: sudo pacman -S texlive-most texlive-lang")
        print("   Packages: sudo pacman -S python-astropy python-matplotlib python-pillow")
    elif distro in ['opensuse', 'suse']:
        print("   Python: sudo zypper install python3 python3-pip")
        print("   LaTeX: sudo zypper install texlive")
        print("   Packages: sudo zypper install python3-astropy python3-matplotlib python3-pillow")
    elif distro == 'gentoo':
        print("   Python: emerge dev-lang/python")
        print("   LaTeX: emerge app-text/texlive")
        print("   Packages: emerge dev-python/astropy dev-python/matplotlib dev-python/pillow")
    elif distro == 'alpine':
        print("   Python: apk add python3 py3-pip")
        print("   LaTeX: apk add texlive")
        print("   Packages: apk add py3-astropy py3-matplotlib py3-pillow")
    else:
        print("   Python: Install python3 and python3-pip using your package manager")
        print("   LaTeX: Install texlive or texlive-full using your package manager")
        print("   Packages: Install python3-astropy, python3-matplotlib, python3-pillow")

def diagnose_mac_variants_issues(platform_info):
    """Diagnose and provide solutions for Mac variant-specific issues"""
    if not platform_info['is_macos']:
        return
    
    mac_variant = platform_info['mac_variant']
    print(f"\n🍎 DIAGNOSTIC MAC - {mac_variant.upper()} - Chemins Python et LaTeX")
    print("=" * 70)
    
    python_paths = platform_info['python_paths']
    
    # Check Python executable
    if python_paths['python_executable']:
        print(f"✅ Python executable: {python_paths['python_executable']}")
    else:
        print("❌ Python executable not found")
    
    # Check Python3 in PATH
    if python_paths['python3_in_path']:
        print(f"✅ Python3 in PATH: {python_paths['python3_in_path']}")
    else:
        print("❌ Python3 not found in PATH")
    
    # Check pip3 in PATH
    if python_paths['pip3_in_path']:
        print(f"✅ Pip3 in PATH: {python_paths['pip3_in_path']}")
    else:
        print("❌ Pip3 not found in PATH")
    
    # Get Mac-specific paths
    mac_paths = get_mac_variants_paths()
    
    # Determine which variant to check
    variant_to_check = 'apple_silicon' if platform_info['is_apple_silicon'] else 'intel'
    if platform_info['has_homebrew']:
        variant_to_check = 'homebrew'
    elif platform_info['has_macports']:
        variant_to_check = 'macports'
    elif platform_info['has_mactex']:
        variant_to_check = 'mactex'
    
    if variant_to_check in mac_paths:
        paths = mac_paths[variant_to_check]
    else:
        # Use Apple Silicon as default for unknown variants
        paths = mac_paths['apple_silicon']
    
    # Check Python paths
    print(f"\n🔍 Checking Python paths for {mac_variant}:")
    for path in paths['python_paths']:
        import os
        if os.path.exists(path):
            print(f"✅ {path}")
        else:
            print(f"❌ {path}")
    
    # Check pip paths
    print(f"\n🔍 Checking Pip paths for {mac_variant}:")
    for path in paths['pip_paths']:
        import os
        if os.path.exists(path):
            print(f"✅ {path}")
        else:
            print(f"❌ {path}")
    
    # Check LaTeX paths
    print(f"\n🔍 Checking LaTeX paths for {mac_variant}:")
    for path in paths['latex_paths']:
        import os
        if os.path.exists(path):
            print(f"✅ {path}")
        else:
            print(f"❌ {path}")
    
    # Provide Mac-specific solutions
    print(f"\n💡 Recommended solutions for {mac_variant.upper()}:")
    
    if platform_info['is_apple_silicon']:
        print("   🍎 Apple Silicon (M1/M2/M3) Mac:")
        print("   Python: brew install python")
        print("   LaTeX: brew install --cask mactex")
        print("   Packages: brew install python-astropy python-matplotlib python-pillow")
    elif platform_info['is_intel_mac']:
        print("   🍎 Intel Mac:")
        print("   Python: brew install python")
        print("   LaTeX: brew install --cask mactex")
        print("   Packages: brew install python-astropy python-matplotlib python-pillow")
    
    if platform_info['has_homebrew']:
        print("   🍺 Homebrew detected:")
        print("   Python: brew install python")
        print("   LaTeX: brew install --cask mactex")
        print("   Packages: brew install python-astropy python-matplotlib python-pillow")
    elif platform_info['has_macports']:
        print("   🍺 MacPorts detected:")
        print("   Python: sudo port install python3 py3-pip")
        print("   LaTeX: sudo port install texlive")
        print("   Packages: sudo port install py3-astropy py3-matplotlib py3-pillow")
    else:
        print("   📦 Recommended installation:")
        print("   1. Install Homebrew: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
        print("   2. Install Python: brew install python")
        print("   3. Install LaTeX: brew install --cask mactex")
        print("   4. Install packages: brew install python-astropy python-matplotlib python-pillow")

def diagnose_manjaro_python_issues(platform_info):
    """Legacy function - now redirects to comprehensive Linux diagnostic"""
    diagnose_linux_distribution_issues(platform_info)

def install_python_packages_automatically():
    """Attempt to install missing Python packages automatically"""
    package_status = check_python_packages()
    
    if package_status['all_available']:
        print("✅ All required Python packages are available!")
        return True
    
    missing = package_status['missing']
    print(f"⚠️  Missing Python packages: {', '.join(missing)}")
    print("   🤖 Attempting automatic installation...")
    
    # Find working pip executable
    pip_cmd = find_pip_executable()
    if not pip_cmd:
        print("   ❌ Could not find pip executable")
        print("   💡 Solutions:")
        print("      1. Use: python -m pip install <package>")
        print("      2. Or install pip: python -m ensurepip --upgrade")
        print("      3. Or use Anaconda: https://www.anaconda.com/download")
        return False
    
    print(f"   🔍 Found pip: {pip_cmd}")
    
    try:
        import subprocess
        import sys
        import platform
        
        # Try to install missing packages with multiple strategies
        failed_packages = []
        is_windows = platform.system().lower() == 'windows'
        
        for package in missing:
            print(f"   📦 Installing {package}...")
            success = False
            
            # Strategy 1: Try pre-compiled wheels first (especially for Windows)
            if is_windows:
                try:
                    if ' -m ' in pip_cmd:
                        cmd_parts = pip_cmd.split() + ['install', package, '--only-binary=all', '--upgrade', '--quiet']
                    else:
                        cmd_parts = [pip_cmd, 'install', package, '--only-binary=all', '--upgrade', '--quiet']
                    
                    retcode, stdout, stderr = _safe_subprocess_run(cmd_parts, timeout=300)
                    
                    if retcode == 0:
                        print(f"   ✅ {package} installed successfully (pre-compiled)")
                        success = True
                    else:
                        print(f"   ⚠️  Pre-compiled version failed, trying other methods...")
                except Exception as e:
                    print(f"   ⚠️  Pre-compiled installation failed: {e}")
            
            # Strategy 2: Try regular pip install
            if not success:
                try:
                    if ' -m ' in pip_cmd:
                        cmd_parts = pip_cmd.split() + ['install', package, '--upgrade', '--quiet']
                    else:
                        cmd_parts = [pip_cmd, 'install', package, '--upgrade', '--quiet']
                    
                    retcode, stdout, stderr = _safe_subprocess_run(cmd_parts, timeout=300)
                    
                    if retcode == 0:
                        print(f"   ✅ {package} installed successfully")
                        success = True
                    else:
                        print(f"   ❌ Failed to install {package}")
                        if 'compiler' in stderr.lower() or 'build' in stderr.lower():
                            print(f"   💡 {package} requires compilation - missing C++ compiler")
                        
                except Exception as e:
                    print(f"   ❌ Error installing {package}: {e}")
            
            if not success:
                failed_packages.append(package)
        
        # Re-check packages after installation
        print("\n   🔍 Re-checking packages...")
        new_status = check_python_packages()
        
        if new_status['all_available']:
            print("✅ All packages are now available!")
            # Try to re-check astropy availability in current session
            if recheck_astropy_availability():
                print("   🎉 Astropy is now available in current session!")
                return True
            else:
                print("   🔄 Please restart the program for changes to take effect.")
                print("   💡 The newly installed packages will be available on the next run.")
                return True
        else:
            still_missing = new_status['missing']
            print(f"⚠️  Still missing: {', '.join(still_missing)}")
            
            # Provide comprehensive solutions for failed packages
            print("\n   🔧 Alternative solutions for failed packages:")
            print("      📦 For packages requiring compilation (matplotlib, pandas, scipy):")
            print()
            print("      🚀 QUICK SOLUTION - Use Anaconda/Miniconda:")
            print("         1. Download Anaconda: https://www.anaconda.com/download")
            print("         2. Install Anaconda")
            print("         3. Run: conda install matplotlib pandas scipy")
            print("         4. Run: pip install reportlab tqdm astropy pillow")
            print()
            print("      🔧 ALTERNATIVE - Manual installation:")
            print("         1. Install Visual Studio Build Tools:")
            print("            https://visualstudio.microsoft.com/visual-cpp-build-tools/")
            print("         2. Restart command prompt")
            print("         3. Run: pip install matplotlib pandas scipy")
            print()
            print("      🎯 SPECIFIC COMMANDS for your system:")
            print("         # Try pre-compiled versions:")
            print("         pip install --only-binary=all matplotlib pandas scipy")
            print("         pip install reportlab tqdm astropy pillow")
            print()
            print("         # Or use conda for scientific packages:")
            print("         conda install matplotlib pandas scipy")
            print("         pip install reportlab tqdm astropy pillow")
            print()
            print("      💡 TIP: Anaconda is the easiest solution for Windows!")
            
            return False
            
    except ImportError:
        print("   ❌ subprocess module not available for automatic installation")
        return False
    except Exception as e:
        print(f"   ❌ Error during automatic installation: {e}")
        return False

def suggest_python_installation():
    """Suggest Python package installation commands"""
    package_status = check_python_packages()
    
    if package_status['all_available']:
        print("✅ All required Python packages are available!")
        return True
    
    missing = package_status['missing']
    print(f"⚠️  Missing Python packages: {', '.join(missing)}")
    
    # Ask user if they want automatic installation
    try:
        response = input("   🤖 Would you like to install missing packages automatically? (y/n): ").lower().strip()
        if response in ['y', 'yes', 'oui', 'o']:
            if install_python_packages_automatically():
                return True
    except (KeyboardInterrupt, EOFError):
        print("\n   ⏹️  Installation cancelled by user")
    
    # Show manual installation instructions with correct pip commands
    print("   🐍 Manual installation commands:")
    print("      # Try these commands in order:")
    print(f"      python -m pip install {' '.join(missing)}")
    print()
    print("   📦 Or install all at once:")
    print("      python -m pip install matplotlib numpy pandas reportlab tqdm astropy pillow scipy")
    print()
    print("   🔧 Alternative installation methods:")
    print("      # Using conda (if available):")
    print("      conda install matplotlib numpy pandas scipy astropy")
    print("      python -m pip install reportlab tqdm pillow")
    print()
    print("      # Using pip with requirements file:")
    print("      python -m pip install -r requirements.txt")
    print()
    print("   💡 If 'python -m pip' doesn't work, try:")
    print("      py -m pip install <package>")
    print("      or")
    print("      python3 -m pip install <package>")
    print()
    
    return False

def get_platform_latex_instructions():
    """Get platform-specific LaTeX installation instructions with package details"""
    import platform
    
    system = platform.system().lower()
    required_packages = get_required_latex_packages()
    
    if system == 'windows':
        return {
            'name': 'Windows',
            'distributions': [
                {
                    'name': 'MiKTeX (Recommended)',
                    'url': 'https://miktex.org/download',
                    'install_cmd': 'Download and run the installer',
                    'package_install': 'MiKTeX Console → Packages → Install missing packages automatically',
                    'description': 'LaTeX distribution optimized for Windows with automatic package installation'
                },
                {
                    'name': 'TeX Live',
                    'url': 'https://www.tug.org/texlive/acquire-netinst.html',
                    'install_cmd': 'Download and run the installer',
                    'package_install': 'tlmgr install <package_name>',
                    'description': 'Complete and cross-platform LaTeX distribution'
                },
                {
                    'name': 'TeXstudio (Editor)',
                    'url': 'https://www.texstudio.org/',
                    'install_cmd': 'Download and install',
                    'package_install': 'Requires MiKTeX or TeX Live',
                    'description': 'Modern LaTeX editor with graphical interface'
                }
            ],
            'package_managers': [
                {
                    'name': 'Chocolatey',
                    'install_cmd': 'choco install miktex',
                    'url': 'https://chocolatey.org/',
                    'description': 'Gestionnaire de packages pour Windows'
                },
                {
                    'name': 'Winget',
                    'install_cmd': 'winget install MiKTeX.MiKTeX',
                    'url': 'https://docs.microsoft.com/en-us/windows/package-manager/',
                    'description': 'Gestionnaire de packages natif Windows 10/11'
                }
            ],
            'alternatives': [
                {
                    'name': 'Overleaf (Online)',
                    'url': 'https://www.overleaf.com/',
                    'description': 'Online LaTeX editor, no installation required'
                },
                {
                    'name': 'Typst (Modern)',
                    'url': 'https://typst.app/',
                    'description': 'Modern alternative to LaTeX with simplified syntax'
                }
            ]
        }
    elif system == 'darwin':
        return {
            'name': 'macOS',
            'distributions': [
                {
                    'name': 'MacTeX (Recommended)',
                    'url': 'https://www.tug.org/mactex/',
                    'install_cmd': 'Download and run the installer',
                    'package_install': 'TeX Live Utility → Install packages',
                    'description': 'Complete LaTeX distribution for macOS'
                },
                {
                    'name': 'BasicTeX',
                    'url': 'https://www.tug.org/mactex/morepackages.html',
                    'install_cmd': 'Download BasicTeX (lighter)',
                    'package_install': 'tlmgr install <package_name>',
                    'description': 'Lightweight version of MacTeX'
                }
            ],
            'package_managers': [
                {
                    'name': 'Homebrew',
                    'install_cmd': 'brew install --cask mactex',
                    'url': 'https://brew.sh/',
                    'description': 'Gestionnaire de packages pour macOS'
                },
                {
                    'name': 'MacPorts',
                    'install_cmd': 'sudo port install texlive',
                    'url': 'https://www.macports.org/',
                    'description': 'Alternative to Homebrew'
                }
            ],
            'alternatives': [
                {
                    'name': 'Overleaf (Online)',
                    'url': 'https://www.overleaf.com/',
                    'description': 'Online LaTeX editor'
                },
                {
                    'name': 'Typst (Modern)',
                    'url': 'https://typst.app/',
                    'description': 'Modern alternative to LaTeX'
                }
            ]
        }
    else:  # Linux and others
        return {
            'name': 'Linux',
            'distributions': [
                {
                    'name': 'TeX Live (Ubuntu/Debian)',
                    'install_cmd': 'sudo apt install texlive-full texlive-latex-extra',
                    'package_install': 'sudo apt install texlive-latex-extra',
                    'description': 'Complete distribution via apt'
                },
                {
                    'name': 'TeX Live (Fedora/RHEL)',
                    'install_cmd': 'sudo dnf install texlive-scheme-full',
                    'package_install': 'sudo dnf install texlive-latex-extra',
                    'description': 'Complete distribution via dnf'
                },
                {
                    'name': 'TeX Live (Arch Linux)',
                    'install_cmd': 'sudo pacman -S texlive-most texlive-lang',
                    'package_install': 'sudo pacman -S texlive-latexextra',
                    'description': 'Complete distribution via pacman'
                },
                {
                    'name': 'TeX Live (openSUSE)',
                    'install_cmd': 'sudo zypper install texlive',
                    'package_install': 'sudo zypper install texlive-latex',
                    'description': 'Distribution via zypper'
                },
                {
                    'name': 'TeX Live (Gentoo)',
                    'install_cmd': 'emerge app-text/texlive',
                    'package_install': 'emerge app-text/texlive-latex',
                    'description': 'Distribution via emerge'
                }
            ],
            'package_managers': [
                {
                    'name': 'Snap',
                    'install_cmd': 'sudo snap install texlive',
                    'url': 'https://snapcraft.io/',
                    'description': 'Packages universels Linux'
                },
                {
                    'name': 'Flatpak',
                    'install_cmd': 'flatpak install flathub org.texlive.TeXLive',
                    'url': 'https://flatpak.org/',
                    'description': 'Packages universels Linux'
                }
            ],
            'manual_install': {
                'url': 'https://www.tug.org/texlive/',
                'instructions': 'Download and run the install-tl script',
                'description': 'Manual TeX Live installation'
            },
            'alternatives': [
                {
                    'name': 'Overleaf (Online)',
                    'url': 'https://www.overleaf.com/',
                    'description': 'Online LaTeX editor'
                },
                {
                    'name': 'Typst (Modern)',
                    'url': 'https://typst.app/',
                    'description': 'Modern alternative to LaTeX'
                }
            ]
        }

def display_latex_installation_suggestions():
    """Display LaTeX installation suggestions for the current platform"""
    instructions = get_platform_latex_instructions()
    
    print(f"\n{'='*80}")
    print(f"📄 MISSING LaTeX DISTRIBUTION - {instructions['name'].upper()}")
    print(f"{'='*80}")
    print(f"❌ No LaTeX distribution detected on your {instructions['name']} system")
    print(f"📋 Here are the recommended options to install LaTeX:")
    print()
    
    # Distributions principales
    print("🎯 RECOMMENDED DISTRIBUTIONS:")
    print("-" * 50)
    for i, dist in enumerate(instructions['distributions'], 1):
        print(f"{i}. {dist['name']}")
        print(f"   📝 Description: {dist['description']}")
        print(f"   🔗 Link: {dist['url']}")
        print(f"   ⚙️  Installation: {dist['install_cmd']}")
        if 'package_install' in dist:
            print(f"   📦 Packages: {dist['package_install']}")
        print()
    
    # Package managers
    if 'package_managers' in instructions:
        print("📦 PACKAGE MANAGERS:")
        print("-" * 50)
        for pm in instructions['package_managers']:
            print(f"• {pm['name']}")
            print(f"  📝 Description: {pm['description']}")
            print(f"  🔗 Link: {pm['url']}")
            print(f"  ⚙️  Installation: {pm['install_cmd']}")
            print()
    
    # Installation manuelle
    if 'manual_install' in instructions:
        print("🔧 MANUAL INSTALLATION:")
        print("-" * 50)
        print(f"• {instructions['manual_install']['description']}")
        print(f"  🔗 Link: {instructions['manual_install']['url']}")
        print(f"  ⚙️  Instructions: {instructions['manual_install']['instructions']}")
        print()
    
    # Alternatives
    if 'alternatives' in instructions:
        print("🌐 ALTERNATIVES (No installation required):")
        print("-" * 50)
        for alt in instructions['alternatives']:
            print(f"• {alt['name']}")
            print(f"  📝 Description: {alt['description']}")
            print(f"  🔗 Link: {alt['url']}")
            print()
    
    print("💡 TIP: For a quick installation, we recommend:")
    if instructions['name'] == 'Windows':
        print("   1. Download MiKTeX from https://miktex.org/download")
        print("   2. Or use: winget install MiKTeX.MiKTeX")
    elif instructions['name'] == 'macOS':
        print("   1. Download MacTeX from https://www.tug.org/mactex/")
        print("   2. Or use: brew install --cask mactex")
    else:  # Linux
        print("   1. Use your package manager:")
        print("      • Ubuntu/Debian: sudo apt install texlive-full")
        print("      • Fedora: sudo dnf install texlive-scheme-full")
        print("      • Arch: sudo pacman -S texlive-most")
    
    print(f"\n{'='*80}")
    print("⚠️  After installation, restart this program to generate LaTeX reports")
    print(f"{'='*80}\n")

def cleanup_latex_temp_files(output_folder):
    """Clean up LaTeX temporary files after compilation"""
    import os
    
    # LaTeX temporary file extensions to clean
    temp_extensions = ['.aux', '.log', '.out', '.synctex.gz', '.toc', '.lof', '.lot', 
                       '.fls', '.fdb_latexmk', '.bbl', '.blg', '.nav', '.snm', '.vrb']
    
    cleaned_files = []
    
    try:
        print(f"🔍 Searching for temporary files in: {output_folder}")
        
        # Check if the folder exists (try both relative and absolute paths)
        if not os.path.exists(output_folder):
            # Try to find the folder in current directory
            current_dir = os.getcwd()
            potential_path = os.path.join(current_dir, output_folder)
            if os.path.exists(potential_path):
                output_folder = potential_path
                print(f"   📁 Folder found in current directory: {output_folder}")
            else:
                # Maybe we're already in the output folder, try current directory
                if os.path.basename(current_dir) == output_folder:
                    output_folder = current_dir
                    print(f"   📁 We are already in the output folder: {output_folder}")
                else:
                    print(f"   ❌ Folder does not exist: {output_folder}")
                    print(f"   🔍 Current directory: {current_dir}")
                    return
        
        # Get all files in the directory
        all_files = os.listdir(output_folder)
        print(f"   📁 Files in folder: {len(all_files)}")
        
        # Look for files with temporary extensions
        for filename in all_files:
            file_path = os.path.join(output_folder, filename)
            
            # Check if file has a temporary extension
            should_delete = False
            for ext in temp_extensions:
                if filename.endswith(ext):
                    should_delete = True
                    break
            
            if should_delete:
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        cleaned_files.append(filename)
                        print(f"   ✅ Deleted: {filename}")
                except (OSError, PermissionError) as e:
                    print(f"   ❌ Unable to delete {filename}: {e}")
        
        if cleaned_files:
            print(f"🧹 Cleanup completed: {len(cleaned_files)} temporary file(s) deleted")
        else:
            print("🧹 No LaTeX temporary files found")
            
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")

def select_best_fits_for_thumbnail(target_data):
    """
    Selects the best FITS image for creating a thumbnail.
    Priority: Luminance > H-alpha > Other filter with most signal
    Avoids cloudy images by checking for good signal-to-noise ratio
    """
    if not target_data or not target_data.get('files'):
        return None
    
    # Separate files by filter
    files_by_filter = {}
    for file_data in target_data['files']:
        filter_name = file_data['info']['filter']
        if filter_name not in files_by_filter:
            files_by_filter[filter_name] = []
        files_by_filter[filter_name].append(file_data)
    
    def evaluate_file_quality(file_data):
        """Evaluate file quality based on exposure time and potential signal"""
        exposure_time = file_data['info'].get('exposure_time') or 0  # Use 0 if None
        # Prefer longer exposures (more signal) but not too long (might be saturated)
        # Also consider if it's a science frame vs calibration
        is_science = not file_data['info'].get('is_calibration', False)
        
        # Penalize very long exposures that might be saturated
        # Optimal range: 60-180s for most objects
        if exposure_time > 300:
            quality_multiplier = 0.3  # Strong penalty for very long exposures
        elif exposure_time > 180:
            quality_multiplier = 0.6  # Penalty for long exposures
        elif exposure_time < 30:
            quality_multiplier = 0.7  # Penalty for very short exposures
        else:
            quality_multiplier = 1.0  # Optimal range
        
        # Additional check for potential saturation issues
        # If exposure time is very long (>240s), it might be saturated
        if exposure_time > 240:
            quality_multiplier *= 0.5  # Additional penalty for potentially saturated images
        
        return exposure_time * (2 if is_science else 1) * quality_multiplier
    
    # Priority 1: Luminance - best for thumbnails
    # Use FILTERS_INFO to get all luminance-related filters
    luminance_filters = [filter_name for filter_name in FILTERS_INFO.keys() 
                       if FILTERS_INFO[filter_name]['name'] == 'Luminance']
    for lum_filter in luminance_filters:
        if lum_filter in files_by_filter:
            luminance_files = files_by_filter[lum_filter]
            
            # For bright objects like M31, prefer shorter exposures to avoid saturation
            # Try different possible keys for target name
            target_name = ''
            for key in ['target', 'name', 'object', 'target_name']:
                if key in target_data:
                    target_name = str(target_data[key]).upper()
                    break
            
            # If still empty, try to extract from the first file path
            if not target_name and target_data.get('files'):
                first_file = target_data['files'][0]
                if 'path' in first_file:
                    file_path = first_file['path']
                    # Extract target from filename (e.g., LIGHT_M31_... -> M31, LIGHT_M 82_... -> M 82)
                    import re
                    # Try different patterns for target extraction
                    patterns = [
                        r'LIGHT_([^_]+)_',  # LIGHT_M31_...
                        r'LIGHT_([^_]+)_\d{4}-\d{2}-\d{2}',  # LIGHT_M 82_2025-04-27...
                        r'LIGHT_([A-Za-z0-9\s]+)_\d{4}',  # LIGHT_M 82_2025...
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, file_path)
                        if match:
                            target_name = match.group(1).upper()
                            break
            
            # Normalize target name by removing spaces and common variations
            normalized_target = target_name.replace(' ', '').replace('_', '').replace('-', '')
            
            # Enhanced bright object detection
            bright_objects = ['M31', 'M31ANDROMEDA', 'ANDROMEDA', 'M82', 'M82CIGAR', 'CIGAR', 'M42', 'ORION', 'M45', 'PLEIADES', 'M1', 'CRAB', 'M51', 'M51WHIRLPOOL', 'M101', 'M101']
            is_bright_object = any(bright_object in normalized_target for bright_object in bright_objects)
            
            if is_bright_object:
                print(f"   ⭐ Bright object detected, using shorter exposure preference")
                # Prefer exposures between 30-90s for bright objects to avoid saturation
                def evaluate_bright_object_quality(file_data):
                    exposure_time = file_data['info'].get('exposure_time') or 0  # Use 0 if None
                    is_science = not file_data['info'].get('is_calibration', False)
                    
                    # Optimal range for bright objects: 30-90s (shorter to avoid saturation)
                    if 30 <= exposure_time <= 90:
                        return exposure_time * (2 if is_science else 1) * 2.0  # Strong bonus for optimal range
                    elif 15 <= exposure_time < 30:
                        return exposure_time * (2 if is_science else 1) * 1.5  # Good range
                    elif 90 < exposure_time <= 120:
                        return exposure_time * (2 if is_science else 1) * 1.0  # Acceptable
                    elif exposure_time > 120:
                        return exposure_time * (2 if is_science else 1) * 0.3  # Strong penalty for long exposures
                    else:
                        return exposure_time * (2 if is_science else 1) * 0.8  # Penalty for very short
                
                best_l_file = max(luminance_files, key=evaluate_bright_object_quality)
            else:
                best_l_file = max(luminance_files, key=evaluate_file_quality)
            return best_l_file
    
    # Priority 2: H-alpha - good contrast for nebulae
    # Use the comprehensive FILTERS_INFO database for H-alpha detection
    ha_filters = [filter_name for filter_name in FILTERS_INFO.keys() 
                  if FILTERS_INFO[filter_name]['name'] == 'Hydrogen Alpha']
    for ha_filter in ha_filters:
        if ha_filter in files_by_filter:
            ha_files = files_by_filter[ha_filter]
            best_ha_file = max(ha_files, key=evaluate_file_quality)
            return best_ha_file
    
    # Priority 3: RGB filters - good for color objects
    # Use FILTERS_INFO to get all RGB-related filters
    rgb_filters = [filter_name for filter_name in FILTERS_INFO.keys() 
                   if FILTERS_INFO[filter_name]['name'] in ['Red', 'Green', 'Blue']]
    for filter_name in rgb_filters:
        if filter_name in files_by_filter:
            rgb_files = files_by_filter[filter_name]
            best_rgb_file = max(rgb_files, key=evaluate_file_quality)
            return best_rgb_file
    
    # Priority 4: Other filter with best quality
    if files_by_filter:
        best_file = None
        best_quality = 0
        best_filter = None
        for filter_name, files in files_by_filter.items():
            for file_data in files:
                quality = evaluate_file_quality(file_data)
                if quality > best_quality:
                    best_quality = quality
                    best_file = file_data
                    best_filter = filter_name
        return best_file
    
    return None

def generate_thumbnails_sequential(data_by_target, output_folder):
    """
    Generate thumbnails sequentially for maximum stability.
    Avoids thread-related crashes and memory issues.
    
    Args:
        data_by_target: Dictionary of target data
        output_folder: Output folder path
    
    Returns:
        dict: Results of thumbnail generation
    """
    import time
    
    print(f"🖼️  Generating thumbnails sequentially for maximum stability...")
    
    # Prepare tasks
    tasks = []
    for target, data in data_by_target.items():
        if not data['files'] or is_calibration_target(target):
            continue
            
        best_fits_file = select_best_fits_for_thumbnail(data)
        if best_fits_file:
            thumbnail_filename = f"thumbnail_{target.replace(' ', '_').replace('/', '_').replace('\\', '_').replace(':', '_')}.png"
            thumbnail_path = os.path.join(output_folder, thumbnail_filename)
            
            tasks.append({
                'target': target,
                'fits_file': best_fits_file,
                'thumbnail_path': thumbnail_path,
                'thumbnail_filename': thumbnail_filename
            })
    
    if not tasks:
        return {}
    
    # Process thumbnails sequentially
    results = {}
    start_time = time.time()
    
    for i, task in enumerate(tasks, 1):
        target = task['target']
        print(f"📸 Processing {target}... ({i}/{len(tasks)})")
        
        try:
            success = create_fits_thumbnail_pil(task['fits_file']['path'], task['thumbnail_path'])
            if success:
                print(f"   ✅ Thumbnail created: {task['thumbnail_filename']}")
                results[target] = {
                    'success': True,
                    'thumbnail_path': task['thumbnail_path'],
                    'thumbnail_filename': task['thumbnail_filename'],
                    'fits_file': task['fits_file']
                }
            else:
                print(f"   ❌ Failed to create thumbnail for {target}")
                results[target] = {'success': False}
        except Exception as e:
            print(f"   ❌ Error creating thumbnail for {target}: {e}")
            results[target] = {'success': False, 'error': str(e)}
    
    elapsed_time = time.time() - start_time
    print(f"⚡ Sequential thumbnail generation completed in {elapsed_time:.1f}s")
    
    return results

def generate_thumbnails_parallel_robust(data_by_target, output_folder, max_workers=None):
    """
    Generate thumbnails in parallel with improved stability and crash prevention.
    OPTIMIZED: Enhanced performance with intelligent caching and memory management.
    
    Args:
        data_by_target: Dictionary of target data
        output_folder: Output folder path
        max_workers: Maximum number of parallel workers (default: optimized for performance)
    
    Returns:
        dict: Results of thumbnail generation
    """
    import concurrent.futures
    import multiprocessing
    import time
    import gc
    import hashlib
    
    # Use more workers for better performance while maintaining stability
    if max_workers is None:
        # Use up to 75% of CPU cores, but at least 2 and at most 8
        max_workers = max(2, min(8, int(multiprocessing.cpu_count() * 0.75)))
    
    print(f"🚀 Generating thumbnails in parallel using {max_workers} workers (OPTIMIZED robust mode)...")
    
    # NO CACHE: Always regenerate thumbnails for consistent quality
    
    # Prepare tasks - NO CACHE, always generate fresh
    print(f"   📋 Préparation des tâches de génération de thumbnails...")
    tasks = []
    
    for target, data in data_by_target.items():
        if not data['files'] or is_calibration_target(target):
            continue
            
        best_fits_file = select_best_fits_for_thumbnail(data)
        if best_fits_file:
            thumbnail_filename = f"thumbnail_{target.replace(' ', '_').replace('/', '_').replace('\\', '_').replace(':', '_')}.png"
            thumbnail_path = os.path.join(output_folder, thumbnail_filename)
            
            tasks.append({
                'target': target,
                'fits_file': best_fits_file,
                'thumbnail_path': thumbnail_path,
                'thumbnail_filename': thumbnail_filename
            })
    
    if not tasks:
        print("⚠️  No thumbnail tasks to process - this might indicate no valid targets found")
        return {}
    
    print(f"   ✓ {len(tasks)} thumbnail(s) à générer")
    print(f"   ⏳ Génération en cours...")
    
    # Process thumbnails in parallel with timeout and error handling
    results = {}
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks with timeout
        future_to_task = {}
        for task in tasks:
            future = executor.submit(create_fits_thumbnail_optimized, 
                                   task['fits_file']['path'], 
                                   task['thumbnail_path'])
            future_to_task[future] = task
        
        print(f"   ✓ {len(tasks)} tâche(s) soumise(s) aux {max_workers} worker(s)")
        
        # Process completed tasks with timeout
        completed = 0
        if TQDM_AVAILABLE:
            # Use progress bar for thumbnails
            from tqdm import tqdm
            progress_bar = tqdm(total=len(tasks), desc="🖼️  Generating thumbnails", unit="thumb")
        
        for future in concurrent.futures.as_completed(future_to_task, timeout=300):  # 5 min timeout
            task = future_to_task[future]
            target = task['target']
            completed += 1
            
            try:
                success = future.result(timeout=60)  # 1 min per task
                if success:
                    if TQDM_AVAILABLE:
                        progress_bar.update(1)
                    else:
                        print(f"   ✅ Thumbnail created: {task['thumbnail_filename']} ({completed}/{len(tasks)})")
                    results[target] = {
                        'success': True,
                        'thumbnail_path': task['thumbnail_path'],
                        'thumbnail_filename': task['thumbnail_filename'],
                        'fits_file': task['fits_file']
                    }
                else:
                    if TQDM_AVAILABLE:
                        progress_bar.update(1)
                    else:
                        print(f"   ❌ Failed to create thumbnail for {target}")
                    results[target] = {'success': False}
            except concurrent.futures.TimeoutError:
                if TQDM_AVAILABLE:
                    progress_bar.update(1)
                else:
                    print(f"   ⏰ Timeout creating thumbnail for {target}")
                results[target] = {'success': False, 'error': 'timeout'}
            except Exception as e:
                if TQDM_AVAILABLE:
                    progress_bar.update(1)
                else:
                    print(f"   ❌ Error creating thumbnail for {target}: {e}")
                results[target] = {'success': False, 'error': str(e)}
            
            # OPTIMIZATION: Intelligent garbage collection
            if completed % 5 == 0:  # Only collect every 5 tasks to reduce overhead
                gc.collect()
    
    if TQDM_AVAILABLE:
        progress_bar.close()
    
    elapsed_time = time.time() - start_time
    successful = sum(1 for r in results.values() if r.get('success', False))
    print(f"⚡ Parallel thumbnail generation completed in {elapsed_time:.1f}s")
    print(f"   ✅ {successful}/{len(tasks)} thumbnail(s) généré(s) avec succès")
    
    return results

def generate_thumbnails_parallel(data_by_target, output_folder, max_workers=None):
    """
    Generate thumbnails in parallel for better performance.
    
    Args:
        data_by_target: Dictionary of target data
        output_folder: Output folder path
        max_workers: Maximum number of parallel workers (default: CPU count)
    
    Returns:
        dict: Results of thumbnail generation
    """
    import concurrent.futures
    import multiprocessing
    import time
    
    if max_workers is None:
        max_workers = min(multiprocessing.cpu_count(), 4)  # Limit to 4 to avoid memory issues
    
    print(f"🚀 Generating thumbnails in parallel using {max_workers} workers...")
    
    # Prepare tasks
    tasks = []
    for target, data in data_by_target.items():
        if not data['files'] or is_calibration_target(target):
            continue
            
        best_fits_file = select_best_fits_for_thumbnail(data)
        if best_fits_file:
            thumbnail_filename = f"thumbnail_{target.replace(' ', '_').replace('/', '_').replace('\\', '_').replace(':', '_')}.png"
            thumbnail_path = os.path.join(output_folder, thumbnail_filename)
            
            tasks.append({
                'target': target,
                'fits_file': best_fits_file,
                'thumbnail_path': thumbnail_path,
                'thumbnail_filename': thumbnail_filename
            })
    
    if not tasks:
        return {}
    
    # Process thumbnails in parallel
    results = {}
    start_time = time.time()
    
    # Use ThreadPoolExecutor with proper matplotlib backend handling
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks using the PIL version to avoid matplotlib thread issues
        future_to_task = {
            executor.submit(create_fits_thumbnail_pil, task['fits_file']['path'], task['thumbnail_path']): task
            for task in tasks
        }
        
        # Process completed tasks
        completed = 0
        for future in concurrent.futures.as_completed(future_to_task):
            task = future_to_task[future]
            target = task['target']
            completed += 1
            
            try:
                success = future.result()
                if success:
                    print(f"   ✅ Thumbnail created: {task['thumbnail_filename']} ({completed}/{len(tasks)})")
                    results[target] = {
                        'success': True,
                        'thumbnail_path': task['thumbnail_path'],
                        'thumbnail_filename': task['thumbnail_filename'],
                        'fits_file': task['fits_file']
                    }
                else:
                    print(f"   ❌ Failed to create thumbnail for {target}")
                    results[target] = {'success': False}
            except Exception as e:
                print(f"   ❌ Error creating thumbnail for {target}: {e}")
                results[target] = {'success': False, 'error': str(e)}
    
    elapsed_time = time.time() - start_time
    successful_thumbnails = sum(1 for r in results.values() if r.get('success', False))
    print(f"⚡ OPTIMIZED parallel thumbnail generation completed in {elapsed_time:.1f}s")
    print(f"📊 Performance: {len(tasks)/elapsed_time:.1f} thumbnails/second")
    print(f"✅ Successfully created {successful_thumbnails}/{len(tasks)} thumbnails")
    
    return results

def cleanup_thumbnails(output_folder, keep_thumbnails=False):
    """
    Cleans up thumbnail files after LaTeX report generation.
    
    Args:
        output_folder: Path to the output folder containing thumbnails
        keep_thumbnails: If True, keep thumbnails; if False, delete them
    
    Returns:
        int: Number of thumbnails cleaned up
    """
    import glob
    
    if keep_thumbnails:
        return 0
    
    try:
        # Find all thumbnail files - use absolute path
        thumbnail_files = set()  # Use set to avoid duplicates
        
        # Primary search pattern
        thumbnail_pattern = os.path.join(os.path.abspath(output_folder), "thumbnail_*.png")
        found_files = glob.glob(thumbnail_pattern)
        thumbnail_files.update(found_files)
        
        # Also search recursively in subdirectories
        recursive_pattern = os.path.join(os.path.abspath(output_folder), "**", "thumbnail_*.png")
        recursive_thumbnails = glob.glob(recursive_pattern, recursive=True)
        thumbnail_files.update(recursive_thumbnails)
        
        # If no files found, try alternative search patterns
        if not thumbnail_files:
            alternative_patterns = [
                os.path.join(output_folder, "thumbnail_*.png"),
                os.path.join(output_folder, "*.png"),
                os.path.join(output_folder, "thumbnail*.png")
            ]
            
            for alt_pattern in alternative_patterns:
                alt_files = glob.glob(alt_pattern)
                if alt_files:
                    # Filter to only thumbnail files
                    filtered_files = [f for f in alt_files if 'thumbnail' in os.path.basename(f).lower()]
                    thumbnail_files.update(filtered_files)
                    if thumbnail_files:
                        break
            
            if not thumbnail_files:
                print("ℹ️  No thumbnail files found with any pattern")
                return 0
        
        # Convert set back to list for processing
        thumbnail_files = list(thumbnail_files)
        
        # Delete thumbnail files
        deleted_count = 0
        for thumbnail_file in thumbnail_files:
            try:
                print(f"🗑️  Attempting to delete: {thumbnail_file}")
                os.remove(thumbnail_file)
                deleted_count += 1
                print(f"✅ Successfully deleted: {os.path.basename(thumbnail_file)}")
            except Exception as e:
                print(f"⚠️  Warning: Could not delete {os.path.basename(thumbnail_file)}: {e}")
        
        print(f"🧹 Thumbnail cleanup completed: {deleted_count} files deleted")
        return deleted_count
        
    except Exception as e:
        print(f"Warning: Error during thumbnail cleanup: {e}")
        return 0

def create_fits_thumbnail_optimized(fits_file_path, output_path, size=(300, 300)):
    """
    OPTIMIZED thumbnail creation with black sky and bright objects.
    """
    try:
        # Import with error handling
        try:
            from astropy.io import fits
            import numpy as np
            from PIL import Image
        except ImportError as e:
            print(f"⚠️  Import error: {e}")
            return False
        
        # Open the FITS file with error handling
        try:
            with open_fits_for_data(fits_file_path) as hdul:
                data = hdul[0].data
                
                if data is None:
                    return False
                
                # Remove any NaN or infinite values
                data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
                
                # SIMPLE AND RELIABLE ALGORITHM: Black sky with bright objects
                # Step 1: Basic normalization to [0,1]
                data_min, data_max = np.nanmin(data), np.nanmax(data)
                if data_max > data_min:
                    data_norm = (data - data_min) / (data_max - data_min)
                else:
                    data_norm = np.zeros_like(data)
                
                # Step 2: Apply gentler stretch to preserve details in bright areas
                # Use a more moderate stretch that preserves highlights
                data_stretched = np.power(data_norm, 0.7)  # Gentler than square root
                
                # Step 3: Apply lighter gamma correction to preserve bright details
                gamma = 0.7  # Lighter gamma to preserve highlights
                data_gamma = np.power(data_stretched, gamma)
                
                # Step 4: Create darker sky while preserving bright object details
                # Find the sky level (lower percentile to be less aggressive)
                sky_level = np.percentile(data_gamma, 30)  # 30th percentile instead of median
                
                # Make sky darker while keeping bright objects
                data_final = np.where(data_gamma < sky_level, 
                                    data_gamma * 0.15,  # More aggressive darkening for center
                                    data_gamma)         # Keep bright objects
                
                # Step 4.5: Additional center darkening for overexposed areas
                # Create a mask for very bright areas (likely overexposed center)
                overexposed_mask = data_final > 0.8
                data_final = np.where(overexposed_mask, 
                                    data_final * 0.3,  # Significantly darken overexposed areas
                                    data_final)
                
                # Step 5: Final normalization to ensure good contrast
                final_min, final_max = np.percentile(data_final, [1, 99])
                if final_max > final_min:
                    data_final = np.clip((data_final - final_min) / (final_max - final_min), 0, 1)
                
                # Step 6: NO INVERSION - keep objects bright on dark background
                
                # Convert to 8-bit and create PIL image
                try:
                    data_8bit = (data_final * 255).astype(np.uint8)
                    img = Image.fromarray(data_8bit, mode='L')
                    
                    # Resize to thumbnail size
                    img_resized = img.resize(size, Image.Resampling.BILINEAR)
                    
                    # Save the thumbnail
                    img_resized.save(output_path, 'PNG', optimize=True)
                    
                    # Clean up memory
                    del data_8bit, img, img_resized, data_final, data_gamma, data_stretched, data_norm, data
                    
                    return True
                    
                except MemoryError as e:
                    print(f"⚠️  Memory error creating thumbnail: {e}")
                    return False
                except Exception as e:
                    print(f"⚠️  Error processing image: {e}")
                    return False
                    
        except Exception as e:
            print(f"⚠️  Error opening FITS file: {e}")
            return False
            
    except Exception as e:
        print(f"⚠️  Error creating thumbnail: {e}")
        return False

def create_fits_thumbnail_pil_robust(fits_file_path, output_path, size=(300, 300)):
    """
    Robust version of PIL thumbnail creation with better error handling and memory management.
    """
    try:
        # Import with error handling
        try:
            from astropy.io import fits
            from astropy.visualization import ZScaleInterval, AsinhStretch
            import numpy as np
            from PIL import Image
        except ImportError as e:
            print(f"⚠️  Import error: {e}")
            return False
        
        # Open the FITS file with error handling
        try:
            with open_fits_for_data(fits_file_path) as hdul:
                data = hdul[0].data
                
                if data is None:
                    return False
                
                # Remove any NaN or infinite values
                data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
                
                # SIMPLE AND RELIABLE ALGORITHM: Black sky with bright objects
                # Step 1: Basic normalization to [0,1]
                data_min, data_max = np.nanmin(data), np.nanmax(data)
                if data_max > data_min:
                    data_norm = (data - data_min) / (data_max - data_min)
                else:
                    data_norm = np.zeros_like(data)
                
                # Step 2: Apply gentler stretch to preserve details in bright areas
                # Use a more moderate stretch that preserves highlights
                data_stretched = np.power(data_norm, 0.7)  # Gentler than square root
                
                # Step 3: Apply lighter gamma correction to preserve bright details
                gamma = 0.7  # Lighter gamma to preserve highlights
                data_gamma = np.power(data_stretched, gamma)
                
                # Step 4: Create darker sky while preserving bright object details
                # Find the sky level (lower percentile to be less aggressive)
                sky_level = np.percentile(data_gamma, 30)  # 30th percentile instead of median
                
                # Make sky darker while keeping bright objects
                data_final = np.where(data_gamma < sky_level, 
                                    data_gamma * 0.15,  # More aggressive darkening for center
                                    data_gamma)         # Keep bright objects
                
                # Step 4.5: Additional center darkening for overexposed areas
                # Create a mask for very bright areas (likely overexposed center)
                overexposed_mask = data_final > 0.8
                data_final = np.where(overexposed_mask, 
                                    data_final * 0.3,  # Significantly darken overexposed areas
                                    data_final)
                
                # Step 5: Final normalization to ensure good contrast
                final_min, final_max = np.percentile(data_final, [1, 99])
                if final_max > final_min:
                    data_final = np.clip((data_final - final_min) / (final_max - final_min), 0, 1)
                
                # Step 6: NO INVERSION - keep objects bright on dark background
                
                # Convert to 8-bit and create PIL image with memory management
                try:
                    data_8bit = (data_final * 255).astype(np.uint8)
                    img = Image.fromarray(data_8bit, mode='L')
                    
                    # OPTIMIZATION: Use faster resampling for thumbnails
                    # LANCZOS is high quality but slower, BILINEAR is faster for thumbnails
                    img_resized = img.resize(size, Image.Resampling.BILINEAR)
                    
                    # Save the thumbnail
                    img_resized.save(output_path, 'PNG', optimize=True)
                    
                    # Clean up memory
                    del data_8bit, img, img_resized, data_final, data_gamma, data_stretched, data_norm, data
                    
                    return True
                    
                except MemoryError as e:
                    print(f"⚠️  Memory error creating thumbnail: {e}")
                    return False
                except Exception as e:
                    print(f"⚠️  Error processing image: {e}")
                    return False
                    
        except Exception as e:
            print(f"⚠️  Error opening FITS file: {e}")
            return False
            
    except Exception as e:
        print(f"⚠️  Error creating thumbnail with PIL: {e}")
        return False

def create_fits_thumbnail_pil(fits_file_path, output_path, size=(300, 300)):
    """
    Alternative thumbnail creation using PIL instead of matplotlib to avoid thread issues.
    """
    try:
        # Import with error handling
        try:
            from astropy.io import fits
            from astropy.visualization import ZScaleInterval, AsinhStretch
            import numpy as np
            from PIL import Image
        except ImportError as e:
            print(f"⚠️  Import error: {e}")
            return False
        
        # Open the FITS file (suppress warnings)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            try:
                hdul = fits.open(fits_file_path, output_verify='ignore')
            except TypeError:
                hdul = fits.open(fits_file_path)
        with hdul:
            data = hdul[0].data
            
            if data is None:
                return False
            
            # Remove any NaN or infinite values
            data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
            
            # Use ZScale normalization for better contrast
            zscale = ZScaleInterval()
            vmin, vmax = zscale.get_limits(data)
            
            # Normalize data to [0,1] range first
            data_normalized = (data - vmin) / (vmax - vmin)
            data_normalized = np.clip(data_normalized, 0, 1)
            
            # Apply Asinh stretch for better contrast in faint areas
            stretch = AsinhStretch()
            data_stretched = stretch(data_normalized)
            
            # EXTREME contrast enhancement for truly black sky background
            p0_1, p99_9 = np.percentile(data_stretched, [0.1, 99.9])
            data_enhanced = np.clip((data_stretched - p0_1) / (p99_9 - p0_1), 0, 1)
            
            # Apply EXTREME gamma correction for truly black background
            gamma = 0.1
            data_final = np.power(data_enhanced, gamma)
            
            # EXTREME sky darkening
            data_final = np.where(data_final < 0.8, data_final * 0.05, data_final)
            data_final = np.where(data_final < 0.5, data_final * 0.01, data_final)
            data_final = np.where(data_final < 0.2, 0.001, data_final)
            
            # Convert to 8-bit and create PIL image with memory management
            try:
                data_8bit = (data_final * 255).astype(np.uint8)
                img = Image.fromarray(data_8bit, mode='L')
                
                # Resize to thumbnail size
                img_resized = img.resize(size, Image.Resampling.LANCZOS)
                
                # Save the thumbnail
                img_resized.save(output_path, 'PNG', optimize=True)
                
                # Clean up memory
                del data_8bit, img, img_resized
                
                return True
                
            except MemoryError as e:
                print(f"⚠️  Memory error creating thumbnail: {e}")
                return False
            except Exception as e:
                print(f"⚠️  Error processing image: {e}")
                return False
            
    except Exception as e:
        print(f"⚠️  Error creating thumbnail with PIL: {e}")
        return False

def create_fits_thumbnail_safe(fits_file_path, output_path, size=(300, 300)):
    """
    Thread-safe version of create_fits_thumbnail that avoids matplotlib GUI issues.
    """
    try:
        if not MATPLOTLIB_AVAILABLE:
            return False
        
        # Force matplotlib to use non-GUI backend before any imports
        import os
        os.environ['MPLBACKEND'] = 'Agg'
        os.environ['MPLBACKEND'] = 'Agg'  # Double ensure
        os.environ['DISPLAY'] = ''  # Disable display
        
        # Disable tkinter completely
        import sys
        if 'tkinter' in sys.modules:
            del sys.modules['tkinter']
        
        import matplotlib
        matplotlib.use('Agg', force=True)
        
        import matplotlib.pyplot as plt
        from astropy.io import fits
        from astropy.visualization import ZScaleInterval, AsinhStretch
        import numpy as np
        
        # Ensure non-interactive mode and disable GUI
        plt.ioff()
        plt.switch_backend('Agg')
        
        # Open the FITS file (suppress warnings)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            try:
                hdul = fits.open(fits_file_path, output_verify='ignore')
            except TypeError:
                hdul = fits.open(fits_file_path)
        with hdul:
            data = hdul[0].data
            
            if data is None:
                return False
            
            # Remove any NaN or infinite values
            data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
            
            # Use ZScale normalization for better contrast
            zscale = ZScaleInterval()
            vmin, vmax = zscale.get_limits(data)
            
            # Normalize data to [0,1] range first
            data_normalized = (data - vmin) / (vmax - vmin)
            data_normalized = np.clip(data_normalized, 0, 1)
            
            # Apply Asinh stretch for better contrast in faint areas
            stretch = AsinhStretch()
            data_stretched = stretch(data_normalized)
            
            # EXTREME contrast enhancement for truly black sky background
            p0_1, p99_9 = np.percentile(data_stretched, [0.1, 99.9])
            data_enhanced = np.clip((data_stretched - p0_1) / (p99_9 - p0_1), 0, 1)
            
            # Apply EXTREME gamma correction for truly black background
            gamma = 0.1
            data_final = np.power(data_enhanced, gamma)
            
            # EXTREME sky darkening
            data_final = np.where(data_final < 0.8, data_final * 0.05, data_final)
            data_final = np.where(data_final < 0.5, data_final * 0.01, data_final)
            data_final = np.where(data_final < 0.2, 0.001, data_final)
            
            # Create the figure
            fig, ax = plt.subplots(figsize=(size[0]/100, size[1]/100), dpi=100)
            
            # Display the image
            im = ax.imshow(data_final, cmap='gray', origin='lower', 
                          vmin=0.1, vmax=1, interpolation='bilinear')
            
            ax.axis('off')
            plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
            
            # Save the thumbnail
            plt.savefig(output_path, dpi=100, bbox_inches='tight', 
                       facecolor='none', edgecolor='none', 
                       pad_inches=0, transparent=True)
            
            # Close figure and clear memory
            plt.close(fig)
            plt.clf()
            plt.cla()
            
            return True
            
    except Exception as e:
        print(f"⚠️  Error creating thumbnail: {e}")
        # Clean up matplotlib state
        try:
            plt.close('all')
            plt.clf()
            plt.cla()
        except Exception:
            pass
        return False

def create_fits_thumbnail(fits_file_path, output_path, size=(300, 300)):
    """
    Creates a thumbnail from a FITS file with enhanced contrast and black background.
    
    Args:
        fits_file_path: Path to the FITS file
        output_path: Output path for the thumbnail
        size: Thumbnail size (width, height)
    
    Returns:
        bool: True if thumbnail was created successfully
    """
    try:
        if not MATPLOTLIB_AVAILABLE:
            print("⚠️  Matplotlib required to create thumbnails")
            return False
        
        # Set matplotlib backend to non-GUI for thread safety
        import matplotlib
        matplotlib.use('Agg', force=True)  # Force non-GUI backend for thread safety
        
        import matplotlib.pyplot as plt
        import matplotlib.image as mpimg
        from astropy.io import fits
        from astropy.visualization import ZScaleInterval, AsinhStretch
        import numpy as np
        
        # Ensure matplotlib is in non-interactive mode
        plt.ioff()  # Turn off interactive mode
        
        # Open the FITS file
        with fits.open(fits_file_path) as hdul:
            data = hdul[0].data
            
            if data is None:
                print(f"⚠️  No data in {fits_file_path}")
                return False
            
            # Remove any NaN or infinite values
            data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
            
            # Use ZScale normalization for better contrast
            # This is similar to what DS9 uses for display
            zscale = ZScaleInterval()
            vmin, vmax = zscale.get_limits(data)
            
            # Normalize data to [0,1] range first
            data_normalized = (data - vmin) / (vmax - vmin)
            data_normalized = np.clip(data_normalized, 0, 1)
            
            # Apply Asinh stretch for better contrast in faint areas
            stretch = AsinhStretch()
            data_stretched = stretch(data_normalized)
            
            # EXTREME contrast enhancement for truly black sky background
            # Use very extreme percentiles to push sky to absolute black
            p0_1, p99_9 = np.percentile(data_stretched, [0.1, 99.9])
            data_enhanced = np.clip((data_stretched - p0_1) / (p99_9 - p0_1), 0, 1)
            
            # Apply EXTREME gamma correction for truly black background
            gamma = 0.1  # EXTREMELY low gamma for truly black sky
            data_final = np.power(data_enhanced, gamma)
            
            # EXTREME sky darkening: push low values to absolute black
            data_final = np.where(data_final < 0.8, data_final * 0.05, data_final)
            
            # Additional EXTREME black point adjustment - push everything below 0.5 to near zero
            data_final = np.where(data_final < 0.5, data_final * 0.01, data_final)
            
            # Final black point push - anything below 0.2 becomes essentially black
            data_final = np.where(data_final < 0.2, 0.001, data_final)
            
            # Create the figure without black background (transparent)
            fig, ax = plt.subplots(figsize=(size[0]/100, size[1]/100), dpi=100)
            
            # Display the image with EXTREME black background forcing
            # Set vmin to a much higher value to force sky to absolute black
            im = ax.imshow(data_final, cmap='gray', origin='lower', 
                          vmin=0.1, vmax=1, interpolation='bilinear')
            
            # No title, no axes
            ax.axis('off')
            
            # Remove any white space around the image
            plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
            
            # Save the thumbnail without background
            plt.savefig(output_path, dpi=100, bbox_inches='tight', 
                       facecolor='none', edgecolor='none', 
                       pad_inches=0, transparent=True)
            plt.close()
            
            return True
            
    except Exception as e:
        print(f"⚠️  Error creating thumbnail: {e}")
        # Ensure matplotlib is closed properly
        try:
            plt.close('all')
        except Exception:
            pass
        return False

def generate_latex_report(data_by_target, global_data, output_folder):
    """Generates LaTeX report"""
    if not MATPLOTLIB_AVAILABLE:
        if SYSTEM_LANGUAGE == 'fr':
            print("⚠️  La génération du rapport LaTeX nécessite matplotlib")
        else:
            print("⚠️  LaTeX report generation requires matplotlib")
        return
    
    if SYSTEM_LANGUAGE == 'fr':
        print(f"📄 Génération du rapport LaTeX...")
    else:
        print(f"📄 Generating LaTeX report...")
    import os
    import shutil
    report_path = os.path.join(output_folder, "astronomical_analysis_report.tex")
    if SYSTEM_LANGUAGE == 'fr':
        print(f"   📝 Écriture du fichier LaTeX: {os.path.basename(report_path)}")
    else:
        print(f"   📝 Writing LaTeX file: {os.path.basename(report_path)}")
    
    # Determine report language
    if SYSTEM_LANGUAGE == 'fr':
        report_title = "Rapport d'Analyse Astronomique"
        report_author = "Généré par le Programme d'Analyse Astronomique"
    else:
        report_title = "Astronomical Analysis Report"
        report_author = "Generated by Astronomical Analysis Program"
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("\\documentclass[12pt]{article}\n")
        f.write("\\usepackage[utf8]{inputenc}\n")
        f.write("\\usepackage[T1]{fontenc}\n")
        f.write("\\usepackage{geometry}\n")
        f.write("\\usepackage{graphicx}\n")
        f.write("\\usepackage{booktabs}\n")
        f.write("\\usepackage{longtable}\n")
        f.write("\\usepackage{amsmath}\n")
        f.write("\\usepackage{siunitx}\n")
        f.write("\\usepackage{needspace}\n")
        f.write("\\usepackage{float}\n")
        f.write("\\usepackage{tikz}\n")
        f.write("\\usepackage{xcolor}\n")
        # Language package
        if SYSTEM_LANGUAGE == 'fr':
            f.write("\\usepackage[french]{babel}\n")
        else:
            f.write("\\usepackage[english]{babel}\n")
        # hyperref should be loaded last (or near last) for proper bookmark generation
        f.write("\\usepackage[bookmarks=true,bookmarksopen=true,bookmarksopenlevel=2,colorlinks=true,linkcolor=blue,urlcolor=blue,citecolor=blue]{hyperref}\n")
        f.write("\\geometry{margin=2.5cm}\n")
        f.write(f"\\title{{{report_title}}}\n")
        f.write(f"\\author{{{report_author}}}\n")
        f.write("\\date{\\today}\n")
        f.write("\\begin{document}\n")
        # Ensure bookmarks are generated
        f.write("\\hypersetup{pdfstartview={FitH}}\n")
        
        # Draw the physics-accurate triple-atom logo (S II, Hα, O III) directly in TikZ above the title
        f.write("\\begin{center}\n")
        f.write("\\vspace*{-0.5cm}\n")
        f.write(r"""
\begin{tikzpicture}[scale=0.8]
% Pastel/soft hues closer to real emission colors
\definecolor{rouge}{RGB}{200,70,70}   % S II soft red
\definecolor{rougeH}{RGB}{210,60,60}  % H-alpha soft red
\definecolor{cyanO}{RGB}{80,170,185}  % O III soft cyan
\definecolor{bleu}{RGB}{0,0,255}
\definecolor{vert}{RGB}{0,128,0}
\definecolor{orange}{RGB}{255,165,0}
\definecolor{darkgreen}{RGB}{0,100,0}

% --- S II realistic (left): forbidden lines [S II] 6716/6731 Å ---
\begin{scope}[shift={(-6,0)}]
  \node at (0,3.0) {\textbf{\normalsize S II}};
  \node at (0,2.4) {\small Sulfur ion (S$^+$)};
  % Energy levels
  \draw[rouge,opacity=0.9,line width=1pt] (-2,1.4) -- (2,1.4); % ^2D5/2
  \node[anchor=west,rouge] at (2.1,1.4) {$\,\,{}^{2}\,\mathrm{D}_{5/2}$};
  \draw[rouge,opacity=0.9,line width=0.8pt] (-2,0.9) -- (2,0.9); % ^2D3/2
  \node[anchor=west,rouge] at (2.1,0.9) {$\,\,{}^{2}\,\mathrm{D}_{3/2}$};
  \draw[black,line width=0.8pt] (-2,-0.2) -- (2,-0.2); % ^4S3/2
  \node[anchor=west] at (2.1,-0.2) {$\,\,{}^{4}\,\mathrm{S}_{3/2}$};
  % Transitions and labels
  \draw[rouge,opacity=0.9,line width=1pt,->] (-0.45,1.4) -- (-0.45,-0.2);
  \draw[rouge,opacity=0.9,line width=0.6pt,dashed,->] (0.85,0.9) -- (0.85,-0.2);
  \node[rouge] at (-1.1,1.55) {\small\textbf{[S II]}};
  \draw[rouge,opacity=0.9,line width=0.6pt,->] (-0.45,-0.2) -- (1.8,-0.2);
  \node[rouge,fill=white,inner sep=1pt] at (1.0,-0.02) {\tiny 671.6 nm};
  \draw[rouge,opacity=0.9,line width=0.5pt,dashed,->] (0.85,-0.2) -- (1.8,-0.2);
  \node[rouge,fill=white,inner sep=1pt] at (1.05,-0.38) {\tiny 673.1 nm};
  \node at (0,-1.8) {\scriptsize $3\mathrm{s}^{2}3\mathrm{p}^{3}: {}^{2}\,\mathrm{D} \rightarrow {}^{4}\,\mathrm{S}$};
\end{scope}

% --- H\alpha (center): n=3 -> n=2, horizontal-level style ---
\begin{scope}
  \node at (0,3.0) {\textbf{\normalsize H$\alpha$}};
  \node at (0,2.4) {\small Hydrogen atom};
  \draw[rougeH,opacity=0.9,line width=1pt] (-2,1.2) -- (2,1.2);
  \node[anchor=west,rougeH] at (2.1,1.2) {$\,\,\mathit{n}=3$};
  \draw[black,line width=0.8pt] (-2,-0.2) -- (2,-0.2);
  \node[anchor=west] at (2.1,-0.2) {$\,\,\mathit{n}=2$};
  \draw[rougeH,opacity=0.9,line width=1pt,->] (-0.3,1.2) -- (-0.3,-0.2);
  \node[rougeH] at (-1.0,1.45) {\small\textbf{H$\alpha$}};
  \draw[rougeH,opacity=0.9,line width=0.8pt,->] (-0.3,-0.2) -- (1.8,-0.2);
  \node[rougeH,fill=white,inner sep=1pt] at (0.9,-0.05) {\tiny 656.3 nm};
  \node at (0,-1.8) {\scriptsize Balmer: $\mathit{n}=3 \to \mathit{n}=2$};
\end{scope}

% --- O III realistic (right): forbidden lines ---
\begin{scope}[shift={(6,0)}]
  \node at (0,3.0) {\textbf{\normalsize O III}};
  \node at (0,2.4) {\small Doubly ionized oxygen (O$^{2+}$)};
  \draw[cyanO,opacity=0.9,line width=1pt] (-2,1.2) -- (2,1.2);
  \node[anchor=west,cyanO] at (2.1,1.2) {$\,\,{}^{1}\,\mathrm{D}_{2}$};
  \draw[black,line width=0.8pt] (-2,-0.4) -- (2,-0.4);
  \node[anchor=west] at (2.1,-0.4) {$\,\,{}^{3}\,\mathrm{P}_{2}$};
  \draw[black,line width=0.6pt] (-2,-0.8) -- (2,-0.8);
  \node[anchor=west] at (2.1,-0.8) {$\,\,{}^{3}\,\mathrm{P}_{1}$};
  \draw[cyanO,opacity=0.9,line width=1pt,->] (-0.45,1.2) -- (-0.45,-0.4);
  \node[cyanO] at (1.25,1.45) {\small\textbf{[O III]}};
  \draw[cyanO,opacity=0.9,line width=0.6pt,->] (-0.45,-0.4) -- (1.8,-0.4);
  \node[cyanO,fill=white,inner sep=1pt] at (1.12,-0.18) {\tiny 500.7 nm};
  \draw[cyanO,opacity=0.9,line width=0.5pt,dashed,->] (0.45,1.2) -- (0.45,-0.8);
  \draw[cyanO,opacity=0.9,line width=0.5pt,dashed,->] (0.45,-0.8) -- (1.8,-0.8);
  \node[cyanO,fill=white,inner sep=1pt] at (1.12,-0.58) {\tiny 495.9 nm};
  \node at (0,-1.8) {\scriptsize $2\mathrm{p}^{2}: {}^{1}\,\mathrm{D}_{2} \rightarrow {}^{3}\,\mathrm{P}_{2}, {}^{3}\,\mathrm{P}_{1}$};
\end{scope}
\end{tikzpicture}
""")
        f.write("\\vspace{1.2cm}\n")
        f.write(f"\\Huge \\textbf{{{('Analyse Astronomique' if SYSTEM_LANGUAGE == 'fr' else 'Astronomical Analysis')}}}\n")
        f.write("\\vspace{1cm}\n")
        f.write("\\end{center}\n")
        
        # Add photon propagation equation
        f.write("\\vspace{0.5cm}\n")
        f.write("\\begin{center}\n")
        f.write(f"\\textbf{{{('Équation de propagation du photon dans le vide :' if SYSTEM_LANGUAGE == 'fr' else 'Photon Propagation Equation in Vacuum:')}}}\n")
        f.write("\\end{center}\n")
        f.write("\\vspace{0.3cm}\n")
        f.write("\\begin{center}\n")
        f.write("\\begin{equation}\n")
        f.write("\\nabla^2 \\vec{E} - \\frac{1}{c^2} \\frac{\\partial^2 \\vec{E}}{\\partial t^2} = \\nabla^2 \\vec{B} - \\frac{1}{c^2} \\frac{\\partial^2 \\vec{B}}{\\partial t^2}\n")
        f.write("\\end{equation}\n")
        f.write("\\end{center}\n")
        f.write("\\vspace{0.3cm}\n")
        f.write("\\begin{center}\n")
        f.write(f"{('où' if SYSTEM_LANGUAGE == 'fr' else 'where')} $c = 299\\,792\\,458$ m/s {('est la vitesse de la lumière dans le vide' if SYSTEM_LANGUAGE == 'fr' else 'is the speed of light in vacuum')}\n")
        f.write("\\end{center}\n")
        f.write("\\vspace{0.5cm}\n")
        
        # Global summary - bilingual
        _is_fr = (SYSTEM_LANGUAGE == 'fr')
        f.write(f"\\section{{{('Résumé Global' if _is_fr else 'Global Summary')}}}\n")
        used_equipment_count = len(sorted(set((global_data.get('used_instruments') or []) + (global_data.get('used_telescopes') or []))))
        f.write(f"{('Fichiers analysés' if _is_fr else 'Total files analyzed')}: {global_data['total_files']}\n\n")
        f.write(f"{('Cibles trouvées' if _is_fr else 'Targets found')}: {len(global_data['found_targets'])}\n\n")
        f.write(f"{('Équipements utilisés' if _is_fr else 'Equipment used')}: {used_equipment_count}\n\n")
        _total_obs_label = "Temps total d'observation" if _is_fr else "Total observation time"
        f.write(f"{_total_obs_label}: {format_time_with_details(global_data['total_time'])}\n\n")

        # Start Targets Summary on new page for better organization
        f.write("\\newpage\n")

        # Add targets summary table
        f.write(f"\\subsection{{{('Résumé des Cibles' if _is_fr else 'Targets Summary')}}}\n")
        # Use fixed column widths for proper alignment - ensure columns align correctly
        # Column widths: Target (40%), Time (15%), Telescope (30%), Files (15%)
        f.write("\\begin{longtable}{p{0.40\\textwidth} c p{0.30\\textwidth} c}\n")
        _tbl_hdr = f"{('Cible' if _is_fr else 'Target')} & {('Temps (heures)' if _is_fr else 'Time (hours)')} & {('Télescope' if _is_fr else 'Telescope')} & {('Fichiers' if _is_fr else 'Files')}"
        f.write("\\toprule\n")
        f.write(f"{_tbl_hdr} \\\\\n")
        f.write("\\midrule\n")
        f.write("\\endfirsthead\n")
        f.write("\\toprule\n")
        f.write(f"{_tbl_hdr} \\\\\n")
        f.write("\\midrule\n")
        f.write("\\endhead\n")
        f.write("\\bottomrule\n")
        f.write("\\endfoot\n")
        f.write("\\bottomrule\n")
        f.write("\\endlastfoot\n")
        
        # Configure longtable for proper page breaks and overflow handling
        f.write("\\setlength{\\LTcapwidth}{\\textwidth}\n")
        f.write("\\setlength{\\LTleft}{0pt}\n")
        f.write("\\setlength{\\LTright}{0pt}\n")
        f.write("\\renewcommand{\\arraystretch}{1.2}\n")
        f.write("\\setlength{\\LTpre}{\\bigskipamount}\n")
        f.write("\\setlength{\\LTpost}{\\bigskipamount}\n")
        f.write("\\setlength{\\LTchunksize}{100}\n")
        
        # Sort targets alphabetically
        target_summary = []
        sorted_targets = sorted(data_by_target.items(), key=lambda x: x[0].lower())
        for target, data in sorted_targets:
            if not data['files']:
                continue
            
            # Skip calibration targets
            if is_calibration_target(target):
                continue
            
            # Use files_by_date to calculate total time (same as detailed section)
            files_by_date = group_files_by_date(data)
            total_time = 0
            for date_data in files_by_date.values():
                total_time += date_data['total_time']
            total_time_hours = total_time / 3600  # Convert to hours
            
            # Get telescope (use first one if multiple)
            telescope = list(data['telescopes'])[0] if data['telescopes'] else 'Unknown'
            
            total_files = len(data['files'])
            
            target_summary.append((target, total_time_hours, telescope, total_files))
        
        # Sort target_summary alphabetically by target name (case-insensitive, improved for astronomical objects)
        target_summary.sort(key=lambda x: get_astronomical_sort_key(x[0]))
        
        # Add rows to table
        for target, time_hours, telescope, files in target_summary:
            f.write(f"{format_target_name_for_latex(target)} & {time_hours:.1f} & {escape_latex(telescope)} & {files} \\\\\n")
        
        f.write("\\end{longtable}\n\n")
        
        # Target details - sort targets alphabetically
        target_count = 0
        
        # Generate thumbnails only if user requested them
        thumbnail_results = {}
        thumbnail_targets = []
        
        if GENERATE_THUMBNAILS:
            # Count targets that will have thumbnails
            sorted_targets = sorted(data_by_target.items(), key=lambda x: get_astronomical_sort_key(x[0]))
            for target, data in sorted_targets:
                if not data['files']:
                    continue
                # Skip calibration targets
                if is_calibration_target(target):
                    continue
                thumbnail_targets.append((target, data))
            
            print(f"\n🖼️  Generating thumbnails for {len(thumbnail_targets)} targets...")
            # Generate thumbnails in parallel with improved stability
            thumbnail_results = generate_thumbnails_parallel_robust(data_by_target, output_folder)
        else:
            print(f"\n⏭️  Skipping thumbnail generation (user choice)")
        
        sorted_targets = sorted(data_by_target.items(), key=lambda x: get_astronomical_sort_key(x[0]))
        for target, data in sorted_targets:
            if not data['files']:
                continue
            
            # Skip calibration targets
            if is_calibration_target(target):
                continue
            
            # Add page break before each target only if thumbnails are generated
            # (thumbnails need space, but text-only sections can be more compact)
            if target_count > 0 and GENERATE_THUMBNAILS:
                f.write("\\newpage\n")
            
            latex_name = format_target_name_for_latex(target)
            # Use texorpdfstring so hyperref gets a clean bookmark string
            f.write(f"\\section{{\\texorpdfstring{{{latex_name}}}{{{target}}}}}\n")
            target_count += 1
            
            # SIMBAD object info (type, distance, redshift, common name) when available
            simbad_info = data.get('simbad_info') or {}
            if simbad_info:
                parts = []
                _is_fr = (SYSTEM_LANGUAGE == 'fr')
                if simbad_info.get('otype'):
                    type_label = format_simbad_otype(simbad_info['otype'])
                    parts.append(f"Type: {escape_latex(type_label)}")
                if simbad_info.get('distance_pc') is not None and simbad_info['distance_pc'] > 0:
                    d = simbad_info['distance_pc']
                    _dist_label = "Distance" if not _is_fr else "Distance"
                    if d >= 1e6:
                        parts.append(f"{_dist_label}: {d/1e6:.2f} Mpc")
                    elif d >= 1000:
                        parts.append(f"{_dist_label}: {d/1000:.2f} kpc")
                    else:
                        parts.append(f"{_dist_label}: {d:.1f} pc")
                    if simbad_info.get('distance_ly') is not None and simbad_info['distance_ly'] > 0:
                        dly = simbad_info['distance_ly']
                        _ly_unit = "a.l." if _is_fr else "ly"
                        if dly >= 1e6:
                            parts.append(f"{dly/1e6:.2f} M {_ly_unit}")
                        elif dly >= 1000:
                            parts.append(f"{dly/1000:.1f} k {_ly_unit}")
                        else:
                            parts.append(f"{dly:.1f} {_ly_unit}")
                if simbad_info.get('redshift') is not None:
                    z = simbad_info['redshift']
                    if abs(z) < 0.01:
                        parts.append(f"z = {z:.4f}")
                    else:
                        parts.append(f"z = {z:.3f}")
                if simbad_info.get('common_name'):
                    _name_label = "Nom" if _is_fr else "Name"
                    parts.append(f"{_name_label}: {escape_latex(simbad_info['common_name'])}")
                if parts:
                    info_line = " | ".join(parts)
                    # Add SIMBAD link if main_id is available
                    if simbad_info.get('main_id'):
                        import urllib.parse
                        # URL encode the identifier properly
                        main_id_url = urllib.parse.quote(simbad_info['main_id'], safe='')
                        simbad_url = f"https://simbad.cds.unistra.fr/simbad/sim-id?Ident={main_id_url}"
                        # Escape URL for LaTeX: % and # are TeX specials that must be escaped
                        # Do NOT escape _ inside \href{} - hyperref handles it
                        simbad_url_esc = simbad_url.replace('\\', '/').replace('%', '\\%').replace('#', '\\#')
                        f.write(f"\\textit{{{info_line} | \\href{{{simbad_url_esc}}}{{SIMBAD}}}}\n\n")
                    else:
                        f.write(f"\\textit{{{info_line}}}\n\n")
            
            # Use pre-generated thumbnail if available and thumbnails were requested
            if GENERATE_THUMBNAILS and target in thumbnail_results and thumbnail_results[target]['success']:
                result = thumbnail_results[target]
                best_fits_file = result['fits_file']
                thumbnail_filename = result['thumbnail_filename']
                
                print(f"📸 Using pre-generated thumbnail for {target}... ({target_count}/{len(thumbnail_targets)})")
                exposure_time_display = best_fits_file['info'].get('exposure_time') or 0
                print(f"   🎯 Selected: {best_fits_file['info']['filter']} filter, {exposure_time_display:.1f}s exposure")
                print(f"   📁 Source: {os.path.basename(best_fits_file['path'])}")
                
                f.write("\\begin{figure}[H]\n")
                f.write("\\centering\n")
                f.write(f"\\includegraphics[width=0.6\\textwidth]{{{thumbnail_filename}}}\n")
                exposure_time_display = best_fits_file['info'].get('exposure_time') or 0
                filter_display = format_filter_name_latex(best_fits_file['info']['filter'])
                if _is_fr:
                    f.write(f"\\caption{{Aperçu de \\texorpdfstring{{{escape_latex(target)}}}{{{target}}} - Filtre : \\texorpdfstring{{{filter_display}}}{{{best_fits_file['info']['filter']}}}, Temps d'exposition : {exposure_time_display:.1f}s}}\n")
                else:
                    f.write(f"\\caption{{Thumbnail of \\texorpdfstring{{{escape_latex(target)}}}{{{target}}} - Filter: \\texorpdfstring{{{filter_display}}}{{{best_fits_file['info']['filter']}}}, Exposure time: {exposure_time_display:.1f}s}}\n")
                f.write("\\end{figure}\n\n")
            else:
                print(f"   ⚠️  No thumbnail available for {target}")
            
            # Global summary for this target
            total_files = len(data['files'])
            files_by_date = group_files_by_date(data)
            num_nights = len(files_by_date)
            
            # Calculate total time from files_by_date to avoid duplication
            total_time = 0
            for date_data in files_by_date.values():
                total_time += date_data['total_time']
            
            f.write(f"\\subsection{{{('Résumé Global' if _is_fr else 'Global Summary')}}}\n")
            f.write(f"{('Fichiers' if _is_fr else 'Files')}: {total_files}\n\n")
            f.write(f"{('Temps total' if _is_fr else 'Total time')}: {format_time_with_details(total_time)}\n\n")
            _nights_label = "Nuits d'observation" if _is_fr else "Observation nights"
            f.write(f"{_nights_label}: {num_nights}\n\n")
            equipment_global = sorted(set((data.get('telescopes') or []) + (data.get('instruments') or [])))
            equipment_global = [x for x in equipment_global if x and str(x).strip() and str(x).upper() != 'UNKNOWN']
            f.write(f"{('Équipement' if _is_fr else 'Equipment')}: {', '.join(equipment_global) if equipment_global else '-'}\n\n")
            
            # Add space and ensure proper page break if needed
            f.write("\\vspace{0.5cm}\n")
            f.write("\\needspace{5cm}\n")  # Ensure enough space for next section
            
            # If content is too long, force a page break
            if total_files > 100:  # For targets with many files
                f.write("\\clearpage\n")  # Force page break for very long content
            
            # Check if this is a mosaic target
            if 'panels' in data and data['panels']:
                f.write(f"\\subsection{{{('Panneaux Mosaïque' if _is_fr else 'Mosaic Panels')}}}\n")
                f.write(f"{('Cette cible est composée de plusieurs panneaux mosaïque' if _is_fr else 'This target is composed of multiple mosaic panels')}:\n\n")
                f.write("\\begin{itemize}\n")
                for panel_num, panel_info in sorted(data['panels'].items(), key=lambda x: int(x[0])):
                    panel_name = panel_info['original_name']
                    panel_files = len(panel_info['files'])
                    panel_time = panel_info['total_time']
                    if _is_fr:
                        f.write(f"\\item Panneau {panel_num}: {escape_latex(panel_name)} ({panel_files} fichiers, {format_time_with_details(panel_time)})\n")
                    else:
                        f.write(f"\\item Panel {panel_num}: {escape_latex(panel_name)} ({panel_files} files, {format_time_with_details(panel_time)})\n")
                f.write("\\end{itemize}\n\n")
            
            # Group files by equipment (telescope = instrument = lunette: one concept)
            equipment_groups = {}
            files_by_date = group_files_by_date(data)
            
            for file_data in data['files']:
                file_info = file_data.get('info')
                if not file_info:
                    continue
                telescope = (file_info.get('info') or {}).get('telescope', 'Unknown')
                instrument = (file_info.get('info') or {}).get('instrument', 'Unknown')
                equipment_name = get_equipment_name(telescope, instrument)
                if equipment_name == 'Unknown':
                    continue
                
                if equipment_name not in equipment_groups:
                    equipment_groups[equipment_name] = {
                        'telescope': telescope,
                        'instrument': instrument,
                        'time_by_filter': {},
                        'total_time': 0
                    }
                
                filter_name = file_info.get('filter')
                exposure_time = file_info.get('exposure_time') or 0
                
                if filter_name not in equipment_groups[equipment_name]['time_by_filter']:
                    equipment_groups[equipment_name]['time_by_filter'][filter_name] = []
                
                equipment_groups[equipment_name]['time_by_filter'][filter_name].append(exposure_time)
                equipment_groups[equipment_name]['total_time'] += exposure_time
            
            if not equipment_groups:
                f.write(f"\\subsection{{{('Équipement' if _is_fr else 'Equipment')}}}\n")
                _no_equip = "Aucune donnée d'équipement pour cette cible." if _is_fr else "No equipment data found for this target."
                f.write(f"{_no_equip}\n\n")
            else:
                f.write("\\needspace{8cm}\n")
                for equipment_name, group_data in equipment_groups.items():
                    telescope = group_data['telescope']
                    instrument = group_data['instrument']
                    group_time = group_data['total_time']
                    group_time_by_filter = group_data['time_by_filter']
                    
                    # Calculate total files from time_by_filter
                    total_group_files = sum(len(time_list) for time_list in group_time_by_filter.values())
                    
                    f.write(f"\\subsection{{\\texorpdfstring{{{escape_latex(equipment_name)}}}{{{equipment_name}}}}}\n")
                    f.write(f"{('Fichiers' if _is_fr else 'Files')}: {total_group_files}\n\n")
                    f.write(f"{('Temps total' if _is_fr else 'Total time')}: {format_time(group_time)}\n\n")


                    # Filter details for this telescope/instrument combination
                    f.write(f"\\subsubsection{{{('Distribution des Filtres' if _is_fr else 'Filter Distribution')}}}\n")
                    f.write("\\begin{tabular}{lccc}\n")
                    f.write("\\toprule\n")
                    f.write(f"{('Filtre' if _is_fr else 'Filter')} & Images & {('Temps Total' if _is_fr else 'Total Time')} & {('Temps Moyen' if _is_fr else 'Average Time')} \\\\\n")
                    f.write("\\midrule\n")
                    
                    # Define the specific order for filters
                    filter_order = ['L', 'R', 'G', 'B', 'SII', 'Ha', 'OIII']
                    
                    # First, add filters in the specified order
                    for filter_name in filter_order:
                        if filter_name in group_time_by_filter:
                            time_list = group_time_by_filter[filter_name]
                            total_time = sum(time_list)
                            nb_images = len(time_list)
                            average_time = total_time / nb_images
                            
                            f.write(f"{convert_filter_name_to_greek_latex(filter_name)} & {nb_images} & {format_time_hours_minutes(total_time)} & {format_time_hours_minutes(average_time)} \\\\\n")
                    
                    # Then add any remaining filters not in the specified order
                    for filter_name in sorted(group_time_by_filter.keys()):
                        if filter_name not in filter_order:
                            time_list = group_time_by_filter[filter_name]
                            total_time = sum(time_list)
                            nb_images = len(time_list)
                            average_time = total_time / nb_images
                            
                            f.write(f"{convert_filter_name_to_greek_latex(filter_name)} & {nb_images} & {format_time_hours_minutes(total_time)} & {format_time_hours_minutes(average_time)} \\\\\n")
                    
                    f.write("\\bottomrule\n")
                    f.write("\\end{tabular}\n\n")
                    
                    # Night-by-night observation details for this telescope/instrument
                    f.write(f"\\subsubsection{{{('Détails des Observations par Nuit' if _is_fr else 'Observation Details by Night')}}}\n")
                    f.write("\\needspace{3cm}\n")
                    
                    # Create telescope-specific files_by_date by directly processing files
                    # This ensures we only include filters that actually belong to this telescope/instrument
                    telescope_files_by_date = {}
                    
                    # Process files directly to build telescope-specific data by date
                    # Only process LIGHT files that match this telescope/instrument
                    for file_data in data['files']:
                        file_info = file_data.get('info')
                        if not file_info:
                            continue
                        
                        # Skip non-LIGHT files (calibration files)
                        if file_info.get('type') != 'LIGHT':
                            continue
                        
                        # Get telescope and instrument info with normalization
                        if 'info' not in file_info:
                            continue
                        
                        file_telescope = file_info['info'].get('telescope') or 'Unknown'
                        file_instrument = file_info['info'].get('instrument') or 'Unknown'
                        file_equipment = get_equipment_name(file_telescope, file_instrument)
                        if str(file_equipment).strip().upper() != str(equipment_name).strip().upper():
                            continue
                        
                        # Get required fields
                        file_date = file_info.get('observation_date')
                        file_filter = file_info.get('filter')
                        
                        # Skip if essential information is missing or invalid
                        if (not file_date or not file_filter or 
                            str(file_date).strip() == '' or str(file_filter).strip() == '' or
                            str(file_date).strip().upper() == 'UNKNOWN' or str(file_filter).strip().upper() == 'UNKNOWN'):
                            continue
                        
                        # Normalize date to standard format 'YYYY-MM-DD night'
                        file_date = normalize_night_date(file_date)
                        if not file_date:
                            continue  # Skip if date normalization failed
                        
                        # Normalize filter string
                        file_filter = str(file_filter).strip()
                        
                        # Initialize date data if not exists
                        if file_date not in telescope_files_by_date:
                            telescope_files_by_date[file_date] = {
                                'time_by_filter': {},
                                'total_time': 0,
                                'exposure_details': {}
                            }
                        
                        # Get exposure time
                        exposure_time = file_info.get('exposure_time')
                        if exposure_time is None:
                            exposure_time = 0
                        else:
                            try:
                                exposure_time = float(exposure_time)
                            except (ValueError, TypeError):
                                exposure_time = 0
                        
                        # Add to time_by_filter
                        if file_filter not in telescope_files_by_date[file_date]['time_by_filter']:
                            telescope_files_by_date[file_date]['time_by_filter'][file_filter] = []
                        telescope_files_by_date[file_date]['time_by_filter'][file_filter].append(exposure_time)
                        
                        # Add to total time
                        telescope_files_by_date[file_date]['total_time'] += exposure_time
                        
                        # Add to exposure details
                        if file_filter not in telescope_files_by_date[file_date]['exposure_details']:
                            telescope_files_by_date[file_date]['exposure_details'][file_filter] = {}
                        if exposure_time not in telescope_files_by_date[file_date]['exposure_details'][file_filter]:
                            telescope_files_by_date[file_date]['exposure_details'][file_filter][exposure_time] = 0
                        telescope_files_by_date[file_date]['exposure_details'][file_filter][exposure_time] += 1
                    
                    # Add total_files and filters fields to each date (same logic as original)
                    for date_str, date_data in telescope_files_by_date.items():
                        # Calculate total files from time_by_filter
                        date_data['total_files'] = sum(len(time_list) for time_list in date_data['time_by_filter'].values())
                        
                        # Calculate filter statistics from time_by_filter
                        date_data['filters'] = {}
                        for filter_name, time_list in date_data['time_by_filter'].items():
                            total_time = sum(time_list)
                            count = len(time_list)
                            date_data['filters'][filter_name] = {
                                'count': count,
                                'time': total_time
                            }
                    
                    # Use the telescope-specific files_by_date
                    files_by_date = telescope_files_by_date
                    
                    # Sort dates chronologically
                    sorted_dates = sorted(files_by_date.keys())
                    
                    if len(sorted_dates) == 1:
                        # Only one date, show with the date
                        date_str = sorted_dates[0]
                        night_data = files_by_date[date_str]
                        display_date = format_night_display(date_str)
                        f.write(f"\\paragraph{{{display_date}}}\n")
                        _tot_obs_lbl = "Temps total d'observation" if _is_fr else "Total observation time"
                        _num_img_lbl = "Nombre d'images" if _is_fr else "Number of images"
                        f.write(f"{_tot_obs_lbl}: {format_time(night_data['total_time'])}\n")
                        f.write(f"{_num_img_lbl}: {night_data['total_files']}\n\n")

                        # Filter breakdown for all observations
                        if night_data['filters']:
                            _flt_hdr = "Filtre & Images & Temps Total & Temps Moyen" if _is_fr else "Filter & Images & Total Time & Average Time"
                            f.write("\n\\begin{tabular}{lccc}\n")
                            f.write("\\toprule\n")
                            f.write(f"{_flt_hdr} \\\\\n")
                            f.write("\\midrule\n")
                            
                            # Use the same filter order
                            filter_order = ['L', 'R', 'G', 'B', 'SII', 'Ha', 'OIII']
                            
                            # First, add filters in the specified order
                            for filter_name in filter_order:
                                if filter_name in night_data['filters']:
                                    stats = night_data['filters'][filter_name]
                                    avg_time = stats['time'] / stats['count'] if stats['count'] > 0 else 0
                                    f.write(f"{convert_filter_name_to_greek_latex(filter_name)} & {stats['count']} & {format_time(stats['time'])} & {format_time(avg_time)} \\\\\n")
                            
                            # Then add any remaining filters not in the specified order
                            for filter_name in sorted(night_data['filters'].keys()):
                                if filter_name not in filter_order:
                                    stats = night_data['filters'][filter_name]
                                    avg_time = stats['time'] / stats['count'] if stats['count'] > 0 else 0
                                    f.write(f"{convert_filter_name_to_greek_latex(filter_name)} & {stats['count']} & {format_time(stats['time'])} & {format_time(avg_time)} \\\\\n")
                            
                            f.write("\\bottomrule\n")
                            f.write("\\end{tabular}\n\n")
                            
                            # Add detailed exposure breakdown for this single night - ALWAYS generate if filters exist
                            if night_data['filters']:
                                # Build exposure_details from time_by_filter if not available or incomplete
                                exposure_details_data = {}
                                if 'exposure_details' in night_data and night_data['exposure_details']:
                                    exposure_details_data = night_data['exposure_details'].copy()
                                
                                # Ensure all filters have exposure details by building from time_by_filter
                                if 'time_by_filter' in night_data:
                                    for filter_name, time_list in night_data['time_by_filter'].items():
                                        if filter_name not in exposure_details_data or not exposure_details_data[filter_name]:
                                            # Build exposure_details from time_list
                                            exposure_details_data[filter_name] = {}
                                            for exp_time in time_list:
                                                if exp_time not in exposure_details_data[filter_name]:
                                                    exposure_details_data[filter_name][exp_time] = 0
                                                exposure_details_data[filter_name][exp_time] += 1
                                
                                # Collect all unique exposure times from all filters
                                all_exposure_times = set()
                                for filter_details in exposure_details_data.values():
                                    if filter_details:
                                        all_exposure_times.update(filter_details.keys())
                                
                                # Also collect from time_by_filter as fallback
                                if 'time_by_filter' in night_data:
                                    for time_list in night_data['time_by_filter'].values():
                                        all_exposure_times.update(time_list)
                                
                                if all_exposure_times:
                                    sorted_exposure_times = sorted(all_exposure_times)
                                    
                                    f.write("\\needspace{3cm}\n")
                                    f.write(f"\\textbf{{{_('detailed_exposure_times')}:}}\n\n")

                                    # Create a compact horizontal table
                                    f.write("\\begin{table}[H]\n")
                                    f.write("\\small\n")
                                    f.write("\\begin{tabular}{l|")

                                    # Add column headers for each exposure time
                                    for _exp in sorted_exposure_times:
                                        f.write("c|")
                                    f.write("}\n")
                                    f.write("\\toprule\n")

                                    # Header row with exposure times
                                    f.write("Filtre" if _is_fr else "Filter")
                                    for exp_time in sorted_exposure_times:
                                        f.write(f" & {exp_time:.0f}s")
                                    f.write(" \\\\\n")
                                    f.write("\\midrule\n")

                                    # Use the same filter order
                                    filter_order = ['L', 'R', 'G', 'B', 'SII', 'Ha', 'OIII']

                                    # First, add filters in the specified order
                                    for filter_name in filter_order:
                                        if filter_name in night_data['filters']:
                                            f.write(convert_filter_name_to_greek_latex(filter_name))
                                            # Get counts from exposure_details_data or count from time_list
                                            if filter_name in exposure_details_data and exposure_details_data[filter_name]:
                                                filter_details = exposure_details_data[filter_name]
                                                for exp_time in sorted_exposure_times:
                                                    count = filter_details.get(exp_time, 0)
                                                    f.write(f" & {count if count > 0 else '-'}")
                                            elif filter_name in night_data.get('time_by_filter', {}):
                                                # Count occurrences in time_list
                                                time_list = night_data['time_by_filter'][filter_name]
                                                for exp_time in sorted_exposure_times:
                                                    count = time_list.count(exp_time)
                                                    f.write(f" & {count if count > 0 else '-'}")
                                            else:
                                                # No data available
                                                for exp_time in sorted_exposure_times:
                                                    f.write(" & -")
                                            f.write(" \\\\\n")
                                    
                                    # Then add any remaining filters not in the specified order
                                    for filter_name in sorted(night_data['filters'].keys()):
                                        if filter_name not in filter_order:
                                            f.write(convert_filter_name_to_greek_latex(filter_name))
                                            # Get counts from exposure_details_data or count from time_list
                                            if filter_name in exposure_details_data and exposure_details_data[filter_name]:
                                                filter_details = exposure_details_data[filter_name]
                                                for exp_time in sorted_exposure_times:
                                                    count = filter_details.get(exp_time, 0)
                                                    f.write(f" & {count if count > 0 else '-'}")
                                            elif filter_name in night_data.get('time_by_filter', {}):
                                                # Count occurrences in time_list
                                                time_list = night_data['time_by_filter'][filter_name]
                                                for exp_time in sorted_exposure_times:
                                                    count = time_list.count(exp_time)
                                                    f.write(f" & {count if count > 0 else '-'}")
                                            else:
                                                # No data available
                                                for exp_time in sorted_exposure_times:
                                                    f.write(" & -")
                                            f.write(" \\\\\n")
                                    
                                    f.write("\\bottomrule\n")
                                    f.write("\\end{tabular}\n")
                                    f.write("\\end{table}\n\n")
                        else:
                            if SYSTEM_LANGUAGE == 'fr':
                                f.write(f"{_('no_filter_info')}.\n\n")
                            else:
                                f.write(f"{_('no_filter_info')}.\n\n")
                    else:
                        # Multiple dates, show each night separately
                        for date_str in sorted_dates:
                            night_data = files_by_date[date_str]
                            # Format night display with readable format
                            display_date = format_night_display(date_str)
                            
                            # Check if we need a page break (only if not enough space)
                            # Reserve space for the entire night section to avoid page breaks
                            f.write("\\needspace{8cm}\n")
                            f.write(f"\\paragraph{{{display_date}}}\n")
                            _tot_obs_lbl2 = "Temps total d'observation" if _is_fr else "Total observation time"
                            _num_img_lbl2 = "Nombre d'images" if _is_fr else "Number of images"
                            f.write(f"{_tot_obs_lbl2}: {format_time(night_data['total_time'])}\n")
                            f.write(f"{_num_img_lbl2}: {night_data['total_files']}\n\n")


                            # Filter breakdown for this night
                            if night_data['filters']:
                                _flt_hdr2 = "Filtre & Images & Temps Total & Temps Moyen" if _is_fr else "Filter & Images & Total Time & Average Time"
                                f.write("\\begin{table}[H]\n")
                                f.write("\\begin{tabular}{lccc}\n")
                                f.write("\\toprule\n")
                                f.write(f"{_flt_hdr2} \\\\\n")
                                f.write("\\midrule\n")
                                
                                # Use the same filter order
                                filter_order = ['L', 'R', 'G', 'B', 'SII', 'Ha', 'OIII']
                                
                                # First, add filters in the specified order
                                for filter_name in filter_order:
                                    if filter_name in night_data['filters']:
                                        stats = night_data['filters'][filter_name]
                                        avg_time = stats['time'] / stats['count'] if stats['count'] > 0 else 0
                                        f.write(f"{convert_filter_name_to_greek_latex(filter_name)} & {stats['count']} & {format_time(stats['time'])} & {format_time(avg_time)} \\\\\n")
                                
                                # Then add any remaining filters not in the specified order
                                for filter_name in sorted(night_data['filters'].keys()):
                                    if filter_name not in filter_order:
                                        stats = night_data['filters'][filter_name]
                                        avg_time = stats['time'] / stats['count'] if stats['count'] > 0 else 0
                                        f.write(f"{convert_filter_name_to_greek_latex(filter_name)} & {stats['count']} & {format_time(stats['time'])} & {format_time(avg_time)} \\\\\n")
                                
                                f.write("\\bottomrule\n")
                                f.write("\\end{tabular}\n")
                                f.write("\\end{table}\n\n")
                                
                                # Add detailed exposure breakdown for this night - ALWAYS generate if filters exist
                                if night_data['filters']:
                                    # Build exposure_details from time_by_filter if not available or incomplete
                                    exposure_details_data = {}
                                    if 'exposure_details' in night_data and night_data['exposure_details']:
                                        exposure_details_data = night_data['exposure_details'].copy()
                                    
                                    # Ensure all filters have exposure details by building from time_by_filter
                                    if 'time_by_filter' in night_data:
                                        for filter_name, time_list in night_data['time_by_filter'].items():
                                            if filter_name not in exposure_details_data or not exposure_details_data[filter_name]:
                                                # Build exposure_details from time_list
                                                exposure_details_data[filter_name] = {}
                                                for exp_time in time_list:
                                                    if exp_time not in exposure_details_data[filter_name]:
                                                        exposure_details_data[filter_name][exp_time] = 0
                                                    exposure_details_data[filter_name][exp_time] += 1
                                    
                                    # Collect all unique exposure times from all filters
                                    all_exposure_times = set()
                                    for filter_details in exposure_details_data.values():
                                        if filter_details:
                                            all_exposure_times.update(filter_details.keys())
                                    
                                    # Also collect from time_by_filter as fallback
                                    if 'time_by_filter' in night_data:
                                        for time_list in night_data['time_by_filter'].values():
                                            all_exposure_times.update(time_list)
                                    
                                    if all_exposure_times:
                                        sorted_exposure_times = sorted(all_exposure_times)
                                        
                                        f.write("\\needspace{3cm}\n")
                                        f.write(f"\\textbf{{{_('detailed_exposure_times')}:}}\n\n")

                                        # Create a compact horizontal table
                                        f.write("\\begin{table}[H]\n")
                                        f.write("\\small\n")
                                        f.write("\\begin{tabular}{l|")

                                        # Add column headers for each exposure time
                                        for _exp in sorted_exposure_times:
                                            f.write("c|")
                                        f.write("}\n")
                                        f.write("\\toprule\n")

                                        # Header row with exposure times
                                        f.write("Filtre" if _is_fr else "Filter")
                                        for exp_time in sorted_exposure_times:
                                            f.write(f" & {exp_time:.0f}s")
                                        f.write(" \\\\\n")
                                        f.write("\\midrule\n")
                                        
                                        # Use the same filter order
                                        filter_order = ['L', 'R', 'G', 'B', 'SII', 'Ha', 'OIII']
                                        
                                        # First, add filters in the specified order
                                        for filter_name in filter_order:
                                            if filter_name in night_data['filters']:
                                                f.write(convert_filter_name_to_greek_latex(filter_name))
                                                # Get counts from exposure_details_data or count from time_list
                                                if filter_name in exposure_details_data and exposure_details_data[filter_name]:
                                                    filter_details = exposure_details_data[filter_name]
                                                    for exp_time in sorted_exposure_times:
                                                        count = filter_details.get(exp_time, 0)
                                                        f.write(f" & {count if count > 0 else '-'}")
                                                elif filter_name in night_data.get('time_by_filter', {}):
                                                    # Count occurrences in time_list
                                                    time_list = night_data['time_by_filter'][filter_name]
                                                    for exp_time in sorted_exposure_times:
                                                        count = time_list.count(exp_time)
                                                        f.write(f" & {count if count > 0 else '-'}")
                                                else:
                                                    # No data available
                                                    for exp_time in sorted_exposure_times:
                                                        f.write(" & -")
                                                f.write(" \\\\\n")
                                        
                                        # Then add any remaining filters not in the specified order
                                        for filter_name in sorted(night_data['filters'].keys()):
                                            if filter_name not in filter_order:
                                                f.write(convert_filter_name_to_greek_latex(filter_name))
                                                # Get counts from exposure_details_data or count from time_list
                                                if filter_name in exposure_details_data and exposure_details_data[filter_name]:
                                                    filter_details = exposure_details_data[filter_name]
                                                    for exp_time in sorted_exposure_times:
                                                        count = filter_details.get(exp_time, 0)
                                                        f.write(f" & {count if count > 0 else '-'}")
                                                elif filter_name in night_data.get('time_by_filter', {}):
                                                    # Count occurrences in time_list
                                                    time_list = night_data['time_by_filter'][filter_name]
                                                    for exp_time in sorted_exposure_times:
                                                        count = time_list.count(exp_time)
                                                        f.write(f" & {count if count > 0 else '-'}")
                                                else:
                                                    # No data available
                                                    for exp_time in sorted_exposure_times:
                                                        f.write(" & -")
                                                f.write(" \\\\\n")
                                        
                                        f.write("\\bottomrule\n")
                                        f.write("\\end{tabular}\n")
                                        f.write("\\end{table}\n\n")
                            else:
                                if SYSTEM_LANGUAGE == 'fr':
                                    f.write(f"{_('no_filter_info_night')}.\n\n")
                                else:
                                    f.write(f"{_('no_filter_info_night')}.\n\n")
            
            
        
        f.write("\\end{document}\n")
    
    print(f"\n✅ Thumbnail generation completed!")
    print(f"📄 LaTeX report generated: {report_path}")
    
    # Try to compile LaTeX to PDF
    latex_compilation_successful = False
    try:
        import subprocess
        
        # Find LaTeX executable
        latex_exe = find_latex_executable()
        
        if not latex_exe:
            platform_info = get_platform_latex_instructions()
            required_latex_packages = get_required_latex_packages()
            required_python_packages = get_required_python_packages()
            
            print(f"⚠️  LaTeX not found on this {platform_info['name']} system.")
            print("   📄 LaTeX report file generated: astronomical_analysis_report.tex")
            print("   🌐 You can compile it online with Overleaf:")
            print("      https://www.overleaf.com/")
            print("   📋 Overleaf Instructions:")
            print("      1. Go to https://www.overleaf.com/")
            print("      2. Create a new project")
            print("      3. Upload the .tex file from your output folder")
            print("      4. Click 'Compile' to generate the PDF")
            print(f"   💡 Or install LaTeX locally on {platform_info['name']}:")
            print()
            
            # Show distribution options
            if 'distributions' in platform_info:
                print("   📦 LaTeX Distributions:")
                for dist in platform_info['distributions']:
                    print(f"      • {dist['name']}")
                    print(f"        URL: {dist['url']}")
                    print(f"        Install: {dist['install_cmd']}")
                    if 'package_install' in dist:
                        print(f"        Packages: {dist['package_install']}")
                    print()
            
            # Show package managers
            if 'package_managers' in platform_info:
                print("   📦 Package Managers:")
                for pm in platform_info['package_managers']:
                    print(f"      • {pm['name']}: {pm['install_cmd']}")
                print()
            elif 'package_manager' in platform_info:
                pm = platform_info['package_manager']
                print(f"   📦 Package Manager: {pm['name']}")
                print(f"      Install: {pm['install_cmd']}")
                print()
            
            # Show required LaTeX packages
            print("   📋 Required LaTeX Packages:")
            print("      The following packages are needed for the report:")
            for i, pkg in enumerate(required_latex_packages, 1):
                print(f"      {i:2d}. {pkg}")
            print()
            
            # Show required Python packages
            print("   🐍 Required Python Packages:")
            print("      Install with: pip install <package_name>")
            for i, pkg in enumerate(required_python_packages, 1):
                print(f"      {i:2d}. {pkg}")
            print()
            
            # Show installation commands
            if platform_info['name'] == 'Windows':
                print("   🚀 Quick Installation Commands:")
                print("      # Using Chocolatey (if installed):")
                print("      choco install miktex")
                print("      # Or download MiKTeX from: https://miktex.org/download")
                print()
            elif platform_info['name'] == 'macOS':
                print("   🚀 Quick Installation Commands:")
                print("      # Using Homebrew (if installed):")
                print("      brew install --cask mactex")
                print("      # Or download MacTeX from: https://www.tug.org/mactex/")
                print()
            else:  # Linux
                print("   🚀 Quick Installation Commands:")
                print("      # Ubuntu/Debian:")
                print("      sudo apt update && sudo apt install texlive-full texlive-latex-extra")
                print("      # Fedora:")
                print("      sudo dnf install texlive-scheme-full")
                print("      # Arch Linux:")
                print("      sudo pacman -S texlive-most texlive-lang")
                print()
            
            return
        
        print(f"📄 Found LaTeX: {latex_exe}")
        print("📄 Compiling LaTeX to PDF...")
        
        # Change to output directory
        original_dir = os.getcwd()
        os.chdir(output_folder)
        
        try:
            # First pass: generate initial PDF and auxiliary files
            if SYSTEM_LANGUAGE == 'fr':
                print(f"   🔄 {_('first_pass')} de {_('latex_compilation')}...")
            else:
                print(f"   🔄 {_('first_pass')} of {_('latex_compilation')}...")
            result1 = subprocess.run([latex_exe, '-interaction=nonstopmode', 'astronomical_analysis_report.tex'], 
                                  capture_output=True, text=True, timeout=120)
            
            # Second pass: resolve cross-references and generate bookmarks
            if SYSTEM_LANGUAGE == 'fr':
                print(f"   🔄 {_('second_pass')}...")
            else:
                print(f"   🔄 {_('second_pass')}...")
            result2 = subprocess.run([latex_exe, '-interaction=nonstopmode', 'astronomical_analysis_report.tex'], 
                                  capture_output=True, text=True, timeout=120)
            
            # Third pass: finalize bookmarks and ensure all references are correct
            if SYSTEM_LANGUAGE == 'fr':
                print(f"   🔄 {_('third_pass')}...")
            else:
                print(f"   🔄 {_('third_pass')}...")
            result3 = subprocess.run([latex_exe, '-interaction=nonstopmode', 'astronomical_analysis_report.tex'], 
                                  capture_output=True, text=True, timeout=120)
            
            # Check if PDF was generated (even if there were warnings)
            pdf_path = os.path.join(output_folder, 'astronomical_analysis_report.pdf')
            if os.path.exists(pdf_path):
                if SYSTEM_LANGUAGE == 'fr':
                    print(f"✅ {_('pdf_generated')}: astronomical_analysis_report.pdf")
                    print(f"✅ {_('bookmarks_generated')}")
                else:
                    print(f"✅ {_('pdf_generated')}: astronomical_analysis_report.pdf")
                    print(f"✅ {_('bookmarks_generated')}")
                latex_compilation_successful = True
            else:
                # Extract errors from all 3 passes (check earliest failure first)
                def _extract_latex_errors(result):
                    """Extract error lines from pdflatex output (errors go to stdout)"""
                    lines = []
                    for src in [result.stdout or '', result.stderr or '']:
                        for l in src.split('\n'):
                            if l.startswith('!') or 'Error' in l or 'Fatal' in l or 'Undefined control sequence' in l:
                                lines.append(l.strip())
                    return lines

                all_errors = []
                for pass_num, res in enumerate([result1, result2, result3], 1):
                    errs = _extract_latex_errors(res)
                    if errs:
                        all_errors.append(f"Pass {pass_num}: " + '; '.join(errs[:3]))

                error_output = '\n'.join(all_errors[:6]) if all_errors else ''

                if SYSTEM_LANGUAGE == 'fr':
                    print(f"⚠️  La {_('latex_compilation')} n'a pas généré de PDF")
                    if error_output:
                        print(f"   Erreur:\n   {error_output[:1000]}")
                    else:
                        print(f"   Code retour pdflatex: pass1={result1.returncode}, pass2={result2.returncode}, pass3={result3.returncode}")
                    print(f"   📄 {_('latex_file_available')}: astronomical_analysis_report.tex")
                    print(f"   🌐 {_('compile_online')}:")
                else:
                    print(f"⚠️  {_('compilation_failed')}")
                    if error_output:
                        print(f"   Error:\n   {error_output[:1000]}")
                    else:
                        print(f"   pdflatex return code: pass1={result1.returncode}, pass2={result2.returncode}, pass3={result3.returncode}")
                    print(f"   📄 {_('latex_file_available')}: astronomical_analysis_report.tex")
                    print(f"   🌐 {_('compile_online')}:")
                print("      https://www.overleaf.com/")
                
        except subprocess.TimeoutExpired:
            if SYSTEM_LANGUAGE == 'fr':
                print(f"⚠️  {_('compilation_timeout')}")
            else:
                print(f"⚠️  {_('compilation_timeout')}")
            print(f"   📄 {_('latex_file_available')}: astronomical_analysis_report.tex")
            print(f"   🌐 {_('compile_online')}:")
            print("      https://www.overleaf.com/")
        except FileNotFoundError:
            if SYSTEM_LANGUAGE == 'fr':
                print(f"⚠️  {_('latex_not_found')}")
            else:
                print(f"⚠️  {_('latex_not_found')}")
            print(f"   📄 {_('latex_file_available')}: astronomical_analysis_report.tex")
            print(f"   🌐 {_('compile_online')}:")
            print("      https://www.overleaf.com/")
            
            # Try alternative PDF generation
            if REPORTLAB_AVAILABLE:
                print("🔄 Attempting PDF generation without LaTeX...")
                generate_pdf_report_without_latex(data_by_target, global_data, output_folder)
            else:
                print("💡 To generate PDF without LaTeX, install reportlab: pip install reportlab")
                
        except Exception as e:
            print(f"⚠️  LaTeX compilation error: {e}")
            
            # Try alternative PDF generation
            if REPORTLAB_AVAILABLE:
                print("🔄 Attempting PDF generation without LaTeX...")
                generate_pdf_report_without_latex(data_by_target, global_data, output_folder)
            else:
                print("💡 To generate PDF without LaTeX, install reportlab: pip install reportlab")
            
        finally:
            try:
                # Clean up LaTeX temporary files
                cleanup_latex_temp_files(output_folder)
                # Clean up thumbnail files only if LaTeX compilation was successful and thumbnails were generated
                if latex_compilation_successful and GENERATE_THUMBNAILS:
                    print("🧹 Starting final thumbnail cleanup...")
                    # Since we're already in the output_folder directory, use current directory
                    deleted_count = cleanup_thumbnails(".", keep_thumbnails=False)
                    if deleted_count > 0:
                        print(f"🧹 Cleaned up {deleted_count} thumbnail files")
                    else:
                        print("ℹ️  No thumbnails found to clean up in final cleanup")
            finally:
                # Always return to original directory
                os.chdir(original_dir)
            
    except ImportError:
        print("⚠️  subprocess module not available for LaTeX compilation")
    except Exception as e:
        print(f"⚠️  Error during LaTeX compilation: {e}")


def generate_html_report(data_by_target, global_data, output_folder):
    """Generates an interactive HTML report with collapsible sections"""
    
    if SYSTEM_LANGUAGE == 'fr':
        print(f"🌐 Génération du rapport HTML interactif...")
    else:
        print(f"🌐 Generating interactive HTML report...")
    
    report_path = os.path.join(output_folder, "astronomical_analysis_report.html")
    
    # Translations
    is_fr = SYSTEM_LANGUAGE == 'fr'
    tr = {
        'title': "Rapport d'Analyse Astronomique" if is_fr else "Astronomical Analysis Report",
        'generated_by': "Généré par FITS Analyser" if is_fr else "Generated by FITS Analyser",
        'global_stats': "Statistiques Globales" if is_fr else "Global Statistics",
        'total_files': "Fichiers analysés" if is_fr else "Files analyzed",
        'total_targets': "Cibles trouvées" if is_fr else "Targets found",
        'total_instruments': "Instruments utilisés" if is_fr else "Instruments used",
        'total_telescopes': "Télescopes utilisés" if is_fr else "Telescopes used",
        'total_equipment': "Équipement utilisé" if is_fr else "Equipment used",
        'total_exposure': "Temps d'exposition total" if is_fr else "Total exposure time",
        'targets_detail': "Détails par Cible" if is_fr else "Target Details",
        'files': "fichiers" if is_fr else "files",
        'exposure_time': "Temps d'exposition" if is_fr else "Exposure time",
        'filters': "Filtres" if is_fr else "Filters",
        'filter': "Filtre" if is_fr else "Filter",
        'total': "Total" if is_fr else "Total",
        'count': "Nombre" if is_fr else "Count",
        'dates': "Dates d'observation" if is_fr else "Observation dates",
        'telescopes': "Télescopes" if is_fr else "Telescopes",
        'instruments': "Instruments" if is_fr else "Instruments",
        'nights': "Nuits d'observation" if is_fr else "Observation nights",
        'night': "Nuit" if is_fr else "Night",
        'exposure_details': "Détails des expositions par filtre" if is_fr else "Exposure details by filter",
        'no_data': "Aucune donnée" if is_fr else "No data",
        'expand_all': "Tout déplier" if is_fr else "Expand all",
        'collapse_all': "Tout replier" if is_fr else "Collapse all",
        'search': "Rechercher une cible..." if is_fr else "Search for a target...",
        'summary': "Résumé" if is_fr else "Summary",
        'equipment': "Équipement" if is_fr else "Equipment",
        'timeline': "Chronologie" if is_fr else "Timeline",
        'mosaic_panels': "Panneaux de mosaïque" if is_fr else "Mosaic panels",
        'panel': "Panneau" if is_fr else "Panel",
    }
    
    # Calculate global stats
    total_files = global_data.get('total_files', 0)
    found_targets = global_data.get('found_targets', [])
    used_instruments = global_data.get('used_instruments', [])
    used_telescopes = global_data.get('used_telescopes', [])
    total_time = global_data.get('total_time', 0)
    
    # Format time
    def format_time_html(seconds):
        if seconds <= 0:
            return "0m"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"
    
    # Filter colors for badges
    filter_colors = {
        'L': '#888888', 'R': '#ff4444', 'G': '#44ff44', 'B': '#4444ff',
        'Ha': '#ff6666', 'Hα': '#ff6666', 'H-alpha': '#ff6666',
        'OIII': '#66ffff', 'O3': '#66ffff', '[OIII]': '#66ffff',
        'SII': '#ff9966', 'S2': '#ff9966', '[SII]': '#ff9966',
        'RGB': '#ffffff', 'OSC': '#ffcc00', 'Clear': '#cccccc',
    }
    
    def get_filter_color(filter_name):
        fn = filter_name.upper().strip()
        for key, color in filter_colors.items():
            if key.upper() in fn or fn in key.upper():
                return color
        return '#aaaaaa'
    
    with open(report_path, 'w', encoding='utf-8') as f:
        # HTML Header with CSS
        f.write(f'''<!DOCTYPE html>
<html lang="{'fr' if is_fr else 'en'}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{tr['title']}</title>
    <style>
        :root {{
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --accent-green: #00ff88;
            --accent-blue: #58a6ff;
            --accent-purple: #a371f7;
            --accent-orange: #f0883e;
            --accent-red: #f85149;
            --border-color: #30363d;
        }}
        
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        /* Header */
        .header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            border-radius: 16px;
            padding: 40px;
            margin-bottom: 30px;
            text-align: center;
            border: 1px solid var(--border-color);
            position: relative;
            overflow: hidden;
        }}
        
        .header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--accent-green), var(--accent-blue), var(--accent-purple));
        }}
        
        .header h1 {{
            font-size: 2.5em;
            color: var(--accent-green);
            margin-bottom: 10px;
            text-shadow: 0 0 30px rgba(0, 255, 136, 0.3);
        }}
        
        .header .subtitle {{
            color: var(--text-secondary);
            font-size: 1.1em;
        }}
        
        .header .date {{
            color: var(--accent-blue);
            margin-top: 15px;
            font-size: 0.95em;
        }}
        
        /* Stats Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .stat-card {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 25px;
            text-align: center;
            border: 1px solid var(--border-color);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        
        .stat-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        }}
        
        .stat-card .icon {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        .stat-card .value {{
            font-size: 2.2em;
            font-weight: bold;
            color: var(--accent-green);
        }}
        
        .stat-card .label {{
            color: var(--text-secondary);
            font-size: 0.95em;
            margin-top: 5px;
        }}
        
        /* Controls */
        .controls {{
            display: flex;
            gap: 15px;
            margin-bottom: 25px;
            flex-wrap: wrap;
            align-items: center;
        }}
        
        .search-box {{
            flex: 1;
            min-width: 250px;
            padding: 12px 20px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            background: var(--bg-secondary);
            color: var(--text-primary);
            font-size: 1em;
        }}
        
        .search-box:focus {{
            outline: none;
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.2);
        }}
        
        .btn {{
            padding: 12px 24px;
            border-radius: 8px;
            border: none;
            cursor: pointer;
            font-size: 0.95em;
            font-weight: 500;
            transition: all 0.2s;
        }}
        
        .btn-primary {{
            background: var(--accent-blue);
            color: white;
        }}
        
        .btn-primary:hover {{
            background: #4a90e2;
        }}
        
        .btn-secondary {{
            background: var(--bg-tertiary);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
        }}
        
        .btn-secondary:hover {{
            background: var(--border-color);
        }}
        
        /* Section Headers */
        .section-header {{
            display: flex;
            align-items: center;
            gap: 15px;
            margin: 30px 0 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--border-color);
        }}
        
        .section-header h2 {{
            color: var(--accent-blue);
            font-size: 1.5em;
        }}
        
        .section-header .count {{
            background: var(--accent-blue);
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
        }}
        
        /* Target Cards */
        .target-card {{
            background: var(--bg-secondary);
            border-radius: 12px;
            margin-bottom: 15px;
            border: 1px solid var(--border-color);
            overflow: hidden;
            transition: border-color 0.2s;
        }}
        
        .target-card:hover {{
            border-color: var(--accent-blue);
        }}
        
        .target-header {{
            padding: 20px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--bg-tertiary);
            user-select: none;
        }}
        
        .target-header:hover {{
            background: #2a3142;
        }}
        
        .target-info {{
            display: flex;
            align-items: center;
            gap: 15px;
            flex-wrap: wrap;
        }}
        
        .target-name {{
            font-size: 1.3em;
            font-weight: 600;
            color: var(--accent-green);
        }}
        
        .target-meta {{
            display: flex;
            gap: 20px;
            color: var(--text-secondary);
            font-size: 0.9em;
        }}
        
        .target-meta span {{
            display: flex;
            align-items: center;
            gap: 5px;
        }}
        
        .simbad-details {{
            margin-top: 4px;
            font-size: 0.85em;
            color: var(--text-secondary);
            opacity: 0.95;
        }}
        
        .chevron {{
            font-size: 1.5em;
            color: var(--text-secondary);
            transition: transform 0.3s;
        }}
        
        .target-card.open .chevron {{
            transform: rotate(180deg);
        }}
        
        .target-content {{
            display: none;
            padding: 25px;
            border-top: 1px solid var(--border-color);
        }}
        
        .target-card.open .target-content {{
            display: block;
        }}
        
        /* Filter Badges */
        .filter-badges {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin: 10px 0;
        }}
        
        .filter-badge {{
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 500;
            border: 2px solid;
        }}
        
        /* Info Grid */
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        
        .info-box {{
            background: var(--bg-primary);
            border-radius: 10px;
            padding: 20px;
            border: 1px solid var(--border-color);
        }}
        
        .info-box h4 {{
            color: var(--accent-purple);
            margin-bottom: 15px;
            font-size: 1.05em;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .info-box ul {{
            list-style: none;
        }}
        
        .info-box li {{
            padding: 8px 0;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            color: var(--text-secondary);
        }}
        
        .info-box li:last-child {{
            border-bottom: none;
        }}
        
        .info-box li .value {{
            color: var(--text-primary);
            font-weight: 500;
        }}
        
        /* Night Details */
        .night-section {{
            margin-top: 20px;
        }}
        
        .night-card {{
            background: var(--bg-primary);
            border-radius: 8px;
            margin-bottom: 10px;
            border: 1px solid var(--border-color);
        }}
        
        .night-header {{
            padding: 15px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .night-header:hover {{
            background: var(--bg-tertiary);
        }}
        
        .night-content {{
            display: none;
            padding: 15px;
            border-top: 1px solid var(--border-color);
        }}
        
        .night-card.open .night-content {{
            display: block;
        }}
        
        /* Exposure Table */
        .exposure-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        
        .exposure-table th, .exposure-table td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        
        .exposure-table th {{
            background: var(--bg-tertiary);
            color: var(--accent-blue);
            font-weight: 600;
        }}
        
        .exposure-table tr:hover {{
            background: var(--bg-tertiary);
        }}
        
        /* Mosaic Panels */
        .panels-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            margin-top: 15px;
        }}
        
        .panel-card {{
            background: var(--bg-primary);
            border-radius: 8px;
            padding: 15px;
            text-align: center;
            border: 1px solid var(--border-color);
        }}
        
        .panel-card .panel-num {{
            font-size: 1.5em;
            font-weight: bold;
            color: var(--accent-orange);
        }}
        
        /* Footer */
        .footer {{
            text-align: center;
            padding: 30px;
            margin-top: 40px;
            color: var(--text-secondary);
            border-top: 1px solid var(--border-color);
        }}
        
        /* Responsive */
        @media (max-width: 768px) {{
            .header h1 {{ font-size: 1.8em; }}
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .controls {{ flex-direction: column; }}
            .search-box {{ width: 100%; }}
        }}
        
        /* Animation */
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .target-card {{
            animation: fadeIn 0.3s ease-out;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>🔭 {tr['title']}</h1>
            <p class="subtitle">{tr['generated_by']}</p>
            <p class="date">📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>
        
        <!-- Global Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="icon">📁</div>
                <div class="value">{total_files}</div>
                <div class="label">{tr['total_files']}</div>
            </div>
            <div class="stat-card">
                <div class="icon">🎯</div>
                <div class="value">{len(found_targets)}</div>
                <div class="label">{tr['total_targets']}</div>
            </div>
            <div class="stat-card">
                <div class="icon">🔧</div>
                <div class="value">{len(sorted(set((used_instruments or []) + (used_telescopes or []))))}</div>
                <div class="label">{tr['total_equipment']}</div>
            </div>
            <div class="stat-card">
                <div class="icon">⏱️</div>
                <div class="value">{format_time_html(total_time)}</div>
                <div class="label">{tr['total_exposure']}</div>
            </div>
        </div>
''')
        
        # Controls
        f.write(f'''
        <!-- Controls -->
        <div class="controls">
            <input type="text" class="search-box" id="searchBox" placeholder="{tr['search']}" onkeyup="filterTargets()">
            <button class="btn btn-primary" onclick="expandAll()">{tr['expand_all']}</button>
            <button class="btn btn-secondary" onclick="collapseAll()">{tr['collapse_all']}</button>
        </div>
        
        <!-- Targets Section -->
        <div class="section-header">
            <h2>🎯 {tr['targets_detail']}</h2>
            <span class="count">{len([t for t in data_by_target if data_by_target[t].get('files')])}</span>
        </div>
        
        <div id="targetsContainer">
''')
        
        # Sort targets
        sorted_targets = sorted(data_by_target.items(), key=lambda x: x[0].lower())
        
        for target, data in sorted_targets:
            if not data.get('files'):
                continue
            
            # Skip calibration targets
            target_upper = target.upper()
            if any(cal in target_upper for cal in ['BIAS', 'DARK', 'FLAT', 'CALIBRATION']):
                continue
            
            # Calculate target stats
            num_files = len(data.get('files', []))
            time_by_filter = data.get('time_by_filter', {})
            target_time = 0
            for times in time_by_filter.values():
                if isinstance(times, list):
                    target_time += sum(times)
                else:
                    target_time += times
            
            filters = list(time_by_filter.keys())
            dates = data.get('dates', [])
            telescopes = list(data.get('telescopes', []))
            instruments = list(data.get('instruments', []))
            
            # Escape HTML in target name
            target_escaped = target.replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')
            simbad_info = data.get('simbad_info') or {}
            # Display title: add common name when available (e.g. "M 51 (Whirlpool Galaxy)")
            if simbad_info.get('common_name'):
                common_escaped = simbad_info['common_name'].replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')
                target_display = f"{target_escaped} ({common_escaped})"
            else:
                target_display = target_escaped
            
            f.write(f'''
            <div class="target-card" data-name="{target_escaped.lower()}">
                <div class="target-header" onclick="toggleTarget(this)">
                    <div class="target-info">
                        <span class="target-name">🔭 {target_display}</span>
                        <div class="target-meta">
                            <span>📁 {num_files} {tr['files']}</span>
                            <span>⏱️ {format_time_html(target_time)}</span>
                        </div>
''')
            # SIMBAD details (type, distance, distance ly, redshift) under the target name when available
            if simbad_info:
                simbad_parts = []
                _is_fr_html = (SYSTEM_LANGUAGE == 'fr')
                if simbad_info.get('otype'):
                    type_label = format_simbad_otype(simbad_info['otype'])
                    type_esc = type_label.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    type_desc = get_simbad_otype_description(simbad_info['otype'])
                    type_desc_esc = type_desc.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;') if type_desc else ''
                    if type_desc_esc:
                        simbad_parts.append(f'Type : <span title="{type_desc_esc}" style="cursor: help; border-bottom: 1px dotted currentColor;">{type_esc}</span>' if _is_fr_html else f'Type: <span title="{type_desc_esc}" style="cursor: help; border-bottom: 1px dotted currentColor;">{type_esc}</span>')
                    else:
                        simbad_parts.append(f"Type : {type_esc}" if _is_fr_html else f"Type: {type_esc}")
                if simbad_info.get('distance_pc') is not None and simbad_info['distance_pc'] > 0:
                    d = simbad_info['distance_pc']
                    if d >= 1e6:
                        simbad_parts.append(f"Distance : {d/1e6:.2f} Mpc" if _is_fr_html else f"Distance: {d/1e6:.2f} Mpc")
                    elif d >= 1000:
                        simbad_parts.append(f"Distance : {d/1000:.2f} kpc" if _is_fr_html else f"Distance: {d/1000:.2f} kpc")
                    else:
                        simbad_parts.append(f"Distance : {d:.1f} pc" if _is_fr_html else f"Distance: {d:.1f} pc")
                if simbad_info.get('distance_ly') is not None and simbad_info['distance_ly'] > 0:
                    dly = simbad_info['distance_ly']
                    _ly_unit = "a.l." if _is_fr_html else "ly"
                    if dly >= 1e6:
                        simbad_parts.append(f"{dly/1e6:.2f} M {_ly_unit}")
                    elif dly >= 1000:
                        simbad_parts.append(f"{dly/1000:.1f} k {_ly_unit}")
                    else:
                        simbad_parts.append(f"{dly:.1f} {_ly_unit}")
                if simbad_info.get('redshift') is not None:
                    z = simbad_info['redshift']
                    if abs(z) < 0.01:
                        simbad_parts.append(f"z = {z:.4f}")
                    else:
                        simbad_parts.append(f"z = {z:.3f}")
                if simbad_parts:
                    simbad_str = " | ".join(simbad_parts)
                    # Add SIMBAD link if main_id is available
                    if simbad_info.get('main_id'):
                        import urllib.parse
                        main_id_url = urllib.parse.quote(simbad_info['main_id'], safe='')
                        simbad_url = f"https://simbad.cds.unistra.fr/simbad/sim-id?Ident={main_id_url}"
                        simbad_link = f'<a href="{simbad_url}" target="_blank" style="color: #4fc3f7; text-decoration: none;">SIMBAD</a>'
                        f.write(f'                        <div class="simbad-details">🌐 {simbad_str} | {simbad_link}</div>\n')
                    else:
                        f.write(f'                        <div class="simbad-details">🌐 {simbad_str}</div>\n')
            f.write(f'''                    </div>
                    <span class="chevron">▼</span>
                </div>
                <div class="target-content">
''')
            
            # Filter badges
            if filters:
                f.write('                    <div class="filter-badges">\n')
                for flt in sorted(filters):
                    color = get_filter_color(flt)
                    f.write(f'                        <span class="filter-badge" style="background: {color}22; border-color: {color}; color: {color};">{flt}</span>\n')
                f.write('                    </div>\n')
            
            # Info grid
            f.write('                    <div class="info-grid">\n')
            
            # Summary box
            f.write(f'''                        <div class="info-box">
                            <h4>📊 {tr['summary']}</h4>
                            <ul>
                                <li><span>{tr['files']}:</span> <span class="value">{num_files}</span></li>
                                <li><span>{tr['exposure_time']}:</span> <span class="value">{format_time_html(target_time)}</span></li>
                                <li><span>{tr['filters']}:</span> <span class="value">{', '.join(sorted(filters)) if filters else '-'}</span></li>
''')
            if dates:
                min_date = min(dates)
                max_date = max(dates)
                date_str = min_date if min_date == max_date else f"{min_date} → {max_date}"
                f.write(f'                                <li><span>{tr["dates"]}:</span> <span class="value">{date_str}</span></li>\n')
            f.write('                            </ul>\n                        </div>\n')
            
            # Equipment box (telescope = instrument = lunette: one concept)
            equipment_list = sorted(set((telescopes or []) + (instruments or [])))
            equipment_list = [x for x in equipment_list if x and str(x).strip() and str(x).upper() != 'UNKNOWN']
            if equipment_list:
                f.write(f'''                        <div class="info-box">
                            <h4>🔧 {tr['equipment']}</h4>
                            <ul>
                                <li><span>{tr['equipment']}:</span> <span class="value">{", ".join(equipment_list[:5])}{"..." if len(equipment_list) > 5 else ""}</span></li>
                            </ul>
                        </div>\n''')
            
            # Exposure details by filter
            if time_by_filter:
                f.write(f'''                        <div class="info-box">
                            <h4>📋 {tr['exposure_details']}</h4>
                            <ul>
''')
                for flt in sorted(time_by_filter.keys()):
                    times = time_by_filter[flt]
                    if isinstance(times, list):
                        total = sum(times)
                        count = len(times)
                    else:
                        total = times
                        count = 1
                    f.write(f'                                <li><span>{flt}:</span> <span class="value">{count} × {format_time_html(total/count if count > 0 else 0)} = {format_time_html(total)}</span></li>\n')
                f.write('                            </ul>\n                        </div>\n')
            
            f.write('                    </div>\n')  # End info-grid
            
            # Mosaic panels if present
            panels = data.get('panels', {})
            if panels:
                f.write(f'''                    <div class="night-section">
                        <h4 style="color: var(--accent-orange); margin-bottom: 15px;">🧩 {tr['mosaic_panels']} ({len(panels)})</h4>
                        <div class="panels-grid">
''')
                for panel_num, panel_info in sorted(panels.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0):
                    panel_files = len(panel_info.get('files', []))
                    panel_time = panel_info.get('total_time', 0)
                    f.write(f'''                            <div class="panel-card">
                                <div class="panel-num">{tr['panel']} {panel_num}</div>
                                <div style="color: var(--text-secondary); margin-top: 8px;">📁 {panel_files} {tr['files']}</div>
                                <div style="color: var(--text-secondary);">⏱️ {format_time_html(panel_time)}</div>
                            </div>
''')
                f.write('                        </div>\n                    </div>\n')
            
            # Night details: same logic as LaTeX (build from files with normalized dates)
            files_by_date = build_files_by_date_from_file_list(data.get('files', []))
            if not files_by_date and data.get('files_by_date'):
                files_by_date = data.get('files_by_date', {})
            if not files_by_date and data.get('time_by_filter'):
                files_by_date = group_files_by_date(data)
            if files_by_date and len(files_by_date) > 0:
                f.write(f'''                    <div class="night-section">
                        <h4 style="color: var(--accent-purple); margin-bottom: 15px;">📅 {tr['nights']} ({len(files_by_date)})</h4>
''')
                for date in sorted(files_by_date.keys()):
                    night_data = files_by_date[date]
                    night_time = night_data.get('total_time', 0)
                    
                    # Calculate files count from time_by_filter
                    night_time_by_filter = night_data.get('time_by_filter', {})
                    night_files = sum(len(times) if isinstance(times, list) else 1 for times in night_time_by_filter.values())
                    if night_files == 0:
                        night_files = night_data.get('files_count', night_data.get('total_files', len(night_data.get('files', []))))
                    
                    display_date = format_night_display(date) if 'format_night_display' in dir() else date
                    
                    f.write(f'''                        <div class="night-card">
                            <div class="night-header" onclick="toggleNight(this)">
                                <span>📅 {display_date} - {night_files} {tr['files']} - {format_time_html(night_time)}</span>
                                <span class="chevron" style="font-size: 1em;">▼</span>
                            </div>
                            <div class="night-content">
''')
                    # Build filters dict from time_by_filter if not present
                    night_filters = night_data.get('filters', {})
                    if not night_filters and night_time_by_filter:
                        # Reconstruct filters from time_by_filter
                        night_filters = {}
                        for flt_name, time_list in night_time_by_filter.items():
                            if isinstance(time_list, list):
                                night_filters[flt_name] = {
                                    'count': len(time_list),
                                    'total_time': sum(time_list),
                                    'time': sum(time_list)
                                }
                            else:
                                night_filters[flt_name] = {
                                    'count': 1,
                                    'total_time': time_list,
                                    'time': time_list
                                }
                    
                    if night_filters:
                        # First show filter badges
                        f.write('                                <div class="filter-badges" style="margin-bottom: 15px;">\n')
                        for flt in sorted(night_filters.keys()):
                            color = get_filter_color(flt)
                            flt_stats = night_filters[flt]
                            if isinstance(flt_stats, dict):
                                flt_time = flt_stats.get('total_time', flt_stats.get('time', 0))
                                flt_count = flt_stats.get('count', 0)
                            else:
                                flt_time = flt_stats
                                flt_count = 0
                            avg_exp = flt_time / flt_count if flt_count > 0 else 0
                            f.write(f'                                    <span class="filter-badge" style="background: {color}22; border-color: {color}; color: {color};">{flt}: {flt_count} × {avg_exp:.0f}s = {format_time_html(flt_time)}</span>\n')
                        f.write('                                </div>\n')
                        
                        # Build detailed exposure table from exposure_details
                        exposure_details_data = night_data.get('exposure_details', {}).copy()
                        
                        # Build from time_by_filter if exposure_details is empty
                        if not exposure_details_data and night_time_by_filter:
                            for filter_name, time_list in night_time_by_filter.items():
                                if isinstance(time_list, list) and time_list:
                                    exposure_details_data[filter_name] = {}
                                    for exp_time in time_list:
                                        exp_key = round(exp_time, 1) if exp_time else 0
                                        if exp_key not in exposure_details_data[filter_name]:
                                            exposure_details_data[filter_name][exp_key] = 0
                                        exposure_details_data[filter_name][exp_key] += 1
                        
                        # Collect all unique exposure times
                        all_exposure_times = set()
                        for filter_details in exposure_details_data.values():
                            if filter_details:
                                all_exposure_times.update(filter_details.keys())
                        
                        if all_exposure_times and len(all_exposure_times) > 0:
                            sorted_exposure_times = sorted(all_exposure_times)
                            
                            # Create exposure detail table
                            f.write(f'''                                <table class="exposure-table" style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9em;">
                                    <thead>
                                        <tr style="background: var(--bg-tertiary);">
                                            <th style="padding: 8px; text-align: left; border-bottom: 1px solid var(--border-color);">{tr.get('filter', 'Filter')}</th>
''')
                            for exp_time in sorted_exposure_times:
                                f.write(f'                                            <th style="padding: 8px; text-align: center; border-bottom: 1px solid var(--border-color);">{exp_time:.0f}s</th>\n')
                            f.write(f'                                            <th style="padding: 8px; text-align: center; border-bottom: 1px solid var(--border-color);">{tr.get("total", "Total")}</th>\n')
                            f.write('                                        </tr>\n                                    </thead>\n                                    <tbody>\n')
                            
                            # Filter order
                            filter_order = ['L', 'R', 'G', 'B', 'SII', 'Ha', 'OIII']
                            all_filter_names = list(night_filters.keys())
                            ordered_filters = [f for f in filter_order if f in all_filter_names] + [f for f in sorted(all_filter_names) if f not in filter_order]
                            
                            for filter_name in ordered_filters:
                                color = get_filter_color(filter_name)
                                f.write(f'                                        <tr>\n')
                                f.write(f'                                            <td style="padding: 8px; color: {color}; font-weight: 500;">{filter_name}</td>\n')
                                
                                row_total = 0
                                if filter_name in exposure_details_data and exposure_details_data[filter_name]:
                                    filter_details = exposure_details_data[filter_name]
                                    for exp_time in sorted_exposure_times:
                                        count = filter_details.get(exp_time, 0)
                                        row_total += count
                                        cell_content = str(count) if count > 0 else '-'
                                        f.write(f'                                            <td style="padding: 8px; text-align: center; color: var(--text-secondary);">{cell_content}</td>\n')
                                else:
                                    for exp_time in sorted_exposure_times:
                                        f.write(f'                                            <td style="padding: 8px; text-align: center; color: var(--text-secondary);">-</td>\n')
                                
                                f.write(f'                                            <td style="padding: 8px; text-align: center; font-weight: 500;">{row_total}</td>\n')
                                f.write('                                        </tr>\n')
                            
                            f.write('                                    </tbody>\n                                </table>\n')
                    
                    f.write('                            </div>\n                        </div>\n')
                f.write('                    </div>\n')
            
            f.write('                </div>\n            </div>\n')  # End target-content and target-card
        
        # Footer and JavaScript
        f.write(f'''
        </div>
        
        <!-- Footer -->
        <div class="footer">
            <p>🔭 {tr['generated_by']} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
    
    <script>
        function toggleTarget(header) {{
            const card = header.parentElement;
            card.classList.toggle('open');
        }}
        
        function toggleNight(header) {{
            const card = header.parentElement;
            card.classList.toggle('open');
        }}
        
        function expandAll() {{
            document.querySelectorAll('.target-card').forEach(card => {{
                card.classList.add('open');
            }});
        }}
        
        function collapseAll() {{
            document.querySelectorAll('.target-card').forEach(card => {{
                card.classList.remove('open');
            }});
            document.querySelectorAll('.night-card').forEach(card => {{
                card.classList.remove('open');
            }});
        }}
        
        function filterTargets() {{
            const search = document.getElementById('searchBox').value.toLowerCase();
            document.querySelectorAll('.target-card').forEach(card => {{
                const name = card.getAttribute('data-name');
                if (name.includes(search)) {{
                    card.style.display = 'block';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
        }}
    </script>
</body>
</html>
''')
    
    if SYSTEM_LANGUAGE == 'fr':
        print(f"   ✓ Rapport HTML généré: {os.path.basename(report_path)}")
    else:
        print(f"   ✓ HTML report generated: {os.path.basename(report_path)}")


def generate_pdf_report_without_latex(data_by_target, global_data, output_folder):
    """Generates a PDF report without LaTeX using reportlab"""
    if not REPORTLAB_AVAILABLE:
        print("⚠️  PDF generation without LaTeX requires reportlab")
        print("   Install with: pip install reportlab")
        return
    
    print(f"\nGENERATING PDF REPORT (without LaTeX)")
    print("=" * 80)
    
    # Create PDF file
    pdf_path = os.path.join(output_folder, "astronomical_analysis_report.pdf")
    
    try:
        # Create document
        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        story = []
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            spaceBefore=12,
            textColor=colors.darkblue
        )
        normal_style = styles['Normal']
        
        # Title - bilingual
        _is_fr = (SYSTEM_LANGUAGE == 'fr')
        story.append(Paragraph(
            ("Rapport d'Analyse Astronomique" if _is_fr else "Astronomical Analysis Report"),
            title_style))
        story.append(Spacer(1, 20))

        # Global Summary
        story.append(Paragraph(
            ("Résumé Global" if _is_fr else "Global Summary"),
            heading_style))

        # Global statistics
        total_files = global_data['total_files']
        total_targets = len([t for t in data_by_target.keys() if not is_calibration_target(t)])
        total_time_hours = global_data['total_time'] / 3600

        used_equipment_count = len(sorted(set((global_data.get('used_instruments') or []) + (global_data.get('used_telescopes') or []))))
        if _is_fr:
            global_text = f"""
            <b>Fichiers analysés :</b> {total_files}<br/>
            <b>Cibles trouvées :</b> {total_targets}<br/>
            <b>Temps total d'observation :</b> {format_time_with_details(global_data['total_time'])}<br/>
            <b>Équipements utilisés :</b> {used_equipment_count}<br/>
            """
        else:
            global_text = f"""
            <b>Total files analyzed:</b> {total_files}<br/>
            <b>Targets found:</b> {total_targets}<br/>
            <b>Total observation time:</b> {format_time_with_details(global_data['total_time'])}<br/>
            <b>Equipment used:</b> {used_equipment_count}<br/>
            """
        story.append(Paragraph(global_text, normal_style))
        story.append(Spacer(1, 20))

        # Targets Summary Table
        story.append(Paragraph(
            ("Résumé des Cibles" if _is_fr else "Targets Summary"),
            heading_style))
        
        # Prepare targets data
        target_data = []
        for target, data in data_by_target.items():
            if not data['files'] or is_calibration_target(target):
                continue
            
            # Calculate total time
            files_by_date = group_files_by_date(data)
            total_time = 0
            for date_data in files_by_date.values():
                total_time += date_data['total_time']
            total_time_hours = total_time / 3600
            
            # Get telescope
            telescope = list(data['telescopes'])[0] if data['telescopes'] else 'Unknown'
            total_files = len(data['files'])
            
            target_data.append([target, f"{total_time_hours:.1f}", telescope, str(total_files)])
        
        # Sort by observation time
        target_data.sort(key=lambda x: float(x[1]), reverse=True)
        
        # Create table
        if _is_fr:
            table_data = [['Cible', 'Temps (h)', 'Télescope', 'Fichiers']] + target_data
        else:
            table_data = [['Target', 'Time (h)', 'Telescope', 'Files']] + target_data
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
        story.append(PageBreak())
        
        # Individual target details
        for target, data in data_by_target.items():
            if not data['files'] or is_calibration_target(target):
                continue
            
            story.append(Paragraph(target, heading_style))
            
            # Target summary
            total_files = len(data['files'])
            files_by_date = group_files_by_date(data)
            total_time = 0
            for date_data in files_by_date.values():
                total_time += date_data['total_time']
            
            if _is_fr:
                target_summary = f"""
                <b>Fichiers :</b> {total_files}<br/>
                <b>Temps total :</b> {format_time_with_details(total_time)}<br/>
                <b>Nuits d'observation :</b> {len(files_by_date)}<br/>
                <b>Télescopes :</b> {', '.join(data['telescopes'])}<br/>
                """
            else:
                target_summary = f"""
                <b>Files:</b> {total_files}<br/>
                <b>Total time:</b> {format_time_with_details(total_time)}<br/>
                <b>Observation nights:</b> {len(files_by_date)}<br/>
                <b>Telescopes:</b> {', '.join(data['telescopes'])}<br/>
                """
            story.append(Paragraph(target_summary, normal_style))

            # Filter distribution
            story.append(Paragraph(
                ("Distribution des Filtres" if _is_fr else "Filter Distribution"),
                heading_style))
            
            # Aggregate filter data
            filter_data = []
            for date_data in files_by_date.values():
                for filter_name, time_list in date_data['time_by_filter'].items():
                    if filter_name not in [row[0] for row in filter_data]:
                        filter_data.append([filter_name, 0, 0])
                    
                    # Find existing row and update
                    for row in filter_data:
                        if row[0] == filter_name:
                            row[1] += len(time_list)
                            row[2] += sum(time_list)
                            break
            
            # Sort by filter name
            filter_data.sort(key=lambda x: x[0])
            
            # Create filter table
            if _is_fr:
                filter_table_data = [['Filtre', 'Images', 'Temps Total', 'Temps Moyen']]
            else:
                filter_table_data = [['Filter', 'Images', 'Total Time', 'Average Time']]
            for filter_name, count, total_time in filter_data:
                avg_time = total_time / count if count > 0 else 0
                filter_table_data.append([
                    filter_name,
                    str(count),
                    format_time(total_time),
                    format_time(avg_time)
                ])
            
            filter_table = Table(filter_table_data)
            filter_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(filter_table)
            story.append(PageBreak())
        
        # Build PDF
        doc.build(story)
        print(f"✅ PDF report generated: {pdf_path}")
        
    except Exception as e:
        print(f"❌ Error generating PDF report: {e}")

def get_season_from_date(date_str):
    """Determines the season (Northern Hemisphere) from a date string.
    Accepts formats: YYYY-MM-DD, YYYY/MM/DD, YYYY-MM-DDTHH:MM:SS, YYYY-MM-DD HH:MM:SS.
    Uses meteorological seasons for robustness: Spring=Mar-May, Summer=Jun-Aug, Autumn=Sep-Nov, Winter=Dec-Feb.
    """
    from datetime import datetime
    if not isinstance(date_str, str):
        return 'Unknown'
    candidates = [
        '%Y-%m-%d',
        '%Y/%m/%d',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y/%m/%d %H:%M:%S'
    ]
    date_obj = None
    for fmt in candidates:
        try:
            date_obj = datetime.strptime(date_str[:19], fmt)
            break
        except Exception:
            continue
    if date_obj is None:
        # Try to extract just the date part before 'T' or space
        basic = date_str.split('T')[0].split(' ')[0].replace('/', '-')
        try:
            date_obj = datetime.strptime(basic, '%Y-%m-%d')
        except Exception:
            return 'Unknown'
    m = date_obj.month
    if m in (3, 4, 5):
        return 'Spring'
    if m in (6, 7, 8):
        return 'Summer'
    if m in (9, 10, 11):
        return 'Autumn'
    return 'Winter'

def generate_graphs(data_by_target, global_data, output_folder):
    """Generates combined analysis graphs in a single PNG file"""
    if not MATPLOTLIB_AVAILABLE:
        print("⚠️  Graph generation requires matplotlib")
        return
    
    print(f"\nGENERATING COMBINED GRAPHS")
    print("=" * 80)
    print(f"📊 Génération des graphiques combinés...")
    
    # Set style
    plt.style.use('default')
    plt.rcParams['font.size'] = 10
    
    # Create a large figure with multiple subplots
    fig = plt.figure(figsize=(20, 16))
    
    # 1. Time distribution by filter (top left)
    print("   📊 Génération du graphique de distribution du temps par filtre...")
    ax1 = plt.subplot(2, 3, 1)
    
    filter_times = {}
    for target, data in data_by_target.items():
        # Skip calibration targets
        if is_calibration_target(target):
            continue
            
        # Use files_by_date instead of time_by_filter
        if 'files_by_date' in data:
            for date_data in data['files_by_date'].values():
                for filter_name, time_list in date_data['time_by_filter'].items():
                    if filter_name not in filter_times:
                        filter_times[filter_name] = []
                    filter_times[filter_name].extend(time_list)
        else:
            # Fallback to time_by_filter if files_by_date not available
            for filter_name, time_list in data['time_by_filter'].items():
                if filter_name not in filter_times:
                    filter_times[filter_name] = []
                filter_times[filter_name].extend(time_list)
    
    if filter_times:
        # Desired display order
        desired_order = ['L', 'R', 'G', 'B', 'SII', 'HA', 'OIII']
        # Normalize keys for ordering (map variants to canonical)
        def canonical(f):
            u = f.upper()
            if u in ('LUM', 'L'): return 'L'
            if u in ('H-ALPHA', 'HA'): return 'HA'
            if u in ('O3', 'OIII'): return 'OIII'
            if u in ('S2', 'SII'): return 'SII'
            return u
        # Build ordered list of filters present according to desired order, then append others
        present = list(filter_times.keys())
        ordered = [f for key in desired_order for f in present if canonical(f) == key]
        others = [f for f in present if f not in ordered]
        filters = ordered + others
        times = [sum(filter_times[f]) for f in filters]

        # Consistent colors per filter
        filter_colors = {
            'HA': '#d62728', 'Ha': '#d62728', 'H-ALPHA': '#d62728',
            'OIII': '#1f77b4', 'O3': '#1f77b4',
            'SII': '#9467bd', 'S2': '#9467bd',
            'L': '#7f7f7f', 'LUM': '#7f7f7f',
            'R': '#e41a1c',
            'G': '#4daf4a',
            'B': '#377eb8',
            'RGB': '#ff7f00',
            'OSC': '#ff7f00'
        }

        # Convert filter names to Greek characters for display
        display_filters = [convert_filter_name_to_greek_matplotlib(f) for f in filters]
        bar_colors = [filter_colors.get(f, '#87CEFA') for f in filters]

        # Convert times from seconds to hours for display
        times_hours = [t / 3600 for t in times]
        bars = ax1.bar(display_filters, times_hours, color=bar_colors, edgecolor='navy', alpha=0.85)
        ax1.set_xlabel('Filter')
        ax1.set_ylabel('Total Time (hours)')
        ax1.set_title('Total Observation Time by Filter')
        ax1.tick_params(axis='x', rotation=45)
        
        # Add value labels on bars
        for bar, time_hours in zip(bars, times_hours):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                   f'{time_hours:.1f}h', ha='center', va='bottom')
    
    # 2. Average exposure time by filter (top center)
    print("   📊 Génération du graphique de temps d'exposition moyen par filtre...")
    ax2 = plt.subplot(2, 3, 2)
    
    # Collect exposure time data by filter
    filter_exposure_times = {}
    for target, data in data_by_target.items():
        # Skip calibration targets
        if is_calibration_target(target):
            continue
            
        if 'files_by_date' in data:
            for date_data in data['files_by_date'].values():
                for filter_name, time_list in date_data['time_by_filter'].items():
                    if filter_name not in filter_exposure_times:
                        filter_exposure_times[filter_name] = []
                    filter_exposure_times[filter_name].extend(time_list)
        else:
            # Fallback to time_by_filter if files_by_date not available
            for filter_name, time_list in data['time_by_filter'].items():
                if filter_name not in filter_exposure_times:
                    filter_exposure_times[filter_name] = []
                filter_exposure_times[filter_name].extend(time_list)
    
    if filter_exposure_times:
        # Desired display order
        desired_order = ['L', 'R', 'G', 'B', 'SII', 'HA', 'OIII']
        def canonical(f):
            u = f.upper()
            if u in ('LUM', 'L'): return 'L'
            if u in ('H-ALPHA', 'HA'): return 'HA'
            if u in ('O3', 'OIII'): return 'OIII'
            if u in ('S2', 'SII'): return 'SII'
            return u
        present = list(filter_exposure_times.keys())
        ordered = [f for key in desired_order for f in present if canonical(f) == key]
        others = [f for f in present if f not in ordered]
        filters = ordered + others
        avg_exposure_times = [sum(filter_exposure_times[f]) / len(filter_exposure_times[f]) for f in filters]

        # Consistent colors per filter
        filter_colors = {
            'HA': '#d62728', 'Ha': '#d62728', 'H-ALPHA': '#d62728',
            'OIII': '#1f77b4', 'O3': '#1f77b4',
            'SII': '#9467bd', 'S2': '#9467bd',
            'L': '#7f7f7f', 'LUM': '#7f7f7f',
            'R': '#e41a1c',
            'G': '#4daf4a',
            'B': '#377eb8',
            'RGB': '#ff7f00',
            'OSC': '#ff7f00'
        }

        # Convert filter names to Greek characters for display
        display_filters = [convert_filter_name_to_greek_matplotlib(f) for f in filters]
        bar_colors = [filter_colors.get(f, '#F08080') for f in filters]

        bars = ax2.bar(display_filters, avg_exposure_times, color=bar_colors, edgecolor='darkred', alpha=0.85)
        ax2.set_xlabel('Filter')
        ax2.set_ylabel('Average Exposure Time (seconds)')
        ax2.set_title('Average Exposure Time by Filter')
        ax2.tick_params(axis='x', rotation=45)
        
        # Add value labels on bars
        for bar, time in zip(bars, avg_exposure_times):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                   f'{time:.1f}s', ha='center', va='bottom')
    else:
        ax2.set_xlabel('Filter')
        ax2.set_ylabel('Average Exposure Time (seconds)')
        ax2.set_title('Average Exposure Time by Filter (No Data)')
        ax2.text(0.5, 0.5, 'No exposure data available', transform=ax2.transAxes, 
                ha='center', va='center', fontsize=12, color='red')
    
    # 3. Target time comparison (top right)
    print("   📊 Génération du graphique de comparaison du temps par cible...")
    ax3 = plt.subplot(2, 3, 3)
    
    # Limit to top 10 targets by observation time to keep graph readable
    target_time_pairs = []
    for target, data in data_by_target.items():
        # Skip calibration targets
        if is_calibration_target(target):
            continue
            
        # Use files_by_date instead of time_by_filter
        if 'files_by_date' in data:
            total_time = 0
            for date_data in data['files_by_date'].values():
                total_time += date_data['total_time']
        else:
            # Fallback to time_by_filter if files_by_date not available
            total_time = sum(sum(times) for times in data['time_by_filter'].values())
        target_time_pairs.append((target, total_time))
    
    # Sort by time (descending) and take top 10
    target_time_pairs.sort(key=lambda x: x[1], reverse=True)
    top_targets = target_time_pairs[:10]
    
    if top_targets:
        targets = [pair[0] for pair in top_targets]
        target_times = [pair[1] for pair in top_targets]
        
        # Truncate long target names for better display
        display_targets = []
        for target in targets:
            if len(target) > 20:
                display_targets.append(target[:17] + '...')
            else:
                display_targets.append(target)
        
        bars = ax3.bar(display_targets, target_times, color='lightgreen', edgecolor='darkgreen', alpha=0.7)
        ax3.set_xlabel('Target')
        ax3.set_ylabel('Total Time (seconds)')
        ax3.set_title('Top 10 Targets by Observation Time')
        ax3.tick_params(axis='x', rotation=90)
        
        # Add extra margin at the top to prevent annotation from masking bars
        y_max = max(target_times) if target_times else 0
        ax3.set_ylim(0, y_max * 1.15)  # Add 15% margin at the top
        
        # Adjust layout to prevent label overlap
        plt.tight_layout()
        
        # Add value labels on bars
        for bar, time in zip(bars, target_times):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                   f'{format_time_hours_minutes(time)}', ha='center', va='bottom')
        
        # Add note if there are more targets
        if len(data_by_target) > 10:
            # Position the annotation at the bottom to avoid masking bars
            ax3.text(0.02, 0.02, f'Showing top 10 of {len(data_by_target)} targets', 
                    transform=ax3.transAxes, fontsize=8, verticalalignment='bottom',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
    else:
        ax3.set_xlabel('Target')
        ax3.set_ylabel('Total Time (seconds)')
        ax3.set_title('Observation Time by Target (No Data)')
        ax3.text(0.5, 0.5, 'No target data available', transform=ax3.transAxes, 
                ha='center', va='center', fontsize=12, color='red')
    
    # 4. Target files comparison (bottom left)
    print("   📊 Génération du graphique de comparaison du nombre de fichiers par cible...")
    ax4 = plt.subplot(2, 3, 4)
    
    # Collect all targets with their file counts and sort by files (descending)
    target_file_pairs = []
    for target, data in data_by_target.items():
        # Skip calibration targets
        if is_calibration_target(target):
            continue
        total_files = len(data['files'])
        target_file_pairs.append((target, total_files))
    
    # Sort by file count (descending) and take top 10
    target_file_pairs.sort(key=lambda x: x[1], reverse=True)
    top_file_targets = target_file_pairs[:10]
    
    if top_file_targets:
        targets = [pair[0] for pair in top_file_targets]
        target_files = [pair[1] for pair in top_file_targets]
        
        # Truncate long target names for better display
        display_targets = []
        for target in targets:
            if len(target) > 20:
                display_targets.append(target[:17] + '...')
            else:
                display_targets.append(target)
        
        bars = ax4.bar(display_targets, target_files, color='orange', edgecolor='darkorange', alpha=0.7)
        ax4.set_xlabel('Target')
        ax4.set_ylabel('Number of Files')
        ax4.set_title('Top 10 Targets by Number of Files')
        ax4.tick_params(axis='x', rotation=90)
        
        # Add extra margin at the top to prevent annotation from masking bars
        y_max = max(target_files) if target_files else 0
        ax4.set_ylim(0, y_max * 1.15)  # Add 15% margin at the top
        
        # Adjust layout to prevent label overlap
        plt.tight_layout()
        
        # Add value labels on bars
        for bar, files in zip(bars, target_files):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height,
                   f'{files}', ha='center', va='bottom')
        
        # Add note if there are more targets
        if len(data_by_target) > 10:
            # Position the annotation at the bottom to avoid masking bars
            ax4.text(0.02, 0.02, f'Showing top 10 of {len(data_by_target)} targets', 
                    transform=ax4.transAxes, fontsize=8, verticalalignment='bottom',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
    else:
        ax4.set_xlabel('Target')
        ax4.set_ylabel('Number of Files')
        ax4.set_title('Number of Files by Target (No Data)')
        ax4.text(0.5, 0.5, 'No target data available', transform=ax4.transAxes, 
                ha='center', va='center', fontsize=12, color='red')
    
    # 5. Observation hours by season (bottom center)
    print("   📊 Génération du graphique des heures d'observation par saison...")
    ax5 = plt.subplot(2, 3, 5)
    
    # Collect observation data by season
    season_data = {}
    for target, data in data_by_target.items():
        # Skip calibration targets
        if is_calibration_target(target):
            continue
            
        if 'files_by_date' in data:
            for date_str, date_data in data['files_by_date'].items():
                season = get_season_from_date(date_str)
                if season not in season_data:
                    season_data[season] = 0
                season_data[season] += date_data['total_time']
        else:
            # Fallback: try to extract dates from other sources
            if 'dates' in data and data['dates']:
                for date_str in data['dates']:
                    season = get_season_from_date(date_str)
                    if season not in season_data:
                        season_data[season] = 0
                    # Estimate time per date (total time / number of dates)
                    estimated_time_per_date = data['total_time'] / len(data['dates']) if data['dates'] else 0
                    season_data[season] += estimated_time_per_date
    
    if season_data:
        seasons = list(season_data.keys())
        # Sort seasons in chronological order
        season_order = ['Spring', 'Summer', 'Autumn', 'Winter']
        seasons = [s for s in season_order if s in seasons] + [s for s in seasons if s not in season_order]
        
        times = [season_data[s] for s in seasons]
        hours = [t / 3600 for t in times]  # Convert to hours
        
        # Color mapping for seasons
        season_colors = {
            'Spring': '#90EE90',  # Light green
            'Summer': '#FFD700',  # Gold
            'Autumn': '#FF8C00',  # Dark orange
            'Winter': '#87CEEB',  # Sky blue
            'Unknown': '#D3D3D3'  # Light gray
        }
        
        colors = [season_colors.get(season, '#D3D3D3') for season in seasons]
        
        bars = ax5.bar(seasons, hours, color=colors, edgecolor='black', alpha=0.8)
        ax5.set_xlabel('Season')
        ax5.set_ylabel('Observation Hours')
        ax5.set_title('Observation Hours by Season')
        ax5.tick_params(axis='x', rotation=45)
        
        # Add extra margin at the top to prevent annotation from masking bars
        y_max = max(hours) if hours else 0
        ax5.set_ylim(0, y_max * 1.15)  # Add 15% margin at the top
        
        # Add value labels on bars
        for bar, hours_val in zip(bars, hours):
            height = bar.get_height()
            ax5.text(bar.get_x() + bar.get_width()/2., height,
                   f'{hours_val:.1f}h', ha='center', va='bottom')
        
        # Add total hours annotation
        total_hours = sum(hours)
        # Position the annotation at the bottom to avoid masking bars
        ax5.text(0.02, 0.02, f'Total: {total_hours:.1f} hours', 
                transform=ax5.transAxes, fontsize=10, verticalalignment='bottom',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='lightblue', alpha=0.7))
    else:
        ax5.set_xlabel('Season')
        ax5.set_ylabel('Observation Hours')
        ax5.set_title('Observation Hours by Season (No Data)')
        ax5.text(0.5, 0.5, 'No seasonal data available', transform=ax5.transAxes, 
                ha='center', va='center', fontsize=12, color='red')
    
    # 6. Global statistics summary (bottom right)
    print("   📊 Génération du résumé des statistiques globales...")
    ax6 = plt.subplot(2, 3, 6)
    ax6.axis('off')
    
    # Calculate global statistics
    total_files = global_data['total_files']
    total_time = global_data['total_time']
    total_targets = len(data_by_target)
    # Calculate total filters from files_by_date
    all_filters = set()
    for target, data in data_by_target.items():
        # Skip calibration targets
        if is_calibration_target(target):
            continue
            
        if 'files_by_date' in data:
            for date_data in data['files_by_date'].values():
                all_filters.update(date_data['time_by_filter'].keys())
        else:
            all_filters.update(data['time_by_filter'].keys())
    total_filters = len(all_filters)
    
    # Calculate filter statistics
    filter_stats = {}
    for target, data in data_by_target.items():
        # Skip calibration targets
        if is_calibration_target(target):
            continue
            
        if 'files_by_date' in data:
            for date_data in data['files_by_date'].values():
                for filter_name, time_list in date_data['time_by_filter'].items():
                    if filter_name not in filter_stats:
                        filter_stats[filter_name] = {'files': 0, 'time': 0}
                    filter_stats[filter_name]['files'] += len(time_list)
                    filter_stats[filter_name]['time'] += sum(time_list)
        else:
            for filter_name, time_list in data['time_by_filter'].items():
                if filter_name not in filter_stats:
                    filter_stats[filter_name] = {'files': 0, 'time': 0}
                filter_stats[filter_name]['files'] += len(time_list)
                filter_stats[filter_name]['time'] += sum(time_list)
    
    # Create summary text
    summary_text = f"""
GLOBAL STATISTICS SUMMARY

Total Files: {total_files}
Total Time: {format_time_hours_minutes(total_time)}
Targets: {total_targets}
Filters: {total_filters}

FILTER DETAILS:
"""
    
    # Add filter details in specific order
    filter_order = ['L', 'R', 'G', 'B', 'SII', 'Ha', 'OIII']
    for filter_name in filter_order:
        if filter_name in filter_stats:
            stats = filter_stats[filter_name]
            summary_text += f"• {filter_name}: {stats['files']} files, {format_time_hours_minutes(stats['time'])}\n"
    
    # Add any remaining filters not in the specified order
    for filter_name in sorted(filter_stats.keys()):
        if filter_name not in filter_order:
            stats = filter_stats[filter_name]
            summary_text += f"• {filter_name}: {stats['files']} files, {format_time_hours_minutes(stats['time'])}\n"
    
    summary_text += "\nTARGETS:\n"
    for target in targets:
        data = data_by_target[target]
        target_time = sum(sum(times) for times in data['time_by_filter'].values())
        target_files = len(data['files'])
        summary_text += f"• {target}: {target_files} files, {format_time_hours_minutes(target_time)}\n"
    
    ax6.text(0.05, 0.95, summary_text, transform=ax6.transAxes, fontsize=10,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgray', alpha=0.8))
    
    # Add main title
    fig.suptitle('Astronomical Analysis - Complete Statistics', fontsize=16, fontweight='bold')
    
    # Adjust layout and save - give more space at bottom for vertical labels
    plt.subplots_adjust(top=0.93, bottom=0.15, left=0.05, right=0.95, hspace=0.4, wspace=0.3)
    
    # Save the combined graph in both PNG and SVG formats
    combined_graph_png_path = os.path.join(output_folder, 'astronomical_analysis_complete.png')
    combined_graph_svg_path = os.path.join(output_folder, 'astronomical_analysis_complete.svg')
    
    # Save as PNG (high resolution)
    print(f"   💾 Sauvegarde du graphique PNG...")
    plt.savefig(combined_graph_png_path, dpi=300, bbox_inches='tight')
    print(f"   ✓ Graphique PNG sauvegardé: {os.path.basename(combined_graph_png_path)}")
    
    # Save as SVG (vector format)
    print(f"   💾 Sauvegarde du graphique SVG...")
    plt.savefig(combined_graph_svg_path, format='svg', bbox_inches='tight')
    print(f"   ✓ Graphique SVG sauvegardé: {os.path.basename(combined_graph_svg_path)}")
    
    plt.close()
    
    print("✅ Tous les graphiques ont été générés avec succès (PNG et SVG)")

def compress_output_folder(output_folder):
    """Compresses the output folder to a ZIP file"""
    try:
        zip_path = output_folder + ".zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(output_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, output_folder)
                    zipf.write(file_path, arcname)
        
        print(f"📦 Output folder compressed to: {zip_path}")
        return zip_path
        
    except Exception as e:
        print(f"❌ Error compressing output folder: {e}")
        return None

def save_config(config):
    """Save configuration to file"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"💾 Configuration saved to: {CONFIG_FILE}")
        return True
    except Exception as e:
        print(f"❌ Error saving configuration: {e}")
        return False

def load_config():
    """Load configuration from file"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(config):
    """Save configuration to file"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving configuration: {e}")

def get_sensor_info(camera_model):
    """Get sensor information from database"""
    return SENSORS_DATABASE.get(camera_model, SENSORS_DATABASE['default'])

def get_telescope_info(telescope_model):
    """Get telescope information from database"""
    return TELESCOPES_DATABASE.get(telescope_model, TELESCOPES_DATABASE['default'])

def extract_filter_from_filename(filename):
    """Extract filter information from filename.
    Order: 1) regex patterns (most specific, e.g. IDAS NBZ II), 2) width+nm fallback, 3) FILTERS_INFO key substring.
    """
    filename_upper = filename.upper()
    
    # 1) Pattern matching first (more specific than raw key substring, e.g. NBZ II vs NBZ)
    patterns = {
            # H-Alpha variants - comprehensive coverage
            r'\bH[-_\s]?A(LPHA)?\b': 'HA',
            r'\bH[-_\s]?A\b': 'HA',  # H-A, H_A, H A
            r'\bHA\b': 'HA',  # HA, ha, Ha
            r'\bHALPHA\b': 'HA',  # HALPHA, halpha, Halpha
            r'\bHYDROGEN[-_\s]?ALPHA\b': 'HA',  # HYDROGEN ALPHA, HYDROGEN-ALPHA
            r'\bH[-_\s]?ALPHA\b': 'HA',  # H-ALPHA, H_ALPHA, H ALPHA
            
            # H-Beta variants
            r'\bH[-_\s]?B(ETA)?\b': 'HBETA',
            r'\bH[-_\s]?B\b': 'HBETA',  # H-B, H_B, H B
            r'\bHB\b': 'HBETA',  # HB, hb, Hb
            r'\bHBETA\b': 'HBETA',  # HBETA, hbeta, Hbeta
            r'\bHYDROGEN[-_\s]?BETA\b': 'HBETA',  # HYDROGEN BETA, HYDROGEN-BETA
            
            # Support for Greek characters in filter names
            r'\bHα\b': 'HA',
            r'\bHβ\b': 'HBETA',
            r'\bHγ\b': 'HGAMMA',
            r'\bHδ\b': 'HDELTA',
            r'\bHε\b': 'HEPSILON',
            r'\bHζ\b': 'HZETA',
            r'\bHη\b': 'HETA',
            r'\bHθ\b': 'HTHETA',
            r'\bHι\b': 'HIOTA',
            r'\bHκ\b': 'HKAPPA',
            r'\bHλ\b': 'HLAMBDA',
            r'\bHμ\b': 'HMU',
            r'\bHν\b': 'HNU',
            r'\bHξ\b': 'HXI',
            r'\bHο\b': 'HOMICRON',
            r'\bHπ\b': 'HPI',
            r'\bHρ\b': 'HRHO',
            r'\bHσ\b': 'HSIGMA',
            r'\bHτ\b': 'HTAU',
            r'\bHυ\b': 'HUPSILON',
            r'\bHφ\b': 'HPHI',
            r'\bHχ\b': 'HCHI',
            r'\bHψ\b': 'HPSI',
            r'\bHω\b': 'HOMEGA',
            
            # OIII variants - comprehensive coverage
            r'\bOIII\b': 'OIII',
            r'\bO3\b': 'OIII',  # O3, o3
            r'\bO[-_\s]?3\b': 'OIII',  # O-3, O_3, O 3
            r'\bOXYGEN[-_\s]?III\b': 'OIII',  # OXYGEN III, OXYGEN-III
            r'\bOXYGEN[-_\s]?3\b': 'OIII',  # OXYGEN 3, OXYGEN-3
            
            # SII variants - comprehensive coverage  
            r'\bSII\b': 'SII',
            r'\bS2\b': 'SII',  # S2, s2
            r'\bS[-_\s]?2\b': 'SII',  # S-2, S_2, S 2
            r'\bSULFUR[-_\s]?II\b': 'SII',  # SULFUR II, SULFUR-II
            r'\bSULFUR[-_\s]?2\b': 'SII',  # SULFUR 2, SULFUR-2
            
            # NII variants
            r'\bNII\b': 'NII',
            r'\bN2\b': 'NII',  # N2, n2
            r'\bN[-_\s]?2\b': 'NII',  # N-2, N_2, N 2
            r'\bNITROGEN[-_\s]?II\b': 'NII',  # NITROGEN II, NITROGEN-II
            r'\bNITROGEN[-_\s]?2\b': 'NII',  # NITROGEN 2, NITROGEN-2
            
            # HEII variants
            r'\bHEII\b': 'HEII',
            r'\bHE[-_\s]?II\b': 'HEII',  # HE-II, HE_II, HE II
            r'\bHE[-_\s]?2\b': 'HEII',  # HE-2, HE_2, HE 2
            r'\bHELIUM[-_\s]?II\b': 'HEII',  # HELIUM II, HELIUM-II
            r'\bHELIUM[-_\s]?2\b': 'HEII',  # HELIUM 2, HELIUM-2
            
            # Luminance variants - comprehensive coverage
            r'\bLUM(INANCE)?\b': 'LUM',
            r'\bLUMINANCE\b': 'LUM',  # LUMINANCE, luminance, Luminance
            r'\bLUM\b': 'LUM',  # LUM, lum, Lum
            r'\bLIGHT\b': 'LUM',  # LIGHT, light, Light
            r'\bL\b': 'L',  # L, l (single letter)
            
            # Clear filter
            r'\bCLEAR\b': 'CLEAR',
            
            # Other filters
            r'\bIR[-_\s]?CUT\b': 'IRCUT',
            r'\bUV[-_\s]?IR\b': 'UVIR',
            r'\bARGON\b': 'ARGON',
            r'\bARIII\b': 'ARIII',
            r'\bARIV\b': 'ARIV',
            r'\bARV\b': 'ARV',
            r'\bNEON\b': 'NEON',
            r'\bKRYPTON\b|\bKR\b': 'KRYPTON',
            r'\bXENON\b|\bXE\b': 'XENON',
            r'\bHE[-_\s]?I\b|\bHELIUM\b': 'HEI',
            r'\bSODIUM\b|\bNA\b': 'SODIUM',
            r'\bPOTASSIUM\b|\bK\b': 'K',
            r'\bCA[-_\s]?K\b': 'CAK',
            r'\bCA[-_\s]?H\b': 'CAH',
            r'\bOI[-_\s]?5577\b': 'OI_5577',
            r'\bOI[-_\s]?6300\b': 'OI_6300',
            r'\bOI[-_\s]?6364\b': 'OI_6364',
            r'\bSIII[-_\s]?9531\b|\bS3[-_\s]?9531\b': 'SIII_9531',
            r'\bCH4\b|\bMETHANE\b': 'CH4',
            r'\bRGB\b|\bOSC\b|\bCOLOR\b': 'RGB',
            
            # Broadband filters - comprehensive coverage
            r'\bU\b': 'U',
            r'\bV\b': 'V',
            r'\bR\b': 'R',
            r'\bI\b': 'I',
            r'\bRC\b': 'RC',
            r'\bIC\b': 'IC',
            r'\bG\b': 'G',
            r'\bB\b': 'B',
            
            # RGB variants - comprehensive coverage
            r'\bGREEN\b': 'G',  # GREEN, green, Green
            r'\bRED\b': 'R',    # RED, red, Red
            r'\bBLUE\b': 'B',   # BLUE, blue, Blue
            
            # Light pollution and multiband
            r'\bCLS\b': 'CLS',
            r'\bUHC\b': 'UHC',
            r'\bL[-_\s]?PRO\b|\bLPRO\b': 'LPRO',
            r'\bL[-_\s]?E[Nn]HANCE\b|\bLENHANCE\b': 'LEHNANCE',
            r'\bL[-_\s]?E[Xx]TREME\b|\bLEXTREME\b': 'LEXTREME',
            r'\bL[-_\s]?ULTIMATE\b|\bLULTIMATE\b': 'LULTIMATE',
            r'\bIDAS\b.*\bLPS\b': 'IDAS_LPS',
            r'\bIDAS\b.*\bD1\b': 'IDAS_LPS_D1',
            r'\bIDAS\b.*\bD2\b': 'IDAS_LPS_D2',
            r'\bIDAS\b.*\bNBZ\b.*\bII\b|\bNBZ\s*II\b': 'IDAS_NBZ_II',
            r'\bIDAS\b.*\bNB3\b|\bNB3\b': 'IDAS_NB3',
            r'\bIDAS\b.*\bNBZ\b|\bNBZ\b': 'NBZ',
            r'\bTRI[-_\s]?BAND\b': 'TRIBAND',
            r'\bQUAD[-_\s]?BAND\b': 'QUAD_BAND',
            
            # Sloan aliases
            r'\bU[_-]?SDSS|U[_-]?SLOAN\b': 'U_SDSS',
            r'\bG[_-]?SDSS|G[_-]?SLOAN\b': 'G_SDSS',
            r'\bR[_-]?SDSS|R[_-]?SLOAN\b': 'R_SDSS',
            r'\bI[_-]?SDSS|I[_-]?SLOAN\b': 'I_SDSS',
            r'\bZ[_-]?SDSS|Z[_-]?SLOAN\b': 'Z_SDSS',
            
            # Filter aliases - improved patterns for better detection
            r'\bLUMINANCE\b': 'L',
            r'\bLUM\b': 'L',
            r'\bHALPHA\b': 'HA',
            r'\bH[-_\s]?ALPHA\b': 'HA',
            r'\bH\b': 'HA'  # Single H defaults to H-Alpha
    }
    
    # Additional patterns for common filter naming in folder structures
    additional_patterns = {
        r'LUMINANCE': 'L',
        r'LUM': 'L',
        r'GREEN': 'G',
        r'RED': 'R',
        r'BLUE': 'B',
        r'LIGHT': 'L',
        r'CLEAR': 'CLEAR'
    }
    
    for pattern, filter_code in patterns.items():
        if re.search(pattern, filename_upper):
            return filter_code, FILTERS_INFO[filter_code]
    
    for pattern, filter_code in additional_patterns.items():
        if pattern in filename_upper:
            return filter_code, FILTERS_INFO[filter_code]
    
    # 2) Width extraction (e.g., Ha_3nm, OIII5nm)
    width_match = re.search(r'(\d{1,2})\s*nm', filename_upper)
    if width_match:
        nm = float(width_match.group(1))
        for hint, code in [('HA','HA'), ('OIII','OIII'), ('O3','O3'), ('SII','SII'), ('S2','S2'), ('HB','HBETA'), ('HEII','HEII'), ('NII','NII')]:
            if hint in filename_upper:
                base = FILTERS_INFO.get(code)
                if base:
                    return code, {**base, 'width': nm}
    
    # 3) Fallback: direct FILTERS_INFO key substring (e.g. LEXTREME in filename)
    for filter_code, info in FILTERS_INFO.items():
        if filter_code.upper() in filename_upper:
            return filter_code, info
    
    return None, None

def analyze_fits_header(file_path):
    """Analyze FITS header to extract metadata"""
    try:
        if not ASTROPY_AVAILABLE:
            return {}
            
        with open_fits_for_data(file_path, header_only=True) as hdul:
            # Get best header (checks extensions for .fits.fz files)
            header = get_best_header(hdul)
            if header is None:
                header = hdul[0].header
            
            metadata = {}
            
            # Basic information
            if 'EXPTIME' in header:
                metadata['exposure_time'] = float(header['EXPTIME'])
            elif 'EXPOSURE' in header:
                metadata['exposure_time'] = float(header['EXPOSURE'])
            
            if 'GAIN' in header:
                metadata['gain'] = float(header['GAIN'])
            elif 'EGAIN' in header:
                metadata['gain'] = float(header['EGAIN'])
            
            if 'TEMPERATURE' in header:
                metadata['temperature'] = float(header['TEMPERATURE'])
            elif 'CCD-TEMP' in header:
                metadata['temperature'] = float(header['CCD-TEMP'])
            
            # Normalize image type; accept variants like "Light", "Light Frame", etc.
            image_type_raw = None
            if 'IMAGETYP' in header:
                image_type_raw = str(header['IMAGETYP'])
            elif 'IMTYPE' in header:
                image_type_raw = str(header['IMTYPE'])
            
            if image_type_raw:
                t = image_type_raw.strip().upper()
                if 'LIGHT' in t:
                    metadata['image_type'] = 'LIGHT'
                elif 'DARK' in t:
                    metadata['image_type'] = 'DARK'
                elif 'BIAS' in t or 'OFFSET' in t:
                    metadata['image_type'] = 'BIAS'
                else:
                    metadata['image_type'] = t
            else:
                # Fallback from filename: if not containing dark/bias, assume LIGHT
                name_upper = file_path.name.upper()
                if ('DARK' in name_upper) or ('BIAS' in name_upper) or ('OFFSET' in name_upper):
                    if 'DARK' in name_upper:
                        metadata['image_type'] = 'DARK'
                    else:
                        metadata['image_type'] = 'BIAS'
                else:
                    metadata['image_type'] = 'LIGHT'
            
            if 'FILTER' in header:
                metadata['filter'] = header['FILTER']
            
            # Detect Bayer pattern to flag OSC/color cameras
            bayer_keys = ['BAYERPAT', 'BAYERPATN', 'BAYERPATTERN', 'COLORTYP', 'COLORSPACE']
            bayer_value = None
            for k in bayer_keys:
                if k in header:
                    try:
                        bayer_value = str(header[k]).strip().upper()
                        break
                    except Exception:
                        pass
            
            # Check if the bayer value is a valid Bayer pattern
            valid_bayer_patterns = [
                'BGGR', 'RGGB', 'GRBG', 'GBRG',  # Standard Bayer patterns
                'BG', 'RG', 'GR', 'GB',          # 2-letter patterns
                'BAYER', 'COLOR', 'RGB',         # Generic color indicators
                'CFA', 'COLORFILTER',            # Color filter array indicators
                '1', 'TRUE', 'YES', 'ON'        # Boolean indicators
            ]
            
            if bayer_value and any(pattern in bayer_value for pattern in valid_bayer_patterns):
                metadata['is_color'] = True
                metadata['bayer_pattern'] = bayer_value
                # If no explicit filter provided, mark as RGB/OSC so files are not dropped
                if 'filter' not in metadata or not str(metadata['filter']).strip():
                    metadata['filter'] = 'RGB'
            
            inst = get_instrument_from_header(header)
            tel = get_telescope_from_header(header)
            if inst and inst != 'Unknown':
                metadata['instrument'] = inst
            if tel and tel != 'Unknown':
                metadata['telescope'] = tel
            
            # Object name with fallback from filename if missing/empty
            obj = None
            if 'OBJECT' in header:
                obj = str(header['OBJECT']).strip()
            if not obj:
                # Derive from filename: take leading words before first underscore or date pattern
                base = file_path.stem  # filename without extension
                # remove trailing timestamp-like suffixes: _YYYY-MM-DD or _YYYYMMDD etc.
                base_clean = re.split(r"_\d{4}[-_]?(\d{2})?[-_]?(\d{2})?", base)[0]
                # replace separators with space
                base_clean = re.sub(r"[_-]+", " ", base_clean).strip()
                obj = base_clean if base_clean else 'Unknown'
            
            # Normalize object name (case-insensitive, remove extra spaces)
            if obj and obj != 'Unknown':
                obj = normalize_target_name(obj)
            metadata['object'] = obj
            
            if 'DATE-OBS' in header:
                metadata['date_obs'] = header['DATE-OBS']
            
            if 'SITELAT' in header:
                metadata['latitude'] = float(header['SITELAT'])
            
            if 'SITELONG' in header:
                metadata['longitude'] = float(header['SITELONG'])
            
            # Fallbacks from filename if missing
            base_upper = file_path.stem.upper()
            # Instrument/camera
            if 'instrument' not in metadata or not str(metadata['instrument']).strip():
                for cam in SENSORS_DATABASE.keys():
                    if cam == 'default':
                        continue
                    if cam.upper() in base_upper:
                        metadata['instrument'] = cam
                        break
            # Telescope
            if 'telescope' not in metadata or not str(metadata['telescope']).strip():
                for tel in TELESCOPES_DATABASE.keys():
                    if tel == 'default':
                        continue
                    if tel.upper() in base_upper:
                        metadata['telescope'] = normalize_telescope_name(tel)
                        break
            # Filter from filename if missing
            if 'filter' not in metadata or not str(metadata['filter']).strip():
                filt_code, filt_info = extract_filter_from_filename(file_path.name)
                if filt_code:
                    metadata['filter'] = filt_code
            
            # Ensure essential fields for inclusion
            if 'image_type' not in metadata or not str(metadata['image_type']).strip():
                metadata['image_type'] = 'LIGHT'
            if 'filter' not in metadata or not str(metadata['filter']).strip():
                # Try to detect filter from filename more aggressively
                filename_upper = file_path.name.upper()
                if 'LUMINANCE' in filename_upper or 'LUM' in filename_upper:
                    metadata['filter'] = 'L'
                elif 'RED' in filename_upper:
                    metadata['filter'] = 'R'
                elif 'GREEN' in filename_upper:
                    metadata['filter'] = 'G'
                elif 'BLUE' in filename_upper:
                    metadata['filter'] = 'B'
                elif 'HALPHA' in filename_upper or 'H-ALPHA' in filename_upper:
                    metadata['filter'] = 'HA'
                elif 'OIII' in filename_upper or 'O3' in filename_upper:
                    metadata['filter'] = 'OIII'
                elif 'SII' in filename_upper or 'S2' in filename_upper:
                    metadata['filter'] = 'SII'
                else:
                    metadata['filter'] = 'RGB' if metadata.get('is_color') else 'L'  # Default to L for unknown filters
            if 'object' not in metadata or not str(metadata['object']).strip():
                # Reuse previous filename-based object derivation
                base = file_path.stem
                base_clean = re.split(r"_\d{4}[-_]?(\d{2})?[-_]?(\d{2})?", base)[0]
                base_clean = re.sub(r"[_-]+", " ", base_clean).strip()
                if base_clean:
                    # Normalize object name (case-insensitive, remove extra spaces)
                    metadata['object'] = normalize_target_name(base_clean)
                else:
                    metadata['object'] = 'Unknown'

            return metadata
            
    except Exception as e:
        print(f"Error analyzing FITS header for {file_path}: {e}")
        return {}

# Placeholder for the complete implementation
# This is a simplified version - the full implementation would need to be translated
# from the original French code which is much more complex


def smart_title_case(text):
    """
    Convert text to title case while respecting apostrophes
    """
    if not text:
        return text
    
    # Split by spaces
    words = text.split()
    result = []
    
    for word in words:
        if not word:
            continue
            
        # Handle words with apostrophes
        if "'" in word:
            # Split by apostrophe and capitalize each part
            parts = word.split("'")
            capitalized_parts = []
            for i, part in enumerate(parts):
                if part:  # Only capitalize if part is not empty
                    if i == 0:  # First part
                        capitalized_parts.append(part.capitalize())
                    else:  # Parts after apostrophe (like 's, 't, etc.)
                        capitalized_parts.append(part.lower())
            result.append("'".join(capitalized_parts))
        else:
            # Regular word - just capitalize first letter
            result.append(word.capitalize())
    
    return ' '.join(result)

def get_telescope_from_header(header):
    """Extract telescope name from FITS header using standard and common keywords."""
    if header is None:
        return 'Unknown'
    for key in ['TELESCOP', 'TELESCOPE', 'OBSERVAT', 'SCOPE', 'OPTIC', 'TELESCOPE_NAME', 'TELESCOPE-ID', 'OBSERVATORY']:
        try:
            val = header.get(key, '')
            if val is not None and str(val).strip():
                return normalize_telescope_name(str(val).strip())
        except (KeyError, TypeError):
            continue
    return 'Unknown'

def get_instrument_from_header(header):
    """Extract instrument/camera name from FITS header using standard and common keywords."""
    if header is None:
        return 'Unknown'
    for key in ['INSTRUME', 'INSTRUMENT', 'CAMERA', 'DETECTOR', 'CCD-NAME', 'CAMNAME', 'SENSOR', 'DETECTOR-NAME', 'INSTRUMENT-ID']:
        try:
            val = header.get(key, '')
            if val is not None and str(val).strip():
                return str(val).strip()
        except (KeyError, TypeError):
            continue
    return 'Unknown'

def get_equipment_name(telescope, instrument):
    """Single name for equipment: telescope and instrument are the same concept (télescope = lunette = instrument)."""
    t = (telescope or '').strip()
    i = (instrument or '').strip()
    if t and t.upper() != 'UNKNOWN':
        return t
    if i and i.upper() != 'UNKNOWN':
        return i
    return 'Unknown'

def normalize_telescope_name(telescope_name):
    """
    Normalize telescope name: replace technical descriptions and mount names with 'Unknown'.
    Many FITS headers put the mount (e.g. AM5, CEM40) in TELESCOP; that is a mount, not a telescope.
    """
    if not telescope_name or telescope_name.strip() == '' or telescope_name.strip() == 'Unknown':
        return 'Unknown'
    
    telescope = telescope_name.strip()
    telescope_upper = telescope.upper()
    
    # Known mount identifiers (mounts, not telescopes) -> treat as Unknown
    mount_indicators = [
        'AM5', 'AM3', 'CEM40', 'CEM26', 'CEM25', 'CEM70', 'iOptron',
        'EQ6', 'EQ8', 'EQ5', 'EQ3', 'HEQ5', 'NEQ6', 'EQ6-R', 'EQ8-R',
        'SkyWatcher', 'AZEQ6', 'AZ-EQ6', 'AVX', 'CGEM', 'CGX', 'NexStar',
        'Losmandy', 'G11', 'G8', '10Micron', 'Paramount', 'ZWO AM5', 'ZWO AM3',
    ]
    for mount in mount_indicators:
        if mount.upper() in telescope_upper or telescope_upper == mount.upper():
            return 'Unknown'
    
    technical_indicators = [
        '->', 'driver', 'connected', 'through', 'for telescope', 'telescope connected',
        'driver for', 'connected through', 'ACP->', 'DRIVER FOR', 'CONNECTED THROUGH', 'ACP->DRIVER'
    ]
    for indicator in technical_indicators:
        if indicator.upper() in telescope_upper:
            return 'Unknown'
    
    if len(telescope) > 50:
        return 'Unknown'
    
    problematic_chars = ['->', '(', ')', '[', ']', '{', '}', '|', '\\', '/', ':', ';', '=', '*', '&', '%', '$', '#', '@', '!', '?', '<', '>']
    problematic_count = sum(1 for char in telescope if char in problematic_chars)
    if problematic_count > 2 or any(phrase in telescope_upper for phrase in ['DRIVER', 'CONNECTED', 'THROUGH', 'FOR TELESCOPE']):
        return 'Unknown'
    
    return telescope


def get_platform_info():
    """Get detailed platform information for compatibility"""
    import platform
    import sys
    import os
    import shutil
    
    system = platform.system().lower()
    machine = platform.machine().lower()
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    # Detect architecture
    if 'arm' in machine or 'aarch64' in machine:
        arch = "ARM"
    elif 'x86_64' in machine or 'amd64' in machine:
        arch = "x64"
    elif 'x86' in machine or 'i386' in machine or 'i686' in machine:
        arch = "x86"
    else:
        arch = "Unknown"
    
    # Detect Linux distribution
    linux_distro = "Unknown"
    if system == 'linux':
        try:
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if line.startswith('ID='):
                        linux_distro = line.split('=')[1].strip().strip('"')
                        break
        except (FileNotFoundError, OSError):
            try:
                with open('/etc/issue', 'r') as f:
                    content = f.read().lower()
                    if 'manjaro' in content:
                        linux_distro = 'manjaro'
                    elif 'arch' in content:
                        linux_distro = 'arch'
                    elif 'ubuntu' in content:
                        linux_distro = 'ubuntu'
                    elif 'debian' in content:
                        linux_distro = 'debian'
            except (FileNotFoundError, OSError):
                pass
    
    # Detect Mac variants
    mac_variant = "Unknown"
    if system == 'darwin':
        try:
            # Detect Apple Silicon vs Intel
            import subprocess
            result = subprocess.run(['uname', '-m'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                arch = result.stdout.strip()
                if arch == 'arm64':
                    mac_variant = 'apple_silicon'
                elif arch == 'x86_64':
                    mac_variant = 'intel'
            
            # Detect package managers
            if shutil.which('brew'):
                if mac_variant == 'apple_silicon':
                    mac_variant = 'homebrew_apple_silicon'
                else:
                    mac_variant = 'homebrew_intel'
            elif shutil.which('port'):
                mac_variant = 'macports'
            
            # Detect MacTeX
            if os.path.exists('/Library/TeX/texbin/pdflatex'):
                if mac_variant == 'Unknown':
                    mac_variant = 'mactex'
                else:
                    mac_variant += '_mactex'
            
            # Detect Xcode Command Line Tools
            if os.path.exists('/Library/Developer/CommandLineTools/usr/bin/python3'):
                if mac_variant == 'Unknown':
                    mac_variant = 'xcode_tools'
                else:
                    mac_variant += '_xcode'
                    
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            # Fallback detection
            if os.path.exists('/opt/homebrew/bin/python3'):
                mac_variant = 'apple_silicon'
            elif os.path.exists('/usr/local/bin/python3'):
                mac_variant = 'intel'
            else:
                mac_variant = 'unknown'
    
    # Detect Python and pip paths
    python_paths = {
        'python_executable': sys.executable,
        'python_in_path': shutil.which('python'),
        'python3_in_path': shutil.which('python3'),
        'pip_in_path': shutil.which('pip'),
        'pip3_in_path': shutil.which('pip3')
    }
    
    return {
        'system': system,
        'machine': machine,
        'architecture': arch,
        'python_version': python_version,
        'linux_distro': linux_distro,
        'mac_variant': mac_variant,
        'is_windows': system == 'windows',
        'is_linux': system == 'linux',
        'is_macos': system == 'darwin',
        'is_manjaro': linux_distro == 'manjaro',
        'is_apple_silicon': mac_variant in ['apple_silicon', 'homebrew_apple_silicon'],
        'is_intel_mac': mac_variant in ['intel', 'homebrew_intel'],
        'has_homebrew': 'homebrew' in mac_variant,
        'has_macports': 'macports' in mac_variant,
        'has_mactex': 'mactex' in mac_variant,
        'python_paths': python_paths
    }

def main_cli():
    """Main function for CLI mode (original)"""
    global ADU_ANALYSIS_ENABLED, ADU_SAMPLE_PER_FILTER, FAST_ANALYSIS, BIAS_DARK_PATH, DEFAULT_REGION_SIZE, GENERATE_THUMBNAILS
    
    # Get platform information
    platform_info = get_platform_info()
    
    # Initialize thumbnail generation flag
    GENERATE_THUMBNAILS = False
    
    # Start timing
    import time
    start_time = time.time()
    
    # Display title in detected language
    if SYSTEM_LANGUAGE == 'fr':
        print("ANALYSEUR D'ASTROPHOTOGRAPHIE TÉLESCOPE")
    else:
        print("TELESCOPE ASTROPHOTOGRAPHY ANALYZER")
    print("=" * 80)
    
    # Display platform information for compatibility
    if SYSTEM_LANGUAGE == 'fr':
        print(f"🖥️  {_('platform')}: {platform_info['system'].title()} ({platform_info['architecture']})")
    else:
        print(f"🖥️  {_('platform')}: {platform_info['system'].title()} ({platform_info['architecture']})")
    
    # Ask user about thumbnail generation
    print(f"\n🖼️  {_('thumbnail_generation')}")
    print("=" * 50)
    print(_('thumbnail_question'))
    print(_('thumbnail_info1'))
    print(_('thumbnail_info2'))
    print(_('thumbnail_info3'))
    
    # Note: Console encoding will be handled automatically by Python
    
    # Simple approach: just use input() and let the user decide
    # If they don't respond, the program will wait, but that's better than crashing
    try:
        user_input = input(f"\n{_('thumbnail_prompt')} ").strip().lower()
        
        if user_input in ['y', 'yes', 'o', 'oui']:
            GENERATE_THUMBNAILS = True
            print(f"✅ {_('thumbnail_yes')}")
        else:
            GENERATE_THUMBNAILS = False
            print(f"❌ {_('thumbnail_no')}")
    except (UnicodeDecodeError, KeyboardInterrupt, EOFError):
        # Handle any input errors gracefully
        GENERATE_THUMBNAILS = False
        print(f"❌ {_('thumbnail_no_error')}")
    except Exception:
        # Any other error
        GENERATE_THUMBNAILS = False
        print(f"❌ {_('thumbnail_no_fallback')}")
    
    print("=" * 50)
    if platform_info['is_linux'] and platform_info['linux_distro'] != 'Unknown':
        print(f"🐧 Distribution: {platform_info['linux_distro'].title()}")
    elif platform_info['is_macos'] and platform_info['mac_variant'] != 'Unknown':
        print(f"🍎 Mac Variant: {platform_info['mac_variant'].title()}")
        if platform_info['is_apple_silicon']:
            print(f"🍎 Type: Apple Silicon (M1/M2/M3)")
        elif platform_info['is_intel_mac']:
            print(f"🍎 Type: Intel Mac")
        if platform_info['has_homebrew']:
            print(f"🍺 Homebrew: Detected")
        if platform_info['has_macports']:
            print(f"🍺 MacPorts: Detected")
        if platform_info['has_mactex']:
            print(f"📄 MacTeX: Detected")
    print(f"🐍 Python: {platform_info['python_version']}")
    print(f"🔧 Architecture: {platform_info['machine']}")
    
    # Show Python path information for debugging on Linux and Mac
    if platform_info['is_linux'] or platform_info['is_macos']:
        print(f"🔍 Python detected: {platform_info['python_paths']['python_executable']}")
        if platform_info['python_paths']['python3_in_path']:
            print(f"🔍 Python3 in PATH: {platform_info['python_paths']['python3_in_path']}")
        if platform_info['python_paths']['pip3_in_path']:
            print(f"🔍 Pip3 in PATH: {platform_info['python_paths']['pip3_in_path']}")
        
        # Show LaTeX detection
        latex_exe = find_latex_executable()
        if latex_exe:
            print(f"🔍 LaTeX detected: {latex_exe}")
        else:
            print("⚠️  LaTeX not detected - PDF report not available")
    
    print("-" * 80)
    
    # Parse arguments first
    args = parse_args()
    
    # Auto-detect CPU cores if workers not specified
    if args.workers is None:
        import multiprocessing
        
        # Get system information with robust error handling
        try:
            cpu_count = multiprocessing.cpu_count()
            if cpu_count <= 0:
                cpu_count = 1  # Fallback for invalid CPU count
        except (OSError, NotImplementedError):
            # Fallback for systems where CPU count detection fails
            cpu_count = 1
        
        # Try to get memory info, fallback to CPU-based estimation
        try:
            import psutil
            memory_gb = psutil.virtual_memory().total / (1024**3)
            memory_available = True
        except (ImportError, OSError, AttributeError):
            # Fallback: estimate memory based on CPU count and platform
            import platform
            system = platform.system().lower()
            if system == "windows":
                memory_gb = cpu_count * 2  # Conservative estimate for Windows
            elif system == "darwin":  # macOS
                memory_gb = cpu_count * 4  # macOS typically has more memory
            else:  # Linux and others
                memory_gb = cpu_count * 3  # Linux estimate
            memory_available = False
        
        # Detect storage type (HDD vs SSD) for optimal worker selection
        # Use the folder path if available, otherwise detect system disk
        if args.folder:
            folder = Path(args.folder).resolve()
            is_ssd, storage_info = detect_storage_type(folder)
        else:
            # Fallback to system disk detection if no folder specified yet
            is_ssd = True
            storage_info = "SSD (assumed - no folder specified)"
        
        # Intelligent worker selection based on system capabilities and storage type
        if cpu_count >= 16 and memory_gb >= 16:
            # High-end system: use all cores for SSD, limit for HDD
            if is_ssd:
                args.workers = cpu_count
            else:
                args.workers = max(4, min(8, cpu_count // 2))  # Limit for HDD
            system_type = "High-end"
        elif cpu_count >= 8 and memory_gb >= 8:
            # Mid-range system: use 75% of cores for SSD, 50% for HDD
            if is_ssd:
                args.workers = max(4, int(cpu_count * 0.75))
            else:
                args.workers = max(2, int(cpu_count * 0.5))
            system_type = "Mid-range"
        elif cpu_count >= 4 and memory_gb >= 4:
            # Entry-level system: use 50% of cores for SSD, 25% for HDD
            if is_ssd:
                args.workers = max(2, int(cpu_count * 0.5))
            else:
                args.workers = max(1, int(cpu_count * 0.25))
            system_type = "Entry-level"
        else:
            # Low-end system: use 1-2 cores maximum
            args.workers = min(2, cpu_count)
            system_type = "Low-end"
        
        memory_info = f"{memory_gb:.1f}GB RAM" if memory_available else "RAM (estimated)"
        print(f"🧵 Auto-detected {cpu_count} CPU cores, {memory_info}, {storage_info} ({system_type} system)")
        print(f"   📊 Optimal workers: {args.workers} (auto-optimized for your system)")
        
        # Additional recommendations
        if system_type == "Low-end":
            print("   💡 Tip: Consider using --workers 1 for better stability on low-end systems")
        elif system_type == "High-end":
            print("   💡 Tip: Your system can handle maximum performance with all cores")
        elif not memory_available:
            print("   💡 Tip: Install psutil for more accurate memory detection: pip install psutil")
    
    # Check Python packages at startup
    print("🔍 Checking Python packages...")
    
    # Run platform-specific diagnostic if needed
    if platform_info['is_linux']:
        diagnose_linux_distribution_issues(platform_info)
    elif platform_info['is_macos']:
        diagnose_mac_variants_issues(platform_info)
    
    if args.auto_install:
        print("🤖 Auto-install mode enabled")
        if not install_python_packages_automatically():
            print("⚠️  Some packages could not be installed automatically")
            print("   Please install them manually or run without --auto-install")
            if platform_info['is_manjaro']:
                print("\n💡 Manjaro-specific solutions:")
                print("   sudo pacman -S python python-pip")
                print("   sudo pacman -S python-astropy python-matplotlib python-pillow")
                print("   sudo pacman -S python-requests python-tqdm")
    else:
        suggest_python_installation()
    print()
    print("Recursive FITS folder analysis")
    print("Target separation and detailed statistics")
    print("Observed sky regions analysis")
    print("=" * 80)
    
    if not ASTROPY_AVAILABLE:
        print("ERROR: Astropy is not installed. Cannot continue.")
        print("   Install with: pip install astropy")
        return
    
    # CLI Args
    args = parse_args()
    
    # Random seed
    if args.seed is not None:
        try:
            np.random.seed(args.seed)
            print(f"Random seed set: {args.seed}")
        except Exception as e:
            print(f"WARNING: Cannot set seed: {e}")

    # Load existing configuration
    print("Loading configuration...")
    loaded_config = load_config()

    # Analysis folder (cross-platform path handling)
    script_dir = Path(__file__).resolve().parent
    if args.folder:
        # Handle both relative and absolute paths
        folder = Path(args.folder).resolve()
    else:
        folder = script_dir
    print(f"Analysis folder: {folder}")
    if not folder.exists():
        print(f"ERROR: Analysis folder does not exist: {folder}")
        if platform_info['is_windows']:
            print("💡 Windows: Enclose paths in quotes, e.g. --folder \"C:\\Path\\To\\Your\\Folder\"")
        elif platform_info['is_linux']:
            print("💡 Linux: Use forward slashes, e.g. --folder \"/home/username/astro\"")
        elif platform_info['is_macos']:
            print("💡 macOS: Use forward slashes, e.g. --folder \"/Users/username/astro\"")
        return
    if not folder.is_dir():
        print(f"ERROR: Analysis folder is not a directory: {folder}")
        return
    

    # SNR region size
    DEFAULT_REGION_SIZE = max(16, int(args.region_size))

    # Force Mode 1 only
    global ADU_ANALYSIS_ENABLED, FAST_ANALYSIS, ADU_SAMPLE_PER_FILTER
    
    # Force Mode 1: Fast analysis
    ADU_ANALYSIS_ENABLED = False
    FAST_ANALYSIS = True
    ADU_SAMPLE_PER_FILTER = 3
    
    print(f"\nSTARTING ANALYSIS")
    print("=" * 80)
    
    # Create output folder at the ROOT of the analyzed folder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_folder_name = f"astronomical_analysis_{timestamp}"
    output_folder = os.path.join(str(folder), output_folder_name)
    os.makedirs(output_folder, exist_ok=True)
    print(f"📁 Output folder: {output_folder}")
    
    try:
        # Analyze FITS files
        print("🔍 Starting FITS analysis...")
        try:
            data_by_target, global_data = analyze_folder_recursive(str(folder), args.workers)
        except Exception as e:
            print(f"❌ Error during FITS analysis: {e}")
            import traceback
            traceback.print_exc()
            return
        
        if not data_by_target:
            # No LIGHT files - still proceed with storage optimization if requested
            files_after_dedup = global_data.get('files_after_dedup', 0)
            
            if args.optimize_storage and files_after_dedup > 0:
                if SYSTEM_LANGUAGE == 'fr':
                    print(f"\nℹ️  Aucun fichier LIGHT trouvé parmi {files_after_dedup} fichier(s).")
                    print("   Poursuite de l'optimisation du stockage (tous types de fichiers)...")
                else:
                    print(f"\nℹ️  No LIGHT files found among {files_after_dedup} file(s).")
                    print("   Proceeding with storage optimization (all file types)...")
                
                optimize_storage(
                    str(folder),
                    args.optimize_storage,
                    prefer_format=args.prefer_format,
                    compress_fits=not args.no_compress,
                    workers=args.workers or 1
                )
            else:
                if files_after_dedup > 0:
                    if SYSTEM_LANGUAGE == 'fr':
                        print(f"ℹ️  Aucun fichier LIGHT trouvé parmi {files_after_dedup} fichier(s) (tous calibrations).")
                        print("   Utilisez --optimize-storage DOSSIER pour optimiser le stockage de tous les types.")
                    else:
                        print(f"ℹ️  No LIGHT files found among {files_after_dedup} file(s) (all calibration).")
                        print("   Use --optimize-storage FOLDER to optimize storage for all file types.")
                else:
                    print("❌ No FITS/XISF files found")
            return
        
        # Group normalized targets (e.g., LMC and lmc)
        print("🔗 Grouping normalized targets...")
        original_count = len(data_by_target)
        data_by_target = group_normalized_targets(data_by_target)
        normalized_count = len(data_by_target)
        
        if original_count != normalized_count:
            print(f"   📊 Target normalization: {original_count} → {normalized_count} targets")
            # Show which targets were grouped
            for target_name, target_data in data_by_target.items():
                if 'original_names' in target_data and len(target_data['original_names']) > 1:
                    print(f"   🔗 Grouped: {', '.join(target_data['original_names'])} → {target_name}")
        
        # Optional: resolve targets via SIMBAD and merge duplicates (e.g. M31 = NGC 224)
        if getattr(args, 'resolve_simbad', False):
            if SIMBAD_AVAILABLE:
                print("🔍 Resolving targets via SIMBAD (merge duplicate catalog names)...")
                unique_names = list(data_by_target.keys())
                name_to_canonical, canonical_to_info = query_simbad_for_targets(unique_names)
                if name_to_canonical:
                    before = len(data_by_target)
                    data_by_target = merge_targets_by_simbad(data_by_target, name_to_canonical, canonical_to_info)
                    after = len(data_by_target)
                    if before != after:
                        print(f"   📊 SIMBAD merge: {before} → {after} targets")
                    for tname, tdata in data_by_target.items():
                        if 'simbad_info' in tdata and tdata.get('original_names'):
                            info = tdata['simbad_info']
                            otype = format_simbad_otype(info.get('otype') or '') or '—'
                            ids_preview = ', '.join(info.get('all_ids', [])[:5])
                            if len(info.get('all_ids', [])) > 5:
                                ids_preview += ', ...'
                            print(f"   🌐 {tname}: type={otype} | ids: {ids_preview}")
            else:
                print("   ⚠️ astroquery not installed. Install with: pip install astroquery")
        
        # Group mosaic panels
        print("🔗 Grouping mosaic panels...")
        mosaic_original_count = len(data_by_target)
        data_by_target = group_mosaic_panels(data_by_target)
        grouped_count = len(data_by_target)
        
        if mosaic_original_count != grouped_count:
            print(f"   📊 Mosaic grouping: {mosaic_original_count} → {grouped_count} targets")
            mosaic_targets = [name for name, data in data_by_target.items() if 'panels' in data]
            if mosaic_targets:
                print(f"   🧩 Mosaic targets found: {', '.join(mosaic_targets)}")
        
        # Display results
        display_target_statistics(data_by_target)
        
        # Generate outputs
        if not args.no_graphs:
            generate_graphs(data_by_target, global_data, output_folder)
        
        if not args.no_latex:
            generate_latex_report(data_by_target, global_data, output_folder)
            # Always generate HTML report alongside LaTeX
            generate_html_report(data_by_target, global_data, output_folder)
        
        if args.export_csv:
            export_csv(data_by_target, global_data, output_folder)
        
        if args.zip_output:
            compress_output_folder(output_folder)
        
        # Storage optimization (if requested via CLI)
        if args.optimize_storage:
            optimize_storage(
                str(folder),
                args.optimize_storage,
                prefer_format=args.prefer_format,
                compress_fits=not args.no_compress,
                workers=args.workers or 1
            )
        
        # Calculate execution time and performance statistics
        end_time = time.time()
        total_time = end_time - start_time
        
        # Get total files processed
        total_files = global_data.get('total_files', 0)
        
        # Calculate files per second
        if total_time > 0:
            files_per_second = total_files / total_time
        else:
            files_per_second = 0
        
        # Format time display
        hours = int(total_time // 3600)
        minutes = int((total_time % 3600) // 60)
        seconds = int(total_time % 60)
        
        if hours > 0:
            time_str = f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            time_str = f"{minutes}m {seconds}s"
        else:
            time_str = f"{seconds}s"
        
        print(f"\n✅ Analysis completed successfully!")
        print(f"📁 Results saved in: {output_folder}")
        
        # Enhanced performance statistics with more prominent execution time
        print(f"\n" + "=" * 80)
        print(f"⏱️  TOTAL PROGRAM EXECUTION TIME: {time_str}")
        print(f"=" * 80)
        
        print(f"\n📊 DETAILED PERFORMANCE STATISTICS")
        print(f"=" * 50)
        print(f"📁 Total FITS files processed: {total_files:,}")
        print(f"⚡ Average processing speed: {files_per_second:.2f} files/second")
        print(f"📈 Efficiency: {files_per_second:.1f} files per second")
        
        # Display file type statistics
        file_types = global_data.get('file_types', {})
        if file_types and any(file_types.values()):
            print(f"\n📋 STATISTIQUES PAR TYPE DE FICHIER:")
            print(f"=" * 50)
            if file_types.get('fits', 0) > 0:
                print(f"   📄 .fits: {file_types['fits']:,} fichier(s)")
            if file_types.get('fit', 0) > 0:
                print(f"   📄 .fit: {file_types['fit']:,} fichier(s)")
            if file_types.get('fits.fz', 0) > 0:
                print(f"   📦 .fits.fz: {file_types['fits.fz']:,} fichier(s)")
            if file_types.get('xisf', 0) > 0:
                print(f"   📄 .xisf: {file_types['xisf']:,} fichier(s)")
            if file_types.get('xifs', 0) > 0:
                print(f"   📄 .xifs: {file_types['xifs']:,} fichier(s)")
            if file_types.get('xif', 0) > 0:
                print(f"   📄 .xif: {file_types['xif']:,} fichier(s)")
            
            # Verify total matches
            total_by_type = sum(file_types.values())
            if total_by_type != total_files:
                print(f"   ⚠️  Note: Total par type ({total_by_type:,}) ≠ Total traité ({total_files:,})")
            else:
                print(f"   ✓ Total vérifié: {total_by_type:,} fichier(s)")
        
        # Enhanced performance rating with more details
        if files_per_second >= 1000:
            rating = "🚀 Excellent"
            rating_desc = "Exceptional performance"
        elif files_per_second >= 500:
            rating = "⚡ Very Good"
            rating_desc = "Very satisfactory performance"
        elif files_per_second >= 100:
            rating = "✅ Good"
            rating_desc = "Correct performance"
        else:
            rating = "🐌 Slow"
            rating_desc = "Slow performance"
        
        print(f"🏆 Performance evaluation: {rating} - {rating_desc}")
        print(f"📊 Summary: {total_files:,} files processed in {time_str} ({files_per_second:.2f} files/second)")
        print(f"=" * 50)
        
    except KeyboardInterrupt:
        print(f"\n⚠️  Analysis interrupted by user")
    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Check if the error is related to missing Python packages
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ['no module named', 'import', 'module not found', 'package', 'pip']):
            print("\n" + "="*80)
            print("🔧 PYTHON PACKAGE ERROR DETECTED")
            print("="*80)
            print("The error appears to be related to missing Python packages.")
            print("This can happen due to:")
            print("• Incompatible Python version (some packages don't support newer versions)")
            print("• Missing required packages")
            print("• Package installation failure")
            print("\n💡 SOLUTIONS:")
            print("1. Try running with --auto-install flag:")
            print("   python script.py --auto-install")
            print("2. Install packages manually:")
            print("   python -m pip install matplotlib numpy pandas reportlab tqdm astropy pillow scipy requests")
            print("3. If using Python 3.13+, try with Python 3.12:")
            print("   • Download Python 3.12 from https://www.python.org/downloads/")
            print("   • Or use a virtual environment with Python 3.12")
            print("4. Check your Python installation and pip configuration")
            print("="*80)

def smart_title_case(text):
    """
    Convert text to title case while respecting apostrophes
    """
    if not text:
        return text
    
    # Split by spaces
    words = text.split()
    result = []
    
    for word in words:
        if not word:
            continue
            
        # Handle words with apostrophes
        if "'" in word:
            # Split by apostrophe and capitalize each part
            parts = word.split("'")
            capitalized_parts = []
            for i, part in enumerate(parts):
                if part:  # Only capitalize if part is not empty
                    if i == 0:  # First part
                        capitalized_parts.append(part.capitalize())
                    else:  # Parts after apostrophe (like 's, 't, etc.)
                        capitalized_parts.append(part.lower())
            result.append("'".join(capitalized_parts))
        else:
            # Regular word - just capitalize first letter
            result.append(word.capitalize())
    
    return ' '.join(result)

def normalize_target_name(target_name):
    """
    Normalize target name with special handling for astronomical catalogs and object names
    """
    if not target_name or target_name.strip() == '' or target_name.strip() == 'Unknown':
        return 'Unknown'
    
    target = target_name.strip()
    target_upper = target.upper()

    # Preserve Solar System object names exactly (avoid catalog normalization like "M oon")
    solar_system_objects = {
        # Star
        'SUN': 'Sun', 'SOL': 'Sun', 'SOLEIL': 'Sun',  # SOLEIL = Sun (French)
        # Planets
        'MERCURY': 'Mercury', 'MERCURE': 'Mercury',  # MERCURE = Mercury (French)
        'VENUS': 'Venus',
        'EARTH': 'Earth', 'TERRE': 'Earth',  # TERRE = Earth (French)
        'MARS': 'Mars', 'JUPITER': 'Jupiter', 'SATURN': 'Saturn', 'SATURNE': 'Saturn',  # SATURNE = Saturn (French)
        'URANUS': 'Uranus', 'NEPTUNE': 'Neptune', 'NEPTUN': 'Neptune',  # NEPTUN = Neptune (German/other)
        # Earth Moon
        'MOON': 'Moon', 'LUNA': 'Moon', 'LUNE': 'Moon',  # LUNE = Moon (French)
        # Dwarf planets
        'PLUTO': 'Pluto', 'CERES': 'Ceres', 'ERIS': 'Eris',
        'HAUMEA': 'Haumea', 'MAKEMAKE': 'Makemake',
        # Mars moons
        'PHOBOS': 'Phobos', 'DEIMOS': 'Deimos',
        # Jupiter moons (Galilean + common)
        'IO': 'Io', 'EUROPA': 'Europa', 'GANYMEDE': 'Ganymede', 'CALLISTO': 'Callisto',
        'AMALTHEA': 'Amalthea', 'THEBE': 'Thebe', 'METIS': 'Metis', 'ADRASTEA': 'Adrastea',
        'HIMALIA': 'Himalia', 'ELARA': 'Elara', 'LEDA': 'Leda', 'LYSITHEA': 'Lysithea',
        'ANANKE': 'Ananke', 'CARME': 'Carme', 'PASIPHAE': 'Pasiphae', 'SINOPE': 'Sinope',
        # Saturn moons (major)
        'TITAN': 'Titan', 'RHEA': 'Rhea', 'IAPETUS': 'Iapetus', 'DIONE': 'Dione',
        'TETHYS': 'Tethys', 'ENCELADUS': 'Enceladus', 'MIMAS': 'Mimas', 'HYPERION': 'Hyperion', 'PHOEBE': 'Phoebe',
        'ATLAS': 'Atlas', 'PROMETHEUS': 'Prometheus', 'PANDORA': 'Pandora', 'JANUS': 'Janus', 'EPIMETHEUS': 'Epimetheus',
        'HELENE': 'Helene', 'TELESTO': 'Telesto', 'CALYPSO': 'Calypso',
        # Uranus moons (major)
        'MIRANDA': 'Miranda', 'ARIEL': 'Ariel', 'UMBRIEL': 'Umbriel', 'TITANIA': 'Titania', 'OBERON': 'Oberon',
        'PUCK': 'Puck',
        # Neptune moons
        'TRITON': 'Triton', 'NEREID': 'Nereid', 'PROTEUS': 'Proteus', 'LARISSA': 'Larissa', 'DESPINA': 'Despina',
        'GALATEA': 'Galatea', 'THALASSA': 'Thalassa', 'NAIAD': 'Naiad',
        # Pluto system
        'CHARON': 'Charon', 'PLUTO I': 'Charon', 'PLUTO 1': 'Charon',
        'HYDRA': 'Hydra', 'NIX': 'Nix', 'KERBEROS': 'Kerberos', 'STYX': 'Styx',
        'PLUTO II': 'Hydra', 'PLUTO 2': 'Hydra',
        'PLUTO III': 'Nix', 'PLUTO 3': 'Nix',
        'PLUTO IV': 'Kerberos', 'PLUTO 4': 'Kerberos',
        'PLUTO V': 'Styx', 'PLUTO 5': 'Styx',
        # Roman numeral aliases for major moons by primary
        # Earth
        'EARTH I': 'Moon', 'EARTH 1': 'Moon',
        # Mars
        'MARS I': 'Phobos', 'MARS 1': 'Phobos',
        'MARS II': 'Deimos', 'MARS 2': 'Deimos',
        # Jupiter (Galilean)
        'JUPITER I': 'Io', 'JUPITER 1': 'Io',
        'JUPITER II': 'Europa', 'JUPITER 2': 'Europa',
        'JUPITER III': 'Ganymede', 'JUPITER 3': 'Ganymede',
        'JUPITER IV': 'Callisto', 'JUPITER 4': 'Callisto',
        # Saturn (classics)
        'SATURN I': 'Mimas', 'SATURN 1': 'Mimas',
        'SATURN II': 'Enceladus', 'SATURN 2': 'Enceladus',
        'SATURN III': 'Tethys', 'SATURN 3': 'Tethys',
        'SATURN IV': 'Dione', 'SATURN 4': 'Dione',
        'SATURN V': 'Rhea', 'SATURN 5': 'Rhea',
        'SATURN VI': 'Titan', 'SATURN 6': 'Titan',
        'SATURN VII': 'Hyperion', 'SATURN 7': 'Hyperion',
        'SATURN VIII': 'Iapetus', 'SATURN 8': 'Iapetus',
        'SATURN IX': 'Phoebe', 'SATURN 9': 'Phoebe',
        # Uranus (classics)
        'URANUS I': 'Ariel', 'URANUS 1': 'Ariel',
        'URANUS II': 'Umbriel', 'URANUS 2': 'Umbriel',
        'URANUS III': 'Titania', 'URANUS 3': 'Titania',
        'URANUS IV': 'Oberon', 'URANUS 4': 'Oberon',
        'URANUS V': 'Miranda', 'URANUS 5': 'Miranda',
        # Neptune (classics)
        'NEPTUNE I': 'Triton', 'NEPTUNE 1': 'Triton',
        'NEPTUNE II': 'Nereid', 'NEPTUNE 2': 'Nereid',
        # Dwarf planet moons
        'DYSNOMIA': 'Dysnomia',  # Eris
        'HIIAKA': "Hi'iaka", "HII'AKA": "Hi'iaka", 'HII-AKA': "Hi'iaka", 'HII IAKA': "Hi'iaka", 'HIIIAKA': "Hi'iaka",
        'NAMAKA': 'Namaka',      # Haumea
        # Notable asteroids
        'VESTA': 'Vesta', 'PALLAS': 'Pallas', 'HYGEIA': 'Hygiea', 'EROS': 'Eros',
        'ITOKAWA': 'Itokawa', 'BENNU': 'Bennu', 'RYUGU': 'Ryugu', 'PSYCHE': 'Psyche',
        # Famous comets (common names)
        'HALLEY': 'Halley', 'ENCKE': 'Encke', 'HALE BOPP': 'Hale-Bopp', 'HALE-BOPP': 'Hale-Bopp',
        'SHOEMAKER LEVY 9': 'Shoemaker-Levy 9', 'SHOEMAKER-LEVY 9': 'Shoemaker-Levy 9',
        '67P': '67P/Churyumov–Gerasimenko', 'CHURYUMOV GERASIMENKO': '67P/Churyumov–Gerasimenko',
        'C2020 F3': 'C/2020 F3 (NEOWISE)', 'NEOWISE': 'C/2020 F3 (NEOWISE)',
        # Additional famous comets and aliases
        '1P': '1P/Halley', '1P/HALLEY': '1P/Halley',
        '2P': '2P/Encke', '2P/ENCKE': '2P/Encke',
        '9P': '9P/Tempel 1', '9P/TEMPEL 1': '9P/Tempel 1', 'TEMPEL 1': '9P/Tempel 1',
        '12P': '12P/Pons-Brooks', '12P/PONS BROOKS': '12P/Pons-Brooks', 'PONS BROOKS': '12P/Pons-Brooks', 'PONS-BROOKS': '12P/Pons-Brooks',
        '19P': '19P/Borrelly', '19P/BORRELLY': '19P/Borrelly', 'BORRELLY': '19P/Borrelly',
        '21P': '21P/Giacobini-Zinner', '21P/GIACOBINI ZINNER': '21P/Giacobini-Zinner', 'GIACOBINI ZINNER': '21P/Giacobini-Zinner', 'GIACOBINI-ZINNER': '21P/Giacobini-Zinner',
        '26P': '26P/Grigg-Skjellerup', '26P/GRIGG SKJELLERUP': '26P/Grigg-Skjellerup', 'GRIGG SKJELLERUP': '26P/Grigg-Skjellerup', 'GRIGG-SKJELLERUP': '26P/Grigg-Skjellerup',
        '55P': '55P/Tempel-Tuttle', '55P/TEMPEL TUTTLE': '55P/Tempel-Tuttle', 'TEMPEL TUTTLE': '55P/Tempel-Tuttle', 'TEMPEL-TUTTLE': '55P/Tempel-Tuttle',
        '67P': '67P/Churyumov–Gerasimenko', '67P/CHURYUMOV GERASIMENKO': '67P/Churyumov–Gerasimenko', 'CHURYUMOV GERASIMENKO': '67P/Churyumov–Gerasimenko', 'CHURYUMOV-GERASIMENKO': '67P/Churyumov–Gerasimenko',
        '73P': '73P/Schwassmann–Wachmann', '73P/SCHWASSMANN WACHMANN': '73P/Schwassmann–Wachmann', 'SCHWASSMANN WACHMANN': '73P/Schwassmann–Wachmann', 'SCHWASSMANN-WACHMANN': '73P/Schwassmann–Wachmann',
        '81P': '81P/Wild 2', '81P/WILD 2': '81P/Wild 2', 'WILD 2': '81P/Wild 2',
        '96P': '96P/Machholz', '96P/MACHHOLZ': '96P/Machholz', 'MACHHOLZ': '96P/Machholz',
        '103P': '103P/Hartley', '103P/HARTLEY': '103P/Hartley', 'HARTLEY': '103P/Hartley',
        '109P': '109P/Swift-Tuttle', '109P/SWIFT TUTTLE': '109P/Swift-Tuttle', 'SWIFT TUTTLE': '109P/Swift-Tuttle', 'SWIFT-TUTTLE': '109P/Swift-Tuttle',
        'ISON': 'C/2012 S1 (ISON)', 'C2012 S1': 'C/2012 S1 (ISON)', 'C/2012 S1': 'C/2012 S1 (ISON)',
        # Hale-Bopp (MPC designation)
        'C1995 O1': 'C/1995 O1 (Hale-Bopp)', 'C/1995 O1': 'C/1995 O1 (Hale-Bopp)',
        'PANSTARRS': 'C/2011 L4 (PANSTARRS)', 'C2011 L4': 'C/2011 L4 (PANSTARRS)', 'C/2011 L4': 'C/2011 L4 (PANSTARRS)',
        'SIDING SPRING': 'C/2013 A1 (Siding Spring)', 'C2013 A1': 'C/2013 A1 (Siding Spring)', 'C/2013 A1': 'C/2013 A1 (Siding Spring)',
        'CATALINA': 'C/2013 US10 (Catalina)', 'C2013 US10': 'C/2013 US10 (Catalina)', 'C/2013 US10': 'C/2013 US10 (Catalina)',
        'MCNAUGHT': 'C/2006 P1 (McNaught)', 'C2006 P1': 'C/2006 P1 (McNaught)', 'C/2006 P1': 'C/2006 P1 (McNaught)',
        'NEAT': 'C/2001 Q4 (NEAT)', 'C2001 Q4': 'C/2001 Q4 (NEAT)', 'C/2001 Q4': 'C/2001 Q4 (NEAT)',
        'HYAKUTAKE': 'C/1996 B2 (Hyakutake)', 'C1996 B2': 'C/1996 B2 (Hyakutake)', 'C/1996 B2': 'C/1996 B2 (Hyakutake)',
        'OUMUAMUA': "1I/'Oumuamua", "1I": "1I/'Oumuamua", "1I/‘OUMUAMUA": "1I/'Oumuamua",
        '2I': '2I/Borisov', 'BORISOV': '2I/Borisov'
    }
    # Preserve well-known artificial satellites/spacecraft as-is
    artificial_space_objects = {
        'JWST': 'JWST', 'JAMES WEBB': 'JWST', 'JAMES WEBB SPACE TELESCOPE': 'JWST',
        'HUBBLE': 'Hubble', 'HST': 'Hubble',
        'ISS': 'ISS', 'INTERNATIONAL SPACE STATION': 'ISS',
        'TIANGONG': 'Tiangong', 'CHINESE SPACE STATION': 'Tiangong', 'CSS': 'Tiangong',
        'SKYLAB': 'Skylab', 'MIR': 'Mir',
        'SPUTNIK': 'Sputnik', 'SPUTNIK 1': 'Sputnik 1', 'SPUTNIK-1': 'Sputnik 1',
        'VOYAGER 1': 'Voyager 1', 'VOYAGER-1': 'Voyager 1', 'VOYAGER1': 'Voyager 1',
        'VOYAGER 2': 'Voyager 2', 'VOYAGER-2': 'Voyager 2', 'VOYAGER2': 'Voyager 2',
        'CASSINI': 'Cassini', 'JUNO': 'Juno', 'NEW HORIZONS': 'New Horizons',
        'ROSETTA': 'Rosetta', 'PHILAE': 'Philae',
    }
    if target_upper in artificial_space_objects:
        return artificial_space_objects[target_upper]
    if target_upper in solar_system_objects:
        return solar_system_objects[target_upper]
    
    # List of astronomical catalogs that should be in uppercase
    # Note: Single letters like 'C' are only catalogs if followed by a number
    catalogs = [
        'NGC', 'IC', 'ARP', 'M', 'MESSIER', 'BARNARD', 'LDN', 'LBN',
        'RCW', 'GUM', 'VDB', 'VAN DEN BERGH', 'LBN', 'LDN', 'LBN',
        'PK', 'PN', 'PLANETARY', 'OC', 'OPEN CLUSTER', 'GC', 'GLOBULAR', 'GC', 'GLOBULAR',
        'UGC', 'PGC', 'ESO', 'MCG', 'IRAS', '2MASS', 'WISE', 'SDSS', 'HIP', 'TYC',
        'HD', 'HR', 'SAO', 'BD', 'CD', 'CP', 'GJ', 'GL', 'GJ', 'GLIESE', 'LHS', 'LTT',
        'NLTT', 'LP', 'LPM', 'LTT', 'NLTT', 'LP', 'LPM', 'LTT', 'NLTT', 'LP', 'LPM'
    ]
    
    # Special catalogs that need custom handling (handled by specific functions)
    special_catalogs = ['SH2', 'SHARPLESS']
    
    # Special handling for single letter catalogs that need number validation
    single_letter_catalogs = ['B', 'C']
    
    # Check if target starts with a catalog name
    
    # Skip special catalogs that are handled by specific functions
    for special_catalog in special_catalogs:
        if target_upper.startswith(special_catalog):
            # Let the specific function handle this catalog
            break
    else:
        # Only process if it's not a special catalog
        for catalog in catalogs:
            if target_upper.startswith(catalog):
                # Extract the catalog part and number/name part
                catalog_part = catalog.upper()
                
                # Remove the catalog name from the beginning
                remaining = target[len(catalog):].strip()
                
                # For catalogues, extract only the number part (ignore additional words)
                import re
                if catalog in ['M', 'NGC', 'IC', 'ARP']:
                    # Extract only the number part (digits and letters like M 31A, NGC 211A)
                    number_match = re.match(r'^[_\s\-\.]*(\d+[A-Za-z]*)', remaining)
                    if number_match:
                        number_part = number_match.group(1)
                        return f"{catalog_part} {number_part}"
                    else:
                        # If no number found, try to extract any digits
                        digits_match = re.search(r'\d+', remaining)
                        if digits_match:
                            return f"{catalog_part} {digits_match.group()}"
                        else:
                            # No digits at all: this is not a catalog reference (e.g., "Moon")
                            # Return the original target unmodified to avoid outputs like "M oon"
                            return target
                else:
                    # For other catalogs, keep the full remaining part
                    return f"{catalog_part} {remaining}"
    
    # Check for single letter catalogs that need number validation
    for catalog in single_letter_catalogs:
        if target_upper.startswith(catalog):
            # Check if single letter is followed by a number (like B144, C14, etc.)
            remaining = target[1:].strip()
            import re
            if re.match(r'^\d', remaining):
                # It's a catalog entry - normalize the number part
                catalog_part = catalog.upper()
                # Extract just the number part, removing any extra spaces
                number_match = re.match(r'^(\d+)', remaining)
                if number_match:
                    number_part = number_match.group(1)
                    return f"{catalog_part} {number_part}"
                else:
                    return f"{catalog_part} {remaining}"
            else:
                # Not a catalog entry, continue to normal processing
                break
    
    # Check for common astronomical abbreviations
    target_upper = target.upper()
    
    # Magellanic Clouds
    if target_upper in ['LMC', 'LARGE MAGELLANIC CLOUD', 'LARGE MAGELLANIC', 'ESO056-G115', 'ESO 056-G115']:
        return 'Large Magellanic Cloud (LMC)'
    elif target_upper in ['SMC', 'SMALL MAGELLANIC CLOUD', 'SMALL MAGELLANIC']:
        return 'Small Magellanic Cloud (SMC)'
    
    # Common astronomical objects with catalog numbers
    elif target_upper in ['MW', 'MILKY WAY', 'MILKY WAY GALAXY']:
        return 'Milky Way'
    elif target_upper in ['ANDROMEDA', 'ANDROMEDA GALAXY', 'ANDROMEDA NEBULA', 'M31', 'M 31', 'NGC224', 'NGC 224']:
        return 'M 31 (Andromeda Galaxy)'
    elif target_upper in ['TRIANGULUM', 'TRIANGULUM GALAXY', 'TRIANGULUM NEBULA', 'M33', 'M 33', 'NGC598', 'NGC 598']:
        return 'M 33 (Triangulum Galaxy)'
    elif target_upper in ['WHIRLPOOL', 'WHIRLPOOL GALAXY', 'M51', 'M 51', 'NGC5194', 'NGC 5194']:
        return 'M 51 (Whirlpool Galaxy)'
    elif target_upper in ['SOMBRERO', 'SOMBRERO GALAXY', 'M104', 'M 104', 'NGC4594', 'NGC 4594']:
        return 'M 104 (Sombrero Galaxy)'
    elif target_upper in ['PINWHEEL', 'PINWHEEL GALAXY', 'M101', 'M 101', 'NGC5457', 'NGC 5457']:
        return 'M 101 (Pinwheel Galaxy)'
    elif target_upper in ['BLACK EYE', 'BLACK EYE GALAXY', 'M64', 'M 64', 'NGC4826', 'NGC 4826']:
        return 'M 64 (Black Eye Galaxy)'
    elif target_upper in ['SUNFLOWER', 'SUNFLOWER GALAXY', 'M63', 'M 63', 'NGC5055', 'NGC 5055']:
        return 'M 63 (Sunflower Galaxy)'
    elif target_upper in ['CIGAR', 'CIGAR GALAXY', 'M82', 'M 82', 'NGC3034', 'NGC 3034']:
        return 'M 82 (Cigar Galaxy)'
    elif target_upper in ['BODES', 'BODES GALAXY', 'M81', 'M 81', 'NGC3031', 'NGC 3031']:
        return 'M 81 (Bode\'s Galaxy)'
    elif target_upper in ['CARTWHEEL', 'CARTWHEEL GALAXY']:
        return 'Cartwheel Galaxy'
    elif target_upper in ['ANTENNAE', 'ANTENNAE GALAXIES', 'NGC4038', 'NGC 4038', 'NGC4039', 'NGC 4039']:
        return 'NGC 4038/4039 (Antennae Galaxies)'
    elif target_upper in ['MICE', 'MICE GALAXIES', 'NGC4676', 'NGC 4676']:
        return 'NGC 4676 (Mice Galaxies)'
    elif target_upper in ['TADPOLE', 'TADPOLE GALAXY', 'UGC10214', 'UGC 10214']:
        return 'UGC 10214 (Tadpole Galaxy)'
    elif target_upper in ['BUTTERFLY', 'BUTTERFLY GALAXY']:
        return 'Butterfly Galaxy'
    
    # Messier objects with common names
    elif target_upper in ['CRAB', 'CRAB NEBULA', 'M1', 'M 1', 'NGC1952', 'NGC 1952']:
        return 'M 1 (Crab Nebula)'
    elif target_upper in ['ORION', 'ORION NEBULA', 'M42', 'M 42', 'NGC1976', 'NGC 1976']:
        return 'M 42 (Orion Nebula)'
    elif target_upper in ['PLEIADES', 'PLEIADES CLUSTER', 'M45', 'M 45']:
        return 'M 45 (Pleiades)'
    elif target_upper in ['BEEHIVE', 'BEEHIVE CLUSTER', 'M44', 'M 44', 'NGC2632', 'NGC 2632']:
        return 'M 44 (Beehive Cluster)'
    elif target_upper in ['LAGOON', 'LAGOON NEBULA', 'M8', 'M 8', 'NGC6523', 'NGC 6523']:
        return 'M 8 (Lagoon Nebula)'
    elif target_upper in ['TRIFID', 'TRIFID NEBULA', 'M20', 'M 20', 'NGC6514', 'NGC 6514']:
        return 'M 20 (Trifid Nebula)'
    elif target_upper in ['EAGLE', 'EAGLE NEBULA', 'M16', 'M 16', 'NGC6611', 'NGC 6611']:
        return 'M 16 (Eagle Nebula)'
    elif target_upper in ['OMEGA', 'OMEGA NEBULA', 'M17', 'M 17', 'NGC6618', 'NGC 6618']:
        return 'M 17 (Omega Nebula)'
    elif target_upper in ['HORSEHEAD', 'HORSEHEAD NEBULA', 'IC434', 'IC 434']:
        return 'IC 434 (Horsehead Nebula)'
    elif target_upper in ['FLAMING STAR', 'FLAMING STAR NEBULA', 'IC405', 'IC 405', 'FLAMING STAR (IC 405)', 'FLAMING STAR NEBULA (IC 405)']:
        return 'IC 405 (Flaming Star Nebula)'
    elif target_upper in ['WITCH HEAD', 'WITCH HEAD NEBULA', 'IC2118', 'IC 2118']:
        return 'IC 2118 (Witch Head Nebula)'
    elif target_upper in ['ROSETTE', 'ROSETTE NEBULA', 'NGC2237', 'NGC 2237', 'NGC2238', 'NGC 2238', 'NGC2239', 'NGC 2239', 'NGC2246', 'NGC 2246']:
        return 'NGC 2237 (Rosette Nebula)'
    elif target_upper in ['VEIL', 'VEIL NEBULA', 'NGC6960', 'NGC 6960', 'NGC6979', 'NGC 6979', 'NGC6992', 'NGC 6992', 'NGC6995', 'NGC 6995']:
        return 'NGC 6960 (Veil Nebula)'
    elif target_upper in ['DUMBBELL', 'DUMBBELL NEBULA', 'M27', 'M 27', 'NGC6853', 'NGC 6853']:
        return 'M 27 (Dumbbell Nebula)'
    elif target_upper in ['RING', 'RING NEBULA', 'M57', 'M 57', 'NGC6720', 'NGC 6720']:
        return 'M 57 (Ring Nebula)'
    elif target_upper in ['HELIX', 'HELIX NEBULA', 'NGC7293', 'NGC 7293']:
        return 'NGC 7293 (Helix Nebula)'
    elif target_upper in ['CAT\'S EYE', 'CATS EYE', 'CATS EYE NEBULA', 'NGC6543', 'NGC 6543', 'C6', 'C 6', 'CALDWELL 6']:
        return 'NGC 6543 (Cat\'s Eye Nebula)'
    elif target_upper in ['ESKIMO', 'ESKIMO NEBULA', 'NGC2392', 'NGC 2392']:
        return 'NGC 2392 (Eskimo Nebula)'
    elif target_upper in ['BUTTERFLY', 'BUTTERFLY NEBULA', 'NGC6302', 'NGC 6302']:
        return 'NGC 6302 (Butterfly Nebula)'
    elif target_upper in ['CONE', 'CONE NEBULA', 'NGC2264', 'NGC 2264']:
        return 'NGC 2264 (Cone Nebula)'
    elif target_upper in ['HOURGLASS', 'HOURGLASS NEBULA', 'NGC3132', 'NGC 3132']:
        return 'NGC 3132 (Hourglass Nebula)'
    elif target_upper in ['SPIROGRAPH', 'SPIROGRAPH NEBULA', 'NGC6537', 'NGC 6537']:
        return 'NGC 6537 (Spirograph Nebula)'
    elif target_upper in ['RED SPIDER', 'RED SPIDER NEBULA', 'NGC6537', 'NGC 6537']:
        return 'NGC 6537 (Red Spider Nebula)'
    elif target_upper in ['BLUE RACQUETBALL', 'BLUE RACQUETBALL NEBULA', 'NGC6572', 'NGC 6572']:
        return 'NGC 6572 (Blue Racquetball Nebula)'
    elif target_upper in ['JEWEL BOX', 'JEWEL BOX CLUSTER', 'NGC4755', 'NGC 4755']:
        return 'NGC 4755 (Jewel Box Cluster)'
    elif target_upper in ['DOUBLE CLUSTER', 'NGC869', 'NGC 869', 'NGC884', 'NGC 884']:
        return 'NGC 869/884 (Double Cluster)'
    elif target_upper in ['WILD DUCK', 'WILD DUCK CLUSTER', 'M11', 'M 11', 'NGC6705', 'NGC 6705']:
        return 'M 11 (Wild Duck Cluster)'
    elif target_upper in ['BUTTERFLY', 'BUTTERFLY CLUSTER', 'M6', 'M 6', 'NGC6405', 'NGC 6405']:
        return 'M 6 (Butterfly Cluster)'
    elif target_upper in ['SCORPION', 'SCORPION CLUSTER', 'M7', 'M 7', 'NGC6475', 'NGC 6475']:
        return 'M 7 (Scorpion Cluster)'
    # Additional famous objects
    elif target_upper in ['CARINA', 'CARINA NEBULA', 'NGC3372', 'NGC 3372']:
        return 'NGC 3372 (Carina Nebula)'
    elif target_upper in ['KEYHOLE', 'KEYHOLE NEBULA', 'NGC3324', 'NGC 3324']:
        return 'NGC 3324 (Keyhole Nebula)'
    elif target_upper in ['HOMUNCULUS', 'HOMUNCULUS NEBULA', 'NGC3372', 'NGC 3372']:
        return 'NGC 3372 (Homunculus Nebula)'
    elif target_upper in ['ETA CARINAE', 'ETA CARINAE NEBULA', 'NGC3372', 'NGC 3372']:
        return 'NGC 3372 (η Carinae Nebula)'
    elif target_upper in ['NORTH AMERICA', 'NORTH AMERICA NEBULA', 'NGC7000', 'NGC 7000']:
        return 'NGC 7000 (North America Nebula)'
    elif target_upper in ['PELICAN', 'PELICAN NEBULA', 'NGC5070', 'NGC 5070']:
        return 'NGC 5070 (Pelican Nebula)'
    elif target_upper in ['ELEPHANT TRUNK', 'ELEPHANT TRUNK NEBULA', 'IC1396', 'IC 1396']:
        return 'IC 1396 (Elephant Trunk Nebula)'
    elif target_upper in ['PILLARS OF CREATION', 'PILLARS OF CREATION NEBULA', 'M16', 'M 16', 'NGC6611', 'NGC 6611']:
        return 'M 16 (Pillars of Creation)'
    elif target_upper in ['TARANTULA', 'TARANTULA NEBULA', 'NGC2070', 'NGC 2070']:
        return 'NGC 2070 (Tarantula Nebula)'
    elif target_upper in ['30 DORADUS', '30 DOR', 'NGC2070', 'NGC 2070']:
        return 'NGC 2070 (30 Doradus)'
    elif target_upper in ['BUBBLE', 'BUBBLE NEBULA', 'NGC7635', 'NGC 7635']:
        return 'NGC 7635 (Bubble Nebula)'
    elif target_upper in ['CRESCENT', 'CRESCENT NEBULA', 'NGC6888', 'NGC 6888']:
        return 'NGC 6888 (Crescent Nebula)'
    elif target_upper in ['COCONUT', 'COCONUT NEBULA', 'NGC246', 'NGC 246']:
        return 'NGC 246 (Coconut Nebula)'
    elif target_upper in ['LITTLE DUMBBELL', 'LITTLE DUMBBELL NEBULA', 'M76', 'M 76', 'NGC650', 'NGC 650']:
        return 'M 76 (Little Dumbbell Nebula)'
    elif target_upper in ['OWL', 'OWL NEBULA', 'M97', 'M 97', 'NGC3587', 'NGC 3587']:
        return 'M 97 (Owl Nebula)'
    elif target_upper in ['BLINKING', 'BLINKING PLANETARY', 'NGC6826', 'NGC 6826']:
        return 'NGC 6826 (Blinking Planetary)'
    elif target_upper in ['BLUE SNOWBALL', 'BLUE SNOWBALL NEBULA', 'NGC7662', 'NGC 7662']:
        return 'NGC 7662 (Blue Snowball Nebula)'
    elif target_upper in ['SATURN', 'SATURN NEBULA', 'NGC7009', 'NGC 7009']:
        return 'NGC 7009 (Saturn Nebula)'
    elif target_upper in ['GHOST OF JUPITER', 'GHOST OF JUPITER NEBULA', 'NGC3242', 'NGC 3242']:
        return 'NGC 3242 (Ghost of Jupiter Nebula)'
    elif target_upper in ['GHOST', 'GHOST NEBULA', 'SH2-136', 'SH2 136', 'VDB141', 'VDB 141', 'VDB-141']:
        return 'Sh2-136 (Ghost Nebula)'
    elif target_upper in ['TURTLE', 'TURTLE NEBULA', 'NGC6210', 'NGC 6210']:
        return 'NGC 6210 (Turtle Nebula)'
    elif target_upper in ['RED RECTANGLE', 'RED RECTANGLE NEBULA', 'HD44179', 'HD 44179']:
        return 'HD 44179 (Red Rectangle Nebula)'
    elif target_upper in ['BOW TIE', 'BOW TIE NEBULA', 'NGC40', 'NGC 40']:
        return 'NGC 40 (Bow Tie Nebula)'
    elif target_upper in ['WESTERLUND', 'WESTERLUND 2', 'NGC3242', 'NGC 3242']:
        return 'NGC 3242 (Westerlund 2)'
    elif target_upper in ['R136', 'R136 CLUSTER', 'NGC2070', 'NGC 2070']:
        return 'NGC 2070 (R136 Cluster)'
    elif target_upper in ['TRAPEZIUM', 'TRAPEZIUM CLUSTER', 'M42', 'M 42', 'NGC1976', 'NGC 1976']:
        return 'M 42 (Trapezium Cluster)'
    elif target_upper in ['BEEHIVE', 'BEEHIVE CLUSTER', 'M44', 'M 44', 'NGC2632', 'NGC 2632']:
        return 'M 44 (Beehive Cluster)'
    elif target_upper in ['PRAESEPE', 'PRAESEPE CLUSTER', 'M44', 'M 44', 'NGC2632', 'NGC 2632']:
        return 'M 44 (Praesepe Cluster)'
    elif target_upper in ['COAT HANGER', 'COAT HANGER CLUSTER', 'BROCCHI\'S CLUSTER', 'CR399', 'CR 399']:
        return 'Cr 399 (Coat Hanger Cluster)'
    elif target_upper in ['DIAMOND RING', 'DIAMOND RING CLUSTER', 'NGC2516', 'NGC 2516']:
        return 'NGC 2516 (Diamond Ring Cluster)'
    elif target_upper in ['SOUTHERN PLEIADES', 'SOUTHERN PLEIADES CLUSTER', 'IC2602', 'IC 2602']:
        return 'IC 2602 (Southern Pleiades)'
    elif target_upper in ['KEESEY', 'KEESEY CLUSTER', 'NGC2422', 'NGC 2422']:
        return 'NGC 2422 (Keesey Cluster)'
    
    # Famous galaxy groups and special objects
    elif target_upper in ['QUINTET', 'STEPHAN\'S QUINTET', 'STEPHANS QUINTET', 'NGC7317', 'NGC 7317', 'NGC7318A', 'NGC 7318A', 'NGC7318B', 'NGC 7318B', 'NGC7319', 'NGC 7319', 'NGC7320', 'NGC 7320']:
        return 'Stephan\'s Quintet (NGC 7317/7318/7319/7320)'
    elif target_upper in ['SQUID', 'SQUID GALAXY', 'CALAMAR', 'CALAMAR GALAXY', 'NGC488', 'NGC 488']:
        return 'NGC 488 (Squid Galaxy)'
    elif target_upper in ['HICKSON', 'HICKSON 44', 'NGC3190', 'NGC 3190', 'NGC3193', 'NGC 3193', 'NGC3187', 'NGC 3187', 'NGC3185', 'NGC 3185']:
        return 'Hickson 44 (NGC 3190/3193/3187/3185)'
    elif target_upper in ['LEO TRIPLET', 'LEO TRIPLET GALAXIES', 'M65', 'M 65', 'NGC3623', 'NGC 3623', 'M66', 'M 66', 'NGC3627', 'NGC 3627', 'NGC3628', 'NGC 3628']:
        return 'Leo Triplet (M 65/66/NGC 3628)'
    elif target_upper in ['VIRGO CLUSTER', 'VIRGO CLUSTER GALAXIES', 'M87', 'M 87', 'NGC4486', 'NGC 4486']:
        return 'M 87 (Virgo Cluster)'
    elif target_upper in ['COMA CLUSTER', 'COMA CLUSTER GALAXIES', 'NGC4889', 'NGC 4889', 'NGC4874', 'NGC 4874']:
        return 'Coma Cluster (NGC 4889/4874)'
    elif target_upper in ['FORNAX CLUSTER', 'FORNAX CLUSTER GALAXIES', 'NGC1399', 'NGC 1399', 'NGC1404', 'NGC 1404']:
        return 'Fornax Cluster (NGC 1399/1404)'
    elif target_upper in ['CENTAURUS A', 'CENTAURUS A GALAXY', 'NGC5128', 'NGC 5128']:
        return 'NGC 5128 (Centaurus A)'
    
    # Famous individual stars
    elif target_upper in ['SIRIUS', 'SIRIUS A', 'ALPHA CANIS MAJORIS', 'ALPHA CMA', 'HD48915', 'HD 48915']:
        return 'Sirius (α Canis Majoris)'
    elif target_upper in ['CANOPUS', 'ALPHA CARINAE', 'ALPHA CAR', 'HD45348', 'HD 45348']:
        return 'Canopus (α Carinae)'
    elif target_upper in ['VEGA', 'ALPHA LYRAE', 'ALPHA LYR', 'HD172167', 'HD 172167']:
        return 'Vega (α Lyrae)'
    elif target_upper in ['CAPELLA', 'ALPHA AURIGAE', 'ALPHA AUR', 'HD34029', 'HD 34029']:
        return 'Capella (α Aurigae)'
    elif target_upper in ['RIGEL', 'BETA ORIONIS', 'BETA ORI', 'HD34085', 'HD 34085']:
        return 'Rigel (β Orionis)'
    elif target_upper in ['PROCYON', 'ALPHA CANIS MINORIS', 'ALPHA CMI', 'HD61421', 'HD 61421']:
        return 'Procyon (α Canis Minoris)'
    elif target_upper in ['BETELGEUSE', 'ALPHA ORIONIS', 'ALPHA ORI', 'HD39801', 'HD 39801']:
        return 'Betelgeuse (α Orionis)'
    elif target_upper in ['ACRUX', 'ALPHA CRUCIS', 'ALPHA CRU', 'HD108248', 'HD 108248']:
        return 'Acrux (α Crucis)'
    elif target_upper in ['HADAR', 'BETA CENTAURI', 'BETA CEN', 'HD121263', 'HD 121263']:
        return 'Hadar (β Centauri)'
    elif target_upper in ['ALTAIR', 'ALPHA AQUILAE', 'ALPHA AQL', 'HD187642', 'HD 187642']:
        return 'Altair (α Aquilae)'
    elif target_upper in ['SPICA', 'ALPHA VIRGINIS', 'ALPHA VIR', 'HD116658', 'HD 116658']:
        return 'Spica (α Virginis)'
    elif target_upper in ['ANTARES', 'ALPHA SCORPII', 'ALPHA SCO', 'HD148478', 'HD 148478']:
        return 'Antares (α Scorpii)'
    elif target_upper in ['POLLUX', 'BETA GEMINORUM', 'BETA GEM', 'HD62509', 'HD 62509']:
        return 'Pollux (β Geminorum)'
    elif target_upper in ['DENEB', 'ALPHA CYGNI', 'ALPHA CYG', 'HD197345', 'HD 197345']:
        return 'Deneb (α Cygni)'
    elif target_upper in ['FOMALHAUT', 'ALPHA PISCIS AUSTRINI', 'ALPHA PSA', 'HD216956', 'HD 216956']:
        return 'Fomalhaut (α Piscis Austrini)'
    elif target_upper in ['MIMOSA', 'BETA CRUCIS', 'BETA CRU', 'HD111123', 'HD 111123']:
        return 'Mimosa (β Crucis)'
    elif target_upper in ['REGULUS', 'ALPHA LEONIS', 'ALPHA LEO', 'HD87901', 'HD 87901']:
        return 'Regulus (α Leonis)'
    elif target_upper in ['ADHARA', 'EPSILON CANIS MAJORIS', 'EPSILON CMA', 'HD52089', 'HD 52089']:
        return 'Adhara (ε Canis Majoris)'
    elif target_upper in ['CASTOR', 'ALPHA GEMINORUM', 'ALPHA GEM', 'HD60179', 'HD 60179']:
        return 'Castor (α Geminorum)'
    elif target_upper in ['SHAULA', 'LAMBDA SCORPII', 'LAMBDA SCO', 'HD158926', 'HD 158926']:
        return 'Shaula (λ Scorpii)'
    elif target_upper in ['BELLATRIX', 'GAMMA ORIONIS', 'GAMMA ORI', 'HD35468', 'HD 35468']:
        return 'Bellatrix (γ Orionis)'
    elif target_upper in ['ALNILAM', 'EPSILON ORIONIS', 'EPSILON ORI', 'HD37128', 'HD 37128']:
        return 'Alnilam (ε Orionis)'
    elif target_upper in ['ALNITAK', 'ZETA ORIONIS', 'ZETA ORI', 'HD37742', 'HD 37742']:
        return 'Alnitak (ζ Orionis)'
    elif target_upper in ['MINTAKA', 'DELTA ORIONIS', 'DELTA ORI', 'HD36486', 'HD 36486']:
        return 'Mintaka (δ Orionis)'
    elif target_upper in ['SAIPH', 'KAPPA ORIONIS', 'KAPPA ORI', 'HD38771', 'HD 38771']:
        return 'Saiph (κ Orionis)'
    elif target_upper in ['MEISSA', 'LAMBDA ORIONIS', 'LAMBDA ORI', 'HD36861', 'HD 36861']:
        return 'Meissa (λ Orionis)'
    elif target_upper in ['ALDEBARAN', 'ALPHA TAURI', 'ALPHA TAU', 'HD29139', 'HD 29139']:
        return 'Aldebaran (α Tauri)'
    elif target_upper in ['ALGOL', 'BETA PERSEI', 'BETA PER', 'HD19356', 'HD 19356']:
        return 'Algol (β Persei)'
    elif target_upper in ['ARCTURUS', 'ALPHA BOOTIS', 'ALPHA BOO', 'HD124897', 'HD 124897']:
        return 'Arcturus (α Bootis)'
    elif target_upper in ['MIRFAK', 'ALPHA PERSEI', 'ALPHA PER', 'HD20902', 'HD 20902']:
        return 'Mirfak (α Persei)'
    elif target_upper in ['ALGIEBA', 'GAMMA LEONIS', 'GAMMA LEO', 'HD89484', 'HD 89484']:
        return 'Algieba (γ Leonis)'
    elif target_upper in ['ALPHARD', 'ALPHA HYDRAE', 'ALPHA HYA', 'HD81797', 'HD 81797']:
        return 'Alphard (α Hydrae)'
    elif target_upper in ['ALPHECCA', 'ALPHA CORONAE BOREALIS', 'ALPHA CRB', 'HD139006', 'HD 139006']:
        return 'Alphecca (α Coronae Borealis)'
    elif target_upper in ['ALPHERATZ', 'ALPHA ANDROMEDAE', 'ALPHA AND', 'HD358', 'HD 358']:
        return 'Alpheratz (α Andromedae)'
    elif target_upper in ['ANKA', 'ALPHA PHOENICIS', 'ALPHA PHE', 'HD2261', 'HD 2261']:
        return 'Anka (α Phoenicis)'
    
    # Wolf-Rayet stars
    elif target_upper in ['WR 134', 'WR134', 'HD191765', 'HD 191765']:
        return 'WR 134 (HD 191765)'
    elif target_upper in ['WR 135', 'WR135', 'HD192103', 'HD 192103']:
        return 'WR 135 (HD 192103)'
    elif target_upper in ['WR 136', 'WR136', 'HD192163', 'HD 192163']:
        return 'WR 136 (HD 192163)'
    elif target_upper in ['WR 140', 'WR140', 'HD193793', 'HD 193793']:
        return 'WR 140 (HD 193793)'
    elif target_upper in ['WR 147', 'WR147', 'HD211853', 'HD 211853']:
        return 'WR 147 (HD 211853)'
    elif target_upper in ['WR 148', 'WR148', 'HD197406', 'HD 197406']:
        return 'WR 148 (HD 197406)'
    elif target_upper in ['WR 152', 'WR152', 'HD211564', 'HD 211564']:
        return 'WR 152 (HD 211564)'
    elif target_upper in ['WR 156', 'WR156', 'HD192641', 'HD 192641']:
        return 'WR 156 (HD 192641)'
    elif target_upper in ['WR 157', 'WR157', 'HD192103', 'HD 192103']:
        return 'WR 157 (HD 192103)'
    elif target_upper in ['WR 158', 'WR158', 'HD197406', 'HD 197406']:
        return 'WR 158 (HD 197406)'
    elif target_upper in ['WR 159', 'WR159', 'HD211853', 'HD 211853']:
        return 'WR 159 (HD 211853)'
    elif target_upper in ['WR 160', 'WR160', 'HD211564', 'HD 211564']:
        return 'WR 160 (HD 211564)'
    elif target_upper in ['WR 161', 'WR161', 'HD192641', 'HD 192641']:
        return 'WR 161 (HD 192641)'
    elif target_upper in ['WR 162', 'WR162', 'HD192103', 'HD 192103']:
        return 'WR 162 (HD 192103)'
    elif target_upper in ['WR 163', 'WR163', 'HD197406', 'HD 197406']:
        return 'WR 163 (HD 197406)'
    elif target_upper in ['WR 164', 'WR164', 'HD211853', 'HD 211853']:
        return 'WR 164 (HD 211853)'
    elif target_upper in ['WR 165', 'WR165', 'HD211564', 'HD 211564']:
        return 'WR 165 (HD 211564)'
    elif target_upper in ['WR 166', 'WR166', 'HD192641', 'HD 192641']:
        return 'WR 166 (HD 192641)'
    elif target_upper in ['WR 167', 'WR167', 'HD192103', 'HD 192103']:
        return 'WR 167 (HD 192103)'
    elif target_upper in ['WR 168', 'WR168', 'HD197406', 'HD 197406']:
        return 'WR 168 (HD 197406)'
    elif target_upper in ['WR 169', 'WR169', 'HD211853', 'HD 211853']:
        return 'WR 169 (HD 211853)'
    elif target_upper in ['WR 170', 'WR170', 'HD211564', 'HD 211564']:
        return 'WR 170 (HD 211564)'
    elif target_upper in ['WR 171', 'WR171', 'HD192641', 'HD 192641']:
        return 'WR 171 (HD 192641)'
    elif target_upper in ['WR 172', 'WR172', 'HD192103', 'HD 192103']:
        return 'WR 172 (HD 192103)'
    elif target_upper in ['WR 173', 'WR173', 'HD197406', 'HD 197406']:
        return 'WR 173 (HD 197406)'
    elif target_upper in ['WR 174', 'WR174', 'HD211853', 'HD 211853']:
        return 'WR 174 (HD 211853)'
    elif target_upper in ['WR 175', 'WR175', 'HD211564', 'HD 211564']:
        return 'WR 175 (HD 211564)'
    elif target_upper in ['WR 176', 'WR176', 'HD192641', 'HD 192641']:
        return 'WR 176 (HD 192641)'
    elif target_upper in ['WR 177', 'WR177', 'HD192103', 'HD 192103']:
        return 'WR 177 (HD 192103)'
    elif target_upper in ['WR 178', 'WR178', 'HD197406', 'HD 197406']:
        return 'WR 178 (HD 197406)'
    elif target_upper in ['WR 179', 'WR179', 'HD211853', 'HD 211853']:
        return 'WR 179 (HD 211853)'
    elif target_upper in ['WR 180', 'WR180', 'HD211564', 'HD 211564']:
        return 'WR 180 (HD 211564)'
    elif target_upper in ['WR 181', 'WR181', 'HD192641', 'HD 192641']:
        return 'WR 181 (HD 192641)'
    elif target_upper in ['WR 182', 'WR182', 'HD192103', 'HD 192103']:
        return 'WR 182 (HD 192103)'
    elif target_upper in ['WR 183', 'WR183', 'HD197406', 'HD 197406']:
        return 'WR 183 (HD 197406)'
    elif target_upper in ['WR 184', 'WR184', 'HD211853', 'HD 211853']:
        return 'WR 184 (HD 211853)'
    elif target_upper in ['WR 185', 'WR185', 'HD211564', 'HD 211564']:
        return 'WR 185 (HD 211564)'
    elif target_upper in ['WR 186', 'WR186', 'HD192641', 'HD 192641']:
        return 'WR 186 (HD 192641)'
    elif target_upper in ['WR 187', 'WR187', 'HD192103', 'HD 192103']:
        return 'WR 187 (HD 192103)'
    elif target_upper in ['WR 188', 'WR188', 'HD197406', 'HD 197406']:
        return 'WR 188 (HD 197406)'
    elif target_upper in ['WR 189', 'WR189', 'HD211853', 'HD 211853']:
        return 'WR 189 (HD 211853)'
    elif target_upper in ['WR 190', 'WR190', 'HD211564', 'HD 211564']:
        return 'WR 190 (HD 211564)'
    elif target_upper in ['WR 191', 'WR191', 'HD192641', 'HD 192641']:
        return 'WR 191 (HD 192641)'
    elif target_upper in ['WR 192', 'WR192', 'HD192103', 'HD 192103']:
        return 'WR 192 (HD 192103)'
    elif target_upper in ['WR 193', 'WR193', 'HD197406', 'HD 197406']:
        return 'WR 193 (HD 197406)'
    elif target_upper in ['WR 194', 'WR194', 'HD211853', 'HD 211853']:
        return 'WR 194 (HD 211853)'
    elif target_upper in ['WR 195', 'WR195', 'HD211564', 'HD 211564']:
        return 'WR 195 (HD 211564)'
    elif target_upper in ['WR 196', 'WR196', 'HD192641', 'HD 192641']:
        return 'WR 196 (HD 192641)'
    elif target_upper in ['WR 197', 'WR197', 'HD192103', 'HD 192103']:
        return 'WR 197 (HD 192103)'
    elif target_upper in ['WR 198', 'WR198', 'HD197406', 'HD 197406']:
        return 'WR 198 (HD 197406)'
    elif target_upper in ['WR 199', 'WR199', 'HD211853', 'HD 211853']:
        return 'WR 199 (HD 211853)'
    elif target_upper in ['WR 200', 'WR200', 'HD211564', 'HD 211564']:
        return 'WR 200 (HD 211564)'
    
    # Additional famous stars with Greek letters
    elif target_upper in ['RHO OPHIUCHI', 'RHO OPH', 'HD147933', 'HD 147933']:
        return 'ρ Ophiuchi'
    elif target_upper in ['SIGMA ORIONIS', 'SIGMA ORI', 'HD37468', 'HD 37468']:
        return 'σ Orionis'
    elif target_upper in ['PHI ORIONIS', 'PHI ORI', 'HD36822', 'HD 36822']:
        return 'φ Orionis'
    elif target_upper in ['CHI ORIONIS', 'CHI ORI', 'HD39587', 'HD 39587']:
        return 'χ Orionis'
    elif target_upper in ['PSI ORIONIS', 'PSI ORI', 'HD35715', 'HD 35715']:
        return 'ψ Orionis'
    elif target_upper in ['OMEGA ORIONIS', 'OMEGA ORI', 'HD37490', 'HD 37490']:
        return 'ω Orionis'
    elif target_upper in ['TAU CANIS MAJORIS', 'TAU CMA', 'HD47105', 'HD 47105']:
        return 'τ Canis Majoris'
    elif target_upper in ['UPSILON SCORPII', 'UPSILON SCO', 'HD158408', 'HD 158408']:
        return 'υ Scorpii'
    elif target_upper in ['PHI CENTAURI', 'PHI CEN', 'HD121743', 'HD 121743']:
        return 'φ Centauri'
    elif target_upper in ['CHI CENTAURI', 'CHI CEN', 'HD125473', 'HD 125473']:
        return 'χ Centauri'
    
    # More famous stars with Greek letters - Constellations
    elif target_upper in ['ALPHA PEGASI', 'ALPHA PEG', 'HD87801', 'HD 87801']:
        return 'Markab (α Pegasi)'
    elif target_upper in ['BETA PEGASI', 'BETA PEG', 'HD88601', 'HD 88601']:
        return 'Scheat (β Pegasi)'
    elif target_upper in ['GAMMA PEGASI', 'GAMMA PEG', 'HD88635', 'HD 88635']:
        return 'Algenib (γ Pegasi)'
    elif target_upper in ['DELTA PEGASI', 'DELTA PEG', 'HD85795', 'HD 85795']:
        return 'δ Pegasi'
    elif target_upper in ['EPSILON PEGASI', 'EPSILON PEG', 'HD206778', 'HD 206778']:
        return 'Enif (ε Pegasi)'
    elif target_upper in ['ZETA PEGASI', 'ZETA PEG', 'HD214923', 'HD 214923']:
        return 'Homam (ζ Pegasi)'
    elif target_upper in ['ETA PEGASI', 'ETA PEG', 'HD215182', 'HD 215182']:
        return 'Matar (η Pegasi)'
    elif target_upper in ['THETA PEGASI', 'THETA PEG', 'HD222143', 'HD 222143']:
        return 'Biham (θ Pegasi)'
    elif target_upper in ['IOTA PEGASI', 'IOTA PEG', 'HD210027', 'HD 210027']:
        return 'ι Pegasi'
    elif target_upper in ['KAPPA PEGASI', 'KAPPA PEG', 'HD220657', 'HD 220657']:
        return 'Jih (κ Pegasi)'
    elif target_upper in ['LAMBDA PEGASI', 'LAMBDA PEG', 'HD218356', 'HD 218356']:
        return 'λ Pegasi'
    elif target_upper in ['MU PEGASI', 'MU PEG', 'HD216131', 'HD 216131']:
        return 'Sadalbari (μ Pegasi)'
    elif target_upper in ['NU PEGASI', 'NU PEG', 'HD217459', 'HD 217459']:
        return 'ν Pegasi'
    elif target_upper in ['XI PEGASI', 'XI PEG', 'HD215648', 'HD 215648']:
        return 'ξ Pegasi'
    elif target_upper in ['OMICRON PEGASI', 'OMICRON PEG', 'HD214994', 'HD 214994']:
        return 'ο Pegasi'
    elif target_upper in ['PI PEGASI', 'PI PEG', 'HD210459', 'HD 210459']:
        return 'π Pegasi'
    elif target_upper in ['RHO PEGASI', 'RHO PEG', 'HD216735', 'HD 216735']:
        return 'ρ Pegasi'
    elif target_upper in ['SIGMA PEGASI', 'SIGMA PEG', 'HD216385', 'HD 216385']:
        return 'σ Pegasi'
    elif target_upper in ['TAU PEGASI', 'TAU PEG', 'HD220061', 'HD 220061']:
        return 'τ Pegasi'
    elif target_upper in ['UPSILON PEGASI', 'UPSILON PEG', 'HD220657', 'HD 220657']:
        return 'υ Pegasi'
    elif target_upper in ['PHI PEGASI', 'PHI PEG', 'HD216385', 'HD 216385']:
        return 'φ Pegasi'
    elif target_upper in ['CHI PEGASI', 'CHI PEG', 'HD220657', 'HD 220657']:
        return 'χ Pegasi'
    elif target_upper in ['PSI PEGASI', 'PSI PEG', 'HD220657', 'HD 220657']:
        return 'ψ Pegasi'
    elif target_upper in ['OMEGA PEGASI', 'OMEGA PEG', 'HD220657', 'HD 220657']:
        return 'ω Pegasi'
    
    # More famous stars with Greek letters - Other constellations
    elif target_upper in ['ALPHA CASSIOPEIAE', 'ALPHA CAS', 'HD7924', 'HD 7924']:
        return 'Schedar (α Cassiopeiae)'
    elif target_upper in ['BETA CASSIOPEIAE', 'BETA CAS', 'HD432', 'HD 432']:
        return 'Caph (β Cassiopeiae)'
    elif target_upper in ['GAMMA CASSIOPEIAE', 'GAMMA CAS', 'HD5394', 'HD 5394']:
        return 'Tsih (γ Cassiopeiae)'
    elif target_upper in ['DELTA CASSIOPEIAE', 'DELTA CAS', 'HD8538', 'HD 8538']:
        return 'Ruchbah (δ Cassiopeiae)'
    elif target_upper in ['EPSILON CASSIOPEIAE', 'EPSILON CAS', 'HD8912', 'HD 8912']:
        return 'Segin (ε Cassiopeiae)'
    elif target_upper in ['ZETA CASSIOPEIAE', 'ZETA CAS', 'HD3360', 'HD 3360']:
        return 'Fulu (ζ Cassiopeiae)'
    elif target_upper in ['ETA CASSIOPEIAE', 'ETA CAS', 'HD4614', 'HD 4614']:
        return 'Achird (η Cassiopeiae)'
    elif target_upper in ['THETA CASSIOPEIAE', 'THETA CAS', 'HD6960', 'HD 6960']:
        return 'θ Cassiopeiae'
    elif target_upper in ['IOTA CASSIOPEIAE', 'IOTA CAS', 'HD15089', 'HD 15089']:
        return 'ι Cassiopeiae'
    elif target_upper in ['KAPPA CASSIOPEIAE', 'KAPPA CAS', 'HD2905', 'HD 2905']:
        return 'κ Cassiopeiae'
    elif target_upper in ['LAMBDA CASSIOPEIAE', 'LAMBDA CAS', 'HD11519', 'HD 11519']:
        return 'λ Cassiopeiae'
    elif target_upper in ['MU CASSIOPEIAE', 'MU CAS', 'HD6582', 'HD 6582']:
        return 'μ Cassiopeiae'
    elif target_upper in ['NU CASSIOPEIAE', 'NU CAS', 'HD10362', 'HD 10362']:
        return 'ν Cassiopeiae'
    elif target_upper in ['XI CASSIOPEIAE', 'XI CAS', 'HD11171', 'HD 11171']:
        return 'ξ Cassiopeiae'
    elif target_upper in ['OMICRON CASSIOPEIAE', 'OMICRON CAS', 'HD10894', 'HD 10894']:
        return 'ο Cassiopeiae'
    elif target_upper in ['PI CASSIOPEIAE', 'PI CAS', 'HD5810', 'HD 5810']:
        return 'π Cassiopeiae'
    elif target_upper in ['RHO CASSIOPEIAE', 'RHO CAS', 'HD224014', 'HD 224014']:
        return 'ρ Cassiopeiae'
    elif target_upper in ['SIGMA CASSIOPEIAE', 'SIGMA CAS', 'HD11832', 'HD 11832']:
        return 'σ Cassiopeiae'
    elif target_upper in ['TAU CASSIOPEIAE', 'TAU CAS', 'HD223165', 'HD 223165']:
        return 'τ Cassiopeiae'
    elif target_upper in ['UPSILON CASSIOPEIAE', 'UPSILON CAS', 'HD13324', 'HD 13324']:
        return 'υ Cassiopeiae'
    elif target_upper in ['PHI CASSIOPEIAE', 'PHI CAS', 'HD7927', 'HD 7927']:
        return 'φ Cassiopeiae'
    elif target_upper in ['CHI CASSIOPEIAE', 'CHI CAS', 'HD7291', 'HD 7291']:
        return 'χ Cassiopeiae'
    elif target_upper in ['PSI CASSIOPEIAE', 'PSI CAS', 'HD8491', 'HD 8491']:
        return 'ψ Cassiopeiae'
    elif target_upper in ['OMEGA CASSIOPEIAE', 'OMEGA CAS', 'HD10460', 'HD 10460']:
        return 'ω Cassiopeiae'
    
    # More famous stars with Greek letters - Ursa Major
    elif target_upper in ['ALPHA URSAE MAJORIS', 'ALPHA UMA', 'HD95689', 'HD 95689']:
        return 'Dubhe (α Ursae Majoris)'
    elif target_upper in ['BETA URSAE MAJORIS', 'BETA UMA', 'HD95418', 'HD 95418']:
        return 'Merak (β Ursae Majoris)'
    elif target_upper in ['GAMMA URSAE MAJORIS', 'GAMMA UMA', 'HD103287', 'HD 103287']:
        return 'Phecda (γ Ursae Majoris)'
    elif target_upper in ['DELTA URSAE MAJORIS', 'DELTA UMA', 'HD106591', 'HD 106591']:
        return 'Megrez (δ Ursae Majoris)'
    elif target_upper in ['EPSILON URSAE MAJORIS', 'EPSILON UMA', 'HD112185', 'HD 112185']:
        return 'Alioth (ε Ursae Majoris)'
    elif target_upper in ['ZETA URSAE MAJORIS', 'ZETA UMA', 'HD116656', 'HD 116656']:
        return 'Mizar (ζ Ursae Majoris)'
    elif target_upper in ['ETA URSAE MAJORIS', 'ETA UMA', 'HD120315', 'HD 120315']:
        return 'Alkaid (η Ursae Majoris)'
    elif target_upper in ['THETA URSAE MAJORIS', 'THETA UMA', 'HD82328', 'HD 82328']:
        return 'θ Ursae Majoris'
    elif target_upper in ['IOTA URSAE MAJORIS', 'IOTA UMA', 'HD76644', 'HD 76644']:
        return 'Talitha (ι Ursae Majoris)'
    elif target_upper in ['KAPPA URSAE MAJORIS', 'KAPPA UMA', 'HD77327', 'HD 77327']:
        return 'Alkaphrah (κ Ursae Majoris)'
    elif target_upper in ['LAMBDA URSAE MAJORIS', 'LAMBDA UMA', 'HD89021', 'HD 89021']:
        return 'Tania Borealis (λ Ursae Majoris)'
    elif target_upper in ['MU URSAE MAJORIS', 'MU UMA', 'HD89758', 'HD 89758']:
        return 'Tania Australis (μ Ursae Majoris)'
    elif target_upper in ['NU URSAE MAJORIS', 'NU UMA', 'HD91312', 'HD 91312']:
        return 'Alula Borealis (ν Ursae Majoris)'
    elif target_upper in ['XI URSAE MAJORIS', 'XI UMA', 'HD93765', 'HD 93765']:
        return 'Alula Australis (ξ Ursae Majoris)'
    elif target_upper in ['OMICRON URSAE MAJORIS', 'OMICRON UMA', 'HD71369', 'HD 71369']:
        return 'Muscida (ο Ursae Majoris)'
    elif target_upper in ['PI URSAE MAJORIS', 'PI UMA', 'HD73108', 'HD 73108']:
        return 'π Ursae Majoris'
    elif target_upper in ['RHO URSAE MAJORIS', 'RHO UMA', 'HD81937', 'HD 81937']:
        return 'ρ Ursae Majoris'
    elif target_upper in ['SIGMA URSAE MAJORIS', 'SIGMA UMA', 'HD78154', 'HD 78154']:
        return 'σ Ursae Majoris'
    elif target_upper in ['TAU URSAE MAJORIS', 'TAU UMA', 'HD78362', 'HD 78362']:
        return 'τ Ursae Majoris'
    elif target_upper in ['UPSILON URSAE MAJORIS', 'UPSILON UMA', 'HD84999', 'HD 84999']:
        return 'υ Ursae Majoris'
    elif target_upper in ['PHI URSAE MAJORIS', 'PHI UMA', 'HD85235', 'HD 85235']:
        return 'φ Ursae Majoris'
    elif target_upper in ['CHI URSAE MAJORIS', 'CHI UMA', 'HD85444', 'HD 85444']:
        return 'χ Ursae Majoris'
    elif target_upper in ['PSI URSAE MAJORIS', 'PSI UMA', 'HD85693', 'HD 85693']:
        return 'ψ Ursae Majoris'
    elif target_upper in ['OMEGA URSAE MAJORIS', 'OMEGA UMA', 'HD85841', 'HD 85841']:
        return 'ω Ursae Majoris'
    
    # More famous stars with Greek letters - Cygnus
    elif target_upper in ['ALPHA CYGNI', 'ALPHA CYG', 'HD197345', 'HD 197345']:
        return 'Deneb (α Cygni)'
    elif target_upper in ['BETA CYGNI', 'BETA CYG', 'HD183912', 'HD 183912']:
        return 'Albireo (β Cygni)'
    elif target_upper in ['GAMMA CYGNI', 'GAMMA CYG', 'HD194093', 'HD 194093']:
        return 'Sadr (γ Cygni)'
    elif target_upper in ['DELTA CYGNI', 'DELTA CYG', 'HD186882', 'HD 186882']:
        return 'Fawaris (δ Cygni)'
    elif target_upper in ['EPSILON CYGNI', 'EPSILON CYG', 'HD197989', 'HD 197989']:
        return 'Gienah (ε Cygni)'
    elif target_upper in ['ZETA CYGNI', 'ZETA CYG', 'HD183227', 'HD 183227']:
        return 'ζ Cygni'
    elif target_upper in ['ETA CYGNI', 'ETA CYG', 'HD188947', 'HD 188947']:
        return 'η Cygni'
    elif target_upper in ['THETA CYGNI', 'THETA CYG', 'HD185395', 'HD 185395']:
        return 'θ Cygni'
    elif target_upper in ['IOTA CYGNI', 'IOTA CYG', 'HD184006', 'HD 184006']:
        return 'ι Cygni'
    elif target_upper in ['KAPPA CYGNI', 'KAPPA CYG', 'HD181276', 'HD 181276']:
        return 'κ Cygni'
    elif target_upper in ['LAMBDA CYGNI', 'LAMBDA CYG', 'HD182564', 'HD 182564']:
        return 'λ Cygni'
    elif target_upper in ['MU CYGNI', 'MU CYG', 'HD193924', 'HD 193924']:
        return 'μ Cygni'
    elif target_upper in ['NU CYGNI', 'NU CYG', 'HD199629', 'HD 199629']:
        return 'ν Cygni'
    elif target_upper in ['XI CYGNI', 'XI CYG', 'HD200905', 'HD 200905']:
        return 'ξ Cygni'
    elif target_upper in ['OMICRON CYGNI', 'OMICRON CYG', 'HD192579', 'HD 192579']:
        return 'ο Cygni'
    elif target_upper in ['PI CYGNI', 'PI CYG', 'HD182917', 'HD 182917']:
        return 'π Cygni'
    elif target_upper in ['RHO CYGNI', 'RHO CYG', 'HD185435', 'HD 185435']:
        return 'ρ Cygni'
    elif target_upper in ['SIGMA CYGNI', 'SIGMA CYG', 'HD202850', 'HD 202850']:
        return 'σ Cygni'
    elif target_upper in ['TAU CYGNI', 'TAU CYG', 'HD199960', 'HD 199960']:
        return 'τ Cygni'
    elif target_upper in ['UPSILON CYGNI', 'UPSILON CYG', 'HD186408', 'HD 186408']:
        return 'υ Cygni'
    elif target_upper in ['PHI CYGNI', 'PHI CYG', 'HD187929', 'HD 187929']:
        return 'φ Cygni'
    elif target_upper in ['CHI CYGNI', 'CHI CYG', 'HD187796', 'HD 187796']:
        return 'χ Cygni'
    elif target_upper in ['PSI CYGNI', 'PSI CYG', 'HD189684', 'HD 189684']:
        return 'ψ Cygni'
    elif target_upper in ['OMEGA CYGNI', 'OMEGA CYG', 'HD195774', 'HD 195774']:
        return 'ω Cygni'
    
    # More famous stars with Greek letters - Aquila
    elif target_upper in ['ALPHA AQUILAE', 'ALPHA AQL', 'HD187642', 'HD 187642']:
        return 'Altair (α Aquilae)'
    elif target_upper in ['BETA AQUILAE', 'BETA AQL', 'HD188512', 'HD 188512']:
        return 'Alshain (β Aquilae)'
    elif target_upper in ['GAMMA AQUILAE', 'GAMMA AQL', 'HD186791', 'HD 186791']:
        return 'Tarazed (γ Aquilae)'
    elif target_upper in ['DELTA AQUILAE', 'DELTA AQL', 'HD185194', 'HD 185194']:
        return 'δ Aquilae'
    elif target_upper in ['EPSILON AQUILAE', 'EPSILON AQL', 'HD188310', 'HD 188310']:
        return 'ε Aquilae'
    elif target_upper in ['ZETA AQUILAE', 'ZETA AQL', 'HD177724', 'HD 177724']:
        return 'ζ Aquilae'
    elif target_upper in ['ETA AQUILAE', 'ETA AQL', 'HD187929', 'HD 187929']:
        return 'η Aquilae'
    elif target_upper in ['THETA AQUILAE', 'THETA AQL', 'HD191692', 'HD 191692']:
        return 'θ Aquilae'
    elif target_upper in ['IOTA AQUILAE', 'IOTA AQL', 'HD173227', 'HD 173227']:
        return 'ι Aquilae'
    elif target_upper in ['KAPPA AQUILAE', 'KAPPA AQL', 'HD186791', 'HD 186791']:
        return 'κ Aquilae'
    elif target_upper in ['LAMBDA AQUILAE', 'LAMBDA AQL', 'HD177756', 'HD 177756']:
        return 'λ Aquilae'
    elif target_upper in ['MU AQUILAE', 'MU AQL', 'HD189340', 'HD 189340']:
        return 'μ Aquilae'
    elif target_upper in ['NU AQUILAE', 'NU AQL', 'HD191692', 'HD 191692']:
        return 'ν Aquilae'
    elif target_upper in ['XI AQUILAE', 'XI AQL', 'HD188310', 'HD 188310']:
        return 'ξ Aquilae'
    elif target_upper in ['OMICRON AQUILAE', 'OMICRON AQL', 'HD187929', 'HD 187929']:
        return 'ο Aquilae'
    elif target_upper in ['PI AQUILAE', 'PI AQL', 'HD177724', 'HD 177724']:
        return 'π Aquilae'
    elif target_upper in ['RHO AQUILAE', 'RHO AQL', 'HD188512', 'HD 188512']:
        return 'ρ Aquilae'
    elif target_upper in ['SIGMA AQUILAE', 'SIGMA AQL', 'HD185194', 'HD 185194']:
        return 'σ Aquilae'
    elif target_upper in ['TAU AQUILAE', 'TAU AQL', 'HD191692', 'HD 191692']:
        return 'τ Aquilae'
    elif target_upper in ['UPSILON AQUILAE', 'UPSILON AQL', 'HD186791', 'HD 186791']:
        return 'υ Aquilae'
    elif target_upper in ['PHI AQUILAE', 'PHI AQL', 'HD188310', 'HD 188310']:
        return 'φ Aquilae'
    elif target_upper in ['CHI AQUILAE', 'CHI AQL', 'HD177724', 'HD 177724']:
        return 'χ Aquilae'
    elif target_upper in ['PSI AQUILAE', 'PSI AQL', 'HD188512', 'HD 188512']:
        return 'ψ Aquilae'
    elif target_upper in ['OMEGA AQUILAE', 'OMEGA AQL', 'HD185194', 'HD 185194']:
        return 'ω Aquilae'
    
    # Common star names
    elif target_upper in ['ALPHA CENTAURI', 'ALPHA CEN', 'ALPHA CEN A', 'ALPHA CEN B']:
        return 'α Centauri'
    elif target_upper in ['BETA CENTAURI', 'BETA CEN']:
        return 'β Centauri'
    elif target_upper in ['GAMMA CENTAURI', 'GAMMA CEN']:
        return 'γ Centauri'
    elif target_upper in ['OMEGA CENTAURI', 'OMEGA CEN']:
        return 'ω Centauri'
    
    # Additional objects that were missing from the original list
    elif target_upper in ['ELEPHANT TRUNK', 'ELEPHANT TRUNK NEBULA', 'IC1396', 'IC 1396']:
        return 'IC 1396 (Elephant Trunk Nebula)'
    elif target_upper in ['HEART', 'HEART NEBULA', 'IC1805', 'IC 1805']:
        return 'IC 1805 (Heart Nebula)'
    elif target_upper in ['CALIFORNIA', 'CALIFORNIA NEBULA', 'NGC1499', 'NGC 1499']:
        return 'NGC 1499 (California Nebula)'
    elif target_upper in ['WESTERN VEIL', 'WESTERN VEIL NEBULA', 'NGC6960', 'NGC 6960']:
        return 'NGC 6960 (Western Veil Nebula)'
    elif target_upper in ['NORTH AMERICA', 'NORTH AMERICA NEBULA', 'NGC7000', 'NGC 7000']:
        return 'NGC 7000 (North America Nebula)'
    
    # For non-catalog targets, normalize separators and use Title Case
    import re
    # Replace all separators (underscores, hyphens, dots) with spaces
    normalized = re.sub(r'[_\s\-\.]+', ' ', target)
    # Remove extra spaces and convert to Title Case
    normalized = ' '.join(normalized.split())
    
    # Custom title case that respects apostrophes
    normalized = smart_title_case(normalized)
    
    return normalized

def normalize_telescope_name(telescope_name):
    """
    Normalize telescope name: replace technical descriptions and mount names with 'Unknown'.
    Many FITS headers put the mount (e.g. AM5, CEM40, EQ6) in TELESCOP; that is a mount, not a telescope.
    """
    if not telescope_name or telescope_name.strip() == '' or telescope_name.strip() == 'Unknown':
        return 'Unknown'
    
    telescope = telescope_name.strip()
    telescope_upper = telescope.upper()
    
    # Known mount identifiers (mounts, not telescopes) -> treat as Unknown so instrument/camera is used
    mount_indicators = [
        'AM5', 'AM3', 'CEM40', 'CEM26', 'CEM25', 'CEM70', 'iOptron',
        'EQ6', 'EQ8', 'EQ5', 'EQ3', 'HEQ5', 'NEQ6', 'EQ6-R', 'EQ8-R',
        'SkyWatcher', 'SKYWATCHER', 'AZEQ6', 'AZ-EQ6', 'AZ-EQ5',
        'Celestron AVX', 'AVX', 'CGEM', 'CGX', 'CGX-L', 'NexStar',
        'Losmandy', 'G11', 'G8', 'GM8', 'Titan',
        '10Micron', 'GM1000', 'GM2000',
        'Paramount', 'ME', 'MYT', 'MX', 'MX+',
        'Rainbow', 'RST', 'RST-135', 'RST-300',
        'Harmonic', 'ZWO AM5', 'ZWO AM3',
        'Astro-Physics', 'AP Mach1', 'AP1100', 'AP900', 'AP1600',
        'Software Bisque', 'Bisque',
    ]
    for mount in mount_indicators:
        if mount.upper() in telescope_upper or telescope_upper == mount.upper():
            return 'Unknown'
    
    # Check for technical descriptions that should be replaced with 'Unknown'
    technical_indicators = [
        '->', 'driver', 'connected', 'through', 'for telescope', 'telescope connected',
        'driver for', 'connected through', 'telescope driver', 'driver connected',
        'ACP->', 'ACP->Driver', 'Driver for', 'Connected through', 'Telescope connected',
        'TELESCOPE CONNECTED', 'DRIVER FOR', 'CONNECTED THROUGH', 'ACP->DRIVER'
    ]
    for indicator in technical_indicators:
        if indicator.upper() in telescope_upper:
            return 'Unknown'
    
    # Check for very long names (more than 50 characters) that might break table formatting
    if len(telescope) > 50:
        return 'Unknown'
    
    # Check for names that look like technical descriptions
    problematic_chars = ['->', '(', ')', '[', ']', '{', '}', '|', '\\', '/', ':', ';', '=', '*', '&', '%', '$', '#', '@', '!', '?', '<', '>']
    problematic_count = sum(1 for char in telescope if char in problematic_chars)
    if problematic_count > 2 or any(phrase in telescope_upper for phrase in ['DRIVER', 'CONNECTED', 'THROUGH', 'FOR TELESCOPE']):
        return 'Unknown'
    
    return telescope




# ============================================================================
# SECTION GUI: GRAPHICAL USER INTERFACE (PyQt6)
# ============================================================================

if PYQT6_AVAILABLE:
    
    class AnalysisWorker(QThread):
        """Worker thread for background analysis"""
        output_signal = pyqtSignal(str)
        progress_signal = pyqtSignal(int, int, str)  # current, total, phase
        finished_signal = pyqtSignal(bool, str, str, object, object)  # success, message, folder, data_by_target, global_data
        
        def __init__(self, folder_path, options):
            super().__init__()
            self.folder_path = folder_path
            self.options = options
            self.should_stop = False
            self.output_folder = None
            self.data_by_target = None
            self.global_data = None
        
        def run(self):
            """Run the analysis"""
            global ADU_ANALYSIS_ENABLED, ADU_SAMPLE_PER_FILTER, FAST_ANALYSIS, GENERATE_THUMBNAILS
            
            # Set up progress callback to emit signal
            def progress_callback(current, total, phase):
                self.progress_signal.emit(current, total, phase)
            
            set_progress_callback(progress_callback)
            
            # Redirect stdout to capture output
            import io
            
            class OutputCapture:
                def __init__(self, signal):
                    self.signal = signal
                    self.buffer = ""
                
                def write(self, text):
                    if text:
                        self.signal.emit(str(text))
                    return len(text) if text else 0
                
                def flush(self):
                    pass
            
            old_stdout = sys.stdout
            sys.stdout = OutputCapture(self.output_signal)
            
            try:
                # Configure analysis
                GENERATE_THUMBNAILS = self.options.get('generate_thumbnails', False)
                ADU_ANALYSIS_ENABLED = False
                FAST_ANALYSIS = True
                ADU_SAMPLE_PER_FILTER = 3
                
                workers = self.options.get('workers')
                if workers is None or workers == 0:
                    import multiprocessing
                    try:
                        workers = multiprocessing.cpu_count()
                    except Exception:
                        workers = 1
                
                # Create output folder at the ROOT of the analyzed folder
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_folder_name = f"astronomical_analysis_{timestamp}"
                self.output_folder = os.path.join(str(self.folder_path), output_folder_name)
                os.makedirs(self.output_folder, exist_ok=True)
                
                # Messages bilingues
                if SYSTEM_LANGUAGE == 'fr':
                    print(f"📁 Dossier de sortie: {self.output_folder}")
                    print(f"🔍 Analyse de: {self.folder_path}")
                    print(f"🧵 Workers: {workers}")
                else:
                    print(f"📁 Output folder: {self.output_folder}")
                    print(f"🔍 Analyzing: {self.folder_path}")
                    print(f"🧵 Workers: {workers}")
                print("=" * 60)
                
                if self.should_stop:
                    msg = "Arrêté par l'utilisateur" if SYSTEM_LANGUAGE == 'fr' else "Stopped by user"
                    self.finished_signal.emit(False, msg, self.output_folder, None, None)
                    return
                
                # Run analysis (pass check_abort so user can stop mid-phase)
                if SYSTEM_LANGUAGE == 'fr':
                    print("🔍 Démarrage de l'analyse FITS...")
                else:
                    print("🔍 Starting FITS analysis...")
                result = analyze_folder_recursive(str(self.folder_path), workers, check_abort=lambda: self.should_stop)
                if result is None:
                    msg = "Arrêté par l'utilisateur" if SYSTEM_LANGUAGE == 'fr' else "Stopped by user"
                    self.finished_signal.emit(False, msg, self.output_folder, None, None)
                    return
                data_by_target, global_data = result
                
                # Store for later use
                self.data_by_target = data_by_target
                self.global_data = global_data
                
                if self.should_stop:
                    msg = "Arrêté par l'utilisateur" if SYSTEM_LANGUAGE == 'fr' else "Stopped by user"
                    self.finished_signal.emit(False, msg, self.output_folder, None, None)
                    return
                
                if not data_by_target:
                    # No LIGHT files found - but still proceed with compression/extraction
                    # if those options are enabled (they work on ALL file types: LIGHT, DARK, FLAT, BIAS)
                    has_storage_tasks = (self.options.get('compress_fits', False) or 
                                        self.options.get('extract_duplicates', False))
                    files_after_dedup = self.global_data.get('files_after_dedup', 0)
                    
                    if has_storage_tasks and files_after_dedup > 0:
                        # There ARE files, just no LIGHT - proceed with storage optimization
                        if SYSTEM_LANGUAGE == 'fr':
                            print(f"\nℹ️  Aucun fichier LIGHT trouvé parmi {files_after_dedup} fichier(s).")
                            print("   Poursuite de l'optimisation du stockage (compression/extraction) pour tous types...")
                        else:
                            print(f"\nℹ️  No LIGHT files found among {files_after_dedup} file(s).")
                            print("   Proceeding with storage optimization (compression/extraction) for all types...")
                        
                        # Extraction folder when extract_duplicates is enabled
                        extraction_folder = None
                        if self.options.get('extract_duplicates', False):
                            extraction_folder = os.path.join(os.path.dirname(str(self.folder_path)),
                                                             "extracted_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
                            os.makedirs(extraction_folder, exist_ok=True)
                            prefer_format = self.options.get('prefer_format', 'xisf')
                            set_prefer_format(prefer_format)
                        
                        # Compress FITS to XISF (all types) — move originals to extraction folder when enabled
                        if self.options.get('compress_fits', False):
                            if SYSTEM_LANGUAGE == 'fr':
                                print("\n🗜️ Compression FITS → XISF (tous types de fichiers)...")
                            else:
                                print("\n🗜️ Compressing FITS → XISF (all file types)...")
                            compress_fits_to_xisf(
                                str(self.folder_path),
                                backup_folder=extraction_folder,
                                workers=workers,
                                add_to_duplicates=not extraction_folder,
                                check_abort=lambda: self.should_stop
                            )
                        
                        # Extract remaining duplicates (compressed originals already moved above if extraction_folder was set)
                        if extraction_folder:
                            extract_duplicates_to_folder(str(self.folder_path), extraction_folder)
                        
                        duplicates_info = get_detected_duplicates()
                        total_dups = (len(duplicates_info.get('name_based', [])) + 
                                      len(duplicates_info.get('content_based', [])) + 
                                      len(duplicates_info.get('compressed', [])))
                        
                        if SYSTEM_LANGUAGE == 'fr':
                            msg = ("Optimisation du stockage terminée.\n"
                                   "Aucun fichier LIGHT/SCIENCE trouvé pour l'analyse.\n"
                                   "%d fichier(s) traité(s)." % files_after_dedup)
                            if total_dups > 0:
                                msg += "\n%d doublon(s) détecté(s)/traité(s) (tous types)." % total_dups
                        else:
                            msg = ("Storage optimization completed.\n"
                                   "No LIGHT/SCIENCE files found for analysis.\n"
                                   "%d file(s) processed." % files_after_dedup)
                            if total_dups > 0:
                                msg += "\n%d duplicate(s) detected/processed (all types)." % total_dups
                        
                        self.finished_signal.emit(True, msg, self.output_folder, None, global_data)
                        return
                    else:
                        # No storage tasks requested and no LIGHT files
                        duplicates_info = get_detected_duplicates()
                        total_dups = (len(duplicates_info.get('name_based', [])) + 
                                      len(duplicates_info.get('content_based', [])) + 
                                      len(duplicates_info.get('compressed', [])))
                        if files_after_dedup > 0:
                            if SYSTEM_LANGUAGE == 'fr':
                                msg = ("Aucun fichier LIGHT/SCIENCE trouvé.\n"
                                       "%d fichier(s) FITS/XISF analysé(s), tous calibrations (DARK/FLAT/BIAS).\n" % files_after_dedup)
                                if total_dups > 0:
                                    msg += "%d doublon(s) détecté(s) (tous types).\n" % total_dups
                                msg += "Cochez 'Compresser FITS → XISF' pour optimiser le stockage de tous les types."
                            else:
                                msg = ("No LIGHT/SCIENCE files found.\n"
                                       "%d FITS/XISF file(s) analyzed, all calibration (DARK/FLAT/BIAS).\n" % files_after_dedup)
                                if total_dups > 0:
                                    msg += "%d duplicate(s) detected (all types).\n" % total_dups
                                msg += "Check 'Compress FITS → XISF' to optimize storage for all file types."
                        else:
                            msg = "Aucun fichier FITS/XISF trouvé" if SYSTEM_LANGUAGE == 'fr' else "No FITS/XISF files found"
                        self.finished_signal.emit(False, msg, self.output_folder, None, None)
                        return
                
                # Group targets
                if SYSTEM_LANGUAGE == 'fr':
                    print("🔗 Regroupement des cibles...")
                else:
                    print("🔗 Grouping targets...")
                data_by_target = group_normalized_targets(data_by_target)
                # Optional: resolve via SIMBAD and merge duplicate catalog names
                if self.options.get('resolve_simbad', False):
                    if SIMBAD_AVAILABLE:
                        if SYSTEM_LANGUAGE == 'fr':
                            print("🔍 Résolution des cibles via SIMBAD...")
                        else:
                            print("🔍 Resolving targets via SIMBAD...")
                        unique_names = list(data_by_target.keys())
                        name_to_canonical, canonical_to_info = query_simbad_for_targets(unique_names, check_abort=lambda: self.should_stop)
                        if name_to_canonical:
                            before = len(data_by_target)
                            data_by_target = merge_targets_by_simbad(data_by_target, name_to_canonical, canonical_to_info)
                            if len(data_by_target) != before and SYSTEM_LANGUAGE == 'fr':
                                print(f"   📊 Fusion SIMBAD: {before} → {len(data_by_target)} cibles")
                            elif len(data_by_target) != before:
                                print(f"   📊 SIMBAD merge: {before} → {len(data_by_target)} targets")
                    else:
                        if SYSTEM_LANGUAGE == 'fr':
                            print("   ⚠️ astroquery non installé. pip install astroquery")
                        else:
                            print("   ⚠️ astroquery not installed. pip install astroquery")
                data_by_target = group_mosaic_panels(data_by_target)
                self.data_by_target = data_by_target
                
                # Display statistics
                display_target_statistics(data_by_target)
                
                if self.should_stop:
                    self.finished_signal.emit(False, "Stopped by user", self.output_folder, None, None)
                    return
                
                # Generate outputs
                if self.options.get('generate_graphs', True):
                    if SYSTEM_LANGUAGE == 'fr':
                        print("📊 Génération des graphiques...")
                    else:
                        print("📊 Generating graphs...")
                    generate_graphs(data_by_target, global_data, self.output_folder)
                
                if self.should_stop:
                    msg = "Arrêté par l'utilisateur" if SYSTEM_LANGUAGE == 'fr' else "Stopped by user"
                    self.finished_signal.emit(False, msg, self.output_folder, None, None)
                    return
                
                if self.options.get('generate_latex', True):
                    if SYSTEM_LANGUAGE == 'fr':
                        print("📄 Génération du rapport LaTeX...")
                    else:
                        print("📄 Generating LaTeX report...")
                    generate_latex_report(data_by_target, global_data, self.output_folder)
                    
                    # Always generate HTML report alongside LaTeX
                    generate_html_report(data_by_target, global_data, self.output_folder)
                
                # Export AstroBin CSV
                if self.options.get('export_astrobin', False):
                    if SYSTEM_LANGUAGE == 'fr':
                        print("🌟 Export CSV AstroBin...")
                    else:
                        print("🌟 Exporting AstroBin CSV...")
                    export_astrobin_csv(data_by_target, global_data, self.output_folder)
                
                # Extraction folder (used for moving compressed originals and/or other duplicates)
                extraction_folder = None
                if self.options.get('extract_duplicates', False):
                    extraction_folder = os.path.join(os.path.dirname(str(self.folder_path)),
                                                     "extracted_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
                    os.makedirs(extraction_folder, exist_ok=True)
                    prefer_format = self.options.get('prefer_format', 'xisf')
                    set_prefer_format(prefer_format)
                
                # Compress FITS to XISF — when extraction is enabled, move originals to extraction folder (preserving structure)
                if self.options.get('compress_fits', False):
                    compress_fits_to_xisf(
                        str(self.folder_path),
                        backup_folder=extraction_folder if extraction_folder else None,
                        workers=workers,
                        add_to_duplicates=not extraction_folder,  # if we move to extraction_folder, no need to add to list
                        check_abort=lambda: self.should_stop
                    )
                    if self.should_stop:
                        msg = "Arrêté par l'utilisateur" if SYSTEM_LANGUAGE == 'fr' else "Stopped by user"
                        self.finished_signal.emit(False, msg, self.output_folder, None, None)
                        return
                
                # Extract remaining duplicates (name-based, content-based; compressed originals already moved above)
                if extraction_folder:
                    extract_duplicates_to_folder(str(self.folder_path), extraction_folder)
                
                if SYSTEM_LANGUAGE == 'fr':
                    print("\n✅ Analyse terminée avec succès !")
                    self.finished_signal.emit(True, "Analyse terminée", self.output_folder, data_by_target, global_data)
                else:
                    print("\n✅ Analysis completed successfully!")
                    self.finished_signal.emit(True, "Analysis completed", self.output_folder, data_by_target, global_data)
                
            except Exception as e:
                print(f"\n❌ Error: {str(e)}")
                traceback.print_exc()
                self.finished_signal.emit(False, str(e), self.output_folder or "", None, None)
            finally:
                sys.stdout = old_stdout
                clear_progress_callback()
                clear_header_cache()
        
        def stop(self):
            self.should_stop = True
    
    
    class FitsAnalyserGUI(QMainWindow):
        """Main GUI Window"""
        
        def __init__(self):
            super().__init__()
            self.lang = SYSTEM_LANGUAGE
            self.output_folder = None
            self.worker = None
            self.last_browse_folder = self._get_default_folder()
            self.init_ui()
        
        def _get_default_folder(self):
            """Get the default folder for file dialogs (script's directory)"""
            try:
                # Get the directory where the script is located
                script_dir = os.path.dirname(os.path.abspath(__file__))
                if os.path.isdir(script_dir):
                    return script_dir
            except Exception:
                pass
            
            # Fallback to current working directory
            try:
                cwd = os.getcwd()
                if os.path.isdir(cwd):
                    return cwd
            except Exception:
                pass
            
            # Last resort: user's home
            return str(Path.home())
        
        def tr(self, key):
            """Translation helper"""
            translations = {
                'fr': {
                    'title': '🔭 Analyseur FITS - Astrophotographie',
                    'folder': 'Dossier à analyser',
                    'browse': 'Parcourir...',
                    'start': '▶ Démarrer',
                    'stop': '⏹ Arrêter',
                    'options': 'Options de sortie',
                    'thumbnails': 'Miniatures',
                    'graphs': 'Graphiques',
                    'latex': 'Rapport LaTeX/PDF',
                    'csv': 'Export CSV',
                    'zip': 'Compression ZIP',
                    'advanced': 'Options avancées',
                    'workers': 'Workers',
                    'auto': 'Auto',
                    'console': 'Console',
                    'results': 'Résultats',
                    'clear': 'Effacer',
                    'open': 'Ouvrir dossier',
                    'ready': 'Prêt',
                    'running': 'Analyse en cours...',
                    'done': 'Terminé',
                    'no_folder': 'Sélectionnez un dossier',
                    'no_results': 'Aucun résultat',
                    'confirm_quit': 'Analyse en cours. Quitter ?',
                    'output_folder': 'Dossier de sortie',
                    'analyzing': 'Analyse de',
                    'starting': 'Démarrage de l\'analyse...',
                    'grouping': 'Regroupement des cibles...',
                    'gen_graphs': 'Génération des graphiques...',
                    'gen_latex': 'Génération du rapport LaTeX...',
                    'export_csv': 'Export CSV...',
                    'compressing': 'Compression...',
                    'complete': 'Analyse terminée avec succès !',
                    'stopped': 'Arrêté par l\'utilisateur',
                    'no_fits': 'Aucun fichier FITS trouvé',
                    'selected': 'Sélectionné',
                    'results_title': 'Résultats de l\'analyse',
                    'files_generated': 'Fichiers générés',
                    'language': 'Langue',
                    'lang_auto': '🌐 Auto (Système)',
                    'lang_fr': '🇫🇷 Français',
                    'lang_en': '🇬🇧 English',
                    'lang_changed': 'Langue changée.',
                    'subtitle': 'Analyse FITS/XISF • Rapports LaTeX • Statistiques',
                    'folder_placeholder': 'Choisir un dossier FITS/XISF...',
                    # Tooltips
                    'thumbnails_tip': 'Génère des miniatures d\'aperçu pour chaque image traitée',
                    'graphs_tip': 'Crée des graphiques de statistiques (histogrammes, temps de pose, etc.)',
                    'latex_tip': 'Produit un rapport LaTeX/PDF détaillé avec toutes les statistiques',
                    'workers_tip': 'Nombre de workers en parallèle (0 = automatique selon le nombre de cœurs)',
                    'language_tip': 'Choisit la langue de l\'interface (Auto = langue du système)',
                    'browse_tip': 'Sélectionner le dossier contenant vos fichiers FITS/XISF',
                    'start_tip': 'Lancer l\'analyse complète du dossier sélectionné',
                    'stop_tip': 'Arrêter proprement l\'analyse en cours',
                    'clear_tip': 'Effacer le contenu de la console',
                    'open_tip': 'Ouvrir le dossier de sortie contenant les rapports générés',
                    'file_management': 'Gestion des fichiers',
                    'compress_fits': '🗜️ Compresser FITS → XISF',
                    'compress_fits_tip': 'Compresse les FITS non compressés en XISF (zlib-6, byte-shuffle, vérifié SHA-256)',
                    'resolve_simbad': '🌐 Résoudre les cibles via SIMBAD',
                    'resolve_simbad_tip': 'Fusionne les doublons de cibles (ex. M31 = NGC 224) et récupère type/coordonnées via la base SIMBAD',
                    'extract_duplicates': '📦 Extraire les doublons',
                    'extract_duplicates_tip': 'Déplace les fichiers en double vers un dossier externe (arborescence préservée)',
                    'prefer_format': 'Format préféré:',
                    'prefer_xisf': 'XISF (compressé)',
                    'prefer_fits': 'FITS (original)',
                    'prefer_fz': 'FITS.FZ (fpack)',
                    'astrobin_csv': '🌟 Export AstroBin CSV',
                    'astrobin_csv_tip': 'Génère un fichier CSV compatible avec l\'import AstroBin',
                    # Menu Aide
                    'menu_help': 'Aide',
                    'help_about': 'À propos',
                    'help_usage': 'Guide d\'utilisation',
                    'help_latex': 'Installation LaTeX',
                    'help_features': 'Fonctionnalités',
                },
                'en': {
                    'title': '🔭 FITS Analyser - Astrophotography',
                    'folder': 'Folder to analyze',
                    'browse': 'Browse...',
                    'start': '▶ Start',
                    'stop': '⏹ Stop',
                    'options': 'Output Options',
                    'thumbnails': 'Thumbnails',
                    'graphs': 'Graphs',
                    'latex': 'LaTeX/PDF Report',
                    'csv': 'CSV Export',
                    'zip': 'ZIP Compression',
                    'advanced': 'Advanced Options',
                    'workers': 'Workers',
                    'auto': 'Auto',
                    'console': 'Console',
                    'results': 'Results',
                    'clear': 'Clear',
                    'open': 'Open folder',
                    'ready': 'Ready',
                    'running': 'Analyzing...',
                    'done': 'Done',
                    'no_folder': 'Select a folder',
                    'no_results': 'No results',
                    'confirm_quit': 'Analysis running. Quit?',
                    'output_folder': 'Output folder',
                    'analyzing': 'Analyzing',
                    'starting': 'Starting analysis...',
                    'grouping': 'Grouping targets...',
                    'gen_graphs': 'Generating graphs...',
                    'gen_latex': 'Generating LaTeX report...',
                    'export_csv': 'Exporting CSV...',
                    'compressing': 'Compressing...',
                    'complete': 'Analysis completed successfully!',
                    'stopped': 'Stopped by user',
                    'language': 'Language',
                    'lang_auto': '🌐 Auto (System)',
                    'lang_fr': '🇫🇷 Français',
                    'lang_en': '🇬🇧 English',
                    'lang_changed': 'Language changed.',
                    'subtitle': 'FITS/XISF Analysis • LaTeX Reports • Statistics',
                    'folder_placeholder': 'Select FITS/XISF folder...',
                    'no_fits': 'No FITS files found',
                    'selected': 'Selected',
                    'results_title': 'Analysis Results',
                    'files_generated': 'Files generated',
                    'file_management': 'File Management',
                    'compress_fits': '🗜️ Compress FITS → XISF',
                    'compress_fits_tip': 'Compress uncompressed FITS to XISF (zlib-6, byte-shuffle, SHA-256 verified)',
                    'resolve_simbad': '🌐 Resolve targets via SIMBAD',
                    'resolve_simbad_tip': 'Merge duplicate targets (e.g. M31 = NGC 224) and fetch type/coordinates from SIMBAD',
                    'extract_duplicates': '📦 Extract duplicates',
                    'extract_duplicates_tip': 'Move duplicate files to external folder (preserves directory structure)',
                    'prefer_format': 'Preferred format:',
                    'prefer_xisf': 'XISF (compressed)',
                    'prefer_fits': 'FITS (original)',
                    'prefer_fz': 'FITS.FZ (fpack)',
                    'astrobin_csv': '🌟 AstroBin CSV Export',
                    'astrobin_csv_tip': 'Generate CSV file compatible with AstroBin import',
                    # Tooltips
                    'thumbnails_tip': 'Generate preview thumbnails for each processed image',
                    'graphs_tip': 'Create statistical graphs (histograms, exposure time, etc.)',
                    'latex_tip': 'Produce a detailed LaTeX/PDF report with all statistics',
                    'workers_tip': 'Number of parallel workers (0 = automatic based on CPU cores)',
                    'language_tip': 'Select the interface language (Auto = system language)',
                    'browse_tip': 'Select the folder containing your FITS/XISF files',
                    'start_tip': 'Start the full analysis of the selected folder',
                    'stop_tip': 'Safely stop the running analysis',
                    'clear_tip': 'Clear console output',
                    'open_tip': 'Open the output folder with generated reports',
                    # Help Menu
                    'menu_help': 'Help',
                    'help_about': 'About',
                    'help_usage': 'Usage Guide',
                    'help_latex': 'LaTeX Installation',
                    'help_features': 'Features',
                }
            }
            return translations.get(self.lang, translations['en']).get(key, key)
        
        def init_ui(self):
            self.setWindowTitle(self.tr('title'))
            # Minimum and initial size account for progress bar so layout doesn't shift when it appears
            self.setMinimumSize(950, 760)
            self.resize(1200, 880)
            
            # Create menu bar (keep refs for language update)
            menubar = self.menuBar()
            self.help_menu = menubar.addMenu(self.tr('menu_help'))
            self.about_action = self.help_menu.addAction(self.tr('help_about'))
            self.about_action.triggered.connect(self.show_help_about)
            self.usage_action = self.help_menu.addAction(self.tr('help_usage'))
            self.usage_action.triggered.connect(self.show_help_usage)
            self.features_action = self.help_menu.addAction(self.tr('help_features'))
            self.features_action.triggered.connect(self.show_help_features)
            self.help_menu.addSeparator()
            self.latex_action = self.help_menu.addAction(self.tr('help_latex'))
            self.latex_action.triggered.connect(self.show_help_latex)
            
            central = QWidget()
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(8)
            
            # Header
            header = QFrame()
            header.setStyleSheet("QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1e3a5f,stop:1 #2d5a87);border-radius:8px;padding:12px;}")
            h_layout = QVBoxLayout(header)
            self.header_title = QLabel(self.tr('title'))
            self.header_title.setStyleSheet("color:white;font-size:18px;font-weight:bold;")
            h_layout.addWidget(self.header_title)
            self.header_subtitle = QLabel(self.tr('subtitle'))
            self.header_subtitle.setStyleSheet("color:#a0c4e8;font-size:11px;")
            h_layout.addWidget(self.header_subtitle)
            layout.addWidget(header)
            
            # Folder selection
            self.folder_group = QGroupBox(self.tr('folder'))
            folder_layout = QHBoxLayout(self.folder_group)
            self.folder_input = QLineEdit()
            self.folder_input.setPlaceholderText(self.tr('folder_placeholder'))
            self.folder_input.setMinimumHeight(32)
            folder_layout.addWidget(self.folder_input)
            self.browse_btn = QPushButton(self.tr('browse'))
            self.browse_btn.setToolTip(self.tr('browse_tip'))
            self.browse_btn.setMinimumHeight(32)
            self.browse_btn.clicked.connect(self.browse_folder)
            folder_layout.addWidget(self.browse_btn)
            layout.addWidget(self.folder_group)
            
            # Main splitter
            splitter = QSplitter(Qt.Orientation.Horizontal)
            
            # Left panel - Options (scrollable to avoid overlap when window is narrow)
            left = QWidget()
            left.setMinimumWidth(220)
            left_layout = QVBoxLayout(left)
            left_layout.setContentsMargins(0, 0, 0, 0)
            
            self.opt_group = QGroupBox(self.tr('options'))
            opt_layout = QVBoxLayout(self.opt_group)
            self.cb_thumb = QCheckBox(self.tr('thumbnails'))
            self.cb_graph = QCheckBox(self.tr('graphs'))
            self.cb_graph.setToolTip(self.tr('graphs_tip'))
            self.cb_graph.setChecked(True)
            self.cb_latex = QCheckBox(self.tr('latex'))
            self.cb_latex.setToolTip(self.tr('latex_tip'))
            self.cb_latex.setChecked(True)
            self.cb_thumb.setToolTip(self.tr('thumbnails_tip'))
            self.cb_astrobin = QCheckBox(self.tr('astrobin_csv'))
            self.cb_astrobin.setToolTip(self.tr('astrobin_csv_tip'))
            self.cb_astrobin.setChecked(True)
            opt_layout.addWidget(self.cb_thumb)
            opt_layout.addWidget(self.cb_graph)
            opt_layout.addWidget(self.cb_latex)
            opt_layout.addWidget(self.cb_astrobin)
            left_layout.addWidget(self.opt_group)
            
            # File management options
            self.file_group = QGroupBox(self.tr('file_management'))
            file_layout = QVBoxLayout(self.file_group)
            
            # Compress FITS checkbox
            self.cb_compress_fits = QCheckBox(self.tr('compress_fits'))
            self.cb_compress_fits.setToolTip(self.tr('compress_fits_tip'))
            file_layout.addWidget(self.cb_compress_fits)
            self.cb_resolve_simbad = QCheckBox(self.tr('resolve_simbad'))
            self.cb_resolve_simbad.setToolTip(self.tr('resolve_simbad_tip'))
            file_layout.addWidget(self.cb_resolve_simbad)
            
            # Extract duplicates checkbox
            self.cb_extract_duplicates = QCheckBox(self.tr('extract_duplicates'))
            self.cb_extract_duplicates.setToolTip(self.tr('extract_duplicates_tip'))
            self.cb_extract_duplicates.stateChanged.connect(self.on_extract_duplicates_changed)
            file_layout.addWidget(self.cb_extract_duplicates)
            
            # Format preference combo (enabled only when extract is checked)
            format_layout = QHBoxLayout()
            format_layout.addSpacing(20)
            self.format_label = QLabel(self.tr('prefer_format'))
            self.format_label.setEnabled(False)
            format_layout.addWidget(self.format_label)
            
            self.format_combo = QComboBox()
            self.format_combo.addItem(self.tr('prefer_xisf'), 'xisf')
            self.format_combo.addItem(self.tr('prefer_fits'), 'fits')
            self.format_combo.addItem(self.tr('prefer_fz'), 'fz')
            self.format_combo.setEnabled(False)
            self.format_combo.setCurrentIndex(0)  # XISF par défaut
            format_layout.addWidget(self.format_combo)
            format_layout.addStretch()
            file_layout.addLayout(format_layout)
            
            left_layout.addWidget(self.file_group)
            
            self.adv_group = QGroupBox(self.tr('advanced'))
            adv_layout = QVBoxLayout(self.adv_group)
            
            # Workers
            w_layout = QHBoxLayout()
            self.workers_label = QLabel(self.tr('workers') + ":")
            w_layout.addWidget(self.workers_label)
            self.workers_spin = QSpinBox()
            self.workers_spin.setToolTip(self.tr('workers_tip'))
            self.workers_spin.setRange(0, 64)
            self.workers_spin.setValue(0)
            self.workers_spin.setSpecialValueText(self.tr('auto'))
            w_layout.addWidget(self.workers_spin)
            w_layout.addStretch()
            adv_layout.addLayout(w_layout)
            
            # Language selector
            lang_layout = QHBoxLayout()
            self.lang_label = QLabel(self.tr('language') + ":")
            lang_layout.addWidget(self.lang_label)
            self.lang_combo = QComboBox()
            self.lang_combo.setToolTip(self.tr('language_tip'))
            self.lang_combo.addItem(self.tr('lang_auto'), 'auto')
            self.lang_combo.addItem(self.tr('lang_fr'), 'fr')
            self.lang_combo.addItem(self.tr('lang_en'), 'en')
            # Set current language
            current_lang = get_language()
            if current_lang == 'fr':
                self.lang_combo.setCurrentIndex(1)
            elif current_lang == 'en':
                self.lang_combo.setCurrentIndex(2)
            else:
                self.lang_combo.setCurrentIndex(0)
            self.lang_combo.currentIndexChanged.connect(self.on_language_changed)
            lang_layout.addWidget(self.lang_combo)
            lang_layout.addStretch()
            adv_layout.addLayout(lang_layout)
            
            left_layout.addWidget(self.adv_group)
            left_layout.addStretch()
            
            # Wrap left panel in scroll area so options don't overlap when window is narrow
            left_scroll = QScrollArea()
            left_scroll.setWidget(left)
            left_scroll.setWidgetResizable(True)
            left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            left_scroll.setFrameShape(QFrame.Shape.NoFrame)
            left_scroll.setMinimumWidth(200)
            splitter.addWidget(left_scroll)
            
            # Right panel - Console
            right = QWidget()
            right_layout = QVBoxLayout(right)
            right_layout.setContentsMargins(0, 0, 0, 0)
            
            self.tabs = QTabWidget()
            
            console_tab = QWidget()
            console_layout = QVBoxLayout(console_tab)
            self.console = QTextEdit()
            self.console.setReadOnly(True)
            self.console.setFont(QFont('Consolas', 9))
            self.console.setStyleSheet("QTextEdit{background:#1a1a2e;color:#00ff88;border:1px solid #333;border-radius:4px;}")
            console_layout.addWidget(self.console)
            self.clear_btn = QPushButton("🗑 " + self.tr('clear'))
            self.clear_btn.setToolTip(self.tr('clear_tip'))
            self.clear_btn.clicked.connect(self.console.clear)
            console_layout.addWidget(self.clear_btn)
            self.tabs.addTab(console_tab, "📋 " + self.tr('console'))
            
            results_tab = QWidget()
            results_layout = QVBoxLayout(results_tab)
            self.results_text = QTextEdit()
            self.results_text.setReadOnly(True)
            results_layout.addWidget(self.results_text)
            self.open_btn = QPushButton("📂 " + self.tr('open'))
            self.open_btn.setToolTip(self.tr('open_tip'))
            self.open_btn.clicked.connect(self.open_output)
            self.open_btn.setEnabled(False)
            results_layout.addWidget(self.open_btn)
            self.tabs.addTab(results_tab, "📊 " + self.tr('results'))
            
            right_layout.addWidget(self.tabs)
            splitter.addWidget(right)
            splitter.setSizes([250, 650])
            layout.addWidget(splitter, 1)
            
            # Progress section - always in layout with fixed height so options don't get squashed when it appears
            progress_frame = QFrame()
            progress_frame.setStyleSheet("QFrame{background:#1a1a2e;border-radius:5px;padding:8px;border:1px solid #333;}")
            progress_frame.setMinimumHeight(102)
            progress_frame.setMaximumHeight(102)
            progress_layout = QVBoxLayout(progress_frame)
            progress_layout.setContentsMargins(10, 6, 10, 6)
            
            self.progress_label = QLabel("")
            self.progress_label.setStyleSheet("font-weight:bold;color:#00ff88;")
            self.progress_label.setMinimumHeight(30)
            self.progress_label.setWordWrap(True)
            progress_layout.addWidget(self.progress_label)
            
            self.progress = QProgressBar()
            self.progress.setMinimum(0)
            self.progress.setMaximum(100)
            self.progress.setValue(0)
            self.progress.setTextVisible(True)
            self.progress.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #444;
                    border-radius: 5px;
                    text-align: center;
                    background: #2d2d44;
                    height: 22px;
                    color: #00ff88;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #2e7d32, stop:1 #4CAF50);
                    border-radius: 4px;
                }
            """)
            progress_layout.addWidget(self.progress)
            
            self.progress_frame = progress_frame
            layout.addWidget(progress_frame)
            
            # Buttons
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            self.stop_btn = QPushButton(self.tr('stop'))
            self.stop_btn.setToolTip(self.tr('stop_tip'))
            self.stop_btn.setStyleSheet("background:#dc3545;color:white;font-weight:bold;padding:8px 20px;")
            self.stop_btn.clicked.connect(self.stop_analysis)
            self.stop_btn.hide()
            btn_layout.addWidget(self.stop_btn)
            self.start_btn = QPushButton(self.tr('start'))
            self.start_btn.setToolTip(self.tr('start_tip'))
            self.start_btn.setStyleSheet("background:#28a745;color:white;font-weight:bold;padding:8px 30px;")
            self.start_btn.clicked.connect(self.start_analysis)
            btn_layout.addWidget(self.start_btn)
            layout.addLayout(btn_layout)
            
            # Status bar
            self.status = QStatusBar()
            self.setStatusBar(self.status)
            self.status.showMessage(self.tr('ready'))
        
        def browse_folder(self):
            # Use last browsed folder, or current input if it exists
            start_folder = self.last_browse_folder
            current_input = self.folder_input.text().strip()
            if current_input and os.path.isdir(current_input):
                start_folder = current_input
            elif current_input:
                # Try parent folder if current doesn't exist
                parent = os.path.dirname(current_input)
                if parent and os.path.isdir(parent):
                    start_folder = parent
            
            folder = QFileDialog.getExistingDirectory(
                self, 
                self.tr('folder'), 
                start_folder,
                QFileDialog.Option.ShowDirsOnly
            )
            if folder:
                self.folder_input.setText(folder)
                self.last_browse_folder = folder  # Remember for next time
                self.log(f"📁 {self.tr('selected')}: {folder}")
        
        def log(self, msg):
            clean = re.sub(r'\x1b\[[0-9;]*m', '', str(msg))
            self.console.append(clean.rstrip())
            cursor = self.console.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.console.setTextCursor(cursor)
        
        def start_analysis(self):
            folder = self.folder_input.text().strip()
            if not folder or not os.path.isdir(folder):
                QMessageBox.warning(self, "Warning", self.tr('no_folder'))
                return
            
            options = {
                'generate_thumbnails': self.cb_thumb.isChecked(),
                'generate_graphs': self.cb_graph.isChecked(),
                'generate_latex': self.cb_latex.isChecked(),
                'export_astrobin': self.cb_astrobin.isChecked(),
                'workers': self.workers_spin.value(),
                'compress_fits': self.cb_compress_fits.isChecked(),
                'resolve_simbad': self.cb_resolve_simbad.isChecked(),
                'extract_duplicates': self.cb_extract_duplicates.isChecked(),
                'prefer_format': self.format_combo.currentData() if self.cb_extract_duplicates.isChecked() else 'xisf',
            }
            
            # Clear detected duplicates from previous run
            clear_detected_duplicates()
            
            self.start_btn.hide()
            self.stop_btn.show()
            self.progress.setMaximum(100)
            self.progress.setValue(0)
            self.progress_label.setText("Initialisation..." if SYSTEM_LANGUAGE == 'fr' else "Initializing...")
            self.progress_frame.show()
            self.status.showMessage(self.tr('running'))
            self.tabs.setCurrentIndex(0)
            
            self.log("\n" + "=" * 50)
            if SYSTEM_LANGUAGE == 'fr':
                self.log("🚀 Démarrage de l'analyse...")
            else:
                self.log("🚀 Starting analysis...")
            self.log("=" * 50 + "\n")
            
            self.worker = AnalysisWorker(folder, options)
            self.worker.output_signal.connect(self.log)
            self.worker.progress_signal.connect(self.update_progress)
            self.worker.finished_signal.connect(self.on_finished)
            self.worker.start()
        
        def update_progress(self, current, total, phase):
            """Met à jour la barre de progression"""
            if total > 0:
                self.progress.setMaximum(total)
                self.progress.setValue(current)
                
                # Format du message selon la phase
                percent = int(100 * current / total)
                if phase == "phase2":
                    phase_name = "📋 Phase 2: Signatures" if SYSTEM_LANGUAGE == 'fr' else "📋 Phase 2: Signatures"
                elif phase == "phase3":
                    phase_name = "📂 Phase 3: Headers" if SYSTEM_LANGUAGE == 'fr' else "📂 Phase 3: Headers"
                elif phase == "phase4":
                    phase_name = "⚡ Phase 4: Analyse" if SYSTEM_LANGUAGE == 'fr' else "⚡ Phase 4: Analysis"
                elif phase == "phase5":
                    phase_name = "🗜️ Phase 5: Compression" if SYSTEM_LANGUAGE == 'fr' else "🗜️ Phase 5: Compression"
                else:
                    phase_name = phase
                
                self.progress_label.setText(f"{phase_name}: {current}/{total} ({percent}%)")
                self.status.showMessage(f"{phase_name}: {percent}%")
            else:
                # Mode indéterminé
                self.progress.setMaximum(0)
                self.progress_label.setText("Traitement en cours..." if SYSTEM_LANGUAGE == 'fr' else "Processing...")
        
        def stop_analysis(self):
            if self.worker:
                self.worker.stop()
                if SYSTEM_LANGUAGE == 'fr':
                    self.log("\n⚠️ Arrêt demandé...")
                else:
                    self.log("\n⚠️ Stop requested...")
        
        def on_extract_duplicates_changed(self, state):
            """Enable/disable format combo when extract duplicates is checked"""
            enabled = state == 2  # Qt.Checked
            self.format_label.setEnabled(enabled)
            self.format_combo.setEnabled(enabled)
        
        def show_help_about(self):
            """Show About dialog"""
            if SYSTEM_LANGUAGE == 'fr':
                title = "À propos de FITS Analyser"
                text = """<h2>🔭 FITS Analyser</h2>
                <p><b>Version:</b> 2.0</p>
                <p><b>Auteur:</b> ARP273-ROSE</p>
                <p>Analyseur complet pour l'astrophotographie.<br>
                Analyse les fichiers FITS et XISF, génère des rapports<br>
                détaillés en PDF et HTML, et optimise le stockage.</p>
                <p><b>Formats supportés:</b> .fits, .fit, .xisf, .fits.fz</p>"""
            else:
                title = "About FITS Analyser"
                text = """<h2>🔭 FITS Analyser</h2>
                <p><b>Version:</b> 2.0</p>
                <p><b>Author:</b> ARP273-ROSE</p>
                <p>Complete analyzer for astrophotography.<br>
                Analyzes FITS and XISF files, generates detailed<br>
                PDF and HTML reports, and optimizes storage.</p>
                <p><b>Supported formats:</b> .fits, .fit, .xisf, .fits.fz</p>"""
            
            QMessageBox.about(self, title, text)
        
        def show_help_usage(self):
            """Show Usage Guide dialog"""
            if SYSTEM_LANGUAGE == 'fr':
                title = "Guide d'utilisation"
                text = """<h2>📖 Guide d'utilisation</h2>
                
                <h3>1. Sélection du dossier</h3>
                <p>Cliquez sur "Parcourir" pour sélectionner un dossier contenant vos fichiers FITS/XISF.</p>
                
                <h3>2. Options de sortie</h3>
                <ul>
                <li><b>Miniatures:</b> Génère des aperçus des images</li>
                <li><b>Graphiques:</b> Crée des graphiques de statistiques</li>
                <li><b>Rapport LaTeX/PDF:</b> Génère un rapport professionnel</li>
                <li><b>Export AstroBin:</b> Crée un CSV compatible AstroBin</li>
                </ul>
                
                <h3>3. Gestion des fichiers</h3>
                <ul>
                <li><b>Compresser FITS→XISF:</b> Convertit les FITS en XISF compressé (zlib-6)</li>
                <li><b>Extraire doublons:</b> Déplace les fichiers en double vers un dossier externe</li>
                </ul>
                
                <h3>4. Lancement</h3>
                <p>Cliquez sur "▶ Démarrer" pour lancer l'analyse. Les résultats seront dans le dossier analysé.</p>"""
            else:
                title = "Usage Guide"
                text = """<h2>📖 Usage Guide</h2>
                
                <h3>1. Folder Selection</h3>
                <p>Click "Browse" to select a folder containing your FITS/XISF files.</p>
                
                <h3>2. Output Options</h3>
                <ul>
                <li><b>Thumbnails:</b> Generate image previews</li>
                <li><b>Graphs:</b> Create statistical charts</li>
                <li><b>LaTeX/PDF Report:</b> Generate a professional report</li>
                <li><b>AstroBin Export:</b> Create AstroBin-compatible CSV</li>
                </ul>
                
                <h3>3. File Management</h3>
                <ul>
                <li><b>Compress FITS→XISF:</b> Convert FITS to compressed XISF (zlib-6)</li>
                <li><b>Extract duplicates:</b> Move duplicate files to external folder</li>
                </ul>
                
                <h3>4. Launch</h3>
                <p>Click "▶ Start" to begin analysis. Results will be in the analyzed folder.</p>"""
            
            msg = QMessageBox(self)
            msg.setWindowTitle(title)
            msg.setTextFormat(Qt.TextFormat.RichText)
            msg.setText(text)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
        
        def show_help_latex(self):
            """Show LaTeX Installation guide"""
            if SYSTEM_LANGUAGE == 'fr':
                title = "Installation de LaTeX"
                text = """<h2>🔧 Installation de LaTeX</h2>
                
                <h3>Windows</h3>
                <p>Installez <b>MiKTeX</b>:</p>
                <ol>
                <li>Téléchargez depuis <a href="https://miktex.org/download">miktex.org/download</a></li>
                <li>Exécutez l'installateur</li>
                <li>Choisissez "Install missing packages on-the-fly: Yes"</li>
                </ol>
                
                <h3>macOS</h3>
                <p>Installez <b>MacTeX</b>:</p>
                <ol>
                <li>Téléchargez depuis <a href="https://www.tug.org/mactex/">tug.org/mactex</a></li>
                <li>Ouvrez le fichier .pkg et suivez les instructions</li>
                </ol>
                
                <h3>Linux (Ubuntu/Debian)</h3>
                <pre>sudo apt-get install texlive-full</pre>
                <p>Ou version minimale:</p>
                <pre>sudo apt-get install texlive-latex-base texlive-fonts-recommended texlive-latex-extra</pre>
                
                <h3>Linux (Fedora/RHEL)</h3>
                <pre>sudo dnf install texlive-scheme-full</pre>
                
                <h3>Linux (Arch)</h3>
                <pre>sudo pacman -S texlive-most</pre>
                
                <p><i>Note: Si LaTeX n'est pas installé, le programme génère un PDF basique avec ReportLab.</i></p>"""
            else:
                title = "LaTeX Installation"
                text = """<h2>🔧 LaTeX Installation</h2>
                
                <h3>Windows</h3>
                <p>Install <b>MiKTeX</b>:</p>
                <ol>
                <li>Download from <a href="https://miktex.org/download">miktex.org/download</a></li>
                <li>Run the installer</li>
                <li>Choose "Install missing packages on-the-fly: Yes"</li>
                </ol>
                
                <h3>macOS</h3>
                <p>Install <b>MacTeX</b>:</p>
                <ol>
                <li>Download from <a href="https://www.tug.org/mactex/">tug.org/mactex</a></li>
                <li>Open the .pkg file and follow instructions</li>
                </ol>
                
                <h3>Linux (Ubuntu/Debian)</h3>
                <pre>sudo apt-get install texlive-full</pre>
                <p>Or minimal version:</p>
                <pre>sudo apt-get install texlive-latex-base texlive-fonts-recommended texlive-latex-extra</pre>
                
                <h3>Linux (Fedora/RHEL)</h3>
                <pre>sudo dnf install texlive-scheme-full</pre>
                
                <h3>Linux (Arch)</h3>
                <pre>sudo pacman -S texlive-most</pre>
                
                <p><i>Note: If LaTeX is not installed, the program generates a basic PDF with ReportLab.</i></p>"""
            
            msg = QMessageBox(self)
            msg.setWindowTitle(title)
            msg.setTextFormat(Qt.TextFormat.RichText)
            msg.setText(text)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
        
        def show_help_features(self):
            """Show Features dialog"""
            if SYSTEM_LANGUAGE == 'fr':
                title = "Fonctionnalités"
                text = """<h2>✨ Fonctionnalités</h2>
                
                <h3>📊 Analyse</h3>
                <ul>
                <li>Analyse des headers FITS et XISF</li>
                <li>Détection automatique des cibles, filtres, instruments</li>
                <li>Statistiques par nuit, par filtre, par temps de pose</li>
                <li>Détection des panneaux de mosaïque</li>
                <li>Calcul du temps total d'observation</li>
                </ul>
                
                <h3>📄 Rapports</h3>
                <ul>
                <li>Rapport PDF professionnel (LaTeX)</li>
                <li>Rapport HTML interactif</li>
                <li>Export CSV compatible AstroBin</li>
                <li>Graphiques de répartition par filtre</li>
                </ul>
                
                <h3>🗜️ Optimisation du stockage</h3>
                <ul>
                <li>Compression FITS→XISF (60-70% de gain)</li>
                <li>Vérification SHA-256 de l'intégrité</li>
                <li>Détection des doublons par signature</li>
                <li>Extraction avec arborescence préservée</li>
                </ul>
                
                <h3>⚡ Performance</h3>
                <ul>
                <li>Traitement multi-cœurs optimisé</li>
                <li>Cache des headers pour éviter les relectures</li>
                <li>Détection SSD/HDD pour ajuster les workers</li>
                </ul>"""
            else:
                title = "Features"
                text = """<h2>✨ Features</h2>
                
                <h3>📊 Analysis</h3>
                <ul>
                <li>FITS and XISF header analysis</li>
                <li>Automatic detection of targets, filters, instruments</li>
                <li>Statistics by night, filter, exposure time</li>
                <li>Mosaic panel detection</li>
                <li>Total observation time calculation</li>
                </ul>
                
                <h3>📄 Reports</h3>
                <ul>
                <li>Professional PDF report (LaTeX)</li>
                <li>Interactive HTML report</li>
                <li>AstroBin-compatible CSV export</li>
                <li>Filter distribution charts</li>
                </ul>
                
                <h3>🗜️ Storage Optimization</h3>
                <ul>
                <li>FITS→XISF compression (60-70% savings)</li>
                <li>SHA-256 integrity verification</li>
                <li>Duplicate detection by signature</li>
                <li>Extraction with preserved directory structure</li>
                </ul>
                
                <h3>⚡ Performance</h3>
                <ul>
                <li>Optimized multi-core processing</li>
                <li>Header caching to avoid re-reading</li>
                <li>SSD/HDD detection to adjust workers</li>
                </ul>"""
            
            msg = QMessageBox(self)
            msg.setWindowTitle(title)
            msg.setTextFormat(Qt.TextFormat.RichText)
            msg.setText(text)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
        
        def update_ui_language(self):
            """Refresh all UI strings from current language (call after changing self.lang)."""
            self.setWindowTitle(self.tr('title'))
            self.help_menu.setTitle(self.tr('menu_help'))
            self.about_action.setText(self.tr('help_about'))
            self.usage_action.setText(self.tr('help_usage'))
            self.features_action.setText(self.tr('help_features'))
            self.latex_action.setText(self.tr('help_latex'))
            self.header_title.setText(self.tr('title'))
            self.header_subtitle.setText(self.tr('subtitle'))
            self.folder_group.setTitle(self.tr('folder'))
            self.folder_input.setPlaceholderText(self.tr('folder_placeholder'))
            self.browse_btn.setText(self.tr('browse'))
            self.opt_group.setTitle(self.tr('options'))
            self.cb_thumb.setText(self.tr('thumbnails'))
            self.cb_graph.setText(self.tr('graphs'))
            self.cb_latex.setText(self.tr('latex'))
            self.cb_astrobin.setText(self.tr('astrobin_csv'))
            self.cb_astrobin.setToolTip(self.tr('astrobin_csv_tip'))
            self.file_group.setTitle(self.tr('file_management'))
            self.cb_compress_fits.setText(self.tr('compress_fits'))
            self.cb_compress_fits.setToolTip(self.tr('compress_fits_tip'))
            self.cb_resolve_simbad.setText(self.tr('resolve_simbad'))
            self.cb_resolve_simbad.setToolTip(self.tr('resolve_simbad_tip'))
            self.cb_extract_duplicates.setText(self.tr('extract_duplicates'))
            self.cb_extract_duplicates.setToolTip(self.tr('extract_duplicates_tip'))
            self.format_label.setText(self.tr('prefer_format'))
            self.format_combo.setItemText(0, self.tr('prefer_xisf'))
            self.format_combo.setItemText(1, self.tr('prefer_fits'))
            self.format_combo.setItemText(2, self.tr('prefer_fz'))
            self.adv_group.setTitle(self.tr('advanced'))
            self.workers_label.setText(self.tr('workers') + ":")
            self.workers_spin.setSpecialValueText(self.tr('auto'))
            self.lang_label.setText(self.tr('language') + ":")
            self.lang_combo.blockSignals(True)
            self.lang_combo.setItemText(0, self.tr('lang_auto'))
            self.lang_combo.setItemText(1, self.tr('lang_fr'))
            self.lang_combo.setItemText(2, self.tr('lang_en'))
            self.lang_combo.blockSignals(False)
            self.clear_btn.setText("🗑 " + self.tr('clear'))
            self.open_btn.setText("📂 " + self.tr('open'))
            self.tabs.setTabText(0, "📋 " + self.tr('console'))
            self.tabs.setTabText(1, "📊 " + self.tr('results'))
            self.stop_btn.setText(self.tr('stop'))
            self.start_btn.setText(self.tr('start'))
            self.status.showMessage(self.tr('ready'))
        
        def on_language_changed(self, index):
            """Handle language change from combo box"""
            lang_code = self.lang_combo.currentData()
            new_lang = set_language(lang_code)
            self.lang = new_lang
            
            # Refresh all UI strings to the new language
            self.update_ui_language()
            
            # Log the change
            if new_lang == 'fr':
                self.log("🌐 Langue changée: Français")
            else:
                self.log("🌐 Language changed: English")
            
            self.status.showMessage(self.tr('lang_changed'))
        
        def on_finished(self, success, message, output_folder, data_by_target, global_data):
            self.start_btn.show()
            self.stop_btn.hide()
            # Keep progress frame visible so layout doesn't shift; reset to idle state
            self.progress_label.setText("")
            self.progress.setValue(0)
            self.progress.setMaximum(100)
            
            if success:
                self.status.showMessage(self.tr('done'))
                self.log("\n" + "=" * 50)
                self.log("✅ " + message)
                self.log("=" * 50)
                self.output_folder = output_folder
                if output_folder and os.path.isdir(output_folder):
                    self.open_btn.setEnabled(True)
                    self.update_results(output_folder, data_by_target, global_data)
                    self.tabs.setCurrentIndex(1)
            else:
                self.status.showMessage("Error")
                self.log(f"\n❌ {message}")
        
        def update_results(self, folder, data_by_target=None, global_data=None):
            if not folder or not os.path.isdir(folder):
                return
            
            # Build HTML content
            is_fr = self.lang == 'fr'
            
            # Header
            html = f"""
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; color: #e0e0e0; }}
                h2 {{ color: #00ff88; border-bottom: 2px solid #00ff88; padding-bottom: 5px; }}
                h3 {{ color: #4fc3f7; margin-top: 15px; }}
                .stat-box {{ background: #2d2d44; border-radius: 8px; padding: 10px; margin: 5px 0; }}
                .stat-label {{ color: #888; font-size: 0.9em; }}
                .stat-value {{ color: #00ff88; font-size: 1.2em; font-weight: bold; }}
                .target-card {{ background: #252540; border-left: 3px solid #4fc3f7; padding: 8px 12px; margin: 5px 0; border-radius: 4px; }}
                .target-name {{ color: #4fc3f7; font-weight: bold; font-size: 1.1em; }}
                .target-info {{ color: #aaa; font-size: 0.9em; margin-top: 3px; }}
                .filter-badge {{ display: inline-block; background: #3d3d5c; padding: 2px 8px; border-radius: 10px; margin: 2px; font-size: 0.85em; }}
                .files-list {{ margin-top: 15px; }}
                .file-item {{ padding: 3px 0; }}
                ul {{ list-style-type: none; padding-left: 10px; }}
                li {{ padding: 2px 0; }}
            </style>
            """
            
            # Title
            title_fr = "📊 Résultats de l'analyse"
            title_en = "📊 Analysis Results"
            html += f"<h2>{title_fr if is_fr else title_en}</h2>"
            html += f"<p><b>{'Dossier:' if is_fr else 'Folder:'}</b> {folder}</p>"
            
            # Global statistics
            if global_data:
                stats_title = "📈 Statistiques globales" if is_fr else "📈 Global Statistics"
                html += f"<h3>{stats_title}</h3>"
                html += "<div class='stat-box'>"
                
                total_files = global_data.get('total_files', 0)
                found_targets = global_data.get('found_targets', [])
                used_instruments = global_data.get('used_instruments', [])
                used_telescopes = global_data.get('used_telescopes', [])
                total_time = global_data.get('total_time', 0)
                
                lbl_files = "Fichiers analysés:" if is_fr else "Files analyzed:"
                lbl_targets = "Cibles trouvées:" if is_fr else "Targets found:"
                lbl_equipment = "Équipement utilisé:" if is_fr else "Equipment used:"
                lbl_time = "Temps total d'exposition:" if is_fr else "Total exposure time:"
                used_equipment_count = len(sorted(set((used_instruments or []) + (used_telescopes or []))))
                
                html += f"<p><span class='stat-label'>{lbl_files}</span> <span class='stat-value'>{total_files}</span></p>"
                html += f"<p><span class='stat-label'>{lbl_targets}</span> <span class='stat-value'>{len(found_targets)}</span></p>"
                html += f"<p><span class='stat-label'>{lbl_equipment}</span> <span class='stat-value'>{used_equipment_count}</span></p>"
                
                # Format total time
                hours = int(total_time // 3600)
                minutes = int((total_time % 3600) // 60)
                time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                html += f"<p><span class='stat-label'>{lbl_time}</span> <span class='stat-value'>{time_str}</span></p>"
                
                html += "</div>"
            
            # Target details
            if data_by_target:
                details_title = "🎯 Détails par cible" if is_fr else "🎯 Target Details"
                html += f"<h3>{details_title}</h3>"
                
                # Sort targets
                sorted_targets = sorted(data_by_target.items(), key=lambda x: x[0].lower())
                
                for target, data in sorted_targets:
                    if not data.get('files'):
                        continue
                    
                    # Skip calibration targets
                    target_upper = target.upper()
                    if any(cal in target_upper for cal in ['BIAS', 'DARK', 'FLAT', 'CALIBRATION']):
                        continue
                    
                    html += "<div class='target-card'>"
                    html += f"<div class='target-name'>🔭 {target}</div>"
                    
                    # Files count
                    num_files = len(data.get('files', []))
                    html += f"<div class='target-info'>📁 {num_files} {'fichiers' if is_fr else 'files'}"
                    
                    # Total time for this target
                    target_time = 0
                    time_by_filter = data.get('time_by_filter', {})
                    for times in time_by_filter.values():
                        if isinstance(times, list):
                            target_time += sum(times)
                        else:
                            target_time += times
                    
                    if target_time > 0:
                        t_hours = int(target_time // 3600)
                        t_minutes = int((target_time % 3600) // 60)
                        t_str = f"{t_hours}h {t_minutes}m" if t_hours > 0 else f"{t_minutes}m"
                        html += f" | ⏱️ {t_str}"
                    
                    html += "</div>"
                    
                    # Filters
                    filters = list(time_by_filter.keys())
                    if filters:
                        html += "<div class='target-info'>"
                        for f in sorted(filters):
                            html += f"<span class='filter-badge'>{f}</span>"
                        html += "</div>"
                    
                    # Dates
                    dates = data.get('dates', [])
                    if dates:
                        min_date = min(dates) if dates else ''
                        max_date = max(dates) if dates else ''
                        if min_date and max_date:
                            if min_date == max_date:
                                html += f"<div class='target-info'>📅 {min_date}</div>"
                            else:
                                html += f"<div class='target-info'>📅 {min_date} → {max_date}</div>"
                    
                    html += "</div>"
            
            # Files list
            html += f"<h3 class='files-list'>{'📁 Fichiers générés' if is_fr else '📁 Generated Files'}</h3>"
            files = sorted(os.listdir(folder))
            html += "<ul>"
            for f in files:
                icon = "📄"
                if f.endswith('.pdf'): icon = "📕"
                elif f.endswith(('.png', '.jpg')): icon = "🖼️"
                elif f.endswith('.csv'): icon = "📊"
                elif f.endswith('.tex'): icon = "📝"
                elif f.endswith('.zip'): icon = "📦"
                html += f"<li class='file-item'>{icon} {f}</li>"
            html += "</ul>"
            
            self.results_text.setHtml(html)
        
        def open_output(self):
            if self.output_folder and os.path.isdir(self.output_folder):
                if sys.platform == 'win32':
                    os.startfile(self.output_folder)
                elif sys.platform == 'darwin':
                    subprocess.run(['open', self.output_folder])
                else:
                    subprocess.run(['xdg-open', self.output_folder])
        
        def closeEvent(self, event):
            if self.worker and self.worker.isRunning():
                reply = QMessageBox.question(self, "Confirm", "Analysis running. Quit?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self.worker.stop()
                    self.worker.wait(2000)
                    event.accept()
                else:
                    event.ignore()
            else:
                event.accept()


# ============================================================================
# MAIN FUNCTION - GUI/CLI SELECTOR
# ============================================================================

def main():
    """Main function - selects between GUI and CLI mode"""
    
    # Check for CLI mode arguments
    cli_mode = '--cli' in sys.argv or '--folder' in sys.argv or '--help' in sys.argv or '-h' in sys.argv
    
    if cli_mode:
        # Run original CLI mode
        main_cli()
    else:
        # Run GUI mode
        if not PYQT6_AVAILABLE:
            if SYSTEM_LANGUAGE == 'fr':
                print("❌ PyQt6 n'est pas disponible pour le mode GUI.")
                print("   Installez avec : pip install PyQt6")
                print("   Ou utilisez le mode CLI : python script.py --cli --folder /chemin")
                print("\nBasculement vers le mode CLI...\n")
            else:
                print("❌ PyQt6 is not available for GUI mode.")
                print("   Install with: pip install PyQt6")
                print("   Or use CLI mode: python script.py --cli --folder /path")
                print("\nFalling back to CLI mode...\n")
            main_cli()
            return
        
        if SYSTEM_LANGUAGE == 'fr':
            print("🖥️  Lancement de l'interface graphique...")
        else:
            print("🖥️  Launching graphical interface...")
        
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        app.setFont(QFont('Segoe UI', 10))
        
        window = FitsAnalyserGUI()
        window.show()
        
        sys.exit(app.exec())


if __name__ == "__main__":
    main()