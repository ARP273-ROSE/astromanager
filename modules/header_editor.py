#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AstroFileManager - Mass FITS Header Editor
===========================================
Edit any FITS header field in bulk across thousands of files.
Supports FITS, XISF, and FITS.FZ formats.

Based on NINA standard header fields with full bilingual (EN/FR) support.
"""

import os
import re
import shutil
import struct
import logging
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Any, Callable

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NINA-compatible FITS header field definitions
# Based on the NINA file pattern screenshot + standard FITS keywords
# ---------------------------------------------------------------------------

# Categories matching NINA's organization
HEADER_CATEGORIES = {
    'acquisition': {
        'en': 'Acquisition',
        'fr': 'Acquisition',
    },
    'camera': {
        'en': 'Camera',
        'fr': 'Caméra',
    },
    'image': {
        'en': 'Image',
        'fr': 'Image',
    },
    'filter': {
        'en': 'Filter Wheel',
        'fr': 'Roue à Filtres',
    },
    'focus': {
        'en': 'Focus',
        'fr': 'Focalisation',
    },
    'guiding': {
        'en': 'Guiding',
        'fr': 'Guidage',
    },
    'rotator': {
        'en': 'Rotator',
        'fr': 'Rotateur',
    },
    'weather': {
        'en': 'Weather',
        'fr': 'Météo',
    },
    'telescope': {
        'en': 'Telescope',
        'fr': 'Télescope',
    },
    'coordinates': {
        'en': 'Coordinates',
        'fr': 'Coordonnées',
    },
    'processing': {
        'en': 'Processing',
        'fr': 'Traitement',
    },
    'software': {
        'en': 'Software',
        'fr': 'Logiciel',
    },
}

# Complete FITS header field definitions
# Each field: fits_key, category, type, description_en, description_fr, aliases
HEADER_FIELDS = {
    # ---- Acquisition ----
    'DATE-OBS': {
        'category': 'acquisition',
        'type': 'string',
        'en': 'Observation date/time (ISO 8601)',
        'fr': "Date/heure d'observation (ISO 8601)",
        'aliases': ['DATE', 'DATE_OBS'],
        'pattern': '$$DATETIME$$',
        'editable': True,
        'default_visible': True,
    },
    'MJD-OBS': {
        'category': 'acquisition',
        'type': 'float',
        'en': 'Modified Julian Date',
        'fr': 'Date Julienne Modifiée',
        'aliases': ['MJD'],
        'pattern': '$$MJD$$',
        'editable': True,
        'default_visible': False,
    },
    'DATE-LOC': {
        'category': 'acquisition',
        'type': 'string',
        'en': 'Local date (DATE-OBS minus 12h, YYYY-MM-DD)',
        'fr': 'Date locale (DATE-OBS moins 12h, AAAA-MM-JJ)',
        'aliases': ['DATELOC'],
        'pattern': '$$DATEMINUS12$$',
        'editable': True,
        'default_visible': False,
    },
    'DATE': {
        'category': 'acquisition',
        'type': 'string',
        'en': 'UTC date (YYYY-MM-DD)',
        'fr': 'Date UTC (AAAA-MM-JJ)',
        'aliases': ['DATEUTC'],
        'pattern': '$$DATEUTC$$',
        'editable': True,
        'default_visible': False,
    },
    'TIME-OBS': {
        'category': 'acquisition',
        'type': 'string',
        'en': 'Observation time (HH:MM:SS)',
        'fr': "Heure d'observation (HH:MM:SS)",
        'aliases': ['TIMEOBS'],
        'pattern': '$$TIME$$',
        'editable': True,
        'default_visible': False,
    },
    # ---- Camera ----
    'INSTRUME': {
        'category': 'camera',
        'type': 'string',
        'en': 'Camera name',
        'fr': 'Nom de la caméra',
        'aliases': ['CAMERA', 'CAMERAN', 'CCD-NAME'],
        'pattern': '$$CAMERA$$',
        'editable': True,
        'default_visible': True,
    },
    'XBINNING': {
        'category': 'camera',
        'type': 'int',
        'en': 'Horizontal binning',
        'fr': 'Binning horizontal',
        'aliases': ['BINX'],
        'pattern': '$$BINNING$$',
        'editable': True,
        'default_visible': True,
    },
    'YBINNING': {
        'category': 'camera',
        'type': 'int',
        'en': 'Vertical binning',
        'fr': 'Binning vertical',
        'aliases': ['BINY'],
        'pattern': '$$BINNING$$',
        'editable': True,
        'default_visible': True,
    },
    'GAIN': {
        'category': 'camera',
        'type': 'float',
        'en': 'Camera gain',
        'fr': 'Gain caméra',
        'aliases': ['EGAIN', 'ISOSPEED'],
        'pattern': '$$GAIN$$',
        'editable': True,
        'default_visible': True,
    },
    'OFFSET': {
        'category': 'camera',
        'type': 'int',
        'en': 'Camera offset',
        'fr': 'Offset caméra',
        'aliases': ['BLKLEVEL'],
        'pattern': '$$OFFSET$$',
        'editable': True,
        'default_visible': True,
    },
    'READOUTM': {
        'category': 'camera',
        'type': 'string',
        'en': 'Camera readout mode',
        'fr': 'Mode de lecture de la caméra',
        'aliases': ['READMODE'],
        'pattern': '$$READOUTMODE$$',
        'editable': True,
        'default_visible': False,
    },
    'CCD-TEMP': {
        'category': 'camera',
        'type': 'float',
        'en': 'Sensor temperature (°C)',
        'fr': 'Température capteur (°C)',
        'aliases': ['TEMPERAT', 'TEMPERATURE', 'TEMP', 'SET-TEMP'],
        'pattern': '$$SENSORTEMP$$',
        'editable': True,
        'default_visible': True,
    },
    'SET-TEMP': {
        'category': 'camera',
        'type': 'float',
        'en': 'Temperature setpoint (°C)',
        'fr': 'Consigne de température (°C)',
        'aliases': ['TEMPSET'],
        'pattern': '$$TEMPERATURESETPOINT$$',
        'editable': True,
        'default_visible': False,
    },
    'USBLIMIT': {
        'category': 'camera',
        'type': 'int',
        'en': 'USB bandwidth limit',
        'fr': "Limite de bande passante USB",
        'aliases': [],
        'pattern': '$$USBLIMIT$$',
        'editable': True,
        'default_visible': False,
    },
    'BAYERPAT': {
        'category': 'camera',
        'type': 'string',
        'en': 'Bayer pattern (RGGB, GRBG, etc.)',
        'fr': 'Motif Bayer (RGGB, GRBG, etc.)',
        'aliases': ['BAYERPATN', 'COLORTYP'],
        'editable': True,
        'default_visible': False,
    },
    'XPIXSZ': {
        'category': 'camera',
        'type': 'float',
        'en': 'Pixel size X (microns)',
        'fr': 'Taille pixel X (microns)',
        'aliases': ['PIXSIZE1', 'PIXELSX'],
        'pattern': '$$PIXELSIZE$$',
        'editable': True,
        'default_visible': False,
    },
    'YPIXSZ': {
        'category': 'camera',
        'type': 'float',
        'en': 'Pixel size Y (microns)',
        'fr': 'Taille pixel Y (microns)',
        'aliases': ['PIXSIZE2', 'PIXELSY'],
        'pattern': '$$PIXELSIZE$$',
        'editable': True,
        'default_visible': False,
    },
    'EGAIN': {
        'category': 'camera',
        'type': 'float',
        'en': 'Electronic gain (e-/ADU)',
        'fr': 'Gain électronique (e-/ADU)',
        'aliases': ['EPERADU', 'ELECTRGN'],
        'pattern': '$$EGAIN$$',
        'editable': True,
        'default_visible': False,
    },
    # ---- Image ----
    'EXPTIME': {
        'category': 'image',
        'type': 'float',
        'en': 'Exposure time (seconds)',
        'fr': "Temps d'exposition (secondes)",
        'aliases': ['EXPOSURE'],
        'pattern': '$$EXPOSURETIME$$',
        'editable': True,
        'default_visible': True,
    },
    'IMAGETYP': {
        'category': 'image',
        'type': 'string',
        'en': 'Image type (Light, Dark, Flat, Bias)',
        'fr': "Type d'image (Light, Dark, Flat, Bias)",
        'aliases': ['IMTYPE', 'FRAME'],
        'pattern': '$$IMAGETYPE$$',
        'editable': True,
        'default_visible': True,
    },
    'OBJECT': {
        'category': 'image',
        'type': 'string',
        'en': 'Target name',
        'fr': 'Nom de la cible',
        'aliases': ['OBJNAME', 'TARGNAME'],
        'pattern': '$$TARGETNAME$$',
        'editable': True,
        'default_visible': True,
    },
    'SEQTITLE': {
        'category': 'image',
        'type': 'string',
        'en': 'Sequence title',
        'fr': 'Titre de la séquence',
        'aliases': [],
        'pattern': '$$SEQUENCETITLE$$',
        'editable': True,
        'default_visible': False,
    },
    'HFR': {
        'category': 'image',
        'type': 'float',
        'en': 'Half Flux Radius',
        'fr': "Rayon de demi-flux",
        'aliases': [],
        'pattern': '$$HFR$$',
        'editable': True,
        'default_visible': False,
    },
    'STARS': {
        'category': 'image',
        'type': 'int',
        'en': 'Star count',
        'fr': "Nombre d'étoiles",
        'aliases': ['STARCOUNT', 'NSTARS'],
        'pattern': '$$STARCOUNT$$',
        'editable': True,
        'default_visible': False,
    },
    'NAXIS1': {
        'category': 'image',
        'type': 'int',
        'en': 'Image width (pixels)',
        'fr': "Largeur de l'image (pixels)",
        'aliases': [],
        'editable': False,
        'default_visible': True,
    },
    'NAXIS2': {
        'category': 'image',
        'type': 'int',
        'en': 'Image height (pixels)',
        'fr': "Hauteur de l'image (pixels)",
        'aliases': [],
        'editable': False,
        'default_visible': True,
    },
    'BITPIX': {
        'category': 'image',
        'type': 'int',
        'en': 'Bits per pixel',
        'fr': 'Bits par pixel',
        'aliases': [],
        'editable': False,
        'default_visible': False,
    },
    'FRAMENR': {
        'category': 'image',
        'type': 'int',
        'en': 'Frame number in sequence',
        'fr': 'Numéro de frame dans la séquence',
        'aliases': ['FRAMENUM', 'FRAMENO'],
        'pattern': '$$FRAMENR$$',
        'editable': True,
        'default_visible': False,
    },
    'ROWORDER': {
        'category': 'image',
        'type': 'string',
        'en': 'Row order (TOP-DOWN / BOTTOM-UP)',
        'fr': "Ordre des lignes (TOP-DOWN / BOTTOM-UP)",
        'aliases': [],
        'editable': True,
        'default_visible': False,
    },
    # ---- Filter ----
    'FILTER': {
        'category': 'filter',
        'type': 'string',
        'en': 'Filter name',
        'fr': 'Nom du filtre',
        'aliases': ['FILTRE', 'FILT'],
        'pattern': '$$FILTER$$',
        'editable': True,
        'default_visible': True,
    },
    'FLTPOS': {
        'category': 'filter',
        'type': 'int',
        'en': 'Filter wheel position',
        'fr': 'Position de la roue à filtres',
        'aliases': ['FILTERPOS', 'FILTPOS'],
        'pattern': '$$FILTERPOSITION$$',
        'editable': True,
        'default_visible': False,
    },
    # ---- Focus ----
    'FOCPOS': {
        'category': 'focus',
        'type': 'int',
        'en': 'Focuser position',
        'fr': 'Position du focaliseur',
        'aliases': ['FOCUSPOS', 'FOCUS'],
        'pattern': '$$FOCUSERPOSITION$$',
        'editable': True,
        'default_visible': False,
    },
    'FOCTEMP': {
        'category': 'focus',
        'type': 'float',
        'en': 'Focuser temperature (°C)',
        'fr': 'Température du focaliseur (°C)',
        'aliases': ['FOCUSTEM'],
        'pattern': '$$FOCUSERTEMP$$',
        'editable': True,
        'default_visible': False,
    },
    'FWHM': {
        'category': 'focus',
        'type': 'float',
        'en': 'Full Width at Half Maximum',
        'fr': 'Largeur à mi-hauteur',
        'aliases': [],
        'pattern': '$$FWHM$$',
        'editable': True,
        'default_visible': False,
    },
    'ECCENT': {
        'category': 'focus',
        'type': 'float',
        'en': 'Eccentricity',
        'fr': 'Excentricité',
        'aliases': ['ECCENTRICITY'],
        'pattern': '$$ECCENTRICITY$$',
        'editable': True,
        'default_visible': False,
    },
    # ---- Guiding ----
    'GUIDRMS': {
        'category': 'guiding',
        'type': 'float',
        'en': 'Guiding RMS error (pixels)',
        'fr': 'Erreur RMS de guidage (pixels)',
        'aliases': ['AGGRMS'],
        'pattern': '$$RMS$$',
        'editable': True,
        'default_visible': False,
    },
    'GUIDRMSA': {
        'category': 'guiding',
        'type': 'float',
        'en': 'Guiding RMS error (arcsec)',
        'fr': 'Erreur RMS de guidage (arcsec)',
        'aliases': ['AGGRMSA'],
        'pattern': '$$RMSARCSEC$$',
        'editable': True,
        'default_visible': False,
    },
    'PEAKDEC': {
        'category': 'guiding',
        'type': 'float',
        'en': 'Peak Dec guiding error (pixels)',
        'fr': 'Erreur max guidage Dec (pixels)',
        'aliases': [],
        'pattern': '$$PEAKDEC$$',
        'editable': True,
        'default_visible': False,
    },
    'PEAKRA': {
        'category': 'guiding',
        'type': 'float',
        'en': 'Peak RA guiding error (pixels)',
        'fr': 'Erreur max guidage RA (pixels)',
        'aliases': [],
        'pattern': '$$PEAKRA$$',
        'editable': True,
        'default_visible': False,
    },
    'GUIDRMSRA': {
        'category': 'guiding',
        'type': 'float',
        'en': 'Guiding RMS RA error (arcsec)',
        'fr': 'Erreur RMS guidage RA (arcsec)',
        'aliases': ['GUIDERAA'],
        'pattern': '$$GUIDINGERRORRAMEDIANARC$$',
        'editable': True,
        'default_visible': False,
    },
    'GUIDRMSD': {
        'category': 'guiding',
        'type': 'float',
        'en': 'Guiding RMS Dec error (arcsec)',
        'fr': 'Erreur RMS guidage Dec (arcsec)',
        'aliases': ['GUIDEDEA'],
        'pattern': '$$GUIDINGERRORDECMEDIANARC$$',
        'editable': True,
        'default_visible': False,
    },
    'PEAKRAA': {
        'category': 'guiding',
        'type': 'float',
        'en': 'Peak RA guiding error (arcsec)',
        'fr': 'Erreur max guidage RA (arcsec)',
        'aliases': [],
        'pattern': '$$PEAKRAARCSEC$$',
        'editable': True,
        'default_visible': False,
    },
    'PEAKDECA': {
        'category': 'guiding',
        'type': 'float',
        'en': 'Peak Dec guiding error (arcsec)',
        'fr': 'Erreur max guidage Dec (arcsec)',
        'aliases': [],
        'pattern': '$$PEAKDECARCSEC$$',
        'editable': True,
        'default_visible': False,
    },
    # ---- Rotator ----
    'ROTATION': {
        'category': 'rotator',
        'type': 'float',
        'en': 'Rotator angle (degrees)',
        'fr': 'Angle du rotateur (degrés)',
        'aliases': ['ROTATOR', 'ROTATANG', 'POSANGLE'],
        'pattern': '$$ROTATORANGLE$$',
        'editable': True,
        'default_visible': True,
    },
    # ---- Weather ----
    'SQM': {
        'category': 'weather',
        'type': 'float',
        'en': 'Sky Quality Meter (mag/arcsec²)',
        'fr': 'Qualité du ciel (mag/arcsec²)',
        'aliases': ['MPSAS', 'SKYQUAL'],
        'pattern': '$$SQM$$',
        'editable': True,
        'default_visible': False,
    },
    'AIRMASS': {
        'category': 'weather',
        'type': 'float',
        'en': 'Airmass',
        'fr': "Masse d'air",
        'aliases': [],
        'editable': True,
        'default_visible': False,
    },
    'AMBTEMP': {
        'category': 'weather',
        'type': 'float',
        'en': 'Ambient temperature (°C)',
        'fr': 'Température ambiante (°C)',
        'aliases': ['TEMPAMB'],
        'editable': True,
        'default_visible': False,
    },
    'HUMIDITY': {
        'category': 'weather',
        'type': 'float',
        'en': 'Humidity (%)',
        'fr': 'Humidité (%)',
        'aliases': [],
        'editable': True,
        'default_visible': False,
    },
    'CLOUDCVR': {
        'category': 'weather',
        'type': 'float',
        'en': 'Cloud cover (%)',
        'fr': 'Couverture nuageuse (%)',
        'aliases': ['CLOUD'],
        'editable': True,
        'default_visible': False,
    },
    'DEWPOINT': {
        'category': 'weather',
        'type': 'float',
        'en': 'Dew point temperature (°C)',
        'fr': 'Point de rosée (°C)',
        'aliases': ['DEWPT'],
        'editable': True,
        'default_visible': False,
    },
    'PRESSURE': {
        'category': 'weather',
        'type': 'float',
        'en': 'Atmospheric pressure (hPa)',
        'fr': 'Pression atmosphérique (hPa)',
        'aliases': ['BARO', 'ATMOSPR'],
        'editable': True,
        'default_visible': False,
    },
    'WINDSPD': {
        'category': 'weather',
        'type': 'float',
        'en': 'Wind speed (m/s)',
        'fr': 'Vitesse du vent (m/s)',
        'aliases': ['WINDVEL'],
        'editable': True,
        'default_visible': False,
    },
    'WINDDIR': {
        'category': 'weather',
        'type': 'float',
        'en': 'Wind direction (degrees)',
        'fr': 'Direction du vent (degrés)',
        'aliases': [],
        'editable': True,
        'default_visible': False,
    },
    # ---- Telescope ----
    'TELESCOP': {
        'category': 'telescope',
        'type': 'string',
        'en': 'Telescope description',
        'fr': 'Description du télescope',
        'aliases': ['SCOPE', 'TELESC'],
        'pattern': '$$TELESCOPE$$',
        'editable': True,
        'default_visible': True,
    },
    'FOCALLEN': {
        'category': 'telescope',
        'type': 'float',
        'en': 'Focal length (mm)',
        'fr': 'Longueur focale (mm)',
        'aliases': ['FOCAL', 'FOCLEN'],
        'editable': True,
        'default_visible': True,
    },
    'FOCRATIO': {
        'category': 'telescope',
        'type': 'float',
        'en': 'Focal ratio (f/D)',
        'fr': 'Rapport focal (f/D)',
        'aliases': ['APERTURE'],
        'editable': True,
        'default_visible': False,
    },
    'APTDIA': {
        'category': 'telescope',
        'type': 'float',
        'en': 'Aperture diameter (mm)',
        'fr': "Diamètre d'ouverture (mm)",
        'aliases': ['APTDIAM'],
        'editable': True,
        'default_visible': False,
    },
    'SCALE': {
        'category': 'telescope',
        'type': 'float',
        'en': 'Plate scale (arcsec/pixel)',
        'fr': "Échelle de plaque (arcsec/pixel)",
        'aliases': ['SECPIX', 'PIXSCALE', 'ARCSECPX', 'CDELT1'],
        'editable': True,
        'default_visible': False,
    },
    # ---- Coordinates ----
    'RA': {
        'category': 'coordinates',
        'type': 'float',
        'en': 'Right Ascension (degrees)',
        'fr': 'Ascension droite (degrés)',
        'aliases': ['OBJCTRA', 'CRVAL1'],
        'editable': True,
        'default_visible': True,
    },
    'DEC': {
        'category': 'coordinates',
        'type': 'float',
        'en': 'Declination (degrees)',
        'fr': 'Déclinaison (degrés)',
        'aliases': ['OBJCTDEC', 'CRVAL2'],
        'editable': True,
        'default_visible': True,
    },
    'SITELAT': {
        'category': 'coordinates',
        'type': 'float',
        'en': 'Site latitude (degrees)',
        'fr': 'Latitude du site (degrés)',
        'aliases': ['OBSLAT', 'LAT-OBS'],
        'editable': True,
        'default_visible': False,
    },
    'SITELONG': {
        'category': 'coordinates',
        'type': 'float',
        'en': 'Site longitude (degrees)',
        'fr': 'Longitude du site (degrés)',
        'aliases': ['OBSLONG', 'LONG-OBS'],
        'editable': True,
        'default_visible': False,
    },
    'SITEELEV': {
        'category': 'coordinates',
        'type': 'float',
        'en': 'Site elevation (m)',
        'fr': 'Altitude du site (m)',
        'aliases': ['OBSELEV', 'ALT-OBS'],
        'editable': True,
        'default_visible': False,
    },
    # ---- Software ----
    'SWCREATE': {
        'category': 'software',
        'type': 'string',
        'en': 'Capture software',
        'fr': 'Logiciel de capture',
        'aliases': ['CREATOR', 'PROGRAM', 'SOFTWARE'],
        'editable': True,
        'default_visible': False,
    },
    'OBSERVER': {
        'category': 'software',
        'type': 'string',
        'en': 'Observer name',
        'fr': "Nom de l'observateur",
        'aliases': [],
        'editable': True,
        'default_visible': False,
    },
}

# Default fields visible in the header editor table
DEFAULT_VISIBLE_FIELDS = [k for k, v in HEADER_FIELDS.items() if v.get('default_visible', False)]

# Fields that are typically safe to mass-edit
MASS_EDITABLE_FIELDS = [k for k, v in HEADER_FIELDS.items() if v.get('editable', False)]


# ---------------------------------------------------------------------------
# Header value type coercion
# ---------------------------------------------------------------------------

def coerce_header_value(value: str, field_type: str) -> Any:
    """Convert a string value to the appropriate FITS header type."""
    if value is None or (isinstance(value, str) and value.strip() == ''):
        return None
    
    if field_type == 'int':
        return int(float(value))
    elif field_type == 'float':
        return float(value)
    elif field_type == 'bool':
        return str(value).strip().upper() in ('TRUE', 'T', 'YES', '1')
    else:  # string
        return str(value).strip()


def format_header_value(value: Any, field_type: str) -> str:
    """Format a header value for display."""
    if value is None:
        return ''
    if field_type == 'float':
        try:
            f = float(value)
            if f == int(f) and abs(f) < 1e10:
                return f"{f:.1f}"
            return f"{f:.6g}"
        except (ValueError, TypeError):
            return str(value)
    return str(value)


# ---------------------------------------------------------------------------
# File type detection and header I/O
# ---------------------------------------------------------------------------

def detect_file_type(filepath: str) -> str:
    """Detect astronomical file type: 'fits', 'xisf', 'fz', or 'unknown'."""
    path = Path(filepath)
    name = path.name.lower()
    
    if name.endswith('.fits.fz') or name.endswith('.fit.fz'):
        return 'fz'
    elif name.endswith(('.fits', '.fit', '.fts')):
        return 'fits'
    elif name.endswith('.xisf'):
        return 'xisf'
    else:
        return 'unknown'


def read_header(filepath: str) -> Dict[str, Any]:
    """
    Read header from any supported format. Returns dict of keyword->value.
    For XISF, reads FITSKeyword elements from XML header.
    """
    ftype = detect_file_type(filepath)
    
    if ftype in ('fits', 'fz'):
        return _read_fits_header(filepath)
    elif ftype == 'xisf':
        return _read_xisf_header(filepath)
    else:
        raise ValueError(f"Unsupported file type: {filepath}")


def _read_fits_header(filepath: str) -> Dict[str, Any]:
    """Read header from FITS or FITS.FZ file."""
    try:
        from astropy.io import fits
    except ImportError:
        raise ImportError("astropy is required for FITS header reading")
    
    header_dict = {}
    with fits.open(filepath, mode='readonly', memmap=True) as hdul:
        # For compressed FITS (.fz), the image data is in extension 1
        if len(hdul) > 1 and hasattr(hdul[1], 'header'):
            header = hdul[1].header
            # Also merge primary header
            for key in hdul[0].header:
                if key and key not in ('', 'COMMENT', 'HISTORY', 'END'):
                    if key not in header:
                        header_dict[key] = hdul[0].header[key]
        else:
            header = hdul[0].header
        
        for key in header:
            if key and key not in ('', 'COMMENT', 'HISTORY', 'END'):
                header_dict[key] = header[key]
    
    return header_dict


def _read_xisf_header(filepath: str) -> Dict[str, Any]:
    """Read FITSKeyword elements from XISF XML header."""
    import xml.etree.ElementTree as ET
    
    header_dict = {}
    
    with open(filepath, 'rb') as f:
        # Read XISF signature
        sig = f.read(8)
        if sig != b'XISF0100':
            raise ValueError(f"Not a valid XISF file: {filepath}")
        
        # Read header length
        header_len = struct.unpack('<I', f.read(4))[0]
        f.read(4)  # reserved
        
        # Read XML header
        xml_data = f.read(header_len)
        xml_str = xml_data.rstrip(b'\x00').decode('utf-8', errors='replace')
    
    # Parse XML
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        logger.warning(f"Failed to parse XISF XML header: {filepath}")
        return header_dict
    
    ns = {'xisf': 'http://www.pixinsight.com/xisf'}
    
    # Find FITSKeyword elements
    for elem in root.iter():
        if elem.tag.endswith('FITSKeyword') or elem.tag == 'FITSKeyword':
            name = elem.get('name', '').strip()
            value = elem.get('value', '').strip()
            
            if not name:
                continue
            
            # Parse value types
            if value.startswith("'") and value.endswith("'"):
                # String value
                header_dict[name] = value[1:-1].strip()
            elif value.upper() == 'T':
                header_dict[name] = True
            elif value.upper() == 'F':
                header_dict[name] = False
            else:
                try:
                    if '.' in value or 'E' in value.upper():
                        header_dict[name] = float(value)
                    else:
                        header_dict[name] = int(value)
                except ValueError:
                    header_dict[name] = value
    
    return header_dict


# ---------------------------------------------------------------------------
# Header writing
# ---------------------------------------------------------------------------

def write_header_changes(filepath: str, changes: Dict[str, Any],
                         backup: bool = True) -> bool:
    """
    Apply header changes to a file. Supports FITS, XISF, FITS.FZ.
    
    Args:
        filepath: Path to the file
        changes: Dict of {keyword: new_value}. Value=None removes the key.
        backup: If True, create .bak backup before modifying
    
    Returns:
        True if successful
    """
    ftype = detect_file_type(filepath)
    
    if backup:
        bak = filepath + '.bak'
        if not os.path.exists(bak):
            shutil.copy2(filepath, bak)
    
    try:
        if ftype in ('fits', 'fz'):
            return _write_fits_header(filepath, changes)
        elif ftype == 'xisf':
            return _write_xisf_header(filepath, changes)
        else:
            logger.error(f"Unsupported file type for writing: {filepath}")
            return False
    except Exception as e:
        logger.error(f"Failed to write header for {filepath}: {e}")
        # Restore backup on failure
        if backup:
            bak = filepath + '.bak'
            if os.path.exists(bak):
                shutil.copy2(bak, filepath)
        return False


def _write_fits_header(filepath: str, changes: Dict[str, Any]) -> bool:
    """Write header changes to a FITS or FITS.FZ file."""
    try:
        from astropy.io import fits
    except ImportError:
        raise ImportError("astropy is required for FITS header writing")
    
    with fits.open(filepath, mode='update') as hdul:
        # Determine which HDU to modify
        if len(hdul) > 1 and hasattr(hdul[1], 'header'):
            header = hdul[1].header
        else:
            header = hdul[0].header
        
        for key, value in changes.items():
            if value is None:
                # Remove key
                if key in header:
                    del header[key]
            else:
                # Add/update key
                field_def = HEADER_FIELDS.get(key, {})
                field_type = field_def.get('type', 'string')
                
                try:
                    typed_value = coerce_header_value(str(value), field_type)
                    if typed_value is not None:
                        header[key] = typed_value
                except (ValueError, TypeError) as e:
                    logger.warning(f"Cannot set {key}={value}: {e}")
        
        hdul.flush()
    
    return True


def _write_xisf_header(filepath: str, changes: Dict[str, Any]) -> bool:
    """Write header changes to an XISF file by modifying the XML header."""
    import xml.etree.ElementTree as ET
    
    with open(filepath, 'rb') as f:
        sig = f.read(8)
        if sig != b'XISF0100':
            raise ValueError(f"Not a valid XISF file: {filepath}")
        
        header_len = struct.unpack('<I', f.read(4))[0]
        reserved = f.read(4)
        xml_data = f.read(header_len)
        # Everything after the header
        data_offset = 16 + header_len
        f.seek(data_offset)
        rest_of_file = f.read()
    
    xml_str = xml_data.rstrip(b'\x00').decode('utf-8', errors='replace')
    
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        logger.error(f"Failed to parse XISF XML: {filepath}")
        return False
    
    ns = 'http://www.pixinsight.com/xisf'
    
    # Find the Image element (parent of FITSKeyword elements)
    image_elem = None
    for elem in root.iter():
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        if tag == 'Image':
            image_elem = elem
            break
    
    if image_elem is None:
        logger.error(f"No Image element found in XISF: {filepath}")
        return False
    
    # Build map of existing FITSKeyword elements
    existing_keywords = {}
    for child in list(image_elem):
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag == 'FITSKeyword':
            name = child.get('name', '')
            existing_keywords[name] = child
    
    for key, value in changes.items():
        if value is None:
            # Remove keyword
            if key in existing_keywords:
                image_elem.remove(existing_keywords[key])
                del existing_keywords[key]
        else:
            # Format value for XISF FITSKeyword
            field_def = HEADER_FIELDS.get(key, {})
            field_type = field_def.get('type', 'string')
            
            try:
                typed_value = coerce_header_value(str(value), field_type)
            except (ValueError, TypeError):
                typed_value = str(value)
            
            if isinstance(typed_value, str):
                xisf_value = f"'{typed_value}'"
            elif isinstance(typed_value, bool):
                xisf_value = 'T' if typed_value else 'F'
            elif isinstance(typed_value, float):
                xisf_value = f"{typed_value}"
            elif isinstance(typed_value, int):
                xisf_value = f"{typed_value}"
            else:
                xisf_value = f"'{typed_value}'"
            
            if key in existing_keywords:
                existing_keywords[key].set('value', xisf_value)
            else:
                # Create new FITSKeyword element
                new_elem = ET.SubElement(image_elem, f'{{{ns}}}FITSKeyword')
                new_elem.set('name', key)
                new_elem.set('value', xisf_value)
                new_elem.set('comment', '')
                existing_keywords[key] = new_elem
    
    # Serialize XML back
    new_xml = ET.tostring(root, encoding='unicode', xml_declaration=True)
    new_xml_bytes = new_xml.encode('utf-8')
    
    # Pad to maintain alignment (XISF requires header to be consistent)
    # If new XML is shorter, pad with null bytes to original length
    # If longer, we need to rewrite the file with adjusted offsets
    if len(new_xml_bytes) <= header_len:
        # Pad to original length
        new_xml_bytes = new_xml_bytes.ljust(header_len, b'\x00')
        
        with open(filepath, 'r+b') as f:
            f.seek(16)  # Skip signature + length + reserved
            f.write(new_xml_bytes)
        
        return True
    else:
        # Need to rewrite the entire file with new header length
        # This requires adjusting data block offsets in the XML
        # For safety, we rewrite from scratch
        new_header_len = ((len(new_xml_bytes) + 4095) // 4096) * 4096
        new_xml_bytes = new_xml_bytes.ljust(new_header_len, b'\x00')
        
        offset_delta = new_header_len - header_len

        # Adjust attachment offsets in the XML
        xml_adjusted = _adjust_xisf_offsets(new_xml_bytes.decode('utf-8', errors='replace'),
                                             offset_delta)
        adjusted_bytes = xml_adjusted.encode('utf-8')
        # Re-check: adjusted offsets may have more digits, causing XML to grow
        if len(adjusted_bytes) > new_header_len:
            new_header_len = ((len(adjusted_bytes) + 4095) // 4096) * 4096
            # Re-adjust with corrected delta
            offset_delta = new_header_len - header_len
            xml_adjusted = _adjust_xisf_offsets(new_xml_bytes.decode('utf-8', errors='replace'),
                                                 offset_delta)
            adjusted_bytes = xml_adjusted.encode('utf-8')
        new_xml_bytes = adjusted_bytes.ljust(new_header_len, b'\x00')
        
        with open(filepath, 'wb') as f:
            f.write(b'XISF0100')
            f.write(struct.pack('<I', new_header_len))
            f.write(reserved)
            f.write(new_xml_bytes)
            f.write(rest_of_file)
        
        return True


def _adjust_xisf_offsets(xml_str: str, delta: int) -> str:
    """Adjust attachment:offset:size references in XISF XML when header size changes."""
    def replace_offset(match):
        offset = int(match.group(1))
        size = match.group(2)
        new_offset = offset + delta
        return f'attachment:{new_offset}:{size}'
    
    return re.sub(r'attachment:(\d+):(\d+)', replace_offset, xml_str)


# ---------------------------------------------------------------------------
# Resolve alias: find the actual key used in a header
# ---------------------------------------------------------------------------

def resolve_key(header: Dict[str, Any], canonical_key: str) -> Optional[str]:
    """
    Find which actual key is present in a header for a canonical field.
    Checks the canonical key first, then all known aliases.
    Returns the actual key found, or None.
    """
    if canonical_key in header:
        return canonical_key
    
    field_def = HEADER_FIELDS.get(canonical_key, {})
    for alias in field_def.get('aliases', []):
        if alias in header:
            return alias
    
    return None


def get_header_value(header: Dict[str, Any], canonical_key: str) -> Any:
    """Get a header value by canonical key, checking aliases."""
    actual_key = resolve_key(header, canonical_key)
    if actual_key is not None:
        return header[actual_key]
    return None


# ---------------------------------------------------------------------------
# Batch header reading (parallel)
# ---------------------------------------------------------------------------

def _read_header_worker(filepath: str, fields: List[str]) -> Tuple[str, Dict[str, Any]]:
    """Worker function for parallel header reading."""
    try:
        header = read_header(filepath)
        result = {}
        for field in fields:
            val = get_header_value(header, field)
            result[field] = val
        return (filepath, result)
    except Exception as e:
        return (filepath, {'_error': str(e)})


def read_headers_batch(filepaths: List[str],
                       fields: Optional[List[str]] = None,
                       num_workers: int = 4,
                       progress_callback: Optional[Callable] = None,
                       stop_event=None) -> Dict[str, Dict[str, Any]]:
    """
    Read header fields from multiple files in parallel.
    
    Args:
        filepaths: List of file paths to read
        fields: List of canonical field names to extract (None = all known fields)
        num_workers: Number of parallel workers
        progress_callback: Called with (completed, total) for progress updates
        stop_event: threading.Event to signal cancellation
    
    Returns:
        Dict of {filepath: {field: value}}
    """
    if fields is None:
        fields = list(HEADER_FIELDS.keys())
    
    results = {}
    total = len(filepaths)
    completed = 0
    
    if num_workers <= 1 or total <= 5:
        # Serial execution for small batches
        for fp in filepaths:
            if stop_event and stop_event.is_set():
                break
            fp_str, data = _read_header_worker(fp, fields)
            results[fp_str] = data
            completed += 1
            if progress_callback:
                progress_callback(completed, total)
    else:
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = {executor.submit(_read_header_worker, fp, fields): fp
                       for fp in filepaths}
            
            for future in as_completed(futures):
                if stop_event and stop_event.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                try:
                    fp_str, data = future.result(timeout=30)
                    results[fp_str] = data
                except Exception as e:
                    fp = futures[future]
                    results[fp] = {'_error': str(e)}
                
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)
    
    return results


# ---------------------------------------------------------------------------
# Batch header writing (parallel)
# ---------------------------------------------------------------------------

def _write_header_worker(filepath: str, changes: Dict[str, Any],
                         backup: bool) -> Tuple[str, bool, str]:
    """Worker function for parallel header writing."""
    try:
        success = write_header_changes(filepath, changes, backup=backup)
        return (filepath, success, '')
    except Exception as e:
        return (filepath, False, str(e))


def write_headers_batch(filepaths: List[str],
                        changes: Dict[str, Any],
                        backup: bool = True,
                        num_workers: int = 4,
                        progress_callback: Optional[Callable] = None,
                        stop_event=None) -> Dict[str, bool]:
    """
    Apply header changes to multiple files in parallel.
    
    Args:
        filepaths: List of file paths
        changes: Dict of {keyword: new_value} to apply to ALL files
        backup: Create .bak backups
        num_workers: Parallel workers
        progress_callback: Called with (completed, total)
        stop_event: threading.Event for cancellation
    
    Returns:
        Dict of {filepath: success_bool}
    """
    results = {}
    total = len(filepaths)
    completed = 0
    errors = []
    
    # Header writing can be I/O heavy; use fewer workers for safety
    safe_workers = min(num_workers, 4)
    
    if safe_workers <= 1 or total <= 3:
        for fp in filepaths:
            if stop_event and stop_event.is_set():
                break
            fp_str, success, err = _write_header_worker(fp, changes, backup)
            results[fp_str] = success
            if err:
                errors.append((fp_str, err))
            completed += 1
            if progress_callback:
                progress_callback(completed, total)
    else:
        with ProcessPoolExecutor(max_workers=safe_workers) as executor:
            futures = {executor.submit(_write_header_worker, fp, changes, backup): fp
                       for fp in filepaths}
            
            for future in as_completed(futures):
                if stop_event and stop_event.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                try:
                    fp_str, success, err = future.result(timeout=60)
                    results[fp_str] = success
                    if err:
                        errors.append((fp_str, err))
                except Exception as e:
                    fp = futures[future]
                    results[fp] = False
                    errors.append((fp, str(e)))
                
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)
    
    if errors:
        logger.warning(f"Header write errors: {len(errors)} files failed")
        for fp, err in errors[:5]:
            logger.warning(f"  {fp}: {err}")
    
    return results


# ---------------------------------------------------------------------------
# Per-file changes (different values per file)
# ---------------------------------------------------------------------------

def write_per_file_changes(file_changes: Dict[str, Dict[str, Any]],
                           backup: bool = True,
                           num_workers: int = 4,
                           progress_callback: Optional[Callable] = None,
                           stop_event=None) -> Dict[str, bool]:
    """
    Apply different header changes to each file.
    
    Args:
        file_changes: Dict of {filepath: {keyword: value}}
        backup: Create backups
        num_workers: Parallel workers
        progress_callback: Progress callback
        stop_event: Cancellation event
    
    Returns:
        Dict of {filepath: success_bool}
    """
    results = {}
    total = len(file_changes)
    completed = 0
    
    safe_workers = min(num_workers, 4)
    
    if safe_workers <= 1 or total <= 3:
        for fp, changes in file_changes.items():
            if stop_event and stop_event.is_set():
                break
            fp_str, success, _ = _write_header_worker(fp, changes, backup)
            results[fp_str] = success
            completed += 1
            if progress_callback:
                progress_callback(completed, total)
    else:
        with ProcessPoolExecutor(max_workers=safe_workers) as executor:
            futures = {}
            for fp, changes in file_changes.items():
                fut = executor.submit(_write_header_worker, fp, changes, backup)
                futures[fut] = fp
            
            for future in as_completed(futures):
                if stop_event and stop_event.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                try:
                    fp_str, success, _ = future.result(timeout=60)
                    results[fp_str] = success
                except Exception as e:
                    fp = futures[future]
                    results[fp] = False
                
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)
    
    return results


# ---------------------------------------------------------------------------
# Filename pattern builder
# ---------------------------------------------------------------------------

# Standard NINA-compatible filename pattern tokens
FILENAME_TOKENS = {
    '$$IMAGETYPE$$':    lambda h: _norm_image_type(get_header_value(h, 'IMAGETYP')),
    '$$TARGETNAME$$':   lambda h: _sanitize(get_header_value(h, 'OBJECT') or 'Unknown'),
    '$$DATE$$':         lambda h: _extract_date(get_header_value(h, 'DATE-OBS')),
    '$$DATETIME$$':     lambda h: _extract_datetime(get_header_value(h, 'DATE-OBS')),
    '$$TIME$$':         lambda h: _extract_time(get_header_value(h, 'DATE-OBS')),
    '$$FILTER$$':       lambda h: _sanitize(get_header_value(h, 'FILTER') or ''),
    '$$BINNING$$':      lambda h: _format_binning(h),
    '$$EXPOSURETIME$$': lambda h: _format_exposure(get_header_value(h, 'EXPTIME')),
    '$$ROTATORANGLE$$': lambda h: _format_rotation(get_header_value(h, 'ROTATION')),
    '$$SENSORTEMP$$':   lambda h: _format_temp(get_header_value(h, 'CCD-TEMP')),
    '$$TELESCOPE$$':    lambda h: _sanitize(get_header_value(h, 'TELESCOP') or 'Unknown'),
    '$$CAMERA$$':       lambda h: _sanitize(get_header_value(h, 'INSTRUME') or 'Unknown'),
    '$$GAIN$$':         lambda h: str(int(float(get_header_value(h, 'GAIN') or 0))),
    '$$SQM$$':          lambda h: f"{float(get_header_value(h, 'SQM') or 0):.2f}",
    '$$FWHM$$':         lambda h: f"{float(get_header_value(h, 'FWHM') or 0):.2f}",
    '$$HFR$$':          lambda h: f"{float(get_header_value(h, 'HFR') or 0):.2f}",
}

# Default filename pattern (NINA-compatible)
DEFAULT_FILENAME_PATTERN = (
    "$$IMAGETYPE$$_$$TARGETNAME$$_$$DATETIME$$_$$FILTER$$_"
    "$$BINNING$$_$$EXPOSURETIME$$s_$$ROTATORANGLE$$deg_"
    "$$SENSORTEMP$$_$$TELESCOPE$$_$$CAMERA$$"
)


def _sanitize(s: str) -> str:
    """Sanitize a string for use in filenames."""
    if not s:
        return ''
    s = s.strip()
    # Replace problematic characters
    s = re.sub(r'[<>:"/\\|?*\']', '_', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def _norm_image_type(raw: Any) -> str:
    """Normalize image type to standard form."""
    if not raw:
        return 'UNKNOWN'
    t = str(raw).strip().upper()
    if 'LIGHT' in t:
        return 'LIGHT'
    elif 'DARK' in t:
        return 'DARK'
    elif 'FLAT' in t:
        return 'FLAT'
    elif 'BIAS' in t or 'OFFSET' in t:
        return 'BIAS'
    return t


def _extract_date(date_obs: Any) -> str:
    """Extract date portion from DATE-OBS."""
    if not date_obs:
        return '0000-00-00'
    try:
        dt = datetime.fromisoformat(str(date_obs).replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d')
    except Exception:
        s = str(date_obs)[:10]
        return s if len(s) >= 10 else '0000-00-00'


def _extract_time(date_obs: Any) -> str:
    """Extract time portion from DATE-OBS."""
    if not date_obs:
        return '00-00-00'
    try:
        dt = datetime.fromisoformat(str(date_obs).replace('Z', '+00:00'))
        return dt.strftime('%H-%M-%S')
    except Exception:
        return '00-00-00'


def _extract_datetime(date_obs: Any) -> str:
    """Extract full datetime from DATE-OBS."""
    return f"{_extract_date(date_obs)}_{_extract_time(date_obs)}"


def _format_binning(header: Dict) -> str:
    """Format binning from header."""
    bx = get_header_value(header, 'XBINNING')
    by = get_header_value(header, 'YBINNING')
    bx = int(bx) if bx else 1
    by = int(by) if by else 1
    return f"{bx}x{by}"


def _format_exposure(exp: Any) -> str:
    """Format exposure time."""
    try:
        return f"{float(exp):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _format_rotation(rot: Any) -> str:
    """Format rotation angle."""
    try:
        return f"{float(rot):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _format_temp(temp: Any) -> str:
    """Format sensor temperature."""
    try:
        return str(int(round(float(temp))))
    except (TypeError, ValueError):
        return "0"


def build_filename(header: Dict[str, Any],
                   pattern: str = DEFAULT_FILENAME_PATTERN,
                   frame_number: int = 1,
                   extension: str = '') -> str:
    """
    Build a filename from header values using a NINA-compatible pattern.
    
    Args:
        header: Dict of header values (canonical keys)
        pattern: Filename pattern with $$TOKEN$$ placeholders
        frame_number: Frame number for $$FRAMENR$$
        extension: File extension (e.g., '.fits', '.xisf')
    
    Returns:
        Generated filename string
    """
    result = pattern
    
    for token, extractor in FILENAME_TOKENS.items():
        if token in result:
            try:
                value = extractor(header)
                result = result.replace(token, str(value))
            except Exception:
                result = result.replace(token, '')
    
    # Handle frame number separately
    result = result.replace('$$FRAMENR$$', f"{frame_number:04d}")
    
    # Clean up multiple underscores
    result = re.sub(r'_+', '_', result)
    result = result.strip('_')
    
    # Add frame number if not in pattern
    if '$$FRAMENR$$' not in pattern:
        result += f"_{frame_number:04d}"
    
    # Add extension
    if extension and not result.endswith(extension):
        result += extension
    
    return _sanitize(result)


# ---------------------------------------------------------------------------
# Batch rename files using header-based patterns
# ---------------------------------------------------------------------------

def rename_files_batch(filepaths: List[str],
                       pattern: str = DEFAULT_FILENAME_PATTERN,
                       output_dir: Optional[str] = None,
                       copy_mode: bool = False,
                       num_workers: int = 4,
                       progress_callback: Optional[Callable] = None,
                       stop_event=None) -> Dict[str, str]:
    """
    Rename (or copy) files based on header content and a naming pattern.
    
    Args:
        filepaths: List of files to rename
        pattern: NINA-compatible filename pattern
        output_dir: If set, copy files to this directory. If None, rename in place.
        copy_mode: If True, copy instead of rename
        num_workers: Workers for reading headers
        progress_callback: Progress callback
        stop_event: Cancellation event
    
    Returns:
        Dict of {old_path: new_path}
    """
    # First, read all headers
    headers = read_headers_batch(filepaths, num_workers=num_workers,
                                 progress_callback=progress_callback,
                                 stop_event=stop_event)
    
    if stop_event and stop_event.is_set():
        return {}
    
    # Sort by timestamp for frame numbering
    sorted_files = sorted(filepaths, key=lambda f: _get_timestamp(headers.get(f, {})))
    
    # Group by target+date+filter+telescope for frame numbering
    groups = {}
    for fp in sorted_files:
        h = headers.get(fp, {})
        target = get_header_value(h, 'OBJECT') or 'Unknown'
        date = _extract_date(get_header_value(h, 'DATE-OBS'))
        filt = get_header_value(h, 'FILTER') or ''
        scope = get_header_value(h, 'TELESCOP') or ''
        group_key = f"{target}_{date}_{filt}_{scope}"
        if group_key not in groups:
            groups[group_key] = []
        groups[group_key].append(fp)
    
    # Build rename map
    rename_map = {}
    for group_key, group_files in groups.items():
        for idx, fp in enumerate(group_files, 1):
            h = headers.get(fp, {})
            ext = Path(fp).suffix
            if fp.lower().endswith('.fits.fz'):
                ext = '.fits.fz'
            
            new_name = build_filename(h, pattern, frame_number=idx, extension=ext)
            
            if output_dir:
                new_path = os.path.join(output_dir, new_name)
            else:
                new_path = os.path.join(os.path.dirname(fp), new_name)
            
            # Avoid collisions
            if new_path != fp and os.path.exists(new_path):
                base, ext2 = os.path.splitext(new_path)
                counter = 2
                while os.path.exists(f"{base}_{counter}{ext2}"):
                    counter += 1
                new_path = f"{base}_{counter}{ext2}"
            
            rename_map[fp] = new_path
    
    # Execute renames/copies
    results = {}
    total = len(rename_map)
    done = 0
    
    for old_path, new_path in rename_map.items():
        if stop_event and stop_event.is_set():
            break
        
        try:
            if old_path == new_path:
                results[old_path] = new_path
            elif copy_mode:
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                shutil.copy2(old_path, new_path)
                results[old_path] = new_path
            else:
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                os.rename(old_path, new_path)
                results[old_path] = new_path
        except Exception as e:
            logger.error(f"Rename failed {old_path} -> {new_path}: {e}")
            results[old_path] = old_path  # Keep original
        
        done += 1
        if progress_callback:
            progress_callback(done, total)
    
    return results


def _get_timestamp(header: Dict) -> float:
    """Extract a timestamp for sorting."""
    date_obs = get_header_value(header, 'DATE-OBS')
    if date_obs:
        try:
            dt = datetime.fromisoformat(str(date_obs).replace('Z', '+00:00'))
            return dt.timestamp()
        except Exception:
            pass
    return 0.0


# ---------------------------------------------------------------------------
# Undo support - restore backups
# ---------------------------------------------------------------------------

def restore_backups(filepaths: List[str]) -> Dict[str, bool]:
    """Restore .bak files created during header editing."""
    results = {}
    for fp in filepaths:
        bak = fp + '.bak'
        if os.path.exists(bak):
            try:
                shutil.copy2(bak, fp)
                os.remove(bak)
                results[fp] = True
            except Exception as e:
                logger.error(f"Failed to restore {bak}: {e}")
                results[fp] = False
        else:
            results[fp] = False
    return results


def cleanup_backups(filepaths: List[str]) -> int:
    """Remove .bak files after confirming changes."""
    removed = 0
    for fp in filepaths:
        bak = fp + '.bak'
        if os.path.exists(bak):
            try:
                os.remove(bak)
                removed += 1
            except Exception:
                pass
    return removed


# ---------------------------------------------------------------------------
# Scan directory for supported files
# ---------------------------------------------------------------------------

def scan_directory(folder: str,
                   recursive: bool = True,
                   skip_calibration: bool = False,
                   skip_pixinsight: bool = True) -> List[str]:
    """
    Scan a directory for supported astronomical image files.
    
    Args:
        folder: Directory to scan
        recursive: Include subdirectories
        skip_calibration: Skip calibration frames (bias, dark, flat masters)
        skip_pixinsight: Skip PixInsight processing artifacts
    
    Returns:
        List of file paths
    """
    extensions = {'.fits', '.fit', '.fts', '.xisf', '.fz'}
    
    # PixInsight artifact patterns
    pi_patterns = {'_c.xisf', '_d.xisf', '_r.xisf', '_cc.xisf',
                   '_cal.xisf', '_cal.fits', '_drizzle', '_ABE', '_DBE'}
    pi_prefixes = {'master', 'calibrated', 'registered', 'integrated'}
    
    files = []
    folder_path = Path(folder)
    
    if recursive:
        file_iter = folder_path.rglob('*')
    else:
        file_iter = folder_path.glob('*')
    
    for f in file_iter:
        if not f.is_file():
            continue
        
        name = f.name.lower()
        
        # Check extension
        if name.endswith('.fits.fz') or name.endswith('.fit.fz'):
            ext_match = True
        elif f.suffix.lower() in extensions:
            ext_match = True
        else:
            ext_match = False
        
        if not ext_match:
            continue
        
        # Skip PixInsight artifacts
        if skip_pixinsight:
            if any(name.endswith(p) for p in pi_patterns):
                continue
            if any(name.startswith(p) for p in pi_prefixes):
                continue
            # Skip common processing directories
            parts = [p.lower() for p in f.parts]
            if any(d in parts for d in ['calibrated', 'registered', 'integrated',
                                         'process', 'masters', 'output']):
                continue
        
        # Skip calibration directories
        if skip_calibration:
            parts_lower = [p.lower() for p in f.parts]
            if any(d in parts_lower for d in ['bias', 'dark', 'flat', 'calibration']):
                continue
        
        files.append(str(f))
    
    return sorted(files)
