# AUBIEETERNAL Curriculum System (v67+)

This directory contains the modular, versioned curriculum for AUBIEETERNAL.

## Structure

- `lessons/` — Individual lesson files written in Markdown with YAML frontmatter.
- `tracks/` — Track definitions that specify ordered sequences of lessons, prerequisites, and requirements.
- `loaders/` — Python code responsible for discovering, parsing, and loading lessons and tracks into usable data structures (compatible with `family_hud.py` and the Family HUD).
- `README.md` — This file.

## Lesson Format

Each file in `lessons/` should be named after its key (e.g. `core-v67-1.md`).

Example:

```markdown
---
id: core-v67-1
title: Core v67 — Epistemic Rigor First
topic: Every claim must be steelmanned, simulation-tested, and coherence-scored before acceptance.
steelman: What is the strongest argument that requiring steelmans for everything slows down learning and kills wonder?
example: A 7-year-old says 'the sky is blue because God painted it.' Parent helps: 'What's the strongest evidence against that? What would prove it true or false?'
age_hint: All ages — foundation of everything
xp: 25
rune: CORE•V67
min_coherence: 0.70
---

## Full Lesson Content

(Additional rich Markdown content, activities, further reading, etc. can go here.)
```

The loader will parse the frontmatter into the same dict format previously used in the hardcoded `LESSONS` dictionary.

## Track Format

Tracks live in `tracks/`. Example `core-v67.yaml`:

```yaml
id: core-v67
name: AUBIEETERNAL Core v67
description: The 10 foundational lessons required before any other track.
version: "v67"
lessons:
  - core-v67-1
  - core-v67-2
  - ...
  - core-v67-10
prerequisites: []
min_coherence: 0.78
xp_total: 264
```

## Usage in Code

```python
from curriculum.loaders.lessons import load_lessons
from curriculum.loaders.tracks import load_tracks

LESSONS = load_lessons()
TRACKS = load_tracks()

# Then use in FamilySession, etc.
```

## Design Principles (from School Charter)

- **Distributional Requirements**: Core content must be multi-channel, offline-first, forkable, and graduates have propagation duties.
- **Epistemic Rigor**: Every lesson includes steelman + simulation prompt + coherence scoring.
- **Sovereignty**: Lessons run locally, data stays with the family.

## Contributing / Proposals

New lessons and tracks should be proposed via `curriculum_proposals.py`. Approved items are merged into this directory structure.

See the School Charter Article VI for Distributional Requirements around the Core.

**War Eagle Eternal** 🦅
