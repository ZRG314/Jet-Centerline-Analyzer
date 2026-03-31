@echo off
setlocal

:: -------------------------------------------------------
:: Jet Analyzer Program - Windows build script
:: Run this file from any directory; it handles all paths.
:: Output: JetAnalyzer.exe and _internal\ in the project root
:: -------------------------------------------------------

cd /d "%~dp0"
set "ROOT=%CD%"
set "EXE_PATH=%ROOT%\JetAnalyzer.exe"
set "INTERNAL_DIR=%ROOT%\_internal"
set "PYI_WORK=%ROOT%\build\pyinstaller"
set "DIST_ROOT=%ROOT%\dist"
set "DIST_APP=%DIST_ROOT%\JetAnalyzer"

echo [1/6] Closing any running JetAnalyzer instance...
taskkill /F /IM JetAnalyzer.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/6] Removing old build output...
if exist "%EXE_PATH%" del /q "%EXE_PATH%" >nul 2>&1
if exist "%INTERNAL_DIR%" rd /s /q "%INTERNAL_DIR%" >nul 2>&1
if exist "%PYI_WORK%" rd /s /q "%PYI_WORK%" >nul 2>&1
if exist "%DIST_ROOT%" rd /s /q "%DIST_ROOT%" >nul 2>&1
timeout /t 1 /nobreak >nul

echo [3/6] Installing build dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency install failed.
    pause
    exit /b 1
)

echo [4/6] Checking PyInstaller...
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    python -m pip install pyinstaller
)

echo [5/6] Building executable...
python -m PyInstaller JetAnalyzer.spec --noconfirm --distpath "%DIST_ROOT%" --workpath "%PYI_WORK%"
if errorlevel 1 (
    echo BUILD FAILED. Make sure JetAnalyzer is closed and OneDrive has finished syncing, then try again.
    pause
    exit /b 1
)

echo [6/6] Copying runtime files next to the executable...
if not exist "%DIST_APP%\JetAnalyzer.exe" (
    echo Build output was not found at "%DIST_APP%\JetAnalyzer.exe".
    pause
    exit /b 1
)

copy /Y "%DIST_APP%\JetAnalyzer.exe" "%EXE_PATH%" >nul
if errorlevel 1 (
    echo Failed to copy JetAnalyzer.exe to the project root.
    pause
    exit /b 1
)

if exist "%DIST_APP%\_internal" (
    xcopy /Y /I /E "%DIST_APP%\_internal\*" "%INTERNAL_DIR%\" >nul
)

if not exist "%ROOT%\app_settings.json" (
    copy "Code\app_settings.json" "%ROOT%\app_settings.json" >nul
    echo   Copied app_settings.json
)

echo Done.
echo.
echo Output folder:  %ROOT%
echo Executable:     %EXE_PATH%
echo.
echo Runtime files next to the executable:
echo   _internal\
echo.
echo App data is resolved relative to the current folder:
echo   projects\
echo   Example Videos\
echo   app_settings.json
echo.
pause
