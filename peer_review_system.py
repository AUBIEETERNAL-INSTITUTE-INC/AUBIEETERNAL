"""
peer_review_system.py — AUBIEETERNAL Peer Review System
========================================================
Structured peer review for Truth Architect and higher degree capstones.

Required for:
  - Truth Architect: ≥1 reviewer outside household
  - Master: ≥2 reviewers, at least one at Master level or above
  - PhD: ≥2 reviewers, at least one holding a degree in the relevant track

Review structure follows academic conventions adapted for sovereign context:
  - Blind review where possible (reviewer sees work, not identity)
  - Structured rubric with scores + narrative
  - Author response round
  - Final accept/revise/reject recommendation
  - All reviews sealed in Bitcoin (permanent record)

Usage:
    from peer_review_system import PeerReviewSystem
    system = PeerReviewSystem()
    submission_id = system.submit_capstone(family_id, title, content, degree_level)
    system.request_review(submission_id, reviewer_family_id)
"""

import os, json, hashlib, datetime, uuid
from pathlib import Path
from typing import Dict, List, Optional
import socket as _socket

def _data_dir() -> Path:
    try:
        _socket.gethostbyname("ollama.startos")
        return Path("/mnt/main")
    except Exception:
        p = Path(os.path.expanduser("~/.aubieeternal/main"))
        p.mkdir(parents=True, exist_ok=True)
        return p

DATA_DIR      = _data_dir()
REVIEWS_DIR   = DATA_DIR / "peer_reviews"
REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
SUBMISSIONS_LOG = REVIEWS_DIR / "submissions.jsonl"
REVIEWS_LOG     = REVIEWS_DIR / "reviews.jsonl"
DECISIONS_LOG   = REVIEWS_DIR / "decisions.jsonl"

# ── Review rubric ─────────────────────────────────────────────────────────────
RUBRIC = {
    "epistemic_rigor": {
        "label": "Epistemic Rigor",
        "description": "Are claims calibrated? Is uncertainty acknowledged? Are premises defended?",
        "max_score": 25,
    },
    "steelman_quality": {
        "label": "Steelman Quality",
        "description": "Does the work seriously engage with the strongest counterarguments?",
        "max_score": 20,
    },
    "originality": {
        "label": "Originality",
        "description": "Does this advance understanding rather than merely summarize existing work?",
        "max_score": 20,
    },
    "practical_contribution": {
        "label": "Practical Contribution",
        "description": "Does this produce something useful for others (code, data, protocol, deployment)?",
        "max_score": 20,
    },
    "clarity": {
        "label": "Clarity and Reproducibility",
        "description": "Could another person understand and build on this work from the document alone?",
        "max_score": 15,
    },
}

DECISIONS = ["accept", "minor_revision", "major_revision", "reject"]

from degrees import DEGREE_REVIEW_REQUIREMENTS  # canonical


class PeerReviewSystem:

    def submit_capstone(
        self,
        family_id: str,
        title: str,
        abstract: str,
        content: str,
        degree_level: str,
        student_name: str = "Sovereign Student",
    ) -> str:
        """Submit a capstone for peer review. Returns submission_id."""
        submission_id = str(uuid.uuid4())[:12]
        content_hash  = hashlib.sha256(content.encode()).hexdigest()

        record = {
            "submission_id": submission_id,
            "family_id":     family_id,
            "student_name":  student_name,
            "title":         title,
            "abstract":      abstract,
            "content_hash":  content_hash,
            "degree_level":  degree_level,
            "submitted_at":  datetime.datetime.now().isoformat(),
            "status":        "awaiting_review",
            "reviews":       [],
            "req":           DEGREE_REVIEW_REQUIREMENTS.get(degree_level, {}),
        }

        # Save full submission
        submission_path = REVIEWS_DIR / f"submission_{submission_id}.json"
        submission_path.write_text(json.dumps({
            **record,
            "content": content,
        }, indent=2))

        # Log without full content
        with open(SUBMISSIONS_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")

        return submission_id

    def get_open_submissions(self, exclude_family: str = "") -> List[Dict]:
        """Get submissions awaiting review (excluding submitter's own)."""
        if not SUBMISSIONS_LOG.exists():
            return []
        submissions = []
        for line in SUBMISSIONS_LOG.read_text().strip().split("\n"):
            try:
                s = json.loads(line)
                if (s.get("status") == "awaiting_review" and
                        s.get("family_id") != exclude_family):
                    submissions.append(s)
            except Exception:
                pass
        return submissions

    def submit_review(
        self,
        submission_id: str,
        reviewer_family_id: str,
        reviewer_name: str,
        scores: Dict[str, int],  # rubric_key → score
        narrative: str,
        decision: str,
        reviewer_coherence: float = 0.75,
    ) -> str:
        """Submit a review for a capstone. Returns review_id."""
        if decision not in DECISIONS:
            raise ValueError(f"Decision must be one of {DECISIONS}")

        # Validate scores
        total_score = 0
        for key, rubric_item in RUBRIC.items():
            score = scores.get(key, 0)
            if score > rubric_item["max_score"]:
                raise ValueError(f"Score for {key} exceeds max {rubric_item['max_score']}")
            total_score += score

        review_id = str(uuid.uuid4())[:12]
        review = {
            "review_id":           review_id,
            "submission_id":       submission_id,
            "reviewer_family_id":  reviewer_family_id,
            "reviewer_name":       reviewer_name,
            "reviewer_coherence":  reviewer_coherence,
            "scores":              scores,
            "total_score":         total_score,
            "max_possible":        sum(r["max_score"] for r in RUBRIC.values()),
            "score_pct":           round(total_score / 100, 3),
            "narrative":           narrative,
            "decision":            decision,
            "reviewed_at":         datetime.datetime.now().isoformat(),
        }

        with open(REVIEWS_LOG, "a") as f:
            f.write(json.dumps(review) + "\n")

        # Update submission status
        self._update_submission_status(submission_id)

        # Seal to Bitcoin
        review_hash = hashlib.sha256(json.dumps(review, sort_keys=True).encode()).hexdigest()
        rune_log = DATA_DIR / "rune_memory.jsonl"
        with open(rune_log, "a") as f:
            f.write(json.dumps({
                "timestamp":    review["reviewed_at"],
                "family_id":    reviewer_family_id,
                "event_type":   "peer_review_submitted",
                "content":      f"REVIEW: {reviewer_name} reviewed {submission_id} — {decision} ({total_score}/100)",
                "shield_sealed": True,
                "seal_hash":    review_hash,
            }) + "\n")

        return review_id

    def get_reviews_for_submission(self, submission_id: str) -> List[Dict]:
        """Get all reviews for a specific submission."""
        if not REVIEWS_LOG.exists():
            return []
        reviews = []
        for line in REVIEWS_LOG.read_text().strip().split("\n"):
            try:
                r = json.loads(line)
                if r.get("submission_id") == submission_id:
                    reviews.append(r)
            except Exception:
                pass
        return reviews

    def _update_submission_status(self, submission_id: str) -> None:
        """Re-evaluate submission status based on reviews received."""
        reviews = self.get_reviews_for_submission(submission_id)

        # Load submission to get degree level
        sub_path = REVIEWS_DIR / f"submission_{submission_id}.json"
        if not sub_path.exists():
            return
        sub = json.loads(sub_path.read_text())
        req = DEGREE_REVIEW_REQUIREMENTS.get(sub.get("degree_level",""), {})

        if len(reviews) < req.get("min_reviewers", 1):
            return  # Not enough reviews yet

        # Check if all decisions are accept/minor_revision
        decisions = [r["decision"] for r in reviews]
        scores    = [r["total_score"] for r in reviews]
        avg_score = sum(scores) / len(scores) if scores else 0

        if ("reject" in decisions or
                avg_score < req.get("min_score", 60)):
            new_status = "needs_major_revision"
        elif "major_revision" in decisions:
            new_status = "needs_major_revision"
        elif "minor_revision" in decisions:
            new_status = "needs_minor_revision"
        else:
            new_status = "accepted"

        sub["status"]    = new_status
        sub["avg_score"] = round(avg_score, 1)
        sub.pop("content", None)  # Don't log content in status update

        # FIX: persist the new status back to the submission record itself
        # (previously only logged to decisions.jsonl, so the UI never updated)
        full = json.loads(sub_path.read_text())
        full["status"]    = new_status
        full["avg_score"] = round(avg_score, 1)
        sub_path.write_text(json.dumps(full, indent=2))

        with open(DECISIONS_LOG, "a") as f:
            f.write(json.dumps({
                "submission_id": submission_id,
                "status":        new_status,
                "avg_score":     round(avg_score, 1),
                "n_reviews":     len(reviews),
                "decided_at":    datetime.datetime.now().isoformat(),
            }) + "\n")

    def get_family_submissions(self, family_id: str) -> List[Dict]:
        """Get all submissions from a family."""
        if not SUBMISSIONS_LOG.exists():
            return []
        submissions = []
        for line in SUBMISSIONS_LOG.read_text().strip().split("\n"):
            try:
                s = json.loads(line)
                if s.get("family_id") == family_id:
                    submissions.append(s)
            except Exception:
                pass
        return submissions

    def get_rubric_display(self) -> List[Dict]:
        """Return rubric in display-friendly format."""
        return [
            {"key": k, **v}
            for k, v in RUBRIC.items()
        ]
