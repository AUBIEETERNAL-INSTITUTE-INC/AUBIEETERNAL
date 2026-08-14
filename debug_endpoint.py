"""
AUBIEETERNAL — /debug endpoint
File: /home/aubieeternal/AUBIEETERNAL/debug_endpoint.py

Add to assistant_server.py:
    from debug_endpoint import router as debug_router
    app.include_router(debug_router)

Requires memory_layer.py in the same directory.
"""

import asyncio
import difflib
import subprocess
import textwrap
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from memory_layer import (
    find_similar_crashes,
    log_crash,
    resolve_crash,
)

router = APIRouter()

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
DEBUG_MODEL = "qwen2.5:14b"
MAX_ATTEMPTS = 3

# ─── Request / response models ────────────────────────────────────────────────

class DebugRequest(BaseModel):
    script_path: str          # absolute path on Ryzen, e.g. "/home/aubieeternal/AUBIEETERNAL/assistant_server.py"
    args: list[str] = []      # extra CLI args to pass
    auto_apply: bool = False  # if True, apply fix without asking (ONLY for non-servo code)


class DebugResponse(BaseModel):
    success: bool
    attempts: int
    final_error: Optional[str] = None
    fix_summary: Optional[str] = None
    diff: Optional[str] = None
    awaiting_approval: bool = False   # True when auto_apply=False and a fix is ready
    crash_id: Optional[int] = None


# Pending fixes waiting for human approval  {crash_id: {"path": ..., "new_content": ..., "diff": ...}}
_pending_fixes: dict[int, dict] = {}


# ─── Approval endpoint ────────────────────────────────────────────────────────

class ApproveRequest(BaseModel):
    crash_id: int
    approve: bool


@router.post("/debug/approve")
async def approve_fix(req: ApproveRequest):
    fix = _pending_fixes.pop(req.crash_id, None)
    if fix is None:
        raise HTTPException(404, "No pending fix for that crash_id")
    if not req.approve:
        return {"status": "rejected"}
    Path(fix["path"]).write_text(fix["new_content"], encoding="utf-8")
    resolve_crash(req.crash_id, fix["root_cause"], fix["diff"])
    return {"status": "applied", "path": fix["path"]}


# ─── Main debug loop ──────────────────────────────────────────────────────────

@router.post("/debug", response_model=DebugResponse)
async def debug_script(req: DebugRequest):
    script = Path(req.script_path)
    if not script.exists():
        raise HTTPException(400, f"Script not found: {req.script_path}")

    crash_id: Optional[int] = None
    last_error = ""

    for attempt in range(1, MAX_ATTEMPTS + 1):

        # 1. Run the script
        result = subprocess.run(
            ["python3", str(script)] + req.args,
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            if crash_id:
                resolve_crash(crash_id, "script ran cleanly", "")
            return DebugResponse(success=True, attempts=attempt)

        error_text = (result.stderr + result.stdout).strip()
        last_error = error_text

        # 2. Log / update crash record
        if crash_id is None:
            crash_id = log_crash(str(script), error_text)

        # 3. Check prior similar crashes
        prior = find_similar_crashes(error_text, limit=2)
        prior_context = ""
        if prior:
            prior_context = "\n\nPrior similar crashes and their fixes:\n" + "\n---\n".join(
                f"Error: {p['error_text'][:300]}\nFix: {p['fix_applied']}" for p in prior
            )

        # 4. Read the source file for context (first 300 lines)
        source_lines = script.read_text(encoding="utf-8", errors="replace").splitlines()
        source_snippet = "\n".join(source_lines[:300])

        # 5. Ask the model
        prompt = textwrap.dedent(f"""
            You are a Python debugging assistant. A script failed. Return ONLY the corrected
            full file content — no explanation, no markdown fences, no commentary.
            If you cannot determine a safe fix, reply with exactly: GIVE_UP

            Script path: {script}
            Error (attempt {attempt}/{MAX_ATTEMPTS}):
            {error_text[:2000]}
            {prior_context}

            Current file content (first 300 lines):
            {source_snippet}
        """).strip()

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(OLLAMA_URL, json={
                "model": DEBUG_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            })
        resp.raise_for_status()
        proposed = resp.json()["message"]["content"].strip()

        if proposed == "GIVE_UP" or not proposed:
            break

        # Strip accidental markdown fences if model added them
        if proposed.startswith("```"):
            lines = proposed.splitlines()
            proposed = "\n".join(
                l for l in lines
                if not l.startswith("```")
            )

        original = script.read_text(encoding="utf-8", errors="replace")
        patch = "\n".join(difflib.unified_diff(
            original.splitlines(), proposed.splitlines(),
            fromfile=f"{script.name} (original)",
            tofile=f"{script.name} (proposed)",
            lineterm=""
        ))

        # 6. Apply or queue for approval
        if req.auto_apply:
            script.write_text(proposed, encoding="utf-8")
            resolve_crash(crash_id, "auto-applied", patch)
        else:
            _pending_fixes[crash_id] = {
                "path": str(script),
                "new_content": proposed,
                "diff": patch,
                "root_cause": f"attempt {attempt} model fix"
            }
            return DebugResponse(
                success=False,
                attempts=attempt,
                final_error=error_text[:1000],
                diff=patch,
                awaiting_approval=True,
                crash_id=crash_id
            )

    # Exhausted attempts
    return DebugResponse(
        success=False,
        attempts=MAX_ATTEMPTS,
        final_error=last_error[:2000],
        crash_id=crash_id
    )
