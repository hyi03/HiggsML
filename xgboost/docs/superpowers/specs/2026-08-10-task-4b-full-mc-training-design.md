# Task 4B Full-MC Training Design

Date: 2026-08-10

## 1. Goal

Create a scientifically controlled, reproducible XGBoost training baseline from
the frozen Task 4A full-MC table. The new baseline must correct the extreme
event-count imbalance between Higgs and ZZ, use the scarce background events
efficiently, choose a modest model by MC-only cross-validation, and freeze an
independent test result without reading or scoring real data.

Task 4B produces a model that is eligible for a later blinded data-analysis
stage. It does not claim that a 125 GeV peak has been observed.

## 2. Frozen input baseline

The canonical input is:

```text
runs/full-baseline-2026-08-10/
├── config.yaml
├── processed/mc_events.csv.gz
└── artifacts/
    ├── cutflow.json
    ├── data_summary.json
    └── run_manifest.json
```

Verified selected-MC counts are:

| Split | ZZ label 0 | Higgs label 1 |
|---|---:|---:|
| train | 285 | 210715 |
| validation | 106 | 70143 |
| test | 80 | 70070 |
| total | 471 | 350928 |

The training command treats this run as read-only. It verifies that the Task 4A
manifest is complete, checks its declared configuration and raw-input hashes,
reconciles the MC CSV row counts with the summary, and records hashes of the
Task 4A manifest, summary, config snapshot, and MC CSV. Those hashes are checked
again immediately before publishing the Task 4B manifest so a changing input
cannot silently produce a mixed-provenance model.

The Task 4A `data_events.csv.gz` file is never opened by Task 4B.

## 3. Scientific and operational boundary

Task 4B includes:

- all 351399 selected MC events; no event-count downsampling;
- a new class-balanced, non-negative training-weight policy;
- deterministic five-fold cross-validation on the existing train and validation
  events;
- a fixed six-candidate XGBoost comparison;
- final fitting on train plus validation after model selection;
- one independent evaluation on the existing test split;
- MC-only loose, medium, and tight score working points;
- overfitting, stability, feature-leakage, and MC mass-sculpting diagnostics;
- a fresh, auditable training-run directory.

The effective training sampling fraction is therefore exactly `1.0` for both
classes. The manifest records this explicitly rather than leaving the absence of
sampling implicit.

Task 4B excludes:

- reading, scoring, plotting, or otherwise inspecting real data;
- inspecting the real-data 120--130 GeV interval;
- using `m4l` as a feature or target;
- changing selection, reconstruction, Task 4A outputs, luminosity, cross
  sections, k-factors, filter efficiencies, or sums of weights;
- reusing the historical 5,000-entry model or its `0.93` threshold;
- adding data periods or MC samples;
- broad automated hyperparameter optimization;
- returning to parameter selection after the independent test result is opened.

## 4. Feature contract

The exact frozen feature list remains `src.features.FEATURES`:

```text
lep1_pt, lep2_pt, lep3_pt, lep4_pt,
lep1_eta, lep2_eta, lep3_eta, lep4_eta,
mZ1, mZ2, pt4l, deltaR_Z1, deltaR_Z2, deltaPhi_ZZ
```

`m4l`, identifiers, sample metadata, truth metadata, split labels, and all weight
columns are forbidden model inputs. `m4l` may be joined to scores only after
prediction for MC-only sculpting diagnostics.

Training fails before model fitting if required fields are missing, feature or
weight values are non-finite, labels are not exactly 0 or 1, splits are unknown,
or event identifiers needed for deterministic folds are invalid. Repeated
`(channelNumber, eventNumber)` pairs are permitted only when every row in the
group has one label and one split; cross-label or cross-split groups are errors.

## 5. Training-weight policy

Signed `physical_weight` remains the only weight used for expected physical
yields. It is never overwritten.

XGBoost requires non-negative sample weights. For a fitting subset `T`, define
the Task 4B training weight of event `i` in class `c` as:

\[
w_i^{\mathrm{train}}
=
\lvert w_i^{\mathrm{physical}}\rvert
\frac{N_T}
{2\sum_{j\in T,\ y_j=c}\lvert w_j^{\mathrm{physical}}\rvert}.
\]

Consequences:

- every training weight is finite and non-negative;
- each class contributes total training weight `N_T / 2`;
- the combined fitting subset has mean training weight 1;
- negative MC events retain their sign in `physical_weight` but use their
  magnitude for classifier fitting;
- the 350928 Higgs events cannot dominate the objective merely by event count.

Weights are recomputed using only the fitting rows in each cross-validation
fold. The held-out fold does not influence the fitting-weight normalization.
The final model recomputes weights once from the complete train-plus-validation
development sample. Task 4B does not trust or reuse the per-sample
`train_weight` column written by Task 4A.

Evaluation AUC and distribution-comparison weights use
`abs(physical_weight)`, because those algorithms require non-negative weights.
Expected signal and background yields continue to use signed
`physical_weight` and are always labeled as signed yields.

## 6. Development, folds, and independent test isolation

The existing `train` and `validation` rows form the development sample. The
existing `test` rows stay sealed during candidate comparison, early stopping,
candidate selection, final tree-count selection, and working-point selection.

Each development event receives one fold in `[0, 4]` from a namespaced BLAKE2b
hash of `(channelNumber, eventNumber)`. The fold algorithm is deterministic and
independent of the existing split hash. Rows sharing that pair are retained as
distinct rows and necessarily receive the same fold. Every fold must contain
both classes. The pandas DataFrame index, which must be unique, is the row key
for assigning OOF predictions exactly once.

This identity rule is a post-first-run correction based on the measured Task 4A
MC table: five safe repeated-pair groups contain ten rows, with no group spanning
labels or splits and no exact full-row duplicates.

For each candidate and fold:

1. fit on four folds using Task 4B class-balanced training weights;
2. use the fifth fold only as the early-stopping evaluation set;
3. supply non-negative absolute physical evaluation weights;
4. save the held-out prediction exactly once;
5. record weighted and unweighted AUC and the best boosting iteration.

The program verifies that out-of-fold predictions contain every development
row index exactly once, contain no test row, and are reproducible for the same
input and configuration.

## 7. Fixed model candidates

Task 4B compares six candidates formed by:

```text
max_depth:       [2, 3, 4]
min_child_weight:[5, 20]
```

All candidates share:

```yaml
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
random_state: 42
```

The tracked training configuration also records the requested thread count.
Software versions and the effective XGBoost parameter dictionary are written to
the manifest.

The primary candidate metric is the mean five-fold absolute-physical-weighted
AUC. The candidate with the largest mean defines the best mean and its standard
error. Candidates within one standard error of that best mean are treated as
statistically tied. The selected candidate is the simplest eligible candidate,
ordered by lower `max_depth` first and then higher `min_child_weight`.

This one-standard-error rule prevents a noisy, slightly higher AUC from
automatically selecting a more complex tree.

## 8. Final fit and one-shot test evaluation

For the selected candidate, the final tree count is the rounded median of its
five positive best-iteration counts, with the XGBoost zero-based iteration
converted to a tree count. The final model is fitted once on all development
rows with this fixed tree count and no test eval set.

Only after the model file, chosen parameters, development OOF predictions, and
working points are fixed in memory may the program score the test rows. Test
results are evaluated and published once. The implementation exposes no
automatic path from test metrics back into candidate selection or fitting.

The independent test report includes at least:

- weighted and unweighted ROC-AUC;
- event counts and signed/absolute physical-weight sums by class;
- signal and background efficiencies at all three frozen working points;
- signed signal and background yields at all three working points;
- development-versus-test score-distribution checks by class;
- train/development-versus-test AUC gaps and warning reasons.

No fixed minimum AUC is used as a scientific pass/fail gate. The frozen result
is reported even when disappointing; a poor independent result must start a new
explicit design cycle rather than silently reopening this test set.

## 9. MC-only working points

Working points come only from the selected candidate's out-of-fold development
ZZ scores, weighted by `abs(physical_weight)`:

| Name | Target retained ZZ efficiency | Role |
|---|---:|---|
| loose | 0.50 | high-efficiency diagnostic |
| medium | 0.20 | default Task 4B operating point |
| tight | 0.10 | high-purity diagnostic |

Thresholds are weighted empirical quantiles with deterministic tie handling.
The output records target and achieved background efficiency, signal efficiency,
raw selected-event counts, and signed/absolute yields. Discreteness can prevent
exact target efficiency, so the achieved value is authoritative.

The numeric thresholds are fixed from OOF scores and applied unchanged to the
final model. Because a model fitted on all development rows can have a slightly
different score calibration from a four-fold fit, the report also records the
final model's development-sample achieved efficiencies as a calibration-drift
diagnostic. This diagnostic may raise a warning but must never recalibrate a
threshold using test events.

Required ordering is:

```text
threshold_loose <= threshold_medium <= threshold_tight
```

The historical `0.93` threshold is neither an input nor a fallback. Task 4B does
not maximize an Asimov significance to choose a cut because the small ZZ sample
and signed MC weights make an extremal threshold unstable.

## 10. Mass-sculpting and overfitting diagnostics

Although `m4l` is forbidden as a feature, correlated kinematic features can
still alter the background mass shape. Task 4B therefore evaluates MC-only
diagnostics using selected-candidate OOF predictions before the test is opened,
then reports the independent test comparison separately.

The report contains:

- ZZ score versus `m4l` correlation using non-negative evaluation weights;
- inclusive and loose/medium/tight ZZ `m4l` histograms;
- per-mass-bin ZZ selection efficiencies for all working points;
- weighted distribution-distance diagnostics between inclusive and selected ZZ;
- feature importance and score distributions for both classes;
- fold-by-fold AUC and chosen tree-count stability.

Because only 471 selected ZZ MC events exist, sculpting diagnostics are warning
and review evidence rather than an automatic claim that the model is valid or
invalid. Any warning is preserved in the manifest and plots. It cannot be
resolved by consulting real-data mass spectra during Task 4B.

The initial implementation uses an absolute-physical-weighted Pearson
correlation for score versus mass and an absolute-physical-weighted KS distance
for inclusive-versus-selected comparisons. Histogram bin edges are frozen in the
tracked training configuration so a later run cannot move bins after seeing a
shape.

## 11. CLI and run-directory contract

The intended command is:

```bash
.venv/bin/python -m scripts.train_full_mc \
  --input-run runs/full-baseline-2026-08-10 \
  --config config/full_training.yaml \
  --run-dir runs/full-training-2026-08-10
```

The approved output layout is:

```text
runs/full-training-2026-08-10/
├── config.yaml
├── model/
│   └── xgboost_model.json
├── artifacts/
│   ├── training_manifest.json
│   ├── weight_summary.json
│   ├── cv_results.csv
│   ├── metrics.json
│   └── working_points.json
├── predictions/
│   ├── oof_scores.csv.gz
│   └── test_scores.csv.gz
└── plots/
    ├── roc_curve.png
    ├── score_distributions.png
    ├── cv_stability.png
    ├── feature_importance.png
    └── mc_mass_sculpting.png
```

Rules:

- `--run-dir` is mandatory and must be absent, including dangling symlinks;
- the run directory is claimed atomically before children are written;
- no Task 4A or legacy `outputs/` file is modified;
- the config snapshot contains the exact source configuration bytes;
- files are written by atomic replacement within the claimed run directory;
- `training_manifest.json` is published last and marks successful completion;
- on failure, partial output remains visibly incomplete and a best-effort
  `artifacts/failure.json` records the error; partial output is not auto-deleted;
- output artifacts include SHA-256 hashes and row counts in the final manifest;
- a completed run is immutable input to later real-data evaluation.

Prediction tables contain only the columns necessary for audit and downstream
MC diagnostics: event identifiers, original split, fold where applicable,
label, `physical_weight`, `m4l`, and XGBoost score. They do not replace Task 4A
processed tables. `weight_summary.json` reports unique-pair count, duplicate-pair
group count, rows in duplicate-pair groups, cross-label group count, and
cross-split group count.

## 12. Validation and failure behavior

Training aborts before fitting when:

- the input is not a complete Task 4A full run;
- manifest, summary, configuration, hash, or row-count checks disagree;
- required columns, classes, splits, or finite values are missing;
- an identifier collision group spans labels or splits;
- a development fold lacks a class;
- a fitting subset has zero absolute physical-weight sum for either class;
- recomputed training weights are negative, non-finite, do not have mean 1, or
  do not give equal class totals within a strict floating-point tolerance;
- a test identifier appears in fitting, OOF prediction, parameter selection, or
  working-point selection;
- OOF DataFrame row indexes are duplicated or missing;
- thresholds are non-finite or violate their ordering;
- the requested output path already exists or cannot be claimed safely.

Errors identify the failed invariant and avoid vague partial-success messages.
Test metrics or plots are not published as final unless all required artifacts
and the final manifest are written successfully.

## 13. Test strategy

Implementation follows test-driven development. Focused tests cover:

1. the exact class-balanced weight formula, negative physical weights, finite
   checks, equal class totals, and mean-one normalization;
2. deterministic namespaced fold assignment and both-class fold validation;
3. test isolation and exact one-row-per-development-event OOF coverage;
4. the six-candidate matrix, weighted fold metrics, one-standard-error rule,
   simplicity ordering, and median best-iteration conversion;
5. weighted-quantile tie handling, threshold ordering, and achieved background
   efficiency and final-model calibration-drift reporting;
6. forbidden-feature enforcement, especially `m4l` and all metadata/weight
   columns;
7. input-run provenance, repeated hash checking, row-count reconciliation,
   atomic fresh-directory claim, atomic artifact publication, incomplete-run
   behavior, and overwrite refusal;
8. manifest schemas and artifact hashes;
9. MC-only plotting and sculpting diagnostics;
10. a small synthetic end-to-end CLI run that proves no data table is opened;
11. compatibility of the existing historical demo entry points and the complete
    existing pytest suite.

The real full-MC training command runs only after focused and full synthetic
tests pass. Its acceptance report records the exact command, wall time, chosen
candidate, fold metrics, final tree count, working points, test metrics, all
warnings, artifact hashes, and exact pytest result.

## 14. Scientific interpretation

Task 4B improves training validity; it cannot manufacture missing background or
real-data statistics. A clean independent MC result means the classifier is
ready for a later blinded application. It does not guarantee a visible 125 GeV
peak in the current period-A data.

The later data stage must be separately approved, expand data periods as
planned, freeze all Task 4B choices before unblinding, and report the mass
distribution without retuning on the observed 125 GeV region.

## 15. Completion criteria

Task 4B is complete only when:

- the approved class-balanced full-MC policy is implemented and tested;
- the six-candidate five-fold process completes deterministically;
- the final model is trained on development MC and test is evaluated once;
- three MC-only working points and all required diagnostics are frozen;
- the fresh run contains every required artifact and a final complete manifest;
- no real-data table was read or scored;
- no Task 4A, historical processed-data, or legacy output artifact changed;
- focused tests and the complete synthetic suite pass;
- documentation distinguishes the new Task 4B model from the historical
  5,000-entry model and from any later real-data result.
