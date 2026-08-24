@echo off
title AUBIEETERNAL Installer
color 0A

echo.
echo ============================================================
echo   *** AUBIEETERNAL - Windows Installer ***
echo   Sovereign Family Intelligence
echo   CC0 Public Domain - War Eagle Eternal
echo ============================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python not found. Installing via winget...
    winget install Python.Python.3.11 --silent
    if %errorlevel% neq 0 (
        echo [!] Auto-install failed. Please install Python from:
        echo     https://python.org/downloads
        echo     Make sure to check "Add Python to PATH"
        pause
        exit /b 1
    )
    echo [OK] Python installed.
) else (
    echo [OK] Python found.
)

:: Create Desktop shortcut
echo.
echo [*] Creating desktop shortcut...
set SCRIPT_DIR=%~dp0

:: %USERPROFILE%\Desktop is wrong on any machine where OneDrive has moved
:: Desktop into OneDrive (Known Folder Move) - that plain path may not even
:: exist there, so the shortcut write silently fails with no error the user
:: would notice. Ask Windows for the real, current Desktop path instead.
set DESKTOP_DIR=
for /f "usebackq tokens=*" %%A in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')" 2^>nul`) do set DESKTOP_DIR=%%A
if not defined DESKTOP_DIR set DESKTOP_DIR=%USERPROFILE%\Desktop
set SHORTCUT=%DESKTOP_DIR%\AUBIEETERNAL.bat

echo @echo off > "%SHORTCUT%"
echo title AUBIEETERNAL >> "%SHORTCUT%"
echo cd /d "%SCRIPT_DIR%" >> "%SHORTCUT%"
echo python launcher.py >> "%SHORTCUT%"
echo pause >> "%SHORTCUT%"

if exist "%SHORTCUT%" (
    echo [OK] Desktop shortcut created: %SHORTCUT%
) else (
    echo [!] Could not create the desktop shortcut at %SHORTCUT%
    echo     You can still launch AUBIEETERNAL by running: python launcher.py
    echo     from this folder: %SCRIPT_DIR%
)

:: Install Python packages now
echo.
echo [*] Installing Python packages (first time only)...
python -m pip install streamlit requests openai pandas plotly python-dateutil pytz --quiet --disable-pip-version-check
echo [OK] Packages installed.

:: Check for Ollama
echo.
echo [*] Checking for Ollama...
ollama --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ============================================================
    echo   Ollama (local AI engine) is not installed.
    echo.
    echo   AUBIEETERNAL uses Ollama to run AI locally, for free.
    echo   Download it from: https://ollama.ai/download
    echo.
    echo   After installing Ollama, double-click AUBIEETERNAL.bat
    echo   on your Desktop to launch.
    echo ============================================================
    echo.
    set /p OPEN_OLLAMA="Open Ollama download page now? (y/n): "
    if /i "%OPEN_OLLAMA%"=="y" start https://ollama.ai/download
) else (
    echo [OK] Ollama found.
    echo.

    :: Detect RAM to recommend a model tier - a stronger machine should
    :: default to a bigger model, not always the smallest one.
    set RAM_GB=
    for /f "usebackq tokens=*" %%A in (`powershell -NoProfile -Command "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)" 2^>nul`) do set RAM_GB=%%A

    set RECOMMENDED=1
    if defined RAM_GB (
        if %RAM_GB% GEQ 28 (
            set RECOMMENDED=3
        ) else if %RAM_GB% GEQ 16 (
            set RECOMMENDED=2
        )
    )

    echo   Choose AI model:
    if defined RAM_GB echo   ^(detected ~%RAM_GB%GB RAM^)
    echo   [1] qwen2.5:7b  - Fast, works on 8GB RAM    ^(4.7GB download^)
    echo   [2] qwen2.5:14b - Best, needs 16GB RAM       ^(9.0GB download^)
    echo   [3] qwen2.5:32b - Strongest, needs 28GB+ RAM ^(18GB download^)
    echo   [4] Skip
    set MODEL_CHOICE=
    set /p MODEL_CHOICE="  Choice (1/2/3/4) [recommended: %RECOMMENDED%]: "
    if not defined MODEL_CHOICE set MODEL_CHOICE=%RECOMMENDED%

    set MODEL=qwen2.5:7b
    if "%MODEL_CHOICE%"=="2" set MODEL=qwen2.5:14b
    if "%MODEL_CHOICE%"=="3" set MODEL=qwen2.5:32b
    if "%MODEL_CHOICE%"=="4" set MODEL=

    if defined MODEL (
        echo.
        echo [*] Pulling %MODEL% - this may take a few minutes...
        ollama pull %MODEL%
        echo [OK] Model ready.
    ) else (
        echo [*] Skipped model download.
    )
)

echo.
echo ============================================================
echo   Installation complete!
echo.
echo   To launch AUBIEETERNAL:
echo   - Double-click "AUBIEETERNAL.bat" on your Desktop
echo   - Or run: python launcher.py
echo ============================================================
echo.
pause
