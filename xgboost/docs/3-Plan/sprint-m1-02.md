# Sprint M1-02

## 1. Sprint 目标

覆盖 [FR-001](../1-Requirement/FR-001-angular19-xgboost-refactor.md)，迁移纯 domain 与
MC-only ROOT 预处理，使一个 `higgsml-preprocess` run 直接发布 development/test 分离的
Angular19 数据集。

核心目标：

- 等价迁移重建、selection、Base14、Angular5、权重、identity 和 split。
- 删除主链对真实数据的依赖，但本 Sprint 暂不删除历史文件。
- 发布完整 preprocess manifest、cutflow 与 summary。

## 2. 前置依赖

- `sprint-m1-01` 已完成并提交。
- [FR-001](../1-Requirement/FR-001-angular19-xgboost-refactor.md) 与
  [批准设计](../superpowers/specs/2026-09-01-xgboost-refactor-design.md)。

协同说明：复用 M1-01 的 protocol 和 artifact 基础设施。

## 3. 纳入范围

- `src/domain/`
- `src/preprocessing/`
- `src/cli/preprocess.py`
- M1-01 已冻结的 preprocessing protocol v1（本 Sprint byte-for-byte 消费，不修改）
- preprocessing run config
- unit、golden、微型 ROOT 集成测试

## 4. 暂不纳入范围

- XGBoost develop、qualification、open-test 和历史代码删除。

原因：先完成可审计的数据边界。

## 5. 工作范围

### 5.1 Domain 等价迁移

目标：纯函数形式迁移科学计算。

实现任务清单：

- [x] 迁移四动量、SFOS 配对、Z1/Z2、selection 和 cutflow。
- [x] 迁移 Base14 与 Angular5 数学、范围和符号约定。
- [x] 迁移 normalization、signed/absolute 权重和 identity。
- [x] `src/domain/` 提供 protocol 固定算法的纯 deterministic split；
      `src/preprocessing/` 负责逐行调用、分区发布及在 manifest 记录 split authority。

测试要求：

- [x] 旧/新函数 golden 输出满足 `sprint-m1-01.md` §5.1 与
      `tests/golden/test_refactor_characterization.py` 中 `RTOL=ATOL=1e-12` 所固定的
      等价政策；整数、identity、split、schema、列序和同平台直接迁移 domain 值 exact，
      不在本 Sprint 重定义容差。
- [x] 19 项特征顺序和 forbidden features 精确验证。

### 5.2 MC-only pipeline

目标：只读取 345060/363490，并物理分离 development/test。

实现任务清单：

- [x] 迁移 release22/open-data input profile 与 ROOT reader。
- [x] 实现 chunk pipeline、source identity、cutflow 与 summary。
- [x] 构造仅供测试的微型 ROOT fixture builder，覆盖 release22 `analysis`/GeV、
      open-data `mini`/MeV、345060/363490、lepton-quality、单位换算、train/validation/test
      bucket 以及重复 canonical identity 拒绝。
- [x] 在读取每个 ROOT 前记录 regular-file stat signature 与 SHA-256，读取后复验并把
      绑定写入 manifest；symlink、非普通文件和读取期间替换均 fail closed。
- [x] 两个 CSV.GZ 使用统一有序 schema：protocol 固定顺序的 19 项模型特征，随后为
      `m4l`、`label`、`split`、`physical_weight`、`train_weight`、`channelNumber`、
      `eventNumber`、`runNumber`、`mcWeight`、`xsec`、`kfac`、`filteff`、
      `sum_of_weights`。
- [x] `development.csv.gz` 只含原 split 为 train/validation 的行并保留逐行 split；
      `test.csv.gz` 只含原 split 为 test 的行。
- [x] 在 staging 中完成两份 CSV.GZ、cutflow、summary、双重哈希与 manifest 后整体
      promote；失败只发布 failure receipt，不发布部分成功 manifest。

测试要求：

- [x] 微型 ROOT 全链和重复运行 canonical hash 测试。
- [x] 两份 CSV 的精确 header、行分区、19 项模型特征 allowlist 和 forbidden-feature
      不进入模型的边界精确验证；必要 metadata 不被误删。
- [x] 缺分支、DSID 不符、非法单位、重复 identity 和真实数据配置拒绝。
- [x] Manifest 记录输入 stat/SHA-256；读取期间替换、symlink 和非普通文件拒绝。
- [x] 新 preprocess 入口的 import graph 不依赖旧 real-data、plotting 或 generic-predict
      模块。

### 5.3 CLI 完成

目标：实现批准的 `higgsml-preprocess` 参数面。

实现任务清单：

- [x] 连接 protocol、run config、pipeline 和 artifacts。
- [x] 规范成功/失败退出码和终端消息。

测试要求：

- [x] CLI smoke、occupied run fail-before-read，以及不受 protocol 允许的真实数据/DSID
      run config 在 ROOT 解析前 fail-closed 测试。

## 6. 验收标准

- 输出恰好包含 §5.2 固定顺序的 19 项模型特征和 13 项必要 metadata；metadata 不得进入
  模型特征 allowlist。
- Development=train+validation、test=test bucket；split 精确保持原行为但分文件发布。
- 新预处理无真实数据输入面。
- Manifest 绑定 protocol、run config、Git/代码身份、软件环境、输入 stat/SHA-256、输出、
  schema、计数与压缩/canonical 双重哈希。
- 专项测试全绿；完整测试相对 M1-01 基线不得新增失败、扩大失败集合或出现归因于 M1-02
  的失败。

## 7. 验证要求

项目声明的验证命令：

- `python -m pytest -q`
- M1-02 判定边界：M1-01 基线为 `776 passed, 211 failed, 2 skipped`；完整命令即使因同一
  历史集合 exit 1，也必须证明没有新增失败、失败集合增长或 M1-02 归因失败。历史面在
  M1-05/M1-06 删除后再要求全绿。

专项验证：

- `python -m pytest -q tests/unit/test_refactor_domain.py tests/unit/test_refactor_preprocessing.py tests/golden/test_refactor_preprocess_golden.py tests/integration/test_refactor_preprocess_cli.py`
- 微型 ROOT CLI smoke 由
  `tests/integration/test_refactor_preprocess_cli.py::test_higgsml_preprocess_micro_root_smoke`
  创建临时 ROOT/run config 并执行等价于
  `higgsml-preprocess --protocol config/preprocessing_protocol_v1.yaml --run-config <tmp>/run.yaml --run-dir <tmp>/run`
  的 console 入口，要求 exit 0 且只发布批准的 run layout。

## 8. 实施顺序

1. TDD 迁移 domain。
2. TDD 迁移 reader/pipeline。
3. 完成输出与 manifest。
4. 连接 CLI。
5. 运行专项和完整验证。

## 9. 风险控制

- 旧实现保留到 golden 对比完成，避免先删后猜。
- 不读取工作区真实 ROOT；集成测试只用临时微型 fixture。
- 浮点差异不得在结果产生后放宽容差。
- `preprocessing_protocol_v1.yaml` 保持 M1-01 提交内容不变；输出 layout/schema 属于批准
  设计与 application contract，未来 protocol 变更必须升版并重新评审。
- M1-05 删除历史文件前，以 import/CLI 边界防止新主链传递依赖真实数据、绘图或通用
  predict。
- 本 worktree 不含权威 ROOT 或冻结 run，不执行 345060/363490 权威计数/cutflow 复现；
  交付只对照记录冻结参考：345060 read `419943`、selected `350928`，363490 read
  `11260`、selected `471`，并明确该门未执行，不读取真实数据或既有冻结 artifact 补证。
- ROOT identity 按批准设计只在整次读取前后复验；逐 chunk 复验属于更强威胁模型。读取期间
  的临时替换可能先影响内存解析，但最终复验会阻止成功 manifest 发布。
- protocol V1 固定启用 lepton quality；非 enhanced legacy 路径由 domain/历史测试保护，
  不增加 CLI/run-config 科学覆盖面。

## 10. 交付结论

### 10.1 文档评审证据

- Document review：
  `docs/4-Reviews/sprint-m1-02-review-by-opencode-go-kimi-k2.7-code.md`、
  `docs/4-Reviews/sprint-m1-02-review-by-opencode-go-glm-5.2.md`。
- Review confirm：`docs/4-Reviews/sprint-m1-02-review-confirm.md`。
- 17 项逐条裁决已应用；metadata 只禁止进入 19 项模型 allowlist，不从审计 CSV 删除。
  权威 ROOT 门和历史物理删除分别明确延后到具备授权的环境与 M1-05。

### 10.2 代码评审证据

- Code review：
  `docs/4-Reviews/sprint-m1-02-code-review-by-opencode-go-kimi-k2.7-code.md`、
  `docs/4-Reviews/sprint-m1-02-code-review-by-opencode-go-glm-5.2.md`。
- Code review confirm：`docs/4-Reviews/sprint-m1-02-code-review-confirm.md`，29 条 finding
  全部逐项裁决。
- 已应用 AST/相对导入感知的 import graph、直接 domain 导入、untracked dirty、完整
  code/software identity、manifest luminosity、32 列唯一/disjoint、DSID CLI 负例、ZZ
  official-metadata golden、Angular5 hard run failure、配置 no-symlink、统一 DSID sample key
  和 M1-05 compat-stub 删除说明。
- 未解决但已接受的边界：ROOT 只做读取前后复验；sealed protocol V1 不补 luminosity 字段；
  非 enhanced selection 不扩展到 CLI。

### 10.3 环境与验证证据

- Worktree `D:\code\HiggsML-worktrees\xgboost-refactor`，branch
  `codex/xgboost-refactor`，base `409a728746616c5692103f94d1835ebdcb1c308b`；验证时实现为
  该 base 加 M1-02 working-tree change set。
- Windows 10 `10.0.19045`，Python `3.12.13`；awkward `2.13.0`、NumPy `2.5.2`、
  pandas `3.0.5`、PyYAML `6.0.3`、uproot `5.7.6`、vector `1.8.1`、XGBoost `3.4.1`。
- M1-02 专项最终重跑、M1-01+M1-02 unit/golden、CLI integration 和历史 domain 回归均
  通过；对应实际计数为 `22 passed, 2 skipped`、`64 passed, 3 skipped`、`13 passed`、
  `155 passed`。
- 完整 `python -m pytest -q --tb=no`：`798 passed, 211 failed, 4 skipped`。相对 M1-01
  `776 passed, 211 failed, 2 skipped` 新增恰好 22 pass/2 skip；211 个 failure test id
  与评审时已逐项复现的 M1-01 集合相同，且没有 M1-02 测试失败。
- `pip install -e .`、`pip check`、console/module 形式的 preprocess/xgboost 四项 help、
  `compileall` 和 `git diff --check` 均 exit 0。
- 所有集成数据均为 `%TEMP%` 微型 ROOT。未读取真实数据、工作区权威 ROOT、冻结 run 或
  held-out test；345060/363490 权威 count/cutflow 门未执行。

### 10.4 Artifact 与提交证据

- 微型 ROOT 重复 run 均发布且仅发布批准的六文件 layout；每次为 8 development、4 test、
  总计 12 行，列为唯一且有序的 19 model + 13 metadata。cutflow/summary 使用
  `higgs_345060`、`zz_363490` key。
- Manifest 记录 protocol/run-config 路径与 SHA-256、Git commit/worktree dirty、代码哈希、
  软件版本、`luminosity_pb: 10000.0`、ROOT device/inode/size/mtime/SHA-256、计数、schema
  及两份 CSV 的 compressed/canonical 双重哈希；重复 run 的 canonical hashes 相同。
- 只 stage M1-02 plan/reviews/implementation/tests；M1-03 至 M1-06 plan 保持未跟踪。
- 提交消息：`feat: complete sprint-m1-02 code and change base on reviews`；提交 hash 在 Git
  commit 完成后由交付响应记录。
