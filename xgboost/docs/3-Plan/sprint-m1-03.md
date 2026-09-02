# Sprint M1-03

## 1. Sprint 目标

覆盖 [FR-001](../1-Requirement/FR-001-angular19-xgboost-refactor.md)，实现
`higgsml-xgboost develop`：只消费 development 数据，完成 XGBoost 五折 OOF、冻结工作点、
资格门控及 eligible-only 最终模型发布。

核心目标：

- 等价迁移现有 Angular19 XGBoost 训练行为；qualification 是新增的发布生命周期门，
  不改变候选训练结果。
- 将资格证据和模型发布绑定到不可变 run。
- 证明 development 阶段不打开 held-out test 文件。

## 2. 前置依赖

- [FR-001](../1-Requirement/FR-001-angular19-xgboost-refactor.md) 与
  [批准设计](../superpowers/specs/2026-09-01-xgboost-refactor-design.md) 已批准。
- `sprint-m1-01`、[sprint-m1-02](sprint-m1-02.md) 已完成并提交；M1-02 的
  [document review confirm](../4-Reviews/sprint-m1-02-review-confirm.md) 与
  [code review confirm](../4-Reviews/sprint-m1-02-code-review-confirm.md) 是上游消费合同。

协同说明：只消费 preprocess manifest 中声明的 development artifact。

## 3. 纳入范围

- `src/training/dataset.py`
- `src/training/model.py`
- `src/training/folds.py`
- `src/training/trainer.py`
- `src/training/evaluation.py`
- `src/training/qualification.py`
- `src/cli/xgboost.py` 的 `develop`
- development artifacts、plots 和测试
- `config/xgboost_protocol_v1.yaml` 只做 byte-for-byte 消费，不修改其内容；未来科学行为
  变化必须新建 protocol 版本并重新评审。

## 4. 暂不纳入范围

- Held-out test-opening（M1-04）。
- 历史代码删除（M1-05）与最终归档（M1-06）。

原因：先冻结 development 决策和模型发布合同。

## 5. 工作范围

### 5.1 Dataset 与训练核心

目标：等价迁移 frame 校验、fold、权重、候选 fit 和 OOF。

实现任务清单：

- [x] 只接受 M1-02 已提交的固定、有序且无重复的 32 列 schema：19 项模型特征，加
  `m4l, label, split, physical_weight, train_weight, channelNumber, eventNumber, runNumber,
  mcWeight, xsec, kfac, filteff, sum_of_weights` 13 项 metadata；校验类型、有限性、
  development split、identity 唯一性和 forbidden fields。`m4l` 是禁止进入模型的
  metadata，同时是 qualification 的 ZZ 质量 KS 必需输入。
- [x] Fold 严格迁移为
  `blake2b(f"task4b-fold:{channel}:{event}", digest_size=8)` 的 big-endian 整数 `% folds`；
  不做 stratified assignment，分配后逐 fold 验证同时包含 label 0/1，并证明五折互斥、
  并集覆盖全部 development 行。
- [x] XGBoost `sample_weight` 不读取 CSV 的 `train_weight`；每个 fitting subset 和最终
  development fit 均从 `physical_weight` 调用 class-balanced 规则重算：以
  `abs(physical_weight)` 为基础，使 label 0/1 各自总权重为 `len(frame)/2`，整体均值为 1。
  CSV `train_weight = abs(w)/mean(abs(w))` 只作为 preprocessing 审计字段。
- [x] 迁移 early stopping、进度和唯一 V1 candidate。选择继续按 mean weighted AUC 的
  既有语义，但 V1 不新增运行时网格或多候选 tie-break；`objective="binary:logistic"`、
  `eval_metric="auc"` 作为 legacy authority 的 code-fixed 参数，不写入或修改 protocol V1。
- [x] 每个 development 事件仅由未包含它的 fold 模型给出一个有限 OOF score；最终树数为
  `max(1, int(np.rint(np.median([best_iteration + 1 for fold in selected.folds]))))`，其中
  `np.rint` 保持 half-to-even。

测试要求：

- [x] 对照设计 §7.2 指定的 `scripts/higgsml.py`、`src/experiment_config.py`、
  `src/experiment_runner.py`、`config/experiment_training.yaml`、`ANGULAR19_PROFILE` 和
  `src/angular5.py`，完成旧/新 fold、class-balanced weight、候选结果和预测 golden 对比。
- [x] 复用 `sprint-m1-01.md` §5.1 与
  `tests/golden/test_refactor_characterization.py` 的 `RTOL=ATOL=1e-12`；整数、identity、
  split、fold、schema、列顺序和终态必须精确相等，不在结果产生后修改容差。
- [x] 为 final-tree median 恰为 `x.5` 的 fixture 锁定 `np.rint` half-to-even。
- [x] 每个 development 行恰好一个有限 OOF 分数。

### 5.2 工作点与 qualification

目标：冻结 OOF ZZ 工作点并执行全部门槛。

实现任务清单：

- [x] Weighted fold/OOF AUC 使用 `abs(physical_weight)`，既不用 signed weight，也不用
  CSV `train_weight`。
- [x] 工作点只使用 development OOF ZZ（label 0）的 score 与 `abs(physical_weight)`：按
  score 高到低 stable 排序，累计绝对权重首次达到 `target * total_weight` 时取该 score，
  最终 `score >= threshold` 完整保留同分 tie；不得使用 signal 或 test 反推阈值。
- [x] 每个工作点的 KS 比较 inclusive ZZ 与 `score >= threshold` selected ZZ 的 `m4l`；
  向 `weighted_ks_distance` 传现有 signed `physical_weight` 并保留其内部取绝对值语义。
  每类效率为 selected `abs(physical_weight)` 总和除以 inclusive 同类绝对权重总和。
- [x] 新增 qualification 生命周期门，且仅当以下四项全部成立才为 `eligible`：weighted OOF
  AUC `>= qualification.minimum_weighted_oof_auc`（V1 为 0.80）；loose/medium/tight 三个
  ZZ `m4l` KS 全部 `<= qualification.maximum_background_ks`（V1 为 0.10）；当
  `qualification.require_signal_efficiency_above_background` 为 true 时，每个工作点 signal
  efficiency 严格大于 achieved background efficiency；OOF 完整、有限且每个 development
  event 恰好一次。
- [x] 任一门不满足时终态为正常的 `no_eligible_candidate`；门控不得改变候选训练结果。
- [x] Eligible-only 训练并发布最终模型。

测试要求：

- [x] AUC/KS 等于门槛、效率严格不等式、缺 ZZ、不完整/重复/非有限 OOF、合格和不合格
  fixture；golden 锁定旧/新阈值、完整 tie、KS 和效率。

### 5.3 Develop CLI 与 artifacts

目标：发布完整 development run。

实现任务清单：

- [x] Develop CLI 只允许 `--input-run --protocol --run-dir`；不提供 `--overwrite`，不允许
  覆盖特征、seed、fold、XGBoost 参数、候选、工作点或 qualification 门槛。
- [x] 在读取 CSV 前校验并绑定上游 preprocess run 路径、preprocess manifest SHA-256、
  `development.csv.gz` 的 compressed/canonical 双重 SHA-256，以及上游 protocol/run-config
  identity；拒绝 hash 漂移、未知 schema/layout、symlink 和既有/非直接 `runs/<id>` 输出。
- [x] 发布设计 §10.1 的 development layout：`config.yaml`；
  `artifacts/{candidate_metrics.csv,fold_metrics.csv,qualification.json,working_points.json,
  manifest.json}`；`predictions/oof_scores.csv.gz`；`plots/`；以及仅 eligible 时出现的
  `model/model.json`（XGBoost JSON）。M1-03 无论 eligible 与否都不创建
  `state/test_opening.json`；该 claim 只属于 M1-04 `open-test`。
- [x] OOF CSV 固定为有序八列 `channelNumber, eventNumber, split, label, physical_weight,
  m4l, development_fold, oof_score`。Development manifest 延续 M1-02 的 schema/run type/
  status/protocol/code/software/input/output/count/schema/hash，并增加 upstream run、candidate、
  selected candidate、working points、qualification 与 `test_opened: false` 绑定。
- [x] 通过文件访问 spy/deny fixture 暴露 test CSV.GZ 路径，证明 develop 不对其执行任何
  open/read，只打开 manifest 声明的 development artifact。

测试要求：

- [x] 输入/manifest 篡改、occupied output、非法科学覆盖、eligible/no-eligible、test deny 和
  eligible-only model CLI 集成测试。

## 6. 验收标准

- Development 不读取 test CSV.GZ。
- OOF、fold、工作点和资格证据完整且可审计。
- 不合格 run 无任何 `model/` 或 `model/model.json`；development manifest 明确
  `test_opened: false`，且本 Sprint 不创建 `state/test_opening.json`。
- 合格 run 的模型预测与迁移前语义等价。

## 7. 验证要求

项目声明的验证命令：

- `python -m pytest -q`

完整套件按 M1-02 已记录的 `798 passed, 211 failed, 4 skipped` 历史边界判定：不得新增
failure、不得扩大 211 个 failure test-id 集合，且不得存在 M1-03 attributable failure；
实际计数和集合对比在 §10 交付时记录。历史失败将在 M1-05/M1-06 删除旧执行面后清零。

专项验证：

- `python -m pytest -q tests/unit/test_refactor_training_dataset.py tests/unit/test_refactor_training_policy.py tests/unit/test_refactor_training_evaluation.py tests/unit/test_refactor_training_qualification.py tests/golden/test_refactor_training_golden.py tests/integration/test_refactor_develop_cli.py`
- 小型 XGBoost develop CLI smoke。

## 8. 实施顺序

1. TDD 迁移 dataset/folds/weights。
2. TDD 迁移 trainer/OOF。
3. 实现 evaluation/qualification。
4. 实现 artifacts 与 CLI。
5. 运行专项和完整验证。

## 9. 风险控制

- Test 文件访问使用 spy/deny fixture 锁定。
- 资格门槛和 XGBoost 参数来自 protocol，代码不得重复硬编码可漂移副本。
- 不以测试结果调整参数或门槛。
- 不读取、修改或复用冻结 Full14/363490 run，不提前实现去相关训练，也不读取真实数据或
  既有 held-out test 补证。

## 10. 交付结论

### 10.1 文档评审证据

- Document review：
  `docs/4-Reviews/sprint-m1-03-review-by-opencode-go-kimi-k2.7-code.md`、
  `docs/4-Reviews/sprint-m1-03-review-by-opencode-go-glm-5.2.md`。
- Review confirm：`docs/4-Reviews/sprint-m1-03-review-confirm.md`；全部 finding 逐项裁决并应用。

### 10.2 代码评审证据

- Code review：
  `docs/4-Reviews/sprint-m1-03-code-review-by-opencode-go-kimi-k2.7-code.md`、
  `docs/4-Reviews/sprint-m1-03-code-review-by-opencode-go-glm-5.2.md`。第二主评审因内部访问
  `%TEMP%` 被权限策略中止，按 `review-start` 规则由 `deepseek/deepseek-v4-flash`
  fallback 写入原 GLM 路径，事实已在报告与 confirm 中记录。
- Code review confirm：`docs/4-Reviews/sprint-m1-03-code-review-confirm.md`；两份报告全部
  20 条 finding 已逐项裁决，19 Accept、1 Reject。唯一 Reject 是 protocol V1 不可达且
  未授权的 `folds==1` 扩展。
- 已应用 nested upstream identity、occupied-output/test-deny、audit-only `train_weight`、
  transitive code hash、legacy progress、逐 split 双类、CLI 错误归一化和 exact layout
  修正，并补齐对应回归测试。

### 10.3 环境与验证证据

- Worktree `D:\code\HiggsML-worktrees\xgboost-refactor`，branch
  `codex/xgboost-refactor`，base `386437f`；验证时实现为该 base 加 M1-03 working-tree
  change set。
- Windows 10 `10.0.19045`，Python `3.12.13`；NumPy `2.5.2`、pandas `3.0.5`、
  PyYAML `6.0.3`、uproot `5.7.6`、XGBoost `3.4.1`、scikit-learn `1.9.0`、
  pytest `9.1.1`。
- M1-03 专项最终重跑：`28 passed`；完整重构 `tests/unit tests/golden tests/integration`：
  `105 passed, 3 skipped`。专项包含真实 XGBoost module CLI smoke。
- 另行实际运行 module 与 editable-install console 两条微型 `develop`：均 exit 0、终态
  `no_eligible_candidate`，无 CLI failure 诊断。
- 完整 `.venv\Scripts\python.exe -m pytest -q --tb=no`：
  `826 passed, 211 failed, 4 skipped, 5 warnings`。相对 M1-02 `798/211/4` 恰好新增
  28 pass、0 failure、0 skip；当前 211 个 failure test-id 与修正前评审记录的历史集合
  一致，仍全部位于既有 legacy run/script 模块，无 M1-03 attributable failure。
- `pip install -e .`、`pip check`、console/module 形式的 preprocess/xgboost 四项 help、
  `compileall` 和 `git diff --check` 均 exit 0。
- 所有训练/CLI 验证均只使用 `%TEMP%` 合成 CSV。未读取真实数据、工作区权威 ROOT、
  冻结 run 或 held-out test 内容；345060/363490 权威大规模训练门未执行。

### 10.4 Artifact 与提交证据

- Eligible 微型 run 精确发布 9 个文件：`config.yaml`、4 个非 manifest artifact、
  `artifacts/manifest.json`、OOF gzip、OOF plot 与 `model/model.json`；no-eligible 精确发布
  前 8 个文件且没有 `model/`。两种终态均无 `state/test_opening.json`。
- Manifest 显式绑定上游 manifest、development compressed/canonical hashes、经 64-hex/
  schema 校验的 preprocessing protocol/run-config identity、当前 protocol/code/software、
  candidate、final parameters、working points、qualification、counts 与固定 schema。
- 全链 `Path.read_bytes` deny/spy 证明 held-out `processed/test.csv.gz` 零读取；occupied output
  在任何 protocol/manifest/CSV 读取前拒绝且不改写用户文件；adversarial `train_weight`
  不改变五折 OOF、各 fold fit weight 或 final fit weight。Code-hash spy 证明读取
  preprocessing schema 与全部 domain sources；progress factory 精确覆盖五折加 final fit。
- 只 stage M1-03 plan/reviews/implementation/tests；M1-04 至 M1-06 plan 保持未跟踪。
- 提交消息：`feat: complete sprint-m1-03 code and change base on reviews`；提交 hash 在 Git
  commit 完成后由交付响应记录。
