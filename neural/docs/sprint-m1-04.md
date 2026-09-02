# Sprint M1-04

## 1. Sprint 目标

交付 [`FR-001`](FR-001-adversarial-mlp-refactor.md) 的五折 development OOF、工作点、候选比较、资格判断和 artifact 发布系统，覆盖 eligible、`no_eligible_candidate` 与异常中止三类终态。

核心目标：

- 以完整 OOF 证据严格选择或拒绝预注册 lambda 候选。
- 证明 held-out test 不参与任何 development 决策。

## 2. 前置依赖

- Sprint M1-03 已完成确定性单 fold 训练原语。
- Sprint M1-02 的预处理 manifest/schema 已冻结。
- [`Preprocess Protocol V1`](preprocess-protocol-v1.md) 的 input manifest、29 列 schema、file 与
  canonical-content SHA-256 contract。
- [`FR-001`](FR-001-adversarial-mlp-refactor.md) R4、R6、R7。
- 自包含实现规范：[`Development Protocol V1`](development-protocol-v1.md)。

协同说明：

- 本 Sprint 可封存 eligible 最终模型，但不得执行或隐式授权 test-opening。

## 3. 纳入范围

本 Sprint 纳入以下 FR：

- `FR-001`：Development 五折 OOF、资格判断、最终模型封存和完整证据

涉及包和目录：

- `neural/src/training/folds.py`、`qualification.py`、`trainer.py`
- `neural/src/training/development_reader.py`：唯一 persistent input binder、split router 与 decoder
- `neural/src/training/development.py`：五候选五折、OOF、final fit 编排与发布
- `neural/src/cli/train.py` 的 `develop` 子命令
- `neural/src/artifacts/manifest.py`、`plots.py`
- development integration/golden/CLI tests 与文档

协议内容门：

- 在 `adversarial_mlp_protocol_v1.yaml` 中新增并密封 folding、working points、qualification、
  final fit 与 development artifact blocks；同步扩展 `src/training/config.py::_EXPECTED` 与 mutation
  tests，exact 语义以 Development Protocol V1 为准。
- Development reader 只解码 split 路由和获准 development 行；held-out test feature token 不得
  数值解码、物化或进入任何训练/指标/图路径。
- 旧 `xgboost/src` 只用于文档期行为核对，不得成为 neural runtime dependency。
- `trainer.py` 新增 `train_fixed_epochs`：使用既有 optimizer/loss/schedule，但不创建 validation、
  checkpoint 或 early stopping；全 development scaler 由 dataset/development 层拟合。

## 4. 暂不纳入范围

- 读取 held-out test 特征或生成 test 指标/预测。
- test-opening claim 和 test run 发布。
- 运行时扩展 lambda、网络或质量 bins。

原因：

- Development 必须先作为不可变证据独立封存。

## 5. 工作范围

### 5.1 工作包：稳定 folds 与 OOF 完整性

目标：

- 让每个 development 身份稳定进入一个 fold，并恰好获得一次 OOF 分数。

实现任务清单：

- [x] 按 canonical identity 建立稳定五折。
- [x] 对五个 lambda 依次运行相同 fold/seed/batch 协议。
- [x] 汇总 OOF 分数并校验完整、有限、唯一、无跨 split 重复。

测试要求：

- [x] 行顺序变化不改变身份 fold。
- [x] 缺失、重复、非有限 OOF 或 test 身份混入时关闭式失败。

### 5.2 工作包：工作点与资格规则

目标：

- 只用 development OOF 背景分数确定三工作点并执行冻结资格规则。

实现任务清单：

- [x] 实现 weighted AUC、目标背景效率阈值、ZZ `m4l` KS 和信号/背景效率。
- [x] 实现 AUC/KS/效率联合资格、AUC 排序和 `1e-6` 较小 lambda tie-break。
- [x] 实现 `no_eligible_candidate`、eligible 与异常中止终态。

测试要求：

- [x] 覆盖门槛等号边界、严格效率比较和 tie-break。
- [x] 验证无合格候选时无 model/scaler 且禁止 test-opening。

### 5.3 工作包：最终模型与 development 发布

目标：

- 对 eligible 候选封存全部 development 上的 scaler/模型及完整证据。

实现任务清单：

- [x] 最终 epoch 使用五折最佳 epoch 中位数的最近整数。
- [x] 发布候选/折指标、qualification、working points、OOF 预测、图和 manifest。
- [x] 仅 eligible 时发布 `model.pt` 与 `scaler.json`，并绑定全部哈希。

测试要求：

- [x] 覆盖 eligible/no-eligible 的目录布局和 manifest 状态。
- [x] Spy/fixture 证明 development 命令从未读取 test 特征值。

## 6. 验收标准

- 五个 lambda 均产生五折完整证据或 run 明确异常失败。
- 工作点只由 development OOF 背景确定。
- 资格、排序和 tie-break 与 FR 完全一致。
- 无合格候选时不存在模型/scaler；eligible 时模型由全 development 按冻结 epoch 拟合。
- 所有 development artifact 可由 manifest/hash 追溯，test 保持未读。

## 7. 验证要求

项目声明的验证命令：

- `conda run -n pytorch python -m pytest -q`
- `conda run -n pytorch python -m pip check`

专项验证：

- `conda run -n pytorch python -m pytest -q tests/unit/test_folds.py tests/unit/test_qualification.py tests/integration/test_development_run.py`
- `conda run -n pytorch higgsml-train develop --input-run <fixture-preprocess-run> --protocol config/adversarial_mlp_protocol_v1.yaml --run-dir runs/mlp-development-<unique-id>`
- `conda run -n pytorch higgsml-preprocess --help`
- `conda run -n pytorch higgsml-train --help`
- `git diff --check`

CLI smoke 只使用新建 synthetic MC preprocess fixture/run，不得指向或探测 full-data、真实数据或
held-out test。收尾证据必须明确未运行 full-data training、未读取真实数据、未打开 held-out
test、未执行 `open-test`，且 Windows/synthetic 不替代 locked native `osx-arm64` 权威 gate。

## 8. 实施顺序

1. 实现 folds 与 OOF 完整性失败测试。
2. 实现指标、工作点与资格边界测试。
3. 编排五候选五折并发布中间证据。
4. 实现 eligible 最终模型和 no-eligible 布局。
5. 运行 CLI smoke、专项与完整测试。

路径解析：`FR_DIR=SPRINT_DIR=neural/docs/`，`REVIEW_DIR=docs/4-Reviews/`；验证命令来自
`neural/AGENTS.md`，专项与 CLI smoke 由本 Sprint 补充。工作流不创建额外 state 文件。

## 9. 风险控制

- 不因候选耗时或结果差而中途删减候选；异常必须使 run 明确失败。
- Development 数据加载层必须物理隔离 test 行读取，而不只是在指标层过滤。
- 候选比较中的浮点容差只用于 FR 指定 tie-break，不扩散到资格门槛。

## 10. 交付结论

M1-04 文档门、实现、双模型代码评审与逐条 code-review-confirm 已完成；确认文档中的
Accept/Partial 动作均已落实。最终实现补齐了 input-run resolved containment、preprocess
protocol/run-config lineage hashes、development manifest schema/epoch/OOF completeness、真实
synthetic E2E、reader/OOF/working-point/final-epoch/model artifact 证据与安全进度日志。

验证记录（Windows、synthetic-only、非权威）：

- 确认项专项：`81 passed`。
- 完整 suite：`174 passed, 1 skipped`。
- 唯一 skip：`authoritative_gate_not_run`，原因是批准的 r3-ARM64 external golden table 本机不存在。
- `conda run -n pytorch python -m pip check`：`No broken requirements found.`
- `conda run -n pytorch higgsml-preprocess --help`：通过。
- `conda run -n pytorch higgsml-train --help`：通过，含 `develop` 子命令。
- `git diff --check`：通过。
- 真实 CLI smoke 使用新建 `runs/m1-04-synthetic-cli-smoke-20260902-01/` synthetic MC fixture，
  exit 0，状态 `eligible`，5 candidates × 5 folds、1,100 OOF rows，并发布 final model/scaler。

本 Sprint 未运行 full-data training 或权威 gate，未读取、哈希、探测、预处理、评分、绘图或发布
任何真实数据；held-out test feature 未被解码或打开，且未执行 `open-test`。上述 Windows/
synthetic 结果只证明 educational/technical demo 的实现机制，不替代由 `osx.yml` 恢复的 locked
native `osx-arm64` full-data gate，也不构成 ATLAS 结果、Higgs discovery 或 physics measurement。
