# Sprint M1-03 Code Review

- **Reviewer:** opencode-go / glm-5.2
- **Review type:** code review (implementation change set)
- **Review date:** 2026-09-02
- **Worktree:** `D:\code\HiggsML-worktrees\xgboost-refactor` (branch `codex/xgboost-refactor`, base HEAD `386437f` = sprint M1-02 commit, plus the uncommitted M1-03 change set)
- **Authoritative inputs:** `AGENTS.md`, `docs/1-Requirement/FR-001-angular19-xgboost-refactor.md`, approved design `docs/superpowers/specs/2026-09-01-xgboost-refactor-design.md`, confirmed plan `docs/3-Plan/sprint-m1-03.md`, `docs/4-Reviews/sprint-m1-03-review-confirm.md` (37 adjudicated items), `config/xgboost_protocol_v1.yaml`, M1-02 manifest/CSV contract (`src/preprocessing/pipeline.py`, `src/preprocessing/application.py`), and the legacy training authorities named in plan §5.1 (`src/experiment_runner.py`, `src/full_training_policy.py`, `src/full_training_evaluation.py`, `src/validation.py`, `src/experiment_config.py`).
- **Scope boundary:** M1-03 only. `docs/3-Plan/sprint-m1-04.md` through `sprint-m1-06.md` were **not** reviewed.

**Verdict: Pass with required actions.** No Critical and no High findings. The M1-03 change
set is a faithful, scientifically behavior-equivalent migration of the Angular19 XGBoost
development lifecycle, and it correctly realizes the qualification gate that the approved
design introduced as *new* release-lifecycle behavior. Development consumes only the
development artifact, the held-out test is never opened, the fold/weight/OOF/working-point
semantics match the legacy authorities exactly (golden-locked), the artifact transaction is
immutable and no-clobber, and `no_eligible_candidate` produces no `model/` and no
`state/test_opening.json`. Three Medium findings (one upstream identity-binding gap, two
explicit plan test requirements not yet exercised end-to-end) and six Low/Info findings
should be resolved or explicitly triaged in the M1-03 code-review-confirm.

## 1. Change set reviewed

Tracked modification (1 file):

- `src/cli/xgboost.py` — M1-03 placeholder replaced with the real `develop` command
  (`run_development` application-service call).

Untracked implementation and tests:

- `src/training/` (`__init__.py`, `dataset.py`, `folds.py`, `model.py`, `trainer.py`,
  `evaluation.py`, `qualification.py`)
- `tests/refactor_training_support.py`
- `tests/unit/test_refactor_training_{dataset,policy,evaluation,qualification}.py`
- `tests/golden/test_refactor_training_golden.py`
- `tests/integration/test_refactor_develop_cli.py`

Not modified (verified): `config/xgboost_protocol_v1.yaml` is consumed byte-for-byte —
the plan §3/§5.3 declaration holds (`run_development` copies the protocol bytes verbatim to
`config.yaml` and records `protocol.sha256`); all legacy execution modules and tests are
untouched. M1-04–M1-06 plans remain untracked.

## 2. Verification performed

Prior recorded verification in this worktree is trusted and reported verbatim below; the
full suite was **not** rerun by this reviewer. Review method was line-by-line static
comparison of the migrated modules against the revised plan, the confirm decisions, FR-001
R4/R5/R7, design §8–§11, and the legacy authorities; repository facts were confirmed by
file reads and targeted grep only.

| Check | Command / method | Result |
|---|---|---|
| Focused M1-03 tests (recorded) | `python -m pytest -q tests/unit/test_refactor_training_dataset.py tests/unit/test_refactor_training_policy.py tests/unit/test_refactor_training_evaluation.py tests/unit/test_refactor_training_qualification.py tests/golden/test_refactor_training_golden.py tests/integration/test_refactor_develop_cli.py` | **18 passed** |
| Full suite (recorded) | `python -m pytest -q` | **816 passed, 211 failed, 4 skipped**; vs. M1-02 baseline `798 passed, 211 failed, 4 skipped` → exactly +18 pass, 0 new failures, 0 failure-set growth, no M1-03-attributable failures (per recorded inventory) |
| Equivalence (static) | `src/training/folds.py` vs `src/full_training_policy.py`; `src/training/evaluation.py` vs `src/full_training_evaluation.py`/`src/experiment_runner.py`; `src/training/model.py` vs `src/experiment_runner.py` | Fold payload, class-balanced weight formula, weighted-retention threshold, background `m4l` KS, weighted OOF AUC, and `final_tree_count = max(1, int(np.rint(np.median(best_iteration+1))))` are line-equivalent |
| Import-boundary (static) | `tests/unit/test_refactor_training_policy.py:42-70` | AST-based, relative-import-aware check forbidding legacy execution modules from the new training/CLI graph; includes `src/cli/xgboost.py` and all `src/training/*.py` |
| Dev-only read (static) | `src/training/dataset.py` | Only `processed/development.csv.gz` is opened; `processed/test.csv.gz` is never read — only its manifest `path`/`rows` metadata is validated |
| No-clobber / failure semantics (static) | `src/artifacts/transaction.py`, `src/training/trainer.py:320-365` | Fresh-dir claim before input parsing; `xb` writes; `failure.json` on exception; no success manifest on failure |

Boundary observed during this review: no real data, no authoritative ROOT, no frozen run,
and no held-out test content exist in or were opened from this worktree; the authoritative
345060/363490 large-scale training gate was **not** executed and no evidence was fabricated
for it. No implementation or test file was modified by this review; the only file written
is this report.

## 3. Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| Medium | Requirement / Auditability | `src/training/dataset.py:116-124,194-204`; `src/training/trainer.py:301-317` | The upstream preprocess `protocol` and `run_config` identity required by plan §5.3 is copied through but never shape-validated. `load_development_input` requires the top-level `protocol`/`run_config` keys to exist and later copies them verbatim into the development manifest's `upstream_run` block, but the nested `sha256` fields are never checked to be well-formed (non-empty 64-hex strings), and no schema-version/role consistency is asserted against the known M1-02 preprocessing contract. | `dataset.py:116-124` lists `protocol`/`run_config` among required keys but never inspects them; `trainer.py:310-311` passes `dict(manifest["protocol"])` / `dict(manifest["run_config"])` straight into `upstream_payload`. A corrupted-but-parsable upstream manifest with a garbage `protocol.sha256` is accepted and re-published as evidence. | In `load_development_input`, validate `manifest["protocol"]["schema_version"] == "1.0"` and both `protocol.sha256`/`run_config.sha256` as 64-char hex strings, store them on `DevelopmentInput`, and re-verify them in `verify_development_input`; surface them explicitly in the development manifest's `upstream_run`. |
| Medium | Test / Requirement | `tests/integration/test_refactor_develop_cli.py` (whole file) | Plan §5.3 test requirement explicitly lists an "occupied output" CLI integration case, and FR-001 R7 / design §11 require atomic no-clobber output claim. `RunTransaction` implements the `FileExistsError` check (`transaction.py:102-110`), but no M1-03 test pre-creates `run_dir` and asserts the run is rejected before any upstream manifest or development CSV is parsed. | The five integration tests cover eligible layout, no-eligible, tampered input, parser override rejection, and a real-XGBoost micro smoke — none pre-creates the output directory. The tampered-input test (`test_refactor_develop_cli.py:70-90`) exercises a failure *inside* the transaction, not the occupied-output path. | Add `test_develop_rejects_occupied_output_before_input_read`: create the output directory first, point a spy at the upstream development CSV / manifest, and assert the run raises `FileExistsError` (or exits 1) with neither input opened nor `artifacts/manifest.json` written. |
| Medium | Test / Evidence | `tests/integration/test_refactor_develop_cli.py:19-49` vs `tests/unit/test_refactor_training_dataset.py:13-31` | Held-out-test non-access ("test deny") is proven only at the loader unit level. The end-to-end `run_development` integration test asserts `test_opened is False` and file-layout membership but does not install a file-open spy over the whole `develop` path, so the strongest claim in the plan §6 acceptance ("Development 不读取 test CSV.GZ") is not exercised through the full run (fold fitting, plots, artifact writes). The fixture writes `b"forbidden held-out test"` into `test.csv.gz`, so an accidental read would be loud, but that is implicit rather than asserted. | `test_loader_binds_committed_schema_and_never_reads_test` monkeypatches `Path.read_bytes` and asserts the test path is absent from the opened set; the equivalent instrument is missing from `test_development_run_publishes_frozen_layout_without_opening_test`. | Install the same `Path.read_bytes` deny/spy in the integration test around `run_development` (or a real subprocess invocation) and assert `test.csv.gz` is never opened; keep the unit-level test as the loader contract and state this in the plan §10 evidence. |
| Low | Test / Correctness proof | `tests/refactor_training_support.py:31`; `src/training/trainer.py:85,172`; `src/training/folds.py:40-61` | The "CSV `train_weight` is audit-only, never fed to XGBoost" contract (plan §5.1, confirm decision #22) is implemented correctly but not directly proven. Every fixture writes the constant `train_weight=1.0`, so a regression that accidentally read the column would only be caught if the constant differed from the recomputed class-balanced weights. The golden test pins weight equality against the legacy function, which also ignores the column, so it cannot detect such a regression either. | `development_frame()` sets `train_weight=1.0` for all rows; `class_balanced_training_weights` recomputes from `physical_weight` and the trainer never references the column beyond the finite-value scan in `validate_development_frame`. | Add a test that rewrites `train_weight` to adversarial values (e.g., mirror of `physical_weight` or a large constant) and asserts fold fitting weights, OOF scores, and final-model weights are byte-identical — locking the audit-only contract. |
| Low | Maintainability / Reproducibility | `src/training/trainer.py:248-266` | `_code_sha256` enumerates a hardcoded source list that omits the schema-defining modules the run actually consumes. `src/training/dataset.py:17` imports `MODEL_FEATURES`/`OUTPUT_COLUMNS` from `src/preprocessing/pipeline.py`, which in turn depends on `src/domain/*`; those files are absent from the digest (which covers `src/config.py`, `src/artifacts/*`, `src/cli/xgboost.py`, `src/training/*`, and the legacy `src/validation.py`). A change to the 19+13 column contract would alter development behavior without changing the recorded code identity. | Sources list at `trainer.py:250-258`; omitted: `src/preprocessing/pipeline.py`, `src/domain/*.py`. The manifest separately pins the input schema via `schema.input_columns`/`model_features` and the upstream preprocess manifest, which partially mitigates but does not close the gap. | Either extend `_code_sha256` to cover the transitively imported schema modules (`src/preprocessing/pipeline.py` and the `src/domain/*.py` modules defining `FEATURES`/`ANGULAR5_FEATURES`/`OUTPUT_COLUMNS`), or document explicitly that the code identity covers the training/CLI/artifact layer only and the schema is bound via `manifest.schema` + upstream manifest. |
| Low | Requirement / Maintainability | plan §5.1 (L67); `src/training/trainer.py:88-95,168-175` | Plan §5.1 says "迁移 early stopping、进度和唯一 V1 candidate"; the "进度" (progress) element is not migrated. All `classifier.fit(...)` calls use `verbose=False` with no `TrainingProgress`/`callbacks`, whereas the legacy authority (`src/experiment_runner.py:500-518` `_fit_progress`, wired at `:140-166,206-226`) provided per-fold and final-model progress. The deletion is silent rather than a recorded decision. | Grep: `verbose=False` at `trainer.py:93,173`; no `callbacks`/`TrainingProgress` anywhere in `src/training/`. No behavioral/scientific impact (progress is UI only). | Record in the plan/confirm that progress reporting is intentionally omitted from V1 develop (silent fits for CI), or add an optional `progress_factory`/`show_progress` path defaulting to silent, matching legacy. |
| Low | Consistency / Correctness hardening | `src/training/dataset.py:86-99` vs `src/full_training_policy.py:147-181` | The migrated development-frame validator checks global `split` and `label` sets and rejects *any* duplicated `(channelNumber, eventNumber)`, but it does not enforce the legacy authority's per-split dual-label rule (`full_training_policy.py:167-169` requires each of train/validation to contain labels 0 and 1) nor its cross-split/cross-label identity-collision analysis. A single-class `train` subset (all ZZ in `validation`) would pass the new validator and could silently rebalance fold fitting weights instead of failing fast. | `dataset.py:86-90` checks `set(split)=={train,validation}` and `set(labels)=={0,1}` only; legacy `_validate_analysis_frame` iterates required splits and requires both labels each. In practice the M1-02 pipeline (Higgs + ZZ each spanning all splits) cannot produce such input, so the risk is regression-hardening only. | Tighten `validate_development_frame` to require each of `train`/`validation` to contain both labels (cheap), matching the legacy fail-fast behavior, or record the intentional relaxation in the confirm. |
| Low | Consistency / CLI diagnosability | `src/cli/xgboost.py:25-35` vs `src/cli/preprocess.py:21-40` | The `develop` CLI lets application exceptions escape uncaught (full traceback, generic exit 1), while the sibling `higgsml-preprocess` CLI catches exceptions and prints a normalized `higgsml-preprocess failed: {Type}: {message}` line. Failure receipts (`failure.json`) are still written correctly by the transaction, and the exit code is nonzero, but terminal diagnostics are inconsistent and the FR-001 error-path smoke surface is weaker. | `preprocess.py:29-34` wraps `run_preprocessing` in `try/except`; `xgboost.py` has no equivalent around `run_development`. | Add the same `try/except` normalization in `main` (print `higgsml-xgboost failed: {type}: {exc}` to stderr, return 1) while keeping the success/status print and normalized exit codes. |
| Low | Test / Layout strictness | `tests/integration/test_refactor_develop_cli.py:35-49,52-68` | The layout assertions use `expected.issubset(files)`, so stray/unapproved files inside the run directory would pass silently (only the specific `state/test_opening.json` absence is asserted at line 46). The plan §6/design §10.1 contract is "exactly the approved layout" for both eligible and ineligible runs; the tests do not lock the full set. | `test_development_run_publishes_frozen_layout_without_opening_test` and `test_no_eligible_run_has_no_model_or_test_claim` assert subset membership / non-existence of `model` and `state`, not equality of the file set. | Assert `files == expected ∪ {model/model.json, plots/oof_scores.png}` for the eligible case and `files == expected_no_model` for the ineligible case, so any unapproved addition fails the suite. |
| Info | Consistency / Degenerate-case divergence | `src/training/trainer.py:119-123` vs `src/experiment_runner.py:195-199` | `standard_error_weighted_auc` is computed unconditionally as `std(ddof=1)/sqrt(folds)`; the legacy authority guarded `folds > 1` (else 0.0). With `folds == 1`, the migrated formula yields NaN (std with ddof=1 on one sample) instead of 0.0. Unreachable under V1 because the protocol pins `folds: 5` and `config.py:415-416` requires `folds >= 2`. | `trainer.py:120-122`; `experiment_runner.py:195-199` (`if config.folds > 1 else 0.0`). | No code change needed for V1; note the intentional simplification in the confirm so a future protocol with `folds == 1` does not silently produce NaN in the manifest. |
| Info | Requirement (positive) | whole change set | The confirm's 37 decisions are realized: 32-column fail-closed loader with `m4l` dual role (dataset.py), `blake2b("task4b-fold:{channel}:{event}")` big-endian fold with post-hoc dual-label fold verification (folds.py), class-balanced weights recomputed from `physical_weight` (folds.py), one-candidate OOF with `np.rint` half-to-even final tree count (model.py, trainer.py), ZZ-only working points from `abs(physical_weight)` with complete tie retention and signed-weight `m4l` KS (evaluation.py), the four qualification gates including strict efficiency inequality and OOF integrity (qualification.py), eligible-only `model/model.json`, and `no_eligible_candidate` with no `state/test_opening.json`. | Golden tests pin fold/weight/OOF/final-parameter equality to the legacy authority at `rtol=atol=1e-12`; integration tests assert layout, `test_opened: false`, no-model-when-ineligible, tampered-input failure receipt, and parser rejection of scientific overrides. | No change; these are the sprint's core evidence. |

## 4. Coverage assessment

| Source requirement | Implementation location | Assessment |
|---|---|---|
| Fixed, ordered, unique 32-column dev schema; type/finite/split/identity/forbidden validation | `src/training/dataset.py:79-101`; schema source `src/preprocessing/pipeline.py:24-40` | Covered; exact `OUTPUT_COLUMNS` match and per-split label parity are the only deltas (Low finding above) |
| Deterministic 5-fold; no stratification; per-fold label 0/1 verification; mutual exclusion + full coverage | `src/training/folds.py:13-37`; `src/training/trainer.py:74-113` | Covered; golden test asserts exact equality with legacy folds and OOF coverage |
| `sample_weight` recomputed from `physical_weight` (class-balanced, class total `len/2`, mean 1); CSV `train_weight` audit-only | `src/training/folds.py:40-61`; `src/training/trainer.py:85,172` | Covered; audit-only contract lacks a direct adversarial test (Low finding) |
| Early stopping, single candidate, `binary:logistic`/`auc` code-fixed, final tree count `np.rint` half-to-even | `src/training/model.py:32-76`; `src/training/trainer.py:66-128` | Covered; `.5`-median fixture locks half-to-even (golden test); progress omission is a Low/decision item |
| Working points from OOF ZZ `abs(physical_weight)`, stable high-to-low, first-reach target, full tie | `src/training/evaluation.py:47-121` | Covered; exact equality vs legacy asserted in unit test |
| Per-point inclusive-vs-selected ZZ `m4l` KS with signed weights (internal abs); abs-weight efficiencies | `src/training/evaluation.py:124-139`; `src/validation.py:16-68` | Covered |
| Weighted OOF AUC with `abs(physical_weight)` | `src/training/evaluation.py:37-44` | Covered |
| Four qualification gates; no-eligible normal terminal; gate never feeds back | `src/training/qualification.py:46-97`; `src/training/trainer.py:138-145,339-345` | Covered; unit fixtures cover AUC/KS boundary, strict efficiency, incomplete OOF |
| Eligible-only final model publication; ineligible has no `model/` | `src/training/trainer.py:158-175,339-345,361-363` | Covered by integration test |
| `develop` CLI only `--input-run --protocol --run-dir`; no overrides | `src/cli/xgboost.py:9-35` | Covered; parser-rejection test present; error normalization differs from preprocess CLI (Low) |
| Development layout + manifest `test_opened: false`; no `state/test_opening.json` in M1-03 | `src/training/trainer.py:320-429` | Covered; layout test is subset-based only (Low) |
| Upstream run/manifest/CSV dual-hash binding; protocol/run-config identity | `src/training/dataset.py:104-204` | Partially covered; `protocol`/`run_config` `sha256` subfields unvalidated (Medium) |
| Test-denial proof and occupied-output rejection | `tests/` | Unit-level loader spy only; no end-to-end spy and no occupied-output test (two Medium test gaps) |

## 5. Positive observations

- **Scientific behavior equivalence is precisely locked.** Fold payload/bytes, class-balanced
  weights, working-point thresholds, `m4l` KS, weighted OOF AUC, and the final-tree-count
  formula are line-equivalent to the legacy authorities and pinned by golden tests at
  `rtol=atol=1e-12` with exact integer/identity/schema equality.
- **Dev-only/test isolation is structural, not incidental.** `dataset.py` resolves and reads
  only `processed/development.csv.gz`; the held-out `test.csv.gz` path is validated only via
  manifest metadata and is never opened. Symlink/non-regular inputs, path escapes, hash
  drift, and unknown schemas fail closed.
- **The qualification gate is a pure lifecycle control.** It consumes already-produced OOF
  evidence and never influences candidate training, threshold selection, or model fitting;
  `no_eligible_candidate` is a normal successful terminal state with full evidence and no
  model.
- **Immutable-artifact discipline is maintained.** The run directory is claimed before any
  input is parsed, all writes are `xb` no-clobber, the manifest is published atomically, and
  failures leave only a `failure.json` receipt.
- **The import boundary between new and legacy execution code is enforced with an
  AST-based, relative-import-aware test** — the strongest guard yet in this refactor — and
  `src/cli/xgboost.py` no longer imports any legacy execution module.

## 6. Boundary statement

This review inspected only M1-03 files and did not review or modify M1-04 (`open-test`),
M1-05 (historical deletion), or M1-06 (final archival). No real data, authoritative ROOT
files, frozen runs, or held-out test contents were accessed; the authoritative 345060/363490
large-scale training gate was not executed. The full test suite was not rerun; the recorded
focused (`18 passed`) and full (`816 passed, 211 failed, 4 skipped`, +18/0/0 vs. M1-02)
results are reported as recorded.

## 7. Required actions before M1-03 close

1. Validate and bind the upstream `protocol`/`run_config` SHA-256 identity in
   `load_development_input` and surface it in the development manifest (Medium).
2. Add the occupied-output rejection integration test and the end-to-end test-denial
   spy/deny integration test required by plan §5.3 (two Medium).
3. Triage the six Low/Info findings in code-review-confirm: train_weight adversarial test,
   `_code_sha256` schema-module coverage, progress-migration decision, per-split label
   parity, CLI error normalization, and exact-set layout assertions.
4. Complete plan §10 delivery evidence (environment, verification, artifact/commit records)
   verbatim from actual command output, and record the M1-03-attributable-failure audit
   against the `798/211/4` M1-02 boundary.

None of the above change scientific parameters, candidates, working points, thresholds,
qualification gates, or any frozen artifact.

— opencode-go / glm-5.2, 2026-09-02
