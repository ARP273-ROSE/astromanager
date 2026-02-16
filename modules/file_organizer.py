#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - FILE ORGANIZER MODULE
================================================================================
Organizes astrophotography files into a clean folder structure based on
FITS headers (target, date, filter, equipment, image type).

Structure options:
  - By Target:    Target/Date/Filter/files
  - By Date:      Date/Target/Filter/files
  - By Equipment: Telescope/Target/Date/Filter/files
  - Flat:         Target_Date_Filter/files

Supports copy or move mode, with dry-run preview.
================================================================================
"""

import os
import shutil
import logging
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Optional, Callable, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


# Organization pattern presets
ORGANIZATION_PRESETS = {
    'by_target': {
        'en': 'By Target (Target/Date/Filter)',
        'fr': 'Par Cible (Cible/Date/Filtre)',
        'pattern': '{target}/{date}/{filter}',
    },
    'by_date': {
        'en': 'By Date (Date/Target/Filter)',
        'fr': 'Par Date (Date/Cible/Filtre)',
        'pattern': '{date}/{target}/{filter}',
    },
    'by_equipment': {
        'en': 'By Equipment (Telescope/Target/Date/Filter)',
        'fr': 'Par Equipement (Telescope/Cible/Date/Filtre)',
        'pattern': '{telescope}/{target}/{date}/{filter}',
    },
    'by_type': {
        'en': 'By Type (Light|Flat|Dark|Bias/Target/Filter)',
        'fr': 'Par Type (Light|Flat|Dark|Bias/Cible/Filtre)',
        'pattern': '{imagetype}/{target}/{filter}',
    },
    'by_target_equipment': {
        'en': 'Target + Equipment (Target/Telescope/Date/Filter)',
        'fr': 'Cible + Equipement (Cible/Telescope/Date/Filtre)',
        'pattern': '{target}/{telescope}/{date}/{filter}',
    },
}


def _sanitize_folder_name(name: str) -> str:
    """Sanitize a string for use as folder name."""
    if not name:
        return 'Unknown'
    # Replace problematic characters
    for ch in ['<', '>', ':', '"', '|', '?', '*', '/', '\\']:
        name = name.replace(ch, '_')
    name = name.strip('. ')
    return name if name else 'Unknown'


def _read_file_info(filepath: str) -> Optional[Dict]:
    """Read header info from a FITS/XISF/FZ file for organization."""
    try:
        from .header_editor import read_header, get_header_value
        header = read_header(filepath)
        if not header:
            return None

        target = get_header_value(header, 'OBJECT') or 'Unknown'
        date_obs = get_header_value(header, 'DATE-OBS') or ''
        if date_obs and len(date_obs) >= 10:
            date_str = date_obs[:10]
        else:
            date_str = 'Unknown_Date'

        filter_name = get_header_value(header, 'FILTER') or 'NoFilter'
        telescope = get_header_value(header, 'TELESCOP') or 'Unknown_Telescope'
        camera = get_header_value(header, 'INSTRUME') or ''
        imagetype = get_header_value(header, 'IMAGETYP') or 'LIGHT'

        # Normalize image type
        imagetype_upper = imagetype.upper().strip()
        if 'LIGHT' in imagetype_upper or 'SCIENCE' in imagetype_upper:
            imagetype = 'LIGHT'
        elif 'DARK' in imagetype_upper:
            imagetype = 'DARK'
        elif 'FLAT' in imagetype_upper:
            imagetype = 'FLAT'
        elif 'BIAS' in imagetype_upper or 'OFFSET' in imagetype_upper:
            imagetype = 'BIAS'
        else:
            imagetype = imagetype_upper if imagetype_upper else 'LIGHT'

        return {
            'target': _sanitize_folder_name(target),
            'date': _sanitize_folder_name(date_str),
            'filter': _sanitize_folder_name(filter_name),
            'telescope': _sanitize_folder_name(telescope),
            'camera': _sanitize_folder_name(camera),
            'imagetype': imagetype,
        }
    except Exception as e:
        logger.warning(f"Cannot read header for {filepath}: {e}")
        return None


def plan_organization(source_folder: str,
                       dest_folder: str,
                       preset: str = 'by_target',
                       progress_callback: Optional[Callable] = None,
                       check_abort: Optional[Callable] = None
                       ) -> List[Tuple[str, str]]:
    """
    Plan file organization (dry run).

    Args:
        source_folder: Source directory to scan
        dest_folder: Destination root directory
        preset: Organization preset name (from ORGANIZATION_PRESETS)
        progress_callback: Optional callback(current, total, message)
        check_abort: Optional function returning True to abort

    Returns:
        List of (source_path, destination_path) tuples
    """
    pattern_info = ORGANIZATION_PRESETS.get(preset)
    if not pattern_info:
        pattern_info = ORGANIZATION_PRESETS['by_target']
    pattern = pattern_info['pattern']

    # Scan for files
    files = []
    for root, _, filenames in os.walk(source_folder):
        for fn in filenames:
            ext = fn.lower()
            if ext.endswith(('.fits', '.fit', '.fts', '.xisf', '.fz')):
                files.append(os.path.join(root, fn))

    if not files:
        return []

    plan = []
    total = len(files)

    # Phase 1: Read all headers in parallel for performance
    file_infos = {}
    num_workers = min(os.cpu_count() or 4, total, 8)

    if num_workers > 1 and total > 5:
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = {executor.submit(_read_file_info, fp): fp for fp in files}
            for i, future in enumerate(as_completed(futures)):
                if check_abort and check_abort():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                fp = futures[future]
                try:
                    info = future.result()
                    if info:
                        file_infos[fp] = info
                except Exception:
                    pass
                if progress_callback and i % 50 == 0:
                    progress_callback(i, total, f"Planning: {os.path.basename(fp)}")
    else:
        for i, fp in enumerate(files):
            if check_abort and check_abort():
                break
            if os.path.islink(fp):
                continue
            info = _read_file_info(fp)
            if info:
                file_infos[fp] = info
            if progress_callback and i % 50 == 0:
                progress_callback(i, total, f"Planning: {os.path.basename(fp)}")

    # Phase 2: Build plan from cached headers (fast, in-memory)
    errors = []
    for filepath, info in file_infos.items():
        if check_abort and check_abort():
            break

        # Skip symlinks
        if os.path.islink(filepath):
            continue

        # Build subdirectory from pattern
        subdir = pattern.format(**info)
        dest_dir = os.path.join(dest_folder, subdir)
        dest_path = os.path.join(dest_dir, os.path.basename(filepath))

        # Path traversal check
        rel = os.path.relpath(dest_path, dest_folder)
        if rel.startswith('..'):
            errors.append(f"Skipped {filepath}: path traversal detected")
            continue

        # Handle name conflicts
        if os.path.exists(dest_path) and dest_path != filepath:
            base, ext = os.path.splitext(os.path.basename(filepath))
            if filepath.lower().endswith('.fits.fz'):
                base = Path(filepath).stem
                base = Path(base).stem  # Remove .fits
                ext = '.fits.fz'
            counter = 1
            while os.path.exists(dest_path):
                dest_path = os.path.join(dest_dir, f"{base}_{counter}{ext}")
                counter += 1

        plan.append((filepath, dest_path))

    if progress_callback:
        progress_callback(total, total, "Planning complete")

    return plan


def execute_organization(plan: List[Tuple[str, str]],
                          copy_mode: bool = True,
                          progress_callback: Optional[Callable] = None,
                          check_abort: Optional[Callable] = None
                          ) -> Dict[str, int]:
    """
    Execute a file organization plan.

    Args:
        plan: List of (source, dest) from plan_organization()
        copy_mode: True=copy files, False=move files
        progress_callback: Optional callback(current, total, message)
        check_abort: Optional abort check

    Returns:
        Dict with 'moved', 'errors', 'skipped' counts
    """
    result = {'moved': 0, 'errors': 0, 'skipped': 0, 'total': len(plan),
              'error_details': []}
    total = len(plan)
    completed_moves = []  # Track moves for potential rollback info

    for i, (src, dst) in enumerate(plan):
        if check_abort and check_abort():
            break

        if progress_callback and i % 10 == 0:
            progress_callback(i, total, f"{'Copying' if copy_mode else 'Moving'}: {os.path.basename(src)}")

        if src == dst:
            result['skipped'] += 1
            continue

        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)

            # Handle TOCTOU race: if dest appeared between plan and execute
            if os.path.exists(dst) and dst != src:
                import time as _time
                base, ext = os.path.splitext(dst)
                dst = f"{base}_{int(_time.time() * 1000) % 100000}{ext}"

            if copy_mode:
                shutil.copy2(src, dst)
            else:
                shutil.move(src, dst)
                completed_moves.append((src, dst))

            result['moved'] += 1
        except Exception as e:
            logger.warning(f"Failed to organize {src}: {e}")
            result['errors'] += 1
            result['error_details'].append(f"{src}: {e}")

    # Summary of partial failure for move mode
    if not copy_mode and result['errors'] > 0 and completed_moves:
        logger.warning(
            f"Partial failure in move mode: {result['moved']} moved, "
            f"{result['errors']} errors. Successfully moved files cannot be "
            f"automatically rolled back."
        )
        result['completed_moves'] = completed_moves

    if progress_callback:
        progress_callback(total, total, "Organization complete")

    return result


def get_organization_summary(plan: List[Tuple[str, str]]) -> Dict:
    """
    Generate a summary of what the organization plan will do.

    Returns:
        Dict with target_count, unique_folders, file_count, size estimates
    """
    folders = set()
    targets = set()
    total_size = 0

    for src, dst in plan:
        folders.add(os.path.dirname(dst))
        # Extract target from path
        parts = Path(dst).parts
        if len(parts) > 1:
            targets.add(parts[-3] if len(parts) >= 3 else parts[-2])

        try:
            total_size += os.path.getsize(src)
        except OSError:
            pass

    return {
        'file_count': len(plan),
        'folder_count': len(folders),
        'target_count': len(targets),
        'total_size_bytes': total_size,
        'total_size_gb': round(total_size / (1024**3), 2),
    }
