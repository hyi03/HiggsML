# Sprint M1-04 Code Review Confirm

**Reviewed Inputs**

- `docs/4-Reviews/sprint-m1-04-code-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-04-code-review-by-opencode-go-glm-5.2.md`
- M1-04 implementation、tests、Sprint、Development Protocol V1、FR-001、root design 与两级 AGENTS

**Review Date**

- 2026-09-02

## Overall Conclusion

两份评审均确认核心 MC-only、held-out routing、OOF、qualification、final-fit 与 transaction
机制基本正确；GLM 通过 synthetic path probe 证明 `_bound_input_run` 存在可越出 allowed root
的 `..` 穿越，这是合入前必须修复的 High 问题。Development Protocol V1 §2、§9、§10 还明确
要求 preprocess lineage hashes、schema/counts 与若干最低测试证据，这些缺口一并在本 Sprint
关闭。

本确认不采纳未被需求支撑的 API 扩展、命名统一或大范围重构。所有 Accept/Partial 项现已完成
并重新验证，M1-04 可在 staged-diff 检查和独立提交后关闭；提交前仍不得启动 M1-05。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---:|---|---|---|---|---|---|---|
| 1 | High | Test | `Kimi H1` | 真实 trainer→OOF→qualification→final-fit 未被端到端测试 | Accept | Development Protocol V1 §10 明确要求完整调用与 final-fit；现有 integration 全部替换 scientific functions | 增加一个小型 synthetic、非 monkeypatch 的 `execute_development` E2E，核对状态、OOF 顺序、AUC 与 manifest/hash。 |
| 2 | High | Test | `Kimi H2` | reader 的 path/hash/schema 安全分支缺专门测试 | Accept | reader 是 §2 唯一 persistent binder，且 GLM 已动态证明其中存在真实路径缺陷 | 新增 `tests/unit/test_development_reader.py`，参数化覆盖 traversal、link/reparse、manifest/output/hash/canonical/split/count/identity 失败。 |
| 3 | Medium | Requirement | `Kimi M1` | development manifest 缺 `schema` | Accept | Development Protocol V1 §9 明确要求 manifest 记录 schema/counts | 增加 OOF、candidate、fold 的列与 dtype schema，并由 integration test exact 校验。 |
| 4 | Medium | Requirement | `Kimi M2` | manifest 未显式记录 preprocess protocol/run-config SHA | Accept | §2 要求按 payload bytes SHA-256 引用输入 preprocess protocol/config | reader 严格读取真实 preprocess manifest 的两个 64-hex SHA，并写入 development manifest input block。 |
| 5 | Medium | Test | `Kimi M3` | 未测试发布 OOF exact 行序与 canonical hash | Accept | §5 冻结 lambda/identity 行序及 gzip/canonical hashes | 在 integration/E2E 中 exact 校验排序，并从解压 canonical bytes 重算 hash。 |
| 6 | Medium | Test | `Kimi M4` | final epoch 中位数未用非退化值验证 | Accept | §8 指定选五折 best epoch 排序后的第三个整数 | 让 fake folds 返回不同 best epochs，并断言只使用 selected candidate 的中位数。 |
| 7 | Medium | Test | `Kimi M5` | preprocess manifest fail-closed mutation 未覆盖 | Accept | §2/§10 要求 manifest/schema/hash 先于 routing 完整绑定 | 纳入 reader 参数化 mutation tests，逐类改变 status/run_type/protocol/key/schema/config。 |
| 8 | Medium | Maintainability | `Kimi M6` | `train_fixed_epochs` 与 fold tensor 构造重复 | Reject | 当前 full-development scaler/tensor contract 与 fold-local fitting/validation contract不同；评审未证明行为错误，Sprint 也未要求公共 tensor abstraction | 保留当前显式 final-fit 路径，避免在安全修订中扩大 dataset/trainer 重构面；以现有及新增 E2E 锁定一致性。 |
| 9 | Low | Test | `Kimi L1` | poison test 只查 DataFrame 字符串，不能证明 decoder 未被调用 | Accept | §2/§10 明确要求 poison row/parser 证明 test feature decoder never called | 给 numeric decoder 加 spy/monkeypatch 证据，并增加 command-level poison pipeline 测试。 |
| 10 | Low | Documentation | `Kimi L2` | README 状态停留在 M1-02 | Accept | M1-04 完成后该状态会失真 | 最终验收时更新 README 为 M1-04 development-only 能力与非权威边界。 |
| 11 | Low | Test | `Kimi L3` | fold hash 还应增加近 `2**64` 等边界 | Reject | §4 的 payload、first-8-byte big-endian/mod 5 已由 known vectors（含 entry=0）、reorder、type/range/NUL tests 锁定；人为寻找 digest 极值不增加语义覆盖 | 不加入概率性/挖值测试；保留 deterministic known vectors 与输入拒绝测试。 |
| 12 | Low | Test | `Kimi L4` | working-point cumulative equality/all-score-tie 边界不足 | Accept | §6 明确 first `>=` 与 inclusive full tie | 增加 cumulative exact equality 和全背景同分数的手算测试。 |
| 13 | Low | Test | `Kimi L5` | eligible model payload 与 manifest hashes 未校验 | Accept | §8/§9 冻结 model/scaler payload binding 与 eligible-only paths | integration test 加载 synthetic model payload、核对 scaler schema，并验证两条 eligible output hashes。 |
| 14 | Low | Test | `Kimi L6` | qualification missing/extra point fields 未测试 | Accept | `qualification_reasons` 的 exact schema 是 fail-closed 边界 | 增加 missing/extra field mutation。 |
| 15 | Low | Test | `Kimi L7` | 未验证 `assign_folds` 覆盖全部五折 | Reject | `test_assign_folds_is_stable_under_row_reorder_and_covers_all_folds` 已明确断言 `set(...) == set(range(5))` | reviewer 对现有测试的描述不准确；不重复同一断言。 |
| 16 | Info | Requirement | `Kimi I1` | CLI 应暴露 `--input-allowed-root` | Reject | Development Protocol V1 §2 冻结命令只接受 `--input-run`、`--protocol`、`--run-dir`；同一 cwd/runs root 是有意边界 | 不扩展 CLI；测试并文档化 input/output 均须位于 cwd 的 `runs/`。 |
| 17 | Info | Consistency | `Kimi I2` | manifest `environment` 应改名为 `determinism` | Reject | §9 要求内容而未冻结 key 名；当前 environment 包含 deterministic flags，改名会产生无功能 schema churn | 保留 `environment`，在 schema/test 中 exact 固定其内容。 |
| 18 | Info | API | `Kimi I3` | `working_point_metrics` 应接受 numpy float | Reject | 该函数只由 sealed `TrainingProtocol.working_points` 调用并收到 Python `float`；type-strict fail-closed 与项目约定一致 | 不扩大内部 API 输入域。 |
| 19 | Info | Error hygiene | `Kimi I4` | gzip 失败应记录行号/offset | Reject | §9 禁止日志/收据泄露 row/value/test identity；generic binding error 是有意最小披露，且报告未证明诊断不足阻塞验收 | 保持通用消息；测试确保错误不含敏感 row/value/path。 |
| 20 | Info | Performance | `Kimi I5` | OOF identity sort 每次用 `iloc` 造成高开销 | Accept | full-data development 行数较大，现有 key 每行构造 Series；可在不改变语义下局部优化 | 预提取 UTF-8 sample bytes 与 integer entries 后排序，并用 exact order test 防止行为漂移。 |
| 21 | High | Security | `GLM H1` | `_bound_input_run` 可经 `..` 越出 allowed root | Accept | reviewer 用临时 synthetic paths 复现；resolved path 没有再次 `relative_to(root)`，违反 §2 | 拒绝 `..`，resolve 后再次验证 containment，包装 root resolve 错误，并测试绝对/相对 traversal 与 root-equals-input。 |
| 22 | Medium | Requirement | `GLM M1` | preprocess protocol/config payload hashes 未校验/传播 | Accept | 与 Kimi M2 独立一致，且真实 M1-02 manifest 在 `configuration` 中提供两项 SHA | 对 configuration 做 exact required-field/type/hash 校验，并传播两项 hash；synthetic fixture 改为真实 schema。 |
| 23 | Medium | Test | `GLM M2` | reader 十余个 fail-closed 分支与 command poison 未覆盖 | Accept | 与 Kimi H2/L1 结论一致，但额外指出 command-level 证据 | 纳入专门 reader test matrix，并让 poison fixture 经 `execute_development` 走到 training fakes。 |
| 24 | Medium | Test | `GLM M3` | 无 un-mocked E2E，score↔identity placement 未锁定 | Accept | reviewer 的临时 real synthetic E2E 已证明当前机制可运行，但该证据未在 repo test 中持久化 | 新增 repo 内 synthetic E2E，重算每 candidate AUC 并核对发布行序与 identity/fold。 |
| 25 | Medium | Test | `GLM M4` | OOF mutation matrix 缺 extra/range/field/test identity/order | Accept | Development Protocol V1 §5/§10 逐项要求这些拒绝路径 | 扩展参数化 mutation tests，并在发布测试覆盖 exact order。 |
| 26 | Low | Requirement | `GLM L1` | manifest 缺 epoch counts 与显式 OOF completeness | Accept | §9 明确列出 candidate/fold/epoch 数与 OOF 完整性 | 增加 `fold_epoch_rows`、per-candidate OOF row/identity counts 与 unique/complete flags。 |
| 27 | Low | Consistency | `GLM L2` | sealed flags/常数未全部从 protocol 动态读取 | Reject | V1 loader `_EXPECTED` 已 exact 固定这些值；fold function 是 V1 固定算法而非可配置 API，`rtol=0` 时现式选择公式与协议 exact 等价 | 保留 executable constants，依靠 strict loader/mutation tests 防止 drift，避免把冻结 V1 误改成动态协议解释器。 |
| 28 | Low | Performance | `GLM L3` | pandas `iloc` identity sort 成本高 | Accept | 与 Kimi I5 独立一致 | 按第 20 项做局部预提取优化。 |
| 29 | Low | Architecture | `GLM L4` | plot 层重算 ROC 且硬编码 mass edges | Partial | 硬编码 mass edges 会重复 scientific truth；ROC 仅生成诊断 plot，但确属 scientific computation | mass edges 改由 protocol 传入；ROC point 计算移到 qualification helper，plot 层只消费已计算 arrays。 |
| 30 | Low | Test | `GLM L5` | 缺负 signed physical weight 的手算证据 | Accept | §6/§10 明确 absolute-weight efficiency/KS，正权重用例不能证明 `abs()` | 增加负权重与等绝对值正权重结果一致的 threshold/efficiency/KS 测试。 |
| 31 | Low | Test | `GLM L6` | final epoch median 测试全为 1 | Accept | 与 Kimi M4 独立一致 | 按第 6 项使用非退化 fold epochs，并断言 selected candidate median。 |
| 32 | Low | Operability | `GLM L7` | CLI 不记录候选/fold进度和正常终态 | Partial | full-data 运行较长，最终状态必须可见；逐 fold INFO 会产生较多日志但仍合理 | 增加每 candidate 完成及最终 status/selected lambda/run path 的 INFO；不输出 row/value/test identity。 |
| 33 | Info | Reproducibility | `GLM I1` | 直接重训有 last-ulp 漂移，建议 subprocess test | Reject | reviewer 同时证明两次完整 command 的 OOF/candidate 等科学产物字节一致；不同调用结构的 ≤1.1e-16 差异不是当前失败 | 冻结 run 继续以 artifact hashes 验证，不以重训练重建 bytes；不新增昂贵 subprocess 门。 |
| 34 | Info | Reproducibility | `GLM I2` | 可选验证 `model.pt` byte equality | Reject | §8 要求 state/payload 语义与 manifest byte hash，不要求跨 run `torch.save` bytes 相等；现有 tensor state deterministic | 不把 pickle/container bytes 稳定性升级为验收条件。 |
| 35 | Info | Consistency | `GLM I3` | development config snapshot 重序列化 protocol | Reject | §2 的“不复制或改写”对象是输入 preprocess protocol/config；当前 snapshot 是本次 development protocol 的审计副本，原 payload SHA 仍被记录 | 保留可读 snapshot 与原始 SHA binding。 |
| 36 | Info | Robustness | `GLM I4` | allowed root resolve error及非表 output record types未统一 | Partial | root resolve 应稳定映射为 input-binding；所有 output records exact type validation能加强 fail-closed | 包装 root resolve；对每个 output record 校验 hash/size/row_count/canonical 类型和值域，table 再施加专属约束。 |
| 37 | Info | Documentation | `GLM I5` | Sprint 交付结论仍是占位 | Accept | 当前正处 code-review-confirm 阶段，最终关闭前必须按 Sprint §7/§10 回填 | 修订与最终验证后勾选 checklist、记录命令/计数/skip/安全边界与非权威声明。 |

## Needs Immediate Action

- 修复 `_bound_input_run` 的 absolute/relative `..` 穿越，并完成 reader 全面 fail-closed 测试。
- 传播 preprocess protocol/run-config payload SHA，补齐 manifest schema、epoch/OOF completeness。
- 增加真实 synthetic E2E、OOF mutation/order/hash、非退化 median、negative-weight、model payload 证据。
- 将 ROC 计算移出 plot publication 层、由 protocol 提供 mass edges，并补安全日志。

## Can Be Deferred

- 不做 `train_fixed_epochs` tensor abstraction 重构。
- 不增加 `--input-allowed-root`、numpy scalar API、manifest key rename、subprocess/model-container byte gate。
- 不将 locked V1 literals 改造成动态可变协议。

## Final Status

**Accepted after confirmed revisions.** 37 项意见均已逐条决策，Accept/Partial 动作已落实。
确认项专项 `81 passed`，完整 suite `174 passed, 1 skipped`；唯一 skip 为
`authoritative_gate_not_run`。`pip check`、两个 CLI help、真实 synthetic CLI smoke 与
`git diff --check` 均通过。未运行 full-data training/authority gate，未读取真实数据，未打开
held-out test，未执行 `open-test`；Windows/synthetic 证据不替代 locked native `osx-arm64` gate。
