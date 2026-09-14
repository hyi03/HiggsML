# 物理期刊论文参考文献与具体引用计划

整理日期：2026-09-14。对应 [manuscript.md](manuscript.md) 的质量条件判别、信号强度推断与从属样本效率研究。检索使用 **SciSpace**，并以 Crossref、INSPIRE-HEP、CERN Open Data 等公开来源补充核验；[检索记录](literature-search-log.md) 保存查询与候选结果。

本文档面向物理期刊的方法与计算研究论文写作。引用目的在于说明物理动机、已有方法、本文差异和统计假设，不能替代本项目的完整 MC 结果。当前稿件仍缺冻结的主比较、独立矩阵元参考、覆盖与有来源的系统变化证据；增加引用不改变这一状态。

## 使用规则与核验深度

- **A：书目交叉核验，内容摘要级核验。** 已核对 DOI 注册元数据或 INSPIRE 记录；不代表逐页读过全文。
- **B：SciSpace 题名、作者与摘要级核验。** 提供预印本或官方入口；尚未完整核验出版字段。
- **D：官方数据／软件来源。** 数据集或版本文档，独立于研究论文引用。
- 每条“拟引用内容”是针对本项目的写作计划／转述，不是原文引语。涉及定理条件、算法实现、公式编号和数值比较，投稿前应在全文中逐项核对；本次不编造页码或图号。
- 优先引用正式发表版本，并附 arXiv；预印本、会议文献、技术报告明确注明。短作者表列全，多作者使用首作者 et al.，大型实验使用合作组作者名。R 编号为稳定引用键，不是正文最终排序。
- 每条标注“核心”“相关工作”或“条件引用”；条件引用仅在正文确实讨论该内容时采用，不为增加数量而引用。

## 章节与论证对应

| 稿件位置／需要支持的论点 | 推荐条目 | 本文需要自己给出的证据 |
|---|---|---|
| §1、§3：四轻子质量与衰变运动学、矩阵元参照 | R01–R03 | 角度约定、输入信息匹配、独立 MELA 数值参考 |
| §2：2020 受控 MC 来源 | R04、R05 | DSID、生成链、归一化、事件身份和选择审计 |
| §1、§4：质量雕刻、训练与后处理方法差别 | R06–R12、R27 | 本项目 raw/CDF、对抗训练及有限校准对照 |
| §3：表示与信息、为什么 AUC 不是最终目标 | R13、R14、R28 | M5/M4 配对 W68、质量基线和容量对照 |
| 似然与评价章节：Asimov、有限 MC、区间覆盖 | R15–R21 | 带符号组方差、shapesys 适用性、Toy 覆盖 |
| 特征归因与样本效率章节 | R22–R26 | 同流程空集、全部子集、实际学习曲线与独立确认 |

## 一、四轻子物理与数据来源

### R01 — Avery2013MEKD（核心；原稿 [1]）

**标准书目：** P. Avery et al., “Precision studies of the Higgs boson decay channel H → ZZ → 4ℓ with MEKD,” *Physical Review D* **87**, 055006 (2013). [DOI](https://doi.org/10.1103/PhysRevD.87.055006)；[arXiv:1210.0896](https://arxiv.org/abs/1210.0896)。

- **拟引用内容与位置：** §1、§3 的矩阵元基线段落：四轻子运动学可用于信号／连续 ZZ 区分及自旋宇称判别；MEKD 用完整领先阶矩阵元构造判别量。扩展到 4e/4μ 时，引用其关于相同轻子排列干涉重要性的讨论。
- **建议转述：** “矩阵元判别为四轻子末态中衰变运动学的判别能力提供了物理参照。”
- **边界：** MEKD 与本项目拟接入的 MELA 不是同一个软件；该论文不能证明本项目角度重建、概率归一化或 backend 已正确。
- **核验：A。** SciSpace 摘要及 Crossref 期刊元数据。索引将预印本记录标为 2022，不采用该年份；正式出版为 2013。

### R02 — CMS2017H4l（核心；原稿 [2]）

**标准书目：** CMS Collaboration, A. M. Sirunyan et al., “Measurements of properties of the Higgs boson decaying into the four-lepton final state in pp collisions at √s = 13 TeV,” *Journal of High Energy Physics* **11** (2017) 047. [DOI](https://doi.org/10.1007/JHEP11(2017)047)；[arXiv:1706.09936](https://arxiv.org/abs/1706.09936)。

- **拟引用内容与位置：** §1 的实验物理动机以及 μ 定义附近：H→ZZ→4ℓ 是研究 Higgs 性质的重要通道，真实实验将重建和统计推断结合，测量信号强度等量。
- **建议转述：** “四轻子通道已被用于信号强度和 Higgs 性质的实验研究，因而本文以预期 μ 精度作为方法比较目标。”
- **边界：** CMS 的 35.9 fb⁻¹ 数据分析不等于本项目的 ATLAS 2020 MC、2e2μ 子集及 10 fb⁻¹ 设置；不迁移选择、系统误差、产额或实验精度。
- **核验：A。** SciSpace 摘要、Crossref 元数据；具体分类与矩阵元定义仍需全文定位。

### R03 — Gritsan2020JHUGen（核心；原稿 [8]）

**标准书目：** A. V. Gritsan, J. Roskes, U. Sarica, M. Schulze, M. Xiao and Y. Zhou, “New features in the JHU generator framework: Constraining Higgs boson properties from on-shell and off-shell production,” *Physical Review D* **102**, 056022 (2020). [DOI](https://doi.org/10.1103/PhysRevD.102.056022)；[arXiv:2002.09888](https://arxiv.org/abs/2002.09888)。

- **拟引用内容与位置：** 矩阵元方法章节：JHUGen/MELA 框架提供事件生成、矩阵元分析、最优判别和重加权等能力；用作实际 MELA 后端的方法来源。
- **建议转述：** “矩阵元参照拟使用 JHUGen/MELA 框架，并单独固定过程假设及软件版本。”
- **边界：** 框架支持 off-shell、反常耦合等功能，不表示本文使用或验证了这些功能。须另记录版本、过程开关、生产信息与探测器处理；不据此声称 NN 超越最优矩阵元。
- **核验：A。** INSPIRE 摘要、DOI 与 Crossref 作者／出版信息。

### R04 — ATLAS2020FourLeptonCollection（核心，数据引用）

**标准书目：** ATLAS Collaboration, “ATLAS 13 TeV samples collection at least four leptons (electron or muon), for 2020 Open Data release,” *CERN Open Data Portal*, record 15005 (2020), dataset collection. [DOI](https://doi.org/10.7483/OPENDATA.ATLAS.2Y1T.TLGL)；[官方记录](https://opendata.cern.ch/record/15005)。访问日期：2026-09-14。

- **拟引用内容与位置：** §2.1 数据来源：明确 2020 release 的至少四轻子 collection。本文实际成员由仓库契约限定为 `mc_345060.ggH125_ZZ4lep.4lep.root` 和 `mc_363490.llll.4lep.root`。
- **建议转述：** “本研究使用 ATLAS 2020 开放数据发布中四轻子集合的两个受控模拟成员；输入身份由数据集契约绑定。”
- **边界：** 集合引用不授权分析其中真实数据，也不能替代两成员的生成器、截面与过滤效率来源。`llll` 文件名不能直接证明纯 qq̄→ZZ；2025 release 不能替代此引用。
- **核验：D。** 官方 record API 已核对题名、DOI 与发布年；成员选择来自当前 [数据集契约](../config/datasets/atlas2020_4lep.json)。本次只读元数据，未读取事件文件。

### R05 — Serkin2020OpenData（相关工作，会议文献）

**标准书目：** L. Serkin, “The release of the 13 TeV ATLAS Open Data: using open education resources effectively,” *EPJ Web of Conferences* **245**, 08026 (2020). [DOI](https://doi.org/10.1051/epjconf/202024508026)。

- **拟引用内容与位置：** 数据章节说明发布背景、开放教育资源及复现用途，配合 R04 区分“发布说明”与“实际数据集标识”。
- **建议转述：** “该发布面向开放教育资源使用；本文在其受控模拟样本上开展方法研究。”
- **边界：** 不用教育资源说明证明实验级系统误差模型完整，也不把这篇会议论文写成数据集 DOI。
- **核验：A。** SciSpace 检索与 Crossref 书目；具体发布范围需读全文。

## 二、质量去相关与条件变换

### R06 — Louppe2017Pivot（核心；原稿 [3]）

**标准书目：** G. Louppe, M. Kagan and K. Cranmer, “Learning to Pivot with Adversarial Networks,” *Advances in Neural Information Processing Systems* **30** (2017). [arXiv:1611.01046](https://arxiv.org/abs/1611.01046)。会议论文；预印本首发 2016。

- **拟引用内容与位置：** 对抗训练目标：通过 adversary 约束输出对 nuisance／保护变量的依赖，存在判别能力与稳健性的权衡；解释 λ 的角色。
- **建议转述：** “对抗目标可用于学习近似 pivotal 的输出，并通过惩罚强度控制分类与去相关的权衡。”
- **边界：** 本项目绝对权重背景、11 个质量箱及训练日程是自身协议，不是该文结论；训练完成不保证独立性或物理系统误差稳健性。
- **核验：B。** SciSpace 作者与摘要核验；会议卷页在最终参考文献导出前复核。

### R07 — Kasieczka2020DisCo（相关工作；原稿 [4]）

**标准书目：** G. Kasieczka and D. Shih, “Robust Jet Classifiers through Distance Correlation,” *Physical Review Letters* **125**, 122001 (2020). [DOI](https://doi.org/10.1103/PhysRevLett.125.122001)；[arXiv:2001.05310](https://arxiv.org/abs/2001.05310)。预印本题名为 “DisCo Fever: Robust Networks Through Distance Correlation”。

- **拟引用内容与位置：** 引言的替代去相关方法：用 distance correlation 惩罚非线性相关，可作为对抗训练以外的训练约束。
- **建议转述：** “距离相关正则化提供了另一种控制分类器输出与质量关系的训练方法。”
- **边界：** 本项目没有运行 DisCo 对照，不能写成已比较的模型；jet tagging 性能不能迁移成 H4l 精度改善。
- **核验：A。** SciSpace 摘要、Crossref 出版信息。

### R08 — Windischhofer2020Preserving（核心相关工作；原稿 [5]）

**标准书目：** P. Windischhofer, M. Zgubič and D. Bortoletto, “Preserving physically important variables in optimal event selections: a case study in Higgs physics,” *Journal of High Energy Physics* **07** (2020) 001. [DOI](https://doi.org/10.1007/JHEP07(2020)001)；[arXiv:1907.02098](https://arxiv.org/abs/1907.02098)。

- **拟引用内容与位置：** 引言中连接去相关和最终推断的段落：用可微互信息估计控制选择造成的分布变形，并在 H→bb 案例中研究信号强度提取。
- **建议转述：** “去相关应与最终信号提取结合评价，已有 Higgs 案例展示了这一分析思路。”
- **边界：** 此文最接近本文的分析目标，但末态、背景估计与训练方法不同；本文须解释四轻子表示比较和 signed-CDF 的额外问题，不能把一般思路宣称为首次提出。
- **核验：A。** SciSpace 摘要与 Crossref 作者、题名、出版信息。

### R09 — Klein2022ConditionalFlows（核心相关工作；原稿 [6]）

**标准书目：** S. Klein and T. Golling, “Decorrelation with conditional normalizing flows,” arXiv:2211.02486 (2022), preprint. [arXiv](https://arxiv.org/abs/2211.02486)；[预印本 DOI](https://doi.org/10.48550/arXiv.2211.02486)。

- **拟引用内容与位置：** 条件 CDF 章节：以保护变量为条件的可逆后处理，可以在固定保护变量时保持判别能力，并降低质量雕刻。
- **建议转述：** “条件可逆变换的思想说明，固定质量下的判别能力与全局质量相关性是不同问题。”
- **边界：** 本项目采用有限网格约束 CDF，存在 ties、平台和分箱，不能照搬连续 flow 的可逆性保证；该文也不验证 signed 权重构成的概率分布。
- **核验：A。** SciSpace 与 INSPIRE 摘要、作者、arXiv 一致；本次 INSPIRE 未提供期刊版本，按预印本列出，不假定已发表。

### R10 — Kitouni2021MoDe（相关工作；原稿 [7]）

**标准书目：** O. Kitouni, B. Nachman, C. Weisser and M. Williams, “Enhancing searches for resonances with machine learning and moment decomposition,” *Journal of High Energy Physics* **04** (2021) 070. [DOI](https://doi.org/10.1007/JHEP04(2021)070)；[arXiv:2010.09745](https://arxiv.org/abs/2010.09745)。

- **拟引用内容与位置：** 去相关动机与讨论：完全独立是避免背景局域伪结构的充分思路，但并非唯一要求；MoDe 允许更灵活的相关结构。
- **建议转述：** “控制有害的背景形状结构与要求严格统计独立并不等价。”
- **边界：** MoDe 的共振搜索与边带背景估计背景不等于本文共同模板似然；不把该文当作本文覆盖保证。
- **核验：A。** Crossref 及 INSPIRE 题名、作者与摘要；不要混入另一本题为 “Moments of Clarity” 的 2024 文献。

### R11 — Dolen2016DDT（相关工作）

**标准书目：** J. Dolen, P. Harris, S. Marzani, S. Rappoccio and N. Tran, “Thinking outside the ROCs: Designing Decorrelated Taggers (DDT) for jet substructure,” *Journal of High Energy Physics* **05** (2016) 156. [DOI](https://doi.org/10.1007/JHEP05(2016)156)；[arXiv:1603.00027](https://arxiv.org/abs/1603.00027)。

- **拟引用内容与位置：** 引言中 ROC/AUC 之外的分析要求：将质量／尺度相关性纳入 tagger 设计，以减轻选择对谱形的影响。
- **建议转述：** “分类器评价应同时考虑选择效率与对拟合观测量的形状影响。”
- **边界：** DDT 的特定变量修正不能等同于本项目完整条件 CDF；本文不声称执行了 DDT。
- **核验：A。** SciSpace 摘要与 Crossref 书目。

### R12 — Rosenblatt1952Transform（核心数学来源）

**标准书目：** M. Rosenblatt, “Remarks on a Multivariate Transformation,” *The Annals of Mathematical Statistics* **23** (3), 470–472 (1952). [DOI](https://doi.org/10.1214/aoms/1177729394)。

- **拟引用内容与位置：** `u=F_b(t|m)` 的概率论背景：条件分布变换用于将连续随机变量映射到标准概率坐标；正式正文应写明连续性与适用分布。
- **建议转述：** “理想连续条件分布下，条件概率积分变换给出固定质量的均匀背景坐标。”
- **边界：** 有符号经验累计和不是概率 CDF。非负、总产额守恒的拟合是本文额外的估计步骤，其偏差及不确定性须自行验证。
- **核验：A（仅书目）。** Crossref 作者、题名、卷页已核对；数学命题及条件尚须原文精读后最终引用。

## 三、表示选择与推断目标

### R13 — Datta2017Information（相关工作；原稿 [10]）

**标准书目：** K. Datta and A. J. Larkoski, “How much information is in a jet?”, *Journal of High Energy Physics* **06** (2017) 073. [DOI](https://doi.org/10.1007/JHEP06(2017)073)；[arXiv:1704.08249](https://arxiv.org/abs/1704.08249)。

- **拟引用内容与位置：** §3 和讨论中的表示研究动机：通过结构化运动学表示研究判别信息，而不是仅增加网络复杂度。
- **建议转述：** “基于受控物理表示的比较为研究可利用判别信息提供了一种方法论参照。”
- **边界：** 不把 jet 的相空间／信息结论推广为 decay7 充分性；本文重训练收益也不等于信息熵变化。
- **核验：A（书目）。** Crossref 元数据；内容保留为宽泛方法背景，正文的具体信息论主张须精读原文。

### R14 — DeCastro2019INFERNO（核心相关工作）

**标准书目：** P. de Castro and T. Dorigo, “INFERNO: Inference-Aware Neural Optimisation,” *Computer Physics Communications* **244**, 170–179 (2019). [DOI](https://doi.org/10.1016/j.cpc.2019.06.007)；[arXiv:1806.04743](https://arxiv.org/abs/1806.04743)。

- **拟引用内容与位置：** 引言的目标选择以及讨论：以参数不确定性为学习目标的 summary statistics，与普通分类损失训练存在区别，尤其在 nuisance 存在时。
- **建议转述：** “分类损失与推断目标并不相同，因此本文把 W68 作为主评价量，而将 AUC 用于训练诊断。”
- **边界：** 本项目仍是 BCE 训练、事后推断评价，没有实现 INFERNO；不能称为 inference-aware optimization，也不能声称优于它。
- **核验：A。** SciSpace 与 INSPIRE 摘要、期刊与 DOI。

## 四、似然、有限 MC 与覆盖

### R15 — Cowan2011Asymptotic（核心；原稿 [9]）

**标准书目：** G. Cowan, K. Cranmer, E. Gross and O. Vitells, “Asymptotic formulae for likelihood-based tests of new physics,” *European Physical Journal C* **71**, 1554 (2011); erratum **73**, 2501 (2013). [DOI](https://doi.org/10.1140/epjc/s10052-011-1554-0)；[勘误](https://doi.org/10.1140/epjc/s10052-013-2501-z)；[arXiv:1007.1727](https://arxiv.org/abs/1007.1727)。

- **拟引用内容与位置：** 剖面似然和 Asimov 定义处：nuisance profiling、渐近统计量分布以及代表性 Asimov 样本的预期灵敏度用途。
- **建议转述：** “采用 Asimov 区间宽度作预期精度指标，同时以伪实验单独检查有限样本覆盖。”
- **边界：** 渐近公式不保证 μ≥0 边界、稀疏箱及带符号有限 MC 下的 68% 覆盖。不能把 Asimov 宽度称为实测不确定度。
- **核验：A。** Crossref、INSPIRE 摘要及勘误记录；SciSpace 显示的 2022 年和不完整作者表已纠正。

### R16 — Barlow1993FiniteMC（核心）

**标准书目：** R. Barlow and C. Beeston, “Fitting using finite Monte Carlo samples,” *Computer Physics Communications* **77**, 219–228 (1993). [DOI](https://doi.org/10.1016/0010-4655(93)90005-W)。

- **拟引用内容与位置：** T0/T1 区别：MC 模板本身有统计涨落，拟合中应显式处理有限模拟统计，而非把估计模板视为精确期望。
- **建议转述：** “有限 MC 模板误差需要进入统计模型，经典处理见 Barlow–Beeston。”
- **边界：** 不将原始有限计数构造直接等同于当前 signed 权重有效计数 `shapesys` 近似；尤其需检验组相关性与抵消。
- **核验：A（书目）。** Crossref 题名、作者和页码；具体推导须全文核对。

### R17 — Cranmer2012HistFactory（核心，技术报告）

**标准书目：** K. Cranmer, G. Lewis, L. Moneta, A. Shibata and W. Verkerke, “HistFactory: A tool for creating statistical models for use with RooFit and RooStats,” CERN-OPEN-2012-016 (2012). [CERN 报告](https://cds.cern.ch/record/1456844)。

- **拟引用内容与位置：** 共同质量×类别模板似然：组合分箱样本、期望率与辅助约束的模型表达；为 pyhf 的 HistFactory 模型语义提供来源。
- **建议转述：** “分箱似然采用 HistFactory 模型表达，并通过 pyhf 执行推断。”
- **边界：** 这是技术报告，不伪装为期刊论文；不同 modifier 不可互换，报告本身不验证 signed 样本近似。
- **核验：A（报告书目）。** INSPIRE 报告号及五位作者；modifier 细节与版本文档联合核对。

### R18 — Heinrich2021pyhf（核心，软件论文）

**标准书目：** L. Heinrich, M. Feickert, G. Stark and K. Cranmer, “pyhf: pure-Python implementation of HistFactory statistical models,” *Journal of Open Source Software* **6** (58), 2823 (2021). [DOI](https://doi.org/10.21105/joss.02823)。

- **拟引用内容与位置：** 统计实现及复现章节：说明所用 HistFactory 的纯 Python 实现；应与 R19 的具体版本契约同时引用。
- **建议转述：** “似然构建与数值推断使用 pyhf，运行版本及模型规格随分析冻结。”
- **边界：** 软件论文不能证明当前模型选择、拟合收敛、有效计数或覆盖正确；不以搜索返回的演讲 Zenodo DOI 替代软件论文。
- **核验：A。** Crossref 作者、题名、出版年、卷与文章号；SciSpace 的实现摘要作补充背景。

### R19 — pyhf076Likelihood（核心，版本文档；原稿 [11]）

**标准书目：** pyhf developers, *pyhf documentation, version 0.7.6: Likelihood specification*. [版本文档](https://pyhf.readthedocs.io/en/v0.7.6/likelihood.html)。

- **拟引用内容与位置：** T1 方法及复现：具体采用 `shapesys`、独立 process/bin 的辅助 Poisson 约束，以及协议绑定的版本。
- **建议转述：** “T1 采用版本绑定的 shapesys 模型；有效计数映射和独立箱假设须由输入样本另行验证。”
- **边界：** 不把 `staterror`、`histosys` 与 `shapesys` 混写；文档引用之外仍需 run 中的软件版本和验证证据。
- **核验：D（仓库绑定，外部页面待复核）。** 链接与版本由当前方法文档核对，本次未重新读取该外部页面，不填虚假的网页访问日期。

### R20 — Mandrik2017NegativeMC（核心，会议文献）

**标准书目：** P. Mandrik, “The evaluation of the systematic uncertainties for the finite MC samples in the presence of negative weights,” *EPJ Web of Conferences* **158**, 06005 (2017). [DOI](https://doi.org/10.1051/epjconf/201715806005)；[arXiv:1708.07708](https://arxiv.org/abs/1708.07708)。

- **拟引用内容与位置：** 权重与 T1 适用性段落：有限 MC 且有负权重时，需要专门考虑模板统计建模及其近似。
- **建议转述：** “负权重使有限模板统计的概率建模更复杂，不能仅用非负样本的直觉解释有效计数。”
- **边界：** 文献题名中的 systematic 不意味着有限 MC 误差等于物理生成器／探测器系统误差；不证明本项目的独立箱近似适用。
- **核验：A。** SciSpace 摘要及 Crossref 作者、卷、文章号。

### R21 — Gluesenkamp2018WeightedMC（核心补充）

**标准书目：** T. Glüsenkamp, “Probabilistic treatment of the uncertainty from the finite size of weighted Monte Carlo data,” *European Physical Journal Plus* **133**, 218 (2018). [DOI](https://doi.org/10.1140/epjp/i2018-12042-x)；[arXiv:1712.01293](https://arxiv.org/abs/1712.01293)。

- **拟引用内容与位置：** 加权 MC 不确定性章节：支持把权重分布、有限模拟统计及概率模型假设作为明确的方法问题，而不只保存 sumw2。
- **建议转述：** “加权模拟预测的有限样本不确定性需要与所采用概率模型一致。”
- **边界：** 不假定其所有构造允许任意负权重或相关事件组；具体权重与独立性假设需原文核对。本文 `V_ab` 的组协方差实现仍需自身推导与验证。
- **核验：A。** SciSpace 摘要、Crossref 期刊书目；算法适用条件待全文精读。

## 五、特征归因、样本效率与确认

### R22 — Shapley1953Value（核心，原始数学来源）

**标准书目：** L. S. Shapley, “A Value for n-Person Games,” in *Contributions to the Theory of Games*, Vol. II, H. W. Kuhn and A. W. Tucker (eds.), Princeton University Press (1953), pp. 307–318. [DOI](https://doi.org/10.1515/9781400881970-018)。

- **拟引用内容与位置：** 分组 Shapley 公式及效率恒等式：按联盟大小加权的边际贡献分配。
- **建议转述：** “以特征组为参与者、重训练后负区间宽度为价值，按 Shapley 规则分配整个流程的增益。”
- **边界：** `v(S)=-W68(S)`、A/B/C/D、质量条件空集和网络种子均是本文定义；原始博弈论结果不证明物理因果性，也不自动证明特征选择最优。
- **核验：A（书目）。** Crossref 书名、作者、年代与页码；正式数学命题须核对原文。

### R23 — Covert2020SAGE（核心相关工作）

**标准书目：** I. Covert, S. M. Lundberg and S.-I. Lee, “Understanding Global Feature Contributions With Additive Importance Measures,” *Advances in Neural Information Processing Systems* **33** (2020). [官方论文入口](https://proceedings.neurips.cc/paper/2020/hash/c7bf0b7c1a86d5eb3be2c722cf2cf746-Abstract.html)；[arXiv:2004.00668](https://arxiv.org/abs/2004.00668)。

- **拟引用内容与位置：** 特征归因定义之前：说明全局预测能力归因与单事件 prediction explanation 的区别，以及交互的作用。
- **建议转述：** “本文采用流程级价值函数的全局归因，而不是解释单个事件的网络输出。”
- **边界：** 每个子集重新训练并重建推断链，不等于直接调用 SAGE 或 SHAP；不能把本文 W68 归因解释为论文中损失价值的同一估计量。
- **核验：B。** SciSpace 作者、摘要及官方会议入口；卷页待正式导出时复核。

### R24 — Fryer2021Selection（核心限制来源）

**标准书目：** D. Fryer, I. Strümke and H. Nguyen, “Shapley Values for Feature Selection: The Good, the Bad, and the Axioms,” *IEEE Access* **9**, 144352–144360 (2021). [DOI](https://doi.org/10.1109/ACCESS.2021.3119110)。

- **拟引用内容与位置：** 紧凑候选选择及讨论：归因公理的合理性不自动转化为子集选择规则的合理性；Shapley 排名不等于最佳子集。
- **建议转述：** “候选选择直接比较子集的配对 W68，并另行确认，而不简单删除 Shapley 最小的特征组。”
- **边界：** 该文对特征选择的批评不否定本文在固定价值函数下报告归因；支持的是解释与选择分离。
- **核验：A。** SciSpace 摘要与 Crossref 作者、页码。

### R25 — Cawley2010SelectionBias（核心）

**标准书目：** G. C. Cawley and N. L. C. Talbot, “On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation,” *Journal of Machine Learning Research* **11**, 2079–2107 (2010). [官方论文](https://jmlr.org/papers/v11/cawley10a.html)。

- **拟引用内容与位置：** 五角色分离、冻结以及样本效率独立确认：模型选择准则也有方差，对其过度优化会引入评价偏差。
- **建议转述：** “紧凑候选的探索选择与确认评价使用分离总体，并保留全部选择历史。”
- **边界：** 固定角色和重新划分历史样本不能自动恢复从未被反馈污染的独立性；五个训练种子也不是五份独立 MC。
- **核验：A。** SciSpace 摘要与 JMLR 官方页面的作者、年、卷及 2079–2107 页已交叉核对；正文具体设计仍是本项目协议。

### R26 — Mohr2022LearningCurves（相关工作，暂用预印本）

**标准书目：** F. Mohr and J. N. van Rijn, “Learning Curves for Decision Making in Supervised Machine Learning — A Survey,” arXiv:2201.12150 (2022). [arXiv](https://arxiv.org/abs/2201.12150)。本次未确定对应正式出版版本，暂按预印本引用。

- **拟引用内容与位置：** 样本效率定义：学习曲线刻画训练资源与性能之间的关系；与训练 epoch 曲线、运行时间区分。
- **建议转述：** “以实际物理训练事件组数为横轴研究性能变化，将训练样本效率与计算效率分开。”
- **边界：** 综述不提供本项目的样本节省倍数，不证明曲线必然单调，也不支持观测范围外推。非劣性容差与 bootstrap 规则需独立注册。
- **核验：B。** SciSpace 题名、作者与摘要。

## 六、较新研究与投稿定位

### R27 — Algren2024OptimalTransport（相关工作）

**标准书目：** M. Algren, J. A. Raine and T. Golling, “Decorrelation using optimal transport,” *European Physical Journal C* **84**, 579 (2024). [DOI](https://doi.org/10.1140/epjc/s10052-024-12868-6)；[arXiv:2307.05187](https://arxiv.org/abs/2307.05187)。

- **拟引用内容与位置：** 相关工作／讨论：去相关已拓展到连续多维特征空间和多分类输出的 optimal transport 后处理。
- **建议转述：** “条件变换之外，最优传输也被用于分类输出的去相关；本文聚焦一维分数在有限 signed-MC 下的校准与推断。”
- **边界：** 不声称提出一般去相关的新范式；本文没有 optimal transport 实验，不进行性能排名。
- **核验：A。** SciSpace 摘要及 Crossref 书目。

### R28 — Maitre2025Symmetries（相关工作）

**标准书目：** D. Maître, V. S. Ngairangbam and M. Spannowsky, “Optimal equivariant architectures from the symmetries of matrix-element likelihoods,” *Machine Learning: Science and Technology* **6**, 015059 (2025). [DOI](https://doi.org/10.1088/2632-2153/adbab1)；[arXiv:2410.18553](https://arxiv.org/abs/2410.18553)。

- **拟引用内容与位置：** 表示与样本效率讨论：矩阵元似然所包含的对称性可指导网络设计，最大的形式对称性未必适合实际碰撞机判别问题。
- **建议转述：** “物理表示与网络归纳偏置可影响有限样本学习效率，需与额外输入信息的贡献区分。”
- **边界：** 文献示例是双 Higgs→四 b，不是本项目 H4l；不据此断言实验室系变量必然提升精度或 decay7 非充分。
- **核验：A。** SciSpace 摘要与 Crossref 作者、期刊、文章号。

### R29 — Alexe2026Undercoverage（核心新补充）

**标准书目：** C.-A. Alexe, J. Bendavid, L. Bianchini and D. Bruschini, “Under-coverage in high-statistics counting experiments with finite MC samples,” *Nuclear Instruments and Methods in Physics Research A* **1086**, 171360 (2026). [DOI](https://doi.org/10.1016/j.nima.2026.171360)；[arXiv:2401.10542](https://arxiv.org/abs/2401.10542)。

- **拟引用内容与位置：** 覆盖评价动机及局限：即使数据和模拟箱计数看似较大，有限 MC 与 nuisance 的组合仍可能使渐近区间欠覆盖。
- **建议转述：** “高计数本身不足以保证渐近覆盖，因此本研究将覆盖检查与 Asimov 精度比较分别报告。”
- **边界：** 文献不意味着本项目一定欠覆盖；更不能用该文数值替代自己的 Toys。本文低支持、负权重场景的细节仍需专门验证。
- **核验：A。** SciSpace 发现预印本；INSPIRE 核对完整作者、摘要及 2026 正式期刊信息。

## 原稿占位引用替换映射

保持原稿现有编号时，可按下表补全书目；新增引用在实际插入正文后统一重新编号。本次未批量改动正文数字引用。

| 原稿编号 | 文献键 | 需要修正／补充 |
|---|---|---|
| [1] | R01 | 补完整题名及期刊 DOI |
| [2] | R02 | 补合作组、完整题名与 DOI |
| [3] | R06 | 区分 2016 预印本与 2017 会议论文 |
| [4] | R07 | 正式题名与 DisCo 预印本题名不同 |
| [5] | R08 | 补作者重音、题名与 DOI |
| [6] | R09 | 按已核验预印本状态列出 |
| [7] | R10 | 使用 MoDe 正确正式题名和作者 |
| [8] | R03 | 将“JHU framework”补为具体论文 |
| [9] | R15 | 补第四作者、正式期刊与勘误 |
| [10] | R13 | 补 JHEP 正式引用，限制 jet 类比 |
| [11] | R19 + R18 | 保留版本文档，另加软件论文 |

## 与已有工作的差异：建议如何写贡献

| 不宜作为新颖性主张 | 可检验的本文差异 | 主要对照文献 |
|---|---|---|
| 首次将 ML 用于四轻子或首次使用矩阵元 | 在匹配质量信息与后处理条件下，比较 decay7 与 engineered19 的 μ 精度 | R01–R03、R14 |
| 首次提出质量去相关／条件可逆变换 | 有限 signed-MC 条件 CDF、校准不确定性和共同模板推断的受控比较 | R06–R12、R20、R21、R27 |
| Shapley 揭示了唯一物理信息或因果贡献 | 对固定重训练与推断流程的区间宽度增益作组归因 | R22–R24 |
| 更少特征就证明更省 MC | 冻结候选后，以训练事件组数学习曲线和独立非劣确认评价样本效率 | R25、R26、R28 |
| 软件通过或区间变窄就说明测量可靠 | 配对主结果、有限 MC 适用性、偏差／覆盖及真实来源变化共同限定结论 | R15–R21、R29 |

现阶段适合准备“物理问题驱动的方法研究”稿件；论文贡献需由完整 MC 比较支持，可接受无增益或适用性受限的结果。不能仅凭本次定向检索声称某方法“首次”，也不能把受控模拟结果写成 ATLAS/CMS 测量。

## 投稿前仍需补齐的引用与证据

1. **输入生成链来源。** 按两个实际 DSID 的 metadata 确定 generator、parton shower、PDF、截面、过滤效率、负权重成因后，再选择对应生成器论文。当前不猜测应引用哪一个产生链。
2. **重建和 MELA 精确定义。** 对照全文确认 Z1/Z2、负电轻子角度、FSR、生产信息、传递函数及软件版本；给出独立验证，而不仅是框架论文。
3. **signed-CDF 估计器。** R12 仅是概率变换背景；需给出当前非负约束估计的目标函数、总量约束、误差处理、偏差及覆盖。不能暗示上述文献已验证此具体组合。
4. **非劣性与重采样。** 如论文保留确认性非劣性结论，补充与最终单侧判据、置信水平和配对事件组 bootstrap 相符的统计来源；目前不引用不匹配的临床规则替代方法论证。
5. **全文定位。** A/B 条目均需针对实际使用的公式、假设、算法和数字精读；建立最终正文句子—原文位置对应。未核验的数字不进入结果或比较表。
6. **近期检索更新。** 本次收录到 2026 的相关记录，但非穷尽检索；确定投稿期刊和冻结结果后，再按具体主张更新相关工作并检查预印本正式版本。
