# Documentation

项目根目录的 [README](../README.md) 是运行入口，[AGENTS](../AGENTS.md) 是
Codex 接手入口。本页负责连接详细说明、物理标准、路线图和历史记录。

## 推荐阅读顺序

1. [项目 README](../README.md)
2. [项目总览](project/overview.md)
3. [物理原理](physics/physics-principles.md)
4. [事件选择标准](physics/selection-standard.md)
5. [下一阶段路线图](roadmap/next-stage.md)

## 当前有效文档

| 文档 | 作用 |
|---|---|
| [项目总览](project/overview.md) | 架构、数据流程、验证结果和当前限制 |
| [物理原理](physics/physics-principles.md) | 从对撞、四轻子重建到 XGBoost、质量塑形和数据封存的物理逻辑 |
| [数据说明](physics/data-description.md) | 输入数据、字段、来源、校验和使用边界 |
| [事件选择标准](physics/selection-standard.md) | 已实现的四轻子 selection 与 cutflow 契约 |
| [下一阶段路线图](roadmap/next-stage.md) | 当前优先级、后续任务和验收标准 |
| [进展简报](briefings/progress-briefing.md) | 面向导师的研究进展与讨论问题 |
| [Task 4B 设计](superpowers/specs/2026-08-10-task-4b-full-mc-training-design.md) | 冻结的 MC-only 训练、选择和审计设计 |
| [Task 4B 实施计划](superpowers/plans/2026-08-10-task-4b-full-mc-training.md) | Task 4B 分步实现、运行和收尾记录 |
| [DropTop4 + 重加权设计](superpowers/specs/2026-08-12-drop-top4-mass-bin-reweighting-design.md) | 冻结的十特征、质量分箱重加权和 test-sealing 契约 |
| [DropTop4 + 重加权计划](superpowers/plans/2026-08-12-drop-top4-mass-bin-reweighting.md) | 1.2 MC-only 方法比较、审计和交接记录 |
| [Angular5 + DropTop4 ARM64 执行报告](superpowers/plans/2026-08-26-drop-top4-angular5-r3-arm64-report.md) | 当前一次性 15 特征 MC-only 训练的 OOF 轨迹、终态和冻结比较 |

## 历史与开发记录

归档文件用于保留历史背景，不是当前状态的来源：

- [原始 Demo 设计](archive/original-demo-spec.md)
- [旧 Codex 交接与研究路线图](archive/codex-handoff-and-roadmap.md)

已完成任务的设计和实施记录继续保存在：

- [设计规格](superpowers/specs/)
- [实施计划](superpowers/plans/)
