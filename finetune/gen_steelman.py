import json, re, urllib.request

qs = [l.strip() for l in open('output/steelman_questions.txt') if l.strip()]
qs = [q for q in qs if 'death penalty' not in q.lower()]   # Modelfile example poisons it
out = {}
for i, q in enumerate(qs, 1):
    body = json.dumps({"model": "aubie", "prompt": q, "stream": False,
                       "options": {"num_predict": 800, "temperature": 0.7}}).encode()
    req = urllib.request.Request('http://localhost:11434/api/generate', data=body,
                                 headers={'Content-Type': 'application/json'})
    txt = json.loads(urllib.request.urlopen(req, timeout=600).read())['response']
    paras = [p.strip() for p in txt.split('\n\n') if p.strip()]
    cut = next((j for j, p in enumerate(paras) if 'push back' in p[:60].lower()), None)
    if cut is None:
        print(f"{i:3} SKIP  {q[:50]}"); continue
    kept = paras[:cut+1]
    last = re.split(r'(?<=[.!?])\s+', kept[-1])
    while last and last[-1].strip().endswith('?'):
        last.pop()
    if not last:
        print(f"{i:3} SKIP  {q[:50]}"); continue
    kept[-1] = ' '.join(last)
    if any('###' in p or '**' in p for p in kept):
        print(f"{i:3} MKDN  {q[:50]}"); continue
    out[q] = '\n\n'.join(kept)
    print(f"{i:3} ok    {q[:50]}")

with open('output/steelman_clean.txt', 'w') as f:
    for q, a in out.items():
        f.write(f"=== {q}\n{a}\n\n")
print(len(out), "clean answers -> output/steelman_clean.txt")
