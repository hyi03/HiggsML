# 科研质量审查：逐项确认与解决方案分析

日期：2026-09-23。分析基线：`5275fc586ec25d41e84459e665c168dba6a31671`。

**结论：优先补齐“证据版本一致 → 统计区间可靠 → 比较设计有效”这条链，再决定是否扩大物理基线和样本规模。联合支持阈值方法已经实现；重新实现它、增加网络数量或直接增加 Toy 数量，都不是当前问题的通用解法。**

推荐近期将工作收敛为“有限 signed-MC 下特征组合的流程级归因及适用边界”。如果最终仍要主张“在利用质量峰之后，紧凑输入可靠地改善信号强度推断”，则需要另一套预先注册、具有质量形状基线和独立确认资源的实验。两条路线可以共用软件和验证工具，但不能共用一个被追溯赋予确认性身份的结果。

本文是解决方案分析，方案、建议阈值和实验矩阵均未自动成为注册协议。本次只新增本文；未修改科研代码、协议、原审查报告或稿件，未启动训练、正式 bootstrap、Toy、assessment 或 T2。

## 1. 输入、核查范围与当前状态

主要输入：

- [科研质量与投稿成熟度审查报告](research-quality-audit-2026-09-23.md)，包含 F2 更正。
- [项目 README](../../README.md)、[文档入口](../README.md)、[研究设计](../research-design.md)、[方法与评估](../methods-and-evaluation.md)、[数据与处理](../data-and-processing.md)、[复现实验手册](../implementation-and-reproduction.md)。
- [核心协议](../../config/protocols/h4l_protocol.json)、[联合支持配置](../../config/protocols/h4l_off_joint_support_v1.json)、[样本效率协议模板](../../config/protocols/sample_efficiency_v1.json)。
- [联合支持实现验证记录](../changes/h4l-off-joint-support-v1/verification.md)、当前实现、论文中英文对应段落、随稿来源清单和已发布的 Stage B 完成度。
- SciSpace 定向检索的题名、摘要和元数据；六篇相关论文的书目信息另用 Crossref 核对。文献用途和限制见第 10 节。

核查所得：

1. `_profile_from_fit` 仍使用 `chi2.ppf(confidence, 1)`；T1 仍将 signed 模板的一、二阶矩交给 `shapesys`。这支持 F3 的验证需求，但并不直接证明某个候选已经显著欠覆盖。
2. `_automated_validations` 确实自动填写 P0/T1 的 `validated`，引用标为 `automated-not-independent`；`_p0_audit` 检查引用存在及绑定后设置 `physics_sources_validated=True`。F4 是状态语义与科学证据不匹配。
3. `select_joint_threshold` 已实现两角色支持检查、19 个候选、固定排序及无可行阈值失败。开发记录为 200/200 支持通过、131 次非中位数选择、75 个名义中位数，且明确 `inference_run=false`。本次读取记录，未重新执行或重新验证其全部上游哈希。
4. `runs/h4l-off-test03/report-B/evaluation_completeness.csv` 的 36 个单元均为 `not_run`。这是该已发布 Stage B 报告的状态，**不能据此判定后台正式计算当前没有运行**；本次没有检查后台执行状态或搜索全部未发布产物。
5. 随稿 provenance 登记的 14 个旧来源路径当前均不存在。英文正文的“不报告覆盖率”段落、中文架构遗漏、证据 README 的执行版本混写和导出器硬编码均可在当前文件中核实。
6. 本次没有重跑审查报告中的测试，没有打开 ROOT、事件载荷或新的 assessment。图谱已存在；图谱没有返回部分脚本和角变量实现时，才回退读取报告指定的文件。

## 2. 逐项确认

`Accept` 表示问题或更正有依据，应纳入后续工作；不表示本次已修复。`Partial` 表示诊断成立，但解决范围取决于论文主张。严重性以“支持可靠精度增益主张”为参照。

| 编号 | 严重性 | 类型 | 审查来源与问题 | 决定 | 主要依据 | 解决动作与验收标准 |
|---|---|---|---|---|---|---|
| F1 | High | Requirement | 单质量箱弱化质量基线 | Accept | 当前联合支持配置固定 `[105,140]`；审查列出实际冻结网格 | 近期明确为计数分类研究；强主张另建可解析质量峰的共同基线及质量控制。新网格不得反写旧分析，见第 6 节。 |
| F2 | High | Consistency | 旧失败已处理，新方法正式证据待完成 | Accept | `joint_support.py::select_joint_threshold`、开发 verification 及复现手册 | 接受报告更正，不再列为未实现修复。检查新运行全链完成率、区间、阈值频率和失败原因；200/200 开发支持不能替代正式结果，见第 4 节。 |
| F3a | High | Correctness | 低计数与物理边界下渐近区间未独立验证 | Accept | `likelihood.py::_profile_from_fit`；核心协议的 500-Toy 设置 | 先建一、二计数箱的独立枚举参考，再校准及独立检验区间；比较同一可靠性要求下的宽度，见第 5 节。 |
| F3b | High | Correctness | signed-MC 的矩匹配不保证 T1 生成模型成立 | Accept | `likelihood.py::build_model`；方法文档的 T1 假设 | 建已知真值、保留组相关的 signed 权重重复生成基准；检查固定阈值和重新选阈值两种程序。只有通过适用域验证才允许提升科学资格。 |
| F4 | High | Consistency | 自动 `validated` 强于实际证据 | Accept | `scripts/h4l_prepare.py::_automated_validations`；`workflow.py::_p0_audit` | 区分契约检查、自审、独立数值验证和物理来源确认；新 schema/gate 不得仅凭非空引用授予独立资格，保留旧产物原语义，见第 3 节。 |
| F5 | High | Risk | BC/AC 和 105 对比较存在探索选择 | Accept | 研究设计明确 BC/AC 为探索候选；同 MC 五种子不是独立数据 | 预先冻结一个主比较，或明确少量比较的错误率安排；确认资源必须有可核实的未使用历史。无独立资源则保留探索定位，见第 7 节。 |
| F6a | High | Correctness | 样本过程、归一化、角约定和修正来源不足 | Accept | `dataset_science_v1.json`、profile、数据文档；MELA 背景设置不等于 DSID 组成 | 建 DSID 级来源表与独立数值参考；逐项说明有效截面是否已含修正，避免双计数。发现物理定义错误则沿受影响链重跑。 |
| F6b | High | Requirement | 理论/探测器/组成变化不足 | Partial | 协议将 ±10% 标为 artificial stress；项目允许窄 MC 方法研究 | 对所声称的适用范围补有来源的变化和选择迁移；窄方法研究不必假装完整实验系统误差，但仍需多场景统计及机制验证。 |
| F7 | High | Requirement | 基线和可迁移贡献不足 | Accept | MEKD、INFERNO 已覆盖相关基础；当前文档承认 MELA 未独立验证 | 以研究问题选择最小有辨识力的基线；方法贡献应来自可检验机制和适用边界，不能仅来自组合软件。无需恢复 XGBoost 或堆叠网络，见第 6 节。 |
| F8 | High | Correctness | 人工 CRN 被误读为物理联合配对的风险 | Accept | 方法文档及当前完成度均声明 `physical_event_pairing=False` | 保留边缘结果；用注册的独立分配敏感性检查计算误差；若要物理配对结论，另建合法联合事件/联合格点模型，见第 8 节。 |
| F9a | Medium | Risk | D 的负贡献机制未分离 | Accept | `angular5.py::build_angular5`、MLP 架构、两类模板流程 | 顺序检查角定义、周期编码、容量/收敛、支持/分箱和训练规模。每一步有独立假设及失败记录，避免全组合搜索，见第 8 节。 |
| F9b | Medium | Documentation | 中文架构漏第二个 Dropout 和第三个 LayerNorm | Accept | `ResearchClassifier.__init__` 与中文稿 3.2 不一致 | 根据实际执行 revision 的架构及模型配置修正文稿；不得仅依据当前代码改写历史运行描述。无需因此重训。 |
| F10 | Medium | Requirement | 紧凑输入被扩大为样本效率/普遍最优 | Partial | 样本效率 overlay 多项为 null，且已有 study 是 mass-on 独立族 | 近期删除超范围推论；若保留样本效率主张，另行注册学习曲线、W68 不确定度和非劣容差。不能直接把 off-only BC 填入现有 mass-on 研究，见第 8 节。 |
| F11a | High | Consistency | 中文、英文、快照和 test03 状态混用 | Accept | 英文正文覆盖率段落、随稿 README、审查列出的三版本 | 建一张版本/指标/来源/资格矩阵，正文和表格从同一指定快照生成；历史覆盖数值注明来源可核验程度，不删数值掩盖冲突。 |
| F11b | High | Maintainability | 原来源缺失，无法完整重验谱系 | Accept | 本次核查 provenance 的 14 个路径均缺失 | 优先恢复原字节并验哈希；无法恢复则显式记为历史汇总并独立归档新结果，不能用数值相同的新文件替换旧来源。 |
| F11c | High | Maintainability | 导出路径、准备目录和结果状态硬编码 | Accept | `paper/scripts/collect_evidence.py::main` | 改为显式证据入口并沿 manifest/freeze 解析谱系，支持 Stage B 与 final 的真实状态；去掉“bootstrap 必须不完整/access 必须非独立”等历史假设，保留身份核验。 |
| F12a | Medium | Test | Windows 长临时路径导致一项测试失败 | Accept | 原报告记录默认路径失败、短路径单项通过；本次未重跑 | 用独立短临时根完成当前 revision 的全套验证并记录平台；若承诺支持普通长路径，再修路径处理。不得将单项重跑写成全套通过。 |
| F12b | High | Clarity | 软件、发布完成度与科学资格混淆 | Accept | 核心协议仍标 synthetic defaults；test03 科学状态未完成 | 报告分别列软件测试、产物发布、正式计算、独立验证和主张资格，资格由证据逐项决定，不能由文件存在或测试数推导。 |

没有需要整条拒绝的 F 编号；需要限制的是某些修复的适用范围及由现象引出的强推论。

## 3. 第一优先级：修正证据与资格语义

这部分投入小、依赖少，并能避免后续实验继续积累难以解释的证据。

**证据对齐。** 为每个分析登记 `code_revision`、执行 revision、protocol/method digest、prepared/model/freeze/report ID、结果文件哈希、访问历史和证据级别。至少区分旧 test01 汇总、test03 Stage B、新 joint-support 正式产物。论文引用哪份证据应显式选择，不应自动取最近修改目录。执行版本不同可以合理，但必须分别绑定。

**来源恢复。** 先寻找可合法恢复的原产物并逐文件核验；若旧源找不回，保留快照为“历史已发布汇总，本次仅可验内部一致性”。新运行即使数值相同也只能成为新的证据。科研归档可独立于 Git 保存生成产物、receipt、环境和许可证；无需违反仓库禁止提交运行产物的规则。

**导出器。** 建议由一个显式 report/证据清单入口解析上游；Stage B 不存在正式区间时，应输出真实缺失状态。最终报告有合法区间时，应正常导出。验收应覆盖：带名 prepare、旧完整报告、Stage B、完整/失败 bootstrap、不同 access 资格、上游缺失和哈希不匹配。跨版本对接需明确兼容契约，不能只取消断言。

**资格状态。** 推荐在新版本证据契约中表达下列独立维度，而非一个含义过强的布尔值：

| 维度 | 自动程序可确认什么 | 还需要什么 |
|---|---|---|
| contract_checked | schema、版本、身份和引用文件绑定一致 | 不证明科学正确性 |
| source_audited | 样本与物理定义的来源审核材料齐全且结论明确 | 必须有可追溯的来源及审核范围 |
| independent_numerical_validation | 独立实现/生成模型下的对照记录满足冻结标准 | 不允许生产实现复制自身结果作为参考 |
| physical_applicability | 数值验证覆盖绑定样本和拟声称的条件 | 不能由合成测试自动升级 |
| confirmatory_eligibility | 选择历史、population、freeze 和访问条件均满足确认设计 | 单人 self-review 或新 run 名称不创造独立性 |

这些是建议语义，字段名需经后续设计确定。探索性执行可以在明确标注的契约下继续；正式科学资格必须 fail-closed。旧 `validated` 记录不能原地改写；需要新版本解释/派生记录及绑定。单纯修状态文案不要求重算事件，但若改变了下游证据合同，必须重新发布受影响的审计、freeze/资格产物，不能静默继承。

## 4. 联合支持方法：下一步是正式证据和方法适用性

现有方法按 `(abs(k-10), k)` 选择最接近中位数的可行阈值，不直接最小化 W68；这降低了针对精度指标调参的自由度。但是它使用 template 支持来选择阈值，最终类别及其统计性质仍依赖有限 MC，不能据此免除选择后验证。

建议先完成或读取已授权的新方法正式链路，收集四类结果：

1. **可执行性：** 全计划分母、支持失败、拟合失败、无界区间分别记录；报告最弱过程/类别、阈值选择频率及距支持门槛的余量。
2. **有限 MC 稳定性：** 新的 calibration/template 组级 bootstrap，每个副本重新选择阈值、重建模板、推断及归因；按当前契约完整 200/200 才提供正式百分位区间。即使如此，区间仍只对应固定网络的该重采样程序。
3. **条件可靠性：** 固定名义模板/阈值的 model-self，以及符合访问历史条件的 assessment；逐种子报告覆盖、偏差、失败，而不是只给五种子中位数。
4. **程序可靠性：** T2 当前只重采 calibration、固定 template；它不能回答 template 参与选阈值后的完整重复实验覆盖。第 5 节的独立外层基准要同时重生 calibration/template，并在每次外层重做选择。

对纯阈值方法更新，绑定未变且审计通过的 prepared 和 75 个冻结模型可以复用；Stage B 及之后应在新根目录重新建立。若正式支持仍失败，先定位局部原因，再决定增加 MC、改变分辨率或停止该范围；失败本身不能触发未注册的补抽、放宽门槛或候选删除。

本次只确认已发布记录，不承诺新方法必然完成 200/200，也不根据旧 39/200 判定它仍失败。

## 5. 核心统计方案：把区间验证拆成三个层次

### 5.1 层 A：低计数与边界的独立参考

以当前报告给出的约 `s=2.7683、b=2.4979` 作为一个代表性参考点，并预先注册附近信号强度、信背比和总计数网格。第一步使用**固定已知模板的 T0**，对一个计数箱、再对两个类别，枚举整数 Poisson 观测并计算其概率。尾部截断须有误差上界；不能只扫描有限 n 后宣称精确覆盖。

使用独立实现的 Neyman 构造/似然比排序作为参考，比较当前 chi-square 临界值区间的实际覆盖、端点、边界行为和宽度。Feldman–Cousins 的思想适合作为小计数参照 [R1]；它并不自动解决本项目所有有限 MC nuisance。

这一步无需新增 H4l 物理 MC，就能隔离“观测计数约五个”带来的问题。若它已显示明显失配，应先解决区间构造，再投入大规模特征比较。

### 5.2 层 B：T1 和 signed 权重的生成模型验证

当前近似用 `y=sum(w)`、组级方差 V 构造 `tau=y²/V`。一、二阶矩匹配不保证抵消、偏态和稀疏尾部被正确描述。Barlow–Beeston、加权模板近似及 compound-Poisson 文献为构造参照提供背景 [R2–R4]，不能直接作为任意 signed-MC 的认证。

建议构造有已知物理真值的独立基准：先固定非负的真实信号/背景强度，再生成其有限 MC 估计。设置无负权、温和抵消、接近支持边界、长尾权重及组内相关等情景。生成机制可采用有明确假设的带标记 Poisson/固定样本数构造；正负分量若相关，必须按共同物理组生成，不能一律假定两个独立 Poisson。数据计数始终来自非负真值，绝不从 signed 权重直接抽概率。

每个情景比较：已知真值参考、当前 T1，以及经推导和独立实现的候选有限 MC 模型。正负分量模型可作为研究候选，但在总率非负、相关结构和 nuisance 可辨识性未经验证前，不能直接替换 `shapesys`。同一 pyhf 模型生成再拟合保留为内部闭合测试，单独不能通过本层。

最小诊断包括逐情景/逐种子的偏差、估计分布、明确分母约定的 pull、68%/95% 覆盖区间、拟合及无界失败率、宽度分布。边界处分布不应机械要求高斯或零偏差；应与独立参考比较。不能只报告成功拟合者的覆盖而隐藏失败。

### 5.3 层 C：选择程序的覆盖与比较

注册两条独立随机流：一条用于区间临界值/方法开发，另一条仅用于最终验证。每次外层重新生成或按已知机制独立获得 calibration/template，然后重做联合阈值选择及建模；内层生成观测并求区间。若主张固定网络的程序性能，模型可以固定；若主张整个学习程序的可靠性，还须加入训练样本及重训练随机性，并单独报告成本和估计目标。

在存在 nuisance 时，按拟合点 plug-in 校准的 Toy 只给点位/条件证据。应冻结 nuisance 验证网格，或采用覆盖其取值范围的构造；如果采用 nuisance 上的最坏情形临界值或投影，需要评估保守性与计算成本。不得宣称一次名义校准保证整个参数空间覆盖。

**指标也必须更新。** 原来的 `W68_Asimov` 继续作为原分析的名义描述。离散 confidence belt 定义在整数计数观测上，不能未经定义就在非整数 Asimov 计数上读取同一个“校准宽度”。新实验建议预先选定 Toy 期望宽度 `E[U-L]` 或中位宽度作为主要精度指标，同时报告另一项和失败/无界情况；无界结果不得通过删除来制造有限均值。

比较应采用相同区间构造和可靠性规则。例如预注册 `C_L(mu,scenario) >= 1-alpha-epsilon_cov`，其中 C_L 是考虑设计及多重情景后的覆盖下界；同时规定失败率上界。`epsilon_cov`、允许的保守性和实用精度差异必须来自拟定用途，不能看过当前 0.634/0.668 后反推。更窄但未通过覆盖要求的模型不能作为可靠精度赢家。

**预算量级。** 单个独立二项覆盖估计，近似 95% 半宽 h 所需 `N≈1.96² p(1-p)/h²`。p=0.68 时，h=0.01 约需 8,360 次，h=0.02 约需 2,090 次；这只是条件覆盖估计的规划量级，不是功效计算或同时覆盖保证。500 次的半宽约 4.1 个百分点，难以精确区分几个百分点差异。T2 的外层聚类会改变有效信息量，应增加独立外层并按外层计算不确定度，不能把 20×100 当作 2,000 个独立全流程样本。

为控制成本，先做层 A 和少数代表性 signed 情景；发现结构性问题即回到方法设计。方法冻结后才投入较大、独立的验证预算。验证用有限情景通过只支持所覆盖适用域。

## 6. F1/F6/F7：恢复研究问题所需的最小物理基线

### 6.1 两种可选择的论文路线

| 路线 | 可提出的核心问题 | 必须补齐 | 不能据此声称 |
|---|---|---|---|
| A：有限 MC 流程归因 | 支持约束、表示和阈值程序如何影响区间及归因的稳定性？ | 一致证据、独立统计参照、完整新方法结果、至少一组能区分机制的受控实验 | 超越精细质量谱、普遍最优特征、已确认物理灵敏度提升 |
| B：可靠紧凑推断 | 利用质量峰后，紧凑表示能否在相同覆盖要求下保留或改善精度？ | 路线 A 的正确性基础，加可解析质量形状、质量控制、物理判别参考、独立确认和声称范围内的变化 | 完整实验测量、未经验证的跨生成器/探测器泛化 |

路线 A 更接近当前资源，但“流程完整”或“开发支持从 161/200 变为 200/200”本身仍不充分构成方法创新。需要展示可复核的失败机制、预测适用边界，并说明这些规律在哪些新情景成立；结果阴性或不确定也应保留。

### 6.2 路线 B 的基线顺序

1. **B0：质量形状。** 采用能解析信号峰的共同质量模型。优先在合法 development/template 范围内做支持可行性研究；若直方图支持不足，可研究有独立验证及形状不确定度的参数化/半参数化质量模型。平滑不能创造 MC 信息，模型偏差必须进入验证。
2. **B1：质量 + 冻结运动学分数。** 与 B0 使用同一质量模型、选择、产额、支持标准及 nuisance 处理；BC/AC/ABCD 的差异只通过已声明的分数分类进入。
3. **质量控制。** 比较显式质量 on/off，并用共同质量网格细化和 mass-only classifier 控制有限质量箱内的残留质量信息。`off` 不等于条件独立；条件 CDF/去相关策略也需要自己的有限样本校验。
4. **B2：质量 + 经校验的矩阵元判别。** MELA/MEKD 提供有物理解释的基线 [R5]。确认角、单位、Z 排序和概率定义；不能把仓库 round-trip 当独立参考。当前 adapter 的 qqZZ 背景假设必须与真实 DSID 组成核对，否则只能报告特定假设下的基线，不能叫完整背景最优判别。
5. **B3：推断目标训练，按主张选做。** 若论文声称学习方法优越，再加入一个明确的 inference-aware 基线，例如 INFERNO 类目标 [R6]，匹配训练机会和 nuisance 信息。它优化的近似目标也须通过最终低计数覆盖验证，不保证自动胜出。

共同网格若因全部 15 联盟中的最弱模型被迫合成单箱，说明“完整联盟归因”与“最佳质量分辨率比较”可能是两个不同实验族。可以新注册一个只含主候选/完整输入/物理基线的确认族，冻结其共同模型；不能在旧 Shapley 族中删除失败联盟后继续声称原来的完整归因。

物理来源审核至少应列 DSID、生成器/版本、阶数、PDF/淋浴、生成过滤、有效截面定义、负权来源、FSR、探测器和事件修正。当前 profile 未列出效率修正不证明它们一定缺失或未被吸收；应查来源后决定。如果权重、重建或选择被修正，必须评估 prepare、训练和全部推断的失效范围。

## 7. F5：用明确的确认对象解决选择偏差

建议将 BC 作为一个**待冻结**的主要紧凑候选，理由是它是已有探索提出的六输入候选；AC 可保留为次要分析。该建议不把 BC 追溯变成预注册候选，也不表示它已被证明最优。若目标同时确认 BC 和 AC，需预先定义少量假设的错误率安排，例如适用条件下的 Holm 调整。105 对比较继续作为完整探索表，不能仅展示赢家。

优先考虑“覆盖合格条件下的非劣性”作为紧凑性的确认问题。令 D 为已冻结的宽度指标的紧凑模型减完整模型差异，注册科学可接受容差 delta；只有有效上置信限不超过 delta 才支持非劣。若要宣称有实际意义的优势，则要求对应置信界超过预设最小改善。不能把当前约 1.3%–1.4% 的优势反过来当作容差依据。

确认资源按以下顺序判断：

1. 利用现有 metadata、population/access ledger 审核是否有确未用于选择的 MC；不要为判断资格而先读取其评估值。还需审核同组重复、跨 release 重叠和历史 basket 解释问题。
2. 如有合格资源，可确认冻结模型在同一模拟分布中的比较；这不自动证明整个训练算法跨 MC 的优势。
3. 如没有，则需要新增独立 MC 批次或维持探索定位。新网络 seed、重新分角色、嵌套交叉验证或新增 Toy 都不能清除既往全局设计反馈。
4. 嵌套验证对一个预先固定的新选择程序有开发价值，但所有预处理、候选选择和校准都须在外层内部重做。它不能把已经看过全池结果的这次分析重新标为独立确认。

五种子应继续报告配对结果，但它们共享 MC。关于 MC 泛化的区间应来自正确的物理组/独立模拟单位；关于训练随机性的区间另报，不能把种子作为五份独立物理样本。

## 8. F8/F9/F10：机制实验与扩展，按信息价值排序

**CRN。** 先区分三个目标：名义 Asimov 宽度、单候选边缘覆盖、两候选物理联合差值分布。人工 CRN 不改变前两者的理论定义；它改变后者的耦合和 Monte Carlo 估计方差。完成独立分配敏感性可以说明结果对耦合的敏感程度，不能赋予任一耦合真实事件解释。

如确需物理配对，构造所有候选对同一物理事件的联合分类，并验证联合格点的每个过程强度非负且重现各候选边缘。在 signed-MC 下边缘合法不保证联合格点合法；不能裁负、取绝对值、用同一个随机种子冒充解决。构造失败时可保留非配对比较及明确的 Monte Carlo 积分误差，放弃无法支撑的物理配对主张。

**D 组机制。** 建议分步做以下对照，前一步不通过先解决前一步：

| 顺序 | 对照 | 支持什么解释 | 不能单独说明什么 |
|---|---|---|---|
| D1 | 约定对齐的独立四矢量/角参考；电荷、Z 排序、周期边界和退化几何测试 | 排除定义/实现错误 | 内部 round-trip 不能代替独立角参考 |
| D2 | 对两个周期角使用 sin/cos；保持其余流程并控制参数量 | 检验周期不连续的学习影响 | 更好的编码不证明角包含或缺少多少内禀信息 |
| D3 | 紧凑/完整输入的容量与收敛对照 | 检验参数数目和优化难度 | 增加训练预算后变好不是普遍最优的证明 |
| D4 | 新注册的类别分辨率/共同支持对照 | 检验信息是否在两类压缩中丢失 | 不能为单个赢家单独选更有利网格 |
| D5 | 少量训练规模、独立 subset draws，冻结评价规则 | 检验有限训练样本机制 | 同池缩小训练集不能证明外部泛化 |

初期可只用 D、BC、BCD、ABCD 等针对问题的少量对照。只有计划重新报告完整 Shapley 时，才需要在同一新实验族下补齐所有联盟；不完整联盟不能填零。

**样本效率。** 现有 overlay 的注册缺项和主要为 AUC 的评估 bootstrap 必须先补齐；真正主张节省训练 MC，应画实际物理组数量对覆盖合格宽度的曲线，采用嵌套组子集及多次 subset draws，报告 train/calibration/template/assessment 成本的区别。只有跨越预先定义目标且具有相应不确定度，才能估计达到同等质量所需训练组数；不可向未观察规模外推。

现有样本效率设计属于显式质量 on 的实验族。若要研究 off-only BC，应另建明确继承/变更关系的协议，不得静默改写已有研究定义。跨架构、生成器和 detector 变化只在要声称该范围时扩展；2025 release 不能直接等同于独立样本或 generator variation。

## 9. 执行优先级、重跑范围和停止条件

| 阶段 | 工作包与产物 | 前置条件 | 验收/停止条件 |
|---|---|---|---|
| P0 | 版本矩阵、来源恢复决策、文稿事实修正、资格字段设计 | 现有文档及安全 metadata | 每个数字和状态能追到指定证据；找不到来源明确降级，不伪造替代 |
| P1 | DSID/角参考审核；层 A 的独立小计数基准 | 无需新增 H4l 物理 MC | 数值参考可重现；区间行为及误差界明确；有结构性失败先修方法 |
| P2 | 新 joint-support 正式结果；层 B/C 的有界开发基准 | 新根、冻结配置、各阶段访问条件 | 失败完整保留；分别判定支持、条件覆盖和选择程序覆盖，不能一个 complete 全部放行 |
| P3 | 按路线冻结主问题、宽度指标、覆盖/非劣容差、物理基线和预算 | P1/P2 提供可行性信息；确认资源仍未用于选择 | 没有可行质量模型则不提出质量峰之后的增益；没有独立资源则不提出确认性结论 |
| P4 | 独立验证/确认与必要机制实验 | 独立流/资源及有效 freeze | 按注册规则报告优势、非劣、无结论或失败；不因结果不佳临时换赢家 |
| P5 | 从冻结证据生成中英文稿、复现包和独立归档 | 上述证据实际满足所选主张 | 干净环境能重建对应层次；软件复算、聚合复算与完整科学重跑分别描述 |

重跑范围不能一概而论：

| 变更 | prepare | 训练 | Stage B/推断与验证 |
|---|---|---|---|
| 文稿事实、引用和纯导出修正 | 不需要 | 不需要 | 从原绑定产物重新导出；不改其科学状态 |
| 单纯采用已实现的 joint-support，数据/模型契约未变 | 通过审计后复用 | 复用冻结 75 模型 | 新根重建 nominal/template、gate、freeze、Asimov、正式评估；旧阶段不改名复用 |
| 新区间构造或新覆盖要求 | 通常可复用 | 通常可复用 | 新 inference contract；重新校准、独立验证及重算宽度/归因，不能继承旧区间 |
| 质量模型/网格/阈值族变更 | 依输入需求判断 | 输入和学习目标未变可复用 | 新注册实验族重建受影响下游，并保留探索历史 |
| sin/cos、容量、损失函数或训练规模变更 | 基础物理事件可复用；特征合同另绑定 | 受影响候选重训 | 新校准/模板/freeze/评估；完整归因要求同族完整联盟 |
| 物理权重、角定义、FSR、选择或过程身份纠错 | 受影响 preparation 重建 | 若训练输入、权重或群体改变则重训 | 全部受影响下游重建，旧结果作为历史记录 |

近期可以推进 P0/P1 以及已授权的新方法结果核查，而无需先承诺新增物理 MC。合成生成实验能回答统计方法问题，不能冒充独立 H4l 物理确认。新增背景 MC 是否必要，应由支持和验证结果决定；新增独立确认资源是否必要，应由历史用途审计决定。

## 10. 文献依据、检索记录与适用边界

本次通过用户指定的 SciSpace 做了八次成功检索；另一次负权重专题请求发生传输错误，随后改写问题重试成功。检索采用完整自然语言问题，主题如下。结果存在重复记录、预印本被索引为较新年份和语义检索未返回指定题名的情况，不能按排名直接认定相关性。

| 查询 | 研究问题 |
|---|---|
| Q1 | How can frequentist confidence intervals with reliable coverage be constructed for sparse Poisson signal-strength inference with finite Monte Carlo templates and negative event weights, beyond asymptotic profile likelihood intervals? |
| Q2 | How should feature-subset selection and machine-learning classifier optimization be validated independently when comparing expected parameter-inference precision in high energy physics, to control selection bias and distinguish exploratory results from confirmatory evidence? |
| Q3 | What likelihood methods have been developed for binned template fits with positive and negative Monte Carlo event weights, and how are their coverage and bias validated against independent compound Poisson simulation? |
| Q4 | How do Cawley and Talbot explain overfitting in model selection and selection bias in performance evaluation, and what validation designs prevent it? |
| Q5 | How can matrix element discriminants for Higgs decay to four leptons and inference-aware learning methods such as INFERNO provide baselines for estimating signal strength precision beyond a mass-only fit? |
| Q6 | How does INFERNO, inference-aware neural optimisation by de Castro and Dorigo, optimize summary statistics for parameter uncertainty instead of classification accuracy? |
| Q7 | How does the Feldman Cousins unified likelihood-ratio ordering construct frequentist confidence intervals for a Poisson signal with known background near a physical boundary? |
| Q8 | What methods are proposed in the paper Treatment of negative weights in Monte Carlo simulated data for including negative weights in likelihood-based data analysis? |

| 引用 | 文献及核验层级 | 本文采用的用途 | 适用边界 |
|---|---|---|---|
| R1 | Feldman & Cousins (1998), *Unified approach to the classical statistical analysis of small signals*, [DOI](https://doi.org/10.1103/PhysRevD.57.3873)；Crossref 核对书目，Q7 返回相关覆盖研究 | 选择小计数/边界 Neyman 参考构造 | 本次未全文复现算法；不能直接为任意 signed nuisance 保证覆盖 |
| R2 | Barlow & Beeston (1993), *Fitting using finite Monte Carlo samples*, [DOI](https://doi.org/10.1016/0010-4655(93)90005-W)；Crossref 核对书目 | 有限模板统计的基础对照 | 不把无权 Poisson 模板结论无条件移植到相关 signed 权重 |
| R3 | Dembinski & Abdelmotteleb (2022), *A new maximum-likelihood method for template fits*, [DOI](https://doi.org/10.1140/epjc/s10052-022-11019-z)；SciSpace 返回相关作者工作摘要，Crossref 核对正式题名 | 候选模板近似与数值比较设计 | 未确认全文对本项目 signed 分布的全部适用条件，不能直接替换 T1 |
| R4 | Glüsenkamp (2020), *A unified perspective on modified Poisson likelihoods for limited Monte Carlo data*, [DOI](https://doi.org/10.1088/1748-0221/15/01/P01035)；SciSpace 摘要、Crossref 书目 | 以 compound-Poisson 视角分析有限 MC 的生成假设 | 摘要讨论的统一框架不证明任意正负相关事件的近似有效 |
| R5 | Avery et al. (2013), *Precision studies of the Higgs boson decay channel H → ZZ → 4l with MEKD*, [DOI](https://doi.org/10.1103/PhysRevD.87.055006)；SciSpace 摘要、Crossref 书目 | 四轻子物理判别基线及角信息的既有背景 | 需独立运行/核对定义；论文存在不等于仓库 adapter 已科学验证 |
| R6 | de Castro & Dorigo (2019), *INFERNO: Inference-Aware Neural Optimisation*, [DOI](https://doi.org/10.1016/j.cpc.2019.06.007)；SciSpace 摘要、Crossref 书目 | 区分分类目标与推断目标，选择一个有意义的学习基线 | 优化近似不确定度不等于本项目低计数区间覆盖通过 |
| R7 | Cawley & Talbot (2010), *On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation*, [JMLR](https://jmlr.org/papers/v11/cawley10a.html)；SciSpace 摘要与元数据 | 选择与评价隔离；同池加种子不能替代独立验证 | 不从一般 ML 文献推导本项目选择偏差的具体数值 |
| R8 | Alexe et al., *Undercoverage in high-statistics counting experiments with finite MC samples*, [arXiv:2401.10542](https://arxiv.org/abs/2401.10542)；SciSpace 摘要 | 提醒有限 MC 与 nuisance 的区间风险 | 高统计条件下的结论不能直接量化当前约五事件的情景 |
| R9 | *Unbiased elimination of negative weights in Monte Carlo samples* (2022), [DOI](https://doi.org/10.1140/epjc/s10052-022-10372-3)；SciSpace 摘要与元数据 | 负权消除/重采样属于另一个可研究方向 | 不作为近期修复：会新增权重变换及误差传播问题，不能替代已绑定物理权重 |

Q8 没有可靠定位到指定的 Mandrik 题名，故本文不援引其算法细节。R1/R2 为相关检索后补充的经典书目核验，不声称 SciSpace 已返回它们的原文。全文推导、软件独立实现及数值适用性仍是后续工作；本分析不是系统综述，也不是由外部文献给本项目结果授予认证。

**最终状态：** 审查的主要诊断成立，F2 应继续维持“实现完成、正式证据待核查”的更正。现有材料可支持限定清楚的探索观察；较强投稿主张至少需要证据一致、独立统计参照、明确的主要比较及与之匹配的物理/确认资源。每一项新增实验均应允许失败或不确定结论，不以得到正向提升为验收条件。
