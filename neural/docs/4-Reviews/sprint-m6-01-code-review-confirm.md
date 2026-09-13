# Sprint M6-01 Code Review Confirm

**Reviewed Inputs**

- `docs/3-Plan/sprint-m6-01.md`
- `docs/1-Requirement/FR-SE-06-controls-and-confirmation.md`
- `docs/4-Reviews/sprint-m6-01-code-review-by-gpt-5.6-sol.md`
- `docs/4-Reviews/sprint-m6-01-code-review-by-gpt-5.5.md`
- `docs/4-Reviews/sprint-m6-01-review-confirm.md`
- `docs/sw-dev/artifact-schema.md` §12
- 当前 M6 working-tree diff 与 M1–M5 public readers

**Review Date**

- 2026-09-13

## Overall Conclusion

两份评审对指出了相同的核心阻：当前实现通过了 focused 和全回归，但 enabled controls 与 confirmation reader 还没有达到 FR 已确认的可重放信任边界，不能按现状接受。disabled 零 decode、capacity stage DAG、CDF replay、排除集覆盖、typed evaluation receipts、preclaim 字节语法和 path exit code 都应在 M6 内修复。

M7 仍负责正式 controlled-MC producer、独立受信 package、ARM64 authority 与 scientific numerical evidence；M6 不应伪造这些外部证据。因此 evaluation receipt 的精确角色/摘要校验现在实现，正式 artifact producer 与科学 pointer 重放保持 `external_pending`。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---:|---|---|---|---|---|---|---|
| 1 | High | Requirement | `gpt-5.6-sol C1` | both-disabled controls 仍先重放 M4/M5 并解码 prepared。 | Accept | FR 与 artifact-schema §12 明确 disabled 零 payload decode/零训练；`_build_controls` 当前无条件调用两个 public reader。 | 在 enable flags 前分支；both-disabled 只验证 run manifest、协议、stage 与 M5→M4 upstream，不进入 M4/M5 semantic replay，并增加 decode/trainer sentinel 测试。 |
| 2 | High | Correctness | `gpt-5.6-sol C2` | capacity calibration/template/inference 仅存在内存，无独立 stage artifact 和 W68 pointer。 | Accept | FR 的 capacity DAG、direct upstream 与 ledger 契约是 document-review-confirmed；当前只发布 model run。 | 增加 capacity calibration/template/inference envelope runs、精确 upstream、relative paths、grid ID、stage artifact IDs 和固定 W68 JSON pointer。 |
| 3 | High | Correctness | `gpt-5.6-sol C3` | controls reader 不重放 enabled capacity/CDF。 | Accept | reader 仅检查顶层自摘要和 upstream prefix，自洽重签可改变科学字段；两位 reviewer 独立确认同一缺口。 | reader 重建注册计划、严格核对完整 upstream，逐 cell 调专用 model reader并重算 calibration/template/inference/CDF mapping、threshold与指标；增加重签篡改测试。 |
| 4 | High | Correctness | `gpt-5.6-sol C4` | exclusion identity sets 未证明覆盖 freeze 和 M4/M5 lineage populations。 | Accept | FR 要求 receipt-bound exclusion sets 覆盖 discovery/browsed/excluded 及 M4/M5 lineage；当前允许任意 unrelated set。 | exact 要求 population ID 覆盖 `freeze.excluded_population_ids ∪ {overlay.population_id}`，拒绝缺失、重复和额外集合；identity-set ID/SHA 进入 claim key，并在 claim 前完成 overlap。正式 authoritative producer 留 M7。 |
| 5 | High | Correctness | `gpt-5.6-sol C5` | evaluation receipts 只是任意自报列表，缺两侧与各 stage 角色。 | Partial | 问题真实；但 document review 已明确正式 controlled-MC producer/public numerical replay 留 M7，M6 受信 package 尚不可得时必须 external pending。 | M6 现在冻结 exact typed receipt 角色、两侧 representation、population、artifact/stage/SHA/pointer 与并；synthetic fixture按具名角色校验。controlled-MC 仍只发布 `external_pending`，正式 artifact 打开与数值重放留 M7。 |
| 6 | High | Security | `gpt-5.6-sol C6` | confirmation reader 不认证完整 claim、freeze/overlay/M4/M5/CI 语义。 | Accept | `read_confirmation(base=...)` 无法重建 claim key或校验 upstream/scope；确可通过重签改变未检查。 | 扩展 reader 输入为 overlay/freeze/freeze artifact/allowed root/upstreams/exclusion receipts，严格 exact keys/location/key preimage/preclaim/result/CI/status matrix，并禁止 M6 reader接受 scientific confirmed 状态。 |
| 7 | High | Correctness | `gpt-5.6-sol C7` | 可在 claim 前识别的 delimiter/payload 行数错误却在 claim 后才拒绝。 | Accept | scanner 已读完整文件但只记录首个 delimiter；唯一 delimiter 与恰好一行 payload 属纯字节语法，不要求解释 payload。 | preclaim scanner统计 delimiter和post-delimiter行数，要求1/1；继续 poison 仍不解码，结构错误不创建 claim。 |
| 8 | Medium | Correctness | `gpt-5.6-sol C8` | 任意不完整 raw M4 cell 都被错误归因 CDF calibration uncertainty。 | Accept | FR 静态映射只覆盖四个 physical calibration/support 终终态。 | upstream raw 不可用改为 `raw_cell_unavailable`并保留原 status/reason；仅冻结四状态映射为 `calibration_uncertainty_dominant`。 |
| 9 | Medium | Consistency | `gpt-5.6-sol C9` | controls output 路径冲突返回3而非4。 | Accept | neural/AGENTS.md 与和 FR 固定 run-path/transaction failure=4；当前 `_fail` 为3。 | containment/existing/creation交给 `RunPathError`或 RunTransaction，CLI增加现有目标与非法name测试。 |
| 10 | High | Test | `gpt-5.6-sol C10` | M6 九项测试没有覆盖大部分负例矩阵。 | Partial | 覆盖确实不足；部分 reviewer 建议的正式 controlled-MC producer/authority fault injection 属 M7，但 M6 reader、claim、grammar、disabled与tamper边界必须覆盖。 | 增加 both-disabled sentinel、partial/full坐标、capacity schema隔离、enabled replay/tamper、identity grammar/coverage、typed receipt、claim repeat/key drift、controlled external-pending及 reader重签测试；M7 外部 producer/ARM64故障注入不在本 Sprint伪造。 |
| 11 | High | Correctness | `gpt-5.5 C1` | enabled controls reader 未重放。 | Accept | 与第3项同结论但证据独立，明确指出 trailing capacity upstream未核对。 | 与第3项共同修复；确认文档保留独立来源，实施使用同一 replay builder避免。 |
| 12 | Medium | Risk | `gpt-5.5 C2` | controlled-MC external_pending仍携带未任意自报CI数字。 | Partial | M6 必须计算冻结规则以验证状态机，但不能将未受信数字解释成科学结论；`external_pending`是已确认的边界。 | exact typed receipts与reader绑定；结果保留 rule计算但 validation scope/status 强制 external pending，文档明确 estimate非scientific evidence；M7受信producer后方可升级状态。 |

## Needs Immediate Action

- 修复 disabled controls 零 decode 和路径退出码。
- 发布并重放完整 capacity stage DAG；逐 cell 重放 CDF。
- 强化 exclusion coverage、typed evaluation receipts、preclaim grammar 和 confirmation reader。
- 扩展 M6 trust-boundary/tamper 测试并重跑 focused、回归、pip check 与全量 pytest。

## Can Be Deferred

- 正式 independent controlled-MC evaluation package producer与pointer数值重放。
- native ARM64 authority、完整 ROOT、scientific numerical validation与相关平台故障注入。

## Final Status

**Changes required；当前实现不可接受。** 最小剩余工作为完成以上 Accept/Partial 的 M6 内行动、验证通过并使代码复评确认无阻断项。

## 整改执行记录

- 2026-09-13：Accept 项 1—4、6—9、11 已实现；Partial 项 5、10、12 的 M6 内 typed receipt、信任边界测试与 `external_pending` 状态约束已实现。
- both-disabled 只做 manifest/upstream 验证；enabled capacity 发布并逐段重放 model/calibration/template/inference，注册的 template 统计终态保留前三段并阻断 inference；CDF 重放全部注册 raw cells。
- confirmation 现在要求精确 exclusion population 覆盖、固定 typed receipt 角色、唯一 delimiter/单 payload 行，并由 reader 重放输入、exclusion、upstream、claim key preimage/location、preclaim、CI 与 scope/status。
- focused `19 passed, 111 warnings`；M1—M5 回归 `105 passed, 180 warnings`；`pip check` 通过；全量 `705 passed, 338 warnings`。
- 整改后状态：M6 软件实现可接受。正式 controlled-MC producer/public numerical replay、完整 ROOT 和 native ARM64 authority 按本确认文档继续留待 M7，不从 synthetic 结果推断。
