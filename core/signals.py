#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - GLOBAL SIGNAL BUS
================================================================================
Centralized signal bus for cross-tab and cross-component communication.
Singleton is managed by get_signals() factory function (not class-level
__new__/__init__, which conflicts with PyQt6's QObject on Python 3.13+).
================================================================================
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Dict, Any


class GlobalSignalBus(QObject):
    """
    Centralized signal bus for application-wide event communication.
    Enables loose coupling between UI components.

    NOTE: Do NOT override __new__ or __init__ with singleton logic.
    PyQt6's QObject.__init__ triggers C-level recursion when combined
    with singleton __new__. Use get_signals() for singleton access.
    """

    # =========================================================================
    # Analysis Signals
    # =========================================================================
    analysis_started = pyqtSignal(str)  # folder_path
    analysis_progress = pyqtSignal(int, int, str)  # current, total, phase_name
    analysis_completed = pyqtSignal(dict)  # results_dict
    analysis_error = pyqtSignal(str)  # error_message
    analysis_stopped = pyqtSignal()

    # =========================================================================
    # Compression Signals
    # =========================================================================
    compression_started = pyqtSignal(int)  # total_file_count
    compression_file_progress = pyqtSignal(str, int, int)  # filename, current, total
    compression_file_done = pyqtSignal(str, bool, str)  # filename, success, message
    compression_completed = pyqtSignal(dict)  # statistics_dict
    compression_error = pyqtSignal(str)  # error_message

    # =========================================================================
    # Header Editing Signals
    # =========================================================================
    headers_edit_started = pyqtSignal(int)  # file_count
    headers_edit_progress = pyqtSignal(int, int)  # current, total
    headers_modified = pyqtSignal(list)  # modified_file_paths
    headers_edit_completed = pyqtSignal(dict)  # statistics_dict
    headers_edit_error = pyqtSignal(str)  # error_message

    # =========================================================================
    # Flat Manager Signals
    # =========================================================================
    flats_scan_started = pyqtSignal(str)  # folder_path
    flats_scan_progress = pyqtSignal(int, int)  # current, total
    flats_scanned = pyqtSignal(dict)  # flat_groups_dict
    master_flat_created = pyqtSignal(str, str, str)  # date, setup, filter
    flat_linked_to_target = pyqtSignal(str, str)  # target_name, flat_id
    flats_error = pyqtSignal(str)  # error_message

    # =========================================================================
    # Target Tracking Signals
    # =========================================================================
    target_added = pyqtSignal(str, dict)  # target_name, target_data
    target_updated = pyqtSignal(str, dict)  # target_name, updated_data
    observation_added = pyqtSignal(str, dict)  # target_name, observation_data
    target_selected = pyqtSignal(str)  # target_name
    targets_refreshed = pyqtSignal()

    # =========================================================================
    # Plate Solving Signals
    # =========================================================================
    plate_solve_started = pyqtSignal(str)  # file_path
    plate_solve_progress = pyqtSignal(int, int)  # current, total
    plate_solve_result = pyqtSignal(str, dict)  # file_path, wcs_data
    plate_solve_error = pyqtSignal(str, str)  # file_path, error_message
    plate_solve_completed = pyqtSignal(dict)  # statistics_dict

    # =========================================================================
    # Weather Signals
    # =========================================================================
    weather_fetch_started = pyqtSignal(str)  # date
    weather_fetched = pyqtSignal(str, dict)  # date, weather_data
    weather_cache_updated = pyqtSignal(int)  # cached_entries_count
    weather_error = pyqtSignal(str)  # error_message

    # =========================================================================
    # Disk Space Signals
    # =========================================================================
    storage_analysis_started = pyqtSignal(str)  # folder_path
    storage_analysis_progress = pyqtSignal(int, int)  # current, total
    storage_analyzed = pyqtSignal(dict)  # storage_stats_dict
    storage_optimization_started = pyqtSignal(str)  # operation_type
    storage_optimization_completed = pyqtSignal(dict)  # results_dict
    storage_error = pyqtSignal(str)  # error_message

    # =========================================================================
    # Observation History Signals
    # =========================================================================
    history_refreshed = pyqtSignal()
    history_exported = pyqtSignal(str, int)  # file_path, record_count
    history_imported = pyqtSignal(int, int)  # targets_count, observations_count
    history_auto_saved = pyqtSignal()

    # =========================================================================
    # Database Signals
    # =========================================================================
    database_initialized = pyqtSignal()
    database_error = pyqtSignal(str)  # error_message
    database_backup_created = pyqtSignal(str)  # backup_file_path

    # =========================================================================
    # UI State Signals
    # =========================================================================
    tab_changed = pyqtSignal(int, str)  # tab_index, tab_name
    theme_changed = pyqtSignal(str)  # theme_name
    language_changed = pyqtSignal(str)  # language_code
    busy_state_changed = pyqtSignal(bool)  # is_busy

    # =========================================================================
    # General Application Signals
    # =========================================================================
    log_message = pyqtSignal(str, str)  # level, message (level: INFO, WARNING, ERROR)
    status_message = pyqtSignal(str, int)  # message, timeout_ms
    error_occurred = pyqtSignal(str, str)  # title, message
    warning_occurred = pyqtSignal(str, str)  # title, message
    info_occurred = pyqtSignal(str, str)  # title, message


# Global singleton instance - lazy initialization to avoid
# crashes when imported before QApplication exists
_signals_instance = None


def get_signals() -> GlobalSignalBus:
    """Get global signal bus instance (creates on first call)."""
    global _signals_instance
    if _signals_instance is None:
        _signals_instance = GlobalSignalBus()
    return _signals_instance


class _SignalsProxy:
    """Proxy that lazily initializes GlobalSignalBus on first attribute access.
    This allows `from core.signals import signals` to work at module level
    without requiring QApplication to exist at import time."""

    def __getattr__(self, name):
        return getattr(get_signals(), name)

    def __repr__(self):
        if _signals_instance is not None:
            return f"<SignalsProxy -> {_signals_instance!r}>"
        return "<SignalsProxy (not initialized)>"


signals = _SignalsProxy()
