# Sprint M1-03 Re-review Report

**Reviewer:** opencode-go/kimi-k2.7-code
**Review type:** Document re-review (post review-confirm)
**Primary target:** `neural/docs/sprint-m1-03.md`
**Bound protocol:** `neural/docs/adversarial-mlp-protocol-v1.md`
**Decision source:** `docs/4-Reviews/sprint-m1-03-review-confirm.md`
**Date:** 2026-09-02

## 1. Executive Summary

All 29 Accept/Partial actions from `sprint-m1-03-review-confirm.md` have been applied correctly in the amended Sprint and protocol. The amended documents are internally consistent with each other and with `FR-001`, `neural_adversarial_mlp_refactor_design.md`, `neural/docs/preprocess-protocol-v1.md`, and both `AGENTS.md` files.

No new Critical, High, or Medium blocker was introduced. The documents are implementation-ready, subject to the Low and Info clarity/consistency findings in §3.

## 2. Decision Source Verification

| No. | Severity | Decision | Applied? | Notes |
|---:|---|---|---|---|
| 1 | High | Accept | Yes | Loader/trainer boundary clarified in Sprint §3 and Protocol §1/§2.1. |
| 2 | High | Partial | Yes | Checkpoint schema deepened; persistence correctly deferred to a later Sprint. |
| 3 | High | Accept | Yes | Validation AUC preconditions in Protocol §8 and Sprint §5.3. |
| 4 | Medium | Partial | Yes | Poison-accessor test order in Sprint §5.1; Protocol §2.1 step ordering. |
| 5 | Medium | Accept | Yes | Lambda whitelist in Protocol §4.3 and Sprint §5.3. |
| 6 | Medium | Accept | Yes | Protocol SHA-256 binding in Protocol §8 and Sprint §3/§5.3. |
| 7 | Medium | Accept | Yes | Empty-bin / zero-sum failure in Protocol §5.3 and Sprint §5.2. |
| 8 | Medium | Accept | Yes | `drop_last=False` in Protocol §6 and Sprint §5.2/§5.3. |
| 9 | Medium | Accept | Yes | No-background batch mechanism in Protocol §5.3/§6 and Sprint §5.2. |
| 10 | Low | Accept | Yes | Fitting definition clarified in Protocol §2.1 and Sprint §3. |
| 11 | Low | Accept | Yes | Error-message hygiene in Protocol §9 and Sprint §5.1. |
| 12 | Low | Partial | Yes | Exit codes bound to `InputBindingError`/3 and 70; no fake paths created. |
| 13 | Low | Accept | Yes | Sprint §10 now records closure evidence. |
| 14 | Info | Accept | Yes | Windows/synthetic authority boundary preserved. |
| 15 | Info | Accept | Yes | Exact parameter counts preserved. |
| 16 | Medium | Accept | Yes | Sprint §7 now lists `pip check`, CLI help, `git diff --check`, and boundaries. |
| 17 | Medium | Accept | Yes | YAML/loader work packages in Sprint §5.1/§8. |
| 18 | Medium | Accept | Yes | Protocol §10 binding in Sprint §5.3. |
| 19 | Medium | Accept | Yes | AdamW weight-decay avoidance in Protocol §5.3/§6 and Sprint §5.2. |
| 20 | Low | Accept | Yes | Warm-up / λ=0 and epoch aggregation in Protocol §9 and Sprint §5.3. |
| 21 | Low | Accept | Yes | Bias / affine / eps in Protocol §4; implicitly bound via Sprint §3 YAML seal. |
| 22 | Low | Accept | Yes | `m4l` range and signal/background binning in Protocol §2.1/§5.1 and Sprint §5.2. |
| 23 | Low | Accept | Yes | Result / environment evidence in Sprint §5.3 via Protocol §9. |
| 24 | Low | Accept | Yes | Failure-diagnosis hygiene test in Sprint §5.1. |
| 25 | Low | Accept | Yes | Protocol header now has status, date, source, and authority platform. |
| 26 | Info | Accept | Yes | Core numbers consistent. |
| 27 | Info | Accept | Yes | M1-02/M1-04 dependencies consistent. |
| 28 | Info | Accept | Yes | MC-only / test / feature boundaries closed. |
| 29 | Info | Accept | Yes | Sprint normative wording tightened; exact `1e-4` test in Sprint §5.3. |

## 3. Findings Table

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| Low | Consistency | `adversarial-mlp-protocol-v1.md` §1 vs §2.1 | §1 states the single-fold trainer accepts a "loader-constructed validated fold object," while §2.1 says the loader outputs a "validated development object" and M1-04 derives folds. | §1: "single-fold trainer 只接受 loader 构造的 validated fold 对象"; §2.1: "loader 输出 validated development 对象；M1-04 将从中编排 OOF folds". | Use a single consistent term: the loader outputs a validated development object; the single-fold trainer receives a validated fold object derived from that development object. |
| Low | Consistency | `adversarial-mlp-protocol-v1.md` §2.1/§5.1 vs `preprocess-protocol-v1.md` §3.2 | The adversarial protocol accepts `105 <= m4l <= 160` and uses a closed last bin `[155,160]`, while the preprocess protocol selects `105 <= m4l < 160`. | Preprocess §3.2 item 18: `105 <= m4l < 160`; Adversarial §2.1: `105 <= m4l <= 160`; Adversarial §5.1: last bin `[155,160]`. | Align the adversarial protocol upper bound with preprocess (`< 160` and `[155,160)`), or add an explicit note that `<= 160` is a defensive superset never triggered by bound M1-02 outputs. |
| Low | Clarity | `sprint-m1-03.md` §5.3 | The Sprint implementation checklist does not explicitly restate the protocol's CUDA/MPS rejection requirement or enumerate the environment evidence fields required by Protocol §9. | Protocol §6: "训练入口必须拒绝 CUDA/MPS device 请求"; Protocol §9 lists environment evidence fields. Sprint §5.3 only says "强制 CPU" and "按协议 §9 返回完整... environment evidence". | Add explicit checklist items: (a) reject CUDA/MPS device requests with `InputBindingError`/3, and (b) capture OS / architecture / Python / PyTorch / device / dtype / thread / deterministic flags. |
| Info | Clarity | `sprint-m1-03.md` §5.3/§6 | Sprint does not explicitly restate that validation runs only the classifier in `eval()` mode and must not run the adversary or update the scaler, model, optimizer, or RNG. | Protocol §8: "validation 只执行 `model.eval()` classifier forward；不得运行 adversary，不得更新 scaler、模型、optimizer 或 RNG-dependent augmentation." Sprint §6 only states test is absent from scaler / training / early-stop / checkpoint. | Add a one-line checklist item in §5.3 stating validation is classifier-forward-only with no adversary, scaler, model, optimizer, or RNG updates. |
| Info | Clarity | `adversarial-mlp-protocol-v1.md` §8 vs §9 | The checkpoint field list uses abbreviated "best AUC" while the result object uses the more explicit "best_validation_weighted_auc". | §8: "best AUC"; §9: "best_validation_weighted_auc". | Use "best_validation_weighted_auc" in the §8 checkpoint field list to avoid any ambiguity about which AUC is stored. |
| Info | Clarity | `sprint-m1-03.md` §5.2 | Sprint does not explicitly restate Protocol §4's requirement that all Linear layers use bias and all LayerNorm layers use affine weight/bias with `eps=1e-5`. | Protocol §4: "所有 Linear 都使用 bias；所有 LayerNorm 都使用 affine weight/bias 和 `eps=1e-5`." Sprint §5.2 only lists layer dimensions. | Add an explicit checklist item or cross-reference to Protocol §4 in §5.2 to ensure these architectural defaults are transcribed into the sealed YAML and tested. |

## 4. Implementation-Readiness Assessment

The amended Sprint and protocol together provide a complete, fail-closed, and deterministic implementation specification for the M1-03 adversarial MLP core. All high-risk items from the prior review have been addressed:

- Dataset loader and single-fold trainer boundaries are separated.
- Checkpoint schema, deep copy, and protocol hash binding are specified.
- Validation AUC preconditions, mass-bin validity, and no-background batch semantics are fail-closed.
- Lambda whitelist, error hygiene, exit codes, and epoch aggregation are explicit.
- Full-data training, held-out test access, and `open-test` remain out of scope and unauthorized.

The Low and Info findings above are polish/consistency items that do not block implementation but would reduce ambiguity for implementers and future reviewers.

## 5. Safety & Authority Boundary Statement

This review was performed as a document-only re-review. No real data was read, hashed, preprocessed, or trained. No held-out test set was accessed and no `open-test` command was run. The review preserves the strict MC-only boundary and confirms that Windows/synthetic results are not treated as authoritative native `osx-arm64` evidence.

---

**Status:** Document gate passes; approved for implementation after addressing Low/Info findings at the implementer's discretion. No Critical / High / Medium blockers.
