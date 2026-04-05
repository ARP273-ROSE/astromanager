#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - SHOOT CALENDAR TAB
================================================================================
Monthly calendar and yearly heatmap of astrophotography imaging sessions.
Provides visual overview of imaging activity, session details, and statistics.
================================================================================
"""

import logging
import calendar
from datetime import datetime, date, timedelta
from collections import defaultdict

import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QSpinBox, QComboBox,
    QFrame, QGridLayout, QScrollArea, QStackedWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QButtonGroup, QRadioButton, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QPixmap, QPainter

from core.config import get_config
from core.database import get_db
from core.i18n import get_lang
from core.signals import signals
from gui.theme import COLORS, prettify_filter_name

logger = logging.getLogger(__name__)

# Heatmap color scale (6 levels: none → very high)
_HEAT_COLORS = [
    '#0a0e1a',  # No data (bg_dark)
    '#1a2a3a',  # Low
    '#2a4a5a',  # Medium-low
    '#4a7a8a',  # Medium
    '#6a9aaa',  # High
    '#94b8c8',  # Very high (accent_cyan)
]


def _lerp_color(c1: str, c2: str, t: float) -> str:
    """Linearly interpolate between two hex colors."""
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f'#{r:02x}{g:02x}{b:02x}'


def _heat_color(value: float, max_value: float) -> str:
    """Return a color from the heatmap scale based on value/max ratio."""
    if max_value <= 0 or value <= 0:
        return _HEAT_COLORS[0]
    ratio = min(value / max_value, 1.0)
    # Map ratio to index in the 5 non-zero color levels
    idx = ratio * 4  # 0..4 mapping into colors[1..5]
    lo = int(idx)
    hi = min(lo + 1, 4)
    frac = idx - lo
    return _lerp_color(_HEAT_COLORS[lo + 1], _HEAT_COLORS[hi + 1], frac)


# ============================================================================
# STAT CARD (reusable stat display widget)
# ============================================================================

class _StatCard(QFrame):
    """Compact card displaying a single statistic."""

    def __init__(self, title: str, value: str = "-", color: str = "#88b8d8",
                 parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            _StatCard {{
                background: rgba(20, 30, 50, 0.6);
                border: 1px solid rgba(100, 140, 180, 0.3);
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #8898a8; font-size: 8pt;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(
            f"color: {color}; font-size: 14pt; font-weight: bold;"
        )
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)

    def set_value(self, value: str):
        self.value_label.setText(value)

    def set_title(self, title: str):
        self.title_label.setText(title)


# ============================================================================
# DAY CELL (for monthly calendar grid)
# ============================================================================

class _DayCell(QFrame):
    """Single day cell in the monthly calendar grid."""

    clicked = pyqtSignal(str)  # YYYY-MM-DD

    def __init__(self, parent=None):
        super().__init__(parent)
        self._date_str = ""
        self._has_data = False
        self.setFixedHeight(80)
        self.setMinimumWidth(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(1)

        # Day number
        self.day_label = QLabel("")
        self.day_label.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 10pt; "
            f"font-weight: bold; background: transparent;")
        self.day_label.setAlignment(Qt.AlignmentFlag.AlignLeft
                                    | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.day_label)

        # Frames count
        self.frames_label = QLabel("")
        self.frames_label.setStyleSheet(
            f"color: {COLORS['accent_cyan']}; font-size: 7pt; "
            f"background: transparent;")
        self.frames_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.frames_label)

        # Integration time
        self.time_label = QLabel("")
        self.time_label.setStyleSheet(
            f"color: {COLORS['accent_purple']}; font-size: 7pt; "
            f"background: transparent;")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.time_label)

        # Target names
        self.targets_label = QLabel("")
        self.targets_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 7pt; "
            f"background: transparent;")
        self.targets_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.targets_label.setWordWrap(True)
        layout.addWidget(self.targets_label)

        layout.addStretch()
        self._apply_empty_style()

    def _apply_empty_style(self):
        """Style for empty/unused cell."""
        self.setStyleSheet(f"""
            _DayCell {{
                background-color: {COLORS['bg_darkest']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
            }}
        """)

    def set_empty(self):
        """Mark cell as outside the current month."""
        self._date_str = ""
        self._has_data = False
        self.day_label.setText("")
        self.frames_label.setText("")
        self.time_label.setText("")
        self.targets_label.setText("")
        self.setToolTip("")
        self._apply_empty_style()
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_day(self, day: int, date_str: str, data: dict | None,
                is_today: bool, bg_color: str, lang: str):
        """Configure the cell for a specific day.

        Parameters
        ----------
        day : int
            Day number (1-31).
        date_str : str
            ISO date string (YYYY-MM-DD).
        data : dict or None
            {frames, exposure, targets, target_count} or None.
        is_today : bool
            Whether this is today's date.
        bg_color : str
            Background hex color from heatmap scale.
        lang : str
            'fr' or 'en'.
        """
        self._date_str = date_str
        self._has_data = data is not None
        self.day_label.setText(str(day))
        self.setCursor(Qt.CursorShape.PointingHandCursor
                       if self._has_data
                       else Qt.CursorShape.ArrowCursor)

        border_color = COLORS['accent_cyan'] if is_today else COLORS['border']
        border_width = "2px" if is_today else "1px"

        if data:
            frames = data.get('frames', 0)
            exposure = data.get('exposure', 0)
            targets = data.get('targets', [])

            self.frames_label.setText(
                f"{'images' if lang == 'fr' else 'frames'}: {frames}")
            self.time_label.setText(self._fmt_time(exposure, lang))

            # Show up to 2 target names
            if len(targets) > 2:
                names = ", ".join(targets[:2]) + f" +{len(targets) - 2}"
            else:
                names = ", ".join(targets) if targets else ""
            self.targets_label.setText(names)

            # Tooltip with full details
            if lang == 'fr':
                tip = (f"📅 {date_str}\n"
                       f"🖼 {frames} images\n"
                       f"⏱ {self._fmt_time(exposure, lang)}\n"
                       f"🎯 {', '.join(targets)}")
            else:
                tip = (f"📅 {date_str}\n"
                       f"🖼 {frames} frames\n"
                       f"⏱ {self._fmt_time(exposure, lang)}\n"
                       f"🎯 {', '.join(targets)}")
            self.setToolTip(tip)
        else:
            self.frames_label.setText("")
            self.time_label.setText("")
            self.targets_label.setText("")
            if lang == 'fr':
                self.setToolTip(f"{date_str} — Aucune donnée")
            else:
                self.setToolTip(f"{date_str} — No data")

        self.setStyleSheet(f"""
            _DayCell {{
                background-color: {bg_color};
                border: {border_width} solid {border_color};
                border-radius: 4px;
            }}
            _DayCell:hover {{
                border-color: {COLORS['accent_cyan']};
            }}
        """)

    @staticmethod
    def _fmt_time(seconds: float, lang: str) -> str:
        """Format seconds into a compact human-readable string."""
        if seconds <= 0:
            return ""
        hours = seconds / 3600
        if hours >= 1:
            h = int(hours)
            m = int((hours - h) * 60)
            return f"{h}h {m:02d}m" if m else f"{h}h"
        minutes = seconds / 60
        if minutes >= 1:
            return f"{minutes:.0f}m"
        return f"{seconds:.0f}s"

    def mousePressEvent(self, event):
        if self._date_str and self._has_data:
            self.clicked.emit(self._date_str)
        super().mousePressEvent(event)


# ============================================================================
# MAIN CALENDAR TAB
# ============================================================================

class CalendarTab(QWidget):
    """Shoot Calendar — monthly calendar and yearly heatmap of imaging sessions."""

    date_selected = pyqtSignal(str)  # YYYY-MM-DD

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self.lang = get_lang()

        # Internal state
        self._year_data = {}       # {date_str: {frames, exposure, targets, target_count, details}}
        self._selected_date = None
        self._current_year = datetime.now().year
        self._current_month = datetime.now().month

        self._init_ui()
        self._connect_signals()

        # Deferred initial load
        QTimer.singleShot(300, self._load_year_data)

    # ────────────────────────────────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────────────────────────────────

    def _tr(self, en: str, fr: str) -> str:
        return fr if self.lang == 'fr' else en

    def _format_time(self, seconds: float) -> str:
        """Format seconds into human-readable string."""
        if seconds is None or seconds <= 0:
            return "-"
        hours = seconds / 3600
        if hours >= 1:
            h = int(hours)
            m = int((hours - h) * 60)
            return f"{h}h {m:02d}m" if m else f"{h}h"
        minutes = seconds / 60
        if minutes >= 1:
            return f"{minutes:.0f}m"
        return f"{seconds:.0f}s"

    # ────────────────────────────────────────────────────────────────────
    # UI Construction
    # ────────────────────────────────────────────────────────────────────

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # ── Title ──
        title = QLabel(self._tr(
            "📅 Shoot Calendar",
            "📅 Calendrier de Prises de Vue"
        ))
        title.setStyleSheet(
            "font-size: 13pt; font-weight: bold; color: #a8c8e8;")
        title.setToolTip(self._tr(
            "Visual overview of all your imaging sessions",
            "Vue d'ensemble visuelle de toutes vos sessions d'imagerie"
        ))
        main_layout.addWidget(title)

        # ── Statistics Summary Cards ──
        self._build_stats_bar(main_layout)

        # ── Controls Bar ──
        self._build_controls_bar(main_layout)

        # ── Stacked views (Monthly / Yearly) ──
        self.view_stack = QStackedWidget()
        self._build_monthly_view()
        self._build_yearly_view()
        main_layout.addWidget(self.view_stack, 1)

        # ── Session Details Panel ──
        self._build_details_panel(main_layout)

    # ------------------------------------------------------------------
    # Stats bar
    # ------------------------------------------------------------------

    def _build_stats_bar(self, parent_layout: QVBoxLayout):
        """Build the statistics summary cards row."""
        cards_layout = QGridLayout()
        cards_layout.setSpacing(6)

        self.card_nights = _StatCard(
            self._tr("Imaging Nights", "Nuits d'Imagerie"),
            "-", "#88d8b8")
        self.card_nights.setToolTip(self._tr(
            "Total number of nights with imaging data this year",
            "Nombre total de nuits avec des données d'imagerie cette année"
        ))

        self.card_total_time = _StatCard(
            self._tr("Total Integration", "Intégration Totale"),
            "-", "#88b8d8")
        self.card_total_time.setToolTip(self._tr(
            "Total integration time accumulated this year",
            "Temps d'intégration total accumulé cette année"
        ))

        self.card_best_month = _StatCard(
            self._tr("Best Month", "Meilleur Mois"),
            "-", "#d8b888")
        self.card_best_month.setToolTip(self._tr(
            "Month with the most integration time this year",
            "Mois avec le plus de temps d'intégration cette année"
        ))

        self.card_avg_frames = _StatCard(
            self._tr("Avg Frames/Night", "Moy. Images/Nuit"),
            "-", "#b888d8")
        self.card_avg_frames.setToolTip(self._tr(
            "Average number of frames per imaging night this year",
            "Nombre moyen d'images par nuit d'imagerie cette année"
        ))

        self.card_streak = _StatCard(
            self._tr("Longest Streak", "Plus Longue Série"),
            "-", "#d88888")
        self.card_streak.setToolTip(self._tr(
            "Longest streak of consecutive imaging nights this year",
            "Plus longue série de nuits d'imagerie consécutives cette année"
        ))

        self.card_targets_count = _StatCard(
            self._tr("Unique Targets", "Cibles Uniques"),
            "-", "#88d8d8")
        self.card_targets_count.setToolTip(self._tr(
            "Number of unique targets imaged this year",
            "Nombre de cibles uniques imagées cette année"
        ))

        cards_layout.addWidget(self.card_nights, 0, 0)
        cards_layout.addWidget(self.card_total_time, 0, 1)
        cards_layout.addWidget(self.card_best_month, 0, 2)
        cards_layout.addWidget(self.card_avg_frames, 0, 3)
        cards_layout.addWidget(self.card_streak, 0, 4)
        cards_layout.addWidget(self.card_targets_count, 0, 5)

        parent_layout.addLayout(cards_layout)

    # ------------------------------------------------------------------
    # Controls bar
    # ------------------------------------------------------------------

    def _build_controls_bar(self, parent_layout: QVBoxLayout):
        """Build the navigation and control buttons bar."""
        controls = QHBoxLayout()
        controls.setSpacing(8)

        # View toggle: Monthly / Yearly
        self.view_monthly_rb = QRadioButton(
            self._tr("Monthly", "Mensuel"))
        self.view_monthly_rb.setToolTip(self._tr(
            "Show monthly calendar grid view",
            "Afficher la vue calendrier mensuel"
        ))
        self.view_monthly_rb.setChecked(True)
        self.view_monthly_rb.toggled.connect(self._on_view_toggled)

        self.view_yearly_rb = QRadioButton(
            self._tr("Yearly Heatmap", "Heatmap Annuelle"))
        self.view_yearly_rb.setToolTip(self._tr(
            "Show yearly GitHub-style contribution heatmap",
            "Afficher la heatmap de contribution style GitHub annuelle"
        ))

        view_group = QButtonGroup(self)
        view_group.addButton(self.view_monthly_rb, 0)
        view_group.addButton(self.view_yearly_rb, 1)

        controls.addWidget(self.view_monthly_rb)
        controls.addWidget(self.view_yearly_rb)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setStyleSheet(f"color: {COLORS['border']};")
        controls.addWidget(sep1)

        # Navigation: << < [Month Year] > >>
        self.prev_year_btn = QPushButton("≪")
        self.prev_year_btn.setFixedWidth(36)
        self.prev_year_btn.setToolTip(self._tr(
            "Go to previous year", "Aller à l'année précédente"))
        self.prev_year_btn.clicked.connect(self._prev_year)

        self.prev_month_btn = QPushButton("◀")
        self.prev_month_btn.setFixedWidth(36)
        self.prev_month_btn.setToolTip(self._tr(
            "Go to previous month", "Aller au mois précédent"))
        self.prev_month_btn.clicked.connect(self._prev_month)

        self.month_year_label = QLabel("")
        self.month_year_label.setStyleSheet(
            f"color: {COLORS['accent_cyan']}; font-size: 12pt; "
            f"font-weight: bold; background: transparent; padding: 0 12px;")
        self.month_year_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.month_year_label.setMinimumWidth(180)
        self.month_year_label.setToolTip(self._tr(
            "Currently displayed month and year",
            "Mois et année actuellement affichés"
        ))

        self.next_month_btn = QPushButton("▶")
        self.next_month_btn.setFixedWidth(36)
        self.next_month_btn.setToolTip(self._tr(
            "Go to next month", "Aller au mois suivant"))
        self.next_month_btn.clicked.connect(self._next_month)

        self.next_year_btn = QPushButton("≫")
        self.next_year_btn.setFixedWidth(36)
        self.next_year_btn.setToolTip(self._tr(
            "Go to next year", "Aller à l'année suivante"))
        self.next_year_btn.clicked.connect(self._next_year)

        controls.addWidget(self.prev_year_btn)
        controls.addWidget(self.prev_month_btn)
        controls.addWidget(self.month_year_label)
        controls.addWidget(self.next_month_btn)
        controls.addWidget(self.next_year_btn)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet(f"color: {COLORS['border']};")
        controls.addWidget(sep2)

        # Year spinbox
        year_label = QLabel(self._tr("Year:", "Année :"))
        year_label.setStyleSheet("background: transparent;")
        year_label.setToolTip(self._tr(
            "Select a specific year", "Sélectionner une année spécifique"))
        controls.addWidget(year_label)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, 2100)
        self.year_spin.setValue(self._current_year)
        self.year_spin.setToolTip(self._tr(
            "Select the year to display",
            "Sélectionner l'année à afficher"
        ))
        self.year_spin.valueChanged.connect(self._on_year_changed)
        controls.addWidget(self.year_spin)

        # Color-by selector
        color_label = QLabel(self._tr("Color by:", "Couleur par :"))
        color_label.setStyleSheet("background: transparent;")
        color_label.setToolTip(self._tr(
            "Choose which metric determines cell color intensity",
            "Choisir quelle métrique détermine l'intensité de couleur"
        ))
        controls.addWidget(color_label)

        self.color_by_combo = QComboBox()
        self.color_by_combo.addItem(
            self._tr("Integration Time", "Temps d'Intégration"), "exposure")
        self.color_by_combo.addItem(
            self._tr("Frame Count", "Nombre d'Images"), "frames")
        self.color_by_combo.addItem(
            self._tr("Target Count", "Nombre de Cibles"), "target_count")
        self.color_by_combo.setToolTip(self._tr(
            "Metric used for color intensity in calendar and heatmap",
            "Métrique utilisée pour l'intensité des couleurs dans le calendrier et la heatmap"
        ))
        self.color_by_combo.currentIndexChanged.connect(self._on_color_by_changed)
        controls.addWidget(self.color_by_combo)

        controls.addStretch()

        # Export button
        self.export_btn = QPushButton(self._tr("📷 Export PNG", "📷 Exporter PNG"))
        self.export_btn.setToolTip(self._tr(
            "Export the current calendar view as a PNG image",
            "Exporter la vue calendrier actuelle en image PNG"
        ))
        self.export_btn.clicked.connect(self._export_png)
        controls.addWidget(self.export_btn)

        # Today button
        self.today_btn = QPushButton(self._tr("📍 Today", "📍 Aujourd'hui"))
        self.today_btn.setToolTip(self._tr(
            "Jump to current month and year",
            "Aller au mois et à l'année en cours"
        ))
        self.today_btn.clicked.connect(self._go_today)
        controls.addWidget(self.today_btn)

        # Refresh button
        self.refresh_btn = QPushButton(self._tr("🔄 Refresh", "🔄 Actualiser"))
        self.refresh_btn.setToolTip(self._tr(
            "Reload data from the database",
            "Recharger les données depuis la base de données"
        ))
        self.refresh_btn.clicked.connect(self._load_year_data)
        controls.addWidget(self.refresh_btn)

        parent_layout.addLayout(controls)

    # ------------------------------------------------------------------
    # Monthly calendar view (pure PyQt6)
    # ------------------------------------------------------------------

    def _build_monthly_view(self):
        """Build the monthly calendar grid using QGridLayout + _DayCell."""
        self.monthly_widget = QWidget()
        monthly_layout = QVBoxLayout(self.monthly_widget)
        monthly_layout.setSpacing(4)
        monthly_layout.setContentsMargins(0, 0, 0, 0)

        # Day-of-week header row
        header_layout = QGridLayout()
        header_layout.setSpacing(4)
        day_names_en = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_names_fr = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
        day_names = day_names_fr if self.lang == 'fr' else day_names_en

        for col, name in enumerate(day_names):
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {COLORS['accent_cyan']}; font-weight: bold; "
                f"font-size: 9pt; background: transparent; padding: 4px;")
            lbl.setToolTip(self._tr(
                f"Day of the week: {day_names_en[col]}",
                f"Jour de la semaine : {day_names_fr[col]}"
            ))
            header_layout.addWidget(lbl, 0, col)
        monthly_layout.addLayout(header_layout)

        # Day cells grid (6 rows × 7 columns)
        self.day_grid = QGridLayout()
        self.day_grid.setSpacing(4)
        self._day_cells: list[list[_DayCell]] = []

        for row in range(6):
            row_cells = []
            for col in range(7):
                cell = _DayCell()
                cell.clicked.connect(self._on_day_clicked)
                self.day_grid.addWidget(cell, row, col)
                row_cells.append(cell)
            self._day_cells.append(row_cells)

        monthly_layout.addLayout(self.day_grid)
        monthly_layout.addStretch()

        # Color legend
        self._build_monthly_legend(monthly_layout)

        self.view_stack.addWidget(self.monthly_widget)

    def _build_monthly_legend(self, parent_layout: QVBoxLayout):
        """Build the color legend bar for the monthly view."""
        legend_layout = QHBoxLayout()
        legend_layout.setSpacing(4)

        legend_label = QLabel(self._tr("Less", "Moins"))
        legend_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 8pt; "
            f"background: transparent;")
        legend_label.setToolTip(self._tr(
            "Color legend — darker means less data",
            "Légende des couleurs — plus sombre = moins de données"
        ))
        legend_layout.addStretch()
        legend_layout.addWidget(legend_label)

        for color in _HEAT_COLORS:
            swatch = QFrame()
            swatch.setFixedSize(16, 16)
            swatch.setStyleSheet(
                f"background-color: {color}; border: 1px solid "
                f"{COLORS['border']}; border-radius: 2px;")
            legend_layout.addWidget(swatch)

        more_label = QLabel(self._tr("More", "Plus"))
        more_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 8pt; "
            f"background: transparent;")
        more_label.setToolTip(self._tr(
            "Color legend — brighter means more data",
            "Légende des couleurs — plus clair = plus de données"
        ))
        legend_layout.addWidget(more_label)
        legend_layout.addStretch()

        parent_layout.addLayout(legend_layout)

    # ------------------------------------------------------------------
    # Yearly heatmap view (matplotlib)
    # ------------------------------------------------------------------

    def _build_yearly_view(self):
        """Build the yearly heatmap using matplotlib embedded canvas."""
        self.yearly_widget = QWidget()
        yearly_layout = QVBoxLayout(self.yearly_widget)
        yearly_layout.setContentsMargins(0, 0, 0, 0)

        # Lazy import matplotlib to avoid startup cost
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
            import matplotlib

            matplotlib.use('QtAgg')

            self._fig = Figure(figsize=(14, 3), dpi=100)
            self._fig.patch.set_facecolor(COLORS['bg_dark'])
            self._canvas = FigureCanvasQTAgg(self._fig)
            self._canvas.setToolTip(self._tr(
                "Yearly imaging heatmap — each cell is one day, "
                "color intensity reflects activity",
                "Heatmap d'imagerie annuelle — chaque cellule est un jour, "
                "l'intensité de couleur reflète l'activité"
            ))
            yearly_layout.addWidget(self._canvas)
            self._has_matplotlib = True
        except ImportError:
            self._has_matplotlib = False
            fallback = QLabel(self._tr(
                "⚠ matplotlib is required for the yearly heatmap view.\n"
                "Install it with: pip install matplotlib",
                "⚠ matplotlib est requis pour la vue heatmap annuelle.\n"
                "Installez-le avec : pip install matplotlib"
            ))
            fallback.setStyleSheet(
                f"color: {COLORS['warning']}; font-size: 10pt; "
                f"padding: 20px;")
            fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            yearly_layout.addWidget(fallback)

        self.view_stack.addWidget(self.yearly_widget)

    # ------------------------------------------------------------------
    # Session details panel
    # ------------------------------------------------------------------

    def _build_details_panel(self, parent_layout: QVBoxLayout):
        """Build the bottom panel showing detailed session info for a selected day."""
        self.details_group = QGroupBox(
            self._tr("📋 Session Details", "📋 Détails de Session"))
        self.details_group.setToolTip(self._tr(
            "Click a day with imaging data to see detailed session information",
            "Cliquez sur un jour avec des données d'imagerie pour voir "
            "les détails de la session"
        ))
        details_layout = QVBoxLayout(self.details_group)
        details_layout.setContentsMargins(6, 14, 6, 6)

        # Date label
        self.detail_date_label = QLabel(self._tr(
            "Select a day with data to view details.",
            "Sélectionnez un jour avec des données pour voir les détails."
        ))
        self.detail_date_label.setStyleSheet(
            f"color: {COLORS['accent_cyan']}; font-size: 10pt; "
            f"font-weight: bold; background: transparent;")
        self.detail_date_label.setToolTip(self._tr(
            "Date of the selected imaging session",
            "Date de la session d'imagerie sélectionnée"
        ))
        details_layout.addWidget(self.detail_date_label)

        # Details table
        self.details_table = QTableWidget()
        self.details_table.setColumnCount(7)
        self.details_table.setHorizontalHeaderLabels([
            self._tr("Target", "Cible"),
            self._tr("Filter", "Filtre"),
            self._tr("Frames", "Images"),
            self._tr("Integration", "Intégration"),
            self._tr("HFR", "HFR"),
            self._tr("FWHM", "FWHM"),
            self._tr("Telescope", "Télescope"),
        ])
        self.details_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.details_table.setAlternatingRowColors(True)
        self.details_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.details_table.setMaximumHeight(180)
        self.details_table.setToolTip(self._tr(
            "Per-target breakdown of the selected night's observations",
            "Détail par cible des observations de la nuit sélectionnée"
        ))
        self.details_table.verticalHeader().setVisible(False)
        details_layout.addWidget(self.details_table)

        # Totals row
        self.detail_totals_label = QLabel("")
        self.detail_totals_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 9pt; "
            f"background: transparent;")
        self.detail_totals_label.setToolTip(self._tr(
            "Summary totals for the selected night",
            "Totaux récapitulatifs pour la nuit sélectionnée"
        ))
        details_layout.addWidget(self.detail_totals_label)

        parent_layout.addWidget(self.details_group)

    # ────────────────────────────────────────────────────────────────────
    # Signal Connections
    # ────────────────────────────────────────────────────────────────────

    def _connect_signals(self):
        """Connect global signals for data refresh."""
        signals.observation_added.connect(self._on_data_changed)
        signals.targets_refreshed.connect(self._on_data_changed)
        signals.history_refreshed.connect(self._on_data_changed)

    def _on_data_changed(self, *args):
        """Reload data when observations change."""
        self._load_year_data()

    # ────────────────────────────────────────────────────────────────────
    # Data Loading
    # ────────────────────────────────────────────────────────────────────

    def _load_year_data(self):
        """Load all observation data for the current year from the database."""
        self._year_data.clear()
        db = get_db()

        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                # Fetch all observations for the year, joined with target names
                cursor.execute("""
                    SELECT
                        o.observation_date,
                        t.name AS target_name,
                        o.filter,
                        o.frame_count,
                        o.exposure_time,
                        o.hfr,
                        o.fwhm,
                        o.telescope,
                        o.camera
                    FROM observations o
                    JOIN targets t ON o.target_id = t.id
                    WHERE o.observation_date BETWEEN ? AND ?
                    ORDER BY o.observation_date
                """, (f"{self._current_year}-01-01",
                      f"{self._current_year}-12-31"))

                rows = cursor.fetchall()

                for row in rows:
                    date_str = row['observation_date']
                    if not date_str:
                        continue

                    if date_str not in self._year_data:
                        self._year_data[date_str] = {
                            'frames': 0,
                            'exposure': 0.0,
                            'targets': [],
                            'target_count': 0,
                            'details': [],
                        }

                    entry = self._year_data[date_str]
                    frames = row['frame_count'] or 0
                    exposure = row['exposure_time'] or 0.0
                    target_name = row['target_name'] or '?'

                    entry['frames'] += frames
                    entry['exposure'] += exposure

                    if target_name not in entry['targets']:
                        entry['targets'].append(target_name)

                    entry['details'].append({
                        'target': target_name,
                        'filter': row['filter'] or '',
                        'frames': frames,
                        'exposure': exposure,
                        'hfr': row['hfr'],
                        'fwhm': row['fwhm'],
                        'telescope': row['telescope'] or '',
                        'camera': row['camera'] or '',
                    })

                # Compute target_count for each day
                for entry in self._year_data.values():
                    entry['target_count'] = len(entry['targets'])

        except Exception as e:
            logger.error(f"Failed to load calendar data: {e}")

        # Update all views
        self._update_stats()
        self._update_monthly_view()
        if self.view_stack.currentIndex() == 1:
            self._update_yearly_view()

    # ────────────────────────────────────────────────────────────────────
    # Statistics Computation
    # ────────────────────────────────────────────────────────────────────

    def _update_stats(self):
        """Recompute and display year-level statistics."""
        data = self._year_data

        # Total imaging nights
        total_nights = len(data)
        self.card_nights.set_value(str(total_nights))

        # Total integration time
        total_exposure = sum(d['exposure'] for d in data.values())
        self.card_total_time.set_value(self._format_time(total_exposure))

        # Best month
        month_exposure = defaultdict(float)
        for date_str, d in data.items():
            try:
                m = int(date_str.split('-')[1])
                month_exposure[m] += d['exposure']
            except (IndexError, ValueError):
                continue

        if month_exposure:
            best_m = max(month_exposure, key=month_exposure.get)
            month_names_en = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            month_names_fr = ["", "Jan", "Fév", "Mar", "Avr", "Mai", "Juin",
                              "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]
            names = month_names_fr if self.lang == 'fr' else month_names_en
            self.card_best_month.set_value(
                f"{names[best_m]} ({self._format_time(month_exposure[best_m])})")
        else:
            self.card_best_month.set_value("-")

        # Average frames per night
        total_frames = sum(d['frames'] for d in data.values())
        avg = total_frames / total_nights if total_nights > 0 else 0
        self.card_avg_frames.set_value(f"{avg:.0f}" if avg > 0 else "-")

        # Longest streak of consecutive imaging nights
        if data:
            sorted_dates = sorted(data.keys())
            parsed = []
            for ds in sorted_dates:
                try:
                    parsed.append(date.fromisoformat(ds))
                except ValueError:
                    continue

            max_streak = 1
            current_streak = 1
            for i in range(1, len(parsed)):
                if (parsed[i] - parsed[i - 1]).days == 1:
                    current_streak += 1
                    max_streak = max(max_streak, current_streak)
                else:
                    current_streak = 1
            streak_label = (f"{max_streak} "
                            + self._tr("nights", "nuits"))
            self.card_streak.set_value(streak_label)
        else:
            self.card_streak.set_value("-")

        # Unique targets
        all_targets = set()
        for d in data.values():
            all_targets.update(d['targets'])
        self.card_targets_count.set_value(
            str(len(all_targets)) if all_targets else "-")

    # ────────────────────────────────────────────────────────────────────
    # Monthly View Rendering
    # ────────────────────────────────────────────────────────────────────

    def _update_monthly_view(self):
        """Refresh the monthly calendar grid for the current month/year."""
        year = self._current_year
        month = self._current_month

        # Update month/year label
        month_names_en = ["", "January", "February", "March", "April", "May",
                          "June", "July", "August", "September", "October",
                          "November", "December"]
        month_names_fr = ["", "Janvier", "Février", "Mars", "Avril", "Mai",
                          "Juin", "Juillet", "Août", "Septembre", "Octobre",
                          "Novembre", "Décembre"]
        names = month_names_fr if self.lang == 'fr' else month_names_en
        self.month_year_label.setText(f"{names[month]} {year}")

        # Calendar math (Monday = 0)
        first_weekday, days_in_month = calendar.monthrange(year, month)
        today = date.today()

        # Find max value for color scaling within this month
        metric_key = self.color_by_combo.currentData() or "exposure"
        month_values = []
        for day in range(1, days_in_month + 1):
            ds = f"{year}-{month:02d}-{day:02d}"
            if ds in self._year_data:
                month_values.append(self._year_data[ds].get(metric_key, 0))
        max_val = max(month_values) if month_values else 1.0

        # Fill cells
        day_num = 1
        for row in range(6):
            for col in range(7):
                cell = self._day_cells[row][col]
                cell_index = row * 7 + col

                if cell_index < first_weekday or day_num > days_in_month:
                    cell.set_empty()
                else:
                    ds = f"{year}-{month:02d}-{day_num:02d}"
                    day_data = self._year_data.get(ds)
                    is_today = (date(year, month, day_num) == today)

                    # Determine color
                    if day_data:
                        val = day_data.get(metric_key, 0)
                        bg = _heat_color(val, max_val)
                    else:
                        bg = COLORS['bg_medium']

                    cell.set_day(day_num, ds, day_data, is_today, bg,
                                 self.lang)
                    day_num += 1

    # ────────────────────────────────────────────────────────────────────
    # Yearly Heatmap Rendering (matplotlib)
    # ────────────────────────────────────────────────────────────────────

    def _update_yearly_view(self):
        """Render the GitHub-style yearly heatmap."""
        if not self._has_matplotlib:
            return

        from matplotlib.colors import LinearSegmentedColormap
        import matplotlib.pyplot as plt

        self._fig.clear()
        ax = self._fig.add_subplot(111)

        year = self._current_year
        metric_key = self.color_by_combo.currentData() or "exposure"

        # Build 53×7 grid (weeks × days)
        jan1 = date(year, 1, 1)
        dec31 = date(year, 12, 31)
        start_offset = jan1.weekday()  # Monday=0

        total_days = (dec31 - jan1).days + 1
        # Number of columns (weeks)
        n_weeks = ((start_offset + total_days - 1) // 7) + 1
        grid = np.full((7, n_weeks), np.nan)
        day_dates = {}

        for i in range(total_days):
            d = jan1 + timedelta(days=i)
            col = (start_offset + i) // 7
            row = (start_offset + i) % 7
            ds = d.isoformat()
            val = 0.0
            if ds in self._year_data:
                val = float(self._year_data[ds].get(metric_key, 0))
            grid[row, col] = val
            day_dates[(row, col)] = ds

        # Custom colormap matching theme
        cmap_colors = [
            (int(c[1:3], 16)/255, int(c[3:5], 16)/255, int(c[5:7], 16)/255)
            for c in _HEAT_COLORS
        ]
        cmap = LinearSegmentedColormap.from_list(
            'cosmic_heat', cmap_colors, N=256)

        # Mask NaN cells
        masked = np.ma.masked_invalid(grid)
        max_val = np.nanmax(grid) if np.any(np.isfinite(grid)) else 1.0
        if max_val <= 0:
            max_val = 1.0

        ax.set_facecolor(COLORS['bg_dark'])
        im = ax.pcolormesh(masked, cmap=cmap, vmin=0, vmax=max_val,
                           edgecolors=COLORS['border'], linewidth=0.5)

        # Month labels along top
        month_names_en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        month_names_fr = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin",
                          "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]
        m_names = month_names_fr if self.lang == 'fr' else month_names_en

        for m in range(1, 13):
            first_of_month = date(year, m, 1)
            day_offset = (first_of_month - jan1).days
            week_col = (start_offset + day_offset) // 7
            ax.text(week_col + 0.5, -0.5, m_names[m - 1],
                    ha='left', va='bottom', fontsize=7,
                    color=COLORS['text_secondary'])

        # Day-of-week labels on the left
        day_labels_en = ["Mon", "", "Wed", "", "Fri", "", "Sun"]
        day_labels_fr = ["Lun", "", "Mer", "", "Ven", "", "Dim"]
        d_labels = day_labels_fr if self.lang == 'fr' else day_labels_en

        ax.set_yticks([i + 0.5 for i in range(7)])
        ax.set_yticklabels(d_labels, fontsize=7,
                           color=COLORS['text_secondary'])
        ax.set_xticks([])
        ax.invert_yaxis()

        # Style axes
        ax.tick_params(axis='both', length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)

        # Color legend bar
        cbar = self._fig.colorbar(im, ax=ax, orientation='horizontal',
                                  fraction=0.04, pad=0.15,
                                  aspect=40)
        metric_labels = {
            'exposure': self._tr("Integration (s)", "Intégration (s)"),
            'frames': self._tr("Frames", "Images"),
            'target_count': self._tr("Targets", "Cibles"),
        }
        cbar.set_label(metric_labels.get(metric_key, ""),
                       fontsize=8, color=COLORS['text_secondary'])
        cbar.ax.tick_params(labelsize=7, colors=COLORS['text_secondary'])

        # Title
        ax.set_title(
            self._tr(f"Imaging Activity — {year}",
                     f"Activité d'Imagerie — {year}"),
            fontsize=11, fontweight='bold',
            color=COLORS['accent_cyan'], pad=12)

        self._fig.tight_layout(pad=1.0)
        self._canvas.draw()

    # ────────────────────────────────────────────────────────────────────
    # Session Details
    # ────────────────────────────────────────────────────────────────────

    def _show_day_details(self, date_str: str):
        """Populate the details panel for a specific day."""
        self._selected_date = date_str
        data = self._year_data.get(date_str)

        if not data or not data.get('details'):
            self.detail_date_label.setText(self._tr(
                f"No data for {date_str}",
                f"Aucune donnée pour {date_str}"
            ))
            self.details_table.setRowCount(0)
            self.detail_totals_label.setText("")
            return

        # Header
        self.detail_date_label.setText(self._tr(
            f"📅 Session: {date_str}  —  "
            f"{len(data['targets'])} target(s), "
            f"{data['frames']} frames",
            f"📅 Session : {date_str}  —  "
            f"{len(data['targets'])} cible(s), "
            f"{data['frames']} images"
        ))

        # Table
        details = data['details']
        self.details_table.setRowCount(len(details))

        total_frames = 0
        total_exposure = 0.0

        for i, d in enumerate(details):
            frames = d.get('frames', 0)
            exposure = d.get('exposure', 0.0)
            total_frames += frames
            total_exposure += exposure

            items = [
                d.get('target', ''),
                prettify_filter_name(d.get('filter', '')),
                str(frames),
                self._format_time(exposure),
                f"{d['hfr']:.2f}" if d.get('hfr') else "-",
                f"{d['fwhm']:.2f}" if d.get('fwhm') else "-",
                d.get('telescope', ''),
            ]

            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                # Color target name column
                if col == 0:
                    item.setForeground(QColor(COLORS['accent_cyan']))
                # Color filter column
                elif col == 1:
                    item.setForeground(QColor(COLORS['accent_purple']))
                self.details_table.setItem(i, col, item)

        # Totals row
        self.detail_totals_label.setText(self._tr(
            f"Total:  {total_frames} frames  •  "
            f"{self._format_time(total_exposure)} integration",
            f"Total :  {total_frames} images  •  "
            f"{self._format_time(total_exposure)} d'intégration"
        ))

        self.date_selected.emit(date_str)

    # ────────────────────────────────────────────────────────────────────
    # Navigation Handlers
    # ────────────────────────────────────────────────────────────────────

    def _prev_month(self):
        """Navigate to the previous month."""
        if self._current_month == 1:
            self._current_month = 12
            self._current_year -= 1
            self.year_spin.blockSignals(True)
            self.year_spin.setValue(self._current_year)
            self.year_spin.blockSignals(False)
            self._load_year_data()
        else:
            self._current_month -= 1
            self._update_monthly_view()

    def _next_month(self):
        """Navigate to the next month."""
        if self._current_month == 12:
            self._current_month = 1
            self._current_year += 1
            self.year_spin.blockSignals(True)
            self.year_spin.setValue(self._current_year)
            self.year_spin.blockSignals(False)
            self._load_year_data()
        else:
            self._current_month += 1
            self._update_monthly_view()

    def _prev_year(self):
        """Navigate to the previous year."""
        self._current_year -= 1
        self.year_spin.blockSignals(True)
        self.year_spin.setValue(self._current_year)
        self.year_spin.blockSignals(False)
        self._load_year_data()

    def _next_year(self):
        """Navigate to the next year."""
        self._current_year += 1
        self.year_spin.blockSignals(True)
        self.year_spin.setValue(self._current_year)
        self.year_spin.blockSignals(False)
        self._load_year_data()

    def _go_today(self):
        """Jump to the current month and year."""
        now = datetime.now()
        year_changed = self._current_year != now.year
        self._current_year = now.year
        self._current_month = now.month
        self.year_spin.blockSignals(True)
        self.year_spin.setValue(self._current_year)
        self.year_spin.blockSignals(False)
        if year_changed:
            self._load_year_data()
        else:
            self._update_monthly_view()

    def _on_year_changed(self, year: int):
        """Handle year spinbox change."""
        if year != self._current_year:
            self._current_year = year
            self._load_year_data()

    def _on_view_toggled(self, checked: bool):
        """Toggle between monthly and yearly view."""
        if self.view_monthly_rb.isChecked():
            self.view_stack.setCurrentIndex(0)
            self._update_monthly_view()
            # Show month navigation
            self.prev_month_btn.setVisible(True)
            self.next_month_btn.setVisible(True)
        else:
            self.view_stack.setCurrentIndex(1)
            self._update_yearly_view()
            # Hide month navigation in yearly mode
            self.prev_month_btn.setVisible(True)
            self.next_month_btn.setVisible(True)

    def _on_color_by_changed(self, _index: int):
        """Handle color-by metric change."""
        self._update_monthly_view()
        if self.view_stack.currentIndex() == 1:
            self._update_yearly_view()

    def _on_day_clicked(self, date_str: str):
        """Handle click on a day cell."""
        self._show_day_details(date_str)

    # ────────────────────────────────────────────────────────────────────
    # Export
    # ────────────────────────────────────────────────────────────────────

    def _export_png(self):
        """Export the current view as a PNG image."""
        default_name = (f"shoot_calendar_{self._current_year}"
                        f"_{self._current_month:02d}.png")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("Export Calendar as PNG",
                      "Exporter le Calendrier en PNG"),
            default_name,
            "PNG Images (*.png)"
        )
        if not file_path:
            return

        try:
            if self.view_stack.currentIndex() == 1 and self._has_matplotlib:
                # Save matplotlib figure directly
                self._fig.savefig(
                    file_path, dpi=150,
                    facecolor=COLORS['bg_dark'],
                    bbox_inches='tight')
            else:
                # Grab the monthly widget as pixmap
                target_widget = self.monthly_widget
                pixmap = target_widget.grab()
                pixmap.save(file_path, "PNG")

            logger.info(f"Calendar exported to {file_path}")
            signals.status_message.emit(
                self._tr(f"Calendar exported to {file_path}",
                         f"Calendrier exporté vers {file_path}"),
                5000)
        except Exception as e:
            logger.error(f"Failed to export calendar: {e}")
            signals.error_occurred.emit(
                self._tr("Export Error", "Erreur d'Export"),
                str(e))

    # ────────────────────────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────────────────────────

    def refresh(self):
        """Public refresh method — reload all data."""
        self._load_year_data()

    def navigate_to_date(self, date_str: str):
        """Navigate the calendar to show a specific date and select it.

        Parameters
        ----------
        date_str : str
            ISO date string (YYYY-MM-DD).
        """
        try:
            d = date.fromisoformat(date_str)
        except ValueError:
            return

        year_changed = d.year != self._current_year
        self._current_year = d.year
        self._current_month = d.month

        self.year_spin.blockSignals(True)
        self.year_spin.setValue(self._current_year)
        self.year_spin.blockSignals(False)

        if year_changed:
            self._load_year_data()
        else:
            self._update_monthly_view()

        # Auto-select the day if it has data
        if date_str in self._year_data:
            self._show_day_details(date_str)
