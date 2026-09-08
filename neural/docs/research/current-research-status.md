# 当前科研与软件状态

状态日期：2026-09-08。本文只描述当前工作区能够支持的能力和明确缺口，不转录旧运行数值。

## 状态矩阵

| 能力 | 状态 | 当前边界 |
|---|---|---|
| 两套受控 MC 数据集绑定 | 当前代码已实现 | `atlas2020_4lep` 与 `atlas2025_exactly4lep` 分开运行，跨 release 等价性未证明 |
| 有窗、inclusive、debug 预处理 | 当前代码已实现 | 只处理 MC；development/test 独立发布 |
| 19 项工程特征与 Angular5 | 当前代码已实现 | 未完整持久化新研究所需逐轻子四动量和终态信息 |
| 固定 legacy15 adversarial MLP | 当前代码已实现 | classifier 禁止 `m4l`；网络与候选集合密封 |
| 事件组五折 OOF 与 final fit | 当前代码已实现 | 不等同于新研究的五角色拆分 |
| normal/inclusive 资格判断 | 当前代码已实现 | AUC、KS、效率是当前流程门槛，不是 μ 推断结果 |
| debug diagnostic | 当前代码已实现 | 仅供诊断，不能升级为正式科学资格 |
| 冻结 held-out MC 评价 | 当前代码已实现 | 需要匹配 dataset 和 run 绑定；不自动授权 |
| 锁定 ARM64 权威验证 | 需要外部或权威验证 | Windows/synthetic 结果不能替代 authority gate |
| 完整 MC 新研究证据 | 需要外部或权威验证 | 当前没有可作为 H4l 论文结果的冻结运行 |
| `src.research` 与 `higgsml-research` | 最新方案规划中 | 当前代码和 CLI 均不存在 |
| ResearchProtocol 与五角色数据 | 最新方案规划中 | 需要独立契约，不能复用五折 OOF 冒充 |
| decay7/engineered19/mass-only 可变模型 | 最新方案规划中 | 当前 classifier 只支持 legacy15 |
| MELA 适配和独立参考 | 最新方案规划中 | 当前环境和仓库没有实现或验证证据 |
| 条件 CDF 与 calibration artifact | 最新方案规划中 | 尚无算法、产物或数值验证 |
| 二维模板、pyhf 与 μ inference | 最新方案规划中 | 尚无生产实现、锁定依赖或似然验证 |
| G0/G1、Asimov、伪实验和覆盖 | 最新方案规划中 | 尚未执行，不能声称精度改善或稳健性 |
| 有来源系统变化和外部 MC | 需要外部或权威验证 | 人为压力测试不能冒充实验系统误差 |

## 当前可支持的结论

仓库目前提供一个严格绑定、MC-only 的 adversarial MLP 技术流程，可研究固定 15 特征分类器在有窗或 inclusive 范围内的 AUC、工作点效率和背景质量 KS。它还提供数据集隔离、不可覆盖 run、协议/输入哈希和冻结 test 评价等软件安全机制。

这些能力只能支持 educational/technical demo。代码存在、单元测试通过、合成数据验证、真实 MC 运行、锁定 ARM64 复现、外部矩阵元验证和论文级科学结论是不同状态，不能相互替代。

## H4l 项目缺口

[`H4l-Research-Project.md`](H4l-Research-Project.md) 是下一阶段方案，目前仍是 draft。开始主实验前至少需要：

- 审计样本过程、终态、支持域、signed yield、有效统计和历史 test 反馈；
- 增加 development-only 研究导出与固定 train/validation/calibration/template/assessment 角色；
- 实现可变表示模型、MELA 导入、条件 CDF、共同模板和 μ 推断；
- 冻结 G0/G1、分箱、稀疏/抵消失败、似然、区间和重采样规则；
- 完成合成数值验证、绑定 MC 先导、独立参考和有来源稳健性验证。

上述内容在对应代码、协议、测试和产物存在前一律标记为“规划中”，不得从现有 `eligible`、`debug_diagnostic` 或 `test_reproduced` 状态推导完成。

## 继续工作的入口

- 科研总方案：[`H4l-Research-Project.md`](H4l-Research-Project.md)
- 当前预处理：[`preprocess-protocol.md`](preprocess-protocol.md)
- 当前模型：[`adversarial-mlp-protocol.md`](adversarial-mlp-protocol.md)
- 当前 development/test：[`development-protocol.md`](development-protocol.md)、[`test-opening-protocol.md`](test-opening-protocol.md)
- 工程操作与 schema：[`../sw-dev/dataset-v2-runbook.md`](../sw-dev/dataset-v2-runbook.md)、[`../sw-dev/artifact-schema.md`](../sw-dev/artifact-schema.md)
