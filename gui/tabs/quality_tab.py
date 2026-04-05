#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - FRAME QUALITY TAB
================================================================================
Per-frame quality analysis with star detection, PSF fitting, scoring, and
batch statistics. Provides interactive results table, distribution charts,
star map visualization, and export capabilities.
================================================================================
"""

import csv
import logging
import math
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox,
    QPushButton, QLabel, QLineEdit, QFileDialog, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QProgressBar, QSplitter, QFrame, QMenu, QDialog,
    QDialogButtonBox, QSizePolicy, QGridLayout, QScrollArea,
    QApplication, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QBrush, QPainter, QPen

from core.config import get_config
from core.i18n import get_lang
from core.signals import signals
from gui.theme import COLORS, get_mono_font

logger = logging.getLogger(__name__)

# Supported file extensions (must match quality_analysis module)
_SUPPORTED_EXTENSIONS = ('.fits', '.fit', '.fts', '.fits.fz', '.fz', '.xisf')

# Score color thresholds
_SCORE_COLORS = {
    'excellent': '#88b098',   # score >= 80 — success green
    'good':      '#94b8c8',   # score 60-79 — accent cyan
    'mediocre':  '#b8a880',   # score 40-59 — warning tan
    'poor':      '#b89090',   # score 20-39 — error coral
    'bad':       '#b89090',   # score < 20  — error coral bold
}

# Row background tints (low alpha for subtle coloring)
_ROW_GOOD = QColor(136, 176, 152, 30)       # green tint
_ROW_MEDIOCRE = QColor(184, 168, 128, 25)   # tan tint
_ROW_BAD = QColor(184, 144, 144, 30)        # coral tint


def _score_color(score: float) -> str:
    """Return hex color for a quality score value."""
    if score >= 80:
        return _SCORE_COLORS['excellent']
    elif score >= 60:
        return _SCORE_COLORS['good']
    elif score >= 40:
        return _SCORE_COLORS['mediocre']
    elif score >= 20:
        return _SCORE_COLORS['poor']
    return _SCORE_COLORS['bad']


def _score_row_bg(score: float) -> Optional[QColor]:
    """Return row background tint for a quality score."""
    if score >= 70:
        return _ROW_GOOD
    elif score >= 30:
        return _ROW_MEDIOCRE
    return _ROW_BAD


def _collect_files(folder: str) -> List[str]:
    """Recursively collect supported image files from a folder."""
    files = []
    folder_path = Path(folder)
    if not folder_path.is_dir():
        return files
    for root, dirs, filenames in os.walk(folder):
        # Skip known analysis/extraction folders
        base = os.path.basename(root).lower()
        if any(base.startswith(p) for p in ('extracted_', 'duplicates_', 'astronomical_analysis_')):
            continue
        for fn in sorted(filenames):
            fn_lower = fn.lower()
            if any(fn_lower.endswith(ext) for ext in _SUPPORTED_EXTENSIONS):
                files.append(os.path.join(root, fn))
    return files


# ============================================================================
# Analysis Worker (QThread)
# ============================================================================

class _AnalysisWorker(QThread):
    """Background worker for batch frame quality analysis."""

    # Signals
    progress = pyqtSignal(int, int, str)        # current, total, filename
    frame_result = pyqtSignal(object)            # FrameQualityResult
    finished = pyqtSignal(list)                  # all results
    error = pyqtSignal(str)                      # error message

    def __init__(self, filepaths: List[str], max_stars: int = 500, parent=None):
        super().__init__(parent)
        self.filepaths = filepaths
        self.max_stars = max_stars
        self._stop_requested = False

    def stop(self):
        """Request graceful stop of the analysis loop."""
        self._stop_requested = True

    def run(self):
        """Execute frame-by-frame analysis in this thread."""
        try:
            from modules.quality_analysis import analyze_frame
        except ImportError as e:
            self.error.emit(f"Import error: {e}")
            return

        results = []
        total = len(self.filepaths)

        for i, fp in enumerate(self.filepaths):
            if self._stop_requested:
                break

            filename = os.path.basename(fp)
            self.progress.emit(i + 1, total, filename)

            try:
                result = analyze_frame(fp, max_stars=self.max_stars)
            except Exception as e:
                # Build a minimal error result
                from modules.quality_analysis import FrameQualityResult
                result = FrameQualityResult(
                    filepath=fp, star_count=0,
                    fwhm_median=0.0, fwhm_std=0.0, hfr_median=0.0,
                    eccentricity_median=0.0, snr_median=0.0,
                    background_level=0.0, background_noise=0.0,
                    trailing_detected=False, quality_score=0.0,
                    rejection_flag=True,
                    rejection_reasons=[f"Exception: {e}"],
                    stars=[], plate_scale=0.0, analysis_time_ms=0.0,
                    error=str(e),
                )

            results.append(result)
            self.frame_result.emit(result)

        self.finished.emit(results)


# ============================================================================
# StatCard Widget
# ============================================================================

class _StatCard(QFrame):
    """Compact statistics card with label, value, and optional sub-text."""

    def __init__(self, title: str, value: str = "—", subtitle: str = "",
                 accent_color: str = COLORS['accent_cyan'], parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            _StatCard {{
                background-color: {COLORS['bg_medium']};
                border: 1px solid {COLORS['border']};
                border-left: 3px solid {accent_color};
                border-radius: 6px;
                padding: 6px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(64)
        self.setMaximumHeight(80)

        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(8, 4, 8, 4)

        self._title_lbl = QLabel(title)
        self._title_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 8pt;")
        layout.addWidget(self._title_lbl)

        self._value_lbl = QLabel(value)
        self._value_lbl.setStyleSheet(
            f"color: {accent_color}; font-size: 14pt; font-weight: bold;"
        )
        layout.addWidget(self._value_lbl)

        self._sub_lbl = QLabel(subtitle)
        self._sub_lbl.setStyleSheet(f"color: {COLORS['text_disabled']}; font-size: 7pt;")
        if not subtitle:
            self._sub_lbl.hide()
        layout.addWidget(self._sub_lbl)

    def set_value(self, value: str, subtitle: str = ""):
        self._value_lbl.setText(value)
        if subtitle:
            self._sub_lbl.setText(subtitle)
            self._sub_lbl.show()

    def set_color(self, color: str):
        self._value_lbl.setStyleSheet(
            f"color: {color}; font-size: 14pt; font-weight: bold;"
        )


# ============================================================================
# Star Map Dialog
# ============================================================================

class _StarMapDialog(QDialog):
    """Dialog showing detected stars plotted on a dark canvas."""

    def __init__(self, result, lang: str = 'en', parent=None):
        super().__init__(parent)
        self.result = result
        self.lang = lang
        self._color_mode = 'eccentricity'  # or 'fwhm'
        self.setWindowTitle(self._tr(
            f"Star Map — {os.path.basename(result.filepath)}",
            f"Carte des Etoiles — {os.path.basename(result.filepath)}"
        ))
        self.setMinimumSize(700, 600)
        self.resize(800, 700)
        self._init_ui()

    def _tr(self, en, fr):
        return fr if self.lang == 'fr' else en

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Controls
        ctrl = QHBoxLayout()
        lbl = QLabel(self._tr("Color by:", "Colorer par :"))
        lbl.setToolTip(self._tr(
            "Choose which metric to use for star color coding",
            "Choisir la metrique pour le code couleur des etoiles"
        ))
        ctrl.addWidget(lbl)

        self.btn_ecc = QPushButton(self._tr("Eccentricity", "Excentricite"))
        self.btn_ecc.setToolTip(self._tr(
            "Color stars by eccentricity (roundness deviation)",
            "Colorer les etoiles par excentricite (deviation de rondeur)"
        ))
        self.btn_ecc.setCheckable(True)
        self.btn_ecc.setChecked(True)
        self.btn_ecc.clicked.connect(lambda: self._set_color_mode('eccentricity'))
        ctrl.addWidget(self.btn_ecc)

        self.btn_fwhm = QPushButton("FWHM")
        self.btn_fwhm.setToolTip(self._tr(
            "Color stars by FWHM (Full Width at Half Maximum)",
            "Colorer les etoiles par FWHM (largeur a mi-hauteur)"
        ))
        self.btn_fwhm.setCheckable(True)
        self.btn_fwhm.clicked.connect(lambda: self._set_color_mode('fwhm'))
        ctrl.addWidget(self.btn_fwhm)

        ctrl.addStretch()

        info_lbl = QLabel(self._tr(
            f"Stars: {self.result.star_count} | Score: {self.result.quality_score:.1f}",
            f"Etoiles : {self.result.star_count} | Score : {self.result.quality_score:.1f}"
        ))
        info_lbl.setToolTip(self._tr(
            "Number of detected stars and overall quality score",
            "Nombre d'etoiles detectees et score de qualite global"
        ))
        info_lbl.setStyleSheet(f"color: {COLORS['accent_cyan']};")
        ctrl.addWidget(info_lbl)
        layout.addLayout(ctrl)

        # Canvas for star map
        self._canvas = _StarMapCanvas(self.result, self._color_mode)
        layout.addWidget(self._canvas, stretch=1)

        # Legend
        legend = QLabel()
        legend.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 8pt;")
        legend.setText(self._tr(
            "Circle size = flux | Line = elongation direction | Color = metric value (blue=good, red=poor)",
            "Taille cercle = flux | Ligne = direction d'elongation | Couleur = valeur metrique (bleu=bon, rouge=mauvais)"
        ))
        legend.setToolTip(self._tr(
            "How to read the star map visualization",
            "Comment lire la visualisation de la carte des etoiles"
        ))
        layout.addWidget(legend)

        # Close button
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_color_mode(self, mode: str):
        self._color_mode = mode
        self.btn_ecc.setChecked(mode == 'eccentricity')
        self.btn_fwhm.setChecked(mode == 'fwhm')
        self._canvas.set_color_mode(mode)


class _StarMapCanvas(QWidget):
    """Custom paint widget rendering stars as annotated circles."""

    def __init__(self, result, color_mode: str = 'eccentricity', parent=None):
        super().__init__(parent)
        self.result = result
        self._color_mode = color_mode
        self.setMinimumSize(400, 400)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Determine image bounds from star positions
        self._img_w = 1.0
        self._img_h = 1.0
        if result.stars:
            max_x = max(s.x for s in result.stars)
            max_y = max(s.y for s in result.stars)
            self._img_w = max(max_x + 50, 100)
            self._img_h = max(max_y + 50, 100)

    def set_color_mode(self, mode: str):
        self._color_mode = mode
        self.update()

    def paintEvent(self, event):
        """Render star positions as colored annotated circles."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Dark background
        painter.fillRect(0, 0, w, h, QColor(COLORS['bg_darkest']))

        stars = self.result.stars
        if not stars:
            painter.setPen(QColor(COLORS['text_disabled']))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "No stars detected"
            )
            painter.end()
            return

        # Scale factors
        margin = 20
        sx = (w - 2 * margin) / self._img_w
        sy = (h - 2 * margin) / self._img_h
        scale = min(sx, sy)

        # Collect metric values for normalization
        if self._color_mode == 'eccentricity':
            values = [s.eccentricity for s in stars]
        else:
            values = [s.fwhm for s in stars]

        v_min = min(values) if values else 0
        v_max = max(values) if values else 1
        v_range = max(v_max - v_min, 0.001)

        # Flux range for circle sizing
        fluxes = [s.flux for s in stars]
        f_min = min(fluxes) if fluxes else 0
        f_max = max(fluxes) if fluxes else 1
        f_range = max(f_max - f_min, 1.0)

        for star in stars:
            px = margin + star.x * scale
            py = margin + star.y * scale

            # Normalized metric value: 0 = good (blue), 1 = bad (red)
            if self._color_mode == 'eccentricity':
                t = min(1.0, max(0.0, (star.eccentricity - v_min) / v_range))
            else:
                t = min(1.0, max(0.0, (star.fwhm - v_min) / v_range))

            # Color interpolation: cyan (#94b8c8) -> coral (#b89090)
            r_c = int(148 + t * (184 - 148))
            g_c = int(184 + t * (144 - 184))
            b_c = int(200 + t * (144 - 200))
            color = QColor(r_c, g_c, b_c, 200)

            # Circle radius from flux (3 to 12 px)
            flux_t = (star.flux - f_min) / f_range
            radius = 3 + flux_t * 9

            # Draw circle
            painter.setPen(QPen(color, 1.5))
            painter.setBrush(QColor(r_c, g_c, b_c, 60))
            painter.drawEllipse(int(px - radius), int(py - radius),
                                int(2 * radius), int(2 * radius))

            # Elongation direction tick (line showing theta angle)
            if star.eccentricity > 0.2:
                theta_rad = math.radians(star.theta)
                tick_len = radius + 4
                dx = math.cos(theta_rad) * tick_len
                dy = math.sin(theta_rad) * tick_len
                painter.setPen(QPen(QColor(r_c, g_c, b_c, 140), 1.0))
                painter.drawLine(int(px - dx), int(py - dy),
                                 int(px + dx), int(py + dy))

        painter.end()


# ============================================================================
# Quality Tab
# ============================================================================

class QualityTab(QWidget):
    """Frame Quality Analysis tab — PSF fitting, scoring, batch statistics."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self.lang = get_lang()
        self._worker: Optional[_AnalysisWorker] = None
        self._results: List = []
        self._files: List[str] = []
        self._start_time: float = 0.0
        self._init_ui()
        self._connect_signals()

    def _tr(self, en: str, fr: str) -> str:
        """Simple bilingual translation helper."""
        return fr if self.lang == 'fr' else en

    # -----------------------------------------------------------------------
    # UI Setup
    # -----------------------------------------------------------------------

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # ── Control Panel (top) ──
        ctrl_group = QGroupBox(self._tr(
            "Control Panel", "Panneau de Controle"
        ))
        ctrl_group.setToolTip(self._tr(
            "Configure and launch frame quality analysis",
            "Configurer et lancer l'analyse de qualite des frames"
        ))
        ctrl_layout = QVBoxLayout(ctrl_group)

        # Row 1: folder selection
        row1 = QHBoxLayout()
        self.browse_btn = QPushButton(self._tr("Browse...", "Parcourir..."))
        self.browse_btn.setToolTip(self._tr(
            "Select a folder containing FITS/XISF files to analyze",
            "Selectionner un dossier contenant des fichiers FITS/XISF a analyser"
        ))
        self.browse_btn.setProperty("accent", True)
        self.browse_btn.clicked.connect(self._browse_folder)
        row1.addWidget(self.browse_btn)

        self.path_label = QLineEdit()
        self.path_label.setReadOnly(True)
        self.path_label.setPlaceholderText(self._tr(
            "No folder selected...", "Aucun dossier selectionne..."
        ))
        self.path_label.setToolTip(self._tr(
            "Path to the folder being analyzed",
            "Chemin vers le dossier en cours d'analyse"
        ))
        row1.addWidget(self.path_label, stretch=1)

        self.file_counter = QLabel(self._tr("0 files", "0 fichiers"))
        self.file_counter.setToolTip(self._tr(
            "Number of supported image files found in the selected folder",
            "Nombre de fichiers image compatibles trouves dans le dossier selectionne"
        ))
        self.file_counter.setStyleSheet(f"color: {COLORS['text_secondary']};")
        row1.addWidget(self.file_counter)
        ctrl_layout.addLayout(row1)

        # Row 2: options + actions
        row2 = QHBoxLayout()

        lbl_stars = QLabel(self._tr("Max stars:", "Max etoiles :"))
        lbl_stars.setToolTip(self._tr(
            "Maximum number of stars to detect per frame (higher = slower but more precise)",
            "Nombre maximum d'etoiles a detecter par frame (plus = plus lent mais plus precis)"
        ))
        row2.addWidget(lbl_stars)

        self.spin_max_stars = QSpinBox()
        self.spin_max_stars.setRange(50, 5000)
        self.spin_max_stars.setValue(500)
        self.spin_max_stars.setSingleStep(50)
        self.spin_max_stars.setToolTip(self._tr(
            "Maximum stars per frame for PSF fitting (default: 500)",
            "Maximum d'etoiles par frame pour le fitting PSF (defaut : 500)"
        ))
        row2.addWidget(self.spin_max_stars)

        self.cb_include_rejected = QCheckBox(self._tr(
            "Include rejected in export", "Inclure les rejetees dans l'export"
        ))
        self.cb_include_rejected.setToolTip(self._tr(
            "When checked, rejected frames will be included in CSV/file list exports",
            "Si coche, les frames rejetees seront incluses dans les exports CSV/liste"
        ))
        row2.addWidget(self.cb_include_rejected)

        row2.addStretch()

        self.analyze_btn = QPushButton(self._tr("Analyze", "Analyser"))
        self.analyze_btn.setToolTip(self._tr(
            "Start batch quality analysis on all files in the selected folder",
            "Demarrer l'analyse de qualite par lot sur tous les fichiers du dossier selectionne"
        ))
        self.analyze_btn.setProperty("accent", True)
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.clicked.connect(self._start_analysis)
        row2.addWidget(self.analyze_btn)

        self.stop_btn = QPushButton(self._tr("Stop", "Arreter"))
        self.stop_btn.setToolTip(self._tr(
            "Stop the current analysis (already completed frames are kept)",
            "Arreter l'analyse en cours (les frames deja analysees sont conservees)"
        ))
        self.stop_btn.setProperty("danger", True)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_analysis)
        row2.addWidget(self.stop_btn)
        ctrl_layout.addLayout(row2)

        # Row 3: progress bar
        row3 = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setToolTip(self._tr(
            "Analysis progress with estimated time remaining",
            "Progression de l'analyse avec temps restant estime"
        ))
        row3.addWidget(self.progress_bar, stretch=1)

        self.eta_label = QLabel("")
        self.eta_label.setToolTip(self._tr(
            "Estimated time remaining for analysis completion",
            "Temps restant estime pour la fin de l'analyse"
        ))
        self.eta_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        self.eta_label.setMinimumWidth(120)
        row3.addWidget(self.eta_label)
        ctrl_layout.addLayout(row3)

        main_layout.addWidget(ctrl_group)

        # ── Main splitter: Table (left) + Stats (right) ──
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setToolTip(self._tr(
            "Drag to resize results table and statistics panel",
            "Glisser pour redimensionner le tableau des resultats et le panneau de statistiques"
        ))

        # Left: Results table
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(4)

        self.results_table = QTableWidget()
        self.results_table.setToolTip(self._tr(
            "Quality analysis results — double-click for star map, right-click for options",
            "Resultats d'analyse de qualite — double-clic pour la carte des etoiles, clic-droit pour les options"
        ))
        self._setup_table()
        table_layout.addWidget(self.results_table, stretch=1)

        # Batch summary panel (below table)
        self.summary_group = QGroupBox(self._tr(
            "Batch Summary", "Resume du Lot"
        ))
        self.summary_group.setToolTip(self._tr(
            "Summary statistics and export options after analysis completes",
            "Statistiques resumees et options d'export apres la fin de l'analyse"
        ))
        summary_layout = QVBoxLayout(self.summary_group)

        self.summary_label = QLabel(self._tr(
            "Run an analysis to see the batch summary.",
            "Lancez une analyse pour voir le resume du lot."
        ))
        self.summary_label.setToolTip(self._tr(
            "Overview of batch analysis results",
            "Apercu des resultats d'analyse du lot"
        ))
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        summary_layout.addWidget(self.summary_label)

        btn_row = QHBoxLayout()
        self.btn_export_accepted = QPushButton(self._tr(
            "Export Accepted List", "Exporter Liste Acceptees"
        ))
        self.btn_export_accepted.setToolTip(self._tr(
            "Save a text file listing all accepted frame file paths",
            "Enregistrer un fichier texte listant les chemins de toutes les frames acceptees"
        ))
        self.btn_export_accepted.setEnabled(False)
        self.btn_export_accepted.clicked.connect(self._export_accepted_list)
        btn_row.addWidget(self.btn_export_accepted)

        self.btn_export_csv = QPushButton(self._tr(
            "Export Report (CSV)", "Exporter Rapport (CSV)"
        ))
        self.btn_export_csv.setToolTip(self._tr(
            "Export all frame metrics as a CSV file for external analysis",
            "Exporter toutes les metriques des frames en fichier CSV pour analyse externe"
        ))
        self.btn_export_csv.setEnabled(False)
        self.btn_export_csv.clicked.connect(self._export_csv)
        btn_row.addWidget(self.btn_export_csv)

        btn_row.addStretch()
        summary_layout.addLayout(btn_row)
        self.summary_group.setMaximumHeight(140)
        table_layout.addWidget(self.summary_group)

        splitter.addWidget(table_container)

        # Right: Statistics panel
        stats_container = QWidget()
        stats_layout = QVBoxLayout(stats_container)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(6)

        # StatCards (2 columns x 3 rows)
        cards_grid = QGridLayout()
        cards_grid.setSpacing(4)

        self.card_total = _StatCard(
            self._tr("Total Frames", "Frames Totales"),
            accent_color=COLORS['accent_cyan']
        )
        self.card_total.setToolTip(self._tr(
            "Total number of frames analyzed in the batch",
            "Nombre total de frames analysees dans le lot"
        ))
        cards_grid.addWidget(self.card_total, 0, 0)

        self.card_accepted = _StatCard(
            self._tr("Accepted", "Acceptees"),
            accent_color=COLORS['success']
        )
        self.card_accepted.setToolTip(self._tr(
            "Number of frames that passed quality criteria",
            "Nombre de frames ayant passe les criteres de qualite"
        ))
        cards_grid.addWidget(self.card_accepted, 0, 1)

        self.card_rejected = _StatCard(
            self._tr("Rejected", "Rejetees"),
            accent_color=COLORS['error']
        )
        self.card_rejected.setToolTip(self._tr(
            "Number of frames flagged for rejection",
            "Nombre de frames signalees pour rejet"
        ))
        cards_grid.addWidget(self.card_rejected, 1, 0)

        self.card_fwhm = _StatCard(
            self._tr("Median FWHM", "FWHM Mediane"),
            accent_color=COLORS['accent_purple']
        )
        self.card_fwhm.setToolTip(self._tr(
            "Median Full Width at Half Maximum across all frames (in pixels)",
            "Largeur a mi-hauteur mediane sur toutes les frames (en pixels)"
        ))
        cards_grid.addWidget(self.card_fwhm, 1, 1)

        self.card_ecc = _StatCard(
            self._tr("Median Ecc.", "Ecc. Mediane"),
            accent_color=COLORS['accent_orange']
        )
        self.card_ecc.setToolTip(self._tr(
            "Median eccentricity across all frames (0 = perfect circle, 1 = line)",
            "Excentricite mediane sur toutes les frames (0 = cercle parfait, 1 = ligne)"
        ))
        cards_grid.addWidget(self.card_ecc, 2, 0)

        self.card_score = _StatCard(
            self._tr("Median Score", "Score Median"),
            accent_color=COLORS['accent_yellow']
        )
        self.card_score.setToolTip(self._tr(
            "Median quality score across all frames (0-100 scale)",
            "Score de qualite median sur toutes les frames (echelle 0-100)"
        ))
        cards_grid.addWidget(self.card_score, 2, 1)

        stats_layout.addLayout(cards_grid)

        # Charts area (2x2 grid with matplotlib)
        self._charts_container = QWidget()
        self._charts_layout = QGridLayout(self._charts_container)
        self._charts_layout.setSpacing(4)
        self._charts_layout.setContentsMargins(0, 0, 0, 0)

        # Placeholder label until charts are drawn
        self._charts_placeholder = QLabel(self._tr(
            "Charts will appear after analysis.",
            "Les graphiques apparaitront apres l'analyse."
        ))
        self._charts_placeholder.setToolTip(self._tr(
            "Distribution charts for FWHM, quality scores, eccentricity, and trends",
            "Graphiques de distribution pour FWHM, scores de qualite, excentricite et tendances"
        ))
        self._charts_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._charts_placeholder.setStyleSheet(f"color: {COLORS['text_disabled']};")
        self._charts_layout.addWidget(self._charts_placeholder, 0, 0, 2, 2)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._charts_container)
        scroll.setToolTip(self._tr(
            "Scroll to view all distribution charts",
            "Defiler pour voir tous les graphiques de distribution"
        ))
        stats_layout.addWidget(scroll, stretch=1)

        splitter.addWidget(stats_container)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter, stretch=1)

    def _setup_table(self):
        """Configure the results table columns and behavior."""
        columns = [
            self._tr("Filename", "Fichier"),
            self._tr("Score", "Score"),
            self._tr("FWHM (px)", "FWHM (px)"),
            "HFR",
            self._tr("Eccentricity", "Excentricite"),
            "SNR",
            self._tr("Stars", "Etoiles"),
            self._tr("Background", "Fond"),
            self._tr("Trailing?", "Trainee ?"),
            self._tr("Rejected?", "Rejetee ?"),
            self._tr("Rejection Reasons", "Raisons de Rejet"),
            self._tr("Time (ms)", "Temps (ms)"),
        ]
        self.results_table.setColumnCount(len(columns))
        self.results_table.setHorizontalHeaderLabels(columns)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setSortingEnabled(True)
        self.results_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_table.customContextMenuRequested.connect(self._show_context_menu)
        self.results_table.doubleClicked.connect(self._on_row_double_click)

        hdr = self.results_table.horizontalHeader()
        hdr.setStretchLastSection(True)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(columns)):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        # Column tooltips
        col_tips = [
            self._tr("File name of the analyzed frame", "Nom du fichier de la frame analysee"),
            self._tr("Overall quality score (0-100)", "Score de qualite global (0-100)"),
            self._tr("Median FWHM in pixels", "FWHM mediane en pixels"),
            self._tr("Median Half-Flux Radius in pixels", "Rayon de demi-flux median en pixels"),
            self._tr("Median star eccentricity (0=round, 1=elongated)",
                      "Excentricite mediane des etoiles (0=ronde, 1=allongee)"),
            self._tr("Median signal-to-noise ratio", "Rapport signal-sur-bruit median"),
            self._tr("Number of stars detected", "Nombre d'etoiles detectees"),
            self._tr("Background level +/- noise", "Niveau de fond +/- bruit"),
            self._tr("Satellite trail detected?", "Trainee de satellite detectee ?"),
            self._tr("Frame flagged for rejection?", "Frame signalee pour rejet ?"),
            self._tr("Reasons for rejection (if any)", "Raisons du rejet (le cas echeant)"),
            self._tr("Analysis time in milliseconds", "Temps d'analyse en millisecondes"),
        ]
        for i, tip in enumerate(col_tips):
            item = self.results_table.horizontalHeaderItem(i)
            if item:
                item.setToolTip(tip)

    def _connect_signals(self):
        """Connect global signal bus if needed."""
        pass

    # -----------------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------------

    def _browse_folder(self):
        """Open folder dialog and scan for image files."""
        last_dir = self.config.get('quality.last_folder', '')
        folder = QFileDialog.getExistingDirectory(
            self,
            self._tr("Select Image Folder", "Selectionner le Dossier d'Images"),
            last_dir
        )
        if not folder:
            return

        self.path_label.setText(folder)
        self.config.set('quality.last_folder', folder)

        # Scan for files
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._files = _collect_files(folder)
        finally:
            QApplication.restoreOverrideCursor()

        count = len(self._files)
        self.file_counter.setText(
            self._tr(f"{count} files", f"{count} fichiers")
        )
        self.analyze_btn.setEnabled(count > 0)

        # Reset previous results
        self._results.clear()
        self.results_table.setRowCount(0)
        self._reset_stats()

    def _start_analysis(self):
        """Launch the analysis worker thread."""
        if not self._files:
            return

        if self._worker is not None and self._worker.isRunning():
            return

        # Prepare UI
        self.analyze_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.browse_btn.setEnabled(False)
        self.btn_export_accepted.setEnabled(False)
        self.btn_export_csv.setEnabled(False)
        self.progress_bar.setRange(0, len(self._files))
        self.progress_bar.setValue(0)
        self.eta_label.setText("")
        self._results.clear()
        self.results_table.setSortingEnabled(False)
        self.results_table.setRowCount(0)
        self._reset_stats()
        self._start_time = time.perf_counter()

        # Start worker
        max_stars = self.spin_max_stars.value()
        self._worker = _AnalysisWorker(self._files, max_stars=max_stars, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.frame_result.connect(self._on_frame_result)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _stop_analysis(self):
        """Request the worker to stop."""
        if self._worker is not None:
            self._worker.stop()
            self.stop_btn.setEnabled(False)
            self.eta_label.setText(self._tr("Stopping...", "Arret en cours..."))

    # -----------------------------------------------------------------------
    # Worker callbacks (run on main thread via signals)
    # -----------------------------------------------------------------------

    def _on_progress(self, current: int, total: int, filename: str):
        """Update progress bar and ETA."""
        self.progress_bar.setValue(current)
        self.file_counter.setText(
            self._tr(f"{current} / {total} files", f"{current} / {total} fichiers")
        )

        # ETA calculation
        elapsed = time.perf_counter() - self._start_time
        if current > 0:
            per_frame = elapsed / current
            remaining = per_frame * (total - current)
            if remaining >= 60:
                eta_str = f"ETA: {remaining / 60:.1f} min"
            else:
                eta_str = f"ETA: {remaining:.0f} s"
            self.eta_label.setText(eta_str)

    def _on_frame_result(self, result):
        """Add a single frame result to the table."""
        self._results.append(result)
        self._add_table_row(result)

    def _on_finished(self, results: list):
        """Analysis complete — update stats and charts."""
        self._results = results
        self.analyze_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.browse_btn.setEnabled(True)
        self.btn_export_accepted.setEnabled(len(results) > 0)
        self.btn_export_csv.setEnabled(len(results) > 0)
        self.results_table.setSortingEnabled(True)

        elapsed = time.perf_counter() - self._start_time
        if elapsed >= 60:
            time_str = f"{elapsed / 60:.1f} min"
        else:
            time_str = f"{elapsed:.1f} s"

        self.eta_label.setText(self._tr(
            f"Done in {time_str}", f"Termine en {time_str}"
        ))

        self._update_stats(results)
        self._update_charts(results)
        self._update_summary(results)

    def _on_error(self, msg: str):
        """Handle worker-level error."""
        self.analyze_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.browse_btn.setEnabled(True)
        self.eta_label.setText(self._tr("Error!", "Erreur !"))
        logger.error("Quality analysis worker error: %s", msg)
        QMessageBox.warning(
            self,
            self._tr("Analysis Error", "Erreur d'Analyse"),
            msg
        )

    # -----------------------------------------------------------------------
    # Table management
    # -----------------------------------------------------------------------

    def _add_table_row(self, result):
        """Append a FrameQualityResult as a new table row."""
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)

        filename = os.path.basename(result.filepath)
        score = result.quality_score
        row_bg = _score_row_bg(score)

        # Column 0: Filename
        item_fn = QTableWidgetItem(filename)
        item_fn.setToolTip(result.filepath)
        item_fn.setData(Qt.ItemDataRole.UserRole, result)
        self.results_table.setItem(row, 0, item_fn)

        # Column 1: Score (with color)
        item_score = QTableWidgetItem()
        item_score.setData(Qt.ItemDataRole.DisplayRole, round(score, 1))
        item_score.setForeground(QBrush(QColor(_score_color(score))))
        if score < 20:
            font = item_score.font()
            font.setBold(True)
            item_score.setFont(font)
        item_score.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_table.setItem(row, 1, item_score)

        # Column 2: FWHM
        fwhm_str = f"{result.fwhm_median:.2f}"
        if result.plate_scale > 0:
            fwhm_arcsec = result.fwhm_median * result.plate_scale
            fwhm_str = f"{result.fwhm_median:.2f} ({fwhm_arcsec:.1f}\")"
        item_fwhm = QTableWidgetItem()
        item_fwhm.setData(Qt.ItemDataRole.DisplayRole, round(result.fwhm_median, 2))
        item_fwhm.setToolTip(fwhm_str)
        item_fwhm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_table.setItem(row, 2, item_fwhm)

        # Column 3: HFR
        item_hfr = QTableWidgetItem()
        item_hfr.setData(Qt.ItemDataRole.DisplayRole, round(result.hfr_median, 2))
        item_hfr.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_table.setItem(row, 3, item_hfr)

        # Column 4: Eccentricity
        item_ecc = QTableWidgetItem()
        item_ecc.setData(Qt.ItemDataRole.DisplayRole, round(result.eccentricity_median, 3))
        item_ecc.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_table.setItem(row, 4, item_ecc)

        # Column 5: SNR
        item_snr = QTableWidgetItem()
        item_snr.setData(Qt.ItemDataRole.DisplayRole, round(result.snr_median, 1))
        item_snr.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_table.setItem(row, 5, item_snr)

        # Column 6: Stars
        item_stars = QTableWidgetItem()
        item_stars.setData(Qt.ItemDataRole.DisplayRole, result.star_count)
        item_stars.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_table.setItem(row, 6, item_stars)

        # Column 7: Background
        bg_str = f"{result.background_level:.0f} \u00b1 {result.background_noise:.1f}"
        item_bg = QTableWidgetItem(bg_str)
        item_bg.setToolTip(self._tr(
            f"Background level: {result.background_level:.1f}, noise: {result.background_noise:.2f}",
            f"Niveau de fond : {result.background_level:.1f}, bruit : {result.background_noise:.2f}"
        ))
        item_bg.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_table.setItem(row, 7, item_bg)

        # Column 8: Trailing
        trail_str = self._tr("Yes", "Oui") if result.trailing_detected else ""
        item_trail = QTableWidgetItem(trail_str)
        if result.trailing_detected:
            item_trail.setForeground(QBrush(QColor(COLORS['warning'])))
        item_trail.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_table.setItem(row, 8, item_trail)

        # Column 9: Rejected
        rej_str = self._tr("REJECT", "REJET") if result.rejection_flag else ""
        item_rej = QTableWidgetItem(rej_str)
        if result.rejection_flag:
            item_rej.setForeground(QBrush(QColor(COLORS['error'])))
            font = item_rej.font()
            font.setBold(True)
            item_rej.setFont(font)
        item_rej.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_table.setItem(row, 9, item_rej)

        # Column 10: Rejection reasons
        reasons = ", ".join(result.rejection_reasons) if result.rejection_reasons else ""
        item_reasons = QTableWidgetItem(reasons)
        item_reasons.setToolTip(reasons if reasons else self._tr(
            "No rejection reasons", "Aucune raison de rejet"
        ))
        self.results_table.setItem(row, 10, item_reasons)

        # Column 11: Analysis time
        item_time = QTableWidgetItem()
        item_time.setData(Qt.ItemDataRole.DisplayRole, round(result.analysis_time_ms, 0))
        item_time.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_table.setItem(row, 11, item_time)

        # Apply row background tint
        if row_bg:
            for col in range(self.results_table.columnCount()):
                cell = self.results_table.item(row, col)
                if cell:
                    cell.setBackground(QBrush(row_bg))

    # -----------------------------------------------------------------------
    # Context menu
    # -----------------------------------------------------------------------

    def _show_context_menu(self, pos):
        """Show right-click context menu on the results table."""
        index = self.results_table.indexAt(pos)
        if not index.isValid():
            return

        row = index.row()
        item = self.results_table.item(row, 0)
        if item is None:
            return
        result = item.data(Qt.ItemDataRole.UserRole)
        if result is None:
            return

        menu = QMenu(self)

        # Toggle reject/accept
        if result.rejection_flag:
            action_toggle = menu.addAction(self._tr("Accept Frame", "Accepter la Frame"))
            action_toggle.setToolTip(self._tr(
                "Remove rejection flag from this frame",
                "Retirer le marqueur de rejet de cette frame"
            ))
        else:
            action_toggle = menu.addAction(self._tr("Reject Frame", "Rejeter la Frame"))
            action_toggle.setToolTip(self._tr(
                "Manually flag this frame for rejection",
                "Marquer manuellement cette frame pour rejet"
            ))
        action_toggle.triggered.connect(lambda: self._toggle_rejection(row, result))

        # Star map
        action_starmap = menu.addAction(self._tr("View Star Map", "Voir la Carte des Etoiles"))
        action_starmap.setToolTip(self._tr(
            "Open a visual map of detected stars in this frame",
            "Ouvrir une carte visuelle des etoiles detectees dans cette frame"
        ))
        action_starmap.triggered.connect(lambda: self._show_star_map(result))

        # Copy to clipboard
        action_copy = menu.addAction(self._tr(
            "Copy Metrics to Clipboard", "Copier les Metriques"
        ))
        action_copy.setToolTip(self._tr(
            "Copy this frame's metrics to the system clipboard",
            "Copier les metriques de cette frame dans le presse-papiers"
        ))
        action_copy.triggered.connect(lambda: self._copy_to_clipboard(result))

        menu.exec(self.results_table.viewport().mapToGlobal(pos))

    def _toggle_rejection(self, row: int, result):
        """Toggle the rejection flag on a frame result."""
        result.rejection_flag = not result.rejection_flag
        if result.rejection_flag:
            if "Manual rejection" not in result.rejection_reasons:
                result.rejection_reasons.append("Manual rejection")
        else:
            result.rejection_reasons = [
                r for r in result.rejection_reasons if r != "Manual rejection"
            ]

        # Update table row visuals
        rej_item = self.results_table.item(row, 9)
        if rej_item:
            if result.rejection_flag:
                rej_item.setText(self._tr("REJECT", "REJET"))
                rej_item.setForeground(QBrush(QColor(COLORS['error'])))
                font = rej_item.font()
                font.setBold(True)
                rej_item.setFont(font)
            else:
                rej_item.setText("")
                rej_item.setForeground(QBrush(QColor(COLORS['text_primary'])))

        reasons_item = self.results_table.item(row, 10)
        if reasons_item:
            reasons_item.setText(", ".join(result.rejection_reasons))

        # Update row background
        score = result.quality_score
        row_bg = _score_row_bg(score)
        if result.rejection_flag:
            row_bg = _ROW_BAD
        if row_bg:
            for col in range(self.results_table.columnCount()):
                cell = self.results_table.item(row, col)
                if cell:
                    cell.setBackground(QBrush(row_bg))

        # Refresh stats
        if self._results:
            self._update_stats(self._results)
            self._update_summary(self._results)

    def _on_row_double_click(self, index):
        """Open star map dialog on double-click."""
        row = index.row()
        item = self.results_table.item(row, 0)
        if item is None:
            return
        result = item.data(Qt.ItemDataRole.UserRole)
        if result is not None:
            self._show_star_map(result)

    def _show_star_map(self, result):
        """Display the star map dialog for a specific frame."""
        if not result.stars:
            QMessageBox.information(
                self,
                self._tr("No Stars", "Aucune Etoile"),
                self._tr(
                    "No stars were detected in this frame.",
                    "Aucune etoile n'a ete detectee dans cette frame."
                )
            )
            return
        dlg = _StarMapDialog(result, lang=self.lang, parent=self)
        dlg.exec()

    def _copy_to_clipboard(self, result):
        """Copy frame metrics to clipboard as text."""
        name = os.path.basename(result.filepath)
        ps_info = ""
        if result.plate_scale > 0:
            fwhm_arcsec = result.fwhm_median * result.plate_scale
            ps_info = f" ({fwhm_arcsec:.2f}\")"

        text = (
            f"File: {name}\n"
            f"Score: {result.quality_score:.1f}/100\n"
            f"Stars: {result.star_count}\n"
            f"FWHM: {result.fwhm_median:.2f} px{ps_info}\n"
            f"HFR: {result.hfr_median:.2f} px\n"
            f"Eccentricity: {result.eccentricity_median:.3f}\n"
            f"SNR: {result.snr_median:.1f}\n"
            f"Background: {result.background_level:.0f} +/- {result.background_noise:.1f}\n"
            f"Trailing: {'Yes' if result.trailing_detected else 'No'}\n"
            f"Rejected: {'Yes' if result.rejection_flag else 'No'}\n"
        )
        if result.rejection_reasons:
            text += f"Reasons: {', '.join(result.rejection_reasons)}\n"

        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    # -----------------------------------------------------------------------
    # Statistics
    # -----------------------------------------------------------------------

    def _reset_stats(self):
        """Reset all stat cards to default."""
        self.card_total.set_value("—")
        self.card_accepted.set_value("—")
        self.card_rejected.set_value("—")
        self.card_fwhm.set_value("—")
        self.card_ecc.set_value("—")
        self.card_score.set_value("—")

    def _update_stats(self, results: list):
        """Update stat cards from analysis results."""
        try:
            from modules.quality_analysis import get_batch_summary
            summary = get_batch_summary(results)
        except ImportError:
            return

        total = summary.get('total_frames', 0)
        analyzed = summary.get('analyzed_frames', 0)
        rejected = summary.get('rejected_frames', 0)
        accepted = total - rejected

        self.card_total.set_value(str(total), self._tr(
            f"{analyzed} analyzed", f"{analyzed} analysees"
        ))

        self.card_accepted.set_value(str(accepted))
        self.card_accepted.set_color(COLORS['success'] if accepted > 0 else COLORS['text_disabled'])

        self.card_rejected.set_value(str(rejected))
        self.card_rejected.set_color(COLORS['error'] if rejected > 0 else COLORS['text_disabled'])

        med_fwhm = summary.get('median_fwhm', 0)
        self.card_fwhm.set_value(f"{med_fwhm:.2f} px")

        med_ecc = summary.get('median_eccentricity', 0)
        self.card_ecc.set_value(f"{med_ecc:.3f}")

        med_score = summary.get('median_quality_score', summary.get('avg_quality_score', 0))
        self.card_score.set_value(f"{med_score:.1f}")
        self.card_score.set_color(_score_color(med_score))

    def _update_summary(self, results: list):
        """Update the batch summary panel text."""
        try:
            from modules.quality_analysis import get_batch_summary
            summary = get_batch_summary(results)
        except ImportError:
            return

        total = summary.get('total_frames', 0)
        rejected = summary.get('rejected_frames', 0)
        accepted = total - rejected
        avg_score = summary.get('avg_quality_score', 0)
        med_fwhm = summary.get('median_fwhm', 0)
        best = summary.get('best_frame')
        worst = summary.get('worst_frame')

        best_name = os.path.basename(best) if best else "N/A"
        worst_name = os.path.basename(worst) if worst else "N/A"
        best_score = summary.get('best_score', 0)
        worst_score = summary.get('worst_score', 0)

        text = self._tr(
            f"<b>{total}</b> frames analyzed — "
            f"<span style='color:{COLORS['success']}'><b>{accepted}</b> accepted</span>, "
            f"<span style='color:{COLORS['error']}'><b>{rejected}</b> recommended for rejection</span><br/>"
            f"Average score: <b>{avg_score:.1f}</b> | Median FWHM: <b>{med_fwhm:.2f}</b> px<br/>"
            f"Best: <b>{best_name}</b> ({best_score:.1f}) | "
            f"Worst: <b>{worst_name}</b> ({worst_score:.1f})",

            f"<b>{total}</b> frames analysees — "
            f"<span style='color:{COLORS['success']}'><b>{accepted}</b> acceptees</span>, "
            f"<span style='color:{COLORS['error']}'><b>{rejected}</b> recommandees pour rejet</span><br/>"
            f"Score moyen : <b>{avg_score:.1f}</b> | FWHM mediane : <b>{med_fwhm:.2f}</b> px<br/>"
            f"Meilleure : <b>{best_name}</b> ({best_score:.1f}) | "
            f"Pire : <b>{worst_name}</b> ({worst_score:.1f})"
        )
        self.summary_label.setText(text)

    # -----------------------------------------------------------------------
    # Charts (matplotlib embedded)
    # -----------------------------------------------------------------------

    def _update_charts(self, results: list):
        """Render the 4 distribution charts using matplotlib."""
        try:
            import matplotlib
            matplotlib.use('QtAgg')
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
        except ImportError:
            self._charts_placeholder.setText(self._tr(
                "matplotlib not available — install it for charts",
                "matplotlib non disponible — installez-le pour les graphiques"
            ))
            return

        # Filter valid results
        valid = [r for r in results if r.error is None and r.star_count > 0]
        if not valid:
            self._charts_placeholder.setText(self._tr(
                "No valid frames to chart.", "Aucune frame valide pour les graphiques."
            ))
            return

        # Remove placeholder
        self._charts_placeholder.hide()

        # Clear existing charts
        for i in reversed(range(self._charts_layout.count())):
            widget = self._charts_layout.itemAt(i).widget()
            if widget and widget is not self._charts_placeholder:
                widget.setParent(None)
                widget.deleteLater()

        # Theme colors
        bg_color = COLORS['bg_darkest']
        text_color = COLORS['text_primary']
        grid_color = COLORS['border']
        accent = COLORS['accent_cyan']
        warn_color = COLORS['warning']

        def _style_ax(ax):
            """Apply cosmic dark theme to a matplotlib axes."""
            ax.set_facecolor(bg_color)
            ax.tick_params(colors=text_color, labelsize=7)
            ax.xaxis.label.set_color(text_color)
            ax.yaxis.label.set_color(text_color)
            ax.title.set_color(text_color)
            ax.title.set_fontsize(8)
            for spine in ax.spines.values():
                spine.set_color(grid_color)
            ax.grid(True, alpha=0.15, color=grid_color)

        # -- Chart 1: FWHM distribution histogram --
        fig1 = Figure(figsize=(3.5, 2.5), dpi=100)
        fig1.set_facecolor(bg_color)
        fig1.subplots_adjust(left=0.15, right=0.95, top=0.88, bottom=0.18)
        ax1 = fig1.add_subplot(111)
        _style_ax(ax1)

        fwhm_vals = [r.fwhm_median for r in valid]
        ax1.hist(fwhm_vals, bins=min(30, max(5, len(fwhm_vals) // 3)),
                 color=accent, alpha=0.7, edgecolor=bg_color, linewidth=0.5)
        ax1.set_title(self._tr("FWHM Distribution", "Distribution FWHM"), fontsize=8)
        ax1.set_xlabel(self._tr("FWHM (px)", "FWHM (px)"), fontsize=7)
        ax1.set_ylabel(self._tr("Count", "Nombre"), fontsize=7)

        canvas1 = FigureCanvasQTAgg(fig1)
        canvas1.setToolTip(self._tr(
            "Histogram of median FWHM values across all frames",
            "Histogramme des valeurs FWHM medianes sur toutes les frames"
        ))
        self._charts_layout.addWidget(canvas1, 0, 0)

        # -- Chart 2: Quality score distribution --
        fig2 = Figure(figsize=(3.5, 2.5), dpi=100)
        fig2.set_facecolor(bg_color)
        fig2.subplots_adjust(left=0.15, right=0.95, top=0.88, bottom=0.18)
        ax2 = fig2.add_subplot(111)
        _style_ax(ax2)

        scores = [r.quality_score for r in valid]
        # Color bars by score range
        n_bins = min(25, max(5, len(scores) // 3))
        counts, bins, patches = ax2.hist(
            scores, bins=n_bins, alpha=0.8, edgecolor=bg_color, linewidth=0.5
        )
        for patch, left_edge in zip(patches, bins[:-1]):
            center = left_edge + (bins[1] - bins[0]) / 2
            patch.set_facecolor(_score_color(center))

        ax2.set_title(self._tr("Score Distribution", "Distribution des Scores"), fontsize=8)
        ax2.set_xlabel("Score (0-100)", fontsize=7)
        ax2.set_ylabel(self._tr("Count", "Nombre"), fontsize=7)

        canvas2 = FigureCanvasQTAgg(fig2)
        canvas2.setToolTip(self._tr(
            "Histogram of quality scores across all frames",
            "Histogramme des scores de qualite sur toutes les frames"
        ))
        self._charts_layout.addWidget(canvas2, 0, 1)

        # -- Chart 3: FWHM vs Frame number (tracking quality over time) --
        fig3 = Figure(figsize=(3.5, 2.5), dpi=100)
        fig3.set_facecolor(bg_color)
        fig3.subplots_adjust(left=0.15, right=0.95, top=0.88, bottom=0.18)
        ax3 = fig3.add_subplot(111)
        _style_ax(ax3)

        frame_indices = list(range(1, len(valid) + 1))
        fwhm_series = [r.fwhm_median for r in valid]
        ax3.plot(frame_indices, fwhm_series, color=accent, alpha=0.8,
                 linewidth=1.0, marker='.', markersize=3)

        # Running median (window of 5)
        if len(fwhm_series) >= 5:
            import numpy as np
            kernel = min(5, len(fwhm_series))
            padded = np.pad(fwhm_series, (kernel // 2, kernel // 2), mode='edge')
            running = np.convolve(padded, np.ones(kernel) / kernel, mode='valid')
            running = running[:len(frame_indices)]
            ax3.plot(frame_indices, running, color=warn_color, alpha=0.7,
                     linewidth=1.5, linestyle='--', label=self._tr("Trend", "Tendance"))
            ax3.legend(fontsize=6, loc='upper right',
                       facecolor=bg_color, edgecolor=grid_color,
                       labelcolor=text_color)

        ax3.set_title(self._tr("FWHM over Time", "FWHM dans le Temps"), fontsize=8)
        ax3.set_xlabel(self._tr("Frame #", "Frame #"), fontsize=7)
        ax3.set_ylabel(self._tr("FWHM (px)", "FWHM (px)"), fontsize=7)

        canvas3 = FigureCanvasQTAgg(fig3)
        canvas3.setToolTip(self._tr(
            "FWHM trend across frames in capture order (tracks seeing evolution)",
            "Tendance FWHM sur les frames dans l'ordre de capture (suit l'evolution du seeing)"
        ))
        self._charts_layout.addWidget(canvas3, 1, 0)

        # -- Chart 4: Eccentricity vs FWHM scatter --
        fig4 = Figure(figsize=(3.5, 2.5), dpi=100)
        fig4.set_facecolor(bg_color)
        fig4.subplots_adjust(left=0.15, right=0.95, top=0.88, bottom=0.18)
        ax4 = fig4.add_subplot(111)
        _style_ax(ax4)

        ecc_vals = [r.eccentricity_median for r in valid]
        score_vals = [r.quality_score for r in valid]
        scatter_colors = [_score_color(s) for s in score_vals]

        ax4.scatter(fwhm_vals, ecc_vals, c=scatter_colors, alpha=0.7,
                    s=20, edgecolors='none')

        ax4.set_title(self._tr(
            "Eccentricity vs FWHM", "Excentricite vs FWHM"
        ), fontsize=8)
        ax4.set_xlabel(self._tr("FWHM (px)", "FWHM (px)"), fontsize=7)
        ax4.set_ylabel(self._tr("Eccentricity", "Excentricite"), fontsize=7)

        canvas4 = FigureCanvasQTAgg(fig4)
        canvas4.setToolTip(self._tr(
            "Scatter plot of eccentricity vs FWHM — color indicates quality score",
            "Nuage de points excentricite vs FWHM — la couleur indique le score de qualite"
        ))
        self._charts_layout.addWidget(canvas4, 1, 1)

    # -----------------------------------------------------------------------
    # Export functions
    # -----------------------------------------------------------------------

    def _export_accepted_list(self):
        """Export a text file listing accepted frame file paths."""
        if not self._results:
            return

        include_rejected = self.cb_include_rejected.isChecked()
        if include_rejected:
            export_results = self._results
        else:
            export_results = [r for r in self._results if not r.rejection_flag]

        if not export_results:
            QMessageBox.information(
                self,
                self._tr("Nothing to Export", "Rien a Exporter"),
                self._tr(
                    "No frames match the export criteria.",
                    "Aucune frame ne correspond aux criteres d'export."
                )
            )
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("Export Accepted File List", "Exporter la Liste des Fichiers Acceptes"),
            os.path.join(
                os.path.dirname(self._files[0]) if self._files else "",
                "accepted_frames.txt"
            ),
            self._tr("Text Files (*.txt)", "Fichiers Texte (*.txt)")
        )
        if not filepath:
            return

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for r in export_results:
                    f.write(r.filepath + '\n')
            logger.info("Exported %d frame paths to %s", len(export_results), filepath)
        except OSError as e:
            logger.error("Failed to export accepted list: %s", e)
            QMessageBox.warning(
                self,
                self._tr("Export Error", "Erreur d'Export"),
                str(e)
            )

    def _export_csv(self):
        """Export all frame metrics as a CSV file."""
        if not self._results:
            return

        include_rejected = self.cb_include_rejected.isChecked()
        export_results = self._results if include_rejected else [
            r for r in self._results if not r.rejection_flag
        ]

        if not export_results:
            QMessageBox.information(
                self,
                self._tr("Nothing to Export", "Rien a Exporter"),
                self._tr(
                    "No frames match the export criteria.",
                    "Aucune frame ne correspond aux criteres d'export."
                )
            )
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("Export Rejection Report (CSV)", "Exporter le Rapport de Rejet (CSV)"),
            os.path.join(
                os.path.dirname(self._files[0]) if self._files else "",
                "quality_report.csv"
            ),
            self._tr("CSV Files (*.csv)", "Fichiers CSV (*.csv)")
        )
        if not filepath:
            return

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Filename', 'FilePath', 'QualityScore', 'FWHM_px',
                    'FWHM_arcsec', 'HFR_px', 'Eccentricity', 'SNR',
                    'StarCount', 'BackgroundLevel', 'BackgroundNoise',
                    'TrailingDetected', 'Rejected', 'RejectionReasons',
                    'PlateScale_arcsec_px', 'AnalysisTime_ms'
                ])
                for r in export_results:
                    fwhm_arcsec = (r.fwhm_median * r.plate_scale) if r.plate_scale > 0 else ''
                    writer.writerow([
                        os.path.basename(r.filepath),
                        r.filepath,
                        round(r.quality_score, 1),
                        round(r.fwhm_median, 3),
                        round(fwhm_arcsec, 2) if fwhm_arcsec != '' else '',
                        round(r.hfr_median, 3),
                        round(r.eccentricity_median, 4),
                        round(r.snr_median, 1),
                        r.star_count,
                        round(r.background_level, 1),
                        round(r.background_noise, 2),
                        r.trailing_detected,
                        r.rejection_flag,
                        '; '.join(r.rejection_reasons),
                        round(r.plate_scale, 4) if r.plate_scale > 0 else '',
                        round(r.analysis_time_ms, 0),
                    ])
            logger.info("Exported CSV report (%d frames) to %s",
                        len(export_results), filepath)
        except OSError as e:
            logger.error("Failed to export CSV: %s", e)
            QMessageBox.warning(
                self,
                self._tr("Export Error", "Erreur d'Export"),
                str(e)
            )
