# 正式无质量窗协议

## 科学定义

`inclusive` 方案不在预处理、训练或主评价阶段额外施加 `m4l` 质量窗。
所有通过现有 trigger、轻子质量、SFOS、Z1/Z2 等选择的 MC 保留在预处理输出中。
全部 development 事件参与五折 OOF 和 final fit；test 仍封存，不能参与任何拟合。
全范围指绑定 MC 和这些预选下的全部事件，不意味着没有生成级或数据集预选限制。

分类器固定 15 个输入及 7,617 参数，`m4l`、身份和权重不作为输入。
对抗器仍为 11 类、1,611 参数；λ、优化器、epoch、早停和现有资格门槛保持不变。
早停 AUC、OOF 资格、候选排名和三个工作点均使用全范围。AUC 最低 0.80，
三个背景质量 KS 最大 0.10，各工作点信号效率须严格高于实际背景效率。
无合格候选不生成 final model，不允许正式 test-opening。

全范围指标不证明每个局部质量区间都无塑形，也不证明 Higgs 峰附近性能提升。
本方案只报告全范围及分箱诊断，不单设 105–160 GeV 子区域。
所有结果仍为 MC educational/technical demo，不是 ATLAS 结果或物理测量。

## 文件与接口

| 协议 | 文件 | 内部 schema |
|---|---|---|
| 有窗预处理 | `preprocess_protocol_mass_window.yaml` | 2.0 |
| 无窗预处理 | `preprocess_protocol_inclusive.yaml` | 3.0 |
| 有窗正式训练 | `adversarial_mlp_protocol_mass_window.yaml` | 2.0 |
| 无窗正式训练 | `adversarial_mlp_protocol_inclusive.yaml` | 3.0 |

有窗文件由原 `preprocess_protocol_v2.yaml` 和
`adversarial_mlp_protocol_normal_v2.yaml` 重命名，内容字节、内部 ID 和 SHA-256 不变。
旧文件名没有副本；历史文档和冻结 run 中的记录保持原样。
协议身份由 ID、schema、精确内容及哈希确认，改成其他文件名不会改变科学行为。

新预处理 ID 为 `higgsml-preprocess-inclusive`，训练 ID 为
`adversarial-mlp-protocol-inclusive`。两者必须配对使用；不接收旧有窗或 debug
预处理 run。新协议拒绝 `--debug`，不会跳过文件、canonical、数据集或协议绑定校验。

从 `neural/` 执行，每次使用新输出目录：

```powershell
conda run -n pytorch higgsml-preprocess --dataset atlas2020_4lep --protocol config/preprocess_protocol_inclusive.yaml --run-config config/preprocess_run.example.yaml --run-dir runs/atlas2020_4lep/preprocess-inclusive-001
conda run -n pytorch higgsml-train --dataset atlas2020_4lep --input-run runs/atlas2020_4lep/preprocess-inclusive-001 --protocol config/adversarial_mlp_protocol_inclusive.yaml --run-dir runs/atlas2020_4lep/development-inclusive-001
```

2025 数据集使用 `atlas2025_exactly4lep`，所有路径和数据集参数保持一致。
test 仍通过既有 `higgsml-test` 正常入口、同数据集 eligible gate 和可选一次性 claim。
示例不构成开启实际 held-out test 的授权。

## 拟合折统计

每个拟合折只用背景绝对物理权重确定 11 个质量分位数 bin。
算法以 float64 排序并合并相同质量，零权重不影响边界；内部边界取累计权重首次达到
总权重的 `j/11`（j=1…10）的质量。区间为 `(-∞,b1]`、`(b1,b2]`…`(b10,+∞)`。
离散事件及并列质量意味着各 bin 权重不保证严格相等。
相同质量不能拆分，重复边界或空有效 bin 返回 `insufficient_statistics`，不会自动调整 bin。

每折边界只拟合一次，所有 λ 候选共用；最终拟合在全部 development 上重新确定边界。
报告分箱取全部 development 背景边界，仅供汇总展示，不进入 OOF 拟合。
test 使用冻结的报告边界，即使质量超出 development 极值也进入明确无界的首尾区间。

优化器权重为 `abs(physical_weight) / 拟合折同类绝对权重均值`。
验证的归一化参数来自该拟合折；final fit 的参数仅来自 development。
类缺失或绝对权重和为零会在优化前停止。对抗损失继续按拟合折各 bin 绝对权重和归一化。
AUC、ROC、效率和 KS 使用绝对物理权重；pooled OOF 不混合各折优化器权重。
signed physical weight 仅用于物理产额。

## 新产物

- 预处理表为原 31 列移除 `train_weight` 后的 30 列，两个分区列结构相同。
- cutflow 的 `m4l_analysis_window.enabled` 为 `false`；其计数表示沿用上一阶段，不表示执行了质量筛选。
- OOF/test 预测表以 `metric_weight` 替代 `train_weight`，数值等于绝对物理权重。
- `artifacts/scientific_state.json` 记录五折拟合状态、final fit 状态、报告分箱和折内 bin 统计，绑定协议 SHA 和数据集身份。
- checkpoint 与 final model 包含 `scientific_state`。加载时验证状态及其绑定，不能单独更换模型内的分箱或权重均值。
- 分箱对象使用 `edges_gev: [null, b1, ..., b10, null]`，`null` 表示无界，不发布 JSON Infinity。
- `artifacts/mass_diagnostics.json` 保存各候选 OOF 的三个工作点分箱诊断；test 的对应诊断嵌入 `artifacts/test_metrics.json`。

诊断包括每 bin 两类事件数、负权重数、绝对权重和、平方和、有效样本量，
信号/背景效率、背景选前/选后占比及局部质量 KS。不可计算值为 `null` 并附原因，
不修改主资格判定。图表采用明确边界标签的分类轴及全范围质量 CDF，
无界区间不作为有限宽度密度柱。有效样本量是描述性统计，没有新增事后数值门槛。

统计不足时发布新目录中的配置、qualification 和独立 schema 的 manifest，
保留原因与 development 分类/折统计，不产生模型或预测，退出码为 0。

旧有窗/debug schema 和产物读取行为保持兼容。旧版本全部选后样本的权重均值
仍含 test 权重影响；只有新 inclusive 流程移除了这项依赖。
独立权威参考登记前不宣称 authority gate 通过；Windows 验证不替代锁定 ARM64 复现。
