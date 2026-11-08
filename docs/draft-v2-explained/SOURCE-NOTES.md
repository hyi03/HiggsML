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

## Neural-network teaching expansion — 8 November 2026

The eight added bilingual pages are educational explanations based on report
Section 3 and the existing ResearchClassifier implementation; they are not added
scientific evidence or changes to the report. The actual network remains
`d_in → 64 → 64 → 32 → 1` with sigmoid applied for scoring. Hidden blocks 1/2
use Linear/LayerNorm/SiLU/Dropout(0.1), block 3 omits Dropout, and output is Linear.
Training uses logits for stable loss. Saved input scaling differs from within-event
LayerNorm; dropout masks hidden outputs only during training.

The tiny forward function in `teaching.js` uses these fixed artificial definitions:

```text
x1 = (pT4l - 40) / 20
x2 = (absDeltaPhiZZ - 1.6) / 0.8
a1 = 0.6*x1 - 0.4*x2 + 0.1
a2 = -0.3*x1 + 0.8*x2 - 0.2
h1 = SiLU(a1); h2 = SiLU(a2)
z = 0.9*h1 - 0.7*h2 + 0.05
score = sigmoid(z)
```

Inputs range over [0,160] GeV and [0,pi] rad, defaulting to 40 and 1.6.
Default hidden outputs are about 0.052497918747894 and -0.09003320053750444;
z is 0.1602713672493577 and score 0.539982293295586. Display rounds to four
decimals; intermediate calculations retain JavaScript Number precision. Invalid
or nonfinite inputs are rejected. Reset restores inputs, not trained parameters.

These scaling statistics and coefficients are not obtained from MC, checkpoints
or a fit. The reduced network omits extra layers, LayerNorm and Dropout, and has
no real selection threshold. Independent input adjustment does not imply a valid
full physical event. The example score must not be interpreted as a physical
probability, model performance or research result. Teaching slides are labelled
separately from current report results. Existing report display data and publication
figures retain their original bytes, bindings and interpretation.
