# Codex 项目交接说明

## 当前授权工作（2026-09-01）

用户已批准
`docs/superpowers/specs/2026-09-01-xgboost-refactor-design.md`，并授权按 FR-001 与
Sprint M1-01 至 M1-06 自动执行 XGBoost 科学行为等价重构。该工作固定采用现有
Base14 + Angular5 共 19 项特征，只重构架构、CLI、protocol、artifact 和生命周期。

此授权不改变下述冻结科学结论：不得新增训练候选、调参、放宽 AUC/KS/效率门槛、
复用或覆盖冻结 run、执行真实规模训练、开启现有 held-out test 或访问真实数据。
旧路线图中的“下一阶段为去相关研究”仍是未来科学研究方向，不优先于本次已经单独
批准、且不产生新科学结论的工程重构。

## 当前冻结状态（2026-08-11）

### Full14 封存决定（2026-08-23）

Full14 XGBoost 已封存为失败的历史参考；不是可部署模型，也不是未来真实数据候选。
停止 Full14 + OOF 质量依赖阈值研究，不得继续用阈值变换、校准、追加重加权或调参
补救现有模型。现有 Full14 及 Full14 重加权 run、模型、manifest 和预测只保留作
不可修改的历史比较；不得打开 held-out test，不得读取 periodA。

下一阶段必须另行预先设计原生质量去相关训练，使用新配置和新 run path，并继续要求
AUC >= 0.80、三个工作点 KS <= 0.10。未来若要用相同 14 个输入变量配合全新的
去相关目标，必须重新立项和批准，不能视为当前 Full14 的延续。

MC-only 方法学 1.0 已完成。DSID 363490 全链与质量塑形消融均已运行并冻结；最终
消融结论为 `no_eligible_profile`。不要修改或复用
`runs/full-baseline-363490-2026-08-11-r2`、
`runs/full-training-363490-2026-08-11-r2` 或
`runs/mass-ablation-363490-2026-08-11`。下一阶段必须新建设计和新 run path，优先
研究 decorrelation-aware training；不得放宽既定 AUC/KS 门槛或开启真实数据。

当前下一阶段是质量去相关训练研究；不得事后放宽 AUC/KS 门槛或打开真实数据。

## 适用范围

本文件适用于整个 `higgs-xgboost-demo/` 目录。新设备或新 Codex 会话开始工作时，应按顺序阅读：

1. `AGENTS.md`：本文件，项目约束和接手规则；
2. `README.md`：用户运行入口；
3. `docs/project/overview.md`：当前项目、流程、结果和限制；
4. `docs/roadmap/next-stage.md`：下一阶段路线图。

详细数据与物理标准见 `docs/physics/data-description.md` 和
`docs/physics/selection-standard.md`；导师汇报材料见
`docs/briefings/progress-briefing.md`；全部文档导航见 `docs/README.md`。

在另一台设备上，应把 `higgs-xgboost-demo` 文件夹本身作为 Codex 工作区打开。首次对话可以直接说：

> 请先阅读 AGENTS.md、README.md、docs/project/overview.md 和
> docs/roadmap/next-stage.md，检查数据与测试基线，然后从推荐的下一阶段任务继续；不要重新设计已经完成的 Demo。

## 项目目标

这是一个 \(H\rightarrow ZZ^*\rightarrow4\ell\) XGBoost 端到端技术 Demo：

- Higgs MC 是信号，标签 `1`；
- 连续 \(ZZ^*\) MC 是背景，标签 `0`；
- 真实数据标签固定为 `-1`，绝不参与监督训练；
- 模型只在 train 拟合；
- 分类阈值只在 validation 选择；
- test 只用于最终评价；
- \(m_{4\ell}\) 禁止作为模型特征；它用于预处理阶段宽范围的四轻子质量 selection，
  并在模型固定后用于盲化控制和质量分布检查。

不要把当前 Demo 输出描述为 Higgs 发现、测量或正式 ATLAS 结果。

## 当前完成状态

截至 2026-08-10，以下历史 5,000-entry 模型流程已经实际运行：

1. ROOT 检查；
2. 数据预处理；
3. 300 轮 XGBoost 训练；
4. train/validation/test AUC；
5. 加权 KS 过拟合检查；
6. validation 阈值扫描；
7. 固定模型对真实数据打分；
8. 高分和低分 \(m_{4\ell}\) 绘图；
9. 完整 pytest。

历史 5,000-entry 模型参考基准（不是 Task 4A 的新训练结果）：

| 项目 | 当前值 |
|---|---:|
| Higgs MC 处理后事件 | 4,884 |
| ZZ MC 处理后事件 | 4,685 |
| Data 处理后事件 | 1,112 |
| Train / Validation / Test | 5,752 / 1,919 / 1,898 |
| Train / Validation / Test weighted AUC | 0.9936 / 0.9741 / 0.9813 |
| Validation 选择阈值 | 0.93 |
| Signal / Background KS | 0.0867 / 0.0319 |
| 过拟合报警 | False |
| Task 4A 冻结验收测试 | 194 passed（2026-08-10） |
| Task 4B 前完整合成源码测试 | 382 passed |
| Task 8 文档收尾后完整测试 | 383 passed |

浮点指标在不同操作系统或依赖版本下允许有小幅差异。事件数在输入文件、配置和代码完全一致时应一致。

## 科学与实现约束

修改代码时必须保持：

- `src/features.py::FEATURES` 不得加入 `m4l`、事件标识、样本标识或权重字段；
- signed `physical_weight` 用于物理产额；
- XGBoost 的 `train_weight` 使用归一化的 `abs(physical_weight)`，因为 XGBoost 不接受负 sample weight；
- 不得用 test 选择阈值、调超参数或决定模型；
- 不得用真实数据标签训练；真实数据实际上没有信号/背景 truth；
- channel number 必须由 ROOT 内容和可信 metadata 核对，不能凭文件名猜；
- 图中 `score >= threshold` 只表示 signal-like，不表示事件一定来自 Higgs；
- 对任何“完成、通过、无过拟合”结论，先运行相应验证命令。

## Task 4A 全量预处理基准

已验证命令与冻结路径：

```bash
.venv/bin/python -m scripts.prepare_demo --config config/demo.yaml --full \
  --run-dir runs/full-baseline-2026-08-10
```

| 样本 | 完整读取数 | selection 后事件数 |
|---|---:|---:|
| Higgs MC | 419943 | 350928 |
| ZZ MC | 11260 | 471 |
| data16_periodA | 29275 | 226 |

合并 MC selection 数为 `351399`，data 重复 run/event 对为 `0`。运行目录只包含配置
快照、两份 gzip CSV 和三份 aggregate JSON；manifest schema 为 `1.1`。配置快照哈希、
三个 ROOT 输入 SHA-256、full 读取策略、输出路径和 MC 归一化字段已验证。运行前后
`data/raw/`、`data/processed/`、`outputs/` 全部文件的路径、字节大小和修改时间一致。

Task 4A processes and records the full inputs only. It does not retrain XGBoost,
choose a new threshold, score real data, or manually inspect the blinded real-data
mass region.

Task 4A aggregate preprocessing baseline 本身不是模型、新阈值、新评分或新物理结果；
其 MC 表随后作为下述 Task 4B 的冻结输入。

## 历史 Task 4B/DSID 700600 基准（已被 363490 1.0 取代）

已实际运行：

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
差异有很大的统计不确定性；这一背景告警不得通过查看真实数据后的重调来消除。
五张批准图均只使用 MC；质量图只包含 ZZ，不能显示或验证 Higgs 125 GeV 峰。

Task 4B 未读取或评分真实数据，也不声称在真实数据中观察到 125 GeV Higgs 峰。
该历史阶段收尾测试为 `383 passed`。其 471 个 ZZ 事件与旧 warning 不得作为当前
结论；当前冻结结论见本文开头。

## 已知限制

新 Codex 不应把以下项目误认为已经实现：

1. Task 4A 已全量运行 selection 和逐级、分样本 cutflow；现有 `data/processed/` 与
   `outputs/` 仍是未改写的历史 5,000-entry 模型基准；
2. 当前尚未加入 trigger、identification、isolation 或 impact-parameter 选择；
3. `entry_stop: 5000` 仍描述默认 smoke/历史模型读取；Task 4A 用 `--full` 覆盖为全量读取；
4. Task 4B 已完成 MC-only 训练与审计，但仅有 471 条 selected ZZ，背景诊断统计不确定性很大；
5. 只使用 `data16_periodA`；
6. 当前 \(Z_A\) 不是可用于物理结论的正式显著性；
7. 没有系统误差、控制区、sideband 或质量谱拟合；
8. Task 4A 的新 summary/manifest 位于独立 run 目录；现有
   `outputs/data_summary.json` 仍是历史 artifact。

下一项推荐开发任务是扩充 data periods，并另行设计冻结 Task 4B 模型的盲化数据应用；
不得在查看真实数据后重新调整 Task 4B。

## 跨设备数据注意事项

`.gitignore` 排除了：

- `.venv/`
- `data/raw/*`
- `data/processed/*`
- `outputs/*`
- `runs/*`

因此通过 Git 克隆时，只会得到代码、配置和文档，不会得到 ROOT、处理后 CSV、模型和图片。
Task 4A 的 full-run 配置快照、处理后表格和 aggregate JSON 也不会通过 Git 传到新设备；
`runs/.gitkeep` 只保留目录形状，不包含任何运行 artifact。

三个 ROOT 文件应手动复制到：

```text
data/raw/higgs.root
data/raw/zz.root
data/raw/data16_periodA.root
```

参考文件大小和 SHA-256：

| 文件 | 字节 | SHA-256 |
|---|---:|---|
| `higgs.root` | 182,051,943 | `5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0` |
| `zz.root` | 5,407,367 | `3d7588b897fc50a2342ef1d7b10f8c1b34f035456b2af215f62ad92525422789` |
| `data16_periodA.root` | 15,023,271 | `adc3236398d1b6175438c9b5f77f540f3e1a377d628899156030b0bd3e0042cb` |

检查：

```bash
shasum -a 256 data/raw/higgs.root data/raw/zz.root data/raw/data16_periodA.root
```

Linux 没有 `shasum` 时可使用：

```bash
sha256sum data/raw/higgs.root data/raw/zz.root data/raw/data16_periodA.root
```

如果整目录手动复制，仍应在新设备重建 `.venv`，不要复制或复用旧设备的虚拟环境。

## 新设备恢复步骤

从项目根目录运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

macOS 的 XGBoost 需要 OpenMP：

```bash
brew install libomp
```

然后验证：

```bash
python -c "import xgboost, uproot; print(xgboost.__version__, uproot.__version__)"
python -m pytest -q
```

如果 ROOT 文件已复制但 Task 4A 基准不存在，可运行：

```bash
python -m scripts.inspect_root data/raw/higgs.root
python -m scripts.inspect_root data/raw/zz.root
python -m scripts.inspect_root data/raw/data16_periodA.root
python -m scripts.prepare_demo --config config/demo.yaml --full \
  --run-dir runs/<new-full-run-name>
```

Task 4A 成功 aggregate 基准：

```text
prepared higgs_345060: 419943 read, 350928 selected
prepared zz_700600: 11260 read, 471 selected
prepared data16_periodA: 29275 read, 226 selected
prepared 351399 MC events and 226 data events
194 passed
```

该命令不运行 `train_demo` 或 `evaluate_data`。Task 4B 训练使用独立的 MC-only 命令；
真实数据评分仍必须作为后续独立、明确授权且遵守盲化方案的工作。

## 参考环境

当前已验证环境，不是强制锁定版本：

```text
macOS 26.1, arm64
Python 3.12.13
libomp 22.1.8
awkward 2.12.0
matplotlib 3.11.1
mplhep 1.3.2
numpy 2.5.1
pandas 3.0.5
PyYAML 6.0.3
scikit-learn 1.9.0
tqdm 4.70.0
uproot 5.7.5
vector 1.8.1
xgboost 3.3.0
```

## Codex 接手检查清单

新 Codex 开始修改前：

1. 确认当前工作目录是项目根目录；
2. 阅读本文件、`README.md`、`docs/project/overview.md` 和 `docs/roadmap/next-stage.md`；
3. 运行 `git status --short`，不要覆盖用户的未提交修改；
4. 检查 ROOT 是否存在，不存在时不要假装可以重建 outputs；
5. 运行 `python -m pytest -q` 建立基线；
6. 修改任何功能前先写能失败的测试；
7. 修改后运行聚焦测试和完整测试；
8. 如重新训练，明确哪些 outputs 被覆盖，并重新运行 data evaluation；
9. 更新文档中的基准值时，必须来自实际命令输出。

当前项目目录在父仓库中仍显示为未跟踪的 `higgs-xgboost-demo/`。如果通过 Git 交接，应先有意识地建立项目提交历史；不要把 ROOT、`.venv` 或生成 outputs 加入普通源码提交。
