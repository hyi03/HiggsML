# Sprint M1-02 Document Review Confirm（复审）

**Reviewed Inputs**

- `neural/docs/sprint-m1-02.md`
- `neural/docs/preprocess-protocol-v1.md`
- `neural/docs/FR-001-adversarial-mlp-refactor.md`
- `neural_adversarial_mlp_refactor_design.md`
- `docs/4-Reviews/sprint-m1-02-review-by-opencode-go-kimi-k2.7-code.md`
- `docs/4-Reviews/sprint-m1-02-review-by-opencode-go-glm-5.2.md`
- `AGENTS.md`、`neural/AGENTS.md` 与评审引用的只读 xgboost 证据

**Review Date**

- 2026-09-01

## Overall Conclusion

两份复审都确认此前两个 Critical 阻塞已解除，协议已达到 M1-02 可实现门。科学常数、
ROOT profile、selection、weight、identity、split、Base14/Angular5、序列化、artifact schema、
golden 与等价谓词均已形成闭合决策，且 MC-only 与平台权威边界未放宽。

本轮没有 Critical/High。13 条可执行的 Medium/Low 意见均是准确的澄清或一致性修复；其中
逐级 cutflow 的数值规则需按所有者已批准政策拆分为“count exact、浮点 tolerance”，故为
Partial。其余接受并立即写回文档。外部 r3 artifact 仍缺失，因此当前只通过文档门，不代表
全量 ARM64 golden 已运行。

## Decision Table

| No. | Severity | Type | Review Source | Original Comment Summary | Decision | Evidence | Follow-up Plan / Rejection Reason |
|---|---|---|---|---|---|---|---|
| 1 | Medium | Clarity | Kimi M1 | `source_entry` 被误读为物理 branch | Accept | `source_entry` 是 reader 生成的 zero-based entry index；旧 reader 也拒绝伪造 branch | 改写 §2.3，明确未声明物理 branch 与物理 `source_entry` 都被拒绝，identity 由 reader 生成。 |
| 2 | Medium | Requirement | Kimi M2 | `all_sfos_mass` 的“所有组合”范围含糊 | Accept | 旧实现遍历四轻子全部 `combinations(4,2)` 中的 SFOS，不限最终 Z partition | 明确为所有可能 SFOS pair，不能只检查 Z1/Z2。 |
| 3 | Medium | Clarity | Kimi M3 | Angular5 frame notation 未定义 | Accept | 公式本身与旧实现一致，但 `l1-_X` 记号缺少 legend | 在公式前定义 charge、frame suffix 与 `.spatial`。 |
| 4 | Medium | Consistency | Kimi M4 | 363490 r2 baseline 易与历史 700600 baseline 混淆 | Accept | 两条 run lineage 服务不同 DSID，只有带 `363490-r2` 的 manifest 绑定当前协议 | 在 §7.1 显式排除 `full-baseline-2026-08-10`。 |
| 5 | Low | Clarity | Kimi L1 | `.17g` 是否可交给 pandas 不明确 | Accept | canonical hash 依赖 token，而非库 API 名称 | 明确逐标量 token 结果必须等价；任何 writer 都须证明产生相同 bytes。 |
| 6 | Low | Test | Kimi L2 | Sprint 工作包未重述 synthetic-only fixture | Accept | Protocol §9 已冻结该规则，但 Sprint checklist 应可直接验收 | 在 5.1/5.2 测试项中链接 §9 并明确不提交真实/MC 派生 fixture。 |
| 7 | Info | Completeness | Kimi I1 | Golden 与 tolerance 已闭合 | Accept (positive) | 三份 neural 文档一致绑定 r3 table、exact/tolerance 与 ARM64 | 无修改，保持。 |
| 8 | Info | Completeness | Kimi I2 | 科学常数已自包含 | Accept (positive) | Protocol §2–§5 可独立实现 | 无修改，保持。 |
| 9 | Info | Consistency | Kimi I3 | 29 列、行序和映射已确定 | Accept (positive) | Protocol §6–§7 明确旧新映射 | 无修改，保持。 |
| 10 | Info | Safety | Kimi I4 | MC-only/fail-closed/不可变边界正确 | Accept (positive) | 与根及 neural AGENTS 一致 | 无修改，后续实现必须保持。 |
| 11 | Medium | Consistency | GLM M1 | 根设计称 run config 含 output path，与 protocol 冲突 | Accept | M1-01 CLI 已把输出事务绑定到 `--run-dir`；新协议精确白名单不含 output | 修改根设计 §6.1，声明路径仅两个 ROOT，输出只由 `--run-dir`。 |
| 12 | Medium | Clarity | GLM M2 | manifest outputs 句子把 summary/manifest “自身”写混 | Accept | 正确无自引用集合应是 config、表、cutflow、summary，排除 manifest | 枚举四项并明确仅排除 manifest 自身。 |
| 13 | Medium | Edge case | GLM M3 | Boost 公式遗漏 `beta=0` identity case | Accept | 旧 Angular5 在除法前原样返回；字面公式会除零 | 在 §4.3 冻结零 beta identity boost。 |
| 14 | Low | Clarity | GLM L1 | “前八个质量阶段”与 exactly-four 冲突 | Accept | `exactly_four_good_leptons` 之前的 filtering stages 是至少四个，该 stage 自身恰好四个 | 改为按语义描述，不使用错误计数。 |
| 15 | Low | Verification | GLM L2 | 未明确逐级 cutflow 比较 | Partial | Stage count 属结构 exact；efficiency/yield 是浮点，应服从已批准 `rtol/atol=1e-12`，不能全 exact | 增加两个样本所有 stage count exact；对应效率/加权产额按浮点容差比较。 |
| 16 | Low | Consistency | GLM L3 | Sprint run-config 简述漏 schema/nesting | Accept | Protocol 白名单是 `schema_version/samples/resources` | Sprint 改为精确内容说明并继续引用 protocol。 |
| 17 | Low | Status | GLM L4 | Protocol “已批准”与 Sprint “等待复审”冲突 | Accept | 所有者批准的是 golden/policy；协议全文在本确认完成后才通过文档门 | 协议状态改为“文档复审通过，等待实现验证”，Sprint 交付结论同步。 |
| 18 | Info | Verification | GLM I1 | artifact-dependent duplicate/lineage 需在 gate 复验 | Partial | 本机已验证 baseline manifest `10e0...`；r3 identity/enrichment 仍外部缺失 | 不改变决策；实现测试 baseline binding，ARM64 gate 再验证 r3 hashes/duplicates，并记录未运行边界。 |
| 19 | Info | Consistency | GLM I2 | Golden hashes/counts/predicate 内部一致 | Accept (positive) | 数字求和及 frozen config 证据一致 | 无修改，保持。 |
| 20 | Info | Safety | GLM I3 | 安全、CLI 与 fixture 边界完整 | Accept (positive) | Protocol §1/§2/§9 与 AGENTS 一致 | 无修改，实施测试必须覆盖。 |

## Needs Immediate Action

- 应用第 1–6、11–17 项文档修订。
- 修订后以 `git diff --check` 和协议关键字段检查确认文档门完整。

## Can Be Deferred

- 外部 r3 enrichment/identity artifact 与绑定 ROOT 的全量逐列比较只能在锁定 ARM64 环境执行；
  当前状态必须保持 `authoritative_gate_not_run`。
- 五折 development fold 规则在后续 OOF Sprint 开始前另行冻结，不属于 M1-02 输出。

## Final Status

`Accepted for implementation after applying the listed documentation actions`。本确认不授权
`open-test`，也不代表权威 full-data gate 已通过。
