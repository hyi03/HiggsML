# Configurable Four-Lepton Selection and Cutflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make YAML-configured four-lepton selection affect every sample and emit a deterministic, per-sample cutflow with correct MC weighted yields and data counts.

**Architecture:** Extract reusable event normalization/reconstruction from feature building, evaluate named cuts through a typed `SelectionConfig`, and accumulate cutflow stages while iterating each sample. Keep the current feature list, labels, weights, and split behavior unchanged after selection.

**Tech Stack:** Python 3.12, NumPy, pandas, PyYAML, uproot, pytest/unittest-compatible tests.

## Global Constraints

- Scope is Roadmap Task 1 and Task 2 only; Task 3 summary/manifest is not implemented here.
- `m4l`, identifiers, sample metadata, truth, and weights must not enter `FEATURES`.
- Data keeps label `-1` and never enters supervised training.
- Signed `physical_weight` is used for MC yields; non-negative `train_weight` remains separate.
- Do not preprocess the real ROOT files, overwrite current processed data/outputs, retrain, or inspect the real-data 120–130 GeV window.
- Default Z2 mode is `fixed`; `sliding` remains a tested configuration option.
- The parent repository has no commits and the project is untracked; do not create commits or worktrees during this plan.

---

### Task 1: Shared four-lepton reconstruction

**Files:**
- Create: `src/reconstruction.py`
- Modify: `src/pairing.py`
- Modify: `src/features.py`
- Modify: `tests/test_pairing.py`
- Modify: `tests/test_features.py`

**Interfaces:**
- Produces: `NormalizedLeptons`, `FourLeptonCandidate`, `normalize_leptons()`, `reconstruct_candidate()`, `all_sfos_pair_masses()`, and `build_candidate_features()`.
- Preserves: `build_event_features(event, momentum_unit)` and the exact `FEATURES` list.

- [ ] **Step 1: Add failing pairing tests for every SFOS mass**

Add tests showing that `all_sfos_pair_masses()` returns both selected and alternative SFOS combinations in a `4e` event and returns an empty tuple when no SFOS pair exists.

```python
def test_all_sfos_pair_masses_include_alternative_pairs(self):
    leptons = [
        Lepton(at_rest(46), 1, 11),
        Lepton(at_rest(45), -1, 11),
        Lepton(at_rest(16), 1, 11),
        Lepton(at_rest(14), -1, 11),
    ]
    self.assertEqual(all_sfos_pair_masses(leptons), (91.0, 60.0, 61.0, 30.0))
```

- [ ] **Step 2: Run the focused pairing test and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_pairing.py -q
```

Expected: FAIL because `all_sfos_pair_masses` is not defined.

- [ ] **Step 3: Implement `all_sfos_pair_masses()`**

Iterate `combinations(range(len(leptons)), 2)`, retain pairs satisfying `is_sfos()`, and return masses in deterministic index order.

```python
def all_sfos_pair_masses(leptons: Sequence[Lepton]) -> tuple[float, ...]:
    return tuple(
        invariant_mass([leptons[first].vector, leptons[second].vector])
        for first, second in combinations(range(len(leptons)), 2)
        if is_sfos(leptons[first], leptons[second])
    )
```

- [ ] **Step 4: Add failing reconstruction and compatibility tests**

Test GeV/MeV normalization, stable descending pT sorting across every lepton field, deterministic Z1/Z2 reconstruction, all-SFOS masses, and equality between the legacy wrapper and candidate-based feature builder.

```python
normalized = normalize_leptons(event, "MeV")
candidate = reconstruct_candidate(normalized)
direct = build_candidate_features(event, candidate)
legacy = build_event_features(event, "MeV")
self.assertEqual(direct, legacy)
```

- [ ] **Step 5: Run reconstruction-related tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_pairing.py tests/test_features.py -q
```

Expected: FAIL because shared reconstruction interfaces do not exist.

- [ ] **Step 6: Implement shared reconstruction and refactor feature building**

Move unit conversion and aligned sorting into `normalize_leptons()`. Build immutable `FourLeptonCandidate` values once. Make `build_candidate_features()` compute the existing output fields from the candidate, and make `build_event_features()` a compatibility wrapper without applying selection.

- [ ] **Step 7: Run reconstruction regression tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_pairing.py tests/test_features.py -q
```

Expected: PASS, with `FEATURES` unchanged.

- [ ] **Step 8: Record a checkpoint without committing**

Run:

```bash
git status --short
```

Confirm only planned project files and previously known untracked parent files are present. Do not stage or commit.

### Task 2: Selection configuration and boundary semantics

**Files:**
- Create: `src/selection.py`
- Create: `tests/test_selection.py`

**Interfaces:**
- Consumes: `normalize_leptons()` and `reconstruct_candidate()` from Task 1.
- Produces: `SelectionConfig.from_mapping()`, `SelectionResult`, `z2_min_mass_gev()`, and `select_event()`.

- [ ] **Step 1: Add failing configuration tests**

Create a valid mapping fixture matching `docs/physics/selection-standard.md`. Test parsing and explicit failures for missing fields, a non-descending pT list, invalid windows, `require_exactly_four_leptons: false`, unsupported flavours, and unsupported Z2 modes.

```python
def test_parses_fixed_and_sliding_z2_modes():
    fixed = SelectionConfig.from_mapping(selection_mapping("fixed"))
    sliding = SelectionConfig.from_mapping(selection_mapping("sliding"))
    assert fixed.z2_min_mode == "fixed"
    assert sliding.z2_min_mode == "sliding"
```

- [ ] **Step 2: Add failing sliding-threshold tests**

Assert the configured function gives `12.0` at 125 and 140 GeV, `19.6` at 150 GeV, and `50.0` at and above 190 GeV. Assert continuity immediately around 140 and 190 within floating-point tolerance.

- [ ] **Step 3: Run configuration tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_selection.py -q
```

Expected: FAIL because `src.selection` does not exist.

- [ ] **Step 4: Implement typed configuration parsing and Z2 strategies**

Implement frozen dataclasses, finite/non-negative numeric checks, ordered-window checks, and interpolation derived from configured endpoints:

```python
slope = (
    config.z2_sliding.high_min_gev - config.z2_sliding.low_min_gev
) / (
    config.z2_sliding.high_m4l_gev - config.z2_sliding.low_m4l_gev
)
```

- [ ] **Step 5: Run configuration tests and verify pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_selection.py -q
```

Expected: configuration and Z2 threshold tests PASS; event-selection tests have not yet been added.

- [ ] **Step 6: Add failing staged event-selection tests**

Use synthetic raw-event dictionaries and small helpers that vary one property at a time. Cover every stage and each required boundary:

```python
result = select_event(event, config, "GeV")
assert not result.accepted
assert result.failed_stage == "lepton_pt"
assert result.passed_stages == (
    "exactly_four_leptons",
    "allowed_lepton_types",
)
```

For mass-window boundaries, construct back-to-back massless leptons at `eta=0`, where a pair with equal pT has invariant mass `2*pT`; avoid approximate fixtures whose expected failure stage is ambiguous.

- [ ] **Step 7: Run staged selection tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_selection.py -q
```

Expected: FAIL because `select_event()` has not been implemented.

- [ ] **Step 8: Implement `select_event()` with exact stage attribution**

Evaluate stages in `SELECTION_STAGES` order. Return immediately at the first failure. Only attach a candidate when valid pairing exists; append `selected` only after all mass cuts pass.

- [ ] **Step 9: Run selection tests and regressions**

Run:

```bash
.venv/bin/python -m pytest tests/test_selection.py tests/test_pairing.py tests/test_features.py -q
```

Expected: PASS.

### Task 3: Cutflow accumulation

**Files:**
- Modify: `src/selection.py`
- Modify: `src/weights.py`
- Create: `tests/test_cutflow.py`
- Modify: `tests/test_weights.py`

**Interfaces:**
- Consumes: `SelectionResult` and ordered `SELECTION_STAGES` from Task 2.
- Produces: `CutflowAccumulator`, `physical_event_weight()`, and JSON-ready stage dictionaries.

- [ ] **Step 1: Add failing scalar physical-weight test**

```python
def test_scalar_physical_event_weight_matches_vector_formula(self):
    event = {
        "mcWeight": -0.5,
        "xsec": 2.0,
        "kfac": 1.2,
        "filteff": 0.5,
        "sum_of_weights": 100.0,
    }
    self.assertAlmostEqual(physical_event_weight(event, 1000.0), -6.0)
```

- [ ] **Step 2: Add failing cutflow accumulator tests**

Record one positive MC event, one negative MC event, and data events with different `SelectionResult` failures. Verify counts, monotonicity, efficiencies, signed yields, absolute yields, and omission of weighted fields for data.

- [ ] **Step 3: Run cutflow tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_cutflow.py tests/test_weights.py -q
```

Expected: FAIL because the scalar weight and accumulator do not exist.

- [ ] **Step 4: Implement the scalar weight wrapper**

Delegate to `physical_event_weights()` using scalar event fields and convert the returned zero-dimensional NumPy value to `float`.

- [ ] **Step 5: Implement `CutflowAccumulator`**

Required API:

```python
class CutflowAccumulator:
    def __init__(self, *, sample_name: str, is_data: bool): ...
    def record_read(self, physical_weight: float | None = None) -> None: ...
    def record_selection(
        self,
        result: SelectionResult,
        physical_weight: float | None = None,
    ) -> None: ...
    def to_dict(self) -> dict[str, Any]: ...
```

Require `None` weights for data and finite numeric weights for MC. `record_selection()` increments only the ordered `passed_stages` and validates that the result cannot skip or reorder stages.

- [ ] **Step 6: Run cutflow and weight tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_cutflow.py tests/test_weights.py -q
```

Expected: PASS.

### Task 4: Pipeline and CLI integration

**Files:**
- Modify: `src/pipeline.py`
- Modify: `scripts/prepare_demo.py`
- Modify: `config/demo.yaml`
- Modify: `tests/test_cutflow.py`

**Interfaces:**
- Consumes: `SelectionConfig`, `select_event()`, `CutflowAccumulator`, `physical_event_weight()`, and `build_candidate_features()`.
- Produces: `PreparedSample(frame, cutflow)` and `outputs/cutflow.json` when the CLI is intentionally run.

- [ ] **Step 1: Add failing pipeline integration test with a mocked iterator**

Monkeypatch `src.pipeline.iter_events` to return synthetic MC events that pass and fail different cuts. Assert:

```python
prepared = prepare_sample(...)
assert len(prepared.frame) == prepared.cutflow["stages"]["selected"]["count"]
assert set(prepared.frame["split"]) <= {"train", "validation", "test"}
assert (prepared.frame["label"] == 1).all()
```

Add an equivalent data test asserting label `-1`, split `data`, and no cutflow weighted-yield keys.

- [ ] **Step 2: Run pipeline integration tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_cutflow.py -q
```

Expected: FAIL because `prepare_sample()` still returns only a DataFrame and does not apply selection.

- [ ] **Step 3: Implement `PreparedSample` and integrate selection**

Calculate each MC event's physical weight once before selection, record cutflow, construct features only for selected candidates, then preserve the existing label, training-weight, and hash-split behavior.

- [ ] **Step 4: Expand `config/demo.yaml`**

Replace the incomplete selection block with the exact fixed-default configuration approved in `docs/physics/selection-standard.md`, including the dormant `sliding` values.

- [ ] **Step 5: Update the preparation CLI**

Parse `SelectionConfig` before opening ROOT files, pass stable sample names, combine frames through `.frame`, and write cutflow JSON with schema version `1.0`.

Implement a pure writer function that accepts a destination path so tests can use `tmp_path`; do not invoke `main()` against real data.

- [ ] **Step 6: Add deterministic JSON writer test**

Write cutflow twice to separate temporary files and assert byte-for-byte equality, trailing newline, stable stage order, separate sample keys, and no weighted fields for data.

- [ ] **Step 7: Run Task 1–2 focused acceptance tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_selection.py tests/test_cutflow.py tests/test_pairing.py tests/test_features.py tests/test_weights.py -q
```

Expected: PASS.

### Task 5: Full regression and documentation status

**Files:**
- Modify: `docs/physics/selection-standard.md`
- Modify: `README.md`
- Modify: `docs/project/overview.md`
- Modify: `docs/roadmap/next-stage.md`
- Modify: `docs/briefings/progress-briefing.md`
- Modify: `docs/archive/codex-handoff-and-roadmap.md`

**Interfaces:**
- Consumes: verified test output from Tasks 1–4.
- Produces: documentation that distinguishes implemented/tested logic from unrerun real-data outputs.

- [ ] **Step 1: Run the complete test suite**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: all tests PASS. Record the actual count; do not assume the historical count of 23.

- [ ] **Step 2: Check code for feature leakage and accidental signal-window access**

Run:

```bash
rg -n 'FEATURES|m4l|120|130|data_with_xgb_score' src scripts tests
```

Inspect matches and confirm `m4l` remains analysis-only and no real-data signal-window read was introduced.

- [ ] **Step 3: Update documentation with verified status**

State that selection and cutflow logic are implemented and unit/integration tested, but real ROOT preprocessing has not been rerun and historical event counts/outputs remain pre-selection artifacts. Do not claim a new physical baseline.

- [ ] **Step 4: Run the complete test suite again after documentation/code-adjacent edits**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: all tests PASS with the same actual test count as Step 1.

- [ ] **Step 5: Review the final workspace diff without staging**

Run:

```bash
git status --short
git diff --no-index /dev/null docs/physics/selection-standard.md
```

Because the project is untracked in a no-history parent repository, also list changed project files explicitly in the handoff. Do not stage, commit, preprocess real ROOT, or overwrite outputs.
