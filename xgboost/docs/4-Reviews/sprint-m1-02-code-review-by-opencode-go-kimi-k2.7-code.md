# Sprint M1-02 Code Review Report

- **Reviewer:** `opencode-go/kimi-k2.7-code`
- **Review type:** Code review
- **Review date:** 2026-09-02
- **Worktree / branch:** `D:\code\HiggsML-worktrees\xgboost-refactor` / `codex/xgboost-refactor`
- **Target change set:**
  - Tracked modifications: `src/angular5.py`, `src/artifacts/transaction.py`, `src/cli/preprocess.py`, `src/features.py`, `src/input_profiles.py`, `src/pairing.py`, `src/reconstruction.py`, `src/selection.py`, `src/split.py`, `src/weights.py`
  - Untracked implementation: `src/domain/`, `src/preprocessing/`
  - Untracked tests: `tests/unit/test_refactor_domain.py`, `tests/unit/test_refactor_preprocessing.py`, `tests/golden/test_refactor_preprocess_golden.py`, `tests/integration/test_refactor_preprocess_cli.py`
- **Governing sources:**
  - `xgboost/AGENTS.md`
  - `xgboost/docs/1-Requirement/FR-001-angular19-xgboost-refactor.md`
  - `xgboost/docs/superpowers/specs/2026-09-01-xgboost-refactor-design.md`
  - `xgboost/docs/3-Plan/sprint-m1-02.md`
  - `xgboost/docs/4-Reviews/sprint-m1-02-review-confirm.md`

## Verdict

**Pass with required actions.** No Critical or High scientific-correctness findings. The implementation correctly migrates the frozen Base14 + Angular5 domain, builds an MC-only preprocessing pipeline, physically separates `development` and `test`, binds inputs with stat/SHA-256, and keeps the full-suite failure set unchanged relative to the M1-01 baseline. All document-review findings from the prior review cycle have been addressed in code or tests.

The remaining issues are boundary/audit, test-coverage, and M1-05 deletion-readiness concerns rated Medium and Low. None change selection, weights, split, feature math, or any frozen scientific parameter.

## 1. Scope and method

Checks performed:

- Read all governing requirements and the approved Sprint M1-02 plan.
- Inspected `git status --short` and `git diff --stat` to identify tracked vs. untracked changes.
- Read every new/ changed source file under `src/domain/`, `src/preprocessing/`, `src/cli/preprocess.py`, `src/artifacts/transaction.py`, and the compatibility alias modules.
- Read the new unit / golden / integration tests.
- Ran the focused M1-02 test suite and the full project test suite.
- Verified the output schema, manifest fields, CLI surface, and import boundaries against FR-001 and the approved design.
- Cross-checked the prior document-review findings (Kimi H1–H3, M1–M3; GLM H-1–H-2, M-1–M-4, L-1–L-3) against the implemented code.

Repository facts verified:

- Current HEAD: `409a728` (M1-01 baseline commit).
- M1-02 source files are currently untracked.
- Full-suite baseline after M1-01: `776 passed, 211 failed, 2 skipped`.
- Full-suite after M1-02 implementation: `791 passed, 211 failed, 3 skipped` — same 211 historical failures, 15 new passes and 1 new skip from M1-02 tests.
- No authoritative ROOT files or frozen runs are present in the worktree; no real data was read.

## 2. Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| Medium | Boundary / Correctness | `src/artifacts/transaction.py:102-108`; `src/preprocessing/application.py:123` | Run directory parent is not validated against the project `runs/` root. `RunTransaction` only checks that `run_dir` is a direct child of `runs_root`, but `runs_root` is passed as `run_dir.parent`, so any existing directory can serve as the root. This deviates from design §11: "run 路径必须全新，且位于允许的 `runs/` 根下". | `application.py:123` passes `runs_root=destination.parent`; `transaction.py:106-108` compares resolved parent to the supplied `runs_root`. | Add an allowed-runs-root check (defaulting to the project `runs/` directory) and reject `--run-dir` values whose resolved parent is not that root, while preserving the existing path-escape and symlink checks. |
| Medium | Audit / Reproducibility | `src/preprocessing/application.py:45-65` | Git dirty flag excludes untracked source files. `_git_identity` uses `git status --porcelain --untracked-files=no`. Because all M1-02 implementation files are currently untracked, the manifest will record `tracked_worktree_dirty: false` even though the executing code differs from the committed HEAD. The code SHA-256 does capture the new files, but the git-dirty semantics are misleading. | `application.py:54-62` strips untracked files from the dirty check. | Either remove `--untracked-files=no` so untracked source changes are reported as dirty, or document that `code.sha256` is the authoritative code identity and `tracked_worktree_dirty` reflects only tracked modifications. |
| Medium | Test Coverage / Equivalence | `tests/golden/test_refactor_preprocess_golden.py` | Golden test only covers the Higgs sample with event-derived normalization. It does not exercise the ZZ `official_metadata` normalization-override path, which is the production configuration for DSID 363490. | The test builds legacy and migrated samples using `protocol.raw["samples"]["higgs"]` and `sample_name="higgs"`; no second case for `zz`. | Add a second golden comparison for the ZZ sample with `official_metadata` normalization, asserting equivalent `physical_weight`, `train_weight`, and cutflow. |
| Medium | Robustness / Correctness | `src/preprocessing/pipeline.py:127-128` | If `build_angular5` raises on a selected event (e.g., pathological geometry causing a zero-norm axis), the exception aborts the entire run instead of dropping the event. | `prepare_mc_sample` calls `row.update(build_angular5(result.candidate))` without a guard; `domain/angular5.py` raises `ValueError` on non-finite or zero-norm vectors. | Define and test the policy: either (a) wrap the Angular5 computation and continue if it fails, treating finiteness as an implicit selection criterion, or (b) document that Angular5 finiteness is a hard run-level requirement and add a test for the failure path. |
| Low | Completeness | `src/preprocessing/application.py:88-101` | Software-environment manifest omits packages used by the reader. `_software_versions` records `numpy`, `pandas`, `pyyaml`, and `uproot`, but `awkward` and `vector` are also used during ROOT reading and event construction. | `application.py:89-94` lists only four distributions. | Add `awkward` and `vector` (and any other runtime dependencies not already captured) to the software-versions payload. |
| Low | Correctness / Security | `src/preprocessing/application.py:128-135` | Input revalidation happens only after the entire dataset is read. A replacement that occurs during chunked reading could corrupt parsed events before the post-read `verify_mc_input` detects the change. | `build_preprocessed_dataset` is called before `verify_mc_input`; design §8.1 only requires before/after verification. | Document this as an accepted threat-model limitation, or implement per-chunk revalidation for high-assurance runs. The current before/after model satisfies the approved design. |
| Low | Clarity / Schema | `src/preprocessing/application.py:192` | The preprocess manifest includes `test_opened: false`, a field whose semantics belong to the development-run lifecycle rather than an MC-preprocessing run. | `manifest` dictionary contains `"test_opened": False`. | Remove `test_opened` from the preprocessing manifest, or rename it (e.g., `test_partition_published`) to avoid confusion with the `higgsml-xgboost open-test` claim mechanism. |
| Low | Completeness | `src/preprocessing/application.py:68-85` | Code-identity hash omits package initialization files. `_code_sha256` hashes `src/config.py`, artifact/CLI files, and all `.py` files under `src/domain` and `src/preprocessing`, but not `src/__init__.py` or `src/cli/__init__.py`. | `application.py:70-77` builds the source list. | Include `src/__init__.py` and `src/cli/__init__.py` in the code-identity hash so that package-structure changes are reflected in the manifest. |
| Low | Consistency | `src/domain/features.py:33-45`; `src/config.py:16-25` | The domain-level and protocol-level forbidden-feature sets are inconsistent. `domain/features.py` forbids `source_file` and `period`; `config.py` / the protocol forbids `physical_weight`, `train_weight`, `source_sample`, and `source_entry`. Neither leaks into model features, but the divergence is confusing. | Compare the two constant definitions. | Align the domain `FORBIDDEN_FEATURES` with the protocol contract, or add a comment explaining that the domain set is a legacy compatibility guard while `config.py` enforces the authoritative V1 model-feature allowlist. |
| Low | Maintainability / M1-05 readiness | `src/angular5.py`, `src/features.py`, `src/input_profiles.py`, `src/pairing.py`, `src/reconstruction.py`, `src/selection.py`, `src/split.py`, `src/weights.py` | Compatibility alias modules use `sys.modules[__name__] = _implementation`. While this preserves legacy import paths, it complicates M1-05 deletion tracking and may surprise static-analysis or introspection tools. | All nine listed modules consist of the alias pattern. | Add deprecation comments at the top of each alias module and include them in the M1-05 deletion checklist, with a pointer to the authoritative `src/domain/` or `src/preprocessing/` replacement. |
| Low | Maintainability | `src/config.py:234-250` | The protocol loader hard-codes V1 sample contracts (exact DSIDs, labels, profiles, tree names, units). This is correct for V1 but makes the loader fragile to future protocol versions. | `_validate_preprocessing_sections` compares sample dictionaries against fixed tuples. | Document explicitly that `load_preprocessing_protocol` is a V1-sealed loader, not a generic loader, and that any future protocol change must bump `schema_version` and update the loader accordingly. |
| Low | Test Coverage | `tests/integration/test_refactor_preprocess_cli.py` | No end-to-end CLI test exercises the non-enhanced selection path. Because `preprocessing_protocol_v1.yaml` has `lepton_quality.enabled: true`, the legacy non-enhanced path is only reached through synthetic domain unit tests. | Protocol L41-50 enables lepton quality; CLI smoke uses that protocol unchanged. | Add a focused test that runs `prepare_mc_sample` with a disabled `lepton_quality` configuration, or document that the non-enhanced path is covered by `tests/unit/test_refactor_domain.py` / `tests/unit/test_refactor_preprocessing.py`. |
| Info | Verification (positive) | `tests/unit/test_refactor_domain.py`, `tests/unit/test_refactor_preprocessing.py`, `tests/golden/test_refactor_preprocess_golden.py`, `tests/integration/test_refactor_preprocess_cli.py` | M1-02 tests all pass and do not expand the historical failure set. Focused suite: `15 passed, 1 skipped`. Full suite: `791 passed, 211 failed, 3 skipped` vs. M1-01 baseline `776 passed, 211 failed, 2 skipped`. | Pytest output from this worktree. | Record these counts and the unchanged failure inventory in the Sprint M1-02 verification evidence. |
| Info | Schema (positive) | `src/preprocessing/pipeline.py:23-40` | Output schema is exactly pinned to 19 model features + 13 metadata columns, resolving document-review finding GLM H-1. `OUTPUT_COLUMNS` matches design §8.3 and the Sprint M1-02 acceptance criteria. | `MODEL_FEATURES` = 19 columns; `METADATA_COLUMNS` = 13 columns; integration test asserts header order. | No action required. |
| Info | Input binding (positive) | `src/preprocessing/reader.py:51-77`; `src/preprocessing/application.py:124-135`; `tests/unit/test_refactor_preprocessing.py:79-109` | Input stat/SHA-256 binding and replacement detection are implemented, resolving document-review finding GLM H-2. Symlink and non-regular-file rejection are also tested. | `inspect_mc_input` / `verify_mc_input`; tests for replacement, suffix, non-regular path, and symlink. | No action required. |
| Info | MC-only boundary (positive) | `src/config.py:231-250`; `src/preprocessing/pipeline.py:185-203`; `tests/integration/test_refactor_preprocess_cli.py:198-217` | Real-data / unknown DSID configurations are rejected before ROOT parsing, resolving document-review findings Kimi M1 and GLM I-2. The pipeline only reads `higgs` and `zz` samples from the protocol. | Protocol loader rejects unknown samples keys; CLI test rejects a protocol with a `data` sample. | No action required. |

## 3. Positive observations

- **Scientific behavior equivalence is preserved.** Domain functions (`src/domain/pairing.py`, `reconstruction.py`, `selection.py`, `features.py`, `angular5.py`, `split.py`, `weights.py`) are deterministic copies of the legacy modules, and the golden test shows identical Base14 values, weights, split assignments, and cutflow for the covered event.
- **Output schema is the central data contract and it is fixed.** `development.csv.gz` and `test.csv.gz` both carry the same ordered 19 + 13 columns, with `development = train + validation` rows and `test = test-bucket` rows, exactly as required by design §8.3.
- **MC-only boundary is enforced at multiple layers.** The protocol loader seals the sample keys to `{higgs, zz}`, the reader only accepts `.root` regular files, real-data sample injection fails before any ROOT I/O, and the new import-graph test prevents the preprocessing CLI from reaching legacy real-data / plotting / predict modules.
- **Artifact atomicity and failure semantics are intact.** `RunTransaction` claims a fresh directory, writes with `xb` mode, rejects path escape / symlink substitution, publishes the manifest last, and writes `failure.json` on any uncaught exception without a success manifest.
- **Dual-hash canonical CSV receipts are implemented.** Each CSV.GZ records both `sha256_compressed` and `sha256_canonical_csv`, and the integration test proves repeated micro-ROOT runs produce identical canonical hashes.
- **Verification discipline is observed.** The full suite was run and the historical 211-failure boundary is unchanged; all new M1-02 tests pass.

## 4. Relation to prior reviews and confirm decisions

This code review follows the document review cycle recorded in `docs/4-Reviews/sprint-m1-02-review-by-opencode-go-glm-5.2.md` and `docs/4-Reviews/sprint-m1-02-review-confirm.md`. The confirm decision table items have been addressed as follows:

| Confirm # | Decision | Implementation status |
|---|---|---|
| 1 | Add manifest code/software binding | Done: `application.py` records git identity, code SHA-256, and software versions. |
| 2 | Anchor golden authority and pre-registered tolerance | Done: `tests/golden/test_refactor_preprocess_golden.py` uses `RTOL = ATOL = 1e-12` from M1-01 policy. |
| 3 | Pin exact output schema | Done: `pipeline.py:OUTPUT_COLUMNS` = 19 features + 13 metadata; tests assert exact header order. |
| 4 | Keep metadata in CSV, forbid only model features | Done: `m4l`/identity/weights are metadata columns; `MODEL_FEATURES` is the 19-feature allowlist. |
| 5 | ROOT input stat/SHA-256 binding and replacement tests | Done: `reader.py` + `application.py` + unit tests. |
| 6 | CLI real-data rejection | Done: `test_cli_rejects_real_data_protocol_before_root_read`. |
| 7 | Split ownership: domain function vs. preprocessing partition | Done: `domain/split.py` computes buckets; `preprocessing/pipeline.py` applies them and writes manifest. |
| 8 | New import-graph boundary | Done: `test_new_preprocess_imports_do_not_reach_legacy_execution_modules`. |
| 9 | Full-suite baseline gate | Done: plan §7 records M1-01 baseline; implementation does not add failures. |
| 10 | Authoritative ROOT counts declared unexecuted | Done: plan §9 states no authoritative ROOT / frozen run is used. |
| 11 | Micro-ROOT fixture coverage | Done: integration test creates both profiles, both DSIDs, MeV/GeV scales, lepton-quality branches, and all three split buckets. |
| 12 | Explicit test file list | Done: plan §7 lists the four M1-02 test files explicitly. |
| 13 | Atomic promote / failure receipt | Done: `RunTransaction` + `application.py`. |
| 14 | Evidence checklist | Plan §10 is pre-populated; this report provides code-review evidence. |
| 15 | Design link | Plan §2 links to the approved design. |
| 16 | Protocol v1 consumed unchanged | Plan §3 states v1 is consumed byte-for-byte; output schema is fixed in code/tests. |
| 17 | M1-02 files staged in sprint commit | To be completed at commit time; plan §10.4 lists the stage set. |

## 5. Conclusion and required actions

The Sprint M1-02 implementation is scientifically sound and meets the approved plan's acceptance criteria. The code is ready to commit after addressing the Medium and Low findings above. The highest-priority actions are:

1. Validate the run directory against the project `runs/` root (finding #1).
2. Fix the git-dirty semantics for untracked source files (finding #2).
3. Add the ZZ `official_metadata` normalization golden test (finding #3).
4. Define and test the policy for `build_angular5` failures on selected events (finding #4).

The remaining Low findings should be resolved or documented before M1-03 begins consuming the preprocessing outputs.

No real data, authoritative ROOT, or frozen runs were accessed during this review. The authoritative count/cutflow equivalence check remains an unexecuted boundary, to be performed only when DSID 345060/363490 inputs and explicit authorization are available.

## 6. Verification performed for this review

- Read `AGENTS.md`, `FR-001-angular19-xgboost-refactor.md`, `2026-09-01-xgboost-refactor-design.md`, `sprint-m1-02.md`, `sprint-m1-02-review-confirm.md`.
- Read all files in `src/domain/`, `src/preprocessing/`, the modified `src/artifacts/transaction.py`, `src/cli/preprocess.py`, the nine compatibility alias modules, and the four new test files.
- Ran focused tests:
  ```
  .venv/Scripts/python -m pytest -q tests/unit/test_refactor_domain.py tests/unit/test_refactor_preprocessing.py tests/golden/test_refactor_preprocess_golden.py tests/integration/test_refactor_preprocess_cli.py
  15 passed, 1 skipped
  ```
- Ran full suite:
  ```
  .venv/Scripts/python -m pytest -q --tb=no
  791 passed, 211 failed, 3 skipped
  ```
- Compared full-suite result to M1-01 baseline (`776 passed, 211 failed, 2 skipped`) and confirmed no new failures and no failure-set growth.
- Verified `higgsml-preprocess --help` and import of the new domain package.
- Checked `git status --short` and `git diff --stat` for the tracked compatibility-module changes.
