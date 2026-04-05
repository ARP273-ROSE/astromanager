#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - WBPP EXPORT TAB
================================================================================
GUI tab for organizing FITS/XISF files into a folder structure ready for
PixInsight's Weighted Batch PreProcessing (WBPP) script.

Scan source folders, preview the planned folder tree, match calibration
frames, validate completeness, and export with copy/symlink/list modes.
================================================================================
"""

import os
import time
from collections import defaultdict
from pathlib import Path
from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox,
    QPushButton, QLabel, QLineEdit, QFileDialog, QDoubleSpinBox,
    QComboBox, QTextEdit, QTreeWidget, QTreeWidgetItem, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QSplitter, QFrame,
    QSizePolicy, QAbstractItemView, QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QBrush

from core.config import get_config
from gui.theme import COLORS, get_mono_font

# Import WBPP export module
try:
    from modules.wbpp_export import (
        scan_files, build_export_plan, execute_export, validate_export,
        match_calibrations, get_folder_preview, get_plan_statistics,
        FileInfo, ExportPlan, ExportResult,
    )
    WBPP_AVAILABLE = True
except ImportError:
    WBPP_AVAILABLE = False


# =============================================================================
# Worker threads
# =============================================================================

class ScanWorker(QThread):
    """Background worker for scanning source folders."""
    progress = pyqtSignal(int, int, str)     # current, total, message
    finished = pyqtSignal(list)              # List[FileInfo]
    error = pyqtSignal(str)

    def __init__(self, folders: List[str], recursive: bool):
        super().__init__()
        self.folders = folders
        self.recursive = recursive
        self._cancelled = False

    def run(self):
        try:
            def callback(current, total, msg):
                if self._cancelled:
                    raise InterruptedError("Scan cancelled")
                self.progress.emit(current, total, msg)

            results = scan_files(self.folders, self.recursive, callback=callback)
            if not self._cancelled:
                self.finished.emit(results)
        except InterruptedError:
            self.finished.emit([])
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self._cancelled = True


class ExportWorker(QThread):
    """Background worker for executing the export plan."""
    progress = pyqtSignal(int, int, str)     # current, total, message
    finished = pyqtSignal(object)            # ExportResult
    error = pyqtSignal(str)

    def __init__(self, plan: List[ExportPlan], mode: str):
        super().__init__()
        self.plan = plan
        self.mode = mode
        self._cancelled = False

    def run(self):
        try:
            def callback(current, total, msg):
                if self._cancelled:
                    raise InterruptedError("Export cancelled")
                self.progress.emit(current, total, msg)

            result = execute_export(self.plan, mode=self.mode, callback=callback)
            if not self._cancelled:
                self.finished.emit(result)
        except InterruptedError:
            self.finished.emit(ExportResult(
                total_files=len(self.plan), copied_files=0, failed_files=0,
                warnings=["Export cancelled by user"],
            ))
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self._cancelled = True


# =============================================================================
# Unicode icons for image types
# =============================================================================

_TYPE_ICONS = {
    'LIGHT':    '\u2605',  # Star
    'DARK':     '\u263E',  # Moon
    'FLAT':     '\u25A0',  # Square
    'BIAS':     '\u2022',  # Bullet
    'DARKFLAT': '\u25C6',  # Diamond
}

_TYPE_COLORS = {
    'LIGHT':    COLORS['accent_cyan'],
    'DARK':     COLORS['accent_purple'],
    'FLAT':     COLORS['accent_orange'],
    'BIAS':     COLORS['accent_pink'],
    'DARKFLAT': COLORS['accent_yellow'],
}


# =============================================================================
# Main tab widget
# =============================================================================

class WBPPExportTab(QWidget):
    """WBPP Export tab - organize files for PixInsight preprocessing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self.lang = self.config.get('application.language', 'auto')
        if self.lang == 'auto':
            from core.i18n import get_lang
            self.lang = get_lang()

        # State
        self._scanned_files: List[FileInfo] = []
        self._export_plan: List[ExportPlan] = []
        self._scan_worker: Optional[ScanWorker] = None
        self._export_worker: Optional[ExportWorker] = None
        self._export_start_time: float = 0.0

        self._init_ui()

    # -----------------------------------------------------------------
    # i18n
    # -----------------------------------------------------------------

    def _tr(self, en: str, fr: str) -> str:
        """Simple bilingual translation helper."""
        return fr if self.lang == 'fr' else en

    # =================================================================
    # UI Construction
    # =================================================================

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(6, 6, 6, 6)

        # ── Top: source selection ──
        root.addWidget(self._build_source_group())

        # ── Middle: config + preview (splitter) ──
        mid_splitter = QSplitter(Qt.Orientation.Horizontal)
        mid_splitter.addWidget(self._build_config_group())
        mid_splitter.addWidget(self._build_preview_group())
        mid_splitter.setStretchFactor(0, 2)
        mid_splitter.setStretchFactor(1, 3)
        root.addWidget(mid_splitter, 3)

        # ── Bottom: calibration + validation (splitter) ──
        bot_splitter = QSplitter(Qt.Orientation.Horizontal)
        bot_splitter.addWidget(self._build_calibration_group())
        bot_splitter.addWidget(self._build_validation_group())
        bot_splitter.setStretchFactor(0, 3)
        bot_splitter.setStretchFactor(1, 2)
        root.addWidget(bot_splitter, 2)

        # ── Progress bar ──
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setToolTip(self._tr(
            "Overall progress of the current operation",
            "Progression globale de l'operation en cours"
        ))
        root.addWidget(self.progress_bar)

        # ── Status label ──
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        self.status_label.setToolTip(self._tr(
            "Current status message",
            "Message de statut actuel"
        ))
        root.addWidget(self.status_label)

        # ── Action buttons ──
        root.addLayout(self._build_action_buttons())

    # -----------------------------------------------------------------
    # Source Selection
    # -----------------------------------------------------------------

    def _build_source_group(self) -> QGroupBox:
        group = QGroupBox(self._tr(
            "\u2B50 Source Folders", "\u2B50 Dossiers Sources"))
        group.setToolTip(self._tr(
            "Folders containing FITS/XISF files to organize for WBPP",
            "Dossiers contenant les fichiers FITS/XISF a organiser pour WBPP"
        ))
        layout = QVBoxLayout(group)

        # Folder list
        self.folder_list = QListWidget()
        self.folder_list.setMaximumHeight(90)
        self.folder_list.setToolTip(self._tr(
            "List of source folders to scan for FITS/XISF files",
            "Liste des dossiers sources a scanner pour les fichiers FITS/XISF"
        ))
        self.folder_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self.folder_list)

        # Buttons row
        btn_row = QHBoxLayout()

        self.add_light_btn = QPushButton(self._tr(
            "\u2605 Add Light Folder", "\u2605 Ajouter Dossier Lights"))
        self.add_light_btn.setToolTip(self._tr(
            "Add a folder containing LIGHT frames (science images)",
            "Ajouter un dossier contenant des fichiers LIGHT (images scientifiques)"
        ))
        self.add_light_btn.clicked.connect(lambda: self._add_folder("LIGHT"))
        btn_row.addWidget(self.add_light_btn)

        self.add_calib_btn = QPushButton(self._tr(
            "\u263E Add Calibration Folder",
            "\u263E Ajouter Dossier Calibrations"))
        self.add_calib_btn.setToolTip(self._tr(
            "Add a folder containing calibration frames (Dark, Flat, Bias)",
            "Ajouter un dossier contenant des images de calibration (Dark, Flat, Bias)"
        ))
        self.add_calib_btn.clicked.connect(lambda: self._add_folder("CALIB"))
        btn_row.addWidget(self.add_calib_btn)

        self.add_folder_btn = QPushButton(self._tr(
            "\U0001F4C1 Add Folder", "\U0001F4C1 Ajouter Dossier"))
        self.add_folder_btn.setToolTip(self._tr(
            "Add any folder (auto-detects image types from headers)",
            "Ajouter un dossier quelconque (detection auto du type depuis les en-tetes)"
        ))
        self.add_folder_btn.clicked.connect(lambda: self._add_folder("ANY"))
        btn_row.addWidget(self.add_folder_btn)

        self.remove_btn = QPushButton(self._tr(
            "\u2716 Remove Selected", "\u2716 Supprimer Selection"))
        self.remove_btn.setToolTip(self._tr(
            "Remove selected folders from the list",
            "Supprimer les dossiers selectionnes de la liste"
        ))
        self.remove_btn.clicked.connect(self._remove_selected_folders)
        btn_row.addWidget(self.remove_btn)

        btn_row.addStretch()

        self.cb_recursive = QCheckBox(self._tr(
            "Recursive scan", "Scan recursif"))
        self.cb_recursive.setChecked(True)
        self.cb_recursive.setToolTip(self._tr(
            "Scan subdirectories recursively for FITS/XISF files",
            "Scanner les sous-dossiers recursivement pour les fichiers FITS/XISF"
        ))
        btn_row.addWidget(self.cb_recursive)

        layout.addLayout(btn_row)
        return group

    # -----------------------------------------------------------------
    # Export Configuration
    # -----------------------------------------------------------------

    def _build_config_group(self) -> QGroupBox:
        group = QGroupBox(self._tr(
            "\u2699 Export Configuration", "\u2699 Configuration Export"))
        group.setToolTip(self._tr(
            "Configure the WBPP export parameters",
            "Configurer les parametres d'export WBPP"
        ))
        layout = QVBoxLayout(group)

        # Destination folder
        lbl_dest = QLabel(self._tr("Export destination:", "Destination export :"))
        lbl_dest.setToolTip(self._tr(
            "Root folder where the WBPP structure will be created",
            "Dossier racine ou la structure WBPP sera creee"
        ))
        layout.addWidget(lbl_dest)

        dest_row = QHBoxLayout()
        self.dest_input = QLineEdit()
        self.dest_input.setPlaceholderText(self._tr(
            "Select export destination...",
            "Selectionner la destination d'export..."))
        self.dest_input.setToolTip(self._tr(
            "Path to the root export folder for WBPP structure",
            "Chemin vers le dossier racine d'export pour la structure WBPP"
        ))
        dest_row.addWidget(self.dest_input)

        self.browse_dest_btn = QPushButton(self._tr("Browse...", "Parcourir..."))
        self.browse_dest_btn.setToolTip(self._tr(
            "Browse for an export destination folder",
            "Parcourir pour selectionner un dossier de destination"
        ))
        self.browse_dest_btn.clicked.connect(self._browse_destination)
        dest_row.addWidget(self.browse_dest_btn)
        layout.addLayout(dest_row)

        # Template pattern
        lbl_tmpl = QLabel(self._tr("Template pattern:", "Modele de dossiers :"))
        lbl_tmpl.setToolTip(self._tr(
            "Folder structure template using token placeholders",
            "Modele de structure de dossiers utilisant des jetons de remplacement"
        ))
        layout.addWidget(lbl_tmpl)

        self.template_input = QLineEdit("{OBJECT}/{IMAGETYP}/{FILTER}")
        self.template_input.setToolTip(self._tr(
            "Template with tokens: {OBJECT}, {IMAGETYP}, {FILTER}, {DATE}, "
            "{CAMERA}, {EXPTIME}, {TEMP}, {GAIN}, {BINNING}, {TELESCOPE}",
            "Modele avec jetons : {OBJECT}, {IMAGETYP}, {FILTER}, {DATE}, "
            "{CAMERA}, {EXPTIME}, {TEMP}, {GAIN}, {BINNING}, {TELESCOPE}"
        ))
        layout.addWidget(self.template_input)

        # Token quick-insert buttons
        token_row = QHBoxLayout()
        token_row.setSpacing(3)
        for token, tip_en, tip_fr in [
            ("{OBJECT}",   "Target name",       "Nom de la cible"),
            ("{IMAGETYP}", "Image type",        "Type d'image"),
            ("{FILTER}",   "Filter name",       "Nom du filtre"),
            ("{DATE}",     "Observation date",  "Date d'observation"),
            ("{CAMERA}",   "Camera/instrument", "Camera/instrument"),
        ]:
            btn = QPushButton(token)
            btn.setFixedHeight(22)
            btn.setToolTip(self._tr(
                f"Insert {tip_en} token into template",
                f"Inserer le jeton {tip_fr} dans le modele"
            ))
            btn.clicked.connect(lambda checked, t=token: self._insert_token(t))
            token_row.addWidget(btn)
        token_row.addStretch()
        layout.addLayout(token_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Export mode
        mode_row = QHBoxLayout()
        lbl_mode = QLabel(self._tr("Export mode:", "Mode d'export :"))
        lbl_mode.setToolTip(self._tr(
            "How files are transferred to the export folder",
            "Comment les fichiers sont transferes vers le dossier d'export"
        ))
        mode_row.addWidget(lbl_mode)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            self._tr("Copy files", "Copier les fichiers"),
            self._tr("Create symlinks", "Creer des liens symboliques"),
            self._tr("List only (dry run)", "Lister seulement (simulation)"),
        ])
        self.mode_combo.setToolTip(self._tr(
            "Copy: duplicate files, Symlink: create symbolic links, "
            "List: preview only without moving any file",
            "Copier : dupliquer les fichiers, Symlink : creer des liens symboliques, "
            "Lister : apercu seulement sans deplacer de fichier"
        ))
        mode_row.addWidget(self.mode_combo)
        layout.addLayout(mode_row)

        # Temperature tolerance
        temp_row = QHBoxLayout()
        lbl_temp = QLabel(self._tr(
            "Dark temp. tolerance:", "Tolerance temp. darks :"))
        lbl_temp.setToolTip(self._tr(
            "Maximum temperature difference in Celsius for dark frame matching",
            "Difference de temperature maximale en Celsius pour l'appairage des darks"
        ))
        temp_row.addWidget(lbl_temp)

        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 20.0)
        self.temp_spin.setValue(2.0)
        self.temp_spin.setSuffix(" \u00B0C")
        self.temp_spin.setSingleStep(0.5)
        self.temp_spin.setToolTip(self._tr(
            "Darks with temperature further than this from the lights "
            "will not be matched (default 2.0 C)",
            "Les darks dont la temperature s'ecarte de plus de cette valeur "
            "des lights ne seront pas appaires (defaut 2.0 C)"
        ))
        temp_row.addWidget(self.temp_spin)
        temp_row.addStretch()
        layout.addLayout(temp_row)

        # Checkboxes
        self.cb_include_calibrations = QCheckBox(self._tr(
            "Include calibration frames", "Inclure les calibrations"))
        self.cb_include_calibrations.setChecked(True)
        self.cb_include_calibrations.setToolTip(self._tr(
            "Include Dark, Flat, and Bias frames in the export structure",
            "Inclure les fichiers Dark, Flat et Bias dans la structure d'export"
        ))
        layout.addWidget(self.cb_include_calibrations)

        self.cb_auto_match = QCheckBox(self._tr(
            "Auto-match calibrations", "Appairage auto des calibrations"))
        self.cb_auto_match.setChecked(True)
        self.cb_auto_match.setToolTip(self._tr(
            "Automatically match darks/flats/biases to light groups by "
            "exposure, temperature, filter, and camera",
            "Appairer automatiquement les darks/flats/biases aux groupes de lights "
            "par exposition, temperature, filtre et camera"
        ))
        layout.addWidget(self.cb_auto_match)

        layout.addStretch()
        return group

    # -----------------------------------------------------------------
    # Preview Panel
    # -----------------------------------------------------------------

    def _build_preview_group(self) -> QGroupBox:
        group = QGroupBox(self._tr(
            "\U0001F4C2 Export Preview", "\U0001F4C2 Apercu de l'Export"))
        group.setToolTip(self._tr(
            "Preview of the planned folder structure before exporting",
            "Apercu de la structure de dossiers prevue avant l'export"
        ))
        layout = QVBoxLayout(group)

        # Stats bar
        self.preview_stats = QLabel("")
        self.preview_stats.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 8pt;")
        self.preview_stats.setToolTip(self._tr(
            "Summary statistics of the scanned files",
            "Statistiques resumees des fichiers scannes"
        ))
        layout.addWidget(self.preview_stats)

        # Tree widget
        self.preview_tree = QTreeWidget()
        self.preview_tree.setHeaderLabels([
            self._tr("Folder / File", "Dossier / Fichier"),
            self._tr("Files", "Fichiers"),
        ])
        self.preview_tree.setToolTip(self._tr(
            "Planned folder tree structure for the WBPP export. "
            "Green = complete, Yellow = warnings, Red = missing calibrations",
            "Arborescence prevue pour l'export WBPP. "
            "Vert = complet, Jaune = avertissements, Rouge = calibrations manquantes"
        ))
        self.preview_tree.setColumnWidth(0, 300)
        self.preview_tree.setAlternatingRowColors(True)
        self.preview_tree.header().setToolTip(self._tr(
            "Column headers for the preview tree",
            "En-tetes de colonnes de l'arborescence d'apercu"
        ))
        layout.addWidget(self.preview_tree)

        return group

    # -----------------------------------------------------------------
    # Calibration Coverage
    # -----------------------------------------------------------------

    def _build_calibration_group(self) -> QGroupBox:
        group = QGroupBox(self._tr(
            "\U0001F50D Calibration Coverage",
            "\U0001F50D Couverture des Calibrations"))
        group.setToolTip(self._tr(
            "Per-group calibration status showing darks, flats, biases availability",
            "Statut des calibrations par groupe montrant la disponibilite "
            "des darks, flats, biases"
        ))
        layout = QVBoxLayout(group)

        self.calib_table = QTableWidget()
        self.calib_table.setColumnCount(6)
        self.calib_table.setHorizontalHeaderLabels([
            self._tr("Light Group", "Groupe Light"),
            self._tr("Frames", "Images"),
            self._tr("Darks", "Darks"),
            self._tr("Flats", "Flats"),
            self._tr("Biases", "Biases"),
            self._tr("Warnings", "Alertes"),
        ])
        self.calib_table.setToolTip(self._tr(
            "Calibration coverage for each light group. "
            "Check mark = matched, Warning = partial, Cross = missing",
            "Couverture des calibrations pour chaque groupe de lights. "
            "Coche = appaire, Attention = partiel, Croix = manquant"
        ))
        self.calib_table.horizontalHeader().setToolTip(self._tr(
            "Click column headers to sort",
            "Cliquer sur les en-tetes pour trier"
        ))
        self.calib_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.calib_table.verticalHeader().setVisible(False)
        self.calib_table.setAlternatingRowColors(True)
        self.calib_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.calib_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.calib_table)

        return group

    # -----------------------------------------------------------------
    # Validation Warnings
    # -----------------------------------------------------------------

    def _build_validation_group(self) -> QGroupBox:
        group = QGroupBox(self._tr(
            "\u26A0 Validation Warnings", "\u26A0 Alertes de Validation"))
        group.setToolTip(self._tr(
            "Validation warnings and errors detected in the scanned files",
            "Alertes et erreurs de validation detectees dans les fichiers scannes"
        ))
        layout = QVBoxLayout(group)

        self.validation_text = QTextEdit()
        self.validation_text.setReadOnly(True)
        self.validation_text.setFont(get_mono_font(8))
        self.validation_text.setToolTip(self._tr(
            "Color-coded validation messages: cyan = info, "
            "yellow = warning, red = error",
            "Messages de validation en couleur : cyan = info, "
            "jaune = avertissement, rouge = erreur"
        ))
        layout.addWidget(self.validation_text)

        return group

    # -----------------------------------------------------------------
    # Action Buttons
    # -----------------------------------------------------------------

    def _build_action_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 4, 0, 2)

        self.scan_btn = QPushButton(self._tr(
            "\U0001F50E Scan Files", "\U0001F50E Scanner les Fichiers"))
        self.scan_btn.setToolTip(self._tr(
            "Scan all source folders to discover FITS/XISF files and "
            "read their headers",
            "Scanner tous les dossiers sources pour decouvrir les fichiers "
            "FITS/XISF et lire leurs en-tetes"
        ))
        self.scan_btn.setProperty("accent", True)
        self.scan_btn.clicked.connect(self._start_scan)
        row.addWidget(self.scan_btn)

        self.validate_btn = QPushButton(self._tr(
            "\u2714 Validate", "\u2714 Valider"))
        self.validate_btn.setToolTip(self._tr(
            "Run validation checks on the scanned files "
            "(calibration matching, completeness, consistency)",
            "Lancer les verifications de validation sur les fichiers scannes "
            "(appairage calibrations, completude, coherence)"
        ))
        self.validate_btn.setEnabled(False)
        self.validate_btn.clicked.connect(self._run_validation)
        row.addWidget(self.validate_btn)

        self.export_btn = QPushButton(self._tr(
            "\u25B6 Export", "\u25B6 Exporter"))
        self.export_btn.setToolTip(self._tr(
            "Execute the export plan — copy, symlink, or list files "
            "into the WBPP structure",
            "Executer le plan d'export — copier, lier, ou lister les fichiers "
            "dans la structure WBPP"
        ))
        self.export_btn.setProperty("success", True)
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._start_export)
        row.addWidget(self.export_btn)

        row.addStretch()

        self.cancel_btn = QPushButton(self._tr(
            "\u23F9 Cancel", "\u23F9 Annuler"))
        self.cancel_btn.setToolTip(self._tr(
            "Cancel the current scan or export operation",
            "Annuler l'operation de scan ou d'export en cours"
        ))
        self.cancel_btn.setProperty("danger", True)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_operation)
        row.addWidget(self.cancel_btn)

        return row

    # =================================================================
    # Folder management
    # =================================================================

    def _add_folder(self, kind: str):
        """Open a directory dialog and add the selected folder to the list."""
        titles = {
            "LIGHT": self._tr("Select Light Frames Folder",
                               "Selectionner le Dossier de Lights"),
            "CALIB": self._tr("Select Calibration Frames Folder",
                               "Selectionner le Dossier de Calibrations"),
            "ANY":   self._tr("Select Source Folder",
                               "Selectionner un Dossier Source"),
        }
        folder = QFileDialog.getExistingDirectory(
            self, titles.get(kind, titles["ANY"]))
        if not folder:
            return

        # Prevent duplicates
        for i in range(self.folder_list.count()):
            if self.folder_list.item(i).data(Qt.ItemDataRole.UserRole) == folder:
                return

        # Add to list with label
        label_map = {"LIGHT": "\u2605 ", "CALIB": "\u263E ", "ANY": "\U0001F4C1 "}
        prefix = label_map.get(kind, "")
        item = QListWidgetItem(f"{prefix}{folder}")
        item.setData(Qt.ItemDataRole.UserRole, folder)
        item.setToolTip(self._tr(
            f"Source folder: {folder}",
            f"Dossier source : {folder}"
        ))
        self.folder_list.addItem(item)

    def _remove_selected_folders(self):
        """Remove all selected items from the folder list."""
        for item in self.folder_list.selectedItems():
            self.folder_list.takeItem(self.folder_list.row(item))

    def _get_source_folders(self) -> List[str]:
        """Return all folder paths from the list widget."""
        folders = []
        for i in range(self.folder_list.count()):
            path = self.folder_list.item(i).data(Qt.ItemDataRole.UserRole)
            if path:
                folders.append(path)
        return folders

    # =================================================================
    # Destination
    # =================================================================

    def _browse_destination(self):
        """Browse for the export destination folder."""
        folder = QFileDialog.getExistingDirectory(
            self, self._tr("Select Export Destination",
                            "Selectionner la Destination d'Export"))
        if folder:
            self.dest_input.setText(folder)

    # =================================================================
    # Template helper
    # =================================================================

    def _insert_token(self, token: str):
        """Insert a token at the cursor position in the template field."""
        cursor_pos = self.template_input.cursorPosition()
        current = self.template_input.text()
        new_text = current[:cursor_pos] + token + current[cursor_pos:]
        self.template_input.setText(new_text)
        self.template_input.setCursorPosition(cursor_pos + len(token))

    # =================================================================
    # Export mode mapping
    # =================================================================

    def _get_export_mode(self) -> str:
        """Map combo box index to export mode string."""
        idx = self.mode_combo.currentIndex()
        return ['copy', 'symlink', 'list'][idx]

    # =================================================================
    # Scan operation
    # =================================================================

    def _start_scan(self):
        """Launch the background scan worker."""
        if not WBPP_AVAILABLE:
            self._set_status(self._tr(
                "WBPP export module not available",
                "Module d'export WBPP non disponible"), error=True)
            return

        folders = self._get_source_folders()
        if not folders:
            self._set_status(self._tr(
                "No source folders selected",
                "Aucun dossier source selectionne"), error=True)
            return

        self._set_busy(True)
        self._clear_results()

        self._scan_worker = ScanWorker(folders, self.cb_recursive.isChecked())
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.error.connect(self._on_worker_error)
        self._scan_worker.start()

    def _on_scan_progress(self, current: int, total: int, msg: str):
        """Update progress bar during scanning."""
        self.progress_bar.setMaximum(max(total, 1))
        self.progress_bar.setValue(current)
        self._set_status(msg)

    def _on_scan_finished(self, files: list):
        """Process scan results and populate preview."""
        self._scanned_files = files
        self._set_busy(False)

        if not files:
            self._set_status(self._tr(
                "No FITS/XISF files found in the selected folders",
                "Aucun fichier FITS/XISF trouve dans les dossiers selectionnes"))
            return

        # Build export plan
        dest = self.dest_input.text().strip()
        if not dest:
            dest = str(Path(self._get_source_folders()[0]) / "WBPP_Export")
            self.dest_input.setText(dest)

        template = self.template_input.text().strip() or None
        self._export_plan = build_export_plan(
            files, dest, template=template,
            include_calibrations=self.cb_include_calibrations.isChecked(),
        )

        # Populate UI
        self._populate_preview()
        self._populate_calibration_table()
        self._run_validation()

        self.validate_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

        # Stats summary
        stats = get_plan_statistics(self._export_plan)
        type_summary = ", ".join(
            f"{_TYPE_ICONS.get(t, '')} {t}: {c}"
            for t, c in sorted(stats.get('by_type', {}).items())
        )
        self._set_status(self._tr(
            f"Scan complete: {stats['total_files']} files "
            f"({stats.get('total_size_gb', 0):.1f} GB) | {type_summary}",
            f"Scan termine : {stats['total_files']} fichiers "
            f"({stats.get('total_size_gb', 0):.1f} Go) | {type_summary}"
        ))

    # =================================================================
    # Preview tree
    # =================================================================

    def _populate_preview(self):
        """Build the preview tree from the export plan."""
        self.preview_tree.clear()
        if not self._export_plan:
            return

        tree_data = get_folder_preview(self._export_plan)
        stats = get_plan_statistics(self._export_plan)

        # Stats label
        size_str = f"{stats.get('total_size_gb', 0):.1f}"
        self.preview_stats.setText(self._tr(
            f"{stats['total_files']} files | "
            f"{stats.get('unique_folders', 0)} folders | "
            f"{size_str} GB total",
            f"{stats['total_files']} fichiers | "
            f"{stats.get('unique_folders', 0)} dossiers | "
            f"{size_str} Go total"
        ))

        # Build tree recursively
        self._add_tree_nodes(None, tree_data)
        self.preview_tree.expandAll()

    def _add_tree_nodes(self, parent_item, data: dict):
        """Recursively add nodes to the preview tree."""
        for key, value in sorted(data.items()):
            if key == '_files':
                continue

            # Determine icon and color from image type keywords
            icon = '\U0001F4C1'  # Default folder icon
            color = COLORS['text_primary']
            key_upper = key.upper()
            for img_type, type_icon in _TYPE_ICONS.items():
                if img_type in key_upper:
                    icon = type_icon
                    color = _TYPE_COLORS.get(img_type, color)
                    break

            # Count files recursively under this node
            file_count = self._count_files_recursive(value)

            if parent_item is None:
                item = QTreeWidgetItem(self.preview_tree)
            else:
                item = QTreeWidgetItem(parent_item)

            item.setText(0, f"{icon} {key}")
            item.setText(1, str(file_count) if file_count > 0 else "")
            item.setForeground(0, QBrush(QColor(color)))
            item.setToolTip(0, self._tr(
                f"Folder: {key} ({file_count} files)",
                f"Dossier : {key} ({file_count} fichiers)"
            ))
            item.setToolTip(1, self._tr(
                f"Number of files in this folder",
                f"Nombre de fichiers dans ce dossier"
            ))

            # Recurse into subfolders
            if isinstance(value, dict):
                self._add_tree_nodes(item, value)

    def _count_files_recursive(self, node: dict) -> int:
        """Count total files under a tree node."""
        count = len(node.get('_files', []))
        for key, value in node.items():
            if key != '_files' and isinstance(value, dict):
                count += self._count_files_recursive(value)
        return count

    # =================================================================
    # Calibration table
    # =================================================================

    def _populate_calibration_table(self):
        """Fill the calibration coverage table from scanned files."""
        self.calib_table.setRowCount(0)
        if not self._scanned_files:
            return

        # Separate by type
        lights = [f for f in self._scanned_files if f.image_type == 'LIGHT']
        darks = [f for f in self._scanned_files if f.image_type == 'DARK']
        flats = [f for f in self._scanned_files if f.image_type == 'FLAT']
        biases = [f for f in self._scanned_files if f.image_type == 'BIAS']

        if not lights:
            return

        # Match calibrations
        tol = self.temp_spin.value()
        matches = match_calibrations(lights, darks, flats, biases, tol)

        # Group lights for count
        light_groups = defaultdict(int)
        for lf in lights:
            key = f"{lf.target}|{lf.filter_name}"
            light_groups[key] += 1

        self.calib_table.setRowCount(len(matches))

        for row, (key, match) in enumerate(sorted(matches.items())):
            target, filt = key.split('|', 1)
            frame_count = light_groups.get(key, 0)

            # Column 0: Light group
            item_group = QTableWidgetItem(f"{target} / {filt}")
            item_group.setForeground(QBrush(QColor(COLORS['accent_cyan'])))
            item_group.setToolTip(self._tr(
                f"Light group: target={target}, filter={filt}",
                f"Groupe light : cible={target}, filtre={filt}"
            ))
            self.calib_table.setItem(row, 0, item_group)

            # Column 1: Frame count
            item_count = QTableWidgetItem(str(frame_count))
            item_count.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter)
            item_count.setToolTip(self._tr(
                f"{frame_count} light frames in this group",
                f"{frame_count} images light dans ce groupe"
            ))
            self.calib_table.setItem(row, 1, item_count)

            # Column 2: Darks status
            self.calib_table.setItem(row, 2,
                self._make_status_item(
                    match.darks, "Dark",
                    f"\u0394T={match.dark_temp_delta:.1f}\u00B0C"
                    if match.darks else ""))

            # Column 3: Flats status
            self.calib_table.setItem(row, 3,
                self._make_status_item(match.flats, "Flat"))

            # Column 4: Biases status
            self.calib_table.setItem(row, 4,
                self._make_status_item(match.biases, "Bias"))

            # Column 5: Warning count
            warn_count = len(match.warnings)
            item_warn = QTableWidgetItem(
                str(warn_count) if warn_count > 0 else "\u2714")
            if warn_count > 0:
                item_warn.setForeground(QBrush(QColor(COLORS['warning'])))
            else:
                item_warn.setForeground(QBrush(QColor(COLORS['success'])))
            item_warn.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter)
            item_warn.setToolTip(self._tr(
                "\n".join(match.warnings) if match.warnings
                else "No warnings for this group",
                "\n".join(match.warnings) if match.warnings
                else "Aucune alerte pour ce groupe"
            ))
            self.calib_table.setItem(row, 5, item_warn)

    def _make_status_item(self, frames: list, frame_type: str,
                          extra: str = "") -> QTableWidgetItem:
        """Create a color-coded status cell for calibration coverage."""
        if frames:
            count = len(frames)
            text = f"\u2714 {count}"
            if extra:
                text += f" ({extra})"
            item = QTableWidgetItem(text)
            item.setForeground(QBrush(QColor(COLORS['success'])))
            item.setToolTip(self._tr(
                f"{count} {frame_type} frames matched",
                f"{count} images {frame_type} appairees"
            ))
        else:
            item = QTableWidgetItem("\u2718 0")
            item.setForeground(QBrush(QColor(COLORS['error'])))
            item.setToolTip(self._tr(
                f"No {frame_type} frames matched for this group",
                f"Aucune image {frame_type} appairee pour ce groupe"
            ))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    # =================================================================
    # Validation
    # =================================================================

    def _run_validation(self):
        """Run validation checks and display results."""
        self.validation_text.clear()
        if not self._scanned_files:
            return

        warnings = validate_export(
            self._scanned_files,
            temp_tolerance=self.temp_spin.value(),
        )

        if not warnings:
            self._append_validation(
                self._tr("\u2714 All checks passed - ready for export",
                         "\u2714 Toutes les verifications sont passees - pret pour l'export"),
                "info")
            return

        for w in warnings:
            # Classify by content
            w_lower = w.lower()
            if "no " in w_lower and ("dark" in w_lower or "flat" in w_lower
                                     or "bias" in w_lower):
                level = "error"
            elif "mismatch" in w_lower or "mixed" in w_lower:
                level = "warning"
            elif "only" in w_lower and "frame" in w_lower:
                level = "warning"
            else:
                level = "info"
            self._append_validation(w, level)

    def _append_validation(self, msg: str, level: str = "info"):
        """Append a color-coded message to the validation panel."""
        color_map = {
            'info':    COLORS['info'],
            'warning': COLORS['warning'],
            'error':   COLORS['error'],
        }
        color = color_map.get(level, COLORS['text_primary'])
        icon_map = {'info': '\u2139', 'warning': '\u26A0', 'error': '\u2718'}
        icon = icon_map.get(level, '')
        self.validation_text.append(
            f'<span style="color:{color};">{icon} {msg}</span>'
        )

    # =================================================================
    # Export operation
    # =================================================================

    def _start_export(self):
        """Launch the background export worker."""
        if not self._export_plan:
            self._set_status(self._tr(
                "No export plan. Scan files first.",
                "Aucun plan d'export. Scannez les fichiers d'abord."), error=True)
            return

        mode = self._get_export_mode()
        dest = self.dest_input.text().strip()

        # Safety: verify destination does not contain path traversal
        if '..' in dest:
            self._set_status(self._tr(
                "Invalid destination path (contains '..')",
                "Chemin de destination invalide (contient '..')"), error=True)
            return

        # Rebuild plan with current settings in case user changed template/dest
        template = self.template_input.text().strip() or None
        self._export_plan = build_export_plan(
            self._scanned_files, dest, template=template,
            include_calibrations=self.cb_include_calibrations.isChecked(),
        )

        self._set_busy(True)
        self._export_start_time = time.time()

        self._export_worker = ExportWorker(self._export_plan, mode)
        self._export_worker.progress.connect(self._on_export_progress)
        self._export_worker.finished.connect(self._on_export_finished)
        self._export_worker.error.connect(self._on_worker_error)
        self._export_worker.start()

    def _on_export_progress(self, current: int, total: int, msg: str):
        """Update progress bar and ETA during export."""
        self.progress_bar.setMaximum(max(total, 1))
        self.progress_bar.setValue(current)

        # Compute ETA
        elapsed = time.time() - self._export_start_time
        if current > 0 and elapsed > 0:
            rate = current / elapsed
            remaining = (total - current) / rate if rate > 0 else 0
            eta_str = self._format_duration(remaining)
            self._set_status(f"{msg}  |  ETA: {eta_str}")
        else:
            self._set_status(msg)

    def _on_export_finished(self, result):
        """Handle export completion."""
        self._set_busy(False)

        if isinstance(result, ExportResult):
            elapsed = time.time() - self._export_start_time
            duration_str = self._format_duration(elapsed)
            self._set_status(self._tr(
                f"Export complete: {result.copied_files}/{result.total_files} "
                f"files ({duration_str})"
                + (f", {result.failed_files} failed" if result.failed_files else ""),
                f"Export termine : {result.copied_files}/{result.total_files} "
                f"fichiers ({duration_str})"
                + (f", {result.failed_files} echoue(s)" if result.failed_files else "")
            ))

            # Show errors in validation panel
            if result.errors:
                for err in result.errors:
                    self._append_validation(err, "error")
        else:
            self._set_status(self._tr(
                "Export finished with unknown result",
                "Export termine avec un resultat inconnu"))

    # =================================================================
    # Error & cancel
    # =================================================================

    def _on_worker_error(self, msg: str):
        """Handle worker thread error."""
        self._set_busy(False)
        self._set_status(f"Error: {msg}", error=True)
        self._append_validation(msg, "error")

    def _cancel_operation(self):
        """Cancel the current scan or export."""
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.cancel()
        if self._export_worker and self._export_worker.isRunning():
            self._export_worker.cancel()
        self._set_status(self._tr("Operation cancelled", "Operation annulee"))

    # =================================================================
    # UI state helpers
    # =================================================================

    def _set_busy(self, busy: bool):
        """Toggle UI state between idle and busy."""
        self.scan_btn.setEnabled(not busy)
        self.validate_btn.setEnabled(not busy and bool(self._scanned_files))
        self.export_btn.setEnabled(not busy and bool(self._export_plan))
        self.cancel_btn.setVisible(busy)
        self.progress_bar.setVisible(busy)
        if not busy:
            self.progress_bar.setValue(0)

    def _set_status(self, msg: str, error: bool = False):
        """Update the status label."""
        color = COLORS['error'] if error else COLORS['text_secondary']
        self.status_label.setStyleSheet(f"color: {color};")
        self.status_label.setText(msg)

    def _clear_results(self):
        """Clear all result panels."""
        self._scanned_files = []
        self._export_plan = []
        self.preview_tree.clear()
        self.preview_stats.setText("")
        self.calib_table.setRowCount(0)
        self.validation_text.clear()
        self.validate_btn.setEnabled(False)
        self.export_btn.setEnabled(False)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format a duration in seconds to a human-readable string."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        if minutes < 60:
            return f"{minutes}m{secs:02d}s"
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h{mins:02d}m"
