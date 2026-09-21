---
title: H→ZZ*→4ℓ 中无显式四轻子质量输入的运动学特征归因与信号强度推断
title_en: Kinematic Feature Attribution and Signal-Strength Inference without Explicit Four-Lepton Mass Input in H→ZZ*→4ℓ
date: 2026-09-21
version: writing-draft-v0.3
status: exploratory-MC-results-incomplete-validation
documentation_source_revision: e066bae9a12e5bd2d02cd199bbd09a99151ea6d7
scientific_result_baseline: h4l-off-test01/report-resume-6f5909a8b7f58d5e
protocol_reference: h4l-on-shell-software-v1
scope: MC-only educational and technical demonstration
---

# H→ZZ*→4ℓ 中无显式四轻子质量输入的运动学特征归因与信号强度推断

**英文题目：** *Kinematic Feature Attribution and Signal-Strength Inference without Explicit Four-Lepton Mass Input in H→ZZ*→4ℓ*

**作者、单位：**【待填：作者及单位】

> 本文报告 h4l-off-test01 的探索性受控 MC 结果。数值来自已发布的冻结分析及最新恢复报告，方法核对至上述代码版本。运行整体仍为 incomplete，独立验证未完成。本文不构成 ATLAS/CMS 官方结果、Higgs 发现或真实数据物理测量。逐项来源、代码版本与文件摘要见[结果证据索引](result-evidence.md)。

## 摘要

本文在受控 H→ZZ*→4ℓ 蒙特卡洛样本中研究运动学表示对信号强度 μ 推断的贡献。分类器不输入显式四轻子不变质量 m4l，采用十九个运动学变量的 A/B/C/D 分组，比较全部十五个非空组合和同流程常数空集。分析复用五个训练种子共七十五个固定网络，以共同模板和 T1 有限模板统计模型计算 μ=1、10 fb⁻¹ 下的 Asimov 68% 区间宽度 W68。冻结质量网格合并为 105–140 GeV 的单一质量箱，因此结果限定于该粗化模板分析，不能解释为对精细质量谱分析的增益。BC、AC 与完整 ABCD 的 W68 中位数分别为 1.511617、1.515244 和 1.535930；BC 和 AC 相对常数空集分别改善 9.143% 和 8.924%，相对 ABCD 的逐种子配对改善中位数分别为 1.299% 和 1.425%。Shapley 分解显示 B、C 为主要正贡献组，A 的贡献较小，D 的贡献为负。分类 AUC 与区间宽度排序不完全一致。冻结 assessment 和重复校准 T2 的数值拟合已完成，但事件组 bootstrap 仅 161/200 个副本完整有效，访问审核为非独立自审，且人工共同随机数耦合的配对误差仅具条件诊断意义。结果支持固定学习与推断流程中的紧凑表示候选和有限样本适用性结论，尚不支持独立确认的精度优势、可靠覆盖或物理稳健性声明。

**关键词：** 四轻子末态；蒙特卡洛；特征归因；信号强度；剖面似然；有限模拟统计

## Abstract

We study the contribution of kinematic representations to signal-strength inference in controlled H→ZZ*→4ℓ Monte Carlo samples. The classifier omits explicit four-lepton mass input. All fifteen nonempty subsets of four feature groups are compared with a constant-score baseline, using seventy-five fixed networks trained with five seeds. Expected precision is quantified by the Asimov 68% interval width W68 at μ=1 and 10 fb⁻¹ under a common T1 template-statistical model. The frozen mass grid contains a single bin spanning 105–140 GeV; the conclusions therefore apply to this coarsened analysis, rather than establish gains over a resolved mass-spectrum fit. Median widths are 1.511617, 1.515244 and 1.535930 for BC, AC and ABCD, respectively. BC and AC reduce the width relative to the constant baseline by 9.143% and 8.924%; their median paired improvements over ABCD are 1.299% and 1.425%. Exact Shapley attribution assigns the largest positive contributions to B and C, a smaller contribution to A, and a negative contribution to D. Validation AUC and interval-width rankings differ. Assessment and repeated-calibration fits have completed, but only 161 of 200 event-group bootstrap replicas are fully valid. Access was authorized through non-independent self-review, and paired uncertainties under artificial common-random-number coupling remain conditional diagnostics. These exploratory results identify compact candidates and finite-sample limitations within the fixed procedure; independently confirmed precision gains and reliable coverage remain unestablished.

## 1 引言

四轻子末态同时包含共振质量与衰变运动学结构。矩阵元判别为这类分析提供了物理参照，相关背景见 [R01–R03](references/references.md)。本研究关注实际分类器、分数压缩和模板误差共同作用下，哪些运动学组合能够缩短信号强度区间。输入更多变量不保证有限样本学习更有效，分类排序改善也不必然降低最终参数不确定度。INFERNO 以推断目标训练统计量，说明分类目标与推断目标需要区分 [R14](references/references.md)；本文仍使用 BCE 训练和验证 AUC 早停，在冻结后评价 W68，并未实现 INFERNO 优化。

当前论文主线为 raw、m4l=off 的完整特征组归因。M5/M4 的物理 CDF 比较、矩阵元、对抗去相关和训练样本效率属于独立扩展，不作为本次结果的已完成实验。本研究的六类输出为：W68、全部子集排名及种子稳定性、精确 Shapley 与 24 个条件交互、验证 AUC 与 W68 的关系、探索选定的 BC/AC 对 ABCD 比较，以及全部 105 个非空子集直接配对比较。

分析不预设精度改善，也不把不同训练种子视为独立 MC 数据集。归因描述固定流程中的边际收益，不表示因果信息量、最小充分统计量或已确认的最佳特征选择 [R22–R25](references/references.md)。

## 2 数据、物理定义与样本隔离

### 2.1 研究对象与适用范围

先导研究指定 `atlas2020_4lep` 数据集，信号 DSID 为 345060，背景 DSID 为 363490，终态为 2e2μ，四轻子质量范围为 105–140 GeV，积分亮度为 10 fb⁻¹。信号强度 μ 定义为相对于绑定的 ggH125 信号模板的乘性因子。背景过程的详细产生链尚需来源审计，因此本文不将 DSID 363490 未经核验地等同于纯 qq̄→ZZ 背景。采用 μs+b 形式还意味着使用相应的 on-shell、忽略相关干涉项的模板近似，其适用性需在输入物理定义中说明。

研究导出复用封存数据 profile 与既有轻子选择、Z 配对、四动量及角变量计算，并另行要求 2e2μ 终态。轻子横动量和质量统一以 GeV 表示，角度使用弧度。原始轻子电荷、味道、能量和配对索引随研究事件保存，四轻子快度由完整四动量计算：

\[
y_{4\ell}=\frac{1}{2}\log\frac{E_{4\ell}+p_{z,4\ell}}
{E_{4\ell}-p_{z,4\ell}}. \tag{1}
\]

无效角或不可定义的快度不通过替代值补齐，而产生显式失败状态。所复用的质量窗预处理配置给出的降序轻子横动量阈值为 20、15、10、7 GeV，电子／μ 子的绝对赝快度阈值为 2.47／2.7，轨迹和量能器相对隔离阈值均为 0.3。电子／μ 子的横向冲击参数显著性阈值为 5／3，纵向量 z0·sinθ 的阈值为 0.5 mm；所有同味异号对的质量下限为 5 GeV，Z1 和 Z2 质量窗分别为 50–106 GeV、12–115 GeV，Z2 下限使用 fixed 模式。研究导出把该配置中的四轻子窗口替换为 105–140 GeV。这些数值是源码引用配置的事实，具体边界判据和完整选择流程仍以绑定实现为准。

正式数据章节还需补入 Z1/Z2 与负电轻子方向约定、FSR 处理、独立重建参考、生成器及版本、PDF、淋浴、过滤效率和探测器链证据。本稿不依据通常的四轻子分析习惯补造这些信息。

表 1 给出已在软件协议中明确的研究设置。它们是实验默认契约，不是已完成的样本审计结果。

| 项目 | 设置或状态 |
|---|---|
| 数据集 | atlas2020_4lep；MC-only |
| 信号／背景标识 | DSID 345060／363490 |
| 末态与质量范围 | 2e2μ；105 ≤ m4l < 140 GeV，左闭右开 |
| 积分亮度 | 10000 pb⁻¹，即 10 fb⁻¹ |
| 历史 development 概率 | 0.8 |
| 训练种子 | 42、43、44、45、46 |
| 软件协议 | h4l-on-shell-software-v1 |
| 协议适用性 | 合成软件默认规则，尚非绑定 MC 的科学验证 |
| 2e2μ 实际入选计数及物理产额 | 【待填：绑定输入审计】 |

上述选择具有明确但有限的动机。固定 2020 MC 对使输入身份、标签和流程绑定可审计；选择 2e2μ 可限制首期工作量并减少同味配对歧义；on-shell 质量窗保留信号区及连续背景上下文；10 fb⁻¹ 提供统一的预期产额尺度。这些理由不证明具体窗口、角色比例或亮度是最优值，现有文档也没有建立其数值优化依据。是否适用于实际 MC 必须在冻结评估前审计，不能依据 assessment 的方法排名调整。

下载工具识别的 atlas2025_exactly4lep 是另一 release/collection，不自动成为可替换输入、独立确认样本或生成器变化。当前 H4l 流程仍绑定 atlas2020_4lep；跨 release 组合需要过程、事件重叠及历史反馈证据。

### 2.2 五角色与事件身份

首期只使用原有 development 分区，并按物理事件组的固定哈希划分五种角色。事件组由过程身份和事件编号构成，技术行身份另行保留。同一物理事件的多行、重复表示或系统变体必须保持同一角色。各方法和各随机种子共享划分，网络种子不改变样本角色。

| 角色 | development 内比例 | 允许用途 |
|---|---:|---|
| train | 40% | 网络参数、标准化量、优化权重、对抗质量箱 |
| validation | 10% | 普通网络早停与 checkpoint；只评价训练诊断 |
| calibration | 20% | 条件 CDF 与分数类别阈值 |
| template | 20% | 物理模板、有效统计和共同网格 |
| assessment | 10% | 冻结分析后的闭合和失配评价、伪数据母模板 |

输入读取先验证身份与角色，再决定是否解码特征。ROOT 导出先判断既有 development/test 身份，应用层仅请求不跨 test 条目的连续 development 区间。但请求范围本身不足以证明底层从未解释相邻 held-out 特征：历史 uproot 5.7.5 合成 mixed-basket 检查观察到最终切片前的 basket 级数值视图。绑定来源的分支解释行为与严格访问契约仍需独立审计，不能把区间读取或合成吞吐测试写成完整访问保证。这不授权整块解码后再过滤，也不授权重新打开旧 test 特征。研究不通过旧 test 入口完成终评，不把五种角色等同于历史五折 OOF。

assessment 的使用要求冻结模型、映射、候选清单和共同模板。其结果不能反向选择网络、CDF 网格或统计阈值。原样本池存在历史研究反馈的可能性，当前角色隔离仅支持内部验证意义上的独立；正式外部验证还需要历史反馈审计以及未参与分析选择的批次和事件重叠证据。对已经影响分析设计的样本重新划分或更换随机种子，不能恢复这种独立性。

### 2.3 权重及事件组统计

物理事件权重保留符号，归一化由受控样本契约中的亮度、截面与 sum-of-weights 等约定给出。截面是否包含分支比、k-factor 与过滤效率必须按来源确认，不能重复相乘。负权重的成因也必须查证，不仅凭符号将其归于量子干涉。

设某条事件记录的物理权重为 \(w_i\)，所属角色的条件抽样概率为 \(r\)，则用于完整目标产额估计的权重为

\[
\widetilde w_i=\frac{w_i}{p_{\mathrm{dev}}r},\qquad p_{\mathrm{dev}}=0.8. \tag{2}
\]

归一化使用已知抽样概率，不将各角色的总产额强制调成相同数值。定义事件组 g 对箱 a 的总贡献 \(W_{ga}=\sum_{i\in(g,a)}\widetilde w_i\)，模板的产额和事件组协方差估计为

\[
Y_a=\sum_g W_{ga},\qquad V_{ab}=\sum_g W_{ga}W_{gb}. \tag{3}
\]

对于单一统计区域，令 \(A=\sum_i|\widetilde w_i|\)、\(V=\sum_g(\sum_{i\in g}\widetilde w_i)^2\)，记录

\[
N_{\mathrm{eff,signed}}=\frac{Y^2}{V},\quad
N_{\mathrm{eff,abs}}=\frac{A^2}{V},\quad
\rho=\frac{|Y|}{A}. \tag{4}
\]

同时报告原始行数、物理事件组数、正负权重和及负权重行比例。式 (3) 对组内相关技术行先求和再平方；逐行平方和一般不能替代该方差。式 (4) 用于识别有限统计与抵消问题，不构成模板误差近似已经成立的证明。

### 2.4 两级统计支持检查

G0 对 assessment 之外的各角色与信号／背景检查正产额、有效计数和抵消程度。当前软件默认阈值为 \(N_{\mathrm{eff,signed}}\ge20\)、\(\rho\ge0.2\)。G0 不使用分数，不能证明二维模板有效，也不自行证明物理来源已经验证。

G1 在最小模型、校准和模板建立后，检查条件分布、共同分箱及 T1 所要求的数值和相关性条件。实际组协方差不满足独立箱假设时，即使提供了验证标记，也不能通过 G1。通过最小链路后才扩展其余种子、对抗强度、固定轮数对照、绝对权重 CDF 及 L1。实际 MC 中若默认阈值或网格不适用，应在 assessment 之前形成新协议；不得根据结果输赢调节规则。

## 3 特征表示与分类器

### 3.1 输入、空集和质量信息

| 组 | 输入变量 | 数量 |
|---|---|---:|
| A | lep1_pt–lep4_pt，lep1_eta–lep4_eta | 8 |
| B | mZ1，mZ2，deltaR_Z1，deltaR_Z2 | 4 |
| C | pt4l，deltaPhi_ZZ | 2 |
| D | cos_theta_star，cos_theta_1，cos_theta_2，phi_decay_planes，phi_production_plane | 5 |

ABCD 共十九项，BC 六项，AC 十项。m4l 不属于四组，当前 off 模型不将其追加到输入。移除显式质量列并不消除相关运动学携带的质量信息；因此本文不声称获得了固定精确质量条件下的独立信息分解，也不声称分数已与质量去相关。

十五个非空组合分别使用种子 42–46 的既有独立训练 checkpoint，本次归因阶段不重训。另建立五个确定性的 M0off 身份，分数恒为 0.5，阈值为 0.5，ties 归入高类别。低类别的结构零和同网格似然等价性由专门契约处理。空集不使用 M0c 质量分类器替代；五个空集身份具有相同 W68，仅用于种子配对。

### 3.2 学习器与校准

网络结构为 input→Linear(64)→LayerNorm→SiLU→Dropout(0.1)→Linear(64)→LayerNorm→SiLU→Linear(32)→SiLU→Linear(1)。训练使用 CPU float32、AdamW、学习率 0.001、weight decay 0.0001、batch size 1024；最多 200 epochs，验证绝对权重 AUC 最小改善 0.0001、patience 20。标准化和类内绝对权重归一化由 train 估计。物理产额保留权重符号，优化使用类内均值归一后的绝对权重 BCE。

AUC 为所选 checkpoint 在 validation 角色上的绝对物理权重 AUC。它不使用 assessment，不是 signed 概率 ROC，也不是 CDF 后的新 AUC。相同隐藏宽度仍随输入数改变参数量，因此当前比较没有完全排除容量差异。

本实验族使用 raw 分数；calibration 估计分数类别阈值，全部入选事件保留并恰好分到一个类别。本文没有把物理 CDF、对抗训练或矩阵元结果混入 off-only 表格。这些实现的独立方法见[方法文档](../docs/methods-and-evaluation.md)。

## 4 模板、推断与不确定度

### 4.1 共同网格与 T1

各候选使用共同质量边界、两个分数类别及 signed 物理产额。协议初始质量箱宽为 1 GeV，但本次实际冻结边界为 **[105,140] GeV**。因此非空模型的最终观察量至多为该质量窗内两个类别的计数，M0off 为一个非零计数箱；质量坐标仍存在于流程中，但质量峰的箱间形状已不再保留。这是解读全部增益的关键条件。不得将本次空集称为保留精细质量谱的基线，也不能据此证明超越质量峰的判别信息增量。

似然采用

\[
\mathcal L(\mu,\theta)=\prod_{c,j}\operatorname{Pois}(n_{cj}\mid\mu s_{cj}(\theta)+b_{cj}(\theta))\prod_a\pi_a(\theta_a).
\]

当前运行采用 pyhf 0.7.6 的 T1 shapesys 模型，对正产额 y 和方差 σ² 使用 τ=y²/σ² 的辅助 Poisson 约束；过程／箱按契约独立。模型一般背景及实现分别见 [R15–R21](references/references.md)。当前数值参考来自自动软件材料，signed-MC 的独立适用性参考仍待补齐。label_level_legacy 支持不能提升为逐物理背景过程的独立验证。

剖面统计量为 q(μ)=−2 log[L(μ,θ̂̂)/L(μ̂,θ̂)]，区间使用 χ² 的一个自由度临界值，置信水平为 0.68 和 0.95，μ∈[0,20]。缺少有效上端点或拟合失败均保留失败状态；搜索上界不能直接充当有效区间上限。Asimov 宽度是期望精度指标，不是实测 μ 的误差。

### 4.2 主要比较量与精确归因

在 μ=1、10 fb⁻¹ 下定义

\[
W_{68}(S,s)=\mu_{\rm upper}-\mu_{\rm lower},\quad
\Delta_s(L,R)=W_{68}(L,s)-W_{68}(R,s),\quad
I_s(L,R)=1-\frac{W_{68}(L,s)}{W_{68}(R,s)}.
\]

对每个配对量先在同种子计算，再取五种子中位数；中位数的差／比不替代配对差／比的中位数。所有 80 个身份必须完整，所有 105 对非空子集比较保留。BC、AC 为探索选择的紧凑比较，不追溯标为确认性预注册候选。

对 N={A,B,C,D}，令 v_s(S)=−W68(S,s)，计算

\[
\phi_{G,s}=\sum_{S\subseteq N\setminus\{G\}}\frac{|S|!(3-|S|)!}{4!}[v_s(S\cup\{G\})-v_s(S)]
\]

以及全部 24 个条件二阶差分 Δ_GH v_s(S)=v_s(S∪{G,H})−v_s(S∪{G})−v_s(S∪{H})+v_s(S)。逐种子满足 Σ_G φ_G,s=v_s(N)−v_s(∅)，逐组中位数一般不满足同一求和关系。贡献的单位为 μ 区间宽度，不能称为物理信息百分比。

训练种子稳定性区间枚举全部 5⁵=3125 个有放回的有序联合种子向量，对每个统计量的中位数取线性 16/84 和 2.5/97.5 百分位数。它仅描述共享当前 MC 条件下的训练种子稳定性。105 对区间为逐对区间，不具同时覆盖或多重比较显著性保证。

### 4.3 MC bootstrap、Toy 与 T2

固定网络的事件 MC bootstrap 分别对 calibration/template 物理事件组执行 200 个共同有放回多项式重数抽样（每个角色保持原事件组抽样总数），seed=42001，重估 raw 阈值并重建模板、推断和归因，固定名义质量网格。全部 200 个完整副本有效才发布正式百分位区间；成功副本子集只具条件诊断意义。该层不包含重训练或 assessment 母样本不确定性，不能与训练种子区间直接相加。

当前默认评估采用五个训练种子区块，每块 16 个候选。model-self 和 assessment 分别在 μ=0、1、2 生成每候选 500 个 Toy；T2 在 μ=1 使用每种子 20 个 calibration 外层副本，每个 100 个内层 Toy。T2 的独立流程单位为 20 个外层副本，不能把 2000 个内层拟合当作 2000 个独立的无条件校准实验。

候选间采用共同总 Poisson 计数和单调类别分配的人工共同随机数（CRN）耦合。它保持各候选边缘 Poisson 分布，但不复现物理事件跨模型协方差。不同训练种子间也没有 Toy-index 物理配对。报告固定标注 physical_event_pairing=false、primary_claim_eligible=false；独立类别分配的敏感性仍为 pending。文件中 generated_physical_toys 为保留字段名，不构成物理事件配对的证据。

覆盖同时保留有效拟合条件下的覆盖 K/N_valid、计划分母下的成功且覆盖 K/N_planned、Wilson 区间及失败率。五种子汇总为描述性中位数，不合并成独立 MC 试验。在 500 个条件 Toy 下，名义 68% 和 95% 覆盖的二项标准误差约为 2.09 和 0.97 个百分点；这些数字不是中位覆盖率的误差。Toy 检查不会自动校准临界值。

### 4.4 冻结、访问与完成状态

J0/J1 在 freeze 前检查模板边缘支持；J1 使用 200 次事件组 Bernoulli thinning，要求每种子零失败。本次两门通过，且记录 assessment_payload_read=false。工程筛查不能替代 bootstrap、prospective assessment 或物理适用性验证。

分析冻结模型、映射、模板、质量边界和预算后建立访问 claim。此次 access receipt 为 single_researcher_self_review，independent=false；自动 P0/T1 材料不授予独立科学资格。当前 h4l_all.py 默认可生成这种自审，独立审核需外部绑定材料。已打开总体不能靠改名、重签协议或换种子恢复独立性。

## 5 运行结果

### 5.1 全部组合的预期宽度

下表来自 nominal Asimov，而非 assessment 上重新优化后的结果。范围表示五个训练种子的最小／最大值，不是 MC 置信区间。空集相同，故此处相对空集的配对改善中位数也等于用宽度中位数计算的比值。

| 组合 | 输入数 | W68 中位数 | 五种子最小–最大 | 相对空集改善 | 验证 AUC 中位数 |
|---|---:|---:|---:|---:|---:|
| BC | 6 | 1.511617 | 1.510597–1.519604 | 9.143% | 0.813139 |
| AC | 10 | 1.515244 | 1.497197–1.517854 | 8.924% | 0.877541 |
| ABC | 14 | 1.521157 | 1.515306–1.530425 | 8.569% | 0.861716 |
| BCD | 11 | 1.524459 | 1.510199–1.528379 | 8.371% | 0.828307 |
| ABCD | 19 | 1.535930 | 1.529465–1.548047 | 7.681% | 0.846351 |
| B | 4 | 1.560187 | 1.555102–1.567178 | 6.223% | 0.757807 |
| BD | 9 | 1.561357 | 1.555593–1.574187 | 6.153% | 0.756259 |
| ABD | 17 | 1.573683 | 1.564355–1.595962 | 5.412% | 0.762427 |
| AB | 12 | 1.575967 | 1.567645–1.583937 | 5.275% | 0.755419 |
| ACD | 15 | 1.578276 | 1.522365–1.588725 | 5.136% | 0.788580 |
| C | 2 | 1.591920 | 1.591568–1.592885 | 4.316% | 0.690957 |
| CD | 7 | 1.600086 | 1.586208–1.607355 | 3.825% | 0.688374 |
| A | 8 | 1.622891 | 1.615166–1.631261 | 2.454% | 0.683600 |
| AD | 13 | 1.628972 | 1.622602–1.635079 | 2.089% | 0.684562 |
| D | 5 | 1.659076 | 1.653873–1.662969 | 0.279% | 0.559358 |
| M0off（空集） | 0 | 1.663723 | 1.663723–1.663723 | 0.000% | — |

BC 的宽度中位数最低，但逐种子冠军为 42:AC、43:BC、44:BC、45:BCD、46:AC。BC 和 AC 均没有在全部种子排名第一。ACD 的宽度范围为 1.522365–1.588725，显示其训练种子波动较大。

### 5.2 紧凑组合与完整表示

| 比较（左／右） | 配对 ΔW68 中位数 | 配对相对改善中位数 | 95% 种子稳定性区间（改善） | 左侧胜出种子数 |
|---|---:|---:|---:|---:|
| AC / BC | +0.001876 | -0.124% | [-0.361%, +0.943%] | 2/5 |
| AC / ABCD | -0.021913 | +1.425% | [+0.930%, +3.285%] | 5/5 |
| BC / ABCD | -0.019951 | +1.299% | [+1.031%, +2.364%] | 5/5 |
| ABC / ABCD | -0.014159 | +0.926% | [+0.490%, +1.737%] | 5/5 |

BC、AC 均在 5/5 个种子具有比 ABCD 更窄的名义区间，但 AC 与 BC 的配对区间跨零。五种子稳定性不能补足有限 MC 误差，也不能把探索筛选后的胜出计数转成确认性显著性结论。当前数据支持两个紧凑候选，不支持唯一最优子集或正式非劣性。

AC 的验证 AUC 中位数为 0.877541，高于 BC 的 0.813139；BC 的 W68 中位数却更小。ABCD 的 AUC 也高于 BC，但宽度更大。十五个候选中位数的 AUC–W68 Pearson 相关系数为 −0.9448，Spearman 为 −0.9107：整体关联较强，局部排名仍有反转。该相关性为同一共享样本中的描述统计，没有独立显著性检验。

### 5.3 贡献与互补性

| 组 | Shapley 中位数 | 95% 训练种子稳定性区间 |
|---|---:|---:|
| A | +0.015023 | [+0.010241, +0.019018] |
| B | +0.062223 | [+0.048518, +0.068939] |
| C | +0.060943 | [+0.054209, +0.063676] |
| D | -0.011103 | [-0.016000, -0.001804] |

B、C 是主要正贡献组，A 较小，D 在所有五个种子为负。不能仅由 B、C 中位数的细微差异断言 B 的真实贡献大于 C；也不能由 D 为负推断衰变角没有物理信息。

AC 在空集条件下的二阶差分中位数为 +0.042459，95% 种子稳定性区间为 [+0.028091,+0.053053]，支持当前价值函数下的互补性。AB 对应 −0.053436，区间 [−0.065367,−0.043438]。AB 在给定 C 时为 −0.082098，区间 [−0.104377,−0.080013]。负交互可能反映预测冗余、学习和压缩限制，不能归为唯一物理机制。

### 5.4 覆盖与重复校准

| 母模板／层次 | 注入 μ | 组合 | 68% 覆盖率中位数 | 95% 覆盖率中位数 |
|---|---:|---|---:|---:|
| assessment | 0 | M0off | 0.8800 | 0.9900 |
| assessment | 0 | BC | 0.8940 | 0.9800 |
| assessment | 0 | AC | 0.9180 | 0.9940 |
| assessment | 0 | ABCD | 0.9100 | 0.9920 |
| assessment | 1 | M0off | 0.6200 | 0.9440 |
| assessment | 1 | BC | 0.6680 | 0.9600 |
| assessment | 1 | AC | 0.6340 | 0.9660 |
| assessment | 1 | ABCD | 0.6340 | 0.9700 |
| assessment | 2 | M0off | 0.6520 | 0.9360 |
| assessment | 2 | BC | 0.6580 | 0.9300 |
| assessment | 2 | AC | 0.6540 | 0.9300 |
| assessment | 2 | ABCD | 0.6600 | 0.9300 |
| t2 | 1 | M0off | 0.6420 | 0.9510 |
| t2 | 1 | BC | 0.6660 | 0.9535 |
| t2 | 1 | AC | 0.6480 | 0.9645 |
| t2 | 1 | ABCD | 0.6500 | 0.9650 |

表内为五种子覆盖率的中位数，T2 先在每种子的 20 个外层副本汇总。全部 15 个 assessment 单元完成 120000 次有效拟合；5 个 T2 单元完成 160000 次有效拟合，记录的失败率均为零。拟合有效表示计算产生有效结果，不表示覆盖通过科学验证。

μ=1 时，BC 的 68% 条件覆盖较接近名义值，AC/ABCD 的数值较低；T2 同样显示名义 68% 水平下的偏低趋势。没有外层不确定度及独立科学资格，不能据此宣称欠覆盖显著、BC 已有可靠覆盖，或以覆盖再次选择候选。μ=0 的高覆盖与物理边界下的保守行为相容，但尚未通过独立对照确证原因。偏差、pull 及真实来源的系统变化不因覆盖表存在而自动获验证。

### 5.5 完整性与统计支持失败

| 评价层 | 计划 | 本次终态 |
|---|---|---|
| Nominal Asimov | 80 个身份 | 80/80 有效 |
| MC bootstrap | 200 个完整副本 | 161 有效、39 不完整（19.5%） |
| Model-self，μ=0 | 5 个种子区块 | 3 有效，43/44 为 blocked_consumed_budget |
| Model-self，μ=1 | 5 个种子区块 | 4 有效，45 为 blocked_consumed_budget |
| Model-self，μ=2 | 5 个种子区块 | 5 有效 |
| Assessment，μ=0、1、2 | 各 5 个区块 | 15/15 有效；非独立自审 |
| T2，μ=1 | 5 个区块 | 5/5 有效 |
| 独立类别分配敏感性 | 需绑定执行预算 | pending |
| 总报告 | 36 个科学单元及报告 | incomplete |

bootstrap 的 39 个失败副本共包含 49 个候选 insufficient_statistics 状态：D/seed42 为 37 次，D/seed43 为 5 次，D/seed44 为 4 次，ACD/seed46 为 2 次，AC/seed46 为 1 次。同一副本可涉及多个候选，因此 49 不能作为副本失败数。全部 148 条正式 bootstrap 不确定度导出记录均为 bootstrap_incomplete，区间为空。J1 通过并不与此矛盾：筛查抽样、支持对象和完整推断 bootstrap 的要求不同。

这些结果说明 D 的部分模型在重采样下支持脆弱，但不证明负权重抵消是唯一原因。不能删除 D 或失败副本后重新把同一评估称为完整确认。三处 model-self 的预算阻断也不能当作零失败或由其他种子代替。

## 6 讨论与局限

当前最有依据的结论是：在固定模型、raw 类别压缩和单质量箱 T1 流程中，紧凑输入可以获得比完整输入更窄的 nominal Asimov 区间。它可能来自冗余、有限学习能力、参数量、类别划分和样本支持的共同影响，尚不能归因为独立物理自由度的增加。尤其不能把单质量箱的结果推广为精细质量谱下的额外运动学收益。

有限 MC 和独立性是主要证据限制。五个训练种子共享样本，200 个 bootstrap 中 39 个不完整，自动 P0/T1 缺少独立物理和数值参考，assessment 使用自审；人工 CRN 也不提供物理事件协方差。有关有限 MC 可能造成区间欠覆盖的研究 [R29](references/references.md) 支持单独检查覆盖的必要性，但其特定假设不能直接证明本次偏差的成因。

BC/AC 是探索候选；Shapley 公理不保证最优子集选择 [R24](references/references.md)。少特征不等于更省训练 MC，本次没有训练样本量曲线、容量匹配确认或独立非劣性证据。MELA、物理 CDF、对抗训练、跨 release 以及生成器／探测器变化均属于其他实验范围，不借本次结果宣称优越性或稳健性。

后续确认须使用具有合法历史和来源证据的独立总体，事先固定候选、质量网格、统计支持、误差与覆盖判据。不能依据已打开 assessment 调整阈值、删减组合、重定临界值或选择分箱后仍称独立验证。现有结果作为探索证据保留；拟合或支持失败同样属于研究结果。

## 7 结论

在本次受控 H→ZZ*→4ℓ MC、无显式 m4l 分类器输入和单质量箱分析中，BC 与 AC 的 W68 相对常数基线分别缩小 9.143% 和 8.924%，相对完整 ABCD 的配对改善中位数为 1.299% 和 1.425%。B、C 为主要正贡献组，D 在当前流程中为负贡献；AUC 的整体关联不能消除其与推断排名的局部差异。

本实验提供了完整 nominal 组合归因和已执行的条件覆盖诊断，同时暴露出 bootstrap 统计支持缺口。由于整体评价不完整、独立审核和适用性参考缺失，本结论限于探索性 MC 技术研究。独立确认的精度优势、可靠覆盖、样本节省和物理稳健性仍待验证。

## 参考文献与复现说明

文内采用稳定 R 键，完整书目、发表版本、核验层级与使用限制见[参考文献与引用计划](references/references.md)，本次 SciSpace 查询见[检索记录](references/literature-search-log.md)。本次补充检索为题名／摘要级定向检索，不代表全文精读或系统综述。

核心方法对应 R14（INFERNO）、R15（Asimov／剖面似然）、R16–R21（有限 MC 与 pyhf）、R22–R25（归因与选择）、R29（欠覆盖）。项目方法以[文档索引](../docs/README.md)和绑定协议为准；当旧 docs 中的默认版本叙述与当前实现不同，以实际运行协议、manifest 和源码为此次结果依据。

[结果证据索引](result-evidence.md)记录当前代码与实际运行代码的区别、所有数值来源及校验范围。此次论文更新读取已发布结果并重算汇总，没有重训模型、重新生成 Toy 或重开原始数据；没有把历史软件测试数目当作当前科学验证结果。
