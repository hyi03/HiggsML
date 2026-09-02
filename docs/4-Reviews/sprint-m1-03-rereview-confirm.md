# Sprint M1-03 Focused Re-review Confirm

**Reviewed Inputs**

- `docs/4-Reviews/sprint-m1-03-rereview-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-03-rereview-by-opencode-go-glm-5.2.md`
- `docs/4-Reviews/sprint-m1-03-review-confirm.md`
- `neural/docs/sprint-m1-03.md`
- `neural/docs/adversarial-mlp-protocol-v1.md`
- M1-02 preprocess protocol、M1-04 scope、FR、设计与两级 AGENTS

**Review Date**

- 2026-09-02

## Overall Conclusion

两份复审均确认原确认表 29 项动作已应用；Kimi 无 Medium 以上发现，GLM 发现一个输入
语义矛盾。该矛盾真实：M1-02 的完整产物含 test 行，而 M1-03 又禁止打开 test，因此
M1-03 不应声明自行读取完整 all-split artifact。本确认选择更严格的 development-only
输入契约：M1-03 只验证调用方提供的 29 列 development-only in-memory frame；生产环境
如何物理隔离持久 artifact 中的 test 行必须在 M1-04 文档门另行冻结，不能由 M1-03 猜测。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---:|---|---|---|---|---|---|---|
| 1 | Low | Consistency | `Kimi L1` | validated development 与 validated fold 对象关系不一致 | Accept | validator 与 caller/fold-builder 的职责应分开 | validator 只产出 validated development；`build_validated_fold` 从其构造 fold；trainer 只收 fold。 |
| 2 | Low | Consistency | `Kimi L2` | M1-03 `<=160` 与 M1-02 `<160` 不同 | Partial | 根设计明确最后 bin `[155,160]`，M1-02 输出域是其严格子集 | 保留 inclusive defensive superset，并说明 bound M1-02 不会产生 160。 |
| 3 | Low | Requirement | `Kimi L3` | Sprint 未显式列 CUDA/MPS refusal 与环境字段 | Accept | Protocol 已要求但 execution checklist 可更直接 | 增加 checklist。 |
| 4 | Info | Consistency | `Kimi I1` | validation classifier-only 语义仅在 protocol | Accept | 是关键无泄漏执行语义 | Sprint §5.3 增加一行。 |
| 5 | Info | Clarity | `Kimi I2` | checkpoint 的 best AUC 名称缩写 | Accept | result 已使用精确名称 | 统一为 `best_validation_weighted_auc`。 |
| 6 | Info | Clarity | `Kimi I3` | Sprint 未重述 Linear/LayerNorm defaults | Accept | sealed YAML 必须显式转录 | Sprint §5.2 增加实现项。 |
| 7 | Medium | Specification | `GLM R1` | validator 对混合 all-split 表是排除 test 还是整体拒绝不清 | Accept | 完整 M1-02 表固定含 test；M1-03 又不得打开 test feature | M1-03 不读取持久 all-split artifact，只接受已隔离 development-only frame；若 frame 含 test 行，split-first 后整体拒绝且不读其 identity/features。生产隔离留给 M1-04 文档门。 |
| 8 | Low | Correctness | `GLM R2` | 有背景但 batch adversarial weight sum 为零会 0/0 | Accept | zero physical weights 合法且不应制造 NaN | 视为“无有效背景权重”并走同一 differentiable-zero/no-adversary-update 路径；增加测试。 |
| 9 | Low | Requirement | `GLM R3` | validated fold 的构造与字段未定义 | Accept | M1-03 测试需要稳定 API，但 production 5-fold 规则仍属 M1-04 | 定义 caller-supplied index partition 与最小 fold fields，不冻结 production fold algorithm。 |
| 10 | Info | Documentation | `GLM R4` | bin constraint 与 drop-last 合并、空格 typo | Accept | 纯组织问题 | 分开 checklist 并修空格。 |
| 11 | Info | Consistency | `GLM R5` | inclusive 160 是兼容 defensive superset | Accept | M1-02 域 `[105,160)` 是其子集 | 按第 2 项加说明，不改变 root design。 |

## Needs Immediate Action

- 应用全部 11 项澄清并运行 `git diff --check`。
- 用文本 spot-check 确认 M1-03 不再声称读取 M1-02 all-split table。

## Can Be Deferred

- 持久 all-split artifact 的 development-only 物理读取/隔离算法必须在 M1-04 文档门解决；
  在此之前不得运行 full-data training。

## Final Status

`Document gate passes after applying the focused amendments and local spot-check.` 不授权真实
数据、full-data training、held-out test 或 `open-test`。
