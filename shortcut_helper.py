"""
Desktop shortcut auto-creation helper.
At first launch, offers to create a desktop shortcut if none is detected.
Stores user choice in config to never ask again.

Cross-platform: Windows (.lnk), Linux (.desktop), macOS (info only).

Usage in main script, AFTER window.show():
    from shortcut_helper import offer_shortcut
    offer_shortcut(app_name, main_script, icon_file, db_or_config)
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


def _project_dir() -> Path:
    """Get the project root directory."""
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


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


def _shortcut_exists(app_name: str) -> bool:
    """Check if a desktop shortcut already exists for this app."""
    desktop = _desktop_path()
    if not desktop.exists():
        return False
    if sys.platform == "win32":
        return (desktop / f"{app_name}.lnk").exists()
    elif sys.platform == "linux":
        safe = app_name.lower().replace(" ", "-").replace("è", "e").replace("é", "e")
        return (desktop / f"{safe}.desktop").exists()
    return False


def _create_windows_shortcut(app_name: str, main_script: str, icon_file: str) -> bool:
    """Create .lnk shortcut on Windows desktop."""
    import subprocess
    project = _project_dir()
    desktop = _desktop_path()

    # Find best pythonw.exe: venv first, then system
    pythonw = project / "venv" / "Scripts" / "pythonw.exe"
    if not pythonw.exists():
        pythonw = Path(sys.executable).parent / "pythonw.exe"
    if not pythonw.exists():
        pythonw = Path(sys.executable)

    icon_path = project / icon_file
    shortcut_path = desktop / f"{app_name}.lnk"

    ps_script = (
        f'$s = (New-Object -ComObject WScript.Shell)'
        f'.CreateShortcut("{shortcut_path}");'
        f'$s.TargetPath = "{pythonw}";'
        f'$s.Arguments = "{main_script}";'
        f'$s.WorkingDirectory = "{project}";'
        f'$s.IconLocation = "{icon_path},0";'
        f'$s.Description = "{app_name}";'
        f'$s.Save()'
    )

    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_script],
            capture_output=True, timeout=10
        )
        return result.returncode == 0
    except Exception as e:
        logger.warning("Failed to create Windows shortcut: %s", e)
        return False


def _create_linux_shortcut(app_name: str, main_script: str, icon_file: str) -> bool:
    """Create .desktop file on Linux desktop."""
    project = _project_dir()
    desktop = _desktop_path()
    desktop.mkdir(parents=True, exist_ok=True)

    python_exe = project / "venv" / "bin" / "python"
    if not python_exe.exists():
        python_exe = Path(sys.executable)

    icon_path = project / icon_file.replace(".ico", ".png")
    safe = app_name.lower().replace(" ", "-").replace("è", "e").replace("é", "e")
    shortcut_path = desktop / f"{safe}.desktop"

    content = (
        f"[Desktop Entry]\n"
        f"Version=1.0\n"
        f"Type=Application\n"
        f"Name={app_name}\n"
        f"Exec={python_exe} {project / main_script}\n"
        f"Icon={icon_path}\n"
        f"Path={project}\n"
        f"Terminal=false\n"
        f"Categories=Office;Education;\n"
    )

    try:
        shortcut_path.write_text(content, encoding="utf-8")
        shortcut_path.chmod(shortcut_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
        return True
    except Exception as e:
        logger.warning("Failed to create Linux shortcut: %s", e)
        return False


def offer_shortcut(app_name: str, main_script: str, icon_file: str,
                   get_config=None, set_config=None):
    """
    Check if a desktop shortcut exists. If not, and if user hasn't declined
    before, show a dialog offering to create one.

    Parameters:
        app_name: Display name (e.g. "BiblioThèque")
        main_script: Main .py file (e.g. "bibliotheque.py")
        icon_file: Icon file (e.g. "icon.ico" or "logo.ico")
        get_config: callable(key) -> value or None, to read config
        set_config: callable(key, value), to save config
    """
    # Skip on macOS (no auto shortcut) or PyInstaller bundles
    if sys.platform == "darwin" or hasattr(sys, '_MEIPASS'):
        return

    # Check if user already declined or shortcut was created
    config_key = "shortcut_offered"
    if get_config:
        try:
            if get_config(config_key):
                return
        except Exception:
            pass

    # Check if shortcut already exists
    if _shortcut_exists(app_name):
        if set_config:
            set_config(config_key, "exists")
        return

    # Show dialog
    try:
        from PyQt6.QtWidgets import QMessageBox
    except ImportError:
        return

    msg = QMessageBox()
    msg.setWindowTitle(app_name)
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setText(_T(
        f"Créer un raccourci {app_name} sur le bureau ?",
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
            success = _create_windows_shortcut(app_name, main_script, icon_file)
        elif sys.platform == "linux":
            success = _create_linux_shortcut(app_name, main_script, icon_file)

        if success:
            QMessageBox.information(
                None, app_name,
                _T("Raccourci créé sur le bureau !",
                    "Desktop shortcut created!")
            )
        else:
            QMessageBox.warning(
                None, app_name,
                _T("Impossible de créer le raccourci.",
                    "Could not create the shortcut.")
            )

    # Remember choice so we don't ask again
    if set_config:
        set_config(config_key, "offered")
