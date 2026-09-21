import re, sys

TXT = "output/steelman_clean.txt"
data = open(TXT, "rb").read()

bad_ctrl = [b for b in data if b < 32 and b not in (9, 10, 13)]
text = data.decode("utf-8", "replace")
eins = re.findall(r"\b\d{2}-\d{7}\b", text)
names = re.findall(r"\b(?:VanHorn|Mateo|Gabriela|Matthew)\b", text)

print(f"control chars: {len(bad_ctrl)}")
print(f"EIN-shaped numbers: {len(eins)} {set(eins)}")
print(f"personal names: {len(names)} {set(names)}")

sys.exit(1 if (bad_ctrl or eins or names) else 0)
