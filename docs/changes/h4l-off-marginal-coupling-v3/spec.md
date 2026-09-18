---
change_id: h4l-off-marginal-coupling-v3
status: approved
source: User request on 2026-09-18 to incorporate the two spec reviews and their point-by-point confirmation
updated_at: 2026-09-18T11:04:14+08:00
---

# Spec: H4l off-only marginal-preserving common-random-number coupling

This revision incorporates the decisions in the
[point-by-point review confirmation](../../4-Reviews/h4l-off-marginal-coupling-v3-review-confirm.md),
covering the [GPT-5.6 Sol review](../../4-Reviews/spec-review-by-gpt-5.6-sol.md)
and [GPT-5.5 review](../../4-Reviews/spec-review-by-gpt-5.5.md).
The confirmation accepts nine findings and partially accepts the identity-scope
finding. It is not approval to implement or to change the default version.

## Problem and Outcome

The v2 within-seed contract builds one empirical joint category cell for every
observed combination of the 16 candidates in a training-seed block. On the
template parent used by `runs/h4l-off-test01-v2/support-j0`, this produces
2,238--2,522 occupied joint cells per seed. Signed MC cancellation makes some
aggregate-label joint-cell rates negative, so all five seed blocks fail J0 with
`negative_process_rate` before freeze.

The same J0 artifact shows that this is a joint-refinement failure rather than
a candidate-marginal failure at label level: each seed has 62 projected
label/candidate/category marginal rates, none are negative or zero, and every projection mismatch count
is zero (maximum numerical projection error about `1.51e-13`). J0 did not read
assessment payload. Its `process_identity_source=label_legacy` identifies
aggregate background/signal labels, not separately audited physical processes.

The desired outcome is a versioned evaluation contract that:

1. preserves the exact Poisson marginal observation law of every candidate;
2. keeps all 16 coalitions in one globally consistent within-seed coupled Toy;
3. avoids using the empirical `2^16` category cross-product as Poisson
   intensities;
4. retains signed-weight rejection at the candidate marginal level;
5. describes the induced dependence truthfully as a registered
   common-random-number (CRN) coupling, not shared physical-event pairing.

## Affected Users and Systems

- Researchers running the MC-only off-only attribution workflow.
- J0/J1 support qualification, model-self, assessment and T2 Toy generation.
- Pairing/evaluation schemas, freeze/plan identities, claims, reports and CLI
  version dispatch.
- Existing v1 and v2 artifacts and claims remain immutable historical evidence.

This is a high-risk statistical-contract change. It changes covariance between
candidate Toy results but must not change any candidate's marginal likelihood
or pseudo-observation distribution.

## Scope

- Introduce a new `v3` analysis/evaluation version and pairing contract
  `h4l-mass-off-marginal-crn-v1`. Do not mutate the meaning of v2 artifacts.
- Keep the five canonical seed blocks and all 16 identities per seed.
- Replace joint-cell Poisson sampling with the common-total monotone coupling
  specified below.
- Replace v2 joint-cell support gates with marginal-support and common-total
  consistency gates.
- Apply the same contract to model-self, frozen assessment and T2 inner Toys.
- Preserve candidate-specific auxiliary-constraint streams.
- Update reports and schemas so the coupling source and interpretation are
  explicit.
- Keep v3 opt-in through implementation and software verification. Default
  cutover is a separate approval gate requiring fresh, bound controlled-MC J0
  and J1 passes; explicit `--evaluation-version v1|v2` remains compatible.

## Non-goals

- This change does not make the already opened `test01` assessment population
  eligible again and does not authorize new assessment access.
- It does not delete, relabel, overwrite or resume the failed v2 J0 run.
- It does not clip negative rates, take absolute weights, add epsilon, merge
  bins adaptively or remove failed seeds/candidates.
- It does not claim that CRN covariance equals the covariance of a physical
  event sample classified by all 16 models.
- It does not add MC, change role allocation, retrain models, change the common
  nominal mass grid, alter the Shapley value function or change Toy budgets.
- It does not introduce automatic 4-way/2-way fallback.

## Requirements and Design

### Version and identity

`evaluation-version v3` is a new evidence identity. Its specification, freeze,
evaluation plan, RNG streams, claims and reports bind the new pairing-contract
digest. v1/v2 artifacts may be referenced only as explicit historical or
compatibility inputs; no v2 seed-evaluation terminal or assessment claim is a
v3 result.

The candidate family remains
`engineered19_raw_T1_m4l_off_attribution_v1`. Seeds remain 42--46 and each seed
block remains `M0off + 15` canonical nonempty coalitions. Cross-seed pairing
remains `none`.

### Marginal-rate construction

For one parent, training-seed block, process `p`, mass bin `b`, candidate `c`
and category `k in {0,1}`, compute the signed marginal rate

```text
lambda[c,p,b,k] = sum(yield_weight for rows mapped to c,b,k,p)
```

Here `p` denotes the registered qualification unit: a physical process in
`physical_process` mode or an aggregate label in `label_level_legacy` mode.
All support records, coupling receipts and downstream reports must carry
`identity_qualification` with one of those two values and the role-map digest;
readers must not infer physical-process qualification from the variable name.

Signal rates are multiplied by the registered injection `mu`; background rates
are not. Every process identity is resolved through a version-bound role map
with exactly one of `signal` or `background`. Missing, duplicate or ambiguous
roles are binding errors before rate construction. A physical `process` field
uses an audited process-to-role map. The registered legacy dataset may instead
bind `{0: background, 1: signal}`, but its machine-readable qualification is
`label_level_legacy`, not `physical_process`; it cannot support physical-process
claims or prove that separate background processes do not cancel within label
0. Signal and background may never cancel each other to repair a rate.

Every marginal rate must be finite and nonnegative. Each process must have
positive total support before injection. For every `p,b`, candidate totals

```text
Lambda[c,p,b] = lambda[c,p,b,0] + lambda[c,p,b,1]
```

must agree across all 16 candidates with one canonical direct-parent total.
For each `(p,b)`, `Lambda[p,b]` is computed once from the unmapped parent after
group-first deterministic accumulation: rows are sorted by canonical
`(process identity, mass-bin index, event_group_id, source_row_id, event_id)`,
each physical-group sum and then the process/bin sum use IEEE-754 binary64
inputs with `math.fsum`. Candidate categories are accumulated by the same rule.
Candidate totals are compared to the pre-injection direct total using
`rtol=1e-10` and `atol=1e-10`; values just inside/outside both boundaries are
contract tests. Injection scaling occurs only after this equality check.
The comparison is `abs(actual - reference) <= 1e-10 + 1e-10 * abs(reference)`,
where the reference is the direct-parent total; direct-histogram projection
uses the same rule with the direct candidate histogram as reference. This
tolerance applies only to equality checks, never to negative-rate rejection.
Receipts serialize binary64 values through the repository's canonical JSON
full-precision representation and bind the numeric-contract version. A
mismatch is a binding/implementation error, not insufficient statistics.
`M0off` uses its registered structural-zero category and the same total.

No empirical cross-candidate category pattern is used as a Poisson intensity.
Joint-pattern diagnostics may be retained only as descriptive, non-gating
evidence.

### Common-total monotone coupling

For every Toy index, process `p` and mass bin `b`:

1. Draw one shared total `N[p,b] ~ Poisson(Lambda[p,b])` from a stable physical
   stream bound to contract, stage, `mu`, training seed, outer index and Toy
   index.
2. Draw `N[p,b]` iid uniforms `U[p,b,i]` from a separately identified shared
   allocation stream.
3. For candidate `c`, define
   `theta[c,p,b] = lambda[c,p,b,1] / Lambda[p,b]` and set
   `n[c,p,b,1] = count(U < theta[c,p,b])`,
   `n[c,p,b,0] = N - n[c,p,b,1]`.
4. Sum process counts into each candidate's observed category/mass vector.

For every candidate this is exactly Poisson splitting: conditional category
counts are binomial and unconditional category counts have the required
independent Poisson marginals. Candidates share the same total count and the
same uniforms, producing a deterministic monotone CRN coupling. It is a
variance-reduction/comparison device, not an empirical physical-event joint
distribution.

`Lambda=0` produces zero counts without uniforms. `mu=0` therefore removes
signal observations without special negative-rate handling. Category threshold
ties are resolved by the specified strict comparison and fixed floating-point
serialization; stream derivation never uses Python's randomized hash.

Distinct `(process identity, mass-bin index, Toy index)` cells use disjoint
stable substreams. Stream identity binds pairing-contract digest, stage, `mu`,
training seed, outer index, Toy index, canonical process identity, mass-bin
index and stream kind (`physical_total_poisson` or `shared_category_uniform`).
Canonical process ordering is the serialized registered identity order and mass
bins use ascending zero-based indexes. Candidate auxiliary streams use a
separate namespace. Tests must detect substream-ID collisions, swapped process
order, reuse across mass bins and accidental reuse of auxiliary variates.
Permutation of input process traversal must leave each identity's draws
unchanged. Fixed-seed synthetic covariance checks must also detect unintended
dependence across distinct process/mass cells; these supplement, rather than
replace, the analytic independence argument and stream-identity checks.

### Pairing semantics

Published metadata must use:

```text
pairing_scope: within_seed
pairing_kind: marginal_common_total_monotone_crn
physical_event_pairing: false
cross_seed_pairing: none
```

The phrase `shared_joint_physical_event_cells` is forbidden for v3. Candidate
coverage and interval summaries keep their ordinary marginal interpretation.
Paired differences and their Monte Carlo errors are conditional on this
registered coupling and must be labelled accordingly. No claim may be made
that v3 recovers real cross-classifier event covariance.

CRN-dependent paired errors are diagnostic-only fields with a machine-readable
`uncertainty_scope=conditional_on_registered_crn_coupling`. They cannot qualify
physical covariance, total uncertainty, coverage reliability or a primary
scientific claim. A registered sensitivity diagnostic repeats key paired-error
summaries with the same common totals but independent per-candidate allocation
streams. It does not replace the primary coupling or trigger fallback; reports
show both results or mark sensitivity `pending`.

This restriction covers paired coverage differences, paired Toy width/bias
differences and any Toy-derived subset, Shapley or interaction error summary.
Each such output records `primary_claim_eligible=false` and its coupling kind;
consumers must enforce that field, not just display a warning. Nominal Asimov
values, group-level MC-bootstrap uncertainty and training-seed stability retain
their separate value sources and are not relabelled as CRN errors.
Before freeze, the sensitivity definition binds the compared summaries and
Toy indexes. It reuses the primary total draws, adds candidate identity to a
distinct `independent_category_uniform` allocation namespace, and preserves
the same marginal rates. A report with sensitivity `pending` states the reason
and cannot treat the diagnostic as completed. No extra assessment access or
increase to registered Toy budgets is authorized by this sensitivity clause;
if it cannot run within the bound authorization it remains pending.

### J0 and J1

J0 validates candidate/identity/mass/category marginals, candidate-invariant
totals, structural zeros, process/label consistency, event-group integrity,
mapping/grid identity and exact projection against direct candidate
histograms. A negative marginal rate remains `insufficient_statistics` and is
never repaired. A candidate-total mismatch is a binding error.

J1 retains the fixed 200 group-level Bernoulli-thinning replicas and registered
`q_thin`. Each replica applies the same retained physical groups across all
candidates, then repeats the v3 marginal and common-total checks. The gate
requires zero failures out of 200 replicas for each of all five seeds; it does not inspect assessment and is
not scientific validation.

v3 screening artifacts store scalar `q_thin`, and coupling receipts store
`theta[c,p,b]` separately (null with a zero-total marker when `Lambda=0`).
Neither field may substitute for the other. The v1/v2 schema's `policy.q`
retains its existing thinning meaning; any compatibility adapter records that
explicit mapping to `q_thin` without rewriting historical artifacts.

The current v2 J0 artifact is `label_level_legacy` characterization evidence
only. Its projected 62 rates per seed suggest the v3 J0 definition would remove
the observed cross-product failure at aggregate signal/background-label level;
it neither proves physical-process support nor qualifies assessment. The
implementation must recompute from the bound parent and may still truthfully
fail. A fixture with one negative background process hidden by positive label-0
cancellation must be rejected by `physical_process` mode and recorded as an
unresolved limitation in `label_level_legacy` mode.

### Evaluation layers

- Model-self uses nominal/template-parent marginal rates.
- Assessment uses the frozen assessment parent's direct candidate marginals;
  assessment marginals are not required to equal nominal template rates.
- T2 is two-phase. Phase 1 deterministically builds and binds all 20 outer
  multiplicities, mappings, templates and candidate marginals, and validates
  every outer support record before any inner physical Toy is generated. If a
  non-first or any outer fails, the terminal records all outer preflight states,
  zero generated inner physical Toys and the full planned denominator. Phase 2
  runs the 100 inner Toys per outer only after all 20 preflights pass, keeping
  the nominal mass grid and v3 inner coupling.
  Phase 2 consumes the bound Phase 1 mappings and marginals without rebuilding
  them. A preflight support failure retains all 20 outer records and the
  planned 20x100 denominator for the seed; other seed blocks retain their own
  actual counts. An execution/fit failure after generation must retain actual
  generated counts and consumed claims, never report them as zero.
- Candidate-specific auxiliary observations retain independent, stable streams
  unless a modifier explicitly has a registered shared-normal contract.
- MC bootstrap and nominal Asimov estimands are unchanged unless their binding
  metadata must carry the new version identity.

Existing 500-Toy, 200-bootstrap and 20x100-T2 budgets do not change. A support
failure publishes a complete scientific terminal with planned denominators and
zero generated physical Toys; malformed identity or total mismatch remains an
execution error.

## Interfaces and Data

Expected affected interfaces include:

- a pure marginal-support service replacing v3 calls to
  `diagnose_joint_support`;
- a v3 paired-Toy generator returning candidate observations plus stream and
  coupling receipts;
- v3 seed-block/evaluation/specification/freeze/plan/access schemas;
- CLI choices `v1|v2|v3` and v3 dispatch in `h4l_all.py`,
  `h4l_off_run.py`, `h4l_evaluate.py` and attribution routing;
- reports and CSV fields for coupling kind, marginal-support counts, minimum
  rates, total-consistency error, identity qualification,
  `uncertainty_scope`, sensitivity status and interpretation limits;
- all user-facing reproduction/method/result documentation and regression
  coverage for explicit `v1|v2|v3` routing. An omitted version may route to v3
  only after the separately approved default-cutover gate.

The exact module split is an implementation-plan decision after spec approval,
but statistical logic must remain in inference/domain services, not CLI code.

## Failure, Recovery, and Compatibility

- Before default cutover, each entry point preserves its prior default;
  adding v3 support must not silently align differing wrapper defaults.
  The implementation plan records the actual pre-change default of each
  entry point, including any separately authorized `h4l_all.py` change.
  A cutover record must bind the passed J0/J1 artifact IDs, prepared population,
  registration/nominal IDs, pairing and screening-policy digests, role-map
  digest, identity qualification and explicit human approval. Both gates must
  cover all five seeds under the same bound rules and record
  `assessment_payload_read=false` and
  `evidence_scope=engineering_screen_not_scientific_validation`.
  Legacy qualification permits only a label-qualified cutover, never an
  upgrade to physical-process evidence or assessment authorization. Failed,
  missing or mismatched evidence leaves the prior default unchanged.
- v1 and v2 remain readable and explicitly runnable; their schemas and pairing
  meanings are unchanged.
- v3 requires a fresh run root, new freeze/spec/plan and new claims. Existing
  failed v2 support evidence remains immutable.
- Existing trained checkpoints and nominal candidate definitions may be reused
  only through the current compatibility audit; the new coupling alone does
  not require retraining.
- A v2 access receipt cannot be relabelled v3. Assessment history continues to
  span versions and freeze IDs.
- Resume may skip a fully bound v3 terminal, including scientific failure, but
  may not recompute a consumed assessment cell.
- Rollback disables new v3 entry points/default routing. It never deletes v3
  artifacts or claims and never reinterprets them as v2.

## Policy and Architecture Constraints

- MC-only; never inspect or use real data.
- Freeze precedes assessment access; no assessment-driven tuning of coupling,
  bins, thresholds, mappings, candidates or policy.
- Signed physical weights estimate yields; negative marginal intensities are
  invalid for Poisson generation.
- Physical event groups stay intact while constructing every parent and J1
  replica.
- One common nominal mass grid and all 80 registered identities remain fixed.
- Software/synthetic validation, template-parent controlled-MC diagnostics and
  actual frozen assessment are distinct evidence levels.
- Do not describe outputs as ATLAS results, discovery or measurement.

## Risks and Concerns

1. **Artificial covariance:** monotone CRN maximizes positive dependence for
   binary splits ordered by `theta`; paired-error bars may be smaller than under a
   physical joint sample. Control: explicit labels, marginal conclusions as
   primary, coupling-sensitive paired quantities as conditional diagnostics,
   machine-readable eligibility and an independent-allocation sensitivity.
2. **Contract identity:** changing v2 in place would make identical labels mean
   different probability spaces. Control: introduce v3 despite the request's
   shorthand wording “modify v2”.
3. **Assessment remains blocked:** this design fixes the template support
   architecture, not the historical-use gate or missing eligible assessment
   source.
4. **Marginal negative rates can remain:** lower dimensionality reduces but does
   not eliminate signed-MC failure. The implementation must publish failure.
5. **Process totals and floating point:** totals computed through different
   mappings may differ by summation order. Use the frozen binary64/group-first
   `math.fsum` contract, direct-parent canonical total and registered tolerance;
   never coerce a material mismatch.
6. **Interpretation drift:** legacy reports and tests use “physical pairing”.
   All v3 outputs and documentation must remove that claim without weakening
   v1/v2 historical descriptions.
7. **Legacy identity scope:** aggregate labels can hide cancellation among
   physical backgrounds. Legacy mode stays explicitly label-qualified and
   cannot establish physical-process support.
8. **Premature default migration:** J1 feasibility is unknown. v3 remains
   opt-in until controlled-MC J0 and J1 both pass and cutover is approved.

## Acceptance Criteria

1. A hand-computable two-candidate/two-category fixture proves every candidate
   has the requested marginal observations and shares one total draw.
2. Analytic/property tests prove the algorithm implements Poisson splitting
   and independent generating variates across distinct process/mass cells;
   fixed-stream tests prove serial/parallel bitwise-identical outputs and reject
   substream collisions or auxiliary-stream reuse.
3. A negative candidate marginal is rejected even when its process total and
   other candidates are positive; no clipping/absolute value/epsilon occurs.
4. A candidate-total mismatch is rejected as a binding error. The canonical
   direct-parent `Lambda[p,b]`, deterministic binary64 accumulation,
   `rtol=atol=1e-10`, pre-injection comparison and full-precision receipt are
   tested just inside and outside the boundary. A fixture with allowed
   summation noise proves the canonical total is independent of candidate
   order and is neither a selected candidate total nor an average.
5. Current `test01-v2` template characterization recomputed under the new gate
   reports 62 positive label-level marginals per seed and no cross-product-rate
   criterion; it is labelled `label_level_legacy` controlled-MC engineering
   evidence, not physical-process or assessment validation.
6. J0/J1 and plan-only demonstrably do not decode assessment or create claims.
7. Model-self, assessment and T2 use the same versioned coupling contract and
   preserve registered budgets, stream identities and planned denominators.
   T2 validates and binds all 20 outer mappings/support records before any inner
   physical Toy; a later-outer preflight failure records zero generated inner
   Toys and all outer statuses.
8. Reports state `physical_event_pairing=false`, never use the v2 physical-cell
   label for v3, and explain the conditional CRN interpretation.
9. v1/v2 golden tests continue to pass; v2 failed artifacts cannot be loaded as
   v3 and v3 artifacts cannot satisfy v2 consumers.
10. Existing assessment history still blocks `test01` from prospective v3
    assessment access.
11. Focused and full software suites pass in the dependency-complete Python
    3.12 environment; synthetic tests are not reported as scientific
    validation.
12. Every process identity has a bound signal/background role; swapped,
    missing or ambiguous legacy maps are rejected before injection scaling.
13. CRN-dependent errors carry conditional scope, are ineligible for physical
    covariance/total-uncertainty claims, and key paired errors have the
    registered independent-allocation sensitivity or explicit `pending` state.
14. v3 remains opt-in until fresh bound controlled-MC J0 and all 200 J1
    replicas per seed pass. Default cutover additionally requires explicit
    human approval; a failed gate preserves evidence and leaves the prior
    default unchanged.
15. CLI and documentation tests cover `v1|v2|v3` for every entry point, the
    pre-cutover default, explicit legacy routing and the separately approved
    post-cutover behavior, including the cutover evidence bindings above.
16. v3 artifacts distinguish scalar J1 `q_thin` from indexed allocation
    `theta`; schema/receipt mutation tests reject substituted fields and
    preserve the v1/v2 `policy.q` interpretation.

## Review Decision Traceability

The references below identify requirements to implement and verify, not tests
already run or proof that the new statistical contract has passed.

| Confirmation | Decision | Incorporated requirement | Acceptance criteria |
|---|---|---|---|
| 1 / Sol C1 | Accept | Independent process/bin substreams, auxiliary isolation, traversal invariance and covariance checks | 1, 2 |
| 2 / Sol C2 | Partial | Label-level evidence explicitly qualified; physical-process cancellation remains unqualified in legacy mode | 3, 5, 12 |
| 3 / Sol C3 | Accept | Bind all T2 outer preflights before inner generation; preserve truthful per-seed accounting | 7 |
| 4 / Sol C4 | Accept | Opt-in v3; fresh bound J0/J1 passes and separate default-cutover approval | 14, 15 |
| 5 / Sol C5 | Accept | Binary64, group-first accumulation, fixed equality rule and full-precision receipts | 4 |
| 6 / Sol C6 | Accept | Machine-readable diagnostic eligibility and independent-allocation sensitivity | 8, 13 |
| 7 / GPT-5.5 C1 | Accept | Direct-parent canonical total, independent of candidate order | 4 |
| 8 / GPT-5.5 C2 | Accept | Bound identity-to-role map before rate construction and injection | 12 |
| 9 / GPT-5.5 C3 | Accept | Separate `theta` and `q_thin` fields and legacy schema interpretation | 16 |
| 10 / GPT-5.5 C4 | Accept | Entry-point default/explicit-version coverage and corresponding documentation | 9, 14, 15 |

## Proof Required

- Red/green unit tests for marginal aggregation, total consistency, coupling
  construction, stream independence/determinism and negative-rate failures.
- Schema and artifact mutation tests across v1/v2/v3.
- Workflow tests for gate-before-freeze, terminal publication, resume and
  assessment-history refusal.
- Controlled-MC read-only v3 J0/J1 run in a fresh run root, recording exact
  evidence level and preserving the v2 failed run. Both gates must pass before
  any proposal to change the default route.
- Coupling-sensitivity evidence comparing monotone shared allocation with
  common totals plus independent per-candidate allocation for registered key
  paired-error summaries.
- Focused pytest commands, full pytest, `pip check` and `git diff --check`.
- Two independent plan/code reviews at the appropriate lifecycle stages.
- No production assessment/T2 run without a separately eligible source and
  explicit authorization.

## Open Questions

The user approved implementation of this design on 2026-09-18. Monotone CRN
covariance remains an explicitly artificial, versioned coupling for paired
diagnostics, while candidate marginal inference retains the primary
interpretation. Default cutover and prospective assessment remain separate
authorizations.

## Approval Record

- Status: approved
- Decision source: User instruction on 2026-09-18: 按此方案执行任务，修改代码
- Approved at: 2026-09-18 (current task)
