# HiggsML Neural Artifact Schema v2

本文描述当前按数据集隔离的产物；历史 v1 字段见相应历史协议文档。精确字段和列序以版本化协议及 reader 为准。所有 run 使用 `neural/runs/<dataset>/<new-run>/` 新路径，冻结和失败 run 不可覆盖。

## 通用绑定

`dataset_binding` 包含数据集名称、定义修订与字节摘要、release、collection、profile/science 摘要、事件身份策略及两个成员的受控元数据。下载定义在 `config/datasets/`；科学规则、profile 独立封存。名称不能重标记其他数据集的文件或模型。

成功 manifest 最后发布，列出自身以外的产物文件大小与 SHA-256。CSV gzip 另记录解压后 canonical 内容摘要、行数。snapshot 保存协议及绑定，development snapshot 还保存精确训练协议文本以校验 Debug 字节。

## Preprocess

```text
config.yaml
processed/development_events.csv.gz
processed/test_events.csv.gz
artifacts/cutflow.json
artifacts/mc_summary.json
artifacts/manifest.json
```

Manifest 为 `schema_version: "2.0"`、`run_type: preprocess`、`protocol_id: higgsml-preprocess-v2`。记录 inputs、configuration、dataset_binding、outputs、schema、counts、software、platform、determinism、performance。

两张表使用 `config/preprocess_protocol_mass_window.yaml` 的相同 31 列；原 29 列加 `source_file_id`、`event_group_id`。development 仅含 train/validation，test 仅含 test。来源行键为 file ID + source entry；事件分组字符串为 `channelNumber:eventNumber`。新身份字段、质量、权重、标识符均禁止进入 15 维模型输入。

Development reader 校验 manifest 和非 test 产物，只解码 development 分区；不会打开、计算哈希或 stat test 文件。test 文件的描述符此时只作为冻结的预期值，不能声称已重新验证。

## Development

```text
config.yaml
artifacts/candidate_metrics.csv
artifacts/fold_metrics.csv
artifacts/qualification.json
artifacts/working_points.json
artifacts/manifest.json
predictions/oof_scores.csv.gz
plots/auc_vs_lambda.png
plots/ks_vs_lambda.png
plots/oof_roc.png
plots/oof_mass_sculpting.png
model/model.pt                  # eligible only
model/scaler.json               # eligible only
```

Manifest 使用 `development-manifest-v2`，config 使用 `development-config-v2`。记录上游分区与 manifest 摘要、协议、数据绑定、OOF 完整性、候选资格、环境及性能；`statistics` 为 development 各类、fold、背景质量 bin 的计数、负权重数、绝对权重和、平方和与有效样本量。

OOF 精确列序：

```text
source_file_id,event_group_id,target_lambda,source_sample,source_entry,fold_index,label,m4l,physical_weight,train_weight,score
```

资格与工作点算法未变，分别保留 `development-qualification-v1` 和 `development-working-points-v1` schema。状态为 `eligible` 或 `no_eligible_candidate`；后者不发布 final model。Final payload 为 `adversarial-mlp-final-v2`；scaler 为 `fold-local-scaler-v2`，携带同一绑定。模型、scaler 和阈值不可跨数据集使用。

## Test-opening

```text
config.yaml
artifacts/test_metrics.json
artifacts/manifest.json
predictions/test_scores.csv.gz
plots/test_roc.png
plots/test_mass_sculpting.png
```

Manifest 为 `test-manifest-v2`，记录数据绑定及 development/preprocess/model/scaler/working-points lineage。指标保留 `test-metrics-v1`；正常终态为 `test_reproduced` 或 `test_nonreproduction`。预测列为 source_file_id、event_group_id 及原 source_sample、source_entry、label、m4l、physical_weight、train_weight、score，精确顺序以 test reader 常量为准。

完成数据集与资格 gate 后才校验/解码 test 分区。提供 authorization reference 时，在 development 的 `state/test_opening.json` 建立 `test-opening-state-v2` 一次性 claim；成功或 `failed_after_claim` 均为不可重试终态。已有空、partial 或不可解析 state 也拒绝重试。省略 reference 时保持原有不同新输出目录的可重复评价模式。

## 失败及独立验证

事务 `failure.json` 包含失败类型、退出码、时间、消息、可用的阶段及 dataset_binding；不同时发布成功 manifest。test claim 后消息经过清理，禁止泄漏事件特征、预测及阈值。

Authority 使用 `authority-development-v2`，仅在 native osx-arm64 上比较同数据集 development 特征及结构计数，要求独立登记且摘要固定的 reference。`config/validation/registry.json` 当前为空，因此不会把首次输出自认证为 golden。test 特征比较未纳入此 gate。

实际验证范围见 [dataset-v2-verification.md](dataset-v2-verification.md)，命令见 [dataset-v2-runbook.md](dataset-v2-runbook.md)。

## Explicit debug diagnostics

Explicit `higgsml-train --debug` publishes `debug_diagnostic` in the development
manifest and qualification artifact, with a final model/scaler. Candidate
eligibility and rejection reasons remain unchanged. When none qualifies,
`tie_rule.reference` is `maximum_oof_auc`; otherwise it is `maximum_eligible_auc`.
Normal-mode artifact schemas and terminal states remain unchanged.

`higgsml-test --debug` publishes `debug_diagnostic` in metrics, manifest and any
successful one-shot state receipt. Its config and metrics contain `debug: true`,
and manifest boundaries contain `debug: true`. Metrics retain the original
qualification failure reasons and frozen working points; this status never
asserts formal test reproduction. The original development artifacts are
immutable (apart from the existing optional state claim).

## Inclusive schema 扩展

正式无窗的预处理 schema 为 3.0，原 31 列移除 `train_weight`。development-config、development-manifest、adversarial-mlp-final 使用 v3 内部 schema；test-manifest 为 v3、test-metrics 为 v2。OOF/test 表使用 `metric_weight = abs(physical_weight)`。新增科学状态、报告分箱、分箱诊断及统计不足产物详见 [inclusive 协议手册](../research/inclusive-protocol.md)。旧 schema 的含义不变。
