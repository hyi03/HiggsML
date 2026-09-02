# Document Review Report: Sprint M1-06

**Reviewed file:** `D:\code\HiggsML\neural\docs\sprint-m1-06.md`

**Review type:** Document review

**Reviewer:** opencode-go/kimi-k2.7-code

**Date:** 2026-09-02

**Scope:** This review evaluates the `sprint-m1-06.md` plan document against [`FR-001`](neural/docs/FR-001-adversarial-mlp-refactor.md), [`neural/AGENTS.md`](neural/AGENTS.md), [`neural_adversarial_mlp_refactor_design.md`](neural_adversarial_mlp_refactor_design.md), and the completed M1-01 through M1-05 Sprint artifacts. It is a document-only review; no data, held-out test, or model execution was performed.

---

## Executive Summary

The M1-06 Sprint plan correctly frames the final phase of FR-001: it limits the authority gate to a locked native `osx-arm64` environment, keeps `open-test` behind a separate explicit authorization, distinguishes Windows development evidence from authority evidence, and does not relax the scientific safety constraints established in the design and earlier Sprints. However, the plan references four deliverable documents and a final README state that do not yet exist in the repository, and it contains a stale platform status line and a few missing cross-references that could create ambiguity during execution. Because M1-06 is a plan rather than an evidence report, the empty checkboxes and blank delivery conclusion are acceptable as placeholders, but the missing downstream documents must be produced (or explicitly deferred with owners) before the Sprint can be closed.

---

## Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| Critical | Requirement | Section 3 (In scope), Section 5.3, Section 6 (Acceptance criteria) | Four deliverable documents listed as in-scope for M1-06 do not exist in the repository: `neural/docs/runbook.md`, `neural/docs/artifact-schema.md`, `neural/docs/m1-06-verification-evidence.md`, and `neural/docs/final-technical-report.md`. | Directory listing of `neural/docs/` contains only Sprint/FR/protocol files; `runbook.md`, `artifact-schema.md`, `m1-06-verification-evidence.md`, and `final-technical-report.md` are absent. `neural/README.md` references protocol docs but not a runbook or artifact schema. | Create the four documents before marking M1-06 complete. If the plan is being approved before document creation, add explicit "to be created" placeholders with owners and due dates in Section 5.3 or Section 6. |
| High | Consistency | `neural/README.md`, lines 7–8 | The README status banner still states "Sprint M1-04 MC-only development …" and "Windows/synthetic 验证不替代尚未执行的 locked native `osx-arm64` full-data gate." M1-06 requires the README to be final and sufficient for recovery from scratch. | `README.md` lines 7–8. The current content does not reflect M1-05 test-opening completion or the M1-06 full-chain reproduction goal. | Update the README status banner to M1-06, add pointers to the runbook and artifact schema once they exist, and ensure recovery instructions cover the full preprocess → develop → optional open-test chain. |
| Medium | Clarity | Section 5.1, Section 5.2, Section 7 (Verification requirements) | The document requires recording `osx.yml` SHA-256, ROOT SHA-256, protocol/config SHA-256, and manifest SHA-256, but it does not inline or explicitly cross-reference the exact expected values. Readers must independently locate them in FR-001 or the design document. | FR-001 lines 116–117 and design document lines 207–208 list Higgs ROOT `5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0` and ZZ ROOT `76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07`; these values are absent from `sprint-m1-06.md`. | Add a "Bound hashes / expected references" subsection or table that cites the two ROOT hashes, the r3-ARM64 golden table hash (`bc31f4e65ccecc0a1962648cfe240b67d8ecc6df8eda2478b3f46c93d2f34f09`), and the relevant protocol file paths, with explicit references to FR-001 and the design doc. |
| Medium | Risk | Section 6 (Acceptance criteria), lines 129–131 | The acceptance criteria state that `m1-06-verification-evidence.md` must distinguish evidence classes and that "只有要求的 authority 项全部通过后才能关闭 Sprint." The required items are environment, preprocess, and development, but the sentence is adjacent to the `test_opening` class and could be misread as implying test-opening is a required closure gate. | Section 6, lines 129–131. | Add an explicit parenthetical or bullet clarifying that `test_opening` is **not** a required authority item for Sprint closure and must remain `not_run` unless the user separately authorizes it. |
| Medium | Correctness | Section 2 (Prerequisites), line 21 | The plan states "当前执行主机经 preflight 确认为 Windows/AMD64." This is accurate for the current host but is execution-context specific and will become stale if the document is reused on the authority host. | Section 2, line 21. | Rephrase as a dynamic preflight note, e.g., "Preflight note (2026-09-02): the current host is Windows/AMD64, therefore …", or move this observation to `m1-06-verification-evidence.md` and keep the Sprint plan host-neutral. |
| Low | Consistency | Document header | Unlike FR-001 (lines 1–7) and the design document (lines 1–5), `sprint-m1-06.md` has no metadata header (status, version, date, owner). This makes revision tracking harder. | File begins directly with `# Sprint M1-06`. | Add a small metadata block: status (e.g., "Plan / Pending authority gate"), version, date, and owner/reviewer. |
| Low | Clarity | Section 5.1, lines 74–75 | The plan requires two CLI smokes: "synthetic mechanism smoke 与 authority full-data preprocess/develop." The synthetic mechanism smoke is not defined in this document. | Section 5.1, lines 74–75. | Add a one-line cross-reference to the existing smoke definitions (e.g., M1-01 CLI help smoke and M1-04 synthetic fixture smoke) or include the exact example commands. |
| Info | Documentation | Section 10 (Delivery conclusion) | The delivery conclusion is intentionally blank because the Sprint is a plan. This is acceptable, but it provides no tracking signal. | Section 10, lines 176–178. | Keep the placeholder but add a note such as "Must be filled only after the authority gate passes or is explicitly blocked; do not pre-populate expected results." |

---

## Positive Observations

- **Authority boundary is correctly maintained.** Section 2 and Section 7 explicitly state that the current Windows/AMD64 host can only perform local development verification and documentation preparation, and cannot substitute for the locked native `osx-arm64` authority gate. This matches [`neural/AGENTS.md`](neural/AGENTS.md) and the design document.
- **Test-opening authorization is properly gated.** Sections 4, 5.3, 6, and 7 repeatedly clarify that `open-test` is out of scope unless the user provides separate explicit authorization, and that a `not_run` state is the correct default.
- **No scientific safety relaxation.** The document does not propose to add features, widen AUC/KS thresholds, reuse failed runs, or read real data; it preserves the MC-only, 15-feature, five-candidate five-fold, fail-closed constraints from FR-001 and earlier Sprints.
- **Failure retention is preserved.** Sections 5.2 and 9 require failed runs to be kept, not deleted or reused, consistent with the immutable run policy.
- **Evidence taxonomy is well structured.** The plan distinguishes `static`, `windows_development`, `synthetic_fixture`, `authority_full_data`, and `test_opening` evidence classes, which aligns with the need to separate authority evidence from development/synthetic evidence.

---

## Cross-Check Notes

| Reference | M1-06 Treatment | Verdict |
|---|---|---|
| FR-001 R1–R7 | M1-06 scope maps to R1 (recovery/docs), R2 (full preprocess), R3/R4 (development OOF), R5 (test-opening boundary), R6 (audit/manifest), R7 (tests/docs). | Consistent |
| Design doc §13 (Phase 6) | M1-06 matches Phase 6: full-chain reproduction, documentation, and optional test-opening. | Consistent |
| M1-05 test-opening mechanism | M1-06 correctly treats M1-05 as implemented but not automatically authorized. | Consistent |
| M1-02/M1-03/M1-04 verification counts | M1-06 expects the full suite, golden gate, and CLI smokes to pass; it does not contradict earlier evidence. | Consistent |
| `neural/tests/golden/test_preprocess_authority.py` | The document correctly references `tests/golden/test_preprocess_authority.py` and notes that `authoritative_gate_not_run` is a blocker on Windows but not a pass. | Consistent |

---

## Recommendations Summary

1. **Before Sprint closure:** create `runbook.md`, `artifact-schema.md`, `m1-06-verification-evidence.md`, and `final-technical-report.md`, or explicitly defer them with owners.
2. **Before Sprint closure:** update `README.md` to reflect M1-06 status and link to the new runbook/artifact-schema documents.
3. **Inline the bound hashes** (ROOT, golden table, lock file integrity references) or provide explicit cross-references in M1-06 to reduce lookup errors during authority execution.
4. **Clarify** that `test_opening` is excluded from the required authority items for Sprint closure.
5. **Add document metadata** (status, version, date) to `sprint-m1-06.md` for revision control.

---

## Conclusion

`sprint-m1-06.md` is a scientifically sound and well-bounded plan for the final FR-001 phase. Its main gaps are documentary: four referenced deliverables do not yet exist, and the README/status references are stale. No correctness or scientific-safety violations were identified. The plan can be approved as the working Sprint definition once the missing document placeholders are created or explicitly deferred, and once the README metadata is updated.
