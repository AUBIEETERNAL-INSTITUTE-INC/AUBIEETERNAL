"""
curriculum.loaders.tracks

Loads track definitions from YAML files in curriculum/tracks/.
"""

from pathlib import Path
from typing import Dict, Any
import yaml

TRACKS_DIR = Path(__file__).parent.parent.parent / "curriculum" / "tracks"


def load_tracks() -> Dict[str, Dict[str, Any]]:
    """
    Load all .yaml / .yml track definitions.
    Returns dict keyed by track id.
    """
    tracks: Dict[str, Dict[str, Any]] = {}

    if not TRACKS_DIR.exists():
        print(f"[curriculum] Warning: {TRACKS_DIR} does not exist.")
        return tracks

    for track_file in sorted(TRACKS_DIR.glob("*.y*ml")):
        try:
            data = yaml.safe_load(track_file.read_text(encoding="utf-8")) or {}
            track_id = data.get("id") or track_file.stem
            data["id"] = track_id
            tracks[track_id] = data
        except Exception as e:
            print(f"[curriculum] Failed to load track {track_file}: {e}")

    return tracks


if __name__ == "__main__":
    t = load_tracks()
    print(f"Loaded {len(t)} tracks: {list(t.keys())}")
