# H → ZZ* → 4ℓ Demo 事件选择标准

> **文档日期：** 2026-08-10  
> **状态：** Task 1–2 selection 已接入；Task 4A full-ROOT 验收为 `194 passed`，发布安全加固后合成测试为 `198 passed`  
> **适用范围：** `higgs-xgboost-demo` 的 Higgs MC、连续 ZZ MC 和真实数据
s
## 1. 目的与边界

本项目研究：

\[
H\rightarrow ZZ^*\rightarrow4\ell,\qquad \ell=e,\mu.
\]

事件选择（selection）的目的，是定义一个探测器能够较可靠测量、并与四轻子末态相符的分析相空间。它不能证明通过选择的事件来自 Higgs；连续 \(ZZ^*\)、可约背景和误识别事件也可能通过。

本文标准是面向教学与小型研究基线的 ATLAS-inspired selection，不是对某一项正式 ATLAS 分析的完整复刻。trigger、lepton identification、isolation、impact parameter、系统误差和数据驱动背景估计尚不属于本轮实现范围。

`m4l` 可以用于事件选择、盲化和最终质量分布，但不得进入 XGBoost 模型特征。
Task 4A 使用该宽质量窗口完成预处理，只核对 aggregate artifact，没有人工检查真实数据的
盲化质量区。

## 2. 输入数据已经包含的上游选择

当前 ROOT 来自 ATLAS 13 TeV 2025 Education Open Data 的 `exactly4lep` collection。该 collection 在上游已经要求：

- 恰好四个预选择轻子；
- 每个轻子的横动量至少为 7 GeV。

项目仍应在本地代码中显式验证这些条件，原因是：

- 不能只根据文件名假定事件内容；
- 需要检查 `lep_n` 与各数组长度是否一致；
- cutflow 必须记录每一级选择；
- 配置和处理结果必须可追溯；
- 更换输入数据后仍应主动失败或给出可诊断结果。

上游已经删除的事件无法通过放宽本项目 selection 恢复。

## 3. 基础 selection

以下条件按固定顺序执行。Higgs MC、ZZ MC 和真实数据使用相同的事件选择逻辑。

### 3.1 恰好四个有效轻子

要求：

```text
lep_n == 4
```

并检查下列数组长度一致且均为 4：

```text
lep_pt
lep_eta
lep_phi
lep_e
lep_charge
lep_type
```

每个轻子必须是电子或 muon：

\[
|\texttt{lep\_type}|\in\{11,13\}.
\]

少于四个轻子无法重建两个 Z 候选；多于四个轻子需要额外的 quadruplet 选择规则，超出当前 Demo 范围。

### 3.2 有序轻子横动量

四个轻子按 \(p_T\) 从高到低稳定排序，然后要求：

\[
p_{T,1}\ge20,\quad
p_{T,2}\ge15,\quad
p_{T,3}\ge10,\quad
p_{T,4}\ge7\ \mathrm{GeV}.
\]

这些门槛用于排除触发、重建或识别效率不稳定的过软轻子，同时保留离壳 \(Z^*\) 产生的较软轻子。20、15、10 GeV 是 ATLAS 四轻子分析中常见的有序门槛；7 GeV 与当前 `exactly4lep` collection 的上游最低门槛一致。

边界约定：恰好等于门槛时通过。

### 3.3 轻子赝快度接受度

电子要求：

\[
|\eta_e|<2.47.
\]

Muon 要求：

\[
|\eta_\mu|<2.7.
\]

这些边界来自 ATLAS 对电子和 muon 的有效探测与重建覆盖。Muon 系统的可用覆盖比标准电子候选更向前延伸，因此 muon 的 \(|\eta|\) 上限更大。

边界约定：恰好等于 2.47 或 2.7 时不通过。

### 3.4 四轻子总电荷为零

要求：

\[
\sum_{i=1}^{4}q_i=0.
\]

两个合法 SFOS pair 也会隐含总电荷为零，但将其作为独立阶段有助于 cutflow 诊断输入数据和错误原因。

### 3.5 存在两个不重叠的 SFOS pair

SFOS 表示 same-flavour opposite-sign，即同味异号：

\[
e^+e^-\quad\text{或}\quad\mu^+\mu^-.
\]

四个轻子必须能组成两个不共享轻子的 SFOS pair。对于 \(2e2\mu\)，配对通常唯一；对于 \(4e\) 或 \(4\mu\)，可能存在多种合法划分。

### 3.6 所有可能的 SFOS pair 质量大于 5 GeV

事件中所有可能的 SFOS pair，而不只是最终选中的 Z1 和 Z2，都必须满足：

\[
m_{\ell\ell}>5\ \mathrm{GeV}.
\]

只要任意一个可能的 SFOS pair 质量不大于 5 GeV，整个事件就被拒绝。该条件用于排除低质量共振及相关背景。

边界约定：恰好 5 GeV 时不通过。

### 3.7 定义 Z1 和 Z2

名义 Z 质量取：

\[
m_Z=91.1876\ \mathrm{GeV}.
\]

对每一种合法的不重叠 SFOS 划分：

1. 计算两个 dilepton pair 的不变质量；
2. 将质量最接近 \(m_Z\) 的 pair 定义为 Z1；
3. 同一划分中剩余的 pair 定义为 Z2；
4. 如果存在多种合法划分，选择 Z1 最接近 \(m_Z\) 的划分；
5. 如果距离完全相同，按轻子索引顺序确定性打破平局。

“Z1”只是分析重建约定，不表示能够逐事件确定量子层面真正的“第一个 Z”。

### 3.8 Z1 质量窗口

要求：

\[
50<m_{Z1}<106\ \mathrm{GeV}.
\]

该非对称窗口包含正常 Z 质量峰，同时排除明显不符合 Z 候选的组合。

边界约定：恰好 50 或 106 GeV 时不通过。

### 3.9 Z2 基础质量窗口

默认基础模式采用固定下限：

\[
12<m_{Z2}<115\ \mathrm{GeV}.
\]

Z2 在 \(H\rightarrow ZZ^*\) 中经常是离壳的 \(Z^*\)，所以允许它远低于名义 Z 质量。12 GeV 下限比“所有 SFOS pair 大于 5 GeV”更严格，作用于最终选定的 Z2。

边界约定：恰好 12 或 115 GeV 时不通过。

### 3.10 四轻子分析质量窗口

要求：

\[
105\le m_{4\ell}<160\ \mathrm{GeV}.
\]

该窗口覆盖约 125 GeV 的 Higgs 质量区域以及两侧质量区。`m4l` 只参与事件选择、盲化和最终质量研究，不加入模型 `FEATURES`。

边界约定：105 GeV 通过，160 GeV 不通过。

## 4. 可选增强：动态 Z2 下限

为了支持更强的 ATLAS-inspired 选择，Z2 下限提供 `fixed` 和 `sliding` 两种模式。基础配置默认使用 `fixed`；启用 `sliding` 后：

\[
m_{Z2}^{\min}(m_{4\ell})=
\begin{cases}
12, & m_{4\ell}\le140,\\
12+0.76(m_{4\ell}-140), & 140<m_{4\ell}<190,\\
50, & m_{4\ell}\ge190,
\end{cases}
\]

并始终要求：

\[
m_{Z2}^{\min}(m_{4\ell})<m_{Z2}<115\ \mathrm{GeV}.
\]

示例：

| \(m_{4\ell}\) | Z2 下限 |
|---:|---:|
| 125 GeV | 12 GeV |
| 140 GeV | 12 GeV |
| 150 GeV | 19.6 GeV |
| 160 GeV | 27.2 GeV |
| 190 GeV | 50 GeV |

动态下限反映了不同四轻子质量区域的运动学差异：低 \(m_{4\ell}\) 区域需要保留低质量离壳 \(Z^*\)；随着 \(m_{4\ell}\) 增加，可以逐渐提高 Z2 下限来抑制低质量背景和错误组合。

当前分析窗口为 \(m_{4\ell}<160\) GeV，所以实际只会使用前两个分段。保留 190 GeV 分段是为了完整记录该策略的定义，而不是扩大当前分析窗口。

建议配置结构：

```yaml
selection:
  z2_mass:
    min_mode: fixed  # fixed 或 sliding
    fixed_min_gev: 12.0
    max_gev: 115.0
    sliding:
      low_m4l_gev: 140.0
      high_m4l_gev: 190.0
      low_min_gev: 12.0
      high_min_gev: 50.0
```

切换到动态模式只需设置：

```yaml
min_mode: sliding
```

cutflow、data summary 和 run manifest 必须记录实际使用的模式。

## 5. 固定 cutflow 顺序

Task 2 应按以下顺序记录每个样本的事件数和效率：

```text
read
exactly_four_leptons
allowed_lepton_types
lepton_pt
lepton_eta
zero_charge
valid_sfos_pairing
all_sfos_mass
z1_mass_window
z2_mass_window
m4l_analysis_window
selected
```

每一级的事件数必须单调不增，`selected` 必须等于最终输出表的行数。

## 6. 暂不启用的增强条件

以下条件有明确物理用途，但不在 Task 1 基础实现中直接启用：

- single-lepton 或 multi-lepton trigger；
- electron/muon identification working point；
- track 和 calorimeter isolation；
- transverse/longitudinal impact parameter；
- 电子量能器 barrel–endcap 过渡区排除；
- 同味和异味轻子之间的 \(\Delta R\) 分离条件。

当前 Open Data 文档表明部分相关分支可能存在，但加入前必须检查三个本地 ROOT 的实际分支、定义以及 data/MC 一致性。不得仅凭在线文档猜测本地文件内容。

## 7. 配置草案

Task 1 建议将 `config/demo.yaml` 的 selection 扩展为：

```yaml
selection:
  require_exactly_four_leptons: true
  allowed_lepton_types: [11, 13]

  lepton_pt_thresholds_gev: [20.0, 15.0, 10.0, 7.0]
  electron_max_abs_eta: 2.47
  muon_max_abs_eta: 2.7
  require_zero_charge: true

  min_all_sfos_mass_gev: 5.0
  z1_mass_window_gev: [50.0, 106.0]

  z2_mass:
    min_mode: fixed
    fixed_min_gev: 12.0
    max_gev: 115.0
    sliding:
      low_m4l_gev: 140.0
      high_m4l_gev: 190.0
      low_min_gev: 12.0
      high_min_gev: 50.0

  m4l_window_gev: [105.0, 160.0]
```

配置解析必须验证：

- `lepton_pt_thresholds_gev` 恰好包含四个非负且从高到低排列的值；
- 所有质量窗口下限小于上限；
- `min_mode` 只能是 `fixed` 或 `sliding`；
- sliding 的两个 break point 和两个下限均单调不减；
- 所有数值有限；
- 修改 YAML 后人工构造的边界事件选择结果会按预期改变。

## 8. 科学解释约束

- selection 通过不代表事件来自 Higgs；
- Z1/Z2 是重建约定，不是真值标签；
- `m4l` 参与 selection 不等于允许它进入 XGBoost；
- `xgb_score` 不是 Higgs 概率；
- fixed 与 sliding 的结果不得混在同一基准中比较；
- 在模型和选择规则冻结前，不检查或优化真实数据的 120–130 GeV observed signal window；
- 事件数、效率和产额必须来自实际保留的 output artifact，不能从历史文档直接复制。

## 9. 参考资料

- [ATLAS 13 TeV 2025 Data — Beta](https://opendata.atlas.cern/docs/data/for_education/13TeV25_details)
- [ATLAS 四轻子运动学选择，ATL-PHYS-PUB-2017-005](https://cds.cern.ch/record/2261933/files/ATL-PHYS-PUB-2017-005.pdf)
- 项目内部要求：[AGENTS](../../AGENTS.md) 与[下一阶段路线图](../roadmap/next-stage.md)
