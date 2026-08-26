"""
launcher.py — AUBIEETERNAL Launcher
=====================================
Double-click this file to run AUBIEETERNAL on any PC.
No technical knowledge required.

What this does automatically:
  1. Checks Python version (3.10+ required)
  2. Installs required Python packages if missing
  3. Checks for Ollama — guides install if missing
  4. Pulls the recommended AI model if not present
  5. Creates your data folder
  6. Runs AUBIEETERNAL in your browser

Works on: Windows 10/11, macOS 12+, Ubuntu 22.04+

Source: https://github.com/AUBIEETERNAL-INSTITUTE-INC/AUBIEETERNAL
License: CC0 Public Domain
"""

import sys
import os
import subprocess
import platform
import time
import webbrowser
import json
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
APP_NAME     = "AUBIEETERNAL"
APP_VERSION  = "v68.0"
DEFAULT_PORT = 8501
DEFAULT_MODEL = "qwen2.5:7b"     # 7b = fast, works on 8GB RAM
HEAVY_MODEL   = "qwen2.5:14b"    # 14b = balanced, needs 16GB RAM
DATA_DIR_NAME = "AUBIEETERNAL"

REQUIRED_PACKAGES = [
    "streamlit>=1.32.0",
    "requests>=2.31.0",
    "openai>=1.14.0",
    "pandas>=2.0.0",
    "plotly>=5.18.0",
    "python-dateutil>=2.8.2",
    "pytz>=2023.3",
]

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║   🦅  AUBIEETERNAL — Sovereign Family Intelligence           ║
║   v68.0 | CC0 Public Domain | War Eagle Eternal              ║
╚══════════════════════════════════════════════════════════════╝
"""

# ── Helpers ────────────────────────────────────────────────────────────────────

def log(msg, icon="  "):
    print(f"{icon} {msg}")

def log_ok(msg):
    print(f"  ✅ {msg}")

def log_warn(msg):
    print(f"  ⚠️  {msg}")

def log_err(msg):
    print(f"  ❌ {msg}")

def log_step(n, total, msg):
    print(f"\n[{n}/{total}] {msg}")


# ── Step 1: Python version check ───────────────────────────────────────────────

def check_python():
    log_step(1, 6, "Checking Python version...")
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 10):
        log_err(f"Python 3.10+ required. You have {major}.{minor}")
        log_err("Download from: https://python.org/downloads")
        input("\nPress Enter to exit...")
        sys.exit(1)
    log_ok(f"Python {major}.{minor} — good")


# ── Step 2: Install Python packages ───────────────────────────────────────────

def install_packages():
    log_step(2, 6, "Checking Python packages...")
    missing = []
    for pkg in REQUIRED_PACKAGES:
        pkg_name = pkg.split(">=")[0].split("==")[0].replace("-", "_")
        try:
            __import__(pkg_name)
        except ImportError:
            missing.append(pkg)

    if not missing:
        log_ok("All packages present")
        return

    log_warn(f"Installing {len(missing)} missing packages...")
    for pkg in missing:
        log(f"Installing {pkg}...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg,
             "--quiet", "--disable-pip-version-check"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            log_ok(f"Installed {pkg.split('>=')[0]}")
        else:
            log_warn(f"Could not install {pkg} — {result.stderr[:100]}")


# ── Step 3: Data directory ─────────────────────────────────────────────────────

def setup_data_dir() -> Path:
    log_step(3, 6, "Setting up data directory...")

    # Choose platform-appropriate location
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home())) / DATA_DIR_NAME
    elif system == "Darwin":  # macOS
        base = Path.home() / "Library" / "Application Support" / DATA_DIR_NAME
    else:  # Linux
        base = Path.home() / f".{DATA_DIR_NAME.lower()}"

    # Create subdirectories
    (base / "families").mkdir(parents=True, exist_ok=True)
    (base / "insights" / "daily").mkdir(parents=True, exist_ok=True)
    (base / "insights" / "x_lessons").mkdir(parents=True, exist_ok=True)
    (base / "insights" / "probe").mkdir(parents=True, exist_ok=True)
    (base / "lattice").mkdir(parents=True, exist_ok=True)

    # Set the environment variable so all modules can find it
    os.environ["AUBIE_DATA"] = str(base)

    log_ok(f"Data directory: {base}")
    return base


# ── Step 4: Check/install Ollama ───────────────────────────────────────────────

def check_ollama() -> bool:
    log_step(4, 6, "Checking Ollama (local AI engine)...")

    # Check if Ollama is already running
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
            if r.status == 200:
                data = json.loads(r.read())
                models = [m["name"] for m in data.get("models", [])]
                log_ok(f"Ollama running — {len(models)} models available: {models[:3]}")
                return True
    except Exception:
        pass

    # Check if ollama binary exists but isn't running
    ollama_cmd = "ollama"
    try:
        result = subprocess.run([ollama_cmd, "--version"],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            log_warn("Ollama installed but not running. Starting...")
            # Try to start it
            if platform.system() == "Windows":
                subprocess.Popen(["ollama", "serve"],
                                  creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(["ollama", "serve"],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            time.sleep(3)
            # Check again
            try:
                with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as r:
                    if r.status == 200:
                        log_ok("Ollama started successfully")
                        return True
            except Exception:
                pass
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Ollama not found — guide user
    system = platform.system()
    print("""
  ┌─────────────────────────────────────────────────────────┐
  │  Ollama not found. Ollama is the free local AI engine.   │
  │  It's required to run AUBIEETERNAL offline.              │
  │                                                          │
  │  Install it now (free, ~500MB download):                 │
  │""")
    if system == "Windows":
        ollama_url = "https://ollama.ai/download/OllamaSetup.exe"
        print(f"  │  → Download: {ollama_url}")
        print(  "  │  → Run the installer, then restart AUBIEETERNAL")
        answer = input("\n  Open Ollama download page in browser? (y/n): ")
        if answer.lower() == 'y':
            webbrowser.open(ollama_url)
    elif system == "Darwin":
        ollama_url = "https://ollama.ai/download/Ollama-darwin.zip"
        print(f"  │  → Download: {ollama_url}")
        print(  "  │  Or run: curl -fsSL https://ollama.ai/install.sh | sh")
        answer = input("\n  Open Ollama download page? (y/n): ")
        if answer.lower() == 'y':
            webbrowser.open("https://ollama.ai/download")
    else:
        print("  │  → Run: curl -fsSL https://ollama.ai/install.sh | sh")
        answer = input("\n  Run Ollama installer now? (y/n): ")
        if answer.lower() == 'y':
            subprocess.run("curl -fsSL https://ollama.ai/install.sh | sh", shell=True)
            time.sleep(5)
            return check_ollama()

    print("""  └─────────────────────────────────────────────────────────┘""")
    print("\n  AUBIEETERNAL will launch without AI features until Ollama is installed.")
    print("  You can still use all tabs and lessons — just not the AI oracle/tutor.\n")
    return False


# ── Step 5: Pull AI model ──────────────────────────────────────────────────────

def pull_model(ollama_available: bool, data_dir: Path):
    log_step(5, 6, "Checking AI model...")

    if not ollama_available:
        log_warn("Skipping model check — Ollama not available")
        return

    # Read model preference from settings if exists
    settings_path = data_dir / "settings.json"
    settings      = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except Exception:
            pass

    preferred_model = settings.get("model", DEFAULT_MODEL)

    # Check if model is already available
    try:
        import urllib.request, json as _json
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as r:
            data   = _json.loads(r.read())
            models = [m["name"] for m in data.get("models", [])]
            model_base = preferred_model.split(":")[0]
            if any(model_base in m for m in models):
                log_ok(f"Model {preferred_model} ready")
                os.environ["AUBIE_MODEL"] = preferred_model
                return
    except Exception:
        pass

    # Prompt user to choose model
    print(f"""
  ┌─────────────────────────────────────────────────────────┐
  │  No AI model found. Choose one to download:             │
  │                                                          │
  │  [1] qwen2.5:7b   — Fast, works on 8GB RAM  (4.7GB)    │
  │  [2] qwen2.5:14b  — Best balance, 16GB RAM  (9.0GB)    │
  │  [3] Skip for now — launch without AI                   │
  └─────────────────────────────────────────────────────────┘""")

    choice = input("  Your choice (1/2/3): ").strip()
    if choice == "2":
        model = HEAVY_MODEL
    elif choice == "3":
        log_warn("Skipping model download")
        return
    else:
        model = DEFAULT_MODEL

    print(f"\n  Downloading {model} (this is a one-time download)...")
    print("  This may take 5-20 minutes depending on your internet speed.\n")

    result = subprocess.run(["ollama", "pull", model])
    if result.returncode == 0:
        log_ok(f"Model {model} ready")
        os.environ["AUBIE_MODEL"] = model
        # Save preference
        settings["model"] = model
        settings_path.write_text(json.dumps(settings, indent=2))
    else:
        log_warn("Model download failed — launching without AI model")


# ── Step 6: Launch ─────────────────────────────────────────────────────────────

def launch_app(data_dir: Path):
    log_step(6, 6, "Launching AUBIEETERNAL...")

    # Find app.py in the same directory as launcher.py
    launcher_dir = Path(__file__).parent.resolve()
    app_path     = launcher_dir / "app.py"

    if not app_path.exists():
        # Try offline runner
        offline_path = launcher_dir / "aubie_offline.py"
        if offline_path.exists():
            log_warn("app.py not found — launching offline runner")
            os.environ["AUBIE_DATA"] = str(data_dir)
            os.environ["AUBIE_PORT"] = str(DEFAULT_PORT)
            subprocess.run([sys.executable, str(offline_path)])
            return
        else:
            log_err("app.py not found. Make sure launcher.py is in the AUBIEETERNAL folder.")
            input("Press Enter to exit...")
            sys.exit(1)

    # Set environment
    os.environ["AUBIE_DATA"] = str(data_dir)
    if "AUBIE_MODEL" not in os.environ:
        os.environ["AUBIE_MODEL"] = DEFAULT_MODEL

    # Open browser after a short delay
    def open_browser():
        time.sleep(3)
        webbrowser.open(f"http://localhost:{DEFAULT_PORT}")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    print(f"""
  ┌─────────────────────────────────────────────────────────┐
  │  🦅 AUBIEETERNAL is launching!                          │
  │                                                          │
  │  Browser will open automatically.                        │
  │  If not: http://localhost:{DEFAULT_PORT}                          │
  │                                                          │
  │  To stop: press Ctrl+C in this window                   │
  └─────────────────────────────────────────────────────────┘
""")

    subprocess.run([
        sys.executable, "-m", "streamlit", "run", str(app_path),
        f"--server.port={DEFAULT_PORT}",
        "--server.address=localhost",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--theme.base=dark",
        "--theme.primaryColor=#f7931a",
        "--theme.backgroundColor=#0a0e1a",
        "--theme.secondaryBackgroundColor=#1a2233",
        "--theme.textColor=#c8d8ff",
    ])


# ── First-run welcome ──────────────────────────────────────────────────────────

def first_run_setup(data_dir: Path):
    settings_path = data_dir / "settings.json"
    if settings_path.exists():
        return  # Already set up

    print("""
  ┌─────────────────────────────────────────────────────────┐
  │  👋 Welcome to AUBIEETERNAL!                            │
  │                                                          │
  │  First time setup — takes 30 seconds.                   │
  └─────────────────────────────────────────────────────────┘
""")

    family_name = input("  Your family name (e.g. 'The Smiths'): ").strip() or "My Family"
    parent_name = input("  Your name (parent): ").strip() or "Parent"
    kid_name    = input("  Kid's name (or press Enter to skip): ").strip() or ""

    settings = {
        "family_name":   family_name,
        "parent_name":   parent_name,
        "kid_name":      kid_name,
        "model":         DEFAULT_MODEL,
        "setup_complete": True,
        "setup_date":    __import__("datetime").date.today().isoformat(),
    }
    settings_path.write_text(json.dumps(settings, indent=2))

    print(f"""
  ✅ Welcome, {family_name}!

  Your data stays 100% on this computer.
  No accounts. No cloud. No subscription.
  Source code: https://github.com/AUBIEETERNAL-INSTITUTE-INC/AUBIEETERNAL
""")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(BANNER)
    print(f"  Starting {APP_NAME} {APP_VERSION}...\n")

    check_python()
    install_packages()
    data_dir = setup_data_dir()
    first_run_setup(data_dir)
    ollama_ok = check_ollama()
    pull_model(ollama_ok, data_dir)
    launch_app(data_dir)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  🦅 AUBIEETERNAL stopped. War Eagle Eternal.")
    except Exception as e:
        print(f"\n  ❌ Unexpected error: {e}")
        input("  Press Enter to exit...")
