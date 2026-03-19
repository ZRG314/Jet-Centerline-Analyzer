# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Jet Analyzer Program.
Build with:  pyinstaller JetAnalyzer.spec
Output:      dist\JetAnalyzer\JetAnalyzer.exe
"""

import os

ROOT = os.path.dirname(os.path.abspath(SPEC))
CODE_DIR = os.path.join(ROOT, "Code")
PROJECTS_DIR = os.path.join(ROOT, "projects")
ICON_PATH = os.path.join(ROOT, "icon.ico")

a = Analysis(
    [os.path.join(CODE_DIR, "gui.py")],
    pathex=[CODE_DIR],
    binaries=[],
    datas=[
        # Bundle the documentation file as a read-only resource inside _internal/
        (os.path.join(CODE_DIR, "app_documentation.md"), "."),
        # Bundle the icon so the app window can reference it at runtime
        (ICON_PATH, "."),
    ],
    icon=ICON_PATH,
    hiddenimports=[
        "cv2",
        "numpy",
        "PIL",
        "PIL.Image",
        "PIL.ImageTk",
        "wmi",
        "winreg",
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
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "scipy", "pandas", "IPython", "jupyter"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="JetAnalyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    icon=ICON_PATH,
    console=False,           # No console window — GUI-only app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="JetAnalyzer",
)
