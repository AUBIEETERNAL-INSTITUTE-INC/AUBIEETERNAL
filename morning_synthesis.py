"""
morning_synthesis.py v3 — AUBIEETERNAL Integrated Morning Synthesis
Integrates: synthesis + humanity mapper + certifications + AI honesty + EPISTEMIC COMMONS
$0.00 cost — runs on local Ollama
"""
import os, sys, json, datetime, requests, argparse
from pathlib import Path

WORK_DIR       = Path("/mnt/main/repo")
INSIGHTS_DIR   = WORK_DIR / "insights" / "daily"
INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
OLLAMA_URL     = "http://ollama.startos:11434/v1/chat/completions"
OLLAMA_MODEL   = "qwen2.5:32b"
OLLAMA_TIMEOUT = 300
TRUTH_LOG      = WORK_DIR / "master_truth_log.jsonl"
TIER2_DIGEST   = WORK_DIR / "tier2_digest.txt"
SWARM_STATUS   = Path("/mnt/main/swarm_status.json")
_last_synthesis_date = None


def maybe_trigger_morning_synthesis():
    global _last_synthesis_date
    now = datetime.datetime.now()
    today = now.date().isoformat()
    if now.hour == 6 and _last_synthesis_date != today:
        _last_synthesis_date = today
        run_full_synthesis()


def run_full_synthesis(force=False):
    today    = datetime.date.today().isoformat()
    out_path = INSIGHTS_DIR / f"{today}.md"
    if out_path.exists() and not force:
        print(f"[synthesis] Already ran today ({today})"); return

    print(f"[synthesis] 🌅 Running integrated morning synthesis v3 for {today}...")

    # ── Get digest ────────────────────────────────────────────────────────────
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
        print("[synthesis] No digest available yet"); return

    # ── Swarm status ──────────────────────────────────────────────────────────
    swarm_status = {}
    if SWARM_STATUS.exists():
        try: swarm_status = json.loads(SWARM_STATUS.read_text())
        except: pass
    wonder = swarm_status.get("wonder_index", 1.0)
    coh    = swarm_status.get("inter_rune_coherence", 1.0)
    mets   = swarm_status.get("mets", 0)
    grok_ct= swarm_status.get("grokipedia_count", 0)

    # ── Core synthesis ────────────────────────────────────────────────────────
    synthesis = _call_ollama(f"""Synthesize the 3 most important insights from this AUBIEETERNAL swarm output.
Today: {today} | Wonder: {wonder:.4f} | Coherence: {coh:.6f}

{digest}

For each insight: state it clearly, what it implies for epistemic families, one action today.
End with one sentence on what this means for humanity's collective intelligence.
Be direct and non-extractive.""")
    if not synthesis:
        print("[synthesis] Ollama not responding"); return

    # ── Humanity Impact ───────────────────────────────────────────────────────
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
            f"**Global-scale insights:** {h.get('global_insights', 0)}"
        )
    except Exception as e:
        humanity_summary = f"*(Humanity mapper: {e})*"

    # ── Certifications ────────────────────────────────────────────────────────
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
            claim_breakdown = " · ".join(
                f"{k}: {v}" for k, v in stats.get("claim_types", {}).items()
            )
            honesty_summary = (
                f"**Outputs scored:** {stats['total']}  \n"
                f"**Avg confidence:** {stats['avg_confidence']:.3f}  \n"
                f"**High-risk:** {stats['high_risk_pct']:.1f}%  \n"
                f"**Need verification:** {stats.get('need_verification', 0)}  \n"
                f"**Honest AI score:** {stats.get('honest_ai_score', 0):.3f}  \n"
                f"**Claim types:** {claim_breakdown}"
            )
        else:
            honesty_summary = "No scored outputs yet."
    except Exception as e:
        honesty_summary = f"*(Honesty layer: {e})*"

    # ── Epistemic Commons ─────────────────────────────────────────────────────
    commons_summary = ""
    try:
        from epistemic_commons import EpistemicCommons
        commons = EpistemicCommons()
        result  = commons.run_daily_publish()
        status  = result.get("status", "unknown")
        if status in ("published", "already_published"):
            seeds_n = result.get("seeds", 0)
            steel_n = result.get("steelmans", 0)
            url     = f"https://github.com/hodlmateo/AUBIEETERNAL/blob/main/epistemic_commons/daily/{today}.md"
            ctx_url = "https://raw.githubusercontent.com/hodlmateo/AUBIEETERNAL/main/epistemic_commons/ai_context/latest.txt"
            commons_summary = (
                f"**Status:** {'✅ Published' if status == 'published' else '✅ Already published'}  \n"
                f"**Seeds:** {seeds_n} · **Steelmans:** {steel_n}  \n"
                f"**Today's Commons:** [{today}.md]({url})  \n"
                f"**AI Context URL (any AI can fetch this):**  \n"
                f"`{ctx_url}`"
            )
        else:
            commons_summary = f"*(Commons: {status})*"
    except Exception as e:
        commons_summary = f"*(Epistemic Commons: {e})*"

    # ── Build report ──────────────────────────────────────────────────────────
    report = f"""# AUBIEETERNAL Morning Synthesis — {today}

**Wonder:** {wonder:.4f} | **Coherence:** {coh:.6f} | **METS:** {mets:,} | **Grokipedia:** {grok_ct}/256

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

## Sovereign Certifications

{cert_summary}

---

## AI Honesty Report

{honesty_summary}

---

*AUBIEETERNAL Morning Synthesis v3 — War Eagle Eternal 🦅❤️*
*Loop: Swarm → Honesty-Score → Digest → Synthesis → Humanity → Commons → GitHub — Forever*
*Daily Cost: $0.00 | Stack: StartOS + Ollama + qwen2.5:32b*
"""
    out_path.write_text(report)
    print(f"[synthesis] ✅ Written: {out_path}")
    _git_push(today)


def _call_ollama(prompt):
    try:
        r = requests.post(
            OLLAMA_URL,
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
    import subprocess
    repo = Path("/mnt/main/repo")
    try:
        subprocess.run(["git", "add", "insights/", "epistemic_commons/"],
                       cwd=repo, capture_output=True)
        subprocess.run(["git", "commit", "-m",
                        f"Morning synthesis + commons {date} | v3"],
                       cwd=repo, capture_output=True)
        subprocess.run(["git", "push"], cwd=repo, capture_output=True)
        print("[synthesis] ✅ Pushed to GitHub")
    except Exception as e:
        print(f"[synthesis] Git error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run_full_synthesis(force=args.force)
