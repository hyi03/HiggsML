# Sprint M1-04 Code Review

- Reviewer model: `opencode-go-kimi-k2.7-code`
- Review type: code review (read-only source review)
- Date: 2026-09-02
- Scope: Sprint M1-04 working-tree change set
- Reviewed files:
  - `src/training/test_opening.py` (new)
  - `src/cli/xgboost.py` (modified)
  - `src/training/trainer.py` (modified)
  - `tests/refactor_training_support.py` (modified)
  - `tests/unit/test_refactor_test_opening.py` (new)
  - `tests/integration/test_refactor_open_test_cli.py` (new)

## 1. Method and constraints

This review inspects the working-tree contents directly, including untracked M1-04
files. It is a read-only source review: no tests, package managers, venv commands,
installers, formatters, git mutations, or environment-changing commands were run.
Only this report file is written.

Source-of-truth consulted: `AGENTS.md`,
`docs/1-Requirement/FR-001-angular19-xgboost-refactor.md`,
`docs/3-Plan/sprint-m1-04.md`,
`docs/superpowers/specs/2026-09-01-xgboost-refactor-design.md` (§6.3/§10/§11),
`config/preprocessing_protocol_v1.yaml`, `config/xgboost_protocol_v1.yaml`.

Test execution is treated as already externally verified. Findings below are from
source and test-coverage inspection; they do not re-run the suite.

## 2. Summary verdict

The M1-04 `open-test` implementation is correct and well-engineered with respect to
its core safety contracts. The ordering that matters most is implemented exactly
as the sprint requires:

1. reserve a fresh test run directory (atomic, no-clobber, refuse occupied);
2. validate all upstream/eligibility/hash identity using manifest metadata and
   `lstat` only — **without reading test bytes**;
3. atomically claim `state/test_opening.json` via exclusive create;
4. read/hash/decompress/parse/score the test bytes exactly once;
5. re-verify every source byte and the test fingerprint before publishing;
6. publish the success manifest, or a `failure.json` on any exception.

No Critical or High correctness defect was found. The main observations are
test-coverage gaps (no legacy golden numeric equivalence test, thread-only
concurrency coverage) and low-severity hardening/clarity notes. None of them
weakens the fail-closed claim semantics, threshold provenance, or output
allowlist.

## 3. Findings table

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| Medium | Missing test | `tests/unit/test_refactor_test_opening.py` | No characterization/golden test locks `_test_metrics` / plot semantics to the legacy `experiment_runner._test_metrics` | `_test_metrics` is a verbatim copy (`src/training/test_opening.py:410-433` == `src/experiment_runner.py:574-601`), but no test compares outputs; sprint 5.2 explicitly lists "Golden 对照 legacy score/metrics/三张 plot 的输入语义" | Add a golden/characterization test asserting identical `test_metrics.json` fields (weighted/unweighted AUC, per-class efficiency, selected_rows) and identical score semantics on a shared fixture |
| Medium | Missing test | `tests/unit/test_refactor_test_opening.py:290-308` | Concurrency is tested only with threads (`ThreadPoolExecutor`), not across processes | Claim atomicity rests on `open("xb")` O_EXCL (`src/training/test_opening.py:387`), which is process-atomic, but no multi-process test exercises it | Add a two-subprocess concurrency test (two `run_open_test` in separate processes on distinct run-dirs) asserting exactly one winner |
| Low | Defensive coding | `src/training/test_opening.py:410-433` | `_test_metrics` divides by class weight sum without an in-function guard | Denominator safety is established only in `_validate_test_frame` (`:404-407`), a separate function | Add an explicit per-class denominator `<= 0` guard inside `_test_metrics` for defense-in-depth |
| Low | TOCTOU hardening | `src/training/test_opening.py:370-375` | `state.is_symlink()` check and `state.mkdir(exist_ok=True)` are not a single atomic unit | `if state.is_symlink(): raise` then `state.mkdir(exist_ok=True)`; a concurrent actor could swap `state/` between the check and mkdir | Use `os.mkdir`/`os.open` with `O_NOFOLLOW`, or `mkdir` then re-verify `lstat` is a directory and not a symlink before opening the claim |
| Low | Robustness | `src/training/test_opening.py:387-388` | Claim write is `open("xb")` + `write`, not fsync/atomic | A crash between open and write leaves a partial claim that still blocks re-open (safe/fail-closed) but is not content-verified on later attempts | Acceptable per design; optionally fsync before close, and treat any pre-existing claim as terminal regardless of content (already the case) |
| Low | CLI hardening | `src/cli/xgboost.py:11-24` | `argparse` allows option-prefix abbreviation by default | `--dev`/`--run` would silently resolve to `--development-run`/`--run-dir`; not a scientific override but weakens the "reject unknown" contract | Pass `allow_abbrev=False` to `ArgumentParser` for the `open-test` surface |
| Info | Clarity | `src/training/test_opening.py:556-560` | Test-run manifest `claim.path` is `state/test_opening.json`, scoped to the *development* run, not the test run | The test run contains no `state/`; the path is only meaningful relative to `development_run.path` (`:561-564`) | Document this scoping or record the absolute claim path to avoid ambiguity |
| Info | Design note | `src/training/test_opening.py:469-476` | `score_vs_m4l.png` reveals the held-out test mass distribution | Approved plot in design §10.2 / sprint 5.2; MC-only, not real data, so not a blinding violation | No action; retain as an intentional approved artifact |
| Info | Efficiency | `src/training/test_opening.py:500-502` | Full expensive validation (OOF decompress, working-point rebuild, qualification re-derivation) runs before the atomic claim | `_validate_development` is invoked before `_claim`; concurrent losers redo the entire validation | Not a correctness issue; acceptable given the claim must follow full fail-closed validation |
| Info | Fingerprint | `src/training/test_opening.py:98-107` | `st_ino` fallback and ctime semantics differ by platform | `getattr(info, "st_ino", 0)`; Windows `st_ctime` differs; but any content change is also caught by the compressed SHA check (`:508`) | No action; the SHA check is the authoritative content guard |

## 4. Detailed findings

### 4.1 Correctness: claim ordering (verified correct)

`run_open_test` (`src/training/test_opening.py:494-592`) enforces the required
sequence. `RunTransaction.__enter__` (`src/artifacts/transaction.py:21-26`) claims
the fresh run dir atomically (`mkdir` after `_validate_target` refuses existing
paths). `_validate_development` performs the upstream binding and eligibility
checks; its only interaction with the held-out test is `_resolve_test_path`
(`:110-133`), which uses `_safe_artifact` (path-containment/`resolve`) and
`_file_fingerprint` (`lstat`) — no byte read. The claim is created by `_claim`
(`:370-391`) before the single `read_regular_bytes(test_path, ...)` at `:506`.
This is confirmed by the spy test
`test_open_test_claims_before_read_and_publishes_exact_contract`
(`tests/unit/test_refactor_test_opening.py:53-93`), which asserts the claim file
exists at the moment the test bytes are read. No test-byte read precedes the
claim.

### 4.2 Exactly-once and fail-closed claim

The exclusive claim is implemented with `claim_path.open("xb")` (`:387`), which is
`O_CREAT|O_EXCL` and therefore atomic across processes. A loser of the race
receives `FileExistsError`, which is re-raised as `FileExistsError("held-out test
has already been opened")` (`:389-390`). Because the claim precedes any test read,
a post-claim failure permanently consumes the opening right: `test_claimed_failure_is_terminal...`
(`:113-133`) and `test_same_size_corrupt_test_fails_after_claim_and_consumes_opening`
(`:232-246`) both assert a pre-existing claim blocks re-open. Pre-claim validation
failures correctly do **not** consume the right (`test_preclaim_qualification_tamper...`,
`test_upstream_artifact_tamper...`, `test_unknown_development_layout...`).

### 4.3 Immutable upstream binding (verified thorough)

`_validate_development` (`:165-367`) validates, before the claim:

- the development run is a non-symlink directory and unopened (`:166-170`);
- manifest V1 schema/run_type/status/test_opened (`:185-191`);
- exact nine-file allowlist (`:318-331`);
- every output receipt's SHA-256 and size (`_receipt_bytes`, `:80-95`);
- sealed `config.yaml` SHA == manifest protocol identity, re-parsed by the V1
  loader (`:249-257`);
- upstream preprocess manifest SHA == binding (`:263-264`);
- preprocess protocol/run_config identity and preprocessing protocol hash
  (`:265-282`);
- working points rebuilt from OOF and compared field-for-field (`:284-299`);
- qualification re-derived (AUC/KS/efficiency/integrity) and compared, requiring
  `eligible is True` (`:300-305`);
- counts/schema/candidate/selected_candidate consistency (`:306-317`);
- model loads and its booster feature names equal the frozen 19-feature order
  (`_load_model`, `:136-146`).

This satisfies the sprint's requirement to re-derive qualification evidence rather
than trusting the `eligible` string, and to never write back development bytes.
`_verify_preclaim_sources` (`:484-491`) re-reads all ten source artifacts plus the
claim and compares to the originally-read bytes before publication, and
`test_success_does_not_write_back_any_development_artifact` (`:311-327`) proves no
development artifact (other than the new claim) is modified.

### 4.4 Scientific equivalence and threshold provenance (verified correct)

`_test_metrics` (`src/training/test_opening.py:410-433`) is a byte-for-byte copy of
the legacy `experiment_runner._test_metrics` (`src/experiment_runner.py:574-601`):
weighted AUC on `abs(physical_weight)`, unweighted AUC, and per-working-point
`threshold` / per-class weighted `efficiency` / `selected_rows`. Thresholds are
taken from `evidence["working_points"]` — the frozen development working points —
and never recomputed from protocol targets or test scores.
`test_frozen_threshold_comes_only_from_development_working_points` (`:152-165`) and
`test_test_scores_cannot_change_frozen_thresholds` (`:330-348`) verify this. No
test KS, qualification gate, reproduction gate, or test-result decision is
introduced, matching the sprint's explicit prohibition.

### 4.5 Output allowlist (verified correct)

The success test run publishes exactly six files:
`artifacts/test_metrics.json`, `artifacts/manifest.json`,
`predictions/test_scores.csv.gz`, and the three approved plots. No `config.yaml`,
`model/`, or `state/` is written. `test_open_test_claims_before_read_and_publishes_exact_contract`
(`:73-80`) asserts this exact set. `PREDICTION_COLUMNS = OUTPUT_COLUMNS + ("xgb_score",)`
yields the required 33-column prediction table, and the score gzip uses
`mtime=0`/`compresslevel=9` for determinism (`:530`).

### 4.6 Failure receipts

`RunTransaction.__exit__` (`src/artifacts/transaction.py:28-38`) writes `failure.json`
on any uncaught exception with no success manifest. The occupied-output case is
handled correctly because `_validate_target` raises before `__enter__` claims the
directory, so `__exit__` never runs and no receipt is written
(`test_occupied_output_is_zero_read_and_zero_write`, `:96-110`). Failure messages
are generic `ValueError` strings (parse/decompress errors are wrapped, `:510-519`),
so no test bytes, scores, labels, or event content leak into stderr or
`failure.json`.

### 4.7 CLI surface

`open-test` accepts only `--development-run` and `--run-dir`
(`src/cli/xgboost.py:21-23`). Override options are rejected by argparse
(`test_open_test_parser_rejects_all_overrides`). `main` catches only `Exception`
(not `BaseException`), normalizes to `higgsml-xgboost failed: Type: message` with
exit 1, and prints `succeeded` on success. `KeyboardInterrupt`/`SystemExit` remain
uncaught, matching the sprint's "不捕获 BaseException" requirement, while still
producing a `failure.json` via the transaction's `__exit__`.

## 5. Test coverage assessment

Covered well:

- claim-before-read ordering (spy), exactly-once read;
- occupied output = zero read/zero write;
- post-claim failure terminal + second run-dir rejection;
- pre-claim tamper (qualification, upstream artifacts, preprocess manifest,
  unknown layout, ineligible run) without consuming claim;
- same-size corrupt test and invalid schema fail only after claim;
- thread-level concurrency single-winner;
- no write-back to development run on success;
- frozen thresholds unaffected by poisoned scores.

Gaps (see table): no legacy golden numeric-equivalence test, no cross-process
concurrency test, no explicit symlink/path-escape rejection test for the test
artifact receipt (mitigated by the exact-path requirement in `_safe_artifact`,
`src/training/test_opening.py:63-77`, which makes escape impossible by
construction).

## 6. Requirement and sprint conformance

- FR-001 R6 (one-time test-opening): satisfied — atomic claim, failure consumes
  the opening, no retrain/rethreshold/write-back.
- FR-001 R7 (artifact/failure semantics): satisfied — fresh no-clobber run dirs,
  symlink/path-escape/input-substitution rejection, failure receipt without
  success manifest, full manifest binding.
- Sprint M1-04 §5.1 (binding & claim), §5.2 (frozen test evaluation), §5.3 (CLI):
  all task-checklist items are implemented; the two test-coverage items noted
  above (legacy golden, multi-process concurrency) are partial.
- Design §10.2 test-run tree and §11 immutability/claim-consumption: satisfied.
- No real data, frozen run, or authoritative test-opening is performed; fixtures
  are synthetic (`tests/refactor_training_support.py`).

## 7. Conclusion

The M1-04 implementation is correct, fail-closed, and meets its scientific-safety
contracts. No blocking issue was found. Recommended follow-ups are additive test
hardening (legacy golden equivalence, cross-process concurrency) and a few
low-severity defensive/CLI clarity improvements enumerated in the findings table.
