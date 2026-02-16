#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - CONFIGURATION MANAGER
================================================================================
Centralized configuration management with auto-detection of system capabilities.
Supports YAML configuration files with defaults.
================================================================================
"""

import os
import sys
import yaml
import platform
import threading
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Default configuration paths
CONFIG_DIR = Path.home() / '.astromanager'
CONFIG_FILE = CONFIG_DIR / 'config.yaml'
if getattr(sys, 'frozen', False):
    _BASE = Path(sys._MEIPASS)
else:
    _BASE = Path(__file__).parent.parent
DEFAULT_CONFIG_FILE = _BASE / 'config' / 'default_config.yaml'

# Ensure config directory exists with restrictive permissions
try:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if platform.system() != 'Windows':
        os.chmod(str(CONFIG_DIR), 0o700)
except OSError:
    pass


class ConfigManager:
    """Centralized configuration manager with system detection"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Thread-safe singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize configuration manager"""
        if self._initialized:
            return

        self.config = {}
        self.system_caps = {}
        self._load_config()
        self._detect_system_capabilities()
        self._initialized = True

    def _load_config(self):
        """Load configuration from file or create default"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f) or {}
                logger.info(f"Configuration loaded from {CONFIG_FILE}")
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                self.config = self._get_default_config()
        else:
            # Create default config
            self.config = self._get_default_config()
            self.save_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        if DEFAULT_CONFIG_FILE.exists():
            try:
                with open(DEFAULT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Error loading default config: {e}")

        # Hardcoded fallback
        return {
            'application': {
                'version': '1.0.0',
                'language': 'auto',
                'theme': 'cosmic_dark',
            },
            'system': {
                'workers': 0,  # Auto-detect
                'batch_size': 1000,
                'cache_size': 5000,
                'enable_caching': True,
            },
            'observatory': {
                'latitude': 51.4769,  # Greenwich default
                'longitude': -0.0005,
                'elevation_m': 46,
                'timezone': 'UTC',
            },
            'analysis': {
                'enable_simbad': True,
                'enable_plate_solving': False,
                'enable_weather_fetch': False,
                'duplicate_detection': True,
                'generate_thumbnails': False,
                'generate_graphs': True,
                'generate_latex': True,
                'generate_csv': True,
            },
            'compression': {
                'default_profile': 'zlib_6',
                'delete_source': False,
                'verify_integrity': True,
                'quarantine_failed': True,
            },
            'plate_solving': {
                'solver': 'astap',
                'astap_path': None,
                'astrometry_path': None,
                'timeout_sec': 5,
                'max_retries': 3,
            },
            'weather': {
                'api_provider': 'open-meteo',
                'api_key': None,
                'cache_duration_days': 365,
            },
            'bug_reporting': {
                'enabled': False,
            },
            'ui': {
                'window_width': 1200,
                'window_height': 880,
                'console_max_lines': 1000,
                'show_splash_screen': True,
            },
        }

    def _detect_system_capabilities(self):
        """Auto-detect system specs and optimize settings"""
        try:
            import psutil
            cpu_count = psutil.cpu_count(logical=True) or os.cpu_count() or 4
            cpu_physical = psutil.cpu_count(logical=False) or cpu_count
            ram_gb = psutil.virtual_memory().total / (1024**3)
        except ImportError:
            logger.warning("psutil not available, using fallback system detection")
            cpu_count = os.cpu_count() or 4
            cpu_physical = max(1, cpu_count // 2)
            ram_gb = 8.0  # Conservative default

        # Detect storage type (SSD vs HDD)
        storage_type = self._detect_storage_type()

        # Calculate optimal workers based on resources
        if ram_gb < 8:
            # Low RAM: Conservative settings
            optimal_workers = max(1, cpu_physical // 2)
            batch_size = 500
            cache_size = 1000
        elif ram_gb < 16:
            # Medium RAM: Balanced settings
            optimal_workers = max(1, cpu_physical - 1)
            batch_size = 1000
            cache_size = 5000
        else:
            # High RAM: Aggressive settings
            optimal_workers = cpu_physical
            batch_size = 5000
            cache_size = 10000

        # Adjust for storage type
        if storage_type == 'network':
            # Network/NAS: Severely limit I/O workers to avoid network saturation
            optimal_workers = max(1, min(4, optimal_workers // 3))
        elif storage_type == 'hdd':
            # HDD: Reduce I/O workers to avoid disk contention
            optimal_workers = max(2, optimal_workers // 2)

        # Detect CPU name
        cpu_name = self._detect_cpu_name()

        # Detect proper OS name (Windows 11 vs 10)
        os_name = platform.system()
        os_version = platform.version()
        if os_name == 'Windows':
            try:
                build = int(os_version.split('.')[-1]) if '.' in os_version else 0
                if build >= 22000:
                    os_name = 'Windows 11'
                else:
                    os_name = 'Windows 10'
            except (ValueError, IndexError):
                pass

        self.system_caps = {
            'cpu_count': cpu_count,
            'cpu_count_logical': cpu_count,
            'cpu_count_physical': cpu_physical,
            'cpu_name': cpu_name,
            'ram_gb': round(ram_gb, 1),
            'storage_type': storage_type,
            'optimal_workers': optimal_workers,
            'batch_size': batch_size,
            'cache_size': cache_size,
            'os': os_name,
            'os_version': os_version,
            'python_version': platform.python_version(),
        }

        logger.info(f"System capabilities detected: {self.system_caps}")

    def _detect_cpu_name(self) -> str:
        """Detect CPU model name"""
        try:
            if platform.system() == 'Windows':
                try:
                    import winreg
                    with winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
                    ) as key:
                        cpu_name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                        return cpu_name.strip()
                except Exception:
                    pass
            elif platform.system() == 'Linux':
                try:
                    with open('/proc/cpuinfo', 'r') as f:
                        for line in f:
                            if line.startswith('model name'):
                                return line.split(':', 1)[1].strip()
                except Exception:
                    pass
            elif platform.system() == 'Darwin':
                try:
                    import subprocess
                    result = subprocess.run(
                        ['sysctl', '-n', 'machdep.cpu.brand_string'],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        return result.stdout.strip()
                except Exception:
                    pass
        except Exception:
            pass
        # Fallback
        proc = platform.processor()
        return proc if proc else 'Unknown'

    def _detect_storage_type(self, path: Optional[str] = None) -> str:
        """
        Detect storage type for a given path (SSD, HDD, or network).
        If path is None, detects the system disk type.
        Properly handles NAS, UNC paths, mapped network drives, SMB/NFS mounts.
        """
        check_path = path or str(Path.home())

        # ─── Phase 1: Detect network/NAS drives ───
        network = self._is_network_path(check_path)
        if network:
            return 'network'

        # ─── Phase 2: Detect local SSD vs HDD ───
        try:
            if platform.system() == 'Windows':
                return self._detect_storage_windows(check_path)

            elif platform.system() == 'Linux':
                return self._detect_storage_linux(check_path)

            elif platform.system() == 'Darwin':
                return self._detect_storage_macos(check_path)

        except Exception as e:
            logger.debug(f"Storage type detection error: {e}")

        # Default: assume SSD for better performance
        return 'ssd'

    @staticmethod
    def _is_network_path(path: str) -> bool:
        """
        Check if a path is a network/NAS/remote path.
        Handles: UNC paths (\\\\server\\share), mapped drives (Windows),
        NFS/CIFS/SMB mounts (Linux/macOS).
        """
        if not path:
            return False

        # Normalize path
        norm = os.path.normpath(path)

        # UNC paths: \\server\share or //server/share
        if norm.startswith('\\\\') or norm.startswith('//'):
            return True

        if platform.system() == 'Windows':
            # Check if drive letter maps to a network share
            try:
                import ctypes
                drive = os.path.splitdrive(norm)[0]
                if drive and len(drive) >= 2 and drive[1] == ':':
                    drive_root = drive + '\\'
                    DRIVE_REMOTE = 4
                    drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_root)
                    if drive_type == DRIVE_REMOTE:
                        return True
            except Exception:
                pass
        else:
            # Linux/macOS: check mount table for network filesystems
            try:
                real_path = os.path.realpath(path)
                mount_file = '/proc/mounts' if os.path.exists('/proc/mounts') else None
                if mount_file:
                    with open(mount_file, 'r') as f:
                        for line in f:
                            parts = line.split()
                            if len(parts) >= 3:
                                mount_point = parts[1]
                                fs_type = parts[2]
                                if (real_path.startswith(mount_point) and
                                        fs_type in ('nfs', 'nfs4', 'cifs', 'smbfs',
                                                     'fuse.sshfs', 'fuse.rclone',
                                                     'fuse.mergerfs', '9p', 'afs')):
                                    return True
                else:
                    # macOS: use mount command
                    import subprocess
                    result = subprocess.run(
                        ['mount'], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        for line in result.stdout.splitlines():
                            # Format: device on /mount/point (fstype, options)
                            if '(' in line:
                                mount_point = line.split(' on ')[1].split(' (')[0] if ' on ' in line else ''
                                fs_info = line.split('(')[1] if '(' in line else ''
                                if (real_path.startswith(mount_point) and
                                        any(fs in fs_info for fs in
                                            ['smbfs', 'nfs', 'cifs', 'afpfs', 'webdav'])):
                                    return True
            except Exception:
                pass

        return False

    def _detect_storage_windows(self, path: str) -> str:
        """Detect SSD vs HDD on Windows for a given path."""
        try:
            import wmi
            c = wmi.WMI()

            # Try to find which physical disk the path is on
            drive_letter = os.path.splitdrive(path)[0]
            if drive_letter and len(drive_letter) >= 2:
                # Query partitions to find the physical disk
                for disk in c.Win32_DiskDrive():
                    model = (disk.Model or '').upper()
                    for part in disk.associators("Win32_DiskDriveToDiskPartition"):
                        for logical in part.associators("Win32_LogicalDiskToPartition"):
                            if (logical.DeviceID or '').upper() == drive_letter.upper():
                                if 'SSD' in model or 'NVME' in model or 'SOLID STATE' in model:
                                    return 'ssd'
                                return 'hdd'

            # Fallback: check any physical disk
            for disk in c.Win32_DiskDrive():
                model = (disk.Model or '').upper()
                if 'SSD' in model or 'NVME' in model or 'SOLID STATE' in model:
                    return 'ssd'
                elif 'HDD' in model or 'HARD DISK' in model:
                    return 'hdd'
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Windows storage detection error: {e}")
        return 'ssd'

    def _detect_storage_linux(self, path: str) -> str:
        """Detect SSD vs HDD on Linux for a given path."""
        try:
            import subprocess, re
            real_path = os.path.realpath(path)
            df_result = subprocess.run(
                ['df', '--output=source', real_path],
                capture_output=True, text=True, timeout=5
            )
            device = df_result.stdout.strip().split('\n')[-1].strip()
            if device and device.startswith('/dev/'):
                base = re.sub(r'[0-9]+$', '', os.path.basename(device))
                base = re.sub(r'p[0-9]+$', '', base)
                rota_path = f'/sys/block/{base}/queue/rotational'
                if os.path.exists(rota_path):
                    with open(rota_path) as f:
                        return 'hdd' if f.read().strip() == '1' else 'ssd'
                if 'nvme' in base:
                    return 'ssd'
        except Exception as e:
            logger.debug(f"Linux storage detection error: {e}")
        return 'ssd'

    def _detect_storage_macos(self, path: str) -> str:
        """Detect SSD vs HDD on macOS for a given path."""
        try:
            import subprocess
            real_path = os.path.realpath(path)
            if not os.path.exists(real_path):
                return 'ssd'
            result = subprocess.run(
                ['diskutil', 'info', '--', real_path],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                output = result.stdout
                if 'Solid State' in output or 'SSD' in output:
                    return 'ssd'
                if 'HDD' in output or 'Rotational' in output:
                    return 'hdd'
            # Fallback: check root volume
            result = subprocess.run(
                ['diskutil', 'info', '/'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                output = result.stdout
                if 'Solid State' in output or 'SSD' in output:
                    return 'ssd'
                if 'HDD' in output or 'Rotational' in output:
                    return 'hdd'
            # NVMe check
            result = subprocess.run(
                ['system_profiler', 'SPNVMeDataType'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return 'ssd'
        except Exception as e:
            logger.debug(f"macOS storage detection error: {e}")
        return 'ssd'

    def detect_path_storage_type(self, path: str) -> str:
        """
        Public API: detect storage type for a specific folder path.
        Returns 'ssd', 'hdd', or 'network'.
        Use this when analyzing a user-selected folder (not the system disk).
        """
        return self._detect_storage_type(path)

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated path.

        Example:
            config.get('analysis.enable_simbad')  # Returns True
            config.get('system.workers')  # Returns 0 (auto)
        """
        keys = key_path.split('.')
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def set(self, key_path: str, value: Any):
        """
        Set configuration value by dot-separated path.

        Example:
            config.set('analysis.enable_simbad', False)
        """
        keys = key_path.split('.')
        config = self.config

        for key in keys[:-1]:
            if key not in config or not isinstance(config.get(key), dict):
                config[key] = {}
            config = config[key]

        config[keys[-1]] = value

    def save_config(self):
        """Save current configuration to file with restrictive permissions"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
            if platform.system() != 'Windows':
                os.chmod(str(CONFIG_FILE), 0o600)
            logger.info(f"Configuration saved to {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def get_workers(self) -> int:
        """Get optimal number of workers (auto-detected if 0)"""
        workers = self.get('system.workers', 0)
        if workers == 0:
            return self.system_caps.get('optimal_workers', 4)
        return workers

    def get_batch_size(self) -> int:
        """Get optimal batch size"""
        batch_size = self.get('system.batch_size')
        if batch_size is not None:
            return batch_size
        return self.system_caps.get('batch_size', 1000)

    def get_cache_size(self) -> int:
        """Get optimal cache size"""
        cache_size = self.get('system.cache_size')
        if cache_size is not None:
            return cache_size
        return self.system_caps.get('cache_size', 5000)

    def get_system_info(self) -> Dict[str, Any]:
        """Get system capabilities summary"""
        return self.system_caps.copy()


# Global singleton instance
_config_manager = None
_config_lock = threading.Lock()

def get_config() -> ConfigManager:
    """Get global configuration manager instance (thread-safe)"""
    global _config_manager
    if _config_manager is None:
        with _config_lock:
            if _config_manager is None:
                _config_manager = ConfigManager()
    return _config_manager
