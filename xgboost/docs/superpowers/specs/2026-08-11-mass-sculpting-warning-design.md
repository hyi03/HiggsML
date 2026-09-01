# Mass-sculpting warning correction design

## Context

The immutable DSID 363490 training run
`runs/full-training-363490-2026-08-11-r2` produced the intended Higgs MC
concentration near 125 GeV, but its frozen working points strongly changed the
ZZ mass shape.  The recorded inclusive-to-selected weighted KS distances are
0.291/0.408/0.458 for OOF ZZ and 0.324/0.432/0.473 for test ZZ.  Nevertheless,
`mass_sculpting.warning` is false.

The root cause is local to warning construction.  The evaluator calculates and
stores the KS distances, but it currently warns only for empty selected ZZ
samples and non-finite diagnostics.  It never compares a finite KS distance to
the configured `ks_distance_limit` (0.10).

## Scope and scientific interpretation

This change corrects the diagnostic, not the trained classifier.  The existing
successful run remains byte-for-byte immutable and continues to be the primary
evidence of the model's behavior.  Documentation must state both findings:

- the Higgs MC mass distribution has a visible peak near 125 GeV;
- the selected ZZ background is mass-sculpted, so the current classifier does
  not yet satisfy the background-shape goal.

Feature removal, decorrelation, adversarial training, and retraining are outside
this narrow correction.  They belong to a separate, auditable mitigation study.

## Warning behavior

For each of `oof_zz` and `test_zz`, and for each frozen working point
`loose`, `medium`, and `tight`, compare
`inclusive_to_selected_ks_distance` with `policy.ks_distance_limit`.

- A finite distance strictly greater than the limit adds one deterministic
  reason named `<split>.<working_point>.ks_distance`.
- An empty selected sample retains its existing
  `<split>.<working_point>.empty_selected_zz` reason and is not also labelled as
  a KS exceedance.
- Non-finite diagnostic handling remains unchanged.
- `mass_sculpting.warning` is true whenever any reason exists.
- The top-level training warning continues to be the logical OR of overfitting
  and mass-sculpting warnings.

The strict `>` comparison matches the existing overfitting warning convention.

## Verification and publication

Use test-driven development: first add a focused regression whose synthetic
finite KS distance exceeds 0.10 and observe the current false warning.  Then add
the smallest evaluator change and run focused, related, and full synthetic test
suites.  Independently recompute the six DSID 363490 KS comparisons from the
immutable metrics artifact and record the corrected expected warning reasons in
an SDD report.  Do not edit or republish the historical training manifest or
metrics artifact.

## Follow-on mitigation study

After this correction is reviewed, rank mass correlation and feature importance,
then evaluate a small predeclared feature-ablation set using development folds.
Compare weighted OOF AUC, test AUC only after candidate selection, score-mass
correlation, and all six working-point KS distances.  A mitigation may replace
the baseline only if it materially reduces sculpting without using `m4l` and
without hiding a loss of signal discrimination.
