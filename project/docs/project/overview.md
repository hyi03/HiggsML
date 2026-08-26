# H → ZZ* → 4ℓ XGBoost Demo 项目总览

## 当前 ARM64 Angular5 + DropTop4 终态（2026-08-26）

在原生 Apple Silicon ARM64（Python `3.12.13`、NumPy `2.5.1`、pandas `3.0.5`、
scikit-learn `1.9.0`、XGBoost `3.3.0`）中，预先冻结的一次性 MC-only 质量分箱迭代
ZZ 重加权研究已完成。它保留 DropTop4 的十个模型特征，只追加五个 Angular5 角变量；
`m4l`、标识/provenance 字段和权重均未作为模型特征。R2 在 x86_64/Rosetta 上因重新计算
浮点量与 ARM 冻结表不完全相等而停止：`mZ1` 的最大绝对差异为 `9.66e-13`（其他派生量为
约 `1e-15`–`1.83e-12`）。这确认是 CPU/运行架构差异，而不是 source identity、CSV
解析、selection 或 ROOT 输入损坏；R3 使用独立的原生 ARM64 路径，没有采用容差方案。

identity 与 enrichment 都保留 `199104` 行和权威旧列的词法记录/行序。旧 legacy key 有
2 个重复组、4 行，但 canonical `(source_sample, source_entry)` 是完整一对一且唯一的。
绑定的生产收据为 identity manifest
`74ebc01ee452bf2f6a7a792d14ed1a62eefefffc6bb090a498fb76abe20273a0`、identity table
`a3ffd8c53aca90dc1813d4f88f9d12113b1918a6f193b8f8ee792cdfd4621f94`、enrichment manifest
`ab5e283f4b6a2038a100a2a9d4e6745cccc3ee7f400ef056bcd05d3c22f28ad5`、enrichment table
`bc31f4e65ccecc0a1962648cfe240b67d8ecc6df8eda2478b3f46c93d2f34f09`，以及 training config
`3b771cc739947d7feb4bb0f2f92a2a34b572bd0c78da8d20a4bf477964c285de`。

冻结资格条件是 weighted OOF AUC >= `0.80`、每个 loose/medium/tight OOF ZZ KS <=
`0.10`，且三个工作点的 signal efficiency 都严格高于 achieved ZZ efficiency。六轮中
所有 signal-efficiency gate 都通过：iteration 0 通过 AUC 但三个 KS 均失败；iteration 5
通过全部 KS 但 AUC 失败。因此选择记录为 `no_eligible_iteration`、
`selected_iteration: null`、`test_opened: false`，且精确 8-file no-selection allowlist
审计通过：没有模型、test 指标或预测 artifact。

| 迭代 | 候选 / 树数 | weighted OOF AUC | ZZ KS（loose / medium / tight） | 资格与原因 |
|---:|---|---:|---:|---|
| 0 | `depth4_child20` / 907 | 0.805150881259955 | 0.1645048771773192 / 0.2871440397452666 / 0.333771961215733 | 否；loose、medium、tight KS |
| 1 | `depth3_child20` / 980 | 0.7969512716122573 | 0.1331765017253415 / 0.20697354210107244 / 0.24956891177813523 | 否；AUC、loose、medium、tight KS |
| 2 | `depth4_child20` / 882 | 0.7910393793089066 | 0.11802005736915522 / 0.1779058575996429 / 0.21232784339918892 | 否；AUC、loose、medium、tight KS |
| 3 | `depth4_child20` / 731 | 0.7777583601726561 | 0.0897799588703656 / 0.12320645298202404 / 0.12778560765808394 | 否；AUC、medium、tight KS |
| 4 | `depth4_child20` / 835 | 0.7705509060126216 | 0.07725381616480781 / 0.10586890011029743 / 0.10377348918175572 | 否；AUC、medium、tight KS |
| 5 | `depth4_child20` / 879 | 0.7665404021047497 | 0.07381807828236636 / 0.090638729937013 / 0.08836325258185229 | 否；AUC |

iteration 5 相对于冻结的十特征 DropTop4 + 重加权 iteration 5（AUC
`0.7588712973047708`、最大 KS `0.09720271279351`）略提高 AUC 并降低最大 KS，但仍不合格。
它也优于 KNN flatness 的最终候选（AUC `0.7566586485761435`、最大 KS
`0.20566162971445773`）的质量形状，但没有改变选择结论。Full14（AUC
`0.8852959102354316`、最大 KS `0.4579540115915921`）和 Full14 + 重加权 iteration 5
（AUC `0.8523982143190011`、最大 KS `0.24583464407366806`）仍是仅供比较的冻结历史参考。
完整 signal/ZZ efficiencies、收据和审计见
[ARM64 Angular5 执行报告](../superpowers/plans/2026-08-26-drop-top4-angular5-r3-arm64-report.md)。

这是一项教育/技术性 MC-only 研究，不是 ATLAS 结果、Higgs 发现或物理测量。本报告不
授权下一阶段训练、额外 iteration、放宽门槛、held-out test-opening 或真实数据访问；
任何后续工作必须采用新的预注册设计、配置和 run path。

## DropTop4 KNN flatness 终态（2026-08-25）

一次性 MC-only 原生平坦度训练已经完成。五个预声明系数的 weighted OOF AUC 为
`0.7631932798301158` 至 `0.7566586485761435`，最大 OOF ZZ KS 为
`0.25914767204496136` 至 `0.20566162971445773`；没有候选同时通过 AUC >= 0.80
和三个工作点 KS <= 0.10。终态为 `no_eligible_candidate`，test 未开启，未生成
最终模型，也未读取真实数据。详见
[执行报告](../superpowers/plans/2026-08-24-drop-top4-knn-flatness-training-report.md)。

数据和运行产物已经齐备；当前无需再次下载或复制数据。下一开发阶段应先形成新的
预注册方法设计，而不是延长本次系数扫描或降低冻结门槛。

## Full14 封存决定（2026-08-23）

Full14 XGBoost 已封存为失败的历史参考；不是可部署模型，也不是未来真实数据候选。
停止 Full14 + OOF 质量依赖阈值研究，不再对现有模型追加阈值变换、校准、重加权或
调参。冻结的 Full14 与 Full14 重加权结果仅保留用于方法比较；不得修改其 run 或
artifact，不得打开 held-out test，不得读取 periodA。

下一阶段改为另行预先设计的原生质量去相关训练，必须使用新配置和新 run path，且
资格门槛保持 AUC >= 0.80、三个工作点 KS <= 0.10。若未来研究相同 14 个输入变量与
全新去相关目标的组合，必须单独立项和批准，不能延续或复用当前 Full14 模型。

## 当前 1.2 科学结论（2026-08-12）

DSID 363490 的增强 selection 保留 11,976 个连续 ZZ 背景事件。无 `m4l` 的 full-14
XGBoost 能取得 OOF AUC 0.885296，并在 Higgs MC 中显示约 125 GeV 的窄集中；但
其 ZZ OOF 最大质量形状 KS 为 0.457954，说明代理运动学变量仍让分类器学习到了很强
的质量相关性。三个预声明的删特征 profile 均未同时通过 AUC >= 0.80 与所有 KS <=
0.10，因此消融运行按协议发布 `no_eligible_profile`，没有打开 held-out test。

最新冻结的组合实验把最强的四个质量代理（`lep3_pt`、`lep4_pt`、`mZ1`、`mZ2`）
移除，并与固定质量分箱迭代 ZZ 重加权结合。它在
`runs/mass-reweighting-drop-top4-363490-2026-08-12` 正常结束，终态精确为
`no_eligible_iteration`，`selected_iteration: null`，`test_opened: false`。六轮均只
使用 development OOF：重加权使三个工作点的 KS 在第 5 轮都达到 <= 0.10，但 AUC 已由
0.7996529199780816 降为 0.7588712973047708，仍低于不可放宽的 0.80 门槛。因此该
组合尚未解决去相关—判别力权衡；MC test 和 periodA 均未开启。

| 迭代 | OOF AUC | ZZ KS（loose / medium / tight） | 资格 |
|---:|---:|---:|---|
| 0 | 0.7996529199780816 | 0.1754125886831281 / 0.2776300864689386 / 0.34469234042569663 | 否（AUC、三项 KS） |
| 1 | 0.7909840349437066 | 0.14116831342466396 / 0.22668300278758247 / 0.2563535629356366 | 否（AUC、三项 KS） |
| 2 | 0.7840745577657593 | 0.12466822176125592 / 0.1785279696252552 / 0.1845589106499591 | 否（AUC、三项 KS） |
| 3 | 0.7719399667136062 | 0.09349705772211825 / 0.1297707080628676 / 0.12623889191144305 | 否（AUC、medium/tight KS） |
| 4 | 0.7634006325078653 | 0.08043449205869585 / 0.11308325067710806 / 0.1169067754006049 | 否（AUC、medium/tight KS） |
| 5 | 0.7588712973047708 | 0.07416808989370494 / 0.09720271279351 / 0.09406967019374574 | 否（AUC） |

| 方法 | OOF AUC | 最大 OOF ZZ KS | 状态 |
|---|---:|---:|---|
| Full14 | 0.8852959102354316 | 0.4579540115915921 | 冻结参考 |
| Drop top four，无重加权 | 0.7996529199780816 | 0.34469234042569663 | 冻结参考 |
| Full14 + 重加权，第 5 轮 | 0.8523982143190011 | 0.24583464407366806 | 冻结参考；`no_eligible_iteration` |
| Drop top four + 重加权，第 5 轮 | 0.7588712973047708 | 0.09720271279351 | 新结果；`no_eligible_iteration` |

这是一项 MC-only 方法比较，检验减少质量代理与背景重加权是否互补，不是 Higgs
观测、测量或真实数据验证。下一阶段应预先定义较强的去相关目标（例如 uBoost 风格或
对抗式目标）并继续使用相同冻结 AUC/KS 门槛；不得事后加轮、改 bin、降门槛或查看
periodA。

当前下一阶段是质量去相关训练研究；不得事后放宽 AUC/KS 门槛或打开真实数据。

> 跨设备或交给新的 Codex 会话时，请先阅读根目录的 `AGENTS.md`。该文件记录数据传输、环境恢复、校验和、科学约束和当前接手任务。

## 1. 项目目的

这个 Demo 展示一条最小但完整的高能物理机器学习分析链：

1. 从 ROOT 文件读取 Higgs MC、连续 \(ZZ^*\) 背景 MC 和真实数据；
2. 重建四轻子运动学变量；
3. 使用 MC 训练 XGBoost 区分 Higgs 信号与 \(ZZ^*\) 背景；
4. 用独立验证集选择分类阈值；
5. 用独立测试集评价模型和检查过拟合；
6. 固定模型后对真实数据打分；
7. 查看高分事件的四轻子不变质量 \(m_{4\ell}\) 分布。

目标信号过程是：

\[
H \rightarrow ZZ^* \rightarrow 4\ell,\qquad \ell=e,\mu
\]

这是一个分析流程 Demo，不是完整的 ATLAS 物理测量，也不能仅凭当前输出声称观察或重新发现 Higgs 玻色子。

## 2. 当前数据

原始数据位于 `data/raw/`：

| 文件 | 类型 | 用途 |
|---|---|---|
| `higgs.root` | Higgs MC，channel 345060 | 信号，标签 `1` |
| `zz.root` | \(ZZ^*\rightarrow4\ell\) MC，channel 700600 | 背景，标签 `0` |
| `data16_periodA.root` | 真实碰撞数据 | 无标签数据，标签 `-1` |

### 历史 5,000-entry 模型输入

历史模型运行使用 `config/demo.yaml` 的 `entry_stop: 5000`，每个 ROOT 文件最多只读取
前 5,000 条原始记录。该历史运行经过四轻子重建后生成：

| 样本 | 处理后事件数 |
|---|---:|
| Higgs MC | 4,884 |
| ZZ MC | 4,685 |
| 真实数据 | 1,112 |
| 合计 | 10,681 |

处理后的表格位于：

- `data/processed/mc_events.csv.gz`
- `data/processed/data_events.csv.gz`

这些旧表及其后续模型指标没有被 Task 4A 改写。

### Task 4A 全量预处理基准（未训练）

2026-08-10 的全量基准位于 `runs/full-baseline-2026-08-10`：

| 样本 | 完整读取数 | selection 后事件数 |
|---|---:|---:|
| Higgs MC | 419943 | 350928 |
| ZZ MC | 11260 | 471 |
| 真实数据 | 29275 | 226 |

合并后的 MC selection 数为 `351399`；data 的重复 run/event 对为 `0`。CSV gzip
行数与摘要中的 selection 数一致。`run_manifest.json` 使用 schema `1.1`，记录 full
读取策略（`entry_stop: null`、`chunk_size_events: 50000`）、配置快照与 SHA-256、
三个输入文件 SHA-256、输出位置，以及 Higgs/ZZ 的 luminosity、cross section、
k-factor、filter efficiency、sum of weights 和 effective cross section。配置快照哈希
与源配置及 manifest 完全一致；旧 `data/processed/` 和 `outputs/` 未改变。

### 历史 Task 4B/DSID 700600 基准（已被 363490 1.0 取代）

2026-08-11 已实际运行：

```bash
.venv/bin/python -m scripts.train_full_mc \
  --input-run runs/full-baseline-2026-08-10 \
  --config config/full_training.yaml \
  --run-dir runs/full-training-2026-08-11
```

完成运行的 manifest schema 为 `1.0`；全量 MC `351399`，development OOF `281249`，
independent test `70150`。one-standard-error 规则选择 `depth2_child20`，最终树数 `124`；
OOF weighted AUC `0.7819012512935757`，test weighted AUC `0.844677675856134`。

- 工作点阈值：loose `0.4421731233596802`，medium `0.6183240413665771`，tight `0.6919658780097961`。
- OOF 达到的 ZZ / signal efficiency：loose `0.5004580267548995 / 0.8806158272151767`，medium `0.20065226444487125 / 0.5799549950508799`，tight `0.1005088836655481 / 0.4257204708429173`。
- independent-test 达到的 ZZ / signal efficiency：loose `0.4253686842730043 / 0.8807478236049668`，medium `0.11723106326431036 / 0.602126444983588`，tight `0.0556776426566235 / 0.43029827315541624`。

总 warning 为 `true`，唯一原因是 `background_ks_distance`，对应 background KS distance `0.1903422555517139`；
signal KS distance `0.023516517743828735`，mass-sculpting warning 为 `false`。
selected ZZ 总数 `471`（`391 development`、`80 test`），所以背景指标及 OOF/test
差异有很大的统计不确定性。
五张批准图均只使用 MC；质量图只包含 ZZ，不能显示或验证 Higgs 125 GeV 峰。

Task 4B 未读取或评分真实数据，也不声称在真实数据中观察到 125 GeV Higgs 峰。
该历史阶段收尾测试为 `383 passed`。其 471 个 ZZ 事件与旧 warning 不得作为当前
结论；当前结论见本页开头。

## 3. 项目文件

### 配置与入口

| 路径 | 作用 |
|---|---|
| `config/demo.yaml` | ROOT 路径、TTree、单位、channel number、读取上限和模型超参数 |
| `scripts/inspect_root.py` | 检查 ROOT 的 TTree、分支和事件数 |
| `scripts/prepare_demo.py` | 读取 ROOT、构造特征/权重/划分，并写 cutflow、分离摘要和运行 manifest |
| `scripts/train_demo.py` | 训练 XGBoost、验证模型并生成 MC 图 |
| `scripts/evaluate_data.py` | 加载固定模型，对真实数据打分并画 \(m_{4\ell}\) |
| `scripts/make_synthetic_demo.py` | 不依赖 ROOT 的合成数据快速验证入口 |

### 核心模块

| 路径 | 作用 |
|---|---|
| `src/io.py` | 用 uproot 发现 TTree、检查分支并逐事件读取 ROOT |
| `src/pairing.py` | 四动量、SFOS 配对、\(Z_1/Z_2\) 选择和角距离 |
| `src/features.py` | 构造模型特征和 \(m_{4\ell}\)，检查特征泄漏 |
| `src/weights.py` | 计算物理权重和 XGBoost 可接受的训练权重 |
| `src/split.py` | 基于事件号哈希生成稳定的 60/20/20 划分 |
| `src/pipeline.py` | 串联读取、特征、权重、标签和数据划分 |
| `src/provenance.py` | 构造 data/MC 分离摘要、输入 SHA-256、软件/Git 运行 manifest |
| `src/train.py` | 配置并训练 XGBoost，保存模型和验证报告 |
| `src/validation.py` | AUC、阈值扫描、Asimov 显著性、KS 和过拟合判断 |
| `src/progress.py` | 显示 boosting round 训练进度和验证集 AUC |
| `src/plots.py` | 生成 ROC、分数、特征和质量分布图 |

### 测试

| 路径 | 当前覆盖 |
|---|---|
| `tests/test_pairing.py` | 四动量质量、SFOS、\(Z_1/Z_2\)、无效配对、\(\Delta\phi\) 边界 |
| `tests/test_features.py` | MeV→GeV、有限特征、禁止 \(m_{4\ell}\) 等字段进入模型 |
| `tests/test_weights.py` | 物理权重、负权重、训练权重和零分母 |
| `tests/test_split.py` | 划分可重复、集合互斥且无事件丢失 |
| `tests/test_validation.py` | 加权 KS、验证集选阈值、测试集冻结评价和过拟合报告 |
| `tests/test_progress.py` | 训练进度、验证 AUC 后缀、关闭行为和总轮数 |
| `tests/test_summary.py` | data/MC 字段隔离、事件唯一性、MC 权重与摘要校验 |
| `tests/test_manifest.py` | 文件哈希、UTC、软件版本、Git fallback 和 manifest schema |

Task 4A 在 2026-08-10 的冻结验收结果为 `194 passed`；`383 passed` 是历史 Task 8
文档收尾边界。当前接受的 Task 5 pre-run 完整测试结果为 `714 passed`。测试覆盖 selection
配置、所有边界、fixed/sliding Z₂、cutflow 计数/效率、MC signed/absolute yield、
data/MC 摘要隔离、文件哈希、manifest、运行目录隔离、full 读取策略、分块读取和
prepare CLI 接线。Task 4A 已用新 selection 完成全量真实 ROOT 预处理，但没有训练或评分。

## 4. 特征与防止数据泄漏

模型使用 14 个运动学特征：

- 四个轻子的 \(p_T\)；
- 四个轻子的 \(\eta\)；
- \(m_{Z_1}\)、\(m_{Z_2}\)；
- \(p_T^{4\ell}\)；
- 两个 Z 候选内部的 \(\Delta R\)；
- 两个 Z 候选之间的 \(\Delta\phi\)。

每个 feature 的报告级定义、单位、物理意义、轻子排序和 \(Z_1/Z_2\) 配对规则，见[进展简报](../briefings/progress-briefing.md)的“模型细节 → 输入特征”。

以下字段明确禁止进入模型：

- \(m_{4\ell}\)；
- event、run 和 channel number；
- MC 权重、截面和归一化字段；
- 数据来源和 period。

其中最重要的是 \(m_{4\ell}\) 不参与训练。模型完成选择后才查看质量分布，避免模型直接学习“125 GeV 附近就是信号”。

## 5. 历史流程与 Task 4B 流程

### 历史 5,000-entry 端到端流程

下图只描述历史模型：它使用 train/validation/test、在 validation 上做 Asimov 阈值
扫描，并曾对 1,112 条历史真实数据评分。它不是 Task 4B 的训练或应用流程。

```text
ROOT files
   │
   ├─ 检查 TTree、分支、channel number 和单位
   │
   ├─ 要求事件能重建为四个轻子
   ├─ 建立两个 SFOS 轻子对
   ├─ 选择质量最接近 Z 的 Z1，另一个作为 Z2
   ├─ 计算 14 个模型特征和 m4l
   │
   ├─ MC：计算物理权重、标签和 train/validation/test
   └─ Data：标签设为 -1，不参与监督训练
            │
            ▼
      XGBoost 训练（只用 train）
            │
            ├─ validation：选择使 Asimov ZA 最大的阈值
            └─ test：最终 AUC、ZA、KS 和过拟合检查
            │
            ▼
       保存固定模型
            │
            ▼
       对真实数据打分
            │
            ├─ score < threshold
            └─ score ≥ threshold
                    │
                    ▼
              绘制 m4l 分布
```

### Task 4B MC-only 流程

Task 4B 只读取 Task 4A 的 `mc_events.csv.gz`，不打开 `data_events.csv.gz`：

```text
Task 4A full MC (351399)
   │
   ├─ development MC (281249)
   │    ├─ 五折 OOF 比较六个候选
   │    ├─ one-standard-error 规则选择 depth2_child20
   │    ├─ OOF 冻结 loose / medium / tight 三个背景效率工作点
   │    └─ 用全部 development 拟合最终 124 棵树
   │
   └─ independent test MC (70150)
        └─ 只应用冻结模型与工作点，报告 AUC、效率、KS 和质量塑形诊断

真实数据：Task 4B 不读取、不评分、不画图
```

因此，Task 4B 的候选与工作点不由 independent test 或真实数据决定；其五张批准图均为
MC-only，后续真实数据应用属于另行设计的 Task 4C 盲化阶段。

## 6. 历史 5,000-entry 模型验证规则

数据按事件哈希稳定划分：

- Train：约 60%，只用于拟合模型；
- Validation：约 20%，只用于选择阈值和观察训练评价；
- Test：约 20%，只用于最终模型评价。

历史 5,000-entry 模型的集合事件数：

| 集合 | 事件数 |
|---|---:|
| Train | 5,752 |
| Validation | 1,919 |
| Test | 1,898 |

阈值在 validation 上从 `0.05` 到 `0.95`、以 `0.01` 为步长扫描，并最大化：

\[
Z_A=\sqrt{2\left[(S+B)\ln(1+S/B)-S\right]}
\]

历史扫描选择 `0.93`。这个数是历史 5,000-entry 小样本和当时权重下的工作点，
不是 Task 4A 结果、物理常数或校准后的 Higgs 概率。

过拟合检查包括：

- train、validation、test 加权 AUC；
- train-test AUC gap；
- Higgs 和 ZZ 分数分布的加权 KS 距离；
- AUC gap 大于 `0.05` 或 KS 大于 `0.10` 时报警。

## 7. 历史 5,000-entry 训练与评分结果

以下 AUC、KS、阈值和评分数字全部来自历史 5,000-entry、300 轮训练；Task 4A 没有
重训模型、选择阈值或对真实数据评分：

| 指标 | 结果 |
|---|---:|
| Train weighted AUC | 0.9936 |
| Validation weighted AUC | 0.9741 |
| Test weighted AUC | 0.9813 |
| Train-test AUC gap | 0.0123 |
| Signal KS | 0.0867 |
| Background KS | 0.0319 |
| 过拟合警告 | False |
| Validation 选择阈值 | 0.93 |

历史固定模型曾对历史 1,112 个真实数据事件完成打分：

- `score ≥ 0.93`：16 个事件；
- `score < 0.93`：1,096 个事件；
- `122–128 GeV` 内原本有 10 个事件，但没有事件通过 `0.93`；
- 该质量窗内最高分为约 `0.9221`。

因此当前小样本没有在高分区域显示明显的 125 GeV 峰。这个结果不影响端到端 Demo 已经跑通，但不能用于得出物理结论。

## 8. 输出文件

| 文件 | 内容 |
|---|---|
| `outputs/xgboost_demo.json` | 训练后的 XGBoost 模型 |
| `outputs/metrics.json` | 阈值扫描、AUC、预期产额和最终测试指标 |
| `outputs/overfitting_check.json` | AUC gap、KS 和报警原因 |
| `outputs/data_with_xgb_score.csv.gz` | 带 XGBoost 分数的真实数据 |
| `outputs/roc_curve.png` | 测试集加权与非加权 ROC |
| `outputs/train_test_score_comparison.png` | train/test 信号与背景分数比较 |
| `outputs/score_vs_m4l.png` | 分数与质量的相关性检查 |
| `outputs/feature_distributions.png` | MC 特征分布 |
| `outputs/m4l_before_xgb.png` | 真实数据选择前质量分布 |
| `outputs/m4l_low_score.png` | 低分真实数据质量分布 |
| `outputs/m4l_high_score.png` | 高分真实数据质量分布 |

## 9. 如何重新运行

```bash
# 先进入复制或克隆后的项目根目录
cd /path/to/higgs-xgboost-demo
source .venv/bin/activate

python -m pytest -q
python -m scripts.prepare_demo --config config/demo.yaml \
  --run-dir runs/<new-smoke-run-name>

# 全量 Task 4A 预处理；必须使用另一个不存在的新目录
python -m scripts.prepare_demo --config config/demo.yaml --full \
  --run-dir runs/<new-full-run-name>
```

预处理本身不会训练或评分。Task 4B 已通过上面的独立 MC-only 命令完成；真实数据
应用不属于该命令，仍需单独设计和授权。

### 在另一台设备恢复

把 `higgs-xgboost-demo` 文件夹本身作为 Codex 工作区打开，这样根目录的 `AGENTS.md` 才能作为项目级交接说明生效。

不要复制旧设备的 `.venv`，应在新设备重新创建：

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

如果项目通过 Git 传输，需要额外手动复制三个 ROOT 文件，因为 `data/raw/` 被 `.gitignore` 排除。处理后 CSV、模型和图片同样不会随 Git 传输，可以在新设备重新运行完整流程生成。具体路径、大小、SHA-256 和验收输出见 `AGENTS.md`。

## 10. 当前限制

1. 历史模型每个 ROOT 文件只读取前 5,000 条记录；Task 4A 已完成全量预处理，
   Task 4B 已完成全量 MC 训练，但两者与历史结果必须分开解释。
2. 只使用一个真实数据 period，统计量很少。
3. selection、Z 质量窗和四轻子质量窗已接入并用于 Task 4A 全量预处理；历史
   processed data、模型和图片没有按该全量基准重建。
4. 目前没有触发、隔离、identification、impact parameter 等更完整分析选择。
5. Task 4A 已在独立 run 目录生成真实 ROOT 的新摘要、cutflow 和 manifest；现有
   `outputs/data_summary.json` 仍是历史运行产物。
6. 使用全部 validation 事件优化 Asimov 阈值是历史 5,000-entry 流程的限制；Task 4B
   改用 development OOF 冻结三个背景效率工作点，但尚无系统误差模型。
7. 历史 \(Z_A\) 数值不能解释为正式预期显著性；Task 4B 不使用 \(Z_A\) 选择工作点。
8. 没有系统误差、控制区、sideband 或质量谱统计拟合。

## 11. 后续需要补充的测试用例

### 最高优先级

1. **ROOT I/O 测试**
   - 缺少必要分支时给出准确错误；
   - TTree 自动发现和显式名称行为一致；
   - channel number 不匹配时失败；
   - MC 与 data 的必需分支集合不同。

2. **小型端到端集成测试**
   - 用测试生成的微型 ROOT 文件运行 prepare；
   - 训练一个很小的模型；
   - 保存并重新加载模型后预测完全一致；
   - evaluate 输出事件数与输入一致。

3. **权重与抽样测试**
   - 全样本和确定性抽样的归一化关系正确；
   - train/validation/test 的加权产额之和守恒；
   - 负权重只在训练副本中取绝对值，物理产额仍保留符号。

### 第二优先级

5. **可重复性测试**
   - 相同随机种子产生一致预测和指标；
   - 改变输入行顺序不改变事件划分；
   - 模型特征列顺序被固定并验证。

6. **阈值稳定性测试**
   - validation 的小扰动不会造成不合理的大幅阈值变化；
   - 测试集标签或分数变化不能反向影响阈值；
   - 当所有候选阈值的背景为零时行为明确。

7. **数据质量测试**
   - 重复 event number 检测；
   - NaN、无穷值、数组长度不一致和非法单位；
   - 四动量产生负质量平方时的数值边界。

8. **绘图与报告测试**
   - 所有预期图片和 JSON 均非空；
   - JSON 数值有限且字段版本明确；
   - 图标题中的阈值与 `metrics.json` 一致。

更具体的升级顺序见[下一阶段路线图](../roadmap/next-stage.md)。
