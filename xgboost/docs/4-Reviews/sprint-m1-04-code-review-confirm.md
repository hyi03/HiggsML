# Sprint M1-04 Code Review Confirm

**Reviewed Inputs**

- `src/training/test_opening.py`
- `src/cli/xgboost.py`
- `src/training/trainer.py`
- `tests/refactor_training_support.py`
- `tests/unit/test_refactor_test_opening.py`
- `tests/integration/test_refactor_open_test_cli.py`
- `docs/4-Reviews/sprint-m1-04-code-review-by-opencode-go-kimi-k2.7-code.md`
  （主模型未能按只写报告约束完成，实际由 `deepseek/deepseek-v4-pro` fallback 独立生成）
- `docs/4-Reviews/sprint-m1-04-code-review-by-opencode-go-glm-5.2.md`
- FR-001、Sprint M1-04、批准设计、两份 protocol V1、M1-03 manifest/artifact 合同与
  legacy `experiment_runner` test-evaluation authority

**Review Date**

- 2026-09-02

## Overall Conclusion

两份独立评审均确认一次性 claim、claim-before-test-read、冻结阈值、V1 指标、六文件输出和
失败收据的核心实现正确，未发现 Critical/High 缺陷。本 confirm 覆盖两份报告全部 24 条
finding：13 Accept、4 Partial、7 Reject。

接受项主要补齐 Sprint 已声明但尚缺的可执行证据，并收紧 code/final-parameter/receipt/
run-path 审计绑定。Partial 项保留 exactly-once test read 和当前 Sprint 边界，只做最小的
跨进程 claim、优先负例和发布前指纹证据。Reject 项要么已由紧邻调用的强校验覆盖，要么会
偏离 legacy 等价性、exactly-once read 或扩张为非必要共享模块重构。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---|---|---|---|---|---|---|---|
| 1 | Medium | Test | `Kimi M1` | 缺少 legacy test metrics/plot 语义 golden。 | Accept | Sprint §5.2 明确要求 golden；当前只有源码逐行旁证。 | 新增同一 scored test frame 的 legacy/new metrics 完全相等断言，并比较三张 plot 的生成输入/PNG 结果。 |
| 2 | Medium | Test | `Kimi M2` | 并发只用线程，未验证跨进程 O_EXCL。 | Partial | Sprint 只要求并发唯一获胜；线程测试已穿过同一文件系统 `open("xb")`，但直接跨进程证据能加强一次性 claim。 | 增加两个独立 Python 进程竞争同一 claim 的聚焦测试，不重复执行完整 XGBoost scoring。 |
| 3 | Low | Correctness | `Kimi L1` | `_test_metrics` 内部没有再次保护零分母。 | Reject | `_validate_test_frame` 在唯一生产调用点紧邻执行，并已要求两类绝对权重和均大于 0；保持 `_test_metrics` 与 legacy 逐行等价是批准合同。 | 不在 metrics 内新增重复分支；用 golden 锁定等价性，零权重继续由输入验证拒绝。 |
| 4 | Low | Security | `Kimi L2` | `state` symlink 检查与 mkdir 之间存在 TOCTOU。 | Accept | Claim 目录位于可变文件系统；二次验证不会改变 claim 顺序或科学行为。 | mkdir 后重新 lstat/resolve state 目录，确认 regular directory、非 symlink 且仍位于 development run，再 exclusive-create claim。 |
| 5 | Low | Robustness | `Kimi L3` | Claim 未 fsync，崩溃可留下部分文件。 | Reject | 设计规定 claim 一旦成功占用即永久消耗；部分 claim 同样安全地 fail closed，后续从不信任既有 claim 内容。 | 不引入平台相关 fsync 协议；保留 any-existing-claim-is-terminal 语义。 |
| 6 | Low | CLI | `Kimi L4` | argparse 默认接受长选项缩写。 | Accept | Sprint §5.3 要求拒绝未知项，缩写会扩大表面。 | 对顶层 parser 与两个 subparser 设置 `allow_abbrev=False`，补缩写拒绝断言。 |
| 7 | Info | Clarity | `Kimi I1` | Test manifest 中 claim path 的相对作用域可能含混。 | Reject | Manifest 同一层已记录 `development_run.path`，Sprint/设计明确 claim 位于 development run；改字段会无必要扩展 V1 schema。 | 保留当前字段，并在 Sprint 交付证据中明确它相对 development run。 |
| 8 | Info | Requirement | `Kimi I2` | `score_vs_m4l.png` 展示 held-out MC mass。 | Reject | 该图由设计 §10.2 与 Sprint §5.2 明确批准，输入仅 synthetic/MC，不涉及真实数据。 | 保留批准 artifact，不作修改。 |
| 9 | Info | Performance | `Kimi I3` | 并发 loser 在 claim 前重复完整资格验证。 | Reject | Claim 必须晚于完整无-test-content 校验；提前 claim 会错误消耗未通过资格验证的开启权。 | 保持顺序；这是 fail-closed 生命周期成本。 |
| 10 | Info | Portability | `Kimi I4` | stat fingerprint 字段跨平台语义不同。 | Reject | 初次 compressed SHA 是 test 内容 authority；发布前 fingerprint 用于检测路径/文件身份变化，且当前目标平台测试通过。 | 不改变身份字段；Partial No.17 另行补充其验证边界。 |
| 11 | Medium | Auditability | `GLM F1` | `_code_sha256` 漏掉维护链源文件。 | Accept | FR R7 要求绑定代码；reader/profiles/application/preprocess CLI/progress 均属于新维护链。 | 对新 `src/{artifacts,cli,domain,preprocessing,training}` 包全部 `.py` 加根级 config/validation/progress 做稳定哈希，并更新测试。 |
| 12 | Medium | Correctness | `GLM F2` | `final_parameters` 未从 fold evidence/model 树数 exact-validate。 | Accept | Sprint §5.1 明确列出 final parameters；当前只验证 candidate 与特征。 | 解析 candidate/fold receipts，重算最终树数与完整 final parameters，并与 loaded booster rounds 三方一致后才 claim。 |
| 13 | Medium | Test | `GLM F3` | 缺少 §5.2 legacy golden。 | Accept | 与 No.1 同方向但独立给出 plots/legacy authority 证据。 | 同 No.1，保留独立 finding 追踪。 |
| 14 | Medium | Test | `GLM F4` | 缺 CLI 层不同 run-dir 二次调用 exit 1/无第二次读取。 | Accept | Sprint §5.3 原文要求该证据；单元层不足以锁 CLI exit/stderr。 | 首次 module CLI 成功后破坏 test bytes，再以第二新 run-dir 调用；断言 exit 1、already-opened 错误、failure receipt、无 manifest，证明未读损坏 bytes。 |
| 15 | Medium | Maintainability | `GLM F5` | Fixture 依赖后续将删除的 legacy `full_training_policy`。 | Accept | `src.training.folds.development_fold` 已是等价新 authority；M1-05 将删除旧执行面。 | 将 import 切换到 `src.training.folds`，不改变 fixture 数据。 |
| 16 | Low | Correctness | `GLM F6` | Test receipt SHA 只查长度、不查 hex。 | Accept | 畸形 identity 应在 claim 前失败，否则会不必要消耗开启权。 | 复用严格 64-hex 规则并加 pre-claim 负例。 |
| 17 | Low | Verification | `GLM F7` | 发布前 test 只复核 stat，不重读 bytes。 | Partial | Sprint 同时要求恰好读取一次 test bytes；二次读/hash 会直接冲突。初次 SHA 验证内容，末次 stat 指纹验证同一路径文件未变化。 | 保留 single-read + fingerprint，新增 fingerprint-change-before-manifest 测试，并在 Sprint 证据中明确该 proof boundary；不二次读取 test。 |
| 18 | Low | Correctness | `GLM F8` | Candidate/fold/OOF receipt rows/columns 未核取值。 | Accept | Sprint §5.1 要求 exact-validate 全部 receipts；当前只绑定 path/sha/size。 | 解析三个 CSV，校验固定 columns、rows、candidate/fold coverage 与 OOF receipt rows/columns。 |
| 19 | Low | Security | `GLM F9` | 文件级 allowlist 看不到空目录，且 test run 可嵌套上游 run。 | Accept | 唯一允许的上游写入是 claim；嵌套 test run 会违反该边界。 | 要求 development/test 是同一 resolved `runs` root 的不同 direct children；文件与目录均 exact-allowlist，拒绝 symlink/额外空目录。 |
| 20 | Low | Test | `GLM F10` | 缺文件、split/双类/identity/rows/hash/发布前变更等负例不足。 | Partial | 这些分支真实存在，但一次补齐所有排列会重复底层 validator 测试并扩大本 Sprint。 | 补优先矩阵：缺文件、non-hex、test split、单类/零权重、重复 identity、rows/canonical hash、发布前 fingerprint 变化；保留已覆盖的 schema/compressed hash/scoring。 |
| 21 | Info | Clarity | `GLM F11` | `_verify_preclaim_sources` 名称与实际 post-claim 时序不符。 | Accept | 调用发生在 claim 与输出写入之后、manifest 之前。 | 重命名为 `_verify_sources_before_manifest` 并保持逻辑不变。 |
| 22 | Info | Maintainability | `GLM F12` | 私有 helper 跨模块导入且存在重复 JSON/receipt helper。 | Reject | 抽取共享 provenance 模块会同时重构 M1-03 与 M1-04，超出最小等价迁移；现有 helper 无循环依赖且测试覆盖。 | 留待 M1-05 删除/收口阶段统一整理，不在本 Sprint 扩张架构。 |
| 23 | Info | Auditability | `GLM F13` | Software manifest 未记录 matplotlib。 | Accept | Test run 产生三张 PNG，matplotlib 版本影响可复现性。 | 将 matplotlib 加入 `_software_versions` 并由 development/test manifest 共用。 |
| 24 | Info | Correctness | `GLM F14` | 生产路径使用可被 `-O` 移除的 assert。 | Accept | 三处 assert 承担类型不变量；显式 fail-closed 更合适。 | 改为显式类型检查/RuntimeError，不依赖 assert。 |

## Needs Immediate Action

- 收紧 code hash、final parameters/model rounds、receipt rows/columns 和 runs-root/layout 绑定。
- 增加 legacy golden、CLI 二次调用、跨进程 claim 与优先负例矩阵。
- 应用 hex、state revalidation、argparse no-abbrev、matplotlib software identity 和显式类型检查。

## Can Be Deferred

- 不抽取新的共享 provenance/helper 模块；在 M1-05 删除旧执行面时统一收口。
- 不新增 test 二次读取、fsync 协议、test KS/reproduction gate 或未批准 manifest schema。
- 不优化 claim 前完整资格复核的运行成本。

## Final Status

代码为“修正后接受”。应用以上 Accept/Partial 行动、重新通过专项/refactor/完整验证后，
可以完成 M1-04；当前没有需要修改 FR、批准设计或 protocol V1 的阻塞性问题。
