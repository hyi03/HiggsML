# \(H\rightarrow ZZ^*\rightarrow4\ell\) XGBoost Demo

> **已归档：** 本文保留项目实施前的原始设计，不是当前状态来源。请从
> [README](../../README.md)、[AGENTS](../../AGENTS.md) 和
> [文档导航](../README.md) 开始阅读。

## 1. Demo 目的

本 Demo 的目标是用少量 ATLAS Open Data 跑通一条最小的端到端分析链：

```text
少量Higgs MC和ZZ背景MC
        ↓
读取ROOT并构造物理特征
        ↓
训练和测试XGBoost
        ↓
将固定模型应用于一个真实数据period
        ↓
比较选择前后的四轻子质量分布
```

Demo 用于验证代码、数据和分析方法是否能够正常工作，不用于给出最终物理结论。

## 2. 研究过程

研究的信号过程为：

\[
H\rightarrow ZZ^*\rightarrow4\ell,\qquad \ell=e,\mu.
\]

第一版只考虑最主要的不可约背景：

\[
q\bar q/gg\rightarrow ZZ^*\rightarrow4\ell.
\]

模型需要回答：

> 在不使用四轻子质量 \(m_{4\ell}\) 的情况下，事件的其他运动学特征能否区分 Higgs 信号和连续 \(ZZ^*\) 背景？

## 3. 数据

### 3.1 数据来源

- [ATLAS exactly4lep 真实碰撞数据](https://opendata.cern.ch/record/atlas-93924)
- [ATLAS exactly4lep MC模拟](https://opendata.cern.ch/record/atlas-93928)
- [ATLAS 2025 beta MC metadata](https://opendata.atlas.cern/docs/data/for_education/13TeV25_metadata)

`exactly4lep` 集合要求事件中恰好有四个预选择电子或缪子，并且每个轻子的横动量至少为 7 GeV。

### 3.2 Demo 使用范围

第一版只下载：

1. 一个 \(H\rightarrow ZZ^*\rightarrow4\ell\) MC 文件；
2. 一个连续 \(ZZ^*\rightarrow4\ell\) MC 文件；
3. 一个真实数据 period，例如 `data16_periodA`。

MC 样本应通过官方 metadata 中的 `channelNumber` 和过程描述选择。不要仅根据文件名猜测物理过程。

### 3.3 三类数据的用途

| 数据 | 标签 | 用途 |
|---|---:|---|
| Higgs MC | 1 | 训练和测试信号 |
| \(ZZ^*\) MC | 0 | 训练和测试背景 |
| 真实数据 | 未知 | 最终推理和分布检查 |

真实数据不能作为有标签的监督训练数据。

## 4. 建议目录结构

```text
higgs-xgboost-demo/
├── config/
│   └── demo.yaml
├── data/
│   ├── raw/
│   └── processed/
├── src/
│   ├── io.py
│   ├── pairing.py
│   ├── features.py
│   ├── weights.py
│   ├── train.py
│   └── plots.py
├── tests/
│   ├── test_pairing.py
│   ├── test_features.py
│   └── test_weights.py
├── scripts/
│   ├── inspect_root.py
│   ├── prepare_demo.py
│   ├── train_demo.py
│   └── evaluate_data.py
├── outputs/
├── requirements.txt
└── README.md
```

`data/raw/` 和模型输出通常不应提交到 Git 仓库。

## 5. 软件环境

建议使用：

```text
Python
uproot
awkward
vector
numpy
pandas
scikit-learn
xgboost
matplotlib
mplhep
pytest
pyyaml
```

示例 `requirements.txt`：

```text
awkward
matplotlib
mplhep
numpy
pandas
pyyaml
pytest
scikit-learn
uproot
vector
xgboost
```

## 6. 第一步：检查 ROOT 文件

在编写分析逻辑前，先检查文件结构：

```python
import uproot

path = "data/raw/example.root"

with uproot.open(path) as root_file:
    print(root_file.keys())
```

找到实际 TTree 名称后，再检查分支：

```python
with uproot.open(path) as root_file:
    tree = root_file["ACTUAL_TREE_NAME"]
    print(tree.num_entries)
    print(tree.keys())
    tree.show()
```

需要确认：

- TTree 的真实名称；
- `lep_pt`、`lep_eta`、`lep_phi`、`lep_e` 的类型；
- 动量和能量使用 MeV 还是 GeV；
- 轻子是否已经按 \(p_T\) 排序；
- `channelNumber` 是否与文件 metadata 一致；
- `mcWeight` 是否存在负数；
- 数据和 MC 的分支是否一致。

所有单位应在进入模型前统一为 GeV。

## 7. 第二步：事件重建

### 7.1 轻子基本信息

至少读取：

```text
runNumber
eventNumber
channelNumber
lep_n
lep_pt
lep_eta
lep_phi
lep_e
lep_charge
lep_type
mcWeight
xsec
kfac
filteff
sum_of_weights
```

其中部分 MC 专用字段在真实数据中可能不存在或没有物理意义，代码需要分别处理 data 和 MC。

### 7.2 SFOS 配对

四个轻子需要组成两个同味异号轻子对：

```text
same flavour:  |lep_type_i| == |lep_type_j|
opposite sign: lep_charge_i * lep_charge_j == -1
```

若存在多个合法组合：

1. 将质量最接近 \(m_Z=91.1876\) GeV 的轻子对定义为 \(Z_1\)；
2. 剩余轻子对定义为 \(Z_2\)。

### 7.3 不变质量

\[
m^2=
\left(\sum_iE_i\right)^2-
\left(\sum_ip_{x,i}\right)^2-
\left(\sum_ip_{y,i}\right)^2-
\left(\sum_ip_{z,i}\right)^2.
\]

需要计算：

```text
mZ1
mZ2
m4l
```

`m4l` 只用于绘图和最终物理检验，不输入主分类模型。

## 8. Demo 输入特征

第一版使用：

```python
FEATURES = [
    "lep1_pt",
    "lep2_pt",
    "lep3_pt",
    "lep4_pt",
    "lep1_eta",
    "lep2_eta",
    "lep3_eta",
    "lep4_eta",
    "mZ1",
    "mZ2",
    "pt4l",
    "deltaR_Z1",
    "deltaR_Z2",
    "deltaPhi_ZZ",
]
```

轻子应使用固定排序规则，例如按 \(p_T\) 从高到低排列。

禁止输入：

```text
m4l
channelNumber
eventNumber
runNumber
mcWeight
xsec
kfac
filteff
sum_of_weights
source_file
period
```

`channelNumber` 用于创建标签；MC 权重用于训练或评价；它们都不能成为模型特征。

## 9. MC 权重

MC 事件的基本物理权重可写为：

\[
w_i=
\mathcal L
\frac{\sigma\,k\,\epsilon_{\mathrm{filter}}}
{\sum w_{\mathrm{gen}}}
w_{\mathrm{MC},i}
\prod_j SF_{j,i}.
\]

Demo 至少需要：

- 检查权重是否有限；
- 检查是否有负权重；
- 分别记录训练权重和物理评价权重；
- 不把 MC 权重作为模型输入。

第一版可以同时报告未加权和加权指标，但最终物理产额与显著性必须使用正确的物理权重。

## 10. 数据划分

MC 建议划分为：

```text
训练集：60%
验证集：20%
测试集：20%
```

使用确定性的事件分组，避免同一事件进入多个集合。例如根据 `eventNumber` 计算哈希分组。真实碰撞数据完全不参与这个划分。

需要保存：

```text
eventNumber
channelNumber
split
```

并测试三个集合之间没有事件重叠。

## 11. XGBoost 模型

Demo 初始参数：

```python
from xgboost import XGBClassifier

model = XGBClassifier(
    n_estimators=300,
    max_depth=3,
    learning_rate=0.05,
    min_child_weight=5,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.1,
    reg_lambda=2.0,
    objective="binary:logistic",
    eval_metric="auc",
    random_state=42,
)
```

Demo 阶段不进行大规模超参数搜索。模型训练完成后保存为：

```python
model.save_model("outputs/xgboost_demo.json")
```

## 12. 评价指标

至少计算：

- 加权和未加权 ROC-AUC；
- ROC 曲线；
- 信号与背景的 XGBoost 分数分布；
- 训练集和测试集分数分布；
- 模型分数与 \(m_{4\ell}\) 的相关性；
- 不同分数阈值下的 \(S\)、\(B\) 和 \(S/B\)；
- Asimov significance。

\[
Z_A=
\sqrt{
2\left[
(S+B)\ln\left(1+\frac{S}{B}\right)-S
\right]
}.
\]

accuracy 只能作为辅助指标，不能作为最终物理评价标准。

## 13. 应用于真实数据

模型训练、特征和阈值固定后，将同一套特征构造流程应用于一个真实数据 period：

```python
data["xgb_score"] = model.predict_proba(data[FEATURES])[:, 1]
```

比较：

1. 所有真实事件的 \(m_{4\ell}\)；
2. 低 XGBoost 分数区域的 \(m_{4\ell}\)；
3. 高 XGBoost 分数区域的 \(m_{4\ell}\)。

只使用一个 period 时统计量可能很少，没有明显 125 GeV 峰是正常现象。Demo 主要验证推理和绘图流程。

## 14. 输出文件

```text
outputs/
├── data_summary.json
├── feature_distributions.png
├── roc_curve.png
├── score_distribution.png
├── score_vs_m4l.png
├── m4l_before_xgb.png
├── m4l_high_score.png
├── metrics.json
└── xgboost_demo.json
```

`metrics.json` 至少保存：

```json
{
  "features": [],
  "train_events": 0,
  "validation_events": 0,
  "test_events": 0,
  "weighted_auc": null,
  "unweighted_auc": null,
  "best_threshold": null,
  "expected_signal": null,
  "expected_background": null,
  "asimov_significance": null
}
```

## 15. 最小测试

建议采用 TDD 为核心物理函数编写测试：

1. 静止粒子的四动量给出正确质量；
2. 两个轻子的组合质量计算正确；
3. SFOS 判断正确；
4. \(Z_1\) 总是选择最接近 \(m_Z\) 的合法轻子对；
5. 无合法 SFOS 组合时返回明确状态；
6. \(\Delta\phi\) 正确处理 \(-\pi/\pi\) 边界；
7. `m4l` 不在 `FEATURES`；
8. `channelNumber` 不在 `FEATURES`；
9. 训练、验证和测试事件不重叠；
10. 权重和模型输入不包含 NaN 或无穷值。

## 16. Demo 完成标准

满足以下条件即可进入完整分析：

- [ ] 可以读取一个 data 文件和两个 MC 文件；
- [ ] 正确识别 TTree 和必要分支；
- [ ] 单位已统一为 GeV；
- [ ] Higgs 与 \(ZZ^*\) 的 `channelNumber` 映射已核对；
- [ ] SFOS 和 \(Z_1/Z_2\) 配对测试通过；
- [ ] 能计算 \(m_{Z_1}\)、\(m_{Z_2}\) 和 \(m_{4\ell}\)；
- [ ] 模型输入不含泄漏变量；
- [ ] 训练、验证和测试集合没有事件重叠；
- [ ] XGBoost 能完成训练、保存和重新加载；
- [ ] 能输出 ROC、分数和质量分布；
- [ ] 能对一个真实数据 period 产生 XGBoost 分数；
- [ ] 整个流程可以通过固定命令重复运行。

## 17. Demo 之后的扩展顺序

1. 加入所有相关 Higgs 产生模式；
2. 加入完整连续 \(ZZ^*\) MC；
3. 加入 \(Z+\)jets、\(t\bar t\) 等可约背景；
4. 完善所有 MC 权重和效率修正；
5. 合并全部真实数据 period；
6. 做 period-level data quality 检查；
7. 进行特征组消融实验；
8. 检查质量塑形；
9. 优化 XGBoost 超参数；
10. 计算最终预期显著性并撰写报告。

## 18. Demo 不应得出的结论

Demo 可以证明：

- 数据能够读取和重建；
- XGBoost 分析链可以运行；
- 选定特征在 MC 中具有一定分类能力。

Demo 不能证明：

- 已经重新发现希格斯玻色子；
- 模型在全部真实数据上具有稳定性能；
- 所有背景和系统误差都已被正确描述；
- Demo AUC 可以直接转化为真实实验显著性。
