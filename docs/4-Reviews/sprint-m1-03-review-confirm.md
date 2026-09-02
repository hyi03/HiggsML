# Sprint M1-03 Document Review Confirm

**Reviewed Inputs**

- `neural/docs/sprint-m1-03.md`
- `neural/docs/adversarial-mlp-protocol-v1.md`
- `neural/docs/FR-001-adversarial-mlp-refactor.md`
- `neural_adversarial_mlp_refactor_design.md`
- `docs/4-Reviews/sprint-m1-03-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-03-review-by-opencode-go-glm-5.2.md`
- `AGENTS.md`、`neural/AGENTS.md`、M1-02 preprocess protocol 与 M1-04 scope

**Review Date**

- 2026-09-02

## Overall Conclusion

两份独立评审均确认 M1-03 的核心架构、29 列输入、15 特征、精确参数量、训练常数和
MC-only/test 隔离边界一致且可实现。可执行 checklist 与少数机械语义仍需补齐，尤其是
dataset loader 与 single-fold trainer 的边界、完整 checkpoint schema、validation AUC 前置条件、
YAML mutation gate，以及无背景 batch 下 AdamW 不得改变 adversary 参数。

以下 Accept/Partial 动作应用后文档门通过。确认不授权真实数据、full-data training、held-out
test 或 `open-test`；Windows/synthetic 仍不是锁定原生 `osx-arm64` 权威证据。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---:|---|---|---|---|---|---|---|
| 1 | High | Consistency | `Kimi H1` | loader 的完整 development table 与 trainer 的已分 fold frame 边界混淆 | Accept | Protocol §2.1 与 Sprint §3 用词确实不一致 | 明确 dataset loader 先验证完整 29 列 development table；single-fold trainer 只能接收 loader 构造的 validated fold 对象。 |
| 2 | High | Requirement | `Kimi H2` | Sprint 未列 checkpoint 最小字段及反序列化检查 | Partial | Protocol §8 要求内存 checkpoint 字段；同时明确 M1-03 不发布 artifact | 增加完整字段、deep CPU copy、protocol hash 和内存 validator；持久化反序列化留给后续 artifact Sprint，不在 M1-03 扩 scope。 |
| 3 | High | Correctness | `Kimi H3` | validation 单类或坏权重会使 weighted AUC 无定义 | Accept | Protocol §8 已要求双类、有限非负权重和正总和 | 加入 implementation/test checklist，并以 input binding failure 关闭。 |
| 4 | Medium | Data Safety | `Kimi M1` | test-first refusal 的执行顺序验证不够强 | Partial | 必须先看列名和 `split` 才能拒绝；但不得读取 feature values、identity values 或统计量 | 用 poison accessor/probe 证明 split 检查后立即失败，且 feature/identity/statistic accessor 未被调用；不声称 DataFrame 对象从未物化。 |
| 5 | Medium | Requirement | `Kimi M2` | Sprint 未重述 target lambda 白名单 | Accept | Protocol §4.3 已冻结五个候选 | Sprint 增加白名单与 schedule mutation rejection。 |
| 6 | Medium | Audit | `Kimi M3` | checkpoint 未显式绑定 protocol SHA-256 | Accept | Protocol §8 已列 protocol SHA-256 | loader 计算 YAML bytes SHA-256；checkpoint 保存并由 validator exact 比较。 |
| 7 | Medium | Correctness | `Kimi M4` | 空 mass bin/零 absolute-weight sum 未进入 Sprint checklist | Accept | Protocol §5.3 明确 fail closed | 加入实现与测试项。 |
| 8 | Medium | Correctness | `Kimi M5` | 未要求保留最后一个不完整 batch | Accept | Protocol §6 明确不得 drop | 明确 `drop_last=False` 语义并测试。 |
| 9 | Medium | Correctness | `Kimi M6` | 无背景 batch 缺少实现与测试 | Accept | Protocol §5.3 有要求，GLM 进一步证明 naive AdamW 会 weight-decay 更新 | 冻结为 `0.0 * classifier_logits.sum()`，不运行 adversary forward；`zero_grad(set_to_none=True)`，断言 adversary grad 为 `None` 且参数不变。 |
| 10 | Low | Clarity | `Kimi L1` | fitting 容易被误读为新的 split 枚举 | Accept | M1-02 split 只有 train/validation/test | 定义 fitting 是 loader validated development rows 中传给当前 fold optimizer 的训练部分，不新增 split 值。 |
| 11 | Low | Security | `Kimi L2` | 错误消息可能泄露 row/value/path | Accept | Protocol §9 已禁止 | Sprint 增加 hygiene 实现与测试。 |
| 12 | Low | Consistency | `Kimi L3` | Sprint 未绑定稳定退出码 | Partial | M1-03 主要是 library primitive，无 qualification/test-opening 路径 | schema/protocol/data contract 统一抛 `InputBindingError`（CLI 映射 3）；unexpected 为 70。退出码 4/5 只在存在对应 path/qualification 边界时使用，不制造虚假路径。 |
| 13 | Low | Documentation | `Kimi L4` | 交付结论 placeholder 未说明收尾证据 | Accept | §10 尚待填写属正常，但收尾标准可更明确 | 增加收尾时记录 §6、验证、边界与权威未运行状态。 |
| 14 | Info | Safety | `Kimi I1` | Windows/synthetic 权威边界正确 | Accept | 与 AGENTS 一致 | 保持原文。 |
| 15 | Info | Consistency | `Kimi I2` | 精确参数量正确 | Accept | 独立算术验证为 7,617/1,611/9,228 | 保持并写 executable assertions。 |
| 16 | Medium | Verification | `GLM M1` | Sprint §7 漏 pip check、CLI help、diff check 与边界声明 | Accept | neural AGENTS 和 Protocol §10 都要求这些证据 | 补入 §7。 |
| 17 | Medium | Requirement | `GLM M2` | YAML/loader 无明确 work package、测试模块或实施顺序 | Accept | 文件尚不存在，当前 checklist 可漏实现 | 在 5.1、§7、§8 增加配置转录、exact loader 与 mutation tests。 |
| 18 | Medium | Test | `GLM M3` | Sprint checklist 是 Protocol §10 的有损子集 | Accept | 手算 loss、identity overlap、round-trip、lambda=0 等未列 | 绑定 Protocol §10 全部条目为强制 gate，并在各工作包补主要 edge cases。 |
| 19 | Medium | Correctness | `GLM M4` | differentiable zero 与单 AdamW weight decay 机械冲突 | Accept | PyTorch AdamW 会更新拥有 zero grad 的参数，但跳过 `grad=None` | 采用第 9 项机制并测试参数 bytes 不变。 |
| 20 | Low | Clarity | `GLM L1` | warm-up/λ=0 的 adv metric 与 epoch 聚合未定义 | Accept | Protocol 只定义 batch loss，§9 要求 epoch 字段 | warm-up/λ=0 记录 adv=0、total=cls；epoch loss 累计全 epoch 加权分子/分母，不取 batch 简单平均。 |
| 21 | Low | Consistency | `GLM L2` | adversary 的 Linear bias/LayerNorm affine/eps 只被参数量间接约束 | Accept | §4.2 未显式复述 | 声明网络两部分统一使用 bias、affine LayerNorm、eps=1e-5，并写入 YAML。 |
| 22 | Low | Clarity | `GLM L3` | m4l range 是全行还是只背景不清楚 | Accept | M1-02 所有 selected row 均受 analysis window；signal 不参与 binning | 输入契约对所有行验证有限且 `105 <= m4l <= 160`；仅背景计算 bin/adversarial loss，测试 signal/background 两类。 |
| 23 | Low | Requirement | `GLM L4` | Sprint 未列完整 result/environment evidence | Accept | Protocol §9 有完整字段 | Sprint 绑定 Protocol §9 result object。 |
| 24 | Low | Risk | `GLM L5` | 失败诊断 hygiene 未在 Sprint 测试 | Accept | 与 Kimi L2 独立同结论 | 按第 11 项实施并保留独立证据来源。 |
| 25 | Low | Documentation | `GLM L6` | protocol 缺状态/日期/来源/权威平台 header | Accept | M1-02 protocol 有既有格式 | 增加 header，状态记为文档评审确认通过、等待实现验证。 |
| 26 | Info | Consistency | `GLM I1` | 核心数值/结构一致 | Accept | reviewer 独立验证 29/15 列、参数量和 ramp | 无修改，保持。 |
| 27 | Info | Dependency | `GLM I2` | M1-02/M1-04 依赖与 repo 状态一致 | Accept | 当前 training 仅骨架且 M1-02 已提交 | 无修改，保持顺序门。 |
| 28 | Info | Safety | `GLM I3` | MC-only/test/feature 边界闭合 | Accept | 与 FR 和 AGENTS 一致 | 无修改，实施与代码评审继续验证。 |
| 29 | Info | Consistency | `GLM I4` | 三处 Sprint paraphrase 比 protocol 更松 | Accept | test-first、exact threshold、mutation 类型在 protocol 更精确 | Sprint normative 句改为 protocol 原文，并增加 exact `1e-4` boundary test。 |

## Needs Immediate Action

- 应用第 1–13、16–25、29 项文档修订。
- 文档修订后运行 `git diff --check`，并进行针对修订段落的双模型复审。

## Can Be Deferred

- checkpoint 的持久化格式、文件发布与反序列化属于后续 run artifact Sprint；M1-03 只需
  完成可验证的内存 schema、deep copy 与 protocol hash binding。
- 真实 full-data training 与锁定原生 `osx-arm64` 权威证据不属于 M1-03。

## Final Status

`Accepted for implementation after applying the listed document actions and passing focused
re-review.` 本确认不授权真实数据、held-out test、`open-test` 或 full-data training。
