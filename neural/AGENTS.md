# Neural Project Agent Guide

## Scope and authority

These instructions apply to the whole `neural/` project. The repository root
`AGENTS.md` and `neural_adversarial_mlp_refactor_design.md` remain authoritative;
this file may narrow their rules but never relax them.

Run project commands from `neural/`. Use the Conda environment named `pytorch`.
`osx.yml` is the authoritative `osx-arm64` lock and `win.yml` is for Windows
development verification. Windows results are not exact substitutes for the
authoritative ARM64 run.

## Scientific safety

- The project is strictly MC-only. Do not read, hash, preprocess, score, plot,
  or otherwise inspect real data.
- Never use `m4l`, identifiers, provenance, split fields, or weight columns as
  classifier features. The v1 classifier uses only the protocol's fixed 15
  features.
- Signed `physical_weight` is for physical-yield reporting. Optimizer weights
  use the protocol-defined normalized absolute weight.
- Development may not read held-out test feature values. Test opening requires
  an eligible frozen development run and separate explicit user authorization.
- Do not relax AUC, KS, efficiency, candidate, epoch, architecture, or threshold
  rules after seeing results.
- `adversarial_mlp_protocol_debug.yaml` is the only diagnostic exception: a
  user may set `qualification.auc_minimum` and `qualification.ks_maximum`
  before starting a new run. All other fields remain sealed, the exact debug
  bytes/hash must be recorded, and debug runs may never open held-out test.
- Frozen and failed runs are immutable. Every run uses a new path and retains
  its audit evidence.
- Describe all output as an educational/technical demo, never an ATLAS result,
  Higgs discovery, or physics measurement.

## Package boundaries

- Runtime code lives in `src/` and must not import or call `xgboost/src`.
- CLI modules parse arguments and call application services; scientific
  calculations do not live in CLI or artifact-publication code.
- Protocol files own scientific rules. Run configuration owns only paths and
  resource settings.

## Stable process exit codes

| Code | Meaning |
|---:|---|
| 0 | Success or a declared normal scientific terminal state |
| 2 | Command-line usage error |
| 3 | Input, schema, hash, or protocol binding failure |
| 4 | Run-path or transaction failure |
| 5 | Qualification or test-opening refusal |
| 70 | Unexpected internal error |

## Verification

Run focused tests first, then:

```powershell
conda run -n pytorch python -m pip check
conda run -n pytorch python -m pytest -q
```

Do not claim authority-environment or full-data verification unless it was
actually performed on the locked ARM64 environment with the bound ROOT inputs.
