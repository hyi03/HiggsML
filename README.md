# HiggsML H4l

本仓库只维护 `H -> ZZ* -> 4l` 的 **MC-only 教育与技术研究流程**。当前研究比较不同运动学表示、质量条件化与样本效率对信号强度 `mu` 推断精度的影响，并以绑定协议、不可覆盖产物和冻结后的 assessment 隔离保证流程可审计。

仓库输出不构成 ATLAS/CMS 官方结果、Higgs discovery 或物理测量。软件实现、合成测试、完整 MC 验证、独立矩阵元参考和原生 ARM64 authority 验证是不同证据层级，不能互相替代。

## 当前范围与状态

- 活跃代码只有 `src/higgsml` 下的 H4l 包；旧 legacy15 预处理、旧训练/测试流程和 XGBoost 实现已移除。
- 默认研究对象是受控 `atlas2020_4lep` MC 对，协议终态为 `2e2mu`，质量范围为 105–140 GeV。
- `mass-only`、`decay7`、`engineered19`、`lab-extension`，普通/对抗训练、条件 CDF、共同二维模板、冻结 assessment、T0/T1 推断及样本效率链路均已有软件实现。
- 默认协议的 `protocol_scope` 是 `synthetic_software_defaults_not_physics_validation`；当前没有可直接作为论文结果的冻结完整 MC run。
- MELA 只有导出/导入及可选 adapter 契约，实际后端和独立物理参考仍需验证。

精确证据状态见[当前科研与软件状态](docs/validation/current-status.md)，研究设计见[研究方案](docs/methods/research-project.md)。

## 仓库结构

```text
src/higgsml/       H4l 包：物理重建、建模、推断与样本效率
config/            数据集契约、profiles、协议、schemas 与示例
scripts/           受控下载、主工作流和研究辅助脚本
tests/             单元、工作流与合成科学契约测试
docs/              方法、复现、产物和验证文档
paper/             论文稿件
data/raw/          本地受控 MC 输入（忽略，不提交）
runs/              本地不可变运行产物（忽略，不提交）
```

## 环境与安装

项目要求 Python `>=3.12,<3.13`，仓库约定使用 Conda `pytorch` 环境。Windows 开发环境可直接复用现有环境：

```powershell
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pip install --no-deps -e .
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pip check
```

从环境定义创建时：

```bash
conda env create -f environment.yml
conda activate pytorch
python -m pip install --no-deps -e .
python -m pip check
```

核心推断需要 `pyhf` 等研究扩展依赖：

```bash
python -m pip install -r requirements-research.txt
```

`win.yml` 与 `osx.yml` 分别记录 Windows 和 macOS ARM64 锁定环境。Windows 测试不能替代原生 ARM64 authority 验证；MELA 后端需在独立 Linux/WSL 环境中配置。

安装后统一核心入口为：

```bash
higgsml --help
```

## 获取受控 MC

下载器只执行数据集契约中固定的 HTTPS 请求，并在文件大小与 SHA-256 全部匹配后发布 receipt：

```bash
python scripts/init_data.py --dataset atlas2020_4lep
```

输入写入 `data/raw/<dataset>/`。下载器也认识 `atlas2025_exactly4lep`，但它属于独立 release/collection，不能与 2020 文件混配；当前正式 H4l 协议与工作流仍绑定 `atlas2020_4lep`。任何阶段都不得读取或处理真实数据。

数据契约位于：

- [`config/datasets/atlas2020_4lep.json`](config/datasets/atlas2020_4lep.json)
- [`config/datasets/atlas2025_exactly4lep.json`](config/datasets/atlas2025_exactly4lep.json)

## 推荐主工作流

所有命令从仓库根目录运行。完整规则、门槛与恢复方式以[复现实验手册](docs/reproducibility/runbook.md)为准。

### 1. 准备一次、复用输入

```bash
python scripts/h4l_prepare.py
```

脚本执行 `audit` 和 `prepare`，默认使用：

- receipt：`data/raw/atlas2020_4lep/dataset_receipt.json`
- profile：`config/profiles/open_data_2020.yaml`
- 协议：`config/protocols/h4l_protocol.json`
- 输出根：`runs/h4l-prepare/`

可复用的 prepared artifact 位于 `runs/h4l-prepare/prepare`。它不会继续训练、校准或构建模板。需要先做有限工作量性能诊断时，可使用 `--diagnostic-entries-per-file`；诊断产物不能作为 G1 输入。

全局 prepare 根目录的结构为：

```text
runs/h4l-prepare/
├── inputs/    ROOT manifest、P0/T1 绑定证据
├── audit/     来源审计产物
└── prepare/   events.jsonl 与 prepared manifest
```

`h4l_prepare.py` 不接受 `--run-name`。只有在诊断或需要独立新目录时才传入 `--run-root`；正式全局目录已存在时，脚本会拒绝覆盖。

### 2. 执行 seed 42 的 G1 门

```bash
python scripts/h4l_g1.py --run-name pilot-001
```

G1 从全局 prepared artifact 运行 M0c、M2、M3、五个校准和共同模板。只有 G1 通过后，才允许展开受门控的候选。失败目录仍是不可变证据；修复后必须使用新的 `--run-name` 或 `--output-root`。
`--run-name pilot-001` 的实验输出根目录为 `runs/h4l-train-pilot-001/`。

### 3. 执行完整五种子批次

先审计计划，再正式运行：

```bash
python scripts/h4l_run.py --run-name pilot-001 --plan-only
python scripts/h4l_run.py --run-name pilot-001
```

默认批次执行 seed 42–46 的注册候选、校准、共同模板、T1 `mu=1` inference 与报告。显式 `--seed 42` 仅是单种子诊断，不能支持五种子主比较。

三个脚本均支持 `--help`、`--plan-only` 和 `--no-progress`。它们也提供严格限于所选 `runs/` 子目录的 `--clean`；`--clean` 不能与 `--plan-only` 同时使用，执行前应先用 `--help` 或单独的计划命令核对路径。清理会删除不可恢复的本地运行产物；完成、失败、诊断或已发布的 run 均不得原地覆盖。

## 核心 CLI 阶段

`higgsml` 暴露十个可组合阶段：

```text
audit -> prepare -> [me-export -> me-import] -> train -> calibrate
      -> templates -> freeze -> infer -> report
```

```bash
higgsml train --help
higgsml calibrate --help
higgsml templates --help
higgsml infer --help
```

直接调用阶段时，必须显式绑定 dataset、`config/protocols/h4l_protocol.json`、上游 run 与 `runs/` 下的全新输出目录。编排脚本会自动传入该唯一默认协议；`higgsml` 子命令仍要求显式提供 `--protocol`。`manifest.json` 记录数据集、协议快照、上游 artifact、文件摘要、代码/环境、随机种子和科学终态；模型 JSON 只保存数值张量，不加载可执行 pickle。详细字段见[产物与谱系契约](docs/reproducibility/artifact-schema.md)。

## 样本效率研究

样本效率不是 `higgsml` 的子命令，而由三个独立脚本承载：

```bash
python scripts/h4l_learning_curve.py --help
python scripts/h4l_sample_efficiency_report.py --help
python scripts/h4l_sample_efficiency_controls.py --help
```

正式批次绑定 `config/protocols/sample_efficiency_v1.json`、compact candidate freeze、训练子集、G1 和 T1 证据。协议中的 `null` 是待注册占位，不能直接当作正式研究值。方法与确认边界见[样本效率方法](docs/methods/sample-efficiency.md)。

## 科学与运行约束

- 只处理受控 MC 或显式标记的合成事件，绝不读取、散列、预处理、评分或绘制真实数据。
- `m4l` 只能按版本化 H4l 协议使用；signed `physical_weight` 用于物理产额，优化器权重按协议定义。
- 同一物理事件组必须保持在同一 split/fold；train、validation、calibration、template、assessment 的职责不可混用。
- assessment 只能在协议定义的冻结状态后访问，结果不得回流调整候选、阈值、分箱、映射或协议。
- 数据身份、SHA-256、协议 seal、checkpoint、上游绑定与 lineage 必须保留。
- 软件测试通过只证明对应软件行为；不能据此声称获得 `mu` 精度改善、覆盖可靠性或完整 MC 科学结论。

## 验证

在仓库根目录运行：

```powershell
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m compileall -q src scripts tests
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pytest -q
& 'D:\apps\anaconda3\Scripts\conda.exe' run -n pytorch python -m pip check
```

当前测试数量、警告和未完成的科学验证以[状态页](docs/validation/current-status.md)的日期化记录为准，不在 README 中复制易过期的数字。

## 文档入口

- [文档索引](docs/README.md)
- [研究方案](docs/methods/research-project.md)
- [软件与科学模块结构](docs/methods/architecture.md)
- [复现实验手册](docs/reproducibility/runbook.md)
- [产物与谱系契约](docs/reproducibility/artifact-schema.md)
- [证据与完成边界](docs/validation/evidence-and-completion.md)
- [当前科研与软件状态](docs/validation/current-status.md)
- [论文稿件](paper/manuscript.md)

## License

见 [`LICENSE`](LICENSE)。第三方数据、软件与实验资料仍受其各自许可和使用条款约束。
