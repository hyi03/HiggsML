# Project Folder and Markdown Organization Design

Date: 2026-08-05

## 1. Goal

Reorganize `higgs-xgboost-demo` so that its root contains only the project entry
points and software/data directories, while active documentation is grouped by
purpose and historical documents remain available without competing with the
current sources of truth.

The reorganization must preserve code behavior, research data, processed files,
models, plots, and historical technical records.

## 2. Scope

This work includes:

- Markdown files that belong to `higgs-xgboost-demo`, including the three related
  files currently stored in `/Users/xuhongyi/Documents/research`;
- internal documentation references affected by moved files;
- generated Python, pytest, and macOS metadata caches inside the demo;
- a new documentation index.

This work excludes and leaves in place:

- `/Users/xuhongyi/Documents/research/higgs_4lepton_ml_project.md`;
- `/Users/xuhongyi/Documents/research/introduction-to-machine-learning-higgs-peak.ipynb`;
- `/Users/xuhongyi/Documents/research/未命名.base`;
- `/Users/xuhongyi/Documents/research/.obsidian/`;
- `/Users/xuhongyi/Documents/research/.pnpm-store/`;
- the project's `.venv/`, `data/raw/`, `data/processed/`, and `outputs/` contents;
- source-code module layout, configuration paths, and runtime output paths.

## 3. Target structure

```text
higgs-xgboost-demo/
├── README.md
├── AGENTS.md
├── requirements.txt
├── config/
├── data/
├── outputs/
├── scripts/
├── src/
├── tests/
└── docs/
    ├── README.md
    ├── project/
    │   └── overview.md
    ├── physics/
    │   ├── data-description.md
    │   └── selection-standard.md
    ├── roadmap/
    │   └── next-stage.md
    ├── briefings/
    │   └── progress-briefing.md
    ├── archive/
    │   ├── original-demo-spec.md
    │   └── codex-handoff-and-roadmap.md
    └── superpowers/
        ├── plans/
        └── specs/
```

The root `README.md` remains the human usage entry point. `AGENTS.md` remains the
Codex operating entry point. `docs/README.md` becomes the documentation map.

## 4. Exact move map

| Current path | Destination |
|---|---|
| `DEMO_OVERVIEW.md` | `docs/project/overview.md` |
| `NEXT_STAGE.md` | `docs/roadmap/next-stage.md` |
| `PROGRESS_BRIEFING.md` | `docs/briefings/progress-briefing.md` |
| `/Users/xuhongyi/Documents/research/DATA_DESCRIPTION.md` | `docs/physics/data-description.md` |
| `/Users/xuhongyi/Documents/research/SELECTION_STANDARD.md` | `docs/physics/selection-standard.md` |
| `higgs_4lepton_xgboost_demo.md` | `docs/archive/original-demo-spec.md` |
| `/Users/xuhongyi/Documents/research/CODEX_HANDOFF_AND_ROADMAP.md` | `docs/archive/codex-handoff-and-roadmap.md` |

Moves preserve file contents unless a merge or reference update below explicitly
requires an edit.

## 5. Active documents and merge policy

The active documentation set is:

- `README.md`: installation, commands, outputs, and essential safety notes;
- `AGENTS.md`: current verified state, constraints, restoration steps, and the
  next Codex task;
- `docs/project/overview.md`: detailed project architecture and validated demo
  behavior;
- `docs/physics/data-description.md`: data sources, schemas, local inputs, and data
  limitations;
- `docs/physics/selection-standard.md`: the implemented four-lepton selection;
- `docs/roadmap/next-stage.md`: the current forward-looking roadmap;
- `docs/briefings/progress-briefing.md`: a professor-facing progress narrative.

The two archived documents are handled as follows:

1. `codex-handoff-and-roadmap.md` no longer acts as a required entry point. Its
   current-status, constraints, and next-task information must be represented in
   `AGENTS.md` and `docs/roadmap/next-stage.md`. The full original remains in the
   archive with an archive notice.
2. `original-demo-spec.md` is the pre-implementation specification. Any still
   relevant high-level behavior must already be present in
   `docs/project/overview.md`; the original remains intact with an archive notice.

No active document is merged into the root `README.md`: this avoids turning the
quick-start page into another monolithic handoff document.

The completed Superpowers design and implementation records remain under
`docs/superpowers/`. They are traceability records rather than active user-facing
documentation and will not be merged.

## 6. Documentation index

Create `docs/README.md` with:

- a short reading order for users, Codex, and professor-facing review;
- a table of active documents and their single responsibility;
- a separate historical/development-record section;
- a warning that archive files are not current sources of truth;
- project-root-relative links to every listed document.

## 7. Reference updates

Update all project Markdown references to the new paths, including references in
historical Superpowers plans and specifications. At minimum this covers:

- `README.md` and `AGENTS.md` startup reading order;
- cross-references among overview, roadmap, briefing, physics, and archive files;
- references inside `docs/superpowers/plans/` and `docs/superpowers/specs/`;
- self-location and startup lists inside the archived handoff document.

References should use project-root-relative paths when describing command-line or
Codex workflows. Markdown navigation links should use paths relative to the
containing document.

After migration, searches for the old root paths must return no active-reference
matches. The move map in this organization design/plan is intentionally exempt,
because it documents the migration itself. Historical prose may mention an old
filename only when explicitly marked as history, never as a current location.

## 8. Cache cleanup

Delete only generated, reproducible clutter inside `higgs-xgboost-demo`:

- `.pytest_cache/`, including its generated `README.md`;
- `src/__pycache__/`;
- `scripts/__pycache__/`;
- `tests/__pycache__/`;
- every `.DS_Store` found inside the project.

Do not delete `.venv`, `.gitkeep` files, data, models, plots, JSON outputs, CSV
outputs, design records, or user-authored documents.

The existing `.gitignore` already ignores these caches and does not need a new
rule unless verification finds an uncovered cache pattern.

## 9. Safety and failure handling

Before moving files:

- record exact file paths, sizes, and hashes for every moved document;
- record file metadata for `data/raw`, `data/processed`, and `outputs`;
- ensure no destination exists and no move would overwrite another file.

After moving files:

- compare moved-document SHA-256 values before content edits;
- apply content merges and reference changes only after successful moves;
- stop if an expected source is missing or a destination unexpectedly exists;
- never use a broad recursive deletion target.

The parent Git repository has no commits and treats the demo as untracked, so no
commit, branch, or worktree will be created as part of this reorganization.

## 10. Verification

The organization is accepted when all of the following are true:

1. the target directory structure exists and old document locations do not;
2. `docs/README.md` provides working navigation to all active and archived docs;
3. no active Markdown reference points to an old location;
4. no Python cache, pytest cache, or `.DS_Store` remains inside the project after
   the final post-test cleanup;
5. `.venv`, ROOT files, processed CSV files, models, plots, and existing output
   artifacts have unchanged metadata;
6. Python source and tests compile;
7. the complete pytest suite still passes;
8. `python -m scripts.prepare_demo --help` still succeeds;
9. no real ROOT preprocessing, training, evaluation, or signal-window inspection
   occurs during verification.

Compilation and pytest may recreate Python or pytest caches. Therefore verification
runs first, followed by one final explicit cache cleanup and filesystem scan.
