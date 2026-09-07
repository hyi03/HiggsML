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

用于诊断，符合开测条件的 DEBUG 训练产物也可执行测试。以下预处理协议关闭 `m4l` 质量窗；训练必须显式传入 `--debug`，该选项会跳过输入 run 的 SHA 和训练协议封存校验。

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

### 2.3 higgsml-test：测试

DEBUG development run 为 eligible、数据集一致且已获得明确开测授权后，可执行：

```powershell
higgsml-test `
  --dataset atlas2020_4lep `
  --train-run runs/atlas2020_4lep/development-debug-001 `
  --run-dir runs/atlas2020_4lep/test-debug-001
```

`higgsml-test` 不需要、也不接受 `--debug` 参数；测试仍执行协议和产物完整性校验，不继承训练阶段跳过校验的行为。若训练结果为 `no_eligible_candidate`，不得开启 test。可选 `--authorization-reference` 的用法与正式模式相同。

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
