#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - DATABASE MANAGER
================================================================================
SQLite database management for target tracking, weather cache, and historical data.
Provides thread-safe access and automatic schema migrations.
================================================================================
"""

import os
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)

# Database location
DB_DIR = Path.home() / '.astromanager'
DB_PATH = DB_DIR / 'astromanager.db'
DB_BACKUP_PATH = DB_DIR / 'astromanager_backup.db'

# Ensure database directory exists with restrictive permissions
import platform as _platform
try:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    if _platform.system() != 'Windows':
        import os as _os
        _os.chmod(str(DB_DIR), 0o700)
except OSError:
    pass

# Thread-local storage for database connections
_thread_local = threading.local()


class DatabaseManager:
    """Thread-safe SQLite database manager"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern with thread-safe initialization"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize database manager"""
        if self._initialized:
            return

        self.db_path = DB_PATH
        self._initialized = True
        self.init_database()

    @contextmanager
    def get_connection(self):
        """
        Get thread-local database connection with context manager.
        Supports nesting: only the outermost context commits/rollbacks.

        Usage:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM targets")
        """
        if not hasattr(_thread_local, 'connection') or _thread_local.connection is None:
            _thread_local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            _thread_local.connection.row_factory = sqlite3.Row
            # Set restrictive permissions on DB file
            if _platform.system() != 'Windows':
                try:
                    os.chmod(str(self.db_path), 0o600)
                except OSError:
                    pass

            # Performance optimizations
            cursor = _thread_local.connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=10000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA foreign_keys=ON")

        # Track nesting depth — only outermost context commits/rollbacks
        if not hasattr(_thread_local, '_depth'):
            _thread_local._depth = 0
        _thread_local._depth += 1

        try:
            yield _thread_local.connection
        except Exception as e:
            _thread_local._depth -= 1
            if _thread_local._depth == 0:
                _thread_local.connection.rollback()
            logger.error(f"Database error: {e}")
            raise
        else:
            _thread_local._depth -= 1
            if _thread_local._depth == 0:
                _thread_local.connection.commit()

    def close_connection(self):
        """Close the thread-local database connection if open."""
        if hasattr(_thread_local, 'connection') and _thread_local.connection is not None:
            try:
                _thread_local.connection.close()
            except Exception:
                pass
            _thread_local.connection = None
            _thread_local._depth = 0

    def init_database(self):
        """Initialize database schema with integrity check and recovery"""
        # Check integrity first — recover from backup if corrupt
        try:
            self._check_integrity()
        except Exception as e:
            logger.error(f"Database integrity check failed: {e}")
            self._attempt_recovery()

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Version table for schema migrations
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Targets table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    canonical_name TEXT,
                    ra REAL,
                    dec REAL,
                    object_type TEXT,
                    simbad_data TEXT,
                    first_observed DATE,
                    last_observed DATE,
                    total_exposure_time REAL DEFAULT 0,
                    total_frames INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Observations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_id INTEGER NOT NULL,
                    observation_date DATE NOT NULL,
                    filter TEXT,
                    exposure_time REAL,
                    frame_count INTEGER,
                    setup TEXT,
                    telescope TEXT,
                    camera TEXT,
                    hfr REAL,
                    fwhm REAL,
                    temperature REAL,
                    weather_data TEXT,
                    file_paths TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (target_id) REFERENCES targets(id) ON DELETE CASCADE
                )
            """)

            # Weather cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS weather_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    observation_date DATE NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    weather_data TEXT NOT NULL,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(observation_date, latitude, longitude)
                )
            """)

            # Header cache table (for performance)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS header_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_hash TEXT,
                    header_data TEXT NOT NULL,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Analysis results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folder_path TEXT NOT NULL,
                    analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    file_count INTEGER,
                    total_exposure_time REAL,
                    results_data TEXT,
                    output_folder TEXT
                )
            """)

            # Create indexes (idx_targets_name omitted: UNIQUE on name already creates one)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_targets_canonical ON targets(canonical_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_target ON observations(target_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_date ON observations(observation_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_weather_date ON weather_cache(observation_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_header_path ON header_cache(file_path)")

            # Prevent duplicate observations at the database level.
            # Uses COALESCE to treat NULL as '' for dedup matching.
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_obs_dedup
                ON observations(
                    target_id, observation_date,
                    COALESCE(filter, ''), COALESCE(telescope, ''), COALESCE(camera, '')
                )
            """)

            # Set schema version
            cursor.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (1)")

            logger.info("Database initialized successfully")

    def _check_integrity(self):
        """Run PRAGMA integrity_check on the database"""
        if not self.db_path.exists():
            return
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()
            if result[0] != 'ok':
                raise sqlite3.DatabaseError(f"Integrity check failed: {result[0]}")
        finally:
            conn.close()

    def _attempt_recovery(self):
        """Attempt to recover from a corrupted database using backup"""
        import shutil
        if DB_BACKUP_PATH.exists():
            logger.warning("Attempting database recovery from backup...")
            try:
                # Verify backup integrity first
                conn = sqlite3.connect(DB_BACKUP_PATH, timeout=10.0)
                result = conn.execute("PRAGMA integrity_check").fetchone()
                conn.close()
                if result[0] == 'ok':
                    shutil.copy2(str(DB_BACKUP_PATH), str(self.db_path))
                    logger.info("Database recovered from backup")
                    return
                else:
                    logger.error("Backup is also corrupt")
            except Exception as e:
                logger.error(f"Recovery from backup failed: {e}")

        # Last resort: delete corrupt DB and recreate from scratch
        logger.warning("Recreating database from scratch")
        try:
            self.db_path.unlink(missing_ok=True)
        except Exception:
            pass

    def backup_database(self) -> Optional[Path]:
        """Create database backup using SQLite backup API (WAL-safe)"""
        if not self.db_path.exists():
            return None
        src = None
        dst = None
        try:
            import sqlite3 as _sqlite3
            src = _sqlite3.connect(self.db_path, timeout=30.0)
            dst = _sqlite3.connect(str(DB_BACKUP_PATH))
            src.backup(dst)
            logger.info(f"Database backed up to {DB_BACKUP_PATH}")
            return DB_BACKUP_PATH
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            return None
        finally:
            if dst:
                try:
                    dst.close()
                except Exception:
                    pass
            if src:
                try:
                    src.close()
                except Exception:
                    pass

    # =========================================================================
    # Target Management
    # =========================================================================

    def add_target(self, name: str, canonical_name: Optional[str] = None,
                   ra: Optional[float] = None, dec: Optional[float] = None,
                   object_type: Optional[str] = None,
                   simbad_data: Optional[Dict] = None) -> int:
        """Add or update target in database.

        Deduplication: if canonical_name is provided and another target
        already shares the same canonical_name, merge into the existing
        target instead of creating a duplicate entry.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Strip SIMBAD "NAME " prefix (e.g. "NAME Rosette Nebula" → "Rosette Nebula")
            if canonical_name and canonical_name.startswith('NAME '):
                canonical_name = canonical_name[5:].strip()

            simbad_json = json.dumps(simbad_data) if simbad_data else None

            # Prevent duplicates: if we have a canonical_name, check if
            # another target already uses it (same object, different name).
            if canonical_name:
                cursor.execute(
                    "SELECT id FROM targets WHERE canonical_name = ? AND name != ?",
                    (canonical_name, name)
                )
                existing = cursor.fetchone()
                if existing:
                    # Merge into the existing target
                    cursor.execute("""
                        UPDATE targets SET
                            ra = COALESCE(?, ra),
                            dec = COALESCE(?, dec),
                            object_type = COALESCE(?, object_type),
                            simbad_data = COALESCE(?, simbad_data),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (ra, dec, object_type, simbad_json, existing[0]))
                    return existing[0]

            cursor.execute("""
                INSERT INTO targets (name, canonical_name, ra, dec, object_type, simbad_data)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    canonical_name = COALESCE(excluded.canonical_name, canonical_name),
                    ra = COALESCE(excluded.ra, ra),
                    dec = COALESCE(excluded.dec, dec),
                    object_type = COALESCE(excluded.object_type, object_type),
                    simbad_data = COALESCE(excluded.simbad_data, simbad_data),
                    updated_at = CURRENT_TIMESTAMP
            """, (name, canonical_name, ra, dec, object_type, simbad_json))

            cursor.execute("SELECT id FROM targets WHERE name = ?", (name,))
            target_id = cursor.fetchone()[0]

            return target_id

    def get_target(self, name: str) -> Optional[Dict]:
        """Get target by name"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM targets WHERE name = ? OR canonical_name = ?", (name, name))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    def get_all_targets(self) -> List[Dict]:
        """Get all targets"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM targets ORDER BY last_observed DESC")
            return [dict(row) for row in cursor.fetchall()]

    def update_target_stats(self, target_id: int):
        """Update target statistics using a single aggregate query"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Single scan instead of 4 correlated subqueries
            cursor.execute("""
                SELECT COALESCE(SUM(exposure_time), 0),
                       COALESCE(SUM(frame_count), 0),
                       MIN(observation_date),
                       MAX(observation_date)
                FROM observations WHERE target_id = ?
            """, (target_id,))
            row = cursor.fetchone()
            cursor.execute("""
                UPDATE targets SET
                    total_exposure_time = ?,
                    total_frames = ?,
                    first_observed = ?,
                    last_observed = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (row[0], row[1], row[2], row[3], target_id))

    # =========================================================================
    # Observation Management
    # =========================================================================

    def add_observation(self, target_id: int, observation_date: str,
                       filter_name: Optional[str] = None,
                       exposure_time: Optional[float] = None,
                       frame_count: Optional[int] = None,
                       setup: Optional[str] = None,
                       **kwargs) -> int:
        """Add observation record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO observations (
                    target_id, observation_date, filter, exposure_time,
                    frame_count, setup, telescope, camera, hfr, fwhm,
                    temperature, weather_data, file_paths, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                target_id, observation_date, filter_name, exposure_time,
                frame_count, setup,
                kwargs.get('telescope'), kwargs.get('camera'),
                kwargs.get('hfr'), kwargs.get('fwhm'),
                kwargs.get('temperature'),
                json.dumps(kwargs.get('weather_data')) if kwargs.get('weather_data') else None,
                json.dumps(kwargs.get('file_paths')) if kwargs.get('file_paths') else None,
                kwargs.get('notes')
            ))

            obs_id = cursor.lastrowid

            # Update target stats
            self.update_target_stats(target_id)

            return obs_id

    def get_observations(self, target_id: int) -> List[Dict]:
        """Get all observations for a target"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM observations
                WHERE target_id = ?
                ORDER BY observation_date DESC
            """, (target_id,))
            return [dict(row) for row in cursor.fetchall()]

    def delete_target(self, target_id: int):
        """Delete a target and all its observations (CASCADE)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM observations WHERE target_id = ?", (target_id,))
            cursor.execute("DELETE FROM targets WHERE id = ?", (target_id,))

    def delete_all_history(self):
        """Delete all observations and targets."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM observations")
            cursor.execute("DELETE FROM targets")

    # =========================================================================
    # Weather Cache
    # =========================================================================

    def get_weather(self, date: str, latitude: float, longitude: float) -> Optional[Dict]:
        """Get cached weather data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT weather_data FROM weather_cache
                WHERE observation_date = ? AND latitude = ? AND longitude = ?
            """, (date, latitude, longitude))

            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row['weather_data'])
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Corrupt weather cache for {date}, removing")
                    cursor.execute("DELETE FROM weather_cache WHERE observation_date = ? AND latitude = ? AND longitude = ?", (date, latitude, longitude))
                    return None
            return None

    def cache_weather(self, date: str, latitude: float, longitude: float, weather_data: Dict):
        """Cache weather data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO weather_cache (observation_date, latitude, longitude, weather_data)
                VALUES (?, ?, ?, ?)
            """, (date, latitude, longitude, json.dumps(weather_data)))

    # =========================================================================
    # Header Cache
    # =========================================================================

    def get_cached_header(self, file_path: str) -> Optional[Dict]:
        """Get cached header data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT header_data FROM header_cache WHERE file_path = ?
            """, (file_path,))

            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row['header_data'])
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Corrupt header cache for {file_path}, removing")
                    cursor.execute("DELETE FROM header_cache WHERE file_path = ?", (file_path,))
                    return None
            return None

    def cache_header(self, file_path: str, header_data: Dict, file_hash: Optional[str] = None):
        """Cache header data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO header_cache (file_path, file_hash, header_data)
                VALUES (?, ?, ?)
            """, (file_path, file_hash, json.dumps(header_data)))

    # =========================================================================
    # Utility Functions
    # =========================================================================

    def vacuum(self):
        """Optimize database (VACUUM)"""
        try:
            # VACUUM cannot run inside a transaction — use a separate autocommit connection
            conn = sqlite3.connect(self.db_path, isolation_level=None, timeout=30.0)
            conn.execute("VACUUM")
            conn.close()
            logger.info("Database vacuumed")
        except Exception as e:
            logger.error(f"VACUUM failed: {e}")

    def get_database_size(self) -> int:
        """Get database size in bytes"""
        if self.db_path.exists():
            return self.db_path.stat().st_size
        return 0

    def clear_old_cache(self, days: int = 90):
        """Clear cache older than specified days"""
        if not isinstance(days, int) or days < 1:
            days = 90
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM header_cache
                WHERE cached_at < datetime('now', '-' || ? || ' days')
            """, (days,))
            deleted = cursor.rowcount
            logger.info(f"Cleared {deleted} old cache entries")


# Global singleton instance
_db_manager = None
_db_lock = threading.Lock()

def get_db() -> DatabaseManager:
    """Get global database manager instance (thread-safe)"""
    global _db_manager
    if _db_manager is None:
        with _db_lock:
            if _db_manager is None:
                _db_manager = DatabaseManager()
    return _db_manager
