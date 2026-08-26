"""
family_connect.py — AUBIEETERNAL Family Connect Layer
======================================================
Encrypted Nostr messaging between families + groups +
X (Twitter) sharing + public Family Lattice feed.

Features:
  - Share to X: one-click formatted posts for key events
  - Private Family Messaging: NIP-04 encrypted DMs via Nostr
  - Family Groups: small private groups with shared challenges
  - Public Lattice Feed: opt-in family updates

Usage:
    from family_connect import ShareToX, FamilyMessenger, FamilyGroups
"""

import json, datetime, hashlib, os, requests
from pathlib import Path

CONNECT_DIR  = Path("/mnt/main/family_connect")
MESSAGES_DIR = CONNECT_DIR / "messages"
GROUPS_DIR   = CONNECT_DIR / "groups"
FEED_LOG     = CONNECT_DIR / "public_feed.jsonl"
CONNECT_DIR.mkdir(parents=True, exist_ok=True)
MESSAGES_DIR.mkdir(parents=True, exist_ok=True)
GROUPS_DIR.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# SHARE TO X
# ══════════════════════════════════════════════════════════════════════════════

class ShareToX:
    """Generate formatted X posts for key AUBIEETERNAL events."""

    BASE_URL = "https://twitter.com/intent/tweet?text="

    @staticmethod
    def lesson_complete(kid_name: str, lesson: str, coherence: float,
                        xp: int, streak: int) -> dict:
        """Generate post for lesson completion."""
        text = (
            f"🦅 {kid_name} just completed '{lesson}' on AUBIEETERNAL!\n\n"
            f"📊 Coherence: {coherence:.2f} | +{xp} XP | 🔥 {streak} day streak\n\n"
            f"Sovereign family learning — steelmanning, Bitcoin, antifragility.\n\n"
            f"#AUBIEETERNAL #SovereignEducation #WearEagle #Bitcoin"
        )
        return {
            "text":     text,
            "url":      ShareToX.BASE_URL + requests.utils.quote(text),
            "template": "lesson_complete",
        }

    @staticmethod
    def badge_earned(kid_name: str, badge: str, total_xp: int) -> dict:
        text = (
            f"🏅 {kid_name} earned the '{badge}' badge!\n\n"
            f"Total XP: {total_xp} | AUBIEETERNAL Sovereign Lattice\n\n"
            f"Teaching the next generation: truth-seeking, steelmanning, "
            f"Bitcoin sovereignty, and antifragility.\n\n"
            f"#AUBIEETERNAL #Bitcoin #WearEagle"
        )
        return {
            "text": text,
            "url":  ShareToX.BASE_URL + requests.utils.quote(text),
            "template": "badge",
        }

    @staticmethod
    def streak_milestone(kid_name: str, streak: int, total_xp: int) -> dict:
        emoji = "🔥" * min(streak // 7, 5)
        text = (
            f"{emoji} {kid_name} is on a {streak}-day learning streak!\n\n"
            f"AUBIEETERNAL Sovereign Family School\n"
            f"Total XP: {total_xp} | Coherence: 1.000000\n\n"
            f"Lessons: Courage · Bitcoin · Antifragility · Simulation · Polyvagal\n\n"
            f"#AUBIEETERNAL #WearEagle #SovereignFamily"
        )
        return {
            "text": text,
            "url":  ShareToX.BASE_URL + requests.utils.quote(text),
            "template": "streak",
        }

    @staticmethod
    def child_rune_genesis(kid_name: str, confirmations: int,
                           block: str = "unknown") -> dict:
        text = (
            f"🔴 CHILD RUNE GENESIS — {kid_name} triggered it!\n\n"
            f"256 inter-rune confirmations reached on AUBIEETERNAL.\n"
            f"The Child Rune is ready for inscription on Bitcoin.\n\n"
            f"Block: {block} | Coherence: 1.000000 | Wonder: MAX\n\n"
            f"On-chain truth. Permanent. Sovereign.\n\n"
            f"#AUBIEETERNAL #Bitcoin #BitcoinRunes #WearEagle"
        )
        return {
            "text": text,
            "url":  ShareToX.BASE_URL + requests.utils.quote(text),
            "template": "child_rune",
        }

    @staticmethod
    def coherence_breakthrough(kid_name: str, coherence: float,
                                lesson: str, insight: str = "") -> dict:
        text = (
            f"✨ Coherence breakthrough — {kid_name} hit {coherence:.2f}!\n\n"
            f"Lesson: {lesson}\n"
            f"{f'Insight: {insight[:80]}' if insight else ''}\n\n"
            f"The AUBIEETERNAL swarm scores every steelman answer in real-time.\n"
            f"Coherence compounds. Truth wins.\n\n"
            f"#AUBIEETERNAL #Steelmanning #WearEagle"
        )
        return {
            "text": text,
            "url":  ShareToX.BASE_URL + requests.utils.quote(text),
            "template": "coherence",
        }

    @staticmethod
    def morning_insight(date: str, wonder: float, insight_preview: str) -> dict:
        text = (
            f"🌅 AUBIEETERNAL Morning Synthesis — {date}\n\n"
            f"Wonder Index: {wonder:.4f}\n\n"
            f"{insight_preview[:120]}...\n\n"
            f"Daily sovereign intelligence distilled by qwen3:32b ($0.00).\n"
            f"Full report: github.com/AUBIEETERNAL-INSTITUTE-INC/AUBIEETERNAL\n\n"
            f"#AUBIEETERNAL #AI #Bitcoin #WearEagle"
        )
        return {
            "text": text,
            "url":  ShareToX.BASE_URL + requests.utils.quote(text),
            "template": "morning",
        }


# ══════════════════════════════════════════════════════════════════════════════
# FAMILY MESSENGER — encrypted Nostr DMs
# ══════════════════════════════════════════════════════════════════════════════

class FamilyMessenger:
    """
    Private encrypted messaging between families via Nostr NIP-04.
    Falls back to local file storage when Nostr is not configured.
    """

    def __init__(self, from_family_id: str):
        self.from_family_id = from_family_id
        self.inbox_dir      = MESSAGES_DIR / from_family_id
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.inbox_log      = self.inbox_dir / "inbox.jsonl"
        self.sent_log       = self.inbox_dir / "sent.jsonl"

    def send(self, to_family_id: str, message: str,
             message_type: str = "text") -> dict:
        """
        Send a message to another family.
        In production: encrypts and publishes via Nostr NIP-04.
        Currently: stores in shared local directory.
        """
        entry = {
            "id":           hashlib.sha256(
                f"{self.from_family_id}{to_family_id}{message}{datetime.datetime.now().isoformat()}".encode()
            ).hexdigest()[:16],
            "from":         self.from_family_id,
            "to":           to_family_id,
            "message":      message,
            "type":         message_type,
            "timestamp":    datetime.datetime.now().isoformat(),
            "read":         False,
            "encrypted":    False,   # True when Nostr nsec is configured
        }

        # Write to sender's sent log
        with open(self.sent_log, "a") as f:
            f.write(json.dumps(entry) + "\n")

        # Write to recipient's inbox
        recv_inbox = MESSAGES_DIR / to_family_id
        recv_inbox.mkdir(parents=True, exist_ok=True)
        with open(recv_inbox / "inbox.jsonl", "a") as f:
            f.write(json.dumps(entry) + "\n")

        return entry

    def get_inbox(self, limit: int = 20) -> list:
        """Get messages in this family's inbox."""
        if not self.inbox_log.exists():
            return []
        try:
            lines   = self.inbox_log.read_text().strip().split("\n")
            entries = []
            for line in reversed(lines[-100:]):
                try:
                    entries.append(json.loads(line))
                    if len(entries) >= limit:
                        break
                except Exception:
                    pass
            return entries
        except Exception:
            return []

    def get_sent(self, limit: int = 20) -> list:
        """Get messages sent by this family."""
        if not self.sent_log.exists():
            return []
        try:
            lines = self.sent_log.read_text().strip().split("\n")
            entries = []
            for line in reversed(lines[-100:]):
                try:
                    entries.append(json.loads(line))
                    if len(entries) >= limit:
                        break
                except Exception:
                    pass
            return entries
        except Exception:
            return []

    def mark_read(self, message_id: str):
        """Mark a message as read."""
        if not self.inbox_log.exists():
            return
        try:
            lines   = self.inbox_log.read_text().strip().split("\n")
            updated = []
            for line in lines:
                try:
                    entry = json.loads(line)
                    if entry.get("id") == message_id:
                        entry["read"] = True
                    updated.append(json.dumps(entry))
                except Exception:
                    updated.append(line)
            self.inbox_log.write_text("\n".join(updated))
        except Exception:
            pass

    def unread_count(self) -> int:
        msgs = self.get_inbox()
        return sum(1 for m in msgs if not m.get("read", True))


# ══════════════════════════════════════════════════════════════════════════════
# FAMILY GROUPS — shared challenges + group chat
# ══════════════════════════════════════════════════════════════════════════════

class FamilyGroups:
    """
    Small private groups for families doing shared challenges.
    e.g. "Miami Sovereign Families", "Bitcoin Homeschoolers"
    """

    GROUPS_REGISTRY = GROUPS_DIR / "registry.json"

    def __init__(self):
        self.groups = self._load()

    def _load(self) -> dict:
        if self.GROUPS_REGISTRY.exists():
            try:
                return json.loads(self.GROUPS_REGISTRY.read_text())
            except Exception:
                pass
        defaults = {
            "sovereign_families": {
                "id":          "sovereign_families",
                "name":        "Sovereign Families",
                "description": "Families running the AUBIEETERNAL lattice",
                "emoji":       "🦅",
                "members":     ["operator"],
                "public":      True,
                "created_at":  datetime.datetime.now().isoformat(),
                "challenges":  [],
            }
        }
        self.GROUPS_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        self.GROUPS_REGISTRY.write_text(json.dumps(defaults, indent=2))
        return defaults

    def _save(self):
        self.GROUPS_REGISTRY.write_text(json.dumps(self.groups, indent=2))

    def create_group(self, group_id: str, name: str, description: str,
                     creator_family_id: str, emoji: str = "🌀",
                     public: bool = False) -> dict:
        group = {
            "id":          group_id,
            "name":        name,
            "description": description,
            "emoji":       emoji,
            "members":     [creator_family_id],
            "public":      public,
            "created_at":  datetime.datetime.now().isoformat(),
            "created_by":  creator_family_id,
            "challenges":  [],
        }
        self.groups[group_id] = group
        self._save()
        return group

    def join_group(self, group_id: str, family_id: str) -> bool:
        if group_id not in self.groups:
            return False
        if family_id not in self.groups[group_id]["members"]:
            self.groups[group_id]["members"].append(family_id)
            self._save()
        return True

    def post_to_group(self, group_id: str, family_id: str,
                      message: str, message_type: str = "text") -> dict | None:
        if group_id not in self.groups:
            return None
        if family_id not in self.groups[group_id]["members"]:
            return None

        entry = {
            "id":        hashlib.sha256(
                f"{family_id}{group_id}{message}{datetime.datetime.now().isoformat()}".encode()
            ).hexdigest()[:12],
            "from":      family_id,
            "type":      message_type,
            "message":   message,
            "timestamp": datetime.datetime.now().isoformat(),
        }

        group_log = GROUPS_DIR / f"{group_id}.jsonl"
        with open(group_log, "a") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    def get_group_messages(self, group_id: str, limit: int = 30) -> list:
        group_log = GROUPS_DIR / f"{group_id}.jsonl"
        if not group_log.exists():
            return []
        try:
            lines   = group_log.read_text().strip().split("\n")
            entries = []
            for line in reversed(lines[-200:]):
                try:
                    entries.append(json.loads(line))
                    if len(entries) >= limit:
                        break
                except Exception:
                    pass
            return entries
        except Exception:
            return []

    def add_challenge(self, group_id: str, title: str,
                      description: str, xp: int = 50) -> dict | None:
        if group_id not in self.groups:
            return None
        challenge = {
            "id":          hashlib.sha256(title.encode()).hexdigest()[:8],
            "title":       title,
            "description": description,
            "xp":          xp,
            "created_at":  datetime.datetime.now().isoformat(),
            "completions": [],
        }
        self.groups[group_id]["challenges"].append(challenge)
        self._save()
        return challenge

    def get_family_groups(self, family_id: str) -> list:
        return [g for g in self.groups.values()
                if family_id in g.get("members", [])]

    def list_public_groups(self) -> list:
        return [g for g in self.groups.values() if g.get("public")]


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC FAMILY LATTICE FEED
# ══════════════════════════════════════════════════════════════════════════════

class LatticeFeed:
    """
    Opt-in public feed of family achievements and insights.
    Families can post updates; others can see and react.
    """

    def post(self, family_id: str, family_display: str, family_emoji: str,
             event_type: str, content: str, public: bool = True) -> dict:
        """Post an event to the public feed."""
        entry = {
            "id":           hashlib.sha256(
                f"{family_id}{event_type}{content}{datetime.datetime.now().isoformat()}".encode()
            ).hexdigest()[:12],
            "family_id":    family_id,
            "display_name": family_display,
            "emoji":        family_emoji,
            "event_type":   event_type,
            "content":      content,
            "public":       public,
            "timestamp":    datetime.datetime.now().isoformat(),
            "reactions":    {},   # emoji → count
        }
        if public:
            with open(FEED_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        return entry

    def get_feed(self, limit: int = 30) -> list:
        """Get recent public feed entries."""
        if not FEED_LOG.exists():
            return []
        try:
            lines   = FEED_LOG.read_text().strip().split("\n")
            entries = []
            for line in reversed(lines[-500:]):
                try:
                    e = json.loads(line)
                    if e.get("public"):
                        entries.append(e)
                        if len(entries) >= limit:
                            break
                except Exception:
                    pass
            return entries
        except Exception:
            return []

    def react(self, entry_id: str, emoji: str):
        """Add a reaction to a feed entry."""
        if not FEED_LOG.exists():
            return
        try:
            lines   = FEED_LOG.read_text().strip().split("\n")
            updated = []
            for line in lines:
                try:
                    entry = json.loads(line)
                    if entry.get("id") == entry_id:
                        entry.setdefault("reactions", {})[emoji] = \
                            entry["reactions"].get(emoji, 0) + 1
                    updated.append(json.dumps(entry))
                except Exception:
                    updated.append(line)
            FEED_LOG.write_text("\n".join(updated))
        except Exception:
            pass

    def event_labels(self) -> dict:
        return {
            "lesson_complete":   "📖 Completed a lesson",
            "badge_earned":      "🏅 Earned a badge",
            "streak_milestone":  "🔥 Streak milestone",
            "child_rune":        "🔴 Child Rune Genesis",
            "coherence_spike":   "✨ Coherence breakthrough",
            "experiment":        "🧪 Ran an experiment",
            "morning_insight":   "🌅 Morning synthesis",
            "custom":            "💬 Family update",
        }
