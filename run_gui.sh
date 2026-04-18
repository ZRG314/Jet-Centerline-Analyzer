#!/usr/bin/env bash
# Launch JetCenterlineAnalyzer from source on macOS / Linux.
# Usage:  ./run_gui.sh
#         ./run_gui.sh /path/to/python3

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE_DIR="$SCRIPT_DIR/Code"

# Use the Python passed as $1, or fall back to python3 / python on PATH.
if [[ -n "${1:-}" ]]; then
    PYTHON="$1"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PYTHON="python"
else
    echo "Error: No Python interpreter found. Install Python 3.10+ and try again." >&2
    exit 1
fi

echo "Using Python: $PYTHON ($($PYTHON --version 2>&1))"

# Ensure dependencies are installed
if ! "$PYTHON" -c "import cv2, numpy, customtkinter" 2>/dev/null; then
    echo "Installing dependencies from requirements.txt ..."
    "$PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt"
fi

echo "Launching Jet Centerline Analyzer ..."
exec "$PYTHON" "$CODE_DIR/gui.py"
