# Project Folder and Markdown Organization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the demo's Markdown files into purpose-specific documentation
directories, preserve historical records, repair every active reference, and
remove only reproducible cache clutter.

**Architecture:** Keep `README.md` and `AGENTS.md` as the only root documentation
entry points. Move active documentation under `docs/` by audience, move superseded
monoliths under `docs/archive/`, and add `docs/README.md` as the navigation layer.
Use explicit source/destination moves and before/after metadata checks so research
data and outputs cannot be affected.

**Tech Stack:** POSIX filesystem operations, Markdown, ripgrep, SHA-256, Python
3.12, pytest.

## Global Constraints

- Do not modify or inspect event contents in `.venv/`, `data/raw/`,
  `data/processed/`, or `outputs/`.
- Do not move the standalone notebook, `higgs_4lepton_ml_project.md`, Obsidian
  files, `.pnpm-store`, or `未命名.base` from the research root.
- Preserve every user-authored Markdown document; only generated cache content may
  be deleted.
- Do not preprocess ROOT, train/evaluate models, or inspect the 120--130 GeV real
  data signal window.
- The parent Git repository has no commits and the demo is untracked; do not create
  a branch, worktree, stage, or commit.
- Never use a broad recursive deletion target. Cache removals must name the exact
  project paths approved in the design.

---

### Task 1: Capture safety baselines and validate destinations

**Files:**

- Read only: all seven source Markdown files
- Read only: `data/raw/`, `data/processed/`, `outputs/`, `.venv/`

**Interfaces:**

- Produces: in-session baseline maps for document SHA-256 values and protected-file
  path/size/mtime metadata.

- [ ] **Step 1: Record source document hashes and sizes**

Run from `/Users/xuhongyi/Documents/research`:

```bash
shasum -a 256 \
  CODEX_HANDOFF_AND_ROADMAP.md \
  DATA_DESCRIPTION.md \
  SELECTION_STANDARD.md \
  higgs-xgboost-demo/DEMO_OVERVIEW.md \
  higgs-xgboost-demo/NEXT_STAGE.md \
  higgs-xgboost-demo/PROGRESS_BRIEFING.md \
  higgs-xgboost-demo/higgs_4lepton_xgboost_demo.md
```

Retain the output in the execution session for comparison after the move.

- [ ] **Step 2: Record protected artifact metadata without reading contents**

Run:

```bash
find higgs-xgboost-demo/data/raw \
     higgs-xgboost-demo/data/processed \
     higgs-xgboost-demo/outputs \
     higgs-xgboost-demo/.venv \
     -type f -exec stat -f '%N|%z|%m' {} \;
```

Sort and retain the output in the execution session. Do not hash or open ROOT,
processed CSV, model, plot, or output files.

- [ ] **Step 3: Prove every source exists and every destination is absent**

Check the seven source paths individually. Check that none of these destinations
exists:

```text
higgs-xgboost-demo/docs/project/overview.md
higgs-xgboost-demo/docs/roadmap/next-stage.md
higgs-xgboost-demo/docs/briefings/progress-briefing.md
higgs-xgboost-demo/docs/physics/data-description.md
higgs-xgboost-demo/docs/physics/selection-standard.md
higgs-xgboost-demo/docs/archive/original-demo-spec.md
higgs-xgboost-demo/docs/archive/codex-handoff-and-roadmap.md
```

Stop without moving anything if a source is missing or a destination exists.

### Task 2: Create the documentation hierarchy and move documents

**Files:**

- Create directories: `docs/project/`, `docs/roadmap/`, `docs/briefings/`,
  `docs/physics/`, `docs/archive/`
- Move: the seven paths listed in Task 1

**Interfaces:**

- Consumes: validated source/destination map and pre-move hashes from Task 1.
- Produces: the approved directory tree with byte-identical moved files.

- [ ] **Step 1: Create only the approved directories**

Run from the demo root:

```bash
mkdir -p docs/project docs/roadmap docs/briefings docs/physics docs/archive
```

- [ ] **Step 2: Move the four project-root documents explicitly**

Run from the demo root:

```bash
mv DEMO_OVERVIEW.md docs/project/overview.md
mv NEXT_STAGE.md docs/roadmap/next-stage.md
mv PROGRESS_BRIEFING.md docs/briefings/progress-briefing.md
mv higgs_4lepton_xgboost_demo.md docs/archive/original-demo-spec.md
```

- [ ] **Step 3: Move the three related research-root documents explicitly**

Run from the research root:

```bash
mv DATA_DESCRIPTION.md higgs-xgboost-demo/docs/physics/data-description.md
mv SELECTION_STANDARD.md higgs-xgboost-demo/docs/physics/selection-standard.md
mv CODEX_HANDOFF_AND_ROADMAP.md \
  higgs-xgboost-demo/docs/archive/codex-handoff-and-roadmap.md
```

- [ ] **Step 4: Verify byte identity immediately after moving**

Run `shasum -a 256` on all seven destination files and compare each hash to Task
1 before any content edit. Stop on any mismatch.

### Task 3: Establish active documentation and archive boundaries

**Files:**

- Create: `docs/README.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/project/overview.md`
- Modify: `docs/roadmap/next-stage.md`
- Modify: `docs/archive/original-demo-spec.md`
- Modify: `docs/archive/codex-handoff-and-roadmap.md`

**Interfaces:**

- Produces: one navigation index, explicit active sources of truth, and archive
  notices that prevent historical documents from being mistaken for current state.

- [ ] **Step 1: Create `docs/README.md` with the exact navigation groups**

Use `apply_patch` to create a concise index containing:

```markdown
# Documentation

## Recommended reading

1. [Project README](../README.md)
2. [Project overview](project/overview.md)
3. [Selection standard](physics/selection-standard.md)
4. [Next-stage roadmap](roadmap/next-stage.md)

## Active references

| Document | Purpose |
|---|---|
| [Project overview](project/overview.md) | Architecture, workflow, and verified state |
| [Data description](physics/data-description.md) | Inputs, schemas, provenance, and limits |
| [Selection standard](physics/selection-standard.md) | Implemented event-selection contract |
| [Next-stage roadmap](roadmap/next-stage.md) | Current priorities and acceptance criteria |
| [Progress briefing](briefings/progress-briefing.md) | Professor-facing status summary |

## Historical and development records

Archive documents preserve history and are not current sources of truth. Completed
designs and plans remain under `superpowers/`.
```

Include links to both archive files and to `superpowers/specs/` and
`superpowers/plans/` in the historical section.

- [ ] **Step 2: Update the root entry points**

In `README.md`, replace root-document names with:

```text
docs/project/overview.md
docs/roadmap/next-stage.md
docs/briefings/progress-briefing.md
docs/archive/original-demo-spec.md
```

Add one visible link to `docs/README.md` near the opening reading order.

In `AGENTS.md`, make the startup order:

```text
AGENTS.md
README.md
docs/project/overview.md
docs/roadmap/next-stage.md
```

Point physics decisions to `docs/physics/selection-standard.md` and data details to
`docs/physics/data-description.md`.

- [ ] **Step 3: Verify active merge coverage before archiving monoliths**

Confirm that `AGENTS.md` contains the current verified test state, protected-data
constraints, and default Task 4. Confirm that `docs/roadmap/next-stage.md` contains
Task 4 and the later research stages. Confirm that `docs/project/overview.md`
contains the implemented pipeline, feature/weight/split behavior, outputs, current
limitations, and rerun commands.

If an item is absent, copy only that missing current information from the
appropriate monolith using `apply_patch`; do not copy duplicated historical
sections.

- [ ] **Step 4: Add archive notices**

Prepend this notice, adjusted only for the archive filename, to both archive files:

```markdown
> **Archived:** This document preserves historical design and handoff context. It
> is not a current source of truth. Start with `README.md`, `AGENTS.md`, and
> `docs/README.md`.
```

For links inside an archive file, use paths relative to `docs/archive/`, such as
`../../README.md`, `../../AGENTS.md`, and `../README.md`.

### Task 4: Repair all moved-document references

**Files:**

- Modify: all Markdown files reported by the reference audit

**Interfaces:**

- Consumes: the final move map from Task 2.
- Produces: no current workflow or navigation reference to an obsolete root path.

- [ ] **Step 1: Apply the canonical path replacements**

Use `apply_patch` so current project-root-relative prose uses:

```text
DEMO_OVERVIEW.md                -> docs/project/overview.md
NEXT_STAGE.md                   -> docs/roadmap/next-stage.md
PROGRESS_BRIEFING.md            -> docs/briefings/progress-briefing.md
DATA_DESCRIPTION.md             -> docs/physics/data-description.md
SELECTION_STANDARD.md           -> docs/physics/selection-standard.md
higgs_4lepton_xgboost_demo.md   -> docs/archive/original-demo-spec.md
CODEX_HANDOFF_AND_ROADMAP.md    -> docs/archive/codex-handoff-and-roadmap.md
```

Apply this to the root entry points, moved active documents, archive documents,
and every file under `docs/superpowers/plans/` and `docs/superpowers/specs/`.

- [ ] **Step 2: Fix navigation links relative to their containing files**

Use these relative-link bases:

```text
docs/project/*   -> ../briefings/, ../roadmap/, ../physics/, ../archive/
docs/physics/*   -> ../project/, ../roadmap/, ../archive/
docs/roadmap/*   -> ../project/, ../physics/, ../briefings/
docs/archive/*   -> ../../README.md, ../../AGENTS.md, ../README.md
```

- [ ] **Step 3: Scan for stale active references**

Run `rg` over all Markdown except the organization design and implementation plan.
Any old filename must either be removed or be explicitly labelled as a historical
former path. No old filename may appear in a startup list, command, or current
file-responsibility table.

- [ ] **Step 4: Validate Markdown links locally**

Extract every relative `.md` link from active documents, resolve it against the
containing file, and assert the destination exists. Archive and Superpowers links
must also resolve when they are intended as navigation rather than historical
literal text.

### Task 5: Remove only approved generated caches

**Files:**

- Delete: `.pytest_cache/`
- Delete: `src/__pycache__/`
- Delete: `scripts/__pycache__/`
- Delete: `tests/__pycache__/`
- Delete: project `.DS_Store` files found during the initial inventory

**Interfaces:**

- Produces: a cache-free project tree without deleting user-authored or research
  artifacts.

- [ ] **Step 1: Resolve the exact cache targets again**

List each approved cache directory and `.DS_Store` path. Verify every target is
inside `/Users/xuhongyi/Documents/research/higgs-xgboost-demo` and none is a
symlink.

- [ ] **Step 2: Delete only those explicit paths**

Remove the four named cache directories and each individually resolved project
`.DS_Store`. Do not use the project root, `$HOME`, `~`, a wildcard, or an unresolved
environment variable as a deletion target.

- [ ] **Step 3: Verify cleanup**

Run:

```bash
find . -name '.DS_Store' -o -name '__pycache__' -o -name '.pytest_cache'
```

Expected before tests: no output.

### Task 6: Verify behavior and protected artifacts

**Files:**

- Read only: source, tests, docs, and protected-file metadata

**Interfaces:**

- Produces: fresh evidence that organization changed paths only, not software or
  research artifacts.

- [ ] **Step 1: Compile and run the complete suite**

Run from the demo root:

```bash
.venv/bin/python -m compileall -q src scripts tests
.venv/bin/python -m pytest -q
.venv/bin/python -m scripts.prepare_demo --help
```

Expected: compilation succeeds, the complete suite passes, and help shows
`--output-dir`.

- [ ] **Step 2: Compare protected metadata to Task 1**

Regenerate the sorted `stat` map for `.venv`, `data/raw`, `data/processed`, and
`outputs`. It must exactly equal the baseline. If `.venv` metadata changes merely
from interpreter cache behavior, compare all pre-existing files individually and
document the reason; data and output metadata must always match exactly.

- [ ] **Step 3: Run final cache cleanup again**

The compile and pytest commands recreate cache directories. Re-run Task 5's exact
target resolution and cleanup, then assert the cache scan produces no output.

- [ ] **Step 4: Run final structure and reference checks**

Confirm:

- every approved destination exists;
- every old source location is absent;
- both research-root exclusions remain in place;
- every active Markdown link resolves;
- old names occur only in the organization design/plan move map or explicitly
  historical prose;
- the demo root contains only `README.md` and `AGENTS.md` as Markdown entry points.

- [ ] **Step 5: Review and hand off without committing**

Report moved files, archived files, cache removals, test output, protected metadata
comparison, and the next active roadmap path. Do not stage or commit because this
repository has no commit history and the project remains untracked.
