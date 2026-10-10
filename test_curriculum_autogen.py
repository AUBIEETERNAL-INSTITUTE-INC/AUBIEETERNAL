"""Standalone check (no Ollama needed): autogen rejects vague lessons and retries; approving keeps lesson content for the tutor chat. Run: python3 test_curriculum_autogen.py"""
import sys, json, tempfile
from pathlib import Path
sys.path.insert(0, '.')
import curriculum, curriculum_autogen as ca, curriculum_proposals as cp
fails = 0
def check(name, ok):
    global fails; fails += not ok; print(("PASS " if ok else "FAIL ") + name)

today = {"key":"wonder-and-resilience","title":"Wonder and Resilience","topic":"x",
 "example":"A historical figure who faced significant challenges but maintained a sense of curiosity and awe, leading them to discover new opportunities and solutions.",
 "activity":"","check_questions":[]}
good = {"key":"curie-keeps-testing","title":"Curiosity Under Pressure","topic":"How curiosity keeps you going when results are slow.",
 "example":"Marie Curie processed tonnes of pitchblende in a leaky shed for years before isolating radium.",
 "activity":"Pick a question about something at home and test it three different ways; write what changed.",
 "check_questions":["What made the shed work hard?","What would you have tried next?","How did each test change what she knew?"],
 "age_hint":"10+","xp":20,"target_track":"Wonder","rationale":"r"}
p = ca.validate_candidate(today); check(f"rejects last night's proposal {p}", bool(p))
check("accepts a concrete lesson", ca.validate_candidate(good) == [])
check("rejects 'someone who'", bool(ca.validate_candidate({**good, "example":"Imagine someone who keeps trying."})))

# generator retries once with feedback, then accepts
calls = []
replies = [json.dumps(today), json.dumps(good)]
ca._call_ollama = lambda prompt: (calls.append(prompt), replies.pop(0))[1]
curriculum.all_titles_and_keys = lambda: [("k","T","🦁 Courage")]
curriculum.track_names = lambda: [("courage","🦁 Courage")]
c = ca.generate_candidate()
check("retry produced the good lesson", c and c["key"] == good["key"])
check("retry prompt told the model why", len(calls) == 2 and "rejected" in calls[1])
# two bad replies -> None (nothing submitted)
replies[:] = [json.dumps(today), json.dumps(today)]
check("two bad drafts -> nothing submitted", ca.generate_candidate() is None)

# approve keeps content; chat lookup finds it
tmp = Path(tempfile.mkdtemp())
curriculum.EXTRA_PATH = tmp / "curriculum_extra.json"
curriculum.track_names = lambda: [("wonder","💡 Wonder")]
lesson = {k: good[k] for k in ("key","title","topic","example","activity","check_questions","age_hint","xp")}
ok = cp.merge_approved_proposal({"type":"lesson","lesson":lesson,"target_track":"Wonder"})
check("merge ok", ok)
got = cp.get_lesson_content(good["key"])
check("content kept: example + activity + 3 check questions",
      got and got["example"].startswith("Marie Curie") and got["activity"] and len(got["check_questions"]) == 3)
tree = json.loads(curriculum.EXTRA_PATH.read_text())
check("curriculum tree still gets [key,title,age,xp]", tree[0]["levels"][0] == [good["key"], good["title"], "10+", 20])
check("unknown key -> None", cp.get_lesson_content("nope") is None)
print(f"\n{fails} failures")
