# AUBIEETERNAL — Legacy Archive

_Provenance bundle from the pre-StartOS era (Colab / JupyterLab period)._

This directory is the historical record of what the AUBIEETERNAL swarm discovered before it migrated to sovereign hardware. It is preserved here as a reference, not as runnable code — newer versions live in the main project tree.

## What's inside

### `logs/`
The canonical truth and daily logs from the swarm's final Colab run.

| File | Entries | Snapshot date |
|---|---|---|
| `master_truth_log.jsonl` | 10,327 | 2026-05-12 11:37 |
| `daily_log.jsonl` | 516 | 2026-05-12 11:37 |

`logs/all-snapshots/` contains every intermediate snapshot of those two logs (8 versions of `master_truth_log`, 3 of `daily_log`) so you can reconstruct how the logs grew over time. The canonical files above are the largest/latest captures from May 12.

### `status/`
- `master_status.json` — final master-node state snapshot (66K)
- `swarm_status.json` — final swarm-coordinator snapshot
- `all-snapshots/` — every saved state, useful for reconstructing the timeline of swarm decisions

### `scripts/`
- `swarm_master.py` — the canonical swarm coordinator script (36K, 2026-05-12 21:23)
- `swarm_master_v4.py` — earlier v4 variant for reference
- `other/` — related Python files (lattice_core, etc.)

### `screenshots/error-story/`
163 chronologically-numbered screenshots of every "error" captured during the debugging journey. Filenames are prefixed `001_YYYY-MM-DD_` through `163_YYYY-MM-DD_` — open the folder, sort by name, and you'll walk through the debugging arc from **2026-03-14** (first capture) through **2026-05-13** (final pre-migration capture).

### `screenshots/app-milestones/`
135 screenshots of key UI and capability milestones — AubieEternal wallet, AubieShield, coherence/accuracy benchmarks, demo runs, dashboards, and platform integrations (Unisat, etc.). These are the moments the swarm hit a visible target.

### `notebooks/`
62 Jupyter notebooks (`.ipynb`) — the full Colab/JupyterLab development trail. Organized two ways:

- **`notebooks/by-version/`** — grouped by major version tag: `v27.3_prototype/`, `v60.8/`, `v60.9_main/`, `v60.9_daily-driver/`, `v61.2/`, `v63/`, `v63.0.85/`, `v64/`, `v65.0.0/`, `v5.5_dailydriver/`. The dense iteration phase shows up clearly: 14 daily-driver snapshots of v60.9 and 20 of v60.9 main alone.
- **`notebooks/by-date/`** — every notebook with a chronological numeric prefix (`001_2026-03-17_...` through `062_2026-05-09_...`), so the full evolution from the v27.3 prototype on March 17 to the v65 daily driver on May 9 plays back in order.

Largest single notebook is 9.3 MB. All notebooks are well under GitHub's per-file limits — no LFS needed for this folder.

### `snapshots/`
Project source-tree zip snapshots, organized by version tag. Includes the v4.1 → v60 evolution and several Google-Drive-exported bundles. **See "Upload notes" below before pushing — three of these exceed GitHub file size limits.**

## Upload notes for GitHub `/Legacy/`

**Two files exceed GitHub's 100 MB hard limit** and will be rejected on push:

- `snapshots/AUBIEETERNAL-20260501T175646Z-3-006.zip` (128 MB)
- `snapshots/AUBIEETERNAL-20260501T175646Z-3-001.zip` (101 MB)

Four more files are between 50–100 MB. GitHub allows these but warns; for a clean repo, configure **Git LFS** for the `snapshots/` folder before committing:

```bash
git lfs install
git lfs track "Legacy/snapshots/*.zip"
git add .gitattributes
git add Legacy/
git commit -m "Add AUBIEETERNAL legacy archive (pre-StartOS provenance)"
git push
```

If you'd rather not use LFS, alternatives:
- Re-bundle the seven `AUBIEETERNAL-20260501T175646Z-3-*.zip` parts into one archive and host on Releases / GDrive, linking from this README.
- Drop the seven-part split entirely and rely on the single `AUBIEETERNAL-main.zip` (11 MB) plus the per-version snapshots as the historical record.

## Timeline

- **2025-06 → 2025-07** — StartOS install attempts, balenaEtcher, ISO experiments
- **2026-03-14** — first "new error" capture, debugging journey begins
- **2026-04-14** — first AUBIEETERNAL v60.8 demo zip
- **2026-04 → 2026-05** — the dense error-story arc (163 captures), heavy iteration
- **2026-05-09** — last entry in the notebook trail (`AUBIEETERNAL_v65_0_0_DAILY_DRIVER_MAIN (3).ipynb`)
- **2026-05-12** — final truth log captured at 10,327 entries; swarm_master.py reaches its 36K final form
- **2026-05-13** — last error captures before migration to sovereign hardware

War Eagle.
