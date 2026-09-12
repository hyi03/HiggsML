# Neural 科研文档

本目录只保存当前科研定义、当前实现所支持的科学语义，以及下一阶段研究方案。命令参数、产物字段、退出码和工程验收记录统一放在 [`../sw-dev/`](../sw-dev/)；这里不复制工程协议，也不保存已经失效的历史正文。

## 权威顺序

1. [`H4l-Research-Project.md`](H4l-Research-Project.md) 是下一阶段 H→ZZ*→4ℓ 研究的最高层方案。它描述目标、实验设计、软件建设和结论门槛，但不表示相应代码或结果已经存在。
2. [`H4l-Compact-Kinematics-Sample-Efficiency.md`](H4l-Compact-Kinematics-Sample-Efficiency.md) 是从上位方案收敛出的正式课题方向，聚焦完整特征组合、紧凑表示、训练样本量学习曲线与独立非劣性确认。
3. 当前代码能够执行的 MC 预处理、固定 15 特征 adversarial MLP、development OOF 和冻结 test 评价，以代码及 `config/` 下实际协议为准；本目录的专题文档解释其科学含义。
4. 软件架构、需求与 artifact 契约以 [`../sw-dev/README.md`](../sw-dev/README.md) 和 [`../sw-dev/artifact-schema.md`](../sw-dev/artifact-schema.md) 为准；一次性操作与验证记录不作为长期文档维护。

发生冲突时，不得用下一阶段方案反向改变现有协议，也不得把现有 legacy15 流程冒充为新研究实现。

## 状态标记

本文档集使用三种状态：

- **当前代码已实现**：仓库中已有代码、配置和测试支持；是否完成权威环境或完整 MC 验证仍需单独说明。
- **最新方案规划中**：已写入 H4l 方案，但当前没有对应生产实现或科学产物。
- **需要外部或权威验证**：代码或设计存在，但缺少锁定 ARM64、外部参考、独立 MC 或完整数值验证。

## 文档索引

- [`H4l-Compact-Kinematics-Sample-Efficiency.md`](H4l-Compact-Kinematics-Sample-Efficiency.md)：有限 MC 下的紧凑运动学表示、样本效率及独立确认方案。
- [`preprocess-protocol.md`](preprocess-protocol.md)：数据集、选择、特征、权重与隔离。
- [`adversarial-mlp-protocol.md`](adversarial-mlp-protocol.md)：当前固定 15 特征 adversarial MLP。
- [`development-protocol.md`](development-protocol.md)：五折 OOF、资格判断和 final fit。
- [`test-opening-protocol.md`](test-opening-protocol.md)：冻结 held-out MC 评价边界。
- [`inclusive-protocol.md`](inclusive-protocol.md)：正式无固定质量窗流程。
- [`mass-decorrelation.md`](mass-decorrelation.md)：质量雕刻、AUC、KS、λ 和条件 CDF。
- [`mu-precision-as-primary-objective.md`](mu-precision-as-primary-objective.md)：μ 精度的定义、论文主目标理由及其与 AUC 的关系。
- [`current-research-status.md`](current-research-status.md)：当前能力与 H4l 方案缺口。

所有内容均为 MC-only educational/technical demo，不是 ATLAS 结果、Higgs discovery 或物理测量。
