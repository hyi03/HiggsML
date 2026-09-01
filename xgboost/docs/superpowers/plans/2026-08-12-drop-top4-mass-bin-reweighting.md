# Drop-top4 Mass-bin Iterative Reweighting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run one sealed MC-only study that trains the exact ten-feature `drop_top4_mass_proxies` model with the existing fixed-bin iterative ZZ reweighting policy and compares it with three frozen reference results.

**Architecture:** Extend the existing reweighting core at one strictly validated feature-profile seam, then pass the configuration-bound profile through the existing CLI, artifact writer, and manifest-last publisher. Do not duplicate the workflow or create arbitrary feature search; accept only captured Full14 and captured drop-top4 tuples, preserving Full14 as the default.

**Tech Stack:** Python 3.11, pandas, NumPy, scikit-learn, XGBoost, Matplotlib, PyYAML, pytest.

## Global Constraints

- Never modify or reuse `runs/full-baseline-363490-2026-08-11-r2`, `runs/full-training-363490-2026-08-11-r2`, `runs/mass-ablation-363490-2026-08-11`, or `runs/mass-reweighting-363490-2026-08-11`.
- Never read or score `data16_periodA`, `data_events`, or any real-data artifact.
- The new ordered feature tuple is exactly `lep1_pt, lep2_pt, lep1_eta, lep2_eta, lep3_eta, lep4_eta, pt4l, deltaR_Z1, deltaR_Z2, deltaPhi_ZZ`.
- `m4l`, `lep3_pt`, `lep4_pt`, `mZ1`, and `mZ2` must not reach model fit or prediction for the new profile.
- Keep AUC floor `0.80`, all three KS limits `0.10`, 11 bins from 105 to 160 GeV in 5 GeV steps, minimum effective count `100`, and maximum corrections `5` unchanged.
- Keep the six XGBoost candidates, one-standard-error choice, final-tree rule, seeds, working points, and weighting formula unchanged.
- Use focused tests during implementation; run the full synthetic suite once only at the final pre-run acceptance boundary unless a final documentation-only fix requires a fresh final verification.
- The real study command is invoked exactly once. A scientifically disappointing result is not retried.
- No Git stage, commit, branch, reset, or cleanup action is authorized in this untracked workspace. Record each task in `.superpowers/sdd/2026-08-12-drop-top4-mass-bin-reweighting/` and the project progress ledger instead.

---

## File map

- Modify `src/mass_bin_reweighting.py`: exact captured model-profile validation and propagation through fit/predict calls.
- Modify `src/mass_bin_reweighting_run.py`: dual approved-profile config validation and feature-aware manifest validation.
- Modify `scripts/run_mass_bin_reweighting.py`: pass the configuration-bound feature tuple into the core study.
- Create `config/mass_bin_reweighting_drop_top4.yaml`: sealed ten-feature study configuration.
- Modify `tests/test_mass_bin_reweighting.py`: core fit/predict profile and runtime-rebinding tests.
- Modify `tests/test_mass_bin_reweighting_run.py`: exact config, policy manifest, output, and source-contract tests.
- Modify `tests/test_run_mass_bin_reweighting_script.py`: CLI propagation, stage order, and tiny real-XGBoost integration tests.
- Reuse `src/mass_bin_reweighting_plots.py` unchanged unless a focused test proves it incorrectly assumes Full14.
- Create `.superpowers/sdd/2026-08-12-drop-top4-mass-bin-reweighting/task-*.md`: RED/GREEN commands, review findings, hashes, and real-run audit.
- Modify `docs/roadmap/next-stage.md` and the relevant progress/migration ledgers only after the real result exists.

---

### Task 1: Seal and propagate the exact ten-feature model profile

**Files:**
- Modify: `src/mass_bin_reweighting.py:183-330`
- Modify: `src/mass_bin_reweighting.py:667-676`
- Test: `tests/test_mass_bin_reweighting.py`
- Create: `.superpowers/sdd/2026-08-12-drop-top4-mass-bin-reweighting/task-1-report.md`

**Interfaces:**
- Consumes: existing `TrainingPolicy`, `ReweightingPolicy`, and `tuple(FEATURES)`.
- Produces: `approved_reweighting_features(value: object) -> tuple[str, ...]` and `run_mass_bin_reweighting_study(..., *, features: tuple[str, ...] = captured_full14, model_factory=None) -> ReweightingStudyOutcome`.
- Later tasks pass `MassBinReweightingConfig.features` into this keyword-only `features` argument.

- [ ] **Step 1: Snapshot the scoped files and record hashes**

Run:

```bash
mkdir -p /private/tmp/drop-top4-reweight-task1-before
cp src/mass_bin_reweighting.py tests/test_mass_bin_reweighting.py /private/tmp/drop-top4-reweight-task1-before/
shasum -a 256 src/mass_bin_reweighting.py tests/test_mass_bin_reweighting.py /private/tmp/drop-top4-reweight-task1-before/*
```

Expected: each live file matches its copied snapshot. Do not modify `data/`, `runs/`, or `outputs/`.

- [ ] **Step 2: Write failing exact-profile tests**

Add tests that define the literal approved profile instead of importing a mutable production global:

```python
DROP_TOP4 = (
    "lep1_pt", "lep2_pt", "lep1_eta", "lep2_eta", "lep3_eta",
    "lep4_eta", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
)

@pytest.mark.parametrize("features", [DROP_TOP4, tuple(FEATURES)])
def test_study_passes_only_approved_features_to_every_fit_and_predict(features):
    factory = _StudyFactory()
    outcome = mass_bin_reweighting.run_mass_bin_reweighting_study(
        _study_frame(("flat",)), load_training_policy("config/full_training.yaml"),
        ReweightingPolicy(
            mass_bin_edges=EDGES, minimum_effective_count=100.0,
            epsilon_floor=1e-6, damping=0.5,
            round_factor_bounds=(0.5, 2.0), cumulative_bounds=(0.2, 5.0),
            maximum_corrections=5, auc_floor=0.80, ks_limit=0.10,
        ),
        features=features, model_factory=factory,
    )
    assert factory.records
    assert all(record["fit_columns"] == features for record in factory.records)
    assert all(columns == features for record in factory.records
               for columns in record["predict_columns"])
```

Extend `_StudyClassifier.predict_proba()` in the test double to append
`tuple(x.columns)` to a `predict_columns` list before reading scores. Also add
parameterized rejection cases for one missing feature, an extra feature,
reversed order, duplicates, a list rather than tuple, `m4l`, each removed feature
inserted into the ten-profile, and arbitrary Full14 subsets. Add an attack that
rebinds any public profile globals before entry and proves the altered tuple is
rejected before split access or `model_factory` invocation.

- [ ] **Step 3: Run the focused RED tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_mass_bin_reweighting.py -k 'approved_features or passes_only_approved_features or feature_profile_rebinding' -q
```

Expected: FAIL because the study has no `features` keyword and always calls `_model_features()` Full14.

- [ ] **Step 4: Implement the minimal captured profile seam**

Capture literal tuples at import/function-definition time and validate by exact type, length, value, and order:

```python
_FULL14_FEATURES = tuple(FEATURES)
_DROP_TOP4_FEATURES = (
    "lep1_pt", "lep2_pt", "lep1_eta", "lep2_eta", "lep3_eta",
    "lep4_eta", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
)

def approved_reweighting_features(
    value: object,
    approved: tuple[tuple[str, ...], ...] = (_FULL14_FEATURES, _DROP_TOP4_FEATURES),
) -> tuple[str, ...]:
    if not isinstance(value, tuple) or not any(value == item for item in approved):
        raise ValueError("features must equal an approved reweighting profile")
    return tuple(value)
```

Capture `features` before accessing `frame["split"]`. Replace every call to
`_model_features()` in cross-validation, final fit, and score with that captured
tuple. Preserve the existing Full14 default.

- [ ] **Step 5: Run focused GREEN and adjacent core regressions**

Run:

```bash
.venv/bin/python -m pytest tests/test_mass_bin_reweighting.py tests/test_full_training_model.py tests/test_full_training_policy.py -q
```

Expected: all pass. Confirm every recorded new-profile `fit_columns` and prediction
column order equals the literal ten-feature tuple.

- [ ] **Step 6: Self-review and record Task 1**

Inspect only the Task 1 diff. Verify validation occurs before split access,
Full14 stays the default, no test branch was weakened, and no mutable global can
expand the approved profiles. Append exact RED/GREEN commands, counts, scoped
hashes, and findings to `task-1-report.md`.

---

### Task 2: Add the sealed ten-feature configuration and feature-aware manifest policy

**Files:**
- Create: `config/mass_bin_reweighting_drop_top4.yaml`
- Modify: `src/mass_bin_reweighting_run.py:90-250`
- Modify: `src/mass_bin_reweighting_run.py:282-360`
- Modify: `src/mass_bin_reweighting_run.py:916-946`
- Modify: `src/mass_bin_reweighting_run.py:1083-1100`
- Test: `tests/test_mass_bin_reweighting_run.py`
- Create: `.superpowers/sdd/2026-08-12-drop-top4-mass-bin-reweighting/task-2-report.md`

**Interfaces:**
- Consumes: `approved_reweighting_features()` from Task 1.
- Produces: `load_mass_bin_reweighting_config()` returning `MassBinReweightingConfig.features` as either exact Full14 or exact drop-top4, an optional bound Full14-reweighting reference for the new schema, and `policy_manifest_record(config)` whose feature list must match that captured config.
- Existing Full14 `config/mass_bin_reweighting.yaml` remains byte-compatible and valid.

- [ ] **Step 1: Snapshot scoped files**

Run:

```bash
mkdir -p /private/tmp/drop-top4-reweight-task2-before
cp src/mass_bin_reweighting_run.py tests/test_mass_bin_reweighting_run.py /private/tmp/drop-top4-reweight-task2-before/
shasum -a 256 src/mass_bin_reweighting_run.py tests/test_mass_bin_reweighting_run.py /private/tmp/drop-top4-reweight-task2-before/*
```

- [ ] **Step 2: Write config and manifest RED tests**

Create schema `1.1` YAML by copying every Full14 policy/source/allowlist field,
changing `features` to the literal ten-profile, and adding these frozen comparison
receipts:

```yaml
reweighting_reference_run: runs/mass-reweighting-363490-2026-08-11
reweighting_reference_manifest_sha256: 145e38478dfd12310a82f4ed544c6cf0b09204cbc1c7d08e6e485941c00f9e38
```

The existing Full14 schema `1.0` remains valid unchanged. Add tests:

```python
def test_drop_top4_config_changes_only_the_approved_feature_profile():
    full = load_mass_bin_reweighting_config("config/mass_bin_reweighting.yaml")
    reduced = load_mass_bin_reweighting_config(
        "config/mass_bin_reweighting_drop_top4.yaml"
    )
    assert reduced.schema_version == "1.1"
    assert reduced.features == DROP_TOP4
    assert reduced.reweighting_reference_run == (
        "runs/mass-reweighting-363490-2026-08-11"
    )
    assert reduced.reweighting_reference_manifest_sha256 == (
        "145e38478dfd12310a82f4ed544c6cf0b09204cbc1c7d08e6e485941c00f9e38"
    )
    for name in (
        "mass_bin_edges", "minimum_effective_count", "epsilon_floor",
        "damping", "round_factor_bounds", "cumulative_bounds",
        "maximum_corrections", "auc_floor", "ks_limit",
        "require_signal_efficiency_above_zz", "artifacts_no_selection",
        "artifacts_selected",
    ):
        assert getattr(reduced, name) == getattr(full, name)

def test_policy_manifest_record_uses_bound_drop_top4_profile():
    config = load_mass_bin_reweighting_config(
        "config/mass_bin_reweighting_drop_top4.yaml"
    )
    assert policy_manifest_record(config)["features"] == list(DROP_TOP4)
```

Extend mutation tests so missing, extra, reordered, duplicated, `m4l`, or a
non-approved subset is rejected for both configs. Add a validator test proving a
drop-top4 manifest policy cannot be substituted with Full14 after artifact write.

- [ ] **Step 3: Run Task 2 RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_mass_bin_reweighting_run.py -k 'drop_top4 or feature_profile or policy_manifest' -q
```

Expected: FAIL because `_load_config_bytes()` and `_validate_policy_record()` are
hard-coded to Full14.

- [ ] **Step 4: Implement exact dual-profile config validation**

Import `approved_reweighting_features`, parse `raw["features"]` only when it is a
list of strings, convert it to a tuple, and validate it against the two captured
profiles. Accept only the exact old schema `1.0` field set for Full14 and the exact
new schema `1.1` field set for drop-top4. Store the captured tuple and new frozen
reference fields in `MassBinReweightingConfig`.

Extend `ReweightingSources` and its records for schema `1.1` with a
`reweighting_reference_manifest` source. Hash it without parsing tables, protect
its run directory in `resolve_reweighting_output`, include its receipt in the
published source inventory, and recheck it immediately before manifest
publication. Schema `1.0` keeps its current 11-source inventory.

Change policy-record validation to accept an explicit expected captured feature
tuple originating from the bound config/receipt rather than `_FEATURES`. It must
still reject runtime global rebinding and cross-profile substitution.

- [ ] **Step 5: Run focused GREEN and Full14 compatibility tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_mass_bin_reweighting_run.py -q
```

Expected: all tests pass for both checked-in configs, all mutation cases fail
closed, and existing Full14 receipts/manifests retain their contract.

- [ ] **Step 6: Review Task 2 and record evidence**

Confirm the YAML changes only schema/profile plus the two required frozen-reference
fields, all other policy values and allowlists are equal, the source hashes are
exact, the old Full14 schema remains accepted, and the manifest cannot claim a
profile different from the one used by the runner. Record commands, counts,
hashes, and review findings in `task-2-report.md`.

---

### Task 3: Wire the bound profile through the sealed CLI

**Files:**
- Modify: `scripts/run_mass_bin_reweighting.py:35-93`
- Test: `tests/test_run_mass_bin_reweighting_script.py`
- Create: `.superpowers/sdd/2026-08-12-drop-top4-mass-bin-reweighting/task-3-report.md`

**Interfaces:**
- Consumes: `sources.config.features` from Task 2 and the Task 1 study keyword.
- Produces: one CLI path that runs either approved profile while preserving output-preflight, source-binding, atomic-claim, single-parse, source-recheck, and manifest-last order.

- [ ] **Step 1: Write CLI propagation RED tests**

Update the sealed-order fixture so its fake study records keyword arguments and
asserts:

```python
assert study_calls == [{
    "frame": parsed_frame,
    "training_policy": sources.policy,
    "reweighting_policy": sources.reweighting_policy,
    "features": DROP_TOP4,
}]
```

Add a tiny real-XGBoost drop-top4 case that records model feature names and proves
all fits/predictions use exactly ten columns; poison access to `m4l`, `lep3_pt`,
`lep4_pt`, `mZ1`, and `mZ2` through the model-input seam. Keep both no-selection
and selected synthetic terminals covered.

Extend the sealed-order assertion so the second `resolve_reweighting_output()`
receives `sources.reweighting_reference_run` for schema `1.1`, proving the frozen
Full14-reweighting run is protected before atomic claim. The old schema passes
`None` and keeps its existing behavior.

- [ ] **Step 2: Run CLI RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_run_mass_bin_reweighting_script.py -k 'drop_top4 or sealed_order' -q
```

Expected: FAIL because `main()` does not pass `sources.config.features`.

- [ ] **Step 3: Add the one-line feature propagation**

Change the study call to:

```python
outcome = run_mass_bin_reweighting_study(
    frame,
    sources.policy,
    sources.reweighting_policy,
    features=sources.config.features,
)
```

Do not change parser flags, stage order, publication logic, or error handling.
Pass the schema `1.1` frozen reweighting-reference path into the second output
resolver together with the existing ablation and raw-ZZ protected paths.

- [ ] **Step 4: Run Task 3 GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_run_mass_bin_reweighting_script.py tests/test_mass_bin_reweighting.py tests/test_mass_bin_reweighting_run.py -q
```

Expected: all pass, including both tiny real-XGBoost conditional terminals and
the exact single post-claim MC parse assertion.

- [ ] **Step 5: Review the sealed boundary and record Task 3**

Verify occupied output still refuses before source/CSV/model access, fresh output
still claims before parse, no-eligible still performs zero test work, and failure
still publishes no complete manifest. Record exact evidence in `task-3-report.md`.

---

### Task 4: End-to-end synthetic publication and adversarial verification

**Files:**
- Modify only if a failing focused test requires it: `src/mass_bin_reweighting_run.py`, `scripts/run_mass_bin_reweighting.py`
- Test: `tests/test_mass_bin_reweighting_run.py`
- Test: `tests/test_run_mass_bin_reweighting_script.py`
- Test: `tests/test_mass_bin_reweighting_plots.py`
- Create: `.superpowers/sdd/2026-08-12-drop-top4-mass-bin-reweighting/task-4-report.md`

**Interfaces:**
- Consumes: completed Tasks 1--3.
- Produces: verified conditional artifacts and manifest evidence for the exact ten-profile with no new production API.

- [ ] **Step 1: Add a synthetic drop-top4 completed-run test**

Use a temporary directory and real XGBoost to exercise the CLI with the new config.
For both selected and no-selection outcomes, assert:

```python
assert manifest["policy"]["features"] == list(DROP_TOP4)
assert manifest["decision"]["test_opened"] is selected
assert set(relative_files) == approved_reweighting_artifacts(selected=selected)
assert all(receipt["sha256"] == sha256(path.read_bytes()).hexdigest()
           for path, receipt in output_receipts)
```

Also assert 33 bin-efficiency rows and 11 multiplier rows per executed iteration,
exact iteration prefix `0..selected` or `0..5`, finite CSV/JSON values, and no
forbidden feature in model metadata.

- [ ] **Step 2: Add adversarial profile/publication tests**

Test cross-profile policy substitution, feature-list mutation after source bind,
config byte substitution after claim, symlink replacement, same-path publication,
and manifest policy mismatch. Every case must fail before manifest promotion and
leave only the approved failure terminal when a run has been claimed.

- [ ] **Step 3: Run focused RED/GREEN loop**

Run the exact new node IDs first. If any test fails, make only the smallest change
inside the existing feature-aware validation seam, then rerun the node. After the
new nodes pass, run:

```bash
.venv/bin/python -m pytest \
  tests/test_mass_bin_reweighting.py \
  tests/test_mass_bin_reweighting_plots.py \
  tests/test_mass_bin_reweighting_run.py \
  tests/test_run_mass_bin_reweighting_script.py -q
```

Expected: all focused reweighting tests pass.

- [ ] **Step 4: Inspect synthetic PNGs and review Task 4**

Open only the newly generated temporary PNGs. Check titles, axes, legends,
iteration coverage, three working points, and lack of clipping. Verify no plot
uses test data in a no-selection terminal. Record visual observations, commands,
counts, hashes, and any fix loop in `task-4-report.md`.

---

### Task 5: Final pre-run acceptance gate

**Files:**
- Read: all files changed in Tasks 1--4
- Create: `.superpowers/sdd/2026-08-12-drop-top4-mass-bin-reweighting/task-5-report.md`

**Interfaces:**
- Consumes: the complete implementation.
- Produces: a signed-off code/config state eligible for one real command.

- [ ] **Step 1: Perform a scoped code review**

Review feature capture, test sealing, source timing, output resolution, descriptor
publication, terminal consistency, and Full14 compatibility. Any Critical or
Important issue requires a focused RED/GREEN fix and scoped re-review before the
next step.

- [ ] **Step 2: Run the final synthetic acceptance suite exactly once**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: all tests pass. Do not rerun merely to obtain a cleaner duration.

- [ ] **Step 3: Compile and scan forbidden paths**

Run:

```bash
.venv/bin/python -m compileall -q src scripts tests
rg -n 'periodA|data_events|data16|700600|real.data' \
  config/mass_bin_reweighting_drop_top4.yaml \
  src/mass_bin_reweighting.py src/mass_bin_reweighting_run.py \
  scripts/run_mass_bin_reweighting.py
```

Expected: compile exit 0 and no prohibited new-study path. Legitimate historical
comments are not acceptable in the new config or command route.

- [ ] **Step 4: Bind pre-run immutable evidence**

Record paths, file types, sizes, mtimes, symlink inventory, and SHA-256 for all
four frozen runs, `data/raw/zz_363490.root`, the new config, and changed source
files. Verify the target
`runs/mass-reweighting-drop-top4-363490-2026-08-12` is absent and is not a
symlink. Abort before the real command if any gate fails.

- [ ] **Step 5: Write Task 5 acceptance report**

Record the one full-suite result, compile result, forbidden scan, protected hashes,
target-absence proof, and code-review verdict in `task-5-report.md`.

---

### Task 6: Execute the real study once and audit it read-only

**Files:**
- Create once: `runs/mass-reweighting-drop-top4-363490-2026-08-12/`
- Create: `.superpowers/sdd/2026-08-12-drop-top4-mass-bin-reweighting/task-6-report.md`

**Interfaces:**
- Consumes: the accepted CLI/config and frozen DSID 363490 MC input.
- Produces: one immutable selected or no-selection study plus a complete audit.

- [ ] **Step 1: Invoke the exact command once**

Run once:

```bash
.venv/bin/python -m scripts.run_mass_bin_reweighting \
  --input-run runs/full-baseline-363490-2026-08-11-r2 \
  --reference-run runs/full-training-363490-2026-08-11-r2 \
  --config config/mass_bin_reweighting_drop_top4.yaml \
  --run-dir runs/mass-reweighting-drop-top4-363490-2026-08-12
```

Wait for natural completion, reporting status at intervals no longer than 60
seconds. Do not interrupt, interact with, or retry the command.

- [ ] **Step 2: Audit structure, receipts, and terminal**

Without modifying artifacts, verify exact conditional allowlist, zero symlinks,
manifest-last timestamp, config byte equality, source receipts, output hashes and
row counts, finite JSON/CSV values, exact ten features, iteration prefix, 33/11
rows per iteration, all formulas and gates, and terminal/test-opened consistency.

- [ ] **Step 3: Inspect only the new approved plots**

Open the new iteration trade-off and ZZ efficiency-by-mass plots, plus selected
mass-sculpting only if the run is eligible. Verify labels, three working points,
all iterations, fixed mass bins, and scientific readability. Do not open any
periodA/data plot.

- [ ] **Step 4: Execute one same-path refusal**

Invoke the exact command once more only as the approved refusal check. Expected:
`FileExistsError` at output preflight before source binding, CSV parse, model fit,
or plot construction. Compare every protected and new-study hash before/after;
they must be identical.

- [ ] **Step 5: Record the scientific comparison**

Write all iteration AUC/KS/efficiency values and the four-way frozen comparison
to `task-6-report.md`. State one of exactly two conclusions:

```text
eligible: the first passing iteration was selected and MC test was evaluated once
no_eligible_iteration: the combination improved or failed to improve the trade-off, and MC test remained unopened
```

Never describe either outcome as a Higgs observation or as validation on real
data.

---

### Task 7: Documentation and final handoff

**Files:**
- Modify: `docs/roadmap/next-stage.md`
- Modify: `docs/project/overview.md` if it contains the active-method status
- Modify: the DSID 363490 progress and migration handoff documents linked from the current ledger
- Modify: `.superpowers/sdd/2026-08-12-drop-top4-mass-bin-reweighting/progress.md`
- Create: `.superpowers/sdd/2026-08-12-drop-top4-mass-bin-reweighting/task-7-report.md`

**Interfaces:**
- Consumes: immutable Task 6 metrics and audit.
- Produces: a physics-readable record of what was tested, what passed, and whether MC test remains sealed.

- [ ] **Step 1: Update documents from artifacts, not memory**

Record the exact terminal, selected iteration or null, all six-or-fewer iteration
metrics, four-way comparison, artifact path, manifest hash, test-opened value,
and periodA unopened status. Explain in physics language that the experiment tests
whether reduced mass proxies and background reweighting are complementary.

- [ ] **Step 2: Add a focused documentation test if exact status is machine-checked**

If an existing documentation test owns the active roadmap status, update that
single test with literal manifest-derived values and stale-text rejection. Run
only that focused test and record the result.

- [ ] **Step 3: Run final read-only consistency checks**

Recompute protected and new-study hashes, verify no symlinks or unexpected files,
and confirm `periodA`, `data_events`, and real-data paths never appear in the new
manifest, predictions, or logs. Do not rerun the model.

- [ ] **Step 4: Write the final report and handoff**

Append exact verification evidence, remaining scientific limitations, and the
recommended next experiment to `task-7-report.md` and `progress.md`. The next
step must be based on the fixed gates and MC-only evidence, not on periodA.
