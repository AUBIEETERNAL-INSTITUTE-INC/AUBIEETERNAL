# How Aubie protects your child's privacy

A short, plain guide for parents. No scare talk. No legal fine print.

## The short version

Aubie is meant to help your child learn **on this computer**. We do not sell data. We do not build ads. We do not score your child's personality.

Below, each promise is marked **True today** (what the software actually does now) or **Coming soon** (designed, not fully built yet).

## What is stored today (True today)

On a typical home install, learning progress lives in local files under `/mnt/main/families/` (or the install's local data folder). For each family account that can include:

| What | Where | Notes |
|------|--------|--------|
| XP, level, badges, streaks, quests done | `families/<id>.json` | Progress game stats |
| Optional Memory Palace notes | same file, `memory_palace` list | Topic + short text + tags + time — only if something was saved |
| Model / thinking preferences | same file | Which local model to use |
| Live chat in Ask Aubie | **browser session only** | Clears when you close or refresh; not a permanent transcript store |
| Family name / kid display name in the registry | `family_registry.json` | Needed to log in |

**Not stored today as a permanent kid profile:** full chat transcripts, emotion scores, personality scores, or ad IDs.

Other institute files on the machine (swarm logs, curriculum drafts, etc.) are about the **system**, not a child's private chat. Academic "transcript" features, if used, are separate learning records you choose to generate — not chat logs.

## Our principles

### 1. Stays on this computer
**True today for family learning data:** progress and Memory Palace notes are written on the local machine, not to a cloud AI vendor for training.  
**Coming soon:** clearer one-screen export/delete for everything Aubie ever wrote about your child, including any future lesson memory fields.

### 2. Keep the minimum
**Coming soon:** per lesson, keep only four learning facts — last miss, help level, mastery score, one verified check — and delete raw chat after a set number of days.  
**True today:** we do not yet enforce that four-field lesson memory. What exists is XP/progress and optional Memory Palace notes (which can be longer than four fields if someone saved them).

### 3. Parents see progress, not private transcripts
**True today:** Parent Dashboard-style views show progress (XP, lessons, badges). Chat is session-based, so there is no permanent chat transcript library for parents to scroll.  
**Coming soon:** simple progress summaries that never include personality or emotion scores (we do not compute those today either).

### 4. Opt-in, visible, deletable
**True today (partial):** families create accounts locally; Memory Palace entries can be browsed in the portal.  
**Coming soon:** one parent button to delete all saved child learning data; a kid-facing page “What Aubie remembers about me.”

### 5. Never for ads, ranking, or sharing without consent
**True today:** the portal does not include ad SDKs or child ranking for advertisers. Open-source code is public; **your family's local files are not uploaded by that fact alone**.  
**Coming soon:** explicit consent gates before any optional share (for example, publishing a school story you choose to share).

## Kid view — “What Aubie remembers about me”
**Coming soon.** The idea: a simple screen your child can open that lists only the saved learning facts and notes, in kid language, with nothing creepy.

## What to do if you want something deleted today
1. Open the family account on this computer.  
2. Clear or edit Memory Palace notes in the portal.  
3. Remove or reset the family JSON under the local `families/` data folder if you want a full wipe (advanced).  
**Coming soon:** a single “Delete my child's Aubie data” button that does this safely.

## Questions
See **Getting help** in the portal, or email `aubieeternal_institute@pm.me`. We would rather answer a privacy question twice than leave a parent guessing.
