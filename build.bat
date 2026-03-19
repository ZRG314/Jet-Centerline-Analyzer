@echo off
setlocal

:: -------------------------------------------------------
:: Jet Analyzer Program — Windows build script
:: Run this file from any directory; it handles all paths.
:: Output: dist\JetAnalyzer\JetAnalyzer.exe
:: -------------------------------------------------------

cd /d "%~dp0"

echo [1/5] Closing any running JetAnalyzer instance...
taskkill /F /IM JetAnalyzer.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/5] Removing old dist folder...
if exist "dist\JetAnalyzer" (
    rd /s /q "dist\JetAnalyzer" >nul 2>&1
    timeout /t 2 /nobreak >nul
)

echo [3/5] Checking PyInstaller...
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

echo [4/5] Building executable...
python -m PyInstaller JetAnalyzer.spec --noconfirm
if errorlevel 1 (
    echo BUILD FAILED. Make sure JetAnalyzer is closed and OneDrive has finished syncing, then try again.
    pause
    exit /b 1
)

echo [5/5] Copying writable data files next to executable...

:: app_settings.json lives next to the exe so it can be written by the app
if not exist "dist\JetAnalyzer\app_settings.json" (
    copy "Code\app_settings.json" "dist\JetAnalyzer\app_settings.json"
    echo   Copied app_settings.json
)

:: Copy the projects folder so sample projects are available on first launch
if not exist "dist\JetAnalyzer\projects" mkdir "dist\JetAnalyzer\projects"
xcopy /Y /I "projects\*" "dist\JetAnalyzer\projects\" >nul
echo   Copied projects\

:: Copy example videos so relative sample-project paths work on other computers
if exist "Example Videos" (
    if not exist "dist\JetAnalyzer\Example Videos" mkdir "dist\JetAnalyzer\Example Videos"
    xcopy /Y /I /E "Example Videos\*" "dist\JetAnalyzer\Example Videos\" >nul
    echo   Copied Example Videos\
)

echo [4/4] Done.
echo.
echo Output folder:  dist\JetAnalyzer\
echo Executable:     dist\JetAnalyzer\JetAnalyzer.exe
echo.
echo To distribute: zip the entire dist\JetAnalyzer\ folder
echo and extract it on any Windows machine — no Python required.
echo.
pause
