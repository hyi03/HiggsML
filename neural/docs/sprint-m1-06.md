# Sprint M1-06

## 1. Sprint 目标

完成 [`FR-001`](FR-001-adversarial-mlp-refactor.md) 的全链复现、验证证据与用户文档收尾：在锁定 ARM64 环境中验证从 ROOT 到 development 资格结论的完整主线，并明确记录 test-opening 的授权边界与最终技术结论。

核心目标：

- 用完整 pytest、CLI smoke、全量预处理 golden、development OOF 和 manifest 审计证明交付边界。
- 让新环境可凭 README、Conda lock、两个 MC ROOT 和配置从零恢复。

## 2. 前置依赖

- Sprint M1-01 至 M1-05 均已完成评审确认和代码验证。
- 权威 `osx-arm64` 主机、锁定 Conda 环境和两个只读 MC ROOT 可用。
- [`FR-001`](FR-001-adversarial-mlp-refactor.md) 全部需求。

协同说明：

- Development OOF 是本 Sprint 的验证范围；`open-test` 仍只在 eligible 且用户另行明确授权时执行。

## 3. 纳入范围

本 Sprint 纳入以下 FR：

- `FR-001`：全链恢复、权威 MC 验证、审计、文档与最终技术报告

涉及包和目录：

- `neural/README.md`、`neural/docs/`
- `neural/config/`、`neural/tests/`
- 新建且唯一的权威 preprocess/development run paths（保持 ignored，不提交产物）
- 全部源码与 artifact schema 的最终一致性检查

## 4. 暂不纳入范围

- 在无另行授权时执行权威 `open-test`。
- 真实数据、系统误差、控制区、sideband 或 likelihood。
- 因 development 不合格而改变模型、lambda、门槛或 protocol。
- 将 run、ROOT、模型、图、cache 或环境提交到 Git。

原因：

- 这些边界由 FR 的科学安全与仓库变更纪律明确禁止或延期。

## 5. 工作范围

### 5.1 工作包：环境与自动化回归

目标：

- 证明锁定环境可恢复、源码测试与 CLI 主线一致。

实现任务清单：

- [ ] 从权威 `osx.yml` 创建/验证 `pytorch`；Windows 开发验证使用 `win.yml`。
- [ ] 运行 `pip check`、完整 pytest 和两个 CLI smoke。
- [ ] 审计源码没有 `xgboost/src` 运行时依赖或真实数据路径。

测试要求：

- [ ] 完整测试无跳过关键科学/安全测试；任何例外逐项记录。
- [ ] 环境、平台和 deterministic 设置写入证据。

### 5.2 工作包：权威全量预处理与 development

目标：

- 在新唯一 run path 上生成可审计的全量 MC 证据和资格结论。

实现任务清单：

- [ ] 验证 ROOT SHA-256 后运行全量 preprocess。
- [ ] 核验 187,128/11,976/199,104 计数、schema、canonical hash 与 manifest。
- [ ] 运行完整五候选五折 development OOF。
- [ ] 审计 OOF 完整性、指标、资格、模型有无和 test 未读状态。

测试要求：

- [ ] Development 为 no-eligible 时验证无模型/无 test artifact。
- [ ] Development eligible 时验证模型已封存，但 test 仍未读且未自动 claim。

### 5.3 工作包：文档与最终报告

目标：

- 提供从零恢复、运行、审计和解释终态所需的自包含文档。

实现任务清单：

- [ ] 完成 README、配置说明、运行手册和 artifact schema。
- [ ] 记录验证命令、结果、环境、run 标识、哈希和未完成边界。
- [ ] 生成最终技术报告，使用教育/技术演示措辞。
- [ ] 若 development eligible，仅记录可申请 test-opening，不把资格等同于授权。

测试要求：

- [ ] 逐条执行或静态核对文档命令和路径。
- [ ] 文档数字只能引用实际 run artifact，不手工臆测更新。

## 6. 验收标准

- 锁定 ARM64 环境恢复、`pip check`、完整 pytest 与 CLI smoke 有可追踪证据。
- 全量预处理计数、19 特征、provenance、hash 和 manifest 全部通过。
- 五候选五折 OOF 完整发布，资格结论严格来自冻结规则。
- no-eligible/eligible 两种合法科学结论均不会自动访问 test。
- README 足以在具备两个 ROOT 时从零恢复主线。
- `xgboost/`、冻结 runs 和用户既有修改均未被覆盖。

## 7. 验证要求

项目声明的验证命令：

- 权威平台：`conda-lock install --name pytorch osx.yml`
- Windows 开发平台：`conda-lock install --name pytorch win.yml`
- `conda run -n pytorch python -m pip check`
- `conda run -n pytorch python -m pytest -q`

专项验证：

- `conda run -n pytorch higgsml-preprocess --protocol config/preprocess_protocol_v1.yaml --run-config config/preprocess_run.local.yaml --run-dir runs/preprocess-<unique-id>`
- `conda run -n pytorch higgsml-train develop --input-run runs/preprocess-<id> --protocol config/adversarial_mlp_protocol_v1.yaml --run-dir runs/mlp-development-<unique-id>`
- `open-test` 命令只有在 eligible 且用户另行明确授权后才加入本 Sprint 的实际验证记录。

## 8. 实施顺序

1. 在权威平台重建环境并完成自动化回归。
2. 验证输入哈希并运行全量预处理。
3. 审计 preprocess artifact 后运行 development OOF。
4. 审计资格、模型有无和 test 未读状态。
5. 更新 README、schema、运行手册与最终报告。
6. 仅在另行授权时执行一次 `open-test`；否则以未开启边界收尾。

## 9. 风险控制

- 全量运行耗时或资源不足时保留失败收据和已完成证据，不以小样本结果替代权威结论。
- 任何 golden 差异、OOF 不完整或 deterministic 偏差都先诊断，禁止改门槛或重写历史 artifact。
- 文档必须区分源码/静态验证、自动化测试、全量预处理、development 训练和 test-opening 五类证据门。

## 10. 交付结论

待实施、评审确认、全链验证和最终验收后填写。
