# English and Chinese manuscript builds

The six PDF figures and four generated TeX inputs used by
[main.tex](latex/main.tex) are committed under `latex/figures/` and
`latex/generated/`. A normal PDF build reads these files directly; it does not
need local runs, evidence snapshots, NumPy, Matplotlib, or figure generation.
The Chinese result tables are already saved in [manuscript.md](manuscript.md).
The current source is `runs/h4l-off-test05/evaluation/report`; its identity
and result hashes are pinned by [selected-snapshot.json](selected-snapshot.json).
See the [evidence index](result-evidence.md) for scientific qualifications.
The local `paper/evidence/` directory is ignored by Git.

PDF compilation requires a TeX distribution with REVTeX 4.2, BibTeX and
latexmk. From the repository root, build directly from the committed assets:

```powershell
& 'D:/apps/anaconda3/envs/pytorch/python.exe' paper/scripts/build.py
```

The default build runs only the TeX compiler and layout/reference checks. It does
not read `paper/selected-snapshot.json`, `paper/evidence/`, `var/`, or `runs/`.
To compile without the Python wrapper, run `latexmk -pdf -outdir=.build main.tex`
from `paper/latex/`; the resulting PDF is `.build/main.pdf`. The wrapper copies
it to `paper/latex/main.pdf` and rejects undefined references, overfull boxes and
stuck floats. Author/contact/affiliation/funding placeholders still need author input.

Only when intentionally refreshing figures and tables from the run, use Python
3.12 in the `pytorch` environment with NumPy and Matplotlib:

```powershell
& 'D:/apps/anaconda3/envs/pytorch/python.exe' paper/scripts/build.py --run-name test05
```

The run-name option reads `runs/h4l-off-test05/evaluation/report`, checks it against
the pinned snapshot, checks the Chinese tables, regenerates the six PDF figures and
four TeX inputs, then compiles. Review the resulting asset diff before committing.
Fresh provenance timestamps may differ, but the selected result bytes must match.
An optional local `--evidence-manifest` can additionally bind a report and access
receipt. Changing analyses requires reconciling both drafts and updating the
selection explicitly.

Export a separate snapshot without changing either draft:

```powershell
& 'D:/apps/anaconda3/envs/pytorch/python.exe' paper/scripts/collect_evidence.py --run-name test05 --output var/paper-evidence/test05-new-check
```

Output directories must be fresh. For relocated files use repeatable `--path-map OLD=NEW`;
the longest prefix wins. Maps never alter manifest bytes, artifact IDs or result meaning.
Missing required sources, wrong identities and hash mismatches fail closed. The collector
retains recorded bootstrap completion, finite-MC intervals, method and qualification
metadata. It checks selected aggregates and manifest links, not every checkpoint/event/raw
payload. It does not train models, fit likelihoods, generate Toys or open new assessment data.

The current aggregate snapshot is in the ignored local directory
`var/paper-evidence/test05-20260926/`. Preserve this package and the source runs
for future regeneration or independent checks. Historical test01 bindings and
snapshots remain local under `paper/evidence/`. The compiled `main.pdf`, PNG previews,
build logs, runs and evidence packages remain ignored. The committed PDF figure and
TeX inputs are sufficient to compile the current manuscript from a clean checkout.
Permanent external archival publication has not been performed.
