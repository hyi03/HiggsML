# FR-SE-06：容量/CDF机制检查与独立总体非劣性确认

## 目标

M6实现SampleEfficiencyProtocol中已冻结的唯一capacity variant、精简physical CDF检查，以及独立总体上的claim-before-decode非劣性确认。M6不得重新选择compact候选、容差、fraction、seed、宽度、CDF点或CI算法。

## 容量控制

容量变体ID固定为`match_engineered19_parameter_count_v1`。对输入维数`d`，第一隐藏层宽度为最接近`5568/(d+67)`的正整数，恰好半整数时向下；后两层固定64/32。协议的`width_rule`必须精确为`nearest_positive_integer_ties_lower_5568_over_d_plus_67`。只为`capacity_control.enabled=true`且已注册的fraction/network seed生成cell；三表示与同一raw主cell使用相同training subset、draw、validation、calibration、共同网格和pairing。每个表示只有该一个宽度，禁止候选列表或运行时覆盖。

capacity artifact schema为`h4l-sample-efficiency-capacity-control-v1`，绑定overlay、M4 batch、M5 report、输入维数、解析宽度、实际参数量、主模型参数量、registered coordinates、每cell状态/模型/指标和`capacity_control_id`。disabled时发布具名`disabled`计划但不训练；enabled时只允许注册点。capacity结果只标为mechanism check，不能进入candidate freeze、M5主曲线或confirmation决策。

## 精简physical CDF检查

CDF只在`cdf_check.enabled=true`的注册fraction和协议固定三表示执行，默认必须包含full endpoint。每个检查从对应M4 verified raw model重新加载同一prepared calibration/template角色：在calibration background上调用冻结`fit_calibration(target="physical")`，应用mapping并按相同质量网格/ties/tails/merge规则构建检查指标。

`h4l-sample-efficiency-cdf-check-v1`逐cell绑定raw experiment/pairing/model/calibration artifact、physical mapping ID、注册fraction和共同质量网格。指标固定为calibration category target与实际absolute-weight acceptance的最大绝对误差，以及template background mass-bin acceptance相对raw的最大绝对形变；保留有效分母、terminal状态和`cdf_check_id`。disabled时具名记录且零payload decode。CDF结果不能新增表示/fraction、回扩15组合、替换主raw曲线或触发候选重选；若支持不足，状态为`calibration_uncertainty_dominant`并停止解释。

## Confirmation input与identity-first边界

confirmation输入是外部、不可覆盖的`h4l-noninferiority-evaluation-input-v1`文件：第一行canonical header；随后是零个或多个`identity-json<TAB>`行；分隔行固定`--PAYLOAD--`；最后一行canonical payload。identity exact keys为`event_group_id,label,role,split,dataset`且role必须assessment、label为0/1、dataset/base一致。payload exact记录schema、population ID、base/overlay/freeze digests、compact/reference representation、bootstrap unit/seed/replicates/algorithm、paired W68 difference数组、evaluation artifact receipts与payload ID。

preclaim扫描器只读取header和分隔符之前的identity字段，不解析分隔符之后的payload；按`population_digest`重算population ID。它同时可对整个文件做流式SHA-256但不能解释payload。身份重复、组内label冲突、非assessment role或 malformed input在claim前拒绝。

## 独立性与durable claim

确认population ID不得等于overlay population，不得出现在freeze的`discovery_population_ids`、`browsed_population_ids`或`excluded_population_ids`，也不得与任何M4/M5 lineage population相同；否则在payload decode前以`confirmation_population_not_independent`拒绝。

claim namespace固定`h4l-sample-efficiency-confirmation-v1`，路径位于allowed root的`.sample-efficiency-confirmation-claims/`。claim key覆盖population ID、base digest、overlay digest、compact freeze artifact/digest、delta、confidence、CI algorithm、bootstrap unit/count/seed、evaluation file SHA。以`O_CREAT|O_EXCL`独占创建canonical JSON，flush+fsync文件并fsync目录后才允许decode。已有claim默认`assessment_already_started`；只有freeze/claim key完全相同且调用者显式`repeat=true`才可重放，内容不同永不覆盖。symlink/reparse claim root拒绝。

## 预注册CI与确认payload

decode后重新验证payload population与preclaim scan、全部digest、compact候选、engineered19 reference、bootstrap配置、evaluation receipts及`payload_id`。paired differences数量必须等于`bootstrap_replicates`、全部有限，定义`D=W68(compact)-W68(engineered19)`。区间固定为two-sided equal-tailed percentile，NumPy linear quantile，端点`alpha/2`和`1-alpha/2`；点估计为差数组均值。

只有`upper_ci <= delta_w68`时状态为`confirmed_noninferior_within_registered_margin`；否则为`noninferiority_unconfirmed`。上界恰等容差通过。输出`h4l-noninferiority-confirmation-v1`绑定claim、输入SHA/payload ID、population、协议/freeze、区间算法/预算、estimate/lower/upper/delta、decision和`confirmation_id`。synthetic source的`validation_scope`固定为`synthetic_software_validation`，不得表述为科学确认；controlled-MC仍需M7 authority/numerical evidence。

confirmation run manifest直接upstream为freeze、M4 batch、M5 report，且run只在claim持久化、payload验证和计算完成后发布。任一claim后失败保留claim并发布新的失败run，不允许redesign或回写M1—M5 artifact。

## CLI与输出

新增`python -m src.cli.sample_efficiency_controls`及脚本wrapper，不新增console entry point。exact config列出dataset/base/overlay/freeze/batch/report/confirmation input/output root/name/repeat；科学参数不能由CLI覆盖。production output root固定`neural/runs`。`--controls-only`执行capacity/CDF且不访问confirmation input；`--confirm`要求输入并执行claim-before-decode，两者可分别运行到不同新run。

## 验收

- width公式和ties-lower golden values唯一；disabled/未注册capacity零训练。
- CDF只使用注册三表示/点，绑定raw pairing且不改变主报告。
- 非独立、malformed identity、claim冲突均在payload decode sentinel前失败。
- 合法路径先产生可fsync claim，再触发decode；claim后失败不可重试为新设计。
- CI上界等于delta通过，大于delta不确认；NaN/缺replicate/配置漂移拒绝。
- 现有M1—M5、ResearchProtocol v1/v2/v3和旧CLI保持通过。

Windows synthetic仅证明软件访问顺序与状态机；正式独立总体、ARM64 authority、完整ROOT和科学数值确认可标为external pending并留待M7。

## 精确执行与artifact契约

capacity坐标按`(fraction, draw_or_full, representation, network_seed)`的canonical字典序生成。partial fraction遍历overlay的全部`sample_draw_seeds`；1.0只生成一次canonical `full`。每个cell必须重验M2 subset artifact ID、subset ID、membership digest和对应M4 raw pairing坐标。disabled计划的planned/canonical数量均为0，且不得打开prepared payload或调用训练器。

capacity使用专用`h4l-capacity-discriminant-v1`，不得被`research-discriminant-v2`、M4、M5或confirmation reader接受。模型层序列固定为`Linear(d,w)-LayerNorm(w)-SiLU-Dropout(0.1)-Linear(w,64)-LayerNorm(64)-SiLU-Dropout(0.1)-Linear(64,32)-LayerNorm(32)-SiLU-Linear(32,1)`；训练预算、checkpoint、scaler和优化器规则继承baseline。专用reader从输入维数重算`w`、architecture、参数量、state tensors、cell ID和lineage。capacity calibration/template/T1各有独立envelope和直接上游；顶层ledger保存各stage artifact ID与W68 JSON pointer。其ID preimage包含overlay、M2 subset、representation、fraction、draw/full、network seed和capacity variant，因此不能与baseline pairing ID混用。

CDF检查遍历注册fraction对应的全部M4 canonical raw cells。每个cell重新加载verified raw model及calibration/template角色，在calibration background上拟合physical mapping，再对mapped calibration score重新拟合physical median threshold。第一项指标定义为`abs(sum_abs_weight(mapped_category=1)/sum_abs_weight(all background)-0.5)`；分母为零则`insufficient_statistics`。第二项按M4 `final_mass_edges`在template background中分别计算raw与mapped category-1 absolute-weight acceptance，对有效分母质量箱取`max(abs(mapped_acceptance-raw_acceptance))`；无有效箱则`insufficient_statistics`。不得除以raw acceptance，负signed weight只参与physical mapping拟合，两个报告指标使用absolute weight。`fit_calibration`产生的`insufficient_statistics`、`nonpositive_calibration_yield`、`outside_calibration_support`和`template_stat_model_unvalidated`静态映射为cell `calibration_uncertainty_dominant`，不得观察数值后改阈值。

CDF DAG固定为`verified M4 batch/cell + prepared + raw model/calibration/template + M4 common-grid -> physical check`。只复用并核对M4 `grid_id/final_mass_edges`，不重新合并网格。`h4l-sample-efficiency-cdf-check-v1` reader须重跑M4 public reader、预测、mapping、threshold和两项指标，拒绝receipt重签、stage替换和raw report变化。

controls容器发布`capacity-control.json`与`cdf-check.json`，stage为`sample-efficiency-controls`，直接上游为prepared、freeze、training-subsets、G1/T1、M4 batch和M5 report。两文件均包含`enabled/status/cells`；disabled为`enabled=false,status=disabled,cells=[]`。科学终态仍以exit 0发布，输入/绑定失败为3、run-path失败为4、意外异常为70。

## Confirmation evaluation package与字节语法

输入必须是UTF-8无BOM、只用LF、以LF结尾且不超过64 MiB的普通非link文件；scanner与decoder始终使用同一个已打开文件句柄，并在decode前后核对文件identity、size和SHA-256。语法精确为：一行canonical header；至少两行`identity-json<TAB>`（每行TAB后为空）；唯一一行`--PAYLOAD--`；恰好一行canonical payload。禁止CR、额外TAB、重复JSON key、重复identity、超长行和额外payload行；identity必须同时含label 0与1。

header exact keys为`schema_version,dataset,source_kind,base_research_protocol_sha256,sample_efficiency_protocol_sha256,compact_freeze_artifact_id,compact_freeze_sha256,bootstrap_unit,bootstrap_replicates,bootstrap_seed,ci_algorithm,confidence_level,delta_w68,evaluation_package_id`。除`source_kind`和`evaluation_package_id`外，值全部来自已验证base/overlay/freeze并在preclaim阶段逐项比较。identity exact keys为`event_group_id,label,role,split,dataset`，role必须`assessment`。

payload exact keys为header的绑定字段，加`schema_version,population_id,compact_representation,reference_representation,canonical_event_group_order,multiplicity_plan_id,replicates,evaluation_artifact_receipts,validation_scope,payload_id`。每个replicate exact记录`index,multiplicity_digest,compact_w68,reference_w68,difference,compact_pointer,reference_pointer`；decoder重算`difference=compact_w68-reference_w68`、整个difference数组、multiplicity plan ID及payload ID。receipts必须绑定两侧model/calibration/template/grid/inference artifact与population；M6 synthetic fixture可用具名synthetic receipts验证重放。没有可由public reader验证的controlled-MC package时不得解码为科学结论，状态固定`external_pending`，正式producer和数值证据留M7。

独立性在claim前检查canonical event-group集合。config必须给出receipt-bound exclusion identity-set artifacts，覆盖freeze的discovery/browsed/excluded population IDs及M4/M5 lineage；scanner对集合做完全不相交验证，拒绝partial overlap、subset、superset或换role/split复用同组。排除artifact ID/digest进入claim key。仅比较population digest不构成独立性证明。

## Claim、attempt与判定状态机

先验证fresh output路径并exclusive-create attempt staging，写入并fsync `preclaim.json`；再以`O_CREAT|O_EXCL`创建global immutable claim，claim绑定attempt ID/output、输入SHA、population、base/overlay/freeze、排除集合receipts和全部CI参数，fsync文件及目录后才能seek同一handle并decode。claim后所有异常在已占有attempt中发布terminal manifest；进程崩溃留下的staging由reader标`postclaim_crashed`并只允许封存，不允许改设计覆盖。final rename失败保留staging和claim关联证据。

首次无claim允许执行；已有不同key永远拒绝。相同key只有显式`repeat=true`才允许新immutable attempt：成功结果可重新验证/重算，postclaim失败也只能按相同输入SHA与冻结配置重放；每次都引用同一只读claim并使用新output name。`repeat=false`、并发attempt或任何key漂移均为`assessment_already_started`。claim不追加也不覆盖。

CI对逐replicate difference使用NumPy `method="linear"`的双侧等尾percentile；estimate为均值。规则命中时，synthetic输出`synthentic_rule_satisfied`更正为`synthetic_rule_satisfied`，`validation_scope=synthetic_software_validation`；未命中为`synthetic_rule_not_satisfied`。controlled-MC在M7 authority/evaluation证据门完成前只输出`external_pending`，不得出现`confirmed_noninferior_within_registered_margin`。门完成后才允许上界`<= delta_w68`发布该科学状态，否则`noninferiority_unconfirmed`。

CLI采用互斥`--controls-only`与`--confirm`，两者均未给或同时给返回usage 2。exact tagged config包含`mode,dataset,protocol,sample_efficiency_protocol,prepared_run,compact_freeze_run,training_subsets_run,gate_run,t1_validation,batch_run,report_run,exclusion_identity_sets,confirmation_input,output_root,output_name,repeat`；controls模式要求`confirmation_input=null,repeat=false`，confirm模式要求输入路径。production root固定`neural/runs`。confirmation结果stage为`sample-efficiency-confirmation`，固定文件为`preclaim.json,confirmation.json`及run协议/manifest；绑定失败3、路径/事务4、拒绝访问5、正常科学终态0、意外异常70。

当前阶段：completed。M6代码双评审确认后的整改已落实；focused `19 passed, 111 warnings`、M1—M5回归 `105 passed, 180 warnings`、`pip check`和全量 `705 passed, 338 warnings`均通过。证据仅为Windows synthetic软件验证；正式independent controlled-MC、ARM64 authority与scientific numerical validation留M7。
