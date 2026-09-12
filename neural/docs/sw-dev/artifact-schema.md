# Artifact 契约

**当前代码已实现。** 本文描述当前持久化接口。文件名保持稳定；正文中的 schema identifier 可版本化，因为 reader 需要据此拒绝不兼容 artifact。精确字段和列序最终以当前配置与 reader 常量为准。

## 1. 通用运行契约

所有 run 位于允许根下的具名 dataset 与全新 run 目录中。运行先在同父目录 staging，成功后原子发布。成功 manifest 最后发布并列出自身之外每个产物的大小和 SHA-256；失败发布 `failure.json`，不发布成功 manifest。

`dataset_binding` 包含 dataset 名、定义 revision/摘要、release、collection、profile/science 摘要、事件身份策略和两个受控 MC 成员。配置 snapshot 保存调用时的精确协议与绑定，不能用后来修改的同名配置解释旧 run。

CSV gzip 记录压缩文件摘要、解压后 canonical CSV 摘要和行数。Canonical JSON/CSV 固定编码、键/列顺序、数值和换行规则。

## 2. Preprocess run

```text
config.yaml
processed/development_events.csv.gz
processed/test_events.csv.gz
artifacts/cutflow.json
artifacts/mc_summary.json
artifacts/manifest.json
```

Mass-window/debug manifest 使用当前 2.x 内部契约，两个表各 31 列；inclusive 使用当前 3.x 内部契约，各 30 列且无 `train_weight`。共同尾部身份字段为 `source_file_id` 和 `event_group_id`。Development 表只含 train/validation，test 表只含 test。

Manifest 至少绑定：输入文件与摘要、dataset/profile/science、协议和 run config、ordered columns/dtypes、每成员 cutflow、split 计数、软件/平台、确定性和性能。

## 3. Development run

```text
config.yaml
artifacts/candidate_metrics.csv
artifacts/fold_metrics.csv
artifacts/qualification.json
artifacts/working_points.json
predictions/oof_scores.csv.gz
plots/auc_vs_lambda.png
plots/ks_vs_lambda.png
plots/oof_roc.png
plots/oof_mass_sculpting.png
artifacts/manifest.json
model/model.pt                 # 仅允许终态
model/scaler.json              # 仅允许终态
```

Inclusive 还要求：

```text
artifacts/scientific_state.json
artifacts/mass_diagnostics.json
```

有窗 OOF 列为：

```text
source_file_id,event_group_id,target_lambda,source_sample,source_entry,
fold_index,label,m4l,physical_weight,train_weight,score
```

Inclusive 将 `train_weight` 列替换为 `metric_weight`。Fold/candidate 表字段由训练协议中的 `development_artifacts` 固定。

Manifest 绑定上游 preprocess partition/manifest、dataset、协议、OOF 完整性、候选资格、环境与统计。Final payload 使用当前 `adversarial-mlp-final` 内部 schema；scaler 使用 `fold-local-scaler-v2`，二者都携带同一 dataset/protocol/feature binding。

状态与发布规则：

| 状态 | Manifest | Final model/scaler | 含义 |
|---|---|---|---|
| `eligible` | 是 | 是 | 正式 development 候选通过 |
| `no_eligible_candidate` | 是 | 否 | 正常完成但无合格候选 |
| `insufficient_statistics` | 是 | 否 | Inclusive 统计前提不足 |
| `debug_diagnostic` | 是 | 可有 | 仅诊断，不构成正式资格 |

## 4. Test-opening run

```text
config.yaml
artifacts/test_metrics.json
predictions/test_scores.csv.gz
plots/test_roc.png
plots/test_mass_sculpting.png
artifacts/manifest.json
```

Test manifest 绑定 preprocess/development/model/scaler/working-points 的 lineage、dataset、协议和所有摘要。普通预测列包含来源行/事件组身份、sample/entry、label、`m4l`、physical/train weight 和 score；inclusive 使用 `metric_weight` 替代 `train_weight`。

状态为 `test_reproduced`、`test_nonreproduction` 或显式 `debug_diagnostic`。有 authorization reference 时，development run 下另有：

```text
state/test_opening.json
```

其内部 schema 为 `test-opening-state-v2`，记录 claim、成功或 `failed_after_claim` 终态。该 state 是 one-shot 协调状态，不得手工删除以重试。

## 5. 失败、安全与 authority

`failure.json` 记录异常类别、稳定退出码、时间、已知 stage 和可安全公开的 binding；test claim 后只允许清理过的阶段消息。它不能包含事件行、特征值、预测、模型参数或阈值。

Authority evidence 与普通 run 分离。当前 comparator 只在 native osx-arm64 上针对相同 dataset 的 development 特征/结构比较预登记 reference；空 `config/validation/registry.json` 表示没有可自认证的 golden。运行产物和模型不提交 Git。

## 6. 独立研究 artifact

**当前代码已实现。** `research-run-v1` manifest绑定协议快照、上游、文件摘要、代码/环境及状态。各阶段保存events、model、ME、calibration、templates、freeze和inference的独立JSON产物。v2协议不改写v1协议字节；新model中的history_contract绑定分项损失与逐轮质量诊断，`learning-curves.png`进入manifest；report可从已绑定的train产物生成同种子M6/λ=0配对图。

μ=0的v2 Toy另存`signed_mu_diagnostic`及汇总，标为固定名义模板T0点估计、非T1剖面；搜索边界/不可用状态保留，不替代原物理区间或覆盖状态。历史模型缺少分项history时不补造曲线。阶段文件及失败契约见[运行手册](h4l-research-runbook.md)。

**需要外部或权威验证。** 任何未来 schema 只有通过合成数值测试、独立参考和锁定平台重放后，才可支持方案中的科学结论。

## 7. 样本效率元数据契约

**已实现纯 payload 校验；实验执行及正式预注册未完成。** `src/research/sample_efficiency_protocol.py` 独立于旧 ResearchProtocol，提供下表两个契约。它不发布 run，不验证 manifest receipt，不读取事件，不创建 claim，也不实现 CI/子集/容量/CDF 的统计执行器。

| Schema | API | 身份与摘要 |
|---|---|---|
| `h4l-compact-candidate-freeze-v1` | `freeze_compact_candidate(metadata, groups=..., base_protocol=...)`；`CompactCandidateFreeze(raw, base_protocol=...)`；`load_compact_candidate_freeze(path, base_protocol=...)` | builder 从显式组构造 canonical candidate descriptor；保存探索历史、总体排除集、delta/source。`payload_sha256` 与对象 `.digest` 均为排除 payload_sha256 键后的 canonical SHA-256。 |
| `h4l-sample-efficiency-protocol-v1` | `SampleEfficiencyProtocol(raw, base_protocol=..., prepared_artifact_id=..., population_id=..., compact_freeze=..., compact_freeze_artifact_id=...)`；同参数的 `load_sample_efficiency_protocol(path, ...)` | `.digest` 为完整 canonical payload SHA-256；分别绑定 base digest、prepared ID、population ID、freeze manifest artifact ID 与 freeze payload digest。 |

构造函数和 loader 都执行校验；没有接受未经绑定 bytes 的快捷构造。`.payload` 为不可变 bytes，`.to_dict()` 和索引返回防御性副本。Canonical JSON 复用旧协议的排序键、紧凑 separators、非有限拒绝策略，不改变旧版本摘要；JSON 重复键、未知/缺少字段、错误类型、NaN/Infinity 均拒绝。未知 schema/算法 ID 不迁移、不猜测。

字段全集、算法 ID 和绑定不变量记录在 [FR-SE-01](../1-Requirement/Done/FR-SE-01-sample-efficiency-contracts.md) 的“v1 软件字段规范”。overlay 精确包含 decay7、唯一 compact、engineered19；fraction 必须有完整端点；seed 分层；capacity/CDF 只允许冻结的精简点位；calibration uncertainty 明确为 not_estimated；评价重采样只声明 validation absolute-weight AUC，不能冒充 W68 误差。统计执行器实现前，这些可解析规则不授权任何实验或确认访问。

`config/research_sample_efficiency_protocol_v1.json` 是**不可运行模板**，null 表示未注册值，普通 loader 必须拒绝。测试中的完整值只用于 synthetic 软件验证。调用者需要显式提交注册值、合法 freeze 和期望上游身份；payload 自摘要不能证明来源、历史完整性或总体独立性。未来 workflow 必须另外验证上游 receipts、把学习总体加入确认排除集、完成 claim-before-decode。

M1 额外拒绝把 freeze payload SHA 同时用作 freeze artifact ID，即使调用方传入了同样的期望值；该检查不证明其他任意 ID 的来源合法性。

无 freeze 时抛 `ResearchError(status="compact_candidate_not_frozen")`，exit_code=3；其他 schema/binding 失败也是输入错误。M1 不发布科学终态；未知异常仍由未来 CLI 映射。旧 `research-run-v1`、ResearchProtocol v1/v2/v3、`research-discriminant-v1` 不变，未来 subset/model v2/report/confirmation payload 尚未实现。

证据范围仅为 Windows synthetic 软件验证。Repository ARM64 authority、完整 ROOT 与 scientific numerical validation 均需后续独立证据。

## 8. 训练子集计划

**已实现并通过synthetic验证。** `training-subsets` research run绑定base ResearchProtocol、SampleEfficiencyProtocol snapshot、prepared和compact-freeze两个上游。读取器先验证manifest及每个文件receipt，再重算identity、population、成员资格、摘要、subset/alias ID和ledger。

| 文件 | Schema | 内容 |
|---|---|---|
| `training-subsets.json` | `h4l-training-subset-plan-v1` | 双协议/freeze/prepared/population绑定、identity digest、去重subset及逐类和总计的组级权重摘要 |
| `training-subset-membership.jsonl` | header `h4l-training-subset-membership-v1` | canonical排序的draw/full、fraction、label、event_group_id；full成员只发布一次 |
| `training-subset-ledger.json` | `h4l-training-subset-ledger-v1` | 每个原始draw/fraction alias、共享full subset、planned或低统计终态 |

prepared events采用两阶段读取：所有 public API 从路径重新执行 `read_run` 并验证整文件receipt，再按 base protocol 精确验证split、全部identity、`event_id`/`source_row_id`唯一性，随后只解码train payload的weight/m4l用于摘要。其他角色、尤其assessment payload永不解码。membership reader要求拒绝重复键并逐行验证canonical JSON bytes；fraction端点固定为JSON float `1.0`。`training_subset_insufficient_statistics`保留为complete计划内cell状态；输入非有限、身份、receipt或重算不一致为`training_subset_binding_mismatch`。本阶段不训练模型。

## 9. 子集绑定判别器与实验血缘

`sample-efficiency-train` research run 由非 CLI application service 发布。它从 receipt 验证后的 prepared `events.jsonl` 内部加载数据，只筛选 train membership并保留完整validation；manifest upstream精确绑定 `prepare`、`compact-freeze`、`training-subsets`。run保存 `sample-efficiency-protocol.json` snapshot和 `model.json`，reader从路径重验所有run/receipt、M2 selection、snapshot及模型语义。

| Schema | 位置 | 关键约束 |
|---|---|---|
| `h4l-training-subset-selection-v1` | 内存不可变 `TrainingSubset` | 由M2 plan/membership/ledger重算后选择；绑定prepared/population/overlay/subset/membership、规范fraction/draw、逐类/总计摘要和M1 freeze candidate descriptor。消费者根据保存的三个run路径再次验证，类型本身不是信任证明。 |
| `research-discriminant-v2` | `sample-efficiency-train/model.json` | 保留v1科学字段并增加base/overlay/subset/prepared身份、representation、network/architecture、实际摘要、train-fitted来源及experiment/pairing ID。严格拒绝未知/缺失/非有限字段；即使重签model ID也重算seed、full/partial、表示、参数量、摘要和ID不变量。 |
| `h4l-experiment-lineage-v1` | raw calibration、template entry、model-self result的`experiment_lineage` | 只能由verified model-run reader构造；绑定source model artifact/model ID、双协议、prepared/population、subset/membership、fraction/draw/network、representation/architecture、raw transform及experiment/pairing ID。每层从直接可信上游精确比较。 |

`experiment_cell_id`的canonical SHA-256 preimage为 `[overlay_digest,training_subset_artifact_id,subset_id,representation_id,fraction,draw_or_full,network_seed,"raw",architecture_variant]`；`pairing_id`去掉representation字段。因此同一数据/网络/架构的三表示共享pairing ID，experiment cell互不冲突。M3仅开放基线架构、raw calibration、普通template和model-self Asimov；CDF/absolute、capacity、assessment/mismatch及sample-efficiency confirmation在M6前保持关闭。旧`train_discriminant()`与`research-discriminant-v1`读取路径不变。

可信 v2 计算接口不接受裸 `model.json` 或调用方构造的 lineage。`read_subset_discriminant_run()` 返回不可由普通构造函数伪造的 `LoadedSubsetDiscriminant`；v2 预测、校准和模板构建均消费该 handle并重新检查model receipt。raw calibration由绑定prepared run的calibration role内部生成，作为不可变 `RawCalibrationBundle` 返回；其`calibration_id`覆盖完整model、threshold、lineage和校准元数据。template同样从绑定prepared run的template role内部生成，`template_id`覆盖lineage；model-self result的`result_id`覆盖lineage。带sample-efficiency lineage的template若省略可信lineage，或进入toy/assessment/mismatch入口，会在模型构建、RNG和assessment payload访问前以`training_subset_binding_mismatch`拒绝。

## 10. 学习曲线批处理

M4以已发布且完整重验的`training-subsets`为前置，`sample-efficiency-plan` run先封存科学/执行计划。scientific batch ID不含路径或资源；execution plan ID另绑定resolved output与resources。full draw aliases只保留一个canonical cell，原alias数量仍记录在summary。

| Stage | 文件 | Schema | 关键绑定 |
|---|---|---|---|
| `sample-efficiency-plan` | `batch-plan.json` | `h4l-sample-efficiency-batch-plan-v1` | prepared、compact-freeze、training-subsets、旧G1 gate及T1 snapshot digest |
| `sample-efficiency-calibration` | `calibration.json` | `h4l-sample-efficiency-calibration-v1` | sealed plan、prepared、v2 model及M3 raw calibration lineage/digest |
| `sample-efficiency-common-grid` | `common-grid.json` | `h4l-sample-efficiency-common-grid-v1` | sealed plan、subsets和全部且仅calibration-success runs；participant集合、merge history、edges和grid ID可重算 |
| `sample-efficiency-template` | `template.json` | `h4l-sample-efficiency-template-v1` | 自己的raw calibration、共同grid、prepared和lineage |
| `sample-efficiency-inference` | `inference.json` | `h4l-sample-efficiency-inference-v1` | 共同grid、template、T1 evidence SHA、μ=1 model-self result及固定W68/AUC pointer |
| `sample-efficiency-batch` | `batch-ledger.json`,`batch-summary.json` | `h4l-sample-efficiency-batch-ledger-v1`,`h4l-sample-efficiency-batch-summary-v1` | 全部planned canonical cell、已发布stage facts、terminal/blocked stage、四项计数和所有直接run upstream |

校准行的 schema 为 `h4l-sample-efficiency-calibration-v1`；其envelope digest覆盖M3 `RawCalibrationBundle`。所有stage reader先重验manifest/file receipts和严格upstream path/multiplicity，再重放M3 calibration、共同grid、template及固定T1 Asimov计算。科学terminal保留已发布stage ID并将后续stage列入blocked；全部cell被complete或允许terminal解释时，外层manifest仍为complete，payload `batch_status`区分`complete`与`scientific_terminal`。binding、重复、缺失或未知错误不产生M5可消费ledger。

`--plan-only`不写目录、不训练且不构建pyhf/RNG；它会调用M2 reader，并可能只为重验M2摘要而重新解码verified MC train payload，绝不访问assessment/test。M4固定`workers=1`。`--clean`只可在任何research run或failure evidence产生前删除exclusive ownership marker与空staging；partial、failed、complete、link/reparse或含未知内容的目标保持不可变并拒绝清理。
