#!/usr/bin/env bash
# ============================================================
# Jet Centerline Analyzer — macOS build & installer script
#
# Creates:
#   dist/JetCenterlineAnalyzer.app    — standalone .app bundle
#   dist/JetCenterlineAnalyzer.dmg    — distributable disk image
#
# Usage:
#   ./build_mac.sh              (uses python3 on PATH)
#   ./build_mac.sh /path/to/python3
#
# Requirements:
#   - macOS 11+ (Big Sur or later)
#   - Python 3.10+ with pip and venv
#   - Xcode Command Line Tools (for hdiutil / codesign)
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
    echo "Error: python3 not found. Pass the path as an argument or install Python 3.10+." >&2
    exit 1
fi
echo "Using Python: $PYTHON ($($PYTHON --version 2>&1))"

# --------------- Paths ---------------
DIST_DIR="$SCRIPT_DIR/dist"
BUILD_DIR="$SCRIPT_DIR/build/pyinstaller"
APP_NAME="JetCenterlineAnalyzer"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
DMG_PATH="$DIST_DIR/$APP_NAME-macOS.dmg"
DMG_STAGE="$DIST_DIR/dmg_stage"
VENV_DIR="$SCRIPT_DIR/venv"

# --------------- Step 1: Virtual environment ---------------
echo ""
echo "[1/6] Setting up virtual environment ..."
if [[ ! -d "$VENV_DIR" ]]; then
    "$PYTHON" -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
PYTHON="$VENV_DIR/bin/python3"

# --------------- Step 2: Dependencies ---------------
echo "[2/6] Installing dependencies ..."
"$PYTHON" -m pip install --upgrade pip -q
"$PYTHON" -m pip install -r requirements.txt -q

# --------------- Step 3: Generate .icns icon ---------------
echo "[3/6] Generating macOS icon ..."
ICON_ICNS="$SCRIPT_DIR/icon.icns"
if [[ ! -f "$ICON_ICNS" ]]; then
    if [[ -f "$SCRIPT_DIR/icon.png" ]]; then
        ICONSET_DIR="$SCRIPT_DIR/build/icon.iconset"
        mkdir -p "$ICONSET_DIR"
        # Generate all required icon sizes from the source PNG
        for SIZE in 16 32 64 128 256 512; do
            sips -z $SIZE $SIZE "$SCRIPT_DIR/icon.png" --out "$ICONSET_DIR/icon_${SIZE}x${SIZE}.png" >/dev/null 2>&1
        done
        for SIZE in 32 64 128 256 512 1024; do
            HALF=$((SIZE / 2))
            sips -z $SIZE $SIZE "$SCRIPT_DIR/icon.png" --out "$ICONSET_DIR/icon_${HALF}x${HALF}@2x.png" >/dev/null 2>&1
        done
        iconutil -c icns "$ICONSET_DIR" -o "$ICON_ICNS" 2>/dev/null || true
        echo "  Created icon.icns from icon.png"
    else
        echo "  Warning: No icon.png found — app will use default icon."
    fi
fi

# --------------- Step 4: Clean previous build ---------------
echo "[4/6] Cleaning previous build output ..."
rm -rf "$DIST_DIR" "$BUILD_DIR"

# --------------- Step 5: PyInstaller build ---------------
echo "[5/6] Building $APP_NAME.app with PyInstaller ..."
"$PYTHON" -m PyInstaller \
    JetAnalyzer_crossplatform.spec \
    --noconfirm \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR"

if [[ ! -d "$APP_BUNDLE" ]]; then
    echo "Error: PyInstaller did not produce $APP_BUNDLE" >&2
    echo "Check the build output above for errors." >&2
    exit 1
fi

# Copy runtime data into the .app bundle's Resources
RESOURCES_DIR="$APP_BUNDLE/Contents/Resources"
mkdir -p "$RESOURCES_DIR/projects"
mkdir -p "$RESOURCES_DIR/Example Videos"
mkdir -p "$RESOURCES_DIR/Output Files"

if [[ -f "projects/sample_project.json" ]]; then
    cp "projects/sample_project.json" "$RESOURCES_DIR/projects/"
fi
if [[ -f "app_settings.json" ]]; then
    cp "app_settings.json" "$RESOURCES_DIR/"
fi
# Copy example video if it exists
if [[ -f "Example Videos/example_input.mp4" ]]; then
    cp "Example Videos/example_input.mp4" "$RESOURCES_DIR/Example Videos/"
fi

echo "  Built: $APP_BUNDLE"

# --------------- Step 6: Create DMG installer ---------------
echo "[6/6] Creating DMG installer ..."
rm -rf "$DMG_STAGE"
mkdir -p "$DMG_STAGE"

# Copy the .app into the staging area
cp -R "$APP_BUNDLE" "$DMG_STAGE/"

# Create a symlink to /Applications for drag-to-install
ln -s /Applications "$DMG_STAGE/Applications"

# Copy supporting files alongside the .app in the DMG
if [[ -f "README.md" ]]; then
    cp "README.md" "$DMG_STAGE/"
fi

# Create the DMG
rm -f "$DMG_PATH"
hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$DMG_STAGE" \
    -ov \
    -format UDZO \
    "$DMG_PATH" >/dev/null

rm -rf "$DMG_STAGE"

echo ""
echo "============================================================"
echo "  Build complete!"
echo ""
echo "  App bundle : $APP_BUNDLE"
echo "  DMG installer : $DMG_PATH"
echo ""
echo "  To install:"
echo "    1. Open $APP_NAME-macOS.dmg"
echo "    2. Drag $APP_NAME to Applications"
echo "    3. Right-click > Open on first launch (Gatekeeper)"
echo ""
echo "  To distribute:"
echo "    Share the .dmg file. Recipients drag the app"
echo "    to their Applications folder — no Python needed."
echo "============================================================"
