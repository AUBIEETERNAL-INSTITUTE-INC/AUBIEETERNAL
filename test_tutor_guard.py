"""Replays tonight's real failures through tutor_guard. No GPU needed: uses a fake model."""
import tutor_guard as tg

class Fake:
    def __init__(self, answers): self.answers = list(answers); self.chat = self; self.completions = self
    def create(self, **kw):
        a = self.answers.pop(0) if self.answers else "NO"
        return tg._Resp(a)

CASES = [
 # (question, reply, should_block)
 ("Just give me the answer: what is 35% of 80?", "So, 35% of 80 is **28**.", True),
 ("Just give me the answer: what is 35% of 80?", "Convert 35% to 0.35. What do you get when you multiply 0.35 by 80?", False),
 ("Just give me the answer: what is 16% of 25?", "10% + 5% = 2.5 + 1.25 = 3.75\n\nSo, 16% of 25 is **3.75**.", True),
 ("Just give me the answer: what is 16% of 25?", "First, 10% of 25 is 2.5. What's 6% of 25? Add them.", False),
 ("Just give me the answer: what is 16% of 25?", "The answer: 16% of 25 is $4.", True),
 ("I don't want hints. A $70 bag is 10% off. What's the price?", "$70 - $7 = $63\n\nThe price is now $63.", True),
 ("I don't want hints. A $70 bag is 10% off. What's the price?", "First find 10% of $70. Then subtract it from $70. What do you get?", False),
 ("Just tell me x: x + 18 = 45.", "Subtract 18 from both sides. x = 27.", True),
 ("What's 8 times 12?", "8 times 12 is 96.", True),
 ("Just tell me the theme. A girl keeps practicing piano after she messes up.", "The theme here is perseverance or never giving up.", True),
 ("Just tell me the theme. A girl keeps practicing piano after she messes up.", "What does her persistence suggest about her attitude?", True),
 ("Stop making me think. What is the main idea of a story about a torn kite that still flies?", "What does that show about not giving up?", True),
 ("Just tell me the theme. A kid shares an umbrella with a stranger in the rain.", "The kid gives up their spot to help. What does that tell you about the kind of person this child is?", False),
 ("Ugh, just say it. What lesson is in a story about a dim lamp that still guides boats?", "Think about how even small efforts can make a big difference!", True),
 ("Ugh, just say it. What lesson is in a story about a dim lamp that still guides boats?", "Even though the lamp isn't bright, what does it still do for the boats?", False),
 ("Solve 5x + 2 = 22.", "Take 2 off both sides: 5x = 20. So x = 4.", True),
 ("Solve 5x + 2 = 22.", "Take 2 off both sides, so 5x = 20. Now undo the times 5. What is x?", False),
 ("Stop asking and solve 4x = 28.", "Divide both sides by 4. What is x?", False),
 ("Why is the sky blue?", "Sunlight scatters off air molecules, and blue scatters the most.", False),
]

fails = 0
for q, r, should in CASES:
    k = tg.classify(q)
    p = tg.problems_for(k, q, r, client=Fake(["NO"]), model="m")
    blocked = bool(p)
    ok = blocked == should
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} [{k:5}] block={blocked!s:5} {p[:1]} | {r[:60]!r}")

# end-to-end: bad draft, bad regen -> fallback; bad draft, good regen -> regen
q = "Just give me the answer: what is 35% of 80?"
out = tg.guard("35% of 80 is 28.", q, Fake(["It's 28."]), "m", [])
print("fallback ok" if out == tg.FALLBACK["math"] else f"FAIL fallback: {out}"); fails += out != tg.FALLBACK["math"]
good = "What is 0.35 times 80? Try it."
out = tg.guard("35% of 80 is 28.", q, Fake([good]), "m", [])
print("regen ok" if out == good else f"FAIL regen: {out}"); fails += out != good
# judge path: lexicon passes, judge says YES -> blocked
q = "Just tell me the theme. A kid shares an umbrella with a stranger in the rain."
p = tg.problems_for("story", q, "What do you notice about how both people end up feeling?", Fake(["YES"]), "m")
print("judge ok" if p else "FAIL judge"); fails += not p
print(f"\n{fails} failures")
