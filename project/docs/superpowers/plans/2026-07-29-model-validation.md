# Model Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Select the XGBoost score threshold only on validation MC, reserve test MC for final metrics, and produce quantitative overfitting diagnostics.

**Architecture:** Add a pure `src/validation.py` module that consumes an already-scored event table and returns deterministic validation metrics. Keep model fitting in `src/train.py`; it will delegate all threshold and overfitting calculations to the new module and persist both `metrics.json` and `overfitting_check.json`.

**Tech Stack:** Python 3.12, NumPy, pandas, scikit-learn, pytest, XGBoost.

## Global Constraints

- `m4l`, identifiers, source fields, and weight fields remain excluded from model features.
- The model is fitted on `train`, the threshold is selected on `validation`, and `test` is evaluated exactly once at that frozen threshold.
- Distribution comparisons use absolute physical weights because signed weights do not define a monotonic CDF.
- Overfitting thresholds are diagnostic heuristics: weighted AUC gap greater than `0.05` or weighted KS distance greater than `0.10`.

---

### Task 1: Pure validation metrics

**Files:**
- Create: `src/validation.py`
- Create: `tests/test_validation.py`

**Interfaces:**
- Produces: `weighted_ks_distance(values_a, values_b, weights_a=None, weights_b=None) -> float`
- Produces: `evaluate_scored_events(frame) -> dict`

- [ ] Write failing tests proving that validation—not test—selects the threshold.
- [ ] Write failing tests for identical and shifted train/test score distributions.
- [ ] Run `python -m pytest tests/test_validation.py -q` and confirm failures are caused by the missing module.
- [ ] Implement weighted CDF distance, split AUCs, validation threshold scan, frozen-threshold test yields, and warning flags.
- [ ] Run `python -m pytest tests/test_validation.py -q` and confirm all tests pass.

### Task 2: Integrate validation into training outputs

**Files:**
- Modify: `src/train.py`
- Modify: `src/plots.py`
- Modify: `scripts/train_demo.py`
- Modify: `README.md`
- Test: `tests/test_validation.py`

**Interfaces:**
- Consumes: `evaluate_scored_events(frame) -> dict`
- Produces: `outputs/metrics.json`
- Produces: `outputs/overfitting_check.json`
- Produces: `outputs/train_test_score_comparison.png`

- [ ] Add a failing integration-level assertion for the required report keys and selection dataset.
- [ ] Replace test-set threshold optimization with `evaluate_scored_events`.
- [ ] Persist the overfitting subset of metrics separately.
- [ ] Save the existing train/test score plot under the explicit comparison filename.
- [ ] Update README output descriptions.
- [ ] Run the full unit test suite.

### Task 3: Verification

**Files:**
- Verify: `src/validation.py`
- Verify: `src/train.py`
- Verify: `tests/test_validation.py`

- [ ] Run `python -m compileall -q src scripts tests`.
- [ ] Run `python -m pytest -q`.
- [ ] Inspect a validation report generated from a deterministic fixture and confirm all numeric fields are finite.
- [ ] Confirm existing processed data files remain unchanged.
