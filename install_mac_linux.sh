#!/bin/bash
# AUBIEETERNAL Installer — macOS & Linux
# CC0 Public Domain | War Eagle Eternal

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "============================================================"
echo "   🦅  AUBIEETERNAL — macOS / Linux Installer"
echo "   Sovereign Family Intelligence"
echo "   CC0 Public Domain — War Eagle Eternal"
echo "============================================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OS="$(uname -s)"

# ── Step 1: Program language ──────────────────────────────────────────────────
# Written to ~/.aubieeternal/language, the single source of truth read by both
# the Streamlit launcher and the voice assistant (assistant_server.py). "en"
# and "es" ship today; the file format is just a bare language code so more
# can be added later without touching this script.
echo "[1/5] Choose your language / Elige tu idioma..."
echo "  [1] English"
echo "  [2] Español"
read -p "  Choice / Elección (1/2) [1]: " LANG_CHOICE
case "${LANG_CHOICE:-1}" in
    2) APP_LANG="es" ;;
    *) APP_LANG="en" ;;
esac
CONFIG_DIR="$HOME/.aubieeternal"
mkdir -p "$CONFIG_DIR"
if printf '%s\n' "$APP_LANG" > "$CONFIG_DIR/language" 2>/dev/null; then
    echo -e "  ${GREEN}✅ Language set to '$APP_LANG' ($CONFIG_DIR/language)${NC}"
else
    echo -e "  ${YELLOW}⚠️  Could not write $CONFIG_DIR/language - the app will default to English.${NC}"
    echo -e "     To fix by hand: mkdir -p \"$CONFIG_DIR\" && echo $APP_LANG > \"$CONFIG_DIR/language\""
fi

# ── Step 2: Python ────────────────────────────────────────────────────────────
echo "[2/5] Checking Python..."
PYTHON_OK=0
for CMD in python3 python; do
    if command -v "$CMD" &>/dev/null; then
        VERSION=$("$CMD" -c "import sys; print(sys.version_info[:2])")
        MAJOR=$("$CMD" -c "import sys; print(sys.version_info[0])")
        MINOR=$("$CMD" -c "import sys; print(sys.version_info[1])")
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
            echo -e "  ${GREEN}✅ Python $MAJOR.$MINOR found ($CMD)${NC}"
            PYTHON_CMD="$CMD"
            PYTHON_OK=1
            break
        fi
    fi
done

if [ "$PYTHON_OK" -eq 0 ]; then
    echo -e "  ${RED}❌ Python 3.10+ required.${NC}"
    if [ "$OS" = "Darwin" ]; then
        echo "  Install via Homebrew: brew install python@3.11"
        echo "  Or download: https://python.org/downloads"
    else
        echo "  Install: sudo apt install python3.11 python3.11-pip"
    fi
    exit 1
fi

# ── Step 3: Install packages ───────────────────────────────────────────────────
echo ""
echo "[3/5] Installing Python packages..."
"$PYTHON_CMD" -m pip install streamlit requests openai pandas plotly python-dateutil pytz \
    --quiet --disable-pip-version-check --break-system-packages 2>/dev/null || \
"$PYTHON_CMD" -m pip install streamlit requests openai pandas plotly python-dateutil pytz \
    --quiet --disable-pip-version-check
echo -e "  ${GREEN}✅ Packages ready${NC}"

# ── Step 4: Ollama ────────────────────────────────────────────────────────────
echo ""
echo "[4/5] Checking Ollama..."
if command -v ollama &>/dev/null; then
    echo -e "  ${GREEN}✅ Ollama found${NC}"
    OLLAMA_OK=1
else
    echo -e "  ${YELLOW}⚠️  Ollama not found. Installing...${NC}"
    curl -fsSL https://ollama.ai/install.sh | sh
    if command -v ollama &>/dev/null; then
        echo -e "  ${GREEN}✅ Ollama installed${NC}"
        OLLAMA_OK=1
    else
        echo -e "  ${RED}❌ Ollama install failed. Try manually: https://ollama.ai${NC}"
        OLLAMA_OK=0
    fi
fi

if [ "$OLLAMA_OK" -eq 1 ]; then
    # Start Ollama if not running
    if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
        echo "  Starting Ollama..."
        ollama serve &>/dev/null &
        sleep 3
    fi

    # Detect RAM to recommend a model tier - a stronger machine should
    # default to a bigger model, not always the smallest one.
    if [[ "$OSTYPE" == "darwin"* ]]; then
        RAM_GB=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1073741824 ))
    else
        RAM_GB=$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo 2>/dev/null)
    fi
    if [ -n "$RAM_GB" ] && [ "$RAM_GB" -ge 28 ] 2>/dev/null; then
        RECOMMENDED=3
    elif [ -n "$RAM_GB" ] && [ "$RAM_GB" -ge 16 ] 2>/dev/null; then
        RECOMMENDED=2
    else
        RECOMMENDED=1
    fi

    # Pull model
    echo ""
    echo "  Choose AI model:"
    [ -n "$RAM_GB" ] && [ "$RAM_GB" -gt 0 ] 2>/dev/null && echo "  (detected ~${RAM_GB}GB RAM)"
    echo "  [1] qwen2.5:7b  — Fast, works on 8GB RAM (4.7GB download)"
    echo "  [2] qwen2.5:14b — Best, needs 16GB RAM   (9.0GB download)"
    echo "  [3] qwen2.5:32b — Strongest, needs 28GB+ RAM (18GB download)"
    echo "  [4] Skip"
    read -p "  Choice (1/2/3/4) [recommended: $RECOMMENDED]: " MODEL_CHOICE
    MODEL_CHOICE="${MODEL_CHOICE:-$RECOMMENDED}"
    case "$MODEL_CHOICE" in
        2) MODEL="qwen2.5:14b" ;;
        3) MODEL="qwen2.5:32b" ;;
        4) MODEL="" ;;
        *) MODEL="qwen2.5:7b" ;;
    esac

    if [ -n "$MODEL" ]; then
        echo "  Pulling $MODEL (this takes a few minutes)..."
        ollama pull "$MODEL"
        echo -e "  ${GREEN}✅ Model $MODEL ready${NC}"
    fi
fi

# ── Step 5: Create launcher ────────────────────────────────────────────────────
echo ""
echo "[5/5] Creating launcher..."

LAUNCHER_SCRIPT="$SCRIPT_DIR/run_aubieeternal.sh"
cat > "$LAUNCHER_SCRIPT" << RUNEOF
#!/bin/bash
cd "$SCRIPT_DIR"
$PYTHON_CMD launcher.py
RUNEOF
chmod +x "$LAUNCHER_SCRIPT"

# Create desktop shortcut. This step is best-effort: if $HOME/Desktop is
# missing (headless box, non-English locale folder, OneDrive redirection)
# the write can fail, and previously the script printed a success line
# anyway and moved on - leaving a support-case user with no obvious way to
# start the app. Now a failure is reported, and the manual-launch commands
# below always print regardless of what happened here.
SHORTCUT_OK=0
mkdir -p "$HOME/Desktop" 2>/dev/null
if [ "$OS" = "Darwin" ]; then
    DESKTOP="$HOME/Desktop/AUBIEETERNAL.command"
    if cat > "$DESKTOP" << DESKTOPEOF 2>/dev/null
#!/bin/bash
cd "$SCRIPT_DIR"
$PYTHON_CMD launcher.py
DESKTOPEOF
    then
        chmod +x "$DESKTOP" 2>/dev/null && SHORTCUT_OK=1
    fi
    [ "$SHORTCUT_OK" -eq 1 ] && echo -e "  ${GREEN}✅ Desktop shortcut: AUBIEETERNAL.command${NC}"
else
    # Linux .desktop file
    DESKTOP_FILE="$HOME/Desktop/aubieeternal.desktop"
    if cat > "$DESKTOP_FILE" << DESKTOPEOF 2>/dev/null
[Desktop Entry]
Name=AUBIEETERNAL
Comment=Sovereign Family Intelligence
Exec=bash -c 'cd $SCRIPT_DIR && $PYTHON_CMD launcher.py'
Icon=$SCRIPT_DIR/icon.png
Terminal=true
Type=Application
Categories=Education;
DESKTOPEOF
    then
        chmod +x "$DESKTOP_FILE" 2>/dev/null && SHORTCUT_OK=1
    fi
    [ "$SHORTCUT_OK" -eq 1 ] && echo -e "  ${GREEN}✅ Desktop shortcut: aubieeternal.desktop${NC}"
fi
[ "$SHORTCUT_OK" -eq 0 ] && echo -e "  ${YELLOW}⚠️  Couldn't create a Desktop shortcut - use the manual command below.${NC}"

echo ""
echo "============================================================"
echo -e "  ${GREEN}✅ Installation complete!${NC}"
echo ""
echo "  To launch AUBIEETERNAL (any of these work):"
[ "$SHORTCUT_OK" -eq 1 ] && echo "  - Double-click the Desktop shortcut"
echo "  - Run:  cd \"$SCRIPT_DIR\" && $PYTHON_CMD launcher.py"
echo "  - Run:  \"$SCRIPT_DIR/run_aubieeternal.sh\""
echo "============================================================"
echo ""
