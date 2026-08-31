# H → ZZ* → 4ℓ XGBoost Demo

## Angular5 + DropTop4 重加权终态（ARM64，2026-08-26）

原生 ARM64 的一次性、MC-only 15 特征研究已经完成；它在 DropTop4 的十个特征上仅追加
五个 Angular5 角变量。六个 development-OOF iteration 没有任何一个同时满足冻结的
weighted AUC >= 0.80 与 loose/medium/tight 三个 ZZ KS 均 <= 0.10 门槛，终态为
`no_eligible_iteration`、`selected_iteration: null`、`test_opened: false`。iteration 0 的
AUC `0.805150881259955` 通过，但三个 KS 都失败；iteration 5 的三个 KS 都通过（最大
`0.090638729937013`），但 AUC `0.7665404021047497` 失败。所有信号效率门槛均通过，
却不能替代 AUC/KS 资格条件。

因此没有最终模型、held-out MC test 指标或预测，也没有读取、哈希、评分、绘图或盘点
真实数据。完整的 six-iteration 数值、证据收据、ARM64 环境与历史比较见
[执行报告](docs/superpowers/plans/2026-08-26-drop-top4-angular5-r3-arm64-report.md)。这项
工作是教育/技术性的 MC-only 方法研究，不是 ATLAS 结果、Higgs 发现或物理测量；本报告
不授权下一阶段训练、test-opening 或真实数据访问。

## DropTop4 原生平坦度训练结论（2026-08-25）

预先设计的 MC-only `hep_ml` KNN flatness 研究已完成，冻结 run 为
`runs/decorrelation-drop-top4-363490-2026-08-24`。五个系数候选均未通过既定的
OOF AUC >= 0.80 与三个工作点 KS <= 0.10 门槛，终态为
`no_eligible_candidate`、`selected_candidate: null`、`test_opened: false`。
因此没有最终模型，held-out MC test 和真实数据均未开启。完整证据见
[执行报告](docs/superpowers/plans/2026-08-24-drop-top4-knn-flatness-training-report.md)。

下一步不是下载更多数据、补扫系数或放宽门槛，而是为新的去相关目标或
template/sideband 统计方案另行预注册设计、配置和 run path。

## Full14 封存决定（2026-08-23）

Full14 XGBoost 已封存为失败的历史参考；不是可部署模型，也不是未来真实数据候选。
停止 Full14 + OOF 质量依赖阈值研究，不再通过阈值变换、校准、追加重加权或调参
补救现有模型。所有既有 Full14 run 和 artifact 保持不可修改；不得打开 held-out test，
不得读取 periodA。

后续原生质量去相关训练必须另行预先设计，使用新配置和新 run path，并继续满足
AUC >= 0.80、三个工作点 KS <= 0.10。现有 Full14 指标只用于历史方法比较。

## 当前 1.0 结论（2026-08-11）

MC-only 方法学 1.0 已完成。官方 DSID 363490 连续 ZZ MC 经完整 selection 后得到
11,976 个背景事件，是旧 DSID 700600 基准 471 个事件的 25.4 倍。14 特征模型不含
`m4l`，OOF/test AUC 为 0.885296/0.894054，Higgs MC 在 125 GeV 附近形成窄峰；
但该模型会明显塑造 ZZ 质量谱（OOF 最大 KS 0.457954）。

预先声明的三种删特征方案均未同时达到 OOF AUC >= 0.80 和所有工作点 KS <= 0.10，
真实消融运行因此以 `no_eligible_profile` 正常结束，held-out test 未开启。这个结果说明
简单删特征不足以兼顾分类能力和背景质量形状，而不是程序失败。下一步应研究带质量
去相关约束的训练；门槛不能事后放宽，真实数据仍保持封存。详见
[Task 8D 报告](../.superpowers/sdd/2026-08-11-dsid-363490-training/task-8d-report.md)
和[迁移交接](CODEX_ACCOUNT_MIGRATION_HANDOFF.md)。

当前下一阶段是质量去相关训练研究；不得事后放宽 AUC/KS 门槛或打开真实数据。

跨设备开发或交给新的 Codex 会话时，先阅读 [AGENTS.md](AGENTS.md)，再阅读
[项目总览](docs/project/overview.md) 和
[下一阶段路线图](docs/roadmap/next-stage.md)。完整文档导航见
[docs/README.md](docs/README.md)。

与导师讨论当前进展时，可使用
[进展简报](docs/briefings/progress-briefing.md)。

这是一个由[原始 Demo 设计](docs/archive/original-demo-spec.md)演进而来的最小端到端分析工程：

1. 从一个 Higgs MC、一个连续 ZZ* MC 和一个真实数据 period 读取 ROOT；
2. 统一 MeV/GeV 单位，完成四轻子 SFOS 配对与物理特征构造；
3. 按事件哈希做 60%/20%/20% 的训练、验证和测试划分；
4. 使用物理权重训练并评价 XGBoost；
5. 固定模型后对真实数据打分，比较选择前后的四轻子质量分布。

Demo 只验证分析链，不代表 ATLAS 官方测量，也不能用于声称重新发现希格斯玻色子。

## 通用 XGBoost 实验入口

面向新的技术实验，项目提供统一命令：

```bash
python -m scripts.higgsml <train|predict|evaluate-test> ...
```

它读取已经完成 selection、权重计算和数据集划分的 processed MC CSV/CSV.GZ；不读取
ROOT、不生成新的 split，也不会自动处理真实数据。历史封存研究仍使用各自原有命令、
配置和 manifest；通用入口不会修改或替代这些冻结流程。

### 训练与调参

```bash
python -m scripts.higgsml train \
  --input runs/<prepared-run>/processed/mc_events.csv.gz \
  --output-dir runs/<new-experiment> \
  --config config/experiment_training.yaml \
  --feature-profile base14 \
  --feature lep4_pt=off \
  --max-depth 2 --max-depth 3 \
  --min-child-weight 5 --min-child-weight 20 \
  --learning-rate 0.05
```

训练命令默认显示 XGBoost boosting round 进度。交叉验证阶段会分别显示每个候选参数和
fold（例如 `Candidate 1/4 fold 2/5`）的完成比例及最新 validation AUC；候选选择完成后
再显示 `Final model` 的训练进度。early stopping 提前终止时，进度条保留实际完成轮数。
在 CI、日志重定向或不需要交互输出时可关闭进度条：

```bash
python -m scripts.higgsml train \
  --input runs/<prepared-run>/processed/mc_events.csv.gz \
  --output-dir runs/<new-experiment> \
  --config config/experiment_training.yaml \
  --feature-profile base14 \
  --no-progress
```

输入表必须包含 `label`、`split`、`physical_weight`、`channelNumber`、
`eventNumber`、`m4l` 和全部启用的 feature。配置优先级为内置默认值、YAML、命令行；
后者优先级最高。以下参数既可在 YAML 中配置，也可使用同名命令行参数覆盖：

- `n_estimators`、`early_stopping_rounds`、`random_seed`、`n_jobs`、`tree_method`、`folds`；
- `learning_rate`、`max_depth`、`min_child_weight`、`subsample`、
  `colsample_bytree`、`reg_alpha`、`reg_lambda`。

第二组参数可重复传入。每项只有一个值时运行单个候选；任一参数有多个值时按笛卡尔积
运行网格，并以 mean weighted development-OOF AUC 选择候选，相同时保留配置展开顺序
中的第一个候选。训练权重继续使用按类别归一化的 `abs(physical_weight)`。

`base14` 包含现有 14 个基础 feature；`angular19` 在其后追加五个 Angular5 feature。
Profile 内所有 feature 默认开启，可以重复使用 `--feature NAME=on|off` 覆盖。最终列顺序
始终由 profile 决定。`m4l`、事件/样本标识、来源字段和权重字段永远不能作为模型输入。

`train` 只使用 train/validation development 行完成 OOF、参数与工作点选择，再在全部
development 行拟合固定模型；不会评分 held-out test。输出目录包含：

```text
model.json
effective_config.yaml
manifest.json
metrics.json
cv_results.csv
oof_scores.csv.gz
plots/
```

### 固定模型预测

```bash
python -m scripts.higgsml predict \
  --input data/new_events.csv.gz \
  --model-dir runs/<experiment> \
  --output-dir runs/<new-prediction>
```

`predict` 从训练 manifest 读取固定 feature 及顺序，生成 `predictions.csv.gz`。输入若包含
任何 `split=test` 行会失败，避免绕过独立 test 入口。

### 独立 test 评价

模型方案固定后，显式运行：

```bash
python -m scripts.higgsml evaluate-test \
  --input runs/<prepared-run>/processed/mc_events.csv.gz \
  --model-dir runs/<experiment> \
  --output-dir runs/<new-test-evaluation>
```

该命令只评分 `split=test`，不允许覆盖 feature、参数或工作点，输出
`test_scores.csv.gz`、`metrics.json`、`manifest.json` 和 `plots/`。

所有子命令默认拒绝已有输出目录。`--overwrite` 只接受已有 manifest 明确标记为通用
实验产物的目录，并在新产物完整生成后原子替换；未知目录、软链接、源码/配置/数据目录
和封存研究输出均拒绝覆盖。每份 manifest 都记录输入、模型和输出 SHA-256、软件版本、
最终 feature、有效参数和 test 是否开启。

## 1. 安装

建议使用 Python 3.11 或更新版本。从本项目根目录（即包含
`requirements.txt` 的 `project/` 目录）创建并激活独立虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

每次打开新的终端后，都需要在 `project/` 目录重新执行：

```bash
source .venv/bin/activate
```

macOS 上的 XGBoost 还需要 OpenMP 运行库：

```bash
brew install libomp
```

安装后检查当前 `python` 是否确实来自项目虚拟环境，并验证核心依赖：

```bash
which python
python -c "import xgboost, uproot; print(xgboost.__version__, uproot.__version__)"
python -m pip check
```

`which python` 应该指向当前项目的 `.venv/bin/python`。如果它仍指向
Anaconda、pyenv 或系统 Python，说明项目虚拟环境没有正确激活；请重新执行
`source .venv/bin/activate` 后再检查。也可以显式使用虚拟环境解释器，
避免受当前 shell 的 Python 配置影响：

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m scripts.higgsml --help
```

## 2. 先运行核心测试

```bash
python -m pytest -q
```

测试覆盖四动量质量、SFOS、Z₁/Z₂ 选择、selection 全部边界、fixed/sliding Z₂ 下限、逐级 cutflow、data/MC 分离摘要、运行 manifest、特征泄漏、事件划分和 MC 权重。

## 3. 不下载 ROOT 的快速验证

合成模式不会冒充真实数据，只用于确认训练、保存模型和绘图代码能跑通：

```bash
python -m scripts.make_synthetic_demo
```

结果写入 `outputs/`。

## 4. 接入 ATLAS Open Data

把三个 ROOT 文件放到 `data/raw/`。先逐个检查：

```bash
python -m scripts.inspect_root data/raw/higgs.root
python -m scripts.inspect_root data/raw/zz.root
python -m scripts.inspect_root data/raw/data16_periodA.root
```

然后在 `config/demo.yaml` 中：

- 填写真实 TTree 名称；留空时程序选择文件中的第一个 TTree；
- 确认动量单位是 `MeV` 或 `GeV`；
- 根据 [ATLAS 官方 metadata](https://opendata.atlas.cern/docs/data/for_education/13TeV25_metadata) 填写两个 MC 样本的 `channel_numbers`；
- 如需先小规模试跑，可设置 `entry_stop`。
- 在 `selection` 中配置有序轻子 pT、电子/muon η、SFOS、Z₁/Z₂ 和 `m4l` 窗口；Z₂ 下限默认 `fixed`，也可切换为 `sliding`。

`channel_numbers` 留空时程序会主动失败，防止只看文件名猜测物理过程。

## 5. 预处理命令

保留 `config/demo.yaml` 中的 `entry_stop: 5000` 时，可沿用 legacy smoke 预处理：

```bash
python -m scripts.prepare_demo --config config/demo.yaml
```

不传 `--run-dir` 的 legacy smoke 会写入或覆盖 `data/processed/` 和 `outputs/`；
指定 `--output-dir` 时，artifact 会写入或覆盖该目录，处理后 CSV 仍写入或覆盖
`data/processed/`。如需隔离 smoke 输出，也可以显式使用一个不存在的新运行目录：

```bash
python -m scripts.prepare_demo --config config/demo.yaml \
  --run-dir runs/<new-smoke-run-name>
```

已验证的 Task 4A 全量预处理命令是：

```bash
python -m scripts.prepare_demo --config config/demo.yaml --full \
  --run-dir runs/full-baseline-2026-08-10
```

只有 full 模式强制要求 `--run-dir`，且它必须指向一个不存在的新目录；任何显式
`--run-dir` 都不会覆盖已有运行。全量基准只在该目录生成以下六个文件，不改写旧的
`data/processed/` 或 `outputs/`：

```text
runs/full-baseline-2026-08-10/
├── config.yaml
├── processed/
│   ├── mc_events.csv.gz
│   └── data_events.csv.gz
└── artifacts/
    ├── cutflow.json
    ├── data_summary.json
    └── run_manifest.json
```

Task 4A processes and records the full inputs only. It does not retrain XGBoost,
choose a new threshold, score real data, or manually inspect the blinded real-data
mass region.

### 历史 Task 4B/DSID 700600 基准（已被 363490 1.0 取代）

Task 4B 使用且仅使用 Task 4A 的 MC 表，已实际运行：

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
这一背景告警必须显著保留：selected ZZ 总数 `471`（`391 development`、`80 test`），
所以背景指标及 OOF/test 差异有很大的统计不确定性。
五张批准图均只使用 MC；质量图只包含 ZZ，不能显示或验证 Higgs 125 GeV 峰。

Task 4B 未读取或评分真实数据，也不声称在真实数据中观察到 125 GeV Higgs 峰。
该历史阶段收尾测试为 `383 passed`。其 471 个 ZZ 事件和 warning 字段不得再作为
当前 1.0 结论；当前结论见本文开头的 DSID 363490 状态框。

以下输出和数值仍是明确分开的历史 5,000-entry 模型结果，不得解释为 Task 4B 结果。

历史 5,000-entry 模型运行曾生成：

```text
outputs/
├── cutflow.json
├── data_summary.json
├── run_manifest.json
├── feature_distributions.png
├── roc_curve.png
├── score_distribution.png
├── train_test_score_comparison.png
├── score_vs_m4l.png
├── m4l_before_xgb.png
├── m4l_low_score.png
├── m4l_high_score.png
├── metrics.json
├── overfitting_check.json
├── data_with_xgb_score.csv.gz
└── xgboost_demo.json
```

`cutflow.json` 按 `higgs_345060`、`zz_700600` 和 `data16_periodA` 分开记录每一级未加权事件数与效率。MC 另外记录 signed/absolute weighted yield；data 不生成物理加权产额字段。

`data_summary.json` 将 data 的 period、读取/选择计数和 run/event 唯一性与 MC 的 DSID、读取/选择计数、signed/absolute 权重和负权重比例彻底分开。`run_manifest.json` 记录 UTC 时间、软件版本、配置与输入文件 SHA-256、处理上限、随机种子、selection 模式和 Git commit 状态。

Task 4A full-ROOT 基准在 2026-08-10 验收时为 `194 passed`；本次发布安全加固后
完整合成测试为 `198 passed`。Task 4A 已在
`runs/full-baseline-2026-08-10` 全量读取 Higgs `419943`、ZZ `11260` 和 data
`29275` 条记录，并分别选择 `350928`、`471` 和 `226` 条；data 的重复
run/event 对为 `0`。该运行的 manifest schema 为 `1.1`，配置快照、三个输入
SHA-256 和 MC 归一化字段均已验证。旧 `data/processed/` 与 `outputs/` 的路径、
大小和修改时间在运行前后完全一致。`outputs/` 中的模型、阈值、分数、指标和图片
仍属于历史 5,000-entry 模型运行。

## 关键分析约束

- `m4l` 不进入模型 `FEATURES`；它用于预处理阶段宽范围的四轻子质量 selection，
  并在模型固定后用于盲化控制、最终绘图和质量塑形检查。Task 4A 没有人工检查
  真实数据的盲化质量区。
- `channelNumber`、事件编号、数据来源字段和所有权重字段不进入模型。
- 有符号权重保留用于物理产额；训练副本使用 `|w|` 并归一化，因为 XGBoost 不接受负的 `sample_weight`。
- 模型只在训练集拟合，分数阈值只在验证集选择，测试集仅用于一次最终评价。
- `overfitting_check.json` 报告三个集合的 AUC、train-test AUC gap，以及信号和背景各自的加权 KS 距离。
- 真实数据的标签固定为 `-1`，不参与监督训练。
- 一个 data period 统计量很少时看不到明显的 125 GeV 峰是正常现象。
