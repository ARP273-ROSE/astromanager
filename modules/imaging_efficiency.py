#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - IMAGING EFFICIENCY CALCULATOR
================================================================================
Calculates astronomical dark hours (sun altitude < -18 degrees) and
imaging efficiency ratio (integration time / dark hours) per session.
Uses astropy for precise solar position calculations.
================================================================================
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Feature-gate astropy imports
try:
    from astropy.coordinates import EarthLocation, AltAz, get_sun
    from astropy.time import Time
    import astropy.units as u
    ASTROPY_AVAILABLE = True
except ImportError:
    ASTROPY_AVAILABLE = False
    logger.info("astropy not available — imaging efficiency calculation disabled")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class ImagingEfficiencyCalculator:
    """Calculates dark hours and imaging efficiency per session."""

    def __init__(self):
        from core.database import get_db
        self.db = get_db()
        from core.config import get_config
        self.config = get_config()

    def calculate_dark_hours(self, date_str: str,
                             latitude: float, longitude: float,
                             elevation_m: float = 0.0) -> Optional[float]:
        """Calculate astronomical dark hours for a given date and location.

        Astronomical darkness = sun altitude < -18 degrees.
        Samples sun position every 10 minutes from noon to noon.

        Args:
            date_str: Date string 'YYYY-MM-DD' (the evening date)
            latitude: Observatory latitude in degrees
            longitude: Observatory longitude in degrees
            elevation_m: Observatory elevation in meters

        Returns:
            Dark hours as float, or None if astropy unavailable
        """
        if not ASTROPY_AVAILABLE or not NUMPY_AVAILABLE:
            return None

        try:
            location = EarthLocation(
                lat=latitude * u.deg,
                lon=longitude * u.deg,
                height=elevation_m * u.m
            )

            # Sample from noon day-of to noon next day (covers the full night)
            start_dt = datetime.strptime(date_str, '%Y-%m-%d').replace(hour=12, minute=0)
            end_dt = start_dt + timedelta(days=1)

            # 144 samples (every 10 minutes over 24 hours)
            n_samples = 144
            times_utc = Time(
                [start_dt + timedelta(minutes=10 * i) for i in range(n_samples)]
            )

            altaz_frame = AltAz(obstime=times_utc, location=location)
            sun_altaz = get_sun(times_utc).transform_to(altaz_frame)
            sun_alt = sun_altaz.alt.deg  # numpy array of altitudes

            # Count samples where sun is below -18 degrees
            dark_samples = np.sum(sun_alt < -18.0)
            dark_hours = dark_samples * (10.0 / 60.0)  # Each sample = 10 minutes

            return round(dark_hours, 2)

        except Exception as e:
            logger.error(f"Error calculating dark hours for {date_str}: {e}")
            return None

    def calculate_efficiency(self, session_date: str,
                             integration_seconds: Optional[float] = None) -> Optional[Dict]:
        """Calculate imaging efficiency for a session.

        Args:
            session_date: Date string 'YYYY-MM-DD'
            integration_seconds: Total integration time. If None, computed from DB.

        Returns:
            Dict with dark_hours, integration_hours, efficiency_pct, or None
        """
        lat = self.config.get('observatory.latitude', 51.4769)
        lon = self.config.get('observatory.longitude', -0.0005)
        elev = self.config.get('observatory.elevation_m', 0)

        # Check cache
        cached = self._get_cached(session_date)
        if cached:
            return cached

        # Calculate dark hours
        dark_hours = self.calculate_dark_hours(session_date, lat, lon, elev)
        if dark_hours is None or dark_hours <= 0:
            return None

        # Get integration time from DB if not provided
        if integration_seconds is None:
            integration_seconds = self._get_integration_from_db(session_date)

        if integration_seconds is None or integration_seconds <= 0:
            integration_seconds = 0.0

        dark_seconds = dark_hours * 3600.0
        efficiency_pct = min(100.0, (integration_seconds / dark_seconds) * 100.0)

        result = {
            'session_date': session_date,
            'dark_hours': dark_hours,
            'integration_hours': round(integration_seconds / 3600.0, 2),
            'integration_seconds': integration_seconds,
            'efficiency_pct': round(efficiency_pct, 1),
            'latitude': lat,
            'longitude': lon,
        }

        # Cache result
        self._cache_result(result)

        return result

    def get_efficiency_history(self, limit: int = 365) -> List[Dict]:
        """Get all cached efficiency records, most recent first."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_date, dark_hours_seconds, integration_seconds,
                       efficiency_pct, latitude, longitude
                FROM imaging_efficiency
                ORDER BY session_date DESC
                LIMIT ?
            """, (limit,))
            results = []
            for row in cursor.fetchall():
                dark_sec = row['dark_hours_seconds'] or 0
                results.append({
                    'session_date': row['session_date'],
                    'dark_hours': round(dark_sec / 3600.0, 2),
                    'integration_hours': round((row['integration_seconds'] or 0) / 3600.0, 2),
                    'efficiency_pct': row['efficiency_pct'] or 0,
                })
            return results

    def compute_batch(self, dates: List[str],
                      progress_callback=None) -> List[Dict]:
        """Compute efficiency for multiple dates."""
        results = []
        for i, date_str in enumerate(dates):
            if progress_callback:
                progress_callback(i, len(dates))
            eff = self.calculate_efficiency(date_str)
            if eff:
                results.append(eff)
        if progress_callback:
            progress_callback(len(dates), len(dates))
        return results

    def _get_integration_from_db(self, session_date: str) -> Optional[float]:
        """Get total integration seconds from nina_exposures or observations."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Try nina_exposures first
            cursor.execute("""
                SELECT SUM(exposure_seconds) FROM nina_exposures
                WHERE session_date = ?
            """, (session_date,))
            row = cursor.fetchone()
            if row and row[0]:
                return float(row[0])

            # Fallback to observations table
            cursor.execute("""
                SELECT SUM(exposure_time) FROM observations
                WHERE observation_date = ?
            """, (session_date,))
            row = cursor.fetchone()
            if row and row[0]:
                return float(row[0])

            return None

    def _get_cached(self, session_date: str) -> Optional[Dict]:
        """Get cached efficiency result."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_date, dark_hours_seconds, integration_seconds,
                       efficiency_pct, latitude, longitude
                FROM imaging_efficiency
                WHERE session_date = ?
            """, (session_date,))
            row = cursor.fetchone()
            if row:
                dark_sec = row['dark_hours_seconds'] or 0
                return {
                    'session_date': row['session_date'],
                    'dark_hours': round(dark_sec / 3600.0, 2),
                    'integration_hours': round((row['integration_seconds'] or 0) / 3600.0, 2),
                    'integration_seconds': row['integration_seconds'] or 0,
                    'efficiency_pct': row['efficiency_pct'] or 0,
                    'latitude': row['latitude'],
                    'longitude': row['longitude'],
                }
            return None

    def _cache_result(self, result: Dict):
        """Cache efficiency result in DB."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO imaging_efficiency
                (session_date, latitude, longitude, dark_hours_seconds,
                 integration_seconds, efficiency_pct)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                result['session_date'],
                result.get('latitude'),
                result.get('longitude'),
                result['dark_hours'] * 3600.0,
                result.get('integration_seconds', 0),
                result['efficiency_pct'],
            ))
