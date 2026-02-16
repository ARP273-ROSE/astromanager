#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - ASIAIR IMPORT TAB
================================================================================
One-click ASIAIR workflow: compress FITS → XISF, write telescope/filter
overrides, rename with NINA pattern, optionally organize into directory tree.
================================================================================
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox,
    QPushButton, QLabel, QLineEdit, QFileDialog, QRadioButton,
    QButtonGroup, QTextEdit, QTabWidget, QScrollArea, QFrame,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy, QSpacerItem, QAbstractItemView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from core.workers import UnifiedWorker, WorkerJob, JobType
from core.signals import signals
from core.config import get_config
from gui.theme import get_mono_font

# Import compression profiles
try:
    from modules.compression import COMPRESSION_PROFILES
    COMPRESSION_AVAILABLE = True
except ImportError:
    COMPRESSION_AVAILABLE = False
    COMPRESSION_PROFILES = {}

# Import default filename pattern
try:
    from modules.header_editor import DEFAULT_FILENAME_PATTERN
except ImportError:
    DEFAULT_FILENAME_PATTERN = (
        "$$IMAGETYPE$$_$$TARGETNAME$$_$$DATETIME$$_$$FILTER$$_"
        "$$BINNING$$_$$EXPOSURETIME$$s_$$ROTATORANGLE$$deg_"
        "$$SENSORTEMP$$_$$TELESCOPE$$_$$CAMERA$$"
    )


class ASIAIRImportTab(QWidget):
    """ASIAIR Import tab — compress, override headers, rename, organize."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.config = get_config()
        self.lang = self.config.get('application.language', 'auto')
        if self.lang == 'auto':
            from core.i18n import get_lang
            self.lang = get_lang()

        # Load user telescope/filter options from config
        self.telescope_options = self.config.get(
            'asiair_import.telescope_options', [])
        self.filter_options = self.config.get(
            'asiair_import.filter_options', [])

        self._init_ui()
        self._restore_options()

    def _tr(self, en, fr):
        return fr if self.lang == 'fr' else en

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Sub-tabs ──
        self.sub_tabs = QTabWidget()
        self.sub_tabs.addTab(
            self._create_folders_tab(),
            self._tr("📁 Folders", "📁 Dossiers"))
        self.sub_tabs.addTab(
            self._create_setup_tab(),
            self._tr("🔧 Setup", "🔧 Setup"))
        self.sub_tabs.addTab(
            self._create_options_tab(),
            self._tr("⚙️ Options", "⚙️ Options"))
        layout.addWidget(self.sub_tabs, 1)

        # ── Action Buttons (always visible) ──
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 4, 0, 2)
        btn_layout.addStretch()

        self.stop_btn = QPushButton(self._tr("⏹ Cancel", "⏹ Annuler"))
        self.stop_btn.setToolTip(self._tr(
            "Cancel the current import",
            "Annuler l'import en cours"))
        self.stop_btn.setProperty("danger", True)
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self._stop)
        btn_layout.addWidget(self.stop_btn)

        self.start_btn = QPushButton(self._tr("▶ Import", "▶ Importer"))
        self.start_btn.setToolTip(self._tr(
            "Start ASIAIR import: compress, rename, organize",
            "Démarrer l'import ASIAIR : compresser, renommer, organiser"))
        self.start_btn.setProperty("accent", True)
        self.start_btn.clicked.connect(self._start_import)
        btn_layout.addWidget(self.start_btn)
        layout.addLayout(btn_layout)

        # ── Console (always visible) ──
        self.console = QTextEdit()
        self.console.setToolTip(self._tr(
            "Import progress and output log",
            "Progression de l'import et journal de sortie"))
        self.console.setReadOnly(True)
        self.console.setFont(get_mono_font(9))
        self.console.setMinimumHeight(100)
        self.console.setMaximumHeight(180)
        layout.addWidget(self.console)

    # ------------------------------------------------------------------
    # Sub-tab 1: Folders
    # ------------------------------------------------------------------

    def _create_folders_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 8, 6, 6)

        # Source folder
        src_group = QGroupBox(self._tr(
            "📂 Source Folder (ASIAIR)", "📂 Dossier Source (ASIAIR)"))
        src_layout = QVBoxLayout(src_group)
        src_layout.setSpacing(6)

        src_desc = QLabel(self._tr(
            "Folder containing the .fits files captured by ASIAIR.",
            "Dossier contenant les fichiers .fits capturés par l'ASIAIR."))
        src_desc.setStyleSheet("color: #7a8498;")
        src_layout.addWidget(src_desc)

        src_row = QHBoxLayout()
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText(self._tr(
            "Select folder with FITS files...",
            "Sélectionner dossier avec fichiers FITS..."))
        self.source_input.setMinimumHeight(24)
        src_row.addWidget(self.source_input)
        src_btn = QPushButton(self._tr("Browse...", "Parcourir..."))
        src_btn.setMinimumHeight(24)
        src_btn.clicked.connect(lambda: self._browse('source'))
        src_row.addWidget(src_btn)
        src_layout.addLayout(src_row)
        layout.addWidget(src_group)

        # Backup folder
        bak_group = QGroupBox(self._tr(
            "📂 Backup Folder", "📂 Dossier de Sauvegarde"))
        bak_layout = QVBoxLayout(bak_group)
        bak_layout.setSpacing(6)

        bak_desc = QLabel(self._tr(
            "Original .fits files are moved here after successful compression. "
            "Directory structure is preserved.",
            "Les fichiers .fits originaux sont déplacés ici après compression réussie. "
            "L'arborescence source est préservée."))
        bak_desc.setStyleSheet("color: #7a8498;")
        bak_desc.setWordWrap(True)
        bak_layout.addWidget(bak_desc)

        bak_row = QHBoxLayout()
        self.backup_input = QLineEdit()
        self.backup_input.setPlaceholderText(self._tr(
            "Backup folder (leave empty = no backup)",
            "Dossier de sauvegarde (vide = pas de sauvegarde)"))
        self.backup_input.setMinimumHeight(24)
        bak_row.addWidget(self.backup_input)
        bak_btn = QPushButton(self._tr("Browse...", "Parcourir..."))
        bak_btn.setMinimumHeight(24)
        bak_btn.clicked.connect(lambda: self._browse('backup'))
        bak_row.addWidget(bak_btn)
        bak_layout.addLayout(bak_row)
        layout.addWidget(bak_group)

        # Output organization
        org_group = QGroupBox(self._tr(
            "📤 Output Organization", "📤 Organisation de Sortie"))
        org_layout = QVBoxLayout(org_group)
        org_layout.setSpacing(8)

        self.organize_group = QButtonGroup(self)

        self.radio_keep = QRadioButton(self._tr(
            "Keep original directory structure (compress + rename in place)",
            "Garder l'arborescence initiale (compresser + renommer sur place)"))
        self.radio_keep.setChecked(True)
        self.organize_group.addButton(self.radio_keep, 0)
        org_layout.addWidget(self.radio_keep)

        self.radio_organize = QRadioButton(self._tr(
            "Organize into folders: Telescope / Target / Night_N / LIGHT|FLAT",
            "Réorganiser en dossiers : Telescope / Cible / Nuit_N / LIGHT|FLAT"))
        self.organize_group.addButton(self.radio_organize, 1)
        org_layout.addWidget(self.radio_organize)

        # Output folder (only visible when organize is selected)
        self.output_row = QHBoxLayout()
        self.output_label = QLabel(self._tr(
            "  Output folder:", "  Dossier de sortie :"))
        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText(self._tr(
            "Root folder for organized output...",
            "Dossier racine pour la sortie organisée..."))
        self.output_input.setMinimumHeight(24)
        self.output_btn = QPushButton(self._tr("Browse...", "Parcourir..."))
        self.output_btn.setMinimumHeight(24)
        self.output_btn.clicked.connect(lambda: self._browse('output'))
        self.output_row.addWidget(self.output_label)
        self.output_row.addWidget(self.output_input)
        self.output_row.addWidget(self.output_btn)
        org_layout.addLayout(self.output_row)

        # Show/hide output folder based on radio selection
        self._toggle_output_folder(False)
        self.radio_keep.toggled.connect(
            lambda checked: self._toggle_output_folder(not checked))

        layout.addWidget(org_group)
        layout.addStretch()
        return widget

    def _toggle_output_folder(self, visible):
        self.output_label.setVisible(visible)
        self.output_input.setVisible(visible)
        self.output_btn.setVisible(visible)

    # ------------------------------------------------------------------
    # Sub-tab 2: Setup (Telescope + Filter)
    # ------------------------------------------------------------------

    def _create_setup_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 8, 6, 6)

        # ── Telescope ──
        scope_group = QGroupBox(self._tr(
            "🔭 Telescope Override", "🔭 Override Télescope"))
        scope_layout = QVBoxLayout(scope_group)
        scope_layout.setSpacing(6)

        scope_desc = QLabel(self._tr(
            "ASIAIR does not write the telescope name in FITS headers. "
            "Select your telescope here or keep the FITS header value.",
            "L'ASIAIR n'écrit pas le nom du télescope dans les headers FITS. "
            "Sélectionnez votre télescope ici ou gardez la valeur du header."))
        scope_desc.setStyleSheet("color: #7a8498;")
        scope_desc.setWordWrap(True)
        scope_layout.addWidget(scope_desc)

        self.telescope_combo = QComboBox()
        self.telescope_combo.setMinimumHeight(24)
        self.telescope_combo.addItem(
            self._tr("Use FITS header", "Utiliser le header FITS"), "")
        for t in self.telescope_options:
            self.telescope_combo.addItem(t, t)
        self.telescope_combo.setEditable(True)
        self.telescope_combo.setToolTip(self._tr(
            "Type a new telescope name or select from the list. "
            "New names are saved to your config.",
            "Tapez un nouveau nom de télescope ou sélectionnez dans la liste. "
            "Les nouveaux noms sont sauvegardés dans votre config."))
        scope_layout.addWidget(self.telescope_combo)

        layout.addWidget(scope_group)

        # ── Filter ──
        filter_group = QGroupBox(self._tr(
            "🔴 Filter Override", "🔴 Override Filtre"))
        filter_layout = QVBoxLayout(filter_group)
        filter_layout.setSpacing(8)

        filter_desc = QLabel(self._tr(
            "With a manual filter wheel, ASIAIR does not know which filter is in use. "
            "Choose a single filter for the whole session or assign filters by time range.",
            "Avec un porte-filtre manuel, l'ASIAIR ne connaît pas le filtre utilisé. "
            "Choisissez un filtre unique pour toute la session ou assignez par plage horaire."))
        filter_desc.setStyleSheet("color: #7a8498;")
        filter_desc.setWordWrap(True)
        filter_layout.addWidget(filter_desc)

        self.filter_mode_group = QButtonGroup(self)

        # Mode 1: Single filter
        self.radio_single_filter = QRadioButton(self._tr(
            "Same filter for the whole session",
            "Même filtre pour toute la session"))
        self.radio_single_filter.setChecked(True)
        self.filter_mode_group.addButton(self.radio_single_filter, 0)
        filter_layout.addWidget(self.radio_single_filter)

        self.filter_single_combo = QComboBox()
        self.filter_single_combo.setMinimumHeight(24)
        self.filter_single_combo.addItem(
            self._tr("Use FITS header", "Utiliser le header FITS"), "")
        for f in self.filter_options:
            self.filter_single_combo.addItem(f, f)
        self.filter_single_combo.setEditable(True)
        self.filter_single_combo.setToolTip(self._tr(
            "Type a new filter name or select from the list.",
            "Tapez un nouveau nom de filtre ou sélectionnez dans la liste."))
        filter_layout.addWidget(self.filter_single_combo)

        # Mode 2: Time ranges
        self.radio_timerange = QRadioButton(self._tr(
            "Filters by time range",
            "Filtres par plage horaire"))
        self.filter_mode_group.addButton(self.radio_timerange, 1)
        filter_layout.addWidget(self.radio_timerange)

        # Time reference selector
        tr_ref_layout = QHBoxLayout()
        tr_ref_label = QLabel(self._tr(
            "  Time reference:", "  Référence horaire :"))
        self.time_ref_combo = QComboBox()
        self.time_ref_combo.setMinimumHeight(24)
        self.time_ref_combo.addItem("UTC", "utc")
        self.time_ref_combo.addItem(self._tr(
            "Local solar time (auto from FITS coordinates)",
            "Heure solaire locale (auto depuis coordonnées FITS)"), "solar")

        # Add configured timezone if available
        obs_tz = self.config.get('observatory.timezone', '')
        if obs_tz and obs_tz != 'UTC':
            self.time_ref_combo.addItem(
                self._tr(f"Timezone: {obs_tz} (DST-aware)",
                         f"Fuseau : {obs_tz} (heure d'été gérée)"),
                "timezone")
        self.time_ref_combo.setToolTip(self._tr(
            "How to interpret the start/end times you enter below.\n\n"
            "• UTC: enter times in UTC (default).\n"
            "• Local solar time: times are in local solar time, "
            "computed from SITELAT/SITELONG in each FITS header. "
            "No DST — purely based on longitude.\n"
            "• Timezone: times are in your observatory's timezone "
            "(from Settings). DST transitions are handled automatically.",
            "Comment interpréter les heures de début/fin ci-dessous.\n\n"
            "• UTC : saisir les heures en UTC (par défaut).\n"
            "• Heure solaire locale : heures en temps solaire local, "
            "calculé depuis SITELAT/SITELONG de chaque header FITS. "
            "Pas d'heure d'été — purement basé sur la longitude.\n"
            "• Fuseau horaire : heures dans le fuseau de votre observatoire "
            "(depuis Réglages). Les changements d'heure d'été sont gérés."))
        tr_ref_layout.addWidget(tr_ref_label)
        tr_ref_layout.addWidget(self.time_ref_combo, 1)
        filter_layout.addLayout(tr_ref_layout)

        # Info label — shows detected offset dynamically
        self.time_ref_info = QLabel("")
        self.time_ref_info.setStyleSheet("color: #7a8498; font-size: 9pt; padding-left: 20px;")
        self.time_ref_info.setWordWrap(True)
        filter_layout.addWidget(self.time_ref_info)
        self.time_ref_combo.currentIndexChanged.connect(self._update_time_ref_info)
        self._update_time_ref_info()

        # Time range table
        self.timerange_table = QTableWidget(0, 3)
        self.timerange_table.setHorizontalHeaderLabels([
            self._tr("Start", "Début"),
            self._tr("End", "Fin"),
            self._tr("Filter", "Filtre"),
        ])
        self.timerange_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.timerange_table.setMinimumHeight(100)
        self.timerange_table.setMaximumHeight(180)
        self.timerange_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        filter_layout.addWidget(self.timerange_table)

        # Add/Remove buttons
        tr_btn_layout = QHBoxLayout()
        tr_btn_layout.addStretch()
        self.add_range_btn = QPushButton(self._tr("+ Add", "+ Ajouter"))
        self.add_range_btn.setToolTip(self._tr(
            "Add a new time range for filter assignment",
            "Ajouter une nouvelle plage horaire pour l'attribution de filtre"))
        self.add_range_btn.clicked.connect(self._add_time_range)
        tr_btn_layout.addWidget(self.add_range_btn)

        self.remove_range_btn = QPushButton(self._tr("- Remove", "- Supprimer"))
        self.remove_range_btn.setToolTip(self._tr(
            "Remove the selected time range",
            "Supprimer la plage horaire sélectionnée"))
        self.remove_range_btn.clicked.connect(self._remove_time_range)
        tr_btn_layout.addWidget(self.remove_range_btn)
        filter_layout.addLayout(tr_btn_layout)

        # Toggle time range widgets visibility
        self._toggle_timerange(False)
        self.radio_single_filter.toggled.connect(
            lambda checked: self._toggle_timerange(not checked))

        layout.addWidget(filter_group)
        layout.addStretch()
        scroll.setWidget(widget)
        return scroll

    def _toggle_timerange(self, visible):
        self.timerange_table.setVisible(visible)
        self.add_range_btn.setVisible(visible)
        self.remove_range_btn.setVisible(visible)
        self.time_ref_combo.setVisible(visible)
        self.time_ref_info.setVisible(visible)
        # Find the label in the layout — use parent visibility
        for w in (self.time_ref_combo, self.time_ref_info):
            w.setVisible(visible)
        self.filter_single_combo.setVisible(not visible)

    def _add_time_range(self):
        row = self.timerange_table.rowCount()
        self.timerange_table.insertRow(row)
        self.timerange_table.setItem(row, 0, QTableWidgetItem("20:00"))
        self.timerange_table.setItem(row, 1, QTableWidgetItem("23:30"))

        # Filter combo in the table cell
        combo = QComboBox()
        for f in self.filter_options:
            combo.addItem(f, f)
        combo.setEditable(True)
        self.timerange_table.setCellWidget(row, 2, combo)

    def _remove_time_range(self):
        rows = set()
        for item in self.timerange_table.selectedItems():
            rows.add(item.row())
        for row in sorted(rows, reverse=True):
            self.timerange_table.removeRow(row)

    def _update_time_ref_info(self):
        """Update the info label based on selected time reference."""
        ref = self.time_ref_combo.currentData() or 'utc'
        if ref == 'utc':
            self.time_ref_info.setText(self._tr(
                "Enter times in UTC. Example: 21:15 UTC.",
                "Saisissez les heures en UTC. Exemple : 21:15 UTC."))
        elif ref == 'solar':
            obs_long = self.config.get('observatory.longitude', 0)
            offset_h = obs_long / 15.0
            sign = '+' if offset_h >= 0 else ''
            self.time_ref_info.setText(self._tr(
                f"Enter times in local solar time. Each file's longitude "
                f"(SITELONG) is used for conversion. "
                f"Observatory default: UTC{sign}{offset_h:+.1f}h "
                f"(long={obs_long:.2f}°). "
                f"Example: if you changed filter at 23:30 local, enter 23:30.",
                f"Saisissez les heures en heure solaire locale. La longitude "
                f"(SITELONG) de chaque fichier est utilisée pour la conversion. "
                f"Défaut observatoire : UTC{sign}{offset_h:+.1f}h "
                f"(long={obs_long:.2f}°). "
                f"Exemple : si vous avez changé de filtre à 23h30 locale, "
                f"saisissez 23:30."))
        elif ref == 'timezone':
            tz = self.config.get('observatory.timezone', 'UTC')
            # Try to show current offset
            offset_info = ''
            try:
                from datetime import datetime, timezone as dt_tz
                try:
                    from zoneinfo import ZoneInfo
                    tz_obj = ZoneInfo(tz)
                except ImportError:
                    import pytz
                    tz_obj = pytz.timezone(tz)
                now = datetime.now(dt_tz.utc).astimezone(tz_obj)
                utc_off = now.utcoffset()
                if utc_off is not None:
                    hours = utc_off.total_seconds() / 3600
                    offset_info = self._tr(
                        f" Current offset: UTC{hours:+.0f}h.",
                        f" Décalage actuel : UTC{hours:+.0f}h.")
            except Exception:
                pass
            self.time_ref_info.setText(self._tr(
                f"Enter times in {tz} timezone. DST transitions are handled "
                f"automatically.{offset_info} "
                f"Example: if you changed filter at 23:30 {tz}, enter 23:30.",
                f"Saisissez les heures en fuseau {tz}. Les changements "
                f"d'heure d'été sont gérés automatiquement.{offset_info} "
                f"Exemple : si vous avez changé de filtre à 23h30 {tz}, "
                f"saisissez 23:30."))

    # ------------------------------------------------------------------
    # Sub-tab 3: Options
    # ------------------------------------------------------------------

    def _create_options_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 8, 6, 6)

        opts_group = QGroupBox(self._tr(
            "⚙️ Import Options", "⚙️ Options d'Import"))
        opts_layout = QVBoxLayout(opts_group)
        opts_layout.setSpacing(8)

        self.cb_verify = QCheckBox(self._tr(
            "Verify file integrity after compression",
            "Vérifier l'intégrité des fichiers après compression"))
        self.cb_verify.setChecked(
            self.config.get('asiair_import.verify_integrity',
                            self.config.get('compression.verify_integrity', True)))
        opts_layout.addWidget(self.cb_verify)

        self.cb_overrides = QCheckBox(self._tr(
            "Write overrides into XISF headers (TELESCOP, FILTER)",
            "Écrire les overrides dans les headers XISF (TELESCOP, FILTER)"))
        self.cb_overrides.setChecked(
            self.config.get('asiair_import.write_overrides', True))
        opts_layout.addWidget(self.cb_overrides)

        layout.addWidget(opts_group)

        # XISF Profile
        profile_group = QGroupBox(self._tr(
            "🗜️ XISF Compression Profile", "🗜️ Profil de Compression XISF"))
        profile_layout = QVBoxLayout(profile_group)
        profile_layout.setSpacing(6)

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumHeight(24)

        default_profile = self.config.get(
            'asiair_import.default_profile',
            self.config.get('compression.default_profile', 'zlib_6'))

        profile_order = [
            'zlib_6', 'zstd_6', 'zstd_10', 'lz4',
            'zlib_1', 'zlib_9', 'zstd_3', 'zstd_19', 'lz4_hc'
        ]
        for pname in profile_order:
            p = COMPRESSION_PROFILES.get(pname, {})
            if not p:
                continue
            lang_key = 'fr' if self.lang == 'fr' else 'en'
            label = p.get(f'name_{lang_key}', pname)
            self.profile_combo.addItem(label, pname)
            if pname == default_profile:
                self.profile_combo.setCurrentIndex(
                    self.profile_combo.count() - 1)

        self.profile_combo.setToolTip(self._tr(
            "Compression profile for FITS → XISF conversion",
            "Profil de compression pour la conversion FITS → XISF"))
        profile_layout.addWidget(self.profile_combo)

        layout.addWidget(profile_group)
        layout.addStretch()
        return widget

    # ==================================================================
    # Actions
    # ==================================================================

    # ==================================================================
    # Persistence
    # ==================================================================

    def _restore_options(self):
        """Restore saved options from config."""
        src = self.config.get('asiair_import.last_source_folder', '')
        if src:
            self.source_input.setText(src)
        bak = self.config.get('asiair_import.last_backup_folder', '')
        if bak:
            self.backup_input.setText(bak)
        out = self.config.get('asiair_import.last_output_folder', '')
        if out:
            self.output_input.setText(out)
        org_mode = self.config.get('asiair_import.organize_mode', 0)
        if org_mode == 1:
            self.radio_organize.setChecked(True)
        else:
            self.radio_keep.setChecked(True)
        filt_mode = self.config.get('asiair_import.filter_mode', 0)
        if filt_mode == 1:
            self.radio_timerange.setChecked(True)
        else:
            self.radio_single_filter.setChecked(True)
        time_ref_idx = self.config.get('asiair_import.time_reference_index', 0)
        if 0 <= time_ref_idx < self.time_ref_combo.count():
            self.time_ref_combo.setCurrentIndex(time_ref_idx)

    def _save_options(self):
        """Save current options to config for next session."""
        self.config.set('asiair_import.last_source_folder',
                        self.source_input.text().strip())
        self.config.set('asiair_import.last_backup_folder',
                        self.backup_input.text().strip())
        self.config.set('asiair_import.last_output_folder',
                        self.output_input.text().strip())
        self.config.set('asiair_import.organize_mode',
                        1 if self.radio_organize.isChecked() else 0)
        self.config.set('asiair_import.filter_mode',
                        1 if self.radio_timerange.isChecked() else 0)
        self.config.set('asiair_import.time_reference_index',
                        self.time_ref_combo.currentIndex())
        self.config.set('asiair_import.verify_integrity',
                        self.cb_verify.isChecked())
        self.config.set('asiair_import.write_overrides',
                        self.cb_overrides.isChecked())
        profile = self.profile_combo.currentData() or 'zlib_6'
        self.config.set('asiair_import.default_profile', profile)
        self.config.save_config()

    def _browse(self, which):
        folder = QFileDialog.getExistingDirectory(
            self, self._tr("Select Folder", "Sélectionner Dossier"))
        if folder:
            if which == 'source':
                self.source_input.setText(folder)
            elif which == 'backup':
                self.backup_input.setText(folder)
            elif which == 'output':
                self.output_input.setText(folder)

    def _get_filter_ranges(self):
        """Read time range table into list of dicts."""
        ranges = []
        for row in range(self.timerange_table.rowCount()):
            start_item = self.timerange_table.item(row, 0)
            end_item = self.timerange_table.item(row, 1)
            combo = self.timerange_table.cellWidget(row, 2)

            start = start_item.text().strip() if start_item else ''
            end = end_item.text().strip() if end_item else ''
            filt = combo.currentText().strip() if combo else ''

            if start and end and filt:
                ranges.append({
                    'start': start,
                    'end': end,
                    'filter': filt,
                })
        return ranges

    def _save_new_options(self):
        """Save any new telescope/filter names typed by the user to config."""
        # Telescope
        tele_text = self.telescope_combo.currentText().strip()
        if tele_text and tele_text != self._tr(
                "Use FITS header", "Utiliser le header FITS"):
            if tele_text not in self.telescope_options:
                self.telescope_options.append(tele_text)
                self.config.set('asiair_import.telescope_options',
                                self.telescope_options)
                self.config.save_config()

        # Filter (single mode)
        filt_text = self.filter_single_combo.currentText().strip()
        if filt_text and filt_text != self._tr(
                "Use FITS header", "Utiliser le header FITS"):
            if filt_text not in self.filter_options:
                self.filter_options.append(filt_text)
                self.config.set('asiair_import.filter_options',
                                self.filter_options)
                self.config.save_config()

        # Filters from time range table
        for row in range(self.timerange_table.rowCount()):
            combo = self.timerange_table.cellWidget(row, 2)
            if combo:
                ft = combo.currentText().strip()
                if ft and ft not in self.filter_options:
                    self.filter_options.append(ft)
        self.config.set('asiair_import.filter_options', self.filter_options)
        self.config.save_config()

    def _start_import(self):
        self._save_options()
        source = self.source_input.text().strip()
        if not source or not os.path.isdir(source):
            self.console.append(self._tr(
                "❌ Select a valid source folder.",
                "❌ Sélectionnez un dossier source valide."))
            return

        organize = self.radio_organize.isChecked()
        output_folder = self.output_input.text().strip() if organize else ''
        if organize and not output_folder:
            self.console.append(self._tr(
                "❌ Select an output folder for organized structure.",
                "❌ Sélectionnez un dossier de sortie pour l'arborescence."))
            return

        # Save any new user-typed telescope/filter names
        self._save_new_options()

        # Telescope override
        tele_data = self.telescope_combo.currentData()
        if tele_data is None:
            # User typed a custom value
            tele_text = self.telescope_combo.currentText().strip()
            telescope_override = '' if tele_text == self._tr(
                "Use FITS header", "Utiliser le header FITS") else tele_text
        else:
            telescope_override = tele_data

        # Filter mode
        if self.radio_single_filter.isChecked():
            filter_mode = 'single'
            filt_data = self.filter_single_combo.currentData()
            if filt_data is None:
                filt_text = self.filter_single_combo.currentText().strip()
                filter_single = '' if filt_text == self._tr(
                    "Use FITS header", "Utiliser le header FITS") else filt_text
            else:
                filter_single = filt_data
            filter_ranges = []
        else:
            filter_mode = 'timerange'
            filter_single = ''
            filter_ranges = self._get_filter_ranges()
            if not filter_ranges:
                self.console.append(self._tr(
                    "❌ Add at least one time range.",
                    "❌ Ajoutez au moins une plage horaire."))
                return

        # Profile
        profile = self.profile_combo.currentData() or 'zlib_6'

        self.console.clear()
        self.start_btn.setVisible(False)
        self.stop_btn.setVisible(True)
        signals.busy_state_changed.emit(True)

        self.worker = UnifiedWorker()
        self.worker.output_signal.connect(
            lambda t: self.console.append(t.rstrip()) if t.strip() else None)
        self.worker.progress_signal.connect(
            lambda c, t, p: signals.analysis_progress.emit(c, t, p))
        self.worker.finished_signal.connect(self._on_finished)

        # Time reference for filter ranges
        time_reference = self.time_ref_combo.currentData() or 'utc'
        timezone_str = ''
        if time_reference == 'timezone':
            timezone_str = self.config.get('observatory.timezone', 'UTC')

        job = WorkerJob(
            job_type=JobType.ASIAIR_IMPORT,
            params={
                'source_folder': source,
                'backup_folder': self.backup_input.text().strip() or '',
                'organize': organize,
                'output_folder': output_folder,
                'telescope_override': telescope_override,
                'filter_mode': filter_mode,
                'filter_single': filter_single,
                'filter_ranges': filter_ranges,
                'time_reference': time_reference,
                'timezone_str': timezone_str,
                'profile': profile,
                'verify_integrity': self.cb_verify.isChecked(),
                'write_overrides': self.cb_overrides.isChecked(),
                'rename_pattern': DEFAULT_FILENAME_PATTERN,
                'lang': self.lang,
            },
            priority=8
        )
        self.worker.set_single_job(job)
        self.worker.start()

    def _stop(self):
        if self.worker:
            self.worker.stop()

    def _on_finished(self, success, message, result):
        self.start_btn.setVisible(True)
        self.stop_btn.setVisible(False)
        signals.busy_state_changed.emit(False)
        if success and result:
            signals.compression_completed.emit(result)
        self.worker = None
