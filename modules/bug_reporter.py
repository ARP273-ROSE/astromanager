#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - ANONYMOUS BUG REPORTER
================================================================================
Collects crash reports anonymously for quality improvement.
No personal data is collected - only technical information.
Reporting is disabled by default; users must explicitly opt in.
================================================================================
"""

import sys
import os
import json
import hashlib
import platform
import re
import traceback
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Tuple, Callable

logger = logging.getLogger(__name__)

# Bug report endpoint (hardcoded - not configurable) [FIX #4]
DEFAULT_ENDPOINT = "https://bugs.astromanager.io/report"

# Patterns that indicate sensitive data in stack traces [FIX #2]
_SENSITIVE_PATTERNS = re.compile(
    r'(api_key|password|token|secret)', re.IGNORECASE
)


class AnonymousBugReporter:
    """Anonymous bug/crash reporter"""

    def __init__(self, version='1.0.0', enabled=False):
        """
        Initialize the bug reporter.

        Args:
            version: Application version string
            enabled: Whether reporting is enabled (default False, opt-in) [FIX #5]
        """
        self.version = version
        self.endpoint = DEFAULT_ENDPOINT  # [FIX #4] Always use hardcoded endpoint
        self.enabled = enabled
        self._original_excepthook = None
        self._original_threading_excepthook = None
        self._crash_callback: Optional[Callable] = None
        self._anonymous_id = self._get_or_create_anonymous_id()

    def set_crash_callback(self, callback: Optional[Callable]):
        """
        Set a callback to be called on crash with the report dict.
        The callback receives one argument: the report dictionary.
        Used by the GUI to show a consent dialog before sending.
        """
        self._crash_callback = callback

    def _get_or_create_anonymous_id(self) -> str:
        """
        Get or create a stable anonymous user ID.

        Uses a random UUID4 persisted in ~/.astromanager/anonymous_id.
        The ID is not derived from any hardware or personal information. [FIX #1]
        """
        try:
            id_dir = Path.home() / '.astromanager'
            id_file = id_dir / 'anonymous_id'

            # Read existing ID if available
            if id_file.exists():
                stored_id = id_file.read_text(encoding='utf-8').strip()
                if stored_id:
                    return stored_id

            # Generate a new truly random ID
            new_id = str(uuid.uuid4())

            # Persist to file with restrictive permissions [FIX #6]
            id_dir.mkdir(parents=True, exist_ok=True)
            if platform.system() != 'Windows':
                os.chmod(str(id_dir), 0o700)

            id_file.write_text(new_id, encoding='utf-8')
            if platform.system() != 'Windows':
                os.chmod(str(id_file), 0o600)

            return new_id
        except Exception:
            return "unknown"

    def install_global_handler(self):
        """Install as global exception handler (sys + threading)"""
        self._original_excepthook = sys.excepthook
        sys.excepthook = self._handle_exception
        self._original_threading_excepthook = threading.excepthook
        threading.excepthook = self._handle_thread_exception

    def uninstall_global_handler(self):
        """Restore original exception handlers"""
        if self._original_excepthook:
            sys.excepthook = self._original_excepthook
        if self._original_threading_excepthook:
            threading.excepthook = self._original_threading_excepthook

    def _handle_exception(self, exc_type, exc_value, exc_tb):
        """Global exception handler for sys.excepthook"""
        # Call original handler first
        if self._original_excepthook:
            self._original_excepthook(exc_type, exc_value, exc_tb)

        if self.enabled:
            try:
                report = self.create_report(exc_type, exc_value, exc_tb)
                # Always save locally first
                self._save_local_report(report)
                # If a crash callback is set (GUI consent dialog), use it
                if self._crash_callback:
                    self._crash_callback(report)
                else:
                    # No GUI — send directly (headless / test mode)
                    report_id, was_sent = self.send_report(report)
                    status = "sent" if was_sent else "saved locally"
                    logger.info(f"Bug report {status}: {report_id}")
            except Exception:
                pass  # Never crash on crash reporting

    def _handle_thread_exception(self, args):
        """Global exception handler for threading.excepthook"""
        # args is a threading.ExceptHookArgs namedtuple:
        #   (exc_type, exc_value, exc_traceback, thread)
        exc_type = args.exc_type
        exc_value = args.exc_value
        exc_tb = args.exc_traceback

        # Call original handler first
        if self._original_threading_excepthook:
            try:
                self._original_threading_excepthook(args)
            except Exception:
                pass

        if self.enabled:
            try:
                thread_name = args.thread.name if args.thread else 'unknown'
                report = self.create_report(exc_type, exc_value, exc_tb,
                                            description=f"Unhandled exception in thread: {thread_name}")
                self._save_local_report(report)
                if self._crash_callback:
                    self._crash_callback(report)
                else:
                    report_id, was_sent = self.send_report(report)
                    status = "sent" if was_sent else "saved locally"
                    logger.info(f"Bug report (thread {thread_name}) {status}: {report_id}")
            except Exception:
                pass  # Never crash on crash reporting

    def _sanitize_traceback(self, tb_lines: list) -> list:
        """
        Sanitize traceback lines for privacy. [FIX #2]

        - Replaces the user's home directory with '~'
        - Strips any line containing sensitive keywords (api_key, password, token, secret)
        """
        home_dir = str(Path.home())
        sanitized = []
        for line in tb_lines:
            # Strip lines containing sensitive keywords
            if _SENSITIVE_PATTERNS.search(line):
                continue
            # Replace home directory paths with ~
            line = line.replace(home_dir, '~')
            sanitized.append(line)
        return sanitized

    def create_report(self, exc_type=None, exc_value=None,
                      exc_tb=None, description='') -> Dict:
        """Create a bug report dictionary"""
        report = {
            'report_id': self._generate_report_id(),
            'timestamp': datetime.now(timezone.utc).isoformat(),  # [FIX #9]
            'version': self.version,
            'anonymous_id': self._anonymous_id,

            # System info - minimal to avoid fingerprinting [FIX #3]
            'system': {
                'os': platform.system(),
                'python_version': platform.python_version(),
            },

            # Description
            'description': description,
        }

        # Exception info
        if exc_type:
            raw_tb = (
                traceback.format_exception(exc_type, exc_value, exc_tb)
                if exc_tb else []
            )
            # Sanitize exception message too (may contain paths) [FIX #11]
            exc_msg = str(exc_value) if exc_value else ''
            exc_msg = exc_msg.replace(str(Path.home()), '~')
            report['exception'] = {
                'type': exc_type.__name__ if exc_type else 'Unknown',
                'message': exc_msg,
                'traceback': self._sanitize_traceback(raw_tb),  # [FIX #2]
            }

        # Dependencies
        report['dependencies'] = self._get_dependency_versions()

        return report

    def _generate_report_id(self) -> str:
        """Generate unique report ID"""
        raw = f"{datetime.now(timezone.utc).isoformat()}_{self._anonymous_id}"  # [FIX #9]
        hash_val = hashlib.sha256(raw.encode()).hexdigest()[:16]  # [FIX #8] 16 hex chars
        return f"BR-{hash_val}"

    def _get_dependency_versions(self) -> Dict[str, str]:
        """Get versions of key dependencies"""
        deps = {}
        for module_name in ['PyQt6', 'astropy', 'numpy', 'xisf', 'zstandard', 'lz4']:
            try:
                mod = __import__(module_name)
                deps[module_name] = getattr(mod, '__version__', 'installed')
            except ImportError:
                deps[module_name] = 'not installed'
        return deps

    def send_report(self, report: Dict) -> Tuple[Optional[str], bool]:
        """
        Send bug report to endpoint. [FIX #7]

        Always saves locally first, then attempts to send to the remote
        endpoint. Returns (report_id, was_sent).
        """
        report_id = report.get('report_id')

        # Always save locally first (even before network attempt)
        self._save_local_report(report)

        try:
            import urllib.request
            import urllib.error

            data = json.dumps(report).encode('utf-8')

            req = urllib.request.Request(
                self.endpoint,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': f'AstroManager/{self.version}',
                },
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    return (report_id, True)

        except (urllib.error.URLError, OSError) as e:
            logger.debug(f"Could not send bug report: {e}")
        except Exception as e:
            logger.debug(f"Bug report error: {e}")

        return (report_id, False)

    def _save_local_report(self, report: Dict):
        """Save report locally when network is unavailable"""
        try:
            report_dir = Path.home() / '.astromanager' / 'crash_reports'
            report_dir.mkdir(parents=True, exist_ok=True)
            if platform.system() != 'Windows':
                os.chmod(str(report_dir), 0o700)

            report_file = report_dir / f"{report.get('report_id', 'unknown')}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
            if platform.system() != 'Windows':
                os.chmod(str(report_file), 0o600)

            logger.info(f"Bug report saved locally: {report_file}")
        except Exception:
            pass

    def get_report_preview(self, report: Dict) -> str:
        """
        Return a human-readable summary of the report for user review. [FIX #10]

        This allows the UI to show users exactly what will be sent
        before they approve submission.

        Args:
            report: The report dictionary from create_report()

        Returns:
            A sanitized multi-line summary string suitable for display.
        """
        lines = []
        lines.append(f"Report ID:   {report.get('report_id', 'N/A')}")
        lines.append(f"Timestamp:   {report.get('timestamp', 'N/A')}")
        lines.append(f"App Version: {report.get('version', 'N/A')}")
        lines.append("")

        system = report.get('system', {})
        lines.append("System Information:")
        lines.append(f"  OS:             {system.get('os', 'N/A')}")
        lines.append(f"  Python Version: {system.get('python_version', 'N/A')}")
        lines.append("")

        if report.get('description'):
            lines.append(f"Description: {report['description']}")
            lines.append("")

        exc = report.get('exception')
        if exc:
            lines.append(f"Exception: {exc.get('type', 'Unknown')}")
            lines.append(f"Message:   {exc.get('message', '')}")
            tb = exc.get('traceback', [])
            if tb:
                lines.append("Traceback (sanitized):")
                for tb_line in tb:
                    lines.append(f"  {tb_line.rstrip()}")
            lines.append("")

        deps = report.get('dependencies', {})
        if deps:
            lines.append("Dependencies:")
            for name, ver in deps.items():
                lines.append(f"  {name}: {ver}")

        return "\n".join(lines)

    def format_github_issue_markdown(self, report: Dict) -> Tuple[str, str]:
        """
        Format a report as a GitHub Issue (title + markdown body).

        Returns:
            Tuple of (title, body_markdown)
        """
        exc = report.get('exception', {})
        exc_type = exc.get('type', 'Unknown')
        is_manual = report.get('manual', False)
        version = report.get('version', '?')

        if is_manual:
            title = f"[bug-report] ManualReport (v{version})"
            label = 'bug-report'
        else:
            title = f"[crash-report] {exc_type} (v{version})"
            label = 'crash-report'

        # Build markdown body
        lines = []
        lines.append(f"**Report ID:** `{report.get('report_id', 'N/A')}`")
        lines.append(f"**Timestamp:** {report.get('timestamp', 'N/A')}")
        lines.append(f"**Version:** {version}")
        lines.append("")

        system = report.get('system', {})
        lines.append("## System")
        lines.append(f"- **OS:** {system.get('os', 'N/A')}")
        lines.append(f"- **Python:** {system.get('python_version', 'N/A')}")
        lines.append("")

        if report.get('description'):
            lines.append("## Description")
            lines.append(report['description'])
            lines.append("")

        if report.get('steps_to_reproduce'):
            lines.append("## Steps to Reproduce")
            lines.append(report['steps_to_reproduce'])
            lines.append("")

        if exc and exc.get('type'):
            lines.append("## Exception")
            lines.append(f"**Type:** `{exc_type}`")
            lines.append(f"**Message:** {exc.get('message', '')}")
            lines.append("")
            tb = exc.get('traceback', [])
            if tb:
                lines.append("## Traceback")
                lines.append("```")
                for tb_line in tb:
                    lines.append(tb_line.rstrip())
                lines.append("```")
                lines.append("")

        deps = report.get('dependencies', {})
        if deps:
            lines.append("## Dependencies")
            for name, ver in deps.items():
                lines.append(f"- **{name}:** {ver}")

        body = "\n".join(lines)
        return (title, body)

    def submit_manual_report(self, description: str,
                              steps_to_reproduce: str = '') -> Tuple[Optional[str], bool]:
        """
        Submit a manual bug report (from Help menu).

        Args:
            description: Bug description
            steps_to_reproduce: Steps to reproduce

        Returns:
            Tuple of (report_id, was_sent) [FIX #7]
        """
        report = self.create_report(description=description)
        report['manual'] = True
        report['steps_to_reproduce'] = steps_to_reproduce
        return self.send_report(report)


# Global instance (thread-safe double-checked locking) [FIX #12]
_reporter = None
_reporter_lock = threading.Lock()


def get_bug_reporter(version='1.0.0') -> AnonymousBugReporter:
    """Get global bug reporter instance (thread-safe)"""
    global _reporter
    if _reporter is None:
        with _reporter_lock:
            if _reporter is None:
                try:
                    from core.config import get_config
                    config = get_config()
                    enabled = config.get('bug_reporting.enabled', False)  # [FIX #5] Default disabled
                    # [FIX #4] No config-based endpoint override; always use DEFAULT_ENDPOINT
                    _reporter = AnonymousBugReporter(version=version, enabled=enabled)
                except Exception:
                    _reporter = AnonymousBugReporter(version=version, enabled=False)  # [FIX #5]
    return _reporter
