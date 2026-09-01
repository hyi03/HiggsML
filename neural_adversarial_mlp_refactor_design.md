# HiggsML `neural` 对抗式 MLP 重构设计与实施计划

**文档状态：** 已确认方案  
**日期：** 2026-09-01  
**目标目录：** `neural/`
**原工程：** `xgboost/`，保持原状，不作为新程序的运行时依赖

## 1. 方案摘要

在仓库根目录新建独立工程 `neural/`，把现有多代 Demo、专用研究脚本和通用训练入口收敛为两个可执行程序：

1. `higgsml-preprocess`：完成严格 MC-only 的 ROOT 读取、四轻子重建、selection、权重、稳定划分、Base14 与 Angular5 特征构造以及审计产物发布。
2. `higgsml-train`：使用 PyTorch 对抗式多层感知机完成 development OOF 训练、质量去相关资格判断，以及经过显式授权的 held-out MC test-opening。

预处理的科学行为保持不变，但重新实现为职责清晰、可测试的模块；不复制现有千行级 run 模块，也不调用旧 `xgboost/`。预处理表输出完整 19 项特征，训练协议固定使用 DropTop4 后的 10 项基础特征与 5 项 Angular5 特征，共 15 项。

神经网络采用约 9,228 个可训练参数的紧凑结构。其规模依据 199,104 条 MC、其中仅 11,976 条 ZZ 背景的实际数据瓶颈确定。模型通过背景质量分箱对抗器直接抑制 score 对 `m4l` 的依赖，不使用 OmniLearn/PET 这类面向大规模 jet constituent 点云的模型。

## 2. 当前工程事实与重构动机

当前 `xgboost/` 同时存在三类流程：

- 早期 Demo：`prepare_demo`、`train_demo`、`evaluate_data`；
- Full14、消融、质量分箱重加权、KNN flatness、Angular5 等专用冻结研究；
- 最近加入的通用 `higgsml train/predict/evaluate-test` 入口。

这些流程重复实现配置解析、输入绑定、输出事务、manifest、模型选择和 test-opening，部分源码模块已超过 1,000 行。新工程不迁移全部历史工作流，而是整理出一条明确的、可复现的最终主线。

当前权威 MC 数据规模为：

| 项目 | 数量 |
|---|---:|
| Higgs 345060 selection 后事件 | 187,128 |
| ZZ 363490 selection 后事件 | 11,976 |
| MC 总数 | 199,104 |
| Development（train + validation） | 159,395 |
| Held-out test | 39,709 |
| Train / validation / test | 119,676 / 39,719 / 39,709 |

类别计数约为 15.6:1，但物理产额并非同样失衡，因此训练继续使用按类别归一化的 `abs(physical_weight)`，物理产额报告继续使用 signed `physical_weight`。

## 3. 范围与不可变约束

### 3.1 本次范围

- 新建独立 Conda 环境和独立 Python package；
- 行为等价重写最终 MC 预处理流程；
- 输出 Base14 + Angular5 共 19 项特征；
- 实现固定规模的对抗式 MLP；
- 实现 5-fold development OOF、资格门槛、模型封存和显式 test-opening；
- 生成配置快照、输入与输出哈希、指标、预测、图和 manifest；
- 建立单元、集成、golden、CLI 和端到端 smoke 测试；
- 整理旧工程最终科学结论，但不迁移历史实验执行器。

### 3.2 不在本次范围

- 不读取、哈希、预处理、评分或绘制真实数据；
- 不迁移 Full14、删特征消融、六轮质量重加权或 KNN flatness 为可执行工作流；
- 不实现 OmniLearn、PET、扩散生成、异常检测或 likelihood-ratio estimation；
- 不打开已封存 run，不覆盖旧产物；
- 不增加系统误差、控制区、sideband 或质量谱 likelihood；
- 不把结果描述为 ATLAS 结果、Higgs 发现或物理测量。

### 3.3 科学安全约束

- `m4l`、event/run/channel 标识、source/provenance 字段和权重不得进入分类器；
- 真实数据不得用于监督训练；
- test 不得用于架构、超参数、去相关强度、阈值或 epoch 选择；
- test 仅能由已经封存的 development run 显式开启一次；
- AUC、KS 和信号效率门槛不得因结果不理想而事后放宽；
- 所有 run 目录默认不可覆盖，失败 run 也保留失败收据。

## 4. OmniLearn/PET 评估结论

OmniLearn 的 PET 适合含大量、变长 jet constituents 的点云输入，通过节点、边和 class-token 学习 jet 表示。当前任务是固定四轻子事件，现有预处理输出是事件级 19 项连续变量，不包含完整逐轻子 `phi`、能量、charge、flavour、mask 和显式 pair-edge 张量。

因此 OmniLearn 不能在“预处理方案保持不变”的条件下直接使用。即使扩展输入，每个事件只有四个节点，完整 PET 的注意力与边建模优势有限；相对于 11,976 个背景事件，其参数规模和预训练域差异也会增加过拟合与迁移不确定性。PET 同样不会自动解决 `m4l` 塑形问题。

若未来单独立项研究结构化四轻子模型，可考虑 2–3 层、`d_model=32–64`、4 heads、约 5–20 万参数的轻量 Set Transformer/PET，并重新定义逐轻子输入契约。该方向不得作为本次 MLP 的失败后备分支。

## 5. 目标工程结构

```text
neural/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── environment.yml
├── osx.yml
├── win.yml
├── config/
│   ├── preprocess_protocol_v1.yaml
│   ├── preprocess_run.example.yaml
│   └── adversarial_mlp_protocol_v1.yaml
├── src/
│   ├── cli/
│   │   ├── preprocess.py
│   │   └── train.py
│   ├── config.py
│   ├── domain/
│   │   ├── four_vectors.py
│   │   ├── reconstruction.py
│   │   ├── selection.py
│   │   ├── features.py
│   │   ├── angular5.py
│   │   ├── weights.py
│   │   └── splitting.py
│   ├── preprocessing/
│   │   ├── root_reader.py
│   │   ├── pipeline.py
│   │   └── outputs.py
│   ├── training/
│   │   ├── dataset.py
│   │   ├── network.py
│   │   ├── losses.py
│   │   ├── folds.py
│   │   ├── trainer.py
│   │   ├── qualification.py
│   │   └── test_opening.py
│   └── artifacts/
│       ├── manifest.py
│       ├── transaction.py
│       └── plots.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── golden/
│   └── fixtures/
├── data/
│   └── .gitkeep
└── runs/
    └── .gitkeep
```

每个模块只承担一个明确职责。CLI 只负责解析参数和调用 application service；科学计算不写在 CLI 或 artifact 发布代码中。

## 6. 两个可执行程序

`pyproject.toml` 只发布以下两个 console entry points：

```toml
[project.scripts]
higgsml-preprocess = "src.cli.preprocess:main"
higgsml-train = "src.cli.train:main"
```

### 6.1 预处理

```bash
conda run -n pytorch higgsml-preprocess \
  --protocol config/preprocess_protocol_v1.yaml \
  --run-config config/preprocess_run.local.yaml \
  --run-dir runs/preprocess-<unique-id>
```

运行配置只允许指定 ROOT 路径、输出路径、chunk size 和资源参数。Selection、输入 profile、DSID、归一化、特征定义、split 算法与预期 SHA-256 位于版本化 protocol 中；普通命令行不能覆盖这些科学规则。

### 6.2 Development 训练

```bash
conda run -n pytorch higgsml-train develop \
  --input-run runs/preprocess-<id> \
  --protocol config/adversarial_mlp_protocol_v1.yaml \
  --run-dir runs/mlp-development-<unique-id>
```

该命令只读取 development 行，完成五折 OOF、候选 λ 比较、资格判断和工作点冻结。若没有合格候选，不生成最终模型。

若存在合格候选，则使用全部 development 行拟合并封存最终 scaler 与模型，但仍不读取 test 行的特征值或产生 test 预测。

### 6.3 显式 test-opening

```bash
conda run -n pytorch higgsml-train open-test \
  --development-run runs/mlp-development-<id> \
  --run-dir runs/mlp-test-<unique-id>
```

`open-test` 是同一个训练可执行程序的独立子命令。它必须验证：

- development manifest 完整且状态为 eligible；
- 输入表、protocol、scaler、模型、工作点和 OOF 证据哈希未变化；
- development run 尚无 test-opening 收据；
- 输出目录不存在且位于允许的 `runs/` 根下。

命令通过原子 claim 文件占用唯一 test-opening 槽位。成功或失败均写入收据，后续重复开启被拒绝。Test 结果只评价已冻结模型，不影响任何模型或阈值。

## 7. 预处理数据契约

### 7.1 输入

- Higgs MC：DSID 345060；
- 连续 ZZ MC：DSID 363490；
- ROOT 文件路径由 run YAML 提供，默认可指向旧工程或外部只读数据目录；
- protocol 固定输入 SHA-256：
  - Higgs：`5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0`；
  - ZZ：`76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07`。

`neural` 不复制大 ROOT 文件，也不依赖旧工程 Python 代码。只读数据路径是可配置的；输入内容由 SHA-256 绑定。

### 7.2 保持不变的处理行为

- 相同 release22/open-data 输入 profile 和单位转换；
- 相同 trigger、ID、isolation、impact parameter、四轻子、SFOS、Z1/Z2 与 `m4l` selection；
- 相同 MC normalization；
- signed `physical_weight` 与归一化 `abs` 训练权重语义；
- 稳定 train/validation/test 划分；
- canonical `(source_sample, source_entry)` identity；
- 相同 Base14 和 Angular5 数学定义、角度范围和确定性配对。

### 7.3 输出列

预处理表必须包含以下 19 项可选模型特征：

```text
lep1_pt, lep2_pt, lep3_pt, lep4_pt,
lep1_eta, lep2_eta, lep3_eta, lep4_eta,
mZ1, mZ2, pt4l, deltaR_Z1, deltaR_Z2, deltaPhi_ZZ,
cos_theta_star, cos_theta_1, cos_theta_2,
phi_decay_planes, phi_production_plane
```

并包含非模型字段：

```text
m4l, label, split, physical_weight, train_weight,
source_sample, source_entry, runNumber, eventNumber, channelNumber
```

训练协议只选择以下 15 项：

```text
lep1_pt, lep2_pt,
lep1_eta, lep2_eta, lep3_eta, lep4_eta,
pt4l, deltaR_Z1, deltaR_Z2, deltaPhi_ZZ,
cos_theta_star, cos_theta_1, cos_theta_2,
phi_decay_planes, phi_production_plane
```

`lep3_pt`、`lep4_pt`、`mZ1`、`mZ2` 留在预处理表中但禁止进入 v1 分类器。

### 7.4 预处理产物

```text
runs/preprocess-<id>/
├── config.yaml
├── processed/mc_events.csv.gz
└── artifacts/
    ├── cutflow.json
    ├── mc_summary.json
    └── manifest.json
```

Manifest 记录原始输入、protocol、配置、软件、Git、事件数、列 schema 和全部输出 SHA-256。为避免 gzip 时间戳导致伪差异，同时记录解压后 canonical CSV 内容哈希。

## 8. 对抗式 MLP 设计

### 8.1 输入变换

- 仅标准化 15 项分类器输入；
- 每个 OOF fold 的 scaler 只在该 fold 的 fitting 子集拟合；
- 最终 scaler 只在全部 development 上拟合；
- 不对 `m4l` 做分类器输入变换；它只用于背景对抗标签和资格检查；
- 缺失值、无穷值、列顺序变化或 forbidden feature 一律 fail closed。

### 8.2 分类器

```text
15
 └─ Linear(15, 64) → LayerNorm → SiLU → Dropout(0.10)
    └─ Linear(64, 64) → LayerNorm → SiLU → Dropout(0.10)
       └─ Linear(64, 32) → LayerNorm → SiLU
          └─ Linear(32, 1) → logit
```

分类器约 7,617 个参数。

### 8.3 背景质量对抗器

对抗器只接收背景事件的分类器标量 logit，经 Gradient Reversal Layer 后预测 11 个固定 `m4l` bin：`[105,110), ..., [155,160]`。

```text
1
 └─ Linear(1, 32) → LayerNorm → SiLU
    └─ Linear(32, 32) → LayerNorm → SiLU
       └─ Linear(32, 11)
```

对抗器约 1,611 个参数，完整模型约 9,228 个参数。

### 8.4 损失与权重

分类损失：

```text
L_cls = weighted BCEWithLogits(label, logit)
```

分类权重继续使用按类别归一化的 `abs(physical_weight)`；负物理权重不得直接传给优化器。

对抗损失：

```text
L_adv = weighted CrossEntropy(m4l_bin, adversary(logit))  # background only
```

背景对抗权重先在每个质量 bin 内按 `abs(physical_weight)` 归一化，再让 11 个 bin 具有相同总权重，防止对抗器只学习自然质量先验。Gradient Reversal 使分类器优化方向等价于：

```text
min_classifier L_cls - λ·L_adv
min_adversary  L_adv
```

### 8.5 固定训练参数

| 参数 | 值 |
|---|---:|
| Optimizer | AdamW |
| Learning rate | `1e-3` |
| Weight decay | `1e-4` |
| Batch size | `1024` |
| Maximum epochs | `200` |
| Early-stopping patience | `20` |
| Minimum AUC improvement | `1e-4` |
| Classifier warm-up | `5` epochs |
| λ linear ramp | following `10` epochs |
| Base random seed | `42` |
| PyTorch device | CPU/ARM64 authority |

每个 fold 使用 `seed = 42 + fold_index`；不同 λ 候选在同一 fold 复用相同初始化种子和 batch 顺序，以降低候选比较噪声。Checkpoint 仅按该 fold validation weighted AUC 早停，不使用 test。

## 9. OOF、候选选择与资格门槛

### 9.1 Development folds

原 `train` 与 `validation` 合并为 development，使用 canonical identity 的稳定哈希分成五折。相同 source identity 永远进入同一 fold，禁止跨 fold 或跨 split 重复。

### 9.2 预注册 λ 候选

```text
0.00, 0.05, 0.10, 0.20, 0.50
```

`λ=0` 是相同网络架构的普通加权 MLP 基线。层数、宽度、dropout、optimizer、质量 bins 和 λ 列表均不进行运行时网格扩展。

### 9.3 工作点

只使用 development OOF 背景分数确定：

| 名称 | 目标背景效率 |
|---|---:|
| loose | 0.50 |
| medium | 0.20 |
| tight | 0.10 |

### 9.4 资格规则

一个 λ 候选必须同时满足：

- weighted development OOF AUC `>= 0.80`；
- loose、medium、tight 三个工作点的 OOF ZZ `m4l` KS 均 `<= 0.10`；
- 每个工作点的 signal efficiency 严格高于 achieved ZZ efficiency；
- OOF 预测完整、有限且每行恰好出现一次。

若多个候选合格，选择 weighted OOF AUC 最高者；若绝对差不超过 `1e-6`，选择较小 λ。若无候选合格，终态固定为 `no_eligible_candidate`，不生成模型且不允许 test-opening。

最终模型使用全部 development 数据、选定 λ、相同网络和 scaler。训练 epoch 数取五个 fold 最佳 epoch 的中位数并向最近整数取整，不再重新早停。

## 10. 训练与 test 产物

### 10.1 Development run

```text
runs/mlp-development-<id>/
├── config.yaml
├── artifacts/
│   ├── candidate_metrics.csv
│   ├── fold_metrics.csv
│   ├── qualification.json
│   ├── working_points.json
│   └── manifest.json
├── predictions/
│   └── oof_scores.csv.gz
├── model/                    # 仅 eligible 时存在
│   ├── model.pt
│   └── scaler.json
├── plots/
│   ├── auc_vs_lambda.png
│   ├── ks_vs_lambda.png
│   ├── oof_roc.png
│   └── oof_mass_sculpting.png
└── state/
    └── test_opening.json     # open-test 后写入的唯一审计状态
```

### 10.2 Test run

```text
runs/mlp-test-<id>/
├── artifacts/
│   ├── test_metrics.json
│   └── manifest.json
├── predictions/test_scores.csv.gz
└── plots/
    ├── test_roc.png
    └── test_mass_sculpting.png
```

Test 使用 OOF 冻结阈值，报告相同 AUC、KS 和效率指标。它只产生 `test_reproduced` 或 `test_nonreproduction` 结论，不触发重训或阈值调整。

## 11. Conda 与精确复现

独立环境名称固定为 `pytorch`。`environment.yml` 声明跨平台直接依赖，`osx.yml` 锁定权威 `osx-arm64` 环境，`win.yml` 锁定 `win-64` 开发与测试环境。首个权威环境以以下已验证基线为起点：

```text
Python 3.12.13
NumPy 2.5.1
pandas 3.0.5
PyYAML 6.0.3
uproot 5.7.5
scikit-learn 1.9.0
matplotlib 3.11.1
mplhep 1.3.2
awkward 2.12.0
vector 1.8.1
tqdm 4.70.0
PyTorch 2.7.1 CPU
pytest
conda-lock
```

创建与验证命令：

```bash
conda-lock install --name pytorch osx.yml
conda run -n pytorch python -m pip check
conda run -n pytorch python -m pytest -q
```

Windows 开发与测试环境使用：

```powershell
conda-lock install --name pytorch win.yml
conda run -n pytorch python -m pip check
conda run -n pytorch python -m pytest -q
```

权威训练强制 CPU、单线程数据加载、固定随机种子和 `torch.use_deterministic_algorithms(True)`；禁用 MPS/CUDA。Manifest 记录 CPU 架构、操作系统、PyTorch build、线程数和 deterministic 标志。跨平台运行可用于开发测试，但不得声明与 ARM64 权威 run 精确等价。

## 12. 测试设计

### 12.1 预处理单元测试

- MeV/GeV 转换、四动量与不变质量；
- SFOS 配对、Z1/Z2 决策和无效事件；
- 每一级 selection 边界与 cutflow；
- Angular5 取值范围、符号约定和退化几何；
- signed/absolute 权重与负权重；
- 稳定 split 和 canonical identity；
- forbidden feature 检测。

### 12.2 训练单元测试

- 网络输入、输出 shape 和精确参数量；
- Gradient Reversal 的梯度符号；
- 对抗器只接收背景行；
- 分类与质量 bin 权重归一化；
- fold scaler 无泄漏；
- λ tie-break、资格门槛和无合格终态；
- test-opening claim、哈希变化和重复开启拒绝。

### 12.3 Golden 与集成测试

- 微型 ROOT fixture 全链生成 19 项特征；
- 同一输入重复预处理的 canonical CSV 哈希一致；
- 权威 ROOT 全量结果为 187,128 Higgs、11,976 ZZ、共 199,104 行；
- 19 项特征、metadata 列和行顺序与旧最终方案逐列比较；
- 相同 seed 的两次小型 CPU 训练得到相同模型参数和 OOF 分数；
- CLI 从预处理到 `no_eligible_candidate` 或 eligible 模型发布的 smoke test；
- `open-test` 在无资格、哈希不符和重复调用时 fail closed。

### 12.4 性能验收

性能指标不是预先保证的结果，但完整权威 run 必须：

- 发布所有五个 λ 候选的五折 OOF 证据；
- 严格按冻结规则选择或拒绝模型；
- 不因模型不合格而访问 test；
- 记录 wall time、峰值内存和每 epoch 吞吐；
- 在当前 Apple Silicon 主机上无需 GPU 即可完成。

## 13. 实施阶段

### 阶段 1：工程骨架与环境

- 创建 `neural/`、`pyproject.toml`、独立 Conda lock、两个空 CLI 和基础测试；
- 配置源码安装、日志、异常退出码、不可覆盖 run 事务；
- 验证新 package 不导入 `xgboost/src`。

**阶段验收：** 两个 `--help` 可运行，环境可从 lock 重建，空测试套件通过。

### 阶段 2：行为等价预处理

- 先为旧流程建立 characterization/golden fixtures；
- 按 domain、I/O、pipeline、artifact 四层重写；
- 合并 identity 与 Angular5 enrichment，使一个预处理命令直接发布最终 19 项表；
- 用微型 ROOT 和权威全量计数验证等价性。

**阶段验收：** 事件数、列顺序、cutflow、权重、split、19 项特征和 canonical 内容全部通过。

### 阶段 3：对抗式 MLP 核心

- 测试驱动实现 dataset、scaler、网络、GRL、损失和确定性训练循环；
- 使用合成数据证明 λ 增大时 GRL 梯度方向正确；
- 固定参数量与 protocol schema。

**阶段验收：** 小数据 CPU 训练可重复，参数量为约 9,228，禁止字段无法进入模型。

### 阶段 4：OOF 与资格系统

- 实现五折训练、OOF 汇总、工作点、AUC/KS/效率和 λ 选择；
- 发布完整候选证据、图和 manifest；
- 覆盖 eligible、no-eligible、异常中止三种终态。

**阶段验收：** 测试证明 test 行从未进入 development 的 scaler、训练、早停或资格判断。

### 阶段 5：显式 test-opening

- 实现 development artifact 绑定、唯一 claim、模型加载和 test 指标发布；
- 验证重复开启、产物篡改和未知目录全部拒绝；
- Test 失败不触发任何重训。

**阶段验收：** 只有 eligible 且未开启的冻结 run 能产生一次 test 收据。

### 阶段 6：全链复现与文档

- 在锁定 ARM64 Conda 环境中从原始 ROOT 执行全量预处理；
- 执行完整 development OOF；
- 仅在满足资格且另有明确授权时执行 `open-test`；
- 更新 README、运行手册、artifact schema 和最终技术报告。

**阶段验收：** 完整 pytest、CLI smoke、全量预处理 golden、manifest 审计和文档命令全部通过。

## 14. 总体验收标准

重构只有在以下条件全部满足时才算完成：

1. 原 `xgboost/` 的代码、配置、数据和冻结 runs 未被修改；用户现有未提交修改被保留。
2. `neural` 可仅凭 README、Conda lock、两个 MC ROOT 和配置从零恢复。
3. 对外只有 `higgsml-preprocess` 与 `higgsml-train` 两个程序。
4. 预处理生成 199,104 行、19 项特征和完整 provenance，科学行为与旧最终方案等价。
5. 分类器固定为约 9k 参数的对抗式 MLP，训练只使用固定 15 项特征。
6. 五个 λ 候选、五折 OOF、门槛、tie-break 和 test-opening 均由版本化协议锁定。
7. 无合格候选时不存在模型与 test artifact；有合格候选时 test 仍需显式二阶段开启。
8. 所有结论都有配置、哈希、指标、图、manifest 和自动化测试证据。

## 15. 已采用的默认决定

- 新目录：`neural/`；
- 原工程：完全保留；
- 数据边界：严格 MC-only；
- 原始 ROOT：通过外部只读路径使用，并用 SHA-256 绑定，不复制进 v2；
- 预处理：行为等价重写，输出全部 19 项特征；
- 训练输入：固定 DropTop4 + Angular5 的 15 项；
- 网络：约 9,228 参数的对抗式 MLP；
- 框架：PyTorch CPU；
- 去相关候选：`λ={0,0.05,0.10,0.20,0.50}`；
- 资格：AUC `>=0.80`、三个 KS `<=0.10`、三工作点信号效率高于背景效率；
- Test：显式二阶段、单次开启；
- 权威平台：锁定的原生 `osx-arm64` Conda 环境。
