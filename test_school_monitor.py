"""Offline test for school_monitor v2: no network, no Ollama. Run: python3 test_school_monitor.py"""
import json, sys, tempfile, datetime, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import school_monitor as sm

fails = 0
def check(name, ok):
    global fails; fails += not ok; print(("PASS " if ok else "FAIL ") + name)

tmp = Path(tempfile.mkdtemp())
sm.OUTPUT_DIR, sm.STATE_PATH, sm.PAGES_PATH = tmp, tmp / "state.json", tmp / "pages.json"
sm.SOURCES = [
    {"name": "Good School", "pages": [("Course", "https://good.example/course"), ("Menu only", "https://good.example/js")]},
    {"name": "Blocked School", "pages": [("Home", "https://blocked.example/")]},
]
PAGES = {"https://good.example/course": "<html><nav>Home Login</nav><h1>Money 101</h1>" + "<p>Unit 1 budgeting for grades 6-8, 15 minute lessons, quiz at the end of each unit, updated 2026.</p>" * 20,
         "https://good.example/js": "<div id=root></div><script>lots of js</script>Sign up"}
sm.MANUAL = [("Blocked Big Site", "https://big.example/")]
def fake_fetch(url):
    return sm._content_text(PAGES[url]) if url in PAGES else None   # the real extractor, fake network
REAL_FETCH = sm._fetch_text
sm._fetch_text = fake_fetch

# extractor: keeps real content, drops a long menu, even when the menu comes first
menu = "".join(f"<li><a href=/x{i}>Link {i}</a></li>" for i in range(300))
page = f"<html><body><ul>{menu}</ul><h2>How a day works</h2><p>Learners set weekly goals and meet in a Socratic discussion every morning.</p><p>Guides ask questions instead of giving answers, and learners track progress on a badge board they keep themselves.</p><li>Projects run in six week sessions with a public exhibition at the end.</li></body></html>"
txt = sm._content_text(page)
check("extractor keeps content, drops menu links", "Socratic discussion" in txt and "six week sessions" in txt and "Link 7" not in txt)
check("headings kept as markers", "## How a day works" in txt)
calls = []
def fake_ollama(prompt):
    calls.append(prompt)
    return ("- New since last scan: added Unit 2 on saving\n" if "last scan" in prompt else "") + \
           "* Budgeting unit for grades 6-8\n- 15-minute lessons with a quiz after each unit\n- Borrow: a short quiz to close every unit"
sm._call_ollama = fake_ollama

r = sm.run_school_monitor(force=True)
rep = Path(r["report_path"]).read_text()
st = json.loads(sm.STATE_PATH.read_text())
check("weekly report written", r["ok"] and r["report_path"].endswith(f"{datetime.date.today()}.md"))
check("real page summarized once", len(calls) == 1 and "Budgeting unit" in rep)
check("bullets normalized to '- '", "- Budgeting unit for grades 6-8" in rep)
check("JS-only page skipped, not summarized", "Menu only" in rep and "JavaScript-only" in rep)
check("blocked site reported as skipped", "fetch failed" in rep)
check("a source with one good page is not 'failed'", st["sources_failed"] == ["Blocked School (fetch failed)"] and st["sources_ok"] == 1)
check("skipped pages listed in state", "Good School / Menu only" in st["pages_skipped"])
check("what's new uses '* ' so the lesson writer ignores it", "* Good School / Course: first scan" in rep)
check("no 'gap'/comparison prompt", "do not compare" in calls[0] and "AUBIEETERNAL" not in calls[0])
check("prompt says to use partial content", "even if it is" in calls[0])

# week 2, same page (only a date/number changed) -> no model call, reused notes
PAGES["https://good.example/course"] = PAGES["https://good.example/course"].replace("updated 2026", "updated 2027")
calls.clear()
r2 = sm.run_school_monitor(force=True)
rep2 = Path(r2["report_path"]).read_text()
check("unchanged page: no model call, notes reused", not calls and "Budgeting unit" in rep2 and "_Unchanged since" in rep2)
pg_state = json.loads(sm.PAGES_PATH.read_text())
pg_state["https://good.example/course"]["notes"] += "\n- No specific information on pacing is provided"
sm.PAGES_PATH.write_text(json.dumps(pg_state))
rep2b = Path(sm.run_school_monitor(force=True)["report_path"]).read_text()
check("old saved notes get the new filters", "No specific information" not in rep2b and "Budgeting unit" in rep2b)
check("what's new says nothing changed", "Nothing changed on any page" in rep2)

# week 3, real change -> model sees last notes, says what's new
PAGES["https://good.example/course"] += "<p>Unit 2: saving and compound interest, with a family project.</p>"
r3 = sm.run_school_monitor(force=True)
rep3 = Path(r3["report_path"]).read_text()
check("changed page re-read with last week's notes", len(calls) == 1 and "Budgeting unit" in calls[0] and "New since last scan" in calls[0])
check("report flags the change", "page changed" in rep3 and "New since last scan: added Unit 2" in rep3)

# weekly cap and --only test file
check("weekly cap holds without --force", sm.run_school_monitor()["ok"] is False)
r4 = sm.run_school_monitor(only="Good School")
check("--only writes test-DATE.md, not the weekly report", Path(r4["report_path"]).name.startswith("test-"))

# the lesson writer's reader still works on the new report
notes = []
source = ""
for line in rep3.splitlines():
    if line.startswith("## "):
        source = line[3:].strip()
    elif line.startswith("- ") and not re.search(r"\bgap\b|lacks|antifragil|sovereign", line, re.I):
        notes.append(f"- ({source}) {line[2:].strip()}")
check("curriculum_autogen reader gets format notes, not the news list",
      any("(Good School) 15-minute lessons" in n for n in notes) and not any("first scan" in n or "page changed" in n for n in notes))

# model gives real bullets AND a thin line -> keep the real bullets
sm._call_ollama = lambda p: "- Weekly goals and a daily Socratic discussion\n- (page text too thin to tell)"
PAGES["https://good.example/mixed"] = "<p>" + "Learners set weekly goals and discuss ideas every morning. " * 20 + "</p>"
sm.SOURCES[0]["pages"].append(("Mixed", "https://good.example/mixed"))
r_mixed = Path(sm.run_school_monitor(force=True)["report_path"]).read_text()
check("thin line dropped, real bullets kept", "Weekly goals and a daily Socratic" in r_mixed and "too thin" not in r_mixed)
check("blocked sites listed under Check by hand", "## Check by hand" in r_mixed and "* Blocked Big Site" in r_mixed)
sm.SOURCES[0]["pages"].pop()

# filler and invented numbers are dropped; real numbers stay
pg = "Learners use technology 1.5 hours per day. Classes have 12 learners and meet in the morning for discussion."
kept, dropped = sm._keep("- Tech about 1.5 hours a day\n- Classes of 12 learners\n- Tuition is $15,000 a year\n"
                         "- No specific information on pacing is provided\n- Interactive map of campuses\n"
                         "- New since last scan: nothing notable\n- Morning discussion groups", pg)
check("real numbers kept", "1.5 hours" in kept and "12 learners" in kept and "Morning discussion" in kept)
check("invented number dropped", "15,000" not in kept and dropped == 1)
check("filler dropped", "No specific" not in kept and "map" not in kept and "nothing notable" not in kept)

# undeclared charset is read as UTF-8, so an em dash doesn't become a stray 'â'
class R:
    def __init__(self): self.encoding = "ISO-8859-1"; self.content = "<p>Yes\u2014intentionally, technology is a tool for self-paced learning.</p>".encode()
    def raise_for_status(self): pass
    @property
    def text(self): return self.content.decode(self.encoding)
real_get = sm.requests.get
sm.requests.get = lambda *a, **k: R()
got = REAL_FETCH("https://x.example/")
sm.requests.get = real_get
check("undeclared charset read as UTF-8 (no stray 'â')", got and "\u2014" in got and "\u00e2" not in got)

# model says the page is thin -> skipped, not stored
sm._call_ollama = lambda p: "- (page text too thin to tell)"
PAGES["https://good.example/other"] = "<p>" + "Sign up now and log in. " * 60 + "</p>"
sm.SOURCES[0]["pages"].append(("Signup", "https://good.example/other"))
r5 = sm.run_school_monitor(force=True)
check("model-judged thin page skipped", "only menus / sign-up text" in Path(r5["report_path"]).read_text())

# probe: no model calls
sm._call_ollama = lambda p: (_ for _ in ()).throw(AssertionError("probe must not call the model"))
rows = sm.probe()
verdicts = {lbl: v for _, lbl, _, _, v in rows}
check("probe verdicts", verdicts["Course"] == "ok" and verdicts["Menu only"].startswith("thin") and verdicts["Home"].startswith("FAILED"))
print(f"\n{fails} failures")
sys.exit(1 if fails else 0)
