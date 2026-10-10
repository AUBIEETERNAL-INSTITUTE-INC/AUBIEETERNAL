"""Single source of truth for Thinking Mode → model + prompt extras.

12 GB GPU policy (RTX 3060 class):
  Fast     → best small/fast local tune if present, else qwen2.5:7b
  Balanced → qwen2.5:14b (everyday default)
  Deep     → qwen2.5:14b + longer step-by-step system add-on (no 32b)
"""
from __future__ import annotations

import os
import requests

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")

# Preference order for Fast (first match that is actually pulled wins).
# 2026-10-09: kid portal moved Fast to 14b + coaching rule (r10 leaked 25/25 on held-out).
# Old list kept for reference:
# FAST_CANDIDATES = [
#     "aubie-r10:latest",  # newest registered fine-tune (bench winner vs r8b/r9)
#     "aubie-r9:latest",
#     "aubie-r8b:latest",
#     "aubie-r8:latest",
#     "aubie:latest",
#     "qwen2.5:7b",
# ]
# Biggest first; each machine uses the first one it has pulled (students run this on their own hardware).
MODEL_LADDER = [
    "qwen2.5:14b",   # 12 GB+ GPU (the Ryzen rig)
    "qwen2.5:7b",    # ~8 GB GPU
    "qwen2.5:3b",    # small GPU or CPU-only laptop
]
FAST_CANDIDATES = MODEL_LADDER

BALANCED_MODEL = "qwen2.5:14b"
DEEP_MODEL = "qwen2.5:14b"

DEEP_SYSTEM_ADDON = (
    "Deep Thinking mode is on. Work step by step: (1) restate the question in plain words, "
    "(2) list the key facts or assumptions, (3) reason carefully, (4) give one clear next step or clue, not the final answer, "
    "(5) note one thing that could change the answer if it were different. "
    "Keep language parent-friendly when the audience is a family. No fake metrics or hype."
)

UI_LABELS = {
    "⚡ Fast": "fast",
    "⚖️ Balanced": "balanced",
    "🧠 Deep Thinking": "deep",
    "Fast": "fast",
    "Balanced": "balanced",
    "Deep Thinking": "deep",
}


def list_pulled() -> set[str]:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        names = set()
        for m in r.json().get("models", []):
            n = m.get("name") or ""
            names.add(n)
            if ":" in n:
                names.add(n.split(":", 1)[0])
        return names
    except Exception:
        return set()


def _pulled(name: str, available: set[str]) -> bool:
    if name in available:
        return True
    base = name.split(":", 1)[0]
    # accept either tag form
    return any(a == name or a.startswith(base + ":") for a in available)


def resolve_fast_model(available: set[str] | None = None) -> str:
    avail = available if available is not None else list_pulled()
    for cand in FAST_CANDIDATES:
        if _pulled(cand, avail):
            # Prefer exact tag if present
            if cand in avail:
                return cand
            base = cand.split(":", 1)[0]
            for a in avail:
                if a.startswith(base + ":"):
                    return a
            return cand
    for a in sorted(avail):  # nothing from the ladder: use any qwen2.5 the machine has
        if a.startswith("qwen2.5:") and ":" in a:
            return a
    return MODEL_LADDER[-1]  # smallest; the app will say it is not pulled


def model_for_mode(ui_mode: str, available: set[str] | None = None) -> str:
    key = UI_LABELS.get(ui_mode, UI_LABELS.get(ui_mode.strip(), "balanced"))
    # Every mode walks the same ladder, so a laptop without the 14b still works in all three.
    # Deep differs by its system add-on, not by a bigger model.
    return resolve_fast_model(available)


def system_addon_for_mode(ui_mode: str) -> str:
    key = UI_LABELS.get(ui_mode, "balanced")
    return DEEP_SYSTEM_ADDON if key == "deep" else ""


def router_task_models() -> dict[str, str]:
    """Legacy ai_model_router task_type → model (no 32b)."""
    fast = resolve_fast_model()
    return {
        "default": BALANCED_MODEL,
        "fast": fast,
        "heavy": DEEP_MODEL,
        "synthesis": BALANCED_MODEL,
        "chat": fast,
    }
