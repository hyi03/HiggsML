# Configurable Four-Lepton Selection and Cutflow Design

**Date:** 2026-08-05  
**Status:** Proposed for implementation after user review  
**Scope:** Roadmap Task 1 and Task 2 only

## 1. Goal

Make the `selection` section of `config/demo.yaml` control which Higgs MC, continuum ZZ MC, and real-data events are retained, and produce a deterministic per-sample cutflow that explains every selection loss.

This change must preserve the current scientific boundaries:

- data keeps label `-1` and is never used for supervised training;
- `m4l`, identifiers, sample metadata, truth, and weights never enter model `FEATURES`;
- signed physical weights are used only for MC physical yields;
- non-negative training weights remain separate;
- no real-data 120–130 GeV signal-window inspection occurs during implementation;
- no existing processed data, model, plot, or output is overwritten during unit-test implementation.

Task 3 summary/manifest changes, full-file processing, sampling correction, retraining, and real-data evaluation are explicitly out of scope.

## 2. Selected approach

Use a staged, single-event selection pipeline with a structured result.

Alternatives considered:

1. **Selected: shared reconstruction plus staged selection.** Normalize and reconstruct the event once, evaluate named cuts in order, and pass the accepted reconstruction to feature building. This gives exact failure reasons without duplicating four-vector calculations.
2. **Rejected: wrap the current `build_event_features()` with external cuts.** This would repeat calculations and cannot reliably distinguish invalid SFOS pairing from non-finite kinematics.
3. **Rejected: vectorize the whole pipeline in pandas/awkward.** This would broaden the task into an I/O and data-model rewrite before full-file processing is designed.

## 3. File responsibilities

### New: `src/reconstruction.py`

Own the conversion from raw event arrays to reusable four-lepton kinematics.

Public interfaces:

```python
@dataclass(frozen=True)
class NormalizedLeptons:
    pt: np.ndarray
    eta: np.ndarray
    phi: np.ndarray
    energy: np.ndarray
    charge: np.ndarray
    flavour: np.ndarray

@dataclass(frozen=True)
class FourLeptonCandidate:
    normalized: NormalizedLeptons
    leptons: tuple[Lepton, Lepton, Lepton, Lepton]
    pairing: PairingResult
    z1: FourVector
    z2: FourVector
    four_lepton: FourVector
    all_sfos_masses: tuple[float, ...]

def normalize_leptons(
    event: Mapping[str, Any], momentum_unit: str
) -> NormalizedLeptons:
    """Convert momentum fields to GeV and sort all lepton fields by descending pT."""

def reconstruct_candidate(
    normalized: NormalizedLeptons,
) -> FourLeptonCandidate | None:
    """Return the deterministic two-SFOS candidate, or None if no valid pairing exists."""
```

`select_event()` checks array presence and lengths before calling `normalize_leptons()`. The normalization function converts structurally valid arrays to the requested unit, keeps all lepton fields aligned during the stable pT sort, and rejects unsupported units. Finite-value checks are attributed to the earliest cut that consumes the affected quantity, so they remain visible in cutflow rather than becoming an unclassified reconstruction failure.

`reconstruct_candidate()` uses `src.pairing.pair_four_leptons()` for the existing Z1/Z2 rule and computes all possible SFOS masses for the low-mass veto.

### Modified: `src/pairing.py`

Keep the existing deterministic two-SFOS partition logic. Add only a focused helper:

```python
def all_sfos_pair_masses(leptons: Sequence[Lepton]) -> tuple[float, ...]:
    """Return invariant masses for every SFOS pair among the supplied leptons."""
```

This helper includes alternative pairings in `4e` and `4mu` events, not only the selected Z1 and Z2.

### New: `src/selection.py`

Own configuration parsing, boundary semantics, ordered cut evaluation, and cutflow accumulation.

Public interfaces:

```python
SELECTION_STAGES: tuple[str, ...]

@dataclass(frozen=True)
class SlidingZ2Config:
    low_m4l_gev: float
    high_m4l_gev: float
    low_min_gev: float
    high_min_gev: float

@dataclass(frozen=True)
class SelectionConfig:
    require_exactly_four_leptons: bool
    allowed_lepton_types: tuple[int, ...]
    lepton_pt_thresholds_gev: tuple[float, float, float, float]
    electron_max_abs_eta: float
    muon_max_abs_eta: float
    require_zero_charge: bool
    min_all_sfos_mass_gev: float
    z1_mass_window_gev: tuple[float, float]
    z2_min_mode: Literal["fixed", "sliding"]
    z2_fixed_min_gev: float
    z2_max_gev: float
    z2_sliding: SlidingZ2Config
    m4l_window_gev: tuple[float, float]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SelectionConfig": ...

@dataclass(frozen=True)
class SelectionResult:
    accepted: bool
    passed_stages: tuple[str, ...]
    failed_stage: str | None
    candidate: FourLeptonCandidate | None

def z2_min_mass_gev(m4l: float, config: SelectionConfig) -> float: ...

def select_event(
    event: Mapping[str, Any],
    config: SelectionConfig,
    momentum_unit: str,
) -> SelectionResult: ...
```

Configuration validation rejects:

- missing required fields;
- `require_exactly_four_leptons: false`, because selecting a quadruplet from events with more than four leptons is outside this design;
- non-finite or negative thresholds;
- a pT threshold list that does not contain exactly four descending values;
- windows whose lower bound is not below the upper bound;
- unsupported `z2_mass.min_mode` values;
- sliding break points or sliding lower limits that decrease;
- allowed lepton types other than absolute PDG identifiers `11` and `13`.

The dynamic Z2 lower limit is:

\[
m_{Z2}^{\min}(m_{4\ell})=
\begin{cases}
12, & m_{4\ell}\le140,\\
12+0.76(m_{4\ell}-140), & 140<m_{4\ell}<190,\\
50, & m_{4\ell}\ge190.
\end{cases}
\]

The values are derived from the configured break points and endpoint minima rather than hard-coding `0.76`.

### Modified: `src/features.py`

Preserve `FEATURES`, `FORBIDDEN_FEATURES`, and `assert_no_feature_leakage()`.

Add:

```python
def build_candidate_features(
    event: Mapping[str, Any], candidate: FourLeptonCandidate
) -> dict[str, Any]: ...
```

Keep `build_event_features(event, momentum_unit)` as a compatibility wrapper for existing tests and callers. It normalizes and reconstructs an event using the shared reconstruction module, then delegates to `build_candidate_features()`. It does not apply the new analysis selection; only `select_event()` does.

### Modified: `src/pipeline.py`

Return the selected frame and its cutflow explicitly:

```python
@dataclass(frozen=True)
class PreparedSample:
    frame: pd.DataFrame
    cutflow: dict[str, Any]

def prepare_sample(
    path,
    *,
    sample_name: str,
    selection: SelectionConfig,
    tree_name,
    momentum_unit,
    is_data,
    label=None,
    expected_channels=(),
    luminosity_pb=10000.0,
    entry_stop=None,
) -> PreparedSample: ...
```

For each raw event:

1. calculate its MC physical weight once when applicable;
2. increment `read`;
3. call `select_event()`;
4. increment every stage in `passed_stages`;
5. build a feature row only for accepted events;
6. apply label, physical weight, training weight, and split exactly as before.

If no event is selected, `prepare_sample()` raises a message containing the sample name and final cutflow instead of returning an ambiguous empty frame.

### Modified: `src/weights.py`

Add a scalar wrapper used by cutflow:

```python
def physical_event_weight(
    event: Mapping[str, Any], luminosity_pb: float
) -> float: ...
```

It uses the same formula and validation as `physical_event_weights()`. It does not modify `training_weights()` semantics.

### Modified: `scripts/prepare_demo.py`

- parse `SelectionConfig` once;
- pass the same selection object to Higgs, ZZ, and data;
- provide stable sample names: `higgs_345060`, `zz_700600`, and `data16_periodA`;
- adapt to `PreparedSample.frame`;
- combine per-sample cutflows and write `outputs/cutflow.json`;
- continue writing processed CSV files and the existing summary format until Task 3 replaces it.

The implementation and tests must not invoke this script on the real ROOT files, because doing so would overwrite existing processed data and outputs.

## 4. Selection order and boundary semantics

The exact ordered stages are:

```text
read
exactly_four_leptons
allowed_lepton_types
lepton_pt
lepton_eta
zero_charge
valid_sfos_pairing
all_sfos_mass
z1_mass_window
z2_mass_window
m4l_analysis_window
selected
```

Rules:

| Stage | Passing condition |
|---|---|
| `exactly_four_leptons` | `lep_n == 4` and all six lepton arrays have length 4 |
| `allowed_lepton_types` | every `abs(lep_type)` is configured, initially 11 or 13 |
| `lepton_pt` | sorted pT values are component-wise greater than or equal to `[20, 15, 10, 7]` GeV |
| `lepton_eta` | electrons have `abs(eta) < 2.47`; muons have `abs(eta) < 2.7` |
| `zero_charge` | charge sum equals zero |
| `valid_sfos_pairing` | two non-overlapping SFOS pairs exist |
| `all_sfos_mass` | every possible SFOS mass is strictly above 5 GeV |
| `z1_mass_window` | `50 < mZ1 < 106` GeV |
| `z2_mass_window` | configured lower limit `< mZ2 < 115` GeV |
| `m4l_analysis_window` | `105 <= m4l < 160` GeV |
| `selected` | all preceding stages passed |

The charge stage is retained even though two valid SFOS pairs imply zero total charge, because its separate count is diagnostically useful.

## 5. Cutflow schema

`outputs/cutflow.json` has schema version `1.0`:

```json
{
  "schema_version": "1.0",
  "selection": {
    "z2_min_mode": "fixed"
  },
  "samples": {
    "higgs_345060": {
      "kind": "mc",
      "stages": {
        "read": {
          "count": 5000,
          "efficiency_previous": 1.0,
          "efficiency_read": 1.0,
          "signed_weighted_yield": 0.0,
          "absolute_weighted_yield": 0.0
        }
      }
    },
    "data16_periodA": {
      "kind": "data",
      "stages": {
        "read": {
          "count": 5000,
          "efficiency_previous": 1.0,
          "efficiency_read": 1.0
        }
      }
    }
  }
}
```

The numeric values above illustrate the schema only; they are not expected results.

For each stage:

- `count` is an integer and cannot increase;
- `efficiency_previous` is `count / previous_count`, or `0.0` if the previous count is zero;
- `efficiency_read` is `count / read_count`, or `0.0` if `read_count` is zero;
- MC includes signed and absolute weighted yields;
- data omits weighted-yield fields entirely rather than storing misleading zeroes or unit weights.

JSON writing uses stable stage ordering, sorted sample keys, UTF-8, two-space indentation, and a trailing newline.

## 6. Error handling

- Invalid YAML fails before reading ROOT data and names the invalid configuration field.
- Unsupported momentum units fail with the existing clear error.
- Inconsistent per-event lepton array lengths reject the event at `exactly_four_leptons`; a branch missing from the ROOT schema remains an I/O-level error.
- Non-finite lepton values reject the event at the earliest named stage that consumes them and never enter the processed frame.
- Missing MC normalization fields raise an error; they are not replaced with defaults.
- A cutflow object validates stage order and refuses unknown stage names.
- Output directories are created only by the CLI entry point, not by pure selection functions.

## 7. Tests

### `tests/test_selection.py`

Use synthetic event dictionaries with analytically controlled four-vectors. Cover:

- exactly 3, 4, and 5 leptons;
- `lep_n` disagreement with array lengths;
- unsupported flavour;
- each ordered pT threshold just below, equal to, and above its boundary;
- electron and muon eta just below, equal to, and above their limits;
- non-zero total charge;
- no valid two-SFOS pairing;
- every possible alternative SFOS pair in the 5 GeV veto;
- Z1 lower and upper boundaries;
- fixed Z2 lower and upper boundaries;
- sliding Z2 values and continuity at 140 and 190 GeV;
- `m4l` lower and upper boundaries;
- changing a parsed YAML value changes the event result;
- accepted events produce finite features without adding forbidden fields.

### `tests/test_cutflow.py`

Construct one event that fails at each stage plus accepted MC and data events. Verify:

- counts are monotonically non-increasing;
- every failure increments exactly the preceding stages;
- `selected` equals the final frame length;
- relative and cumulative efficiencies are correct, including zero denominators;
- MC signed and absolute weighted yields are accumulated at every passed stage;
- negative MC weights remain signed in one field and positive in the absolute field;
- data has no weighted-yield fields;
- sample keys remain separate;
- repeated processing of identical synthetic input produces identical cutflow content.

### Existing regression tests

The existing pairing, features, weights, split, validation, and progress tests must continue to pass. `FEATURES` remains unchanged.

## 8. Acceptance commands

Focused validation:

```bash
.venv/bin/python -m pytest tests/test_selection.py tests/test_cutflow.py tests/test_pairing.py tests/test_features.py tests/test_weights.py -q
```

Full validation:

```bash
.venv/bin/python -m pytest -q
```

No real-data preprocessing, model training, output replacement, or signal-window evaluation is part of these acceptance commands.

## 9. Documentation updates after implementation

After tests pass, update:

- `docs/physics/selection-standard.md` from proposed to implemented status;
- `README.md` with the active YAML fields and cutflow output;
- `docs/project/overview.md` with the new processing flow;
- `docs/roadmap/next-stage.md` to mark Task 1–2 complete only after actual verification;
- `docs/briefings/progress-briefing.md` and `docs/archive/codex-handoff-and-roadmap.md` with verified status, without copying historical event counts into the new baseline.

Because the parent Git repository has no commit history and the project is wholly untracked, this specification and subsequent implementation will not be committed unless the user separately authorizes establishing a Git baseline.
