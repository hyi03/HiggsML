# DSID 363490 mass-sculpting ablation design

## Scientific question

Can a smaller, physics-motivated feature set retain useful Higgs-versus-ZZ
discrimination while keeping the selected ZZ `m4l` shape close to the inclusive
shape?  The study is MC-only.  It must not use `m4l` as a feature, inspect real
data, use DSID 700600, or tune a candidate after viewing test results.

The immutable full-feature reference is
`runs/full-training-363490-2026-08-11-r2`.  Its OOF weighted AUC is 0.885296,
but its largest OOF mass-shape KS distance is 0.457954, well above the 0.10
limit.

## Predeclared feature profiles

The reference profile is the existing 14-feature model and is not retrained:

- `full14_reference`: four lepton transverse momenta, four lepton eta values,
  `mZ1`, `mZ2`, `pt4l`, `deltaR_Z1`, `deltaR_Z2`, and `deltaPhi_ZZ`.

Three new profiles are evaluated:

- `drop_top4_mass_proxies`: remove `lep3_pt`, `lep4_pt`, `mZ1`, and `mZ2`;
  retain leading-lepton momenta plus eta, `pt4l`, and angular information.
- `shape8`: retain the four eta values, `pt4l`, `deltaR_Z1`, `deltaR_Z2`, and
  `deltaPhi_ZZ`; remove all individual lepton transverse momenta and both
  reconstructed Z masses.
- `angular_eta7`: retain only the four eta values and three angular variables;
  this is the strongest simple decorrelation candidate and provides a useful
  negative/control result if discrimination becomes too weak.

No profile may contain `m4l`, an event identity, split, label, or weight.

## Sealed comparison protocol

Use the existing deterministic train/validation development folds and the same
six XGBoost hyperparameter candidates, training-weight policy, early stopping,
and random seed as `config/full_training.yaml`.  For each new profile:

1. cross-validate all six candidates using development events only;
2. choose that profile's model candidate by the existing CV rule;
3. create OOF scores for every development event exactly once;
4. derive loose/medium/tight thresholds from OOF ZZ only;
5. calculate OOF weighted AUC, score–mass correlation, working-point signal
   efficiency, and inclusive-to-selected ZZ mass KS distances.

The held-out test split must not be scored during this comparison.

## Profile eligibility and selection

A new profile is eligible only if all of the following hold on OOF evidence:

- every loose/medium/tight ZZ mass KS distance is finite and at most 0.10;
- weighted OOF AUC is at least 0.80;
- at each working point, signal efficiency is strictly greater than that
  point's target ZZ efficiency (0.50, 0.20, and 0.10).

Among eligible profiles, select the highest weighted OOF AUC; break an exact
tie by smaller maximum OOF KS, then by profile name.  The full14 reference is
reported but is ineligible because its OOF KS distances exceed 0.10.

If no new profile is eligible, publish a complete `no_eligible_profile` study
and stop before any new test scoring.  This is a valid scientific outcome and
means simple feature removal is insufficient.

## Test opening and final evidence

Selection and test opening must be one sealed public operation. It accepts only
the MC frame, training policy, and an optional model factory—not caller-supplied
development results, a selected result, a transferable certificate, or
eligibility-threshold overrides. The operation evaluates all three predeclared
profiles itself in their canonical order captured at implementation-definition
time, not by reading the mutable public profile mapping at invocation time. It
retains a deep snapshot of the complete development result mapping, recomputes
the fixed 0.80/0.10 eligibility/ranking rule
internally, and then follows one branch:

- no eligible profile: return a complete `no_eligible_profile` decision without
  locating or scoring test rows;
- one selected profile: fit only that profile on all development events and
  score the held-out test exactly once.

There is no public `fit_and_score_selected(result)` interface or result-mapping
input. This avoids both unreliable Python capability-token designs and borrowed
`ModelSelectionResult` objects. The returned outcome contains all canonical
development results plus the optional internally selected result and final
evidence. Nested result mappings are immutable views and score tables are
defensive copies, so later mutation of evaluator-owned objects cannot rewrite
the published decision evidence. Use the already frozen OOF thresholds and report test weighted AUC,
all working-point efficiencies, score–mass correlation, and test ZZ mass KS
distances. Test performance cannot change the internally selected profile.

The study may call a profile a successful simple mitigation only if all three
test ZZ KS distances are also finite and at most 0.10.  A test failure is
reported as failure to reproduce, not used to select another profile.

## Software boundaries and artifacts

Parameterize existing model-fitting and scoring functions with an explicit
feature sequence while preserving the current 14-feature default for all
existing callers.  Put study orchestration and eligibility logic in a separate
module.  The CLI claims one fresh output directory atomically, refuses existing
or symlink paths before loading the MC table, publishes fixed-name artifacts,
and writes its terminal manifest last.

The fresh study directory is
`runs/mass-ablation-363490-2026-08-11`.  Its allowlist is:

- `config.yaml`
- `artifacts/profile_results.csv`
- `artifacts/selection.json`
- `artifacts/test_metrics.json` only when a profile is selected
- `model/xgboost_model.json` only when a profile is selected
- `predictions/selected_oof_scores.csv.gz` only when a profile is selected
- `predictions/test_scores.csv.gz` only when a profile is selected
- `plots/oof_profile_tradeoff.png`
- `plots/selected_mass_sculpting.png` only when a profile is selected
- `artifacts/study_manifest.json`, published last

On failure, publish only a fixed `failure.json` terminal record according to
the established no-overwrite safety pattern.  Every artifact is finite,
hash-bound in the manifest, and derived from the immutable r2 baseline input.

## Verification

Use strict TDD for feature parameterization, eligibility, sealed test ordering,
fresh-path refusal, artifact allowlisting, and manifest-last publication.  Run
focused tests, the full synthetic suite, then the real study command exactly
once.  Independently review code and the completed study.  Do not alter the
reference baseline or training run.
