# Codex account migration handoff

> Status snapshot: 2026-08-12 after completion of the version 1.2 DropTop4 +
> mass-bin iterative reweighting study. Its real terminal is
> `no_eligible_iteration`, `selected_iteration` is null, and `test_opened` is
> false; held-out MC test and periodA remain sealed. No implementation task is
> currently in progress.

## Start here on the other Codex account

Open this same local workspace on the same Mac:

`/Users/xuhongyi/Documents/research/higgs-xgboost-demo`

Paste the following prompt into the new Codex task:

```text
Continue the ATLAS Open Data H→ZZ*→4l MC methodology project in
/Users/xuhongyi/Documents/research/higgs-xgboost-demo.

First read, in order:
1. CODEX_ACCOUNT_MIGRATION_HANDOFF.md
2. AGENTS.md
3. docs/superpowers/specs/2026-08-11-dsid-363490-training-design.md
4. docs/superpowers/plans/2026-08-11-dsid-363490-training.md
5. docs/superpowers/specs/2026-08-11-mass-sculpting-warning-design.md
6. docs/superpowers/plans/2026-08-11-mass-sculpting-warning.md
7. docs/superpowers/specs/2026-08-11-mass-sculpting-ablation-design.md
8. docs/superpowers/plans/2026-08-11-mass-sculpting-ablation.md
9. /Users/xuhongyi/Documents/research/.superpowers/sdd/2026-08-11-dsid-363490-training/progress.md
10. docs/superpowers/specs/2026-08-11-mass-bin-iterative-reweighting-design.md
11. docs/superpowers/plans/2026-08-11-mass-bin-iterative-reweighting.md
12. /Users/xuhongyi/Documents/research/.superpowers/sdd/2026-08-11-mass-bin-iterative-reweighting/task-6-report.md
13. docs/superpowers/specs/2026-08-12-drop-top4-mass-bin-reweighting-design.md
14. docs/superpowers/plans/2026-08-12-drop-top4-mass-bin-reweighting.md
15. /Users/xuhongyi/Documents/research/.superpowers/sdd/2026-08-12-drop-top4-mass-bin-reweighting/task-7-report.md

Then verify the current filesystem state and latest SDD reports before taking
any action. Do not trust chat history over files. Continue from the first
unfinished, reviewed plan task. Use strict TDD, fresh output paths, immutable
run artifacts, and independent review. Do not use DSID 700600 for the 1.0
runtime, do not inspect/score real data, do not include m4l as a feature, do not
lower selection or mass-sculpting thresholds after seeing results, and do not
perform Git writes because this project is wholly untracked inside its parent
repository. Explain results to the user in physics-first Chinese.
```

## Research objective

Build a reproducible ATLAS Open Data MC-only H→ZZ*→4l methodology in which:

- physics selection is explicit and source-backed;
- XGBoost separates Higgs MC from continuum ZZ MC without using `m4l`;
- the Higgs MC distribution shows the expected concentration near 125 GeV;
- selected ZZ remains sufficiently mass-shape stable to support an honest
  background interpretation;
- every input, split, weight, model, plot, and terminal artifact is auditable.

Version 1.0 is an MC methodology result, not a real-data Higgs discovery.  Real
data and the 120–130 GeV data signal region remain sealed.

## Non-negotiable physics and scope rules

- Primary background: official ATLAS Open Data DSID 363490 `llll` ZZ MC.
- DSID 700600 is optional legacy code only; do not spend 1.0 runtime on it.
- Never add `m4l` to the model features.
- Never inspect or score real data in the signal region.
- Use absolute physical weights for training/evaluation shapes and signed
  weights only for physical-yield reporting.
- Development folds select models and freeze working points.  Test is opened
  only after selection and cannot change it.
- Do not dynamically loosen selection, AUC floors, or KS limits after viewing
  outcomes.
- Do not apply an unrecorded 1.3 ggZZ factor.

## Official DSID 363490 input

- CERN record: `https://opendata.cern.ch/record/15005`
- Direct file: `https://opendata.cern.ch/record/15005/files/mc_363490.llll.4lep.root`
- Local file: `data/raw/zz_363490.root`
- Size: 179,082,866 bytes
- SHA-256: `76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07`
- Normalization: cross section 1.2564 pb, k-factor 1, filter efficiency 1,
  sum of weights 7,538,705.808.

## Completed physical selection

The enhanced four-lepton selection includes trigger, trigger matching, Tight
identification, track/calo isolation, electron/muon impact-parameter cuts,
`|z0 sin(theta)| < 0.5 mm`, ordered lepton-pT thresholds 20/15/10/7 GeV,
electron `|eta| < 2.47`, muon `|eta| < 2.7`, zero total charge, SFOS pairing,
all-SFOS mass above 5 GeV, `50 < mZ1 < 106 GeV`, `12 < mZ2 < 115 GeV`, and
`105 < m4l < 160 GeV`.

The corrected r2 baseline selected 11,976 DSID 363490 events, split as
7,174 train, 2,429 validation, and 2,373 test.  This is 25.4 times the old
700600 count of 471.

## Immutable successful runs

- Baseline: `runs/full-baseline-363490-2026-08-11-r2`
- Training: `runs/full-training-363490-2026-08-11-r2`

Training result:

- selected model candidate `depth4_child20`;
- final tree count 998;
- weighted OOF AUC 0.885296;
- weighted test AUC 0.894054;
- loose/medium/tight thresholds 0.256185501814, 0.631632328033,
  and 0.782604217529;
- Higgs MC has a visible narrow concentration near 125 GeV.

Do not edit, reuse, delete, or republish these directories.

## Critical current scientific result

The same classifier strongly sculpts ZZ mass despite excluding `m4l`:

- OOF loose/medium/tight KS: 0.291194 / 0.408339 / 0.457954;
- test loose/medium/tight KS: 0.323940 / 0.431848 / 0.473386;
- OOF/test weighted score–mass correlations: about -0.634 / -0.638.

The historical `mass_sculpting.warning=false` is a confirmed software defect,
not evidence of shape stability.  A TDD correction makes every finite KS value
strictly above the configured 0.10 limit produce a deterministic warning.

The feature diagnostic found the strongest test-ZZ correlations with `m4l` in
`lep3_pt` (0.486), `lep4_pt` (0.393), `mZ2` (0.383), and `mZ1` (0.240).
`deltaPhi_ZZ`, `mZ1`, `mZ2`, and `lep3_pt` have the largest gain importance.

Technical report:
`docs/reports/dsid363490-sculpting-diagnostic/report.html`

## Historical version 1.0 implementation direction

The then-approved sealed feature-ablation study used three profiles:

- `drop_top4_mass_proxies`;
- `shape8`;
- `angular_eta7`.

Eligibility is fixed before running:

- all OOF ZZ working-point KS distances ≤ 0.10;
- weighted OOF AUC ≥ 0.80;
- signal efficiency strictly greater than target ZZ efficiency at every point.

If no profile qualifies, publish `no_eligible_profile` and do not open test.
If one qualifies, choose using OOF only, then fit/score test once.  Never add a
candidate or relax a threshold after seeing results.

This ablation is complete and frozen; it is not the current next study and must
not be rerun. Its `no_eligible_profile` terminal left the held-out test sealed.

### Completed ablation foundations

Task 8A is independently approved.  CV, final fit, and scoring accept a
validated explicit ordered feature tuple; invalid/forbidden tuples reject
before factory invocation; the old CLI keeps the default 14 features.  Its
full suite passed 489 tests, and r2 hashes stayed unchanged.

Task 8B's profile definitions, development OOF metrics, exact loose/medium/tight
map gate, eligibility boundaries, and tie-breaking are implemented and tested.
The latest full suite passed 503 tests.  Three certificate-based attempts to
prove that a caller-supplied selected result was genuine were deliberately
rejected after independent adversarial review: Python module-private classes and
keys remain importable, so a certificate is not a trustworthy architecture.

### Historical version 1.0 continuation point

Task 8B, Task 8C, and the real Task 8D study are complete and independently
approved. The frozen real study is
`runs/mass-ablation-363490-2026-08-11`; its terminal result is
`no_eligible_profile`. The full-14 reference retained strong discrimination
(OOF AUC 0.885296) but strongly sculpted ZZ mass (maximum OOF KS 0.457954).
The three predeclared deletion profiles reduced mass dependence but none met
both fixed gates: AUC >= 0.80 and every working-point KS <= 0.10. Accordingly,
the held-out test remained unopened and no selected model or test artifact was
published. This is the honest version 1.0 MC methodology conclusion.

Task 8C's publication workflow is production-safe within its reviewed scope:
post-claim single MC parsing, development-only selection, exact conditional
allowlist, descriptor-owned no-clobber writes, failure terminal, and
manifest-last source/output hashes and row counts. The pre-run full suite was
535 passed. Independent final Task 8D review found no Critical/Important issue;
only the right-edge reference label in the trade-off PNG is slightly clipped.

### Completed version 1.1 mass-bin iterative reweighting study

The reviewed version 1.1 study is frozen at
`runs/mass-reweighting-363490-2026-08-11`. Its exact real terminal is
`no_eligible_iteration`. Six OOF iterations preserved weighted AUC from
0.885296 to 0.852398 and reduced loose/medium/tight ZZ KS distances from
0.291194/0.408339/0.457954 to 0.173197/0.214474/0.245835, but every KS value
remained above the fixed 0.10 gate. Test was not opened and no selected model,
test metrics, or prediction artifact exists. Same-path refusal and the frozen
r2/ablation/ROOT inventories were verified byte-identical. Independent review
found 0 Critical, 0 Important, and 0 Minor issues.

This is a useful negative result: fixed mass-bin training reweighting reduces
sculpting without satisfying the predeclared shape criterion. It does not
authorize periodA, and it must not be reinterpreted by lowering the gate,
changing bins, or adding iterations after seeing the outcome.

### Current next work after version 1.2

Do not rerun or modify the frozen r2 baseline/training, ablation, 1.1
reweighting, or 1.2 DropTop4-plus-reweighting runs. The current next work is a
separately reviewed, predeclared stronger MC-only decorrelation method, such as
a uBoost-style or adversarial objective. Retain the same frozen OOF AUC/KS gates
and one-time test-sealing rule. Held-out test and periodA remain sealed; any
real-data, sideband/control-region, systematic, or likelihood work requires a
separate blind protocol and is not authorized by this handoff.

### Completed version 1.2 DropTop4 + mass-bin iterative reweighting study

The final reviewed combination is frozen at
`runs/mass-reweighting-drop-top4-363490-2026-08-12`, with manifest SHA-256
`e41473e74cdf662d0d7e71ea753edc2a272f0d7526a429b4b354576e32d2d27e`.
It used the exact ten-feature profile obtained by dropping `lep3_pt`,
`lep4_pt`, `mZ1`, and `mZ2`, while retaining the predeclared bins, five
corrections, AUC >= 0.80 and all-working-point KS <= 0.10 gates.

Its terminal is exactly `no_eligible_iteration`; selected iteration is null and
test was not opened. The six development-OOF iterations have AUC
`0.7996529199780816`, `0.7909840349437066`, `0.7840745577657593`,
`0.7719399667136062`, `0.7634006325078653`, and `0.7588712973047708`.
The corresponding maximum ZZ KS values are `0.34469234042569663`,
`0.2563535629356366`, `0.1845589106499591`, `0.1297707080628676`,
`0.1169067754006049`, and `0.09720271279351`. At iteration 5 the loose,
medium, and tight KS values are all <= 0.10, but its AUC is below 0.80; no
iteration is eligible. The four-way comparison is Full14 `0.8852959102354316 /
0.4579540115915921`, DropTop4 without reweighting `0.7996529199780816 /
0.34469234042569663`, Full14 + reweighting iteration 5 `0.8523982143190011 /
0.24583464407366806`, and the new combination `0.7588712973047708 /
0.09720271279351` (OOF AUC / maximum OOF ZZ KS).

This shows a remaining decorrelation–discrimination trade-off, not a reason to
open test or periodA. One Task 6 procedural Minor is disclosed: a broad
immutability SHA-256 inventory byte-read frozen `data_events.csv.gz`. It was
not decompressed, parsed, displayed, plotted, used in training, or changed, and
has no scientific impact; future inventories must exclude that artifact.

Relevant review evidence:

- `task-8b-review.md`: incomplete working-point map finding;
- `task-8b-fix-1-review.md`: raw-result substitution finding;
- `task-8b-fix-2-review.md`: nested dataclass certificate replacement finding;
- `task-8b-fix-3-review.md`: module-private certificate construction finding
  and explicit requirement for architecture redesign.

## Durable evidence locations

- Main project plan: `docs/superpowers/plans/2026-08-11-dsid-363490-training.md`
- Main project checkpoint: `docs/superpowers/plans/2026-08-11-dsid-363490-training-report.md`
- Ablation design: `docs/superpowers/specs/2026-08-11-mass-sculpting-ablation-design.md`
- Ablation plan: `docs/superpowers/plans/2026-08-11-mass-sculpting-ablation.md`
- SDD ledger: `/Users/xuhongyi/Documents/research/.superpowers/sdd/2026-08-11-dsid-363490-training/progress.md`
- Task reports/reviews: the same SDD directory, named `task-*.md`.
- DropTop4 SDD ledger and final handoff:
  `/Users/xuhongyi/Documents/research/.superpowers/sdd/2026-08-12-drop-top4-mass-bin-reweighting/progress.md`
  and `task-7-report.md` in that directory.

## Migration procedure at the 7% boundary

Before stopping, the current Codex task must:

1. stop starting new tasks at 10% remaining context;
2. let the current safe test or computation boundary finish;
3. refresh this file's current status, exact test counts, changed-file hashes,
   active output paths, and next executable step;
4. run the narrowest safe verification appropriate to the current state;
5. record any background process PID/session without interrupting it;
6. confirm protected-run hashes or explicitly state which audit remains pending;
7. give the user the copy/paste prompt at the top of this file;
8. stop at or before 7% rather than beginning more work.
