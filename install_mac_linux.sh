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

# ── Step 1: Python ────────────────────────────────────────────────────────────
echo "[1/4] Checking Python..."
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

# ── Step 2: Install packages ───────────────────────────────────────────────────
echo ""
echo "[2/4] Installing Python packages..."
"$PYTHON_CMD" -m pip install streamlit requests openai pandas plotly python-dateutil pytz \
    --quiet --disable-pip-version-check --break-system-packages 2>/dev/null || \
"$PYTHON_CMD" -m pip install streamlit requests openai pandas plotly python-dateutil pytz \
    --quiet --disable-pip-version-check
echo -e "  ${GREEN}✅ Packages ready${NC}"

# ── Step 3: Ollama ────────────────────────────────────────────────────────────
echo ""
echo "[3/4] Checking Ollama..."
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

    # Pull model
    echo ""
    echo "  Choose AI model:"
    echo "  [1] qwen2.5:7b  — Fast, works on 8GB RAM (4.7GB download)"
    echo "  [2] qwen2.5:14b — Best, needs 16GB RAM   (9.0GB download)"
    echo "  [3] Skip"
    read -p "  Choice (1/2/3): " MODEL_CHOICE
    case "$MODEL_CHOICE" in
        2) MODEL="qwen2.5:14b" ;;
        3) MODEL="" ;;
        *) MODEL="qwen2.5:7b" ;;
    esac

    if [ -n "$MODEL" ]; then
        echo "  Pulling $MODEL (this takes a few minutes)..."
        ollama pull "$MODEL"
        echo -e "  ${GREEN}✅ Model $MODEL ready${NC}"
    fi
fi

# ── Step 4: Create launcher ────────────────────────────────────────────────────
echo ""
echo "[4/4] Creating launcher..."

LAUNCHER_SCRIPT="$SCRIPT_DIR/run_aubieeternal.sh"
cat > "$LAUNCHER_SCRIPT" << RUNEOF
#!/bin/bash
cd "$SCRIPT_DIR"
$PYTHON_CMD launcher.py
RUNEOF
chmod +x "$LAUNCHER_SCRIPT"

# Create desktop shortcut
if [ "$OS" = "Darwin" ]; then
    DESKTOP="$HOME/Desktop/AUBIEETERNAL.command"
    cat > "$DESKTOP" << DESKTOPEOF
#!/bin/bash
cd "$SCRIPT_DIR"
$PYTHON_CMD launcher.py
DESKTOPEOF
    chmod +x "$DESKTOP"
    echo -e "  ${GREEN}✅ Desktop shortcut: AUBIEETERNAL.command${NC}"
else
    # Linux .desktop file
    DESKTOP_FILE="$HOME/Desktop/aubieeternal.desktop"
    cat > "$DESKTOP_FILE" << DESKTOPEOF
[Desktop Entry]
Name=AUBIEETERNAL
Comment=Sovereign Family Intelligence
Exec=bash -c 'cd $SCRIPT_DIR && $PYTHON_CMD launcher.py'
Icon=$SCRIPT_DIR/icon.png
Terminal=true
Type=Application
Categories=Education;
DESKTOPEOF
    chmod +x "$DESKTOP_FILE"
    echo -e "  ${GREEN}✅ Desktop shortcut: aubieeternal.desktop${NC}"
fi

echo ""
echo "============================================================"
echo -e "  ${GREEN}✅ Installation complete!${NC}"
echo ""
echo "  To launch AUBIEETERNAL:"
echo "  - Double-click the Desktop shortcut"
echo "  - Or run: $PYTHON_CMD launcher.py"
echo "  - Or run: ./run_aubieeternal.sh"
echo "============================================================"
echo ""
