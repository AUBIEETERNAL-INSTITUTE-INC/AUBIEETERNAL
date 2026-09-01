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

:: ── Program language ────────────────────────────────────────
:: Written to %USERPROFILE%\.aubieeternal\language - the single source of
:: truth read by both the Streamlit launcher and the voice assistant
:: (assistant_server.py). "en" and "es" ship today; the file is just a bare
:: language code so more can be added later without touching this script.
echo [*] Choose your language / Elige tu idioma:
echo   [1] English
echo   [2] Espanol
set LANG_CHOICE=
set /p LANG_CHOICE="  Choice / Eleccion (1/2) [1]: "
if not defined LANG_CHOICE set LANG_CHOICE=1
set APP_LANG=en
if "%LANG_CHOICE%"=="2" set APP_LANG=es
set CONFIG_DIR=%USERPROFILE%\.aubieeternal
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%" >nul 2>&1
> "%CONFIG_DIR%\language" echo %APP_LANG%
if exist "%CONFIG_DIR%\language" (
    echo [OK] Language set to "%APP_LANG%" ^(%CONFIG_DIR%\language^)
) else (
    echo [!] Could not write %CONFIG_DIR%\language - the app will default to English.
)
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python not found.

    :: winget is NOT guaranteed to exist - confirmed missing entirely on a
    :: real Windows 10 machine during testing, even though it's bundled on
    :: most Windows 11 installs. Download the official installer directly
    :: instead of depending on it, same approach as the Ollama install below.
    where winget >nul 2>&1
    if %errorlevel% equ 0 (
        echo [*] Installing Python via winget...
        winget install Python.Python.3.11 --silent
    ) else (
        echo [*] winget not found - downloading Python installer directly...
        set PYTHON_INSTALLER=%TEMP%\python-installer.exe
        curl -L -o "%PYTHON_INSTALLER%" https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe --silent --show-error
        if exist "%PYTHON_INSTALLER%" (
            echo [*] Installing Python silently...
            "%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
            del "%PYTHON_INSTALLER%" >nul 2>&1
            :: PrependPath=1 updates PATH for future sessions, but this cmd
            :: window won't see that until it restarts - add the known
            :: per-user 3.11 install location directly so the rest of this
            :: same script run (pip install, the shortcut it creates) can
            :: still find python without needing a fresh window.
            set "PATH=%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%LOCALAPPDATA%\Programs\Python\Python311;%PATH%"
        ) else (
            echo [!] Download failed.
        )
    )

    python --version >nul 2>&1
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
    echo [!] Ollama not found. Downloading installer - this is a large
    echo     file ^(~1.5GB^), it may take a few minutes...
    set OLLAMA_INSTALLER=%TEMP%\OllamaSetup.exe
    curl -L -o "%OLLAMA_INSTALLER%" https://ollama.com/download/OllamaSetup.exe --silent --show-error
    if exist "%OLLAMA_INSTALLER%" (
        echo [*] Installing Ollama silently...
        "%OLLAMA_INSTALLER%" /VERYSILENT /NORESTART
        del "%OLLAMA_INSTALLER%" >nul 2>&1
    ) else (
        echo [!] Download failed.
    )
    ollama --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo.
        echo ============================================================
        echo   Automatic Ollama install didn't complete.
        echo.
        echo   AUBIEETERNAL uses Ollama to run AI locally, for free.
        echo   Download it yourself from: https://ollama.ai/download
        echo.
        echo   After installing Ollama, double-click AUBIEETERNAL.bat
        echo   on your Desktop to launch.
        echo ============================================================
        echo.
        set /p OPEN_OLLAMA="Open Ollama download page now? (y/n): "
        if /i "%OPEN_OLLAMA%"=="y" start https://ollama.ai/download
    ) else (
        echo [OK] Ollama installed.
        call :PickAndPullModel
    )
) else (
    echo [OK] Ollama found.
    call :PickAndPullModel
)

goto :AfterOllamaSection

:PickAndPullModel
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

echo.
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
goto :eof

:AfterOllamaSection
echo.
echo ============================================================
echo   Installation complete!
echo.
echo   To launch AUBIEETERNAL (any of these work):
echo   - Double-click "AUBIEETERNAL.bat" on your Desktop
echo   - Or open a terminal here and run:  python launcher.py
echo     from this folder: %SCRIPT_DIR%
echo ============================================================
echo.
pause
