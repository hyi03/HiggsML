# Test-opening Protocol V1

## 1. 目的、授权与边界

本文是 Sprint M1-05 的自包含实现协议，冻结 held-out MC test-opening 的输入绑定、
可选原子 claim、冻结评价、receipt 和 test run 发布行为。

命令为：

```text
higgsml-test --train-run <eligible-frozen-run> --run-dir <new-test-run> [--authorization-reference <non-empty-audit-reference>]
```

`authorization-reference` 是可选参数。省略时不创建 development claim，manifest 中记录
`authorization_reference: null`，同一 development run 可使用不同的新输出目录重复评价。
提供时启用一次性 claim，且值必须 `strip()` 后非空；strip 后的 Unicode code point 数至多 256，
并拒绝 Unicode category `Cc`/`Cf`（包括 C0/C1、DEL、format/bidi controls）。它只保存公开、
非敏感的外部批准审计引用（如工单号）；case-insensitive 的 `password|passwd|api[ _-]*key|secret|
token|credential` 后跟可选空白及 `:`/`=` 的 credential assignment 形式必须拒绝。该拒绝仅是最小
hygiene，不能证明任意字符串不含秘密。它不是密码学证明，也不能由软件自行判断
用户是否真实批准。调用者仍必须在命令外取得明确授权。fixture 测试固定使用
`synthetic-fixture-only`，它不得被解释为权威 test-opening 授权。命令不提供 `--force`、
`--retry`、threshold、lambda、model 或 metric override。

所有输出只能称为 educational/technical demo。Windows/synthetic 机制验证不替代由 `osx.yml`
恢复的 locked native `osx-arm64` 权威 gate。

## 2. 输入与 pre-claim 顺序

命令必须按 `neural/AGENTS.md` 从 `neural/` 运行，因此当前工作目录的 `runs/` allowed root 即
`neural/runs/`。`development-run` 与 `run-dir` 均必须位于该 root 下；逐 path
component 拒绝 symlink、junction/reparse point、`..` 与 resolved containment escape。输出 run
必须不存在。pre-claim 只能执行路径、manifest、artifact bytes/hash/schema 与配置解析，不得解码
held-out test feature token。

按以下顺序 fail closed：

1. 验证 test output `RunTransaction` target 合法且不存在；仅创建唯一 staging，不发布。
2. 仅绑定 ordinary、无 link/reparse 的 development run path。一次性模式若发现任何
   `state/test_opening.json` 已存在，立即按 exit 5 拒绝；可重复模式不检查该 state。一次性模式的
   cheap probe 不读取 manifest/artifact，`O_CREAT|O_EXCL` 仍是并发竞争的权威 guard。
3. 读取 development canonical manifest bytes，exact 验证 manifest schema/version、
   `run_type=development`、`status=eligible`、Normal protocol ID、
   selected lambda/final epochs、boundary flags、schema/counts/OOF completeness。
   Debug protocol 即使状态为 `eligible` 且存在模型，也必须在 claim 和 test feature decode 前按
   exit 5 拒绝。
4. 遍历 manifest `outputs`，验证 exact path set、ordinary file、size 与 SHA-256；eligible-only
   `model/model.pt`、`model/scaler.json` 必须存在。manifest 自身 SHA-256 单独计算。
5. 解析并相互绑定 `config.yaml`、`qualification.json`、`working_points.json`、scaler 与 model
   payload：protocol SHA、selected lambda、final epochs、15-feature tuple、scaler 必须 exact 一致。
   Runtime qualification constants、feature tuple 与 working-point order 的唯一来源是 hash-bound
   development config raw protocol snapshot 及 working-points；禁止读取当前 repo protocol。
6. 从 development config 的 `input_run` 定位原 preprocess run，仅复用 M1-04 reader 的 path、
   manifest/output/hash/schema helpers，不得调用 development row decoder。preprocess run 使用同一
   `runs/` root：absolute 必须 contained；relative `runs/...` 相对 allowed-root 的父目录
   `neural/`，例如 `runs/preprocess-1` 解析为 `neural/runs/preprocess-1`；其他 relative path 相对
   allowed root，例如 `preprocess-1` 也解析为 `neural/runs/preprocess-1`。最后再次验证 resolved
   containment。其 manifest/table/canonical-content SHA 必须与 development
   manifest `input` block exact 一致。此时允许完整文件 bytes 为完整性 hash 顺序流过，但仍不得
   decode test feature。
7. 一次性模式再次 cheap probe `state/test_opening.json`，然后才尝试原子 claim；最终唯一性由
   `O_CREAT|O_EXCL` 决定。可重复模式完成输入绑定后直接进入 test-only reader。

任一步失败均不得读取 test features；必须调用 transaction abort path 删除 staging，且不得发布
failure run。一次性模式只有 claim 后异常才发布 failure run；可重复模式由输出 transaction 记录失败，
不写 development state。

## 3. 可选原子 claim 与不可重试状态机

本节只适用于提供 `authorization-reference` 的一次性模式。省略参数时不创建、读取或更新
`state/test_opening.json`，因此 development run 不被占用；每次调用仍必须使用不存在的新
test run 路径。

Claim 固定写入 development run 的 `state/test_opening.json`。先以并发安全的
`mkdir(exist_ok=True)` 创建或复用 `state/`，再逐 component 验证 ordinary/no link/reparse。
claim 文件使用 same-filesystem `O_CREAT|O_EXCL` 原子创建；并发调用只有
一个成功，其他调用返回 stable qualification refusal exit code 5。

初始 claim canonical JSON 至少包含：

- `schema_version=test-opening-state-v1`
- `status=claimed`
- development manifest SHA-256、resolved logical test run path、resolved output staging path、
  authorization reference
- `claimed_at_utc`
- `test_features_opened=false`
- `terminal_receipt=false`

若本次新建 `state/`，必须先在 parent development-run directory 对该新目录项执行 POSIX directory
fsync 或 Windows 等价 durable metadata flush。claim 写完后必须 flush + file fsync，并对 `state/`
执行同等 directory durable flush；全部成功后才允许 test decode。terminal temp 同样 flush/fsync，再 `os.replace`
并 durable flush directory。claim 创建后永不删除，任何现存 state（包括 empty、partial、
unparseable，以及 `claimed`、`test_reproduced`、`test_nonreproduction`、
`failed_after_claim`）都永久拒绝后续调用。正常完成或捕获到的 claim 后异常通过同目录临时文件
加 `os.replace` 原子更新为 terminal receipt；不得先删除 claim。硬崩溃/断电可能留下
`status=claimed, terminal_receipt=false`；不可解析 state 也按相同 indeterminate 语义永久不可重试。

若 `O_EXCL` 已创建 claim、但 claim file/directory durable flush 失败，固定 stage
`claim_durability`、exit 4；不得 decode test，尽力发布 sanitized failure run 与
`failed_after_claim` terminal receipt。若 terminalization 也不能 durable 完成，现存 partial/claimed
state 仍永久拒绝重试。

Claim 后失败 receipt 固定包含 `schema_version`、`status=failed_after_claim`、development manifest
SHA-256、resolved test run/staging path、authorization reference、`claimed_at_utc`、failure stage、
error type、stable exit code、failed time、是否已经开始 test feature decode、failure run 是否成功
发布和 `terminal_receipt=true`。不得记录 event row、identity、feature value、score 或阈值值。
成功 receipt 固定保留 `schema_version`、development manifest SHA-256、resolved test run/staging
path、authorization reference、`claimed_at_utc`，并记录与 test run 相同的 terminal status、test
manifest SHA-256、完成时间、`test_features_opened=true`、`terminal_receipt=true`。

Claim 记录 output staging logical path。硬崩溃遗留的 hidden `.tmp` staging 永不自动发布；只能经
另行人工授权清理，且清理绝不允许重试 opening。

## 4. 输入绑定及可选 Claim 后的 test-only reader

Claim 成功后才允许第二阶段读取 preprocess gzip。Reader 顺序验证 exact 29-column header，并对
每行只先定位/ASCII decode `split`：

- `train|validation`：不解析、物化或记录其他 token；
- `test`：才解析完整 29 列进入 test frame；
- unknown/empty：解析其他 token 前失败。

Test frame 必须同时匹配 preprocess `counts.totals.split_counts.test` 与 development
`counts.held_out_test_rows_not_opened`，且两者先 exact 相等；exact 校验 29 列、dtype、finite、
`split` 全为 `test`、canonical identity 唯一、label、`105 <= m4l <= 160`、weight 与 15-feature
whitelist，禁止 clip。Classifier tensor 只能由固定 15 features
构造；`m4l`、identity、provenance、split、physical/train weight 都不得进入 classifier。
每个 label class 的 `train_weight` 总和及 `abs(physical_weight)` 总和必须严格大于零；否则指标
分母未定义，固定为 post-claim `test_frame_binding` exit 3。该 total-class binding failure 不同于
§6 中 total class 有权重但冻结阈值选中零背景权重的正常 nonreproduction。

## 5. 冻结模型、scaler 与评分

唯一 scientific source 是 development config 的 hash-bound raw protocol snapshot，不得读取当前
repo protocol。使用 `torch.load(..., map_location="cpu", weights_only=True)` 加载 sealed payload；拒绝额外/缺失
payload keys、非 CPU/float32 state、shape/key 漂移、protocol SHA、feature tuple、selected lambda、
seed、epoch 或 scaler binding 漂移。以 fresh `AdversarialMLP` exact 加载 classifier/adversary state，
`eval()` 后只用冻结 scaler transform test 的 15 features 并产生 finite `[0,1]` sigmoid score。

严禁调用 `train_fold`、`train_fixed_epochs`、optimizer、backward、scaler fit、threshold selection、
candidate selection 或 early stopping。测试必须用 spy 证明这些路径未调用。

## 6. 冻结 test 指标与结论

Test weighted AUC 使用 `train_weight`。每个 loose/medium/tight 工作点只读取 selected development
candidate 已冻结的 `threshold` 与 target；应用 `score >= threshold`，以
`abs(physical_weight)` 计算 achieved background/signal efficiency 和 selected-vs-all background
weighted `m4l` KS。不得在 test 上重新选择或调整 threshold。

只有每个预期 test identity 恰好产生一次 finite `[0,1]` score、行数与两处 manifest count exact
相等且 schema/order/hash 完整的有效评价才能产生科学终态；违反 test-frame binding 时 exit 3，
model 产生非有限/越界 score 时 stage=`model_scoring`、exit 70，publication 失败时 exit 4，均为
`failed_after_claim`，不得解释为科学非复现。在有效评价上，`test_reproduced` 当且仅当满足冻结
qualification predicates：AUC `>=0.80`、三个
KS 各 `<=0.10`、各工作点 signal efficiency 严格大于 achieved background efficiency。比较不
使用 epsilon。仅冻结 scientific predicates 不满足时结论为 `test_nonreproduction`，保存稳定
rejection reasons；两种有效科学终态均 exit 0，且
都不会触发训练、调参、候选扩展、阈值变化或 development artifact 修改（唯一 state receipt 除外）。

若某个冻结阈值在 test 上选中的背景绝对权重为零，则 achieved background efficiency 固定为
`0.0`，该工作点的 KS 保守记为 `1.0`；这属于正常的 `test_nonreproduction`，不是 input binding
错误；point 记录 `empty_selected_background=true`，reasons 增加
`<working-point>_empty_selected_background` sentinel。不得在 test 上降低阈值以制造非空样本。

## 7. Test run artifact schema

正常 test run exact layout：

```text
config.yaml
artifacts/test_metrics.json
artifacts/manifest.json
predictions/test_scores.csv.gz
plots/test_roc.png
plots/test_mass_sculpting.png
```

`test_scores.csv.gz` exact 列顺序：

```text
source_sample,source_entry,label,m4l,physical_weight,train_weight,score
```

行按 `source_sample` UTF-8 bytes、`source_entry` 升序；同时记录 gzip file SHA-256 与解压
canonical CSV content SHA-256。`test_metrics.json` 与 test manifest 使用 M1-04
`canonical_json_bytes`。metrics 记录 status、frozen selected lambda、weighted AUC、三个 frozen
working points、pass/fail/reasons 和明确 no-feedback boundaries。

Manifest 固定 `schema_version=test-manifest-v1`、`run_type=test_opening`，`authorization_reference`
在省略参数时为 `null`，最后写入并覆盖自身以外
所有发布文件的 size/SHA-256，并记录：development
manifest/hash/selection、preprocess table hashes、authorization reference、protocol/model/scaler/
working-point hashes、schema/counts、test conclusion、deterministic environment、wall time、peak
memory 与 boundaries。`boundaries` exact 包含 `educational_technical_demo=true`、
`real_data_read=false`、`held_out_test_opened=true`、`open_test_run=true` 与
`authority_environment_verified`（仅 locked native authority gate 可为 true；Windows/synthetic
固定 false）。正常 run 不包含 claim 副本；唯一 opening state 只在 development run。

捕获到的 claim 后异常由 `RunTransaction` 发布 sanitized `failure.json`，只含 stage/error type，
不得写 raw `str(exc)` 或 test row/value/identity/score/threshold，且不得包含成功 manifest。若 output
transaction 自身无法发布，development receipt 仍必须记录 `failed_after_claim` 和审计边界。
若正常 test run 已原子发布、但 terminal state replace 或 durable directory flush 随后失败，则命令
返回 exit 4；现存 state 按 `claimed`/indeterminate 永久不可重试，已经发布的 test run也不得覆盖或
删除。软件不得把该状态谎报为完整成功。

## 8. Stable exit codes 与 CLI

- `0`：`test_reproduced` 或 `test_nonreproduction`
- `2`：argparse usage，包括缺少 required authorization flag
- `3`：input/schema/hash/protocol/model binding failure
- `4`：output transaction/publish 或 claim/terminal state-receipt durability failure
- `5`：ineligible、已有 claim、authorization value strip 后为空等 qualification refusal
- `70`：claim 后 model scoring/numerical 或其他 unexpected internal failure

Claim 后 test-frame binding failure 固定 exit 3；output transaction/publish failure、
`claim_durability` 与 `terminal_receipt` 固定 exit 4；model scoring/internal failure固定 exit 70，
receipt 记录同一 code。

CLI 日志只记录阶段、terminal status 和 run path；不得输出 test row/value/identity/score。
`terminal_receipt` exit 4 必须明确记录 output 可能已经发布且需要 manual audit，不能输出成功提示。

## 9. 最小测试门

- 无资格/no-eligible、missing/extra artifact、任一 byte/hash/schema/selection/scaler/model drift 在
  claim 和 test decode 前拒绝；
- absolute/relative traversal、symlink/junction/reparse、existing output 拒绝；
- `O_EXCL` 并发竞争只有一个 claim，existing/claimed/terminal state 永久拒绝；
- claim/receipt durability injection、empty/partial/unparseable state 永久拒绝；
- claim-only crash-boundary 模拟保留 `claimed` 并证明永久拒绝；捕获异常形成
  `failed_after_claim`，并区分 test 未读/已读；
- poison development row 证明 test-only decoder 不读取 development feature；unknown split 先失败；
- frozen model/scaler/threshold exact 使用；spies 证明 trainer/optimizer/scaler fit/threshold selection
  未调用；
- test score/order/hash schema、reproduced/nonreproduction、success/failure layout 与 manifest-last；
- empty-selected-background 的 efficiency `0.0`、KS `1.0` 与 sentinel reason 形成正常非复现；
- 省略 authorization flag 可执行并可重复；显式 blank、超过 256 Unicode code points、credential
  assignment、Unicode `Cc`/`Cf` authorization value exit 5；post-claim 3/4/70 exact mapping；
- 已发布 output 后 terminal receipt replace/flush 注入失败：exit 4、state 永久不可重试、output 不覆盖；
- development tree 除唯一 state file 外不变；failure/log/state poison assertions 不含 test value；
- fixture-only CLI smoke、focused/full pytest、pip check、两个 CLI help、`git diff --check`；
- 所有收尾证据明确未运行权威 `open-test`、未读取真实数据，Windows/synthetic 非权威。
