# Draft-v2 manuscript: draft001 results

[main.tex](main.tex) is the current manuscript in REVTeX 4.2 APS/PRD reprint
format. It reports the completed controlled-MC run `h4l-draft-v2-draft001`, with
60/20/20 training/validation/final allocation and five representations trained
separately for seeds 42–44. All fifteen model intervals and the shared inclusive
reference have valid numerical status. Results remain exploratory,
non-independent and coverage-unvalidated.

## Current files

- [main.tex](main.tex): manuscript, abstract, methods, results and references.
- [workflow.tex](workflow.tex): executed workflow diagram.
- [draft001-tables.tex](draft001-tables.tex): fifteen widths and twelve paired contrasts.
- [draft001-spectra.tex](draft001-spectra.tex): signed-yield table and spectrum discussion.
- [DRAFT001-EVIDENCE.md](DRAFT001-EVIDENCE.md): report identities, hashes and checks.
- `figures/draft001/`: two verified PDF figures copied from the immutable report.

The figures are inputs to compilation, not disposable build-cache files. They
remain ignored and must be preserved with the local manuscript. Their originals
remain in `runs/h4l-draft-v2-draft001/report/`.

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
