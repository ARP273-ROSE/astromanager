#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - OBSERVATION HISTORY TAB
================================================================================
Dashboard tab showing comprehensive observation history statistics,
with export/import functionality and auto-save support.
================================================================================
"""

import json
import logging
import threading
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget, QAbstractItemView,
    QMessageBox, QFileDialog, QFrame, QGridLayout,
    QComboBox, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from core.signals import signals
from core.config import get_config
from core.i18n import get_lang
from gui.theme import prettify_filter_name

logger = logging.getLogger(__name__)


def _translate_otype(code: str, lang: str = 'en') -> str:
    """Translate a SIMBAD otype code to a human-readable label.

    Uses fits_analyser_gui.SIMBAD_OTYPE_LABELS when available, otherwise
    falls back to a compact built-in mapping of the most common codes.
    """
    if not code or not code.strip():
        return 'Unknown' if lang == 'en' else 'Inconnu'
    code = code.strip()

    # Try the comprehensive dictionary from the analysis engine
    try:
        from fits_analyser_gui import SIMBAD_OTYPE_LABELS
        idx = 0 if lang == 'fr' else 1
        if code in SIMBAD_OTYPE_LABELS:
            return SIMBAD_OTYPE_LABELS[code][idx]
        for n in (3, 2, 1):
            if len(code) >= n and code[:n] in SIMBAD_OTYPE_LABELS:
                return SIMBAD_OTYPE_LABELS[code[:n]][idx]
    except ImportError:
        pass

    # Compact fallback for the most common deep-sky codes
    _fallback = {
        'G':   ('Galaxie', 'Galaxy'),
        'GNe': ('Nébuleuse', 'Nebula'),
        'PN':  ('Nébuleuse planétaire', 'Planetary Nebula'),
        'HII': ('Région HII', 'HII Region'),
        'RNe': ('Nébuleuse par réflexion', 'Reflection Nebula'),
        'DNe': ('Nébuleuse obscure', 'Dark Nebula'),
        'SNR': ('Rémanent de supernova', 'Supernova Remnant'),
        'OpC': ('Amas ouvert', 'Open Cluster'),
        'GlC': ('Amas globulaire', 'Globular Cluster'),
        'Cl*': ("Amas d'étoiles", 'Star Cluster'),
        'ClG': ("Amas de galaxies", 'Galaxy Cluster'),
        '*':   ('Étoile', 'Star'),
        '**':  ('Étoile double', 'Double Star'),
        'ISM': ('Milieu interstellaire', 'Interstellar Medium'),
        'SFR': ('Région de formation stellaire', 'Star-forming Region'),
        'Pl':  ('Planète', 'Planet'),
        '?':   ('Inconnu', 'Unknown'),
    }
    idx = 0 if lang == 'fr' else 1
    if code in _fallback:
        return _fallback[code][idx]
    return code


class StatCard(QFrame):
    """A styled card widget for displaying a single statistic."""

    def __init__(self, title: str, value: str = "-", color: str = "#88b8d8",
                 parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            StatCard {{
                background: rgba(20, 30, 50, 0.6);
                border: 1px solid rgba(100, 140, 180, 0.3);
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #8898a8; font-size: 9pt;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(
            f"color: {color}; font-size: 16pt; font-weight: bold;"
        )
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)

    def set_value(self, value: str):
        self.value_label.setText(value)

    def set_title(self, title: str):
        self.title_label.setText(title)


class HistoryTab(QWidget):
    """Observation History tab - comprehensive stats dashboard with export/import."""

    # Signal emitted when background maintenance finishes [PERF]
    _maintenance_done_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self.lang = get_lang()
        self._init_ui()
        self._connect_signals()
        # Defer initial load to avoid DB access during construction
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(500, self.refresh_all)

    def _tr(self, en, fr):
        return fr if self.lang == 'fr' else en

    def _format_time(self, seconds):
        """Format seconds into human-readable time string."""
        if seconds is None or seconds <= 0:
            return "-"
        hours = seconds / 3600
        if hours >= 1:
            h = int(hours)
            m = int((hours - h) * 60)
            return f"{h}h {m:02d}m" if m > 0 else f"{h}h"
        minutes = seconds / 60
        if minutes >= 1:
            return f"{minutes:.0f}m"
        return f"{seconds:.0f}s"

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Top bar: Title + Buttons ──
        top_bar = QHBoxLayout()

        title = QLabel(self._tr(
            "📊 Observation History & Statistics",
            "📊 Historique d'Observations & Statistiques"
        ))
        title.setStyleSheet("font-size: 13pt; font-weight: bold; color: #a8c8e8;")
        top_bar.addWidget(title)
        top_bar.addStretch()

        self.refresh_btn = QPushButton(self._tr("🔄 Refresh", "🔄 Actualiser"))
        self.refresh_btn.setToolTip(self._tr(
            "Refresh all statistics from database",
            "Actualiser toutes les statistiques depuis la base de données"
        ))
        self.refresh_btn.clicked.connect(self.refresh_all)
        top_bar.addWidget(self.refresh_btn)

        self.export_json_btn = QPushButton(self._tr("📤 Export JSON", "📤 Exporter JSON"))
        self.export_json_btn.setToolTip(self._tr(
            "Export complete observation history to JSON file",
            "Exporter l'historique complet des observations en fichier JSON"
        ))
        self.export_json_btn.clicked.connect(self._export_json)
        top_bar.addWidget(self.export_json_btn)

        self.export_csv_btn = QPushButton(self._tr("📤 Export CSV", "📤 Exporter CSV"))
        self.export_csv_btn.setToolTip(self._tr(
            "Export observations to CSV spreadsheet",
            "Exporter les observations en tableur CSV"
        ))
        self.export_csv_btn.clicked.connect(self._export_csv)
        top_bar.addWidget(self.export_csv_btn)

        self.import_json_btn = QPushButton(self._tr("📥 Import JSON", "📥 Importer JSON"))
        self.import_json_btn.setToolTip(self._tr(
            "Import observation history from JSON file",
            "Importer l'historique des observations depuis un fichier JSON"
        ))
        self.import_json_btn.clicked.connect(self._import_json)
        top_bar.addWidget(self.import_json_btn)

        self.import_csv_btn = QPushButton(self._tr("📥 Import CSV", "📥 Importer CSV"))
        self.import_csv_btn.setToolTip(self._tr(
            "Import observations from CSV spreadsheet",
            "Importer les observations depuis un tableur CSV"
        ))
        self.import_csv_btn.clicked.connect(self._import_csv)
        top_bar.addWidget(self.import_csv_btn)

        self.clear_all_btn = QPushButton(self._tr("🗑 Clear All", "🗑 Tout Effacer"))
        self.clear_all_btn.setToolTip(self._tr(
            "Delete all observation history (targets and sessions)",
            "Supprimer tout l'historique d'observations (cibles et sessions)"
        ))
        self.clear_all_btn.setStyleSheet("QPushButton { color: #ff6666; }")
        self.clear_all_btn.clicked.connect(self._clear_all_history)
        top_bar.addWidget(self.clear_all_btn)

        layout.addLayout(top_bar)

        # ── Summary Cards ──
        cards_layout = QGridLayout()
        cards_layout.setSpacing(8)

        self.card_targets = StatCard(
            self._tr("Targets", "Cibles"), "-", "#88d8b8")
        self.card_time = StatCard(
            self._tr("Total Integration", "Intégration Totale"), "-", "#88b8d8")
        self.card_frames = StatCard(
            self._tr("Total Frames", "Images Totales"), "-", "#d8b888")
        self.card_nights = StatCard(
            self._tr("Observation Nights", "Nuits d'Observation"), "-", "#b888d8")
        self.card_hfr = StatCard(
            self._tr("Average HFR", "HFR Moyen"), "-", "#d88888")
        self.card_telescopes = StatCard(
            self._tr("Telescopes", "Télescopes"), "-", "#88d8d8")

        cards_layout.addWidget(self.card_targets, 0, 0)
        cards_layout.addWidget(self.card_time, 0, 1)
        cards_layout.addWidget(self.card_frames, 0, 2)
        cards_layout.addWidget(self.card_nights, 0, 3)
        cards_layout.addWidget(self.card_hfr, 0, 4)
        cards_layout.addWidget(self.card_telescopes, 0, 5)

        layout.addLayout(cards_layout)

        # ── Sub-Tabs ──
        self.sub_tabs = QTabWidget()
        layout.addWidget(self.sub_tabs, 1)

        # --- Sub-tab 1: Target Rankings ---
        self._create_target_rankings_tab()

        # --- Sub-tab 2: Filter Stats ---
        self._create_filter_stats_tab()

        # --- Sub-tab 3: Equipment Stats ---
        self._create_equipment_stats_tab()

        # --- Sub-tab 4: Temporal Stats ---
        self._create_temporal_stats_tab()

        # --- Sub-tab 5: Best Nights ---
        self._create_best_nights_tab()

        # --- Sub-tab 6: Object Types ---
        self._create_object_types_tab()

    def _create_target_rankings_tab(self):
        """Create the target rankings sub-tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        self.target_table = QTableWidget()
        self.target_table.setToolTip(self._tr(
            "Targets ranked by total integration time",
            "Cibles classées par temps d'intégration total"
        ))
        self.target_table.setColumnCount(9)
        self.target_table.setHorizontalHeaderLabels([
            self._tr("Target", "Cible"),
            self._tr("Type", "Type"),
            self._tr("Telescope", "Télescope"),
            self._tr("Integration", "Intégration"),
            self._tr("Frames", "Images"),
            self._tr("Sessions", "Sessions"),
            self._tr("Filters", "Filtres"),
            self._tr("First Obs", "Première Obs"),
            self._tr("Last Obs", "Dernière Obs"),
        ])
        self.target_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.target_table.setAlternatingRowColors(True)
        self.target_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.target_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.target_table.setSortingEnabled(True)
        layout.addWidget(self.target_table)

        # Action buttons under the table
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        self.delete_target_btn = QPushButton(self._tr(
            "🗑 Delete Selected Targets", "🗑 Supprimer les Cibles Sélectionnées"))
        self.delete_target_btn.setToolTip(self._tr(
            "Delete selected targets and all their observations",
            "Supprimer les cibles sélectionnées et toutes leurs observations"
        ))
        self.delete_target_btn.setStyleSheet("QPushButton { color: #ff6666; }")
        self.delete_target_btn.clicked.connect(self._delete_selected_targets)
        btn_bar.addWidget(self.delete_target_btn)
        layout.addLayout(btn_bar)

        self.sub_tabs.addTab(tab, self._tr("🎯 Target Rankings", "🎯 Classement Cibles"))

    def _create_filter_stats_tab(self):
        """Create the filter statistics sub-tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        self.filter_table = QTableWidget()
        self.filter_table.setToolTip(self._tr(
            "Statistics per filter across all targets",
            "Statistiques par filtre sur toutes les cibles"
        ))
        self.filter_table.setColumnCount(7)
        self.filter_table.setHorizontalHeaderLabels([
            self._tr("Filter", "Filtre"),
            self._tr("Targets", "Cibles"),
            self._tr("Sessions", "Sessions"),
            self._tr("Frames", "Images"),
            self._tr("Integration", "Intégration"),
            self._tr("Avg Sub Exp", "Exp Moy"),
            self._tr("Avg HFR", "HFR Moy"),
        ])
        self.filter_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.filter_table.setAlternatingRowColors(True)
        self.filter_table.setSortingEnabled(True)
        layout.addWidget(self.filter_table)

        self.sub_tabs.addTab(tab, self._tr("🔬 Filters", "🔬 Filtres"))

    def _create_equipment_stats_tab(self):
        """Create the equipment statistics sub-tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        # Equipment type selector
        eq_bar = QHBoxLayout()
        eq_bar.addWidget(QLabel(self._tr("View:", "Vue :")))
        self.equip_combo = QComboBox()
        self.equip_combo.addItem(self._tr("Telescopes", "Télescopes"), "telescope")
        self.equip_combo.addItem(self._tr("Cameras", "Caméras"), "camera")
        self.equip_combo.addItem(self._tr("Setups (Telescope+Camera)", "Setups (Télescope+Caméra)"), "setup")
        self.equip_combo.currentIndexChanged.connect(self._refresh_equipment_table)
        eq_bar.addWidget(self.equip_combo)
        eq_bar.addStretch()
        layout.addLayout(eq_bar)

        self.equip_table = QTableWidget()
        self.equip_table.setToolTip(self._tr(
            "Equipment usage statistics",
            "Statistiques d'utilisation de l'équipement"
        ))
        self.equip_table.setAlternatingRowColors(True)
        self.equip_table.setSortingEnabled(True)
        layout.addWidget(self.equip_table)

        self.sub_tabs.addTab(tab, self._tr("🔭 Equipment", "🔭 Équipement"))

    def _create_temporal_stats_tab(self):
        """Create the temporal statistics sub-tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        # View selector
        temp_bar = QHBoxLayout()
        temp_bar.addWidget(QLabel(self._tr("Period:", "Période :")))
        self.temporal_combo = QComboBox()
        self.temporal_combo.addItem(self._tr("Monthly", "Mensuel"), "monthly")
        self.temporal_combo.addItem(self._tr("Yearly", "Annuel"), "yearly")
        self.temporal_combo.addItem(self._tr("Day of Week", "Jour de la Semaine"), "dow")
        self.temporal_combo.currentIndexChanged.connect(self._refresh_temporal_table)
        temp_bar.addWidget(self.temporal_combo)
        temp_bar.addStretch()
        layout.addLayout(temp_bar)

        self.temporal_table = QTableWidget()
        self.temporal_table.setToolTip(self._tr(
            "Observation statistics over time",
            "Statistiques d'observation dans le temps"
        ))
        self.temporal_table.setAlternatingRowColors(True)
        self.temporal_table.setSortingEnabled(True)
        layout.addWidget(self.temporal_table)

        self.sub_tabs.addTab(tab, self._tr("📅 Temporal", "📅 Temporel"))

    def _create_best_nights_tab(self):
        """Create the best nights sub-tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        # View selector
        nights_bar = QHBoxLayout()
        nights_bar.addWidget(QLabel(self._tr("Rank by:", "Classer par :")))
        self.nights_combo = QComboBox()
        self.nights_combo.addItem(self._tr("Best Quality (HFR)", "Meilleure Qualité (HFR)"), "quality")
        self.nights_combo.addItem(self._tr("Most Productive", "Plus Productives"), "productive")
        self.nights_combo.currentIndexChanged.connect(self._refresh_nights_table)
        nights_bar.addWidget(self.nights_combo)
        nights_bar.addStretch()
        layout.addLayout(nights_bar)

        self.nights_table = QTableWidget()
        self.nights_table.setToolTip(self._tr(
            "Best observation nights",
            "Meilleures nuits d'observation"
        ))
        self.nights_table.setColumnCount(6)
        self.nights_table.setHorizontalHeaderLabels([
            self._tr("Date", "Date"),
            self._tr("Integration", "Intégration"),
            self._tr("Frames", "Images"),
            self._tr("Targets", "Cibles"),
            self._tr("Filters", "Filtres"),
            self._tr("Avg HFR", "HFR Moy"),
        ])
        self.nights_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.nights_table.setAlternatingRowColors(True)
        layout.addWidget(self.nights_table)

        self.sub_tabs.addTab(tab, self._tr("🌙 Best Nights", "🌙 Meilleures Nuits"))

    def _create_object_types_tab(self):
        """Create the object types statistics sub-tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        self.objtype_table = QTableWidget()
        self.objtype_table.setToolTip(self._tr(
            "Statistics by astronomical object type",
            "Statistiques par type d'objet astronomique"
        ))
        self.objtype_table.setColumnCount(5)
        self.objtype_table.setHorizontalHeaderLabels([
            self._tr("Object Type", "Type d'Objet"),
            self._tr("Targets", "Cibles"),
            self._tr("Nights", "Nuits"),
            self._tr("Frames", "Images"),
            self._tr("Integration", "Intégration"),
        ])
        self.objtype_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.objtype_table.setAlternatingRowColors(True)
        self.objtype_table.setSortingEnabled(True)
        layout.addWidget(self.objtype_table)

        self.sub_tabs.addTab(tab, self._tr("🌌 Object Types", "🌌 Types d'Objets"))

    def _connect_signals(self):
        """Connect to global signal bus."""
        signals.analysis_completed.connect(lambda r: self.refresh_all())
        signals.targets_refreshed.connect(self.refresh_all)
        self._maintenance_done_signal.connect(self._on_maintenance_done)

    # =========================================================================
    # Data Refresh
    # =========================================================================

    def refresh_all(self):
        """Refresh all statistics from database.

        On first refresh, runs lightweight maintenance in a background thread
        to avoid blocking the GUI:
        - merge targets that share the same canonical_name (duplicates)
        - fill in missing object_type using catalog classification
        - normalise Greek Unicode chars in filter names
        """
        try:
            from modules.observation_history import get_history
            self._history = get_history()
        except Exception as e:
            logger.error(f"Failed to initialize observation history: {e}")
            return

        # Lightweight cleanup (no-op when nothing to fix) — once per session, in background [PERF]
        if not hasattr(self, '_maintenance_started'):
            self._maintenance_started = True
            def _do_maintenance():
                try:
                    self._history.merge_duplicate_targets()
                    self._history.fix_unknown_object_types()
                    self._history.normalize_filter_names()
                    self._history.normalize_equipment_names()
                except Exception as e:
                    logger.debug(f"Cleanup pass: {e}")
                self._maintenance_done_signal.emit()
            threading.Thread(target=_do_maintenance, daemon=True).start()

        self._refresh_summary_cards()
        self._refresh_target_rankings()
        self._refresh_filter_stats()
        self._refresh_equipment_table()
        self._refresh_temporal_table()
        self._refresh_nights_table()
        self._refresh_object_types()

    def _on_maintenance_done(self):
        """Called when background maintenance finishes — refresh data to reflect any merges."""
        self._refresh_summary_cards()
        self._refresh_target_rankings()

    def _refresh_summary_cards(self):
        """Refresh the summary cards."""
        try:
            stats = self._history.get_global_stats()

            self.card_targets.set_value(str(stats.get('total_targets', 0)))

            total_sec = stats.get('total_integration_seconds', 0) or 0
            self.card_time.set_value(self._format_time(total_sec))

            self.card_frames.set_value(f"{stats.get('total_frames', 0):,}")
            self.card_nights.set_value(str(stats.get('unique_nights', 0)))

            avg_hfr = stats.get('avg_hfr')
            self.card_hfr.set_value(f'{avg_hfr:.2f}"' if avg_hfr else "-")

            self.card_telescopes.set_value(str(stats.get('unique_telescopes', 0)))
        except Exception as e:
            logger.error(f"Error refreshing summary cards: {e}")

    def _refresh_target_rankings(self):
        """Refresh the target rankings table."""
        try:
            rankings = self._history.get_target_rankings(limit=100)
            self.target_table.setSortingEnabled(False)
            self.target_table.setRowCount(len(rankings))

            for i, r in enumerate(rankings):
                name = r.get('canonical_name') or r.get('name', '-')
                name_item = QTableWidgetItem(name)
                # Store target_id for deletion
                name_item.setData(Qt.ItemDataRole.UserRole + 1, r.get('id'))
                self.target_table.setItem(i, 0, name_item)

                # Translate SIMBAD otype code to readable label
                raw_type = r.get('object_type') or ''
                type_label = _translate_otype(raw_type, self.lang) if raw_type else '-'
                self.target_table.setItem(i, 1, QTableWidgetItem(type_label))

                # Equipment (telescopes) used for this target
                telescopes = r.get('telescopes_used') or '-'
                self.target_table.setItem(i, 2, QTableWidgetItem(telescopes))

                time_str = self._format_time(r.get('total_exposure_time', 0))
                item = QTableWidgetItem(time_str)
                item.setData(Qt.ItemDataRole.UserRole,
                             r.get('total_exposure_time', 0))
                self.target_table.setItem(i, 3, item)

                frames_item = QTableWidgetItem(str(r.get('total_frames', 0) or 0))
                frames_item.setData(Qt.ItemDataRole.UserRole,
                                    r.get('total_frames', 0) or 0)
                self.target_table.setItem(i, 4, frames_item)

                sessions_item = QTableWidgetItem(str(r.get('sessions', 0)))
                sessions_item.setData(Qt.ItemDataRole.UserRole,
                                      r.get('sessions', 0))
                self.target_table.setItem(i, 5, sessions_item)

                self.target_table.setItem(i, 6,
                    QTableWidgetItem(str(r.get('filters_used', 0))))
                self.target_table.setItem(i, 7,
                    QTableWidgetItem(str(r.get('first_observed') or '-')))
                self.target_table.setItem(i, 8,
                    QTableWidgetItem(str(r.get('last_observed') or '-')))

            self.target_table.setSortingEnabled(True)
        except Exception as e:
            logger.error(f"Error refreshing target rankings: {e}")

    def _refresh_filter_stats(self):
        """Refresh the filter statistics table."""
        try:
            stats = self._history.get_filter_stats()
            self.filter_table.setSortingEnabled(False)
            self.filter_table.setRowCount(len(stats))

            for i, s in enumerate(stats):
                raw_filt = s.get('filter') or '-'
                self.filter_table.setItem(i, 0,
                    QTableWidgetItem(prettify_filter_name(raw_filt)))

                targets_item = QTableWidgetItem(str(s.get('target_count', 0)))
                targets_item.setData(Qt.ItemDataRole.UserRole,
                                     s.get('target_count', 0))
                self.filter_table.setItem(i, 1, targets_item)

                sessions_item = QTableWidgetItem(str(s.get('session_count', 0)))
                sessions_item.setData(Qt.ItemDataRole.UserRole,
                                      s.get('session_count', 0))
                self.filter_table.setItem(i, 2, sessions_item)

                frames_item = QTableWidgetItem(str(s.get('total_frames', 0) or 0))
                frames_item.setData(Qt.ItemDataRole.UserRole,
                                    s.get('total_frames', 0) or 0)
                self.filter_table.setItem(i, 3, frames_item)

                time_str = self._format_time(s.get('total_time', 0))
                time_item = QTableWidgetItem(time_str)
                time_item.setData(Qt.ItemDataRole.UserRole,
                                  s.get('total_time', 0))
                self.filter_table.setItem(i, 4, time_item)

                avg_sub = s.get('avg_sub_exposure')
                self.filter_table.setItem(i, 5,
                    QTableWidgetItem(f"{avg_sub:.0f}s" if avg_sub else "-"))

                avg_hfr = s.get('avg_hfr')
                hfr_item = QTableWidgetItem(
                    f'{avg_hfr:.2f}"' if avg_hfr else "-")
                if avg_hfr:
                    if avg_hfr < 2.0:
                        hfr_item.setForeground(QColor('#88b098'))
                    elif avg_hfr < 3.0:
                        hfr_item.setForeground(QColor('#b8a880'))
                    else:
                        hfr_item.setForeground(QColor('#b89090'))
                self.filter_table.setItem(i, 6, hfr_item)

            self.filter_table.setSortingEnabled(True)
        except Exception as e:
            logger.error(f"Error refreshing filter stats: {e}")

    def _refresh_equipment_table(self):
        """Refresh the equipment statistics table based on selected type."""
        try:
            equip_type = self.equip_combo.currentData() or "telescope"

            if equip_type == "telescope":
                data = self._history.get_telescope_stats()
                headers = [
                    self._tr("Telescope", "Télescope"),
                    self._tr("Targets", "Cibles"),
                    self._tr("Sessions", "Sessions"),
                    self._tr("Frames", "Images"),
                    self._tr("Integration", "Intégration"),
                    self._tr("Avg HFR", "HFR Moy"),
                    self._tr("Best HFR", "Meilleur HFR"),
                ]
                name_key = 'telescope'
            elif equip_type == "camera":
                data = self._history.get_camera_stats()
                headers = [
                    self._tr("Camera", "Caméra"),
                    self._tr("Targets", "Cibles"),
                    self._tr("Sessions", "Sessions"),
                    self._tr("Frames", "Images"),
                    self._tr("Integration", "Intégration"),
                    self._tr("Avg HFR", "HFR Moy"),
                    self._tr("Best HFR", "Meilleur HFR"),
                ]
                name_key = 'camera'
            else:
                data = self._history.get_setup_stats()
                headers = [
                    self._tr("Telescope", "Télescope"),
                    self._tr("Camera", "Caméra"),
                    self._tr("Targets", "Cibles"),
                    self._tr("Sessions", "Sessions"),
                    self._tr("Frames", "Images"),
                    self._tr("Integration", "Intégration"),
                    self._tr("Avg HFR", "HFR Moy"),
                ]
                name_key = None

            self.equip_table.setSortingEnabled(False)
            self.equip_table.setColumnCount(len(headers))
            self.equip_table.setHorizontalHeaderLabels(headers)
            self.equip_table.horizontalHeader().setSectionResizeMode(
                QHeaderView.ResizeMode.Stretch)
            self.equip_table.setRowCount(len(data))

            for i, row_data in enumerate(data):
                col = 0
                if name_key:
                    self.equip_table.setItem(i, col,
                        QTableWidgetItem(str(row_data.get(name_key) or '-')))
                    col += 1
                else:
                    self.equip_table.setItem(i, col,
                        QTableWidgetItem(str(row_data.get('telescope') or '-')))
                    col += 1
                    self.equip_table.setItem(i, col,
                        QTableWidgetItem(str(row_data.get('camera') or '-')))
                    col += 1

                targets_item = QTableWidgetItem(
                    str(row_data.get('target_count', 0)))
                targets_item.setData(Qt.ItemDataRole.UserRole,
                                     row_data.get('target_count', 0))
                self.equip_table.setItem(i, col, targets_item)
                col += 1

                sessions_item = QTableWidgetItem(
                    str(row_data.get('session_count', 0)))
                sessions_item.setData(Qt.ItemDataRole.UserRole,
                                      row_data.get('session_count', 0))
                self.equip_table.setItem(i, col, sessions_item)
                col += 1

                frames_item = QTableWidgetItem(
                    str(row_data.get('total_frames', 0) or 0))
                frames_item.setData(Qt.ItemDataRole.UserRole,
                                    row_data.get('total_frames', 0) or 0)
                self.equip_table.setItem(i, col, frames_item)
                col += 1

                time_str = self._format_time(row_data.get('total_time', 0))
                time_item = QTableWidgetItem(time_str)
                time_item.setData(Qt.ItemDataRole.UserRole,
                                  row_data.get('total_time', 0))
                self.equip_table.setItem(i, col, time_item)
                col += 1

                avg_hfr = row_data.get('avg_hfr')
                hfr_item = QTableWidgetItem(
                    f'{avg_hfr:.2f}"' if avg_hfr else "-")
                self.equip_table.setItem(i, col, hfr_item)
                col += 1

                if name_key:
                    best_hfr = row_data.get('best_hfr')
                    best_item = QTableWidgetItem(
                        f'{best_hfr:.2f}"' if best_hfr else "-")
                    if best_hfr and best_hfr < 2.0:
                        best_item.setForeground(QColor('#88b098'))
                    self.equip_table.setItem(i, col, best_item)

            self.equip_table.setSortingEnabled(True)
        except Exception as e:
            logger.error(f"Error refreshing equipment stats: {e}")

    def _refresh_temporal_table(self):
        """Refresh the temporal statistics table."""
        try:
            period = self.temporal_combo.currentData() or "monthly"
            dow_names_en = ['Sunday', 'Monday', 'Tuesday', 'Wednesday',
                            'Thursday', 'Friday', 'Saturday']
            dow_names_fr = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi',
                            'Jeudi', 'Vendredi', 'Samedi']

            if period == "monthly":
                data = self._history.get_monthly_stats()
                headers = [
                    self._tr("Month", "Mois"),
                    self._tr("Targets", "Cibles"),
                    self._tr("Nights", "Nuits"),
                    self._tr("Sessions", "Sessions"),
                    self._tr("Frames", "Images"),
                    self._tr("Integration", "Intégration"),
                    self._tr("Avg HFR", "HFR Moy"),
                ]
            elif period == "yearly":
                data = self._history.get_yearly_stats()
                headers = [
                    self._tr("Year", "Année"),
                    self._tr("Targets", "Cibles"),
                    self._tr("Nights", "Nuits"),
                    self._tr("Sessions", "Sessions"),
                    self._tr("Frames", "Images"),
                    self._tr("Integration", "Intégration"),
                    self._tr("Avg HFR", "HFR Moy"),
                ]
            else:
                data = self._history.get_day_of_week_stats()
                headers = [
                    self._tr("Day", "Jour"),
                    self._tr("Nights", "Nuits"),
                    self._tr("Sessions", "Sessions"),
                    self._tr("Frames", "Images"),
                    self._tr("Integration", "Intégration"),
                ]

            self.temporal_table.setSortingEnabled(False)
            self.temporal_table.setColumnCount(len(headers))
            self.temporal_table.setHorizontalHeaderLabels(headers)
            self.temporal_table.horizontalHeader().setSectionResizeMode(
                QHeaderView.ResizeMode.Stretch)
            self.temporal_table.setRowCount(len(data))

            for i, row_data in enumerate(data):
                col = 0

                if period == "dow":
                    dow = row_data.get('dow', 0)
                    names = dow_names_fr if self.lang == 'fr' else dow_names_en
                    self.temporal_table.setItem(i, col,
                        QTableWidgetItem(names[dow] if 0 <= dow < 7 else '?'))
                    col += 1

                    nights_item = QTableWidgetItem(
                        str(row_data.get('nights', 0)))
                    nights_item.setData(Qt.ItemDataRole.UserRole,
                                        row_data.get('nights', 0))
                    self.temporal_table.setItem(i, col, nights_item)
                    col += 1

                    sessions_item = QTableWidgetItem(
                        str(row_data.get('sessions', 0)))
                    sessions_item.setData(Qt.ItemDataRole.UserRole,
                                          row_data.get('sessions', 0))
                    self.temporal_table.setItem(i, col, sessions_item)
                    col += 1

                    frames_item = QTableWidgetItem(
                        str(row_data.get('total_frames', 0) or 0))
                    frames_item.setData(Qt.ItemDataRole.UserRole,
                                        row_data.get('total_frames', 0) or 0)
                    self.temporal_table.setItem(i, col, frames_item)
                    col += 1

                    time_str = self._format_time(row_data.get('total_time', 0))
                    time_item = QTableWidgetItem(time_str)
                    time_item.setData(Qt.ItemDataRole.UserRole,
                                      row_data.get('total_time', 0))
                    self.temporal_table.setItem(i, col, time_item)
                else:
                    period_key = 'month' if period == 'monthly' else 'year'
                    self.temporal_table.setItem(i, col,
                        QTableWidgetItem(str(row_data.get(period_key, '-'))))
                    col += 1

                    targets_item = QTableWidgetItem(
                        str(row_data.get('targets', 0)))
                    targets_item.setData(Qt.ItemDataRole.UserRole,
                                         row_data.get('targets', 0))
                    self.temporal_table.setItem(i, col, targets_item)
                    col += 1

                    nights_item = QTableWidgetItem(
                        str(row_data.get('nights', 0)))
                    nights_item.setData(Qt.ItemDataRole.UserRole,
                                        row_data.get('nights', 0))
                    self.temporal_table.setItem(i, col, nights_item)
                    col += 1

                    sessions_item = QTableWidgetItem(
                        str(row_data.get('sessions', 0)))
                    sessions_item.setData(Qt.ItemDataRole.UserRole,
                                          row_data.get('sessions', 0))
                    self.temporal_table.setItem(i, col, sessions_item)
                    col += 1

                    frames_item = QTableWidgetItem(
                        str(row_data.get('total_frames', 0) or 0))
                    frames_item.setData(Qt.ItemDataRole.UserRole,
                                        row_data.get('total_frames', 0) or 0)
                    self.temporal_table.setItem(i, col, frames_item)
                    col += 1

                    time_str = self._format_time(row_data.get('total_time', 0))
                    time_item = QTableWidgetItem(time_str)
                    time_item.setData(Qt.ItemDataRole.UserRole,
                                      row_data.get('total_time', 0))
                    self.temporal_table.setItem(i, col, time_item)
                    col += 1

                    avg_hfr = row_data.get('avg_hfr')
                    hfr_item = QTableWidgetItem(
                        f'{avg_hfr:.2f}"' if avg_hfr else "-")
                    self.temporal_table.setItem(i, col, hfr_item)

            self.temporal_table.setSortingEnabled(True)
        except Exception as e:
            logger.error(f"Error refreshing temporal stats: {e}")

    def _refresh_nights_table(self):
        """Refresh the best nights table."""
        try:
            ranking = self.nights_combo.currentData() or "quality"

            if ranking == "quality":
                data = self._history.get_best_nights(limit=20)
            else:
                data = self._history.get_most_productive_nights(limit=20)

            self.nights_table.setSortingEnabled(False)
            self.nights_table.setRowCount(len(data))

            for i, row_data in enumerate(data):
                self.nights_table.setItem(i, 0,
                    QTableWidgetItem(str(row_data.get('observation_date', '-'))))

                time_str = self._format_time(row_data.get('total_time', 0))
                time_item = QTableWidgetItem(time_str)
                time_item.setData(Qt.ItemDataRole.UserRole,
                                  row_data.get('total_time', 0))
                self.nights_table.setItem(i, 1, time_item)

                frames_item = QTableWidgetItem(
                    str(row_data.get('total_frames', 0) or 0))
                frames_item.setData(Qt.ItemDataRole.UserRole,
                                    row_data.get('total_frames', 0) or 0)
                self.nights_table.setItem(i, 2, frames_item)

                self.nights_table.setItem(i, 3,
                    QTableWidgetItem(str(row_data.get('targets', 0))))
                self.nights_table.setItem(i, 4,
                    QTableWidgetItem(str(row_data.get('filters') or '-')))

                avg_hfr = row_data.get('avg_hfr')
                hfr_item = QTableWidgetItem(
                    f'{avg_hfr:.2f}"' if avg_hfr else "-")
                if avg_hfr:
                    if avg_hfr < 2.0:
                        hfr_item.setForeground(QColor('#88b098'))
                    elif avg_hfr < 3.0:
                        hfr_item.setForeground(QColor('#b8a880'))
                    else:
                        hfr_item.setForeground(QColor('#b89090'))
                self.nights_table.setItem(i, 5, hfr_item)

            self.nights_table.setSortingEnabled(True)
        except Exception as e:
            logger.error(f"Error refreshing best nights: {e}")

    def _refresh_object_types(self):
        """Refresh the object types table."""
        try:
            data = self._history.get_object_type_stats()
            self.objtype_table.setSortingEnabled(False)
            self.objtype_table.setRowCount(len(data))

            for i, row_data in enumerate(data):
                raw_type = row_data.get('object_type') or ''
                type_label = _translate_otype(raw_type, self.lang) if raw_type else '-'
                self.objtype_table.setItem(i, 0, QTableWidgetItem(type_label))

                targets_item = QTableWidgetItem(
                    str(row_data.get('target_count', 0)))
                targets_item.setData(Qt.ItemDataRole.UserRole,
                                     row_data.get('target_count', 0))
                self.objtype_table.setItem(i, 1, targets_item)

                nights_item = QTableWidgetItem(
                    str(row_data.get('nights', 0) or 0))
                nights_item.setData(Qt.ItemDataRole.UserRole,
                                    row_data.get('nights', 0) or 0)
                self.objtype_table.setItem(i, 2, nights_item)

                frames_item = QTableWidgetItem(
                    str(row_data.get('total_frames', 0) or 0))
                frames_item.setData(Qt.ItemDataRole.UserRole,
                                    row_data.get('total_frames', 0) or 0)
                self.objtype_table.setItem(i, 3, frames_item)

                time_str = self._format_time(row_data.get('total_time', 0))
                time_item = QTableWidgetItem(time_str)
                time_item.setData(Qt.ItemDataRole.UserRole,
                                  row_data.get('total_time', 0))
                self.objtype_table.setItem(i, 4, time_item)

            self.objtype_table.setSortingEnabled(True)
        except Exception as e:
            logger.error(f"Error refreshing object type stats: {e}")

    # =========================================================================
    # Export / Import Actions
    # =========================================================================

    def _export_json(self):
        """Export history to JSON file."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("Export History (JSON)", "Exporter Historique (JSON)"),
            f"astromanager_history_{datetime.now().strftime('%Y%m%d')}.json",
            "JSON Files (*.json)"
        )
        if not path:
            return

        try:
            from modules.observation_history import get_history
            history = get_history()
            count = history.export_to_json(path)
            QMessageBox.information(self,
                self._tr("Export", "Export"),
                self._tr(
                    f"Successfully exported {count} targets to:\n{path}",
                    f"{count} cibles exportées avec succès vers :\n{path}"
                ))
        except Exception as e:
            QMessageBox.warning(self,
                self._tr("Export Error", "Erreur d'Export"),
                str(e))

    def _export_csv(self):
        """Export observations to CSV file."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("Export Observations (CSV)", "Exporter Observations (CSV)"),
            f"astromanager_observations_{datetime.now().strftime('%Y%m%d')}.csv",
            "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            from modules.observation_history import get_history
            history = get_history()
            count = history.export_to_csv(path)
            QMessageBox.information(self,
                self._tr("Export", "Export"),
                self._tr(
                    f"Successfully exported {count} observation records to:\n{path}",
                    f"{count} enregistrements d'observation exportés vers :\n{path}"
                ))
        except Exception as e:
            QMessageBox.warning(self,
                self._tr("Export Error", "Erreur d'Export"),
                str(e))

    def _import_json(self):
        """Import history from JSON file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._tr("Import History (JSON)", "Importer Historique (JSON)"),
            "",
            "JSON Files (*.json)"
        )
        if not path:
            return

        reply = QMessageBox.question(self,
            self._tr("Confirm Import", "Confirmer l'Import"),
            self._tr(
                "Import will merge data with existing history. "
                "Existing targets with the same name will be updated. Continue?",
                "L'import fusionnera les données avec l'historique existant. "
                "Les cibles existantes avec le même nom seront mises à jour. Continuer ?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            from modules.observation_history import get_history
            history = get_history()
            targets, obs = history.import_from_json(path)
            self.refresh_all()
            signals.targets_refreshed.emit()
            QMessageBox.information(self,
                self._tr("Import", "Import"),
                self._tr(
                    f"Successfully imported {targets} targets and {obs} observations.",
                    f"{targets} cibles et {obs} observations importées avec succès."
                ))
        except Exception as e:
            QMessageBox.warning(self,
                self._tr("Import Error", "Erreur d'Import"),
                str(e))

    def _import_csv(self):
        """Import observations from CSV file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._tr("Import Observations (CSV)", "Importer Observations (CSV)"),
            "",
            "CSV Files (*.csv)"
        )
        if not path:
            return

        reply = QMessageBox.question(self,
            self._tr("Confirm Import", "Confirmer l'Import"),
            self._tr(
                "Import will add observations to existing history. Continue?",
                "L'import ajoutera les observations à l'historique existant. Continuer ?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            from modules.observation_history import get_history
            history = get_history()
            targets, obs = history.import_from_csv(path)
            self.refresh_all()
            signals.targets_refreshed.emit()
            QMessageBox.information(self,
                self._tr("Import", "Import"),
                self._tr(
                    f"Successfully imported {targets} targets and {obs} observations.",
                    f"{targets} cibles et {obs} observations importées avec succès."
                ))
        except Exception as e:
            QMessageBox.warning(self,
                self._tr("Import Error", "Erreur d'Import"),
                str(e))

    # =========================================================================
    # Delete / Clear Actions
    # =========================================================================

    def _delete_selected_targets(self):
        """Delete selected targets and all their observations."""
        selected_rows = self.target_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self,
                self._tr("Info", "Info"),
                self._tr(
                    "Select one or more targets in the table first.",
                    "Sélectionnez d'abord une ou plusieurs cibles dans le tableau."
                ))
            return

        # Collect target names and IDs
        targets_to_delete = []
        for idx in selected_rows:
            row = idx.row()
            name_item = self.target_table.item(row, 0)
            if name_item:
                target_id = name_item.data(Qt.ItemDataRole.UserRole + 1)
                name = name_item.text()
                if target_id is not None:
                    targets_to_delete.append((target_id, name))

        if not targets_to_delete:
            return

        names_preview = '\n'.join(f"  - {name}" for _, name in targets_to_delete[:10])
        if len(targets_to_delete) > 10:
            names_preview += f"\n  ... (+{len(targets_to_delete) - 10})"

        reply = QMessageBox.warning(self,
            self._tr("Confirm Deletion", "Confirmer la Suppression"),
            self._tr(
                f"Delete {len(targets_to_delete)} target(s) and ALL their observations?\n\n"
                f"{names_preview}\n\nThis cannot be undone.",
                f"Supprimer {len(targets_to_delete)} cible(s) et TOUTES leurs observations ?\n\n"
                f"{names_preview}\n\nCette action est irréversible."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            from core.database import get_db
            db = get_db()
            for target_id, _ in targets_to_delete:
                db.delete_target(target_id)
            self.refresh_all()
            signals.targets_refreshed.emit()
        except Exception as e:
            QMessageBox.warning(self,
                self._tr("Error", "Erreur"), str(e))

    def _clear_all_history(self):
        """Delete all observation history."""
        reply = QMessageBox.warning(self,
            self._tr("Confirm Clear All", "Confirmer la Suppression Totale"),
            self._tr(
                "This will permanently delete ALL targets and ALL observations.\n\n"
                "This cannot be undone. Continue?",
                "Ceci supprimera définitivement TOUTES les cibles et TOUTES les observations.\n\n"
                "Cette action est irréversible. Continuer ?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Double confirmation for destructive action
        reply2 = QMessageBox.warning(self,
            self._tr("Are you sure?", "Êtes-vous sûr ?"),
            self._tr(
                "Really delete everything? Last chance!",
                "Vraiment tout supprimer ? Dernière chance !"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply2 != QMessageBox.StandardButton.Yes:
            return

        try:
            from core.database import get_db
            db = get_db()
            db.delete_all_history()
            self.refresh_all()
            signals.targets_refreshed.emit()
            QMessageBox.information(self,
                self._tr("Done", "Terminé"),
                self._tr(
                    "All observation history has been cleared.",
                    "Tout l'historique d'observations a été effacé."
                ))
        except Exception as e:
            QMessageBox.warning(self,
                self._tr("Error", "Erreur"), str(e))
