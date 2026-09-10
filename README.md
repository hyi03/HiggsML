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

## 2. H4l 质量条件研究流程

项目方案对应的研究软件入口是 `higgsml-research`。它是独立的 MC-only 研究流程，
不改变历史 `higgsml-preprocess`、`higgsml-train` 和 `higgsml-test` 的固定 15 维分类器、
资格门槛或 test-opening 规则。只有绑定版本化研究协议的新模型，才允许把 `m4l` 作为共同质量条件输入；
不得把这一例外用于历史模型或真实数据。

以下命令均从仓库的 `neural/` 目录执行。`runs/<名称>` 只是命名示例；成功、科学终态或失败的
run 均不可覆盖，重跑时必须更换目录名。

两个跨平台 Python 脚本覆盖完整流程：`scripts/h4l_prepare.py` 自动生成绑定输入和 P0/T1 验证，
执行 audit、prepare 和前置 G1，并准备下一阶段命令；`scripts/h4l_run.py` 执行单个 seed 的
A、B、C、D 全组合研究。整个流程不打开 assessment 或历史 held-out test。

### 2.1 安装研究依赖

从仓库根目录开始，进入 `neural/` 并确认研究 CLI 可用：

```bash
cd neural
conda activate pytorch
python -m pip install -r requirements-research.txt
python -m pip install --no-deps -e .
python -m pip check
higgsml-research --help
```

### 2.2 完成准备

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

| 阶段 | 子命令 | 主要输入 | 输出目录 | 作用 |
|---:|---|---|---|---|
| 1 | `audit` | ROOT manifest、研究协议 | `<run-root>/audit` | 核对受控 MC 来源、协议绑定和角色隔离，并按角色与类别检查 signed yield、有效统计量及权重抵消率；只生成 G0/P0 审计证据，不读取 assessment。 |
| 2 | `prepare` | ROOT manifest、profile、P0 验证 | `<run-root>/prepare` | 重建并筛选四轻子事件，计算冻结研究变量和物理权重，按物理事件组划分 train、validation、calibration、template、assessment 五种角色；保存后续阶段共用且身份绑定的 prepared run，但不打开 assessment 内容。 |
| 3 | `train M0c` | prepared run、候选 `M0c`、seed 42 | `<run-root>/g1/train/m0c` | 训练 mass-only 空集基线：只输入 `m4l`（1 维）；`c` 表示它是产生分类分数的质量模型，用于区别无分类器、仅使用质量模板的 M0。 |
| 4 | `train M2` | prepared run、候选 `M2`、seed 42 | `<run-root>/g1/train/m2` | 训练 decay7 + `m4l` 普通 MLP：输入 `mZ1`、`mZ2`、5 个衰变角和 `m4l`（共 8 维），其冻结分数经 physical CDF 校准后形成 M4。 |
| 5 | `train M3` | prepared run、候选 `M3`、seed 42 | `<run-root>/g1/train/m3` | 训练 engineered19 + `m4l` 普通 MLP：输入 19 个工程化运动学变量和 `m4l`（共 20 维），其冻结分数经 physical CDF 校准后形成 M5。 |
| 6 | `calibrate M0c raw` | prepared run、M0c 模型 | `<run-root>/g1/calibrate/m0c-raw` | 保留 M0c 的原始网络分数，不做 CDF 变换；仅使用独立 calibration 角色拟合冻结分类阈值，作为同流程的纯质量空集参照。 |
| 7 | `calibrate M2 raw` | prepared run、M2 模型 | `<run-root>/g1/calibrate/m2-raw` | 保留 M2 的原始网络分数，并在 calibration 角色上拟合冻结阈值；用于观察未经质量条件校准的 decay7 基线。 |
| 8 | `calibrate M2 physical` | prepared run、M2 模型 | `<run-root>/g1/calibrate/m4-physical` | 用 calibration 背景及 signed physical weight 拟合质量条件 CDF，将冻结的 M2 分数变换并重新拟合阈值，派生出 M4；不重新训练网络。 |
| 9 | `calibrate M3 raw` | prepared run、M3 模型 | `<run-root>/g1/calibrate/m3-raw` | 保留 M3 的原始网络分数，并在 calibration 角色上拟合冻结阈值；用于观察未经质量条件校准的 engineered19 表示。 |
| 10 | `calibrate M3 physical` | prepared run、M3 模型 | `<run-root>/g1/calibrate/m5-physical` | 用 calibration 背景及 signed physical weight 拟合质量条件 CDF，将冻结的 M3 分数变换并重新拟合阈值，派生出 M5；不重新训练网络。 |
| 11 | `templates` | prepared run、5 个 calibration run、T1 验证 | `<run-root>/g1/templates` | 将 M0、M0c、M2、M3、M4、M5 放在同一质量网格上构建分类模板，必要时对所有候选共同合并统计不足的质量箱；G1 同时检查校准状态、非负产额、有效模板统计、协方差结构和 T1 `shapesys` 契约。只有 `g1.json` 为 `passed` 才给出下一批次命令。 |

如只需预览前置命令，在上述命令末尾追加 `--plan-only`；计划模式不创建 run，也不显示动态进度条。
在 CI 或需要保存纯文本日志时，可关闭进度条，命令执行内容不变：

```bash
python scripts/h4l_prepare.py --dataset-receipt ../data/raw/atlas2020_4lep/dataset_receipt.json --run-root runs/h4l-feature-combinations-prerequisites-001 --no-progress
```

### 2.3 执行完整批次

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

| 阶段 | 数量 | 子命令与对象 | 输出目录 | 作用 |
|---:|---:|---|---|---|
| 1 | 1 | `train M0c baseline` | `<output-root>/train/empty` | 使用当前 seed 重新训练只输入 `m4l` 的 M0c（1 维），作为本批次同流程、同总体的空集基线；执行前校验 prepared run 与前置 G1 gate 的绑定。 |
| 2 | 1 | `calibrate M0c baseline` | `<output-root>/calibrate/empty` | 保留 M0c 原始分数，并只在 calibration 角色上拟合冻结阈值；该结果代表不含 A/B/C/D 工程特征的空集价值。 |
| 3、5、…、31 | 15 | `train groups <组合>` | `<output-root>/train/groups-<组合>` | 分别训练 `A`、`B`、`C`、`D`、`AB`、`AC`、`AD`、`BC`、`BD`、`CD`、`ABC`、`ABD`、`ACD`、`BCD`、`ABCD`；每个 M3 子模型只使用指定的 engineered19 特征组，并共同额外输入 `m4l`。 |
| 4、6、…、32 | 15 | `calibrate groups <组合>` | `<output-root>/calibrate/groups-<组合>` | 对紧邻的组合模型保留 raw 分数，并在相同 calibration 角色上独立拟合冻结阈值，使 15 个组合与 M0c 基线采用一致的后处理流程。 |
| 33 | 1 | `templates` | `<output-root>/templates` | 汇总 M0c 和 15 个组合的 calibration run，在所有候选共享的质量网格上构建模板并绑定已验证的 T1 有限模板 MC 统计模型；统计不足时采用共同合箱，不能为单个组合单独优化网格。 |
| 34 | 1 | `infer T1` | `<output-root>/inference` | 在共同 T1 模板模型下对 16 个候选执行 `mu=1` 的 model-self Asimov 推断，得到可比较的预期信号强度区间。 |
| 35 | 1 | `report` | `<output-root>/report` | 汇总同一 seed 的 16 个推断结果，核对组合是否完整，并以 M0c 为空集计算 A/B/C/D 的精确 Shapley 贡献；任一组合缺失或无效时不得用零填补。 |

其中，A 为 4 个轻子的 `pt`/`eta`（8 项），B 为 `mZ1`、`mZ2`、`deltaR_Z1`、
`deltaR_Z2`（4 项），C 为 `pt4l`、`deltaPhi_ZZ`（2 项），D 为 5 个产生与衰变角变量；
四组共 19 项，`m4l` 是所有组合共同的质量条件，不计入 A/B/C/D。

### 2.4 查看和检查结果

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

## 3. DEBUG 诊断模式

本节仅用于既有 debug 诊断流程。正式 `inclusive` 协议拒绝 `--debug`，不能将正式无窗 run 直接转为本节流程。诊断训练和测试均须显式传入 `--debug`，不会根据协议文件名自动启用。以下预处理协议关闭 `m4l` 质量窗；输入有效且训练成功时，DEBUG 训练无论候选是否 eligible 都生成模型，DEBUG 测试忽略 eligible 判定。训练和测试结果均标记为 `debug_diagnostic`，保留资格失败原因，不代表正式测试通过，也不得用于根据 test 结果调参。

### 3.1 higgsml-preprocess：预处理

```bash
higgsml-preprocess \
  --dataset atlas2020_4lep \
  --protocol config/preprocess_protocol_debug.yaml \
  --run-config config/preprocess_run.example.yaml \
  --run-dir runs/atlas2020_4lep/preprocess-debug-001
```

### 3.2 higgsml-train：训练

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

### 3.3 higgsml-test：测试

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

## 4. 验证与参考

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
