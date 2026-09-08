# Development 科研协议

状态：**当前五折 OOF 流程已实现；新研究的五角色实验隔离尚未实现。**

## 当前数据边界

development 命令必须显式绑定 dataset、预处理 run、训练协议和全新输出目录。reader 在解码特征前验证数据集、协议、manifest、文件哈希和分区契约，只物化 development 行；held-out test 特征不能进入 scaler、fold、训练、指标、绘图或失败诊断。

来源行使用 `source_file_id` 和 `source_entry` 绑定，物理事件使用 `event_group_id` 分组。五折分配采用密封的 `sha256_event_group_v2` 规则，使同一物理事件的所有来源行保持在同一 fold。旧的行身份折分规则不再代表当前数据集隔离实现。

## OOF 与候选评价

每个预注册 λ 在五个 fold 上训练。每个 development 物理事件对每个候选必须恰好获得一个 validation score；缺失、重复、错误 fold、身份漂移或非有限 score 均使运行失败。

候选评价包括：

- 非负 metric weight 加权的 OOF AUC；
- loose、medium、tight 三个目标背景效率工作点；
- 各工作点的信号效率和筛选前后背景 `m4l` weighted KS；
- OOF 完整性与协议、数据集绑定。

normal/inclusive 的冻结资格条件为 AUC 不低于 0.80、三个 KS 不高于 0.10，且每个工作点的信号效率严格高于实际背景效率。先在 eligible 候选中取最高 AUC，再在冻结容差内选择较小 λ。没有 eligible 候选是可审计的正常科学终态，不产生 final model。

debug v2 只允许在运行前设置 AUC 与 KS 门槛。若没有候选满足门槛，当前实现可选择最佳 OOF AUC 候选并发布 `debug_diagnostic`，同时保留所有拒绝原因。该状态只用于诊断，不能冒充 normal/inclusive 科学资格。

## Final fit 与产物

eligible 候选的 final epoch 数取五折最佳 epoch 的中位数。模型和 scaler 随后只使用全部 development 重新拟合，不创建 test 反馈，也不改变已冻结的 OOF 评价。inclusive final fit 重新在 development 背景上拟合质量分位边界和类别归一化，并把 scientific state 绑定到模型。

运行发布 OOF、候选与 fold 指标、工作点、qualification、图表和 manifest；只有允许的终态才发布模型。具体路径和字段见 [`../sw-dev/artifact-schema.md`](../sw-dev/artifact-schema.md)。所有输出目录不可覆盖，失败证据同样保留。

## 与新 H4l 研究的关系

状态：**最新方案规划中。** 新方案将现有 development 进一步固定拆分为 train、validation、calibration、template 和 assessment 五种角色，并要求所有方法、表示、种子和系统变体共享角色身份。当前五折 OOF 不等同于这些角色，也不能冒充独立 calibration、template 或 assessment 数据。

新方案的 G0/G1 有效统计门、共同模板、条件 CDF、paired seeds、Asimov/伪实验和 μ 区间尚未实现。未来实现必须建立独立 research protocol 和产物状态，不通过当前 `eligible` 门伪装兼容。
