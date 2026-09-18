---
change_id: h4l-off-marginal-coupling-v3
status: implemented
source: User instruction on 2026-09-18 to execute the reviewed spec and modify code
updated_at: 2026-09-18
---

# Implementation work packages

The user authorized implementation of [spec.md](spec.md). This breakdown records
that authorization; it does not authorize default cutover or assessment access.

1. Implement pure marginal support, bound role/numeric contracts, canonical
   common totals, stable cell streams and monotone/independent allocations.
   Test signed rejection, numerical boundaries, identities and Poisson laws.
2. Add opt-in v3 artifact identities and J0/J1 orchestration, preserving v2
   consumers and historical schemas. Share existing inference/claim machinery
   where contracts permit; isolate version-specific orchestration.
3. Integrate model-self/assessment marginal generation and two-phase T2, with
   bound outer preflight material and truthful planned/generated counts.
4. Route CLI and wrappers explicitly; retain local h4l_all default v2 and
   off_run/evaluate/attribution default v1. Expose v3 interpretation and support
   fields in reports. Preserve history checks across versions.
5. Run focused synthetic/compatibility tests, full Python 3.12 suite and pip
   check. Inspect template-only controlled-MC J0/J1 feasibility in a fresh run
   root if compatible inputs permit. Record failures without repair. Do not
   execute assessment/T2 on the consumed population or claim scientific proof.

This is a high-risk statistical change. Acceptance follows spec criteria 1--16;
software evidence, engineering qualification, and scientific validation remain
separate. Rollback selects explicit v1/v2, retaining all v3 evidence. No commit,
push, default migration, retraining or source-data change is authorized.

Approval source: current user instruction to implement the reviewed design.
