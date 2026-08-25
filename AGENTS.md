# Repository Agent Guide

## Scope

These instructions apply to the entire repository. The maintained Python project
lives in `project/`. Before changing anything under that directory, read and
follow `project/AGENTS.md`; its more specific instructions take precedence.

The root-level notebook and Markdown files are historical/reference material.
Do not treat them as the current implementation unless a task explicitly targets
them.

## Start Here

For work on the maintained project, read these files in order:

1. `project/AGENTS.md`
2. `project/README.md`
3. `project/docs/project/overview.md`
4. `project/docs/roadmap/next-stage.md`

Run project commands from `project/`, where `src`, `scripts`, `config`, and
`tests` are importable as expected.

## Development Workflow

- Use the repository virtual environment when available:
  `project/.venv/bin/python` from the repository root, or `.venv/bin/python`
  from `project/`.
- Install dependencies with `python -m pip install -r requirements.txt` from
  `project/`.
- Run the full test suite with `python -m pytest -q` from `project/`.
- For a focused change, run the relevant test module first, then the full suite
  before claiming completion.
- Keep source code in `project/src/`, CLI entry points in `project/scripts/`,
  configuration in `project/config/`, and tests in `project/tests/`.
- Do not commit generated data, run outputs, models, plots, virtual environments,
  caches, or other ignored artifacts.

## Scientific Safety

- Preserve the feature, weighting, split, threshold-selection, and blinding
  constraints documented in `project/AGENTS.md`.
- Never use real data for supervised training or tune decisions on the held-out
  test set.
- Do not add `m4l`, identifiers, provenance fields, or weight columns to model
  features.
- Treat frozen runs and artifacts as immutable. New experiments must use a new
  configuration and a new run path.
- Do not open blinded real-data regions or relax predeclared AUC/KS criteria
  without explicit user authorization and an approved design.
- Describe results as an educational/technical demo, not as an ATLAS result,
  Higgs discovery, or physics measurement.

## Change Discipline

- Make the smallest change that satisfies the task and preserve unrelated user
  edits.
- Add or update tests for behavior changes.
- Update relevant documentation and configuration examples when interfaces or
  workflows change.
- Before reporting success, run checks appropriate to the change and state
  exactly what was verified.
