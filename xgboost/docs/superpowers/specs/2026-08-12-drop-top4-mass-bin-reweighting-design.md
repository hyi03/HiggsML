# Drop-top4 mass-bin iterative reweighting design

Date: 2026-08-12

## Purpose

Run one new MC-only comparison that combines the two already completed mitigation
ideas:

1. remove the four strongest mass-proxy inputs; and
2. apply the frozen mass-bin iterative ZZ reweighting algorithm.

The study asks whether the combination can satisfy the predeclared discrimination
and mass-sculpting gates without changing them after seeing the result. It is a
method comparison, not a Higgs discovery or measurement.

## Frozen references

The following completed runs are immutable inputs or report-only references. They
must not be modified, reused as output directories, or retrained:

| Run | Role | Manifest SHA-256 |
|---|---|---|
| `runs/full-baseline-363490-2026-08-11-r2` | frozen selected-MC input | `10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8` |
| `runs/full-training-363490-2026-08-11-r2` | Full14 reference | `da015d0a00bb002e69dc98eb9631c1b561af65f8da44b78a641d4e013558bf65` |
| `runs/mass-ablation-363490-2026-08-11` | feature-ablation reference | `5120e6080e82b14f66917ba731c98715fa5d6190c25c396d8c675200e9ca52df` |
| `runs/mass-reweighting-363490-2026-08-11` | Full14 reweighting reference | `145e38478dfd12310a82f4ed544c6cf0b09204cbc1c7d08e6e485941c00f9e38` |

`data/raw/zz_363490.root` remains a protected provenance input with SHA-256
`76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07`.
The new study does not preprocess ROOT again.

## Fixed feature profile

The new model uses exactly these ten ordered features:

```text
lep1_pt
lep2_pt
lep1_eta
lep2_eta
lep3_eta
lep4_eta
pt4l
deltaR_Z1
deltaR_Z2
deltaPhi_ZZ
```

It removes `lep3_pt`, `lep4_pt`, `mZ1`, and `mZ2`. It must never use `m4l`,
event identity, sample identity, labels, split metadata, or weights as model
features. The profile is named `drop_top4_mass_proxies` and must match the
existing ablation profile byte-for-byte and in order.

## Frozen training and reweighting policy

Everything except the feature profile remains identical to the approved Full14
reweighting study:

- the same DSID 363490 selected MC and train/validation/test split;
- development-only five-fold OOF model selection;
- the same six XGBoost candidates and one-standard-error selection rule;
- the same final-tree-count rule and fixed random seeds;
- normalized absolute physical weights for XGBoost training;
- signed physical weights for physical yields;
- fixed mass bins `[105, 110, ..., 160]` GeV;
- minimum effective ZZ count `100` in every fixed development bin;
- damping `0.5`, round factor bounds `[0.5, 2.0]`, cumulative bounds
  `[0.2, 5.0]`, and epsilon floor `1e-6`;
- iteration 0 plus at most five corrections;
- working points `loose`, `medium`, and `tight` derived only from OOF ZZ scores.

The eligibility gates are immutable:

1. weighted OOF AUC must be at least `0.80`;
2. OOF ZZ mass KS must be at most `0.10` at all three working points; and
3. signal efficiency must be strictly greater than achieved ZZ efficiency at all
   three working points.

The known unweighted-ablation starting point has OOF AUC
`0.7996529199780816`, just below the AUC floor. This does not authorize lowering
the floor. Iterations 1 through 5 still run so the predeclared trajectory can be
measured.

## Architecture

Use the existing mass-bin reweighting workflow and publication contract rather
than duplicating them. Generalize only the model-feature boundary so it accepts
one strictly validated, immutable ordered subset of the frozen Full14 features.
Default Full14 behavior must remain unchanged.

Add a dedicated configuration file:

```text
config/mass_bin_reweighting_drop_top4.yaml
```

It must bind the exact ten-feature profile, all frozen inputs and hashes, the
unchanged policy, and the approved output allowlists. The proposed fresh output
directory is:

```text
runs/mass-reweighting-drop-top4-363490-2026-08-12
```

The implementation must not introduce a general arbitrary feature-search API.
Only Full14 and the exact `drop_top4_mass_proxies` profile are accepted in this
stage.

## Data flow and test sealing

The command must execute in this order:

1. reject an existing, dangling-symlink, non-directory, or protected output path;
2. bind and verify frozen source paths, file types, sizes, hashes, and manifests
   without parsing the MC table;
3. atomically claim the fresh output directory;
4. revalidate the bound sources and parse the MC table exactly once;
5. expose only development rows to iteration 0--5 training and OOF evaluation;
6. choose the first iteration satisfying every fixed gate;
7. if no iteration is eligible, publish a truthful `no_eligible_iteration`
   terminal without locating, validating, fitting on, or scoring test rows;
8. if an iteration is eligible, open the MC test split exactly once for final
   evaluation of that frozen iteration;
9. publish the complete manifest last using descriptor-bound, no-clobber output
   semantics.

`data16_periodA`, all `data_events` artifacts, and any real-data scoring path are
out of scope and must remain unopened.

## Outputs

Reuse the approved conditional output contract.

Every completed study records:

- configuration snapshot;
- `iteration_results.csv`;
- `bin_efficiencies.csv`;
- `weight_multipliers.csv`;
- `selection.json`;
- iteration trade-off plot;
- ZZ efficiency-by-mass plot; and
- manifest published last.

Only an eligible study may additionally publish the selected model, OOF and test
scores, test metrics, and selected mass-sculpting plot. A no-eligible terminal
must not contain any of those test/model artifacts.

The manifest must directly record the exact ten-feature profile, source receipts,
source and output row counts, all iteration multipliers, fixed-bin effective
counts, gate decisions, selection terminal, and whether test was opened.

## Four-way comparison

The final report compares, without retraining the first three rows:

| Method | OOF AUC | Maximum OOF ZZ KS | Status |
|---|---:|---:|---|
| Full14 | `0.8852959102354316` | `0.4579540115915921` | frozen reference |
| Drop top four, no reweighting | `0.7996529199780816` | `0.34469234042569663` | frozen reference |
| Full14 plus reweighting, iteration 5 | `0.8523982143190011` | `0.24583464407366806` | frozen reference; no eligible iteration |
| Drop top four plus reweighting | measured by this study | measured by this study | new result |

Interpretation must consider the full trajectory: AUC, all three KS values,
signal and achieved-ZZ efficiencies, and per-bin effective statistics. A lower KS
alone is not success if discrimination falls below `0.80`.

If no iteration passes, that is a valid result: removing four mass proxies plus
the current reweighting algorithm is insufficient under the fixed gates. The
result must be retained as a comparison, without threshold relaxation or
periodA inspection.

## Error handling and immutability

- Any source hash, row-count, feature-order, policy, output allowlist, or numerical
  inconsistency fails closed.
- Non-finite model inputs, weights, scores, metrics, multipliers, or JSON/CSV
  values fail closed.
- Failure publishes only the approved terminal failure record and never a complete
  manifest.
- Existing runs, protected raw data, and output artifacts must be identical before
  and after both the real command and the same-path refusal check.
- The real study command is invoked once. A scientifically disappointing result
  is not a reason to retry or alter the policy.

## Verification strategy

Implementation uses focused test-driven development. Narrow tests must prove:

- exact ten-feature ordering and rejection of missing, extra, reordered, or
  runtime-rebound profiles;
- exclusion of `m4l` and the four removed features from every fit and prediction;
- unchanged Full14 default behavior;
- exact training/reweighting policy, formulas, gates, iteration cap, and first
  eligible selection;
- zero test access for all pre-selection and no-eligible branches;
- exactly one final test evaluation for an eligible branch;
- source binding before parse, parse after atomic claim, and immediate source
  freshness checks;
- exact conditional allowlists, descriptor-bound receipts, manifest-last
  publication, symlink/race refusal, and failure-only terminals;
- consistency among CSV evidence, manifest audit fields, hashes, row counts, and
  plots.

Use focused tests during development. Run the complete synthetic suite once at
the final acceptance boundary, followed by compile verification. Before the real
run, recheck every protected hash and confirm the target is absent and not a
symlink. After the one real run, audit all artifacts read-only, inspect only the
new approved plots, execute one same-path refusal, and document the four-way
comparison.

## Expected duration

- implementation and focused tests: 1--2 hours;
- one real study: approximately 15--25 minutes;
- read-only audit, plot inspection, and report updates: 30--60 minutes.

The estimate is operational, not a promise of scientific eligibility.
