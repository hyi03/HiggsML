# Neural 软件设计文档

本目录只保存长期有效的软件架构、软件需求和方案设计。Sprint、任务清单、运行手册、一次性验证记录、机器相关证据和历史变更副本不在这里维护；精确资源摘要由 `config/` 承载，运行证据由不可覆盖的 run artifact 承载。

## 权威顺序

1. 仓库根 [`../../../AGENTS.md`](../../../AGENTS.md) 与 Neural [`../../AGENTS.md`](../../AGENTS.md) 的安全约束优先。
2. 当前行为以 `src/`、`config/`、`pyproject.toml` 和测试为准。
3. 本目录描述稳定的软件契约和设计意图。
4. 科学语义以 [`../research/`](../research/) 为准；下一阶段研究以 [`../research/H4l-Research-Project.md`](../research/H4l-Research-Project.md) 为最高层方案。

设计文档不得把计划功能写成当前能力，也不得用 Windows、synthetic 或首次运行输出代替锁定原生 ARM64 或外部权威验证。

## 状态标记

- **当前代码已实现**：仓库中已有实现、配置与相应契约；不自动表示完整 MC 或权威平台已验证。
- **最新方案规划中**：H4l 方案已提出，但生产代码、CLI 或产物尚不存在。
- **需要外部或权威验证**：设计或实现存在，结论仍依赖锁定平台、独立参考或完整科学验证。

## 文档索引

- [`architecture.md`](architecture.md)：系统边界、分层、数据流和安全架构。
- [`software-requirements.md`](software-requirements.md)：长期功能与非功能需求。
- [`dataset-and-preprocessing-design.md`](dataset-and-preprocessing-design.md)：受控数据集、下载、身份、选择、特征和分区设计。
- [`training-and-evaluation-design.md`](training-and-evaluation-design.md)：development OOF、候选资格、final fit 与 test-opening 设计。
- [`artifact-schema.md`](artifact-schema.md)：运行目录、manifest、表格及状态契约。
- [`research-software-design.md`](research-software-design.md)：从当前 legacy15 流程扩展到 H4l 研究软件的规划方案。
- [`research-performance-refactor-design.md`](research-performance-refactor-design.md)：研究模块循环热点、性能重构设计、科学一致性验收与分阶段交付方案。
- [`research-performance-refactor-implementation.md`](research-performance-refactor-implementation.md)：重构实现、资源接口、合成验证记录与尚未完成的 ROOT/权威平台验收。

本项目严格 MC-only，仅为 educational/technical demo，不构成 ATLAS 结果、Higgs discovery 或物理测量。
