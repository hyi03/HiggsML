# Draft-v2 manuscript: draft001 results

[main.tex](main.tex) is the current manuscript in REVTeX 4.2 APS/PRD reprint
format. It reports the completed controlled-MC run `h4l-draft-v2-draft001`, with
60/20/20 training/validation/final allocation and five representations trained
separately for seeds 42–44. All fifteen model intervals and the shared inclusive
reference have valid numerical status. Results remain exploratory,
non-independent and coverage-unvalidated.

## Project Report

[project-report.tex](project-report.tex) is a separate
English A4 project report dated 30 October 2026.
It presents the completed draft001 spectrum comparisons, lists
exact baseline cuts with external-source correspondence and project adaptations,
and distinguishes evaluation event-group counts from expected signed yields.
It includes two spectrum figures, selection/yield summaries and a compact
interval-results update. It does not claim a complete step-by-step cutflow.

Compile this report explicitly, independently of the manuscript:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=.build/project-report project-report.tex
cp .build/project-report/project-report.pdf project-report.pdf
```

The convenience [PDF](project-report.pdf) and build output are
ignored. The PDF is synchronized with the current source. The report uses the
existing figure copies in `figures/draft001/`;
compilation does not require the run directory or external document downloads.
In an editor, select `project-report.tex` explicitly as the build
target; keep `main.tex` as the original manuscript's target.

The current report was verified on 30 October 2026: eight A4 pages
compiled with local TeX Live 2026 /
latexmk 4.88, without warnings or overfull/underfull boxes. All pages were rendered
and visually inspected. Report numbers were checked against bound draft001
aggregates; the original manuscript source was unchanged. Tight-ID working-point
correspondence and the exact external source of the longitudinal-impact cut
remain explicitly unconfirmed. The report now states the model-self Asimov/T1
interval construction, the exact spectrum support-flag criteria and the
descriptive status of the mass-region fractions. No scientific stage was rerun.

## Chinese project report

The Chinese reports were reorganized on 1 November 2026 after the annotated-PDF
revision and the limited statistical update. They use two reading routes:

- [project-report-cn.tex](project-report-cn.tex) keeps the original filename and
  follows the spectrum-centered structure: scope, samples and selection, frozen
  network method, event counts and yields, mass spectra, and conclusions.
  Interval results and statistical diagnostics are retained in an appendix;
  the main conclusions still state the non-independence and undercoverage limits.
- [project-report-B-cn.tex](project-report-B-cn.tex) is a separate
  question-driven report: what the network selects, how feature-group deletion
  changes nominal intervals, and how robust those differences are. Each question
  connects the necessary method to its evidence and interpretation limits.

Both versions distinguish training, AUC checkpoint selection, validation-background
threshold selection, frozen evaluation, and signed-yield accounting. The existing
numerical table bodies and two figure assets are preserved. Detailed branch,
reconstruction, selection-source, normalization, and training information remains
in the appendices. Sample production details and exact release preselection are
still unconfirmed. The English report and REVTeX manuscript are separate versions.
The earlier ten-page layout is superseded; chapter and appendix references now
follow each report's structure. The comparison that motivated these changes is
in [structure-options-cn.md](structure-options-cn.md).

```sh
latexmk -lualatex -interaction=nonstopmode -halt-on-error -outdir=.build/project-report-cn project-report-cn.tex
cp .build/project-report-cn/project-report-cn.pdf project-report-cn.pdf

latexmk -lualatex -interaction=nonstopmode -halt-on-error -outdir=.build/project-report-B-cn project-report-B-cn.tex
cp .build/project-report-B-cn/project-report-B-cn.pdf project-report-B-cn.pdf
```

Both Chinese PDFs and build directories remain ignored; no scientific run is needed.
Choose the corresponding `.tex` file explicitly as the editor's build target.

## Current files

- [main.tex](main.tex): manuscript, abstract, methods, results and references.
- [workflow.tex](workflow.tex): executed workflow diagram.
- [draft001-tables.tex](draft001-tables.tex): fifteen widths and twelve paired contrasts.
- [draft001-spectra.tex](draft001-spectra.tex): signed-yield table and spectrum discussion.
- [DRAFT001-EVIDENCE.md](DRAFT001-EVIDENCE.md): report identities, hashes and checks.
- `figures/draft001/`: two verified PDF figures copied from the immutable report.

The two figure PDFs are tracked publication assets and are included in a clean
checkout. They are copied byte-for-byte from `runs/h4l-draft-v2-draft001/report/`
after checking their sizes and SHA-256 hashes against the bound manifest and
the evidence index. Ordinary compilation uses the tracked copies and does not
require `runs/`. Other generated figures and build outputs remain ignored.

## Compile

Keep this directory open in the Codex LaTeX editor for compilation and PDF preview.
A separate terminal build is also available, from this directory:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=.build main.tex
```

This requires REVTeX 4.2 and the AMS, graphicx, booktabs, TikZ,
microtype, xurl and hyperref packages. References are embedded; no external
bibliography is needed. Terminal output goes to `.build/main.pdf`. Build outputs
and the REVTeX-generated `mainNotes.bib` remain ignored. Compilation does not
require event access, scoring, training or interval fitting.

## Removed historical material

The historical illustration, tables, spectra, export helpers and their diagnostic
outputs are no longer part of this directory. They are archived in
[paper/draft-v2-history](../draft-v2-history/README.md), together with the earlier
manuscript snapshot. The bilingual historical explanation links the archived
sources. The historical selected manuscript, source runs and access ledgers retain
their identities. Current-source numerical values are not taken from that archive.

The tables use native `tabular` columns, following the reference manuscript.
This avoids the REVTeX/array/tabularx compatibility error observed with the local
TeX Live 2026 installation. Both the desktop compiler and the local LaTeX Workshop
`latexmk` command were checked after this change.
