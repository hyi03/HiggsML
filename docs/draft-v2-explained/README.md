# Draft-v2 explained: basic selection metrics

Open [Chinese](index.html) or [English](index-en.html) directly in a browser.
Both editions have 40 aligned slides following the seven chapters of the updated
[Chinese basic report](../../paper/draft-v2/project-report-cn.tex), dated
8 November 2026. The intended audience is advanced physics undergraduates and
readers who need an introduction to the ML method. No server, local runs,
ignored asset bundle, installation or internet is required.

## Reading route

| Slides | Report topic |
|---|---|
| 1–4 | Purpose, conditional deletions, roadmap and physical channel |
| 5–10 | Samples, baseline selection, weights, grouped errors and data roles |
| 11–18 | Features, MLP architecture, loss, AUC checkpoints, threshold and freeze |
| 19–23 | Retentions, signal/background ratio, units and ABCD/BCD worked example |
| 24–32 | All fifteen models, twelve contrast rows, interactions, deletion plot and C/A/B/D interpretation |
| 33–36 | Yields/errors, absolute spectra, normalized shapes and support limits |
| 37–40 | Qualifications, identities, outstanding evidence and conclusions |

The toolbar opens [all basic metrics](index.html#all-results) or
[mass spectra](index.html#spectra). Semantic links follow slide IDs; numeric
navigation uses the current order. Language switching preserves the current page.
Four existing interactions now teach input dimensions, weighted medians,
seed/metric comparisons and paired contrasts. The report's five-event artificial
threshold example gives t=0.80 and 60% high-side absolute weight; it is the default
teaching example. The grouped-weight arithmetic remains explicitly artificial.

Supervisor-request links and badges cover slides 33–36. They connect before/after
yields, simulated signal/background location, shape redistribution and interpretation
limits. They do not claim supervisor approval or new scientific validation.

## Current results and provenance

The current report artifact is
`a7e610a163e5d155705014201b7ee330323e3bf69309e0e89b2496edba5d4317`, documented in
[BASIC-20261108-EVIDENCE.md](../../paper/draft-v2/BASIC-20261108-EVIDENCE.md).
The shared run-directory name `h4l-draft-v2-draft001` does not identify the historical
`9aab6d…` artifact. Source identities, current PDFs and numerical tables are bound
separately; old interval/supplement values are not inputs or validation for this report.

Compare R_S, R_B and Q=S/B together at each model's frozen working point.
Removing C lowers signal retention, raises background retention and lowers Q for
all three seeds; A/B/D involve tradeoffs or seed dependence. All fifteen models
and all twelve metric/removed-group contrast rows remain visible. Retention
contrasts use percentage points; Q contrasts are direct differences. Min/max seed
segments are not confidence intervals, and no contrast significance is established.

`manuscript-data.js` transcribes report display cells: yields to four decimals,
percentages/percentage-point differences to two, Q/Q differences to three.
Paired medians and ranges come directly from the contrast table, not from
subtracting rounded cells. No full-precision aggregates or covariance are inferred.
The three original PDF figures are embedded from `figures/basic-20261108/`, with
links to open them separately if inline PDF viewing is unsupported.

Qualification remains `exploratory_posthoc`, `independent=false`,
`selection_aware_coverage=unvalidated`, `primary_claim_eligible=false`.
This educational/technical controlled-MC study is not an official ATLAS/CMS result,
a Higgs discovery or a physics measurement. The report also retains the source
collection's educational-use restriction.

## Checks and maintenance

```sh
node docs/draft-v2-explained/tools/check.mjs
```

Default checks evaluate both complete editions, compare all metric/contrast cells
with the current report, verify source identities and current PDF hashes, check
translations, links, navigation, teaching examples and LF endings.
`--source-only` runs the smaller script/resource/teaching check.

These are report/source consistency checks, not a new audit of original run
aggregates, event payloads or scientific validity. See [source notes](SOURCE-NOTES.md)
and [verification](VERIFICATION.md) for exact scope and browser checks.

Historical `supplement-data.js` and `tools/sync-results.py` retain their original
source meanings. Neither is loaded or executed by the current page. The old
synchronizer remains pinned to the historical artifact and must not be used to
populate this basic report. Historical statistical methods are briefly identified
on the provenance slide, as in the report's final appendix.
