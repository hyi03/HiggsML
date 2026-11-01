# Draft001 manuscript evidence — 29 October 2026

The numerical source for `main.tex` is the completed controlled-MC report
`runs/h4l-draft-v2-draft001/report/`. This is the new 60/20/20 study, with
ABCD/BCD/ACD/ABD/ABC separately trained at seeds 42–44. All fifteen model intervals
and the one shared inclusive-count reference have valid numerical status.
The historical test05 values and template spectra are not numerical inputs to
this manuscript version. Historical source files are archived in `paper/draft-v2-history/`.

Qualification remains `exploratory_posthoc`, `independent=false`,
`selection_aware_coverage=unvalidated`, `primary_claim_eligible=false`.
All controlled 2020 MC includes the historical test partition; repartitioning
and separate numerical outputs do not establish source independence. Explicit
user approval preceded the frozen final evaluation. No bootstrap, Toys, T2,
Shapley, CDF or adversarial results are added.

## Bound identities

- `report_artifact_id`: `9aab6d274a3e2d00d892c2d8fbf89b1e46f5b7a95d0bf0c085af90672ea36898`
- `evaluation_artifact_id`: `01df03a5ea98bb098f6e3c2069fee50a17c67d06e53a1bd84003b1d6680aa324`
- `freeze_artifact_id`: `f93ef041a9d32120fcaa1af0272d1a2af00484d5e08a50cafccaf457f6a60e8d`
- `prepared_artifact_id`: `23c0e583716df4efdeb80654409aabc106661063ff765765712cab411e320953`
- `source_kind`: `controlled_mc`
- `protocol_sha256`: `827cd54c01c03bd692dab38aed75656d5e4b76d99ea1ac5c9d134b1ec0da39cc`

The source manifest records revision `b71b0a09badc1f777a666be3f654ce34f329bc21`
and `git_dirty=true`. The run used Python 3.12.13 and pyhf 0.7.6 on macOS x86_64.

## Consumed report files

All report files were checked against their recorded sizes and SHA-256 hashes.
Evaluation and freeze aggregate files were similarly checked, as were the report's
prepared/freeze/evaluation upstream identifiers. `results.json`, `summary.json`
and `spectra.json` are byte-identical between report and evaluation. This is an
aggregate-binding check, not a new raw-data audit or physics validation.

| File | SHA-256 |
|---|---|
| `summary.json` | `d1258c0bf881f3e794cf1f1ffbb5ed3bf5a1f31f91b7e4d18e499452328d16a9` |
| `results.json` | `65cb901da9ce3124312b72c096c30238bf4c3767158b7729316ab379d44eec8d` |
| `spectra.json` | `c39ac66f09955d7a01589c8b8d93a44120a5c1d65428545e39c76939a3324b45` |
| `widths.csv` | `e099e9bc5c2636ff7cebecf7fc0e0bd80d5554eb1e9193a0e5ea33bae8a336a7` |
| `contrasts.csv` | `bd56775a5ec7f997fa1ef7c6cc48f7e921ecd806006124c933a0a0d05b6e34aa` |
| `yield-summary.csv` | `eb6092074678a26f2b81bebfb2adff669ee3a033eac053b6d31d5a9c15d034a9` |
| `mass-yields.pdf` | `3c55ff6007c10397418f74b978a6fb74378ee5dcfecb16537de7849199b2b305` |
| `mass-shapes.pdf` | `7f4dc8370882422531cb4f8effac4252213c1072e17333cad9c1a6b67bfff91c` |

`draft001-tables.tex` displays the bound summary at six decimal places. Every
width was checked against the result interval, and all twelve reduced-minus-ABCD
differences and their four medians were recomputed from unrounded widths.
`draft001-spectra.tex` quotes signed yields, correlated retention errors and mass
fractions from the bound report aggregates. The two spectrum PDFs are byte-for-byte
copies in the ignored `figures/draft001/` directory. Full before/after
and normalized-shape covariance remains in the immutable report's `spectra.json`.

This manuscript update did not read event payloads, score models, change thresholds,
train, fit intervals or rerun scientific stages. Numerical validity is distinct
from calibrated coverage and independent physical applicability.

## Build

From `paper/draft-v2/`, after preserving the verified figure copies:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=.build main.tex
```

Terminal output is `.build/main.pdf`, an ignored build output. The editor
maintains its own PDF preview. Compilation only reads TeX sources and the two copied
PDF figures, with no event or run access. A fresh environment needs the verified
figure assets; do not rerun MC analysis to compile the manuscript.
The pre-update main source, workflow and README are preserved locally under
`var/paper-evidence/draft001-manuscript-before-update/`.

## Manuscript validation before the REVTeX format conversion

The updated source compiled successfully with local TeX Live 2026 / latexmk 4.88
on 29 October 2026, producing 12 pages. The final log contains no undefined
references, LaTeX warnings, overfull boxes or underfull boxes. Figure and table
pages were visually inspected. The displayed width/contrast cells were checked
against the bound summary; source LF/whitespace, local graphic paths and reference
labels passed checks. `git diff --check` passed. The convenience PDF is identical
to the compiled PDF. No software regression suite was rerun for this document-only
update, and no new scientific or independent physics validation was performed.

## Directory cleanup — 29 October 2026

The obsolete historical TeX inputs and export helpers were moved to
`paper/draft-v2-history/`. The archived pre-draft001 manuscript and workflow
preserve the context required by the historical bilingual explanation. Historical
diagnostic output directories were relocated byte-for-byte, including manifests;
the original recorded provenance paths remain unchanged. The offline website's
source links and verification helpers now point to the archive.

The two current report figure copies were moved from the build-cache directory
to `figures/draft001/`, with identical bytes and hashes. The active spectrum source
uses those stable paths. Old previews, logs, auxiliary files and the obsolete
convenience PDF were removed from the active directory and preserved locally in
`var/paper-evidence/draft-v2-cleanup-20261029/`. That directory's `relocation.json`
records original paths, new paths and hashes. No run, checkpoint, final-evaluation
payload, access ledger or selected historical paper asset was removed or changed.

After cleanup, the desktop compiler successfully compiled the current project
through `workflow.tex`, resolving `main.tex` as the main document. Both offline
historical website verification scripts passed, as did all three archived
spectrum-helper tests. Current TeX input/figure paths, immutable-report figure
hashes, LF and `git diff --check` were checked. These are reporting and software
checks; no scientific stages were rerun.

## Chinese project report only — supplemental update, 1 November 2026

This addition binds only the limited statistical update in Chapter 7 and the
provenance note of `project-report-cn.tex`. It does not revise the historical
records above or the numerical source of `main.tex` and the English report.
Nominal widths, event counts, yields and spectrum figures retain the draft001
report identity stated above. The new material is taken from the separately
published controlled-MC supplement:

- Report: `runs/h4l-draft-v2-validation001/report/`.
- Report artifact ID: `0e95510075beff91cbcd68bba53109b63d459c70faea6223fdcf9181eba4c195`.
- Bound source report: `9aab6d274a3e2d00d892c2d8fbf89b1e46f5b7a95d0bf0c085af90672ea36898`.
- Execution and numerical status: complete; 248/248 terminal units, comprising
  200 paired event-group bootstrap replicas and 48 model-self cells containing
  500 Toys each (24,000 total). Threshold diagnostics share the bootstrap units.

| Consumed aggregate | SHA-256 |
|---|---|
| `summary.json` | `414e31e427969e6b4a423c0400704ac7097f784cbf9333d3a029d13351711837` |
| `bootstrap-summary.csv` | `1080d9ca991eed9a843e0844e4cf9fd08a8b6a9d5ec2b3c8f2b3f4aa650f06d6` |
| `coverage.csv` | `65d15b129ee237bbc1e43bd5b32dd1a567b87c23f664786fc85b5bd0cb7a0594` |

Chapter 7 adds the refitted-threshold 2.5/97.5 percentile ranges for the median
within-seed reduced-minus-ABCD width difference: C `[0.0101, 0.0711]` and
D `[-0.0384, 0.0055]`, rounded to four decimals. A and B ranges include zero.
These ranges condition on existing checkpoints and omit retraining and complete
model-selection uncertainty; they are not calibrated confidence intervals.
At injected mu=1, the 15 models and inclusive reference have model-self coverage
between 60.4% and 67.2% for nominal 68% intervals. This is evidence of
undercoverage within the model-self diagnostic, not independent calibration.
Assessment and T2 results are not included in this supplement. Qualification
remains exploratory_posthoc, independent=false,
selection_aware_coverage=unvalidated and primary_claim_eligible=false.

Before editing, the Chinese source and PDF were preserved in
`var/paper-evidence/project-report-cn-supplement-20261101-204139/`, with hashes
in `before.json`. The candidate compiled with the existing LuaLaTeX workflow
to ten A4 pages, without LaTeX warnings, undefined references or overfull/underfull
boxes. All ten pages were rendered at 150 dpi. Pages 1–8 are pixel-identical to
the preserved PDF, the original page-9 nominal table retains its position,
and changes on pages 9–10 are confined to the updated paragraphs and provenance.
Chapter starts, figure/table labels, nominal table source and references were
checked unchanged. The updated last two pages were visually inspected.
The local evidence folder contains source and page comparisons. No event
payload was opened and no training, scoring, Toy generation or interval fitting
was performed for this document update.

## Chinese report restructuring — 1 November 2026

The spectrum-centered rewrite keeps `project-report-cn.tex`; the separate
`project-report-B-cn.tex` presents the same evidence through three
questions about selection, feature-group deletion, and statistical robustness.
The separate report was subsequently renamed to `project-report-B-cn` and its
question-form headings and overview row labels were changed to declarative wording.
The earlier Chapter 7 references above describe the previous layout. Its interval
and supplemental results now appear in Appendix C of the spectrum report and
Sections 4–5 of the question-driven report. No source run or qualification changed.

The original source and PDF were preserved in
`var/paper-evidence/report-structure-20261101/`. All seven retained table bodies
(population, selection, features, evaluation groups, yields, mass-region fractions,
and nominal widths) match the pre-restructure source exactly. The progress-navigation
table was removed. The width table's caption now explicitly distinguishes
three-seed medians from the single shared inclusive-count reference.
The two figure copies still match the hashes recorded above. These checks compare
document assets; they do not constitute a fresh audit of scientific run payloads.

The revision separates network learning, validation-AUC checkpoint selection,
validation-background threshold selection, frozen evaluation, and signed-yield
accounting. Both reports retain the physical and statistical limitations,
including implicit mass information, one-bin/two-category inference, conditional
bootstrap ranges, model-self undercoverage and non-independence. Detailed
reconstruction, source comparisons and normalization remain available in appendices.

Both reports compile with the existing LuaLaTeX/latexmk workflow on macOS using
TeX Live 2026. The spectrum-centered report has 12 A4 pages; the question-driven
report has 11. Final logs contain no LaTeX warnings, undefined references,
overfull or underfull boxes. All final pages were rendered at 120 dpi and reviewed
for layout, with detailed inspection of the rewritten method and figure pages.
Labels, local graphic paths, preserved table bodies, quoted statistical values,
LF line endings and whitespace were checked. The convenience PDFs match the
compiled outputs. No event payload, scientific execution, new external-source
verification, or software regression suite was involved in this document-only edit.
