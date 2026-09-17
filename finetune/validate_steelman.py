#!/usr/bin/env python3
"""
validate_steelman.py - structural gate + claim router for Aubie answers.
Usage: python3 validate_steelman.py output/steelman_clean.txt
Exits 1 if any answer fails structure. Writes output/review_queue.txt.
"""
import re, sys, os

ANSI  = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]|\r')
IDENT = re.compile(r"\bI'?m Mateo\b|\bI am Mateo\b|VanHorn", re.I)
CLAIM = re.compile(
    r'\d|%|\$'                       # any number, percent, dollar
    r'|\b(19|20)\d{2}\b'             # years
    r'|\b[A-Z][a-z]+ (v\.|vs\.) '    # court cases
)
PROPER = re.compile(r'(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{2,}(?: [A-Z][a-z]+)+')

def parse(path):
    d, q = {}, None
    for line in open(path):
        line = ANSI.sub('', line)
        if line.startswith('=== '):
            q = line[4:].strip(); d[q] = []
        elif q is not None:
            d[q].append(line)
    return {k: ''.join(v).strip() for k, v in d.items()}

def check(q, a):
    errs = []
    paras = [p.strip() for p in a.split('\n\n') if p.strip()]
    if len(paras) != 3:
        errs.append(f"{len(paras)} paragraphs (want 3)")
    if paras and not paras[0].startswith(('The strongest case', 'The strongest argument')):
        errs.append("p1 does not open with 'The strongest case'")
    if len(paras) > 1 and not paras[1].startswith('The strongest'):
        errs.append("p2 does not open with 'The strongest'")
    pb = [i for i, p in enumerate(paras) if 'push back' in p[:60].lower()]
    if len(pb) != 1:
        errs.append(f"{len(pb)} pushback paragraphs (want 1)")
    elif pb[0] != len(paras) - 1:
        errs.append("pushback is not the last paragraph")
    if '###' in a or '**' in a:
        errs.append("markdown headers or bold")
    if paras and '?' in paras[-1]:
        errs.append("question in final paragraph")
    if IDENT.search(a):
        errs.append("identity leak (claims to be Mateo)")
    n = len(a.split())
    if not 120 <= n <= 500:
        errs.append(f"{n} words (want 120-500)")
    return errs

def claims(a):
    out = []
    for s in re.split(r'(?<=[.!?])\s+', a):
        if CLAIM.search(s) or PROPER.search(s):
            out.append(s.strip())
    return out

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'output/steelman_clean.txt'
    data = parse(path)
    failed, queue, nclaims = [], [], 0
    for q, a in data.items():
        errs = check(q, a)
        if errs:
            failed.append((q, errs))
        cs = claims(a)
        if cs:
            nclaims += len(cs)
            queue.append((q, cs))

    print(f"{len(data)} answers checked\n")
    if failed:
        print(f"STRUCTURE FAILURES: {len(failed)}")
        for q, errs in failed:
            print(f"  {q[:60]}")
            for e in errs:
                print(f"      - {e}")
    else:
        print("STRUCTURE: all pass")

    with open('output/review_queue.txt', 'w') as f:
        for q, cs in queue:
            f.write(f"=== {q}\n")
            for s in cs:
                f.write(f"  [ ] {s}\n")
            f.write("\n")
    print(f"\nCLAIMS TO VERIFY: {nclaims} sentences -> output/review_queue.txt")

    if failed and '--email' in sys.argv:
        try:
            sys.path.insert(0, os.path.expanduser('~/AUBIEETERNAL/aubieeternal_build'))
            from self_audit import send_alert_email
            body = "\n".join(
                f"{q}\n  - " + "\n  - ".join(e) for q, e in failed
            )
            send_alert_email(f"[AUBIEETERNAL] Steelman validation: {len(failed)} failures", body)
        except Exception as exc:
            print(f"  alert email skipped: {exc}")

    sys.exit(1 if failed else 0)

if __name__ == '__main__':
    main()
