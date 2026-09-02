# Sprint M1-03 Code Review Confirm

**Reviewed Inputs**

- `docs/4-Reviews/sprint-m1-03-code-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-03-code-review-by-opencode-go-glm-5.2.md`
  （第二主评审进程因仓库外临时路径权限中止后，按 `review-start` 规则由
  `deepseek/deepseek-v4-flash` fallback 写入既定路径）
- `docs/3-Plan/sprint-m1-03.md`
- M1-03 implementation、tests、FR-001、批准设计、protocol V1 与 legacy authority

**Review Date**

- 2026-09-02

## Overall Conclusion

两份代码评审均判定无 Critical/High，核心科学行为、dev-only 边界、qualification 与
eligible-only 发布正确。下表覆盖两份报告全部 20 条 finding：19 条 Accept、1 条 Reject。
所有 Medium 均接受并立即修正；Low 中与确认计划或 legacy fail-fast 一致的
项目也在本 Sprint 关闭。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---|---|---|---|---|---|---|---|
| 1 | Medium | Requirement | `Kimi M1` | 上游 protocol/run-config SHA-256 只透传、未校验。 | Accept | Plan §5.3 明确要求绑定 identity；M1-02 manifest 固定 nested schema。 | 在 loader exact-validate `protocol{path,schema_version,sha256}`、`run_config{path,sha256}`，要求 64-hex，保存为 binding 并显式发布；补损坏 identity 负例。 |
| 2 | Medium | Test | `Kimi M2` | 缺 occupied output 在输入读取前拒绝的集成测试。 | Accept | FR-001 R7、plan §5.3 与 `RunTransaction.__enter__`。 | 预创建 run-dir，spy/deny 所有输入读取，断言 `FileExistsError`、输入零读取、无 manifest。 |
| 3 | Medium | Test | `Kimi M3` | Test deny 只在 loader unit，未贯穿 run_development。 | Accept | Plan §5.3/§6 要求完整 develop 路径证据。 | 在 eligible integration 上安装 `Path.read_bytes` deny/spy，断言 held-out path 从未出现。 |
| 4 | Low | Reproducibility | `Kimi L1` | code hash 未覆盖 schema-defining preprocessing/domain 模块。 | Accept | `dataset.py` 运行时消费 `preprocessing.pipeline`，后者消费 domain features/Angular5。 | 将 package initializers、`preprocessing/pipeline.py` 与 `domain/*.py` 纳入 code hash，并测试读取覆盖。 |
| 5 | Low | Requirement | `Kimi L2` | Legacy TrainingProgress 未迁移。 | Accept | Confirmed plan §5.1 明确包含“进度”，不能以静默 fit 代替。 | 增加与 legacy 同语义的可选 `show_progress/progress_factory` 路径；CLI develop 启用，测试/程序调用默认静默，不增加普通 CLI override。 |
| 6 | Info | Positive | `Kimi I1` | Fold 与 class-balanced weights 等价。 | Accept | Golden exact equality 已通过。 | 无代码变更；保留验证证据。 |
| 7 | Info | Positive | `Kimi I2` | Working point、KS、efficiency、AUC 等价。 | Accept | Old/new unit/golden 与静态对照一致。 | 无代码变更。 |
| 8 | Info | Positive | `Kimi I3` | Qualification 与 eligible-only 发布正确。 | Accept | 四 gate、no-model/no-state tests 通过。 | 无代码变更。 |
| 9 | Info | Verification | `Kimi I4` | M1-03 增加 18 pass，未扩展 211 failure。 | Accept | Reviewer 实跑 `816/211/4`，无 M1-03 failure。 | 最终自有验证重跑后将实际结果写入 plan §10。 |
| 10 | Medium | Requirement | `GLM M1` | Nested upstream identity 与 schema version 未 shape-validate。 | Accept | 与 Kimi M1 同问题但额外指出 schema-version/hex 约束。 | 同 No.1；不读取外部 upstream protocol/run-config 文件，只校验被 upstream manifest hash 封存的 identity，因为 development 消费的是 manifest contract。 |
| 11 | Medium | Test | `GLM M2` | 缺 occupied-output end-to-end 门。 | Accept | 与 Kimi M2 独立同结论。 | 同 No.2，并断言输出未被改写。 |
| 12 | Medium | Test | `GLM M3` | 缺 end-to-end held-out deny spy。 | Accept | 与 Kimi M3 独立同结论。 | 同 No.3。 |
| 13 | Low | Test | `GLM L1` | `train_weight` 固定为 1，未直接证明 audit-only。 | Accept | 代码未引用该列进行 fit，但 review-confirm #22 要求锁定此双重语义。 | 用 adversarial `train_weight` 重跑 evidence/final fit，断言 OOF 与实际 sample weights 不变。 |
| 14 | Low | Reproducibility | `GLM L2` | code hash 遗漏 schema transitive inputs。 | Accept | 与 Kimi L1 相同。 | 同 No.4。 |
| 15 | Low | Requirement | `GLM L3` | Progress 被静默遗漏。 | Accept | 与 Kimi L2 相同。 | 同 No.5。 |
| 16 | Low | Correctness | `GLM L4` | Development validator 未保持每个 split 双类 fail-fast。 | Accept | Legacy `full_training_policy` 要求 train/validation 各有 label 0/1；收紧不会改变有效 M1-02 数据。 | 加逐 split 双类校验和负例，保持 legacy fail-fast。 |
| 17 | Low | Consistency | `GLM L5` | XGBoost CLI 错误输出未与 preprocess 归一化。 | Accept | 同仓库 CLI 应提供稳定非 traceback 错误面；不改变 failure receipt。 | 捕获普通 Exception，stderr 输出 `higgsml-xgboost failed: Type: message` 并返回 1；不吞 BaseException。 |
| 18 | Low | Test | `GLM L6` | Layout 测试只做 subset。 | Accept | 设计 §10.1 是批准 allowlist；多余文件也应失败。 | Eligible/no-eligible 分别断言 exact file set，含批准 plot 与条件模型。 |
| 19 | Info | Consistency | `GLM I1` | `folds==1` 时 SE 与 legacy guard 不同。 | Reject | Protocol loader 已强制 `folds>=2`，V1 byte-fixed `folds=5`；该状态不可达，且未来改 folds 需新 protocol/design。 | 不为不可达、未批准的单 fold 扩展代码；未来版本在新评审中决定。 |
| 20 | Info | Positive | `GLM I2` | 37 项 document-confirm 决策均已实现。 | Accept | 静态和 golden/integration 证据一致。 | 无代码变更；本 confirm 的修正完成后重跑全部门。 |

## Needs Immediate Action

- 校验并显式发布 upstream protocol/run-config identity。
- 补 occupied-output、end-to-end test deny、adversarial train_weight、per-split labels、exact
  layout 与 code-hash coverage 测试。
- 恢复可选 progress 路径，并统一 CLI 失败诊断。

## Can Be Deferred

- `folds==1` 不属于 V1；不增加未批准行为。
- 权威 345060/363490 大规模训练仍只在具备授权输入的环境执行。

## Final Status

代码评审结论为“修正后接受”。应用 19 条 Accept 的立即动作、重跑验证并更新 Sprint §10
后，M1-03 可进入独立提交门；唯一 Reject 不构成遗留缺陷。
