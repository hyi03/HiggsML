# Sprint M1-04 Review Confirm

**Reviewed Inputs**

- `docs/3-Plan/sprint-m1-04.md`
- `docs/4-Reviews/sprint-m1-04-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-04-review-by-opencode-go-glm-5.2.md`
  （`opencode-go/glm-5.2` 超过普通文档评审窗口且未生成报告后，由
  `deepseek/deepseek-v4-flash` 独立 fallback 写入原路径；实际 reviewer 已在报告中记录）
- `AGENTS.md`、FR-001、批准设计、protocol V1、提交 `4e7d540` 的 M1-03 合同与 legacy
  `experiment_runner` test-evaluation authority

**Review Date**

- 2026-09-02

## Overall Conclusion

两份评审均正确识别了 M1-04 对 exactly-once state machine、传递 test binding 和输出合同的
描述不足。下表覆盖全部 30 条 finding：26 Accept、4 Partial、0 Reject。四条 Partial
分别收窄 protocol 复核对象、test metric 集合及 pre-claim failure receipt 语义，避免引入
未批准的 test KS/reproduction 判定或依赖可移动的外部 XGBoost protocol 原路径。

计划在应用本 confirm 后可接受并进入 TDD 实施；不需要修改 FR、批准设计或 protocol V1。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---|---|---|---|---|---|---|---|
| 1 | High | Requirement | `Kimi H1` | 未枚举 open-test 必须复核的四项 qualification 条件。 | Accept | FR R5、设计 §9 与 M1-03 `qualify` 固定 AUC、三 KS、严格效率和 OOF 完整性。 | §5.1 要求从冻结 OOF/working points 重算四门并与 qualification/manifest 完全一致；补边界与篡改测试。 |
| 2 | High | Correctness | `Kimi H2` | claim-before-test-parse 只写在风险控制，没有成为实现合同。 | Accept | 设计 §6.3/§11 要求 claim 一旦占用即不可重开，且 test 结果不能反向决策。 | §5.1 固定 reserve test run → 无 test-content 校验 → claim → test read/parse 的顺序；补 claim 后损坏与不可重开测试。 |
| 3 | High | Requirement | `Kimi H3` | open-test CLI 参数面未固定。 | Accept | FR R3/R7 与设计 §6.3 只允许 `--development-run --run-dir`。 | §5.3 明确仅这两个参数，拒绝 overwrite/protocol/model/features/seed/folds/candidate/threshold 等覆盖及未知项。 |
| 4 | Medium | Requirement | `Kimi M1` | 两份 protocol 应 byte-identical 复核。 | Partial | Development run 已把 XGBoost protocol 原始 bytes 封存在 `config.yaml` 并以 manifest SHA 绑定；依赖其外部源路径会削弱冻结 run 自包含性。Preprocess run 没有 protocol snapshot，只保留 path/SHA identity。 | 校验 development `config.yaml` SHA 与 manifest protocol identity 并用 sealed V1 loader 解析；传递复核 upstream manifest 绑定的 preprocessing protocol path/SHA。无需重新依赖 development manifest 中的外部 XGBoost protocol source path。 |
| 5 | Medium | Correctness | `Kimi M2` | test metric/status 不明确，建议 AUC、KS、效率与新 completed 状态。 | Partial | V1 test authority `experiment_runner._test_metrics` 只定义 `status=complete`、rows、weighted/unweighted AUC 和冻结阈值的每类 efficiency/selected rows；没有 test KS 或 reproduction gate。 | 删除 reproduction 状态；test-run manifest 使用 `status=succeeded`，metrics 使用 `status=complete`，等价迁移 AUC/效率。不得新增 test KS、门槛或 failure reason 决策；异常由 `failure.json` 表达。 |
| 6 | Medium | Requirement | `Kimi M3` | claim 前未明确要求 manifest `test_opened=false` 与 claim 文件不存在。 | Accept | M1-03 manifest 固定 `test_opened: false`，真正开启记录只属于 M1-04 state claim。 | §5.1 exact-validate `test_opened is false`，并以 `state/test_opening.json` no-clobber 创建作为唯一 opened marker。 |
| 7 | Medium | Requirement | `Kimi M4` | Test 输入缺完整 32 列与双哈希校验。 | Accept | M1-02 preprocess manifest 固定 full schema、compressed/canonical SHA、rows/columns。 | §5.2 固定传递 binding、32 列顺序、test-only split、双类、有限值、唯一 identity、rows/columns 与双哈希；逐类 tamper 测试。 |
| 8 | Medium | Test | `Kimi M5` | `-k` 专项门会因命名静默漏测。 | Accept | M1-02/M1-03 已改用显式文件列表。 | §7 改为 `tests/unit/test_refactor_test_opening.py` 与 `tests/integration/test_refactor_open_test_cli.py`。 |
| 9 | Medium | Documentation | `Kimi M6` | §10 是占位符。 | Accept | Sprint workflow 要求预置 document/code review、验证和提交证据。 | 按 M1-03 结构预填 §10.1～§10.4。 |
| 10 | Medium | Verification | `Kimi M7` | 未预注册 M1-03 完整测试边界。 | Accept | M1-03 交付基线为 `826 passed, 211 failed, 4 skipped`。 | §7 固定不得增加 failure、扩大 211 test-id 集合或出现 M1-04 归因失败，§10 记录实际比较。 |
| 11 | Low | Clarity | `Kimi L1` | Development claim 与 test-run artifact 边界含混。 | Accept | 设计 §10.1 把 claim 放在 development run，§10.2 把 test artifacts 放在新 test run。 | §3/§5.1 明确两处归属；development manifest 永不回写。 |
| 12 | Low | Traceability | `Kimi L2` | 未链接 M1-03 review/code-review confirms。 | Accept | 两份 confirm 是 open-test 消费的已提交上游合同。 | §2 添加相对链接并声明消费 eligible-only layout/manifest/no-claim 合同。 |
| 13 | Low | Documentation | `Kimi L3` | Sprint 目标未引用 FR R6 与设计 §6.3/§11。 | Accept | 这些条款是一次性生命周期和失败语义 authority。 | §1 增加引用。 |
| 14 | Low | Requirement | `Kimi L4` | 模型存在性、哈希与 XGBoost JSON loadability 未固定。 | Accept | M1-03 eligible-only `model/model.json` receipt 是唯一可评分模型。 | §5.1 要求 regular/no-symlink、receipt/hash、XGBoost `load_model` 和 19-feature 绑定复核。 |
| 15 | Info | Positive | `Kimi I1` | Synthetic-only/no real frozen opening 边界正确。 | Accept | 与 AGENTS、FR 非目标和设计 §4.2 一致。 | 保留并在 §10 记录未执行权威 open-test。 |
| 16 | Info | Risk | `Kimi I2` | Claim-before-parse 与 receipt 不泄露 test 内容方向正确。 | Accept | 支持 FR R6/R7 和设计 §11。 | 保留风险控制，并提升到 §5.1 可测试任务。 |
| 17 | Info | Traceability | `Kimi I3` | 实施顺序合理。 | Accept | 上游验证/claim 在 scoring/CLI 前符合 TDD 与生命周期依赖。 | 保持顺序，增加先扩展 valid-test fixture 的明确步骤。 |
| 18 | High | Requirement | `DeepSeek H1` | `test_reproduced/test_nonreproduction` 无当前 authority。 | Accept | 术语只属于冻结历史实验；FR、批准设计和 protocol V1 均未定义 test reproduction decision。 | 从计划删除；成功仅发布 `succeeded` manifest 与 `complete` metrics。若未来要 reproduction gate，必须新 protocol/design。 |
| 19 | High | Correctness | `DeepSeek H2` | Claim location、顺序和哪些失败消耗开启权未固定。 | Partial | 设计 §11 的精确语义是“claim 一旦成功占用”后成功/失败均不可重开；FR 的“失败也消耗”按此解释为 post-claim failure。Occupied output 在输入读取前拒绝且不能写 receipt。 | Claim 位于 development run；新 test run 先以 `RunTransaction` 占用。占用后、claim 前的 eligibility/hash 拒绝写 test-run `failure.json` 但不消耗；occupied target 零读取/零写；claim 后任何失败永久消耗并由 claim + test-run failure receipt 记录。 |
| 20 | Medium | Correctness | `DeepSeek M3` | 未固定 dev manifest → preprocess manifest → test artifact 传递哈希链。 | Accept | M1-03 upstream payload 只直接存 development hashes，test record 只能从绑定 preprocess manifest 取得。 | §5.2 精确列出 manifest SHA、`outputs.test` exact shape、路径 containment、compressed/canonical hash、size/rows/columns 与解析后 schema 验证。 |
| 21 | Medium | Verification | `DeepSeek M1` | 未预注册完整套件 failure-set 门。 | Accept | 与 No.10 独立同结论，并强调不能只比计数。 | §7/§10 同时记录 test-id 集合比较。 |
| 22 | Medium | Test | `DeepSeek M2` | `-k` 命名耦合可能漏测。 | Accept | 与 No.8 独立同结论。 | 使用显式两个模块路径。 |
| 23 | Medium | Correctness | `DeepSeek M4` | 指标语义和 frozen threshold 来源未固定。 | Partial | Frozen score thresholds 必须来自 development `working_points.json`，不能从 protocol targets/test 重算；但 V1 test authority 没有 test KS。 | 等价迁移 weighted/unweighted AUC、每工作点 signal/background efficiency 与 selected rows；阈值只读 development artifact；测试 poison protocol targets 与 test score distribution，证明阈值不重算。 |
| 24 | Medium | Test | `DeepSeek M5` | 现有 fixture 故意写非法 test，无法支持成功全链。 | Accept | M1-03 test-deny fixture 的非法 bytes 是有意设计。 | 扩展 helper 仅在显式 `valid_test` 模式生成 test-only 32 列 deterministic gzip 与正确 manifest receipt；默认仍保持 deny fixture。 |
| 25 | Medium | Requirement | `DeepSeek M6` | Test-run layout、manifest、prediction schema 和失败语义未固定。 | Accept | 设计 §10.2 固定顶层布局，legacy runner 固定 32 输入列加 `xgb_score` 和三张 test plot。 | §5.2 固定六文件 success allowlist：2 artifacts、1 prediction、3 plots；prediction 为 `OUTPUT_COLUMNS + xgb_score`；manifest 绑定 claim/dev/preprocess/test/model/protocol/code/software/outputs/counts/schema/hashes；failure 为 `failure.json` 且无 manifest。 |
| 26 | Low | Documentation | `DeepSeek L1` | §10 缺四类证据预置。 | Accept | 与 No.9 独立同结论。 | 预填四小节。 |
| 27 | Low | Clarity | `DeepSeek L2` | Fresh runs-root transaction 与 claim/receipt 区分不清。 | Accept | M1-03 `RunTransaction` 已提供 direct `runs/<id>`、no-clobber、failure/manifest-last 语义。 | §5.1 指定复用该 transaction；claim 是 development durable marker，test run 以 manifest 或 failure receipt 终结。 |
| 28 | Low | Traceability | `DeepSeek L3` | §2 未说明具体 M1-03 消费合同。 | Accept | 与 No.12 同方向且补充 layout/state。 | §2 明确 commit `4e7d540`、eligible manifest/model/OOF/working-points receipts 和 claim absence。 |
| 29 | Info | Consistency | `DeepSeek I1` | 科学安全边界正确。 | Accept | Worktree 无 `data/`/`runs/` 权威输入，计划明确 synthetic-only。 | 保留；实现和验证不得读取、哈希或打开权威/冻结 test。 |
| 30 | Info | Requirement | `DeepSeek I2` | §6 四项验收直接覆盖 FR R6。 | Accept | 只有 eligible/unopened、并发唯一、失败后不重开、无 write-back 都正确。 | 为每项建立命名测试，并补 fresh second run-dir 二次开启拒绝。 |

## Needs Immediate Action

- 删除未授权 reproduction 状态，冻结 ordinary success/metrics status。
- 冻结 development claim 与 test-run transaction 的位置、顺序、消耗语义和并发行为。
- 冻结 development/OOF/model/protocol/preprocess/test 的完整传递验证链。
- 冻结 legacy-equivalent test score/metric/plot schema 和六文件 success allowlist。
- 建立 valid synthetic test fixture、显式专项门与 M1-03 failure-set 基线。

## Can Be Deferred

- 任何 test reproduction 门、test KS 或新的 test 资格阈值都不属于 protocol V1；未来若需要，
  必须新设计、新 protocol 和新 review。
- 权威冻结 run 的实际 open-test 未授权，继续不执行。

## Final Status

文档为“修正后接受”。应用以上 Accept/Partial 行动后，可进入 Sprint M1-04 TDD 实施；
没有阻塞性未决问题。
