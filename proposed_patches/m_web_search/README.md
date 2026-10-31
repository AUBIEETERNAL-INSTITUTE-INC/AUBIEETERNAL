# M web search fix (DRAFT, not installed) - 2026-10-31

## What was wrong
- Model `aubie-it` ("M IT") in Open WebUI has only one tool attached: `aubie_task` (functions
  `aubie_task` + `aubie_approve`). It is a generic job runner -> AUBIE endpoint 127.0.0.1:8765.
  There is NO search tool. (`aubie_it_tool` "M shell (admin)" and `rig_diagnostics` exist but are not attached.)
- M IT's system prompt (SEARCH CHECKS + RIG CHEAT SHEET) tells it to test search with
  `curl -s -o /dev/null -w '%{http_code}' 'http://127.0.0.1:8087/search?q=test'` - a health check that
  only returns "200". M used that for real questions, got "200", then invented results and 127.0.0.1 links.
- Open WebUI's built-in web search is configured (engine searxng, `http://127.0.0.1:8087/search?q=<query>`,
  8 results) but `builtin_tools` is false for M IT and it needs the per-chat "Web search" toggle, so M never used it.
- Link schemes verified with `curl -k` on 2026-10-31: https://m.tail00eb41.ts.net:8463 (M avatar) 200, http on 8463 = 400
  (HTTPS only); http://m.tail00eb41.ts.net:8080 (Open WebUI) 200 (no https on 8080);
  https://aubieeternal.tail00eb41.ts.net:8443 (Streamlit portal) 200, http = 400; bare https://aubieeternal.tail00eb41.ts.net = 404.
  https://m.tail00eb41.ts.net:8443 is also Streamlit (local 8501). https://m.tail00eb41.ts.net (-> 8800) = 404 at "/".

## Files
- `m_web_search_tool.py` - new Open WebUI Tool: `web_search(query)` (SearXNG format=json, top 5 title/url/snippet,
  strict "cite only these urls, never fabricate" rules, clear failure/no-results messages) + `rig_links()`.
- `m_link_rewrite_filter.py` - optional Open WebUI Filter (outlet): rewrites 127.0.0.1/localhost links in M's
  replies to Tailscale addresses (8080, 8460/8463, 8501->:8443, 8800->:443); other ports (8087, 8765) become a note.
- `m_it_system_prompt.ORIGINAL.txt` / `.PROPOSED.txt` / `.diff` (chmod 600) - prompt change: marks the curl as a
  health check only, adds WEB SEARCH rules and RIG LINKS.
- `test_standalone.py`, `test_output.txt` - standalone test vs 127.0.0.1:8087 (passed).

## Install (you do this; nothing has been changed live)
1. Backup: `cp /srv/vanhorn/openwebui-data/webui.db /srv/vanhorn/openwebui-data/webui.db.bak-$(date +%Y%m%d)-websearch`
   (better: `sqlite3 /srv/vanhorn/openwebui-data/webui.db ".backup /srv/vanhorn/openwebui-data/webui.db.bak-$(date +%Y%m%d)-websearch"`)
2. Open WebUI (http://m.tail00eb41.ts.net:8080) -> Workspace -> Tools -> "+" -> paste `m_web_search_tool.py`,
   Tool ID `m_web_search`, name "M web search" -> Save. (Valves: searxng_url http://127.0.0.1:8087, result_count 5.)
3. Workspace -> Models -> M IT -> edit -> Tools: tick "M web search" (keep "M task runner") -> System Prompt: replace
   with the contents of `m_it_system_prompt.PROPOSED.txt` -> Save.
4. Optional: Admin Panel -> Functions -> "+" -> paste `m_link_rewrite_filter.py` -> enable it, then attach it to M IT
   (Models -> M IT -> Filters) or make it Global.
5. Test in a new M IT chat: "search the web for SearXNG". Expect [1]..[5] with real https urls, no 127.0.0.1.
   Then "give me the link to the avatar" -> https://m.tail00eb41.ts.net:8463.
6. No service restart needed; Open WebUI loads tools/functions on save.
Rollback: delete the tool/filter in the UI and paste back `m_it_system_prompt.ORIGINAL.txt` (or restore the db backup
with Open WebUI stopped).

Note: this folder is inside the git repo ~/AUBIEETERNAL and is NOT gitignored. The prompt copies are chmod 600 but
would still be committed by `git add -A`. Don't commit them (or move the folder out) - nothing has been committed.

## INSTALLED 2026-10-31 ~06:52 EDT (by Grok Bot, user-approved)
- Backup: /srv/vanhorn/openwebui-data/webui.db.bak-20261031-websearch (sqlite backup API, integrity ok, chmod 600)
- Installed with `install_via_owui_orm.py` (Open WebUI 0.12.2's own Tools.insert_new_tool / Models.update_model_by_id,
  so tool_history/model_history/version_id are written like the UI does). Rehearsed on a temp DB copy first.
- Tool `m_web_search` ("M web search": web_search, rig_links) owned by the admin; aubie-it toolIds = [aubie_task, m_web_search];
  aubie-it system prompt = m_it_system_prompt.PROPOSED.txt. Filter NOT installed.
- e2e_model_test.py / e2e_output.txt: Ollama qwen2.5:14b (same path as aubie_it_chat tool_passthrough) called web_search and
  answered with real cited urls; asked for links it gave the Tailscale urls.
## UNDO
- UI: Workspace -> Models -> M IT -> untick "M web search", paste back m_it_system_prompt.ORIGINAL.txt (or use the model's
  version history); Workspace -> Tools -> delete "M web search".
- Or full restore: stop Open WebUI, `cp /srv/vanhorn/openwebui-data/webui.db.bak-20261031-websearch /srv/vanhorn/openwebui-data/webui.db`,
  remove webui.db-wal/-shm, start it.
