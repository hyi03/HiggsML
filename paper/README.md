# English and Chinese manuscript builds

Both drafts use [selected-snapshot.json](evidence/selected-snapshot.json), which pins
result bytes, provenance bytes and report identity. The [version matrix](result-evidence.md)
separates restored test01, the old Chinese recovery report and unfinished test03.
The selected report is `var/runs-test-01/h4l-off-test01-old1/evaluation/report`;
`var/runs-test-01/h4l-off-test01/` is another version.

Use Python 3.12 in the `pytorch` environment, NumPy and Matplotlib. PDF compilation
also requires TeX Live, REVTeX 4.2, BibTeX and latexmk. From the repository root:

```bash
python paper/scripts/sync_manuscript.py --check
python paper/scripts/build.py
```

`sync_manuscript.py` without `--check` regenerates Chinese result tables from the
same pinned snapshot used by the English numeric macros and figures. The PDF build
rejects undefined references, overfull boxes and stuck floats. Visual PDF inspection
remains separate. Author/contact/affiliation/funding placeholders still need author input.

To reverify archived sources and rebuild identical selected results:

```bash
python paper/scripts/build.py --evidence-manifest paper/evidence/test01-source.json
```

The source manifest pins report/access identities and explicit original-to-archive
path maps. Fresh provenance timestamps may differ, but the existing paper requires
identical pinned result bytes. The selected snapshot is never overwritten.
`--run-name NAME` selects `runs/h4l-off-NAME/evaluation/report`; it is usable only
when its results match the paper selection. Changing analyses requires reconciling
both drafts and explicitly updating the selection.

Export a separate snapshot, without changing either draft:

```bash
python paper/scripts/collect_evidence.py --evidence-manifest paper/evidence/test01-source.json --output var/paper-evidence/test01-new-check
python paper/scripts/collect_evidence.py --report runs/h4l-off-test03/report-B --output var/paper-evidence/test03-stage-B-new-check
```

Output directories must be fresh. For relocated files use repeatable `--path-map OLD=NEW`;
the longest prefix wins. Maps never alter manifest bytes, artifact IDs or result meaning.
Missing required sources, wrong identities and hash mismatches fail closed. Stage B
missing results, failed bootstrap, valid intervals and either access independence value
are retained as recorded. The exporter checks selected aggregates and manifest links,
not every checkpoint/event/raw payload. No training, fitting, Toys or new assessment runs.

The selected generated snapshot is in `var/paper-evidence/`; the original snapshot remains
in `paper/evidence/data/`. Preserve these ignored local packages and archived sources when
moving the manuscript. Generated results/plots/PDFs must not be committed. A clean source
checkout requires the separate evidence package to rebuild; permanent external archival
publication has not been performed. See [verification](../docs/changes/evidence-alignment-20260923.md)
for software, source, numerical, PDF and scientific qualification boundaries.
