"""
model_selector.py — picks the best local Ollama model a machine can actually
run, instead of a fixed hardcoded preference order.

Every install runs on different hardware. A family running AUBIEETERNAL on a
much stronger machine than the reference setup should default to a bigger,
better model - not silently get stuck on whatever the smallest hardcoded
model in some fallback list happens to be. This has no opinion about which
*family* of model to use (qwen2.5, llama3, etc.) - it just ranks whatever is
actually available by size and picks the largest one this machine's RAM can
comfortably hold.
"""

import re

import requests

OLLAMA_URL = "http://localhost:11434"

# Rough RAM needed per model size tier for a typical 4-bit quantized GGUF
# pull via Ollama - generous enough to avoid recommending something that'll
# swap/OOM, not an exact science. Keyed by rounded parameter count (billions).
TIER_RAM_GB = {32: 24, 14: 10, 8: 6, 7: 6, 3: 4, 2: 3, 1: 2}
TIER_VRAM_GB = {32: 20, 14: 9, 8: 6, 7: 5, 3: 3, 2: 2, 1: 2}


def detect_ram_gb() -> float | None:
    """System RAM in GB, or None if it can't be detected (e.g. non-Linux
    without /proc/meminfo) - callers should fail open, not block, on None."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return round(kb / (1024 * 1024), 1)
    except Exception:
        pass
    return None


def detect_vram_gb() -> float | None:
    """GPU VRAM in GB, or None if it can't be detected.
    nvidia-smi --format=csv,noheader,nounits returns MiB for memory.total."""
    import subprocess
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        mib = float(result.stdout.strip().splitlines()[0].strip())
        return round(mib / 1024.0, 1)
    except Exception:
        return None


def _model_size_b(name: str) -> float:
    """'qwen2.5:14b' -> 14.0. Unparseable names sort last (0.0), not first -
    an unknown-size model shouldn't accidentally win "biggest available"."""
    m = re.search(r":(\d+(?:\.\d+)?)b", name.lower())
    return float(m.group(1)) if m else 0.0


def list_available_models() -> list[str]:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def pick_best_model(candidates: list[str] | None = None) -> str | None:
    """Largest already-pulled model this machine can actually run.

    When GPU VRAM is detectable, VRAM fitness wins (a 12GB card prefers 14b over
    32b even if system RAM is huge). When VRAM is unknown, fall back to system RAM.
    """
    available = candidates if candidates is not None else list_available_models()
    if not available:
        return None
    ranked = sorted(available, key=_model_size_b, reverse=True)
    vram = detect_vram_gb()
    ram = detect_ram_gb()

    if vram is None and ram is None:
        return ranked[0]

    for name in ranked:
        size_b = _model_size_b(name)
        if vram is not None:
            needed_vram = TIER_VRAM_GB.get(round(size_b))
            if needed_vram is None:
                needed_vram = size_b * 0.7 + 1
            if needed_vram <= vram:
                return name
            continue
        # VRAM unknown ? RAM path
        needed_ram = TIER_RAM_GB.get(round(size_b)) or (size_b * 0.8 + 2)
        if needed_ram <= ram:
            return name
    return ranked[-1]


def ranked_try_order(candidates: list[str] | None = None) -> list[str]:
    """Full fallback order for a caller that wants to try more than one
    model if the first fails: best-fit first, then everything else
    available largest-to-smallest."""
    available = candidates if candidates is not None else list_available_models()
    best = pick_best_model(available)
    rest = sorted([m for m in available if m != best], key=_model_size_b, reverse=True)
    return ([best] if best else []) + rest


def recommend_model_to_pull(preferred_family: str = "qwen2.5") -> str:
    """For first-time setup, before anything is pulled yet: which model tag
    should the installer grab, given this machine's RAM alone."""
    ram = detect_ram_gb()
    if ram is None or ram < 16:
        return f"{preferred_family}:7b"
    if ram < 28:
        return f"{preferred_family}:14b"
    return f"{preferred_family}:32b"
