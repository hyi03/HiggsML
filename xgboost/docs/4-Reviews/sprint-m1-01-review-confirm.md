# Sprint M1-01 Document Review Confirm

**Reviewed Inputs**

- `docs/1-Requirement/FR-001-angular19-xgboost-refactor.md`
- `docs/3-Plan/sprint-m1-01.md`
- `docs/4-Reviews/sprint-m1-01-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-01-review-by-opencode-go-glm-5.2.md`
- `AGENTS.md`
- `docs/superpowers/specs/2026-09-01-xgboost-refactor-design.md`
- `docs/roadmap/next-stage.md`

**Review Date**

- 2026-09-01

## Overall Conclusion

两份评审均确认 MC-only、Angular19、资格门槛、不可变 run 和一次性 test-opening 的科学
边界正确。文档可在应用下表的 Accept/Partial 项后进入实施。重复意见合并，但保留不同
证据来源。M1-01 不提前创建由 M1-02/M1-03 明确负责的空业务目录。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---:|---|---|---|---|---|---|---|
| 1 | High | Consistency | Kimi H1; GLM H-1 | `AGENTS.md`/roadmap 仍把去相关训练写为下一阶段，与已批准重构冲突 | Accept | 用户已批准 2026-09-01 设计并要求执行全部 Sprint；重构不授权新训练、放宽门槛或真实数据 | 在 `AGENTS.md` 与 roadmap 顶部记录重构授权及不改变冻结科学结论的边界 |
| 2 | High | Test | GLM H-2; Kimi Info | 数值等价政策缺少平台权威和各值类型规则 | Accept | 设计 §13.4 要求在看到差异前固定；当前是 Windows，历史 Angular5 权威为 ARM64 exact | 在 Sprint 中预注册同平台 exact/allclose 分类，并声明 Windows 不能替代 ARM64 权威 |
| 3 | Medium | Test | GLM M-1 | Characterization 未覆盖设计 §13.1 全部类别 | Accept | 设计要求迁移前锁定 selection、特征、权重、fold、指标、模型 round-trip | 扩大 M1-01 基线；无法在 M1-01 安全运行的类别必须在对应迁移写码前先捕获旧基线 |
| 4 | Medium | Documentation | Kimi M baseline; GLM M-2 | 缺 worktree、Git、环境、完整测试基线证据 | Accept | 设计阶段 1 明确要求；worktree 已创建 | 新增环境与基线工作包、验收项和证据记录 |
| 5 | Medium | Test | Kimi CLI; GLM M-3 | 只测 module help，没有安装和 console script | Accept | `pyproject.toml` 对外合同是两个 console scripts | 增加 editable install、两个真实入口和 module guard smoke |
| 6 | Medium | Test | GLM M-4 | 缺 protocol 与现有权威逐项对应测试 | Accept | 设计 §7.2 明确要求转录等价 | 增加 19 特征、参数、工作点和门槛逐项断言 |
| 7 | Medium | Consistency | GLM M-5 | 平铺新测试不会被后续 `tests/unit|golden|integration` 聚焦命令收集 | Accept | 批准设计固定目标测试目录 | M1-01 直接创建目标测试目录并把新测试放入对应层 |
| 8 | Medium | Process | Kimi review evidence; GLM M-6 | Sprint 交付结论未列评审确认、验证和提交证据 | Accept | Sprint workflow 要求每 Sprint 具备四类证据 | 在 §10 加入明确清单，完成后填路径、命令结果与 commit hash |
| 9 | Medium | Documentation | GLM M-7; Kimi future debt | M1-05 未包含 `AGENTS.md`/roadmap 的旧命令清理 | Accept | 两者是强制接手来源，当前包含待删除命令 | 扩大 M1-05 文档范围并保留冻结历史 |
| 10 | Medium | Maintainability | Kimi skeleton | M1-01 应预建 domain/preprocessing/training 全部空目录 | Reject | M1-02 明确拥有 domain/preprocessing，M1-03 拥有 training；空目录不提供当前验收行为，GLM 也确认实际阶段映射完整 | 保持目录按首次有实现和测试的 Sprint 创建，避免无意义骨架 |
| 11 | Low | Requirement | GLM L-1 | FR 的 OOF 条款缺“每个事件恰好一次” | Accept | 设计 §9 和 M1-03 均有该硬约束 | 补回 FR R5 精确措辞 |
| 12 | Low | Test | GLM L-2 | Protocol fail-closed 测试未枚举 duplicate key/type/non-finite/schema | Accept | FR R3 已要求全部拒绝 | 扩大 M1-01 protocol 测试清单 |
| 13 | Low | Traceability | Kimi stage mapping; GLM L-3 | 六 Sprint 与七设计阶段映射未记录 | Accept | M1-01 合并设计阶段 1/2，其余一一对应 | 在 FR 备注写出完整映射 |
| 14 | Low | Test | GLM L-4 | Windows symlink 创建权限可能导致测试不可靠 | Partial | 拒绝逻辑必须测试，但 OS 原生创建能力可能不可用 | 能创建时做真实 symlink 测试；否则跳过 OS 集成项，同时通过注入/path resolver 单测覆盖拒绝分支并记录平台限制 |
| 15 | Low | Documentation | Kimi structure; GLM L-5 | FR 影响范围遗漏 `src/config.py` | Accept | 批准设计和 M1-01 均包含该文件 | 补入 FR 影响范围 |
| 16 | Info | Maintainability | GLM I-1 | 顶层包名 `src` 需要显式 package discovery 和 `__main__` guards | Accept | 这是用户明确批准的结构 | 加入 M1-01 实现/验证任务，不改变 package 命名 |
| 17 | Info | Risk | GLM I-2 | 最终冻结路径审计不得重新字节读取历史 `data_events.csv.gz` | Accept | roadmap 已记录该程序性 Minor | 在 M1-06 明确只用 Git 状态/路径元数据并排除冻结 artifact 字节哈希 |
| 18 | Info | Documentation | GLM I-3 | `AGENTS.md` 冻结状态日期陈旧 | Partial | 当前需要修复授权冲突，但全面重写历史日期会扩大文档重构 | 添加 2026-09-01 当前重构状态，不改写旧历史段落日期 |
| 19 | Info | Process | Kimi unset; GLM I-4 | `WORKFLOW_STATE_PATH=<unset>` 看似模板占位 | Accept | 用户未要求持久状态文件，skill 明确默认不创建 | 从 FR 删除该字段 |

## Needs Immediate Action

- 应用 1-9、11-13、15-17、19 的文档修订。
- 将 14 和 18 的受限处理写入 Sprint/治理文档。

## Can Be Deferred

- ARM64 权威 bitwise 复现只能在相应平台和依赖环境中完成；Windows 本轮只提供同平台
  old/new 等价证据，并明确缺失门。

## Final Status

文档在上述修订落地后接受，可自动进入 Sprint M1-01 实施，无需人工确认。
