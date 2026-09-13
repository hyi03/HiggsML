# H4l Artifact 与谱系契约

本文概述当前持久化接口。精确字段、schema identifier 和列顺序以 reader 常量及版本化协议为准。

## 通用运行契约

所有 run 位于允许根 `runs/` 下的全新目录。运行先写同父目录 staging，成功后原子发布；成功 manifest 最后写入，并登记自身之外每个文件的大小和 SHA-256。失败发布清理过的失败证据，不伪造成功 manifest。

每个阶段至少绑定：

- dataset 定义、profile、协议原始字节及摘要；
- 直接上游 artifact 的路径、stage、artifact ID 与 receipt；
- 阶段参数、随机种子、资源、软件版本和平台；
- 文件摘要、canonical payload 摘要和科学终态。

Reader 不信任调用者构造的内存对象，必须从路径重新验证 manifest、文件 receipt、schema、上游 multiplicity 和可重算身份。完成、失败和诊断 run 都不可覆盖。

## H4l 主流程

主流程使用 `research-run-v1` manifest，阶段包括：

| 阶段 | 主要产物 | 关键绑定 |
|---|---|---|
| `audit` | 数据来源与统计审计 | dataset、profile、协议、ROOT manifest |
| `prepare` | `events.jsonl` 与角色摘要 | 重建/选择、事件身份、五角色、权重与总体 |
| `me-export` / `me-import` | 冻结输入与外部矩阵元结果 | 后端配置、输入顺序、参考和结果摘要 |
| `train` | `model.json`、训练历史与曲线 | 表示、条件变量、scaler、结构、seed、checkpoint |
| `calibrate` | calibration payload | 模型、calibration 总体、权重语义、CDF/threshold |
| `templates` | template、共同网格与 G1 | calibration 集合、共同分箱、signed yield、sumw2 |
| `freeze` | 冻结状态与 assessment 预算 | 协议、候选、模板、likelihood 与所有前置门 |
| `infer` | workspace、点估计、区间或 Toy | 模板、layer、注入点、seed、预算和失败状态 |
| `mc-bootstrap` | `bootstrap.json`、封存评价计划 | 固定网络、配对 calibration/template 事件组重采样、共同质量网格 |
| `evidence-import` | `evidence.json` | 外部文件 receipt、独立性说明、协议与总体适用范围 |
| `report` | 绑定结果、图表与分析表 | result/training/evaluation/evidence 分类输入、结论门和解释范围 |

`prepare` 将物理事件组分为 train、validation、calibration、template、assessment。身份与角色不允许交叉；assessment 在 freeze 前不得解码。`mu=0` 的 signed diagnostic 是固定名义模板 T0 点估计，不替代 T1 剖面或物理区间覆盖结论。

## 增强报告导出契约

`report` 保留原有字段并发布 `h4l-analysis-export-v1`。报告输入不扫描目录猜测关系，只消费通过
manifest/receipt 校验且显式传入的 `--training-run`、`--evaluation-run`、`--evidence-run` 和
`--result-run`。主要表如下：

| 文件 | 行粒度 |
|---|---|
| `models.csv` / `training_history.csv` / `model_mass_diagnostics.csv` | 模型×seed、模型×epoch、模型×质量箱 |
| `feature_metrics.csv` / `feature_summary.csv` | 特性组合×seed、特性组合五种子汇总 |
| `calibration_summary.csv` / `calibration_slices.csv` / `calibration_bins.csv` | mapping、质量切片、分数箱 |
| `template_bins.csv` / `template_covariance.csv` | 候选×过程×模板箱、非零组协方差元素 |
| `inference_intervals.csv` / `toy_fits.csv` | Asimov 区间、逐 Toy×置信水平拟合 |
| `coverage_summary.csv` / `fit_diagnostics.csv` / `paired_comparisons.csv` | coverage、bias/pull、共享观测配对差 |
| `bootstrap_replicas.csv` / `procedure_replicas.csv` / `stress_results.csv` | 主 bootstrap、T2 外层副本、人工压力场景 |
| `feature_attribution.csv` / `feature_interactions.csv` | Shapley 与全部二阶差分 |
| `run_statuses.csv` / `evidence_status.csv` | 分阶段状态、独立证据状态 |

`provenance.json` 绑定协议、总体、上游、评价计划、共同网格、软件环境及导出文件 receipt；
`data_dictionary.json` 给出列类型、单位、公式、评价角色与缺失语义。历史字段不存在时保持空值并以
`not_recorded`/状态列解释，不从总 loss 推测分类 loss，不把缺失值填零。AUC 仅指所选 checkpoint 的
`validation_absolute_weight_auc`；M4/M5 的 CDF 后处理不继承 raw AUC 并改称 CDF AUC。
`analysis_records.jsonl` 以 `{table,row}` 逐行镜像所有 CSV 逻辑行，保留 JSON 数值精度，便于无需
CSV 类型推断的重放。

完整逐 Toy/逐副本数据保存在 CSV 和原始 inference/procedure/bootstrap artifact 中；`report.json`
保留兼容的结果摘要、索引和表行数，但以 `result_count`/`results_export` 代替逐 Toy 数组，避免重复嵌入大型结果。

## 独立证据包

`h4l-independent-evidence-v1` 可表达 `signed_mc_t1`、`physical_systematics`、`mela`、
`arm64_authority` 与 `frozen_assessment`。`validated` 状态必须提供外部生产者、reference ID、
独立性依据和至少一个位于包目录内的 SHA-256/大小 receipt；每种证据还需其类型专用元数据。
格式通过本身不构成独立科学验证。材料未到位时可导入 `external_pending`，但不能提升任何对应结论。

## 样本效率流程

样本效率 overlay 位于 `config/protocols/sample_efficiency_v1.json`。其中 `null` 是待注册占位，不能作为正式运行值；测试中的完整值仅用于合成软件验证。

### 冻结与训练子集

| 产物 | Schema / stage | 含义 |
|---|---|---|
| compact candidate freeze | `h4l-compact-candidate-freeze-v1` | 冻结唯一 compact 组、探索历史、总体排除集和 payload digest |
| overlay | `h4l-sample-efficiency-protocol-v1` | 绑定 base protocol、prepared population、freeze artifact 和实验预算 |
| subset plan | `training-subsets` | 确定性 fraction/draw、成员 JSONL、full alias 与逐类统计 |
| subset model | `sample-efficiency-train` | 绑定 subset、representation、architecture、seed、模型与实验 lineage |

子集 reader 先验证完整 prepared receipt 和所有身份，只解码 train payload 计算成员与摘要；其他角色，尤其 assessment，不得读取。相同数据、网络和结构的不同表示共享 `pairing_id`，每个具体 cell 使用独立 `experiment_cell_id`。

### 学习曲线批次

| Stage | 主要文件 | 约束 |
|---|---|---|
| `sample-efficiency-plan` | `batch-plan.json` | 科学计划与执行计划分离，绑定 prepared、freeze、subsets、G1/T1 |
| `sample-efficiency-calibration` | `calibration.json` | 只接受已验证 subset model 与 raw calibration lineage |
| `sample-efficiency-common-grid` | `common-grid.json` | 从完整参与者集合生成可重算的共同质量网格 |
| `sample-efficiency-template` | `template.json` | 绑定自身 calibration、共同网格、prepared 和 lineage |
| `sample-efficiency-inference` | `inference.json` | 固定 model-self Asimov 语义与 W68/AUC pointer |
| `sample-efficiency-batch` | ledger 与 summary | 每个计划 cell 的完成、科学终态或 blocked stage |

科学终态保留已发布阶段并显式列出 blocked stages；绑定错误、重复、缺失或未知错误不得产生可供报告消费的 batch。

### 配对聚合报告

`sample-efficiency-report` 固定发布：

```text
report-contract.json
sample-efficiency-records.jsonl
sample-efficiency-summary.json
sample-efficiency-curves.csv
sample-efficiency-curves.png
sample-efficiency-report.md
manifest.json
```

Reader 重放 batch、cell、bootstrap、配对聚合和 Q*，并逐字节核对 JSON/JSONL/CSV/Markdown；PNG 是由绑定 plot spec 生成的非权威缓存。报告必须显式给出 planned、complete、terminal 与有效 pair 分母，不能用缺失 cell 得出非劣结论。

### Controls 与独立确认

`sample-efficiency-controls` 可执行容量匹配和 physical-CDF 检查。容量对照使用协议固定的参数量匹配结构；CDF 指标以 absolute-weight acceptance 报告，而 signed physical weight 只用于拟合冻结 mapping。

Confirmation 输入在 claim 前只扫描 header、identity 与文件摘要，不解码 payload。身份排除集必须拒绝与训练、校准、模板、assessment 或已登记探索总体的任何重叠。Durable claim 使用 exclusive create；claim 后成功或失败都是终态，只有协议允许且显式请求时才可在新目录重放同一冻结分析。

合成验证只能产生 synthetic 结论。受控 MC 的非劣确认在正式 evaluation package、独立性证明和 authority 证据完成前保持 `external_pending`。

## 失败、安全与 authority

失败证据只能包含可安全公开的阶段与 binding，不得包含未授权 assessment 行、特征、预测或阈值。空的 `config/schemas/registry.json` 表示没有可自认证的 golden；authority reference 必须独立预登记。

软件测试、合成数值验证、完整 MC、独立 MELA 参考和原生 ARM64 authority 是不同证据层级。任何 schema 或 run 只有在对应证据实际完成后，才能支持相应科学结论。
