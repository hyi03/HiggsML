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

## 6. 规划 artifact

**最新方案规划中。** ResearchProtocol、五角色 research dataset、MELA、conditional-CDF calibration、共同二维 templates、workspace、fit/interval 和 pseudoexperiment artifact 尚无生产 schema。其 namespace、lineage 与失败状态须独立设计，见 [`research-software-design.md`](research-software-design.md)。

**需要外部或权威验证。** 任何未来 schema 只有通过合成数值测试、独立参考和锁定平台重放后，才可支持方案中的科学结论。
