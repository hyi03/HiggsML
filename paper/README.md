# LaTeX manuscript build

The six PDF figures and four generated TeX inputs used by
[main.tex](latex/main.tex) are committed under `latex/figures/` and
`latex/generated/`. A normal PDF build reads these files directly; it does not
need local runs, evidence snapshots, NumPy, Matplotlib, or figure generation.
The historical source is pinned by [selected-snapshot.json](selected-snapshot.json).
As checked on 2026-10-12, the selected snapshot is absent at its declared path,
and `runs/h4l-off-test05/evaluation/report` contains a different report identity.
The historical committed assets are retained; the current local report is not
a replacement for the selected source. Ordinary compilation still works, but
selected-source regeneration and a bound full-precision release remain pending.
See the [evidence index](result-evidence.md) for scientific qualifications.
The local `paper/evidence/` directory is ignored by Git.

PDF compilation requires a TeX distribution with REVTeX 4.2, BibTeX and
latexmk. From the repository root, build directly from the committed assets:

```shell
conda activate pytorch
python paper/scripts/build.py
```

With Conda on PATH, `conda run -n pytorch python paper/scripts/build.py` is
equivalent. Ordinary compilation needs only Python's standard library and TeX;
absolute Python installation paths are host-specific, not prerequisites.

The default build runs only the TeX compiler and layout/reference checks. It does
not read `paper/selected-snapshot.json`, `paper/evidence/`, `var/`, or `runs/`.
To compile without the Python wrapper, run `latexmk -pdf -outdir=.build main.tex`
from `paper/latex/`; the resulting PDF is `.build/main.pdf`. The wrapper copies
it to `paper/latex/main.pdf` and rejects undefined references, overfull boxes and
stuck floats. Author/contact/affiliation/funding placeholders still need author input.

Only when intentionally refreshing figures and tables from the run, use Python
3.12 in the `pytorch` environment with NumPy and Matplotlib:

```shell
python paper/scripts/build.py --run-name test05
```

The run-name option reads `runs/h4l-off-test05/evaluation/report`, checks it against
the pinned snapshot, regenerates the six PDF figures and four TeX inputs, then
compiles. Review the resulting asset diff before committing.
Fresh provenance timestamps may differ, but the selected result bytes must match.
The known selected/current identity mismatch must be resolved before using this
refresh route; numerical agreement does not authorize reselection.
An optional local `--evidence-manifest` can additionally bind a report and access
receipt. Changing analyses requires revising the LaTeX manuscript and updating
the selection explicitly.

Export a separate snapshot without changing the manuscript or its selection:

```shell
python paper/scripts/collect_evidence.py --run-name test05 --output var/paper-evidence/test05-new-check
```

Output directories must be fresh. For relocated files use repeatable `--path-map OLD=NEW`;
the longest prefix wins. Maps never alter manifest bytes, artifact IDs or result meaning.
Missing required sources, wrong identities and hash mismatches fail closed. The collector
retains recorded bootstrap completion, finite-MC intervals, method and qualification
metadata. It checks selected aggregates and manifest links, not every checkpoint/event/raw
payload. It does not train models, fit likelihoods, generate Toys or open new assessment data.

The selected aggregate snapshot was recorded in the ignored local directory
`var/paper-evidence/test05-20260926/`, but is not currently present there.
Recover and preserve that exact package and its source runs for regeneration
or independent checks. An export of the current report has its own identity.
Historical test01 bindings and
snapshots remain local under `paper/evidence/`. The compiled `main.pdf`, PNG previews,
build logs, runs and evidence packages remain ignored. The committed PDF figure and
TeX inputs are sufficient to compile the current manuscript from a clean checkout.
Permanent external archival publication has not been performed.
