# Document Review Report: Sprint M1-04 — One-shot Frozen Test Opening (`higgsml-xgboost open-test`)

- **Reviewer:** `deepseek/deepseek-v4-flash`
- **Review note:** This report is the configured fallback for a timed-out `opencode-go/glm-5.2`
  document review. The requested output path is preserved unchanged
  (`docs/4-Reviews/sprint-m1-04-review-by-opencode-go-glm-5.2.md`); the actual reviewer is
  identified as `deepseek/deepseek-v4-flash` per the fallback rule, as previously recorded for the
  M1-03 code review. No other Sprint M1-04 review report was read or relied on.
- **Review date:** 2026-09-02
- **Review type:** Document review
- **Review target (single target):**
  - `xgboost/docs/3-Plan/sprint-m1-04.md`
- **Governing sources:**
  - `xgboost/AGENTS.md` (frozen-state and scientific-safety constraints)
  - `xgboost/docs/1-Requirement/FR-001-angular19-xgboost-refactor.md` (FR-001, in particular R6/R7)
  - `xgboost/docs/superpowers/specs/2026-09-01-xgboost-refactor-design.md` (approved design;
    §6.3, §9, §10.1/§10.2, §11, §13.2/§13.3, §14 stage 5)
  - `xgboost/config/xgboost_protocol_v1.yaml` (frozen in M1-01, committed `409a728`)
  - Committed Sprint M1-03 contracts (commit `4e7d540`): `sprint-m1-03.md`,
    `docs/4-Reviews/sprint-m1-03-review-confirm.md`, `sprint-m1-03-code-review-confirm.md`,
    and implementation `src/training/{dataset,model,folds,trainer,evaluation,qualification}.py`,
    `src/cli/xgboost.py`, `tests/refactor_training_support.py`,
    `tests/integration/test_refactor_develop_cli.py`
  - Sprint-workflow acceptance gates: FR-001 §高层要求/§失败与降级/§验收要点, and the review/verify/
    commit evidence pattern established in `sprint-m1-01.md`/`sprint-m1-02.md`/`sprint-m1-03.md`
  - Sibling plans `sprint-m1-05.md` / `sprint-m1-06.md` (boundary consistency only)

**Verdict:** Pass with required actions. No Critical findings. Two High findings must be resolved
before M1-04 implementation starts, because they directly govern the sprint's core goal
(exactly-once test opening): (1) the plan introduces undefined terminal vocabulary
`test_reproduced` / `test_nonreproduction` that exists nowhere in FR-001, the approved design, or
protocol V1 and risks becoming an unauthorized test-result-based decision; (2) the claim state
machine is under-specified — the location of `state/test_opening.json`, the ordering of
validation/claim/test-parse, and which failure classes consume the opening right are not pinned,
which can break the once-only guarantee or burn a valid development run on a transient error.
A further High-adjacent Medium, the transitive binding of the frozen test artifact
(development run → upstream preprocess run manifest → `processed/test.csv.gz` dual-hash
verification before parse), is not specified and must be pinned to avoid scoring the wrong or
tampered file. No scientific-safety violation was found; the plan's boundaries
(synthetic-only, no real frozen-run opening, no real data) are correct.

---

## 1. Executive summary

Sprint M1-04 implements the final FR-001 lifecycle stage: `higgsml-xgboost open-test` consumes a
frozen, eligible development run and its bound held-out test exactly once, publishing test
evidence that never feeds back into training, thresholds, or any upstream decision. The plan's
scope (`src/training/test_opening.py`, the `open-test` CLI, metrics/predictions/plots/manifest and
the one-shot claim), its out-of-scope decision (no execution against real frozen runs), and its
risk controls (claim before test parse, failure receipt without test-content leakage, synthetic
fixtures only) match design stage 5 (design §14 阶段 5) and FR-001 R6/R7.

The plan is materially thinner than its M1-03 predecessor in the exact areas where M1-03's own
review forced precision: artifact layout, manifest schema, terminal status vocabulary, and
failure semantics. Because the entire purpose of this sprint is a single, irreversible claim, the
under-specification of the claim state machine and of the test-artifact binding path are not
cosmetic.

Required actions before implementation:

1. **Define or remove `test_reproduced`/`test_nonreproduction`** (§5.2 L57). Neither FR-001 nor the
   approved design nor protocol V1 defines these. If they denote an informational manifest status,
   define them against the design §10.2 test-run manifest and make explicit that no threshold or
   comparison is computed from test results; if they are meant to be a pass/fail "reproduction"
   judgement, they violate FR-001 R6 ("Test 只评价冻结模型，不得触发训练、调参、改阈值或回写
   development 决策") and must be removed or re-approved in the design ([H-1]).
2. **Pin the claim state machine** (§5.1/§6/§9): `state/test_opening.json` lives in the
   *development* run (design §10.1), the claim is created only after the new test run-dir is
   reserved and after eligibility/hash validation, strictly before any parse of test content, and
   only post-claim failures permanently consume the right — with an explicit list of which
   pre-claim refusal classes do not burn the slot ([H-2]).
3. **Pin the frozen-test-artifact binding path** (§5.2): open-test receives only
   `--development-run`; the test CSV location and its compressed/canonical hashes are obtained
   transitively via the bound upstream preprocess run manifest, and both hashes plus row/column
   counts must be re-verified before any parse or scoring ([H-3]/[M-3]).
4. Address the Medium findings: pre-register the full-suite boundary (M1-03 recorded
   `826 passed, 211 failed, 4 skipped`) ([M-1]); replace or harden the `-k` focused gate ([M-2]);
   pin test-metric semantics and the source of the applied thresholds ([M-4]); extend the shared
   fixture to emit a *well-formed* test partition with valid dual hashes so the eligible
   full-chain smoke can actually run ([M-5]); pin the test-run layout/manifest and the
   failure-receipt semantics per design §10.2 and FR-001 R7 ([M-6]).
5. Address the Low/Info items in §7.

---

## 2. Scope, method, and repository grounding

Checks performed: sprint-to-design-stage-5 coverage; FR-001 R6/R7 coverage; scientific-safety
compliance against `AGENTS.md`; cross-sprint contract consistency (M1-03 committed development
run → M1-04 test opening); exactly-once and no-clobber semantics; acceptance-criterion-to-
verification mapping; test-requirement completeness against design §13.2/§13.3; repository
grounding against the committed M1-03 implementation and test fixtures.

Repository facts verified in this worktree (branch `codex/xgboost-refactor`, HEAD `4e7d540`,
`git status --short` shows `docs/3-Plan/sprint-m1-04.md`, `sprint-m1-05.md`, `sprint-m1-06.md`
untracked — M1-03 is committed and the sibling plans remain unstaged):

- The M1-03 precondition is satisfied: commit `4e7d540` ("feat: complete sprint-m1-03 code and
  change base on reviews") delivers the development lifecycle and records
  `826 passed, 211 failed, 4 skipped` in its §10.3.
- The handoff point is real: `src/cli/xgboost.py:20-23` already exposes the `open-test` subparser
  with exactly `--development-run` and `--run-dir`, and `main` (`:44`) currently raises
  `SystemExit("open-test implementation is delivered by Sprint M1-04")`.
- The committed development manifest (`src/training/trainer.py:469-496`) records `schema_version`,
  `run_type="xgboost_development"`, `status`, `test_opened: false`, `protocol`, `code`, `software`,
  `upstream_run` (path + preprocess manifest path/SHA-256 + protocol/run-config identity +
  development CSV dual hashes), `candidate`, `selected_candidate`, `final_parameters`,
  `working_points`, `qualification`, `outputs` (with per-file receipts incl. `model`, `oof_scores`
  dual hashes, `working_points`, `qualification`), `counts`, `schema` — grounding for [H-3]/[M-3]
  and [M-6].
- The committed development layout (`test_refactor_develop_cli.py:53-67,99-108`) is exactly the
  nine-file eligible / eight-file ineligible layout with **no** `state/test_opening.json`;
  `state/` is created only by M1-04 open-test (design §10.1).
- The development manifest's `upstream_run` payload binds the preprocess run and its manifest
  SHA-256 plus only the **development** CSV hashes; it does **not** store the `test.csv.gz` path
  or hashes directly. The preprocess manifest (`tests/refactor_training_support.py:57-98`) records
  `outputs.test` with `path="processed/test.csv.gz"`, `rows`, `columns`, `sha256_compressed`,
  `sha256_canonical_csv`, `size_bytes` — the transitive binding source for open-test — grounding
  for [H-3].
- The committed shared fixture `write_preprocess_run` (`tests/refactor_training_support.py:47-102`)
  deliberately writes `processed/test.csv.gz` as `b"forbidden held-out test"` and records dummy
  test hashes (`"e"*64`/`"f"*64`) because M1-03's develop path must never read it. It therefore
  cannot be reused as-is for an eligible open-test full-chain fixture — grounding for [M-5].
- M1-03's development manifest `status` values are `"eligible"` | `"no_eligible_candidate"`
  (`qualification.py:84`); eligibility is recorded both in `qualification.json` and the manifest.
  `test_opened: false` is fixed at develop time and is never updated by develop (M1-03 trainer
  writes it once), so the authoritative "opened once" record after M1-04 is the claim file — a
  fact the plan does not state ([H-2]/[M-6]).
- Vocabulary check: `test_reproduced` / `test_nonreproduction` appear **only** in legacy,
  frozen experimental designs (`2026-08-11-mass-bin-iterative-reweighting-design.md`,
  `2026-08-12-drop-top4-mass-bin-reweighting.md`, `2026-08-11-mass-sculpting-ablation.md`) and their
  run modules — not in FR-001, not in the approved 2026-09-01 refactor design, not in
  `xgboost_protocol_v1.yaml` — grounding for [H-1].
- The approved test-run layout (design §10.2) is `runs/xgboost-test-<id>/` with
  `artifacts/{test_metrics.json, manifest.json}`, `predictions/test_scores.csv.gz`, `plots/` and
  **no** `state/` and no `config.yaml` — the claim belongs to the development run layout
  (design §10.1). The plan does not cite or pin either layout ([M-6]).
- Design §11/FR-001 R7 failure semantics ("失败 run 写失败收据但不写成功 manifest") apply to the
  new test run; the plan's §9 "Receipt 记录失败阶段但不泄露 test 内容" is consistent but the
  receipt file/schema and its relationship to the claim are not pinned ([H-2]/[M-6]).
- The committed xgboost protocol (`config/xgboost_protocol_v1.yaml`) has no test-reproduction
  thresholds or terminal-status vocabulary; the working-point values `loose/medium/tight` are
  *target background efficiencies*, and the frozen *score thresholds* are stored in the
  development run's `working_points.json` — grounding for [M-4] (thresholds must come from the
  frozen dev run, not the protocol).
- This worktree has no authoritative ROOT, no frozen runs, and no `data/raw/`; `runs/` holds only
  `.gitkeep`. No real data, frozen run, or held-out test content was accessed during this review.

---

## 3. Coverage assessment

| Source requirement | Sprint M1-04 coverage | Assessment |
|---|---|---|
| Design §14 阶段 5 (L500-506): upstream binding, full hash re-check, atomic claim; load frozen model, publish test metrics; cover double-open, tamper, missing evidence, failure terminal | §5.1 binding/claim; §5.2 evaluation; §5.1 tests | Covered at a high level; claim state machine/location not pinned [H-2]; test artifact transitive binding not specified [H-3] |
| FR-001 R6 (L84-88): validate manifest/protocol/input/model/working points/OOF binding; atomic claim, one open per run, failure also consumes; test only evaluates frozen model | §1 goal; §5.1; §6 bullets 1-4 | Covered; `test_reproduced`/`test_nonreproduction` risk a test-result decision [H-1]; "which failures consume" ambiguous [H-2] |
| FR-001 R7 (L92-95): fresh no-clobber run dirs; occupied output rejected before input read; failure writes receipt, no success manifest; manifest binds protocol/config/code/software/inputs/outputs/schema/counts/hash | §9 risk (implied), §3 manifest | Failure receipt semantics and test-run manifest schema not pinned [M-6]; runs-root/no-clobber reuse of `RunTransaction` not stated [L-2] |
| Design §10.2 test-run layout (L366-376) | §3 "test metrics、predictions、plots、manifest"; §5.2 "发布 scores、AUC/KS/效率、图和 manifest" | Referenced loosely; exact layout and manifest schema not pinned [M-6] |
| Design §10.1 dev-run `state/test_opening.json` (created by open-test claim) (L348-364) | §5.1 "no-clobber state/test_opening.json claim" | Claim file name given; location (development run, not test run) not stated [H-2] |
| Design §13.2/§13.3 test matrix (hash change, duplicate, retry-after-failure, concurrency, eligible fixture one open) | §5.1 tests; §6 bullet 2; §5.3 test | Covered; fixture to produce a *well-formed* frozen test partition not described [M-5] |
| M1-03 committed contract (manifest fields, layout, `status` vocabulary, no `state/` at develop) | §5.1 "校验 eligible、模型、protocol、preprocess、OOF、工作点和 manifest" | Verified categories only; exact artifact fields to re-hash not enumerated [M-3] |
| Sprint-workflow gates (review/confirm/verify/commit evidence; full-suite boundary pre-registration) | §10 placeholder; §7 full suite | Full-suite boundary not pre-registered vs M1-03 `826/211/4` [M-1]; focused `-k` naming coupling [M-2]; §10 empty [L-1] |

---

## 4. Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| High | Requirement / Clarity | sprint-m1-04 §5.2 (L57); §3 (L24); FR-001 R6 (L84-88); design §10.2 (L366-376) | **[H-1]** The terminal vocabulary `test_reproduced` / `test_nonreproduction` is undefined and has no authority in this refactor. It does not exist in FR-001, the approved 2026-09-01 design, or `xgboost_protocol_v1.yaml`; it appears only in frozen legacy experiment designs (`2026-08-11-mass-bin-iterative-reweighting-design.md`, `2026-08-12-drop-top4-mass-bin-reweighting.md`, `2026-08-11-mass-sculpting-ablation.md`) where it encodes a test-vs-development quality decision with predeclared thresholds. Adopting it here, with no definition, location, or criterion, risks reintroducing a test-result-based classification ("did the test reproduce development?") that FR-001 R6 and design §9 forbid ("test 结果不触发重训、改阈值、改候选或回写 development 决策"), and reuses vocabulary the AGENTS.md freeze treats as a different, closed scientific context. | sprint L57: "明确 `test_reproduced`/`test_nonreproduction`，不回写训练决策。"; `rg` across `docs/`, `src/`, `config/` shows these terms only in legacy mass-bin/sculpting artifacts; FR-001 L84-88; design §10.2 defines a test run of `test_metrics.json` + `manifest.json` with no reproduction status; protocol V1 has no such statuses | Define precisely in §5.2/§10 what these states mean, which artifact records them (test-run manifest `status`? `test_metrics.json`?), and state explicitly that no comparison threshold or decision is derived from test results — or remove them and use an ordinary success status per design §10.2. If a "reproduction" judgement is intended, it must first be added to the approved design and re-reviewed, per the "result-produced rules are not allowed post hoc" discipline. |
| High | Correctness / Risk | sprint-m1-04 §5.1 (L37-47), §6 (L76-81), §9 (L102-106); FR-001 R6 (L86-87); design §10.1 (L362-363), §11 (L392-393) | **[H-2]** The claim state machine is under-specified, and the sprint's core property (exactly-once) depends on it. The plan never states that `state/test_opening.json` is written into the **development run** directory (design §10.1: the dev-run layout owns `state/test_opening.json`, "created by open-test claim"), not the fresh test run-dir. If the claim were scoped to the test run-dir, a second `open-test --development-run <same-dev> --run-dir <different>` would create a new claim and reopen the held-out test, violating FR-001 R6 ("一个 development run 只能开启一次 test"). The plan also does not fix the ordering: reserve new test run-dir (no-clobber, before input reads) → validate eligibility/hashes without parsing test → atomically claim → parse/score test → publish; and does not enumerate which failure classes consume the right (only post-claim failures should be permanent, so a transient validation error or an occupied run-dir does not burn a valid eligible run). The existing M1-03 develop integration tests (`test_refactor_develop_cli.py:111-161`) already prove the occupied-output/tamper patterns the open-test path must mirror; the plan neither references them nor defines the open-test analogue. | sprint L42: "实现 no-clobber `state/test_opening.json` claim。"; L43: "成功或失败均写终态 receipt，拒绝二次开启。"; L105: "Claim 必须早于 test 文件解析。"; design §10.1 places `state/test_opening.json` under the dev run; design §11 "test-opening claim 一旦成功占用，后续成功或失败均不得再次开启"; `src/cli/xgboost.py:20-23` (open-test takes `--development-run` + `--run-dir`) | Pin in §5.1: (a) the claim file is created inside the *development* run at `state/test_opening.json` and is the single authoritative "opened" record (the dev manifest `test_opened: false` is fixed at develop time and never rewritten); (b) ordering: no-clobber reservation of the new test run-dir and all eligibility/hash validation complete before the claim is atomically created, and the claim is created strictly before any test-content read/parse; (c) only post-claim failures consume the right; pre-claim refusals (ineligible, missing file, hash drift, occupied run-dir) write a failure receipt without creating a claim. Add tests for second-open with a *different* test run-dir and for occupied-run-dir-does-not-consume. |
| Medium | Correctness / Requirement | sprint-m1-04 §5.2 (L53-57), §5.1 (L41); FR-001 R6 (L84-85); design §8.3 (L314-315), §10.2 (L366-376) | **[H-3→M]** The binding path to the frozen test artifact is not specified. open-test receives only `--development-run`. The committed dev manifest (`trainer.py:357-373,469-496`) binds the upstream preprocess run path and manifest SHA-256 plus only the *development* CSV dual hashes; it does not store `test.csv.gz` path/hashes. To locate and authenticate the held-out test, open-test must read the bound preprocess run manifest (verifying its SHA-256 against the dev manifest), take `outputs.test.path` / `rows` / `columns` / `sha256_compressed` / `sha256_canonical_csv`, then re-verify both hashes and the row/column count of the actual `processed/test.csv.gz` **before** any parse. The plan says only "校验 … preprocess …" and "读取绑定 test artifact，校验 19 特征与 identity" without this transitive, dual-hash verification chain. | sprint L41: "校验 eligible、模型、protocol、preprocess、OOF、工作点和 manifest。"; L55: "读取绑定 test artifact，校验 19 特征与 identity。"; `src/training/trainer.py:357-373` `_upstream_payload` (development hashes only); `tests/refactor_training_support.py:77-84` (preprocess manifest `outputs.test` records path/rows/columns/dual hashes); design §8.3 dual compressed/canonical hashes | Specify in §5.2 the full chain: dev manifest → bound upstream preprocess run → preprocess manifest SHA-256 re-verification → `outputs.test` record → read `processed/test.csv.gz` → verify `sha256_compressed` and `sha256_canonical_csv` and row/column consistency → then schema/identity validation (32-column order, 19 features, `split == {"test"}`, labels {0,1}, unique identity, finite values) → score with the frozen model. Add an explicit tamper test on `test.csv.gz`. |
| Medium | Verification / Risk | sprint-m1-04 §7 (L85-92); M1-03 §10.3 (L215-218); FR-001 §失败与降级 (L130-133) | **[M-1]** §7 lists `python -m pytest -q` but does not pre-register the full-suite acceptance boundary. After M1-03 the recorded full-suite state is `826 passed, 211 failed, 4 skipped` (exit 1 until M1-05/M1-06 remove the legacy surface). M1-02 and M1-03 each pre-registered their gate interpretation ("no new failures, no failure-set growth, no sprint-attributable failures"); M1-04 does not, so a later "full suite passed" claim has no fixed comparison point and a regression in the 211-failure set would be undetectable from the plan alone. | sprint L87: "`python -m pytest -q`"; M1-03 §10.3 L215-218 records `826 passed, 211 failed, 4 skipped, 5 warnings`; M1-02 §7 and M1-03 §7 both pre-registered the boundary in-plan | Add to §7 the pre-registered gate: full suite judged against the M1-03-recorded `826 passed, 211 failed, 4 skipped` boundary — no new failures, no expansion of the 211 failure-id set, no M1-04-attributable failure — with exact counts recorded in §10 at delivery. |
| Medium | Test / Consistency | sprint-m1-04 §7 (L91); M1-03 §7 (L160-161); M1-02 review [M-4] | **[M-2]** The focused gate `python -m pytest -q tests/unit tests/integration -k "test_opening or open_test"` silently depends on M1-04 test file/function names containing `test_opening` or `open_test`. The existing refactor test files follow `test_refactor_*.py` naming; if the new unit tests are named e.g. `test_refactor_claim.py` or `test_refactor_opens_test.py` with node ids that do not contain the filter tokens, they fall out of the focused gate without warning. M1-03 §7 used an explicit file list; M1-04 regresses to a naming-coupled `-k`. | sprint L91: `-k "test_opening or open_test"`; existing files `tests/unit/test_refactor_training_*.py`, `tests/integration/test_refactor_develop_cli.py` (none match these tokens); M1-03 §7 lists explicit files | Replace the `-k` filter with an explicit file list (e.g. `tests/unit/test_refactor_test_opening.py`, `tests/integration/test_refactor_open_test_cli.py`), or state the required test-naming convention and add a guard so any new test not matched by the filter fails loudly. |
| Medium | Correctness / Requirement | sprint-m1-04 §5.2 (L53-57); M1-03 committed `src/training/evaluation.py`; `config/xgboost_protocol_v1.yaml:38-41` | **[M-4]** Test-metric semantics and the source of the applied thresholds are not pinned. §5.2 says "发布 scores、AUC/KS/效率、图和 manifest" but not: (a) that metrics reuse the committed `evaluation.py` semantics (weighted AUC with `abs(physical_weight)`; KS between inclusive ZZ and threshold-selected ZZ on `m4l` using signed `physical_weight` with its internal abs semantics; efficiency = selected-class `abs(physical_weight)` sum / inclusive-class sum); (b) that the *score thresholds* applied to test scores are the frozen per-point `threshold` values in the development run's `working_points.json`, **not** the protocol `loose/medium/tight` target efficiencies (`0.50/0.20/0.10`) and **not** recomputed from test; (c) that test scoring never recomputes OOF, working points, or thresholds. A divergent metric implementation would silently break behavior-equivalence and the "frozen working points" guarantee. | sprint L53-56: "只加载冻结模型和冻结工作点产生 test 证据…发布 scores、AUC/KS/效率、图和 manifest"; `src/training/evaluation.py` (weighted AUC, retention threshold, KS, efficiency); `config/xgboost_protocol_v1.yaml:38-41` working_points are target efficiencies; dev-run `working_points.json` (M1-03 trainer) stores computed thresholds | Specify in §5.2 that test AUC/KS/efficiency reuse the committed `evaluation.py` definitions, that the applied thresholds are read from the frozen development run's `working_points.json` (not derived from protocol targets or test data), and add golden/unit tests asserting test metrics are invariant under re-derivation attempts. |
| Medium | Test / Risk | sprint-m1-04 §5.3 (L74), §7 (L92); `tests/refactor_training_support.py:47-102` | **[M-5]** The committed shared fixture cannot support the promised eligible full-chain open-test smoke. `write_preprocess_run` deliberately writes `test.csv.gz` as `b"forbidden held-out test"` with dummy manifest hashes (`"e"*64`/`"f"*64`) because develop must never read it. An eligible open-test run requires a *well-formed* frozen test partition (valid gzip CSV, 32-column ordered schema, `split == test`, correct compressed/canonical hashes, row/column counts matching the preprocess manifest `outputs.test`), plus an eligible development run whose `upstream_run` binds that same preprocess run. The plan does not describe extending the fixture or adding a valid-test builder, so the §5.3 "全链成功" and §7 "合成 eligible fixture CLI smoke" may be unachievable with current helpers. | sprint L74: "Eligible fixture 全链成功且第二次调用失败。"; L92: "合成 eligible fixture CLI smoke。"; `tests/refactor_training_support.py:47-102` (test artifact = `b"forbidden held-out test"`, dummy hashes); `tests/integration/test_refactor_develop_cli.py:27-49` (same fixture, valid development partition) | Add a fixture (e.g. `write_preprocess_run(..., real_test=True)` or a new `write_test_partition`) that emits a valid `test.csv.gz` with correct dual hashes and matching manifest rows/columns, and state that the eligible full-chain test drives open-test against it end-to-end (including a second invocation with a different run-dir asserting refusal per [H-2]). |
| Medium | Requirement / Consistency | sprint-m1-04 §3 (L20-25), §5.2 (L53-57); design §10.2 (L366-376); FR-001 R7 (L92-95) | **[M-6]** The test-run artifact layout and manifest schema are not pinned, and the failure-receipt semantics are not stated. Design §10.2 fixes `runs/xgboost-test-<id>/` = `artifacts/{test_metrics.json, manifest.json}`, `predictions/test_scores.csv.gz`, `plots/` (no `state/`, no `config.yaml`). The plan lists only generic "test metrics、predictions、plots、manifest" and never enumerates the files, the ordered `test_scores.csv.gz` columns, the manifest fields (extend the M1-03 manifest pattern with `run_type="xgboost_test"`, upstream dev-run + claim binding, test counts/schema/hashes), or that a failed open-test writes a failure receipt and never a success manifest (FR-001 R7 / design §11). M1-03's review forced exactly this kind of pinning for the development layout; M1-04 repeats the gap on its own output contract. | sprint L20-25, L53-57; design §10.2 (layout); `src/training/trainer.py:469-496` (manifest precedent); FR-001 R7 L92-95; design §11 L387-393 | Reference design §10.2 in §5.2 and enumerate the exact test-run layout, the manifest fields (schema/run type/status/protocol/code/software/upstream dev-run binding with claim path + SHA-256/outputs/counts/schema/hashes), the ordered prediction columns, and the failure rule (failure.json, no manifest). |
| Low | Process / Documentation | sprint-m1-04 §10 (L110); FR-001 §高层要求 (L109-110), §验收要点 (L161); sprint-m1-03 §10 | **[L-1]** §10 is a bare "待实施、评审和验证后填写" placeholder; FR-001 makes per-sprint document review, code review, verification, and commit evidence mandatory and blocking, and prior sprints pre-populated §10 with an evidence checklist (M1-03 §10.1-10.4). | sprint L110; FR-001 L109-110, L161; M1-03 §10 structure | Pre-populate §10 with the four evidence classes (document review + confirm, code review + confirm, verification outputs incl. the [M-1] boundary, and the sprint commit hash) so the delivery records are unambiguous. |
| Low | Clarity / Maintainability | sprint-m1-04 §5.1 (L37, L42); M1-03 `src/training/trainer.py:385-389` | **[L-2]** §5.1 "布局" and the claim/receipt file split are ambiguous: the plan does not say the new test run-dir must be a fresh direct child of a `runs/` root reserved no-clobber via the committed `RunTransaction` (M1-03 develop enforces `destination.parent.name == "runs"`), nor whether the "receipt" is the claim file itself, a `failure.json` in the test run, or both. | sprint L37: "在读取 test 前完成资格、布局和哈希验证并原子占用。"; L42-43 claim/receipt wording; `src/training/trainer.py:385-389` (runs-root + transaction usage precedent) | State that the new test run-dir reuses the committed no-clobber `RunTransaction` under a `runs/` root, and distinguish the claim file (development run `state/test_opening.json`, durable opened marker) from the test run's failure/success artifacts. |
| Low | Traceability | sprint-m1-04 §2 (L16-18) | **[L-3]** §2 lists the predecessor sprints without relative links to FR-001 or the approved design, and without naming the specific M1-03 contract consumed (development run manifest + `state/test_opening.json` absence). M1-02/M1-03 §2 carried these links. | sprint L16-18; sprint-m1-03 §2 L17-22 | Add relative links to FR-001 and the approved design in §2, and state the exact M1-03 contract M1-04 consumes (eligible-only dev run, manifest schema, no `state/test_opening.json` at develop time). |
| Info | Consistency (positive) | sprint-m1-04 §4 (L29-31), §9 (L104-106); FR-001 §不纳入范围 (L139-140); AGENTS.md 冻结状态 | **[I-1]** Scientific-safety boundaries are correct: real frozen-run test-opening is explicitly out of scope; integration tests use only temp synthetic test artifacts; claim precedes test parse; the receipt records the failure stage without leaking test content; nothing reads real data or reuses frozen Full14/363490 runs. This matches AGENTS.md freeze and FR-001 "不自动执行 held-out test-opening". | sprint L29-31, L104-106; FR-001 L139-140; AGENTS.md 当前授权工作/冻结状态 | No change; carry these constraints into implementation and record the unexecuted authoritative boundary in §10. |
| Info | Requirement coverage (positive) | sprint-m1-04 §6 (L78-81); FR-001 R6 (L84-88); design §14 阶段 5 验收 (L506) | **[I-2]** §6 acceptance bullets directly operationalize FR-001 R6 and the design stage-5 acceptance: only complete/eligible/unopened runs enter test; exactly one concurrent claim winner; no reopen after failure; test never triggers training or writes back decisions. The `no_eligible_candidate`/ineligible refusal path is correctly framed as a normal terminal state. | sprint L78-81; FR-001 L84-88; design L506 | No change; when implementing [H-2], ensure each bullet has a named test (ineligible refusal, concurrent single-winner, second-open refusal with fresh run-dir, no-writeback assertion). |

---

## 5. Positive observations

- **The sprint boundary is correct and the deferral is clean.** Real frozen-run test-opening is
  correctly excluded; M1-04 proves the mechanism on synthetic fixtures, matching FR-001 §不纳入
  范围 and AGENTS.md, and M1-05/M1-06 inherit a closed lifecycle.
- **The M1-03 handoff is consumable.** The committed development run already binds status,
  working points, qualification, model, and OOF receipts, and the CLI skeleton
  (`src/cli/xgboost.py:20-23`) already exposes the exact approved `open-test` parameter surface
  (`--development-run`, `--run-dir`), so the application service can be wired without parser or
  contract changes.
- **Risk controls restate the strongest invariant.** "Claim 必须早于 test 文件解析" and "Receipt
  记录失败阶段但不泄露 test 内容" are the correct anti-peeking controls; combined with the
  no-clobber discipline established in M1-01/M1-03 they give the plan a sound spine.
- **TDD sequencing is sound.** Upstream validation and the claim come before scoring and CLI, and
  concurrency/failure/tamper coverage is scheduled before final verification.

---

## 6. Relation to prior reviews

This review continues the M1-01/M1-02/M1-03 review cycle and reuses the established evidence
discipline. Carry-forward patterns: the artifact-layout/manifest pinning forced on M1-03
(`sprint-m1-03` [H-4]) recurs for the test-run output contract ([M-6]); the full-suite boundary
pre-registration ([M-1] in M1-02 and M1-03) recurs as [M-1] with the updated M1-03 boundary
(`826/211/4`); the focused `-k` naming coupling ([M-2] in M1-03, resolved by explicit file lists)
recurs as [M-2]; the §10 evidence placeholder ([L-1]) and missing §2 links ([L-3]) recur.
New findings specific to M1-04's test-opening contract: [H-1] unauthorized/undefined
`test_reproduced`/`test_nonreproduction` vocabulary; [H-2] under-specified claim state machine
(location, ordering, consumption semantics); [H-3→M] transitive frozen-test-artifact binding path;
[M-4] test-metric semantics/threshold source; [M-5] fixture cannot yet produce a well-formed frozen
test partition. The M1-03 review confirmants already reserved this sprint's ownership of
`state/test_opening.json` ("该 claim 只属于 M1-04 `open-test`"), confirming the plan's scope but
not its state-machine precision.

---

## 7. Conclusion and required actions

The sprint plan is ready for implementation after these document edits:

1. Remove or precisely define `test_reproduced`/`test_nonreproduction`, and explicitly rule out any
   test-result-derived decision or threshold ([H-1]).
2. Pin the claim state machine: claim file lives in the *development* run `state/test_opening.json`;
   ordering = reserve new test run-dir → validate eligibility/hashes (no test parse) → atomically
   claim → parse/score → publish; only post-claim failures consume the right ([H-2]).
3. Pin the transitive test-artifact binding: dev manifest → bound preprocess manifest (SHA-256) →
   `outputs.test` → dual compressed/canonical hash + row/column verification before parse ([H-3]).
4. Pre-register the full-suite gate against the M1-03 `826 passed, 211 failed, 4 skipped` boundary
   ([M-1]); harden or replace the `-k` focused gate ([M-2]).
5. Pin test-metric semantics and the use of frozen `working_points.json` thresholds ([M-4]);
   extend the shared fixture to emit a well-formed frozen test partition ([M-5]); pin the test-run
   layout/manifest and failure-receipt semantics per design §10.2 and FR-001 R7 ([M-6]).
6. Pre-populate the §10 evidence checklist ([L-1]); clarify run-dir reservation and
   claim-vs-receipt files ([L-2]); add FR-001/design links and the exact M1-03 contract to §2
   ([L-3]).

None of these actions change scientific scope, model parameters, thresholds, split/fold semantics,
or any frozen artifact; they make the sprint's own acceptance criteria (exactly-once, binding,
failure semantics) verifiable and close the contract gaps the implementation would otherwise have
to guess.

**Verification performed for this review:** full read of the target sprint and all governing
sources (AGENTS.md, FR-001, approved 2026-09-01 design, `xgboost_protocol_v1.yaml`,
`sprint-m1-03.md` and its review/confirm evidence, sibling plans M1-05/M1-06); repository grounding
via `src/cli/xgboost.py`, `src/training/trainer.py` (development run layout, manifest schema,
`_upstream_payload`), `src/training/{dataset,qualification,evaluation}.py` (upstream binding,
status vocabulary, metric semantics), `src/preprocessing/pipeline.py`
(`MODEL_FEATURES`/`OUTPUT_COLUMNS`), `tests/refactor_training_support.py`,
`tests/integration/test_refactor_develop_cli.py`, `git log`/`git show 4e7d540`/`git status`.
Document-only review: no code was changed, no tests were run, no real data or held-out test
content was read, and no frozen runs or authoritative ROOT files were accessed.
