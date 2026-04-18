# Jet Centerline Analyzer

Jet Centerline Analyzer is a desktop app created by Zach Gregory for Cedarville University's wind tunnels. It analyzes videos of a jet in crossflow, tracks the jet centerline over time, and lets users adjust a wide range of parameters to fit their experiment and desired output. The app exports annotated videos and CSV data files for further review and analysis.

## Quick Install (no build required)

| Platform | Download |
|----------|----------|
| Windows  | Run `JetCenterlineAnalyzer.exe` from the repo root |
| macOS    | Download the DMG from [Releases](https://github.com/ZRG314/Jet-Centerline-Analyzer/releases) |

## Running from Source (all platforms)

If you don't want to use a pre-built installer, you can run the app directly with Python on Windows, macOS, or Linux.

### Prerequisites

- Python 3.10 or later
- pip (comes with Python)
- tkinter (included with Python on Windows; may need separate install on macOS/Linux)

#### macOS (Homebrew)
```bash
brew install python@3.14 python-tk@3.14
```

#### Ubuntu / Debian
```bash
sudo apt install python3 python3-pip python3-venv python3-tk
```

#### Fedora
```bash
sudo dnf install python3 python3-pip python3-tkinter
```

#### Windows
Download Python from [python.org](https://www.python.org/downloads/). Make sure to check "Add Python to PATH" during installation. tkinter is included by default.

### Setup and Run

1. Clone the repository:
```bash
git clone https://github.com/ZRG314/Jet-Centerline-Analyzer.git
cd Jet-Centerline-Analyzer
```

2. Create a virtual environment and install dependencies:
```bash
python3 -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows (Command Prompt)
venv\Scripts\activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

3. Run the app:
```bash
python3 Code/gui.py
```

Or use the platform launcher scripts:
```bash
# macOS / Linux
./run_gui.sh

# Windows (PowerShell)
.\run_gui.ps1
```

The app will open with the example video loaded if it's present in the `Example Videos/` folder.

## Building Installers

If you want to package the app for distribution:

- **Windows**: Run `build.bat` — produces `JetCenterlineAnalyzer.exe`
- **macOS**: Run `./build_mac.sh` — produces a `.app` bundle and `.dmg` installer (see [BUILD_MACOS.md](BUILD_MACOS.md))
- **Linux**: Run `./build_linux.sh` — produces a standalone folder and `.tar.gz` archive (see [BUILD_LINUX.md](BUILD_LINUX.md))

Note: Installers must be built on the target platform. You cannot build a macOS installer on Windows or vice versa.
