# Development Protocol V1

## 1. 目的与权威边界

本文是 Sprint M1-04 的自包含实现协议，冻结 development-only 五折 OOF、工作点、资格判断、
最终拟合和发布行为。它只处理 MC preprocess run；所有结果只能称为 educational/technical
demo。M1-04 不执行 `open-test`，不产生 test score/metric/artifact，也不授权后续 test-opening。

Windows/synthetic 验证只证明实现机制，不替代由 `osx.yml` 恢复的 locked native
`osx-arm64` full-data gate。

## 2. 输入绑定与 held-out 隔离

命令只接受 `--input-run`、`--protocol` 和 `--run-dir`。输入 run 必须是 M1-02 成功发布且
不可变的 preprocess run，并在读取表内容前验证：

- run 及表、manifest、protocol/config snapshot 均为 ordinary file/directory，路径解析后位于
  允许根内且无 symlink/reparse-point 穿越；
- manifest schema/status、29 列 schema、行数和每个已声明文件 SHA-256 完整；
- manifest 绑定的 canonical CSV content SHA-256 与实际 gzip 解压内容一致；
- 输入 preprocess protocol/config 与本次 development manifest 以各文件 payload bytes 的 SHA-256
  引用，不复制或改写。

完整文件 bytes 可为完整性校验和 gzip 路由而顺序流过，但 held-out test feature token 不得被
解码为数值、物化进 DataFrame/array/tensor、送入 validator/scaler/fold/trainer/metric/plot 或
写入诊断。实现使用两阶段 reader：第一阶段只定位并解码 header 与每行 `split` token；第二阶段
只对 `split=train|validation` 行解析全部 29 列。遇到未知/空 split 在解析该行其他 token 前失败；
`split=test` 行只计数并跳过。测试必须用 poison row/parser 证明 test feature decoder 从未被调用。

`training/development_reader.py` 是 preprocess artifact 进入 development pipeline 的唯一允许入口；
任何 production/CLI 路径不得直接 `pandas.read_csv` 全表或公开调用 DataFrame validator 绕过它。
`ValidatedDevelopment` 的构造入口保持 module-private，persistent flow 只能接收 reader 返回的
validated object。Reader 内的 `DevelopmentInputBinder` 负责 input path/manifest/hash/schema，
逐 path component 拒绝 symlink 与 Windows junction/reparse point；`RunTransaction` 仍只负责
output。流式计算 file/canonical-content SHA-256 只把 bytes 送入 hash，不把 test feature token
定位、解码、typed parse 或物化，因此不构成 test feature value opening。

development 行合并原 `train` 与 `validation`，之后不保留二者的决策区别。解析完成后继续应用
M1-03 exact schema、dtype、finite、identity、feature 与 weight contract。输入表中的 test 行数只
作为未开启计数写入 manifest；不得记录其 identity、label、weight、feature 统计或 hash 子集。

## 3. Normal 与 Debug protocol blocks

`config/adversarial_mlp_protocol_normal.yaml` 在 M1-04 新增并密封以下 block；loader 继续执行递归
type-strict、mapping-order-strict、list-order-strict、missing/extra/value mutation rejection：

- `folding`: `count=5`、`algorithm=sha256_identity_v1`、UTF-8、NUL separator、first-8-byte
  unsigned big-endian、modulo 5；
- `working_points`: ordered `loose=0.50, medium=0.20, tight=0.10`；
- `qualification`: `auc_minimum=0.80`、`ks_maximum=0.10`、
  `signal_efficiency_strictly_greater=true`、`auc_tie_atol=1e-6`、`auc_tie_rtol=0`；
- `final_fit`: full-development scaler、`seed=42`、fold-best-epoch median、no early stopping；
- `development_artifacts`: exact output schemas and required paths from §9。

`config/adversarial_mlp_protocol_debug.yaml` 复用相同结构，只允许在 development 开始前修改
`qualification.auc_minimum` 和 `qualification.ks_maximum`。两项必须是 `[0.0, 1.0]` 内的有限
浮点数；其余字段继续与 Normal exact 一致。每个 Debug run 保存实际 YAML bytes、SHA-256 和
protocol snapshot。Debug 可以按其门槛生成 final model/scaler，但不能进入 held-out test-opening。

实现必须同步扩展 `src/training/config.py::_NORMAL_EXPECTED`，否则 strict comparator 应当并确实会拒绝
新增 YAML keys。这里的 SHA-256 fold hash 与 M1-02 preprocess split 的 BLAKE2b hash 是两个不同
职责的冻结算法，不得互换。

## 4. Stable fold assignment

Canonical identity 为 exact `(source_sample: str, source_entry: non-negative int64)`。哈希 payload
固定为：

```text
source_sample UTF-8 bytes || 0x00 || base-10 source_entry ASCII without sign/leading zero
```

计算 SHA-256，取 digest 前 8 bytes 按 unsigned big-endian integer 解释，`fold_index = value % 5`。
任何空 sample、负/非整数 entry、NUL sample、重复 identity 或 hash/fold 越界关闭式失败。
`source_entry=0` exact 编码为单个 ASCII `0`；“无 leading zero”只禁止 `00`、`007` 等冗余表示。
输入行重排不得改变 assignment。每个 identity exact 属于一个 validation fold；其余四折为
fitting。每个 candidate 必须按 protocol lambda 顺序、fold `0..4` 顺序运行；任一 fold 不满足
M1-03 label、weight 或 11-bin contract 时整个 run 异常失败，不跳过 candidate/fold。

## 5. OOF contract

每个预注册 lambda、每个 development identity 必须恰好产生一个 validation score。内部和发布前
均 exact 校验：candidate 集合/顺序、identity 集合、fold assignment、row count、唯一性、label、
mass/weight binding、score finite 且 `0 <= score <= 1`。缺失、重复、额外、跨 candidate/fold、
test identity 或字段漂移均失败。

发布 `predictions/oof_scores.csv.gz`，列顺序固定为：

```text
target_lambda, source_sample, source_entry, fold_index,
label, m4l, physical_weight, train_weight, score
```

行顺序固定为 protocol lambda 顺序，然后按 `source_sample` UTF-8 bytes、`source_entry` 升序。
同时记录 gzip file SHA-256 与解压 canonical CSV content SHA-256。

## 6. 指标与工作点

所有 metric 输入先 exact 校验一维、同长、finite、两类存在及正权重和：

- weighted OOF AUC：`sklearn.metrics.roc_auc_score`，`sample_weight=train_weight`；
- 概率型背景/信号效率与 ZZ mass KS：使用 `abs(physical_weight)`；signed weight 只用于产额
  audit，不进入 AUC、阈值、效率、KS 或资格布尔值；
- score cut inclusive：`selected = score >= threshold`。

每个 candidate、每个工作点只在 OOF `label=0` 上确定 threshold：按 score 降序稳定排序，累加
`abs(physical_weight)`，取 cumulative 第一次 `>= target * total` 的 score；应用 `>=` 必须保留
完整 score tie，因此 achieved background efficiency 可高于 target。随后在同一 candidate OOF 上
计算 achieved background efficiency 与 signal efficiency。

手算例：背景 `(score, abs_weight)=[(0.9,1),(0.8,1),(0.8,2),(0.2,6)]`，target `0.20`，
总权重 `10`。累计在第一条为 `1<2`，在第一条 `0.8` 为 `2>=2`，所以 threshold 为 `0.8`；
inclusive full tie 实际选择权重 `1+1+2=4`，achieved background efficiency 为 `0.40`。

ZZ `m4l` KS 比较该 candidate 的全部 OOF 背景与通过该工作点的 OOF 背景。两边均使用
`abs(physical_weight)` 构造右连续 weighted empirical CDF，并在两组 mass value 并集上取最大
绝对差；任一边为空或权重和非正失败，不返回伪造的 `0`。
该 absolute weight 运行时只从 OOF 的 signed `physical_weight` 列派生，不增加冗余持久列；实现
不得误用 signed physical weight 或 normalized `train_weight` 计算效率/KS。

## 7. Qualification 与选择

Normal candidate eligible 当且仅当以下 exact 条件同时成立：

- AUC `>= 0.80`；
- loose/medium/tight KS 各 `<= 0.10`；
- 每个工作点 `signal_efficiency > achieved_background_efficiency`；
- §5 OOF contract 完整。

Debug 使用其 protocol 文件中运行前声明的 `auc_minimum` 和 `ks_maximum` 替代上述两个数值，
效率和 OOF 完整性条件不变。已经发布的 Debug run 不得回改门槛或产物。

门槛比较不使用 epsilon。选择时先取 eligible candidate 的最大 AUC `best_auc`；只在选择层使用
`abs(candidate_auc - best_auc) <= 1e-6`，从该集合选最小 lambda。这一定义避免相邻链式 tie 的
非传递结果。每个 candidate 保存逐项 pass/fail 和稳定排序的 rejection reasons。

无 eligible candidate 是 exit 0 的正常终态 `no_eligible_candidate`：仍发布全部 OOF/metric/
working-point/plot/manifest 证据，但不得创建 `model/`、`model.pt`、`scaler.json`、test artifact
或可被 M1-05 解释为 test-opening 资格的占位文件。

Debug run 即使达到 `eligible` 并生成模型，也不能被 M1-05 解释为 test-opening 资格。

## 8. Eligible final fit

若存在 selected candidate，先把五个 fold `best_epoch` 排序，取第三个整数作为
`final_epochs`；五个整数的中位数本身为整数，不执行 banker rounding。最终 scaler 只在全部
development 15 features 上以 M1-03 float64/population-variance 规则拟合。

以 seed 42 重新初始化完整 9,228 参数模型和 AdamW，使用全部 development、相同 batch/shuffle、
lambda schedule 与 loss contract，恰好训练 `final_epochs`；不创建 validation、AUC checkpoint 或
early stopping。发布的是最后 epoch 的 classifier/adversary deep CPU float32 state，连同 protocol
SHA、feature tuple、selected lambda、seed、final epochs 与 scaler binding。最终拟合不得改变
已冻结 OOF metric/threshold/qualification。

## 9. Transaction 与 artifact schema

`RunTransaction` 负责 allowed-root、不可覆盖、staging、失败收据和最终原子发布。Manifest 最后写入
并覆盖所有发布文件（manifest 自身除外）的 SHA-256。正常终态：

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
model/model.pt       # eligible only
model/scaler.json    # eligible only
```

`fold_metrics.csv` 每行是一个 `(target_lambda, fold_index, epoch)`；fold summary 在该 fold 的每个
epoch row 重复。列顺序 exact 为：

```text
target_lambda, fold_index, fold_seed, epoch, lambda_effective,
train_cls_loss, train_adv_loss, train_total_loss, validation_weighted_auc,
is_best, duration_seconds, events_per_second,
best_epoch, best_validation_weighted_auc, epochs_completed, stopped_early
```

`candidate_metrics.csv`
每行一个 protocol candidate，列含 AUC、三个工作点的 threshold/target/achieved background
efficiency/signal efficiency/KS、eligible 和 rejection reasons JSON。M1-04 新增独立
`canonical_json_bytes`，并只对 `qualification.json`、`working_points.json` 与 development
`manifest.json` 使用 UTF-8、`sort_keys=True`、`separators=(",", ":")`、终止 LF、禁止
NaN/Infinity；M1-02 既有 indented `json_bytes` helper 与历史 bytes 不修改。CSV 使用固定列序、
UTF-8、LF、稳定 float repr。

`qualification.json` 记录 schema/status、selected lambda 或 null、每 candidate pass/fail/reasons、
tie rule 和最终 epoch 或 null；`working_points.json` 记录每 candidate 三工作点，eligible 时另绑定
selected candidate。Manifest 记录 input/protocol/config/output hashes、schema/counts、candidate/fold/
epoch 数、OOF 完整性、deterministic environment、wall time、peak memory、正常终态与明确边界：
real data not read、held-out test not opened、`open-test` not run。

异常终止使用 `InputBindingError`/run-path/internal error 的稳定 exit code，并保留 failure receipt；
异常 run 不得含成功 manifest。日志和失败收据不得包含 event row、feature value 或 test identity。

## 10. 最小测试门

- sealed M1-04 protocol block 的 missing/extra/type/order/value mutation；
- fold hash known vectors、row reorder stability、五折 coverage、identity/test contamination refusal；
- OOF missing/duplicate/extra/nonfinite/out-of-range/wrong-fold/wrong-field rejection；
- weighted AUC、inclusive full-tie thresholds、absolute-weight efficiency 与 weighted KS 手算；
- AUC/KS 等号通过、signal efficiency 等号失败、best-AUC-relative `1e-6` tie-break；
- five candidates × five folds 完整调用，单 fold 异常使 run 失败且不删减候选；
- final epoch median、full-development-only scaler、fixed-epoch/no-early-stop final fit；
- eligible/no-eligible/abnormal 三终态布局、manifest/hash/canonical gzip schema；
- poison test row 证明 test feature decoder、validator、trainer、metric 与 plot 从未收到 test 值；
- CLI usage/exit mapping、non-overwrite/allowed-root、focused/full pytest、pip check、两个 CLI help 和
  `git diff --check`。

M1-04 不以普通 Windows CLI smoke 运行 25-fold full-data training；权威 full-data gate 留在 M1-06。
