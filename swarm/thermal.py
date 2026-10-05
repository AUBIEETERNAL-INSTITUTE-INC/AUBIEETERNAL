"""GPU heat guard for Aubie Bot.

Call wait_for_cool() before every local-model request so agents do not cook the PC.
Limits are configurable below. Never changes power or fan settings (needs sudo).
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

SOFT_LIMIT_C = int(os.environ.get("AUBIE_GPU_SOFT_C", "78"))
RESUME_C = int(os.environ.get("AUBIE_GPU_RESUME_C", "70"))
HARD_LIMIT_C = int(os.environ.get("AUBIE_GPU_HARD_C", "85"))
POLL_S = int(os.environ.get("AUBIE_GPU_POLL_S", "15"))
MAX_WAIT_S = int(os.environ.get("AUBIE_GPU_MAX_WAIT_S", "300"))

LEDGER = Path(os.environ.get(
    "AUBIE_LEDGER",
    str(Path("/mnt/main/aubie-error-ledger.md") if Path("/mnt/main").exists() else Path.home() / "aubie-error-ledger.md"),
))
_PEAK_C = 0


class TooHot(Exception):
    """GPU is above the hard limit, or soft-limit wait timed out."""


def _log(event: str, detail: str = "") -> None:
    line = f"- {time.strftime('%Y-%m-%d %H:%M:%S %Z')} | id=- | thermal | {event}"
    if detail:
        line += " | " + " ".join(str(detail).replace("`", "'").split())[:300]
    try:
        text = LEDGER.read_text(errors="replace") if LEDGER.exists() else ""
        header = "" if "# Aubie action log" in text else "\n\n# Aubie action log (append-only)\n\n"
        with LEDGER.open("a") as f:
            f.write(header + line + "\n")
    except Exception:
        pass


def read_gpu() -> dict:
    try:
        out = subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=temperature.gpu,power.draw,utilization.gpu,fan.speed,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            text=True, timeout=5,
        ).strip().split(",")
        vals = []
        for x in out:
            x = x.strip().replace("[N/A]", "")
            try:
                vals.append(float(x) if x else None)
            except ValueError:
                vals.append(None)
        while len(vals) < 6:
            vals.append(None)
        return {
            "temp_c": int(vals[0]) if vals[0] is not None else None,
            "power_w": vals[1],
            "util_pct": int(vals[2]) if vals[2] is not None else None,
            "fan_pct": int(vals[3]) if vals[3] is not None else None,
            "mem_used_mib": int(vals[4]) if vals[4] is not None else None,
            "mem_total_mib": int(vals[5]) if vals[5] is not None else None,
        }
    except Exception as e:
        return {"temp_c": None, "error": str(e)}


def peak_c() -> int:
    return _PEAK_C


def status_line() -> str:
    g = read_gpu()
    if g.get("temp_c") is None:
        err = g.get("error")
        return f"GPU: (unavailable{': ' + err if err else ''})"
    return (
        f"GPU: {g['temp_c']}C / soft {SOFT_LIMIT_C}C / hard {HARD_LIMIT_C}C"
        f" | power {g.get('power_w')} W | util {g.get('util_pct')}%"
        f" | fan {g.get('fan_pct')}% | VRAM {g.get('mem_used_mib')}/{g.get('mem_total_mib')} MiB"
        f" | peak this process {_PEAK_C}C"
    )


def wait_for_cool(reason: str = "model request") -> dict:
    global _PEAK_C
    g = read_gpu()
    t = g.get("temp_c")
    if t is None:
        return g
    _PEAK_C = max(_PEAK_C, t)
    if t >= HARD_LIMIT_C:
        _log("hard-limit-refuse", f"{reason}: {t}C >= {HARD_LIMIT_C}C; {status_line()}")
        raise TooHot(
            f"GPU is {t}C (hard limit {HARD_LIMIT_C}C). Refusing to start {reason}. "
            f"Let the card cool, then retry. {status_line()}"
        )
    if t < SOFT_LIMIT_C:
        return g
    _log("soft-limit-wait", f"{reason}: {t}C >= {SOFT_LIMIT_C}C; waiting for <= {RESUME_C}C")
    print(
        f"[aubie thermal] GPU {t}C is warm (soft {SOFT_LIMIT_C}C). "
        f"Waiting for <= {RESUME_C}C before {reason}...",
        flush=True,
    )
    start = time.time()
    while True:
        time.sleep(POLL_S)
        g = read_gpu()
        t = g.get("temp_c")
        if t is None:
            return g
        _PEAK_C = max(_PEAK_C, t)
        elapsed = int(time.time() - start)
        if t >= HARD_LIMIT_C:
            _log("hard-limit-during-wait", f"{reason}: rose to {t}C after {elapsed}s")
            raise TooHot(
                f"GPU rose to {t}C while waiting (hard limit {HARD_LIMIT_C}C). "
                f"Aborted {reason}. {status_line()}"
            )
        if t <= RESUME_C:
            _log("soft-limit-resumed", f"{reason}: {t}C after {elapsed}s; {status_line()}")
            print(f"[aubie thermal] GPU {t}C ? resuming {reason}.", flush=True)
            return g
        if elapsed >= MAX_WAIT_S:
            _log("soft-limit-timeout", f"{reason}: still {t}C after {elapsed}s")
            raise TooHot(
                f"GPU still {t}C after waiting {elapsed}s (wanted <= {RESUME_C}C). "
                f"Aborted {reason}. Try again later. {status_line()}"
            )
        print(f"[aubie thermal] still {t}C after {elapsed}s ? waiting...", flush=True)
