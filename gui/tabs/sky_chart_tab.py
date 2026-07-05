#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - SKY CHART TAB
================================================================================
Interactive celestial map showing all observed targets on an Aitoff projection.
Targets are colour-coded by object type, sized by integration time, with
optional Milky Way band, coordinate grid, and hover tooltips.
================================================================================
"""

import json
import logging
import math
import numpy as np
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QCheckBox, QComboBox, QFileDialog,
    QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

# NOTE: matplotlib is imported LAZILY inside the methods that actually build
# the canvas / draw the chart (see _init_ui, _draw_milky_way, _draw_labels),
# mirroring calendar_tab.py. This keeps `import gui.tabs.sky_chart_tab` cheap
# so importing (or, later, deferring the construction of) this tab does not
# pull the heavy matplotlib stack at application startup.
# TODO(perf, finding #15b): construct the 18 main-window tabs lazily on first
# activation so this deferred import is only paid when the Sky Chart tab is
# opened. Kept eager for now: several tabs subscribe to global signals and are
# referenced directly by the main window (e.g. history/analysis tabs).

from core.signals import signals
from core.config import get_config
from core.database import get_db
from core.i18n import get_lang
from gui.theme import COLORS, FILTER_COLORS

logger = logging.getLogger(__name__)


# ============================================================================
# OBJECT TYPE COLOUR MAP (muted cosmic palette)
# ============================================================================

_OBJECT_TYPE_COLORS = {
    # Galaxies
    'G':    '#b89898',
    'GiG':  '#b89898',
    'GiP':  '#b89898',
    'AGN':  '#b89898',
    'SyG':  '#b89898',
    'Sy1':  '#b89898',
    'Sy2':  '#b89898',
    'BiC':  '#b89898',
    'EmG':  '#b89898',
    'SBG':  '#b89898',
    'LSB':  '#b89898',
    'HiI':  '#b89898',
    'GiC':  '#b89898',
    'IG':   '#b89898',
    'PaG':  '#b89898',
    'LeI':  '#b89898',
    'LeG':  '#b89898',
    'BLL':  '#b89898',
    'QSO':  '#b89898',
    'LIN':  '#b89898',
    'rG':   '#b89898',
    # Emission / HII / Star-forming nebulae
    'GNe':  '#90b098',
    'HII':  '#90b098',
    'ISM':  '#90b098',
    'SFR':  '#90b098',
    'RfN':  '#90a0b8',
    # Planetary nebulae
    'PN':   '#a8a0c0',
    # Reflection nebulae
    'RNe':  '#90a0b8',
    # Dark nebulae
    'DNe':  '#8a8a90',
    # Supernova remnants
    'SNR':  '#c0a0ac',
    # Open / stellar clusters
    'OpC':  '#b8b090',
    'Cl*':  '#b8b090',
    'As*':  '#b8b090',
    'MGr':  '#b8b090',
    # Globular clusters
    'GlC':  '#c0b098',
    # Galaxy clusters
    'ClG':  '#b8a0a0',
    'CGr':  '#b8a0a0',
    'SCG':  '#b8a0a0',
    # Stars / stellar objects
    '*':    '#a0a0a8',
    '**':   '#a0a0a8',
    'V*':   '#a0a0a8',
    'Ce*':  '#a0a0a8',
    'RR*':  '#a0a0a8',
    'WR*':  '#a0a0a8',
    'No*':  '#a0a0a8',
    'C*':   '#a0a0a8',
    'Be*':  '#a0a0a8',
    'X':    '#a0a0a8',
}

# Fallback colour for unknown types
_DEFAULT_OBJECT_COLOR = '#7a8498'

# Human-readable category names (for legend) indexed by representative colour
_CATEGORY_LABELS = {
    '#b89898': ('Galaxy', 'Galaxie'),
    '#90b098': ('Emission Nebula', 'Nebuleuse en emission'),
    '#a8a0c0': ('Planetary Nebula', 'Nebuleuse planetaire'),
    '#90a0b8': ('Reflection Nebula', 'Nebuleuse par reflexion'),
    '#8a8a90': ('Dark Nebula', 'Nebuleuse obscure'),
    '#c0a0ac': ('Supernova Remnant', 'Reste de supernova'),
    '#b8b090': ('Open Cluster', 'Amas ouvert'),
    '#c0b098': ('Globular Cluster', 'Amas globulaire'),
    '#b8a0a0': ('Galaxy Cluster', 'Amas de galaxies'),
    '#a0a0a8': ('Star', 'Etoile'),
    '#7a8498': ('Unknown', 'Inconnu'),
}


def _get_object_color(obj_type: str) -> str:
    """Return the muted colour hex for a SIMBAD object type code."""
    if not obj_type:
        return _DEFAULT_OBJECT_COLOR
    # Direct lookup
    c = _OBJECT_TYPE_COLORS.get(obj_type)
    if c:
        return c
    # Try first token (e.g. 'G' from 'GiP')
    token = obj_type.split('/')[0].strip() if '/' in obj_type else obj_type.strip()
    c = _OBJECT_TYPE_COLORS.get(token)
    if c:
        return c
    # Substring heuristics
    lo = obj_type.lower()
    if 'galax' in lo or lo.startswith('g'):
        return '#b89898'
    if 'neb' in lo or 'hii' in lo:
        return '#90b098'
    if 'cluster' in lo or 'amas' in lo:
        return '#b8b090'
    return _DEFAULT_OBJECT_COLOR


def _integration_time_label(seconds: float, lang: str) -> str:
    """Format integration time in a human-readable string."""
    if seconds <= 0:
        return "0 s"
    if seconds < 60:
        return f"{seconds:.0f} s"
    if seconds < 3600:
        m = seconds / 60.0
        return f"{m:.1f} min"
    h = seconds / 3600.0
    if lang == 'fr':
        return f"{h:.1f} h"
    return f"{h:.1f} h"


def _ra_dec_label(ra_h: float, dec_d: float) -> str:
    """Format RA (hours) and Dec (degrees) nicely."""
    ra_hh = int(ra_h)
    ra_mm = int((ra_h - ra_hh) * 60)
    ra_ss = ((ra_h - ra_hh) * 60 - ra_mm) * 60
    dec_sign = '+' if dec_d >= 0 else '-'
    dec_abs = abs(dec_d)
    dec_dd = int(dec_abs)
    dec_mm = int((dec_abs - dec_dd) * 60)
    dec_ss = ((dec_abs - dec_dd) * 60 - dec_mm) * 60
    return (f"RA {ra_hh:02d}h{ra_mm:02d}m{ra_ss:04.1f}s  "
            f"Dec {dec_sign}{dec_dd:02d}\u00b0{dec_mm:02d}'{dec_ss:04.1f}\"")


# ============================================================================
# MILKY WAY BAND (sinusoidal approximation of the galactic plane)
# ============================================================================

def _galactic_plane_points(n: int = 360, half_width_deg: float = 12.0):
    """
    Return arrays (ra_rad, dec_upper, dec_lower) for a simple sinusoidal
    approximation of the Milky Way band in equatorial coordinates.

    The galactic plane can be roughly modelled as:
        Dec ~ 62.87 * sin(RA_deg - 282.25) (degrees)
    with a +-half_width_deg band.  This is a crude but visually convincing
    approximation that avoids requiring astropy's coordinate transforms at
    import time.
    """
    ra_deg = np.linspace(0, 360, n, endpoint=False)
    # Simple sinusoidal model of the galactic plane in equatorial coords
    # The galactic north pole is at (RA=192.85, Dec=27.13); the plane
    # crosses the celestial equator near RA~282 deg and RA~102 deg.
    dec_center = 62.87 * np.sin(np.radians(ra_deg - 282.25))
    dec_upper = np.clip(dec_center + half_width_deg, -90, 90)
    dec_lower = np.clip(dec_center - half_width_deg, -90, 90)

    # Convert to Aitoff radians: RA hours -> shift so 12h is at centre
    ra_rad = (ra_deg - 180.0) * np.pi / 180.0
    dec_upper_rad = dec_upper * np.pi / 180.0
    dec_lower_rad = dec_lower * np.pi / 180.0
    return ra_rad, dec_upper_rad, dec_lower_rad


# ============================================================================
# SKY CHART TAB
# ============================================================================

class SkyChartTab(QWidget):
    """Interactive celestial sky chart tab using Aitoff projection."""

    # Emitted when user clicks a target: (name, ra_hours, dec_degrees)
    target_clicked = pyqtSignal(str, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self.lang = get_lang()

        # Internal data cache
        self._targets = []          # list of dicts from database
        self._scatter = None        # matplotlib PathCollection
        self._annotations = []      # text annotations for labels
        self._tooltip_annot = None  # hover tooltip annotation
        self._milky_way_patches = []
        self._hover_index = None

        self._init_ui()
        self._connect_signals()

        # Deferred first load so the widget is fully laid out
        QTimer.singleShot(200, self._load_and_plot)

    # ── i18n helper ──────────────────────────────────────────────────────
    def _tr(self, en: str, fr: str) -> str:
        return fr if self.lang == 'fr' else en

    # ====================================================================
    # UI CONSTRUCTION
    # ====================================================================

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Controls bar ─────────────────────────────────────────────────
        controls_group = QGroupBox(self._tr(
            "Chart Controls", "Controles de la carte"))
        controls_group.setToolTip(self._tr(
            "Options for displaying the sky chart",
            "Options d'affichage de la carte celeste"))
        ctrl_layout = QHBoxLayout(controls_group)
        ctrl_layout.setSpacing(10)

        # Grid checkbox
        self.chk_grid = QCheckBox(self._tr("Grid", "Grille"))
        self.chk_grid.setChecked(True)
        self.chk_grid.setToolTip(self._tr(
            "Show or hide the RA/Dec coordinate grid",
            "Afficher ou masquer la grille de coordonnees RA/Dec"))
        self.chk_grid.stateChanged.connect(self._on_toggle_grid)
        ctrl_layout.addWidget(self.chk_grid)

        # Milky Way checkbox
        self.chk_milkyway = QCheckBox(self._tr("Milky Way", "Voie lactee"))
        self.chk_milkyway.setChecked(True)
        self.chk_milkyway.setToolTip(self._tr(
            "Show or hide the approximate Milky Way band",
            "Afficher ou masquer la bande approximative de la Voie lactee"))
        self.chk_milkyway.stateChanged.connect(self._on_toggle_milkyway)
        ctrl_layout.addWidget(self.chk_milkyway)

        # Labels checkbox
        self.chk_labels = QCheckBox(self._tr("Labels", "Etiquettes"))
        self.chk_labels.setChecked(False)
        self.chk_labels.setToolTip(self._tr(
            "Show or hide target name labels on the chart",
            "Afficher ou masquer les noms des cibles sur la carte"))
        self.chk_labels.stateChanged.connect(self._on_toggle_labels)
        ctrl_layout.addWidget(self.chk_labels)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setFrameShadow(QFrame.Shadow.Sunken)
        ctrl_layout.addWidget(sep1)

        # Colour-by combo
        lbl_color = QLabel(self._tr("Colour by:", "Couleur par :"))
        lbl_color.setToolTip(self._tr(
            "Choose how target dots are coloured",
            "Choisir le mode de coloration des points"))
        ctrl_layout.addWidget(lbl_color)

        self.cmb_colorby = QComboBox()
        self.cmb_colorby.addItem(self._tr("Object Type", "Type d'objet"), "type")
        self.cmb_colorby.addItem(self._tr("Filter", "Filtre"), "filter")
        self.cmb_colorby.addItem(
            self._tr("Integration Time", "Temps d'integration"), "integration")
        self.cmb_colorby.setToolTip(self._tr(
            "Object Type: colour by SIMBAD type\n"
            "Filter: colour by most-used imaging filter\n"
            "Integration Time: colour gradient by total exposure",
            "Type d'objet : couleur par type SIMBAD\n"
            "Filtre : couleur par filtre d'imagerie principal\n"
            "Temps d'integration : gradient par exposition totale"))
        self.cmb_colorby.currentIndexChanged.connect(self._on_colorby_changed)
        ctrl_layout.addWidget(self.cmb_colorby)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        ctrl_layout.addWidget(sep2)

        # Projection combo
        lbl_proj = QLabel(self._tr("Projection:", "Projection :"))
        lbl_proj.setToolTip(self._tr(
            "Choose the map projection type",
            "Choisir le type de projection cartographique"))
        ctrl_layout.addWidget(lbl_proj)

        self.cmb_projection = QComboBox()
        self.cmb_projection.addItem("Aitoff", "aitoff")
        self.cmb_projection.addItem("Mollweide", "mollweide")
        self.cmb_projection.setToolTip(self._tr(
            "Aitoff: standard equal-area projection\n"
            "Mollweide: elliptical equal-area projection",
            "Aitoff : projection standard a aires egales\n"
            "Mollweide : projection elliptique a aires egales"))
        self.cmb_projection.currentIndexChanged.connect(self._on_projection_changed)
        ctrl_layout.addWidget(self.cmb_projection)

        ctrl_layout.addStretch()

        # Refresh button
        self.btn_refresh = QPushButton(self._tr("Refresh", "Actualiser"))
        self.btn_refresh.setToolTip(self._tr(
            "Reload target data from the database and redraw the chart",
            "Recharger les donnees des cibles depuis la base et redessiner la carte"))
        self.btn_refresh.setProperty("accent", True)
        self.btn_refresh.clicked.connect(self._load_and_plot)
        ctrl_layout.addWidget(self.btn_refresh)

        # Export PNG button
        self.btn_export = QPushButton(self._tr("Export PNG", "Exporter PNG"))
        self.btn_export.setToolTip(self._tr(
            "Save the sky chart as a high-resolution PNG image",
            "Enregistrer la carte celeste en image PNG haute resolution"))
        self.btn_export.clicked.connect(self._export_png)
        ctrl_layout.addWidget(self.btn_export)

        layout.addWidget(controls_group)

        # ── Status bar ───────────────────────────────────────────────────
        self.lbl_status = QLabel("")
        self.lbl_status.setToolTip(self._tr(
            "Number of targets displayed on the chart",
            "Nombre de cibles affichees sur la carte"))
        self.lbl_status.setStyleSheet(
            f"color: {COLORS['text_secondary']}; padding: 2px 4px;")
        layout.addWidget(self.lbl_status)

        # ── Matplotlib canvas ────────────────────────────────────────────
        # Lazy import: pull matplotlib only when the tab is actually built.
        import matplotlib
        matplotlib.use('QtAgg')
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_qtagg import (
            FigureCanvasQTAgg, NavigationToolbar2QT)

        self.figure = Figure(facecolor=COLORS['bg_darkest'], dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.setToolTip(self._tr(
            "Sky chart — hover to see target info, click to select",
            "Carte celeste — survolez pour voir les infos, cliquez pour selectionner"))

        # Navigation toolbar (zoom / pan / home)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.setToolTip(self._tr(
            "Zoom, pan and home controls for the chart",
            "Controles de zoom, deplacement et reinitialisation de la carte"))
        # Style the toolbar for the dark theme
        self.toolbar.setStyleSheet(
            f"background-color: {COLORS['bg_medium']}; "
            f"border: 1px solid {COLORS['border']}; "
            f"border-radius: 4px; padding: 2px;")

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, 1)

        # Connect matplotlib mouse events
        self.canvas.mpl_connect('motion_notify_event', self._on_mouse_move)
        self.canvas.mpl_connect('button_press_event', self._on_mouse_click)

    # ====================================================================
    # SIGNAL CONNECTIONS
    # ====================================================================

    def _connect_signals(self):
        """Connect global signal bus events."""
        signals.targets_refreshed.connect(self._load_and_plot)
        signals.target_updated.connect(lambda *_: self._load_and_plot())
        signals.observation_added.connect(lambda *_: self._load_and_plot())

    # ====================================================================
    # DATA LOADING
    # ====================================================================

    def _load_targets(self):
        """Fetch targets with valid RA/Dec from the database."""
        db = get_db()
        targets = []
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT t.id, t.name, t.canonical_name, t.ra, t.dec,
                           t.object_type, t.total_exposure_time, t.total_frames,
                           t.simbad_data
                    FROM targets t
                    WHERE t.ra IS NOT NULL AND t.dec IS NOT NULL
                    ORDER BY t.name
                """)
                rows = cursor.fetchall()
                for row in rows:
                    ra_val = row['ra']
                    dec_val = row['dec']
                    if ra_val is None or dec_val is None:
                        continue
                    # DB stores RA in degrees (0-360); convert to hours (0-24)
                    if ra_val >= 24.0:
                        ra_val = ra_val / 15.0
                    # Validate RA [0, 24) and Dec [-90, 90]
                    if not (0.0 <= ra_val < 24.0) or not (-90.0 <= dec_val <= 90.0):
                        continue

                    obj_type = row['object_type'] or ''
                    simbad_raw = row['simbad_data']
                    simbad = {}
                    if simbad_raw:
                        try:
                            simbad = json.loads(simbad_raw)
                        except (json.JSONDecodeError, TypeError):
                            pass
                    # Prefer SIMBAD otype over stored object_type
                    if not obj_type and simbad.get('otype'):
                        obj_type = simbad['otype']

                    # Fetch dominant filter for this target
                    dominant_filter = self._get_dominant_filter(
                        conn, row['id'])

                    display_name = row['canonical_name'] or row['name']
                    targets.append({
                        'id': row['id'],
                        'name': row['name'],
                        'display_name': display_name,
                        'ra': ra_val,
                        'dec': dec_val,
                        'object_type': obj_type,
                        'total_exposure': row['total_exposure_time'] or 0.0,
                        'total_frames': row['total_frames'] or 0,
                        'dominant_filter': dominant_filter,
                    })
        except Exception as exc:
            logger.error("Failed to load targets for sky chart: %s", exc)

        self._targets = targets
        count = len(targets)
        self.lbl_status.setText(self._tr(
            f"{count} target{'s' if count != 1 else ''} plotted",
            f"{count} cible{'s' if count != 1 else ''} affichee{'s' if count != 1 else ''}"))
        logger.info("Sky chart: loaded %d targets with valid coordinates.", count)

    @staticmethod
    def _get_dominant_filter(conn, target_id: int) -> str:
        """Return the filter with the most frames for a given target."""
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT filter, SUM(frame_count) AS total
                FROM observations
                WHERE target_id = ? AND filter IS NOT NULL AND filter != ''
                GROUP BY filter
                ORDER BY total DESC
                LIMIT 1
            """, (target_id,))
            row = cursor.fetchone()
            if row:
                return row['filter']
        except Exception:
            pass
        return ''

    # ====================================================================
    # COORDINATE TRANSFORMS
    # ====================================================================

    @staticmethod
    def _ra_dec_to_aitoff(ra_hours: float, dec_deg: float):
        """
        Convert RA (hours) and Dec (degrees) to Aitoff projection radians.

        Matplotlib's Aitoff projection expects:
          - longitude in [-pi, pi]  (RA shifted so 12h = 0)
          - latitude  in [-pi/2, pi/2]

        Convention: RA increases to the left (east), matching standard
        astronomical sky charts.
        """
        # RA hours -> degrees -> shift so 12h maps to 0
        ra_deg = ra_hours * 15.0       # 0..360
        lon_deg = ra_deg - 180.0       # -180..180
        # Flip sign so RA increases leftward on the chart
        lon_rad = -lon_deg * math.pi / 180.0
        lat_rad = dec_deg * math.pi / 180.0
        return lon_rad, lat_rad

    @staticmethod
    def _ra_dec_to_aitoff_array(ra_arr, dec_arr):
        """Vectorised version for numpy arrays."""
        lon_deg = ra_arr * 15.0 - 180.0
        lon_rad = -lon_deg * np.pi / 180.0
        lat_rad = dec_arr * np.pi / 180.0
        return lon_rad, lat_rad

    # ====================================================================
    # PLOTTING
    # ====================================================================

    def _load_and_plot(self):
        """Reload data from DB and redraw the chart."""
        self._load_targets()
        self._draw_chart()

    def _draw_chart(self):
        """Full redraw of the sky chart."""
        self.figure.clear()
        self._annotations.clear()
        self._milky_way_patches.clear()
        self._scatter = None
        self._tooltip_annot = None
        self._hover_index = None

        projection = self.cmb_projection.currentData() or 'aitoff'
        ax = self.figure.add_subplot(111, projection=projection)

        # Dark background
        ax.set_facecolor(COLORS['bg_darkest'])
        self.figure.patch.set_facecolor(COLORS['bg_darkest'])

        # Grid
        ax.grid(self.chk_grid.isChecked(),
                color=COLORS['border'], alpha=0.35, linewidth=0.5,
                linestyle='--')

        # Axis tick styling
        ax.tick_params(colors=COLORS['text_secondary'], labelsize=7)
        for spine in ax.spines.values():
            spine.set_edgecolor(COLORS['border'])
            spine.set_linewidth(0.6)

        # RA tick labels (show hours) — Aitoff x-axis goes from -pi to pi
        ra_ticks_hours = [0, 2, 4, 6, 8, 10, 14, 16, 18, 20, 22]
        ra_tick_labels = [f"{h}h" for h in ra_ticks_hours]
        # Convert hours to the chart x-coordinate
        ra_tick_x = []
        for h in ra_ticks_hours:
            lon_deg = h * 15.0 - 180.0
            ra_tick_x.append(-lon_deg * np.pi / 180.0)
        try:
            ax.set_xticks(ra_tick_x)
            ax.set_xticklabels(ra_tick_labels, fontsize=7,
                               color=COLORS['text_secondary'])
        except Exception:
            pass  # Some projections don't support set_xticks cleanly

        # ── Milky Way band ───────────────────────────────────────────────
        self._draw_milky_way(ax)

        # ── Target scatter ───────────────────────────────────────────────
        if self._targets:
            self._draw_targets(ax)

        # ── Title ────────────────────────────────────────────────────────
        title_text = self._tr("Celestial Sky Chart", "Carte du Ciel")
        ax.set_title(title_text, fontsize=13, fontweight='bold',
                     color=COLORS['accent_cyan'], pad=12)

        # ── Tooltip annotation (invisible until hover) ───────────────────
        self._tooltip_annot = ax.annotate(
            "", xy=(0, 0), xytext=(15, 15),
            textcoords="offset pixels",
            fontsize=8,
            color=COLORS['text_primary'],
            bbox=dict(boxstyle="round,pad=0.4",
                      facecolor=COLORS['bg_light'],
                      edgecolor=COLORS['accent_cyan'],
                      alpha=0.95),
            arrowprops=dict(arrowstyle="->",
                            color=COLORS['accent_cyan'],
                            lw=0.8),
            zorder=100,
            visible=False
        )

        self.figure.tight_layout(pad=1.5)
        self.canvas.draw_idle()

    # ── Milky Way ────────────────────────────────────────────────────────

    def _draw_milky_way(self, ax):
        """Draw the approximate Milky Way band as a filled region."""
        if not self.chk_milkyway.isChecked():
            return

        from matplotlib.patches import Polygon  # lazy import

        try:
            ra_rad, dec_upper, dec_lower = _galactic_plane_points(
                n=500, half_width_deg=12.0)
            # Build filled polygon vertices: upper path forward + lower path reversed
            verts_upper = list(zip(ra_rad, dec_upper))
            verts_lower = list(zip(ra_rad[::-1], dec_lower[::-1]))
            verts = verts_upper + verts_lower

            poly = Polygon(verts, closed=True,
                           facecolor='#303850', edgecolor='none',
                           alpha=0.25, zorder=1,
                           label=self._tr("Milky Way", "Voie lactee"))
            patch = ax.add_patch(poly)
            self._milky_way_patches.append(patch)

            # Central line for emphasis
            ax.plot(ra_rad,
                    (dec_upper + dec_lower[::-1][:len(dec_upper)]) / 2.0
                    if len(dec_upper) == len(dec_lower) else
                    62.87 * np.sin(np.radians(
                        np.linspace(0, 360, 500, endpoint=False) - 282.25
                    )) * np.pi / 180.0,
                    color='#404868', alpha=0.3, linewidth=1.0,
                    linestyle='-', zorder=1)
        except Exception as exc:
            logger.debug("Milky Way drawing error: %s", exc)

    # ── Target scatter ───────────────────────────────────────────────────

    def _draw_targets(self, ax):
        """Scatter-plot all targets with appropriate size and colour."""
        if not self._targets:
            return

        ra_arr = np.array([t['ra'] for t in self._targets])
        dec_arr = np.array([t['dec'] for t in self._targets])
        lon_arr, lat_arr = self._ra_dec_to_aitoff_array(ra_arr, dec_arr)

        # Sizes: proportional to log(total_exposure + 1), clamped
        exposures = np.array([t['total_exposure'] for t in self._targets],
                             dtype=float)
        raw_sizes = np.log1p(exposures)  # log(1 + x)
        # Normalise to a visually pleasant range [20, 200]
        s_min, s_max = 20.0, 200.0
        if raw_sizes.max() > raw_sizes.min():
            sizes = s_min + (raw_sizes - raw_sizes.min()) / (
                raw_sizes.max() - raw_sizes.min()) * (s_max - s_min)
        else:
            sizes = np.full_like(raw_sizes, (s_min + s_max) / 2.0)

        # Colours depend on the selected mode
        colors = self._compute_colors()

        # Alpha: slight variation by density (more data = slightly brighter)
        alphas = np.clip(0.55 + 0.35 * (raw_sizes / max(raw_sizes.max(), 1.0)),
                         0.4, 0.92)

        # Draw scatter with individual alphas via RGBA colours
        rgba_colors = []
        for c_hex, a in zip(colors, alphas):
            r = int(c_hex[1:3], 16) / 255.0
            g = int(c_hex[3:5], 16) / 255.0
            b = int(c_hex[5:7], 16) / 255.0
            rgba_colors.append((r, g, b, a))

        self._scatter = ax.scatter(
            lon_arr, lat_arr,
            s=sizes,
            c=rgba_colors,
            edgecolors='none',
            zorder=5,
            picker=True
        )
        # Subtle glow: a second larger, faint scatter behind
        glow_rgba = [(r, g, b, a * 0.15) for (r, g, b, a) in rgba_colors]
        ax.scatter(lon_arr, lat_arr,
                   s=sizes * 2.5,
                   c=glow_rgba,
                   edgecolors='none',
                   zorder=4)

        # ── Labels ───────────────────────────────────────────────────────
        self._draw_labels(ax, lon_arr, lat_arr)

        # ── Legend ───────────────────────────────────────────────────────
        self._draw_legend(ax, colors)

    def _compute_colors(self) -> list:
        """Return a list of hex colour strings, one per target."""
        mode = self.cmb_colorby.currentData() or 'type'

        if mode == 'type':
            return [_get_object_color(t['object_type']) for t in self._targets]

        elif mode == 'filter':
            result = []
            for t in self._targets:
                filt = (t.get('dominant_filter') or '').strip().upper()
                # Try direct lookup in FILTER_COLORS
                c = FILTER_COLORS.get(filt)
                if not c:
                    # Normalise common aliases
                    if filt in ('HA', 'H-ALPHA', 'HALPHA'):
                        c = FILTER_COLORS.get('Ha', '#b8a0a0')
                    elif filt in ('OIII', 'O-III', 'O3'):
                        c = FILTER_COLORS.get('OIII', '#90b0b0')
                    elif filt in ('SII', 'S-II', 'S2'):
                        c = FILTER_COLORS.get('SII', '#b0a890')
                    else:
                        c = _DEFAULT_OBJECT_COLOR
                result.append(c)
            return result

        elif mode == 'integration':
            # Colour gradient: low=cool blue, high=warm orange
            exposures = np.array([t['total_exposure'] for t in self._targets],
                                 dtype=float)
            log_exp = np.log1p(exposures)
            if log_exp.max() > log_exp.min():
                norm = (log_exp - log_exp.min()) / (log_exp.max() - log_exp.min())
            else:
                norm = np.full_like(log_exp, 0.5)
            # Interpolate between cool blue (#90a0b8) and warm orange (#c0b098)
            result = []
            for n_val in norm:
                r = int(0x90 + (0xc0 - 0x90) * n_val)
                g = int(0xa0 + (0xb0 - 0xa0) * n_val)
                b = int(0xb8 + (0x98 - 0xb8) * n_val)
                result.append(f'#{r:02x}{g:02x}{b:02x}')
            return result

        # Fallback
        return [_DEFAULT_OBJECT_COLOR] * len(self._targets)

    def _draw_labels(self, ax, lon_arr, lat_arr):
        """Optionally draw target name labels."""
        if not self.chk_labels.isChecked():
            return

        import matplotlib.patheffects as patheffects  # lazy import

        for i, t in enumerate(self._targets):
            ann = ax.annotate(
                t['display_name'],
                xy=(lon_arr[i], lat_arr[i]),
                xytext=(4, 4),
                textcoords='offset pixels',
                fontsize=6,
                color=COLORS['text_secondary'],
                alpha=0.8,
                zorder=6,
                path_effects=[
                    patheffects.withStroke(
                        linewidth=2,
                        foreground=COLORS['bg_darkest'])
                ]
            )
            self._annotations.append(ann)

    def _draw_legend(self, ax, colors: list):
        """Draw a colour legend in the lower-right corner."""
        mode = self.cmb_colorby.currentData() or 'type'

        if mode == 'type':
            # Collect unique colours that are actually used
            used = {}
            for c_hex, t in zip(colors, self._targets):
                if c_hex not in used:
                    labels = _CATEGORY_LABELS.get(c_hex, ('Unknown', 'Inconnu'))
                    lbl = labels[1] if self.lang == 'fr' else labels[0]
                    used[c_hex] = lbl

            handles = []
            for c_hex, lbl in used.items():
                h = ax.scatter([], [], s=40, c=c_hex, edgecolors='none',
                               label=lbl)
                handles.append(h)

            if handles:
                legend = ax.legend(
                    handles=handles,
                    loc='lower right',
                    fontsize=7,
                    frameon=True,
                    framealpha=0.7,
                    facecolor=COLORS['bg_medium'],
                    edgecolor=COLORS['border'],
                    labelcolor=COLORS['text_primary'],
                    handletextpad=0.5,
                    borderpad=0.6,
                    title=self._tr("Object Type", "Type d'objet"),
                    title_fontsize=8
                )
                legend.get_title().set_color(COLORS['accent_cyan'])

        elif mode == 'filter':
            used = {}
            for c_hex, t in zip(colors, self._targets):
                filt = t.get('dominant_filter') or '?'
                if c_hex not in used:
                    used[c_hex] = filt

            handles = []
            for c_hex, lbl in used.items():
                h = ax.scatter([], [], s=40, c=c_hex, edgecolors='none',
                               label=lbl)
                handles.append(h)

            if handles:
                legend = ax.legend(
                    handles=handles,
                    loc='lower right',
                    fontsize=7,
                    frameon=True,
                    framealpha=0.7,
                    facecolor=COLORS['bg_medium'],
                    edgecolor=COLORS['border'],
                    labelcolor=COLORS['text_primary'],
                    handletextpad=0.5,
                    borderpad=0.6,
                    title=self._tr("Filter", "Filtre"),
                    title_fontsize=8
                )
                legend.get_title().set_color(COLORS['accent_cyan'])

        elif mode == 'integration':
            # Simple min/max label
            exps = [t['total_exposure'] for t in self._targets]
            if exps:
                lo = _integration_time_label(min(exps), self.lang)
                hi = _integration_time_label(max(exps), self.lang)
                handles = [
                    ax.scatter([], [], s=30, c='#90a0b8', edgecolors='none',
                               label=f"Min: {lo}"),
                    ax.scatter([], [], s=60, c='#c0b098', edgecolors='none',
                               label=f"Max: {hi}"),
                ]
                legend = ax.legend(
                    handles=handles,
                    loc='lower right',
                    fontsize=7,
                    frameon=True,
                    framealpha=0.7,
                    facecolor=COLORS['bg_medium'],
                    edgecolor=COLORS['border'],
                    labelcolor=COLORS['text_primary'],
                    handletextpad=0.5,
                    borderpad=0.6,
                    title=self._tr("Integration Time", "Temps d'integration"),
                    title_fontsize=8
                )
                legend.get_title().set_color(COLORS['accent_cyan'])

    # ====================================================================
    # TOGGLE CALLBACKS
    # ====================================================================

    def _on_toggle_grid(self, _state):
        self._draw_chart()

    def _on_toggle_milkyway(self, _state):
        self._draw_chart()

    def _on_toggle_labels(self, _state):
        self._draw_chart()

    def _on_colorby_changed(self, _index):
        self._draw_chart()

    def _on_projection_changed(self, _index):
        self._draw_chart()

    # ====================================================================
    # MOUSE INTERACTION — TOOLTIP ON HOVER
    # ====================================================================

    def _on_mouse_move(self, event):
        """Handle mouse move: show tooltip for the nearest target."""
        if (self._scatter is None or self._tooltip_annot is None or
                event.inaxes is None or not self._targets):
            if self._tooltip_annot is not None:
                self._tooltip_annot.set_visible(False)
                self.canvas.draw_idle()
            return

        # Check if cursor is near any point
        contains, details = self._scatter.contains(event)
        if not contains:
            if self._hover_index is not None:
                self._hover_index = None
                self._tooltip_annot.set_visible(False)
                self.canvas.draw_idle()
            return

        idx = details['ind'][0]
        if idx == self._hover_index:
            return  # Already showing this tooltip

        self._hover_index = idx
        t = self._targets[idx]

        # Position the tooltip at the target location
        lon, lat = self._ra_dec_to_aitoff(t['ra'], t['dec'])
        self._tooltip_annot.xy = (lon, lat)

        # Build tooltip text
        name = t['display_name']
        obj_type = t['object_type'] or self._tr('Unknown', 'Inconnu')
        integ = _integration_time_label(t['total_exposure'], self.lang)
        coords = _ra_dec_label(t['ra'], t['dec'])
        frames_lbl = self._tr("Frames", "Images")
        type_lbl = self._tr("Type", "Type")
        integ_lbl = self._tr("Integration", "Integration")

        text = (f"{name}\n"
                f"{type_lbl}: {obj_type}\n"
                f"{integ_lbl}: {integ} ({t['total_frames']} {frames_lbl})\n"
                f"{coords}")
        self._tooltip_annot.set_text(text)
        self._tooltip_annot.set_visible(True)
        self.canvas.draw_idle()

    # ====================================================================
    # MOUSE INTERACTION — CLICK TO SELECT
    # ====================================================================

    def _on_mouse_click(self, event):
        """Handle mouse click: emit target_clicked signal."""
        if (self._scatter is None or event.inaxes is None or
                not self._targets):
            return

        contains, details = self._scatter.contains(event)
        if not contains:
            return

        idx = details['ind'][0]
        t = self._targets[idx]
        logger.info("Sky chart: selected target '%s' (RA=%.4f, Dec=%.4f)",
                     t['display_name'], t['ra'], t['dec'])
        self.target_clicked.emit(t['display_name'], t['ra'], t['dec'])
        # Also notify the global signal bus
        signals.target_selected.emit(t['name'])

    # ====================================================================
    # EXPORT
    # ====================================================================

    def _export_png(self):
        """Export the current chart as a high-resolution PNG file."""
        default_name = self._tr("sky_chart.png", "carte_ciel.png")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("Save Sky Chart", "Enregistrer la carte celeste"),
            default_name,
            self._tr("PNG Images (*.png)", "Images PNG (*.png)")
        )
        if not file_path:
            return
        # Sanitise path
        file_path = str(Path(file_path).resolve())
        try:
            self.figure.savefig(
                file_path,
                dpi=200,
                facecolor=COLORS['bg_darkest'],
                edgecolor='none',
                bbox_inches='tight',
                pad_inches=0.3
            )
            logger.info("Sky chart exported to %s", file_path)
            self.lbl_status.setText(self._tr(
                f"Chart exported to {file_path}",
                f"Carte exportee vers {file_path}"))
        except Exception as exc:
            logger.error("Failed to export sky chart: %s", exc)
            self.lbl_status.setText(self._tr(
                f"Export failed: {exc}",
                f"Echec de l'export : {exc}"))

    # ====================================================================
    # PUBLIC API
    # ====================================================================

    def refresh(self):
        """Public method to trigger a full refresh (called from main window)."""
        self._load_and_plot()

    def highlight_target(self, target_name: str):
        """
        Highlight a specific target on the chart (e.g. when selected from
        another tab). Draws a circle around the target and scrolls to it.
        """
        if not self._targets or self._scatter is None:
            return

        for i, t in enumerate(self._targets):
            if t['name'] == target_name or t['display_name'] == target_name:
                lon, lat = self._ra_dec_to_aitoff(t['ra'], t['dec'])
                ax = self.figure.axes[0] if self.figure.axes else None
                if ax is None:
                    return
                # Draw a highlight ring
                ax.scatter([lon], [lat], s=300, facecolors='none',
                           edgecolors=COLORS['accent_cyan'],
                           linewidths=1.5, zorder=10, alpha=0.9)
                # Show the tooltip
                if self._tooltip_annot:
                    self._tooltip_annot.xy = (lon, lat)
                    name = t['display_name']
                    obj_type = t['object_type'] or self._tr(
                        'Unknown', 'Inconnu')
                    integ = _integration_time_label(
                        t['total_exposure'], self.lang)
                    coords = _ra_dec_label(t['ra'], t['dec'])
                    text = (f"{name}\n"
                            f"{self._tr('Type', 'Type')}: {obj_type}\n"
                            f"{self._tr('Integration', 'Integration')}: "
                            f"{integ}\n{coords}")
                    self._tooltip_annot.set_text(text)
                    self._tooltip_annot.set_visible(True)
                self.canvas.draw_idle()
                logger.info("Sky chart: highlighted target '%s'", target_name)
                return
