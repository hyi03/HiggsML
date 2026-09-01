# Task 3: Data Summary and Run Manifest Design

Date: 2026-08-05

## 1. Goal

Task 3 makes preprocessing results auditable without changing event selection,
training, or physics features.

It will:

1. replace the current mixed data/MC summary with separate data and MC sections;
2. create a run manifest that records the exact configuration, inputs, software,
   and processing controls used for a preprocessing run;
3. validate the summary against the selected frames and cutflow before writing;
4. keep all tests synthetic so the existing ROOT files, processed CSV files, and
   current `outputs/` artifacts are not overwritten during implementation.

## 2. Non-goals

Task 3 will not:

- change the selection thresholds or pairing logic;
- change `entry_stop` or increase the sample size;
- train or evaluate a model;
- inspect or unblind the real-data 120--130 GeV signal window;
- automatically execute `scripts/prepare_demo.py` on the real ROOT files;
- introduce automatic timestamped run directories. The script will accept an
  output directory, but choosing a new directory for a real run remains explicit.

## 3. Ownership and interfaces

A new module, `src/provenance.py`, will own summary and manifest construction.
This keeps provenance logic out of the physics pipeline.

The module will provide:

- schema-version constants for the summary and manifest;
- a small immutable input record describing each prepared sample;
- pure builders for the summary and manifest dictionaries;
- SHA-256 file hashing;
- software-version collection;
- git-commit discovery with a safe `unavailable` result;
- stable UTF-8 JSON writing with two-space indentation and a trailing newline.

`src.pipeline.write_summary` will be removed after the script is migrated to the
new module. `write_cutflow` remains in the pipeline for this task.

`scripts/prepare_demo.py` will gain:

```text
--output-dir PATH
```

Its default remains `outputs` for backward compatibility. Tests will always use a
temporary directory. A future real run can use a unique directory deliberately.
This option governs `cutflow.json`, `data_summary.json`, and
`run_manifest.json`; it does not change the current processed-CSV destination.

## 4. `data_summary.json` schema

The file uses schema version `1.0` and has no combined event or weight totals:

```json
{
  "schema_version": "1.0",
  "data": {
    "data16_periodA": {
      "period": "A",
      "read_events": 5000,
      "selected_events": 1112,
      "unique_run_event_pairs": 1112,
      "duplicate_run_event_pairs": 0
    }
  },
  "mc": {
    "higgs_345060": {
      "dsids": [345060],
      "label": 1,
      "read_events": 5000,
      "selected_events": 4884,
      "signed_sum_physical_weights": 0.0,
      "absolute_sum_physical_weights": 0.0,
      "negative_weight_events": 0,
      "negative_weight_fraction": 0.0
    }
  }
}
```

The numeric values above illustrate the shape only; implementation does not copy
or assume those values.

### 4.1 Data rules

- Data is grouped by configured sample name and records its period.
- `read_events` comes from the cutflow `read` stage.
- `selected_events` is both the selected-stage count and frame length; disagreement
  is an error.
- uniqueness is defined by the pair `(runNumber, eventNumber)` in the selected
  frame.
- `duplicate_run_event_pairs = selected_events - unique_run_event_pairs`.
- Data entries never contain physical-weight sums, negative-weight counts, labels,
  or DSIDs.

### 4.2 MC rules

- MC is grouped by configured sample name.
- `dsids` is the sorted list of expected channel numbers for that sample.
- `read_events` comes from the cutflow `read` stage.
- `selected_events` is checked against both the selected-stage count and frame
  length.
- weight statistics use selected events' `physical_weight`, never
  `train_weight` and never data unit weights.
- signed and absolute sums are accumulated separately.
- `negative_weight_fraction` uses selected MC events as its denominator and is
  `0.0` for an empty selected sample.

## 5. `run_manifest.json` schema

The file uses schema version `1.0`:

```json
{
  "schema_version": "1.0",
  "created_at_utc": "2026-08-05T17:30:00Z",
  "software": {
    "python": "3.x.x",
    "numpy": "...",
    "pandas": "...",
    "pyyaml": "...",
    "uproot": "...",
    "xgboost": "...",
    "scikit-learn": "..."
  },
  "config": {
    "path": "config/demo.yaml",
    "sha256": "..."
  },
  "inputs": {
    "higgs_345060": {
      "path": "data/raw/MC/mc_345060.root",
      "size_bytes": 123,
      "sha256": "..."
    }
  },
  "processing": {
    "tree_name": "mini",
    "momentum_unit": "MeV",
    "entry_stop": 5000,
    "random_seed": 42,
    "selection": {
      "z2_min_mode": "fixed"
    }
  },
  "git": {
    "commit": "unavailable"
  },
  "outputs": {
    "cutflow_schema_version": "1.0",
    "data_summary_schema_version": "1.0",
    "run_manifest_schema_version": "1.0"
  }
}
```

### 5.1 Manifest rules

- `created_at_utc` is an ISO-8601 UTC timestamp ending in `Z`.
- the config hash covers the exact bytes of the YAML file used by the script.
- each configured ROOT input records its path, byte size, and SHA-256 hash.
- SHA-256 is calculated by streaming chunks instead of loading a whole ROOT file
  into memory.
- `entry_stop` is recorded as an integer or JSON `null` when no limit is used.
- the current git commit is recorded only when `git rev-parse HEAD` succeeds; a
  repository without commits records `"unavailable"` explicitly.
- timestamps and environment versions are injectable into pure builders so tests
  are deterministic.

## 6. Validation and errors

Construction fails with a clear exception when:

- a data frame lacks `runNumber` or `eventNumber`;
- an MC frame lacks `physical_weight` or the configured/observed DSID disagrees;
- a physical weight is not finite;
- the selected cutflow count disagrees with the selected frame length;
- a required config or input file does not exist;
- a sample kind is neither `data` nor `mc`.

No partially valid summary should be silently written.

## 7. Script flow

After all three samples are prepared, `scripts/prepare_demo.py` will:

1. retain the prepared frames and cutflows with their sample metadata;
2. write the existing processed CSV files as it does today;
3. create the selected output directory;
4. write `cutflow.json`;
5. validate and write the separated `data_summary.json`;
6. hash the exact YAML and three configured ROOT files and write
   `run_manifest.json`.

Manifest creation occurs only when the preparation script itself is run. Unit and
integration tests use temporary dummy files and never hash or open the real ROOT
inputs.

## 8. Test strategy

New tests will cover:

- data and MC appearing in separate top-level sections;
- absence of the old combined `rows`, `labels`, and `weight_summary` fields;
- data run/event uniqueness and duplicate counts;
- MC signed sums, absolute sums, negative counts, and negative fractions;
- empty selected MC handling;
- cutflow/frame mismatches and missing required columns;
- configured versus observed DSID validation;
- exact SHA-256 and file-size reporting on temporary files;
- fixed UTC timestamp and software-version serialization;
- both a real git SHA result and the no-commit `unavailable` fallback;
- stable JSON bytes for fixed inputs;
- CLI wiring to a temporary `--output-dir` without executing real ROOT reads.

The full existing test suite will then be run to prove Task 3 did not change Task
1--2 selection and cutflow behavior.

## 9. Acceptance criteria

Task 3 is complete when:

- `data_summary.json` can no longer mix data unit weights with MC physical weights;
- every required data and MC field is tested;
- `run_manifest.json` records the config and all three input hashes, run controls,
  software versions, UTC time, git state, and schema versions;
- `scripts/prepare_demo.py --help` exposes `--output-dir`;
- all tests pass;
- no real ROOT file, processed CSV, or existing output artifact was modified during
  implementation and verification.
