# Sprint M1-06 Code Review Report

**Review target**

- Git diff from `HEAD` (`85b67d1`) to working tree: tracked changes in `.gitignore`, `neural/README.md`, `neural/docs/sprint-m1-06.md`.
- Untracked M1-06 implementation files:
  - `neural/docs/runbook.md`
  - `neural/docs/artifact-schema.md`
  - `neural/docs/m1-06-verification-evidence.md`
  - `neural/docs/final-technical-report.md`
- Document-review artifacts:
  - `docs/4-Reviews/sprint-m1-06-review-by-opencode-go-kimi-k2.7-code.md`
  - `docs/4-Reviews/sprint-m1-06-review-by-opencode-go-glm-5.2.md`
  - `docs/4-Reviews/sprint-m1-06-review-confirm.md`

**Review type:** Code review

**Reviewer:** opencode-go / kimi-k2.7-code

**Date:** 2026-09-02

**Sources of truth:**

- `neural/docs/sprint-m1-06.md`
- `neural/docs/FR-001-adversarial-mlp-refactor.md`
- `neural/AGENTS.md`
- `neural/docs/preprocess-protocol-v1.md`
- `neural/docs/development-protocol-v1.md`
- `neural/docs/test-opening-protocol-v1.md`
- `neural/config/preprocess_protocol_v1.yaml`
- `neural/config/adversarial_mlp_protocol_v1.yaml`
- Existing implementation under `neural/src/` and `neural/tests/`

**Scope discipline:** Strictly MC-only. No real data was read, hashed, probed, preprocessed, scored, plotted, or published. No held-out test was opened or decoded. No `open-test` command was executed. No source, config, protocol, or frozen run artifact was modified except for writing this review report.

---

## Executive Summary

The M1-06 change set is a documentation-and-hygiene implementation that addresses the accepted findings from the prior document review. It correctly:

- creates the four required deliverable documents (`runbook.md`, `artifact-schema.md`, `m1-06-verification-evidence.md`, `final-technical-report.md`);
- updates `neural/README.md` to the M1-06 blocked status and links the new documents;
- adds a precise `.gitignore` rule for `neural/config/preprocess_run.local.yaml`;
- inlines the bound ROOT/golden hashes and the `run_authority_gate` invocation path;
- adopts the `method × platform × data_scope × authority` evidence taxonomy;
- records the Windows/AMD64 preflight blocker and the required authority gates as `blocked`/`not_run`.

The verified Windows evidence claims (`pip check` exit 0, two CLI `--help` smokes exit 0, focused suite `23 passed`, full suite `227 passed, 2 skipped`) match independent re-runs on this host.

Remaining concerns are tooling and test-coverage gaps around the `run_authority_gate` invocation path, plus a few low-severity documentation/audit precision items. No scientific-safety boundary violation or evidence overclaim was identified. The implementation should not be committed as M1-06 complete until the locked native `osx-arm64` authority gates are executed and transcribed.

---

## Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| Medium | Risk | `neural/docs/runbook.md` L112; `neural/docs/sprint-m1-06.md` L191; `neural/src/preprocessing/authority.py` L193-237 | `run_authority_gate` has no version-controlled executable entry point; the only invocation is a user-pasted Python one-liner. This is error-prone (wrong cwd, typo in `repository_root`, path mismatch) and not reproducible by a script. | No file under `neural/scripts/`; `git grep run_authority_gate` shows only the definition and documentation references. | Add a thin controlled runner script (e.g., `neural/scripts/run_authority_gate.py`) or expose `python -m src.preprocessing.authority` with locked cwd/path validation. Keep `pyproject.toml` console entry points at exactly two. |
| Medium | Test | `neural/tests/golden/test_preprocess_authority.py` L10-14; `neural/src/preprocessing/authority.py` L193-237 | The complete `run_authority_gate` call path is not exercised by the test suite. Existing golden tests cover comparator logic, platform refusal, and lineage hashes, but not the gate's orchestration, evidence-file creation, or count/cutflow integration. | `test_preprocess_authority.py` imports `AuthorityGateError`, `compare_tables`, `require_authority_platform`; it does not import `run_authority_gate`. | Add a synthetic (non-authority) integration test that monkeypatches `require_authority_platform` and calls `run_authority_gate` on a micro preprocess run, asserting the evidence JSON content and exclusive-create behavior. |
| Low | Correctness | `neural/src/preprocessing/authority.py` L234-237 | `run_authority_gate` opens the evidence file with `"xb"` but does not catch `FileExistsError` and map it to a stable exit code. A duplicate evidence path produces an unhandled exception rather than the declared `RunPathError` / exit 4. | `with destination.open("xb") as stream:` is unwrapped. | Wrap exclusive-create failure in `AuthorityGateError` or raise `RunPathError` so the caller receives a stable exit code 4 with a clear message. |
| Low | Risk | `neural/src/preprocessing/authority.py` L200-202 | The gate hard-codes the protocol path as `repository / "neural/config/preprocess_protocol_v1.yaml"`. This couples the authority comparator to a single filename and does not allow using a renamed, hash-bound protocol snapshot. | Function signature has no `protocol_path` argument; runbook command does not pass one. | Accept an optional `protocol_path` argument defaulting to the sealed path, or explicitly document the hardcoded path as part of the sealed contract. |
| Low | Risk | `neural/src/preprocessing/authority.py` L198-199 | `run_authority_gate` resolves `new_run_dir` directly without verifying containment under the allowed `neural/runs/` root. | `Path(new_run_dir).resolve()` is used; no `relative_to(allowed_root)` check. | Add an allowed-root containment check so the gate enforces the same run-path hygiene as `RunTransaction`. |
| Low | Consistency | `neural/docs/sprint-m1-06.md` L234; `neural/docs/m1-06-verification-evidence.md` L31 | The mandated static audit regex `xgboost[\\/]+src` cannot catch Python dotted imports such as `import xgboost.src` or `from xgboost.src import ...`. | The regex only matches slash/backslash separators; no secondary grep covers dotted access. | Extend the audit regex to `xgboost[.\\/]+src` or add a companion grep for `from xgboost` / `import xgboost`. |
| Low | Clarity | `neural/docs/m1-06-verification-evidence.md` L37 | The full local suite is labeled `data_scope: synthetic_mc`, but one of the two skipped tests (`test_external_r3_table_hash_when_available`) is a `source_only` external-table hash check. Bundling the whole suite under `synthetic_mc` slightly blurs the evidence taxonomy. | `-rs` output shows skip reason: `authoritative_gate_not_run: external r3-ARM64 table is absent`. | Add a footnote to the full-suite record noting that the skipped item is `source_only`, or record it separately under `source_only` while keeping the synthetic tests under `synthetic_mc`. |
| Low | Documentation | `neural/docs/artifact-schema.md` section 2 (Preprocess manifest table) | The first audit block is named "identity" even though it lists top-level manifest header/status fields; this collides with the actual `identity` block inside `mc_summary.json`. | Table row "identity" contains `schema_version`, `status`, `run_type`, `protocol_id`, etc. | Rename the block to "header" or "status" to avoid confusion with the `identity` duplicate-count block. |
| Low | Risk | `neural/docs/sprint-m1-06.md` L208-211 | The byte-freeze command for authority execution covers `neural/src` and the two sealed protocol YAMLs, but not `neural/src/cli/*` or `neural/tests/golden/test_preprocess_authority.py`. Changes there could alter evidence format or comparator contract without being caught by the freeze check. | Command: `git diff --exit-code 85b67d1 -- src config/preprocess_protocol_v1.yaml config/adversarial_mlp_protocol_v1.yaml`. | Expand the freeze list to include `src/cli/preprocess.py`, `src/cli/train.py`, and `tests/golden/test_preprocess_authority.py`, or state explicitly that any change to CLI/golden tests affecting evidence format is a review trigger. |
| Info | Documentation | `neural/README.md` L7-9, L181-187; `neural/docs/sprint-m1-06.md` L51-54 | The four required M1-06 deliverable documents have been created and the README banner now reflects the M1-06 blocked state with links to the runbook, artifact schema, evidence, and final report. | Files exist and are referenced. | No action required; preserve these links as the documents evolve. |
| Info | Correctness | `neural/docs/m1-06-verification-evidence.md` L28-38 | The recorded Windows/synthetic evidence claims were independently verified: `pip check` exit 0, both CLI `--help` exit 0, focused suite `23 passed`, full suite `227 passed, 2 skipped` with the two documented skip reasons. | Re-runs on 2026-09-02 produced identical counts and skip reasons. | No action required; ensure future edits to the evidence file are re-verified. |
| Info | Requirement | `.gitignore` L226 | The local run configuration path `neural/config/preprocess_run.local.yaml` is now ignored, closing the prior review risk of committing absolute MC ROOT paths. | `git check-ignore -v neural/config/preprocess_run.local.yaml` returns the matching rule. | No action required; keep the rule and continue verifying with `git check-ignore` before any commit. |

---

## Positive Observations

- **Authority boundary is preserved.** All documents state that the current host is Windows/AMD64, that locked native `osx-arm64` gates are `blocked`/`not_run`, and that Windows/synthetic results do not substitute for authority evidence.
- **No real-data or held-out-test exposure.** The evidence files and final report explicitly record that no real data was read/hashed/preprocessed/scored/plotted and that `open-test` remains `not_run` without separate user authorization.
- **Sealed protocols are unchanged.** `git diff --exit-code 85b67d1 -- src config/preprocess_protocol_v1.yaml config/adversarial_mlp_protocol_v1.yaml` returns exit 0.
- **`run_authority_gate` implementation matches the documented contract.** It performs lineage hash verification, per-column golden comparison, count verification, duplicate verification, and cutflow comparison, then writes an exclusive evidence file.
- **Static forbidden-reference audit is clean.** `rg -n "xgboost[\\/]+src|full-baseline-2026-08-10|700600" src config` returns no matches.

---

## Conclusion

The M1-06 change set is an acceptable documentation-and-boundary implementation. It resolves the accepted items from the prior document review, correctly records the Windows preflight blocker, and does not claim authority closure. The remaining gaps are low-to-medium tooling and test-coverage issues centered on `run_authority_gate` invocation and audit precision; none relax scientific-safety constraints.

Do **not** mark M1-06 complete or commit it as closed until:

1. The locked native `osx-arm64` environment is restored from `osx.yml`.
2. The full-data preprocess run is executed and passes `run_authority_gate` with an independent evidence file.
3. The complete five-candidate five-fold development OOF is run and its actual qualification branch is audited.
4. All evidence is transcribed into `neural/docs/m1-06-verification-evidence.md` with the required `method × platform × data_scope × authority` fields.

`open-test` remains out of scope unless the user separately and explicitly authorizes it against a specific eligible frozen development run.
