#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - FLAT MANAGER TAB
================================================================================
Flat frame organization, grouping, coverage reports, master flat tracking.
Integrates flat_manager.py for flat frame management.
================================================================================
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QMessageBox, QAbstractItemView, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from core.signals import signals
from core.config import get_config
from core.i18n import get_lang
from gui.theme import get_mono_font


class FlatScanWorker(QThread):
    """Worker thread for scanning flat frames without blocking the UI"""
    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(list)  # flat_groups result

    def __init__(self, folder, parent=None):
        super().__init__(parent)
        self.folder = folder

    def run(self):
        # Phase 1: Discover flat files
        self.progress.emit(0, 0, "Discovering flat files...")
        flat_files = []
        for root, _, files in os.walk(self.folder):
            for f in files:
                fn_upper = f.upper()
                if ('FLAT' in fn_upper) and f.lower().endswith(('.fits', '.fit', '.xisf', '.fz')):
                    flat_files.append(os.path.join(root, f))

        if not flat_files:
            self.finished.emit([])
            return

        # Phase 2: Read headers and group
        total = len(flat_files)
        groups = {}

        for i, fp in enumerate(flat_files):
            if i % 5 == 0:
                self.progress.emit(i, total, os.path.basename(fp))
            try:
                from modules.header_editor import read_header
                header = read_header(fp)
                if not header:
                    continue

                date = str(header.get('DATE-OBS', 'Unknown'))[:10]
                telescope = str(header.get('TELESCOP', 'Unknown'))
                camera = str(header.get('INSTRUME', 'Unknown'))
                filter_name = str(header.get('FILTER', 'Unknown'))
                binning = str(header.get('XBINNING', '1')) + 'x' + str(header.get('YBINNING', '1'))

                key = f"{date}|{telescope}|{camera}|{filter_name}|{binning}"

                if key not in groups:
                    groups[key] = {
                        'date': date,
                        'setup': f"{telescope} + {camera}",
                        'filter': filter_name,
                        'binning': binning,
                        'files': [],
                        'master': False,
                        'targets': set(),
                    }
                groups[key]['files'].append(fp)
            except Exception:
                continue

        self.progress.emit(total, total, "Done")
        self.finished.emit(list(groups.values()))


class FlatManagerTab(QWidget):
    """Flat Manager tab - Flat frame organization and tracking"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self.lang = get_lang()
        self.flat_groups = []
        self.analysis_data = None
        self._scan_worker = None
        self._init_ui()
        self._restore_options()
        # Listen for analysis completion to enable target linking
        signals.analysis_completed.connect(self._on_analysis_completed)

    def _tr(self, en, fr):
        return fr if self.lang == 'fr' else en

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Folder Selection ──
        folder_group = QGroupBox(self._tr("📁 Flat Library", "📁 Bibliothèque Flats"))
        folder_layout = QHBoxLayout(folder_group)
        self.folder_input = QLineEdit()
        self.folder_input.setToolTip(self._tr(
            "Path to flat frames folder",
            "Chemin vers le dossier de flat frames"
        ))
        self.folder_input.setPlaceholderText(self._tr("Select your flats folder...", "Sélectionner votre dossier de flats..."))
        folder_layout.addWidget(self.folder_input)
        browse_btn = QPushButton(self._tr("Browse...", "Parcourir..."))
        browse_btn.setToolTip(self._tr(
            "Browse for flat frames folder",
            "Parcourir pour le dossier de flat frames"
        ))
        browse_btn.clicked.connect(self._browse_folder)
        folder_layout.addWidget(browse_btn)
        self.scan_btn = QPushButton(self._tr("🔍 Scan", "🔍 Scanner"))
        self.scan_btn.setToolTip(self._tr(
            "Scan folder for flat frames and group them",
            "Scanner le dossier pour les flat frames et les grouper"
        ))
        self.scan_btn.setProperty("accent", True)
        self.scan_btn.clicked.connect(self._scan_flats)
        folder_layout.addWidget(self.scan_btn)
        layout.addWidget(folder_group)

        # ── Progress Bar ──
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # ── Flat Groups Table ──
        self.table = QTableWidget()
        self.table.setToolTip(self._tr(
            "Flat frame groups detected - shows filter, date, count, and setup",
            "Groupes de flats détectés - affiche filtre, date, nombre et configuration"
        ))
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            self._tr("Date", "Date"),
            self._tr("Setup", "Setup"),
            self._tr("Filter", "Filtre"),
            self._tr("Binning", "Binning"),
            self._tr("Count", "Nombre"),
            self._tr("Master", "Master"),
            self._tr("Targets", "Cibles"),
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, 1)

        # ── Coverage Report ──
        coverage_group = QGroupBox(self._tr("📊 Coverage Report", "📊 Rapport de Couverture"))
        coverage_layout = QVBoxLayout(coverage_group)
        self.coverage_text = QTextEdit()
        self.coverage_text.setToolTip(self._tr(
            "Flat coverage report - shows completeness status per filter and setup",
            "Rapport de couverture des flats - affiche l'état de complétude par filtre et configuration"
        ))
        self.coverage_text.setReadOnly(True)
        self.coverage_text.setFont(get_mono_font(9))
        coverage_layout.addWidget(self.coverage_text)
        layout.addWidget(coverage_group)

        # ── Buttons ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.link_btn = QPushButton(self._tr("🔗 Link to Targets", "🔗 Lier aux Cibles"))
        self.link_btn.setToolTip(self._tr(
            "Link flat groups to science targets",
            "Lier les groupes de flats aux cibles scientifiques"
        ))
        self.link_btn.clicked.connect(self._link_targets)
        btn_layout.addWidget(self.link_btn)
        self.export_btn = QPushButton(self._tr("📄 Export Report", "📄 Exporter Rapport"))
        self.export_btn.setToolTip(self._tr(
            "Export flat frame report",
            "Exporter le rapport de flat frames"
        ))
        self.export_btn.clicked.connect(self._export_report)
        btn_layout.addWidget(self.export_btn)
        layout.addLayout(btn_layout)

    # ==================================================================
    # Persistence
    # ==================================================================

    def _restore_options(self):
        """Restore saved options from config."""
        folder = self.config.get('flat_manager.last_folder', '')
        if folder:
            self.folder_input.setText(folder)

    def _save_options(self):
        """Save current options to config for next session."""
        self.config.set('flat_manager.last_folder',
                        self.folder_input.text().strip())
        self.config.save_config()

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, self._tr("Select Flats Folder", "Sélectionner Dossier Flats"))
        if folder:
            self.folder_input.setText(folder)

    def _scan_flats(self):
        """Scan folder for flat frames (non-blocking, runs in worker thread)"""
        self._save_options()
        folder = self.folder_input.text().strip()
        if not folder or not os.path.isdir(folder):
            return

        # Prevent double-launch
        if self._scan_worker and self._scan_worker.isRunning():
            return

        self.flat_groups = []
        self.table.setRowCount(0)
        self.coverage_text.clear()

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # indeterminate until file count known
        self.progress_bar.setFormat(self._tr("Discovering files...", "Recherche des fichiers..."))
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText(self._tr("⏳ Scanning...", "⏳ Scan en cours..."))

        self._scan_worker = FlatScanWorker(folder)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.start()

    def _on_scan_progress(self, current, total, message):
        """Update progress bar from worker thread"""
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)
            self.progress_bar.setFormat(f"{current}/{total} - {message}")
        else:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat(message)

    def _on_scan_finished(self, groups):
        """Handle scan completion"""
        self.progress_bar.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText(self._tr("🔍 Scan", "🔍 Scanner"))
        self._scan_worker = None

        if not groups:
            self.coverage_text.setText(self._tr(
                "No flat files found. Files must contain 'FLAT' in the filename.",
                "Aucun fichier flat trouvé. Les fichiers doivent contenir 'FLAT' dans le nom."
            ))
            return

        self.flat_groups = groups
        total_files = sum(len(g['files']) for g in groups)
        self.coverage_text.setText(self._tr(
            f"Found {total_files} flat files in {len(groups)} groups.",
            f"{total_files} fichiers flat trouvés dans {len(groups)} groupes."
        ))
        self._populate_table()
        self._generate_coverage_report()

    def _populate_table(self):
        """Populate table with flat groups"""
        self.table.setRowCount(len(self.flat_groups))

        for i, group in enumerate(self.flat_groups):
            count = len(group['files'])

            self.table.setItem(i, 0, QTableWidgetItem(group['date']))
            self.table.setItem(i, 1, QTableWidgetItem(group['setup']))
            from gui.theme import prettify_filter_name
            self.table.setItem(i, 2, QTableWidgetItem(prettify_filter_name(group['filter'])))
            self.table.setItem(i, 3, QTableWidgetItem(group['binning']))

            # Count with color coding
            count_item = QTableWidgetItem(str(count))
            if count >= 15:
                count_item.setForeground(QColor('#88b098'))  # Green - good
            elif count >= 10:
                count_item.setForeground(QColor('#b8a880'))  # Yellow - ok
            else:
                count_item.setForeground(QColor('#b89090'))  # Red - low
            self.table.setItem(i, 4, count_item)

            # Master status
            master_item = QTableWidgetItem("✓" if group['master'] else "✗")
            master_item.setForeground(QColor('#88b098' if group['master'] else '#b89090'))
            self.table.setItem(i, 5, master_item)

            # Linked targets
            targets = ', '.join(group['targets']) if group['targets'] else '-'
            self.table.setItem(i, 6, QTableWidgetItem(targets))

    def _generate_coverage_report(self):
        """Generate coverage report"""
        if not self.flat_groups:
            return

        report = []
        setups = {}

        for group in self.flat_groups:
            setup = group['setup']
            if setup not in setups:
                setups[setup] = []
            setups[setup].append(group)

        for setup, groups in setups.items():
            report.append(f"{'='*50}")
            report.append(f"Setup: {setup}")
            report.append(f"{'='*50}")

            for g in groups:
                count = len(g['files'])
                if count >= 15:
                    status = "✓"
                    color = self._tr("Complete", "Complet")
                elif count >= 10:
                    status = "⚠"
                    color = self._tr(f"Low count ({count}/15)", f"Nombre bas ({count}/15)")
                else:
                    status = "✗"
                    color = self._tr(f"Insufficient ({count}/15)", f"Insuffisant ({count}/15)")

                frames_label = self._tr("frames", "images")
                from gui.theme import prettify_filter_name
                report.append(f"  {status} {prettify_filter_name(g['filter'])} ({g['date']}): {count} {frames_label} - {color}")

        self.coverage_text.setPlainText('\n'.join(report))

    def _on_analysis_completed(self, result):
        """Store analysis results for target linking"""
        if isinstance(result, dict):
            self.analysis_data = result.get('data_by_target', {})

    def _link_targets(self):
        """Link flat groups to observed targets by matching setup and filters"""
        if not self.flat_groups:
            QMessageBox.information(self, self._tr("Info", "Info"),
                self._tr("Scan flats first.", "Scannez les flats d'abord."))
            return

        if not self.analysis_data:
            QMessageBox.information(self, self._tr("Info", "Info"),
                self._tr(
                    "Run an analysis first (Analysis tab) to detect observed targets.",
                    "Lancez d'abord une analyse (onglet Analyse) pour détecter les cibles observées."
                ))
            return

        # Build a mapping of (setup, filter) -> set of targets from analysis
        setup_filter_targets = {}
        for target, info in self.analysis_data.items():
            for f in info.get('files', []):
                telescope = str(f.get('telescope', 'Unknown'))
                camera = str(f.get('instrument', 'Unknown'))
                filt = str(f.get('filter', 'Unknown'))
                setup = f"{telescope} + {camera}"
                key = (setup, filt)
                if key not in setup_filter_targets:
                    setup_filter_targets[key] = set()
                setup_filter_targets[key].add(target)

        # Match flat groups to targets
        linked = 0
        for group in self.flat_groups:
            key = (group['setup'], group['filter'])
            matching_targets = setup_filter_targets.get(key, set())
            if matching_targets:
                group['targets'] = matching_targets
                linked += 1

        self._populate_table()
        QMessageBox.information(self, self._tr("Link Complete", "Liaison Terminée"),
            self._tr(
                f"Linked {linked}/{len(self.flat_groups)} flat groups to observed targets.",
                f"{linked}/{len(self.flat_groups)} groupes de flats liés aux cibles observées."
            ))

    def _export_report(self):
        if not self.flat_groups:
            return

        path, _ = QFileDialog.getSaveFileName(self, self._tr("Export Report", "Exporter Rapport"), "flat_report.txt", "Text Files (*.txt)")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.coverage_text.toPlainText())
            QMessageBox.information(self, self._tr("Export", "Export"), self._tr(f"Report saved to {path}", f"Rapport sauvegardé dans {path}"))

    def cleanup(self):
        """Clean up worker thread on shutdown."""
        if hasattr(self, '_scan_worker') and self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.quit()
            self._scan_worker.wait(3000)
