# 项目数据说明

> **当前状态（2026-08-18）：** 本项目当前的 MC-only 基准使用 Higgs DSID 345060
> 和连续四轻子背景 DSID 363490。全量预处理结果冻结在
> `runs/full-baseline-363490-2026-08-11-r2`。DSID 700600、旧 `zz.root`、
> `entry_stop: 5000` 及 `data/processed/` 结果只属于历史 Demo，统一放在本文末尾，
> 不再作为当前训练输入或当前结果。

## 1. 当前数据概览

项目研究：

\[
H\rightarrow ZZ^*\rightarrow4\ell,
\qquad \ell=e,\mu.
\]

当前使用三份 ROOT 输入：

| 本地文件 | 类型 | DSID / period | 当前用途 | ROOT 事件数 |
|---|---|---|---|---:|
| `data/raw/higgs.root` | Higgs MC | 345060 | 信号，标签 `1` | 419,943 |
| `data/raw/zz_363490.root` | 连续 \(ZZ^{(*)}\rightarrow4\ell\) MC | 363490 | 主要背景，标签 `0` | 554,279 |
| `data/raw/data16_periodA.root` | 真实碰撞数据 | 2016 period A | 无 truth label；当前封存 | 29,275 |

经过当前增强四轻子 selection 后：

| 样本 | 完整读取 | Selection 后 | 说明 |
|---|---:|---:|---|
| Higgs 345060 | 419,943 | 187,128 | 当前信号 MC |
| ZZ 363490 | 554,279 | 11,976 | 当前背景 MC |
| data16 period A | 29,275 | 2 | 只记录预处理摘要；未用于训练或评分 |

当前合并 MC 表共有：

\[
187128+11976=199104
\]

个事件。这里的事件数来自冻结的 r2 `data_summary.json`，不是从旧文档或抽样比例推算的。

## 2. 数据来源

### 2.1 Higgs MC 与真实数据

Higgs DSID 345060 和 `data16_periodA` 来自 ATLAS 13 TeV Open Data for Education
2025 beta 的 `exactly4lep` ROOT ntuple。该 collection 已在上游保留恰好四个预选轻子
的候选事件，以减小文件规模。

- [ATLAS 13 TeV 2025 Data — Beta](https://opendata.atlas.cern/docs/data/for_education/13TeV25_details)
- [ATLAS 13 TeV 2025 metadata](https://opendata.atlas.cern/docs/data/for_education/13TeV25_metadata)
- [Exactly four-lepton collision data](https://opendata.cern.ch/record/atlas-93924)
- [Exactly four-lepton MC simulation](https://opendata.cern.ch/record/atlas-93928)

真实碰撞数据总记录包含多个 2015–2016 data period。本项目当前只在本地保留并预处理
`data16_periodA`，不能把它解释为完整 2015–2016 数据集。

### 2.2 当前连续 ZZ 背景：DSID 363490

当前主要背景来自 CERN Open Data record 15005：

- [CERN Open Data record 15005](https://opendata.cern.ch/record/15005)
- [DSID 363490 ROOT 直接下载](https://opendata.cern.ch/record/15005/files/mc_363490.llll.4lep.root)

本地文件为：

```text
data/raw/zz_363490.root
```

该样本描述标准模型连续四轻子过程：

\[
pp\rightarrow ZZ^{(*)}\rightarrow4\ell.
\]

它与 Higgs 信号具有相同的可见末态，因此是本项目的主要不可约背景。它不是“假数据”，
而是一个真实标准模型过程的 MC 模拟；“背景”只表示它不是本项目要寻找的 Higgs 共振。

当前冻结归一化参数为：

| 字段 | DSID 363490 |
|---|---:|
| Cross section | 1.2564 pb |
| K-factor | 1.0 |
| Filter efficiency | 1.0 |
| Sum of weights | 7,538,705.808 |

这些值来自项目冻结配置中的官方 metadata，不从文件名猜测。

## 3. 当前三个输入样本

### 3.1 Higgs MC：DSID 345060

该样本模拟：

\[
gg\rightarrow H\rightarrow ZZ^*\rightarrow4\ell.
\]

主要 metadata：

| 字段 | 值 |
|---|---|
| Dataset ID | 345060 |
| Physics short | `PowhegPythia8EvtGen_NNLOPS_nnlo_30_ggH125_ZZ4l` |
| Generator | Powheg + Pythia8 + EvtGen |
| Higgs mass | 125 GeV |
| Cross section | 28.3 pb |
| Filter efficiency | 0.000124 |
| K-factor | 1.717 |
| Full sum of weights | 45,231,011.19517517 |

这是模拟事件，不是真实碰撞记录。因为生成过程已知，它可以作为监督学习的信号类别。

### 3.2 连续 ZZ MC：DSID 363490

DSID 363490 是当前监督训练的背景类别。增强 selection 后保留 11,976 个事件，约为旧
700600 基准 471 个事件的 25.4 倍。更多背景统计量降低了旧基准中的小样本不稳定性，
但不能自动消除模型造成的 ZZ 质量塑形。

当前 11,976 个 ZZ 事件的固定划分为：

| Split | 事件数 |
|---|---:|
| Train | 7,174 |
| Validation | 2,429 |
| Held-out test | 2,373 |

Train 和 validation/development 用于模型开发；held-out test 只能在预先规定的模型选择
条件通过后打开，不能参与调参。

### 3.3 真实数据：data16 period A

`data16_periodA.root` 来自真实 ATLAS 质子—质子碰撞。与 MC 不同：

- 没有“该事件是 Higgs 或 ZZ”的 truth label；
- 不使用 MC generator weight、截面或 sum of weights；
- 不能用于监督训练，也不能计算 truth AUC；
- 程序中的标签 `-1` 只表示“无标签数据”，不是第三种物理类别。

当前 r2 预处理在完整 29,275 个输入事件中保留 2 个事件。这个数字只记录在冻结摘要中；
当前 MC-only 方法学尚未授权对 period A 评分、查看信号区或据此调整模型。

## 4. ROOT 格式与输入 profile

三份文件都是 ROOT ntuple，但并非完全相同的发布格式：

| 样本 | Input profile | TTree | 动量单位 |
|---|---|---|---|
| Higgs 345060 | `release22` | `analysis` | GeV |
| data16 period A | `release22` | `analysis` | GeV |
| ZZ 363490 | `open_data_2020` | `mini` | MeV |

项目按 sample profile 读取并统一为 GeV。不能假设所有 ROOT 都有相同的 TTree 名称、
branch 名称或单位，也不能只根据文件名推断 channel number。

ROOT 中的 TTree 可以理解为事件表：每个 entry 对应一个碰撞或模拟事件，branch 保存
事件级标量或数量可变的物理对象数组。项目使用 Python `uproot` 读取这些文件。

### 4.1 通用事件与轻子信息

不同 input profile 的原始 branch 名可能不同，但经过 profile 适配后，项目需要构造：

| 信息 | 用途 |
|---|---|
| Run/event number | 事件追踪、去重和稳定划分；禁止作为模型特征 |
| Channel number | 核对 MC DSID；禁止作为模型特征 |
| Lepton \(p_T,\eta,\phi,E\) | 四动量重建和运动学变量 |
| Lepton charge/type | 构造同味异号轻子对 |
| Trigger、ID、isolation、impact parameter | 当前增强轻子质量选择 |

### 4.2 MC 特有信息

MC 还需要 generator weight、cross section、k-factor、filter efficiency 和完整样本
sum of weights。它们用于构造物理权重：

\[
w_{\mathrm{phys}}
=\mathcal L
\frac{\sigma k\epsilon_{\mathrm{filter}}}{\sum w_{\mathrm{MC}}}
w_{\mathrm{MC}}.
\]

物理产额使用带符号的 `physical_weight`。由于 XGBoost 不接受负 sample weight，训练和
形状评价使用归一化的 `abs(physical_weight)`。真实数据不使用这套 MC 归一化公式。

## 5. 当前全量预处理

当前配置文件是：

```text
config/dsid363490.yaml
```

配置中仍保留：

```yaml
entry_stop: 5000
```

作为快速 smoke test 的默认上限，但冻结的 r2 基准使用 `--full` 覆盖它。manifest 中实际
记录的读取策略为：

```text
mode: full
entry_stop: null
chunk_size_events: 50000
```

因此本文的 419,943、554,279、29,275 和 selection 后计数都来自完整输入，不是前
5,000 条事件。

当前增强 selection 包括：

- event trigger 与 trigger matching；
- Tight lepton identification；
- track/calo isolation；
- electron/muon transverse impact-parameter significance；
- \(|z_0\sin\theta|<0.5\) mm；
- 有序轻子 \(p_T\) 门槛 20/15/10/7 GeV；
- electron \(|\eta|<2.47\)，muon \(|\eta|<2.7\)；
- 四轻子总电荷为零和两个不重叠 SFOS pair；
- 所有 SFOS pair 质量大于 5 GeV；
- \(50<m_{Z1}<106\) GeV；
- \(12<m_{Z2}<115\) GeV；
- \(105\le m_{4\ell}<160\) GeV。

具体顺序、边界和物理解释见[事件选择标准](selection-standard.md)。

## 6. 当前处理后数据和运行目录

当前冻结预处理目录为：

```text
runs/full-baseline-363490-2026-08-11-r2/
```

其中重要文件是：

```text
config.yaml
processed/mc_events.csv.gz
processed/data_events.csv.gz
artifacts/cutflow.json
artifacts/data_summary.json
artifacts/run_manifest.json
```

用途如下：

| 文件 | 内容与边界 |
|---|---|
| `processed/mc_events.csv.gz` | 当前 199,104 行 MC；包含特征、标签、权重和固定 split |
| `processed/data_events.csv.gz` | 当前真实数据预处理表；保持封存，不用于 MC-only 训练 |
| `cutflow.json` | 每个样本逐级 selection 计数与加权产额 |
| `data_summary.json` | data/MC 分离摘要和选后计数 |
| `run_manifest.json` | 输入路径、SHA-256、完整读取策略、配置和输出位置 |

后续当前训练读取的是上述 run 中的 `mc_events.csv.gz`，不是项目根目录下历史
`data/processed/mc_events.csv.gz`。

## 7. 数据完整性

当前三份 ROOT 输入的冻结信息为：

| 文件 | 字节 | SHA-256 |
|---|---:|---|
| `data/raw/higgs.root` | 182,051,943 | `5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0` |
| `data/raw/zz_363490.root` | 179,082,866 | `76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07` |
| `data/raw/data16_periodA.root` | 15,023,271 | `adc3236398d1b6175438c9b5f77f540f3e1a377d628899156030b0bd3e0042cb` |

macOS 校验命令：

```bash
shasum -a 256 \
  data/raw/higgs.root \
  data/raw/zz_363490.root \
  data/raw/data16_periodA.root
```

Linux 可使用：

```bash
sha256sum \
  data/raw/higgs.root \
  data/raw/zz_363490.root \
  data/raw/data16_periodA.root
```

当前 MC 表在训练 manifest 中冻结为 199,104 行，SHA-256 为：

```text
1c5d6a3f9a750a5eb9965241dd8947d70e790cf949a36f8fa6ec1bfd058f378e
```

## 8. 数据使用规则与限制

1. **真实数据没有 truth label。** 不得把 period A 事件直接标记为 Higgs 或 ZZ，也不得
   用真实数据监督训练。
2. **当前研究是 MC-only 方法学。** period A 和 held-out MC test 是否打开，必须遵守
   预先冻结的模型选择与盲化协议。
3. **`m4l` 不得作为模型特征。** 它只用于宽 selection、质量塑形检查和未来冻结后的
   质量谱分析。
4. **MC 是模拟预测。** 正式物理结论还需要系统误差、更多背景、控制区和数据—MC 验证。
5. **当前真实数据只覆盖一个 period。** `data16_periodA` 不能代表完整 2015–2016 数据。
6. **当前信号只使用一个主要 production sample。** 尚未覆盖所有 Higgs production mode。
7. **连续 ZZ 不是唯一背景。** 正式分析还需研究 \(Z+\)jets、\(t\bar t\) 等可约背景。
8. **教育 ntuple 不等于完整实验分析数据产品。** 当前结果只能描述教学和方法研究。

## 9. 历史 Demo 数据（非当前输入）

本节只为复现实验历史而保留。下面的文件和数字不能当作当前 363490 结果。

### 9.1 历史 DSID 700600

旧文件：

```text
data/raw/zz.root
```

对应 DSID 700600、Sherpa 2.2.12 `Sh_2212_llll`，ROOT 中共有 11,260 个事件。旧全量
Task 4A selection 后只保留 471 个 ZZ 事件，因此已被统计量更大的 DSID 363490 取代。
该文件可以保留用于历史复现，但不应混入当前 363490 训练。

旧文件 SHA-256：

```text
3d7588b897fc50a2342ef1d7b10f8c1b34f035456b2af215f62ad92525422789
```

### 9.2 历史 5,000-entry Demo

早期快速 Demo 使用 `config/demo.yaml` 的：

```yaml
entry_stop: 5000
```

每个 ROOT 最多顺序读取前 5,000 条，得到：

| 历史样本 | 最多读取 | 历史处理后 |
|---|---:|---:|
| Higgs 345060 | 5,000 | 4,884 |
| ZZ 700600 | 5,000 | 4,685 |
| data16 period A | 5,000 | 1,112 |

历史输出位于：

```text
data/processed/mc_events.csv.gz
data/processed/data_events.csv.gz
```

这些文件属于早期端到端功能验证，不是随机代表性抽样，也不是当前全量 r2 输入。当前研究
结果必须引用 `runs/full-baseline-363490-2026-08-11-r2` 中的冻结 artifact。

## 10. 推荐阅读

1. [物理原理](physics-principles.md)：从对撞、四轻子重建到质量塑形；
2. [事件选择标准](selection-standard.md)：selection 顺序、门槛和边界；
3. [项目总览](../project/overview.md)：代码流程、模型结果和当前限制；
4. [下一阶段路线图](../roadmap/next-stage.md)：当前 MC-only 去相关研究计划。

## 11. 官方链接与引用

- [ATLAS 13 TeV 2025 Data — Beta](https://opendata.atlas.cern/docs/data/for_education/13TeV25_details)
- [ATLAS 13 TeV 2025 metadata](https://opendata.atlas.cern/docs/data/for_education/13TeV25_metadata)
- [CERN Open Data record 15005：DSID 363490](https://opendata.cern.ch/record/15005)
- [Exactly four-lepton collision data](https://opendata.cern.ch/record/atlas-93924)
- [Exactly four-lepton MC simulation](https://opendata.cern.ch/record/atlas-93928)
- [ATLAS Open Data citation policy](https://opendata.atlas.cern/docs/documentation/ethical_legal/citation_policy)
- [Collision exactly4lep DOI](https://doi.org/10.7483/OPENDATA.ATLAS.3ATL.Q9Z2)
- [MC exactly4lep DOI](https://doi.org/10.7483/OPENDATA.ATLAS.XNPI.CX93)

ATLAS Open Data 请求使用者引用对应数据 DOI 并致谢 ATLAS Collaboration。CERN 和
ATLAS 不为第三方使用开放数据得到的科学结论背书。
