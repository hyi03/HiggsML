# Paper result evidence index

Evidence review date: 2026-09-26. English translation: 2026-10-06; no new scientific
validation was performed for this edit. The formal LaTeX manuscript uses the
published test05 report; [selected-snapshot.json](selected-snapshot.json) pins the
result snapshot, provenance, and report identity. Evidence comes from actual run
artifacts, bound protocols, and execution code; historical documentation statements
are not treated as numerical evidence. The local `paper/evidence/` directory is
ignored by Git and may retain additional source manifests and historical review
records. The default manuscript build does not read that directory.

## Execution revision and bindings

Report path: `runs/h4l-off-test05/evaluation/report`. The report, Asimov, freeze,
prepared, and training artifacts record execution commit
`c5cdfa8dfab1733ee1cb2c0b4fbca087ab222a4f`, with a clean working tree at generation.
The 2026-09-26 paper export ran at the same revision with uncommitted changes to
paper tools. Its provenance field `source_dirty=true` describes the export
environment; it does not mean the historical scientific computation used those
changes.

| Object | Artifact ID |
|---|---|
| report | `baede583dc2ef36330af1184d266833f3e64a3179fc8d5ce8bff1b6867307cb5` |
| asimov | `45805304950d8ad926f551d7a914fb7ed88cfd6267877aace79f613fffd6c78c` |
| freeze | `21e5e6aaeea553c274eeceaffefff6afeb60a2f3ce85146933198ac9244bd2a1` |
| prepared | `2933b92e8df4909c579499b6f57147830fd72a878bcdd3377689be479dfa23cb` |
| registration | `9784a9de8a2b64cafd3ca540e51c26c98570dda1ef29e565975b50799abcb0c5` |
| template | `649a09a23bff2317c2924261caa74ee4d9f06072af7d62498141726d2dec982d` |
| access | `1551fbf5b4751212703e8ecd6d15358aaf16ff4491685614ad93bb27c9b38385` |

Core protocol SHA-256:
`e8747ca77188732bac1d1c72e9e0ce4c86056a580cd45db9be33975837ed515e`.
The threshold method is separately bound as `joint-support-v1`. The shared core
protocol hash alone does not make the historical median method and the current
analysis equivalent.

The snapshot directory is `var/paper-evidence/test05-20260926/`. Provenance records
the sizes, SHA-256 hashes, artifact identities, execution revisions, and manifest
hashes of 15 aggregate sources, together with all training identities.
The 2026-09-23 revision matrix and previous snapshot selection remain local under
`paper/evidence/history/`, preserving their historical meaning. Neither the old
test01 result with 161/200 bootstrap replicas nor the test03 Stage B status supplies
results for the current manuscript.

## Numerical mapping

W68 and AUC are medians across five seeds. Direct contrasts are paired within
seed before aggregation. Shapley values and 24 interactions are recomputed from
the complete coalition vector; all 105 pairwise comparisons were checked.
The algebraic tolerance `rtol=atol=1e-12` does not establish independent statistical
or numerical validation.

[make_figures.py](scripts/make_figures.py) generates manuscript figures, tables,
and macros from the pinned snapshot. The six PDF figures and four TeX inputs used
by the current LaTeX manuscript are committed to Git; ordinary PDF compilation
reads them directly. MC percentile ranges use only the complete-budget bootstrap
fields; training-seed ranges are not substituted for them.

The median W68 values for BC, AC, and ABCD are respectively
1.511617/1.515244/1.535930; the M0off median is 1.663723.
The 95% MC paired width-difference ranges for AC-BC, AC-ABCD, and BC-ABCD all
include zero and do not establish significant superiority. The Shapley 95% MC
ranges are positive for B and C and include zero for A and D. The 200 replicas
hold trained networks fixed, excluding independent retraining and post-selection
interval calibration. Each 2.5% tail contains only about 5 order statistics.

Five-seed median conditional coverage of the 68% intervals at mu=1 is:

| Candidate | model-self | assessment | T2 |
|---|---|---|---|
| M0off | 0.6500 | 0.6280 | 0.6370 |
| AC | 0.6680 | 0.6380 | 0.6535 |
| BC | 0.6780 | 0.6580 | 0.6635 |
| ABCD | 0.6560 | 0.6460 | 0.6495 |

T2 first aggregates outer-replica results within each training seed. Inner fits
must not be treated as independent repetitions of the full workflow. Figure
ranges show the minimum and maximum across five seeds, not confidence intervals
for coverage. Nominal template signed yields are 2.497852287449695 for background
and 2.7683194272433287 for signal. Role yields include role-specific rescaling and
must not be added across roles.

## Method and qualification

`joint-support-v1` explicitly specifies mass boundaries [105,140] GeV. Nonempty
candidates have two score categories, each with one mass bin; M0off is an inclusive
count. Calibration background proposes 19 quantile candidates. After requiring
support in both calibration and template roles, the selector chooses the point
closest to the median; it does not optimize W68. All 75/75 nominal selections use
the median. Of 15000 bootstrap selections, 112 deviate from the median and 0 fail.
T2 holds the template fixed, resamples calibration, and reselects the threshold.

| Evidence dimension | Recorded status |
|---|---|
| Computation completion | 80/80 nominal; 36/36 evaluation valid; 200/200 bootstrap valid |
| Toy candidate fits | model-self 120000, assessment 120000, T2 160000; all valid |
| Registration and post-selection coverage | exploratory_posthoc; selection_aware_coverage=unvalidated |
| Independent numerical / physical applicability validation | Incomplete; recomputation with the same implementation cannot replace an independent reference |
| Assessment access | single_researcher_self_review, independent=false |
| Claim eligibility | primary_claim_eligible=false; category-allocation sensitivity pending |

The prior integrity review checked identities, sizes, and hashes for 403 manifests
and 884 bound files across the three test05 roots. It also recomputed 4160 coverage
summaries from saved Toy intervals and found no inconsistency. The full record
is in the local ignored directory
`artifacts/test05-publication-review-20260926/review.md`. That review did not
redownload and verify raw ROOT files and was not independent validation of physics
or the statistical implementation. The paper exporter checks only its selected
aggregate sources; the wider integrity-review scope must not be attributed to it.

The historical paper export did not retrain, refit, change frozen thresholds,
generate new Toys, or open a new assessment population. Generated evidence remains
in ignored directories rather than being committed as source. Preserve both the
snapshot and run artifacts when migrating the project. Permanent external archival
publication had not been established at the evidence review date.
