# Basic feature comparison — 8 November 2026

This record binds the synchronized Chinese and English basic project reports (`project-report-cn.tex` and `project-report.tex`). The B report, REVTeX manuscript and historical DRAFT001-EVIDENCE.md retain their original sources.

## Source identities

- Report: `a7e610a163e5d155705014201b7ee330323e3bf69309e0e89b2496edba5d4317`
- evaluation_artifact_id: `2e7995da1e9e27f239551acc05cd9b94f97e4f56297bf3cabdbdf96b9044efaf`
- freeze_artifact_id: `c3b15bf87e37b132a542cb3a4dbc7d3d936680ed2691f6b51391a90b7851e12b`
- prepared_artifact_id: `566a4493bfaf9f34b48c7e1671cfc9dacc5dcd6bf4915efd035815ceec76a40c`
- source_kind: `controlled_mc`
- Source: `runs/h4l-draft-v2-draft001/report/`.
- Protocol SHA-256: `827cd54c01c03bd692dab38aed75656d5e4b76d99ea1ac5c9d134b1ec0da39cc`.
- Qualification: exploratory_posthoc; independent=false; selection_aware_coverage=unvalidated; primary_claim_eligible=false.

## Checks and derivation

All four stage manifests passed canonical identity and protocol checks. Consumed non-event files passed size/SHA-256 checks. Report/evaluation aggregate copies match; fifteen model identities and thresholds match the freeze, which is frozen and has a bound approved exploratory-access receipt. All fifteen model results and the shared inclusive reference are valid. Summary recomputation agrees with results.json. Each model uses categories [0,1] and one [105,140) mass bin. Signed high+low yields agree with the inclusive baseline within relative tolerance 1e-10. Spectrum totals agree with templates.

No events.jsonl or ROOT payload was read or hashed; no training, scoring, fitting or Toys were run. No new supplemental validation results were consumed. Training/validation group counts are absent from the consumed aggregates and are not carried forward from historical tables. Source entry counts come from population metadata. Evaluation counts come from templates.

For each seed compute S, B, 100*S/S0, 100*B/B0 and S/B from full-precision template yields. For each removed group subtract ABCD within seed; summarize the three differences with median/min/max. All denominators are positive. Plot points are the three seeds, diamonds their medians, segments min/max, not confidence intervals.

## Consumed report files

| File | SHA-256 |
|---|---|
| `binding.json` | `594bbf30637cd35fbbc6f68f882da04d4a01c696a098614c5ead4f700f63b562` |
| `contrasts.csv` | `bc4bd9383413648804c75554ea6d41979118eea29027fcead92a4b2026147985` |
| `inclusive-reference.csv` | `82ba282c2a6990009dc2eade3644065f3947b218d2c02029bf429888a71b90de` |
| `mass-bins.csv` | `a6dfcd3855807e9ecd120a0347a2233cbbece5f1652744ae17868f4812e7c532` |
| `mass-shapes.pdf` | `2652429bd80559042c1342d3174b809bd560d96b224beeb77a81d7a23c671f6d` |
| `mass-shapes.png` | `16752b2335cda9f31bdba93e37b6ea39ea2912eef6c0eccc9e2b4d7e0dd98efc` |
| `mass-yields.pdf` | `f43e44c43995193ed3bf2b00b85879a21fa402f6e174913a5e977b72d739a06b` |
| `mass-yields.png` | `05f8eba72300a8cba50a854612653704c32354ef99543a744ae99bc97a2c3612` |
| `protocol.json` | `827cd54c01c03bd692dab38aed75656d5e4b76d99ea1ac5c9d134b1ec0da39cc` |
| `report.md` | `0eb282698c6c05d7fad1f66b86e449f11291953ceeaa4cd7603dda7a897836e9` |
| `results.json` | `4aa3728bd00ba6d1c83a47f34c80264194585aea8100ddd54a867bd83630114d` |
| `spectra.json` | `0b6d5dfd0f3db045b48f429f04a280922998fbaa439204a01b61f2c2361cd2c7` |
| `summary.json` | `39c1d99a64941b9c17b94f108961a29ac24f57f1ae18b9e60f1627f8a9bbd5cc` |
| `widths.csv` | `a24591d961fb8bbb64b402d966481ae044fbaf87cc49be140c1a1625357893a2` |
| `yield-summary.csv` | `c56a6bf2eeab33c7b352dfb4d25243bf9cd235d6d395e40105fdbde64ad47038` |

## Publication assets

The two spectra are byte-for-byte copies of the verified report PDFs in `figures/basic-20261108/`; the deletion plot is derived from the same templates. Historical assets in `figures/draft001/` are unchanged.

| Asset | SHA-256 |
|---|---|
| `deletion-differences.pdf` | `7707cb990bfc297c069339e4d1543f3a70a4930bf326af884bb3f9c72bed8ca9` |
| `mass-shapes.pdf` | `2652429bd80559042c1342d3174b809bd560d96b224beeb77a81d7a23c671f6d` |
| `mass-yields.pdf` | `f43e44c43995193ed3bf2b00b85879a21fa402f6e174913a5e977b72d739a06b` |

## Basic values

| Model | S | B | Signal retention (%) | Background retention (%) | S/B |
|---|---:|---:|---:|---:|---:|
| ABCD:42 | 2.68238882282 | 1.20268915207 | 96.8017767907 | 51.0625914242 | 2.23032594765 |
| ABCD:43 | 2.6808502265 | 1.158852302 | 96.7462520822 | 49.2014096214 | 2.31336661442 |
| ABCD:44 | 2.66700285963 | 1.08337394239 | 96.2465297057 | 45.9968237716 | 2.46175651387 |
| BCD:42 | 2.62146040858 | 1.1012081768 | 94.6029983343 | 46.7540121305 | 2.38053118729 |
| BCD:43 | 2.61561374257 | 1.11454584984 | 94.392004442 | 47.3202899155 | 2.34679779475 |
| BCD:44 | 2.6263839168 | 1.13443317487 | 94.7806774014 | 48.1646463732 | 2.31515083919 |
| ACD:42 | 2.66669514036 | 1.15357776606 | 96.235424764 | 48.9774685694 | 2.31167348993 |
| ACD:43 | 2.66792601742 | 1.12321907002 | 96.2798445308 | 47.688528955 | 2.37524992998 |
| ACD:44 | 2.70392917129 | 1.28130436243 | 97.5791227096 | 54.4003585931 | 2.11029420532 |
| ABD:42 | 2.57314848416 | 1.21860952653 | 92.8595224875 | 51.7385230022 | 2.11154469757 |
| ABD:43 | 2.54083796146 | 1.21918795543 | 91.6935036091 | 51.7630813666 | 2.08404122608 |
| ABD:44 | 2.58053374649 | 1.20257782502 | 93.1260410883 | 51.0578648101 | 2.14583513249 |
| ABC:42 | 2.69746706675 | 1.12411478322 | 97.3459189339 | 47.7265582638 | 2.39963668036 |
| ABC:43 | 2.69715934748 | 1.03112153706 | 97.3348139922 | 43.7783426126 | 2.61575309072 |
| ABC:44 | 2.69408215484 | 1.13855759881 | 97.2237645752 | 48.3397571025 | 2.36622385873 |

## Verification on 8 November 2026

Before the model-explanation addition, the 15-page Chinese PDF compiled with no warnings, undefined references, missing
characters or overfull/underfull boxes. All fifteen numerical rows and twelve
contrast rows were checked against the unrounded aggregate calculation; the
published yield/error table was checked against the new report CSV. Labels and
figure paths resolve. All pages were reviewed as a contact sheet; the new tables
and deletion plot were also inspected at full-page resolution. No clipping or
overlap was observed. This verifies document consistency, not independent
physical applicability, coverage or statistical significance.

## Model explanation revision — 8 November 2026

The main text now describes the MLP architecture and each layer's purpose, then
explains mini-batches, weighted binary cross entropy from logits, AdamW, early
stopping, seed variation and frozen scoring at undergraduate level. Source checks
used `ResearchClassifier` in `src/higgsml/modeling/discriminants.py`,
`src/higgsml/draft_v2/training.py`, and the frozen draft-v2 protocol. All fifteen
model files passed manifest/hash and model-seal validation, architecture checks,
checkpoint-history validation and prepared/protocol bindings. No event payload,
training, scoring or fitting was needed. Numerical tables and figure assets are
unchanged. The revised PDF is 16 pages and compiles without warnings, undefined
references, missing glyphs or overfull/underfull boxes.
The rendered model-layer table and training explanation on pages 3–4 were visually checked; no clipping or overlap was observed.

## Structure and concision revision — 8 November 2026

The report is organized into seven main chapters. A compact physical-feature
summary precedes the neural-network explanation; the ABCD/BCD worked example now
precedes the full fifteen-model comparison. A group-by-group C/A/B/D analysis
immediately follows the deletion plot. The historical interval table was removed
from this report and replaced by one paragraph referencing the existing historical
evidence; that evidence record and other manuscripts were not edited.

All six current-result table bodies are unchanged: source/evaluation population,
selected group counts, signed yields/errors, fifteen model metrics, twelve
contrasts, and mass-region fractions. The three current PDF figure SHA-256 hashes
remain identical to those recorded above. New prose explains the derived S/B
identity, group-contribution standard errors and covariance-aware retention
errors. The latter formula was checked against all four existing spectrum
aggregate records after checking the spectra.json hash. These are consistency
checks of existing results, not newly fitted errors or scientific validation.
The code's square-root variance and circle markers were checked against the
corrected spectrum captions. No event payload, scientific run or external
literature fetch was required.

The final PDF remains 16 pages. LuaLaTeX/latexmk completed with no warnings,
undefined references, missing characters or overfull/underfull boxes. Seven-chapter
order, retained user-specified subsection titles, label uniqueness, reference
resolution and LF endings passed checks. All pages were reviewed in a contact
sheet; the example/difference methods, results interpretation, error appendix and
implementation/source appendix were also inspected at full-page resolution.
No clipping or overlap was observed. Reproduction details and the README were
updated to describe this final organization.


## English synchronization — 8 November 2026

`project-report.tex` now follows the revised Chinese basic report's seven-section
structure and five appendices. It includes the three-hidden-layer MLP, training
and checkpoint rules, frozen threshold procedure, basic metrics and worked
example, full results, C/A/B/D interpretation, spectra and scientific limitations.
The former English interval table and historical-run yields are superseded in
this report; historical interval methods are summarized with their original
source and undercoverage limitations. Historical evidence records are unchanged.

Six numerical table bodies match the Chinese version: population, event-group
counts, yields/errors, fifteen model metrics, twelve contrast rows and mass-region
fractions. The existing `results.json` SHA-256 was checked against the record
above; its fifteen valid model results and inclusive reference were used to
recompute all displayed basic metrics, within-seed differences, medians and ranges.
High+low yields agree with the shared baseline at relative tolerance 1e-10.
All three figure hashes are unchanged. Display equations agree apart from
translated annotations and sentence punctuation; labels, citations, source URLs
and figure paths match, with no unresolved references or residual Chinese text.

The 19-page English PDF was built using LuaLaTeX/latexmk on macOS 27.2 arm64
(TeX Live 2026, LuaHBTeX 1.24.0, latexmk 4.88). The final log has no warnings,
undefined references, missing glyphs or overfull/underfull boxes. All pages were
rendered; layout overviews and full-page checks covered the network explanation,
worked example, full comparison, spectra and appendices. No clipping or overlap
was observed. The convenience PDF and README build instructions are synchronized;
the English report now uses LuaLaTeX in place of its historical pdfLaTeX build.
Verification was limited to existing aggregates and document consistency. No
raw-event access, scientific run, new error estimate, external-reference audit
or change in scientific qualification occurred.
