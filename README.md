# HiggsML

本文介绍 Neural 项目的 MC 数据预处理、训练和测试操作。网络原理见 [Neural 文档](neural/README.md)，XGBoost 的使用方法见 [XGBoost 文档](xgboost/README.md)。

## 1. 准备代码、数据和环境

以下示例使用 Linux 开发环境，需要 Git、Python 和 Conda。已有仓库副本时，直接进入仓库根目录。

### 1.1 获取代码

```bash
git clone git@github.com:hyi03/HiggsML.git
cd HiggsML
```

### 1.2 下载 MC 数据

在仓库根目录执行，默认下载并校验两套数据，已有且校验通过的文件会跳过：

```bash
python scripts/init_data.py
```

按需选择以下命令，只下载一套数据或强制重新下载：

```bash
python scripts/init_data.py --dataset atlas2020_4lep
python scripts/init_data.py --dataset atlas2025_exactly4lep
python scripts/init_data.py --dataset atlas2020_4lep --force
```

数据保存在 `data/raw/<dataset>/`，不提交到 Git。

下载最多尝试 3 次。同一次运行中，连接中断或响应不完整后会从已下载位置请求续传；服务器忽略 Range 时从头重下。文件大小和 SHA-256 全部匹配后才发布文件，哈希不符会清空临时内容后重试。重试耗尽或退出时清理本次临时文件，不保留跨运行的续传进度；下次运行仍会跳过已校验成功的完整文件。

## 1.3 Linux 安装和初始化 Conda

如果 Linux 尚未安装 Conda，可使用 Miniconda。下面命令根据主机架构下载对应安装程序，
并把 Conda 初始化到 Bash：

```bash
cd ~
case "$(uname -m)" in
  x86_64) CONDA_ARCH=x86_64 ;;
  aarch64|arm64) CONDA_ARCH=aarch64 ;;
  *) echo "Unsupported Linux architecture: $(uname -m)" >&2; exit 2 ;;
esac
curl -fsSLo miniconda.sh "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-${CONDA_ARCH}.sh"
bash miniconda.sh -b -p "$HOME/miniconda3"
rm -f miniconda.sh
"$HOME/miniconda3/bin/conda" init bash
source "$HOME/miniconda3/etc/profile.d/conda.sh"
```

重新打开终端，或再次执行 `source ~/.bashrc`。

### 1.4 创建并激活环境

首次使用 Anaconda 默认频道时，较新的 Conda 可能要求先接受频道服务条款。如果
`conda env create` 报告 `CondaToSNonInteractiveError`，请先阅读并确认接受对应条款，
然后执行：

```bash
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

如果所在组织不允许接受这些条款，应按照报错中链接的 Conda 官方频道文档移除或替换这些频道，
不要继续执行下面的环境创建命令。

```bash
cd neural
conda env create -f environment.yml
conda activate pytorch
python -m pip install --no-deps -e .
python -m pip check
```

`conda env create` 必须无错误结束才表示环境创建成功；ToS 报错发生在创建前，不能视为已完成。
已有 `pytorch` 环境时可通过 `conda env list` 确认，并跳过创建步骤。激活后，终端提示符应显示
`(pytorch)`；`python -m pip check` 应报告 `No broken requirements found.`。后续命令均在
`neural/` 目录、已激活的环境中执行。锁定环境的使用见 [v2 运行手册](neural/docs/sw-dev/dataset-v2-runbook.md)。

### 1.5 运行约定

- 以下以 `atlas2020_4lep` 为例；使用 `atlas2025_exactly4lep` 时，一致替换数据集名称和全部上下游路径。
- 每次输出必须使用 `runs/` 下尚不存在的新目录；成功或失败的目录均不可复用，例如下次改为 `*-002`。
- 仅使用 MC 数据，不读取或处理真实数据。不得根据 test 结果调参或选择数据集。
- 三个命令均支持追加 `--no-progress` 关闭进度显示。

## 2. 正式无质量窗模式（inclusive）

本流程不额外施加 `m4l` 质量窗，保留通过现有 trigger、轻子、SFOS、Z1/Z2 等选择的全部 MC。所有 development 事件参与训练，早停、候选选择和主评价均使用全范围；test 仍独立封存。`m4l` 不进入分类器，固定 15 个输入特征及现有 AUC、KS、效率门槛保持不变。

预处理和训练必须使用配套的 `inclusive` 协议，不添加 `--debug`。文件名描述用途，内部 schema 和精确内容哈希用于兼容性与绑定校验。算法及科学边界详见 [inclusive 协议手册](neural/docs/research/inclusive-protocol.md)。

### 2.1 higgsml-preprocess：无窗预处理

```bash
higgsml-preprocess \
  --dataset atlas2020_4lep \
  --protocol config/preprocess_protocol_inclusive.yaml \
  --run-config config/preprocess_run.example.yaml \
  --run-dir runs/atlas2020_4lep/preprocess-inclusive-001
```

输出包含 `processed/development_events.csv.gz` 和 `processed/test_events.csv.gz`。两张表均为 30 列，保留 `physical_weight`，不预先生成 `train_weight`。cutflow 将 `m4l_analysis_window.enabled` 标记为 `false`，其余物理选择继续执行。

### 2.2 higgsml-train：全范围开发训练

```bash
higgsml-train \
  --dataset atlas2020_4lep \
  --input-run runs/atlas2020_4lep/preprocess-inclusive-001 \
  --protocol config/adversarial_mlp_protocol_inclusive.yaml \
  --run-dir runs/atlas2020_4lep/development-inclusive-001
```

训练仅读取 development 分区，每个拟合折独立确定：

- 背景绝对物理权重的 11 个质量分位数 bin，区间右闭、首尾无界；同一折的所有 λ 候选共用边界。
- 各类绝对物理权重均值，用于归一化优化器权重；scaler 同样只拟合该折的拟合数据。

final fit 使用全部 development 重新确定统计参数。验证和 test 不参与拟合折统计；AUC、ROC、效率和 KS 使用绝对物理权重，预测表以 `metric_weight` 记录。signed 物理权重只用于产额报告。

训练后先检查 `artifacts/qualification.json` 和 `artifacts/manifest.json`：

| 状态 | 含义与后续操作 |
|---|---|
| `eligible` | 已冻结最终模型、scaler 和 OOF 阈值，可在满足开测条件后进入下一步。 |
| `no_eligible_candidate` | 没有候选满足预先固定的资格规则；不生成最终模型，不得开启 test。 |
| `insufficient_statistics` | 分位数边界重复、有效 bin 为空或某类缺少有效权重等，优化开始前停止；保留原因，不生成模型或预测。 |

后两项均为声明的科学终态，命令退出码为 0；不能仅凭退出码判断模型可用于 test，也不能自动放宽规则或改用 `--debug`。

`artifacts/scientific_state.json` 保存各折、final fit 和报告分箱的冻结统计及绑定信息；`artifacts/mass_diagnostics.json` 保存各候选 OOF 的分箱效率、背景占比、局部质量 KS 和有效样本量。不可计算的局部指标为 `null` 并附原因，不改变主资格判定。图表覆盖全部事件，以分箱占比、效率和质量 CDF 展示结果。

### 2.3 higgsml-test：冻结模型测试

仅在 development run 为 `eligible`、数据集一致且已获得明确开测授权后执行：

```bash
higgsml-test \
  --dataset atlas2020_4lep \
  --train-run runs/atlas2020_4lep/development-inclusive-001 \
  --run-dir runs/atlas2020_4lep/test-inclusive-001
```

测试使用冻结模型、scaler、全范围 OOF 阈值和 development 报告分箱，不重新拟合、训练或选择候选。测试分箱诊断保存在 `artifacts/test_metrics.json`，预测保存在 `predictions/test_scores.csv.gz`，结果为 `test_reproduced` 或 `test_nonreproduction`。不得根据结果反馈调参。

可追加 `--authorization-reference <公开审计引用>` 启用持久化一次性 claim；省略时允许使用新输出目录重复评价，但仍须遵守开测授权边界。

## 3. 有窗模式兼容说明

现有有窗正式流程继续保留，使用以下配套协议，不添加 `--debug`：

| 环节 | 协议文件 |
|---|---|
| 预处理 | `config/preprocess_protocol_mass_window.yaml` |
| 训练 | `config/adversarial_mlp_protocol_mass_window.yaml` |

沿用第 2 节命令结构，将两个 `--protocol` 替换为上表文件，并将全部上下游 run 路径一致改为 `preprocess-mass-window-001`、`development-mass-window-001`、`test-mass-window-001`。

此流程保留 `105 ≤ m4l < 160 GeV` 的预处理质量窗、固定 5 GeV 对抗分箱及原权重定义。预处理表仍含 `train_weight`，其类均值使用全部选后样本，包含 test 权重统计的影响；只有新 `inclusive` 流程改为拟合折内归一化。

有窗文件由原 `preprocess_protocol_v2.yaml` 和 `adversarial_mlp_protocol_normal_v2.yaml` 重命名，内容字节、内部 ID 和 SHA-256 不变，旧文件名不保留副本。历史冻结 run 的记录不改写。新无窗训练不能直接使用旧有窗或 debug 预处理产物，必须在新目录重新预处理。

## 4. DEBUG 诊断模式

本节仅用于既有 debug 诊断流程。正式 `inclusive` 协议拒绝 `--debug`，不能将正式无窗 run 直接转为本节流程。诊断训练和测试均须显式传入 `--debug`，不会根据协议文件名自动启用。以下预处理协议关闭 `m4l` 质量窗；输入有效且训练成功时，DEBUG 训练无论候选是否 eligible 都生成模型，DEBUG 测试忽略 eligible 判定。训练和测试结果均标记为 `debug_diagnostic`，保留资格失败原因，不代表正式测试通过，也不得用于根据 test 结果调参。

### 4.1 higgsml-preprocess：预处理

```bash
higgsml-preprocess \
  --dataset atlas2020_4lep \
  --protocol config/preprocess_protocol_debug.yaml \
  --run-config config/preprocess_run.example.yaml \
  --run-dir runs/atlas2020_4lep/preprocess-debug-001
```

### 4.2 higgsml-train：训练

将上一步的输出目录传给 `--input-run`：

```bash
higgsml-train \
  --debug \
  --dataset atlas2020_4lep \
  --input-run runs/atlas2020_4lep/preprocess-debug-001 \
  --protocol config/adversarial_mlp_protocol_debug_v2.yaml \
  --run-dir runs/atlas2020_4lep/development-debug-001
```

`--debug` 跳过输入 run 的 SHA 和训练协议封存校验。若有合格候选，按原规则选择；若没有，则选择 development OOF AUC 最高的候选，AUC 差值在协议的 `auc_tie_atol` 内时优先较小 λ。随后仅使用 development 数据完成 final fit，epoch 仍取所选候选五折 best epoch 的中位数，无论候选是否 eligible 都输出 `model/model.pt` 和 `model/scaler.json`。

### 4.3 higgsml-test：测试

已有模型、scaler 和冻结阈值，且数据集一致时，显式使用 `--debug` 进行诊断评分，无需模型或候选为 eligible：

```bash
higgsml-test \
  --debug \
  --dataset atlas2020_4lep \
  --train-run runs/atlas2020_4lep/development-debug-001 \
  --run-dir runs/atlas2020_4lep/test-debug-001
```

`higgsml-test --debug` 忽略 run/candidate 的 eligible 判定及候选排名复核，跳过预处理 lineage/分区哈希比对和训练协议封存快照校验，并允许任意有限 `m4l`。仍校验 development 产物哈希、协议精确字节、数据集身份、固定 15 项特征、模型/scaler/阈值绑定，以及 test 分区结构和行数。测试阶段不补训模型、不重新选择候选或阈值；省略 `--debug` 时仍执行正式资格检查，拒绝 `debug_diagnostic` run。

旧版本生成的 `no_eligible_candidate` run 没有最终模型和 scaler，追加 `--debug` 也无法直接评分。需使用 `higgsml-train --debug` 在新目录（例如 `development-debug-002`）重新训练，再将该目录传给 `--train-run`，并使用新的测试输出目录。不得修改或覆盖旧 run。

可选 `--authorization-reference` 的用法与正式模式相同：提供公开审计引用时启用一次性 claim；省略时允许重复评价，每次仍须使用新输出目录。

## 5. H4l 质量条件研究流程

项目方案对应的研究软件入口是 `higgsml-research`。它是独立的 MC-only 研究流程，
不改变历史 `higgsml-preprocess`、`higgsml-train` 和 `higgsml-test` 的固定 15 维分类器、
资格门槛或 test-opening 规则。只有绑定版本化研究协议的新模型，才允许把 `m4l` 作为共同质量条件输入；
不得把这一例外用于历史模型或真实数据。

以下命令均从仓库的 `neural/` 目录执行。`runs/<名称>` 只是命名示例；成功、科学终态或失败的
run 均不可覆盖，重跑时必须更换目录名。

### 5.1 脚本自动执行方案

两个跨平台 Python 脚本覆盖完整流程：`scripts/h4l_prepare.py` 自动生成绑定输入和 P0/T1 验证，
执行 audit、prepare 和前置 G1，并准备下一阶段命令；`scripts/h4l_run.py` 执行单个 seed 的
A、B、C、D 全组合研究。整个流程不打开 assessment 或历史 held-out test。

#### 5.1.1 安装研究依赖

从仓库根目录开始，进入 `neural/` 并确认研究 CLI 可用：

```bash
cd neural
conda activate pytorch
python -m pip install -r requirements-research.txt
python -m pip install --no-deps -e .
python -m pip check
higgsml-research --help
```

#### 5.1.2 完成准备

执行下面命令自动检查下载收据、生成并校验 ROOT manifest 和 P0/T1 绑定验证，随后执行
audit、prepare、M0c/M2/M3、校准、共同 templates 和 G1 检查：

```bash
python scripts/h4l_prepare.py --dataset-receipt ../data/raw/atlas2020_4lep/dataset_receipt.json --run-root runs/h4l-feature-combinations-prerequisites-001
```

脚本把三个绑定文件保存在 `<run-root>/inputs/`，成功后打印可直接执行的 `Next batch command`。
正式执行时会在标准错误流显示 `H4l prerequisites` 总进度条，共 11 个阶段：audit、prepare、
3 次训练、5 次校准和 templates。进度条后缀显示当前阶段；只有当前子命令成功结束后才推进，
任一步失败仍保留原始错误信息和退出码。每个子命令运行期间还会每秒输出累计运行秒数，
即使终端无法绘制动态进度条，也能确认进程仍在运行。

如只需预览前置命令，在上述命令末尾追加 `--plan-only`；计划模式不创建 run，也不显示动态进度条。
在 CI 或需要保存纯文本日志时，可关闭进度条，命令执行内容不变：

```bash
python scripts/h4l_prepare.py --dataset-receipt ../data/raw/atlas2020_4lep/dataset_receipt.json --run-root runs/h4l-feature-combinations-prerequisites-001 --no-progress
```

#### 5.1.3 执行完整批次

确认预览中的 prepared run、G1 gate、T1 文件、seed 和新输出目录正确后，直接执行前置脚本打印的
原始 `Next batch command`，不要附加计划参数。该命令调用跨平台的 `scripts/h4l_run.py`。

```bash
python scripts/h4l_run.py --seed 42 --prepared-run runs/h4l-feature-combinations-prerequisites-001/prepare --gate-run runs/h4l-feature-combinations-prerequisites-001/g1/templates --t1-validation runs/h4l-feature-combinations-prerequisites-001/inputs/t1-validation.json --output-root runs/h4l-feature-combinations-prerequisites-001/batch/seed42
```

研究 CLI 会校验协议、数据总体和前置 gate 绑定。脚本接受 seed 42–46，每个 seed 和每次重跑均须
使用新的 `OUTPUT_ROOT`，且该目录必须位于 `neural/runs/` 下。

正式执行时会在标准错误流显示 `H4l batch seed <seed>` 总进度条，共 35 个阶段：16 次训练、
16 次校准、templates、infer 和 report。进度条后缀显示当前基线、特征组合或收尾阶段；只有子命令
成功结束后才推进。每个子命令运行期间还会每秒输出累计运行秒数，即使终端无法绘制动态进度条，
也能确认进程仍在运行。`--plan-only` 不显示动态进度条；在 CI 或需要纯文本日志时，可在批次命令
末尾追加 `--no-progress`，执行内容和科学门禁不变。

#### 5.1.4 查看和检查结果

批次共执行 16 次训练：15 个非空组合和 1 个 M0c 空集基线。批次输出固定在
`<run-root>/batch/seed42/`。`h4l_run.py` 会在结束前读取 `report/report.json`，确认完整组合比较的
状态、数量和 seed；检查通过后打印 `report/report.md` 的实际路径，无需再执行额外检查命令。

查看 Markdown 报告：

```bash
python -c "from pathlib import Path; print(Path('runs/h4l-feature-combinations-prerequisites-001/batch/seed42/report/report.md').read_text(encoding='utf-8'))"
```

检查 JSON 中的完整组合比较状态，并输出该项结果：

```bash
python -c "import json; from pathlib import Path; r=json.loads(Path('runs/h4l-feature-combinations-prerequisites-001/batch/seed42/report/report.json').read_text(encoding='utf-8')); c=r.get('feature_combination_comparisons', []); assert len(c)==1 and c[0].get('status')=='valid' and c[0].get('seed')==42, c; print(json.dumps(c[0], indent=2, ensure_ascii=False))"
```

只有 16 个同总体、同网格、T1、μ=1 的结果全部有效时，报告才生成有效 Shapley；缺失或失败组合
不会用零值替代。软件命令成功也不等于完成了原生 ARM64 权威验收或独立科学数值验证。

### 5.2 手工执行方案

手工方案用于逐阶段执行完整 H4l 研究流程，适合检查每个中间产物、候选状态和冻结条件。

#### 5.2.1 环境与公共变量

```bash
cd neural
conda activate pytorch
python -m pip install -r requirements-research.txt
python -m pip install --no-deps -e .
higgsml-research --help

DATASET="atlas2020_4lep"
PROTOCOL="config/research_protocol_v1.json"
PROFILE="config/profiles/open_data_2020.yaml"
ROOT_MANIFEST="<受控的-h4l-root-input-v1-manifest.json>"
P0_VALIDATION="<已完成外部审计的-p0-validation.json>"
T1_VALIDATION="<已完成独立验证的-t1-validation.json>"
BACKEND_CONFIG="<固定ME后端与过程定义.json>"
ME_REFERENCE="<独立MELA数值参考.json>"
PREPARE_RUN="runs/h4l-prepare-001"
```

受控 ROOT manifest 必须来自已有下载校验记录并绑定 `mc_only: true`、两个 MC 文件的 SHA256、
大小和 mtime。首先只记录来源元数据，再使用封存 profile 和已完成的 P0 外部审计生成 prepared run：

```bash
higgsml-research audit \
  --dataset "$DATASET" \
  --protocol "$PROTOCOL" \
  --input-manifest "$ROOT_MANIFEST" \
  --run-dir runs/h4l-audit-metadata-001

higgsml-research prepare \
  --dataset "$DATASET" \
  --protocol "$PROTOCOL" \
  --input-manifest "$ROOT_MANIFEST" \
  --profile "$PROFILE" \
  --p0-validation "$P0_VALIDATION" \
  --run-dir "$PREPARE_RUN"
```

只有显式标记的合成输入才能改用下面的 prepare 命令；该路径不构成真实 MC 或 P0 验证：

```bash
SYNTHETIC_EVENTS="<显式标记的合成-events.jsonl>"
higgsml-research prepare \
  --dataset "$DATASET" \
  --protocol "$PROTOCOL" \
  --events "$SYNTHETIC_EVENTS" \
  --run-dir runs/h4l-prepare-synthetic-001
```

#### 5.2.2 最小候选矩阵与 G1

先运行种子 42 的 M0c、M2、M3；其中 M2 的 physical CDF 产生 M4，M3 的 physical CDF 产生 M5。
`raw` 校准仍负责冻结阈值和模型身份。以下五个 calibration run 构成 G1 的最小候选矩阵：

```bash
for candidate in M0c M2 M3; do
  higgsml-research train \
    --dataset "$DATASET" \
    --protocol "$PROTOCOL" \
    --input-run "$PREPARE_RUN" \
    --candidate "$candidate" \
    --seed 42 \
    --run-dir "runs/h4l-${candidate,,}-42"
done

higgsml-research calibrate --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --model-run runs/h4l-m0c-42 --transform raw --run-dir runs/h4l-m0c-raw-42
higgsml-research calibrate --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --model-run runs/h4l-m2-42 --transform raw --run-dir runs/h4l-m2-raw-42
higgsml-research calibrate --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --model-run runs/h4l-m2-42 --transform physical --run-dir runs/h4l-m4-42
higgsml-research calibrate --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --model-run runs/h4l-m3-42 --transform raw --run-dir runs/h4l-m3-raw-42
higgsml-research calibrate --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --model-run runs/h4l-m3-42 --transform physical --run-dir runs/h4l-m5-42

GATE_RUN="runs/h4l-templates-g1-001"
higgsml-research templates \
  --dataset "$DATASET" \
  --protocol "$PROTOCOL" \
  --input-run "$PREPARE_RUN" \
  --calibration-run runs/h4l-m0c-raw-42 \
  --calibration-run runs/h4l-m2-raw-42 \
  --calibration-run runs/h4l-m4-42 \
  --calibration-run runs/h4l-m3-raw-42 \
  --calibration-run runs/h4l-m5-42 \
  --t1-validation "$T1_VALIDATION" \
  --run-dir "$GATE_RUN"
```

继续之前应检查 `$GATE_RUN/g1.json` 的 `status` 确实为 `passed`。不能通过放宽支持域、signed yield、
有效统计量或 T1 门槛来强行通过 G1。

#### 5.2.3 矩阵元 M1/M1c

MELA 在独立 Linux 环境运行。后端配置必须精确记录 backend 的 name/version/configuration SHA256，
以及 signal/background/PDF/approximation；`$ME_REFERENCE` 必须是绑定相同 adapter SHA256 的独立数值参考。

```bash
ME_EXPORT_RUN="runs/h4l-me-export-development-001"
higgsml-research me-export \
  --dataset "$DATASET" \
  --protocol "$PROTOCOL" \
  --input-run "$PREPARE_RUN" \
  --backend-config "$BACKEND_CONFIG" \
  --run-dir "$ME_EXPORT_RUN"
```

在 Linux 的 MELA 环境中执行；不要用任意替代概率公式：

```bash
python scripts/research_mela.py \
  --input runs/h4l-me-export-development-001/me-input.json \
  --adapter /path/to/verified_mela_adapter.py \
  --adapter-sha256 <64位小写SHA256> \
  --output /path/to/me-development-output.json
```

回到 `neural/` 和 `pytorch` 环境后导入并生成 M1/M1c：

```bash
ME_DEVELOPMENT_RESULTS="<Linux产生的-me-development-output.json>"
ME_IMPORT_RUN="runs/h4l-me-import-development-001"
higgsml-research me-import \
  --dataset "$DATASET" \
  --protocol "$PROTOCOL" \
  --input-run "$PREPARE_RUN" \
  --export-run "$ME_EXPORT_RUN" \
  --results "$ME_DEVELOPMENT_RESULTS" \
  --reference "$ME_REFERENCE" \
  --run-dir "$ME_IMPORT_RUN"

higgsml-research calibrate --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --model-run "$ME_IMPORT_RUN" --transform raw --run-dir runs/h4l-m1-raw
higgsml-research calibrate --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --model-run "$ME_IMPORT_RUN" --transform physical --run-dir runs/h4l-m1c
```

#### 5.2.4 完整候选矩阵

G1 通过后，补齐种子 43–46 的基础候选、五个种子的固定 200 轮对照与 M6 λ 扫描，最后运行 L1:42。
下面的 `ALL_CALIBRATION_RUNS` 同时收集最终共同模板所需的全部 calibration run：

```bash
ALL_CALIBRATION_RUNS=(
  runs/h4l-m0c-raw-42 runs/h4l-m2-raw-42 runs/h4l-m4-42
  runs/h4l-m3-raw-42 runs/h4l-m5-42 runs/h4l-m1-raw runs/h4l-m1c
)

for seed in 43 44 45 46; do
  for candidate in M0c M2 M3; do
    candidate_lower=${candidate,,}
    model_run="runs/h4l-${candidate_lower}-${seed}"
    raw_run="runs/h4l-${candidate_lower}-raw-${seed}"
    higgsml-research train --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --candidate "$candidate" --seed "$seed" --gate-run "$GATE_RUN" --run-dir "$model_run"
    higgsml-research calibrate --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --model-run "$model_run" --transform raw --run-dir "$raw_run"
    ALL_CALIBRATION_RUNS+=("$raw_run")
    if [[ "$candidate" == M2 ]]; then
      derived_run="runs/h4l-m4-${seed}"
      higgsml-research calibrate --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --model-run "$model_run" --transform physical --run-dir "$derived_run"
      ALL_CALIBRATION_RUNS+=("$derived_run")
    elif [[ "$candidate" == M3 ]]; then
      physical_run="runs/h4l-m5-${seed}"
      absolute_run="runs/h4l-m5-abs-${seed}"
      higgsml-research calibrate --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --model-run "$model_run" --transform physical --run-dir "$physical_run"
      higgsml-research calibrate --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --model-run "$model_run" --transform absolute --run-dir "$absolute_run"
      ALL_CALIBRATION_RUNS+=("$physical_run" "$absolute_run")
    fi
  done
done

# Seed 42 M5-abs, fixed-200 and M6 lambda scans.
higgsml-research calibrate --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --model-run runs/h4l-m3-42 --transform absolute --run-dir runs/h4l-m5-abs-42
ALL_CALIBRATION_RUNS+=(runs/h4l-m5-abs-42)
for seed in 42 43 44 45 46; do
  model_run="runs/h4l-m3-fixed200-${seed}"
  calibration_run="runs/h4l-m3-fixed200-raw-${seed}"
  higgsml-research train --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --candidate M3-fixed200 --seed "$seed" --gate-run "$GATE_RUN" --run-dir "$model_run"
  higgsml-research calibrate --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --model-run "$model_run" --transform raw --run-dir "$calibration_run"
  ALL_CALIBRATION_RUNS+=("$calibration_run")
  for strength in 0.05 0.1 0.2 0.5; do
    tag=${strength//./p}
    m6_model_run="runs/h4l-m6-${seed}-lambda-${tag}"
    m6_calibration_run="runs/h4l-m6-raw-${seed}-lambda-${tag}"
    higgsml-research train --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --candidate M6 --seed "$seed" --strength "$strength" --gate-run "$GATE_RUN" --run-dir "$m6_model_run"
    higgsml-research calibrate --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --model-run "$m6_model_run" --transform raw --run-dir "$m6_calibration_run"
    ALL_CALIBRATION_RUNS+=("$m6_calibration_run")
  done
done
higgsml-research train --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --candidate L1 --seed 42 --gate-run "$GATE_RUN" --run-dir runs/h4l-l1-42
higgsml-research calibrate --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --model-run runs/h4l-l1-42 --transform raw --run-dir runs/h4l-l1-raw-42
ALL_CALIBRATION_RUNS+=(runs/h4l-l1-raw-42)
```

#### 5.2.5 最终共同模板与冻结

将所有候选放到同一个质量网格中。Bash 数组循环用来为每个路径重复传入
`--calibration-run`：

```bash
FINAL_TEMPLATE_RUN="runs/h4l-templates-final-001"
TEMPLATE_ARGS=(templates --dataset "$DATASET" --protocol "$PROTOCOL"
  --input-run "$PREPARE_RUN" --t1-validation "$T1_VALIDATION" --run-dir "$FINAL_TEMPLATE_RUN")
for run_path in "${ALL_CALIBRATION_RUNS[@]}"; do
  TEMPLATE_ARGS+=(--calibration-run "$run_path")
done
higgsml-research "${TEMPLATE_ARGS[@]}"

FREEZE_RUN="runs/h4l-freeze-001"
higgsml-research freeze \
  --dataset "$DATASET" \
  --protocol "$PROTOCOL" \
  --input-run "$PREPARE_RUN" \
  --template-run "$FINAL_TEMPLATE_RUN" \
  --run-dir "$FREEZE_RUN"
```

如果候选已形成 `blocked_missing_reference`、`insufficient_statistics`、`training_failed` 或 `fit_failed`
等允许的终态，应根据已有不可变失败产物制作完整的外部 candidate ledger，并在 freeze 命令中增加
`--candidate-ledger <candidate-ledger.json>`；不得把未运行项伪报为终态。freeze 同时把压力测试参考固定为 `M3:42`。

#### 5.2.6 冻结后的 assessment ME 补充

冻结前的 ME 导出不会包含 assessment 事件。M1/M1c 进入最终模板时，冻结后必须用同一 prepared population、
同一后端、adapter 和独立参考重新导出并只补充缺失的 assessment 分数：

```bash
ASSESSMENT_ME_EXPORT_RUN="runs/h4l-me-export-assessment-001"
higgsml-research me-export \
  --dataset "$DATASET" \
  --protocol "$PROTOCOL" \
  --input-run "$PREPARE_RUN" \
  --freeze-run "$FREEZE_RUN" \
  --backend-config "$BACKEND_CONFIG" \
  --run-dir "$ASSESSMENT_ME_EXPORT_RUN"
```

```bash
python scripts/research_mela.py \
  --input runs/h4l-me-export-assessment-001/me-input.json \
  --adapter /path/to/verified_mela_adapter.py \
  --adapter-sha256 <与冻结前完全相同的64位小写SHA256> \
  --output /path/to/me-assessment-output.json
```

```bash
ASSESSMENT_ME_RESULTS="<Linux产生的-me-assessment-output.json>"
ASSESSMENT_ME_IMPORT_RUN="runs/h4l-me-import-assessment-001"
higgsml-research me-import \
  --dataset "$DATASET" \
  --protocol "$PROTOCOL" \
  --input-run "$PREPARE_RUN" \
  --export-run "$ASSESSMENT_ME_EXPORT_RUN" \
  --results "$ASSESSMENT_ME_RESULTS" \
  --reference "$ME_REFERENCE" \
  --run-dir "$ASSESSMENT_ME_IMPORT_RUN"
```

#### 5.2.7 推断、T2、压力测试与报告

先运行不打开 assessment 的共同模板 Asimov/T0 和 Asimov+toys/T1。随后 assessment 调用必须绑定 freeze；
由于上一节的冻结后 ME 导出已经建立一次持久 claim，后续命令显式使用 `--repeat-assessment`：

```bash
RESULT_RUNS=()
T0_RUN="runs/h4l-infer-model-self-t0-mu1-001"
higgsml-research infer --dataset "$DATASET" --protocol "$PROTOCOL" --template-run "$FINAL_TEMPLATE_RUN" --layer T0 --mu 1 --run-dir "$T0_RUN"
RESULT_RUNS+=("$T0_RUN")
T1_RUN="runs/h4l-infer-model-self-t1-mu1-001"
higgsml-research infer --dataset "$DATASET" --protocol "$PROTOCOL" --template-run "$FINAL_TEMPLATE_RUN" --layer T1 --mu 1 --toys 500 --seed 42 --run-dir "$T1_RUN"
RESULT_RUNS+=("$T1_RUN")
ASSESSMENT_RUN="runs/h4l-infer-assessment-fixed-t1-mu1-001"
higgsml-research infer --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --template-run "$FINAL_TEMPLATE_RUN" --freeze-run "$FREEZE_RUN" --assessment-me-run "$ASSESSMENT_ME_IMPORT_RUN" --expectation-kind assessment --procedure fixed --layer T1 --mu 1 --toys 500 --seed 42 --repeat-assessment --run-dir "$ASSESSMENT_RUN"
RESULT_RUNS+=("$ASSESSMENT_RUN")
T2_RUN="runs/h4l-infer-assessment-t2-t1-mu1-001"
higgsml-research infer --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --template-run "$FINAL_TEMPLATE_RUN" --freeze-run "$FREEZE_RUN" --assessment-me-run "$ASSESSMENT_ME_IMPORT_RUN" --expectation-kind assessment --procedure t2 --layer T1 --mu 1 --toys 0 --seed 42 --repeat-assessment --run-dir "$T2_RUN"
RESULT_RUNS+=("$T2_RUN")
for kind in normalization mass score correlation; do
  for direction in -1 1; do
    for mode in omitted modeled; do
      direction_tag=plus; [[ "$direction" == -1 ]] && direction_tag=minus
      stress_run="runs/h4l-infer-stress-${kind}-${direction_tag}-${mode}-001"
      higgsml-research infer --dataset "$DATASET" --protocol "$PROTOCOL" --input-run "$PREPARE_RUN" --template-run "$FINAL_TEMPLATE_RUN" --freeze-run "$FREEZE_RUN" --assessment-me-run "$ASSESSMENT_ME_IMPORT_RUN" --expectation-kind assessment --procedure stress --layer T1 --stress-kind "$kind" --stress-direction "$direction" --stress-mode "$mode" --reference-candidate M3:42 --mu 1 --toys 500 --seed 42 --repeat-assessment --run-dir "$stress_run"
      RESULT_RUNS+=("$stress_run")
    done
  done
done
REPORT_RUN="runs/h4l-report-001"
REPORT_ARGS=(report --dataset "$DATASET" --protocol "$PROTOCOL" --run-dir "$REPORT_RUN")
for run_path in "${RESULT_RUNS[@]}"; do REPORT_ARGS+=(--result-run "$run_path"); done
higgsml-research "${REPORT_ARGS[@]}"
```

如未运行 M1/M1c，并已通过 candidate ledger 将它们记为允许的终态，则省略 ME 两节、从
`ALL_CALIBRATION_RUNS` 中移除 `runs/h4l-m1-raw` / `runs/h4l-m1c`，并省略所有
`--assessment-me-run` 参数。其他候选若形成允许的终态，也不得把不存在的 calibration run 加入最终模板。
assessment 首次打开若不是由冻结后 `me-export` 触发，则首次 infer 不加
`--repeat-assessment`；只有相同冻结分析的后续调用才增加该参数。每个 μ、seed、procedure、压力方向和
重复实验仍须使用新的 run 目录，不能复用上面的 `-001`。

#### 5.2.8 验证与解释边界

```bash
python -m pytest tests/research -q
python -m pip check
python -m pytest -q
python -m build --wheel --no-isolation
```

冻结后 assessment 只能使用已冻结的模型、CDF、阈值、共同质量网格和 `M3:42` 压力测试参考。
内部异常会保留可报告的失败 manifest，并以退出码 70 结束。任何阶段失败后都应检查该 run 的
`manifest.json` / `failure.json`，修正根因后改用新目录，不能覆盖失败产物。

该流程的默认协议明确标记为软件合成验证，不等于真实 MC、MELA 物理参考、signed-MC T1 近似或论文实验已经完成。
真实 MC 先导、独立 MELA 验证、原生 ARM64 权威验收和 R1–R4 实验仍需分别通过各自门槛。
详见 [H4l 项目方案](neural/docs/research/H4l-Research-Project.md)、
[研究运行手册](neural/docs/sw-dev/h4l-research-runbook.md) 和
[开发与验证记录](neural/docs/sw-dev/h4l-research-development.md)。

## 6. 验证与参考

在已激活的 `pytorch` 环境、`neural/` 目录下检查依赖并运行测试套件：

```bash
python -m pip check
python -m pytest -q
```

- [正式无质量窗协议与产物说明](neural/docs/research/inclusive-protocol.md)
- [Artifact schema](neural/docs/sw-dev/artifact-schema.md)
- [有窗兼容与数据集运行手册](neural/docs/sw-dev/dataset-v2-runbook.md)
- [Neural 实现说明](neural/README.md)
- [数据下载验证记录](neural/docs/sw-dev/init-data-verification.md)
- [v2 实际验证记录](neural/docs/sw-dev/dataset-v2-verification.md)

Linux 或合成测试不能替代原生锁定 ARM64 与实际绑定数据的权威验证。项目仅用于 educational/technical demo。
