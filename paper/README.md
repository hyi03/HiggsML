# PRD-style English manuscript

`latex/main.tex` is an independently written research draft, not a LaTeX conversion
of `manuscript.md`. `latex/main.pdf` is the compiled reading copy. Author, affiliation,
correspondence, and funding placeholders require the authors' information.

The draft is an exploratory simulation study. PRD/REVTeX styling does not establish
submission readiness: the limitations in the abstract and validation section are
part of the scientific result.

## Build the supplied snapshot

Use Python 3.12 with NumPy and Matplotlib (the project's `pytorch` Conda environment
already supplies these), plus TeX Live with REVTeX 4.2, BibTeX, and latexmk.
Run from the repository root:

```bash
conda activate pytorch
python paper/scripts/build.py
```

To refresh the checked snapshot from a particular off-only run before building,
pass its short run name. For example, `test01` selects
`runs/h4l-off-test01/evaluation/report` and the other bound artifacts under
`runs/h4l-off-test01/`:

```bash
python paper/scripts/build.py --run-name test01
```

If latexmk is not on PATH, pass its executable explicitly:

```bash
python paper/scripts/build.py --latexmk /path/to/latexmk
```

The script generates four vector figures, two appendix tables, and the shared
numeric macros, then builds `latex/main.pdf`. It uses an argument vector for latexmk
and works without shell-dependent quoting. Intermediate TeX files and logs are
placed in `latex/.build/`. It rejects undefined references, overfull boxes, and stuck
floats before publishing the reading copy. Visual PDF inspection remains separate.

## Refresh from the same published local artifacts

```bash
python paper/scripts/collect_evidence.py --run-name test01
python paper/scripts/build.py
```

`collect_evidence.py` reads only the named published aggregate files in the retained
run and its prepared audit. It verifies their byte counts and SHA-256 values,
compares all 80 nominal widths with the Asimov output, and recomputes the four
Shapley contributions, 24 conditional interactions, and 105 paired comparisons.
It never reads event payloads, refits a likelihood, retrains a model, or creates
pseudo-experiments. A missing or changed input fails instead of substituting an
old Markdown value. It is intentionally bound to this paper's one retained run.

## Materials

- `latex/main.tex`, `latex/references.bib`: manuscript and bibliography entries.
- `scripts/collect_evidence.py`: verified extraction of the aggregate snapshot.
- `scripts/make_figures.py`: figures, appendix rows, and numeric macros from that snapshot.
- `scripts/build.py`: reproducible paper-only build.
- `evidence/README.md`: source identities, verification scope, and differences from old documentation.
- `evidence/scispace-search.json`: literature discovery queries and bibliographic policy.
- `evidence/data/`: checked aggregate snapshot, provenance, Crossref and official-page metadata.
- `latex/figures/`: vector PDF figures and PNG previews consumed by the manuscript.
- `latex/generated/`: numeric macros and appendix table bodies consumed by the manuscript.
- `latex/.build/`: TeX logs and local layout-review artifacts.

Generated results, figures, build files, and the PDF are ignored by
`latex/.gitignore` and the repository rules. They are available locally, but should not
be committed under the repository's generated-artifact policy. Preserve the
`evidence/data/` snapshot when moving the draft to another machine; it makes rebuilding
independent of the original run directory. The existing Markdown manuscript,
research code, protocols, and published runs are unchanged.
