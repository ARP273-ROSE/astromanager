"""
Desktop shortcut auto-creation helper.
At first launch, offers to create a desktop shortcut if none is detected.
Stores user choice in config to never ask again.

Cross-platform: Windows (.lnk), Linux (.desktop), macOS (info only).

Usage in main script, AFTER window.show():
    from shortcut_helper import offer_shortcut
    offer_shortcut(app_name, main_script, icon_file, get_config, set_config)
"""

import os
import sys
import stat
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── i18n ─────────────────────────────────────────────────────────────────────
try:
    import locale
    _LANG = "fr" if (locale.getdefaultlocale()[0] or "").startswith("fr") else "en"
except Exception:
    _LANG = "en"


def _T(fr: str, en: str) -> str:
    return fr if _LANG == "fr" else en


def _get_project_dir() -> Path:
    """Get the project root directory from the running script (sys.argv[0])."""
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    # Use the actually running script to find the project directory
    main_script = sys.argv[0] if sys.argv else __file__
    return Path(os.path.abspath(main_script)).parent


def _desktop_path() -> Path:
    """Get the user's Desktop path (cross-platform)."""
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            )
            desktop = winreg.QueryValueEx(key, "Desktop")[0]
            winreg.CloseKey(key)
            return Path(desktop)
        except Exception:
            pass
    elif sys.platform == "linux":
        xdg = os.environ.get("XDG_DESKTOP_DIR")
        if xdg:
            return Path(xdg)
    return Path.home() / "Desktop"


def _get_shortcut_path(app_name: str) -> Path:
    """Get the expected shortcut file path."""
    desktop = _desktop_path()
    if sys.platform == "win32":
        return desktop / f"{app_name}.lnk"
    elif sys.platform == "linux":
        safe = app_name.lower().replace(" ", "-").replace("è", "e").replace("é", "e")
        return desktop / f"{safe}.desktop"
    return desktop / app_name


def _shortcut_exists(app_name: str) -> bool:
    """Check if a desktop shortcut already exists for this app."""
    return _get_shortcut_path(app_name).exists()


def _read_windows_shortcut(shortcut_path: Path) -> dict:
    """Read a .lnk shortcut and return its properties."""
    import subprocess
    try:
        ps = (
            f'$s = (New-Object -ComObject WScript.Shell)'
            f'.CreateShortcut("{shortcut_path}");'
            f'Write-Output $s.TargetPath;'
            f'Write-Output $s.WorkingDirectory'
        )
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=10
        )
        lines = r.stdout.strip().splitlines()
        if len(lines) >= 2:
            return {"target": lines[0].strip(), "workdir": lines[1].strip()}
    except Exception:
        pass
    return {}


def _shortcut_paths_valid(app_name: str, project: Path, main_script: str) -> bool:
    """Check if existing shortcut points to the correct project location."""
    if sys.platform == "win32":
        shortcut_path = _get_shortcut_path(app_name)
        if not shortcut_path.exists():
            return False
        props = _read_windows_shortcut(shortcut_path)
        if not props:
            return False
        # Check that WorkingDirectory matches current project
        current_workdir = str(project).replace("/", "\\").rstrip("\\").lower()
        shortcut_workdir = props.get("workdir", "").rstrip("\\").lower()
        return current_workdir == shortcut_workdir
    elif sys.platform == "linux":
        shortcut_path = _get_shortcut_path(app_name)
        if not shortcut_path.exists():
            return False
        try:
            content = shortcut_path.read_text(encoding="utf-8")
            return str(project / main_script) in content
        except Exception:
            return False
    return False


def _copy_icon_locally(icon_source: Path) -> Path:
    """Copy icon to local storage so .lnk shortcuts display it reliably.

    Network/NAS paths may not resolve for shortcut icons on Windows.
    Handles icons in subdirectories (e.g. assets/icon.ico).
    Returns the local copy path, or the original if copy fails.
    """
    if not icon_source.exists():
        return icon_source
    local_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "AstroManager"
    if not local_dir.parent.exists():
        return icon_source
    try:
        local_dir.mkdir(parents=True, exist_ok=True)
        local_icon = local_dir / icon_source.name
        # Only copy if source is newer or local doesn't exist
        if not local_icon.exists() or icon_source.stat().st_mtime > local_icon.stat().st_mtime:
            import shutil
            shutil.copy2(icon_source, local_icon)
            logger.info("Icon copied locally: %s", local_icon)
        return local_icon
    except Exception as e:
        logger.debug("Could not copy icon locally: %s", e)
        return icon_source


def _create_windows_shortcut(app_name: str, main_script: str, icon_file: str,
                             project: Path) -> bool:
    """Create .lnk shortcut on Windows desktop.

    Targets launch.bat instead of a specific pythonw.exe so the shortcut
    works on any PC (NAS / synced folder) regardless of Python install path.
    The batch file detects Python locally, creates venv if needed, and launches
    with pythonw (no console).
    """
    import subprocess
    desktop = _desktop_path()
    launch_bat = project / "launch.bat"
    icon_path = _copy_icon_locally(project / icon_file)
    shortcut_path = desktop / f"{app_name}.lnk"

    # Sanitize all values for PowerShell string interpolation
    def _ps_escape(val):
        return str(val).replace('"', '`"').replace("'", "''")

    ps_script = (
        f'$s = (New-Object -ComObject WScript.Shell)'
        f'.CreateShortcut("{_ps_escape(shortcut_path)}");'
        f'$s.TargetPath = "{_ps_escape(launch_bat)}";'
        f'$s.Arguments = "";'
        f'$s.WorkingDirectory = "{_ps_escape(project)}";'
        f'$s.IconLocation = "{_ps_escape(icon_path)},0";'
        f'$s.Description = "{_ps_escape(app_name)}";'
        f'$s.WindowStyle = 7;'
        f'$s.Save()'
    )

    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_script],
            capture_output=True, timeout=10
        )
        if result.returncode == 0:
            logger.info("Shortcut created: %s -> %s", shortcut_path, launch_bat)
            return True
        logger.warning("PowerShell shortcut failed: %s", result.stderr)
        return False
    except Exception as e:
        logger.warning("Failed to create Windows shortcut: %s", e)
        return False


def _create_linux_shortcut(app_name: str, main_script: str, icon_file: str,
                           project: Path) -> bool:
    """Create .desktop file on Linux desktop.

    Uses launch.sh for portability across PCs (NAS/synced folder).
    """
    desktop = _desktop_path()
    desktop.mkdir(parents=True, exist_ok=True)

    launch_sh = project / "launch.sh"
    icon_path = project / icon_file.replace(".ico", ".png")
    safe = app_name.lower().replace(" ", "-").replace("è", "e").replace("é", "e")
    shortcut_path = desktop / f"{safe}.desktop"

    # Sanitize values to prevent .desktop injection via newlines
    def _desktop_escape(val):
        return str(val).replace("\n", "").replace("\r", "")

    content = (
        f"[Desktop Entry]\n"
        f"Version=1.0\n"
        f"Type=Application\n"
        f"Name={_desktop_escape(app_name)}\n"
        f"Exec={_desktop_escape(launch_sh)}\n"
        f"Icon={_desktop_escape(icon_path)}\n"
        f"Path={_desktop_escape(project)}\n"
        f"Terminal=false\n"
        f"Categories=Office;Education;\n"
    )

    try:
        shortcut_path.write_text(content, encoding="utf-8")
        shortcut_path.chmod(shortcut_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
        logger.info("Shortcut created: %s", shortcut_path)
        return True
    except Exception as e:
        logger.warning("Failed to create Linux shortcut: %s", e)
        return False


def offer_shortcut(app_name: str, main_script: str, icon_file: str,
                   get_config=None, set_config=None):
    """
    Check if a desktop shortcut exists with correct paths.
    If not, or if paths are stale, offer to create/update it.

    Parameters:
        app_name: Display name (e.g. "AstroManager")
        main_script: Main .py file (e.g. "astromanager.py")
        icon_file: Icon file (e.g. "assets/icon.ico")
        get_config: callable(key) -> value or None, to read config
        set_config: callable(key, value), to save config
    """
    # Skip on macOS (no auto shortcut) or PyInstaller bundles
    if sys.platform == "darwin" or hasattr(sys, '_MEIPASS'):
        return

    # Determine the actual project directory from the running script
    project = _get_project_dir()

    # If shortcut exists AND paths are correct — nothing to do
    if _shortcut_exists(app_name) and _shortcut_paths_valid(app_name, project, main_script):
        return

    # If shortcut exists but paths are WRONG — offer to update
    needs_update = _shortcut_exists(app_name) and not _shortcut_paths_valid(
        app_name, project, main_script)

    # If shortcut doesn't exist, check if user already declined
    if not needs_update:
        config_key = "shortcut_offered"
        if get_config:
            try:
                if get_config(config_key):
                    return
            except Exception:
                pass

    # Show dialog
    try:
        from PyQt6.QtWidgets import QMessageBox
    except ImportError:
        return

    msg = QMessageBox()
    msg.setWindowTitle(app_name)
    msg.setIcon(QMessageBox.Icon.Question)

    if needs_update:
        msg.setText(_T(
            f"Le raccourci {app_name} pointe vers un ancien emplacement.\n"
            f"Mettre a jour avec le chemin actuel ?",
            f"The {app_name} shortcut points to an old location.\n"
            f"Update with the current path?"
        ))
        msg.setInformativeText(str(project))
    else:
        msg.setText(_T(
            f"Creer un raccourci {app_name} sur le bureau ?",
            f"Create a {app_name} shortcut on the desktop?"
        ))
        msg.setInformativeText(_T(
            "Vous pouvez aussi le faire plus tard depuis le menu Aide.",
            "You can also do this later from the Help menu."
        ))

    msg.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    msg.setDefaultButton(QMessageBox.StandardButton.Yes)

    result = msg.exec()

    if result == QMessageBox.StandardButton.Yes:
        success = False
        if sys.platform == "win32":
            success = _create_windows_shortcut(app_name, main_script, icon_file, project)
        elif sys.platform == "linux":
            success = _create_linux_shortcut(app_name, main_script, icon_file, project)

        if success:
            QMessageBox.information(
                None, app_name,
                _T("Raccourci cree sur le bureau !",
                    "Desktop shortcut created!")
            )
        else:
            QMessageBox.warning(
                None, app_name,
                _T("Impossible de creer le raccourci.",
                    "Could not create the shortcut.")
            )

    # Remember choice so we don't ask again (only for new shortcuts, not updates)
    if not needs_update and set_config:
        set_config("shortcut_offered", "offered")


def create_shortcut_force(app_name: str, main_script: str, icon_file: str):
    """
    Force-create or update a desktop shortcut (called from Help menu).
    Returns True on success, False on failure. Shows result via QMessageBox.
    """
    if sys.platform == "darwin":
        return False

    project = _get_project_dir()
    success = False
    if sys.platform == "win32":
        success = _create_windows_shortcut(app_name, main_script, icon_file, project)
    elif sys.platform == "linux":
        success = _create_linux_shortcut(app_name, main_script, icon_file, project)

    try:
        from PyQt6.QtWidgets import QMessageBox
        if success:
            QMessageBox.information(
                None, app_name,
                _T("Raccourci cree sur le bureau !",
                    "Desktop shortcut created!")
            )
        else:
            QMessageBox.warning(
                None, app_name,
                _T("Impossible de creer le raccourci.",
                    "Could not create the shortcut.")
            )
    except ImportError:
        pass

    return success
