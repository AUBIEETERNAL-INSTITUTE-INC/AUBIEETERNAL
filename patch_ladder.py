"""Hardware ladder for thinking_mode_config.py: every mode picks the biggest model the machine has pulled.
Run on the rig from ~/AUBIEETERNAL. Backs up first; refuses if the file doesn't look as expected."""
import shutil, sys, time
from pathlib import Path
p = Path(sys.argv[1] if len(sys.argv) > 1 else "thinking_mode_config.py")
s = p.read_text()
if "MODEL_LADDER" in s:
    sys.exit("ladder already in; nothing to do")
old_fast = 'FAST_CANDIDATES = [\n    "qwen2.5:14b",\n]'
old_mfm_fast = '    if key == "fast":\n        return resolve_fast_model(available)\n    if key == "deep":\n        return DEEP_MODEL\n    return BALANCED_MODEL\n'
old_fallback = '            return cand\n    return "qwen2.5:7b"\n'
for name, frag in [("FAST_CANDIDATES", old_fast), ("model_for_mode", old_mfm_fast), ("fast fallback", old_fallback)]:
    if s.count(frag) != 1:
        sys.exit(f"{name} block not found exactly once; not patching")
s = s.replace(old_fast,
    '# Biggest first; each machine uses the first one it has pulled (students run this on their own hardware).\n'
    'MODEL_LADDER = [\n'
    '    "qwen2.5:14b",   # 12 GB+ GPU (the Ryzen rig)\n'
    '    "qwen2.5:7b",    # ~8 GB GPU\n'
    '    "qwen2.5:3b",    # small GPU or CPU-only laptop\n'
    ']\n'
    'FAST_CANDIDATES = MODEL_LADDER')
s = s.replace(old_fallback,
    '            return cand\n'
    '    for a in sorted(avail):  # nothing from the ladder: use any qwen2.5 the machine has\n'
    '        if a.startswith("qwen2.5:") and ":" in a:\n'
    '            return a\n'
    '    return MODEL_LADDER[-1]  # smallest; the app will say it is not pulled\n')
s = s.replace(old_mfm_fast,
    '    # Every mode walks the same ladder, so a laptop without the 14b still works in all three.\n'
    '    # Deep differs by its system add-on, not by a bigger model.\n'
    '    return resolve_fast_model(available)\n')
bak = p.with_name(p.name + ".bak_ladder_" + time.strftime("%Y%m%d_%H%M"))
shutil.copy2(p, bak); p.write_text(s); print("patched", p, "| backup:", bak)
