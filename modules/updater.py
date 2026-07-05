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
import time
import zipfile
import hashlib
import logging

import requests

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com/repos/ARP273-ROSE/astromanager/releases/latest"
GITHUB_REPO = "ARP273-ROSE/astromanager"

# Directories to exclude when applying updates
EXCLUDED_DIRS = {'config', 'venv', '.venv', '.git', '__pycache__'}

# Maximum download size: 500 MB
_MAX_DOWNLOAD_BYTES = 500 * 1024 * 1024

# Maximum size for the SHA256SUMS integrity file: 1 MB (it is a few lines of text)
_MAX_SHA256SUMS_BYTES = 1 * 1024 * 1024

# Name of the release asset holding the archive checksums
_SHA256SUMS_ASSET_NAME = 'SHA256SUMS'

# Retry configuration
_MAX_RETRIES = 3
_RETRY_DELAY_SECONDS = 2

# Allowed URL prefixes for downloads
_ALLOWED_URL_PREFIXES = (
    "https://github.com/",
    "https://api.github.com/",
)

# File extensions considered safe to copy during updates
_SAFE_EXTENSIONS = {
    '.py', '.md', '.txt', '.yml', '.yaml', '.json', '.toml', '.cfg',
    '.sh', '.bat', '.png', '.ico', '.pdf', '.css', '.html', '.ui', '.qrc',
}


def version_compare(version_a, version_b):
    """
    Compare two version strings by splitting on '.' and comparing integer tuples.

    Args:
        version_a: First version string (e.g. '1.2.3')
        version_b: Second version string (e.g. '1.3.0')

    Returns:
        -1 if version_a < version_b, 0 if equal, 1 if version_a > version_b.
    """
    def _parse_parts(v):
        parts = []
        for part in v.split('.'):
            try:
                parts.append(int(part))
            except ValueError:
                parts.append(0)
        return tuple(parts)

    a = _parse_parts(version_a)
    b = _parse_parts(version_b)

    # Pad shorter tuple with zeros so lengths match
    max_len = max(len(a), len(b))
    a = a + (0,) * (max_len - len(a))
    b = b + (0,) * (max_len - len(b))

    if a < b:
        return -1
    elif a > b:
        return 1
    return 0


def _request_with_retry(method, url, **kwargs):
    """
    Execute a requests call with retry logic.

    Retries up to _MAX_RETRIES times on ConnectionError or Timeout,
    sleeping _RETRY_DELAY_SECONDS between attempts.

    Args:
        method: HTTP method string ('get', 'post', etc.)
        url: Request URL
        **kwargs: Passed through to requests.request()

    Returns:
        requests.Response object

    Raises:
        Last caught exception if all retries are exhausted.
    """
    last_exc = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.request(method, url, **kwargs)
            return resp
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                logger.warning(
                    "Request to %s failed (attempt %d/%d): %s — retrying in %ds",
                    url, attempt, _MAX_RETRIES, exc, _RETRY_DELAY_SECONDS,
                )
                time.sleep(_RETRY_DELAY_SECONDS)
            else:
                logger.error(
                    "Request to %s failed after %d attempts: %s",
                    url, _MAX_RETRIES, exc,
                )
    raise last_exc


def check_for_update(current_version):
    """
    Check GitHub Releases for a newer version.

    Args:
        current_version: Current app version string (e.g. '1.0.0')

    Returns:
        dict with update info if newer version available, None otherwise.
        Raises on network error.
    """
    resp = _request_with_retry(
        'get',
        GITHUB_API,
        headers={'Accept': 'application/vnd.github.v3+json'},
        timeout=5,
    )
    resp.raise_for_status()
    data = resp.json()

    tag = data.get('tag_name', '')
    remote_version = tag.lstrip('v')

    if not remote_version:
        return None

    if version_compare(remote_version, current_version) > 0:
        return {
            'version': remote_version,
            'url': data.get('html_url', ''),
            'download_url': data.get('zipball_url', ''),
            'body': data.get('body', ''),
            'date': data.get('published_at', ''),
        }

    return None


def _validate_download_url(download_url):
    """
    Validate that a download URL points to a trusted GitHub domain.

    Args:
        download_url: URL string to validate

    Raises:
        ValueError: If URL does not start with an allowed prefix.
    """
    if not any(download_url.startswith(prefix) for prefix in _ALLOWED_URL_PREFIXES):
        raise ValueError(
            f"Refusing to download from untrusted URL: {download_url}"
        )


def _compute_file_sha256(path):
    """
    Compute the hex SHA-256 digest of a file, reading it in chunks.

    Args:
        path: Path to the file to hash

    Returns:
        Lowercase hex digest string.
    """
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(65536), b''):
            h.update(block)
    return h.hexdigest().lower()


def _fetch_release_sha256sums(download_url):
    """
    Fetch and parse the SHA256SUMS asset published on the GitHub release that
    the given archive was downloaded from.

    The checksums are only trusted when they come from the very release whose
    zipball matches ``download_url`` (guards against pointing at a different
    release). The SHA256SUMS asset URL is validated against the same allowlist
    used for archive downloads.

    Args:
        download_url: The archive (zipball) URL that is being verified.

    Returns:
        A set of lowercase hex SHA-256 strings listed in the SHA256SUMS file,
        or None if the matching release publishes no usable SHA256SUMS asset.
    """
    resp = _request_with_retry(
        'get',
        GITHUB_API,
        headers={'Accept': 'application/vnd.github.v3+json'},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    # Only trust checksums from the release the archive was actually fetched
    # from. If the latest release changed in the meantime, refuse (fail-safe).
    if data.get('zipball_url', '') != download_url:
        logger.error(
            "Release mismatch: latest release zipball (%r) does not match the "
            "archive URL being verified (%r); cannot verify integrity",
            data.get('zipball_url', ''), download_url,
        )
        return None

    sums_url = None
    for asset in (data.get('assets') or []):
        name = (asset.get('name') or '').strip()
        if name.upper() == _SHA256SUMS_ASSET_NAME:
            sums_url = asset.get('browser_download_url', '') or ''
            break

    if not sums_url:
        logger.error("Release publishes no %s asset", _SHA256SUMS_ASSET_NAME)
        return None

    # Enforce the same trusted-domain allowlist as the archive download.
    _validate_download_url(sums_url)

    sums_resp = _request_with_retry(
        'get',
        sums_url,
        headers={'Accept': 'application/octet-stream'},
        timeout=30,
    )
    sums_resp.raise_for_status()

    content = sums_resp.content
    if len(content) > _MAX_SHA256SUMS_BYTES:
        raise ValueError(
            f"{_SHA256SUMS_ASSET_NAME} file is unexpectedly large "
            f"({len(content)} bytes); refusing to parse"
        )

    hashes = set()
    for line in content.decode('utf-8', errors='replace').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # Standard `sha256sum` format is: "<hex>␠␠<filename>" (filename may be
        # prefixed by '*' for binary mode). Keep only the leading digest token.
        token = line.split()[0].lstrip('*').lower()
        if len(token) == 64 and all(c in '0123456789abcdef' for c in token):
            hashes.add(token)

    if not hashes:
        logger.error("%s asset contained no valid SHA-256 digests", _SHA256SUMS_ASSET_NAME)
        return None

    return hashes


def _validate_zip_members(zf):
    """
    Validate all zip member paths for Zip Slip and absolute path attacks.

    Args:
        zf: An open zipfile.ZipFile object

    Raises:
        ValueError: If any member contains '..' path components or is absolute.
    """
    for name in zf.namelist():
        # Reject absolute paths
        if os.path.isabs(name):
            raise ValueError(f"Zip member has absolute path: {name}")
        # Normalise and check for path traversal
        normalised = os.path.normpath(name)
        if normalised.startswith('..') or (os.sep + '..') in normalised:
            raise ValueError(f"Zip member attempts path traversal: {name}")
        # Also check with forward slashes (platform-independent)
        if '..' in name.split('/'):
            raise ValueError(f"Zip member contains '..' component: {name}")


def _is_safe_file(path):
    """
    Check whether a file has an allowed extension for copying.

    Args:
        path: File path to check

    Returns:
        True if the file extension is in _SAFE_EXTENSIONS, False otherwise.
    """
    _, ext = os.path.splitext(path)
    return ext.lower() in _SAFE_EXTENSIONS


def _safe_copytree(src, dst):
    """
    Recursively copy a directory tree, skipping symlinks and unsafe file types.

    Args:
        src: Source directory path
        dst: Destination directory path
    """
    os.makedirs(dst, exist_ok=True)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)

        # Skip symlinks
        if os.path.islink(s):
            logger.warning("Skipping symlink during update: %s", s)
            continue

        if os.path.isdir(s):
            _safe_copytree(s, d)
        else:
            if _is_safe_file(s):
                shutil.copy2(s, d)
            else:
                logger.info("Skipping file with disallowed extension: %s", s)


def download_and_apply_update(download_url, app_dir, progress_callback=None):
    """
    Download a release zipball and apply it over the current installation.

    Uses a staging directory so the live app_dir is only modified on success.
    Validates zip contents, enforces download size limits, skips symlinks
    and unsafe file types.

    Before anything is extracted or applied, the archive's SHA-256 is verified
    against the release's SHA256SUMS asset. If that asset is missing or the
    hash does not match, the update is refused (fail-safe) and the archive is
    discarded — the installation is left untouched.

    Args:
        download_url: GitHub zipball URL
        app_dir: Application root directory
        progress_callback: Optional callable(bytes_downloaded, total_bytes)
            invoked as chunks are received. total_bytes may be 0 if the
            server did not send Content-Length.

    Returns:
        True if successful. Raises on error.
    """
    # Validate URL before any network activity
    _validate_download_url(download_url)

    tmp_dir = tempfile.mkdtemp(prefix='astromanager_update_')
    zip_path = os.path.join(tmp_dir, 'update.zip')
    staging_dir = app_dir + '.update_staging'

    try:
        # Download zipball with retry
        resp = _request_with_retry(
            'get',
            download_url,
            headers={'Accept': 'application/vnd.github.v3+json'},
            timeout=120,
            stream=True,
        )
        resp.raise_for_status()

        # Check Content-Length before downloading
        content_length = resp.headers.get('Content-Length')
        total_bytes = int(content_length) if content_length else 0
        if total_bytes > _MAX_DOWNLOAD_BYTES:
            raise ValueError(
                f"Download too large: {total_bytes} bytes exceeds "
                f"{_MAX_DOWNLOAD_BYTES} byte limit"
            )

        bytes_downloaded = 0
        with open(zip_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                bytes_downloaded += len(chunk)
                if bytes_downloaded > _MAX_DOWNLOAD_BYTES:
                    raise ValueError(
                        f"Download exceeded {_MAX_DOWNLOAD_BYTES} byte limit "
                        f"during streaming (received {bytes_downloaded} bytes)"
                    )
                f.write(chunk)
                if progress_callback is not None:
                    progress_callback(bytes_downloaded, total_bytes)

        # --- Integrity verification (fail-safe, BEFORE extracting/applying) ---
        # Compute the SHA-256 of the downloaded archive and require it to match
        # a hash published in the release's SHA256SUMS asset. If the asset is
        # absent or the hash does not match, we refuse to apply the update. The
        # archive is removed by the `finally` block on the way out.
        archive_digest = _compute_file_sha256(zip_path)
        expected_hashes = _fetch_release_sha256sums(download_url)

        if not expected_hashes:
            logger.error(
                "Integrity check failed: no trusted SHA256SUMS available for "
                "this release. Refusing to apply the update."
            )
            raise RuntimeError(
                "Update integrity check failed: this release does not publish a "
                "SHA256SUMS checksum file, so the download could not be verified. "
                "Refusing to apply the update for safety. Please update "
                "AstroManager manually from the GitHub releases page."
            )

        if archive_digest not in expected_hashes:
            logger.error(
                "Integrity check failed: archive SHA-256 %s not listed in "
                "SHA256SUMS. Possible tampering. Refusing to apply the update.",
                archive_digest,
            )
            raise RuntimeError(
                "Update integrity check failed: the downloaded archive checksum "
                f"({archive_digest}) does not match the release's SHA256SUMS "
                "(possible corruption or tampering). Refusing to apply the "
                "update. Please update AstroManager manually from the GitHub "
                "releases page."
            )

        logger.info("Archive integrity verified against SHA256SUMS")

        # Extract with Zip Slip protection
        extract_dir = os.path.join(tmp_dir, 'extracted')
        with zipfile.ZipFile(zip_path, 'r') as zf:
            _validate_zip_members(zf)
            zf.extractall(extract_dir)

        # GitHub zipball contains a single top-level directory
        # e.g. ARP273-ROSE-astromanager-abc1234/
        contents = os.listdir(extract_dir)
        if len(contents) == 1 and os.path.isdir(os.path.join(extract_dir, contents[0])):
            source_dir = os.path.join(extract_dir, contents[0])
        else:
            source_dir = extract_dir

        # Stage update into a temporary staging directory alongside app_dir.
        # If staging fails, only the staging dir is cleaned up — app_dir is untouched.
        if os.path.exists(staging_dir):
            shutil.rmtree(staging_dir)
        os.makedirs(staging_dir, exist_ok=True)

        try:
            # Copy current app_dir contents into staging (preserve excluded dirs, etc.)
            for item in os.listdir(app_dir):
                src = os.path.join(app_dir, item)
                dst = os.path.join(staging_dir, item)

                # Skip symlinks (TOCTOU-safe: check link before any operation)
                if os.path.islink(src):
                    logger.warning("Skipping symlink in app_dir: %s", src)
                    continue

                if os.path.isdir(src):
                    shutil.copytree(src, dst, symlinks=False)
                else:
                    shutil.copy2(src, dst)

            # Apply new files from the update into staging, excluding protected dirs
            for item in os.listdir(source_dir):
                if item in EXCLUDED_DIRS:
                    continue

                src = os.path.join(source_dir, item)
                dst = os.path.join(staging_dir, item)

                # Skip symlinks in the downloaded archive
                if os.path.islink(src):
                    logger.warning("Skipping symlink in update archive: %s", src)
                    continue

                if os.path.isdir(src):
                    # Remove the old version of this directory in staging
                    if os.path.exists(dst):
                        if os.path.islink(dst):
                            logger.warning("Skipping symlink target in staging: %s", dst)
                            continue
                        shutil.rmtree(dst)
                    _safe_copytree(src, dst)
                else:
                    if _is_safe_file(src):
                        shutil.copy2(src, dst)
                    else:
                        logger.info("Skipping file with disallowed extension: %s", src)

        except Exception:
            # Staging failed — clean up staging dir and re-raise
            logger.error("Staging failed; cleaning up staging directory")
            if os.path.exists(staging_dir) and not os.path.islink(staging_dir):
                shutil.rmtree(staging_dir)
            raise

        # Swap: rename live dir out, move staged dir in, remove old dir
        backup_dir = app_dir + '.update_backup'
        if os.path.exists(backup_dir):
            if os.path.islink(backup_dir):
                os.unlink(backup_dir)
            else:
                shutil.rmtree(backup_dir)

        shutil.move(app_dir, backup_dir)
        try:
            shutil.move(staging_dir, app_dir)
        except Exception:
            # Rollback: restore backup
            logger.error("Failed to swap staging dir into place; rolling back")
            shutil.move(backup_dir, app_dir)
            raise

        # Remove old backup
        if os.path.exists(backup_dir) and not os.path.islink(backup_dir):
            shutil.rmtree(backup_dir)

        logger.info("Update applied successfully")
        return True

    finally:
        # Clean up temp directory
        try:
            shutil.rmtree(tmp_dir)
        except Exception as exc:
            logger.warning("Failed to clean up temp directory %s: %s", tmp_dir, exc)

        # Clean up staging dir if it still exists (e.g. unexpected error path)
        try:
            if os.path.exists(staging_dir) and not os.path.islink(staging_dir):
                shutil.rmtree(staging_dir)
        except Exception as exc:
            logger.warning("Failed to clean up staging directory %s: %s", staging_dir, exc)


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
