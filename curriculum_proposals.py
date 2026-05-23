"""
curriculum_proposals.py — AUBIEETERNAL Curriculum Submission & Review
=====================================================================
Allows anyone (Tommy, Gabriela, forks, families) to propose new
curriculum tracks or lessons. Each proposal goes through:

  1. Steelman test (strongest argument FOR and AGAINST)
  2. Simulation questions (4 standard checks)
  3. Coherence score gate (≥ 0.70 to pass)
  4. Human review in the app
  5. Merge to family_hud.py (with approval)

Submissions stored in curriculum-proposals/ folder.
Published to LatticeFeed (opt-in) for community comment.

Usage:
    from curriculum_proposals import CurriculumReviewer
    reviewer = CurriculumReviewer()
    reviewer.submit_track("Tommy", "Building & Hurricane Hardening", ...)
    reviewer.get_pending()
"""

import json, datetime, hashlib, os
from pathlib import Path

PROPOSALS_DIR = Path("/mnt/main/repo/curriculum-proposals")
PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

REVIEW_TEMPLATE = {
    "steelman_for":     "",
    "steelman_against": "",
    "sim_q1_reality":   "",
    "sim_q2_falsify":   "",
    "sim_q3_lattice":   "",
    "sim_q4_coherence": "",
    "coherence_score":  0.0,
    "reviewer_notes":   "",
    "status":           "pending",
}

LESSON_TEMPLATE = {
    "key":           "",
    "title":         "",
    "topic":         "",
    "steelman":      "",
    "example":       "",
    "age_hint":      "All ages",
    "xp":            20,
    "rune":          "RUNE",
    "min_coherence": 0.65,
}


class CurriculumReviewer:

    def submit_track(self, author: str, track_name: str, description: str,
                     lessons: list, rationale: str = "",
                     public: bool = True) -> dict:
        """
        Submit a new curriculum track for review.
        lessons: list of LESSON_TEMPLATE dicts
        """
        track_id = hashlib.sha256(
            f"{author}{track_name}{datetime.datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        proposal = {
            "id":          track_id,
            "type":        "track",
            "author":      author,
            "track_name":  track_name,
            "description": description,
            "lessons":     lessons,
            "rationale":   rationale,
            "public":      public,
            "submitted_at": datetime.datetime.now().isoformat(),
            "status":      "pending",
            "review":      REVIEW_TEMPLATE.copy(),
            "comments":    [],
        }

        path = PROPOSALS_DIR / f"{track_id}.json"
        path.write_text(json.dumps(proposal, indent=2))
        print(f"[curriculum] ✅ Track '{track_name}' submitted by {author} — ID: {track_id}")
        return proposal

    def submit_lesson(self, author: str, lesson: dict,
                      target_track: str = "", rationale: str = "") -> dict:
        """Submit a single lesson for addition to an existing track."""
        lesson_id = hashlib.sha256(
            f"{author}{lesson.get('title','')}{datetime.datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        proposal = {
            "id":           lesson_id,
            "type":         "lesson",
            "author":       author,
            "target_track": target_track,
            "lesson":       lesson,
            "rationale":    rationale,
            "submitted_at": datetime.datetime.now().isoformat(),
            "status":       "pending",
            "review":       REVIEW_TEMPLATE.copy(),
            "comments":     [],
        }

        path = PROPOSALS_DIR / f"{lesson_id}.json"
        path.write_text(json.dumps(proposal, indent=2))
        return proposal

    def get_pending(self) -> list:
        pending = []
        for f in PROPOSALS_DIR.glob("*.json"):
            try:
                p = json.loads(f.read_text())
                if p.get("status") == "pending":
                    pending.append(p)
            except Exception:
                pass
        return sorted(pending, key=lambda x: x.get("submitted_at",""), reverse=True)

    def get_all(self, limit: int = 50) -> list:
        all_props = []
        for f in sorted(PROPOSALS_DIR.glob("*.json"),
                        key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
            try:
                all_props.append(json.loads(f.read_text()))
            except Exception:
                pass
        return all_props

    def add_review(self, proposal_id: str, review: dict) -> bool:
        path = PROPOSALS_DIR / f"{proposal_id}.json"
        if not path.exists():
            return False
        try:
            p = json.loads(path.read_text())
            p["review"].update(review)
            path.write_text(json.dumps(p, indent=2))
            return True
        except Exception:
            return False

    def add_comment(self, proposal_id: str, author: str, comment: str) -> bool:
        path = PROPOSALS_DIR / f"{proposal_id}.json"
        if not path.exists():
            return False
        try:
            p = json.loads(path.read_text())
            p["comments"].append({
                "author":    author,
                "comment":   comment,
                "timestamp": datetime.datetime.now().isoformat(),
            })
            path.write_text(json.dumps(p, indent=2))
            return True
        except Exception:
            return False

    def approve(self, proposal_id: str) -> bool:
        path = PROPOSALS_DIR / f"{proposal_id}.json"
        if not path.exists():
            return False
        try:
            p = json.loads(path.read_text())
            p["status"]      = "approved"
            p["approved_at"] = datetime.datetime.now().isoformat()
            path.write_text(json.dumps(p, indent=2))
            return True
        except Exception:
            return False

    def reject(self, proposal_id: str, reason: str = "") -> bool:
        path = PROPOSALS_DIR / f"{proposal_id}.json"
        if not path.exists():
            return False
        try:
            p = json.loads(path.read_text())
            p["status"]           = "rejected"
            p["rejected_at"]      = datetime.datetime.now().isoformat()
            p["rejection_reason"] = reason
            path.write_text(json.dumps(p, indent=2))
            return True
        except Exception:
            return False

    def get_review_template(self) -> dict:
        """Return a blank review template for the UI."""
        return {
            "steelman_for":     "The strongest argument FOR this curriculum is...",
            "steelman_against": "The strongest argument AGAINST this curriculum is...",
            "sim_q1_reality":   "If this curriculum is taught, what does it imply for how families understand the world?",
            "sim_q2_falsify":   "What outcome would prove this curriculum is harmful or wrong?",
            "sim_q3_lattice":   "Is this consistent with AUBIEETERNAL's core values (antifragility, sovereignty, steelmanning)?",
            "sim_q4_coherence": "Does this increase or decrease overall family coherence?",
            "coherence_score":  0.0,
            "reviewer_notes":   "",
        }

    def export_approved_to_hud(self) -> list:
        """
        Export all approved single-lesson proposals as family_hud.py dict entries.
        Returns list of Python dict strings ready to paste.
        """
        approved = [p for p in self.get_all() if p.get("status") == "approved" and p.get("type") == "lesson"]
        exports  = []
        for p in approved:
            lesson = p.get("lesson", {})
            key    = lesson.get("key","unknown")
            entry  = f'''    "{key}": {{
        "title":       "{lesson.get('title','')}",
        "topic":       "{lesson.get('topic','')}",
        "steelman":    "{lesson.get('steelman','')}",
        "example":     "{lesson.get('example','')}",
        "age_hint":    "{lesson.get('age_hint','All ages')}",
        "xp":          {lesson.get('xp',20)}, "rune": "{lesson.get('rune','RUNE')}", "min_coherence": {lesson.get('min_coherence',0.65)},
    }},'''
            exports.append({"key": key, "author": p.get("author",""), "entry": entry})
        return exports


# ── Pre-seed Tommy and Gabriela's tracks as approved proposals ─────────────────
def seed_initial_proposals():
    """Write the initial community track submissions to curriculum-proposals/."""
    reviewer = CurriculumReviewer()
    existing = {p["id"] for p in reviewer.get_all()}

    # Tommy's Building Track seed
    tommy_id = "tommy_building_seed"
    if not (PROPOSALS_DIR / f"{tommy_id}.json").exists():
        tommy = {
            "id":          tommy_id,
            "type":        "track",
            "author":      "Tommy",
            "track_name":  "Building & Hurricane Hardening",
            "description": "Hands-on track teaching hurricane hardening, construction fundamentals, and community resilience from a practicing builder's perspective.",
            "rationale":   "Tommy has direct field experience hardening homes on the Gulf Coast. This track turns his knowledge into teachable modules that directly reduce insurance risk for families.",
            "lessons":     [
                {"key":"building-1","title":"Building L1 — How Houses Fail"},
                {"key":"building-2","title":"Building L2 — Wind Load Physics"},
                {"key":"building-3","title":"Building L3 — The $500 Retrofit"},
                {"key":"building-4","title":"Building L4 — Insurance & Building Codes"},
                {"key":"building-5","title":"Building L5 — Community Resilience ★"},
            ],
            "submitted_at": datetime.datetime.now().isoformat(),
            "status":      "approved",
            "approved_at": datetime.datetime.now().isoformat(),
            "public":      True,
            "review": {
                "steelman_for":     "Real-world building knowledge directly reduces hurricane losses and insurance premiums — measurable ROI for every family.",
                "steelman_against": "Hands-on building skills are hard to teach digitally and may create false confidence without physical practice.",
                "sim_q1_reality":   "If families understand wind physics, they make better hardening investments and demand better insurance products.",
                "sim_q2_falsify":   "If hardened homes don't show measurable premium reductions, the insurance incentive argument fails.",
                "sim_q3_lattice":   "Yes — antifragile (hardening strengthens under stress), sovereign (DIY reduces dependence), skin in the game (Tommy has done this work).",
                "sim_q4_coherence": "Increases — adds a practical, measurable track that connects to Legal Literacy and Insurance tracks downstream.",
                "coherence_score":  0.92,
                "reviewer_notes":   "Pre-approved — Tommy's direct field experience qualifies this as tutor-grade content.",
            },
            "comments": [],
        }
        (PROPOSALS_DIR / f"{tommy_id}.json").write_text(json.dumps(tommy, indent=2))

    # Gabriela's Baking Track seed
    gaby_id = "gabriela_baking_seed"
    if not (PROPOSALS_DIR / f"{gaby_id}.json").exists():
        gabriela = {
            "id":          gaby_id,
            "type":        "track",
            "author":      "Gabriela",
            "track_name":  "Deep Baking & Self-Sufficiency",
            "description": "A track on fermentation, traditional food preparation, nutrition science, and local food economics — taught through the lens of antifragility and family resilience.",
            "rationale":   "Self-sufficiency in food is a foundational sovereignty skill. Gabriela's deep baking practice makes this hands-on and immediately applicable.",
            "lessons":     [
                {"key":"baking-1","title":"Deep Baking L1 — Fermentation is Antifragile"},
                {"key":"baking-2","title":"Deep Baking L2 — Local Food Systems"},
                {"key":"baking-3","title":"Deep Baking L3 — Nutrition as Antifragility"},
                {"key":"baking-4","title":"Deep Baking L4 — Self-Sufficiency Economics ★"},
            ],
            "submitted_at": datetime.datetime.now().isoformat(),
            "status":      "approved",
            "approved_at": datetime.datetime.now().isoformat(),
            "public":      True,
            "review": {
                "steelman_for":     "Food sovereignty reduces family vulnerability to supply chain failures and builds genuine self-sufficiency — fully Lindy.",
                "steelman_against": "Time cost of home food production is prohibitive for working families with two incomes.",
                "sim_q1_reality":   "Families who produce food understand inputs, seasonality, and nutrition at a deeper level — better health + resilience decisions.",
                "sim_q2_falsify":   "If home-produced food consistently costs more in real terms (time-adjusted) than store-bought, the economics don't hold.",
                "sim_q3_lattice":   "Yes — antifragile (fermentation improves with time/stress), sovereign (reduces dependence), Lindy (traditional methods are millennia old).",
                "sim_q4_coherence": "Increases — practical self-sufficiency skills compound with building and legal literacy tracks.",
                "coherence_score":  0.90,
                "reviewer_notes":   "Pre-approved — Gabriela's direct practice qualifies this as lived-experience curriculum.",
            },
            "comments": [],
        }
        (PROPOSALS_DIR / f"{gaby_id}.json").write_text(json.dumps(gabriela, indent=2))

    print("[curriculum] ✅ Initial proposals seeded (Tommy + Gabriela)")
