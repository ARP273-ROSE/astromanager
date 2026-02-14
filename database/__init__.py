#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AstroManager - Equipment & Catalog Databases
==================================================
Unified access to camera, telescope, filter, and target databases.
"""

from .cameras import (
    SENSORS_DATABASE, INSTRUMENT_HEADER_MAPPING,
    normalize_camera_name, lookup_camera, get_pixel_size,
    get_sensor_dimensions, is_color_camera, list_cameras_by_brand,
)

from .telescopes import (
    TELESCOPES_DATABASE, TELESCOPE_HEADER_MAPPING,
    normalize_telescope_name, lookup_telescope, get_focal_length,
    get_aperture, get_focal_ratio, calculate_image_scale,
    calculate_fov, detect_focal_reducer, list_telescopes_by_brand,
)

from .filters import (
    FILTERS_DATABASE, FILTER_ALIASES,
    normalize_filter_name, lookup_filter, get_filter_type,
    is_narrowband, get_filter_wavelength, classify_filter_set,
    detect_palette, list_filters_by_type,
)

from .targets import (
    MESSIER_DATABASE, EXTENDED_ASTRONOMICAL_DATABASE, ARP_DATABASE,
    SOLAR_SYSTEM_OBJECTS, TARGET_TYPES,
    resolve_target_name, resolve_target_simbad, are_same_target,
    classify_target_type, is_calibration_target, search_catalogs,
)
