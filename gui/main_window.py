#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - MAIN WINDOW
================================================================================
Main application window with tabbed interface, menu bar, status bar,
console output, and progress tracking.
================================================================================
"""

import html
import sys
import os
import logging
import threading
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTextEdit, QProgressBar, QLabel,
    QMenuBar, QMenu, QStatusBar, QSplitter,
    QMessageBox, QDialog, QDialogButtonBox,
    QApplication, QPushButton, QFrame,
    QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox,
    QLineEdit, QCheckBox, QComboBox, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, QUrl, QProcess, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor, QAction, QIcon, QDesktopServices

from core.config import get_config
from core.signals import signals
from gui.theme import apply_cosmic_theme, create_cosmic_cursor, COLORS

logger = logging.getLogger(__name__)

from core import __version__


class AstroManagerWindow(QMainWindow):
    """Main application window"""

    _download_done_signal = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()
        self.config = get_config()
        self.lang = self.config.get('application.language', 'auto')
        if self.lang == 'auto':
            self.lang = self._detect_language()

        self.setWindowTitle(f"AstroManager v{__version__}")
        self.setMinimumSize(900, 600)
        self.resize(1400, 900)

        # Set window icon (also appears in title bar)
        if getattr(sys, 'frozen', False):
            _base = sys._MEIPASS
        else:
            _base = os.path.dirname(os.path.dirname(__file__))
        icon_path = os.path.join(_base, 'assets', 'icon.ico')
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._init_ui()
        self._init_menu()
        self._init_status_bar()
        self._connect_signals()

        # Apply custom cosmic cursor to window
        try:
            cursor = create_cosmic_cursor()
            self.setCursor(cursor)
        except Exception:
            pass

        # Install bug reporter
        self._init_bug_reporter()

        logger.info(f"AstroManager v{__version__} window initialized")

    def _tr(self, en, fr):
        return fr if self.lang == 'fr' else en

    def _detect_language(self):
        """Auto-detect system language"""
        from core.i18n import get_lang
        return get_lang()

    def _init_ui(self):
        """Initialize the main UI"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # Main splitter: tabs on top, console on bottom
        self.splitter = QSplitter(Qt.Orientation.Vertical)

        # ── Tab Widget ──
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # Create tabs
        self._create_tabs()

        self.splitter.addWidget(self.tab_widget)

        # ── Console / Output ──
        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(2)

        # Console header
        console_header = QHBoxLayout()
        console_label = QLabel(self._tr("Console Output", "Sortie Console"))
        console_label.setStyleSheet(f"color: {COLORS['accent_cyan']}; font-weight: bold; font-size: 10pt;")
        console_header.addWidget(console_label)
        console_header.addStretch()

        clear_btn = QPushButton(self._tr("Clear", "Effacer"))
        clear_btn.setToolTip(self._tr(
            "Clear console output",
            "Effacer la sortie console"
        ))
        clear_btn.setFixedWidth(80)
        clear_btn.clicked.connect(lambda: self.console.clear())
        console_header.addWidget(clear_btn)
        console_layout.addLayout(console_header)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        console_font = QFont("Consolas", 9)
        console_font.setStyleHint(QFont.StyleHint.Monospace)
        self.console.setFont(console_font)
        self.console.setMaximumHeight(200)
        console_layout.addWidget(self.console)

        self.splitter.addWidget(console_widget)

        # Set splitter proportions (tabs take most space)
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 1)

        main_layout.addWidget(self.splitter)

        # ── Progress Bar ──
        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setToolTip(self._tr(
            "Overall operation progress",
            "Progression globale de l'opération"
        ))
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v / %m  (%p%)")
        progress_layout.addWidget(self.progress_bar)

        self.phase_label = QLabel("")
        self.phase_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 9pt;")
        self.phase_label.setMinimumWidth(200)
        progress_layout.addWidget(self.phase_label)

        self.eta_label = QLabel("")
        self.eta_label.setStyleSheet(f"color: {COLORS['accent_yellow']}; font-size: 9pt;")
        self.eta_label.setFixedWidth(120)
        progress_layout.addWidget(self.eta_label)

        coffee_btn = QPushButton("☕")
        coffee_btn.setFixedSize(22, 22)
        coffee_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        coffee_btn.setToolTip("Buy me a coffee")
        coffee_btn.setStyleSheet("QPushButton { border: none; font-size: 9pt; color: #555; padding: 0; } QPushButton:hover { color: #c8a86e; }")
        coffee_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://buymeacoffee.com/orlytourbou")))
        progress_layout.addWidget(coffee_btn)

        main_layout.addLayout(progress_layout)

    def _create_tabs(self):
        """Create all application tabs"""
        from gui.tabs.analysis_tab import AnalysisTab
        from gui.tabs.compression_tab import CompressionTab
        from gui.tabs.header_editor_tab import HeaderEditorTab
        from gui.tabs.flat_manager_tab import FlatManagerTab
        from gui.tabs.target_tracking_tab import TargetTrackingTab
        from gui.tabs.disk_space_tab import DiskSpaceTab
        from gui.tabs.history_tab import HistoryTab
        from gui.tabs.database_tab import DatabaseTab
        from gui.tabs.asiair_import_tab import ASIAIRImportTab
        from gui.tabs.pixinsight_tab import PixInsightTab
        from gui.tabs.mount_tab import MountTab

        self.analysis_tab = AnalysisTab()
        self.compression_tab = CompressionTab()
        self.header_tab = HeaderEditorTab()
        self.flat_tab = FlatManagerTab()
        self.target_tab = TargetTrackingTab()
        self.history_tab = HistoryTab()
        self.database_tab = DatabaseTab()
        self.disk_tab = DiskSpaceTab()
        self.asiair_tab = ASIAIRImportTab()
        self.pixinsight_tab = PixInsightTab()
        self.mount_tab = MountTab()

        self.tab_widget.addTab(self.analysis_tab,
            self._tr("📊 Analysis", "📊 Analyse"))
        self.tab_widget.addTab(self.compression_tab,
            self._tr("🗜️ Compression", "🗜️ Compression"))
        self.tab_widget.addTab(self.asiair_tab,
            self._tr("🔭 ASIAIR Import", "🔭 Import ASIAIR"))
        self.tab_widget.addTab(self.header_tab,
            self._tr("✏️ Header Editor", "✏️ Éditeur Headers"))
        self.tab_widget.addTab(self.flat_tab,
            self._tr("📸 Flat Manager", "📸 Gestion Flats"))
        self.tab_widget.addTab(self.target_tab,
            self._tr("🎯 Target Tracking", "🎯 Suivi Cibles"))
        self.tab_widget.addTab(self.pixinsight_tab,
            self._tr("🔬 PixInsight", "🔬 PixInsight"))
        self.tab_widget.addTab(self.mount_tab,
            self._tr("🔭 Mount", "🔭 Monture"))
        self.tab_widget.addTab(self.history_tab,
            self._tr("📈 History", "📈 Historique"))
        self.tab_widget.addTab(self.database_tab,
            self._tr("📚 Database", "📚 Base de Données"))
        self.tab_widget.addTab(self.disk_tab,
            self._tr("💾 Disk Space", "💾 Espace Disque"))

    def _init_menu(self):
        """Initialize menu bar"""
        menubar = self.menuBar()

        # ── File Menu ──
        file_menu = menubar.addMenu(self._tr("&File", "&Fichier"))

        open_action = QAction(self._tr("📂 &Open Folder...", "📂 &Ouvrir Dossier..."), self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_folder)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        exit_action = QAction(self._tr("E&xit", "&Quitter"), self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # ── Tools Menu ──
        tools_menu = menubar.addMenu(self._tr("&Tools", "&Outils"))

        settings_action = QAction(self._tr("⚙ &Settings...", "⚙ &Réglages..."), self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._show_settings)
        tools_menu.addAction(settings_action)

        tools_menu.addSeparator()

        vacuum_action = QAction(self._tr("Optimize Database", "Optimiser Base de Données"), self)
        vacuum_action.triggered.connect(self._vacuum_database)
        tools_menu.addAction(vacuum_action)

        clear_cache_action = QAction(self._tr("Clear Old Cache", "Vider Cache Ancien"), self)
        clear_cache_action.triggered.connect(self._clear_cache)
        tools_menu.addAction(clear_cache_action)

        tools_menu.addSeparator()

        export_history_action = QAction(self._tr("📤 Export History...", "📤 Exporter Historique..."), self)
        export_history_action.triggered.connect(self._export_history)
        tools_menu.addAction(export_history_action)

        import_history_action = QAction(self._tr("📥 Import History...", "📥 Importer Historique..."), self)
        import_history_action.triggered.connect(self._import_history)
        tools_menu.addAction(import_history_action)

        tools_menu.addSeparator()

        reset_config_action = QAction(self._tr("Reset Configuration", "Réinitialiser Configuration"), self)
        reset_config_action.triggered.connect(self._reset_config)
        tools_menu.addAction(reset_config_action)

        # ── View Menu ──
        view_menu = menubar.addMenu(self._tr("&View", "&Affichage"))

        toggle_console_action = QAction(self._tr("Toggle Console", "Basculer Console"), self)
        toggle_console_action.setShortcut("Ctrl+`")
        toggle_console_action.triggered.connect(self._toggle_console)
        view_menu.addAction(toggle_console_action)

        # ── Language submenu ──
        lang_menu = view_menu.addMenu(self._tr("Language", "Langue"))

        en_action = QAction("English", self)
        en_action.triggered.connect(lambda: self._set_language('en'))
        lang_menu.addAction(en_action)

        fr_action = QAction("Français", self)
        fr_action.triggered.connect(lambda: self._set_language('fr'))
        lang_menu.addAction(fr_action)

        # ── Help Menu ──
        help_menu = menubar.addMenu(self._tr("&Help", "&Aide"))

        guide_action = QAction(self._tr("📖 User &Guide", "📖 &Guide Utilisateur"), self)
        guide_action.setShortcut("F1")
        guide_action.triggered.connect(self._show_user_guide)
        help_menu.addAction(guide_action)

        shortcuts_action = QAction(self._tr("⌨ &Keyboard Shortcuts", "⌨ &Raccourcis Clavier"), self)
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)

        help_menu.addSeparator()

        sysinfo_action = QAction(self._tr("System Info", "Info Système"), self)
        sysinfo_action.triggered.connect(self._show_system_info)
        help_menu.addAction(sysinfo_action)

        update_action = QAction(self._tr("🔄 Check for Updates...", "🔄 Vérifier les mises à jour..."), self)
        update_action.triggered.connect(self._check_for_updates)
        help_menu.addAction(update_action)

        bug_action = QAction(self._tr("Report &Bug", "Signaler &Bug"), self)
        bug_action.triggered.connect(self._show_bug_dialog)
        help_menu.addAction(bug_action)

        shortcut_action = QAction(self._tr("Create Desktop Shortcut", "Créer raccourci bureau"), self)
        shortcut_action.triggered.connect(self._create_desktop_shortcut)
        help_menu.addAction(shortcut_action)

        help_menu.addSeparator()

        about_action = QAction(self._tr("&About", "&À propos"), self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _init_status_bar(self):
        """Initialize status bar"""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage(self._tr(
            f"AstroManager v{__version__} - Ready",
            f"AstroManager v{__version__} - Prêt"
        ))

        # Add permanent widgets
        self.status_files = QLabel("")
        self.status_bar.addPermanentWidget(self.status_files)

        sys_info = self.config.get_system_info()
        workers = self.config.get_workers()
        self.status_system = QLabel(
            f"Workers: {workers} | {sys_info.get('ram_gb', '?')} GB RAM"
        )
        self.status_system.setStyleSheet(f"color: {COLORS['text_secondary']};")
        self.status_bar.addPermanentWidget(self.status_system)

    def _connect_signals(self):
        """Connect to global signal bus"""
        signals.log_message.connect(self._on_log_message)
        signals.status_message.connect(self._on_status_message)
        signals.error_occurred.connect(self._on_error)
        signals.warning_occurred.connect(self._on_warning)
        signals.busy_state_changed.connect(self._on_busy_changed)

        # Analysis signals
        signals.analysis_progress.connect(self._on_progress)
        signals.analysis_completed.connect(self._on_analysis_completed)

        # Download completion signal (thread-safe)
        self._download_done_signal.connect(self._on_download_done)

    def _init_bug_reporter(self):
        """Initialize anonymous bug reporter with crash dialog support"""
        try:
            from modules.bug_reporter import get_bug_reporter
            self.bug_reporter = get_bug_reporter(version=__version__)
            self.bug_reporter.set_crash_callback(self._on_crash_report)
            self.bug_reporter.install_global_handler()
            # Connect bug report signals
            signals.bug_report_crash.connect(self._show_crash_dialog)
            signals.bug_report_result.connect(self._on_report_result)
        except Exception as e:
            logger.warning(f"Bug reporter initialization failed: {e}")
            self.bug_reporter = None

    def _on_crash_report(self, report):
        """Crash callback — called from any thread. Emits thread-safe signal."""
        try:
            signals.bug_report_crash.emit(report)
        except Exception:
            pass

    def _show_crash_dialog(self, report):
        """Show crash report consent dialog (runs on main/GUI thread via signal)."""
        try:
            from gui.dialogs.bug_report_dialog import CrashReportDialog
            dialog = CrashReportDialog(
                report, self.bug_reporter, lang=self.lang, parent=self)
            dialog.exec()
            if dialog.was_sent():
                self._send_report_async(report)
            else:
                report_id = report.get('report_id', '?')
                self._log(self._tr(
                    f"Crash report saved locally: {report_id}",
                    f"Rapport de crash sauvegardé localement : {report_id}"
                ))
        except Exception as e:
            logger.error(f"Failed to show crash dialog: {e}")

    def _send_report_async(self, report):
        """Send a report in a background thread, emit result signal."""
        import threading as _threading

        def _worker():
            try:
                report_id, was_sent = self.bug_reporter.send_report(report)
                signals.bug_report_result.emit(was_sent, report_id or '?')
            except Exception as e:
                logger.error(f"Failed to send report: {e}")
                signals.bug_report_result.emit(False, report.get('report_id', '?'))

        t = _threading.Thread(target=_worker, daemon=True)
        t.start()

    def _on_report_result(self, was_sent, report_id):
        """Handle bug report send result — update status bar."""
        if was_sent:
            self.status_bar.showMessage(self._tr(
                f"Bug report sent: {report_id}",
                f"Rapport de bug envoyé : {report_id}"
            ), 8000)
        else:
            self.status_bar.showMessage(self._tr(
                f"Bug report saved locally: {report_id}",
                f"Rapport de bug sauvegardé localement : {report_id}"
            ), 8000)

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def _on_tab_changed(self, index):
        tab_names = ['analysis', 'compression', 'asiair_import',
                     'header_editor', 'flat_manager', 'target_tracking',
                     'history', 'database', 'disk_space']
        if 0 <= index < len(tab_names):
            signals.tab_changed.emit(index, tab_names[index])

    def _on_progress(self, current, total, phase):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.phase_label.setText(phase)

    def _on_log_message(self, level, message):
        self._log(message, level)

    def _on_status_message(self, message, timeout):
        self.status_bar.showMessage(message, timeout)

    def _on_error(self, title, message):
        QMessageBox.critical(self, title, message)

    def _on_warning(self, title, message):
        QMessageBox.warning(self, title, message)

    def _on_busy_changed(self, busy):
        # Only disable the tab bar (prevent switching), not the tab content
        # so that Stop buttons inside tabs remain clickable
        self.tab_widget.tabBar().setEnabled(not busy)

    def _on_analysis_completed(self, results):
        """Auto-store analysis results in observation database + refresh history."""
        self._log(self._tr(
            "Analysis completed successfully.", "Analyse terminée avec succès."))
        if not results or 'data_by_target' not in results:
            return
        # Only auto-save if the user checked "Save to observation history"
        if not results.get('_auto_save_history', False):
            return
        try:
            from modules.observation_history import get_history
            history = get_history()
            targets, obs = history.store_analysis_results(results)
            if targets > 0:
                self._log(self._tr(
                    f"Saved {targets} targets, {obs} observations to history database.",
                    f"{targets} cibles, {obs} observations sauvegardées dans l'historique."
                ))
                signals.targets_refreshed.emit()
        except Exception as e:
            logger.error(f"Auto-store to history failed: {e}")

    def _log(self, text, level='INFO'):
        """Write to console"""
        color_map = {
            'INFO': COLORS['success'],
            'WARNING': COLORS['warning'],
            'ERROR': COLORS['error'],
        }
        color = color_map.get(level, COLORS['text_primary'])
        timestamp = datetime.now().strftime("%H:%M:%S")
        text = html.escape(str(text))
        self.console.append(f'<span style="color:{COLORS["text_secondary"]}">[{timestamp}]</span> '
                           f'<span style="color:{color}">{text}</span>')
        self.console.moveCursor(QTextCursor.MoveOperation.End)

    # =========================================================================
    # Menu Actions
    # =========================================================================

    def _open_folder(self):
        """Open folder dialog and set it in the active tab"""
        from PyQt6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(
            self, self._tr("Select Folder", "Sélectionner Dossier"))
        if folder:
            # Set folder in the currently active tab if it has a folder_input
            current_tab = self.tab_widget.currentWidget()
            if hasattr(current_tab, 'folder_input'):
                current_tab.folder_input.setText(folder)

    def _vacuum_database(self):
        try:
            from core.database import get_db
            db = get_db()
            db.vacuum()
            QMessageBox.information(self,
                self._tr("Database", "Base de Données"),
                self._tr("Database optimized successfully.", "Base de données optimisée avec succès."))
        except Exception as e:
            QMessageBox.warning(self, self._tr("Error", "Erreur"), str(e))

    def _clear_cache(self):
        try:
            from core.database import get_db
            db = get_db()
            db.clear_old_cache(90)
            QMessageBox.information(self,
                self._tr("Cache", "Cache"),
                self._tr("Old cache entries cleared.", "Anciennes entrées du cache supprimées."))
        except Exception as e:
            QMessageBox.warning(self, self._tr("Error", "Erreur"), str(e))

    def _reset_config(self):
        reply = QMessageBox.question(self,
            self._tr("Reset Configuration", "Réinitialiser Configuration"),
            self._tr("Reset all settings to defaults? This cannot be undone.",
                     "Réinitialiser tous les paramètres par défaut? Ceci est irréversible."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.config = self.config._get_default_config()
            self.config.save_config()
            QMessageBox.information(self,
                self._tr("Reset", "Réinitialisation"),
                self._tr("Configuration reset. Restart for full effect.",
                         "Configuration réinitialisée. Redémarrez pour effet complet."))

    def _toggle_console(self):
        """Toggle console visibility"""
        sizes = self.splitter.sizes()
        if sizes[1] > 0:
            self._saved_console_size = sizes[1]
            self.splitter.setSizes([sizes[0] + sizes[1], 0])
        else:
            restore = getattr(self, '_saved_console_size', 200)
            self.splitter.setSizes([sizes[0] - restore, restore])

    def _set_language(self, lang):
        self.config.set('application.language', lang)
        self.config.save_config()
        QMessageBox.information(self,
            self._tr("Language", "Langue"),
            self._tr("Language changed. Restart to apply.",
                     "Langue modifiée. Redémarrez pour appliquer."))

    def _create_desktop_shortcut(self):
        """Create a desktop shortcut for AstroManager."""
        try:
            from shortcut_helper import create_shortcut_force
            create_shortcut_force("AstroManager", "astromanager.py", "assets/icon.ico")
        except Exception as e:
            QMessageBox.warning(self,
                self._tr("Error", "Erreur"),
                self._tr(f"Could not create shortcut: {e}",
                         f"Impossible de créer le raccourci : {e}"))

    def _show_about(self):
        QMessageBox.about(self,
            self._tr("About AstroManager", "À propos d'AstroManager"),
            f"""<h2>AstroManager v{__version__}</h2>
            <p>{self._tr(
                "Professional Astrophotography File Management Suite",
                "Suite Professionnelle de Gestion de Fichiers Astrophotographiques"
            )}</p>
            <p><b>{self._tr("Features:", "Fonctionnalités:")}</b></p>
            <ul>
                <li>{self._tr("Universal FITS/XISF Analysis", "Analyse Universelle FITS/XISF")}</li>
                <li>{self._tr("Multi-Codec Compression", "Compression Multi-Codec")}</li>
                <li>{self._tr("Mass Header Editing", "Édition de Headers en Masse")}</li>
                <li>{self._tr("Flat Frame Management", "Gestion des Flats")}</li>
                <li>{self._tr("Target Tracking", "Suivi de Cibles")}</li>
                <li>{self._tr("Observation History & Statistics", "Historique d'Observations & Statistiques")}</li>
                <li>{self._tr("Database Browser (40,000+ references)", "Explorateur de Bases de Données (40 000+ références)")}</li>
                <li>{self._tr("Storage Optimization", "Optimisation du Stockage")}</li>
            </ul>
            <p>{self._tr("License: MIT", "Licence: MIT")}</p>
            <p>{self._tr("Made with love for the astrophotography community.",
                         "Fait avec amour pour la communauté d'astrophotographie.")}</p>
            <p style="font-size: 8pt; color: #666;"><a href="https://buymeacoffee.com/orlytourbou" style="color: #777; text-decoration: none;">☕</a></p>"""
        )

    def _show_bug_dialog(self):
        """Open in-app manual bug report dialog."""
        if not self.bug_reporter:
            QMessageBox.warning(self,
                self._tr("Bug Report", "Rapport de Bug"),
                self._tr("Bug reporter is not initialized.",
                         "Le rapporteur de bugs n'est pas initialisé."))
            return

        from gui.dialogs.bug_report_dialog import ManualBugReportDialog
        dialog = ManualBugReportDialog(
            self.bug_reporter, lang=self.lang, parent=self)
        dialog.exec()
        if dialog.was_submitted():
            report = dialog.get_report()
            self._send_report_async(report)

    def _show_system_info(self):
        """Show system information dialog"""
        info = self.config.get_system_info()
        workers = self.config.get_workers()
        batch = self.config.get_batch_size()

        os_display = info.get('os', '?')
        os_ver = info.get('os_version', '')
        # Don't repeat version if OS already contains "Windows 11" etc.
        if os_ver and os_ver not in os_display:
            os_display = f"{os_display} (build {os_ver.split('.')[-1]})" if 'Windows' in os_display else f"{os_display} {os_ver}"

        cpu_name = info.get('cpu_name', '?')
        cpu_cores = f"{info.get('cpu_count_physical', '?')}P / {info.get('cpu_count_logical', '?')}L"

        _esc = html.escape
        text = f"""<h3>{self._tr("System Information", "Informations Système")}</h3>
        <table>
        <tr><td><b>OS:</b></td><td>{_esc(str(os_display))}</td></tr>
        <tr><td><b>CPU:</b></td><td>{_esc(str(cpu_name))}</td></tr>
        <tr><td><b>{self._tr("Cores:", "Coeurs :")}</b></td><td>{_esc(str(cpu_cores))}</td></tr>
        <tr><td><b>RAM:</b></td><td>{_esc(str(info.get('ram_gb', '?')))} GB</td></tr>
        <tr><td><b>Storage:</b></td><td>{_esc(str(info.get('storage_type', '?')).upper())}</td></tr>
        <tr><td><b>Python:</b></td><td>{_esc(str(info.get('python_version', '?')))}</td></tr>
        <tr><td><b>Workers:</b></td><td>{_esc(str(workers))}</td></tr>
        <tr><td><b>Batch Size:</b></td><td>{_esc(str(batch))}</td></tr>
        </table>"""

        QMessageBox.information(self,
            self._tr("System Info", "Info Système"), text)

    # =========================================================================
    # Update System
    # =========================================================================

    def _check_for_updates(self, silent=False):
        """Check for updates via GitHub Releases API.

        Args:
            silent: If True, only show a status bar message on update found
                    and suppress all dialogs on no-update / error.
        """
        from core.updater import UpdateChecker, UpdateWorker
        self._update_silent = silent

        checker = UpdateChecker(__version__, self.config)

        # Manual check: ignore interval throttle and skipped version
        if not silent:
            checker.clear_skipped_version()

        self._update_worker = UpdateWorker(
            checker, respect_interval=silent, parent=self)
        self._update_worker.update_found.connect(self._on_update_found)
        self._update_worker.no_update.connect(self._on_no_update)
        self._update_worker.check_failed.connect(self._on_update_error)
        self._update_worker.start()

    def _on_update_found(self, result):
        """Handle update available (called on main thread via signal)."""
        if self._update_silent:
            v = result['latest_version']
            msg = self._tr(
                f"Update available: v{v} — Help > Check for Updates",
                f"Mise à jour disponible : v{v} — Aide > Vérifier les mises à jour"
            )
            self.status_bar.showMessage(msg, 15000)
        else:
            self._show_update_dialog(result)

    def _on_no_update(self):
        """Handle no-update result."""
        if not self._update_silent:
            QMessageBox.information(self,
                self._tr("Updates", "Mises à jour"),
                self._tr(
                    f"You are up to date (v{__version__}).",
                    f"Vous êtes à jour (v{__version__})."
                ))

    def _on_update_error(self, message):
        """Handle update check error."""
        if not self._update_silent:
            QMessageBox.warning(self,
                self._tr("Update Check Failed", "Vérification échouée"),
                self._tr(
                    f"Could not check for updates:\n{message}",
                    f"Impossible de vérifier les mises à jour :\n{message}"
                ))

    def _show_update_dialog(self, release_info):
        """Show update available dialog with changelog."""
        from gui.dialogs.update_dialog import UpdateDialog

        dialog = UpdateDialog(release_info, __version__,
                              lang=self.lang, parent=self)
        dialog.exec()

        if dialog.action == 'install':
            self._do_update(release_info)
        elif dialog.action == 'skip':
            from core.updater import UpdateChecker
            checker = UpdateChecker(__version__, self.config)
            checker.skip_version(release_info['latest_version'])

    def _do_update(self, release_info):
        """Download and apply update (source installs only, not frozen .exe)"""
        # Frozen .exe cannot self-update — redirect to GitHub
        release_url = release_info.get('release_url') or release_info.get('url', '')
        if getattr(sys, 'frozen', False):
            QDesktopServices.openUrl(QUrl(release_url))
            return

        reply = QMessageBox.question(self,
            self._tr("Update", "Mise à jour"),
            self._tr(
                "The application will restart after the update.\nContinue?",
                "L'application va redémarrer après la mise à jour.\nContinuer?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.status_bar.showMessage(self._tr(
            "Downloading update...", "Téléchargement de la mise à jour..."))

        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        def _worker():
            try:
                url = release_info['download_url']
                if not url.startswith('https://github.com/') and not url.startswith('https://api.github.com/'):
                    self._download_done_signal.emit(False, "Invalid download URL")
                    return
                from modules.updater import download_and_apply_update
                download_and_apply_update(url, app_dir)
                self._download_done_signal.emit(True, "")
            except Exception as e:
                self._download_done_signal.emit(False, str(e))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _on_download_done(self, success, message):
        """Handle download completion"""
        if success:
            QMessageBox.information(self,
                self._tr("Update Installed", "Mise à jour installée"),
                self._tr(
                    "Update installed successfully. The application will now restart.",
                    "Mise à jour installée avec succès. L'application va redémarrer."
                ))
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            QProcess.startDetached(sys.executable, [os.path.join(app_dir, 'astromanager.py')])
            QApplication.quit()
        else:
            self.status_bar.showMessage("")
            QMessageBox.critical(self,
                self._tr("Update Failed", "Mise à jour échouée"),
                self._tr(
                    f"Update failed:\n{message}",
                    f"La mise à jour a échoué :\n{message}"
                ))

    def _show_settings(self):
        """Show settings dialog with all configurable options"""
        dialog = QDialog(self)
        dialog.setWindowTitle(self._tr("Settings", "Réglages"))
        dialog.setMinimumSize(550, 500)
        main_layout = QVBoxLayout(dialog)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)

        # ── General ──
        gen_group = QGroupBox(self._tr("General", "Général"))
        gen_form = QFormLayout(gen_group)

        lang_combo = QComboBox()
        lang_combo.addItem(self._tr("Auto-detect", "Auto-détection"), "auto")
        lang_combo.addItem("English", "en")
        lang_combo.addItem("Français", "fr")
        current_lang = self.config.get('application.language', 'auto')
        for i in range(lang_combo.count()):
            if lang_combo.itemData(i) == current_lang:
                lang_combo.setCurrentIndex(i)
        lang_combo.setToolTip(self._tr("Application display language", "Langue d'affichage de l'application"))
        gen_form.addRow(self._tr("Language:", "Langue:"), lang_combo)

        cb_updates = QCheckBox()
        cb_updates.setChecked(self.config.get('application.check_updates_on_startup', True))
        cb_updates.setToolTip(self._tr(
            "Automatically check for updates on startup (single HTTPS call to GitHub, max once per day)",
            "Vérifier automatiquement les mises à jour au démarrage (un seul appel HTTPS vers GitHub, max une fois par jour)"))
        gen_form.addRow(self._tr("Check updates on startup:", "Vérifier mises à jour au démarrage:"), cb_updates)

        layout.addWidget(gen_group)

        # ── Observatory ──
        obs_group = QGroupBox(self._tr("Observatory", "Observatoire"))
        obs_form = QFormLayout(obs_group)

        lat_spin = QDoubleSpinBox()
        lat_spin.setRange(-90, 90)
        lat_spin.setDecimals(4)
        lat_spin.setValue(self.config.get('observatory.latitude', 51.4769))
        lat_spin.setToolTip(self._tr("Observatory latitude in decimal degrees", "Latitude de l'observatoire en degrés décimaux"))
        obs_form.addRow(self._tr("Latitude:", "Latitude:"), lat_spin)

        lon_spin = QDoubleSpinBox()
        lon_spin.setRange(-180, 180)
        lon_spin.setDecimals(4)
        lon_spin.setValue(self.config.get('observatory.longitude', -0.0005))
        lon_spin.setToolTip(self._tr("Observatory longitude in decimal degrees", "Longitude de l'observatoire en degrés décimaux"))
        obs_form.addRow(self._tr("Longitude:", "Longitude:"), lon_spin)

        elev_spin = QSpinBox()
        elev_spin.setRange(0, 9000)
        elev_spin.setValue(int(self.config.get('observatory.elevation_m', 0)))
        elev_spin.setSuffix(" m")
        elev_spin.setToolTip(self._tr("Observatory elevation above sea level", "Altitude de l'observatoire au-dessus du niveau de la mer"))
        obs_form.addRow(self._tr("Elevation:", "Altitude:"), elev_spin)

        tz_input = QLineEdit(str(self.config.get('observatory.timezone', 'UTC')))
        tz_input.setToolTip(self._tr("Timezone (e.g. Europe/Paris, America/New_York, UTC)", "Fuseau horaire (ex: Europe/Paris, America/New_York, UTC)"))
        obs_form.addRow(self._tr("Timezone:", "Fuseau:"), tz_input)

        detect_btn = QPushButton(self._tr(
            "📍 Auto-detect from FITS headers",
            "📍 Auto-détecter depuis les headers FITS"))
        detect_btn.setToolTip(self._tr(
            "Scan a folder of FITS files to find observatory coordinates (SITELAT/SITELONG)",
            "Scanner un dossier de fichiers FITS pour trouver les coordonnées de l'observatoire (SITELAT/SITELONG)"))

        def _auto_detect_position():
            from PyQt6.QtWidgets import QFileDialog
            folder = QFileDialog.getExistingDirectory(
                dialog,
                self._tr("Select folder with FITS files", "Sélectionner dossier avec fichiers FITS"))
            if not folder:
                return

            # Scan FITS files for location headers
            # Smart: one file per target (OBJECT), no point scanning 200 files
            # from the same target — the telescope didn't move
            locations = {}
            import glob as g
            fits_files = []
            for ext in ('*.fits', '*.fit', '*.fts', '*.fz', '*.FITS', '*.FIT'):
                fits_files.extend(g.glob(os.path.join(folder, '**', ext), recursive=True))

            if not fits_files:
                QMessageBox.information(dialog,
                    self._tr("Auto-detect", "Auto-détection"),
                    self._tr("No FITS files found in this folder.",
                             "Aucun fichier FITS trouvé dans ce dossier."))
                return

            scanned = 0
            seen_targets = set()  # skip files from already-scanned targets

            for fp in fits_files:
                try:
                    from astropy.io import fits as pyfits
                    with pyfits.open(fp, memmap=True) as hdul:
                        hdr = hdul[0].header

                        # Skip if we already scanned a file for this target
                        obj = str(hdr.get('OBJECT', '')).strip().upper()
                        if obj and obj in seen_targets:
                            continue
                        if obj:
                            seen_targets.add(obj)

                        lat = lon = elev = None
                        for lat_key in ('SITELAT', 'OBSLAT', 'LAT-OBS', 'OBSGEO-B'):
                            if lat_key in hdr and hdr[lat_key] is not None:
                                try:
                                    lat = float(hdr[lat_key])
                                    break
                                except (ValueError, TypeError):
                                    pass
                        for lon_key in ('SITELONG', 'OBSLONG', 'LONG-OBS', 'OBSGEO-L'):
                            if lon_key in hdr and hdr[lon_key] is not None:
                                try:
                                    lon = float(hdr[lon_key])
                                    break
                                except (ValueError, TypeError):
                                    pass
                        for elev_key in ('SITEELEV', 'OBSELEV', 'ALT-OBS', 'OBSGEO-H'):
                            if elev_key in hdr and hdr[elev_key] is not None:
                                try:
                                    elev = float(hdr[elev_key])
                                    break
                                except (ValueError, TypeError):
                                    pass
                        if lat is not None and lon is not None:
                            key = (round(lat, 4), round(lon, 4))
                            if key not in locations:
                                locations[key] = {'lat': key[0], 'lon': key[1],
                                                  'elev': round(elev, 0) if elev else None,
                                                  'targets': []}
                            if obj:
                                locations[key]['targets'].append(obj)
                        scanned += 1
                except Exception:
                    continue

            if not locations:
                QMessageBox.information(dialog,
                    self._tr("Auto-detect", "Auto-détection"),
                    self._tr(f"No location data found in {scanned} scanned files "
                             f"({len(seen_targets)} targets).\n"
                             "Your FITS files may not contain SITELAT/SITELONG headers.",
                             f"Aucune donnée de position trouvée dans {scanned} fichiers scannés "
                             f"({len(seen_targets)} cibles).\n"
                             "Vos fichiers FITS ne contiennent peut-être pas les headers SITELAT/SITELONG."))
                return

            # Sort by number of targets using this position (most used first)
            sorted_locs = sorted(locations.values(), key=lambda x: -len(x['targets']))

            if len(sorted_locs) == 1:
                loc = sorted_locs[0]
                lat_spin.setValue(loc['lat'])
                lon_spin.setValue(loc['lon'])
                if loc['elev'] is not None:
                    elev_spin.setValue(int(loc['elev']))
                n_tgt = len(loc['targets'])
                QMessageBox.information(dialog,
                    self._tr("Auto-detect", "Auto-détection"),
                    self._tr(f"Position found: {loc['lat']:.4f}, {loc['lon']:.4f}"
                             f" ({n_tgt} target{'s' if n_tgt > 1 else ''} scanned)",
                             f"Position trouvée : {loc['lat']:.4f}, {loc['lon']:.4f}"
                             f" ({n_tgt} cible{'s' if n_tgt > 1 else ''} scannée{'s' if n_tgt > 1 else ''})"))
            else:
                choice_dialog = QDialog(dialog)
                choice_dialog.setWindowTitle(self._tr(
                    "Choose Observatory Position",
                    "Choisir la Position de l'Observatoire"))
                choice_dialog.setMinimumWidth(450)
                cl = QVBoxLayout(choice_dialog)
                cl.addWidget(QLabel(self._tr(
                    f"Found {len(sorted_locs)} different positions ({len(seen_targets)} targets scanned):",
                    f"{len(sorted_locs)} positions différentes ({len(seen_targets)} cibles scannées) :")))

                from PyQt6.QtWidgets import QRadioButton, QButtonGroup
                btn_group = QButtonGroup(choice_dialog)
                for i, loc in enumerate(sorted_locs):
                    elev_str = f", {int(loc['elev'])}m" if loc['elev'] else ""
                    n_tgt = len(loc['targets'])
                    label = (f"{loc['lat']:.4f}, {loc['lon']:.4f}{elev_str}"
                             f"  ({n_tgt} target{'s' if n_tgt > 1 else ''})")
                    radio = QRadioButton(label)
                    if i == 0:
                        radio.setChecked(True)
                    btn_group.addButton(radio, i)
                    cl.addWidget(radio)

                btns = QDialogButtonBox(
                    QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
                btns.accepted.connect(choice_dialog.accept)
                btns.rejected.connect(choice_dialog.reject)
                cl.addWidget(btns)

                if choice_dialog.exec() == QDialog.DialogCode.Accepted:
                    idx = btn_group.checkedId()
                    if 0 <= idx < len(sorted_locs):
                        loc = sorted_locs[idx]
                        lat_spin.setValue(loc['lat'])
                        lon_spin.setValue(loc['lon'])
                        if loc['elev'] is not None:
                            elev_spin.setValue(int(loc['elev']))

        detect_btn.clicked.connect(_auto_detect_position)
        obs_form.addRow("", detect_btn)

        layout.addWidget(obs_group)

        # ── Performance ──
        perf_group = QGroupBox(self._tr("Performance", "Performance"))
        perf_form = QFormLayout(perf_group)

        workers_spin = QSpinBox()
        workers_spin.setRange(0, 64)
        workers_spin.setValue(self.config.get('system.workers', 0))
        workers_spin.setToolTip(self._tr("Number of parallel workers (0 = auto-detect based on CPU/RAM)", "Nombre de workers parallèles (0 = auto-détection selon CPU/RAM)"))
        perf_form.addRow(self._tr("Workers (0=auto):", "Workers (0=auto):"), workers_spin)

        batch_spin = QSpinBox()
        batch_spin.setRange(50, 10000)
        batch_spin.setSingleStep(100)
        batch_spin.setValue(self.config.get('system.batch_size', 1000))
        batch_spin.setToolTip(self._tr("Number of files to process per batch (higher = faster but more RAM)", "Nombre de fichiers par lot (plus élevé = plus rapide mais plus de RAM)"))
        perf_form.addRow(self._tr("Batch size:", "Taille lot:"), batch_spin)

        layout.addWidget(perf_group)

        # ── Compression ──
        comp_group = QGroupBox(self._tr("Compression Defaults (XISF)", "Compression par Défaut (XISF)"))
        comp_form = QFormLayout(comp_group)

        profile_combo = QComboBox()
        profiles = ['zlib_1', 'zlib_6', 'zlib_9', 'zstd_3', 'zstd_6', 'zstd_10', 'zstd_19', 'lz4', 'lz4_hc']
        current_profile = self.config.get('compression.default_profile', 'zlib_6')
        for p in profiles:
            profile_combo.addItem(p, p)
            if p == current_profile:
                profile_combo.setCurrentIndex(profile_combo.count() - 1)
        profile_combo.setToolTip(self._tr("Default compression profile for new compressions", "Profil de compression par défaut pour les nouvelles compressions"))
        comp_form.addRow(self._tr("Default profile:", "Profil par défaut:"), profile_combo)

        cb_delete = QCheckBox()
        cb_delete.setChecked(self.config.get('compression.delete_source', False))
        cb_delete.setToolTip(self._tr("Delete source files after successful compression", "Supprimer les fichiers source après compression réussie"))
        comp_form.addRow(self._tr("Delete source:", "Supprimer source:"), cb_delete)

        cb_verify = QCheckBox()
        cb_verify.setChecked(self.config.get('compression.verify_integrity', True))
        cb_verify.setToolTip(self._tr("Verify integrity with SHA-256 after compression", "Vérifier l'intégrité SHA-256 après compression"))
        comp_form.addRow(self._tr("Verify integrity:", "Vérifier intégrité:"), cb_verify)

        layout.addWidget(comp_group)

        # ── Analysis ──
        analysis_group = QGroupBox(self._tr("Analysis Defaults", "Analyse par Défaut"))
        analysis_form = QFormLayout(analysis_group)

        cb_simbad = QCheckBox()
        cb_simbad.setChecked(self.config.get('analysis.enable_simbad', True))
        cb_simbad.setToolTip(self._tr("Enable SIMBAD queries by default", "Activer les requêtes SIMBAD par défaut"))
        analysis_form.addRow(self._tr("SIMBAD:", "SIMBAD:"), cb_simbad)

        cb_platesolve = QCheckBox()
        cb_platesolve.setChecked(self.config.get('analysis.enable_plate_solving', False))
        cb_platesolve.setToolTip(self._tr("Enable plate solving by default", "Activer le plate solving par défaut"))
        analysis_form.addRow(self._tr("Plate solving:", "Plate solving :"), cb_platesolve)

        cb_weather = QCheckBox()
        cb_weather.setChecked(self.config.get('analysis.enable_weather_fetch', False))
        cb_weather.setToolTip(self._tr("Enable weather data fetch by default", "Activer la récupération météo par défaut"))
        analysis_form.addRow(self._tr("Weather:", "Météo:"), cb_weather)

        cb_duplicates = QCheckBox()
        cb_duplicates.setChecked(self.config.get('analysis.duplicate_detection', True))
        cb_duplicates.setToolTip(self._tr("Detect duplicate files during analysis", "Détecter les fichiers en double lors de l'analyse"))
        analysis_form.addRow(self._tr("Duplicate detection:", "Détection doublons:"), cb_duplicates)

        cb_graphs = QCheckBox()
        cb_graphs.setChecked(self.config.get('analysis.generate_graphs', True))
        cb_graphs.setToolTip(self._tr("Generate graphs and charts in analysis reports", "Générer des graphiques dans les rapports d'analyse"))
        analysis_form.addRow(self._tr("Generate graphs:", "Générer graphiques:"), cb_graphs)

        cb_latex = QCheckBox()
        cb_latex.setChecked(self.config.get('analysis.generate_latex', True))
        cb_latex.setToolTip(self._tr("Generate LaTeX/PDF report (requires LaTeX installed)", "Générer un rapport LaTeX/PDF (nécessite LaTeX installé)"))
        analysis_form.addRow(self._tr("LaTeX/PDF report:", "Rapport LaTeX/PDF:"), cb_latex)

        cb_csv = QCheckBox()
        cb_csv.setChecked(self.config.get('analysis.generate_csv', True))
        cb_csv.setToolTip(self._tr("Generate CSV export of analysis results", "Générer un export CSV des résultats d'analyse"))
        analysis_form.addRow(self._tr("CSV export:", "Export CSV:"), cb_csv)

        layout.addWidget(analysis_group)

        # ── File Naming Pattern ──
        naming_group = QGroupBox(self._tr("File Naming Pattern (NINA)", "Pattern Nom de Fichier (NINA)"))
        naming_form = QVBoxLayout(naming_group)

        naming_pattern_input = QLineEdit()
        default_pattern = "$IMAGETYPE$_$TARGETNAME$_$DATETIME$_$FILTER$_$BINNING$_$EXPOSURETIME$s_$ROTATORANGLE$deg_$SENSORTEMP$_$TELESCOPE$_$CAMERA$_$FRAMENR$"
        naming_pattern_input.setText(self.config.get('file_naming.pattern', default_pattern))
        naming_pattern_input.setToolTip(self._tr(
            "NINA-compatible filename pattern using tokens from FITS headers",
            "Pattern de nom de fichier compatible NINA utilisant les tokens des headers FITS"
        ))
        naming_form.addWidget(naming_pattern_input)

        tokens_label = QLabel(
            self._tr(
                "Tokens: $IMAGETYPE$ $TARGETNAME$ $DATETIME$ $FILTER$ $BINNING$ $EXPOSURETIME$ "
                "$ROTATORANGLE$ $SENSORTEMP$ $TELESCOPE$ $CAMERA$ $FRAMENR$ $GAIN$ $OFFSET$",
                "Tokens: $IMAGETYPE$ $TARGETNAME$ $DATETIME$ $FILTER$ $BINNING$ $EXPOSURETIME$ "
                "$ROTATORANGLE$ $SENSORTEMP$ $TELESCOPE$ $CAMERA$ $FRAMENR$ $GAIN$ $OFFSET$"
            ))
        tokens_label.setStyleSheet("color: #8b95b0; font-size: 9pt;")
        tokens_label.setWordWrap(True)
        naming_form.addWidget(tokens_label)

        layout.addWidget(naming_group)

        # ── Bug Reporting ──
        bug_group = QGroupBox(self._tr("Bug Reporting", "Rapports de Bugs"))
        bug_form = QFormLayout(bug_group)

        cb_bugs = QCheckBox()
        cb_bugs.setChecked(self.config.get('bug_reporting.enabled', False))
        cb_bugs.setToolTip(self._tr("Send anonymous crash reports to help improve AstroManager", "Envoyer des rapports de crash anonymes pour améliorer AstroManager"))
        bug_form.addRow(self._tr("Enable:", "Activer:"), cb_bugs)

        layout.addWidget(bug_group)

        layout.addStretch()
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)

        # ── Buttons ──
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        main_layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Save all settings
            self.config.set('application.language', lang_combo.currentData())
            self.config.set('application.check_updates_on_startup', cb_updates.isChecked())
            self.config.set('observatory.latitude', lat_spin.value())
            self.config.set('observatory.longitude', lon_spin.value())
            self.config.set('observatory.elevation_m', elev_spin.value())
            self.config.set('observatory.timezone', tz_input.text().strip())
            self.config.set('system.workers', workers_spin.value())
            self.config.set('system.batch_size', batch_spin.value())
            self.config.set('compression.default_profile', profile_combo.currentData())
            self.config.set('compression.delete_source', cb_delete.isChecked())
            self.config.set('compression.verify_integrity', cb_verify.isChecked())
            self.config.set('analysis.enable_simbad', cb_simbad.isChecked())
            self.config.set('analysis.enable_plate_solving', cb_platesolve.isChecked())
            self.config.set('analysis.enable_weather_fetch', cb_weather.isChecked())
            self.config.set('analysis.duplicate_detection', cb_duplicates.isChecked())
            self.config.set('analysis.generate_graphs', cb_graphs.isChecked())
            self.config.set('analysis.generate_latex', cb_latex.isChecked())
            self.config.set('analysis.generate_csv', cb_csv.isChecked())
            self.config.set('bug_reporting.enabled', cb_bugs.isChecked())
            self.config.set('file_naming.pattern', naming_pattern_input.text().strip())
            self.config.save_config()

            QMessageBox.information(self,
                self._tr("Settings", "Réglages"),
                self._tr("Settings saved. Some changes require a restart.",
                         "Réglages sauvegardés. Certains changements nécessitent un redémarrage."))

    def _export_history(self):
        """Export observation history via the history tab"""
        if hasattr(self, 'history_tab'):
            self.history_tab._export_json()

    def _import_history(self):
        """Import observation history via the history tab"""
        if hasattr(self, 'history_tab'):
            self.history_tab._import_json()

    def _show_user_guide(self):
        """Show comprehensive user guide dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle(self._tr("User Guide", "Guide Utilisateur"))
        dialog.setMinimumSize(650, 550)
        layout = QVBoxLayout(dialog)

        text = QTextEdit()
        text.setReadOnly(True)
        font = QFont("Segoe UI", 10)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        text.setFont(font)

        if self.lang == 'fr':
            text.setHtml("""
            <h2>Guide Utilisateur AstroManager</h2>
            <h3>1. Analyse (onglet principal)</h3>
            <ul>
                <li><b>Sélection dossier :</b> Choisissez le dossier contenant vos fichiers FITS/XISF</li>
                <li><b>SIMBAD :</b> Résout les noms d'objets (M31 = NGC 224) et fusionne automatiquement</li>
                <li><b>Plate solving :</b> Détecte les réducteurs focaux via ASTAP</li>
                <li><b>Météo :</b> Récupère les conditions météo historiques pour chaque nuit</li>
                <li><b>Workers :</b> 0 = auto-détection optimale selon votre CPU/RAM/disque</li>
                <li><b>Sorties :</b> Graphiques, rapport PDF/LaTeX, miniatures, CSV AstroBin</li>
            </ul>
            <h3>2. Compression</h3>
            <ul>
                <li><b>Profils :</b> zlib (universel), zstd (haute compression), lz4 (ultra-rapide)</li>
                <li><b>Formats :</b> FITS → XISF, FITS → FITS.FZ (RICE), et inversement</li>
                <li><b>Intégrité :</b> Vérification SHA-256 optionnelle après compression</li>
            </ul>
            <h3>3. Éditeur Headers</h3>
            <ul>
                <li><b>Édition en masse :</b> Modifiez les headers FITS/XISF de centaines de fichiers</li>
                <li><b>Catégories :</b> Acquisition, Caméra, Filtre, Image, Télescope, etc.</li>
                <li><b>Pattern NINA :</b> Générateur de pattern de nom de fichier compatible NINA</li>
                <li><b>Renommage auto :</b> Après modification des headers, proposition automatique de renommer les fichiers selon le pattern NINA configuré</li>
            </ul>
            <h3>4. Gestion Flats</h3>
            <ul>
                <li><b>Scan :</b> Détecte et groupe les flat frames par setup/filtre/date</li>
                <li><b>Couverture :</b> Vérifie que chaque combinaison a assez de flats</li>
            </ul>
            <h3>5. Suivi Cibles</h3>
            <ul>
                <li><b>Historique :</b> Temps d'observation par cible au fil du temps</li>
                <li><b>Prévisions :</b> Météo et visibilité des cibles pour les prochaines nuits</li>
            </ul>
            <h3>6. Historique & Statistiques</h3>
            <ul>
                <li><b>Tableau de bord :</b> Statistiques globales (cibles, intégration, nuits, HFR)</li>
                <li><b>Classement cibles :</b> Cibles triées par temps d'intégration</li>
                <li><b>Filtres :</b> Statistiques par filtre (temps, images, HFR moyen)</li>
                <li><b>Équipement :</b> Statistiques par télescope, caméra et setup</li>
                <li><b>Temporel :</b> Statistiques mensuelles, annuelles, par jour de la semaine</li>
                <li><b>Meilleures nuits :</b> Classement par qualité (HFR) ou productivité</li>
                <li><b>Export/Import :</b> JSON (complet) ou CSV (tableur) pour sauvegarde et partage</li>
                <li><b>Sauvegarde auto :</b> Base de données sauvegardée automatiquement à la fermeture</li>
            </ul>
            <h3>7. Base de Données</h3>
            <ul>
                <li><b>Caméras :</b> 1 600+ capteurs avec specs (pixel, bruit, QE, résolution)</li>
                <li><b>Télescopes :</b> 3 900+ modèles avec ouverture, focale, rapport f/</li>
                <li><b>Filtres :</b> 1 600+ filtres avec longueur d'onde et bande passante</li>
                <li><b>Cibles :</b> 32 900+ objets astronomiques (Messier, NGC, IC, Arp, etc.)</li>
                <li><b>Recherche :</b> Recherche par nom + filtre par marque/type/catalogue</li>
            </ul>
            <h3>8. Espace Disque</h3>
            <ul>
                <li><b>Analyse :</b> Répartition FITS/XISF/FZ et espace utilisé</li>
                <li><b>Organisation :</b> Organiser les fichiers par type/date/cible avec des presets</li>
            </ul>
            <h3>9. Exécutable Autonome (.exe)</h3>
            <ul>
                <li><b>Windows :</b> Lancez <code>build.bat</code> pour créer <code>dist\\AstroManager\\AstroManager.exe</code></li>
                <li><b>Linux / macOS :</b> Lancez <code>./build.sh</code> pour créer <code>dist/AstroManager/AstroManager</code></li>
                <li><b>Prérequis :</b> PyInstaller (<code>pip install pyinstaller</code>)</li>
                <li><b>Données :</b> Configuration et base de données restent dans le répertoire du projet</li>
                <li><b>Multiplateforme :</b> Fonctionne sur Windows, Linux et macOS</li>
            </ul>
            <h3>10. Mises à jour</h3>
            <ul>
                <li><b>Automatique :</b> Vérifie les nouvelles versions au démarrage (opt-in dans Réglages)</li>
                <li><b>Manuel :</b> Aide > Vérifier les mises à jour</li>
                <li><b>Ignorer :</b> Bouton « Ignorer cette version » pour ne plus être notifié</li>
                <li><b>Fréquence :</b> Un seul appel HTTPS vers GitHub, max une fois par 24h</li>
            </ul>
            <h3>Raccourcis</h3>
            <p>Ctrl+, = Réglages | Ctrl+Q = Quitter | Ctrl+` = Console | F1 = Aide</p>
            """)
        else:
            text.setHtml("""
            <h2>AstroManager User Guide</h2>
            <h3>1. Analysis (main tab)</h3>
            <ul>
                <li><b>Folder selection:</b> Choose the folder containing your FITS/XISF files</li>
                <li><b>SIMBAD:</b> Resolves object names (M31 = NGC 224) and auto-merges</li>
                <li><b>Plate solving:</b> Detects focal reducers via ASTAP</li>
                <li><b>Weather:</b> Fetches historical weather data for each observation night</li>
                <li><b>Workers:</b> 0 = optimal auto-detection based on CPU/RAM/disk</li>
                <li><b>Outputs:</b> Graphs, PDF/LaTeX report, thumbnails, AstroBin CSV</li>
            </ul>
            <h3>2. Compression</h3>
            <ul>
                <li><b>Profiles:</b> zlib (universal), zstd (high compression), lz4 (ultra-fast)</li>
                <li><b>Formats:</b> FITS → XISF, FITS → FITS.FZ (RICE), and reverse</li>
                <li><b>Integrity:</b> Optional SHA-256 verification after compression</li>
            </ul>
            <h3>3. Header Editor</h3>
            <ul>
                <li><b>Mass editing:</b> Modify FITS/XISF headers for hundreds of files at once</li>
                <li><b>Categories:</b> Acquisition, Camera, Filter, Image, Telescope, etc.</li>
                <li><b>NINA pattern:</b> NINA-compatible filename pattern generator</li>
                <li><b>Auto-rename:</b> After header changes, automatically proposes renaming files to match the configured NINA pattern</li>
            </ul>
            <h3>4. Flat Management</h3>
            <ul>
                <li><b>Scan:</b> Detect and group flat frames by setup/filter/date</li>
                <li><b>Coverage:</b> Verify each combination has enough flats</li>
            </ul>
            <h3>5. Target Tracking</h3>
            <ul>
                <li><b>History:</b> Observation time per target over time</li>
                <li><b>Forecast:</b> Weather and target visibility for upcoming nights</li>
            </ul>
            <h3>6. History & Statistics</h3>
            <ul>
                <li><b>Dashboard:</b> Global stats (targets, integration, nights, HFR)</li>
                <li><b>Target Rankings:</b> Targets sorted by integration time</li>
                <li><b>Filters:</b> Per-filter stats (time, frames, average HFR)</li>
                <li><b>Equipment:</b> Stats per telescope, camera, and setup</li>
                <li><b>Temporal:</b> Monthly, yearly, day-of-week statistics</li>
                <li><b>Best Nights:</b> Ranked by quality (HFR) or productivity</li>
                <li><b>Export/Import:</b> JSON (complete) or CSV (spreadsheet) for backup and sharing</li>
                <li><b>Auto-save:</b> Database automatically backed up on exit</li>
            </ul>
            <h3>7. Database Browser</h3>
            <ul>
                <li><b>Cameras:</b> 1,600+ sensors with specs (pixel size, noise, QE, resolution)</li>
                <li><b>Telescopes:</b> 3,900+ models with aperture, focal length, f-ratio</li>
                <li><b>Filters:</b> 1,600+ filters with wavelength and bandwidth</li>
                <li><b>Targets:</b> 32,900+ astronomical objects (Messier, NGC, IC, Arp, etc.)</li>
                <li><b>Search:</b> Search by name + filter by brand/type/catalog</li>
            </ul>
            <h3>8. Disk Space</h3>
            <ul>
                <li><b>Analysis:</b> FITS/XISF/FZ breakdown and space usage</li>
                <li><b>Organization:</b> Organize files by type/date/target with presets</li>
            </ul>
            <h3>9. Standalone Executable (.exe)</h3>
            <ul>
                <li><b>Windows:</b> Run <code>build.bat</code> to create <code>dist\\AstroManager\\AstroManager.exe</code></li>
                <li><b>Linux / macOS:</b> Run <code>./build.sh</code> to create <code>dist/AstroManager/AstroManager</code></li>
                <li><b>Prerequisite:</b> PyInstaller (<code>pip install pyinstaller</code>)</li>
                <li><b>Data:</b> Configuration and database remain in the project directory</li>
                <li><b>Cross-platform:</b> Works on Windows, Linux, and macOS</li>
            </ul>
            <h3>10. Updates</h3>
            <ul>
                <li><b>Automatic:</b> Checks for new versions on startup (opt-in via Settings)</li>
                <li><b>Manual:</b> Help > Check for Updates</li>
                <li><b>Skip:</b> "Skip This Version" button to dismiss specific releases</li>
                <li><b>Frequency:</b> Single HTTPS call to GitHub, max once per 24 hours</li>
            </ul>
            <h3>Shortcuts</h3>
            <p>Ctrl+, = Settings | Ctrl+Q = Quit | Ctrl+` = Console | F1 = Help</p>
            """)

        layout.addWidget(text)
        close_btn = QPushButton(self._tr("Close", "Fermer"))
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.exec()

    def _show_shortcuts(self):
        """Show keyboard shortcuts dialog"""
        shortcuts = [
            ("Ctrl+O", self._tr("Open folder", "Ouvrir un dossier")),
            ("Ctrl+,", self._tr("Open Settings", "Ouvrir Réglages")),
            ("Ctrl+Q", self._tr("Quit application", "Quitter l'application")),
            ("Ctrl+`", self._tr("Toggle console panel", "Basculer panneau console")),
            ("F1", self._tr("Open user guide", "Ouvrir le guide utilisateur")),
        ]
        rows = "".join(
            f"<tr><td style='padding:4px 12px 4px 0;'><code>{key}</code></td><td>{desc}</td></tr>"
            for key, desc in shortcuts
        )
        QMessageBox.information(self,
            self._tr("Keyboard Shortcuts", "Raccourcis Clavier"),
            f"<h3>{self._tr('Keyboard Shortcuts', 'Raccourcis Clavier')}</h3>"
            f"<table>{rows}</table>")

    def closeEvent(self, event):
        """Handle window close - check for running analysis"""
        # Check if analysis is running
        if hasattr(self, 'analysis_tab') and self.analysis_tab.is_running():
            reply = QMessageBox.question(self,
                self._tr("Confirm Exit", "Confirmer la Fermeture"),
                self._tr(
                    "An analysis is currently running.\nAre you sure you want to exit?",
                    "Une analyse est en cours d'exécution.\nÊtes-vous sûr de vouloir quitter?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            # Stop the worker
            self.analysis_tab._stop_analysis()

        # Save window geometry
        try:
            self.config.set('ui.window_width', self.width())
            self.config.set('ui.window_height', self.height())
            self.config.save_config()
        except Exception:
            pass

        # Auto-save: backup database on exit
        try:
            from core.database import get_db
            db = get_db()
            backup_path = db.backup_database()
            if backup_path:
                signals.history_auto_saved.emit()
                logger.info(f"Auto-save: database backed up to {backup_path}")
        except Exception as e:
            logger.warning(f"Auto-save backup failed: {e}")

        if self.bug_reporter:
            self.bug_reporter.uninstall_global_handler()
        event.accept()


def create_application():
    """Create and configure the Qt application"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setApplicationName("AstroManager")
    app.setApplicationVersion(__version__)

    # Set application icon (taskbar + window)
    if getattr(sys, 'frozen', False):
        _base = sys._MEIPASS
    else:
        _base = os.path.dirname(os.path.dirname(__file__))
    icon_path = os.path.join(_base, 'assets', 'icon.png')
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Apply cosmic theme
    apply_cosmic_theme(app)

    return app


def main():
    """Main entry point for AstroManager GUI"""
    app = create_application()

    # Initialize core services
    config = None
    try:
        from core.config import get_config
        from core.database import get_db
        config = get_config()
        db = get_db()
        db.backup_database()
    except Exception as e:
        logger.error(f"Core initialization failed: {e}")

    window = AstroManagerWindow()
    window.show()

    # Offer desktop shortcut on first launch
    from shortcut_helper import offer_shortcut
    offer_shortcut("AstroManager", "astromanager.py", "assets/icon.ico",
                   get_config=lambda k: config.get(k) if config else None,
                   set_config=lambda k, v: (config.set(k, v), config.save_config()) if config else None)

    # Auto-check for updates after a delay (let the UI load first)
    if config and config.get('application.check_updates_on_startup', True):
        QTimer.singleShot(3000, lambda: window._check_for_updates(silent=True))

    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
