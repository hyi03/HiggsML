# Sprint M1-02

## 1. Sprint 目标

交付 [`FR-001`](FR-001-adversarial-mlp-refactor.md) 的行为等价 MC-only 预处理程序，从两个哈希绑定的 ROOT 输入生成具有固定 schema、19 项特征、稳定 split、审计产物和 canonical 内容哈希的 MC 表。

核心目标：

- 用职责分离的新模块重写最终预处理行为，不复制旧千行 run 模块。
- 通过微型 ROOT 与权威全量 golden 证明行为等价。

## 2. 前置依赖

- Sprint M1-01 已通过文档/代码评审确认并完成验证。
- [`FR-001`](FR-001-adversarial-mlp-refactor.md) R2、R6、R7。
- 已确认设计第 7、12.1、12.3 节。
- 已批准的自包含规范附录：[`Preprocess Protocol V1`](preprocess-protocol-v1.md)。

协同说明：

- `xgboost/` 仅可用于只读 characterization/golden 比对；新运行时不得调用其 Python 代码。

## 3. 纳入范围

本 Sprint 纳入以下 FR：

- `FR-001`：MC-only 行为等价预处理与预处理审计产物

涉及包和目录：

- `neural/config/preprocess_protocol_v1.yaml`、`preprocess_run.example.yaml`
- `neural/src/domain/`、`neural/src/preprocessing/`
- `neural/src/artifacts/manifest.py`
- `neural/src/cli/preprocess.py`、相关 fixtures/tests/docs

协议内容门：

- `preprocess_protocol_v1.yaml` 必须逐项实现
  [`Preprocess Protocol V1`](preprocess-protocol-v1.md)，包括两个 per-sample ROOT profile、
  完整 selection、重建/特征公式、normalization、identity、split、29 列 schema、canonical
  CSV/gzip、golden 和三份 JSON schema。
- `preprocess_run.example.yaml` 只能包含 `schema_version`、`samples.higgs.path`、
  `samples.zz.path` 和 `resources.chunk_size_events`；未知样本、额外字段、DSID 700600 和
  真实数据路径必须 fail closed。

## 4. 暂不纳入范围

- 神经网络、GRL、OOF、候选资格和 test-opening。
- 真实数据处理或任何真实数据 artifact。
- 修改旧预处理 run 或冻结产物。

原因：

- 本 Sprint 只冻结训练之前的数据契约和科学等价性。

## 5. 工作范围

### 5.1 工作包：Characterization 与 domain 行为

目标：

- 在重写前建立旧最终方案的可执行行为基线。

实现任务清单：

- [x] 建立最小 golden fixtures 和逐字段预期值。
- [x] 实现四动量、重建、selection、Base14、Angular5、权重、identity 和 split 模块。
- [x] 固定角度范围、SFOS/Z1/Z2 决策、边界和退化几何规则。

测试要求：

- [x] 覆盖单位、质量、配对、每级 selection、负权重、split 和 forbidden feature。
- [x] 覆盖 Angular5 符号、范围和退化几何。
- [x] 按协议 §9 在测试时生成 synthetic micro-ROOT；不得提交真实数据或 MC 派生 fixture。

### 5.2 工作包：ROOT pipeline 与发布

目标：

- 通过一个命令发布最终 19 特征 MC 表与完整审计证据。

实现任务清单：

- [x] 实现 chunked ROOT 读取、profile/schema 校验和输入 SHA-256 绑定。
- [x] 实现预处理 pipeline、固定列顺序和确定性行顺序。
- [x] 发布 gzip CSV、cutflow、MC summary、config snapshot 和 manifest。
- [x] 同时记录 gzip 哈希与解压后 canonical CSV 内容哈希。

测试要求：

- [x] 微型 ROOT 端到端生成 19 项特征及 metadata。
- [x] 相同输入重复运行的 canonical 内容哈希一致。
- [x] 输入哈希、schema、非有限值和输出覆盖失败路径关闭式失败。
- [x] Synthetic fixture 策略与协议 §9 一致，临时 ROOT 在测试结束后不作为项目数据发布。

### 5.3 工作包：权威全量 golden

目标：

- 在只读权威 ROOT 可用时验证全量计数和逐列等价性。

实现任务清单：

- [ ] 运行全量 preprocess 到新的唯一 run path。
- [ ] 比较事件数、cutflow、权重、split、19 特征、metadata、列顺序与行顺序。
- [ ] 记录命令、环境、耗时、峰值内存和证据路径。
- [ ] 先验证 r3-ARM64 enrichment manifest/table 与其 identity lineage 的批准 SHA-256，
  再按附录第 7 节进行比较。

测试要求：

- [ ] 验证 Higgs 187,128、ZZ 11,976、总计 199,104 行。
- [ ] Exact 验证 read、selected、split、identity、整数/枚举、列/行顺序与 legacy duplicate
  事实；浮点逐元素验证 `rtol=1e-12, atol=1e-12, equal_nan=false`。
- [ ] 任何差异必须解释并重新走设计确认，不得更新 golden 掩盖差异。

## 6. 验收标准

- 普通 CLI 无法覆盖 protocol 中的科学规则。
- 输出精确包含设计规定的 19 特征和非模型字段。
- 微型 ROOT 全链与重复运行确定性测试通过。
- 权威 ROOT 可用时，全量数量和逐列 golden 通过；不可用时明确保留该验证门，不宣称全量等价已证实。
- 权威逐列表固定为
  `xgboost/runs/angular5-mc-363490-2026-08-26-r3-arm64/processed/mc_events_angular5.csv.gz`
  （SHA-256 `bc31f4e65ccecc0a1962648cfe240b67d8ecc6df8eda2478b3f46c93d2f34f09`），
  不得以另一个旧 run 或实现输出替代。
- 未读取、哈希或产生任何真实数据 artifact。

## 7. 验证要求

项目声明的验证命令：

- `conda run -n pytorch python -m pytest -q`

专项验证：

- `conda run -n pytorch python -m pytest -q tests/unit tests/integration tests/golden`
- `conda run -n pytorch higgsml-preprocess --protocol config/preprocess_protocol_v1.yaml --run-config config/preprocess_run.local.yaml --run-dir runs/preprocess-<unique-id>`（从 example 复制后只填写路径；仅在权威只读 ROOT 可用时）

权威 gate：

- 仅在 `conda-lock install --name pytorch osx.yml` 恢复的原生 `osx-arm64` 环境执行。
- Windows 运行可覆盖除权威 full-data gate 外的测试，但不得作为其替代。

2026-09-02 最终本地验证：

- `conda run -n pytorch python -m pytest -q`：`69 passed, 1 skipped`；唯一 skip 为
  `authoritative_gate_not_run`，原因是批准的 r3-ARM64 外部 golden table 不在本机。
- `conda run -n pytorch python -m pip check`：`No broken requirements found.`
- `conda run -n pytorch higgsml-preprocess --help`：通过。
- `conda run -n pytorch higgsml-train --help`：通过。
- `git diff --check`：通过。
- 未执行 full-data preprocess；未读取、哈希、探测、预处理或发布真实数据；未打开
  held-out test，未执行 `open-test`。

## 8. 实施顺序

1. 建立 characterization/golden fixtures 与失败测试。
2. 实现纯 domain 模块。
3. 实现 ROOT reader、pipeline 与 artifact 发布。
4. 运行微型 ROOT、确定性与关闭式失败测试。
5. 在条件满足时执行权威全量 golden，并记录证据。

## 9. 风险控制

- 行为比对发现旧实现歧义时先更新设计并复审，不擅自选择新语义。
- ROOT 路径可配置但内容必须哈希绑定；大文件不进入源码仓库。
- 全量 golden 依赖外部数据，缺失时属于未完成验证门而非自动失败或自动通过。
- Synthetic micro-ROOT 由测试在临时目录确定性生成；不得提交或从真实数据/绑定 MC
  截取 fixture。

## 10. 交付结论

本地实现与验证完成（2026-09-02；权威 full-data gate 保留）：

- 所有者已批准唯一 r3-ARM64 golden table 及完整 SHA-256。
- 所有者已批准“结构字段 exact；浮点 `rtol=1e-12, atol=1e-12`；权威 gate 仅在锁定
  `osx-arm64`”的等价政策。
- ROOT profile、selection、normalization、identity、split、Base14/Angular5、row/column
  order、canonical CSV、golden lineage 与 artifact schema 已写入
  [`Preprocess Protocol V1`](preprocess-protocol-v1.md)，双模型文档复审与逐条确认已通过。
- 代码实现、双模型代码评审、逐条确认及所有 Accept/Partial 修订已完成；本地测试结果为
  `69 passed, 1 skipped`，依赖检查、两个 CLI help 和 `git diff --check` 均通过。
- 唯一 skip 精确记录为 `authoritative_gate_not_run`。批准的 r3-ARM64 外部 golden table
  不在本机，故未运行且不宣称全量等价；Windows/synthetic 结果不替代锁定原生
  `osx-arm64` 权威 gate。
- M1-03 至 M1-06 在本 Sprint 提交前保持未启动；全程未读取、哈希、探测、预处理或发布
  真实数据，未打开 held-out test，未执行 `open-test`。
