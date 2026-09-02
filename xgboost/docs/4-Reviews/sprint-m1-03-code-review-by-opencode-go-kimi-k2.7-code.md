# Sprint M1-03 Code Review Report

- **Reviewer:** opencode-go/kimi-k2.7-code
- **Review Date:** 2026-09-02
- **Review Type:** Code review
- **Review Target:**
  - `docs/3-Plan/sprint-m1-03.md` (revised plan)
  - Implementation files:
    - `src/training/dataset.py`
    - `src/training/folds.py`
    - `src/training/model.py`
    - `src/training/trainer.py`
    - `src/training/evaluation.py`
    - `src/training/qualification.py`
    - `src/cli/xgboost.py`
  - Test files:
    - `tests/refactor_training_support.py`
    - `tests/unit/test_refactor_training_dataset.py`
    - `tests/unit/test_refactor_training_policy.py`
    - `tests/unit/test_refactor_training_evaluation.py`
    - `tests/unit/test_refactor_training_qualification.py`
    - `tests/golden/test_refactor_training_golden.py`
    - `tests/integration/test_refactor_develop_cli.py`
- **Governing Sources:**
  - `xgboost/AGENTS.md`
  - `docs/1-Requirement/FR-001-angular19-xgboost-refactor.md`
  - `docs/superpowers/specs/2026-09-01-xgboost-refactor-design.md`
  - `config/xgboost_protocol_v1.yaml`
  - `docs/4-Reviews/sprint-m1-03-review-confirm.md`
  - Legacy training authorities:
    - `scripts/higgsml.py`
    - `src/experiment_config.py`
    - `src/experiment_runner.py`
    - `config/experiment_training.yaml`
    - `src/full_training_policy.py`
    - `src/full_training_evaluation.py`
    - `src/validation.py`

## Overall Verdict

**Pass with required actions.**

No Critical or High findings. The M1-03 implementation correctly realizes the revised Sprint plan:

- Development consumes only `processed/development.csv.gz`; held-out test is never opened or read.
- Five-fold OOF, class-balanced sample weights, working-point freezing, OOF AUC/KS/efficiency, and the four qualification gates match the legacy authority and the approved design.
- Final model publication is eligible-only; `no_eligible_candidate` is a normal terminal state.
- The `develop` CLI rejects scientific overrides and provides only `--input-run`, `--protocol`, `--run-dir`.
- New tests pass and do not introduce any M1-03-attributable failure into the legacy-bound full suite.

The required actions are one medium-severity immutable-artifact binding gap, two test-coverage gaps, and two low-severity maintainability/observability notes. M1-04 through M1-06 files were explicitly excluded from this review.

## Scope and Method

Checks performed:

1. Read all files listed in the review target.
2. Compared scientific logic line-by-line against the legacy authorities (`experiment_runner.py`, `full_training_policy.py`, `full_training_evaluation.py`, `validation.py`).
3. Verified the implementation against the revised `sprint-m1-03.md` requirements (32-column schema, weight semantics, fold payload, working-point/KS/efficiency rules, qualification gates, artifact layout, CLI restrictions, test-deny evidence).
4. Ran the Sprint's focused test command and the full project test suite.
5. Ran `pip check`, `compileall` on the new modules/tests, and `git diff --check`.
6. Confirmed no access to real data, ROOT inputs, frozen runs, or held-out test files during review.

## Verification Performed

| Check | Command | Result |
|---|---|---|
| Focused M1-03 tests | `python -m pytest -q tests/unit/test_refactor_training_dataset.py tests/unit/test_refactor_training_policy.py tests/unit/test_refactor_training_evaluation.py tests/unit/test_refactor_training_qualification.py tests/golden/test_refactor_training_golden.py tests/integration/test_refactor_develop_cli.py` | **18 passed** in 6.67 s |
| Full project suite | `python -m pytest -q` | **816 passed, 211 failed, 4 skipped** (M1-02 baseline was 798/211/4; no new failures, no `test_refactor_training`/`develop_cli` failures) |
| Dependency consistency | `python -m pip check` | No broken requirements |
| Byte-code compilation | `python -m compileall src/training src/cli tests/refactor_training_support.py tests/unit/test_refactor_training_*.py tests/golden/test_refactor_training_golden.py tests/integration/test_refactor_develop_cli.py` | Success |
| Whitespace | `git diff --check` | Clean |

Repository state verified: the only modified file under review is `src/cli/xgboost.py` (M1-03 placeholder replaced by `run_development` call). All training modules and tests are new/untracked and scoped to M1-03. No M1-04/M1-05/M1-06 implementation was reviewed.

## Coverage Assessment

| Source Requirement | Implementation Location | Assessment |
|---|---|---|
| 32-column development CSV schema, identity uniqueness, finite values, forbidden features | `src/training/dataset.py:79-101`, `src/preprocessing/pipeline.py:24-40` | Covered; exact `OUTPUT_COLUMNS` match enforced |
| Deterministic 5-fold assignment, per-fold label balance, no stratification | `src/training/folds.py:13-37` | Covered; matches `full_training_policy.development_fold` exactly |
| Class-balanced weights recomputed from `physical_weight`, not CSV `train_weight` | `src/training/folds.py:40-61`, `src/training/trainer.py:85,172` | Covered; golden test exact-matches legacy weights |
| XGBoost fit, early stopping, one candidate, final tree count `np.rint` half-to-even | `src/training/model.py:32-57`, `src/training/trainer.py:66-155` | Covered; `final_tree_count` formula locked by golden test |
| Working points from OOF ZZ `abs(physical_weight)`; complete score-tie retention | `src/training/evaluation.py:47-121` | Covered; matches `full_training_evaluation.weighted_retention_threshold` |
| Background `m4l` KS using signed `physical_weight` (internally abs) | `src/training/evaluation.py:124-139`, `src/validation.py:16-68` | Covered |
| Weighted OOF AUC from `abs(physical_weight)` | `src/training/evaluation.py:37-44` | Covered |
| Four qualification gates (AUC, three KS, efficiency inequality, OOF integrity) | `src/training/qualification.py:46-97` | Covered |
| Eligible-only final model; `no_eligible_candidate` terminal state | `src/training/trainer.py:158-175`, `trainer.py:339-345` | Covered |
| `develop` CLI only `--input-run --protocol --run-dir`; no overrides | `src/cli/xgboost.py:9-35` | Covered; parser-rejection tests present |
| Development artifact layout and `test_opened: false` manifest binding | `src/training/trainer.py:320-429` | Covered; `state/test_opening.json` never created |
| Held-out test file not opened/read | `src/training/dataset.py:104-204`, `tests/unit/test_refactor_training_dataset.py:13-31` | Covered at loader level; CLI-level spy/deny in integration test could be added |

## Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| **Medium** | **Requirement / Immutable Artifact Semantics** | `src/training/dataset.py:116-123`, `_upstream_payload` in `src/training/trainer.py:301-317` | Upstream preprocessing `protocol` and `run_config` identity are copied as dictionaries but their SHA-256 subfields are not validated. The plan §5.3 requires binding "上游 protocol/run-config identity"; the manifest keys are required, but `protocol.sha256` and `run_config.sha256` are never inspected. | `load_development_input` requires `protocol` and `run_config` top-level keys but only passes them through to `upstream_payload`. No check ensures the `sha256` fields exist or are well-formed. | In `load_development_input`, require and validate `manifest["protocol"]["sha256"]` and `manifest["run_config"]["sha256"]`, store them in `DevelopmentInput`, and include them explicitly in `upstream_payload`. Fail closed if the fields are missing or non-strings. |
| **Medium** | **Test** | `tests/integration/test_refactor_develop_cli.py` | Missing integration test for occupied output directory rejection before any input is read. The plan §5.3 and FR-001 R7 require atomic output claim and no-clobber semantics. | No test pre-creates `run_dir` and asserts `FileExistsError` (or `failure.json`) before `development.csv.gz` or the upstream manifest is parsed. `RunTransaction` implements the check, but it is not exercised by the M1-03 test suite. | Add `test_develop_rejects_existing_output_before_input_read` that creates the output directory first and asserts the run fails before any model fitting or manifest publication. |
| **Medium** | **Test / Consistency** | `tests/integration/test_refactor_develop_cli.py:19-49` | The end-to-end `run_development` integration test checks the published layout but does not assert that the held-out `test.csv.gz` was not opened. The unit-level spy/deny in `test_refactor_training_dataset.py` covers `load_development_input`, but the CLI smoke path is not instrumented. | `test_development_run_publishes_frozen_layout_without_opening_test` verifies file existence and `test_opened: false`, but never installs a `Path.read_bytes` spy. The fixture writes `b"forbidden held-out test"` into `test.csv.gz`, so an accidental read would fail loudly, yet this is implicit. | Either add a `monkeypatch` spy/deny to the integration test that records every path opened by `run_development` and asserts the test path is absent, or document that the unit-level `test_loader_binds_committed_schema_and_never_reads_test` is the authoritative test-deny evidence and keep it in the focused test gate. |
| **Low** | **Maintainability / Clarity** | `src/training/trainer.py:248-266` | `_code_sha256` hardcodes the list of source files and omits the `src/preprocessing/pipeline.py` / `src/domain/*` modules that define the `OUTPUT_COLUMNS` and `MODEL_FEATURES` consumed by the run. | The digest covers `src/config.py`, `src/artifacts/*.py`, `src/cli/*.py`, `src/training/*.py`, and `src/validation.py`, but not the modules that pin the 19+13 column schema. If those schema modules change, the training code identity hash does not reflect it. | Document that the code identity hash covers the training/CLI/artifact layer only, and that the feature/schema contract is separately bound via `manifest.schema` and the upstream preprocessing manifest. Alternatively, include `src/preprocessing/pipeline.py` and the `src/domain/*.py` files that determine `OUTPUT_COLUMNS` and `MODEL_FEATURES`. |
| **Low** | **Maintainability / UX** | `src/training/trainer.py:86-95`, `168-175` | Training progress feedback from the legacy runner (`TrainingProgress` callbacks / tqdm bars) is not migrated. The plan §5.1 mentions migrating "进度" alongside early stopping. | All `classifier.fit(...)` calls use `verbose=False` and no `callbacks`; `experiment_runner.py` provided per-fold and final-model progress bars via `TrainingProgress`. | Decide whether progress bars are in scope for V1. If omitted intentionally, record the decision in the plan or code comments. If desired, add an optional `progress_factory`/`show_progress` path to `build_development_evidence` and `fit_final_model` while keeping the default silent for CI. |
| **Info** | **Consistency / Positive** | `src/training/folds.py`, `tests/unit/test_refactor_training_policy.py:24-29` | Fold algorithm and class-balanced weights are behavior-equivalent with the legacy authority. | `development_fold` uses the identical `blake2b("task4b-fold:{channel}:{event}", digest_size=8)` payload and big-endian modulo; `class_balanced_training_weights` recomputes per-class totals to `len(frame)/2` with mean 1; golden test asserts exact array equality against `full_training_policy.class_balanced_training_weights`. | No change required. |
| **Info** | **Requirement / Positive** | `src/training/evaluation.py`, `tests/unit/test_refactor_training_evaluation.py` | Working-point freezing, background `m4l` KS, efficiency, and weighted OOF AUC semantics match the design and legacy code. | `weighted_retention_threshold` scans OOF ZZ scores high-to-low with stable sort and absolute weights; `background_mass_ks` passes signed `physical_weight` to `weighted_ks_distance` (which internally takes absolute values); efficiencies use `|selected| / |inclusive|` per class. | No change required. |
| **Info** | **Requirement / Positive** | `src/training/qualification.py`, `src/training/trainer.py:339-345` | The four qualification gates and eligible-only model publication are implemented exactly as specified. | `qualify` checks `weighted_oof_auc >= minimum`, three KS distances `<= maximum`, signal efficiency `>` background efficiency when required, and OOF completeness/uniqueness; `fit_final_model` refuses to run when `eligible` is false; no `model/` is created for ineligible runs. | No change required. |
| **Info** | **Test / Positive** | Full pytest output | M1-03 tests pass and do not expand the pre-existing failure set. | Focused M1-03 command: 18 passed. Full suite: 816 passed / 211 failed / 4 skipped (vs. M1-02 baseline 798/211/4). No `test_refactor_training*` or `test_refactor_develop_cli*` failures appear in the 211 failures. | No change required; record the actual counts and failure-set comparison in the Sprint §10 verification evidence. |

## Positive Observations

- **Scientific behavior equivalence is well locked.** The implementation does not read `train_weight` from the CSV; it recomputes class-balanced weights from `physical_weight` for every fitting subset and the final development fit. Golden tests assert exact equality with `full_training_policy` and `experiment_runner` semantics.
- **Dev-only/test isolation is enforced at the file boundary.** `dataset.py` resolves only `processed/development.csv.gz`, rejects symlinks and non-regular files, validates both compressed and canonical SHA-256s against the upstream manifest, and never touches `processed/test.csv.gz`.
- **Artifact transaction is fail-closed and no-clobber.** `RunTransaction` claims the directory before any input is read, writes all artifacts with `xb` mode, publishes the manifest atomically, and leaves `failure.json` on any exception.
- **Qualification is a pure lifecycle gate.** It inspects already-produced evidence and never feeds back into candidate training, threshold selection, or model fitting.
- **CLI is minimal and protocol-driven.** No `--overwrite`, feature toggles, XGBoost parameter overrides, or threshold arguments are exposed; parser-rejection tests cover representative illegal overrides.
- **Tests respect the pre-registered precision policy.** Golden comparisons use `rtol=atol=1e-12`; integer/fold/schema/identity checks use exact equality.

## Conclusion and Required Actions

The M1-03 implementation is ready to proceed after addressing the items below. None of them change scientific parameters, candidate definitions, thresholds, or frozen artifacts.

1. **Validate upstream protocol/run-config SHA-256 identity** in `src/training/dataset.py` and surface it in the development manifest (`src/training/trainer.py`).
2. **Add an occupied-output rejection test** to `tests/integration/test_refactor_develop_cli.py`.
3. **Add or document CLI-level test-deny evidence** for held-out test non-access in the integration test.
4. **Clarify the scope of `_code_sha256`** and consider including schema-defining source files for full reproducibility.
5. **Record the decision on training progress bars** (migrate vs. intentionally omit) to close the §5.1 "进度" requirement.

Once these are resolved, the Sprint can be considered implemented and the M1-03 code review confirm can be recorded.

---

**Verification boundary statement:** This review inspected only M1-03 files. M1-04 (`open-test`), M1-05 (historical deletion), and M1-06 (final archival) implementations were not present and were not reviewed. No authoritative ROOT files, real data, frozen runs, or held-out test contents were accessed.
