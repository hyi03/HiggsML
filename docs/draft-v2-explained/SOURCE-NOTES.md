# Basic report explanation: sources and limits — 8 November 2026

## Current source

Both language editions follow `paper/draft-v2/project-report-cn.tex`, especially
its fifteen-row basic metric table, twelve-row paired-contrast table, worked
yield/error example and seven-chapter reading order. The main figures come from
`paper/draft-v2/figures/basic-20261108/`. The evidence index is
`paper/draft-v2/BASIC-20261108-EVIDENCE.md`.

| Binding | Current identity |
|---|---|
| Report | `a7e610a163e5d155705014201b7ee330323e3bf69309e0e89b2496edba5d4317` |
| Evaluation | `2e7995da1e9e27f239551acc05cd9b94f97e4f56297bf3cabdbdf96b9044efaf` |
| Freeze | `c3b15bf87e37b132a542cb3a4dbc7d3d936680ed2691f6b51391a90b7851e12b` |
| Prepared | `566a4493bfaf9f34b48c7e1671cfc9dacc5dcd6bf4915efd035815ceec76a40c` |

The browser's `manuscript-data.js` records these identities and source-file SHA-256
hashes. Default checks compare displayed cells to the report and verify all three
PDF hashes against the current evidence record. This verifies transcription and
publication assets, not original run integrity. The evidence index describes
its own earlier checks; this synchronization does not claim to repeat them.

## Numeric representation and interpretation

Yields retain four decimals, retention percentages and percentage-point contrasts
two, and Q/Q contrasts three. The site displays the recorded paired differences,
medians and ranges directly. The alternative difference-of-medians widget uses
rounded displayed metric values and is labelled accordingly; it does not recover
unrounded results. Regional fractions retain one percentage decimal.

Error cells are fixed-model/cut grouped MC standard errors. Sum contributions
inside a physical group, square each group's sum, then sum and take the square
root. Retention errors additionally include shared numerator/denominator event
covariance. No new error bars or significance tests are fitted for deletion
contrasts. Seed min/max segments are not confidence intervals. Negative yields
and unsupported bins remain visible; no clipping or smoothing is performed.

Source ROOT metadata counts (164,716 signal, 554,279 background) and evaluation
physical-group counts (9,049, 698) are different counting units. Neither a complete
cutflow nor one-to-one entry/group correspondence is established. Training and
validation group counts are absent from current consumed aggregates and are not
filled from old records. The spectra show only ABCD/BCD at seed 42 and cannot
identify C's internal mechanism or explain all deletions.

## Same directory name, different artifacts

The historical nominal report `9aab6d…` and validation001 supplement `0e9551…`
retain the meanings documented in `DRAFT001-EVIDENCE.md`. They studied interval
widths and model-self diagnostics without establishing independent coverage
calibration. They are not current basic-metric inputs or validation. The current
page does not load `supplement-data.js`; the old synchronizer remains pinned to
its original report and does not refresh the current display transcription.
Historical figures in `figures/draft001/` are not referenced by current slides.

## Scientific boundary

No ROOT/events/checkpoints or original run aggregate payloads were read, hashed,
trained, scored or fitted for this synchronization. Only repository report text,
evidence records and publication figures were consumed. No scientific stage was
run and no contract or run evidence was changed.

Results remain `exploratory_posthoc`, `independent=false`,
`selection_aware_coverage=unvalidated`, `primary_claim_eligible=false`.
The study uses two controlled educational MC members, not collision data.
Repartitioning does not restore independence. No significance, precision gain,
independent feature contribution or universal best subset is established.
The collection's educational-use/publication restriction and unconfirmed production,
release-selection and some external-cut/weight details remain explicit in the report.
