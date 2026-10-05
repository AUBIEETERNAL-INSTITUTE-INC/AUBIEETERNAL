"""Kid-friendly flash cards for the AUBIEETERNAL portal.

Static decks live in flashcards/decks.json (user-editable).
Math and coin decks are generated in code so they never run out.
Progress is stored locally per profile name under DATA_DIR/flashcards/.
"""
from .ui import render_flashcards

__all__ = ["render_flashcards"]
