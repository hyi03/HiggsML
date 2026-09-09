# 论文证据索引与补充实验清单

编制日期：2026-09-10。对应[正文初稿 v0.1](H4l-Thesis-Draft.md)。本文件是写作工作底稿，不是科学验证报告。

## 1 编制依据与核验范围

| 来源 | 本稿用途 |
|---|---|
| [研究方案](../research/H4l-Research-Project.md) | 科学问题、主比较、实验族、推断语义与结论边界 |
| [neural 项目规则](../../AGENTS.md) | MC-only、研究质量条件例外、角色／test 边界与验证层次 |
| [科研状态](../research/current-research-status.md) | 2026-09-09 的能力与科学缺口 |
| [研究运行手册](../sw-dev/h4l-research-runbook.md) | 阶段、证据绑定、运行与失败状态 |
| [研究协议 v2](../../config/research_protocol_v2.json) | 数值默认值、预算和未验证状态 |
| [继承的选择配置](../../config/preprocess_protocol_mass_window.yaml) | 轻子及 Z 质量选择阈值；研究另改四轻子质量窗 |
| [初期开发记录](../sw-dev/h4l-research-development.md) | 合成链路和历史测试的背景 |
| [v2 修订验证记录](../sw-dev/h4l-review-revision-2026-09-09.md) | 105／499 项历史测试及最终增量复核的准确范围 |

阅读代码的 Git HEAD 为 `3bac339283805cdf13ff479c7462b9518ce8106d`，写作开始前 `git status --short` 为空。本次用代码图工具定位主要函数，再核对当前源码；对索引行界与当前文件不一致的段落补读源文件。没有把代码图中的旧行号写成固定论文证据，也没有修改研究实现或协议。

本次未读取 ROOT、events payload、真实数据或 held-out test；未运行训练、MC 先导、Toy 或完整软件回归；未独立核验历史测试 XML、MELA 后端或外部文献。正文所述“当前缺少论文主结果”依据仓库科研状态及验证记录，不是通过重新打开所有历史 run 得出的结论。若另有未纳入仓库状态的冻结实验，须先验证其身份与适用范围再补入。

## 2 正文—实现对应

| 正文主题 | 已核对实现入口 | 写作口径与限制 |
|---|---|---|
| §2 development-only 导出 | [data.py](../../src/research/data.py)：`export_research_data` | 先读身份，跳过 test 后才请求轻子字段；不声称存储层从未读混合 basket |
| §2 五角色与产额校正 | [data.py](../../src/research/data.py)：`role_for_group`、`assign_roles`、`validate_role_isolation` | 固定组哈希；yield_weight=physical_weight/(0.8r)；事件身份不是模型特征 |
| §2 有效统计与 G0 | [data.py](../../src/research/data.py)：`grouped_statistics`、`audit_g0` | sumw² 为组内求和后的平方和；G0 不使用 assessment、不证明来源验证 |
| §3 有序表示 | [representations.py](../../src/research/representations.py)：`representation_features` | A/B/C/D 固定顺序；m4l 最后追加；主表示实际为 8／20 维 |
| §4 网络与 checkpoint | [discriminants.py](../../src/research/discriminants.py)：`ResearchClassifier`、`train_discriminant` | 未加权 train scaler、类内均值归一绝对权重、普通早停／固定 epoch200 分开 |
| §4 对抗强度与诊断 | [discriminants.py](../../src/research/discriminants.py)：`effective_lambda`、`_diagnostics` | λ 通过梯度反转；复合 loss 不是纯分类目标；验证诊断不选择模型 |
| §4 外部 ME | [matrix_element.py](../../src/research/matrix_element.py)：`export_me_inputs`、`import_me_results`；[MELA 契约](../research/mela-adapter-contract.md) | 外部 adapter、概率语义和独立参考必须绑定；接口不等于物理计算通过 |
| §4 CDF | [calibration.py](../../src/research/calibration.py)：`_moments`、`constrained_distribution`、`fit_calibration`、`apply_calibration` | 有限网格约束估计，不保证严格可逆；跨箱相关性不支持时拒绝 |
| §4 类别阈值 | [calibration.py](../../src/research/calibration.py)：`fit_thresholds`、`assign_categories` | 物理背景拟合中位数；阈值处进入高类别；M5-abs 的最终模板仍为 signed |
| §5 共同模板与 G1 | [templates.py](../../src/research/templates.py)：`build_templates`、`common_mass_grid`、`gate_g1` | 共同合箱；实际协方差检查；空箱与结构零分别处理 |
| §5 T0/T1 与区间 | [inference.py](../../src/research/inference.py)：`build_model`、`profile_interval`、`run_asimov` | pyhf 0.7.6／64 位；shapesys 独立箱近似；搜索上限不是置信上限 |
| §5 Toy 生成 | [inference.py](../../src/research/inference.py)：`run_toys`、`paired_event_toys`；[assessment.py](../../src/research/assessment.py)：`infer_assessment` | 单模板 Toy 与共同联合单元配对路径分开；母模板非负性先检查 |
| §5 带符号 μ | [diagnostics.py](../../src/research/diagnostics.py)：`signed_mu_fit`、`signed_mu_summary` | 固定模板 T0 点估计；不是 T1 剖面诊断，不提供校准区间 |
| §5 覆盖及 pull | [reporting.py](../../src/research/reporting.py)：`coverage_summary`、`paired_coverage_error`、`fit_diagnostics` | 失败留在预算；Wilson 区间针对成功且覆盖比例；pull 使用区间半宽 |
| §5 重复校准 | [assessment.py](../../src/research/assessment.py)：`run_assessment_t2`；[calibration.py](../../src/research/calibration.py)：`bootstrap_calibration` | 同一新映射应用于 template 与共同母事件；不在副本内重新选质量网格 |
| §5 压力场景 | [inference.py](../../src/research/inference.py)：`stress_weights`；[stress.py](../../src/research/stress.py) | 固定共同参考 M3:42；人工 ±10%；modeled／omitted 分开 |
| §5／6 主汇总 | [reporting.py](../../src/research/reporting.py)：`main_comparison` | 只接受五对有效 T1、μ=1、model_self_asimov；缺失则中位数为 null |
| §5／6 精确归因 | [reporting.py](../../src/research/reporting.py)：`exact_shapley` | 输入同族全部 16 个值；逐种子效率校验；调用工具存在不等于完成实验 |
| 全文复现身份 | [artifacts.py](../../src/research/artifacts.py)、[workflow.py](../../src/research/workflow.py)、[CLI](../../src/cli/research.py) | 上游／协议／模型／映射摘要、不可覆盖 run 与冻结 assessment 守卫 |

## 3 不能被正文省略的实现差别

1. **软件默认协议与物理协议。** `protocol_scope=synthetic_software_defaults_not_physics_validation`，`inference.validation_status=unvalidated`。N_eff=20、ρ=0.2、5 GeV／1 GeV 网格及 20×100 外层／内层预算均不是已经证明适用于真实 MC 的数值选择。
2. **CDF 的零格与物理结构零。** 约束估计器把零方差零产额格保持为零，这只是其有限直方图约定；模板构造对结构零要求额外证据。正文不能把二者写成已证明的物理支持域。
3. **等产额目标与严格等分。** `fit_thresholds` 对物理产额的约束分布估计取中位数；有限样本、离散网格及 ties 使实际两类别产额不必严格相等。CDF 输出阈值也不应自动写死成 0.5。
4. **训练归一化。** scaler 使用 train 未加权均值和总体标准差；分类权重按类别的绝对权重均值归一，不是两类总权重各为 1。对抗 CE 的背景权重和分母与分类 BCE 的行数分母不同。
5. **区间与诊断。** 物理区间的 μ≥0、默认搜索上限 20；带符号诊断另用 [-20,20] 与正率域交集。Toy 覆盖检查未实现临界值校准，signed μ 不包括 T1 nuisance 剖面。
6. **覆盖失败语义。** 所有区间有效才发布普通覆盖；存在失败则保留 `coverage_incomplete`，报告成功且覆盖比例及 Wilson 区间。当前 pull 为偏差除以区间半宽，不能改写成按偏差选择的一侧误差。
7. **配对来源。** assessment 的主观测计数来自共同联合单元。模板统计辅助 Poisson 使用候选专属流；不能声称所有辅助涨落也来自同一次模板事件 bootstrap。物理源之间的额外相关性需另行验证。
8. **G1 与扩展。** 源码及运行手册对 G1 证据与输入总体进行绑定，尤其 M5-abs 在校准 payload 解码前检查门槛。该守卫是访问控制，不是 G1 已经通过。
9. **归因／网格实验的完成程度。** 分组表示、精确 Shapley 函数、共同合箱能力已经存在；完整 15 子集训练和空集、B 拆分的全流程、预注册多网格稳定性实验仍需组织并运行。不能将辅助函数当成已完成结果。
10. **软件报告状态。** 当前 `build_report` 保留 `scientific_results_obtained=False` 和后续实验注册提示。发表时不能只依据 `software_report` 或 `trained` 字段宣称科学结论，必须追踪实际推断与外部验证证据。

## 4 图表交付设计

以下为图表规格，不包含虚构结果图。所有正式实验图应显示 dataset、协议／冻结身份、种子、误差层和生成来源，并能追溯到原始产物。

| 图号 | 建议图题与内容 | 所需证据 | 正文位置 |
|---|---|---|---|
| 图 1 | 五角色与模型—校准—模板—冻结评估流程；标出各拟合来源 | 冻结协议、角色与上游身份；可先制作方法示意图 | §2 |
| 图 2 | M6／M3-fixed200 逐轮 BCE、CE、λ、AUC 与质量诊断；标记 warm-up／ramp／epoch200 | 同种子和分组的模型 history；已有 learning-curves 产物 | §4.3 |
| 图 3 | 原始分数、物理 CDF 与 absolute CDF 的背景接受率随质量变化 | 独立 template；校准 correction、mapping_id、权重定义 | §4.5／6.2 |
| 图 4 | M0／M0c／主方法的共同粗细网格诊断 | 预注册多网格实验族、共同样本及有效统计；不是单次合箱记录 | §5.1／6.3 |
| 图 5 | 主图：五个配对种子的 M4／M5 T1 Asimov W68 和 R_s | 十个有效主结果；共同总体、网格及 T1 证据；完整失败记录 | §6.3 |
| 图 6 | μ=0、1、2 的偏差、68%／95% 覆盖及失败率 | model-self／assessment 分开展示，预算、Wilson 区间与 pairing_id | §6.4 |
| 图 7 | T2-procedure 外层 W68 散布与副本失败率 | 每个副本的映射、同步变换证据、20×100 预算和随机化范围 | §6.4 |
| 图 8 | 四组贡献及二阶差分 | 同一实验族全部16个值、逐种子效率残差、事件组配对误差 | §6.5 |
| 图 9 | modeled／omitted 人工扰动中的增益、偏差与覆盖 | 同一 M3:42 参考、扰动端点、辅助模型；明确标 S | §6.4／7 |
| 图 10 | 外部变化下的增益保留 | 新 MC／理论／探测器来源与相关性证据；明确标 P | §7.3 |

图 8–10 可以在主比较之后完成。缺少相应实验时不绘制平滑示意曲线冒充结果；若方法流程图使用示意数据，必须单独标识且不进入性能讨论。

## 5 数值结果的最小溯源字段

主表每行至少保存：dataset、源样本及 prepared 身份、protocol_sha256、代码 commit／dirty、软件环境、candidate_id、网络 seed、selected_epoch、target/effective_lambda、ordered_inputs、model_id、mapping_id、threshold_id、模板身份、共同 mass_edges、layer、T1 evidence_id、expectation_kind、μ 注入值、置信水平、区间上下端／宽度、失败状态。

Toy／assessment 再保存 freeze_id、母事件／母模板身份、pairing_id、Toy 随机种子与预算、辅助测量是否重生成、覆盖／失败数量及边界计数。T2 还需外层重采样范围、重数、副本 mapping_id 和各副本终态。Shapley 还需 family_id、所有子集和空集来源、逐种子效率残差及配对误差的重建范围。

表 4 中的主改善率应复用 `main_comparison` 的完整性语义，手工转录也必须核对相同结果选择条件。中位数之外的置信区间须注明估计方法；不能用五个种子的最小值／最大值冒充置信限。

## 6 补写顺序与结论条件

| 顺序 | 缺失工作 | 能解锁的正文 |
|---:|---|---|
| 1 | 来源物理定义、重建参考、历史反馈与事件独立性审计 | 数据章节与输入证据表 |
| 2 | 实际 2e2μ 导出、G0、最小模型／CDF／模板及 signed-MC T1 验证 | 样本支持、网格与校准结果；G1 结论 |
| 3 | 完整候选扩展、配对种子、MELA 独立参考、全局冻结 | 主模型比较和外部物理基线 |
| 4 | 五种子主 Asimov、seed42 预定覆盖、带符号诊断 | 主结果、可靠性与有限 MC 结论 |
| 5 | T2、S、L1、完整归因与网格诊断 | 增益来源与受限解释 |
| 6 | 未参与选择的新事件、有来源系统变化及其验证 | 物理稳健性结论及是否恢复“稳健”题目 |
| 7 | 核验文献、补足准确数据／MELA／统计参考及署名 | 可投稿版本的书目、致谢和复现附件 |

“预期区间更窄”要求完整有效的预指定比较；“覆盖可靠”还要求预注册容差、足够预算、失败处理和适当的独立验证；“新增产生信息”另需质量利用与表示对照；“对物理系统误差稳健”必须有 P 层来源与响应模型。没有任何单一 AUC、KS、测试通过数量或 Asimov 宽度能够同时支持这些结论。

若关键门槛失败，保留各候选终态，将结论改写为统计支持或模型适用性受限。只有数据来源、窗口或规则发生实质变化时才建立新的科学协议；不能为了改善论文数值修改冻结产物。本文档的待办不构成启动训练、开启 assessment 或 test 的新授权。
