# FR-SE-05：配对聚合、评价重采样与学习曲线报告

## 背景与目标

M4 已发布并可逐层重验完整 learning-curve batch，但尚未形成可审计的统计记录与图表。M5 新增隔离的报告层，只消费 M4 verified reader 和其直接绑定的 MC validation/model/inference artifacts，输出所有计划 cell、严格配对比较、分层误差、观测范围内 Q* 结论及机器可读/可视化文件。

## 范围与约束

1. 新增 `src/research/sample_efficiency.py`、`src/cli/sample_efficiency_report.py` 与 `scripts/h4l_sample_efficiency_report.py`；不改变旧 reporting 或 M4 batch publisher。
2. 入口只接受已验证的 M4 batch、prepared、compact-freeze、training-subsets、gate/T1、base/overlay；禁止 assessment/held-out test。
3. 报告 run stage 固定为 `sample-efficiency-report`，直接 upstream 仅为完整 M4 batch run；manifest context 只作索引。
4. 输出固定为 `sample-efficiency-records.jsonl`、`sample-efficiency-summary.json`、`sample-efficiency-curves.csv`、`sample-efficiency-curves.png`、`sample-efficiency-report.md` 和 `report-contract.json`。capacity/CDF 文件属于 M6，不在 M5 产生。
5. publisher 必须先经 M4 reader 重验完整 plan/ledger/summary及全部 stage，再读取 cell payload。失败、缺失与 terminal cell 都保留为记录，禁止删选、重抽或插补。

## 报告合同

`report-contract.json` schema 为 `h4l-sample-efficiency-report-contract-v1`，精确记录 M4 batch artifact ID、scientific/execution batch ID、base/overlay digest、evaluation uncertainty、calibration uncertainty、primary metric、pairing keys、quality target、输出 schema版本与 `report_contract_id`。ID覆盖除自身外完整 payload。

`sample-efficiency-records.jsonl` 每个 canonical plan cell恰有一行，顺序等于 plan。schema为`h4l-sample-efficiency-record-v1`，精确字段为：

- plan/cell身份：`plan_index,experiment_cell_id,pairing_id,representation_id,sample_fraction_target,sample_draw_seed_or_full,network_seed,architecture_variant,training_subset_id,actual_train_group_count`；
- 状态：`cell_status,terminal_stage,status,reason,stage_artifact_ids`；
- 指标：`w68,validation_absolute_weight_auc,evaluation_auc_bootstrap`；
- 配对：`baseline_experiment_cell_id,pair_status,delta_w68,relative_w68`；
- `record_id`。

complete cell 的 W68 必须由 M4 inference pointer 指向的 μ=1、68% interval width读取；训练 AUC必须由 model pointer读取。所有cell的实际训练组数以重验后的M2 training-subset `summary_total.group_count`为权威来源；存在model时再要求model值精确相等，因此model-stage terminal也有确定组数。terminal cell的W68/AUC/bootstrap为null。每条记录ID覆盖其余字段。

主基线固定为 `engineered19`。比较只在 `(sample_fraction_target,sample_draw_seed_or_full,network_seed,architecture_variant)` 完全相同且双方 complete 时成立：`delta_w68=W68(R)-W68(engineered19)`，`relative_w68=W68(R)/W68(engineered19)`。engineered19 自身配对自身，差为0、比为1。任一侧非complete或缺失时 `pair_status=paired_cell_missing` 且差/比为null；不能跨seed、draw、fraction或架构补齐。

## 评价事件组 bootstrap

评价误差只针对 validation absolute-weight AUC。先从 lineage绑定的 prepared run通过M3 public role loader加载 `role=validation`，拒绝空集合、混合role、组内label冲突和非有限权重。group ID按canonical JSON UTF-8 bytes升序；使用NumPy `Generator(PCG64(seed))`，replicate从0递增，每次调用`integers(0,G,size=G,endpoint=False)`并形成组multiplicity。所有 complete models 共用同一batch resample plan，plan ID覆盖排序group digest、算法、seed、replicate数和完整multiplicity矩阵；每条bootstrap结果绑定该ID。行权重为 `abs(physical_weight) × group multiplicity`；两类总正权重均大于0时计算AUC，否则replicate无效。不得重训、重校准、重建模板或改变候选。

AUC固定为带权Mann–Whitney算法：按score升序，score完全相等为一组，正类权重乘“此前负类权重+本tie负类权重的一半”，总和除以正负总权重乘积；signal label固定为1。所有输入/输出必须有限。统计标准差固定`ddof=1`，分位数固定NumPy linear quantile。0个有效replicate时全部统计量null、status=`not_estimated`；1个时mean及两个quantile为该值、std=null、status=`partially_estimated`；达到请求数且至少2个时`estimated`，否则`partially_estimated`。

每个 complete cell 的 `evaluation_auc_bootstrap` 精确记录 method/unit/seed/requested_replicates/valid_replicates/status/mean/std/quantile_16/quantile_84。全部有效时status=`estimated`；部分无效为`partially_estimated`；零有效为`not_estimated`。这些结果只描述评价 AUC 误差，不标为训练子集或模板统计误差。

## 聚合与误差分层

summary schema为`h4l-sample-efficiency-summary-v1`，按 `(representation_id,sample_fraction_target,actual_train_group_count)` canonical排序聚合 complete与terminal计数、failure_rate、均值 W68/AUC/relative W68/delta W68和配对完整率。

- `network_uncertainty`：同一 representation/fraction/draw/actual-count 内网络seed指标的样本标准差（`ddof=1`），再报告这些 draw-level标准差的算术均值；不足2 seed为`not_estimated`。
- `subset_uncertainty`：只使用所有draw共同complete的network-seed交集；先按draw对交集seed取均值，再跨draw算样本标准差（`ddof=1`）。少于2 draw或交集少于2 seed为`not_estimated`；full endpoint固定为`not_estimated`，不得由重复alias制造方差。delta/relative直接使用已配对record值执行相同算法。
- `evaluation_uncertainty`：对每个replicate先在该curve row的固定complete cell集合上取AUC算术均值，再对replicate-level aggregate计算mean/std/linear 16%/84%分位；保留requested/valid replicate数与resample plan ID。W68写`not_estimated`。
- `calibration_uncertainty`：按协议固定写`not_estimated`。
- `template_finite_mc`：写`propagated_by_shapesys_T1`，不把它与上述经验标准差合并。

所有均值、标准差和分位数只使用记录中明确 complete/estimated 的值；非有限值禁止进入artifact。summary row精确计数`planned_count,complete_count,terminal_count,pair_eligible_count,paired_count,baseline_missing_count,target_missing_count`；指标均值分母为complete count，delta/relative分母为`pair_status=paired` count，pair completeness为`paired_count/pair_eligible_count`。engineered19自配对计入paired。五个网络种子的标准差不得称为 MC 统计误差。

## Q* 与渲染

若 `quality_target.enabled=false`，每个表示状态为`disabled`。启用时，Q*只使用`complete_count==planned_count`的curve row；不完整点产生`not_estimated_incomplete`且不能由幸存均值支持结论。每个表示的实际组数必须唯一；不同fraction映射到相同实际组数时该表示为`ambiguous_duplicate_actual_count`。其余点按实际组数升序；只允许浮点精确相等命中 Q*，或相邻点满足前点 `W68>Q*`、后点 `W68<Q*` 且实际组数严格增加时按`n=n0+(Q*-w0)*(n1-n0)/(w1-w0)`线性插值。多个合法区间取最小n的第一个并记录两侧curve row IDs；没有合法区间时为`not_reached_within_study_range`。禁止端点外推、curve拟合、幂律或缩放律。

CSV 与 PNG 只从已经构造并通过 exact schema 的 summary curve rows生成。CSV固定UTF-8、LF、RFC4180、header与curve-row exact列，浮点使用Python round-trip十进制、null为空字段。PNG固定两个 panel：W68与 relative W68，横轴均为实际 train event-group count；误差层用独立字段/图例表达，缺失值不连线。summary内保存exact `plot_spec`及覆盖panel/series/curve-row IDs/轴标签/误差语义的digest；PNG明确为非权威缓存，reader认证plot spec/CSV并检查PNG receipt。Markdown用固定模板从contract/summary/失败记录逐字节重放；只陈述合同、完整性、失败表、误差层状态与 Q* 状态，不生成 MC 节省倍数，不描述为 ATLAS结果或物理测量。

summary顶层exact keys为`schema_version,report_contract_id,resample_plan_id,record_count,curve_rows,quality_targets,plot_spec,summary_id`。curve row exact keys为`curve_row_id,representation_id,sample_fraction_target,actual_train_group_count,counts,means,network_uncertainty,subset_uncertainty,evaluation_uncertainty,calibration_uncertainty,template_finite_mc`；每个嵌套对象使用固定键及`estimated|partially_estimated|not_estimated`状态和按状态nullability。quality target exact记录`representation_id,status,target_w68,estimated_group_count,left_curve_row_id,right_curve_row_id`。report contract须列出上述schema映射、weighted AUC/PCG64/ddof/quantile算法ID、JSONL无header及CSV方言。

## Reader 与完整性

publisher接收M4 path和完整M4 verification inputs，先调用M4 public reader；随后每次取cell model/inference时再次调用对应public reader/`LoadedRun.file()`并核对ledger artifact ID，避免把“曾验证过的路径”当capability。report reader接收report path加同一组M4 verification inputs，重新执行完全相同链路。它验证 report run receipt、唯一M4 batch直接 upstream、contract/record/summary IDs、JSONL逐行strict JSON与行数/顺序、所有 plan cell覆盖恰好一次、指标指针、bootstrap plan与数值重放、配对/聚合/Q*重算、CSV逐字节重放、Markdown逐字节重放，以及 PNG receipt与plot-spec digest。任何 receipt自洽的语义漂移统一拒绝为`learning_curve_incomplete`或`training_subset_binding_mismatch`。

## CLI 与安全

CLI配置另设exact `h4l-sample-efficiency-report-config-v1`：`schema_version,dataset,protocol,sample_efficiency_protocol,prepared_run,compact_freeze_run,training_subsets_run,gate_run,t1_validation,batch_run,output_root,output_name`，所有路径/名称为非空字符串且未知键拒绝。公开参数为上述字段对应选项加`--config`，显式参数优先；dataset必须显式且与config/base/overlay/batch一致。不新增console entry point。生产output root固定为`neural/runs`，output name为安全单层名，目标必须是不存在的新直接子目录。CLI不得提供筛选cell、重设seed/replicates/Q*或跳过失败项的参数；usage为2、binding/incomplete为3、未知异常为70。

## 验收与验证

- 顺序打乱不影响聚合；所有 planned cell均在JSONL中且terminal不被删除。
- 配对只使用完全匹配键；缺失/terminal baseline产生`paired_cell_missing`。
- bootstrap按event group、跨模型共用replicate且确定；评价、draw、network、confirmation seeds不混用。
- full endpoint subset uncertainty为`not_estimated`；其他未实现误差层显式标注。
- Q*只在观测相邻点包围或精确命中时报告，永不外推。
- focused测试后运行`python -m pip check`与全量`python -m pytest -q`。

Windows synthetic只证明软件路径；ARM64 authority、完整ROOT与科学数值验证留待M7。

artifact schema同步新增§11“配对聚合报告”，记录contract、records JSONL、resample plan、summary/curve、CSV/plot spec与Markdown reader责任。

当前阶段：completed。focused报告3 passed/105 warnings、CLI 3 passed，pip check通过，全量686 passed/227 warnings；Windows synthetic不构成ARM64 authority、完整ROOT或科学数值验证。
