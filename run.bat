@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
REM ============================================================================
REM  AstroManager - Windows Launcher
REM  Auto-detects/installs: Python, winget, LaTeX, venv, pip dependencies
REM  Then launches astromanager.py
REM ============================================================================

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
set "VENV_DIR=%SCRIPT_DIR%venv"
set "PYTHON_EXE="
set "LANG=en"

REM -- Detect system language (FR or EN)
for /f "tokens=3" %%a in ('reg query "HKCU\Control Panel\International" /v LocaleName 2^>nul ^| findstr /i "LocaleName"') do (
    echo %%a | findstr /i "^fr" >nul 2>&1 && set "LANG=fr"
)

echo.
echo   ============================================================
echo     AstroManager - Setup
echo   ============================================================
echo.

REM ============================================================================
REM  Step 1: Find or install Python
REM ============================================================================
call :find_python
if defined PYTHON_EXE goto :python_ok

REM Python not found - install it
echo.
if "!LANG!"=="fr" (
    echo   [X] Python 3 n'est pas installe.
    echo       Installation automatique en cours...
) else (
    echo   [X] Python 3 is not installed.
    echo       Installing automatically...
)

REM Ensure winget is available
call :ensure_winget
if errorlevel 1 goto :manual_python

echo.
if "!LANG!"=="fr" (
    echo   Installation de Python 3.12 via winget...
) else (
    echo   Installing Python 3.12 via winget...
)
winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements --silent
if errorlevel 1 (
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
)

REM Refresh PATH from registry to pick up new installation
call :refresh_path

REM Try again
call :find_python
if defined PYTHON_EXE goto :python_ok

REM Still not found - probe common install locations manually
for %%d in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%ProgramFiles%\Python313\python.exe"
    "%ProgramFiles%\Python312\python.exe"
    "%ProgramFiles%\Python311\python.exe"
    "%ProgramFiles(x86)%\Python312\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
) do (
    if exist %%d (
        set "PYTHON_EXE=%%~d"
        goto :python_ok
    )
)

:manual_python
echo.
if "!LANG!"=="fr" (
    echo   [!] Impossible d'installer Python automatiquement.
    echo       Telechargez-le depuis : https://www.python.org/downloads/windows/
    echo       IMPORTANT : Cochez "Add Python to PATH" pendant l'installation !
    echo       Puis relancez run.bat.
) else (
    echo   [!] Cannot install Python automatically.
    echo       Download it from: https://www.python.org/downloads/windows/
    echo       IMPORTANT: Check "Add Python to PATH" during installation!
    echo       Then rerun run.bat.
)
start "" "https://www.python.org/downloads/windows/"
pause
goto :eof

:python_ok
REM Display Python version
for /f "tokens=*" %%v in ('"!PYTHON_EXE!" --version 2^>^&1') do set "PY_VER=%%v"
echo   [OK] !PY_VER! (!PYTHON_EXE!)

REM ============================================================================
REM  Step 2: Virtual environment
REM ============================================================================
if exist "!VENV_DIR!\Scripts\python.exe" (
    REM Verify the existing venv actually works (not broken by removed Python)
    "!VENV_DIR!\Scripts\python.exe" -c "import sys; sys.exit(0)" >nul 2>&1
    if !errorlevel!==0 (
        if "!LANG!"=="fr" (
            echo   [OK] Environnement virtuel existant
        ) else (
            echo   [OK] Existing virtual environment
        )
        goto :activate_venv
    ) else (
        if "!LANG!"=="fr" (
            echo   [!] Environnement virtuel casse ^(Python de base supprime^). Recreation...
        ) else (
            echo   [!] Broken virtual environment ^(base Python removed^). Recreating...
        )
        rmdir /s /q "!VENV_DIR!" >nul 2>&1
    )
)

echo.
if "!LANG!"=="fr" (
    echo   Creation de l'environnement virtuel...
) else (
    echo   Creating virtual environment...
)
"!PYTHON_EXE!" -m venv "!VENV_DIR!"
if errorlevel 1 (
    if "!LANG!"=="fr" (
        echo   [!] Impossible de creer le venv, utilisation de Python global
    ) else (
        echo   [!] Cannot create venv, using global Python
    )
    goto :install_deps_global
)

:activate_venv
set "PYTHON_EXE=!VENV_DIR!\Scripts\python.exe"
set "PATH=!VENV_DIR!\Scripts;!PATH!"
if "!LANG!"=="fr" (
    echo   [OK] Environnement virtuel active
) else (
    echo   [OK] Virtual environment activated
)

REM Install/upgrade pip
"!PYTHON_EXE!" -m pip install --upgrade pip --quiet >nul 2>&1

:install_deps_global
REM Install dependencies from requirements.txt
if exist "%SCRIPT_DIR%requirements.txt" (
    if "!LANG!"=="fr" (
        echo   Installation des dependances Python ^(peut prendre quelques minutes^)...
    ) else (
        echo   Installing Python dependencies ^(may take a few minutes^)...
    )
    "!PYTHON_EXE!" -m pip install -r "%SCRIPT_DIR%requirements.txt" 2>nul
    if not errorlevel 1 (
        if "!LANG!"=="fr" (
            echo   [OK] Dependances Python installees
        ) else (
            echo   [OK] Python dependencies installed
        )
    ) else (
        if "!LANG!"=="fr" (
            echo   [!] Certaines dependances ont echoue ^(le programme reessaiera au demarrage^)
        ) else (
            echo   [!] Some dependencies failed ^(the program will retry at startup^)
        )
    )
)

REM ============================================================================
REM  Step 3: LaTeX (optional, for PDF reports)
REM ============================================================================
call :find_latex
if defined LATEX_EXE (
    echo   [OK] LaTeX ^(!LATEX_EXE!^)
    goto :launch
)

echo.
if "!LANG!"=="fr" (
    echo   [?] LaTeX ^(pdflatex^) n'est pas installe.
    echo       Il est necessaire pour generer les rapports PDF complets.
    echo       Le programme fonctionnera sans, avec des rapports PDF simplifies.
    echo.
    echo   Installer MiKTeX automatiquement ? [O/N]
) else (
    echo   [?] LaTeX ^(pdflatex^) is not installed.
    echo       It is needed to generate full PDF reports.
    echo       The program will work without it, with simplified PDF reports.
    echo.
    echo   Install MiKTeX automatically? [Y/N]
)
set /p "INSTALL_LATEX=> "
if /I not "!INSTALL_LATEX!"=="O" if /I not "!INSTALL_LATEX!"=="Y" (
    echo.
    goto :launch
)

call :ensure_winget
if errorlevel 1 (
    if "!LANG!"=="fr" (
        echo   [!] winget non disponible. Installez MiKTeX manuellement : https://miktex.org/download
    ) else (
        echo   [!] winget not available. Install MiKTeX manually: https://miktex.org/download
    )
    goto :launch
)

echo.
if "!LANG!"=="fr" (
    echo   Installation de MiKTeX via winget...
) else (
    echo   Installing MiKTeX via winget...
)
winget install -e --id MiKTeX.MiKTeX --accept-source-agreements --accept-package-agreements

REM Refresh PATH from registry
call :refresh_path

REM Try to find pdflatex now
call :find_latex
if defined LATEX_EXE (
    echo   [OK] LaTeX installe ^(!LATEX_EXE!^)
) else (
    REM Probe common MiKTeX paths
    for %%d in (
        "%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe"
        "%ProgramFiles%\MiKTeX\miktex\bin\x64\pdflatex.exe"
        "%ProgramFiles(x86)%\MiKTeX\miktex\bin\x64\pdflatex.exe"
        "C:\MiKTeX\miktex\bin\x64\pdflatex.exe"
        "%LOCALAPPDATA%\Programs\MiKTeX 2.9\miktex\bin\x64\pdflatex.exe"
    ) do (
        if exist %%d (
            REM Add to PATH for this session
            for %%f in (%%d) do set "MIKTEX_BIN=%%~dpf"
            set "PATH=!MIKTEX_BIN!;!PATH!"
            echo   [OK] LaTeX trouve : %%~d
            if "!LANG!"=="fr" (
                echo   [!] Pour les prochaines sessions, ajoutez a votre PATH :
            ) else (
                echo   [!] For future sessions, add to your PATH:
            )
            echo       !MIKTEX_BIN!
            goto :launch
        )
    )
    if "!LANG!"=="fr" (
        echo   [!] MiKTeX installe mais pdflatex pas encore dans le PATH.
        echo       Fermez et rouvrez le terminal, ou ajoutez MiKTeX au PATH manuellement.
    ) else (
        echo   [!] MiKTeX installed but pdflatex not yet in PATH.
        echo       Close and reopen the terminal, or add MiKTeX to PATH manually.
    )
)

REM ============================================================================
REM  Step 4: Launch AstroManager
REM ============================================================================
:launch
echo.
echo   ============================================================
if "!LANG!"=="fr" (
    echo     AstroManager - Demarrage...
) else (
    echo     AstroManager - Starting...
)
echo   ============================================================
echo.

"!PYTHON_EXE!" "%SCRIPT_DIR%astromanager.py" %*
set "EXIT_CODE=!errorlevel!"
if !EXIT_CODE! neq 0 (
    echo.
    if "!LANG!"=="fr" (
        echo   Erreur lors du demarrage ^(code: !EXIT_CODE!^)
    ) else (
        echo   Error during startup ^(code: !EXIT_CODE!^)
    )
    pause
)
goto :eof

REM ============================================================================
REM  Helper: find Python executable
REM ============================================================================
:find_python
set "PYTHON_EXE="

REM Try python in PATH - verify it's real (not Windows Store stub)
where python >nul 2>&1
if !errorlevel!==0 (
    REM Check it actually runs and is Python 3.8+
    python -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" >nul 2>&1
    if !errorlevel!==0 (
        REM Resolve full path to avoid the Store stub
        for /f "tokens=*" %%p in ('python -c "import sys; print(sys.executable)" 2^>nul') do (
            set "PYTHON_EXE=%%p"
        )
        if defined PYTHON_EXE exit /b 0
    )
)

REM Try py launcher
where py >nul 2>&1
if !errorlevel!==0 (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" >nul 2>&1
    if !errorlevel!==0 (
        for /f "tokens=*" %%p in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do (
            set "PYTHON_EXE=%%p"
        )
        if defined PYTHON_EXE exit /b 0
    )
)
exit /b 1

REM ============================================================================
REM  Helper: find LaTeX (pdflatex)
REM ============================================================================
:find_latex
set "LATEX_EXE="
where pdflatex >nul 2>&1
if !errorlevel!==0 (
    for /f "tokens=*" %%p in ('where pdflatex 2^>nul') do (
        set "LATEX_EXE=%%p"
        exit /b 0
    )
)
exit /b 1

REM ============================================================================
REM  Helper: refresh PATH from Windows registry
REM  Re-reads Machine + User PATH so newly installed programs are found
REM ============================================================================
:refresh_path
set "NEW_PATH="

REM Read system PATH
for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul ^| findstr /i "Path"') do (
    set "NEW_PATH=%%b"
)

REM Read user PATH and append
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v Path 2^>nul ^| findstr /i "Path"') do (
    if defined NEW_PATH (
        set "NEW_PATH=!NEW_PATH!;%%b"
    ) else (
        set "NEW_PATH=%%b"
    )
)

REM Append essentials
if defined NEW_PATH (
    set "PATH=!NEW_PATH!;%SystemRoot%\system32;%SystemRoot%"
    REM Re-add venv if it was activated
    if exist "!VENV_DIR!\Scripts\python.exe" (
        set "PATH=!VENV_DIR!\Scripts;!PATH!"
    )
)
exit /b 0

REM ============================================================================
REM  Helper: ensure winget is available, install if not
REM ============================================================================
:ensure_winget
where winget >nul 2>&1
if !errorlevel!==0 exit /b 0

if "!LANG!"=="fr" (
    echo   winget n'est pas disponible. Tentative d'installation...
) else (
    echo   winget is not available. Attempting installation...
)

REM Method 1: Register via PowerShell (Windows 11 / recent Win10)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel!==0 (
    call :refresh_path
    where winget >nul 2>&1
    if !errorlevel!==0 (
        echo   [OK] winget
        exit /b 0
    )
)

REM Method 2: Install via PowerShell (Windows 10 1709+)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ProgressPreference='SilentlyContinue'; try { Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Force -ErrorAction SilentlyContinue | Out-Null; Install-Module -Name Microsoft.WinGet.Client -Force -AllowClobber -ErrorAction Stop | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel!==0 (
    call :refresh_path
    where winget >nul 2>&1
    if !errorlevel!==0 (
        echo   [OK] winget
        exit /b 0
    )
)

REM Method 3: Download latest winget from GitHub releases
if "!LANG!"=="fr" (
    echo   Telechargement de winget depuis GitHub...
) else (
    echo   Downloading winget from GitHub...
)
set "WINGET_URL=https://aka.ms/getwinget"
set "WINGET_INSTALLER=%TEMP%\Microsoft.DesktopAppInstaller.msixbundle"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri '%WINGET_URL%' -OutFile '%WINGET_INSTALLER%' -UseBasicParsing -ErrorAction Stop; Add-AppxPackage -Path '%WINGET_INSTALLER%' -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel!==0 (
    del "%WINGET_INSTALLER%" >nul 2>&1
    call :refresh_path
    where winget >nul 2>&1
    if !errorlevel!==0 (
        echo   [OK] winget
        exit /b 0
    )
)
del "%WINGET_INSTALLER%" >nul 2>&1

REM Method 4: Open Microsoft Store as last resort
if "!LANG!"=="fr" (
    echo   [!] Installation automatique echouee.
    echo       Ouverture du Microsoft Store pour installer "Programme d'installation d'application"...
    echo       Installez-le, puis relancez run.bat.
) else (
    echo   [!] Automatic installation failed.
    echo       Opening Microsoft Store to install "App Installer"...
    echo       Install it, then rerun run.bat.
)
start "" "ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1"
pause
exit /b 1
