# Sprint M1-01 / FR-001 Review Confirm

**Reviewed Inputs**

- `neural/docs/FR-001-adversarial-mlp-refactor.md`
- `neural/docs/sprint-m1-01.md`
- `docs/4-Reviews/sprint-m1-01-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-01-review-by-opencode-go-glm-5.2.md`
- `AGENTS.md`
- `neural_adversarial_mlp_refactor_design.md`（当前工作区版本）
- `neural/README.md`
- `neural/osx.yml`
- `neural/win.yml`

**Review Date**

- 2026-09-01

## Overall Conclusion

两份评审对科学边界的判断一致：FR/Sprint 的 MC-only、禁止字段、development/test 隔离和一次性 test-opening 方向正确。阻塞项来自文档未同步用户当前修改后的设计：权威环境契约已经改为固定环境名 `pytorch`、跨平台直接依赖 `environment.yml`、权威 `osx.yml` 与开发验证 `win.yml`。

环境/lock 契约、R6 范围、AGENTS 追踪、lock provenance 和退出码契约均接受并在实现前修正。生成 lock 的通用 `YOURENV` 头不直接编辑；Sprint 交付结论在实际完成时填写。完成下表中的文档动作后，M1-01 可进入实现。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---|---|---|---|---|---|---|---|
| 1 | High | Consistency | Kimi H1; GLM H1 | 环境名 `higgsml-neural` 与当前设计/README 的 `pytorch` 冲突 | Accept | 当前设计 §6/§11 与 README 均固定 `pytorch` | 在 FR 和六份 Sprint 中统一改为 `pytorch`。 |
| 2 | High | Consistency | Kimi H2; GLM H2 | 文档引用不存在的 `conda-lock.yml` | Accept | 当前设计和仓库均使用 `osx.yml`、`win.yml` | 更新 FR/Sprint 的交付物和命令，分别记录权威与开发平台 lock。 |
| 3 | High | Completeness | GLM H3 | M1-01 遗漏 win-64 开发验证 lock | Accept | 当前设计 §11 明确 `win.yml` 用于 win-64 开发测试 | 将 `win.yml` 纳入 M1-01 交付和 Windows 验证命令，声明不等价于 ARM64 权威运行。 |
| 4 | Medium | Scope | Kimi M1; GLM L3 | “R6 基础部分”边界不明确 | Accept | M1-01 只具备事务基础，尚无业务 artifact | 明确本 Sprint 仅覆盖允许根、不可覆盖、原子发布和失败收据；manifest/hash/canonical CSV 延后。 |
| 5 | Medium | Completeness | Kimi M2; GLM M2 | `environment.yml` 缺失且现有 locks 的来源不可复现 | Accept | 两个 lock 的 metadata 均指向 `environment.yml`，仓库尚无该文件 | 从设计基线建立直接依赖文件，校验两平台 lock 的直接依赖与基线；不手工改 lock。 |
| 6 | Medium | Traceability | Kimi M3; GLM M4 | 文档未规范引用根 AGENTS 科学安全约束 | Accept | 根 `AGENTS.md` 适用于全仓库 | FR 添加规范引用；M1-01 要求 `neural/AGENTS.md` 固化 MC-only、禁止特征、冻结 run 和证据边界。 |
| 7 | Medium | Change control | GLM M1 | README 更新步骤可能把正确契约回退成旧契约 | Accept | README 已是 `pytorch` + 双 lock | 把任务改为保持并补充当前设计契约，关闭时核对 README/FR/Sprint/设计一致。 |
| 8 | Medium | Requirement | GLM M3 | FR R1 未承载两平台 lock 契约，是跨 Sprint 漂移根因 | Accept | FR 只写了 osx-arm64 锁定环境 | FR R1/影响范围/验证命令增加环境名、三文件职责和两平台命令。 |
| 9 | Low | Clarity | Kimi L1 | 生成 lock 头使用通用 `YOURENV` | Reject | 该头由 conda-lock 自动生成；README 和设计已固定实际环境名 | 不手工编辑生成文件；通过 README、FR 和可执行命令固定 `pytorch`。 |
| 10 | Low | Documentation | Kimi L2 | FR 缺少状态、日期、版本 | Accept | 需求为可审计主线文档 | 增加 `文档状态`、`日期`、`版本`。 |
| 11 | Low | Documentation | Kimi L3 | Sprint 交付结论尚未填写 | Reject | 计划阶段按模板必须保持待实施，提前填写会伪造证据 | 在本 Sprint 实际完成评审、实现和验证后填写。 |
| 12 | Low | Scope | GLM L1 | 是否创建完整目录骨架不清楚 | Accept | 设计 §5 给出完整树，M1-01 负责骨架 | 明确创建完整目录骨架；仅空占位，不提前实现后续模块。 |
| 13 | Low | Requirement | GLM L2 | 稳定退出码没有具体表 | Accept | 后续 CLI/CI 依赖可观察状态 | 在 `neural/AGENTS.md`/README 定义 0、2、3、4、5、70 的稳定含义并测试 usage/transaction 路径。 |
| 14 | Info | Risk | GLM I1 | 顶层 package 名 `src` 非常规且可能冲突 | Reject | 当前用户修改后的设计明确采用 `src.cli.*`，M1-01 无权静默重命名 | 按设计实现并增加精确 entry-point/import 测试；实际冲突才回到设计门。 |
| 15 | Info | Scientific safety | Kimi I1; GLM I2 | MC-only、禁止字段、test 隔离等约束正确 | Accept | 与设计 §3 和根 AGENTS 一致 | 保持这些规则，并写入 `neural/AGENTS.md`。 |
| 16 | Info | Scope | Kimi I2 | 不纳入范围清晰 | Accept | FR 和 Sprint 明确排除真实数据、历史执行器和正式统计分析 | 后续 Sprint 保持同样的边界。 |
| 17 | Info | Reproducibility | GLM I3 | 现有两份 lock 的直接依赖版本与设计基线一致 | Accept | 评审逐项核对了 osx/win lock | 视为现有基线；`environment.yml` 需描述同一直接依赖集合，不因当前 Windows 主机重新求解而宣称 ARM64 lock 已复现。 |

## Needs Immediate Action

- 同步 FR 与全部 Sprint 的 `pytorch`、`environment.yml`、`osx.yml`、`win.yml` 契约。
- 明确 M1-01 R6、目录骨架、退出码和 `neural/AGENTS.md` 约束。
- 创建可追溯的 `environment.yml`，保留现有用户生成的两平台 locks。

## Can Be Deferred

- Manifest、artifact SHA-256 和 canonical gzip 内容哈希在 M1-02 以后实现。
- Sprint 交付结论在本 Sprint 完成时填写。
- 顶层 package `src` 仅在可执行测试证明冲突时回到设计确认。

## Final Status

文档目标在应用上述 Accept 项前不可进入实现；应用后可接受并进入 Sprint M1-01 TDD 实现。
