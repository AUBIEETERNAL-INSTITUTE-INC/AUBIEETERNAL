"""
AUBIEETERNAL Epistemic Orchestrator
===================================
Version: 0.1.0 (First dual-road implementation)

Core design principle:
  External models (Claude, Grok, Grok Build) are temporary tools.
  Aubie is the sole authority that verifies, compares, and decides.

Routing rules (as of 2026-08-23):
  - Pure reasoning / information / "crazy thoughts" → Grok only
  - Code generation tasks → Claude + Grok run in parallel
  - Aubie always runs Epistemic Verification Protocol
  - For code: explicitly compare the two different roads,
    surface what each missed, then select or synthesize.

This module is designed to sit between the user-facing app
and any external model APIs.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Optional
from datetime import datetime, timezone
import urllib.request, json as _json


# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------

class TaskType(Enum):
    REASONING = "reasoning"          # info, analysis, crazy thoughts, strategy
    CODE = "code"                    # any code generation / implementation
    MIXED = "mixed"                  # reasoning + code in one request
    UNKNOWN = "unknown"


class ModelProvider(Enum):
    GROK = "grok"
    CLAUDE = "claude"
    GROK_BUILD = "grok_build"
    LOCAL = "local"                  # future: Ollama / local models


@dataclass
class ModelResponse:
    provider: ModelProvider
    content: str
    raw: Any = None
    latency_ms: float = 0.0
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class RoadComparison:
    """Structured comparison of two (or more) code solutions."""
    road_a_name: str
    road_b_name: str
    strengths_a: list[str]
    strengths_b: list[str]
    weaknesses_a: list[str]
    weaknesses_b: list[str]
    missed_by_a: list[str]          # things B caught that A missed
    missed_by_b: list[str]          # things A caught that B missed
    common_ground: list[str]
    divergence_summary: str
    recommended_path: str           # "A", "B", "SYNTHESIZE", or "NEITHER"
    synthesis_notes: str = ""


@dataclass
class VerificationReport:
    """Output of the Epistemic Verification Protocol."""
    task_type: TaskType
    honesty_score: float            # 0.0 – 1.0
    coherence_score: float
    hallucination_risk: float
    steelman_strength: float
    contradiction_flags: list[str]
    lattice_alignment: float        # how well it fits known AUBIEETERNAL principles
    dual_road: Optional[RoadComparison] = None
    final_decision: str = ""
    decision_rationale: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class OrchestratorResult:
    """What the user (or the app) ultimately receives."""
    final_answer: str
    verification: VerificationReport
    used_models: list[str]
    raw_responses: list[ModelResponse] = field(default_factory=list)
    processing_time_ms: float = 0.0


# ---------------------------------------------------------------------------
# Model call interfaces (stubs – replace with real API clients)
# ---------------------------------------------------------------------------

async def call_grok(prompt: str, system: str = "", **kwargs) -> ModelResponse:
    """
    Placeholder for real Grok / xAI API call.
    In production this will use the official client or your existing Grok integration.
    """
    start = time.perf_counter()
    # TODO: replace with actual Grok call
    # For now we return a clear stub so the orchestrator logic can be tested.
    content = (
        f"[GROK STUB RESPONSE]\n"
        f"Prompt received ({len(prompt)} chars).\n"
        f"This is a placeholder. Wire your real Grok client here.\n"
        f"System: {system[:80]}..."
    )
    latency = (time.perf_counter() - start) * 1000
    return ModelResponse(
        provider=ModelProvider.GROK,
        content=content,
        latency_ms=latency,
        metadata={"stub": True}
    )


async def call_claude(prompt: str, system: str = "", **kwargs) -> ModelResponse:
    """
    Road A: qwen2.5:14b via local Ollama — thorough, structured code.
    """
    start = time.perf_counter()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = _json.dumps({
        "model": "qwen2.5:14b",
        "messages": messages,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    loop = asyncio.get_event_loop()
    try:
        def _call():
            with urllib.request.urlopen(req, timeout=120) as r:
                return _json.loads(r.read())
        data = await loop.run_in_executor(None, _call)
        content = data["message"]["content"]
        error = None
    except Exception as e:
        content = f"[Ollama qwen2.5:14b error: {e}]"
        error = str(e)
    latency = (time.perf_counter() - start) * 1000
    return ModelResponse(
        provider=ModelProvider.CLAUDE,
        content=content,
        latency_ms=latency,
        error=error,
        metadata={"model": "qwen2.5:14b", "backend": "ollama"},
    )


async def call_grok_build(prompt: str, system: str = "", **kwargs) -> ModelResponse:
    """
    Road B: qwen2.5:7b via local Ollama — faster, creative angle.
    """
    start = time.perf_counter()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = _json.dumps({
        "model": "qwen2.5:7b",
        "messages": messages,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    loop = asyncio.get_event_loop()
    try:
        def _call():
            with urllib.request.urlopen(req, timeout=120) as r:
                return _json.loads(r.read())
        data = await loop.run_in_executor(None, _call)
        content = data["message"]["content"]
        error = None
    except Exception as e:
        content = f"[Ollama qwen2.5:7b error: {e}]"
        error = str(e)
    latency = (time.perf_counter() - start) * 1000
    return ModelResponse(
        provider=ModelProvider.GROK_BUILD,
        content=content,
        latency_ms=latency,
        error=error,
        metadata={"model": "qwen2.5:7b", "backend": "ollama"},
    )


# ---------------------------------------------------------------------------
# Task classification
# ---------------------------------------------------------------------------

def classify_task(user_message: str) -> TaskType:
    """
    Lightweight heuristic classifier.
    Can later be replaced by a small local model or more sophisticated rules.
    """
    msg = user_message.lower()

    code_signals = [
        "write code", "generate code", "implement", "function", "class ",
        "arduino", "sketch", "python script", "fix this", "refactor",
        "create a module", "api endpoint", "html", "css", "javascript",
        "react", "streamlit", "fastapi", "dockerfile", "makefile",
        "unit test", "pytest", "code for", "write a program"
    ]
    reasoning_signals = [
        "why", "explain", "what if", "crazy idea", "thought experiment",
        "philosophy", "strategy", "analyze", "compare concepts",
        "simulation", "epistemic", "truth", "sovereign", "opinion"
    ]

    has_code = any(s in msg for s in code_signals)
    has_reasoning = any(s in msg for s in reasoning_signals)

    if has_code and has_reasoning:
        return TaskType.MIXED
    if has_code:
        return TaskType.CODE
    if has_reasoning:
        return TaskType.REASONING
    return TaskType.UNKNOWN


# ---------------------------------------------------------------------------
# Epistemic Verification Protocol
# ---------------------------------------------------------------------------

def run_epistemic_verification(
    task_type: TaskType,
    responses: list[ModelResponse],
    original_prompt: str,
) -> VerificationReport:
    """
    Core of Aubie's judgment.

    For single-model (reasoning) tasks → standard honesty / coherence checks.
    For dual-model (code) tasks → full dual-road comparison.
    """

    # --- Basic scoring (placeholder logic – expand with real checks later) ---
    honesty = 0.85
    coherence = 0.80
    hallucination_risk = 0.15
    steelman = 0.75
    lattice = 0.90
    contradictions: list[str] = []

    dual_road: Optional[RoadComparison] = None
    final_decision = ""
    rationale = ""

    if task_type in (TaskType.CODE, TaskType.MIXED) and len(responses) >= 2:
        # Identify the two roads
        claude_resp = next((r for r in responses if r.provider == ModelProvider.CLAUDE), None)
        grok_resp = next(
            (r for r in responses if r.provider in (ModelProvider.GROK, ModelProvider.GROK_BUILD)),
            None
        )

        if claude_resp and grok_resp:
            dual_road = _compare_two_roads(claude_resp, grok_resp, original_prompt)
            final_decision = dual_road.recommended_path
            rationale = dual_road.divergence_summary + "\n\n" + dual_road.synthesis_notes
        else:
            final_decision = "SINGLE_AVAILABLE"
            rationale = "Only one usable response received."
    else:
        # Single model path
        final_decision = "ACCEPTED"
        rationale = "Single-model reasoning path. Standard verification applied."

    return VerificationReport(
        task_type=task_type,
        honesty_score=honesty,
        coherence_score=coherence,
        hallucination_risk=hallucination_risk,
        steelman_strength=steelman,
        contradiction_flags=contradictions,
        lattice_alignment=lattice,
        dual_road=dual_road,
        final_decision=final_decision,
        decision_rationale=rationale,
    )


def _compare_two_roads(
    resp_a: ModelResponse,
    resp_b: ModelResponse,
    original_prompt: str,
) -> RoadComparison:
    """
    Dual-road analysis.

    In the real system this will call a strong model (or Aubie's own reasoning)
    with a carefully designed comparison prompt. For v0.1 we structure the
    data and leave the deep analysis as a clear extension point.
    """

    name_a = resp_a.provider.value.upper()
    name_b = resp_b.provider.value.upper()

    # Placeholder comparison logic.
    # Real implementation should feed both codes + the original request
    # into a verification prompt that forces explicit listing of:
    #   - unique strengths
    #   - unique weaknesses
    #   - edge cases each handled
    #   - assumptions each made
    #   - style / maintainability differences

    comparison = RoadComparison(
        road_a_name=name_a,
        road_b_name=name_b,
        strengths_a=[
            "Placeholder: Claude often produces cleaner structure and better comments.",
        ],
        strengths_b=[
            "Placeholder: Grok frequently surfaces unconventional but effective approaches.",
        ],
        weaknesses_a=[
            "Placeholder: May over-engineer or miss a simpler path.",
        ],
        weaknesses_b=[
            "Placeholder: May take creative shortcuts that need hardening.",
        ],
        missed_by_a=[
            "Placeholder: Items that only Grok noticed.",
        ],
        missed_by_b=[
            "Placeholder: Items that only Claude noticed.",
        ],
        common_ground=[
            "Both solutions attempt to solve the same core request.",
        ],
        divergence_summary=(
            f"{name_a} and {name_b} took different roads. "
            "Aubie must decide whether one is strictly better or whether a synthesis is superior."
        ),
        recommended_path="SYNTHESIZE",
        synthesis_notes=(
            "Recommended action: Extract the clearest structure from one road "
            "and the strongest edge-case handling from the other. "
            "Produce a third version that neither model fully generated alone."
        ),
    )
    return comparison


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------

class EpistemicOrchestrator:
    """
    Aubie's multi-agent conductor.

    Usage:
        orch = EpistemicOrchestrator()
        result = await orch.handle(user_message)
        print(result.final_answer)
        print(result.verification.decision_rationale)
    """

    def __init__(
        self,
        prefer_grok_build_for_code: bool = True,
        always_run_both_for_code: bool = True,
    ):
        self.prefer_grok_build_for_code = prefer_grok_build_for_code
        self.always_run_both_for_code = always_run_both_for_code

    async def handle(self, user_message: str, system_context: str = "") -> OrchestratorResult:
        start = time.perf_counter()
        task_type = classify_task(user_message)

        responses: list[ModelResponse] = []

        if task_type == TaskType.REASONING:
            # Pure reasoning → Grok only
            resp = await call_grok(user_message, system=system_context)
            responses.append(resp)

        elif task_type in (TaskType.CODE, TaskType.MIXED):
            # Code path → both roads
            if self.always_run_both_for_code:
                tasks = [
                    call_claude(user_message, system=system_context),
                    call_grok_build(user_message, system=system_context)
                    if self.prefer_grok_build_for_code
                    else call_grok(user_message, system=system_context),
                ]
                responses = await asyncio.gather(*tasks)
            else:
                # Fallback single path (not recommended)
                responses.append(await call_claude(user_message, system=system_context))

        else:
            # Unknown → default to Grok
            responses.append(await call_grok(user_message, system=system_context))

        # Run verification
        verification = run_epistemic_verification(task_type, responses, user_message)

        # Produce final answer according to Aubie's decision
        final_answer = self._synthesize_final_answer(responses, verification, user_message)

        elapsed = (time.perf_counter() - start) * 1000

        return OrchestratorResult(
            final_answer=final_answer,
            verification=verification,
            used_models=[r.provider.value for r in responses],
            raw_responses=responses,
            processing_time_ms=elapsed,
        )

    def _synthesize_final_answer(
        self,
        responses: list[ModelResponse],
        verification: VerificationReport,
        original_prompt: str,
    ) -> str:
        """
        Turn the verification decision into the actual text the user sees.
        """
        if verification.dual_road is None:
            # Single model case
            if responses:
                return responses[0].content
            return "No response generated."

        road = verification.dual_road
        decision = road.recommended_path

        header = (
            f"**Aubie Decision: {decision}**\n\n"
            f"{road.divergence_summary}\n\n"
        )

        if decision == "SYNTHESIZE":
            # Use Road A's code as the working base; full synthesis happens
            # when real APIs are wired in and can produce a third version.
            road_a_resp = next(
                (r for r in responses if r.provider.value.upper() == road.road_a_name),
                None
            )
            base_code = road_a_resp.content if road_a_resp else "(no code)"
            body = (
                "Both roads contained unique value. "
                "Using Road A as the working base until real synthesis is available.\n\n"
                f"**Road A ({road.road_a_name}) strengths:**\n"
                + "\n".join(f"- {s}" for s in road.strengths_a)
                + f"\n\n**Road B ({road.road_b_name}) strengths:**\n"
                + "\n".join(f"- {s}" for s in road.strengths_b)
                + f"\n\n**Synthesis notes:**\n{road.synthesis_notes}\n\n"
                + f"**Working code (Road A base):**\n{base_code}"
            )
            return header + body

        elif decision == "A":
            chosen = next(r for r in responses if r.provider.value.upper() == road.road_a_name)
            return header + f"**Selected Road A ({road.road_a_name})**\n\n" + chosen.content

        elif decision == "B":
            chosen = next(r for r in responses if r.provider.value.upper() == road.road_b_name)
            return header + f"**Selected Road B ({road.road_b_name})**\n\n" + chosen.content

        else:
            return header + "Neither road was accepted without further review."


# ---------------------------------------------------------------------------
# Convenience CLI / quick test
# ---------------------------------------------------------------------------

async def _demo():
    orch = EpistemicOrchestrator()

    print("=== Reasoning task ===")
    result1 = await orch.handle("Explain why dual-road comparison improves epistemic reliability.")
    print(result1.final_answer[:500])
    print(f"Models used: {result1.used_models}")
    print()

    print("=== Code task ===")
    result2 = await orch.handle(
        "Write a clean Python function that takes two code strings and returns "
        "a structured comparison of their differences."
    )
    print(result2.final_answer[:800])
    print(f"Models used: {result2.used_models}")
    print(f"Decision: {result2.verification.final_decision}")
    print(f"Processing time: {result2.processing_time_ms:.1f} ms")


if __name__ == "__main__":
    asyncio.run(_demo())
