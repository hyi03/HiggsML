# Sprint M1-03

## 1. Sprint 目标

交付 [`FR-001`](FR-001-adversarial-mlp-refactor.md) 的固定规模对抗式 MLP 核心，包括严格数据契约、fold-local scaler、分类器、背景质量对抗器、GRL、权重损失和可确定复现的 CPU 训练循环。

核心目标：

- 小型合成数据训练可重复，且精确验证网络结构与梯度方向。
- 任意禁止字段或 test 行都不能进入本阶段模型输入。

## 2. 前置依赖

- Sprint M1-02 已完成并冻结预处理 schema。
- [`FR-001`](FR-001-adversarial-mlp-refactor.md) R3、R7。
- 已确认设计第 8、11、12.2 节。

协同说明：

- 本 Sprint 提供单 fold 训练原语；五折编排和资格选择由 Sprint M1-04 完成。

## 3. 纳入范围

本 Sprint 纳入以下 FR：

- `FR-001`：固定对抗式 MLP、损失、权重和 deterministic 训练核心

涉及包和目录：

- `neural/config/adversarial_mlp_protocol_v1.yaml`
- `neural/src/training/dataset.py`、`network.py`、`losses.py`、`trainer.py`
- 相关 unit/integration tests 与模型协议文档

## 4. 暂不纳入范围

- 五折 OOF 汇总、lambda 选择、工作点和资格结论。
- 最终 development 模型发布和 test-opening。
- 权威全量训练结果。

原因：

- 先独立证明训练原语正确、无泄漏且可重复，再建立选择系统。

## 5. 工作范围

### 5.1 工作包：数据契约与 scaler

目标：

- 只允许固定 15 特征进入模型，并保证 scaler 只拟合 fitting 子集。

实现任务清单：

- [ ] 实现固定列名/顺序、dtype、有限性和 forbidden feature 校验。
- [ ] 实现 fold-local scaler 拟合、应用与序列化。
- [ ] 区分分类 train weight、signed physical weight 和背景质量 bin weight。

测试要求：

- [ ] 缺列、多列、乱序、NaN/Inf、禁止字段均关闭式失败。
- [ ] 构造分布偏移数据证明 validation/test 不参与 scaler 拟合。

### 5.2 工作包：网络、GRL 与损失

目标：

- 精确实现设计规定的分类器和背景 11-bin 对抗器。

实现任务清单：

- [ ] 实现 15-64-64-32-1 分类器与 1-32-32-11 对抗器。
- [ ] 实现 Gradient Reversal Layer 和背景限定前向路径。
- [ ] 实现 weighted BCE 与 bin-balanced background CE。

测试要求：

- [ ] 验证输入/输出 shape 和精确参数量。
- [ ] 验证 GRL 前向恒等、反向梯度符号与 lambda 缩放。
- [ ] 验证信号行不贡献对抗损失，11 个质量 bin 总权重相等。

### 5.3 工作包：确定性训练循环

目标：

- 实现 protocol 固定的 AdamW、早停、warm-up、lambda ramp 和 checkpoint 语义。

实现任务清单：

- [ ] 强制 CPU、单线程数据加载、固定 seed 和 deterministic algorithms。
- [ ] checkpoint 只按 fold validation weighted AUC 选择。
- [ ] 记录 epoch 指标、吞吐、耗时和失败诊断。

测试要求：

- [ ] 相同 seed 的两次小型训练产生相同参数与分数。
- [ ] 不同 lambda 在同 fold 复用初始化与 batch 顺序。
- [ ] 验证 early stopping 和 ramp 边界 epoch。

## 6. 验收标准

- 网络结构、shape 和参数量与 protocol 精确一致，不以“约 9k”替代自动验证。
- 合成数据证明 GRL 使分类器朝增大背景质量分类损失的方向更新。
- 分类权重和背景 bin 权重符合 FR，负 physical weight 不直接进入优化器。
- 小型 CPU 训练重复运行结果一致。
- test 行未出现在 scaler、训练、早停或 checkpoint 选择路径中。

## 7. 验证要求

项目声明的验证命令：

- `conda run -n pytorch python -m pytest -q`

专项验证：

- `conda run -n pytorch python -m pytest -q tests/unit/test_dataset.py tests/unit/test_network.py tests/unit/test_losses.py tests/integration/test_deterministic_training.py`

## 8. 实施顺序

1. 先写 feature contract、scaler 泄漏和权重失败测试。
2. 实现网络与精确参数量测试。
3. 实现 GRL/损失并验证梯度。
4. 实现 deterministic trainer 与 checkpoint。
5. 运行专项和完整测试，记录平台限制。

## 9. 风险控制

- PyTorch deterministic 支持不足时明确失败，不降级后仍宣称权威复现。
- 训练器不预留运行时搜索网络结构或扩展 lambda 的入口。
- 参数量设计说明中的近似值必须在实现时转为精确可执行断言。

## 10. 交付结论

待实施、评审确认和验证后填写。
