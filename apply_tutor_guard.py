"""Wires tutor_guard into ~/AUBIEETERNAL/app.py. Makes a timestamped backup first.
Refuses to change anything if the code doesn't look as expected."""
import re, shutil, sys, time
from pathlib import Path

app = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "AUBIEETERNAL" / "app.py")
s = app.read_text()
if "tutor_guard" in s:
    sys.exit("already wired in; nothing to do")

a = re.findall(r"^([ \t]*)client, model, provider, pname = get_ai_client\(\)\n", s, re.M)
b = re.findall(r"^([ \t]*)reply = response\.choices\[0\]\.message\.content\n", s, re.M)
if len(a) != 1 or len(b) != 1:
    sys.exit(f"expected 1 match each, found get_ai_client={len(a)} reply={len(b)}; not patching")

ind_a, ind_b = a[0], b[0]
s = s.replace(
    f"{ind_a}client, model, provider, pname = get_ai_client()\n",
    f"{ind_a}client, model, provider, pname = get_ai_client()\n"
    f"{ind_a}import tutor_guard as _tg\n"
    f"{ind_a}client = _tg.CoolClient(client)  # heat check before every model call\n", 1)
s = s.replace(
    f"{ind_b}reply = response.choices[0].message.content\n",
    f"{ind_b}reply = response.choices[0].message.content\n"
    f"{ind_b}try:\n"
    f"{ind_b}    reply = _tg.guard(reply, user_input, client, model,\n"
    f"{ind_b}        [{{\"role\": \"system\", \"content\": system + \"\\n\\n\" + COACHING_RULE}}]\n"
    f"{ind_b}        + st.session_state.messages[-6:]\n"
    f"{ind_b}        + [{{\"role\": \"system\", \"content\": \"Reminder before you reply: \" + COACHING_RULE}}])\n"
    f"{ind_b}except Exception as _ge:\n"
    f"{ind_b}    print('tutor_guard error:', _ge, flush=True)\n", 1)

bak = app.with_name(app.name + ".bak_guard_" + time.strftime("%Y%m%d_%H%M"))
shutil.copy2(app, bak)
app.write_text(s)
print("patched", app, "| backup:", bak)
