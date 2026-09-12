# FR-SE-04 学习曲线批处理与完整 ledger

- `FR-ID`: `FR-SE-04`
- `标题`: 学习曲线批处理与完整 ledger
- `所属阶段`: M4
- `开发顺序`: 4
- `优先级`: P0
- `前置依赖`: [FR-SE-03](Done/FR-SE-03-subset-bound-discriminant-v2.md)
- `涉及包`: `src.research.sample_efficiency_workflow`、`src.cli.sample_efficiency`、`scripts/h4l_learning_curve.py`、`tests/research`
- `是否属于原型阶段`: 是（synthetic 软件验证）
- `来源类型`: 新需求
- `原始 SRS 章节`: 样本效率开发计划 §8、§13—17 M4

## 目标

新增与旧发现 workflow 隔离的学习曲线批处理入口：在不读取 assessment/held-out test 的前提下，依据已验证 base/overlay/prepared/freeze 生成确定、去重、完整的计划，执行 M2 子集、M3 baseline v2 模型、raw 校准、批次共同模板网格与 T1 model-self Asimov，并把每个 planned cell 的成功或具名终态保存在可重验 ledger 中。

## 范围

1. 新增薄 CLI `src.cli.sample_efficiency` 与独立脚本 `scripts/h4l_learning_curve.py`。旧 `scripts/h4l_run.py`、`src.research.workflow.execute()`、旧 CLI 参数与输出保持不变。
2. 公开入口为 `python -m src.cli.sample_efficiency` 和 `scripts/h4l_learning_curve.py`，不新增console entry point。CLI 参数固定为 `--dataset atlas2020_4lep`、`--config`、`--protocol`、`--sample-efficiency-protocol`、`--prepared-run`、`--compact-freeze-run`、`--training-subsets-run`、`--gate-run`、`--t1-validation`、`--output-root`、`--resources`、`--plan-only`、`--clean`、`--no-progress`。路径来自显式参数或批次配置，显式路径优先；dataset必须显式给出并与config/base一致。科学网格只能来自已验证协议。
3. M2是M4已发布前置：M4不创建training-subsets。`--plan-only` 和执行模式都必须接收并通过M2 public reader完整重验 `--training-subsets-run`；该reader为重从receipt run语义会重新解码verified prepared中的MC train payload，但永不解码assessment/held-out test。plan-only随后返回 canonical `h4l-sample-efficiency-batch-plan-v1`，不得创建、删除、claim或修改目录，不训练、构建pyhf模型或初始化RNG。
4. 计划以 M2 canonical alias为输入：partial保留协议内每个 `(fraction,draw)`；full的多个draw alias只生成一个 canonical subset/model cell。每个唯一 subset 与三表示、全部 network seed、唯一 baseline architecture组成cell；计划顺序固定为 fraction、draw/full、network seed、representation。禁止调用方删选cell或覆盖科学坐标。
5. plan分离 `scientific_batch_id` 与 `execution_plan_id`。前者绑定双协议、prepared/population/freeze、M2 artifact/plan、gate artifact、T1 canonical digest、共同网格算法、T1 inference contract和canonical cells；不含路径、资源、软件或进度设置。后者绑定完整scientific plan、resolved output root/name与resources。cell experiment/pairing ID沿用M3公式且不受执行配置影响。
6. 执行先重验M2 run，再发布sealed plan run并逐cell调用 M3 application service。每个模型成功或 `training_subset_insufficient_statistics`、既有训练数值终态都写入 ledger；binding错误和未知异常停止批次，不伪装科学终态。
7. 成功模型只执行 raw calibration。从同一 verified prepared template role为所有成功cell生成已分类frame，并调用现有 `common_mass_grid()` 一次确定批次共同质量网格；不得按cell使用不同网格。另发布`sample-efficiency-common-grid` run，其upstream精确为sealed plan、training-subsets及全部且仅calibration-success runs；payload记录参与/排除cell、初始grid、merge history、最终edges和terminal。共同网格失败产生具名 batch terminal，不删除弱单元。
8. 每个有效cell在共同网格上发布 template，并在同一已验证 T1 modifier contract下执行 `expectation_kind="model_self_asimov"`。M4不执行 toys、assessment、mismatch、CDF、capacity或独立确认。
9. plan、model、calibration、common-grid、template、inference各自使用新目录且manifest-last、不可覆盖。直接上游run必须写入manifest：calibration绑定sealed plan+prepared+model；common-grid绑定plan+subsets+全部calibration success；template绑定plan+prepared+calibration+common-grid；inference绑定plan+template+common-grid；batch绑定plan+subsets+common-grid及全部已发布cell stage。每层reader验证receipt、stage、upstream path/multiplicity和正式payload identity。
10. batch ledger schema为 `h4l-sample-efficiency-batch-ledger-v1`，精确包含全部planned cell且每个cell恰有一个终态。成功cell记录四个stage artifact ID、共同grid ID、lineage、W68/AUC的原始输入位置；M4不做跨cell统计。具名终态记录status/reason/exit code，不能省略或跨cell补齐。
11. `sample_efficiency_completeness` 比较plan与ledger：重复、未知、缺失、身份漂移、成功stage不完整均产生 `learning_curve_incomplete`。planned、deduplicated、complete和terminal计数必须可从ledger重算且与summary一致。
12. `--clean`与`--plan-only`及执行互斥。clean只允许删除由application service exclusive-create的 `.sample-efficiency-owner.json` 证明、且仅含该marker和空`staging/`的未启动批次占位目录；marker绑定recomputed execution plan ID和规范绝对目标。目标及每个祖先/后代拒绝symlink、junction/reparse point；出现任意manifest、failure、已发布/冻结run或未知entry即整体拒绝。失败和部分批次保持不可变。路径必须位于仓库`neural/runs`或测试显式`allowed_root`，根目录不可作为目标。
13. M4 reference执行器的资源schema仅接受`workers=1`，从而保证单进程、parent-only publication；多worker与线程调优留给M7平台验证。计划/cell科学身份不含资源字段。
14. gate固定为已验证旧`templates` research run：同一base/prepared upstream、`g1.json.status="passed"`、`g1.json.assessment_used=false`，并含receipt-bound `t1-validation.json`。外部`--t1-validation` canonical bytes必须与该snapshot相同；T1精确匹配`validated/independent_process_bins/poisson_tau_gamma/shapesys/pyhf 0.7.6`且有evidence ID。plan绑定gate artifact ID与完整T1 SHA。旧G1只作为发现前置证据，不作为三表示completeness gate；compact freeze由overlay和其selection/discovery metadata独立验证，不要求旧gate反向引用后生成freeze。
15. T1调用固定为`layer="T1"`、`injections=(1.0,)`、`expectation_kind="model_self_asimov"`，μ边界与confidence levels来自base。ledger中的W68来源固定为inference payload `/result/results/0/intervals` 中`confidence=0.68`的`width`，AUC来源为model payload `/model/validation_absolute_weight_auc`；位置以artifact ID+filename+JSON Pointer记录。
16. 所有公共读取器先验证manifest与文件receipt再解析payload；JSON未知/缺失/重复键、非有限值、重签身份、错误upstream/path均拒绝。任何 discovery/batch命令不得读取assessment role payload。

## 严格 schema 与 artifact 拓扑

batch config schema `h4l-sample-efficiency-batch-config-v1` 精确键为`schema_version,dataset,protocol,sample_efficiency_protocol,prepared_run,compact_freeze_run,training_subsets_run,gate_run,t1_validation,output_root,output_name`；除schema/dataset/output_name外均为非空路径字符串。禁止fraction、draw、seed、representation、architecture、threshold、grid或inference科学参数。M4 batch plan的resources exact schema仅为`workers`且值固定为1。

plan精确根键为`schema_version,scientific_batch_id,execution_plan_id,dataset,base_research_protocol_sha256,sample_efficiency_protocol_sha256,prepared_artifact_id,population_id,compact_freeze_artifact_id,training_subsets_artifact_id,training_subset_plan_id,gate_artifact_id,t1_evidence_sha256,common_grid_contract,inference_contract,planned_alias_count,canonical_cell_count,cells,execution`。`scientific_batch_id=SHA256(canonical(plan去掉scientific_batch_id/execution_plan_id/execution))`；`execution_plan_id=SHA256(canonical(plan去掉execution_plan_id))`。cells按固定顺序且每项exact keys为`plan_index,representation_id,sample_fraction_target,sample_draw_seed,sample_draw_seed_or_full,training_subset_id,membership_digest,network_seed,architecture_variant,experiment_cell_id,pairing_id,relative_paths`；relative_paths exact为model/calibration/template/inference。execution exact为`output_root,output_name,resources`；`--no-progress`只控制本地显示，不进入任何plan identity。

| Stage | 目录/文件 | payload schema与ID | 直接 upstream |
|---|---|---|---|
| `sample-efficiency-plan` | `plan/batch-plan.json` | 上述plan；manifest context仅作索引 | prepared、compact-freeze、training-subsets、gate |
| `sample-efficiency-calibration` | cell `calibration/calibration.json` | envelope `h4l-sample-efficiency-calibration-v1`：`schema_version,experiment_cell_id,calibration,record_id`；record ID覆盖前3项，calibration为M3严格bundle | plan、prepared、model |
| `sample-efficiency-common-grid` | `common-grid/common-grid.json` | `h4l-sample-efficiency-common-grid-v1`：双batch ID、participant/excluded cell+artifact有序表、initial edges、merge history、final edges、status、reason、`grid_id`；grid ID覆盖其余字段 | plan、training-subsets、全部且仅calibration-success |
| `sample-efficiency-template` | cell `template/template.json` | envelope `h4l-sample-efficiency-template-v1`：双batch ID、experiment cell、grid ID、M3 template、`record_id` | plan、prepared、自己的calibration、common-grid |
| `sample-efficiency-inference` | cell `inference/inference.json` | envelope `h4l-sample-efficiency-inference-v1`：双batch ID、experiment cell、grid ID、T1 SHA、M3 result、W68/AUC pointers、`record_id` | plan、自己的template、common-grid |
| `sample-efficiency-batch` | `batch/batch-ledger.json`,`batch-summary.json` | ledger `h4l-sample-efficiency-batch-ledger-v1`和summary `h4l-sample-efficiency-batch-summary-v1`均有覆盖除自身ID外完整payload的digest | plan、training-subsets、common-grid、全部已发布cell runs |

所有列表保持canonical plan顺序，ID字段为小写SHA-256。reader从verified upstream payload重算每个envelope ID、lineage、grid participant集合、cell outcome和ledger/summary计数；upstream按严格列表校验stage/artifact/path且拒绝重复。

## 状态机与完整性

每个canonical ledger cell精确记录`plan_index,experiment_cell_id,stage_artifact_ids,grid_id,cell_status,terminal_stage,blocked_stages,status,reason,exit_code,metric_sources`。`stage_artifact_ids`固定四键且未发布项为null；在grid形成前进入terminal时`grid_id=null`，其余精确等于共同grid。已发布事实永不被后续失败覆盖。模型/校准/template/inference全部成功时`cell_status=complete`；M2低统计或既有科学终态时`cell_status=scientific_terminal`，`terminal_stage`指出发生阶段，后续stage按顺序进入`blocked_stages`。共同grid失败将所有尚未完成template/inference的cell标为scientific terminal，保留已有model/calibration IDs。

`planned_alias_count`是M2原始alias×representation×network的数量；`canonical_cell_count`在full alias去重后计数；`complete_count`为四stage均有artifact且contract有效的cell；`terminal_count`为允许的scientific terminal。完整性要求`complete_count+terminal_count=canonical_cell_count`且ledger cell集合精确等于plan。只要全部cell被解释，外层research manifest为complete，`batch_status`为`complete`或`scientific_terminal`，M5 reader可消费；缺失/重复/身份漂移为`learning_curve_incomplete`并拒绝发布可消费ledger。binding或未知异常只留下ResearchRun失败manifest，M5 reader拒绝。

## 输出

- `plan/`
- `cells/<cell-id>/model|calibration|template|inference/`
- `common-grid/`
- `batch/`
- `batch-plan.json`
- `batch-ledger.json`
- `batch-summary.json`

外层完成run stage为`sample-efficiency-batch`。M5报告只消费其verified reader返回值。

## 不纳入范围

M5的配对聚合、evaluation bootstrap、Q*、CSV/PNG/Markdown；M6的capacity/CDF/assessment确认；M7正式ROOT/ARM64证据。M4不把Windows synthetic结果描述为科学结论。

## 失败语义

- 子集低统计：`training_subset_insufficient_statistics`，cell terminal，exit 0。
- 批次共同模板统计失败：沿用`insufficient_statistics`或`template_stat_model_unvalidated`并形成批次terminal。
- ledger缺失/重复/漂移：`learning_curve_incomplete`，exit 3。
- 路径、receipt、协议、lineage、gate、T1或clean证明失败：`training_subset_binding_mismatch`，exit 3。
- 未知内部错误：exit 70并保留不可覆盖失败证据。

## 最小验证

先运行 `pytest -q tests/research/test_sample_efficiency_workflow.py tests/research/test_h4l_learning_curve_script.py tests/research/test_sample_efficiency_training.py tests/research/test_sample_efficiency_lineage.py tests/research/test_training_subsets.py tests/research/test_templates.py tests/research/test_inference.py`，再运行`python -m pip check`和全量`python -m pytest -q`，均从`neural`目录用Conda `pytorch`环境执行。

## 验收要点

- synthetic缩小协议可端到端跑通三表示×多fraction/draw/network seed，并证明full去重。
- plan-only零写入、clean边界、旧脚本兼容、失败cell保留和共同网格唯一性均有测试。
- plan与ledger的planned/deduplicated/complete/terminal计数一致；篡改任一cell/upstream/receipt会被reader拒绝。
- 全链只读取train/validation/calibration/template，不读取assessment或held-out test。

## 备注

路径：FR_DIR=`docs/1-Requirement`、FR_DONE_DIR=`docs/1-Requirement/Done`、SPRINT_DIR=`docs/3-Plan`、SPRINT_DONE_DIR=`docs/3-Plan/Done`、REVIEW_DIR=`docs/4-Reviews`。当前阶段为completed。focused 45 passed/68 warnings，pip check通过，全量680 passed/122 warnings；Windows synthetic不构成ARM64 authority、完整ROOT或科学数值验证。
