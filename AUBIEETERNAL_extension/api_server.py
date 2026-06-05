"""
api_server.py — AUBIEETERNAL Local API Server
==============================================
Lightweight FastAPI server that runs alongside the Streamlit app.
The browser extension calls this server directly.

Port: 8502 (Streamlit is 8501)

Endpoints:
  GET  /status         — swarm status + wonder/coherence
  POST /bridge         — X Bridge analysis
  POST /oracle         — Oracle question
  GET  /ledger/stats   — Truth Debt stats
  POST /ledger/register — Register a claim

Run it:
  python api_server.py

Or add it to start.sh alongside the Streamlit app:
  nohup python3 api_server.py > /mnt/main/api_server.log 2>&1 &
"""

import os, json, sys, datetime
from pathlib import Path

# ── Try to import FastAPI, fall back to Flask if not available ─────────────────
def _data_dir():
    import socket
    try:
        socket.gethostbyname("ollama.startos")
        return Path("/mnt/main")
    except Exception:
        p = Path(os.path.expanduser("~/.aubieeternal/main"))
        p.mkdir(parents=True, exist_ok=True)
        return p

DATA_DIR = _data_dir()
SWARM_STATUS = DATA_DIR / "swarm_status.json"
REPO_DIR     = DATA_DIR / "repo"

# Add all possible module locations to path
# Handles: StartOS (/mnt/main/repo), WSL ~/AUBIEETERNAL, ~/AUBIEETERNAL_extension
import pathlib as _pl
_possible_paths = [
    str(REPO_DIR),
    str(_pl.Path.home() / "AUBIEETERNAL"),
    str(_pl.Path.home() / "AUBIEETERNAL_extension"),
    str(_pl.Path(__file__).parent),  # same dir as api_server.py
    str(_pl.Path(__file__).parent.parent),  # parent dir
]
for _p in _possible_paths:
    if _p not in sys.path and _pl.Path(_p).exists():
        sys.path.insert(0, _p)

PORT = int(os.environ.get("AUBIE_API_PORT", "8502"))

# ── Try FastAPI first ──────────────────────────────────────────────────────────
try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

# ── Fall back to Flask ─────────────────────────────────────────────────────────
if not USE_FASTAPI:
    try:
        from flask import Flask, request, jsonify
        from flask_cors import CORS
        USE_FLASK = True
    except ImportError:
        USE_FLASK = False
        print("⚠️  Neither FastAPI nor Flask found.")
        print("    Run: pip install fastapi uvicorn")
        print("    Or:  pip install flask flask-cors")
        sys.exit(1)
else:
    USE_FLASK = False


def _load_swarm_status():
    if SWARM_STATUS.exists():
        try:
            return json.loads(SWARM_STATUS.read_text())
        except Exception:
            pass
    return {"wonder_index": 1.0, "inter_rune_coherence": 1.0, "mets": 0,
            "child_rune_confirmations": 0, "daily_cost": 0.0}


def _run_bridge(text: str) -> dict:
    try:
        from x_bridge import XBridge
        bridge = XBridge()
        return bridge.process(text, save_as_lesson=True)
    except ImportError:
        return {"error": "x_bridge.py not found", "epistemic": {}, "family": {}, "simulation": {}}
    except Exception as e:
        return {"error": str(e), "epistemic": {}, "family": {}, "simulation": {}}


def _run_oracle(question: str, api_key: str = "") -> str:
    import requests as _req
    import socket

    system_prompt = (
        "You are the AUBIEETERNAL Oracle — a sovereign epistemic tutor. "
        "Be honest about uncertainty. Steelman opposing views. "
        "Point toward first principles. Never flatter. "
        "If you don't know, say so clearly. Max 150 words."
    )

    # Try xAI API key first (if provided)
    _xai_key = api_key or os.environ.get("XAI_KEY", "")
    if _xai_key:
        try:
            _r = _req.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {_xai_key}",
                         "Content-Type": "application/json"},
                json={"model": "grok-3-mini",
                      "messages": [{"role": "system", "content": system_prompt},
                                   {"role": "user", "content": question}],
                      "max_tokens": 300},
                timeout=30
            )
            if _r.status_code == 200:
                return _r.json()["choices"][0]["message"]["content"].strip()
        except Exception as _e:
            pass  # fall through to Ollama

    # Try Ollama — all possible locations
    _ollama_candidates = [
        "http://ollama.startos:11434",
        "http://painful-recess.local:59885",
        "http://192.168.1.251:59885",
        "http://localhost:11434",
        "http://127.0.0.1:11434",
    ]
    _model = os.environ.get("AUBIE_MODEL", "qwen2.5:7b")
    for _candidate in _ollama_candidates:
        try:
            _check = _req.get(f"{_candidate}/api/tags", timeout=2)
            if _check.status_code == 200:
                _r = _req.post(
                    f"{_candidate}/v1/chat/completions",
                    json={"model": _model,
                          "messages": [{"role": "system", "content": system_prompt},
                                       {"role": "user", "content": question}],
                          "stream": False, "temperature": 0.7},
                    timeout=60
                )
                if _r.status_code == 200:
                    return _r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            continue

    return ("Oracle unavailable. To fix:\n"
            "• Enter your xAI API key in Settings (works instantly), OR\n"
            "• Install Ollama: curl -fsSL https://ollama.ai/install.sh | sh")

    model = os.environ.get("AUBIE_MODEL", "qwen2.5:7b")
    system = (
        "You are the AUBIEETERNAL Oracle — a sovereign epistemic tutor. "
        "Be honest about uncertainty. Steelman opposing views. "
        "Point toward first principles. Never flatter. "
        "If you don't know, say so clearly. Max 150 words."
    )
    try:
        r = _req.post(url, json={
            "model": model,
            "messages": [{"role": "system", "content": system},
                          {"role": "user", "content": question}],
            "stream": False, "temperature": 0.7
        }, timeout=60)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Oracle unavailable: {e}"
    return "Oracle unavailable — check Ollama is running."


def _get_ledger_stats() -> dict:
    try:
        from truth_debt_ledger import TruthDebtLedger
        return TruthDebtLedger().get_accountability_report(90)
    except Exception:
        return {"total": 0, "verified": 0, "refuted": 0, "accuracy_rate": None}


def _register_claim(claim: str, claim_type: str, source: str) -> dict:
    try:
        from truth_debt_ledger import TruthDebtLedger
        return TruthDebtLedger().register(claim=claim, claim_type=claim_type, source=source)
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# FastAPI version
# ══════════════════════════════════════════════════════════════════════════════
if USE_FASTAPI:
    app = FastAPI(title="AUBIEETERNAL API", version="68.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # extension can call from any origin
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class BridgeRequest(BaseModel):
        text: str

    class OracleRequest(BaseModel):
        question: str

    class ClaimRequest(BaseModel):
        claim: str
        claim_type: str = "general"
        source: str = "extension"

    @app.get("/status")
    async def status():
        s = _load_swarm_status()
        return {
            "online":                    True,
            "wonder_index":              s.get("wonder_index", 1.0),
            "coherence":                 s.get("inter_rune_coherence", 1.0),
            "mets":                      s.get("mets", 0),
            "child_rune_confirmations":  s.get("child_rune_confirmations", 0),
            "daily_cost":                s.get("daily_cost", 0.0),
            "timestamp":                 datetime.datetime.now().isoformat(),
        }

    @app.post("/bridge")
    async def bridge(req: BridgeRequest):
        return _run_bridge(req.text)

    @app.post("/oracle")
    async def oracle(req: OracleRequest):
        return {"answer": _run_oracle(req.question, api_key=req.api_key)}

    @app.get("/ledger/stats")
    async def ledger_stats():
        return _get_ledger_stats()

    @app.post("/ledger/register")
    async def ledger_register(req: ClaimRequest):
        return _register_claim(req.claim, req.claim_type, req.source)


    class RecordRequest(BaseModel):
        content: str
        source: str = "extension"
        coherence: float = 0.5

    class SealRequest(BaseModel):
        entry_id: str
        note: str = ""
        broadcaster: str = "family"

    @app.get("/rune/status")
    async def rune_status():
        try:
            from rune_memory import ShieldRune, RuneMemory
            shield = ShieldRune()
            mem    = RuneMemory()
            status = shield.get_status()
            status.update(mem.get_stats())
            return status
        except Exception as e:
            return {"error": str(e), "total_seals": 0, "bitcoin_anchored": 0, "pending_merges": 0}

    @app.post("/rune/record")
    async def rune_record(req: RecordRequest):
        try:
            from rune_memory import record_extension_capture
            entry_id = record_extension_capture(req.content, coherence=req.coherence)
            return {"entry_id": entry_id, "status": "recorded", "level": 1}
        except Exception as e:
            return {"error": str(e)}

    @app.post("/rune/seal")
    async def rune_seal(req: SealRequest):
        try:
            from rune_memory import ShieldRune
            shield = ShieldRune()
            result = shield.seal(req.entry_id, note=req.note, broadcaster=req.broadcaster)
            return result
        except Exception as e:
            return {"error": str(e)}

    @app.get("/rune/memories")
    async def rune_memories():
        try:
            from rune_memory import RuneMemory
            mem = RuneMemory()
            return {"memories": mem.get_recent(20), "stats": mem.get_stats()}
        except Exception as e:
            return {"error": str(e), "memories": []}

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "68.0"}

# ══════════════════════════════════════════════════════════════════════════════
# Flask fallback version
# ══════════════════════════════════════════════════════════════════════════════
elif USE_FLASK:
    app = Flask(__name__)
    CORS(app)

    @app.route("/status")
    def status():
        s = _load_swarm_status()
        return jsonify({
            "online": True,
            "wonder_index": s.get("wonder_index", 1.0),
            "coherence":    s.get("inter_rune_coherence", 1.0),
            "mets":         s.get("mets", 0),
            "child_rune_confirmations": s.get("child_rune_confirmations", 0),
            "daily_cost":   s.get("daily_cost", 0.0),
        })

    @app.route("/bridge", methods=["POST"])
    def bridge():
        data = request.get_json()
        return jsonify(_run_bridge(data.get("text", "")))

    @app.route("/oracle", methods=["POST"])
    def oracle():
        data = request.get_json()
        return jsonify({"answer": _run_oracle(data.get("question", ""), api_key=data.get("api_key",""))})

    @app.route("/ledger/stats")
    def ledger_stats():
        return jsonify(_get_ledger_stats())

    @app.route("/ledger/register", methods=["POST"])
    def ledger_register():
        data = request.get_json()
        return jsonify(_register_claim(
            data.get("claim",""), data.get("claim_type","general"), data.get("source","extension")
        ))

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "version": "68.0"})


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║   🦅  AUBIEETERNAL API Server                                ║
║   Port {PORT} | {'FastAPI' if USE_FASTAPI else 'Flask'}                                  ║
║   Extension connects to: http://localhost:{PORT}              ║
╚══════════════════════════════════════════════════════════════╝
""")

    if USE_FASTAPI:
        uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
    else:
        app.run(host="127.0.0.1", port=PORT, debug=False)
