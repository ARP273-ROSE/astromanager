#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - HEADER EDITOR TAB
================================================================================
Mass FITS header editing with NINA-compatible fields.
Integrates header_editor.py for bulk operations.
================================================================================
"""

import os
import threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QFileDialog, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QMessageBox, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from core.workers import UnifiedWorker, WorkerJob, JobType
from core.signals import signals
from core.config import get_config
from core.i18n import get_lang
from gui.theme import get_mono_font

try:
    from modules.header_editor import (
        HEADER_FIELDS, HEADER_CATEGORIES,
        read_header, scan_directory, detect_file_type
    )
    HEADER_EDITOR_AVAILABLE = True
except ImportError:
    HEADER_EDITOR_AVAILABLE = False
    HEADER_FIELDS = {}
    HEADER_CATEGORIES = {}


class HeaderEditorTab(QWidget):
    """Header Editor tab - Mass FITS header editing"""

    _headers_loaded_signal = pyqtSignal(list, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self.lang = get_lang()
        self.worker = None
        self.loaded_files = []
        self.headers_data = {}
        self._headers_loaded_signal.connect(self._on_headers_loaded)
        self._init_ui()
        self._restore_options()

    def _tr(self, en, fr):
        return fr if self.lang == 'fr' else en

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── File Selection ──
        file_group = QGroupBox(self._tr("📁 File Selection", "📁 Sélection Fichiers"))
        file_layout = QHBoxLayout(file_group)
        self.folder_input = QLineEdit()
        self.folder_input.setToolTip(self._tr(
            "Path to folder with FITS/XISF files for header editing",
            "Chemin vers le dossier avec fichiers FITS/XISF pour édition d'en-têtes"
        ))
        self.folder_input.setPlaceholderText(self._tr("Select folder with FITS/XISF files...", "Sélectionner dossier avec fichiers FITS/XISF..."))
        file_layout.addWidget(self.folder_input)
        browse_btn = QPushButton(self._tr("Browse...", "Parcourir..."))
        browse_btn.setToolTip(self._tr(
            "Browse for a folder with FITS/XISF files",
            "Parcourir pour un dossier avec fichiers FITS/XISF"
        ))
        browse_btn.clicked.connect(self._browse_folder)
        file_layout.addWidget(browse_btn)
        self.load_btn = QPushButton(self._tr("Load Headers", "Charger Headers"))
        self.load_btn.setToolTip(self._tr(
            "Load FITS/XISF headers from the selected folder",
            "Charger les headers FITS/XISF depuis le dossier sélectionné"
        ))
        self.load_btn.setProperty("accent", True)
        self.load_btn.clicked.connect(self._load_headers)
        file_layout.addWidget(self.load_btn)
        layout.addWidget(file_group)

        # File info
        self.info_label = QLabel(self._tr("No files loaded", "Aucun fichier chargé"))
        layout.addWidget(self.info_label)

        # ── Category filter ──
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel(self._tr("Category:", "Catégorie:")))
        self.category_combo = QComboBox()
        self.category_combo.setToolTip(self._tr(
            "Filter header fields by category",
            "Filtrer les champs header par catégorie"
        ))
        self.category_combo.addItem(self._tr("All Categories", "Toutes Catégories"), "all")
        for cat_key, cat_data in HEADER_CATEGORIES.items():
            lang_key = 'fr' if self.lang == 'fr' else 'en'
            self.category_combo.addItem(cat_data.get(lang_key, cat_key), cat_key)
        self.category_combo.currentIndexChanged.connect(self._filter_table)
        filter_layout.addWidget(self.category_combo)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # ── Header Table ──
        self.table = QTableWidget()
        self.table.setToolTip(self._tr(
            "FITS header fields - edit 'New Value' column to set changes",
            "Champs d'en-tête FITS - éditez la colonne 'Nouvelle Valeur' pour définir les modifications"
        ))
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            self._tr("Field", "Champ"),
            self._tr("Category", "Catégorie"),
            self._tr("Current Value", "Valeur Actuelle"),
            self._tr("New Value", "Nouvelle Valeur"),
            self._tr("Description", "Description"),
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, 1)

        # ── NINA Pattern Builder ──
        pattern_group = QGroupBox(self._tr("📝 NINA Filename Pattern", "📝 Pattern Nom de Fichier NINA"))
        pattern_layout = QVBoxLayout(pattern_group)

        pattern_row = QHBoxLayout()
        self.pattern_input = QLineEdit()
        self.pattern_input.setToolTip(self._tr(
            "NINA-compatible filename pattern using tokens",
            "Pattern de nom de fichier compatible NINA utilisant des tokens"
        ))
        # Load pattern from settings, or use default
        config = get_config()
        default_pattern = "$IMAGETYPE$_$TARGETNAME$_$DATETIME$_$FILTER$_$BINNING$_$EXPOSURETIME$s_$ROTATORANGLE$deg_$SENSORTEMP$_$TELESCOPE$_$CAMERA$_$FRAMENR$"
        self.pattern_input.setText(config.get('file_naming.pattern', default_pattern))
        self.pattern_input.setFont(get_mono_font(9))
        pattern_row.addWidget(self.pattern_input, 1)

        save_pattern_btn = QPushButton(self._tr("💾 Save", "💾 Sauver"))
        save_pattern_btn.setToolTip(self._tr(
            "Save current pattern to settings (persists across sessions)",
            "Sauvegarder le pattern actuel dans les réglages (persiste entre les sessions)"
        ))
        save_pattern_btn.clicked.connect(self._save_pattern_to_settings)
        pattern_row.addWidget(save_pattern_btn)

        load_pattern_btn = QPushButton(self._tr("📥 Load", "📥 Charger"))
        load_pattern_btn.setToolTip(self._tr(
            "Load pattern from settings",
            "Charger le pattern depuis les réglages"
        ))
        load_pattern_btn.clicked.connect(self._load_pattern_from_settings)
        pattern_row.addWidget(load_pattern_btn)

        build_pattern_btn = QPushButton(self._tr("🔧 Build from Headers", "🔧 Construire depuis Headers"))
        build_pattern_btn.setToolTip(self._tr(
            "Build a filename pattern from the current header column order",
            "Construire un pattern de nom de fichier à partir de l'ordre des colonnes de headers"
        ))
        build_pattern_btn.clicked.connect(self._build_pattern_from_headers)
        pattern_row.addWidget(build_pattern_btn)

        pattern_layout.addLayout(pattern_row)

        tokens_label = QLabel(self._tr(
            "Tokens: $IMAGETYPE$ $TARGETNAME$ $DATETIME$ $FILTER$ $BINNING$ $EXPOSURETIME$ $ROTATORANGLE$ $SENSORTEMP$ $TELESCOPE$ $CAMERA$ $FRAMENR$ $GAIN$ $OFFSET$",
            "Tokens: $IMAGETYPE$ $TARGETNAME$ $DATETIME$ $FILTER$ $BINNING$ $EXPOSURETIME$ $ROTATORANGLE$ $SENSORTEMP$ $TELESCOPE$ $CAMERA$ $FRAMENR$ $GAIN$ $OFFSET$"
        ))
        tokens_label.setStyleSheet("color: #8b95b0; font-size: 9pt;")
        tokens_label.setWordWrap(True)
        pattern_layout.addWidget(tokens_label)
        layout.addWidget(pattern_group)

        # ── Buttons ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        preview_btn = QPushButton(self._tr("👁 Preview Changes", "👁 Prévisualiser Changements"))
        preview_btn.setToolTip(self._tr(
            "Preview changes before applying them",
            "Prévisualiser les modifications avant de les appliquer"
        ))
        preview_btn.clicked.connect(self._preview_changes)
        btn_layout.addWidget(preview_btn)

        self.apply_btn = QPushButton(self._tr("▶ Apply Changes", "▶ Appliquer Changements"))
        self.apply_btn.setToolTip(self._tr(
            "Apply header changes to all loaded files",
            "Appliquer les modifications de headers à tous les fichiers chargés"
        ))
        self.apply_btn.setProperty("accent", True)
        self.apply_btn.clicked.connect(self._apply_changes)
        btn_layout.addWidget(self.apply_btn)
        layout.addLayout(btn_layout)

    def _save_pattern_to_settings(self):
        """Save current pattern to config for persistence"""
        pattern = self.pattern_input.text().strip()
        if not pattern:
            return
        config = get_config()
        config.set('file_naming.pattern', pattern)
        config.save_config()
        QMessageBox.information(self, self._tr("Pattern", "Pattern"),
            self._tr("Pattern saved to settings.", "Pattern sauvegardé dans les réglages."))

    def _load_pattern_from_settings(self):
        """Load pattern from config"""
        config = get_config()
        pattern = config.get('file_naming.pattern', '')
        if pattern:
            self.pattern_input.setText(pattern)
        else:
            QMessageBox.information(self, self._tr("Pattern", "Pattern"),
                self._tr("No saved pattern found in settings.",
                         "Aucun pattern sauvegardé trouvé dans les réglages."))

    def _build_pattern_from_headers(self):
        """Build a filename pattern from the currently loaded header columns"""
        if self.table.rowCount() == 0:
            QMessageBox.information(self, self._tr("Pattern", "Pattern"),
                self._tr("Load files first to build pattern from headers.",
                         "Chargez d'abord des fichiers pour construire le pattern."))
            return

        # Map common FITS header keywords to NINA tokens
        header_to_token = {
            'IMAGETYP': '$IMAGETYPE$', 'FRAME': '$IMAGETYPE$',
            'OBJECT': '$TARGETNAME$', 'TARGET': '$TARGETNAME$',
            'DATE-OBS': '$DATETIME$', 'DATE_OBS': '$DATETIME$',
            'FILTER': '$FILTER$', 'FILTNAME': '$FILTER$',
            'XBINNING': '$BINNING$', 'BINNING': '$BINNING$',
            'EXPTIME': '$EXPOSURETIME$', 'EXPOSURE': '$EXPOSURETIME$',
            'ROTATANG': '$ROTATORANGLE$', 'ROTANGLE': '$ROTATORANGLE$', 'ROTATOR': '$ROTATORANGLE$',
            'CCD-TEMP': '$SENSORTEMP$', 'CCDTEMP': '$SENSORTEMP$', 'SET-TEMP': '$SENSORTEMP$',
            'TELESCOP': '$TELESCOPE$', 'INSTRUME': '$CAMERA$', 'CAMERA': '$CAMERA$',
            'GAIN': '$GAIN$', 'OFFSET': '$OFFSET$', 'BAYOFFST': '$OFFSET$',
        }

        # Get FITS keywords from table rows (column 0 = field name)
        tokens = []
        seen = set()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                key = item.text().upper().strip()
                token = header_to_token.get(key)
                if token and token not in seen:
                    tokens.append(token)
                    seen.add(token)

        if tokens:
            pattern = '_'.join(tokens)
            self.pattern_input.setText(pattern)
        else:
            QMessageBox.information(self, self._tr("Pattern", "Pattern"),
                self._tr("No matching FITS header tokens found in loaded columns.",
                         "Aucun token de header FITS correspondant trouvé dans les colonnes chargées."))

    # ==================================================================
    # Persistence
    # ==================================================================

    def _restore_options(self):
        """Restore saved options from config."""
        folder = self.config.get('header_editor.last_folder', '')
        if folder:
            self.folder_input.setText(folder)

    def _save_options(self):
        """Save current options to config for next session."""
        self.config.set('header_editor.last_folder',
                        self.folder_input.text().strip())
        self.config.save_config()

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, self._tr("Select Folder", "Sélectionner Dossier"))
        if folder:
            self.folder_input.setText(folder)

    def _load_headers(self):
        """Load headers from files in the selected folder (non-blocking)"""
        self._save_options()
        folder = self.folder_input.text().strip()
        if not folder or not os.path.isdir(folder):
            return

        if not HEADER_EDITOR_AVAILABLE:
            self.info_label.setText(self._tr("❌ Header editor module not available", "❌ Module éditeur headers non disponible"))
            return

        self.load_btn.setEnabled(False)
        self.info_label.setText(self._tr("Scanning files...", "Recherche des fichiers..."))

        def _do_scan():
            found_files = []
            for root, _, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith(('.fits', '.fit', '.xisf', '.fz')):
                        found_files.append(os.path.join(root, f))

            headers_data = {}
            if found_files:
                try:
                    ref_header = read_header(found_files[0])
                    headers_data = ref_header if ref_header else {}
                except Exception:
                    headers_data = {}

            self._headers_loaded_signal.emit(found_files, headers_data)

        threading.Thread(target=_do_scan, daemon=True).start()

    def _on_headers_loaded(self, found_files, headers_data):
        """Handle headers loaded from background thread"""
        self.load_btn.setEnabled(True)
        self.loaded_files = found_files
        self.headers_data = headers_data

        if not self.loaded_files:
            self.info_label.setText(self._tr("No FITS/XISF files found", "Aucun fichier FITS/XISF trouvé"))
            return

        self.info_label.setText(f"{len(self.loaded_files)} {self._tr('files loaded', 'fichiers chargés')}")
        self._populate_table()

    def _populate_table(self):
        """Populate table with header fields"""
        lang_key = 'fr' if self.lang == 'fr' else 'en'

        rows = []
        for field_name, field_info in HEADER_FIELDS.items():
            category = field_info.get('category', 'other')
            cat_display = HEADER_CATEGORIES.get(category, {}).get(lang_key, category)
            description = field_info.get(lang_key, field_info.get('en', ''))
            current_value = str(self.headers_data.get(field_name, ''))

            rows.append((field_name, cat_display, current_value, '', description, category))

        self.table.setRowCount(len(rows))
        for i, (field, cat, current, new, desc, cat_key) in enumerate(rows):
            # Field name
            item = QTableWidgetItem(field)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setForeground(QColor('#94b8c8'))
            self.table.setItem(i, 0, item)

            # Category
            item = QTableWidgetItem(cat)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setData(Qt.ItemDataRole.UserRole, cat_key)
            self.table.setItem(i, 1, item)

            # Current value
            item = QTableWidgetItem(current)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 2, item)

            # New value (editable)
            item = QTableWidgetItem(new)
            self.table.setItem(i, 3, item)

            # Description
            item = QTableWidgetItem(desc)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setForeground(QColor('#8b95b0'))
            self.table.setItem(i, 4, item)

    def _filter_table(self):
        """Filter table by category"""
        selected = self.category_combo.currentData()
        for row in range(self.table.rowCount()):
            cat_item = self.table.item(row, 1)
            if cat_item:
                cat_key = cat_item.data(Qt.ItemDataRole.UserRole)
                visible = (selected == "all" or cat_key == selected)
                self.table.setRowHidden(row, not visible)

    def _get_changes(self):
        """Get all modified fields"""
        changes = {}
        for row in range(self.table.rowCount()):
            field_item = self.table.item(row, 0)
            new_item = self.table.item(row, 3)
            if field_item and new_item:
                new_value = new_item.text().strip()
                if new_value:
                    changes[field_item.text()] = new_value
        return changes

    def _preview_changes(self):
        changes = self._get_changes()
        if not changes:
            QMessageBox.information(self, self._tr("Info", "Info"),
                self._tr("No changes to preview", "Aucun changement à prévisualiser"))
            return

        msg = self._tr(f"Changes to apply to {len(self.loaded_files)} files:\n\n",
                       f"Changements à appliquer à {len(self.loaded_files)} fichiers:\n\n")
        for field, value in changes.items():
            msg += f"  {field} = {value}\n"

        QMessageBox.information(self, self._tr("Preview", "Aperçu"), msg)

    def _apply_changes(self):
        changes = self._get_changes()
        if not changes or not self.loaded_files:
            return

        reply = QMessageBox.question(self, self._tr("Confirm", "Confirmer"),
            self._tr(f"Apply {len(changes)} changes to {len(self.loaded_files)} files?",
                     f"Appliquer {len(changes)} changements à {len(self.loaded_files)} fichiers?"))

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Use worker for batch editing
        self.worker = UnifiedWorker()
        self.worker.output_signal.connect(lambda t: None)
        self.worker.progress_signal.connect(lambda c, t, p: signals.headers_edit_progress.emit(c, t))
        self.worker.finished_signal.connect(self._on_edit_finished)

        job = WorkerJob(
            job_type=JobType.HEADER_EDIT,
            params={'files': self.loaded_files, 'changes': changes},
            priority=8
        )
        self.worker.set_single_job(job)
        self.worker.start()

    def _on_edit_finished(self, success, message, result):
        if success and result:
            modified = result.get('modified', 0)
            QMessageBox.information(self, self._tr("Done", "Terminé"),
                self._tr(f"Modified {modified} files successfully",
                         f"{modified} fichiers modifiés avec succès"))
            signals.headers_modified.emit(self.loaded_files)
