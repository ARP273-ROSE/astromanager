#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - MOUNT TRACKING TAB
================================================================================
Dashboard tab for MountMonitor tracking analysis: deviation charts,
FFT periodic error, target segments, quality rating.
================================================================================
"""

import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView,
    QFrame, QComboBox, QFileDialog, QMessageBox,
    QSplitter, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont

from core.config import get_config
from core.i18n import get_lang
from core.signals import signals
from gui.tooltips import get_tip

logger = logging.getLogger(__name__)


# ─── Inline StatCard (same pattern as PixInsight tab) ───

class _StatCard(QFrame):
    """A styled card widget for displaying a single statistic."""

    def __init__(self, title: str, value: str = "-", color: str = "#88b8d8",
                 parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            _StatCard {
                background: rgba(20, 30, 50, 0.6);
                border: 1px solid rgba(100, 140, 180, 0.3);
                border-radius: 8px;
                padding: 8px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #8898a8; font-size: 9pt;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(
            f"color: {color}; font-size: 16pt; font-weight: bold;"
        )
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)

    def set_value(self, value: str):
        self.value_label.setText(value)

    def set_title(self, title: str):
        self.title_label.setText(title)


class MountTab(QWidget):
    """Mount Tracking tab - MountMonitor log analysis dashboard."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self.lang = get_lang()
        self._current_session_id = None
        self._init_ui()
        QTimer.singleShot(800, self._load_sessions)

    def _tr(self, en, fr):
        return fr if self.lang == 'fr' else en

    # =========================================================================
    # UI Setup
    # =========================================================================

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Top bar: Title + Session selector + Buttons ──
        top_bar = QHBoxLayout()

        title = QLabel(self._tr(
            "🔭 Mount Tracking",
            "🔭 Suivi Monture"
        ))
        title.setStyleSheet("font-size: 13pt; font-weight: bold; color: #a8c8e8;")
        top_bar.addWidget(title)
        top_bar.addStretch()

        # Session selector
        session_label = QLabel(self._tr("Session:", "Session :"))
        session_label.setStyleSheet("color: #8898a8;")
        top_bar.addWidget(session_label)

        self.session_combo = QComboBox()
        self.session_combo.setMinimumWidth(350)
        self.session_combo.setToolTip(get_tip('mount_session_selector'))
        self.session_combo.currentIndexChanged.connect(self._on_session_changed)
        top_bar.addWidget(self.session_combo)

        # Import button
        self.import_btn = QPushButton(self._tr("📂 Import .dat", "📂 Importer .dat"))
        self.import_btn.setToolTip(get_tip('mount_import'))
        self.import_btn.clicked.connect(self._import_file)
        top_bar.addWidget(self.import_btn)

        # Import folder button
        self.import_folder_btn = QPushButton(self._tr("📁 Import Folder", "📁 Importer Dossier"))
        self.import_folder_btn.setToolTip(get_tip('mount_import_folder'))
        self.import_folder_btn.clicked.connect(self._import_folder)
        top_bar.addWidget(self.import_folder_btn)

        # Refresh button
        self.refresh_btn = QPushButton(self._tr("🔄 Refresh", "🔄 Actualiser"))
        self.refresh_btn.setToolTip(self._tr(
            "Refresh current session data",
            "Actualiser les données de la session courante"
        ))
        self.refresh_btn.clicked.connect(self._refresh_current)
        top_bar.addWidget(self.refresh_btn)

        layout.addLayout(top_bar)

        # ── Summary Cards ──
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(8)

        self.card_ra_rms = _StatCard(self._tr("RA RMS", "RMS RA"), "-", "#94b8c8")
        self.card_ra_rms.setToolTip(get_tip('mount_ra_rms'))
        cards_layout.addWidget(self.card_ra_rms)

        self.card_dec_rms = _StatCard(self._tr("DEC RMS", "RMS DEC"), "-", "#a8a0c0")
        self.card_dec_rms.setToolTip(get_tip('mount_dec_rms'))
        cards_layout.addWidget(self.card_dec_rms)

        self.card_tracking_pct = _StatCard(
            self._tr("Tracking %", "Suivi %"), "-", "#88b098")
        self.card_tracking_pct.setToolTip(get_tip('mount_tracking_pct'))
        cards_layout.addWidget(self.card_tracking_pct)

        self.card_samples = _StatCard(
            self._tr("Samples", "Échantillons"), "-", "#b8b090")
        self.card_samples.setToolTip(get_tip('mount_total_samples'))
        cards_layout.addWidget(self.card_samples)

        self.card_quality = _StatCard(
            self._tr("Quality", "Qualité"), "-", "#c0a0ac")
        self.card_quality.setToolTip(get_tip('mount_quality_rating'))
        cards_layout.addWidget(self.card_quality)

        self.card_pe_period = _StatCard(
            self._tr("PE Period", "Période PE"), "-", "#c0b098")
        self.card_pe_period.setToolTip(get_tip('mount_pe_period'))
        cards_layout.addWidget(self.card_pe_period)

        layout.addLayout(cards_layout)

        # ── Main content: Charts + Table ──
        main_splitter = QSplitter(Qt.Orientation.Vertical)

        # Charts area (horizontal split)
        charts_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Tracking chart placeholder
        self.tracking_chart_widget = QWidget()
        tracking_layout = QVBoxLayout(self.tracking_chart_widget)
        tracking_layout.setContentsMargins(4, 4, 4, 4)
        tracking_title = QLabel(self._tr(
            "📈 Tracking Quality (RA/DEC deviations)",
            "📈 Qualité de suivi (déviations RA/DEC)"
        ))
        tracking_title.setStyleSheet("color: #94b8c8; font-weight: bold; font-size: 10pt;")
        tracking_title.setToolTip(get_tip('mount_tracking_chart'))
        tracking_layout.addWidget(tracking_title)

        # Try to use matplotlib if available
        self._tracking_canvas = None
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
            fig = Figure(figsize=(6, 3), dpi=100)
            fig.patch.set_facecolor('#0a0e1a')
            self._tracking_ax = fig.add_subplot(111)
            self._style_axes(self._tracking_ax)
            self._tracking_canvas = FigureCanvasQTAgg(fig)
            tracking_layout.addWidget(self._tracking_canvas)
        except ImportError:
            no_mpl = QLabel(self._tr(
                "Install matplotlib for charts: pip install matplotlib",
                "Installer matplotlib pour les graphiques : pip install matplotlib"
            ))
            no_mpl.setStyleSheet("color: #b89090; padding: 20px;")
            no_mpl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tracking_layout.addWidget(no_mpl)

        charts_splitter.addWidget(self.tracking_chart_widget)

        # FFT chart placeholder
        self.fft_chart_widget = QWidget()
        fft_layout = QVBoxLayout(self.fft_chart_widget)
        fft_layout.setContentsMargins(4, 4, 4, 4)
        fft_title = QLabel(self._tr(
            "📊 Periodic Error (FFT)",
            "📊 Erreur Périodique (FFT)"
        ))
        fft_title.setStyleSheet("color: #a8a0c0; font-weight: bold; font-size: 10pt;")
        fft_title.setToolTip(get_tip('mount_fft_chart'))
        fft_layout.addWidget(fft_title)

        self._fft_canvas = None
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
            fig2 = Figure(figsize=(4, 3), dpi=100)
            fig2.patch.set_facecolor('#0a0e1a')
            self._fft_ax = fig2.add_subplot(111)
            self._style_axes(self._fft_ax)
            self._fft_canvas = FigureCanvasQTAgg(fig2)
            fft_layout.addWidget(self._fft_canvas)
        except ImportError:
            no_mpl2 = QLabel(self._tr(
                "Install matplotlib for charts",
                "Installer matplotlib pour les graphiques"
            ))
            no_mpl2.setStyleSheet("color: #b89090; padding: 20px;")
            no_mpl2.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fft_layout.addWidget(no_mpl2)

        charts_splitter.addWidget(self.fft_chart_widget)
        charts_splitter.setStretchFactor(0, 3)
        charts_splitter.setStretchFactor(1, 2)
        main_splitter.addWidget(charts_splitter)

        # ── Target Segments Table ──
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        table_layout.setContentsMargins(4, 4, 4, 4)

        table_title = QLabel(self._tr(
            "🎯 Target Segments",
            "🎯 Segments par Cible"
        ))
        table_title.setStyleSheet("color: #c0b098; font-weight: bold; font-size: 10pt;")
        table_title.setToolTip(get_tip('mount_segments_table'))
        table_layout.addWidget(table_title)

        self.segments_table = QTableWidget()
        self.segments_table.setColumnCount(10)
        self.segments_table.setHorizontalHeaderLabels([
            self._tr("Segment", "Segment"),
            self._tr("RA", "RA"),
            self._tr("DEC", "DEC"),
            self._tr("Tracking", "Suivi"),
            self._tr("Total", "Total"),
            self._tr("RA RMS (\")", "RMS RA (\")"),
            self._tr("DEC RMS (\")", "RMS DEC (\")"),
            self._tr("RA Range (\")", "Amplitude RA (\")"),
            self._tr("DEC Range (\")", "Amplitude DEC (\")"),
            self._tr("Duration", "Durée"),
        ])
        self.segments_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        self.segments_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self.segments_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        for col in range(3, 10):
            self.segments_table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents)
        self.segments_table.setAlternatingRowColors(True)
        self.segments_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.segments_table.setSortingEnabled(True)
        self.segments_table.setToolTip(get_tip('mount_segments_table'))
        table_layout.addWidget(self.segments_table)

        main_splitter.addWidget(table_widget)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 1)

        layout.addWidget(main_splitter)

    def _style_axes(self, ax):
        """Apply dark theme styling to matplotlib axes."""
        ax.set_facecolor('#0a0e1a')
        ax.tick_params(colors='#7a8498', labelsize=8)
        ax.spines['bottom'].set_color('#3a4258')
        ax.spines['left'].set_color('#3a4258')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.xaxis.label.set_color('#7a8498')
        ax.yaxis.label.set_color('#7a8498')
        ax.title.set_color('#94b8c8')

    # =========================================================================
    # Data Loading
    # =========================================================================

    def _load_sessions(self):
        """Load mount sessions from database."""
        try:
            from analyzers.mount_analyzer import get_mount_sessions
            sessions = get_mount_sessions()

            self.session_combo.blockSignals(True)
            self.session_combo.clear()

            if not sessions:
                self.session_combo.addItem(
                    self._tr("No sessions - Import a .dat file",
                             "Aucune session - Importer un fichier .dat"),
                    None)
            else:
                for s in sessions:
                    label = f"{s['created_at'][:16]} | {s.get('mount_name') or '?'} | " \
                            f"{s['tracking_samples']}/{s['total_samples']} samples"
                    self.session_combo.addItem(label, s['session_id'])

            self.session_combo.blockSignals(False)

            if sessions:
                self.session_combo.setCurrentIndex(0)
                self._on_session_changed(0)
        except Exception as e:
            logger.error(f"Failed to load mount sessions: {e}")

    def _on_session_changed(self, index):
        """Handle session selection change."""
        session_id = self.session_combo.currentData()
        if session_id is None:
            self._current_session_id = None
            self._clear_display()
            return
        self._current_session_id = session_id
        self._refresh_current()

    def _refresh_current(self):
        """Refresh display for current session."""
        if self._current_session_id is None:
            return
        try:
            self._update_cards()
            self._update_tracking_chart()
            self._update_fft_chart()
            self._update_segments_table()
        except Exception as e:
            logger.error(f"Failed to refresh mount data: {e}")
            signals.log_message.emit('ERROR', f"Mount refresh failed: {e}")

    def _clear_display(self):
        """Clear all displays."""
        for card in (self.card_ra_rms, self.card_dec_rms, self.card_tracking_pct,
                     self.card_samples, self.card_quality, self.card_pe_period):
            card.set_value("-")
        self.segments_table.setRowCount(0)
        if self._tracking_canvas:
            self._tracking_ax.clear()
            self._style_axes(self._tracking_ax)
            self._tracking_canvas.draw()
        if self._fft_canvas:
            self._fft_ax.clear()
            self._style_axes(self._fft_ax)
            self._fft_canvas.draw()

    def _update_cards(self):
        """Update summary stat cards."""
        from analyzers.mount_analyzer import get_tracking_stats, get_quality_rating, get_periodic_error

        stats = get_tracking_stats(self._current_session_id)
        quality = get_quality_rating(self._current_session_id)
        pe = get_periodic_error(self._current_session_id)

        # RA/DEC RMS
        ra_rms = stats.get('ra_dev_rms')
        dec_rms = stats.get('dec_dev_rms')
        self.card_ra_rms.set_value(f"{ra_rms}\"" if ra_rms is not None else "-")
        self.card_dec_rms.set_value(f"{dec_rms}\"" if dec_rms is not None else "-")

        # Tracking percentage
        pct = stats.get('tracking_pct', 0)
        self.card_tracking_pct.set_value(f"{pct:.1f}%")

        # Samples
        total = stats.get('total_samples', 0)
        tracking = stats.get('tracking_samples', 0)
        self.card_samples.set_value(f"{tracking}/{total}")

        # Quality rating
        grade = quality.get('grade', '-')
        desc = quality.get('description_fr' if self.lang == 'fr' else 'description_en', '')
        self.card_quality.set_value(grade)
        self.card_quality.setToolTip(f"{get_tip('mount_quality_rating')}\n\n{desc}")

        # PE period (from RA axis if available)
        if pe:
            ra_pe = next((p for p in pe if p['axis'] == 'RA'), None)
            if ra_pe and ra_pe.get('peak1_period'):
                period_s = ra_pe['peak1_period']
                if period_s and period_s > 0:
                    self.card_pe_period.set_value(f"{period_s:.0f}s")
                else:
                    self.card_pe_period.set_value("-")
            else:
                self.card_pe_period.set_value("-")
        else:
            self.card_pe_period.set_value("-")

    def _update_tracking_chart(self):
        """Update tracking deviation timeline chart."""
        if not self._tracking_canvas:
            return

        from analyzers.mount_analyzer import get_tracking_timeline

        data = get_tracking_timeline(self._current_session_id, tracking_only=True)

        ax = self._tracking_ax
        ax.clear()
        self._style_axes(ax)

        if not data['timestamps']:
            ax.text(0.5, 0.5, self._tr("No tracking data", "Aucune donnée de suivi"),
                    transform=ax.transAxes, ha='center', va='center',
                    color='#7a8498', fontsize=11)
            self._tracking_canvas.draw()
            return

        # Convert timestamps to indices for plotting
        n = len(data['timestamps'])
        x = list(range(n))

        # Downsample for performance if too many points
        step = max(1, n // 5000)
        x_ds = x[::step]
        ra_ds = data['ra_dev'][::step]
        dec_ds = data['dec_dev'][::step]

        ax.plot(x_ds, ra_ds, color='#94b8c8', linewidth=0.5, alpha=0.8,
                label='RA')
        ax.plot(x_ds, dec_ds, color='#a8a0c0', linewidth=0.5, alpha=0.8,
                label='DEC')
        ax.axhline(y=0, color='#3a4258', linewidth=0.5, linestyle='--')
        ax.set_ylabel(self._tr('Deviation (")', 'Déviation (")'))
        ax.set_xlabel(self._tr('Sample', 'Échantillon'))
        ax.legend(loc='upper right', fontsize=8, framealpha=0.3,
                  labelcolor='#c8ccd4', facecolor='#141828',
                  edgecolor='#3a4258')

        try:
            ax.figure.tight_layout()
        except Exception:
            pass
        self._tracking_canvas.draw()

    def _update_fft_chart(self):
        """Update FFT periodic error bar chart."""
        if not self._fft_canvas:
            return

        from analyzers.mount_analyzer import get_periodic_error

        pe_data = get_periodic_error(self._current_session_id)

        ax = self._fft_ax
        ax.clear()
        self._style_axes(ax)

        if not pe_data:
            ax.text(0.5, 0.5, self._tr("No FFT data", "Aucune donnée FFT"),
                    transform=ax.transAxes, ha='center', va='center',
                    color='#7a8498', fontsize=11)
            self._fft_canvas.draw()
            return

        # Bar chart of top 3 peaks for each axis
        labels = []
        amplitudes = []
        colors = []

        color_map = {'RA': '#94b8c8', 'DEC': '#a8a0c0'}

        for pe in pe_data:
            axis = pe['axis']
            c = color_map.get(axis, '#b8b090')
            for i in range(1, 4):
                amp = pe.get(f'peak{i}_amp')
                period = pe.get(f'peak{i}_period')
                if amp and period:
                    labels.append(f"{axis}\n{period:.0f}s")
                    amplitudes.append(amp)
                    colors.append(c)

        if labels:
            bars = ax.bar(range(len(labels)), amplitudes, color=colors, alpha=0.8)
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, fontsize=7)
            ax.set_ylabel(self._tr('Amplitude', 'Amplitude'))
            ax.set_title(self._tr('FFT Peaks', 'Pics FFT'), fontsize=10)

        try:
            ax.figure.tight_layout()
        except Exception:
            pass
        self._fft_canvas.draw()

    def _update_segments_table(self):
        """Update target segments table."""
        from analyzers.mount_analyzer import get_target_segments

        segments = get_target_segments(self._current_session_id)

        self.segments_table.setSortingEnabled(False)
        self.segments_table.setRowCount(len(segments))

        for row, seg in enumerate(segments):
            self.segments_table.setItem(row, 0,
                QTableWidgetItem(str(seg['segment'])))
            self.segments_table.setItem(row, 1,
                QTableWidgetItem(seg.get('ra_display', '-')))
            self.segments_table.setItem(row, 2,
                QTableWidgetItem(seg.get('dec_display', '-')))
            self.segments_table.setItem(row, 3,
                QTableWidgetItem(str(seg.get('tracking_samples', 0))))
            self.segments_table.setItem(row, 4,
                QTableWidgetItem(str(seg.get('total_samples', 0))))

            # Numeric items for sorting
            for col, key in [(5, 'ra_rms'), (6, 'dec_rms'),
                             (7, 'ra_range'), (8, 'dec_range')]:
                val = seg.get(key)
                item = QTableWidgetItem()
                if val is not None:
                    item.setText(f"{val:.3f}")
                    item.setData(Qt.ItemDataRole.UserRole, val)
                else:
                    item.setText("-")
                self.segments_table.setItem(row, col, item)

            # Duration (from timestamps)
            first_ts = seg.get('first_timestamp', '')
            last_ts = seg.get('last_timestamp', '')
            duration = self._compute_duration(first_ts, last_ts)
            self.segments_table.setItem(row, 9,
                QTableWidgetItem(duration))

        self.segments_table.setSortingEnabled(True)

    def _compute_duration(self, first: str, last: str) -> str:
        """Compute duration string from HH:MM:SS timestamps."""
        try:
            parts1 = first.split(':')
            parts2 = last.split(':')
            if len(parts1) < 3 or len(parts2) < 3:
                return '-'
            t1 = float(parts1[0]) * 3600 + float(parts1[1]) * 60 + float(parts1[2])
            t2 = float(parts2[0]) * 3600 + float(parts2[1]) * 60 + float(parts2[2])
            diff = t2 - t1
            if diff < 0:
                diff += 86400  # Midnight crossing
            hours = int(diff // 3600)
            minutes = int((diff % 3600) // 60)
            seconds = int(diff % 60)
            if hours > 0:
                return f"{hours}h{minutes:02d}m{seconds:02d}s"
            elif minutes > 0:
                return f"{minutes}m{seconds:02d}s"
            else:
                return f"{seconds}s"
        except (ValueError, IndexError):
            return '-'

    # =========================================================================
    # Import
    # =========================================================================

    def _import_file(self):
        """Import a single MountMonitor .dat file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self._tr("Select MountMonitor .dat file",
                      "Sélectionner un fichier MountMonitor .dat"),
            str(Path.home()),
            self._tr("MountMonitor files (*.dat)", "Fichiers MountMonitor (*.dat)")
        )
        if not file_path:
            return

        self._do_import([file_path])

    def _import_folder(self):
        """Import all MountMonitor .dat files from a folder."""
        folder = QFileDialog.getExistingDirectory(
            self,
            self._tr("Select folder with MountMonitor logs",
                      "Sélectionner le dossier de logs MountMonitor"),
            str(Path.home())
        )
        if not folder:
            return

        dat_files = sorted(Path(folder).glob("MountMonitor_*.dat"))
        if not dat_files:
            QMessageBox.information(
                self,
                self._tr("No Files", "Aucun fichier"),
                self._tr("No MountMonitor_*.dat files found in this folder.",
                          "Aucun fichier MountMonitor_*.dat trouvé dans ce dossier.")
            )
            return

        self._do_import([str(f) for f in dat_files])

    def _do_import(self, file_paths: list):
        """Import one or more .dat files."""
        from parsers.mountmonitor_parser import can_parse, parse_mountmonitor
        from parsers.base_parser import store_mount_results
        from core.database import get_db
        import time

        db = get_db()
        imported = 0
        errors = []

        for fp in file_paths:
            try:
                if not can_parse(fp):
                    errors.append(f"Not a MountMonitor file: {Path(fp).name}")
                    continue

                result = parse_mountmonitor(fp)
                if not result.has_mount_data:
                    errors.append(f"No tracking data in: {Path(fp).name}")
                    continue

                # Generate a session_id from timestamp
                session_id = int(time.time() * 1000) + imported
                result.log_file_path = fp

                store_mount_results(result, session_id)
                imported += 1

                signals.log_message.emit('INFO',
                    f"Imported {Path(fp).name}: "
                    f"{len(result.mount_tracking_data)} samples, "
                    f"{result.mount_num_segments} segments")

            except Exception as e:
                errors.append(f"{Path(fp).name}: {e}")
                logger.error(f"Failed to import {fp}: {e}", exc_info=True)

        # Report
        msg = self._tr(
            f"Imported {imported} file(s).",
            f"{imported} fichier(s) importé(s)."
        )
        if errors:
            msg += "\n\n" + self._tr("Errors:", "Erreurs :") + "\n"
            msg += "\n".join(errors[:10])

        QMessageBox.information(
            self,
            self._tr("Import Complete", "Import terminé"),
            msg
        )

        # Reload sessions
        self._load_sessions()

    def refresh_data(self):
        """Public refresh method (called from main window if needed)."""
        self._load_sessions()
