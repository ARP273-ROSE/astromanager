#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - OBSERVATION HISTORY MODULE
================================================================================
Comprehensive observation history management with statistics, export/import,
and auto-save functionality. Works on top of the existing DatabaseManager.
================================================================================
"""

import json
import csv
import logging
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

from core.database import get_db

logger = logging.getLogger(__name__)


class ObservationHistory:
    """
    Provides comprehensive statistics and export/import on the observation
    history stored in the existing SQLite database (targets + observations).
    """

    def __init__(self):
        self.db = get_db()

    # =========================================================================
    # Global Overview Statistics
    # =========================================================================

    def get_global_stats(self) -> Dict[str, Any]:
        """Get global overview statistics across all observations (single query)."""
        with self.db.get_connection() as conn:
            c = conn.cursor()

            # Combined into a single query for ~10x fewer round-trips
            c.execute("""
                SELECT
                    (SELECT COUNT(*) FROM targets),
                    (SELECT COUNT(*) FROM observations),
                    (SELECT COALESCE(SUM(exposure_time), 0) FROM observations),
                    (SELECT COALESCE(SUM(frame_count), 0) FROM observations),
                    (SELECT MIN(observation_date) FROM observations),
                    (SELECT MAX(observation_date) FROM observations),
                    (SELECT COUNT(DISTINCT observation_date) FROM observations),
                    (SELECT COUNT(DISTINCT filter) FROM observations WHERE filter IS NOT NULL),
                    (SELECT COUNT(DISTINCT telescope) FROM observations WHERE telescope IS NOT NULL AND telescope != ''),
                    (SELECT COUNT(DISTINCT camera) FROM observations WHERE camera IS NOT NULL AND camera != ''),
                    (SELECT AVG(hfr) FROM observations WHERE hfr IS NOT NULL AND hfr > 0),
                    (SELECT AVG(fwhm) FROM observations WHERE fwhm IS NOT NULL AND fwhm > 0)
            """)
            row = c.fetchone()

            return {
                'total_targets': row[0],
                'total_observations': row[1],
                'total_integration_seconds': row[2],
                'total_frames': row[3],
                'first_observation': row[4],
                'last_observation': row[5],
                'unique_nights': row[6],
                'unique_filters': row[7],
                'unique_telescopes': row[8],
                'unique_cameras': row[9],
                'avg_hfr': round(row[10], 2) if row[10] else None,
                'avg_fwhm': round(row[11], 2) if row[11] else None,
            }

    # =========================================================================
    # Per-Target Statistics
    # =========================================================================

    def get_target_rankings(self, limit: int = 50) -> List[Dict]:
        """Get targets ranked by total integration time.

        Each row now also includes a comma-separated list of telescopes
        used for that target so that entries that appear similar can be
        visually differentiated.
        """
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT t.id, t.name, t.canonical_name, t.object_type,
                       t.total_exposure_time, t.total_frames,
                       t.first_observed, t.last_observed,
                       COUNT(DISTINCT o.observation_date) as sessions,
                       COUNT(DISTINCT o.filter) as filters_used,
                       GROUP_CONCAT(DISTINCT o.telescope) as telescopes_used
                FROM targets t
                LEFT JOIN observations o ON o.target_id = t.id
                GROUP BY t.id
                ORDER BY t.total_exposure_time DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in c.fetchall()]

    def get_target_detailed_stats(self, target_id: int) -> Dict[str, Any]:
        """Get detailed statistics for a specific target."""
        with self.db.get_connection() as conn:
            c = conn.cursor()

            # Basic target info
            c.execute("SELECT * FROM targets WHERE id = ?", (target_id,))
            row = c.fetchone()
            if row is None:
                return {}
            target = dict(row)

            # Per-filter breakdown
            c.execute("""
                SELECT filter,
                       COUNT(*) as session_count,
                       SUM(frame_count) as total_frames,
                       SUM(exposure_time) as total_time,
                       AVG(exposure_time / NULLIF(frame_count, 0)) as avg_sub_exposure,
                       MIN(hfr) as best_hfr,
                       AVG(hfr) as avg_hfr
                FROM observations
                WHERE target_id = ?
                GROUP BY filter
                ORDER BY total_time DESC
            """, (target_id,))
            filter_breakdown = [dict(row) for row in c.fetchall()]

            # Per-equipment breakdown
            c.execute("""
                SELECT telescope, camera,
                       COUNT(*) as session_count,
                       SUM(exposure_time) as total_time,
                       SUM(frame_count) as total_frames
                FROM observations
                WHERE target_id = ?
                GROUP BY telescope, camera
                ORDER BY total_time DESC
            """, (target_id,))
            equipment_breakdown = [dict(row) for row in c.fetchall()]

            # Monthly timeline
            c.execute("""
                SELECT strftime('%Y-%m', observation_date) as month,
                       SUM(exposure_time) as total_time,
                       SUM(frame_count) as total_frames,
                       COUNT(*) as sessions
                FROM observations
                WHERE target_id = ?
                GROUP BY month
                ORDER BY month
            """, (target_id,))
            monthly_timeline = [dict(row) for row in c.fetchall()]

            # Best sessions (by HFR)
            c.execute("""
                SELECT observation_date, filter, exposure_time, frame_count,
                       hfr, fwhm, telescope, camera
                FROM observations
                WHERE target_id = ? AND hfr IS NOT NULL AND hfr > 0
                ORDER BY hfr ASC
                LIMIT 5
            """, (target_id,))
            best_sessions = [dict(row) for row in c.fetchall()]

            return {
                'target': target,
                'filter_breakdown': filter_breakdown,
                'equipment_breakdown': equipment_breakdown,
                'monthly_timeline': monthly_timeline,
                'best_sessions': best_sessions,
            }

    # =========================================================================
    # Per-Filter Statistics
    # =========================================================================

    def get_filter_stats(self) -> List[Dict]:
        """Get aggregated statistics per filter across all targets."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT filter,
                       COUNT(DISTINCT target_id) as target_count,
                       COUNT(*) as session_count,
                       SUM(frame_count) as total_frames,
                       SUM(exposure_time) as total_time,
                       AVG(hfr) as avg_hfr,
                       MIN(hfr) as best_hfr,
                       AVG(exposure_time / NULLIF(frame_count, 0)) as avg_sub_exposure
                FROM observations
                WHERE filter IS NOT NULL
                GROUP BY filter
                ORDER BY total_time DESC
            """)
            return [dict(row) for row in c.fetchall()]

    # =========================================================================
    # Per-Equipment Statistics
    # =========================================================================

    def get_telescope_stats(self) -> List[Dict]:
        """Get aggregated statistics per telescope."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT telescope,
                       COUNT(DISTINCT target_id) as target_count,
                       COUNT(*) as session_count,
                       SUM(frame_count) as total_frames,
                       SUM(exposure_time) as total_time,
                       AVG(hfr) as avg_hfr,
                       MIN(hfr) as best_hfr
                FROM observations
                WHERE telescope IS NOT NULL AND telescope != ''
                GROUP BY telescope
                ORDER BY total_time DESC
            """)
            return [dict(row) for row in c.fetchall()]

    def get_camera_stats(self) -> List[Dict]:
        """Get aggregated statistics per camera."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT camera,
                       COUNT(DISTINCT target_id) as target_count,
                       COUNT(*) as session_count,
                       SUM(frame_count) as total_frames,
                       SUM(exposure_time) as total_time,
                       AVG(hfr) as avg_hfr,
                       MIN(hfr) as best_hfr
                FROM observations
                WHERE camera IS NOT NULL AND camera != ''
                GROUP BY camera
                ORDER BY total_time DESC
            """)
            return [dict(row) for row in c.fetchall()]

    def get_setup_stats(self) -> List[Dict]:
        """Get aggregated statistics per telescope+camera setup."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT telescope, camera,
                       COUNT(DISTINCT target_id) as target_count,
                       COUNT(*) as session_count,
                       SUM(frame_count) as total_frames,
                       SUM(exposure_time) as total_time,
                       AVG(hfr) as avg_hfr,
                       MIN(hfr) as best_hfr
                FROM observations
                WHERE telescope IS NOT NULL AND telescope != ''
                      AND camera IS NOT NULL AND camera != ''
                GROUP BY telescope, camera
                ORDER BY total_time DESC
            """)
            return [dict(row) for row in c.fetchall()]

    # =========================================================================
    # Temporal Statistics
    # =========================================================================

    def get_monthly_stats(self) -> List[Dict]:
        """Get monthly aggregated statistics."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT strftime('%Y-%m', observation_date) as month,
                       COUNT(DISTINCT target_id) as targets,
                       COUNT(DISTINCT observation_date) as nights,
                       COUNT(*) as sessions,
                       SUM(frame_count) as total_frames,
                       SUM(exposure_time) as total_time,
                       AVG(hfr) as avg_hfr
                FROM observations
                GROUP BY month
                ORDER BY month
            """)
            return [dict(row) for row in c.fetchall()]

    def get_yearly_stats(self) -> List[Dict]:
        """Get yearly aggregated statistics."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT strftime('%Y', observation_date) as year,
                       COUNT(DISTINCT target_id) as targets,
                       COUNT(DISTINCT observation_date) as nights,
                       COUNT(*) as sessions,
                       SUM(frame_count) as total_frames,
                       SUM(exposure_time) as total_time,
                       AVG(hfr) as avg_hfr
                FROM observations
                GROUP BY year
                ORDER BY year
            """)
            return [dict(row) for row in c.fetchall()]

    def get_day_of_week_stats(self) -> List[Dict]:
        """Get statistics by day of week (0=Sunday, 6=Saturday)."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT CAST(strftime('%w', observation_date) AS INTEGER) as dow,
                       COUNT(DISTINCT observation_date) as nights,
                       COUNT(*) as sessions,
                       SUM(exposure_time) as total_time,
                       SUM(frame_count) as total_frames
                FROM observations
                GROUP BY dow
                ORDER BY dow
            """)
            return [dict(row) for row in c.fetchall()]

    def get_activity_calendar(self, year: Optional[int] = None) -> Dict[str, float]:
        """Get daily integration time for calendar heatmap. Returns {date_str: hours}."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            if year:
                c.execute("""
                    SELECT observation_date, SUM(exposure_time) as total_time
                    FROM observations
                    WHERE strftime('%Y', observation_date) = ?
                    GROUP BY observation_date
                    ORDER BY observation_date
                """, (str(year),))
            else:
                c.execute("""
                    SELECT observation_date, SUM(exposure_time) as total_time
                    FROM observations
                    GROUP BY observation_date
                    ORDER BY observation_date
                """)
            return {row[0]: (row[1] or 0) / 3600.0 for row in c.fetchall()}

    # =========================================================================
    # Quality Statistics
    # =========================================================================

    def get_quality_trends(self) -> List[Dict]:
        """Get HFR/FWHM quality trends over time (monthly)."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT strftime('%Y-%m', observation_date) as month,
                       AVG(hfr) as avg_hfr,
                       MIN(hfr) as best_hfr,
                       AVG(fwhm) as avg_fwhm,
                       MIN(fwhm) as best_fwhm,
                       COUNT(*) as sessions
                FROM observations
                WHERE hfr IS NOT NULL AND hfr > 0
                GROUP BY month
                ORDER BY month
            """)
            return [dict(row) for row in c.fetchall()]

    def get_best_nights(self, limit: int = 10) -> List[Dict]:
        """Get best observation nights ranked by average HFR."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT observation_date,
                       AVG(hfr) as avg_hfr,
                       MIN(hfr) as best_hfr,
                       SUM(exposure_time) as total_time,
                       SUM(frame_count) as total_frames,
                       COUNT(DISTINCT target_id) as targets,
                       GROUP_CONCAT(DISTINCT filter) as filters
                FROM observations
                WHERE hfr IS NOT NULL AND hfr > 0
                GROUP BY observation_date
                HAVING COUNT(*) >= 1
                ORDER BY avg_hfr ASC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in c.fetchall()]

    def get_most_productive_nights(self, limit: int = 10) -> List[Dict]:
        """Get most productive observation nights by total integration time."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT observation_date,
                       SUM(exposure_time) as total_time,
                       SUM(frame_count) as total_frames,
                       COUNT(DISTINCT target_id) as targets,
                       GROUP_CONCAT(DISTINCT filter) as filters,
                       AVG(hfr) as avg_hfr
                FROM observations
                GROUP BY observation_date
                ORDER BY total_time DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in c.fetchall()]

    # =========================================================================
    # Object Type Statistics
    # =========================================================================

    def get_object_type_stats(self) -> List[Dict]:
        """Get statistics by astronomical object type."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT COALESCE(t.object_type, 'Unknown') as object_type,
                       COUNT(DISTINCT t.id) as target_count,
                       SUM(o.exposure_time) as total_time,
                       SUM(o.frame_count) as total_frames,
                       COUNT(DISTINCT o.observation_date) as nights
                FROM targets t
                LEFT JOIN observations o ON o.target_id = t.id
                GROUP BY object_type
                ORDER BY total_time DESC
            """)
            return [dict(row) for row in c.fetchall()]

    # =========================================================================
    # Export / Import
    # =========================================================================

    def export_to_json(self, file_path: str) -> int:
        """
        Export complete observation history to JSON file.
        Returns number of targets exported.
        """
        with self.db.get_connection() as conn:
            c = conn.cursor()

            # Get all targets
            c.execute("SELECT * FROM targets ORDER BY name")
            targets = [dict(row) for row in c.fetchall()]

            export_data = {
                'version': '1.0',
                'exported_at': datetime.now().isoformat(),
                'application': 'AstroManager',
                'targets': [],
            }

            for target in targets:
                target_id = target['id']

                # Get observations for this target
                c.execute("""
                    SELECT * FROM observations
                    WHERE target_id = ?
                    ORDER BY observation_date
                """, (target_id,))
                observations = [dict(row) for row in c.fetchall()]

                # Parse JSON fields
                if target.get('simbad_data'):
                    try:
                        target['simbad_data'] = json.loads(target['simbad_data'])
                    except (json.JSONDecodeError, TypeError):
                        pass

                for obs in observations:
                    for field in ('weather_data', 'file_paths'):
                        if obs.get(field):
                            try:
                                obs[field] = json.loads(obs[field])
                            except (json.JSONDecodeError, TypeError):
                                pass
                    # Remove internal IDs
                    obs.pop('id', None)
                    obs.pop('target_id', None)

                # Remove internal ID
                target.pop('id', None)
                target['observations'] = observations

                export_data['targets'].append(target)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"Exported {len(targets)} targets to {file_path}")
            return len(targets)

    def import_from_json(self, file_path: str) -> Tuple[int, int]:
        """
        Import observation history from JSON file.
        Returns (targets_imported, observations_imported).
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'targets' not in data:
            raise ValueError("Invalid JSON format: missing 'targets' key")

        targets_imported = 0
        obs_imported = 0

        for target_data in data['targets']:
            observations = target_data.pop('observations', [])

            # Re-serialize JSON fields for storage
            simbad_data = target_data.get('simbad_data')
            if isinstance(simbad_data, dict):
                target_data['simbad_data'] = simbad_data
            elif isinstance(simbad_data, str):
                try:
                    target_data['simbad_data'] = json.loads(simbad_data)
                except (json.JSONDecodeError, TypeError):
                    target_data['simbad_data'] = None

            target_id = self.db.add_target(
                name=target_data.get('name', ''),
                canonical_name=target_data.get('canonical_name'),
                ra=target_data.get('ra'),
                dec=target_data.get('dec'),
                object_type=target_data.get('object_type'),
                simbad_data=target_data.get('simbad_data'),
            )
            targets_imported += 1

            # DELETE + INSERT in a single transaction to prevent duplicates
            if observations:
                with self.db.get_connection() as conn:
                    c = conn.cursor()
                    for obs in observations:
                        obs_date = obs.get('observation_date', '')
                        if obs_date:
                            c.execute("""
                                DELETE FROM observations
                                WHERE target_id = ?
                                  AND observation_date = ?
                                  AND COALESCE(filter, '') = ?
                                  AND COALESCE(telescope, '') = ?
                                  AND COALESCE(camera, '') = ?
                            """, (target_id, obs_date,
                                  obs.get('filter') or '',
                                  obs.get('telescope') or '',
                                  obs.get('camera') or ''))

                    for obs in observations:
                        weather_data = obs.get('weather_data')
                        file_paths = obs.get('file_paths')
                        obs_date = obs.get('observation_date', '')
                        c.execute("""
                            INSERT OR REPLACE INTO observations (
                                target_id, observation_date, filter, exposure_time,
                                frame_count, setup, telescope, camera, hfr, fwhm,
                                temperature, weather_data, file_paths, notes
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            target_id, obs_date, obs.get('filter'),
                            obs.get('exposure_time'), obs.get('frame_count'),
                            obs.get('setup'), obs.get('telescope'), obs.get('camera'),
                            obs.get('hfr'), obs.get('fwhm'), obs.get('temperature'),
                            json.dumps(weather_data) if isinstance(weather_data, dict) else None,
                            json.dumps(file_paths) if isinstance(file_paths, list) else None,
                            obs.get('notes'),
                        ))
                        obs_imported += 1

        logger.info(f"Imported {targets_imported} targets, {obs_imported} observations from {file_path}")
        return targets_imported, obs_imported

    def export_to_csv(self, file_path: str) -> int:
        """
        Export observations to CSV file.
        Returns number of rows exported.
        """
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT t.name as target_name, t.canonical_name, t.object_type,
                       t.ra, t.dec,
                       o.observation_date, o.filter, o.exposure_time,
                       o.frame_count, o.setup, o.telescope, o.camera,
                       o.hfr, o.fwhm, o.temperature, o.notes
                FROM observations o
                JOIN targets t ON t.id = o.target_id
                ORDER BY o.observation_date DESC, t.name
            """)

            rows = c.fetchall()
            columns = [desc[0] for desc in c.description]

        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for row in rows:
                writer.writerow(list(row))

        logger.info(f"Exported {len(rows)} observation records to CSV: {file_path}")
        return len(rows)

    def import_from_csv(self, file_path: str) -> Tuple[int, int]:
        """
        Import observations from CSV file.
        Returns (targets_imported, observations_imported).
        """
        targets_seen = set()
        obs_imported = 0
        errors = []

        # Phase 1: Parse and validate all rows [PERF]
        parsed_rows = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, start=1):
                try:
                    target_name = row.get('target_name', '').strip()
                    if not target_name:
                        continue
                    try:
                        ra_val = float(row['ra']) if row.get('ra') else None
                    except (ValueError, TypeError):
                        errors.append(f"Row {i}: invalid ra data, skipped")
                        continue
                    try:
                        dec_val = float(row['dec']) if row.get('dec') else None
                    except (ValueError, TypeError):
                        errors.append(f"Row {i}: invalid dec data, skipped")
                        continue
                    parsed_rows.append((row, target_name, ra_val, dec_val))
                except (ValueError, TypeError, KeyError) as e:
                    errors.append(f"Row {i}: invalid data ({e}), skipped")

        # Phase 2: Add targets and collect dedup keys
        dedup_keys = []  # (target_id, obs_date, filter, telescope, camera)
        insert_rows = []
        for row, target_name, ra_val, dec_val in parsed_rows:
            try:
                target_id = self.db.add_target(
                    name=target_name,
                    canonical_name=row.get('canonical_name') or None,
                    ra=ra_val, dec=dec_val,
                    object_type=row.get('object_type') or None,
                )
                targets_seen.add(target_name)
                obs_date = row.get('observation_date', '')
                if obs_date:
                    dedup_keys.append((target_id, obs_date,
                                      row.get('filter') or '',
                                      row.get('telescope') or '',
                                      row.get('camera') or ''))
                insert_rows.append((target_id, row))
            except Exception as e:
                errors.append(f"Target '{target_name}': {e}")

        # Phase 3: Batch dedup in single connection
        if dedup_keys:
            with self.db.get_connection() as conn:
                c = conn.cursor()
                for key in dedup_keys:
                    c.execute("""
                        DELETE FROM observations
                        WHERE target_id = ?
                          AND observation_date = ?
                          AND COALESCE(filter, '') = ?
                          AND COALESCE(telescope, '') = ?
                          AND COALESCE(camera, '') = ?
                    """, key)

        # Phase 4: Insert all observations
        for target_id, row in insert_rows:
            try:
                self.db.add_observation(
                    target_id=target_id,
                    observation_date=row.get('observation_date', ''),
                    filter_name=row.get('filter') or None,
                    exposure_time=float(row['exposure_time']) if row.get('exposure_time') else None,
                    frame_count=int(row['frame_count']) if row.get('frame_count') else None,
                    setup=row.get('setup') or None,
                    telescope=row.get('telescope') or None,
                    camera=row.get('camera') or None,
                    hfr=float(row['hfr']) if row.get('hfr') else None,
                    fwhm=float(row['fwhm']) if row.get('fwhm') else None,
                    temperature=float(row['temperature']) if row.get('temperature') else None,
                    notes=row.get('notes') or None,
                )
                obs_imported += 1
            except (ValueError, TypeError, KeyError) as e:
                errors.append(f"Observation insert: {e}")

        if errors:
            logger.warning(f"CSV import had {len(errors)} error(s): {'; '.join(errors[:10])}")
        logger.info(f"Imported {len(targets_seen)} targets, {obs_imported} observations from CSV: {file_path}")
        return len(targets_seen), obs_imported

    # =========================================================================
    # Utility
    # =========================================================================

    def get_all_observations_flat(self) -> List[Dict]:
        """Get all observations as flat list with target info joined."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT o.*, t.name as target_name, t.canonical_name, t.object_type
                FROM observations o
                JOIN targets t ON t.id = o.target_id
                ORDER BY o.observation_date DESC
            """)
            return [dict(row) for row in c.fetchall()]

    def store_analysis_results(self, results: Dict) -> Tuple[int, int]:
        """
        Auto-store analysis results into the observation database with
        smart deduplication: same (target, date, filter, telescope, camera)
        is replaced, not duplicated.

        Returns (targets_stored, observations_stored).
        """
        data_by_target = results.get('data_by_target', {})
        if not data_by_target:
            return 0, 0

        targets_stored = 0
        obs_stored = 0

        # Lazy-load classify_target_type for otype fallback
        _classify = None
        try:
            from database.targets import classify_target_type as _classify
        except ImportError:
            pass

        _type_to_otype = {
            'galaxy': 'G', 'nebula': 'GNe', 'emission_nebula': 'HII',
            'planetary_nebula': 'PN', 'reflection_nebula': 'RNe',
            'dark_nebula': 'DNe', 'supernova_remnant': 'SNR',
            'open_cluster': 'OpC', 'globular_cluster': 'GlC',
            'star': '*', 'double_star': '**', 'planetary': 'Pl',
            'comet': 'Pl', 'asteroid': 'Pl', 'galaxy_group': 'ClG',
        }

        for target_name, target_data in data_by_target.items():
            try:
                # Get SIMBAD info if available
                simbad_info = target_data.get('simbad_info', {})
                canonical = simbad_info.get('main_id') if simbad_info else None
                ra = simbad_info.get('ra') if simbad_info else None
                dec = simbad_info.get('dec') if simbad_info else None
                obj_type = simbad_info.get('otype') if simbad_info else None

                # Fallback: classify from name when SIMBAD gave no type
                if (not obj_type or obj_type == '?') and _classify:
                    for candidate in (target_name, canonical):
                        if not candidate:
                            continue
                        classified = _classify(candidate)
                        if classified and classified != 'unknown':
                            obj_type = _type_to_otype.get(classified, obj_type)
                            break

                target_id = self.db.add_target(
                    name=target_name,
                    canonical_name=canonical,
                    ra=ra, dec=dec,
                    object_type=obj_type,
                    simbad_data=simbad_info if simbad_info else None
                )

                # Get equipment info (may be set, list, or str)
                telescopes = target_data.get('telescopes', set())
                instruments = target_data.get('instruments', set())
                if isinstance(telescopes, (set, frozenset, list, tuple)):
                    telescope_str = ', '.join(sorted(set(telescopes)))
                else:
                    telescope_str = str(telescopes or '')
                if isinstance(instruments, (set, frozenset, list, tuple)):
                    camera_str = ', '.join(sorted(set(instruments)))
                else:
                    camera_str = str(instruments or '')
                setup_str = f"{telescope_str} + {camera_str}" if telescope_str and camera_str else telescope_str or camera_str or ''

                # Build observations from files_by_date (batch dedup) [PERF]
                files_by_date = target_data.get('files_by_date', {})

                # Collect all obs rows first, then batch-delete + insert in one connection.
                # Aggregate by the UNIQUE dedup key (target_id, observation_date, filter,
                # telescope, camera) BEFORE inserting: telescope/camera are constant for
                # this target, so the key reduces to (obs_date, filter_name). Two source
                # entries that collapse to the same key (e.g. dates that truncate to the
                # same day) would otherwise produce two INSERTs with the same key and
                # violate idx_obs_dedup -> IntegrityError -> full rollback (no observation
                # stored for the target). Summing exposure/frame counts keeps all the info.
                obs_map = {}
                for date, date_data in files_by_date.items():
                    time_by_filter = date_data.get('time_by_filter', {})
                    for filter_name, exposures in time_by_filter.items():
                        if not exposures:
                            continue
                        obs_date = str(date)[:10] if date else ''
                        if not obs_date:
                            continue
                        # Normalize filter like the UNIQUE index does
                        # (COALESCE(filter,'')) so None and '' can never split
                        # into two keys that then collide in idx_obs_dedup.
                        key = (obs_date, filter_name or '')
                        prev_exp, prev_count = obs_map.get(key, (0, 0))
                        obs_map[key] = (prev_exp + sum(exposures),
                                        prev_count + len(exposures))
                obs_rows = [(obs_date, filter_name, total_exp, frame_count)
                            for (obs_date, filter_name), (total_exp, frame_count)
                            in obs_map.items()]

                if obs_rows:
                    # DELETE + INSERT in a single transaction to guarantee
                    # atomicity and prevent duplicate observations.
                    with self.db.get_connection() as conn:
                        c = conn.cursor()
                        for obs_date, filter_name, total_exp, frame_count in obs_rows:
                            # Dedup: delete existing observation with same key
                            c.execute("""
                                DELETE FROM observations
                                WHERE target_id = ?
                                  AND observation_date = ?
                                  AND COALESCE(filter, '') = ?
                                  AND COALESCE(telescope, '') = ?
                                  AND COALESCE(camera, '') = ?
                            """, (target_id, obs_date, filter_name or '',
                                  telescope_str or '', camera_str or ''))

                        # Insert in same transaction
                        for obs_date, filter_name, total_exp, frame_count in obs_rows:
                            c.execute("""
                                INSERT INTO observations (
                                    target_id, observation_date, filter, exposure_time,
                                    frame_count, setup, telescope, camera
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (target_id, obs_date, filter_name, total_exp,
                                  frame_count, setup_str, telescope_str, camera_str))
                            obs_stored += 1

                    # Update target stats after commit
                    self.db.update_target_stats(target_id)

                targets_stored += 1
            except Exception as e:
                logger.error(f"Error storing target '{target_name}': {e}")
                continue

        logger.info(f"Auto-stored {targets_stored} targets, {obs_stored} observations")
        return targets_stored, obs_stored

    # =========================================================================
    # Data Cleanup / Maintenance
    # =========================================================================

    def merge_duplicate_targets(self) -> int:
        """
        Merge targets that refer to the same physical object.

        Handles three cases:
        1. Multiple targets sharing the same canonical_name.
        2. A target with canonical_name=NULL whose name matches another
           target's canonical_name (old entry without SIMBAD lookup).
        3. A target whose name (stripped of equipment suffix like
           "(455mm)") matches another target's name or canonical.

        The target with the lowest id (earliest created) is kept.
        All observations from duplicates are re-assigned to it.

        Returns the number of duplicate targets removed.
        """
        import re
        removed = 0
        with self.db.get_connection() as conn:
            c = conn.cursor()

            # --- Pass 1: same canonical_name ---
            c.execute("""
                SELECT canonical_name, GROUP_CONCAT(id) as ids
                FROM targets
                WHERE canonical_name IS NOT NULL AND canonical_name != ''
                GROUP BY canonical_name
                HAVING COUNT(*) > 1
            """)
            duplicates = c.fetchall()

            for row in duplicates:
                ids = [int(x) for x in row['ids'].split(',')]
                keep_id = min(ids)
                for dup_id in [i for i in ids if i != keep_id]:
                    c.execute("UPDATE observations SET target_id = ? WHERE target_id = ?",
                              (keep_id, dup_id))
                    c.execute("DELETE FROM targets WHERE id = ?", (dup_id,))
                    removed += 1
                self.db.update_target_stats(keep_id)

            # --- Pass 2: NULL canonical matching another target's canonical ---
            c.execute("""
                SELECT a.id AS orphan_id, b.id AS match_id
                FROM targets a
                JOIN targets b
                  ON a.id != b.id
                 AND b.canonical_name IS NOT NULL
                 AND b.canonical_name != ''
                 AND REPLACE(REPLACE(a.name, '  ', ' '), '  ', ' ')
                     = REPLACE(REPLACE(b.canonical_name, '  ', ' '), '  ', ' ')
                WHERE a.canonical_name IS NULL OR a.canonical_name = ''
            """)
            matches = c.fetchall()
            for row in matches:
                orphan_id, match_id = row['orphan_id'], row['match_id']
                keep_id = min(orphan_id, match_id)
                dup_id = max(orphan_id, match_id)
                # Check dup still exists
                c.execute("SELECT id FROM targets WHERE id = ?", (dup_id,))
                if not c.fetchone():
                    continue
                # Grab canonical from the match before deleting
                c.execute("SELECT canonical_name, object_type FROM targets WHERE id = ?", (match_id,))
                match_row = c.fetchone()
                match_canonical = match_row['canonical_name'] if match_row else None
                match_otype = match_row['object_type'] if match_row else None

                c.execute("UPDATE observations SET target_id = ? WHERE target_id = ?",
                          (keep_id, dup_id))
                c.execute("DELETE FROM targets WHERE id = ?", (dup_id,))
                removed += 1
                # Backfill canonical_name and object_type on keeper
                if match_canonical:
                    c.execute("""UPDATE targets SET
                                    canonical_name = COALESCE(canonical_name, ?),
                                    object_type = COALESCE(object_type, ?)
                                WHERE id = ?""",
                              (match_canonical, match_otype, keep_id))
                self.db.update_target_stats(keep_id)

            # --- Pass 3: name without equipment suffix matches canonical ---
            # Strip "(NNNmm)" or "(NNNNmm)" suffixes for comparison
            c.execute("SELECT id, name, canonical_name FROM targets")
            all_targets = c.fetchall()
            # Build lookup: stripped name → list of target ids
            _strip_re = re.compile(r'\s*\(\d+mm\)\s*$', re.IGNORECASE)
            by_stripped = {}
            for t in all_targets:
                stripped = _strip_re.sub('', t['name']).strip()
                by_stripped.setdefault(stripped, []).append(t['id'])

            for stripped, ids in by_stripped.items():
                if len(ids) <= 1:
                    continue
                # Also pull in any target whose canonical matches this stripped name
                keep_id = min(ids)
                for dup_id in [i for i in ids if i != keep_id]:
                    # Check it still exists (might have been deleted in pass 1/2)
                    c.execute("SELECT id FROM targets WHERE id = ?", (dup_id,))
                    if not c.fetchone():
                        continue
                    c.execute("UPDATE observations SET target_id = ? WHERE target_id = ?",
                              (keep_id, dup_id))
                    # Copy canonical_name to keeper if missing
                    c.execute("""
                        UPDATE targets SET
                            canonical_name = COALESCE(
                                (SELECT canonical_name FROM targets WHERE id = ?),
                                canonical_name
                            ),
                            object_type = COALESCE(
                                object_type,
                                (SELECT object_type FROM targets WHERE id = ?)
                            )
                        WHERE id = ? AND (canonical_name IS NULL OR canonical_name = '')
                    """, (dup_id, dup_id, keep_id))
                    c.execute("DELETE FROM targets WHERE id = ?", (dup_id,))
                    removed += 1
                self.db.update_target_stats(keep_id)

        if removed:
            logger.info(f"Merged {removed} duplicate target(s)")
        return removed

    def fix_unknown_object_types(self) -> int:
        """
        Fill in missing / unknown object_type for existing targets using
        the local catalog classifier (database.targets.classify_target_type)
        and, as a second pass, using the SIMBAD otype labels dictionary.

        Returns the number of targets updated.
        """
        try:
            from database.targets import classify_target_type, TARGET_TYPES
        except ImportError:
            logger.warning("Could not import classify_target_type")
            return 0

        # Map classify_target_type keys → SIMBAD otype codes
        _type_to_otype = {
            'galaxy':           'G',
            'nebula':           'GNe',
            'emission_nebula':  'HII',
            'planetary_nebula': 'PN',
            'reflection_nebula':'RNe',
            'dark_nebula':      'DNe',
            'supernova_remnant':'SNR',
            'open_cluster':     'OpC',
            'globular_cluster': 'GlC',
            'star':             '*',
            'double_star':      '**',
            'planetary':        'Pl',
            'comet':            'Pl',
            'asteroid':         'Pl',
            'galaxy_group':     'ClG',
        }

        updated = 0
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, name, canonical_name
                FROM targets
                WHERE object_type IS NULL
                   OR object_type = ''
                   OR object_type = '?'
            """)
            targets = c.fetchall()

            for t in targets:
                # Try classifying by the original name first, then canonical
                for candidate in (t['name'], t['canonical_name']):
                    if not candidate:
                        continue
                    classified = classify_target_type(candidate)
                    if classified and classified != 'unknown':
                        otype = _type_to_otype.get(classified)
                        if otype:
                            c.execute(
                                "UPDATE targets SET object_type = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                (otype, t['id'])
                            )
                            updated += 1
                            break

        if updated:
            logger.info(f"Fixed object_type for {updated} target(s)")
        return updated

    def normalize_filter_names(self) -> int:
        """Normalise filter names stored in the observations table.

        Fixes three categories of issues:
        1. Greek Unicode chars  → ASCII  (e.g. 'Hα' → 'HA')
        2. Corrupted / encoding-failed names (e.g. 'H?' → 'HA')
        3. Truncated single-char filters (e.g. 'H' → 'HA' when 'HA'
           already exists in the same dataset)

        Returns the number of observations updated.
        """
        try:
            from gui.theme import normalize_filter_name
        except ImportError:
            return 0

        # Known corrupted / truncated → correct mappings
        _corrupted = {
            'H?': 'HA',
            'H':  'HA',
        }

        updated = 0
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT DISTINCT filter FROM observations WHERE filter IS NOT NULL")
            filters = [row['filter'] for row in c.fetchall()]
            filter_set = set(filters)  # for quick membership checks

            for raw in filters:
                # Step 1: check explicit corrupted mapping
                if raw in _corrupted:
                    new = _corrupted[raw]
                else:
                    # Step 2: normalise Greek chars
                    new = normalize_filter_name(raw).upper()

                # Step 3: single-char filter that looks like a truncated
                # version of an existing longer filter (e.g. 'H' → 'HA')
                # Skip standard LRGB broadband filter names
                _standard_single = {'L', 'R', 'G', 'B', 'V', 'U', 'I'}
                if new == raw and len(raw) == 1 and raw.isalpha() and raw not in _standard_single:
                    candidates = [f for f in filter_set
                                  if len(f) > 1 and f.startswith(raw)
                                  and f not in _standard_single]
                    if len(candidates) == 1:
                        new = candidates[0]

                if new != raw:
                    c.execute(
                        "UPDATE observations SET filter = ? WHERE filter = ?",
                        (new, raw),
                    )
                    updated += c.rowcount

        if updated:
            logger.info(f"Normalised filter names for {updated} observation(s)")
        return updated

    @staticmethod
    def _dedup_equipment_parts(value: str) -> str:
        """Deduplicate comma-separated equipment parts.

        If one part is a substring of another (e.g. 'RC10' inside
        'CFF RC10', or 'FLI' inside 'FLI PL16803'), keep only the
        longer (more specific) part.
        """
        parts = [p.strip() for p in value.split(',') if p.strip()]
        if len(parts) <= 1:
            return value

        # Remove any part that is a substring of a longer part
        keep = []
        for p in sorted(parts, key=len, reverse=True):
            # Check if p is already covered by a longer part in keep
            if any(p.lower() in k.lower() for k in keep):
                continue
            keep.append(p)

        return ', '.join(sorted(keep))

    def normalize_equipment_names(self) -> int:
        """Clean up telescope / camera / setup values in the observations table.

        Fixes:
        - Python list repr stored as string: "['FSQ85-EDP']" → "FSQ85-EDP"
        - Substring duplicates: "CFF RC10, RC10" → "CFF RC10"
        - Substring duplicates: "FLI, FLI PL16803" → "FLI PL16803"
        - Rebuilds setup string from cleaned telescope + camera.

        Returns the number of observations updated.
        """
        import ast
        ALLOWED_COLUMNS = {'telescope', 'camera', 'filter'}
        updated = 0
        with self.db.get_connection() as conn:
            c = conn.cursor()

            for col in ('telescope', 'camera'):
                if col not in ALLOWED_COLUMNS:
                    continue
                c.execute(f"SELECT DISTINCT {col} FROM observations WHERE {col} IS NOT NULL AND {col} != ''")
                values = [row[col] for row in c.fetchall()]

                for raw in values:
                    cleaned = raw
                    # Step 1: Detect Python list repr (with size limit against DoS)
                    if raw.startswith('[') and raw.endswith(']') and len(raw) < 10000:
                        try:
                            parsed = ast.literal_eval(raw)
                            if isinstance(parsed, list):
                                cleaned = ', '.join(sorted(set(parsed)))
                        except (ValueError, SyntaxError):
                            pass

                    # Step 2: Deduplicate comma-separated parts
                    cleaned = self._dedup_equipment_parts(cleaned)

                    if cleaned != raw:
                        c.execute(
                            f"UPDATE observations SET {col} = ? WHERE {col} = ?",
                            (cleaned, raw),
                        )
                        updated += c.rowcount

            # Rebuild all setup strings from cleaned telescope + camera
            c.execute("""
                UPDATE observations SET setup =
                    CASE
                        WHEN COALESCE(telescope, '') != '' AND COALESCE(camera, '') != ''
                            THEN telescope || ' + ' || camera
                        WHEN COALESCE(telescope, '') != ''
                            THEN telescope
                        WHEN COALESCE(camera, '') != ''
                            THEN camera
                        ELSE ''
                    END
                WHERE setup != (
                    CASE
                        WHEN COALESCE(telescope, '') != '' AND COALESCE(camera, '') != ''
                            THEN telescope || ' + ' || camera
                        WHEN COALESCE(telescope, '') != ''
                            THEN telescope
                        WHEN COALESCE(camera, '') != ''
                            THEN camera
                        ELSE ''
                    END
                )
            """)
            updated += c.rowcount

        if updated:
            logger.info(f"Normalised equipment names for {updated} observation(s)")
        return updated

    def clear_all_history(self):
        """Clear all observation history (targets + observations). Use with caution."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM observations")
            c.execute("DELETE FROM targets")
            logger.warning("All observation history cleared")


def format_time(seconds: float, lang: str = 'en') -> str:
    """Format seconds into human-readable time string."""
    if seconds is None or seconds <= 0:
        return "-"
    hours = seconds / 3600
    if hours >= 1:
        h = int(hours)
        m = int((hours - h) * 60)
        if lang == 'fr':
            return f"{h}h {m:02d}m" if m > 0 else f"{h}h"
        return f"{h}h {m:02d}m" if m > 0 else f"{h}h"
    minutes = seconds / 60
    if minutes >= 1:
        return f"{minutes:.0f}m"
    return f"{seconds:.0f}s"


# Global singleton
_history_instance = None
_history_lock = threading.Lock()

def get_history() -> ObservationHistory:
    """Get global ObservationHistory instance (thread-safe)."""
    global _history_instance
    if _history_instance is None:
        with _history_lock:
            if _history_instance is None:
                _history_instance = ObservationHistory()
    return _history_instance
