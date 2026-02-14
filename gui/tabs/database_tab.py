#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - DATABASE BROWSER TAB
================================================================================
Browse, search, and explore the built-in reference databases:
cameras, telescopes, filters, and astronomical targets.
================================================================================
"""

import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget, QAbstractItemView,
    QLineEdit, QComboBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from core.config import get_config
from gui.theme import get_mono_font, prettify_filter_name

logger = logging.getLogger(__name__)


# ============================================================================
# Brand / type classification helpers (module-level for reuse)
# ============================================================================

_CAM_BRAND_RULES = [
    # (prefixes_tuple, brand_name)
    (('ASI',), 'ZWO'),
    (('QHY',), 'QHY'),
    (('STF', 'STT', 'STX', 'ST-', 'SBIG'), 'SBIG'),
    (('FLI ', 'PROLINE', 'MICROLINE', 'FLI-', 'FLI_'), 'FLI'),
    (('ATIK',), 'Atik'),
    (('MARS', 'NEPTUNE', 'ARES', 'POSEIDON', 'APOLLO', 'ARTEMIS'), 'Player One'),
    (('TOUPTEK', 'TOUPCAM', 'OGMA', 'RISINGCAM'), 'Touptek'),
    (('CANON', 'EOS '), 'Canon'),
    (('NIKON', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'Z '), 'Nikon'),
    (('SONY', 'ILCE', 'A7', 'A9', 'A1 ', 'A6'), 'Sony'),
    (('FUJI', 'X-T', 'X-H', 'X-S', 'X-E', 'GFX'), 'Fujifilm'),
    (('PENTAX', 'K-'), 'Pentax'),
    (('OLYMPUS', 'OM-', 'E-M', 'E-P'), 'Olympus'),
    (('SVBONY',), 'SVBONY'),
    (('ALTAIR',), 'Altair'),
    (('MALLINCAM',), 'Mallincam'),
    (('SEESTAR', 'VAONIS', 'UNISTELLAR', 'STELLINA', 'VESPERA', 'DWARF'), 'Smart Scope'),
    (('BASLER', 'FLIR', 'IDS', 'PCO', 'ANDOR', 'HAMAMATSU', 'TELEDYNE'), 'Scientific'),
]

_TEL_BRAND_RULES = {
    'Takahashi': ('FC', 'TSA', 'TOA', 'FSQ', 'Epsilon', 'Mewlon', 'BRT', 'CN-', 'CCA', 'SKY90', 'FS-', 'Takahashi'),
    'Celestron': ('CPC', 'C5', 'C6', 'C8', 'C9', 'C11', 'C14', 'RASA', 'EdgeHD', 'NexStar', 'CGX', 'AVX', 'Celestron'),
    'Sky-Watcher': ('SW ', 'HEQ', 'EQ', 'Evostar', 'Esprit', 'Explorer', 'Quattro', 'Heritage', 'Dobson', 'Skyliner', 'Starquest', 'Virtuoso', 'Skywatcher', 'Sky-Watcher', 'Sky Watcher'),
    'Meade': ('Meade', 'LX', 'ACF', 'ETX'),
    'William Optics': ('WO ', 'ZenithStar', 'GT ', 'RedCat', 'SpaceCat', 'FluoroStar', 'Pleiades'),
    'Vixen': ('Vixen', 'VSD', 'VC200', 'VMC', 'AX103', 'FL55', 'SD103', 'SD115'),
    'Askar': ('Askar', 'FMA', 'FRA'),
    'Sharpstar': ('Sharpstar', 'SCA', '61EDPH', '76EDPH', '94EDPH'),
    'Tele Vue': ('TV-', 'Tele Vue', 'NP', 'Nagler'),
    'Stellarvue': ('Stellarvue', 'SVX', 'SV '),
    'Planewave': ('CDK', 'Planewave', 'PW '),
    'Explore Scientific': ('ES ', 'ED80', 'ED102', 'ED127', 'FCD'),
    'APM': ('APM',),
    'TEC': ('TEC',),
    'ASA': ('ASA',),
    'BORG': ('BORG',),
    'Orion': ('Orion',),
    'GSO': ('GSO',),
    'TS Optics': ('TS ', 'TSO', 'TS-'),
    'Astro-Physics': ('Astro-Physics', 'AP ', 'Stowaway', 'Traveler'),
    'Officina Stellare': ('RH ', 'RHA', 'Riccardi', 'Veloce', 'Pro RC'),
    'Tecnosky': ('Tecnosky',),
    'Omegon': ('Omegon', 'OMEGON'),
    'Bresser': ('Bresser',),
    'Lacerta': ('Lacerta',),
    'Saxon': ('Saxon',),
    'TMB': ('TMB',),
    'Canon (lens)': ('Canon ',),
    'Nikon (lens)': ('Nikon ',),
    'Sigma (lens)': ('Sigma ',),
    'iTelescope': ('iTelescope',),
    'Oberwerk': ('Oberwerk',),
    'iOptron': ('iOptron',),
    'Levenhuk': ('Levenhuk',),
}


_FLT_BRAND_RULES = [
    # Sorted A-Z by brand name (parallel with _FLT_BRAND_NAMES)
    ('Altair',), ('Antlia',), ('Askar',), ('Astrodon',), ('Astronomik',), ('Baader',),
    ('Celestron',), ('Chroma',), ('Custom Scientific',),
    ('DayStar', 'Daystar'), ('Edmund',), ('Explore Scientific',),
    ('Hoya',), ('Hutech',), ('IDAS',), ('Lumicon',), ('Meade',),
    ('Omega ',), ('Optolong',), ('Orion ',), ('Player One',),
    ('Radian',), ('Schott',), ('Semrock',), ('Sightron',),
    ('Skywatcher', 'Sky-Watcher'), ('STC ',), ('SVBONY',),
    ('Thorlabs',), ('Thousand Oaks',), ('ZWO',),
]

_FLT_BRAND_NAMES = [
    'Altair', 'Antlia', 'Askar', 'Astrodon', 'Astronomik', 'Baader',
    'Celestron', 'Chroma', 'Custom Scientific',
    'DayStar', 'Edmund', 'Explore Scientific',
    'Hoya', 'Hutech', 'IDAS', 'Lumicon', 'Meade',
    'Omega', 'Optolong', 'Orion', 'Player One',
    'Radian', 'Schott', 'Semrock', 'Sightron',
    'Skywatcher', 'STC', 'SVBONY',
    'Thorlabs', 'Thousand Oaks', 'ZWO',
]


def _get_flt_brand(name):
    nl = name.lower()
    for i, prefixes in enumerate(_FLT_BRAND_RULES):
        for p in prefixes:
            if p.lower() in nl:
                return _FLT_BRAND_NAMES[i]
    return 'Generic'


def _get_flt_passband(center_nm, bandwidth_nm):
    """Classify filter by passband color based on center wavelength."""
    if center_nm == 0 or bandwidth_nm > 200:
        return 'Multi/White'
    if center_nm < 400:
        return 'UV'
    if center_nm < 500:
        return 'Blue'
    if center_nm < 570:
        return 'Green'
    if center_nm < 600:
        return 'Yellow'
    if center_nm < 700:
        return 'Red'
    return 'Near-IR'


def _get_flt_camera(ftype):
    """Classify filter target camera: Mono, Color, or Both."""
    if ftype == 'narrowband':
        return 'Mono'
    if ftype == 'dual_narrowband':
        return 'Color'
    return 'Both'


def _get_cam_brand(name):
    upper = name.upper()
    for prefixes, brand in _CAM_BRAND_RULES:
        for p in prefixes:
            if upper.startswith(p):
                return brand
    # Moravian: G + digit
    if upper.startswith('G') and len(name) > 1 and name[1:2].isdigit():
        return 'Moravian'
    return 'Other'


def _get_tel_brand(name):
    nl = name.lower()
    for brand, prefixes in _TEL_BRAND_RULES.items():
        for p in prefixes:
            if nl.startswith(p.lower()):
                return brand
    return 'Other'


class DatabaseTab(QWidget):
    """Database Browser tab - explore cameras, telescopes, filters, targets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self.lang = self.config.get('application.language', 'auto')
        if self.lang == 'auto':
            import locale
            try:
                loc = locale.getdefaultlocale()[0]
                self.lang = 'fr' if loc and loc.startswith('fr') else 'en'
            except Exception:
                self.lang = 'en'

        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)

        self._data_loaded = {
            'cameras': False, 'telescopes': False,
            'filters': False, 'targets': False,
        }

        self._init_ui()

    def _tr(self, en: str, fr: str) -> str:
        return fr if self.lang == 'fr' else en

    # =========================================================================
    # UI Init
    # =========================================================================

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header
        header = QHBoxLayout()
        title = QLabel(self._tr("Database Browser", "Explorateur de Bases de Données"))
        title.setStyleSheet("color: #94b8c8; font-size: 14pt; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        self.total_label = QLabel("")
        self.total_label.setStyleSheet("color: #7a8498; font-size: 10pt;")
        header.addWidget(self.total_label)
        layout.addLayout(header)

        # Sub-tabs
        self.sub_tabs = QTabWidget()
        self.sub_tabs.currentChanged.connect(self._on_subtab_changed)
        self.sub_tabs.addTab(self._create_cameras_panel(), self._tr("Cameras", "Caméras"))
        self.sub_tabs.addTab(self._create_telescopes_panel(), self._tr("Telescopes", "Télescopes"))
        self.sub_tabs.addTab(self._create_filters_panel(), self._tr("Filters", "Filtres"))
        self.sub_tabs.addTab(self._create_targets_panel(), self._tr("Targets", "Cibles"))
        layout.addWidget(self.sub_tabs)

        QTimer.singleShot(100, self._load_totals)
        QTimer.singleShot(200, lambda: self._ensure_data_loaded(0))

    def _load_totals(self):
        try:
            from database.cameras import SENSORS_DATABASE
            from database.telescopes import TELESCOPES_DATABASE
            from database.filters import FILTERS_DATABASE
            from database.targets import (
                MESSIER_DATABASE, EXTENDED_ASTRONOMICAL_DATABASE,
                ARP_DATABASE, SOLAR_SYSTEM_OBJECTS
            )
            c = len([k for k in SENSORS_DATABASE if k != 'default'])
            t = len([k for k in TELESCOPES_DATABASE if k != 'default'])
            f = len(FILTERS_DATABASE)
            tgt = (len(MESSIER_DATABASE) + len(EXTENDED_ASTRONOMICAL_DATABASE)
                   + len(ARP_DATABASE) + len(SOLAR_SYSTEM_OBJECTS))
            self.total_label.setText(self._tr(
                f"{c + t + f + tgt:,} entries total",
                f"{c + t + f + tgt:,} entrées au total"
            ))
        except Exception as e:
            logger.error(f"Failed to load totals: {e}")

    # =========================================================================
    # Shared helpers
    # =========================================================================

    def _create_table(self, columns):
        table = QTableWidget()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSortingEnabled(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(24)
        table.setFont(get_mono_font(9))
        h = table.horizontalHeader()
        h.setStretchLastSection(True)
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        return table

    def _num_item(self, sort_value, display_text):
        item = QTableWidgetItem(display_text)
        item.setData(Qt.ItemDataRole.UserRole, sort_value)
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return item

    def _make_combo(self, items, callback):
        combo = QComboBox()
        combo.setMinimumWidth(150)
        for en, fr in items:
            combo.addItem(self._tr(en, fr))
        combo.currentIndexChanged.connect(callback)
        return combo

    def _debounce(self, callback):
        """Connect a debounced search to callback."""
        try:
            self._search_timer.timeout.disconnect()
        except (TypeError, RuntimeError):
            pass
        self._search_timer.timeout.connect(callback)
        self._search_timer.start()

    # =========================================================================
    # CAMERAS
    # =========================================================================

    def _create_cameras_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        # Filter bar
        bar = QHBoxLayout()
        bar.setSpacing(6)
        bar.addWidget(QLabel("🔍"))
        self._cam_search = QLineEdit()
        self._cam_search.setPlaceholderText(self._tr("Search cameras...", "Chercher caméras..."))
        self._cam_search.textChanged.connect(lambda: self._debounce(self._apply_cam_filter))
        bar.addWidget(self._cam_search, 1)

        bar.addWidget(QLabel(self._tr("Brand:", "Marque:")))
        self._cam_brand = self._make_combo([
            ("All", "Toutes"),
            ("Altair", "Altair"), ("Atik", "Atik"), ("Canon", "Canon"),
            ("FLI", "FLI"), ("Fujifilm", "Fujifilm"),
            ("Mallincam", "Mallincam"), ("Moravian", "Moravian"),
            ("Nikon", "Nikon"), ("Olympus", "Olympus"), ("Pentax", "Pentax"),
            ("Player One", "Player One"), ("QHY", "QHY"),
            ("SBIG", "SBIG"), ("Scientific", "Scientifique"),
            ("Smart Scope", "Smart Scope"), ("Sony", "Sony"),
            ("SVBONY", "SVBONY"), ("Touptek", "Touptek"), ("ZWO", "ZWO"),
            ("Other", "Autre"),
        ], self._apply_cam_filter)
        bar.addWidget(self._cam_brand)

        bar.addWidget(QLabel(self._tr("Pixel:", "Pixel:")))
        self._cam_pixel = self._make_combo([
            ("All sizes", "Toutes tailles"),
            ("< 2.5 µm", "< 2.5 µm"),
            ("2.5 - 4 µm", "2.5 - 4 µm"),
            ("4 - 6 µm", "4 - 6 µm"),
            ("> 6 µm", "> 6 µm"),
        ], self._apply_cam_filter)
        bar.addWidget(self._cam_pixel)

        bar.addWidget(QLabel(self._tr("Res:", "Rés:")))
        self._cam_res = self._make_combo([
            ("All", "Toutes"),
            ("< 4 MP", "< 4 MP"),
            ("4 - 16 MP", "4 - 16 MP"),
            ("16 - 40 MP", "16 - 40 MP"),
            ("> 40 MP", "> 40 MP"),
        ], self._apply_cam_filter)
        bar.addWidget(self._cam_res)

        self._cam_count = QLabel("")
        self._cam_count.setStyleSheet("color: #7a8498; font-size: 9pt;")
        self._cam_count.setMinimumWidth(120)
        bar.addWidget(self._cam_count)

        bar_w = QWidget()
        bar_w.setLayout(bar)
        lay.addWidget(bar_w)

        # Table
        cols = [
            self._tr("Name", "Nom"),
            self._tr("Brand", "Marque"),
            self._tr("Pixel (µm)", "Pixel (µm)"),
            self._tr("Resolution", "Résolution"),
            self._tr("Gain", "Gain"),
            self._tr("Read Noise (e⁻)", "Bruit (e⁻)"),
            self._tr("Full Well (e⁻)", "Puits (e⁻)"),
            self._tr("QE (%)", "QE (%)"),
        ]
        self._cam_table = self._create_table(cols)
        self._cam_table.setColumnWidth(0, 200)
        self._cam_table.setColumnWidth(1, 90)
        self._cam_table.setColumnWidth(2, 75)
        self._cam_table.setColumnWidth(3, 110)
        self._cam_table.setColumnWidth(4, 55)
        self._cam_table.setColumnWidth(5, 80)
        self._cam_table.setColumnWidth(6, 90)
        lay.addWidget(self._cam_table)
        return w

    def _load_cameras(self):
        from database.cameras import SENSORS_DATABASE
        self._cam_data = []
        for name, specs in sorted(SENSORS_DATABASE.items()):
            if name == 'default':
                continue
            brand = _get_cam_brand(name)
            self._cam_data.append((name, brand, specs))
        self._data_loaded['cameras'] = True
        self._apply_cam_filter()

    def _apply_cam_filter(self, _=None):
        if not self._data_loaded.get('cameras'):
            return
        search = self._cam_search.text().strip().lower()
        brand_idx = self._cam_brand.currentIndex()
        pixel_idx = self._cam_pixel.currentIndex()
        res_idx = self._cam_res.currentIndex()

        brand_names = [
            None, 'Altair', 'Atik', 'Canon', 'FLI', 'Fujifilm',
            'Mallincam', 'Moravian', 'Nikon', 'Olympus', 'Pentax',
            'Player One', 'QHY', 'SBIG', 'Scientific', 'Smart Scope',
            'Sony', 'SVBONY', 'Touptek', 'ZWO', 'Other'
        ]
        sel_brand = brand_names[brand_idx] if brand_idx < len(brand_names) else None

        filtered = []
        for name, brand, specs in self._cam_data:
            # Text search (name + brand)
            if search and search not in name.lower() and search not in brand.lower():
                continue
            # Brand filter
            if sel_brand and brand != sel_brand:
                continue
            # Pixel size filter
            px = specs.get('pixel_size', 0)
            if pixel_idx == 1 and px >= 2.5:
                continue
            if pixel_idx == 2 and (px < 2.5 or px >= 4):
                continue
            if pixel_idx == 3 and (px < 4 or px >= 6):
                continue
            if pixel_idx == 4 and px < 6:
                continue
            # Resolution filter
            mp = specs.get('width_px', 0) * specs.get('height_px', 0) / 1e6
            if res_idx == 1 and mp >= 4:
                continue
            if res_idx == 2 and (mp < 4 or mp >= 16):
                continue
            if res_idx == 3 and (mp < 16 or mp >= 40):
                continue
            if res_idx == 4 and mp < 40:
                continue

            filtered.append((name, brand, specs))

        self._cam_table.setSortingEnabled(False)
        self._cam_table.setRowCount(len(filtered))
        for row, (name, brand, specs) in enumerate(filtered):
            self._cam_table.setItem(row, 0, QTableWidgetItem(name))
            self._cam_table.setItem(row, 1, QTableWidgetItem(brand))
            px = specs.get('pixel_size', 0)
            self._cam_table.setItem(row, 2, self._num_item(px, f"{px:.2f}"))
            ww, hh = specs.get('width_px', 0), specs.get('height_px', 0)
            mp = ww * hh / 1e6
            res_item = QTableWidgetItem(f"{ww}x{hh} ({mp:.1f}MP)")
            res_item.setData(Qt.ItemDataRole.UserRole, ww * hh)
            self._cam_table.setItem(row, 3, res_item)
            gain = specs.get('gain', 0)
            self._cam_table.setItem(row, 4, self._num_item(gain, str(gain)))
            rn = specs.get('read_noise', 0)
            self._cam_table.setItem(row, 5, self._num_item(rn, f"{rn:.1f}"))
            fw = specs.get('full_well', 0)
            self._cam_table.setItem(row, 6, self._num_item(fw, f"{fw:,}"))
            qe = specs.get('quantum_efficiency', 0)
            self._cam_table.setItem(row, 7, self._num_item(qe * 100, f"{qe*100:.0f}%"))
        self._cam_table.setSortingEnabled(True)
        self._cam_count.setText(self._tr(
            f"{len(filtered):,} / {len(self._cam_data):,}",
            f"{len(filtered):,} / {len(self._cam_data):,}"
        ))

    # =========================================================================
    # TELESCOPES
    # =========================================================================

    def _create_telescopes_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        bar.addWidget(QLabel("🔍"))
        self._tel_search = QLineEdit()
        self._tel_search.setPlaceholderText(self._tr("Search telescopes...", "Chercher télescopes..."))
        self._tel_search.textChanged.connect(lambda: self._debounce(self._apply_tel_filter))
        bar.addWidget(self._tel_search, 1)

        bar.addWidget(QLabel(self._tr("Brand:", "Marque:")))
        tel_brands = [("All", "Toutes")]
        for b in sorted(_TEL_BRAND_RULES.keys()):
            tel_brands.append((b, b))
        tel_brands.append(("Other", "Autre"))
        self._tel_brand = self._make_combo(tel_brands, self._apply_tel_filter)
        bar.addWidget(self._tel_brand)

        bar.addWidget(QLabel(self._tr("Type:", "Type:")))
        self._tel_type = self._make_combo([
            ("All", "Tous"),
            ("Cassegrain/SCT/RC", "Cassegrain/SCT/RC"),
            ("Reflector", "Réflecteur"),
            ("Refractor", "Réfracteur"),
            ("Other", "Autre"),
        ], self._apply_tel_filter)
        bar.addWidget(self._tel_type)

        bar.addWidget(QLabel(self._tr("Aperture:", "Ouverture:")))
        self._tel_aper = self._make_combo([
            ("All", "Toutes"),
            ("< 80 mm", "< 80 mm"),
            ("80 - 150 mm", "80 - 150 mm"),
            ("150 - 300 mm", "150 - 300 mm"),
            ("> 300 mm", "> 300 mm"),
        ], self._apply_tel_filter)
        bar.addWidget(self._tel_aper)

        self._tel_count = QLabel("")
        self._tel_count.setStyleSheet("color: #7a8498; font-size: 9pt;")
        self._tel_count.setMinimumWidth(100)
        bar.addWidget(self._tel_count)

        bar_w = QWidget()
        bar_w.setLayout(bar)
        lay.addWidget(bar_w)

        cols = [
            self._tr("Name", "Nom"),
            self._tr("Brand", "Marque"),
            self._tr("Aperture (mm)", "Ouverture (mm)"),
            self._tr("Focal (mm)", "Focale (mm)"),
            self._tr("f/", "f/"),
        ]
        self._tel_table = self._create_table(cols)
        self._tel_table.setColumnWidth(0, 280)
        self._tel_table.setColumnWidth(1, 120)
        self._tel_table.setColumnWidth(2, 100)
        self._tel_table.setColumnWidth(3, 100)
        lay.addWidget(self._tel_table)
        return w

    def _load_telescopes(self):
        from database.telescopes import TELESCOPES_DATABASE
        self._tel_data = []
        for name, specs in sorted(TELESCOPES_DATABASE.items()):
            if name == 'default':
                continue
            brand = _get_tel_brand(name)
            tel_type = self._guess_tel_type(name, specs)
            self._tel_data.append((name, brand, tel_type, specs))
        self._data_loaded['telescopes'] = True
        self._apply_tel_filter()

    def _guess_tel_type(self, name, specs):
        nl = name.lower()
        fr = specs.get('f_number', 0)
        if any(k in nl for k in ('sct', 'cassegrain', 'rc ', ' rc', 'ritchey', 'rcos',
                'cdk', 'dall-kirkham', 'dk ', 'mak', 'maksutov', 'schmidt',
                'meade lx', 'nexstar', 'edgehd')):
            return 'cassegrain'
        if fr and fr >= 8 and specs.get('diameter_mm', 0) >= 200:
            return 'cassegrain'
        if any(k in nl for k in ('newton', 'newtonian', 'dobson', 'dob ',
                'gso ', 'reflector', 'truss', 'hnt', 'quattro')):
            return 'reflector'
        if fr and fr <= 5 and specs.get('diameter_mm', 0) >= 150:
            return 'reflector'
        if any(k in nl for k in ('apo', ' ed', 'ed ', 'edph', 'triplet', 'doublet',
                'refractor', 'fsq', 'tsa', 'toa', 'fc-', 'fc ',
                'wo ', 'stellarvue', 'tv-', 'tele vue',
                'borg', 'askar', 'sharpstar', 'redcat', 'esprit',
                'zenithstar', 'evolux', 'evostar')):
            return 'refractor'
        if specs.get('diameter_mm', 0) <= 130 and fr and fr >= 5:
            return 'refractor'
        return 'other'

    def _apply_tel_filter(self, _=None):
        if not self._data_loaded.get('telescopes'):
            return
        search = self._tel_search.text().strip().lower()
        brand_idx = self._tel_brand.currentIndex()
        type_idx = self._tel_type.currentIndex()
        aper_idx = self._tel_aper.currentIndex()

        # Build brand list matching combo order
        brand_keys = [None] + sorted(_TEL_BRAND_RULES.keys()) + ['Other']
        sel_brand = brand_keys[brand_idx] if brand_idx < len(brand_keys) else None

        type_map = {0: None, 1: 'cassegrain', 2: 'reflector', 3: 'refractor', 4: 'other'}
        sel_type = type_map.get(type_idx)

        filtered = []
        for name, brand, tel_type, specs in self._tel_data:
            if search and search not in name.lower() and search not in brand.lower():
                continue
            if sel_brand and brand != sel_brand:
                continue
            if sel_type and tel_type != sel_type:
                continue
            d = specs.get('diameter_mm', 0)
            if aper_idx == 1 and d >= 80:
                continue
            if aper_idx == 2 and (d < 80 or d >= 150):
                continue
            if aper_idx == 3 and (d < 150 or d >= 300):
                continue
            if aper_idx == 4 and d < 300:
                continue
            filtered.append((name, brand, specs))

        self._tel_table.setSortingEnabled(False)
        self._tel_table.setRowCount(len(filtered))
        for row, (name, brand, specs) in enumerate(filtered):
            self._tel_table.setItem(row, 0, QTableWidgetItem(name))
            self._tel_table.setItem(row, 1, QTableWidgetItem(brand))
            d = specs.get('diameter_mm', 0)
            self._tel_table.setItem(row, 2, self._num_item(d, f"{d:.0f}"))
            fl = specs.get('focal_length_mm', 0)
            self._tel_table.setItem(row, 3, self._num_item(fl, f"{fl:.0f}"))
            fr = specs.get('f_number', 0)
            self._tel_table.setItem(row, 4, self._num_item(fr, f"f/{fr:.1f}"))
        self._tel_table.setSortingEnabled(True)
        self._tel_count.setText(self._tr(
            f"{len(filtered):,} / {len(self._tel_data):,}",
            f"{len(filtered):,} / {len(self._tel_data):,}"
        ))

    # =========================================================================
    # FILTERS
    # =========================================================================

    def _create_filters_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        # Row 1: search + brand + type
        bar1 = QHBoxLayout()
        bar1.setSpacing(6)
        bar1.addWidget(QLabel("🔍"))
        self._flt_search = QLineEdit()
        self._flt_search.setPlaceholderText(self._tr("Search filters...", "Chercher filtres..."))
        self._flt_search.textChanged.connect(lambda: self._debounce(self._apply_flt_filter))
        bar1.addWidget(self._flt_search, 1)

        bar1.addWidget(QLabel(self._tr("Brand:", "Marque:")))
        flt_brand_items = [("All", "Toutes")]
        for b in _FLT_BRAND_NAMES:
            flt_brand_items.append((b, b))
        flt_brand_items.append(("Generic", "Générique"))
        self._flt_brand = self._make_combo(flt_brand_items, self._apply_flt_filter)
        bar1.addWidget(self._flt_brand)

        bar1.addWidget(QLabel(self._tr("Type:", "Type:")))
        self._flt_type = self._make_combo([
            ("All Types", "Tous les Types"),
            ("Broadband (LRGB)", "Large bande (LRGB)"),
            ("Dual Narrowband", "Double bande étroite"),
            ("Light Pollution", "Anti-pollution"),
            ("Narrowband", "Bande étroite"),
            ("Special", "Spécial"),
            ("UV/IR Cut", "Coupure UV/IR"),
        ], self._apply_flt_filter)
        bar1.addWidget(self._flt_type)

        bar1_w = QWidget()
        bar1_w.setLayout(bar1)
        lay.addWidget(bar1_w)

        # Row 2: camera type + passband color + bandwidth + count
        bar2 = QHBoxLayout()
        bar2.setSpacing(6)

        bar2.addWidget(QLabel(self._tr("Camera:", "Caméra:")))
        self._flt_cam = self._make_combo([
            ("All", "Toutes"),
            ("Both", "Les deux"),
            ("Color", "Couleur"),
            ("Mono", "Mono"),
        ], self._apply_flt_filter)
        bar2.addWidget(self._flt_cam)

        bar2.addWidget(QLabel(self._tr("Passband:", "Bande passante:")))
        self._flt_color = self._make_combo([
            ("All", "Toutes"),
            ("UV (< 400 nm)", "UV (< 400 nm)"),
            ("Blue (400-500)", "Bleu (400-500)"),
            ("Green (500-570)", "Vert (500-570)"),
            ("Yellow (570-600)", "Jaune (570-600)"),
            ("Red (600-700)", "Rouge (600-700)"),
            ("Near-IR (> 700)", "Proche-IR (> 700)"),
            ("Multi/White", "Multi/Blanc"),
        ], self._apply_flt_filter)
        bar2.addWidget(self._flt_color)

        bar2.addWidget(QLabel(self._tr("Bandwidth:", "Bande:")))
        self._flt_bw = self._make_combo([
            ("All", "Toutes"),
            ("< 5 nm (ultra NB)", "< 5 nm (ultra NB)"),
            ("5 - 12 nm (NB)", "5 - 12 nm (NB)"),
            ("12 - 50 nm", "12 - 50 nm"),
            ("> 50 nm (broadband)", "> 50 nm (large bande)"),
        ], self._apply_flt_filter)
        bar2.addWidget(self._flt_bw)

        bar2.addStretch()
        self._flt_count = QLabel("")
        self._flt_count.setStyleSheet("color: #7a8498; font-size: 9pt;")
        self._flt_count.setMinimumWidth(100)
        bar2.addWidget(self._flt_count)

        bar2_w = QWidget()
        bar2_w.setLayout(bar2)
        lay.addWidget(bar2_w)

        # Table with extra columns
        cols = [
            self._tr("Name", "Nom"),
            self._tr("Brand", "Marque"),
            self._tr("Type", "Type"),
            self._tr("Camera", "Caméra"),
            self._tr("Passband", "Couleur"),
            self._tr("Center (nm)", "Centre (nm)"),
            self._tr("Bandwidth (nm)", "Bande (nm)"),
            self._tr("Description", "Description"),
        ]
        self._flt_table = self._create_table(cols)
        self._flt_table.setColumnWidth(0, 210)
        self._flt_table.setColumnWidth(1, 100)
        self._flt_table.setColumnWidth(2, 120)
        self._flt_table.setColumnWidth(3, 60)
        self._flt_table.setColumnWidth(4, 80)
        self._flt_table.setColumnWidth(5, 80)
        self._flt_table.setColumnWidth(6, 80)
        lay.addWidget(self._flt_table)
        return w

    def _load_filters(self):
        from database.filters import FILTERS_DATABASE, FILTER_TYPES
        self._flt_data = []
        self._filter_types = FILTER_TYPES
        for name, specs in sorted(FILTERS_DATABASE.items()):
            brand = _get_flt_brand(name)
            ftype = specs.get('type', 'special')
            cam = _get_flt_camera(ftype)
            passband = _get_flt_passband(
                specs.get('center_nm', 0), specs.get('bandwidth_nm', 0))
            self._flt_data.append((name, brand, cam, passband, specs))
        self._data_loaded['filters'] = True
        self._apply_flt_filter()

    def _apply_flt_filter(self, _=None):
        if not self._data_loaded.get('filters'):
            return
        search = self._flt_search.text().strip().lower()
        brand_idx = self._flt_brand.currentIndex()
        type_idx = self._flt_type.currentIndex()
        cam_idx = self._flt_cam.currentIndex()
        color_idx = self._flt_color.currentIndex()
        bw_idx = self._flt_bw.currentIndex()

        # Brand: 0=All, 1..N=specific brands, N+1=Generic
        brand_keys = [None] + _FLT_BRAND_NAMES + ['Generic']
        sel_brand = brand_keys[brand_idx] if brand_idx < len(brand_keys) else None

        type_map = {
            0: None, 1: 'broadband', 2: 'dual_narrowband',
            3: 'light_pollution', 4: 'narrowband', 5: 'special', 6: 'uv_ir_cut'
        }
        sel_type = type_map.get(type_idx)

        cam_map = {0: None, 1: 'Both', 2: 'Color', 3: 'Mono'}
        sel_cam = cam_map.get(cam_idx)

        color_map = {
            0: None, 1: 'UV', 2: 'Blue', 3: 'Green',
            4: 'Yellow', 5: 'Red', 6: 'Near-IR', 7: 'Multi/White'
        }
        sel_color = color_map.get(color_idx)

        filtered = []
        for name, brand, cam, passband, specs in self._flt_data:
            if search:
                desc = specs.get(self.lang, specs.get('en', ''))
                if (search not in name.lower()
                        and search not in desc.lower()
                        and search not in brand.lower()):
                    continue
            ftype = specs.get('type', 'special')
            if sel_type and ftype != sel_type:
                continue
            if sel_brand and brand != sel_brand:
                continue
            if sel_cam and cam != sel_cam:
                continue
            if sel_color and passband != sel_color:
                continue
            bw = specs.get('bandwidth_nm', 0)
            if bw_idx == 1 and (bw >= 5 or bw == 0):
                continue
            if bw_idx == 2 and (bw < 5 or bw > 12):
                continue
            if bw_idx == 3 and (bw < 12 or bw > 50):
                continue
            if bw_idx == 4 and bw <= 50 and bw != 0:
                continue
            filtered.append((name, brand, cam, passband, specs))

        self._flt_table.setSortingEnabled(False)
        self._flt_table.setRowCount(len(filtered))
        for row, (name, brand, cam, passband, specs) in enumerate(filtered):
            self._flt_table.setItem(row, 0, QTableWidgetItem(prettify_filter_name(name)))
            self._flt_table.setItem(row, 1, QTableWidgetItem(brand))
            ftype = specs.get('type', 'special')
            type_info = self._filter_types.get(ftype, {})
            type_label = type_info.get(self.lang, type_info.get('en', ftype))
            self._flt_table.setItem(row, 2, QTableWidgetItem(type_label))
            cam_label = self._tr(cam, {'Mono': 'Mono', 'Color': 'Couleur', 'Both': 'Les deux'}.get(cam, cam))
            self._flt_table.setItem(row, 3, QTableWidgetItem(cam_label))
            self._flt_table.setItem(row, 4, QTableWidgetItem(passband))
            center = specs.get('center_nm', 0)
            self._flt_table.setItem(row, 5,
                self._num_item(center, f"{center:.1f}" if center else "-"))
            bw = specs.get('bandwidth_nm', 0)
            self._flt_table.setItem(row, 6,
                self._num_item(bw, f"{bw:.0f}" if bw else "-"))
            desc = specs.get(self.lang, specs.get('en', ''))
            self._flt_table.setItem(row, 7, QTableWidgetItem(prettify_filter_name(desc)))
        self._flt_table.setSortingEnabled(True)
        self._flt_count.setText(self._tr(
            f"{len(filtered):,} / {len(self._flt_data):,}",
            f"{len(filtered):,} / {len(self._flt_data):,}"
        ))

    # =========================================================================
    # TARGETS
    # =========================================================================

    def _create_targets_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        bar.addWidget(QLabel("🔍"))
        self._tgt_search = QLineEdit()
        self._tgt_search.setPlaceholderText(self._tr("Search targets...", "Chercher cibles..."))
        self._tgt_search.textChanged.connect(lambda: self._debounce(self._apply_tgt_filter))
        bar.addWidget(self._tgt_search, 1)

        bar.addWidget(QLabel(self._tr("Catalog:", "Catalogue:")))
        self._tgt_cat = self._make_combo([
            ("All Catalogs", "Tous les Catalogues"),
            ("Arp", "Arp"),
            ("Barnard (B)", "Barnard (B)"),
            ("Caldwell (C)", "Caldwell (C)"),
            ("IC", "IC"),
            ("Messier (M)", "Messier (M)"),
            ("NGC", "NGC"),
            ("Sharpless (Sh2)", "Sharpless (Sh2)"),
            ("Solar System", "Système Solaire"),
            ("Other", "Autre"),
        ], self._apply_tgt_filter)
        bar.addWidget(self._tgt_cat)

        bar.addWidget(QLabel(self._tr("Type:", "Type:")))
        self._tgt_type = self._make_combo([
            ("All Types", "Tous les Types"),
            ("Cluster", "Amas"),
            ("Galaxy", "Galaxie"),
            ("Nebula", "Nébuleuse"),
            ("Planet/Moon", "Planète/Lune"),
            ("Planetary Nebula", "Néb. Planétaire"),
        ], self._apply_tgt_filter)
        bar.addWidget(self._tgt_type)

        self._tgt_count = QLabel("")
        self._tgt_count.setStyleSheet("color: #7a8498; font-size: 9pt;")
        self._tgt_count.setMinimumWidth(140)
        bar.addWidget(self._tgt_count)

        bar_w = QWidget()
        bar_w.setLayout(bar)
        lay.addWidget(bar_w)

        cols = [
            self._tr("ID", "ID"),
            self._tr("Description", "Description"),
            self._tr("Catalog", "Catalogue"),
            self._tr("Type", "Type"),
        ]
        self._tgt_table = self._create_table(cols)
        self._tgt_table.setColumnWidth(0, 160)
        self._tgt_table.setColumnWidth(1, 350)
        self._tgt_table.setColumnWidth(2, 100)
        lay.addWidget(self._tgt_table)
        return w

    def _load_targets(self):
        from database.targets import (
            MESSIER_DATABASE, EXTENDED_ASTRONOMICAL_DATABASE,
            ARP_DATABASE, SOLAR_SYSTEM_OBJECTS
        )
        self._tgt_data = []
        for key, desc in sorted(MESSIER_DATABASE.items()):
            obj_type = self._guess_obj_type(desc)
            self._tgt_data.append((key, desc, 'Messier', obj_type))
        for key, desc in sorted(EXTENDED_ASTRONOMICAL_DATABASE.items()):
            catalog = self._classify_catalog(key)
            obj_type = self._guess_obj_type(desc)
            self._tgt_data.append((key, desc, catalog, obj_type))
        for key, desc in sorted(ARP_DATABASE.items()):
            self._tgt_data.append((key, desc, 'Arp', 'Galaxy'))
        # SOLAR_SYSTEM_OBJECTS is a set of strings, not a dict
        for name in sorted(SOLAR_SYSTEM_OBJECTS):
            self._tgt_data.append((name, name, 'Solar System', 'Planet/Moon'))
        self._data_loaded['targets'] = True
        self._apply_tgt_filter()

    def _classify_catalog(self, key):
        k = key.upper()
        if k.startswith('NGC'):
            return 'NGC'
        elif k.startswith('IC'):
            return 'IC'
        elif k.startswith('SH2') or k.startswith('SH ') or k.startswith('SHARPLESS'):
            return 'Sharpless'
        elif k.startswith('B ') or k.startswith('BARNARD'):
            return 'Barnard'
        elif k.startswith('CALDWELL') or (k.startswith('C ') and k[2:].strip().isdigit()):
            return 'Caldwell'
        elif k.startswith('ARP'):
            return 'Arp'
        return 'Other'

    def _guess_obj_type(self, desc):
        dl = desc.lower()
        if any(w in dl for w in ('galaxy', 'galax', 'spiral', 'elliptical', 'lenticular', 'barred', 'irregular gal')):
            return 'Galaxy'
        if 'planetary nebula' in dl or 'planétaire' in dl:
            return 'Planetary Nebula'
        if any(w in dl for w in ('nebula', 'nébuleuse', 'emission', 'reflection', 'dark ', 'hii', 'supernova remnant')):
            return 'Nebula'
        if any(w in dl for w in ('cluster', 'amas', 'globular', 'open cluster', 'star cloud')):
            return 'Cluster'
        if any(w in dl for w in ('planet', 'moon', 'comet', 'asteroid', 'sun', 'mercury', 'venus', 'mars', 'jupiter', 'saturn')):
            return 'Planet/Moon'
        return 'Other'

    def _apply_tgt_filter(self, _=None):
        if not self._data_loaded.get('targets'):
            return
        search = self._tgt_search.text().strip().lower()
        cat_idx = self._tgt_cat.currentIndex()
        type_idx = self._tgt_type.currentIndex()

        cat_names = [
            None, 'Arp', 'Barnard', 'Caldwell', 'IC', 'Messier',
            'NGC', 'Sharpless', 'Solar System', 'Other'
        ]
        sel_cat = cat_names[cat_idx] if cat_idx < len(cat_names) else None

        type_names = [None, 'Cluster', 'Galaxy', 'Nebula', 'Planet/Moon', 'Planetary Nebula']
        sel_type = type_names[type_idx] if type_idx < len(type_names) else None

        filtered = []
        for key, desc, catalog, obj_type in self._tgt_data:
            if search and search not in key.lower() and search not in desc.lower():
                continue
            if sel_cat and catalog != sel_cat:
                continue
            if sel_type and obj_type != sel_type:
                continue
            filtered.append((key, desc, catalog, obj_type))

        display_limit = 5000
        show_all = len(filtered) <= display_limit
        display = filtered if show_all else filtered[:display_limit]

        self._tgt_table.setSortingEnabled(False)
        self._tgt_table.setRowCount(len(display))
        for row, (key, desc, catalog, obj_type) in enumerate(display):
            self._tgt_table.setItem(row, 0, QTableWidgetItem(key))
            self._tgt_table.setItem(row, 1, QTableWidgetItem(desc))
            self._tgt_table.setItem(row, 2, QTableWidgetItem(catalog))
            self._tgt_table.setItem(row, 3, QTableWidgetItem(obj_type))
        self._tgt_table.setSortingEnabled(True)

        if show_all:
            self._tgt_count.setText(self._tr(
                f"{len(filtered):,} / {len(self._tgt_data):,}",
                f"{len(filtered):,} / {len(self._tgt_data):,}"
            ))
        else:
            self._tgt_count.setText(self._tr(
                f"{display_limit:,} / {len(filtered):,} (filter to see more)",
                f"{display_limit:,} / {len(filtered):,} (filtrez pour voir +)"
            ))

    # =========================================================================
    # Lazy loading
    # =========================================================================

    def _on_subtab_changed(self, index):
        self._ensure_data_loaded(index)

    def _ensure_data_loaded(self, index):
        loaders = {
            0: ('cameras', self._load_cameras),
            1: ('telescopes', self._load_telescopes),
            2: ('filters', self._load_filters),
            3: ('targets', self._load_targets),
        }
        key, loader = loaders.get(index, (None, None))
        if key and not self._data_loaded.get(key):
            loader()
