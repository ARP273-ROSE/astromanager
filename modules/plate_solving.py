#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - PLATE SOLVING MODULE
================================================================================
Wrapper for ASTAP and Astrometry.net plate solvers.
Detects focal reducers by comparing measured vs expected plate scale.
================================================================================
"""

import os
import sys
import subprocess
import logging
import configparser
import glob
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

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
