# Mass-Bin Iterative Reweighting Design

Date: 2026-08-11

## 1. Objective

Build a version 1.1 development-only study that keeps the frozen 14 XGBoost
features unchanged while iteratively changing only the relative *training*
importance of continuum-ZZ events in fixed `m4l` bins. The aim is to preserve
useful Higgs/ZZ discrimination while making the selected-ZZ efficiency
approximately independent of `m4l`.

The study is successful only if a predeclared iteration satisfies all OOF
eligibility gates and subsequently reproduces them on independent MC test.
PeriodA and every real-data signal-region value remain sealed throughout this
study.

## 2. Frozen inputs and non-goals

The study reads, but never modifies or republishes:

- `runs/full-baseline-363490-2026-08-11-r2`;
- `runs/full-training-363490-2026-08-11-r2`;
- `runs/mass-ablation-363490-2026-08-11`;
- `data/raw/zz_363490.root`.

The reference model remains immediately reloadable if this study fails. A
failed reweighting study does not make that reference model safe for a periodA
signal-region analysis; the reference model retains its recorded ZZ mass
sculpting.

This study does not:

- add, remove, reorder, transform, or standardize model features;
- use `m4l` as a model feature;
- change event labels, physical weights, selection, folds, candidates, or
  working-point target efficiencies;
- use DSID 700600 or real data;
- relax a gate, add an iteration, or change a bin after seeing an outcome;
- claim a periodA result.

## 3. Model features and base policy

Every iteration uses the exact existing 14-feature tuple:

```text
lep1_pt, lep2_pt, lep3_pt, lep4_pt,
lep1_eta, lep2_eta, lep3_eta, lep4_eta,
mZ1, mZ2, pt4l, deltaR_Z1, deltaR_Z2, deltaPhi_ZZ
```

The five deterministic development folds, random seed 42, six frozen
`max_depth`/`min_child_weight` candidates, one-standard-error candidate rule,
early stopping, and loose/medium/tight target-ZZ efficiencies 0.50/0.20/0.10
come unchanged from `config/full_training.yaml`.

## 4. Fixed mass bins and statistical gate

The half-open development-ZZ mass bins are fixed at:

```text
[105,110), [110,115), ..., [155,160] GeV
```

The last bin includes the upper endpoint. Before iteration zero, each bin must
have positive absolute physical-weight sum and effective count

\[
N_{\mathrm{eff},b}=\frac{(\sum_i |w_i|)^2}{\sum_i w_i^2}\ge100.
\]

Failure publishes `insufficient_bin_statistics`; it does not merge bins or
change edges. The real development sample has 9,603 ZZ rows, 289--1,137 raw
rows per bin, and effective counts approximately 200--759, so this gate is
viable without result-driven binning.

## 5. Training-weight semantics

Physical evaluation always uses the original signed or absolute physical
weight according to the established contract. Only XGBoost fitting weights are
modified.

Let `R_b^(t)` be the cumulative mass multiplier for ZZ bin `b` at iteration
`t`, with `R_b^(0)=1`. Before the existing per-fold class balancing:

\[
\tilde w_i^{(t)}=
\begin{cases}
|w_{\mathrm{physical},i}|R_{b(i)}^{(t)}, & y_i=0,\\
|w_{\mathrm{physical},i}|, & y_i=1.
\end{cases}
\]

The established class-balancing step then rescales each class to exactly half
the fitting-row count, preserving mean fitting weight one. This prevents a
changing total ZZ weight from changing the class prior while retaining the
relative mass-bin correction within ZZ.

Evaluation weights, working-point thresholds, AUC, signal efficiency, ZZ
efficiency, correlations, KS distances, plots, and physical yields never use
`R_b^(t)`.

## 6. Iterative update

Iteration zero is the ordinary full-14 OOF training with all multipliers one.
At each iteration, the selected candidate's OOF scores define global
loose/medium/tight thresholds using original absolute physical weights.

For ZZ bin `b` and working point `k`, calculate

\[
\epsilon_{b,k}^{(t)}=
\frac{\sum_{i\in b,\ s_i>c_k}|w_i|}
     {\sum_{i\in b}|w_i|},
\]

where the target efficiencies are `q=(0.50,0.20,0.10)`. With fixed numerical
floor `delta=1e-6`, damping `eta=0.5`, per-round factor bounds `[0.5,2.0]`, and
cumulative bounds `[0.2,5.0]`, define:

\[
u_b^{(t)}=
\exp\left[
\frac{\eta}{3}\sum_k
\log\frac{\epsilon_{b,k}^{(t)}+\delta}{q_k+\delta}
\right],
\]

\[
C_b^{(t)}=\operatorname{clip}(u_b^{(t)},0.5,2.0),
\qquad
R_b^{(t+1)}=
\operatorname{clip}(R_b^{(t)}C_b^{(t)},0.2,5.0).
\]

A bin selected more often than its targets therefore receives more ZZ fitting
weight in the next round. A bin selected less often receives less. Every new
round retrains all six candidates from scratch on the same folds. There are at
most five corrective rounds after iteration zero.

The multiplier is a bin-level development statistic derived from prior-round
OOF predictions, never an event-specific correction derived from in-fold
scores. All adaptation stays inside development; independent test remains
unread until selection freezes.

## 7. OOF selection and stopping

For every iteration, record weighted OOF AUC, score--mass correlation, all
three working points, signal efficiencies, per-bin ZZ efficiencies, and
inclusive-to-selected ZZ KS distances.

An iteration is eligible only if:

\[
\mathrm{weighted\ OOF\ AUC}\ge0.80,
\]

\[
KS_{\mathrm{loose}},KS_{\mathrm{medium}},KS_{\mathrm{tight}}\le0.10,
\]

and the OOF signal efficiency is strictly greater than the achieved OOF ZZ
efficiency at every working point.

The first eligible iteration is frozen immediately. Later iterations are not
run. If iterations zero through five are all ineligible, publish
`no_eligible_iteration` and never locate, validate, fit, or score test rows.

## 8. Independent-test terminal

For the first eligible iteration, freeze its cumulative multipliers, candidate,
tree count, feature tuple, thresholds, and all configuration bytes. Fit once on
all development rows and score independent MC test once.

The terminal is `eligible_iteration_test_reproduced` only if test weighted AUC
is at least 0.80, all three test inclusive-to-selected ZZ KS distances are at
most 0.10, and test signal efficiency is strictly greater than achieved test ZZ
efficiency at every OOF-frozen threshold. Otherwise publish
`test_nonreproduction`. Test evidence cannot change any frozen choice and no
retry is allowed.

Neither terminal authorizes periodA automatically. A separately reviewed
blind sideband protocol is required before real-data application.

## 9. Software boundaries

- `src/mass_bin_reweighting.py`: immutable result types, bin validation,
  per-bin efficiency calculation, multiplier update, iteration loop, OOF
  eligibility, and one-time test reproduction.
- `src/full_training_policy.py`: backward-compatible optional per-row training
  multipliers in class balancing; default behavior remains byte-for-byte
  equivalent numerically.
- `src/full_training_model.py`: backward-compatible optional multiplier input
  for fold fitting and final development fitting; never apply it to evaluation
  weights.
- `src/mass_bin_reweighting_plots.py`: fixed iteration trade-off, per-bin
  efficiency, multiplier history, and optional selected mass-shape plots.
- `src/mass_bin_reweighting_run.py`: source binding, fresh-run resolution,
  exact conditional allowlists, safe artifact publication, failure terminal,
  and manifest-last completion.
- `scripts/run_mass_bin_reweighting.py`: strict CLI orchestration.
- `config/mass_bin_reweighting.yaml`: exact frozen constants and source hashes.

Existing default callers of `full_training_policy` and `full_training_model`
must produce identical weights, predictions, and artifacts when no multiplier
is supplied.

## 10. Run safety and sealed order

The runner reuses the independently reviewed descriptor-owned, no-follow,
no-clobber, failure-terminal, and manifest-last primitives from the 1.0 study.
The output path must be absent and not a symlink. Source bytes and hashes are
bound before claim without parsing the MC CSV; the fresh path is rebound and
atomically claimed; the MC table is parsed once after claim.

The required high-level order is:

```text
output preflight
source byte/hash binding
output rebind
atomic output claim
single MC parse
development-only iteration
[one final development fit and one test score]
write exact allowlist
source/config recheck
publish manifest last
```

The bracketed operation is absent for `no_eligible_iteration` and
`insufficient_bin_statistics`. Any exception installs `failure.json`; a failed
or complete path is never reused.

## 11. Artifacts

Every successful terminal publishes:

```text
config.yaml
artifacts/iteration_results.csv
artifacts/bin_efficiencies.csv
artifacts/weight_multipliers.csv
artifacts/selection.json
plots/iteration_tradeoff.png
plots/zz_efficiency_by_mass.png
artifacts/study_manifest.json
```

An eligible iteration additionally publishes:

```text
artifacts/test_metrics.json
model/xgboost_model.json
predictions/selected_oof_scores.csv.gz
predictions/test_scores.csv.gz
plots/selected_mass_sculpting.png
```

The manifest records exact source and output paths, sizes, SHA-256 values, CSV
row counts, source total/split rows, bin edges, effective counts, all update
constants, every iteration's cumulative multipliers, the terminal, and whether
test was opened. Extra artifacts, symlink targets, non-finite JSON/CSV values,
contradictory terminal/allowlist combinations, and pre-existing entries are
rejected.

## 12. Plots and interpretation

- `iteration_tradeoff.png`: a fixed three-panel figure containing OOF AUC
  versus iteration with the 0.80 line, loose/medium/tight KS versus iteration
  with the 0.10 line, and an 11-bin cumulative-multiplier heatmap.
- `zz_efficiency_by_mass.png`: per-bin OOF ZZ efficiency for all three working
  points, with horizontal 0.50/0.20/0.10 targets. Each displayed uncertainty
  is the fixed effective-binomial estimate
  `sqrt(epsilon * (1 - epsilon) / N_eff)` using the inclusive bin's absolute
  physical-weight effective count.
- `selected_mass_sculpting.png` exists only after OOF eligibility and shows
  inclusive plus three selected ZZ shapes for OOF and test using original
  absolute physical weights and OOF-frozen thresholds.

The plots must not claim that a visually flatter histogram supersedes the
numerical gates. A Higgs 125 GeV MC peak remains a signal-shape diagnostic, not
a real-data observation.

## 13. Verification

Strict TDD must prove:

- an over-selected mass bin receives a larger next-round ZZ multiplier;
- an under-selected bin receives a smaller multiplier;
- damping, per-round bounds, cumulative bounds, endpoint assignment,
  non-finite inputs, missing bins, and effective-count gates are exact;
- class totals and mean-one fitting weights remain exact while physical
  evaluation weights remain unchanged;
- default full-training behavior is unchanged without multipliers;
- iteration selection cannot read or be changed by poisoned test analysis
  columns;
- no-eligible and insufficient-statistics terminals perform zero test access,
  zero final fitting, and publish no test/model names;
- first eligibility stops later rounds;
- selected test is opened once and cannot change iteration/candidate/thresholds;
- occupied files/direct and dangling symlinks refuse before MC parsing;
- exact conditional allowlists, finite values, row counts, hash rechecks,
  failure terminal, manifest-last order, and same-path refusal hold;
- a tiny real-XGBoost synthetic integration exercises at least two iterations.

Focused, related, full-suite, compile, artifact, protected-run hash, and
independent physics/code review gates are required before the one real study.
The real command is invoked once on a fresh path; it is never interrupted or
retried.

## 14. Acceptance and rollback

The version 1.1 reweighting study is complete when it publishes one of the
three honest terminals:

- `no_eligible_iteration`;
- `eligible_iteration_test_reproduced`;
- `test_nonreproduction`.

No terminal overwrites or promotes over the 1.0 reference model. If the method
does not reproduce, the reference model remains available for MC diagnostics
but periodA stays sealed. The next method would be a separately designed
uBoost study or a template/sideband statistical model, not a post-hoc change to
this study.
