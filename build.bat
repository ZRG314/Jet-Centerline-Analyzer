@echo off
setlocal

:: -------------------------------------------------------
:: Jet Analyzer Program - Windows build script
:: Run this file from any directory; it handles all paths.
:: Output: JetCenterlineAnalyzer.exe, support folders, and a release zip
:: -------------------------------------------------------

cd /d "%~dp0"
set "ROOT=%CD%"
set "EXE_PATH=%ROOT%\JetCenterlineAnalyzer.exe"
set "LEGACY_EXE_PATH=%ROOT%\JetAnalyzer.exe"
set "LEGACY_INTERNAL_DIR=%ROOT%\_internal"
set "SUPPORT_DIR=%ROOT%\JetCenterlineAnalyzer"
set "EXAMPLE_VIDEOS_DIR=%ROOT%\Example Videos"
set "EXAMPLE_VIDEO_FILE=%ROOT%\Example Videos\example_input.mp4"
set "PROJECTS_DIR=%ROOT%\projects"
set "STARTUP_PROJECT_FILE=%ROOT%\projects\sample_project.json"
set "DEFAULT_PROJECT_SETTINGS_FILE=%ROOT%\projects\app_defaults.json"
set "OUTPUT_DIR=%ROOT%\Output Files"
set "APP_SETTINGS_PATH=%ROOT%\app_settings.json"
set "PYI_WORK=%ROOT%\build\pyinstaller"
set "DIST_ROOT=%ROOT%\dist"
set "DIST_APP=%DIST_ROOT%\JetCenterlineAnalyzer"
set "DIST_SUPPORT=%DIST_APP%\JetCenterlineAnalyzer"
set "RELEASE_STAGE=%DIST_ROOT%\release_stage"
set "RELEASE_ZIP=%DIST_ROOT%\JetCenterlineAnalyzer-Windows.zip"

echo [1/6] Closing any running JetCenterlineAnalyzer instance...
taskkill /F /IM JetCenterlineAnalyzer.exe >nul 2>&1
taskkill /F /IM JetAnalyzer.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/6] Removing old build output...
if exist "%EXE_PATH%" del /q "%EXE_PATH%" >nul 2>&1
if exist "%LEGACY_EXE_PATH%" del /q "%LEGACY_EXE_PATH%" >nul 2>&1
if exist "%LEGACY_INTERNAL_DIR%" rd /s /q "%LEGACY_INTERNAL_DIR%" >nul 2>&1
if exist "%SUPPORT_DIR%" rd /s /q "%SUPPORT_DIR%" >nul 2>&1
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
    echo BUILD FAILED. Make sure JetCenterlineAnalyzer is closed and OneDrive has finished syncing, then try again.
    pause
    exit /b 1
)

echo [6/6] Copying runtime files next to the executable...
if not exist "%DIST_APP%\JetCenterlineAnalyzer.exe" (
    echo Build output was not found at "%DIST_APP%\JetCenterlineAnalyzer.exe".
    pause
    exit /b 1
)
if not exist "%DIST_SUPPORT%" (
    echo Build support folder was not found at "%DIST_SUPPORT%".
    pause
    exit /b 1
)

copy /Y "%DIST_APP%\JetCenterlineAnalyzer.exe" "%EXE_PATH%" >nul
if errorlevel 1 (
    echo Failed to copy JetCenterlineAnalyzer.exe to the project root.
    pause
    exit /b 1
)

xcopy /Y /I /E "%DIST_SUPPORT%\*" "%SUPPORT_DIR%\" >nul

if not exist "%ROOT%\app_settings.json" (
    copy "Code\app_settings.json" "%ROOT%\app_settings.json" >nul
    echo   Copied app_settings.json
)

echo [7/7] Creating release zip...
mkdir "%RELEASE_STAGE%" >nul 2>&1
mkdir "%RELEASE_STAGE%\Example Videos" >nul 2>&1
mkdir "%RELEASE_STAGE%\projects" >nul 2>&1
mkdir "%RELEASE_STAGE%\Output Files" >nul 2>&1

copy /Y "%EXE_PATH%" "%RELEASE_STAGE%\JetCenterlineAnalyzer.exe" >nul
xcopy /Y /I /E "%SUPPORT_DIR%\*" "%RELEASE_STAGE%\JetCenterlineAnalyzer\" >nul
copy /Y "%APP_SETTINGS_PATH%" "%RELEASE_STAGE%\app_settings.json" >nul
copy /Y "%EXAMPLE_VIDEO_FILE%" "%RELEASE_STAGE%\Example Videos\example_input.mp4" >nul
copy /Y "%STARTUP_PROJECT_FILE%" "%RELEASE_STAGE%\projects\sample_project.json" >nul
copy /Y "%DEFAULT_PROJECT_SETTINGS_FILE%" "%RELEASE_STAGE%\projects\app_defaults.json" >nul
xcopy /Y /I /E "%OUTPUT_DIR%\*" "%RELEASE_STAGE%\Output Files\" >nul

powershell -NoProfile -Command ^
  "Set-Location '%RELEASE_STAGE%'; Compress-Archive -Path * -DestinationPath '%RELEASE_ZIP%' -Force"
if errorlevel 1 (
    echo Failed to create release zip at "%RELEASE_ZIP%".
    pause
    exit /b 1
)

echo Done.
echo.
echo Output folder:  %ROOT%
echo Executable:     %EXE_PATH%
echo.
echo Runtime files next to the executable:
echo   JetCenterlineAnalyzer\
echo   Example Videos\example_input.mp4
echo   projects\sample_project.json
echo   projects\app_defaults.json
echo   Output Files\
echo   app_settings.json
echo.
echo Release zip:
echo   %RELEASE_ZIP%
echo.
echo App data is resolved relative to the current folder:
echo   projects\
echo   Example Videos\
echo   app_settings.json
echo.
pause
