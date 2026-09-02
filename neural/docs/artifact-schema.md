# HiggsML Neural Artifact Schema Index

## 1. 地位与通用约束

本文是已实现 artifact 契约的导航与审计索引，不替代 sealed protocol：

- preprocess 字段与 golden：[`Preprocess Protocol V1`](preprocess-protocol-v1.md) §6–§8；
- development/OOF：[`Development Protocol V1`](development-protocol-v1.md) §5–§9；
- test-opening/receipt：[`Test-opening Protocol V1`](test-opening-protocol-v1.md) §3、§7。

所有 run 必须位于 `neural/runs/` allowed root 下的新路径，不能覆盖、复用或修改 frozen/failed run。
成功 manifest 最后发布并覆盖自身以外的全部文件 size/SHA-256。Canonical gzip 表同时记录 compressed
file SHA-256 和解压后 canonical CSV SHA-256。

## 2. Preprocess run

```text
runs/preprocess-<id>/
├── config.yaml
├── processed/mc_events.csv.gz
└── artifacts/
    ├── cutflow.json
    ├── mc_summary.json
    └── manifest.json
```

`mc_events.csv.gz` 的 29 列及顺序由 preprocess protocol §6.1 exact 固定。`cutflow.json` 按两个批准
MC samples 和固定 stage 记录 count/efficiency/yield；`mc_summary.json` 记录 per-sample 与 total
read/selected/split/weight/identity facts。

Preprocess manifest：

| Block | 最小审计内容 |
|---|---|
| header | `schema_version=1.0`、`status=success`、`run_type=preprocess`、`protocol_id`、UTC times |
| inputs | sample、DSID、logical path、SHA-256、size、tree/profile/unit、entry count |
| configuration | protocol/run-config path 与 SHA-256、chunk size、`full_read=true` |
| outputs | relative path、SHA-256、size、row count、canonical content SHA-256 |
| schema/counts | ordered columns、dtypes、per-sample 与 totals |
| reproducibility | software/packages/Git、platform、determinism、wall time、peak memory |

## 3. Development run

```text
runs/mlp-development-<id>/
├── config.yaml
├── artifacts/
│   ├── candidate_metrics.csv
│   ├── fold_metrics.csv
│   ├── qualification.json
│   ├── working_points.json
│   └── manifest.json
├── predictions/oof_scores.csv.gz
├── plots/
│   ├── auc_vs_lambda.png
│   ├── ks_vs_lambda.png
│   ├── oof_roc.png
│   └── oof_mass_sculpting.png
└── model/                       # eligible only
    ├── model.pt
    └── scaler.json
```

`candidate_metrics.csv` 每个 frozen lambda 一行；`fold_metrics.csv` 每个
`(target_lambda, fold_index, epoch)` 一行。`oof_scores.csv.gz` exact 列为：

```text
target_lambda,source_sample,source_entry,fold_index,label,m4l,
physical_weight,train_weight,score
```

`qualification.json` 使用 `development-qualification-v1`，status 只允许 `eligible` 或
`no_eligible_candidate`，并记录 selected lambda/final epochs、tie rule 和全部 candidates。
`working_points.json` 使用 `development-working-points-v1`，保存每个 candidate 的 loose/medium/tight
冻结工作点。

Development manifest 使用 `development-manifest-v1`，其 status 与 qualification 一致；它绑定 preprocess
manifest/table/canonical/protocol/run-config hashes、training protocol、全部 output、schema/counts、OOF
完整性、selection、environment/software/performance，并明确：real data 未读、held-out test 未开启、
authority environment 未由普通 development run 自证。

## 4. Test-opening run 与唯一 state

正常 test run：

```text
runs/mlp-test-<id>/
├── config.yaml
├── artifacts/
│   ├── test_metrics.json
│   └── manifest.json
├── predictions/test_scores.csv.gz
└── plots/
    ├── test_roc.png
    └── test_mass_sculpting.png
```

`test_scores.csv.gz` exact 列为：

```text
source_sample,source_entry,label,m4l,physical_weight,train_weight,score
```

`test_metrics.json` 使用 `test-metrics-v1`；status 只允许 `test_reproduced` 或
`test_nonreproduction`。`test-manifest-v1` 绑定 authorization reference、development/preprocess、
protocol/model/scaler/working points、outputs、schema/counts、metrics、environment/software/performance
和 no-feedback boundaries。

唯一 claim/terminal receipt 位于源 development run 的 `state/test_opening.json`：

- claim：`test-opening-state-v1`、`status=claimed`、`terminal_receipt=false`；
- claim 后失败：`status=failed_after_claim`、固定 stage/exit code、test feature opened 状态；
- 成功：status 等于 test 终态、绑定 test manifest SHA-256、`terminal_receipt=true`。

任何现存、空、partial 或不可解析 state 都永久拒绝重试。正常 test run 不复制 claim。

## 5. Failure run

普通 preprocess/development transaction 失败时，只发布 `failure.json`，不得同时含成功 manifest：

```text
status="failed"
error_type
exit_code
failed_at_utc
message
stage                         # 仅已分类阶段存在
```

Test-opening claim 后的 output failure receipt 只保留 sanitized stage/error type；详细且同样 sanitized
的 terminal state 保存在 development run。日志、receipt 与 state 不得泄漏 event row、identity、feature、
score 或 threshold value。

## 6. Authority comparator evidence

`run_authority_gate` 只在 locked native `osx-arm64` 执行，并以 exclusive create 写入独立路径。它固定从
`repository/neural/config/preprocess_protocol_v1.yaml` 读取 reviewed sealed protocol，不接受 runtime
protocol-path 注入：

```text
runs/authority-evidence-<id>/preprocess-authority.json
```

成功 evidence 包含 `schema_version=1.0`、`status=passed`、gate id、比较行数、resolved new run、
全部 approved lineage SHA-256，以及 structural/float/equal-nan predicates。Gate 读取新 run 的 canonical
table、MC summary 与 cutflow，但不读取或重新绑定新 run 的 manifest；manifest-last/output hash audit 是
独立前置。Evidence 文件不写回 preprocess run，也不由
`tests/golden/test_preprocess_authority.py` 自动生成。

M1-06 的 Markdown evidence record 另外为每条验证添加正交分类：`method`、`platform`、`data_scope`、
`authority` 和执行 `status`。只有 authority environment、zero-skip automated suite、full-MC preprocess/
golden 和 full development 全部通过，M1-06 才能关闭；未授权 `test_opening=not_run` 不阻塞关闭。
