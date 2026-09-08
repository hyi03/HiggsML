# Adversarial MLP 科研协议

状态：**当前代码已实现固定 legacy15 流程；新 H4l 表示研究仍在规划中。**

本文描述当前 `src/training/` 和训练协议的科学行为。配置字段与 artifact 结构见 [`../sw-dev/artifact-schema.md`](../sw-dev/artifact-schema.md)。

## 分类器输入与网络

当前 classifier 只接受固定且有序的 15 项输入：

```text
lep1_pt, lep2_pt,
lep1_eta, lep2_eta, lep3_eta, lep4_eta,
pt4l, deltaR_Z1, deltaR_Z2, deltaPhi_ZZ,
cos_theta_star, cos_theta_1, cos_theta_2,
phi_decay_planes, phi_production_plane
```

`lep3_pt`、`lep4_pt`、`mZ1`、`mZ2`、`m4l`、标签、身份、provenance、split 和权重均不得进入 classifier。网络为 `15→64→64→32→1`，使用 LayerNorm、SiLU 和前两层 dropout，共 7,617 个可训练参数。fold-local scaler 只在拟合折上估计，validation 只做 transform。

背景质量 adversary 接收 classifier logit，经 gradient reversal 后使用 `1→32→32→11` 网络预测 11 个背景质量类别，共 1,611 个参数。信号不进入 adversarial loss。

## 损失、λ 与训练日程

分类损失是非负优化权重加权的 BCE。对抗损失是背景质量类别的 bin-balanced cross entropy。GRL 前向不改变 logit，反向将传给 classifier 的对抗梯度乘以 `-lambda_effective`，因此 classifier 在保持分类能力的同时尝试移除可供 adversary 恢复的背景质量信息。

当前候选 λ 为 `0, 0.05, 0.10, 0.20, 0.50`。前 5 个 epoch 只训练分类目标，第 6–15 个 epoch 线性升高有效 λ，此后保持目标 λ。优化器、batch size、最多 epoch、early stopping 和确定性设置均由密封协议决定，不能在观察结果后修改。

## 三种协议模式

| 模式 | 质量箱 | 分类优化权重 | 用途 |
|---|---|---|---|
| mass-window normal | 固定 105–160 GeV 内 11 个 5 GeV 箱 | 预处理表中的兼容 `train_weight` | 正式有窗兼容流程 |
| debug | 固定质量箱 | 兼容 `train_weight` | 允许预先修改 AUC/KS 门槛的诊断例外 |
| inclusive | 拟合折背景绝对权重分位数形成 11 个右闭、无界尾箱 | 拟合折内类别绝对权重均值归一化 | 正式无固定质量窗流程 |

inclusive 的质量边界和类别归一化只能来自当前拟合折；validation 与 test 不得参与。重复分位边界、有效空箱、类别缺失或零绝对权重会在优化前形成 `insufficient_statistics`，不得自动换箱或回退到 debug。

## 评价边界

当前训练以 development OOF weighted AUC、三个背景效率工作点的信号效率和背景质量 KS 判断候选。AUC、效率和 KS 使用协议规定的非负 metric weight；signed `physical_weight` 只用于物理产额。`eligible` 表示通过冻结 development 条件，不代表权威验证已经完成，也不自动授权 test-opening。

所有模型、scaler、协议哈希、数据集身份和 inclusive scientific state 必须绑定发布。冻结、失败或统计不足的 run 不可覆盖。

## 与新 H4l 研究的关系

状态：**最新方案规划中。** [`H4l-Research-Project.md`](H4l-Research-Project.md) 计划比较 mass-only、decay7、engineered19、lab-extension 和其他表示，并允许新研究模型显式接收 `m4l` 条件。该许可只适用于未来的独立 research 协议，不能放宽当前 legacy15 classifier 的禁用规则。

当前代码没有可变输入网络、研究模型契约、条件 CDF、MELA 适配或 μ 推断。现有 adversarial MLP 是可复用基线，不是新研究主比较的已完成实现。
