# 正式无固定质量窗协议

状态：**当前代码已实现；独立权威参考和完整 MC 科学结论仍需验证。**

## 科学定义

inclusive 模式在 trigger、轻子质量、SFOS、Z1/Z2 等基础选择之后，不再施加额外 `m4l` 分析窗。全部 development 事件参与五折 OOF 和允许的 final fit；test 继续物理隔离，不能参与 scaler、质量分箱、权重归一化、候选选择或 checkpoint。

“全范围”仅指绑定 MC 在当前预选后的支持域，不表示没有生成级过滤、数据集预选或 Z 质量要求。全范围 AUC/KS 也不证明每个局部质量区域都无雕刻。

classifier 仍使用固定 legacy15 输入和 7,617 参数，`m4l`、身份与权重不作为输入。adversary 仍预测 11 个背景质量类别；候选 λ、网络、优化器、early stopping 和资格门与当前正式流程保持一致。inclusive 不接受 debug 模式。

## 拟合折质量统计

每个 fitting fold 只使用该折背景的 `abs(physical_weight)` 构造 11 个加权质量分位箱。相同质量值先合并；内部边界取累计绝对权重首次达到 `j/11` 的质量，区间采用右闭形式，首尾无界。

边界只拟合一次并由该 fold 的全部 λ 共享。validation 和 test 不参与；final fit 仅在全部 development 上重新拟合；报告分箱来自 development 背景，只用于汇总和冻结 test 诊断。

重复边界、有效空箱、缺失类别或零绝对权重和产生 `insufficient_statistics`。该状态在优化前停止，保留统计证据，但不生成预测或模型；实现不得自动减少质量箱、改变边界或回退到 debug。

## 权重与指标

优化器分类权重按 fitting fold 内各类别的平均绝对物理权重归一化。对抗权重继续在 fitting fold 内按质量箱的绝对权重和归一化。所有这些统计都不能来自 validation 或 test。

OOF AUC、ROC、工作点效率和 KS 使用 `metric_weight = abs(physical_weight)`；signed `physical_weight` 只用于物理产额。不同 fold 的优化器归一化不进入 pooled OOF 指标。

inclusive 预处理表不持久化 `train_weight`。模型和 checkpoint 绑定 fold/final scientific state，包含质量边界、类别归一化、协议哈希和数据集身份。development 与 test 的质量诊断使用同一冻结科学状态。

工程命令、产物字段和正常/统计不足布局见 [`../sw-dev/dataset-v2-runbook.md`](../sw-dev/dataset-v2-runbook.md) 与 [`../sw-dev/artifact-schema.md`](../sw-dev/artifact-schema.md)。

## 与新 H4l 研究的关系

inclusive 协议解决的是固定 legacy15 分类器在无固定质量窗条件下的去相关训练，不等同于新 H4l 方案。新方案首期使用 105–140 GeV on-shell 支持域，比较 decay7 与 engineered19，并以共同质量条件、条件 CDF、模板和 μ 推断组织主结果。

因此 inclusive 可作为现有代码基线和质量去相关经验，但其 `eligible`、AUC 或 KS 不能直接回答新研究的 μ 精度问题。新方案中的显式 `m4l` 条件许可也不能反向改变本协议的 classifier 输入。
