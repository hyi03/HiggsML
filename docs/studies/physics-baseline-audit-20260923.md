# Physical-source audit and minimum-baseline readiness

## Record scope

Historical date: 2026-09-23; working-tree baseline HEAD:
`5275fc586ec25d41e84459e665c168dba6a31671`. HEAD excluded pre-existing uncommitted
changes; the local receipt bound actual starting bytes. This record was translated
into English and relocated on 2026-10-06 from
`docs/changes/priority4-physics-baseline-audit-20260923.md`. The original remains
in Git history before migration (HEAD `e1448f3eb1b841b371d82b3ccfc1bc4f7f2bf160`).
It followed section 6 of the research-quality solution confirmation, historically
`docs/4-Reviews/research-quality-audit-2026-09-23-review-confirm.md` (an ignored
local review, not a distributed evidence source).

**Source checking and baseline design that could proceed independently during F2
were completed. Normalization constants matched the fixed official source, but
data-purpose, event-correction, production-process and independent angle/probability
references remained incomplete. Reliable gain after resolving the mass peak
was not ready for validated execution.** Completion referred to the audit, not
resolution of F1/F6/F7. These are dated findings, not a fresh source certification.
For the current educational/technical study and selected result, see
[research design](../research-design.md) and [results and limitations](../results-and-limitations.md).

Only this audit and ignored evidence/scripts were added in the original task.
F2 code/protocol/input/budget/streams and F4/F11/F12 work were preserved.
No ROOT/event payload/new assessment, training or formal bootstrap/Toy/T2 was opened
or executed. The 2026-10-06 relocation did not repeat external source checks.
Historical evidence under `var/priority45-audit-20260923-001/` was not found in
the migration workspace and is not bundled with Git. Paths below preserve
provenance rather than linking to unavailable artifacts.

## 1. Evidence and checking method

The ignored evidence root was to be preserved separately with the research archive:

- `public-sources/receipts.json`: URLs, acquisition times, sizes and SHA-256 for
  six public records/source files.
- `public-supplement/receipts.json`: three fixed-version HZZ example source files.
- `local-metadata/receipts.json`: 71 whitelisted acquisition/prepare/freeze/access/
  claim metadata copies and original paths.
- `audit-findings.json`: constant comparison, file metadata matching, role support
  and historical resource inventory.
- `summarize_audit.py`: AST-literal extraction of official constants; downloaded
  Python source was not executed.

Official records were read as JSON. Only contracted MC members were compared;
record-listed event files were not downloaded. All 80 saved evidence files passed
size/SHA-256 checks. Filename, size and Adler-32 agreement was metadata matching;
local ROOT hashes were not recomputed. Discovery preferred the graph, falling
back to known files when the graph had no results.

## 2. Data purpose precedes publication positioning

The audit recorded that [CERN Open Data 2020 record 15005](https://opendata.cern.ch/record/15005)
`metadata.usage.description` stated:

> This dataset is provided by the ATLAS Collaboration **only for educational purposes and is not suited for scientific publications**.

The record also listed CC0-1.0. Scientific suitability/purpose and licensing are
different: the statement was not interpreted as a comprehensive legal publication
ban, and CC0 did not turn the samples into research-grade physical inputs.
Retaining these samples requires an educational/technical-method demonstration
scope. Physical precision, realistic background-composition or cross-condition
generalization claims require suitable research-grade MC, provenance and validation.
Journal suitability also depends on contribution, positioning and citation policy;
the audit did not decide on behalf of a journal.

The audit also recorded educational/outreach positioning for the ntuple format in
[2025 record atlas-93928](https://opendata.cern.ch/record/atlas-93928), with research
analysis directed toward research-oriented open data. New 2025 files alone do not
resolve suitability. The project remains MC-only and does not introduce collision
data. These are historical source observations, not a new legal or publication
assessment.

## 3. DSID and normalization-source comparison

The fixed official source was
[infofile.py](https://github.com/atlas-outreach-data-tools/atlas-outreach-Python-uproot-framework-13tev/blob/8ad2015be6d350060c3a183aff5802570bc9ada4/infofile.py),
commit `8ad2015be6d350060c3a183aff5802570bc9ada4`, located through its commit
history. All examples used that commit. Contracted master URLs were not changed;
the audit added an immutable source binding.

| Item | Signal | Background |
|---|---|---|
| DSID | 345060 | 363490 |
| Official key | ggH125_ZZ4lep | llll |
| Official file | mc_345060.ggH125_ZZ4lep.4lep.root | mc_363490.llll.4lep.root |
| File bytes | 50,518,236 | 179,082,866 |
| Official Adler-32 | 1ea0e560 | 6298e6cb |
| xsec, pb | 0.0060239 | 1.2578 |
| sumw | 27,881,776.6536 | 7,538,705.8077 |
| red_eff | 1 | 1 |
| Local k-factor / filter efficiency | 1 / 1 | 1 / 1 |
| Audit conclusion | Metadata/constants matched | Metadata/constants matched |

Official events were 985,000 and 17,825,300, not downloaded skim entry counts;
they cannot replace signed sumw in normalization. The loose at-least-four-lepton
preselection was not the project's final 2e2mu, 105--140 GeV selection.
The [dataset science contract](../../config/dataset_science_v1.json) used
effective_xsec, and [weights.py](../../src/higgsml/physics/weights.py) defined:

```text
w = luminosity_pb * xsec_pb * k_factor * filter_efficiency / sum_of_weights * mcWeight
```

Official [HZZAnalysis.py](https://github.com/atlas-outreach-data-tools/atlas-outreach-Python-uproot-framework-13tev/blob/8ad2015be6d350060c3a183aff5802570bc9ada4/HZZAnalysis.py)
used `lumi*1000*xsec/(sumw*red_eff)`, consistent with 10 fb^-1 = 10,000 pb^-1.
Matching constants did not derive every physical effective-cross-section factor.
Before adding k-factor, BR or filter efficiency, establish whether they are
already absorbed to prevent double multiplication.

### 3.1 Established event-weight difference

The example's calc_weight multiplied:

```text
mcWeight * scaleFactor_PILEUP * scaleFactor_ELE
         * scaleFactor_MUON * scaleFactor_LepTRIGGER
```

The audited [2020 profile](../../config/profiles/open_data_2020.yaml) did not map
these four corrections, and the physical-weight function had no such parameters.
This established a different weight definition, not a numerical yield bias.
Equal xsec constants did not prove event corrections were absorbed. No branch
values or correction effects were computed; direct transplantation into the
project's selection was not justified.
Next, establish reconstruction/ID/isolation/trigger applicability, included
corrections and correlations, then quantify yield/shape/signed-support/training
effects in a separate authorized development study. An uncorrected method scenario
needs explicit scope; revised physical weights need the new lineage in section 6.

### 3.2 Incomplete physical-source requirements

| Item | Evidence at audit time | Missing acceptance material |
|---|---|---|
| 2020 generator/version/order/PDF/shower/tune | File and constants identify processes | Both DSIDs' production configuration/job options, campaign and weights; no borrowing 2025 filename details |
| Effective cross section/filtering | Numbers and red_eff=1 matched | Cross-section source and BR/k-factor/filter absorption |
| llll composition | Official example labels ZZ | Initial state/interference/generation filtering; not proof of pure qqZZ |
| Negative-weight origin/group correlation | Prepare summaries showed negative weights | Generation mechanism, duplicates and positive/negative correlation; moment matching is insufficient |
| FSR/lepton/detector definitions | Repository reconstruction/selection contract | Ntuple dressed/bare, FSR/detector conventions and correspondence |
| Pileup/lepton/trigger corrections | Official example uses them; project does not map them | Applicability and independent numerical comparison; names alone are insufficient |
| Angles/MELA | Adapter and fixed backend contract | Independent four-vector, angle and probability reference; internal round-trip is insufficient |

Official [HZZSamples.py](https://github.com/atlas-outreach-data-tools/atlas-outreach-Python-uproot-framework-13tev/blob/8ad2015be6d350060c3a183aff5802570bc9ada4/HZZSamples.py)
also listed VBF/WH/ZH, Z and ttbar. The ggH/llll two-process setting was narrower
than a complete H->4l analysis. The audit did not expand samples.

## 4. Resolved-mass baseline: total support does not prove per-bin support

Prepare role summaries matched the archived preparation. The task read existing
audit.json only, without generating mass histograms:

| Role/process | Physical groups | signed N_eff | rho | signed yield |
|---|---:|---:|---:|---:|
| calibration background | 575 | 173.3205 | 0.65756 | 2.55317 |
| template background | 590 | 170.3650 | 0.65752 | 2.49785 |
| template signal | 7,221 | 7,173.0798 | 0.99668 | 2.76832 |

Template background negative-weight fraction was about 10.678% and group variance
about 0.03662294. Existing off-only mass edges [105,140] formed one bin. A new
mass/score grid requires per-process/role/bin positive net yield, signed N_eff,
rho and covariance checks. Total N_eff does not specify a feasible bin count;
resolved-mass feasibility remained unverified.

Bounded development should define common candidate grids that resolve the peak,
then inspect only permitted development/calibration/template groups and retain
per-bin signed yield, positive/negative components, group covariance and failures.
Grid/merge rules need advance resolution/support/stability criteria, not assessment
or candidate rankings. Pre-freeze development is separate from F2 formal budgets.
If no histogram is feasible, do not hide it with arbitrary smoothing: stop that
claim or independently validate a parametric model with shape uncertainty.

## 5. Minimum baseline matrix and admission criteria

| Baseline | Question | Common fixed conditions | Audit status / next step |
|---|---|---|---|
| B0: mass shape | Reliable precision from the peak itself? | Selection, yields, mass model, nuisance, interval method | Per-bin support and independent interval validation pending |
| B1: B0 + off score, BC and ABCD | Does compact input retain full-input precision? | Same B0, category budget, selector and training opportunity | Main design in confirmation study; new family, not a rewrite of old attribution |
| mass-only and explicit on/off controls | Is gain residual within-bin mass information? | Common grid/precision rules, separately trained/bound models | Design ready; training/comparison unexecuted; off is not conditional independence |
| B2: B0 + validated MELA | Comparison with interpretable physical discriminator? | Matched information, process assumptions/statistics | Independent angle/probability reference and DSID composition missing |
| B3: inference-target training | Advantage over inference-aware methods? | Matched training/nuisance information/final validation | Add only for a learning-method advantage claim; no implementation expansion here |

The [reproduction guide](../implementation-and-reproduction.md) binds JHUGenMELA
commit `10d36ced1d71b5e4e21abb1c9834a02570bf31c0`,
`kinematic_decay7_at_fixed_m4l_no_mass_pdf`, `computeP(False)`, signal
`HSMHiggs/JHUGen/ZZGG`, and background `bkgZZ/MCFM/ZZQQB`.
Kinematic probability at fixed m4l is not complete m4l independence; the adapter
does not establish decorrelation. Canonical massless leptons remove system boost/
global phi, differing from a full-four-vector optimal likelihood information scope.

Independent checks should cover Z ordering, charge direction, periodic boundaries,
degenerate geometry, units, probabilities for fixed four-vectors, and backend/
compiled extension/adapter/input hashes. qqZZ MELA does not certify llll composition.
The schema registry had mappings; these were not independent physical-reference
certification. The old guide's "empty registry" wording was not a current fact.
The original audit used SciSpace to check titles/abstract uses for
[MEKD](https://doi.org/10.1103/PhysRevD.87.055006) and
[INFERNO](https://arxiv.org/abs/1806.04743), motivating matrix-element and
inference-target baselines. It did not reproduce full algorithms. Indexing year
was not publication year; literature did not validate project implementation.

## 6. Change dependencies and rerun map

| Subsequent change | prepare | train | calibration/template, freeze, inference/report |
|---|---|---|---|
| Source prose/audit/citations only | No event recomputation | No | No numerical rerun for prose; new qualification artifacts rebuild affected bound metadata |
| Event weights/correction fields | New root | Normally retrain because optimizer uses absolute physical weights; prove unchanged inputs/weights for reuse | Rebuild all affected stages |
| Selection/FSR/angles/event identity | New affected reconstruction | Retrain affected representations | Rebuild lineage; no mixing old freeze |
| Only mass likelihood/common grid | Reuse if prepared features identical | Reuse if network/input contract unchanged | New protocol and Stage B; rerun complete comparison |
| MELA baseline | Audited reuse of MC preparation | Reuse old networks; bind MELA separately | Independent reference before export/import/new baseline inference |
| Independent/research-grade MC | Separate preparation after identity/history review | Frozen-model transfer and retraining are different estimands | New resources/protocol/budgets/streams |

F2 could inform support/finite-MC priorities, not replace source, interval or
independence conditions. The [statistical-validation study](statistical-validation-20260923.md)
already found low-count asymptotic undercoverage and left T1/selector validation
pending. No B0--B3 scientific pass was declared.

## 7. Delivery and validation limits

Completed: official-purpose audit, four configured MC files' metadata matching
across two releases, 2020 two-process constant comparison, correction differences,
role support, minimum baseline and rerun map. Independent-resource conclusions
are in the [confirmation design](confirmation-design-20260923.md).
Shared `verification.json` checked saved bytes, extraction assertions, document
links/LF and preservation of existing work. It was not full regression, full-MC,
MELA numerical validation or publication certification. No full suite ran because
production implementation was unchanged.
