# H4l off-only marginal coupling v3 spec review confirm

**Reviewed Inputs**

- `docs/changes/h4l-off-marginal-coupling-v3/spec.md`
- `docs/4-Reviews/spec-review-by-gpt-5.6-sol.md`
- `docs/4-Reviews/spec-review-by-gpt-5.5.md`
- Current v2 inference/support code and `test01-v2` J0 artifact

**Review Date**

- 2026-09-18

## Overall Conclusion

Both reviews are evidence-backed and the spec should not be approved as written.
Nine findings are accepted. The process-identity finding is partially accepted:
the current dataset has only an audited binary label, so v3 may support a
machine-labelled `label_level_legacy` qualification, but it must not present
that evidence as physical-process-qualified or allow an ambiguous signal map.

The spec can return to `awaiting_approval` after the confirmed items below are
incorporated. No implementation or implementation plan is authorized by this
confirmation.

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---:|---|---|---|---|---|---|---|
| 1 | High | Correctness | Sol C1 | RNG contract omits process/bin substream independence. | Accept | `paired_event_toys` currently consumes one joint RNG; the proposed law requires independent draws across distinct process/mass cells and isolation from auxiliary streams. | Bind physical-total and allocation substreams to canonical process ID, mass-bin index, Toy index and stream kind; define canonical ordering and add collision/cross-cell covariance tests. |
| 2 | High | Correctness | Sol C2 | The 62 positive rates are label-level, not physical-process-level evidence. | Partial | The J0 artifact records `process_identity_source=label_legacy`; `data.py` persists label but no physical process field. The reviewer is correct that process-level claims are unsupported, but requiring a new process column would exclude the current registered dataset rather than specify its actual evidence level. | Add explicit `label_level_legacy` versus `physical_process` qualification scopes, require a bound role map in both cases, prohibit process-level claims for the legacy scope, and test hidden process cancellation as an unqualified limitation. |
| 3 | High | Correctness | Sol C3 | T2 can fail after earlier outer Toys, contradicting a blanket zero-generated terminal. | Accept | Current `run_assessment_t2` evaluates outer replicas sequentially through `run_t2_procedure`; a later support failure can follow completed inner Toys. | Require a two-phase T2: compute and bind all 20 mappings/marginals first, then generate no inner Toys unless every outer support check passes. Add a non-first-outer failure test. |
| 4 | High | Requirement | Sol C4 | Default v3 routing is not gated on successful controlled-MC J0 and J1. | Accept | v2 stopped at J0, so no J1 feasibility evidence exists. Making an unqualified version the default would cause ordinary runs to fail before freeze. | Keep v3 opt-in until fresh bound controlled-MC J0 and J1 both pass and a separate default-cutover approval is recorded. Preserve any failed evidence. |
| 5 | Medium | Reproducibility | Sol C5 | Tolerances, accumulation and serialization are not frozen. | Accept | These choices determine binding-error versus pass and the draft claimed no blocking choice remained. | Freeze float64, canonical keys/order, `math.fsum` group accumulation, direct-parent totals, `rtol=atol=1e-10`, pre-injection comparison and canonical JSON/full-double receipts; add boundary mutation tests. |
| 6 | Medium | Risk | Sol C6 | Labels alone do not prevent CRN-dependent paired errors from being overinterpreted. | Accept | The primary paired comparisons depend on the selected copula even with exact marginals. | Add machine-readable output eligibility, prohibit CRN errors from physical/total-uncertainty claims, and register an independent-allocation sensitivity coupling for diagnostic comparison. |
| 7 | High | Correctness | GPT-5.5 C1 | `Lambda[p,b]` has no canonical source after tolerant equality checks. | Accept | The draft defined candidate totals but sampled an undefined scalar. | Define `Lambda[p,b]` as the direct parent process/mass total computed once with deterministic group-first accumulation; compare candidate partitions to it and serialize it in the receipt. |
| 8 | High | Correctness | GPT-5.5 C2 | Legacy labels lack an explicit signal/background role mapping for `mu`. | Accept | Current J0 keys use `0`/`1`; scaling by `mu` must not rely on an implicit or swappable convention. | Bind a versioned identity-to-role map, including `{0: background, 1: signal}` for the registered legacy dataset; reject missing, duplicate or ambiguous mappings before rates are constructed. |
| 9 | Medium | Clarity | GPT-5.5 C3 | `q` is overloaded for category allocation and J1 thinning. | Accept | Existing J1 APIs and schema use scalar `q`, while the draft reused `q[c,p,b]`. | Rename category probability to `theta[c,p,b]` and J1 probability to `q_thin`; store/test both separately. |
| 10 | Medium | Consistency | GPT-5.5 C4 | Default migration lacks documentation and CLI acceptance coverage. | Accept | Current docs state v1 default and current CLIs accept only v1/v2; the local `h4l_all.py` default-to-v2 edit is not a complete v3 migration. | Add all entry-point compatibility tests and docs updates, but execute default migration only after the gated cutover in decision 4. |

## Needs Immediate Action

- Revise the spec for decisions 1--10 before requesting approval.
- Keep v3 opt-in and separate from immutable v2 evidence.
- Make T2 support validation two-phase before any inner physical Toy generation.
- Freeze numeric, process-role and RNG substream contracts.
- Add coupling-sensitivity and machine-readable interpretation boundaries.

## Can Be Deferred

- Adding a true physical-process column or new independent MC source remains a
  separate data-contract change. Until then, legacy evidence is label-level.
- Default migration remains deferred until controlled-MC v3 J0 and J1 pass and
  the user approves cutover.

## Final Status

The original spec should not be accepted as-is. Minimum remaining spec work is
to incorporate the ten decisions above and retain `status: awaiting_approval`.
