#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - WEATHER API MODULE
================================================================================
Weather data retrieval (historical + forecast) via Open-Meteo API (free, no key).
Target visibility calculations (rise/set/transit times).
Caches results in SQLite for offline access.
================================================================================
"""

import json
import math
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple

logger = logging.getLogger(__name__)

# Open-Meteo API endpoints (free, no API key required)
OPEN_METEO_HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Weather classification thresholds
CLOUD_THRESHOLDS = {
    'Clear': (0, 10),
    'Mostly Clear': (10, 25),
    'Partly Cloudy': (25, 50),
    'Mostly Cloudy': (50, 75),
    'Overcast': (75, 100),
}


class WeatherAPIClient:
    """Weather data client using Open-Meteo API with SQLite caching"""

    def __init__(self):
        self._cache_duration_days = 365  # Historical data doesn't change

    # =========================================================================
    # HISTORICAL WEATHER (past observation nights)
    # =========================================================================

    def fetch_weather_historical(self, date_str: str,
                                  latitude: float,
                                  longitude: float,
                                  hour: int = 22) -> Optional[Dict]:
        """
        Fetch historical weather data for a specific date and location.

        Args:
            date_str: Date in YYYY-MM-DD format
            latitude: Observatory latitude
            longitude: Observatory longitude
            hour: Hour of observation (default 22:00 local)

        Returns:
            dict with weather data or None on failure
        """
        cached = self._get_cached(date_str, latitude, longitude)
        if cached:
            return cached

        weather = self._fetch_historical_from_api(date_str, latitude, longitude, hour)

        if weather:
            self._cache_result(date_str, latitude, longitude, weather)

        return weather

    def _fetch_historical_from_api(self, date_str: str, latitude: float,
                                    longitude: float, hour: int = 22) -> Optional[Dict]:
        """Fetch weather data from Open-Meteo Historical API"""
        try:
            import urllib.request
            import urllib.parse

            params = urllib.parse.urlencode({
                'latitude': latitude,
                'longitude': longitude,
                'start_date': date_str,
                'end_date': date_str,
                'hourly': 'temperature_2m,cloud_cover,precipitation,wind_speed_10m,relative_humidity_2m,dew_point_2m',
                'timezone': 'auto',
            })

            url = f"{OPEN_METEO_HISTORICAL_URL}?{params}"

            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'AstroManager/1.0')

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            return self._parse_hourly_data(data, date_str, hour, 'Open-Meteo Historical')

        except Exception as e:
            logger.warning(f"Weather API error for {date_str}: {e}")
            return None

    # =========================================================================
    # WEATHER FORECAST (next 7 days)
    # =========================================================================

    def fetch_forecast(self, latitude: float, longitude: float,
                       days: int = 7) -> Optional[List[Dict]]:
        """
        Fetch weather forecast for upcoming nights.

        Args:
            latitude: Observatory latitude
            longitude: Observatory longitude
            days: Number of days to forecast (1-16, default 7)

        Returns:
            List of nightly forecast dicts or None on failure
        """
        try:
            import urllib.request
            import urllib.parse

            days = min(max(1, days), 16)

            params = urllib.parse.urlencode({
                'latitude': latitude,
                'longitude': longitude,
                'hourly': 'temperature_2m,cloud_cover,precipitation_probability,precipitation,wind_speed_10m,relative_humidity_2m,dew_point_2m,visibility',
                'forecast_days': days,
                'timezone': 'auto',
            })

            url = f"{OPEN_METEO_FORECAST_URL}?{params}"

            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'AstroManager/1.0')

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            if 'hourly' not in data:
                return None

            hourly = data['hourly']
            times = hourly.get('time', [])

            # Group by night (20:00 to 05:00 next day)
            nightly_forecasts = []
            processed_dates = set()

            for i, t in enumerate(times):
                try:
                    dt = datetime.strptime(t, "%Y-%m-%dT%H:%M")
                except (ValueError, TypeError):
                    continue

                # Nighttime hours: 20-23, 0-5
                if dt.hour < 6 or dt.hour >= 20:
                    night_date = dt.strftime("%Y-%m-%d") if dt.hour >= 20 else (dt - timedelta(days=1)).strftime("%Y-%m-%d")

                    if night_date not in processed_dates:
                        processed_dates.add(night_date)
                        # Collect all nighttime hours for this night
                        night_data = self._collect_night_hours(hourly, times, night_date)
                        if night_data:
                            nightly_forecasts.append(night_data)

            return nightly_forecasts if nightly_forecasts else None

        except Exception as e:
            logger.warning(f"Forecast API error: {e}")
            return None

    def _collect_night_hours(self, hourly: Dict, times: List[str],
                              night_date: str) -> Optional[Dict]:
        """Collect and average nighttime hours (20:00-05:00) for a given night"""
        night_temps = []
        night_clouds = []
        night_precip_prob = []
        night_precip = []
        night_wind = []
        night_humidity = []
        night_dew = []
        night_visibility = []

        for i, t in enumerate(times):
            try:
                dt = datetime.strptime(t, "%Y-%m-%dT%H:%M")
            except (ValueError, TypeError):
                continue

            # Check if this hour belongs to this night
            is_evening = dt.strftime("%Y-%m-%d") == night_date and dt.hour >= 20
            next_day = (datetime.strptime(night_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            is_morning = dt.strftime("%Y-%m-%d") == next_day and dt.hour < 6

            if is_evening or is_morning:
                def _safe_get(key, idx):
                    vals = hourly.get(key, [])
                    return vals[idx] if idx < len(vals) and vals[idx] is not None else None

                temp = _safe_get('temperature_2m', i)
                if temp is not None:
                    night_temps.append(temp)
                cloud = _safe_get('cloud_cover', i)
                if cloud is not None:
                    night_clouds.append(cloud)
                pp = _safe_get('precipitation_probability', i)
                if pp is not None:
                    night_precip_prob.append(pp)
                p = _safe_get('precipitation', i)
                if p is not None:
                    night_precip.append(p)
                w = _safe_get('wind_speed_10m', i)
                if w is not None:
                    night_wind.append(w)
                h = _safe_get('relative_humidity_2m', i)
                if h is not None:
                    night_humidity.append(h)
                d = _safe_get('dew_point_2m', i)
                if d is not None:
                    night_dew.append(d)
                v = _safe_get('visibility', i)
                if v is not None:
                    night_visibility.append(v)

        if not night_clouds:
            return None

        def _avg(lst):
            return sum(lst) / len(lst) if lst else None

        avg_cloud = _avg(night_clouds)
        avg_precip = _avg(night_precip)
        classification = self._classify_weather(avg_cloud, avg_precip)
        avg_temp = _avg(night_temps)
        avg_dew = _avg(night_dew)
        seeing_quality = self._estimate_seeing_quality(
            avg_cloud, _avg(night_wind), _avg(night_humidity), avg_temp, avg_dew
        )

        # Count clear hours (cloud < 25%)
        clear_hours = sum(1 for c in night_clouds if c < 25)
        total_hours = len(night_clouds)

        return {
            'night_date': night_date,
            'temperature_c': round(avg_temp, 1) if avg_temp is not None else None,
            'cloud_cover_pct': round(avg_cloud, 1) if avg_cloud is not None else None,
            'cloud_cover_min': round(min(night_clouds), 1) if night_clouds else None,
            'cloud_cover_max': round(max(night_clouds), 1) if night_clouds else None,
            'precipitation_prob_pct': round(max(night_precip_prob), 0) if night_precip_prob else None,
            'precipitation_mm': round(sum(night_precip), 1) if night_precip else 0,
            'wind_speed_kmh': round(_avg(night_wind), 1) if night_wind else None,
            'humidity_pct': round(_avg(night_humidity), 1) if night_humidity else None,
            'dew_point_c': round(avg_dew, 1) if avg_dew is not None else None,
            'visibility_m': round(_avg(night_visibility), 0) if night_visibility else None,
            'classification': classification,
            'seeing_quality': seeing_quality,
            'clear_hours': clear_hours,
            'total_hours': total_hours,
            'imaging_score': self._compute_imaging_score(
                avg_cloud, _avg(night_wind), _avg(night_humidity),
                avg_temp, avg_dew, clear_hours, total_hours
            ),
            'source': 'Open-Meteo Forecast',
        }

    def _compute_imaging_score(self, cloud_cover, wind_speed, humidity,
                                temperature, dew_point, clear_hours,
                                total_hours) -> int:
        """Compute an imaging suitability score (0-100)"""
        score = 100

        if cloud_cover is not None:
            if cloud_cover > 75:
                score -= 60
            elif cloud_cover > 50:
                score -= 40
            elif cloud_cover > 25:
                score -= 20
            elif cloud_cover > 10:
                score -= 5

        if wind_speed is not None:
            if wind_speed > 40:
                score -= 30
            elif wind_speed > 25:
                score -= 20
            elif wind_speed > 15:
                score -= 10

        if humidity is not None:
            if humidity > 95:
                score -= 20
            elif humidity > 85:
                score -= 10

        if temperature is not None and dew_point is not None:
            margin = temperature - dew_point
            if margin < 2:
                score -= 15
            elif margin < 4:
                score -= 5

        if total_hours > 0:
            clear_ratio = clear_hours / total_hours
            score = int(score * (0.5 + 0.5 * clear_ratio))

        return max(0, min(100, score))

    # =========================================================================
    # TARGET VISIBILITY (rise/set/transit calculations)
    # =========================================================================

    @staticmethod
    def compute_target_visibility(ra_deg: float, dec_deg: float,
                                   latitude: float, longitude: float,
                                   date_str: str,
                                   min_altitude: float = 20.0) -> Optional[Dict]:
        """
        Compute target visibility for a given night.

        Uses basic spherical astronomy (no external deps required).

        Args:
            ra_deg: Target Right Ascension in degrees
            dec_deg: Target Declination in degrees
            latitude: Observer latitude in degrees
            longitude: Observer longitude in degrees
            date_str: Date string YYYY-MM-DD
            min_altitude: Minimum altitude above horizon in degrees (default 20)

        Returns:
            dict with rise_time, set_time, transit_time, max_altitude,
            hours_above_min, is_circumpolar, never_rises
        """
        try:
            lat_rad = math.radians(latitude)
            dec_rad = math.radians(dec_deg)
            ra_hours = ra_deg / 15.0

            # Julian date for date at 0h UT
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            jd = _julian_date(dt.year, dt.month, dt.day)

            # Local Sidereal Time at midnight
            lst_midnight = _local_sidereal_time(jd, longitude)

            # Max altitude at transit
            max_alt = math.degrees(math.asin(
                math.sin(lat_rad) * math.sin(dec_rad) +
                math.cos(lat_rad) * math.cos(dec_rad)
            ))

            # Check circumpolar / never rises
            cos_ha_limit = (
                math.sin(math.radians(min_altitude)) -
                math.sin(lat_rad) * math.sin(dec_rad)
            ) / (math.cos(lat_rad) * math.cos(dec_rad))

            if abs(cos_ha_limit) > 1:
                if max_alt > min_altitude:
                    return {
                        'date': date_str,
                        'is_circumpolar': True,
                        'never_rises': False,
                        'max_altitude': round(max_alt, 1),
                        'hours_above_min': 24.0,
                        'transit_time': _ha_to_time(0, ra_hours, lst_midnight, date_str),
                        'rise_time': None,
                        'set_time': None,
                        'imaging_window': "All night",
                    }
                else:
                    return {
                        'date': date_str,
                        'is_circumpolar': False,
                        'never_rises': True,
                        'max_altitude': round(max_alt, 1),
                        'hours_above_min': 0.0,
                        'transit_time': None,
                        'rise_time': None,
                        'set_time': None,
                        'imaging_window': "Not visible",
                    }

            # Hour angle at rise/set (for min_altitude)
            ha_limit = math.degrees(math.acos(cos_ha_limit)) / 15.0  # in hours

            # Transit hour angle = 0
            transit_lst = ra_hours
            transit_time = _ha_to_time(0, ra_hours, lst_midnight, date_str)
            rise_time = _ha_to_time(-ha_limit, ra_hours, lst_midnight, date_str)
            set_time = _ha_to_time(ha_limit, ra_hours, lst_midnight, date_str)

            hours_above = 2 * ha_limit

            # Filter for nighttime only (astronomical twilight: sun alt < -18)
            # Approximate: use 20:00 to 05:00 local as imaging window
            night_start_h = 20.0
            night_end_h = 5.0  # next day

            return {
                'date': date_str,
                'is_circumpolar': False,
                'never_rises': False,
                'max_altitude': round(max_alt, 1),
                'hours_above_min': round(hours_above, 1),
                'transit_time': transit_time,
                'rise_time': rise_time,
                'set_time': set_time,
                'imaging_window': f"{rise_time} - {set_time}" if rise_time and set_time else "Unknown",
            }

        except Exception as e:
            logger.warning(f"Visibility calculation error: {e}")
            return None

    # =========================================================================
    # CLASSIFICATION & SCORING
    # =========================================================================

    def _classify_weather(self, cloud_cover: Optional[float],
                          precipitation: Optional[float]) -> str:
        """Classify weather conditions"""
        if precipitation and precipitation > 0.1:
            return "Precipitation"

        if cloud_cover is None:
            return "Unknown"

        for name, (low, high) in CLOUD_THRESHOLDS.items():
            if low <= cloud_cover < high:
                return name

        return "Overcast"

    def _estimate_seeing_quality(self, cloud_cover, wind_speed,
                                  humidity, temperature, dew_point) -> str:
        """Estimate seeing/imaging quality based on weather parameters"""
        score = 100

        if cloud_cover is not None:
            if cloud_cover > 50:
                return "Poor"
            elif cloud_cover > 25:
                score -= 30
            elif cloud_cover > 10:
                score -= 10

        if wind_speed is not None:
            if wind_speed > 30:
                score -= 40
            elif wind_speed > 20:
                score -= 25
            elif wind_speed > 10:
                score -= 10

        if humidity is not None:
            if humidity > 90:
                score -= 30
            elif humidity > 80:
                score -= 15

        if temperature is not None and dew_point is not None:
            dew_margin = temperature - dew_point
            if dew_margin < 2:
                score -= 25
            elif dew_margin < 5:
                score -= 10

        if score >= 80:
            return "Excellent"
        elif score >= 60:
            return "Good"
        elif score >= 40:
            return "Fair"
        else:
            return "Poor"

    def _parse_hourly_data(self, data: Dict, date_str: str, hour: int,
                            source: str) -> Optional[Dict]:
        """Parse hourly data from Open-Meteo response"""
        if 'hourly' not in data:
            return None

        hourly = data['hourly']
        times = hourly.get('time', [])

        target_hour = f"{date_str}T{hour:02d}:00"
        idx = None
        for i, t in enumerate(times):
            if t == target_hour:
                idx = i
                break

        if idx is None:
            for h in [22, 23, 0, 1, 2, 21, 20]:
                target = f"{date_str}T{h:02d}:00"
                for i, t in enumerate(times):
                    if t == target:
                        idx = i
                        break
                if idx is not None:
                    break

        if idx is None and times:
            idx = min(len(times) - 1, hour)

        if idx is None:
            return None

        temperature = hourly.get('temperature_2m', [None])[idx]
        cloud_cover = hourly.get('cloud_cover', [None])[idx]
        precipitation = hourly.get('precipitation', [None])[idx]
        wind_speed = hourly.get('wind_speed_10m', [None])[idx]
        humidity = hourly.get('relative_humidity_2m', [None])[idx]
        dew_point = hourly.get('dew_point_2m', [None])[idx]

        classification = self._classify_weather(cloud_cover, precipitation)
        seeing_quality = self._estimate_seeing_quality(
            cloud_cover, wind_speed, humidity, temperature, dew_point
        )

        return {
            'date': date_str,
            'temperature_c': temperature,
            'cloud_cover_pct': cloud_cover,
            'precipitation_mm': precipitation,
            'wind_speed_kmh': wind_speed,
            'humidity_pct': humidity,
            'dew_point_c': dew_point,
            'classification': classification,
            'seeing_quality': seeing_quality,
            'source': source,
        }

    # =========================================================================
    # CACHE MANAGEMENT
    # =========================================================================

    def _get_cached(self, date_str: str, latitude: float,
                    longitude: float) -> Optional[Dict]:
        """Get cached weather data from database"""
        try:
            from core.database import get_db
            db = get_db()
            return db.get_weather(date_str, latitude, longitude)
        except Exception:
            return None

    def _cache_result(self, date_str: str, latitude: float,
                      longitude: float, weather: Dict):
        """Cache weather data to database"""
        try:
            from core.database import get_db
            db = get_db()
            db.cache_weather(date_str, latitude, longitude, weather)
        except Exception:
            pass

    def fetch_batch(self, dates: List[str], latitude: float,
                    longitude: float,
                    progress_callback=None) -> Dict[str, Dict]:
        """Fetch weather for multiple dates."""
        results = {}
        total = len(dates)

        for i, date_str in enumerate(dates):
            if progress_callback:
                progress_callback(i + 1, total)

            weather = self.fetch_weather_historical(date_str, latitude, longitude)
            if weather:
                results[date_str] = weather

        return results


# ============================================================================
# ASTRONOMICAL HELPER FUNCTIONS (no external dependencies)
# ============================================================================

def _julian_date(year: int, month: int, day: int) -> float:
    """Compute Julian Date for a given calendar date at 0h UT."""
    if month <= 2:
        year -= 1
        month += 12
    A = int(year / 100)
    B = 2 - A + int(A / 4)
    return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + B - 1524.5


def _local_sidereal_time(jd: float, longitude: float) -> float:
    """Compute Local Sidereal Time in hours for a Julian Date and longitude."""
    T = (jd - 2451545.0) / 36525.0
    # Greenwich Mean Sidereal Time at 0h UT
    gmst = 6.697374558 + 2400.0513369 * T + 0.0000258622 * T * T
    gmst = gmst % 24
    if gmst < 0:
        gmst += 24
    lst = gmst + longitude / 15.0
    lst = lst % 24
    if lst < 0:
        lst += 24
    return lst


def _ha_to_time(ha_hours: float, ra_hours: float, lst_midnight: float,
                 date_str: str) -> Optional[str]:
    """Convert hour angle to local time string (HH:MM)."""
    try:
        target_lst = (ra_hours + ha_hours) % 24
        dt_hours = (target_lst - lst_midnight) % 24
        # Adjust so transit near midnight is shown correctly
        if dt_hours > 18:
            dt_hours -= 24
        hour = int(dt_hours) % 24
        minute = int((dt_hours % 1) * 60)
        return f"{hour:02d}:{minute:02d}"
    except Exception:
        return None
