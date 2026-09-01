# Full ROOT Preprocessing Baseline Design

Date: 2026-08-10

## 1. Goal

Create the first safe, auditable preprocessing baseline that reads every event in
the three configured ROOT files, applies the implemented four-lepton selection,
and writes new processed tables and provenance artifacts without overwriting the
historical demo outputs.

This is Task 4A. It establishes the canonical full-input dataset and verifies MC
normalization metadata. It does not retrain XGBoost or decide how the highly
imbalanced Higgs and ZZ event counts should be presented to the classifier.

## 2. Scope and scientific boundary

Task 4A includes:

- full reads of Higgs DSID 345060, ZZ DSID 700600, and data16 period A;
- chunked ROOT I/O to keep peak input-array memory bounded;
- the existing selection, reconstruction, feature, split, and physical-weight
  behavior;
- a new isolated run directory containing processed CSV files, cutflow, separated
  data/MC summary, configuration snapshot, and run manifest;
- consistency checks and manifest reporting for MC normalization parameters;
- an actual full preprocessing run after synthetic/unit tests pass.

Task 4A excludes:

- XGBoost training, threshold selection, inference, or plot regeneration;
- training-class balancing or class-weight policy;
- deterministic hash-fraction sampling and sampling corrections;
- adding data periods or MC processes;
- trigger, identification, isolation, or impact-parameter selection;
- inspecting the real-data 120--130 GeV mass interval or any event-level signal
  candidates.

The next independent design cycle will use the full MC tables to define training
balance without modifying signed `physical_weight` used for physical yields.

## 3. Chosen approach

The implementation uses an explicit safe full-run override rather than changing
the current smoke-test configuration permanently:

```bash
python -m scripts.prepare_demo \
  --config config/demo.yaml \
  --full \
  --run-dir runs/full-baseline-2026-08-10
```

`config/demo.yaml` retains `entry_stop: 5000` for quick development runs. `--full`
sets the effective `entry_stop` to `null` for this invocation. The manifest records
the effective policy, so the configuration hash and CLI override remain
distinguishable.

Full mode always requires a new `--run-dir`. It can never use the legacy
`data/processed/` and `outputs/` destinations.

## 4. Run-directory contract

The approved output layout is:

```text
runs/full-baseline-2026-08-10/
├── config.yaml
├── processed/
│   ├── mc_events.csv.gz
│   └── data_events.csv.gz
└── artifacts/
    ├── cutflow.json
    ├── data_summary.json
    └── run_manifest.json
```

Rules:

- `--run-dir` must not already exist; no existing run is overwritten.
- The config snapshot contains the exact bytes read from `--config`.
- All three samples are prepared successfully before the run directory is created.
- `run_manifest.json` is written last. A run directory without it is incomplete.
- A write failure may leave an incomplete new run directory; the program reports
  the failure and does not automatically delete user-visible partial output.
- `runs/*` is ignored by Git, while `runs/.gitkeep` preserves the directory shape.

Legacy behavior remains available for small development runs when `--run-dir` is
not supplied. Supplying both an explicit legacy `--output-dir` and `--run-dir` is
an error.

## 5. Effective read policy

The preparation script resolves this JSON-ready policy before reading samples:

```json
{
  "mode": "full",
  "entry_stop": null,
  "chunk_size_events": 50000
}
```

Resolution rules:

1. `--full` always produces `mode: full` and `entry_stop: null`.
2. Without `--full`, a positive configured `entry_stop` produces `mode: head`.
3. A configured `entry_stop: null` also produces `mode: full` and therefore
   requires `--run-dir`.
4. Boolean, zero, negative, fractional, or otherwise invalid `entry_stop` values
   fail before ROOT I/O.
5. `chunk_size_events` comes from the config, defaults to `50000`, and must be a
   positive integer rather than a boolean.

`config/demo.yaml` gains `chunk_size_events: 50000`; its existing
`entry_stop: 5000` stays unchanged.

## 6. Chunked ROOT I/O

`src.io.iter_events()` retains its event-dictionary interface and adds
`chunk_size_events`:

```python
def iter_events(
    path: str | Path,
    tree_name: str | None = None,
    *,
    is_data: bool,
    entry_stop: int | None = None,
    chunk_size_events: int = 50_000,
) -> Iterable[dict[str, Any]]:
    ...
```

Instead of `tree.arrays(...)`, it uses `tree.iterate(...)` with an integer
`step_size`. Each chunk is converted to event dictionaries in order before the
next chunk is read.

Required properties:

- output event order is identical to a single-array read;
- no event is duplicated or dropped at chunk boundaries;
- `entry_stop` applies to the whole tree, not separately to each chunk;
- required-branch and tree-discovery errors retain their existing behavior;
- MC normalization branches are all required for MC rather than requested only
  when present;
- data never requires MC-only branches.

The selected rows are still accumulated into one DataFrame because the complete
processed table is the intended output. Chunking bounds ROOT input-array memory;
it does not claim to make the final selected DataFrame constant-memory.

## 7. MC normalization metadata

`src.weights` gains an immutable `MCNormalization` value containing:

```text
xsec_pb
k_factor
filter_efficiency
sum_of_weights
```

The first read MC event establishes the sample metadata. Every later event must
match it within `rtol=1e-12` and `atol=0.0` after conversion to `float`.

Validation rules:

- all four values are finite;
- `xsec_pb` is non-negative;
- `k_factor` is strictly positive;
- `filter_efficiency` is in the closed interval `[0, 1]`;
- `sum_of_weights` is non-zero;
- an MC sample must read at least one event before metadata can be reported.

`mcWeight` remains event-specific and is not part of this consistency object.
Negative `mcWeight` values remain valid and signed.

`PreparedSample` gains:

```python
normalization: MCNormalization | None
```

It is `None` for data. For MC, the same validated object is used by the physical
weight calculation and passed to manifest construction. This prevents summary
metadata and event weights from relying on different values.

For each MC sample the manifest reports:

```json
{
  "dsids": [345060],
  "luminosity_pb": 10000.0,
  "xsec_pb": 28.3,
  "k_factor": 1.717,
  "filter_efficiency": 0.000124,
  "sum_of_weights": 45231012.0,
  "effective_cross_section_pb": 0.006025...
}
```

Numbers above illustrate the schema; the real artifact must use values read and
validated from the ROOT files.

## 8. Pipeline and CLI integration

`prepare_sample()` adds `chunk_size_events`, validates MC normalization while
iterating, and returns it through `PreparedSample`. Selection, features, labels,
physical weights, training-weight construction, and deterministic split assignment
remain otherwise unchanged.

`scripts.prepare_demo` adds:

```text
--full
--run-dir PATH
```

It changes `--output-dir` to an optional legacy destination so explicit use can be
detected and rejected when `--run-dir` is present.

The script prints a completion line after Higgs, ZZ, and data preparation so a
long full run has observable sample-level progress. It builds and validates the
summary and manifest payloads before creating output directories.

The run-directory writer then:

1. creates `processed/` and `artifacts/`;
2. copies the exact config bytes to `config.yaml`;
3. writes both compressed CSV files;
4. writes cutflow and data summary;
5. writes the manifest last.

## 9. Manifest 1.1

`MANIFEST_SCHEMA_VERSION` increases from `1.0` to `1.1`. Summary and cutflow remain
at `1.0` because their schemas do not change.

The manifest retains software, input hashes, UTC timestamp, Git state, and output
schema versions. It adds or expands:

```json
{
  "config": {
    "path": "config/demo.yaml",
    "snapshot_path": "runs/full-baseline-2026-08-10/config.yaml",
    "sha256": "..."
  },
  "processing": {
    "read_policy": {
      "mode": "full",
      "entry_stop": null,
      "chunk_size_events": 50000
    },
    "random_seed": 42,
    "tree_name": "analysis",
    "momentum_unit": "GeV",
    "selection": {"z2_min_mode": "fixed"}
  },
  "mc_normalization": {
    "higgs_345060": {},
    "zz_700600": {}
  },
  "outputs": {
    "locations": {
      "run_dir": "runs/full-baseline-2026-08-10",
      "processed_dir": "runs/full-baseline-2026-08-10/processed",
      "artifacts_dir": "runs/full-baseline-2026-08-10/artifacts"
    },
    "cutflow_schema_version": "1.0",
    "data_summary_schema_version": "1.0",
    "run_manifest_schema_version": "1.1"
  }
}
```

The source config and copied snapshot must have identical SHA-256 values.

## 10. Error handling

The program fails before ROOT I/O or output creation for:

- full effective read mode without `--run-dir`;
- an existing `--run-dir`;
- simultaneous `--run-dir` and explicit `--output-dir`;
- invalid `entry_stop` or `chunk_size_events`;
- a `--run-dir` that resolves to a protected input, legacy processed, legacy
  output, source, test, or virtual-environment directory.

It fails during preparation for:

- missing MC normalization branches;
- invalid or inconsistent MC normalization values;
- unexpected DSIDs;
- malformed events or no selected events, using existing behavior.

It fails before output writes when:

- cutflow selected counts disagree with DataFrame lengths;
- summary or manifest validation fails;
- the source config changes between initial read and snapshot construction.

## 11. Testing strategy

All implementation tests use fake trees, synthetic event dictionaries, temporary
files, and temporary run directories. They do not read the real ROOT files.

New and updated tests cover:

- two or more ROOT chunks preserving event order;
- a global `entry_stop` crossing a chunk boundary;
- invalid chunk sizes and missing branches;
- valid MC normalization parsing and effective cross section;
- every invalid normalization boundary and within-file inconsistency;
- data returning no normalization metadata;
- `PreparedSample` returning validated MC metadata without changing existing
  features, weights, split, or cutflow;
- full/head read-policy resolution;
- full mode requiring a fresh run directory;
- run-directory and legacy-output mutual exclusion;
- exact config snapshot bytes and hashes;
- isolated processed/artifact paths;
- manifest 1.1 shape, normalization, read policy, and output locations;
- failure before output creation for all preflight validation errors;
- full existing-suite regression.

## 12. Real full-run procedure and acceptance

After code verification, record path/size/mtime metadata for all pre-existing files
under `data/raw`, `data/processed`, and `outputs`. Then run:

```bash
.venv/bin/python -m scripts.prepare_demo \
  --config config/demo.yaml \
  --full \
  --run-dir runs/full-baseline-2026-08-10
```

Only aggregate artifacts are inspected. Acceptance requires:

1. `read` counts equal the ROOT tree entry counts recorded in project data
   documentation: Higgs `419943`, ZZ `11260`, and data `29275`;
2. MC and data selected counts equal their processed CSV row counts;
3. data run/event uniqueness is reported and duplicate count is zero unless a
   documented source-data issue is found;
4. both MC samples report finite signed/absolute yields, negative-weight counts,
   and validated normalization parameters;
5. manifest source/snapshot config hashes match and all three ROOT hashes match the
   documented inputs;
6. all artifacts use the expected schema versions and paths;
7. pre-existing ROOT, legacy processed, and legacy output metadata is unchanged;
8. no model, metric, plot, or scored-data artifact is created in the new run;
9. no event-level real-data mass or score values are inspected.

If the full run fails, report the sample and stage reached, retain any incomplete
new run directory for diagnosis, and do not fall back silently to prefix sampling.

## 13. Documentation updates

After verified implementation and the real full run:

- update `README.md` with full-run and smoke-run commands;
- update `docs/project/overview.md` with the run-directory contract and verified
  aggregate counts;
- update `docs/roadmap/next-stage.md` to mark Task 4A complete and identify
  training balance as Task 4B;
- update `AGENTS.md` with the new verified baseline and immutable safety rules;
- retain historical metrics and explicitly label them as belonging to the old
  5,000-entry model until retraining is completed.

No historical model-performance number is replaced by full-preprocessing counts.
