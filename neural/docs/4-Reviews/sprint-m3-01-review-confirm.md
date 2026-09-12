# Sprint M3-01 Document Review Confirm

**Reviewed Inputs**

- `sprint-m3-01-review-by-gpt-5.5.md`
- `sprint-m3-01-review-by-gpt-5.6-sol.md`
- `../1-Requirement/FR-SE-03-subset-bound-discriminant-v2.md`
- `../3-Plan/sprint-m3-01.md`
- `../sw-dev/h4l-compact-kinematics-sample-efficiency-development-plan.md`
- `../sw-dev/artifact-schema.md`
- `../../src/research/training_subsets.py`
- `../../src/research/discriminants.py`
- `../../src/research/workflow.py`
- `../../AGENTS.md`

**Review Date**

- 2026-09-12

## Overall Conclusion

两份评审正确指出，原草案不能从普通 DataFrame 证明 prepared feature 与完整 validation 的来源，且未把 v2 model dict 放入可验证的 run/upstream 链。该问题阻断验收。M3 将改为非 CLI application service：从重新验证的 prepared run 内部加载数据、选择 M2 subset、训练并发布专用 model run；M4 再调用该服务做批处理。

compact descriptor、strict v2 schema、raw-only 阶段矩阵、failure matrix 和 downstream lineage object 也需在编码前写实。以下接受项已经应用，文档可进入实现门。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---:|---|---|---|---|---|---|---|
| 1 | Critical | Security | GPT-5.6-sol F-01 | 普通 DataFrame 可替换 feature/source row/validation 后冒充 prepared lineage。 | Accept | M2 membership/summary不绑定全部 feature bytes；现 `train_discriminant` 不验证 prepared receipt。 | 新增 v2 application service，从重新 `read_run` 的 prepared `events.jsonl` 内部加载全部可访问数据；不允许调用方 DataFrame取得 v2身份，并测试 feature/source row/validation 篡改或缺失在 receipt/loader 层拒绝。 |
| 2 | High | Interface | GPT-5.5 #2 / GPT-5.6-sol F-02 | v2 调用链缺可信 compact freeze descriptor，旧 candidate/groups 参数冲突规则不明。 | Accept | overlay只有 compact ID，实际 groups/inputs在 M1 freeze；现训练器靠 candidate/groups选择表示。 | selection 携带经 M1 loader 重建的 freeze artifact/digest/candidate descriptor；v2 service 只接收 `representation_id`并自行推导 candidate/groups，固定 lambda=0，拒绝其他表示/架构。 |
| 3 | High | Executability | GPT-5.5 #1 | M3 要求 workflow downstream 集成却不提供 subset ingress。 | Accept | 当前 `workflow train` 没有 subset参数；M4才负责 learning-curve CLI。 | 从 M3 移除旧 `workflow.py` ingress 修改，新增可直接测试和供 M4 调用的 publisher/reader service；旧 workflow保持不变。 |
| 4 | High | Artifact | GPT-5.6-sol F-04 | v2 只有自签 model dict，没有 model run/upstream 发布和可信 reader。 | Accept | 总计划要求正式 payload 与 upstream receipts；当前 train run只绑定prepared。 | 定义 `sample-efficiency-train` run，upstreams精确为 prepared、compact-freeze、training-subsets，保存 overlay snapshot和model；reader从路径重验所有run/receipt、upstream和模型语义后返回可信模型/lineage。 |
| 5 | High | Schema | GPT-5.6-sol F-05 | v2 缺精确键、类型、条件字段和交叉不变量。 | Accept | 单靠 `model_id` 可被修改后重签；v1还有可选 `history_contract`。 | 在 FR 加 v2 schema表和不变量：v1科学字段、可选诊断字段、v2新增字段、finite/canonical、参数量公式、seed、表示、full/partial、summary及ID重算；v1保持现有宽容读取。 |
| 6 | High | Lineage | GPT-5.5 #3 / GPT-5.6-sol F-06 | downstream lineage没有统一对象、落点、source model/run绑定或跨层验证规则。 | Accept | 当前 calibration/template/inference只传播 candidate/mapping/seed。 | 定义严格 `h4l-experiment-lineage-v1` 不可变对象，绑定 source model artifact/model ID及全部实验字段；raw calibration、template entry、model-self result在固定 `experiment_lineage` 键复制，直接上游逐层等值验证。M4 publisher负责各层manifest upstream。 |
| 7 | High | Safety | GPT-5.6-sol F-03 / GPT-5.5 #5 | v2 可能流入 non-raw、CDF 或旧 assessment claim 路径。 | Accept | 当前通用 workflow支持 physical/absolute和assessment，而 M6才定义相应协议与claim。 | 明确阶段矩阵：M3 v2只允许raw、普通template、model-self；任何 non-raw/capacity/assessment/mismatch 在 claim或payload访问前以输入错误拒绝，并加入前置拒绝测试。 |
| 8 | Medium | Determinism | GPT-5.5 #4 | M3 summary 重算的顺序与数值相等规则未定义。 | Accept | M2 用 canonical identity顺序与Python float逐组累计。 | 抽取/复用 M2 frame summary helper，按 canonical identity/source row排序、事件组先求 signed sum，再生成逐类/总计；以 canonical JSON bytes精确比较。 |
| 9 | Medium | Failure | GPT-5.6-sol F-07 | 低统计、alias错误、参数错误的异常/status/exit code不确定。 | Accept | `ResearchStateError` 与 `ResearchError` 外部语义不同。 | 加失败矩阵：M2低统计为 `ResearchStateError(training_subset_insufficient_statistics)`；缺失/重复alias、非协议fraction/draw、伪造对象、表示/摘要/下游错配均为 `ResearchError(training_subset_binding_mismatch)`/exit 3，且发生在训练/RNG/claim前。 |
| 10 | Medium | Test | GPT-5.5 #6 / GPT-5.6-sol F-08 | focused矩阵缺 workflow/downstream、重签篡改和严格兼容攻击。 | Accept | 当前测试清单不能证明来源关闭和语义reader。 | 新增 `test_sample_efficiency_training.py` 与 `test_sample_efficiency_lineage.py`，覆盖 prepared字节篡改、selection/字段重签、validation完整性、v1 bytes、full规范化、train-derived统计、raw-only及逐层lineage替换；纳入focused命令。 |
| 11 | Low | Documentation | GPT-5.5 #7 | Sprint 未引用 M2 最终确认和 artifact schema §8。 | Accept | M2契约在评审后收紧。 | 在依赖中加入 M2 code-review-confirm 与 artifact schema §8，并同步 M3 schema章节。 |

## Needs Immediate Action

- 将 v2 训练改为 receipt-bound publisher/reader service，并补足 freeze descriptor、strict schema和失败矩阵。
- 定义统一 experiment lineage、raw-only阶段矩阵和直接上游验证。
- 扩充 focused tests，覆盖重签后的语义篡改与 v1 byte compatibility。

## Can Be Deferred

- M4 实现 CLI/batch publisher；M6 实现 non-raw、capacity和独立 assessment claim。M3只提供这些后续阶段可调用的已验证服务与血缘原语。

## Final Status

接受。receipt-bound v2 publisher/reader、freeze descriptor、严格schema、raw-only阶段矩阵、failure matrix和downstream lineage落点均已写入FR/Sprint；M3文档门关闭，不需改变M4—M7既定边界。
