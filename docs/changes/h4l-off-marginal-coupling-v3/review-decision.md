---
change_id: h4l-off-marginal-coupling-v3
status: awaiting_approval
source: Evidence-backed decisions on implementation review findings
updated_at: 2026-09-18
---

# Review decisions

| ID | Decision | Implemented resolution | Proof |
|---|---|---|---|
| C1 | Accept | Preserve a sole preflight failure status; mixed states use inference_incomplete and explicit failure-status set | Parameterized late-outer support failure regression |
| C2 | Accept | Record zero_total and zero_injected_total separately | Zero-parent-bin/null-theta regression |
| R1 | Partial | Reject missing access before full v3 work; retain v2 behavior to preserve compatibility | Wrapper guard regression |
| R2 | Accept | State each entry point's default, including existing h4l_all v2 default and explicit v3 selection | Documentation inspection |
| R3 | Accept | Match actual marginal contract and seed-block identities | Real-block schema validation and joint-contract mutation |
| R4 | Accept | Require marginal_support, coupling_receipts and conditional metadata; validate legacy alias equality | Terminal mutation and immutable-resume tests |
| R5 | Accept | Use within-seed wording in plan-only output | Source inspection |
| S1 | Accept | Atomically reserve a shared population across v1/v2/v3 with exclusive creation and durable writes | Forced cross-version race and shared history tests; risk reviewer recheck |
| R6 | Accept | Validate/create the legacy directory before reserving the shared population | Invalid-directory regression and risk reviewer recheck |

All raised changes are implemented. Final software evidence is tracked in
[verification.md](verification.md); this review does not authorize default
cutover, new assessment access, or scientific claims. Sensitivity fitting remains
explicitly pending under the approved spec. No new unresolved reviewer finding
is being presented as accepted risk.
