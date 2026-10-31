import sys; sys.path.insert(0, ".")
import m_web_search_tool as t, m_link_rewrite_filter as f
tool = t.Tools()
for q in ["SearXNG", "Englewood Florida history", "Linux disk usage command"]:
    out = tool.web_search(q)
    print(out.split("RULES")[0][:900]); print("-" * 60)
bad = t.Tools(); bad.valves.searxng_url = "http://127.0.0.1:9"
print("DOWN CASE:", bad.web_search("test")[:160])
print("EMPTY CASE:", tool.web_search("  "))
s = "Open http://127.0.0.1:8080/c/1 or avatar http://localhost:8460/ and search http://127.0.0.1:8087/search?q=x"
print("REWRITE:", f.rewrite(s))
r = t.searx_search("python", n=5)
assert len(r) <= 5 and all(x["url"].startswith("http") and "127.0.0.1" not in x["url"] for x in r), r
print("ASSERTS OK, n =", len(r))
