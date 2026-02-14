#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - TARGET TRACKING TAB
================================================================================
Historical observation timeline, integration time tracking, equipment stats,
SIMBAD data, weather conditions for best sessions.
================================================================================
"""

import json
import threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QTextEdit, QTabWidget, QAbstractItemView,
    QMessageBox, QSpinBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont

from core.signals import signals
from core.config import get_config
from core.database import get_db


class TargetTrackingTab(QWidget):
    """Target Tracking tab - Historical observation data per target"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self.lang = self.config.get('application.language', 'auto')
        if self.lang == 'auto':
            import locale
            try:
                loc = locale.getdefaultlocale()[0]
                self.lang = 'fr' if loc and loc.lower().startswith('fr') else 'en'
            except Exception:
                self.lang = 'en'
        self.current_target = None
        self._last_analysis_results = None
        self._init_ui()
        self._connect_signals()

    def _tr(self, en, fr):
        return fr if self.lang == 'fr' else en

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Target Selection ──
        select_group = QGroupBox(self._tr("🎯 Target Selection", "🎯 Sélection Cible"))
        select_layout = QHBoxLayout(select_group)

        select_layout.addWidget(QLabel(self._tr("Target:", "Cible:")))
        self.target_combo = QComboBox()
        self.target_combo.setToolTip(self._tr(
            "Select a target to view its observation history",
            "Sélectionner une cible pour voir son historique d'observation"
        ))
        self.target_combo.setMinimumWidth(300)
        self.target_combo.setMinimumHeight(32)
        self.target_combo.setEditable(True)
        self.target_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.target_combo.lineEdit().setPlaceholderText(
            self._tr("Type to search or click to select...",
                      "Tapez pour chercher ou cliquez pour sélectionner..."))
        self.target_combo.setStyleSheet("""
            QComboBox {
                padding: 4px 8px;
                font-size: 11pt;
                border: 2px solid #4a5568;
                border-radius: 4px;
            }
            QComboBox:hover, QComboBox:focus {
                border-color: #94b8c8;
            }
            QComboBox::drop-down {
                width: 30px;
                border-left: 1px solid #4a5568;
            }
        """)
        self.target_combo.setMaxVisibleItems(20)
        self.target_combo.currentTextChanged.connect(self._on_target_selected)
        select_layout.addWidget(self.target_combo, 1)

        self.refresh_btn = QPushButton(self._tr("🔄 Refresh", "🔄 Actualiser"))
        self.refresh_btn.setToolTip(self._tr(
            "Refresh target list from database",
            "Rafraîchir la liste des cibles depuis la base de données"
        ))
        self.refresh_btn.clicked.connect(self._load_targets)
        select_layout.addWidget(self.refresh_btn)

        self.import_btn = QPushButton(self._tr("📥 Import from Analysis", "📥 Importer depuis Analyse"))
        self.import_btn.setToolTip(self._tr(
            "Import observation data from analysis results",
            "Importer les données d'observation depuis les résultats d'analyse"
        ))
        self.import_btn.setProperty("accent", True)
        self.import_btn.clicked.connect(self._import_from_analysis)
        select_layout.addWidget(self.import_btn)

        self.simbad_btn = QPushButton(self._tr("🔭 Resolve SIMBAD", "🔭 Résoudre SIMBAD"))
        self.simbad_btn.setToolTip(self._tr(
            "Query SIMBAD for the selected target to get coordinates, type, and canonical name",
            "Interroger SIMBAD pour la cible sélectionnée afin d'obtenir coordonnées, type et nom canonique"
        ))
        self.simbad_btn.clicked.connect(self._resolve_simbad_for_target)
        select_layout.addWidget(self.simbad_btn)

        select_layout.addStretch()
        layout.addWidget(select_group)

        # ── Sub-Tabs ──
        self.sub_tabs = QTabWidget()
        layout.addWidget(self.sub_tabs, 1)

        # --- Sub-tab 1: Info & Stats ---
        info_tab = QWidget()
        info_layout = QVBoxLayout(info_tab)
        info_layout.setSpacing(8)
        info_layout.setContentsMargins(6, 6, 6, 6)

        # Target Info labels
        self.lbl_name = QLabel("-")
        self.lbl_type = QLabel("-")
        self.lbl_coords = QLabel("-")
        self.lbl_canonical = QLabel("-")

        for label_text, value_label in [
            (self._tr("Name:", "Nom :"), self.lbl_name),
            (self._tr("Type:", "Type :"), self.lbl_type),
            (self._tr("Coordinates:", "Coordonnées :"), self.lbl_coords),
            (self._tr("SIMBAD Name:", "Nom SIMBAD :"), self.lbl_canonical),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #94b8c8; font-weight: bold;")
            lbl.setMinimumWidth(120)
            row.addWidget(lbl)
            value_label.setWordWrap(True)
            row.addWidget(value_label, 1)
            info_layout.addLayout(row)

        # Separator between info and stats
        info_layout.addSpacing(4)

        # Statistics labels
        self.stats_labels = {}
        stats_data = [
            ('total_time', self._tr("Total Integration:", "Intégration Totale :")),
            ('total_frames', self._tr("Total Frames:", "Images Totales :")),
            ('sessions', self._tr("Sessions:", "Sessions :")),
            ('first_obs', self._tr("First Observed:", "Première Obs. :")),
            ('last_obs', self._tr("Last Observed:", "Dernière Obs. :")),
            ('best_hfr', self._tr("Best HFR:", "Meilleur HFR :")),
        ]

        for key, label_text in stats_data:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #a8a0c0; font-weight: bold;")
            lbl.setMinimumWidth(130)
            val = QLabel("-")
            self.stats_labels[key] = val
            row.addWidget(lbl)
            row.addWidget(val, 1)
            info_layout.addLayout(row)

        # Separator between stats and filter table
        info_layout.addSpacing(4)

        # Filter Breakdown table
        self.filter_table = QTableWidget()
        self.filter_table.setToolTip(self._tr(
            "Filter integration breakdown for selected target",
            "Détail d'intégration par filtre pour la cible sélectionnée"
        ))
        self.filter_table.setColumnCount(4)
        self.filter_table.setHorizontalHeaderLabels([
            self._tr("Filter", "Filtre"),
            self._tr("Frames", "Img."),
            self._tr("Time", "Temps"),
            self._tr("Avg Exp", "Exp Moy"),
        ])
        self.filter_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.filter_table.setAlternatingRowColors(True)
        info_layout.addWidget(self.filter_table, 1)

        self.sub_tabs.addTab(info_tab, self._tr("📋 Info & Stats", "📋 Info & Stats"))

        # --- Sub-tab 2: History ---
        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        history_layout.setSpacing(8)
        history_layout.setContentsMargins(6, 6, 6, 6)

        # Observation History table
        self.history_table = QTableWidget()
        self.history_table.setToolTip(self._tr(
            "Observation sessions history for selected target",
            "Historique des sessions d'observation pour la cible sélectionnée"
        ))
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels([
            self._tr("Date", "Date"),
            self._tr("Filter", "Filtre"),
            self._tr("Frames", "Images"),
            self._tr("Exposure", "Exposition"),
            self._tr("Setup", "Setup"),
            self._tr("HFR", "HFR"),
            self._tr("Weather", "Météo"),
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        history_layout.addWidget(self.history_table, 1)

        # Notes
        self.notes_text = QTextEdit()
        self.notes_text.setToolTip(self._tr(
            "Personal notes about this target",
            "Notes personnelles sur cette cible"
        ))
        self.notes_text.setMaximumHeight(80)
        self.notes_text.setPlaceholderText(self._tr(
            "Select a session above to view notes...",
            "Sélectionnez une session ci-dessus pour voir les notes..."
        ))
        history_layout.addWidget(self.notes_text)

        self.sub_tabs.addTab(history_tab, self._tr("📅 History", "📅 Historique"))

        # --- Sub-tab 3: Forecast ---
        forecast_tab = QWidget()
        forecast_layout = QVBoxLayout(forecast_tab)
        forecast_layout.setSpacing(8)
        forecast_layout.setContentsMargins(6, 6, 6, 6)

        # Controls row
        fc_controls = QHBoxLayout()
        fc_controls.addWidget(QLabel(self._tr("Forecast days:", "Jours de prévision :")))
        self.forecast_days_spin = QSpinBox()
        self.forecast_days_spin.setToolTip(self._tr(
            "Number of forecast days (1-7)",
            "Nombre de jours de prévision (1-7)"
        ))
        self.forecast_days_spin.setRange(1, 7)
        self.forecast_days_spin.setValue(3)
        fc_controls.addWidget(self.forecast_days_spin)

        self.forecast_btn = QPushButton(self._tr("🌤️ Get Forecast", "🌤️ Obtenir Prévisions"))
        self.forecast_btn.setToolTip(self._tr(
            "Fetch weather forecast and target visibility",
            "Récupérer les prévisions météo et la visibilité de la cible"
        ))
        self.forecast_btn.setProperty("accent", True)
        self.forecast_btn.clicked.connect(self._fetch_forecast)
        fc_controls.addWidget(self.forecast_btn)
        fc_controls.addStretch()
        forecast_layout.addLayout(fc_controls)

        # Forecast table
        self.forecast_table = QTableWidget()
        self.forecast_table.setToolTip(self._tr(
            "Weather forecast and target visibility for upcoming nights",
            "Prévisions météo et visibilité de la cible pour les prochaines nuits"
        ))
        self.forecast_table.setColumnCount(7)
        self.forecast_table.setHorizontalHeaderLabels([
            self._tr("Night", "Nuit"),
            self._tr("Clouds %", "Nuages %"),
            self._tr("Temp °C", "Temp °C"),
            self._tr("Wind km/h", "Vent km/h"),
            self._tr("Score", "Score"),
            self._tr("Clear Hours", "Heures Claires"),
            self._tr("Visibility", "Visibilité"),
        ])
        self.forecast_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.forecast_table.setAlternatingRowColors(True)
        forecast_layout.addWidget(self.forecast_table, 1)

        self.sub_tabs.addTab(forecast_tab, self._tr("🌤️ Forecast", "🌤️ Prévisions"))

        # ── Bottom Buttons ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.export_btn = QPushButton(self._tr("📄 Export Summary", "📄 Exporter Résumé"))
        self.export_btn.setToolTip(self._tr(
            "Export target observation summary",
            "Exporter le résumé d'observation de la cible"
        ))
        self.export_btn.clicked.connect(self._export_summary)
        btn_layout.addWidget(self.export_btn)

        self.delete_btn = QPushButton(self._tr("🗑️ Delete Target", "🗑️ Supprimer Cible"))
        self.delete_btn.setToolTip(self._tr(
            "Delete selected target from database",
            "Supprimer la cible sélectionnée de la base de données"
        ))
        self.delete_btn.setProperty("danger", True)
        self.delete_btn.clicked.connect(self._delete_target)
        btn_layout.addWidget(self.delete_btn)

        layout.addLayout(btn_layout)

        # Load targets on startup
        self._load_targets()

    def _connect_signals(self):
        """Connect to global signal bus"""
        signals.analysis_completed.connect(self._on_analysis_completed)
        signals.targets_refreshed.connect(self._load_targets)

    def _load_targets(self):
        """Load target list from database"""
        try:
            db = get_db()
            targets = db.get_all_targets()
            self.target_combo.blockSignals(True)
            self.target_combo.clear()
            self.target_combo.addItem(self._tr("-- Select Target --", "-- Sélectionner Cible --"))
            for t in targets:
                display = t['canonical_name'] or t['name']
                self.target_combo.addItem(display, t['id'])
            self.target_combo.blockSignals(False)
        except Exception:
            pass

    def _on_target_selected(self, text):
        """Handle target selection"""
        idx = self.target_combo.currentIndex()
        if idx <= 0:
            self._clear_display()
            return

        target_id = self.target_combo.currentData()
        if target_id is None:
            return

        try:
            db = get_db()
            # Get target info
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM targets WHERE id = ?", (target_id,))
                target = cursor.fetchone()
                if not target:
                    return
                target = dict(target)

            self.current_target = target
            self._display_target_info(target)

            # Get observations
            observations = db.get_observations(target_id)
            self._display_observations(observations)
            self._compute_filter_breakdown(observations)
            self._compute_stats(target, observations)

        except Exception as e:
            self.notes_text.setText(f"Error loading target: {e}")

    def _display_target_info(self, target):
        """Display target information"""
        self.lbl_name.setText(target['name'])
        self.lbl_type.setText(target.get('object_type') or '-')
        self.lbl_canonical.setText(target.get('canonical_name') or '-')

        ra = target.get('ra')
        dec = target.get('dec')
        if ra is not None and dec is not None:
            self.lbl_coords.setText(f"RA: {ra:.4f}  Dec: {dec:.4f}")
        else:
            self.lbl_coords.setText("-")

    def _display_observations(self, observations):
        """Display observation history table"""
        self.history_table.setRowCount(len(observations))

        for i, obs in enumerate(observations):
            self.history_table.setItem(i, 0, QTableWidgetItem(str(obs.get('observation_date', ''))))
            from gui.theme import prettify_filter_name as _pfn
            self.history_table.setItem(i, 1, QTableWidgetItem(_pfn(str(obs.get('filter', '-')))))

            frames = obs.get('frame_count', 0) or 0
            self.history_table.setItem(i, 2, QTableWidgetItem(str(frames)))

            exp = obs.get('exposure_time', 0) or 0
            if exp >= 3600:
                exp_str = f"{exp/3600:.1f}h"
            elif exp >= 60:
                exp_str = f"{exp/60:.0f}m"
            else:
                exp_str = f"{exp:.0f}s"
            self.history_table.setItem(i, 3, QTableWidgetItem(exp_str))

            self.history_table.setItem(i, 4, QTableWidgetItem(str(obs.get('setup', '-'))))

            hfr = obs.get('hfr')
            hfr_item = QTableWidgetItem(f"{hfr:.2f}" if hfr else "-")
            if hfr and hfr < 2.0:
                hfr_item.setForeground(QColor('#88b098'))
            elif hfr and hfr < 3.0:
                hfr_item.setForeground(QColor('#b8a880'))
            elif hfr:
                hfr_item.setForeground(QColor('#b89090'))
            self.history_table.setItem(i, 5, hfr_item)

            # Weather
            weather_str = "-"
            weather_data = obs.get('weather_data')
            if weather_data:
                try:
                    wd = json.loads(weather_data) if isinstance(weather_data, str) else weather_data
                    weather_str = wd.get('classification', '-')
                except (json.JSONDecodeError, AttributeError):
                    pass
            self.history_table.setItem(i, 6, QTableWidgetItem(weather_str))

    def _compute_filter_breakdown(self, observations):
        """Compute per-filter statistics"""
        filters = {}
        for obs in observations:
            f = obs.get('filter', 'Unknown') or 'Unknown'
            if f not in filters:
                filters[f] = {'frames': 0, 'time': 0.0, 'count': 0}
            filters[f]['frames'] += (obs.get('frame_count', 0) or 0)
            filters[f]['time'] += (obs.get('exposure_time', 0) or 0)
            filters[f]['count'] += 1

        self.filter_table.setRowCount(len(filters))
        for i, (fname, data) in enumerate(sorted(filters.items())):
            from gui.theme import prettify_filter_name as _pfn
            self.filter_table.setItem(i, 0, QTableWidgetItem(_pfn(fname)))
            self.filter_table.setItem(i, 1, QTableWidgetItem(str(data['frames'])))

            total_time = data['time']
            if total_time >= 3600:
                time_str = f"{total_time/3600:.1f}h"
            else:
                time_str = f"{total_time/60:.0f}m"
            self.filter_table.setItem(i, 2, QTableWidgetItem(time_str))

            avg_exp = total_time / data['frames'] if data['frames'] > 0 else 0
            self.filter_table.setItem(i, 3, QTableWidgetItem(f"{avg_exp:.0f}s"))

    def _compute_stats(self, target, observations):
        """Compute overall statistics"""
        total_time = target.get('total_exposure_time', 0) or 0
        total_frames = target.get('total_frames', 0) or 0

        if total_time >= 3600:
            time_str = f"{total_time/3600:.1f} {self._tr('hours', 'heures')}"
        else:
            time_str = f"{total_time/60:.0f} {self._tr('minutes', 'minutes')}"

        self.stats_labels['total_time'].setText(time_str)
        self.stats_labels['total_frames'].setText(str(total_frames))
        self.stats_labels['sessions'].setText(str(len(observations)))
        self.stats_labels['first_obs'].setText(str(target.get('first_observed', '-')))
        self.stats_labels['last_obs'].setText(str(target.get('last_observed', '-')))

        # Best HFR
        hfrs = [obs.get('hfr') for obs in observations if obs.get('hfr')]
        if hfrs:
            best_hfr = min(hfrs)
            self.stats_labels['best_hfr'].setText(f'{best_hfr:.2f}"')
        else:
            self.stats_labels['best_hfr'].setText("-")

    def _clear_display(self):
        """Clear all display fields"""
        self.lbl_name.setText("-")
        self.lbl_type.setText("-")
        self.lbl_coords.setText("-")
        self.lbl_canonical.setText("-")
        for lbl in self.stats_labels.values():
            lbl.setText("-")
        self.filter_table.setRowCount(0)
        self.history_table.setRowCount(0)
        self.notes_text.clear()
        self.current_target = None

    def _on_analysis_completed(self, results):
        """Store analysis results for manual import"""
        if not results or 'data_by_target' not in results:
            return
        self._last_analysis_results = results

    def _import_from_analysis(self):
        """Manual import from last analysis results"""
        if not self._last_analysis_results or 'data_by_target' not in self._last_analysis_results:
            QMessageBox.information(self, self._tr("Info", "Info"),
                self._tr(
                    "No analysis results available. Run an analysis first (Analysis tab).",
                    "Aucun résultat d'analyse disponible. Lancez d'abord une analyse (onglet Analyse)."
                ))
            return
        self._import_analysis_results(self._last_analysis_results)

    def _import_analysis_results(self, results):
        """Import targets and observations from analysis results"""
        data_by_target = results.get('data_by_target', {})
        if not data_by_target:
            QMessageBox.warning(self, self._tr("Import", "Import"),
                self._tr("No target data found in analysis results.",
                         "Aucune donnée de cible trouvée dans les résultats d'analyse."))
            return

        db = get_db()
        imported = 0
        obs_count = 0

        for target_name, target_data in data_by_target.items():
            try:
                # Get SIMBAD info if available
                simbad_info = target_data.get('simbad_info', {})
                canonical = simbad_info.get('main_id')
                ra = simbad_info.get('ra')
                dec = simbad_info.get('dec')
                obj_type = simbad_info.get('otype')

                target_id = db.add_target(
                    name=target_name,
                    canonical_name=canonical,
                    ra=ra, dec=dec,
                    object_type=obj_type,
                    simbad_data=simbad_info if simbad_info else None
                )

                # Build observations from files_by_date structure
                # Structure: {date: {time_by_filter: {filter: [exp1, exp2, ...]}, total_time: ...}}
                files_by_date = target_data.get('files_by_date', {})

                # Get equipment info from target-level sets
                telescopes = target_data.get('telescopes', set())
                instruments = target_data.get('instruments', set())
                telescope_str = ', '.join(sorted(telescopes)) if isinstance(telescopes, (set, frozenset)) else str(telescopes or '')
                camera_str = ', '.join(sorted(instruments)) if isinstance(instruments, (set, frozenset)) else str(instruments or '')
                setup_str = f"{telescope_str} + {camera_str}" if telescope_str and camera_str else telescope_str or camera_str or ''

                for date, date_data in files_by_date.items():
                    time_by_filter = date_data.get('time_by_filter', {})
                    for filter_name, exposures in time_by_filter.items():
                        if not exposures:
                            continue
                        total_exp = sum(exposures)
                        frame_count = len(exposures)
                        obs_date = str(date)[:10] if date else ''
                        if not obs_date:
                            continue

                        # Dedup: delete matching observation before insert
                        with db.get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                DELETE FROM observations
                                WHERE target_id = ?
                                  AND observation_date = ?
                                  AND COALESCE(filter, '') = ?
                                  AND COALESCE(telescope, '') = ?
                                  AND COALESCE(camera, '') = ?
                            """, (target_id, obs_date, filter_name or '',
                                  telescope_str or '', camera_str or ''))

                        db.add_observation(
                            target_id=target_id,
                            observation_date=obs_date,
                            filter_name=filter_name,
                            exposure_time=total_exp,
                            frame_count=frame_count,
                            setup=setup_str,
                            telescope=telescope_str,
                            camera=camera_str,
                        )
                        obs_count += 1

                imported += 1
            except Exception as e:
                print(f"  ⚠️ Error importing target '{target_name}': {e}")
                continue

        if imported > 0:
            self._load_targets()
            signals.targets_refreshed.emit()
            QMessageBox.information(self, self._tr("Import", "Import"),
                self._tr(
                    f"Imported {imported} targets with {obs_count} observation records.",
                    f"{imported} cibles importées avec {obs_count} enregistrements d'observation."
                ))
        else:
            QMessageBox.warning(self, self._tr("Import", "Import"),
                self._tr(
                    "No targets could be imported from analysis results.",
                    "Aucune cible n'a pu être importée depuis les résultats d'analyse."
                ))

    def _resolve_simbad_for_target(self):
        """Resolve SIMBAD data for the currently selected target"""
        if not self.current_target:
            QMessageBox.information(self, self._tr("SIMBAD", "SIMBAD"),
                self._tr("Select a target first.", "Sélectionnez d'abord une cible."))
            return

        target_name = self.current_target['name']
        self.simbad_btn.setEnabled(False)
        self.simbad_btn.setText(self._tr("⏳ Querying...", "⏳ Requête..."))

        def _do_resolve():
            try:
                import fits_analyser_gui as fag
                if not getattr(fag, 'SIMBAD_AVAILABLE', False):
                    QTimer.singleShot(0, lambda: self._on_simbad_error(
                        self._tr("SIMBAD not available (install astroquery)",
                                 "SIMBAD non disponible (installer astroquery)")))
                    return

                main_id, info = fag._query_simbad_single(target_name)
                if main_id and info:
                    QTimer.singleShot(0, lambda: self._on_simbad_result(info))
                else:
                    QTimer.singleShot(0, lambda: self._on_simbad_error(
                        self._tr(f"No SIMBAD match for '{target_name}'",
                                 f"Aucun résultat SIMBAD pour '{target_name}'")))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_simbad_error(str(e)))

        threading.Thread(target=_do_resolve, daemon=True).start()

    def _on_simbad_result(self, info):
        """Handle successful SIMBAD resolution"""
        self.simbad_btn.setEnabled(True)
        self.simbad_btn.setText(self._tr("🔭 Resolve SIMBAD", "🔭 Résoudre SIMBAD"))

        if not self.current_target:
            return

        target_id = self.current_target['id']
        db = get_db()

        # Update target with SIMBAD data
        db.add_target(
            name=self.current_target['name'],
            canonical_name=info.get('main_id'),
            ra=info.get('ra'),
            dec=info.get('dec'),
            object_type=info.get('otype'),
            simbad_data=info,
        )

        # Refresh display
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM targets WHERE id = ?", (target_id,))
            target = cursor.fetchone()
            if target:
                self.current_target = dict(target)
                self._display_target_info(self.current_target)

        QMessageBox.information(self, self._tr("SIMBAD", "SIMBAD"),
            self._tr(
                f"SIMBAD resolved: {info.get('main_id', '?')} ({info.get('otype', '?')})",
                f"SIMBAD résolu : {info.get('main_id', '?')} ({info.get('otype', '?')})"
            ))

    def _on_simbad_error(self, msg):
        """Handle SIMBAD resolution error"""
        self.simbad_btn.setEnabled(True)
        self.simbad_btn.setText(self._tr("🔭 Resolve SIMBAD", "🔭 Résoudre SIMBAD"))
        QMessageBox.warning(self, self._tr("SIMBAD", "SIMBAD"), msg)

    def _fetch_forecast(self):
        """Fetch weather forecast and target visibility"""
        config = get_config()
        lat = config.get('observatory.latitude', 51.4769)
        lon = config.get('observatory.longitude', -0.0005)
        days = self.forecast_days_spin.value()

        self.forecast_btn.setEnabled(False)
        self.forecast_btn.setText(self._tr("⏳ Loading...", "⏳ Chargement..."))

        def _do_fetch():
            try:
                from modules.weather_api import WeatherAPIClient
                client = WeatherAPIClient()
                forecast = client.fetch_forecast(lat, lon, days=days)

                # Compute target visibility if a target is selected
                visibility = {}
                if (self.current_target and
                        self.current_target.get('ra') is not None and
                        self.current_target.get('dec') is not None):
                    ra = self.current_target['ra']
                    dec = self.current_target['dec']
                    if forecast:
                        for night in forecast:
                            date_str = night.get('night_date', '')
                            if date_str:
                                vis = WeatherAPIClient.compute_target_visibility(
                                    ra, dec, lat, lon, date_str)
                                visibility[date_str] = vis

                QTimer.singleShot(0, lambda: self._display_forecast(forecast, visibility))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_forecast_error(str(e)))

        threading.Thread(target=_do_fetch, daemon=True).start()

    def _display_forecast(self, forecast, visibility):
        """Display forecast results in table"""
        self.forecast_btn.setEnabled(True)
        self.forecast_btn.setText(self._tr("🌤️ Get Forecast", "🌤️ Obtenir Prévisions"))

        if not forecast:
            self.forecast_table.setRowCount(1)
            self.forecast_table.setItem(0, 0, QTableWidgetItem(
                self._tr("No forecast data available", "Aucune donnée de prévision disponible")))
            return

        self.forecast_table.setRowCount(len(forecast))
        for i, night in enumerate(forecast):
            date_str = night.get('night_date', '-')
            self.forecast_table.setItem(i, 0, QTableWidgetItem(date_str))

            # Clouds
            clouds = night.get('cloud_cover_pct', 0) or 0
            cloud_item = QTableWidgetItem(f"{clouds:.0f}%")
            if clouds <= 10:
                cloud_item.setForeground(QColor('#88b098'))
            elif clouds <= 25:
                cloud_item.setForeground(QColor('#88b8a0'))
            elif clouds <= 50:
                cloud_item.setForeground(QColor('#b8a880'))
            else:
                cloud_item.setForeground(QColor('#b89090'))
            self.forecast_table.setItem(i, 1, cloud_item)

            # Temperature
            temp = night.get('temperature_c', 0) or 0
            self.forecast_table.setItem(i, 2, QTableWidgetItem(f"{temp:.1f}"))

            # Wind
            wind = night.get('wind_speed_kmh', 0) or 0
            wind_item = QTableWidgetItem(f"{wind:.0f}")
            if wind > 30:
                wind_item.setForeground(QColor('#b89090'))
            elif wind > 20:
                wind_item.setForeground(QColor('#b8a880'))
            self.forecast_table.setItem(i, 3, wind_item)

            # Score
            score = night.get('imaging_score', 0)
            score_item = QTableWidgetItem(f"{score}/100")
            if score >= 70:
                score_item.setForeground(QColor('#88b098'))
            elif score >= 40:
                score_item.setForeground(QColor('#b8a880'))
            else:
                score_item.setForeground(QColor('#b89090'))
            self.forecast_table.setItem(i, 4, score_item)

            # Clear hours
            clear_h = night.get('clear_hours', 0)
            self.forecast_table.setItem(i, 5, QTableWidgetItem(f"{clear_h:.1f}h"))

            # Target visibility
            vis = visibility.get(date_str, {})
            if vis:
                if vis.get('never_rises'):
                    vis_str = self._tr("Never rises", "Ne se lève jamais")
                    vis_item = QTableWidgetItem(vis_str)
                    vis_item.setForeground(QColor('#b89090'))
                elif vis.get('is_circumpolar'):
                    hours = vis.get('hours_above_min', 0)
                    vis_str = self._tr(f"Circumpolar ({hours:.1f}h)", f"Circumpolaire ({hours:.1f}h)")
                    vis_item = QTableWidgetItem(vis_str)
                    vis_item.setForeground(QColor('#88b098'))
                else:
                    hours = vis.get('hours_above_min', 0)
                    max_alt = vis.get('max_altitude', 0)
                    vis_str = f"{hours:.1f}h (max {max_alt:.0f}°)"
                    vis_item = QTableWidgetItem(vis_str)
                    if hours >= 4:
                        vis_item.setForeground(QColor('#88b098'))
                    elif hours >= 2:
                        vis_item.setForeground(QColor('#b8a880'))
                    else:
                        vis_item.setForeground(QColor('#b89090'))
            else:
                vis_item = QTableWidgetItem(self._tr("Select target", "Sélectionner cible"))
            self.forecast_table.setItem(i, 6, vis_item)

    def _on_forecast_error(self, error_msg):
        """Handle forecast fetch error"""
        self.forecast_btn.setEnabled(True)
        self.forecast_btn.setText(self._tr("🌤️ Get Forecast", "🌤️ Obtenir Prévisions"))
        self.forecast_table.setRowCount(1)
        self.forecast_table.setItem(0, 0, QTableWidgetItem(
            self._tr(f"Error: {error_msg}", f"Erreur : {error_msg}")))

    def _export_summary(self):
        """Export target summary to text file"""
        if not self.current_target:
            return

        from PyQt6.QtWidgets import QFileDialog
        target_name = self.current_target.get('name', 'Unknown')
        path, _ = QFileDialog.getSaveFileName(
            self, self._tr("Export Summary", "Exporter Résumé"),
            f"target_{target_name}.txt",
            "Text Files (*.txt)"
        )
        if not path:
            return

        lines = []
        lines.append(f"{'='*60}")
        lines.append(f"Target: {target_name}")
        if self.current_target.get('canonical_name'):
            lines.append(f"SIMBAD: {self.current_target['canonical_name']}")
        lines.append(f"Type: {self.current_target.get('object_type', '-')}")
        lines.append(f"{'='*60}")
        lines.append("")
        lines.append(f"Total Integration: {self.stats_labels['total_time'].text()}")
        lines.append(f"Total Frames: {self.stats_labels['total_frames'].text()}")
        lines.append(f"Sessions: {self.stats_labels['sessions'].text()}")
        lines.append(f"First Observed: {self.stats_labels['first_obs'].text()}")
        lines.append(f"Last Observed: {self.stats_labels['last_obs'].text()}")
        lines.append(f"Best HFR: {self.stats_labels['best_hfr'].text()}")
        lines.append("")
        lines.append(self._tr("Filter Breakdown:", "Détail par Filtre :"))

        for row in range(self.filter_table.rowCount()):
            fname = self.filter_table.item(row, 0).text() if self.filter_table.item(row, 0) else "-"
            frames = self.filter_table.item(row, 1).text() if self.filter_table.item(row, 1) else "0"
            time = self.filter_table.item(row, 2).text() if self.filter_table.item(row, 2) else "-"
            lines.append(f"  {fname}: {frames} frames, {time}")

        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        QMessageBox.information(self, self._tr("Export", "Export"),
            self._tr(f"Summary saved to {path}", f"Résumé sauvegardé dans {path}"))

    def _delete_target(self):
        """Delete target from database"""
        if not self.current_target:
            return

        target_name = self.current_target.get('name', 'Unknown')
        target_id = self.current_target.get('id')
        if not target_id:
            QMessageBox.warning(self, self._tr("Error", "Erreur"),
                self._tr("Invalid target: missing ID.", "Cible invalide : ID manquant."))
            return

        reply = QMessageBox.question(self,
            self._tr("Confirm Delete", "Confirmer Suppression"),
            self._tr(
                f"Delete target '{target_name}' and all its observations?",
                f"Supprimer la cible '{target_name}' et toutes ses observations?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            db = get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM observations WHERE target_id = ?",
                             (target_id,))
                cursor.execute("DELETE FROM targets WHERE id = ?",
                             (target_id,))

            self._clear_display()
            self._load_targets()
        except Exception as e:
            QMessageBox.warning(self, self._tr("Error", "Erreur"), str(e))
