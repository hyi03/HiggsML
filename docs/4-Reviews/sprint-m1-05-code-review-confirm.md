# Sprint M1-05 Code Review Confirm

**Reviewed Inputs**

- `docs/4-Reviews/sprint-m1-05-code-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-05-code-review-by-opencode-go-glm-5.2.md`
- `docs/4-Reviews/sprint-m1-05-review-confirm.md`
- `neural/docs/test-opening-protocol-v1.md`
- `neural/docs/sprint-m1-05.md`
- M1-05 working-tree implementation and tests

**Review Date**

- 2026-09-02

## Overall Conclusion

两份评审总体有效，但 Kimi 的 High finding 基于已过时的控制流：当前 `_evaluate()` 已在 `weighted_auc()` 之前校验 score shape、finite 与 `[0,1]`，无效模型输出会进入 `model_scoring` exit 70。GLM 找到的 claim 所有权竞态、pre-claim transaction exit、post-publish terminal receipt、fd 清理与 README 回归成立。

确认时识别的阻塞动作现已全部应用；其余 Reject 项未扩大 M1-05 边界。修订后的专项、完整 suite、fixture-only CLI smoke、CLI help、pip check 与 diff check 均已通过。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---|---|---|---|---|---|---|---|
| 1 | High | Correctness | Kimi High 1 | 无效 model score 会先被 `weighted_auc` 映射为 exit 3 | Reject | `test_opening.py::_evaluate` 在构造 frame 和调用 `weighted_auc` 前已 exact 检查 shape、finite、`[0,1]` 并抛 `RuntimeError`；外层将其包装为 `model_scoring` exit 70 | 不改实现；按第 4 项补真实无效 score 回归测试，防止该顺序以后退化。 |
| 2 | Medium | Correctness | Kimi Medium 1 | 现存非法 `state/` 目录应按永久 refusal exit 5 | Reject | 协议 §2/§3 的“任何现存 state”明确指 `state/test_opening.json`；symlink/reparse/non-directory 的 `state/` 属于 pre-claim 路径绑定失败，协议要求逐 component 拒绝，并未把它定义成已经消费 opening slot | 保持 pre-claim fail-closed，不把尚未存在 claim 文件的非法目录伪记为已消费的一次 opening。 |
| 3 | Medium | Clarity | Kimi Medium 2 | empty-background 时不应同时记录 sentinel 与 `ks_above_maximum` | Reject | 协议 §6 同时规定 KS 固定为 `1.0`、保存冻结 predicate rejection reasons，并增加 empty sentinel；因此 KS predicate 和原因 sentinel 是两个稳定事实 | 保持两个 reason；GLM 的独立评审也明确要求端到端测试同时断言二者。 |
| 4 | Medium | Test | Kimi Medium 3 | 缺少真实 classifier 无效 score 到 `model_scoring` exit 70 的测试 | Accept | 现有测试只直接注入 `RuntimeError`，没有从 classifier output 走过 `_evaluate` 的 score guard | 新增 NaN/越界或 shape 错误 classifier output 测试，断言 stage、exit、sanitized failure/state 和 `test_features_opened=true`。 |
| 5 | Medium | Test | Kimi Medium 4 | 缺少完整 empty-selected-background opening 测试 | Accept | 当前只在 metric helper 层验证 efficiency/KS，未覆盖 reason、terminal status、receipt 和 plots publication | 新增完全 synthetic、受控冻结评分的端到端 opening 测试，断言 nonreproduction、exit 0、`0.0`、`1.0`、sentinel、KS reason 和完整发布。 |
| 6 | Low | Security | Kimi Low 1 | credential regex 应增加 word boundary 以免过度拒绝 | Reject | 协议 §1 冻结的 denylist 是 credential 名后接 `:`/`=`，未要求 token boundary；`my_password=...` 仍具有 credential assignment 风险，审计引用应采用公开工单 ID | 保持保守拒绝，避免用宽松边界降低已批准 hygiene。 |
| 7 | Low | Correctness | Kimi Low 2 | pandas 字符串排序与 UTF-8 bytes 排序不一致 | Reject | test reader 将 `source_sample` exact 限定为 ASCII 枚举 `higgs_345060`/`zz_363490`，两种排序在允许域内完全等价；发布结果另有 bytes-key 断言 | 不为协议不允许的 Unicode sample 扩大实现。 |
| 8 | Low | Robustness | Kimi Low 3 | `except RunPathError` 不可达 | Reject | `RunTransaction.__exit__` 的 `_publish()` 在 `_write_success_artifacts()` 返回后执行；其 `RunPathError` 不会被内部 artifact-write handler 捕获，外层分支用于该路径 | 保留分支并由既有 publish-failure 测试覆盖。 |
| 9 | Low | Schema | Kimi Low 4 | `_development_manifest` 的 schema 检查不够深 | Reject | `_development_manifest` 先检查 exact key/type，随后 `_validate_protocol_manifest_binding` 将 columns 与 dtype key sets exact 绑定至 hash-bound protocol；职责已分层且 fail closed | 不复制第二层 exact 绑定逻辑。 |
| 10 | Info | Durability | Kimi Info 1 | Windows/POSIX directory durable flush 正确 | Accept | 实现使用 Windows directory handle `FlushFileBuffers` 与 POSIX directory fsync，现有 durability tests 已覆盖调用顺序 | 保持实现；最终验证中重跑相关测试。 |
| 11 | Info | Scientific safety | Kimi Info 2 | forbidden training/selection spy 覆盖良好 | Accept | 现有测试阻止 trainer、optimizer、scaler fit、threshold/candidate selection 进入 opening | 保持 spy；新增测试也不得绕过产品代码中的 no-feedback 边界。 |
| 12 | Info | Verification | Kimi Info 3 | reviewer 的 full suite/pip/diff 检查通过 | Accept | reviewer 记录 214 passed, 2 skipped、pip clean、diff clean，但后续仍会修改代码 | 只作为中间证据；修订后由主流程重新运行全部最终门。 |
| 13 | Medium | Concurrency | GLM Finding 1 | pre-`O_EXCL` 失败可能把并发 winner 的 claim 当作自己的并覆盖 receipt | Accept | `_claim` 失败后仅用 `lexists` 推断 ownership；mkdir/parent flush/open 失败与并发 winner 创建 state 交错时，该推断不成立 | 引入显式 claim-created ownership 信号；只有本进程已成功 `O_EXCL` 才发布 `claim_durability` failure 并 terminalize，新增确定性交错回归测试。 |
| 14 | Medium | Test | GLM Finding 2 | sentinel/nonreproduction 及 plots 没有端到端覆盖 | Accept | 与第 5 项同一缺口，但补充了 plots 的空选择风险及明确的双 reason 期望 | 与第 5 项共享端到端测试；另增加受控 `test_reproduced` 路径或等价的确定性 terminal-outcome 覆盖。 |
| 15 | Low | Correctness | GLM Finding 3 | claim 前 filesystem/durability 错误被映射为 exit 3/70 | Accept | 协议 §8 将 claim/run-path transaction failure 固定为 exit 4；当前 mkdir/parent flush/open 非 `FileExistsError` 路径不一致 | pre-`O_EXCL` filesystem/durability 失败统一为 `RunPathError` exit 4、abort staging、无 receipt；并发 winner 则 stable refusal，绝不触碰 winner state。 |
| 16 | Low | Crash consistency | GLM Finding 4 | publish 后 manifest hash 失败不进入 terminal receipt 路径 | Accept | `sha256_file` 当前位于 publish 后、terminal replace 前且无 wrapper；捕获失败会留下 claimed state 并错误返回 70 | 把 hash/read 归入 `terminal_receipt` exit 4；尽力写 `failed_after_claim`，保留已发布 output 并提示 manual audit。 |
| 17 | Low | Test | GLM Finding 5 | drift/state/read-unread/score-equivalence 测试覆盖仍不完整 | Partial | existing-state 测试对任意 bytes 已证明 payload 不解析，terminal JSON 再枚举无新增控制流；manual score equivalence 也不是协议要求的独立算法。scaler/preprocess lineage drift 与 `test_features_opened=true` 则是明确 §9 证据缺口 | 增加 scaler 或 selection drift、preprocess table/lineage drift、evaluate failure `test_features_opened=true` 断言；不重复枚举语义相同的 terminal payload，不引入第二套评分算法。 |
| 18 | Low | Documentation | GLM Finding 6 | README 的 `open-test` 示例缺 required authorization flag | Accept | CLI parser、design 与 protocol 均要求三参数，README 示例只有两个 | 更新 `neural/README.md`，补 flag 及“仅审计引用、不能证明授权”的说明。 |
| 19 | Low | Robustness | GLM Finding 7 | `os.fdopen` 构造失败会泄漏 claim/temp descriptor | Accept | raw fd 在 `os.fdopen` 接管前没有失败清理，且 `_claim` 有 no-op re-raise block | 在 `_claim`/`_replace_state` 中保证 fd 未被接管时关闭，删除 no-op handler，并加 focused failure-injection test。 |
| 20 | Info | Portability | GLM Finding 8 | POSIX rename 到并发创建的空目录存在 stdlib TOCTOU | Reject | reviewer 自身判定 acceptable；claim 已串行化同一 development opening，Python stdlib 无 portable no-replace directory rename，扩大 native helper 超出本 Sprint | 在 confirm 中保留残余风险，不修改 transaction publication primitive。 |
| 21 | Info | Consistency | GLM Finding 9 | development config 使用 `safe_load` 而非 duplicate-key loader | Reject | config bytes 已由 manifest hash 绑定，semantic key set、protocol、selection、artifact 相互绑定均 exact；重复但被覆盖的键不能改变已接受语义，统一私有 loader 不构成当前验收缺口 | 不为 consistency-only 项引入跨配置模块依赖。 |
| 22 | Info | Consistency | GLM Finding 10 | `validate_test_frame` 接受非 exact int/float dtype | Accept | 协议 §4 明确要求 dtype exact；decoder 当前产生 int64/object/float64，但 public validator 自身应保持同一契约 | 将 validator 改为 exact dtype 检查并补窄 dtype 拒绝测试。 |
| 23 | Info | Clarity | GLM Finding 11 | open-test input-binding 日志仍使用 develop 文案且缺 stage/run | Accept | 协议 §8 要求 opening 日志只含 stage、terminal status 和 run path；共享 handler 当前输出 `development input binding failed` | open-test 分支记录 sanitized `stage=input_binding run_dir=...`；develop 文案保持不变，并补 CLI log assertion。 |
| 24 | Info | Reproducibility | GLM Finding 12 | 只记录 deterministic flag，未在 standalone opening 强制启用，也未记录 threads | Partial | protocol 要求 deterministic environment；standalone CLI 不保证继承 development 的全局 torch 设置。当前 CPU forward 实践上稳定，但 manifest 应反映受控状态 | 在评分前启用 deterministic algorithms，并记录 thread count；不在 M1-05 重新设计或强制改变线程数。 |
| 25 | Info | Path resolution | GLM Finding 13 | `runs` prefix 使用 case-insensitive 匹配导致平台差异 | Reject | 该判断服务 Windows recorded path；在 case-sensitive 平台不同大小写最终会 fail closed，不会越界或读取错误路径 | 保持当前兼容与最终 containment guard。 |
| 26 | Info | Test safety | GLM Finding 14 | blank-authorization subprocess 依赖 auth-first 顺序且 cwd 指向 repo `neural/runs` | Accept | auth-first 是已批准 invariant，但测试没有必要让 real workspace root 进入其可见范围 | 将 subprocess cwd 改为 `tmp_path`，保持 authorization-first assertion，避免测试接触工作区 runs。 |

## Needs Immediate Action

- 修复 claim ownership 竞态，并统一 claim 前/后 transaction 与 durability 语义。
- 将 post-publish manifest hash 纳入 terminal receipt exit 4 路径。
- 修复 raw fd ownership，补 README required flag。
- 补无效 score、empty-background/nonreproduction、受控 reproduced、lineage/scaler drift、receipt flag、exact dtype、CLI logging 与 tmp cwd 测试。
- standalone opening 启用 deterministic algorithms，并在 manifest 记录 threads。

## Can Be Deferred

- POSIX stdlib rename 的残余 TOCTOU、case-insensitive `runs` routing 与 duplicate-loader consistency 不阻塞 M1-05。
- 不为固定 ASCII sample 实现额外 Unicode bytes-sort 层。
- 不重复枚举 existing-state JSON terminal payload，也不增加独立评分算法。

## Final Status

**Accepted.** 所有 Accept/Partial 动作均已应用；修订后 focused opening 为 `50 passed`，扩大相关回归为 `80 passed, 1 skipped`，完整 suite 为 `227 passed, 2 skipped`，pip check、两个 CLI help、fixture-only CLI smoke 与 `git diff --check` 均通过。两个 skip 分别是缺少外部 r3-ARM64 authority table 和 Windows directory-symlink 能力。

未运行权威 `open-test`，未读取真实数据；successful smoke 只使用 ignored synthetic fixture 与 `synthetic-fixture-only` 审计引用。Windows/synthetic 结果非权威，不能替代 locked native `osx-arm64` gate。
