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
set SHORTCUT=%USERPROFILE%\Desktop\AUBIEETERNAL.bat

echo @echo off > "%SHORTCUT%"
echo title AUBIEETERNAL >> "%SHORTCUT%"
echo cd /d "%SCRIPT_DIR%" >> "%SHORTCUT%"
echo python launcher.py >> "%SHORTCUT%"
echo pause >> "%SHORTCUT%"

echo [OK] Desktop shortcut created: AUBIEETERNAL.bat

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
    echo [*] Pulling AI model (qwen2.5:7b - one time, ~4.7GB)...
    echo     This may take 5-15 minutes on first run.
    ollama pull qwen2.5:7b
    echo [OK] Model ready.
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
