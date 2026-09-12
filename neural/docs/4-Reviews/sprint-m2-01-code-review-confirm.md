# Sprint M2-01 Code Review Confirm

**Reviewed Inputs**

- `sprint-m2-01-code-review-by-gpt-5.5.md`
- `sprint-m2-01-code-review-by-gpt-5.6-sol.md`
- `../1-Requirement/Done/FR-SE-02-deterministic-training-subsets.md`
- `../3-Plan/Done/sprint-m2-01.md`
- `../../src/research/training_subsets.py`
- `../../src/research/sample_efficiency_protocol.py`
- `../../tests/research/test_training_subsets.py`
- `../../AGENTS.md`

**Review Date**

- 2026-09-12

## Overall Conclusion

两份评审均指出了会阻断 FR-SE-02 验收的真实缺口。当前实现的确定性排序、分层前缀、full 去重及非 train payload 隔离方向正确，但在总计摘要、输入重新验证、严格 identity 约束和 canonical membership 读取方面尚不能按原样接受。

以下接受项完成、focused 与全量验证通过后，M2 才可进入提交门。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---:|---|---|---|---|---|---|---|
| 1 | High | Correctness | GPT-5.5 #1 / GPT-5.6-sol F-01 | 每个 subset 只有逐 label 摘要，缺少总计摘要。 | Accept | FR-SE-02 §需求6明确要求“逐类与总计”；当前 `subset_entries` 只发布 `summary_by_label`。 | 在 `training_subsets.py` 增加按全部选中事件组重算的 `summary_total`，同步 artifact schema，并以精确统计断言覆盖 signed/absolute/sumw2/neff、行数、组数和 m4l 范围。 |
| 2 | High | Correctness | GPT-5.5 #2 / GPT-5.6-sol F-02 | prepared identity 的 split 校验过宽，且未拒绝重复 `event_id`。 | Accept | `data._research_split()` 由 base protocol 的 `source_population` 唯一决定 split；现实现允许两种 split，且只维护 `source_row_id` 集合。 | 按 base protocol 精确计算唯一允许 split，同时分别拒绝重复 `event_id` 与 `source_row_id`；增加 receipt 自洽的错误 split 和重复 ID 负例。 |
| 3 | High | Security | GPT-5.6-sol F-03 | 可伪造 `LoadedRun` 绕过 manifest 校验，freeze 解析也未拒绝重复 JSON key。 | Accept | `LoadedRun` 是可构造值；当前 public API 对已有实例不重新执行 `read_run()`，并直接用通用 `read_json()` 构造 freeze。FR-SE-02 §需求1、8要求已验证 run、receipt 与 M1 freeze 重建。 | 所有 public API 入口均从传入 run 的 `.path` 重新执行带精确 stage 的 `read_run()`；freeze 使用 M1 `load_compact_candidate_freeze()`；增加伪造 LoadedRun、错误 stage 和重复 key freeze 测试。 |
| 4 | Medium | Correctness | GPT-5.6-sol F-04 | 整数 `1` 与浮点 `1.0` 可能生成不同 full alias/ID bytes。 | Accept | canonical JSON 区分 `1` 与 `1.0`，而 FR-SE-02 §需求5把 full alias preimage 固定为 `1.0`。 | M1 `_fractions` 明确只接受 float，并在 M2 full 分支规范化为 `1.0`；增加整数 endpoint 拒绝和 full alias 稳定性测试。 |
| 5 | Medium | Consistency | GPT-5.5 #3 / GPT-5.6-sol F-05 | membership reader 只比较解析对象，未验证 canonical JSONL bytes 或重复键。 | Accept | publisher 写 canonical 行，但 reader 使用普通 `json.loads()`；等值对象无法证明输入字节满足 FR-SE-02 §需求5。 | 保留原始行，用拒绝重复键/非有限常量的 loader 解析，并逐行比较 canonical 重编码；增加 receipt 自洽但非 canonical 的 membership run 负例。 |
| 6 | Medium | Test | GPT-5.6-sol F-06 | 缺少真正的行序、重签 receipt 后语义篡改、overlay/upstream 与冲突分支测试。 | Partial | 行序稳定性已由实现中的 canonical identity/line 排序修正，但当前测试未证明；现有 tamper 用例确实只在 receipt 层失败。FR 要求覆盖行序、冲突和摘要篡改。评审建议的每类 artifact 全排列超出证明当前分支的最小集合。 | 增加 `_read_train_rows` 行序对照、payload identity override、group label 冲突、role hash、错误 split、重复 event ID、非 canonical membership，以及 receipt 自洽的 plan/ledger 语义篡改。upstream 和 overlay snapshot 各保留一个绑定负例即可。 |
| 7 | Low | Test | GPT-5.5 #4 | 测试名称声称 identity conflict，实际只注入 NaN。 | Accept | 当前 `test_train_payload_nonfinite_and_identity_conflict_are_binding_failures` 仅修改 `physical_weight`。 | 拆分非有限值和 identity/group/role 冲突测试，确保每个名称与实际触发分支一致。 |

## Needs Immediate Action

- 完成 `summary_total`、严格 split/ID、run 重新验证、M1 freeze loader、float endpoint 和 canonical membership 修复。
- 用 receipt 自洽 fixture 覆盖内容语义校验，而非仅依赖文件摘要失败。
- 更新 artifact schema 和 Sprint 验证记录。

## Can Be Deferred

- 无。表中 Partial 项已缩减为 M2 验收所需的最小测试矩阵，仍须本 Sprint 完成。

## Final Status

接受。六项确认动作均已落实；扩展 focused 测试为 113 passed，`pip check` 通过，全量测试为 661 passed、60 warnings。该证据范围限于 Windows synthetic 软件验证。
