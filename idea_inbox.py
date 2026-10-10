"""
idea_inbox.py — never lose an idea because an AI ran out of usage.

`!idea <text>` from the Discord or SimpleX IT bot (or the CLI) appends one
dated line to a markdown file on the rig. Respects the three-door memory
layout (CLAUDE.md): a tag picks the door, and an untagged idea goes to an
unsorted inbox instead of being guessed into the wrong one.

    !idea #institute lesson on how bridges carry weight, with a straw bridge build
    !idea #business offer local-AI setup as a flat-fee package
    !idea #personal call Juan about the board meeting
    !idea the kiosk should say good morning      -> unsorted inbox
    !ideas #institute                              -> last 5 institute ideas

curriculum_autogen.py reads the latest #institute ideas as hints.
Ideas live outside the repo (no personal data in git). Never raises.

CLI:  python3 idea_inbox.py "#institute text..."      python3 idea_inbox.py --list institute
Bot:  reply = handle_message(text, source="discord");  if reply: send(reply)
"""
from __future__ import annotations

import datetime
import os
import re
import sys
from pathlib import Path

HOME = Path.home()
DOORS = {
    "institute": Path("/srv/institute/ideas.md"),
    "business":  Path("/srv/vanhorn/ideas.md"),
    "personal":  HOME / "grok" / "ideas.md",
    "inbox":     HOME / "ideas_inbox.md",
}
TAGS = {
    "#institute": "institute", "#inst": "institute", "#school": "institute", "#curriculum": "institute",
    "#business": "business", "#biz": "business", "#vanhorn": "business",
    "#personal": "personal", "#me": "personal",
}


def _door_for(text: str) -> tuple[str, str]:
    door = "inbox"
    for tag, d in TAGS.items():
        if re.search(rf"(?<!\w){re.escape(tag)}\b", text, re.I):
            door = d
            text = re.sub(rf"(?<!\w){re.escape(tag)}\b", "", text, flags=re.I)
            break
    return door, " ".join(text.split())


def add_idea(text: str, source: str = "cli") -> tuple[bool, str]:
    door, clean = _door_for(text or "")
    if not clean:
        return False, "Empty idea - write something after !idea."
    path = DOORS[door]
    line = f"- {datetime.datetime.now():%Y-%m-%d %H:%M} [{source}] {clean}\n"
    for target in (path, DOORS["inbox"]):  # if a door isn't writable, never lose it
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            new = not target.exists()
            with target.open("a") as f:
                if new:
                    f.write(f"# Ideas ({'unsorted' if target == DOORS['inbox'] else door})\n\n")
                f.write(line)
            where = door if target == path else f"inbox (couldn't write {door})"
            hint = "" if door != "inbox" else " Tag it #institute, #business or #personal to file it."
            return True, f"Saved to {where}.{hint}"
        except Exception as e:
            err = e
    return False, f"Couldn't save the idea: {err}"


def recent_ideas(door: str = "institute", n: int = 5) -> list[str]:
    try:
        lines = [l.strip()[2:] for l in DOORS[door].read_text().splitlines() if l.startswith("- ")]
        return lines[-n:]
    except Exception:
        return []


def handle_message(text: str, source: str = "bot") -> str | None:
    """For the Discord/SimpleX bots. Returns a reply, or None if the message isn't an idea command."""
    t = (text or "").strip()
    m = re.match(r"^!ideas\b\s*(#\w+)?", t, re.I)
    if m:
        door = TAGS.get((m.group(1) or "#institute").lower(), "institute")
        items = recent_ideas(door)
        return f"Last {len(items)} {door} ideas:\n" + "\n".join(items) if items else f"No {door} ideas yet."
    m = re.match(r"^!idea\b\s*(.*)$", t, re.I | re.S)
    if m:
        return add_idea(m.group(1), source=source)[1]
    return None


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--list":
        print("\n".join(recent_ideas(sys.argv[2] if len(sys.argv) > 2 else "institute")) or "(none)")
    elif len(sys.argv) >= 2:
        print(add_idea(" ".join(sys.argv[1:]), source="cli")[1])
    else:
        print(__doc__)
