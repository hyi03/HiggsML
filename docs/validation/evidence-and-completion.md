# 论文证据与补充实验清单

本文件连接论文主张、软件产物和仍需完成的验证。它是执行清单，不是科学结果报告。

## 证据层级

| 层级 | 能证明什么 | 不能替代什么 |
|---|---|---|
| 代码审查与软件测试 | schema、绑定、拒绝路径、算法实现和确定性 | 完整 MC 的物理适用性 |
| 合成数值验证 | 已知分布下的闭合、失败语义和统计实现 | 实际 H4l 样本支持域与系统变化 |
| 受控 MC G0/G1 | 数据支持、建模、校准与模板门 | 冻结 assessment 和外部泛化 |
| 冻结 MC inference/assessment | 预注册总体上的 `mu` 精度、偏差与覆盖 | 独立 MELA、跨 release 或 authority 重放 |
| 外部参考/变化 | 矩阵元或建模稳健性的独立证据 | 软件平台复现 |
| 原生 ARM64 authority | 锁定环境中的仓库级重放 | 以上任一缺失的科学证据 |

## 论文主张与最小产物

| 主张 | 必需产物 | 完成条件 |
|---|---|---|
| H4l 角色和事件独立 | `audit`、`prepare` | 来源、过程、终态、event-group 无交叉和权重统计通过 |
| 表示提供额外判别信息 | 同总体、同 seed 的模型与 calibration | 完整 planned cells，报告 AUC 及质量切片诊断 |
| 质量雕刻受控 | physical-CDF controls、template 检查 | 独立 calibration，绑定共同网格，接受率偏差满足冻结规则 |
| `mu` 预期区间改善 | T1 model-self Asimov 主比较 | 五个预注册配对 seed 均有效，完整报告 W68 与失败 |
| 区间可靠 | Toy/assessment inference | 注入点、预算、失败率、偏差与覆盖均按协议解释 |
| compact 表示样本效率非劣 | batch、report、controls、confirmation | Q*、容量/CDF 对照与独立确认全部满足注册条件 |
| 外部物理稳健 | MELA 独立参考和有来源变化 | 输入/输出语义、参考摘要、相关性与响应模型可追溯 |

## 正式结果最小溯源字段

每个模型或推断结果至少保存 dataset、prepared population、协议摘要、代码/环境、representation、ordered inputs、网络 seed、checkpoint、model ID、mapping ID、共同 mass edges、template/workspace ID、inference layer、注入 `mu`、区间、失败状态与所有直接上游 receipt。

Toy 与 assessment 还需保存 freeze/claim、母事件或母模板、pairing ID、随机种子、预算、辅助观测生成方式、覆盖/失败/边界计数。样本效率结果另需 fraction、draw/full、实际训练事件组数、subset ID、experiment cell、multiplicity plan 和配对 bootstrap 身份。

## 建议图表

1. 五角色及 train → calibrate → templates → freeze → assessment 流程图。
2. 普通/对抗模型逐 epoch loss、AUC 和质量依赖诊断。
3. raw、physical CDF 与对照映射的背景接受率随 `m4l` 变化。
4. 共同网格下各表示的 T1 Asimov W68 配对比较。
5. `mu=0,1,2` 的偏差、覆盖、失败率与区间宽度。
6. 样本效率曲线、Q*、容量匹配和独立确认结果。

缺少相应实验时不得绘制平滑示意曲线冒充结果。方法示意图必须明确标注为 schematic。

## 完成顺序

1. 冻结协议并完成来源、重建、身份、支持域和权重审计。
2. 执行完整 MC prepare、最小模型、CDF、template 与 G0/G1。
3. 验证 MELA 和关键统计计算的独立参考。
4. 完成预注册 seed 的 Asimov、Toy 和稳健性实验。
5. 完成样本效率 batch、controls 与独立 confirmation。
6. 在原生 ARM64 锁定环境执行 authority 重放。
7. 只从验证过的 artifact 生成论文表格、图和结论。

若关键门失败，保留其终态并把结论改写为统计支持或模型适用性受限；不得为改善论文数值修改冻结产物。
