# Sprint M6-01 Review Confirm

**Reviewed Inputs**

- `docs/1-Requirement/FR-SE-06-controls-and-confirmation.md`
- `docs/3-Plan/sprint-m6-01.md`
- `docs/4-Reviews/sprint-m6-01-review-by-gpt-5.6-sol.md`
- `docs/4-Reviews/sprint-m6-01-review-by-gpt-5.5.md`
- `docs/sw-dev/h4l-compact-kinematics-sample-efficiency-development-plan.md`
- `docs/sw-dev/artifact-schema.md` §8–11
- 当前 M1–M5 public reader、lineage、raw calibration/template 与 transaction 边界

**Review Date**

- 2026-09-12

## Overall Conclusion

两份评审的核心判断成立：当前 FR/Sprint 已冻结 M6 的研究方向，但还没有把 capacity/CDF 的可重放 artifact 链、confirmation 输入可信来源、事件集合独立性、claim 状态机和 CLI 终态写成唯一可实现的契约。目标文档不应按现状进入实现。

M6 的当前边界仍是软件实现与 Windows synthetic validation。正式独立 controlled-MC、ARM64 authority 和 scientific numerical validation 继续留在 M7；但 M6 必须防止 synthetic 规则结果被发布成科学确认，并为未来受信 evaluation package 留下严格 reader/receipt 接口。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---:|---|---|---|---|---|---|---|
| 1 | High | Requirement | `gpt-5.6-sol M6-DOC-001` | capacity 的 partial-fraction draw 坐标未冻结，无法唯一确定计划和 pairing。 | Accept | M1 overlay 的 capacity 只登记 fraction/network seed；M2/M4 对 partial fraction 按全部 draw 产生不同 subset，只有 full 折叠为 `full`。FR 第 9–11 行没有说明选一个 draw 或遍历全部 draw。 | 在 FR 容量控制中固定笛卡尔积：partial fraction 使用 overlay 全部 `sample_draw_seeds`，full 只使用 canonical `full`；规定 canonical 顺序、planned/canonical 数量、subset/membership/draw/pairing 重验。Sprint 增加对应计划 golden、full 去重和 disabled 空计划测试。 |
| 2 | High | Correctness | `gpt-5.6-sol M6-DOC-002` | capacity 新宽度模型没有版本化 builder/reader、schema、cell ID 和下游 lineage。 | Accept | 当前 `research-discriminant-v2` reader只接受 `baseline-fixed64x64x32`、固定 `[d,64,64,32,1]` 和现有 ID preimage；总计划 §12 要求 capacity 是具名 variant且普通训练仍拒绝任意宽度。现 FR 只有顶层聚合 artifact。 | 在 FR 和待新增 artifact-schema §12 定义 capacity 专用 model schema/builder/reader、精确层结构、宽度与参数量重算、capacity cell/pairing ID preimage、direct upstream，以及 calibration/template/inference envelope 和顶层 ledger 的 artifact pointer；保持现有 M3 reader 对 capacity model 的拒绝。 |
| 3 | High | Correctness | `gpt-5.6-sol M6-DOC-003` | CDF 两项指标和 `calibration_uncertainty_dominant` 没有唯一公式或失败映射。 | Accept | FR 第 15–17 行未定义 threshold 来源、absolute-weight 分子/分母、质量箱聚合、raw-relative 归一化、零分母和既有 calibration 失败到终态的映射；现有 physical CDF mapping 与 raw template capability 也不同。 | 在 FR 写出两项指标逐步公式和 golden vector，固定 threshold/category 来源、权重、聚合/max 顺序、零分母行为；明确复用 base 支持阈值还是新增协议阈值，并列出 `insufficient_statistics`、`nonpositive_calibration_yield`、`outside_calibration_support` 等到 M6 终态的静态映射。Sprint 增加边界与失败 golden。 |
| 4 | High | Consistency | `gpt-5.6-sol M6-DOC-004` | CDF 没有明确 stage DAG、共同 grid 来源和可重放 provenance。 | Accept | M4 common-grid 是独立、receipt-bound run；当前 `prepare_sample_efficiency_template_frame` 只接受 verified raw calibration bundle。FR 只列 physical mapping ID 和“共同质量网格”，不足以证明 model、prepared roles、raw 对照、physical mapping 与指标属于同一 cell。 | 在 FR/artifact schema 固定 `verified M4 cell → physical calibration → categorized template/check` DAG；直接 upstream 明确包含 prepared、capacity-independent raw model/calibration/template、M4 common-grid run。只复用并核对 M4 `grid_id/final_mass_edges`，不按 physical cells 重合并；reader 从 receipts 重放 mapping、分类和指标。 |
| 5 | High | Risk | `gpt-5.6-sol M6-DOC-005` | 外部 paired W68 differences 没有受信 producer 或逐 replicate 可重放来源。 | Partial | 问题真实：payload 内自报 receipts 和自摘要不能证明差值来自冻结模型、共同 resample plan和独立总体；总计划 §13 要求正式 payload 加 upstream receipts。评审建议若要求 M6 已提供正式 independent scientific evidence，则超出当前 synthetic 软件边界；M7 仍负责 authority/numerical evidence。 | M6 现在定义严格的 evaluation package schema/reader：绑定 population、两侧 model/calibration/template/grid/inference receipts、multiplicity-plan ID、逐 replicate W68 pointer及可重算差值。若该受信 package 尚不可得，controlled-MC 路径必须为 `external_pending`；synthetic 只能发布 `synthetic_rule_satisfied`，不得发布科学 `confirmed_*`。M7 再提供正式独立输入与权威证据。 |
| 6 | High | Correctness | `gpt-5.6-sol M6-DOC-006` | 只比较 population digest 不等无法排除事件部分重叠。 | Accept | 总计划 §10.2 明确同一批事件换划分仍不是独立总体；整个集合的 digest 不等不能证明集合不相交。freeze 目前只存 population ID，preclaim 无旧 identity set可比较。 | 在 FR 定义 receipt-bound excluded identity-set artifacts或受控且可验证的不相交 population namespace；claim 前按 canonical `event_group_id` 集合做 disjointness检查，并把 exclusion artifact IDs/digests 纳入 claim key。Sprint 增加 partial overlap、subset/superset、同组换 role/split和顺序变化 sentinel 测试。 |
| 7 | High | Correctness | `gpt-5.6-sol M6-DOC-007` | durable claim 前未保证已有可发布失败证据的独占 run，claim 后崩溃可能成为孤立 claim。 | Accept | FR 第 29、37、41 行同时要求 claim-before-decode、不可覆盖输出和所有 claim 后失败均有失败 run，但未规定 output claim与global claim的原子顺序和双向身份。 | 在 FR 固定状态机：先验证路径并 exclusive-create staging/attempt，再写 preclaim metadata；随后 durable-create global claim并互相绑定 attempt ID/output；最后 decode。规定 postclaim异常、崩溃恢复、file/dir fsync和final rename失败的封存语义。Sprint 增加 occupied output、claim 后崩溃、fsync/rename fault injection。 |
| 8 | High | Security | `gpt-5.6-sol M6-DOC-008` | confirmation grammar允许空 identity，且 scanner/decode 字节边界和文件替换防护未冻结。 | Accept | FR 第 21 行明确允许零 identity；同时未给 header/payload exact keys、编码/换行、delimiter唯一性和同一文件句柄要求。两阶段若重新按路径打开，payload 可在 preclaim 后被替换。 | 在 FR 给出 exact header/payload schema与字节语法：至少一个 identity且两类支持满足预注册条件、UTF-8无BOM、LF、唯一 delimiter、恰好一行 payload、duplicate-key拒绝和合理尺寸上限。scanner/decode 使用同一已打开普通文件 handle并核对 identity/stat/size/SHA；拒绝 link/reparse替换。Sprint 增加空输入、delimiter伪装、BOM/CRLF、超长行和替换 sentinel。 |
| 9 | High | Requirement | `gpt-5.6-sol M6-DOC-009` | controls/confirm 的 mode、config union、run schema、终态和退出码不明确。 | Accept | FR 第 41 行称 exact config但未定义两个 mode 的互斥/缺省、confirmation input 条件必填、capacity/CDF 是同一还是独立 run，以及 disabled/terminal/external-pending 的 manifest/exit语义。AGENTS 要求稳定退出码并区分 synthetic、authority和scientific evidence。 | 在 FR 定义两个互斥 subcommand/config schema，或一个 exact tagged union；列出每个 stage、文件名、schema keys、direct upstream、reader和 `0/2/3/4/5/70` 映射。分离统计判定与证据级别：synthetic 使用 `synthetic_rule_satisfied`，只有满足受信输入和后续证据门才允许科学 confirmation 状态。Sprint 增加 mode/config/terminal矩阵。 |
| 10 | Medium | Consistency | `gpt-5.6-sol M6-DOC-010` | `repeat=true` 与 claim 后失败不可重试的关系不清楚。 | Accept | FR 第 29 行允许同 key显式重放，第 37/48 行又把 claim 后失败设为不可作为新设计重试；没有定义 success/failure/crash 后是否 decode、输出名和 attempt记录。 | 在 FR 增加 first/in-progress/crashed/success/postclaim-failed × same/different key 的状态表。建议 claim本身保持只读；允许的同配置重放写入新 immutable attempt run/ledger并引用原 claim，明确何时禁止再次 decode。Sprint覆盖并发 repeat及成功/失败后 repeat。 |
| 11 | Medium | Test | `gpt-5.6-sol M6-DOC-011` | Sprint 未给 focused 命令和可信边界负例矩阵。 | Accept | Sprint §4 只有主题与“focused、全量pytest”，没有具体模块/命令，也遗漏 artifact substitution、partial overlap、claim崩溃、文件替换和public reader重放。 | 在 Sprint 写出 focused pytest 命令和最小负例矩阵，覆盖 M1–M5 public readers、capacity/CDF/confirmation、artifact transaction和assessment guards；明确 decode sentinel、重签/substitution、crash injection、Windows link/reparse差异，并继续把 full suite 与科学/ARM64证据分开报告。 |
| 12 | High | Correctness | `gpt-5.5 M6-DOC-001` | capacity model与现有 M3/M4 reader兼容边界未定义。 | Accept | 该评论与第 2 项结论一致，但强调已有 reader 必须继续拒绝非baseline模型，避免为capacity放宽可信边界；这一理由独立成立。 | 在 FR/artifact schema 明确 capacity 专用 schema和reader、哪些现有 reader必须拒绝它、以及 capacity模型如何从M2/M3/M4 receipt重放；Sprint加“capacity model进入baseline reader/M5/confirmation必须拒绝”回归测试。 |
| 13 | High | Risk | `gpt-5.5 M6-DOC-002` | paired differences与evaluation receipts缺少逐replicate模型/重采样绑定。 | Partial | 来源缺口成立，与第 5 项一致；但“正式科学输入必须在 M6 已可用”不应覆盖 M7 authority/numerical evidence边界。M6必须先保证机器状态不会把 synthetic fixture冒充科学确认。 | 在 M6 定义可验证 evaluation package及逐replicate compact/reference W68、multiplicity digest、population和artifact pointers；没有该 package时 controlled-MC 保持 `external_pending`。Sprint只以 synthetic fixture验证重放/篡改/状态机，不声称独立科学确认。 |
| 14 | High | Correctness | `gpt-5.5 M6-DOC-003` | claim key需要的字段只在payload中，preclaim阶段没有合法来源。 | Accept | FR 第 21 行未列 header exact keys；第 29 行却要求 claim key覆盖 overlay/freeze/delta/CI/bootstrap等字段。若从payload读取会违反 claim-before-decode；若从config读取，文档也未定义与header/payload的三方一致性。 | 在 FR 冻结 header exact keys和每个 claim-key字段的preclaim来源：已验证本地 base/overlay/freeze、exact config、header identity、whole-file SHA。decode 后payload必须逐字段等于preclaim snapshot，否则发布 postclaim failure。Sprint增加 payload drift sentinel。 |
| 15 | Medium | Documentation | `gpt-5.5 M6-DOC-004` | CDF artifact缺少文件surface、direct upstream、disabled/terminal schema和reader重放。 | Accept | 该评论补充第 3–4 项的持久化细节；现有 artifact schema §10–11 对M4/M5均列出固定文件、stage、schema、upstream和reader重放，M6应保持同等级契约。 | 在 artifact-schema §12列出 CDF run stage、固定文件、exact keys、直接上游、disabled零decode形态、terminal枚举/nullability、reader replay和exit映射；Sprint逐项覆盖 receipt重签、零分母、support failure和raw report不可变。 |
| 16 | Medium | Correctness | `gpt-5.5 M6-DOC-005` | M6 config不足以调用 M4/M5 public readers重验完整lineage。 | Accept | 当前 `read_sample_efficiency_report` 等public reader需要 prepared、freeze、subset、gate、T1和batch路径；FR exact config只列 base/overlay/freeze/batch/report等，未说明如何得到其余可信输入。 | 扩充 exact config以显式包含 prepared、training-subsets、gate和T1 evidence，或在FR定义一个经receipt验证、可从report/batch安全解析这些路径的resolver；禁止从manifest自由context猜测。Sprint增加跨prepared、替换gate/T1/batch/report拒绝测试。 |
| 17 | Medium | Test | `gpt-5.5 M6-DOC-006` | Sprint缺少payload poison、postclaim drift及capacity/CDF隔离回归。 | Accept | FR明确 capacity/CDF不得进入候选、M5主结果或confirmation，且claim前不得decode；当前Sprint测试没有把这些负向边界逐项列为可执行验收。 | 在Sprint补充 poison decode sentinel、candidate/delta/bootstrap drift、claim后失败run与repeat、capacity进入M5/confirmation拒绝、CDF替换raw W68拒绝、协议外坐标拒绝，以及 synthetic/external-pending不能升级为scientific confirmation的测试。 |

## Needs Immediate Action

- 修订 FR 的 capacity 坐标、专用模型/下游 artifact reader与ID/lineage契约。
- 修订 FR 的 CDF 公式、失败映射、stage DAG、固定文件和receipt重放契约。
- 修订 confirmation evaluation package、preclaim header/字节语法、事件集合不相交证明和同一文件句柄规则。
- 修订 durable claim/output/attempt/repeat状态机，以及CLI tagged config、终态和退出码。
- 修订 Sprint，加入具体 focused命令和上述负例矩阵。
- 将 synthetic 判定与科学 confirmation 状态分开；受信独立输入缺失时保持 `external_pending`。

## Can Be Deferred

- 正式独立 controlled-MC 输入的取得与运行。
- native ARM64 authority validation、完整 ROOT 和 scientific numerical validation。
- M7 对正式 scientific confirmation 的最终证据登记；这些延后项不得被 synthetic 状态提前宣称完成。

## Final Status

**Reject as-is；修订后再进入 M6 实现。** 最小剩余工作是把以上 Accept/Partial 项写回 FR、Sprint 和计划中的 artifact-schema §12，并完成一次目标文档复核。该结论不要求在 M6 文档阶段取得 M7 的正式科学或authority证据。
