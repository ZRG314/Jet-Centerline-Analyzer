#!/usr/bin/env bash
# ============================================================
# Jet Centerline Analyzer — Linux build & installer script
#
# Creates:
#   dist/JetCenterlineAnalyzer/          — standalone app folder
#   dist/JetCenterlineAnalyzer-Linux.tar.gz — distributable archive
#
# Usage:
#   ./build_linux.sh              (uses python3 on PATH)
#   ./build_linux.sh /path/to/python3
#
# Requirements:
#   - Ubuntu 20.04+ / Fedora 36+ / similar
#   - Python 3.10+ with pip, venv, and tkinter
#   - System packages: python3-tk, python3-venv
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --------------- Python interpreter ---------------
if [[ -n "${1:-}" ]]; then
    PYTHON="$1"
elif [[ -f "venv/bin/python3" ]]; then
    PYTHON="venv/bin/python3"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    echo "Error: python3 not found. Install Python 3.10+ and try again." >&2
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv python3-tk" >&2
    echo "  Fedora:        sudo dnf install python3 python3-pip python3-tkinter" >&2
    exit 1
fi
echo "Using Python: $PYTHON ($($PYTHON --version 2>&1))"

# --------------- Check tkinter ---------------
if ! "$PYTHON" -c "import tkinter" 2>/dev/null; then
    echo "Error: tkinter is not installed for $PYTHON" >&2
    echo "  Ubuntu/Debian: sudo apt install python3-tk" >&2
    echo "  Fedora:        sudo dnf install python3-tkinter" >&2
    exit 1
fi

# --------------- Paths ---------------
DIST_DIR="$SCRIPT_DIR/dist"
BUILD_DIR="$SCRIPT_DIR/build/pyinstaller"
APP_NAME="JetCenterlineAnalyzer"
APP_DIR="$DIST_DIR/$APP_NAME"
TARBALL="$DIST_DIR/$APP_NAME-Linux.tar.gz"
VENV_DIR="$SCRIPT_DIR/venv"

# --------------- Step 1: Virtual environment ---------------
echo ""
echo "[1/5] Setting up virtual environment ..."
if [[ ! -d "$VENV_DIR" ]]; then
    "$PYTHON" -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
PYTHON="$VENV_DIR/bin/python3"

# --------------- Step 2: Dependencies ---------------
echo "[2/5] Installing dependencies ..."
"$PYTHON" -m pip install --upgrade pip -q
"$PYTHON" -m pip install -r requirements.txt -q

# --------------- Step 3: Clean previous build ---------------
echo "[3/5] Cleaning previous build output ..."
rm -rf "$DIST_DIR" "$BUILD_DIR"

# --------------- Step 4: PyInstaller build ---------------
echo "[4/5] Building $APP_NAME with PyInstaller ..."
"$PYTHON" -m PyInstaller \
    JetAnalyzer_crossplatform.spec \
    --noconfirm \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR"

if [[ ! -f "$APP_DIR/$APP_NAME" ]]; then
    echo "Error: PyInstaller did not produce $APP_DIR/$APP_NAME" >&2
    exit 1
fi

# Copy runtime data alongside the executable
mkdir -p "$APP_DIR/projects"
mkdir -p "$APP_DIR/Example Videos"
mkdir -p "$APP_DIR/Output Files"

if [[ -f "projects/sample_project.json" ]]; then
    cp "projects/sample_project.json" "$APP_DIR/projects/"
fi
if [[ -f "app_settings.json" ]]; then
    cp "app_settings.json" "$APP_DIR/"
fi
if [[ -f "Example Videos/example_input.mp4" ]]; then
    cp "Example Videos/example_input.mp4" "$APP_DIR/Example Videos/"
fi
if [[ -f "README.md" ]]; then
    cp "README.md" "$APP_DIR/"
fi

# Create a launcher script inside the dist folder
cat > "$APP_DIR/run.sh" << 'LAUNCHER'
#!/usr/bin/env bash
# Launch Jet Centerline Analyzer
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/JetCenterlineAnalyzer" "$@"
LAUNCHER
chmod +x "$APP_DIR/run.sh"

# Create a .desktop file for Linux desktop integration
cat > "$APP_DIR/$APP_NAME.desktop" << DESKTOP
[Desktop Entry]
Type=Application
Name=Jet Centerline Analyzer
Comment=Analyze jet centerline videos for wind tunnel experiments
Exec=$APP_NAME/JetCenterlineAnalyzer
Icon=$APP_NAME/icon.png
Terminal=false
Categories=Science;Education;
DESKTOP

# Copy icon for the .desktop file
if [[ -f "icon.png" ]]; then
    cp "icon.png" "$APP_DIR/"
fi

echo "  Built: $APP_DIR/"

# --------------- Step 5: Create distributable archive ---------------
echo "[5/5] Creating distributable archive ..."
rm -f "$TARBALL"
tar -czf "$TARBALL" -C "$DIST_DIR" "$APP_NAME"

echo ""
echo "============================================================"
echo "  Build complete!"
echo ""
echo "  App folder  : $APP_DIR/"
echo "  Archive     : $TARBALL"
echo ""
echo "  To run directly:"
echo "    $APP_DIR/run.sh"
echo ""
echo "  To install system-wide:"
echo "    sudo cp -r $APP_DIR /opt/$APP_NAME"
echo "    sudo cp $APP_DIR/$APP_NAME.desktop /usr/share/applications/"
echo "    # Edit Exec= and Icon= paths in the .desktop file to /opt/$APP_NAME/"
echo ""
echo "  To distribute:"
echo "    Share the .tar.gz file. Recipients extract and run:"
echo "      tar xzf $APP_NAME-Linux.tar.gz"
echo "      ./$APP_NAME/run.sh"
echo "============================================================"
