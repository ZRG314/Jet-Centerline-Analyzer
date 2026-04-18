# -*- mode: python ; coding: utf-8 -*-
"""Cross-platform PyInstaller spec for Jet Analyzer Program.

Build with:  pyinstaller JetAnalyzer_crossplatform.spec
Works on:    macOS, Linux, and Windows
"""

import os
import platform
from PyInstaller.utils.hooks import collect_data_files

ROOT = os.path.dirname(os.path.abspath(SPEC))
CODE_DIR = os.path.join(ROOT, "Code")
ICON_PATH = os.path.join(ROOT, "icon.ico")
CTK_DATAS = collect_data_files("customtkinter")

# --- Platform-specific settings ---
IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"

# Icon handling: .ico for Windows, .icns for macOS, None for Linux
icon_file = None
if IS_WINDOWS and os.path.isfile(ICON_PATH):
    icon_file = ICON_PATH
elif IS_MAC:
    icns_path = os.path.join(ROOT, "icon.icns")
    if os.path.isfile(icns_path):
        icon_file = icns_path

# Data files
datas = [
    (os.path.join(CODE_DIR, "app_documentation.md"), "."),
] + CTK_DATAS

# Include icons in the bundle (the app loads them at runtime)
if os.path.isfile(ICON_PATH):
    datas.append((ICON_PATH, "."))
_macos_icon_png = os.path.join(ROOT, "icon_macos.png")
if os.path.isfile(_macos_icon_png):
    datas.append((_macos_icon_png, "."))

# Hidden imports — shared across platforms
hiddenimports = [
    "customtkinter",
    "cv2",
    "numpy",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "tkinter",
    "tkinter.ttk",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "tkinter.colorchooser",
    "tkinter.simpledialog",
    "statistics",
    "csv",
    "threading",
    "copy",
    "json",
]

# Windows-only hidden imports
if IS_WINDOWS:
    hiddenimports += ["wmi", "winreg"]

a = Analysis(
    [os.path.join(CODE_DIR, "gui.py")],
    pathex=[CODE_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "scipy", "pandas", "IPython", "jupyter"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# On macOS, BUNDLE handles the directory structure, so we don't use
# contents_directory (which would create a nested folder that collides
# with the COLLECT name).  On Windows/Linux, keep the original layout.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="JetCenterlineAnalyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    icon=icon_file,
    console=False,
    disable_windowed_traceback=False,
    contents_directory="_internal" if IS_MAC else "JetCenterlineAnalyzer",
    argv_emulation=IS_MAC,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="JetCenterlineAnalyzer",
)

# --- macOS .app bundle (only generated on macOS) ---
if IS_MAC:
    app = BUNDLE(
        coll,
        name="JetCenterlineAnalyzer.app",
        icon=icon_file,
        bundle_identifier="com.jetanalyzer.app",
        info_plist={
            "CFBundleDisplayName": "Jet Centerline Analyzer",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "NSCameraUsageDescription": "This app uses the camera for live jet analysis.",
        },
    )
