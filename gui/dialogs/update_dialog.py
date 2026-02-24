#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - UPDATE NOTIFICATION DIALOG
================================================================================
Shows available update info: current/latest version, release notes.
Offers Download (opens GitHub), Skip This Version, and Later buttons.
All strings are bilingual EN/FR.
================================================================================
"""

import sys
import logging

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton
)
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices, QFont

from gui.theme import COLORS

logger = logging.getLogger(__name__)


class UpdateDialog(QDialog):
    """
    Dialog shown when a new version is available.

    Buttons:
        - Download and Install (source installs) / Download from GitHub (frozen)
        - View on GitHub
        - Skip This Version
        - Later
    """

    def __init__(self, release_info: dict, current_version: str,
                 lang='en', parent=None):
        """
        Args:
            release_info: dict from UpdateChecker.check_for_update() with keys
                          latest_version, release_url, download_url,
                          release_notes, date.
            current_version: Current application version string.
            lang: 'en' or 'fr'.
        """
        super().__init__(parent)
        self.release_info = release_info
        self.current_version = current_version
        self.lang = lang
        self._action = None  # 'install', 'github', 'skip', or None (later)

        self.setWindowTitle(self._tr("Update Available", "Mise à jour disponible"))
        self.setMinimumSize(500, 350)
        self.setModal(True)

        self._init_ui()

    def _tr(self, en, fr):
        return fr if self.lang == 'fr' else en

    @property
    def action(self):
        """Return the action chosen by the user after exec()."""
        return self._action

    def _init_ui(self):
        layout = QVBoxLayout(self)

        latest = self.release_info['latest_version']
        date = (self.release_info.get('date') or '')[:10]
        is_frozen = getattr(sys, 'frozen', False)

        # Header
        header = QLabel(self._tr(
            f"<h3>AstroManager v{latest} is available!</h3>"
            f"<p>Current version: v{self.current_version} → "
            f"New version: v{latest}"
            f"{' (' + date + ')' if date else ''}</p>",
            f"<h3>AstroManager v{latest} est disponible !</h3>"
            f"<p>Version actuelle : v{self.current_version} → "
            f"Nouvelle version : v{latest}"
            f"{' (' + date + ')' if date else ''}</p>"
        ))
        header.setWordWrap(True)
        layout.addWidget(header)

        # Frozen .exe note
        if is_frozen:
            frozen_note = QLabel(self._tr(
                "<p><i>You are running the standalone .exe version.<br>"
                "Please download the new version from GitHub and replace "
                "your current installation.</i></p>",
                "<p><i>Vous utilisez la version .exe autonome.<br>"
                "Veuillez télécharger la nouvelle version depuis GitHub "
                "et remplacer votre installation actuelle.</i></p>"
            ))
            frozen_note.setWordWrap(True)
            frozen_note.setStyleSheet(
                f"color: {COLORS.get('accent_orange', '#FFA500')};")
            layout.addWidget(frozen_note)

        # Release notes
        notes = self.release_info.get('release_notes', '')
        if notes:
            notes_label = QLabel(self._tr("Changelog:", "Notes de version :"))
            notes_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(notes_label)

            # Basic markdown cleanup for display
            cleaned = []
            for line in notes.split('\n'):
                line = line.replace('### ', '').replace('## ', '')
                line = line.replace('# ', '')
                line = line.replace('**', '').replace('__', '')
                cleaned.append(line)
            display_notes = '\n'.join(cleaned).strip()

            notes_text = QTextEdit()
            notes_text.setReadOnly(True)
            notes_text.setPlainText(display_notes)
            notes_text.setMaximumHeight(180)
            font = QFont("Segoe UI", 9)
            font.setStyleHint(QFont.StyleHint.SansSerif)
            notes_text.setFont(font)
            layout.addWidget(notes_text)

        # Buttons
        btn_layout = QHBoxLayout()

        if not is_frozen:
            install_btn = QPushButton(self._tr(
                "Download and Install", "Télécharger et installer"))
            install_btn.setStyleSheet(
                f"background-color: {COLORS['accent_cyan']}; color: white; "
                f"font-weight: bold; padding: 6px 16px;")
            install_btn.clicked.connect(self._on_install)
            btn_layout.addWidget(install_btn)

        github_btn = QPushButton(self._tr(
            "Download from GitHub" if is_frozen else "View on GitHub",
            "Télécharger depuis GitHub" if is_frozen else "Voir sur GitHub"))
        if is_frozen:
            github_btn.setStyleSheet(
                f"background-color: {COLORS['accent_cyan']}; color: white; "
                f"font-weight: bold; padding: 6px 16px;")
        github_btn.clicked.connect(self._on_github)
        btn_layout.addWidget(github_btn)

        skip_btn = QPushButton(self._tr(
            "Skip This Version", "Ignorer cette version"))
        skip_btn.setToolTip(self._tr(
            "Don't notify me again for this version",
            "Ne plus me notifier pour cette version"))
        skip_btn.clicked.connect(self._on_skip)
        btn_layout.addWidget(skip_btn)

        later_btn = QPushButton(self._tr("Later", "Plus tard"))
        later_btn.clicked.connect(self.reject)
        btn_layout.addWidget(later_btn)

        layout.addLayout(btn_layout)

    def _on_install(self):
        self._action = 'install'
        self.accept()

    def _on_github(self):
        url = self.release_info.get('release_url', '')
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _on_skip(self):
        self._action = 'skip'
        self.accept()
