# Sprint M1-03 Review Report

- **Reviewer:** opencode-go / kimi-k2.7-code
- **Review date:** 2026-09-02
- **Review type:** Document review
- **Target document:** `neural/docs/sprint-m1-03.md`
- **Linked review targets:**
  - `neural/docs/adversarial-mlp-protocol-v1.md` (bound protocol)
  - `neural/docs/FR-001-adversarial-mlp-refactor.md`
  - `neural_adversarial_mlp_refactor_design.md`
  - `AGENTS.md` (repository root)
  - `neural/AGENTS.md`

## Executive Summary

`sprint-m1-03.md` correctly binds `adversarial-mlp-protocol-v1.md` as the normative implementation specification for the fixed-scale adversarial MLP core. The Sprint preserves the MC-only boundary, forbids `m4l`/identifiers/weights as classifier features, requires deterministic CPU training, and defers five-fold OOF orchestration and qualification to M1-04, consistent with `FR-001`, the refactor design, and both `AGENTS.md` files.

No Critical scientific-safety or correctness blockers were found. The most important gaps are at the **Sprint/protocol boundary**: the Sprint does not fully mirror the protocol's input-frame contract, checkpoint minimum contents, or validation-set composition checks, which could lead to an implementation that passes the Sprint's acceptance criteria while failing the bound protocol. The remaining findings are clarity, consistency, and test-coverage improvements.

**Overall verdict:** The Sprint is **scientifically safe and decision-ready for implementation** after the High and Medium findings below are addressed or explicitly acknowledged.

## Review Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| High | Consistency / Requirement | `sprint-m1-03.md` §3 vs `adversarial-mlp-protocol-v1.md` §2.1 | The Sprint says M1-03 "只接受调用方已隔离的 development fitting/validation frame", while the bound protocol states the loader入口 receives the full 29-column development MC table and validates `split` ∈ {train, validation}. These two contracts are not the same: the first describes already-folded frames, the second describes the raw development table. | Protocol §2.1: "入口接收已由 M1-02 产出的 29 列 MC 表"; Sprint §3: "M1-03 只接受调用方已隔离的 development fitting/validation frame". | Clarify that the dataset **loader** accepts the full 29-column development table (protocol contract), validates schema/split/identity, and extracts 15 features; the **single-fold trainer primitive** then accepts fitting/validation tensors produced by the loader or a test harness. Do not allow the trainer to silently accept frames that have bypassed protocol validation. |
| High | Requirement / Consistency | `sprint-m1-03.md` §5.3 vs `adversarial-mlp-protocol-v1.md` §8 | Sprint requires "checkpoint 只按 fold validation weighted AUC 选择" but does not enumerate the protocol-mandated checkpoint minimum contents. An implementation could pass the Sprint while emitting a checkpoint missing the protocol SHA-256, feature tuple, scaler, fold seed, or best-epoch metadata. | Protocol §8 lists minimum checkpoint content: protocol SHA-256, feature tuple, scaler, fold index, fold seed, target lambda, best epoch, best AUC, classifier/adversary state dict. Sprint §5.3 only says "记录 epoch 指标、吞吐、耗时和失败诊断". | Add an explicit implementation task: checkpoint must be a deep CPU copy containing **all** fields required by protocol §8, and deserialization must reject any checkpoint missing a field or with a mismatched protocol SHA-256. |
| High | Correctness / Test | `sprint-m1-03.md` §5.3 vs `adversarial-mlp-protocol-v1.md` §8 | Sprint requires validation weighted AUC for checkpoint selection but omits the protocol's precondition that validation must contain both label 0 and label 1, finite non-negative weights, and weight sum > 0. A fold with only one class would produce an undefined AUC and could silently corrupt early stopping. | Protocol §8: "validation 必须同时包含 label 0 与 1，权重有限非负且总和大于零。" Sprint §5.3 does not list these preconditions. | Add a validation-composition check to implementation and test tasks; fail closed with exit code 3 if any precondition is violated. |
| Medium | Data Safety / Test | `sprint-m1-03.md` §5.1 | The Sprint requires a synthetic test with "带毒 test feature ... 证明入口在读取 feature values 前拒绝 test split", but it does not explicitly assert that refusal happens before identity/uniqueness/finiteness checks or any statistic computation. | Protocol §2.1 validation order: split check is step 2, before identity, finiteness, and feature extraction. Sprint §3 says rejection must happen "在 scaler、tensor、模型或 metric 构造前". | Tighten the test to assert that a `split=test` row is rejected immediately after the split validation step, before any other column is read, hashed, or summarized. |
| Medium | Consistency / Requirement | `sprint-m1-03.md` §5.3 | Sprint references the protocol for the lambda schedule but does not restate that only target lambda values in `{0.00, 0.05, 0.10, 0.20, 0.50}` are allowed, nor that the schedule is immutable. | Protocol §4.3: "目标 lambda 只允许 0.00, 0.05, 0.10, 0.20, 0.50。" Sprint §5.3: "不允许 CLI/运行配置修改 schedule." | Add an explicit task: reject any target lambda outside the pre-registered set and any attempt to override warm-up/ramp/max-epoch boundaries. |
| Medium | Audit / Consistency | `sprint-m1-03.md` §3, §5.3 vs `adversarial-mlp-protocol-v1.md` §8 | Sprint requires the YAML to "逐项转录并密封" the protocol, but it does not explicitly require computing and storing the protocol file's SHA-256 in the checkpoint, which the protocol mandates. | Protocol §8 checkpoint minimum content includes "protocol SHA-256"; Sprint §3 uses "密封" but does not define it as a SHA-256 binding. | Define "密封" as: compute SHA-256 of the bound `adversarial_mlp_protocol_v1.yaml` at load time, store it in the checkpoint, and fail closed on mismatch. Add this to both §3 and §5.3. |
| Medium | Correctness / Test | `sprint-m1-03.md` §5.2 | Sprint requires verifying "11 个质量 bin 总权重相等" but does not explicitly require the fail-closed behavior when a mass bin is empty or has zero absolute-weight sum. | Protocol §5.3: "11 个 bin 必须全部非空且每个 bin 的 absolute-weight sum 大于零，否则 fold 关闭式失败。" | Add an explicit test/implementation task: assert all 11 bins are non-empty and each bin's `abs(physical_weight)` sum is positive; otherwise fail closed. |
| Medium | Correctness / Test | `sprint-m1-03.md` §5.3 vs `adversarial-mlp-protocol-v1.md` §6 | Sprint states batch size `1024` and maximum epochs `200` but does not mention the protocol's rule that the last incomplete batch must be retained and not dropped. | Protocol §6: "最后一个不完整 batch 保留；不得 drop。" Sprint §5.3 only gives batch size and max epochs. | Add an explicit task: DataLoader/sampler must retain the final incomplete batch (`drop_last=False` semantics). |
| Medium | Correctness / Test | `sprint-m1-03.md` §5.2 vs `adversarial-mlp-protocol-v1.md` §5.3 | Sprint implementation tasks do not mention the edge case where a batch contains no background rows. | Protocol §5.3: "batch 无背景行时 `L_adv` 为连接到 classifier logit 的 differentiable zero；对抗器不更新。" | Add an implementation task and unit test: when a batch has zero background rows, `L_adv` is a differentiable zero tied to the classifier logit and the adversary parameters receive no update. |
| Low | Clarity / Consistency | `sprint-m1-03.md` §3, §5.1 vs `adversarial-mlp-protocol-v1.md` §2.1 | Sprint uses "development fitting/validation frame" and "fitting 子集", while the protocol's `split` column values are `train` and `validation`. The mixed terminology could be read as introducing a new `fitting` split value. | Protocol §2.1 allows `split` ∈ {train, validation}; design §8.1 uses "fitting" for the fold-local training portion. | Add a one-sentence definition: in M1-03, "fitting" means the fold-local training portion derived from development rows whose `split` is `train`; no new `split` value is introduced. |
| Low | Documentation / Security | `sprint-m1-03.md` §5.1, §6 | Sprint does not include the protocol's constraint that error messages must not dump event rows, feature values, or paths. | Protocol §9: "错误消息只能包含规则名称、列名和计数，不得转储 event row、feature values 或路径内容。" | Add an implementation task and a unit test to verify that raised errors contain only rule/column/count metadata and no row data, feature values, or filesystem paths. |
| Low | Maintainability / Consistency | `sprint-m1-03.md` §5–§6 vs `neural/AGENTS.md` §Stable process exit codes | Sprint does not reference the stable exit codes defined in `neural/AGENTS.md` for schema/protocol failures (3), run-path failures (4), or qualification refusals (5). | `neural/AGENTS.md` defines exit codes 0/2/3/4/5/70. | Add a cross-reference or task: all fail-closed paths in M1-03 must use the appropriate stable exit code (e.g., 3 for schema/protocol binding failures, 5 for any test-opening-like refusal). |
| Low | Documentation | `sprint-m1-03.md` §10 | Section 10 "交付结论" is intentionally left as a placeholder. | Sprint §10: "待实施、评审确认和验证后填写。" | Add a note that this section is completed at sprint close-out and must include pass/fail evidence for each acceptance criterion in §6, plus a statement that no real data or held-out test was used. |
| Info | Positive / Safety | `sprint-m1-03.md` §6, §7 | Sprint correctly states that Windows/synthetic results cannot substitute for the locked native `osx-arm64` authority gate. | Sprint §6: "Windows 结果不得替代锁定原生 `osx-arm64` 的后续权威 gate." | No change required. Keep the caveat in §6 and any run logs. |
| Info | Positive / Consistency | `sprint-m1-03.md` §5.2 | Sprint correctly requires exact assertions for classifier `7,617`, adversary `1,611`, and full-model `9,228` trainable parameters, matching the protocol and design. | Protocol §4.1, §4.2; design §8.2, §8.3. Independent verification confirms the counts. | No change required. Maintain the exact-count tests. |

## Detailed Assessment

### 1. Scientific Safety

- **MC-only and forbidden features:** The Sprint and protocol preserve the MC-only boundary. Classifier features are fixed at 15, and `m4l`, identifiers, provenance, split, and weight columns are forbidden (protocol §2.2; Sprint §3, §6).
- **Held-out test discipline:** Both documents require that any `split=test` row be rejected before feature values are read, and that test data never enters scaler fitting, training, AUC computation, early stopping, or checkpoint selection (protocol §1, §2.1, §8; Sprint §3, §6).
- **No result framing as physics:** Both documents describe output as educational/technical demo, consistent with `AGENTS.md` and `neural/AGENTS.md`.
- **Immutable/frozen runs:** The Sprint defers five-fold OOF, qualification, and final development model release to M1-04, keeping M1-03 focused on auditable single-fold primitives.

### 2. Internal Consistency

- **Sprint ↔ Protocol:** The Sprint correctly binds `adversarial-mlp-protocol-v1.md` as the normative source. Schedule (warm-up 1–5, ramp 6–15, plateau 16–200), batch size, optimizer, early-stopping threshold (`1e-4`), patience (`20`), and exact parameter counts are consistent.
- **Protocol ↔ FR-001 / Design:** The protocol satisfies FR-001 R3 (fixed 15-feature adversarial MLP, GRL, 11 mass bins) and R7 (tests). It matches the design's network topology, λ candidate set, warm-up/ramp schedule, and deterministic CPU training policy.
- **Minor boundary inconsistency:** The only significant inconsistency is the input-frame contract noted in the first High finding. Once clarified, the Sprint and protocol will be fully aligned.

### 3. Correctness Risks

- **Validation AUC:** The missing validation-composition precondition is the main correctness risk. A synthetic fixture that happens to place all signal rows in one fold's validation set would make AUC undefined.
- **Empty mass bins:** With only ~11k ZZ background events and 11 bins, empty bins are unlikely on full data but possible on small synthetic fixtures. The fail-closed rule must be explicitly implemented and tested.
- **Incomplete batch:** On small synthetic data, an incomplete final batch is common. Dropping it would change gradients and break determinism.
- **No-background batch:** A batch containing only signal rows must not crash the trainer or update the adversary.

### 4. Completeness of Test Coverage

The Sprint's test requirements are broad but miss a few protocol-mandated edge cases and metadata checks. Adding the recommendations above will make the test suite sufficient to enforce the bound protocol without requiring the implementer to re-read the protocol for implicit rules.

## Conclusion

`neural/docs/sprint-m1-03.md` and the bound `neural/docs/adversarial-mlp-protocol-v1.md` form a **scientifically safe and largely consistent implementation plan**. The Sprint is **approved for implementation** after addressing the three High findings (input-frame contract, checkpoint content, validation composition) and the six Medium findings (test-refusal timing, lambda whitelist, protocol SHA-256 binding, empty-bin handling, incomplete-batch retention, and no-background-batch behavior). The Low and Info findings are optional but recommended for clarity and auditability.

No source code, real data, or held-out test data were accessed or modified in the preparation of this review.
