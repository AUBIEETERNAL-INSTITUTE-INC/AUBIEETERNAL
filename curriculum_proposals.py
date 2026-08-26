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

# The shared, cross-instance "commons" feed (see publish_to_commons/
# pull_from_commons below) - the canonical public AUBIEETERNAL repo's own
# published curriculum proposals, readable by any separately-run instance
# (a different family's install, not just this machine).
COMMONS_FEED_URL = (
    "https://raw.githubusercontent.com/AUBIEETERNAL-INSTITUTE-INC/AUBIEETERNAL/main/"
    "epistemic_commons/api/curriculum_proposals.json"
)

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


def merge_approved_proposal(proposal: dict) -> bool:
    """Folds an approved lesson/track proposal into curriculum.py's live
    tree via curriculum_extra.json (see curriculum.py's `_load_extra_tracks`)
    — every process reading curriculum.py picks it up on its next call, no
    source edit or restart needed. Called from `approve()` above; also
    callable standalone. Never raises — a merge failure just means the
    proposal stays "approved" without yet being teachable, logged for
    follow-up rather than blocking the approval itself."""
    try:
        import sys as _sys
        _repo_dir = str(Path(__file__).parent)
        if _repo_dir not in _sys.path:
            _sys.path.insert(0, _repo_dir)
        import curriculum

        extra_path = curriculum.EXTRA_PATH
        extra_path.parent.mkdir(parents=True, exist_ok=True)
        tracks = []
        if extra_path.exists():
            try:
                loaded = json.loads(extra_path.read_text())
                if isinstance(loaded, list):
                    tracks = loaded
            except Exception:
                tracks = []

        ptype = proposal.get("type")

        if ptype == "lesson":
            lesson = proposal.get("lesson", {})
            key, title = lesson.get("key"), lesson.get("title")
            if not key or not title:
                return False
            target_raw = (proposal.get("target_track") or "community").strip()
            level = [key, title, lesson.get("age_hint", "All ages"), int(lesson.get("xp", 20) or 20)]

            # Match target_track against a real track by id or display label
            # (emoji/punctuation stripped) before minting a new one — an
            # LLM- or human-typed target like "Bitcoin Sovereignty" or
            # "💡 Wonder" should land on the existing track, not spawn a
            # near-duplicate "🧩 Bitcoin Sovereignty".
            target_slug = target_raw.lower().replace(" ", "-") or "community"
            target_norm = target_raw.lower()
            match_id = None
            for tid, label in curriculum.track_names():
                label_words = "".join(c for c in label if c.isalnum() or c.isspace()).strip().lower()
                if target_slug == tid or target_norm == label_words \
                   or (label_words and (label_words in target_norm or target_norm in label_words)):
                    match_id = tid
                    break
            target_id = match_id or target_slug

            entry = next((t for t in tracks if t.get("track_id") == target_id), None)
            if entry is None:
                base_name = next((label for tid, label in curriculum.track_names() if tid == target_id), None)
                entry = {"track_id": target_id, "track": base_name or f"🧩 {target_raw.title()}",
                         "color": "#00c9ff", "levels": []}
                tracks.append(entry)
            if not any(lvl[0] == key for lvl in entry["levels"]):
                entry["levels"].append(level)

        elif ptype == "track":
            track_name = proposal.get("track_name", "New Track")
            track_id   = track_name.strip().lower().replace(" ", "-").replace("'", "") or "new-track"
            levels = []
            for i, l in enumerate(proposal.get("lessons", [])):
                key   = l.get("key") or f"{track_id}-{i + 1}"
                title = l.get("title", key)
                levels.append([key, title, l.get("age_hint", "All ages"), int(l.get("xp", 20) or 20)])
            if not levels:
                return False  # a track with no lessons yet isn't teachable

            entry = next((t for t in tracks if t.get("track_id") == track_id), None)
            if entry is None:
                entry = {"track_id": track_id, "track": f"🧩 {track_name}", "color": "#00c9ff", "levels": []}
                tracks.append(entry)
            existing_keys = {lvl[0] for lvl in entry["levels"]}
            entry["levels"].extend(lv for lv in levels if lv[0] not in existing_keys)

        else:
            return False

        extra_path.write_text(json.dumps(tracks, indent=2))
        return True
    except Exception as e:
        print(f"[curriculum_proposals] merge_approved_proposal failed: {e}")
        return False


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
            # Fold it into the live curriculum immediately (see
            # merge_approved_proposal below) — approving here is meant to
            # make the lesson teachable, not just flip a status flag that
            # then needs a manual copy-paste into family_hud.py.
            p["merged_to_curriculum"] = merge_approved_proposal(p)
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

    def publish_to_commons(self, proposal_id: str) -> bool:
        """Publishes an already-APPROVED proposal to the same public, CC0
        Epistemic Commons feed epistemic_commons_api.py already writes
        (epistemic_commons/api/curriculum_proposals.json, inside the git
        repo) - the swarm's existing GitHub auto-push is what actually
        makes it public, this doesn't need its own push mechanism. This is
        a deliberately separate, explicit action from approve() - approving
        a proposal makes it live on THIS instance; publishing is a second,
        conscious choice to also offer it to every other AUBIEETERNAL
        instance via pull_from_commons() below. Never automatic."""
        path = PROPOSALS_DIR / f"{proposal_id}.json"
        if not path.exists():
            return False
        try:
            p = json.loads(path.read_text())
        except Exception:
            return False
        if p.get("status") != "approved":
            return False  # only vetted, already-locally-approved content goes public

        try:
            from epistemic_commons_api import API_DIR
        except Exception:
            API_DIR = Path("/mnt/main/repo/epistemic_commons/api")
        API_DIR.mkdir(parents=True, exist_ok=True)

        commons_path = API_DIR / "curriculum_proposals.json"
        entries = []
        if commons_path.exists():
            try:
                loaded = json.loads(commons_path.read_text())
                if isinstance(loaded, list):
                    entries = loaded
            except Exception:
                entries = []

        if not any(e.get("id") == proposal_id for e in entries):
            entries.append({
                "id": proposal_id, "type": p.get("type"),
                "author": p.get("author"), "track_name": p.get("track_name"),
                "target_track": p.get("target_track"),
                "lesson": p.get("lesson"), "lessons": p.get("lessons"),
                "rationale": p.get("rationale"),
                "approved_at": p.get("approved_at"),
                "coherence_score": p.get("review", {}).get("coherence_score"),
                "license": "CC0",
            })
            commons_path.write_text(json.dumps(entries, indent=2))

        p["published_to_commons"]    = True
        p["published_to_commons_at"] = datetime.datetime.now().isoformat()
        path.write_text(json.dumps(p, indent=2))
        return True

    def pull_from_commons(self, feed_url: str = COMMONS_FEED_URL) -> dict:
        """Fetches the shared commons feed (default: the canonical public
        AUBIEETERNAL repo's feed) and re-submits any not-already-seen
        entries as new LOCAL PENDING proposals - never auto-approved, so a
        human on THIS instance still has to review and say yes before
        anything from another instance reaches this instance's real
        curriculum (curriculum_extra.json only changes on approve(), same
        as any other proposal). Safe to call repeatedly - already-imported
        entries are skipped by their commons id."""
        try:
            import requests
            r = requests.get(feed_url, timeout=15)
            r.raise_for_status()
            remote_entries = r.json()
            if not isinstance(remote_entries, list):
                return {"ok": False, "reason": "unexpected feed format"}
        except Exception as e:
            return {"ok": False, "reason": str(e)}

        already_seen = set()
        for p in self.get_all(1000):
            src = p.get("commons_source_id")
            if src:
                already_seen.add(src)

        added = []
        for entry in remote_entries:
            source_id = entry.get("id")
            if not source_id or source_id in already_seen:
                continue
            author = f"{entry.get('author', '?')} (via commons)"
            if entry.get("type") == "lesson" and entry.get("lesson"):
                prop = self.submit_lesson(author, entry["lesson"],
                                           entry.get("target_track", ""), entry.get("rationale", ""))
            elif entry.get("type") == "track" and entry.get("lessons"):
                prop = self.submit_track(author, entry.get("track_name", "Imported Track"),
                                          entry.get("description", ""), entry["lessons"],
                                          entry.get("rationale", ""))
            else:
                continue
            prop["commons_source_id"] = source_id
            (PROPOSALS_DIR / f"{prop['id']}.json").write_text(json.dumps(prop, indent=2))
            added.append(prop["id"])

        return {"ok": True, "added": len(added), "proposal_ids": added, "feed_total": len(remote_entries)}

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
