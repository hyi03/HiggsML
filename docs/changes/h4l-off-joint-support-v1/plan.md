---
change_id: h4l-off-joint-support-v1
status: implemented
source: User approval of spec and explicit implementation request, 2026-09-22
updated_at: 2026-09-22T18:02:18+08:00
---

# Implementation plan

The user approved [spec.md](spec.md) and explicitly authorized implementation. This records the implementation decisions, without claiming separate human review of this plan.

1. Add the versioned method contract and pure selector in `modeling/joint_support.py`, reusing calibration projection and group statistics. Validate roles, process identities, mass/score support, multiplicity and bindings; record all 19 cuts and scientific failures.
2. Rebuild nominal artifacts with a fixed [105,140] grid, preserving source audit, G1 and M0off likelihood equivalence. Bind method identity across marginal registration, nominal, specification, freeze and evaluation plan.
3. Route bootstrap C*/T* and T2 C*/T through the selector. Isolate bootstrap and Toy/T2 streams by analysis contract; preserve CRN, access history, budgets and failure denominators.
4. Propagate the explicit threshold-method flag through CLI and wrappers. Update schemas, qualification reporting and fresh-root runbook commands while preserving median defaults.
5. Run hand-calculation and integration tests, exact hashed fresh-cohort replay, focused tests, full pytest and dependency checks. Record software and development replay separately from unexecuted formal analysis.

## Boundaries

No retraining, formal MC/Toy/T2/assessment execution, old artifact edits, commits or pushes. Selection-aware coverage remains unvalidated. Rollback uses median-v1 and a fresh root. The direct implementation request supersedes the skill's separate plan approval workflow; no newly written plan is represented as independently approved.

Implementation and self-check evidence: [verification.md](verification.md). Direct user authorization and the absence of separate plan review are preserved above.
