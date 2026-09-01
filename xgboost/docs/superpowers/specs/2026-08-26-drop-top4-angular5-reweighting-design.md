# DropTop4 + Angular5 Iterative Mass-Reweighting Design

Date: 2026-08-26

## 1. Purpose

Run one new, immutable, MC-only study that asks whether five standard
four-lepton decay angles add discrimination to the strongest currently known
mass-flat reference: DropTop4 plus iterative ZZ mass-bin reweighting.

The study succeeds only if one development-OOF iteration simultaneously meets
all previously frozen gates:

1. weighted OOF AUC is at least `0.80`;
2. continuum-ZZ OOF mass KS is at most `0.10` at the loose, medium, and tight
   working points; and
3. signal efficiency is strictly above achieved ZZ efficiency at all three
   working points.

This is a technical/educational method study, not an ATLAS result, Higgs
discovery claim, or physics measurement.

## 2. Scope and explicit non-goals

The only new model inputs are the five Angular5 observables defined in this
document. The study does not add Z-system `delta_eta`, `delta_r`, Z transverse
momenta, or transverse-momentum-balance variables.

The following are explicitly out of scope:

- adversarial training or an adversarial loss;
- KNN flatness loss;
- arbitrary feature search or post-result feature selection;
- changes to the event selection, Z pairing, MC normalization, split policy,
  model candidates, mass bins, reweighting formula, iteration cap, or gates;
- using `m4l`, event identity, provenance, split, label, or weight columns as
  model features;
- reading, hashing, processing, scoring, plotting, or inventorying real data;
- opening held-out MC test evidence before an eligible OOF iteration exists;
- changing the Angular5 formulas after observing AUC or KS results.

`Angular5 + ZTopology` is recorded only as a possible future, separately
approved study. It is not a fallback branch of this run and is not implemented
or executed here.

## 3. Frozen references and protected inputs

Existing runs and their artifacts remain immutable. The new study binds at
least these exact MC-only receipts before parsing any input table or ROOT file:

| Source | Role | SHA-256 |
|---|---|---|
| `config/dsid363490.yaml` | frozen preprocessing/selection policy | `0282cfa965228e036f4ada3c010bd7d40b1b14e56c2aa33551784683237cd320` |
| `runs/full-baseline-363490-2026-08-11-r2/artifacts/run_manifest.json` | frozen selected-MC manifest | `10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8` |
| `runs/full-baseline-363490-2026-08-11-r2/processed/mc_events.csv.gz` | authoritative selected-MC rows | `1c5d6a3f9a750a5eb9965241dd8947d70e790cf949a36f8fa6ec1bfd058f378e` |
| `data/raw/higgs.root` | Higgs MC four-lepton input | `5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0` |
| `data/raw/zz_363490.root` | continuum-ZZ MC four-lepton input | `76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07` |
| `config/mass_bin_reweighting_drop_top4.yaml` | frozen DropTop4 reweighting policy reference | `950c4e700ba2a82c7638e0fdebbe60c60c80fc984e815a0e2bd1f664f6e00791` |

The implementation adds two dedicated MC-only configurations:

```text
config/angular5_mc_dsid363490.yaml
config/mass_bin_reweighting_drop_top4_angular5.yaml
```

The first configuration contains only the Higgs and ZZ MC samples, the exact
copied selection/input-profile policy, the frozen reference-config hash, and the
approved enrichment artifacts. It has no data sample, period, or real-data path.
The second binds the exact enriched-MC receipt, 15-feature profile, unchanged
training/reweighting policy, and conditional training artifacts. Neither loader
accepts a data source or data-scoring option.

The completed DropTop4 reweighting result is a report-only reference. Its
terminal status was `no_eligible_iteration`; iteration 5 had weighted OOF AUC
`0.7588712973047708` and loose/medium/tight KS values
`0.07416808989370494`, `0.09720271279351`, and
`0.09406967019374574`. It must not be modified or reused as an output path.

The Higgs and ZZ ROOT files use their already frozen input profiles:
`release22` for Higgs and `open_data_2020` for ZZ. Physical branch-name and
momentum-unit differences continue to be resolved only through those profiles.

## 4. Canonical object and pairing conventions

The existing reconstruction remains authoritative:

1. normalize each selected lepton four-vector to GeV;
2. stable-sort leptons by descending transverse momentum;
3. form two non-overlapping same-flavour, opposite-sign pairs;
4. choose as `Z1` the pair whose invariant mass is closest to the nominal Z
   mass;
5. choose the remaining pair as `Z2`;
6. retain the existing deterministic index tie-break.

Each Z must contain exactly one negatively charged and one positively charged
lepton. Angular orientation always uses the negatively charged lepton. Input
ordering therefore cannot flip an angle sign.

## 5. Angular5 definitions

Let `X = Z1 + Z2` be the four-lepton system. Let `l1-` and `l1+` be the
negative and positive leptons from `Z1`; define `l2-` and `l2+` analogously.
All unit vectors and cross products below are three-vectors evaluated after the
specified Lorentz boost.

The implementation produces exactly these five columns in this order:

```text
cos_theta_star
cos_theta_1
cos_theta_2
phi_decay_planes
phi_production_plane
```

### 5.1 `cos_theta_star`

Boost `Z1` and a massless reference four-vector along the laboratory `+z` beam
direction into the `X` rest frame. `cos_theta_star` is the dot product of their
unit spatial directions:

```text
cos_theta_star = unit(p_Z1^X) dot unit(p_beam+^X)
```

The signed value is retained. Its allowed range is `[-1, 1]`.

### 5.2 `cos_theta_1`

Boost `l1-` and `Z2` into the `Z1` rest frame. The `Z1` helicity axis is the
direction opposite to `Z2`:

```text
cos_theta_1 = unit(p_l1-^Z1) dot (-unit(p_Z2^Z1))
```

Its allowed range is `[-1, 1]`.

### 5.3 `cos_theta_2`

Boost `l2-` and `Z1` into the `Z2` rest frame. The `Z2` helicity axis is the
direction opposite to `Z1`:

```text
cos_theta_2 = unit(p_l2-^Z2) dot (-unit(p_Z1^Z2))
```

Its allowed range is `[-1, 1]`.

### 5.4 `phi_decay_planes`

In the `X` rest frame, define oriented decay-plane normals using fixed charge
ordering:

```text
n1 = unit(p_l1-^X cross p_l1+^X)
n2 = unit(p_l2-^X cross p_l2+^X)
z1 = unit(p_Z1^X)
```

Then define the signed angle with `atan2`:

```text
phi_decay_planes = atan2(z1 dot (n1 cross n2), n1 dot n2)
```

The result is normalized to `[-pi, pi)`.

### 5.5 `phi_production_plane`

In the `X` rest frame, let `b` be the boosted laboratory `+z` beam direction
and define the production-plane normal:

```text
n_production = unit(b cross z1)
```

The signed angle from the production plane to the `Z1` decay plane is:

```text
phi_production_plane = atan2(
    z1 dot (n_production cross n1),
    n_production dot n1,
)
```

The result is normalized to `[-pi, pi)`.

### 5.6 Numerical policy

- Lorentz boosts require finite four-vectors and `|beta| < 1`.
- Dot products used as cosines may be clipped to `[-1, 1]` only within a small
  fixed floating-point tolerance.
- `atan2` fixes the signed-angle quadrants; a returned `+pi` is represented as
  `-pi`.
- Zero-norm axes, degenerate planes, non-finite inputs, invalid charges, or
  non-finite outputs fail closed.
- A selected event with undefined angles is never silently dropped, imputed, or
  assigned a convenient constant.
- `m4l` is not passed as a model feature. Use of the `X` rest frame does not
  exempt the new model from the same OOF mass-sculpting gates.

## 6. Exact model feature profile

The new profile is named `drop_top4_plus_angular5` and contains exactly these
15 ordered inputs:

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
cos_theta_star
cos_theta_1
cos_theta_2
phi_decay_planes
phi_production_plane
```

The four removed mass-proxy inputs remain excluded:

```text
lep3_pt
lep4_pt
mZ1
mZ2
```

The feature-policy API accepts only previously approved frozen profiles plus
this exact new tuple. It must not become an arbitrary runtime feature-search
interface.

## 7. MC-only angular enrichment run

The current frozen MC CSV lacks the lepton phi, energy, charge, and flavour
arrays required to calculate Angular5. A new preprocessing run therefore reads
only the two protected MC ROOT files. It does not read or resolve any real-data
path.

The frozen fresh output path is exactly:

```text
runs/angular5-mc-363490-2026-08-26
```

The command performs these stages in order:

1. reject an existing, symlinked, non-directory, or protected output path;
2. bind the exact config, frozen MC table, manifest, and two raw MC files by
   regular-file identity, size, and SHA-256;
3. atomically claim the new output directory;
4. stream Higgs and ZZ MC with their frozen profiles;
5. apply the unchanged frozen selection and pairing rules;
6. reconstruct the existing features and calculate Angular5;
7. join the five angles to authoritative frozen MC rows using the exact key
   `(runNumber, eventNumber, channelNumber)`;
8. verify one-to-one key coverage and semantic equality of every pre-existing
   field;
9. recheck all sources and publish the manifest last.

The frozen MC table supplies the authoritative existing columns, labels,
weights, and split values. The enrichment process may append Angular5 but may
not recalculate or replace those authoritative values in the published table.

Identity validation requires:

- identical row count and row order;
- unique, complete, one-to-one event-key matching;
- exact equality for event keys, labels, and split strings;
- exact equality of parsed pre-existing numeric values, including old features
  and weights;
- finite Angular5 values within their declared ranges; and
- no missing, extra, duplicated, silently rejected, or imputed event.

Any mismatch installs only the approved failure terminal. It does not produce a
usable enriched MC table.

Approved successful enrichment artifacts are limited to:

```text
config.yaml
processed/mc_events_angular5.csv.gz
artifacts/identity_validation.json
artifacts/angular5_summary.json
artifacts/run_manifest.json
```

The summary contains only MC counts, numerical range checks, and source/output
receipts. It must not contain held-out performance metrics or real-data fields.

## 8. Training and reweighting study

The frozen fresh study path is exactly:

```text
runs/mass-reweighting-drop-top4-angular5-363490-2026-08-26
```

The study reuses the existing mass-bin reweighting implementation and changes
only its strictly approved input table/profile binding. It starts from scratch;
it does not append trees or features to the old iteration-5 model and does not
transplant the old iteration-5 multipliers as the new terminal weights.

The following remain frozen exactly as in the approved DropTop4 reweighting
study:

- the same semantic development/test split;
- development-only five-fold OOF model selection;
- the same six XGBoost candidates and one-standard-error rule;
- the same final-tree-count rule and fixed random seeds;
- normalized absolute physical weights for fitting;
- signed physical weights only for physical-yield reporting;
- fixed mass-bin edges `[105, 110, ..., 160]` GeV;
- minimum effective ZZ count `100` in every development bin;
- damping `0.5`;
- round multiplier bounds `[0.5, 2.0]`;
- cumulative multiplier bounds `[0.2, 5.0]`;
- epsilon floor `1e-6`;
- iteration 0 plus at most five corrections; and
- loose `0.50`, medium `0.20`, and tight `0.10` target ZZ efficiencies.

The algorithm evaluates iterations `0..5` in order and stops at the first
iteration satisfying every frozen eligibility gate. It does not choose a later
iteration because it has a more attractive observed trade-off.

## 9. Test sealing and data boundaries

Feature construction is deterministic and label-independent, so Angular5 may be
materialized for all MC rows before model selection. This does not authorize
using held-out test evidence.

Before an eligible OOF iteration exists, the training workflow must not:

- select or summarize held-out test Angular5 distributions;
- fit on held-out rows;
- score held-out rows;
- calculate held-out AUC, KS, thresholds, or efficiencies; or
- use held-out evidence to change angles, features, weights, candidates,
  iterations, or gates.

If no iteration is eligible, the terminal status is
`no_eligible_iteration`, `selected_iteration` is null, and `test_opened` is
false. If an iteration is eligible, only that first eligible iteration opens the
MC test once for a frozen reproduction check. Test results never feed back into
selection.

Real data remains outside both commands and all manifests, CLI arguments,
source inventories, artifacts, plots, and reports.

## 10. Publication and provenance

Both runs use no-clobber directories, descriptor-bound writes, source freshness
checks, exact conditional artifact allowlists, terminal failure records, and
manifest-last publication.

Every complete training study records:

- exact feature order and Angular5 convention version;
- the enriched-MC manifest and table hashes;
- the frozen training/reweighting policy;
- OOF model-selection evidence;
- per-iteration AUC and all three KS values;
- thresholds, achieved ZZ efficiencies, and signal efficiencies;
- mass-bin efficiencies and cumulative multipliers;
- software and Git provenance;
- whether test was opened; and
- hashes, sizes, and row counts for every output.

The existing conditional training artifact contract is preserved. Model and
test-only artifacts exist only after an eligible selection.

## 11. Failure behavior

Failures after output claim publish only an approved failure record and terminal
marker. A complete manifest is never present beside a failure terminal.

The workflow fails closed on:

- source hash, size, identity, or freshness mismatch;
- any attempt to resolve a real-data source;
- changed selection, pairing, split, normalization, feature order, model,
  reweighting, gate, or artifact policy;
- event-key mismatch or old-column disagreement during enrichment;
- invalid boost, degenerate angular geometry, or non-finite/out-of-range angle;
- insufficient mass-bin statistics;
- duplicate/missing OOF prediction or fold contamination;
- non-finite weights, scores, metrics, or multipliers;
- test access before OOF eligibility; or
- output collision, symlink, race, or post-write mutation.

Neither a scientific no-eligible result nor a software failure authorizes reuse
of the same production path.

## 12. Verification strategy

Implementation follows test-driven development. Focused tests must cover:

### Angular mathematics

- exact Lorentz-boost behavior and rest-frame reconstruction;
- analytic or hand-constructed angle cases;
- bounds and `+pi` to `-pi` normalization;
- invariance under common longitudinal boosts;
- invariance under common global azimuthal rotations;
- deterministic charge ordering and input-permutation stability;
- existing Z1/Z2 pairing and tie-break behavior;
- rejection of invalid charges, zero-norm planes, invalid boosts, and non-finite
  inputs/outputs.

### MC enrichment

- MC-only CLI and absence of any data argument or source key;
- exact source receipts and fresh-path refusal;
- unchanged selection/pairing policy;
- complete one-to-one event join;
- exact preservation of all old columns;
- exact five-column append order and ranges;
- source mutation/race refusal, failure-only terminal, and manifest-last
  publication.

### Training

- exact 15-feature profile and rejection of missing, extra, reordered, or
  rebound profiles;
- continued exclusion of `m4l`, removed mass proxies, identifiers, labels,
  provenance, split, and weights;
- unchanged historical Full14 and DropTop4 behavior;
- exact five-fold OOF and iteration `0..5` trajectory;
- first-eligible selection and unchanged AUC/KS/efficiency gates;
- zero test access for no-selection and exactly one test evaluation after an
  eligible selection;
- exact conditional outputs and internal agreement among CSV, JSON, plots, and
  manifest evidence.

Run focused tests after each behavior change, then the full suite before either
production command. Before a production run, verify protected MC hashes and
confirm the output path is absent. Execute each production command once only.
Afterward, audit only the approved new MC artifacts and plots, verify manifest
ordering and hashes, and write the exact terminal result without relaxing any
decision.

## 13. Documentation

This design is the authoritative Angular5 standard for the study. After
implementation and verified execution, update current navigation and status
documents, including the project overview, data description, roadmap, and
README as relevant.

Historical design and execution reports remain unchanged. They may receive a
forward link to this study only if doing so does not alter their recorded
decision or evidence.

The final execution report must include:

- exact Angular5 definitions and feature order;
- source and output hashes;
- enrichment identity evidence;
- focused and full test results;
- every iteration's full-precision AUC and three KS values;
- terminal selection and conditional test evidence;
- comparison with frozen Full14, DropTop4, DropTop4 reweighting, and KNN
  flatness references; and
- limitations and the still-unexecuted `Angular5 + ZTopology` backup idea.
