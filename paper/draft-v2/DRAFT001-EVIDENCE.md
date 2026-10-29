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
