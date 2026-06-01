"""
test_pipeline.py — proves the consolidated university works end-to-end.

Runs ONE synthetic student through the whole pipeline against the REAL
peer_review_system and transcript_system modules (now importing degrees.py),
and asserts every module agrees on what degrees exist and when they're earned.
"""
import os, json, tempfile, importlib, sys
from pathlib import Path

# Isolate all module I/O to a throwaway dir
TMP = Path(tempfile.mkdtemp(prefix="aubie_test_"))
os.environ["HOME"] = str(TMP)  # _data_dir() falls back to ~/.aubieeternal/main

import degrees
from peer_review_system import PeerReviewSystem, RUBRIC
from transcript_system import TranscriptGenerator, DATA_DIR

PASS, FAIL = "✅", "❌"
ok = True
def check(label, cond):
    global ok
    ok = ok and cond
    print(f"  {PASS if cond else FAIL} {label}")

print("\n=== 1. Single source of truth ===")
check("degrees.py defines 7 degrees", len(degrees.DEGREES) == 7)
check("transcript_system uses the same list object",
      importlib.import_module("transcript_system").DEGREES is degrees.DEGREES)
pr_reqs = importlib.import_module("peer_review_system").DEGREE_REVIEW_REQUIREMENTS
check("peer_review requirements come from degrees.py",
      pr_reqs is degrees.DEGREE_REVIEW_REQUIREMENTS)

print("\n=== 2. Credit math is consistent ===")
# three 15/18/22-xp lessons: must be sum(xp)//10 == 5 everywhere now
xps = [15, 18, 22]
check("credits_from_xp(sum)==5", degrees.credits_from_xp(sum(xps)) == 5)

print("\n=== 3. A student completes lessons and earns degrees ===")
# Simulate a Truth Architect: enough credits + coherence
total_xp, coherence = 1300, 0.78          # 130 credits, coh 0.78
earned = degrees.degrees_earned(degrees.credits_from_xp(total_xp), coherence)
earned_ids = {d["id"] for d in earned}
check("earns Sovereign Associate (60cr/0.68)", "sovereign_associate" in earned_ids)
check("earns Truth Architect (120cr/0.75)", "truth_architect" in earned_ids)
check("does NOT yet earn Master (needs 180cr/0.82)", "master_epistemic_rigor" not in earned_ids)
hi = degrees.highest_degree(degrees.credits_from_xp(total_xp), coherence)
check("highest degree is Truth Architect", hi["id"] == "truth_architect")

print("\n=== 4. PhD is gated on the Child Rune (256) ===")
phd_no = degrees.degrees_earned(300, 0.95, child_rune_confirmations=10)
phd_yes = degrees.degrees_earned(300, 0.95, child_rune_confirmations=256)
check("PhD blocked at 10 rune confirmations",
      "eternal_founder" not in {d["id"] for d in phd_no})
check("PhD granted at 256 rune confirmations",
      "eternal_founder" in {d["id"] for d in phd_yes})

print("\n=== 5. Peer review pipeline (real module) ===")
prs = PeerReviewSystem()
sub_id = prs.submit_capstone(
    family_id="fam_test", title="Falsifying a Simulation-Glitch Claim",
    abstract="A rigorous falsification.", content="...body...",
    degree_level="truth_architect", student_name="Gaby")
check("capstone submitted", isinstance(sub_id, str) and len(sub_id) > 0)
# Truth Architect needs 1 reviewer, min_score 60. Give a 78.
scores = {"epistemic_rigor": 20, "steelman_quality": 16, "originality": 16,
          "practical_contribution": 16, "clarity": 10}  # = 78
prs.submit_review(sub_id, "fam_reviewer", "Reviewer One", scores,
                  "Strong, well-calibrated.", "accept")
sub = json.loads((DATA_DIR / "peer_reviews" / f"submission_{sub_id}.json").read_text())
check("submission accepted after qualifying review", sub["status"] == "accepted")

print("\n=== 6. Transcript generates + degree award is consistent ===")
# Write the student's state where transcript_system reads it
(DATA_DIR).mkdir(parents=True, exist_ok=True)
(DATA_DIR / "app_state.json").write_text(json.dumps({
    "lessons_completed": ["courage-1", "courage-2", "truth-1"],
    "coherence": {"current": 0.78},
}))
gen = TranscriptGenerator(family_id="fam_test", student_name="Gaby")
tx = gen.generate()
check("transcript has a SHA-256 hash", len(tx["sha256"]) == 64)
check("transcript credit math matches degrees.credits_from_xp",
      tx["academic_record"]["total_credits"] ==
      degrees.credits_from_xp(tx["academic_record"]["total_xp"]))

print("\n" + ("=" * 48))
print(f"  {'ALL CHECKS PASSED' if ok else 'SOME CHECKS FAILED'}")
print("=" * 48)
sys.exit(0 if ok else 1)
