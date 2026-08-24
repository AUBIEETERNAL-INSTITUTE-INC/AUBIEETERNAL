"""
AUBIEETERNAL — Browser Agent
File: /home/aubieeternal/AUBIEETERNAL/browser_agent.py

Gives Aubie real browser hands — navigate, click, extract, research.
Uses browser-use + Playwright (headless Chromium).

Add to assistant_server.py:
    from browser_agent import router as browser_router
    app.include_router(browser_router)
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import asyncio, os

router = APIRouter()

# ── Model setup ───────────────────────────────────────────────
MODEL_PREFERENCE = ["qwen2.5:14b", "qwen2.5:7b", "qwen2.5-coder:7b", "qwen2.5:14b", "llama3.1"]
_cached_model = None

def _best_ollama_model():
    """Pick the best installed Ollama model."""
    global _cached_model
    if _cached_model:
        return _cached_model
    try:
        import urllib.request, json as _json
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as r:
            installed = [m["name"] for m in _json.loads(r.read().decode()).get("models", [])]
        for pref in MODEL_PREFERENCE:
            for inst in installed:
                if inst == pref or inst.startswith(pref.split(":")[0] + ":"):
                    _cached_model = inst
                    return inst
        for inst in installed:
            if "vl" not in inst.lower():
                _cached_model = inst
                return inst
    except Exception:
        pass
    _cached_model = "qwen2.5:7b"
    return _cached_model


# Uses Ollama (local) first, falls back to whatever is available
def get_llm():
    try:
        from langchain_ollama import ChatOllama
        return ChatOllama(model=_best_ollama_model(), temperature=0)
    except Exception:
        pass
    try:
        from langchain_openai import ChatOpenAI
        if os.getenv("OPENAI_API_KEY"):
            return ChatOpenAI(model="gpt-4o-mini", temperature=0)
    except Exception:
        pass
    raise RuntimeError("No LLM available — make sure Ollama is running: ollama serve")


class BrowseRequest(BaseModel):
    task: str                  # natural language task
    max_steps: int = 15        # safety cap on browser actions
    headless: bool = True


class ResearchRequest(BaseModel):
    query: str
    sites: list = []           # optional: restrict to these URLs


# ── /browse — general browser agent ──────────────────────────
@router.post("/browse")
async def browse(req: BrowseRequest):
    """
    Give Aubie a task and it uses a real browser to complete it.
    Example: {"task": "Go to amazon.com and find the price of a Raspberry Pi 5"}
    """
    try:
        from browser_use import Agent
        from playwright.async_api import async_playwright

        llm = get_llm()

        async def run():
            agent = Agent(
                task=req.task,
                llm=llm,
                max_actions_per_step=req.max_steps,
                use_vision=False,   # set True if you want screenshot analysis
            )
            result = await agent.run()
            return result

        result = await asyncio.wait_for(run(), timeout=120)

        # Extract final result text
        final = str(result)
        if hasattr(result, 'final_result'):
            final = result.final_result() or final

        return JSONResponse({"status": "ok", "result": final, "task": req.task})

    except asyncio.TimeoutError:
        return JSONResponse({"status": "timeout", "result": "Browser task timed out after 2 minutes."}, status_code=408)
    except Exception as e:
        return JSONResponse({"status": "error", "result": str(e)}, status_code=500)


# ── /browse/research — structured web research ────────────────
@router.post("/browse/research")
async def research(req: ResearchRequest):
    """
    Research a topic across the web and return a summary.
    Example: {"query": "latest price of MG996R servos on Amazon"}
    """
    task = f"Research the following and give me a detailed summary: {req.query}"
    if req.sites:
        sites_str = ", ".join(req.sites)
        task += f". Focus on these sites: {sites_str}"

    return await browse(BrowseRequest(task=task, max_steps=20))


# ── /browse/extract — extract data from a specific URL ────────
class ExtractRequest(BaseModel):
    url: str
    what: str   # what to extract, e.g. "all product prices"

@router.post("/browse/extract")
async def extract(req: ExtractRequest):
    """
    Go to a URL and extract specific information.
    Example: {"url": "https://amazon.com/...", "what": "current price and stock"}
    """
    task = f"Go to {req.url} and extract: {req.what}. Return the information clearly."
    return await browse(BrowseRequest(task=task, max_steps=10))


# ── /browse/status — health check ─────────────────────────────
@router.get("/browse/status")
async def browse_status():
    try:
        from browser_use import Agent
        from playwright.async_api import async_playwright
        llm = get_llm()
        return {"status": "ready", "llm": str(type(llm).__name__)}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
