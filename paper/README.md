# English and Chinese manuscript builds

Both drafts use [selected-snapshot.json](selected-snapshot.json), which pins
result bytes, provenance bytes and the **test05** report identity. The current
source is `runs/h4l-off-test05/evaluation/report`. See the
[evidence index](result-evidence.md) for scientific qualifications. The local
`paper/evidence/` directory is ignored by Git; it holds optional source manifests,
historical records and verification notes.

Use Python 3.12 in the `pytorch` environment, NumPy and Matplotlib. PDF compilation
requires a TeX distribution with REVTeX 4.2, BibTeX and latexmk. From the repository root:

```powershell
& 'D:/apps/anaconda3/envs/pytorch/python.exe' paper/scripts/sync_manuscript.py --check
& 'D:/apps/anaconda3/envs/pytorch/python.exe' paper/scripts/build.py
```

`sync_manuscript.py` without `--check` regenerates Chinese result tables from the
same pinned snapshot used by the English numeric macros and six figures. The new
MC percentile and conditional coverage figures distinguish finite-MC variability
from training-seed spread. The build checks Chinese table synchronization and rejects
undefined references, overfull boxes and stuck floats. Visual PDF inspection remains
separate. Author/contact/affiliation/funding placeholders still need author input.

To reverify the current sources and rebuild identical selected results:

```powershell
& 'D:/apps/anaconda3/envs/pytorch/python.exe' paper/scripts/build.py --run-name test05
```

The run-name option reads `runs/h4l-off-test05/evaluation/report` and rechecks the
result against the pinned snapshot. Fresh provenance timestamps may differ, but the
existing manuscript requires identical pinned result bytes. The selection is never
overwritten. An optional local `--evidence-manifest` can additionally bind a report
and access receipt. Changing analyses requires reconciling both drafts and updating
the selection explicitly.

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

The generated snapshot is in `var/paper-evidence/test05-20260926/`. Preserve this ignored
local package and the source runs when moving the manuscript. Historical test01 source
bindings and snapshots remain local under `paper/evidence/`; they are not the current
paper evidence. Generated results/plots/PDFs must not be committed. A clean source
checkout requires the separate evidence package to rebuild; the tracked selection
alone does not contain the full result arrays. Permanent external archival publication
has not been performed.
