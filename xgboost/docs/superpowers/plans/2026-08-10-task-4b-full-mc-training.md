# Task 4B Full-MC Training Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, run, and freeze a scientifically controlled full-MC XGBoost model with class-balanced weights, deterministic five-fold model selection, three MC-only working points, independent one-shot test evaluation, and no real-data access.

**Architecture:** Keep the historical demo training path unchanged. Add focused modules for policy, model selection, evaluation, plotting, provenance-safe run publication, and a new `scripts.train_full_mc` CLI. The CLI reads only a completed Task 4A MC table, writes a fresh immutable run directory, and publishes the completion manifest last.

**Tech Stack:** Python 3.12, pandas, NumPy, scikit-learn 1.9, XGBoost 3.3, matplotlib, PyYAML, pytest.

## Global Constraints

- Canonical input is `runs/full-baseline-2026-08-10`; it is read-only.
- Use all 351399 selected MC events: 350928 Higgs and 471 ZZ; sampling fraction is `1.0` for each class.
- Development is existing train plus validation; existing test remains sealed until all choices are frozen.
- Signed `physical_weight` is for physical yields. Training and probability-distribution metrics use non-negative absolute weights.
- Recompute Task 4B training weights inside every fitting subset; never reuse Task 4A `train_weight`.
- `src.features.FEATURES` stays unchanged. `m4l`, identifiers, metadata, splits, labels, and weights are forbidden model features.
- Compare exactly six candidates: `max_depth` in `[2, 3, 4]` crossed with `min_child_weight` in `[5, 20]`.
- Use deterministic five-fold CV, the one-standard-error selection rule, and the simpler eligible model.
- Working points retain 50%, 20%, and 10% of OOF ZZ absolute physical weight; medium is the default.
- Task 4B must not open, score, plot, or inspect `data_events.csv.gz` or any real-data event table.
- Every training run requires a fresh atomically claimed `--run-dir`; no legacy `outputs/` file is modified.
- The parent repository has no initial project commit and the project is untracked. Do not stage, commit, create a branch, or create a worktree.
- Follow TDD: observe each focused test fail for the intended reason before adding its implementation.
- Do not claim completion until focused tests, the complete synthetic suite, the real full-MC run, artifact audit, and legacy immutability audit pass.

Post-first-run identity correction (2026-08-11): the measured Task 4A MC table has
five repeated `(channelNumber, eventNumber)` groups containing ten rows. All five
groups are confined to one label and one split, with no exact full-row duplicates.
The pair is therefore a deterministic grouping identifier, not a globally unique
row key. A unique pandas DataFrame index remains the row key for OOF accounting.

## File map

Create:

- `config/full_training.yaml`: frozen Task 4B candidate, fold, working-point, warning, plotting, and thread configuration.
- `src/full_training_policy.py`: config parsing, class-balanced weights, deterministic folds, candidate definitions, and input-frame validation.
- `src/full_training_model.py`: five-fold fits, candidate ranking, final tree-count choice, and final model fit.
- `src/full_training_evaluation.py`: weighted quantiles, working points, AUC/yield/KS/correlation metrics, and warning report.
- `src/full_training_run.py`: Task 4A input verification, hash snapshots, safe output layout, atomic artifact publication, and training manifest.
- `src/full_training_plots.py`: the five approved MC-only figures.
- `scripts/train_full_mc.py`: orchestration CLI that never reads Task 4A data events.
- `tests/test_full_training_policy.py`
- `tests/test_full_training_model.py`
- `tests/test_full_training_evaluation.py`
- `tests/test_full_training_run.py`
- `tests/test_full_training_plots.py`
- `tests/test_train_full_mc_script.py`
- `tests/test_task4b_docs.py`

Modify only after the real run succeeds:

- `README.md`: Task 4B command, output layout, and result boundary.
- `AGENTS.md`: frozen Task 4B result, exact tests, and next-stage boundary.
- `docs/project/overview.md`: replace “Task 4B unimplemented” with actual MC-only results.
- `docs/roadmap/next-stage.md`: mark Task 4B complete; keep data expansion and unblinding unimplemented.
- `docs/README.md`: link the approved Task 4B specification and implementation plan.

Historical compatibility files that must not change behavior:

- `src/train.py`
- `src/validation.py`
- `scripts/train_demo.py`
- `scripts/evaluate_data.py`
- `config/demo.yaml`

---

### Task 1: Freeze policy, validate MC input, and balance fitting weights

**Files:**
- Create: `config/full_training.yaml`
- Create: `src/full_training_policy.py`
- Create: `tests/test_full_training_policy.py`
- Read: `src/features.py`
- Read: `src/split.py`

**Interfaces:**
- Produces: `TrainingPolicy`, `CandidateSpec`, `load_training_policy(path)`, `validate_mc_frame(frame)`, `identity_collision_summary(frame)`, `class_balanced_training_weights(frame)`, `development_fold(channel_number, event_number, folds=5)`, `assign_development_folds(frame, folds=5)`, and `candidate_specs(policy)`.
- Consumes later: Tasks 2, 3, and 6 import these exact names.

- [ ] **Step 1: Write failing tests for the exact class-balanced formula**

Add tests equivalent to:

```python
def test_balanced_weights_use_absolute_physical_weight_and_equal_class_totals():
    frame = pd.DataFrame(
        {"label": [0, 0, 1, 1], "physical_weight": [-2.0, 1.0, 0.25, -0.75]}
    )
    weights = class_balanced_training_weights(frame)
    assert weights.tolist() == pytest.approx([4 / 3, 2 / 3, 0.5, 1.5])
    assert weights[frame.label == 0].sum() == pytest.approx(2.0)
    assert weights[frame.label == 1].sum() == pytest.approx(2.0)
    assert weights.mean() == pytest.approx(1.0)
    assert (weights >= 0).all()


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_balanced_weights_reject_nonfinite_physical_weight(bad):
    frame = pd.DataFrame({"label": [0, 1], "physical_weight": [1.0, bad]})
    with pytest.raises(ValueError, match="physical_weight must be finite"):
        class_balanced_training_weights(frame)


def test_balanced_weights_reject_zero_absolute_class_sum():
    frame = pd.DataFrame({"label": [0, 1], "physical_weight": [0.0, 1.0]})
    with pytest.raises(ValueError, match="positive absolute physical-weight sum"):
        class_balanced_training_weights(frame)
```

- [ ] **Step 2: Run the focused tests and confirm the missing module failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_full_training_policy.py -q
```

Expected: collection fails because `src.full_training_policy` does not exist.

- [ ] **Step 3: Implement immutable policy types and weight construction**

Create these public data types:

```python
@dataclass(frozen=True)
class CandidateSpec:
    name: str
    max_depth: int
    min_child_weight: float


@dataclass(frozen=True)
class TrainingPolicy:
    folds: int
    random_seed: int
    n_jobs: int
    common_parameters: Mapping[str, object]
    candidates: tuple[CandidateSpec, ...]
    working_points: Mapping[str, float]
    auc_gap_limit: float
    ks_distance_limit: float
    mass_bins_gev: tuple[float, ...]
```

Implement:

```python
def class_balanced_training_weights(frame: pd.DataFrame) -> np.ndarray:
    labels = frame["label"].to_numpy(dtype=int)
    physical = frame["physical_weight"].to_numpy(dtype=float)
    if set(labels) != {0, 1}:
        raise ValueError("fitting subset must contain labels 0 and 1")
    if not np.isfinite(physical).all():
        raise ValueError("physical_weight must be finite")
    output = np.empty(len(frame), dtype=float)
    target = len(frame) / 2.0
    for label in (0, 1):
        mask = labels == label
        total = float(np.abs(physical[mask]).sum())
        if total <= 0:
            raise ValueError("each class must have positive absolute physical-weight sum")
        output[mask] = np.abs(physical[mask]) * target / total
    if not np.isfinite(output).all() or np.any(output < 0):
        raise ValueError("training weights must be finite and non-negative")
    return output
```

The implementation must verify both class totals equal `len(frame) / 2` and the combined mean equals 1 using `np.isclose` with `rtol=1e-12`, `atol=1e-12`.

- [ ] **Step 4: Add failing tests for input validation and feature leakage**

Construct a valid frame containing all `FEATURES`, `m4l`, identifiers, `split`, `label`, and `physical_weight`. Test exact rejection of:

```python
@pytest.mark.parametrize("column", FEATURES + ["m4l", "eventNumber", "channelNumber", "split", "label", "physical_weight"])
def test_validate_mc_frame_requires_every_analysis_column(valid_frame, column):
    with pytest.raises(ValueError, match="missing required columns"):
        validate_mc_frame(valid_frame.drop(columns=column))


def test_validate_mc_frame_requires_exact_labels_and_splits(valid_frame):
    with pytest.raises(ValueError, match="labels must be exactly"):
        validate_mc_frame(valid_frame.assign(label=2))
    with pytest.raises(ValueError, match="unknown split"):
        validate_mc_frame(valid_frame.assign(split="data"))


def test_features_still_exclude_mass_identifiers_and_weights():
    assert "m4l" not in FEATURES
    assert set(FEATURES).isdisjoint(FORBIDDEN_FEATURES)
```

- [ ] **Step 5: Implement strict frame validation without modifying `FEATURES`**

`validate_mc_frame(frame)` must:

1. require all frozen features plus `m4l`, `eventNumber`, `channelNumber`, `split`, `label`, and `physical_weight`;
2. allow repeated `(channelNumber, eventNumber)` pairs only when every row in a
   pair has exactly one label and exactly one split; reject cross-label or
   cross-split groups before fitting and never drop or deduplicate rows;
3. require labels exactly `{0, 1}` and splits exactly `{"train", "validation", "test"}`;
4. require every split to contain both classes;
5. require all feature, mass, and physical-weight values finite;
6. call `assert_no_feature_leakage()`;
7. return `None` after validation and never mutate the input.

- [ ] **Step 6: Add and run deterministic-fold tests**

Tests must assert:

```python
def test_development_fold_is_namespaced_deterministic_and_in_range():
    first = development_fold(345060, 123456, folds=5)
    assert first == development_fold(345060, 123456, folds=5)
    assert 0 <= first < 5


def test_assign_folds_excludes_test_and_preserves_row_identity(valid_frame):
    assigned = assign_development_folds(valid_frame, folds=5)
    assert set(assigned.index) == set(valid_frame[valid_frame.split != "test"].index)
    assert set(assigned.unique()) <= set(range(5))
```

Implement the hash from bytes of
`task4b-fold:{channelNumber}:{eventNumber}` using BLAKE2b digest size 8, integer modulo `folds`. `assign_development_folds` returns a Series indexed only by development-row DataFrame indexes, retains repeated identifier rows, assigns every repeated pair to the same fold, and rejects a fold that lacks either class. Cross-validation additionally requires the DataFrame index itself to be unique so every OOF row is assigned exactly once.

- [ ] **Step 7: Freeze and test the six-candidate YAML policy**

Create `config/full_training.yaml` with exact values:

```yaml
schema_version: "1.0"
folds: 5
random_seed: 42
n_jobs: 4
common_parameters:
  n_estimators: 1000
  learning_rate: 0.05
  subsample: 0.8
  colsample_bytree: 0.8
  reg_alpha: 0.1
  reg_lambda: 2.0
  objective: binary:logistic
  eval_metric: auc
  early_stopping_rounds: 50
  tree_method: hist
candidates:
  max_depth: [2, 3, 4]
  min_child_weight: [5, 20]
working_points:
  loose: 0.50
  medium: 0.20
  tight: 0.10
warnings:
  auc_gap_limit: 0.05
  ks_distance_limit: 0.10
mass_bins_gev: [105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160]
```

`load_training_policy` rejects unknown schema versions, wrong fold count, non-positive thread count, a candidate product other than the exact six approved pairs, changed working-point names/efficiencies, missing common parameters, unsorted mass bins, or non-finite values. Candidate names are `depth{d}_child{m}` and ordering is depth ascending, then child weight descending for simplicity.

- [ ] **Step 8: Run Task 1 tests and the historical weight/feature/split tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_full_training_policy.py tests/test_weights.py tests/test_features.py tests/test_split.py -q
```

Expected: all pass. Record the count in the plan execution notes; do not commit.

---

### Task 2: Implement deterministic five-fold candidate selection and final fitting

**Files:**
- Create: `src/full_training_model.py`
- Create: `tests/test_full_training_model.py`
- Read: `src/progress.py`

**Interfaces:**
- Consumes: `TrainingPolicy`, `CandidateSpec`, `class_balanced_training_weights`, `assign_development_folds`, and `FEATURES`.
- Produces: `FoldMetric`, `CandidateResult`, `ModelSelectionResult`, `cross_validate_candidates(frame, policy, model_factory=None)`, `choose_candidate(results)`, `final_tree_count(result)`, and `fit_final_model(frame, selection, policy, model_factory=None)`.

- [ ] **Step 1: Write failing selection-rule tests using fabricated fold metrics**

Use these public immutable types:

```python
@dataclass(frozen=True)
class FoldMetric:
    fold: int
    weighted_auc: float
    unweighted_auc: float
    best_iteration: int


@dataclass(frozen=True)
class CandidateResult:
    candidate: CandidateSpec
    folds: tuple[FoldMetric, ...]
    mean_weighted_auc: float
    standard_error_weighted_auc: float


@dataclass(frozen=True)
class ModelSelectionResult:
    selected: CandidateResult
    candidates: tuple[CandidateResult, ...]
    oof_scores: pd.Series
    development_folds: pd.Series
```

Test that the highest mean defines the one-standard-error band, then lower depth and higher child weight win among eligible candidates. Also test that non-finite AUC, missing folds, duplicate folds, negative best iteration, and a candidate list other than six are rejected.

- [ ] **Step 2: Run the selection tests and confirm the missing module failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_full_training_model.py -q
```

Expected: collection fails because `src.full_training_model` does not exist.

- [ ] **Step 3: Implement candidate ranking and tree-count conversion**

Implement:

```python
def choose_candidate(results: Sequence[CandidateResult]) -> CandidateResult:
    best = max(results, key=lambda item: item.mean_weighted_auc)
    floor = best.mean_weighted_auc - best.standard_error_weighted_auc
    eligible = [item for item in results if item.mean_weighted_auc >= floor]
    return min(
        eligible,
        key=lambda item: (
            item.candidate.max_depth,
            -item.candidate.min_child_weight,
            item.candidate.name,
        ),
    )


def final_tree_count(result: CandidateResult) -> int:
    counts = np.asarray([metric.best_iteration + 1 for metric in result.folds])
    return max(1, int(np.rint(np.median(counts))))
```

Compute fold standard error with sample standard deviation divided by square root of five. Validate all fields before ranking.

- [ ] **Step 4: Write failing CV tests with a recording fake classifier**

The fake must record fit indices, `sample_weight`, eval indices, evaluation weights, parameter dictionaries, and prediction calls. Assert:

- exactly 30 fits occur: 6 candidates times 5 folds;
- no test index is present in a fit or eval set;
- each development index is predicted exactly once per candidate;
- each fitting subset has equal total training weight by class and mean 1;
- eval weights equal `abs(physical_weight)` for the held-out fold;
- XGBoost receives `FEATURES` in frozen order and no other column;
- candidate and common parameters plus `random_state` and `n_jobs` are passed;
- returned OOF scores correspond only to the selected candidate.

- [ ] **Step 5: Implement cross-validation with an injectable model factory**

`cross_validate_candidates` must:

1. validate the frame and assign development folds;
2. instantiate one classifier per candidate/fold;
3. call `fit` with fitting `sample_weight`, one held-out `eval_set`, and `sample_weight_eval_set=[abs(eval physical weight)]`;
4. score the held-out fold;
5. compute weighted and unweighted `roc_auc_score`;
6. capture `best_iteration` and reject missing or invalid values;
7. retain OOF scores for every candidate until ranking is complete;
8. verify exact OOF coverage and discard non-selected per-event predictions from the return value;
9. return candidates in deterministic policy order.

The default factory lazily imports `xgboost.XGBClassifier` and retains the historical libomp error explanation.

- [ ] **Step 6: Write failing final-fit tests**

Assert one final fit uses all and only development rows, recomputes balanced weights, uses the selected depth/child parameters, replaces `n_estimators` with `final_tree_count`, removes `early_stopping_rounds`, provides no eval set, and never predicts test inside `fit_final_model`.

- [ ] **Step 7: Implement final fitting**

Return the fitted classifier. The caller, not `fit_final_model`, controls when test prediction occurs. Expose a helper `effective_parameters(selection, policy, final=True)` so the exact final dictionary can be tested and serialized.

- [ ] **Step 8: Run Task 2 and compatibility tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_full_training_model.py tests/test_progress.py tests/test_validation.py -q
```

Expected: all pass. Do not alter `src/train.py` to make the new tests pass.

---

### Task 3: Freeze working points and build MC-only evaluation diagnostics

**Files:**
- Create: `src/full_training_evaluation.py`
- Create: `tests/test_full_training_evaluation.py`
- Read: `src/validation.py`

**Interfaces:**
- Consumes: selected OOF scores, fitted final model scores, `TrainingPolicy`, and signed `physical_weight`.
- Produces: `weighted_retention_threshold`, `build_working_points`, `weighted_pearson`, `evaluate_full_training`, and JSON-ready metric dictionaries.

- [ ] **Step 1: Write failing weighted-threshold tests including ties**

Tests must prove:

```python
def test_weighted_retention_threshold_uses_background_absolute_weight():
    scores = np.array([0.1, 0.4, 0.8, 0.9])
    weights = np.array([1.0, 1.0, 1.0, 1.0])
    assert weighted_retention_threshold(scores, weights, 0.50) == pytest.approx(0.8)


def test_working_points_are_ordered_and_report_achieved_efficiency():
    points = build_working_points(oof_frame, {"loose": .5, "medium": .2, "tight": .1})
    assert points["loose"]["threshold"] <= points["medium"]["threshold"]
    assert points["medium"]["threshold"] <= points["tight"]["threshold"]
    assert points["medium"]["target_background_efficiency"] == pytest.approx(.2)
```

Tie policy: sort scores descending with stable ordering, choose the lowest score at which cumulative retained absolute weight first reaches or exceeds the target, and report the actual efficiency after selecting every event tied at that score.

- [ ] **Step 2: Implement weighted thresholds with strict validation**

Reject empty arrays, mismatched shapes, non-finite values, non-positive total weight, target outside `(0, 1)`, absent ZZ OOF rows, or non-monotonic thresholds. `build_working_points` derives thresholds from OOF label-0 rows only and reports target/achieved background efficiency, signal efficiency, raw counts, and signed/absolute yields for both classes.

- [ ] **Step 3: Write failing tests for AUC, yields, calibration drift, and sealed test use**

Build separate OOF, final-development, and test frames. Assert:

- weighted AUC uses `abs(physical_weight)`;
- signed yields preserve negative weights;
- the unchanged OOF thresholds are applied to final-development and test scores;
- final-development achieved efficiencies are reported as calibration drift, never used to replace thresholds;
- test metrics do not influence any returned threshold;
- warning reasons are deterministic and JSON serializable.

- [ ] **Step 4: Implement the complete evaluation report**

`evaluate_full_training(oof, final_development, test, working_points, policy)` returns:

```python
{
    "selection": {"candidate": ..., "final_tree_count": ...},
    "development_oof": {"weighted_auc": ..., "unweighted_auc": ...},
    "test": {"weighted_auc": ..., "unweighted_auc": ...},
    "working_points": {...},
    "overfitting": {
        "development_test_auc_gap": ...,
        "signal_ks_distance": ...,
        "background_ks_distance": ...,
        "warning": ...,
        "warning_reasons": [...],
    },
    "mass_sculpting": {...},
}
```

Use `weighted_ks_distance` for score comparisons. AUC/KS warning limits come from policy. Do not calculate or optimize Asimov significance for threshold selection.

- [ ] **Step 5: Write and implement weighted mass-sculpting diagnostics**

Implement `weighted_pearson(x, y, weights)` with absolute finite weights and the standard weighted covariance divided by weighted standard deviations. Return `0.0` when either weighted variance is zero.

For OOF ZZ and independent test ZZ, report:

- weighted score/mass correlation;
- inclusive-to-selected weighted KS distance for each working point;
- fixed-bin inclusive absolute yield, selected absolute yield, and efficiency;
- a warning if any computed diagnostic is non-finite; finite values remain evidence rather than a hard validity gate.

- [ ] **Step 6: Run Task 3 and historical validation tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_full_training_evaluation.py tests/test_validation.py -q
```

Expected: all pass and historical validation threshold behavior remains unchanged.

---

### Task 4: Verify Task 4A provenance and publish a fresh training run safely

**Files:**
- Create: `src/full_training_run.py`
- Create: `tests/test_full_training_run.py`
- Reuse: `src/provenance.py`
- Reuse patterns from: `src/preparation.py`

**Interfaces:**
- Produces: `TrainingInput`, `TrainingOutputLayout`, `resolve_training_input`, `snapshot_input_hashes`, `assert_input_hashes_unchanged`, `resolve_training_output`, `claim_training_output`, `write_training_artifacts`, and `publish_training_manifest`.
- Consumes later: the CLI in Task 6.

- [ ] **Step 1: Write failing provenance tests from a minimal synthetic Task 4A run**

The fixture writes config, MC CSV, summary, and a schema-1.1 full-mode manifest. Tests reject:

- missing manifest or MC CSV;
- manifest schema other than `1.1`;
- read policy other than full with `entry_stop: null`;
- summary counts not matching MC rows or labels;
- non-finite MC data;
- any input path that resolves through a dangling symlink;
- a change to config, summary, manifest, or MC CSV between initial and final hash checks.

Do not create a synthetic `data_events.csv.gz`; successful input resolution must prove it is unnecessary.

- [ ] **Step 2: Implement immutable input and hash types**

```python
@dataclass(frozen=True)
class TrainingInput:
    input_run: Path
    config_path: Path
    mc_path: Path
    summary_path: Path
    manifest_path: Path
    hashes: Mapping[str, str]
    expected_rows: int


@dataclass(frozen=True)
class TrainingOutputLayout:
    run_dir: Path
    config_snapshot: Path
    model_dir: Path
    artifacts_dir: Path
    predictions_dir: Path
    plots_dir: Path
```

Use `sha256_file` for hashes. `resolve_training_input` validates artifacts before returning. `assert_input_hashes_unchanged` re-hashes the same four files and raises `RuntimeError("Task 4A input changed during training")` on any difference.

- [ ] **Step 3: Write failing path-safety and atomic-claim tests**

Cover existing directories, files, dangling symlinks, project root, protected source/config/docs/tests/data/outputs paths, and two concurrent claim attempts. The concurrency test must show exactly one claim succeeds.

- [ ] **Step 4: Implement safe output resolution and claim**

Follow `src.preparation.resolve_output_layout` protections, adding the Task 4A input run itself as protected. Refuse broad or protected paths before model work. Claim the final `run_dir` with `mkdir(parents=True, exist_ok=False)` and then create fixed child directories.

- [ ] **Step 5: Write failing artifact-publication and manifest-last tests**

Use tiny frames and bytes instead of real models. Assert:

- config bytes are checked immediately before snapshot write;
- JSON uses `allow_nan=False`;
- CSV and JSON are written to temporary siblings and atomically replaced;
- model is saved inside `model/`;
- every final artifact has a row count where applicable, byte size, and SHA-256 in the manifest;
- `training_manifest.json` does not exist until every required artifact exists;
- a simulated write failure leaves no complete manifest and writes best-effort `failure.json`;
- an existing output entry is never overwritten.

- [ ] **Step 6: Implement publication helpers and schema `1.0`**

`write_training_artifacts` writes all non-manifest artifacts atomically. `publish_training_manifest` rechecks Task 4A hashes, verifies required output paths, hashes them, serializes software versions/effective parameters/features/sampling fractions/fold policy/working points/warnings, and atomically replaces the manifest last.

The manifest includes:

```json
{
  "schema_version": "1.0",
  "status": "complete",
  "input_task4a": {},
  "sampling_fractions": {"higgs": 1.0, "zz": 1.0},
  "features": [],
  "weight_policy": {},
  "cross_validation": {},
  "selected_model": {},
  "working_points": {},
  "software": {},
  "outputs": {}
}
```

- [ ] **Step 7: Run Task 4 safety tests and existing preparation/provenance tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_full_training_run.py tests/test_preparation.py tests/test_manifest.py tests/test_summary.py -q
```

Expected: all pass, including atomic run-directory regression coverage.

---

### Task 5: Produce the five frozen MC-only figures

**Files:**
- Create: `src/full_training_plots.py`
- Create: `tests/test_full_training_plots.py`

**Interfaces:**
- Produces: `save_full_training_plots(oof_frame, test_frame, cv_results, model, working_points, policy, output_dir)`.
- Consumes: frozen OOF/test scores and evaluation report; never accepts a data frame with label `-1`.

- [ ] **Step 1: Write failing plot-contract tests**

Use small synthetic frames and assert exactly these files are created and non-empty:

```text
roc_curve.png
score_distributions.png
cv_stability.png
feature_importance.png
mc_mass_sculpting.png
```

Also assert label `-1` or split `data` raises before importing plotting modules, plot titles say `MC`, mass axes cover the configured bins, and no path outside `output_dir` is written.

- [ ] **Step 2: Implement lazy plotting imports and deterministic plots**

Use a non-interactive backend, fixed figure dimensions, fixed bins, explicit weighted/unweighted labels, and close every figure. ROC uses test MC and absolute physical weights. Score distributions show OOF and test by class. CV stability shows all six candidates and five folds. Feature importance uses frozen `FEATURES` order. Mass sculpting shows inclusive/loose/medium/tight ZZ MC with OOF and test panels.

- [ ] **Step 3: Run plot and legacy plot tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_full_training_plots.py tests/test_validation.py -q
```

Expected: all pass with five non-empty PNGs.

---

### Task 6: Add the isolated Task 4B CLI and synthetic end-to-end test

**Files:**
- Create: `scripts/train_full_mc.py`
- Create: `tests/test_train_full_mc_script.py`
- Reuse: Tasks 1--5 modules.

**Interfaces:**
- CLI: `python -m scripts.train_full_mc --input-run PATH --config PATH --run-dir PATH`.
- Produces: the exact run layout in the approved specification.

- [ ] **Step 1: Write failing CLI preflight tests**

Patch input resolution, MC loading, and model fitting with recording forbidden
seams. Assert an existing/dangling run path fails before Task 4A input
resolution, MC loading, or fitting and does not mutate the existing entry.
Invalid config still fails before any input/output work, and invalid Task 4A input
still fails before any output claim.

- [ ] **Step 2: Write a failing no-real-data-access test**

Create a valid synthetic Task 4A input with only `processed/mc_events.csv.gz`. Patch `pandas.read_csv` to record every opened path. After successful CLI execution assert:

```python
assert opened_paths == [input_run / "processed/mc_events.csv.gz"]
assert not any("data_events" in str(path) for path in opened_paths)
```

Also assert no label `-1` reaches policy, fitting, evaluation, or plotting fakes.

- [ ] **Step 3: Implement orchestration in sealed order**

Post-Task-7B refusal correction (2026-08-11): the original implementation
resolved and validated the Task 4A input before checking whether `--run-dir`
already existed. The corrected sealed order adds a non-mutating output preflight
using the raw requested input path, then binds the output safety check again to
the validated, resolved Task 4A identity immediately before the atomic claim.
This records the correction without changing the scientific policy or the
history of the completed training run.

`main()` performs exactly:

1. parse required arguments;
2. read config bytes and validate policy;
3. run `resolve_training_output` with the raw requested input path solely as a
   non-mutating early output preflight;
4. resolve and validate the Task 4A input and snapshot its hashes;
5. re-run `resolve_training_output` using the validated, resolved Task 4A input
   identity so the output cannot overlap the actual input run;
6. atomically claim the Task 4B output;
7. read only `processed/mc_events.csv.gz`;
8. validate frame and reconcile counts;
9. run six-candidate CV;
10. freeze selection, final tree count, OOF working points, and effective parameters;
11. fit final model on development;
12. score final development rows for calibration drift;
13. score independent test exactly once;
14. evaluate and plot MC-only results;
15. write non-manifest artifacts;
16. recheck source config bytes and all Task 4A input hashes;
17. publish `training_manifest.json` last;
18. print selected candidate, final tree count, OOF AUC, test AUC, three thresholds, warning status, and output path.

Wrap stages after claim in exception handling that writes best-effort `failure.json`, re-raises the original exception, and never publishes a complete manifest.

- [ ] **Step 4: Write and pass a true tiny-XGBoost integration test**

In addition to fake orchestration tests, construct at least 10 events per class in every development fold and test. Use a test policy with two shallow candidates, small `n_estimators`, and small early stopping patience through an explicitly test-only policy factory; do not weaken production config validation. Run the real XGBoost path and assert model JSON, both prediction CSVs, metrics, working points, CV table, five plots, and final manifest exist and are finite.

- [ ] **Step 5: Run all new Task 4B tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_full_training_policy.py tests/test_full_training_model.py tests/test_full_training_evaluation.py tests/test_full_training_run.py tests/test_full_training_plots.py tests/test_train_full_mc_script.py -q
```

Expected: all Task 4B tests pass.

- [ ] **Step 6: Run the complete synthetic suite before touching the full baseline**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: every existing and new test passes. If any test fails, stop and use `superpowers:systematic-debugging`; do not start the full-MC command.

---

### Task 7: Run and audit the real full-MC Task 4B training

**Files:**
- Read only: `runs/full-baseline-2026-08-10/**`
- Create runtime artifacts only: `runs/full-training-2026-08-10/**`
- Do not modify tracked documentation in this task.

**Interfaces:**
- Consumes: the completed CLI and frozen config.
- Produces: the real frozen Task 4B run and an evidence log for Task 8 documentation.

- [ ] **Step 1: Capture pre-run immutability evidence**

Record path, byte size, modification time, and SHA-256 for every file under:

```text
runs/full-baseline-2026-08-10
data/raw
data/processed
outputs
```

Store the audit snapshot in a temporary directory created with `mktemp -d`, not inside any protected or output path. Confirm `runs/full-training-2026-08-10` is absent, including symlinks.

- [ ] **Step 2: Execute the exact approved full training command**

Run:

```bash
.venv/bin/python -m scripts.train_full_mc \
  --input-run runs/full-baseline-2026-08-10 \
  --config config/full_training.yaml \
  --run-dir runs/full-training-2026-08-10
```

Allow the process to complete. Send the user a concise progress update at least every 60 seconds if it remains active. Do not interrupt a healthy first run merely because cross-validation takes several minutes.

- [ ] **Step 3: Audit run layout, schemas, counts, and finite metrics**

Use a read-only Python assertion command to verify:

- exactly the approved config/model/artifact/prediction/plot paths exist;
- manifest status is complete and schema is `1.0`;
- OOF rows equal 281249 development events and test rows equal 70150 test events;
- label counts match the frozen table;
- no label `-1` or split `data` appears;
- six candidates times five fold rows exist;
- every AUC, threshold, yield, KS, and correlation value is finite where the schema requires a number;
- thresholds are ordered loose, medium, tight;
- feature list exactly matches `FEATURES` and excludes `m4l`;
- output hashes and input hashes match current files;
- sampling fractions are both `1.0`.

- [ ] **Step 4: Visually inspect the five MC-only plots**

Use the local image viewer for each PNG. Check labels are legible, all six candidates appear, distributions are not clipped, axes and legends are correct, and `mc_mass_sculpting.png` clearly says MC. Do not open any real-data plot or event table.

- [ ] **Step 5: Compare post-run immutability evidence**

Recompute the same audit for Task 4A, raw data, legacy processed data, and legacy outputs. Require exact equality of path, size, mtime, and SHA-256 snapshots. Any change is a release blocker.

- [ ] **Step 6: Rerun the real command against the same output path as a safety check**

Expected: fail before reading the MC table or fitting because the run directory exists. Verify every Task 4B artifact hash is unchanged after this refusal.

---

### Task 8: Document actual results and perform final verification

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/project/overview.md`
- Modify: `docs/roadmap/next-stage.md`
- Modify: `docs/README.md`
- Create: `tests/test_task4b_docs.py`
- Read: real Task 4B manifest and metrics.

**Interfaces:**
- Consumes: exact Task 7 outputs; no number may be guessed or copied from a synthetic run.
- Produces: final user-facing Task 4B handoff.

- [ ] **Step 1: Add failing documentation assertions**

Create `tests/test_task4b_docs.py`. It loads `README.md`, `AGENTS.md`,
`docs/project/overview.md`, and `docs/roadmap/next-stage.md`, then requires all
four primary documents to contain:

- the exact Task 4B command and run path;
- selected candidate and final tree count from the real manifest;
- OOF and independent test weighted AUC from real metrics;
- loose/medium/tight thresholds and achieved efficiencies;
- warning status and mass-sculpting diagnostic status;
- exact test count;
- explicit statements that real data was not read/scored and that no 125 GeV observation is claimed;
- the next task is data-period expansion and frozen-model blinded application, not Task 4B retuning.

The same test requires `docs/README.md` to link both
`2026-08-10-task-4b-full-mc-training-design.md` and
`2026-08-10-task-4b-full-mc-training.md`. Run the new test before editing docs
and confirm it fails on the first missing Task 4B completion statement.

- [ ] **Step 2: Update documents using only real artifact values**

Keep the historical 5,000-entry metrics clearly labeled. Mark Task 4B complete separately. Preserve Task 4A counts and hashes. State the 471-ZZ statistical limitation prominently.

- [ ] **Step 3: Run focused Task 4B tests after documentation edits**

Run:

```bash
.venv/bin/python -m pytest tests/test_full_training_policy.py tests/test_full_training_model.py tests/test_full_training_evaluation.py tests/test_full_training_run.py tests/test_full_training_plots.py tests/test_train_full_mc_script.py tests/test_task4b_docs.py -q
```

Expected: all pass.

- [ ] **Step 4: Run the complete suite with fresh evidence**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: all pass. Record exact passed count and elapsed time.

- [ ] **Step 5: Perform final static safety scans**

Run separate read-only searches confirming:

```text
m4l is absent from FEATURES
train_full_mc never references data_events or evaluate_data
historical threshold 0.93 is absent from Task 4B code/config
test metrics are not arguments to candidate or working-point selection
no Task 4B code writes data/processed or outputs
```

Inspect every match rather than relying only on zero/one match counts.

- [ ] **Step 6: Perform final artifact and worktree audit**

Verify real Task 4B hashes again, confirm no partial temporary files remain, inspect `git status --short`, and list every source/document file changed by Task 4B. Do not stage or commit.

- [ ] **Step 7: Use verification-before-completion before reporting success**

Read and follow `superpowers:verification-before-completion`. The final response reports:

- Task 4B completion status;
- selected candidate, tree count, OOF/test AUC, thresholds, and warnings;
- direct links to the five plots, metrics, manifest, specification, plan, and primary CLI/code files;
- exact focused and full pytest evidence;
- Task 4A/legacy immutability result;
- explicit confirmation that no real data was read or scored;
- the scientific limitation that Task 4B cannot itself guarantee a visible 125 GeV peak.

Do not call the result a Higgs discovery, measurement, or ATLAS-quality analysis.
