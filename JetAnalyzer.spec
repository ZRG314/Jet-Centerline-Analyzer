# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Jet Analyzer Program.
Build with:  pyinstaller JetAnalyzer.spec
Output:      JetAnalyzer.exe and _internal\ in the app folder
"""

import os
from PyInstaller.utils.hooks import collect_data_files

ROOT = os.path.dirname(os.path.abspath(SPEC))
CODE_DIR = os.path.join(ROOT, "Code")
ICON_PATH = os.path.join(ROOT, "icon.ico")
CTK_DATAS = collect_data_files("customtkinter")

a = Analysis(
    [os.path.join(CODE_DIR, "gui.py")],
    pathex=[CODE_DIR],
    binaries=[],
    datas=[
        (os.path.join(CODE_DIR, "app_documentation.md"), "."),
        (ICON_PATH, "."),
    ] + CTK_DATAS,
    icon=ICON_PATH,
    hiddenimports=[
        "customtkinter",
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
    upx=False,
    icon=ICON_PATH,
    console=False,
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
    upx=False,
    upx_exclude=[],
    name="JetAnalyzer",
)
