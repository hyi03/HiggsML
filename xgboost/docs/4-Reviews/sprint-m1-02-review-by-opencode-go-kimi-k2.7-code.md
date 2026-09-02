# Sprint M1-02 Document Review Report

- **Reviewed document:** `docs/3-Plan/sprint-m1-02.md`
- **Reviewer:** `opencode-go/kimi-k2.7-code`
- **Date:** 2026-09-02
- **References:**
  - `docs/1-Requirement/FR-001-angular19-xgboost-refactor.md`
  - `docs/3-Plan/sprint-m1-01.md`
  - `xgboost/AGENTS.md`

## Summary

The M1-02 plan correctly scopes the MC-only preprocessing migration and is consistent with FR-001 at the headline level. However, several high-severity gaps need to be closed before implementation: the manifest binding requirement from FR-001 is partially omitted, the source of golden authority for equivalence tests is not explicitly anchored, and the plan does not explicitly require verification that forbidden columns are absent from the published CSV files. Medium and low findings cover CLI real-data rejection, split responsibility, and residual historical-file import risk.

## Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| High | Requirement | Section 6 (Acceptance criteria), line 86 | Manifest binding omits code/software binding required by FR-001 R7. | FR-001 R7 states: "Manifest 绑定 protocol、配置、代码、软件、输入、输出、schema、计数和哈希." Sprint acceptance criteria state only: "Manifest 绑定输入、protocol、schema、计数与双重哈希." | Add explicit acceptance items for git HEAD / code version and software environment (dependency hashes) in the manifest. |
| High | Risk | Section 5.1 (Domain equivalence migration) | Golden outputs must satisfy a pre-registered equivalence policy, but the plan does not state which old-implementation artifacts supply the canonical values for this Sprint. | Section 5.1 test requirement: "旧/新函数 golden 输出满足预注册等价政策." | Reference the M1-01 characterization/golden fixtures (e.g., `tests/golden/test_refactor_characterization.py`) and state how canonical vectors are regenerated or locked before the new domain code is written. |
| High | Correctness | Section 5.2 (MC-only pipeline) | No explicit test or acceptance item verifies that development/test CSVs do not contain forbidden columns (`m4l`, identifiers, provenance, weights). | `AGENTS.md` and FR-001 R4/R7 forbid `m4l`, identifiers, provenance fields and weight columns in model features; Sprint acceptance only checks "输出恰好包含固定顺序的 19 项模型特征和必要 metadata." | Add a test requirement and acceptance criterion asserting that forbidden columns are absent from the published `CSV.GZ` files. |
| Medium | Requirement | Section 5.3 (CLI completion) | CLI fail-before-read is tested for occupied runs, but no test is listed for rejecting real-data input paths or configurations. | Section 5.3 test requirement: "CLI smoke 与 occupied run fail-before-read 测试." | Add CLI test cases that attempt real-data input and verify fail-closed behavior with a clear error message. |
| Medium | Consistency | Sections 5.1 and 5.2 | The responsibility for the development/test split is unclear. | Section 5.1 lists "迁移 normalization、signed/absolute 权重、identity 和 split"; Section 5.2 lists "实现 chunk pipeline、source identity、cutflow 与 summary." | Clarify whether the stable split is computed in `src/domain/` or in `src/preprocessing/`, and where the split seed/authority is recorded. |
| Medium | Maintainability | Section 1 / Section 4 (Out of scope) | Historical files are retained this Sprint while new modules are introduced, creating risk of accidental imports or calls. | Section 1: "删除主链对真实数据的依赖，但本 Sprint 暂不删除历史文件." | Add a risk-control item (e.g., namespace isolation check or import-guard test) ensuring new code does not transitively import old real-data / generic-predict modules. |
| Medium | Test | Section 5.1 (Test requirements) | Equivalence tests are listed but the tolerance policy is not restated for migrated domain functions. | Section 5.1: "旧/新函数 golden 输出满足预注册等价政策." | Restate the M1-01 exact-equality policy (integer/identity/split/fold/schema exact; domain values exact on the same platform) in this Sprint's test requirements. |
| Low | Correctness | Section 5.2 (Atomic publishing) | "原子发布两个 CSV.GZ" is vague about atomicity guarantees and failure semantics. | Section 5.2: "原子发布两个 CSV.GZ 和 canonical 内容哈希." | Define atomicity: both files are written to a staging directory and promoted only after hashes are computed and the manifest is valid; failure must write a receipt, not a partial manifest. |
| Low | Documentation | Section 10 (Delivery conclusion) | Section is intentionally left blank, but the plan lacks a checklist of evidence to collect before filling it. | Section 10: "待实施、评审和验证后填写." | Add a template checklist (environment, commit hash, test counts, CLI smoke, canonical hashes, review-confirm links) analogous to `sprint-m1-01.md` Section 10. |
| Info | Clarity | Section 2 (Prerequisites) | The plan references FR-001 and M1-01 but not the approved design specification. | Section 2: "FR-001 与批准设计." | Add a relative link to `docs/superpowers/specs/2026-09-01-xgboost-refactor-design.md` for traceability. |

## Conclusion

The M1-02 plan is directionally sound and properly limits scope to MC-only preprocessing. Address the three High findings before implementation begins: fully specify manifest code/software binding, anchor the golden authority source, and add explicit forbidden-column absence checks. The Medium findings should be clarified to avoid ambiguity around split responsibility, CLI real-data rejection, and leakage from retained historical files. Once these items are incorporated, the plan can proceed to implementation and review-confirmation.
