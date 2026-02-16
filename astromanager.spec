# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for AstroManager.
Build with:  pyinstaller astromanager.spec --noconfirm
"""

import os
from pathlib import Path

block_cipher = None

# Project root directory (where this .spec file lives)
PROJECT_ROOT = os.path.abspath(SPECPATH)

# ── Data files to bundle inside the .exe ──
# Tuple format: (source_path, destination_directory_in_bundle)
datas = [
    ('assets/icon.ico', 'assets'),
    ('assets/icon.png', 'assets'),
    ('config/default_config.yaml', 'config'),
]

# Include user manuals if they exist
for manual in ('USER_MANUAL_EN.pdf', 'USER_MANUAL_FR.pdf'):
    if Path(os.path.join(PROJECT_ROOT, manual)).exists():
        datas.append((manual, '.'))

# ── Hidden imports ──
# Packages that PyInstaller cannot detect via static analysis.
# Includes local project modules (core, gui, modules, database, fits_analyser_gui)
# that are loaded via dynamic sys.path manipulation.
hiddenimports = [
    # ── Local project modules ──
    'core',
    'core.__init__',
    'core.config',
    'core.database',
    'core.signals',
    'core.workers',
    'core.i18n',
    'gui',
    'gui.__init__',
    'gui.main_window',
    'gui.theme',
    'gui.tabs',
    'gui.tabs.__init__',
    'gui.tabs.analysis_tab',
    'gui.tabs.compression_tab',
    'gui.tabs.asiair_import_tab',
    'gui.tabs.header_editor_tab',
    'gui.tabs.flat_manager_tab',
    'gui.tabs.target_tracking_tab',
    'gui.tabs.disk_space_tab',
    'gui.tabs.history_tab',
    'gui.tabs.database_tab',
    'gui.dialogs',
    'gui.dialogs.__init__',
    'gui.dialogs.bug_report_dialog',
    'modules',
    'modules.__init__',
    'modules.compression',
    'modules.header_editor',
    'modules.flat_manager',
    'modules.plate_solving',
    'modules.weather_api',
    'modules.file_organizer',
    'modules.observation_history',
    'modules.bug_reporter',
    'modules.updater',
    'database',
    'database.__init__',
    'database.cameras',
    'database.telescopes',
    'database.filters',
    'database.targets',
    'fits_analyser_gui',
    # ── Qt ──
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.sip',
    # ── Scientific ──
    'numpy',
    'astropy',
    'astropy.io.fits',
    'astropy.wcs',
    'astropy.coordinates',
    'astropy.units',
    'matplotlib',
    'matplotlib.backends.backend_agg',
    'matplotlib.backends.backend_qtagg',
    'pandas',
    'scipy',
    'scipy.optimize',
    'scipy.stats',
    # ── Image / File ──
    'PIL',
    'PIL.Image',
    'reportlab',
    'reportlab.lib',
    'reportlab.platypus',
    'xisf',
    'defusedxml',
    'defusedxml.ElementTree',
    # ── Compression ──
    'lz4',
    'lz4.block',
    'lz4.frame',
    'zstandard',
    # ── Config / Data ──
    'yaml',
    'sqlite3',
    'zoneinfo',
    # ── System / Network ──
    'psutil',
    'requests',
    'tqdm',
    # ── Astro ──
    'astroquery',
    'astroquery.simbad',
]

# ── Excludes ──
# Reduce bundle size by removing unneeded packages
excludes = [
    'matplotlib.tests',
    'numpy.testing',
    'pytest',
    'IPython',
    'tkinter',
    '_tkinter',
    'sphinx',
    'doctest',
    'pydoc',
    'unittest',
]

a = Analysis(
    ['astromanager.py'],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AstroManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # --windowed: no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AstroManager',
)
