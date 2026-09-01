# DSID 363490 sculpting diagnostic source notes

## Reporting job

- Audience: technical, with physics-first interpretation.
- Question: why does the immutable classifier change the ZZ `m4l` shape even
  though `m4l` is excluded from the 14 training features?
- Decision supported: define a small, predeclared feature-ablation study.
- Scope: selected DSID 363490 ZZ MC in the successful r2 baseline and training
  runs; no real data and no 700600.

## Chart map

1. `ks-chart`: grouped categorical bar chart; working point on x, weighted KS
   on y, OOF/test grouping, and a 0.10 warning reference.  It supports the claim
   that all frozen cuts sculpt mass and the effect reproduces on test.
2. `mass-correlation-chart`: sorted horizontal-style categorical bar contract;
   feature versus test-ZZ weighted Pearson correlation with `m4l`.  It supports
   prioritizing lepton transverse momenta and reconstructed Z masses for causal
   ablation.  Exact OOF/test and gain values remain in the adjacent table.

Palette policy: single-root preferred for the feature chart; hard two-root cap
for OOF versus test.  Non-color distinction is provided by category/group labels
and exact tooltip/table values.

## Reproducibility

The analysis reads the immutable baseline MC table, OOF score table, test score
table, model JSON, and metrics JSON.  It verifies row alignment with
`channelNumber`, `eventNumber`, `split`, and `label`; restricts to label 0; uses
absolute `physical_weight`; computes weighted Pearson values using
`src.full_training_evaluation.weighted_pearson`; and normalizes XGBoost gain by
the total gain across the 14 frozen feature names.

The score-table contract omits most training features, so a verified positional
alignment to the baseline MC table is necessary.  This is a descriptive
diagnostic.  Correlated inputs and nonlinear interactions prevent assigning
causality until the predeclared ablation study is run.
