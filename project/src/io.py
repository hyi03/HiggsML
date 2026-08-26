from __future__ import annotations

from numbers import Integral
from pathlib import Path
from typing import Any, Iterable

from .input_profiles import InputProfile, resolve_input_profile

COMMON_BRANCHES = [
    "runNumber",
    "eventNumber",
    "channelNumber",
    "lep_n",
    "lep_pt",
    "lep_eta",
    "lep_phi",
    "lep_e",
    "lep_charge",
    "lep_type",
]
MC_BRANCHES = [
    "mcWeight",
    "xsec",
    "kfac",
    "filteff",
    "sum_of_weights",
]
NORMALIZATION_BRANCHES = MC_BRANCHES[1:]


def _import_uproot():
    try:
        import uproot
    except ImportError as exc:
        raise RuntimeError("uproot is required to read ROOT files") from exc
    return uproot


def discover_tree(root_file, requested_name: str | None = None):
    if requested_name:
        return root_file[requested_name]
    for _, obj in root_file.items():
        if hasattr(obj, "num_entries") and hasattr(obj, "keys"):
            return obj
    raise ValueError("no TTree found in ROOT file")


def inspect_root(path: str | Path, tree_name: str | None = None) -> dict[str, Any]:
    uproot = _import_uproot()
    with uproot.open(path) as root_file:
        tree = discover_tree(root_file, tree_name)
        return {
            "file_keys": [str(key) for key in root_file.keys()],
            "tree_name": str(tree.name),
            "num_entries": int(tree.num_entries),
            "branches": [str(key) for key in tree.keys()],
        }


def iter_events(
    path: str | Path,
    tree_name: str | None = None,
    *,
    is_data: bool,
    entry_stop: int | None = None,
    chunk_size_events: int = 50_000,
    profile: InputProfile | str = "release22",
    extra_canonical_branches: Iterable[str] = (),
    include_source_entry: bool = False,
) -> Iterable[dict[str, Any]]:
    if (
        isinstance(chunk_size_events, bool)
        or not isinstance(chunk_size_events, Integral)
        or chunk_size_events <= 0
    ):
        raise ValueError("chunk_size_events must be a positive integer")

    resolved_profile = (
        profile if isinstance(profile, InputProfile) else resolve_input_profile(profile)
    )
    extra = tuple(extra_canonical_branches)
    if "source_entry" in extra:
        raise ValueError("source_entry is a generated identity, not a ROOT branch")
    unknown = [name for name in extra if name not in resolved_profile.branches]
    if unknown:
        raise KeyError(f"unknown canonical branches: {unknown}")

    requested_canonical = list(COMMON_BRANCHES)
    for name in extra:
        if name not in requested_canonical:
            requested_canonical.append(name)
    if not is_data:
        if "mcWeight" not in requested_canonical:
            requested_canonical.append("mcWeight")
        if resolved_profile.normalization_in_events:
            for name in NORMALIZATION_BRANCHES:
                if name not in requested_canonical:
                    requested_canonical.append(name)
    missing_canonical = [
        name for name in requested_canonical if name not in resolved_profile.branches
    ]
    if missing_canonical:
        raise KeyError(f"profile is missing canonical branches: {missing_canonical}")
    requested = [resolved_profile.branches[name] for name in requested_canonical]

    uproot = _import_uproot()
    with uproot.open(path) as root_file:
        tree = discover_tree(root_file, tree_name or resolved_profile.tree_name)
        available = set(tree.keys())
        missing = [name for name in requested if name not in available]
        if missing:
            raise KeyError(f"missing required branches: {missing}")
        source_entry = 0
        for arrays in tree.iterate(
            requested,
            entry_stop=entry_stop,
            step_size=int(chunk_size_events),
            library="ak",
        ):
            for index in range(len(arrays)):
                event = {}
                for canonical, physical in zip(requested_canonical, requested):
                    value = arrays[physical][index]
                    event[canonical] = (
                        value.to_list() if hasattr(value, "to_list") else value
                    )
                if include_source_entry:
                    event["source_entry"] = source_entry
                source_entry += 1
                yield event


def validate_channel_numbers(
    observed: Iterable[int], expected: Iterable[int], sample_name: str
) -> None:
    observed_set = {int(value) for value in observed}
    expected_set = {int(value) for value in expected}
    if not expected_set:
        raise ValueError(
            f"{sample_name}: channel_numbers is empty; verify it against official metadata"
        )
    unexpected = observed_set - expected_set
    if unexpected:
        raise ValueError(
            f"{sample_name}: ROOT contains unconfigured channelNumber(s): {sorted(unexpected)}"
        )
