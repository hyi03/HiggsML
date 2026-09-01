# DropTop4 KNN Flatness Training Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and execute one immutable MC-only DropTop4 classifier study whose native KNN flatness loss suppresses continuum-ZZ `m4l` sculpting while preserving the frozen OOF AUC and three-working-point KS gates.

**Architecture:** Add a pure development-only flatness-training layer around `hep_ml.UGradientBoostingClassifier`, then place it behind a hardened run/publishing layer that reuses the repository's source receipts, no-clobber directories, conditional artifact contracts, and manifest-last publication. Candidate OOF evaluation receives only development rows; a separate one-shot test gate is invoked only when deterministic OOF selection returns an eligible candidate.

**Tech Stack:** Python 3.12, pandas, NumPy, scikit-learn, matplotlib, `hep_ml==0.8.0`, pytest, PyYAML

**Spec:** `docs/superpowers/specs/2026-08-24-drop-top4-knn-flatness-training-design.md`

## Global Constraints

- Use exactly the ordered DropTop4 features: `lep1_pt`, `lep2_pt`, `lep1_eta`, `lep2_eta`, `lep3_eta`, `lep4_eta`, `pt4l`, `deltaR_Z1`, `deltaR_Z2`, `deltaPhi_ZZ`.
- `m4l` is available only to `KnnFlatnessLossFunction`; it must never appear in a tree feature matrix.
- Use exactly five development folds and flatness coefficients `0.0`, `0.5`, `1.0`, `2.0`, `3.0`.
- Freeze `n_estimators=300`, `learning_rate=0.05`, `max_depth=3`, `min_samples_leaf=50`, `subsample=0.8`, and `random_seed=42`.
- Freeze `n_neighbours=100`, `max_groups=5000`, `power=2.0`, `uniform_label=0`, and `allow_wrong_signs=true`.
- Eligibility requires weighted OOF AUC `>= 0.80`, every OOF ZZ mass KS `<= 0.10`, and signal efficiency strictly above background efficiency at loose `0.50`, medium `0.20`, and tight `0.10`.
- Candidate fitting and selection may use only development OOF evidence. Held-out MC test opens once only after an eligible selection; it never feeds back into training or selection.
- Do not read, hash, score, plot, or inventory `data_events.csv.gz`, `data16_periodA.root`, or any other real-data path.
- Do not modify or reuse any frozen run. The production path is `runs/decorrelation-drop-top4-363490-2026-08-24` and must be absent before its single execution.
- Every production-code behavior begins with a failing test. Run focused tests after each change and the complete suite before the production run.

---

## File Structure

- `requirements.txt`: add the exact `hep_ml==0.8.0` dependency.
- `config/decorrelation_training_drop_top4.yaml`: immutable source binding, model/loss policy, gates, and artifact allowlists.
- `src/provenance.py`: include `hep_ml` in recorded software versions.
- `src/decorrelation_training.py`: feature policy, model construction, fold-local weights, OOF generation, metrics, selection, final development fit, and one-shot test scoring.
- `src/decorrelation_training_plots.py`: candidate trade-off, per-working-point KS, and conditional selected OOF/test mass-shape PNG builders.
- `src/decorrelation_training_run.py`: config schema, explicit MC-only source inventory, semantic development/test partition, no-clobber publication, pickle serialization, terminal failure handling, and manifest-last publication.
- `scripts/run_decorrelation_training.py`: production CLI and conversion from domain outcomes to approved artifacts.
- `tests/test_decorrelation_training.py`: pure training, OOF, metric, eligibility, and test-gate tests.
- `tests/test_decorrelation_training_plots.py`: plot validation and PNG tests.
- `tests/test_decorrelation_training_run.py`: config, sources, partition, output, manifest, and failure-path tests.
- `tests/test_run_decorrelation_training_script.py`: CLI ordering, test-opening, and artifact-builder tests.
- `tests/test_manifest.py`: `hep_ml` provenance expectation.
- `docs/superpowers/plans/2026-08-24-drop-top4-knn-flatness-training-report.md`: verified execution evidence and exact terminal result.

---

### Task 1: Freeze the dependency, provenance, and study configuration

**Files:**
- Modify: `requirements.txt`
- Create: `config/decorrelation_training_drop_top4.yaml`
- Modify: `src/provenance.py`
- Modify: `tests/test_manifest.py`
- Create: `tests/test_decorrelation_training_run.py`

**Interfaces:**
- Produces: `DecorrelationConfig`, `load_decorrelation_config(path)`, `approved_decorrelation_artifacts(selected: bool)`, and software metadata containing `hep_ml`.
- Consumes: existing `TrainingInput`, `TrainingOutputLayout`, and Task 4A source hashes.

- [ ] **Step 1: Write failing provenance and exact-config tests**

Add `hep_ml` to the expected mapping in `tests/test_manifest.py`:

```python
assert software_versions() == {
    "python": "3.12.9",
    "numpy": "version-of-numpy",
    "pandas": "version-of-pandas",
    "pyyaml": "version-of-PyYAML",
    "uproot": "version-of-uproot",
    "xgboost": "unavailable",
    "scikit-learn": "version-of-scikit-learn",
    "hep_ml": "version-of-hep-ml",
}
assert requested[-1] == "hep-ml"
```

Create `tests/test_decorrelation_training_run.py` with the initial contract tests:

```python
from pathlib import Path

import pytest

from src.decorrelation_training_run import (
    approved_decorrelation_artifacts,
    load_decorrelation_config,
)


def test_production_config_freezes_every_approved_decision():
    config = load_decorrelation_config(
        Path("config/decorrelation_training_drop_top4.yaml")
    )
    assert config.input_run == "runs/full-baseline-363490-2026-08-11-r2"
    assert config.input_manifest_sha256 == (
        "10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8"
    )
    assert config.input_mc_sha256 == (
        "1c5d6a3f9a750a5eb9965241dd8947d70e790cf949a36f8fa6ec1bfd058f378e"
    )
    assert config.coefficients == (0.0, 0.5, 1.0, 2.0, 3.0)
    assert config.auc_floor == 0.80
    assert config.ks_limit == 0.10
    assert config.require_signal_efficiency_above_background is True
    assert set(config.artifacts_no_selection) == approved_decorrelation_artifacts(
        selected=False
    )
    assert set(config.artifacts_selected) == approved_decorrelation_artifacts(
        selected=True
    )


def test_config_rejects_changed_coefficient(tmp_path):
    source = Path("config/decorrelation_training_drop_top4.yaml").read_text()
    changed = tmp_path / "changed.yaml"
    changed.write_text(source.replace("  - 3.0\n", "  - 4.0\n"))
    with pytest.raises(ValueError, match="frozen decision"):
        load_decorrelation_config(changed)
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_manifest.py::test_software_versions_uses_distribution_metadata tests/test_decorrelation_training_run.py -q
```

Expected: collection fails because `src.decorrelation_training_run` does not exist, and the provenance assertion lacks `hep_ml`.

- [ ] **Step 3: Add the exact dependency and configuration**

Append this exact line to `requirements.txt`:

```text
hep_ml==0.8.0
```

Create `config/decorrelation_training_drop_top4.yaml`:

```yaml
schema_version: "1.0"
input_run: runs/full-baseline-363490-2026-08-11-r2
input_manifest_sha256: 10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8
input_mc_sha256: 1c5d6a3f9a750a5eb9965241dd8947d70e790cf949a36f8fa6ec1bfd058f378e
features:
  - lep1_pt
  - lep2_pt
  - lep1_eta
  - lep2_eta
  - lep3_eta
  - lep4_eta
  - pt4l
  - deltaR_Z1
  - deltaR_Z2
  - deltaPhi_ZZ
folds: 5
model:
  type: hep_ml.UGradientBoostingClassifier
  n_estimators: 300
  learning_rate: 0.05
  max_depth: 3
  min_samples_leaf: 50
  subsample: 0.8
  random_seed: 42
flatness:
  type: hep_ml.losses.KnnFlatnessLossFunction
  uniform_feature: m4l
  uniform_label: 0
  n_neighbours: 100
  max_groups: 5000
  power: 2.0
  allow_wrong_signs: true
coefficients: [0.0, 0.5, 1.0, 2.0, 3.0]
working_points:
  loose: 0.50
  medium: 0.20
  tight: 0.10
auc_floor: 0.80
ks_limit: 0.10
require_signal_efficiency_above_background: true
artifacts_no_selection:
  - artifacts/candidate_results.csv
  - artifacts/working_point_metrics.csv
  - artifacts/selection.json
  - predictions/oof_scores.csv.gz
  - plots/candidate_tradeoff.png
  - plots/working_point_ks.png
artifacts_selected:
  - artifacts/candidate_results.csv
  - artifacts/working_point_metrics.csv
  - artifacts/selection.json
  - artifacts/test_metrics.json
  - model/flatness_model.pkl
  - predictions/oof_scores.csv.gz
  - predictions/selected_oof_scores.csv.gz
  - predictions/test_scores.csv.gz
  - plots/candidate_tradeoff.png
  - plots/working_point_ks.png
  - plots/selected_mass_sculpting.png
```

Add `"hep_ml": "hep-ml"` to `_DISTRIBUTIONS` in `src/provenance.py`.

Create the config dataclass and strict loader in
`src/decorrelation_training_run.py`. Validate exact top-level keys, exact nested
keys and values, exact feature order, exact coefficient order, exact hashes,
and exact conditional artifact sets. Return immutable tuples and mapping
proxies.

- [ ] **Step 4: Install the dependency and verify GREEN**

Run:

```bash
.venv/bin/python -m pip install hep_ml==0.8.0
.venv/bin/python -m pytest tests/test_manifest.py::test_software_versions_uses_distribution_metadata tests/test_decorrelation_training_run.py -q
```

Expected: all selected tests pass, and `.venv/bin/python -c "import hep_ml; print(hep_ml.__version__)"` prints `0.8.0`.

- [ ] **Step 5: Commit Task 1**

```bash
git add requirements.txt config/decorrelation_training_drop_top4.yaml src/provenance.py src/decorrelation_training_run.py tests/test_manifest.py tests/test_decorrelation_training_run.py
git commit -m "feat: freeze flatness training policy"
```

---

### Task 2: Implement DropTop4 flatness models and deterministic OOF scoring

**Files:**
- Create: `src/decorrelation_training.py`
- Create: `tests/test_decorrelation_training.py`

**Interfaces:**
- Consumes: `DecorrelationConfig`, `assign_development_folds`, `class_balanced_training_weights`.
- Produces: `DROP_TOP4_FEATURES`, `build_flatness_model(config, coefficient, model_factory=None)`, and `generate_flatness_oof(development, config, coefficient, model_factory=None)`.

- [ ] **Step 1: Write failing feature-boundary and model-construction tests**

Create `tests/test_decorrelation_training.py`:

```python
from types import SimpleNamespace

import numpy as np
import pandas as pd

from src.decorrelation_training import (
    DROP_TOP4_FEATURES,
    build_flatness_model,
    generate_flatness_oof,
)


def test_model_exposes_mass_to_loss_but_not_to_trees(production_config):
    captured = {}

    def factory(**kwargs):
        captured.update(kwargs)
        return object()

    build_flatness_model(production_config, 1.0, model_factory=factory)
    assert captured["train_features"] == list(DROP_TOP4_FEATURES)
    assert "m4l" not in captured["train_features"]
    loss = captured["loss"]
    assert loss.uniform_features == ["m4l"]
    assert np.array_equal(loss.uniform_label, np.array([0]))
    assert loss.fl_coefficient == 1.0


def test_oof_scores_every_development_row_once_and_rebalances_each_fold(
    development_frame, production_config
):
    fitted_indices = []

    class FakeModel:
        def fit(self, X, y, sample_weight):
            assert list(X.columns) == [*DROP_TOP4_FEATURES, "m4l"]
            fitted_indices.append(tuple(X.index))
            labels = y.to_numpy(dtype=int)
            totals = [sample_weight[labels == label].sum() for label in (0, 1)]
            assert np.isclose(totals[0], totals[1])
            return self

        def predict_proba(self, X):
            score = np.linspace(0.1, 0.9, len(X))
            return np.column_stack([1.0 - score, score])

    oof = generate_flatness_oof(
        development_frame,
        production_config,
        0.5,
        model_factory=lambda **kwargs: FakeModel(),
    )
    assert oof.index.equals(development_frame.index)
    assert oof["development_fold"].between(0, 4).all()
    assert np.isfinite(oof["score_lambda_0p5"]).all()
    assert len(fitted_indices) == 5
```

Define these concrete fixtures in the same test file:

```python
@pytest.fixture
def production_config():
    return load_decorrelation_config(
        Path("config/decorrelation_training_drop_top4.yaml")
    )


@pytest.fixture
def development_frame():
    rows = []
    event = 1
    counts = {(fold, label): 0 for fold in range(5) for label in (0, 1)}
    while min(counts.values()) < 3:
        for label in (0, 1):
            channel = 363490 if label == 0 else 345060
            event_number = event * 2 + label
            fold = development_fold(channel, event_number, folds=5)
            if counts[(fold, label)] >= 3:
                continue
            row = {name: float(event + offset) for offset, name in enumerate(FEATURES)}
            row.update({
                "m4l": 105.0 + event % 55,
                "eventNumber": event_number,
                "channelNumber": channel,
                "split": "train" if event % 2 else "validation",
                "label": label,
                "physical_weight": (-1.0 if event % 7 == 0 else 1.0) * (1.0 + label),
            })
            rows.append(row)
            counts[(fold, label)] += 1
        event += 1
    frame = pd.DataFrame(rows)
    # If either semantic development split lacks a label, deterministically
    # flip one same-label row's split; identifiers and fold assignment stay fixed.
    for split in ("train", "validation"):
        for label in (0, 1):
            if not ((frame["split"] == split) & (frame["label"] == label)).any():
                index = frame.index[frame["label"] == label][0]
                frame.loc[index, "split"] = split
    return frame
```

Import `Path`, `pytest`, `FEATURES`, `development_fold`, and
`load_decorrelation_config` explicitly. Before accepting this fixture, assert
that `assign_development_folds(frame).groupby(frame["label"]).nunique()` is
`5` for both labels.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_decorrelation_training.py -q
```

Expected: import or attribute failures for the unimplemented training module.

- [ ] **Step 3: Implement the minimal model and OOF layer**

In `src/decorrelation_training.py`, define the exact feature tuple and a lazy
default model factory:

```python
DROP_TOP4_FEATURES = (
    "lep1_pt", "lep2_pt", "lep1_eta", "lep2_eta", "lep3_eta",
    "lep4_eta", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
)


def _default_model_factory(**kwargs):
    from hep_ml.gradientboosting import UGradientBoostingClassifier
    return UGradientBoostingClassifier(**kwargs)
```

`build_flatness_model` imports `KnnFlatnessLossFunction`, validates the
coefficient against the frozen tuple, creates the loss from config, and passes
these exact arguments to the factory:

```python
return factory(
    loss=loss,
    n_estimators=300,
    learning_rate=0.05,
    max_depth=3,
    min_samples_leaf=50,
    subsample=0.8,
    train_features=list(DROP_TOP4_FEATURES),
    random_state=42,
)
```

`generate_flatness_oof` must:

1. call `validate_development_frame`;
2. compute folds with `assign_development_folds`;
3. for each fold, recompute `class_balanced_training_weights` on only the four
   fit folds;
4. fit using columns `[*DROP_TOP4_FEATURES, "m4l"]`;
5. score only the held-out fold;
6. reject non-finite or incorrectly shaped probabilities; and
7. return an audit frame in original index order with identity, label, split,
   physical weight, mass, fold, and coefficient-specific score.

- [ ] **Step 4: Run focused and compatibility tests**

```bash
.venv/bin/python -m pytest tests/test_decorrelation_training.py tests/test_full_training_policy.py tests/test_full_training_evaluation.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/decorrelation_training.py tests/test_decorrelation_training.py
git commit -m "feat: generate flatness OOF scores"
```

---

### Task 3: Implement metrics, qualification, deterministic selection, and the one-shot test gate

**Files:**
- Modify: `src/decorrelation_training.py`
- Modify: `tests/test_decorrelation_training.py`

**Interfaces:**
- Produces: `FlatnessCandidateResult`, `FlatnessSelection`, `SelectedFlatnessEvidence`, `FlatnessOutcome`, `evaluate_flatness_candidate`, `select_flatness_candidate`, `run_development_study`, `fit_selected_and_score_test`, and `OneShotTestGate`.
- Consumes: `build_working_points`, `zz_mass_diagnostics`, `weighted_pearson`, and `roc_auc_score`.

- [ ] **Step 1: Write failing boundary, tie-break, and gate tests**

Add tests that construct result dataclasses through this production classmethod:

```python
FlatnessCandidateResult.from_metrics(
    *,
    coefficient: float,
    weighted_auc: float,
    background_score_mass_correlation: float,
    working_points: Mapping[str, Mapping[str, object]],
    zz_ks_distances: Mapping[str, float],
    config: DecorrelationConfig,
    oof_scores: pd.DataFrame,
) -> FlatnessCandidateResult
```

The test-local `candidate_result` fixture is a factory around that classmethod.
It builds loose/medium/tight working-point dictionaries with achieved
background efficiencies `0.50`, `0.20`, and `0.10`; accepts optional `ks`,
`signal`, and `maximum_ks`; when only `maximum_ks` is provided it assigns that
value to tight and `maximum_ks / 2` to loose and medium. It supplies a copied
valid OOF audit fixture and a finite correlation of `0.0`. Define
`eligible_selection` as
`FlatnessSelection(results=(candidate,), selected=candidate)` using a candidate
with AUC `0.82`, every KS `0.05`, and signal efficiencies `0.75`, `0.45`, and
`0.25`. Define `test_frame` by deep-copying `development_frame`, setting every
split to `test`, and reassigning fresh collision-free event identifiers.

Then add these tests:

```python
def test_candidate_requires_every_frozen_gate(candidate_result):
    eligible = candidate_result(
        coefficient=1.0,
        auc=0.80,
        ks={"loose": 0.10, "medium": 0.10, "tight": 0.10},
        signal={"loose": 0.51, "medium": 0.21, "tight": 0.11},
    )
    assert eligible.eligibility_reasons == ()

    failed = candidate_result(
        coefficient=2.0,
        auc=np.nextafter(0.80, 0.0),
        ks={"loose": 0.10, "medium": 0.10, "tight": 0.10},
        signal={"loose": 0.51, "medium": 0.21, "tight": 0.11},
    )
    assert failed.eligibility_reasons == ("weighted_auc_below_floor",)


def test_selection_uses_auc_then_maximum_ks_then_lower_coefficient(candidate_result):
    results = [
        candidate_result(coefficient=2.0, auc=0.82, maximum_ks=0.08),
        candidate_result(coefficient=1.0, auc=0.82, maximum_ks=0.07),
        candidate_result(coefficient=0.5, auc=0.82, maximum_ks=0.07),
    ]
    assert select_flatness_candidate(results).selected.coefficient == 0.5


def test_no_eligible_candidate_never_opens_test(development_frame, production_config):
    calls = []
    gate = OneShotTestGate(lambda: calls.append("opened") or pd.DataFrame())
    selection = FlatnessSelection(results=(), selected=None)
    outcome = fit_selected_and_score_test(
        development_frame, gate, production_config, selection
    )
    assert outcome.evidence is None
    assert calls == []


def test_selected_candidate_opens_test_exactly_once(
    development_frame, test_frame, production_config, eligible_selection,
    monkeypatch,
):
    class FakeModel:
        def fit(self, X, y, sample_weight):
            return self

        def predict_proba(self, X):
            score = np.linspace(0.1, 0.9, len(X))
            return np.column_stack([1.0 - score, score])

    monkeypatch.setattr(
        "src.decorrelation_training.build_flatness_model",
        lambda config, coefficient: FakeModel(),
    )
    calls = []

    def test_loader():
        calls.append("opened")
        return test_frame.copy(deep=True)

    gate = OneShotTestGate(test_loader)
    evidence = fit_selected_and_score_test(
        development_frame, gate, production_config, eligible_selection
    ).evidence
    assert evidence is not None
    assert calls == ["opened"]
    with pytest.raises(RuntimeError, match="already opened"):
        gate.open()
```

Define `test_evaluate_candidate_matches_validated_metric_helpers` with a
12-row scored frame containing both labels, nonuniform positive/negative
`physical_weight`, distinct `m4l`, and score column `score_lambda_1p0`.
Rename that column to `oof_score` when passing it independently to
`build_working_points`; calculate expected AUC with
`roc_auc_score(label, score, sample_weight=abs(physical_weight))`, expected
background correlation with `weighted_pearson`, and each expected KS with
`zz_mass_diagnostics`. Assert exact equality to the corresponding fields of
`evaluate_flatness_candidate(frame, production_config, coefficient=1.0)`.

- [ ] **Step 2: Run the tests and verify RED**

```bash
.venv/bin/python -m pytest tests/test_decorrelation_training.py -q
```

Expected: failures for missing result classes, selection, and test gate.

- [ ] **Step 3: Implement result snapshots and selection**

Use frozen dataclasses. `FlatnessCandidateResult.from_metrics` validates and
snapshots its arguments, derives achieved/signal efficiencies from the three
working-point dictionaries, computes eligibility reasons from the supplied
config, and returns a `FlatnessCandidateResult`. The result contains coefficient, weighted
AUC, weighted background score-mass correlation, working points, signal
efficiencies, target background efficiencies, ZZ KS values, eligibility
reasons, and its OOF audit frame. Snapshot mappings with `MappingProxyType` and
copy DataFrames before returning public outcomes.

Eligibility reason order is fixed:

```python
reasons = []
if weighted_auc < 0.80:
    reasons.append("weighted_auc_below_floor")
for name in ("loose", "medium", "tight"):
    if zz_ks_distances[name] > 0.10:
        reasons.append(f"{name}_zz_mass_ks_exceeds_limit")
for name in ("loose", "medium", "tight"):
    if signal_efficiencies[name] <= target_background_efficiencies[name]:
        reasons.append(f"{name}_signal_efficiency_not_above_background")
```

Select with the exact full-precision key:

```python
min(eligible, key=lambda result: (
    -result.weighted_auc,
    max(result.zz_ks_distances.values()),
    result.coefficient,
))
```

`run_development_study` loops over the five frozen coefficients, builds each
OOF audit, evaluates it, and returns one selection. It never receives a test
frame or loader.

- [ ] **Step 4: Implement final development fit and one-shot test scoring**

`OneShotTestGate` stores a zero-argument loader and raises on its second call.
`fit_selected_and_score_test` returns immediately when selection is empty.
Otherwise it:

1. fits exactly one selected model to all development rows with newly computed
   class-balanced weights;
2. calls the gate once;
3. validates the test frame;
4. scores it with the same ten features;
5. computes test AUC, efficiencies, correlation, and mass KS using frozen OOF
   thresholds; and
6. returns evidence without changing the selection.

Run:

```bash
.venv/bin/python -m pytest tests/test_decorrelation_training.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add src/decorrelation_training.py tests/test_decorrelation_training.py
git commit -m "feat: gate flatness candidate selection"
```

---

### Task 4: Build MC-only plots and artifact tables

**Files:**
- Create: `src/decorrelation_training_plots.py`
- Create: `tests/test_decorrelation_training_plots.py`
- Create: `scripts/run_decorrelation_training.py`
- Create: `tests/test_run_decorrelation_training_script.py`

**Interfaces:**
- Produces: `plot_candidate_tradeoff`, `plot_working_point_ks`, `plot_selected_mass_sculpting`, and `build_decorrelation_artifacts(outcome, config)`.
- Consumes: frozen domain outcomes from Task 3.

- [ ] **Step 1: Write failing plot and artifact-shape tests**

Create PNG signature tests:

```python
PNG = b"\x89PNG\r\n\x1a\n"


def test_common_plots_are_mc_only_pngs(candidate_results):
    assert plot_candidate_tradeoff(candidate_results).startswith(PNG)
    assert plot_working_point_ks(candidate_results).startswith(PNG)


def test_mass_plot_requires_exact_working_points(oof_scores, test_scores):
    with pytest.raises(ValueError, match="exactly loose, medium, and tight"):
        plot_selected_mass_sculpting(
            oof_scores, test_scores, {"loose": {"threshold": 0.5}},
            mass_bins_gev=(105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160),
        )
```

Create artifact-builder tests:

```python
def test_no_selection_artifacts_include_all_oof_audits_and_no_test(candidate_outcome, config):
    artifacts = build_decorrelation_artifacts(candidate_outcome, config)
    assert artifacts["selection"] == {
        "schema_version": "1.0",
        "status": "no_eligible_candidate",
        "selected_candidate": None,
        "test_opened": False,
        "auc_floor": 0.80,
        "ks_limit": 0.10,
    }
    assert set(artifacts["plot_artifacts"]) == {
        "candidate_tradeoff.png", "working_point_ks.png"
    }
    assert artifacts["model"] is None
    assert artifacts["test_scores"] is None


def test_selected_artifacts_report_test_without_reselecting(selected_outcome, config):
    artifacts = build_decorrelation_artifacts(selected_outcome, config)
    assert artifacts["selection"]["selected_candidate"] == "lambda_1p0"
    assert artifacts["selection"]["test_opened"] is True
    assert set(artifacts["plot_artifacts"]) == {
        "candidate_tradeoff.png", "working_point_ks.png",
        "selected_mass_sculpting.png",
    }
```

- [ ] **Step 2: Run the tests and verify RED**

```bash
.venv/bin/python -m pytest tests/test_decorrelation_training_plots.py tests/test_run_decorrelation_training_script.py -q
```

Expected: missing-module or missing-function failures.

- [ ] **Step 3: Implement validated plot byte builders**

Follow `mass_sculpting_ablation_plots.py` patterns. Both common plots draw the
fixed AUC `0.80` and KS `0.10` boundaries, label coefficients, validate finite
values, close figures, and return PNG bytes. The selected mass plot has OOF and
test panels, includes only label-0 ZZ MC, uses absolute physical weights and
unit-area shapes, and draws inclusive plus loose/medium/tight selections.

- [ ] **Step 4: Implement deterministic artifact conversion**

`build_decorrelation_artifacts` produces:

- one `candidate_results` row per coefficient with AUC, maximum KS,
  correlation, eligibility, and ordered reasons;
- three `working_point_metrics` rows per coefficient;
- one wide `oof_scores` frame keyed by event identity and containing every
  coefficient score;
- `selection` with the exact no-selection or selected status;
- conditional selected model, selected OOF scores, test scores, test metrics,
  and selected mass plot.

Candidate names use `lambda_0p0`, `lambda_0p5`, `lambda_1p0`, `lambda_2p0`, and
`lambda_3p0`. Preserve full-precision numeric values in tables and JSON.

Run:

```bash
.venv/bin/python -m pytest tests/test_decorrelation_training_plots.py tests/test_run_decorrelation_training_script.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add src/decorrelation_training_plots.py scripts/run_decorrelation_training.py tests/test_decorrelation_training_plots.py tests/test_run_decorrelation_training_script.py
git commit -m "feat: build flatness study artifacts"
```

---

### Task 5: Harden source binding, semantic test isolation, and terminal publication

**Files:**
- Modify: `src/decorrelation_training_run.py`
- Modify: `tests/test_decorrelation_training_run.py`

**Interfaces:**
- Produces: `DecorrelationSources`, `StudySource`, `MCStudyPartitions`, `resolve_decorrelation_sources`, `resolve_decorrelation_output`, `claim_decorrelation_output`, `write_decorrelation_artifacts`, `publish_decorrelation_manifest`, `record_decorrelation_failure`, and `assert_decorrelation_sources_unchanged`.
- Consumes: hardened private helpers already used by `mass_sculpting_ablation_run.py` and `full_training_run.py`.

- [ ] **Step 1: Write failing source-inventory and test-isolation tests**

Add tests that use the existing synthetic Task 4A fixture:

```python
def test_source_inventory_is_explicitly_mc_only(tmp_path, synthetic_task4a_run):
    sources = resolve_decorrelation_sources(
        input_run=synthetic_task4a_run,
        config_path=_bound_config(tmp_path, synthetic_task4a_run),
    )
    assert set(sources.records) == {
        "study_config", "task4a_config", "task4a_mc",
        "task4a_summary", "task4a_manifest",
    }
    assert all("data_events" not in str(source.path) for source in sources.records.values())
    assert all("periodA" not in str(source.path) for source in sources.records.values())


def test_partitions_expose_development_and_open_test_once(mc_frame):
    partitions = MCStudyPartitions.from_frame(mc_frame)
    assert set(partitions.development["split"]) == {"train", "validation"}
    first = partitions.open_test()
    assert set(first["split"]) == {"test"}
    with pytest.raises(RuntimeError, match="already opened"):
        partitions.open_test()
```

Add these separately named output tests so each failure identifies one
contract: `test_no_selection_writes_exact_common_artifacts`,
`test_selection_writes_exact_conditional_artifacts`,
`test_csv_gzip_is_byte_deterministic`,
`test_model_pickle_round_trip_preserves_verification_predictions`,
`test_source_mutation_blocks_manifest`,
`test_decision_artifact_contradiction_is_rejected`,
`test_existing_output_path_is_rejected_before_claim`,
`test_foreign_output_receipt_is_rejected`, and
`test_manifest_is_newer_than_every_published_artifact`. In the two artifact
tests compare recursive relative paths against `_COMMON_ARTIFACTS` plus
`config.yaml` and `artifacts/study_manifest.json`, conditionally unioned with
`_SELECTED_ARTIFACTS`. In the mutation test replace the explicitly bound
`task4a_summary` after resolution and assert
`assert_decorrelation_sources_unchanged` raises. In the pickle test deserialize
only bytes created by the test's locally fitted model and compare
`predict_proba` arrays with `np.testing.assert_allclose`.

- [ ] **Step 2: Run the tests and verify RED**

```bash
.venv/bin/python -m pytest tests/test_decorrelation_training_run.py -q
```

Expected: missing source, partition, and publisher interfaces.

- [ ] **Step 3: Implement MC-only source resolution and partitions**

Reuse `_resolve_task4a_sources_without_table_load` logic but keep only these
source keys:

```python
_SOURCE_KEYS = frozenset({
    "study_config", "task4a_config", "task4a_mc",
    "task4a_summary", "task4a_manifest",
})
```

Resolve exact safe regular files, capture config/summary/manifest bytes, validate
Task 4A manifest receipts, require the configured manifest and MC hashes, and
recheck every source after resolution and before manifest promotion. Never walk
or hash the input run directory.

`MCStudyPartitions.from_frame` validates the complete MC frame once, stores
private deep copies of development and test, exposes a deep development copy,
and allows one deep test copy through `open_test`. It does not expose the
private test frame through a public attribute.

- [ ] **Step 4: Implement conditional writes and manifest-last publication**

The common artifact set is:

```python
_COMMON_ARTIFACTS = frozenset({
    "artifacts/candidate_results.csv",
    "artifacts/working_point_metrics.csv",
    "artifacts/selection.json",
    "predictions/oof_scores.csv.gz",
    "plots/candidate_tradeoff.png",
    "plots/working_point_ks.png",
})
```

The selected-only set is:

```python
_SELECTED_ARTIFACTS = frozenset({
    "artifacts/test_metrics.json",
    "model/flatness_model.pkl",
    "predictions/selected_oof_scores.csv.gz",
    "predictions/test_scores.csv.gz",
    "plots/selected_mass_sculpting.png",
})
```

Serialize tables with the existing deterministic gzip helper. Serialize the
trusted local `hep_ml` model with `pickle.dumps(model, protocol=5)`, immediately
round-trip it with `pickle.loads`, and verify identical predictions on a small
stored verification matrix before publishing bytes. Never expose a CLI option
that loads an arbitrary pickle.

Reuse descriptor-relative atomic writes, directory identity checks, terminal
locks, conditional allowlist validation, failure installation, staged manifest
verification, final source recheck, final output receipt recheck, and
manifest-last promotion from the existing run modules.

Manifest software validation requires `software["hep_ml"] == "0.8.0"`.

Run:

```bash
.venv/bin/python -m pytest tests/test_decorrelation_training_run.py tests/test_full_training_run.py tests/test_mass_sculpting_ablation_run.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 5**

```bash
git add src/decorrelation_training_run.py tests/test_decorrelation_training_run.py
git commit -m "feat: publish immutable flatness studies"
```

---

### Task 6: Wire the production CLI and synthetic end-to-end execution

**Files:**
- Modify: `scripts/run_decorrelation_training.py`
- Modify: `tests/test_run_decorrelation_training_script.py`
- Modify: `tests/test_decorrelation_training_run.py`

**Interfaces:**
- Produces: `main(argv=None) -> int` for `python -m scripts.run_decorrelation_training`.
- Consumes: every approved interface from Tasks 1–5.

- [ ] **Step 1: Write failing orchestration-order tests**

Use monkeypatches to record this exact sequence:

```python
assert stages == [
    "output_preflight",
    "source_resolve",
    "output_rebind",
    "output_claim",
    "mc_load",
    "partition",
    "development_study",
    "selected_test_gate",
    "build_artifacts",
    "write_artifacts",
    "source_recheck",
    "publish_manifest",
]
```

Add `test_no_selection_skips_selected_test_gate` with the same stage recorder
and the exact sequence above minus `"selected_test_gate"`. Add
`test_occupied_output_fails_before_source_resolution`, monkeypatching source
resolution to raise if called; `test_post_claim_error_installs_failure`,
injecting `RuntimeError("study failed")` from `run_development_study` and
asserting `.terminal.failed` plus `failure.json`; and
`test_parser_exposes_only_frozen_paths`, asserting parser actions expose only
`help`, `input_run`, `config`, and `run_dir`. Explicitly assert parsing
`--data`, `--test`, or `--model` exits with code `2`.

- [ ] **Step 2: Run the tests and verify RED**

```bash
.venv/bin/python -m pytest tests/test_run_decorrelation_training_script.py -q
```

Expected: ordering and parser tests fail against the incomplete CLI.

- [ ] **Step 3: Implement the CLI**

The command performs:

```python
project_root = Path(__file__).resolve().parents[1]
working_directory = Path.cwd()
resolve_decorrelation_output(                 # preflight before inputs
    project_root=project_root,
    working_directory=working_directory,
    input_run=args.input_run,
    run_dir=args.run_dir,
)
sources = resolve_decorrelation_sources(
    input_run=args.input_run,
    config_path=args.config,
)
layout = resolve_decorrelation_output(        # rebind canonical paths
    project_root=project_root,
    working_directory=working_directory,
    input_run=sources.training_input.input_run,
    run_dir=args.run_dir,
)
layout = claim_decorrelation_output(layout)
frame = load_training_mc_frame(sources.training_input)
partitions = MCStudyPartitions.from_frame(frame)
selection = run_development_study(partitions.development, sources.config)
outcome = fit_selected_and_score_test(
    partitions.development,
    OneShotTestGate(partitions.open_test),
    sources.config,
    selection,
)
artifacts = build_decorrelation_artifacts(outcome, sources.config)
receipt = write_decorrelation_artifacts(
    layout=layout,
    config_bytes=sources.config_bytes,
    artifacts=artifacts,
)
assert_decorrelation_sources_unchanged(sources)
publish_decorrelation_manifest(
    layout=layout,
    sources=sources,
    outcome=outcome,
    receipt=receipt,
    software=software_versions(),
)
```

Wrap every post-claim operation in `try/except`, call
`record_decorrelation_failure(layout, error)`, then re-raise. Print only status,
selected coefficient, whether test opened, and output path.

- [ ] **Step 4: Add and run a real-model synthetic integration test**

Define `test_real_hep_ml_synthetic_oof_and_manifest` by generating event
identifiers until every `(fold, label)` bucket contains 110 rows. Set all ten
tree features to deterministic finite trigonometric functions of the event
number, set background `m4l` independently on a 105--160 GeV grid, use both
`train` and `validation` split strings for each label, and use finite signed
physical weights. Bind a temporary Task 4A fixture by its exact computed
manifest/MC hashes while leaving every model and loss value unchanged. Limit
the config's candidate tuple only through the test seam passed directly to
`generate_flatness_oof`—never by relaxing the production config loader. Run
coefficient `0.5` through the real factory, assert one finite prediction per
row and assert `m4l` is absent from `model.train_features`. Then publish the
synthetic no-selection outcome into a fresh temporary output path and compare
its recursive files byte-for-byte with the no-selection allowlist plus
`config.yaml` and `artifacts/study_manifest.json`.

Run:

```bash
.venv/bin/python -m pytest tests/test_run_decorrelation_training_script.py tests/test_decorrelation_training_run.py tests/test_decorrelation_training.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 6**

```bash
git add scripts/run_decorrelation_training.py tests/test_run_decorrelation_training_script.py tests/test_decorrelation_training_run.py tests/test_decorrelation_training.py
git commit -m "feat: run sealed flatness training"
```

---

### Task 7: Verify the implementation, execute the one production run, and record evidence

**Files:**
- Create: `docs/superpowers/plans/2026-08-24-drop-top4-knn-flatness-training-report.md`
- Modify only if required by verified static command documentation: `README.md`, `AGENTS.md`, `docs/project/overview.md`, `docs/roadmap/next-stage.md`
- Create Git-ignored artifacts only: `runs/decorrelation-drop-top4-363490-2026-08-24/`

**Interfaces:**
- Consumes: production CLI and exact frozen source/config.
- Produces: one terminal study manifest and an evidence report containing commands, exit codes, hashes, tests, and exact selection values.

- [ ] **Step 1: Run focused and full verification before production**

```bash
.venv/bin/python -m pytest tests/test_decorrelation_training.py tests/test_decorrelation_training_plots.py tests/test_decorrelation_training_run.py tests/test_run_decorrelation_training_script.py tests/test_manifest.py -q
.venv/bin/python -m pytest -q
git diff --check
```

Expected: every command exits `0`; record exact pass counts and durations in the
report. Do not claim completion from earlier test runs.

- [ ] **Step 2: Audit protected inputs and fresh output path**

```bash
test ! -e runs/decorrelation-drop-top4-363490-2026-08-24
shasum -a 256 runs/full-baseline-363490-2026-08-11-r2/artifacts/run_manifest.json runs/full-baseline-363490-2026-08-11-r2/processed/mc_events.csv.gz
```

Expected hashes:

```text
10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8
1c5d6a3f9a750a5eb9965241dd8947d70e790cf949a36f8fa6ec1bfd058f378e
```

Do not run a broad directory inventory; the command intentionally names only
the two approved MC files.

- [ ] **Step 3: Execute exactly one production study**

```bash
.venv/bin/python -m scripts.run_decorrelation_training \
  --input-run runs/full-baseline-363490-2026-08-11-r2 \
  --config config/decorrelation_training_drop_top4.yaml \
  --run-dir runs/decorrelation-drop-top4-363490-2026-08-24
```

Expected: exit `0` with either `no_eligible_candidate` and `test_opened: false`,
or one eligible selected coefficient and `test_opened: true`. Any software
failure is reported as a failure; never rerun into the same path.

- [ ] **Step 4: Verify terminal artifacts and extract exact evidence**

```bash
.venv/bin/python -c "import json,pathlib; p=pathlib.Path('runs/decorrelation-drop-top4-363490-2026-08-24'); s=json.loads((p/'artifacts/selection.json').read_text()); m=json.loads((p/'artifacts/study_manifest.json').read_text()); print(json.dumps({'selection':s,'outputs':sorted(m['outputs']),'software':m['software'],'sources':m['sources']},indent=2,sort_keys=True))"
.venv/bin/python -c "import pandas as pd; p='runs/decorrelation-drop-top4-363490-2026-08-24/artifacts/candidate_results.csv'; print(pd.read_csv(p).to_string(index=False))"
.venv/bin/python -c "import pandas as pd; p='runs/decorrelation-drop-top4-363490-2026-08-24/artifacts/working_point_metrics.csv'; print(pd.read_csv(p).to_string(index=False))"
```

Confirm the manifest is newer than every other artifact, source hashes still
match, output names exactly match the selected/no-selection allowlist, and no
path contains periodA or `data_events.csv.gz`.

- [ ] **Step 5: Write and verify the execution report**

Create `docs/superpowers/plans/2026-08-24-drop-top4-knn-flatness-training-report.md`
with these fixed sections: `Scope and frozen constraints`, `Verification`,
`Source hashes`, `Candidate OOF results`, `Terminal decision`, `Conditional test evidence`,
`Artifact inventory`, and `Remaining limitations`. Copy the complete command
outputs from Steps 1, 2, and 4 and the exact full-precision CSV/JSON values. If
test did not open, write `Held-out test was not opened because no OOF candidate
passed every frozen gate.` If it opened, report test values without using them
to alter the selection.

Run:

```bash
rg -n "TB[D]|TO[D]O|periodA.*(scored|opened)|data_events" docs/superpowers/plans/2026-08-24-drop-top4-knn-flatness-training-report.md
git diff --check
git status --short
```

Expected: no placeholders, no claim that real data was used, and only intended
source/document changes plus Git-ignored run artifacts.

- [ ] **Step 6: Run fresh final verification and commit the report**

```bash
.venv/bin/python -m pytest -q
git diff --check
git add docs/superpowers/plans/2026-08-24-drop-top4-knn-flatness-training-report.md README.md AGENTS.md docs/project/overview.md docs/roadmap/next-stage.md
git commit -m "docs: report flatness training result"
```

Stage only documentation files that were actually changed; omit unchanged
paths from `git add`. Record the fresh final pytest pass count and the terminal
selection in the handoff.
