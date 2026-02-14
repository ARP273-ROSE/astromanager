#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - ANONYMOUS BUG REPORTER
================================================================================
Collects crash reports anonymously for quality improvement.
No personal data is collected - only technical information.
================================================================================
"""

import sys
import os
import json
import hashlib
import platform
import traceback
import logging
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Bug report endpoint
DEFAULT_ENDPOINT = "https://bugs.astromanager.io/report"


class AnonymousBugReporter:
    """Anonymous bug/crash reporter"""

    def __init__(self, version='1.0.0', endpoint=None, enabled=True):
        self.version = version
        self.endpoint = endpoint or DEFAULT_ENDPOINT
        self.enabled = enabled
        self._original_excepthook = None
        self._anonymous_id = self._generate_anonymous_id()

    def _generate_anonymous_id(self) -> str:
        """Generate anonymous user ID (no personal data)"""
        try:
            raw = f"{platform.node()}_{platform.machine()}_{platform.processor()}"
            return hashlib.sha256(raw.encode()).hexdigest()[:16]
        except Exception:
            return "unknown"

    def install_global_handler(self):
        """Install as global exception handler"""
        self._original_excepthook = sys.excepthook
        sys.excepthook = self._handle_exception

    def uninstall_global_handler(self):
        """Restore original exception handler"""
        if self._original_excepthook:
            sys.excepthook = self._original_excepthook

    def _handle_exception(self, exc_type, exc_value, exc_tb):
        """Global exception handler"""
        # Call original handler first
        if self._original_excepthook:
            self._original_excepthook(exc_type, exc_value, exc_tb)

        # Send report
        if self.enabled:
            try:
                report = self.create_report(exc_type, exc_value, exc_tb)
                report_id = self.send_report(report)
                if report_id:
                    logger.info(f"Bug report sent: {report_id}")
            except Exception:
                pass  # Never crash on crash reporting

    def create_report(self, exc_type=None, exc_value=None,
                      exc_tb=None, description='') -> Dict:
        """Create a bug report dictionary"""
        report = {
            'report_id': self._generate_report_id(),
            'timestamp': datetime.utcnow().isoformat(),
            'version': self.version,
            'anonymous_id': self._anonymous_id,

            # System info (no personal data)
            'system': {
                'os': platform.system(),
                'os_version': platform.version(),
                'architecture': platform.machine(),
                'python_version': platform.python_version(),
                'cpu_count': os.cpu_count(),
            },

            # Description
            'description': description,
        }

        # Exception info
        if exc_type:
            report['exception'] = {
                'type': exc_type.__name__ if exc_type else 'Unknown',
                'message': str(exc_value) if exc_value else '',
                'traceback': traceback.format_exception(exc_type, exc_value, exc_tb)
                             if exc_tb else [],
            }

        # Dependencies
        report['dependencies'] = self._get_dependency_versions()

        return report

    def _generate_report_id(self) -> str:
        """Generate unique report ID"""
        raw = f"{datetime.utcnow().isoformat()}_{self._anonymous_id}"
        hash_val = hashlib.sha256(raw.encode()).hexdigest()[:8]
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

    def send_report(self, report: Dict) -> Optional[str]:
        """
        Send bug report to endpoint.

        Returns:
            Report ID on success, None on failure
        """
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
                    return report.get('report_id')

        except (urllib.error.URLError, OSError) as e:
            logger.debug(f"Could not send bug report: {e}")
        except Exception as e:
            logger.debug(f"Bug report error: {e}")

        # Save locally if network fails
        self._save_local_report(report)
        return report.get('report_id')

    def _save_local_report(self, report: Dict):
        """Save report locally when network is unavailable"""
        try:
            from pathlib import Path
            report_dir = Path.home() / '.astromanager' / 'crash_reports'
            report_dir.mkdir(parents=True, exist_ok=True)

            report_file = report_dir / f"{report.get('report_id', 'unknown')}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)

            logger.info(f"Bug report saved locally: {report_file}")
        except Exception:
            pass

    def submit_manual_report(self, description: str,
                              steps_to_reproduce: str = '') -> Optional[str]:
        """
        Submit a manual bug report (from Help menu).

        Args:
            description: Bug description
            steps_to_reproduce: Steps to reproduce

        Returns:
            Report ID
        """
        report = self.create_report(description=description)
        report['manual'] = True
        report['steps_to_reproduce'] = steps_to_reproduce
        return self.send_report(report)


# Global instance
_reporter = None


def get_bug_reporter(version='1.0.0') -> AnonymousBugReporter:
    """Get global bug reporter instance"""
    global _reporter
    if _reporter is None:
        try:
            from core.config import get_config
            config = get_config()
            enabled = config.get('bug_reporting.enabled', True)
            endpoint = config.get('bug_reporting.endpoint_url', DEFAULT_ENDPOINT)
            _reporter = AnonymousBugReporter(version=version, endpoint=endpoint, enabled=enabled)
        except Exception:
            _reporter = AnonymousBugReporter(version=version, enabled=True)
    return _reporter
