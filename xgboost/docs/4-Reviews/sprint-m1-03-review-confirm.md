# Sprint M1-03 Review Confirm

**Reviewed Inputs**

- `docs/3-Plan/sprint-m1-03.md`
- `docs/4-Reviews/sprint-m1-03-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-03-review-by-opencode-go-glm-5.2.md`
- `docs/1-Requirement/FR-001-angular19-xgboost-refactor.md`
- `docs/superpowers/specs/2026-09-01-xgboost-refactor-design.md`
- `config/xgboost_protocol_v1.yaml`
- 当前迁移权威 `src/experiment_runner.py`、`src/full_training_policy.py`、
  `src/full_training_evaluation.py`、`src/validation.py`

**Review Date**

- 2026-09-02

## Overall Conclusion

两份评审均正确判断 M1-03 的阶段边界，没有 Critical finding。计划不能按原稿直接实施；
训练输入、权重、fold、工作点、qualification、artifact 和验证门必须先精确冻结。

下表逐项裁决两份报告的全部 37 条 finding。34 条 Accept，3 条 Partial；Partial 均为
评审识别了真实缺口，但其科学公式或算法描述需要按当前权威纠正。所有 Accept/Partial 的
文档动作均在进入实现前应用到 `sprint-m1-03.md`。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---|---|---|---|---|---|---|---|
| 1 | High | Correctness | `Kimi H1` | KS 的对象未明确为 OOF ZZ 的 `m4l`。 | Accept | 设计 §9 与 `experiment_runner._background_mass_ks` 比较 inclusive ZZ 和阈值选中 ZZ 的 `m4l`。 | 在 §5.2 固定每个工作点的 inclusive-vs-selected ZZ `m4l` KS；调用沿用 signed `physical_weight`，`weighted_ks_distance` 内部按既有语义取绝对值。 |
| 2 | High | Requirement | `Kimi H2` | 工作点未限定为 development OOF ZZ 的绝对物理权重。 | Accept | 设计 §8.2；`build_working_points` 仅筛 label 0，`weighted_retention_threshold` 对权重取绝对值。 | 固定只使用 OOF ZZ score 与 `abs(physical_weight)`，高分到低分稳定累计并完整保留 score tie；禁止 signal/test 参与定阈值。 |
| 3 | High | Requirement | `Kimi H3` | Develop CLI 未明确禁止科学参数和 overwrite 覆盖。 | Accept | FR-001 R3、R7 与设计 §6.4/§7.3。 | 固定 parser 只接收 `--input-run --protocol --run-dir`，为 overwrite、feature、seed、fold、candidate、threshold 和 qualification 覆盖添加拒绝测试。 |
| 4 | Medium | Correctness | `Kimi M1` | Class-balanced weight 应在 Higgs/ZZ 类内归一化。 | Partial | `class_balanced_training_weights` 从 `abs(physical_weight)` 重算，使每类总权重均为 `len(frame)/2`、整体均值为 1；CSV `train_weight=abs(w)/mean(abs(w))` 不是 fit 输入。 | 接受“必须精确定义”的诊断，但不用评审中含混的“归一化到各自权重和”；在 §5.1 写入权威公式并加 exact golden。 |
| 5 | Medium | Consistency | `Kimi M2` | `-k` 专项门可能静默漏测。 | Accept | M1-02 已采用显式文件列表消除此风险。 | §7 改用 M1-03 测试文件的显式路径列表。 |
| 6 | Medium | Requirement | `Kimi M3` | 上游 manifest/hash 绑定字段不具体。 | Accept | FR-001 R7 与 M1-02 manifest 的 protocol、run-config、双重 CSV hash 合同。 | 在 §5.3 固定上游 run、manifest SHA-256、development compressed/canonical hash 及上游 protocol/run-config identity。 |
| 7 | Medium | Correctness | `Kimi M4` | Fold 应按 identity 确定并在两类间分层。 | Partial | `development_fold` 使用 `blake2b("task4b-fold:{channel}:{event}", digest_size=8)` 大端整数取模；`assign_development_folds` 只在分配后验证每折含 0/1，不做 stratified assignment。 | 接受确定性、互斥和覆盖要求；拒绝“分层分配”部分，按权威 hash 算法与事后双类校验写入 §5.1。 |
| 8 | Medium | Requirement | `Kimi M5` | 不合格 run 还应禁止 state claim 和部分模型产物。 | Accept | 设计 §10.1 规定 model 仅 eligible 出现，`state/test_opening.json` 只能由 M1-04 open-test claim 创建。 | §5.3/§6 明确 no-eligible 无任何 `model/`，且 M1-03 无论结果都不创建 `state/test_opening.json`。 |
| 9 | Medium | Documentation | `Kimi M6` | Development run layout 未枚举。 | Accept | 设计 §10.1 给出权威布局。 | 在 §5.3 固定 config、artifacts、OOF、eligible-only model、plots；state claim 明确延后到 M1-04。 |
| 10 | Medium | Test | `Kimi M7` | Test artifact 未读取缺少可执行证明。 | Accept | FR-001 R5、设计 §9 与计划 §9 的 spy/deny 原则。 | 集成测试暴露 test 路径并以访问 spy/deny 断言 develop 只读取 development artifact。 |
| 11 | Medium | Correctness | `Kimi M8` | Weighted AUC 的权重来源未说明。 | Partial | `_development_metrics` 和 fold authority 均向 `roc_auc_score` 传 `abs(physical_weight)`，不是 signed weight 或 CSV `train_weight`。 | 接受区分训练权重与评估权重的诊断；在 §5.2 精确写为 `abs(physical_weight)`。 |
| 12 | Medium | Correctness | `Kimi M9` | 每个工作点应要求 signal efficiency 严格高于 background efficiency。 | Accept | FR-001 R5 与设计 §9。 | 将三点逐点严格比较列为 qualification 条件和边界测试。 |
| 13 | Low | Clarity | `Kimi L1` | Test-opening 与历史删除应拆成不同后续阶段。 | Accept | 设计阶段映射分别为 M1-04 与 M1-05/M1-06。 | 拆分 §4 两条 scope exclusion。 |
| 14 | Low | Clarity | `Kimi L2` | `test_opened: false` 应明确属于 development manifest。 | Accept | M1-02 已从 preprocessing manifest 删除该字段；生命周期从 development run 开始。 | 在 §5.3/§6 指定该字段只在 development manifest，且不等同于提前创建 claim state。 |
| 15 | Low | Documentation | `Kimi L3` | §10 未预填证据结构。 | Accept | FR-001 要求每 Sprint 的文档评审、代码评审、验证和提交证据。 | 按 M1-02 结构预填 §10 四类证据。 |
| 16 | Info | Traceability | `Kimi I1` | 应引用 M1-02 review-confirm 作为上游合同。 | Accept | M1-02 已冻结 32 列、hash 和 manifest 语义。 | §2 增加 M1-02 plan/review-confirm/code-review-confirm 链接。 |
| 17 | Info | Risk | `Kimi I2` | 应显式禁止修改或复用冻结 Full14 run。 | Accept | `AGENTS.md` 冻结状态。 | §9 明确不读取、修改或复用冻结 run，也不提前进行去相关研究。 |
| 18 | Info | Requirement | `Kimi I3` | Eligible 最终模型格式未写明。 | Accept | 设计 §10.1 固定 `model/model.json`。 | §5.3 固定 XGBoost JSON 位置与 eligible-only 条件。 |
| 19 | Info | Test | `Kimi I4` | Golden authority 来源未引用。 | Accept | 设计 §7.2 指定 legacy 入口、config、runner、ANGULAR19 与 Angular5 authority。 | §5.1 引用上述 authority，并复用 M1-01 预注册精度常量。 |
| 20 | High | Requirement | `GLM H-1` | 未绑定 M1-02 的 19+13 固定输入 schema 及 `m4l` 双重角色。 | Accept | `preprocessing.pipeline.OUTPUT_COLUMNS` 固定 19 model + 13 metadata；`m4l` 禁止进模型但用于 KS。 | §5.1 要求完整、有序、唯一 32 列，列出 13 metadata，并对 `m4l` 角色和 header golden 加以固定。 |
| 21 | High | Requirement | `GLM H-2` | 四项 qualification 未枚举，且它是新 lifecycle gate。 | Accept | FR-001 R5、设计 §9；legacy runner 无条件保存模型。 | §1/§5.2 区分等价训练迁移和新增发布门，并列出 AUC、三 KS、三效率及 OOF 完整性四项条件。 |
| 22 | High | Correctness | `GLM H-3` | CSV `train_weight` 与实际 XGBoost sample weight 语义冲突。 | Accept | `training_weights` 是全表 mean-normalized abs；`class_balanced_training_weights` 是按类总和 `len(frame)/2`，runner 使用后者。 | §5.1 明确每 fold fitting 和 final fit 都从 `physical_weight` 重算，CSV 字段只审计。 |
| 23 | High | Requirement | `GLM H-4` | Artifact layout、manifest 和 OOF schema 未固定。 | Accept | 设计 §10.1、M1-02 manifest precedent、legacy OOF frame。 | §5.3 固定文件布局、八列 OOF schema，以及 manifest 的 upstream/candidate/working-point/qualification/test 状态绑定。 |
| 24 | Medium | Verification | `GLM M-1` | Full suite exit 1 缺少相对历史 failure gate。 | Accept | M1-02 记录 `798 passed, 211 failed, 4 skipped`，211 为历史失败集合。 | §7 预注册“不新增 failure、不扩大 failure id 集合、无 M1-03 attributable failure”，§10 记录实际计数与集合比较。 |
| 25 | Medium | Test | `GLM M-2` | `-k` 依赖命名。 | Accept | 与 Kimi M2 相同但理由独立。 | 用显式测试文件列表替换。 |
| 26 | Medium | Correctness | `GLM M-3` | Fold payload、字节序和 protocol/code 边界未固定。 | Accept | `development_fold` 的 namespaced blake2b 实现；当前 protocol V1 只有 folds 数。 | §5.1 固定 payload、digest_size、大端和取模；V1 byte-for-byte 消费，算法作为 legacy code-fixed 行为迁移，不扩 schema。 |
| 27 | Medium | Correctness | `GLM M-4` | 工作点、KS 和效率算法未固定。 | Accept | `weighted_retention_threshold`、`build_working_points`、`_background_mass_ks`、`weighted_ks_distance`。 | §5.2 写入稳定降序累计、首次达到 target、完整 tie、inclusive-vs-selected m4l KS、绝对权重效率，并加 old/new golden。 |
| 28 | Medium | Correctness | `GLM M-5` | Final tree count 的 `np.rint` 规则未固定。 | Accept | `_final_tree_count = max(1, int(np.rint(np.median(best_iteration+1))))`。 | §5.1 固定公式与 half-to-even，并加 `.5` 边界 golden。 |
| 29 | Medium | Consistency | `GLM M-6` | XGBoost protocol V1 未声明 byte-identical 消费。 | Accept | 设计 §7.3 要求改科学行为时版本化；当前 M1-01 protocol 已冻结。 | §3/§5.3 明确不修改 V1 bytes，未来变更需新版本和复审。 |
| 30 | Low | Documentation | `GLM L-1` | §10 缺四类证据清单。 | Accept | 与 Kimi L3 相同但对应 FR blocking gate。 | 预填 document review、code review、verification、artifact/commit 四节。 |
| 31 | Low | Traceability | `GLM L-2` | Golden 未引用预注册浮点策略。 | Accept | M1-01 §5.1 与 `test_refactor_characterization.py` 的 `RTOL=ATOL=1e-12`。 | §5.1 要求复用同一常量，identity/fold/schema/终态精确相等。 |
| 32 | Low | Traceability | `GLM L-3` | §2 缺 FR 和批准设计链接。 | Accept | M1-02 已采用同一链接模式。 | 添加相对链接。 |
| 33 | Low | Correctness | `GLM L-4` | 单候选选择和无 tie-break 未写明。 | Accept | Protocol V1 只有一个 candidate；设计 §9 明确无运行时网格或多候选 tie-break。 | §5.1 固定唯一候选、按 mean weighted AUC 的既有选择语义，并禁止新增 tie-break。 |
| 34 | Low | Requirement | `GLM L-5` | `objective`/`eval_metric` provenance 不清。 | Accept | `_model_parameters` code-fixed `binary:logistic`/`auc`，protocol 无字段。 | §5.1 明确二者按 legacy authority 固定在代码，不修改 protocol V1。 |
| 35 | Info | Consistency | `GLM I-1` | 科学边界正确。 | Accept | 计划与 FR-001、设计、`AGENTS.md` 一致。 | 保留并在实现测试中持续锁定 dev-only、no tuning、no frozen-run access。 |
| 36 | Info | Requirement | `GLM I-2` | 现有验收标准正确覆盖 no-model 与正常 no-eligible 终态。 | Accept | FR-001 R5/R7。 | 保留并补成可测试的 manifest、model 和 claim-state 条件。 |
| 37 | Info | Process | `GLM I-3` | M1-03 交付应只 stage 本 Sprint plan/reviews/实现。 | Accept | M1-04～M1-06 当前为独立未跟踪计划，符合逐 Sprint 提交。 | M1-03 提交只纳入本 Sprint 文件，继续保留 M1-04～M1-06 未跟踪。 |

## Needs Immediate Action

- 在实施前修订 M1-03 plan，精确固定 32 列输入、两种权重语义、fold、OOF、工作点、KS、
  efficiency、qualification、final-tree、CLI 和 artifact 合同。
- 用显式测试文件替换 `-k`，并预注册相对 M1-02 `798/211/4` 基线的完整套件判断门。
- 明确 M1-03 不创建 `state/test_opening.json`，且 no-eligible 不创建任何 `model/`。

## Can Be Deferred

- `state/test_opening.json` 的原子 claim 与 test artifact 读取属于 M1-04。
- 历史执行面删除属于 M1-05，最终全链与归档属于 M1-06。
- 权威 345060/363490 大规模训练只在具备授权输入的环境执行；本 Sprint 可用微型 MC fixture
  证明行为迁移，同时如实记录该验证门未执行。

## Final Status

原计划需修订后方可接受。应用本确认中的 34 条 Accept 与 3 条 Partial 后，M1-03 文档评审
闭环，可以进入 TDD 实施；不改变任何冻结科学参数、候选、工作点或资格门槛。
