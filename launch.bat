@echo off
title AstroManager
cd /d "%~dp0"

REM === Find Python (try multiple methods) ===
set "PYTHON="

REM 1. Windows Python Launcher (most reliable)
py -3 --version >nul 2>&1
if not errorlevel 1 set "PYTHON=py -3"
if defined PYTHON goto :found_python

REM 2. python in PATH
python --version >nul 2>&1
if not errorlevel 1 set "PYTHON=python"
if defined PYTHON goto :found_python

REM 3. python3 in PATH
python3 --version >nul 2>&1
if not errorlevel 1 set "PYTHON=python3"
if defined PYTHON goto :found_python

echo.
echo  Python not found. Please install Python 3.8+ from python.org
echo  Make sure to check "Add Python to PATH" during installation.
echo.
pause
exit /b 1

:found_python

REM === Venv local a chaque PC (pas dans le dossier NAS synchronise) ===
set "VENV_DIR=%LOCALAPPDATA%\AstroManager\venv"

REM === Check if venv exists and works ===
if not exist "%VENV_DIR%\Scripts\python.exe" goto :create_venv
"%VENV_DIR%\Scripts\python.exe" -c "print('ok')" >nul 2>&1
if not errorlevel 1 goto :venv_ok

:create_venv
if exist "%VENV_DIR%" (
    echo Recreating virtual environment...
    rmdir /s /q "%VENV_DIR%"
)
echo Creating virtual environment...
if not exist "%LOCALAPPDATA%\AstroManager" mkdir "%LOCALAPPDATA%\AstroManager"
%PYTHON% -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo.
    echo  Failed to create virtual environment.
    echo  VENV_DIR: %VENV_DIR%
    echo  PYTHON: %PYTHON%
    echo.
    pause
    exit /b 1
)
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo.
    echo  Virtual environment created but python.exe not found.
    echo  Check: %VENV_DIR%\Scripts\
    echo.
    pause
    exit /b 1
)

:venv_ok
REM === Activate venv ===
call "%VENV_DIR%\Scripts\activate.bat"

REM === Install deps (re-install if requirements.txt changes) ===
set "MARKER=%VENV_DIR%\.deps_installed"
if exist "%MARKER%" (
    fc /b requirements.txt "%MARKER%" >nul 2>&1 && goto :launch
)
echo Installing dependencies...
pip install -q -r requirements.txt
copy /y requirements.txt "%MARKER%" >nul 2>&1

:launch
REM Use pythonw (no console) if available
if exist "%VENV_DIR%\Scripts\pythonw.exe" (
    start "" "%VENV_DIR%\Scripts\pythonw.exe" "%~dp0astromanager.py" %*
) else (
    python astromanager.py %*
)
