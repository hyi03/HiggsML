# Sprint M1-01 / FR-001 Document Review Report

- **Reviewer:** opencode-go / kimi-k2.7-code
- **Review date:** 2026-09-01
- **Review type:** Document review
- **Target documents:**
  - `neural/docs/FR-001-adversarial-mlp-refactor.md`
  - `neural/docs/sprint-m1-01.md`
- **Sources of truth:**
  - `AGENTS.md` (repository root)
  - `neural_adversarial_mlp_refactor_design.md` (repository root)
- **Reference documents inspected:**
  - `neural/README.md`
  - `neural/osx.yml`

## Executive Summary

`FR-001` and `sprint-m1-01` accurately capture the scientific intent, scope exclusions, and fail-closed safeguards of the approved adversarial-MLP refactor design. The documents correctly prohibit real-data training, `m4l`/weight/identifier features, test-set leakage, and automatic threshold relaxation.

The review identified two high-severity consistency issues that must be resolved before implementation:

1. **Environment-name inconsistency:** the approved design and `neural/README.md` fix the Conda environment name as `pytorch`, but `FR-001` and `sprint-m1-01` consistently use `higgsml-neural`.
2. **Lock-file name inconsistency:** the approved design and the actual repository use `osx.yml` / `win.yml`, while `FR-001` and `sprint-m1-01` refer to a non-existent `conda-lock.yml`.

Several medium and low findings on scope precision, missing `environment.yml`, and traceability to `AGENTS.md` are also noted below.

## Review Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| High | Consistency / Reproducibility | `FR-001` "最小验证方式" (lines 133–135); `sprint-m1-01` §5.1, §7, §8 | Environment name conflicts with approved design and existing README. The design and README fix the Conda environment name as `pytorch`, but `FR-001` and the Sprint plan use `higgsml-neural`. | Design §11: "独立环境名称固定为 `pytorch`"; `neural/README.md` §1.1: "Conda 环境名称：`pytorch`"; `FR-001` line 133: `conda-lock install --name higgsml-neural conda-lock.yml`; `sprint-m1-01` §5.1: "固定 `higgsml-neural` 环境"; §7/§8 commands use `-n higgsml-neural`. | Align `FR-001` and `sprint-m1-01` with the design and README by changing every environment reference to `pytorch`. Update all example commands and verification steps accordingly. |
| High | Consistency / Verification | `FR-001` "最小验证方式" (line 133); `sprint-m1-01` §3, §5.1, §7 | Lock-file name conflicts with approved design and repository state. The documents reference `conda-lock.yml`, but the design specifies `osx.yml` / `win.yml` and the repository already contains `neural/osx.yml` and `neural/win.yml`. | Design §11 lists `environment.yml`, `osx.yml`, `win.yml`; repo listing shows `neural/osx.yml` and `neural/win.yml`; `FR-001` line 133: `conda-lock install --name higgsml-neural conda-lock.yml`; `sprint-m1-01` §5.1 task: "创建 `environment.yml` 与 `osx-arm64` `conda-lock.yml`"; §7: `conda-lock install --name higgsml-neural conda-lock.yml`. | Replace every `conda-lock.yml` reference with `osx.yml` (macOS authority) and `win.yml` (Windows dev/test). Update Sprint deliverables and verification commands to match the design filenames. |
| Medium | Scope / Clarity | `sprint-m1-01` §3 | Sprint claims to cover FR-001 R6 "基础部分" without enumerating which R6 sub-requirements are in scope. R6 spans manifest, SHA-256, gzip canonical hash, failure receipts, and immutability. | `sprint-m1-01` §3: "FR-001 对抗式 MLP 独立工程重构：R1、R6 的基础部分"; §5.2 only covers directory creation, atomic publish, and failure receipts; no mention of manifest schema, SHA-256, or gzip canonical hashing. | Explicitly list the R6 sub-requirements included in M1-01 (e.g., run-directory immutability, atomic transaction, and failure receipts only) and state that manifest/SHA-256/gzip canonical hashing are deferred to later sprints. |
| Medium | Completeness | `sprint-m1-01` §5.1; `neural/README.md` §1.1, §1.5 | `environment.yml` is a declared M1-01 deliverable but is missing from the repository. | `sprint-m1-01` §5.1 task: "创建 `environment.yml` 与 `osx-arm64` `conda-lock.yml`"; `neural/README.md` line 7: "阶段 1 仍需交付用于重新生成锁文件的 `environment.yml`"; repo listing under `neural/` does not contain `environment.yml`. | Create `neural/environment.yml` with the direct dependencies and pinned versions from design §11. Verify that regenerating `osx.yml` from it produces a lock consistent with the existing authority lock. |
| Medium | Scientific Safety / Traceability | `FR-001` preamble; `sprint-m1-01` §1 | Documents do not explicitly reference the root `AGENTS.md` scientific-safety constraints (feature/blinding/weight prohibitions, frozen-run immutability, no real-data training). | `FR-001` states educational use and MC-only scope but never cites `AGENTS.md`; `sprint-m1-01` does not mention scientific-safety constraints. Root `AGENTS.md` §"Scientific Safety" imposes binding constraints on the whole repository. | Add a short paragraph in `FR-001` and `sprint-m1-01` stating that all implementation must follow root `AGENTS.md` and the forthcoming `neural/AGENTS.md` scientific-safety rules. |
| Low | Clarity | `neural/osx.yml` lines 7–8 | Lock-file header uses the generic placeholder `"YOURENV"`, while the design and README fix the name as `pytorch`. | `neural/osx.yml` line 8: `conda-lock install -n YOURENV conda-lock.yml`; `neural/README.md` §1.3: `conda-lock install --name pytorch osx.yml`. | When regenerating the lock, use `--name pytorch`; or add a project-specific comment in `environment.yml` / README clarifying that the intended name is `pytorch`. |
| Low | Completeness | `FR-001` header | `FR-001` lacks document status, date, and version metadata that the design document includes. | Design header: "文档状态：已确认方案" and "日期：2026-09-01"; `FR-001` contains FR-ID, title, priority, etc., but no status/date/version fields. | Add status, date, and version fields to the `FR-001` header to support audit trail and change control. |
| Low | Completeness | `sprint-m1-01` §10 | The "交付结论" section is intentionally left blank. | `sprint-m1-01` lines 115–117: "待实施、评审确认和验证后填写。" | Keep the placeholder during planning, but require this section to be populated with acceptance evidence before the sprint completion review. |
| Info | Positive | `FR-001` throughout; design §3.3 | Scientific-safety intent is well captured: MC-only data boundary, forbidden features (`m4l`, identifiers, weights, provenance), no test-data leakage, explicit `open-test` authorization, and frozen-run immutability. | `FR-001` R2, R3, R4, R5, "不纳入范围", "失败与降级"; design §3.2, §3.3. | Maintain these constraints; strengthen traceability by linking to `AGENTS.md` (see Medium finding above). |
| Info | Positive | `FR-001` "不纳入范围"; `sprint-m1-01` §4 | Out-of-scope items are clearly enumerated (real data, OmniLearn/PET, historical executors, systematics, likelihood). | `FR-001` lines 123–129; `sprint-m1-01` §4. | Preserve clear exclusions in subsequent sprint documents to prevent scope creep. |

## Detailed Observations

### Scope and Scientific Safety

Both target documents correctly inherit the design's scope boundaries:

- Only Higgs 345060 and ZZ 363490 MC are used; real data is excluded.
- The classifier input is restricted to the fixed 15 DropTop4 + Angular5 features; `m4l`, event/run/channel identifiers, provenance fields, and weight columns are forbidden.
- `open-test` is a separate, explicitly authorized, one-time operation that cannot trigger retraining or threshold changes.
- Frozen runs and old `xgboost/` artifacts remain immutable.

These align with root `AGENTS.md` §"Scientific Safety". The only gap is the lack of an explicit normative reference to `AGENTS.md` in the target documents.

### Environment and Lock-File Naming

The most actionable defects are naming inconsistencies. The approved design is the source of truth:

- **Environment name:** `pytorch` (design §11; README §1.1).
- **Lock files:** `osx.yml` (authority) and `win.yml` (dev/test) (design §11; actual repository).

`FR-001` and `sprint-m1-01` instead use `higgsml-neural` and `conda-lock.yml`. If implemented verbatim, the team would create a redundant environment and a verification command that fails because `conda-lock.yml` does not exist. This must be reconciled before M1-01 implementation begins.

### Sprint M1-01 Scope Precision

`sprint-m1-01` correctly limits itself to the engineering skeleton and transaction foundation. However, claiming coverage of FR-001 R6 "基础部分" without a sub-requirement list risks ambiguity. R6 includes manifest content, SHA-256 coverage, gzip canonical CSV hashing, and failure receipts, most of which require the preprocessing and training pipelines to exist. M1-01 should explicitly limit R6 coverage to directory immutability, atomic publish, and failure receipts; the remaining R6 items should be assigned to later sprints.

### Missing Deliverables

The following M1-01 deliverables are currently absent from the repository (expected at this planning stage, but noted for tracking):

- `neural/environment.yml`
- `neural/pyproject.toml`
- `neural/src/` directory tree
- `neural/config/` directory tree
- `neural/tests/` directory tree
- `neural/AGENTS.md`
- `neural/data/` and `neural/runs/` directories (with `.gitkeep`)

The missing `environment.yml` is called out as a Medium finding because it is a direct M1-01 deliverable and is needed to reproduce the existing `osx.yml` lock file.

## Conclusion

`FR-001` and `sprint-m1-01` are scientifically sound and well aligned with the approved refactor design, but they **must be corrected for environment and lock-file naming** before implementation. Once `pytorch` / `osx.yml` / `win.yml` are adopted consistently, and the M1-01 R6 scope is narrowed and enumerated, the documents will provide a clear, reproducible, and auditable foundation for the engineering skeleton.

No source code or target documents were modified in the preparation of this review.
