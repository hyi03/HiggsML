# HiggsML：H → ZZ* → 4l 的 MC-only 研究流程

本仓库只维护 `H -> ZZ* -> 4l` 的 **MC-only 教育与技术研究流程**。当前论文主线是在分类器移除显式 `m4l` 输入后，研究 A/B/C/D 运动学特征组对信号强度 `mu` 推断精度的贡献、互补性及五种子稳定性，并以绑定协议、不可覆盖产物和冻结后的 assessment 隔离保证流程可审计。

仓库输出不构成 ATLAS/CMS 官方结果、Higgs discovery 或物理测量。软件实现、合成测试、完整 MC 验证和独立矩阵元参考是不同证据层级，不能互相替代。支持的平台与 CPU 架构不具有科研权威等级差异。

## 1. 了解项目范围与证据状态

- 活跃代码只有 `src/higgsml` 下的 H4l 包；旧 legacy15 预处理、旧训练/测试流程和 XGBoost 实现已移除。
- 默认研究对象是受控 `atlas2020_4lep` MC 对，协议终态为 `2e2mu`，质量范围为 105–140 GeV。
- `mass-only`、`decay7`、`engineered19`、`lab-extension`，全部 A/B/C/D 非空组合的显式 `m4l` on/off 重训练对照、普通/对抗训练、条件 CDF、共同二维模板、冻结 assessment、T0/T1 推断及样本效率链路均已有软件实现。
- 默认协议的 `protocol_scope` 是 `synthetic_software_defaults_not_physics_validation`；当前没有可直接作为论文结果的冻结完整 MC run。
- MELA 只有导出/导入及可选 adapter 契约，实际后端和独立物理参考仍需验证。

精确证据状态见[当前科研与软件状态](docs/results-and-limitations.md#software-and-validation-status)，研究设计见[研究方案](docs/research-design.md)。

## 2. 了解代码库目录结构

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

## 3. 配置运行环境并安装项目

项目要求 Python `>=3.12,<3.13`，仓库约定使用 Conda `pytorch` 环境。

从环境定义创建时：

```bash
conda env create -f environment.yml
conda activate pytorch
python -m pip install --no-deps -e .
python -m pip check
```

核心推断需要 `pyhf` 等研究扩展依赖：

```bash
python -m pip install -r requirements.txt
```

`win.yml` 与 `osx.yml` 是已有 Windows 和 macOS 环境快照，`environment.yml` 提供通用环境定义；它们都不是权威平台要求。项目可在依赖可用的 Windows、Linux 或 macOS，以及不同 CPU 架构上运行。MELA 后端需在独立 Linux/WSL 环境中配置。

安装后统一核心入口为：

```bash
higgsml --help
```

## 4. 下载并校验受控 MC 数据集

下载器只执行数据集契约中固定的 HTTPS 请求，并在文件大小与 SHA-256 全部匹配后发布 receipt：

```bash
python scripts/init_data.py --dataset atlas2020_4lep
```

输入写入 `data/raw/<dataset>/`。下载器也认识 `atlas2025_exactly4lep`，但它属于独立 release/collection，不能与 2020 文件混配；当前正式 H4l 协议与工作流仍绑定 `atlas2020_4lep`。任何阶段都不得读取或处理真实数据。

数据契约位于：

- [`config/datasets/atlas2020_4lep.json`](config/datasets/atlas2020_4lep.json)
- [`config/datasets/atlas2025_exactly4lep.json`](config/datasets/atlas2025_exactly4lep.json)

## 5. 运行 H4l 工作流

用一个命令完成 prepare、G1、五随机种子批次、off-only Stage B、评估访问包、C–E evaluation 和最终报告：

```bash
python scripts/h4l_all.py --run-name test01
```

`--run-name` 是唯一需要输入的参数，同时用于 `runs/h4l-train-test01/` 和 `runs/h4l-off-test01/`。不传时默认使用 `default`：

```bash
python scripts/h4l_all.py
```

重复执行同一命令会自动核对进度。绑定一致且 manifest 完整的阶段直接跳过；缺失阶段继续执行；损坏、不完整或绑定不匹配的最终目录会保留为 `.名称.<uuid>.invalid` 后再尝试当前阶段，已有 `.failed` 证据不会删除。若评估预算已经被失败或中断的 assessment/T2 占用，脚本仍按冻结协议拒绝自动重跑。

封装命令为 `h4l_off_run.py` 传入 `--worker-threads 1`，并按启动时可用物理内存为每个 worker 预留 6 GiB、在 1--4 个进程之间选择 `--workers`；内存探测失败时使用 1 个进程。可并行的完整 bootstrap、Toy 和 T2 工作单元并行执行，Stage B 的注册、模板、freeze 与 Asimov 仍按依赖顺序执行。

如果 `runs/h4l-off-<run-name>/access-review/validated-off-assessment-access.json` 已存在，命令直接复用它；否则使用本机 `git user.name`（回退到登录账户名）生成明确标记为 `single_researcher_self_review`、`independent: false` 的单研究者自审包。该包只允许探索性自审结论，不代表独立科学验证。

最终报告位于 `runs/h4l-off-<run-name>/evaluation/report/report.md`。`m4l=off` 仅表示分类器不输入显式四轻子质量，似然仍保留质量坐标。完整阶段契约、人工独立审核方式及恢复限制见[复现实验手册](docs/implementation-and-reproduction.md)。

## 6. 分阶段运行 H4l 工作流

新增 off-only 分析入口为 `python -m higgsml.cli attribution --help`。它复用现有 75 个 off 模型，新增五个确定性 M0off 身份，并依次发布注册、共同模板、freeze、Asimov、事件 bootstrap、Toys、T2 和独立报告。完整命令见[off-only 复现步骤](docs/implementation-and-reproduction.md#off-only-attribution-execution)。已有标准训练链路保留兼容，不需要为这项分析重训模型。

`m4l=off` 仅指分类器不输入显式四轻子质量；似然仍保留质量坐标。自动 P0/T1 材料不能授予独立科学资格；事件 bootstrap、Toys、T2 和外部参考状态分别保存。

所有命令从仓库根目录运行。完整规则、门槛与恢复方式以[复现实验手册](docs/implementation-and-reproduction.md)为准。

### 6.1 准备并固化可复用输入

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

### 6.2 运行门控检查

```bash
python scripts/h4l_check.py --run-name test01
```

Gate 从全局 prepared artifact 运行 M0c、M2、M3、五个校准和共同模板。只有 Gate 通过后，才允许展开受门控的候选。失败目录仍是不可变证据；修复后必须使用新的 `--run-name` 或 `--output-root`。
`--run-name test01` 的实验输出根目录为 `runs/h4l-train-test01/`。

### 6.3 运行五随机种子正式批次

```bash
python scripts/h4l_run.py --run-name test01
```

默认批次执行 seed 42–46 的注册候选、校准、共同模板、T1 `mu=1` inference 与报告。显式 `--seed 42` 仅是单种子诊断，不能支持五种子主比较。

批次中断后，使用 `--continue` 继续：合法的完整阶段会被跳过；不完整、损坏或绑定不匹配的最终阶段目录会先隔离为 `.名称.<uuid>.invalid`，再重试一次。已有 `.failed` 证据不会被删除。

```bash
python scripts/h4l_run.py --run-name test01 --continue
```

三个脚本均支持 `--help`、`--plan-only` 和 `--no-progress`。它们也提供严格限于所选 `runs/` 子目录的 `--clean`；`--clean` 不能与 `--plan-only` 同时使用，执行前应先用 `--help` 或单独的计划命令核对路径。清理会删除不可恢复的本地运行产物；完成、失败、诊断或已发布的 run 均不得原地覆盖。

### 6.4 运行 Stage B 生成 freeze

```bash
python scripts/h4l_off_run.py --source-run-name test01 --run-name study-001 --stage-b
```

先运行 Stage B，产生 freeze 和自动绑定的 evaluation plan。

`scripts/h4l_off_run.py` 直接复用已有的完整五随机种子批次及 `runs/h4l-prepare/prepare`，不重新 prepare 或训练。它自动核对 prepared artifact、population、核心协议，以及 75 个 `m4l=off` 训练/校准产物的候选、seed、checkpoint 和上游绑定；任一身份不一致时拒绝复用。

调试协议或流程代码时，可以复用协议摘要不一致的既有 prepare/train/calibrate 产物：

```bash
python scripts/h4l_off_run.py --source-run-name test01 --run-name debug-001 --stage-b --force
```

`--force` 只绕过来源产物的协议一致性检查，仍校验 dataset、artifact digest、候选身份、checkpoint、population 和上游关系。输出会标记为 `forced_protocol_mismatch_debug`，仅用于调试，不能作为论文或科学结论证据。调试完成后必须去掉 `--force`，使用新的 run name 正常运行。

### 6.5 评估访问审核

Stage B 完成后，assessment/T2 只能使用与实际 freeze、population、protocol 和 P0/T1 文件绑定的 access-review。独立审核者应依据
`config/examples/h4l_off_assessment_access.pending.json` 生成并审核一份完整的
`validated-off-assessment-access.json`，然后在最终执行时通过 `--access-review` 显式传入。该 pending 文件含占位 ID 和 receipt，不能直接使用；脚本也不会自动把它提升为独立证据。

如果项目只有一名研究者，不能形成独立审核，可明确生成单人自审包：

```bash
python scripts/h4l_off_self_review.py --run-name study-001 --reviewer "Researcher Name"
```

该命令只生成标记为 `single_researcher_self_review` 的 access-review，不代表独立验证；`--reviewer` 必须填写实际姓名。它不会执行最终评估。

### 6.6 生成最终报告

完成独立审核，或生成单人自审包后，执行：

```bash
python scripts/h4l_off_run.py --source-run-name test01 --run-name study-001 --evaluation
```

默认读取 `runs/h4l-off-study-001/access-review/validated-off-assessment-access.json`；独立审核包位于其他路径时，显式追加 `--access-review <path>`。该命令读取并绑定实际 prepared、registration、nominal、freeze 和 evaluation-plan artifact，随后执行 C–E evaluation 并生成最终报告。它不会自动生成或批准 access-review。

单人自审命令生成的 access-review 包含：

```text
runs/h4l-off-study-001/access-review/
├── self-reviewed-p0-applicability.json
├── self-reviewed-signed-mc-t1.json
└── validated-off-assessment-access.json
```

单人自审允许执行冻结的 assessment、T2 和最终报告，但不会伪装成独立验证。生成文件和最终报告固定记录 `single_researcher_self_review`、`independent: false` 与 `exploratory_self_reviewed_not_independently_validated`；论文必须披露该限制。命令拒绝覆盖既有 `access-review`。如果 Stage B 使用了 `--force`，最终输出还会保留 debug-only 标记，不能作为正式科学证据；应优先用协议一致的来源 run 和新名称重新运行 Stage B。

脚本依次完成 registration、共同 nominal 模板、freeze、Asimov、事件 bootstrap、三组 model-self Toys、三组受控 assessment Toys、T2 和最终报告。Stage B 使用新目录；`--evaluation` 复用该 Stage B 并拒绝覆盖已有 evaluation。若来源批次尚不存在或不完整，先使用 `scripts/h4l_run.py` 生成新的完整五随机种子批次。详细阶段契约与恢复规则见[off-only 复现步骤](docs/implementation-and-reproduction.md#off-only-attribution-execution)。

### 6.7 按 seed 配对的 v2 评估（显式启用）

`h4l_all.py` 默认 v2；`h4l_off_run.py`、`h4l_evaluate.py` 和 attribution CLI 默认 v1。以下默认 v1 的入口需要显式传入 `--evaluation-version v2`；`h4l_all.py` 省略版本时已选择 v2。v2 并把每个 training seed 的 `M0off + 15` 个 coalition 作为一个 16-way joint block；Toy seed 由冻结预算派生，不能用 `--training-seed` 代替。以下 Linux Bash 命令从仓库根目录运行：

```bash
python scripts/h4l_off_run.py \
  --evaluation-version v2 \
  --source-run-name test01 \
  --run-name within-seed-001 \
  --stage-b \
  --show-command

python -m higgsml.cli attribution access-review \
  --evaluation-version v2 \
  --protocol config/protocols/h4l_protocol.json \
  --registration-run runs/h4l-off-within-seed-001/register \
  --template-run runs/h4l-off-within-seed-001/nominal \
  --freeze-run runs/h4l-off-within-seed-001/freeze \
  --result-run runs/h4l-off-within-seed-001/asimov \
  --evaluation-plan runs/h4l-off-within-seed-001/evaluation-plan/evaluation-plan.json \
  --access-review path/to/validated-off-assessment-access.json \
  --run-dir runs/h4l-off-within-seed-001/access-review-v2

python scripts/h4l_off_run.py \
  --evaluation-version v2 \
  --source-run-name test01 \
  --run-name within-seed-001 \
  --evaluation \
  --access-review runs/h4l-off-within-seed-001/access-review-v2/validated-off-assessment-access.json \
  --show-command
```

Stage B publishes `source-register`, `register`, `source-nominal`, `nominal`, J0, J1, `evaluation-spec`, `freeze`, `asimov`, and `evaluation-plan` in dependency order. The first two `source-*` directories retain the original v1 identities; `register` and `nominal` are audited v2 adapters and do not relabel those artifacts. J0 and J1 use development/template material and record `assessment_payload_read=false`; a failed gate blocks freeze.

The evaluation contains 36 scientific units (one 200-replica MC bootstrap, 15 model-self cells, 15 assessment cells, and five T2 cells) plus the report, for 37 terminal units. Each model-self/assessment cell has 500 Toys for one training seed and one `mu` in `{0,1,2}`; each T2 seed has 20 outer replicas and 100 inner Toys. Scientific failures remain terminal evidence and do not authorize replacement draws. A consumed claim with missing or damaged output is `blocked_consumed_budget` and is never replayed automatically.

An already opened historical assessment population can support only `posthoc_support_diagnostic`; it cannot become a new eligible prospective source. Without an unused, reviewed assessment source, prospective assessment remains `blocked_missing_eligible_assessment_source`. Independent P0/T1 applicability evidence and the original controlled-MC evaluation remain pending.

### 6.8 显式启用 v3 边缘 CRN 评估

```bash
python scripts/h4l_off_run.py --evaluation-version v3 \
  --source-run-name test01 --run-name marginal-v3-001 --stage-b
```

v3 使用共同总数与单调类别分配的人工 CRN 耦合，保持候选边缘 Poisson
分布；它不代表物理事件联合配对。J0/J1 必须通过才能 freeze，历史已打开的
assessment 不会因此重新获得资格。默认版本不切换到 v3。完整契约见
[复现手册](docs/implementation-and-reproduction.md#marginal-crn-evaluation-v3-explicit-opt-in)。

## 7. 使用项目工具开展研究

`higgsml` 暴露十二个可组合阶段：

```text
audit -> prepare -> [me-export -> me-import] -> train -> calibrate
      -> templates -> freeze -> infer -> [mc-bootstrap] -> report
                                      [evidence-import] ---^
```

```bash
higgsml train --help
higgsml calibrate --help
higgsml templates --help
higgsml infer --help
higgsml mc-bootstrap --help
higgsml evidence-import --help
```

直接调用阶段时，必须显式绑定 dataset、`config/protocols/h4l_protocol.json`、上游 run 与 `runs/` 下的全新输出目录。编排脚本会自动传入该唯一默认协议；`higgsml` 子命令仍要求显式提供 `--protocol`。`manifest.json` 记录数据集、协议快照、上游 artifact、文件摘要、代码/环境、随机种子和科学终态；模型 JSON 只保存数值张量，不加载可执行 pickle。详细字段见[产物与谱系契约](docs/implementation-and-reproduction.md#artifact-and-lineage-contract)。

最终 `report` 支持重复传入 `--training-run`、`--evaluation-run`、`--evidence-run`，并继续以
`--result-run` 承载主推断结果。增强报告除 `report.json`/`report.md` 外，会发布完整精度 UTF-8 CSV、
逐表逻辑行的 `analysis_records.jsonl`、`provenance.json` 与 `data_dictionary.json`。其中 `models.csv` 和 `feature_metrics.csv` 明确记录所选
checkpoint 的 validation absolute-weight AUC 及同 seed 相对 M0c 的 AUC 绝对差；训练状态与推断状态
分别保存。旧 run 不修改，可作为显式上游生成新的报告目录。

注册统计评价由独立脚本执行：

```bash
python scripts/h4l_evaluate.py --help
python scripts/h4l_evaluate.py --plan config/examples/h4l_evaluation_plan.json \
  --prepared-run runs/... --template-run runs/... --freeze-run runs/... \
  --output-root runs/h4l-evaluation-001 --plan-only
```

示例计划是 `exploratory_posthoc` 模板，三个输入 artifact ID 均为待替换的零值，不能直接作为正式
注册计划执行。实际执行会核对 prepared/template/freeze artifact ID、协议摘要和 Toy/T2 预算；
计划模式只审计矩阵，不打开 assessment。外部 signed-MC/T1、物理系统变化和 MELA
材料通过 `evidence-import` 只读接入；缺失材料必须保持 `external_pending`。


## 8. 遵守科学与运行约束

- 只处理受控 MC 或显式标记的合成事件，绝不读取、散列、预处理、评分或绘制真实数据。
- `m4l` 只能按版本化 H4l 协议使用；signed `physical_weight` 用于物理产额，优化器权重按协议定义。
- 同一物理事件组必须保持在同一 split/fold；train、validation、calibration、template、assessment 的职责不可混用。
- assessment 只能在协议定义的冻结状态后访问，结果不得回流调整候选、阈值、分箱、映射或协议。
- 数据身份、SHA-256、协议 seal、checkpoint、上游绑定与 lineage 必须保留。
- 软件测试通过只证明对应软件行为；不能据此声称获得 `mu` 精度改善、覆盖可靠性或完整 MC 科学结论。

## 9. 验证代码、依赖与运行环境

在仓库根目录运行：

```powershell
python -m compileall -q src scripts tests
python -m pytest -q
python -m pip check
```

当前测试数量、警告和未完成的科学验证以[状态页](docs/results-and-limitations.md#software-and-validation-status)的日期化记录为准，不在 README 中复制易过期的数字。

## 10. 查阅项目文档

- [文档索引](docs/README.md)
- [研究方案](docs/research-design.md)
- [软件与科学模块结构](docs/implementation-and-reproduction.md#tools-and-architecture)
- [复现实验手册](docs/implementation-and-reproduction.md)
- [产物与谱系契约](docs/implementation-and-reproduction.md#artifact-and-lineage-contract)
- [证据与完成边界](docs/results-and-limitations.md#evidence-required-for-conclusions)
- [当前科研与软件状态](docs/results-and-limitations.md#software-and-validation-status)
- [论文稿件](paper/manuscript.md)

## 11. 许可证与第三方条款

见 [`LICENSE`](LICENSE)。第三方数据、软件与实验资料仍受其各自许可和使用条款约束。
