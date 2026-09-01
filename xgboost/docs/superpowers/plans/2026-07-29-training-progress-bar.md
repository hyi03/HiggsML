# XGBoost Training Progress Bar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a live boosting-round progress bar with the latest validation AUC during demo training.

**Architecture:** A focused `TrainingCallback` adapter will own the `tqdm` lifecycle and extract validation AUC from XGBoost evaluation logs. `src/train.py` will construct the callback using the effective `n_estimators` value and pass it to `XGBClassifier.fit` without changing model validation or dataset roles.

**Tech Stack:** Python, XGBoost 3.3, tqdm, pytest.

## Global Constraints

- The progress bar must not change model parameters, dataset splits, threshold selection, or final evaluation.
- Progress total must equal the effective `n_estimators`.
- Missing validation AUC must not stop round-count updates.
- Training errors must propagate after the progress bar is closed.
- Work in the existing project directory because the enclosing repository has no usable commit history and the project is currently untracked.

---

### Task 1: Progress callback

**Files:**
- Create: `src/progress.py`
- Create: `tests/test_progress.py`

**Interfaces:**
- Consumes: XGBoost `TrainingCallback` hooks and evaluation logs.
- Produces: `TrainingProgress(total_rounds: int, progress_factory=tqdm)` with `after_iteration`, `after_training`, and `close`.

- [ ] **Step 1: Write failing callback tests**

Create a fake progress object that records `update`, `set_postfix`, and `close`. Assert that one iteration increments by one, validation AUC `0.91` is exposed as `validation_auc`, missing AUC still increments, and training completion closes the object.

- [ ] **Step 2: Verify the tests fail**

Run: `.venv/bin/python -m pytest tests/test_progress.py -q`

Expected: FAIL because `src.progress` does not exist.

- [ ] **Step 3: Implement the minimal callback**

Subclass `xgboost.callback.TrainingCallback`, construct `tqdm(total=total_rounds, desc="Training", unit="round")`, update once per `after_iteration`, read the last value from `evals_log["validation_0"]["auc"]`, and close in `after_training`. Provide an idempotent `close()` method for exception cleanup.

- [ ] **Step 4: Verify callback tests pass**

Run: `.venv/bin/python -m pytest tests/test_progress.py -q`

Expected: all callback tests PASS.

### Task 2: Training integration

**Files:**
- Modify: `src/train.py`
- Modify: `requirements.txt`
- Modify: `tests/test_progress.py`

**Interfaces:**
- Consumes: `TrainingProgress(total_rounds)`.
- Produces: existing `train_xgboost(...)` behavior plus visible training progress.

- [ ] **Step 1: Write a failing integration-boundary test**

Test a small helper that builds `TrainingProgress` from the effective XGBoost parameters and assert a configured `n_estimators=17` produces `total_rounds == 17`.

- [ ] **Step 2: Verify the new test fails**

Run: `.venv/bin/python -m pytest tests/test_progress.py -q`

Expected: FAIL because the training callback builder is missing.

- [ ] **Step 3: Integrate the callback**

Add `tqdm` to `requirements.txt`. Construct the callback after merging defaults with YAML parameters, put `callbacks=[progress]` in the `XGBClassifier` constructor parameters, retain `verbose=False` in `fit()`, and close it in `finally` so fit exceptions are not swallowed.

- [ ] **Step 4: Verify focused and full tests**

Run: `.venv/bin/python -m pytest tests/test_progress.py -q`

Run: `.venv/bin/python -m pytest -q`

Expected: all tests PASS.

### Task 3: Real small-sample verification

**Files:**
- Regenerate: `outputs/xgboost_demo.json`
- Regenerate: `outputs/metrics.json`
- Regenerate: `outputs/overfitting_check.json`
- Regenerate: evaluation plots under `outputs/`

**Interfaces:**
- Consumes: `data/processed/mc_events.csv.gz` and `config/demo.yaml`.
- Produces: trained model, validation reports, plots, and visible terminal progress.

- [ ] **Step 1: Run the actual training command**

Run: `.venv/bin/python -m scripts.train_demo --config config/demo.yaml`

Expected: progress reaches `300/300`, the final summary prints, and the command exits zero.

- [ ] **Step 2: Validate generated artifacts**

Parse `metrics.json` and `overfitting_check.json`, confirm required metrics are finite, confirm `threshold_selection_split` is `validation`, and confirm the saved model and comparison plot are non-empty.

- [ ] **Step 3: Run final verification**

Run: `.venv/bin/python -m compileall -q src scripts tests`

Run: `.venv/bin/python -m pytest -q`

Expected: compilation and all tests succeed.
