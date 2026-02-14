#!/bin/bash
# ============================================================================
#  AstroManager - Linux/macOS Launcher
#  Auto-detects/installs: Python, LaTeX, virtual environment, pip dependencies
#  Then launches astromanager.py
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/venv"
PYTHON_CMD=""
LANG_CODE="en"

# -- Detect system language (FR or EN)
SYS_LANG="${LANG:-${LC_ALL:-${LC_MESSAGES:-en}}}"
case "$SYS_LANG" in
    fr*|FR*) LANG_CODE="fr" ;;
esac

msg() {
    if [ "$LANG_CODE" = "fr" ]; then echo "$1"; else echo "$2"; fi
}

OS="$(uname -s 2>/dev/null || echo unknown)"

# -- Detect package manager once
PKG_MGR=""
if [ "$OS" = "Linux" ]; then
    if command -v pacman >/dev/null 2>&1; then
        PKG_MGR="pacman"
    elif command -v apt >/dev/null 2>&1; then
        PKG_MGR="apt"
    elif command -v dnf >/dev/null 2>&1; then
        PKG_MGR="dnf"
    elif command -v zypper >/dev/null 2>&1; then
        PKG_MGR="zypper"
    fi
elif [ "$OS" = "Darwin" ]; then
    if command -v brew >/dev/null 2>&1; then
        PKG_MGR="brew"
    fi
fi

# Helper: install a system package automatically
pkg_install() {
    # $@ = package names
    case "$PKG_MGR" in
        pacman)  sudo pacman -S --needed --noconfirm "$@" ;;
        apt)     sudo apt-get update -qq && sudo apt-get install -y -qq "$@" ;;
        dnf)     sudo dnf install -y -q "$@" ;;
        zypper)  sudo zypper install -y "$@" ;;
        brew)    brew install "$@" ;;
        *)       return 1 ;;
    esac
}

echo
echo "  ============================================================"
echo "    AstroManager - Setup"
echo "  ============================================================"
echo

# ============================================================================
#  Step 1: Find or install Python 3.8+
# ============================================================================
find_python() {
    for cmd in python3 python; do
        if command -v "$cmd" >/dev/null 2>&1; then
            if "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
                PYTHON_CMD="$cmd"
                return 0
            fi
        fi
    done
    return 1
}

if ! find_python; then
    echo
    msg "  [X] Python 3.8+ n'est pas installe." \
        "  [X] Python 3.8+ is not installed."
    msg "      Installation automatique en cours..." \
        "      Installing automatically..."
    echo

    case "$PKG_MGR" in
        pacman)
            pkg_install python python-pip
            ;;
        apt)
            pkg_install python3 python3-pip python3-venv
            ;;
        dnf)
            pkg_install python3 python3-pip
            ;;
        zypper)
            pkg_install python3 python3-pip
            ;;
        brew)
            pkg_install python
            ;;
        *)
            msg "  [!] Aucun gestionnaire de paquets detecte." \
                "  [!] No package manager detected."
            ;;
    esac

    # Refresh shell hash table
    hash -r 2>/dev/null

    if find_python; then
        msg "  [OK] Python installe" "  [OK] Python installed"
    else
        echo
        msg "  [!] Impossible d'installer Python automatiquement." \
            "  [!] Cannot install Python automatically."
        msg "      Installez Python 3.8+ manuellement puis relancez ./run.sh" \
            "      Install Python 3.8+ manually then rerun ./run.sh"
        echo
        case "$OS" in
            Darwin)
                echo "    https://www.python.org/downloads/macos/"
                echo "    brew install python" ;;
            Linux)
                echo "    Arch/Manjaro : sudo pacman -S python"
                echo "    Debian/Ubuntu: sudo apt install python3 python3-pip python3-venv"
                echo "    Fedora       : sudo dnf install python3 python3-pip" ;;
            *)
                echo "    https://www.python.org/downloads/" ;;
        esac
        exit 1
    fi
fi

PY_VER=$($PYTHON_CMD --version 2>&1)
echo "  [OK] $PY_VER"

# ============================================================================
#  Step 2: Virtual environment
# ============================================================================
if [ -f "$VENV_DIR/bin/python" ]; then
    msg "  [OK] Environnement virtuel existant" \
        "  [OK] Existing virtual environment"
else
    msg "  Creation de l'environnement virtuel..." \
        "  Creating virtual environment..."

    if ! $PYTHON_CMD -m venv "$VENV_DIR" 2>/dev/null; then
        # On Debian/Ubuntu, python3-venv is a separate package
        if [ "$PKG_MGR" = "apt" ]; then
            msg "  Installation de python3-venv..." \
                "  Installing python3-venv..."
            pkg_install python3-venv
            $PYTHON_CMD -m venv "$VENV_DIR" 2>/dev/null
        fi
    fi

    if [ ! -f "$VENV_DIR/bin/python" ]; then
        msg "  [!] Impossible de creer le venv, utilisation de Python global" \
            "  [!] Cannot create venv, using global Python"
    fi
fi

if [ -f "$VENV_DIR/bin/python" ]; then
    PYTHON_CMD="$VENV_DIR/bin/python"
    export PATH="$VENV_DIR/bin:$PATH"
    msg "  [OK] Environnement virtuel active" \
        "  [OK] Virtual environment activated"

    # Upgrade pip quietly
    "$PYTHON_CMD" -m pip install --upgrade pip --quiet 2>/dev/null || true
fi

# Install dependencies from requirements.txt
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    msg "  Installation des dependances Python (peut prendre quelques minutes)..." \
        "  Installing Python dependencies (may take a few minutes)..."
    if "$PYTHON_CMD" -m pip install -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null; then
        msg "  [OK] Dependances Python installees" \
            "  [OK] Python dependencies installed"
    else
        msg "  [!] Certaines dependances ont echoue (le programme reessaiera au demarrage)" \
            "  [!] Some dependencies failed (the program will retry at startup)"
    fi
fi

# ============================================================================
#  Step 3: LaTeX (optional, for PDF reports)
# ============================================================================
if command -v pdflatex >/dev/null 2>&1; then
    echo "  [OK] LaTeX (pdflatex)"
else
    echo
    msg "  [?] LaTeX (pdflatex) n'est pas installe." \
        "  [?] LaTeX (pdflatex) is not installed."
    msg "      Il est necessaire pour generer les rapports PDF complets." \
        "      It is needed to generate full PDF reports."
    msg "      Le programme fonctionnera sans, avec des rapports PDF simplifies." \
        "      The program will work without it, with simplified PDF reports."
    echo

    LATEX_PKGS=""
    case "$PKG_MGR" in
        pacman)
            LATEX_PKGS="texlive-basic texlive-latexextra texlive-fontsrecommended"
            ;;
        apt)
            LATEX_PKGS="texlive-latex-base texlive-latex-extra texlive-fonts-recommended"
            ;;
        dnf)
            LATEX_PKGS="texlive-scheme-basic texlive-collection-latexextra"
            ;;
        brew)
            LATEX_PKGS="--cask basictex"
            ;;
    esac

    if [ -n "$LATEX_PKGS" ]; then
        if [ "$LANG_CODE" = "fr" ]; then
            read -r -p "  Installer LaTeX automatiquement ? [O/N] " REPLY
        else
            read -r -p "  Install LaTeX automatically? [Y/N] " REPLY
        fi

        if [[ "$REPLY" =~ ^[YyOo]$ ]]; then
            msg "  Installation de LaTeX..." \
                "  Installing LaTeX..."
            # shellcheck disable=SC2086
            pkg_install $LATEX_PKGS
            hash -r 2>/dev/null

            if command -v pdflatex >/dev/null 2>&1; then
                msg "  [OK] LaTeX installe" "  [OK] LaTeX installed"
            else
                msg "  [!] LaTeX installe mais pdflatex pas dans le PATH." \
                    "  [!] LaTeX installed but pdflatex not in PATH."
                msg "      Redemarrez le terminal si necessaire." \
                    "      Restart the terminal if needed."
            fi
        fi
    else
        msg "  Pour installer manuellement :" \
            "  To install manually:"
        echo "    Arch/Manjaro : sudo pacman -S texlive-basic texlive-latexextra"
        echo "    Debian/Ubuntu: sudo apt install texlive-latex-base texlive-latex-extra"
        echo "    Fedora       : sudo dnf install texlive-scheme-basic"
        echo "    macOS        : brew install --cask basictex"
    fi
    echo
fi

# ============================================================================
#  Step 4: Launch AstroManager
# ============================================================================
echo
echo "  ============================================================"
msg "    AstroManager - Demarrage..." \
    "    AstroManager - Starting..."
echo "  ============================================================"
echo

exec "$PYTHON_CMD" "$SCRIPT_DIR/astromanager.py" "$@"
