# Evidence and verification record

Checked on 2026-09-22. This record accompanies the English REVTeX draft.
It describes manuscript verification, not an independent physics audit.

## Bound sources

The current source revision inspected for the manuscript is
`cd8cd69db45b831c6ddee2193177fb0f8473fc12`.
The retained report and Asimov analysis record the execution revision
`3819547357354aa04fa2dd85e1da3afeeaeb8ffb`.
Current-source inspection does not establish numerical equivalence of arbitrary
executions across these revisions.

| Object | Identity |
|---|---|
| Report path | `runs/h4l-off-test01/evaluation/report` |
| Report artifact | `3fe3e15ffe27f8480719deaa2a84a201d6a5062ca2611b0c5f67d62f54d23e05` |
| Asimov artifact | `5dac36b144f0992fcbfa0de6fe9d8019f22130b21548b8d8dcce8a4feb6ae876` |
| Freeze artifact | `01e623db2028849e7751c6c83c8811864833acd141be7eb521f0a773fbbd6a17` |
| Prepared artifact in freeze | `8c295b2881a808262e43300687b49d8f4c8cfde08c09cb54584c61a1e6c9d4da` |
| Protocol SHA-256 | `e8747ca77188732bac1d1c72e9e0ce4c86056a580cd45db9be33975837ed515e` |

`data/provenance.json` gives each of the 14 inspected published files, its actual
size and SHA-256, enclosing artifact identity, and enclosing manifest checksum.
It is the machine-readable record for the paper's aggregate snapshot.

## Numerical mapping

| Manuscript material | Published source and calculation |
|---|---|
| Abstract, subset widths, Appendix A | `mass_off_feature_metrics.csv`; all 80 widths compared with `asimov/inference.json` |
| Same-seed compact comparisons | Per-seed `1 - W_subset/W_ABCD`, followed by the five-seed median; checked against all 105 exported pairs |
| Shapley contributions | Exact four-player formula recalculated from each complete coalition vector; checked against the attribution CSV |
| Conditional interactions, Appendix B | All 24 second differences recalculated within seeds; checked against the interaction CSV |
| AUC-width plots and correlations | Validation absolute-weight AUC in the metric CSV and the Asimov summary; no assessment AUC was opened |
| Table I counts and total yields | Non-assessment `runs/h4l-prepare/prepare/audit.json` |
| Seed-42 BC category example | Signal/background arrays in the published Asimov model specification |
| Coverage in Table III | `five_seed_descriptive_diagnostics.csv`, `mu=1`, `conditional_coverage`; median of five seed values |
| T2 interpretation | Current `descriptive_seed_diagnostics` averages 20 outer coverages within a seed, then takes the seed median |
| Bootstrap status | `evaluation/mc-bootstrap-mu1/evaluation.json` and empty percentile fields in `mc_bootstrap_uncertainty.csv` |
| Mass grid and access status | Published `freeze/freeze.json` and `access-review/validated-off-assessment-access.json` |

All algebra comparisons use absolute and relative tolerance `1e-12`.
The maximum per-seed Shapley efficiency residual is 0.0 at the checked precision.
Formal bootstrap intervals remain absent. The four plots show individual seeds
and medians, without drawing seed spread as total statistical uncertainty.

The Fisher-information expression in the methods section is an analytic identity
for a known, fixed, nonnegative Poisson model. It is explanatory only. No Fisher
fit, new likelihood scan, or additional simulation experiment was executed.

## Differences from the existing Markdown record

`paper/result-evidence.md` and `paper/manuscript.md` identify
`report-resume-6f5909a8b7f58d5e` with report artifact `9c2413c8...` and different
freeze/prepared identities. That recovery directory is absent in this checkout.
The draft does not pretend that the present report is that recovery snapshot.

The present report has all 15 model-self cells valid. The old Markdown statement
that three model-self cells are blocked is not copied. The present aggregate
status remains incomplete: 161 of 200 event-MC replicas are valid, 39 fail support,
the access review has `independent=false`, and allocation sensitivity is pending.
The manifest's completed publication status is not confused with completed
scientific validation. Minor full-precision differences in widths are retained
from the present files, rather than copied from the old evidence table.

## Bibliographic verification

SciSpace was used for semantic literature discovery and abstract-level context.
Queries are recorded in `scispace-search.json`. The discovery results were not
treated as proof of novelty or as validation of this study's conclusions.

Crossref metadata was read successfully for the MEKD, CMS, INFERNO, Cowan,
Barlow--Beeston, pyhf, Gluesenkamp, Mandrik, Shapley, and Fryer references,
and for the Cowan erratum. These records are saved in
`data/bibliography_metadata.json`. The ATLAS collection title/DOI/year were
checked through the CERN Open Data record API. Cawley--Talbot authors, title,
year, volume, and pages were checked on the JMLR publisher page. The versioned
pyhf likelihood documentation was also opened. These results are in
`data/web_metadata.json`. An absent publication date for that documentation
is represented as `n.d.` rather than invented.

The live PRD author-instructions URL returned HTTP 403. The draft therefore
uses the installed official REVTeX 4.2 PRD style; no claim is made that the
current submission portal's complete checklist was verified. No submission,
third-party messaging, or upload of local research data was performed.

## Validation boundaries

The extraction checked named aggregate files against their enclosing manifests.
It did not rehash raw ROOT files, inspect event payloads, recursively validate
every upstream checkpoint, or rerun any scientific or software test suite.
The manuscript's numerical algebra, bibliography, LaTeX compilation, and page
layout are distinct verification activities. Existing scientific limitations
remain unchanged by preparing the paper.

## Manuscript checks

The main seven sections contain 5,294 prose words according to TeXcount, excluding
the abstract, captions, acknowledgments, data statement, and appendices. There are
four figures, three main-text tables, two appendix tables, and 13 references.
The PDF contains 13 pages, with wide numeric appendices placed on separate pages.

The final build has no undefined references or citations, overfull boxes, or stuck
floats. PDF text extraction finds the displayed key numbers and no unresolved
`??` references or replacement characters. Rendered pages were visually checked
for clipping, overlap, table readability, and equation/figure placement.
The installed REVTeX stack emits a `nameref` label-definition compatibility
warning and the APS bibliography style emits its `jnrlst` control warning;
neither indicates a missing citation or a layout overflow.
