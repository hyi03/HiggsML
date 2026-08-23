# Mass-sculpting Warning Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make finite ZZ inclusive-to-selected mass-shape KS distances above the configured 0.10 limit produce explicit, deterministic mass-sculpting warnings without altering the immutable DSID 363490 training run.

**Architecture:** Extend only the evaluation-layer warning-reason builder, reusing diagnostics that are already computed for OOF and test ZZ.  Preserve the existing empty-sample and non-finite checks, and keep training artifact publication unchanged.  Validate the corrected interpretation against the frozen metrics artifact in a separate SDD report rather than rewriting historical outputs.

**Tech Stack:** Python 3, pandas, NumPy, pytest, JSON, existing `src.full_training_evaluation` and SDD report conventions.

## Global Constraints

- Do not modify anything under `runs/full-training-363490-2026-08-11-r2`.
- Use the existing `policy.ks_distance_limit`, exactly 0.10 in `config/full_training.yaml`.
- Use strict `>` comparison, matching the overfitting warning convention.
- Preserve existing empty-selected-ZZ and non-finite warning reasons.
- Do not change features, thresholds, model parameters, or retrain in this task.
- Do not inspect or score real data.
- Do not execute Git writes; use SDD snapshots, reports, and review evidence.

---

### Task 1: Correct finite KS exceedance warnings

**Files:**
- Modify: `tests/test_full_training_evaluation.py`
- Modify: `src/full_training_evaluation.py`
- Create: `.superpowers/sdd/2026-08-11-dsid-363490-training/task-7c-report.md`

**Interfaces:**
- Consumes: `_mass_sculpting_metrics(oof, oof_score, test, test_score, points, policy) -> dict[str, object]`, whose diagnostics contain `oof_zz` and `test_zz`, each with `working_points` and `inclusive_to_selected_ks_distance`.
- Produces: deterministic reasons named `<split>.<working_point>.ks_distance` and a true `mass_sculpting.warning` when a finite distance is greater than `policy.ks_distance_limit`.

- [ ] **Step 1: Save exact pre-change evidence**

Create an SDD snapshot of `src/full_training_evaluation.py` and `tests/test_full_training_evaluation.py`, recording SHA-256 hashes in `task-7c-report.md`.  Record hashes for all files in the immutable training run before any test or source edit.

- [ ] **Step 2: Write the focused failing regression**

Change the existing finite-diagnostics test so its already-computed test-ZZ loose KS distance of 0.5 must trigger the following reason and warning:

```python
assert report["mass_sculpting"]["warning"] is True
assert "test_zz.loose.ks_distance" in report["mass_sculpting"]["warning_reasons"]
```

Add a focused boundary test using a minimal diagnostics mapping or scored frame to prove a KS distance equal to `policy.ks_distance_limit` does not warn, while a value above it does.

- [ ] **Step 3: Run RED and record the exact expected failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_full_training_evaluation.py -q
```

Expected: failure because the current finite distance of 0.5 leaves `mass_sculpting.warning` false and omits `test_zz.loose.ks_distance`.

- [ ] **Step 4: Add the minimal reason collector**

Add a helper with deterministic split/working-point traversal:

```python
def _excessive_mass_ks_reasons(diagnostics, limit):
    reasons = []
    for split_name in ("oof_zz", "test_zz"):
        for working_point, values in diagnostics[split_name]["working_points"].items():
            distance = values["inclusive_to_selected_ks_distance"]
            if distance is not None and np.isfinite(distance) and distance > float(limit):
                reasons.append(f"{split_name}.{working_point}.ks_distance")
    return reasons
```

Call it from `_mass_sculpting_metrics` after `_empty_selected_zz_reasons` and before `_nonfinite_paths`, using `policy.ks_distance_limit`.  Do not change metric calculations or JSON serialization.

- [ ] **Step 5: Run focused GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_full_training_evaluation.py -q
```

Expected: all tests pass, with exact count and elapsed time copied into `task-7c-report.md`.

- [ ] **Step 6: Run related and full regression suites**

Run:

```bash
.venv/bin/python -m pytest tests/test_full_training_evaluation.py tests/test_train_full_mc_script.py tests/test_full_training_run.py tests/test_validation.py -q
.venv/bin/python -m pytest -q
```

Expected: both commands exit 0.  Record exact counts and timings.

- [ ] **Step 7: Audit the immutable DSID 363490 result**

Read only `runs/full-training-363490-2026-08-11-r2/artifacts/metrics.json`.  Verify all six stored KS distances exceed 0.10 and record the corrected expected reasons:

```text
oof_zz.loose.ks_distance
oof_zz.medium.ks_distance
oof_zz.tight.ks_distance
test_zz.loose.ks_distance
test_zz.medium.ks_distance
test_zz.tight.ks_distance
```

Re-hash the immutable run and require the before/after inventory to match exactly.

- [ ] **Step 8: Independently review the scoped change**

Review only the pre-change snapshot versus the two live files.  Confirm the strict boundary, reason ordering, preservation of empty/non-finite handling, top-level warning propagation, and historical artifact immutability.  Write the verdict to `.superpowers/sdd/2026-08-11-dsid-363490-training/task-7c-review.md`; any Critical or Important finding requires a new TDD fix round before acceptance.
