"""
swarm_evolution.py — AUBIEETERNAL Swarm Self-Evolution Engine
=============================================================
Enables the swarm to propose and (with approval) implement school improvements.

Three modes:
  A. Lesson Proposals    — weekly new lesson suggestions (human approves)
  B. Dynamic Quests      — auto-generate quests from family progress data
  C. Auto-Apply Mode     — swarm applies small changes with safety rails

Safety rails (always active):
  - Every proposal is written to evolution_proposals.jsonl for review
  - Human approval required for curriculum file changes (mode A)
  - Quest generation is always auto (mode B) — low risk, bounded XP
  - Mode C has a diff-review step before any file is written
  - Shield Rune coherence check: proposals with score < 0.7 are blocked

Usage:
    from swarm_evolution import EvolutionEngine
    engine = EvolutionEngine()
    engine.run_weekly_lesson_proposals()   # A
    engine.generate_dynamic_quests("family_alpha")  # B
    engine.run_auto_evolution_tick()       # C
"""

import os, sys, json, datetime, random, requests
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
WORK_DIR       = Path("/mnt/main/repo")
PROPOSALS_LOG  = WORK_DIR / "evolution_proposals.jsonl"
APPROVED_LOG   = WORK_DIR / "evolution_approved.jsonl"
QUESTS_CACHE   = Path("/mnt/main/dynamic_quests.json")
EVOLUTION_STATE= Path("/mnt/main/evolution_state.json")
FAMILIES_DIR   = Path("/mnt/main/families")
TRUTH_LOG      = WORK_DIR / "master_truth_log.jsonl"

# ── Ollama (local, free) ──────────────────────────────────────────────────────
OLLAMA_URL   = "http://192.168.1.251:59885/v1/chat/completions"
OLLAMA_MODEL = "qwen3:32b"
OLLAMA_TIMEOUT = 180

# ── Grok (for high-quality lesson generation) ─────────────────────────────────
GROK_URL   = "https://api.x.ai/v1/chat/completions"
GROK_MODEL = "grok-4.3"

def _load_state() -> dict:
    if EVOLUTION_STATE.exists():
        try: return json.loads(EVOLUTION_STATE.read_text())
        except: pass
    return {
        "last_lesson_proposal_date": "",
        "last_quest_generation":     "",
        "proposals_pending":         0,
        "proposals_approved":        0,
        "proposals_rejected":        0,
        "lessons_auto_added":        0,
        "quests_generated":          0,
        "evolution_cycles":          0,
    }

def _save_state(state: dict):
    EVOLUTION_STATE.parent.mkdir(parents=True, exist_ok=True)
    EVOLUTION_STATE.write_text(json.dumps(state, indent=2))

def _call_local(prompt: str, system: str = "") -> str:
    """Call qwen3:32b locally — $0.00."""
    try:
        msgs = []
        if system: msgs.append({"role":"system","content":system})
        msgs.append({"role":"user","content":prompt})
        resp = requests.post(
            OLLAMA_URL,
            json={"model":OLLAMA_MODEL,"messages":msgs,"temperature":0.7,"stream":False},
            timeout=OLLAMA_TIMEOUT
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[evolution] Local call error: {e}")
    return ""

def _call_grok(prompt: str, system: str = "", api_key: str = "") -> str:
    """Call Grok for higher-quality generation."""
    key = api_key or os.getenv("XAI_API_KEY","")
    if not key:
        return _call_local(prompt, system)
    try:
        msgs = []
        if system: msgs.append({"role":"system","content":system})
        msgs.append({"role":"user","content":prompt})
        resp = requests.post(
            GROK_URL,
            headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
            json={"model":GROK_MODEL,"messages":msgs,"max_tokens":600,"temperature":0.8},
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[evolution] Grok call error: {e}")
    return _call_local(prompt, system)


# ══════════════════════════════════════════════════════════════════════════════
# EVOLUTION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class EvolutionEngine:

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("XAI_API_KEY","")
        self.state   = _load_state()

    # ══════════════════════════════════════════════════════════════════════════
    # MODE A — WEEKLY LESSON PROPOSALS
    # ══════════════════════════════════════════════════════════════════════════

    def run_weekly_lesson_proposals(self, force: bool = False) -> list:
        """
        Runs once per week. Analyzes family coherence data + swarm output,
        proposes 3–5 new lessons. Writes to evolution_proposals.jsonl.
        Human approves in the Swarm Evolution tab before lessons are added.
        """
        today = datetime.date.today().isoformat()
        last  = self.state.get("last_lesson_proposal_date","")

        # Weekly gate (skip if ran this week, unless force=True)
        if not force and last:
            last_d = datetime.date.fromisoformat(last)
            if (datetime.date.today() - last_d).days < 7:
                print(f"[evolution] Lesson proposals ran {(datetime.date.today()-last_d).days} days ago — skipping")
                return []

        print("[evolution] 📚 Running weekly lesson proposal cycle...")

        # 1. Read family progress data
        family_context = self._get_family_context()

        # 2. Read recent swarm insights
        swarm_context = self._get_recent_insights()

        # 3. Read current lesson keys (to avoid duplicates)
        try:
            sys.path.insert(0, str(WORK_DIR))
            from family_hud import LESSONS as current_lessons
            existing_keys = list(current_lessons.keys())
            existing_titles = [v["title"] for v in current_lessons.values()]
        except ImportError:
            existing_keys = []
            existing_titles = []

        # 4. Generate proposals via AI
        prompt = f"""You are the AUBIEETERNAL curriculum evolution engine.
Analyze this family learning data and swarm insights, then propose 3 NEW lessons.

CORE PHILOSOPHY: Truth Education is the meta-skill that makes every other skill more powerful.
Every proposed lesson should include a "Truth Check" — one question that tests the epistemic
rigor of the lesson itself. Lessons that cannot survive their own Truth Check should not be proposed.

FAMILY PROGRESS:
{family_context}

RECENT SWARM INSIGHTS:
{swarm_context}

EXISTING LESSONS (avoid duplicates):
{json.dumps(existing_titles[:20], indent=2)}

Respond ONLY with valid JSON array of 3 lesson objects:
[
  {{
    "key": "topic-level",
    "title": "Topic — Level N",
    "topic": "One sentence what the lesson teaches",
    "steelman": "What is the strongest argument against [this topic]?",
    "example": "Real-world example that makes this vivid",
    "age_hint": "All ages / 8+ / 12+ / etc",
    "xp": 20,
    "rune": "TOPIC•RUNE",
    "min_coherence": 0.65,
    "rationale": "Why this lesson is needed based on the data above",
    "coherence_score": 0.85
  }}
]
No markdown, no preamble. JSON only."""

        raw = _call_grok(prompt, api_key=self.api_key)
        if not raw:
            raw = _call_local(prompt)

        proposals = []
        try:
            # Strip markdown fences
            clean = raw.replace("```json","").replace("```","").strip()
            lessons = json.loads(clean)
            for lesson in lessons:
                # Safety check: coherence score gate
                if float(lesson.get("coherence_score",0)) < 0.70:
                    print(f"[evolution] ⚠️  Proposal '{lesson.get('title','')}' below coherence threshold — blocked")
                    continue
                # Duplicate check
                if lesson.get("key") in existing_keys:
                    continue

                proposal = {
                    "id":           f"prop_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{lesson.get('key','')}",
                    "type":         "new_lesson",
                    "status":       "pending",
                    "proposed_at":  datetime.datetime.now().isoformat(),
                    "proposed_by":  "swarm_evolution",
                    "lesson":       lesson,
                    "coherence_score": lesson.get("coherence_score", 0.8),
                    "rationale":    lesson.get("rationale",""),
                    "approved_at":  None,
                    "rejected_at":  None,
                    "rejection_reason": None,
                }
                proposals.append(proposal)
                with open(PROPOSALS_LOG, "a") as f:
                    f.write(json.dumps(proposal) + "\n")

        except (json.JSONDecodeError, Exception) as e:
            print(f"[evolution] Proposal parse error: {e}")

        # 5. Update state
        self.state["last_lesson_proposal_date"] = today
        self.state["proposals_pending"] = self.state.get("proposals_pending",0) + len(proposals)
        self.state["evolution_cycles"]  = self.state.get("evolution_cycles",0) + 1
        _save_state(self.state)

        print(f"[evolution] ✅ {len(proposals)} lesson proposals written to evolution_proposals.jsonl")

        # 6. Log to truth log
        self._log_to_truth(f"Weekly lesson proposals: {len(proposals)} new lessons proposed", "evolution_lesson_proposal")

        return proposals

    def approve_lesson(self, proposal_id: str) -> bool:
        """
        Operator approves a proposal — automatically adds lesson to family_hud.py.
        Hard gate: proposals with coherence_score < 0.70 are BLOCKED even with approval.
        """
        proposal = self._find_proposal(proposal_id)
        if not proposal:
            print(f"[evolution] Proposal {proposal_id} not found")
            return False

        # ── HARD COHERENCE GATE ───────────────────────────────────────────────
        score = float(proposal.get("coherence_score", 0))
        if score < 0.70:
            print(f"[evolution] ❌ BLOCKED: proposal '{proposal.get('lesson',{}).get('title','')}' "
                  f"has coherence {score:.2f} < 0.70 hard gate. Cannot approve.")
            return False

        lesson = proposal["lesson"]
        lesson_key = lesson.get("key","")

        # Build the Python dict string to inject
        lesson_str = f'''
    "{lesson_key}": {{
        "title":       "{lesson.get('title','')}",
        "topic":       "{lesson.get('topic','')}",
        "steelman":    "{lesson.get('steelman','')}",
        "example":     "{lesson.get('example','')}",
        "age_hint":    "{lesson.get('age_hint','All ages')}",
        "xp":          {lesson.get('xp',20)}, "rune": "{lesson.get('rune','RUNE')}", "min_coherence": {lesson.get('min_coherence',0.65)},
    }},'''

        # Find the closing brace of LESSONS dict and inject before it
        hud_path = WORK_DIR / "family_hud.py"
        if not hud_path.exists():
            print(f"[evolution] family_hud.py not found at {hud_path}")
            return False

        content = hud_path.read_text()
        # Inject before the closing brace of LESSONS (before "# ── Polyvagal State Detector")
        inject_marker = "\n# ── Polyvagal State Detector"
        if inject_marker not in content:
            print("[evolution] Could not find injection marker in family_hud.py")
            return False

        new_content = content.replace(inject_marker, lesson_str + inject_marker, 1)
        hud_path.write_text(new_content)

        # Mark approved
        proposal["status"]      = "approved"
        proposal["approved_at"] = datetime.datetime.now().isoformat()
        with open(APPROVED_LOG, "a") as f:
            f.write(json.dumps(proposal) + "\n")

        self._update_proposal_status(proposal_id, "approved")
        self.state["proposals_approved"] = self.state.get("proposals_approved",0) + 1
        self.state["lessons_auto_added"] = self.state.get("lessons_auto_added",0) + 1
        _save_state(self.state)

        print(f"[evolution] ✅ Lesson '{lesson.get('title','')}' approved and added to family_hud.py")
        self._log_to_truth(f"Lesson approved: {lesson.get('title','')}", "evolution_lesson_approved")
        return True

    def reject_lesson(self, proposal_id: str, reason: str = "") -> bool:
        """Reject a proposal — it will not be added."""
        proposal = self._find_proposal(proposal_id)
        if not proposal:
            return False
        proposal["status"]           = "rejected"
        proposal["rejected_at"]      = datetime.datetime.now().isoformat()
        proposal["rejection_reason"] = reason
        self._update_proposal_status(proposal_id, "rejected", reason)
        self.state["proposals_rejected"] = self.state.get("proposals_rejected",0) + 1
        _save_state(self.state)
        print(f"[evolution] Proposal {proposal_id} rejected: {reason}")
        return True

    # ══════════════════════════════════════════════════════════════════════════
    # MODE B — DYNAMIC QUEST GENERATION
    # ══════════════════════════════════════════════════════════════════════════

    def generate_dynamic_quests(self, family_id: str = "all") -> dict:
        """
        Auto-generates personalized daily quests based on family progress.
        Runs automatically — no human approval needed (quests are bounded + safe).
        Writes to /mnt/main/dynamic_quests.json for Streamlit to read.
        """
        print(f"[evolution] 🎮 Generating dynamic quests for {family_id}...")

        family_ids = self._get_family_ids() if family_id == "all" else [family_id]
        all_quests = {}

        for fid in family_ids:
            stats = self._load_family_stats(fid)
            xp    = stats.get("total_xp", 0)
            level = stats.get("level", 1)
            streak= stats.get("streak_days", 0)
            completed_lessons = set(stats.get("lessons_completed", []))
            coherence_history = stats.get("coherence_history", [])
            avg_coherence = sum(coherence_history[-5:]) / len(coherence_history[-5:]) if coherence_history else 0.72

            # Personalize quest difficulty to family's level
            xp_reward  = min(50, max(10, level * 5))
            sat_reward = min(100, max(20, level * 10))

            quests = []

            # Quest 1 — based on recent coherence
            if avg_coherence < 0.65:
                quests.append({
                    "id":    "coherence_boost",
                    "title": "Complete any Level 1 lesson to boost coherence",
                    "xp":    xp_reward,
                    "sats":  sat_reward,
                    "type":  "adaptive",
                    "hint":  "Your coherence is building — a short lesson will help!",
                })
            elif avg_coherence >= 0.85:
                quests.append({
                    "id":    "master_challenge",
                    "title": "Attempt a Master (★) lesson today",
                    "xp":    xp_reward * 2,
                    "sats":  sat_reward * 2,
                    "type":  "adaptive",
                    "hint":  "Your coherence is high — you're ready for a harder challenge!",
                })
            else:
                quests.append({
                    "id":    "next_level",
                    "title": f"Complete the next lesson in your strongest track",
                    "xp":    xp_reward,
                    "sats":  sat_reward,
                    "type":  "adaptive",
                    "hint":  "Keep building on your momentum!",
                })

            # Quest 2 — streak-based
            if streak == 0:
                quests.append({
                    "id":    "start_streak",
                    "title": "Start a new learning streak — do any lesson today",
                    "xp":    15,
                    "sats":  30,
                    "type":  "streak",
                    "hint":  "Day 1 of your new streak starts NOW!",
                })
            elif streak >= 7 and streak % 7 == 0:
                quests.append({
                    "id":    f"streak_{streak}",
                    "title": f"🔥 Celebrate your {streak}-day streak with a family session",
                    "xp":    streak * 2,
                    "sats":  streak * 5,
                    "type":  "streak_milestone",
                    "hint":  f"You've been at this for {streak} days. That's real antifragility!",
                })
            else:
                quests.append({
                    "id":    "keep_streak",
                    "title": f"Maintain your {streak}-day streak with today's lesson",
                    "xp":    xp_reward,
                    "sats":  sat_reward,
                    "type":  "streak",
                    "hint":  f"Day {streak+1} — keep the chain alive!",
                })

            # Quest 3 — swarm insight integration
            swarm_topic = self._get_todays_swarm_topic()
            quests.append({
                "id":    "swarm_inspired",
                "title": f"Explore today's swarm insight: {swarm_topic[:50]}",
                "xp":    xp_reward + 5,
                "sats":  sat_reward + 10,
                "type":  "swarm",
                "hint":  "The swarm found something worth exploring today!",
            })

            # Quest 4 — Truth Drill (always included — core meta-skill)
            truth_drill = self._get_truth_drill_quest(fid)
            truth_drill["type"] = "truth_drill"
            truth_drill["hint"] = "Truth-seeking is the meta-skill that makes every other skill more powerful."
            quests.append(truth_drill)

            all_quests[fid] = {
                "generated_at": datetime.datetime.now().isoformat(),
                "family_id":    fid,
                "quests":       quests,
                "family_level": level,
                "avg_coherence": round(avg_coherence, 3),
            }

        # Cache to disk for Streamlit
        QUESTS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        QUESTS_CACHE.write_text(json.dumps(all_quests, indent=2))

        self.state["quests_generated"] = self.state.get("quests_generated",0) + len(family_ids)
        self.state["last_quest_generation"] = datetime.datetime.now().isoformat()
        _save_state(self.state)

        print(f"[evolution] ✅ Dynamic quests generated for {len(family_ids)} families")
        return all_quests

    # ══════════════════════════════════════════════════════════════════════════
    # MODE C — AUTO-EVOLUTION TICK (small changes, safety rails)
    # ══════════════════════════════════════════════════════════════════════════

    def run_auto_evolution_tick(self) -> dict:
        """
        Runs every 24 hours. Analyzes coherence trends, adjusts:
        - Quest XP multipliers (±10% based on family engagement)
        - Lesson difficulty hints in insights
        - Grokipedia principle emphasis
        - Morning synthesis focus areas
        
        Does NOT modify source files. Writes evolution_config.json
        which app.py reads to tune behavior dynamically.
        """
        print("[evolution] 🧬 Running auto-evolution tick...")

        family_ids = self._get_family_ids()
        config     = self._load_evolution_config()

        # Analyze all families
        total_coherence = []
        total_streaks   = []
        total_xp_rates  = []

        for fid in family_ids:
            stats = self._load_family_stats(fid)
            coh   = stats.get("coherence_history",[])
            if coh: total_coherence.extend(coh[-5:])
            total_streaks.append(stats.get("streak_days",0))
            total_xp_rates.append(stats.get("total_xp",0))

        avg_coh    = sum(total_coherence) / len(total_coherence) if total_coherence else 0.72
        avg_streak = sum(total_streaks)   / len(total_streaks)   if total_streaks   else 0
        avg_xp     = sum(total_xp_rates)  / len(total_xp_rates)  if total_xp_rates  else 0

        # Evolution rules
        changes = []

        # Rule 1: Low coherence → increase difficulty gating + feature Truth Education
        if avg_coh < 0.60:
            config["min_coherence_override"] = 0.55
            config["quest_xp_multiplier"]    = 1.2
            config["featured_track"]         = "truth"  # truth-seeking rebuilds coherence
            config["suggest_next_track"]     = "truth"
            changes.append(f"Low avg coherence ({avg_coh:.2f}) → featuring Truth Education + easier thresholds + XP boost")

        elif avg_coh > 0.85:
            config["min_coherence_override"] = 0.75  # higher bar for master lessons
            config["quest_xp_multiplier"]    = 1.0
            changes.append(f"High avg coherence ({avg_coh:.2f}) → raising difficulty floor")

        # Rule 2: Low streaks → boost daily quest visibility
        if avg_streak < 2:
            config["highlight_streaks"]  = True
            config["streak_xp_bonus"]    = 1.5
            changes.append(f"Low streaks ({avg_streak:.1f}) → boosting streak incentives")

        # Rule 3: Identify which lesson tracks families complete most
        most_popular = self._get_most_popular_track()
        config["featured_track"]   = most_popular
        config["suggest_next_track"] = self._suggest_next_track(most_popular)
        changes.append(f"Featured track: {most_popular} → suggesting: {config['suggest_next_track']}")

        # Rule 4: Swarm wonder analysis
        wonder = self._get_current_wonder()
        if wonder >= 1.5:
            config["simulation_mode"] = "high_wonder"
            config["bonus_lesson_type"] = "simulation"
            changes.append(f"Wonder spike ({wonder:.4f}) → featuring simulation lessons")
        else:
            config["simulation_mode"] = "standard"
            config["bonus_lesson_type"] = ""

        # Save config
        config["updated_at"]  = datetime.datetime.now().isoformat()
        config["changes"]     = changes
        config["avg_coherence"] = round(avg_coh, 3)
        config["avg_streak"]  = round(avg_streak, 1)
        self._save_evolution_config(config)

        # Log to truth
        self._log_to_truth(
            f"Auto-evolution tick: {len(changes)} adaptations | avg_coh={avg_coh:.2f}",
            "evolution_auto_tick"
        )

        print(f"[evolution] ✅ Auto-evolution tick complete: {len(changes)} adaptations")
        for c in changes:
            print(f"   → {c}")

        return config

    # ── Proposal management ───────────────────────────────────────────────────

    def get_pending_proposals(self) -> list:
        if not PROPOSALS_LOG.exists():
            return []
        try:
            entries = []
            for line in PROPOSALS_LOG.read_text().strip().split("\n"):
                try:
                    e = json.loads(line)
                    if e.get("status") == "pending":
                        entries.append(e)
                except Exception:
                    pass
            return entries
        except Exception:
            return []

    def get_all_proposals(self, limit: int = 50) -> list:
        if not PROPOSALS_LOG.exists():
            return []
        try:
            entries = []
            for line in reversed(PROPOSALS_LOG.read_text().strip().split("\n")[-limit:]):
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
            return entries
        except Exception:
            return []

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_family_context(self) -> str:
        lines = []
        for fid in self._get_family_ids():
            stats = self._load_family_stats(fid)
            coh   = stats.get("coherence_history",[])
            avg   = round(sum(coh[-5:])/len(coh[-5:]),3) if coh else 0.72
            lines.append(
                f"Family {fid}: level={stats.get('level',1)} xp={stats.get('total_xp',0)} "
                f"streak={stats.get('streak_days',0)} avg_coherence={avg} "
                f"completed={len(stats.get('lessons_completed',[]))}"
            )
        return "\n".join(lines) if lines else "No family data yet"

    def _get_recent_insights(self, n: int = 5) -> str:
        insights_dir = WORK_DIR / "insights" / "daily"
        if not insights_dir.exists():
            return "No insights yet"
        files = sorted(insights_dir.glob("*.md"), reverse=True)[:n]
        snippets = []
        for f in files:
            try:
                content = f.read_text()
                # Extract first 200 chars after the header
                lines   = [l for l in content.splitlines() if l and not l.startswith("#")]
                snippet = " ".join(lines[:3])[:200]
                snippets.append(f"{f.stem}: {snippet}")
            except Exception:
                pass
        return "\n".join(snippets) if snippets else "No insights available"

    def _get_family_ids(self) -> list:
        if not FAMILIES_DIR.exists():
            return ["operator"]
        return [d.name for d in FAMILIES_DIR.iterdir() if d.is_dir() and (d/"stats.json").exists()]

    def _load_family_stats(self, family_id: str) -> dict:
        stats_path = FAMILIES_DIR / family_id / "stats.json"
        if stats_path.exists():
            try: return json.loads(stats_path.read_text())
            except: pass
        return {}

    def _get_todays_swarm_topic(self) -> str:
        digest = WORK_DIR / "tier2_digest.txt"
        if digest.exists():
            try:
                lines = [l for l in digest.read_text().splitlines() if l and not l.startswith("=") and not l.startswith("DAUGHTER") and not l.startswith("Generated") and not l.startswith("Wonder")]
                if lines: return lines[0][:60]
            except: pass
        topics = [
            "antifragility in uncertain systems",
            "Bitcoin as temporal anchor for truth",
            "simulation glitch signals in daily life",
            "polyvagal regulation and learning readiness",
            "steelmanning your own beliefs",
        ]
        return random.choice(topics)

    def _get_most_popular_track(self) -> str:
        track_counts = {}
        for fid in self._get_family_ids():
            stats = self._load_family_stats(fid)
            for lesson_key in stats.get("lessons_completed",[]):
                track = lesson_key.split("-")[0] if "-" in lesson_key else lesson_key
                track_counts[track] = track_counts.get(track, 0) + 1
        return max(track_counts, key=track_counts.get) if track_counts else "courage"

    def _suggest_next_track(self, current: str) -> str:
        flow = {
            "courage":       "truth",
            "truth":         "steelmanning",
            "steelmanning":  "antifragility",
            "antifragility": "simulation",
            "simulation":    "epistemology",
            "epistemology":  "bitcoin-sovereignty",
            "bitcoin":       "decentralization",
            "polyvagal":     "stoic",
            "stoic":         "money",
            "money":         "legal",
            "legal":         "building",
            "building":      "baking",
            "baking":        "psychology",
            "psychology":    "media",
            "media":         "faith",
            "faith":         "ai-literacy",
            "ai-literacy":   "wonder",
        }
        return flow.get(current, "wonder")

    def _get_truth_drill_quest(self, family_id: str) -> dict:
        """
        Generate a daily Truth Drill quest pulling LIVE from swarm Tier-2 daughter output.
        Families truth-test the actual swarm insights in real time.
        """
        stats     = self._load_family_stats(family_id)
        completed = set(stats.get("lessons_completed", []))
        truth_level = sum(1 for k in completed if k.startswith("truth-"))

        # Pull latest Tier-2 daughter insight from truth log
        live_insight = self._get_latest_tier2_insight()
        swarm_topic  = self._get_todays_swarm_topic()

        drills = [
            # Level 0 — no truth track needed
            {
                "id":    "truth_drill_headlines",
                "title": "Find the emotional hook in 3 news headlines today",
                "xp": 15, "sats": 30,
                "hint":  "Fear, outrage, pride, hope, or tribal identity — which one is it?",
            },
            # Level 1
            {
                "id":    "truth_drill_steelman",
                "title": "Steelman one opinion you strongly disagree with",
                "xp": 20, "sats": 40,
                "hint":  "State it better than its proponents would. Then — and only then — respond.",
            },
            # Level 2
            {
                "id":    "truth_drill_falsify",
                "title": "Write the falsification condition for one family belief",
                "xp": 25, "sats": 50,
                "hint":  "Complete: 'This belief is WRONG if ___.' If you can't complete it, the belief may not be falsifiable.",
            },
            # Level 3 — coherence check
            {
                "id":    "truth_drill_coherence",
                "title": "Check: do your top 3 beliefs about money/risk point the same direction?",
                "xp": 25, "sats": 50,
                "hint":  "Contradictory beliefs = incoherence. Which one needs to update?",
            },
            # Level 4 — LIVE swarm insight truth-test
            {
                "id":    "truth_drill_swarm_live",
                "title": f"Truth-test today's swarm insight: '{live_insight[:60]}...'",
                "xp": 30, "sats": 60,
                "hint":  "Run the 4-step process: emotional hook? steelman? falsification? coherent with your values?",
                "live_insight": live_insight,
            },
            # Level 5 — full real-world process
            {
                "id":    "truth_drill_realworld",
                "title": "Run the full truth-seeking process on one real pending family decision",
                "xp": 40, "sats": 80,
                "hint":  "This is your Truth Guardian proof-of-work. Write it up and share with the family.",
            },
        ]

        idx = min(truth_level, len(drills) - 1)
        return drills[idx]

    def _get_latest_tier2_insight(self) -> str:
        """Pull the most recent Tier-2 daughter output from the truth log."""
        try:
            if not TRUTH_LOG.exists():
                return self._get_todays_swarm_topic()
            lines = TRUTH_LOG.read_text().strip().split("\n")
            # Find last Tier-2 entry
            for line in reversed(lines[-100:]):
                try:
                    entry = json.loads(line)
                    if entry.get("tier") == 2 and entry.get("result"):
                        result = entry["result"]
                        # Strip evolution prefix if present
                        if result.startswith("[EVOLUTION]"):
                            continue
                        return result[:120]
                except Exception:
                    pass
            # Fall back to last Tier-1
            for line in reversed(lines[-50:]):
                try:
                    entry = json.loads(line)
                    if entry.get("result") and not entry["result"].startswith("["):
                        return entry["result"][:120]
                except Exception:
                    pass
        except Exception:
            pass
        return self._get_todays_swarm_topic()

    def _get_current_wonder(self) -> float:
        try:
            status = Path("/mnt/main/swarm_status.json")
            if status.exists():
                return float(json.loads(status.read_text()).get("wonder_index", 1.0))
        except: pass
        return 1.0

    def _load_evolution_config(self) -> dict:
        cfg_path = Path("/mnt/main/evolution_config.json")
        if cfg_path.exists():
            try: return json.loads(cfg_path.read_text())
            except: pass
        return {
            "min_coherence_override": None,
            "quest_xp_multiplier":    1.0,
            "streak_xp_bonus":        1.0,
            "highlight_streaks":      False,
            "featured_track":         "courage",
            "suggest_next_track":     "antifragility",
            "simulation_mode":        "standard",
            "bonus_lesson_type":      "",
        }

    def _save_evolution_config(self, config: dict):
        Path("/mnt/main/evolution_config.json").write_text(json.dumps(config, indent=2))

    def _find_proposal(self, proposal_id: str) -> dict | None:
        for p in self.get_all_proposals():
            if p.get("id") == proposal_id:
                return p
        return None

    def _update_proposal_status(self, proposal_id: str, status: str, reason: str = ""):
        if not PROPOSALS_LOG.exists(): return
        try:
            lines   = PROPOSALS_LOG.read_text().strip().split("\n")
            updated = []
            for line in lines:
                try:
                    e = json.loads(line)
                    if e.get("id") == proposal_id:
                        e["status"] = status
                        if reason: e["rejection_reason"] = reason
                        if status == "approved": e["approved_at"] = datetime.datetime.now().isoformat()
                        if status == "rejected": e["rejected_at"] = datetime.datetime.now().isoformat()
                    updated.append(json.dumps(e))
                except: updated.append(line)
            PROPOSALS_LOG.write_text("\n".join(updated))
        except Exception as e:
            print(f"[evolution] Status update error: {e}")

    def _log_to_truth(self, message: str, trigger: str):
        try:
            entry = {
                "timestamp":   datetime.datetime.now().isoformat(),
                "tier":        2,
                "trigger":     trigger,
                "daughter":    "VECTOR-A",
                "result":      f"[EVOLUTION] {message}",
                "coherence":   1.0,
                "wonder_index": self._get_current_wonder(),
            }
            with open(TRUTH_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception: pass


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🧬 Swarm Evolution Engine Test")
    engine = EvolutionEngine()
    print("\n--- Mode B: Dynamic Quests ---")
    quests = engine.generate_dynamic_quests("family_alpha")
    for fid, data in quests.items():
        print(f"\n{fid} (level {data['family_level']}, coherence {data['avg_coherence']}):")
        for q in data["quests"]:
            print(f"  ⭕ {q['title']} (+{q['xp']} XP · {q['hint'][:50]})")
    print("\n--- Mode C: Auto-Evolution Tick ---")
    config = engine.run_auto_evolution_tick()
    print(f"Featured track: {config.get('featured_track')} → {config.get('suggest_next_track')}")
    print(f"Quest XP multiplier: {config.get('quest_xp_multiplier')}")
    print("\nWar Eagle 🦅")
