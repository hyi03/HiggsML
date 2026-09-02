# Sprint M1-05 Code Review Report

**Reviewer:** opencode-go/kimi-k2.7-code
**Review date:** 2026-09-02
**Scope:** Current working-tree implementation of Sprint M1-05 held-out MC test-opening mechanism in `D:\code\HiggsML`.
**Sources of truth reviewed:** `neural/docs/test-opening-protocol-v1.md`, `neural/docs/sprint-m1-05.md`, `docs/4-Reviews/sprint-m1-05-review-confirm.md`, root and `neural/AGENTS.md`.

## Scope and method

This review inspected the uncommitted working tree tracked by `git status`, including all modified and untracked files touched by M1-05. No real data, held-out test sets, or blinded regions were read, hashed, scored, plotted, or decoded. Review is source/test-code only.

Key files examined:

- `neural/src/training/test_opening.py`
- `neural/src/training/test_reader.py`
- `neural/src/artifacts/transaction.py`
- `neural/src/artifacts/plots.py`
- `neural/src/training/qualification.py`
- `neural/src/training/config.py`
- `neural/src/cli/train.py`
- `neural/src/config.py`
- `neural/tests/unit/test_test_opening.py`
- `neural/tests/integration/test_open_test_cli.py`
- `neural/tests/unit/test_transaction.py`
- `neural/tests/unit/test_qualification.py`
- `neural/tests/integration/test_development_run.py`
- `neural/tests/integration/test_cli_help.py`
- `neural/tests/development_fixtures.py`
- `neural/src/training/development_reader.py`
- `neural/src/artifacts/manifest.py`

## Verification performed

- `git status` / `git diff --stat` reviewed; `git diff --check` passes.
- `conda run -n pytorch python -m pytest -q tests/unit/test_test_opening.py tests/integration/test_open_test_cli.py` → passed.
- `conda run -n pytorch python -m pytest -q` (full suite) → 214 passed, 2 skipped.
- `conda run -n pytorch python -m pip check` → no broken requirements.
- No authoritative `open-test`, real-data read, or held-out test decode was performed.

## Executive summary

The M1-05 implementation is largely faithful to the Test-opening Protocol V1: path containment, symlink/reparse rejection, atomic `O_CREAT|O_EXCL` claim, permanent refusal of any existing state, durable claim/terminal-receipt flush, sanitized post-claim receipts, frozen model/scaler/threshold binding, test-only reader routing, and CLI exit mapping are all in place and covered by tests.

The single most important finding is a **High** correctness/protocol issue: invalid model outputs (non-finite or out-of-range scores) are currently misclassified as `test_frame_binding` failures (exit 3) because `_evaluate` calls `weighted_auc` before validating the model scores. Protocol §6 requires these to be `model_scoring` failures (exit 70). A few Medium/Low issues around receipt semantics, test coverage gaps, and defensive code clarity are also noted below.

## Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| High | Correctness / Exit-code mapping | `neural/src/training/test_opening.py` `_evaluate()`; `neural/src/training/qualification.py` `weighted_auc()` | Invalid model outputs are reported as `test_frame_binding` (exit 3) instead of `model_scoring` (exit 70). | `_evaluate()` calls `weighted_auc(frame["label"], frame["score"], frame["train_weight"])` before checking `scores.shape`, finiteness, or `[0,1]` bounds. `weighted_auc()` raises `InputBindingError` for non-finite or out-of-range scores. The outer handler in `execute_test_opening()` wraps any `InputBindingError` from `_evaluate()` as `TestOpeningFailure("test_frame_binding", ExitCode.INPUT_BINDING)`. Protocol §6 states: "model 产生非有限/越界 score 时 stage=`model_scoring`、exit 70". | Validate model outputs immediately after inference (finite, shape `(expected_test_rows,)`, all in `[0,1]`) and raise `RuntimeError` (or a dedicated scoring exception) **before** calling `weighted_auc()` / `frozen_working_point_metrics()`. This ensures the existing `except BaseException` handler maps it to `model_scoring` exit 70. |
| Medium | Correctness / State-machine semantics | `neural/src/training/test_opening.py` `_claim()` | An existing invalid `state/` directory (symlink, reparse point, or non-directory) raises `InputBindingError` (exit 3) instead of a permanent refusal (exit 5). | Lines 602–603 raise `InputBindingError("test-opening state directory is invalid")` when `_is_link_or_reparse(state_dir)` or `not state_dir.is_dir()`. Protocol §3 says any existing state, including "empty、partial、unparseable", must permanently refuse subsequent calls (exit 5). | Convert the symlink/reparse/non-directory `state/` check into `TestOpeningRefused("development run already has a test-opening state")`, consistent with the permanent-refusal semantics. |
| Medium | Clarity / Scientific predicate reporting | `neural/src/training/test_opening.py` `_evaluate()` | Empty-selected-background points emit both the explicit sentinel reason and the generic `_ks_above_maximum` reason. | Lines 684–688 append `<name>_empty_selected_background` (when `empty_selected_background` is true) and then always append `<name>_ks_above_maximum` because `ks == 1.0 > 0.10`. Protocol §6 only mandates the sentinel reason for this normal `test_nonreproduction` case. | Either document that both reasons are intentional, or prefer only the `<name>_empty_selected_background` sentinel when the high KS is a direct consequence of an empty selected background. |
| Medium | Missing test / Coverage | `neural/tests/unit/test_test_opening.py` | No test exercises the actual model-scoring path returning invalid scores and asserts exit 70 / `model_scoring`. | `test_post_claim_failures_publish_only_sanitized_receipts` injects raw `RuntimeError` and `InputBindingError`, but does not trigger invalid scores through the real classifier/score production code. | Add a test that monkeypatches the classifier inference or the score array to return NaN / out-of-range / wrong-shape values, then assert `TestOpeningFailure` with `stage="model_scoring"`, `exit_code=70`, sanitized receipts/state, and `test_features_opened=True`. |
| Medium | Missing test / Coverage | `neural/tests/unit/test_test_opening.py` | No full-integration test triggers the empty-selected-background sentinel during a complete `execute_test_opening()` run. | `test_frozen_working_point_uses_exact_threshold_and_handles_empty_background` only unit-tests `frozen_working_point_metrics()`. | Add a fixture or parametrized test that creates a development run whose frozen medium threshold is above all synthetic background test scores, run `execute_test_opening()`, and assert `status="test_nonreproduction"`, `ks==1.0`, `empty_selected_background==true`, and the sentinel reason is present. |
| Low | Security / Authorization hygiene | `neural/src/training/test_opening.py` `_SENSITIVE_AUTHORIZATION` | The credential-assignment regex lacks word boundaries and can over-reject legitimate audit references. | Pattern `(?:password\|passwd\|api[\s_-]*key\|secret\|token\|credential)\s*[:=]` matches substrings such as `my_password=foo` or `apipassword=secret`, because it does not anchor to a word boundary or separator. | Add a leading word-boundary or separator requirement (e.g., `(?:^\|[\s\W])(...)(?:\s*[:=])`) so that incidental substrings are not rejected, while still rejecting clear credential assignments. |
| Low | Correctness / Sort consistency | `neural/src/training/test_opening.py` `_evaluate()` | The expected-identity ordering check uses UTF-8 byte sort, while the published frame is sorted with pandas string sort. | Lines 666–671 build `expected_identities` sorted by `(str(item[0]).encode("utf-8"), int(item[1]))`, but line 665 sorts `frame` with `sort_values(["source_sample", "source_entry"], kind="stable")`. For the fixed ASCII sample names these coincide, but the two sort keys are not equivalent. | Unify the sort key: sort the frame using the same UTF-8 byte key used for `expected_identities`, or use pandas categorical/byte-order sort explicitly. |
| Low | Robustness / Defensive code | `neural/src/training/test_opening.py` `execute_test_opening()` | The `except RunPathError` branch appears to be unreachable under current code paths. | `_write_success_artifacts()` catches `RunPathError` and re-raises it as `TestOpeningFailure("output_transaction", ExitCode.TRANSACTION)` before it can escape the `with transaction:` block. | Document the branch as defensive, or remove it and rely on the `except BaseException` handler, which already stores the failure state correctly. |
| Low | Schema validation | `neural/src/training/test_opening.py` `_development_manifest()` | Manifest `schema` validation is shallow: it checks types but not exact column lists or dtypes. | Lines 212–224 only verify that `schema` keys map to `list`/`dict`. Exact column/dtype binding is deferred to `_validate_protocol_manifest_binding()`. | Either tighten `_development_manifest()` to validate exact schema columns/dtypes against the frozen protocol, or document that the later protocol-manifest binding is the authoritative schema check. |
| Info | Correctness / Durability | `neural/src/training/test_opening.py` `_flush_directory()`, `_claim()`, `_replace_state()` | Durable directory flush on Windows (via `CreateFileW` + `FlushFileBuffers`) and POSIX (`os.fsync` on directory fd) is correctly implemented and tested. | `test_claim_and_terminal_receipt_flush_directories_durably` and `test_claim_durability_failure_is_terminal_without_test_decode` pass; parent-development-run flush is performed only when `state/` is newly created. | Keep the current implementation; consider adding a brief code comment noting the Windows directory-handle semantics for future maintainers. |
| Info | Scientific safety | `neural/tests/unit/test_test_opening.py` `test_opening_never_calls_training_fit_or_selection_paths()` | Strong spy-based evidence that test opening does not invoke training, scaler fitting, threshold selection, or candidate selection. | The test monkeypatches `FoldLocalScaler.fit`, `train_fold`, `train_fixed_epochs`, `working_point_metrics`, and `select_candidate` to `pytest.fail()` and the opening still completes. | Maintain and extend this spy pattern if new training-adjacent helpers are introduced. |
| Info | Verification | Full test suite, `pip check`, `git diff --check` | All automated checks pass. | `pytest -q`: 214 passed, 2 skipped. `pip check`: clean. `git diff --check`: clean. | N/A – keep checks in the Sprint verification checklist. |

## Overall conclusion

The M1-05 implementation satisfies the protocol on the core safety-critical requirements: one-shot atomic claim, permanent refusal, frozen artifact/model/scaler/threshold binding, test-only decoding, sanitized receipts, and correct CLI exit mapping for most paths. The automated test suite passes and covers the main concurrency, durability, and crash-boundary scenarios.

Before marking the Sprint complete, the **High** exit-code misclassification for invalid model outputs must be fixed, and the **Medium** state-machine and reporting issues should be addressed or explicitly documented. The noted Low items are hygiene and clarity improvements. No authoritative `open-test` or real-data access was performed or authorized during this review.
