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
- 自包含实现规范：[`Adversarial MLP Protocol V1`](adversarial-mlp-protocol-v1.md)。

协同说明：

- 本 Sprint 提供单 fold 训练原语；五折编排和资格选择由 Sprint M1-04 完成。

## 3. 纳入范围

本 Sprint 纳入以下 FR：

- `FR-001`：固定对抗式 MLP、损失、权重和 deterministic 训练核心

涉及包和目录：

- `neural/config/adversarial_mlp_protocol_v1.yaml`
- `neural/src/training/dataset.py`、`network.py`、`losses.py`、`trainer.py`
- 相关 unit/integration tests 与模型协议文档

协议内容门：

- YAML 必须逐项转录并密封 [`Adversarial MLP Protocol V1`](adversarial-mlp-protocol-v1.md)
  的 feature contract、dtype、scaler、网络、质量 bin、权重、optimizer、determinism、
  schedule、checkpoint 和 early-stopping 规则；loader 必须拒绝缺字段、额外字段、类型变化、
  顺序变化或值变化。
- M1-03 不读取持久 all-split artifact，只接受调用方已物理隔离、符合 M1-02 schema 的 29 列
  development-only in-memory frame。validator 先验证 exact schema，再在读取 identity/feature
  values 或计算哈希/统计前拒绝任何 `split=test` 行。single-fold trainer 只接受从 validated
  development 对象构造的 fold；持久 artifact 的安全隔离读取方案由 M1-04 文档门冻结。
- “密封”包括在 load time 计算 YAML bytes SHA-256，并把它 exact 绑定到内存 checkpoint。

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

- [x] 实现固定列名/顺序、dtype、有限性和 forbidden feature 校验。
- [x] 转录 `adversarial_mlp_protocol_v1.yaml` 并实现 exact-schema loader；每个冻结 block 的
  缺失、额外、类型、顺序和值变化均关闭式失败。
- [x] 实现 fold-local scaler 拟合、应用与序列化。
- [x] 区分分类 train weight、signed physical weight 和背景质量 bin weight。
- [x] scaler 只以 float64 fitting 统计量按 population variance 拟合；模型输入和参数固定
  float32，label/bin index 固定 int64。

测试要求：

- [x] 缺列、多列、乱序、NaN/Inf、禁止字段均关闭式失败。
- [x] 构造分布偏移数据证明 validation/test 不参与 scaler 拟合。
- [x] 用 poison accessor 证明入口在读取 identity/feature values、哈希或统计前拒绝 test split。
- [x] 覆盖 identity 空/重复/跨 fitting-validation 重叠、整数/label dtype、zero variance 与
  scaler 序列化 round-trip。
- [x] 验证错误只包含规则、列名和计数，不含 row、feature value 或 filesystem path；数据/
  schema/protocol failure 使用 `InputBindingError`。

### 5.2 工作包：网络、GRL 与损失

目标：

- 精确实现设计规定的分类器和背景 11-bin 对抗器。

实现任务清单：

- [x] 实现 15-64-64-32-1 分类器与 1-32-32-11 对抗器。
- [x] 实现 Gradient Reversal Layer 和背景限定前向路径。
- [x] 实现 weighted BCE 与 bin-balanced background CE。
- [x] 所有 11 个背景 bin 必须非空且 fold-level absolute-weight sum 大于零。
- [x] 精确断言分类器 `7,617`、对抗器 `1,611`、完整模型 `9,228` 个可训练参数。
- [x] 所有 Linear 使用 bias；所有 LayerNorm 使用 affine weight/bias 与 `eps=1e-5`，并逐项
  转录至 sealed YAML。

测试要求：

- [x] 验证输入/输出 shape 和精确参数量。
- [x] 验证 GRL 前向恒等、反向梯度符号与 lambda 缩放。
- [x] 验证信号行不贡献对抗损失，11 个质量 bin 总权重相等。
- [x] 验证 `[105,110), ..., [155,160]` 的边界归属、越界/非有限质量关闭式失败。
- [x] 手算核对 weighted BCE/CE；覆盖空 bin、fold zero sum、负 physical weight、无背景或
  batch adversarial-weight sum 为零的 differentiable-zero 路径。
- [x] 无背景 batch 使用 `0.0 * classifier_logits.sum()` 且不运行 adversary forward；断言
  adversary grad 为 `None`、参数 bytes 不变。

### 5.3 工作包：确定性训练循环

目标：

- 实现 protocol 固定的 AdamW、早停、warm-up、lambda ramp 和 checkpoint 语义。

实现任务清单：

- [x] 强制 CPU、单线程数据加载、固定 seed 和 deterministic algorithms。
- [x] 明确拒绝 CUDA/MPS device 请求；记录 OS、architecture、Python、PyTorch、device、
  dtype、thread/data-loader 设置与 deterministic flag。
- [x] checkpoint 只按 fold validation weighted AUC 选择。
- [x] checkpoint 为 deep CPU copy，包含 protocol SHA-256、feature tuple、scaler、fold/seed、
  target lambda、best epoch/AUC 及两张网络 state dict；内存 validator exact 校验 schema/hash。
- [x] validation 必须同时含 label 0/1，权重有限非负且正总和，否则关闭式失败。
- [x] validation 仅以 `model.eval()` 执行 classifier forward，不运行 adversary，不更新 scaler、
  模型、optimizer 或 RNG state。
- [x] 按协议 §9 返回完整逐 epoch、汇总与 environment evidence；失败诊断不得包含 event row、
  feature value 或 filesystem path。
- [x] 按协议固定 epoch 1–5 classifier-only warm-up、epoch 6–15 线性 ramp 和其后目标
  lambda；target lambda 只允许 `0.00/0.05/0.10/0.20/0.50`，任何 schedule override 拒绝。

测试要求：

- [x] 相同 seed 的两次小型训练产生相同参数与分数。
- [x] 不同 lambda 在同 fold 复用初始化与 batch 顺序。
- [x] 验证 schedule epoch `1/5/6/14/15/16`、lambda=0、`drop_last=False` 和 epoch loss
  numerator/denominator 聚合。
- [x] 验证相等或改善不超过 `1e-4` 的 AUC 不替换 checkpoint，连续 20 个未改善 epoch
  触发停止，且 test 从未参与 metric 或 checkpoint。

完整测试绑定：

- [x] [`Adversarial MLP Protocol V1`](adversarial-mlp-protocol-v1.md) §10 的每一条最小测试门
  均必须有可执行证据；本节的摘要 checklist 不得用于跳过协议条目。

## 6. 验收标准

- 网络结构、shape 和参数量与 protocol 精确一致，不以“约 9k”替代自动验证。
- 合成数据证明 GRL 使分类器朝增大背景质量分类损失的方向更新。
- 分类权重和背景 bin 权重符合 FR，负 physical weight 不直接进入优化器。
- 小型 CPU 训练重复运行结果一致。
- test 行未出现在 scaler、训练、早停或 checkpoint 选择路径中。
- 当前 Sprint 仅在 synthetic development 数据上验证训练原语；不得运行权威全量训练，
  Windows 结果不得替代锁定原生 `osx-arm64` 的后续权威 gate。

## 7. 验证要求

项目声明的验证命令：

- `conda run -n pytorch python -m pytest -q`
- `conda run -n pytorch python -m pip check`

专项验证：

- `conda run -n pytorch python -m pytest -q tests/unit/test_training_config.py tests/unit/test_dataset.py tests/unit/test_network.py tests/unit/test_losses.py tests/integration/test_deterministic_training.py`
- `conda run -n pytorch higgsml-preprocess --help`
- `conda run -n pytorch higgsml-train --help`
- `git diff --check`

收尾证据必须明确：未运行 full-data training；未读取、哈希、探测、预处理或发布真实数据；
未打开 held-out test，未执行 `open-test`。

## 8. 实施顺序

1. 先转录密封 YAML，并写 loader mutation、feature contract、scaler 泄漏和权重失败测试。
2. 实现 protocol loader、validated development/fold 对象和 scaler。
3. 实现网络与精确参数量测试。
4. 实现 GRL/损失并验证梯度及无背景 batch 参数不变。
5. 实现 deterministic trainer、完整 result object 与内存 checkpoint validator。
6. 运行专项和完整测试，记录平台限制与安全边界。

## 9. 风险控制

- PyTorch deterministic 支持不足时明确失败，不降级后仍宣称权威复现。
- 训练器不预留运行时搜索网络结构或扩展 lambda 的入口。
- 参数量设计说明中的近似值必须在实现时转为精确可执行断言。

## 10. 交付结论

文档评审、focused re-review、代码实现、双模型代码评审及逐条 code-review-confirm 均已完成；
所有 Accept 和 Partial 后续动作已应用。评审后新增了递归 type/order-strict YAML seal、明确的
bin-balance `rtol=0, atol=1e-7`、raw loss numerator/denominator、直接构造 fold/checkpoint
invariants、early-stopping state 以及对应边界测试。

最终验证记录（Windows `pytorch` 环境，2026-09-02）：

- 专项测试：`61 passed`；
- 完整测试：`130 passed, 1 skipped`；唯一 skip 为 `authoritative_gate_not_run`，原因是批准的
  r3-ARM64 外部 golden table 不在本机；
- `python -m pip check`：`No broken requirements found.`；
- `higgsml-preprocess --help` 与 `higgsml-train --help`：exit code 0；
- `git diff --check`：通过。

本 Sprint 只在 synthetic development 数据上验证 educational/technical demo 训练原语；未运行
full-data training，未读取、哈希、探测、预处理或发布真实数据，未打开 held-out test，未执行
`open-test`。上述 Windows/synthetic 证据不替代由 `osx.yml` 恢复的 locked native
`osx-arm64` 权威 full-data gate。
