@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title AUBIEETERNAL Installer
color 0A

echo.
echo ============================================================
echo   AUBIEETERNAL - Windows Installer
echo   Installs Python, Ollama, and a local AI model, then starts.
echo ============================================================
echo.

echo Choose language / Elige idioma:
echo   [1] English
echo   [2] Espanol
set "LANG_CHOICE=1"
set /p LANG_CHOICE="  Type 1 or 2, then press Enter [1]: "
set "APP_LANG=en"
if "%LANG_CHOICE%"=="2" set "APP_LANG=es"
set "CONFIG_DIR=%USERPROFILE%\.aubieeternal"
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%" >nul 2>&1
> "%CONFIG_DIR%\language" echo %APP_LANG%
echo [OK] Language set to %APP_LANG%
echo.

set "PATH=%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Ollama;%PATH%"

python --version >nul 2>&1
if errorlevel 1 goto :InstallPython
echo [OK] Python found.
goto :AfterPython

:InstallPython
echo [*] Python not found. Installing Python 3.11...
set "PYTHON_INSTALLER=%TEMP%\python-installer.exe"
curl -L -o "%PYTHON_INSTALLER%" https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe --silent --show-error
if not exist "%PYTHON_INSTALLER%" goto :PythonFail
"%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
del "%PYTHON_INSTALLER%" >nul 2>&1
set "PATH=%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%LOCALAPPDATA%\Programs\Python\Python311;%PATH%"
python --version >nul 2>&1
if errorlevel 1 goto :PythonFail
echo [OK] Python installed.
goto :AfterPython

:PythonFail
echo [!] Could not install Python.
echo     Download it from https://python.org/downloads
echo     Check Add python.exe to PATH, then run this installer again.
pause
exit /b 1

:AfterPython
echo.
echo [*] Installing school packages. This can take a few minutes...
python -m pip install streamlit requests openai pandas plotly python-dateutil pytz --disable-pip-version-check
if errorlevel 1 goto :PipFail
echo [OK] Packages installed.
goto :AfterPip

:PipFail
echo [!] Package install failed. Leave this window open and send a photo of it.
pause
exit /b 1

:AfterPip
echo.
echo [*] Checking Ollama, the local AI engine...
ollama --version >nul 2>&1
if errorlevel 1 goto :InstallOllama
echo [OK] Ollama found.
goto :StartOllama

:InstallOllama
echo [*] Downloading Ollama. This is a large file and can take several minutes.
set "OLLAMA_INSTALLER=%TEMP%\OllamaSetup.exe"
curl -L -o "%OLLAMA_INSTALLER%" https://ollama.com/download/OllamaSetup.exe --silent --show-error
if not exist "%OLLAMA_INSTALLER%" goto :OllamaFail
echo [*] Installing Ollama...
"%OLLAMA_INSTALLER%" /VERYSILENT /NORESTART
del "%OLLAMA_INSTALLER%" >nul 2>&1
set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
ollama --version >nul 2>&1
if errorlevel 1 goto :OllamaFail
echo [OK] Ollama installed.
goto :StartOllama

:OllamaFail
echo [!] Ollama did not install.
echo     Download https://ollama.com/download/OllamaSetup.exe
echo     Run it, then run this installer again.
pause
exit /b 1

:StartOllama
ollama list >nul 2>&1
if not errorlevel 1 goto :PickModel
echo [*] Starting Ollama...
start "" /min "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
timeout /t 5 /nobreak >nul

:PickModel
set "RAM_GB=0"
set "VRAM_MB=0"
for /f "usebackq tokens=*" %%A in (`powershell -NoProfile -Command "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)" 2^>nul`) do set "RAM_GB=%%A"
for /f "usebackq tokens=*" %%A in (`nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2^>nul`) do set "VRAM_MB=%%A"

set "MODEL=qwen2.5:7b"
if %RAM_GB% GEQ 16 set "MODEL=qwen2.5:14b"
if %RAM_GB% GEQ 32 set "MODEL=qwen2.5:32b"
if %VRAM_MB% GEQ 10000 if %RAM_GB% GEQ 16 set "MODEL=qwen2.5:14b"
if %VRAM_MB% GEQ 20000 set "MODEL=qwen2.5:32b"

echo.
echo [*] This PC has about %RAM_GB% GB RAM and %VRAM_MB% MB video memory.
echo [*] Downloading %MODEL%. Leave this window open.
ollama pull %MODEL%
if errorlevel 1 goto :ModelFail
echo [OK] Model ready: %MODEL%
goto :Shortcut

:ModelFail
echo [!] Model download failed. Check the internet connection and run this installer again.
pause
exit /b 1

:Shortcut
set "SCRIPT_DIR=%~dp0"
set "DESKTOP_DIR=%USERPROFILE%\Desktop"
for /f "usebackq tokens=*" %%A in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')" 2^>nul`) do set "DESKTOP_DIR=%%A"
set "SHORTCUT=%DESKTOP_DIR%\AUBIEETERNAL.bat"
> "%SHORTCUT%" echo @echo off
>> "%SHORTCUT%" echo title AUBIEETERNAL
>> "%SHORTCUT%" echo cd /d "%SCRIPT_DIR%"
>> "%SHORTCUT%" echo python launcher.py
>> "%SHORTCUT%" echo pause
echo [OK] Desktop shortcut: %SHORTCUT%

echo.
echo ============================================================
echo   Starting AUBIEETERNAL.
echo   A browser tab will open. Leave this black window open.
echo   Next time, double-click AUBIEETERNAL on the Desktop.
echo ============================================================
echo.
python launcher.py
