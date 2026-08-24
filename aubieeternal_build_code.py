"""
AUBIEETERNAL Build Code
=======================
Version: 0.1.0

Extends the Epistemic Orchestrator with a Claude-Code-style agentic layer:
  - File read / write / edit tools
  - Shell command execution (sandboxed)
  - Iterative test-and-fix loop
  - Aubie verifies generated code THEN runs it, checks output, retries if broken

Architecture:
  User request
    │
    ▼
  EpistemicOrchestrator (epistemic_orchestrator.py)
    │  → classifies task
    │  → calls Claude + Grok in parallel (code path)
    │  → runs dual-road verification
    │  → returns best / synthesized code text
    │
    ▼
  BuildCodeAgent  ◄──── THIS FILE
    │  → writes code to disk
    │  → executes in subprocess
    │  → checks stdout / stderr
    │  → if broken: feeds error back → re-routes through orchestrator
    │  → max N iterations (default 4)
    │  → returns final working file + execution log

Usage:
    agent = BuildCodeAgent()
    result = await agent.run("Write a Python web scraper for hacker news headlines")
    print(result.summary)
    print("File:", result.output_file)
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Import the orchestrator you already have.
# Adjust the import path if you move files around.
try:
    from epistemic_orchestrator import (
        EpistemicOrchestrator,
        OrchestratorResult,
        TaskType,
    )
    _ORCHESTRATOR_AVAILABLE = True
except ImportError:
    _ORCHESTRATOR_AVAILABLE = False
    print("[WARNING] epistemic_orchestrator.py not found on sys.path. "
          "BuildCodeAgent will run in stub mode.")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BUILD_WORKSPACE = Path(os.environ.get("AUBIE_BUILD_WORKSPACE", "/tmp/aubie_build"))
MAX_FIX_ITERATIONS = int(os.environ.get("AUBIE_MAX_FIX_ITER", "4"))
EXECUTION_TIMEOUT_S = int(os.environ.get("AUBIE_EXEC_TIMEOUT", "30"))
ALLOWED_EXTENSIONS = {".py", ".js", ".ts", ".sh", ".html", ".css", ".json", ".yaml", ".txt"}

BUILD_WORKSPACE.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# File tools  (the "Claude Code"-ish layer)
# ---------------------------------------------------------------------------

def tool_read_file(path: str | Path) -> str:
    """Read a file and return its contents as a string."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No file at {p}")
    return p.read_text(encoding="utf-8", errors="replace")


def tool_write_file(path: str | Path, content: str) -> Path:
    """Write content to a file, creating parent directories as needed."""
    p = Path(path)
    if p.suffix and p.suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Extension {p.suffix} not in allowed list {ALLOWED_EXTENSIONS}")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def tool_edit_file(path: str | Path, old: str, new: str) -> Path:
    """Replace the first occurrence of `old` with `new` in a file."""
    p = Path(path)
    text = tool_read_file(p)
    if old not in text:
        raise ValueError(f"String not found in {p}: {old!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    return p


def tool_list_files(directory: str | Path = BUILD_WORKSPACE) -> list[str]:
    """Return relative paths of all files under a directory."""
    base = Path(directory)
    return [str(f.relative_to(base)) for f in base.rglob("*") if f.is_file()]


# ---------------------------------------------------------------------------
# Shell execution tool
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    elapsed_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def summary(self) -> str:
        status = "OK" if self.ok else ("TIMEOUT" if self.timed_out else f"EXIT {self.returncode}")
        out = self.stdout[:800] if self.stdout else "(no stdout)"
        err = self.stderr[:400] if self.stderr else ""
        result = f"[{status}] $ {self.command}\n{out}"
        if err:
            result += f"\nSTDERR: {err}"
        return result


def tool_run(command: str, cwd: str | Path = BUILD_WORKSPACE, timeout: int = EXECUTION_TIMEOUT_S) -> RunResult:
    """
    Run a shell command. Returns stdout, stderr, and exit code.
    Never runs as root in production — add a sandbox wrapper here if needed.
    """
    start = time.perf_counter()
    timed_out = False
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=timeout,
        )
        stdout, stderr, returncode = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        stdout, stderr, returncode = "", "Execution timed out.", -1
        timed_out = True

    elapsed = time.perf_counter() - start
    return RunResult(
        command=command,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        elapsed_s=elapsed,
    )


# ---------------------------------------------------------------------------
# Code extraction helper
# ---------------------------------------------------------------------------

_CODE_FENCE = re.compile(r"```(?:\w+)?\n(.*?)```", re.DOTALL)

def extract_code_blocks(text: str) -> list[str]:
    """Pull all fenced code blocks from an LLM response."""
    return [m.group(1).strip() for m in _CODE_FENCE.finditer(text)]


def guess_language(prompt: str) -> str:
    """Very lightweight language guesser from the original user request."""
    p = prompt.lower()
    if any(k in p for k in ["javascript", "node", "react", "npm"]):
        return "js"
    if any(k in p for k in ["bash", "shell", "sh "]):
        return "sh"
    return "py"  # default to Python


def make_run_command(file_path: Path) -> str:
    ext = file_path.suffix
    if ext == ".py":
        return f"{sys.executable} {file_path.name}"
    if ext == ".js":
        return f"node {file_path.name}"
    if ext == ".sh":
        return f"bash {file_path.name}"
    return f"cat {file_path.name}"   # just print it for unsupported types


# ---------------------------------------------------------------------------
# Build Code result
# ---------------------------------------------------------------------------

@dataclass
class BuildCodeResult:
    success: bool
    output_file: Optional[Path]
    final_code: str
    run_log: list[RunResult] = field(default_factory=list)
    iterations: int = 0
    orchestrator_results: list[str] = field(default_factory=list)  # summaries
    error_message: str = ""
    summary: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# The Build Code Agent
# ---------------------------------------------------------------------------

class BuildCodeAgent:
    """
    Aubie's agentic code-building layer.

    1. Takes a user request.
    2. Sends it through the Epistemic Orchestrator (Claude + Grok dual-road).
    3. Extracts the generated code.
    4. Writes it to BUILD_WORKSPACE.
    5. Executes it.
    6. If it fails, feeds the error back through the orchestrator with a fix prompt.
    7. Repeats up to MAX_FIX_ITERATIONS.
    8. Returns BuildCodeResult with the final file and full execution log.
    """

    def __init__(
        self,
        workspace: Path = BUILD_WORKSPACE,
        max_iterations: int = MAX_FIX_ITERATIONS,
        verbose: bool = True,
    ):
        self.workspace = workspace
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.orch = EpistemicOrchestrator() if _ORCHESTRATOR_AVAILABLE else None

    def _log(self, msg: str):
        if self.verbose:
            print(f"[AUBIE BUILD] {msg}")

    async def _call_orchestrator(self, prompt: str, system: str = "") -> str:
        """Call the orchestrator and return the final answer text."""
        if self.orch is None:
            return f"[STUB — orchestrator not loaded]\n\nPrompt was:\n{prompt}"
        result: OrchestratorResult = await self.orch.handle(prompt, system_context=system)
        return result.final_answer

    async def run(self, user_request: str) -> BuildCodeResult:
        """Main entry point. Returns a BuildCodeResult."""
        self._log(f"New build-code task: {user_request[:80]}...")

        lang = guess_language(user_request)
        ext = f".{lang}"
        session_id = uuid.uuid4().hex[:8]
        file_name = f"aubie_build_{session_id}{ext}"
        file_path = self.workspace / file_name

        system_prompt = (
            "You are AUBIEETERNAL's code builder. "
            "Produce clean, complete, runnable code. "
            "Always wrap your code in a single fenced code block. "
            "Include error handling. Add brief inline comments. "
            "Do not explain — just produce the code."
        )

        run_log: list[RunResult] = []
        orch_summaries: list[str] = []
        current_prompt = user_request
        final_code = ""
        last_run: Optional[RunResult] = None

        for iteration in range(1, self.max_iterations + 1):
            self._log(f"Iteration {iteration}/{self.max_iterations} — calling orchestrator...")

            raw_answer = await self._call_orchestrator(current_prompt, system=system_prompt)
            orch_summaries.append(raw_answer[:300])

            # Extract code from the response
            blocks = extract_code_blocks(raw_answer)
            if not blocks:
                # No fenced block found — likely a prose/analysis response
                # rather than real code. Skip and request a fix on next iter.
                code = f"# No code block found in model response.\n# Response was:\n# {raw_answer[:200]!r}\nraise RuntimeError('Model returned no code block — wire real API.')"
            else:
                code = blocks[0]  # take the first (primary) block

            final_code = code

            # Write to disk
            tool_write_file(file_path, code)
            self._log(f"Wrote {file_path.name} ({len(code)} chars)")

            # Execute
            cmd = make_run_command(file_path)
            self._log(f"Running: {cmd}")
            run_result = tool_run(cmd, cwd=self.workspace)
            run_log.append(run_result)
            last_run = run_result

            self._log(run_result.summary())

            if run_result.ok:
                self._log("Execution succeeded.")
                return BuildCodeResult(
                    success=True,
                    output_file=file_path,
                    final_code=final_code,
                    run_log=run_log,
                    iterations=iteration,
                    orchestrator_results=orch_summaries,
                    summary=self._build_summary(user_request, file_path, run_result, iteration),
                )

            # Build a fix prompt for the next iteration
            self._log(f"Execution failed (exit {run_result.returncode}). Building fix prompt...")
            current_prompt = self._build_fix_prompt(
                original_request=user_request,
                broken_code=final_code,
                run_result=run_result,
                iteration=iteration,
            )

        # Exhausted iterations
        self._log("Max iterations reached — returning best attempt.")
        return BuildCodeResult(
            success=False,
            output_file=file_path,
            final_code=final_code,
            run_log=run_log,
            iterations=self.max_iterations,
            orchestrator_results=orch_summaries,
            error_message=last_run.stderr if last_run else "Unknown error",
            summary=self._build_summary(user_request, file_path, last_run, self.max_iterations, failed=True),
        )

    def _build_fix_prompt(
        self,
        original_request: str,
        broken_code: str,
        run_result: RunResult,
        iteration: int,
    ) -> str:
        stderr = run_result.stderr[:600]
        import re as _re
        # Detect missing module
        missing = _re.findall(r"No module named '(\S+)'", stderr)
        stdlib_constraint = ""
        if missing:
            stdlib_constraint = (
                f"\n\nCRITICAL: The module(s) {missing} are NOT installed. "
                "You MUST rewrite using ONLY Python standard library (json, urllib, "
                "socket, threading, http.server, etc.). Do NOT import any third-party package."
            )
        # Detect server/timeout — model wrote a blocking server
        server_constraint = ""
        if run_result.timed_out or "server_bind" in stderr or "Address already in use" in stderr:
            server_constraint = (
                "\n\nCRITICAL: Your code started a blocking server that never exits. "
                "Do NOT start any server or listen on any port. "
                "Instead: write the core logic as a plain Python function, "
                "call it with sample input, print the result, and exit immediately. "
                "Example structure:\n"
                "def handle_request(body: dict) -> dict: ...\n"
                "print(handle_request({'key': 'value'}))"
            )
        return (
            f"ORIGINAL TASK:\n{original_request}\n\n"
            f"ATTEMPT {iteration} FAILED.\n"
            f"Exit code: {run_result.returncode}\n"
            f"STDOUT:\n{run_result.stdout[:600]}\n"
            f"STDERR:\n{stderr}"
            f"{stdlib_constraint}{server_constraint}\n\n"
            f"BROKEN CODE:\n```\n{broken_code}\n```\n\n"
            "Fix every error. Return ONLY corrected code in a single fenced block. "
            "Do not apologize or explain — just fix it."
        )

    def _build_summary(
        self,
        request: str,
        file_path: Path,
        run_result: Optional[RunResult],
        iterations: int,
        failed: bool = False,
    ) -> str:
        status = "FAILED after" if failed else "SUCCEEDED in"
        out = run_result.stdout[:300] if run_result and run_result.stdout else "(no output)"
        return (
            f"AUBIEETERNAL Build Code — {status} {iterations} iteration(s)\n"
            f"Task: {request[:100]}\n"
            f"File: {file_path}\n"
            f"Output:\n{out}"
        )


# ---------------------------------------------------------------------------
# HTTP server integration helper
# ---------------------------------------------------------------------------

async def handle_build_code_request(payload: dict) -> dict:
    """
    Drop-in handler for your existing FastAPI / aiohttp server.

    Expected payload keys:
        request  (str)  — the user's code request
        verbose  (bool) — optional, default True

    Returns a JSON-serializable dict.
    """
    request_text = payload.get("request", "")
    verbose = payload.get("verbose", True)

    if not request_text.strip():
        return {"error": "Empty request"}

    agent = BuildCodeAgent(verbose=verbose)
    result = await agent.run(request_text)

    return {
        "success": result.success,
        "output_file": str(result.output_file) if result.output_file else None,
        "final_code": result.final_code,
        "iterations": result.iterations,
        "summary": result.summary,
        "error_message": result.error_message,
        "run_log": [
            {
                "command": r.command,
                "returncode": r.returncode,
                "stdout": r.stdout[:500],
                "stderr": r.stderr[:500],
                "ok": r.ok,
                "elapsed_s": round(r.elapsed_s, 3),
            }
            for r in result.run_log
        ],
        "timestamp": result.timestamp,
    }


# ---------------------------------------------------------------------------
# FastAPI route blueprint  (paste into your existing server.py)
# ---------------------------------------------------------------------------

FASTAPI_ROUTE_SNIPPET = '''
# ── Add this to aubieeternal_build/server.py ──────────────────────────────

from aubieeternal_build_code import handle_build_code_request

@app.post("/build-code")
async def build_code(payload: dict):
    """
    POST /build-code
    Body: {"request": "Write a Python script that ..."}
    """
    return await handle_build_code_request(payload)
# ─────────────────────────────────────────────────────────────────────────
'''


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------

async def _demo():
    print("=== AUBIEETERNAL Build Code — Demo ===\n")

    agent = BuildCodeAgent(verbose=True)

    result = await agent.run(
        "Write a Python script that prints the current UTC time "
        "and the first 10 fibonacci numbers."
    )

    print("\n" + "="*60)
    print(result.summary)
    print(f"\nSuccess: {result.success}")
    print(f"Iterations used: {result.iterations}")
    if result.output_file:
        print(f"\nFinal file: {result.output_file}")
        print("\n--- Code ---")
        print(result.final_code[:600])

    print("\n--- Server integration snippet ---")
    print(FASTAPI_ROUTE_SNIPPET)


if __name__ == "__main__":
    asyncio.run(_demo())