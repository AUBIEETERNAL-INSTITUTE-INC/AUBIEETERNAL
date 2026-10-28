"""Standalone check (no Ollama needed): autogen rejects vague or unverified lessons and retries; approving keeps lesson content for the tutor chat. Run: python3 test_curriculum_autogen.py"""
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
 "age_hint":"10+","xp":20,"target_track":"Wonder","rationale":"r", "example_kind":"real",
 "steelman_for":"Curiosity keeps you testing when results are slow, so you notice what others miss.",
 "steelman_against":"Curiosity without a plan can waste years; sometimes the right move is to stop and switch."}
today = {**today, "example_kind":"real", "steelman_for": good["steelman_for"], "steelman_against": good["steelman_against"]}
REAL_FACT_CHECK = ca._fact_check
ca._fact_check = lambda ex: (True, "ok")   # no Ollama in this test; the real fact-check is tested below
p = ca.validate_candidate(today); check(f"rejects last night's proposal {p}", bool(p))
check("accepts a concrete lesson", ca.validate_candidate(good) == [])
check("rejects 'someone who'", bool(ca.validate_candidate({**good, "example":"Imagine someone who keeps trying."})))
# 2026-10-11: the Buffett/barbell lesson - kind missing, no steelman sides
buffett = {**good, "example": "Warren Buffett uses a barbell strategy in investing by keeping most funds extremely safe "
           "while taking large risks with a small portion.", "steelman_for": "", "steelman_against": ""}
buffett.pop("example_kind")
pb = ca.validate_candidate(buffett)
check("rejects: no example_kind, empty steelman sides", any("example_kind" in x for x in pb) and
      any("steelman_for" in x for x in pb) and any("steelman_against" in x for x in pb))
madeup = {**good, "example_kind": "made-up",
          "example": "Imagine Ana, 12, who keeps her grades steady and spends two hours a week building a robot that might never work."}
check("accepts a named made-up scenario", ca.validate_candidate(madeup) == [])
check("made-up must start with Imagine + a name",
      bool(ca.validate_candidate({**madeup, "example": "Imagine a kid who builds robots."})) and
      bool(ca.validate_candidate({**madeup, "example": "Ana builds robots on weekends."})))
check("no quotes from real people", bool(ca.validate_candidate({**good, "example": 'Marie Curie said "Nothing in life is to be feared."'})))

# generator retries once with feedback, then accepts
calls = []
replies = [json.dumps(today), json.dumps(good)]
ca._call_ollama = lambda prompt: (calls.append(prompt), replies.pop(0))[1]
curriculum.all_titles_and_keys = lambda: [("k","T","🦁 Courage")]
curriculum.track_names = lambda: [("courage","🦁 Courage")]
c = ca.generate_candidate()
check("retry produced the good lesson", c and c["key"] == good["key"])
check("retry prompt told the model why", len(calls) == 2 and "rejected" in calls[1])
# three bad replies -> None (nothing submitted)
replies[:] = [json.dumps(today), json.dumps(today), json.dumps(today)]
check("three bad drafts -> nothing submitted", ca.generate_candidate() is None)

# a real example the fact-checker isn't sure about -> redo as made-up
calls.clear()
replies[:] = [json.dumps({**buffett, "example_kind": "real", "steelman_for": good["steelman_for"],
                          "steelman_against": good["steelman_against"]}),
              json.dumps({"example": madeup["example"]})]
ca._fact_check = lambda ex: (("Buffett" not in ex), "the barbell strategy is Taleb's, not Buffett's")
c = ca.generate_candidate()
check("unsure real example -> only the example is rewritten (one extra call, lesson kept)",
      c and c["example"].startswith("Imagine Ana") and c["example_kind"] == "made-up"
      and c["title"] == buffett["title"] and len(calls) == 2 and "Old example" in calls[1])
# if the targeted rewrite fails twice, it falls back to redrafting the whole lesson
calls.clear()
replies[:] = [json.dumps({**buffett, "example_kind": "real", "steelman_for": good["steelman_for"],
                          "steelman_against": good["steelman_against"]}),
              '{"example": "Imagine someone who invests."}', '{"example": ""}', json.dumps(madeup)]
c = ca.generate_candidate()
check("rewrite fails twice -> whole lesson redrafted with the reason", c and c["example"].startswith("Imagine Ana")
      and len(calls) == 4 and "Taleb" in calls[3])
# 2026-10-13: unnamed study passed the fact-check; 3 vague examples in a row threw the lesson away
study = {**good, "example": "Physical activity releases endorphins. For instance, a study published in the Journal of "
         "Psychosomatic Research found that regular exercise decreases anxiety."}
check("unnamed study -> rejected as uncheckable", any("unnamed study" in x for x in ca.validate_candidate(study)))
check("a named, well-known fact is still fine", ca.validate_candidate(good) == [])
calls.clear()
vague = {**good, "example": "A famous scientist kept trying for years."}
replies[:] = [json.dumps(vague), json.dumps({"example": madeup["example"]})]
ca._fact_check = lambda ex: (True, "ok")
c = ca.generate_candidate()
check("vague example -> only the example rewritten (2 calls, lesson kept)", c and c["example"].startswith("Imagine Ana")
      and c["title"] == good["title"] and len(calls) == 2)
calls.clear()
replies[:] = [json.dumps({**good, "example": "Imagine someone."}), json.dumps({**good, "check_questions": []}),
              json.dumps(good)]
replies[1:1] = ['{"example": ""}', '{"example": ""}']   # the example rewrite fails twice -> normal redraft continues
c = ca.generate_candidate()
check("rewrite fails -> falls back to redrafting", c and c["key"] == good["key"])
calls.clear()
replies[:] = [json.dumps({**good, "check_questions": []}), json.dumps(good)]
c = ca.generate_candidate()
check("non-example problems still redraft the whole lesson", c and len(calls) == 2 and "rejected" in calls[1])

# the real fact-check reads the model's JSON and treats anything but certain:true as "not sure"
real_call = ca._call_ollama
for reply, want in (('{"certain": true, "why": "documented"}', True), ('{"certain": false, "why": "unsure"}', False),
                    ('{"certain": "maybe"}', False), ('not json', False), (None, False)):
    ca._call_ollama = lambda prompt, r=reply: r
    check(f"fact-check {reply!r} -> {want}", REAL_FACT_CHECK("Marie Curie isolated radium.")[0] is want)
ca._call_ollama = real_call
ca._fact_check = lambda ex: (True, "ok")

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
