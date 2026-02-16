@echo off
echo ============================================================
echo   AstroManager - Windows Build (.exe)
echo ============================================================
echo.

REM Activate venv if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Check PyInstaller is installed
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

echo Building AstroManager.exe...
echo.
pyinstaller astromanager.spec --noconfirm

if errorlevel 1 (
    echo.
    echo BUILD FAILED! Check the errors above.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   BUILD SUCCESSFUL!
echo   Output: dist\AstroManager\AstroManager.exe
echo ============================================================
pause
