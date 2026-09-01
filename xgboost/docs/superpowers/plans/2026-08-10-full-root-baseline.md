# Full ROOT Preprocessing Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a safe, auditable preprocessing path that reads every event in the three configured ROOT files without overwriting the historical demo outputs.

**Architecture:** Keep `config/demo.yaml` in 5,000-entry smoke mode and resolve an explicit immutable `ReadPolicy` for each invocation. Stream ROOT arrays in chunks, validate one immutable MC-normalization object per MC sample, then construct every aggregate payload before a dedicated output writer creates either the legacy smoke destinations or a fresh isolated full-run directory. Manifest schema 1.1 records the effective read policy, MC constants, config snapshot, and output locations.

**Tech Stack:** Python 3.12, pathlib, dataclasses, argparse, PyYAML, uproot 5, awkward arrays, NumPy, pandas, pytest.

## Global Constraints

- Keep `config/demo.yaml` at `entry_stop: 5000`; `--full` alone changes the effective limit to `null`.
- Use `chunk_size_events: 50000` by default and reject booleans, zero, negative values, and fractional values.
- Full effective read mode always requires a fresh `--run-dir`; it must never write to `data/processed/` or `outputs/`.
- Never overwrite a pre-existing run directory, raw ROOT file, historical processed CSV, model, metric, or plot.
- Require all four MC branches: `xsec`, `kfac`, `filteff`, and `sum_of_weights`; keep signed per-event `mcWeight` values valid.
- Require MC constants to match within `rtol=1e-12`, `atol=0.0`; require finite values, `xsec >= 0`, `kfac > 0`, `0 <= filteff <= 1`, and `sum_of_weights != 0`.
- Do not change selection, feature columns, split assignment, physical-weight semantics, or training-weight semantics.
- Do not train XGBoost, select a threshold, score data, make plots, or inspect event-level real-data mass/score values in Task 4A.
- Write `run_manifest.json` last; its absence marks an incomplete run and incomplete directories are retained for diagnosis.
- The parent repository currently has no `HEAD` and the whole project is untracked. Do not stage, commit, initialize Git history, or add ROOT/generated artifacts during this plan. Each task ends with a scoped status checkpoint instead of a commit.

## File Structure

### New files

- `src/preparation.py`: immutable read/output policies, preflight path validation, and the only writer for prepared run artifacts.
- `tests/test_preparation.py`: read-policy, protected-path, fresh-directory, exact-config-copy, and write-order tests.
- `tests/test_io.py`: fake-uproot chunk iteration, branch requirements, order, and global-limit tests.

### Modified files

- `src/io.py`: replace the one-shot `tree.arrays()` read with ordered `tree.iterate()` chunks.
- `src/weights.py`: define and validate `MCNormalization`, and make scalar physical weights consume it.
- `src/pipeline.py`: validate normalization and channel numbers across all read MC events; return normalization with each prepared sample; expose a pure cutflow builder.
- `src/provenance.py`: emit manifest schema 1.1 with config snapshot, read policy, output locations, and typed MC-normalization entries.
- `scripts/prepare_demo.py`: add `--full` and `--run-dir`, perform all preflight checks before ROOT I/O, build all payloads before writing, and report sample-level progress.
- `config/demo.yaml`: add `chunk_size_events: 50000` while retaining `entry_stop: 5000`.
- `.gitignore`: ignore `runs/*` while preserving `runs/.gitkeep`.
- `tests/test_weights.py`: normalization boundaries, tolerance, and effective cross section.
- `tests/test_cutflow.py`: pipeline normalization, full-read channel validation, and chunk-size forwarding.
- `tests/test_manifest.py`: exact manifest 1.1 schema and normalization serialization.
- `tests/test_prepare_script.py`: smoke/full CLI integration, config immutability, output isolation, and incomplete-run behavior.
- `README.md`, `docs/project/overview.md`, `docs/roadmap/next-stage.md`, and `AGENTS.md`: document the verified Task 4A commands, aggregate counts, safety contract, and Task 4B boundary.

---

### Task 1: Resolve and validate the effective ROOT read policy

**Files:**
- Create: `src/preparation.py`
- Create: `tests/test_preparation.py`
- Modify: `config/demo.yaml:1-6`

**Interfaces:**
- Consumes: the parsed top-level YAML mapping and the CLI `--full` boolean.
- Produces: `ReadPolicy(mode: Literal["head", "full"], entry_stop: int | None, chunk_size_events: int)`; `ReadPolicy.as_dict() -> dict[str, object]`; `resolve_read_policy(config: Mapping[str, Any], *, full_override: bool) -> ReadPolicy`.

- [ ] **Step 1: Write failing read-policy tests**

```python
# tests/test_preparation.py
import pytest

from src.preparation import ReadPolicy, resolve_read_policy


def test_head_policy_uses_positive_configured_limit_and_default_chunk_size():
    policy = resolve_read_policy({"entry_stop": 5000}, full_override=False)

    assert policy == ReadPolicy("head", 5000, 50_000)
    assert policy.as_dict() == {
        "mode": "head",
        "entry_stop": 5000,
        "chunk_size_events": 50_000,
    }


def test_full_override_ignores_configured_entry_stop():
    policy = resolve_read_policy(
        {"entry_stop": 5000, "chunk_size_events": 17}, full_override=True
    )

    assert policy == ReadPolicy("full", None, 17)


def test_null_entry_stop_is_full_mode_without_override():
    assert resolve_read_policy(
        {"entry_stop": None, "chunk_size_events": 9}, full_override=False
    ) == ReadPolicy("full", None, 9)


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.5, "5000"])
def test_invalid_entry_stop_fails(value):
    with pytest.raises(ValueError, match="entry_stop must be null or a positive integer"):
        resolve_read_policy({"entry_stop": value}, full_override=False)


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.5, "50000", None])
def test_invalid_chunk_size_fails(value):
    with pytest.raises(ValueError, match="chunk_size_events must be a positive integer"):
        resolve_read_policy(
            {"entry_stop": 5000, "chunk_size_events": value},
            full_override=False,
        )
```

- [ ] **Step 2: Run the focused tests and verify the missing-module failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_preparation.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'src.preparation'`.

- [ ] **Step 3: Implement the immutable policy and strict positive-integer validation**

```python
# src/preparation.py
from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral
from typing import Any, Literal, Mapping


def _positive_integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


@dataclass(frozen=True)
class ReadPolicy:
    mode: Literal["head", "full"]
    entry_stop: int | None
    chunk_size_events: int

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "entry_stop": self.entry_stop,
            "chunk_size_events": self.chunk_size_events,
        }


def resolve_read_policy(
    config: Mapping[str, Any], *, full_override: bool
) -> ReadPolicy:
    chunk_size = _positive_integer(
        config.get("chunk_size_events", 50_000), "chunk_size_events"
    )
    if full_override:
        return ReadPolicy("full", None, chunk_size)

    entry_stop = config.get("entry_stop")
    if entry_stop is None:
        return ReadPolicy("full", None, chunk_size)
    try:
        validated_stop = _positive_integer(entry_stop, "entry_stop")
    except ValueError as exc:
        raise ValueError("entry_stop must be null or a positive integer") from exc
    return ReadPolicy("head", validated_stop, chunk_size)
```

Add this exact top-level config line immediately after `entry_stop: 5000`:

```yaml
chunk_size_events: 50000
```

- [ ] **Step 4: Run the focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_preparation.py -q
```

Expected: all read-policy tests pass.

- [ ] **Step 5: Record the scoped checkpoint without staging**

Run:

```bash
git status --short -- src/preparation.py tests/test_preparation.py config/demo.yaml
```

Expected: only the new policy files and the intended config edit appear in this checkpoint.

---

### Task 2: Stream ROOT events in bounded ordered chunks

**Files:**
- Create: `tests/test_io.py`
- Modify: `src/io.py:56-80`

**Interfaces:**
- Consumes: `ReadPolicy.entry_stop` and `ReadPolicy.chunk_size_events` from Task 1.
- Produces: `iter_events(path, tree_name=None, *, is_data, entry_stop=None, chunk_size_events=50_000) -> Iterable[dict[str, Any]]`, preserving its current event-dictionary output.

- [ ] **Step 1: Write fake-uproot tests for chunk order and a global stop**

```python
# tests/test_io.py
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from src import io


def event_columns(event_numbers, *, is_data):
    size = len(event_numbers)
    columns = {
        "runNumber": [1] * size,
        "eventNumber": event_numbers,
        "channelNumber": [0 if is_data else 345060] * size,
        "lep_n": [4] * size,
        "lep_pt": [[20.0, 15.0, 10.0, 7.0]] * size,
        "lep_eta": [[0.1, -0.1, 0.2, -0.2]] * size,
        "lep_phi": [[0.0, 1.0, 2.0, 3.0]] * size,
        "lep_e": [[25.0, 20.0, 15.0, 10.0]] * size,
        "lep_charge": [[1, -1, 1, -1]] * size,
        "lep_type": [[11, 11, 13, 13]] * size,
    }
    if not is_data:
        columns.update(
            mcWeight=[1.0] * size,
            xsec=[2.0] * size,
            kfac=[1.0] * size,
            filteff=[0.5] * size,
            sum_of_weights=[100.0] * size,
        )
    return columns


class FakeChunk:
    def __init__(self, columns):
        self._columns = columns
        self.fields = list(columns)

    def __len__(self):
        return len(next(iter(self._columns.values())))

    def __getitem__(self, field):
        return self._columns[field]


class FakeTree:
    name = "analysis"
    num_entries = 5

    def __init__(self, chunks, branches):
        self._chunks = chunks
        self._branches = branches
        self.calls = []

    def keys(self):
        return list(self._branches)

    def iterate(self, requested, **kwargs):
        self.calls.append((requested, kwargs))
        yield from self._chunks


class FakeRootFile:
    def __init__(self, tree):
        self.tree = tree

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def __getitem__(self, name):
        assert name == "analysis"
        return self.tree


def install_fake_uproot(monkeypatch, tree):
    module = SimpleNamespace(open=lambda path: FakeRootFile(tree))
    monkeypatch.setattr(io, "_import_uproot", lambda: module)


def test_iter_events_preserves_order_across_chunks(monkeypatch):
    chunks = [
        FakeChunk(event_columns([10, 11], is_data=False)),
        FakeChunk(event_columns([12, 13, 14], is_data=False)),
    ]
    tree = FakeTree(chunks, chunks[0].fields)
    install_fake_uproot(monkeypatch, tree)

    events = list(
        io.iter_events(
            "fake.root",
            "analysis",
            is_data=False,
            entry_stop=None,
            chunk_size_events=2,
        )
    )

    assert [event["eventNumber"] for event in events] == [10, 11, 12, 13, 14]
    assert tree.calls == [
        (
            io.COMMON_BRANCHES + io.MC_BRANCHES,
            {"entry_stop": None, "step_size": 2, "library": "ak"},
        )
    ]


def test_iter_events_passes_one_global_entry_stop_to_tree(monkeypatch):
    chunks = [
        FakeChunk(event_columns([10, 11], is_data=True)),
        FakeChunk(event_columns([12], is_data=True)),
    ]
    tree = FakeTree(chunks, chunks[0].fields)
    install_fake_uproot(monkeypatch, tree)

    list(
        io.iter_events(
            "fake.root",
            "analysis",
            is_data=True,
            entry_stop=3,
            chunk_size_events=2,
        )
    )

    assert tree.calls[0][1]["entry_stop"] == 3
    assert tree.calls[0][1]["step_size"] == 2
```

- [ ] **Step 2: Add failing branch and direct chunk-size validation tests**

```python
@pytest.mark.parametrize("value", [True, False, 0, -1, 1.5])
def test_iter_events_rejects_invalid_chunk_size(value):
    with pytest.raises(ValueError, match="chunk_size_events must be a positive integer"):
        list(io.iter_events("unused.root", is_data=True, chunk_size_events=value))


def test_mc_requires_every_normalization_branch(monkeypatch):
    columns = event_columns([1], is_data=False)
    columns.pop("xsec")
    tree = FakeTree([], columns)
    install_fake_uproot(monkeypatch, tree)

    with pytest.raises(KeyError, match="xsec"):
        list(io.iter_events("fake.root", "analysis", is_data=False))


def test_data_does_not_require_mc_branches(monkeypatch):
    chunk = FakeChunk(event_columns([1], is_data=True))
    tree = FakeTree([chunk], chunk.fields)
    install_fake_uproot(monkeypatch, tree)

    events = list(io.iter_events("fake.root", "analysis", is_data=True))

    assert len(events) == 1
    assert "xsec" not in events[0]
```

- [ ] **Step 3: Run the tests and verify that one-shot I/O fails the contract**

Run:

```bash
.venv/bin/python -m pytest tests/test_io.py -q
```

Expected: failures show that `chunk_size_events` is not accepted and `FakeTree.arrays` is unavailable.

- [ ] **Step 4: Replace the one-shot array read with `tree.iterate()`**

Implement this body in `src/io.py` and import `Integral` from `numbers`:

```python
def iter_events(
    path: str | Path,
    tree_name: str | None = None,
    *,
    is_data: bool,
    entry_stop: int | None = None,
    chunk_size_events: int = 50_000,
) -> Iterable[dict[str, Any]]:
    if (
        isinstance(chunk_size_events, bool)
        or not isinstance(chunk_size_events, Integral)
        or chunk_size_events <= 0
    ):
        raise ValueError("chunk_size_events must be a positive integer")

    uproot = _import_uproot()
    with uproot.open(path) as root_file:
        tree = discover_tree(root_file, tree_name)
        available = set(tree.keys())
        requested = COMMON_BRANCHES + ([] if is_data else MC_BRANCHES)
        missing = [name for name in requested if name not in available]
        if missing:
            raise KeyError(f"missing required branches: {missing}")
        for arrays in tree.iterate(
            requested,
            entry_stop=entry_stop,
            step_size=int(chunk_size_events),
            library="ak",
        ):
            fields = list(arrays.fields)
            for index in range(len(arrays)):
                event = {}
                for field in fields:
                    value = arrays[field][index]
                    event[field] = (
                        value.to_list() if hasattr(value, "to_list") else value
                    )
                yield event
```

- [ ] **Step 5: Run focused I/O tests and the existing suite that touches ROOT interfaces**

Run:

```bash
.venv/bin/python -m pytest tests/test_io.py tests/test_cutflow.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Record the scoped checkpoint without staging**

Run:

```bash
git status --short -- src/io.py tests/test_io.py
```

Expected: only the intended I/O implementation and tests appear for this task.

---

### Task 3: Validate one immutable MC-normalization object per sample

**Files:**
- Modify: `src/weights.py:1-47`
- Modify: `tests/test_weights.py`

**Interfaces:**
- Consumes: an MC event mapping containing `xsec`, `kfac`, `filteff`, and `sum_of_weights`.
- Produces: `MCNormalization.from_event(event) -> MCNormalization`; `assert_matches(event, *, rtol=1e-12, atol=0.0) -> None`; `effective_cross_section_pb: float`; and `physical_event_weight(event, luminosity_pb, *, normalization=None) -> float`.

- [ ] **Step 1: Write failing value, tolerance, and weight-reuse tests**

```python
# add to tests/test_weights.py using pytest-style functions
import pytest

from src.weights import MCNormalization


def normalization_event(**overrides):
    event = {
        "mcWeight": -0.5,
        "xsec": 2.0,
        "kfac": 1.2,
        "filteff": 0.5,
        "sum_of_weights": 100.0,
    }
    event.update(overrides)
    return event


def test_mc_normalization_parses_fields_and_effective_cross_section():
    normalization = MCNormalization.from_event(normalization_event())

    assert normalization == MCNormalization(
        xsec_pb=2.0,
        k_factor=1.2,
        filter_efficiency=0.5,
        sum_of_weights=100.0,
    )
    assert normalization.effective_cross_section_pb == pytest.approx(1.2)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"xsec": float("nan")}, "finite"),
        ({"xsec": -1.0}, "xsec_pb must be non-negative"),
        ({"kfac": 0.0}, "k_factor must be strictly positive"),
        ({"kfac": -1.0}, "k_factor must be strictly positive"),
        ({"filteff": -0.01}, "filter_efficiency must be in"),
        ({"filteff": 1.01}, "filter_efficiency must be in"),
        ({"sum_of_weights": 0.0}, "sum_of_weights must be non-zero"),
        ({"sum_of_weights": float("inf")}, "finite"),
    ],
)
def test_mc_normalization_rejects_invalid_values(overrides, message):
    with pytest.raises(ValueError, match=message):
        MCNormalization.from_event(normalization_event(**overrides))


def test_mc_normalization_accepts_only_values_within_fixed_tolerance():
    normalization = MCNormalization.from_event(normalization_event())
    normalization.assert_matches(normalization_event(xsec=2.0 * (1.0 + 5e-13)))

    with pytest.raises(ValueError, match="xsec_pb changed within one MC sample"):
        normalization.assert_matches(normalization_event(xsec=2.0 * (1.0 + 2e-12)))


def test_scalar_weight_uses_validated_normalization_object():
    event = normalization_event(xsec=2.0 * (1.0 + 5e-13))
    normalization = MCNormalization.from_event(normalization_event())

    assert physical_event_weight(
        event, 1000.0, normalization=normalization
    ) == pytest.approx(-6.0)
```

- [ ] **Step 2: Run the focused tests and verify the missing-type failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_weights.py -q
```

Expected: collection fails because `MCNormalization` does not exist.

- [ ] **Step 3: Implement validation and reuse the object in scalar weights**

Add this exact public type and helpers to `src/weights.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class MCNormalization:
    xsec_pb: float
    k_factor: float
    filter_efficiency: float
    sum_of_weights: float

    def __post_init__(self) -> None:
        for field in (
            "xsec_pb",
            "k_factor",
            "filter_efficiency",
            "sum_of_weights",
        ):
            try:
                value = float(getattr(self, field))
            except (TypeError, ValueError) as exc:
                raise ValueError("MC normalization values must be finite") from exc
            object.__setattr__(self, field, value)
        values = np.asarray(
            [
                self.xsec_pb,
                self.k_factor,
                self.filter_efficiency,
                self.sum_of_weights,
            ],
            dtype=float,
        )
        if not np.isfinite(values).all():
            raise ValueError("MC normalization values must be finite")
        if self.xsec_pb < 0:
            raise ValueError("xsec_pb must be non-negative")
        if self.k_factor <= 0:
            raise ValueError("k_factor must be strictly positive")
        if not 0 <= self.filter_efficiency <= 1:
            raise ValueError("filter_efficiency must be in the closed interval [0, 1]")
        if self.sum_of_weights == 0:
            raise ValueError("sum_of_weights must be non-zero")

    @classmethod
    def from_event(cls, event: Mapping[str, Any]) -> "MCNormalization":
        return cls(
            xsec_pb=float(event["xsec"]),
            k_factor=float(event["kfac"]),
            filter_efficiency=float(event["filteff"]),
            sum_of_weights=float(event["sum_of_weights"]),
        )

    @property
    def effective_cross_section_pb(self) -> float:
        return self.xsec_pb * self.k_factor * self.filter_efficiency

    def assert_matches(
        self,
        event: Mapping[str, Any],
        *,
        rtol: float = 1e-12,
        atol: float = 0.0,
    ) -> None:
        other = MCNormalization.from_event(event)
        for field in (
            "xsec_pb",
            "k_factor",
            "filter_efficiency",
            "sum_of_weights",
        ):
            if not np.isclose(
                getattr(self, field), getattr(other, field), rtol=rtol, atol=atol
            ):
                raise ValueError(f"{field} changed within one MC sample")
```

Change scalar weighting to this compatible signature and body:

```python
def physical_event_weight(
    event: Mapping[str, Any],
    luminosity_pb: float,
    *,
    normalization: MCNormalization | None = None,
) -> float:
    resolved = normalization or MCNormalization.from_event(event)
    if normalization is not None:
        resolved.assert_matches(event)
    value = physical_event_weights(
        event["mcWeight"],
        resolved.xsec_pb,
        resolved.k_factor,
        resolved.filter_efficiency,
        resolved.sum_of_weights,
        luminosity_pb,
    )
    return float(np.asarray(value))
```

- [ ] **Step 4: Run focused weight tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_weights.py -q
```

Expected: all old physical/training-weight tests and all new normalization tests pass.

- [ ] **Step 5: Record the scoped checkpoint without staging**

Run:

```bash
git status --short -- src/weights.py tests/test_weights.py
```

Expected: only the normalization implementation and tests appear for this task.

---

### Task 4: Carry validated normalization through sample preparation

**Files:**
- Modify: `src/pipeline.py:11-77`
- Modify: `tests/test_cutflow.py:142-190`

**Interfaces:**
- Consumes: the Task 2 `iter_events` interface with its `chunk_size_events` keyword and the Task 3 `MCNormalization` type.
- Produces: `PreparedSample(frame, cutflow, normalization)` where normalization is `MCNormalization` for MC and `None` for data; `prepare_sample` gains the keyword `chunk_size_events=50_000`.

- [ ] **Step 1: Extend pipeline tests with the returned normalization and forwarded chunk size**

```python
# update tests/test_cutflow.py
from src.weights import MCNormalization


def test_prepare_sample_returns_one_validated_mc_normalization(monkeypatch):
    events = [
        raw_event(event_number=1, passing=True),
        raw_event(event_number=2, passing=False, mc_weight=-0.5),
    ]
    calls = []

    def fake_iter_events(*args, **kwargs):
        calls.append(kwargs)
        return iter(events)

    monkeypatch.setattr("src.pipeline.iter_events", fake_iter_events)

    prepared = prepare_sample(
        "unused.root",
        sample_name="higgs_42",
        selection=selection_config(),
        tree_name="analysis",
        momentum_unit="GeV",
        is_data=False,
        label=1,
        expected_channels=[42],
        luminosity_pb=1000.0,
        chunk_size_events=17,
    )

    assert prepared.normalization == MCNormalization(2.0, 1.0, 1.0, 100.0)
    assert calls[0]["chunk_size_events"] == 17
    assert prepared.cutflow["stages"]["read"]["signed_weighted_yield"] == 10.0


def test_prepare_sample_rejects_normalization_change_in_rejected_event(monkeypatch):
    events = [
        raw_event(event_number=1, passing=True),
        raw_event(event_number=2, passing=False),
    ]
    events[1]["sum_of_weights"] = 101.0
    monkeypatch.setattr("src.pipeline.iter_events", lambda *args, **kwargs: iter(events))

    with pytest.raises(ValueError, match="sum_of_weights changed"):
        prepare_sample(
            "unused.root",
            sample_name="higgs_42",
            selection=selection_config(),
            tree_name="analysis",
            momentum_unit="GeV",
            is_data=False,
            label=1,
            expected_channels=[42],
        )


def test_prepare_sample_checks_channel_number_before_selection(monkeypatch):
    event = raw_event(event_number=1, passing=False)
    event["channelNumber"] = 999
    monkeypatch.setattr("src.pipeline.iter_events", lambda *args, **kwargs: iter([event]))

    with pytest.raises(ValueError, match="999"):
        prepare_sample(
            "unused.root",
            sample_name="higgs_42",
            selection=selection_config(),
            tree_name="analysis",
            momentum_unit="GeV",
            is_data=False,
            label=1,
            expected_channels=[42],
        )


def test_prepare_sample_data_has_no_mc_normalization(monkeypatch):
    event = raw_event(event_number=1, passing=True, is_data=True)
    monkeypatch.setattr("src.pipeline.iter_events", lambda *args, **kwargs: iter([event]))

    prepared = prepare_sample(
        "unused.root",
        sample_name="data16_periodA",
        selection=selection_config(),
        tree_name="analysis",
        momentum_unit="GeV",
        is_data=True,
    )

    assert prepared.normalization is None
```

- [ ] **Step 2: Add the explicit zero-read MC failure**

```python
def test_prepare_sample_rejects_mc_with_zero_read_events(monkeypatch):
    monkeypatch.setattr("src.pipeline.iter_events", lambda *args, **kwargs: iter(()))

    with pytest.raises(ValueError, match="no MC events were read"):
        prepare_sample(
            "unused.root",
            sample_name="higgs_42",
            selection=selection_config(),
            tree_name="analysis",
            momentum_unit="GeV",
            is_data=False,
            label=1,
            expected_channels=[42],
        )
```

- [ ] **Step 3: Run focused tests and verify interface failures**

Run:

```bash
.venv/bin/python -m pytest tests/test_cutflow.py -q
```

Expected: failures show that `PreparedSample` lacks `normalization` and `prepare_sample` lacks `chunk_size_events`.

- [ ] **Step 4: Integrate normalization before selection and validate all read channels**

Make these structural changes in `src/pipeline.py`:

```python
from .weights import MCNormalization, physical_event_weight, training_weights


@dataclass(frozen=True)
class PreparedSample:
    frame: pd.DataFrame
    cutflow: dict[str, Any]
    normalization: MCNormalization | None = None
```

Add `chunk_size_events=50_000` to `prepare_sample()`. Initialize `normalization = None` and `observed_channels = set()` before the loop. Use this loop ordering:

```python
for event in iter_events(
    path,
    tree_name,
    is_data=is_data,
    entry_stop=entry_stop,
    chunk_size_events=chunk_size_events,
):
    weight = None
    if not is_data:
        observed_channels.add(int(event["channelNumber"]))
        if normalization is None:
            normalization = MCNormalization.from_event(event)
        weight = physical_event_weight(
            event, luminosity_pb, normalization=normalization
        )
    cutflow.record_read(weight)
    result = select_event(event, selection, momentum_unit)
    cutflow.record_selection(result, weight)
    if result.accepted:
        assert result.candidate is not None
        row = build_candidate_features(event, result.candidate)
        if weight is not None:
            row["physical_weight"] = weight
        rows.append(row)
```

Immediately after iteration, enforce these checks before the existing empty-frame check:

```python
if not is_data:
    if normalization is None:
        raise ValueError(f"{sample_name}: no MC events were read from {path}")
    validate_channel_numbers(observed_channels, expected_channels, sample_name)
```

Remove the selected-frame-only channel check and return:

```python
return PreparedSample(
    frame=frame,
    cutflow=cutflow.to_dict(),
    normalization=normalization,
)
```

- [ ] **Step 5: Run pipeline, weight, selection, and feature regressions**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_cutflow.py \
  tests/test_weights.py \
  tests/test_selection.py \
  tests/test_features.py -q
```

Expected: all tests pass with unchanged feature, selection, split, and signed-weight behavior.

- [ ] **Step 6: Record the scoped checkpoint without staging**

Run:

```bash
git status --short -- src/pipeline.py tests/test_cutflow.py
```

Expected: only the prepared-sample integration and tests appear for this task.

---

### Task 5: Upgrade provenance to manifest schema 1.1

**Files:**
- Modify: `src/provenance.py:19-20,33-42,256-298`
- Modify: `tests/test_manifest.py:29-120`

**Interfaces:**
- Consumes: each MC sample's `MCNormalization`, expected DSIDs, luminosity, effective `ReadPolicy.as_dict()`, optional config snapshot path, and resolved output paths.
- Produces: `MCNormalizationInput(sample_name, normalization, dsids, luminosity_pb)` and a schema-1.1 `build_run_manifest` that adds the keyword-only parameters `config_snapshot_path`, `mc_normalizations`, and `output_locations`.

- [ ] **Step 1: Rewrite the primary manifest test around the 1.1 contract**

```python
# imports in tests/test_manifest.py
from src.provenance import MCNormalizationInput
from src.weights import MCNormalization


def test_manifest_records_read_policy_normalization_snapshot_and_outputs(tmp_path):
    config_path = tmp_path / "demo.yaml"
    config_path.write_bytes(b"entry_stop: 5000\nchunk_size_events: 50000\n")
    paths = {}
    for name, content in (
        ("zz_700600", b"zz"),
        ("data16_periodA", b"data"),
        ("higgs_345060", b"higgs"),
    ):
        path = tmp_path / f"{name}.root"
        path.write_bytes(content)
        paths[name] = path

    payload = build_run_manifest(
        config_path=config_path,
        config_snapshot_path="runs/full-baseline-2026-08-10/config.yaml",
        input_paths=paths,
        processing={
            "read_policy": {
                "mode": "full",
                "entry_stop": None,
                "chunk_size_events": 50_000,
            },
            "random_seed": 42,
            "tree_name": "analysis",
            "momentum_unit": "GeV",
            "selection": {"z2_min_mode": "fixed"},
        },
        mc_normalizations=[
            MCNormalizationInput(
                "higgs_345060",
                MCNormalization(2.0, 1.2, 0.5, 100.0),
                (345060,),
                10_000.0,
            ),
            MCNormalizationInput(
                "zz_700600",
                MCNormalization(3.0, 1.0, 0.25, 200.0),
                (700600,),
                10_000.0,
            ),
        ],
        output_locations={
            "run_dir": "runs/full-baseline-2026-08-10",
            "processed_dir": "runs/full-baseline-2026-08-10/processed",
            "artifacts_dir": "runs/full-baseline-2026-08-10/artifacts",
        },
        created_at_utc="2026-08-10T17:30:00Z",
        versions={"python": "3.12.13"},
        git_commit="unavailable",
        cutflow_schema_version="1.0",
    )

    assert payload["schema_version"] == "1.1"
    assert payload["config"] == {
        "path": str(config_path),
        "snapshot_path": "runs/full-baseline-2026-08-10/config.yaml",
        "sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
    }
    assert payload["processing"]["read_policy"]["mode"] == "full"
    assert payload["mc_normalization"]["higgs_345060"] == {
        "dsids": [345060],
        "luminosity_pb": 10_000.0,
        "xsec_pb": 2.0,
        "k_factor": 1.2,
        "filter_efficiency": 0.5,
        "sum_of_weights": 100.0,
        "effective_cross_section_pb": 1.2,
    }
    assert payload["outputs"] == {
        "locations": {
            "run_dir": "runs/full-baseline-2026-08-10",
            "processed_dir": "runs/full-baseline-2026-08-10/processed",
            "artifacts_dir": "runs/full-baseline-2026-08-10/artifacts",
        },
        "cutflow_schema_version": "1.0",
        "data_summary_schema_version": "1.0",
        "run_manifest_schema_version": "1.1",
    }
```

- [ ] **Step 2: Add manifest validation tests for duplicate names and empty DSIDs**

```python
def test_manifest_rejects_duplicate_mc_normalization_names(tmp_path):
    config_path = tmp_path / "demo.yaml"
    input_path = tmp_path / "higgs.root"
    config_path.write_bytes(b"config")
    input_path.write_bytes(b"root")
    item = MCNormalizationInput(
        "higgs_345060",
        MCNormalization(2.0, 1.0, 1.0, 100.0),
        (345060,),
        10_000.0,
    )

    with pytest.raises(ValueError, match="duplicate MC normalization sample_name"):
        build_run_manifest(
            config_path=config_path,
            config_snapshot_path=None,
            input_paths={"higgs_345060": input_path},
            processing={},
            mc_normalizations=[item, item],
            output_locations={
                "run_dir": None,
                "processed_dir": "data/processed",
                "artifacts_dir": "outputs",
            },
            versions={},
            git_commit="unavailable",
        )


def test_manifest_rejects_empty_normalization_dsids(tmp_path):
    config_path = tmp_path / "demo.yaml"
    input_path = tmp_path / "higgs.root"
    config_path.write_bytes(b"config")
    input_path.write_bytes(b"root")

    with pytest.raises(ValueError, match="dsids must not be empty"):
        build_run_manifest(
            config_path=config_path,
            config_snapshot_path=None,
            input_paths={"higgs_345060": input_path},
            processing={},
            mc_normalizations=[
                MCNormalizationInput(
                    "higgs_345060",
                    MCNormalization(2.0, 1.0, 1.0, 100.0),
                    (),
                    10_000.0,
                )
            ],
            output_locations={
                "run_dir": None,
                "processed_dir": "data/processed",
                "artifacts_dir": "outputs",
            },
            versions={},
            git_commit="unavailable",
        )
```

- [ ] **Step 3: Run manifest tests and verify the old schema failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_manifest.py -q
```

Expected: tests fail because the new arguments and `MCNormalizationInput` do not exist and the schema remains `1.0`.

- [ ] **Step 4: Implement the typed normalization manifest entries**

Add to `src/provenance.py`:

```python
from .weights import MCNormalization

MANIFEST_SCHEMA_VERSION = "1.1"


@dataclass(frozen=True)
class MCNormalizationInput:
    sample_name: str
    normalization: MCNormalization
    dsids: tuple[int, ...]
    luminosity_pb: float


def _mc_normalization_entries(
    samples: Sequence[MCNormalizationInput],
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for sample in sorted(samples, key=lambda value: value.sample_name):
        if sample.sample_name in output:
            raise ValueError("duplicate MC normalization sample_name")
        dsids = sorted(_integer_dsids(sample.dsids, sample.sample_name))
        if not dsids:
            raise ValueError(f"{sample.sample_name}: dsids must not be empty")
        luminosity_pb = float(sample.luminosity_pb)
        if not np.isfinite(luminosity_pb) or luminosity_pb <= 0:
            raise ValueError(
                f"{sample.sample_name}: luminosity_pb must be finite and positive"
            )
        normalization = sample.normalization
        output[sample.sample_name] = {
            "dsids": dsids,
            "luminosity_pb": luminosity_pb,
            "xsec_pb": normalization.xsec_pb,
            "k_factor": normalization.k_factor,
            "filter_efficiency": normalization.filter_efficiency,
            "sum_of_weights": normalization.sum_of_weights,
            "effective_cross_section_pb": (
                normalization.effective_cross_section_pb
            ),
        }
    return output
```

Extend `build_run_manifest()` with these required keyword-only arguments:

```python
config_snapshot_path: str | Path | None,
mc_normalizations: Sequence[MCNormalizationInput],
output_locations: Mapping[str, str | Path | None],
```

Build these exact sections:

```python
"config": {
    "path": str(config_source),
    "snapshot_path": (
        None if config_snapshot_path is None else str(config_snapshot_path)
    ),
    "sha256": sha256_file(config_source),
},
"mc_normalization": _mc_normalization_entries(mc_normalizations),
"outputs": {
    "locations": {
        name: None if path is None else str(path)
        for name, path in output_locations.items()
    },
    "cutflow_schema_version": str(cutflow_schema_version),
    "data_summary_schema_version": SUMMARY_SCHEMA_VERSION,
    "run_manifest_schema_version": MANIFEST_SCHEMA_VERSION,
},
```

For the timestamp, software-version, Git-fallback, and unlimited-read tests, pass these exact additional arguments and preserve their existing assertions:

```python
config_snapshot_path=None,
mc_normalizations=[],
output_locations={
    "run_dir": None,
    "processed_dir": "data/processed",
    "artifacts_dir": "outputs",
},
```

The primary MC test uses the two non-empty `MCNormalizationInput` objects shown in Step 1 instead of this empty sequence.

- [ ] **Step 5: Run provenance and summary regressions**

Run:

```bash
.venv/bin/python -m pytest tests/test_manifest.py tests/test_summary.py -q
```

Expected: manifest 1.1 and unchanged summary 1.0 tests pass.

- [ ] **Step 6: Record the scoped checkpoint without staging**

Run:

```bash
git status --short -- src/provenance.py tests/test_manifest.py
```

Expected: only the manifest schema implementation and its tests appear for this task.

---

### Task 6: Add safe output layouts and wire the full-run CLI

**Files:**
- Modify: `src/preparation.py`
- Modify: `tests/test_preparation.py`
- Modify: `src/pipeline.py:80-101`
- Modify: `scripts/prepare_demo.py`
- Modify: `tests/test_prepare_script.py`
- Modify: `.gitignore`
- Create: `runs/.gitkeep`

**Interfaces:**
- Consumes: `ReadPolicy`, three `PreparedSample` values, pure cutflow/summary/manifest mappings, the initially read config bytes, and CLI paths.
- Produces: `OutputLayout`, `resolve_output_layout`, `build_cutflow`, `write_preparation_outputs`, and CLI flags `--full` and `--run-dir PATH` with the signatures defined below.

- [ ] **Step 1: Write output-layout preflight tests before CLI integration**

```python
# add to tests/test_preparation.py
from pathlib import Path

from src.preparation import OutputLayout, resolve_output_layout


def test_full_mode_requires_run_directory(tmp_path):
    with pytest.raises(ValueError, match="full read mode requires --run-dir"):
        resolve_output_layout(
            project_root=tmp_path,
            working_directory=tmp_path,
            read_policy=ReadPolicy("full", None, 50_000),
            run_dir=None,
            output_dir=None,
        )


def test_fresh_run_directory_gets_isolated_paths(tmp_path):
    layout = resolve_output_layout(
        project_root=tmp_path,
        working_directory=tmp_path,
        read_policy=ReadPolicy("full", None, 50_000),
        run_dir=Path("runs/full-baseline-2026-08-10"),
        output_dir=None,
    )

    assert layout == OutputLayout(
        run_dir=Path("runs/full-baseline-2026-08-10"),
        processed_dir=Path("runs/full-baseline-2026-08-10/processed"),
        artifacts_dir=Path("runs/full-baseline-2026-08-10/artifacts"),
        config_snapshot=Path("runs/full-baseline-2026-08-10/config.yaml"),
    )
    assert not (tmp_path / "runs/full-baseline-2026-08-10").exists()


def test_run_directory_and_explicit_output_directory_are_mutually_exclusive(tmp_path):
    with pytest.raises(ValueError, match="cannot be used together"):
        resolve_output_layout(
            project_root=tmp_path,
            working_directory=tmp_path,
            read_policy=ReadPolicy("head", 5000, 50_000),
            run_dir="runs/smoke",
            output_dir="artifacts",
        )


def test_existing_run_directory_fails(tmp_path):
    (tmp_path / "runs/existing").mkdir(parents=True)

    with pytest.raises(FileExistsError, match="already exists"):
        resolve_output_layout(
            project_root=tmp_path,
            working_directory=tmp_path,
            read_policy=ReadPolicy("full", None, 50_000),
            run_dir="runs/existing",
            output_dir=None,
        )


@pytest.mark.parametrize(
    "protected",
    [
        ".",
        "data/raw/new-run",
        "data/processed/new-run",
        "outputs/new-run",
        "config/new-run",
        "docs/new-run",
        "src/new-run",
        "scripts/new-run",
        "tests/new-run",
        ".git/new-run",
        ".venv/new-run",
    ],
)
def test_run_directory_rejects_protected_project_paths(tmp_path, protected):
    with pytest.raises(ValueError, match="protected project path"):
        resolve_output_layout(
            project_root=tmp_path,
            working_directory=tmp_path,
            read_policy=ReadPolicy("full", None, 50_000),
            run_dir=protected,
            output_dir=None,
        )
```

- [ ] **Step 2: Implement output-layout resolution without creating directories**

Add to `src/preparation.py`:

```python
from pathlib import Path


@dataclass(frozen=True)
class OutputLayout:
    run_dir: Path | None
    processed_dir: Path
    artifacts_dir: Path
    config_snapshot: Path | None

    def manifest_locations(self) -> dict[str, str | None]:
        return {
            "run_dir": None if self.run_dir is None else str(self.run_dir),
            "processed_dir": str(self.processed_dir),
            "artifacts_dir": str(self.artifacts_dir),
        }


def _is_within(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def resolve_output_layout(
    *,
    project_root: Path,
    working_directory: Path,
    read_policy: ReadPolicy,
    run_dir: str | Path | None,
    output_dir: str | Path | None,
) -> OutputLayout:
    if read_policy.mode == "full" and run_dir is None:
        raise ValueError("full read mode requires --run-dir")
    if run_dir is not None and output_dir is not None:
        raise ValueError("--run-dir and --output-dir cannot be used together")
    if run_dir is None:
        return OutputLayout(
            run_dir=None,
            processed_dir=Path("data/processed"),
            artifacts_dir=Path("outputs") if output_dir is None else Path(output_dir),
            config_snapshot=None,
        )

    logical_run_dir = Path(run_dir)
    resolved_project = project_root.resolve()
    resolved_run = (
        logical_run_dir
        if logical_run_dir.is_absolute()
        else working_directory.resolve() / logical_run_dir
    ).resolve()
    protected_descendants = [
        resolved_project / "data/raw",
        resolved_project / "data/processed",
        resolved_project / "outputs",
        resolved_project / "config",
        resolved_project / "docs",
        resolved_project / "src",
        resolved_project / "scripts",
        resolved_project / "tests",
        resolved_project / ".git",
        resolved_project / ".venv",
    ]
    if resolved_run == resolved_project or any(
        _is_within(resolved_run, path.resolve()) for path in protected_descendants
    ):
        raise ValueError("--run-dir resolves inside a protected project path")
    if resolved_run.exists():
        raise FileExistsError(f"run directory already exists: {logical_run_dir}")
    return OutputLayout(
        run_dir=logical_run_dir,
        processed_dir=logical_run_dir / "processed",
        artifacts_dir=logical_run_dir / "artifacts",
        config_snapshot=logical_run_dir / "config.yaml",
    )
```

This exact check rejects the project root itself and protected descendants while permitting `runs/full-baseline-2026-08-10`.

- [ ] **Step 3: Extract a pure cutflow payload builder**

Add this public function in `src/pipeline.py` and make `write_cutflow()` call it:

```python
def build_cutflow(
    samples: Mapping[str, CutflowAccumulator | Mapping[str, Any]],
    *,
    z2_min_mode: str,
) -> dict[str, Any]:
    sample_output = {}
    for name in sorted(samples):
        value = samples[name]
        sample_output[name] = (
            value.to_dict() if isinstance(value, CutflowAccumulator) else dict(value)
        )
    return {
        "schema_version": CUTFLOW_SCHEMA_VERSION,
        "selection": {"z2_min_mode": str(z2_min_mode)},
        "samples": sample_output,
    }


def write_cutflow(
    samples: Mapping[str, CutflowAccumulator | Mapping[str, Any]],
    *,
    z2_min_mode: str,
    path: str | Path,
) -> None:
    payload = build_cutflow(samples, z2_min_mode=z2_min_mode)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
```

- [ ] **Step 4: Write exact-copy and manifest-last writer tests**

```python
# add to tests/test_preparation.py
import json
import pandas as pd

from src.preparation import write_preparation_outputs


def test_run_writer_copies_exact_config_and_writes_manifest_last(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_path = Path("config/demo.yaml")
    config_path.parent.mkdir()
    config_bytes = b"entry_stop: 5000\n# exact comment\n"
    config_path.write_bytes(config_bytes)
    layout = OutputLayout(
        run_dir=Path("runs/full"),
        processed_dir=Path("runs/full/processed"),
        artifacts_dir=Path("runs/full/artifacts"),
        config_snapshot=Path("runs/full/config.yaml"),
    )

    write_preparation_outputs(
        layout,
        config_source=config_path,
        config_bytes=config_bytes,
        mc_frame=pd.DataFrame({"eventNumber": [1]}),
        data_frame=pd.DataFrame({"eventNumber": [2]}),
        cutflow_payload={"schema_version": "1.0"},
        summary_payload={"schema_version": "1.0"},
        manifest_payload={"schema_version": "1.1"},
    )

    assert layout.config_snapshot.read_bytes() == config_bytes
    assert json.loads((layout.artifacts_dir / "run_manifest.json").read_text()) == {
        "schema_version": "1.1"
    }


def test_writer_rejects_changed_source_config_before_output_creation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_path = Path("demo.yaml")
    config_path.write_bytes(b"first")
    layout = OutputLayout(
        run_dir=Path("runs/full"),
        processed_dir=Path("runs/full/processed"),
        artifacts_dir=Path("runs/full/artifacts"),
        config_snapshot=Path("runs/full/config.yaml"),
    )
    config_path.write_bytes(b"changed")

    with pytest.raises(RuntimeError, match="config changed during preparation"):
        write_preparation_outputs(
            layout,
            config_source=config_path,
            config_bytes=b"first",
            mc_frame=pd.DataFrame({"eventNumber": [1]}),
            data_frame=pd.DataFrame({"eventNumber": [2]}),
            cutflow_payload={"schema_version": "1.0"},
            summary_payload={"schema_version": "1.0"},
            manifest_payload={"schema_version": "1.1"},
        )

    assert not layout.run_dir.exists()


def test_write_failure_leaves_incomplete_run_without_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_path = Path("demo.yaml")
    config_path.write_bytes(b"config")
    layout = OutputLayout(
        run_dir=Path("runs/full"),
        processed_dir=Path("runs/full/processed"),
        artifacts_dir=Path("runs/full/artifacts"),
        config_snapshot=Path("runs/full/config.yaml"),
    )

    def fail_to_csv(self, path, **kwargs):
        raise OSError("disk write failed")

    monkeypatch.setattr(pd.DataFrame, "to_csv", fail_to_csv)

    with pytest.raises(OSError, match="disk write failed"):
        write_preparation_outputs(
            layout,
            config_source=config_path,
            config_bytes=b"config",
            mc_frame=pd.DataFrame({"eventNumber": [1]}),
            data_frame=pd.DataFrame({"eventNumber": [2]}),
            cutflow_payload={"schema_version": "1.0"},
            summary_payload={"schema_version": "1.0"},
            manifest_payload={"schema_version": "1.1"},
        )

    assert layout.run_dir.exists()
    assert not (layout.artifacts_dir / "run_manifest.json").exists()
```

- [ ] **Step 5: Implement the single output writer with pre-serialization**

Add `pandas`, `json`, and the writer to `src/preparation.py`:

```python
import json

import pandas as pd


def _json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"


def write_preparation_outputs(
    layout: OutputLayout,
    *,
    config_source: Path,
    config_bytes: bytes,
    mc_frame: pd.DataFrame,
    data_frame: pd.DataFrame,
    cutflow_payload: Mapping[str, Any],
    summary_payload: Mapping[str, Any],
    manifest_payload: Mapping[str, Any],
) -> None:
    serialized_cutflow = _json_text(cutflow_payload)
    serialized_summary = _json_text(summary_payload)
    serialized_manifest = _json_text(manifest_payload)
    if config_source.read_bytes() != config_bytes:
        raise RuntimeError("config changed during preparation")
    if layout.run_dir is not None and layout.run_dir.exists():
        raise FileExistsError(f"run directory already exists: {layout.run_dir}")

    layout.processed_dir.mkdir(parents=True, exist_ok=True)
    layout.artifacts_dir.mkdir(parents=True, exist_ok=True)
    if layout.config_snapshot is not None:
        layout.config_snapshot.write_bytes(config_bytes)
    mc_frame.to_csv(layout.processed_dir / "mc_events.csv.gz", index=False)
    data_frame.to_csv(layout.processed_dir / "data_events.csv.gz", index=False)
    (layout.artifacts_dir / "cutflow.json").write_text(
        serialized_cutflow, encoding="utf-8"
    )
    (layout.artifacts_dir / "data_summary.json").write_text(
        serialized_summary, encoding="utf-8"
    )
    (layout.artifacts_dir / "run_manifest.json").write_text(
        serialized_manifest, encoding="utf-8"
    )
```

- [ ] **Step 6: Rewrite the prepare CLI integration test for full isolation**

Import `MCNormalization`, then replace the repeated test setup in `tests/test_prepare_script.py` with these exact helpers so smoke and full tests use identical sample frames:

```python
from src.weights import MCNormalization


def write_test_config_and_inputs(tmp_path):
    input_paths = {}
    for name, content in (
        ("higgs", b"synthetic-higgs-root"),
        ("zz", b"synthetic-zz-root"),
        ("data", b"synthetic-data-root"),
    ):
        path = tmp_path / f"{name}.root"
        path.write_bytes(content)
        input_paths[name] = path
    config = {
        "random_seed": 42,
        "luminosity_pb": 10000.0,
        "tree_name": "analysis",
        "momentum_unit": "GeV",
        "entry_stop": 5000,
        "chunk_size_events": 50000,
        "samples": {
            "higgs": {
                "path": str(input_paths["higgs"]),
                "channel_numbers": [345060],
                "label": 1,
            },
            "zz": {
                "path": str(input_paths["zz"]),
                "channel_numbers": [700600],
                "label": 0,
            },
            "data": {
                "path": str(input_paths["data"]),
                "period": "data16_periodA",
            },
        },
        "selection": selection_mapping(),
    }
    config_path = tmp_path / "demo.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return config_path, input_paths


def install_fake_prepare_sample(monkeypatch):
    calls = []

    def fake_prepare_sample(path, **kwargs):
        calls.append(kwargs)
        is_data = kwargs["is_data"]
        if is_data:
            frame = pd.DataFrame(
                [{
                    "runNumber": 10,
                    "eventNumber": 20,
                    "label": -1,
                    "physical_weight": 1.0,
                    "train_weight": 1.0,
                    "split": "data",
                }]
            )
            normalization = None
        else:
            label = int(kwargs["label"])
            frame = pd.DataFrame(
                [{
                    "eventNumber": 20,
                    "channelNumber": kwargs["expected_channels"][0],
                    "label": label,
                    "physical_weight": -0.5 if label == 1 else 2.0,
                    "train_weight": 1.0,
                    "split": "train",
                }]
            )
            normalization = MCNormalization(2.0, 1.0, 1.0, 100.0)
        return PreparedSample(
            frame=frame,
            cutflow={
                "sample_name": kwargs["sample_name"],
                "kind": "data" if is_data else "mc",
                "stages": {
                    "read": {"count": 2},
                    "selected": {"count": 1},
                },
            },
            normalization=normalization,
        )

    monkeypatch.setattr(prepare_demo, "prepare_sample", fake_prepare_sample)
    return calls
```

Add a full-mode test with these assertions:

```python
def test_prepare_script_full_mode_writes_only_fresh_run_directory(
    tmp_path, monkeypatch
):
    config_path, input_paths = write_test_config_and_inputs(tmp_path)
    calls = install_fake_prepare_sample(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_demo",
            "--config",
            str(config_path),
            "--full",
            "--run-dir",
            "runs/full-baseline-2026-08-10",
        ],
    )

    prepare_demo.main()

    run_dir = tmp_path / "runs/full-baseline-2026-08-10"
    assert [call["entry_stop"] for call in calls] == [None, None, None]
    assert [call["chunk_size_events"] for call in calls] == [50_000] * 3
    assert (run_dir / "config.yaml").read_bytes() == config_path.read_bytes()
    assert (run_dir / "processed/mc_events.csv.gz").exists()
    assert (run_dir / "processed/data_events.csv.gz").exists()
    assert (run_dir / "artifacts/cutflow.json").exists()
    assert (run_dir / "artifacts/data_summary.json").exists()
    manifest = json.loads((run_dir / "artifacts/run_manifest.json").read_text())
    assert manifest["schema_version"] == "1.1"
    assert manifest["processing"]["read_policy"] == {
        "mode": "full",
        "entry_stop": None,
        "chunk_size_events": 50_000,
    }
    assert set(manifest["mc_normalization"]) == {
        "higgs_345060",
        "zz_700600",
    }
    assert not (tmp_path / "data/processed").exists()
    assert not (tmp_path / "outputs").exists()
```

Refactor the existing `--output-dir artifacts` test to call these same helpers, then assert that it remains `mode: head`, writes CSVs to `data/processed`, and sets `config.snapshot_path` to `None`.

- [ ] **Step 7: Add CLI preflight tests proving ROOT preparation is not called**

```python
@pytest.mark.parametrize(
    "arguments",
    [
        ["--full"],
        ["--full", "--run-dir", "runs/full", "--output-dir", "artifacts"],
    ],
)
def test_prepare_script_preflight_errors_before_root_io(
    tmp_path, monkeypatch, arguments
):
    config_path, _ = write_test_config_and_inputs(tmp_path)
    calls = []
    monkeypatch.setattr(
        prepare_demo,
        "prepare_sample",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["prepare_demo", "--config", str(config_path), *arguments],
    )

    with pytest.raises(ValueError):
        prepare_demo.main()

    assert calls == []
    assert not (tmp_path / "runs/full").exists()
```

- [ ] **Step 8: Wire CLI resolution, payload construction, and sample progress**

In `scripts/prepare_demo.py`:

1. Change `--output-dir` to `default=None`.
2. Add `parser.add_argument("--full", action="store_true")`.
3. Add `parser.add_argument("--run-dir")`.
4. Read `config_bytes = config_path.read_bytes()` once and parse those bytes.
5. Resolve `ReadPolicy` and `OutputLayout` before calling `prepare_sample()`, passing `Path(__file__).resolve().parents[1]` as `project_root` and `Path.cwd()` as `working_directory`.
6. Pass both `entry_stop` and `chunk_size_events` to all three samples.
7. Print `prepared <sample_name>: <read> read, <selected> selected` after each sample.
8. Require `prepared.normalization is not None` for each MC sample and construct `MCNormalizationInput` values.
9. Build `cutflow_payload`, `summary_payload`, and `manifest_payload` completely before writing.
10. Call `write_preparation_outputs()` exactly once.

The manifest processing mapping must be:

```python
processing = {
    "read_policy": read_policy.as_dict(),
    "random_seed": config.get("random_seed"),
    "tree_name": config.get("tree_name"),
    "momentum_unit": config.get("momentum_unit", "MeV"),
    "selection": {"z2_min_mode": selection.z2_min_mode},
}
```

The final console line remains:

```python
print(f"prepared {len(mc)} MC events and {len(data)} data events")
```

- [ ] **Step 9: Ignore run artifacts while preserving the directory**

Append to `.gitignore`:

```gitignore
runs/*
!runs/.gitkeep
```

Create the empty file `runs/.gitkeep`.

- [ ] **Step 10: Run all preparation, provenance, and pipeline tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_preparation.py \
  tests/test_prepare_script.py \
  tests/test_io.py \
  tests/test_cutflow.py \
  tests/test_manifest.py \
  tests/test_summary.py \
  tests/test_weights.py -q
```

Expected: all focused tests pass; the full CLI test creates only its temporary run directory.

- [ ] **Step 11: Record the scoped checkpoint without staging**

Run:

```bash
git status --short -- \
  src/preparation.py \
  src/pipeline.py \
  scripts/prepare_demo.py \
  tests/test_preparation.py \
  tests/test_prepare_script.py \
  .gitignore \
  runs/.gitkeep
```

Expected: only Task 6 files appear in this checkpoint; `runs/full-baseline-2026-08-10` is not present yet.

---

### Task 7: Verify the full suite, run all ROOT entries, and freeze the aggregate baseline

**Files:**
- Create at runtime: `runs/full-baseline-2026-08-10/config.yaml`
- Create at runtime: `runs/full-baseline-2026-08-10/processed/mc_events.csv.gz`
- Create at runtime: `runs/full-baseline-2026-08-10/processed/data_events.csv.gz`
- Create at runtime: `runs/full-baseline-2026-08-10/artifacts/cutflow.json`
- Create at runtime: `runs/full-baseline-2026-08-10/artifacts/data_summary.json`
- Create at runtime: `runs/full-baseline-2026-08-10/artifacts/run_manifest.json`
- Modify after successful verification: `README.md`
- Modify after successful verification: `docs/project/overview.md`
- Modify after successful verification: `docs/roadmap/next-stage.md`
- Modify after successful verification: `AGENTS.md`

**Interfaces:**
- Consumes: the fully verified Task 1–6 implementation and the three documented ROOT inputs.
- Produces: the canonical Task 4A aggregate preprocessing baseline and documentation that clearly separates it from the historical 5,000-entry trained model.

- [ ] **Step 1: Run the complete synthetic/unit regression before touching real ROOT**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: all tests pass. Record the exact passed-test count for the documentation update.

- [ ] **Step 2: Verify input identity and confirm the target run is fresh**

Run:

```bash
shasum -a 256 \
  data/raw/higgs.root \
  data/raw/zz.root \
  data/raw/data16_periodA.root
test ! -e runs/full-baseline-2026-08-10
```

Expected hashes, in order:

```text
5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0
3d7588b897fc50a2342ef1d7b10f8c1b34f035456b2af215f62ad92525422789
adc3236398d1b6175438c9b5f77f540f3e1a377d628899156030b0bd3e0042cb
```

- [ ] **Step 3: Snapshot pre-existing raw, processed, and output metadata**

Run on macOS:

```bash
find data/raw data/processed outputs -type f -exec stat -f '%N|%z|%m' {} \; \
  | sort > /tmp/higgs-task4a-before.txt
```

Expected: the file lists the existing paths, byte sizes, and modification times without modifying them.

- [ ] **Step 4: Execute the approved full preprocessing command**

Run:

```bash
.venv/bin/python -m scripts.prepare_demo \
  --config config/demo.yaml \
  --full \
  --run-dir runs/full-baseline-2026-08-10
```

Expected: three sample-level completion lines followed by the combined MC/data selected-row line. Do not run training or evaluation commands.

If the command fails, report the last printed sample/stage, leave any newly created incomplete run directory untouched, and stop this task without changing `entry_stop` or falling back to a prefix read.

- [ ] **Step 5: Validate only aggregate counts, hashes, schemas, and allowed files**

Run:

```bash
.venv/bin/python - <<'PY'
import gzip
import hashlib
import json
import math
from pathlib import Path

run = Path("runs/full-baseline-2026-08-10")
artifacts = run / "artifacts"
cutflow = json.loads((artifacts / "cutflow.json").read_text())
summary = json.loads((artifacts / "data_summary.json").read_text())
manifest = json.loads((artifacts / "run_manifest.json").read_text())

expected_read = {
    "higgs_345060": 419943,
    "zz_700600": 11260,
    "data16_periodA": 29275,
}
expected_input_hashes = {
    "higgs_345060": "5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0",
    "zz_700600": "3d7588b897fc50a2342ef1d7b10f8c1b34f035456b2af215f62ad92525422789",
    "data16_periodA": "adc3236398d1b6175438c9b5f77f540f3e1a377d628899156030b0bd3e0042cb",
}
for name, expected in expected_read.items():
    actual = cutflow["samples"][name]["stages"]["read"]["count"]
    assert actual == expected, (name, actual, expected)

def csv_rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return sum(1 for _ in stream) - 1

mc_selected = sum(
    summary["mc"][name]["selected_events"]
    for name in ("higgs_345060", "zz_700600")
)
data_selected = summary["data"]["data16_periodA"]["selected_events"]
assert csv_rows(run / "processed/mc_events.csv.gz") == mc_selected
assert csv_rows(run / "processed/data_events.csv.gz") == data_selected
assert summary["data"]["data16_periodA"]["duplicate_run_event_pairs"] == 0
assert manifest["schema_version"] == "1.1"
assert cutflow["schema_version"] == "1.0"
assert summary["schema_version"] == "1.0"
assert manifest["processing"]["read_policy"] == {
    "mode": "full",
    "entry_stop": None,
    "chunk_size_events": 50000,
}
source_hash = hashlib.sha256(Path("config/demo.yaml").read_bytes()).hexdigest()
snapshot_hash = hashlib.sha256((run / "config.yaml").read_bytes()).hexdigest()
assert source_hash == snapshot_hash == manifest["config"]["sha256"]
assert manifest["config"]["snapshot_path"] == str(run / "config.yaml")
for name, expected_hash in expected_input_hashes.items():
    assert manifest["inputs"][name]["sha256"] == expected_hash
assert set(manifest["mc_normalization"]) == {"higgs_345060", "zz_700600"}
for name, values in manifest["mc_normalization"].items():
    for key in (
        "luminosity_pb",
        "xsec_pb",
        "k_factor",
        "filter_efficiency",
        "sum_of_weights",
        "effective_cross_section_pb",
    ):
        assert math.isfinite(float(values[key])), (name, key)
for name, values in summary["mc"].items():
    for key in (
        "signed_sum_physical_weights",
        "absolute_sum_physical_weights",
        "negative_weight_fraction",
    ):
        assert math.isfinite(float(values[key])), (name, key)
    assert isinstance(values["negative_weight_events"], int), name
assert manifest["outputs"]["locations"] == {
    "run_dir": str(run),
    "processed_dir": str(run / "processed"),
    "artifacts_dir": str(run / "artifacts"),
}

allowed = {
    "config.yaml",
    "processed/mc_events.csv.gz",
    "processed/data_events.csv.gz",
    "artifacts/cutflow.json",
    "artifacts/data_summary.json",
    "artifacts/run_manifest.json",
}
actual = {
    str(path.relative_to(run)) for path in run.rglob("*") if path.is_file()
}
assert actual == allowed, (actual, allowed)
print(json.dumps({
    "read_events": expected_read,
    "selected_mc_events": mc_selected,
    "selected_data_events": data_selected,
    "duplicate_data_events": 0,
}, indent=2))
PY
```

Expected: all assertions pass and only aggregate event counts are printed. This script deliberately never reads or prints `m4l`, classifier scores, or event identities.

- [ ] **Step 6: Prove legacy files were not modified**

Run:

```bash
find data/raw data/processed outputs -type f -exec stat -f '%N|%z|%m' {} \; \
  | sort > /tmp/higgs-task4a-after.txt
cmp /tmp/higgs-task4a-before.txt /tmp/higgs-task4a-after.txt
```

Expected: `cmp` exits with status 0 and prints nothing.

- [ ] **Step 7: Update the four durable project documents with verified facts**

Apply these content changes using the values printed in Step 5 and the passed-test count from Step 1:

- `README.md`: replace the old overwrite warning with separate smoke and full commands; show the six-file run layout; state that full mode requires a fresh run directory and does not train or score.
- `docs/project/overview.md`: label 4,884/4,685/1,112 and all AUC/threshold metrics as the historical 5,000-entry model; add a Task 4A table containing `419943`, `11260`, `29275`, and the three verified selected counts; describe manifest 1.1 and MC normalization.
- `docs/roadmap/next-stage.md`: mark full preprocessing and normalization validation complete as Task 4A; make class-balance/training policy Task 4B; leave data-period expansion and model work unclaimed.
- `AGENTS.md`: update the test count, add the full-run command and run path, record the aggregate counts, state that legacy artifacts were unchanged, and retain the prohibition on interpreting Task 4A as a new trained result.

Use this exact safety wording in both `README.md` and `AGENTS.md`:

```text
Task 4A processes and records the full inputs only. It does not retrain XGBoost,
choose a new threshold, score real data, or inspect the blinded real-data mass region.
```

- [ ] **Step 8: Run final verification after documentation edits**

Run:

```bash
.venv/bin/python -m pytest -q
rg -n "Task 4A|full-baseline-2026-08-10|419943|11260|29275" \
  README.md AGENTS.md docs/project/overview.md docs/roadmap/next-stage.md
git status --short --untracked-files=all -- .
```

Expected: the full test suite passes; every durable document identifies the same run and full input counts; no ROOT file, legacy processed artifact, legacy output, model, or plot appears as a new source change.

- [ ] **Step 9: Report the frozen baseline without claiming a trained result**

The handoff must state:

```text
- full input counts for Higgs, ZZ, and data;
- selected aggregate counts and zero/nonzero duplicate status;
- manifest/config/input hash verification status;
- legacy-file immutability verification status;
- exact pytest result;
- Task 4B (training class-balance policy) remains separate and unimplemented;
- no event-level real-data mass or score information was inspected.
```

Do not stage or commit because the parent repository still has no initial `HEAD` and initializing project history is outside Task 4A.
