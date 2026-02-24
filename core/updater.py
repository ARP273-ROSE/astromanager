#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - UPDATE CHECKER COORDINATOR
================================================================================
High-level update checking with interval caching, skip-version support,
and a non-blocking QThread worker. Delegates the actual GitHub API call
to modules.updater.check_for_update().

Network access is opt-in: disabled by default, the user must enable
'check_updates_on_startup' in Settings. When enabled, a single HTTPS
GET is sent to the GitHub Releases API (no other network activity).
================================================================================
"""

import time
import logging
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class UpdateChecker:
    """
    Coordinates update checks with interval throttling and skip-version logic.

    Config keys used:
        application.check_updates_on_startup  (bool, default False)
        application.update_check_interval_hours  (int, default 24)
        application.last_update_check  (float, epoch timestamp)
        application.skipped_update_version  (str, e.g. '1.2.0')
    """

    def __init__(self, current_version: str, config):
        self.current_version = current_version
        self.config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def should_check(self) -> bool:
        """Return True if enough time has elapsed since the last check."""
        interval_hours = self.config.get(
            'application.update_check_interval_hours', 24)
        last_check = self.config.get('application.last_update_check', 0)
        try:
            last_check = float(last_check)
        except (TypeError, ValueError):
            last_check = 0

        elapsed_hours = (time.time() - last_check) / 3600
        return elapsed_hours >= interval_hours

    def check_for_update(self, respect_interval: bool = True) -> Optional[dict]:
        """
        Check for updates, optionally respecting the interval throttle.

        Args:
            respect_interval: If True, return None immediately when the
                              check interval has not elapsed yet.

        Returns:
            dict with keys {available, latest_version, current_version,
            download_url, release_url, release_notes, date} when an
            update is available, or None.
        """
        if respect_interval and not self.should_check():
            logger.debug("Update check skipped (interval not elapsed)")
            return None

        try:
            from modules.updater import check_for_update
            result = check_for_update(self.current_version)
        except Exception as exc:
            logger.warning("Update check failed: %s", exc)
            raise

        # Record the check timestamp regardless of result
        self.config.set('application.last_update_check', time.time())
        self.config.save_config()

        if result is None:
            return None

        latest = result['version']

        # Skip if user chose to skip this version
        skipped = self.config.get('application.skipped_update_version', '')
        if skipped and skipped == latest:
            logger.info("Update v%s skipped by user preference", latest)
            return None

        return {
            'available': True,
            'latest_version': latest,
            'current_version': self.current_version,
            'download_url': result.get('download_url', ''),
            'release_url': result.get('url', ''),
            'release_notes': result.get('body', ''),
            'date': result.get('date', ''),
        }

    def skip_version(self, version: str):
        """Record that the user wants to skip a specific version."""
        self.config.set('application.skipped_update_version', version)
        self.config.save_config()

    def clear_skipped_version(self):
        """Clear the skipped version (e.g. on manual check)."""
        self.config.set('application.skipped_update_version', '')
        self.config.save_config()


class UpdateWorker(QThread):
    """
    Non-blocking QThread that runs an update check in the background.

    Signals:
        update_found(dict)  - emitted when a new version is available
        no_update()         - emitted when already up to date
        check_failed(str)   - emitted on error (network, timeout, etc.)
    """

    update_found = pyqtSignal(dict)
    no_update = pyqtSignal()
    check_failed = pyqtSignal(str)

    def __init__(self, checker: UpdateChecker, respect_interval: bool = True,
                 parent=None):
        super().__init__(parent)
        self.checker = checker
        self.respect_interval = respect_interval

    def run(self):
        try:
            result = self.checker.check_for_update(
                respect_interval=self.respect_interval)
            if result is not None:
                self.update_found.emit(result)
            else:
                self.no_update.emit()
        except Exception as exc:
            self.check_failed.emit(str(exc))
