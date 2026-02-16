#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - AUTO-UPDATE MODULE
================================================================================
Checks for updates via GitHub Releases API, downloads and applies updates.
================================================================================
"""

import os
import shutil
import tempfile
import zipfile
import logging

import requests

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com/repos/ARP273-ROSE/astromanager/releases/latest"
GITHUB_REPO = "ARP273-ROSE/astromanager"

# Directories to exclude when applying updates
EXCLUDED_DIRS = {'config', '.astromanager', 'venv', '.venv', '.git', '__pycache__'}


def check_for_update(current_version):
    """
    Check GitHub Releases for a newer version.

    Args:
        current_version: Current app version string (e.g. '1.0.0')

    Returns:
        dict with update info if newer version available, None otherwise.
        Raises on network error.
    """
    try:
        from packaging.version import parse as parse_version
    except ImportError:
        from distutils.version import LooseVersion as parse_version

    resp = requests.get(
        GITHUB_API,
        headers={'Accept': 'application/vnd.github.v3+json'},
        timeout=5
    )
    resp.raise_for_status()
    data = resp.json()

    tag = data.get('tag_name', '')
    remote_version = tag.lstrip('v')

    if not remote_version:
        return None

    if parse_version(remote_version) > parse_version(current_version):
        return {
            'version': remote_version,
            'url': data.get('html_url', ''),
            'download_url': data.get('zipball_url', ''),
            'body': data.get('body', ''),
            'date': data.get('published_at', ''),
        }

    return None


def download_and_apply_update(download_url, app_dir):
    """
    Download a release zipball and apply it over the current installation.

    Args:
        download_url: GitHub zipball URL
        app_dir: Application root directory

    Returns:
        True if successful. Raises on error.
    """
    tmp_dir = tempfile.mkdtemp(prefix='astromanager_update_')
    zip_path = os.path.join(tmp_dir, 'update.zip')

    try:
        # Download zipball
        resp = requests.get(
            download_url,
            headers={'Accept': 'application/vnd.github.v3+json'},
            timeout=120,
            stream=True
        )
        resp.raise_for_status()

        with open(zip_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        # Extract
        extract_dir = os.path.join(tmp_dir, 'extracted')
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)

        # GitHub zipball contains a single top-level directory
        # e.g. ARP273-ROSE-astromanager-abc1234/
        contents = os.listdir(extract_dir)
        if len(contents) == 1 and os.path.isdir(os.path.join(extract_dir, contents[0])):
            source_dir = os.path.join(extract_dir, contents[0])
        else:
            source_dir = extract_dir

        # Copy files, excluding protected directories
        for item in os.listdir(source_dir):
            if item in EXCLUDED_DIRS:
                continue

            src = os.path.join(source_dir, item)
            dst = os.path.join(app_dir, item)

            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        logger.info("Update applied successfully")
        return True

    finally:
        # Clean up temp directory
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass


def get_changelog(release_info):
    """
    Format release notes for display.

    Args:
        release_info: dict from check_for_update()

    Returns:
        Formatted changelog string
    """
    body = release_info.get('body', '') or ''
    # Basic markdown cleanup for display in QMessageBox/QTextEdit
    lines = []
    for line in body.split('\n'):
        line = line.replace('### ', '').replace('## ', '').replace('# ', '')
        line = line.replace('**', '').replace('__', '')
        lines.append(line)
    return '\n'.join(lines).strip()
