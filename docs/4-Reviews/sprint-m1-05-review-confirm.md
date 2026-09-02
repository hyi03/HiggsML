# Sprint M1-05 Document Re-review Confirm

**Reviewed Inputs**

- `docs/4-Reviews/sprint-m1-05-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-05-review-by-opencode-go-glm-5.2.md`
- `neural/docs/sprint-m1-05.md`
- `neural/docs/test-opening-protocol-v1.md`
- `neural_adversarial_mlp_refactor_design.md`
- `neural/docs/FR-001-adversarial-mlp-refactor.md`
- root and `neural/AGENTS.md`

**Review Date**

- 2026-09-02

## Overall Conclusion

两份复审均确认先前 30 项文档动作已纳入，新增的空选中背景 `KS=1.0`、authorization hygiene
与 terminal-receipt failure 方向正确。GLM 指出的三个 Medium 是真实的规范冲突/缺口，必须在
代码评审前修订；Low 项中除已由当前设计满足的陈旧判断外，其余以最小方式纳入。

本确认不授权任何权威 `open-test`。后续仅可继续使用 synthetic fixtures 验证机制；不得读取真实
数据或权威 held-out test。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---:|---|---|---|---|---|---|---|
| 1 | Info | Security | `Kimi Info-1` | 授权诚实与 MC-only 边界正确 | Accept | 协议 §1 与 FR/AGENTS 一致 | 保持 audit-only wording、无权威 opening 授权和 educational/technical-demo 边界。 |
| 2 | Info | Correctness | `Kimi Info-2` | Pre-claim、O_EXCL 与永久拒绝语义正确 | Accept | 协议 §2–§3 明确 claim 前校验和不可重试 | 保持，并按 GLM F02/F03 补完整 durability 层级与 exit。 |
| 3 | Info | Correctness | `Kimi Info-3` | Test-only reader 与冻结评价正确 | Accept | 协议 §4–§6 禁止训练和重选阈值 | 保持 split-first、15-feature whitelist 与 spies/poison tests。 |
| 4 | Info | Risk | `Kimi Info-4` | 空选中背景 `KS=1.0` 正确，建议显式 sentinel | Accept | 仅 generic `*_ks_above_maximum` 不足以区分 sentinel | 在 frozen point 及 rejection reasons 中增加 `empty_selected_background` 审计标识，并补测试/协议。 |
| 5 | Info | Risk | `Kimi Info-5` | Terminal receipt durability 失败语义正确 | Accept | 已发布 run 与 indeterminate claim 不可回滚或重试 | 保持 exit 4，补 stage、稳定 CLI 提示和注入测试。 |
| 6 | Info | Consistency | `Kimi Info-6` | 退出码总体与 AGENTS 一致 | Accept | 0/2/3/4/5/70 大类一致 | 保持，并采用 GLM F01/F03 的精确分类。 |
| 7 | Info | Requirement | `Kimi Info-7` | Sprint 范围与禁止反馈/override 正确 | Accept | Sprint §3/§4/§9 与 FR-001 一致 | 保持。 |
| 8 | Low | Consistency | `Kimi Low-1` | Root design test layout 缺 `config.yaml` | Reject | 当前 `neural_adversarial_mlp_refactor_design.md` §10.2 已在 line 413 列出 `config.yaml` | 不重复修改；该评论基于过期读取。 |
| 9 | Low | Clarity | `Kimi Low-2` | 当前工作目录 `runs/` 与 `neural/runs/` 表述易歧义 | Accept | `neural/AGENTS.md` 要求从 `neural/` 运行 | 在协议中明确 cwd 必须为 `neural/`，因此 allowed root 即 `neural/runs/`。 |
| 10 | Low | Clarity | `Kimi Low-3` | preprocess relative path 解析中的 root parent 不够清晰 | Accept | 当前规则正确但术语可误读 | 增加 `runs/foo` 与 `foo` 两个解析示例。 |
| 11 | Low | Security | `Kimi Low-4` | 协议缺 authorization secret 警示 | Partial | 当前 §1 已有不得包含 credential 的警示，但精确字符/模式尚未固定 | 不重复警示；按 GLM F06 固定 stripped 字符数、Unicode control 类与 credential assignment 模式。 |
| 12 | Low | Audit | `Kimi Low-5` | Terminal-receipt exit 4 缺少稳定 partial-publish CLI 表达 | Accept | 泛化错误日志无法明确要求人工审计 | CLI 记录 stage、run path 和 manual-audit-required，不输出 test 值。 |
| 13 | Low | Schema | `Kimi Low-6` | 成功 terminal receipt 字段未完整枚举 | Accept | 当前 prose 只列追加字段 | 列出完整成功/失败 receipt 字段；terminal receipt 保留 claim 时间、run、staging、authorization 与 development hash。 |
| 14 | Low | Documentation | `Kimi Low-7` | Sprint checklist 与结论仍待回填 | Accept | 当前仍处实现阶段，尚不应提前勾选 | 在代码评审修订与最终验证通过后统一回填，不提前宣称完成。 |
| 15 | Medium | Correctness | `GLM F01` | §6 catch-all 会把 NaN/发布损坏误归为 exit-0 非复现 | Accept | 与 §8 fixed exits 冲突；model 输出非有限属于 scoring malfunction | 将 `test_nonreproduction` 限定为完整有效评价上的冻结 scientific predicate 失败；test-frame binding=3，非有限/越界 model score=`model_scoring` 70，output publication=4。 |
| 16 | Medium | Risk | `GLM F02` | 新建 `state/` 时未规范 parent directory durable flush | Accept | `state/` entry 位于 development-run directory | 明确新建 state 目录后先 durable flush development-run parent，再写/fsync claim 并 flush `state/`。 |
| 17 | Medium | Consistency | `GLM F03` | `claim_durability` 与 `terminal_receipt` 两类 exit 4 未列入 §8 | Accept | 两类均是事务/耐久失败且已进入实现 | 在 §3/§8 固定两个 stage、exit 4、无 decode/indeterminate 语义。 |
| 18 | Low | Test | `GLM F04` | 新规则测试门不完整并缺 hard-crash proof | Partial | over-length 与 terminal replace 测试确实缺失；persisted `claimed` 可用 deterministic claim-only fixture 精确模拟 crash boundary | 补 over-length、terminal receipt failure、empty-selected 和 claim-only permanent-refusal tests；不引入易抖动的 OS process-kill test。 |
| 19 | Low | Correctness | `GLM F05` | Total class weights 为零时分母语义未定义 | Accept | AUC/efficiency 在 total background/signal weight 为零时不可定义，区别于仅 selected background 为空 | Test frame 要求每类 `train_weight` 总和与 `abs(physical_weight)` 总和均大于零；否则 post-claim `test_frame_binding` exit 3。 |
| 20 | Low | Security | `GLM F06` | Authorization control 字符、长度基准、denylist 未精确固定 | Accept | 当前 C0+DEL 实现漏 C1/Unicode format/bidi controls | 对 strip 后 Unicode code points 限 256；拒绝 Unicode categories `Cc`/`Cf`；固定 case-insensitive credential assignment keywords 并补测试。 |
| 21 | Low | Performance | `GLM F07` | Existing state 在全量 hash 后才检查，重复调用代价过高 | Accept | 早期只做安全 path binding 与 state existence probe 不会读取 test | 在 artifact hash 前做 cheap state probe；O_EXCL 仍是唯一权威 race guard。 |
| 22 | Low | Clarity | `GLM F08` | Claim 字段列表漏 `output_staging` | Accept | 后文与实现均要求该字段 | 将 resolved output staging path 加入 claim schema 列表。 |
| 23 | Info | Requirement | `GLM F09` | 先前 30 项修订完整 | Accept | Reviewer 提供逐项交叉核对 | 保持，不重开已确认决策。 |
| 24 | Info | Correctness | `GLM F10` | 空选中背景规则 doc/code/test 一致 | Accept | frozen metric 已保守返回 KS 1.0 | 保持，并按第 4 项增加显式 sentinel。 |
| 25 | Info | Documentation | `GLM F11` | 代码已在工作树，文档应先同步再进 code review | Accept | Sprint workflow 要求实现以确认文档为基线 | 先应用本 confirm 的文档动作，再继续实现/代码评审。 |
| 26 | Info | Consistency | `GLM F12` | 其余 schema/path/exit/boundary 交叉核对一致 | Accept | Reviewer 已逐项核对当前实现 | 保持；代码评审仍独立检查实现正确性。 |
| 27 | Info | Requirement | `GLM F13` | 本轮未访问真实数据或 held-out test | Accept | 评审仅读文档/源码/测试定义 | 将该边界写入最终 Sprint 证据。 |

## Needs Immediate Action

- 修订 protocol 的 nonreproduction/exit、两级 directory durability、receipt schema、allowed-root/path 示例。
- 固定 authorization Unicode hygiene 和 total-weight binding。
- 增加 empty-selected sentinel、early state probe 与缺失的 durability/authorization/crash-boundary tests。
- 完成上述动作后才能进入 M1-05 code review。

## Can Be Deferred

- 不做真实 OS process-kill 测试；claim-only persisted fixture 已覆盖崩溃后可观察状态和永久拒绝。
- 权威 `open-test` 仍需针对具体 frozen development run 的另行明确授权，本 Sprint 不执行。

## Final Status

**Accepted.** 上述 Accept/Partial 动作已在代码评审前应用；文档门重新闭合。本确认仍不构成
任何权威 held-out test-opening 授权。
