# Evidence and verification record

Updated 2026-09-23. Both language drafts now bind **the same report and snapshot**.
The full [version/source/qualification matrix](../result-evidence.md) separates the
selected archived test01, the superseded Chinese recovery report, the other test01
archive, the incomplete test03 Stage B publication, and joint-support development.

## Selected sources and versions

[test01-source.json](test01-source.json) selects report artifact
`3fe3e15ffe27f8480719deaa2a84a201d6a5062ca2611b0c5f67d62f54d23e05`
in `var/runs-test-01/h4l-off-test01-old1/evaluation/report` with explicit path maps.
All 14 original source-file byte counts/SHA-256 values and enclosing manifest hashes
match the original `data/provenance.json`. The original snapshot is preserved.
The new export verifies 15 aggregate files including `report.json` and the explicitly
bound access receipt. No event payload or ROOT file was read.

Execution revisions differ legitimately: report `3819547357354aa04fa2dd85e1da3afeeaeb8ffb`,
Asimov/freeze `65a9d24f1f6ef0478669f3f0969fed0837938f61`, prepared and all 75 training
manifests `a4ecb8f3799729a01bb05aa00f1f5ef7c11b854a`. The earlier inspected-source
revision `cd8cd69db45b831c6ddee2193177fb0f8473fc12` describes the 2026-09-22 manuscript
check, not execution. This update uses baseline `5275fc586ec25d41e84459e665c168dba6a31671`
plus the F4/F11/F12 working-tree changes.

[selected-snapshot.json](selected-snapshot.json) pins the selected result bytes,
provenance bytes and report ID. Chinese tables and English figure/table macros both
read that selection. The selected snapshot is in the ignored local evidence package;
copy it with the manuscript or re-export the same archived sources. Generated data
must not be committed. A newly verified export may have a new check timestamp but
must reproduce the pinned result bytes before the existing manuscript can use it.

## Numerical mapping and limits

The exporter checks all 80 nominal widths against Asimov output, recomputes four
Shapley contributions, 24 conditional interactions and 105 paired comparisons with
`rtol=atol=1e-12`. It reads prepared non-assessment audit aggregates and the published
five-seed diagnostic summaries. Stage B and completed/failed bootstrap outputs retain
their actual state and interval fields. Independent access is never required to be
false by the exporter, and an independent access receipt alone grants no scientific
qualification.

The selected report has 15/15 model-self and 15/15 assessment cells and 5/5 T2 cells
numerically valid. Assessment BC/AC/ABCD conditional 68% coverage medians at mu=1 are
0.6680/0.6340/0.6340. T2 values are 0.6660/0.6480/0.6500. The former English statement
that no coverage summaries were available was incorrect for this selected snapshot.
Bootstrap remains 161/200, all formal percentile intervals absent, the access review
is non-independent and allocation sensitivity is pending. Publication `complete`
is separate from aggregate `incomplete` and scientific eligibility false.

Source restoration and aggregate algebra are software/source checks, not independent
numerical validation, physical-source approval, or confirmatory evidence. The old
P0 boolean and v1 `validated` strings remain unchanged in immutable artifacts; v2
interpretation grants only contract checks. Independent source/applicability packages
and historical-access gates remain required. Software verification and PDF build
limitations for this update are in [the change record](../../docs/changes/evidence-alignment-20260923.md).

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


## Historical manuscript checks (2026-09-22, not rerun here)

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
