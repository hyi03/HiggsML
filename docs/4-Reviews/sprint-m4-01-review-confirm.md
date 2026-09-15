# Sprint M4-01 document review confirmation

Date: 2026-09-14. Inputs: project/3-Plan/sprint-m4-01.md; project/1-Requirement/FR-401-m4l-off-feature-attribution.md; approved project/m4l-off-feature-attribution-plan.md; sprint-m4-01-review-by-gpt-5.6-sol.md; sprint-m4-01-review-by-gpt-5.5.md. The earlier external report is superseded by the user's updated reviewer workflow and is not a required reviewer pass.

Both independent reviews are useful. The approved plan remains authoritative. Apply the clarifications below before code work; they do not change registered statistical budgets or scope.

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---|---|---|---|---|---|---|---|
| 1 | High | Correctness | sol M4DOC-001 | Generic failure suppression incorrectly includes coverage intervals | Accept | Plan Bound grid/failure rules and Stage D; reporting.coverage_summary preserves planned-denominator Wilson interval | Limit formal percentile suppression to Stage C; D keeps conditional and planned coverage with Wilson intervals and failure rate; E retains failed outer budgets separately. |
| 2 | Medium | Requirement | sol M4DOC-002 | B/E injection missing from summaries | Accept | Plan Stage B and T2 specify mu=1 | Explicitly fix B model-self T1 Asimov and E T1 inner inference to mu=1. |
| 3 | Medium | Requirement | sol M4DOC-003 | Shared D/E sampling units underspecified | Accept | Plan Stage D/E; assessment._joint_mother and run_assessment_t2 | Require joint physical counts across candidates and shared outer calibration multiplicity vectors. Joint signed-cell rates must be valid; model-self falls back to marginal closure and unavailable pairing when no compatible joint model exists. |
| 4 | Low | Documentation | sol M4DOC-004 | Sprint status stale relative to baseline | Accept | baseline.md and reuse-audit.json | Link exact baseline and audit results; 75 payload contracts do not prove complete reuse or scientific independence. |
| 5 | Medium | Requirement | gpt55 M4DOC-G55-001 | Evaluation migration checklist too implicit | Partial | Plan already fully incorporated by reference; script/schema v1 mandates stress | Make v2 off-only family/budget/identity preflight, no default stress, unresolved placeholders and v1 compatibility explicit; classify as checklist clarity rather than missing approved requirements. |
| 6 | Medium | Correctness | gpt55 M4DOC-G55-002 | Legacy hard-coded candidate dependencies need explicit migration checklist | Partial | workflow G1/freeze; reporting comparison wrappers; bootstrap; assessment | Name each legacy assumption in B–E tasks and require negative tests; preserve old code path. exact_shapley itself is already general and must be reused, not replaced. |
| 7 | Medium | Clarity | gpt55 M4DOC-G55-003 | Conda executable not pinned | Accept | C:/Users/whchen/anaconda3/Scripts/conda.exe exists; verified Python 3.12.13/import location | Record that executable and explicit PYTHONPATH in verification commands. No shared environment reinstall needed. |
| 8 | Low | Documentation | gpt55 M4DOC-G55-004 | Review root mixes evidence/report types | Partial | Files use distinct baseline/audit/review suffixes; generated stage artifacts must live in runs | Keep already cited baseline files stable, explicitly list review inputs and compact audit evidence; new execution artifacts/logs go under fresh runs roots. Avoid moving immutable or already cited evidence for cosmetic organization. |

## Applied clarification contract

B: T1 model-self Asimov mu=1. D: mu=0,1,2; 500 Toys per candidate/injection/expectation. E: T1 mu=1, 20 common calibration-group outer draws ×100 joint inner Toys. Stage C alone requires all 200 successful complete replicas to publish formal percentile intervals. Stage D always retains budget, failure rate and success-and-coverage Wilson interval; conditional coverage and its Wilson interval require at least one valid fit. Stage E retains every outer state and original inner budget, with no replacement.

Off-only paths must be independent of legacy expected_candidates(), M0/M0c empty set, M4/M5 minimum matrix, M3:42 stress reference and M5/M4-only bootstrap/paired coverage. Legacy v1 behavior stays compatible. No scientific parameters migrate into CLI.

## Final status

Document confirmation complete. The FR/Sprint amendments recorded with this confirmation must be applied before implementation. Baseline failures are recorded, not accepted as a final passing suite; diagnose focused failures without changing historical scientific seals. Independent references/history remain pending and do not block software implementation or explicitly exploratory outputs.
