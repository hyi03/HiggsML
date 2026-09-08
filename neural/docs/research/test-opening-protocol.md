# Held-out MC Test 科研协议

状态：**当前冻结评价入口已实现；它不是新 H4l 研究的最终推断入口。**

## 开启条件

test-opening 只接受与 development run 相同的显式 dataset，并要求输入 run、协议快照、qualification、模型、scaler、工作点、预处理 lineage 和全部哈希一致。所有 preflight 必须在 test 特征解码前完成。

正常模式只接受 `eligible` development run。显式 `--debug` 仅接受 `debug_diagnostic`，并保留其诊断属性。模式不匹配、数据集不匹配、artifact 漂移、缺失模型或统计状态无效都必须在 test 解码前拒绝。

`authorization-reference` 是可选的公开审计引用：

- 省略时不消耗一次性 claim，但每次评价仍需新的输出目录；
- 提供时创建持久、原子的 one-shot claim；claim 创建后即使运行失败也不得自动重试；
- 参数本身不能证明外部授权真实存在，操作者仍须在软件外取得明确授权。

## 冻结评价

test reader 跳过 development 行，只解码绑定的 test 分区。评分使用冻结模型和 scaler，不允许训练、重新拟合 scaler、重新选择 λ、重新选择 threshold、early stopping 或候选扩展。

正常模式复用 development 的冻结资格谓词，计算 test weighted AUC、三个工作点的效率和背景质量 KS。`test_reproduced` 与 `test_nonreproduction` 都是有效的冻结评价终态；后者不能触发调参或回写 development。

debug 模式只产生明确标记的诊断评价，不能升级为 normal/inclusive 资格。任何模型数值错误、输入绑定错误或发布失败都属于执行失败，而不是科学非复现。

test run、claim receipt 和失败证据的精确结构见 [`../sw-dev/artifact-schema.md`](../sw-dev/artifact-schema.md)。日志与收据不得泄露事件行、特征值或身份。

## 科学边界

当前 test-opening 评价的是固定 legacy15 adversarial MLP 的冻结 AUC/KS/效率条件。它不执行新方案中的 MELA、条件 CDF、二维模板、似然、μ 区间、覆盖或系统变化评估，也不为这些研究提供独立性证明。

[`H4l-Research-Project.md`](H4l-Research-Project.md) 明确规定首期新研究只使用 development 内部角色，并要求单独审计历史 test 反馈。未来 research assessment 或外部验证批次必须使用独立入口和证据，不能复用本 CLI 的“reproduced”名称代替 μ 推断结论。

所有 test 输出仍是 MC-only educational/technical demo。没有明确授权不得开启任何新的 held-out MC 评价；真实数据始终不在范围内。
