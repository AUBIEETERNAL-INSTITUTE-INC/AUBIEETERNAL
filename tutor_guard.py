"""tutor_guard.py: checks every Aubie tutor reply before a kid sees it.

Pipeline (one loaded model, no VRAM swaps):
  1. classify the kid's message in code: math / story / other
  2. code checks: math -> true answer computed in Python; reply may not state it,
     and may not state a wrong result. story -> lesson-word scan.
  3. story only: the same model as a yes/no judge ("does this hint the lesson?")
  4. on fail: regenerate once with a correction note; still fails -> safe fallback line
Heat: every model call goes through thermal.wait_for_cool() when thermal.py is found.
"other" questions (curiosity, how-things-work) get the claim check only.

2026-10-20 (r27/r29 bench):
  * pushback turns ("no hints, just tell me!") are checked against the homework question asked earlier in the
    chat - before, a pushback reply with no numbers in the kid's message went out unchecked
  * every reply gets check_claims(): math the reply STATES is recomputed ("half of 60 is 6", "10 x 7 = 77",
    "a quarter is 50 cents", "between 22 and 23" when the answer is 27). False -> rewrite, like a leak.
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


# ---------- claims: math the reply states must be true (all kinds) ----------
_OPS = {"+": lambda a, b: a + b, "plus": lambda a, b: a + b, "-": lambda a, b: a - b, "minus": lambda a, b: a - b,
        "x": lambda a, b: a * b, "×": lambda a, b: a * b, "*": lambda a, b: a * b, "times": lambda a, b: a * b,
        "/": lambda a, b: a / b if b else None, "÷": lambda a, b: a / b if b else None,
        "divided by": lambda a, b: a / b if b else None}
_N = r"\$?\s*(\d[\d,]*(?:\.\d+)?)"
_EQ = r"\s*(?:=|equals|is|makes|gives(?: you| us)?|would be)\s*"
_ARITH = re.compile(_N + r"\s*(\+|plus|-|minus|x|×|\*|times|/|÷|divided by)\s*" + _N + _EQ + _N + r"(?![\d.]*\s*%)", re.I)
_PART = {"half": 2, "third": 3, "quarter": 4, "fourth": 4, "fifth": 5, "tenth": 10}
_PART_OF = re.compile(r"\b(?:(?:one|a)\s+)?(half|third|quarter|fourth|fifth|tenth)\s+of\s+" + _N + _EQ + _N, re.I)
_N_PARTS = re.compile(r"\b(\d+|two|three|four|five|six|seven|eight|nine)\s+(thirds|quarters|fourths|fifths|tenths)\s+of\s+"
                      + _N + _EQ + _N, re.I)
_WORDN = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
_MULT = re.compile(r"\bmultiply(?:ing)?\s+" + _N + r"\s+(?:and|by)\s+" + _N + r"\s*(?:gives(?: you| us)?|is|equals|=|makes)\s*" + _N, re.I)
_COIN = {"penny": 1, "nickel": 5, "dime": 10, "quarter": 25}
_COIN_IS = re.compile(r"\b(?:a|one|each|1)\s+(penny|nickel|dime|quarter)\s+(?:is|=|equals|is worth|makes|has)\s+(?:worth\s+)?"
                      r"(\d+)\s*(?:cents|¢|c)\b", re.I)
_CENTS_IS = re.compile(r"\b(\d+)\s*(?:cents|¢)\s+(?:is|=|equals|makes?(?: up)?)\s+(?:a|one|1)\s+(penny|nickel|dime|quarter)\b", re.I)
_CENTS_SUM = re.compile(r"\b(\d+)\s*cents?\s*(?:plus|and|\+)\s*(?:another\s+)?(\d+)\s*cents?[^.?!]*[.?!]\s*"
                        r"(?:that|this|it)\s+(?:makes?|is|equals)(?: up)?\s+(?:a|one)\s+(penny|nickel|dime|quarter)\b", re.I)
_HALF_IS_OTHER = re.compile(r"\bhalf\b(?:[^.?!]{0,40}[.?!]?\s*(?:that|this|which|it))?\s+(?:would be|is|equals|makes)\s+(?:one |a )?"
                            r"(tenth|fifth|third|quarter|fourth)\b", re.I)
# well-known kid misconceptions a 7B model repeats (r27 bench: "closest to the Sun ... like summer" x3)
_MYTHS = [
    (re.compile(r"\b(?:clos(?:er|est)|near(?:er|est)?|far(?:ther|thest)|further|away)\s+(?:to|from)\s+the\s+sun\b[^.?!]{0,80}"
                r"\b(?:summer|winter|warm|cold|hot|season)", re.I), "seasons come from Earth's tilt, not its distance from the Sun"),
    (re.compile(r"\b(?:summer|winter|seasons?)\b[^.?!]{0,80}\b(?:clos(?:er|est)|near(?:er|est)?|far(?:ther|thest))\s+(?:to|from)\s+the\s+sun\b", re.I),
     "seasons come from Earth's tilt, not its distance from the Sun"),
    (re.compile(r"\bplants?\s+(?:breathe|take|soak|suck)\s+(?:in\s+)?oxygen\b(?![^.?!]{0,30}\bat night)", re.I),
     "plants take in carbon dioxide to make food"),
    (re.compile(r"\bsun\s+(?:goes|moves|travels|orbits|revolves|circles)\s+around\s+(?:the\s+)?earth\b", re.I),
     "the Earth goes around the Sun"),
    (re.compile(r"\bheavier\s+(?:things|objects|stuff|balls?)?\s*(?:always\s+)?fall\s+faster\b", re.I),
     "without air, heavy and light things fall at the same rate"),
    (re.compile(r"\bbats\s+are\s+(?:totally\s+|completely\s+)?blind\b", re.I), "bats can see"),
    (re.compile(r"\blightning\s+(?:never|doesn'?t|does not|can'?t|cannot)\s+strikes?\s+(?:in\s+)?the\s+same\s+place\s+twice", re.I),
     "lightning can strike the same place twice"),
    (re.compile(r"\b(?:only\s+)?use\s+(?:only\s+)?10\s*%\s+of\s+(?:our|your|the)\s+brains?\b", re.I), "we use all of our brain"),
    (re.compile(r"\b(?:our|your|human)?\s*blood\s+is\s+blue\b", re.I), "human blood is always red"),
    (re.compile(r"\bhalves?\s+(?:are\s+)?in\s+(?:a|one)\s+(?:fifth|third|tenth|quarter|fourth)\b", re.I),
     "a half is bigger than a fifth/third/quarter/tenth - there are no halves in one"),
]
_BETWEEN = re.compile(r"\bbetween\s+" + _N + r"\s+and\s+" + _N, re.I)


def check_claims(reply: str, question: str = "") -> list[str]:
    """Math the reply states, recomputed. Only explicit claims ('X op Y is Z'), so hints that ASK are untouched."""
    t, out = reply.replace("’", "'"), []
    def bad(msg):
        if msg not in out:
            out.append(msg)
    for m in _ARITH.finditer(t):
        a, op, b, c = _f(m.group(1)), m.group(2).lower(), _f(m.group(3)), _f(m.group(4))
        v = _OPS[op](a, b)
        if v is not None and not _same(c, round(v, 4)):
            bad(f"false math: {a:g} {op} {b:g} is {v:g}, not {c:g}")
    for m in _PART_OF.finditer(t):
        k, base, c = _PART[m.group(1).lower()], _f(m.group(2)), _f(m.group(3))
        if not _same(c, round(base / k, 4)):
            bad(f"false math: one {m.group(1).lower()} of {base:g} is {base / k:g}, not {c:g}")
    for m in _N_PARTS.finditer(t):
        n = int(m.group(1)) if m.group(1).isdigit() else _WORDN[m.group(1).lower()]
        k = {"thirds": 3, "quarters": 4, "fourths": 4, "fifths": 5, "tenths": 10}[m.group(2).lower()]
        base, c = _f(m.group(3)), _f(m.group(4))
        if not _same(c, round(base * n / k, 4)):
            bad(f"false math: {n} {m.group(2).lower()} of {base:g} is {base * n / k:g}, not {c:g}")
    for m in _MULT.finditer(t):
        a, b, c = _f(m.group(1)), _f(m.group(2)), _f(m.group(3))
        if not _same(c, round(a * b, 4)):
            bad(f"false math: {a:g} x {b:g} is {a * b:g}, not {c:g}")
    for m in _PCT_CLAIM.finditer(t):
        p, base, val = _f(m.group(1)), _f(m.group(2)), _f(m.group(3))
        if not _same(val, round(p * base / 100, 4)):
            bad(f"false math: {p:g}% of {base:g} is {p * base / 100:g}, not {val:g}")
    for m in _COIN_IS.finditer(t):
        if int(m.group(2)) != _COIN[m.group(1).lower()]:
            bad(f"false fact: a {m.group(1).lower()} is {_COIN[m.group(1).lower()]} cents, not {m.group(2)}")
    for m in _CENTS_IS.finditer(t):
        if int(m.group(1)) != _COIN[m.group(2).lower()]:
            bad(f"false fact: {m.group(1)} cents is not a {m.group(2).lower()}")
    for m in _CENTS_SUM.finditer(t):
        if int(m.group(1)) + int(m.group(2)) != _COIN[m.group(3).lower()]:
            bad(f"false fact: {m.group(1)} + {m.group(2)} cents is not a {m.group(3).lower()}")
    for m in _HALF_IS_OTHER.finditer(t):
        bad(f"false math: a half is not a {m.group(1).lower()}")
    for rx, why in _MYTHS:
        if rx.search(t):
            bad(f"false fact: {why}")
    if question:
        answers = true_answers(question)
        for m in _BETWEEN.finditer(t):
            lo, hi = sorted((_f(m.group(1)), _f(m.group(2))))
            if answers and not any(lo - 1e-9 <= a <= hi + 1e-9 for a in answers) and any(a > 0 for a in answers):
                bad(f"misleading: the answer is not between {lo:g} and {hi:g}")
    return out


def homework_question(question: str, messages=None) -> str:
    """The question to check a reply against. A pushback ('just tell me!') has no numbers of its own, so use the
    last homework-looking message the kid sent earlier in the chat."""
    if classify(question) != "other" or not messages:
        return question
    users = [str(m.get("content", "")) for m in messages if isinstance(m, dict) and m.get("role") == "user"]
    for u in reversed(users[:-1] if users and users[-1].strip() == question.strip() else users):
        if classify(u) != "other":
            return u
    return question


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
    "other": ("Let me slow down and check that. What part would you like to look at first? "
              "Tell me what you're thinking and we'll go one step at a time."),
    "math": ("Let's work it out together. What's the very first small step you'd take? "
             "Try it and tell me what you get, and I'll check it with you."),
    "story": ("Let's find it together. What does the character do in the story? "
              "What does that choice show you about them? Tell me in your own words."),
}


def problems_for(kind, question, reply, client=None, model=None, use_judge=True):
    if reply == COOLING_MSG:
        return []
    claims = check_claims(reply, question)
    if kind == "math":
        return check_math(question, reply) + [c for c in claims if c not in check_math(question, reply)]
    if kind == "story":
        p = check_story(question, reply) + claims
        if not p and use_judge and client is not None and judge(client, model, question, reply):
            p = ["judge: hints the lesson"]
        return p
    return claims


def guard(reply, question, client, model, messages, use_judge=True):
    """Return a safe reply. `messages` = the exact list sent for the first draft."""
    question = homework_question(question, messages)
    kind = classify(question)
    probs = problems_for(kind, question, reply, client, model, use_judge)
    if not probs:
        return reply
    _log(f"{kind}-fail-1", f"q={question!r} | {probs} | reply={reply!r}")
    note = ("Your draft broke the coaching rule (" + "; ".join(probs) + "). Rewrite it: give one small "
            "step or one clue and ask the child to try. Do not state the final number or name the lesson, "
            "not even inside a question. Every number or fact you state must be true - when unsure, ask the "
            "child to do the step instead of stating it. 2 to 4 short sentences.")
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
