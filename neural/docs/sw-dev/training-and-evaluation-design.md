# 训练与评价设计

## 1. Development 输入与模型边界

**当前代码已实现。** Development reader 验证 preprocess manifest、dataset binding、协议和 development 表，只允许 train/validation 行；任何 test split、旧 mixed 表、列序漂移、身份重叠或非有限值都会失败关闭。

当前 classifier 输入固定为 15 项：`lep1_pt`、`lep2_pt`、`lep1_eta`、`lep2_eta`、`lep3_eta`、`lep4_eta`、`pt4l`、`deltaR_Z1`、`deltaR_Z2`、`deltaPhi_ZZ`、`cos_theta_star`、`cos_theta_1`、`cos_theta_2`、`phi_decay_planes`、`phi_production_plane`。`m4l` 只供 adversary 和诊断，不进入 classifier。

网络、损失、候选 λ、schedule、optimizer、早停、工作点和资格数值属于科学协议，见 [`../research/adversarial-mlp-protocol.md`](../research/adversarial-mlp-protocol.md)；软件层必须严格加载并绑定其原始字节摘要。

## 2. 五折 OOF 编排

事件组经 `sha256_event_group_v2` 确定性分为五折。对每个 λ 和 fold：

1. 只在其余拟合折拟合 scaler 与网络；scaler 使用 population variance，零方差尺度为 1。
2. Validation fold 不参与 scaler、optimizer 或权重归一化。
3. 早停 checkpoint 保存在内存，以 deep CPU copy 绑定 dataset、协议、特征、fold、seed 和 λ。
4. 每个 development 行恰有一个 OOF score；缺失、重复或事件组交叉均拒绝发布。

Inclusive 模式的背景质量分箱与优化权重归一化只从各 fitting scope 推导；退化分箱进入 `insufficient_statistics`，而不是回退到全 development 或 test 信息。

## 3. 候选资格与 final fit

候选指标只从完整 development OOF 计算。系统按协议检查加权 AUC、各工作点背景质量 KS 和信号效率，生成 `eligible`/拒绝原因并按冻结 tie rule 选择候选。

正常终态：

- `eligible`：允许按 full development 拟合最终 scaler/model，epoch 数由 fold 最佳 epoch 的冻结规则确定。
- `no_eligible_candidate`：属于正常科学终态，不发布 final model/scaler。
- `insufficient_statistics`：inclusive 统计前提不足，不训练或发布 final model。
- `debug_diagnostic`：显式 debug 诊断，可发布诊断模型，但不声称正式资格。

Final fit 不使用 test。模型、scaler、工作点、协议和 dataset binding 是不可拆分的冻结集合，不得跨 dataset 或 run 拼装。

## 4. Test-opening

Test preflight 按顺序校验：dataset 与输入路径、preprocess/development manifest、资格状态、协议快照、模型、scaler、工作点、lineage 和摘要。全部通过后才读取 test artifact；测试阶段仅做冻结变换、评分和指标计算，不训练、不重选 λ、不改阈值。

Authorization reference 可选：

- 提供 reference 时，在 development run 的 `state/test_opening.json` 建立原子 one-shot claim。已存在、partial 或不可解析 state 都拒绝；claim 后成功或 `failed_after_claim` 均不可重试。
- 不提供 reference 时，可在不同的新输出目录重复执行技术评价，但仍受相同冻结绑定和无反馈规则约束。

正常评价状态为 `test_reproduced` 或 `test_nonreproduction`。显式 `--debug` 只能产生 `debug_diagnostic`，并保留原资格失败原因；它不是正式 reproduction。

Claim 后错误只发布阶段化、清理后的收据，不得泄露 test 事件、特征、预测或冻结阈值。

## 5. 当前流程与 H4l 研究的区别

**最新方案规划中。** 当前五折 OOF 是 candidate selection/qualification 机制，不是 H4l 方案的 train、validation、calibration、template、assessment 五角色研究隔离。当前 test-opening 评价分类性能与质量雕刻，也不是二维模板和 μ inference 的最终 assessment。

新研究必须使用独立 ResearchProtocol 和 artifact namespace；不得读取当前 held-out test 来设计 CDF、分箱、模板或似然。

**需要外部或权威验证。** 完整 MC、锁定 ARM64、独立 MELA、模板闭合、Asimov/伪实验、区间覆盖和最终 μ 稳健性尚无权威结果。
