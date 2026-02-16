#!/bin/bash
# ============================================================================
#  AstroManager - Build Script (Linux / macOS)
#  Creates a standalone executable via PyInstaller.
#  Bilingual EN/FR auto-detection.
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# -- Detect system language (FR or EN)
LANG_CODE="en"
SYS_LANG="${LANG:-${LC_ALL:-${LC_MESSAGES:-en}}}"
case "$SYS_LANG" in
    fr*|FR*) LANG_CODE="fr" ;;
esac

msg() {
    if [ "$LANG_CODE" = "fr" ]; then echo "$1"; else echo "$2"; fi
}

echo
echo "  ============================================================"
msg "    AstroManager - Construction de l'executable" \
    "    AstroManager - Building Executable"
echo "  ============================================================"
echo

# -- Activate venv if it exists
PYTHON_CMD="python3"
if [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
    export PATH="$SCRIPT_DIR/venv/bin:$PATH"
    msg "  [OK] Environnement virtuel active" \
        "  [OK] Virtual environment activated"
elif [ -f "$SCRIPT_DIR/venv/Scripts/python.exe" ]; then
    PYTHON_CMD="$SCRIPT_DIR/venv/Scripts/python.exe"
    msg "  [OK] Environnement virtuel active (Windows)" \
        "  [OK] Virtual environment activated (Windows)"
fi

# -- Check PyInstaller
if ! "$PYTHON_CMD" -m PyInstaller --version >/dev/null 2>&1; then
    msg "  PyInstaller non trouve. Installation..." \
        "  PyInstaller not found. Installing..."
    "$PYTHON_CMD" -m pip install pyinstaller
fi

echo
msg "  Construction en cours..." \
    "  Building..."
echo

"$PYTHON_CMD" -m PyInstaller astromanager.spec --noconfirm

if [ $? -ne 0 ]; then
    echo
    msg "  [ERREUR] La construction a echoue ! Verifiez les erreurs ci-dessus." \
        "  [ERROR] Build failed! Check the errors above."
    exit 1
fi

echo
echo "  ============================================================"
msg "  CONSTRUCTION REUSSIE !" \
    "  BUILD SUCCESSFUL!"
msg "  Sortie : dist/AstroManager/" \
    "  Output: dist/AstroManager/"
echo "  ============================================================"
echo
