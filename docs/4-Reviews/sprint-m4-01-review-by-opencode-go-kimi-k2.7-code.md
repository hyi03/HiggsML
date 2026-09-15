# Sprint M4-01 Review — opencode / go-kimi-k2.7-code

- Review date: 2026-09-14
- Reviewer: opencode (model `deepseek/deepseek-v4-pro`)
- Method: read-only static comparison of `project/3-Plan/sprint-m4-01.md` and
  `project/1-Requirement/FR-401-m4l-off-feature-attribution.md` against
  `project/m4l-off-feature-attribution-plan.md` (the authority) and the current
  checkout of `src/`, `config/`, `scripts/`, `tests/`, `docs/`. No tests,
  training, MC runs, or assessment payload were executed or opened.
- Checkout: `879560b2c965c417fbbab12b131102e8b738ca89` (branch `codex/m4l-off-feature-attribution`).

## Scope and method

This review verifies that the sprint and the FR record the approved plan
faithfully (numbers, budgets, sequencing, statistical rules, scope exclusions,
and verification commands) and that their statements are consistent with the
actual repository source. It does **not** re-review the plan's scientific
design; the plan is the requirements authority per FR-401 and the sprint
preamble.

## Executive summary

The sprint and FR are faithful transcriptions of the plan. All hard numbers
cross-check cleanly against both the plan and the source: 15 non-empty
combinations × 5 seeds = 75 non-empty models (+5 `M0off` = 80 identities),
`C(15,2)=105` non-empty pairs, 24 conditional interactions (6 pairs × 4
conditioning subsets), `5^5=3125` joint seed resamples, 200 MC bootstrap
replicas, 500 Toys per injection/expectation/candidate at `mu=0,1,2`, and
20×100 T2 outer/inner replicas. Sequencing A→E, the off-only scope, the
no-retrain / no-commit / no-overwrite rules, and the six-primary-result paper
scope are all correctly reflected.

Findings are limited to **consistency/documentation and implementation-coupling
risks** — no Critical or High discrepancies were found. The two Medium findings
concern (1) an incorrect directory-existence claim plus a split review-root
convention, and (2) the existing exact-Shapley kernel being hard-coded to the
`M0c` empty set, which the plan forbids reusing as the off-family empty set.

## Findings

| ID | Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|---|
| S4-01-001 | Medium | Consistency | `project/1-Requirement/FR-401-m4l-off-feature-attribution.md` (备注) | FR states "neither root review directory existed in checkout" and sets `REVIEW_DIR=docs/4-Reviews`, but `project/4-Reviews/` **did** exist (it holds the readiness review the plan links to). The plan's relative link resolves to `project/4-Reviews/`, while new reviews are directed to `docs/4-Reviews/` (sprint §7 and this task), creating two review roots and a factually incorrect existence claim. | `project/4-Reviews/2026-09-14-academic-research-readiness-review.md` exists; plan line 18 links `4-Reviews/...`; FR line 42; sprint line 7. | Correct the FR 备注 existence claim. Adopt a single review root (`docs/4-Reviews/` is reasonable because `project/` is gitignored) and either repoint the plan's relative link or add an explicit note that `project/4-Reviews/` is historical-only. |
| S4-01-002 | Medium | Correctness / coupling | `src/higgsml/inference/reporting.py`; sprint §5(B); plan "Rejected Alternatives" | Existing exact-Shapley path hard-codes the empty-set candidate to `M0c:{seed}` and requires "a valid empty-set CDF". The plan explicitly forbids reusing `M0`/`M0c` as the off-family empty set, but says to "复用数学内核". Stage B must re-plumb the empty-set identity to `M0off`; the sprint/FR do not surface this hard-coded coupling in the reuse-audit checklist. | `reporting.py:92` `expected={subset:(f"M0c:{seed}" ...)}`; `reporting.py:263` `baseline_key = f"M0c:{seed}"`; `reporting.py:66` "including a valid empty-set CDF"; plan line 233 "不复用 M0 或 M0c 冒充 off-family 空集". | In Stage B, parameterize the empty-set candidate to `M0off` and add a test rejecting `M0`/`M0c` substitution (per plan Test Strategy). Add this coupling explicitly to the Stage A reuse-audit checklist so it is not silently carried over. |
| S4-01-003 | Low | Documentation | `docs/4-Reviews/sprint-m4-01-baseline-tests.txt` | Sprint §7/§10 claim the baseline is documented/persisted under `docs/4-Reviews`, but the file is empty (0 bytes). The plan's R6 requirement — record the current checkout test/dependency status before starting — is not actually satisfied by a non-empty record. | File has 0 lines; sprint lines 7, 10, 37; plan R6 (line 29). | Populate the baseline record (test result, `pip check`, environment, commit, dirty state) before Stage A closes; do not assume historical pass/fail counts carry forward. |
| S4-01-004 | Low | Environment / docs | `AGENTS.md` (Environment and commands); FR line 42; sprint lines 7, 37 | AGENTS.md prescribes `D:\apps\anaconda3\Scripts\conda.exe`, which does not exist on this machine. The sprint/FR correctly record the correction (local conda at `C:/Users/whchen/anaconda3`, Python 3.12.13), but AGENTS.md — the declared source of `VERIFICATION_COMMANDS` — is left stale. | `Test-Path "D:\apps\anaconda3\Scripts\conda.exe"` → False; `C:/Users/whchen/anaconda3/envs/pytorch/python.exe` → True; `environment.yml` `python=3.12.13`; `pyproject.toml` `requires-python = ">=3.12,<3.13"`. | Update the AGENTS.md conda path (or record an explicit fallback) so future automation does not use the stale path; keep it consistent with the repo's Python 3.12 pin. |
| S4-01-005 | Info | Scope | plan work package 0 (line 128); sprint line 22 | The plan's "six maintained documents" list omits `docs/data-and-processing.md`, which contains feature-attribution-relevant statements about the off-control and grouped-M3 retraining that may also need alignment once the off-only results replace the M5/M4 main comparison. | `docs/data-and-processing.md:65` ("registered grouped-M3 control independently retrains each nonempty subset with this explicit input present or absent"); lines 72–73 (off control). | Confirm whether `data-and-processing.md` (and any other affected docs) falls inside the synchronization scope; extend the doc list if the off-only scope changes those statements. |
| S4-01-006 | Info | Naming | `src/higgsml/inference/reporting.py`; plan line 57 | Existing code labels the value function `negative_mu_interval_width` / unit `mu_interval_width`; the new `feature_attribution_mass_off_v1` protocol specifies `-W68`. Semantically equivalent, but the label differs and will need reconciliation when the off-only overlay is added. | `reporting.py:85,231`; plan line 57 ("value function：-W68"). | Normalize the value-function label when adding the off-only overlay; keep old artifacts read-only and un-reinterpreted. |
| S4-01-007 | Info | Risk | `src/higgsml/inference/bootstrap.py`; plan Affected Components (line 113); sprint §5(C) | The existing MC bootstrap requires "all five paired M4/M5 models" and "physical-CDF neural bundles", while Stage C requires a raw (non-CDF) path over all 80 identities. The plan acknowledges this, but the sprint/FR do not restate that the Stage A reuse audit must verify raw-family eligibility separately from the CDF family. | `bootstrap.py:40` ("requires all five paired M4/M5 models"); `bootstrap.py:56` ("requires physical-CDF neural bundles"); plan lines 96, 147 ("本 raw family 不新增 CDF 变换"). | Keep raw-vs-CDF family eligibility as an explicit Stage A audit dimension, and add a test that the off-only bootstrap does not require physical-CDF bundles. |

## Cross-checks confirmed consistent

The following statements in the sprint and FR were verified against the plan and
source and found **consistent** (no findings):

- 80 identities = 75 non-empty (`15×5`) + 5 `M0off`; common grid for all 80.
  (`plan` line 95; `sprint` §5-B; `FR` line 21.)
- 105 non-empty pairs, no empty set. (`plan` line 141; `FR` line 21.)
- 24 conditional interactions `v(S∪{i,j})-v(S∪{i})-v(S∪{j})+v(S)` matching the
  existing `reporting.py:81` second-difference formula.
- 3125 joint seed resamples (`5^5`); 200 MC replicas; 500 Toys at `mu=0,1,2`;
  20×100 T2 replicas. (`plan` lines 58, 147, 154, 159, 164; `sprint` §5-C/D/E;
  `FR` line 21.)
- Sequencing A→B→C→D→E; B is an interim boundary, not C–E completion.
  (`plan` line 271; `sprint` §4/§6; `FR` line 39.)
- No retrain, no commit/push, no run overwrite, no new dependencies, no real
  data. (`plan` lines 126, 178; `sprint` §8/§9; `FR` lines 32, 42.)
- Six off-only paper result areas and exclusion of `m4l=on` from paper results.
  (`plan` lines 40–49; `sprint` §5-E.)
- Component inventory matches source: off-input restricted to grouped M3
  (`discriminants.py:135-136`), legacy M5/M4-CDF bootstrap
  (`bootstrap.py:40,56`), legacy M0 empty-set in templates/assessment
  (`templates.py:96`, `assessment.py:57-58`).
- Legacy protocol state (R1/R2): `validation_status=unvalidated`,
  `bound_mc_pilot=not_run`,
  `protocol_scope=synthetic_software_defaults_not_physics_validation`, and
  `automated-not-independent` references in `h4l_prepare.py:205-231` — all
  confirmed present in source.

## Conclusion

Sprint M4-01 and FR-401 faithfully record the approved plan; no scientific or
budget figures are mis-transcribed, and no Critical or High issues were found.
The plan is a valid authority for Stage A onward. Proceed after addressing the
two Medium items (S4-01-001 directory convention/claim and S4-01-002 `M0c`
empty-set coupling) and populating the empty baseline record (S4-01-003).
