#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - BUG REPORT DIALOGS
================================================================================
Two dialogs for bug reporting:
- CrashReportDialog: shown after an unhandled crash (consent before sending)
- ManualBugReportDialog: opened from Help > Report Bug
================================================================================
"""

import logging

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton
)
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class CrashReportDialog(QDialog):
    """
    Dialog shown after an unhandled exception.
    Shows exception type + report preview, lets the user choose to send or not.
    """

    def __init__(self, report: dict, bug_reporter, lang='en', parent=None):
        super().__init__(parent)
        self.report = report
        self.bug_reporter = bug_reporter
        self.lang = lang
        self._was_sent = False

        self.setWindowTitle(self._tr("Crash Report", "Rapport de Crash"))
        self.setMinimumSize(550, 400)
        self.setModal(True)

        self._init_ui()

    def _tr(self, en, fr):
        return fr if self.lang == 'fr' else en

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Header
        exc = self.report.get('exception', {})
        exc_type = exc.get('type', 'Unknown')
        exc_msg = exc.get('message', '')

        header = QLabel(self._tr(
            f"<h3>AstroManager has crashed</h3>"
            f"<p><b>{exc_type}:</b> {exc_msg}</p>",
            f"<h3>AstroManager a planté</h3>"
            f"<p><b>{exc_type} :</b> {exc_msg}</p>"
        ))
        header.setWordWrap(True)
        layout.addWidget(header)

        # Report preview
        preview_label = QLabel(self._tr(
            "The following data will be sent (read-only):",
            "Les données suivantes seront envoyées (lecture seule) :"
        ))
        layout.addWidget(preview_label)

        preview_text = QTextEdit()
        preview_text.setReadOnly(True)
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        preview_text.setFont(font)
        preview_text.setPlainText(self.bug_reporter.get_report_preview(self.report))
        layout.addWidget(preview_text)

        # Privacy note
        note = QLabel(self._tr(
            "<i>No personal data is collected — only technical information "
            "(OS, Python version, traceback, dependencies).</i>",
            "<i>Aucune donnée personnelle n'est collectée — uniquement des "
            "informations techniques (OS, version Python, traceback, dépendances).</i>"
        ))
        note.setWordWrap(True)
        note.setStyleSheet("color: #8b95b0; font-size: 9pt;")
        layout.addWidget(note)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        dont_send_btn = QPushButton(self._tr("Don't Send", "Ne pas envoyer"))
        dont_send_btn.clicked.connect(self.reject)
        btn_layout.addWidget(dont_send_btn)

        send_btn = QPushButton(self._tr("Send Report", "Envoyer le rapport"))
        send_btn.setDefault(True)
        send_btn.clicked.connect(self._send_report)
        btn_layout.addWidget(send_btn)

        layout.addLayout(btn_layout)

    def _send_report(self):
        """Send the crash report in a background thread."""
        self._was_sent = True
        self.accept()

    def was_sent(self) -> bool:
        return self._was_sent


class ManualBugReportDialog(QDialog):
    """
    Dialog for user-initiated bug reports (Help > Report Bug).
    Fields: description, steps to reproduce.
    Preview button generates the report; Submit is only enabled after preview.
    """

    def __init__(self, bug_reporter, lang='en', parent=None):
        super().__init__(parent)
        self.bug_reporter = bug_reporter
        self.lang = lang
        self._report = None
        self._was_submitted = False

        self.setWindowTitle(self._tr("Report a Bug", "Signaler un Bug"))
        self.setMinimumSize(550, 450)
        self.setModal(True)

        self._init_ui()

    def _tr(self, en, fr):
        return fr if self.lang == 'fr' else en

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Description
        desc_label = QLabel(self._tr(
            "Bug description:",
            "Description du bug :"
        ))
        layout.addWidget(desc_label)

        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText(self._tr(
            "Describe the bug you encountered...",
            "Décrivez le bug rencontré..."
        ))
        self.desc_edit.setMaximumHeight(120)
        layout.addWidget(self.desc_edit)

        # Steps to reproduce
        steps_label = QLabel(self._tr(
            "Steps to reproduce:",
            "Étapes pour reproduire :"
        ))
        layout.addWidget(steps_label)

        self.steps_edit = QTextEdit()
        self.steps_edit.setPlaceholderText(self._tr(
            "1. Open...\n2. Click on...\n3. ...",
            "1. Ouvrir...\n2. Cliquer sur...\n3. ..."
        ))
        self.steps_edit.setMaximumHeight(100)
        layout.addWidget(self.steps_edit)

        # Preview area (hidden until Preview is clicked)
        self.preview_label = QLabel(self._tr("Preview:", "Aperçu :"))
        self.preview_label.setVisible(False)
        layout.addWidget(self.preview_label)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.preview_text.setFont(font)
        self.preview_text.setVisible(False)
        layout.addWidget(self.preview_text)

        # Privacy note
        note = QLabel(self._tr(
            "<i>No personal data is collected — only technical information.</i>",
            "<i>Aucune donnée personnelle n'est collectée — uniquement des informations techniques.</i>"
        ))
        note.setWordWrap(True)
        note.setStyleSheet("color: #8b95b0; font-size: 9pt;")
        layout.addWidget(note)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(self._tr("Cancel", "Annuler"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self.preview_btn = QPushButton(self._tr("Preview", "Aperçu"))
        self.preview_btn.clicked.connect(self._generate_preview)
        btn_layout.addWidget(self.preview_btn)

        self.submit_btn = QPushButton(self._tr("Submit", "Soumettre"))
        self.submit_btn.setEnabled(False)
        self.submit_btn.clicked.connect(self._submit_report)
        btn_layout.addWidget(self.submit_btn)

        layout.addLayout(btn_layout)

    def _generate_preview(self):
        """Generate report and show preview."""
        description = self.desc_edit.toPlainText().strip()
        steps = self.steps_edit.toPlainText().strip()

        if not description:
            self.desc_edit.setFocus()
            return

        report = self.bug_reporter.create_report(description=description)
        report['manual'] = True
        report['steps_to_reproduce'] = steps
        self._report = report

        self.preview_text.setPlainText(self.bug_reporter.get_report_preview(report))
        self.preview_label.setVisible(True)
        self.preview_text.setVisible(True)
        self.submit_btn.setEnabled(True)

    def _submit_report(self):
        """Mark as submitted and accept dialog."""
        if self._report is None:
            return
        self._was_submitted = True
        self.accept()

    def was_submitted(self) -> bool:
        return self._was_submitted

    def get_report(self) -> dict:
        return self._report
