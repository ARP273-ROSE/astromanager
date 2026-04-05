# AstroManager

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

**AstroManager** is a comprehensive, professional-grade file management suite designed specifically for astrophotographers. It combines powerful FITS/XISF analysis, frame quality scoring, universal compression, PixInsight WBPP export, celestial sky charting, observation calendars, calibration matching, and storage optimization — all in a modern, cosmic-themed interface with 15 organized tabs.

---

## Features

### 📊 Universal File Analysis
- Recursive analysis of FITS, XISF, and FITS.FZ files
- Automatic target detection, grouping, and telescope aliasing/merging
- Filter detection (LRGB, narrowband Ha/OIII/SII, OSC, dual narrowband)
- Instrument and telescope identification from built-in databases
- Per-night, per-target, and per-filter statistics
- Mosaic panel detection
- SIMBAD integration for canonical names and object types
- LaTeX/PDF, HTML, CSV, and AstroBin report generation
- AstroBin CSV with automatic filter ID mapping (Ha=4663, OIII=4752, SII=4844, L=2906, R/G/B, NII)

### 🗜️ Multi-Codec Compression
- **9 compression profiles**: zlib (1/6/9), zstd (3/6/10/19), lz4, lz4_hc
- Bidirectional conversion: FITS ↔ XISF ↔ FITS.FZ
- FITS.FZ uses RICE tile compression via Astropy (no external fpack/funpack needed)
- SHA-256 integrity verification
- Parallel processing via ProcessPoolExecutor
- PixInsight full compatibility

### ✏️ Mass Header Editing
- Edit FITS headers across hundreds/thousands of files at once
- NINA-compatible field definitions organized by category
- Filename pattern builder with tokens ($IMAGETYPE$, $TARGETNAME$, $FILTER$, etc.)
- Auto-rename proposal after header changes (filenames reflect updated headers)
- Bulk operations with preview and undo
- Supports FITS, XISF, and FITS.FZ formats

### 📸 Flat Frame Management
- Automatic grouping by date, setup, filter, binning, rotation, temperature
- Coverage reports: complete / insufficient / missing
- Master flat creation and tracking
- Target linking to appropriate flats

### ⭐ Frame Quality Analysis *(New in v1.2.0)*
Inspired by [Athenaeum](https://github.com/eg013ra1n/rustafits)'s PSF analysis pipeline.

- **Star detection**: Automatic peak detection on each FITS/XISF frame using scipy
- **PSF fitting**: 2D elliptical Moffat with Gaussian fallback for each detected star
- **Per-frame metrics**: FWHM, HFR, eccentricity, SNR, star count, background level & noise
- **Quality scoring 0–100**: Weighted composite (FWHM 35%, eccentricity 20%, SNR 20%, stars 15%, roundness 10%)
- **Auto-reject suggestions**: Configurable thresholds, batch-relative outlier detection
- **Satellite trail detection**: Rayleigh R² test for directional coherence of star elongation
- **Star map visualization**: Double-click a frame to see detected stars with PSF shape, elongation direction, and quality color coding
- **Export**: Accepted file list (.txt) and full metrics report (.csv)

### 📦 WBPP Export *(New in v1.2.0)*
Inspired by [Athenaeum](https://github.com/eg013ra1n/rustafits)'s WBPP-ready export with calibration tree visualization.

- **PixInsight WBPP-ready**: Organize files into `Target/LIGHT/Filter/`, `Target/DARK/Exposure_Temp/`, `Target/FLAT/Filter/`, `Target/BIAS/` structure
- **Template tokens**: `{OBJECT}`, `{IMAGETYP}`, `{FILTER}`, `{DATE}`, `{CAMERA}`, `{TELESCOPE}`, `{EXPTIME}`, `{TEMP}`, `{GAIN}`, `{BINNING}`
- **Calibration auto-matching**: Match darks/flats/biases to lights by camera, temperature (±2°C), filter, exposure
- **Calibration scoring**: 8-parameter matching with 3 modes (Exact/Warning/Ignore), quality score 0–1, fallback chains (DarkFlat → Dark → Bias)
- **Preview tree**: Interactive folder tree visualization before export
- **Validation warnings**: Missing calibrations, temperature mismatches, incomplete groups
- **Export modes**: Copy, symlink, or preview-only

### 🎯 Target Tracking Over Time
- Historical observation timeline with bar charts
- Total integration time per target and filter
- Equipment usage statistics with telescope merging
- Best session identification (HFR, FWHM, weather)
- Weather forecast for upcoming nights
- Target visibility and altitude charts
- SIMBAD integration for canonical names
- SQLite database for fast querying

### 🌌 Sky Chart *(New in v1.2.0)*
Inspired by [Athenaeum](https://github.com/eg013ra1n/rustafits)'s interactive sky chart with d3-celestial.

- **Aitoff / Mollweide projection**: Interactive celestial map of all observed targets
- **Color by**: Object type (galaxy, nebula, cluster...), dominant filter, or integration time gradient
- **Size**: Proportional to total integration time per target
- **Milky Way band**: Semi-transparent galactic plane approximation (toggleable)
- **Interactive tooltips**: Hover to see target name, type, RA/Dec, integration time
- **Click to select**: Emits signal for cross-tab navigation
- **Export**: High-resolution PNG (200 DPI)

### 📅 Shoot Calendar *(New in v1.2.0)*
Inspired by [Athenaeum](https://github.com/eg013ra1n/rustafits)'s shoot calendar.

- **Monthly view**: Calendar grid showing frames, integration time, and targets per night
- **Yearly heatmap**: GitHub-style contribution map (52 weeks × 7 days), color intensity = activity
- **Statistics dashboard**: Imaging nights, total integration, best month, avg frames/night, longest streak, unique targets
- **Session details**: Click a day to see per-target breakdown (filter, frames, integration, HFR, FWHM, telescope)
- **Export**: Calendar as PNG

### 📈 Observation History & Statistics
- **Comprehensive dashboard** with 6 stat cards (targets, integration, frames, nights, HFR, telescopes)
- **Target rankings** sorted by total integration time with filters/sessions breakdown
- **Per-filter stats**: usage across targets, sessions, frames, average HFR
- **Equipment stats**: per-telescope, per-camera, and per-setup aggregations
- **Temporal stats**: monthly, yearly, and day-of-week activity breakdowns
- **Best nights**: ranked by quality (HFR) or productivity (integration time)
- **Object type stats**: integration by galaxy, nebula, cluster, etc.
- **Export/Import**: Full JSON export (complete history) or CSV (spreadsheet-compatible)
- **Auto-save**: Database automatically backed up on application exit

### 🔬 PixInsight Log Analysis
- Import and analyze PixInsight WBPP/FBP processing logs
- Per-frame quality metrics (FWHM, SNR, eccentricity, rejection %)
- Integration statistics per filter
- Calibration tracking (master darks, flats, biases used)

### 🔭 Mount Tracking Analysis (MountMonitor)
- Import MountMonitor log files (.dat, .dti, .fft, .env, .log)
- Target segmentation: automatic detection of pointing changes by RA/DEC jumps
- Tracking quality dashboard: RA/DEC RMS deviation, tracking percentage, quality grade (A–F)
- cos(dec) correction for true RA arcseconds on the sky
- TRACKING-only filtering: excludes SLEWING, PARKED, and IDLE samples
- FFT periodic error analysis: dominant PE periods and amplitudes per axis
- Real-time tracking deviation timeline chart
- Per-target statistics table (RMS, range, duration per segment)
- Time synchronization analysis (PC-Mount drift, loop times)
- Environment data correlation (temperature, pressure, alignment)
- Single file or batch folder import

### 🔭 ASIAIR Import
- Raw ASIAIR capture sequence import
- Auto-organization by target, filter, date
- Header fixes for ZWO camera FITS compatibility (BZERO/BSCALE handling)

### 🏷️ Tags & Workflow *(New in v1.2.0)*
Inspired by [Athenaeum](https://github.com/eg013ra1n/rustafits)'s tags and Stage/WIP/Archive workflow.

- **Colored tags**: Create and assign colored tags to targets and observations
- **Workflow stages**: Classify targets as Stage (new data), WIP (processing), or Archive (completed)
- **Database-backed**: Many-to-many relationships, persistent across sessions

### 🧭 DBSCAN Target Clustering *(New in v1.2.0)*
Inspired by [Athenaeum](https://github.com/eg013ra1n/rustafits)'s DBSCAN clustering by celestial coordinates.

- **Coordinate-based clustering**: DBSCAN on RA/Dec using Haversine angular distance
- **Merge suggestions**: Strong (< 5 arcmin) or moderate (< 15 arcmin with name similarity) merge candidates
- **Safe merging**: Dry-run by default, moves observations and recalculates stats
- **Nearby target search**: Find all targets within a given angular radius

### 🔎 Plate Solving *(Optional)*
- ASTAP and Astrometry.net support with auto-detection
- Automatic focal reducer detection (0.67x, 0.72x, 0.8x)
- WCS solution and header updates (REDUCER, corrected FOCAL)
- **Batch solve all lights**: Solve all unsolved raw LIGHT frames (FITS/XISF/FITS.FZ) and write WCS to headers
  - Automatic binning for large images (faster solving)
  - In-place XISF header update (modifies only ~8 KB header, not 60 MB image data)
  - Skips PixInsight processed files, masters, and calibration frames (Dark/Flat/Bias)
  - Uses IMAGETYP/FRAME header keywords for accurate frame type detection

### 🌤️ Weather Integration *(Optional)*
- Historical weather data via Open-Meteo API (free, no API key)
- Temperature, cloud cover, precipitation, wind speed
- 365-day SQLite cache for offline access
- Multi-day weather forecast for session planning

### 💾 Storage Optimization
- Disk space analysis by format (FITS/XISF/FZ/duplicates)
- Duplicate detection: name-based, content-based, compressed pairs
- Optimization recommendations with estimated savings
- File organization with presets (by type, date, target, custom)
- SSD vs HDD detection (Windows WMI, Linux /sys/block, macOS diskutil)

### 🔄 Automatic Update Checker
- Checks GitHub Releases for new versions (opt-in, disabled by default)
- Single HTTPS call to GitHub API, max once per 24 hours
- Non-blocking background check via QThread
- Skip This Version option to dismiss specific releases
- Manual check via Help > Check for Updates
- Fails silently with no internet (5-second timeout)

### 🖥️ Modern Interface
- Cosmic dark theme with muted neon accents
- **15-tab** organized workflow
- Bilingual support (English / French) with auto-detection
- Tooltips on every widget (bilingual)
- Built-in settings dialog (Ctrl+,)
- Built-in user guide (F1) and keyboard shortcuts
- Console output panel with toggle (Ctrl+`)
- Progress bar with phase info and ETA

### ⚡ Performance & Scalability
- **Handles 200,000+ files** efficiently
- Parallel file reading (ThreadPoolExecutor for I/O)
- Parallel compression (ProcessPoolExecutor for CPU)
- Multi-tier caching: Memory → SQLite → Disk
- Auto-detection of system capabilities (CPU, RAM, storage type)
- Auto-tuning of worker count and batch size
- Anonymous crash reporting for continuous improvement

---

## Quick Start

### Recommended: Portable Launcher (NAS / Multi-PC)

```bash
git clone https://github.com/ARP273-ROSE/astromanager.git
cd astromanager

# Windows
launch.bat

# Linux / macOS
chmod +x launch.sh && ./launch.sh
```

The portable launcher scripts (`launch.bat` / `launch.sh`):
- Auto-detect Python on the local machine
- Create a virtual environment **locally** (`%LOCALAPPDATA%\AstroManager\venv` on Windows, `$XDG_DATA_HOME/AstroManager/venv` on Linux)
- Install dependencies automatically
- Launch with `pythonw` (no console window on Windows)
- Work seamlessly when the project folder is on a NAS or synced drive

### Legacy Launcher

The older `run.bat` / `run.sh` scripts still work but create the venv inside the project folder. Use `launch.bat` / `launch.sh` instead for multi-PC portability.

### Manual Installation

```bash
pip install -r requirements.txt
python astromanager.py
```

> **Note:** AstroManager also auto-installs missing dependencies on first launch.

### Standalone Executable (.exe / AppImage)

You can build a self-contained executable that bundles Python, all dependencies, and data files — no installation required.

#### Windows (.exe)

```bash
# From an activated venv with all dependencies installed:
pip install pyinstaller
build.bat
# → dist\AstroManager\AstroManager.exe
```

#### Linux / macOS

```bash
pip install pyinstaller
chmod +x build.sh
./build.sh
# → dist/AstroManager/AstroManager
```

---

## Usage

### 1. 📊 Analysis Tab
1. Click **Browse** and select your FITS/XISF folder
2. Enable options: SIMBAD, Duplicate Detection, Plate Solving, Weather
3. Choose output formats: LaTeX/PDF, HTML, CSV, AstroBin
4. Set workers (0 = auto-detect) and click **Start Analysis**

### 2. 🗜️ Compression Tab
1. Select source and target folders
2. Choose compression profile (`zlib_6` recommended for archival, `lz4` for speed)
3. Enable SHA-256 verification
4. Preview estimated savings and click **Start Compression**

### 3. 🔭 ASIAIR Import Tab
1. Select your ASIAIR capture folder
2. Configure target and organization settings
3. Import and auto-organize by target/filter/date

### 4. ✏️ Header Editor Tab
1. Select files or folder
2. Edit values by category (Acquisition, Camera, Filter, Telescope, etc.)
3. Preview changes, then apply to all files
4. After applying, AstroManager proposes renaming files to match the NINA pattern
5. Use **Undo** if needed

### 5. 📸 Flat Manager Tab
1. Scan your flats library
2. View groups and coverage report
3. Create master flats for incomplete groups
4. Link flats to target light frames

### 6. ⭐ Quality Analysis Tab *(New)*
1. Click **Browse** and select a folder of FITS/XISF light frames
2. Click **Analyze** — each frame is analyzed for star count, FWHM, HFR, eccentricity, SNR
3. Review the results table (color-coded by quality score)
4. Double-click a frame to open the **Star Map** dialog (PSF shapes, elongation)
5. Export accepted file list or full CSV report

### 7. 📦 WBPP Export Tab *(New)*
1. Add light and calibration source folders
2. Set export destination and template pattern
3. Click **Scan** to index all files and auto-match calibrations
4. Review the preview tree and calibration coverage table
5. Click **Export** to copy files into a WBPP-ready structure

### 8. 🎯 Target Tracking Tab
1. Select target from dropdown
2. View observation timeline and integration statistics
3. Check weather forecast for upcoming nights
4. Plan sessions with target visibility charts

### 9. 🌌 Sky Chart Tab *(New)*
1. The map auto-loads all targets with RA/Dec coordinates from the database
2. Toggle grid, Milky Way band, and labels
3. Switch color mode (Object Type / Filter / Integration Time)
4. Hover targets for details, click to select
5. Export the chart as high-resolution PNG

### 10. 📅 Calendar Tab *(New)*
1. Browse monthly or yearly views
2. Click a day to see session details (targets, filters, frames, telescopes)
3. Review statistics: imaging nights, longest streak, best month
4. Export the calendar as PNG

### 11. 🔬 PixInsight Tab
1. Import PixInsight WBPP/FBP processing logs
2. Analyze per-frame quality metrics and integration results

### 12. 🔭 Mount Tracking Tab
1. Click **Import .dat** and select a MountMonitor log file (or **Import Folder** for batch)
2. View tracking quality dashboard: RA/DEC RMS, tracking %, quality grade
3. Analyze tracking deviation timeline chart (RA/DEC over time)
4. Review FFT periodic error peaks (worm gear frequency detection)
5. Browse per-target segment statistics (RMS, range, duration)

### 13. 📈 History & Statistics Tab
1. View global overview (targets, integration time, nights, avg HFR)
2. Browse target rankings, filter stats, equipment usage
3. Explore temporal trends (monthly, yearly, day-of-week)
4. Review best observation nights by quality or productivity
5. Export complete history (JSON) or observations (CSV)

### 14. 📚 Database Browser Tab
1. Browse built-in databases: cameras, telescopes, filters, targets
2. Search by name, filter by brand/type/catalog

### 15. 💾 Disk Space Tab
1. View storage breakdown by format
2. Review optimization recommendations (compression, dedup, archive)
3. Organize files using presets (by type, date, target)

---

## Configuration

### Settings Dialog

Access via **Tools → Settings** or **Ctrl+,**

| Section | Settings |
|---------|----------|
| **General** | Language (auto/en/fr), Check for updates on startup |
| **Observatory** | Latitude, Longitude, Elevation, Timezone |
| **Performance** | Workers (0=auto), Batch size |
| **Compression** | Default profile, Delete source, Verify integrity |
| **Analysis** | SIMBAD, Plate solving, Weather defaults |
| **Bug Reporting** | Enable/disable anonymous crash reports |

### Configuration File

`config.yaml` (in the project directory)

```yaml
application:
  language: "auto"    # auto, en, fr
  theme: "cosmic_dark"

system:
  workers: 0          # 0 = auto-detect
  batch_size: 1000

observatory:
  latitude: 51.4769   # Update for your location!
  longitude: -0.0005
  elevation_m: 46
  timezone: "UTC"

analysis:
  enable_simbad: true
  enable_plate_solving: false
  enable_weather_fetch: false

compression:
  default_profile: "zlib_6"
  verify_integrity: true

plate_solving:
  solver: "astap"     # astap or astrometry

weather:
  api_provider: "open-meteo"
  cache_duration_days: 365

bug_reporting:
  enabled: true
```

### Command-Line Interface

```bash
python astromanager.py                                    # Launch GUI
python astromanager.py --folder /path/to/fits             # CLI analysis
python astromanager.py --folder /path --resolve-simbad    # With SIMBAD
python astromanager.py --folder /path --export-csv        # Export CSV
python astromanager.py --folder /path --workers 8         # 8 workers
python astromanager.py --optimize-storage /backup         # Optimize storage
python astromanager.py --version                          # Show version
python astromanager.py --reset-config                     # Reset config
python astromanager.py --vacuum-db                        # Optimize database
python astromanager.py --debug                            # Debug logging
```

---

## Project Structure

```
astromanager/
├── astromanager.py              # Main launcher (GUI + CLI)
├── fits_analyser_gui.py         # Core analysis engine (19k+ lines)
├── requirements.txt             # Python dependencies
├── launch.bat / launch.sh       # Portable launchers (local venv)
├── run.bat / run.sh             # Legacy launchers
├── build.bat / build.sh         # PyInstaller build scripts
├── astromanager.spec            # PyInstaller spec file
├── LICENSE                      # MIT License
├── USER_MANUAL_EN.pdf           # English user manual
├── USER_MANUAL_FR.pdf           # French user manual
│
├── core/
│   ├── __init__.py              # Version (1.2.0)
│   ├── config.py                # YAML configuration manager
│   ├── database.py              # SQLite (WAL, tags, workflow, quality cache)
│   ├── i18n.py                  # Language detection (auto/en/fr)
│   ├── workers.py               # Unified worker (QThread job queue)
│   ├── signals.py               # Global signal bus (PyQt6)
│   └── updater.py               # Update checker coordinator
│
├── gui/
│   ├── main_window.py           # Main window (15 tabs, menu, console)
│   ├── theme.py                 # Cosmic theme engine + filter normalization
│   ├── dialogs/
│   │   ├── bug_report_dialog.py # Crash report & bug report dialogs
│   │   └── update_dialog.py     # Update notification dialog
│   └── tabs/
│       ├── analysis_tab.py      # 📊 Analysis
│       ├── compression_tab.py   # 🗜️ Compression
│       ├── asiair_import_tab.py # 🔭 ASIAIR Import
│       ├── header_editor_tab.py # ✏️ Header Editor
│       ├── flat_manager_tab.py  # 📸 Flat Manager
│       ├── quality_tab.py       # ⭐ Quality Analysis (NEW)
│       ├── wbpp_export_tab.py   # 📦 WBPP Export (NEW)
│       ├── target_tracking_tab.py # 🎯 Target Tracking
│       ├── sky_chart_tab.py     # 🌌 Sky Chart (NEW)
│       ├── calendar_tab.py      # 📅 Calendar (NEW)
│       ├── pixinsight_tab.py    # 🔬 PixInsight
│       ├── mount_tab.py         # 🔭 Mount Tracking
│       ├── history_tab.py       # 📈 History & Statistics
│       ├── database_tab.py      # 📚 Database Browser
│       └── disk_space_tab.py    # 💾 Disk Space
│
├── modules/
│   ├── compression.py           # Compression engine (9 profiles)
│   ├── header_editor.py         # Header editing engine
│   ├── flat_manager.py          # Flat management engine
│   ├── quality_analysis.py      # Star detection & PSF fitting (NEW)
│   ├── wbpp_export.py           # WBPP file organization (NEW)
│   ├── calibration_scoring.py   # Calibration matching & scoring (NEW)
│   ├── target_clustering.py     # DBSCAN target clustering (NEW)
│   ├── plate_solving.py         # ASTAP/Astrometry.net wrapper
│   ├── weather_api.py           # Open-Meteo weather client
│   ├── observation_history.py   # Observation history stats + export
│   ├── bug_reporter.py          # Anonymous crash reporting
│   ├── updater.py               # GitHub update checker & installer
│   └── file_organizer.py        # File organization with presets
│
├── parsers/
│   ├── base_parser.py           # Data classes and storage functions
│   ├── pixinsight_log_parser.py # PixInsight WBPP/FBP log parser
│   └── mountmonitor_parser.py   # MountMonitor .dat/.dti/.fft/.env parser
│
├── analyzers/
│   ├── pixinsight_analyzer.py   # PixInsight processing analysis
│   └── mount_analyzer.py        # Mount tracking quality analysis
│
├── database/
│   ├── cameras.py               # 1,614 sensors + 2,448 header mappings
│   ├── telescopes.py            # 3,991 models + 6,605 header mappings
│   ├── filters.py               # 1,612 filters + 701 aliases
│   └── targets.py               # 32,923 objects (NGC, IC, Messier, Arp...)
│
└── config/
    └── default_config.yaml      # Default configuration template
```

---

## Built-in Databases (~41,000 entries)

| Database | Entries | Coverage |
|----------|---------|----------|
| **Cameras** | 1,614 sensors + 2,448 header mappings | ZWO, QHY, Atik, FLI, SBIG, Player One, Touptek, Moravian, Starlight Xpress, Canon, Nikon, Sony, Fujifilm, Pentax, Olympus, FLIR, Basler, Andor, Hamamatsu, Vaonis, Unistellar, etc. |
| **Telescopes** | 3,991 models + 6,605 header mappings | Takahashi, Celestron, Sky-Watcher, Meade, APM, William Optics, Vixen, Orion, Astro-Physics, PlaneWave, Officina Stellare, TEC, RCOS, CDK, etc. |
| **Filters** | 1,612 filters + 701 aliases | Baader, Astronomik, Chroma, ZWO, Optolong, Antlia, IDAS, Astrodon, Custom Scientific, narrowband/broadband/photometric/LRGB |
| **Targets** | 32,923 objects | Messier (110), NGC/IC/Extended (32,411), Arp (338), Solar System (64) — includes Sharpless, Barnard, Caldwell, RCW, LBN, PGC, Abell, LDN, Hickson, UGC, etc. |

---

## Database Schema (v4)

AstroManager uses SQLite in WAL mode with 4 schema migrations:

| Version | Tables Added |
|---------|-------------|
| **v1** | `targets`, `observations`, `weather_cache`, `header_cache`, `analysis_results` |
| **v2** | `pixinsight_sessions`, `pixinsight_subframes`, `pixinsight_integrations`, `pixinsight_frame_weights`, `pixinsight_calibrations` |
| **v3** | `mount_sessions`, `mount_tracking_data`, `mount_time_data`, `mount_fft_data`, `mount_environment_data` |
| **v4** *(New)* | `tags`, `target_tags`, `observation_tags`, `frame_quality` + `workflow_stage` column on targets |

---

## Compression Profiles

| Profile | Ratio | Speed | Best For |
|---------|-------|-------|----------|
| `zlib_1` | ~30% | Fast | Temporary files |
| `zlib_6` | ~50% | Medium | **General archival (recommended)** |
| `zlib_9` | ~55% | Slow | Maximum zlib |
| `zstd_3` | ~45% | Fast | Quick archival |
| `zstd_6` | ~55% | Medium | Better than zlib_6 |
| `zstd_10` | ~60% | Slow | High compression |
| `zstd_19` | ~65% | Very slow | Long-term archival |
| `lz4` | ~25% | Ultra-fast | Working files |
| `lz4_hc` | ~35% | Fast | Better LZ4 |

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+,` | Open Settings |
| `Ctrl+Q` | Quit |
| `Ctrl+O` | Open Folder |
| `Ctrl+\`` | Toggle console |
| `F1` | User Guide |

---

## NAS / Multi-PC Portability

AstroManager is designed to work seamlessly from a NAS or any synced folder (Synology, QNAP, OneDrive, Dropbox, etc.).

- **Virtual environment stored locally** on each PC (not in the project folder):
  - Windows: `%LOCALAPPDATA%\AstroManager\venv`
  - Linux: `$XDG_DATA_HOME/AstroManager/venv` (default: `~/.local/share`)
- **Launcher scripts** (`launch.bat` / `launch.sh`) auto-detect Python, create the venv if needed, install dependencies, and start the app with `pythonw` (no console window on Windows).
- **Desktop shortcuts** target the launcher script, so they work even if the project is mapped to a different drive letter on each PC.
- **Database and config** stay in the project directory and are synced across PCs.
- If you move the project folder, use **Help > Create Desktop Shortcut** to update the shortcut path.

---

## Troubleshooting

**No FITS files found:**
- Check folder path and file extensions (.fits, .fit, .fz, .xisf)
- Verify read permissions

**Database locked:**
- Close other AstroManager instances
- Or delete `astromanager.db` (will recreate)

**Slow performance:**
- Check storage type (HDD is much slower)
- Reduce workers in Settings
- Disable SIMBAD/weather for faster analysis
- Clear old cache: Tools → Clear Old Cache

**LaTeX compilation fails:**
- HTML report is always generated as fallback
- ReportLab PDF is generated automatically when LaTeX is unavailable

**Missing dependencies:**
- AstroManager auto-installs on first launch
- Or manually: `pip install -r requirements.txt`

---

## Dependencies

### Required
- Python 3.8+
- PyQt6, numpy, pandas, matplotlib, astropy, Pillow, reportlab, tqdm, requests, xisf

### Recommended
- psutil (system detection), PyYAML (configuration), zstandard (zstd), lz4 (lz4), defusedxml (XML security)

### Optional
- astroquery (SIMBAD), scipy (advanced statistics, PSF fitting, DBSCAN clustering)

---

## License

MIT License — see [LICENSE](LICENSE) file

---

## Acknowledgments

- **[Athenaeum / rustafits](https://github.com/eg013ra1n/rustafits)** (Vilen Sharifov) — Inspiration for frame quality analysis (PSF pipeline), WBPP export, sky chart, shoot calendar, calibration scoring, DBSCAN clustering, tags & workflow stages
- **Astropy** — FITS handling and RICE compression
- **PyQt6** — GUI framework
- **SIMBAD** (CDS, Strasbourg) — Astronomical database
- **Open-Meteo** �� Free weather API
- **ASTAP** (Han Kleijn) — Plate solving
- **Astrometry.net** — Plate solving
- **PixInsight** — XISF specification
- **CloudyNights** community — Testing and feedback
