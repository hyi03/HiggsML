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
        assert name == self.tree.name
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


def test_open_data_profile_renames_external_branches_to_canonical_names(monkeypatch):
    canonical = event_columns([1], is_data=True)
    canonical.update(
        {
            "channelNumber": [363490],
            "trigE": [True],
            "trigM": [False],
            "lep_isTrigMatched": [[True, False, True, False]],
            "lep_isTightID": [[True, True, True, True]],
            "lep_track_iso": [[1.0, 2.0, 3.0, 4.0]],
            "lep_calo_iso": [[1.0, 2.0, 3.0, 4.0]],
            "lep_d0sig": [[0.1, 0.2, 0.3, 0.4]],
            "lep_z0": [[0.1, 0.2, 0.3, 0.4]],
            "mcWeight": [-2.0],
        }
    )
    old_names = {
        "lep_e": "lep_E",
        "lep_isTrigMatched": "lep_trigMatched",
        "lep_track_iso": "lep_ptcone30",
        "lep_calo_iso": "lep_etcone20",
        "lep_d0sig": "lep_tracksigd0pvunbiased",
    }
    columns = {
        old_names.get(name, name): values for name, values in canonical.items()
    }
    chunk = FakeChunk(columns)
    tree = FakeTree([chunk], columns)
    tree.name = "mini"
    install_fake_uproot(monkeypatch, tree)

    events = list(
        io.iter_events(
            "fake.root",
            is_data=False,
            profile="open_data_2020",
            extra_canonical_branches=(
                "trigE",
                "trigM",
                "lep_isTrigMatched",
                "lep_isTightID",
                "lep_track_iso",
                "lep_calo_iso",
                "lep_d0sig",
                "lep_z0",
            ),
        )
    )

    expected_event = {name: values[0] for name, values in canonical.items()}
    assert events == [expected_event]
    assert tree.calls == [
        (
            [
                "runNumber",
                "eventNumber",
                "channelNumber",
                "lep_n",
                "lep_pt",
                "lep_eta",
                "lep_phi",
                "lep_E",
                "lep_charge",
                "lep_type",
                "trigE",
                "trigM",
                "lep_trigMatched",
                "lep_isTightID",
                "lep_ptcone30",
                "lep_etcone20",
                "lep_tracksigd0pvunbiased",
                "lep_z0",
                "mcWeight",
            ],
            {"entry_stop": None, "step_size": 50000, "library": "ak"},
        )
    ]
    assert events[0]["channelNumber"] == 363490


def test_iter_events_rejects_unknown_extra_canonical_branch(monkeypatch):
    chunk = FakeChunk(event_columns([1], is_data=True))
    tree = FakeTree([chunk], chunk.fields)
    install_fake_uproot(monkeypatch, tree)

    with pytest.raises(KeyError, match="unknown canonical branches"):
        list(
            io.iter_events(
                "fake.root",
                is_data=True,
                extra_canonical_branches=("does_not_exist",),
            )
        )


@pytest.mark.parametrize(
    ("profile", "tree_name", "extra_canonical_branches", "expected_requested"),
    [
        (
            "open_data_2020",
            "mini",
            ("mcWeight",),
            [
                "lep_E" if branch == "lep_e" else branch
                for branch in io.COMMON_BRANCHES
            ]
            + ["mcWeight"],
        ),
        (
            "release22",
            "analysis",
            tuple(io.MC_BRANCHES),
            io.COMMON_BRANCHES + io.MC_BRANCHES,
        ),
    ],
)
def test_iter_events_requests_duplicate_mandatory_extra_branches_once(
    monkeypatch, profile, tree_name, extra_canonical_branches, expected_requested
):
    columns = event_columns([1], is_data=False)
    if profile == "open_data_2020":
        columns["lep_E"] = columns.pop("lep_e")
        for field in io.MC_BRANCHES[1:]:
            columns.pop(field)
    chunk = FakeChunk(columns)
    tree = FakeTree([chunk], columns)
    tree.name = tree_name
    install_fake_uproot(monkeypatch, tree)

    list(
        io.iter_events(
            "fake.root",
            is_data=False,
            profile=profile,
            extra_canonical_branches=extra_canonical_branches,
        )
    )

    requested = tree.calls[0][0]
    assert requested == expected_requested
    assert len(requested) == len(set(requested))
