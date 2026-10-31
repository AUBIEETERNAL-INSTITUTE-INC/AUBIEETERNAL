"""Standalone check (no Ollama, no network, temp dirs only): the Sunday follow-up turns a new
school-report page into ONE pending proposal with sources, files an #institute idea, skips
near-duplicates, retries when the model is down. Run: python3 test_intel_to_proposals.py"""
import json, sys, tempfile, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import intel_to_proposals as itp, curriculum_autogen as ca, curriculum_proposals as cp, idea_inbox as ii, curriculum
fails = 0
def check(name, ok):
    global fails; fails += not ok; print(("PASS " if ok else "FAIL ") + name)
tmp = Path(tempfile.mkdtemp())
itp.INTEL_DIR = tmp; itp.STATE_PATH = tmp / "state.json"
cp.PROPOSALS_DIR = tmp / "props"; cp.PROPOSALS_DIR.mkdir()
ii.DOORS = {d: tmp / f"{d}.md" for d in ("institute", "business", "personal", "inbox")}
curriculum.all_titles_and_keys = lambda: [("k", "Needs vs Wants", "💰 Money & Mindset")]
shutil.copy("/srv/institute/competitive_intel/2026-10-25.md", tmp / "2026-10-25.md")
pages = itp.parse_report((tmp / "2026-10-25.md").read_text())
st = {(p["school"], p["page"]): p["status"] for p in pages}
check("parse: Synthesis new, IXL Homepage changed, Acton unchanged, CPALMS skipped",
      st[("Synthesis", "Model")] == "new" and st[("IXL", "Homepage")] == "changed"
      and st[("Acton Academy", "Model")] == "unchanged" and st[("Florida B.E.S.T. Standards (CPALMS)", "Homepage")] == "skipped")
good = {"key": "learning-path-map", "title": "Draw Your Learning Path", "topic": "Plan the next five skills you will learn in order.",
        "steelman": "s", "steelman_for": "Seeing the path ahead helps a learner choose what to practice next with purpose.",
        "steelman_against": "A fixed path can ignore detours where the most interesting learning often happens.",
        "example_kind": "made-up", "example": "Imagine Kai, 9, who draws five stepping stones for fractions.",
        "activity": "Draw five stones and write one skill on each.", "check_questions": ["a?", "b?", "c?"],
        "age_hint": "8+", "xp": 20, "target_track": "How We Learn", "rationale": "Borrowed from IXL's learning path."}
replies = []
ca._call_ollama = lambda prompt: replies.pop(0) if replies else None
ca._recent_proposals = lambda n=30: []
# model down -> nothing created, report not marked processed
r = itp.run()
check("model down -> nothing created, retry next run", r["created"] == [] and r["model_failures"] == 3
      and "2026-10-25.md" not in json.loads(itp.STATE_PATH.read_text())["processed_reports"])
dup = {**good, "key": "nw2", "title": "Needs vs Wants"}
replies[:] = [json.dumps(good), json.dumps(dup), json.dumps(dup), json.dumps({**good, "key": "third", "title": "Teach It Back", "topic": "Explain a skill to someone younger."})]
r = itp.run()
props = [json.loads(f.read_text()) for f in cp.PROPOSALS_DIR.glob("*.json")]
check(f"2 pending proposals created, 1 near-duplicate skipped ({r})", len(r["created"]) == 2 and len(r["skipped"]) == 1)
check("all pending, with sources + report path", all(p["status"] == "pending" and p["sources"][0]["url"].startswith("https://")
      and p["source_reports"] for p in props))
check("rationale names the school", all(any(s in p["rationale"] for s in ("Synthesis", "IXL", "Alpha")) for p in props))
check("ideas.md got 3 #institute lines with URLs", ii.DOORS["institute"].read_text().count("https://") == 3)
check("business door untouched", not ii.DOORS["business"].exists())
check("second run is a no-op", itp.run()["reason"] == "already processed")
print(f"\n{fails} failures")
