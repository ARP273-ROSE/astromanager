#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - COMPRESSION TAB
================================================================================
Multi-codec compression with user-friendly profile selection.
Integrates compression.py profiles with detailed explanations.
Sub-tabs for folders, profiles, and options with airy layout.
================================================================================
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox,
    QPushButton, QLabel, QLineEdit, QFileDialog, QRadioButton,
    QButtonGroup, QTextEdit, QTabWidget, QScrollArea, QFrame,
    QSizePolicy, QSpacerItem
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


class CompressionTab(QWidget):
    """Compression tab - Multi-format compression with profile selection"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.config = get_config()
        self.lang = self.config.get('application.language', 'auto')
        if self.lang == 'auto':
            import locale
            try:
                loc = locale.getdefaultlocale()[0]
                self.lang = 'fr' if loc and loc.lower().startswith('fr') else 'en'
            except Exception:
                self.lang = 'en'
        self._init_ui()

    def _tr(self, en, fr):
        return fr if self.lang == 'fr' else en

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Sub-tabs for organized content ──
        self.sub_tabs = QTabWidget()
        self.sub_tabs.addTab(self._create_folders_tab(), self._tr("📁 Folders & Format", "📁 Dossiers & Format"))
        self.sub_tabs.addTab(self._create_profiles_tab(), self._tr("🗜️ XISF Profile", "🗜️ Profil XISF"))
        self.sub_tabs.addTab(self._create_options_tab(), self._tr("⚙️ Options & Preview", "⚙️ Options & Aperçu"))
        layout.addWidget(self.sub_tabs, 1)

        # ── Action Buttons (always visible) ──
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 4, 0, 2)
        btn_layout.addStretch()

        self.stop_btn = QPushButton(self._tr("⏹ Cancel", "⏹ Annuler"))
        self.stop_btn.setToolTip(self._tr(
            "Cancel the current compression",
            "Annuler la compression en cours"
        ))
        self.stop_btn.setProperty("danger", True)
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self._stop)
        btn_layout.addWidget(self.stop_btn)

        self.start_btn = QPushButton(self._tr("▶ Start Compression", "▶ Démarrer Compression"))
        self.start_btn.setToolTip(self._tr(
            "Start batch compression with selected profile",
            "Démarrer la compression par lot avec le profil sélectionné"
        ))
        self.start_btn.setProperty("accent", True)
        self.start_btn.clicked.connect(self._start_compression)
        btn_layout.addWidget(self.start_btn)
        layout.addLayout(btn_layout)

        # ── Console (always visible) ──
        self.console = QTextEdit()
        self.console.setToolTip(self._tr(
            "Compression progress and output log",
            "Progression de la compression et journal de sortie"
        ))
        self.console.setReadOnly(True)
        self.console.setFont(get_mono_font(9))
        self.console.setMinimumHeight(100)
        self.console.setMaximumHeight(180)
        layout.addWidget(self.console)

    def _create_folders_tab(self):
        """Sub-tab 1: Source/target folders + output format"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 8, 6, 6)

        # Source folder
        src_group = QGroupBox(self._tr("📂 Source Folder", "📂 Dossier Source"))
        src_layout = QVBoxLayout(src_group)
        src_layout.setSpacing(6)

        src_desc = QLabel(self._tr(
            "Folder containing FITS/XISF files to compress.",
            "Dossier contenant les fichiers FITS/XISF à compresser."
        ))
        src_desc.setStyleSheet("color: #7a8498;")
        src_layout.addWidget(src_desc)

        src_row = QHBoxLayout()
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText(self._tr(
            "Select folder with files to compress...",
            "Sélectionner dossier avec fichiers à compresser..."
        ))
        self.source_input.setMinimumHeight(24)
        src_row.addWidget(self.source_input)
        src_btn = QPushButton(self._tr("Browse...", "Parcourir..."))
        src_btn.setMinimumHeight(24)
        src_btn.clicked.connect(lambda: self._browse('source'))
        src_row.addWidget(src_btn)
        src_layout.addLayout(src_row)
        layout.addWidget(src_group)

        # Backup folder
        bak_group = QGroupBox(self._tr("📂 Backup Folder", "📂 Dossier de Sauvegarde"))
        bak_layout = QVBoxLayout(bak_group)
        bak_layout.setSpacing(6)

        bak_desc = QLabel(self._tr(
            "Originals are moved here after successful compression + verification. Leave empty to skip backup.",
            "Les originaux sont déplacés ici après compression + vérification réussie. Laisser vide = pas de sauvegarde."
        ))
        bak_desc.setStyleSheet("color: #7a8498;")
        bak_layout.addWidget(bak_desc)

        bak_row = QHBoxLayout()
        self.backup_input = QLineEdit()
        self.backup_input.setPlaceholderText(self._tr(
            "Backup folder (leave empty = no backup)",
            "Dossier de sauvegarde (vide = pas de sauvegarde)"
        ))
        self.backup_input.setMinimumHeight(24)
        bak_row.addWidget(self.backup_input)
        bak_btn = QPushButton(self._tr("Browse...", "Parcourir..."))
        bak_btn.setMinimumHeight(24)
        bak_btn.clicked.connect(lambda: self._browse('backup'))
        bak_row.addWidget(bak_btn)
        bak_layout.addLayout(bak_row)
        layout.addWidget(bak_group)

        # Output format
        format_group = QGroupBox(self._tr("📤 Output Format", "📤 Format de Sortie"))
        format_layout = QVBoxLayout(format_group)
        format_layout.setSpacing(8)
        self.format_group = QButtonGroup(self)

        format_options = [
            ('xisf', 'XISF',
             self._tr("Compressed XISF using selected profile (recommended)",
                       "XISF compressé avec le profil sélectionné (recommandé)")),
            ('fz', 'FITS.FZ',
             self._tr("RICE tile compression via astropy (no external tools needed)",
                       "Compression par tuiles RICE via astropy (aucun outil externe requis)")),
            ('fits', 'FITS',
             self._tr("Uncompressed FITS (decompress XISF/FZ to standard FITS)",
                       "FITS non compressé (décompresser XISF/FZ en FITS standard)")),
        ]
        for i, (fmt_key, fmt_label, fmt_desc) in enumerate(format_options):
            radio = QRadioButton(f"{fmt_label}  —  {fmt_desc}")
            radio.setProperty('format_key', fmt_key)
            if i == 0:
                radio.setChecked(True)
            self.format_group.addButton(radio, i)
            format_layout.addWidget(radio)

        layout.addWidget(format_group)
        layout.addStretch()
        return widget

    def _create_profiles_tab(self):
        """Sub-tab 2: Compression profiles with full descriptions"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 8, 6, 6)

        header = QLabel(self._tr(
            "Select a compression profile for XISF output. Each profile balances speed vs compression ratio.",
            "Sélectionnez un profil de compression pour la sortie XISF. Chaque profil équilibre vitesse et taux de compression."
        ))
        header.setStyleSheet("color: #7a8498; font-size: 9pt;")
        header.setWordWrap(True)
        layout.addWidget(header)
        layout.addSpacing(8)

        self.profile_group = QButtonGroup(self)

        profile_order = ['zlib_6', 'zstd_6', 'zstd_10', 'lz4', 'zlib_1', 'zlib_9', 'zstd_3', 'zstd_19', 'lz4_hc']
        default_profile = self.config.get('compression.default_profile', 'zlib_6')

        for i, profile_name in enumerate(profile_order):
            profile = COMPRESSION_PROFILES.get(profile_name, {})
            if not profile:
                continue

            lang_key = 'fr' if self.lang == 'fr' else 'en'
            name = profile.get(f'name_{lang_key}', profile_name)
            desc = profile.get(f'desc_{lang_key}', '')

            radio = QRadioButton(f"  {name}")
            radio.setToolTip(desc)
            radio.setProperty('profile_name', profile_name)
            radio.setStyleSheet("font-size: 9pt; padding: 1px 0;")

            if profile_name == default_profile:
                radio.setChecked(True)

            self.profile_group.addButton(radio, i)
            layout.addWidget(radio)

            # Full description (not truncated)
            desc_label = QLabel(f"      {desc}")
            desc_label.setStyleSheet("color: #7a8498; font-size: 9pt; padding-left: 24px;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
            layout.addSpacing(4)

        layout.addStretch()
        scroll.setWidget(widget)
        return scroll

    def _create_options_tab(self):
        """Sub-tab 3: Options + file scan preview"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 8, 6, 6)

        # Options
        opts_group = QGroupBox(self._tr("⚙️ Compression Options", "⚙️ Options de Compression"))
        opts_layout = QVBoxLayout(opts_group)
        opts_layout.setSpacing(8)

        self.cb_verify = QCheckBox(self._tr(
            "Verify file integrity after compression",
            "Vérifier l'intégrité des fichiers après compression"
        ))
        self.cb_verify.setChecked(self.config.get('compression.verify_integrity', True))
        opts_layout.addWidget(self.cb_verify)

        self.cb_quarantine = QCheckBox(self._tr(
            "Move failed files to quarantine folder",
            "Déplacer les fichiers en échec dans un dossier de quarantaine"
        ))
        self.cb_quarantine.setChecked(True)
        opts_layout.addWidget(self.cb_quarantine)

        layout.addWidget(opts_group)

        # Preview
        preview_group = QGroupBox(self._tr("📊 File Scan Preview", "📊 Aperçu du Scan"))
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setSpacing(6)

        preview_desc = QLabel(self._tr(
            "Scan the source folder to preview how many files will be compressed and estimated savings.",
            "Scanner le dossier source pour voir combien de fichiers seront compressés et l'économie estimée."
        ))
        preview_desc.setStyleSheet("color: #7a8498;")
        preview_desc.setWordWrap(True)
        preview_layout.addWidget(preview_desc)

        self.preview_label = QLabel(self._tr(
            "Select a source folder first, then click Scan.",
            "Sélectionnez d'abord un dossier source, puis cliquez Scanner."
        ))
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(60)
        self.preview_label.setStyleSheet("font-size: 11pt; padding: 8px;")
        preview_layout.addWidget(self.preview_label)

        self.scan_btn = QPushButton(self._tr("🔍 Scan Files", "🔍 Scanner Fichiers"))
        self.scan_btn.setToolTip(self._tr(
            "Scan source folder and show compression preview",
            "Scanner le dossier source et afficher l'aperçu de compression"
        ))
        self.scan_btn.clicked.connect(self._scan_preview)
        preview_layout.addWidget(self.scan_btn)

        layout.addWidget(preview_group)
        layout.addStretch()
        return widget

    def _browse(self, which):
        folder = QFileDialog.getExistingDirectory(self, self._tr("Select Folder", "Sélectionner Dossier"))
        if folder:
            if which == 'source':
                self.source_input.setText(folder)
            else:
                self.backup_input.setText(folder)

    def _get_selected_profile(self):
        btn = self.profile_group.checkedButton()
        if btn:
            return btn.property('profile_name')
        return 'zlib_6'

    def _get_selected_format(self):
        btn = self.format_group.checkedButton()
        if btn:
            return btn.property('format_key')
        return 'xisf'

    def _scan_preview(self):
        source = self.source_input.text().strip()
        if not source or not os.path.isdir(source):
            self.preview_label.setText(self._tr("❌ Select a valid source folder", "❌ Sélectionnez un dossier source valide"))
            return

        count = 0
        total_size = 0
        for root, _, files in os.walk(source):
            for f in files:
                if f.lower().endswith(('.fits', '.fit', '.xisf', '.fz')):
                    count += 1
                    try:
                        total_size += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass

        size_gb = total_size / (1024**3)
        estimated_gb = size_gb * 0.5  # Rough estimate for zlib_6

        self.preview_label.setText(
            f"{self._tr('Files', 'Fichiers')}: {count}\n"
            f"{self._tr('Total size', 'Taille totale')}: {size_gb:.1f} GB\n"
            f"{self._tr('Estimated after', 'Estimé après')}: ~{estimated_gb:.1f} GB\n"
            f"{self._tr('Space saved', 'Espace économisé')}: ~{size_gb - estimated_gb:.1f} GB ({50}%)"
        )

    def _start_compression(self):
        source = self.source_input.text().strip()
        if not source or not os.path.isdir(source):
            self.console.append(self._tr("❌ Select a valid source folder", "❌ Sélectionnez un dossier source valide"))
            return

        self.console.clear()
        self.start_btn.setVisible(False)
        self.stop_btn.setVisible(True)

        profile = self._get_selected_profile()
        backup = self.backup_input.text().strip() or ''

        self.worker = UnifiedWorker()
        self.worker.output_signal.connect(lambda t: self.console.append(t.rstrip()) if t.strip() else None)
        self.worker.progress_signal.connect(lambda c, t, p: signals.analysis_progress.emit(c, t, p))
        self.worker.finished_signal.connect(self._on_finished)

        job = WorkerJob(
            job_type=JobType.COMPRESSION,
            params={
                'source_folder': source,
                'backup_folder': backup,
                'profile': profile,
                'output_format': self._get_selected_format(),
                'verify_integrity': self.cb_verify.isChecked(),
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
        if success and result:
            signals.compression_completed.emit(result)
