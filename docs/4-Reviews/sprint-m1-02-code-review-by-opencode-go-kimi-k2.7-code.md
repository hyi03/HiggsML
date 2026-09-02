# Sprint M1-02 Code Review Report

- **Reviewer:** opencode-go / kimi-k2.7-code
- **Review date:** 2026-09-01
- **Review type:** Code review of the M1-02 implementation change set
- **Primary targets reviewed:**
  - `neural/config/preprocess_protocol_v1.yaml`
  - `neural/config/preprocess_run.example.yaml`
  - `neural/src/config.py`
  - `neural/src/domain/` (`selection.py`, `features.py`, `four_vectors.py`, `angular5.py`, `weights.py`, `splitting.py`, `reconstruction.py`)
  - `neural/src/preprocessing/` (`root_reader.py`, `pipeline.py`, `outputs.py`)
  - `neural/src/artifacts/manifest.py`
  - `neural/src/artifacts/transaction.py`
  - `neural/src/cli/preprocess.py`
  - `neural/tests/unit/test_preprocess_*.py`
  - `neural/tests/integration/test_preprocess_micro_root.py`
  - `neural/tests/integration/test_cli_help.py`
  - `neural/tests/golden/test_preprocess_authority.py`
  - `neural/README.md`
  - `neural/docs/preprocess-protocol-v1.md`
  - `neural/docs/sprint-m1-02.md`
  - `docs/4-Reviews/sprint-m1-02-review-confirm.md`
- **Review criteria:** `Preprocess Protocol V1`, `FR-001`, `neural/AGENTS.md`, root `AGENTS.md`
- **Authority status:** The external r3-ARM64 golden artifacts are absent on this device. The implementation correctly records `authoritative_gate_not_run`; no claim of full-data equivalence is made and no real data or held-out test is opened.

---

## Executive Summary

The M1-02 implementation is a clean, responsibility-separated MC-only preprocessor. It correctly avoids `xgboost/src` imports, binds inputs by SHA-256, preserves signed and normalized weights, reconstructs Base14 + Angular5 features, enforces deterministic row/column order, and publishes the required artifacts with manifest-last ordering. The synthetic test suite passes (`32 passed, 1 skipped`) and the code review found **no Critical defects**.

The remaining issues are concentrated in two areas:

1. **Protocol sealing is incomplete.** The YAML loader validates the most important scientific constants but does not seal branch mappings, the exact 29-column schema, split parameters, serialization settings, ZZ normalization constants, or the frozen sliding-Z2 fields. This is the main risk that a future edit to the protocol YAML could silently diverge from the approved science.
2. **Published artifact schemas drift from Protocol §8.3.** The manifest is missing `counts.per_sample`, `schema.dtypes`, and `software.packages`; the `mc_summary.json` identity block is missing the documented legacy duplicate metadata; and failure receipts are not always complete.

All findings are fixable without changing the core physics logic or opening real data.

---

## Review Findings

| Severity | Type | Location | Issue | Evidence | Recommendation |
|---|---|---|---|---|---|
| High | Protocol sealing / correctness | `neural/src/config.py:93-136`; `neural/config/preprocess_protocol_v1.yaml:1-135` | `load_preprocess_protocol` does not seal several frozen protocol fields. It validates sample metadata, selection thresholds, golden tolerances, and output-column *count*, but ignores branch mappings, exact column names/order, split parameters, serialization settings, ZZ normalization constants, and sliding-Z2 freeze fields. | `config.py:98-112` only compares `(source_sample, dsid, label, profile, tree, unit, sha256)`; `config.py:96` checks `len(output_columns) == 29`; `config.py:93-136` never reads `raw["split"]` or `raw["serialization"]`; `preprocess_protocol_v1.yaml:72-84` contains no `z2_min_mode` or sliding-Z2 block. | Add exact expected branch maps, the expected `output_columns` tuple, expected `split` and `serialization` dicts, expected ZZ normalization values, and frozen sliding-Z2 parameters to the loader; reject any mismatch with `InputBindingError`. |
| High | Artifact schema / completeness | `neural/src/preprocessing/pipeline.py:128-134`; `neural/src/artifacts/manifest.py:33-41` | The published `manifest.json` does not match Protocol §8.3: `counts` lacks `per_sample`, `schema` lacks `dtypes`, and `software` lacks `packages`. | `pipeline.py:134` sets `counts` to `summary["totals"]` only and `schema: {"ordered_columns": ...}`; `manifest.py:33-41` returns python/git/platform with no `packages` field. | Populate `counts.per_sample` from `mc_summary.json` samples; add a `schema.dtypes` map for all 29 columns; record package versions in `software.packages` (e.g., via `importlib.metadata` or `pip freeze`). |
| Medium | Artifact schema / completeness | `neural/src/preprocessing/pipeline.py:122` | `mc_summary.json` omits the required `legacy_duplicate_groups` and `legacy_duplicate_rows` fields from the identity block. | `pipeline.py:122` builds `identity: {"fields": ["source_sample", "source_entry"], "unique": True, "duplicate_count": 0}`. | Add `legacy_duplicate_groups: 2` and `legacy_duplicate_rows: 4` per Protocol §5.2 / §8.2, keeping `duplicate_count: 0` for the canonical identity. |
| Medium | Transaction / audit | `neural/src/artifacts/transaction.py:64-94` | Failure receipts do not always include a stable exit code and timestamp. `RunTransaction.__exit__` only writes `exit_code` and `failed_at_utc` when the exception has an `exit_code` attribute; unexpected internal errors omit both. | `transaction.py:66-74` guards the update with `if exc is not None and hasattr(exc, "exit_code")`; `_write_failure_receipt` (lines 85-94) initially writes only `error_type`, `message`, and `status`. | Always include `failed_at_utc`; derive `exit_code` from `exc.exit_code` when present, otherwise map the exception type to the stable code (e.g., `70` for unexpected internal errors) so every receipt is complete. |
| Medium | Protocol sealing / correctness | `neural/src/domain/splitting.py:6-9`; `neural/src/config.py:93-136` | The split algorithm is hardcoded and never validated against the protocol YAML. | `splitting.py:6-9` hardcodes BLAKE2b digest_size=8, big-endian, modulo 10, and bucket boundaries; `config.py` never inspects `raw["split"]`. | Either read split parameters from the sealed protocol and pass them into `event_split`, or validate `raw["split"]` against the expected frozen dict in `load_preprocess_protocol`. |
| Medium | Protocol transcription | `neural/config/preprocess_protocol_v1.yaml:72-84` | The protocol YAML is missing the frozen sliding-Z2 parameters required by Protocol §3.2. | The YAML `selection` block ends at `m4l_window_gev`; there is no `z2_min_mode: fixed` block or `low_m4l/high_m4l/low_min/high_min/max` frozen fields. | Add the frozen sliding-Z2 block to `preprocess_protocol_v1.yaml`, seal it in the loader, and emit `z2_min_mode` in `cutflow.json` from the sealed value. |
| Medium | Test coverage | `neural/tests/unit/test_preprocess_domain.py`; `neural/tests/integration/test_preprocess_micro_root.py`; `neural/tests/unit/test_preprocess_outputs.py` | Several protocol-mandated behaviors are not exercised by tests. | Domain tests cover only one isolation boundary and one split identity; micro-root tests do not assert deterministic canonical-hash equality across two runs, missing/extra branch rejection, channelNumber != DSID, normalization drift, or manifest-last ordering; output tests do not assert non-finite/integer enforcement. | Add synthetic tests (no real data) for each selection boundary, Angular5 degenerate geometry, ROOT schema rejection, split bucket boundaries, canonical CSV rejection of invalid values, and manifest-last behavior. |
| Low | Canonical serialization | `neural/src/preprocessing/outputs.py:43-58` | `canonical_csv_bytes` relies on `csv.writer`, which would quote enum strings if they ever contained CSV special characters. | `outputs.py:43-58` writes string columns `split` and `source_sample` via `csv.writer` without a whitelist check. | Validate that string values match the protocol enum whitelist before writing, or replace `csv.writer` with a deterministic `",".join` that fails on disallowed characters. |
| Low | CLI robustness | `neural/src/cli/preprocess.py:27` | The default `allowed_root` is derived from the source-tree location and is incorrect if the package is installed as a wheel. | `preprocess.py:27` computes `Path(__file__).resolve().parents[2] / "runs"`. | Default `allowed_root` to the current working directory's `runs/` (project-root convention) or add an explicit `--allowed-root` CLI option; retain the test override. |
| Low | Code duplication | `neural/src/domain/selection.py:36-39` | `SelectionConfig.v1()` duplicates the frozen thresholds already in the protocol YAML. | `selection.py:36-39` hardcodes thresholds; tests call `SelectionConfig.v1()` independently of the sealed protocol. | Remove `SelectionConfig.v1()` from production code and construct test fixtures from the loaded protocol, or assert that `v1()` always matches the sealed protocol values. |
| Low | Manifest completeness | `neural/src/preprocessing/pipeline.py:134` | `performance.peak_memory_bytes` is always `None` in the manifest. | `pipeline.py:134` sets `"peak_memory_bytes": None`. | Measure peak RSS with `tracemalloc` or `resource`/`psutil` and record the value, or document that it is intentionally unmeasured on this platform. |
| Info | Positive / safety | `neural/src/`, `neural/tests/` | No `xgboost/src` runtime dependency; MC-only boundary preserved. | `grep` finds no `import xgboost` or `xgboost/src` import under `neural/src`; all fixtures are generated in temporary directories. | None; maintain. |
| Info | Positive / verification | `neural/tests/golden/test_preprocess_authority.py:29-34`; `neural/README.md:7` | The absent r3-ARM64 artifact is correctly handled as `authoritative_gate_not_run`. | Golden test skips with `authoritative_gate_not_run`; README states the gate has not run locally. | None; do not claim full-data equivalence until the gate runs on locked `osx-arm64`. |
| Info | Positive / test status | `neural/tests/` (run under `conda run -n pytorch`) | Existing synthetic test suite passes. | `conda run -n pytorch python -m pytest -q tests/unit tests/integration tests/golden` reports `32 passed, 1 skipped`. | None; keep running focused tests before the full suite per `neural/AGENTS.md`. |

---

## Verification Performed

- Read all listed source, config, test, and documentation targets.
- Inspected `git status` and `git diff` for tracked modifications.
- Confirmed no `xgboost/src` imports or real-data paths in the new code.
- Ran the project test suite in the `pytorch` Conda environment:

  ```powershell
  conda run -n pytorch python -m pytest -q tests/unit tests/integration tests/golden
  ```

  Result: `32 passed, 1 skipped`.

- The single skipped test is `test_external_r3_table_hash_when_available`, which correctly records `authoritative_gate_not_run` because the external r3-ARM64 artifact is not present on this device.

---

## Conclusion

**Verdict: Conditionally acceptable for M1-02, with the High and Medium findings above addressed before claiming Sprint completion.**

The implementation correctly encodes the approved preprocessing physics and passes the synthetic test suite. The dominant remaining risk is incomplete sealing of the protocol YAML: the loader must reject any change to branch maps, output columns, split/serialization parameters, ZZ normalization, and sliding-Z2 freeze fields, because those are exactly the values the golden gate will compare. The manifest and summary schemas also need to be brought into full compliance with Protocol §8 before the run artifacts can be considered audit-complete.

No real data or held-out test data was opened. The external r3-ARM64 golden gate remains recorded as `not run`; Windows and synthetic results are development verification only and do not substitute for the locked `osx-arm64` authority gate.
