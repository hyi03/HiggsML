# Independent-confirmation resource audit and primary comparison draft

## Record scope

Historical date: 2026-09-23. This record followed section 7 of the research-quality
solution confirmation, historically
`docs/4-Reviews/research-quality-audit-2026-09-23-review-confirm.md` (an ignored
local review, not distributed evidence). It was translated into English and
relocated on 2026-10-06 from `docs/changes/priority5-confirmation-design-20260923.md`.
The original remains in Git history before migration (HEAD
`e1448f3eb1b841b371d82b3ccfc1bc4f7f2bf160`).

**The visible-resource metadata audit and confirmation draft were completed.
test03 shared the archived test01 population, whose assessment/T2 access-budget
history was already recorded. No directly certifiable independent confirmation
resource was found. 2025 MC was only an audit candidate; new release/files/
directories did not establish confirmatory eligibility.**

This was preparatory work during F2. No event or new assessment result was opened,
no confirmation computation started, and access/claim/freeze/F2 budgets were not
changed. BC/AC choices were not retrospectively preregistered. The task did not
assess live F2 progress or whether to stop it. Later test05 numerical completion
is documented in [current results](../results-and-limitations.md); it does not
turn this proposal into a registration. The mass-off proposal here remains
separate from the [mass-on sample-efficiency study](../sample-efficiency.md).

Historical evidence was under ignored `var/priority45-audit-20260923-001/`, which
was not found in the migration workspace and is not bundled with Git. Source
paths/IDs and reported counts below were retained without opening payload or
repeating their verification.

## 1. Audit scope and evidence

Whitelisted scans covered only `.research-claims`, `.h4l-mass-off-v2-claims`,
`.h4l-mass-off-v3-claims`, `.h4l-population-access` under runs/ and
var/runs-test-01/, plus specified test03/old1 prepare/freeze/access and 2020/2025
download receipts. They did not cover all disks, remote/deleted history, event,
Toy or assessment payloads.
`local-metadata/` held 71 copies; `local-metadata/receipts.json` mapped originals,
copies, sizes/hashes. `audit-findings.json` held machine-readable extracts.
File presence or self-review's validated label did not replace history review.

## 2. Established same-population history

Both prepare manifests and source-access receipts bound:

```text
population_id = 1059f531f6da7dd2aaae9ef4956c6f2a6465fbf1f5e1254bb0ee81b08fd42e00
```

| Binding | Archived test01 old1 | Then-current test03 |
|---|---|---|
| prepared artifact | `8c295b2881a808262e43300687b49d8f4c8cfde08c09cb54584c61a1e6c9d4da` | `9cddd2daab32c8554769dd8ff860aa5166dbc085430995b95253634388704f63` |
| freeze artifact | `01e623db2028849e7751c6c83c8811864833acd141be7eb521f0a773fbbd6a17` | `17f31e46fe7b39a177b74a5a37563f9c14201728ebed26638f0ec87b35673a65` |
| source receipt independent | false | false |
| history_review | self_reviewed_unused_assessment_population | self_reviewed_unused_assessment_population |
| conclusion scope | exploratory / self-reviewed | exploratory / self-reviewed |

The archived snapshot contained 15 assessment, 5 T2 and 30 model-self claims;
population-access also bound that population to old freeze. The current snapshot
contained 7 model-self claims. Claims mean budget/access history, not completed
calculations; counts cannot infer live progress.
New unused self-review wording did not override archived same-population claims.
Until cross-root history and confirmation-group isolation from prior feedback were
established, unused confirmation could not be certified. New prepared/freeze IDs
or roles do not erase population selection history.

At audit time, graph-located marginal_workflow.py source_history(prepared) used
prepared.path.parents[1] as one root, scanned four directories for population/
prepared and skipped model-self. It was not global history; relocating archives
outside that root exposed a scope gap. The audit did not test bypass with new
assessment or change access code. It proposed explicit relocated/missing/conflicting/
unknown history with paths/hashes and separate synthetic metadata guard work,
without changing F2 mid-execution.
That diagnosis is historical: later entry hardening added declared-root checks,
recorded in [entry-hardening history](../history/h4l-entry-hardening-20260924.md).
The [current guide](../implementation-and-reproduction.md#cross-root-history-and-completion-states)
defines present scope; it still does not prove absence of access elsewhere.

## 3. Resource inventory and recommended order

| Resource | Evidence at audit time | Qualification | Next step |
|---|---|---|---|
| test03 development/assessment population | Same population as old1; archived claims | Not new independent confirmation | Retain exploratory/conditional scope and history |
| Outer 2020 nominal holdout | Difference of source/development entries | Unused status/usable size unproven | Audit access, groups/cross-file identity and basket interpretation before scoring |
| Downloaded 2025 exactly4lep | Complete receipt; two files match official metadata | Candidate only; bytes are not independence/applicability | Campaign, identity/history audit, then define transfer or same-distribution target |
| New research-grade independent MC | No bound ready resource found | Preferred addition, not available evidence | Freeze processes/generation/simulation/independent seeds/history and archive separately |
| New training seeds/splits/bootstrap/Toys | Conditional stability/randomness | No new independent physical population | Do not use to remove selection bias |

### 3.1 Outer-holdout counts are not eligible selected-event counts

Prepare metadata gave signal source/development 164,716/131,776 and background
554,279/443,408: differences 32,940 and 110,871. These were pre-final-selection
entry differences, not selected groups, signed N_eff or certified unused events.
Review should establish whether old scripts interpreted adjacent heldout ROOT
branches within baskets and whether values informed selection. Reading compressed
baskets, branch interpretation and analytic use differ; neither blanket contamination
nor untouched status from target spans alone was justified. Eligibility remained
unproven and was not resolved by opening holdout results.

### 3.2 Special limitations of the 2025 resource

The receipt recorded `status=complete`, `validation_scope=file_bytes_only`,
validated on 2026-09-07:

| Role | DSID | Contract entries | Process cue in filename |
|---|---:|---:|---|
| signal | 345060 | 419,943 | PowhegPythia8EvtGen_NNLOPS_nnlo_30_ggH125_ZZ4l |
| background | 700600 | 11,260 | Sh_2212_llll |

Names were clues, not generation cards/independence proof. Signal DSID matched
2020, background differed; neither agreement nor difference proves overlap or
group independence. Collection-level Release 22 reprocessing/new-MC descriptions
still needed member-level campaign/lineage.
The 2025 skim was exactly four pT>=7 GeV leptons, versus 2020's at-least-four loose
selection. New detector/generator/skim changes target distribution. Even disjoint
events may test transfer rather than same-distribution confirmation. 2025 science
normalization constants were null and planned factorized event fields were not
read or validated.
Order: verify research purpose/production -> cross-release identity, duplicates
and history -> controlled identity audit and unused-resource isolation -> prepare/
score. A pool used for weights/grids/tuning becomes development and needs separate
confirmation. Do not mix 2020/2025 training to obscure unknown equivalence.

## 4. Single primary comparison: compact-input noninferiority draft

Historical `confirmation-design.draft.json` was `draft_not_registered`,
`executable=false`, outside production schemas and not executable input.
Missing identities, interval method, scientific tolerance and budgets remained
null rather than invented.

| Item | Draft choice | Required before registration |
|---|---|---|
| Question | Under the same mass shape and qualified coverage, is BC no worse than ABCD beyond a justified tolerance? | Claim and input applicability |
| Candidates | BC sole primary compact candidate; ABCD reference; AC exploratory | Acknowledge old exploration; freeze checkpoints/protocol hashes |
| Information/baseline | Both explicit mass-off, with the same B0 mass likelihood from the physics audit | Grid/category support/nuisance/correction sources |
| Primary estimand | Fixed-network performance; proposed equal mean over seeds 42--46 | Exact five model sets; no best-seed selection on confirmation |
| Primary point | mu=1 and one explicit nominal nuisance point | Nuisance/target distribution; other points diagnostic |
| Precision | Expected full observed interval length E[U-L] | Validated interval construction and finite expectation |
| Effect | D=mean_seed(E[length_BC]-E[length_ABCD]); lower is better | Which MC/template/training variation is included or conditioned on |
| Null | H0: D>=delta; valid one-sided upper limit strictly below delta supports noninferiority | Purpose/cost-based delta, not fitted to the inspected roughly 1.3% advantage |
| Comparison error/power | Proposed one-sided alpha=0.025, power=0.90 | Final values/model/design effect/budget |
| Reliability | Per-scenario coverage/failure/unbounded rules first | Freeze acceptance tolerance/confidence-bound rule; nominal 68% alone insufficient |

68% signal-strength interval confidence and alpha=0.025 comparison error are
distinct. Old noninteger-Asimov W68 is not renamed calibrated precision for a
discrete belt. Full U-L and historical W68 definitions must remain explicit;
old numbers remain unchanged.
One primary contrast avoids reselecting among 105 pairs. Promoting AC/others needs
an advance hypothesis-family/multiplicity rule such as Holm. Noninferiority is
not superiority; meaningful improvement needs predeclared effect/error rules,
without result-driven target switching.
Fixed-network scope covers these models/target only. Learning-procedure or
sample-efficiency claims need independent outer training resources, retraining
and complete selection. The existing mass-on sample-efficiency protocol cannot
directly accept off-only BC.

## 5. Uncertainty, physical pairing and failures

Five seeds share MC; they are not independent physical samples. For fixed model
sets, average equally within each physical outer repeat, then estimate uncertainty
over independent outer units. Report training variation separately; seed standard
error does not replace MC uncertainty.
Specify fixed-template conditional expectation versus finite-calibration/template
procedure expectation. The latter regenerates roles, reselects and rebuilds each
outer; inner Toys are not independent MC batches. One-pool group bootstrap gives
assumption-conditional uncertainty, not independent physical populations, and
needs the [statistical-validation benchmark](statistical-validation-20260923.md).

Authorized common physical groups can preserve group-level correlation. A joint
classification Toy requires nonnegative per-process joint cells, reproduced
marginals and valid dependence. Signed marginal support does not prove joint
support; no clipping/absolute weights. Artificial CRN is numerical integration
coupling, not physical pairing. If joint modeling fails, pre-register independent
marginal integration, separately handling shared-template estimation correlation
and limiting claims.

Record all planned support/fit/unbounded/search-truncation/valid units. Report
conditional coverage and planned-denominator success-and-coverage separately.
Unbounded intervals can make expected length infinite; no deletion/arbitrary cap
to obtain favorable means. Undefined failure handling or unestimable metrics mean
unable to confirm, without replacement draws or switching to medians afterward.

## 6. Power and budget planning

Separate development estimates outer-difference variance, support failures, cost
and tails from confirmation resources/streams/budget. For finite-variance independent
outer differences, an approximate planning expression is:

```text
N_outer ~= (z_(1-alpha) + z_power)^2 * Var(D_outer) / (delta - D_design)^2
```

D_design<delta needs advance justification, not the old winner's advantage.
This is cost planning, not guaranteed discrete/boundary/failure-aware inference.
Validate comparison error/power in independent synthetic generators; distinguish
outer MC, inner integration and coverage-validation budgets.
Delta, independent resource size, interval/comparison method and variance were
undefined, so no formal Toy count was invented. Freeze budgets/failure stops/
streams/sequential rules before confirmation values. Fixed budget is the default;
no extension based on significance.

## 7. Prerequisites, execution order and F2's role

| Gate | Audit-time status | Required artifact |
|---|---|---|
| G1: sources and research scope | Incomplete | Purpose/process/weights conclusions from physics audit |
| G2: independent resources/history | Unproven | Current/archive history, group identity and unused scope |
| G3: interval/selector reliability | Incomplete | Numerical contract/domain/coverage/failure criteria and independent evidence |
| G4: common mass shape/fair baseline | Feasibility not run | Per-bin support/grid/model bindings; MELA scope if used |
| G5: primary contrast/error budgets | Non-executable draft | Justified delta/estimand/method/power/budget/RNG/bindings |

Order: G1/G2 sources/identity -> independent development and G3/G4 validation ->
G5 registration -> confirmation access/fixed execution -> complete report.
Without qualified independent resources, retain exploratory finite-MC stability/
scope findings rather than manufacture confirmation.
After F2 publication, support/coverage/failure/threshold-frequency/lineage could
inform cost and gaps. F2 completion does not pass G1--G5 or restore independence
of a development-feedback population. This draft did not use new F2 values to
choose delta, candidate, grid or acceptance criteria.

## 8. Historical acceptance

Delivered resource inventory, same-population archival evidence, scan boundaries,
one primary draft, statistical/budget gaps and prerequisites. Preparatory audit/
design completed; formal confirmation did not start. It shared verification.json
with the [physics-baseline audit](physics-baseline-audit-20260923.md), checking
saved evidence/documents/work preservation. No full suite, full-MC comparison or
formal test ran, and no scientific qualification was granted.
