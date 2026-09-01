# Sprint M1-01 Code Review Report

- **Reviewer:** opencode-go / kimi-k2.7-code
- **Review date:** 2026-09-01
- **Review type:** Code review
- **Implementation scope:**
  - `neural/pyproject.toml`
  - `neural/environment.yml`
  - `neural/AGENTS.md`
  - `neural/README.md`
  - `neural/src/config.py`
  - `neural/src/cli/preprocess.py`
  - `neural/src/cli/train.py`
  - `neural/src/artifacts/transaction.py`
  - `neural/tests/unit/test_package_contract.py`
  - `neural/tests/unit/test_transaction.py`
  - `neural/tests/integration/test_cli_help.py`
  - Directory skeleton and `.gitkeep` files
  - Existing `neural/osx.yml` and `neural/win.yml` (environment-contract consistency only)
- **Requirements / sources of truth:**
  - `neural/docs/FR-001-adversarial-mlp-refactor.md`
  - `neural/docs/sprint-m1-01.md`
  - `docs/4-Reviews/sprint-m1-01-review-confirm.md`
  - `AGENTS.md` (repository root)
  - `neural_adversarial_mlp_refactor_design.md` (repository root)

## Executive Summary

The M1-01 implementation delivers the engineering skeleton agreed in the review-confirm decision table: a standalone installable package, the `pytorch` Conda environment contract, two console entry points, a stable exit-code table, a non-overwritable run transaction, and the directory tree needed for later sprints. All 8 unit and integration tests pass in the `pytorch` environment, `pip check` is clean, and both CLI `--help` invocations return success.

The implementation respects the M1-01 scope boundary: no scientific preprocessing, no model code, no manifest/SHA-256/gzip canonical hashing, and no test-opening logic are present, which is correct because those belong to M1-02 through M1-06.

The review finds no Critical or High defects. The actionable issues are concentrated in the run-transaction edge cases and test coverage of exit-code/abort paths. None of them block M1-01 acceptance, but they should be tightened before the transaction API is extended in later sprints.

## Review Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| Medium | Correctness / Atomicity | `neural/src/artifacts/transaction.py` `_publish()` and `__exit__` | `_publish()` checks target existence before `Path.replace()`, creating a TOCTOU window. More importantly, if `_publish()` raises `RunPathError` while handling an exception in `__exit__`, the original failure cause is masked. | `_publish()` lines 65–71 pre-checks `self.run_dir.exists()`; `__exit__` lines 49–63 calls `_publish()` after writing `failure.json` without guarding against a secondary exception. | Use `os.replace()` directly and catch `FileExistsError`/`OSError` inside `_publish()`; in `__exit__`, wrap the publish attempt so the original exception is preserved (e.g., `raise ... from original_exc` or chain context). |
| Medium | Tests | `neural/tests/unit/test_transaction.py` | `RunTransaction.abort_without_receipt()` has no unit test coverage. | Method defined at `transaction.py` lines 73–77; no test invokes it. | Add a test that calls `abort_without_receipt()` and asserts the staging directory is removed and a later `_publish()` / context exit cannot publish to the target. |
| Medium | Exit-code behavior | `neural/tests/integration/test_cli_help.py` | Tests only verify `--help` returns 0; the `AGENTS.md` exit-code contract for usage errors (code 2) is not exercised. | Test parametrizes `--help`; parser currently accepts no positional args, so argparse would raise `SystemExit(2)` on unknown args, but this path is untested. | Add a parametrized test passing an unknown argument and asserting `returncode == 2`, or assert that argparse emits the expected usage error. |
| Low | Path safety | `neural/src/artifacts/transaction.py` `_validate_target()` | Validation relies on `os.path.commonpath` after `Path.resolve(strict=False)`. Symlink components in `allowed_root` that do not yet exist may not be fully resolved, and case-insensitive filesystem edge cases are not explicitly tested. | `_validate_target()` lines 27–37. | Add tests for symlink escape and case-normalization on the target platform; if `strict=False` resolution is intentional, document the assumption that `allowed_root` is a real, canonical directory path. |
| Low | Packaging | `neural/pyproject.toml` | `setuptools` installs `src` as a top-level namespace package, which conflicts with any other `src` package in the same environment. | `top_level.txt` lists `src`; `[tool.setuptools.packages.find] include = ["src*"]` (lines 29–31). | No rename is required for M1-01 because the design explicitly chose `src.cli.*`, but add an integration smoke test that imports the installed package and verify no collision in the locked `pytorch` environment. |
| Low | Completeness | `neural/pyproject.toml` and `neural/environment.yml` | `conda-lock` is part of the design §11 baseline but is not declared as a dependency in either file. | Design §11 lists `conda-lock`; `environment.yml` only includes runtime/test deps plus `pip` for `mplhep`. | Either add `conda-lock` under a dev/test section or keep the current base-environment installation convention and explicitly state in `neural/README.md` that `conda-lock` belongs to `base`. |
| Low | Tests | `neural/tests/unit/test_package_contract.py` `test_runtime_source_does_not_import_xgboost()` | The check is purely static AST-based; dynamic imports such as `importlib.import_module("xgboost")` would not be caught. | Test walks `ast.Import`/`ast.ImportFrom` only (lines 24–32). | Add a grep or runtime import guard test that also flags `importlib` dynamic imports of `xgboost` in `src/`. |
| Info | Scope compliance | `neural/src/cli/preprocess.py`, `neural/src/cli/train.py`, directory skeleton | M1-02 through M1-06 functionality is correctly absent; the CLI parsers are intentionally empty beyond `--help`. | `preprocess.py` and `train.py` define only `build_parser()`/`main()` returning 0; no ROOT/PyTorch/model code exists. | Maintain this boundary; add subcommands and scientific modules only in their assigned sprints. |
| Info | Positive | `neural/src/config.py`, `neural/AGENTS.md` | Exit codes are centralized in an `IntEnum` and documented with stable meanings. | `ExitCode` enum lines 6–12; `AGENTS.md` exit-code table lines 40–49. | Keep the enum as the single source of truth for CLI return values. |
| Info | Positive | `neural/pyproject.toml`, `neural/tests/unit/test_package_contract.py`, `neural/tests/integration/test_cli_help.py` | Console entry points match the design exactly and are tested. | `project.scripts` lists `higgsml-preprocess` → `src.cli.preprocess:main` and `higgsml-train` → `src.cli.train:main`; tests verify exact set and `--help` output. | Preserve the exact two-entry-point contract in future sprints. |
| Info | Positive | `neural/environment.yml`, `neural/osx.yml`, `neural/win.yml` | Direct dependencies in `environment.yml` match the design baseline and the existing platform locks; `pip check` passes. | `environment.yml` pins the same direct versions as design §11; `conda run -n pytorch python -m pip check` reports no broken requirements. | Before regenerating locks, verify `environment.yml` direct deps still match design §11. |
| Info | Positive | Full test suite | All 8 unit and integration tests pass in the locked `pytorch` environment. | `conda run -n pytorch python -m pytest -q` reports `8 passed in 0.31s`. | Keep the focused-first-then-full-suite workflow documented in `neural/AGENTS.md`. |

## Detailed Observations

### Transaction correctness and atomicity

`RunTransaction` correctly enforces the three core invariants required by M1-01: the target must be inside `allowed_root`, the target must not already exist, and publishing must be atomic-ish via a UUID-staged temporary directory. The unit tests cover the happy path, the existing-target rejection, the outside-root rejection, and the failure-receipt publication.

The remaining weakness is the `_publish()` implementation. It checks `self.run_dir.exists()` and then calls `self.path.replace(self.run_dir)`. On POSIX the rename is atomic when the target does not exist, but the pre-check opens a race window and, on Windows, `Path.replace()` cannot replace a non-empty directory so a concurrent directory creation would surface as an `OSError` rather than the intended `RunPathError`. The more consequential defect is exception masking: when the context manager body raises, `__exit__` writes `failure.json` and then calls `_publish()`. If `_publish()` itself raises (race, permissions, disk full), the original scientific/IO exception is lost. Future sprints should guard the publish call and chain exceptions.

### CLI and exit-code behavior

Both CLI modules delegate argument parsing to `argparse` and return `ExitCode.SUCCESS`. Because the parsers currently define no positional/required arguments, calling them with no arguments also returns 0. `argparse` natively emits `SystemExit(2)` for unknown arguments, satisfying the `AGENTS.md` code-2 contract without extra code. However, that path is not tested. A single negative test would lock the contract in place.

### Packaging and environment

`pyproject.toml` correctly declares only the two required console scripts and pins the same direct dependency versions as `environment.yml`. The `requires-python = ">=3.12,<3.13"` matches the Conda environment's Python 3.12.13. The package installs `src` as the top-level namespace, which is exactly what the design §5 and §6 prescribe; the only risk is a future collision with another `src` package, so a smoke test is sufficient mitigation for now.

The `environment.yml` omits `conda-lock`. This is consistent with the README instruction to install `conda-lock` into the `base` environment, but it is inconsistent with the design §11 baseline list. This is minor and can be resolved with a documentation clarification rather than a dependency change.

### Requirement compliance

The implementation satisfies the M1-01 in-scope requirements from `sprint-m1-01.md` §3 and the review-confirm decision table:

- `pytorch` environment name is used everywhere (decision 1).
- `environment.yml`, `osx.yml`, and `win.yml` are present and consistent (decisions 2, 3, 5, 8).
- R6 coverage is limited to allowed-root validation, non-overwritable runs, atomic publish, and failure receipts; manifest/SHA-256/gzip canonical hashing are deferred (decision 4).
- `neural/AGENTS.md` captures MC-only, forbidden features, frozen runs, and evidence boundaries (decisions 6, 15).
- README preserves the current `pytorch` + dual-lock contract (decision 7).
- Lock-file `YOURENV` header is not hand-edited (decision 9).
- Full directory skeleton is created without pre-building future modules (decision 12).
- Stable exit-code table is defined in `neural/AGENTS.md` and implemented in `src/config.py` (decision 13).

## Verification Performed

- `conda run -n pytorch python -m pip check` → `No broken requirements found.`
- `conda run -n pytorch python -m pytest -q` → `8 passed in 0.31s`
- `conda run -n pytorch higgsml-preprocess --help` → exit 0, usage header present
- `conda run -n pytorch higgsml-train --help` → exit 0, usage header present
- Static inspection of `src/**/*.py` for `xgboost` imports → none found

## Conclusion

The Sprint M1-01 implementation is acceptable. It meets the agreed engineering-skeleton scope, passes all tests, installs cleanly, and does not leak M1-02 through M1-06 functionality. The Medium findings (transaction exception masking, missing abort test, missing exit-code-2 test) should be addressed in the next sprint before the transaction API is exercised by real preprocessing and training runs. No source files were modified in the preparation of this review.
