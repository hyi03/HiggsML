# HiggsML

本文介绍 Neural 项目的 MC 数据预处理、训练和测试操作。主流程使用正式无质量窗 `inclusive` 协议：无窗保留、全范围训练与评价。网络原理见 [Neural 文档](neural/README.md)，XGBoost 的使用方法见 [XGBoost 文档](xgboost/README.md)。

## 1. 准备代码、数据和环境

以下示例使用 PowerShell，需要 Git、Python 和 Conda。已有仓库副本时，直接进入仓库根目录。

### 1.1 获取代码

```powershell
git clone git@github.com:hyi03/HiggsML.git
cd HiggsML
```

### 1.2 下载 MC 数据

在仓库根目录执行，默认下载并校验两套数据，已有且校验通过的文件会跳过：

```powershell
python scripts/init_data.py
```

按需选择以下命令，只下载一套数据或强制重新下载：

```powershell
python scripts/init_data.py --dataset atlas2020_4lep
python scripts/init_data.py --dataset atlas2025_exactly4lep
python scripts/init_data.py --dataset atlas2020_4lep --force
```

数据保存在 `data/raw/<dataset>/`，不提交到 Git。

下载最多尝试 3 次。同一次运行中，连接中断或响应不完整后会从已下载位置请求续传；服务器忽略 Range 时从头重下。文件大小和 SHA-256 全部匹配后才发布文件，哈希不符会清空临时内容后重试。重试耗尽或退出时清理本次临时文件，不保留跨运行的续传进度；下次运行仍会跳过已校验成功的完整文件。

### 1.3 创建并激活环境

```powershell
cd neural
conda env create --file environment.yml
conda activate pytorch
python -m pip install --no-deps -e .
python -m pip check
```

已有 `pytorch` 环境时跳过创建步骤。后续命令均在 `neural/` 目录、已激活的环境中执行。锁定环境的使用见 [v2 运行手册](neural/docs/dataset-v2-runbook.md)。

### 1.4 运行约定

- 以下以 `atlas2020_4lep` 为例；使用 `atlas2025_exactly4lep` 时，一致替换数据集名称和全部上下游路径。
- 每次输出必须使用 `runs/` 下尚不存在的新目录；成功或失败的目录均不可复用，例如下次改为 `*-002`。
- 仅使用 MC 数据，不读取或处理真实数据。不得根据 test 结果调参或选择数据集。
- 三个命令均支持追加 `--no-progress` 关闭进度显示。

## 2. 正式无质量窗模式（inclusive）

本流程不额外施加 `m4l` 质量窗，保留通过现有 trigger、轻子、SFOS、Z1/Z2 等选择的全部 MC。所有 development 事件参与训练，早停、候选选择和主评价均使用全范围；test 仍独立封存。`m4l` 不进入分类器，固定 15 个输入特征及现有 AUC、KS、效率门槛保持不变。

预处理和训练必须使用配套的 `inclusive` 协议，不添加 `--debug`。文件名描述用途，内部 schema 和精确内容哈希用于兼容性与绑定校验。算法及科学边界详见 [inclusive 协议手册](neural/docs/inclusive-protocol.md)。

### 2.1 higgsml-preprocess：无窗预处理

```powershell
higgsml-preprocess `
  --dataset atlas2020_4lep `
  --protocol config/preprocess_protocol_inclusive.yaml `
  --run-config config/preprocess_run.example.yaml `
  --run-dir runs/atlas2020_4lep/preprocess-inclusive-001
```

输出包含 `processed/development_events.csv.gz` 和 `processed/test_events.csv.gz`。两张表均为 30 列，保留 `physical_weight`，不预先生成 `train_weight`。cutflow 将 `m4l_analysis_window.enabled` 标记为 `false`，其余物理选择继续执行。

### 2.2 higgsml-train：全范围开发训练

```powershell
higgsml-train `
  --dataset atlas2020_4lep `
  --input-run runs/atlas2020_4lep/preprocess-inclusive-001 `
  --protocol config/adversarial_mlp_protocol_inclusive.yaml `
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

```powershell
higgsml-test `
  --dataset atlas2020_4lep `
  --train-run runs/atlas2020_4lep/development-inclusive-001 `
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

```powershell
higgsml-preprocess `
  --dataset atlas2020_4lep `
  --protocol config/preprocess_protocol_debug.yaml `
  --run-config config/preprocess_run.example.yaml `
  --run-dir runs/atlas2020_4lep/preprocess-debug-001
```

### 4.2 higgsml-train：训练

将上一步的输出目录传给 `--input-run`：

```powershell
higgsml-train `
  --debug `
  --dataset atlas2020_4lep `
  --input-run runs/atlas2020_4lep/preprocess-debug-001 `
  --protocol config/adversarial_mlp_protocol_debug_v2.yaml `
  --run-dir runs/atlas2020_4lep/development-debug-001
```

`--debug` 跳过输入 run 的 SHA 和训练协议封存校验。若有合格候选，按原规则选择；若没有，则选择 development OOF AUC 最高的候选，AUC 差值在协议的 `auc_tie_atol` 内时优先较小 λ。随后仅使用 development 数据完成 final fit，epoch 仍取所选候选五折 best epoch 的中位数，无论候选是否 eligible 都输出 `model/model.pt` 和 `model/scaler.json`。

### 4.3 higgsml-test：测试

已有模型、scaler 和冻结阈值，且数据集一致时，显式使用 `--debug` 进行诊断评分，无需模型或候选为 eligible：

```powershell
higgsml-test `
  --debug `
  --dataset atlas2020_4lep `
  --train-run runs/atlas2020_4lep/development-debug-001 `
  --run-dir runs/atlas2020_4lep/test-debug-001
```

`higgsml-test --debug` 忽略 run/candidate 的 eligible 判定及候选排名复核，跳过预处理 lineage/分区哈希比对和训练协议封存快照校验，并允许任意有限 `m4l`。仍校验 development 产物哈希、协议精确字节、数据集身份、固定 15 项特征、模型/scaler/阈值绑定，以及 test 分区结构和行数。测试阶段不补训模型、不重新选择候选或阈值；省略 `--debug` 时仍执行正式资格检查，拒绝 `debug_diagnostic` run。

旧版本生成的 `no_eligible_candidate` run 没有最终模型和 scaler，追加 `--debug` 也无法直接评分。需使用 `higgsml-train --debug` 在新目录（例如 `development-debug-002`）重新训练，再将该目录传给 `--train-run`，并使用新的测试输出目录。不得修改或覆盖旧 run。

可选 `--authorization-reference` 的用法与正式模式相同：提供公开审计引用时启用一次性 claim；省略时允许重复评价，每次仍须使用新输出目录。

## 5. 验证与参考

在已激活的 `pytorch` 环境、`neural/` 目录下检查依赖并运行测试套件：

```powershell
python -m pip check
python -m pytest -q
```

- [正式无质量窗协议与产物说明](neural/docs/inclusive-protocol.md)
- [Artifact schema](neural/docs/artifact-schema.md)
- [有窗兼容与数据集运行手册](neural/docs/dataset-v2-runbook.md)
- [Neural 实现说明](neural/README.md)
- [数据下载验证记录](neural/docs/init-data-verification.md)
- [v2 实际验证记录](neural/docs/dataset-v2-verification.md)

Windows 或合成测试不能替代原生锁定 ARM64 与实际绑定数据的权威验证。项目仅用于 educational/technical demo。
