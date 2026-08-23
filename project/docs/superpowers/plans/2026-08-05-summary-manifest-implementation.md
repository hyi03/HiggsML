# Separate Data/MC Summary and Run Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task-by-task. Every feature
> change follows red-green-refactor and no real ROOT preparation run is permitted.

**Goal:** Replace the mixed data/MC summary with validated per-sample sections and
write a reproducible preprocessing manifest containing exact file hashes and run
controls.

**Architecture:** Add a dedicated `src.provenance` module containing immutable
summary inputs, pure payload builders, streaming SHA-256, environment/git
discovery, and deterministic JSON output. Keep physics selection in `src.pipeline`,
then wire prepared frames and cutflows into provenance from `prepare_demo.py`.

**Tech Stack:** Python 3.12, pandas, NumPy, PyYAML, `importlib.metadata`,
`hashlib`, `subprocess`, pytest.

## Global constraints

- Implement only roadmap Task 3: summary and run manifest.
- Do not change selection, pairing, features, labels, weights, or sample size.
- Do not run `prepare_demo.py` against the configured real ROOT files.
- Do not inspect the real-data 120--130 GeV signal window.
- Do not overwrite current `data/processed/` or `outputs/` artifacts.
- Use synthetic DataFrames and temporary dummy files in every new test.
- The repository currently has no commit; do not stage or create a commit.

---

### Task 1: Build and validate the separated summary

**Files:**

- Create: `src/provenance.py`
- Create: `tests/test_summary.py`

**Interfaces:**

```python
SUMMARY_SCHEMA_VERSION = "1.0"

@dataclass(frozen=True)
class SampleSummaryInput:
    sample_name: str
    kind: Literal["data", "mc"]
    frame: pd.DataFrame
    cutflow: Mapping[str, Any]
    period: str | None = None
    expected_dsids: tuple[int, ...] = ()
    label: int | None = None

def build_data_summary(samples: Sequence[SampleSummaryInput]) -> dict[str, Any]: ...
def write_json(payload: Mapping[str, Any], path: str | Path) -> None: ...
```

- [ ] **Step 1: Add failing data-summary tests**

Create synthetic selected data containing one duplicated `(runNumber,
eventNumber)` pair. Assert period, read count, selected count, unique pair count,
and duplicate pair count. Assert the entry has no MC-only weight or DSID fields.

Also assert top-level `rows`, `labels`, and `weight_summary` are absent.

- [ ] **Step 2: Add failing MC-summary tests**

Use weights `[2.0, -0.5, 0.0]` and DSID `345060`. Assert:

```python
assert entry["signed_sum_physical_weights"] == 1.5
assert entry["absolute_sum_physical_weights"] == 2.5
assert entry["negative_weight_events"] == 1
assert entry["negative_weight_fraction"] == pytest.approx(1 / 3)
```

Assert an empty selected frame reports a zero negative fraction.

- [ ] **Step 3: Run summary tests and verify failure**

```bash
.venv/bin/python -m pytest tests/test_summary.py -q
```

Expected: FAIL because `src.provenance` does not exist.

- [ ] **Step 4: Implement the minimum summary builder**

Sort samples by `sample_name`, place them under `data` or `mc`, and derive all
statistics only from each sample's selected frame. Read and selected counts come
from the named cutflow stages.

- [ ] **Step 5: Add failing validation tests**

Cover:

- missing data identifiers;
- missing or non-finite MC `physical_weight`;
- unexpected observed DSID;
- missing expected DSIDs;
- cutflow kind/sample-name mismatch;
- missing `read` or `selected` stage;
- selected-stage count versus frame-length mismatch;
- duplicate sample names and unsupported sample kinds.

- [ ] **Step 6: Implement validation**

Require non-negative integer counts, `read_events >= selected_events`, matching
sample metadata, and observed `channelNumber` values contained in configured
DSIDs. Expected DSIDs may be absent from a finite selected subset, but unexpected
observed DSIDs are an error.

- [ ] **Step 7: Add and pass deterministic-writer tests**

Write the same fixed payload twice, assert identical bytes, sorted insertion order,
UTF-8 encoding, parent-directory creation, and a trailing newline.

Run:

```bash
.venv/bin/python -m pytest tests/test_summary.py -q
```

Expected: PASS.

### Task 2: Build the run manifest

**Files:**

- Modify: `src/provenance.py`
- Create: `tests/test_manifest.py`

**Interfaces:**

```python
MANIFEST_SCHEMA_VERSION = "1.0"

def sha256_file(path: str | Path) -> str: ...
def software_versions() -> dict[str, str]: ...
def discover_git_commit(cwd: str | Path) -> str: ...
def build_run_manifest(
    *,
    config_path: str | Path,
    input_paths: Mapping[str, str | Path],
    processing: Mapping[str, Any],
    created_at_utc: str | None = None,
    versions: Mapping[str, str] | None = None,
    git_commit: str | None = None,
    git_cwd: str | Path = ".",
    cutflow_schema_version: str = "1.0",
) -> dict[str, Any]: ...
```

- [ ] **Step 1: Add failing hashing tests**

Hash temporary files with known byte content and compare to `hashlib.sha256`.
Assert missing paths fail and input entries include path, size, and hash.

- [ ] **Step 2: Add failing manifest-shape tests**

Inject a fixed UTC timestamp, software versions, and git SHA. Assert exact config
hash, all three sorted input records, processing values, and all output schema
versions.

- [ ] **Step 3: Run manifest tests and verify failure**

```bash
.venv/bin/python -m pytest tests/test_manifest.py -q
```

Expected: FAIL because manifest helpers are not implemented.

- [ ] **Step 4: Implement streaming hashes and manifest construction**

Read files in fixed-size binary chunks. Generate UTC time with second precision and
`Z` suffix when the caller does not inject it. Preserve `entry_stop=None` as JSON
`null`.

- [ ] **Step 5: Add failing environment and git-discovery tests**

Mock package metadata to verify the keys `python`, `numpy`, `pandas`, `pyyaml`,
`uproot`, `xgboost`, and `scikit-learn`. Mock `git rev-parse HEAD` success and
failure; failure must return `"unavailable"` without raising.

- [ ] **Step 6: Implement environment and git discovery**

Use `platform.python_version()` and `importlib.metadata.version()` without
importing heavyweight packages. Execute only `git rev-parse HEAD`, capture output,
and validate a 40-character hexadecimal SHA before returning it.

- [ ] **Step 7: Run manifest and summary tests**

```bash
.venv/bin/python -m pytest tests/test_manifest.py tests/test_summary.py -q
```

Expected: PASS.

### Task 3: Wire provenance into the preparation script

**Files:**

- Modify: `src/pipeline.py`
- Modify: `scripts/prepare_demo.py`
- Modify: `tests/test_prepare_script.py`

- [ ] **Step 1: Add failing CLI integration expectations**

Update the script test to:

- create three temporary dummy ROOT paths referenced by its YAML;
- make fake prepared data include `runNumber` and `eventNumber`;
- make fake MC include `channelNumber`, `physical_weight`, and labels;
- provide realistic `read` and `selected` cutflow stages;
- invoke `--output-dir artifacts`;
- assert `cutflow.json`, `data_summary.json`, and `run_manifest.json` exist there;
- assert the manifest hashes the exact YAML and three dummy inputs;
- assert no artifact is written to the default `outputs/` path.

- [ ] **Step 2: Run the script test and verify failure**

```bash
.venv/bin/python -m pytest tests/test_prepare_script.py -q
```

Expected: FAIL because `--output-dir` and provenance wiring do not exist.

- [ ] **Step 3: Add a cutflow schema constant**

Define `CUTFLOW_SCHEMA_VERSION = "1.0"` in `src.pipeline` and use it in
`write_cutflow`; keep the emitted JSON unchanged.

- [ ] **Step 4: Implement script wiring**

Keep each `PreparedSample` with its configured metadata. Build
`SampleSummaryInput` records for two MC samples and one data period. Write all
three JSON artifacts under `args.output_dir`. Pass this exact processing block to
the manifest:

```python
{
    "tree_name": config.get("tree_name"),
    "momentum_unit": config.get("momentum_unit", "MeV"),
    "entry_stop": config.get("entry_stop"),
    "random_seed": config.get("random_seed"),
    "selection": {"z2_min_mode": selection.z2_min_mode},
}
```

Remove `write_summary` and its obsolete `weight_summary` import from
`src.pipeline` only after the script no longer imports them.

- [ ] **Step 5: Run focused integration and regressions**

```bash
.venv/bin/python -m pytest tests/test_prepare_script.py tests/test_cutflow.py tests/test_summary.py tests/test_manifest.py -q
```

Expected: PASS.

### Task 4: Documentation and verification

**Files:**

- Modify: `README.md`
- Modify: `docs/project/overview.md`
- Modify: `docs/roadmap/next-stage.md`
- Modify: `docs/briefings/progress-briefing.md`
- Modify if required by current status: `docs/archive/codex-handoff-and-roadmap.md`

- [ ] **Step 1: Add provenance usage documentation**

Document the separated summary, manifest contents, and an example safe output
directory:

```bash
python scripts/prepare_demo.py --config config/demo.yaml \
  --output-dir outputs/runs/<run-name>
```

State explicitly that `--output-dir` does not redirect processed CSV files and
that a real preparation run can still overwrite `data/processed/*.csv.gz`.

- [ ] **Step 2: Run static and full-suite verification**

```bash
.venv/bin/python -m compileall src scripts tests
.venv/bin/python -m pytest -q
.venv/bin/python scripts/prepare_demo.py --help
```

Expected: compilation succeeds, all tests pass, and help lists `--output-dir`.

- [ ] **Step 3: Verify protected artifacts were untouched**

Compare the pre-implementation file inventory/metadata for existing files under
`data/processed/` and `outputs/`. Confirm no real preparation command was run and
inspect only filenames/metadata, never signal-window event content.

- [ ] **Step 4: Review the final diff**

Run targeted `git diff --no-index`/file inspection as needed because this parent
repository has no baseline commit. Confirm no physics feature or selection code was
changed beyond the cutflow schema constant.

- [ ] **Step 5: Request code review, fix actionable findings, and rerun verification**

Use `superpowers:requesting-code-review`, then rerun every command from Step 2.
Do not claim completion until `superpowers:verification-before-completion` checks
fresh command output.
