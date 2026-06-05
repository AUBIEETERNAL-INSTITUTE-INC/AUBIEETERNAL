"""
curriculum.loaders

Provides functions to load lessons and tracks from the modular curriculum/ structure.
"""

from .lessons import load_lessons
from .tracks import load_tracks

__all__ = ["load_lessons", "load_tracks"]
