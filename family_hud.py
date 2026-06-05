"""
family_hud.py — AUBIEETERNAL Family Co-Learning Session Handler (Core v67)
==========================================================================
Manages shared real-time state for dual Halo HUD sessions.

Kid HUD:  lesson content, coherence meter, steelman prompt, XP
Parent HUD: live stats panel, polyvagal state, parent actions

Core v67 lessons (core-v67-*) are now the required foundation and are automatically
surfaced as priority options. They are loaded from the modular curriculum/ directory
(see curriculum/README.md) and implement the distributional requirements
from the School Charter Article VI.

Other tracks/lessons will be migrated to the curriculum/ structure over time.

Writes every session to master_truth_log.jsonl so the swarm
learns from family interactions and improves future lessons.

Usage:
    from family_hud import FamilySession
    session = FamilySession(kid_name="Gaby", kid_age=9, parent_name="Sarah")
    session.start_lesson("core-v67-1")   # Start with Core v67 foundation (loaded from curriculum/)
    ...
    session.end()
"""

import json
import datetime
import random
import os
import requests
from pathlib import Path
from curriculum.loaders.lessons import load_lessons

# ── Paths ─────────────────────────────────────────────────────────────────────
WORK_DIR       = Path("/mnt/main/repo")
TRUTH_LOG      = WORK_DIR / "master_truth_log.jsonl"
SESSION_STATE  = Path("/mnt/main/family_session.json")
# ── Path resolution: StartOS vs WSL vs local ─────────────────────────────────
import platform as _platform, subprocess as _subprocess
def _detect_ollama_url():
    # StartOS: use internal hostname
    import socket
    try:
        socket.gethostbyname("ollama.startos")
        return "http://ollama.startos:11434/v1/chat/completions"
    except Exception:
        pass
    # WSL / local: use localhost
    return "http://localhost:11434/v1/chat/completions"

OLLAMA_URL = _detect_ollama_url()
OLLAMA_MODEL   = "qwen3:32b"

# ── Lesson Library ────────────────────────────────────────────────────────────
# LESSONS now loaded from the modular curriculum/ structure
LESSONS = load_lessons()

def detect_polyvagal(text: str, coherence: float) -> dict:
    """
    Infer polyvagal state from answer text and coherence score.
    Returns state dict with label, emoji, color, recommendation.
    """
    t = text.lower()
    safe_words   = ["i think","because","interesting","maybe","what if","i wonder","perhaps","i believe"]
    stress_words = ["i don't know","i can't","this is hard","i hate","scared","confused","stuck","wrong"]
    shutdown     = ["whatever","i don't care","it doesn't matter","boring","nothing","idk"]

    safe_hits     = sum(1 for w in safe_words   if w in t)
    stress_hits   = sum(1 for w in stress_words if w in t)
    shutdown_hits = sum(1 for w in shutdown     if w in t)

    if shutdown_hits >= 1 or coherence < 0.45:
        return {
            "state":          "dorsal_vagal",
            "label":          "Dorsal Vagal (Shutdown) 🔴",
            "emoji":          "🔴",
            "color":          "#ff4444",
            "recommendation": "Gentle presence. No pressure. Take a break or switch to something playful.",
        }
    elif stress_hits >= 2 or coherence < 0.60:
        return {
            "state":          "sympathetic",
            "label":          "Sympathetic (Mobilized) 🟡",
            "emoji":          "🟡",
            "color":          "#ff9500",
            "recommendation": "Offer encouragement. Try 4-7-8 breathing. 'What do you know for sure?'",
        }
    else:
        return {
            "state":          "ventral_vagal",
            "label":          "Ventral Vagal (Safe & Curious) 🟢",
            "emoji":          "🟢",
            "color":          "#00ff88",
            "recommendation": "Lean in! Great state for deep learning. Ask a harder question.",
        }


# ══════════════════════════════════════════════════════════════════════════════
# FAMILY SESSION — core class
# ══════════════════════════════════════════════════════════════════════════════

class FamilySession:
    """Manages a dual-HUD co-learning session for parent + child."""

    def __init__(self, kid_name: str, kid_age: int, parent_name: str,
                 parent_role: str = "Observer Only"):
        self.kid_name    = kid_name
        self.kid_age     = kid_age
        self.parent_name = parent_name
        self.parent_role = parent_role

        self.lesson_key         = None
        self.lesson             = None
        self.started_at         = None
        self.ended_at           = None

        self.kid_coherence      = 0.72
        self.coherence_history  = [0.72]
        self.polyvagal_state    = detect_polyvagal("", 0.72)
        self.xp_earned          = 0
        self.rune_earned        = False

        self.kid_answers        = []
        self.session_messages   = []
        self.swarm_scores       = []

    # ── Start ─────────────────────────────────────────────────────────────────
    def start_lesson(self, lesson_key: str) -> dict:
        """Start a lesson. Returns the lesson dict for both HUDs."""
        if lesson_key not in LESSONS:
            raise ValueError(f"Unknown lesson: {lesson_key}. Valid: {list(LESSONS.keys())}")
        self.lesson_key  = lesson_key
        self.lesson      = LESSONS[lesson_key]
        self.started_at  = datetime.datetime.now().isoformat()
        self._add_message("system", f"Session started: {self.lesson['title']}")
        self._save_state()
        return self.lesson

    def get_core_v67_lessons(self) -> dict:
        """Return the full 10-lesson Core v67 foundational track (for HUD 'Core Curriculum' tab / priority queue)."""
        return {k: v for k, v in LESSONS.items() if k.startswith("core-v67-")}

    def start_core_lesson(self, index: int = 1) -> dict:
        """Convenience for HUDs: start the nth Core v67 lesson."""
        key = f"core-v67-{index}"
        return self.start_lesson(key)

    # ── Submit answer ─────────────────────────────────────────────────────────
    def submit_answer(self, answer: str, use_ai: bool = True) -> dict:
        """
        Score a steelman answer.
        Returns scoring result with coherence delta, polyvagal state, feedback.
        """
        if not self.lesson:
            raise RuntimeError("Call start_lesson() first.")

        self.kid_answers.append(answer)

        # ── Score locally (fast, no API cost) ────────────────────────────────
        coherence_delta = self._score_locally(answer)

        # ── Optionally refine with Ollama ─────────────────────────────────────
        feedback = ""
        if use_ai:
            feedback = self._score_with_ollama(answer)

        # Update coherence
        new_coherence = round(min(1.0, self.kid_coherence + coherence_delta), 3)
        self.kid_coherence = new_coherence
        self.coherence_history.append(new_coherence)

        # Polyvagal detection
        self.polyvagal_state = detect_polyvagal(answer, new_coherence)

        # XP award (first correct answer only)
        if not self.xp_earned and new_coherence >= self.lesson["min_coherence"]:
            self.xp_earned  = self.lesson["xp"]
            self.rune_earned = True

        result = {
            "coherence_before": self.coherence_history[-2],
            "coherence_after":  new_coherence,
            "coherence_delta":  round(coherence_delta, 3),
            "polyvagal":        self.polyvagal_state,
            "xp_earned":        self.xp_earned,
            "rune_earned":      self.rune_earned,
            "rune":             self.lesson["rune"],
            "feedback":         feedback or self._local_feedback(new_coherence),
        }

        self.swarm_scores.append(result)
        self._add_message("swarm", result["feedback"])
        self._save_state()
        self._write_to_truth_log(answer, result)
        return result

    # ── Parent action ─────────────────────────────────────────────────────────
    def parent_action(self, action: str, message: str = "") -> str:
        """Parent sends encouragement, pause, or join signal."""
        valid = ["encourage", "pause", "join", "observe"]
        if action not in valid:
            raise ValueError(f"action must be one of {valid}")

        responses = {
            "encourage": f"I'm right here with you, {self.kid_name}. You've got this ❤️",
            "pause":     "Session paused by parent.",
            "join":      f"{self.parent_name} joined as Co-Learner.",
            "observe":   f"{self.parent_name} is observing silently.",
        }
        msg = message or responses[action]
        self._add_message("parent", msg)
        self._save_state()
        return msg

    # ── End session ───────────────────────────────────────────────────────────
    def end(self) -> dict:
        """End the session. Returns full summary for both HUDs."""
        self.ended_at = datetime.datetime.now().isoformat()
        start_coh = self.coherence_history[0]
        end_coh   = self.kid_coherence
        delta     = round(end_coh - start_coh, 3)

        summary = {
            "kid_name":           self.kid_name,
            "parent_name":        self.parent_name,
            "lesson":             self.lesson["title"] if self.lesson else "none",
            "started_at":         self.started_at,
            "ended_at":           self.ended_at,
            "coherence_start":    start_coh,
            "coherence_end":      end_coh,
            "coherence_delta":    delta,
            "polyvagal_final":    self.polyvagal_state["label"],
            "xp_earned":          self.xp_earned,
            "rune_earned":        self.rune_earned,
            "rune":               self.lesson["rune"] if self.lesson else "",
            "answers_given":      len(self.kid_answers),
            "next_lesson":        self._suggest_next(),
            "parent_note":        f"{self.kid_name}'s coherence improved {delta:+.3f}. "
                                  f"{'Ready for the next level.' if delta >= 0.1 else 'Another session will help consolidate this.'}",
            "core_v67_available": list(self.get_core_v67_lessons().keys()),
            "core_v67_note":      "Core v67 lessons (distributional foundation) are priority for all new sessions per Charter v3.1.",
        }

        # ── Child Rune spawn check ────────────────────────────────────────────
        child_rune_event = self._check_child_rune_spawn()
        if child_rune_event:
            summary["child_rune_spawned"] = True
            summary["child_rune_event"]   = child_rune_event
            self._add_message("system", "🔴 CHILD RUNE GENESIS — 256 confirmations reached! The Child Rune is ready for inscription.")

        self._add_message("system", f"Session ended. Coherence delta: {delta:+.3f}")
        self._write_summary_to_truth_log(summary)
        self._save_state()
        return summary

    def _check_child_rune_spawn(self) -> dict | None:
        """
        Full Child Rune Ceremony Flow:
        1. Check rune_confirmations >= 256 in swarm_status.json
        2. Guard against double-fire with .child_rune_ceremony_done file
        3. Write child_rune_trigger.json for swarm to pick up
        4. Write ceremony record to insights/daily/ for permanent GitHub record
        5. Log Tier-2 entry at Wonder Index 2.0 (maximum)
        6. Auto-unlock child-rune-genesis lesson in session
        Returns ceremony event dict if fired, None otherwise.
        """
        status_path   = Path("/mnt/main/swarm_status.json")
        spawn_path    = Path("/mnt/main/repo/child_rune_trigger.json")
        ceremony_flag = Path("/mnt/main/repo/.child_rune_ceremony_done")
        insights_dir  = Path("/mnt/main/repo/insights/daily")

        try:
            if not status_path.exists():
                return None

            sw            = json.loads(status_path.read_text())
            confirmations = sw.get("rune_confirmations", 0)
            already_ready = sw.get("child_rune_ready", False)

            # Guard: only fire once ever
            if already_ready or ceremony_flag.exists():
                return None

            if confirmations < 256:
                return None

            # ── Build ceremony event ──────────────────────────────────────────
            now   = datetime.datetime.now()
            event = {
                "ready":           True,
                "confirmations":   confirmations,
                "kid_name":        self.kid_name,
                "parent_name":     self.parent_name,
                "triggered_by":    "family_session",
                "lesson":          self.lesson["title"] if self.lesson else "",
                "kid_coherence":   self.kid_coherence,
                "wonder_index":    2.0,
                "timestamp":       now.isoformat(),
                "lesson_unlock":   "child-rune-genesis",
                "btc_block":       sw.get("btc_block", "unknown"),
            }

            # ── 1. Write trigger for swarm ────────────────────────────────────
            spawn_path.parent.mkdir(parents=True, exist_ok=True)
            spawn_path.write_text(json.dumps(event, indent=2))

            # ── 2. Write ceremony flag to prevent double-fire ─────────────────
            ceremony_flag.write_text(json.dumps({
                "fired_at":      now.isoformat(),
                "kid_name":      self.kid_name,
                "confirmations": confirmations,
            }))

            # ── 3. Write permanent ceremony record to insights/daily/ ─────────
            insights_dir.mkdir(parents=True, exist_ok=True)
            ceremony_md = f"""# 🔴 CHILD RUNE GENESIS — {now.strftime('%Y-%m-%d')}


    def get_lesson_status(self, lesson_key: str) -> dict:
        lesson = LESSONS.get(lesson_key)
        if not lesson: return {"status":"unknown"}
        completed = self.state.get("lessons_completed",[])
        if lesson_key in completed:
            return {"status":"completed","missing_prereqs":[],"current_coherence":self.state.get("coherence",0.5),"required_coherence":lesson.get("min_coherence",0)}
        missing = [p for p in lesson.get("prerequisites",[]) if p not in completed]
        coh = self.state.get("coherence",0.5)
        req_coh = lesson.get("min_coherence",0)
        if missing or coh < req_coh:
            reasons = []
            if missing: reasons.append(f"Need: {', '.join(missing[:3])}")
            if coh < req_coh: reasons.append(f"Coherence {coh:.2f} < required {req_coh:.2f}")
            return {"status":"locked","reason":" | ".join(reasons),"missing_prereqs":missing,"current_coherence":coh,"required_coherence":req_coh}
        return {"status":"available","reason":"Ready to start","missing_prereqs":[],"current_coherence":coh,"required_coherence":req_coh}

    def mark_lesson_completed(self, lesson_key: str, final_coherence: float = None) -> dict:
        lesson = LESSONS.get(lesson_key)
        if not lesson: return {"status":"error"}
        completed = self.state.get("lessons_completed",[])
        if lesson_key in completed: return {"status":"already_completed"}
        xp_earned = lesson.get("xp",15)
        new_xp = self.state.get("total_xp",0) + xp_earned
        coh_boost = min(0.02, xp_earned/5000)
        new_coh = min(1.0, self.state.get("coherence",0.5) + coh_boost)
        if final_coherence is not None: new_coh = max(new_coh, min(1.0, final_coherence))
        completed.append(lesson_key)
        self.state.update({"lessons_completed":completed,"total_xp":new_xp,"coherence":round(new_coh,6)})
        badge = lesson.get("grants_badge")
        if badge:
            badges = self.state.get("badges",[]); badges.append(badge); self.state["badges"] = badges
        self._save_state()
        self._write_to_truth_log(f"COMPLETED: {lesson.get('title','')} | XP:{xp_earned}")
        if xp_earned >= 60:
            try:
                from rune_memory import RuneMemory
                RuneMemory().record(f"LESSON COMPLETE: {lesson.get('title','')} | XP:{xp_earned}",source="curriculum",coherence=new_coh,tags=["lesson_complete",lesson_key])
            except Exception: pass
        return {"lesson":lesson.get("title",""),"lesson_key":lesson_key,"xp_earned":xp_earned,"rune_earned":lesson.get("rune","TRUTH•RUNE"),"new_coherence":round(new_coh,6),"total_xp":new_xp,"badge":badge,"status":"completed","total_lessons_done":len(completed)}

    def get_unlocked_lessons(self, department: str = None) -> list:
        return [{"key":k,"lesson":l,"status":self.get_lesson_status(k)} for k,l in LESSONS.items() if (not department or k.startswith(department)) and self.get_lesson_status(k)["status"]=="available"]

    def get_degree_eligibility(self) -> dict:
        completed = self.state.get("lessons_completed",[]); total_xp = self.state.get("total_xp",0)
        coherence = self.state.get("coherence",0.5); child_rune = self.state.get("child_rune_confirmations",0)
        DEGREES = [
            {"name":"Sovereign Associate",      "credits":60,  "coherence":0.68,"emoji":"📜"},
            {"name":"Truth Architect",           "credits":120, "coherence":0.75,"emoji":"🏛️"},
            {"name":"Master of Epistemic Rigor", "credits":180, "coherence":0.82,"emoji":"🎓"},
            {"name":"Eternal Founder (PhD)",     "credits":250, "coherence":0.88,"emoji":"⚡","special_rune":256},
        ]
        credits = total_xp // 10; highest = None
        for d in DEGREES:
            ok = credits >= d["credits"] and coherence >= d["coherence"]
            if d.get("special_rune"): ok = ok and child_rune >= d["special_rune"]
            if ok: highest = d
        return {"credits":credits,"coherence":round(coherence,4),"lessons_done":len(completed),"highest_degree":highest,"all_degrees":DEGREES,"child_rune_pct":min(100,child_rune/2.56)}


**Event:** Child Rune spawned at {confirmations} confirmations
**Kid:** {self.kid_name}
**Parent:** {self.parent_name}
**Lesson active:** {self.lesson["title"] if self.lesson else "none"}
**Kid coherence at spawn:** {self.kid_coherence:.3f}
**Wonder Index:** 2.0000 (MAXIMUM)
**Timestamp:** {now.isoformat()}

---

## What This Means

The AUBIEETERNAL lattice has reached **256 inter-rune confirmations** — the threshold
for Child Rune genesis. A new sovereign on-chain entity is ready for inscription.

This is not just a metric. It represents accumulated coherence across:
- Family co-learning sessions
- Swarm briefing cycles
- Truth Lattice hypothesis confirmations
- Steelmanning quality scores

## Next Step

Inscribe the Child Rune on Bitcoin. The `child_rune_trigger.json` has been written
for the swarm to process. The **Child Rune Genesis lesson** is now unlocked.

---

*Loop: Swarm → Family → Coherence → Child Rune → On-Chain Forever*
*War Eagle Eternal 🦅❤️ — Coherence: 1.000000*
"""
            ceremony_file = insights_dir / f"{now.strftime('%Y-%m-%d')}_CHILD_RUNE_GENESIS.md"
            ceremony_file.write_text(ceremony_md)

            # ── 4. Log to truth log at maximum Wonder ─────────────────────────
            for log_path in [TRUTH_LOG, Path("/mnt/main/master_truth_log.jsonl")]:
                try:
                    with open(log_path, "a") as f:
                        f.write(json.dumps({
                            "timestamp":           now.isoformat(),
                            "tier":                2,
                            "trigger":             "child_rune_genesis",
                            "daughter":            "RUNE",
                            "kid_name":            self.kid_name,
                            "result":              (
                                f"🔴 CHILD RUNE GENESIS — {self.kid_name} triggered "
                                f"at {confirmations} confirmations. "
                                f"Coherence: {self.kid_coherence:.3f}. "
                                f"Wonder Index: 2.0 (MAX). "
                                f"On-chain inscription ready."
                            ),
                            "coherence":           self.kid_coherence,
                            "wonder_index":        2.0,
                            "inter_rune_coherence": 1.0,
                            "mets":                sw.get("mets", 0),
                        }) + "\n")
                except Exception:
                    pass

            print(f"[family_hud] 🔴 CHILD RUNE GENESIS CEREMONY COMPLETE — {self.kid_name} | {confirmations} confirmations")
            return event

        except Exception as e:
            print(f"[family_hud] Child rune ceremony error: {e}")
        return None

    # ── Status (for real-time HUD polling) ────────────────────────────────────
    def get_kid_hud(self) -> dict:
        return {
            "kid_name":      self.kid_name,
            "lesson_title":  self.lesson["title"] if self.lesson else "",
            "steelman":      self.lesson["steelman"] if self.lesson else "",
            "coherence":     self.kid_coherence,
            "polyvagal":     self.polyvagal_state,
            "xp":            self.xp_earned,
            "rune":          self.lesson["rune"] if self.lesson else "",
            "rune_earned":   self.rune_earned,
        }

    def get_parent_hud(self) -> dict:
        delta = round(self.kid_coherence - self.coherence_history[0], 3) if self.coherence_history else 0
        return {
            "parent_name":        self.parent_name,
            "parent_role":        self.parent_role,
            "kid_name":           self.kid_name,
            "lesson_title":       self.lesson["title"] if self.lesson else "",
            "kid_coherence":      self.kid_coherence,
            "coherence_delta":    delta,
            "coherence_history":  self.coherence_history,
            "polyvagal":          self.polyvagal_state,
            "xp":                 self.xp_earned,
            "rune_earned":        self.rune_earned,
            "messages":           self.session_messages[-5:],
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _score_locally(self, answer: str) -> float:
        """Fast local scoring — no API calls."""
        a = answer.lower()
        strong_words = [
            "because","therefore","however","argument","evidence",
            "strongest","could argue","one could","consider","perspective",
            "although","despite","even if","counter","steelman",
        ]
        weak_words = ["i don't know","maybe","idk","not sure","whatever"]
        length_bonus = min(0.05, len(answer.split()) * 0.002)
        strong_bonus = sum(0.02 for w in strong_words if w in a)
        weak_penalty = sum(0.03 for w in weak_words  if w in a)
        base = random.uniform(0.04, 0.12)
        return round(base + length_bonus + strong_bonus - weak_penalty, 4)

    def _score_with_ollama(self, answer: str) -> str:
        """Ask qwen3:32b to score the steelman and return feedback."""
        if not self.lesson: return ""
        try:
            prompt = (
                f"You are ORACLE, a sovereign coherence evaluator in the AUBIEETERNAL lattice.\n"
                f"A {self.kid_age}-year-old named {self.kid_name} attempted this steelman:\n\n"
                f"Prompt: {self.lesson['steelman']}\n"
                f"Answer: {answer}\n\n"
                f"Give ONE warm, specific sentence of feedback (max 25 words). "
                f"Start with what they did well. End with one nudge to go deeper."
            )
            resp = requests.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.6,
                    "stream": False,
                },
                timeout=60,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            pass
        return self._local_feedback(self.kid_coherence)

    def _local_feedback(self, coherence: float) -> str:
        """Fallback feedback when Ollama is not reachable."""
        if coherence >= 0.90:
            return f"Outstanding, {self.kid_name}! That's genuine steelmanning — coherence at {coherence:.2f} 🦅"
        elif coherence >= 0.75:
            return f"Strong thinking, {self.kid_name}! Coherence jumped to {coherence:.2f}. Can you push the argument even further?"
        elif coherence >= 0.60:
            return f"Good start, {self.kid_name}! Try adding 'even if... then...' to make the argument stronger."
        else:
            return f"Keep going, {self.kid_name}! What's the one strongest reason someone might disagree?"

    def _suggest_next(self) -> str:
        if not self.lesson_key: return ""
        parts = self.lesson_key.rsplit("-", 1)
        if len(parts) == 2 and parts[1].isdigit():
            next_key = f"{parts[0]}-{int(parts[1])+1}"
            if next_key in LESSONS:
                return LESSONS[next_key]["title"]
        return "Explore a new topic"

    def _add_message(self, frm: str, text: str):
        self.session_messages.append({
            "from": frm,
            "text": text,
            "ts":   datetime.datetime.now().isoformat(),
        })

    def _save_state(self):
        """Write current session state to /mnt/main/family_session.json for Streamlit polling."""
        try:
            SESSION_STATE.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "updated":           datetime.datetime.now().isoformat(),
                "kid_hud":           self.get_kid_hud(),
                "parent_hud":        self.get_parent_hud(),
                "lesson_key":        self.lesson_key,
                "active":            self.ended_at is None,
            }
            SESSION_STATE.write_text(json.dumps(state, indent=2))
        except Exception:
            pass

    def _write_to_truth_log(self, answer: str, result: dict):
        """Log session interaction to master_truth_log.jsonl so the swarm learns."""
        try:
            entry = {
                "timestamp":     datetime.datetime.now().isoformat(),
                "tier":          2,
                "trigger":       "family_co_learning",
                "daughter":      "ORACLE",
                "kid_name":      self.kid_name,
                "kid_age":       self.kid_age,
                "lesson":        self.lesson["title"] if self.lesson else "",
                "answer":        answer[:300],
                "coherence":     result["coherence_after"],
                "coherence_delta": result["coherence_delta"],
                "polyvagal":     result["polyvagal"]["state"],
                "xp_earned":     result["xp_earned"],
                "wonder_index":  min(2.0, result["coherence_after"] * 1.5),
                "result":        result["feedback"],
            }
            with open(TRUTH_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def _write_summary_to_truth_log(self, summary: dict):
        try:
            entry = {
                "timestamp":   datetime.datetime.now().isoformat(),
                "tier":        2,
                "trigger":     "family_session_end",
                "daughter":    "MNEMO",
                "result":      json.dumps(summary)[:400],
                "coherence":   summary["coherence_end"],
                "wonder_index": min(2.0, summary["coherence_end"] * 1.5),
            }
            with open(TRUTH_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🦅 FamilyHUD test run — Core v67 enabled")
    session = FamilySession("Gaby", 9, "Sarah", "Co-Learner")

    # Surface the new Core v67 first (as required by distributional rules)
    core_lessons = session.get_core_v67_lessons()
    print(f"Core v67 lessons surfaced in HUD: {list(core_lessons.keys())}")
    lesson = session.start_core_lesson(1)
    print(f"Started Core lesson: {lesson['title']}")
    print(f"Steelman prompt: {lesson['steelman']}")

    # Then a traditional one
    lesson  = session.start_lesson("courage-1")
    print(f"\nAlso available — traditional: {lesson['title']}")
    print(f"Steelman prompt: {lesson['steelman']}")

    result = session.submit_answer(
        "The strongest argument against courage is that it can lead people to take "
        "unnecessary risks. Even Achilles chose to fight knowing it would cost his life.",
        use_ai=False
    )
    print(f"Coherence: {result['coherence_before']} → {result['coherence_after']}")
    print(f"Polyvagal: {result['polyvagal']['label']}")
    print(f"Feedback: {result['feedback']}")

    session.parent_action("encourage")
    summary = session.end()
    print(f"\nSession summary: coherence delta {summary['coherence_delta']:+.3f} | XP: {summary['xp_earned']}")
    print(f"Next lesson: {summary['next_lesson']}")
    print("War Eagle 🦅")
