# Repository Agent Guide

## Scope and instruction precedence

These instructions apply to the whole repository. The maintained implementation
is `neural/`. Before changing anything under it, read and follow
`neural/AGENTS.md`; its more specific rules take precedence over this file.

`xgboost/` is deprecated, read-only historical material and is expected to be
removed later. Do not develop, refactor, run new experiments in, or add new
dependencies to it unless the user explicitly reauthorizes that work. Its local
`xgboost/AGENTS.md` remains relevant only when an explicitly requested task must
inspect or preserve the legacy implementation.

The root notebooks, historical Markdown files, frozen run descriptions, and
legacy XGBoost results are reference material. Do not treat them as the current
Neural implementation or as authority for a new scientific result.

## Current project

HiggsML Neural is an MC-only educational/technical workflow for
`H -> ZZ* -> 4l`. It contains:

- the historical fixed 15-feature adversarial MLP workflow;
- preprocessing, development-only training, qualification, and controlled test
  opening for the supported dataset contracts;
- an isolated `src.research` H4l workflow for protocol-bound studies, including
  the approved common `m4l` conditioning exception;
- immutable, hash-bound artifacts and run directories.

Never describe repository output as an ATLAS result, a Higgs discovery, or a
physics measurement.

## Start here

For maintained work, read the following files in order:

1. `AGENTS.md`
2. `neural/AGENTS.md`
3. `README.md`
4. `neural/README.md`
5. `neural/docs/sw-dev/README.md`
6. The task-specific protocol, design, runbook, or requirement document.

Useful task-specific entry points include:

- `neural/docs/sw-dev/architecture.md`
- `neural/docs/sw-dev/artifact-schema.md`
- `neural/docs/sw-dev/h4l-research-runbook.md`
- `neural/docs/research/current-research-status.md`
- `neural/docs/research/H4l-Research-Project.md`
- `neural/docs/research/inclusive-protocol.md`
- `neural/docs/research/test-opening-protocol.md`

Files under `neural/docs/1-Requirement/`, `neural/docs/3-Plan/`, and
`neural/docs/4-Reviews/` may be active planning or review artifacts. Read their
status and dependencies before treating a proposal as approved or implemented.

## Repository layout

- `scripts/init_data.py`: repository-level controlled MC downloader.
- `data/raw/`: downloaded source data; ignored and never committed.
- `neural/src/`: maintained runtime package.
- `neural/src/cli/`: CLI argument parsing and application entry points.
- `neural/src/domain/`: frozen scientific selections, kinematics, weights, and
  split rules.
- `neural/src/preprocessing/`: ROOT ingestion and partition publication.
- `neural/src/training/`: development, fitting, qualification, and test-opening
  logic.
- `neural/src/research/`: isolated protocol-bound H4l research implementation.
- `neural/src/artifacts/`: canonical serialization and immutable publication.
- `neural/config/`: dataset contracts, profiles, protocols, validation schemas,
  and resource configurations.
- `neural/scripts/`: cross-platform research workflow helpers.
- `neural/tests/`: maintained automated test suite.
- `neural/docs/`: requirements, research protocols, software design, runbooks,
  reviews, and thesis material.
- `neural/runs/`: generated runs; ignored, immutable after creation, and never
  committed.
- `xgboost/`: deprecated legacy implementation; do not extend it.

Runtime code in `neural/` must not import or call `xgboost/src`.

## Local environment

The confirmed Windows Conda installation is:

```text
Conda root:       D:\apps\anaconda3
Conda executable: D:\apps\anaconda3\Scripts\conda.exe
Neural env:       D:\apps\anaconda3\envs\pytorch
Environment name: pytorch
```

The project requires Python 3.12; `neural/environment.yml` currently pins
Python 3.12.13. Use the `pytorch` environment for all maintained project
commands. On PowerShell, prefer explicit commands that do not depend on shell
activation state:

```powershell
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python --version
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pip check
```

For a missing environment, create it from the repository root, then install the
package in editable mode:

```powershell
& 'D:\apps\anaconda3\Scripts\conda.exe' env create -f neural/environment.yml
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pip install --no-deps -e neural
```

Install `neural/requirements-research.txt` only when the requested research
workflow needs those additional dependencies. `neural/osx.yml` is the
authoritative native ARM64 lock; `neural/win.yml` supports Windows development
verification and does not substitute for ARM64 authority validation.

## Command and network conventions

- Run Neural package, CLI, test, and workflow commands from `neural/` unless a
  documented command explicitly starts at the repository root.
- Download controlled MC data from the repository root with
  `python scripts/init_data.py` and an explicit dataset when appropriate.
- Do not use a `webservice` abstraction. For authorized network access, make
  direct HTTP or HTTPS requests.
- All business CLIs require an explicit dataset contract:
  `atlas2020_4lep` or `atlas2025_exactly4lep`.
- The installed console entry points are `higgsml-preprocess`, `higgsml-train`,
  `higgsml-test`, and `higgsml-research`.
- The maintained H4l orchestration helpers are `scripts/h4l_prepare.py`,
  `scripts/h4l_g1.py`, and `scripts/h4l_run.py`. Follow the runbook rather than
  inventing a new execution order.

## Code discovery

Use the codebase knowledge graph before filesystem text search for code
discovery:

1. `search_graph` for functions, classes, routes, and variables.
2. `trace_path` for callers, callees, dependencies, and data flow.
3. `get_code_snippet` for a specific qualified symbol.
4. `query_graph` for complex structural questions.
5. `get_architecture` for a high-level overview.
6. `search_code` for graph-augmented code text search.

If the repository is not indexed, run `index_repository` first. Fall back to
`rg` or file reads for string literals, error messages, configuration,
documentation, shell scripts, and cases where graph results are insufficient.

## Scientific safety

- Neural work is strictly MC-only. Do not read, hash, preprocess, score, plot,
  or otherwise inspect real data.
- Never use real data for supervised training or use its contents to make model,
  threshold, protocol, or analysis decisions.
- For the historical classifier, never add `m4l`, identifiers, provenance,
  split fields, or weight columns to the fixed 15 model features.
- The only `m4l` feature exception is the separately approved, versioned
  `src.research` H4l protocol, where it may be an explicit common mass
  condition. This exception does not alter historical classifier rules or
  test-opening gates.
- Signed `physical_weight` is for physical-yield reporting. Optimizer weights
  use the protocol-defined normalized absolute weight.
- Keep physical event groups together across split and fold assignments.
- Development code must not read held-out test feature values. Do not use test
  results to tune candidates, hyperparameters, thresholds, bins, mappings, or
  selection rules.
- Do not relax predeclared AUC, KS, efficiency, candidate, epoch, architecture,
  or threshold criteria after observing results.
- Research assessment access requires the protocol-defined frozen state and
  cannot be used for model or analysis selection.
- Preserve dataset identity, resource seals, protocol hashes, checkpoint
  binding, and artifact lineage.
- Frozen, failed, diagnostic, and completed runs are immutable. Every new
  execution uses a new run path unless a documented, explicitly requested clean
  operation safely removes the exact generated target.
- Synthetic tests, Windows verification, full-data scientific validation, and
  native ARM64 authority validation are distinct evidence states. Report only
  the states actually verified.

## Development workflow

Before editing:

1. Confirm the task targets the maintained Neural implementation.
2. Read `neural/AGENTS.md` and the relevant protocol/design documents.
3. Run `git status --short` and preserve unrelated or untracked user work.
4. Establish a focused test baseline for the affected behavior.
5. Check whether existing run or data artifacts are available; never infer or
   fabricate missing scientific outputs.

While editing:

- Make the smallest coherent change that satisfies the task.
- Keep scientific calculations in domain, training, preprocessing, or research
  services rather than CLI or artifact-publication code.
- Protocol files own scientific rules. Run configuration owns paths and
  resource settings.
- Add or update tests for behavior changes.
- Update documentation, schemas, and configuration examples when contracts or
  workflows change.
- Preserve stable process exit codes documented in `neural/AGENTS.md`.
- Never overwrite user changes, generated evidence, or frozen artifacts.

## Verification

Run a focused test module first, then the full maintained suite from `neural/`:

```powershell
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pytest -q tests/<focused_test>.py
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pip check
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pytest -q
```

For documentation-only changes, verify links, paths, examples, and the final
diff; a full scientific run is not required. Before reporting success, state
exactly which checks ran and distinguish software tests from scientific or
authority-environment validation.

## Data, artifacts, and Git discipline

- Do not commit raw data, processed data, models, plots, run outputs, caches,
  build products, virtual environments, Conda environments, or package metadata.
- Do not copy an environment between machines; recreate it from the appropriate
  environment definition or lock.
- Verify controlled data with the repository's dataset contracts and receipts;
  do not identify samples from filenames alone.
- Keep generated outputs under their documented run roots and preserve audit
  evidence for both successful and unsuccessful terminal states.
- Root notebooks and historical files may inform context but must not bypass the
  maintained protocols, gates, or package boundaries.

## Deprecated XGBoost policy

XGBoost is no longer an active implementation in this repository. Until its
separate removal is explicitly requested:

- preserve `xgboost/` and its historical artifacts as-is;
- do not run legacy training, evaluation, or real-data commands;
- do not migrate new Neural behavior into XGBoost;
- do not use XGBoost baselines as current acceptance criteria;
- keep any unavoidable compatibility change minimal and clearly labeled as
  legacy maintenance.
