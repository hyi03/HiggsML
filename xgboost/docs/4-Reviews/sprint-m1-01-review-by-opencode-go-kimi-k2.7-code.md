# Document Review Report: Sprint M1-01 / FR-001 Angular19 XGBoost Refactor

**Reviewer:** OpenCode / `opencode-go/kimi-k2.7-code`  
**Review date:** 2026-09-01  
**Review type:** Document review  
**Target documents:**

- `xgboost/docs/1-Requirement/FR-001-angular19-xgboost-refactor.md`
- `xgboost/docs/3-Plan/sprint-m1-01.md`

**Governing sources:**

- `xgboost/AGENTS.md`
- `xgboost/docs/superpowers/specs/2026-09-01-xgboost-refactor-design.md`

---

## 1. Executive summary

The two target documents are broadly aligned with the approved 2026-09-01 refactor design and with the scientific-safety constraints in `AGENTS.md`. FR-001 correctly captures the MC-only scope, the fixed Base14 + Angular5 feature set, the frozen protocol/CLI policy, the development/test separation, and the immutable-run semantics. Sprint M1-01 appropriately limits itself to establishing a baseline, package skeleton, protocol schema, CLI skeleton, and artifact transaction layer.

However, several governance and planning gaps should be closed before execution proceeds:

1. `AGENTS.md` declares the next stage must be *decorrelation-aware training*, while the approved design and FR-001 pursue an *Angular19 refactor*. This governing-source conflict must be reconciled explicitly.
2. FR-001 plans 6 sprints, but the approved design has 7 stages; no mapping is documented.
3. Sprint M1-01 verification uses module invocation (`python -m src.cli.*`) instead of the approved console scripts (`higgsml-preprocess`, `higgsml-xgboost`).
4. Review-confirm evidence required by FR-001 is not explicitly scheduled in the sprint deliverables.
5. The sprint scope omits creation of several target directories shown in the approved package structure.

No critical scientific-safety defects were found in the target documents themselves.

---

## 2. Scope and method

The review compared the requirement and sprint plan against the approved design specification and the project `AGENTS.md`. Checks covered:

- Requirement coverage (structure, MC-only preprocessing, protocol/CLI, scientific equivalence, development/test lifecycle, artifact semantics, historical removal).
- Scientific safety (no real-data training, no held-out test leakage, no forbidden features, frozen thresholds, immutable runs).
- Consistency between governing sources and target documents.
- Clarity and actionability of sprint tasks, acceptance criteria, and verification steps.
- Missing evidence or placeholders that could block execution or review.

---

## 3. Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| High | Governance / source conflict | FR-001 §高层要求; `AGENTS.md` §当前冻结状态 | `AGENTS.md` declares the next stage must be native decorrelation-aware training, whereas FR-001 and the 2026-09-01 approved design implement an Angular19 refactor. Without explicit reconciliation, the FR can be read as violating the governing frozen-state constraint. | `AGENTS.md`: "当前下一阶段是质量去相关训练研究"; "下一阶段必须另行预先设计原生质量去相关训练，使用新配置和新 run path". FR-001: "本 FR 以已批准设计为唯一设计来源" and implements Angular19 refactor. | Update `AGENTS.md` to record the 2026-09-01 refactor design as the authorized next stage, or add an explicit supersession note in FR-001 referencing the newer approved design. |
| High | Planning / coverage gap | FR-001 §备注; Sprint M1-01 §1 | FR-001 splits the work into six sprints (`m1-01` through `m1-06`), while the approved design defines seven stages. No sprint-to-stage mapping is documented. | FR-001: "实施拆分为 `sprint-m1-01` 至 `sprint-m1-06`，必须严格顺序执行。" Design §14: stages 1 (worktree + baseline) through 7 (full-chain validation/delivery). | Add an explicit sprint-to-design-stage mapping (e.g., in Sprint M1-01 or a master plan) so that design stage 7 is not dropped or ambiguously merged. |
| Medium | Verification / CLI naming | Sprint M1-01 §7 | Sprint verification uses `python -m src.cli.preprocess --help` and `python -m src.cli.xgboost --help`, not the approved console scripts `higgsml-preprocess` and `higgsml-xgboost`. | Design §6 CLI: console scripts are `higgsml-preprocess` and `higgsml-xgboost`. Sprint §7 verification commands use module paths. | Add an installation step (`pip install -e .`) and verify the actual entry points `higgsml-preprocess --help` and `higgsml-xgboost --help`; keep module invocation as an additional developer check. |
| Medium | Scope / skeleton completeness | Sprint M1-01 §3; Design §5 | Sprint scope lists only `src/cli/`, `src/config.py`, and `src/artifacts/`; it omits `src/domain/`, `src/preprocessing/`, and `src/training/` directories required by the approved package structure. | Design §5 structure includes `src/domain/`, `src/preprocessing/`, and `src/training/`. Sprint §3 scope omits them. | Expand Sprint M1-01 scope to create the full target directory skeleton, including `__init__.py` files, to establish import boundaries and package layout. |
| Medium | Process / review evidence | Sprint M1-01 §10; FR-001 §高层要求 | The sprint deliverables section is a placeholder and does not enumerate the document review, code review, verification, and submission evidence that FR-001 says cannot be skipped. | FR-001: "独立文档/代码评审与 review-confirm 证据不得跳过". Sprint §10: "待实施、评审和验证后填写". | Add a review-confirm checklist and expected evidence artifacts (review reports, test logs, commit hashes, signatures) to the sprint deliverables. |
| Medium | Scope / baseline | Sprint M1-01 §5.1; Design §14 Stage 1 | Sprint M1-01 does not include design-stage-1 tasks: creating an isolated worktree, recording branch/Git state and Python environment, running existing tests, and saving the baseline. | Design §14 stage 1 lists worktree creation, environment recording, baseline tests. Sprint §5.1 only says "增加不改变生产代码的 characterization/golden tests". | Add explicit baseline tasks and evidence requirements to Sprint M1-01 §5.1 or a new section. |
| Low | Completeness / structure | FR-001 §R1 | FR-001 lists `src/cli`, `src/domain`, `src/preprocessing`, `src/training`, and `src/artifacts` but omits `src/config.py`, which appears at the top level of the approved structure. | Design §5 structure shows `src/config.py`. FR-001 §R1 omits it. | Add `src/config.py` to the directory list in FR-001 §R1. |
| Low | Template / unset field | FR-001 §备注 | `WORKFLOW_STATE_PATH=<unset>` is left as a placeholder. | FR-001 §备注: `WORKFLOW_STATE_PATH=<unset>`. | Either set the expected workflow-state path or remove the placeholder if it is not used by the project automation. |
| Info | Precision policy | Sprint M1-01 §5.1; FR-001 §R4 | Float-equivalence rules must be fixed before migration, but neither document names the actual tolerance, relative/absolute threshold, or bitwise-equivalence policy. | FR-001: "浮点等价规则必须在看到迁移差异前由 golden tests 固定". Sprint §5.1: "固定数值精度政策与禁止字段契约". | Capture the finalized precision/tolerance policy as an explicit deliverable of the characterization work, and reference it in later sprint plans. |
| Info | Future documentation debt | FR-001 §R8; `AGENTS.md` §新设备恢复步骤 | `AGENTS.md` currently documents historical scripts and commands (e.g., `scripts.prepare_demo`, `scripts.train_full_mc`) that FR-001 mandates deleting. | `AGENTS.md` references `scripts.prepare_demo`, `scripts.train_full_mc`, etc. FR-001 §R8 says delete historical scripts and update documentation. | Track an `AGENTS.md` update task for the sprint/stage that removes historical commands, so governing docs remain consistent with the new executable surface. |

---

## 4. Positive observations

- **Scientific safety is preserved.** Both documents keep the MC-only scope, forbid real-data training, forbid held-out test leakage, and prohibit `m4l`/identifiers/weights from entering model features.
- **Feature set and protocol are correctly bounded.** FR-001 and the design spec agree on Base14 + Angular5 = 19 features, the fixed candidate parameters, the fold scheme, and the qualification thresholds.
- **Failure semantics are clear.** `no_eligible_candidate` is treated as a normal scientific outcome, runs are no-clobber, and failure receipts are separated from success manifests.
- **Sprint scope is appropriately narrow.** M1-01 avoids migrating full preprocessing/training or deleting history, which matches the design intent of first establishing boundaries.

---

## 5. Conclusion and recommended actions

The documents are ready for execution after the following actions:

1. Reconcile the `AGENTS.md` frozen-state paragraph with the approved 2026-09-01 refactor design (High).
2. Add a documented mapping between the six planned sprints and the seven design stages (High).
3. Update Sprint M1-01 verification to exercise the published console scripts (Medium).
4. Expand Sprint M1-01 scope to create the complete target directory skeleton and baseline evidence (Medium).
5. Add explicit review-confirm evidence requirements to Sprint M1-01 deliverables (Medium).
6. Close the minor completeness items (`src/config.py` in FR-001, `WORKFLOW_STATE_PATH` placeholder) (Low).

After these changes, the requirement and sprint plan will provide a consistent, safe, and actionable foundation for the refactor work.
