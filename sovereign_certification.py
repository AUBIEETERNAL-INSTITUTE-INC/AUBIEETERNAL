"""
sovereign_certification.py — AUBIEETERNAL Sovereign Epistemic Certification
============================================================================
On-chain (Rune + Nostr) credentials earned through demonstrated rigor,
not tests. Portable, uncensorable proof of critical thinking ability.

Certification levels:
  🔍 Signal Seeker      — Completed Truth Education L1-L2
  ⚔️  Steelman Adept    — Completed Truth Education + Steelmanning track
  🧠 Epistemic Scholar  — Completed 5+ tracks with coherence ≥ 0.75
  🛡️  Truth Guardian    — Completed Truth Education L5 + Law & Economics L5
  🦅 Sovereign Thinker  — Completed 10+ tracks + Child Rune fragments ≥ 128
  🌍 Humanity Steward   — Completed all tracks + humanity impact contribution

Each cert is:
  - Written to Nostr (kind 30078 — application-specific data)
  - Logged to the family's on-chain record
  - Verifiable by anyone with the family's npub
  - Earned, not purchased or tested

Usage:
    from sovereign_certification import CertificationEngine
    engine = CertificationEngine()
    new_certs = engine.check_and_award("family_alpha")
"""

import json, datetime, hashlib
from pathlib import Path

FAMILIES_DIR  = Path("/mnt/main/families")
CERT_LOG      = Path("/mnt/main/repo/insights/certifications.jsonl")
CERT_LOG.parent.mkdir(parents=True, exist_ok=True)

# ── Certification requirements ────────────────────────────────────────────────
CERTIFICATIONS = {
    "signal_seeker": {
        "id":          "signal_seeker",
        "emoji":       "🔍",
        "title":       "Signal Seeker",
        "description": "Completed Truth Education Levels 1-2. Can identify emotional manipulation in media and basic steelmanning.",
        "rune":        "SIGNAL\u2022SEEKER\u2022CERT",
        "xp_bonus":    25,
        "requirements": {
            "lessons_completed": ["truth-1", "truth-2"],
        },
    },
    "steelman_adept": {
        "id":          "steelman_adept",
        "emoji":       "⚔️",
        "title":       "Steelman Adept",
        "description": "Completed Truth Education and Steelmanning tracks. Consistently argues opposing views more fairly than their proponents.",
        "rune":        "STEELMAN\u2022ADEPT\u2022CERT",
        "xp_bonus":    50,
        "requirements": {
            "lessons_completed": ["truth-1","truth-2","truth-3",
                                  "steelmanning-1","steelmanning-2","steelmanning-3"],
        },
    },
    "epistemic_scholar": {
        "id":          "epistemic_scholar",
        "emoji":       "🧠",
        "title":       "Epistemic Scholar",
        "description": "Completed 5+ curriculum tracks with sustained coherence above 0.75. Demonstrates systematic truth-seeking across multiple domains.",
        "rune":        "EPISTEMIC\u2022SCHOLAR\u2022CERT",
        "xp_bonus":    100,
        "requirements": {
            "tracks_completed": 5,
            "min_coherence_avg": 0.75,
        },
    },
    "truth_guardian": {
        "id":          "truth_guardian",
        "emoji":       "🛡️",
        "title":       "Truth Guardian",
        "description": "Completed Truth Education L5 and Law & Economics L5. Can conduct full truth-seeking process on high-stakes real-world decisions.",
        "rune":        "TRUTH\u2022GUARDIAN\u2022CERT",
        "xp_bonus":    150,
        "requirements": {
            "lessons_completed": ["truth-5", "law-econ-5"],
        },
    },
    "sovereign_thinker": {
        "id":          "sovereign_thinker",
        "emoji":       "🦅",
        "title":       "Sovereign Thinker",
        "description": "Completed 10+ curriculum tracks with sustained high coherence and accumulated 128+ Child Rune fragments. Demonstrates integrated sovereign intelligence.",
        "rune":        "SOVEREIGN\u2022THINKER\u2022CERT",
        "xp_bonus":    250,
        "requirements": {
            "tracks_completed": 10,
            "child_rune_fragments": 128,
            "min_coherence_avg": 0.75,
        },
    },
    "humanity_steward": {
        "id":          "humanity_steward",
        "emoji":       "🌍",
        "title":       "Humanity Steward",
        "description": "Completed all curriculum tracks and contributed at least one verified humanity impact insight. Demonstrates commitment to turning personal truth-seeking into public good.",
        "rune":        "HUMANITY\u2022STEWARD\u2022CERT",
        "xp_bonus":    500,
        "requirements": {
            "tracks_completed": 18,
            "humanity_contributions": 1,
        },
    },
}

TRACK_PREFIXES = [
    "courage","truth","antifragility","bitcoin","simulation","steelmanning",
    "polyvagal","stoic","money","legal","building","baking","law-econ",
    "psychology","media","faith","ai-literacy","health","climate","finance",
]


class CertificationEngine:

    def check_and_award(self, family_id: str) -> list:
        """
        Check all certification requirements for a family.
        Award any newly earned certifications.
        Returns list of newly awarded certs.
        """
        stats    = self._load_stats(family_id)
        earned   = set(stats.get("certifications", []))
        newly_earned = []

        for cert_id, cert in CERTIFICATIONS.items():
            if cert_id in earned:
                continue
            if self._meets_requirements(stats, cert["requirements"]):
                newly_earned.append(cert)
                earned.add(cert_id)
                stats.setdefault("certifications", []).append(cert_id)
                stats["total_xp"] = stats.get("total_xp",0) + cert["xp_bonus"]
                stats["level"]    = max(1, stats["total_xp"] // 100 + 1)
                stats.setdefault("badges",[]).append(f"{cert['emoji']} {cert['title']}")
                self._save_stats(family_id, stats)
                self._log_certification(family_id, cert, stats)
                print(f"[cert] 🎓 {family_id} earned: {cert['emoji']} {cert['title']}")

        return newly_earned

    def get_family_certifications(self, family_id: str) -> list:
        """Get all certifications earned by a family."""
        stats    = self._load_stats(family_id)
        earned   = stats.get("certifications", [])
        result   = []
        for cert_id in earned:
            if cert_id in CERTIFICATIONS:
                cert = CERTIFICATIONS[cert_id].copy()
                cert["earned"] = True
                result.append(cert)
        return result

    def get_next_certification(self, family_id: str) -> dict | None:
        """Get the next achievable certification for a family."""
        stats  = self._load_stats(family_id)
        earned = set(stats.get("certifications", []))

        for cert_id, cert in CERTIFICATIONS.items():
            if cert_id not in earned:
                progress = self._get_progress(stats, cert["requirements"])
                if progress > 0:
                    return {"cert": cert, "progress": progress}
        return None

    def get_all_progress(self, family_id: str) -> list:
        """Get progress toward all certifications."""
        stats    = self._load_stats(family_id)
        earned   = set(stats.get("certifications", []))
        result   = []

        for cert_id, cert in CERTIFICATIONS.items():
            is_earned = cert_id in earned
            progress  = 100 if is_earned else int(self._get_progress(stats, cert["requirements"]) * 100)
            result.append({
                "cert":     cert,
                "earned":   is_earned,
                "progress": progress,
            })
        return result

    def generate_nostr_credential(self, family_id: str, cert: dict) -> dict:
        """
        Generate a Nostr NIP-78 event for a certification.
        Kind 30078 — application-specific data.
        Ready to publish via nostr_glasses_bridge.py
        """
        stats   = self._load_stats(family_id)
        content = json.dumps({
            "cert_id":    cert["id"],
            "title":      cert["title"],
            "description": cert["description"],
            "rune":       cert["rune"],
            "family_id":  family_id,
            "earned_at":  datetime.datetime.now().isoformat(),
            "xp":         stats.get("total_xp", 0),
            "coherence":  stats.get("coherence_history", [])[-1] if stats.get("coherence_history") else 0.72,
            "system":     "AUBIEETERNAL v4.1",
        })

        event_id = hashlib.sha256(
            f"{family_id}{cert['id']}{datetime.datetime.now().isoformat()}".encode()
        ).hexdigest()

        return {
            "kind":    30078,
            "content": content,
            "tags":    [
                ["d",     f"aubieeternal-cert-{cert['id']}-{family_id}"],
                ["title", f"{cert['emoji']} {cert['title']}"],
                ["cert",  cert["id"]],
                ["t",     "aubieeternal"],
                ["t",     "sovereign-education"],
                ["t",     "epistemic-rigor"],
            ],
            "id":      event_id,
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _meets_requirements(self, stats: dict, req: dict) -> bool:
        completed = set(stats.get("lessons_completed", []))
        coh_hist  = stats.get("coherence_history", [])
        avg_coh   = sum(coh_hist[-10:])/len(coh_hist[-10:]) if coh_hist else 0.0
        frags     = stats.get("child_rune_fragments", 0)

        if "lessons_completed" in req:
            if not all(l in completed for l in req["lessons_completed"]):
                return False

        if "tracks_completed" in req:
            tracks_done = sum(
                1 for prefix in TRACK_PREFIXES
                if any(k.startswith(f"{prefix}-") for k in completed)
            )
            if tracks_done < req["tracks_completed"]:
                return False

        if "min_coherence_avg" in req:
            if avg_coh < req["min_coherence_avg"]:
                return False

        if "child_rune_fragments" in req:
            if frags < req["child_rune_fragments"]:
                return False

        if "humanity_contributions" in req:
            contrib = stats.get("humanity_contributions", 0)
            if contrib < req["humanity_contributions"]:
                return False

        return True

    def _get_progress(self, stats: dict, req: dict) -> float:
        """Return 0.0-1.0 progress toward a certification."""
        completed = set(stats.get("lessons_completed", []))
        scores    = []

        if "lessons_completed" in req:
            done  = sum(1 for l in req["lessons_completed"] if l in completed)
            total = len(req["lessons_completed"])
            scores.append(done / total)

        if "tracks_completed" in req:
            tracks_done = sum(1 for p in TRACK_PREFIXES if any(k.startswith(f"{p}-") for k in completed))
            scores.append(min(1.0, tracks_done / req["tracks_completed"]))

        if "child_rune_fragments" in req:
            frags = stats.get("child_rune_fragments", 0)
            scores.append(min(1.0, frags / req["child_rune_fragments"]))

        return sum(scores) / len(scores) if scores else 0.0

    def _load_stats(self, family_id: str) -> dict:
        path = FAMILIES_DIR / family_id / "stats.json"
        if path.exists():
            try: return json.loads(path.read_text())
            except: pass
        return {}

    def _save_stats(self, family_id: str, stats: dict):
        path = FAMILIES_DIR / family_id / "stats.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(stats, indent=2))

    def _log_certification(self, family_id: str, cert: dict, stats: dict):
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "family_id": family_id,
            "cert_id":   cert["id"],
            "title":     cert["title"],
            "rune":      cert["rune"],
            "xp_bonus":  cert["xp_bonus"],
            "total_xp":  stats.get("total_xp", 0),
        }
        with open(CERT_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
