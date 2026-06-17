# Building Jet Centerline Analyzer for macOS

This guide walks through packaging the app as a standalone `.app` bundle and `.dmg` installer on macOS. The end result is a distributable disk image that anyone can install by dragging to Applications — no Python required on the target machine.

## Prerequisites

- macOS 11 (Big Sur) or later
- Python 3.10+ (Homebrew recommended: `brew install python@3.14`)
- Xcode Command Line Tools (`xcode-select --install`)
- Tkinter support for your Python version (`brew install python-tk@3.14`)

## Quick Start

From the project root:

```bash
chmod +x build_mac.sh
./build_mac.sh
```

That's it. The script handles everything and produces:

- `dist/JetCenterlineAnalyzer.app` — the standalone app bundle
- `dist/JetCenterlineAnalyzer-macOS.dmg` — the distributable installer

## What the Build Script Does

The `build_mac.sh` script runs six steps:

1. Creates (or reuses) a Python virtual environment in `venv/`
2. Installs all dependencies from `requirements.txt`
3. Generates `icon.icns` from `icon.png` using macOS `sips` and `iconutil`
4. Cleans any previous build output
5. Runs PyInstaller with `JetAnalyzer_crossplatform.spec` to produce the `.app` bundle
6. Wraps the `.app` in a `.dmg` disk image with an Applications shortcut

## Installing the App

### From the DMG (recommended for distribution)

1. Double-click `JetCenterlineAnalyzer-macOS.dmg`
2. Drag `JetCenterlineAnalyzer` onto the `Applications` shortcut
3. Eject the DMG
4. On first launch: right-click the app in Applications, choose "Open", then confirm (this is required because the app is not notarized with Apple)

### From the terminal

```bash
cp -R dist/JetCenterlineAnalyzer.app /Applications/
```

## Running from Source (without packaging)

If you just want to run the app during development:

```bash
# One-time setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run
python3 Code/gui.py
```

Or use the launcher script:

```bash
./run_gui.sh
```

## Key Files

| File | Purpose |
|------|---------|
| `build_mac.sh` | Automated build script (venv, deps, icon, PyInstaller, DMG) |
| `JetAnalyzer_crossplatform.spec` | PyInstaller spec with macOS/Linux/Windows support |
| `requirements.txt` | Python dependencies (WMI is skipped on non-Windows) |
| `run_gui.sh` | Launcher script for running from source |
| `icon.png` | Source icon (converted to `.icns` during build) |

## Customizing the Build

### App metadata

Edit the `info_plist` dict in `JetAnalyzer_crossplatform.spec`:

```python
info_plist={
    "CFBundleDisplayName": "Jet Centerline Analyzer",
    "CFBundleShortVersionString": "1.0.0",
    "NSHighResolutionCapable": True,
    "NSCameraUsageDescription": "This app uses the camera for live jet analysis.",
},
```

- `CFBundleShortVersionString` — version shown in Finder's Get Info
- `NSCameraUsageDescription` — required if using the live camera feature; macOS silently denies camera access without it

### App icon

Replace `icon.png` with your own (ideally 1024x1024). The build script auto-generates all required sizes and creates `icon.icns`. If you already have an `.icns` file, place it at the project root as `icon.icns` and the script will skip generation.

### Bundle identifier

Change `bundle_identifier` in the spec file if distributing officially:

```python
bundle_identifier="com.yourorg.jetanalyzer",
```

## Code Signing and Notarization

The built app is ad-hoc signed by PyInstaller, which is fine for local use. For distribution to other Macs:

### Ad-hoc (current default)
- Recipients must right-click > Open on first launch
- No Apple Developer account needed

### Developer ID signing
If you have an Apple Developer account ($99/year):

```bash
codesign --deep --force --sign "Developer ID Application: Your Name (TEAMID)" \
    dist/JetCenterlineAnalyzer.app
```

### Notarization (removes all Gatekeeper warnings)

```bash
# Create a zip for notarization
ditto -c -k --keepParent dist/JetCenterlineAnalyzer.app JetCenterlineAnalyzer.zip

# Submit
xcrun notarytool submit JetCenterlineAnalyzer.zip \
    --apple-id "your@email.com" \
    --team-id "TEAMID" \
    --password "app-specific-password" \
    --wait

# Staple the ticket to the app
xcrun stapler staple dist/JetCenterlineAnalyzer.app
```

After stapling, rebuild the DMG so it contains the notarized app.

## Troubleshooting

### `No module named '_tkinter'`
Install tkinter for your Python version:
```bash
brew install python-tk@3.14
```
Then recreate the venv (`rm -rf venv` and rerun `build_mac.sh`).

### App crashes on launch with no error
Check the system log:
```bash
log show --predicate 'process == "JetCenterlineAnalyzer"' --last 5m
```

### "App is damaged and can't be opened"
This happens when macOS quarantines unsigned apps downloaded from the internet. Fix with:
```bash
xattr -cr /Applications/JetCenterlineAnalyzer.app
```

### Camera not working
Make sure `NSCameraUsageDescription` is set in the spec's `info_plist`. If the app was previously denied camera access, reset permissions:
```bash
tccutil reset Camera com.jetanalyzer.app
```
