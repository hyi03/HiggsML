# DropTop4 + Angular5 Source-Identity R2 Design

Date: 2026-08-26

## 1. Purpose and authority

This document defines the R2 recovery of the approved DropTop4 + Angular5
study after the original enrichment run failed closed on a false input
assumption: `(runNumber, eventNumber, channelNumber)` is not unique in the
frozen Higgs MC.

This R2 design supersedes only the event-identity, enrichment-source, and fresh
output-path parts of
`docs/superpowers/specs/2026-08-26-drop-top4-angular5-reweighting-design.md`.
All Angular5 formulae, feature order, selection, pairing, normalization,
development/test split values, model candidates, five-fold OOF policy,
mass-bin reweighting policy, eligibility gates, test sealing, and real-data
boundaries remain unchanged.

The failed run remains immutable:

```text
runs/angular5-mc-363490-2026-08-26
```

Its terminal evidence records `ValueError: authoritative table contains
duplicate event keys`. It must not be removed, repaired, completed, or reused.

This is still a technical/educational MC-only study, not an ATLAS result,
Higgs discovery claim, or physics measurement.

## 2. Confirmed root cause

The frozen authoritative MC table has 199,104 rows. Four Higgs rows form two
non-identical duplicate groups under the original key:

| runNumber | eventNumber | channelNumber | raw ROOT entries |
|---:|---:|---:|---|
| 284500 | 102001 | 345060 | 173348, 345900 |
| 284500 | 1136001 | 345060 | 340911, 342358 |

Each pair has different lepton and reconstructed kinematic values. Both rows
are real, distinct ROOT entries. Dropping one, merging them, inventing a tie
break from model features, or treating the original key as unique would alter
the frozen selected sample.

The defect is therefore in the original identity assumption, not in CSV
parsing, Angular5 mathematics, selection, or the ROOT input.

## 3. Canonical source identity

Every raw MC event receives two provenance fields before selection:

```text
source_sample
source_entry
```

Their definitions are exact:

- `source_sample` is the fixed string `higgs_345060` or `zz_363490` selected
  from the sealed sample configuration, never inferred from a filename;
- `source_entry` is the zero-based TTree entry index before any trigger,
  quality, kinematic, pairing, or mass selection;
- `(source_sample, source_entry)` is the sole canonical identity used for R2
  enrichment joins;
- the identity must be independent of ROOT chunk size and must agree for
  direct, chunked, and repeated full reads;
- both fields are provenance only and are forbidden model features.

`runNumber`, `eventNumber`, and `channelNumber` remain published physics
provenance. Their duplicates are reported, not rejected. Existing `split`
values remain authoritative and are not recalculated; the two pairs continue
to share their already-frozen train split.

## 4. Fresh R2 paths and configurations

R2 adds three new no-clobber production paths:

```text
runs/angular5-identity-mc-363490-2026-08-26-r2
runs/angular5-mc-363490-2026-08-26-r2
runs/mass-reweighting-drop-top4-angular5-363490-2026-08-26-r2
```

It adds three dedicated sealed configurations:

```text
config/angular5_identity_mc_dsid363490_r2.yaml
config/angular5_mc_dsid363490_r2.yaml
config/mass_bin_reweighting_drop_top4_angular5_r2.yaml
```

The original design/configuration and failed output path remain historical
evidence. R2 loaders accept only the new exact schemas and paths; they do not
silently upgrade or redirect the original command.

## 5. Protected inputs

The identity run binds the same protected inputs before parsing:

| Source | Role | SHA-256 |
|---|---|---|
| `config/dsid363490.yaml` | frozen selection/input policy | `0282cfa965228e036f4ada3c010bd7d40b1b14e56c2aa33551784683237cd320` |
| `runs/full-baseline-363490-2026-08-11-r2/artifacts/run_manifest.json` | frozen selected-MC manifest | `10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8` |
| `runs/full-baseline-363490-2026-08-11-r2/processed/mc_events.csv.gz` | authoritative old columns and rows | `1c5d6a3f9a750a5eb9965241dd8947d70e790cf949a36f8fa6ec1bfd058f378e` |
| `data/raw/higgs.root` | Higgs MC | `5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0` |
| `data/raw/zz_363490.root` | continuum-ZZ MC | `76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07` |

The identity configuration itself is also bound by regular-file identity,
size, and SHA-256. Source traversal, descriptor-bound reading, freshness
checks, symlink refusal, mutation refusal, and failure-terminal behavior are
at least as strict as the reviewed original enrichment implementation.

Neither R2 source inventory contains a real-data path, data period, data
manifest, or data artifact.

## 6. Source-identity baseline run

The command is:

```bash
.venv/bin/python -m scripts.build_angular5_identity_mc \
  --config config/angular5_identity_mc_dsid363490_r2.yaml \
  --run-dir runs/angular5-identity-mc-363490-2026-08-26-r2
```

It performs these stages in order:

1. bind all protected sources without parsing CSV or ROOT;
2. atomically claim the exact fresh output path;
3. stream each MC ROOT file in raw entry order and attach the zero-based
   `source_entry` before selection;
4. apply the unchanged frozen input profile, selection, pairing,
   normalization, and reconstruction behavior;
5. partition the authoritative MC table by its frozen channel/sample and
   retain its original order;
6. require equal selected row counts for each sample;
7. compare every reconstructed pre-existing field against the corresponding
   authoritative row after the same parse boundary;
8. preserve the authoritative CSV lexical tokens for all old columns and
   append only `source_sample` and `source_entry`;
9. parse and validate the exact final gzip bytes;
10. revalidate all sources and publish the complete manifest last.

Row-order alignment is permitted only in this one identity-bootstrap run and
only because every old field is checked for the corresponding row. It is not
an identity convention exposed to later consumers. A row reorder, semantic
mismatch, missing/extra selected event, or source mutation fails closed.

The identity run must report the two known duplicate legacy-key groups and
prove that all four rows have distinct canonical source identities.

Successful artifacts are exactly:

```text
config.yaml
processed/mc_events_source_identity.csv.gz
artifacts/identity_validation.json
artifacts/run_manifest.json
```

## 7. R2 Angular5 enrichment run

The command is:

```bash
.venv/bin/python -m scripts.enrich_angular5_mc_r2 \
  --config config/angular5_mc_dsid363490_r2.yaml \
  --run-dir runs/angular5-mc-363490-2026-08-26-r2
```

The R2 enrichment binds the complete identity-run manifest and identity table
by exact hash, size, schema, output contract, and row count. It re-reads only
the two protected MC ROOT files, attaches the same canonical identity before
selection, and calculates the already-approved Angular5 observables.

It joins the reconstructed angles to the identity table using exactly
`(source_sample, source_entry)`. The join must be unique, complete, and
one-to-one. Every old column and both identity columns must remain unchanged;
the publisher preserves their lexical CSV tokens and appends only the five
Angular5 tokens.

Successful artifacts remain exactly:

```text
config.yaml
processed/mc_events_angular5.csv.gz
artifacts/identity_validation.json
artifacts/angular5_summary.json
artifacts/run_manifest.json
```

The summary additionally records the two known duplicated legacy-key groups,
but contains no held-out performance metrics or real-data field.

## 8. Training profile and sealing

The ordered model profile remains exactly the original approved 15 features:

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

`source_sample` and `source_entry` join `m4l`, identifiers, labels,
provenance, split, and weights on the forbidden-feature list.

The R2 training config binds the exact R2 enrichment manifest/table and the
same frozen DropTop4 reference receipts. The existing iterative mass-bin
reweighting algorithm remains unchanged: iterations `0..5`, first eligible
selection, AUC at least `0.80`, all three ZZ mass KS values at most `0.10`,
and signal efficiency strictly above achieved ZZ efficiency at every working
point.

Held-out MC test remains sealed until the first eligible development-OOF
iteration. Real data remains outside every configuration, command, inventory,
artifact, plot, and report.

## 9. Failure and publication behavior

All three R2 runs use exact fresh paths, descriptor-bound no-clobber writes,
source freshness checks, output identity checks, conditional allowlists,
failure-only terminals, and manifest-last publication.

Any claimed-run failure, including `KeyboardInterrupt` or `SystemExit`,
records the approved terminal and re-raises. A failed path is never repaired
or reused. No complete manifest may coexist with a failure terminal.

The identity baseline and enrichment fail closed on:

- non-unique canonical source identity;
- source-entry drift across chunk sizes or repeated reads;
- mismatch between authoritative and reconstructed row count/order/semantics;
- changed old lexical or parsed values;
- duplicate, missing, or extra canonical join identities;
- invalid Angular5 geometry or values;
- source/output mutation, symlink, collision, or race; or
- any attempt to introduce or resolve real data.

## 10. Verification strategy

Implementation remains test-driven. Focused tests must include:

### Source identity

- zero-based raw entry indices on both input profiles;
- independence from chunk size and deterministic repeated reads;
- selection preserves each event's pre-selection source entry;
- duplicate legacy event keys map to distinct source identities;
- source identity is never recalculated from filenames or model fields;
- source identity is forbidden from model features.

### Identity baseline

- exact old-column row order, lexical tokens, parsed values, labels, weights,
  and split preservation;
- the real frozen 199,104-row table yields exactly two duplicate legacy-key
  groups and four rows, all uniquely identified;
- row reordering or any old-field mismatch fails closed;
- exact four-artifact success contract and manifest-last publication;
- source swap/mutation and control-exception failure terminals.

### R2 enrichment

- exact source-identity join with both known duplicate groups retained;
- exact five-angle append order and declared ranges;
- missing/extra/duplicate identities and undefined geometry fail closed;
- exact five-artifact success contract and manifest-last publication;
- zero real-data argument, source, inventory, artifact, or text field.

### Training

- exact 15-feature model matrix and explicit source-identity exclusion;
- unchanged legacy Full14 and DropTop4 behavior;
- unchanged iteration trajectory and eligibility/test-opening logic;
- no-selection opens test zero times; first selection opens test exactly once;
- internal agreement among CSV, JSON, plots, and manifest evidence.

Run focused tests after each behavior change and the full suite before each
production command. Before every production execution, verify protected hashes
and confirm its exact path is absent. Execute each production command once.

## 11. Documentation and terminal report

After execution, update current README, project overview, data description,
roadmap, and documentation navigation. Preserve the original design and failed
run as historical evidence and link them forward to this R2 recovery.

The final report must record:

- the duplicate-key root cause and raw ROOT entry indices;
- all source-identity definitions and receipts;
- old-column and identity-bootstrap evidence;
- both R2 preprocessing manifests and table hashes;
- focused/full test results;
- every full-precision OOF iteration metric;
- terminal selection and conditional test evidence;
- comparison with frozen Full14, DropTop4, reweighting, and KNN references;
- confirmation that real data remained unopened; and
- limitations of source-entry identity and the still-unexecuted
  `Angular5 + ZTopology` idea.
