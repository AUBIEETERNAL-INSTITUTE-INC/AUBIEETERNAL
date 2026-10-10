"""tutor_guard.py: checks every Aubie tutor reply before a kid sees it.

Pipeline (one loaded model, no VRAM swaps):
  1. classify the kid's message in code: math / story / other
  2. code checks: math -> true answer computed in Python; reply may not state it,
     and may not state a wrong result. story -> lesson-word scan.
  3. story only: the same model as a yes/no judge ("does this hint the lesson?")
  4. on fail: regenerate once with a correction note; still fails -> safe fallback line
Heat: every model call goes through thermal.wait_for_cool() when thermal.py is found.
"other" questions (curiosity, how-things-work) pass through untouched.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

# ---------- heat guard (reuses IT-support thermal.py) ----------
os.environ.setdefault("AUBIE_GPU_MAX_WAIT_S", "60")   # a kid shouldn't wait 5 minutes
_thermal = None
for _p in (Path.home() / "vanhorn-repo" / "aubie-bot", Path(__file__).parent / "swarm"):
    if (_p / "thermal.py").exists():
        sys.path.insert(0, str(_p))
        try:
            import thermal as _thermal  # type: ignore
        except Exception:
            _thermal = None
        break

COOLING_MSG = ("Aubie's computer is taking a quick cool-down break so it doesn't overheat. "
               "Give it a minute, then ask again!")
LOG = Path(os.environ.get("AUBIE_TUTOR_GUARD_LOG", str(Path.home() / "AUBIEETERNAL" / "tutor_guard.log")))


def _log(kind: str, detail: str) -> None:
    try:
        with LOG.open("a") as f:
            f.write(f"{time.strftime('%F %T')} | {kind} | {' '.join(detail.split())[:400]}\n")
    except Exception:
        pass


class _Msg:
    def __init__(self, c): self.content = c
class _Choice:
    def __init__(self, c): self.message = _Msg(c)
class _Resp:
    def __init__(self, c): self.choices = [_Choice(c)]


class CoolClient:
    """Wraps an OpenAI-style client. Every chat.completions.create() checks GPU heat first.
    If it's too hot, returns a friendly cooling message instead of raising."""
    def __init__(self, client):
        self._client = client
        self.chat = self
        self.completions = self

    def create(self, **kw):
        if _thermal is not None:
            try:
                _thermal.wait_for_cool("portal chat")
            except Exception as e:
                if e.__class__.__name__ == "TooHot":
                    _log("too-hot", str(e))
                    return _Resp(COOLING_MSG)
                raise
        return self._client.chat.completions.create(**kw)

    def __getattr__(self, name):
        return getattr(self._client, name)


# ---------- classify ----------
_STORY = re.compile(r"\b(theme|lesson|moral|main idea|story|message of|teach(es)? us|trait|what does .* show)\b", re.I)
_MATHY = re.compile(r"\d\s*%|\$\s*\d|\d\s*(x|×|\*|/|÷|\+|-|plus|minus|times|divided by)\s*\d|\bof\s+\$?\d|\d+\s*/\s*\d+|\bsolve\b|\d\s*x\b|\bx\s*[+\-=]|=\s*\d", re.I)


def classify(text: str) -> str:
    if _STORY.search(text):
        return "story"
    if _MATHY.search(text):
        return "math"
    return "other"


# ---------- math: compute the true answer ----------
_NUM = r"\$?\s*(-?\d[\d,]*\.?\d*)"


def _f(s: str) -> float:
    return float(s.replace(",", "").replace("$", "").strip())


def true_answers(q: str) -> set[float]:
    q2 = q.lower().replace("×", "*").replace("÷", "/")
    out: set[float] = set()
    m = re.search(r"(\d[\d.]*)\s*%\s*(off|discount)", q2)
    price = re.search(r"\$\s*(\d[\d,.]*)", q2)
    if m and price:
        p, base = _f(m.group(1)), _f(price.group(1))
        out |= {round(base * (1 - p / 100), 2), round(base * p / 100, 2)}
    m = re.search(r"(\d[\d.]*)\s*%\s*(tax)", q2) or (re.search(r"tax is\s*(\d[\d.]*)\s*%", q2))
    if m and price:
        p, base = _f(m.group(1)), _f(price.group(1))
        out |= {round(base * (1 + p / 100), 2), round(base * p / 100, 2)}
    for m in re.finditer(r"(\d[\d.]*)\s*%\s*of\s*\$?\s*(\d[\d,.]*)", q2):
        out.add(round(_f(m.group(1)) * _f(m.group(2)) / 100, 4))
    for m in re.finditer(r"(\d+)\s*/\s*(\d+)\s*of\s*\$?\s*(\d[\d,.]*)", q2):
        out.add(round(int(m.group(1)) / int(m.group(2)) * _f(m.group(3)), 4))
    words = {"plus": "+", "minus": "-", "times": "*", "divided by": "/", "x": "*"}
    expr = q2
    for w, s in words.items():
        expr = re.sub(rf"(?<=\d)\s*\b{w}\b\s*(?=\d)", f" {s} ", expr)
    for m in re.finditer(r"(-?\d[\d,.]*(?:\s*[-+*/]\s*-?\d[\d,.]*)+)", expr):
        e = m.group(1).replace(",", "")
        if re.fullmatch(r"[\d.\s+\-*/]+", e) and re.search(r"[+*/]|\d\s+-\s*\d", e):
            try:
                out.add(round(eval(e, {"__builtins__": {}}), 4))  # digits/operators only
            except Exception:
                pass
    m = re.search(r"(\d+)\s*x\s*([+-])\s*(\d+)\s*=\s*(\d+)", q2)
    if m:
        a, sgn, b, c = int(m.group(1)), m.group(2), int(m.group(3)), int(m.group(4))
        out.add(round((c - b) / a if sgn == "+" else (c + b) / a, 4))
    m = re.search(r"\bx\s*([+-])\s*(\d+)\s*=\s*(\d+)", q2)
    if m and not re.search(r"\d\s*x", q2):
        sgn, b, c = m.group(1), int(m.group(2)), int(m.group(3))
        out.add(c - b if sgn == "+" else c + b)
    m = re.search(r"(\d+)\s*x\s*=\s*(\d+)", q2)
    if m:
        out.add(round(int(m.group(2)) / int(m.group(1)), 4))
    return {v for v in out if v is not None}


def _same(a: float, b: float) -> bool:
    return abs(a - b) < 1e-6 or abs(a - b) <= 0.005 * max(1, abs(b)) and abs(a - b) < 0.01


def _nums(text: str) -> list[float]:
    vals = []
    for m in re.finditer(r"(?<![\w.])\$?\s*(-?\d[\d,]*\.?\d*)(?![\d])", text):
        try:
            vals.append(_f(m.group(1)))
        except ValueError:
            pass
    return vals


_FINAL = re.compile(r"(?:\b(?:so|therefore|thus|that means|the answer is|answer:|it costs|you pay|you get|is|equals|=)\b|=)\s*\*{0,2}\$?\s*(-?\d[\d,]*\.?\d*)\s*\*{0,2}\s*(?:[.!]|$|\n| is the| (?:candies|slices|dollars|pieces|cm|miles|weeks))", re.I | re.M)
_PCT_CLAIM = re.compile(r"(\d[\d.]*)\s*%\s*of\s*\$?\s*(\d[\d,.]*)\s*(?:is|=|equals|would be)\s*(?:about\s*)?\$?\s*(-?\d[\d,]*\.?\d*)", re.I)


def check_math(question: str, reply: str) -> list[str]:
    problems = []
    answers = true_answers(question)
    qnums = _nums(question)
    for v in _nums(reply):
        if any(_same(v, a) for a in answers) and not any(_same(v, q) for q in qnums):
            problems.append(f"states the answer {v:g}")
            break
    for m in _PCT_CLAIM.finditer(reply):
        p, base, val = _f(m.group(1)), _f(m.group(2)), _f(m.group(3))
        if not _same(val, round(p * base / 100, 4)):
            problems.append(f"wrong math: {p:g}% of {base:g} is not {val:g}")
    if answers:
        for m in _FINAL.finditer(reply):
            try:
                v = _f(m.group(1))
            except ValueError:
                continue
            if any(_same(v, q) for q in qnums):
                continue
            ends_reply = "?" not in reply[m.end():]   # a stated result, not a step before a question
            if ends_reply and re.search(r"\b(so|therefore|thus|the answer|that means)\b", reply[max(0, m.start() - 40):m.end()], re.I) \
                    and not any(_same(v, a) for a in answers):
                problems.append(f"states a wrong final result {v:g}")
                break
    return problems


# ---------- story: lesson words ----------
LESSON_WORDS = [
    r"persever\w*", r"persist\w*", r"never give up", r"(?:don'?t|doesn'?t|not|didn'?t) giv(?:e|ing) up",
    r"giv(?:e|ing) up", r"keep(?:s|ing)? (?:going|trying)", r"resilien\w*", r"determin\w*",
    r"kindness", r"\bkind\b(?!\s+of)", r"generos\w*", r"compassion\w*", r"empath\w*",
    r"honest\w*", r"courage\w*", r"brave\w*", r"patien\w*", r"teamwork", r"work(?:ing)? together",
    r"friendship", r"responsib\w*", r"grateful", r"gratitude", r"forgiv\w*", r"\bhope\w*",
    r"hard work", r"small (?:things|efforts|acts|steps|light)[^.?!]{0,40}(?:difference|matter|big)",
    r"believe in yourself", r"(?:theme|lesson|moral|main idea)\s+(?:here\s+)?(?:is|was|could be|might be)",
    r"overcom\w*", r"imperfect\w*[^.?!]{0,30}(?:value|beautiful|useful)",
]
_LESSON = [re.compile(p, re.I) for p in LESSON_WORDS]


def check_story(question: str, reply: str) -> list[str]:
    found = []
    for rx in _LESSON:
        m = rx.search(reply)
        if m and not rx.search(question):
            found.append(f"names the lesson: '{m.group(0)}'")
    return found


JUDGE_PROMPT = (
    "You check a children's tutor. The tutor must NOT state or hint the lesson, theme, moral, "
    "or main idea of a story, not even inside a question or as one option in a list.\n\n"
    "Child asked: {q}\n\nTutor reply: {r}\n\n"
    "Does the tutor reply state or hint the lesson/theme? Answer with one word: YES or NO."
)


def judge(client, model, question, reply) -> bool:
    try:
        r = client.chat.completions.create(
            model=model, max_tokens=3, temperature=0,
            messages=[{"role": "user", "content": JUDGE_PROMPT.format(q=question, r=reply)}],
        )
        return r.choices[0].message.content.strip().upper().startswith("YES")
    except Exception as e:
        _log("judge-error", str(e))
        return False


FALLBACK = {
    "math": ("Let's work it out together. What's the very first small step you'd take? "
             "Try it and tell me what you get, and I'll check it with you."),
    "story": ("Let's find it together. What does the character do in the story? "
              "What does that choice show you about them? Tell me in your own words."),
}


def problems_for(kind, question, reply, client=None, model=None, use_judge=True):
    if reply == COOLING_MSG:
        return []
    if kind == "math":
        return check_math(question, reply)
    if kind == "story":
        p = check_story(question, reply)
        if not p and use_judge and client is not None and judge(client, model, question, reply):
            p = ["judge: hints the lesson"]
        return p
    return []


def guard(reply, question, client, model, messages, use_judge=True):
    """Return a safe reply. `messages` = the exact list sent for the first draft."""
    kind = classify(question)
    probs = problems_for(kind, question, reply, client, model, use_judge)
    if not probs:
        return reply
    _log(f"{kind}-fail-1", f"q={question!r} | {probs} | reply={reply!r}")
    note = ("Your draft broke the coaching rule (" + "; ".join(probs) + "). Rewrite it: give one small "
            "step or one clue and ask the child to try. Do not state the final number or name the lesson, "
            "not even inside a question. 2 to 4 short sentences.")
    try:
        r2 = client.chat.completions.create(
            model=model, max_tokens=300,
            messages=messages + [{"role": "assistant", "content": reply}, {"role": "system", "content": note}],
        ).choices[0].message.content
    except Exception as e:
        _log("regen-error", str(e))
        r2 = ""
    if r2 and r2 != COOLING_MSG and not problems_for(kind, question, r2, client, model, use_judge):
        _log(f"{kind}-fixed", f"q={question!r} | reply={r2!r}")
        return r2
    _log(f"{kind}-fallback", f"q={question!r} | second={r2!r}")
    return FALLBACK[kind]
