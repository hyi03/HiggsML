---
change_id: h4l-off-joint-support-v1
status: approved
source: 用户在本会话选择联合支持约束方法的正式设计，并明确新 200 个开发副本仅是方法选择证据、不限定后续数据分析范围
updated_at: 2026-09-22T18:02:18+08:00
---

# Spec: H4l off-only 联合支持约束阈值选择

## Problem and Outcome

现有 off-only 程序用 calibration 背景的物理产额中位数划分两个分数类别。名义模板可以通过，但独立的 calibration/template 物理事件组重采样可能使其中一侧的 signed 有效统计量低于 20。失败来自模板支持不足以及校准阈值波动，不是计算中断。

目标是定义一个对所有非空联盟一致适用、同时约束 calibration 和 template 两侧支持的阈值选择程序，保留完整五种子、16 联盟、两类别及特征归因目标。没有可行划分时明确失败，不保证所有未来副本都成功。

**用户澄清具有优先级：新生成的 200 个开发副本仅用于选择该方法。它们不是后续分析的数据集、不是正式 bootstrap 的副本集合、不是全部分析预算，也不取代名义分析、Toy、T2 或 assessment。**

本文件是供审批的正式方法设计，不是已批准的实现计划。检查的代码 HEAD 为 `cd8cd69db45b831c6ddee2193177fb0f8473fc12`；当时用户另有 AGENTS.md 与 paper/ 暂存或未暂存工作，本设计不处理它们。

## Affected Users and Systems

- 运行 H4l off-only 完整受控 MC 分析的研究者。
- 阈值生成、nominal 模板、freeze、MC bootstrap、T2、Toy 输入映射和汇总报告。
- 方法配置、阈值/schema、分析身份、来源复用审核、评估预算与已有访问历史。
- 保留原 marginal CRN 的边缘分布与解释；本变更不重新设计 CRN 耦合。

## Scope

1. 在现有受控 MC 母样本上使用原角色划分；所有符合已注册选择的角色事件均参与对应阶段，不从 200 个开发副本筛选“好事件”。
2. 保留 75 个冻结 off 模型、五个确定性 M0off、seed 42–46、全部 16 联盟。模型复用必须通过原核心协议与谱系核对。
3. 引入 `h4l-off-joint-support-v1` 方法合同；名义分析、每个 MC bootstrap 副本、每个 T2 outer 都执行同一阈值选择算法。
4. 新分析固定共同质量网格 `[105,140]`、两个分数类别和原物理选择；不得在名义阶段按结果重新搜索质量网格。
5. 完整保留名义 Asimov、Shapley、24 个条件交互、105 个非空联盟比较、五种子稳定性、MC bootstrap、model-self、assessment 和 T2 的不同证据层。
6. 当前数据已经用于探索与方法选择，新分析必须保留探索性标识。assessment 仍单独受访问与历史审核控制，不能因创建新方法身份自动打开。

## Non-goals

- 不获取新增 MC，不重训网络，不改特征组或样本角色比例。
- 不降低支持门槛，不用绝对权重替代 signed 产额，不丢弃低分类别。
- 不搜索 W68/AUC/Shapley 最优阈值，不按候选特判 D-only 或 AC。
- 不用精确分数边界扫描作为失败后的回退算法。
- 不把开发副本的通过率、原运行的输出或旧审核标记升级为新分析的正式证据。
- 不修订旧运行、旧报告或论文数字；本次已获准实施开发；不运行正式评估、不提交代码。

## Requirements and Design

### 1. 方法选择的证据

主要证据为 [可行性报告](../../../var/h4l-support-feasibility-20260922-001/report.md) 的 `fresh` cohort：固定 seed `20260922`，200 次独立角色组重采样，所有 80 个候选同时满足支持才计一次通过。

| 规则 | 新 200 开发副本完整通过数 |
|---|---:|
| 原背景中位数 | 149 |
| calibration-only 支持约束 | 154 |
| calibration + template 联合支持约束 | 200 |

全部 75 个非空联盟的名义阈值保持中位数；新 15,000 个非空候选/副本单元中有 131 个改选分位点。主要改选到 55% 或 60%。这些观测是选择本规则的依据，不成为固定某候选阈值的查找表。

历史 200 副本只用于故障重建与数值核验，不与新 200 副本合并为“400 次独立确认”。新抽样来自同一经验 MC 分布，亦不是新的独立物理事件。

证据位于忽略目录，文件缺失时不得伪造或重新抽一批后冒充原证据。当前已核对整个 `output-sha256.json`，以下关键绑定用于将来审核：

| 文件（相对于证据目录） | SHA-256 |
|---|---|
| `plan.json` | `873b20a08c6699092ee32f9d706d53c876345e8cec113d5670152ecc6db1ffbf` |
| `summary.json` | `2b4d4dbe8d043cbe20d7760d0f9a256c0ccaa31ca2a22f7e50a8e9c7e7bea84f` |
| `group_draws.npz` | `4ff437c280c9849ae0e04ce5fb6fa0ab0d32083ee360062cf78b9988f621741a` |
| `candidate_draws.csv` | `e2535049cb367f0a18ec69a8a1396b1f0daa87ebf488ff793f686a0e5a80f730` |
| `provenance.json` | `1d92db1c8343e346524e76e79868ec5c8de49ad901843b5118116702bc570131` |

NPZ 的第 0 行是名义重数，第 1–200 行是历史副本；本设计引用的新 cohort 严格为第 201–400 行，对应新 replica 0–199。正式分析不得把整个 NPZ 当成正式 draw plan。

### 2. 目标量和数据职责

每个候选的分析程序为：固定网络 -> calibration 背景生成候选阈值 -> calibration/template 联合支持筛选 -> 同一阈值分类 -> signed 模板 -> T1 Asimov W68。仍令 `v(S)=-W68(S)`，先计算每个 seed 的完整归因向量，再作五 seed 汇总。

阈值现在是两角色数据的函数 `t = T(C,T)`。因此 MC bootstrap 估计的是这个联合选择程序在有限 calibration/template MC 下的波动，不是原中位数程序的遗漏误差。

| 角色/来源 | 新职责与边界 |
|---|---|
| train / validation | 只保留既有冻结模型及其选择历史，不参与新阈值搜索 |
| calibration 背景 | 用 signed physical_weight 生成候选分位点 |
| calibration 信号与背景 | 用 physical_weight 检查每个过程的两侧支持 |
| template 信号与背景 | 用 yield_weight 检查两侧支持并构建最终模板；明确参与阈值选择 |
| assessment | 不参与阈值生成、支持筛选或回退；获准访问后只接受已固定映射 |
| 开发副本 | 方法选择证据及实现重放核验，不作为正式分析输入母样本 |

不改变事件角色，也不把同一组移动到另一角色。template 参与选择属于新程序的显式设计，不是独立验证。

### 3. 确定性阈值规则

对每个非空联盟、每个 seed、每次调用，执行以下固定顺序：

1. 核验 raw 模型、数据集、角色、事件组、权重、固定质量支持及输入身份；预测分数必须有限且位于注册 score_edges 内。
2. 用 calibration 背景、原 score_edges、原组方差和原非负固定总量投影构造背景分布。保留原整体支持要求及同组跨 score-bin 的未验证相关性拒绝规则；投影不是逐 bin 裁剪。
3. 固定候选 `q=k/20, k=1,...,19`。依原 CDF 线性 bin 内插值计算阈值；不得改用经验绝对权重分位点。跨实现校验数值容差只用于一致性检查，不改变支持门槛。
4. 用 `score < threshold` 为低类别，`score >= threshold` 为高类别。同分数必须同类别。重复阈值可保留，其对应 q 和支持检查记录均需可追溯。
5. 分别对 C 与 T 的每个过程、两个类别计算 signed 产额、组方差、逐事件绝对权重和、组占用、rho、neff。一个物理组多行时先组内求和再计算方差；bootstrap 中每份组副本拥有独立副本身份。
6. 一个候选阈值可行，当且仅当两个角色所有过程/类别均有占用、产额大于零、方差大于零、`rho >= 0.2`、`neff_signed >= 20`。任何空 bin 不自动认作结构零。信号或背景整体缺失也失败。
7. 按整数键 `(|k-10|, k)` 取最小的可行候选；这严格实现“最接近中位数，等距选较小 q”，避免浮点距离打破平局。每个角色可采用不同的权重归一化，但不得改变原物理权重或角色抽样概率。
8. 19 个候选全部不可行时输出 `no_feasible_joint_threshold`。不补抽、不加候选、不放宽门槛、不回退名义阈值或单类别。

对角色 R、过程 p、类别 b，令 `W_g = sum_{i in g,p,b} w_i`：

```text
y = sum_g W_g
variance = sum_g W_g^2
sum_abs_weight = sum_i |w_i|
rho = |y| / sum_abs_weight
neff_signed = y^2 / variance
```

重数为 m_g 时，每份组副本均完整保留组内事件，方差贡献是 `m_g * W_g^2`。不能把原组权重乘 m_g 后再平方。

过程粒度沿用实际输入的 process；只有没有 process 列时才允许与旧契约一致的 label 回退，并记录 `process_identity_source=label_legacy`，不得声称获得独立物理过程级验证。两角色过程/信号身份集合不一致则拒绝。

M0off 维持常数 0.5、阈值 0.5、低类别结构零证据及原 likelihood-equivalence 核验；不执行 19 点选择，也不要求它产生两个非空类别。其 template 有效类别仍必须满足原支持门槛。

### 4. 名义分析、门控与冻结

所有候选执行联合规则后，重新构建本方法的 nominal 模板、G1、J0/J1 和身份；任何候选不可行则停止，保留科学失败终态。J0/J1 继续保留原职责和预算，不改成重新选择阈值的循环，也不把 Bernoulli thinning 的 J1 冒充 bootstrap 检验。

开发证据绑定与实现重放是研发核验；不以“看过的 200/200”声称完成独立冻结前资格验证。新增正式分析仍必须通过自身名义支持、现有 G1/J0/J1、绑定及审核门控。

即使本母样本的名义阈值全部与旧中位数相同，也必须发布新 nominal artifact，记录全部 19 个候选的选择理由。当前 marginal nominal adapter 只核对旧模板兼容性，不能直接把旧模板标成新方法产物。

冻结依赖顺序为：来源复用审核 -> 新方法 registration -> 新 nominal/选择记录 -> G1/J0/J1 -> evaluation specification -> freeze -> Asimov/完整 evaluation plan。具体既有发布依赖保持无环；freeze 绑定方法与选择记录，后置 plan 绑定实际 freeze，不反向修改 freeze。

### 5. 完整分析预算与随机流

本设计保留现有分析预算作为新方法的初始正式执行合同，预算来自现行研究协议，不来自开发样本量。这里的“正式”指按新合同执行，不意味着独立确认或具备主科学结论资格。

| 阶段 | 新方法中的分析范围 |
|---|---|
| nominal / Asimov | 完整 MC 对应角色，80 候选；完整归因、排序、交互、成对比较 |
| MC bootstrap | 新登记的 200 个完整角色组副本；每副本重新联合选择、模板、推断及完整归因 |
| model-self | mu=0,1,2 × 五 seed；每候选每 cell 500 Toys |
| assessment | 同上，仍受独立的 access/history/budget 审核控制；不可访问时如实保持未运行 |
| T2 | mu=1 × 五 seed；每 seed 20 个 calibration outer × 100 inner Toys |
| 训练种子稳定性 | 保留现行完整 5-seed 计算与 3125 有序 seed-vector 枚举，不与事件 MC 区间相加 |

开发 cohort、正式 bootstrap、model-self、assessment、T2 outer/inner 使用独立的 stage namespace。不得直接复用开发 cohort 的 seed/counts，也不得复用旧正式 bootstrap 的 draw vectors。

正式 MC bootstrap 的 base_seed 保留 42001，但使用新的确定性 RNG 身份：

```text
payload = canonical_json([
  "h4l-off-joint-support-rng-v1", analysis_contract_digest,
  "mc_bootstrap", 42001, replica_index, role
])
seed_integer = int.from_bytes(SHA256(UTF8(payload)), "big")
rng = numpy.random.Generator(numpy.random.PCG64(seed_integer))
counts = rng.multinomial(n_groups, [1/n_groups] * n_groups)
```

组身份按字符串排序。role 为 calibration 或 template，各角色独立；同一副本每个角色的 counts 由全部候选共享。保存实际 NumPy 版本、排序组摘要和 counts 摘要；并行调度不进入随机身份。digest 不含输出目录、时间戳或结果。

Toy/T2 的现有 stage、mu、seed-block、outer、process、mass-bin 和 auxiliary 子流结构保留；在 stream 根身份中增加本 analysis_contract_digest，不能更改 CRN 的共享总数/分配语义。不同训练 seed 的相同 Toy 序号仍没有物理配对含义。

预算更改必须是新的显式合同修订，不能因失败增加数量直到得到 200 个成功副本。

### 6. 各层重选阈值的语义

**MC bootstrap：** 分别重采样 C 和 T 物理组，对每个候选运行 `T(C*,T*)`，在 T* 上构建模板并执行原 T1/归因链路。完整成功要求 80 个候选的选择、模板、推断和归因均成功，支持通过本身不是完整成功。全部 200 个完整副本才计算 16/84、2.5/97.5 百分位；任何失败则正式区间为 null，成功副本只作条件诊断。

**model-self / assessment：** 使用新 nominal 阶段冻结的联合阈值分类；不能根据 Toy 或 assessment 的类别占用重新选择。零 Poisson 观测不等于 MC 模板支持失败。若评估母样本支持检查失败，只记录失败，绝不利用该母样本改阈值。

**T2：** 维持 calibration-only outer 抽样、template 固定的现有作用域，执行 `T(C*,T_nominal)`。新阈值应用于固定 template 和同一个 outer 的评估母样本/伪事件类别映射。先预检全部 outer 的选择和模板支持，再生成 inner Toys；outer 失败保留计划 inner 预算，不补抽。T2 明确标记为 `calibration_variation_conditional_on_fixed_template_joint_selector`，不称作 calibration+template 联合抽样的全程序覆盖验证。

改变 T2 outer 为双角色抽样会改变其目标量，不包含在本设计。该更全面的选择后覆盖验证属于另行登记的研究，而不是从现有 T2 成功率推导。

### 7. 推断及报告资格

本方法先保留原 signed 模板与 pyhf shapesys 近似，避免同时改变阈值规则和似然模型。旧 T1 参考只能作为原固定分箱近似的证据，不能自动证明使用 template 选阈值之后的覆盖有效。

允许生成探索性的 W68、归因和在完整正式副本下的 bootstrap 百分位摘要；必须标注 `selection_aware_coverage=unvalidated`、`registration_status=exploratory_posthoc`、`primary_claim_eligible=false`，不得将 percentile spread 称作已校准的总体置信区间。

分开报告执行完成、支持检查、完整 bootstrap、条件 Toy 闭合、T2 条件波动、访问审核和科学资格。所有计算均完成时执行状态可 complete，但资格仍可 unvalidated；不得用一个 complete 字段掩盖未验证项。

## Interfaces and Data

### 方法配置与入口

新增独立方法配置 `config/protocols/h4l_off_joint_support_v1.json`，不原地修改旧核心协议快照。配置至少固定 method_id、19 个整数分位点分子、分母 20、选择顺序、两角色权重语义、门槛、质量网格、失败政策与 RNG policy。

`analysis_contract_digest` 对核心协议摘要、方法配置、候选定义、marginal pairing 合同、预算和随机政策整体求规范摘要。source core-protocol 摘要与 analysis-contract 摘要必须作为两个字段传播，不能把核心协议不变当作分析方法未变。

提供显式 `--threshold-method joint-support-v1` 入口，包装器和直接 attribution 入口均传播到领域服务；缺省保持现有 `median-v1` 行为。该参数不是恢复被移除的 evaluation-version 切换。配置/标志冲突时拒绝，不静默覆盖。

### 领域接口

新增领域级纯选择接口（具体文件放置由后续计划确定）：

```text
select_joint_threshold(
  calibration_frame, calibration_scores,
  template_frame, template_scores,
  core_protocol, method_contract,
  model_identity, input_bindings, draw_identity
) -> joint_threshold_record
```

支持统计复用 `GroupBinStatistics`/模板的组矩算法；分位点生成复用 calibration 的投影语义。CLI 不包含科学选择逻辑。`fit_thresholds` 的旧行为保留，不能全局替换影响其他研究流程。

阈值记录采用新 schema `h4l-joint-support-threshold-v1`，至少包含：

- method_id、analysis_contract_digest、model_id、raw mapping_id、candidate key、seed；
- source_role=`calibration_template_joint`、两角色 population/prepared/source artifact 绑定、draw 身份与重数摘要；
- 原 calibration 投影诊断、19 个 q/阈值、每个角色/过程/类别的 y、variance、sum_abs_weight、占用、rho、neff、支持状态与失败原因；
- selected_quantile_numerator、selected_threshold、确定性选择理由及同分数规则；
- status、reason、record digest 和 threshold_id；未定义的统计量写 null，不写 NaN/Inf。

只缓存模型预测分数及不可变输入统计准备；不得在不同 draw 之间缓存选择结果。raw mapping_id 可以保持网络对应的 raw 身份，但 threshold_id 和冻结/评估身份必须绑定完整的新记录，而不只是阈值浮点数。

M0off 记录 `selector_bypassed=registered_constant_baseline` 及原结构零证据。同一 candidate key 可跨方法保留，但 artifact、threshold、freeze、plan 和报告 cohort 不可混用。

### 集成边界

| 现有边界 | 新设计的要求 |
|---|---|
| `modeling/calibration.py`、`inference/statistics.py`、`templates.py` | 共享投影与组统计语义；旧 median 接口不变 |
| `attribution_workflow.py`、`marginal_workflow.py` | 重建新 nominal，不仅发布旧 source-nominal 的兼容适配器；审核模型复用与方法身份 |
| `inference/bootstrap.py` | 新方法路由调用联合选择；原中位数运行维持可重放 |
| `inference/assessment.py` | T2 outer 联合选择及映射同步；普通 Toy/assessment 阈值不再拟合 |
| marginal support/coupling/evaluation-state | 保持原支持与访问职责；绑定 analysis contract，防止跨方法误复用 |
| schemas、报告与运行手册 | 选择记录、资格字段、预算/随机隔离、探索性说明 |

完整 schema、命令参数传播路径和测试文件由批准后的计划列出；不能因本表概括集成边界而省略绑定检查。

## Failure, Recovery, and Compatibility

| 情况 | 必须的行为 |
|---|---|
| 输入身份、核心协议、角色/过程不一致或跨方法缓存 | 硬绑定错误，禁止计算/发布有效结果 |
| calibration 投影失败、未验证组相关性 | 保留原科学失败原因，不进入备用阈值算法 |
| 没有可行联合阈值 | 科学终态 `no_feasible_joint_threshold`，保留 19 项诊断 |
| nominal 任一候选失败 | 禁止 freeze；新目录保留失败证据 |
| 正式 bootstrap 任一候选/拟合失败 | 副本保留；汇总 `bootstrap_incomplete`，正式区间 null |
| T2 outer 或其父样本支持失败 | 按现有预检/预算规则停止相应执行，保留 outer 及未执行 inner 预算 |
| assessment 不具备访问资格 | 保持未运行/资格待定，不通过 --force 或新目录绕过 |
| 同一身份的计算/发布中断 | 仅按原 resume/retry 合同恢复；不把科学失败当作可补抽故障 |

采用全新运行根，旧 `h4l-off-test01`、现有开发证据、已完成或失败 artifact 均不可覆盖。旧数据可作为受审计的上游，旧阈值/模板/报告不能重新贴新方法标签。既有访问 claim 按 population 历史继续审核，不能仅靠 analysis-contract 改名获得新访问权。

当前显式选择不改变默认路径；以后变更默认方法是单独决策。正式分析只执行实际获准的阶段；完整分析范围与是否具备各阶段访问资格必须分别表达。

## Policy and Architecture Constraints

- MC-only；不处理真实数据，不将结果称作 ATLAS/CMS 官方结果、Higgs discovery 或物理测量。
- 核心物理选择、signed 产额、事件组完整性、`m4l=off` 网络输入限制不变，似然仍保留质量坐标。
- 方法设置不能按 assessment、模型排名、W68 或归因贡献调整。当前方法来自既有探索，必须如实记录历史。
- 不提交生成数据、模型、runs、缓存或开发重数文件；设计中的摘要与本地证据路径用于审核，不保证跨机器可用。
- 科学规则放领域服务与版本化合同中；实现研究不得借机重构无关流程。

## Risks and Concerns

1. **选择后覆盖未验证。** template 同时决定阈值与推断模板，原固定分箱近似不能自动赋予无条件覆盖；bootstrap 重选是必要但不充分的处理。
2. **仍有边界风险。** 可行性重建中最小 neff 约 20.15，接近门槛；200 次零失败不是未来必过保证。固定经验分布下其单侧 95% 失败概率上界约 1.49%。
3. **非光滑选择。** 离散 q 与硬门槛会产生阈值跳变，须报告 q 分布、边界接近程度和失败率，不能只展示成功区间。
4. **角色相关性的解释改变。** template 已参与选择，不能继续称作未参与方法选择的验证样本。
5. **既有审核不足。** 无新增 MC、已观察结果以及现有独立参考缺口仍限制确认性结论。本设计不声称独立数据不可得时能恢复确认资格。
6. **开发证据被过度使用。** 回放新 200 cohort 是回归核验，不是新确认；完整正式运行使用独立随机流但仍是同一经验 MC 母样本。

## Acceptance Criteria

| ID | 可观测验收条件 |
|---|---|
| AC-01 | 所有入口对新方法使用同一领域选择器；19 点、权重、门槛、平局规则可由合同和记录重建 |
| AC-02 | 批处理重放已绑定的新 cohort 200 副本，80 候选完整支持 200/200，复现 131 个非空候选/副本的非中位数选择；名义 75 个保持中位数。偏差须诊断，不能改证据或放宽规则 |
| AC-03 | 存在多行物理组的独立手算用例验证组内求和及重数方差；不得把当前单行组假设带入生产代码 |
| AC-04 | M0off 保持结构零及等价性；没有可行划分的合成用例保留失败、无回退 |
| AC-05 | bootstrap 中 C*/T* 都进入选择；T2 中仅 C*、固定 T；Toy/assessment 不参与选择；伪事件与模板使用同一 outer 映射 |
| AC-06 | 正式 bootstrap 的 RNG 命名空间、counts 身份与开发 cohort/旧正式流分离，顺序/并行结果一致；200 预算不是导入开发副本的别名 |
| AC-07 | 核心协议复用审核与新 analysis-contract 身份同时存在；仅阈值数值相同也不能复用旧 nominal/freeze/plan/claim 结果 |
| AC-08 | 新报告同时显示运行完成度与 selection-aware coverage 资格；失败区间 null、成功条件诊断及主结论禁用状态正确 |
| AC-09 | 旧 median 行为和旧 artifact 的读取/重放不变；不覆盖任何旧 run；assessment 访问保护不回退 |
| AC-10 | 完整分析执行矩阵明确包含名义、归因、正式 bootstrap、model-self、assessment、T2；未获准或未运行阶段如实显示，不由开发 200/200 填充 |

AC-02 的 200/200 是实现一致性目标，不保证新正式随机流全成功；正式执行出现科学失败必须忠实报告，不能因此视为获准修改方法。

## Proof Required

**本轮已有证据：** 可行性 artifact 的哈希已核对；现行源码/文档集成边界已静态检查；本轮只编写 spec，没有运行新的 MC、Toy、T2 或代码测试。

**实现后软件证据：** 对选择器的独立预期值、组重数、过程/角色、边界/同分数、投影失败、无解、身份隔离、并行确定性、旧方法兼容及预算失败进行聚焦测试，再按仓库要求完成相关集成检查。具体命令由计划确定。

**开发回放证据：** 使用绑定的新 200 cohort 重放支持选择，和保存记录逐候选核对；允许名义统计数值按预先规定的机器精度容差核验，不允许用容差改变 neff/rho 的有效性判断。

**新正式执行证据：** 新 registration/freeze/plan 下完成实际获准的完整矩阵，报告 200 个新 bootstrap 的完整链路成功数、Toy/assessment/T2 状态与失败预算。不得声称本 spec 或开发回放已完成这些工作。

**科学资格证据：** 选择后覆盖、偏差及 signed-MC T1 近似适用性仍需另行设计并审查验证研究。该研究须在观察验证结果前确定母模型/变化范围、重复构造 C/T 与重选规则、目标覆盖及容差、预算和失败分母；本 spec 不以条件 model-self/T2 替代它，也不授予主科学结论资格。

## Open Questions

当前探索性方法设计没有阻塞算法定义的未决选择。选择后覆盖验证的具体研究预算与参考模型不在本次授权范围内，其资格保持 `unvalidated`；这不阻止审查本方法及后续探索性实现计划，也不允许将该缺口填成已通过。

## Approval Record

- Status: approved.
- Approval source: 用户于 2026-09-22 明确要求“批准正式设计文档，并实施开发”。
- Approved scope: 方法合同、实施开发、软件验证及绑定开发 cohort 重放。
- 实施计划由开发中细化，不声称另行经过人工审阅。
- 正式 MC/Toy/T2/assessment 执行和提交代码未授权。
- Approved at: 2026-09-22 (Asia/Shanghai).
