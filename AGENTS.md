# Repository Agent Guide

## Project scope

This repository maintains one MC-only educational and technical workflow for
`H -> ZZ* -> 4l`. The active package is `src/higgsml`; legacy15 preprocessing,
training, qualification, final-fit, test-opening, and XGBoost implementations
have been removed. Do not reintroduce them unless the user explicitly changes
the project scope.

Never describe repository output as an ATLAS result, a Higgs discovery, or a
physics measurement.

## Start here

Read `README.md`, `docs/README.md`, and the task-specific method, protocol, or
runbook before changing scientific behavior. The main entry points are:

- `docs/research-design.md`
- `docs/implementation-and-reproduction.md`
- `docs/methods-and-evaluation.md`
- `docs/results-and-limitations.md`
- `config/protocols/h4l_protocol.json`

## Repository layout

- `src/higgsml/physics/`: selections, reconstruction, kinematics, weights, and splits.
- `src/higgsml/modeling/`: representations, discriminants, calibration, and matrix elements.
- `src/higgsml/inference/`: templates, likelihood inference, diagnostics, stress tests, and reporting.
- `src/higgsml/sample_efficiency/`: registered sample-efficiency study.
- `config/`: datasets, profiles, protocols, schemas, and examples.
- `scripts/`: controlled download and H4l workflow helpers.
- `tests/`: unit, workflow, and synthetic scientific-contract tests.
- `docs/`: paper-relevant methods, reproducibility, and validation documentation.
- `paper/`: manuscript source.
- `data/raw/` and `runs/`: ignored local inputs and immutable generated evidence.

## Environment and commands

Use Python 3.12 and the `pytorch` Conda environment. Run commands from the
repository root:

```powershell
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pip install --no-deps -e .
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pip check
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pytest -q
```

The installed console entry point is `higgsml`. The orchestration helpers are
`scripts/h4l_prepare.py`, `scripts/h4l_check.py`, `scripts/h4l_run.py`, and the
sample-efficiency scripts. Do not use a webservice abstraction; authorized
network access must use direct HTTP or HTTPS requests.

## Scientific safety

- Process controlled MC only; never inspect, hash, preprocess, score, or plot real data.
- `m4l` may be used only as explicitly defined by the versioned H4l protocol.
- Signed `physical_weight` is for physical yields; optimizer weights follow the protocol.
- Keep physical event groups together across split and fold assignments.
- Do not inspect assessment values before the protocol-defined frozen state.
- Do not tune candidates, thresholds, bins, mappings, or protocols after assessment.
- Preserve dataset identity, hashes, protocol seals, checkpoint bindings, and lineage.
- Never overwrite a completed, failed, diagnostic, or otherwise published run.
- Distinguish software tests, synthetic validation, full-MC validation, and native ARM64 authority validation.

## Change discipline

Before editing, inspect `git status --short` and preserve unrelated or untracked
user work. Keep scientific rules in protocols and domain services, not CLI code.
Update tests, schemas, examples, and documentation when a contract changes.
Generated data, models, plots, runs, caches, build outputs, environments, and
package metadata must not be committed.

Use the codebase knowledge graph for code discovery when its tools are
available; otherwise use `rg`. Run focused tests before the full suite and
report exactly which evidence levels were and were not verified.
