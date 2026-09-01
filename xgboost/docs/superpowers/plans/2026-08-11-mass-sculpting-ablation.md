# DSID 363490 Mass-sculpting Ablation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a sealed MC-only feature-ablation study that may select a useful Higgs-versus-ZZ classifier only when development evidence shows all frozen ZZ mass-shape KS distances at or below 0.10.

**Architecture:** First parameterize the existing model layer with an explicit validated feature tuple while preserving the 14-feature default.  Add a pure study layer that evaluates three predeclared feature profiles on development folds and makes a deterministic eligibility decision before any test scoring.  A dedicated CLI uses the existing immutable Task 4A input contract and a fresh, manifest-last study run contract.

**Tech Stack:** Python 3, pandas, NumPy, scikit-learn, XGBoost, Matplotlib, pytest, JSON/CSV/gzip artifacts.

## Global Constraints

- Input MC is only `runs/full-baseline-363490-2026-08-11-r2`.
- Reference evidence is only `runs/full-training-363490-2026-08-11-r2`.
- Do not modify either immutable r2 run.
- Do not use DSID 700600 or inspect/score real data.
- No feature profile may contain `m4l`, identities, split, label, or weights.
- Candidate/profile selection uses development OOF evidence only; test is opened once after selection.
- Eligibility requires max OOF KS ≤ 0.10, OOF AUC ≥ 0.80, and signal efficiency greater than target ZZ efficiency at every working point.
- Use strict TDD and SDD snapshots; do not execute Git writes.

---

### Task 1: Parameterize model fitting and scoring by feature tuple

**Files:**
- Modify: `src/full_training_model.py`
- Modify: `scripts/train_full_mc.py`
- Modify: `tests/test_full_training_model.py`
- Modify: `tests/test_train_full_mc_script.py`
- Create: `.superpowers/sdd/2026-08-11-dsid-363490-training/task-8a-report.md`

**Interfaces:**
- Produces: `validate_model_features(features) -> tuple[str, ...]`.
- Produces: `cross_validate_candidates(..., *, features=FEATURES)` and `fit_final_model(..., *, features=FEATURES)`.
- Produces: `score_model(model, frame, *, features=FEATURES) -> np.ndarray`.
- Existing callers without `features=` retain byte-compatible 14-feature behavior.

- [x] **Step 1: Snapshot and hash the four target files**

Save exact pre-change copies under `task-8a-before/`.  Record their SHA-256 values and the immutable r2 run inventories.

- [x] **Step 2: Write RED tests for explicit feature usage**

Use a recording model factory and a frame whose omitted columns contain sentinel values.  Assert every fitting/evaluation/prediction matrix has exactly the requested columns and order:

```python
features = ("lep1_eta", "lep2_eta", "deltaPhi_ZZ")
selection = cross_validate_candidates(frame, policy, recording_factory, features=features)
model = fit_final_model(frame, selection, policy, recording_factory, features=features)
scores = score_model(model, frame.loc[frame["split"] == "test"], features=features)
assert recorded_columns == [features] * len(recorded_columns)
assert len(scores) == len(frame.loc[frame["split"] == "test"])
```

Add parameterized invalid cases: empty, duplicate, `m4l`, `label`, unknown name,
and a non-string entry.  Assert rejection occurs before model-factory invocation.

- [x] **Step 3: Run RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_full_training_model.py tests/test_train_full_mc_script.py -q
```

Expected: focused failures because the APIs reject `features=` or still use the global 14-feature tuple.

- [x] **Step 4: Implement the minimal parameterization**

Validate a non-empty, unique tuple that is an ordered subset of `FEATURES` and contains no forbidden field.  Replace each fitting/evaluation matrix slice with `frame.loc[:, validated_features]`.  Route the existing CLI scorer through `score_model` with the default features; do not change artifact names or training behavior.

- [x] **Step 5: Run GREEN and regression**

Run the focused command, then:

```bash
.venv/bin/python -m pytest tests/test_full_training_model.py tests/test_train_full_mc_script.py tests/test_full_training_run.py -q
.venv/bin/python -m pytest -q
```

Record exact counts/timings and re-hash both immutable runs.

- [x] **Step 6: Independent scoped review**

Confirm default behavior, early rejection, exact column order, development/test boundaries, and no artifact-contract changes.  Any Critical/Important finding enters a TDD fix round.

---

### Task 2: Build pure development-only ablation logic

**Files:**
- Create: `src/mass_sculpting_ablation.py`
- Create: `tests/test_mass_sculpting_ablation.py`
- Modify: `src/full_training_evaluation.py`
- Modify: `tests/test_full_training_evaluation.py`
- Create: `.superpowers/sdd/2026-08-11-dsid-363490-training/task-8b-report.md`

**Interfaces:**
- Produces: immutable `FeatureProfile(name: str, features: tuple[str, ...])` and exact `ABLATION_PROFILES`.
- Produces: `evaluate_development_profile(frame, policy, profile, *, model_factory=None) -> ProfileResult`.
- Produces: `select_eligible_profile(results, *, auc_floor=0.80, ks_limit=0.10) -> ProfileResult | None` for development-only reporting.
- Produces: `select_and_score_test(frame, policy, *, model_factory=None) -> AblationOutcome` as the only public test-opening operation; its outcome contains all canonical development results, the internally selected result or `None`, and optional final test evidence.
- Consumes Task 1's explicit-feature fitting/scoring APIs.

- [x] **Step 1: Write RED profile-contract tests**

Assert exact profiles:

```python
assert ABLATION_PROFILES["drop_top4_mass_proxies"].features == (
    "lep1_pt", "lep2_pt",
    "lep1_eta", "lep2_eta", "lep3_eta", "lep4_eta",
    "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
)
assert ABLATION_PROFILES["shape8"].features == (
    "lep1_eta", "lep2_eta", "lep3_eta", "lep4_eta",
    "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
)
assert ABLATION_PROFILES["angular_eta7"].features == (
    "lep1_eta", "lep2_eta", "lep3_eta", "lep4_eta",
    "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
)
```

Assert every tuple is unique, non-empty, and excludes `m4l` and forbidden audit columns.

- [x] **Step 2: Write RED eligibility tests with literal results**

Build literal `ProfileResult` values proving:

- KS 0.1000 is accepted but 0.1001 is rejected;
- AUC 0.8000 is accepted but 0.7999 is rejected;
- signal efficiency equal to the target is rejected;
- highest AUC wins among eligible results;
- exact AUC tie selects smaller max KS, then lexicographic name;
- no eligible result returns `None`.

- [x] **Step 3: Write the sealed-order RED test**

Use a frame with sentinel test values and a recording factory.  Call
`evaluate_development_profile`; assert no fitting, evaluation, threshold, or
prediction input contains a `split == "test"` row.  Then select a result and call
`fit_and_score_selected`; assert test prediction happens only after the selection
function has returned and exactly once.

- [x] **Step 4: Run RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_mass_sculpting_ablation.py tests/test_full_training_evaluation.py -q
```

Expected: collection or behavior failures due to the missing study module and public OOF-ZZ diagnostic interface.

- [x] **Step 5: Implement development metrics and eligibility**

For one profile, call feature-parameterized CV, create an OOF audit frame,
freeze working points from OOF ZZ, and calculate:

```python
weighted_auc = roc_auc_score(labels, scores, sample_weight=np.abs(weights))
score_mass_correlation = weighted_pearson(zz_scores, zz_m4l, zz_weights)
mass_diagnostics = zz_mass_diagnostics(oof, "oof_score", points, policy)
```

Expose a validated public wrapper for the existing ZZ mass diagnostic rather
than duplicating its calculation.  Store candidate name, final tree count,
working-point thresholds, signal efficiencies, three KS distances, and an
eligibility-reason list in `ProfileResult`.

- [x] **Step 6: Implement sealed test scoring**

Do not expose a function that accepts one caller-supplied selected result, a
transferable selection certificate, a result mapping, or `auc_floor`/`ks_limit`
overrides. `select_and_score_test` must accept only the frame, policy, and
optional model factory; evaluate every exact `ABLATION_PROFILES` entry in
canonical order captured at function-definition time rather than reading the
runtime public mapping; retain immutable deep snapshots of all development
results in its outcome; and call the
deterministic development-only selector with the fixed 0.80/0.10 defaults
before locating test rows. If selection returns `None`, return an outcome with
no selected or test evidence without test access. Otherwise fit that one
profile on all development rows, call `score_model` exactly once on test, apply
its OOF-frozen thresholds, and return the outcome. Test performance never feeds
back into selection.

- [x] **Step 7: Run GREEN and full regression**

Run the focused command, Task 1 related tests, and `.venv/bin/python -m pytest -q`.
Record exact evidence and immutable-run hashes.

- [x] **Step 8: Independent scientific/code review**

Review feature definitions, absolute-weight metrics, OOF-only thresholds,
eligibility boundaries, deterministic tie-breaks, and the zero-test-access gate.

---

### Task 3: Add safe study publication, plots, and CLI

**Files:**
- Create: `src/mass_sculpting_ablation_run.py`
- Create: `src/mass_sculpting_ablation_plots.py`
- Create: `scripts/run_mass_sculpting_ablation.py`
- Create: `config/mass_sculpting_ablation.yaml`
- Create: `tests/test_mass_sculpting_ablation_run.py`
- Create: `tests/test_mass_sculpting_ablation_plots.py`
- Create: `tests/test_run_mass_sculpting_ablation_script.py`
- Create: `.superpowers/sdd/2026-08-11-dsid-363490-training/task-8c-report.md`

**Interfaces:**
- CLI: `python -m scripts.run_mass_sculpting_ablation --input-run <Task4A> --reference-run <Task4B> --config <yaml> --run-dir <fresh>`.
- Produces the fixed allowlist and manifest-last contract from the design.
- Consumes Task 2 profile results and selected evidence.

- [x] **Step 1: Write RED preflight/refusal tests**

Assert an existing directory, regular file, direct symlink, or dangling symlink
at `--run-dir` fails before input CSV loading or model-factory invocation.  Assert
the fresh path is claimed atomically with `mkdir(exist_ok=False)` and fixed child
directories are created once.

- [x] **Step 2: Write RED sealed CLI tests**

Use fake input resolvers and study functions to assert exact order:

```text
output_preflight
input_resolve
output_rebind
output_claim
input_load
development_profiles
profile_selection
[fit_selected, score_test]
write_artifacts
input_recheck
publish_manifest
```

For `no_eligible_profile`, assert the bracketed test steps are absent and no
test-only artifact names appear.

- [x] **Step 3: Write RED artifact/plot tests**

Require `profile_results.csv`, `selection.json`, and
`oof_profile_tradeoff.png` for every complete study.  When selected, additionally
require the model, selected OOF/test score tables, `test_metrics.json`, and
`selected_mass_sculpting.png`.  Reject extra names, symlink targets, non-finite
JSON/CSV values, and any pre-existing artifact entry.  Require manifest mtime
and publication after every other artifact.

- [x] **Step 4: Run RED**

Run all three new test files.  Expected failures must be only missing modules,
contracts, or behavior—not fixture/collection errors.

- [x] **Step 5: Implement config and safe layout**

The YAML must exactly bind schema 1.0, the three feature profiles, `auc_floor:
0.80`, `ks_limit: 0.10`, the reference run, and the expected output allowlist.
Resolve and byte-snapshot config/input manifests before claim.  Reuse established
dir-fd, no-follow, no-clobber, failure-terminal, and manifest-last helpers where
their contracts fit; do not weaken them with path-only check-then-write logic.

- [x] **Step 6: Implement the two fixed plots**

`oof_profile_tradeoff.png` shows weighted OOF AUC against maximum OOF KS, with
0.80 and 0.10 reference lines and direct profile labels.  The selected mass
plot shows inclusive plus loose/medium/tight ZZ for OOF and test using absolute
weights and the OOF-frozen thresholds.  Preflight all output paths before
plotting and publish bytes through the safe writer.

- [x] **Step 7: Implement CLI orchestration and terminal states**

Load the MC table only after fresh-output claim, validate identities/finiteness,
run all development profiles, select exactly once, optionally fit/score test,
write the allowlisted artifacts, recheck input/config hashes, and publish the
manifest last.  On an exception, install `failure.json` without a completion
manifest and never reuse the path.

- [x] **Step 8: Run GREEN, integration, and full suite**

Run the three new test files, all Task 1/2 focused tests, a tiny real-XGBoost
synthetic integration, and `.venv/bin/python -m pytest -q`.  Require clean
`compileall` and diff whitespace checks without Git writes.

- [x] **Step 9: Independent safety/science review**

Review no-test-before-selection, feature/profile fidelity, output allowlist,
hash binding, manifest-last, refusal timing, finite metrics, and plot semantics.

---

### Task 4: Execute and audit the real DSID 363490 study once

**Files:**
- Create: `runs/mass-ablation-363490-2026-08-11/` only via the approved CLI.
- Create: `.superpowers/sdd/2026-08-11-dsid-363490-training/task-8d-report.md`
- Modify: `.superpowers/sdd/2026-08-11-dsid-363490-training/progress.md`
- Modify: `docs/superpowers/plans/2026-08-11-dsid-363490-training-report.md`

- [x] **Step 1: Fresh preflight and full test gate**

Hash protected r2 runs and raw input; verify the target path is absent and not a
symlink; run `.venv/bin/python -m pytest -q` once.  Stop before execution if any
gate fails.

- [x] **Step 2: Run the exact command once**

```bash
.venv/bin/python -m scripts.run_mass_sculpting_ablation \
  --input-run runs/full-baseline-363490-2026-08-11-r2 \
  --reference-run runs/full-training-363490-2026-08-11-r2 \
  --config config/mass_sculpting_ablation.yaml \
  --run-dir runs/mass-ablation-363490-2026-08-11
```

Do not interrupt or retry.  Report progress at least every 60 seconds.

- [x] **Step 3: Audit the completed or no-eligible study**

Verify exact allowlist, manifest-last ordering, hashes/row counts, finite values,
three profile definitions, OOF-only selection, and no test artifacts when no
profile is eligible.  If selected, verify test was opened once and could not
change selection.

- [x] **Step 4: Inspect only the new study plots**

Confirm labels, scales, 0.80/0.10 references, thresholds, weight semantics, and
that any claimed mitigation is visually compatible with the recorded KS values.

- [x] **Step 5: Refusal and immutability checks**

Invoke the exact same command once more only for same-path refusal.  Require
rejection before MC table/model access and exact before/after study hashes.
Re-hash all protected r2 runs and raw ROOT input.

- [x] **Step 6: Independent final scientific review**

Classify the result as `successful_simple_mitigation`,
`test_nonreproduction`, or `no_eligible_profile` exactly from the predeclared
rules.  Do not soften thresholds or add candidates after seeing results.
