# FR-SE-01 样本效率协议与候选冻结契约

- `FR-ID`: `FR-SE-01`
- `标题`: 样本效率协议与候选冻结契约
- `所属阶段`: M1 软件契约；正式科学预注册待后续证据
- `开发顺序`: 1
- `优先级`: P0
- `前置依赖`: [开发计划](../../sw-dev/h4l-compact-kinematics-sample-efficiency-development-plan.md) §5、13、17
- `涉及包`: `src.research`、`tests/research`、`config`
- `是否属于原型阶段`: 是（仅合成软件验证）
- `来源类型`: 新需求
- `原始 SRS 章节`: `docs/sw-dev/software-requirements.md` API-03、ART-02、RES-02

## 目标

为后续事件组学习曲线提供严格、可摘要绑定的 overlay 与唯一紧凑候选契约，保持旧协议、训练、候选 key 和 assessment 守卫行为。

## 背景与问题

当前训练不识别训练子集。本次“启动开发”先交付 M1 的软件部分；M2—M7 尚未启动。研究方案未批准具体 compact、正式 draw seeds、容差来源、CI 预算及 CDF/capacity 点位。软件可以接受明确填写的注册值并拒绝遗漏，但不得替研究者选择或把合成 fixture 宣称为正式冻结。

## 影响范围

新增 `src/research/sample_efficiency_protocol.py` 与契约测试；新增明确不可运行的配置模板；登记已实现的纯 payload 契约。旧 runtime 接口不变。

## 需求描述

1. `h4l-sample-efficiency-protocol-v1` 使用严格键集合，所有嵌套字段同样拒绝未知、遗漏、错误类型、重复 JSON 键、NaN/Infinity。返回不可变 canonical bytes、SHA-256 与防御性字典副本。
2. 必须显式绑定经验证的 base ResearchProtocol、prepared artifact ID、population ID 和 compact freeze artifact ID。绑定参数没有默认值，错配以输入失败拒绝。
3. `h4l-compact-candidate-freeze-v1` 只接受一个非空且非完整 ABCD 的 canonical 组子集；表示名、组序、输入序及维数必须由现有 representation registry 重算。记录发现 prepared/report/selection artifact IDs、population 使用历史、选择规则版本、delta_w68 及来源、排除总体、探索性状态、payload 摘要。自身摘要不包含自身 digest 字段。
4. 主表示精确为 decay7、唯一 compact ID、engineered19；fraction 显式提供、严格递增且以 1.0 结束；draw seeds 非空、唯一且与网络 seeds 分开；network seeds 精确为 base 的 42—46。100% endpoint 策略必须声明单一 canonical draw。
5. 协议拥有 subset 算法（group/label/SHA-256/floor/nested）、主指标、配对键、非劣性方向/CI 算法/重采样单位和预算、评价不确定性、Q* 插值规则、capacity、CDF、assessment 与失败政策。算法 ID 白名单只表示可解析的契约，统计执行器 M5/M6 未实现；不得因此允许执行确认。
6. 无 compact freeze 抛出 `ResearchError(status="compact_candidate_not_frozen")`，exit_code=3；其余 schema/binding 失败也使用 `ResearchError`（退出码 3）。不返回结果对象或抛出 exit_code=0 的 ResearchStateError；未来 workflow 负责发布具名状态。该模块仅处理 JSON/内存元数据，不解码事件、创建 claim 或发布 run。
7. candidate freeze 的文件 receipt 与 manifest 发布由后续 workflow 负责；本次验证 payload digest 和调用方显式传入的上游身份，不声称已完成 artifact trust-chain 或总体独立性认证。
8. 配置模板使用 null 标记未决定的正式参数和绑定，由普通 loader 拒绝。完整可接受实例只放在 synthetic 测试 fixture，不提供可误作正式实验的科学默认值。

## 高层要求

遵循 neural/AGENTS.md 和上位研究方案：MC-only，不读取真实数据或历史 test，不打开 assessment，不改变旧 ResearchProtocol v1/v2/v3 digest、不改变历史训练。正式协议可以记录后续研究设计，但不会自动取得执行权限。

## 输入

显式 JSON 路径或内存 payload，以及已校验 base protocol、prepared/population 身份和 compact freeze payload/artifact ID。字段值须由调用者冻结，不接受运行时科学覆盖参数。

## 输出

纯解析/验证 API、canonical digest、候选 payload builder/reader；模板与契约文档。没有新的 CLI、run 或科学报告。

## 失败与降级

失败关闭，不补造旧模型的 subset 身份。缺少正式预注册不是采用默认值的理由；M1 科学门仍 pending，后续主批次不能启动。

## 不纳入范围

M2 子集生成、M3 模型 v2、M4 批次、M5 统计、M6 确认和 M7 ARM64/ROOT 验收；正式数据审计与候选/容差选择。

## 最小验证方式

在 neural/ 用 pytorch Conda 执行新增契约测试、既有 discriminants/workflow guards/h4l script/protocol 测试，再运行 `python -m pip check` 和完整 `python -m pytest -q`。

## 验收要点

严格递归 schema、变更摘要、错配拒绝、候选 registry 一致性、旧行为 characterization 均有可执行测试。未知/未实现 schema 拒绝；模板默认无法加载。只报告 Windows synthetic 软件证据。

## 备注

FR_DIR=`neural/docs/1-Requirement`；FR_BACKLOG_DIR=`FR_DIR/backlog`；FR_DONE_DIR=`FR_DIR/Done`；DESIGN_DIR=`neural/docs/sw-dev`；SPRINT_DIR=`neural/docs/3-Plan`；SPRINT_DONE_DIR=`SPRINT_DIR/Done`；REVIEW_DIR=`neural/docs/4-Reviews`；REVIEW_DONE_DIR=`REVIEW_DIR/Done`；WORKFLOW_STATE_PATH=unset。设计路径来自项目布局，其余是项目内的 skill fallback；不把 Sprint 放进 sw-dev。VERIFICATION_COMMANDS 来源为 neural/AGENTS.md。文档评审见 `../../4-Reviews/sprint-m1-01-review-confirm.md`，以下为确认后补齐的规范。

## v1 软件字段规范

所有表内字段必填，不允许其他字段；只有明确写 nullable 的字段可以为 null。文本为无首尾空白的非空字符串；SHA-256 为64位小写十六进制；数值拒绝 bool、非有限、错误类型；seed 为 [0, 2^32-1] 整数。数值、候选和 seed 的正式值均须调用者显式注册，以下 ID 只固定软件语义。CI、capacity、Q* 等执行器不在 M1 实现。

| 对象 | 键及类型/约束 |
|---|---|
| overlay 根 | schema_version=`h4l-sample-efficiency-protocol-v1`；protocol_id=text；base_research_protocol_sha256=sha；prepared_artifact_id/population_id/compact_candidate_freeze_artifact_id=text；compact_candidate_freeze_sha256=sha；representations=list[text]；sample_fractions=list[number]；sample_draw_seeds/network_seeds=list[seed]；其余嵌套对象如下表 |
| subset_algorithm | id=`stratified_group_sha256_prefix_v1`；unit=`event_group_id`；stratify_by=`label`；hash=`sha256`；rounding=`floor_per_label`；nesting=`shared_sorted_prefix`；full_endpoint=`single_full_identity`；min_groups_per_label=正整数；min_effective_count=正有限数。排序字节采用现有 canonical JSON 的数组 [base_protocol_digest, prepared_artifact_id, algorithm_id, draw_seed, label, event_group_id]；tie 以 group ID 字典序处理。低支持失败不重抽。 |
| primary_metric | id=`W68_Asimov_mu1_T1`；direction=`lower_is_better`；transform=`raw` |
| pairing_keys | 精确数组 [sample_fraction, sample_draw_seed_or_full, network_seed, architecture_variant]；full 为独立于任何数值 seed 的字符串身份 |
| template_policy | `batch_common_mass_grid_v1`，共享基协议合并及失败规则 |
| noninferiority | delta_w68=正有限数；delta_source=text；confidence_level=(0,1)；ci_algorithm=`paired_event_group_percentile_v1`；interval=`two_sided_equal_tailed`；bootstrap_unit=`event_group_id`；bootstrap_replicates=整数>=2；bootstrap_seed=seed；decision=`upper_ci_le_delta`。分位点为 [(1-level)/2,(1+level)/2]，线性分位插值；估计量为同一冻结 paired cell 的 W68(C)-W68(F)，对共同事件组配对重采样，不把网络种子当事件。实际 W68 重拟合/跨 cell 确认估计量仍由 M6 设计并审查，不授予执行权限。 |
| evaluation_uncertainty | method=`paired_event_group_bootstrap_v1`；role=`validation`；replicates=整数>=2；seed=seed；unit=`event_group_id`；metric=`absolute_weight_auc`。只声明固定 validation 上的配对 AUC 评价误差，不把它称作 W68 误差；后者由 T1 和后续确认设计处理。 |
| calibration_uncertainty | method=`not_estimated`；replicates=0（整数）；seed=null。本 v1 不提供外层重校准执行能力，不允许假造该误差已估计。 |
| capacity_control | enabled=bool；architecture_variant=`match_engineered19_parameter_count_v1`；width_rule=`nearest_positive_integer_ties_lower_5568_over_d_plus_67`；sample_fractions=list[number]；network_seeds=list[seed]。enabled 时 fractions 为主网格的1至2点，seeds为主网络seed非空子集；disabled 时两数组为空。固定后两层64/32，第一层宽度最近整数（同距取低），目标7937参数，不允许任意宽度。 |
| cdf_check | enabled=bool；transform=`physical`；representations=与主表示相同数组；sample_fractions=list[number]。启用时1至2点、包含1.0且为主网格子集；禁用时为空。校准规则精确继承 base，所有主 draw/network cell 保持配对，不选赢家。 |
| quality_target | enabled=bool；w68=正数或null；interpolation=`observed_monotone_linear_no_extrapolation_v1`。disabled 时w68=null；enabled时正有限数。只有观测网格包围目标且满足冻结单调规则时才可插值，不能外推；算法执行在 M5 实现。 |
| assessment_access | discovery=`forbidden`；learning_curve=`forbidden`；confirmation=`independent_population_claim_before_decode`；claim_namespace=`h4l-sample-efficiency-confirmation-v1`；repeat=`same_freeze_explicit_only` |
| failure_policy | failed_cells=`retain`；redraw=false；impute=false；missing_pair=`paired_cell_missing`；incomplete_ledger=`learning_curve_incomplete`；unknown_exception_exit_code=70（整数） |

fraction 至少两点、严格递增、在 (0,1] 且结尾1.0；draw seeds 至少一个、唯一且升序；network seeds 精确为 [42,43,44,45,46]。evaluation seed、noninferiority bootstrap seed、draw seeds 和 network seeds 数值互斥，字段含义也分离。允许减少 draw 数但不授予足够统计精度声明。

| compact freeze 根键 | 类型/约束 |
|---|---|
| schema_version/status | `h4l-compact-candidate-freeze-v1` / `frozen` |
| base_research_protocol_sha256 | SHA-256，必须等于经重新验证的 base canonical digest |
| candidate | 严格对象：representation_id=`compact:`加 canonical groups（如 compact:AB）；representation=`engineered19`；groups=ABCD顺序的非空真子集数组；ordered_inputs=registry重算数组（共同m4l在末尾）；input_dimension=重算整数 |
| reference_representation | `engineered19` |
| discovery_prepared_artifact_ids / discovery_report_artifact_ids / selection_artifact_ids | 各为非空、无重复、升序 text 数组；selection 包含所有 discovery report ID |
| discovery_population_ids / browsed_population_ids / excluded_population_ids | 各为非空、无重复、升序 text 数组；discovery ⊆ browsed ⊆ excluded |
| selection_rule_version / selection_reason | 非空 text；显式规则/理由，不从报告自动选候选 |
| evidence_status | `exploratory_only` |
| delta_w68 / delta_source | 正有限数 / 非空 text，来源不能省略 |
| payload_sha256 | SHA-256，重算除该键外全部 canonical payload；builder生成，reader严格校验 |

## 字段级交叉绑定与信任边界

`CompactCandidateFreeze(raw, base_protocol=...)` 校验所有字段和 digest；builder 只从显式 groups 生成 descriptor、schema/status/digest，其他必填元数据由调用方提供。`SampleEfficiencyProtocol(raw, base_protocol=..., prepared_artifact_id=..., population_id=..., compact_freeze=..., compact_freeze_artifact_id=...)` 同时校验结构和全部绑定，构造函数不得绕过这些检查。load API 仅在此基础上增加严格 JSON 文件读取。

overlay 和 freeze 的 base digest 均等于重新 validate 的 base canonical digest；overlay prepared/population 精确等于调用方期待值；overlay freeze artifact ID 精确等于显式传入 ID；overlay freeze SHA 等于重算的 freeze payload_sha256。两个 ID 含义不同，不以 payload SHA 冒充 manifest artifact ID。主 representations 必须精确为 [decay7, freeze.candidate.representation_id, engineered19]，compact groups/inputs/dimension 均由 registry 重算。overlay noninferiority.delta_w68/delta_source 与 freeze 数值/来源精确相等。

discovery prepared/population 不强制等于当前学习总体；M1 只记录历史集合一致性，不认证其完整性或独立性。未来 workflow 必须验证上游 manifest receipts，并把学习总体加入确认排除集合；本次不能用 payload 自摘要替代该验证。

代码评审确认后补充：overlay 即使与调用方期望值一致，也明确拒绝 freeze artifact ID 字面等于 freeze payload SHA。这仅检查已知身份混用，不能证明其他传入 ID 确为合法 manifest 身份。

## 交付状态

M1 软件范围已完成并归档；两轮双模型评审、逐项确认及接受项修复已完成。最终专项157项、全量645项测试通过，pip check通过。正式科学预注册仍pending，M2—M7未启动。详细证据与提交记录见 [Sprint M1-01](../../3-Plan/Done/sprint-m1-01.md)。
