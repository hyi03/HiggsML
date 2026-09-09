# H4l 研究软件方案

本文把[`../research/H4l-Research-Project.md`](../research/H4l-Research-Project.md)映射为长期架构。2026-09-09已核对独立研究软件实现；“已实现”不代表绑定MC、独立MELA、T1近似或ARM64验收通过。

## 1. 隔离原则

新研究在 `src.research` 与 `higgsml-research` 中实现，和现有 `preprocess/train/test` 产品入口、legacy15 协议及 artifact namespace 隔离。它只能消费经过显式导出的 development-only research dataset；不得直接打开当前 held-out test，也不得改变旧 reader、旧模型或冻结 run 的含义。

`ResearchProtocol` 是唯一研究编排契约，固定样本、表示、五角色划分、随机种子、模型、校准、分箱、模板、似然、伪实验和结论门。协议原始字节及每个上游 artifact 摘要必须进入 lineage。

## 2. 目标组件

| 组件 | 责任 | 当前状态 |
|---|---|---|
| Research export adapter | 受控ROOT先判定development身份再导出逐轻子信息 | 已实现；需来源审计 |
| Role partitioner | 事件组固定五角色与采样概率校正 | 已实现 |
| Representation registry | decay7、engineered19、mass-only、lab-extension | 已实现 |
| Model runner | 普通/对抗模型及v2逐轮诊断 | 已实现 |
| MELA adapter | 后端、配置、输入与独立参考绑定 | 已实现适配；需实际外部验证 |
| Conditional CDF calibrator | 独立calibration、物理与绝对权重目标 | 已实现；桥接受G1约束 |
| Template builder | 共同分箱、事件组统计与稀疏失败 | 已实现 |
| Inference engine | pyhf T0/T1区间、Toy覆盖检查；独立固定模板带符号μ诊断 | 已实现；T1剖面伪信号及Toy区间校准待设计 |
| Assessment reporter | freeze/claim/预算、配对Toy及完整状态报告 | 已实现；科学结论需证据 |

## 3. 角色与反馈控制

五角色必须由独立的协议和物理事件组身份产生，不能把当前 OOF fold 重新命名后复用：

- train：拟合模型参数；
- validation：选择 checkpoint/超参数；
- calibration：拟合条件 CDF 或其他校准；
- template：构造冻结模板和统计模型；
- assessment：设计冻结后的一次性最终比较。

每个组件声明可读角色和可写 artifact。编排器在运行前静态检查依赖图，运行时 reader 再做 fail-closed enforcement。Assessment 结果不得回流修改表示、模型、CDF、binning、template 或 likelihood。

## 4. Artifact 与失败状态

每阶段使用 immutable transaction 和 manifest-last。除通用输入/协议/软件绑定外，应记录：

- 角色 membership 与 event-group 无交叉证明；
- 表示字段、单位、支持域和 forbidden fields；
- signed/absolute weight sums、平方和、有效统计和 cancellation；
- MELA 实现/参考、CDF 拟合域、共同 bin edges 和 overflow 规则；
- template 稀疏/负 yield 处理、workspace 摘要、optimizer 与 interval 配置；
- assessment claim、盲态和结论门。

统计不足、支持域越界、权重抵消、空模板 bin、不可识别 likelihood、拟合失败和 coverage 不足必须成为具名终态；不得静默降级或借用 assessment 数据修补。

## 5. 与当前系统的迁移顺序

1. 先做 source/process/final-state/weight/test-feedback 审计，并定义 research export schema。
2. 实现五角色 binder 与 synthetic contract tests，证明角色隔离和可复现。
3. 分别实现表示、模型、MELA 和条件 CDF，并用独立参考验证。
4. 实现共同模板、workspace、μ fit/interval 和数值 closure。
5. 冻结 G0/G1 与失败规则后，才运行 assessment、伪实验和有来源稳健性研究。

该顺序表达依赖，不是 Sprint 或任务清单；每一步是否进入实施需由最新研究方案与单独批准决定。

## 6. 结论边界

**当前代码已实现。** 现有系统只提供受控 MC 预处理、legacy15 adversarial MLP、五折 OOF、资格、final fit 和冻结分类评价，可作为 export/transaction/binding 设计的基础。

**当前研究代码已实现。** `src.research`、新CLI、五角色、MELA适配、CDF、模板与μ inference见[运行手册](h4l-research-runbook.md)。完整R阶段实验、带nuisance的T1剖面伪信号诊断和Toy区间校准仍需独立设计及预注册。

**需要外部或权威验证。** 锁定 ARM64、独立 MELA、完整 MC、外部样本、似然 closure、伪实验覆盖和系统稳健性在获得证据前不得写成结果。最终表述仍限于 educational/technical demo。
