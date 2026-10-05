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
FAST_CANDIDATES = [
    "aubie-r8b:latest",
    "aubie-r8:latest",
    "aubie:latest",
    "qwen2.5:7b",
]

BALANCED_MODEL = "qwen2.5:14b"
DEEP_MODEL = "qwen2.5:14b"

DEEP_SYSTEM_ADDON = (
    "Deep Thinking mode is on. Work step by step: (1) restate the question in plain words, "
    "(2) list the key facts or assumptions, (3) reason carefully, (4) give a clear answer, "
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
    return "qwen2.5:7b"


def model_for_mode(ui_mode: str, available: set[str] | None = None) -> str:
    key = UI_LABELS.get(ui_mode, UI_LABELS.get(ui_mode.strip(), "balanced"))
    if key == "fast":
        return resolve_fast_model(available)
    if key == "deep":
        return DEEP_MODEL
    return BALANCED_MODEL


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
