---
change_id: h4l-off-joint-support-v1
status: approved
source: User selection of a formal joint-support design; the new 200 development replicas are method-selection evidence, not the scope of subsequent analysis
updated_at: 2026-09-22T18:02:18+08:00
---

# H4l off-only joint-support threshold selection

## Record scope and subsequent changes

This is the approved design dated 2026-09-22, translated into English and relocated
on 2026-10-06 from `docs/changes/h4l-off-joint-support-v1/spec.md`.
The original remains in Git history before this migration (HEAD
`e1448f3eb1b841b371d82b3ccfc1bc4f7f2bf160`). The median defaults, implementation
authorization and unexecuted analysis statements below describe that design stage.
Commit `03ea1b4` later made joint support the full wrapper's default; direct
off-only execution and attribution registration retain median defaults.
Use [current methods](../methods-and-evaluation.md) and
[reproduction instructions](../implementation-and-reproduction.md) for current
behavior. Implementation and plan history are in the
[verification record](../history/h4l-off-joint-support-v1-verification-20260922.md);
the later selected test05 result is in [results and limitations](../results-and-limitations.md#h4l-off-test05-controlled-mc-result).
This migration neither changes the bound method contract nor supplies scientific
validation. Local development evidence under `var/` is not bundled with Git and
was not found or revalidated in the migration workspace.

## Problem and outcome

The existing off-only procedure divides scores into two categories at the
calibration background's physical-yield median. Nominal templates can pass while
independent resampling of calibration/template physical groups makes one side's
signed effective count fall below 20. The failure is insufficient template support
and calibration-threshold variation, rather than a computation interruption.

The design defines one threshold-selection procedure for every nonempty coalition,
constraining both calibration and template support. It retains five seeds, 16
coalitions, two categories and the attribution estimands. An infeasible split is
reported as a failure; success for every future replica is not guaranteed.

**The user's clarification takes precedence: the newly generated 200 development
replicas are only evidence for selecting this method. They are not the subsequent
analysis dataset, the formal bootstrap replica set, the entire analysis budget,
or a replacement for nominal analysis, Toys, T2 or assessment.**

The design was initially prepared for approval, not as an already approved
implementation plan. The inspected code HEAD was
`cd8cd69db45b831c6ddee2193177fb0f8473fc12`; pre-existing staged or unstaged user
work in AGENTS.md and paper/ was outside its scope. The approval at the end records
the subsequent implementation authorization.

## Affected users and systems

- Researchers performing complete controlled-MC H4l off-only analysis.
- Threshold generation, nominal templates, freeze, MC bootstrap, T2, Toy input
  mappings and aggregate reports.
- Method configuration, threshold schemas, analysis identity, source-reuse audit,
  evaluation budgets and existing access history.
- Existing marginal-CRN laws and interpretation are retained; coupling is not
  redesigned by this change.

## Scope

1. Use the existing controlled-MC parent and original role assignment. Every event
   satisfying registered selections participates in its role; the development
   replicas are not used to select favorable events.
2. Retain 75 frozen off models, five deterministic M0off identities, seeds 42--46
   and all 16 coalitions. Model reuse must pass core-protocol and lineage checks.
3. Introduce the `h4l-off-joint-support-v1` method contract. Nominal analysis, each
   MC bootstrap replica and each T2 outer use the same selector.
4. Fix the common mass grid to [105,140], with two score categories and the
   original physical selection. Do not search the grid using nominal results.
5. Retain nominal Asimov, Shapley, 24 conditional interactions, 105 nonempty-subset
   contrasts, five-seed stability, MC bootstrap, model-self, assessment and T2 as
   distinct evidence layers.
6. The population has already informed exploration and method selection. Preserve
   exploratory qualification. Assessment remains subject to access/history audit;
   a new method identity does not authorize access.

## Non-goals

- No new MC, network retraining, feature-group changes or role-fraction changes.
- No reduced support thresholds, absolute-weight substitute for signed yields,
  or deletion of the low-score category.
- No W68/AUC/Shapley-optimal threshold search or special treatment of D-only/AC.
- No exact-score-boundary scan as a fallback after failure.
- No promotion of development pass rates, old outputs or old review labels into
  formal evidence for the new analysis.
- No old-run, report or paper-number changes. Implementation was authorized;
  formal evaluation and code commits were outside that authorization.

## Requirements and design

### Method-selection evidence

The primary evidence was the `fresh` cohort in the historical feasibility report
`var/h4l-support-feasibility-20260922-001/report.md`: seed 20260922, 200 independent
role-group resamples. A replica passed only if all 80 candidates met support.

| Rule | Complete passes in the new 200 development replicas |
|---|---:|
| Original background median | 149 |
| Calibration-only support constraint | 154 |
| Calibration + template joint support | 200 |

All 75 nominal nonempty thresholds remained medians. Of the new 15,000 nonempty
candidate/replica cells, 131 selected a different quantile, mainly 55% or 60%.
These observations motivated the rule; they are not a per-candidate threshold
lookup table. The historical 200 replicas supported failure reconstruction and
numerical checks, and were not combined with the fresh cohort as 400 independent
confirmations. Fresh resampling of the same empirical MC is not new independent
physical events.

The original study checked the full `output-sha256.json`. Missing evidence must
not be fabricated or replaced by new draws presented as the original evidence.
Key bindings, with paths relative to the feasibility directory, are:

| File | SHA-256 |
|---|---|
| `plan.json` | `873b20a08c6699092ee32f9d706d53c876345e8cec113d5670152ecc6db1ffbf` |
| `summary.json` | `2b4d4dbe8d043cbe20d7760d0f9a256c0ccaa31ca2a22f7e50a8e9c7e7bea84f` |
| `group_draws.npz` | `4ff437c280c9849ae0e04ce5fb6fa0ab0d32083ee360062cf78b9988f621741a` |
| `candidate_draws.csv` | `e2535049cb367f0a18ec69a8a1396b1f0daa87ebf488ff793f686a0e5a80f730` |
| `provenance.json` | `1d92db1c8343e346524e76e79868ec5c8de49ad901843b5118116702bc570131` |

NPZ row 0 contains nominal multiplicities; rows 1--200 contain historical
replicas. The fresh cohort is strictly rows 201--400, corresponding to fresh
replicas 0--199. The whole NPZ must not become a formal draw plan.

### Estimands and data responsibilities

Each candidate follows: fixed network -> calibration-background threshold
candidates -> joint calibration/template support selection -> classification
using that threshold -> signed template -> T1 Asimov W68.
Keep `v(S)=-W68(S)`, computing a full attribution vector per seed before
five-seed aggregation. The threshold is now `t=T(C,T)`. Bootstrap estimates
finite calibration/template variation of this joint selector, rather than an
omitted uncertainty of the old median procedure.

| Role/source | Responsibility and boundary |
|---|---|
| train / validation | Preserve frozen models and their selection history; no new threshold search |
| calibration background | Generate quantile candidates using signed physical_weight |
| calibration signal/background | Check two-sided process support using physical_weight |
| template signal/background | Check support and build templates using yield_weight; explicitly participate in threshold selection |
| assessment | No threshold generation, support-based selection or fallback; authorized access consumes the fixed mapping |
| development replicas | Method-selection evidence and implementation replay, not the formal analysis parent |

Roles and groups are not reassigned. Template participation is an explicit part
of the new procedure and does not provide independent validation.

### Deterministic threshold rule

For every nonempty coalition, seed and selector invocation:

1. Validate raw model, dataset, roles, groups, weights, fixed mass support and input
   identities. Scores must be finite and within registered score_edges.
2. Construct the calibration-background distribution using original score_edges,
   group variance and the original nonnegative fixed-total projection. Retain
   whole-sample support requirements and rejection of unvalidated same-group
   cross-score-bin correlations. Projection is not binwise clipping.
3. Fix `q=k/20`, `k=1,...,19`. Compute thresholds by original CDF linear within-bin
   interpolation. Do not substitute empirical absolute-weight quantiles.
   Cross-implementation tolerances check consistency, not support eligibility.
4. Assign `score < threshold` low and `score >= threshold` high. Equal scores
   remain together. Duplicate thresholds may remain, with q and support checks
   fully traceable.
5. For each C/T role, process and category, compute signed yield, group variance,
   event-level absolute-weight sum, group occupancy, rho and neff. Sum multiple
   rows within a physical group before squaring; every bootstrap copy has its
   own replica identity.
6. A cut is feasible only when every role/process/category has occupancy,
   positive yield and variance, `rho >= 0.2`, and `neff_signed >= 20`. Empty bins
   are not automatically structural zeros. Missing whole signal/background
   support also fails.
7. Minimize the integer key `(|k-10|,k)` over feasible cuts: nearest the median,
   with lower q on a tie. Avoid floating-point distance tie-breaking. Role weight
   normalizations may differ, but physical weights and role sampling laws do not.
8. If all 19 cuts fail, publish `no_feasible_joint_threshold`. No extra draws,
   extra candidates, relaxed thresholds, nominal fallback or single-category
   fallback are permitted.

For role R, process p and category b, let `W_g=sum_{i in g,p,b} w_i`:

```text
y = sum_g W_g
variance = sum_g W_g^2
sum_abs_weight = sum_i |w_i|
rho = |y| / sum_abs_weight
neff_signed = y^2 / variance
```

With multiplicity m_g, every copy contains the complete group and variance
contributes `m_g * W_g^2`, not `(m_g * W_g)^2`.
Use the actual process column. Only its absence permits the legacy label fallback,
recorded as `process_identity_source=label_legacy`; this does not independently
qualify physical-process support. Different role process/signal identity sets fail.

M0off retains constant score 0.5, threshold 0.5, low-category structural-zero
evidence and likelihood-equivalence checks. It bypasses the 19-cut search and need
not have two occupied categories. Its effective template category must still meet
the original support thresholds.

### Nominal analysis, gates and freeze

Rebuild nominal templates, G1, J0/J1 and identities for the new method after all
candidate selections. Any infeasible candidate stops execution with retained
scientific failure evidence. J0/J1 retain their responsibilities and budgets;
they do not become threshold-reselection loops, and Bernoulli-thinning J1 is not
a bootstrap check.

Development bindings and replay are development verification. The inspected
200/200 does not establish independent pre-freeze qualification. New analysis
must pass its own nominal support, existing G1/J0/J1 and binding/review gates.
Even if every nominal threshold equals its old median, publish a new nominal
artifact with all 19 selection reasons. The old marginal nominal adapter only
checks compatibility; it cannot relabel old templates as new-method output.

Dependency order is: source-reuse audit -> method registration -> new nominal
and selection records -> G1/J0/J1 -> evaluation specification -> freeze ->
Asimov/complete evaluation plan. Keep publication dependencies acyclic. Freeze
binds method/selection records; the later plan binds freeze without modifying it.

### Complete analysis budgets and streams

Initial new-method budgets come from the existing study protocol, not the
development cohort size. "Formal" means execution under the new contract, not
independent confirmation or primary-claim eligibility.

| Stage | Scope |
|---|---|
| nominal / Asimov | Complete relevant MC roles, 80 candidates, full attribution, ranking, interactions and contrasts |
| MC bootstrap | 200 newly registered complete role-group draws; joint reselection, templates, inference and attribution per draw |
| model-self | mu=0,1,2 x five seeds; 500 Toys per candidate/cell |
| assessment | Same matrix, subject to separate access/history/budget review; truthfully not_run if inaccessible |
| T2 | mu=1 x five seeds; 20 calibration outer x 100 inner Toys per seed |
| training-seed stability | Five seeds and all 3125 ordered seed vectors; do not add to event-MC intervals |

Development, formal bootstrap, model-self, assessment and T2 outer/inner streams
have separate stage namespaces. Do not import development seed/counts or reuse
old formal bootstrap draw vectors. Formal MC bootstrap retains base_seed 42001
with a new deterministic RNG identity:

```text
payload = canonical_json([
  "h4l-off-joint-support-rng-v1", analysis_contract_digest,
  "mc_bootstrap", 42001, replica_index, role
])
seed_integer = int.from_bytes(SHA256(UTF8(payload)), "big")
rng = numpy.random.Generator(numpy.random.PCG64(seed_integer))
counts = rng.multinomial(n_groups, [1/n_groups] * n_groups)
```

Sort group identities as strings. Calibration/template role draws are independent;
all candidates share a role's counts within a replica. Record NumPy version,
ordered-group digest and counts digest. Scheduling does not enter RNG identity;
the analysis digest excludes directories, timestamps and results.
Toy/T2 retain stage, mu, seed-block, outer, process, mass-bin and auxiliary
substreams, adding analysis_contract_digest at the root without changing common
total/allocation CRN semantics. Equal Toy indexes across training seeds are not
physical pairing. Budget changes require an explicit new contract revision;
never draw until 200 successful replicas are obtained.

### Reselection semantics by layer

**MC bootstrap:** resample C/T physical groups independently; run `T(C*,T*)`, build
templates on T* and execute T1/full attribution. Complete success requires all 80
selectors, templates, fits and attribution outputs; support alone is insufficient.
Only 200 complete replicas permit 16/84 and 2.5/97.5 percentiles. Any failure makes
formal intervals null; successful replicas provide conditional diagnostics only.

**Model-self / assessment:** use frozen joint nominal thresholds, with no Toy- or
assessment-occupancy reselection. Zero Poisson observations are not MC support
failure. Parent support failure is reported without changing thresholds.

**T2:** retain calibration-only outer resampling with fixed template:
`T(C*,T_nominal)`. Apply that outer threshold to both fixed template and evaluation
parent/pseudo-event mappings. Preflight all outer selections/support before inner
Toys; failed outer records retain planned inner budgets without replacement.
Label the scope
`calibration_variation_conditional_on_fixed_template_joint_selector`.
It is not joint calibration/template full-procedure coverage. Resampling both
roles in T2 would change its estimand and requires a separate study.

### Inference and report qualification

Retain signed templates and pyhf shapesys approximation to avoid changing both
selector and likelihood at once. Old fixed-bin T1 reference evidence does not
automatically validate coverage after template-assisted selection.
Exploratory W68, attribution and complete-replica bootstrap percentiles may be
reported, with `selection_aware_coverage=unvalidated`,
`registration_status=exploratory_posthoc`, and `primary_claim_eligible=false`.
Percentile spread is not calibrated total confidence coverage.
Report execution, support, complete bootstrap, conditional Toy closure, conditional
T2 variation, access review and scientific qualification separately. Complete
execution may coexist with unvalidated qualification.

## Interfaces and data

### Method configuration and entry points

Add `config/protocols/h4l_off_joint_support_v1.json` separately from old core
snapshots. Bind method_id, 19 integer quantile numerators/denominator 20, ordering,
role weights, thresholds, mass grid, failure policy and RNG policy.
Canonical analysis_contract_digest covers core-protocol digest, method configuration,
candidate definition, marginal pairing contract, budgets and RNG policy.
Propagate source core-protocol and analysis-contract digests separately; unchanged
core protocol does not mean unchanged analysis.

Provide explicit `--threshold-method joint-support-v1`, propagated by wrappers
and direct attribution entry points to domain services. The approved design
retained then-existing median-v1 defaults; conflicting flags/configuration fail
rather than silently override. This flag does not restore the removed
evaluation-version selector.

### Domain interface

```text
select_joint_threshold(
  calibration_frame, calibration_scores,
  template_frame, template_scores,
  core_protocol, method_contract,
  model_identity, input_bindings, draw_identity
) -> joint_threshold_record
```

Reuse GroupBinStatistics/template grouped moments and calibration projection
semantics. Scientific selection stays out of CLI. Preserve old fit_thresholds;
do not globally replace it in other workflows.
New `h4l-joint-support-threshold-v1` records contain at least:

- method_id, analysis_contract_digest, model_id, raw mapping_id, candidate key, seed;
- source_role=`calibration_template_joint`, role population/prepared/source bindings,
  draw identity and multiplicity digests;
- calibration projection diagnostics; all 19 q/thresholds and role/process/category
  yield, variance, absolute sum, occupancy, rho, neff, support status and reasons;
- selected_quantile_numerator, selected_threshold, deterministic selection reason
  and score-tie rule;
- status, reason, record digest and threshold_id; undefined quantities are null,
  not NaN/Inf.

Cache immutable predictions/statistical preparation only, never selection results
across draws. Raw mapping_id may retain network identity, but threshold/freeze/
evaluation identities bind the full new record, not just the threshold float.
M0off records `selector_bypassed=registered_constant_baseline` and structural-zero
evidence. Candidate keys may persist across methods; artifacts, thresholds,
freezes, plans and report cohorts must not mix.

### Integration boundaries

| Boundary | Requirement |
|---|---|
| modeling/calibration.py, inference/statistics.py, templates.py | Share projection/group statistics; old median interface unchanged |
| attribution_workflow.py, marginal_workflow.py | Rebuild nominal, not only adapt old source-nominal; audit model reuse/method identity |
| inference/bootstrap.py | New method invokes joint selector; old median remains replayable |
| inference/assessment.py | T2 outer reselection and mapping synchronization; ordinary Toy/assessment thresholds are not refitted |
| marginal support/coupling/evaluation-state | Retain support/access responsibilities; bind analysis contract and reject cross-method reuse |
| schemas, reports, runbook | Selection records, qualification, budgets/RNG isolation and exploratory scope |

The implementation plan determines complete schemas, flag propagation and test
files. This boundary summary does not waive binding checks.

## Failure, recovery and compatibility

| Condition | Required behavior |
|---|---|
| Input/core-protocol/role/process mismatch or cross-method cache | Hard binding error; no valid computation/publication |
| Calibration projection or unvalidated group correlation failure | Retain original scientific reason; no fallback selector |
| No feasible joint cut | no_feasible_joint_threshold; retain all 19 diagnostics |
| Any nominal candidate failure | No freeze; retain fresh-root failure evidence |
| Any formal bootstrap candidate/fit failure | Retain replica; bootstrap_incomplete and formal intervals null |
| T2 outer/parent support failure | Stop under existing preflight/budget rules; retain outer/planned inner budget |
| Ineligible assessment access | not_run/pending; no --force or new-directory bypass |
| Same-identity interruption | Existing resume/retry contract only; no replacement of scientific failures |

Use a fresh root. Never overwrite old h4l-off-test01, development evidence or any
complete/failed artifact. Audited old data may be upstream; old thresholds,
templates and reports cannot be relabelled. Population history applies across
analysis names/contracts. Original explicit selection did not change defaults;
later default changes were separate decisions. Analysis scope and actual stage
authorization must be expressed separately.

## Policy and architecture constraints

- MC-only, with no real data; no ATLAS/CMS result, discovery or measurement claim.
- Physical selection, signed yield, group integrity and off classifier inputs
  unchanged; likelihood retains a mass coordinate.
- No assessment-, ranking-, W68- or attribution-driven method adjustment. Record
  the exploration that motivated the current method.
- No generated data/models/runs/caches/development draws committed. Historical
  hashes/paths do not guarantee cross-machine evidence availability.
- Scientific rules stay in domain services/versioned contracts; no unrelated refactor.

## Risks and concerns

1. Selection-aware coverage is unvalidated: template informs threshold and
   inference. Fixed-bin evidence is insufficient; bootstrap reselection is
   necessary but not sufficient for unconditional coverage.
2. Support remains near a boundary: feasibility minimum neff was about 20.15.
   Zero failures in 200 do not guarantee future success; the fixed empirical
   distribution's one-sided 95% failure-probability upper bound is about 1.49%.
3. Discrete q/hard thresholds cause jumps. Report q distributions, proximity to
   support boundaries and failures, not only successful intervals.
4. Template has participated in selection and is not an untouched validation set.
5. No new MC and missing independent references constrain confirmation; a new
   design does not restore confirmatory eligibility on inspected data.
6. Fresh-cohort replay is regression verification, not confirmation. Separate
   formal streams still sample the same empirical MC parent.

## Acceptance criteria

| ID | Observable criterion |
|---|---|
| AC-01 | Every entry point uses the same domain selector; reconstruct 19 cuts, weights, support and ties from contract/records |
| AC-02 | Bound fresh-cohort replay: 200/200 complete support, 131 nonmedian nonempty cells, all 75 nominal nonempty medians; diagnose deviations without retuning |
| AC-03 | Independent multirow-group arithmetic proves grouped moments/multiplicity variance; no production single-row assumption |
| AC-04 | M0off structural zero/equivalence preserved; synthetic no-solution failure has no fallback |
| AC-05 | Bootstrap C*/T*, T2 C*/fixed T; ordinary Toy/assessment excluded from selection; outer mappings synchronized |
| AC-06 | Formal bootstrap namespace/count identity separate from development/old streams; serial/parallel identity; 200 budget is not development import |
| AC-07 | Core reuse audit and new analysis identity coexist; equal threshold values do not permit old nominal/freeze/plan/claim reuse |
| AC-08 | Reports separate completion/coverage qualification; null failed intervals, conditional diagnostics and primary-claim ineligibility |
| AC-09 | Old median read/replay unchanged; no run overwrite or weaker assessment guards |
| AC-10 | Full nominal/attribution/bootstrap/model-self/assessment/T2 matrix; unauthorized/unexecuted stages remain explicit, never filled by development passes |

AC-02 is implementation consistency, not a guarantee for a new formal stream.
Formal scientific failures are reported and do not authorize method changes.

## Proof required

At design time, feasibility hashes and integration boundaries had been checked;
only the specification was written, with no new MC/Toy/T2 or code tests.

Implementation evidence requires focused independent expected-value, multiplicity,
process/role, boundary/tie, projection-failure, no-solution, identity, determinism,
compatibility and failure-budget tests, then related integration checks.
Development replay uses the bound fresh 200 cohort, checked candidate by candidate;
machine-precision agreement tolerances never alter neff/rho eligibility.

Formal evidence requires the actually authorized matrix under a new
registration/freeze/plan, complete-chain counts for 200 new bootstrap replicas,
Toy/assessment/T2 statuses and failure budgets. Neither design nor replay supplies it.
Coverage, bias and signed-MC T1 applicability require separately designed/reviewed
validation: freeze parent model/variations, repeated C/T generation and reselection,
coverage/tolerance, budgets and failure denominators before inspecting results.
Conditional model-self/T2 is not a substitute and does not grant primary eligibility.

## Open questions

No unresolved choice blocked the exploratory selector definition. The separate
coverage study's reference model/budget were outside authorization and remained
unvalidated. This did not prevent design/implementation review, but could not be
represented as a passed scientific gate.

## Approval record

- Status: approved.
- Approval source: User instruction on 2026-09-22, translated from Chinese:
  "Approve the formal design document and implement the development."
- Approved scope: method contract, implementation, software verification and
  bound development-cohort replay.
- The implementation plan was refined during development; no separate human
  plan review is claimed.
- Formal MC/Toy/T2/assessment execution and code commits were not authorized
  by this implementation instruction.
- Approved at: 2026-09-22 (Asia/Shanghai).
