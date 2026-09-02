# Sprint M1-03 Code Review Report

**Reviewer:** opencode-go/kimi-k2.7-code
**Scope:** M1-03 implementation change set relative to commit `aebf0ce`
**Primary files reviewed:**

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

**Sources of truth:** `neural/docs/sprint-m1-03.md`, `neural/docs/adversarial-mlp-protocol-v1.md`, `docs/4-Reviews/sprint-m1-03-review-confirm.md`, `docs/4-Reviews/sprint-m1-03-rereview-confirm.md`, `neural/docs/FR-001-adversarial-mlp-refactor.md`, `neural_adversarial_mlp_refactor_design.md`, root `AGENTS.md`, `neural/AGENTS.md`.

## Executive Summary

The M1-03 implementation correctly translates the sealed protocol into code: the 29-column input contract, 15-feature classifier tensor, fold-local population-variance scaler, exact `7,617 / 1,611 / 9,228` parameter counts, Gradient Reversal Layer, bin-balanced background adversarial loss, AdamW optimizer, deterministic CPU training loop, lambda ramp, and checkpoint schema are all present and largely tested. The full synthetic/unit test suite passes.

The main gaps are in test coverage for non-zero-lambda determinism, adversary-state determinism, trainer-level zero-effective-background batches, early-stopping/patience boundaries, and a poison-accessor proof of split-first refusal. There are also minor robustness and hygiene observations around the protocol loader's exact-dict comparison and the checkpoint validator's state-dict integrity checks. No real-data or held-out-test leakage was found.

## Verification Performed

All verification used synthetic/unit tests only. No real data was read, hashed, preprocessed, or scored; no held-out test was opened; `open-test` was not executed.

```text
conda run -n pytorch python -m pip check
# -> No broken requirements found.

conda run -n pytorch python -m pytest -q tests/unit/test_training_config.py tests/unit/test_dataset.py tests/unit/test_network.py tests/unit/test_losses.py tests/integration/test_deterministic_training.py
# -> 29 passed in 7.00s

conda run -n pytorch python -m pytest -q
# -> 98 passed, 1 skipped in 13.93s

conda run -n pytorch higgsml-preprocess --help
# -> usage: higgsml-preprocess [-h] --protocol PROTOCOL --run-config RUN_CONFIG --run-dir RUN_DIR

conda run -n pytorch higgsml-train --help
# -> usage: higgsml-train [-h]

git diff --check aebf0ce
# -> (no output)
```

Platform: Windows development verification; no claim is made about the locked native `osx-arm64` authority gate.

## Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| Medium | Test coverage | `neural/tests/integration/test_deterministic_training.py` | Determinism is only verified for `target_lambda=0.0`. The protocol requires exact reproducibility for all pre-registered lambdas and reuse of initialization/batch order across lambdas. | Only `train_fold(fold, protocol, target_lambda=0.0)` is run twice and compared; adversary state dicts are not compared. | Add integration tests for `target_lambda ∈ {0.05, 0.50}` that compare classifier and adversary state dicts and epoch metrics across two runs, and assert that different lambdas start from identical initial weights and first-epoch shuffle order. |
| Medium | Test coverage | `neural/tests/unit/test_dataset.py` | No poison-accessor test proves that the validator rejects `split=test` *before* reading identity or feature values, as required by protocol §2.1 step 2. | Tests mutate the split value and assert `InputBindingError`, but they do not demonstrate that identity/feature accessors were never invoked during validation. | Add a test using a DataFrame subclass or proxy accessor that raises a distinct exception if identity columns or feature columns are accessed before the split column is validated; assert only `InputBindingError` is raised. |
| Medium | Test coverage | `neural/tests/unit/test_dataset.py`, `neural/tests/integration/test_deterministic_training.py` | Validation AUC precondition failures (single class, non-finite/negative weights, zero weight sum) and invalid target-lambda rejection are not explicitly tested. | `build_validated_fold` performs these checks, and `train_fold` checks `target_lambda not in protocol.target_lambdas`, but no tests target these fail-closed paths. | Add parametrized unit tests for malformed validation subsets and for `train_fold` with an unregistered lambda; assert `InputBindingError` is raised without leaking row values or paths. |
| Medium | Test coverage | `neural/tests/unit/test_losses.py`, `neural/tests/integration/test_deterministic_training.py` | The trainer-level path for a batch that contains background rows but has zero effective adversarial weight sum is not tested. | `trainer.py` has the guard `if torch.any(background) and adv_weights.sum().item() > 0.0`, but only the pure-signal case is exercised in `test_zero_effective_background_batch_does_not_update_adversary`. | Add a trainer/fold test where a batch contains background rows with bin absolute-weight sum of zero; assert no adversary forward occurs, adversary gradients remain `None`, and adversary parameter bytes are unchanged after `optimizer.step()`. |
| Medium | Test coverage | `neural/tests/integration/test_deterministic_training.py` | Early-stopping patience and the `> best_auc + 1e-4` improvement threshold are not tested. | `trainer.py` increments patience when AUC does not improve by more than `minimum_improvement`, but there is no test for equal-AUC non-replacement or for stopping after 20 non-improving epochs. | Add a targeted integration or unit test using a controlled synthetic fold to verify: (a) equal AUC does not replace the checkpoint, (b) 20 consecutive non-improving epochs trigger `stopped_early=True`, and (c) a single improvement greater than `1e-4` resets patience. |
| Low | Robustness | `neural/src/training/config.py` (`load_training_protocol`) | Protocol validation relies on exact Python dict equality `raw != _EXPECTED`. | Line 123 uses full dict equality. Equivalent YAML representations (e.g., `1e-5` vs `1.0e-5`, flow vs. block mapping) parse to the same dict and would be accepted, while the byte-level SHA-256 would differ. Conversely, subtle parser differences could make future maintenance brittle. | Keep the byte-level SHA-256 as the immutable seal; consider validating high-level protocol blocks field-by-field against the constants for clearer diagnostics, while preserving fail-closed behavior. |
| Low | Test coverage | `neural/tests/unit/test_training_config.py` | Feature/input-column ordering mutations and byte-level comment changes that affect the sealed SHA-256 are not tested. | The parametrized drift tests only change values, not list order, and there is no assertion that a YAML comment changes `protocol.sha256`. | Add a test that reorders `features` (or `input_columns`) and asserts `InputBindingError`; add a test that appends a YAML comment and asserts the computed `sha256` changes, reinforcing the byte-seal contract. |
| Low | Robustness | `neural/src/training/trainer.py` (`validate_checkpoint`) | The checkpoint validator does not inspect classifier/adversary state dicts for key completeness, tensor shapes, device, or dtype. | `validate_checkpoint` checks the field set, protocol hash, fold binding, and scaler schema, but treats the state dicts as opaque objects. | Extend `validate_checkpoint` to compare state-dict keys against a freshly constructed `AdversarialMLP`, and assert all tensors are on CPU with dtype `float32` and expected shapes. |
| Low | Specification | `neural/src/training/trainer.py` (`TrainingResult`) | `TrainingResult` carries an extra `validation_scores` field not listed in the protocol §9 result contract. | The dataclass includes `validation_scores`, which is convenient for tests but is not one of the mandated epoch/summary/environment fields. | Document `validation_scores` as an implementation-internal convenience, or move it into the checkpoint payload and keep the public `TrainingResult` aligned with protocol §9 for downstream artifact serialization. |
| Info | Scope | `neural/src/cli/train.py` (observed via `higgsml-train --help`) | The `higgsml-train` CLI currently exposes only generic help and no `develop`/`open-test` subcommands. | `higgsml-train --help` prints only `-h/--help`. | Accept for M1-03 because the Sprint scope is the single-fold training primitive; ensure the OOF orchestration CLI is implemented and reviewed in M1-04/M1-05. |
| Info | Positive | `neural/src/training/network.py`, `neural/tests/unit/test_network.py` | Exact parameter counts and architecture match the sealed protocol. | Tests assert `7617`, `1611`, and `9228`; LayerNorm `eps=1.0e-5`, SiLU, Dropout `0.10`, and linear biases are present. | Maintain these executable assertions; keep architecture frozen in the sealed YAML. |
| Info | Positive | `neural/src/training/losses.py`, `neural/tests/unit/test_losses.py` | Mass bin edges, bin-balancing, negative physical-weight handling, and differentiable-zero loss are implemented correctly. | `mass_bin_indices(105.0)` → 0, `160.0` → 10; weights sum to one per bin even with `physical_weight=-2.0`; zero-background batch leaves adversary gradients as `None`. | Keep current loss implementation; add the trainer-level zero-sum background batch test recommended above. |
| Info | Positive | `neural/src/training/trainer.py`, `neural/tests/integration/test_deterministic_training.py` | Lambda schedule and deterministic CPU training loop match the protocol. | Schedule test verifies `0.0, 0.0, 0.05, 0.45, 0.5, 0.5` for epochs `1/5/6/14/15/16`; lambda-0 training is bit-exact across two runs on synthetic data. | Extend determinism coverage to non-zero lambda and adversary state as recommended. |

## Conclusion

The M1-03 implementation is structurally correct and passes all existing synthetic/unit tests. The protocol is byte-sealed through a YAML SHA-256 hash, the data contract is fail-closed, and the training loop is deterministic for the tested `lambda=0` case. No evidence of real-data leakage, test-data leakage, or held-out-test access was found.

The review recommends closing the identified medium-priority test gaps—especially non-zero-lambda determinism, split-first poison-accessor proof, and early-stopping boundaries—before declaring the Sprint fully verified. The low-priority robustness items should be addressed as cleanup. Once those tests are added and the suite still passes, the M1-03 code change set can be accepted.

**Boundary statement:** This review was performed on Windows with synthetic data only. It does not substitute for the locked native `osx-arm64` authority gate, full-data training, or any future `open-test` authorization.
