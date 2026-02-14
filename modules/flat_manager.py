#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AstroFileManager - Flat Frame Manager
=======================================
Group flat frames by night/instrument/filter, track which nights have
complete flat sets, link targets to master flats, track PixInsight processing.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Any, Set, Tuple

from .header_editor import (
    read_header, get_header_value, scan_directory, detect_file_type
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Flat group key: (date, telescope, camera, filter, binning, rotation)
# ---------------------------------------------------------------------------

class FlatGroup:
    """Represents a group of flat frames sharing the same characteristics."""
    
    def __init__(self, date: str, telescope: str, camera: str,
                 filter_name: str, binning: str, rotation: float = 0.0):
        self.date = date
        self.telescope = telescope
        self.camera = camera
        self.filter_name = filter_name
        self.binning = binning
        self.rotation = rotation
        self.files: List[str] = []
        self.master_flat_path: Optional[str] = None
        self.master_created: bool = False
        self.linked_targets: Set[str] = set()
        self.temperature: Optional[float] = None
    
    @property
    def key(self) -> str:
        """Unique key for this flat group."""
        rot = f"{self.rotation:.0f}" if self.rotation else "0"
        return f"{self.date}|{self.telescope}|{self.camera}|{self.filter_name}|{self.binning}|{rot}"
    
    @property
    def count(self) -> int:
        return len(self.files)
    
    @property
    def setup_key(self) -> str:
        """Setup key (telescope+camera) for matching with lights."""
        return f"{self.telescope}|{self.camera}"
    
    def to_dict(self) -> dict:
        return {
            'date': self.date,
            'telescope': self.telescope,
            'camera': self.camera,
            'filter': self.filter_name,
            'binning': self.binning,
            'rotation': self.rotation,
            'files': self.files,
            'master_flat_path': self.master_flat_path,
            'master_created': self.master_created,
            'linked_targets': list(self.linked_targets),
            'temperature': self.temperature,
            'count': self.count,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'FlatGroup':
        fg = cls(
            date=data['date'],
            telescope=data['telescope'],
            camera=data['camera'],
            filter_name=data['filter'],
            binning=data['binning'],
            rotation=data.get('rotation', 0.0),
        )
        fg.files = data.get('files', [])
        fg.master_flat_path = data.get('master_flat_path')
        fg.master_created = data.get('master_created', False)
        fg.linked_targets = set(data.get('linked_targets', []))
        fg.temperature = data.get('temperature')
        return fg


# ---------------------------------------------------------------------------
# Flat Manager
# ---------------------------------------------------------------------------

class FlatManager:
    """Manages flat frame organization, grouping, and master flat tracking."""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Args:
            db_path: Path to JSON database for persistence (optional)
        """
        self.groups: Dict[str, FlatGroup] = {}
        self.db_path = db_path
        if db_path and os.path.exists(db_path):
            self.load()
    
    # ----- Scanning -----
    
    def scan_flats(self, folder: str, recursive: bool = True,
                   progress_callback=None) -> int:
        """
        Scan a directory for flat frames and organize into groups.
        Returns number of flat files found.
        """
        all_files = scan_directory(folder, recursive=recursive,
                                    skip_calibration=False, skip_pixinsight=True)
        
        flat_count = 0
        total = len(all_files)
        
        for i, filepath in enumerate(all_files):
            try:
                header = read_header(filepath)
                
                # Check if this is a flat frame
                image_type = get_header_value(header, 'IMAGETYP')
                if not image_type:
                    # Try to detect from filename
                    if 'flat' in Path(filepath).name.lower():
                        image_type = 'FLAT'
                    else:
                        continue
                
                if 'FLAT' not in str(image_type).upper():
                    continue
                
                # Extract grouping attributes
                date_obs = get_header_value(header, 'DATE-OBS')
                date = self._extract_night_date(date_obs)
                
                telescope = str(get_header_value(header, 'TELESCOP') or 'Unknown').strip()
                camera = str(get_header_value(header, 'INSTRUME') or 'Unknown').strip()
                filter_name = str(get_header_value(header, 'FILTER') or 'Unknown').strip()
                
                bx = get_header_value(header, 'XBINNING') or 1
                by = get_header_value(header, 'YBINNING') or 1
                binning = f"{int(bx)}x{int(by)}"
                
                rotation = float(get_header_value(header, 'ROTATION') or 0)
                
                temp = get_header_value(header, 'CCD-TEMP')
                
                # Create or update group
                fg = FlatGroup(date, telescope, camera, filter_name, binning, rotation)
                key = fg.key
                
                if key in self.groups:
                    if filepath not in self.groups[key].files:
                        self.groups[key].files.append(filepath)
                else:
                    fg.files.append(filepath)
                    if temp is not None:
                        fg.temperature = float(temp)
                    self.groups[key] = fg
                
                flat_count += 1
                
            except Exception as e:
                logger.debug(f"Failed to read flat: {filepath}: {e}")
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return flat_count
    
    def _extract_night_date(self, date_obs: Any) -> str:
        """
        Extract the 'night date' from DATE-OBS.
        If observation is before noon, use previous day (same night).
        """
        if not date_obs:
            return 'Unknown'
        try:
            dt = datetime.fromisoformat(str(date_obs).replace('Z', '+00:00'))
            # If before noon, it's still "last night"
            if dt.hour < 12:
                dt = dt - timedelta(days=1)
            return dt.strftime('%Y-%m-%d')
        except Exception:
            return str(date_obs)[:10] if date_obs else 'Unknown'
    
    # ----- Queries -----
    
    def get_groups_by_night(self) -> Dict[str, List[FlatGroup]]:
        """Get flat groups organized by night date."""
        by_night = defaultdict(list)
        for group in self.groups.values():
            by_night[group.date].append(group)
        return dict(sorted(by_night.items(), reverse=True))
    
    def get_groups_by_setup(self) -> Dict[str, List[FlatGroup]]:
        """Get flat groups organized by setup (telescope+camera)."""
        by_setup = defaultdict(list)
        for group in self.groups.values():
            by_setup[group.setup_key].append(group)
        return dict(sorted(by_setup.items()))
    
    def get_filters_for_night(self, date: str, telescope: str = None,
                               camera: str = None) -> List[str]:
        """Get list of filters that have flats for a given night."""
        filters = set()
        for group in self.groups.values():
            if group.date != date:
                continue
            if telescope and group.telescope != telescope:
                continue
            if camera and group.camera != camera:
                continue
            filters.add(group.filter_name)
        return sorted(filters)
    
    def check_flat_completeness(self, required_filters: List[str],
                                 date: str, telescope: str = None,
                                 camera: str = None) -> Dict[str, bool]:
        """
        Check which required filters have flats for a given night.
        Returns dict of {filter: has_flats}.
        """
        available = set(self.get_filters_for_night(date, telescope, camera))
        return {f: f in available for f in required_filters}
    
    def find_matching_flats(self, target_header: Dict[str, Any],
                             max_days: int = 30) -> List[FlatGroup]:
        """
        Find flat groups that match a light frame's setup.
        Searches within max_days of the light frame's date.
        """
        telescope = str(get_header_value(target_header, 'TELESCOP') or '').strip()
        camera = str(get_header_value(target_header, 'INSTRUME') or '').strip()
        filter_name = str(get_header_value(target_header, 'FILTER') or '').strip()
        
        bx = get_header_value(target_header, 'XBINNING') or 1
        by = get_header_value(target_header, 'YBINNING') or 1
        binning = f"{int(bx)}x{int(by)}"
        
        date_obs = get_header_value(target_header, 'DATE-OBS')
        light_date = self._extract_night_date(date_obs)
        
        matches = []
        for group in self.groups.values():
            # Must match setup
            if telescope and group.telescope != telescope:
                continue
            if camera and group.camera != camera:
                continue
            if filter_name and group.filter_name != filter_name:
                continue
            if group.binning != binning:
                continue
            
            # Check date proximity
            try:
                gd = datetime.strptime(group.date, '%Y-%m-%d')
                ld = datetime.strptime(light_date, '%Y-%m-%d')
                if abs((gd - ld).days) <= max_days:
                    matches.append(group)
            except ValueError:
                matches.append(group)  # Include if dates can't be parsed
        
        # Sort by date proximity
        try:
            ld = datetime.strptime(light_date, '%Y-%m-%d')
            matches.sort(key=lambda g: abs((datetime.strptime(g.date, '%Y-%m-%d') - ld).days))
        except ValueError:
            pass
        
        return matches
    
    # ----- Master flat tracking -----
    
    def set_master_flat(self, group_key: str, master_path: str):
        """Mark a group as having a master flat created."""
        if group_key in self.groups:
            self.groups[group_key].master_flat_path = master_path
            self.groups[group_key].master_created = True
    
    def link_target(self, group_key: str, target_name: str):
        """Link a target to a flat group."""
        if group_key in self.groups:
            self.groups[group_key].linked_targets.add(target_name)
    
    def get_unprocessed_groups(self) -> List[FlatGroup]:
        """Get flat groups that don't have master flats yet."""
        return [g for g in self.groups.values() if not g.master_created]
    
    # ----- Statistics -----
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall flat management statistics."""
        total_files = sum(g.count for g in self.groups.values())
        total_groups = len(self.groups)
        masters_created = sum(1 for g in self.groups.values() if g.master_created)
        nights = len(set(g.date for g in self.groups.values()))
        setups = len(set(g.setup_key for g in self.groups.values()))
        filters = len(set(g.filter_name for g in self.groups.values()))
        
        return {
            'total_flat_files': total_files,
            'total_groups': total_groups,
            'masters_created': masters_created,
            'masters_pending': total_groups - masters_created,
            'nights_covered': nights,
            'setups': setups,
            'filters': filters,
        }
    
    # ----- Persistence -----
    
    def save(self, path: Optional[str] = None):
        """Save flat database to JSON."""
        save_path = path or self.db_path
        if not save_path:
            return
        
        data = {
            'version': 1,
            'timestamp': datetime.now().isoformat(),
            'groups': {k: g.to_dict() for k, g in self.groups.items()}
        }
        
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load(self, path: Optional[str] = None):
        """Load flat database from JSON."""
        load_path = path or self.db_path
        if not load_path or not os.path.exists(load_path):
            return
        
        try:
            with open(load_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for key, gdata in data.get('groups', {}).items():
                self.groups[key] = FlatGroup.from_dict(gdata)
            
            logger.info(f"Loaded {len(self.groups)} flat groups from {load_path}")
        except Exception as e:
            logger.error(f"Failed to load flat database: {e}")
