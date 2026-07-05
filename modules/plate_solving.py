#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - PLATE SOLVING MODULE
================================================================================
Wrapper for ASTAP and Astrometry.net plate solvers.
Detects focal reducers by comparing measured vs expected plate scale.
Batch solve: solve all unsolved LIGHT frames and write WCS to headers.
================================================================================
"""

import os
import sys
import struct
import re
import shutil
import subprocess
import logging
import configparser
import glob
import time
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable

logger = logging.getLogger(__name__)

# Common focal reducer ratios
KNOWN_REDUCERS = {
    0.67: "0.67x Reducer",
    0.72: "0.72x Reducer",
    0.73: "0.73x Reducer (Starizona)",
    0.75: "0.75x Reducer",
    0.80: "0.80x Reducer",
    0.85: "0.85x Reducer",
    1.00: "No Reducer (Native)",
}

# Tolerance for reducer detection (3%)
REDUCER_TOLERANCE = 0.03


_cached_astap_path = None
_astap_path_checked = False


def find_astap_executable() -> Optional[str]:
    """Auto-detect ASTAP installation path (cross-platform). Cached after first call."""
    global _cached_astap_path, _astap_path_checked
    if _astap_path_checked:
        return _cached_astap_path

    import shutil

    # Try PATH first (most reliable, works on all platforms)
    found = shutil.which("astap_cli")
    if found:
        _cached_astap_path = found
        _astap_path_checked = True
        return found

    # Platform-specific fallback paths
    common_paths = []
    if sys.platform == 'win32':
        # Check common Windows install locations
        home = Path.home()
        common_paths = [
            Path(r"C:\Program Files\astap\astap_cli.exe"),
            Path(r"C:\Program Files (x86)\astap\astap_cli.exe"),
            Path(r"C:\astap\astap_cli.exe"),
            home / "AppData" / "Local" / "astap" / "astap_cli.exe",
        ]
        # Also check D: and E: drives
        for drive in ['D:\\', 'E:\\']:
            common_paths.append(Path(drive) / "astap" / "astap_cli.exe")
    elif sys.platform == 'darwin':
        common_paths = [
            Path("/usr/local/bin/astap_cli"),
            Path("/opt/homebrew/bin/astap_cli"),
            Path("/Applications/astap/astap_cli"),
            Path.home() / "astap" / "astap_cli",
        ]
    else:  # Linux
        common_paths = [
            Path("/usr/bin/astap_cli"),
            Path("/usr/local/bin/astap_cli"),
            Path("/opt/astap/astap_cli"),
            Path.home() / "astap" / "astap_cli",
        ]

    for path in common_paths:
        if path.is_file():
            _cached_astap_path = str(path)
            _astap_path_checked = True
            return str(path)

    _astap_path_checked = True
    return None


def find_star_database(astap_dir: str) -> Optional[Dict]:
    """
    Search for ASTAP star database files.

    Returns dict with 'name' and 'path', or None if not found.
    """
    # Database prefixes: h17, h18, d50, d80, v17, w08
    db_prefixes = ['h17', 'h18', 'd50', 'd80', 'v17', 'w08']

    # Search locations (prioritized)
    search_dirs = [astap_dir]
    if sys.platform == 'win32':
        search_dirs.extend([
            r"C:\Program Files\astap",
            r"C:\Program Files (x86)\astap",
        ])
    else:
        search_dirs.extend([
            "/opt/astap",
            "/usr/share/astap",
            str(Path.home() / ".local" / "share" / "astap"),
        ])

    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for prefix in db_prefixes:
            # Database files look like h17_00.290, h18_01.290, etc.
            pattern = os.path.join(search_dir, f"{prefix}_*.*")
            matches = glob.glob(pattern)
            if matches:
                return {'name': prefix.upper(), 'path': search_dir, 'count': len(matches)}

    return None


class PlateSolver:
    """Plate solving engine supporting ASTAP and Astrometry.net"""

    def __init__(self, solver='astap', executable_path=None, timeout=120):
        self.solver = solver
        self.timeout = timeout
        self._db_checked = False
        self._db_info = None

        if executable_path:
            exe_name = os.path.basename(executable_path).lower()
            if not any(name in exe_name for name in ('astap', 'solve-field', 'astrometry')):
                logger.warning(f"Executable path does not appear to be a known plate solver: {executable_path}")
            self.executable = executable_path
        elif solver == 'astap':
            self.executable = find_astap_executable()
        else:
            self.executable = None

    def is_available(self) -> bool:
        """Check if solver is available"""
        if not self.executable or not os.path.isfile(self.executable):
            return False
        # Verify it's a recognized plate solver
        exe_name = os.path.basename(self.executable).lower()
        return any(name in exe_name for name in ('astap', 'solve-field', 'astrometry'))

    def check_database(self) -> Optional[Dict]:
        """Check if a star database is installed. Returns info dict or None."""
        if self._db_checked:
            return self._db_info
        self._db_checked = True
        if self.executable:
            astap_dir = str(Path(self.executable).parent)
            self._db_info = find_star_database(astap_dir)
        return self._db_info

    def solve_field(self, filepath: str, ra_hint: float = None,
                    dec_hint: float = None, fov_hint: float = None) -> Dict:
        """
        Solve plate for a given FITS/XISF file.

        Args:
            filepath: Path to FITS/XISF file
            ra_hint: RA in degrees (0-360)
            dec_hint: Dec in degrees (-90 to +90)
            fov_hint: Approximate field of view in degrees (helps solving)

        Returns:
            dict with keys: solved, ra, dec, scale, rotation, width, height, fov
        """
        if self.solver == 'astap':
            return self._solve_astap(filepath, ra_hint, dec_hint, fov_hint)
        else:
            return {'solved': False, 'error': f'Solver {self.solver} not supported'}

    def _solve_astap(self, filepath: str, ra_hint: float = None,
                     dec_hint: float = None, fov_hint: float = None) -> Dict:
        """Solve using ASTAP"""
        if not self.executable:
            return {'solved': False, 'error': 'ASTAP not found'}

        # Check star database on first call
        db_info = self.check_database()
        if db_info is None:
            return {
                'solved': False,
                'error': 'No star database found! Install H17 from https://www.hnsky.org/astap.htm#deep_sky_databases'
            }

        cmd = [self.executable, '-f', filepath]

        # Add coordinate hints if available (helps ASTAP solve faster)
        has_hints = False
        if ra_hint is not None and dec_hint is not None:
            cmd.extend(['-ra', f'{ra_hint / 15.0:.6f}'])  # Convert degrees to hours
            cmd.extend(['-spd', f'{dec_hint + 90.0:.6f}'])  # Convert to South Pole Distance
            has_hints = True

        # Search radius: smaller with hints, wider without
        if has_hints:
            cmd.extend(['-r', '30'])
        else:
            cmd.extend(['-r', '180'])

        # Field of view hint (greatly helps solving)
        if fov_hint and fov_hint > 0:
            cmd.extend(['-fov', f'{fov_hint:.2f}'])

        # Auto downsample (ASTAP chooses optimal downsampling)
        cmd.extend(['-z', '0'])

        # Specify database path explicitly
        if db_info and db_info.get('path'):
            cmd.extend(['-d', db_info['path']])

        try:
            solve_start = time.time()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(Path(self.executable).parent)
            )

            # Parse ASTAP .ini output file
            # ASTAP writes the .ini next to the source file with same base name
            ini_path = Path(filepath).with_suffix('.ini')
            if ini_path.exists():
                # Verify the INI was written after solve started (TOCTOU protection)
                if ini_path.stat().st_mtime < solve_start:
                    logger.warning(f"INI file predates solve start, ignoring stale result: {ini_path}")
                    self._cleanup_astap_files(filepath)
                    return {'solved': False, 'error': 'Stale INI file detected (predates solve start)'}
                solution = self._parse_astap_ini(str(ini_path))

                # On failure, attach ASTAP diagnostic output
                if not solution.get('solved'):
                    astap_msg = self._extract_astap_diagnostic(result)
                    if astap_msg:
                        solution['error'] = solution.get('error', '') + f' [{astap_msg}]'

                # Clean up temp files
                self._cleanup_astap_files(filepath)
                return solution

            # No .ini generated at all - something is very wrong
            astap_msg = self._extract_astap_diagnostic(result)
            error = 'No solution file generated'
            if astap_msg:
                error += f' [{astap_msg}]'
            return {'solved': False, 'error': error}

        except subprocess.TimeoutExpired:
            self._cleanup_astap_files(filepath)
            return {'solved': False, 'error': f'Timeout ({self.timeout}s)'}
        except Exception as e:
            self._cleanup_astap_files(filepath)
            return {'solved': False, 'error': str(e)}

    @staticmethod
    def _extract_astap_diagnostic(result) -> str:
        """Extract useful diagnostic info from ASTAP stdout/stderr"""
        lines = []
        for src in [result.stdout or '', result.stderr or '']:
            for line in src.strip().split('\n'):
                line = line.strip()
                if not line:
                    continue
                # Keep error/warning messages and key info
                lower = line.lower()
                if any(kw in lower for kw in [
                    'error', 'warning', 'fail', 'not found', 'no database',
                    'can not', 'cannot', 'unable', 'missing', 'solved',
                    'stars', 'database', 'reading'
                ]):
                    lines.append(line)
        return '; '.join(lines[:5])  # Keep max 5 diagnostic lines

    @staticmethod
    def _cleanup_astap_files(filepath: str):
        """Clean up ASTAP temp files (.ini, .wcs)"""
        for suffix in ['.ini', '.wcs']:
            try:
                p = Path(filepath).with_suffix(suffix)
                if p.exists():
                    p.unlink()
            except OSError as e:
                logger.debug(f"Failed to cleanup ASTAP temp file: {e}")

    def _parse_astap_ini(self, ini_path: str) -> Dict:
        """Parse ASTAP .ini solution file (KEY=VALUE format, no section headers)"""
        config = configparser.ConfigParser()
        try:
            # ASTAP .ini files have no section headers - prepend a fake one
            with open(ini_path, 'r', encoding='utf-8', errors='replace') as f:
                ini_content = '[astap]\n' + f.read()
            config.read_string(ini_content)
            section = 'astap'

            solved = config.get(section, 'PLTSOLVD', fallback='F')
            if solved != 'T':
                # Try to get the error message from ASTAP
                warning = config.get(section, 'WARNING', fallback='')
                error_msg = 'No solution found'
                if warning:
                    error_msg += f' ({warning})'
                return {'solved': False, 'error': error_msg}

            ra = float(config.get(section, 'CRVAL1', fallback='0'))
            dec = float(config.get(section, 'CRVAL2', fallback='0'))

            import math

            # Plate scale - prefer CDELT (always written by ASTAP), fallback to CD matrix
            cdelt1 = float(config.get(section, 'CDELT1', fallback='0'))
            cdelt2 = float(config.get(section, 'CDELT2', fallback='0'))

            if cdelt1 != 0 and cdelt2 != 0:
                # CDELT is in degrees/pixel, convert to arcsec/pixel
                scale = (abs(cdelt1) + abs(cdelt2)) / 2.0 * 3600
            else:
                # Fallback: compute from CD matrix
                cd1_1 = float(config.get(section, 'CD1_1', fallback='0'))
                cd1_2 = float(config.get(section, 'CD1_2', fallback='0'))
                cd2_1 = float(config.get(section, 'CD2_1', fallback='0'))
                cd2_2 = float(config.get(section, 'CD2_2', fallback='0'))
                scale_x = math.sqrt(cd1_1**2 + cd2_1**2) * 3600
                scale_y = math.sqrt(cd1_2**2 + cd2_2**2) * 3600
                scale = (scale_x + scale_y) / 2.0

            # Rotation angle - prefer CROTA2, fallback to CD matrix
            crota2 = config.get(section, 'CROTA2', fallback=None)
            if crota2 is not None:
                rotation = float(crota2)
            else:
                cd1_1 = float(config.get(section, 'CD1_1', fallback='0'))
                cd2_1 = float(config.get(section, 'CD2_1', fallback='0'))
                rotation = math.degrees(math.atan2(cd2_1, cd1_1))

            # Image dimensions: NAXIS > CRPIX*2 (CRPIX = center pixel)
            naxis1 = int(config.get(section, 'NAXIS1', fallback='0'))
            naxis2 = int(config.get(section, 'NAXIS2', fallback='0'))
            if naxis1 == 0:
                crpix1 = float(config.get(section, 'CRPIX1', fallback='0'))
                if crpix1 > 0:
                    naxis1 = int(crpix1 * 2)
            if naxis2 == 0:
                crpix2 = float(config.get(section, 'CRPIX2', fallback='0'))
                if crpix2 > 0:
                    naxis2 = int(crpix2 * 2)

            # Field of view
            fov_x = naxis1 * scale / 3600 if naxis1 > 0 else 0  # degrees
            fov_y = naxis2 * scale / 3600 if naxis2 > 0 else 0

            return {
                'solved': True,
                'ra': ra,
                'dec': dec,
                'scale': scale,  # arcsec/pixel
                'rotation': rotation,
                'width': naxis1,
                'height': naxis2,
                'fov_x': fov_x,
                'fov_y': fov_y,
            }

        except Exception as e:
            return {'solved': False, 'error': f'Parse error: {e}'}

    def detect_focal_reducer(self, measured_scale: float,
                              pixel_size_um: float,
                              native_focal_mm: float) -> Dict:
        """
        Detect focal reducer by comparing measured vs expected plate scale.

        Args:
            measured_scale: Measured plate scale in arcsec/pixel (from plate solve)
            pixel_size_um: Camera pixel size in micrometers
            native_focal_mm: Native telescope focal length in mm

        Returns:
            dict with: detected, ratio, reducer_name, effective_focal
        """
        # Expected plate scale without reducer
        # scale = (pixel_size / focal_length) * 206.265
        if not native_focal_mm or not pixel_size_um:
            return {'detected': False, 'ratio': 1.0, 'reducer_name': None,
                    'effective_focal': native_focal_mm}
        expected_scale = (pixel_size_um / native_focal_mm) * 206.265
        if expected_scale == 0:
            return {'detected': False, 'ratio': 1.0, 'reducer_name': None,
                    'effective_focal': native_focal_mm}

        # Actual ratio
        ratio = measured_scale / expected_scale

        # Find closest known reducer
        best_match = None
        best_diff = float('inf')

        for known_ratio, name in KNOWN_REDUCERS.items():
            diff = abs(ratio - known_ratio)
            if diff < best_diff:
                best_diff = diff
                best_match = (known_ratio, name)

        detected = best_diff <= REDUCER_TOLERANCE

        effective_focal = native_focal_mm
        reducer_name = "Unknown"
        matched_ratio = ratio

        if detected and best_match:
            matched_ratio = best_match[0]
            reducer_name = best_match[1]
            effective_focal = native_focal_mm * matched_ratio

        return {
            'detected': detected,
            'ratio': round(matched_ratio, 3),
            'measured_ratio': round(ratio, 4),
            'reducer_name': reducer_name,
            'effective_focal_mm': round(effective_focal, 1),
            'measured_scale': round(measured_scale, 4),
            'expected_scale': round(expected_scale, 4),
        }


def get_astap_install_instructions(lang='en') -> str:
    """
    Return detailed ASTAP installation instructions.

    Args:
        lang: 'en' or 'fr'
    """
    if lang == 'fr':
        return """
=== INSTALLATION D'ASTAP (Astrometric STAcking Program) ===

ASTAP est nécessaire pour le plate solving (astrométrie).
Il permet de détecter automatiquement les réducteurs de focale.

1. TÉLÉCHARGER ASTAP:
   Site officiel: https://www.hnsky.org/astap.htm
   - Windows: télécharger le fichier .exe (installeur)
   - Linux:   télécharger le fichier .deb ou .rpm
   - macOS:   télécharger le fichier .dmg

2. INSTALLER ASTAP:
   - Windows: lancer l'installeur, installer dans C:\\Program Files\\astap
   - Linux (Debian/Ubuntu): sudo dpkg -i astap_*.deb
   - Linux (Arch/Manjaro): disponible dans AUR (yay -S astap-bin)
   - macOS: ouvrir le .dmg et glisser dans Applications

3. TÉLÉCHARGER UNE BASE DE DONNÉES D'ÉTOILES:
   Site: https://www.hnsky.org/astap.htm#deep_sky_databases
   IMPORTANT: Vous DEVEZ installer au moins une base de données !

   Bases recommandées (choisir UNE):
   - H17 (recommandé): ~600 MB - couvre tout le ciel, bonne précision
     Idéal pour la plupart des setups d'astrophotographie
   - H18: ~1.5 GB - plus d'étoiles, meilleure résolution
     Pour les longues focales ou champs étroits
   - D50: ~4 GB - très complète
     Pour les cas difficiles uniquement

   Installation de la base:
   - Décompresser le fichier ZIP dans le dossier d'ASTAP
   - Windows: C:\\Program Files\\astap\\
   - Linux: /opt/astap/ ou ~/.local/share/astap/

4. VÉRIFICATION:
   Ouvrez un terminal et tapez: astap_cli -h
   Si vous voyez l'aide d'ASTAP, l'installation est réussie.

5. CONFIGURATION DANS ASTROMANAGER:
   Si ASTAP n'est pas détecté automatiquement, vous pouvez
   spécifier le chemin dans Paramètres > Plate solving > Chemin ASTAP

NOTE: AstroManager détecte ASTAP automatiquement dans les
emplacements standards. Si vous l'installez ailleurs, configurez
le chemin manuellement dans les paramètres.
"""
    else:
        return """
=== INSTALLING ASTAP (Astrometric STAcking Program) ===

ASTAP is required for plate solving functionality.
It allows automatic detection of focal reducers.

1. DOWNLOAD ASTAP:
   Official site: https://www.hnsky.org/astap.htm
   - Windows: download the .exe installer
   - Linux:   download the .deb or .rpm package
   - macOS:   download the .dmg file

2. INSTALL ASTAP:
   - Windows: run the installer, install to C:\\Program Files\\astap
   - Linux (Debian/Ubuntu): sudo dpkg -i astap_*.deb
   - Linux (Arch/Manjaro): available in AUR (yay -S astap-bin)
   - macOS: open the .dmg and drag to Applications

3. DOWNLOAD A STAR DATABASE:
   Site: https://www.hnsky.org/astap.htm#deep_sky_databases
   IMPORTANT: You MUST install at least one star database!

   Recommended databases (choose ONE):
   - H17 (recommended): ~600 MB - covers the whole sky, good accuracy
     Ideal for most astrophotography setups
   - H18: ~1.5 GB - more stars, better resolution
     For long focal lengths or narrow fields
   - D50: ~4 GB - very comprehensive
     For difficult cases only

   Database installation:
   - Extract the ZIP file into the ASTAP folder
   - Windows: C:\\Program Files\\astap\\
   - Linux: /opt/astap/ or ~/.local/share/astap/

4. VERIFICATION:
   Open a terminal and type: astap_cli -h
   If you see ASTAP help output, the installation was successful.

5. CONFIGURATION IN ASTROMANAGER:
   If ASTAP is not auto-detected, you can specify the path
   in Settings > Plate Solving > ASTAP Path

NOTE: AstroManager auto-detects ASTAP in standard locations.
If you install it elsewhere, configure the path manually
in the settings.
"""


def solve_and_detect_reducer(filepath: str, pixel_size_um: float,
                              native_focal_mm: float,
                              solver='astap', **kwargs) -> Dict:
    """
    Convenience function: solve plate and detect focal reducer in one call.

    Args:
        filepath: Path to FITS/XISF file
        pixel_size_um: Camera pixel size in micrometers
        native_focal_mm: Native telescope focal length in mm
        solver: 'astap' or 'astrometry'

    Returns:
        dict with plate solve results + reducer detection
    """
    ps = PlateSolver(solver=solver, **kwargs)

    if not ps.is_available():
        return {'solved': False, 'error': f'{solver} not available'}

    result = ps.solve_field(filepath)

    if result.get('solved'):
        reducer_info = ps.detect_focal_reducer(
            measured_scale=result['scale'],
            pixel_size_um=pixel_size_um,
            native_focal_mm=native_focal_mm
        )
        result['reducer'] = reducer_info

    return result


# ============================================================================
# BATCH PLATE SOLVING - Solve all unsolved LIGHT frames & write WCS to headers
# ============================================================================

# WCS keywords written to solved files
_WCS_KEYS = [
    'PLTSOLVD', 'CRPIX1', 'CRPIX2', 'CRVAL1', 'CRVAL2',
    'CDELT1', 'CDELT2', 'CROTA1', 'CROTA2',
    'CD1_1', 'CD1_2', 'CD2_1', 'CD2_2',
    'CTYPE1', 'CTYPE2', 'CUNIT1', 'CUNIT2',
]

_WCS_COMMENTS = {
    'PLTSOLVD': 'Plate solved by ASTAP',
    'CRPIX1': 'X of reference pixel',
    'CRPIX2': 'Y of reference pixel',
    'CRVAL1': 'RA of reference pixel (deg)',
    'CRVAL2': 'DEC of reference pixel (deg)',
    'CDELT1': 'X pixel size (deg)',
    'CDELT2': 'Y pixel size (deg)',
    'CROTA1': 'Image twist X axis (deg)',
    'CROTA2': 'Image twist Y axis (deg)',
    'CD1_1': '', 'CD1_2': '', 'CD2_1': '', 'CD2_2': '',
    'CTYPE1': 'first parameter RA, projection TAN',
    'CTYPE2': 'second parameter DEC, projection TAN',
    'CUNIT1': 'Unit of first axis',
    'CUNIT2': 'Unit of second axis',
}

_WCS_FIXED = {
    'CTYPE1': 'RA---TAN', 'CTYPE2': 'DEC--TAN',
    'CUNIT1': 'deg', 'CUNIT2': 'deg', 'PLTSOLVD': 'T',
}

# Directories to skip when scanning for LIGHT files
_SKIP_DIRS = {
    'Dark-Bias', 'poubelle', 'PixInsight', 'traitement Pix',
    'Adam Block tutorials', 'Telescope live', 'Chilescope', 'Seestar S50',
    'calibrated', 'master', 'masters', 'cosmetized', 'temp', 'rejected',
    'registered', 'integrated', 'process', 'output',
}

# PixInsight processed file suffixes (checked before extension)
_PI_SUFFIXES = ('_c', '_d', '_r', '_cc', '_cal', '_drizzle', '_abe', '_dbe')

# Master/processed file prefixes
_PROCESSED_PREFIXES = ('master', 'calibrated', 'registered', 'integrated')

# Valid file extensions for batch solving
_SOLVE_EXTENSIONS = {'.fits', '.fit', '.xisf', '.fz'}


def read_xisf_header_fast(filepath: str) -> Optional[Dict[str, Dict]]:
    """
    Read FITS keywords from XISF header without decompressing image data.
    Only reads the XML header (~4-8 KB), not the full file.

    Returns:
        dict of {keyword: {'value': str, 'comment': str}} or None on error
    """
    try:
        with open(filepath, 'rb') as f:
            magic = f.read(8)
            if magic != b'XISF0100':
                return None
            header_length = struct.unpack('<I', f.read(4))[0]
            f.read(4)  # reserved
            xml_data = f.read(header_length).decode('utf-8')

        keywords = {}
        for m in re.finditer(
            r'<FITSKeyword\s+name="([^"]+)"\s+value="([^"]*)"\s+comment="([^"]*)"',
            xml_data
        ):
            name, value, comment = m.group(1), m.group(2), m.group(3)
            keywords[name] = {'value': value, 'comment': comment}
        return keywords
    except Exception as e:
        logger.debug(f"Failed to read XISF header: {filepath}: {e}")
        return None


def read_fits_header_fast(filepath: str) -> Optional[Dict[str, Dict]]:
    """Read FITS header keywords quickly. Supports .fits, .fit, and .fits.fz."""
    try:
        from astropy.io import fits
        # .fits.fz: image is in extension 1
        ext = 1 if filepath.lower().endswith('.fz') else 0
        hdr = fits.getheader(filepath, ext=ext)
        keywords = {}
        for k in hdr:
            if k and k.strip():
                try:
                    comment = hdr.comments[k]
                except (KeyError, IndexError):
                    comment = ''
                keywords[k] = {'value': str(hdr[k]), 'comment': comment}
        return keywords
    except Exception as e:
        logger.debug(f"Failed to read FITS header: {filepath}: {e}")
        return None


def _get_file_type(filepath: str) -> str:
    """Return normalized file type: 'xisf', 'fits', or 'fz'."""
    lower = filepath.lower()
    if lower.endswith('.xisf'):
        return 'xisf'
    elif lower.endswith('.fits.fz'):
        return 'fz'
    else:
        return 'fits'


def _read_header(filepath: str) -> Optional[Dict[str, Dict]]:
    """Read header from any supported format."""
    ftype = _get_file_type(filepath)
    if ftype == 'xisf':
        return read_xisf_header_fast(filepath)
    else:
        return read_fits_header_fast(filepath)


def is_file_solved(filepath: str) -> bool:
    """Check if a file already has WCS astrometric solution in its header."""
    kw = _read_header(filepath)
    return kw is not None and 'CRVAL1' in kw


def is_calibration_frame(keywords: Dict[str, Dict]) -> bool:
    """Check IMAGETYP/FRAME header to detect calibration frames (DARK/FLAT/BIAS)."""
    for key in ('IMAGETYP', 'FRAME', 'IMTYPE', 'OBSTYPE'):
        if key in keywords:
            val = keywords[key].get('value', '').upper()
            if any(cal in val for cal in ('FLAT', 'DARK', 'BIAS', 'OFFSET')):
                return True
    return False


def is_raw_light(filepath: str) -> bool:
    """
    Check if a file is a raw LIGHT frame (not calibrated/master/processed).

    Uses filename-based heuristics matching AstroManager's existing detection:
    - PixInsight processed file suffixes (_c, _d, _r, _cc, _cal, _drizzle, _ABE, _DBE)
    - Master/calibrated/registered/integrated prefixes
    - Calibration frame prefixes (DARK_, BIAS_, FLAT_)
    - Copy files

    Supports .fits, .fit, .xisf, .fits.fz extensions.
    """
    fname = os.path.basename(filepath)
    lower = fname.lower()

    # Check extension and extract base name
    if lower.endswith('.fits.fz'):
        base = lower[:-8]
    elif lower.endswith('.xisf'):
        base = lower[:-5]
    elif lower.endswith('.fits'):
        base = lower[:-5]
    elif lower.endswith('.fit'):
        base = lower[:-4]
    else:
        return False

    # Skip PixInsight processed file suffixes
    for suffix in _PI_SUFFIXES:
        if base.endswith(suffix):
            return False

    # Skip master/processed file prefixes
    for prefix in _PROCESSED_PREFIXES:
        if lower.startswith(prefix):
            return False

    # Skip calibration frame names
    if (lower.startswith('dark_') or lower.startswith('bias_')
            or lower.startswith('flat_') or lower.startswith('darkflat_')):
        return False

    # Skip copies
    if ' - copie' in lower or ' - copy' in lower:
        return False

    # Skip PixInsight processing chains in filename
    if '_c_cc' in lower or '_c_r.' in lower:
        return False

    return True


def scan_light_files(folder: str) -> List[str]:
    """Scan folder recursively for raw LIGHT files (filename-based fast scan)."""
    files = []
    skip_lower = {d.lower() for d in _SKIP_DIRS}
    # Additional folder prefixes to skip
    skip_prefixes = ('extracted_', 'duplicates_', 'astronomical_analysis_',
                     'fits_originals_', 'duplicates_extracted')
    skip_suffixes = ('_fits_fz_backup',)

    for root, dirs, filenames in os.walk(folder):
        # Filter directories in-place
        dirs[:] = [d for d in dirs
                   if d.lower() not in skip_lower
                   and not any(d.startswith(p) for p in skip_prefixes)
                   and not any(d.endswith(s) for s in skip_suffixes)]
        for fname in filenames:
            fpath = os.path.join(root, fname)
            if is_raw_light(fpath):
                files.append(fpath)
    return files


def _extract_solve_hints(keywords: Dict) -> Dict:
    """Extract RA, DEC, FOV hints from header keywords for ASTAP."""
    hints = {}
    try:
        if 'RA' in keywords:
            ra_deg = float(keywords['RA']['value'])
            hints['ra_h'] = ra_deg / 15.0
        if 'DEC' in keywords:
            dec_deg = float(keywords['DEC']['value'])
            hints['spd'] = 90.0 + dec_deg
        if 'FOCALLEN' in keywords and 'XPIXSZ' in keywords and 'NAXIS1' in keywords:
            focallen = float(keywords['FOCALLEN']['value'])
            pixsize = float(keywords['XPIXSZ']['value'])
            naxis1 = int(keywords['NAXIS1']['value'])
            binning = 1
            if 'XBINNING' in keywords:
                binning = int(keywords['XBINNING']['value'])
            pixel_scale = 206.265 * pixsize * binning / focallen
            hints['fov'] = pixel_scale * naxis1 / 3600
    except (ValueError, KeyError):
        pass
    return hints


def _update_xisf_header_inplace(filepath: str, wcs_solution: Dict) -> bool:
    """
    Write WCS keywords into XISF header by modifying the XML in-place.
    If new header fits in existing space, only header bytes are touched (fast).
    """
    with open(filepath, 'rb') as f:
        preamble = f.read(16)
        magic = preamble[:8]
        if magic != b'XISF0100':
            raise ValueError("Not a valid XISF file")
        header_length = struct.unpack('<I', preamble[8:12])[0]
        xml_bytes = f.read(header_length)

    xml_data = xml_bytes.decode('utf-8')

    loc_match = re.search(r'location="attachment:(\d+):(\d+)"', xml_data)
    if not loc_match:
        raise ValueError("Cannot find attachment location in XISF header")

    att_offset = int(loc_match.group(1))
    att_size = int(loc_match.group(2))

    # Remove existing WCS keywords to avoid duplicates
    for key in _WCS_KEYS:
        xml_data = re.sub(
            rf'<FITSKeyword\s+name="{key}"\s+value="[^"]*"\s+comment="[^"]*"\s*/?>',
            '', xml_data
        )

    # Build WCS FITSKeyword XML entries
    wcs_xml = ''
    for key in _WCS_KEYS:
        if key in _WCS_FIXED:
            val = _WCS_FIXED[key]
        elif key in wcs_solution:
            val = wcs_solution[key].strip()
        else:
            continue
        val = val.replace('&', '&amp;').replace('"', '&quot;').replace("'", "&apos;")
        comment = _WCS_COMMENTS.get(key, '').replace('&', '&amp;').replace('"', '&quot;')
        wcs_xml += f'<FITSKeyword name="{key}" value="{val}" comment="{comment}" />'

    new_xml = xml_data.replace('</Image>', wcs_xml + '</Image>')
    new_xml_bytes = new_xml.encode('utf-8')
    new_header_length = len(new_xml_bytes)

    if 16 + new_header_length <= att_offset:
        # New header fits in the existing header space: only the header region
        # changes, but rewrite the whole file to a temporary and os.replace() it
        # so the original LIGHT is never left partially written (atomic update).
        new_header = b'XISF0100'
        new_header += struct.pack('<I', new_header_length)
        new_header += struct.pack('<I', 0)
        new_header += new_xml_bytes
        new_header += b'\x00' * (att_offset - len(new_header))

        # Copy the pixel attachment (and any trailing bytes) verbatim.
        with open(filepath, 'rb') as f:
            f.seek(att_offset)
            rest = f.read()

        tmp_path = filepath + '.tmp'
        with open(tmp_path, 'wb') as f:
            f.write(new_header)
            f.write(rest)
        os.replace(tmp_path, filepath)
        return True
    else:
        # Rare: header doesn't fit, must rewrite entire file
        new_att_offset = ((16 + new_header_length + 4095) // 4096) * 4096
        new_xml = new_xml.replace(
            f'attachment:{att_offset}:{att_size}',
            f'attachment:{new_att_offset}:{att_size}'
        )
        new_xml_bytes = new_xml.encode('utf-8')
        new_header_length = len(new_xml_bytes)

        with open(filepath, 'rb') as f:
            f.seek(att_offset)
            image_data = f.read(att_size)

        new_file = b'XISF0100'
        new_file += struct.pack('<I', new_header_length)
        new_file += struct.pack('<I', 0)
        new_file += new_xml_bytes
        new_file += b'\x00' * (new_att_offset - len(new_file))
        new_file += image_data

        tmp_path = filepath + '.tmp'
        with open(tmp_path, 'wb') as f:
            f.write(new_file)
        os.replace(tmp_path, filepath)
        return True


def _update_fz_header(filepath: str, wcs_solution: Dict) -> bool:
    """Write WCS keywords into a .fits.fz file header."""
    from astropy.io import fits
    with fits.open(filepath, mode='update', memmap=False) as hdul:
        hdr = hdul[1].header
        for key in _WCS_KEYS:
            if key in _WCS_FIXED:
                val = _WCS_FIXED[key]
            elif key in wcs_solution:
                val = wcs_solution[key].strip()
            else:
                continue
            comment = _WCS_COMMENTS.get(key, '')
            # Convert numeric values
            try:
                if key in ('CTYPE1', 'CTYPE2', 'CUNIT1', 'CUNIT2', 'PLTSOLVD'):
                    hdr[key] = (val, comment)
                else:
                    hdr[key] = (float(val), comment)
            except (ValueError, TypeError):
                hdr[key] = (val, comment)
    return True


def solve_and_update_header(filepath: str, solver: 'PlateSolver',
                             tmp_dir: str = None) -> Dict:
    """
    Solve a single LIGHT frame and write WCS back to its header.

    For XISF: converts to temp FITS (with binning for large images),
    solves with ASTAP, adjusts WCS for binning, updates XISF header in-place.
    For FITS: solves with ASTAP -update directly.

    Returns:
        dict with 'solved' (bool), 'message' (str), optionally 'ra', 'dec'
    """
    if tmp_dir is None:
        tmp_dir = tempfile.gettempdir()

    ftype = _get_file_type(filepath)
    is_xisf = ftype == 'xisf'
    is_fz = ftype == 'fz'

    try:
        # Quick header check
        keywords = _read_header(filepath)

        if keywords is None:
            return {'solved': False, 'message': 'Cannot read header'}
        if 'CRVAL1' in keywords:
            return {'solved': True, 'message': 'Already solved'}
        if is_calibration_frame(keywords):
            return {'solved': False, 'message': 'Calibration frame (skipped)'}

        hints = _extract_solve_hints(keywords)
        bin_factor = 1
        # For plain FITS solved with ASTAP '-update' (which rewrites the file in
        # place), holds the real original path while we solve on a temp copy.
        fits_update_target = None

        if is_xisf:
            import xisf as xisf_lib
            from astropy.io import fits
            import numpy as np

            xisf_obj = xisf_lib.XISF(filepath)
            data = xisf_obj.read_image(0)
            meta = xisf_obj.get_images_metadata()[0]
            fits_kw = meta.get('FITSKeywords', {})

            hdr = fits.Header()
            for key in ['NAXIS1', 'NAXIS2', 'BITPIX', 'OBJECT', 'RA', 'DEC',
                        'FOCALLEN', 'XPIXSZ', 'YPIXSZ', 'XBINNING', 'YBINNING',
                        'EXPOSURE', 'DATE-OBS', 'IMAGETYP', 'FILTER', 'GAIN',
                        'INSTRUME', 'TELESCOP', 'EQUINOX']:
                if key in fits_kw:
                    val = fits_kw[key][0]['value']
                    comment = fits_kw[key][0].get('comment', '')
                    try:
                        if '.' in str(val):
                            val = float(val)
                        else:
                            val = int(val)
                    except (ValueError, TypeError):
                        pass
                    try:
                        hdr[key] = (val, comment)
                    except Exception:
                        pass

            img = data[:, :, 0] if data.ndim == 3 and data.shape[2] == 1 else data
            if data.ndim == 3 and data.shape[0] == 1:
                img = data[0, :, :]

            # Bin large images for faster solving
            max_dim = max(img.shape)
            if max_dim > 4000:
                bin_factor = max(1, max_dim // 3000)
                h, w = img.shape
                nh = h // bin_factor
                nw = w // bin_factor
                img = img[:nh * bin_factor, :nw * bin_factor].reshape(
                    nh, bin_factor, nw, bin_factor
                ).mean(axis=(1, 3)).astype(np.uint16)
                if 'XPIXSZ' in hdr:
                    hdr['XPIXSZ'] = hdr['XPIXSZ'] * bin_factor
                if 'YPIXSZ' in hdr:
                    hdr['YPIXSZ'] = hdr['YPIXSZ'] * bin_factor
                hdr['NAXIS1'] = nw
                hdr['NAXIS2'] = nh

            tmp_fits = os.path.join(tmp_dir, f"solve_{os.getpid()}_{id(filepath) & 0xFFFF}.fits")
            hdu = fits.PrimaryHDU(data=img, header=hdr)
            hdu.writeto(tmp_fits, overwrite=True)
            del data, img
        elif is_fz:
            # .fits.fz: ASTAP can't read fpack'd files, decompress to temp FITS
            from astropy.io import fits
            import numpy as np

            with fits.open(filepath, memmap=False) as hdul:
                data = hdul[1].data
                hdr = hdul[1].header.copy()

            img = data
            if data.ndim == 3 and data.shape[0] == 1:
                img = data[0, :, :]

            # Bin large images for faster solving
            max_dim = max(img.shape)
            if max_dim > 4000:
                bin_factor = max(1, max_dim // 3000)
                h, w = img.shape
                nh = h // bin_factor
                nw = w // bin_factor
                img = img[:nh * bin_factor, :nw * bin_factor].reshape(
                    nh, bin_factor, nw, bin_factor
                ).mean(axis=(1, 3)).astype(np.uint16)
                if 'XPIXSZ' in hdr:
                    hdr['XPIXSZ'] = hdr['XPIXSZ'] * bin_factor
                if 'YPIXSZ' in hdr:
                    hdr['YPIXSZ'] = hdr['YPIXSZ'] * bin_factor
                hdr['NAXIS1'] = nw
                hdr['NAXIS2'] = nh

            tmp_fits = os.path.join(tmp_dir, f"solve_{os.getpid()}_{id(filepath) & 0xFFFF}.fits")
            hdu = fits.PrimaryHDU(data=img, header=hdr)
            hdu.writeto(tmp_fits, overwrite=True)
            del data, img
        else:
            # Plain FITS: ASTAP '-update' rewrites the header IN PLACE, which
            # would mutate the irreplaceable original. Instead, solve on a copy
            # placed in the SAME directory (so os.replace stays atomic on the
            # same filesystem) and swap it in only on success.
            fits_update_target = filepath
            base_dir = os.path.dirname(filepath) or '.'
            tmp_fits = os.path.join(
                base_dir, f".solve_{os.getpid()}_{id(filepath) & 0xFFFF}.fits"
            )
            shutil.copy2(filepath, tmp_fits)

        needs_tmp_cleanup = is_xisf or is_fz

        # Build ASTAP command
        cmd = [solver.executable, '-f', tmp_fits]
        if 'fov' in hints:
            cmd.extend(['-fov', f"{hints['fov']:.3f}"])
        else:
            cmd.extend(['-fov', '0'])
        if 'ra_h' in hints:
            cmd.extend(['-ra', f"{hints['ra_h']:.6f}"])
        if 'spd' in hints:
            cmd.extend(['-spd', f"{hints['spd']:.4f}"])
        cmd.extend(['-r', '30'])

        if not needs_tmp_cleanup:
            # Plain FITS: ASTAP can write WCS directly
            cmd.append('-update')

        # Specify database path
        db_info = solver.check_database()
        if db_info and db_info.get('path'):
            cmd.extend(['-d', db_info['path']])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        # Read solution from .ini
        ini_file = tmp_fits.rsplit('.', 1)[0] + '.ini'
        wcs_solution = {}
        solved = False

        if os.path.exists(ini_file):
            with open(ini_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line:
                        k, v = line.split('=', 1)
                        wcs_solution[k.strip()] = v.strip()
            solved = wcs_solution.get('PLTSOLVD', 'F') == 'T'

        # Cleanup temp files
        for ext_clean in ['.ini', '.wcs', '.log']:
            tmp_clean = tmp_fits.rsplit('.', 1)[0] + ext_clean
            if os.path.exists(tmp_clean):
                try:
                    os.remove(tmp_clean)
                except OSError:
                    pass
        if needs_tmp_cleanup and os.path.exists(tmp_fits):
            try:
                os.remove(tmp_fits)
            except OSError:
                pass

        if not solved:
            # Discard the plain-FITS working copy; leave the original untouched.
            if fits_update_target and os.path.exists(tmp_fits):
                try:
                    os.remove(tmp_fits)
                except OSError:
                    pass
            error_msg = wcs_solution.get('ERROR', 'Unknown error')
            return {'solved': False, 'message': f"Solve failed: {error_msg}"}

        # Adjust WCS for binning
        if bin_factor > 1:
            for key in ['CRPIX1', 'CRPIX2']:
                if key in wcs_solution:
                    wcs_solution[key] = f"{float(wcs_solution[key]) * bin_factor:.6E}"
            for key in ['CDELT1', 'CDELT2', 'CD1_1', 'CD1_2', 'CD2_1', 'CD2_2']:
                if key in wcs_solution:
                    wcs_solution[key] = f"{float(wcs_solution[key]) / bin_factor:.15E}"

        # Write WCS to file header
        if is_xisf:
            _update_xisf_header_inplace(filepath, wcs_solution)
        elif is_fz:
            # Write WCS to .fits.fz header
            _update_fz_header(filepath, wcs_solution)
        elif fits_update_target:
            # ASTAP '-update' wrote the WCS into the temp copy; atomically swap
            # it in for the original (same directory => same filesystem).
            os.replace(tmp_fits, fits_update_target)

        ra = wcs_solution.get('CRVAL1', '?')
        dec = wcs_solution.get('CRVAL2', '?')
        return {'solved': True, 'message': f"Solved: RA={ra}, DEC={dec}",
                'ra': ra, 'dec': dec}

    except Exception as e:
        # Best-effort: never leave a half-solved plain-FITS working copy behind.
        # The original is untouched until the final os.replace(), so it is safe.
        _tmp = locals().get('tmp_fits')
        if locals().get('fits_update_target') and _tmp and os.path.exists(_tmp):
            try:
                os.remove(_tmp)
            except OSError:
                pass
        logger.warning(f"Batch solve error for {filepath}: {e}")
        return {'solved': False, 'message': f"Error: {str(e)}"}
