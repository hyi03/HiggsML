# DropTop4 KNN Flatness Training Design

## 1. Purpose

This study tests whether a native mass-decorrelation training objective can
produce a useful Higgs-versus-continuum-ZZ classifier without sculpting the
continuum-ZZ four-lepton mass distribution. It is a new MC-only study, not a
continuation or repair of the frozen Full14 model.

The classifier uses the approved DropTop4 feature set and a KNN flatness loss
applied to background mass. The study preserves the existing qualification
requirements:

- weighted development OOF AUC must be at least `0.80`;
- inclusive-to-selected development OOF ZZ mass KS must be at most `0.10` at
  each of the loose, medium, and tight working points; and
- signal efficiency must exceed background efficiency at every working point.

The study does not read, hash, score, plot, or otherwise inspect periodA. It
does not expose held-out MC test rows unless a development OOF candidate first
passes every frozen qualification requirement.

## 2. Scientific scope and frozen sources

The source is the immutable DSID 363490 r2 MC baseline. Its selected MC table
contains:

- Higgs DSID 345060 signal MC, label `1`;
- continuum `ZZ(*) -> 4l` DSID 363490 background MC, label `0`.

The source run is `runs/full-baseline-363490-2026-08-11-r2`. Existing Full14,
mass-ablation, and mass-reweighting runs remain immutable historical
references. The implementation must bind the new run to the exact approved
source manifest and MC-table hashes before loading event rows.

The new study uses a new configuration, a new command, and a new output path.
It must not overwrite, append to, resume, or reuse any existing run directory.

## 3. Model features and leakage boundary

The ordered tree feature list is exactly:

1. `lep1_pt`
2. `lep2_pt`
3. `lep1_eta`
4. `lep2_eta`
5. `lep3_eta`
6. `lep4_eta`
7. `pt4l`
8. `deltaR_Z1`
9. `deltaR_Z2`
10. `deltaPhi_ZZ`

The removed features are `lep3_pt`, `lep4_pt`, `mZ1`, and `mZ2`.

`m4l` is supplied only to `KnnFlatnessLossFunction` as the uniformity
coordinate. It is never present in `UGradientBoostingClassifier.train_features`
and is never available to a tree split. Identifiers, DSIDs, source/profile
names, split labels, and all weights also remain forbidden tree features.

The flatness penalty is applied only to background rows with `label == 0`.
Signal mass is not constrained by the flatness objective.

## 4. Training architecture

The implementation uses `hep_ml.UGradientBoostingClassifier` with
`hep_ml.losses.KnnFlatnessLossFunction`. The model and loss parameters are
frozen as follows:

```yaml
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
```

The only candidate dimension is the flatness coefficient:

```text
0.0, 0.5, 1.0, 2.0, 3.0
```

Coefficient `0.0` is the same-model-family non-decorrelated baseline. No tree
parameter, neighbour count, group limit, feature, coefficient, working point,
or qualification threshold may be added or changed after candidate execution
starts.

## 5. Development-only OOF procedure

Candidate evaluation uses the existing deterministic five-fold development
assignment derived from event identity. For every candidate and fold:

1. the fit subset consists of the other four development folds;
2. class-balanced training weights are recomputed on that fit subset from
   finite `abs(physical_weight)` values;
3. the fold model receives a frame containing the ten tree features plus
   `m4l`, while `train_features` exposes only the ten approved tree features;
4. the held-out development fold receives scores from that fold model; and
5. the fold model and its training-only intermediates are discarded after the
   audit record is complete.

The five held-out development predictions are concatenated into one OOF score
column. Every development row must receive exactly one finite OOF prediction.
Duplicate or missing predictions are fatal run errors.

The candidate layer accepts only a validated development-only frame. Held-out
test loading is represented by a separate capability that is unavailable to
candidate training and OOF evaluation.

## 6. Weights and metrics

Fitting uses non-negative class-balanced weights derived from
`abs(physical_weight)`. The weights are recomputed inside each fold so that
information from its OOF rows cannot influence fit-weight normalization.

Scientific metrics do not use the class-balanced training weights. Weighted
AUC, efficiencies, score-mass correlation, and mass-shape diagnostics use
absolute physical MC weights, consistent with the frozen historical studies.

For each OOF candidate, working-point thresholds are determined only from its
OOF ZZ score distribution at the frozen background efficiencies:

- loose: `0.50`;
- medium: `0.20`;
- tight: `0.10`.

At each working point, the mass KS compares the inclusive OOF ZZ `m4l`
distribution with the score-selected OOF ZZ `m4l` distribution. The weighted
background score-mass correlation is recorded as a diagnostic but is not a
qualification requirement.

## 7. Qualification and deterministic selection

A candidate is eligible only when all of the following are true:

1. weighted OOF AUC is at least `0.80`;
2. loose OOF ZZ mass KS is at most `0.10`;
3. medium OOF ZZ mass KS is at most `0.10`;
4. tight OOF ZZ mass KS is at most `0.10`; and
5. signal efficiency is strictly greater than background efficiency at loose,
   medium, and tight.

If several candidates are eligible, selection uses this fixed ordering:

1. higher weighted OOF AUC;
2. lower maximum OOF ZZ mass KS;
3. lower flatness coefficient.

All comparisons use stored full-precision values. Rounded display values never
participate in qualification or tie-breaking.

If no candidate is eligible, the successful scientific terminal state is:

```json
{
  "status": "no_eligible_candidate",
  "selected_candidate": null,
  "test_opened": false
}
```

This state is not a software failure and publishes no selected model or test
artifact.

## 8. Single test-opening rule

Only an eligible selected candidate authorizes the run to:

1. train one final model on all development rows using the selected frozen
   coefficient;
2. open the held-out MC test rows once;
3. score those rows once with the final model; and
4. publish test metrics without any subsequent candidate, coefficient,
   parameter, threshold, or feature change.

Test results are a one-time reproducibility check, not another selection gate.
Failure to reproduce the development result must be reported; it cannot trigger
a retraining or tuning loop. Passing test results do not authorize periodA or
any other real-data access.

## 9. Components and interfaces

The implementation adds the following focused components:

- `config/decorrelation_training_drop_top4.yaml`: exact frozen study contract,
  source bindings, candidates, thresholds, parameters, and artifact allowlists.
- `src/decorrelation_training.py`: config-independent feature validation,
  model construction, fold fitting, OOF assembly, metrics, qualification, and
  deterministic selection.
- `src/decorrelation_training_run.py`: config validation, frozen-source binding,
  development/test access separation, no-clobber output handling, conditional
  artifact publication, failure publication, and manifest-last finalization.
- `src/decorrelation_training_plots.py`: MC-only candidate trade-off and KS
  plots, plus selected OOF/test mass-shape diagnostics when selection occurs.
- `scripts/run_decorrelation_training.py`: the sole production CLI for the
  study.

The implementation follows existing project patterns for immutable source
receipts, atomic writes, conditional artifact allowlists, terminal locks, and
manifest-last publication. It reuses validated evaluation and weighted-KS
helpers rather than introducing alternate metric definitions.

## 10. Artifact contract

Every successful scientific terminal state publishes:

- `config.yaml`;
- `artifacts/candidate_results.csv`;
- `artifacts/working_point_metrics.csv`;
- `artifacts/selection.json`;
- `predictions/oof_scores.csv.gz` containing development identifiers, labels,
  physical weights, mass, fold, and one score per frozen coefficient;
- `plots/candidate_tradeoff.png`;
- `plots/working_point_ks.png`;
- `artifacts/study_manifest.json`, published last.

An eligible selected state additionally publishes:

- `model/flatness_model.pkl`;
- `predictions/selected_oof_scores.csv.gz`;
- `predictions/test_scores.csv.gz`;
- `artifacts/test_metrics.json`;
- `plots/selected_mass_sculpting.png`.

The serialized model is a trusted local artifact and must not be loaded from an
unverified or user-supplied path. Its SHA-256, Python version, `hep_ml` version,
and relevant dependency versions are recorded in the manifest.

The run path must not exist before execution. An existing path, symlink,
protected-source containment, hash mismatch, schema mismatch, dependency
failure, non-finite value, fold violation, feature leak, duplicate prediction,
artifact mismatch, or source mutation is a software failure. Software failures
publish `failure.json` and `.terminal.failed` through the project's existing
failure-publication mechanism and never masquerade as `no_eligible_candidate`.

## 11. PeriodA and provenance boundary

The new source inventory contains only the approved study config, frozen MC
baseline config, frozen MC table, frozen MC summaries/manifests, and any
explicitly approved MC-only reference metadata. It excludes:

- `data_events.csv.gz`;
- `data16_periodA.root`;
- every path whose role is real collision data;
- broad directory hash scans that could read excluded files.

Source hashes are computed from an explicit allowlist. No code path in this
study accepts a real-data path or data-scoring option.

## 12. Plots and interpretation

All plots are labelled MC-only. The required common plots are:

1. weighted OOF AUC versus maximum OOF ZZ mass KS for the five coefficients,
   with the fixed AUC and KS qualification boundaries;
2. loose, medium, and tight OOF ZZ mass KS versus flatness coefficient.

If a candidate is selected, the conditional mass-sculpting plot compares
inclusive and selected ZZ mass shapes for OOF and test. It must not be described
as a Higgs observation, measurement, or real-data validation.

## 13. Test strategy

Implementation follows red-green-refactor TDD. Automated tests cover:

- exact config schema and rejection of every changed frozen decision;
- exact DropTop4 order and rejection of `m4l` or metadata in tree features;
- `m4l` availability to the loss while remaining absent from tree matrices;
- fold-local class-balanced weight normalization;
- deterministic five-fold OOF assembly with one score per row;
- candidate metrics, qualification boundaries, and full-precision tie-breaks;
- zero test-loader calls for `no_eligible_candidate`;
- exactly one test-loader call for an eligible selected candidate;
- conditional artifact allowlists and manifest-last publication;
- no-clobber, protected-path, symlink, source-hash, and mutation defenses;
- explicit exclusion of periodA and `data_events.csv.gz` from inventories;
- a small synthetic end-to-end run using the real model interface; and
- the complete existing pytest suite.

The actual MC-only production run may begin only after focused tests and the
complete regression suite pass. It runs once at a new path. Its result is
reported exactly as produced, including `no_eligible_candidate` when applicable.

## 14. Dependency and reproducibility policy

`hep_ml==0.8.0` is added as an explicit project dependency in
`requirements.txt`, and the resolved version is recorded in the manifest. The
production preflight requires version `0.8.0` and verifies that it exposes the
approved classifier and loss interfaces before claiming the output path.

No PyTorch, TensorFlow, adversarial model, DisCo loss, uBoost ensemble, mass
planing, threshold transformation, additional reweighting, calibration, or
feature search is part of this study.

## 15. Literature basis

The design is informed by:

- Stevens and Williams, *uBoost: A boosting method for producing uniform
  selection efficiencies from multivariate classifiers*, arXiv:1305.7248;
- Rogozhnikov et al., *New approaches for boosting to uniformity*,
  arXiv:1410.4140;
- Louppe, Kagan, and Cranmer, *Learning to Pivot with Adversarial Networks*,
  arXiv:1611.01046;
- Shimmin et al., *Decorrelated Jet Substructure Tagging using Adversarial
  Neural Networks*, arXiv:1703.03507;
- Bradshaw et al., *Mass Agnostic Jet Taggers*, arXiv:1908.08959; and
- Kasieczka and Shih, *DisCo Fever: Robust Networks Through Distance
  Correlation*, arXiv:2001.05310.

The first production study intentionally chooses KNN flatness boosting because
it directly targets uniform background score distributions, produces one score
for all three working points, has a maintained Python implementation, and adds
fewer new optimization freedoms than an adversarial or minibatch-neural-network
approach.
