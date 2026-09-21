import json, re

SRC  = "output/training_data_r9.jsonl"
KEEP = "output/training_data_r10.jsonl"
DROP = "output/dropped_r10.txt"

PII = re.compile(r'\bEIN\b|\d{2}-\d{7}|VanHorn|Mateo|Gabriela|Matthew|Ryzen')

def get(r): return r.get("output") or r["messages"][1]["content"]
def put(r, v):
    if "output" in r: r["output"] = v
    else: r["messages"][1]["content"] = v

def repair(o):
    paras = [p.strip() for p in o.split("\n\n") if p.strip()]
    for i, p in enumerate(paras):
        if p.startswith("The strongest"):
            return "\n\n".join(paras[i:]), i > 0
    return o, False

kept, dropped, fixed = [], [], 0
for line in open(SRC):
    r = json.loads(line)
    o, was_fixed = repair(get(r).strip())
    if o.startswith("The strongest"):
        put(r, o)
        kept.append(r)
        fixed += was_fixed
        continue
    if   "**" in o or "##" in o:  why = "markdown"
    elif o.startswith("{"):       why = "json blob"
    elif o.startswith("The image") or "photo" in o[:80].lower(): why = "vision"
    elif PII.search(o):           why = "org/identity"
    elif len(o.split()) > 120:    why = "long non-steelman"
    else:                         why = None
    if why: dropped.append((why, o[:100]))
    else:   kept.append(r)

with open(KEEP, "w") as f:
    for r in kept: f.write(json.dumps(r) + "\n")
with open(DROP, "w") as f:
    for why, s in dropped: f.write(f"[{why}] {s}\n")

print(len(kept), "kept,", fixed, "preambles stripped ->", KEEP)
print(len(dropped), "dropped ->", DROP)
