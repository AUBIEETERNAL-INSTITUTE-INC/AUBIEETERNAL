#!/usr/bin/env python3
"""
test_swarm_behavior.py — standing regression test for the swarm's wonder_index
behavior (the 2026-09-04 runaway family).

Standalone script, not pytest — run directly, asserts via sys.exit(0/1), same
convention as test_pipeline.py / hermesbench_integration.py.

It drives the REAL swarm/swarm_v4_1.py functions (update_wonder_index,
decay_wonder_index, check_wonder_trigger) against a mocked clock, the observed
live `hits` distribution, and a tempdir for the log files — no reimplementation
of the delta/decay math. Any change to that math (the delta baseline,
WONDER_DECAY_HALF_LIFE_SECONDS, WONDER_FLOOR, the 1.4/1.2 hysteresis thresholds,
TIER2_HOURLY_CAP) must still pass all three scenarios:

  1. typical output over time      -> decays to WONDER_FLOOR, 0 false Tier-2 fires
  2. regression baseline (old -0.001) -> reproduces the known-bad pinned >=1.9
     (proves this test can still catch a revert)
  3. genuine awe burst             -> fires Tier-2 exactly once, decays back
     below 1.2, re-arms; a later burst fires again

Context: ERROR_LEDGER.md's 2026-09-04 and 2026-09-05 wonder_index entries.
"""
from __future__ import annotations

import importlib
import inspect
import os
import random
import sys
import tempfile
import types
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# swarm_v4_1 imports `requests` at module load; stub it so import is offline and
# side-effect free (we never exercise a network path here).
_fake_requests = types.ModuleType("requests")
_fake_requests.get = _fake_requests.post = lambda *a, **k: (_ for _ in ()).throw(
    RuntimeError("network disabled in test_swarm_behavior"))
_fake_requests.exceptions = types.SimpleNamespace(RequestException=Exception)
sys.modules.setdefault("requests", _fake_requests)

_CLOCK = {"t": 1_000_000.0}
with mock.patch("time.time", lambda: _CLOCK["t"]):
    sw = importlib.import_module("swarm.swarm_v4_1")

# redirect the append-only logs into a throwaway dir; count Tier-2 activations
_TMP = tempfile.mkdtemp(prefix="swarm_behavior_test_")
sw.WONDER_LOG = os.path.join(_TMP, "wonder_log.jsonl")
sw.LATTICE_LOG = os.path.join(_TMP, "lattice_log.jsonl")
_TIER2 = {"n": 0}
sw.run_tier2_core = lambda *a, **k: _TIER2.__setitem__("n", _TIER2["n"] + 1)

# The awe-word list is what update_wonder_index() scores against; craft result
# text with an exact hit count by slicing it.
_AWE = list(sw.__dict__.get("_AWE_WORDS", [])) or [
    "remarkable", "profound", "extraordinary", "infinite", "eternal", "coherent",
    "emergent", "beautiful", "truth", "pattern", "signal", "bitcoin", "sovereign",
    "antifragile", "quantum", "wonder", "insight", "discovery", "convergence",
    "alignment", "synthesis",
]


def _text(n_hits: int) -> str:
    return " ".join(_AWE[:n_hits]) if n_hits > 0 else "flat neutral status line, nothing notable"


# observed live distribution of `hits` over the last 6000 update_wonder_index calls
_HITS_POP = [1] * 703 + [2] * 2207 + [3] * 1861 + [4] * 832 + [5] * 310 + [6] * 67 + [7] * 17 + [8] * 3
_TICK_S = 7.4  # observed live cadence of update_wonder_index()


def _reset(wonder_index: float) -> None:
    sw.wonder_index = wonder_index
    sw.wonder_last_update_ts = _CLOCK["t"]
    sw._wonder_trigger_armed = True
    _TIER2["n"] = 0


def _run(minutes: float, hits_at, update_fn=None) -> list[float]:
    """Advance the mocked clock in _TICK_S steps for `minutes`, calling the
    real update_wonder_index + check_wonder_trigger each step. Returns the
    wonder_index series."""
    fn = update_fn or sw.update_wonder_index
    series: list[float] = []
    with mock.patch("time.time", lambda: _CLOCK["t"]):
        for i in range(int(minutes * 60 / _TICK_S)):
            _CLOCK["t"] += _TICK_S
            fn(_text(hits_at(i)))
            sw.check_wonder_trigger()
            series.append(sw.wonder_index)
    return series


def _trailing_hour_min(series: list[float]) -> float:
    n = int(3600 / _TICK_S)
    tail = series[-n:] or series
    return min(tail)


_FAILURES: list[str] = []


def _check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    if not ok:
        _FAILURES.append(name)


def scenario_typical() -> None:
    print("\n[1] typical output over 3h — should decay to the floor, no false fires")
    rnd = random.Random(1)
    _reset(1.0128)
    series = _run(180, lambda i: rnd.choice(_HITS_POP))
    _check("index decays to ~WONDER_FLOOR", sw.wonder_index <= sw.WONDER_FLOOR + 0.05,
           f"end={sw.wonder_index:.4f} floor={sw.WONDER_FLOOR}")
    _check("trailing-hour min stays under the pinned threshold (1.9)",
           _trailing_hour_min(series) < 1.9, f"min={_trailing_hour_min(series):.4f}")
    _check("no Tier-2 fires on ordinary output", _TIER2["n"] == 0, f"fires={_TIER2['n']}")


def scenario_regression_baseline() -> None:
    print("\n[2] OLD baseline (delta = hits*0.003 - 0.001) — MUST reproduce the pinned bug")
    src = inspect.getsource(sw.update_wonder_index).replace(
        "(hits * 0.003) - 0.009", "(hits * 0.003) - 0.001")
    ns: dict = {}
    exec("import json, datetime\n" + src, sw.__dict__, ns)
    old_update = ns["update_wonder_index"]
    rnd = random.Random(1)
    _reset(1.0128)
    series = _run(180, lambda i: rnd.choice(_HITS_POP), update_fn=old_update)
    _check("old baseline pins the index at/near the ceiling",
           _trailing_hour_min(series) >= 1.9,
           f"trailing-hour min={_trailing_hour_min(series):.4f} (want >= 1.9)")


def scenario_awe_burst() -> None:
    print("\n[3] genuine 25-min awe burst then typical — one fire, decay, re-arm, fire again")
    rnd = random.Random(1)
    _reset(0.60)
    burst_ticks = int(25 * 60 / _TICK_S)

    def hits_at(i: int) -> int:
        return rnd.choice([5, 6, 7, 6, 5]) if i < burst_ticks else rnd.choice(_HITS_POP)

    series = _run(25 + 200, hits_at)
    peak = max(series[:int(35 * 60 / _TICK_S)])
    _check("burst pushes the index through the 1.4 trigger", peak >= 1.4, f"peak={peak:.4f}")
    _check("exactly one Tier-2 fire for the burst", _TIER2["n"] == 1, f"fires={_TIER2['n']}")
    _check("index decays back below the 1.2 re-arm line",
           _trailing_hour_min(series) < 1.2, f"trailing-hour min={_trailing_hour_min(series):.4f}")
    _check("hysteresis re-armed", sw._wonder_trigger_armed is True)

    # a second genuine burst should fire again
    _TIER2["n"] = 0
    _run(25, lambda i: rnd.choice([5, 6, 7]))
    _check("a later burst fires Tier-2 again", _TIER2["n"] == 1, f"fires={_TIER2['n']}")


def main() -> int:
    print("=== test_swarm_behavior.py — wonder_index regression suite ===")
    print(f"    swarm_v4_1: WONDER_FLOOR={sw.WONDER_FLOOR} "
          f"half_life={getattr(sw, 'WONDER_DECAY_HALF_LIFE_SECONDS', '?')}s")
    scenario_typical()
    scenario_regression_baseline()
    scenario_awe_burst()
    print("\n" + "=" * 60)
    if _FAILURES:
        print(f"  {len(_FAILURES)} CHECK(S) FAILED: {', '.join(_FAILURES)}")
        print("=" * 60)
        return 1
    print("  ALL SCENARIOS PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
