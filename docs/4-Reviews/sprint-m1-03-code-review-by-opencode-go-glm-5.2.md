# Sprint M1-03 Code Review (by opencode-go / glm-5.2)

- **Review type**: code review (independent; no other M1-03 code review was read)
- **Baseline**: commit `aebf0ce` (working tree, tracked diff + untracked files)
- **Review date**: 2026-09-02
- **Reviewer environment**: Windows dev verification only (`conda run -n pytorch`); not the locked
  native `osx-arm64` authority platform

## 1. Reviewed inputs

Primary implementation files (all untracked vs `aebf0ce`):

- `neural/config/adversarial_mlp_protocol_v1.yaml`
- `neural/src/training/config.py`
- `neural/src/training/dataset.py`
- `neural/src/training/network.py`
- `neural/src/training/losses.py`
- `neural/src/training/trainer.py`
- `neural/tests/training_fixtures.py`
- `neural/tests/unit/test_training_config.py`
- `neural/tests/unit/test_dataset.py`
- `neural/tests/unit/test_network.py`
- `neural/tests/unit/test_losses.py`
- `neural/tests/integration/test_deterministic_training.py`

Tracked-file diffs vs `aebf0ce`:

- `neural/docs/sprint-m1-03.md` (document-gate amendments: protocol content gate, expanded
  checklists, verification commands, closure evidence requirements)
- `neural_adversarial_mlp_refactor_design.md` (§8.2/§8.3 "约" → exact `7,617` / `1,611` / `9,228`)

Related untracked docs: `neural/docs/adversarial-mlp-protocol-v1.md` (protocol source of truth).

Sources of truth used: `neural/docs/sprint-m1-03.md`,
`neural/docs/adversarial-mlp-protocol-v1.md` (hereafter "Protocol"),
`neural/docs/FR-001-adversarial-mlp-refactor.md` (hereafter "FR"),
`neural_adversarial_mlp_refactor_design.md` (hereafter "Design"),
`docs/4-Reviews/sprint-m1-03-review-confirm.md`,
`docs/4-Reviews/sprint-m1-03-rereview-confirm.md`, root `AGENTS.md`, `neural/AGENTS.md`.
`docs/4-Reviews/sprint-m1-03-code-review-by-opencode-go-kimi-k2.7-code.md` was present in the
tree but deliberately not read, per review instructions.

## 2. Verification evidence (what was actually run)

All runs are synthetic-only. No real data was read, hashed, or probed; no held-out test was
accessed; no full-data training and no `open-test` were executed.

| Command (from `neural/`) | Result |
|---|---|
| `conda run -n pytorch python -m pytest -q tests/unit/test_training_config.py tests/unit/test_dataset.py tests/unit/test_network.py tests/unit/test_losses.py tests/integration/test_deterministic_training.py` | 29 passed (7.7 s) |
| `conda run -n pytorch python -m pytest -q` (full suite) | 98 passed, 1 skipped (13.0 s); skip = golden authority gate, correctly refused: `authoritative_gate_not_run: external r3-ARM64 table is absent` |
| `conda run -n pytorch python -m pip check` | No broken requirements found |
| `conda run -n pytorch higgsml-preprocess --help` / `higgsml-train --help` | Both print usage (exit 0) |
| `git diff --check` (repo root) | Clean |

Additional synthetic probes run to substantiate findings (temp scripts, deleted afterwards;
imports only `src.training.*` and the synthetic fixture):

- **Sealing type-drift probe**: a mutated YAML with `linear_bias: 1`, `variance_ddof: false`,
  `drop_last: 0`, `warmup_epochs: 5.0`, `deterministic_algorithms: 1` was **accepted** by
  `load_training_protocol` (Finding H1).
- **Key-order probe**: a YAML with reordered keys inside `dtypes` and `classifier` was
  **accepted** with a different SHA-256 (`28e0048a…`, vs the checked-in hash) (Finding M1).
- **Bin-weight exactness probe**: per-bin `adv_weight` totals deviate from 1 by up to
  `3.7e-8`, including when `physical_weight` is supplied as float64, because
  `adversarial_bin_weights` unconditionally casts to float32 (Finding M4).
- **Training probes** (`train_fold`, synthetic fixture): `target_lambda=0.05` and `0.50` run
  end-to-end without error (21 epochs, early stop); warm-up epochs 1–5 are bit-identical across
  lambdas (init/batch-order reuse works); but validation weighted AUC is exactly `0.5` in every
  epoch for every lambda, `best_epoch` is always 1, and the checkpointed adversary state is
  identical (untrained) across lambdas (Findings H2/H3).
- **GRL composed-gradient probe** (eval mode): loss is lambda-independent in forward; classifier
  logit gradient from `L_adv` equals `-lambda * dL_adv/dlogit` bitwise for lambda 0.5/0.25 vs
  1.0; signal rows receive exactly zero adversarial gradient; adversary parameters receive
  nonzero gradients. The composed mechanics are correct — but no test in the suite provides this
  evidence (Finding H2). A first probe version incorrectly suggested a scaling mismatch; that
  was a probe artifact (dropout active in train mode), re-verified clean in eval mode.
- **Poison-accessor probe**: a `pd.DataFrame` subclass that raises on any `__getitem__` other
  than `"split"` is rejected with `InputBindingError: development frame contains forbidden split`
  without triggering the poison — the test-first read ordering is implemented correctly, but no
  suite test proves it (Finding M5).
- **Out-of-range mass probe**: `m4l = 104.9999` is rejected fail-closed by `mass_bin_indices`
  (correct behavior; uncovered by tests, Finding M6).

## 3. Findings

Severity values: Critical, High, Medium, Low, Info. No Critical findings (no data/test leakage,
no wrong-science path, no training corruption found).

| # | Severity | Type | Location | Issue | Evidence | Recommendation |
|---:|---|---|---|---|---|---|
| H1 | High | Protocol sealing | `neural/src/training/config.py:123`; `neural/tests/unit/test_training_config.py:26-57` | Sealed-protocol comparison `raw != _EXPECTED` uses Python deep equality, which accepts cross-type equal scalars (`True == 1`, `False == 0`, `5 == 5.0`). Type changes are a pre-declared rejected mutation category (Protocol §1 "类型变化"; Sprint §3/§5.1 "类型…变化均关闭式失败") but several type mutations pass sealing. | Probe: one mutated YAML with `linear_bias: 1` (int for bool), `variance_ddof: false` (bool for int), `drop_last: 0`, `deterministic_algorithms: 1`, `warmup_epochs: 5.0` (float for int) loaded successfully. The mutation test matrix covers value/missing/extra/duplicate only — no type or order cases (Protocol §10 requires each frozen block's type/order/value drift to be tested). | Replace deep `==` with a type-strict recursive comparison (reject unless `type(x) is type(y)`, comparing `bool` before `int` because `bool` subclasses `int`), or compare canonicalized bytes. Add parametrized type-mutation and order-mutation loader tests. |
| H2 | High | Missing test | `neural/tests/integration/test_deterministic_training.py:38-51`; `neural/tests/unit/test_network.py` | No executable evidence for the Sprint §6 acceptance criterion "合成数据证明 GRL 使分类器朝增大背景质量分类损失的方向更新" (also FR-001-R7, Design §12.2, Protocol §10 "GRL forward identity、梯度符号与 lambda 缩放；信号不进入 adversary" at training level). No test ever calls `train_fold` with `target_lambda > 0`; the only composed-model test is the isolated `gradient_reverse` unit test. The determinism test also compares only `classifier_state_dict`, never the adversary state. | Suite inspection: the only `train_fold` calls use `target_lambda=0.0`. Probe confirms the composed mechanics are correct (adversary minimizes `L_adv`; classifier logit receives exactly `-lambda * dL_adv/dlogit`; signal rows get zero adversarial gradient; adversary params get nonzero grads) — but this evidence exists only outside the suite. | Add (a) a composed-model gradient test in eval mode: one backward of `L_adv` through `model.adversary(model.classifier(x)[bg], lambda)` asserting adversary param grads nonzero and classifier logit grad equal to `-lambda`-scaled pure-adversary grad, signal rows zero; (b) a small `train_fold(target_lambda>0)` test on a discriminative fixture asserting the adversary state in the checkpoint differs from initialization and from a `lambda=0` run. |
| H3 | High | Test design | `neural/tests/training_fixtures.py:16-19` | The synthetic fixture is non-discriminative: feature values depend only on `local_index`/`feature_index`, not on `label`, so signal and background rows are bitwise identical in all 15 features. Every training-level test therefore runs on a degenerate trajectory: AUC exactly 0.5 each epoch, `best_epoch` always 1, early stop at epoch 21, and the best checkpoint always contains the untrained (initial) adversary. Checkpoint replacement on improvement, the `1e-4` improvement boundary, patience reset, and any observable adversarial influence are never exercised. | Probe: `lambda=0/0.05/0.50` all yield `best_auc=0.5`, 21 epochs, `best_epoch=1`, `is_best=[True, False×20]`, and identical `adversary_state_dict` across lambdas (adversary at init because checkpoint is taken at epoch 1). | Make fixture features label-dependent (e.g., add a label-dependent offset to a few features) so validation AUC improves across epochs and the checkpoint/patience-reset paths execute; optionally keep one constant-AUC case for the pure-early-stop path. This also unlocks H2's lambda>0 test. |
| M1 | Medium | Protocol sealing | `neural/src/training/config.py:123` | Mapping key order is not enforced: dict equality ignores key order, so a YAML with reordered keys inside frozen blocks passes sealing while producing a different protocol SHA-256. Protocol §1 lists "顺序变化" among rejected mutations; list order (features, edges) is correctly enforced because list equality is order-sensitive. Consequence: two byte-different YAMLs are both accepted as "the sealed protocol" yet bind different hashes into checkpoints — protocol identity becomes ambiguous. | Probe: YAML with `dtypes`/`classifier` key order reversed accepted with `sha256=28e0048a…` ≠ checked-in hash. No key-reorder mutation test exists. | Enforce key order recursively (compare `list(raw.keys())` at each level, or compare against a canonical serialization), or explicitly narrow the pre-declared "顺序变化" to list order in the protocol; add a key-reorder mutation test either way. |
| M2 | Medium | Missing test | `neural/src/training/trainer.py:162-173` (logic); no covering test | Early-stopping rules are untested: Sprint §5.3 and Protocol §10/§8 require evidence that equal or ≤`1e-4` AUC improvement does not replace the checkpoint, that replacement resets patience, and that 20 consecutive non-improving epochs stop training. No test asserts `stopped_early`, `is_best` trajectories, or checkpoint non-replacement on ties. | Suite inspection: no assertions on `stopped_early`/`is_best`/non-replacement anywhere. (Probe shows the degenerate fixture stops at epoch 21, but that path is unasserted and the boundary/tie cases are unreachable with a constant AUC.) | Add a targeted test with a discriminative fixture (per H3) or a unit harness with injected AUC sequences covering: improvement > `1e-4` replaces; improvement exactly `1e-4` does not; equal AUC does not; 20 non-improving epochs stop; a later improvement resets patience. |
| M3 | Medium | Missing test | `neural/src/training/trainer.py:109,116` (mechanism); `neural/tests/integration/test_deterministic_training.py` (missing) | Different-lambda init/batch-order reuse is untested. Protocol §6 ("不同目标 lambda 在同 fold 开始前重置相同 fold seed，从而复用 exact 初始化和 epoch-by-epoch shuffle 顺序"), Protocol §10, and Sprint §5.3 all require it. | Probe: warm-up epochs 1–5 (`train_cls_loss`, `validation_weighted_auc`) are exactly equal across `target_lambda=0.05` and `0.50` — the mechanism (per-call `_seed(fold_seed)` + dedicated shuffle `Generator`) works; no suite test asserts it. | Add a test running two lambdas on the same fold and asserting epochs 1–5 metrics are exactly equal (and that post-ramp epochs diverge), plus adversary-state divergence per H2. |
| M4 | Medium | Correctness / numerics | `neural/src/training/losses.py:40`; `neural/tests/unit/test_losses.py:43` | `adversarial_bin_weights` unconditionally casts `abs(physical_weight)` to float32 before per-bin normalization, so each bin's total `adv_weight` deviates from exact 1 by ~`4e-8`. Protocol §5.3 pre-declares "每个 mass bin 的总 adv_weight exact 为 1（允许测试比较容差 rtol=1e-12, atol=1e-12）" — unmet — and the test quietly widens tolerance to `1e-6`, which has no protocol basis and masks the deviation. | Probe: max per-bin `|total-1| = 3.7e-8` for float32 and float64 physical weights alike (cast is unconditional); a `1e-12` test would fail. | Normalize in float64 (per-bin division in float64, verify totals within `1e-12`, then cast to float32 for optimization), or record an explicit protocol amendment justifying the float32 tolerance and keep the test at the pre-declared value. |
| M5 | Medium | Missing test | `neural/tests/unit/test_dataset.py:34-49` | Poison-accessor ordering evidence is missing. Sprint §5.1 and review-confirm item 4 (Kimi M1) require a probe proving the entry refuses `split=test` before reading identity/feature values, hashes, or statistics — not merely that it refuses. | Current test only asserts `InputBindingError` on a test-split frame. Probe with a `__getitem__`-poison DataFrame subclass confirms the implementation refuses having touched only `columns` and `"split"` — evidence not in the suite. | Add the poison-accessor test: a DataFrame subclass that records/raises on column access, asserting only `split` is read before the refusal (and documenting that the frame object itself is materialized, per the confirm decision). |
| M6 | Medium | Missing test | `neural/tests/unit/test_dataset.py`; `neural/tests/unit/test_losses.py:34-43` | The dataset/fold/mass mutation matrix is incomplete relative to Sprint §5.1/§5.2 and Protocol §10. Untested fail-closed paths include: frame-level identity empty/duplicate, label/integer dtype drift (e.g., float label), `m4l` out-of-range or non-finite at frame level, negative `train_weight`, invalid `protocol_sha256`, non-integer/out-of-range/empty/duplicate fold indices, `fold_index` outside 0–4, and `mass_bin_indices` out-of-range/non-finite masses. Fold-level zero absolute-weight bin ("fold zero sum" in Sprint §5.2) is also untested. | Suite covers missing/extra/reordered columns, NaN feature, test split, identity overlap, and one empty-bin case only. Probe incidentally confirmed `m4l=104.9999` is rejected (no test). | Extend the parametrized mutation tests to the listed cases, including the fold-level zero-sum bin (all-zero `abs(physical_weight)` in one bin). |
| M7 | Medium | Missing test | `neural/src/training/trainer.py:143-150`; `neural/tests/unit/test_losses.py:46-60` | The "background rows present but batch adversarial-weight sum zero" path is untested. Rereview-confirm item 8 (GLM R2) explicitly accepted the semantics and required a test: "视为'无有效背景权重'并走同一 differentiable-zero/no-adversary-update 路径；增加测试." The suite only tests the all-signal (no background rows) batch. | `trainer.py` implements the branch (`torch.any(background) and adv_weights.sum().item() > 0.0`), but no test constructs a batch with background rows whose adv weights are all zero. | Add a test: batch containing background rows with zero adversarial weights (zero `abs(physical_weight)` rows surviving fold validation) → `0.0 * logits.sum()` path, no adversary forward, adversary grads `None`, parameters unchanged after `step()`. |
| M8 | Medium | Missing test | `neural/src/training/network.py:29-34,45-49`; `neural/tests/unit/test_network.py:8-18` | Network structure details are not asserted: layer order (LayerNorm/SiLU/Dropout sequence), dropout placement (first two blocks only), dropout probability `0.10`, and LayerNorm `eps=1e-5`. Parameter counts pin widths, bias, and affine (removing any changes the count) but not ordering, eps, or dropout p. Protocol §10 requires "网络 shape、层序、dropout、LayerNorm 与 exact 参数量". | `test_network.py` asserts shapes and counts only; structure is verified only by reading source. | Assert the `nn.Sequential` composition: module types in exact order, dropout modules present only in blocks 1–2 with `p=0.10`, all `LayerNorm` with `eps=1e-5` and affine parameters. |
| M9 | Medium | Missing test | `neural/src/training/trainer.py:129-154`; `neural/tests/training_fixtures.py` | Epoch-loss numerator/denominator aggregation and multi-batch `drop_last=False` are untested (Sprint §5.3: "验证 …`drop_last=False` 和 epoch loss numerator/denominator 聚合"). The fixture has 22 fitting rows < `batch_size=1024`, so every epoch is a single (incomplete) batch; the final-partial-batch-retained semantics and cross-batch weighted aggregation never execute under test. | Suite inspection: no test compares an epoch's `train_cls_loss` to a hand-computed weighted aggregate over batches; no test has >1024 fitting rows. | Add an epoch-aggregation test (hand-computed weighted mean across ≥2 batches) using a synthetic frame with more than `batch_size` fitting rows, asserting the last partial batch is processed. |
| L1 | Low | Protocol deviation | `neural/src/training/dataset.py:142-143` | `build_validated_fold` additionally requires fitting rows to have `split=="train"` and validation rows `split=="validation"` — a constraint Protocol §2.1 does not state (it requires only non-empty, unique, disjoint partitions). Defensible fail-closed strictness for M1-03, but Design §9.1 / FR-001-R4 merge original train+validation into development for the M1-04 five-fold scheme, whose fold fitting subsets will contain original `validation`-split rows; this guard will block them. | Code raises `"fold partition split changed"` for any mixed partition; protocol text requires only non-empty/unique/disjoint; M1-04 fold algorithm is explicitly out of M1-03 scope. | Either document this as an M1-03-only guard that M1-04 must revisit at its document gate, or relax to "indices drawn from the validated development object" so a sealed behavior does not have to be unfrozen later. |
| L2 | Low | Error mapping | `neural/src/training/trainer.py:160-161` | A NaN/Inf AUC or epoch loss mid-training raises `InputBindingError` (CLI exit 3). Inputs were already validated finite at entry, so a runtime non-finite metric is an unexpected internal numerical failure; Protocol §9 maps unexpected internal failures to 70 and reserves `InputBindingError` (exit 3) for schema/protocol/data-contract failures. | `raise InputBindingError("non-finite training metric")` at the only runtime-metric check. | Use the internal-error exception family (exit 70) for runtime non-finite metrics, or record the mapping decision in the protocol. |
| L3 | Low | API hardening | `neural/src/training/dataset.py:70-85`; `neural/src/training/trainer.py:104-108` | `ValidatedFold` is a public dataclass whose constructor accepts arbitrary tensors; `train_fold` cannot verify the fold was produced by `build_validated_fold`. Protocol §2.1: "single-fold trainer 只接受从 validated development 对象构造的 validated fold，不接受绕过 validator 的任意 frame/tensor." The `protocol_sha256` string field is spoofable by direct construction. | Dataclass has no invariants; `train_fold` only string-compares `fold.protocol_sha256 == protocol.sha256`. | Add `__post_init__` invariants on `ValidatedFold` (features float32 `(N,15)` finite; labels int64 in {0,1}; both labels present in validation; weights finite non-negative with positive validation sum; bins in `{-1} ∪ {0..10}` with `−1` exactly on signal rows; adversarial weights zero on signal rows; non-empty fitting) so crafted folds fail closed at construction. |
| L4 | Low | Robustness / error mapping | `neural/src/training/dataset.py:40-45,51-61` | `FoldLocalScaler.transform` performs the arithmetic `(values - mean)/scale` before validating ndim/width, so a wrong-width input raises a raw NumPy broadcast `ValueError` (unexpected internal error, exit 70) instead of `InputBindingError` (exit 3); `fit` validates shape first — inconsistent. `from_dict` `int()`-coerces `fitting_rows`, accepting `"5"` or `5.0`. | Code order in `transform` (line 42 computes, line 43 validates); `int(raw["fitting_rows"])` accepts non-int JSON/YAML scalars. | Validate ndim/shape before arithmetic in `transform`; require `isinstance(raw["fitting_rows"], int) and not isinstance(..., bool)` in `from_dict`. |
| L5 | Low | Device refusal | `neural/src/training/network.py:36-39`; `neural/src/training/trainer.py` | CUDA/MPS refusal is implicit only: there is no device parameter to refuse, and `Classifier.forward` checks the input tensor's device but not the module's own parameters (a caller-moved CUDA model with CPU input fails with a raw `RuntimeError` rather than a clean binding failure). No test covers device refusal (Sprint §5.3: "明确拒绝 CUDA/MPS device 请求"). | `forward` checks `features.device.type != "cpu"` only; no suite test exercises a non-CPU request. | Also verify parameter device in forward (or assert once in `train_fold`), and add a device-refusal test constructing a non-CPU tensor where available (skip cleanly otherwise). |
| I1 | Info | Ordering deviation | `neural/src/training/dataset.py:94-103` | Protocol §2.1 prescribes validation steps 1→6 in order; the implementation checks integer dtypes and label values (step 4) before identity non-emptiness/uniqueness (step 3). The safety-critical ordering — steps 1–2 before any identity/feature-value read — is preserved (poison-probe verified); the swap only changes which error surfaces first. | Code order: `_INTEGER_COLUMNS` loop → `label.unique()` → `source_sample` checks → identity uniqueness → numeric finiteness. | Reorder to the protocol sequence for exact conformance, or note the accepted deviation. |
| I2 | Info | Consistency | `neural/src/training/trainer.py:51-55,169`; `neural/src/training/network.py:30-33` | Dual transcription of frozen constants: `lambda_for_epoch` hard-codes 5/15/10 and `build_validated_fold` hard-codes `42 + fold_index`, while AdamW lr/weight-decay are read from `protocol.raw`; network widths/eps/dropout are hard-coded against the sealed YAML blocks. Safe only because the YAML is sealed against drift, but inconsistent. | Source inspection; `optimization.learning_rate` read at `trainer.py:113-114` vs hard-coded schedule. | Either derive all constants from the loaded protocol or transcribe all uniformly; add a test binding the hard-coded values to `protocol.raw` values. |
| I3 | Info | Hygiene test | `neural/src/training/*.py` (all raise sites); `neural/src/training/dataset.py:92` | Error-message hygiene is implemented correctly — every `InputBindingError` message contains only rule names, column names, or counts; no row content, feature values, or filesystem paths (verified by inspecting all raise sites). But Sprint §5.1 requires a test asserting this, which is absent. Also the empty-frame case raises the misleading message "development frame contains forbidden split". | `if len(splits) == 0 or any(...)` shares one message; no hygiene test exists. | Add hygiene assertions (e.g., regex allow-list over raised messages in the mutation tests) and split the empty-frame message. |
| I4 | Info | Numerics | `neural/src/training/trainer.py:137-140,148-150` | The epoch numerator is reconstructed as `float(batch_loss.item()) * batch_denominator` — a float32 round-trip through the per-batch division — introducing ~`1e-7` relative error versus accumulating the raw weighted sums. Deterministic on-platform and structurally compliant with Protocol §9's numerator/denominator rule. | Code reconstructs `sum(w*l)` from the already-divided batch loss. | Accumulate `(losses * weights).sum()` directly as the numerator for exactness; related to M9's missing aggregation test. |
| I5 | Info | Global state | `neural/src/training/trainer.py:58-63` | `train_fold` mutates global torch state (`torch.set_num_threads(1)`, `torch.use_deterministic_algorithms(True)`) without restore. Acceptable for a primitive that mandates determinism (and recorded in environment evidence), but callers inherit the state change. | `_seed` sets globals on every call. | Document the side effect, or scope-and-restore where it does not conflict with the determinism mandate. |
| I6 | Info | Checkpoint validation / process | `neural/src/training/trainer.py:85-93`; `neural/docs/sprint-m1-03.md` §10 | `validate_checkpoint` does not range-check `best_validation_weighted_auc ∈ [0,1]` nor validate state-dict key sets/shapes/dtypes against the networks (in-memory checkpoints are self-produced, so this is hardening only). Separately, the Sprint §5 checklists are still all unchecked and §10 closure evidence (per-item acceptance, all commands, Protocol §10 evidence, boundary statements) is not yet recorded — expected at code-review stage but required before sprint close. | Validator checks field set, hashes, fold binding, lambda whitelist, epoch ≥ 1, finite AUC, scaler schema only; sprint doc checkboxes all `- [ ]`. | Optionally harden the validator; complete the sprint closure record (§6 items, §7 commands, Protocol §10 per-gate evidence, and the four boundary statements) at sprint close. |

## 4. Confirmed correct (verified)

- **Parameter counts**: classifier `7,617` (1024+128+4160+128+2080+64+33), adversary `1,611`
  (64+64+1056+64+363), total `9,228` — independently re-derived and asserted by executable tests
  at both module and construction level (`AdversarialMLP.__init__`).
- **Architecture**: exact layer sequences per Protocol §4.1/§4.2 (dropout only in the first two
  classifier blocks; adversary 1→32→32→11 with GRL applied to the scalar logit before the
  adversary stack); raw logits, no in-model sigmoid; output shapes `(N,)` / `(N_bg, 11)`.
- **GRL mechanics**: forward is `view_as` identity; backward returns `-lambda * grad` (and `None`
  for the lambda argument); composed-model gradient scaling is bitwise exact (probe);
  signal rows receive exactly zero adversarial gradient.
- **AdamW / differentiable-zero mechanics**: single AdamW over both networks with per-batch
  `optimizer.zero_grad(set_to_none=True)`; adversary parameters keep `grad=None` on
  no-background batches and are provably unchanged after `step()` (test), matching
  review-confirm items 9/19 (Kimi M6/M9, GLM M4). The background-with-zero-weight branch also
  avoids the adversary forward and any 0/0 division.
- **Test-first refusal ordering**: exact 29-column check, then split-only read, refusal of
  `test`/unknown splits before any identity/feature/statistic access (poison-probe verified);
  `m4l ∈ [105,160]` enforced on all rows (defensive inclusive superset per rereview-confirm
  items 2/5); `build_validated_fold` further requires non-empty, unique, disjoint partitions and
  rejects `fold_index` outside 0–4.
- **Feature contract**: exactly the 15 protocol features in order; forbidden columns
  (`lep3_pt`, `lep4_pt`, `mZ1`, `mZ2`, `m4l`, identity/provenance/weights) cannot enter the
  classifier tensor; tensors are float32 CPU `(N,15)`, labels/bins int64, optimizer weights
  float32; no feature-override API exists.
- **Scaler**: fitted on the fitting subset only, float64 population variance (`ddof=0`),
  zero-variance → `scale=1`, finite checks, float64 transform then float32 cast; validation
  provably excluded (distribution-shift test); exact-schema serialization round-trip.
- **Mass bins**: edges `[105..160]`, first ten bins left-closed-right-open, last bin inclusive
  at 160 (`floor((m-105)/5).clamp(max=10)`); boundary masses verified (`105→0`, `109.999→0`,
  `110→1`, `159.999→10`, `160→10`); out-of-range/non-finite rejected without clipping (probe).
- **Deterministic training**: CPU-only, `num_workers=0` semantics (manual batching with a
  dedicated seeded `Generator`), `torch.set_num_threads(1)`,
  `torch.use_deterministic_algorithms(True)`, per-call reseeding with `fold_seed = 42 + fold`;
  two same-lambda runs are bit-exact (suite test); init and epoch shuffle order are reused
  across lambdas (probe); no scheduler; sealed AdamW constants.
- **Schedule**: warm-up epochs 1–5 classifier-only (no adversary forward), linear ramp
  `target*(epoch-5)/10` for epochs 6–15, target from epoch 15/16 on; boundary values verified
  (`1/5/6/14/15/16 → 0, 0, 0.05, 0.45, 0.5, 0.5`); `target_lambda=0` never runs the adversary;
  lambda whitelist enforced with no schedule-override entry point.
- **Validation/checkpoint integrity**: validation is `model.eval()` classifier-only forward
  under `no_grad` (no RNG consumption, no scaler/optimizer/model updates); both-labels and
  weight preconditions enforced fail-closed; weighted AUC via `roc_auc_score` with validation
  `train_weight`; checkpoint selected only by `validation_weighted_auc` with the exact `1e-4`
  rule and patience 20; checkpoint is a deep CPU copy (`detach().cpu().clone()`) containing all
  ten sealed fields, protocol SHA-256 bound at load time and cross-checked against the fold,
  and validated in-memory before return.
- **Epoch metrics/environment**: all Protocol §9 epoch fields, summary fields, and environment
  fields (OS, architecture, Python, PyTorch, device, dtype, threads, data-loader workers,
  deterministic flag) are returned; warm-up/λ=0 epochs record `adv=0`, `total=cls`; losses
  aggregate numerator/denominator across the epoch (single division), not batch means.
- **Exit-code and boundary hygiene**: `InputBindingError` (exit 3) for all schema/protocol/data
  failures; `RuntimeError` (exit 70) for internal invariants; no run-path, qualification, or
  test-opening paths fabricated; messages leak no rows/values/paths; no real data, held-out
  test, or `open-test` anywhere in the change set; golden authority gate correctly refuses to
  run without the external ARM64 table.
- **No regressions**: change set is additive (no tracked runtime code modified); full suite
  98 passed / 1 correctly-skipped; `pip check`, both CLI `--help`, and `git diff --check` clean.

## 5. Safety boundary statement

This review ran only synthetic fixtures and unit/integration probes. No real data was read,
hashed, probed, preprocessed, scored, or published; the held-out test was not accessed;
full-data training and `open-test` were not executed. All Windows results above are development
verification only and do not substitute for the locked native `osx-arm64` authority gate, per
`neural/AGENTS.md`, FR-001, and Protocol §1.

## 6. Conclusion

The M1-03 implementation is scientifically sound on every mechanism I could execute or probe:
feature contract and test-first refusal ordering, fold-local scaler isolation, exact
architecture and parameter counts, GRL gradient mechanics, AdamW/differentiable-zero behavior,
schedule and early-stopping logic, checkpoint integrity, and bit-exact CPU determinism. No
Critical findings and no data/test leakage paths were found.

The main gaps are (1) the sealed-YAML loader's equality-based check accepts certain type-drift
and mapping-key-order mutations (H1/M1), weakening the pre-declared mutation gate, and (2) the
test gate does not yet provide executable evidence for several pre-declared requirements — most
conspicuously the GRL-direction acceptance criterion (no `lambda>0` training test at all, H2)
and a non-discriminative fixture that reduces the flagship deterministic-training test to a
degenerate constant-AUC trajectory (H3), leaving early-stopping boundaries, lambda-reuse,
epoch aggregation, and several fail-closed paths unasserted (M2–M9). The per-bin adversarial
weight exactness also deviates from the pre-declared `1e-12` tolerance (M4).

Recommended disposition: **fix H1 and M4 (small, localized changes); add the missing tests
(H2/H3/M2–M9) before sprint closure**, since Sprint §5.3/Protocol §10 make those gates
mandatory and Sprint §10 requires per-gate executable evidence at close. Low/Info items can be
batched or deferred with documented rationale.
