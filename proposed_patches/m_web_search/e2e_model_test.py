"""End-to-end behaviour test that mirrors the live path without auth: Open WebUI (native tools) ->
aubie_it_chat tool_passthrough -> Ollama qwen2.5:14b with system prompt + GUARD + tool specs from webui.db.
Executes the tool calls with the INSTALLED tool code from the DB, then gets the final answer."""
import json, re, sqlite3, sys, types, urllib.request, ast
sys.path.insert(0, "/home/aubieeternal/aubie-it-chat")
db = sqlite3.connect("file:/srv/vanhorn/openwebui-data/webui.db?mode=ro", uri=True)
params = json.loads(db.execute("select params from model where id='aubie-it'").fetchone()[0])
src = open("/home/aubieeternal/aubie-it-chat/aubie_it_chat.py").read()
m = re.search(r"^GUARD = \(.*?^\)", src, re.S | re.M); ns = {}; exec(m.group(0), ns); GUARD = ns["GUARD"]
tools, impl = [], {}
for tid in ("aubie_task", "m_web_search"):
    content, specs = db.execute("select content, specs from tool where id=?", (tid,)).fetchone()
    for s in json.loads(specs):
        tools.append({"type": "function", "function": s})
    if tid == "m_web_search":
        mod = types.ModuleType("mws"); exec(content, mod.__dict__); impl = mod.Tools()
msgs = [{"role": "system", "content": params["system"] + "\n\n" + GUARD},
        {"role": "user", "content": sys.argv[1] if len(sys.argv) > 1 else "search the web for SearXNG"}]

def call():
    body = {"model": "qwen2.5:14b", "messages": msgs, "tools": tools, "stream": False}
    r = urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:11434/v1/chat/completions",
        json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=300)
    return json.loads(r.read())["choices"][0]["message"]

for step in range(4):
    msg = call(); tcs = msg.get("tool_calls") or []
    if not tcs:
        print("FINAL ANSWER:\n" + (msg.get("content") or "")); break
    msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": tcs})
    for tc in tcs:
        fn = tc["function"]["name"]; args = json.loads(tc["function"].get("arguments") or "{}")
        print(f"TOOL CALL: {fn}({args})")
        out = getattr(impl, fn)(**args) if fn in ("web_search", "rig_links") else "(aubie_task not executed in test)"
        msgs.append({"role": "tool", "tool_call_id": tc.get("id"), "content": out})
        print("  -> returned", len(out), "chars; urls:", re.findall(r"url: (\S+)", out)[:5])
