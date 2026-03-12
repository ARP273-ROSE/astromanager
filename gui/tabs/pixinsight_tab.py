#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - PIXINSIGHT PROCESSING TAB
================================================================================
Dashboard tab displaying PixInsight WBPP/FBP processing results:
SubframeSelector metrics, frame weights, pixel rejection, integration stats.
================================================================================
"""

import logging
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget, QAbstractItemView,
    QFrame, QComboBox, QFileDialog, QMessageBox,
    QScrollArea, QSizePolicy, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont

from core.config import get_config
from core.i18n import get_lang

logger = logging.getLogger(__name__)


class StatCard(QFrame):
    """A styled card widget for displaying a single statistic."""

    def __init__(self, title: str, value: str = "-", color: str = "#88b8d8",
                 parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            StatCard {{
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


class PixInsightTab(QWidget):
    """PixInsight Processing tab - WBPP/FBP log analysis dashboard."""

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
            "🔬 PixInsight Processing",
            "🔬 Traitement PixInsight"
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
        self.session_combo.currentIndexChanged.connect(self._on_session_changed)
        top_bar.addWidget(self.session_combo)

        # Import button
        self.import_btn = QPushButton(self._tr("📂 Import Log", "📂 Importer Log"))
        self.import_btn.setToolTip(self._tr(
            "Import a PixInsight WBPP/FBP log file",
            "Importer un fichier log PixInsight WBPP/FBP"
        ))
        self.import_btn.clicked.connect(self._import_log)
        top_bar.addWidget(self.import_btn)

        # Import folder button
        self.import_folder_btn = QPushButton(self._tr("📁 Import Folder", "📁 Importer Dossier"))
        self.import_folder_btn.setToolTip(self._tr(
            "Import all PixInsight logs from a folder tree",
            "Importer tous les logs PixInsight d'une arborescence"
        ))
        self.import_folder_btn.clicked.connect(self._import_folder)
        top_bar.addWidget(self.import_folder_btn)

        # Refresh button
        self.refresh_btn = QPushButton(self._tr("🔄 Refresh", "🔄 Actualiser"))
        self.refresh_btn.clicked.connect(self._refresh_current)
        top_bar.addWidget(self.refresh_btn)

        layout.addLayout(top_bar)

        # ── Summary Cards ──
        cards_layout = QGridLayout()
        cards_layout.setSpacing(8)

        self.card_total = StatCard(
            self._tr("Total Frames", "Images Totales"), "-", "#88b8d8")
        self.card_approved = StatCard(
            self._tr("Approved", "Approuvées"), "-", "#88d8b8")
        self.card_rejected = StatCard(
            self._tr("Rejected", "Rejetées"), "-", "#d88888")
        self.card_fwhm = StatCard(
            self._tr("Avg FWHM", "FWHM Moyen"), "-", "#d8b888")
        self.card_ecc = StatCard(
            self._tr("Avg Eccentricity", "Excentricité Moy."), "-", "#b888d8")
        self.card_snr = StatCard(
            self._tr("Avg SNR", "SNR Moyen"), "-", "#88d8d8")

        cards_layout.addWidget(self.card_total, 0, 0)
        cards_layout.addWidget(self.card_approved, 0, 1)
        cards_layout.addWidget(self.card_rejected, 0, 2)
        cards_layout.addWidget(self.card_fwhm, 0, 3)
        cards_layout.addWidget(self.card_ecc, 0, 4)
        cards_layout.addWidget(self.card_snr, 0, 5)

        layout.addLayout(cards_layout)

        # ── Sub-Tabs ──
        self.sub_tabs = QTabWidget()
        layout.addWidget(self.sub_tabs, 1)

        self._create_subframe_table_tab()
        self._create_quality_by_filter_tab()
        self._create_integration_tab()
        self._create_calibration_tab()

    def _create_subframe_table_tab(self):
        """SubframeSelector per-frame metrics table."""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(4, 4, 4, 4)

        self.subframe_table = QTableWidget()
        self.subframe_table.setColumnCount(14)
        self.subframe_table.setHorizontalHeaderLabels([
            self._tr("File", "Fichier"),
            self._tr("Target", "Cible"),
            self._tr("Filter", "Filtre"),
            self._tr("Exp (s)", "Exp (s)"),
            "FWHM (px)",
            self._tr("Eccentricity", "Excentricité"),
            self._tr("Stars", "Étoiles"),
            "PSF Weight",
            "PSF SNR",
            "SNR",
            "Median ADU",
            "MAD ADU",
            "Mstar ADU",
            self._tr("Camera", "Caméra"),
        ])
        self.subframe_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 14):
            self.subframe_table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents)
        self.subframe_table.setAlternatingRowColors(True)
        self.subframe_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.subframe_table.setSortingEnabled(True)
        tab_layout.addWidget(self.subframe_table)

        self.sub_tabs.addTab(tab, self._tr(
            "📋 Subframe Metrics", "📋 Métriques Subframes"))

    def _create_quality_by_filter_tab(self):
        """Quality stats grouped by filter."""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(4, 4, 4, 4)

        self.filter_quality_table = QTableWidget()
        self.filter_quality_table.setColumnCount(11)
        self.filter_quality_table.setHorizontalHeaderLabels([
            self._tr("Filter", "Filtre"),
            self._tr("Frames", "Images"),
            self._tr("Avg FWHM", "FWHM Moy"),
            self._tr("Min FWHM", "FWHM Min"),
            self._tr("Max FWHM", "FWHM Max"),
            self._tr("Avg Ecc", "Ecc Moy"),
            self._tr("Avg SNR", "SNR Moy"),
            self._tr("Min SNR", "SNR Min"),
            self._tr("Max SNR", "SNR Max"),
            self._tr("Avg Stars", "Étoiles Moy"),
            self._tr("Avg Median ADU", "Médiane ADU Moy"),
        ])
        self.filter_quality_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.filter_quality_table.setAlternatingRowColors(True)
        self.filter_quality_table.setSortingEnabled(True)
        tab_layout.addWidget(self.filter_quality_table)

        self.sub_tabs.addTab(tab, self._tr(
            "📊 Quality by Filter", "📊 Qualité par Filtre"))

    def _create_integration_tab(self):
        """ImageIntegration results and frame weights."""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(4, 4, 4, 4)

        # Integration summary table
        lbl = QLabel(self._tr(
            "Integration Results", "Résultats d'Intégration"))
        lbl.setStyleSheet("font-size: 11pt; font-weight: bold; color: #a8c8e8;")
        tab_layout.addWidget(lbl)

        self.integration_table = QTableWidget()
        self.integration_table.setColumnCount(11)
        self.integration_table.setHorizontalHeaderLabels([
            self._tr("Filter", "Filtre"),
            self._tr("Method", "Méthode"),
            self._tr("Weight Mode", "Mode Poids"),
            self._tr("Rejection", "Rejet"),
            self._tr("Frames", "Images"),
            self._tr("Integrated", "Intégrées"),
            self._tr("Rejected", "Rejetées"),
            self._tr("Pixel Rej %", "% Rejet Pixel"),
            self._tr("Output SNR", "SNR Sortie"),
            self._tr("Output PSF Signal", "Signal PSF Sortie"),
            self._tr("Output File", "Fichier Sortie"),
        ])
        self.integration_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.integration_table.setAlternatingRowColors(True)
        self.integration_table.setSortingEnabled(True)
        self.integration_table.setMaximumHeight(200)
        tab_layout.addWidget(self.integration_table)

        # Frame weights table
        lbl2 = QLabel(self._tr(
            "Normalized Weights & Pixel Rejection",
            "Poids Normalisés & Rejet Pixels"))
        lbl2.setStyleSheet("font-size: 11pt; font-weight: bold; color: #a8c8e8;")
        tab_layout.addWidget(lbl2)

        self.weights_table = QTableWidget()
        self.weights_table.setColumnCount(7)
        self.weights_table.setHorizontalHeaderLabels([
            self._tr("File", "Fichier"),
            self._tr("Weight", "Poids"),
            self._tr("Accepted", "Acceptée"),
            self._tr("Pix Rej Count", "Nb Rejet Pix"),
            self._tr("Pix Rej %", "% Rejet Pix"),
            self._tr("Low %", "Bas %"),
            self._tr("High %", "Haut %"),
        ])
        self.weights_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 7):
            self.weights_table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents)
        self.weights_table.setAlternatingRowColors(True)
        self.weights_table.setSortingEnabled(True)
        tab_layout.addWidget(self.weights_table)

        self.sub_tabs.addTab(tab, self._tr(
            "⚙ Integration", "⚙ Intégration"))

    def _create_calibration_tab(self):
        """Calibration group details."""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(4, 4, 4, 4)

        self.calibration_table = QTableWidget()
        self.calibration_table.setColumnCount(11)
        self.calibration_table.setHorizontalHeaderLabels([
            self._tr("Filter", "Filtre"),
            self._tr("Frame Type", "Type"),
            self._tr("Total", "Total"),
            self._tr("Active", "Actives"),
            self._tr("Size", "Taille"),
            self._tr("Binning", "Binning"),
            self._tr("Exposure", "Exposition"),
            self._tr("Color", "Couleur"),
            self._tr("Master Dark", "Master Dark"),
            self._tr("Master Flat", "Master Flat"),
            self._tr("Pedestal", "Piédestal"),
        ])
        self.calibration_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.calibration_table.setAlternatingRowColors(True)
        self.calibration_table.setSortingEnabled(True)
        tab_layout.addWidget(self.calibration_table)

        self.sub_tabs.addTab(tab, self._tr(
            "🔧 Calibration", "🔧 Calibration"))

    # =========================================================================
    # Session Management
    # =========================================================================

    def _load_sessions(self):
        """Load session list into combo box."""
        try:
            from analyzers.pixinsight_analyzer import get_session_list
            sessions = get_session_list()
        except Exception as e:
            logger.debug(f"No PI sessions yet: {e}")
            return

        self.session_combo.blockSignals(True)
        self.session_combo.clear()

        if not sessions:
            self.session_combo.addItem(self._tr(
                "No sessions - Import a log file",
                "Aucune session - Importez un log"), None)
            self.session_combo.blockSignals(False)
            return

        for s in sessions:
            log_name = Path(s['log_file_path']).stem if s['log_file_path'] else '?'
            ts = s.get('log_timestamp', '') or ''
            n = s.get('total_subframes', 0)
            label = f"{ts} | {log_name} | {n} frames"
            self.session_combo.addItem(label, s['session_id'])

        self.session_combo.blockSignals(False)

        # Auto-select first session
        if sessions:
            self._current_session_id = sessions[0]['session_id']
            self._refresh_current()

    def _on_session_changed(self, index):
        """Handle session selection change."""
        session_id = self.session_combo.currentData()
        if session_id is not None:
            self._current_session_id = session_id
            self._refresh_current()

    # =========================================================================
    # Import
    # =========================================================================

    def _import_log(self):
        """Import a single PixInsight log file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._tr("Select PixInsight Log", "Sélectionner Log PixInsight"),
            "",
            self._tr("Log files (*.log *.txt);;All files (*)",
                      "Fichiers log (*.log *.txt);;Tous les fichiers (*)")
        )
        if not path:
            return

        try:
            from parsers.pixinsight_log_parser import parse_pixinsight_log
            from parsers.base_parser import store_results
            result = parse_pixinsight_log(path)

            # Use a simple session_id based on existing count
            from core.database import get_db
            db = get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COALESCE(MAX(session_id), 0) + 1 FROM pixinsight_sessions")
                new_id = cursor.fetchone()[0]

            store_results(result, new_id)

            n_sf = result.total_subframes
            n_int = len(result.integrations)
            QMessageBox.information(self, "Import",
                self._tr(
                    f"Imported {n_sf} subframes, {n_int} integrations.",
                    f"Importé {n_sf} subframes, {n_int} intégrations."
                ))

            self._load_sessions()

        except Exception as e:
            logger.error(f"Import failed: {e}", exc_info=True)
            QMessageBox.warning(self, "Error",
                self._tr(f"Import failed: {e}", f"Échec import : {e}"))

    def _import_folder(self):
        """Import all PI logs from a folder tree."""
        folder = QFileDialog.getExistingDirectory(
            self,
            self._tr("Select Folder with PixInsight Logs",
                      "Sélectionner Dossier avec Logs PixInsight"))
        if not folder:
            return

        try:
            from parsers.pixinsight_log_parser import parse_log_folder
            from parsers.base_parser import store_results
            from core.database import get_db

            results = parse_log_folder(folder)
            if not results:
                QMessageBox.information(self, "Import",
                    self._tr("No PixInsight logs found in this folder.",
                              "Aucun log PixInsight trouvé dans ce dossier."))
                return

            db = get_db()
            imported = 0
            skipped = 0

            for r in results:
                # Check if this log is already imported
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT COUNT(*) FROM pixinsight_sessions WHERE log_file_path = ?",
                        (r.log_file_path,))
                    if cursor.fetchone()[0] > 0:
                        skipped += 1
                        continue

                    cursor.execute("SELECT COALESCE(MAX(session_id), 0) + 1 FROM pixinsight_sessions")
                    new_id = cursor.fetchone()[0]

                store_results(r, new_id)
                imported += 1

            QMessageBox.information(self, "Import",
                self._tr(
                    f"Imported {imported} logs ({skipped} already imported).",
                    f"Importé {imported} logs ({skipped} déjà importés)."
                ))

            self._load_sessions()

        except Exception as e:
            logger.error(f"Folder import failed: {e}", exc_info=True)
            QMessageBox.warning(self, "Error",
                self._tr(f"Import failed: {e}", f"Échec import : {e}"))

    # =========================================================================
    # Data Refresh
    # =========================================================================

    def _refresh_current(self):
        """Refresh all displays for the current session."""
        if self._current_session_id is None:
            return
        self._refresh_cards()
        self._refresh_subframe_table()
        self._refresh_quality_by_filter()
        self._refresh_integration()
        self._refresh_calibration()

    def _refresh_cards(self):
        """Update summary stat cards."""
        sid = self._current_session_id
        try:
            from analyzers.pixinsight_analyzer import (
                get_processing_summary, get_frame_rejection_analysis,
                get_all_subframes
            )
            summary = get_processing_summary(sid)
            rejection = get_frame_rejection_analysis(sid)
            subframes = get_all_subframes(sid)

            self.card_total.set_value(str(summary.get('total_subframes', 0)))
            self.card_approved.set_value(str(rejection.get('accepted_count', 0)))
            self.card_rejected.set_value(str(rejection.get('rejected_count', 0)))

            # Calculate averages from subframes
            fwhm_vals = [s['fwhm'] for s in subframes if s.get('fwhm') is not None]
            ecc_vals = [s['eccentricity'] for s in subframes if s.get('eccentricity') is not None]
            snr_vals = [s['snr'] for s in subframes if s.get('snr') is not None]

            if fwhm_vals:
                avg_fwhm = sum(fwhm_vals) / len(fwhm_vals)
                self.card_fwhm.set_value(f"{avg_fwhm:.2f} px")
            else:
                self.card_fwhm.set_value("-")

            if ecc_vals:
                avg_ecc = sum(ecc_vals) / len(ecc_vals)
                self.card_ecc.set_value(f"{avg_ecc:.3f}")
            else:
                self.card_ecc.set_value("-")

            if snr_vals:
                avg_snr = sum(snr_vals) / len(snr_vals)
                self.card_snr.set_value(f"{avg_snr:.3f}")
            else:
                self.card_snr.set_value("-")

        except Exception as e:
            logger.error(f"Error refreshing cards: {e}")

    def _refresh_subframe_table(self):
        """Populate the subframe metrics table."""
        sid = self._current_session_id
        try:
            from analyzers.pixinsight_analyzer import get_all_subframes
            subframes = get_all_subframes(sid)
        except Exception as e:
            logger.error(f"Error loading subframes: {e}")
            return

        self.subframe_table.setSortingEnabled(False)
        self.subframe_table.setRowCount(len(subframes))

        for i, sf in enumerate(subframes):
            # Short filename (just the filename part)
            fname = sf.get('filename', '')
            short = os.path.basename(fname) if fname else '-'
            name_item = QTableWidgetItem(short)
            name_item.setToolTip(fname)
            self.subframe_table.setItem(i, 0, name_item)

            self.subframe_table.setItem(i, 1, QTableWidgetItem(sf.get('target_name') or '-'))
            self.subframe_table.setItem(i, 2, QTableWidgetItem(sf.get('filter_name') or '-'))

            # Exposure
            exp = sf.get('exposure_seconds')
            self.subframe_table.setItem(i, 3, self._num_item(exp, '{:.0f}'))

            # FWHM with color coding
            fwhm = sf.get('fwhm')
            fwhm_item = self._num_item(fwhm, '{:.3f}')
            if fwhm is not None:
                if fwhm < 3.0:
                    fwhm_item.setForeground(QColor("#88d8b8"))  # green = good
                elif fwhm < 6.0:
                    fwhm_item.setForeground(QColor("#d8b888"))  # orange = ok
                else:
                    fwhm_item.setForeground(QColor("#d88888"))  # red = bad
            self.subframe_table.setItem(i, 4, fwhm_item)

            self.subframe_table.setItem(i, 5, self._num_item(sf.get('eccentricity'), '{:.3f}'))
            self.subframe_table.setItem(i, 6, self._num_item(sf.get('num_stars'), '{:.0f}'))
            self.subframe_table.setItem(i, 7, self._num_item(sf.get('psf_signal_weight'), '{:.4f}'))
            self.subframe_table.setItem(i, 8, self._num_item(sf.get('psf_snr'), '{:.3f}'))
            self.subframe_table.setItem(i, 9, self._num_item(sf.get('snr'), '{:.3f}'))
            self.subframe_table.setItem(i, 10, self._num_item(sf.get('median_adu'), '{:.3f}'))
            self.subframe_table.setItem(i, 11, self._num_item(sf.get('mad_adu'), '{:.3f}'))
            self.subframe_table.setItem(i, 12, self._num_item(sf.get('mstar_adu'), '{:.3f}'))
            self.subframe_table.setItem(i, 13, QTableWidgetItem(sf.get('camera') or '-'))

        self.subframe_table.setSortingEnabled(True)

    def _refresh_quality_by_filter(self):
        """Populate quality-by-filter table."""
        sid = self._current_session_id
        try:
            from analyzers.pixinsight_analyzer import get_subframe_quality_by_filter
            data = get_subframe_quality_by_filter(sid)
        except Exception as e:
            logger.error(f"Error loading filter quality: {e}")
            return

        self.filter_quality_table.setSortingEnabled(False)
        self.filter_quality_table.setRowCount(len(data))

        for i, d in enumerate(data):
            self.filter_quality_table.setItem(i, 0, QTableWidgetItem(d.get('filter_name', '-')))
            self.filter_quality_table.setItem(i, 1, self._num_item(d.get('count'), '{:.0f}'))
            self.filter_quality_table.setItem(i, 2, self._num_item(d.get('avg_fwhm'), '{:.3f}'))
            self.filter_quality_table.setItem(i, 3, self._num_item(d.get('min_fwhm'), '{:.3f}'))
            self.filter_quality_table.setItem(i, 4, self._num_item(d.get('max_fwhm'), '{:.3f}'))
            self.filter_quality_table.setItem(i, 5, self._num_item(d.get('avg_eccentricity'), '{:.3f}'))
            self.filter_quality_table.setItem(i, 6, self._num_item(d.get('avg_snr'), '{:.3f}'))
            self.filter_quality_table.setItem(i, 7, self._num_item(d.get('min_snr'), '{:.3f}'))
            self.filter_quality_table.setItem(i, 8, self._num_item(d.get('max_snr'), '{:.3f}'))
            self.filter_quality_table.setItem(i, 9, self._num_item(d.get('avg_stars'), '{:.0f}'))
            self.filter_quality_table.setItem(i, 10, self._num_item(d.get('avg_median_adu'), '{:.3f}'))

        self.filter_quality_table.setSortingEnabled(True)

    def _refresh_integration(self):
        """Populate integration and frame weights tables."""
        sid = self._current_session_id
        try:
            from analyzers.pixinsight_analyzer import get_integration_quality
            data = get_integration_quality(sid)
        except Exception as e:
            logger.error(f"Error loading integration data: {e}")
            return

        # Integration summary
        self.integration_table.setSortingEnabled(False)
        self.integration_table.setRowCount(len(data))

        all_weights = []

        for i, d in enumerate(data):
            self.integration_table.setItem(i, 0, QTableWidgetItem(d.get('filter_name', '-')))
            self.integration_table.setItem(i, 1, QTableWidgetItem(d.get('combination_method') or '-'))
            self.integration_table.setItem(i, 2, QTableWidgetItem(d.get('weight_mode') or '-'))
            self.integration_table.setItem(i, 3, QTableWidgetItem(d.get('rejection_method') or '-'))
            self.integration_table.setItem(i, 4, self._num_item(d.get('frames_total'), '{:.0f}'))
            self.integration_table.setItem(i, 5, self._num_item(d.get('frames_integrated'), '{:.0f}'))
            self.integration_table.setItem(i, 6, self._num_item(d.get('frames_rejected'), '{:.0f}'))
            self.integration_table.setItem(i, 7, self._num_item(d.get('total_rejection_pct'), '{:.2f}%'))
            self.integration_table.setItem(i, 8, self._num_item(d.get('output_snr'), '{:.4f}'))
            self.integration_table.setItem(i, 9, self._num_item(d.get('output_psf_signal'), '{:.6f}'))

            out_file = d.get('output_file') or '-'
            out_item = QTableWidgetItem(os.path.basename(out_file) if out_file != '-' else '-')
            out_item.setToolTip(out_file)
            self.integration_table.setItem(i, 10, out_item)

            all_weights.extend(d.get('frame_weights', []))

        self.integration_table.setSortingEnabled(True)

        # Frame weights table
        self.weights_table.setSortingEnabled(False)
        self.weights_table.setRowCount(len(all_weights))

        for i, fw in enumerate(all_weights):
            fname = fw.get('filename', '')
            short = os.path.basename(fname) if fname else '-'
            name_item = QTableWidgetItem(short)
            name_item.setToolTip(fname)
            self.weights_table.setItem(i, 0, name_item)

            self.weights_table.setItem(i, 1, self._num_item(fw.get('weight'), '{:.4f}'))

            accepted = fw.get('accepted', True)
            acc_item = QTableWidgetItem("Yes" if accepted else "No")
            if not accepted:
                acc_item.setForeground(QColor("#d88888"))
            else:
                acc_item.setForeground(QColor("#88d8b8"))
            self.weights_table.setItem(i, 2, acc_item)

            self.weights_table.setItem(i, 3, self._num_item(fw.get('pixel_rejection_count'), '{:.0f}'))
            self.weights_table.setItem(i, 4, self._num_item(fw.get('pixel_rejection_pct'), '{:.2f}%'))
            self.weights_table.setItem(i, 5, self._num_item(fw.get('low_rejection_pct'), '{:.2f}%'))
            self.weights_table.setItem(i, 6, self._num_item(fw.get('high_rejection_pct'), '{:.2f}%'))

        self.weights_table.setSortingEnabled(True)

    def _refresh_calibration(self):
        """Populate calibration table."""
        sid = self._current_session_id
        try:
            from analyzers.pixinsight_analyzer import get_calibration_summary
            data = get_calibration_summary(sid)
        except Exception as e:
            logger.error(f"Error loading calibration data: {e}")
            return

        self.calibration_table.setSortingEnabled(False)
        self.calibration_table.setRowCount(len(data))

        for i, d in enumerate(data):
            self.calibration_table.setItem(i, 0, QTableWidgetItem(d.get('filter_name') or '-'))
            self.calibration_table.setItem(i, 1, QTableWidgetItem(d.get('frame_type') or '-'))
            self.calibration_table.setItem(i, 2, self._num_item(d.get('frames_total'), '{:.0f}'))
            self.calibration_table.setItem(i, 3, self._num_item(d.get('frames_active'), '{:.0f}'))

            w = d.get('image_width')
            h = d.get('image_height')
            size_str = f"{w}x{h}" if w and h else '-'
            self.calibration_table.setItem(i, 4, QTableWidgetItem(size_str))

            self.calibration_table.setItem(i, 5, self._num_item(d.get('binning'), '{:.0f}'))

            exp = d.get('exposure_seconds')
            self.calibration_table.setItem(i, 6, self._num_item(exp, '{:.1f}s'))

            self.calibration_table.setItem(i, 7, QTableWidgetItem(d.get('color_mode') or '-'))

            dark = d.get('master_dark_path') or '-'
            dark_item = QTableWidgetItem(os.path.basename(dark) if dark != '-' else '-')
            dark_item.setToolTip(dark)
            self.calibration_table.setItem(i, 8, dark_item)

            flat = d.get('master_flat_path') or '-'
            flat_item = QTableWidgetItem(os.path.basename(flat) if flat != '-' else '-')
            flat_item.setToolTip(flat)
            self.calibration_table.setItem(i, 9, flat_item)

            self.calibration_table.setItem(i, 10, self._num_item(d.get('pedestal_value'), '{:.1f}'))

        self.calibration_table.setSortingEnabled(True)

    # =========================================================================
    # Helpers
    # =========================================================================

    def _num_item(self, value, fmt='{:.2f}'):
        """Create a right-aligned numeric QTableWidgetItem with sort support."""
        if value is None:
            item = QTableWidgetItem('-')
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return item

        try:
            text = fmt.format(value)
        except (ValueError, TypeError):
            text = str(value)

        item = QTableWidgetItem(text)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        # Store numeric value for proper sorting
        try:
            item.setData(Qt.ItemDataRole.UserRole, float(value))
        except (ValueError, TypeError):
            pass
        return item
