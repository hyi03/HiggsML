# Adversarial MLP Normal Protocol

- `协议 ID`: `adversarial-mlp-protocol-normal`
- `文档状态`: 文档评审确认通过，等待实现验证
- `日期`: 2026-09-02
- `所属 Sprint`: `M1-03`
- `需求来源`: `FR-001-R3`、`FR-001-R7`
- `权威平台`: locked native `osx-arm64`；Windows/synthetic 仅为开发验证

## 1. 状态、范围与权威边界

- `schema_version`: `1.0`
- 适用 Sprint：`M1-03`
- 数据边界：严格 MC-only，仅允许 synthetic development 测试；不得读取、哈希、探测、
  预处理或发布真实数据。
- 本协议不授权 held-out test 或 `open-test`。M1-03 不读取持久 all-split artifact，只接受
  调用方已物理隔离的 29 列 development-only in-memory frame。validator 在读取 identity 或
  feature values 前拒绝任何 `split=test` 行；single-fold trainer 只接受从 validated
  development 对象构造的 validated fold，不接受绕过 validator 的任意 frame/tensor。
- Windows/synthetic 结果只证明本地训练原语，不替代锁定原生 `osx-arm64` 环境的后续
  权威 full-data gate。
- 输出只能描述为 educational/technical demo，不得描述为 ATLAS 结果、发现或物理测量。

本协议是 M1-03 的自包含实现规范。`neural/config/adversarial_mlp_protocol_normal.yaml` 必须
逐项转录全部冻结字段；loader 必须拒绝缺字段、额外字段、类型变化、顺序变化或值变化。

仓库另提供 `neural/config/adversarial_mlp_protocol_debug.yaml`。Debug 保留本协议的网络、特征、
训练日程、候选、工作点和产物契约，只允许在运行前修改 `qualification.auc_minimum` 与
`qualification.ks_maximum`。两项必须是 `[0.0, 1.0]` 内的有限浮点数；完整 Debug 文件及其
SHA-256 仍绑定到每个 run。Debug run 可以生成模型，但不具备 authority 或 held-out test-opening
资格。

## 2. Development frame 与 feature contract

### 2.1 允许的完整输入 schema

入口接收符合 M1-02 schema 的 29 列 development-only MC frame，列顺序必须 exact；
M1-03 不负责从含 test 的 M1-02 持久产物创建该 frame：

```text
lep1_pt, lep2_pt, lep3_pt, lep4_pt,
lep1_eta, lep2_eta, lep3_eta, lep4_eta,
mZ1, mZ2, pt4l, deltaR_Z1, deltaR_Z2, deltaPhi_ZZ,
cos_theta_star, cos_theta_1, cos_theta_2,
phi_decay_planes, phi_production_plane,
m4l, label, split, physical_weight, train_weight,
source_sample, source_entry, runNumber, eventNumber, channelNumber
```

不得在本层接受缺列、多列或乱序输入。入口按以下顺序验证，前一步失败时不得执行后一步：

1. exact 列名与顺序；
2. `split` 只允许 `train` 或 `validation`，出现 `test` 或其他值立即拒绝；
3. `(source_sample, source_entry)` 非空且唯一；
4. `label` 仅为整数 `0/1`，`source_entry/runNumber/eventNumber/channelNumber` 为整数；
5. 所有数值列有限，`train_weight >= 0`，`physical_weight` 可带符号；
6. 只按 2.2 的 exact 顺序提取分类器特征。

第 2 步必须在读取 identity 或 feature values、计算哈希或统计量之前执行。测试可用 poison
accessor 证明步骤顺序，但不把已经由调用方物化的 DataFrame 对象误称为“从未读取”。
所有行的 `m4l` 还必须满足 `105 <= m4l <= 160`；只有背景行进入 mass binning。inclusive
upper bound 是根设计 `[155,160]` 的 defensive superset；绑定的 M1-02 输出域为
`105 <= m4l < 160`，不会产生 exact 160。

validator 输出 validated development 对象。`build_validated_fold` 接受该对象和调用方提供的
fitting/validation row indices，验证两部分非空、canonical identity 唯一且互不相交，再输出：
fitting/validation feature、label、train weight 与 identity，fitting 背景 m4l/physical weight，
fold index、fold seed 和 fitted scaler。M1-03 的测试可提供 partition；production 五折算法与
从持久 artifact 物理隔离 test 的读取方案都由 M1-04 文档门冻结。

### 2.2 唯一分类器 feature tuple

```text
lep1_pt, lep2_pt,
lep1_eta, lep2_eta, lep3_eta, lep4_eta,
pt4l, deltaR_Z1, deltaR_Z2, deltaPhi_ZZ,
cos_theta_star, cos_theta_1, cos_theta_2,
phi_decay_planes, phi_production_plane
```

以下列虽然存在于预处理表中，但禁止进入 classifier tensor：

```text
lep3_pt, lep4_pt, mZ1, mZ2,
m4l, label, split, physical_weight, train_weight,
source_sample, source_entry, runNumber, eventNumber, channelNumber
```

API 不接受 feature override。构造出的 classifier tensor 必须恰为 shape `(N, 15)`、
dtype `torch.float32`、device `cpu`。label 与 mass-bin index 使用 `torch.int64`；优化权重使用
`torch.float32`。原始 `physical_weight` 只用于审计和构造对抗权重，不直接进入 optimizer。

## 3. Fold-local scaler

- scaler 只在当前 fold 的 fitting feature matrix 上拟合；validation 只能调用 transform。
- 拟合统计量使用 float64：`mean = sum(x)/N`，`variance = sum((x-mean)^2)/N`
  （population variance，`ddof=0`）。
- `scale = sqrt(variance)`；exact zero variance 的列使用 `scale=1.0`，非有限统计量拒绝。
- transform 先用 float64 执行 `(x-mean)/scale`，验证结果有限后转换为 `torch.float32`。
- 序列化对象必须包含 `schema_version`、15 项有序 `features`、15 个 float64 `mean`、
  15 个 float64 `scale` 和 `fitting_rows`；反序列化执行相同 exact schema 校验。
- fitting 与 validation canonical identity 必须非空、各自唯一且互不相交。

## 4. 网络

本节两张网络的所有 Linear 都使用 bias；所有 LayerNorm 都使用 affine weight/bias 和
`eps=1e-5`。

### 4.1 分类器

```text
Linear(15, 64) -> LayerNorm(64) -> SiLU -> Dropout(0.10)
Linear(64, 64) -> LayerNorm(64) -> SiLU -> Dropout(0.10)
Linear(64, 32) -> LayerNorm(32) -> SiLU
Linear(32, 1) -> logit
```

- Dropout 只在前两层，概率 exact `0.10`。
- 输出 shape 为 `(N,)` 的 raw logits，不在模型内应用 sigmoid。
- 可训练参数量 exact `7,617`。

### 4.2 背景质量对抗器

```text
scalar classifier logit
GradientReversal(lambda_effective)
Linear(1, 32) -> LayerNorm(32) -> SiLU
Linear(32, 32) -> LayerNorm(32) -> SiLU
Linear(32, 11) -> mass-bin logits
```

- 对抗器只接收 `label=0` 的 classifier logits，输入 shape `(N_background, 1)`，输出
  shape `(N_background, 11)`。
- 对抗器可训练参数量 exact `1,611`；完整模型 exact `9,228`。
- 信号行不得进入 adversary forward、mass binning 或 adversarial loss。

### 4.3 Gradient Reversal Layer

- forward 返回数值与 shape 不变的 view/identity。
- backward 对输入梯度返回 `-lambda_effective * gradient`。
- lambda 必须有限且非负；目标 lambda 只允许 `0.00, 0.05, 0.10, 0.20, 0.50`。
- GRL 只反转传向 classifier logit 的梯度；adversary 参数仍按最小化 `L_adv` 更新。

## 5. 背景质量 bins 与权重

### 5.1 固定 11 bins

edges exact：

```text
105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160
```

前十个 bin 左闭右开，最后一个为 `[155,160]`。`m4l < 105`、`m4l > 160` 或非有限值
拒绝，不 clip。

### 5.2 分类损失

对当前 batch：

```text
L_cls = sum(train_weight_i * BCEWithLogits(logit_i, label_i))
        / sum(train_weight_i)
```

`train_weight` 必须有限且非负，batch 权重和必须大于零。signed `physical_weight` 不得直接
传给 BCE 或 optimizer。

### 5.3 对抗权重与损失

只在 fitting 背景子集上，以 `abs(physical_weight)` 预计算每行对抗权重：

```text
adv_weight_i = abs(physical_weight_i)
               / sum(abs(physical_weight_j) for j in same mass bin)
```

因此 fitting 背景中每个 mass bin 的总 `adv_weight` 目标为 `1`。优化权重按已冻结的
float32 表示，逐 bin 比较谓词固定为 `rtol=0, atol=1e-7`；不得以测试局部参数继续放宽。
11 个 bin 必须全部非空且每个 bin 的 absolute-weight sum 大于零，否则 fold 关闭式失败。
validation 不参与这些权重的拟合。

对当前 batch 的背景行：

```text
L_adv = sum(adv_weight_i * CrossEntropy(adversary_i, mass_bin_i))
        / sum(adv_weight_i)
```

batch 无背景行时不运行 adversary forward，`L_adv` exact 构造为
`0.0 * classifier_logits.sum()`；因此 zero 连接到 classifier graph，但 adversary 参数保持
`grad=None` 且不得更新。
batch 有背景行但 `sum(adv_weight)==0` 时视为“无有效背景权重”，使用同一 differentiable-zero
路径，不执行除法或 adversary forward。
总训练目标为 `L_total = L_cls + L_adv`，GRL 在反向传播中使 classifier 接收
`-lambda_effective * dL_adv/dlogit`，而 adversary 继续最小化 `L_adv`。

## 6. 确定性与 optimizer

- device exact `cpu`；模型和输入 dtype exact `torch.float32`。
- `base_seed=42`，fold seed 为 `42 + fold_index`，`fold_index` 只允许 `0..4`。
- 设置 Python、NumPy 与 PyTorch RNG seed；调用
  `torch.use_deterministic_algorithms(True)`；DataLoader `num_workers=0`。
- single-fold primitive 将当前进程的 PyTorch deterministic algorithms 与 intra-op threads
  强制为上述值且不恢复；调用方必须把该全局 side effect 视为协议的一部分。
- 训练入口必须拒绝 CUDA/MPS device 请求，不得静默降级后宣称权威复现。
- optimizer exact `AdamW(lr=1e-3, weight_decay=1e-4)`；不配置 scheduler。
- 每 batch 前执行 `optimizer.zero_grad(set_to_none=True)`；这也是无背景 batch 不触发
  adversary AdamW weight decay 的必要条件。
- batch size `1024`，maximum epochs `200`。最后一个不完整 batch 保留，等价于
  `drop_last=False`。
- 不同目标 lambda 在同一 fold 开始前重置相同 fold seed，从而复用 exact 初始化和
  epoch-by-epoch shuffle 顺序。候选间不得复用已更新的模型或 optimizer state。
- 相同环境、输入 bytes、fold、lambda 和 seed 的 deterministic fields（模型 state、logits、
  epoch metric 数值与 best epoch）必须 exact；wall time 与 throughput 不属于 exact 比较字段。

## 7. Warm-up 与 lambda ramp

epoch 使用 one-based 编号：

```text
epoch 1..5:   lambda_effective = 0；只优化 L_cls，不运行 adversary forward
epoch 6..15: lambda_effective = target_lambda * (epoch - 5) / 10
epoch 16..200: lambda_effective = target_lambda
```

因此 epoch 6 为 `0.1 * target_lambda`，epoch 15 首次达到 target。`target_lambda=0` 时保持
同一完整模型结构与 seed，但所有 epoch 只优化分类损失，不运行 adversary forward。

## 8. Validation AUC、checkpoint 与 early stopping

- validation 只执行 `model.eval()` classifier forward；不得运行 adversary，不得更新 scaler、
  模型、optimizer 或 RNG-dependent augmentation。
- weighted AUC 使用 validation `train_weight` 和 sigmoid score；validation 必须同时包含
  label 0 与 1，权重有限非负且总和大于零。
- epoch 1 建立初始 best checkpoint。其后仅当
  `current_auc > best_auc + 1e-4` 时替换 checkpoint；相等或改善不超过 `1e-4` 均不替换。
- 每个未替换 checkpoint 的 epoch 将 patience counter 加一；替换时归零。counter 达到
  `20` 后结束训练。NaN/Inf AUC 或 loss 立即失败，不发布 checkpoint。
- checkpoint 是深拷贝的 CPU state，不得引用继续训练中的 tensor。最小内容：protocol
  SHA-256、feature tuple、scaler、fold index、fold seed、target lambda、best epoch、
  `best_validation_weighted_auc`、classifier/adversary state dict。M1-03 只返回内存对象；
  run artifact 发布属于后续 Sprint。
- loader 在读取 YAML bytes 时计算 SHA-256；内存 checkpoint validator 必须拒绝缺字段、
  额外字段、错误 feature tuple 或 protocol hash mismatch。持久化/反序列化属于后续 Sprint。
- test split、test feature、test label、test weight 或 test metric 不得进入 AUC、early stopping、
  checkpoint 或失败诊断。

## 9. 训练结果与诊断

M1-03 的单 fold结果至少返回：

- best checkpoint；
- 按 epoch 有序的 `epoch`、`lambda_effective`、`train_cls_loss`、`train_adv_loss`、
  `train_total_loss`、`validation_weighted_auc`、`is_best`、`duration_seconds`、
  `events_per_second`；
- `epochs_completed`、`stopped_early`、`best_epoch`、`best_validation_weighted_auc`；
- environment evidence：OS、architecture、Python、PyTorch、device、dtype、thread/data-loader
  设置与 deterministic flag。

warm-up epoch 与全部 `target_lambda=0` epoch 记录 `train_adv_loss=0.0`、
`train_total_loss=train_cls_loss`。epoch loss 不取 batch loss 的简单平均；实现必须跨整个 epoch
累计各自加权 loss numerator 与 weight denominator，再执行一次除法。`train_total_loss` 为该
epoch 聚合后的 `train_cls_loss + train_adv_loss`。

错误消息只能包含规则名称、列名和计数，不得转储 event row、feature values 或路径内容。
schema/protocol/data contract 失败使用 `InputBindingError`（CLI 映射 exit code 3）；unexpected
内部失败映射 70。M1-03 不制造不存在的 run-path 或 qualification/test-opening 错误路径。

## 10. 最小测试门

- YAML/loader mutation rejection：每个冻结 block 的缺失、额外、类型、顺序和值变化。
- exact 29 列输入契约、test-first refusal、identity overlap、NaN/Inf、dtype 与 forbidden feature。
- scaler fitting-only、population variance、zero variance、序列化 round-trip。
- 网络 shape、层序、dropout、LayerNorm 与 exact `7,617/1,611/9,228` 参数量。
- GRL forward identity、梯度符号与 lambda 缩放；信号不进入 adversary。
- 质量 bin 全部边界、11-bin total weight、空 bin、零和与负 physical weight。
- weighted BCE/CE 手算对照和 differentiable-zero batch。
- schedule epoch `1/5/6/14/15/16`，lambda=0 路径，early-stop 改善/相等/阈值边界。
- 相同 seed 两次 synthetic 训练 exact；不同 lambda exact 初始化与 batch order。
- validation/test 不参与 scaler、训练、对抗权重、early stopping 或 checkpoint。
- 完整测试、`pip check`、两个 CLI help 与 `git diff --check`；明确记录未运行 full-data
  training、未读取真实数据、未执行 `open-test`。
