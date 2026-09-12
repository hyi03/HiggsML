# Sprint M4-01 文档评审确认

## 输入与结论

- 目标：[FR-SE-04](../1-Requirement/FR-SE-04-learning-curve-batch-workflow.md)、[sprint-m4-01](../3-Plan/sprint-m4-01.md)
- 评审：[gpt-5.5](sprint-m4-01-review-by-gpt-5.5.md)、[gpt-5.6-sol](sprint-m4-01-review-by-gpt-5.6-sol.md)
- 结论：文档的批次目标正确，但plan-only依赖、共同grid provenance、gate/T1绑定、严格schema、状态机和clean边界尚不足以安全实现。以下接受项应用后再进入编码。

| 严重度 | 类型 | 评审意见 | 决定 | 依据 | 文档/实现动作 |
|---|---|---|---|---|---|
| High | Requirement | gpt-5.5 #1：plan-only无法在不运行M2时给出subset/cell最终身份。 | Accept | experiment ID绑定M2 artifact ID，现有参数确实不足。 | 增加`--training-subsets-run`；plan-only必需，执行模式也要求预先发布的M2 run。M4只消费并重验，不在批次内发布M2。 |
| High | Schema | gpt-5.5 #2：各stage payload/schema/reader重算未定义。 | Accept | M4 reader和M5消费需要稳定契约。 | 补充stage名、文件、schema、digest、upstream、lineage与reader责任表。 |
| High | Security | gpt-5.5 #3：gate/T1来源和旧G1关系不明确。 | Accept | 旧G1不能作为三表示completeness gate，但可作为前置发现证据。 | gate固定为旧`templates` run的passed `g1.json`与receipt-bound `t1-validation.json`；绑定prepared/base，外部T1 canonical bytes必须一致。compact freeze通过其selection/discovery metadata独立关联，不要求旧gate反向引用后生成freeze。 |
| Medium | Correctness | gpt-5.5 #4：共同grid失败后的cell/batch状态不清。 | Accept | 完整ledger必须保留已完成stage事实并给后续stage确定状态。 | 增加状态矩阵、blocked_stage、batch_status与计数公式。科学terminal仍发布complete外层run；binding/内部错误发布失败manifest且M5不消费。 |
| Medium | Security | gpt-5.5 #5：clean proof和flag组合不精确。 | Accept | 删除是破坏性操作且项目要求失败/完成run不可变。 | `--clean`与执行/plan-only互斥；只删除exclusive ownership marker证明、无任何manifest/failure/未知entry的未启动占位目录。部分、失败、complete或含run后代一律拒绝。 |
| Medium | Concurrency | gpt-5.5 #6：worker返回/发布与失败序列化未定义。 | Accept | M4可以采用更小且可验证的reference范围。 | M4明确只接受`workers=1`；多worker执行延期，plan/cell科学身份保持与资源无关。 |
| Medium | Test | gpt-5.5 #7：focused未覆盖M3下游边界。 | Accept | M4组合了lineage/template/inference接口。 | focused加入M3 lineage、templates、inference测试。 |
| Low | Clarity | gpt-5.5 #8：config/resources/overlay职责不清。 | Accept | 科学坐标不得落入run config。 | 定义exact batch config仅含schema、dataset、base protocol/path默认值、output name；resources只含既有资源键且M4 workers固定1；拒绝科学键。 |
| High | Requirement | gpt-5.6-sol F-01：plan identity循环。 | Accept | 与gpt-5.5 #1独立论证一致；核对M2 public reader后确认其严格语义重验必须重新解码verified MC train payload。 | M2成为M4已发布前置；plan-only调用M2 reader重验receipts/ledger并允许其MC train-only decode，仍保证零写入、零训练/RNG且不读取assessment。 |
| High | Security | gpt-5.6-sol F-02：每cell template无法证明共同grid来自全部成功calibration。 | Accept | 外层grid ID不足以成为直接上游。 | 新增`sample-efficiency-common-grid` run，upstream精确为subset、sealed plan和全部calibration success；template直接绑定grid+自己的calibration+prepared。 |
| High | Security | gpt-5.6-sol F-03：gate artifact和T1内容未进入identity。 | Accept | evidence_id不是内容摘要。 | scientific batch ID绑定gate artifact ID与T1 canonical SHA；外部证据与gate snapshot完全一致，所有T1 stage继续绑定grid/plan。 |
| High | Schema | gpt-5.6-sol F-04：plan/cell/grid/ledger/summary缺字段级schema。 | Accept | 严格未知字段和重签抵抗需要exact schema。 | 文档固定root keys、cell keys、ID preimage、顺序、nullability、JSON Pointer和重算规则；实现集中validator。 |
| High | Correctness | gpt-5.6-sol F-05：cell/batch状态机不闭合。 | Accept | 与gpt-5.5 #4一致且指出计数定义缺口。 | `planned_count`为alias坐标，`deduplicated_count`为canonical cell，`complete_count`为四stage成功，`terminal_count`为合法科学terminal；blocked后续stage逐项记录。 |
| High | Security | gpt-5.6-sol F-06：clean对部分批次/Windows路径不安全。 | Accept | 任何已有run或failure evidence不得删除。 | ownership marker exclusive-create且绑定绝对目标/scientific ID；逐组件拒绝reparse/symlink，未知entry或任意后代manifest/failure立即拒绝；整体不清理部分批次。 |
| Medium | Identity | gpt-5.6-sol F-07：路径和资源不应进入科学batch ID。 | Accept | run配置不属于科学身份，多worker等价性也要求科学ID稳定。 | 分离`scientific_batch_id`与`execution_plan_id`；后者绑定resolved output/resources，cell ID保持协议定义。 |
| Medium | CLI | gpt-5.6-sol F-08：CLI名称、dataset/base protocol/config优先级不清。 | Accept | 项目business CLI要求显式dataset。 | 公开入口为脚本和`python -m src.cli.sample_efficiency`，不新增console entry；必需`--dataset atlas2020_4lep --protocol`，显式参数覆盖config路径但不能覆盖科学值。 |
| Medium | Correctness | gpt-5.6-sol F-09：T1 Asimov调用参数与指标pointer未冻结。 | Accept | M1 primary metric要求μ=1、T1、68%。 | 固定`layer=T1`、`injections=[1.0]`、base μ bounds/confidence levels；W68 pointer为μ=1的0.68 interval width，AUC pointer为model validation absolute-weight AUC。 |

## 状态

当前阶段：document-review-confirmed。应用上述文档修改后才能开始focused tests与实现。
