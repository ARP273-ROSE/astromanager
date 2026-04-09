#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - EQUIPMENT PERFORMANCE ANALYSIS
================================================================================
Computes per-equipment-combo statistics (telescope + camera + filter)
from N.I.N.A. exposure data or observation history.
================================================================================
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class EquipmentPerformance:
    """Analyze equipment performance by telescope+camera+filter combo."""

    def __init__(self):
        from core.database import get_db
        self.db = get_db()

    def compute_from_nina_data(self) -> List[Dict]:
        """Compute performance stats from nina_exposures table.

        Returns list of dicts per combo with:
        telescope, camera, filter_name, median_hfr, median_fwhm,
        median_eccentricity, best_hfr, frame_count
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT telescope, camera, filter_name,
                       hfr, fwhm, eccentricity
                FROM nina_exposures
                WHERE telescope IS NOT NULL AND camera IS NOT NULL
                ORDER BY telescope, camera, filter_name
            """)
            rows = cursor.fetchall()

        if not rows:
            return []

        # Group by combo
        combos = {}
        for row in rows:
            key = (row['telescope'] or 'Unknown',
                   row['camera'] or 'Unknown',
                   row['filter_name'] or 'Unknown')
            if key not in combos:
                combos[key] = {'hfr': [], 'fwhm': [], 'ecc': []}
            if row['hfr'] is not None:
                combos[key]['hfr'].append(row['hfr'])
            if row['fwhm'] is not None:
                combos[key]['fwhm'].append(row['fwhm'])
            if row['eccentricity'] is not None:
                combos[key]['ecc'].append(row['eccentricity'])

        results = []
        for (telescope, camera, filter_name), data in sorted(combos.items()):
            result = {
                'telescope': telescope,
                'camera': camera,
                'filter_name': filter_name,
                'frame_count': max(len(data['hfr']), len(data['fwhm']), 1),
                'median_hfr': None,
                'median_fwhm': None,
                'median_eccentricity': None,
                'best_hfr': None,
            }

            if NUMPY_AVAILABLE:
                if data['hfr']:
                    arr = np.array(data['hfr'])
                    result['median_hfr'] = round(float(np.median(arr)), 3)
                    result['best_hfr'] = round(float(np.min(arr)), 3)
                if data['fwhm']:
                    result['median_fwhm'] = round(float(np.median(data['fwhm'])), 3)
                if data['ecc']:
                    result['median_eccentricity'] = round(float(np.median(data['ecc'])), 3)
            else:
                if data['hfr']:
                    s = sorted(data['hfr'])
                    result['median_hfr'] = round(s[len(s) // 2], 3)
                    result['best_hfr'] = round(s[0], 3)
                if data['fwhm']:
                    s = sorted(data['fwhm'])
                    result['median_fwhm'] = round(s[len(s) // 2], 3)
                if data['ecc']:
                    s = sorted(data['ecc'])
                    result['median_eccentricity'] = round(s[len(s) // 2], 3)

            results.append(result)

        # Cache to DB
        self._cache_results(results)

        return results

    def compute_from_observations(self) -> List[Dict]:
        """Fallback: compute stats from observations table."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT telescope, camera, filter,
                       hfr, fwhm
                FROM observations
                WHERE telescope IS NOT NULL AND camera IS NOT NULL
            """)
            rows = cursor.fetchall()

        if not rows:
            return []

        combos = {}
        for row in rows:
            key = (row['telescope'] or 'Unknown',
                   row['camera'] or 'Unknown',
                   row['filter'] or 'Unknown')
            if key not in combos:
                combos[key] = {'hfr': [], 'fwhm': [], 'count': 0}
            combos[key]['count'] += 1
            if row['hfr'] is not None:
                combos[key]['hfr'].append(row['hfr'])
            if row['fwhm'] is not None:
                combos[key]['fwhm'].append(row['fwhm'])

        results = []
        for (telescope, camera, filter_name), data in sorted(combos.items()):
            result = {
                'telescope': telescope,
                'camera': camera,
                'filter_name': filter_name,
                'frame_count': data['count'],
                'median_hfr': None,
                'median_fwhm': None,
                'median_eccentricity': None,
                'best_hfr': None,
            }
            if data['hfr']:
                s = sorted(data['hfr'])
                result['median_hfr'] = round(s[len(s) // 2], 3)
                result['best_hfr'] = round(s[0], 3)
            if data['fwhm']:
                s = sorted(data['fwhm'])
                result['median_fwhm'] = round(s[len(s) // 2], 3)

            results.append(result)

        return results

    def get_performance_table(self) -> List[Dict]:
        """Get cached equipment performance from DB."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT telescope, camera, filter_name,
                       median_hfr, median_fwhm, median_eccentricity,
                       best_hfr, frame_count
                FROM equipment_performance
                ORDER BY telescope, camera, filter_name
            """)
            return [dict(row) for row in cursor.fetchall()]

    def _cache_results(self, results: List[Dict]):
        """Cache computed results to DB."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            for r in results:
                cursor.execute("""
                    INSERT OR REPLACE INTO equipment_performance
                    (telescope, camera, filter_name, median_hfr, median_fwhm,
                     median_eccentricity, best_hfr, frame_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r['telescope'], r['camera'], r['filter_name'],
                    r.get('median_hfr'), r.get('median_fwhm'),
                    r.get('median_eccentricity'), r.get('best_hfr'),
                    r.get('frame_count', 0),
                ))
