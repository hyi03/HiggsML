# Sprint M1-01

## 1. Sprint 目标

交付 [`FR-001`](FR-001-adversarial-mlp-refactor.md) 的独立工程骨架、锁定环境、两个空 CLI、日志/退出码约定和不可覆盖 run 事务基础，使后续科学实现可以在明确边界内测试驱动开发。

核心目标：

- 从零创建可安装、可测试且不依赖 `xgboost/src` 的 `neural` package。
- 使 `higgsml-preprocess --help` 与 `higgsml-train --help` 在锁定环境中可运行。

## 2. 前置依赖

- [`FR-001`](FR-001-adversarial-mlp-refactor.md)
- [`neural_adversarial_mlp_refactor_design.md`](../../neural_adversarial_mlp_refactor_design.md) 第 5、6、11、13 节

协同说明：

- 本 Sprint 只建立工程和事务边界，不实现科学预处理或模型训练。

## 3. 纳入范围

本 Sprint 纳入以下 FR：

- `FR-001` 对抗式 MLP 独立工程重构：R1；R6 中的允许根校验、不可覆盖、原子发布与失败收据

涉及包和目录：

- `neural/pyproject.toml`、`neural/environment.yml`、`neural/osx.yml`、`neural/win.yml`
- `neural/src/cli/`、`neural/src/config.py`、`neural/src/artifacts/transaction.py`
- `neural/tests/`、`neural/AGENTS.md`、`neural/README.md`

## 4. 暂不纳入范围

- ROOT 读取、四轻子重建、selection、特征和权重。
- PyTorch 网络、OOF、资格判断与 test-opening。
- 权威 ROOT 全量运行。
- Manifest schema、artifact SHA-256、gzip canonical 内容哈希与完整业务 artifact 集；这些分别在 M1-02 至 M1-05 实现。

原因：

- 这些能力分别由后续 Sprint 在已验证的工程边界上实现。

## 5. 工作范围

### 5.1 工作包：工程与环境

目标：

- 建立独立 package、固定 `pytorch` 环境和可复现的双平台依赖入口。

实现任务清单：

- [x] 创建设计第 5 节规定的完整目录骨架与必要 `.gitkeep`；后续模块只建空骨架，不提前实现。
- [x] 配置 package metadata、源码安装和仅两个 console entry point。
- [x] 从设计第 11 节基线创建 `environment.yml`，并核对现有 `osx.yml` 与 `win.yml` 的直接依赖版本、平台和来源 metadata；不得手工编辑生成 lock。
- [x] 增加静态/运行时保护，证明 `neural` 不导入 `xgboost/src`。
- [x] 创建 `neural/AGENTS.md`，规范继承根 AGENTS，并固定 MC-only、禁止字段、冻结 run、fail-closed、证据边界和教育/技术演示措辞。

测试要求：

- [x] 验证 package 可导入且 console entry point 集合精确匹配设计。
- [x] 验证依赖图或导入守卫拒绝 `xgboost/src` 运行时依赖。

### 5.2 工作包：CLI 与 run 事务基础

目标：

- 建立统一日志、异常退出码、允许根目录校验和不可覆盖事务。

实现任务清单：

- [x] 实现两个 CLI 的 parser、`--help` 和稳定退出码。
- [x] 固定退出码：`0` 成功或声明的正常科学终态、`2` CLI usage、`3` 输入/协议绑定、`4` run 事务、`5` 资格/test-opening 拒绝、`70` 未预期内部错误。
- [x] 实现新 run 目录创建、临时写入、原子发布和失败收据基础。
- [x] 拒绝既有目录、允许根外路径和不完整发布。

测试要求：

- [x] CLI help smoke 测试。
- [x] 不可覆盖、路径逃逸、成功发布与失败收据单元测试。

## 6. 验收标准

- 锁定环境可安装，`pip check` 通过。
- 两个且仅两个 CLI 的 `--help` 返回成功。
- 测试证明运行时代码不依赖 `xgboost/src`。
- run 事务不会覆盖已有目录，错误路径关闭式失败。
- 尚未声称任何科学处理或训练结果。

## 7. 验证要求

项目声明的验证命令：

- 权威平台：`conda-lock install --name pytorch osx.yml`
- Windows 开发平台：`conda-lock install --name pytorch win.yml`
- `conda run -n pytorch python -m pip check`
- `conda run -n pytorch python -m pytest -q`

专项验证：

- `conda run -n pytorch higgsml-preprocess --help`
- `conda run -n pytorch higgsml-train --help`

## 8. 实施顺序

1. 先写 package/entry point/事务失败测试。
2. 创建环境、package 与目录骨架。
3. 实现 CLI 和事务最小行为。
4. 运行专项测试、完整 pytest 和依赖检查。
5. 保持 README、FR、Sprint 与设计的 `pytorch`/双 lock 契约一致，并补充 smoke 命令与退出码。

## 9. 风险控制

- `win-64` 可执行开发验证，但不能宣称与 `osx-arm64` 权威训练精确等价。
- 事务 API 在后续 Sprint 扩展时必须保持不可覆盖和失败收据语义。
- 不为未来功能预建未被设计要求的抽象层。

## 10. 交付结论

已完成（2026-09-01，win-64 开发验证）：

- 文档评审：两份报告与 `sprint-m1-01-review-confirm.md` 已完成，接受项已应用。
- 代码评审：两份报告与 `sprint-m1-01-code-review-confirm.md` 已完成；环境 content hash、事务嵌套/异常路径、usage 测试与 artifact ignore 已修复。
- 环境：`environment.yml` 对 `win.yml` 与 `osx.yml` 的 input hash 检查均显示已锁定并跳过求解；未修改生成 lock。
- 验证：`pip check` 通过；完整测试 `15 passed`；两个已安装 CLI 的 `--help` 返回 0。
- 证据边界：只完成工程骨架和 Windows 开发验证，未执行 ARM64 权威复现、ROOT 预处理、训练或 test-opening。
