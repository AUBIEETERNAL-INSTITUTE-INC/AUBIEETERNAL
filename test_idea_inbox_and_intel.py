"""Standalone check (no Ollama, no network): idea inbox files ideas by tag; autogen
borrows structure from the weekly school report and founder ideas; self_audit flags a
school_monitor run where a source failed. Run: python3 test_idea_inbox_and_intel.py"""
import json, sys, tempfile, datetime
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / "aubieeternal_build"))
import idea_inbox as ii, curriculum_autogen as ca
fails = 0
def check(name, ok):
    global fails; fails += not ok; print(("PASS " if ok else "FAIL ") + name)

tmp = Path(tempfile.mkdtemp())
ii.DOORS = {d: tmp / f"{d}.md" for d in ("institute", "business", "personal", "inbox")}
r = ii.handle_message("!idea #institute lesson: build a straw bridge and test how much it holds", "discord")
check(f"#institute idea saved ({r})", "institute" in r and "straw bridge" in ii.DOORS["institute"].read_text())
r = ii.handle_message("!idea the kiosk should say good morning", "simplex")
check("untagged goes to inbox with a hint", "inbox" in r and "#institute" in r and ii.DOORS["inbox"].exists())
ii.handle_message("!idea #biz flat-fee local AI setup", "discord")
check("#biz goes to business door", "flat-fee" in ii.DOORS["business"].read_text())
check("institute door has no business idea", "flat-fee" not in ii.DOORS["institute"].read_text())
check("!ideas lists institute ideas", "straw bridge" in ii.handle_message("!ideas", "discord"))
check("non-commands ignored", ii.handle_message("hello aubie") is None)
check("empty idea rejected", "Empty" in ii.handle_message("!idea   "))
# unwritable door falls back to inbox
ii.DOORS["institute"] = Path("/proc/nope/ideas.md")
r = ii.handle_message("!idea #institute fallback test")
check(f"unwritable door falls back to inbox ({r})", "inbox" in r and "fallback test" in ii.DOORS["inbox"].read_text())
ii.DOORS["institute"] = tmp / "institute.md"

# autogen sees structure notes (real 2026-10-04 report shape) and founder ideas
intel = tmp / "intel"; intel.mkdir()
(intel / "2026-10-04.md").write_text("""# Competitive Intel — 2026-10-04
## Khan Academy
- Structured with video tutorials, practice exercises, and personalized learning dashboards.
- Emphasizes self-paced learning and mastery over speed or competition.
- Gap: Limited focus on antifragility, sovereignty, and civic literacy compared to AUBIEETERNAL's curriculum.
## Florida DOE — B.E.S.T. Standards
_Scan failed: fetch failed_
## IXL
- Utilizes real-time diagnostics and analytics to provide recommendations.
""")
ca.INTEL_DIR = intel
notes = ca._outside_structure_notes()
check("structure notes include Khan mastery + IXL diagnostics",
      "(Khan Academy) Emphasizes self-paced" in notes and "(IXL) Utilizes real-time" in notes)
check("'Gap' lines and failed scans left out", "Gap" not in notes and "Scan failed" not in notes)
check("notes say borrow format, not content", "never copy" in notes)
check("founder ideas reach the prompt", "straw bridge" in ca._founder_ideas())
seen = []
ca._call_ollama = lambda p: (seen.append(p), None)[1]
import curriculum
curriculum.all_titles_and_keys = lambda: []; curriculum.track_names = lambda: []
ca.generate_candidate()
check("prompt sent to the model contains both", seen and "Khan Academy" in seen[0] and "straw bridge" in seen[0])
ca.INTEL_DIR = tmp / "missing"
check("no report -> no notes, no crash", ca._outside_structure_notes() == "")

# self_audit flags partial failure and staleness
import self_audit as sa
st = tmp / "school_monitor_state.json"; sa.SCHOOL_MONITOR_STATE = st
today = datetime.date.today().isoformat()
st.write_text(json.dumps({"last_run_date": today, "sources_failed": ["Florida DOE — B.E.S.T. Standards (fetch failed)"]}))
f = sa.check_school_monitor()
check(f"partial failure flagged with a suggestion", f and f["id"] == "institute:school_monitor_partial" and "--only" in f["msg"])
st.write_text(json.dumps({"last_run_date": today, "sources_failed": []}))
check("clean run -> no finding", sa.check_school_monitor() is None)
st.write_text(json.dumps({"last_run_date": "2026-09-01", "sources_failed": []}))
check("missed week -> stale finding", (sa.check_school_monitor() or {}).get("id") == "institute:school_monitor_stale")
sa.SCHOOL_MONITOR_STATE = tmp / "nope.json"
check("never installed -> no alert", sa.check_school_monitor() is None)
check("ids get first-detection email", "institute:school_monitor_partial" in sa.SWARM_ALERT_CHECK_IDS)
print(f"\n{fails} failures")
