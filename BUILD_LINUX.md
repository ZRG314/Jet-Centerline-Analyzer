# Building Jet Centerline Analyzer for Linux

This guide covers packaging the app as a standalone executable on Linux. The result is a `.tar.gz` archive that anyone can extract and run — no Python required on the target machine.

## Prerequisites

### Ubuntu / Debian
```bash
sudo apt install python3 python3-pip python3-venv python3-tk
```

### Fedora
```bash
sudo dnf install python3 python3-pip python3-tkinter
```

### Arch Linux
```bash
sudo pacman -S python python-pip tk
```

## Quick Start

```bash
chmod +x build_linux.sh
./build_linux.sh
```

This produces:
- `dist/JetCenterlineAnalyzer/` — standalone app folder with all dependencies
- `dist/JetCenterlineAnalyzer-Linux.tar.gz` — distributable archive

## Running the App

```bash
./dist/JetCenterlineAnalyzer/run.sh
```

Or directly:
```bash
./dist/JetCenterlineAnalyzer/JetCenterlineAnalyzer
```

## Installing System-Wide

```bash
sudo cp -r dist/JetCenterlineAnalyzer /opt/JetCenterlineAnalyzer

# Create a desktop entry
sudo cp dist/JetCenterlineAnalyzer/JetCenterlineAnalyzer.desktop /usr/share/applications/

# Edit the .desktop file to use absolute paths
sudo sed -i 's|Exec=.*|Exec=/opt/JetCenterlineAnalyzer/JetCenterlineAnalyzer|' \
    /usr/share/applications/JetCenterlineAnalyzer.desktop
sudo sed -i 's|Icon=.*|Icon=/opt/JetCenterlineAnalyzer/icon.png|' \
    /usr/share/applications/JetCenterlineAnalyzer.desktop
```

The app will then appear in your desktop environment's application menu.

## Running from Source

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 Code/gui.py
```

Or use the launcher: `./run_gui.sh`

## Distributing

Share the `.tar.gz` file. Recipients install with:

```bash
tar xzf JetCenterlineAnalyzer-Linux.tar.gz
./JetCenterlineAnalyzer/run.sh
```

No Python installation needed — everything is bundled.

## User Data

On Linux, the app stores user data in `~/JetCenterlineAnalyzer/`:
- `Input Videos/` — default location for input video files
- `Output Files/` — default location for analysis output

## Troubleshooting

### `No module named '_tkinter'`
Install the tkinter package for your distro:
```bash
# Ubuntu/Debian
sudo apt install python3-tk

# Fedora
sudo dnf install python3-tkinter
```
Then delete `venv/` and rerun `build_linux.sh`.

### App won't launch — missing shared libraries
Check what's missing:
```bash
ldd dist/JetCenterlineAnalyzer/JetCenterlineAnalyzer | grep "not found"
```
Common fixes:
```bash
# Ubuntu/Debian
sudo apt install libgl1-mesa-glx libglib2.0-0 libxcb-xinerama0

# Fedora
sudo dnf install mesa-libGL glib2
```

### No display / X11 error
The app requires a graphical display. If running over SSH, use X forwarding:
```bash
ssh -X user@host
./JetCenterlineAnalyzer/run.sh
```

### `.desktop` file not showing in app menu
```bash
update-desktop-database ~/.local/share/applications/
```
