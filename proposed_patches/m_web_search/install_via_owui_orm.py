"""Install m_web_search into Open WebUI using Open WebUI's own ORM functions (same path as the
/api/v1/tools/create route and the model editor), then attach to aubie-it and apply the proposed prompt.
Run with the Open WebUI python and DATA_DIR set. Idempotent: skips the tool insert if it exists."""
import asyncio, json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL_ID, TOOL_NAME, MODEL_ID = "m_web_search", "M web search", "aubie-it"


async def main():
    from open_webui.utils.plugin import load_tool_module_by_id, replace_imports
    from open_webui.utils.tools import get_tool_specs
    from open_webui.models.tools import Tools, ToolForm, ToolMeta
    from open_webui.models.models import Models, ModelForm

    model = await Models.get_model_by_id(MODEL_ID)
    owner = model.user_id
    if await Tools.get_tool_by_id(TOOL_ID) is None:
        content = replace_imports((HERE / "m_web_search_tool.py").read_text())
        module, frontmatter, _ = await load_tool_module_by_id(TOOL_ID, content=content)
        specs = get_tool_specs(module)
        form = ToolForm(id=TOOL_ID, name=TOOL_NAME, content=content,
                        meta=ToolMeta(description="Real web search via local SearXNG (format=json): top 5 title/url/snippet; cite only returned urls.",
                                      manifest=frontmatter, has_user_valves=hasattr(module, "UserValves")),
                        commit_message="install m_web_search (2026-10-31)")
        await Tools.insert_new_tool(owner, form, specs, module=module)
        print("tool inserted; specs:", [s["name"] for s in specs])
    else:
        print("tool already present; not changed")

    data = model.model_dump()
    meta, params = data["meta"], data["params"]
    ids = list(meta.get("toolIds") or [])
    for t in ("aubie_task", TOOL_ID):
        if t not in ids:
            ids.append(t)
    meta["toolIds"] = ids
    orig = (HERE / "m_it_system_prompt.ORIGINAL.txt").read_text()
    new = (HERE / "m_it_system_prompt.PROPOSED.txt").read_text()
    if params.get("system") == new:
        print("prompt already applied")
    elif params.get("system") != orig:
        sys.exit("ABORT: live system prompt differs from ORIGINAL copy; not overwriting")
    else:
        params["system"] = new
    form = ModelForm(id=MODEL_ID, base_model_id=data.get("base_model_id"), name=data["name"], meta=meta,
                     params=params, is_active=data.get("is_active", True),
                     commit_message="attach m_web_search + web-search prompt rules (2026-10-31)")
    await Models.update_model_by_id(MODEL_ID, form, user_id=owner)
    m2 = await Models.get_model_by_id(MODEL_ID)
    print("aubie-it toolIds:", m2.meta.model_dump().get("toolIds"), "| prompt len:", len(m2.params.model_dump().get("system", "")))

asyncio.run(main())
