# Sprint M1-01 Code Review Report

**Reviewer:** opencode-go/kimi-k2.7-code  
**Date:** 2026-09-01  
**Change set:** Sprint M1-01 artifacts for FR-001 / XGBoost behavior-equivalent refactor  
**Source of truth:**

- `docs/superpowers/specs/2026-09-01-xgboost-refactor-design.md`
- `docs/1-Requirement/FR-001-angular19-xgboost-refactor.md`
- `docs/3-Plan/sprint-m1-01.md`
- `AGENTS.md`

## Executive Summary

The M1-01 change set successfully establishes the new package skeleton:
`pyproject.toml` with the two approved console scripts, versioned protocol YAMLs, a
strict YAML loader, CLI argument parsers, and a no-clobber run transaction. The
focused M1-01 test suite passes. However, the protocol loaders are not yet fully
fail-closed for unknown nested fields or incorrect nested types, and the
characterization/golden test baseline is narrower than the sprint requires.

## Scope Reviewed

- `pyproject.toml`
- `config/preprocessing_protocol_v1.yaml`
- `config/preprocessing_run.example.yaml`
- `config/xgboost_protocol_v1.yaml`
- `src/config.py`
- `src/cli/__init__.py`
- `src/cli/preprocess.py`
- `src/cli/xgboost.py`
- `src/artifacts/__init__.py`
- `src/artifacts/manifest.py`
- `src/artifacts/transaction.py`
- `tests/golden/test_refactor_characterization.py`
- `tests/unit/test_refactor_config.py`
- `tests/unit/test_refactor_artifacts.py`
- `tests/integration/test_refactor_cli.py`
- `AGENTS.md`
- `docs/roadmap/next-stage.md`

`docs/1-Requirement/FR-001-angular19-xgboost-refactor.md` and
`docs/3-Plan/sprint-m1-01.md` were used as source-of-truth specifications and were
not reviewed as implementation artifacts.

## Verification Performed

1. Read all source-of-truth specifications.
2. Read every file in the change set.
3. Ran the focused M1-01 test suite:

   ```powershell
   .venv\Scripts\python -m pytest -q tests/golden/test_refactor_characterization.py tests/unit/test_refactor_config.py tests/unit/test_refactor_artifacts.py tests/integration/test_refactor_cli.py
   ```

   Result: `16 passed in 2.24s`

4. Ran CLI help smoke tests:
   - `python -m src.cli.preprocess --help` → exit 0
   - `python -m src.cli.xgboost --help` → exit 0
5. Ran the full project pytest:
   - Result: `211 failed, 737 passed, 1 skipped`
   - All failures are in pre-existing historical scripts/tests on Windows
     (e.g., `os.O_DIRECTORY` is not available, symlink creation requires
     elevation). They are unrelated to the M1-01 change set.

## Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| High | Requirement | `src/config.py` `load_preprocessing_protocol` (lines 101–118) | Unknown nested keys inside `samples`, `selection`, `features`, `splitting`, and `forbidden_features` are not rejected. Only top-level unknown keys are checked. | `_reject_unknown(features, {"base14", "angular5", "model"}, ...)` is called, but no `_reject_unknown` is applied to `samples`, `selection`, or `splitting`. | Add per-section allowed-key sets and reject unknown nested keys, or validate with a schema. Document the allowed nested structure explicitly. |
| High | Correctness | `src/config.py` `load_xgboost_protocol` (lines 143–177) | Unknown nested keys inside `candidate`, `common`, `working_points`, and `qualification` are not rejected; expected keys are not enforced; value types are not validated. | The function iterates numeric values with `_finite_number` but never calls `_reject_unknown` on the four nested mappings. | Reject unknown keys in each nested mapping, enforce exact expected keys, and validate types (e.g., `n_estimators`/`folds` are `int`, `tree_method` is `str`). |
| High | Correctness | `src/config.py` `load_preprocessing_protocol` (lines 101–118) | Structural invariants of the preprocessing protocol are not validated: sample channel numbers, splitting fractions summing to 1.0, non-negative fractions, and the forbidden-feature list. | No validation of `samples.higgs.channel_numbers`, `samples.zz.channel_numbers`, `splitting.*_fraction`, or `forbidden_features`. | Validate channel numbers equal `[345060]` and `[363490]`; validate fractions sum to 1.0 and are non-negative; assert `forbidden_features` contains at least the design-mandated fields. |
| High | Test | `tests/golden/test_refactor_characterization.py` | The characterization baseline is incomplete. Sprint M1-01 §5.1 requires coverage of selection/cutflow, SFOS/Z1/Z2/4-momentum, Base14/Angular5 actual values, identity/split algorithm, working points, metrics, qualification, and model save/load/predict. | The file only tests feature-name contracts, default config values, and weight/fold/final-tree rules. No tests exist for cutflow counts, Angular5 math, model serialization, or actual AUC/KS/working-point computation. | Add golden tests that exercise the existing production code paths and capture authoritative counts, feature values, working points, and model round-trip behavior before M1-02/M1-03 replace them. |
| Medium | Test | `tests/unit/test_refactor_config.py` | Fail-closed behavior is only tested for the run config; the two checked-in protocol files are not exercised for unknown keys, wrong types, or non-finite values. | The parametrized cases cover `load_preprocessing_run_config` only. | Add parametrized fail-closed cases for `load_preprocessing_protocol` and `load_xgboost_protocol` covering unknown nested keys, wrong types, missing required sections, and non-finite numeric values. |
| Medium | Test | `tests/integration/test_refactor_cli.py` | Only `--help` success is tested. Error paths, unknown arguments, and the installed console scripts are not covered. | The test has one parametrized case asserting `returncode == 0` for `python -m src.cli.* --help`. | Add tests for missing required arguments (non-zero exit), unknown arguments, and the installed entry points `higgsml-preprocess` / `higgsml-xgboost` after `pip install -e .`. |
| Medium | Test | `tests/unit/test_refactor_artifacts.py` | Artifact-transaction edge cases are not covered: concurrent claim races, symlink rejection, writing after manifest publication, and failure-receipt no-clobber. | Existing tests cover basic claim, failure, and unsafe/reserved paths. | Add tests for symlinked `run_dir`/`runs_root` rejection (or skip on Windows with a note), concurrent `RunTransaction` claims, and attempting `write_bytes` after `publish_manifest`. |
| Medium | Correctness | `src/artifacts/transaction.py` `RunTransaction.__enter__` (lines 20–24) | Directory claim is not atomic across processes. `mkdir()` alone can race; the design requires atomic output claiming before any input is read. | `self.run_dir.mkdir()` is called without an OS-level atomic lock or exclusive open. | Implement an atomic claim mechanism (e.g., `os.mkdir` exception-handling loop or lock file) and add a concurrency test. At minimum, document the limitation as a known M1-01 risk. |
| Medium | Security | `src/artifacts/transaction.py` `_validate_target` (lines 69–77) | `resolve(strict=True)` follows symlinks in the parent path, potentially allowing escape if an ancestor of `runs_root` is a symlink, even though `runs_root` itself is checked for being a symlink. | `root = self.runs_root.resolve(strict=True)` and `target_parent = self.run_dir.parent.resolve(strict=True)` use `resolve`, which follows symlinks. | Validate that every path component from the filesystem root to `runs_root` is not a symlink, or document and test the accepted Windows/POSIX symlink policy explicitly. |
| Medium | Correctness | `src/config.py` `load_xgboost_protocol` (lines 143–177) | Working-point ordering and qualification threshold ranges are not validated. A malformed protocol could reverse loose/medium/tight or set AUC/KS thresholds outside `[0,1]`. | No check that `working_points` values are strictly decreasing or that `minimum_weighted_oof_auc`/`maximum_background_ks` are in `[0,1]`. | Enforce loose > medium > tight and validate that AUC/KS thresholds lie in `[0,1]`. |
| Low | Clarity | `src/cli/preprocess.py` `main` (line 20) and `src/cli/xgboost.py` `main` (line 26) | Return type annotation `-> int` is inconsistent with raising `SystemExit(str)`. | Functions are annotated to return `int` but always raise `SystemExit`. | Either return an integer and let the caller raise, or change the annotation to `NoReturn`. |
| Low | Maintainability | `pyproject.toml` `[tool.setuptools.packages.find]` (lines 31–34) | `include = ["src*"]` relies on fnmatch and may inadvertently pick up unrelated packages if any are added later. | Pattern is functional but non-idiomatic. | Use `packages = ["src"]` or `find = {where = ["."], include = ["src", "src.*"]}` for clearer intent. |
| Low | Maintainability | `tests/golden/test_refactor_characterization.py` (lines 11–17) | Golden tests depend on modules (`src.experiment_runner`, `src.full_training_policy`) that the design explicitly schedules for deletion in M1-06. | Imports `_final_tree_count`, `assign_development_folds`, and `class_balanced_training_weights` from historical modules. | Before M1-06 deletion, migrate these behavioral contracts into the new domain/tests or snapshot their outputs so the golden baseline survives the historical cleanup. |
| Low | Test | `tests/unit/test_refactor_config.py` `test_checked_in_protocols_are_strict_and_complete` (lines 15–34) | Does not assert all `common` training parameters or `working_points` values. | Only `training.common["folds"] == 5` is checked; `n_estimators`, `early_stopping_rounds`, `tree_method`, etc., and working points are not asserted. | Assert the full `common` mapping and `working_points` mapping against the design values. |
| Low | Consistency | `config/preprocessing_run.example.yaml` (line 3) | Example ZZ ROOT path is `data/raw/zz_363490.root`, while `AGENTS.md` refers to `data/raw/zz.root`. | File uses `zz_363490.root`; `AGENTS.md` cross-device data note lists `zz.root`. | Keep the example internally consistent with `config/dsid363490.yaml` (which uses `zz_363490.root`) and add a comment clarifying that the example path matches the DSID-specific config, not necessarily the generic `AGENTS.md` copy destination. |
| Info | Risk | Full pytest suite (historical tests) | 211 pre-existing tests fail on Windows due to POSIX-only APIs (`os.O_DIRECTORY`, symlink creation), unrelated to M1-01. | Failures are in `tests/test_angular5_enrichment*.py`, `tests/test_train_full_mc_script.py`, `tests/test_full_training_run.py`, etc. | Track these as Windows-portability debt for the historical execution surface; do not let them block M1-01, but ensure M1-06 cleanup removes the offending historical code. |

## Conclusion

M1-01 delivers the required skeleton, the focused tests pass, and no existing
scientific behavior was changed. The main blockers before starting M1-02 are:

1. Make the protocol loaders fully fail-closed for unknown nested keys and
   incorrect nested types/values.
2. Expand the characterization/golden baseline to cover the selection,
   reconstruction, feature math, and model serialization contracts required by
   the design.
3. Strengthen artifact-transaction tests and clarify the atomic-claim policy.

No frozen runs, models, predictions, plots, manifests, or real data were touched
by this change set.
