"""
morning_synthesis.py v5 — AUBIEETERNAL Integrated Morning Synthesis
Fixed version with proper Simulation Probe + Rune Memory integration
"""

import os, sys, json, datetime, requests, argparse, subprocess
from pathlib import Path

# ── Path resolution ───────────────────────────────────────────────────────────
def _resolve():
    import socket
    try:
        socket.gethostbyname("localhost")
        return Path("/mnt/main")
    except Exception:
        p = Path(os.path.expanduser("~/.aubieeternal/main"))
        p.mkdir(parents=True, exist_ok=True)
        return p

WORK_DIR      = _resolve() / "repo"
INSIGHTS_DIR  = WORK_DIR / "insights" / "daily"
INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)

def _ollama_url():
    import socket
    try:
        socket.gethostbyname("localhost")
        return "http://localhost:11434/v1/chat/completions"
    except Exception:
        return "http://localhost:11434/v1/chat/completions"

OLLAMA_MODEL   = os.environ.get("AUBIE_MODEL", "qwen2.5:7b")
OLLAMA_TIMEOUT = 1200   # 20 min — synthesis runs in a background daemon thread (non-blocking),
                        # so a long, patient timeout is safe and lets a cold CPU model finish.
TRUTH_LOG      = WORK_DIR / "master_truth_log.jsonl"
TIER2_DIGEST   = WORK_DIR / "tier2_digest.txt"
SWARM_STATUS   = _resolve() / "swarm_status.json"

_last_synthesis_date = None


# ── Import new modules ────────────────────────────────────────────────────────
try:
    from simulation_probe import SimulationProbe
    from rune_memory import RuneMemory, ShieldRune, auto_seal_high_coherence
    HAS_PROBE_AND_RUNE = True
except Exception:
    HAS_PROBE_AND_RUNE = False


def run_full_synthesis(force=False):
    today    = datetime.date.today().isoformat()
    out_path = INSIGHTS_DIR / f"{today}.md"
    if out_path.exists() and not force:
        print(f"[synthesis] Already ran today ({today})")
        return {"status": "already_ran", "date": today}

    print(f"[synthesis] 🌅 Running morning synthesis v5 for {today}...")

    # ── Get digest ──────────────────────────────────────────────────────────
    digest = ""
    if TIER2_DIGEST.exists():
        digest = TIER2_DIGEST.read_text()[:3000]

    if not digest:
        digest = "No recent swarm output available."

    # ── Swarm status ────────────────────────────────────────────────────────
    swarm_status = {}
    if SWARM_STATUS.exists():
        try:
            swarm_status = json.loads(SWARM_STATUS.read_text())
        except:
            pass

    wonder = swarm_status.get("wonder_index", 1.0)
    coh    = swarm_status.get("inter_rune_coherence", 1.0)
    mets   = swarm_status.get("mets", 0)
    grok_n = swarm_status.get("grokipedia_count", 0)

    # ── Core Synthesis ──────────────────────────────────────────────────────
    synthesis = _call_ollama(f"""Synthesize the 3 most important insights from this AUBIEETERNAL swarm output.
Today: {today} | Wonder: {wonder:.4f} | Coherence: {coh:.6f} | METS: {mets:,}

{digest}

For each insight: state it clearly + one action for epistemic families.
Be direct and honest. Max 280 words.""")

    if not synthesis:
        synthesis = f"Swarm status: Wonder {wonder:.4f} | Coherence {coh:.6f} | METS {mets:,}"

    # ── Simulation Probe 🔭 ─────────────────────────────────────────────────
    probe_summary = ""
    if HAS_PROBE_AND_RUNE:
        try:
            probe = SimulationProbe()
            report = probe.run_daily_probe()
            score = report.get("probe_score", 0)
            integrity = report.get("lattice_integrity", {}).get("note", "")
            anomalies = report.get("coherence_anomalies", {}).get("anomaly_count", 0)
            probe_summary = f"**Probe Score:** {score}/10\n**Integrity:** {integrity}\n**Anomalies:** {anomalies}"
        except Exception as e:
            probe_summary = f"*(Simulation Probe: {e})*"
    else:
        probe_summary = "Simulation Probe module not loaded."

    # ── Rune Memory 🛡️ ──────────────────────────────────────────────────────
    rune_summary = ""
    if HAS_PROBE_AND_RUNE:
        try:
            sealed_today = auto_seal_high_coherence(threshold=0.88)
            mem = RuneMemory()
            stats = mem.get_stats()
            shield = ShieldRune()
            shield_status = shield.get_status()

            rune_summary = (
                f"**Memories:** {stats.get('total', 0)} | **Sealed:** {stats.get('sealed', 0)}\n"
                f"**Today's seals:** {shield_status.get('today_seals', 0)}\n"
                f"**Pending merges:** {stats.get('pending_merges', 0)}"
            )
            if sealed_today:
                rune_summary += f"\n**Auto-sealed high-coherence entries:** {len(sealed_today)}"
        except Exception as e:
            rune_summary = f"*(Rune Memory: {e})*"
    else:
        rune_summary = "Rune Memory module not loaded."

    # ── Build final report ──────────────────────────────────────────────────
    report = f"""# AUBIEETERNAL Morning Synthesis — {today}

**Wonder:** {wonder:.4f} | **Coherence:** {coh:.6f} | **METS:** {mets:,}

## Daily Synthesis
{synthesis}

## Simulation Probe 🔭
{probe_summary}

## Rune Memory 🛡️
{rune_summary}

*AUBIEETERNAL v5 — War Eagle Eternal 🦅*
"""
    out_path.write_text(report)
    print(f"[synthesis] ✅ Written: {out_path}")
    return {"status": "complete", "date": today, "path": str(out_path)}


def _call_ollama(prompt):
    try:
        r = requests.post(
            _ollama_url(),
            json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False, "keep_alive": "30m"},
            timeout=OLLAMA_TIMEOUT,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[synthesis] Ollama error: {e}")
    return ""


# ── Alias for the swarm ───────────────────────────────────────────────────────
# swarm_v4_1.py imports `run_morning_synthesis`; v5 renamed the function to
# run_full_synthesis. This alias restores the expected name so the 6AM auto-trigger
# import stops failing with ImportError. (This is the bug that killed the auto-sync.)
run_morning_synthesis = run_full_synthesis


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = run_full_synthesis(force=args.force)
    print(result)
