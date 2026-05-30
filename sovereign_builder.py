"""
sovereign_builder.py — AUBIEETERNAL Sovereign Builder
======================================================
The builder track module. Halo glasses as always-on AR mentor.

Kids who grow up building their sovereign AI stack don't just use technology —
they understand it, modify it, and eventually design the next generation of it.

This module tracks:
  1. Builder level (Junior → Master → PhD → Humanity Builder)
  2. Hardware progression (what the family has, what they've upgraded)
  3. Contribution log (what they've built or improved for the lattice)
  4. AR/Halo integration hooks (real-time overlay guidance)
  5. Benchmark database (family's hardware performance, shared with lattice)

The humanitarian case:
  Every family that can build and maintain sovereign AI infrastructure
  is one family that cannot be cut off from epistemic tools.
  At 10,000 families, this becomes resilient civilizational infrastructure.
  At 100,000, it is the most important epistemic network ever built.

Usage:
    from sovereign_builder import SovereignBuilder, BuilderContribution
    builder = SovereignBuilder(family_id="alpha")
    builder.log_upgrade("RAM", from_spec="16GB DDR4", to_spec="32GB DDR4")
    builder.log_benchmark("qwen2.5:14b", tokens_per_sec=12.4, hardware="Ryzen 7 + 32GB")
    contrib = BuilderContribution()
    contrib.log("curriculum", "Added systems thinking lesson for age 8", url="...")
"""

import os, json, hashlib, datetime
from pathlib import Path
import socket as _socket

def _data_dir() -> Path:
    try:
        _socket.gethostbyname("ollama.startos")
        return Path("/mnt/main")
    except Exception:
        p = Path(os.path.expanduser("~/.aubieeternal/main"))
        p.mkdir(parents=True, exist_ok=True)
        return p

DATA_DIR      = _data_dir()
BUILDER_FILE  = DATA_DIR / "sovereign_builder.json"
CONTRIB_LOG   = DATA_DIR / "builder_contributions.jsonl"
BENCHMARK_LOG = DATA_DIR / "hardware_benchmarks.jsonl"
UPGRADE_LOG   = DATA_DIR / "hardware_upgrades.jsonl"

# ── Builder Level Definitions ─────────────────────────────────────────────────
BUILDER_LEVELS = {
    "junior": {
        "title":      "Junior Builder",
        "emoji":      "🔧",
        "age_range":  "5-10",
        "description": "Knows the parts, has done first upgrade",
        "required_lessons": ["builder-1", "builder-2"],
        "xp_threshold": 80,
        "rune_grant": 50,
    },
    "master": {
        "title":      "Master Builder",
        "emoji":      "⚙️",
        "age_range":  "11-15",
        "description": "Understands transformers, has optimized the stack",
        "required_lessons": ["builder-3", "builder-4", "builder-5"],
        "xp_threshold": 230,
        "rune_grant": 200,
    },
    "phd": {
        "title":      "PhD Builder",
        "emoji":      "🧬",
        "age_range":  "16+",
        "description": "Understands neural architecture, cryptography, distributed systems",
        "required_lessons": ["builder-6", "builder-7", "tech-sovereignty-4"],
        "xp_threshold": 430,
        "rune_grant": 500,
    },
    "humanity": {
        "title":      "Humanity Builder",
        "emoji":      "🌍",
        "age_range":  "Any age",
        "description": "Has contributed back to the lattice",
        "required_lessons": ["builder-8"],
        "xp_threshold": 530,
        "rune_grant": 1000,
    },
}

# ── AR/Halo Integration Hooks ─────────────────────────────────────────────────
AR_OVERLAYS = {
    "ram_upgrade": {
        "title":    "RAM Upgrade Guide",
        "steps": [
            "Ground yourself — touch the metal chassis",
            "Locate RAM slots on motherboard (usually near CPU)",
            "Press outward on release clips at both ends",
            "Remove old stick (pulls straight up)",
            "Align notch on new stick with gap in slot",
            "Press firmly until BOTH clips snap shut",
            "Boot and verify in BIOS or system settings",
        ],
        "highlight": ["RAM slots", "release clips", "notch alignment"],
        "verify_command": "sudo dmidecode -t memory | grep Size",
    },
    "ssd_install": {
        "title":    "SSD Installation Guide",
        "steps": [
            "Identify M.2 slot or 2.5\" bay",
            "For M.2: angle in at 30°, press down, secure with screw",
            "For 2.5\": connect SATA power and data cables",
            "Boot to BIOS to verify detection",
            "Install OS or format as data drive",
        ],
        "highlight": ["M.2 slot", "SATA ports", "mounting screw"],
        "verify_command": "lsblk",
    },
    "ollama_setup": {
        "title":    "Ollama Setup Guide",
        "steps": [
            "Install: curl -fsSL https://ollama.ai/install.sh | sh",
            "Start service: ollama serve",
            "Pull model: ollama pull qwen2.5:14b",
            "Test: ollama run qwen2.5:14b 'What is coherence?'",
            "Set AUBIEETERNAL model: export AUBIE_MODEL=qwen2.5:14b",
        ],
        "highlight": ["terminal", "download progress"],
        "verify_command": "ollama list",
    },
    "benchmark": {
        "title":    "Performance Benchmark",
        "steps": [
            "Start timing: time ollama run qwen2.5:14b 'Count to 100' > /dev/null",
            "Count tokens in output",
            "Calculate tokens/second",
            "Compare with benchmark database",
            "Identify bottleneck: CPU, RAM bandwidth, or GPU",
        ],
        "highlight": ["terminal", "htop CPU graph", "RAM usage bar"],
        "verify_command": "ollama ps",
    },
}


class SovereignBuilder:
    """Tracks a family's sovereign builder journey."""

    def __init__(self, family_id: str = "default"):
        self.family_id = family_id
        self._load_state()

    def _load_state(self):
        if BUILDER_FILE.exists():
            try:
                all_states = json.loads(BUILDER_FILE.read_text())
                self._state = all_states.get(self.family_id, self._default_state())
            except Exception:
                self._state = self._default_state()
        else:
            self._state = self._default_state()

    def _default_state(self) -> dict:
        return {
            "family_id":     self.family_id,
            "level":         "junior",
            "xp":            0,
            "hardware":      {},
            "upgrades":      [],
            "benchmarks":    [],
            "contributions": 0,
            "ar_sessions":   0,
            "created":       datetime.date.today().isoformat(),
        }

    def _save_state(self):
        all_states = {}
        if BUILDER_FILE.exists():
            try:
                all_states = json.loads(BUILDER_FILE.read_text())
            except Exception:
                pass
        all_states[self.family_id] = self._state
        BUILDER_FILE.write_text(json.dumps(all_states, indent=2))

    # ── Hardware tracking ──────────────────────────────────────────────────────

    def log_upgrade(self, component: str, from_spec: str = "",
                    to_spec: str = "", notes: str = "") -> dict:
        """Log a hardware upgrade."""
        upgrade = {
            "date":      datetime.date.today().isoformat(),
            "component": component,
            "from_spec": from_spec,
            "to_spec":   to_spec,
            "notes":     notes,
            "xp_earned": 25,
        }
        self._state["upgrades"].append(upgrade)
        self._state["xp"] += 25
        self._state["hardware"][component] = to_spec
        self._save_state()

        with open(UPGRADE_LOG, "a") as f:
            f.write(json.dumps({**upgrade, "family_id": self.family_id}) + "\n")

        print(f"[builder] Upgrade logged: {component} {from_spec} → {to_spec} | +25 XP")
        return upgrade

    def log_benchmark(self, model: str, tokens_per_sec: float,
                       hardware: str = "", context_length: int = 2048,
                       quantization: str = "Q4") -> dict:
        """Log a hardware benchmark."""
        bench = {
            "date":           datetime.date.today().isoformat(),
            "family_id":      self.family_id,
            "model":          model,
            "tokens_per_sec": tokens_per_sec,
            "hardware":       hardware or self._state["hardware"].get("CPU", "unknown"),
            "context_length": context_length,
            "quantization":   quantization,
        }
        self._state["benchmarks"].append(bench)
        self._state["xp"] += 15
        self._save_state()

        with open(BENCHMARK_LOG, "a") as f:
            f.write(json.dumps(bench) + "\n")

        print(f"[builder] Benchmark: {model} @ {tokens_per_sec:.1f} tok/s | +15 XP")
        return bench

    def log_ar_session(self, overlay_key: str, completed: bool = True):
        """Log a Halo AR overlay session."""
        self._state["ar_sessions"] += 1
        if completed:
            self._state["xp"] += 10
        self._save_state()
        print(f"[builder] AR session: {overlay_key} | {'completed' if completed else 'started'}")

    # ── Level assessment ───────────────────────────────────────────────────────

    def get_level(self) -> dict:
        """Get current builder level and progress."""
        xp        = self._state.get("xp", 0)
        upgrades  = len(self._state.get("upgrades", []))
        contribs  = self._state.get("contributions", 0)

        current_level = "junior"
        for level_key in ["humanity", "phd", "master", "junior"]:
            threshold = BUILDER_LEVELS[level_key]["xp_threshold"]
            if xp >= threshold:
                current_level = level_key
                break

        level_info = BUILDER_LEVELS[current_level]
        next_level = {"junior":"master","master":"phd","phd":"humanity","humanity":None}[current_level]
        next_threshold = BUILDER_LEVELS[next_level]["xp_threshold"] if next_level else None

        return {
            "level":           current_level,
            "title":           level_info["title"],
            "emoji":           level_info["emoji"],
            "xp":              xp,
            "next_level":      next_level,
            "xp_to_next":      (next_threshold - xp) if next_threshold else 0,
            "upgrades_done":   upgrades,
            "contributions":   contribs,
            "ar_sessions":     self._state.get("ar_sessions", 0),
            "hardware":        self._state.get("hardware", {}),
        }

    # ── AR overlay guidance ────────────────────────────────────────────────────

    def get_ar_guide(self, task: str) -> dict:
        """Get AR overlay guidance for a hardware task."""
        key = task.lower().replace(" ", "_").replace("-", "_")
        return AR_OVERLAYS.get(key, {
            "title": f"Guide: {task}",
            "steps": [
                "Look up the specific guide for your hardware model",
                "Check compatibility before purchasing",
                "Ground yourself before touching components",
                "Work slowly and methodically",
                "Verify each step before proceeding",
            ],
            "highlight": [],
            "verify_command": "",
        })

    # ── Community benchmarks ───────────────────────────────────────────────────

    def get_community_benchmarks(self, model: str = "") -> list:
        """Get benchmarks from all families for comparison."""
        if not BENCHMARK_LOG.exists():
            return []
        benches = []
        for line in BENCHMARK_LOG.read_text().strip().split("\n"):
            try:
                b = json.loads(line)
                if not model or model in b.get("model",""):
                    benches.append(b)
            except Exception:
                pass
        return sorted(benches, key=lambda x: x.get("tokens_per_sec", 0), reverse=True)[:20]

    def get_stats(self) -> dict:
        level = self.get_level()
        return {
            **level,
            "total_benchmarks": len(self._state.get("benchmarks", [])),
        }


class BuilderContribution:
    """Track contributions back to the lattice."""

    CONTRIBUTION_TYPES = {
        "curriculum":    ("📚", 50,  "Lesson or curriculum improvement"),
        "bugfix":        ("🐛", 40,  "Bug fix or code improvement"),
        "benchmark":     ("📊", 20,  "Hardware benchmark data"),
        "documentation": ("📝", 30,  "Documentation or guide"),
        "new_module":    ("🔧", 100, "New feature or module"),
        "preference_data": ("🎓", 60, "High-quality AI preference data"),
    }

    def log(self, contrib_type: str, description: str,
            url: str = "", family_id: str = "default") -> dict:
        emoji, xp, type_desc = self.CONTRIBUTION_TYPES.get(
            contrib_type, ("🔧", 30, "Contribution"))

        contrib = {
            "contrib_id":  hashlib.sha256(
                f"{description}{datetime.datetime.now().isoformat()}".encode()
            ).hexdigest()[:12],
            "timestamp":   datetime.datetime.now().isoformat(),
            "family_id":   family_id,
            "type":        contrib_type,
            "description": description[:400],
            "url":         url,
            "xp_earned":   xp,
        }

        with open(CONTRIB_LOG, "a") as f:
            f.write(json.dumps(contrib) + "\n")

        # Also seal in rune memory
        try:
            from rune_memory import record_extension_capture
            record_extension_capture(
                f"BUILDER CONTRIBUTION [{contrib_type}]: {description[:200]}",
                coherence=0.85
            )
        except Exception:
            pass

        print(f"[builder] {emoji} Contribution: {contrib_type} | +{xp} XP | {description[:50]}")
        return contrib

    def get_all(self, family_id: str = "") -> list:
        if not CONTRIB_LOG.exists():
            return []
        entries = []
        for line in CONTRIB_LOG.read_text().strip().split("\n"):
            try:
                e = json.loads(line)
                if not family_id or e.get("family_id") == family_id:
                    entries.append(e)
            except Exception:
                pass
        return list(reversed(entries))

    def get_community_stats(self) -> dict:
        all_contribs = self.get_all()
        if not all_contribs:
            return {"total": 0}
        return {
            "total":         len(all_contribs),
            "families":      len(set(c["family_id"] for c in all_contribs)),
            "by_type":       {t: len([c for c in all_contribs if c["type"] == t])
                              for t in self.CONTRIBUTION_TYPES},
            "latest":        all_contribs[0]["description"][:80] if all_contribs else None,
        }


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🔧 Sovereign Builder Test")
    builder = SovereignBuilder("test_family")
    builder.log_upgrade("RAM", "16GB DDR4", "32GB DDR4", "Upgraded to run qwen2.5:14b")
    builder.log_benchmark("qwen2.5:14b", 12.4, "Ryzen 7 5700X + 32GB DDR4")
    builder.log_ar_session("ram_upgrade", completed=True)

    level = builder.get_level()
    print(f"Level: {level['emoji']} {level['title']} | XP: {level['xp']} | "
          f"Next: {level['xp_to_next']} XP to go")

    contrib = BuilderContribution()
    c = contrib.log("benchmark", "qwen2.5:14b benchmark on Ryzen 7: 12.4 tok/s Q4",
                    family_id="test_family")
    print(f"Contribution: {c['contrib_id']}")

    guide = builder.get_ar_guide("ram_upgrade")
    print(f"AR Guide: {guide['title']} — {len(guide['steps'])} steps")
    print("✅ Sovereign Builder operational — War Eagle Eternal 🦅")
