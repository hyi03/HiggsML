# Sprint M1-03 Code Review Confirm

**Reviewed Inputs**

- `docs/4-Reviews/sprint-m1-03-code-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-03-code-review-by-opencode-go-glm-5.2.md`
- M1-03 implementation、tests、Sprint、bound protocol、FR、design、两级 AGENTS

**Review Date**

- 2026-09-02

## Overall Conclusion

实现的网络、GRL、loss、CPU deterministic loop 与安全边界基本正确，但代码评审证明现有
测试不能支撑完整验收，且 sealed loader 接受类型/映射顺序漂移。另有一个协议内部冲突：
优化权重冻结为 float32，却把 per-bin sum 容差写成 `1e-12`。本确认选择保留 float32，
显式修订为 `rtol=0, atol=1e-7`，并禁止测试继续使用无来源的 `1e-6`。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---:|---|---|---|---|---|---|---|
| 1 | Medium | Test | `Kimi M1` | 只验证 lambda=0 determinism | Accept | 非零 lambda 路径未进入 suite | 增加 0.05/0.50 两次运行、两张网络 state/epoch metric 比较与 warm-up 相同证据。 |
| 2 | Medium | Test | `Kimi M2` | 缺 split-first poison accessor | Accept | 现有 test 只证明最终拒绝 | 加 DataFrame proxy/subclass，断言拒绝前只访问 split。 |
| 3 | Medium | Test | `Kimi M3` | AUC 前置条件与非法 lambda 未测试 | Accept | 分支存在但无证据 | 参数化覆盖单类、坏权重、零和和未注册 lambda。 |
| 4 | Medium | Test | `Kimi M4` | trainer zero-effective-background 未测试 | Accept | 只有纯 signal optimizer 单测 | 增加背景行存在但 batch adv sum=0 的 trainer/helper 证据。 |
| 5 | Medium | Test | `Kimi M5` | patience/threshold 未测试 | Accept | checkpoint replacement 逻辑无边界证据 | 抽出 deterministic early-stop state helper，测试 tie、exact 1e-4、改善、reset、20 次停止。 |
| 6 | Low | Robustness | `Kimi L1` | dict equality 与 byte hash 语义不清 | Partial | SHA 用于绑定实际 bytes；semantic loader 仍必须 type/order strict | 保留 byte SHA 绑定，semantic validation 改为递归 type/key-order strict；不同注释可加载但 hash 必须变化。 |
| 7 | Low | Test | `Kimi L2` | list/order 与 comment hash 未测试 | Accept | Protocol §10 要求 order mutation | 增加 list/key reorder rejection 与 comment hash change。 |
| 8 | Low | Robustness | `Kimi L3` | checkpoint state dict 未校验 keys/shapes/device/dtype | Accept | 当前 validator 把核心 payload 当 opaque | 与 fresh model schema exact 对比并检查 CPU/float32/AUC range。 |
| 9 | Low | Specification | `Kimi L4` | `validation_scores` 不在 result 字段表 | Reject | Protocol §9 明确“至少返回”，允许实现内部附加字段，且该字段不发布 artifact | 保留为内存测试/下游评分便利；artifact schema 留后续 Sprint。 |
| 10 | Info | Scope | `Kimi I1` | train CLI 尚无 develop/open-test | Accept | M1-03 只交付单 fold primitive | 保持，M1-04/M1-05 再实现。 |
| 11 | Info | Positive | `Kimi I2` | 参数量/结构正确 | Accept | executable assertions 已通过 | 保持。 |
| 12 | Info | Positive | `Kimi I3` | bin/负权重/zero loss 正确 | Accept | 机制正确但 trainer edge 缺证据 | 保持并补第 4 项。 |
| 13 | Info | Positive | `Kimi I4` | lambda schedule/lambda0 deterministic 正确 | Accept | 现有测试通过 | 扩展第 1、5 项。 |
| 14 | High | Protocol | `GLM H1` | Python equality 接受 bool/int/float type drift | Accept | probe 已复现，违反预声明 gate | 实现递归 `type is type`、key order、list order strict comparator，并加 mutation tests。 |
| 15 | High | Test | `GLM H2` | 无 composed GRL/非零 lambda 证据 | Accept | probe 证明机制正确但 suite 缺失 | 加 eval-mode composed gradient 与 signal-zero test；加非零 train_fold。 |
| 16 | High | Test design | `GLM H3` | fixture 两类 feature 完全相同，AUC 恒 0.5 | Accept | probe 证明 checkpoint 永远 epoch1 | 让部分 feature label-dependent；early-stop 边界用独立 helper 序列测试，避免依赖偶然训练轨迹。 |
| 17 | Medium | Protocol | `GLM M1` | mapping key order 未密封 | Accept | 重排 mapping 被接受且 hash 不同 | 纳入第 14 项递归 order check。 |
| 18 | Medium | Test | `GLM M2` | early stop 规则无测试 | Accept | 与 Kimi M5 独立一致 | 纳入第 5 项。 |
| 19 | Medium | Test | `GLM M3` | 不同 lambda init/batch reuse 未测试 | Accept | probe 证明机制有效 | 比较 epoch1-5 exact metrics；公开只读 batch-order fingerprint 或内部 helper 供测试。 |
| 20 | Medium | Numerics | `GLM M4` | float32 bin sum 不满足文档 1e-12，test 偷放宽 1e-6 | Accept | max error 3.7e-8；float32 contract 与 1e-12 冲突 | 修订 protocol 为 `rtol=0, atol=1e-7`，YAML seal 该容差，测试使用 exact 新谓词。 |
| 21 | Medium | Test | `GLM M5` | poison order 缺证据 | Accept | 与 Kimi M2 独立一致 | 纳入第 2 项。 |
| 22 | Medium | Test | `GLM M6` | data/fold/mass mutation matrix 不足 | Partial | 所列路径真实，但不需重复每个等价 NumPy failure | 覆盖 identity empty/duplicate、dtype、m4l、negative weight、hash、indices、fold、mass nonfinite/range、fold zero sum 的代表性分支。 |
| 23 | Medium | Test | `GLM M7` | zero-effective background batch 未测试 | Accept | rereview-confirm 已要求 | 纳入第 4 项。 |
| 24 | Medium | Test | `GLM M8` | 网络层序/dropout/LN eps 未断言 | Accept | 参数量不能固定顺序/eps/dropout | 加 exact module sequence/p/eps tests。 |
| 25 | Medium | Test | `GLM M9` | 多 batch、drop_last、epoch numerator 未测试 | Accept | fixture 始终单 batch | 抽出/使用 raw weighted numerator helper并对多 batch + partial tail 做手算测试。 |
| 26 | Low | Compatibility | `GLM L1` | 原始 split guard 会阻塞 M1-04 合并 development 五折 | Accept | M1-04 fitting 会混合原 train/validation | 移除 train/validation 固定 guard，只要求 indices 来自 validated development 且不重叠。 |
| 27 | Low | Error mapping | `GLM L2` | runtime non-finite metric 错映射 exit3 | Accept | 输入已验证后属于 internal numerical failure | 改抛 `RuntimeError`，由 CLI 映射 70。 |
| 28 | Low | API | `GLM L3` | ValidatedFold 可直接伪造 | Accept | protocol hash 字符串不足以证明 invariants | 加 `__post_init__` 形状/dtype/finite/label/bin/weight/identity/scaler invariants。 |
| 29 | Low | Robustness | `GLM L4` | scaler transform 先广播、fitting_rows 强制转换 | Accept | 可泄露 raw ValueError并接受类型漂移 | 先验证 shape；fitting_rows 要 exact int 非 bool。 |
| 30 | Low | Device | `GLM L5` | device refusal 只隐式 | Partial | API 不接受 device 请求；Windows 无可用非 CPU device | train_fold/network 显式断言 model/input CPU；测试 helper/device string refusal，不强造不可用 CUDA。 |
| 31 | Info | Ordering | `GLM I1` | identity 与 dtype 校验顺序偏离 protocol | Accept | safety-critical split-first 已满足但可 exact 对齐 | 调整为 schema→split→identity→integer/label→numeric→features。 |
| 32 | Info | Consistency | `GLM I2` | 部分常数硬编码、部分从 YAML 读取 | Partial | sealed literal implementation可保留，避免运行时解释扩大面 | 增加代码常数与 protocol.raw exact binding test；schedule/seed 从 protocol properties 读取，network 继续 executable literal + assertion。 |
| 33 | Info | Hygiene | `GLM I3` | hygiene 未测、empty message 误导 | Accept | Sprint 明确要求 | 分开 empty message并断言 error 不含 row/value/path。 |
| 34 | Info | Numerics | `GLM I4` | 用 batch mean 反推 numerator 有 float32 roundtrip | Accept | 与 raw numerator contract 不完全一致 | loss helper返回/提供 raw numerator/denominator，epoch直接累加。 |
| 35 | Info | Global state | `GLM I5` | trainer 修改全局 torch state | Partial | deterministic primitive必须强制该状态 | 文档和 environment 明确 side effect；不恢复为非 deterministic 状态。 |
| 36 | Info | Checkpoint | `GLM I6` | AUC range/state schema未校验 | Accept | 与 Kimi L3 独立一致 | 纳入第 8 项。 |
| 37 | Info | Process | `GLM I6` | Sprint checklist/closure 尚未完成 | Accept | 正处 code-review 阶段 | 修订和最终验证后勾选并记录，不提前宣称完成。 |

## Needs Immediate Action

- 完成所有 Accept 与 high-priority Partial 动作；重点是 sealing、非零 lambda/GRL、
  deterministic/early-stop、future M1-04 compatibility 和 checkpoint/fold invariants。
- 更新 protocol/YAML 的 adversarial-weight tolerance，并在最终验证记录这一显式修订。

## Can Be Deferred

- `validation_scores` 保留为内存便利字段；持久 artifact schema 由后续 Sprint 决定。
- CLI subcommands、production fold algorithm、full-data training 与 authority evidence 不属于 M1-03。

## Final Status

**Accepted after confirmed revisions.** 37 项意见均已按本表决策处理；Accept/Partial 动作已落实，
专项测试 `61 passed`，完整测试 `130 passed, 1 skipped`，`pip check`、两个 CLI help 和
`git diff --check` 均通过。唯一 skip 为 `authoritative_gate_not_run`；未运行 full-data
training、未读取真实数据、未打开 held-out test、未执行 `open-test`。Windows/synthetic
结果不替代 locked native `osx-arm64` 权威 gate。
