# 优先级 4：物理来源与最小基线准备度审计

日期：2026-09-23。对应 [解决方案分析第 6 节](../4-Reviews/research-quality-audit-2026-09-23-review-confirm.md)。工作树基线 HEAD：`5275fc586ec25d41e84459e665c168dba6a31671`；HEAD 不包含启动时已存在的未提交修改，具体字节基线见本地证据清单。

**已完成 F2 运行期间可以独立开展的来源核查与基线设计。当前归一化常数与官方固定版本相符，但数据用途、事件修正、生成过程及独立角／概率参考仍有缺口；尚不能启动并宣称完成“利用质量峰后的可靠精度增益”验证。**

本次只新增审计文档及忽略目录内的证据、研究脚本。没有修改 F2 代码、协议、输入、预算或随机流，没有读取 ROOT／事件载荷、新 assessment 数值，也没有启动训练、正式 bootstrap、Toy 或 T2。既有 F4/F11/F12 修改保持原样。本文的“完成”指审计工作，非问题 F1/F6/F7 已全部解决。

## 1. 证据与核查方法

本地证据根：[priority45-audit-20260923-001](../../var/priority45-audit-20260923-001/)。它属于忽略目录，应随研究档案另行保存，不提交生成产物。

- [public-sources/receipts.json](../../var/priority45-audit-20260923-001/public-sources/receipts.json)：六份公开记录／源码的 URL、下载时间、大小及 SHA-256。
- [public-supplement/receipts.json](../../var/priority45-audit-20260923-001/public-supplement/receipts.json)：三份固定版本 HZZ 示例源码。
- [local-metadata/receipts.json](../../var/priority45-audit-20260923-001/local-metadata/receipts.json)：71 份白名单内的下载、prepare、freeze、access、claim 元数据副本及原路径。
- [audit-findings.json](../../var/priority45-audit-20260923-001/audit-findings.json)：常数比较、文件元数据匹配、角色支持汇总、历史资源盘点。
- [summarize_audit.py](../../var/priority45-audit-20260923-001/summarize_audit.py)：使用 AST 字面量读取官方常数；未执行下载的 Python 代码。

官方记录只读取 JSON；仅比对配置指定的 MC 成员，不下载记录中的事件文件。80 份保存证据均通过大小与 SHA-256 回验。与官方文件记录的匹配是文件名、大小和 Adler-32 的**元数据匹配**；本次没有重新计算本地 ROOT 的哈希。源码发现优先使用代码图谱；图谱无结果时回退读取已知目标。

## 2. 数据用途是投稿定位的先决条件

[CERN Open Data 2020 record 15005](https://opendata.cern.ch/record/15005) 的 `metadata.usage.description` 明确写道：

> This dataset is provided by the ATLAS Collaboration **only for educational purposes and is not suited for scientific publications**.

记录同时列出 CC0-1.0。这两者分别涉及用途／科学适用性和许可，不能把上句简单改写成法律上的全面发表禁令，也不能仅凭 CC0 将其当作研究级物理输入。本项目若保留这些样本，应明确教育与技术方法演示的范围；若要提出物理精度、真实背景组成或跨条件泛化主张，需要适用的研究级 MC、完整来源及验证。方法论文是否适合具体期刊，还需结合贡献、材料定位和引用政策判断，不能由本审计替期刊决定。

[2025 record atlas-93928](https://opendata.cern.ch/record/atlas-93928) 也将该 ntuple 格式主要定位为教育和 outreach，建议研究质量分析优先考虑面向研究的开放数据。换用 2025 文件本身不会自动消除定位问题。仓库继续严格限于 MC，不因此引入真实碰撞数据。

## 3. DSID 与归一化来源对照

固定来源为官方 outreach 仓库的 [infofile.py](https://github.com/atlas-outreach-data-tools/atlas-outreach-Python-uproot-framework-13tev/blob/8ad2015be6d350060c3a183aff5802570bc9ada4/infofile.py)，commit `8ad2015be6d350060c3a183aff5802570bc9ada4`。该提交由 `infofile.py` 提交历史查询定位，本次所有示例文件均使用同一提交。现有合同中的 `master` URL 没有原地修改；此审计补充不可变来源绑定。

| 项目 | 信号 | 背景 |
|---|---|---|
| DSID | 345060 | 363490 |
| 官方键 | `ggH125_ZZ4lep` | `llll` |
| 官方文件 | `mc_345060.ggH125_ZZ4lep.4lep.root` | `mc_363490.llll.4lep.root` |
| 文件字节数 | 50,518,236 | 179,082,866 |
| 官方 Adler-32 | `1ea0e560` | `6298e6cb` |
| `xsec`，pb | 0.0060239 | 1.2578 |
| `sumw` | 27,881,776.6536 | 7,538,705.8077 |
| `red_eff` | 1 | 1 |
| 本地 k-factor / filter efficiency | 1 / 1 | 1 / 1 |
| 本次结论 | 文件元数据和常数匹配 | 文件元数据和常数匹配 |

官方 `events` 分别为 985,000 和 17,825,300；它们不是下载后 skim 文件的条目数，不能用来替换 signed `sumw` 作为归一化分母。记录描述为至少四个轻子的松预选，也不是项目最终的 `2e2mu, 105–140 GeV` 选择。

[dataset_science_v1.json](../../config/dataset_science_v1.json) 使用 `effective_xsec`；[weights.py](../../src/higgsml/physics/weights.py) 的定义为：

```text
w = luminosity_pb * xsec_pb * k_factor * filter_efficiency / sum_of_weights * mcWeight
```

官方 [HZZAnalysis.py](https://github.com/atlas-outreach-data-tools/atlas-outreach-Python-uproot-framework-13tev/blob/8ad2015be6d350060c3a183aff5802570bc9ada4/HZZAnalysis.py) 使用 `lumi*1000*xsec/(sumw*red_eff)`，与此处 10 fb⁻¹ 转为 10,000 pb⁻¹ 的常数约定一致。**常数匹配不等于已完成有效截面各因子的物理推导。** 新增 k-factor、BR 或过滤效率之前，必须查清是否已吸收在有效截面中，避免重复相乘。

### 3.1 已证实的事件权重差异

上述官方示例的 `calc_weight` 明确乘入：

```text
mcWeight * scaleFactor_PILEUP * scaleFactor_ELE
         * scaleFactor_MUON * scaleFactor_LepTRIGGER
```

当前 [2020 profile](../../config/profiles/open_data_2020.yaml) 没有映射这四个修正字段，当前物理权重函数也没有这些参数。这证实了项目与示例的权重定义不同；`xsec` 常数相等不能证明逐事件修正已被吸收。尚未读取分支值或计算修正影响，不能宣称产额偏差是多少，也不能直接把示例权重移植到当前选择。

下一步应先从来源核实四项修正适用的重建／ID／隔离／触发选择、是否包含已用修正及相关性，再在单独的合法 development 研究中量化产额、形状、signed 支持及训练权重影响。若选择保留未修正 MC 方法场景，应明确范围；若修正物理定义，按第 6 节建立新链路。

### 3.2 尚未闭合的物理来源表

| 项目 | 当前证据 | 缺口与验收材料 |
|---|---|---|
| 2020 生成器、版本、阶数、PDF、淋浴、tune | 文件与常数表标识过程 | 两个 DSID 的生产配置／job options、campaign 和权重说明；不能借用 2025 文件名填充 2020 |
| 有效截面与过滤 | 数值和 `red_eff=1` 匹配 | 截面来源、衰变 BR、k-factor／过滤吸收关系的完整说明 |
| `llll` 背景组成 | 官方示例将其归为 ZZ | 是否含特定初态、干涉和生成级过滤；不能因此称为纯 qqZZ |
| 负权来源与组相关 | 现有 prepare 汇总显示负权 | 生成级机制、重复事件及正负权相关说明；不以矩匹配替代生成模型 |
| FSR、轻子定义与探测器 | 仓库已有重建与选择合同 | 源 ntuple 的 dressed/bare、FSR／探测器约定及与合同对应关系 |
| pileup／轻子／触发修正 | 官方示例明确使用，本项目未映射 | 适用条件与独立数值对照；不凭字段名假定适用 |
| 角／MELA 定义 | 已有 adapter 与固定后端合同 | 独立四矢量、角和概率参考；内部 round-trip 不足 |

官方 [HZZSamples.py](https://github.com/atlas-outreach-data-tools/atlas-outreach-Python-uproot-framework-13tev/blob/8ad2015be6d350060c3a183aff5802570bc9ada4/HZZSamples.py) 还列出 VBF/WH/ZH 及 Z、ttbar 等样本；当前仅 ggH 与 `llll` 的问题定义是较窄的两过程 MC 场景，不应称为完整 H→4l 分析。本文不扩增样本范围。

## 4. 质量形状基线：总支持足够不能证明逐箱可行

当前 prepare 的角色级汇总与归档旧 prepare 相同；本次只读已有 `audit.json`，没有新作质量直方图：

| 角色／过程 | 物理组数 | signed N_eff | rho | signed yield |
|---|---:|---:|---:|---:|
| calibration 背景 | 575 | 173.3205 | 0.65756 | 2.55317 |
| template 背景 | 590 | 170.3650 | 0.65752 | 2.49785 |
| template 信号 | 7,221 | 7,173.0798 | 0.99668 | 2.76832 |

背景 template 负权比例约 10.678%，组级方差约 0.03662294。现有 off-only 质量边界 `[105,140]` 是单箱；新质量网格与分数交叉后，每个过程、角色和箱都须重新检查正净产额、signed N_eff、rho 和协方差。总 N_eff 不能直接换算“最多可分几箱”；本审计没有逐质量箱支持，因此**质量形状可行性仍未验证**。

最小后续开发实验应先确定共同、能解析峰的候选质量网格，再只读取允许的 development/calibration/template 组；记录每箱 signed yield、正负贡献、组方差／协方差和支持失败。网格与合并规则只能依据事先声明的分辨率、支持和稳定性标准选择，不使用 assessment 或候选精度排名。冻结前允许有界开发，开发重复不占用或并入 F2 正式预算。若无可行直方图，不以任意平滑掩盖缺口：停止该主张，或另行验证带形状不确定度的参数化模型。

## 5. 最小基线矩阵与准入条件

| 基线 | 回答的问题 | 固定的共同条件 | 当前状态／下一步 |
|---|---|---|---|
| B0：质量形状 | 质量峰本身提供多少可靠精度？ | 选择、产额、质量模型、nuisance、区间方法 | 逐箱支持与独立区间验证待完成 |
| B1：B0 + off 分数，BC 与 ABCD | 紧凑表示是否保留完整输入的精度？ | 同一 B0、类别预算、阈值规则、训练机会 | 主比较设计见优先级 5；新实验族，不能改写旧联盟归因 |
| 质量控制：mass-only、显式 on/off | 增益是否来自有限质量箱内的残留质量信息？ | 共同网格与精度标准；对应模型单独训练和绑定 | 设计就绪，训练与比较未执行；off 不保证条件独立 |
| B2：B0 + 已验证 MELA 判别 | 与有物理解释的判别相比如何？ | 同一信息范围、过程假设及统计处理 | 独立角／概率参考和 DSID 组成待补 |
| B3：推断目标训练 | 是否优于已有 inference-aware 方法？ | 匹配训练资源、nuisance 信息、最终验证 | 仅在主张学习方法优势时加入；当前不扩大实现 |

MELA 合同见 [复现手册](../implementation-and-reproduction.md)：JHUGenMELA commit `10d36ced1d71b5e4e21abb1c9834a02570bf31c0`，`kinematic_decay7_at_fixed_m4l_no_mass_pdf`，`computeP(False)`，信号 `HSMHiggs/JHUGen/ZZGG`，背景 `bkgZZ/MCFM/ZZQQB`。固定 m4l 的运动学概率不等于完全不依赖 m4l；不能声称 adapter 已实现去相关。canonical 无质量轻子去除了系统 boost/global phi，信息范围也不等同完整四矢量最优似然。

独立检查应覆盖 Z 排序、电荷方向、角周期边界、退化几何、单位、给定四矢量下的两类概率，以及源版本／编译扩展／adapter／输入的哈希绑定。MELA 的 qqZZ 设置不能认证 `llll` 的组成。当前 `config/schemas/registry.json` 有 schema 映射；**这些映射不是独立物理参考认证**。不沿用旧手册中“empty registry”一词作为当前事实。

本次通过 SciSpace 复核了 MEKD 与 INFERNO 的题名／摘要用途：[MEKD](https://doi.org/10.1103/PhysRevD.87.055006) 支持选取矩阵元基线，[INFERNO](https://arxiv.org/abs/1806.04743) 支持按推断目标设计训练基线。没有新增全文算法复现；检索结果的入库年份不能替代发表年份，文献不能替代本项目实现验证。

## 6. 修改依赖与重跑地图

| 后续实际改动 | prepare | train | calibration/template、freeze、推断与报告 |
|---|---|---|---|
| 只补来源说明、审计和引用 | 不需要事件重算 | 不需要 | 若只写文档不重算；若发布新资格产物，按新绑定重建受影响元数据 |
| 改事件权重或修正字段 | 新根重做 | 当前训练使用物理权重绝对值，原则上重训；可复用必须逐项证明输入／权重不变 | 全部受影响阶段重建 |
| 改选择、FSR、角或事件身份 | 新根重做受影响重建 | 所有受影响表示重训 | 重建谱系，不混接旧 freeze |
| 只改质量似然／共同网格 | 已准备特征完全相同时可复用 | 冻结网络及输入合同不变时可复用 | 新协议与新 Stage B 起点；完整比较重新执行 |
| 加入 MELA 基线 | 原 MC 准备可按绑定复用 | 原网络可复用；MELA 单独绑定 | 先独立参考，再 export/import 与新基线推断 |
| 新独立 MC 或研究级输入 | 单独准备、先核实身份与历史 | 固定网络迁移与重训练是不同估计目标 | 新资源、新协议、新预算和随机流 |

F2 结果可帮助判断支持失败与有限 MC 稳定性的重点，**不能替代上述来源、区间或独立性条件**。优先级 3 的低计数参照已显示渐近覆盖问题，且 T1／选择程序的独立验证仍待完成，见 [优先级 3 记录](priority3-statistical-validation-20260923.md)。因此本次不把任何 B0–B3 项目标为科学验证通过。

## 7. 交付与验证边界

本次完成：官方用途核查、四个配置 MC 文件与两代官方记录的元数据匹配、2020 两过程常数核对、事件修正差异定位、角色支持盘点、最小基线与重跑地图。独立确认资源结论见 [优先级 5 文档](priority5-confirmation-design-20260923.md)。

验证记录：[verification.json](../../var/priority45-audit-20260923-001/verification.json)。检查仅覆盖证据字节一致、提取断言、文档链接／LF 和原有工作树文件保全；不等于完整源码回归、全 MC 验证、MELA 数值验证或投稿资格认证。本次未运行仓库全套测试，因为未更改生产实现。
