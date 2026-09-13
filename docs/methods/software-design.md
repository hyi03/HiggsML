# H4l 研究软件设计

本文把[研究方案](research-project.md)映射到当前 `src/higgsml/` 实现。“已实现”只表示软件能力存在，不代表完整 MC、独立 MELA、似然适用性或 ARM64 authority 已通过。

## 组件

| 组件 | 责任 | 当前边界 |
|---|---|---|
| Data preparation | 受控 ROOT、H4l 重建、选择、权重与五角色分配 | 需完整 MC 来源审计 |
| Representation registry | mass-only、decay7、engineered19、lab-extension | 输入顺序和共同条件受协议约束 |
| Model runner | 普通/对抗网络、checkpoint 与逐轮诊断 | 模型性能需实际实验确认 |
| MELA adapter | 冻结输入、后端配置、输出与参考绑定 | 外部后端需独立验证 |
| Conditional CDF | 独立 calibration、physical/absolute 权重语义 | 桥接规则受 G1 约束 |
| Template builder | 共同分箱、signed yield、sumw2 和稀疏检查 | signed-MC 适用性需证据 |
| Inference engine | pyhf T0/T1、Asimov、Toy 与压力诊断 | 覆盖检查不等于区间校准 |
| Assessment/reporting | freeze、claim、预算、配对比较与结论门 | 结果不得回流调参 |
| Sample efficiency | 冻结 compact 候选、确定性子集、学习曲线、配对聚合与确认 | 正式注册实验尚待执行 |

## 角色与反馈控制

物理事件组被确定性分配到 train、validation、calibration、template、assessment 五个互斥角色。每个 reader 验证允许角色和上游 receipt；assessment 只能在模型、CDF、分箱、模板和 likelihood 冻结后读取。

## Artifact 与失败状态

每阶段使用 immutable transaction 和 manifest-last，并记录：

- dataset、协议、上游 artifact 和代码/环境身份；
- 角色 membership 与事件组无交叉证明；
- 表示字段、单位、支持域和禁止字段；
- signed/absolute 权重统计与抵消程度；
- MELA 配置、CDF 域、共同 bin edges 和 overflow 规则；
- template 统计、workspace、optimizer、区间和 assessment claim。

统计不足、支持域越界、权重抵消、模板无效、不可识别 likelihood、拟合失败和覆盖不足必须成为显式终态，不能静默降级或利用 assessment 修补。

## 验证路径

1. 用合成数据验证 schema、身份、反馈守卫和数值边界。
2. 对受控 MC 执行 G0 数据审计和 G1 建模/模板门。
3. 使用独立参考验证矩阵元与关键数值计算。
4. 冻结协议后执行 inference、assessment 和有来源的稳健性研究。
5. 在原生 ARM64 锁定环境重放，单独登记 authority 证据。

运行方式见[复现手册](../reproducibility/runbook.md)，证据边界见[当前状态](../validation/current-status.md)。
