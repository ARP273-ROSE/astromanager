#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - ANALYTICS TAB
================================================================================
Advanced analytics dashboard with 6 sub-tabs:
1. N.I.N.A. Import — import CSV metadata from N.I.N.A. sessions
2. Efficiency — imaging efficiency (integration vs dark hours)
3. Correlations — scatter plots with regression analysis
4. Time Series — metric evolution with moving averages
5. Equipment — performance by telescope+camera+filter combo
6. Session Notes — per-session observation notes
================================================================================
"""

import logging
import os
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QPushButton, QLineEdit, QComboBox, QFrame, QTableWidget,
    QTableWidgetItem, QTextEdit, QDateEdit, QFileDialog,
    QProgressBar, QHeaderView, QSplitter, QGroupBox,
    QGridLayout, QSizePolicy, QCheckBox, QSpinBox
)
from PyQt6.QtCore import Qt, QTimer, QDate, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from core.config import get_config
from core.i18n import get_lang
from core.signals import signals
from core.workers import UnifiedWorker, WorkerJob, JobType
from gui.theme import COLORS, get_mono_font
from gui.tooltips import get_tip

logger = logging.getLogger(__name__)

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    from scipy import stats as scipy_stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


class StatCard(QFrame):
    """Compact statistic display card."""

    def __init__(self, title: str, value: str = "-", color: str = None):
        super().__init__()
        color = color or COLORS.get('accent_cyan', '#88b8d8')
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background: {COLORS.get('bg_dark', '#1a1a2e')};
                border: 1px solid {COLORS.get('border', '#333355')};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"color: {COLORS.get('text_secondary', '#8888aa')}; font-size: 11px;")
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: bold;")
        layout.addWidget(self.value_label)

    def set_value(self, value: str):
        self.value_label.setText(value)

    def set_title(self, title: str):
        self.title_label.setText(title)


class _AnalyticsBgWorker(QThread):
    """Generic background worker for analytics computations.
    Prevents UI freezes by moving DB queries + heavy computation off the main thread."""
    finished_result = pyqtSignal(str, object)  # task_name, result
    error_signal = pyqtSignal(str, str)  # task_name, error_message

    def __init__(self, task_name, func, parent=None):
        super().__init__(parent)
        self._task_name = task_name
        self._func = func

    def run(self):
        try:
            result = self._func()
            self.finished_result.emit(self._task_name, result)
        except Exception as e:
            logger.error("Analytics worker error (%s): %s", self._task_name, e)
            self.error_signal.emit(self._task_name, str(e))


class AnalyticsTab(QWidget):
    """Analytics dashboard with N.I.N.A. import, efficiency, correlations, time series, equipment, notes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self.lang = get_lang()
        self.worker = None
        self._bg_worker = None
        self._init_ui()
        self._connect_signals()

    def _tr(self, en, fr):
        return fr if self.lang == 'fr' else en

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self.sub_tabs = QTabWidget()
        layout.addWidget(self.sub_tabs)

        self._create_nina_import_tab()
        self._create_efficiency_tab()
        self._create_correlations_tab()
        self._create_timeseries_tab()
        self._create_equipment_tab()
        self._create_notes_tab()

    def _connect_signals(self):
        signals.nina_import_completed.connect(self._on_nina_import_done)

    def _run_bg(self, task_name, func):
        """Run a function in background thread, route result to _on_bg_result."""
        if self._bg_worker is not None and self._bg_worker.isRunning():
            self._bg_worker.quit()
            self._bg_worker.wait(500)
        self._bg_worker = _AnalyticsBgWorker(task_name, func)
        self._bg_worker.finished_result.connect(self._on_bg_result)
        self._bg_worker.error_signal.connect(self._on_bg_error)
        self._bg_worker.finished.connect(self._bg_worker.deleteLater)
        self._bg_worker.start()

    def _on_bg_result(self, task_name, result):
        """Dispatch background worker results to the appropriate handler."""
        handlers = {
            'efficiency': self._update_efficiency_display,
            'correlation': self._update_correlation_display,
            'timeseries': self._update_timeseries_display,
            'equipment': self._populate_equipment_table,
        }
        handler = handlers.get(task_name)
        if handler and result is not None:
            handler(result)

    def _on_bg_error(self, task_name, error):
        logger.error("Analytics background task '%s' failed: %s", task_name, error)

    # =========================================================================
    # Sub-tab 1: N.I.N.A. Import
    # =========================================================================

    def _create_nina_import_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Folder selection
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel(self._tr("N.I.N.A. Data Folder:", "Dossier données N.I.N.A. :")))
        self.nina_folder_edit = QLineEdit()
        self.nina_folder_edit.setPlaceholderText(
            self._tr("Select folder with ImageMetaData.csv files...",
                      "Sélectionner le dossier avec les fichiers ImageMetaData.csv..."))
        self.nina_folder_edit.setToolTip(get_tip('nina_import_folder'))
        folder_row.addWidget(self.nina_folder_edit, stretch=1)

        browse_btn = QPushButton(self._tr("Browse...", "Parcourir..."))
        browse_btn.setToolTip(self._tr("Select N.I.N.A. data folder", "Sélectionner le dossier N.I.N.A."))
        browse_btn.clicked.connect(self._browse_nina_folder)
        folder_row.addWidget(browse_btn)
        layout.addLayout(folder_row)

        # Import controls
        ctrl_row = QHBoxLayout()
        self.nina_import_btn = QPushButton(self._tr("📥 Import N.I.N.A. Data", "📥 Importer données N.I.N.A."))
        self.nina_import_btn.setToolTip(get_tip('nina_import_btn'))
        self.nina_import_btn.clicked.connect(self._start_nina_import)
        ctrl_row.addWidget(self.nina_import_btn)

        self.nina_progress = QProgressBar()
        self.nina_progress.setVisible(False)
        self.nina_progress.setToolTip(get_tip('nina_progress'))
        ctrl_row.addWidget(self.nina_progress, stretch=1)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

        # Stats cards
        cards_row = QHBoxLayout()
        self.nina_card_sessions = StatCard(self._tr("Sessions", "Sessions"))
        self.nina_card_exposures = StatCard(self._tr("Exposures", "Expositions"))
        self.nina_card_weather = StatCard(self._tr("Weather Records", "Relevés Météo"))
        self.nina_card_errors = StatCard(self._tr("Errors", "Erreurs"), color=COLORS.get('error', '#c44'))
        for card in (self.nina_card_sessions, self.nina_card_exposures,
                     self.nina_card_weather, self.nina_card_errors):
            cards_row.addWidget(card)
        layout.addLayout(cards_row)

        # Session summary table
        self.nina_table = QTableWidget()
        self.nina_table.setToolTip(get_tip('nina_table'))
        self.nina_table.setColumnCount(7)
        self.nina_table.setHorizontalHeaderLabels([
            self._tr("Date", "Date"),
            self._tr("Frames", "Frames"),
            self._tr("Targets", "Cibles"),
            self._tr("Integration", "Intégration"),
            self._tr("Avg HFR", "HFR Moy"),
            self._tr("Filters", "Filtres"),
            self._tr("Equipment", "Équipement"),
        ])
        self.nina_table.horizontalHeader().setStretchLastSection(True)
        self.nina_table.setAlternatingRowColors(True)
        self.nina_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.nina_table, stretch=1)

        self.sub_tabs.addTab(tab, self._tr("📥 N.I.N.A. Import", "📥 Import N.I.N.A."))

        # Load existing data
        QTimer.singleShot(800, self._refresh_nina_summary)

    def _browse_nina_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._tr("Select N.I.N.A. Data Folder", "Sélectionner le dossier N.I.N.A."))
        if folder:
            self.nina_folder_edit.setText(folder)

    def _start_nina_import(self):
        folder = self.nina_folder_edit.text().strip()
        if not folder or not os.path.isdir(folder):
            return

        self.nina_import_btn.setEnabled(False)
        self.nina_progress.setVisible(True)
        self.nina_progress.setValue(0)

        self.worker = UnifiedWorker()
        job = WorkerJob(
            job_type=JobType.NINA_IMPORT,
            params={
                'folder': folder,
                'skip_calibrations': self.config.get('nina_import.skip_calibration_targets', True),
            },
            priority=7
        )
        self.worker.progress_signal.connect(self._on_nina_progress)
        self.worker.finished_signal.connect(self._on_nina_finished)
        self.worker.set_single_job(job)
        self.worker.start()

    def _on_nina_progress(self, current, total, phase):
        if total > 0:
            self.nina_progress.setMaximum(total)
            self.nina_progress.setValue(current)

    def _on_nina_finished(self, success, message, result):
        self.nina_import_btn.setEnabled(True)
        self.nina_progress.setVisible(False)

    def _on_nina_import_done(self, summary):
        self.nina_card_sessions.set_value(str(summary.get('sessions', 0)))
        self.nina_card_exposures.set_value(str(summary.get('exposures_imported', 0)))
        self.nina_card_weather.set_value(str(summary.get('weather_imported', 0)))
        errors = summary.get('errors', [])
        self.nina_card_errors.set_value(str(len(errors)))
        self._refresh_nina_summary()

    def _refresh_nina_summary(self):
        """Load session summary from DB."""
        try:
            from core.database import get_db
            db = get_db()
            rows = db.get_nina_session_summary()
            self.nina_table.setRowCount(len(rows))
            for i, row in enumerate(rows):
                self.nina_table.setItem(i, 0, QTableWidgetItem(row.get('session_date', '')))
                self.nina_table.setItem(i, 1, QTableWidgetItem(str(row.get('frame_count', 0))))
                self.nina_table.setItem(i, 2, QTableWidgetItem(str(row.get('target_count', 0))))
                total_sec = row.get('total_integration') or 0
                hours = total_sec / 3600.0
                self.nina_table.setItem(i, 3, QTableWidgetItem(f"{hours:.1f}h"))
                avg_hfr = row.get('avg_hfr')
                self.nina_table.setItem(i, 4, QTableWidgetItem(f"{avg_hfr:.2f}" if avg_hfr else "-"))
                self.nina_table.setItem(i, 5, QTableWidgetItem(row.get('filters', '') or ''))
                equip = []
                if row.get('telescopes'):
                    equip.append(row['telescopes'])
                if row.get('cameras'):
                    equip.append(row['cameras'])
                self.nina_table.setItem(i, 6, QTableWidgetItem(' + '.join(equip)))
        except Exception as e:
            logger.error(f"Error refreshing N.I.N.A. summary: {e}")

    # =========================================================================
    # Sub-tab 2: Imaging Efficiency
    # =========================================================================

    def _create_efficiency_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Controls
        ctrl_row = QHBoxLayout()
        compute_btn = QPushButton(self._tr("🔄 Compute Efficiency", "🔄 Calculer l'efficacité"))
        compute_btn.setToolTip(get_tip('efficiency_chart'))
        compute_btn.clicked.connect(self._compute_efficiency)
        ctrl_row.addWidget(compute_btn)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

        # Stat cards
        cards_row = QHBoxLayout()
        self.eff_card_avg = StatCard(self._tr("Avg Efficiency", "Efficacité Moy"))
        self.eff_card_best = StatCard(self._tr("Best Night", "Meilleure Nuit"), color=COLORS.get('success', '#4a8'))
        self.eff_card_total_dark = StatCard(self._tr("Total Dark Hours", "Heures Sombres Total"))
        self.eff_card_total_int = StatCard(self._tr("Total Integration", "Intégration Totale"))
        for card in (self.eff_card_avg, self.eff_card_best, self.eff_card_total_dark, self.eff_card_total_int):
            cards_row.addWidget(card)
        layout.addLayout(cards_row)

        # Chart
        if MATPLOTLIB_AVAILABLE:
            self.eff_figure = Figure(figsize=(10, 4), facecolor=COLORS.get('bg_darkest', '#0a0a1a'))
            self.eff_canvas = FigureCanvas(self.eff_figure)
            layout.addWidget(self.eff_canvas, stretch=1)
        else:
            layout.addWidget(QLabel(self._tr("matplotlib required for charts", "matplotlib requis pour les graphiques")))

        self.sub_tabs.addTab(tab, self._tr("⚡ Efficiency", "⚡ Efficacité"))

    def _compute_efficiency(self):
        """Compute imaging efficiency for all sessions (background thread)."""
        def _work():
            from modules.imaging_efficiency import ImagingEfficiencyCalculator
            from core.database import get_db
            db = get_db()
            dates = db.get_nina_session_dates()
            if not dates:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT DISTINCT observation_date FROM observations ORDER BY observation_date DESC")
                    dates = [r['observation_date'] for r in cursor.fetchall()]
            if not dates:
                return None
            calc = ImagingEfficiencyCalculator()
            return calc.compute_batch(dates)
        self._run_bg('efficiency', _work)

    def _update_efficiency_display(self, results):
        if not results:
            return

        if NUMPY_AVAILABLE:
            effs = [r['efficiency_pct'] for r in results if r.get('efficiency_pct')]
            if effs:
                self.eff_card_avg.set_value(f"{np.mean(effs):.1f}%")
                best_idx = np.argmax(effs)
                self.eff_card_best.set_value(f"{results[best_idx]['session_date']} ({effs[best_idx]:.0f}%)")

            total_dark = sum(r.get('dark_hours', 0) for r in results)
            total_int = sum(r.get('integration_hours', 0) for r in results)
            self.eff_card_total_dark.set_value(f"{total_dark:.1f}h")
            self.eff_card_total_int.set_value(f"{total_int:.1f}h")

        if MATPLOTLIB_AVAILABLE and results:
            self.eff_figure.clear()
            ax = self.eff_figure.add_subplot(111)
            ax.set_facecolor(COLORS.get('bg_darkest', '#0a0a1a'))

            dates = [r['session_date'] for r in results]
            dark_h = [r.get('dark_hours', 0) for r in results]
            int_h = [r.get('integration_hours', 0) for r in results]

            x = range(len(dates))
            ax.bar(x, dark_h, color=COLORS.get('accent_purple', '#9988cc'), alpha=0.5,
                   label=self._tr('Dark Hours', 'Heures Sombres'))
            ax.bar(x, int_h, color=COLORS.get('accent_cyan', '#88b8d8'),
                   label=self._tr('Integration', 'Intégration'))

            # Only show every Nth label to avoid overlap
            step = max(1, len(dates) // 15)
            ax.set_xticks([i for i in x if i % step == 0])
            ax.set_xticklabels([dates[i] for i in x if i % step == 0],
                               rotation=45, ha='right', fontsize=7,
                               color=COLORS.get('text_secondary', '#8888aa'))
            ax.tick_params(colors=COLORS.get('text_secondary', '#8888aa'))
            ax.set_ylabel(self._tr('Hours', 'Heures'),
                          color=COLORS.get('text_primary', '#ccccdd'))
            ax.legend(loc='upper left', fontsize=8,
                      facecolor=COLORS.get('bg_dark', '#1a1a2e'),
                      edgecolor=COLORS.get('border', '#333355'),
                      labelcolor=COLORS.get('text_primary', '#ccccdd'))
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            for spine in ax.spines.values():
                spine.set_color(COLORS.get('border', '#333355'))

            self.eff_figure.tight_layout()
            self.eff_canvas.draw()

    # =========================================================================
    # Sub-tab 3: Correlations
    # =========================================================================

    def _create_correlations_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Metric selectors
        ctrl_row = QHBoxLayout()

        ctrl_row.addWidget(QLabel(self._tr("X:", "X :")))
        self.corr_x_combo = QComboBox()
        self.corr_x_combo.setToolTip(get_tip('correlation_x'))
        x_metrics = [
            ('weather_temperature', self._tr('Temperature', 'Température')),
            ('weather_humidity', self._tr('Humidity', 'Humidité')),
            ('weather_wind_speed', self._tr('Wind Speed', 'Vitesse Vent')),
            ('weather_cloud_cover', self._tr('Cloud Cover', 'Couverture Nuageuse')),
            ('weather_pressure', self._tr('Pressure', 'Pression')),
            ('weather_sky_quality', self._tr('Sky Quality (SQM)', 'Qualité Ciel (SQM)')),
            ('focuser_temp', self._tr('Focuser Temp', 'Temp Focuser')),
            ('airmass', self._tr('Airmass', 'Masse d\'Air')),
            ('sensor_temp', self._tr('Sensor Temp', 'Temp Capteur')),
        ]
        for key, label in x_metrics:
            self.corr_x_combo.addItem(label, key)
        ctrl_row.addWidget(self.corr_x_combo)

        ctrl_row.addWidget(QLabel(self._tr("Y:", "Y :")))
        self.corr_y_combo = QComboBox()
        self.corr_y_combo.setToolTip(get_tip('correlation_y'))
        y_metrics = [
            ('hfr', 'HFR'),
            ('fwhm', 'FWHM'),
            ('eccentricity', self._tr('Eccentricity', 'Excentricité')),
            ('guiding_rms_total', self._tr('Guiding RMS', 'RMS Guidage')),
            ('detected_stars', self._tr('Detected Stars', 'Étoiles Détectées')),
            ('adu_mean', self._tr('ADU Mean', 'ADU Moyen')),
            ('adu_median', self._tr('ADU Median', 'ADU Médian')),
        ]
        for key, label in y_metrics:
            self.corr_y_combo.addItem(label, key)
        ctrl_row.addWidget(self.corr_y_combo)

        plot_btn = QPushButton(self._tr("📊 Plot", "📊 Tracer"))
        plot_btn.setToolTip(get_tip('correlation_chart'))
        plot_btn.clicked.connect(self._plot_correlation)
        ctrl_row.addWidget(plot_btn)

        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

        # Stats display
        self.corr_stats_label = QLabel("")
        self.corr_stats_label.setFont(get_mono_font(9))
        self.corr_stats_label.setStyleSheet(f"color: {COLORS.get('text_secondary', '#8888aa')};")
        layout.addWidget(self.corr_stats_label)

        # Chart
        if MATPLOTLIB_AVAILABLE:
            self.corr_figure = Figure(figsize=(10, 5), facecolor=COLORS.get('bg_darkest', '#0a0a1a'))
            self.corr_canvas = FigureCanvas(self.corr_figure)
            layout.addWidget(self.corr_canvas, stretch=1)
        else:
            layout.addWidget(QLabel(self._tr("matplotlib required", "matplotlib requis")))

        self.sub_tabs.addTab(tab, self._tr("🔗 Correlations", "🔗 Corrélations"))

    def _plot_correlation(self):
        """Plot X vs Y scatter with regression (DB query in background)."""
        x_key = self.corr_x_combo.currentData()
        y_key = self.corr_y_combo.currentData()
        if not x_key or not y_key:
            return

        # Capture combo labels before thread (GUI access must be on main thread)
        x_label = self.corr_x_combo.currentText()
        y_label = self.corr_y_combo.currentText()

        def _work():
            from core.database import get_db
            db = get_db()
            rows = db.get_nina_exposures()
            if not rows:
                return None
            x_vals, y_vals = [], []
            for row in rows:
                xv = row.get(x_key)
                yv = row.get(y_key)
                if xv is not None and yv is not None:
                    x_vals.append(float(xv))
                    y_vals.append(float(yv))
            if len(x_vals) < 3:
                return None
            # Compute stats in thread (numpy/scipy are thread-safe for read)
            result = {'x_vals': x_vals, 'y_vals': y_vals, 'x_label': x_label, 'y_label': y_label}
            if NUMPY_AVAILABLE:
                x_arr = np.array(x_vals)
                y_arr = np.array(y_vals)
                slope, intercept = np.polyfit(x_arr, y_arr, 1)
                ss_res = np.sum((y_arr - (slope * x_arr + intercept))**2)
                ss_tot = np.sum((y_arr - np.mean(y_arr))**2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
                result.update(slope=slope, intercept=intercept, r_squared=r_squared)
                if SCIPY_AVAILABLE:
                    pr, pp = scipy_stats.pearsonr(x_arr, y_arr)
                    sr, sp = scipy_stats.spearmanr(x_arr, y_arr)
                    result.update(pearson_r=pr, pearson_p=pp, spearman_r=sr, spearman_p=sp)
                    if len(x_vals) > 10:
                        n = len(x_vals)
                        x_mean = np.mean(x_arr)
                        s_xx = np.sum((x_arr - x_mean)**2)
                        residuals = y_arr - (slope * x_arr + intercept)
                        s_err = np.sqrt(np.sum(residuals**2) / (n - 2))
                        t_val = scipy_stats.t.ppf(0.975, n - 2)
                        x_line = np.linspace(x_arr.min(), x_arr.max(), 100)
                        se_line = s_err * np.sqrt(1.0 / n + (x_line - x_mean)**2 / s_xx)
                        result.update(x_line=x_line.tolist(), se_line=se_line.tolist(), t_val=t_val)
            return result
        self._run_bg('correlation', _work)

    def _update_correlation_display(self, result):
        """Update correlation chart on main thread with pre-computed data."""
        if not result or not MATPLOTLIB_AVAILABLE or not NUMPY_AVAILABLE:
            return
        x_arr = np.array(result['x_vals'])
        y_arr = np.array(result['y_vals'])
        slope = result.get('slope', 0)
        intercept = result.get('intercept', 0)

        stats_text = f"n = {len(x_arr)}"
        if 'pearson_r' in result:
            stats_text += f"  |  Pearson r = {result['pearson_r']:.3f} (p={result['pearson_p']:.2e})"
            stats_text += f"  |  Spearman ρ = {result['spearman_r']:.3f} (p={result['spearman_p']:.2e})"
        stats_text += f"  |  R² = {result.get('r_squared', 0):.3f}"
        self.corr_stats_label.setText(stats_text)

        self.corr_figure.clear()
        ax = self.corr_figure.add_subplot(111)
        ax.set_facecolor(COLORS.get('bg_darkest', '#0a0a1a'))
        ax.scatter(x_arr, y_arr, s=8, alpha=0.5,
                   color=COLORS.get('accent_cyan', '#88b8d8'), edgecolors='none')
        x_line = np.linspace(x_arr.min(), x_arr.max(), 100)
        y_line = slope * x_line + intercept
        ax.plot(x_line, y_line, color=COLORS.get('accent_orange', '#cc9966'),
                linewidth=1.5, label=f"y = {slope:.4f}x + {intercept:.2f}")

        if 'se_line' in result:
            se = np.array(result['se_line'])
            xl = np.array(result['x_line'])
            yl = slope * xl + intercept
            t_val = result['t_val']
            ax.fill_between(xl, yl - t_val * se, yl + t_val * se,
                            alpha=0.15, color=COLORS.get('accent_orange', '#cc9966'),
                            label=self._tr('95% confidence', 'Confiance 95%'))

        ax.set_xlabel(result.get('x_label', ''), color=COLORS.get('text_primary', '#ccccdd'))
        ax.set_ylabel(result.get('y_label', ''), color=COLORS.get('text_primary', '#ccccdd'))
        ax.tick_params(colors=COLORS.get('text_secondary', '#8888aa'))
        ax.legend(fontsize=8, facecolor=COLORS.get('bg_dark', '#1a1a2e'),
                  edgecolor=COLORS.get('border', '#333355'),
                  labelcolor=COLORS.get('text_primary', '#ccccdd'))
        for spine in ax.spines.values():
            spine.set_color(COLORS.get('border', '#333355'))
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        self.corr_figure.tight_layout()
        self.corr_canvas.draw()

    # =========================================================================
    # Sub-tab 4: Time Series
    # =========================================================================

    def _create_timeseries_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel(self._tr("Metric:", "Métrique :")))
        self.ts_metric_combo = QComboBox()
        self.ts_metric_combo.setToolTip(get_tip('timeseries_metric'))
        ts_metrics = [
            ('hfr', 'HFR'),
            ('fwhm', 'FWHM'),
            ('eccentricity', self._tr('Eccentricity', 'Excentricité')),
            ('guiding_rms_total', self._tr('Guiding RMS', 'RMS Guidage')),
            ('detected_stars', self._tr('Detected Stars', 'Étoiles Détectées')),
            ('weather_temperature', self._tr('Temperature', 'Température')),
            ('weather_humidity', self._tr('Humidity', 'Humidité')),
            ('weather_cloud_cover', self._tr('Cloud Cover', 'Couverture Nuageuse')),
        ]
        for key, label in ts_metrics:
            self.ts_metric_combo.addItem(label, key)
        ctrl_row.addWidget(self.ts_metric_combo)

        plot_btn = QPushButton(self._tr("📈 Plot", "📈 Tracer"))
        plot_btn.setToolTip(get_tip('ts_plot_btn'))
        plot_btn.clicked.connect(self._plot_timeseries)
        ctrl_row.addWidget(plot_btn)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

        if MATPLOTLIB_AVAILABLE:
            self.ts_figure = Figure(figsize=(10, 4), facecolor=COLORS.get('bg_darkest', '#0a0a1a'))
            self.ts_canvas = FigureCanvas(self.ts_figure)
            layout.addWidget(self.ts_canvas, stretch=1)
        else:
            layout.addWidget(QLabel(self._tr("matplotlib required", "matplotlib requis")))

        self.sub_tabs.addTab(tab, self._tr("📈 Time Series", "📈 Séries Temporelles"))

    def _plot_timeseries(self):
        """Plot nightly median of selected metric with moving averages (background)."""
        metric_key = self.ts_metric_combo.currentData()
        if not metric_key or not MATPLOTLIB_AVAILABLE or not NUMPY_AVAILABLE:
            return
        metric_label = self.ts_metric_combo.currentText()

        def _work():
            from core.database import get_db
            db = get_db()
            rows = db.get_nina_exposures()
            if not rows:
                return None
            by_date = {}
            for row in rows:
                date = row.get('session_date')
                val = row.get(metric_key)
                if date and val is not None:
                    by_date.setdefault(date, []).append(float(val))
            if not by_date:
                return None
            dates_sorted = sorted(by_date.keys())
            medians = [float(np.median(by_date[d])) for d in dates_sorted]
            arr = np.array(medians)
            result = {'dates': dates_sorted, 'medians': medians, 'metric_label': metric_label}
            if len(arr) >= 7:
                result['ma7'] = np.convolve(arr, np.ones(7) / 7, mode='valid').tolist()
            if len(arr) >= 30:
                result['ma30'] = np.convolve(arr, np.ones(30) / 30, mode='valid').tolist()
            return result
        self._run_bg('timeseries', _work)

    def _update_timeseries_display(self, result):
        """Update time series chart on main thread."""
        if not result or not MATPLOTLIB_AVAILABLE:
            return
        dates_sorted = result['dates']
        medians = result['medians']

        self.ts_figure.clear()
        ax = self.ts_figure.add_subplot(111)
        ax.set_facecolor(COLORS.get('bg_darkest', '#0a0a1a'))

        x = range(len(dates_sorted))
        ax.plot(x, medians, color=COLORS.get('accent_cyan', '#88b8d8'),
                linewidth=0.8, alpha=0.6, label=self._tr('Nightly Median', 'Médiane Nocturne'))
        ax.scatter(x, medians, s=6, color=COLORS.get('accent_cyan', '#88b8d8'), alpha=0.4)

        ma7 = result.get('ma7')
        ma30 = result.get('ma30')
        if ma7 is not None:
            offset7 = len(medians) - len(ma7)
            ax.plot(range(offset7, len(medians)), ma7,
                    color=COLORS.get('accent_orange', '#cc9966'), linewidth=1.5,
                    label=self._tr('7-day MA', 'MM 7j'))
        if ma30 is not None:
            offset30 = len(medians) - len(ma30)
            ax.plot(range(offset30, len(medians)), ma30,
                    color=COLORS.get('accent_pink', '#cc88aa'), linewidth=2,
                    label=self._tr('30-day MA', 'MM 30j'))

        step = max(1, len(dates_sorted) // 15)
        ax.set_xticks([i for i in x if i % step == 0])
        ax.set_xticklabels([dates_sorted[i] for i in x if i % step == 0],
                           rotation=45, ha='right', fontsize=7,
                           color=COLORS.get('text_secondary', '#8888aa'))
        ax.tick_params(colors=COLORS.get('text_secondary', '#8888aa'))
        ax.set_ylabel(result.get('metric_label', ''),
                      color=COLORS.get('text_primary', '#ccccdd'))
        ax.legend(fontsize=8, facecolor=COLORS.get('bg_dark', '#1a1a2e'),
                  edgecolor=COLORS.get('border', '#333355'),
                  labelcolor=COLORS.get('text_primary', '#ccccdd'))
        for spine in ax.spines.values():
            spine.set_color(COLORS.get('border', '#333355'))
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        self.ts_figure.tight_layout()
        self.ts_canvas.draw()

    # =========================================================================
    # Sub-tab 5: Equipment Performance
    # =========================================================================

    def _create_equipment_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        ctrl_row = QHBoxLayout()
        refresh_btn = QPushButton(self._tr("🔄 Compute Stats", "🔄 Calculer les Stats"))
        refresh_btn.setToolTip(get_tip('equipment_table'))
        refresh_btn.clicked.connect(self._compute_equipment_stats)
        ctrl_row.addWidget(refresh_btn)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

        self.equip_table = QTableWidget()
        self.equip_table.setToolTip(get_tip('equipment_table'))
        self.equip_table.setColumnCount(7)
        self.equip_table.setHorizontalHeaderLabels([
            self._tr("Telescope", "Télescope"),
            self._tr("Camera", "Caméra"),
            self._tr("Filter", "Filtre"),
            self._tr("Med HFR", "HFR Méd"),
            self._tr("Med FWHM", "FWHM Méd"),
            self._tr("Med Ecc", "Ecc Méd"),
            self._tr("Frames", "Frames"),
        ])
        self.equip_table.horizontalHeader().setStretchLastSection(True)
        self.equip_table.setAlternatingRowColors(True)
        self.equip_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.equip_table.setSortingEnabled(True)
        layout.addWidget(self.equip_table, stretch=1)

        self.sub_tabs.addTab(tab, self._tr("🔧 Equipment", "🔧 Équipement"))

        QTimer.singleShot(1200, self._load_cached_equipment)

    def _compute_equipment_stats(self):
        """Compute equipment performance stats (background thread)."""
        def _work():
            from modules.equipment_performance import EquipmentPerformance
            ep = EquipmentPerformance()
            results = ep.compute_from_nina_data()
            if not results:
                results = ep.compute_from_observations()
            return results
        self._run_bg('equipment', _work)

    def _load_cached_equipment(self):
        try:
            from modules.equipment_performance import EquipmentPerformance
            ep = EquipmentPerformance()
            results = ep.get_performance_table()
            if results:
                self._populate_equipment_table(results)
        except Exception as e:
            logger.debug(f"No cached equipment data: {e}")

    def _populate_equipment_table(self, results):
        self.equip_table.setRowCount(len(results))
        for i, r in enumerate(results):
            self.equip_table.setItem(i, 0, QTableWidgetItem(r.get('telescope', '')))
            self.equip_table.setItem(i, 1, QTableWidgetItem(r.get('camera', '')))
            self.equip_table.setItem(i, 2, QTableWidgetItem(r.get('filter_name', '')))
            for col, key in enumerate(('median_hfr', 'median_fwhm', 'median_eccentricity'), start=3):
                val = r.get(key)
                self.equip_table.setItem(i, col, QTableWidgetItem(f"{val:.3f}" if val else "-"))
            self.equip_table.setItem(i, 6, QTableWidgetItem(str(r.get('frame_count', 0))))

    # =========================================================================
    # Sub-tab 6: Session Notes
    # =========================================================================

    def _create_notes_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Date + target selection
        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel(self._tr("Date:", "Date :")))
        self.note_date_edit = QDateEdit()
        self.note_date_edit.setCalendarPopup(True)
        self.note_date_edit.setDate(QDate.currentDate())
        self.note_date_edit.setToolTip(get_tip('session_note_date'))
        self.note_date_edit.dateChanged.connect(self._load_note_for_date)
        ctrl_row.addWidget(self.note_date_edit)

        ctrl_row.addWidget(QLabel(self._tr("Target:", "Cible :")))
        self.note_target_combo = QComboBox()
        self.note_target_combo.setEditable(True)
        self.note_target_combo.setToolTip(get_tip('note_target_combo'))
        self.note_target_combo.addItem(self._tr("(All / General)", "(Tous / Général)"), None)
        self.note_target_combo.currentIndexChanged.connect(self._load_note_for_date)
        ctrl_row.addWidget(self.note_target_combo, stretch=1)
        layout.addLayout(ctrl_row)

        # Note editor
        self.note_editor = QTextEdit()
        self.note_editor.setPlaceholderText(
            self._tr("Write your observation notes here...",
                      "Écrivez vos notes d'observation ici..."))
        self.note_editor.setToolTip(get_tip('session_note_text'))
        layout.addWidget(self.note_editor, stretch=1)

        # Save/delete buttons
        btn_row = QHBoxLayout()
        save_btn = QPushButton(self._tr("💾 Save Note", "💾 Sauvegarder la Note"))
        save_btn.setToolTip(self._tr("Save this session note", "Sauvegarder cette note de session"))
        save_btn.clicked.connect(self._save_note)
        btn_row.addWidget(save_btn)

        delete_btn = QPushButton(self._tr("🗑️ Delete Note", "🗑️ Supprimer la Note"))
        delete_btn.setToolTip(self._tr("Delete this session note", "Supprimer cette note de session"))
        delete_btn.clicked.connect(self._delete_note)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Notes list
        self.notes_table = QTableWidget()
        self.notes_table.setToolTip(get_tip('notes_table'))
        self.notes_table.setColumnCount(3)
        self.notes_table.setHorizontalHeaderLabels([
            self._tr("Date", "Date"),
            self._tr("Target", "Cible"),
            self._tr("Note (preview)", "Note (aperçu)"),
        ])
        self.notes_table.horizontalHeader().setStretchLastSection(True)
        self.notes_table.setAlternatingRowColors(True)
        self.notes_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.notes_table.cellClicked.connect(self._on_note_selected)
        layout.addWidget(self.notes_table)

        self.sub_tabs.addTab(tab, self._tr("📝 Notes", "📝 Notes"))

        QTimer.singleShot(1000, self._refresh_notes_list)

    def _load_note_for_date(self):
        date_str = self.note_date_edit.date().toString('yyyy-MM-dd')
        target = self.note_target_combo.currentData()
        try:
            from modules.session_notes import SessionNotes
            sn = SessionNotes()
            notes = sn.get_notes(session_date=date_str, target_name=target)
            if notes:
                self.note_editor.setText(notes[0].get('note_text', ''))
            else:
                self.note_editor.clear()
        except Exception as e:
            logger.debug(f"Error loading note: {e}")

    def _save_note(self):
        date_str = self.note_date_edit.date().toString('yyyy-MM-dd')
        target = self.note_target_combo.currentData()
        text = self.note_editor.toPlainText().strip()
        if not text:
            return
        try:
            from modules.session_notes import SessionNotes
            sn = SessionNotes()
            sn.save_note(date_str, text, target_name=target)
            self._refresh_notes_list()
        except Exception as e:
            logger.error(f"Error saving note: {e}")

    def _delete_note(self):
        date_str = self.note_date_edit.date().toString('yyyy-MM-dd')
        target = self.note_target_combo.currentData()
        try:
            from modules.session_notes import SessionNotes
            sn = SessionNotes()
            notes = sn.get_notes(session_date=date_str, target_name=target)
            if notes:
                sn.delete_note(notes[0]['id'])
                self.note_editor.clear()
                self._refresh_notes_list()
        except Exception as e:
            logger.error(f"Error deleting note: {e}")

    def _refresh_notes_list(self):
        try:
            from modules.session_notes import SessionNotes
            sn = SessionNotes()
            all_notes = sn.get_notes()
            self.notes_table.setRowCount(len(all_notes))
            for i, note in enumerate(all_notes):
                self.notes_table.setItem(i, 0, QTableWidgetItem(note.get('session_date', '')))
                self.notes_table.setItem(i, 1, QTableWidgetItem(note.get('target_name', '') or self._tr('(General)', '(Général)')))
                preview = (note.get('note_text', '') or '')[:80].replace('\n', ' ')
                self.notes_table.setItem(i, 2, QTableWidgetItem(preview))
        except Exception as e:
            logger.debug(f"Error refreshing notes list: {e}")

    def _on_note_selected(self, row, col):
        date_item = self.notes_table.item(row, 0)
        if date_item:
            date_str = date_item.text()
            self.note_date_edit.setDate(QDate.fromString(date_str, 'yyyy-MM-dd'))
