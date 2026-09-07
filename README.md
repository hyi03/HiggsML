# HiggsML

本文介绍 Neural 项目的 MC 数据预处理、训练和测试操作。网络原理见 [Neural 文档](neural/README.md)，XGBoost 的使用方法见 [XGBoost 文档](xgboost/README.md)。

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

## 2. DEBUG 模式

用于诊断，训练和测试均须显式传入 `--debug`，不会根据协议文件名自动启用。以下预处理协议关闭 `m4l` 质量窗；DEBUG 训练无论候选是否 eligible 都生成模型，DEBUG 测试忽略 eligible 判定。训练和测试结果均标记为 `debug_diagnostic`，保留资格失败原因，不代表正式测试通过，也不得用于根据 test 结果调参。

### 2.1 higgsml-preprocess：预处理

```powershell
higgsml-preprocess `
  --dataset atlas2020_4lep `
  --protocol config/preprocess_protocol_debug.yaml `
  --run-config config/preprocess_run.example.yaml `
  --run-dir runs/atlas2020_4lep/preprocess-debug-001
```

### 2.2 higgsml-train：训练

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

### 2.3 higgsml-test：测试

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

## 3. 正式模式

按预处理、训练、测试的顺序执行，使用正式 v2 协议，不添加 `--debug`。

### 3.1 higgsml-preprocess：预处理

```powershell
higgsml-preprocess `
  --dataset atlas2020_4lep `
  --protocol config/preprocess_protocol_v2.yaml `
  --run-config config/preprocess_run.example.yaml `
  --run-dir runs/atlas2020_4lep/preprocess-001
```

输出包含独立的 development 和 test 分区，供后续命令使用。

### 3.2 higgsml-train：训练

```powershell
higgsml-train `
  --dataset atlas2020_4lep `
  --input-run runs/atlas2020_4lep/preprocess-001 `
  --protocol config/adversarial_mlp_protocol_normal_v2.yaml `
  --run-dir runs/atlas2020_4lep/development-001
```

训练仅读取 development 分区。若结果为 `no_eligible_candidate`，流程到此结束，不得开启 test。

### 3.3 higgsml-test：测试

仅在 development run 为 eligible、数据集一致且已获得明确开测授权后执行：

```powershell
higgsml-test `
  --dataset atlas2020_4lep `
  --train-run runs/atlas2020_4lep/development-001 `
  --run-dir runs/atlas2020_4lep/test-001
```

可追加 `--authorization-reference <公开审计引用>` 启用持久化一次性 claim；省略时允许使用新输出目录重复评价，但仍须遵守开测授权边界。测试使用冻结模型、scaler 和阈值，不重新训练或调参。

## 4. 验证与参考

运行测试套件：

```powershell
python -m pytest -q
```

- [v2 运行手册](neural/docs/dataset-v2-runbook.md)
- [Neural 实现说明](neural/README.md)
- [数据下载验证记录](neural/docs/init-data-verification.md)
- [v2 实际验证记录](neural/docs/dataset-v2-verification.md)

Windows 或合成测试不能替代原生锁定 ARM64 与实际绑定数据的权威验证。项目仅用于 educational/technical demo。
