# Mass-Bin Iterative Reweighting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add and execute a sealed XGBoost study that keeps the existing 14
features but iteratively reweights development-ZZ training events in fixed
`m4l` bins, accepting only an iteration that passes frozen OOF and independent
MC-test AUC/KS gates.

**Architecture:** Extend the existing training seam with optional aligned
per-row fitting multipliers while preserving default behavior. A pure
development-only module performs fixed-bin diagnostics, multiplier updates,
and first-eligible stopping; its sole top-level study operation opens test only
after internal selection freezes. A separate descriptor-owned runner publishes
an exact conditional artifact set and manifest last in a fresh immutable run.

**Tech Stack:** Python 3.11+, pandas, NumPy, scikit-learn, XGBoost, Matplotlib,
PyYAML, pytest, existing `full_training_*` and safe publication primitives.

## Global Constraints

- Follow
  `docs/superpowers/specs/2026-08-11-mass-bin-iterative-reweighting-design.md`
  exactly.
- Preserve the exact 14-feature tuple; `m4l` remains audit-only and must never
  enter `model.fit` or `predict_proba`.
- Use only Higgs 345060 and ZZ 363490 MC. Do not read or score periodA or any
  real-data artifact. Do not run DSID 700600.
- Keep the three existing r2/ablation runs and `data/raw/zz_363490.root`
  immutable; capture and compare protected hashes before and after each task
  that can execute a run.
- OOF thresholds and diagnostics use original absolute physical weights.
  Signed physical weights remain available only for physical-yield reporting.
  Reweighting multipliers affect fitting weights only.
- Fixed constants: edges 105:5:160 GeV, effective-count minimum 100,
  `delta=1e-6`, `eta=0.5`, round bounds `[0.5,2.0]`, cumulative bounds
  `[0.2,5.0]`, at most five corrections after iteration zero, AUC floor 0.80,
  and all three KS limits 0.10.
- The first OOF-eligible iteration stops the loop. If none is eligible, test
  must not be located, validated, fitted, or scored.
- An eligible iteration opens independent MC test exactly once. Test cannot
  change any iteration, weight, candidate, tree count, threshold, or gate.
- Use strict RED → GREEN TDD for every production behavior. Capture exact RED
  and GREEN commands in task reports.
- The project is wholly untracked inside its parent repository. Do not stage,
  commit, branch, merge, or otherwise write Git state. Replace commit steps by
  task-scoped snapshots, SHA-256 inventories, reports, and independent review.
- Never overwrite, delete, reuse, or repair a failed/complete run directory.

---

### Task 1: Add a backward-compatible fitting-multiplier seam

**Files:**

- Modify: `src/full_training_policy.py`
- Modify: `src/full_training_model.py`
- Modify: `tests/test_full_training_policy.py`
- Modify: `tests/test_full_training_model.py`
- Create: `.superpowers/sdd/2026-08-11-mass-bin-iterative-reweighting/task-1-report.md`

**Interfaces:**

- `class_balanced_training_weights(frame, *, multipliers=None) -> np.ndarray`
- `cross_validate_candidates(frame, policy, model_factory=None, *,
  training_weight_multipliers=None, features=FEATURES) -> ModelSelectionResult`
- `fit_final_model(frame, selection, policy, model_factory=None, *,
  training_weight_multipliers=None, features=FEATURES) -> Any`
- `multipliers` is a finite, strictly positive `pd.Series` whose index exactly
  equals the input frame index. `None` preserves existing numerical behavior.

- [x] **Step 1: Snapshot and baseline**

Copy the four target files into the task snapshot directory outside the
project tree, record SHA-256 values, and run:

```bash
.venv/bin/python -m pytest \
  tests/test_full_training_policy.py \
  tests/test_full_training_model.py -q
```

Record the exact baseline count. Do not modify production code yet.

- [x] **Step 2: Write RED weight-policy tests**

Add tests equivalent to:

```python
def test_training_multipliers_preserve_class_balance(frame):
    multipliers = pd.Series(1.0, index=frame.index)
    zz = frame["label"].eq(0)
    multipliers.loc[zz & frame["m4l"].between(120, 130, inclusive="left")] = 2.0
    weights = class_balanced_training_weights(frame, multipliers=multipliers)
    assert weights[zz].sum() == pytest.approx(len(frame) / 2)
    assert weights[~zz].sum() == pytest.approx(len(frame) / 2)
    assert weights.mean() == pytest.approx(1.0)

def test_default_weights_are_exactly_unchanged(frame):
    before = class_balanced_training_weights(frame)
    after = class_balanced_training_weights(frame, multipliers=None)
    np.testing.assert_array_equal(after, before)
```

Also require rejection before output allocation for non-Series values,
misordered/missing/extra indices, zero, negative, NaN, and infinity.

- [x] **Step 3: Write RED model-seam tests**

Use recording classifiers to prove fitting rows receive multiplied/class-
balanced weights, evaluation sets still receive
`abs(evaluation.physical_weight)`, and `predict_proba` sees exactly the frozen
features. Assert a multiplier Series with any test index is rejected when the
function receives a development-only frame.

- [x] **Step 4: Run RED**

Run only the new tests with `-q`. Expected failures must be `TypeError` for the
missing keyword or assertions showing the old fitting weights; collection and
fixtures must be green.

- [x] **Step 5: Implement the minimal seam**

Implement strict alignment in one private helper. In class balancing, replace
the per-class base value by:

```python
adjusted = np.abs(physical) * validated_multipliers
```

then retain the existing exact per-class target and mean-one checks. In every
fold, pass only `training_weight_multipliers.loc[fitting.index]`; never pass a
multiplier to evaluation AUC, early-stopping evaluation weights, scoring, or
working-point construction. Final fitting receives only development indices.

- [x] **Step 6: Run GREEN and default-path regression**

Run the two focused files, all Task 4B/8A model tests, and a deterministic
default-versus-`None` prediction comparison using the recording factory.

- [x] **Step 7: Review and report**

Diff against the snapshot. Verify no default caller changes behavior, no
evaluation weight uses a multiplier, and no `m4l` column reaches a classifier.
Write the Task 1 report and record protected-run hashes.

---

### Task 2: Implement fixed-bin diagnostics and multiplier mathematics

**Files:**

- Create: `src/mass_bin_reweighting.py`
- Create: `tests/test_mass_bin_reweighting.py`
- Create: `.superpowers/sdd/2026-08-11-mass-bin-iterative-reweighting/task-2-report.md`

**Interfaces:**

```python
@dataclass(frozen=True)
class ReweightingPolicy:
    mass_bin_edges: tuple[float, ...]
    minimum_effective_count: float
    epsilon_floor: float
    damping: float
    round_factor_bounds: tuple[float, float]
    cumulative_bounds: tuple[float, float]
    maximum_corrections: int
    auc_floor: float
    ks_limit: float

summarize_development_zz_bins(
    development: pd.DataFrame, policy: ReweightingPolicy
) -> pd.DataFrame

compute_bin_efficiencies(
    oof: pd.DataFrame,
    working_points: Mapping[str, Mapping[str, object]],
    policy: ReweightingPolicy,
) -> pd.DataFrame

update_cumulative_multipliers(
    efficiencies: pd.DataFrame,
    current: pd.Series,
    policy: ReweightingPolicy,
) -> pd.Series
```

- [x] **Step 1: Write RED policy and bin-assignment tests**

Require exact monotonic edges `(105,110,...,160)`, exactly eleven bins,
left-closed/right-open assignment except inclusive 160 GeV endpoint, and
rejection of masses outside the configured range, duplicate edges, non-finite
values, missing labels/weights, and non-development splits.

- [x] **Step 2: Write RED effective-count tests**

Construct literal weighted bins and assert
`(sum(abs(w))**2 / sum(w**2))`. Require a bin with 99.999 effective events to
fail and exactly 100 to pass. No automatic merging or edge changes are
permitted.

- [x] **Step 3: Write RED efficiency tests**

Use literal OOF rows and thresholds to assert per-bin numerator, denominator,
efficiency, effective count, and
`sqrt(epsilon*(1-epsilon)/N_eff)` for each exact key
`{loose,medium,tight}`. Reject missing/extra working points, non-finite scores,
and weights not taken from the original OOF `physical_weight` column.

- [x] **Step 4: Write RED multiplier-update tests**

For a bin whose efficiencies exceed `(0.50,0.20,0.10)`, assert the next
multiplier increases by the exact geometric formula. Assert the inverse for an
under-selected bin. Add exact tests for `delta`, `eta`, 0.5/2.0 round clipping,
0.2/5.0 cumulative clipping, deterministic bin ordering, and finite strictly
positive output.

- [x] **Step 5: Run RED**

Run `tests/test_mass_bin_reweighting.py -q`; expected failure is the missing
module/API, followed by missing behavior—not fixture errors.

- [x] **Step 6: Implement pure mathematics**

Use no model fitting, file I/O, global state, or mutation. Return defensive
DataFrame/Series copies with fixed names and index order. Keep physical weights
unchanged in every returned audit table.

- [x] **Step 7: Run GREEN and property probes**

Run the focused file. Additionally probe monotonic response over a grid of
efficiencies and confirm every output stays within cumulative bounds.

- [x] **Step 8: Review and report**

Review literal formulas against the design, run `compileall` for the new
module, and write the Task 2 report.

---

### Task 3: Build the sealed development loop and one-time test terminal

**Files:**

- Modify: `src/mass_bin_reweighting.py`
- Modify: `tests/test_mass_bin_reweighting.py`
- Test: `tests/test_full_training_evaluation.py`
- Create: `.superpowers/sdd/2026-08-11-mass-bin-iterative-reweighting/task-3-report.md`

**Interfaces:**

```python
@dataclass(frozen=True)
class IterationEvidence:
    iteration: int
    cumulative_multipliers: Mapping[str, float]
    candidate_name: str
    final_tree_count: int
    weighted_oof_auc: float
    working_points: Mapping[str, Mapping[str, object]]
    zz_ks_distances: Mapping[str, float]
    signal_efficiencies: Mapping[str, float]
    achieved_zz_efficiencies: Mapping[str, float]
    bin_efficiencies: pd.DataFrame
    eligible: bool
    eligibility_reasons: tuple[str, ...]

@dataclass(frozen=True)
class ReweightingStudyOutcome:
    status: str
    iterations: tuple[IterationEvidence, ...]
    selected_iteration: int | None
    selected_oof_scores: pd.DataFrame | None
    model: Any | None
    test_scores: pd.DataFrame | None
    test_metrics: Mapping[str, object] | None

run_mass_bin_reweighting_study(
    frame: pd.DataFrame,
    training_policy: TrainingPolicy,
    reweighting_policy: ReweightingPolicy,
    *,
    model_factory=None,
) -> ReweightingStudyOutcome
```

This is the sole public operation capable of opening test. It internally
derives all iterations, selection, multipliers, and frozen thresholds; callers
cannot inject a selected iteration or development result.

- [x] **Step 1: Write RED iteration-zero and update-loop tests**

Use a deterministic recording model factory whose OOF scores make specific
bins over-selected. Assert iteration zero uses all-one multipliers, iteration
one uses the exact Task 2 update, all six candidates are refitted, and no input
DataFrame or physical weight is mutated.

- [x] **Step 2: Write RED stopping tests**

Cover:

```text
iteration 0 eligible -> exactly one iteration
iteration 2 first eligible -> exactly iterations 0,1,2
iterations 0..5 ineligible -> no_eligible_iteration
insufficient bin statistics -> insufficient_bin_statistics
```

Eligibility must require AUC, all three KS values, and strictly better signal
efficiency at all working points. Boundary equality for AUC/KS passes; signal
efficiency equality fails.

- [x] **Step 3: Write RED sealed-test tests**

Poison all test analysis columns with NaN while leaving `split` readable. The
no-eligible and insufficient-statistics branches must return normally without
model-factory final-fit calls or any test validation. Make an eligible branch
with a recording factory and assert one final development fit, one test
`predict_proba`, OOF-frozen thresholds, and no later iteration.

Reject public signature additions for selected iteration, thresholds,
development results, multipliers, AUC floor, or KS limit. Monkeypatch public
constants and prove the operation uses the validated policy instance captured
at entry, not mutable module globals.

- [x] **Step 4: Write RED test-terminal classification tests**

Literal test evidence must yield exactly
`eligible_iteration_test_reproduced` or `test_nonreproduction`. Changing test
labels/scores may change only that terminal and test metrics; it must not change
iterations, selected iteration, candidate, tree count, multipliers, or
thresholds.

- [x] **Step 5: Run RED**

Run the focused new tests plus `tests/test_full_training_evaluation.py`. Record
the exact expected failures.

- [x] **Step 6: Implement the minimal atomic study**

Create a development copy using only the `split` column before any full-frame
validation. For every iteration:

1. map the eleven cumulative bin multipliers onto development ZZ rows and one
   onto Higgs rows;
2. call the Task 1 OOF seam;
3. construct working points and diagnostics with physical weights;
4. freeze defensive evidence;
5. stop at first eligibility or update the bin multipliers.

Only after eligibility, validate the complete MC frame, fit with the selected
cumulative multipliers on all development rows, and score test once.

- [x] **Step 7: Run GREEN and real-XGBoost tiny integration**

Run the focused tests, then a synthetic finite frame through real
`XGBClassifier` for at least two iterations. Assert feature count 14, no `m4l`
feature, finite metrics, and deterministic output.

- [x] **Step 8: Independent adversarial review and report**

Review no-test-before-selection, injection/substitution paths, mutable aliases,
physical-versus-training weights, first-eligible stopping, and test terminal
semantics. Fix every Critical/Important finding with a new RED/GREEN round.
Write the Task 3 report only after scoped re-review approval.

---

### Task 4: Add fixed diagnostic plots

**Files:**

- Create: `src/mass_bin_reweighting_plots.py`
- Create: `tests/test_mass_bin_reweighting_plots.py`
- Create: `.superpowers/sdd/2026-08-11-mass-bin-iterative-reweighting/task-4-report.md`

**Interfaces:**

```python
build_iteration_tradeoff_png(outcome: ReweightingStudyOutcome) -> bytes
build_zz_efficiency_by_mass_png(outcome: ReweightingStudyOutcome) -> bytes
build_selected_mass_sculpting_png(
    outcome: ReweightingStudyOutcome,
) -> bytes
```

- [x] **Step 1: Write RED plot-contract tests**

Require PNG signatures, non-empty finite plotting tables, fixed titles/axes,
0.80 AUC and 0.10 KS lines, all executed iterations, exact three working-point
keys, exact 0.50/0.20/0.10 target lines, fixed eleven mass-bin centers, and the
effective-binomial error formula.

- [x] **Step 2: Write RED weight and threshold tests**

Intercept histogram/errorbar calls. Assert multiplier heatmap values come from
the cumulative audit map, ZZ efficiency plots use physical weights, and the
selected mass plot uses original absolute physical weights plus OOF-frozen
thresholds. Training multipliers must never appear as histogram weights.

- [x] **Step 3: Write RED artifact-conditional tests**

`build_selected_mass_sculpting_png` must reject no-selected outcomes before
accessing test scores. Existing output files, regular directories, direct
symlinks, and dangling symlinks must be rejected by the publication layer
before Matplotlib is invoked.

- [x] **Step 4: Run RED, implement, and run GREEN**

Implement fixed Agg-backend plots with explicit figure closure and deterministic
labels. Run the focused tests and visually inspect synthetic eligible and
no-eligible images for clipping, misleading scales, and gate-line placement.

- [x] **Step 5: Review and report**

Confirm plot text calls every result OOF or test explicitly and never implies a
real-data observation. Write the Task 4 report.

---

### Task 5: Add exact config, safe publication, and CLI orchestration

**Files:**

- Create: `config/mass_bin_reweighting.yaml`
- Create: `src/mass_bin_reweighting_run.py`
- Create: `scripts/run_mass_bin_reweighting.py`
- Create: `tests/test_mass_bin_reweighting_run.py`
- Create: `tests/test_run_mass_bin_reweighting_script.py`
- Create: `.superpowers/sdd/2026-08-11-mass-bin-iterative-reweighting/task-5-report.md`

**Interfaces:**

```text
python -m scripts.run_mass_bin_reweighting \
  --input-run runs/full-baseline-363490-2026-08-11-r2 \
  --reference-run runs/full-training-363490-2026-08-11-r2 \
  --config config/mass_bin_reweighting.yaml \
  --run-dir <fresh-path>
```

The config exactly binds schema 1.0, both source manifest hashes, the full-14
feature tuple, every fixed update constant, all three gates, and both exact
conditional allowlists.

- [x] **Step 1: Write RED config tests**

Require exact keys and values. Reject defaults, unknown keys, reordered or
altered features, changed bins/round count/damping/bounds/gates, wrong source
hashes, and contradictory artifact names.

- [x] **Step 2: Write RED output-preflight and claim tests**

Reuse the reviewed Task 8C adversarial matrix: existing directory/file,
direct/dangling symlink, concurrent claim, parent substitution, output inside a
protected source, and immediate freshness recheck. All occupied targets must
refuse before `pd.read_csv`, model factory, or plot creation.

- [x] **Step 3: Write RED sealed CLI-order tests**

Assert exact order:

```text
output_preflight
source_bind_without_csv_parse
output_rebind
atomic_claim
single_mc_parse
development_iteration
[final_fit_and_test_score]
write_conditional_artifacts
source_recheck
publish_manifest_last
```

No-eligible and insufficient-statistics traces omit the bracketed step.
Monkeypatch `pd.read_csv` to prove zero pre-claim parses and exactly one
post-claim parse.

- [x] **Step 4: Write RED artifact and terminal tests**

Require the exact eight-file complete no-selection set (including manifest)
and exact thirteen-file selected set. Assert CSV row counts, finite JSON/CSV,
source total/split rows, input/config/output hashes, selected/test-opened
consistency, manifest newest/publication-last, failure-only terminal after an
exception, and descriptor-bound protection against staged-path substitution.

- [x] **Step 5: Run RED**

Run both new test files. Expected failures must be only missing config/module or
unimplemented behavior.

- [x] **Step 6: Implement using reviewed primitives**

Adapt, do not weaken, the safe primitives in `mass_sculpting_ablation_run.py`,
`full_training_run.py`, and `external_zz_run.py`. Bind source bytes/hashes
without CSV parsing, claim atomically, parse once, publish through directory
descriptors with no-follow/no-clobber, recheck sources, and publish the
descriptor-bound manifest last.

- [x] **Step 7: Run GREEN and integration**

Run Task 5 focused tests, Tasks 1--4 related tests, the real-XGBoost tiny CLI
integration for no-eligible and eligible synthetic outcomes, then the complete
suite and `compileall`. No real r2 study is allowed in this task.

- [x] **Step 8: Independent safety/science review and report**

Review source-read timing, no-test branch, exact allowlists, finite values,
row-count/hash provenance, failure terminal, symlink races, same-path refusal,
and protected-reference immutability. Repair every Critical/Important finding
by RED/GREEN and obtain scoped approval. Write the Task 5 report.

---

### Task 6: Execute and audit the real DSID 363490 study once

**Files:**

- Create only through CLI:
  `runs/mass-reweighting-363490-2026-08-11/`
- Create: `.superpowers/sdd/2026-08-11-mass-bin-iterative-reweighting/task-6-report.md`
- Modify: `.superpowers/sdd/2026-08-11-dsid-363490-training/progress.md`
- Modify: `CODEX_ACCOUNT_MIGRATION_HANDOFF.md`
- Modify: `docs/roadmap/next-stage.md`

- [x] **Step 1: Fresh preflight**

Run the complete test suite once. Hash every file in the three protected runs
and the ROOT input, inventory symlinks, confirm the target is absent and not a
symlink, and confirm no real-data path appears in the new config or CLI.

- [x] **Step 2: Invoke the exact real command once**

```bash
.venv/bin/python -m scripts.run_mass_bin_reweighting \
  --input-run runs/full-baseline-363490-2026-08-11-r2 \
  --reference-run runs/full-training-363490-2026-08-11-r2 \
  --config config/mass_bin_reweighting.yaml \
  --run-dir runs/mass-reweighting-363490-2026-08-11
```

Do not interrupt or retry. Report progress at least every 60 seconds.

- [x] **Step 3: Audit the scientific terminal**

Verify iteration zero reproduces the reference OOF behavior within the exact
declared numerical tolerance, every multiplier follows the fixed formula, no
round exceeds bounds, candidate/tree/threshold evidence is complete, and the
terminal is exactly one of the three accepted values. For no eligibility,
prove test remained unopened. For eligibility, prove test was opened once and
could not change selection.

- [x] **Step 4: Inspect only new plots**

Check labels, bin centers/error bars, fixed AUC/KS/efficiency lines, multiplier
heatmap, and compatibility between the visual shape and recorded numbers.

- [x] **Step 5: Same-path refusal and immutable-input audit**

Invoke the exact command once more only for refusal. Require rejection at
output preflight before CSV/model access and byte-identical study artifacts.
Re-hash every protected source and verify no symlink or unapproved artifact.

- [x] **Step 6: Independent final review**

An independent reviewer recomputes all iteration formulas and gates from the
published CSVs, verifies conditional artifacts and test sealing, and classifies
all Critical/Important/Minor findings. Do not proceed to periodA on any open
Critical/Important issue or any terminal other than
`eligible_iteration_test_reproduced`.

- [x] **Step 7: Final documentation and verification**

Record the honest physics conclusion, elapsed time, exact metrics/hashes, and
next allowed action. Run the complete suite again after documentation changes.
Update the migration handoff so another account cannot mistake an unsuccessful
iteration for authorization to inspect periodA.
