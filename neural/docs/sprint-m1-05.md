# Sprint M1-05

## 1. Sprint 目标

交付 [`FR-001`](FR-001-adversarial-mlp-refactor.md) 的 held-out MC test-opening 机制，包括 development artifact 绑定、可选原子 claim、冻结模型评价、成功/失败收据和关闭式拒绝路径。当前接口在省略 authorization reference 时允许使用新输出目录重复评价。

核心目标：

- 只有 eligible、完整、未开启且获得另行明确授权的冻结 development run 才能开启一次 test。
- Test 结果不反馈到训练、阈值或候选决策。

## 2. 前置依赖

- Sprint M1-04 已完成并能生成冻结 eligible/no-eligible development run。
- [`FR-001`](FR-001-adversarial-mlp-refactor.md) R5、R6、R7。
- 自包含实现规范：[`Test-opening Protocol V1`](test-opening-protocol-v1.md)。
- 实际执行 `open-test` 前另有用户明确授权；本 Sprint 的实现与测试本身不构成该授权。

协同说明：

- 自动化测试必须使用合成/fixture test 数据，不得借测试名义开启权威 held-out MC。

## 3. 纳入范围

本 Sprint 纳入以下 FR：

- `FR-001`：一次性 test-opening、冻结评价和审计收据

涉及包和目录：

- `neural/src/training/test_opening.py`
- `neural/src/training/test_reader.py`
- `neural/src/cli/train.py` 的 `open-test` 子命令
- test artifact/manifest/plot 发布模块
- claim、篡改、重复调用和 CLI integration tests

协议内容门：

- `open-test` 只接受 development run、新 output run 与非空 external authorization reference；
  reference 只做审计留痕，软件不得伪称它能证明用户批准。
- 所有 development/preprocess/artifact/hash/model/scaler/threshold 校验在 claim 与 test feature decode
  前完成。
- claim 以 `O_CREAT|O_EXCL` 原子创建；任何 `claimed` 或 terminal state 均永久拒绝重试，硬崩溃
  保留 indeterminate claim。
- Test reader 只解析 test 行；评价只消费冻结 model/scaler/threshold，不得调用任何训练、拟合、
  threshold/candidate selection 路径。
- 冻结阈值选中零背景绝对权重时，不重选阈值；KS 保守记为 `1.0` 并形成正常
  `test_nonreproduction`。

## 4. 暂不纳入范围

- 权威 held-out test 的实际开启（除非用户届时单独明确授权）。
- 根据 test 结果重训、调参、改阈值或追加候选。
- 真实数据或 sideband。

原因：

- Test 是独立授权和一次性审计事件，不是实现完成后的自动步骤。

## 5. 工作范围

### 5.1 工作包：前置校验与唯一 claim

目标：

- 在读取 test 特征前验证资格、完整性、位置和唯一性。

实现任务清单：

- [x] 校验 development status、manifest、protocol、输入表、模型、scaler、工作点与 OOF 哈希。
- [x] 校验输出目录不存在且位于允许的 `runs/` 根下。
- [x] 以原子操作创建唯一 claim，并定义并发/崩溃语义。
- [x] 成功或失败均持久化不可歧义的 test-opening 收据。
- [x] Claim file/directory 完成平台等价 durable flush 后才允许 test decode；pre-claim refusal 必须
  abort staging，post-claim failure 才发布 sanitized failure run。
- [x] 正常 run 已发布但 terminal receipt 无法 durable replace 时返回 exit 4，并永久保留
  indeterminate claim 与不可覆盖 output。

测试要求：

- [x] 无资格、缺 artifact、哈希变化、已有 claim、路径逃逸和并发竞争全部拒绝。
- [x] 失败后收据能够区分“未读 test”与“claim 后评价失败”。
- [x] 覆盖 empty/partial state、missing/blank authorization、post-claim 3/4/70 exit 与 tree-only-state
  mutation。

### 5.2 工作包：冻结 test 评价与发布

目标：

- 只评价已封存模型和阈值，发布独立 test run。

实现任务清单：

- [x] 加载冻结 scaler/model/working points 并对 test 行评分。
- [x] 计算 frozen-threshold AUC、KS 与效率。
- [x] 发布 test metrics、scores、ROC、mass-sculpting 图和 manifest。
- [x] 仅产生 `test_reproduced` 或 `test_nonreproduction` 结论。

测试要求：

- [x] 验证 test 评价不调用 trainer、optimizer、scaler fit 或阈值选择。
- [x] 验证重复调用永久拒绝，test 非复现不会触发任何修正路径。

## 6. 验收标准

- Fixture 测试证明只有 eligible、完整、未开启 run 能获得 claim。
- Artifact 任一字节变化会在 test 读取前被发现并拒绝。
- 同一 development run 最多有一个 test-opening 收据，竞争调用只有一个成功占位。
- Test 使用冻结阈值且不会训练或选择任何参数。
- 没有额外用户授权时，权威 held-out test 保持未开启。

## 7. 验证要求

项目声明的验证命令：

- `conda run -n pytorch python -m pytest -q`
- `conda run -n pytorch python -m pip check`

专项验证：

- `conda run -n pytorch python -m pytest -q tests/unit/test_test_opening.py tests/integration/test_open_test_cli.py`
- 仅对 fixtures 运行 `higgsml-train open-test` smoke；不得在无单独授权时指向权威 development run。
- `conda run -n pytorch higgsml-preprocess --help`
- `conda run -n pytorch higgsml-train --help`
- `git diff --check`

路径解析：`FR_DIR=SPRINT_DIR=neural/docs/`，`REVIEW_DIR=docs/4-Reviews/`；验证命令来自
`neural/AGENTS.md`，fixture-only CLI smoke 由本 Sprint 补充。工作流不创建额外 state 文件。

## 8. 实施顺序

1. 先定义 receipt/claim schema 和失败状态机测试。
2. 实现读取 test 前的全部 artifact 校验。
3. 实现原子 claim 与并发测试。
4. 实现冻结评价和 test artifact 发布。
5. 运行 fixture CLI smoke、专项和完整测试。

## 9. 风险控制

- Claim/receipt 语义必须能承受进程崩溃，禁止通过删除状态文件重试。
- 测试 fixtures 与权威 run 路径显式隔离，避免测试误开真实 test。
- `open-test` 不提供 `--force`、`--retry` 或科学参数覆盖选项。

## 10. 交付结论

M1-05 实现、文档双模型评审、review-confirm、代码双模型评审与 code-review-confirm 已完成。
代码评审确认中的 Accept/Partial 项已应用，包括 claim ownership 竞态、pre-claim exit 4、
post-publish terminal receipt、fd ownership、exact dtype、deterministic opening、README/CLI 文案与
覆盖缺口修订。

验证证据（均在 Windows `pytorch` 环境，非权威）：

- focused opening：`50 passed`；扩大相关回归：`80 passed, 1 skipped`；
- 完整 suite：`227 passed, 2 skipped`；skip 精确为
  `authoritative_gate_not_run: external r3-ARM64 table is absent` 与
  `directory symlinks are unavailable on this platform`；
- `python -m pip check`：`No broken requirements found.`；
- `higgsml-preprocess --help` 与 `higgsml-train --help`：exit 0；
- `git diff --check`：通过；
- 新建 ignored fixture-only CLI smoke：
  `neural/runs/m1-05-synthetic-cli-smoke-20260902-02`，authorization reference 固定为
  `synthetic-fixture-only`，实际 `higgsml-train open-test` exit 0，终态
  `test_nonreproduction`，terminal receipt 完整。

本 Sprint 未读取、哈希、探测、预处理、评分、绘图或发布任何真实数据；未对任何权威 development
run 执行 `open-test`，也未打开权威 held-out test。fixture-only smoke 打开的只是 synthetic test
rows，不构成权威授权或科学结论。Windows/synthetic 结果不能替代 locked native `osx-arm64` full-data
gate；全部输出仅为 educational/technical demo。
