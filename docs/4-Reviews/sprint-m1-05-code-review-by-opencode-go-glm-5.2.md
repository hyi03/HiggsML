# Sprint M1-05 Code Review (by opencode-go / glm-5.2)

**Review type:** code review (working tree, uncommitted)

**Review date:** 2026-09-02

**Reviewer model:** opencode-go / glm-5.2

## Reviewed inputs

Tracked diff and untracked files from `git status` in `D:\code\HiggsML`:

- `neural/src/training/test_opening.py` (new)
- `neural/src/training/test_reader.py` (new)
- `neural/src/artifacts/transaction.py` (modified)
- `neural/src/artifacts/plots.py` (modified)
- `neural/src/training/qualification.py` (modified)
- `neural/src/training/config.py` (modified)
- `neural/src/cli/train.py` (modified)
- `neural/src/config.py` (modified)
- `neural/tests/unit/test_test_opening.py` (new)
- `neural/tests/integration/test_open_test_cli.py` (new)
- `neural/tests/development_fixtures.py` (modified)
- `neural/tests/integration/test_cli_help.py` (modified)
- `neural/tests/integration/test_development_run.py` (modified)
- `neural/tests/unit/test_qualification.py` (modified)
- `neural/tests/unit/test_transaction.py` (modified)
- `neural/docs/sprint-m1-05.md` (modified), `neural/docs/test-opening-protocol-v1.md` (new)
- `neural_adversarial_mlp_refactor_design.md` (modified)

Cross-referenced support code (unmodified, read for binding verification):
`src/training/development_reader.py`, `src/training/dataset.py`,
`src/training/network.py`, `src/training/development.py`,
`src/artifacts/manifest.py`, `src/preprocessing/outputs.py`,
`src/logging_config.py`, `neural/README.md`, `neural/pyproject.toml`,
`tests/training_fixtures.py`, `tests/unit/test_development_reader.py`.

Sources of truth: `neural/docs/test-opening-protocol-v1.md`,
`neural/docs/sprint-m1-05.md`,
`docs/4-Reviews/sprint-m1-05-review-confirm.md`, root and `neural/AGENTS.md`.

## Review boundaries honored

- Strictly MC-only: no real data was read, hashed, probed, preprocessed,
  scored, plotted, or published. No held-out test was opened or decoded.
  `open-test` was not executed against any run, authoritative or synthetic.
- Source/test-code review only. No pytest, no CLI smoke, no `pip check` was
  run by the reviewer (those remain the implementer's verification gate per
  sprint §7).

## Verification performed by the reviewer

- Full read of every file listed above, including exact diff review of all
  modified files.
- Static byte-compile check of all touched Python files
  (`python -m py_compile ...`): **OK**.
- `git diff --check` from repository root: **clean** (no whitespace errors).
- Line-by-line trace of the claim/failure state machine against protocol
  §2/§3/§8 exit codes and receipt schemas, and of the frozen-evaluation path
  against §4/§5/§6.

## Overall assessment

The implementation is substantially conformant with Test-opening Protocol V1
and with the confirm decisions (F01–F08, sentinel, hygiene, durability). The
pre-claim binding chain, atomic `O_CREAT|O_EXCL` claim, two-level directory
durability, permanent-refusal semantics, sanitized receipts, test-only reader,
frozen model/scaler/threshold evaluation, and stable exit mapping are all
implemented and mostly well tested. No Critical or High severity defects were
found. The findings below are one real concurrency/audit edge case (Medium),
one protocol-declared test gate that remains uncovered (Medium), and several
low/info-level exit-code, robustness, documentation, and coverage items.

## Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| Medium | Concurrency / Crash consistency | `neural/src/training/test_opening.py:924-944` (with `_claim` at `:588-629`) | The claim-failure fallback treats "state file exists" as "this process created the claim", but in a race the existing file may belong to a concurrent winner, whose receipt is then overwritten. | `except BaseException as error: if not os.path.lexists(state_candidate): ... wrapped = TestOpeningFailure("claim_durability", ...); _store_failure_state(state_candidate, ...)`. `_claim` can fail **before** its `O_CREAT\|O_EXCL` (parent `_flush_directory` failure at `:604-608`, `mkdir`/`os.open` transient non-`FileExistsError` at `:598-601`, `:617-620`) while a concurrent process's `O_EXCL` succeeds in between. This process then publishes a spurious failure run and `_replace_state` overwrites the winner's `claimed` state with its own `failed_after_claim` (`test_features_opened=false`). If the winner later hard-crashes after decode, the persisted receipt falsely records that test features were never opened — an audit-integrity violation. Fail-closed refusal is preserved either way, but receipt provenance is wrong. | Make `_claim` report whether the `O_EXCL` creation was performed by this process (e.g., a dedicated exception attribute or sentinel return); enter the `claim_durability`/terminalization path only in that case. Otherwise surface `TestOpeningRefused`/`RunPathError` and abort staging without touching the state file. Add a regression test for the pre-`O_EXCL`-failure-with-concurrent-winner interleaving. |
| Medium | Missing test | `neural/src/training/test_opening.py:684-691`; `neural/tests/unit/test_test_opening.py:64-136`; `neural/tests/unit/test_qualification.py:87-104` | The `<point>_empty_selected_background` sentinel-reason path and a definite `test_nonreproduction` terminal flow have no test coverage; protocol §9 requires "empty-selected-background 的 efficiency 0.0、KS 1.0 与 sentinel reason 形成正常非复现". | `if point["empty_selected_background"]: reasons.append(f"{name}_empty_selected_background")` (`test_opening.py:686-688`) is executed by no test. The only empty-selected test is unit-level (`test_frozen_working_point_uses_exact_threshold_and_handles_empty_background`, values only — no reason, no status). `test_synthetic_opening_publishes_terminal_run_and_only_mutates_state` accepts `status in {"test_reproduced", "test_nonreproduction"}`, so neither terminal conclusion is pinned end-to-end. The empty-selection mass histogram (`plots.py:143-146`, `density=True` on a possibly empty selection) is also never exercised through publication (numpy 0/0 density may emit warnings). | Add a fixture-driven opening test that forces zero selected-background absolute weight at a frozen threshold and asserts: reasons contain `<point>_empty_selected_background` plus `<point>_ks_above_maximum`, status `test_nonreproduction`, exit 0, and both plots publish cleanly. Pin at least one definite `test_reproduced` and one definite `test_nonreproduction` fixture outcome. |
| Low | Correctness / exit-code semantics | `neural/src/training/test_opening.py:596-608, 617-620` | Filesystem/durability failures during claim staging are classified as input-binding (exit 3) or escape unwrapped (exit 70) instead of the transaction category (exit 4) that `neural/AGENTS.md` and protocol §8 assign to claim durability failures. | `state_dir.mkdir` OSError → `InputBindingError` (`:599-601`); parent-directory durable flush failure → `InputBindingError("test-opening state directory is not durable")` (`:604-608`); non-`FileExistsError` `os.open` OSError propagates raw and reaches the CLI generic handler → exit 70 (`train.py:88-90`). No claim file exists in these paths, so staging is aborted and the call is retryable (fail-closed, §2-compliant on that aspect) — the defect is exit-code misreporting only. | Raise `RunPathError` (exit 4) for filesystem/durability failures in `_claim` instead of `InputBindingError`/raw `OSError`, keeping the pre-claim abort-without-receipt behavior. |
| Low | Crash consistency / audit | `neural/src/training/test_opening.py:998` | The post-publication manifest hash read sits outside every wrap/receipt path; a failure there escapes without a `failed_after_claim` receipt. | `manifest_sha = sha256_file(transaction.run_dir / "artifacts/manifest.json")` runs after the transaction has published but before terminal `_replace_state`. An `OSError` here (AV lock, disk error) propagates unwrapped: no receipt update occurs, the CLI logs a traceback and returns exit 70, while the test run is already published and the claim is held. State stays `claimed` → permanently refused (hard-crash-equivalent, fail-closed), but per protocol §3 a *captured* post-claim exception should terminalize the receipt, and §8 maps receipt-finalization failure to exit 4. | Wrap the manifest read into the `terminal_receipt` stage (or a dedicated post-publish stage) routing through `_store_failure_state` on failure, returning exit 4. |
| Low | Missing tests | `neural/tests/unit/test_test_opening.py` (suite); `neural/src/training/test_opening.py:414-542` | Protocol §9 gate "任一 byte/hash/schema/selection/scaler/model drift 在 claim 和 test decode 前拒绝" is exercised only for a subset of the implemented drift checks; terminal-state payloads and the read/unread receipt distinction are also partially un asserted. | Covered: model byte tamper (`:155-170`), missing model (`:173-185`), working-point schema drift with manifest re-hash (`:243-270`), no-eligible (`:188-212`). Not covered through `execute_test_opening`: `model/scaler.json` drift, qualification/selection drift (non-eligible selected candidate, re-derived selection mismatch at `test_opening.py:400-410`), preprocess lineage/table hash drift (`:504-511`), extra output record (`seen != _DEV_OUTPUTS`, `:266-267`), terminal-status state payloads (`test_reproduced`/`failed_after_claim` enumerated in §3; the parametrization at `:295` covers only empty/partial/`claimed`), `test_features_opened=True` on the evaluate-failure receipt (only the `False` case is asserted, `:512`), and score equivalence against a manual forward pass of the frozen model. All of these code paths read as strict by inspection. | Add focused pre-claim refusal tests for scaler/selection/preprocess-table tamper (rehashing manifests like the working-point test does); extend the state-payload parametrization to terminal statuses; assert `test_features_opened` on post-claim receipts; optionally assert published scores equal a manual `classifier` forward pass on the fixture test frame. |
| Low | Documentation regression | `neural/README.md:147-155` | The `open-test` usage example omits the now-required `--authorization-reference` flag. | README §2.3 shows a two-flag invocation while `build_parser` declares all three arguments `required=True` (`neural/src/cli/train.py:35-41`); a copy-paste invocation exits 2. The design doc (updated in this change) and protocol §1 both include the flag. | Update README §2.3 to include `--authorization-reference <external-approval-reference>` with the audit-only wording from protocol §1. |
| Low | Robustness | `neural/src/training/test_opening.py:617-629, 632-640` | File-descriptor leak if `os.fdopen` fails after `O_CREAT|O_EXCL`, plus a no-op `except BaseException: raise` block in `_claim`. | `descriptor = os.open(state, ...)` then `with os.fdopen(descriptor, "wb")`: if the `fdopen` constructor raises, the descriptor is never closed (on Windows the half-open handle can block later state reads until process exit). Lines `:627-628` re-raise unconditionally with no cleanup — dead code. `_replace_state` (`:634-638`) has the same unguarded `fdopen` shape. | In both `_claim` and `_replace_state`, close the raw descriptor on any failure before `fdopen` succeeds (`try/except BaseException: os.close(descriptor); raise`); delete the no-op except block. |
| Info | Portability / race | `neural/src/artifacts/transaction.py:171-180` | `_publish` guards with `run_dir.exists()` then `rename`; POSIX `rename` onto an existing *empty* directory succeeds silently, leaving a narrow check-then-rename TOCTOU. | `if self.run_dir.exists(): raise RunPathError(...)` followed by `self.path.rename(self.run_dir)`. On Windows rename onto an existing directory fails closed; on POSIX a concurrently created empty directory at `run_dir` would be replaced. Practical risk is minimal because claim serialization upstream means at most one publisher per development run. | Acceptable as-is; document the residual semantics. A portable no-replace directory rename primitive does not exist in the Python stdlib. |
| Info | Consistency | `neural/src/training/test_opening.py:419-422` | The development `config.yaml` is parsed with plain `yaml.safe_load` instead of the duplicate-key-rejecting `_UniqueLoader` used everywhere else. | `config = yaml.safe_load((run / "config.yaml").read_bytes())` vs `src/config.py:41-55` and `src/training/config.py:30-44`. The file is hash-bound via the manifest output record (`_validate_dev_outputs`) and its content exactly schema-checked (`set(config) != {...}`, `:423-426`), so duplicate keys cannot alter the accepted value set — consistency-only. | Reuse the unique-key loader for uniform hardening. |
| Info | Consistency | `neural/src/training/test_reader.py:86-103` | `validate_test_frame` dtype checks are permissive (`is_integer_dtype`/`is_numeric_dtype` admit int32/float32) although the pipeline always constructs int64/object/float64 frames. | `:86-88` uses `is_integer_dtype`; `:96-103` uses `is_numeric_dtype`. `_decode_test_rows` (`:27-41`) fixes exact dtypes, so in-pipeline frames are exact; only direct callers of the public `validate_test_frame` could pass narrower dtypes. | Compare exact dtype strings (`frame[column].dtype == "int64"` etc.) for strictness, or leave as-is with a note that the decoder is the dtype authority. |
| Info | Clarity / UX | `neural/src/cli/train.py:82-84` | Open-test input-binding refusals are logged with develop-centric wording and without stage/run-path context. | Shared `except InputBindingError` handler logs `"development input binding failed: %s"`; protocol §8 asks CLI logs to carry stage and run path (the `TestOpeningFailure` branch does; this branch does not). | Log a stage-aware message (e.g., include `arguments.run_dir` and a `stage=input_binding` qualifier) without test values. |
| Info | Reproducibility | `neural/src/training/test_opening.py:804-815` | Deterministic environment is recorded but not enforced; CPU thread count is not recorded. | `"deterministic_algorithms": torch.are_deterministic_algorithms_enabled()` records `False` rather than asserting/enabling it; `torch.get_num_threads()` (which can perturb CPU reduction order) is not captured, unlike the development run's environment fields. Eval-mode CPU forward is deterministic in practice, and published score hashes make any rerun divergence visible. | Enable deterministic algorithms before scoring and record the flag; optionally pin/record thread count so published score hashes are exactly reproducible. |
| Info | Path resolution | `neural/src/training/test_opening.py:270-278` | `_resolve_preprocess` matches the allowed-root name ("runs") case-insensitively when routing relative recorded input paths. | `raw.parts[0].lower() == allowed_root.name.lower()` — Windows-motivated (matches protocol §2's `runs/...` example on case-insensitive filesystems). On case-sensitive platforms a differently-cased prefix routes under the root instead of the root's parent and then fails existence/containment — fail-closed, but platform-asymmetric. | Document the case-insensitive matching as Windows-motivated, or match exactly and document both accepted forms. |
| Info | Test safety | `neural/tests/integration/test_open_test_cli.py:38-56`; `neural/src/training/test_opening.py:892-899` | Subprocess CLI tests run with cwd `neural/`, where the real `neural/runs/` root exists; their safety depends on authorization being validated before any filesystem touch. | `test_blank_authorization_value_returns_refusal` passes `--development-run runs/missing` against the real root; `_authorization_reference` (`:893`) raises before `RunTransaction` construction (`:894`), so no staging is created. `neural/runs/` currently contains only a synthetic M1-04 smoke run. The ordering is load-bearing for test hygiene. | Keep the authorization-first ordering invariant (comment or test); for defense in depth, chdir these subprocess cases to a tmp root. |

## Protocol conformance verified (strengths)

- **§2 pre-claim order and cheap probes:** output `RunTransaction` target
  validated/non-existent with unique staging only (`test_opening.py:894-900`);
  path binding then state existence probe before any manifest/artifact read
  (`:902-908`); full binding; second probe; `O_EXCL` as the sole authoritative
  race guard. Authorization is validated before any filesystem touch. No test
  feature token is decoded pre-claim; the preprocess table bytes only stream
  through the integrity hash (`_canonical_content_sha256`), which §2 permits.
- **§2 binding completeness:** manifest exact key schema, canonical-bytes
  check, `run_type=development`, `status=eligible` (exit 5) vs schema drift
  (exit 3), boundaries exact, counts arithmetic, OOF completeness, exact output
  path set with per-file size/SHA-256 and OOF canonical re-hash
  (`:146-267`); config/qualification/working-points/scaler/model mutual
  binding incl. protocol SHA, selected lambda, final epochs, feature tuple,
  seed, scaler equality and `fitting_rows == development_rows`
  (`:414-496`); preprocess lineage re-verification with manifest/table/canonical
  SHAs exact-matched to the development input block and row-count equality
  (`:498-518`). Qualification constants, tie rule, and selection are
  re-derived solely from the hash-bound snapshot
  (`validate_training_protocol_snapshot`, `src/training/config.py:174-178`);
  the repo protocol file is never read. Relative/absolute `input_run`
  resolution follows §2's `runs/...` vs `foo` examples with final resolved
  containment.
- **§3 atomic claim and state machine:** `mkdir(exist_ok=True)` + link/reparse
  validation of `state/`; `O_CREAT|O_EXCL` 0o600 canonical claim with all
  required fields including `output_staging` (F08); parent-run directory flush
  when `state/` is newly created, then file flush+fsync, then `state/` flush,
  all before decode (F02); Windows `FlushFileBuffers` equivalent with
  `FILE_FLAG_BACKUP_SEMANTICS` (`:545-585`). Any existing state file —
  empty/partial/unparseable/claimed/terminal — permanently refuses; the claim
  is never deleted; terminalization uses same-dir temp + `os.replace` +
  directory flush; `claim_durability` failure → exit 4, no decode, best-effort
  sanitized failure run + `failed_after_claim` receipt; non-durable
  terminalization still leaves permanently refusable state.
- **§4 test-only reader:** exact 29-column header; split-token-first routing
  (`_field_token`), train/validation rows never parsed or materialized,
  unknown/empty split fails before any other token decode
  (`test_reader.py:44-73`); count equality with both manifests (enforced
  pre-claim and again in the reader); full frame validation: 29 columns,
  dtypes, finite, `split == test`, unique identities, label set and
  sample-label binding, `105 <= m4l <= 160`, non-negative `train_weight`,
  strictly positive per-class `train_weight` and `abs(physical_weight)` totals
  → post-claim `test_frame_binding` exit 3 (F05), distinct from §6's normal
  empty-selected-background nonreproduction.
- **§5 frozen model/scaler/scoring:** `torch.load(..., weights_only=True)`,
  exact payload key set, CPU/float32/finite tensors, strict `load_state_dict`
  on a fresh `AdversarialMLP`, `eval()`, frozen scaler transform of only the 15
  features, finite `[0,1]` sigmoid scores with shape/completeness checks
  (`:454-496`, `:654-671`). No trainer/optimizer/scaler-fit/threshold/candidate
  selection path is invoked; spies prove it
  (`test_test_opening.py:424-450`).
- **§6 frozen metrics and conclusion:** weighted AUC on `train_weight`;
  per-point frozen threshold+target with `score >= threshold`;
  `abs(physical_weight)` achieved/signal efficiencies and selected-vs-all
  weighted m4l KS; no epsilon in comparisons; empty selected background →
  efficiency `0.0`, KS `1.0`, `empty_selected_background` sentinel (F10 +
  confirm #4); nonreproduction restricted to frozen scientific predicates;
  frame-binding → 3, non-finite/out-of-range score → `model_scoring` 70,
  publication → 4 (F01); both terminal states exit 0 with no-feedback
  boundaries recorded.
- **§7 artifacts:** exact 6-file layout; score CSV column order exact
  (`source_sample,source_entry,label,m4l,physical_weight,train_weight,score`);
  rows ordered by sample/entry; gzip file SHA and decompressed canonical CSV
  SHA both recorded with row count; canonical JSON metrics/manifest;
  manifest-last with development hashes/selection, preprocess input hashes,
  authorization reference, protocol/model/scaler/working-point hashes,
  schema/counts, conclusion, environment, wall time, peak memory, and exact
  boundaries (`authority_environment_verified=False` on Windows/synthetic);
  no claim copy inside the test run; published-output + failed-terminal-receipt
  → exit 4 with indeterminate claim and untouched output; CLI logs the
  manual-audit-required wording (confirm #12).
- **§8 exits:** 0/2/3/4/5/70 mapping exact, including the two new exit-4
  stages (`claim_durability`, `terminal_receipt`, F03); no `--force`/`--retry`
  or scientific overrides; logs carry stage/status/run path only.
- **Authorization hygiene (F06 + confirm #11/#20):** strip-then-nonempty,
  ≤256 Unicode code points, `Cc`/`Cf` rejection (covers C1 and bidi/format
  controls), case-insensitive credential-assignment denylist
  (`test_opening.py:84-132`), tested at both unit and CLI level.
- **Transaction hardening:** `..` traversal rejection even when it resolves
  inside, symlink/junction/reparse rejection of root and all components
  (before and after parent creation), resolved containment via
  `commonpath`, existing-output refusal via `lexists`, no-overwrite publish,
  `.failed` staging preservation, sanitized failure receipts via
  safe-message/stage (transaction.py), all newly tested.
- **MC-only discipline:** every test uses synthetic fixtures under `tmp_path`
  roots with the `synthetic-fixture-only` reference; no test references an
  authoritative run or real data; this review likewise touched no data.

## Coverage vs protocol §9 minimal test gate

| §9 gate | Status | Evidence |
|---|---|---|
| No-eligible / missing artifact / hash / schema drift refused pre-claim | Partial | no-eligible, missing model, model byte tamper, working-point schema drift (with manifest re-hash) covered; scaler/selection/preprocess-table/extra-record drift untested (Finding 5) |
| Traversal / symlink / junction / reparse / existing output refused | Covered | output side: `test_output_path_escape_and_existing_output_refuse_before_claim`, `test_transaction_rejects_parent_traversal_even_when_it_resolves_inside`, `test_transaction_rejects_symlink_component_when_supported`; input side via M1-04 `test_development_reader.py:66-104` on the shared `_bound_input_run` |
| `O_EXCL` concurrency single winner; existing/claimed/terminal state permanent refusal | Mostly covered | `test_atomic_claim_allows_exactly_one_concurrent_winner` (incl. claim-only crash boundary + permanent refusal); empty/partial/unparseable/`claimed` payloads covered; terminal-status payloads not parametrized (Finding 5) |
| Claim/receipt durability injection; empty/partial/unparseable permanent refusal | Covered | flush-order spy, `claim_durability` injection (decode blocked), `terminal_receipt` injection (output preserved, retry refused) |
| Caught post-claim exceptions → `failed_after_claim` with read/unread distinction | Mostly covered | `test_post_claim_failures_publish_only_sanitized_receipts` (3/70, sanitized), `test_claim_durability...` (`test_features_opened=false`); `test_features_opened=true` not asserted on evaluate-failure receipts (Finding 5) |
| Poison development row; unknown split fails first | Covered | `test_test_reader_skips_poison_development_features_before_decode`, `test_unknown_split_fails_before_full_row_decode` |
| Frozen model/scaler/threshold exact use; spies on forbidden paths | Covered | `test_opening_never_calls_training_fit_or_selection_paths`; score equivalence to a manual forward pass not asserted (Finding 5) |
| Score order/hash/schema; reproduced/nonreproduction; success/failure layout; manifest-last | Partial | success layout, canonical SHA, ordering covered; neither terminal status pinned end-to-end; empty-selected sentinel reason untested (Finding 2); manifest-last not explicitly asserted |
| Empty-selected-background efficiency 0.0 / KS 1.0 / sentinel reason normal nonreproduction | Partial | unit-level values covered; reason formation and end-to-end nonreproduction untested (Finding 2) |
| Missing flag exit 2; blank/over-length/credential/`Cc`/`Cf` exit 5; post-claim 3/4/70 | Covered | `test_open_test_requires_all_three_arguments`, `test_sensitive_authorization_reference_is_refused_before_output`, `test_open_test_cli_exit_mapping`, claim_durability/terminal_receipt/publish-failure tests |
| Published output + terminal receipt replace/flush failure: exit 4, permanent refusal, no overwrite | Covered | `test_terminal_receipt_failure_preserves_published_run_and_claim`, `test_terminal_receipt_cli_log_requires_manual_audit` |
| Development tree unchanged except state; poison-free failure/state assertions | Covered | tree receipts before/after; poison assertions in failure.json and state |
| Fixture-only CLI smoke; focused/full pytest; pip check; CLI helps; `git diff --check` | Partial (reviewer scope) | CLI smoke + both helps + fixture tests present; `git diff --check` clean and byte-compile OK per this review; full pytest / pip check / fixture CLI smoke must be run by the implementer per sprint §7 and were not run here |
| Closing evidence: no authoritative `open-test`, no real data, Windows/synthetic non-authoritative | Honored | tests and this review; sprint §10 must record it at close-out |

## Conclusion

**Accept with required follow-ups.** The M1-05 mechanism is implemented with
high fidelity to Test-opening Protocol V1: the pre-claim binding chain, atomic
one-shot claim with two-level durability, permanent-refusal state machine,
test-only reader, frozen evaluation, sanitized receipts, stable exits, and
MC-only test discipline are all in place. Before the sprint's delivery
conclusion (§10) is backfilled and the checklist is checked off, the following
must be addressed:

1. Fix the claim-failure misattribution race (Finding 1, Medium).
2. Add the empty-selected-background sentinel/nonreproduction end-to-end test
   and pin both terminal statuses (Finding 2, Medium).
3. Apply the low-severity exit-code, receipt-path, README, and fd-safety fixes
   (Findings 3, 4, 6, 7) and close the remaining coverage gaps (Finding 5).
4. Run the full verification gate from `neural/` per sprint §7 / `neural/AGENTS.md`
   (focused modules, full `pytest -q`, `pip check`, fixture-only CLI smoke,
   both CLI helps, `git diff --check`) and record that no authoritative
   `open-test` was run and no real data was read.

This review itself did not run `open-test`, did not execute the test suite,
and did not access any real data or held-out test content. Windows/synthetic
verification is not a substitute for the locked `osx-arm64` authority gate.
