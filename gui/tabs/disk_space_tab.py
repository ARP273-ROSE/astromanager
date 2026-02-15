#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - DISK SPACE TAB
================================================================================
Storage analysis, optimization recommendations, duplicate detection,
format breakdown, and cleanup actions.

Interactive recommendation cards with PixInsight safety protection.
================================================================================
"""

import os
import time
import shutil
import threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QProgressBar, QMessageBox, QAbstractItemView, QComboBox,
    QCheckBox, QTabWidget, QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from core.workers import UnifiedWorker, WorkerJob, JobType
from core.signals import signals
from gui.theme import get_mono_font
from core.config import get_config


class DiskSpaceTab(QWidget):
    """Disk Space tab - Storage analysis and optimization"""

    # Thread-safe signals for background operations
    _preview_result_signal = pyqtSignal(str)
    _organize_progress_signal = pyqtSignal(int)
    _organize_done_signal = pyqtSignal(int, int, str)
    _archive_done_signal = pyqtSignal(int, int, str)  # moved, errors, error_msg

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
        self._pending_actions = []
        self._reco_cards = []  # list of card dicts for execution
        # Connect thread-safe signals
        self._preview_result_signal.connect(self._show_preview_result)
        self._organize_progress_signal.connect(lambda pct: self.org_progress.setValue(pct))
        self._organize_done_signal.connect(
            lambda m, e, msg: self._on_organize_done(success=m, errors=e, error_msg=msg if msg else None))
        self._archive_done_signal.connect(self._on_archive_done)
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
        """Build the Recommendations sub-tab with interactive cards."""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setSpacing(6)
        tab_layout.setContentsMargins(6, 6, 6, 6)

        # ── Scrollable card area ──
        self.reco_scroll = QScrollArea()
        self.reco_scroll.setWidgetResizable(True)
        self.reco_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.reco_container = QWidget()
        self.reco_cards_layout = QVBoxLayout(self.reco_container)
        self.reco_cards_layout.setSpacing(8)
        self.reco_cards_layout.setContentsMargins(2, 2, 2, 2)

        # Placeholder label
        self._reco_placeholder = QLabel(self._tr(
            "Run storage analysis to see optimization recommendations.",
            "Lancez l'analyse de stockage pour voir les recommandations."
        ))
        self._reco_placeholder.setStyleSheet("color: #7a8498; padding: 20px;")
        self._reco_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reco_cards_layout.addWidget(self._reco_placeholder)
        self.reco_cards_layout.addStretch()

        self.reco_scroll.setWidget(self.reco_container)
        tab_layout.addWidget(self.reco_scroll, 1)

        # ── Action buttons bar ──
        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        self.reco_apply_btn = QPushButton(self._tr(
            "▶ Apply Selected", "▶ Appliquer les sélectionnées"))
        self.reco_apply_btn.setToolTip(self._tr(
            "Execute the selected optimization actions",
            "Exécuter les actions d'optimisation sélectionnées"
        ))
        self.reco_apply_btn.setProperty("accent", True)
        self.reco_apply_btn.setEnabled(False)
        self.reco_apply_btn.clicked.connect(self._apply_selected_actions)
        action_bar.addWidget(self.reco_apply_btn)

        self.reco_stop_btn = QPushButton(self._tr("⏹ Stop", "⏹ Arrêter"))
        self.reco_stop_btn.setToolTip(self._tr(
            "Stop the current operation",
            "Arrêter l'opération en cours"
        ))
        self.reco_stop_btn.setStyleSheet("QPushButton { color: #b89090; }")
        self.reco_stop_btn.setVisible(False)
        self.reco_stop_btn.clicked.connect(self._stop_actions)
        action_bar.addWidget(self.reco_stop_btn)

        action_bar.addStretch()
        tab_layout.addLayout(action_bar)

        # ── Execution progress bar ──
        self.reco_progress = QProgressBar()
        self.reco_progress.setVisible(False)
        tab_layout.addWidget(self.reco_progress)

        # ── Execution console ──
        self.reco_console = QTextEdit()
        self.reco_console.setReadOnly(True)
        self.reco_console.setFont(get_mono_font(9))
        self.reco_console.setMaximumHeight(150)
        self.reco_console.setVisible(False)
        tab_layout.addWidget(self.reco_console)

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

    # =========================================================================
    # RECOMMENDATION CARDS
    # =========================================================================

    def _clear_reco_cards(self):
        """Remove all cards from the recommendations layout."""
        while self.reco_cards_layout.count():
            item = self.reco_cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._reco_cards = []

    def _build_recommendation_cards(self, stats):
        """Build interactive recommendation cards from analysis stats."""
        self._clear_reco_cards()

        fits_count = stats.get('fits_count', 0)
        fits_size = stats.get('fits_size', 0)
        xisf_recomp_count = stats.get('xisf_recompressible_count', 0)
        xisf_recomp_size = stats.get('xisf_recompressible_size', 0)
        xisf_pi_count = stats.get('xisf_pixinsight_count', 0)
        total_size = stats.get('total_size', 0)

        # Filter calibration files older than 6 months
        six_months_ago = time.time() - (6 * 30 * 24 * 3600)
        old_calib_files = [(fp, sz, mt) for fp, sz, mt in stats.get('calibration_files', [])
                           if mt > 0 and mt < six_months_ago]
        old_calib_size = sum(sz for _, sz, _ in old_calib_files)

        has_any_card = False

        # ── Card 1: Compress FITS → XISF ──
        if fits_count > 0:
            has_any_card = True
            estimated_savings = int(fits_size * 0.50)
            estimated_after = fits_size - estimated_savings

            card = QGroupBox()
            card.setStyleSheet("""
                QGroupBox {
                    border: 1px solid #2a3248;
                    border-radius: 6px;
                    padding: 8px;
                    margin-top: 4px;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)

            # Line 1: Checkbox + Title + Count
            line1 = QHBoxLayout()
            cb = QCheckBox()
            cb.setChecked(True)
            line1.addWidget(cb)
            title = QLabel(self._tr(
                f"<b style='color:#94b8c8'>Compress FITS → XISF</b>  "
                f"<span style='color:#7a8498'>({fits_count:,} {self._tr('files', 'fichiers')})</span>",
                f"<b style='color:#94b8c8'>Compresser FITS → XISF</b>  "
                f"<span style='color:#7a8498'>({fits_count:,} fichiers)</span>"
            ))
            title.setTextFormat(Qt.TextFormat.RichText)
            line1.addWidget(title, 1)
            card_layout.addLayout(line1)

            # Line 2: Size info
            size_label = QLabel(self._tr(
                f"  {self._format_size(fits_size)} → ~{self._format_size(estimated_after)}  "
                f"<span style='color:#88b098'>(-{self._format_size(estimated_savings)}, ~50%)</span>",
                f"  {self._format_size(fits_size)} → ~{self._format_size(estimated_after)}  "
                f"<span style='color:#88b098'>(-{self._format_size(estimated_savings)}, ~50%)</span>"
            ))
            size_label.setTextFormat(Qt.TextFormat.RichText)
            card_layout.addWidget(size_label)

            # Line 3: Profile info
            profile_label = QLabel(self._tr(
                "  Profile: zlib_6 (recommended) — integrity verification enabled",
                "  Profil : zlib_6 (recommandé) — vérification d'intégrité activée"
            ))
            profile_label.setStyleSheet("color: #7a8498; font-size: 9pt;")
            card_layout.addWidget(profile_label)

            # Line 4: Backup folder
            backup_row = QHBoxLayout()
            backup_row.addWidget(QLabel(self._tr("  Backup folder:", "  Dossier backup :")))
            backup_input = QLineEdit()
            backup_input.setPlaceholderText(self._tr(
                "Optional: move originals here after conversion",
                "Optionnel : déplacer les originaux ici après conversion"
            ))
            backup_row.addWidget(backup_input, 1)
            backup_browse = QPushButton(self._tr("Browse...", "Parcourir..."))
            backup_browse.clicked.connect(
                lambda checked, inp=backup_input: self._browse_for_line_edit(inp))
            backup_row.addWidget(backup_browse)
            card_layout.addLayout(backup_row)

            self.reco_cards_layout.addWidget(card)
            self._reco_cards.append({
                'type': 'compress_fits',
                'checkbox': cb,
                'backup_input': backup_input,
                'files': stats.get('fits_files', []),
                'card': card,
            })

        # ── Card 2: Recompress XISF → zstd ──
        if xisf_recomp_count > 0:
            has_any_card = True
            estimated_savings = int(xisf_recomp_size * 0.15)
            estimated_after = xisf_recomp_size - estimated_savings

            card = QGroupBox()
            card.setStyleSheet("""
                QGroupBox {
                    border: 1px solid #2a3248;
                    border-radius: 6px;
                    padding: 8px;
                    margin-top: 4px;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)

            # Line 1: Checkbox + Title
            line1 = QHBoxLayout()
            cb = QCheckBox()
            cb.setChecked(True)
            line1.addWidget(cb)
            title = QLabel(self._tr(
                f"<b style='color:#94b8c8'>Recompress XISF → zstd</b>  "
                f"<span style='color:#7a8498'>({xisf_recomp_count:,} {self._tr('files', 'fichiers')})</span>",
                f"<b style='color:#94b8c8'>Recompresser XISF → zstd</b>  "
                f"<span style='color:#7a8498'>({xisf_recomp_count:,} fichiers)</span>"
            ))
            title.setTextFormat(Qt.TextFormat.RichText)
            line1.addWidget(title, 1)
            card_layout.addLayout(line1)

            # Line 2: Size info
            size_label = QLabel(self._tr(
                f"  {self._format_size(xisf_recomp_size)} → ~{self._format_size(estimated_after)}  "
                f"<span style='color:#88b098'>(-{self._format_size(estimated_savings)}, ~15%)</span>",
                f"  {self._format_size(xisf_recomp_size)} → ~{self._format_size(estimated_after)}  "
                f"<span style='color:#88b098'>(-{self._format_size(estimated_savings)}, ~15%)</span>"
            ))
            size_label.setTextFormat(Qt.TextFormat.RichText)
            card_layout.addWidget(size_label)

            # Line 3: PixInsight exclusion warning
            if xisf_pi_count > 0:
                pi_label = QLabel(self._tr(
                    f"  <span style='color:#b8a880'>{xisf_pi_count:,} PixInsight files excluded (not touched)</span>",
                    f"  <span style='color:#b8a880'>{xisf_pi_count:,} fichiers PixInsight exclus (non touchés)</span>"
                ))
                pi_label.setTextFormat(Qt.TextFormat.RichText)
                card_layout.addWidget(pi_label)

            # Line 4: Profile info
            profile_label = QLabel(self._tr(
                "  Profile: zstd_10 — in-place via atomic .tmp_recomp + os.replace()",
                "  Profil : zstd_10 — sur place via .tmp_recomp atomique + os.replace()"
            ))
            profile_label.setStyleSheet("color: #7a8498; font-size: 9pt;")
            card_layout.addWidget(profile_label)

            self.reco_cards_layout.addWidget(card)
            self._reco_cards.append({
                'type': 'recompress_xisf',
                'checkbox': cb,
                'files': stats.get('xisf_recompressible_files', []),
                'card': card,
            })

        # ── Card 3: Archive old calibration ──
        if old_calib_files:
            has_any_card = True

            card = QGroupBox()
            card.setStyleSheet("""
                QGroupBox {
                    border: 1px solid #2a3248;
                    border-radius: 6px;
                    padding: 8px;
                    margin-top: 4px;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)

            # Line 1: Checkbox + Title
            line1 = QHBoxLayout()
            cb = QCheckBox()
            cb.setChecked(False)  # Off by default — destructive-ish
            line1.addWidget(cb)
            title = QLabel(self._tr(
                f"<b style='color:#94b8c8'>Archive Old Calibration Data</b>  "
                f"<span style='color:#7a8498'>({len(old_calib_files):,} files, > 6 months)</span>",
                f"<b style='color:#94b8c8'>Archiver anciennes données de calibration</b>  "
                f"<span style='color:#7a8498'>({len(old_calib_files):,} fichiers, > 6 mois)</span>"
            ))
            title.setTextFormat(Qt.TextFormat.RichText)
            line1.addWidget(title, 1)
            card_layout.addLayout(line1)

            # Line 2: Size info
            size_label = QLabel(self._tr(
                f"  Total size: {self._format_size(old_calib_size)}",
                f"  Taille totale : {self._format_size(old_calib_size)}"
            ))
            size_label.setStyleSheet("color: #7a8498;")
            card_layout.addWidget(size_label)

            # Line 3: Archive destination
            archive_row = QHBoxLayout()
            archive_row.addWidget(QLabel(self._tr("  Archive folder:", "  Dossier archive :")))
            source_folder = self.folder_input.text().strip()
            default_archive = os.path.join(source_folder, '_archived_calibration') if source_folder else ''
            archive_input = QLineEdit(default_archive)
            archive_input.setPlaceholderText(self._tr(
                "Destination for archived calibration files",
                "Destination pour les fichiers de calibration archivés"
            ))
            archive_row.addWidget(archive_input, 1)
            archive_browse = QPushButton(self._tr("Browse...", "Parcourir..."))
            archive_browse.clicked.connect(
                lambda checked, inp=archive_input: self._browse_for_line_edit(inp))
            archive_row.addWidget(archive_browse)
            card_layout.addLayout(archive_row)

            self.reco_cards_layout.addWidget(card)
            self._reco_cards.append({
                'type': 'archive_calibration',
                'checkbox': cb,
                'archive_input': archive_input,
                'files': old_calib_files,
                'card': card,
            })

        # ── Card 4: Tiered storage (info only) ──
        if total_size > 1024**4:  # > 1 TB
            has_any_card = True

            card = QGroupBox()
            card.setStyleSheet("""
                QGroupBox {
                    border: 1px solid #2a3248;
                    border-radius: 6px;
                    padding: 8px;
                    margin-top: 4px;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)

            title = QLabel(self._tr(
                "<b style='color:#90a8b8'>ℹ️ Consider Tiered Storage</b>",
                "<b style='color:#90a8b8'>ℹ️ Envisager un stockage hiérarchisé</b>"
            ))
            title.setTextFormat(Qt.TextFormat.RichText)
            card_layout.addWidget(title)

            info = QLabel(self._tr(
                f"  Your data exceeds {self._format_size(total_size)}. Consider:\n"
                "  - SSD (NVMe) for current projects and active processing\n"
                "  - HDD (RAID) for archive and completed sessions\n"
                "  - NAS/Cloud for long-term backup",
                f"  Vos données dépassent {self._format_size(total_size)}. Considérez :\n"
                "  - SSD (NVMe) pour les projets en cours et traitement actif\n"
                "  - HDD (RAID) pour les archives et sessions terminées\n"
                "  - NAS/Cloud pour la sauvegarde à long terme"
            ))
            info.setStyleSheet("color: #7a8498;")
            card_layout.addWidget(info)

            self.reco_cards_layout.addWidget(card)
            # No entry in _reco_cards — info only, not actionable

        # ── Safety banner ──
        if has_any_card:
            safety = QLabel(self._tr(
                "<div style='background: rgba(136,176,152,0.1); border: 1px solid #88b098; "
                "border-radius: 4px; padding: 8px; color: #88b098;'>"
                "🛡️ <b>Non-destructive operations</b> — FITS originals can be backed up, "
                "XISF recompression uses atomic temp files. "
                "PixInsight-processed files are never modified.</div>",
                "<div style='background: rgba(136,176,152,0.1); border: 1px solid #88b098; "
                "border-radius: 4px; padding: 8px; color: #88b098;'>"
                "🛡️ <b>Opérations non-destructives</b> — Les originaux FITS peuvent être sauvegardés, "
                "la recompression XISF utilise des fichiers temporaires atomiques. "
                "Les fichiers traités par PixInsight ne sont jamais modifiés.</div>"
            ))
            safety.setTextFormat(Qt.TextFormat.RichText)
            safety.setWordWrap(True)
            self.reco_cards_layout.addWidget(safety)

            self.reco_apply_btn.setEnabled(True)
        else:
            # No recommendations
            no_reco = QLabel(self._tr(
                "Your storage is already well optimized!",
                "Votre stockage est déjà bien optimisé !"
            ))
            no_reco.setStyleSheet("color: #88b098; padding: 20px;")
            no_reco.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.reco_cards_layout.addWidget(no_reco)
            self.reco_apply_btn.setEnabled(False)

        self.reco_cards_layout.addStretch()

    def _browse_for_line_edit(self, line_edit):
        """Open folder browser and set result in the given QLineEdit."""
        folder = QFileDialog.getExistingDirectory(
            self, self._tr("Select Folder", "Sélectionner Dossier"))
        if folder:
            line_edit.setText(folder)

    # =========================================================================
    # ACTION EXECUTION PIPELINE
    # =========================================================================

    def _apply_selected_actions(self):
        """Collect selected cards and launch sequential execution."""
        selected = []
        for card_info in self._reco_cards:
            if card_info['checkbox'].isChecked():
                selected.append(card_info)

        if not selected:
            QMessageBox.information(self, self._tr("Info", "Info"),
                self._tr("No actions selected.", "Aucune action sélectionnée."))
            return

        # Build confirmation message
        lines = [self._tr("The following actions will be executed:",
                           "Les actions suivantes seront exécutées :"), ""]
        for card_info in selected:
            t = card_info['type']
            if t == 'compress_fits':
                n = len(card_info['files'])
                lines.append(self._tr(
                    f"  - Compress {n:,} FITS files → XISF (zlib_6)",
                    f"  - Compresser {n:,} fichiers FITS → XISF (zlib_6)"))
            elif t == 'recompress_xisf':
                n = len(card_info['files'])
                lines.append(self._tr(
                    f"  - Recompress {n:,} XISF files → zstd_10",
                    f"  - Recompresser {n:,} fichiers XISF → zstd_10"))
            elif t == 'archive_calibration':
                n = len(card_info['files'])
                dest = card_info.get('archive_input', None)
                dest_text = dest.text().strip() if dest else '?'
                lines.append(self._tr(
                    f"  - Archive {n:,} calibration files → {dest_text}",
                    f"  - Archiver {n:,} fichiers calibration → {dest_text}"))

        reply = QMessageBox.question(self,
            self._tr("Confirm Actions", "Confirmer les actions"),
            '\n'.join(lines),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Prepare execution state
        self._pending_actions = list(selected)
        self._action_errors = []

        # UI: disable cards, show progress
        self.reco_apply_btn.setEnabled(False)
        self.reco_stop_btn.setVisible(True)
        self.reco_progress.setVisible(True)
        self.reco_progress.setValue(0)
        self.reco_console.setVisible(True)
        self.reco_console.clear()
        self.analyze_btn.setEnabled(False)

        # Disable all checkboxes during execution
        for card_info in self._reco_cards:
            card_info['checkbox'].setEnabled(False)

        self._execute_next_action()

    def _execute_next_action(self):
        """Pop and execute the next pending action."""
        if not self._pending_actions:
            self._on_all_actions_done()
            return

        action = self._pending_actions[0]
        action_type = action['type']

        if action_type == 'compress_fits':
            self._execute_compress_fits(action)
        elif action_type == 'recompress_xisf':
            self._execute_recompress_xisf(action)
        elif action_type == 'archive_calibration':
            self._execute_archive_calibration(action)
        else:
            # Unknown action type, skip
            self._pending_actions.pop(0)
            self._execute_next_action()

    def _execute_compress_fits(self, action):
        """Execute FITS → XISF compression via worker."""
        files = [fp for fp, _size in action['files']]
        backup_folder = action.get('backup_input', None)
        backup_path = backup_folder.text().strip() if backup_folder else ''
        source_folder = self.folder_input.text().strip()

        self.reco_console.append(self._tr(
            f"--- Compressing {len(files):,} FITS files → XISF (zlib_6) ---",
            f"--- Compression de {len(files):,} fichiers FITS → XISF (zlib_6) ---"))

        self.worker = UnifiedWorker()
        self.worker.progress_signal.connect(self._on_reco_progress)
        self.worker.output_signal.connect(self._on_reco_output)
        self.worker.finished_signal.connect(self._on_action_finished)
        self.worker.set_single_job(WorkerJob(
            job_type=JobType.COMPRESSION,
            params={
                'files': files,
                'source_folder': source_folder,
                'backup_folder': backup_path,
                'profile': 'zlib_6',
                'output_format': 'xisf',
                'verify_integrity': True,
                'lang': self.lang,
            }
        ))
        self.worker.start()

    def _execute_recompress_xisf(self, action):
        """Execute XISF recompression via worker."""
        files = [fp for fp, _size, _codec in action['files']]
        source_folder = self.folder_input.text().strip()

        self.reco_console.append(self._tr(
            f"--- Recompressing {len(files):,} XISF files → zstd_10 ---",
            f"--- Recompression de {len(files):,} fichiers XISF → zstd_10 ---"))

        self.worker = UnifiedWorker()
        self.worker.progress_signal.connect(self._on_reco_progress)
        self.worker.output_signal.connect(self._on_reco_output)
        self.worker.finished_signal.connect(self._on_action_finished)
        self.worker.set_single_job(WorkerJob(
            job_type=JobType.COMPRESSION,
            params={
                'files': files,
                'source_folder': source_folder,
                'profile': 'zstd_10',
                'output_format': 'xisf',
                'verify_integrity': True,
                'lang': self.lang,
            }
        ))
        self.worker.start()

    def _execute_archive_calibration(self, action):
        """Execute calibration file archiving in a background thread."""
        archive_dest = action.get('archive_input', None)
        dest_path = archive_dest.text().strip() if archive_dest else ''
        if not dest_path:
            self.reco_console.append(self._tr(
                "  Skipping archive: no destination folder specified.",
                "  Archivage ignoré : aucun dossier destination spécifié."))
            self._pending_actions.pop(0)
            self._execute_next_action()
            return

        files = action['files']
        source_folder = self.folder_input.text().strip()

        self.reco_console.append(self._tr(
            f"--- Archiving {len(files):,} calibration files → {dest_path} ---",
            f"--- Archivage de {len(files):,} fichiers calibration → {dest_path} ---"))

        def _do_archive():
            moved = 0
            errors = 0
            error_msgs = []
            for i, (fp, _size, _mtime) in enumerate(files):
                try:
                    rel = os.path.relpath(fp, source_folder)
                    dst = os.path.join(dest_path, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.move(fp, dst)
                    moved += 1
                except Exception as e:
                    errors += 1
                    error_msgs.append(f"{os.path.basename(fp)}: {e}")
            err_msg = '\n'.join(error_msgs[:10]) if error_msgs else ''
            self._archive_done_signal.emit(moved, errors, err_msg)

        threading.Thread(target=_do_archive, daemon=True).start()

    def _on_archive_done(self, moved, errors, error_msg):
        """Handle archive completion."""
        self.reco_console.append(self._tr(
            f"  Archive complete: {moved} moved, {errors} errors",
            f"  Archivage terminé : {moved} déplacés, {errors} erreurs"))
        if error_msg:
            self.reco_console.append(f"  Errors:\n{error_msg}")
        # Pop this action and continue
        if self._pending_actions:
            self._pending_actions.pop(0)
        self._execute_next_action()

    def _on_reco_progress(self, current, total, phase):
        """Update progress bar during recommendation execution."""
        if total > 0:
            self.reco_progress.setValue(int(current * 100 / total))

    def _on_reco_output(self, text):
        """Append worker output to the recommendation console."""
        self.reco_console.append(text.rstrip())
        # Auto-scroll to bottom
        sb = self.reco_console.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_action_finished(self, success, message, result):
        """Handle completion of a single action (compression worker)."""
        if success and result:
            processed = result.get('processed', 0)
            errors = result.get('errors', 0)
            self.reco_console.append(self._tr(
                f"  Done: {processed} processed, {errors} errors",
                f"  Terminé : {processed} traités, {errors} erreurs"))
        elif not success:
            self.reco_console.append(f"  Error: {message}")

        # Pop this action and continue
        if self._pending_actions:
            self._pending_actions.pop(0)
        self._execute_next_action()

    def _on_all_actions_done(self):
        """All selected actions have completed."""
        self.reco_console.append(self._tr(
            "\n✅ All selected actions completed.",
            "\n✅ Toutes les actions sélectionnées sont terminées."))

        # Re-enable UI
        self.reco_apply_btn.setEnabled(True)
        self.reco_stop_btn.setVisible(False)
        self.analyze_btn.setEnabled(True)

        for card_info in self._reco_cards:
            card_info['checkbox'].setEnabled(True)

        QMessageBox.information(self,
            self._tr("Complete", "Terminé"),
            self._tr(
                "All selected optimization actions have been completed.\n"
                "Run a new analysis to see updated results.",
                "Toutes les actions d'optimisation sélectionnées sont terminées.\n"
                "Relancez une analyse pour voir les résultats mis à jour."))

    def _stop_actions(self):
        """Stop the current action and cancel remaining."""
        if self.worker:
            self.worker.stop()
        self._pending_actions.clear()
        self.reco_console.append(self._tr(
            "\n⏹ Stopped by user.",
            "\n⏹ Arrêté par l'utilisateur."))
        self.reco_apply_btn.setEnabled(True)
        self.reco_stop_btn.setVisible(False)
        self.analyze_btn.setEnabled(True)
        for card_info in self._reco_cards:
            card_info['checkbox'].setEnabled(True)

    # =========================================================================
    # RECOMMENDATIONS TEXT (for export report)
    # =========================================================================

    def _generate_recommendations_text(self, stats):
        """Generate optimization recommendations as plain text (for export)."""
        reco = []

        fits_size = stats.get('fits_size', 0)
        fits_count = stats.get('fits_count', 0)
        xisf_recomp_count = stats.get('xisf_recompressible_count', 0)
        xisf_recomp_size = stats.get('xisf_recompressible_size', 0)
        xisf_pi_count = stats.get('xisf_pixinsight_count', 0)
        total_size = stats.get('total_size', 0)

        reco.append(f"{'='*55}")
        reco.append(self._tr("  OPTIMIZATION RECOMMENDATIONS", "  RECOMMANDATIONS D'OPTIMISATION"))
        reco.append(f"{'='*55}")
        reco.append("")

        if fits_count > 0:
            estimated_savings = fits_size * 0.50
            reco.append(self._tr(
                f"  1. COMPRESS FITS → XISF (zlib_6 recommended)",
                f"  1. COMPRESSER FITS → XISF (zlib_6 recommandé)"
            ))
            reco.append(f"     {fits_count:,} FITS files = {self._format_size(fits_size)}")
            reco.append(self._tr(
                f"     Estimated savings: ~{self._format_size(int(estimated_savings))} (~50%)",
                f"     Économie estimée : ~{self._format_size(int(estimated_savings))} (~50%)"
            ))
            reco.append("")

        if xisf_recomp_count > 0:
            extra_savings = xisf_recomp_size * 0.15
            reco.append(self._tr(
                f"  2. RECOMPRESS XISF (zstd_10 for better ratio)",
                f"  2. RECOMPRESSER XISF (zstd_10 pour meilleur ratio)"
            ))
            reco.append(f"     {xisf_recomp_count:,} XISF files = {self._format_size(xisf_recomp_size)}")
            if xisf_pi_count > 0:
                reco.append(self._tr(
                    f"     ({xisf_pi_count:,} PixInsight files excluded)",
                    f"     ({xisf_pi_count:,} fichiers PixInsight exclus)"))
            reco.append(self._tr(
                f"     Potential additional savings: ~{self._format_size(int(extra_savings))}",
                f"     Économie potentielle supplémentaire : ~{self._format_size(int(extra_savings))}"
            ))
            reco.append("")

        six_months_ago = time.time() - (6 * 30 * 24 * 3600)
        old_calib = [(fp, sz, mt) for fp, sz, mt in stats.get('calibration_files', [])
                     if mt > 0 and mt < six_months_ago]
        if old_calib:
            old_size = sum(sz for _, sz, _ in old_calib)
            reco.append(self._tr(
                f"  3. ARCHIVE OLD CALIBRATION DATA",
                f"  3. ARCHIVER ANCIENNES DONNÉES DE CALIBRATION"
            ))
            reco.append(self._tr(
                f"     {len(old_calib):,} files older than 6 months = {self._format_size(old_size)}",
                f"     {len(old_calib):,} fichiers de plus de 6 mois = {self._format_size(old_size)}"
            ))
            reco.append("")

        if total_size > 1024**4:
            reco.append(self._tr(
                f"  4. CONSIDER TIERED STORAGE",
                f"  4. ENVISAGER STOCKAGE HIÉRARCHISÉ"
            ))
            reco.append(self._tr(
                "     SSD for current projects, HDD for archive.",
                "     SSD pour projets en cours, HDD pour archives."
            ))
            reco.append("")

        total_potential_savings = fits_size * 0.50 + xisf_recomp_size * 0.15
        if total_potential_savings > 0:
            reco.append(f"{'─'*55}")
            reco.append(self._tr(
                f"  TOTAL POTENTIAL SAVINGS: ~{self._format_size(int(total_potential_savings))}",
                f"  ÉCONOMIE POTENTIELLE TOTALE : ~{self._format_size(int(total_potential_savings))}"
            ))

        if not reco or len(reco) <= 4:
            reco.append(self._tr(
                "  Your storage is already well optimized!",
                "  Votre stockage est déjà bien optimisé !"
            ))

        return '\n'.join(reco)

    # =========================================================================
    # SLOTS / LOGIC
    # =========================================================================

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
            self._build_recommendation_cards(result)
            self._display_details(result)
        elif not success:
            self._clear_reco_cards()
            error_label = QLabel(f"Error: {message}")
            error_label.setStyleSheet("color: #b89090; padding: 10px;")
            self.reco_cards_layout.addWidget(error_label)
            self.reco_cards_layout.addStretch()

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
            (self._tr("PixInsight Files", "Fichiers PixInsight"),
             f"{stats.get('xisf_pixinsight_count', 0):,}",
             self._tr("🔒 Protected", "🔒 Protégés") if stats.get('xisf_pixinsight_count', 0) > 0 else ""),
            (self._tr("Recompressible XISF", "XISF recompressibles"),
             f"{stats.get('xisf_recompressible_count', 0):,}", ""),
        ]

        self.details_table.setRowCount(len(details))
        for i, (metric, value, status) in enumerate(details):
            self.details_table.setItem(i, 0, QTableWidgetItem(metric))
            self.details_table.setItem(i, 1, QTableWidgetItem(value))

            status_item = QTableWidgetItem(status)
            if "✓" in status or "🔒" in status:
                status_item.setForeground(QColor('#88b098'))
            elif "⚠" in status:
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
            f.write(self._generate_recommendations_text(self.storage_stats))

        QMessageBox.information(self, self._tr("Export", "Export"),
            self._tr(f"Report saved to {path}", f"Rapport sauvegardé dans {path}"))
