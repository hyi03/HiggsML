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

协同说明：

- `xgboost/` 仅可用于只读 characterization/golden 比对；新运行时不得调用其 Python 代码。

## 3. 纳入范围

本 Sprint 纳入以下 FR：

- `FR-001`：MC-only 行为等价预处理与预处理审计产物

涉及包和目录：

- `neural/config/preprocess_protocol_v1.yaml`、`preprocess_run.example.yaml`
- `neural/src/domain/`、`neural/src/preprocessing/`
- `neural/src/artifacts/manifest.py`、`plots.py`
- `neural/src/cli/preprocess.py`、相关 fixtures/tests/docs

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

- [ ] 建立最小 golden fixtures 和逐字段预期值。
- [ ] 实现四动量、重建、selection、Base14、Angular5、权重、identity 和 split 模块。
- [ ] 固定角度范围、SFOS/Z1/Z2 决策、边界和退化几何规则。

测试要求：

- [ ] 覆盖单位、质量、配对、每级 selection、负权重、split 和 forbidden feature。
- [ ] 覆盖 Angular5 符号、范围和退化几何。

### 5.2 工作包：ROOT pipeline 与发布

目标：

- 通过一个命令发布最终 19 特征 MC 表与完整审计证据。

实现任务清单：

- [ ] 实现 chunked ROOT 读取、profile/schema 校验和输入 SHA-256 绑定。
- [ ] 实现预处理 pipeline、固定列顺序和确定性行顺序。
- [ ] 发布 gzip CSV、cutflow、MC summary、config snapshot 和 manifest。
- [ ] 同时记录 gzip 哈希与解压后 canonical CSV 内容哈希。

测试要求：

- [ ] 微型 ROOT 端到端生成 19 项特征及 metadata。
- [ ] 相同输入重复运行的 canonical 内容哈希一致。
- [ ] 输入哈希、schema、非有限值和输出覆盖失败路径关闭式失败。

### 5.3 工作包：权威全量 golden

目标：

- 在只读权威 ROOT 可用时验证全量计数和逐列等价性。

实现任务清单：

- [ ] 运行全量 preprocess 到新的唯一 run path。
- [ ] 比较事件数、cutflow、权重、split、19 特征、metadata、列顺序与行顺序。
- [ ] 记录命令、环境、耗时、峰值内存和证据路径。

测试要求：

- [ ] 验证 Higgs 187,128、ZZ 11,976、总计 199,104 行。
- [ ] 任何差异必须解释并重新走设计确认，不得更新 golden 掩盖差异。

## 6. 验收标准

- 普通 CLI 无法覆盖 protocol 中的科学规则。
- 输出精确包含设计规定的 19 特征和非模型字段。
- 微型 ROOT 全链与重复运行确定性测试通过。
- 权威 ROOT 可用时，全量数量和逐列 golden 通过；不可用时明确保留该验证门，不宣称全量等价已证实。
- 未读取、哈希或产生任何真实数据 artifact。

## 7. 验证要求

项目声明的验证命令：

- `conda run -n pytorch python -m pytest -q`

专项验证：

- `conda run -n pytorch python -m pytest -q tests/unit tests/integration tests/golden`
- `conda run -n pytorch higgsml-preprocess --protocol config/preprocess_protocol_v1.yaml --run-config <local-run-config> --run-dir runs/preprocess-<unique-id>`（仅在权威只读 ROOT 可用时）

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

## 10. 交付结论

待实施、评审确认和验证后填写。
