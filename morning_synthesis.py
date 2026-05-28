"""
morning_synthesis.py v4 — AUBIEETERNAL Integrated Morning Synthesis
Runs: daily at 6AM automatically + manually any time via --force
Integrates: synthesis + humanity mapper + certifications + AI honesty + epistemic commons + living lattice
$0.00 cost — runs on local Ollama
"""
import os, sys, json, datetime, requests, argparse, subprocess
from pathlib import Path

# ── Path resolution ────────────────────────────────────────────────────────────
def _resolve():
    import socket
    try:
        socket.gethostbyname("ollama.startos")
        return Path("/mnt/main")
    except Exception:
        pass
    p = Path(os.path.expanduser("~/.aubieeternal/main"))
    p.mkdir(parents=True, exist_ok=True)
    return p

WORK_DIR      = _resolve() / "repo"
INSIGHTS_DIR  = WORK_DIR / "insights" / "daily"
INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)

def _ollama_url():
    import socket
    try:
        socket.gethostbyname("ollama.startos")
        return "http://ollama.startos:11434/v1/chat/completions"
    except Exception:
        return "http://localhost:11434/v1/chat/completions"

OLLAMA_MODEL   = os.environ.get("AUBIE_MODEL", "qwen2.5:14b")
OLLAMA_TIMEOUT = 300
TRUTH_LOG      = WORK_DIR / "master_truth_log.jsonl"
TIER2_DIGEST   = WORK_DIR / "tier2_digest.txt"
SWARM_STATUS   = _resolve() / "swarm_status.json"

# Track last run in memory (for swarm loop)
_last_synthesis_date = None


def maybe_trigger_morning_synthesis():
    """
    Call this from the swarm main loop every tick.
    Fires at 6AM — but with a 90-minute window so it never misses a tick.
    """
    global _last_synthesis_date
    now   = datetime.datetime.now()
    today = now.date().isoformat()
    # Fire between 6:00 and 7:30 AM, once per day
    if 6 <= now.hour < 8 and _last_synthesis_date != today:
        _last_synthesis_date = today
        print(f"[synthesis] ⏰ 6AM trigger fired for {today}")
        run_full_synthesis()
    # Also fire if it's past 7:30 and still hasn't run today (recovery)
    elif now.hour >= 8 and _last_synthesis_date != today:
        today_path = INSIGHTS_DIR / f"{today}.md"
        if not today_path.exists():
            _last_synthesis_date = today
            print(f"[synthesis] 🔄 Recovery trigger — synthesis missed, running now")
            run_full_synthesis()


def run_full_synthesis(force=False):
    today    = datetime.date.today().isoformat()
    out_path = INSIGHTS_DIR / f"{today}.md"
    if out_path.exists() and not force:
        print(f"[synthesis] Already ran today ({today})")
        return {"status": "already_ran", "date": today}

    print(f"[synthesis] 🌅 Running integrated morning synthesis v4 for {today}...")

    # ── Get digest ──────────────────────────────────────────────────────────
    digest = ""
    if TIER2_DIGEST.exists():
        digest = TIER2_DIGEST.read_text()[:3000]
    elif TRUTH_LOG.exists():
        lines = TRUTH_LOG.read_text().strip().split("\n")
        tier2 = []
        for line in reversed(lines[-100:]):
            try:
                e = json.loads(line)
                if e.get("tier") == 2 and e.get("result") and len(e["result"]) > 50:
                    tier2.append(f"{e.get('daughter','?')}: {e['result'][:200]}")
                    if len(tier2) >= 10: break
            except: pass
        digest = "\n\n".join(reversed(tier2))

    if not digest:
        # Use any recent truth log entries as fallback
        if TRUTH_LOG.exists():
            lines = TRUTH_LOG.read_text().strip().split("\n")
            any_entries = []
            for line in reversed(lines[-50:]):
                try:
                    e = json.loads(line)
                    if e.get("result") and len(e["result"]) > 30:
                        any_entries.append(e["result"][:150])
                        if len(any_entries) >= 5: break
                except: pass
            digest = "\n".join(any_entries)

    if not digest:
        digest = "No swarm output available yet. Synthesis will be brief."

    # ── Swarm status ────────────────────────────────────────────────────────
    swarm_status = {}
    if SWARM_STATUS.exists():
        try: swarm_status = json.loads(SWARM_STATUS.read_text())
        except: pass
    wonder = swarm_status.get("wonder_index", 1.0)
    coh    = swarm_status.get("inter_rune_coherence", 1.0)
    mets   = swarm_status.get("mets", 0)
    grok_n = swarm_status.get("grokipedia_count", 0)

    # ── Core synthesis ──────────────────────────────────────────────────────
    synthesis = _call_ollama(f"""Synthesize the 3 most important insights from this AUBIEETERNAL swarm output.
Today: {today} | Wonder: {wonder:.4f} | Coherence: {coh:.6f} | METS: {mets:,}

{digest}

For each insight: state it clearly, what it implies for epistemic families, one action today.
End with one sentence on what this means for humanity's collective intelligence.
Be direct, honest, and non-extractive. Max 300 words total.""")

    if not synthesis:
        synthesis = (f"Ollama not available for synthesis. "
                     f"Swarm status: Wonder {wonder:.4f} | Coherence {coh:.6f} | METS {mets:,}\n"
                     f"Latest digest entries logged but synthesis skipped — check Ollama at {_ollama_url()}")

    # ── Humanity Impact ─────────────────────────────────────────────────────
    humanity_summary = ""
    try:
        sys.path.insert(0, str(WORK_DIR))
        from humanity_impact import HumanityImpactMapper
        mapper = HumanityImpactMapper()
        result = mapper.run_mapping_cycle()
        h = mapper.get_impact_summary(1)
        humanity_summary = (
            f"**Insights mapped:** {h.get('total_mappings', 0)}  \n"
            f"**Top domain:** {h.get('top_domain', 'none')}  \n"
            f"**Global-scale:** {h.get('global_insights', 0)}"
        )
    except Exception as e:
        humanity_summary = f"*(Humanity mapper: {e})*"

    # ── Epistemic Commons ────────────────────────────────────────────────────
    commons_summary = ""
    try:
        from epistemic_commons import EpistemicCommons
        commons = EpistemicCommons()
        result  = commons.run_daily_publish()
        status  = result.get("status", "unknown")
        if status in ("published", "already_published"):
            url = f"https://github.com/hodlmateo/AUBIEETERNAL/blob/main/epistemic_commons/daily/{today}.md"
            ctx = "https://raw.githubusercontent.com/hodlmateo/AUBIEETERNAL/main/epistemic_commons/ai_context/latest.txt"
            commons_summary = (
                f"**Status:** ✅ {'Published' if status == 'published' else 'Already published'}  \n"
                f"**Seeds:** {result.get('seeds', 0)} · **Steelmans:** {result.get('steelmans', 0)}  \n"
                f"**AI URL:** `{ctx}`"
            )
        else:
            commons_summary = f"*(Commons: {status})*"
    except Exception as e:
        commons_summary = f"*(Epistemic Commons: {e})*"

    # ── Living Lattice ────────────────────────────────────────────────────────
    lattice_summary = ""
    try:
        from living_lattice import LivingLattice
        lattice = LivingLattice()
        result  = lattice.publish_daily_signal()
        stats   = lattice.get_lattice_summary().get("stats", {})
        lattice_summary = (
            f"**Status:** {'✅ Published' if result.get('status') == 'published' else '✅ Already published'}  \n"
            f"**Wisdom GDP:** {stats.get('wisdom_gdp', 0):.2f}/10  \n"
            f"**Avg Coherence (30d):** {stats.get('avg_coherence_30d', 0):.4f}  \n"
            f"**Trend:** {stats.get('trend', 'insufficient data').title()}"
        )
    except Exception as e:
        lattice_summary = f"*(Living Lattice: {e})*"

    # ── Certifications ───────────────────────────────────────────────────────
    cert_summary = ""
    try:
        from sovereign_certification import CertificationEngine
        from family_profiles import FamilyAuth
        engine = CertificationEngine()
        auth   = FamilyAuth()
        new_certs = []
        for fam in auth.list_families():
            newly = engine.check_and_award(fam["family_id"])
            for cert in newly:
                new_certs.append(f"{fam['display_name']}: {cert['emoji']} {cert['title']}")
        cert_summary = (
            "**New Certifications:**\n" + "\n".join(f"- {c}" for c in new_certs)
        ) if new_certs else "No new certifications today."
    except Exception as e:
        cert_summary = f"*(Certification check: {e})*"

    # ── AI Honesty Stats ──────────────────────────────────────────────────────
    honesty_summary = ""
    try:
        from ai_honesty import HonestyLayer
        stats = HonestyLayer().get_swarm_honesty_stats(100)
        if stats.get("total", 0) > 0:
            honesty_summary = (
                f"**Outputs scored:** {stats['total']}  \n"
                f"**Avg confidence:** {stats['avg_confidence']:.3f}  \n"
                f"**High-risk:** {stats['high_risk_pct']:.1f}%  \n"
                f"**Honest AI score:** {stats.get('honest_ai_score', 0):.3f}"
            )
        else:
            honesty_summary = "No scored outputs yet today."
    except Exception as e:
        honesty_summary = f"*(Honesty layer: {e})*"

    # ── Build report ─────────────────────────────────────────────────────────
    report = f"""# AUBIEETERNAL Morning Synthesis — {today}

**Wonder:** {wonder:.4f} | **Coherence:** {coh:.6f} | **METS:** {mets:,} | **Grokipedia:** {grok_n}/256

---

## Daily Synthesis

{synthesis}

---

## Humanity Impact

{humanity_summary}

---

## Epistemic Commons 🌐

{commons_summary}

---

## Simulation Probe 🔭

{probe_summary}

---

## Living Lattice 🕸️

{lattice_summary}

---

## Sovereign Certifications

{cert_summary}

---

## AI Honesty Report

{honesty_summary}

---

*AUBIEETERNAL Morning Synthesis v4 — War Eagle Eternal 🦅❤️*
*Loop: Swarm → Honesty-Score → Digest → Synthesis → Commons → Lattice → GitHub — Forever*
*Daily Cost: $0.00 | Stack: StartOS + Ollama + {OLLAMA_MODEL}*
"""
    out_path.write_text(report)
    print(f"[synthesis] ✅ Written: {out_path}")
    _git_push(today)
    return {"status": "complete", "date": today, "path": str(out_path)}


def _call_ollama(prompt):
    try:
        r = requests.post(
            _ollama_url(),
            json={"model": OLLAMA_MODEL,
                  "messages": [{"role": "user", "content": prompt}],
                  "stream": False, "temperature": 0.7},
            timeout=OLLAMA_TIMEOUT,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[synthesis] Ollama error: {e}")
    return ""


def _git_push(date):
    repo = WORK_DIR
    try:
        subprocess.run(["git", "add", "insights/", "epistemic_commons/", "lattice/"],
                       cwd=repo, capture_output=True)
        subprocess.run(["git", "commit", "-m",
                        f"Morning synthesis {date} | v4 integrated"],
                       cwd=repo, capture_output=True)
        subprocess.run(["git", "push"], cwd=repo, capture_output=True)
        print("[synthesis] ✅ Pushed to GitHub")
    except Exception as e:
        print(f"[synthesis] Git error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AUBIEETERNAL Morning Synthesis")
    parser.add_argument("--force", action="store_true",
                        help="Force run even if already ran today")
    args = parser.parse_args()
    result = run_full_synthesis(force=args.force)
    print(f"\nResult: {result}")
