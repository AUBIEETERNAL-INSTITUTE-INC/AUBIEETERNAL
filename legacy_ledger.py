"""
legacy_ledger.py — AUBIEETERNAL Legacy Ledger
==============================================
The Dynasty Engine. The single most powerful lever toward legendary status.

When a 12-year-old in 2035 says "We're an AUBIEETERNAL family — my great-grandparents
started the lattice," that is the moment legend is born.

This module builds the infrastructure for that moment.

THREE LAYERS:
  1. FAMILY DYNASTY — track coherence, wisdom, and legacy across 3 generations
  2. LEGACY LEDGER — on-chain family wisdom archive (append-only, Bitcoin-anchored)
  3. INHERITANCE MECHANICS — Rune fragments, wisdom scores, and rites of passage
     that pass automatically from parent to child

WHY THIS CREATES LEGEND:
  Ancient educational systems survived because they produced intergenerational trust
  and capital. The Talmudic tradition, the great monastic schools, the Academy —
  all of them created mechanisms for wisdom to compound across bloodlines.
  AUBIEETERNAL adds something none of them had: cryptographic permanence.

  A family's wisdom archive, sealed with Bitcoin Runes, survives any institutional
  collapse, any government, any algorithm. It is the family's permanent contribution
  to civilization — visible to their descendants, verifiable by anyone.

MY ADDITION (Claude):
  The "Rite of Passage Protocol" — formal on-chain ceremonies for milestone achievements.
  Not just XP and badges. Real rituals that families design together, seal permanently,
  and reference as living history. The moment a child completes the full Gatekeeping track
  and earns "Sovereign Epistemic Node" status should feel different from earning a badge
  in a video game. It should feel like becoming something.

Usage:
    from legacy_ledger import LegacyLedger, RiteOfPassage
    ledger = LegacyLedger(family_id="alpha")
    ledger.record_wisdom("What my grandfather taught me about courage", author="grandparent")
    ledger.record_milestone("first_seal", member="Gaby", age=12)
    rite = RiteOfPassage()
    rite.conduct("Gaby", "sovereign_node", family_id="alpha")
"""

import os, json, hashlib, datetime
from pathlib import Path
import socket as _socket

def _data_dir() -> Path:
    try:
        _socket.gethostbyname("localhost")
        return Path("/mnt/main")
    except Exception:
        p = Path(os.path.expanduser("~/.aubieeternal/main"))
        p.mkdir(parents=True, exist_ok=True)
        return p

DATA_DIR      = _data_dir()
LEGACY_DIR    = DATA_DIR / "repo" / "legacy"
LEGACY_DIR.mkdir(parents=True, exist_ok=True)
WISDOM_LOG    = DATA_DIR / "family_wisdom.jsonl"
MILESTONE_LOG = DATA_DIR / "family_milestones.jsonl"
DYNASTY_FILE  = DATA_DIR / "dynasty_state.json"

# ── Rite of Passage definitions ───────────────────────────────────────────────
RITES_OF_PASSAGE = {
    "first_lesson": {
        "title":    "First Light",
        "emoji":    "🌅",
        "meaning":  "The journey begins. You chose to learn rather than accept.",
        "rune_grant": 10,
        "ceremony": "Family gathers. The learner reads aloud the lesson's core insight. Parent witnesses.",
    },
    "first_seal": {
        "title":    "The First Seal",
        "emoji":    "🛡️",
        "meaning":  "You sealed your first permanent memory on Bitcoin. Truth cannot be taken from you.",
        "rune_grant": 50,
        "ceremony": "Read the sealed insight aloud. Family discusses: why does this truth matter?",
    },
    "gatekeeper_free": {
        "title":    "Sovereign Epistemic Node",
        "emoji":    "🔓",
        "meaning":  "You completed the Gatekeeping track. You can now see the chain between you and any source.",
        "rune_grant": 100,
        "ceremony": "Name one belief you held that arrived through an unexamined gatekeeper. Release it. Log the replacement.",
    },
    "admin_elevated": {
        "title":    "Admin Elevated",
        "emoji":    "⚡",
        "meaning":  "You passed the 5 Admin Tests. You operate with redundant verification and permanent records.",
        "rune_grant": 150,
        "ceremony": "Run the full Admin Stress Test with your family watching. Seal the result.",
    },
    "child_rune_genesis": {
        "title":    "Child Rune Genesis",
        "emoji":    "₿",
        "meaning":  "256 confirmations. Your sovereign identity is permanently on Bitcoin. No institution issued it. None can revoke it.",
        "rune_grant": 500,
        "ceremony": "Family reads the SOVEREIGN_FAMILY_LAW_CHARTER aloud. The new sovereign node responds: 'I understand and I hold this.'",
    },
    "truth_lattice_architect": {
        "title":    "Truth Lattice Architect",
        "emoji":    "🏗️",
        "meaning":  "You understand the architecture of decentralized truth. You can teach it to others.",
        "rune_grant": 200,
        "ceremony": "Teach the Truth Lattice Architecture lesson to someone who hasn't heard it. Seal their understanding as a new node.",
    },
    "dynasty_founder": {
        "title":    "Dynasty Founder",
        "emoji":    "👑",
        "meaning":  "Three generations of your family have participated in the lattice. The dynasty is real.",
        "rune_grant": 1000,
        "ceremony": "Three generations gather. Each shares one insight from their generation's work. Seal all three as a merged node.",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# LEGACY LEDGER — family wisdom archive
# ══════════════════════════════════════════════════════════════════════════════

class LegacyLedger:
    """
    On-chain family wisdom archive. Append-only, Bitcoin-anchored.
    The family's permanent contribution to civilization.
    """

    def __init__(self, family_id: str = "default"):
        self.family_id  = family_id
        self.family_dir = LEGACY_DIR / family_id
        self.family_dir.mkdir(parents=True, exist_ok=True)

    # ── Record wisdom ─────────────────────────────────────────────────────────

    def record_wisdom(self, content: str, author: str = "family",
                      generation: int = 1, tags: list = None,
                      seal: bool = False) -> dict:
        """
        Record a wisdom entry in the family's legacy ledger.
        generation: 1 = current parents, 2 = grandparents, 3 = great-grandparents
        """
        entry_id = hashlib.sha256(
            f"{content}{datetime.datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        entry = {
            "entry_id":   entry_id,
            "timestamp":  datetime.datetime.now().isoformat(),
            "date":       datetime.date.today().isoformat(),
            "family_id":  self.family_id,
            "content":    content[:1000],
            "author":     author,
            "generation": generation,
            "tags":       tags or [],
            "sealed":     False,
            "rune_anchor": None,
        }

        with open(WISDOM_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")

        # Auto-seal if requested
        if seal:
            entry = self._seal_entry(entry)

        # Write to family's legacy file (human-readable)
        self._append_to_family_ledger(entry)
        print(f"[legacy] Wisdom recorded: {entry_id[:8]} | {author} | gen={generation}")
        return entry

    def _seal_entry(self, entry: dict) -> dict:
        """Seal a wisdom entry with the Shield Rune."""
        try:
            from rune_memory import ShieldRune
            seal = ShieldRune().seal(
                entry["entry_id"],
                note=f"Family wisdom — {entry['author']} | Generation {entry['generation']}",
                broadcaster=self.family_id
            )
            entry["sealed"]      = True
            entry["rune_anchor"] = seal.get("bitcoin_txid", seal.get("seal_hash",""))[:32]
        except Exception as e:
            print(f"[legacy] Seal failed: {e}")
        return entry

    def _append_to_family_ledger(self, entry: dict):
        ledger_path = self.family_dir / "wisdom_archive.md"
        with open(ledger_path, "a") as f:
            f.write(f"\n---\n")
            f.write(f"**{entry['date']}** | {entry['author']} | Generation {entry['generation']}\n\n")
            f.write(f"{entry['content']}\n\n")
            if entry.get("sealed"):
                f.write(f"*🛡️ Bitcoin-anchored: {entry.get('rune_anchor','?')[:20]}...*\n")

    # ── Record milestone ──────────────────────────────────────────────────────

    def record_milestone(self, milestone_key: str, member: str,
                          age: int = 0, notes: str = "") -> dict:
        """Record a family milestone in the permanent log."""
        milestone_id = hashlib.sha256(
            f"{milestone_key}{member}{datetime.datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        rite = RITES_OF_PASSAGE.get(milestone_key, {})
        milestone = {
            "milestone_id": milestone_id,
            "timestamp":    datetime.datetime.now().isoformat(),
            "date":         datetime.date.today().isoformat(),
            "family_id":    self.family_id,
            "key":          milestone_key,
            "member":       member,
            "age":          age,
            "notes":        notes,
            "title":        rite.get("title", milestone_key),
            "emoji":        rite.get("emoji", "🦅"),
            "rune_grant":   rite.get("rune_grant", 0),
            "ceremony":     rite.get("ceremony", ""),
        }

        with open(MILESTONE_LOG, "a") as f:
            f.write(json.dumps(milestone) + "\n")

        print(f"[legacy] Milestone: {rite.get('emoji','🦅')} {rite.get('title','?')} — {member}")
        return milestone

    # ── Get dynasty state ─────────────────────────────────────────────────────

    def get_dynasty_state(self) -> dict:
        """Calculate current dynasty state across all generations."""
        wisdom  = self._load_wisdom()
        milests = self._load_milestones()

        generations = {}
        for w in wisdom:
            g = w.get("generation", 1)
            generations.setdefault(g, {"wisdom_count": 0, "sealed": 0, "members": set()})
            generations[g]["wisdom_count"] += 1
            if w.get("sealed"):
                generations[g]["sealed"] += 1
            if w.get("author"):
                generations[g]["members"].add(w["author"])

        n_gen = len(generations)
        dynasty_score = min(100, (
            n_gen * 25 +                                   # generations (max 75)
            min(25, len(wisdom) * 0.5) +                   # wisdom entries
            min(25, sum(1 for w in wisdom if w.get("sealed")) * 2)  # sealed entries
        ))

        return {
            "family_id":       self.family_id,
            "total_wisdom":    len(wisdom),
            "total_milestones": len(milests),
            "generations_active": n_gen,
            "generation_data": {k: {**v, "members": list(v["members"])}
                                for k, v in generations.items()},
            "dynasty_score":   round(dynasty_score, 1),
            "dynasty_level":   "Founder" if n_gen >= 3 else "Builder" if n_gen >= 2 else "Seeker",
            "is_dynasty":      n_gen >= 3,
            "sealed_wisdom":   sum(1 for w in wisdom if w.get("sealed")),
            "latest_wisdom":   wisdom[-1]["content"][:100] if wisdom else None,
        }

    # ── Get family timeline ───────────────────────────────────────────────────

    def get_timeline(self, n: int = 20) -> list:
        """Get the family's combined milestone + wisdom timeline."""
        wisdom   = [{"type": "wisdom",    "date": w["date"],
                      "content": w["content"][:80], "author": w.get("author","?"),
                      "sealed": w.get("sealed", False)}
                    for w in self._load_wisdom()]
        milests  = [{"type": "milestone", "date": m["date"],
                      "content": f"{m.get('emoji','🦅')} {m.get('title','?')} — {m.get('member','?')}",
                      "author": m.get("member","?"), "sealed": True}
                    for m in self._load_milestones()]
        combined = sorted(wisdom + milests, key=lambda x: x["date"], reverse=True)
        return combined[:n]

    def _load_wisdom(self) -> list:
        if not WISDOM_LOG.exists(): return []
        entries = []
        for line in WISDOM_LOG.read_text().strip().split("\n"):
            try:
                e = json.loads(line)
                if e.get("family_id") == self.family_id:
                    entries.append(e)
            except Exception: pass
        return entries

    def _load_milestones(self) -> list:
        if not MILESTONE_LOG.exists(): return []
        entries = []
        for line in MILESTONE_LOG.read_text().strip().split("\n"):
            try:
                e = json.loads(line)
                if e.get("family_id") == self.family_id:
                    entries.append(e)
            except Exception: pass
        return entries


# ══════════════════════════════════════════════════════════════════════════════
# RITE OF PASSAGE — formal ceremonies for milestone achievements
# ══════════════════════════════════════════════════════════════════════════════

class RiteOfPassage:
    """
    Formal on-chain ceremonies for milestone achievements.
    Not just XP. Real rituals that families design together, seal permanently,
    and reference as living history.

    The moment a child earns 'Sovereign Epistemic Node' should feel different
    from earning a video game badge. It should feel like becoming something.
    """

    def conduct(self, member: str, rite_key: str,
                family_id: str = "default",
                family_statement: str = "",
                member_pledge: str = "") -> dict:
        """
        Conduct a Rite of Passage ceremony.
        Records the ceremony permanently and seals it with the Shield Rune.
        """
        rite = RITES_OF_PASSAGE.get(rite_key)
        if not rite:
            return {"error": f"Unknown rite: {rite_key}"}

        ceremony_id = hashlib.sha256(
            f"{member}{rite_key}{datetime.datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        ceremony = {
            "ceremony_id":     ceremony_id,
            "timestamp":       datetime.datetime.now().isoformat(),
            "date":            datetime.date.today().isoformat(),
            "family_id":       family_id,
            "member":          member,
            "rite_key":        rite_key,
            "rite_title":      rite["title"],
            "rite_emoji":      rite["emoji"],
            "meaning":         rite["meaning"],
            "ceremony_guide":  rite["ceremony"],
            "rune_granted":    rite["rune_grant"],
            "family_statement": family_statement or f"The {family_id} family witnesses this.",
            "member_pledge":   member_pledge or "I understand what this means.",
            "sealed":          False,
            "rune_anchor":     None,
        }

        # Write ceremony record
        ceremony_path = LEGACY_DIR / family_id / f"rite_{ceremony_id}.json"
        ceremony_path.parent.mkdir(parents=True, exist_ok=True)
        ceremony_path.write_text(json.dumps(ceremony, indent=2))

        # Write human-readable ceremony document
        self._write_ceremony_doc(ceremony)

        # Seal permanently
        try:
            from rune_memory import ShieldRune, RuneMemory
            mem = RuneMemory()
            entry_id = mem.record(
                f"RITE OF PASSAGE: {rite['emoji']} {rite['title']} — {member}\n"
                f"Family: {family_id} | Date: {ceremony['date']}\n"
                f"Meaning: {rite['meaning']}\n"
                f"Pledge: {ceremony['member_pledge']}",
                source="rite_of_passage",
                coherence=0.95,
                tags=["rite_of_passage", rite_key, member, family_id]
            )
            seal = ShieldRune().seal(
                entry_id,
                note=f"Rite of Passage: {rite['title']} — {member} | {family_id}",
                broadcaster=family_id
            )
            ceremony["sealed"]      = True
            ceremony["rune_anchor"] = seal.get("bitcoin_txid", seal.get("seal_hash",""))[:32]
            ceremony_path.write_text(json.dumps(ceremony, indent=2))
        except Exception as e:
            print(f"[rite] Seal failed: {e}")

        # Record milestone in Legacy Ledger
        ledger = LegacyLedger(family_id)
        ledger.record_milestone(rite_key, member, notes=member_pledge)

        print(f"[rite] {rite['emoji']} {rite['title']} — {member} | "
              f"{'SEALED 🛡️' if ceremony['sealed'] else 'recorded'}")
        return ceremony

    def _write_ceremony_doc(self, c: dict):
        """Write the ceremony as a beautiful markdown document."""
        doc = f"""# {c['rite_emoji']} Rite of Passage: {c['rite_title']}

**Family:** {c['family_id']} | **Member:** {c['member']} | **Date:** {c['date']}

---

## The Meaning

{c['meaning']}

---

## The Ceremony

*{c['ceremony_guide']}*

---

## Family Statement

> {c['family_statement']}

## Member Pledge

> {c['member_pledge']}

---

**Rune Granted:** {c['rune_granted']} fragments

**Sealed:** {'🛡️ Bitcoin-anchored — permanent' if c.get('sealed') else '⏳ Pending seal'}
{f"**Anchor:** `{c.get('rune_anchor','?')}`" if c.get('rune_anchor') else ''}

---
*AUBIEETERNAL Legacy Ledger — This ceremony is part of your family's permanent record.*
*War Eagle Eternal 🦅❤️*
"""
        doc_dir = LEGACY_DIR / c["family_id"]
        doc_dir.mkdir(parents=True, exist_ok=True)
        (doc_dir / f"rite_{c['ceremony_id']}.md").write_text(doc)


# ══════════════════════════════════════════════════════════════════════════════
# DYNASTY SCORE — compute the family's legacy position
# ══════════════════════════════════════════════════════════════════════════════

def get_global_dynasty_stats() -> dict:
    """Aggregate stats across all families."""
    if not MILESTONE_LOG.exists():
        return {"total_families": 0, "total_milestones": 0, "dynasty_families": 0}
    entries = []
    for line in MILESTONE_LOG.read_text().strip().split("\n"):
        try: entries.append(json.loads(line))
        except Exception: pass
    families = set(e.get("family_id","?") for e in entries)
    return {
        "total_families":    len(families),
        "total_milestones":  len(entries),
        "total_rites":       len([e for e in entries if e.get("key") in RITES_OF_PASSAGE]),
        "highest_rite":      max(
            (e.get("key","") for e in entries),
            key=lambda k: RITES_OF_PASSAGE.get(k, {}).get("rune_grant", 0),
            default="none"
        ),
    }


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("👑 Legacy Ledger Test")
    print("=" * 50)
    family_id = "test_dynasty"
    ledger    = LegacyLedger(family_id)
    e1 = ledger.record_wisdom(
        "The greatest lie my generation was told: that you need credentials to know things. "
        "The truth is freely available to anyone willing to trace it to its source.",
        author="grandparent", generation=2, seal=True
    )
    print(f"\n✅ Wisdom recorded: {e1['entry_id'][:8]} | Sealed: {e1.get('sealed')}")

    rite   = RiteOfPassage()
    result = rite.conduct(
        member="Gaby", rite_key="first_seal", family_id=family_id,
        family_statement="The family witnesses Gaby's first permanent truth.",
        member_pledge="I understand that sealed truth cannot be taken from me."
    )
    print(f"✅ Rite conducted: {result['rite_emoji']} {result['rite_title']} | Sealed: {result['sealed']}")

    state = ledger.get_dynasty_state()
    print(f"\n📊 Dynasty State:")
    print(f"   Level: {state['dynasty_level']} | Score: {state['dynasty_score']}/100")
    print(f"   Wisdom entries: {state['total_wisdom']} | Sealed: {state['sealed_wisdom']}")
    print(f"   Generations active: {state['generations_active']}")
    print(f"\n✅ Legacy Ledger operational — War Eagle Eternal 🦅")
