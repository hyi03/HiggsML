# H → ZZ* → 4ℓ 项目 Codex 交接与研究路线图

> **已归档：** 本文保留历史设计和交接背景，不是当前状态来源。请从
> [README](../../README.md)、[AGENTS](../../AGENTS.md) 和
> [文档导航](../README.md) 开始阅读。

> **文档日期：** 2026-08-03  
> **适用对象：** 新建的 Codex 对话、新电脑上的开发者或未来维护者  
> **项目根目录：** 本文件上两级目录，即 `higgs-xgboost-demo/`  
> **用途：** 在不读取旧聊天记录的情况下恢复项目背景、验证当前状态、制定方案并继续写代码

---

## 0. 给新 Codex 的强制阅读说明

如果你是刚接手本项目的新 Codex，请不要依赖任何先前对话，也不要立即修改代码。先依次阅读：

1. `docs/archive/codex-handoff-and-roadmap.md`（本文件，历史参考）；
2. `AGENTS.md`；
3. `README.md`；
4. `docs/project/overview.md`；
5. `docs/roadmap/next-stage.md`；
6. `docs/briefings/progress-briefing.md`；
7. `config/demo.yaml`；
8. 与当前任务直接相关的源码和测试。

本文件中的数值是历史基准，不自动代表当前工作区状态。任何“测试通过”“模型完成”“没有过拟合”或“结果可复现”的结论，都必须先通过本机命令重新验证。

### 新 Codex 的第一轮工作规则

1. 使用 `pwd` 确认工作目录是本文件所在的项目根目录。
2. 使用 `git status --short` 检查未提交修改；不得覆盖用户已有改动。
3. 使用 `rg --files` 或等价命令确认文件结构，不要凭本文猜测文件是否仍存在。
4. 检查 `.venv`、ROOT 数据、处理后数据和 outputs 是否存在。
5. 先运行测试建立基线，再提出或实施改动。
6. 如果测试或数据状态与本文不同，以现场检查结果为准，并更新交接文档。
7. 修改功能前先写失败测试；修改后先运行聚焦测试，再运行完整测试。
8. 不得把 `m4l`、事件标识、样本标识、truth 或权重加入模型特征。
9. 不得用真实数据训练，也不得用 test 集调参或选择阈值。
10. 未经用户明确授权，不下载大规模数据、不解盲 120–130 GeV 区间、不覆盖有价值的旧输出。

---

## 1. 项目一句话定义

### 2026-08-05 代码状态更新

- Task 1 可配置四轻子 selection 已接入 `prepare_sample`；
- Task 2 逐级、分样本 cutflow schema 与生成逻辑已实现；
- fixed/sliding Z2 下限均有边界测试；
- 当前完整源码测试为 `121 passed`；
- 尚未使用新 selection 重跑真实 ROOT，现有 processed data、模型、指标、图片和历史事件数仍属于旧基准；
- Task 3 data/MC summary、run manifest 和 `--output-dir` 生成逻辑已实现并通过合成测试；现有 outputs 尚未由新代码重建。

以上状态来自合成事件单元/集成测试，不代表新的真实数据物理基准已经产生。

本项目是一个基于 ATLAS 13 TeV Open Data 的端到端机器学习 Demo，研究：

> 能否使用不包含四轻子不变质量 `m4l` 的运动学特征训练 XGBoost，区分
> \(H\rightarrow ZZ^*\rightarrow4\ell\) 信号与连续 \(ZZ^*\rightarrow4\ell\)
> 背景，并在模型固定后安全地检查真实数据的四轻子质量分布？

当前项目证明了技术链能够运行，但尚不是完整物理分析，不能声称重新发现 Higgs、测量信号强度或得到正式 ATLAS 显著性。

---

## 2. 两阶段总体目标

后续工作分为两个明确阶段，不应一次性把复杂框架全部塞进当前 Demo。

### 阶段一：完善当前 `higgs-xgboost-demo`

目标是把教学型 Demo 升级为可信、可测试、可解释的小型研究基线：

- 让物理 selection 配置真正生效；
- 生成逐级 cutflow；
- 正确分开 data 数量与 MC 加权产额；
- 解决“每个文件前 5,000 条”的抽样偏差；
- 检查多随机种子稳定性；
- 量化 score 对 `m4l` 的质量塑形；
- 明确教授所说的 linear fit 的具体含义。

### 阶段二：迁移到 `particleML`

目标是研究：

> 在通过质量去相关检查后，XGBoost 相比 cut-based baseline 能提高多少
> expected profile-likelihood sensitivity？

参考项目：<https://github.com/xulei-leon/particleML>

`particleML` 是独立的研究级框架，不是当前 Demo 的简单参数优化。它包括完整数据目录、多模型、多随机种子、DDT、pyhf、盲分析、哈希追踪和统计拟合。迁移时应保留当前 Demo 作为容易解释的入门版本。

---

## 3. 当前 Demo 的历史验证基准

以下结果来自 2026-07-29 至 2026-07-30 的实际运行，供新环境复现时比较。

### 3.1 当前数据

| 仓库相对路径 | 类型 | Dataset ID / period | ROOT 总记录数 | 当前读取策略 |
|---|---|---:|---:|---|
| `data/raw/higgs.root` | Higgs MC | 345060 | 419,943 | 前 5,000 条 |
| `data/raw/zz.root` | 连续 ZZ MC | 700600 | 11,260 | 前 5,000 条 |
| `data/raw/data16_periodA.root` | 真实数据 | data16 period A | 29,275 | 前 5,000 条 |

SHA-256：

| 文件 | 字节 | SHA-256 |
|---|---:|---|
| `higgs.root` | 182,051,943 | `5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0` |
| `zz.root` | 5,407,367 | `3d7588b897fc50a2342ef1d7b10f8c1b34f035456b2af215f62ad92525422789` |
| `data16_periodA.root` | 15,023,271 | `adc3236398d1b6175438c9b5f77f540f3e1a377d628899156030b0bd3e0042cb` |

处理后历史事件数：

| 样本 | 事件数 |
|---|---:|
| Higgs MC | 4,884 |
| ZZ MC | 4,685 |
| data16 period A | 1,112 |
| MC train / validation / test | 5,752 / 1,919 / 1,898 |

### 3.2 当前配置

`config/demo.yaml` 的重要值：

```yaml
random_seed: 42
luminosity_pb: 10000.0
tree_name: analysis
momentum_unit: GeV
entry_stop: 5000
```

当前 XGBoost：

```yaml
n_estimators: 300
max_depth: 3
learning_rate: 0.05
min_child_weight: 5
subsample: 0.8
colsample_bytree: 0.8
reg_alpha: 0.1
reg_lambda: 2.0
```

### 3.3 当前模型历史结果

| 指标 | 历史值 |
|---|---:|
| Train weighted AUC | 0.993625 |
| Validation weighted AUC | 0.974099 |
| Test weighted AUC | 0.981321 |
| Train-test AUC gap | 0.012304 |
| Signal weighted KS | 0.086683 |
| Background weighted KS | 0.031947 |
| 过拟合警告 | `False` |
| Validation 选择的阈值 | 0.93 |

固定模型曾对 1,112 个真实数据事件打分：

- `score >= 0.93`：16 个事件；
- `score < 0.93`：1,096 个事件；
- 122–128 GeV 内有 10 个事件，但没有事件通过 0.93；
- 该质量窗内最高 score 约为 0.9221。

这些数值只能证明当前小样本流程跑通。`0.93` 不是 Higgs 概率，也不是固定物理常数。

### 3.4 当前测试历史基准

历史完整测试结果：

```text
23 passed
```

不同 pytest 版本可能以参数化 case 的方式统计测试数量。新 Codex 应以实际测试是否全部通过为判断标准，而不是只比较数字 23。

---

## 4. 当前文件与职责

### 4.1 入口和配置

| 路径 | 责任 |
|---|---|
| `config/demo.yaml` | 数据路径、单位、channel、读取上限、selection 和训练参数 |
| `scripts/inspect_root.py` | 检查 ROOT tree、分支和事件数 |
| `scripts/prepare_demo.py` | 读取 ROOT、预处理、写 processed data 和摘要 |
| `scripts/train_demo.py` | 训练 XGBoost、保存模型、指标和 MC 图 |
| `scripts/evaluate_data.py` | 对真实数据推理并画质量分布 |
| `scripts/make_synthetic_demo.py` | 不依赖真实 ROOT 的 smoke test |

### 4.2 核心模块

| 路径 | 责任 |
|---|---|
| `src/io.py` | ROOT tree 与分支读取、channel 校验 |
| `src/pairing.py` | 四动量、SFOS 配对、Z1/Z2 选择 |
| `src/features.py` | 构造 14 个模型特征与 `m4l` |
| `src/weights.py` | signed 物理权重与非负训练权重 |
| `src/split.py` | 事件哈希 60/20/20 划分 |
| `src/pipeline.py` | 预处理、标签、权重、划分与摘要 |
| `src/train.py` | XGBoost 训练、模型保存和验证报告 |
| `src/validation.py` | AUC、阈值扫描、KS 和简化 Asimov 显著性 |
| `src/progress.py` | 训练进度条 |
| `src/plots.py` | ROC、score、feature 和 `m4l` 图 |

### 4.3 当前模型输入

模型使用 14 个变量：

```text
lep1_pt, lep2_pt, lep3_pt, lep4_pt,
lep1_eta, lep2_eta, lep3_eta, lep4_eta,
mZ1, mZ2, pt4l,
deltaR_Z1, deltaR_Z2, deltaPhi_ZZ
```

禁止输入：

```text
m4l,
eventNumber, runNumber, channelNumber,
mcWeight, xsec, kfac, filteff, sum_of_weights,
physical_weight, train_weight,
source_file, period, process label, truth fields
```

---

## 5. 当前已知限制

新 Codex 不得把以下内容误写为已经完成：

1. selection、ordered lepton \(p_T\)、\(\eta\)、Z1/Z2 和 `m4l` 窗口已接入代码并通过合成测试，但真实 ROOT 尚未重跑。
2. 新 cutflow 的真实样本 artifact 尚未生成，现有 outputs 不代表新 selection。
3. 当前分支列表没有正式使用 trigger、identification、isolation 或 impact-parameter 变量。
4. `entry_stop: 5000` 是读取文件开头，不是随机抽样。
5. 未对小样本抽样比例进行 MC 产额修正。
6. 真实数据只有 data16 period A。
7. 背景只有连续 ZZ，没有 Z+jets、ttbar 等 reducible background。
8. 现有 `outputs/data_summary.json` 是旧运行 artifact，仍混合 data 单位权重和 MC 物理权重；新生成逻辑已修复，但尚未对真实 ROOT 重跑。
9. 当前阈值只来自一个小样本和一个随机种子。
10. 当前简化 \(Z_A\) 不包含系统误差，也不是正式物理显著性。
11. 尚无 sideband、control region、质量去相关或质量谱 likelihood fit。
12. `m4l` 虽未直接输入模型，但其他特征仍可能间接塑造质量分布。
13. 项目目前位于一个尚无提交历史的父 Git 工作区中，并显示为未跟踪目录；不能假设代码已安全备份到 Git。

---

## 6. 新聊天窗口的启动流程

### 6.1 同一台电脑、新建 Codex 对话

1. 将 `higgs-xgboost-demo/` 本身作为工作区打开。
2. 在新对话中附上或引用本文件。
3. 粘贴第 16 节的启动提示。
4. 让 Codex 先只读检查，不要立即写代码。

### 6.2 另一台电脑

源代码可以通过 Git、压缩包或文件同步传输，但必须注意：

```text
.venv/
data/raw/*
data/processed/*
outputs/*
```

均被 `.gitignore` 排除。只 clone 源码不会得到 ROOT、processed CSV、模型或图片。

新设备应重建 `.venv`，不要复制旧环境：

```bash
cd /path/to/higgs-xgboost-demo
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

macOS 还需要：

```bash
brew install libomp
```

检查数据校验和：

```bash
shasum -a 256 data/raw/higgs.root data/raw/zz.root data/raw/data16_periodA.root
```

Linux 可用：

```bash
sha256sum data/raw/higgs.root data/raw/zz.root data/raw/data16_periodA.root
```

建立测试基线：

```bash
python -c "import xgboost, uproot; print(xgboost.__version__, uproot.__version__)"
python -m pytest -q
```

如果 processed data 和 outputs 不存在：

```bash
python -m scripts.inspect_root data/raw/higgs.root
python -m scripts.inspect_root data/raw/zz.root
python -m scripts.inspect_root data/raw/data16_periodA.root
python -m scripts.prepare_demo --config config/demo.yaml
python -m scripts.train_demo --config config/demo.yaml
python -m scripts.evaluate_data
```

历史参考输出：

```text
prepared 9569 MC events and 1112 data events
Training: 100% ... 300/300
scored 1112 unlabeled data events; threshold=0.93
23 passed
```

---

## 7. 阶段一实施计划：完善当前 Demo

阶段一应按照任务 1–7 顺序进行。每项任务完成后都应拥有独立测试、可检查产物和一次文档状态更新。

### Task 1：实现可配置的四轻子 selection

**目标：** 配置文件中的选择条件真正改变事件是否被保留。

**建议文件：**

- 新建：`src/selection.py`
- 新建：`tests/test_selection.py`
- 修改：`config/demo.yaml`
- 修改：`src/pipeline.py`
- 必要时修改：`src/features.py`

**第一版固定选择：**

1. 恰好四个 electron 或 muon；
2. 四个轻子按 \(p_T\) 降序后满足 20、15、10、7 GeV；
3. electron 满足 \(|\eta|<2.47\)；
4. muon 满足 \(|\eta|<2.7\)；
5. 四轻子总电荷为 0；
6. 可以构造两个不重叠 SFOS pair；
7. Z1 是质量最接近 91.1876 GeV 的 pair；
8. \(50<m_{Z1}<106\) GeV；
9. \(12<m_{Z2}<115\) GeV；
10. 所有可能的 SFOS pair 质量大于 5 GeV；
11. \(105\le m_{4\ell}<160\) GeV。

**暂不强行实现：** trigger、ID、isolation 和 impact parameter。只有在 ROOT 中确认分支存在、定义明确并与数据/MC一致后才能加入。

**测试要求：**

- 每个边界分别测试刚好低于、等于和高于阈值；
- electron/muon 的 eta 上限分别测试；
- 测试总电荷非零、无 SFOS、Z1/Z2 窗外和 `m4l` 窗外；
- 测试 YAML 参数变化会改变选择结果；
- 保留原有配对、feature leakage 和单位测试。

**验收：**

```bash
python -m pytest tests/test_selection.py tests/test_pairing.py tests/test_features.py -q
python -m pytest -q
```

全部通过，并且 `config/demo.yaml` 的 selection 参数可追溯到实际代码。

### Task 2：实现逐级、分样本 cutflow

**目标：** 清楚显示事件在哪一步被拒绝，而不是只报告最终事件数。

**建议文件：**

- 修改：`src/selection.py`
- 修改：`src/pipeline.py`
- 修改：`scripts/prepare_demo.py`
- 新建：`tests/test_cutflow.py`
- 生成：`outputs/cutflow.json`

**固定 cutflow 顺序：**

```text
read
exactly_four_leptons
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

后续加入 trigger/ID/isolation 时，应插入独立阶段，不得合并成无法诊断的单一步骤。

**输出要求：**

`outputs/cutflow.json` 至少按以下样本分别记录：

```text
higgs_345060
zz_700600
data16_periodA
```

每一级应包含：

- unweighted count；
- 相对上一阶段的效率；
- 相对 `read` 的累计效率；
- MC 的 signed weighted yield；
- MC 的 absolute weighted yield；
- data 不计算“物理权重产额”，只报告事件数。

**测试要求：**

- 人工构造事件覆盖每个失败原因；
- 每级 count 必须单调不增；
- `selected` 必须等于最终输出 DataFrame 长度；
- data 和 MC 的统计字段不得混淆；
- 重复运行相同输入得到相同 cutflow。

### Task 3：重做数据摘要与运行 manifest（代码完成，真实 artifact 待生成）

**目标：** `data_summary.json` 不再把 data 单位权重与 MC 加权产额相加，并能够追踪输入和配置。

**建议文件：**

- 新建：`src/provenance.py`
- 移除：`src/pipeline.py::write_summary`
- 修改：`scripts/prepare_demo.py`
- 新建：`tests/test_summary.py`
- 新建：`tests/test_manifest.py`
- 真实运行时生成：`<output-dir>/data_summary.json`
- 真实运行时生成：`<output-dir>/run_manifest.json`

**data summary 必须分开：**

- data：period、读取数、最终数、run/event 唯一性；
- MC：DSID、读取数、最终数、signed sum weights、absolute sum weights、负权重数和比例；
- 不再生成 data+MC 的统一 `sum_weights`。

**manifest 至少记录：**

- UTC 运行时间；
- Python 和关键库版本；
- 配置文件 SHA-256；
- 三个 ROOT 文件的 SHA-256；
- `entry_stop` 或抽样规则；
- 随机种子；
- Git commit；若无 commit，明确写 `unavailable`；
- 输出 schema version。

**代码验收（2026-08-05）：** 旧的混合 `weight_summary` 已从生成逻辑中移除；所有规定字段、校验和 CLI 接线已通过合成测试。尚未运行真实 ROOT，因此旧 `outputs/data_summary.json` 不能视为新 schema 的结果。

### Task 4：解决前 5,000 条抽样与 MC 归一化

**推荐方案：优先完整处理现有三个 ROOT。**

现有 ROOT 总规模约 460k 条记录，优先尝试将：

```yaml
entry_stop: null
```

并记录运行时间和内存。如果整文件读取内存过高，再把 `src/io.py::iter_events` 改成 `uproot.iterate` 分块读取；不要退回“前 N 条”作为正式方案。

**备选方案：确定性哈希抽样。** 只有在完整处理不可行时使用：

- 抽样 key 至少包括 DSID、run/event number；
- 相同输入和 seed 必须得到相同子样本；
- 抽样比例按样本分别记录；
- 用于产额时必须说明并验证 `1/f_sample` 修正；
- 比较抽样前后主要 feature 和 cutflow。

**建议文件：**

- 修改：`src/io.py`
- 可能新建：`src/sampling.py`
- 新建：`tests/test_sampling.py`
- 修改：`config/demo.yaml`
- 修改：`outputs/run_manifest.json` 的生成逻辑

**验收：** 正式结果不再来源于文件开头 5,000 条；重复运行得到相同样本和产额。

### Task 5：建立多随机种子模型稳定性

**目标：** 判断 AUC、KS 和阈值 0.93 是否依赖单个随机种子或小样本波动。

**固定种子建议：**

```text
17, 42, 314, 2026, 2718
```

**建议文件：**

- 修改：`config/demo.yaml`
- 修改：`src/train.py`
- 修改或新建：`src/stability.py`
- 新建：`tests/test_stability.py`
- 生成：`outputs/stability_summary.json`
- 生成：`outputs/threshold_stability.png`

**每个 seed 保存：**

- train/validation/test weighted AUC；
- signal/background weighted KS；
- validation 选择阈值；
- test signal/background yield；
- 简化 \(Z_A\)；
- 模型文件或模型文件索引。

**汇总：** 每项报告 mean、standard deviation、minimum、maximum。正式比较使用固定规则，不得因看到 test 或真实数据结果而删除表现差的 seed。

**验收：** 同一 seed 重复训练预测一致；保存并重新加载模型后的预测在数值容差内一致。

### Task 6：量化 score–mass 相关性与质量塑形

**目标：** 证明模型不是通过与 `m4l` 间接相关的输入在人为制造窄峰。

**建议文件：**

- 新建：`src/mass_sculpting.py`
- 新建：`tests/test_mass_sculpting.py`
- 修改：`scripts/train_demo.py`
- 修改：`scripts/evaluate_data.py`
- 生成：`outputs/mass_sculpting.json`
- 生成：`outputs/background_m4l_by_score_bin.png`
- 生成：`outputs/sideband_efficiency.png`

**最低检查项：**

1. background MC raw score 与 `m4l` 的 Spearman 相关系数；
2. background MC 在不同 score 分位区间内的 `m4l` 分布；
3. 不同阈值下 background acceptance 随 `m4l` 的变化；
4. data sideband 与 MC sideband 的比较；
5. 120–130 GeV 在模型与规则冻结前保持盲化；
6. 任何高分窄结构都要做 sideband 或 spurious-signal 检查。

**重要：** 仅仅不把 `m4l` 放进 `FEATURES`，不能证明没有质量塑形。

### Task 7：确认并实现教授所说的 linear fit

在写代码前向教授确认下面两种含义中的哪一种：

#### 含义 A：Logistic Regression 线性分类基线

目的：与 XGBoost 比较，判断非线性结构是否真正提供额外分类能力。

如果是这个含义：

- 对连续变量标准化；
- 使用与 XGBoost 完全相同的 train/validation/test 和权重；
- 只在 validation 选择超参数和工作点；
- 在相同 test 上比较 AUC、KS 和预期指标。

#### 含义 B：对 `m4l` sideband 做线性背景拟合

形式可能是：

\[
N(m_{4\ell})=a+b\,m_{4\ell}.
\]

如果是这个含义：

- 只用预先定义的 sidebands 拟合背景；
- 120–130 GeV 不参与冻结前的参数选择；
- 报告参数、协方差、残差和拟合优度；
- 检查一阶模型是否足够，不能因为直线简单就默认合理；
- 与指数或低阶多项式做预先规定的稳健性比较；
- 该拟合是质量谱背景模型，不是 Logistic Regression。

在教授确认前，只写接口设计和测试计划，不擅自把两者混为一谈。

---

## 8. 阶段一完成定义

只有满足下列条件，才能说“当前 Demo 的可信基线完成”：

- [ ] selection 配置真实生效；
- [ ] 每个选择边界都有单元测试；
- [ ] 生成逐级、分样本 cutflow；
- [ ] data 与 MC 摘要完全分开；
- [ ] 输入、配置和输出具有 manifest/哈希；
- [ ] 不再使用有顺序偏差的前 5,000 条作为正式样本；
- [ ] MC 权重与处理比例得到验证；
- [ ] 多随机种子稳定性完成；
- [ ] 模型保存/加载预测一致；
- [ ] score–mass 塑形得到数值和图形检查；
- [ ] signal region 在冻结规则前保持盲化；
- [ ] 完整测试和端到端 smoke test 通过；
- [ ] README、docs/project/overview.md、docs/briefings/progress-briefing.md 和本文同步更新。

---

## 9. 阶段二实施计划：迁移到 particleML

### 9.1 迁移原则

1. `particleML` 放在独立目录，不覆盖 `higgs-xgboost-demo`。
2. 当前 Demo 保留为教学版和最小可运行参考。
3. 不逐文件复制两套实现；优先使用 `particleML` 已定义的公共 pipeline。
4. `particleML` 文档中的 `implemented/tested/planned` 必须严格区分。
5. synthetic demo 通过不等于正式物理分析完成。
6. 正式配置使用 Jetson CUDA；Mac CPU 运行只能作为便携验证，不能冒充正式 CUDA 结果。

### 9.2 第一步：获取并检查仓库

```bash
cd /path/to/research
git clone https://github.com/xulei-leon/particleML.git
cd particleML
```

先阅读：

```text
AGENTS.md
README.md
configs/analysis-v1.yaml
configs/catalog-sources.yaml
docs/research/research-plan.md
docs/research/model-selection.md
docs/research/statistical-analysis-plan.md
docs/engineering/offline-demo-guide.md
docs/engineering/analysis-run-guide.md
docs/software/requirements.md
```

现场检查当前 `main`，不要假设本文件评审时看到的版本仍是最新版本。

### 9.3 第二步：在 CPU 环境跑 synthetic offline demo

目标是验证：

```text
synthetic ROOT
→ selection
→ Parquet
→ four models
→ five seeds
→ DDT
→ templates
→ expected pyhf fit
→ report
```

以仓库当前 `README.md` 和 `docs/engineering/offline-demo-guide.md` 为准。运行前先安装与当前 Python 版本兼容的依赖；不要直接复用 `higgs-xgboost-demo/.venv`。

验收：

- 完整测试通过；
- synthetic demo 结束且输出 schema 验证通过；
- 输出明确标记为 synthetic/non-formal；
- synthetic 输出不能用于 analysis freeze 或 observed fit。

### 9.4 第三步：确认正式数据范围与资源

正式 `particleML` 不只需要当前三个 ROOT。其目录包括：

- 2015+2016 exactly4lep real data；
- 多种 Higgs production modes；
- continuum ZZ irreducible background；
- Z+jets、ttbar 等 reducible backgrounds；
- 部分 generator variations。

下载前应确认：

- 总下载量和本地空间；
- 网络和缓存目录；
- Jetson/Docker/CUDA 环境是否可用；
- 用户是否授权大规模下载；
- 数据 catalog 的 URL、大小和 SHA-256 是否冻结。

### 9.5 第四步：正式 blinded pipeline

以仓库当时的 `analysis-run-guide.md` 为准，顺序应保持：

```text
catalog freeze
→ dataset build
→ data audit
→ validation-only tuning
→ four-model/five-seed blinded study
→ DDT gates
→ expected profile-likelihood fits
→ blinded report
```

核心对照：

- cut-based：物理基线；
- Logistic Regression：线性 ML 对照；
- XGBoost：主要模型；
- sklearn MLP：非线性对照。

核心终点：

\[
Z_{\mathrm{expected}}(\mathrm{XGBoost\!\!\!-DDT})
-Z_{\mathrm{expected}}(\mathrm{cut\!\!\!-based}).
\]

分类 AUC 只能作为次要指标；XGBoost 必须在 DDT 后仍提高 expected sensitivity，且通过质量塑形 gates，才具有研究意义。

### 9.6 DDT 解释

`particleML` 的 raw XGBoost score 仍是分类器输出，不是 Higgs 概率。DDT score 定义为背景 score 在给定 `m4l` 和 final-state channel 下的条件 CDF：

\[
s_{\mathrm{DDT}}=F_B(s_{\mathrm{raw}}\mid m_{4\ell},\mathrm{channel}).
\]

固定阈值 0.8 表示大约选择相应背景分布中 score 最高的 20%，与当前 Demo 在 validation 上扫描出的 0.93 含义不同。

### 9.7 正式分析完成定义

- [ ] 完整 public-data catalog 已冻结并校验；
- [ ] canonical dataset 和 split manifest 已生成；
- [ ] data 未进入训练；
- [ ] 70/10/10/10 train/calibration/validation/test 划分可复现；
- [ ] 四种模型、五个种子和 ensemble 已完成；
- [ ] tuning 只使用 validation 和规定 seed；
- [ ] persisted model reload 检查通过；
- [ ] DDT 只在 calibration-background MC 上拟合；
- [ ] background MC 和 data sideband correlation gate 通过；
- [ ] sideband acceptance gate 通过；
- [ ] spurious-signal gate 通过；
- [ ] 六通道 expected pyhf fit 完成；
- [ ] 系统误差和 MC 统计误差进入 workspace；
- [ ] 所有结果能追踪到 config、catalog、manifest、predictions 和 fit artifact；
- [ ] 在独立授权前没有访问 120–130 GeV observed signal window。

---

## 10. 测试策略

新 Codex 写任何代码时应遵循以下测试层级。

### 10.1 单元测试

覆盖：

- selection 每个阈值边界；
- SFOS 配对和 Z1/Z2 决策；
- MeV/GeV 转换；
- 物理权重、负权重和训练权重；
- hash split/sampling 可重复性；
- feature leakage；
- cutflow 计数和效率；
- summary schema；
- AUC、KS、阈值冻结；
- score–mass 相关性；
- 模型保存/加载一致性。

### 10.2 微型 ROOT 集成测试

创建很小的 synthetic ROOT fixture，包含：

- 一个通过全部选择的 Higgs-like MC event；
- 一个通过全部选择的 background event；
- 每个 cut 各一个失败 event；
- 一个负 `mcWeight` event；
- 一个 data event；
- 一个错误 channel 或缺失分支 fixture。

该 fixture 必须足够小，可以在 CI 中运行，不依赖真实 ROOT。

### 10.3 端到端 smoke test

验证：

```text
ROOT → processed table → train → validate → save/reload → data score → plots/reports
```

测试不能依赖大文件或网络，也不能把 synthetic 输出误标为真实物理结果。

### 10.4 完整数据回归测试

不必在普通 CI 运行。手动或专用环境中检查：

- 每个样本的 cutflow；
- event uniqueness；
- 权重总和；
- 主要 feature 分布；
- AUC/KS/threshold 的允许范围；
- 输出 manifest 和 SHA-256。

---

## 11. 科学解释边界

### 当前可以说

- 端到端 Demo 已经在历史环境中跑通；
- 当前 MC 小样本 test weighted AUC 曾达到约 0.981；
- 历史 AUC gap 和 KS 检查未显示明显过拟合；
- XGBoost 已成功应用到无标签真实数据；
- 当前结果揭示了 selection、抽样、权重和质量塑形仍需加强。

### 当前不能说

- 发现或重新发现了 Higgs；
- 0.93 是 Higgs 概率；
- 高分事件一定来自 Higgs；
- 没有把 `m4l` 输入模型就一定没有质量塑形；
- 当前 \(Z_A\) 是正式 ATLAS 显著性；
- synthetic demo 通过就等于正式数据分析完成；
- `particleML` 的框架代码存在就等于五种子物理结果已经产生。

---

## 12. 输出与文档更新规则

每完成一个阶段，新 Codex 应同步更新：

- `README.md`：用户命令和主要输出；
- `docs/project/overview.md`：流程、文件和验证结果；
- `docs/roadmap/next-stage.md`：移除已完成项，调整推荐下一步；
- `docs/briefings/progress-briefing.md`：教授汇报内容；
- `docs/archive/codex-handoff-and-roadmap.md`：历史状态和研究路线；
- `AGENTS.md`：跨设备约束或不可破坏规则发生变化时更新。

指标只能从实际保留的 output artifact 中抄录。不得凭记忆更新事件数、AUC、KS、阈值或显著性。

生成新 outputs 时：

1. 记录配置和输入哈希；
2. 避免静默覆盖旧结果；
3. 推荐使用带 run ID 的子目录；
4. 清楚标记 `synthetic`、`pilot`、`blinded`、`formal`；
5. 图表必须说明使用的数据、选择、权重和是否盲化。

---

## 13. Git 与备份注意事项

本文件生成时，父工作区 `master` 尚无 commit，`higgs-xgboost-demo/` 整体显示为未跟踪目录。因此：

- 不要声称修改已经提交或推送；
- 不要在没有检查的情况下执行 reset、clean 或删除操作；
- ROOT、`.venv`、processed data 和 outputs 不应进入普通源码 commit；
- 在跨电脑开发前，应有意识地初始化或整理 Git 历史，或者完整复制项目目录；
- 如果只传源码，必须同时保存 ROOT 的下载来源和 SHA-256；
- 建立 Git 历史前先确认父目录中哪些文件属于本项目，避免意外提交无关研究资料。

---

## 14. 推荐执行顺序与里程碑

### Milestone 0：新会话恢复

- [ ] 阅读交接文档；
- [ ] 检查工作区和未提交修改；
- [ ] 重建/激活环境；
- [ ] 检查 ROOT 或确认使用 synthetic mode；
- [ ] 运行完整测试；
- [ ] 报告实际基线与本文差异。

### Milestone 1：可信 selection

- [x] 完成 Task 1 selection；
- [x] 完成 Task 2 cutflow；
- [x] 完成 Task 3 summary/manifest 生成逻辑；
- [x] 全部源码测试通过（121 passed）；
- [ ] 使用小样本重跑并检查 cutflow。

### Milestone 2：可信数据与权重

- [ ] 完成 Task 4 全样本或确定性抽样；
- [ ] 核对 MC normalization；
- [ ] 检查负权重；
- [ ] 检查事件唯一性；
- [ ] 保存全样本回归基准。

### Milestone 3：可信模型

- [ ] 完成 Task 5 多种子稳定性；
- [ ] 完成模型 reload 检查；
- [ ] 冻结阈值选择规则；
- [ ] 完成 Task 6 mass sculpting；
- [ ] 与教授确认 Task 7 linear fit。

### Milestone 4：particleML 离线复现

- [ ] 独立 clone `particleML`；
- [ ] 阅读其研究与软件契约；
- [ ] 新建独立环境；
- [ ] 完整测试通过；
- [ ] synthetic offline demo 通过；
- [ ] 记录当前仓库 commit 和环境。

### Milestone 5：particleML 正式 blinded study

- [ ] 获得完整数据下载与计算资源授权；
- [ ] catalog freeze；
- [ ] canonical dataset build/audit；
- [ ] tuning；
- [ ] four-model/five-seed run；
- [ ] DDT gates；
- [ ] expected pyhf fits；
- [ ] blinded report；
- [ ] 教授审阅后再决定是否进入独立解盲流程。

---

## 15. 下一项默认任务

如果用户没有指定其他任务，新 Codex 应从以下任务开始：

> **实施 Task 4：解决前 5,000 条顺序抽样与 MC 归一化；先确定完整处理或确定性抽样方案，再在用户确认目录后生成真实 ROOT 基准。**

Task 1–3 的代码范围已经完成合成测试。下一步默认工作范围：

- 完整读取与确定性抽样方案；
- 抽样比例及 MC physical-weight 归一化；
- processed/output 运行目录策略；
- 小样本与全样本 feature/cutflow 回归比较；
- 对应文档更新。

新 Codex 在动手前，应先提出一个窄范围设计，说明：

1. selection config 的字段；
2. 单事件选择函数的输入/输出；
3. cutflow 如何收集；
4. 现有 `build_event_features` 与 selection 的调用顺序；
5. data 与 MC 如何共享选择；
6. 每项边界测试如何构造；
7. 如何保持现有 feature leakage、权重和 split 约束。

用户批准设计后再编码。

---

## 16. 可直接复制给新 Codex 的启动提示

```text
这个工作区是 H → ZZ* → 4ℓ XGBoost 分析项目。不要依赖任何旧聊天记录。

请先完整阅读项目根目录中的：
1. docs/archive/codex-handoff-and-roadmap.md
2. AGENTS.md
3. README.md
4. docs/project/overview.md
5. docs/roadmap/next-stage.md
6. docs/briefings/progress-briefing.md
7. config/demo.yaml

然后只读检查当前工作区：
- 确认项目根目录和文件结构；
- 运行 git status --short，保留现有修改；
- 检查 .venv、data/raw、data/processed 和 outputs；
- 如果环境可用，运行 python -m pytest -q；
- 对照交接文档报告当前状态、差异、风险和推荐下一步。

在我确认方案前先不要修改代码、下载大数据、重新训练、覆盖 outputs 或访问/解盲真实数据的 120–130 GeV signal window。

默认下一任务是：为当前 higgs-xgboost-demo 解决前 5,000 条顺序抽样与 MC 归一化。请先比较完整处理和确定性抽样方案，说明 processed/output 目录策略、权重修正规则、测试用例和验收命令；经我确认后再按测试驱动方式写代码。Task 1–3 的生成逻辑已经完成，不要重新实现。

必须保持这些科学约束：
- m4l、事件/样本标识、truth 和权重不得进入模型特征；
- data 标签为 -1，不参加监督训练；
- train 只拟合，validation 只调参/选阈值，test 只做冻结后的最终评价；
- signed physical_weight 用于物理产额，非负 train_weight 用于 XGBoost；
- score 不是 Higgs 概率；
- 当前结果不能描述为 Higgs 发现或正式 ATLAS 测量；
- 完成或通过的结论必须来自当前工作区的实际验证命令。
```

---

## 17. 新会话首次回复的期望格式

新 Codex 完成只读检查后，应按以下结构回复用户：

```markdown
## 当前状态

- 工作区：...
- Git 状态：...
- 环境：...
- 数据：...
- 测试：...
- outputs：...

## 与交接基准的差异

- ...

## 风险或阻塞

- ...

## 推荐下一步

1. ...
2. ...

## 本次是否修改文件

- 否；等待用户确认设计。
```

如果缺少 ROOT 或环境，新 Codex 仍应继续完成能做的源码检查，并准确报告缺失项；不得伪造运行结果。

---

## 18. 最终研究叙事

项目应形成清楚的成长路径：

```text
最小端到端 XGBoost Demo
→ 完整 selection 与 cutflow
→ 可信抽样、权重和多种子验证
→ score–mass 塑形检查
→ cut-based / Logistic / XGBoost / MLP 对照
→ DDT 质量去相关
→ 六通道 profile-likelihood expected fit
→ 冻结分析规则
→ 经独立授权后才可能进行 observed fit
```

对教授的准确表述应是：

> 当前 Demo 已经验证从 ROOT 到模型再到真实数据推理的完整技术链。下一步先补齐 selection、cutflow、样本归一化和质量塑形检查，再迁移到 particleML 的 DDT 与 profile-likelihood 框架，研究 XGBoost 相对 cut-based baseline 的预期灵敏度提升。
