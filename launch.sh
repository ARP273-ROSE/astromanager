#!/bin/bash
cd "$(dirname "$0")"

# === Find Python ===
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Python 3 not found. Please install Python 3.8+"
    exit 1
fi

# === Venv local to each PC (not in the synced NAS folder) ===
VENV_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/AstroManager/venv"

# === Check if venv exists and works ===
VENV_OK=0
if [ -x "$VENV_DIR/bin/python" ]; then
    "$VENV_DIR/bin/python" -c "print('ok')" &>/dev/null && VENV_OK=1
fi

if [ "$VENV_OK" = "0" ]; then
    if [ -d "$VENV_DIR" ]; then
        echo "Recreating virtual environment..."
        rm -rf "$VENV_DIR"
    fi
    echo "Creating virtual environment..."
    mkdir -p "$(dirname "$VENV_DIR")"
    $PYTHON -m venv "$VENV_DIR" || { echo "Failed to create venv"; exit 1; }
fi

# === Activate and install deps ===
source "$VENV_DIR/bin/activate"

MARKER="$VENV_DIR/.deps_installed"
if [ ! -f "$MARKER" ] || ! diff -q requirements.txt "$MARKER" &>/dev/null; then
    echo "Installing dependencies..."
    pip install -q -r requirements.txt
    cp requirements.txt "$MARKER"
fi

# === Launch ===
python astromanager.py "$@"
