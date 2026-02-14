#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - ANALYSIS TAB
================================================================================
FITS/XISF file analysis with target detection, report generation.
Reuses existing fits_analyser_gui.py analysis engine.
================================================================================
"""

import os
import sys
import locale
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox,
    QPushButton, QLabel, QLineEdit, QFileDialog, QSpinBox,
    QComboBox, QTextEdit, QTabWidget, QFrame, QSplitter,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QTextCursor, QFont

from core.workers import UnifiedWorker, WorkerJob, JobType
from core.signals import signals
from core.config import get_config
from gui.theme import get_mono_font, prettify_filter_name


class AnalysisTab(QWidget):
    """Analysis tab - FITS/XISF file analysis and report generation"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.output_folder = ''
        self._last_result = None
        self._console_buffer = []
        self._console_timer = QTimer(self)
        self._console_timer.setInterval(100)
        self._console_timer.timeout.connect(self._flush_console)
        self.config = get_config()
        self.lang = self.config.get('application.language', 'auto')
        if self.lang == 'auto':
            try:
                lang = locale.getdefaultlocale()[0]
                self.lang = 'fr' if lang and lang.startswith('fr') else 'en'
            except Exception:
                self.lang = 'en'
        self._init_ui()
        self._restore_options()
        self._connect_signals()

    def _tr(self, en, fr):
        """Simple translation helper"""
        return fr if self.lang == 'fr' else en

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Folder Selection ──
        folder_group = QGroupBox(self._tr("📁 Folder Selection", "📁 Sélection du Dossier"))
        folder_layout = QHBoxLayout(folder_group)
        self.folder_input = QLineEdit()
        self.folder_input.setToolTip(self._tr(
            "Path to folder containing FITS/XISF files to analyze",
            "Chemin vers le dossier contenant les fichiers FITS/XISF à analyser"
        ))
        self.folder_input.setPlaceholderText(self._tr("Select folder to analyze...", "Sélectionner un dossier à analyser..."))
        folder_layout.addWidget(self.folder_input)
        self.browse_btn = QPushButton(self._tr("Browse...", "Parcourir..."))
        self.browse_btn.setToolTip(self._tr(
            "Browse for a folder containing FITS/XISF files",
            "Parcourir pour sélectionner un dossier contenant des fichiers FITS/XISF"
        ))
        self.browse_btn.clicked.connect(self._browse_folder)
        folder_layout.addWidget(self.browse_btn)
        layout.addWidget(folder_group)

        # ── Options Row ──
        options_layout = QHBoxLayout()

        # Analysis Options
        analysis_group = QGroupBox(self._tr("🔧 Analysis Options", "🔧 Options d'Analyse"))
        analysis_layout = QVBoxLayout(analysis_group)
        self.cb_simbad = QCheckBox(self._tr("Resolve targets via SIMBAD", "Résoudre les cibles via SIMBAD"))
        self.cb_simbad.setToolTip(self._tr(
            "Query SIMBAD to merge duplicates (M31 = NGC 224) and get object types",
            "Interroger SIMBAD pour fusionner les doublons (M31 = NGC 224) et obtenir les types d'objets"
        ))
        analysis_layout.addWidget(self.cb_simbad)

        self.cb_plate_solve = QCheckBox(self._tr("Plate solve (detect reducers)", "Plate solving (détecter réducteurs)"))
        self.cb_plate_solve.setToolTip(self._tr(
            "Use ASTAP to detect focal reducers by comparing actual vs expected image scale",
            "Utiliser ASTAP pour détecter les réducteurs focaux en comparant l'échelle réelle vs attendue"
        ))
        analysis_layout.addWidget(self.cb_plate_solve)

        self.cb_weather = QCheckBox(self._tr("Fetch weather data", "Récupérer données météo"))
        self.cb_weather.setToolTip(self._tr(
            "Fetch historical weather data from Open-Meteo for each observation date",
            "Récupérer les données météo historiques de Open-Meteo pour chaque date d'observation"
        ))
        analysis_layout.addWidget(self.cb_weather)
        options_layout.addWidget(analysis_group)

        # Output Formats
        output_group = QGroupBox(self._tr("📊 Output Formats", "📊 Formats de Sortie"))
        output_layout = QVBoxLayout(output_group)
        self.cb_graphs = QCheckBox(self._tr("Graphs", "Graphiques"))
        self.cb_graphs.setToolTip(self._tr(
            "Generate statistical charts and graphs",
            "Générer des graphiques et diagrammes statistiques"
        ))
        output_layout.addWidget(self.cb_graphs)
        self.cb_latex = QCheckBox(self._tr("LaTeX/PDF Report", "Rapport LaTeX/PDF"))
        self.cb_latex.setToolTip(self._tr(
            "Generate a full LaTeX/PDF report with all analysis details",
            "Générer un rapport LaTeX/PDF complet avec tous les détails d'analyse"
        ))
        output_layout.addWidget(self.cb_latex)
        self.cb_thumbnails = QCheckBox(self._tr("Thumbnails", "Miniatures"))
        self.cb_thumbnails.setToolTip(self._tr(
            "Generate thumbnail preview images for each FITS/XISF file",
            "Générer des miniatures d'aperçu pour chaque fichier FITS/XISF"
        ))
        output_layout.addWidget(self.cb_thumbnails)
        self.cb_astrobin = QCheckBox(self._tr("AstroBin CSV", "CSV AstroBin"))
        self.cb_astrobin.setToolTip(self._tr(
            "Export acquisition data as CSV for AstroBin import",
            "Exporter les données d'acquisition en CSV pour import AstroBin"
        ))
        output_layout.addWidget(self.cb_astrobin)
        options_layout.addWidget(output_group)

        # Processing
        proc_group = QGroupBox(self._tr("⚡ Processing", "⚡ Traitement"))
        proc_layout = QVBoxLayout(proc_group)
        workers_layout = QHBoxLayout()
        workers_layout.addWidget(QLabel(self._tr("Workers:", "Workers:")))
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(0, 64)
        self.workers_spin.setValue(0)
        self.workers_spin.setToolTip(self._tr("0 = Auto-detect", "0 = Auto-détection"))
        workers_layout.addWidget(self.workers_spin)
        workers_layout.addWidget(QLabel(self._tr("(0 = Auto)", "(0 = Auto)")))
        proc_layout.addLayout(workers_layout)

        # Compress option
        self.cb_compress = QCheckBox(self._tr("Compress FITS → XISF after analysis", "Compresser FITS → XISF après analyse"))
        self.cb_compress.setToolTip(self._tr(
            "Automatically compress FITS files to XISF format after analysis",
            "Compresser automatiquement les fichiers FITS en format XISF après l'analyse"
        ))
        proc_layout.addWidget(self.cb_compress)
        self.cb_extract_dups = QCheckBox(self._tr("Extract duplicates", "Extraire les duplicatas"))
        self.cb_extract_dups.setToolTip(self._tr(
            "Move detected duplicate files to a separate folder",
            "Déplacer les fichiers dupliqués détectés dans un dossier séparé"
        ))
        proc_layout.addWidget(self.cb_extract_dups)

        self.cb_auto_history = QCheckBox(self._tr("Save to observation history", "Sauvegarder dans l'historique"))
        self.cb_auto_history.setToolTip(self._tr(
            "Automatically save analysis results to the observation history database "
            "(duplicates are detected and replaced, not added twice)",
            "Sauvegarder automatiquement les résultats dans la base d'historique d'observations "
            "(les doublons sont détectés et remplacés, pas ajoutés en double)"
        ))
        self.cb_auto_history.setChecked(True)
        proc_layout.addWidget(self.cb_auto_history)

        # Telescope merging button
        self.merge_telescopes_btn = QPushButton(self._tr("🔗 Telescope Aliases...", "🔗 Alias Télescopes..."))
        self.merge_telescopes_btn.setToolTip(self._tr(
            "Define telescope name aliases to merge identical instruments with different names",
            "Définir des alias de noms de télescopes pour fusionner les instruments identiques avec des noms différents"
        ))
        self.merge_telescopes_btn.clicked.connect(self._show_telescope_aliases)
        proc_layout.addWidget(self.merge_telescopes_btn)

        options_layout.addWidget(proc_group)
        layout.addLayout(options_layout)

        # ── Buttons ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.stop_btn = QPushButton(self._tr("⏹ Stop", "⏹ Arrêter"))
        self.stop_btn.setToolTip(self._tr(
            "Stop the current analysis",
            "Arrêter l'analyse en cours"
        ))
        self.stop_btn.setProperty("danger", True)
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self._stop_analysis)
        btn_layout.addWidget(self.stop_btn)

        self.start_btn = QPushButton(self._tr("▶ Start Analysis", "▶ Démarrer l'Analyse"))
        self.start_btn.setToolTip(self._tr(
            "Start the analysis of all FITS/XISF files in the selected folder",
            "Démarrer l'analyse de tous les fichiers FITS/XISF dans le dossier sélectionné"
        ))
        self.start_btn.setProperty("accent", True)
        self.start_btn.clicked.connect(self._start_analysis)
        btn_layout.addWidget(self.start_btn)

        self.open_folder_btn = QPushButton(self._tr("📁 Open Output Folder", "📁 Ouvrir Dossier Sortie"))
        self.open_folder_btn.setToolTip(self._tr(
            "Open the output folder in file explorer",
            "Ouvrir le dossier de sortie dans l'explorateur de fichiers"
        ))
        self.open_folder_btn.setVisible(False)
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        btn_layout.addWidget(self.open_folder_btn)

        self.open_html_btn = QPushButton(self._tr("🌐 Open HTML Report", "🌐 Ouvrir Rapport HTML"))
        self.open_html_btn.setToolTip(self._tr(
            "Open the interactive HTML report in your browser",
            "Ouvrir le rapport HTML interactif dans votre navigateur"
        ))
        self.open_html_btn.setVisible(False)
        self.open_html_btn.clicked.connect(self._open_html_report)
        btn_layout.addWidget(self.open_html_btn)

        self.open_pdf_btn = QPushButton(self._tr("📄 Open PDF Report", "📄 Ouvrir Rapport PDF"))
        self.open_pdf_btn.setToolTip(self._tr(
            "Open the PDF report",
            "Ouvrir le rapport PDF"
        ))
        self.open_pdf_btn.setVisible(False)
        self.open_pdf_btn.clicked.connect(self._open_pdf_report)
        btn_layout.addWidget(self.open_pdf_btn)

        self.save_history_btn = QPushButton(self._tr(
            "💾 Save to History", "💾 Sauver dans l'Historique"))
        self.save_history_btn.setToolTip(self._tr(
            "Manually save this analysis to the observation history database",
            "Sauvegarder manuellement cette analyse dans la base d'historique d'observations"
        ))
        self.save_history_btn.setVisible(False)
        self.save_history_btn.clicked.connect(self._manual_save_history)
        btn_layout.addWidget(self.save_history_btn)

        layout.addLayout(btn_layout)

        # ── Console / Results ──
        self.console_tabs = QTabWidget()
        # Console
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(get_mono_font(9))
        self.console.setToolTip(self._tr(
            "Real-time analysis output and progress messages",
            "Sortie d'analyse en temps réel et messages de progression"
        ))
        self.console_tabs.addTab(self.console, self._tr("📋 Console", "📋 Console"))

        # Results
        self.results_display = QTextEdit()
        self.results_display.setReadOnly(True)
        self.results_display.setToolTip(self._tr(
            "Analysis results summary",
            "Résumé des résultats d'analyse"
        ))
        self.console_tabs.addTab(self.results_display, self._tr("📊 Results", "📊 Résultats"))
        layout.addWidget(self.console_tabs)

    def _connect_signals(self):
        signals.language_changed.connect(self._on_language_changed)

    def _on_language_changed(self, lang):
        self.lang = lang

    # =========================================================================
    # Options persistence
    # =========================================================================

    def _restore_options(self):
        """Restore saved options from config"""
        self.cb_simbad.setChecked(self.config.get('analysis.enable_simbad', True))
        self.cb_plate_solve.setChecked(self.config.get('analysis.enable_plate_solving', False))
        self.cb_weather.setChecked(self.config.get('analysis.enable_weather_fetch', False))
        self.cb_graphs.setChecked(self.config.get('analysis.generate_graphs', True))
        self.cb_latex.setChecked(self.config.get('analysis.generate_latex', True))
        self.cb_thumbnails.setChecked(self.config.get('analysis.generate_thumbnails', False))
        self.cb_astrobin.setChecked(self.config.get('analysis.export_astrobin', False))
        self.cb_compress.setChecked(self.config.get('analysis.compress_fits', False))
        self.cb_extract_dups.setChecked(self.config.get('analysis.extract_duplicates', False))
        self.cb_auto_history.setChecked(self.config.get('analysis.auto_save_history', True))
        self.workers_spin.setValue(self.config.get('system.workers', 0))

        # Restore last folder
        last_folder = self.config.get('analysis.last_folder', '')
        if last_folder and os.path.isdir(last_folder):
            self.folder_input.setText(last_folder)
        elif not last_folder:
            # Try default folder detection
            default = self._get_default_folder()
            if default:
                self.folder_input.setText(default)

    def _save_options(self):
        """Save current options to config"""
        self.config.set('analysis.enable_simbad', self.cb_simbad.isChecked())
        self.config.set('analysis.enable_plate_solving', self.cb_plate_solve.isChecked())
        self.config.set('analysis.enable_weather_fetch', self.cb_weather.isChecked())
        self.config.set('analysis.generate_graphs', self.cb_graphs.isChecked())
        self.config.set('analysis.generate_latex', self.cb_latex.isChecked())
        self.config.set('analysis.generate_thumbnails', self.cb_thumbnails.isChecked())
        self.config.set('analysis.export_astrobin', self.cb_astrobin.isChecked())
        self.config.set('analysis.compress_fits', self.cb_compress.isChecked())
        self.config.set('analysis.extract_duplicates', self.cb_extract_dups.isChecked())
        self.config.set('analysis.auto_save_history', self.cb_auto_history.isChecked())
        self.config.set('analysis.last_folder', self.folder_input.text().strip())
        self.config.set('system.workers', self.workers_spin.value())
        self.config.save_config()

    def _get_default_folder(self):
        """Try to find a sensible default folder"""
        home = os.path.expanduser("~")
        candidates = [
            os.path.join(home, "Astrophotography"),
            os.path.join(home, "Astro"),
            os.path.join(home, "Pictures", "Astrophotography"),
            os.path.join(home, "Documents", "Astrophotography"),
        ]
        # Windows-specific paths
        if sys.platform == 'win32':
            for drive in ['D:', 'E:', 'F:', 'G:']:
                candidates.append(os.path.join(drive, os.sep, "Astrophotography"))
                candidates.append(os.path.join(drive, os.sep, "Astro"))
        for c in candidates:
            if os.path.isdir(c):
                return c
        return ''

    # =========================================================================
    # Telescope Aliases
    # =========================================================================

    def _show_telescope_aliases(self):
        """Show dialog for managing telescope name aliases"""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                      QTableWidget, QTableWidgetItem,
                                      QHeaderView, QPushButton, QLabel,
                                      QLineEdit, QMessageBox)
        try:
            from database.telescopes import get_telescope_aliases, add_telescope_alias, remove_telescope_alias
        except ImportError:
            QMessageBox.warning(self, self._tr("Error", "Erreur"), self._tr("telescopes module not available", "module telescopes non disponible"))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(self._tr("Telescope Name Aliases", "Alias de Noms de Télescopes"))
        dialog.setMinimumSize(600, 400)
        dlg_layout = QVBoxLayout(dialog)

        dlg_layout.addWidget(QLabel(self._tr(
            "Define aliases to merge identical telescopes with different names.\n"
            "Example: 'FSQ85' → 'Takahashi FSQ-85EDP'",
            "Définir des alias pour fusionner les télescopes identiques avec des noms différents.\n"
            "Exemple : 'FSQ85' → 'Takahashi FSQ-85EDP'"
        )))

        # Current aliases table
        alias_table = QTableWidget()
        alias_table.setColumnCount(3)
        alias_table.setHorizontalHeaderLabels([
            self._tr("Variant Name", "Nom Variante"),
            self._tr("Canonical Name", "Nom Canonique"),
            "",
        ])
        alias_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        alias_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        alias_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        alias_table.horizontalHeader().resizeSection(2, 80)
        alias_table.setAlternatingRowColors(True)
        dlg_layout.addWidget(alias_table)

        def refresh_table():
            aliases = get_telescope_aliases()
            alias_table.setRowCount(len(aliases))
            for i, (variant, canonical) in enumerate(sorted(aliases.items())):
                alias_table.setItem(i, 0, QTableWidgetItem(variant))
                alias_table.setItem(i, 1, QTableWidgetItem(canonical))
                del_btn = QPushButton("🗑️")
                del_btn.clicked.connect(lambda checked, v=variant: _delete_alias(v))
                alias_table.setCellWidget(i, 2, del_btn)

        def _delete_alias(variant):
            remove_telescope_alias(variant)
            refresh_table()

        refresh_table()

        # Add new alias row
        add_layout = QHBoxLayout()
        add_layout.addWidget(QLabel(self._tr("Variant:", "Variante :")))
        variant_input = QLineEdit()
        variant_input.setPlaceholderText(self._tr("e.g. FSQ85", "ex: FSQ85"))
        add_layout.addWidget(variant_input)
        add_layout.addWidget(QLabel(self._tr("→ Canonical:", "→ Canonique :")))
        canonical_input = QLineEdit()
        canonical_input.setPlaceholderText(self._tr("e.g. Takahashi FSQ-85EDP", "ex: Takahashi FSQ-85EDP"))
        add_layout.addWidget(canonical_input)

        add_btn = QPushButton(self._tr("➕ Add", "➕ Ajouter"))
        def _add_alias():
            v = variant_input.text().strip()
            c = canonical_input.text().strip()
            if v and c:
                add_telescope_alias(v, c)
                variant_input.clear()
                canonical_input.clear()
                refresh_table()
        add_btn.clicked.connect(_add_alias)
        add_layout.addWidget(add_btn)
        dlg_layout.addLayout(add_layout)

        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_btn = QPushButton(self._tr("Close", "Fermer"))
        close_btn.clicked.connect(dialog.accept)
        close_layout.addWidget(close_btn)
        dlg_layout.addLayout(close_layout)

        dialog.exec()

    # =========================================================================
    # Actions
    # =========================================================================

    def _browse_folder(self):
        start_dir = self.folder_input.text().strip()
        if not start_dir or not os.path.isdir(start_dir):
            start_dir = os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self, self._tr("Select Folder", "Sélectionner Dossier"), start_dir)
        if folder:
            self.folder_input.setText(folder)

    def _get_options(self):
        return {
            'resolve_simbad': self.cb_simbad.isChecked(),
            'generate_graphs': self.cb_graphs.isChecked(),
            'generate_latex': self.cb_latex.isChecked(),
            'generate_thumbnails': self.cb_thumbnails.isChecked(),
            'export_astrobin': self.cb_astrobin.isChecked(),
            'compress_fits': self.cb_compress.isChecked(),
            'extract_duplicates': self.cb_extract_dups.isChecked(),
            'workers': self.workers_spin.value(),
            'plate_solve': self.cb_plate_solve.isChecked(),
            'weather': self.cb_weather.isChecked(),
        }

    def _start_analysis(self):
        folder = self.folder_input.text().strip()
        if not folder or not os.path.isdir(folder):
            self.console.append(self._tr("❌ Please select a valid folder", "❌ Veuillez sélectionner un dossier valide"))
            return

        # Save options before starting
        self._save_options()

        # Check ASTAP availability if plate solving is enabled
        if self.cb_plate_solve.isChecked():
            try:
                from modules.plate_solving import find_astap_executable, get_astap_install_instructions
                if find_astap_executable() is None:
                    from PyQt6.QtWidgets import QMessageBox, QTextEdit, QVBoxLayout, QDialog, QPushButton, QDialogButtonBox
                    dlg = QDialog(self)
                    dlg.setWindowTitle(self._tr("ASTAP Not Found", "ASTAP Non Trouvé"))
                    dlg.setMinimumSize(600, 500)
                    dlg_layout = QVBoxLayout(dlg)
                    info_text = QTextEdit()
                    info_text.setReadOnly(True)
                    info_text.setPlainText(get_astap_install_instructions(self.lang))
                    dlg_layout.addWidget(info_text)
                    buttons = QDialogButtonBox()
                    continue_btn = buttons.addButton(
                        self._tr("Continue without plate solving", "Continuer sans plate solving"),
                        QDialogButtonBox.ButtonRole.AcceptRole)
                    cancel_btn = buttons.addButton(
                        self._tr("Cancel", "Annuler"),
                        QDialogButtonBox.ButtonRole.RejectRole)
                    buttons.accepted.connect(dlg.accept)
                    buttons.rejected.connect(dlg.reject)
                    dlg_layout.addWidget(buttons)
                    if dlg.exec() == QDialog.DialogCode.Rejected:
                        return
                    self.cb_plate_solve.setChecked(False)
            except Exception:
                pass

        self.console.clear()
        self.results_display.clear()
        self.start_btn.setVisible(False)
        self.stop_btn.setVisible(True)
        self.open_folder_btn.setVisible(False)
        self.open_html_btn.setVisible(False)
        self.open_pdf_btn.setVisible(False)

        signals.analysis_started.emit(folder)
        signals.busy_state_changed.emit(True)

        self.worker = UnifiedWorker()
        self.worker.output_signal.connect(self._on_output)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_finished)

        job = WorkerJob(
            job_type=JobType.ANALYSIS,
            params={'folder': folder, 'options': self._get_options()},
            priority=10
        )
        self.worker.set_single_job(job)
        self.worker.start()

    def _stop_analysis(self):
        if self.worker:
            self.worker.stop()
            self.console.append(self._tr("\n⏹ Stopping analysis...", "\n⏹ Arrêt de l'analyse..."))

    def is_running(self):
        """Check if analysis is currently running"""
        return self.worker is not None and self.worker.isRunning()

    # =========================================================================
    # Signal handlers
    # =========================================================================

    def _on_output(self, text):
        import re
        clean = re.sub(r'\x1b\[[0-9;]*m', '', text)
        if clean.strip():
            self._console_buffer.append(clean.rstrip())
            if not self._console_timer.isActive():
                self._console_timer.start()

    def _flush_console(self):
        """Flush buffered console output to QTextEdit (batched for performance)"""
        if not self._console_buffer:
            self._console_timer.stop()
            return
        # Batch all pending lines into a single append
        batch = '\n'.join(self._console_buffer)
        self._console_buffer.clear()
        self.console.append(batch)
        self.console.moveCursor(QTextCursor.MoveOperation.End)

    def _on_progress(self, current, total, phase):
        signals.analysis_progress.emit(current, total, phase)

    def _on_finished(self, success, message, result):
        # Flush any remaining console output
        self._flush_console()
        self.start_btn.setVisible(True)
        self.stop_btn.setVisible(False)
        signals.busy_state_changed.emit(False)

        if success and result:
            self.output_folder = result.get('output_folder', '')
            self.open_folder_btn.setVisible(bool(self.output_folder))

            # Detect generated report files
            self._html_report_path = ''
            self._pdf_report_path = ''
            if self.output_folder and os.path.isdir(self.output_folder):
                for fn in os.listdir(self.output_folder):
                    fn_lower = fn.lower()
                    if fn_lower.endswith('.html') and 'report' in fn_lower:
                        self._html_report_path = os.path.join(self.output_folder, fn)
                    elif fn_lower.endswith('.pdf') and 'report' in fn_lower:
                        self._pdf_report_path = os.path.join(self.output_folder, fn)
            self.open_html_btn.setVisible(bool(self._html_report_path))
            self.open_pdf_btn.setVisible(bool(self._pdf_report_path))

            self.console_tabs.setCurrentIndex(1)

            # Build enriched results HTML
            self.results_display.setHtml(self._build_results_html(result))

            # Tag result with auto-save preference
            result['_auto_save_history'] = self.cb_auto_history.isChecked()
            self._last_result = result
            self.save_history_btn.setVisible(not self.cb_auto_history.isChecked())

            signals.analysis_completed.emit(result)
        else:
            self.console.append(f"\n{'='*40}\n{message}")

    def _build_results_html(self, result):
        """Build enriched HTML results summary"""
        data = result.get('data_by_target', {})
        global_data = result.get('global_data', {})
        output = result.get('output_folder', '')

        # Compute summary stats
        total_files = sum(len(info.get('files', [])) for info in data.values())
        total_targets = len(data)

        # Collect unique instruments, telescopes, filters
        instruments = set()
        telescopes = set()
        all_filters = {}
        total_exposure_s = 0

        for target, info in data.items():
            for f in info.get('files', []):
                fi = f.get('info', {})
                fi_inner = fi.get('info', {})
                inst = fi_inner.get('instrument', '')
                tel = fi_inner.get('telescope', '')
                filt = fi.get('filter', 'Unknown')
                exp = fi.get('exposure_time', 0) or 0
                if inst:
                    instruments.add(inst)
                if tel:
                    telescopes.add(tel)
                total_exposure_s += exp
                if filt not in all_filters:
                    all_filters[filt] = {'count': 0, 'time': 0}
                all_filters[filt]['count'] += 1
                all_filters[filt]['time'] += exp

        total_hours = total_exposure_s / 3600.0

        # Build HTML
        html = f"""
        <h2>{self._tr('Analysis Results', 'Résultats d\'Analyse')}</h2>
        <table style="border-collapse: collapse; width: 100%;">
        <tr><td style="padding: 4px;"><b>{self._tr('Total files', 'Fichiers totaux')}:</b></td><td style="padding: 4px;">{total_files}</td></tr>
        <tr><td style="padding: 4px;"><b>{self._tr('Targets', 'Cibles')}:</b></td><td style="padding: 4px;">{total_targets}</td></tr>
        <tr><td style="padding: 4px;"><b>{self._tr('Total integration', 'Intégration totale')}:</b></td><td style="padding: 4px;">{total_hours:.1f}h ({total_exposure_s:.0f}s)</td></tr>
        <tr><td style="padding: 4px;"><b>{self._tr('Instruments', 'Instruments')}:</b></td><td style="padding: 4px;">{', '.join(sorted(instruments)) or 'N/A'}</td></tr>
        <tr><td style="padding: 4px;"><b>{self._tr('Telescopes', 'Télescopes')}:</b></td><td style="padding: 4px;">{', '.join(sorted(telescopes)) or 'N/A'}</td></tr>
        <tr><td style="padding: 4px;"><b>{self._tr('Output', 'Sortie')}:</b></td><td style="padding: 4px;">{output}</td></tr>
        </table>
        """

        # Filter breakdown
        if all_filters:
            html += f"<h3>{self._tr('Filter Distribution', 'Distribution des Filtres')}</h3>"
            html += '<table style="border-collapse: collapse; width: 100%;">'
            html += f'<tr style="background: #1a1e2e;"><th style="padding: 4px; text-align: left;">{self._tr("Filter", "Filtre")}</th>'
            html += f'<th style="padding: 4px; text-align: right;">{self._tr("Files", "Fichiers")}</th>'
            html += f'<th style="padding: 4px; text-align: right;">{self._tr("Time", "Temps")}</th></tr>'
            for filt in sorted(all_filters.keys()):
                info = all_filters[filt]
                time_h = info['time'] / 3600.0
                html += f'<tr><td style="padding: 4px;">{prettify_filter_name(filt)}</td>'
                html += f'<td style="padding: 4px; text-align: right;">{info["count"]}</td>'
                html += f'<td style="padding: 4px; text-align: right;">{time_h:.1f}h</td></tr>'
            html += '</table>'

        # Per-target details
        html += f"<h3>{self._tr('Per-Target Details', 'Détails par Cible')}</h3>"
        for target in sorted(data.keys()):
            info = data[target]
            files = info.get('files', [])
            target_exp = sum(f.get('info', {}).get('exposure_time', 0) or 0 for f in files)
            target_h = target_exp / 3600.0
            target_filters = set(f.get('info', {}).get('filter', '?') for f in files)
            pretty_filters = ', '.join(sorted(prettify_filter_name(f) for f in target_filters))
            html += f"<h4>🎯 {target}</h4>"
            html += f"<p>{len(files)} {self._tr('files', 'fichiers')} | "
            html += f"{target_h:.1f}h | "
            html += f"{self._tr('Filters', 'Filtres')}: {pretty_filters}</p>"

        return html

    def _open_output_folder(self):
        if self.output_folder:
            self._open_system(self.output_folder)

    def _open_html_report(self):
        if self._html_report_path and os.path.isfile(self._html_report_path):
            self._open_system(self._html_report_path)

    def _open_pdf_report(self):
        if self._pdf_report_path and os.path.isfile(self._pdf_report_path):
            self._open_system(self._pdf_report_path)

    def _manual_save_history(self):
        """Manually save last analysis results to observation history."""
        if not hasattr(self, '_last_result') or not self._last_result:
            return
        try:
            from modules.observation_history import get_history
            history = get_history()
            targets, obs = history.store_analysis_results(self._last_result)
            self.save_history_btn.setVisible(False)
            if targets > 0:
                signals.targets_refreshed.emit()
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self,
                    self._tr("History", "Historique"),
                    self._tr(
                        f"Saved {targets} targets and {obs} observations to history.",
                        f"{targets} cibles et {obs} observations sauvegardées dans l'historique."
                    ))
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self,
                    self._tr("History", "Historique"),
                    self._tr("No observation data found to save.",
                             "Aucune donnée d'observation à sauvegarder."))
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self,
                self._tr("Error", "Erreur"), str(e))

    @staticmethod
    def _open_system(path):
        """Open a file or folder with the system default application"""
        import subprocess
        try:
            if sys.platform == 'win32':
                os.startfile(path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
        except (OSError, FileNotFoundError):
            pass
