#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - DISK SPACE TAB
================================================================================
Storage analysis, optimization recommendations, duplicate detection,
format breakdown, and cleanup actions.
================================================================================
"""

import os
import threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QProgressBar, QMessageBox, QAbstractItemView, QComboBox,
    QCheckBox, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from core.workers import UnifiedWorker, WorkerJob, JobType
from core.signals import signals
from gui.theme import get_mono_font
from core.config import get_config


class DiskSpaceTab(QWidget):
    # Thread-safe signals for background operations
    _preview_result_signal = pyqtSignal(str)
    _organize_progress_signal = pyqtSignal(int)
    _organize_done_signal = pyqtSignal(int, int, str)
    """Disk Space tab - Storage analysis and optimization"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self.lang = self.config.get('application.language', 'auto')
        if self.lang == 'auto':
            import locale
            try:
                loc = locale.getdefaultlocale()[0]
                self.lang = 'fr' if loc and loc.lower().startswith('fr') else 'en'
            except Exception:
                self.lang = 'en'
        self.worker = None
        self.storage_stats = None
        # Connect thread-safe signals
        self._preview_result_signal.connect(self._show_preview_result)
        self._organize_progress_signal.connect(lambda pct: self.org_progress.setValue(pct))
        self._organize_done_signal.connect(
            lambda m, e, msg: self._on_organize_done(success=m, errors=e, error_msg=msg if msg else None))
        self._init_ui()

    def _tr(self, en, fr):
        return fr if self.lang == 'fr' else en

    def _format_size(self, size_bytes):
        """Format bytes to human readable"""
        if size_bytes >= 1024**4:
            return f"{size_bytes / (1024**4):.2f} TB"
        elif size_bytes >= 1024**3:
            return f"{size_bytes / (1024**3):.2f} GB"
        elif size_bytes >= 1024**2:
            return f"{size_bytes / (1024**2):.1f} MB"
        elif size_bytes >= 1024:
            return f"{size_bytes / 1024:.0f} KB"
        return f"{size_bytes} B"

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # ── Folder Selection (always visible) ──
        folder_group = QGroupBox(self._tr("💾 Storage Location", "💾 Emplacement Stockage"))
        folder_layout = QHBoxLayout(folder_group)
        self.folder_input = QLineEdit()
        self.folder_input.setToolTip(self._tr(
            "Select folder to analyze disk usage",
            "Sélectionner le dossier pour analyser l'utilisation disque"
        ))
        self.folder_input.setPlaceholderText(self._tr(
            "Select your astrophotography folder...",
            "Sélectionner votre dossier d'astrophotographie..."
        ))
        folder_layout.addWidget(self.folder_input)

        browse_btn = QPushButton(self._tr("Browse...", "Parcourir..."))
        browse_btn.setToolTip(self._tr(
            "Select folder to analyze disk usage",
            "Sélectionner le dossier pour analyser l'utilisation disque"
        ))
        browse_btn.clicked.connect(self._browse_folder)
        folder_layout.addWidget(browse_btn)

        self.analyze_btn = QPushButton(self._tr("🔍 Analyze Storage", "🔍 Analyser Stockage"))
        self.analyze_btn.setToolTip(self._tr(
            "Analyze disk space usage and file distribution",
            "Analyser l'utilisation d'espace disque et la distribution des fichiers"
        ))
        self.analyze_btn.setProperty("accent", True)
        self.analyze_btn.clicked.connect(self._analyze_storage)
        folder_layout.addWidget(self.analyze_btn)

        main_layout.addWidget(folder_group)

        # ── Progress (always visible) ──
        self.progress_bar = QProgressBar()
        self.progress_bar.setToolTip(self._tr(
            "Storage analysis progress",
            "Progression de l'analyse du stockage"
        ))
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # ── Sub-tabs ──
        self.sub_tabs = QTabWidget()
        main_layout.addWidget(self.sub_tabs, 1)

        self._build_breakdown_tab()
        self._build_recommendations_tab()
        self._build_organization_tab()

        # ── Bottom Action Buttons (always visible) ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.compress_btn = QPushButton(self._tr("🗜️ Compress FITS → XISF", "🗜️ Compresser FITS → XISF"))
        self.compress_btn.setToolTip(self._tr(
            "Compress FITS files to save disk space",
            "Compresser les fichiers FITS pour économiser de l'espace disque"
        ))
        self.compress_btn.setProperty("accent", True)
        self.compress_btn.clicked.connect(self._compress_fits)
        self.compress_btn.setEnabled(False)
        btn_layout.addWidget(self.compress_btn)

        self.export_btn = QPushButton(self._tr("📄 Export Report", "📄 Exporter Rapport"))
        self.export_btn.setToolTip(self._tr(
            "Export disk analysis report",
            "Exporter le rapport d'analyse disque"
        ))
        self.export_btn.clicked.connect(self._export_report)
        btn_layout.addWidget(self.export_btn)

        main_layout.addLayout(btn_layout)

    # ── Sub-tab builders ──

    def _build_breakdown_tab(self):
        """Build the Breakdown sub-tab: storage breakdown table + total + details table."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 6, 6, 6)

        # Storage breakdown table
        self.breakdown_table = QTableWidget()
        self.breakdown_table.setToolTip(self._tr(
            "Storage breakdown by file format",
            "Répartition du stockage par format de fichier"
        ))
        self.breakdown_table.setColumnCount(4)
        self.breakdown_table.setHorizontalHeaderLabels([
            self._tr("Format", "Format"),
            self._tr("Files", "Fichiers"),
            self._tr("Size", "Taille"),
            self._tr("Percentage", "Pourcentage"),
        ])
        self.breakdown_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.breakdown_table.setAlternatingRowColors(True)
        layout.addWidget(self.breakdown_table)

        # Total line
        total_layout = QHBoxLayout()
        total_layout.addStretch()
        self.total_label = QLabel(self._tr("Total: -", "Total: -"))
        self.total_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: #94b8c8;")
        total_layout.addWidget(self.total_label)
        layout.addLayout(total_layout)

        # Storage details table
        self.details_table = QTableWidget()
        self.details_table.setToolTip(self._tr(
            "Detailed file listing with sizes and formats",
            "Liste détaillée des fichiers avec tailles et formats"
        ))
        self.details_table.setColumnCount(3)
        self.details_table.setHorizontalHeaderLabels([
            self._tr("Metric", "Métrique"),
            self._tr("Value", "Valeur"),
            self._tr("Status", "Statut"),
        ])
        self.details_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.details_table.setAlternatingRowColors(True)
        layout.addWidget(self.details_table)

        self.sub_tabs.addTab(tab, self._tr("📊 Breakdown", "📊 Répartition"))

    def _build_recommendations_tab(self):
        """Build the Recommendations sub-tab: full-height text area."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 6, 6, 6)

        self.reco_text = QTextEdit()
        self.reco_text.setToolTip(self._tr(
            "Optimization recommendations based on storage analysis",
            "Recommandations d'optimisation basées sur l'analyse du stockage"
        ))
        self.reco_text.setReadOnly(True)
        self.reco_text.setFont(get_mono_font(9))
        layout.addWidget(self.reco_text)

        self.sub_tabs.addTab(tab, self._tr("💡 Recommendations", "💡 Recommandations"))

    def _build_organization_tab(self):
        """Build the Organization sub-tab: preset, destination, copy mode, preview, progress, buttons."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 6, 6, 6)

        # Controls row
        org_controls = QHBoxLayout()
        org_controls.addWidget(QLabel(self._tr("Preset:", "Modèle :")))
        self.org_preset_combo = QComboBox()
        self.org_preset_combo.setToolTip(self._tr(
            "Select a file organization preset",
            "Sélectionner un preset d'organisation de fichiers"
        ))
        self._populate_org_presets()
        self.org_preset_combo.setMinimumWidth(250)
        org_controls.addWidget(self.org_preset_combo)

        org_controls.addWidget(QLabel(self._tr("Destination:", "Destination :")))
        self.org_dest_input = QLineEdit()
        self.org_dest_input.setToolTip(self._tr(
            "Destination folder for organized files",
            "Dossier de destination pour les fichiers organisés"
        ))
        self.org_dest_input.setPlaceholderText(self._tr("Select destination folder...", "Sélectionner dossier destination..."))
        org_controls.addWidget(self.org_dest_input)

        org_browse_btn = QPushButton(self._tr("Browse...", "Parcourir..."))
        org_browse_btn.setToolTip(self._tr(
            "Browse for destination folder",
            "Parcourir pour le dossier de destination"
        ))
        org_browse_btn.clicked.connect(self._browse_org_dest)
        org_controls.addWidget(org_browse_btn)
        layout.addLayout(org_controls)

        # Options row
        org_opts = QHBoxLayout()
        self.org_copy_mode = QCheckBox(self._tr("Copy mode (keep originals)", "Mode copie (garder originaux)"))
        self.org_copy_mode.setToolTip(self._tr(
            "Copy files instead of moving them",
            "Copier les fichiers au lieu de les déplacer"
        ))
        self.org_copy_mode.setChecked(True)
        org_opts.addWidget(self.org_copy_mode)
        org_opts.addStretch()
        layout.addLayout(org_opts)

        # Preview text
        self.org_preview_text = QTextEdit()
        self.org_preview_text.setToolTip(self._tr(
            "Preview of file organization changes before execution",
            "Aperçu des changements d'organisation de fichiers avant exécution"
        ))
        self.org_preview_text.setReadOnly(True)
        self.org_preview_text.setFont(get_mono_font(9))
        self.org_preview_text.setPlaceholderText(self._tr(
            "Click 'Preview' to see the planned file organization...",
            "Cliquez 'Aperçu' pour voir l'organisation planifiée..."
        ))
        layout.addWidget(self.org_preview_text, 1)

        # Progress + Buttons row
        org_action_row = QHBoxLayout()

        self.org_progress = QProgressBar()
        self.org_progress.setToolTip(self._tr(
            "File organization progress",
            "Progression de l'organisation des fichiers"
        ))
        self.org_progress.setVisible(False)
        org_action_row.addWidget(self.org_progress, 1)

        self.org_preview_btn = QPushButton(self._tr("👁️ Preview", "👁️ Aperçu"))
        self.org_preview_btn.setToolTip(self._tr(
            "Preview file organization without making changes",
            "Prévisualiser l'organisation des fichiers sans faire de changements"
        ))
        self.org_preview_btn.clicked.connect(self._preview_organization)
        org_action_row.addWidget(self.org_preview_btn)

        self.org_execute_btn = QPushButton(self._tr("▶️ Organize", "▶️ Organiser"))
        self.org_execute_btn.setToolTip(self._tr(
            "Execute file organization (move or copy files)",
            "Exécuter l'organisation des fichiers (déplacer ou copier)"
        ))
        self.org_execute_btn.setProperty("accent", True)
        self.org_execute_btn.clicked.connect(self._execute_organization)
        org_action_row.addWidget(self.org_execute_btn)

        layout.addLayout(org_action_row)

        self.sub_tabs.addTab(tab, self._tr("📂 Organization", "📂 Organisation"))

    # ── Slots / Logic (unchanged) ──

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._tr("Select Folder", "Sélectionner Dossier"))
        if folder:
            self.folder_input.setText(folder)

    def _analyze_storage(self):
        """Analyze disk space usage"""
        folder = self.folder_input.text().strip()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, self._tr("Warning", "Avertissement"),
                self._tr("Please select a valid folder.", "Veuillez sélectionner un dossier valide."))
            return

        self.analyze_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.worker = UnifiedWorker()
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.set_single_job(WorkerJob(
            job_type=JobType.DISK_ANALYSIS,
            params={'folder': folder}
        ))
        self.worker.start()

    def _on_progress(self, current, total, phase):
        if total > 0:
            self.progress_bar.setValue(int(current * 100 / total))

    def _on_finished(self, success, message, result):
        self.analyze_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        if success and result:
            self.storage_stats = result
            self._display_breakdown(result)
            self._generate_recommendations(result)
            self._display_details(result)
            self.compress_btn.setEnabled(result.get('fits_count', 0) > 0)
        elif not success:
            self.reco_text.setText(f"Error: {message}")

    def _display_breakdown(self, stats):
        """Display storage breakdown table"""
        formats = [
            ("FITS (.fits/.fit)", stats.get('fits_count', 0), stats.get('fits_size', 0), '#b8a890'),
            ("XISF (.xisf)", stats.get('xisf_count', 0), stats.get('xisf_size', 0), '#90a8b8'),
            ("Compressed (.fz)", stats.get('fz_count', 0), stats.get('fz_size', 0), '#88b8a0'),
            (self._tr("Other", "Autres"), stats.get('other_count', 0), stats.get('other_size', 0), '#909098'),
        ]

        total_size = stats.get('total_size', 1)
        if total_size == 0:
            total_size = 1

        self.breakdown_table.setRowCount(len(formats))
        for i, (name, count, size, color) in enumerate(formats):
            pct = (size / total_size * 100) if total_size > 0 else 0

            name_item = QTableWidgetItem(name)
            name_item.setForeground(QColor(color))
            self.breakdown_table.setItem(i, 0, name_item)
            self.breakdown_table.setItem(i, 1, QTableWidgetItem(f"{count:,}"))
            self.breakdown_table.setItem(i, 2, QTableWidgetItem(self._format_size(size)))

            pct_item = QTableWidgetItem(f"{pct:.1f}%")
            if pct > 50:
                pct_item.setForeground(QColor('#b8a880'))
            self.breakdown_table.setItem(i, 3, pct_item)

        self.total_label.setText(
            f"Total: {stats.get('total_count', 0):,} "
            f"{self._tr('files', 'fichiers')} - {self._format_size(stats.get('total_size', 0))}"
        )

    def _generate_recommendations(self, stats):
        """Generate optimization recommendations"""
        reco = []

        fits_size = stats.get('fits_size', 0)
        fits_count = stats.get('fits_count', 0)
        xisf_size = stats.get('xisf_size', 0)
        total_size = stats.get('total_size', 0)

        reco.append(f"{'='*55}")
        reco.append(self._tr("  OPTIMIZATION RECOMMENDATIONS", "  RECOMMANDATIONS D'OPTIMISATION"))
        reco.append(f"{'='*55}")
        reco.append("")

        if fits_count > 0:
            estimated_savings = fits_size * 0.50  # ~50% with zlib_6
            reco.append(self._tr(
                f"  1. COMPRESS FITS → XISF (zlib_6 recommended)",
                f"  1. COMPRESSER FITS → XISF (zlib_6 recommandé)"
            ))
            reco.append(f"     {fits_count:,} FITS files = {self._format_size(fits_size)}")
            reco.append(self._tr(
                f"     Estimated savings: ~{self._format_size(int(estimated_savings))} ({50}%)",
                f"     Économie estimée: ~{self._format_size(int(estimated_savings))} ({50}%)"
            ))
            reco.append("")

        if xisf_size > 0:
            # Check if XISF files could be recompressed with better codec
            reco.append(self._tr(
                f"  2. RECOMPRESS XISF (consider zstd_10 for better ratio)",
                f"  2. RECOMPRESSER XISF (considérer zstd_10 pour meilleur ratio)"
            ))
            reco.append(f"     {stats.get('xisf_count', 0):,} XISF files = {self._format_size(xisf_size)}")
            extra_savings = xisf_size * 0.15  # ~15% additional with zstd
            reco.append(self._tr(
                f"     Potential additional savings: ~{self._format_size(int(extra_savings))}",
                f"     Économie potentielle supplémentaire: ~{self._format_size(int(extra_savings))}"
            ))
            reco.append("")

        if total_size > 500 * 1024**3:  # > 500 GB
            reco.append(self._tr(
                f"  3. ARCHIVE OLD CALIBRATION DATA",
                f"  3. ARCHIVER ANCIENNES DONNÉES DE CALIBRATION"
            ))
            reco.append(self._tr(
                "     Consider moving calibration files older than 6 months to cold storage.",
                "     Envisagez de déplacer les fichiers de calibration de plus de 6 mois."
            ))
            reco.append("")

        if total_size > 1024**4:  # > 1 TB
            reco.append(self._tr(
                f"  4. CONSIDER TIERED STORAGE",
                f"  4. ENVISAGER STOCKAGE HIÉRARCHISÉ"
            ))
            reco.append(self._tr(
                "     SSD for current projects, HDD for archive.",
                "     SSD pour projets en cours, HDD pour archives."
            ))
            reco.append("")

        # Summary
        total_potential_savings = fits_size * 0.50
        if total_potential_savings > 0:
            reco.append(f"{'─'*55}")
            reco.append(self._tr(
                f"  TOTAL POTENTIAL SAVINGS: ~{self._format_size(int(total_potential_savings))}",
                f"  ÉCONOMIE POTENTIELLE TOTALE: ~{self._format_size(int(total_potential_savings))}"
            ))

        if not reco or len(reco) <= 4:
            reco.append(self._tr(
                "  Your storage is already well optimized!",
                "  Votre stockage est déjà bien optimisé!"
            ))

        self.reco_text.setPlainText('\n'.join(reco))

    def _display_details(self, stats):
        """Display storage details table"""
        total_size = stats.get('total_size', 0)

        # Detect storage type
        folder = self.folder_input.text().strip()
        storage_type = self._detect_storage_type(folder)

        details = [
            (self._tr("Storage Type", "Type Stockage"), storage_type,
             "✓" if 'SSD' in storage_type else
             self._tr("⚠ Network: limit workers, higher latency", "⚠ Réseau : limiter les workers, latence élevée") if 'Network' in storage_type or 'Réseau' in storage_type else
             self._tr("⚠ HDD slower for parallel I/O", "⚠ HDD plus lent pour les E/S parallèles")),
            (self._tr("Total Files", "Total Fichiers"), f"{stats.get('total_count', 0):,}", ""),
            (self._tr("Total Size", "Taille Totale"), self._format_size(total_size), ""),
            (self._tr("FITS Files", "Fichiers FITS"), f"{stats.get('fits_count', 0):,}", ""),
            (self._tr("XISF Files", "Fichiers XISF"), f"{stats.get('xisf_count', 0):,}", ""),
            (self._tr("Compressed (.fz)", "Compressés (.fz)"), f"{stats.get('fz_count', 0):,}", ""),
            (self._tr("Avg File Size", "Taille Moy. Fichier"),
             self._format_size(total_size // max(stats.get('total_count', 1), 1)), ""),
        ]

        self.details_table.setRowCount(len(details))
        for i, (metric, value, status) in enumerate(details):
            self.details_table.setItem(i, 0, QTableWidgetItem(metric))
            self.details_table.setItem(i, 1, QTableWidgetItem(value))

            status_item = QTableWidgetItem(status)
            if status.startswith("✓"):
                status_item.setForeground(QColor('#88b098'))
            elif status.startswith("⚠"):
                status_item.setForeground(QColor('#b8a880'))
            self.details_table.setItem(i, 2, status_item)

    def _detect_storage_type(self, folder):
        """Detect if folder is on SSD, HDD, or Network/NAS (per-path detection)"""
        try:
            from core.config import get_config
            config = get_config()
            # Use per-path detection (not cached system detection)
            storage = config.detect_path_storage_type(folder) if folder else config.system_caps.get('storage_type', 'ssd')
            if storage == 'network':
                return self._tr("Network (NAS/SMB/NFS)", "Réseau (NAS/SMB/NFS)")
            elif storage == 'ssd':
                return "SSD (NVMe/SATA)"
            elif storage == 'hdd':
                return "HDD (Mechanical)"
            return self._tr("Unknown", "Inconnu")
        except Exception:
            return self._tr("Unknown", "Inconnu")

    def _populate_org_presets(self):
        """Populate the organization preset combo"""
        try:
            from modules.file_organizer import ORGANIZATION_PRESETS
            lang_key = 'fr' if self.lang == 'fr' else 'en'
            for key, info in ORGANIZATION_PRESETS.items():
                self.org_preset_combo.addItem(info.get(lang_key, info.get('en', key)), key)
        except ImportError:
            self.org_preset_combo.addItem(self._tr("By Target", "Par Cible"), "by_target")

    def _browse_org_dest(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._tr("Select Destination", "Sélectionner Destination"))
        if folder:
            self.org_dest_input.setText(folder)

    def _preview_organization(self):
        """Preview the file organization plan"""
        source = self.folder_input.text().strip()
        dest = self.org_dest_input.text().strip()
        preset = self.org_preset_combo.currentData() or 'by_target'

        if not source or not os.path.isdir(source):
            QMessageBox.warning(self, self._tr("Warning", "Avertissement"),
                self._tr("Please select a valid source folder first (analyze storage).",
                         "Veuillez d'abord sélectionner un dossier source valide (analyser stockage)."))
            return

        if not dest:
            QMessageBox.warning(self, self._tr("Warning", "Avertissement"),
                self._tr("Please select a destination folder.",
                         "Veuillez sélectionner un dossier destination."))
            return

        self.org_preview_btn.setEnabled(False)
        self.org_preview_text.setText(self._tr("Scanning files...", "Analyse des fichiers..."))

        def _do_preview():
            try:
                from modules.file_organizer import plan_organization, get_organization_summary
                plan = plan_organization(source, dest, preset)
                summary = get_organization_summary(plan)

                lines = []
                lines.append(self._tr("ORGANIZATION PREVIEW", "APERÇU D'ORGANISATION"))
                lines.append(f"{'='*50}")
                lines.append(self._tr(
                    f"Files to organize: {summary['file_count']}",
                    f"Fichiers à organiser : {summary['file_count']}"))
                lines.append(self._tr(
                    f"Folders to create: {summary['folder_count']}",
                    f"Dossiers à créer : {summary['folder_count']}"))
                lines.append(self._tr(
                    f"Targets found: {summary['target_count']}",
                    f"Cibles trouvées : {summary['target_count']}"))
                lines.append(self._tr(
                    f"Total size: {summary['total_size_gb']:.2f} GB",
                    f"Taille totale : {summary['total_size_gb']:.2f} Go"))
                lines.append("")

                # Show first 20 moves as sample
                sample = plan[:20]
                lines.append(self._tr("Sample of planned moves:", "Échantillon des déplacements :"))
                for src, dst in sample:
                    rel_src = os.path.basename(src)
                    rel_dst = os.path.relpath(dst, dest)
                    lines.append(f"  {rel_src} → {rel_dst}")
                if len(plan) > 20:
                    lines.append(f"  ... {self._tr(f'and {len(plan)-20} more', f'et {len(plan)-20} de plus')}")

                result_text = '\n'.join(lines)
                self._org_plan = plan
                self._preview_result_signal.emit(result_text)
            except Exception as e:
                self._preview_result_signal.emit(f"Error: {e}")

        self._org_plan = []
        threading.Thread(target=_do_preview, daemon=True).start()

    def _show_preview_result(self, text):
        self.org_preview_btn.setEnabled(True)
        self.org_preview_text.setPlainText(text)

    def _execute_organization(self):
        """Execute the file organization"""
        if not hasattr(self, '_org_plan') or not self._org_plan:
            QMessageBox.information(self, self._tr("Info", "Info"),
                self._tr("Run a preview first.", "Lancez d'abord un aperçu."))
            return

        copy_mode = self.org_copy_mode.isChecked()
        mode_str = self._tr("COPY", "COPIER") if copy_mode else self._tr("MOVE", "DÉPLACER")
        reply = QMessageBox.question(self,
            self._tr("Confirm Organization", "Confirmer Organisation"),
            self._tr(
                f"{mode_str} {len(self._org_plan)} files to the destination folder?",
                f"{mode_str} {len(self._org_plan)} fichiers vers le dossier destination ?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.org_execute_btn.setEnabled(False)
        self.org_progress.setVisible(True)
        self.org_progress.setValue(0)
        plan = self._org_plan

        def _do_organize():
            try:
                from modules.file_organizer import execute_organization

                def on_progress(current, total, msg):
                    pct = int(current * 100 / max(total, 1))
                    self._organize_progress_signal.emit(pct)

                result = execute_organization(plan, copy_mode=copy_mode, progress_callback=on_progress)
                moved = result.get('moved', 0)
                errors = result.get('errors', 0)
                self._organize_done_signal.emit(moved, errors, '')
            except Exception as e:
                self._organize_done_signal.emit(0, 0, str(e))

        threading.Thread(target=_do_organize, daemon=True).start()

    def _on_organize_done(self, success=0, errors=0, error_msg=None):
        self.org_execute_btn.setEnabled(True)
        self.org_progress.setVisible(False)
        if error_msg:
            QMessageBox.warning(self, self._tr("Error", "Erreur"), error_msg)
        else:
            QMessageBox.information(self,
                self._tr("Organization Complete", "Organisation Terminée"),
                self._tr(
                    f"Successfully organized {success} files.\nErrors: {errors}",
                    f"{success} fichiers organisés avec succès.\nErreurs : {errors}"
                ))

    def _compress_fits(self):
        """Redirect to compression tab"""
        QMessageBox.information(self, self._tr("Info", "Info"),
            self._tr(
                "Switch to the Compression tab to compress your FITS files.\n"
                "Recommended profile: zlib_6 (50% space savings)",
                "Passez à l'onglet Compression pour compresser vos fichiers FITS.\n"
                "Profil recommandé: zlib_6 (50% d'économie d'espace)"
            ))

    def _export_report(self):
        """Export storage report"""
        if not self.storage_stats:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, self._tr("Export Report", "Exporter Rapport"), "storage_report.txt", "Text Files (*.txt)")
        if not path:
            return

        with open(path, 'w', encoding='utf-8') as f:
            f.write(self._tr("ASTROMANAGER - STORAGE ANALYSIS REPORT\n", "ASTROMANAGER - RAPPORT D'ANALYSE DE STOCKAGE\n"))
            f.write(f"{'='*55}\n\n")
            f.write(f"Folder: {self.folder_input.text()}\n\n")
            f.write(self._tr("BREAKDOWN:\n", "RÉPARTITION :\n"))
            f.write(f"  FITS:  {self.storage_stats.get('fits_count', 0):>8,} files  "
                   f"{self._format_size(self.storage_stats.get('fits_size', 0)):>12}\n")
            f.write(f"  XISF:  {self.storage_stats.get('xisf_count', 0):>8,} files  "
                   f"{self._format_size(self.storage_stats.get('xisf_size', 0)):>12}\n")
            f.write(f"  FZ:    {self.storage_stats.get('fz_count', 0):>8,} files  "
                   f"{self._format_size(self.storage_stats.get('fz_size', 0)):>12}\n")
            f.write(f"  Other: {self.storage_stats.get('other_count', 0):>8,} files  "
                   f"{self._format_size(self.storage_stats.get('other_size', 0)):>12}\n")
            f.write(f"\n  TOTAL: {self.storage_stats.get('total_count', 0):>8,} files  "
                   f"{self._format_size(self.storage_stats.get('total_size', 0)):>12}\n")
            f.write(self._tr("\n\nRECOMMENDATIONS:\n", "\n\nRECOMMANDATIONS :\n"))
            f.write(self.reco_text.toPlainText())

        QMessageBox.information(self, self._tr("Export", "Export"),
            self._tr(f"Report saved to {path}", f"Rapport sauvegardé dans {path}"))
