# Sprint M1-04

## 1. Sprint 目标

覆盖 [FR-001](../1-Requirement/FR-001-angular19-xgboost-refactor.md)，实现绑定、原子、
一次性的 `higgsml-xgboost open-test`，只评价已冻结且 eligible 的 XGBoost 模型。
一次性生命周期的权威为 FR-001 R6/R7 与
[批准设计](../superpowers/specs/2026-09-01-xgboost-refactor-design.md) §6.3/§10/§11。

核心目标：

- 验证 development、preprocess、protocol、模型和 OOF 证据完整未变。
- Claim 后失败也消耗唯一 test-opening 权，杜绝反复窥视 test；claim 前的 fail-closed
  拒绝尚未读取 test bytes，不消耗开启权。
- Test 结果不影响任何上游选择。

## 2. 前置依赖

- `sprint-m1-01` 至 [sprint-m1-03](sprint-m1-03.md) 已完成并提交；M1-03 commit 为
  `4e7d540`。
- M1-03 的 [document review confirm](../4-Reviews/sprint-m1-03-review-confirm.md) 与
  [code review confirm](../4-Reviews/sprint-m1-03-code-review-confirm.md) 是本 Sprint 的上游
  消费合同。

协同说明：只消费 M1-03 发布的 eligible development manifest、模型、OOF、working points
及其 upstream preprocess binding；development 阶段不存在 `state/test_opening.json`。

## 3. 纳入范围

- `src/training/test_opening.py`
- `src/cli/xgboost.py` 的 `open-test`
- test metrics、predictions、plots、manifest 与 failure receipt
- 一次性 claim 和篡改测试
- Development run 内新增的 `state/test_opening.json` 是唯一、不可覆盖的 opened marker；
  新 test run 不包含 `state/`。

## 4. 暂不纳入范围

- 对真实冻结 run 实际执行 test-opening。

原因：本 Sprint 只实现并用合成 fixture 验证机制，用户未授权打开真实 held-out test。

## 5. 工作范围

### 5.1 上游绑定与 claim

目标：在读取 test 前完成资格、布局和哈希验证并原子占用。

实现任务清单：

- [x] `--run-dir` 必须是命名 `runs/` 根的全新直接子目录；先复用 `RunTransaction` 原子占用
  新 test run，occupied target 在任何 development/protocol/test 输入读取前拒绝且零改写。
- [x] Exact-validate eligible development run 的九文件 allowlist、manifest V1、
  `test_opened is false`、protocol/config snapshot、candidate/final parameters、模型、OOF、
  qualification、working points、counts/schema 与全部 output receipts；development manifest
  和既有 artifact 永不回写。
- [x] 从冻结 OOF、working points 和 protocol 重新计算并逐字段比较四项资格证据：weighted
  OOF AUC `>= minimum_weighted_oof_auc`；三个 ZZ `m4l` KS 均
  `<= maximum_background_ks`；每个 working point 的 signal efficiency 严格大于 achieved
  background efficiency；OOF 有限、唯一且覆盖全部 development event。不得只信任
  `status: eligible` 字符串。
- [x] 校验 development `config.yaml` bytes 的 SHA-256 等于 manifest protocol identity，并用
  sealed XGBoost V1 loader 解析；验证 upstream preprocess manifest SHA-256 与其中绑定的
  preprocessing protocol path/schema/SHA。Development 不依赖外部 XGBoost protocol 原路径。
- [x] 校验 `model/model.json` 为 regular non-symlink、receipt/hash 匹配、可由 XGBoost
  `load_model` 加载，且只接受冻结 19 特征顺序；模型不得重新 fit。
- [x] 在不读取 `test.csv.gz` bytes 的前提下，从已验证 preprocess manifest 取得并 exact-
  validate `outputs.test` 的 path/rows/columns/size/双 SHA identity，校验 path containment、
  regular/non-symlink 状态；所有 test bytes 的读取、哈希、解压和解析必须晚于 claim。
- [x] 在 development run 内以 exclusive/no-clobber 方式创建
  `state/test_opening.json`，内容固定为 schema/status/created time、development manifest
  SHA-256、resolved test-run path 和预期 test artifact identity；claim 文件创建后永不改写，
  是唯一 opened marker。Development manifest 的 `test_opened: false` 保持冻结不回写。
- [x] 顺序固定为：reserve test run → 无 test-content 的上游/eligibility/hash-identity 校验 →
  atomic claim → test read/hash/decompress/parse/score → test manifest。并发不同 test run-dir
  时恰有一个 claim 获胜者，失败者不得读取 test。
- [x] Test run 在 claim 后成功以 manifest 终结，异常以 `failure.json` 终结且无 manifest；
  claim 后任何失败均永久消耗开启权。Claim 前验证失败在已占用 test run 中写
  `failure.json` 但不创建 claim；occupied output 因从未占用而不写 receipt。

测试要求：

- [x] 不合格、四门矛盾、未知/多余布局、缺文件、protocol/model/OOF/working-point/preprocess
  manifest hash 变化、预存 claim、重复调用、不同 run-dir 二次调用和并发调用。
- [x] File-access spy 证明 claim 前不读取 test bytes；claim 后 test 损坏/模型 scoring 异常会
  写 failure receipt、保留 claim，且重试拒绝；occupied/pre-claim 拒绝不消耗 claim。

### 5.2 冻结 test 评价

目标：只加载冻结模型和冻结工作点产生 test 证据。

实现任务清单：

- [x] Claim 后恰好读取一次绑定 test bytes，先验证 compressed SHA/size，再 deterministic
  gzip 解压并验证 canonical CSV SHA，随后解析并校验 manifest rows/columns、固定有序 32 列、
  `split == {"test"}`、label 0/1、有限数值和 `(channelNumber,eventNumber)` 唯一性；禁止
  development 行或其他字段布局。
- [x] 用冻结 XGBoost JSON 和固定顺序 19 特征评分，不调用任何 `fit`；prediction 固定为
  `OUTPUT_COLUMNS + ("xgb_score",)` 共 33 列，使用 deterministic gzip。
- [x] 等价迁移 legacy `experiment_runner._test_metrics`：`status: complete`、test rows、
  weighted AUC（`abs(physical_weight)`）、unweighted AUC，以及 development
  `working_points.json` 冻结 score threshold 下 signal/background efficiency 与 selected
  rows。不得从 protocol target 或 test scores 重算 threshold，不新增 test KS、qualification、
  reproduction gate 或任何 test-result decision。
- [x] Success test run 精确为六文件：
  `artifacts/{test_metrics.json,manifest.json}`、`predictions/test_scores.csv.gz`、
  `plots/{roc_curve.png,score_distribution.png,score_vs_m4l.png}`；无 `config.yaml`、`model/`
  或 `state/`。Manifest `schema_version: 1.0`、`run_type: xgboost_test`、`status: succeeded`，
  并绑定 claim、development/preprocess/test/model/protocol/code/software、outputs、counts、
  schema、features、working points 与 hashes。
- [x] Manifest 发布前再次验证 claim、development manifest/artifacts、preprocess manifest、
  protocol/model/test bytes 均未改变；test metrics、scores 或 plots 的任何替换均 fail closed。

测试要求：

- [x] Golden 对照 legacy score/metrics/三张 plot 的输入语义；poison protocol target 和 test
  score distribution，证明 test 结果变化不改变模型、候选、阈值、资格或 development bytes。
- [x] Test compressed/canonical hash、32 列顺序、split、双类、identity、rows/counts 及
  before-manifest input/output mutation 负例。

### 5.3 CLI 集成

目标：完成批准的最小参数面和错误退出码。

实现任务清单：

- [x] `open-test` parser 只允许 `--development-run --run-dir`；拒绝 `--overwrite`、
  `--protocol`、`--model`、features/seed/folds/candidate/threshold/qualification 覆盖及未知项。
- [x] 连接 `open-test` application service；普通 Exception 归一化为
  `higgsml-xgboost failed: Type: message`/exit 1，不捕获 `BaseException`。
- [x] 成功仅输出 `succeeded`；失败消息不包含 test bytes、scores、labels 或事件内容。

测试要求：

- [x] 扩展合成 helper 的显式 `valid_test` 模式：生成 test-only 32 列 deterministic gzip、
  正确双哈希/计数和真实可加载微型 XGBoost eligible model；默认 M1-03 deny fixture 不变。
- [x] Eligible module/console CLI 全链成功；以同一 development run、不同新 test run-dir
  第二次调用 exit 1，且没有第二次 test read。

## 6. 验收标准

- 只有完整、eligible、未开启 run 能进入 test。
- 原子 claim 在并发下恰有一个获胜者。
- 失败后不能重开。
- Test 不触发训练或回写决策。
- Development manifest/config/model/OOF/working points bytes 保持不变，唯一允许的新上游状态
  是 append-only `state/test_opening.json`。
- Success test run 只有批准的六文件；pre-claim/post-claim failure 与 claim 消耗边界可审计。

## 7. 验证要求

项目声明的验证命令：

- `python -m pytest -q`

完整套件按 M1-03 已记录的 `826 passed, 211 failed, 4 skipped` 判定：不得新增 failure、
不得扩大 211 个 failure test-id 集合、不得出现 M1-04 attributable failure；实际计数与
集合比较在 §10 记录。历史失败仍由 M1-05/M1-06 删除旧执行面后清零。

专项验证：

- `python -m pytest -q tests/unit/test_refactor_test_opening.py tests/integration/test_refactor_open_test_cli.py`
- 合成 eligible fixture CLI smoke。

## 8. 实施顺序

1. TDD 扩展显式 valid-test fixture，默认 deny fixture 保持不变。
2. TDD 实现上游验证、transaction 与 claim state machine。
3. 等价迁移 test scoring、metrics、plots 和 artifacts。
4. 连接 CLI。
5. 覆盖并发、pre/post-claim failure、二次开启、阈值 poison 和篡改。
6. 运行专项和完整验证。

## 9. 风险控制

- 所有集成测试使用临时合成 test，不访问现有冻结 test。
- Claim 必须早于 test bytes 的 read/hash/decompress/parse；claim 前只允许读取 manifest 中的
  test identity metadata 和执行 lstat/path containment。
- Receipt 记录失败阶段但不泄露 test 内容。
- 不读取、哈希或盘点真实数据、权威 ROOT、冻结 run 或其 held-out test；不执行权威
  345060/363490 test-opening。
- 不以 test 结果调整模型、候选、阈值、qualification 或任何 protocol 字节。

## 10. 交付结论

### 10.1 文档评审证据

- Document review：
  `docs/4-Reviews/sprint-m1-04-review-by-opencode-go-kimi-k2.7-code.md`、
  `docs/4-Reviews/sprint-m1-04-review-by-opencode-go-glm-5.2.md`。
- Review confirm：`docs/4-Reviews/sprint-m1-04-review-confirm.md`。全部 finding 已逐项裁决；
  Accept/Partial 项已应用到本 Sprint 文档，Reject 项均保留了 V1 科学行为、一次性开启和
  exactly-once test read 边界，没有修改批准设计或 protocol V1 bytes。

### 10.2 代码评审证据

- 独立 code review：
  `docs/4-Reviews/sprint-m1-04-code-review-by-opencode-go-kimi-k2.7-code.md`、
  `docs/4-Reviews/sprint-m1-04-code-review-by-opencode-go-glm-5.2.md`。第一份报告因原主模型未能
  遵守只写报告约束，实际由 `deepseek/deepseek-v4-pro` fallback 独立生成；第二份为 GLM
  独立重跑，运行时临时移走第一份报告，完成后按 SHA-256 原样恢复。
- Code-review-confirm：`docs/4-Reviews/sprint-m1-04-code-review-confirm.md`，24 条 finding
  裁决为 13 Accept、4 Partial、7 Reject。已应用严格 64-hex identity、state mkdir 后
  重校验、argparse 禁止缩写、维护链 code hash、matplotlib software identity、candidate/
  fold/OOF receipt exact-validation、fold 中位数 final tree count、完整 final parameters 与
  booster rounds 三方一致、文件和目录 allowlist、同一 resolved `runs` root、显式 fail-closed
  类型检查及 helper 重命名。
- 已补齐 legacy metrics/三图 golden、两个独立进程 claim、CLI 二次开启、缺文件、non-hex、
  split、单类/零权重、重复 identity、rows/canonical hash、发布前 fingerprint 变化和 code
  hash 覆盖测试。保留 single-read，不引入二次 test hash、test KS、reproduction gate、fsync
  协议或共享 provenance 重构。

### 10.3 环境与验证证据

- 验证环境：Windows、Python `3.12.4`、matplotlib `3.11.1`、NumPy `2.5.2`、pandas
  `3.0.5`、scikit-learn `1.9.0`、XGBoost `3.4.1`。
- M1-04 专项：
  `python -m pytest -q tests/unit/test_refactor_test_opening.py tests/integration/test_refactor_open_test_cli.py`
  为 `36 passed in 20.08s`。
- 新维护链：`python -m pytest -q tests/unit tests/golden tests/integration` 为
  `141 passed, 3 skipped in 43.48s`。其中 eligible module/console `open-test` 均真实执行并
  输出 `succeeded`；同一 development run 的第二个新 run-dir 返回 exit 1、already-opened、
  failure receipt 且无 manifest。
- Editable install 成功，`python -m pip check` 为 `No broken requirements found.`；module/
  console 的 preprocess、XGBoost 和 open-test help 均 exit 0；`python -m compileall -q src tests`
  与 `git diff --check` 均通过。
- 当前完整套件为 `862 passed, 211 failed, 4 skipped, 5 warnings in 119.14s`。为做集合级
  比较，在临时 detached worktree 复跑 M1-03 提交 `4e7d540`，得到
  `826 passed, 211 failed, 4 skipped, 5 warnings in 104.17s`。两份 JUnit 的 failure test-id
  集合均为 211 项，差分为新增 0、缺失 0；因此 M1-04 恰增加 36 pass、0 failure、0 skip，
  没有 M1-04 attributable failure。临时验证 worktree 确认干净后已移除。
- 第一位主评审曾违反只写报告约束执行虚拟环境命令，发现后立即中止；随后已恢复并重验
  Python `3.12.4`、NumPy `2.5.2`、XGBoost `3.4.1`、editable install 与 `pip check`。
- 全部新增 test-opening 验证只使用 `%TEMP%` 合成 Higgs/ZZ MC。未读取、哈希或盘点真实
  数据、权威 ROOT、冻结 run 或既有 held-out test，未执行权威 345060/363490 test-opening。

### 10.4 Artifact 与提交证据

- Claim 固定位于 development run 的 `state/test_opening.json`，以 exclusive/no-clobber
  创建；线程和两个独立 Python 进程竞争均恰好一胜一败。Claim 前失败不消耗开启权，claim
  后 test/hash/schema/scoring/fingerprint 失败永久消耗，后续不同 run-dir 在读取 test 前拒绝。
- Test bytes 在 claim 后恰好读取一次。内容证明边界为这一次读取时验证 compressed SHA-256/
  size 与 deterministic gzip 解压后的 canonical CSV SHA-256；manifest 发布前不二次读取，
  而以最终 `(size, mtime_ns, ctime_ns, inode)` fingerprint 检测路径/文件身份变化。该边界由
  file-access spy 和 before-manifest fingerprint mutation 测试锁定。
- Eligible success 精确发布六文件、prediction 固定为 33 列、指标与三张图等价 legacy
  authority、阈值只来自冻结 development working points；development manifest/config/model/
  OOF/working points 均不回写，唯一新增上游状态是 append-only claim。
- 只 stage M1-04 plan/reviews/implementation/tests；M1-05/M1-06 plan 保持未跟踪。
- 提交消息：`feat: complete sprint-m1-04 code and change base on reviews`；提交 hash 在 Git
  commit 完成后由交付响应记录。
