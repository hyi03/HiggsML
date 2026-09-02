"""MC-only ROOT reader with before/after source binding."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from numbers import Integral
from pathlib import Path
import stat
from typing import Any, Iterable

from .profiles import InputProfile, resolve_input_profile


COMMON_BRANCHES = (
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
)
NORMALIZATION_BRANCHES = ("xsec", "kfac", "filteff", "sum_of_weights")


@dataclass(frozen=True)
class InputReceipt:
    path: str
    device: int
    inode: int
    size_bytes: int
    mtime_ns: int
    sha256: str

    def as_dict(self) -> dict[str, int | str]:
        return asdict(self)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_mc_input(path: str | Path) -> InputReceipt:
    source = Path(path).absolute()
    if source.suffix.lower() != ".root":
        raise ValueError("MC input must use the .root suffix")
    if source.is_symlink():
        raise ValueError("symlink MC inputs are not allowed")
    try:
        metadata = source.lstat()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"MC input does not exist: {source}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("MC input must be a regular file")
    resolved = source.resolve(strict=True)
    return InputReceipt(
        path=str(resolved),
        device=int(metadata.st_dev),
        inode=int(metadata.st_ino),
        size_bytes=int(metadata.st_size),
        mtime_ns=int(metadata.st_mtime_ns),
        sha256=_sha256(resolved),
    )


def verify_mc_input(receipt: InputReceipt) -> None:
    current = inspect_mc_input(receipt.path)
    if current != receipt:
        raise RuntimeError(f"MC input changed while being read: {receipt.path}")


def _import_uproot():
    try:
        import uproot
    except ImportError as exc:
        raise RuntimeError("uproot is required to read ROOT files") from exc
    return uproot


def _tree(root_file: Any, requested_name: str):
    try:
        return root_file[requested_name]
    except KeyError as exc:
        raise KeyError(f"missing required ROOT tree: {requested_name}") from exc


def iter_mc_events(
    path: str | Path,
    *,
    tree_name: str,
    chunk_size_events: int,
    profile: InputProfile | str,
    extra_canonical_branches: Iterable[str] = (),
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
    if tree_name != resolved_profile.tree_name:
        raise ValueError("tree_name does not match the frozen input profile")

    requested_canonical = list(COMMON_BRANCHES)
    for name in extra_canonical_branches:
        if name not in resolved_profile.branches:
            raise KeyError(f"unknown canonical branch: {name}")
        if name not in requested_canonical:
            requested_canonical.append(name)
    if "mcWeight" not in requested_canonical:
        requested_canonical.append("mcWeight")
    if resolved_profile.normalization_in_events:
        for name in NORMALIZATION_BRANCHES:
            if name not in requested_canonical:
                requested_canonical.append(name)
    missing_profile = [
        name for name in requested_canonical if name not in resolved_profile.branches
    ]
    if missing_profile:
        raise KeyError(f"profile is missing canonical branches: {missing_profile}")
    physical_names = [resolved_profile.branches[name] for name in requested_canonical]

    uproot = _import_uproot()
    with uproot.open(path) as root_file:
        tree = _tree(root_file, tree_name)
        available = set(tree.keys())
        missing = [name for name in physical_names if name not in available]
        if missing:
            raise KeyError(f"missing required branches: {missing}")
        for arrays in tree.iterate(
            physical_names,
            step_size=int(chunk_size_events),
            library="ak",
        ):
            for index in range(len(arrays)):
                event: dict[str, Any] = {}
                for canonical, physical in zip(
                    requested_canonical, physical_names, strict=True
                ):
                    value = arrays[physical][index]
                    event[canonical] = (
                        value.to_list() if hasattr(value, "to_list") else value
                    )
                yield event


def validate_channel_numbers(
    observed: Iterable[int], expected: Iterable[int], sample_name: str
) -> None:
    observed_set = {int(value) for value in observed}
    expected_set = {int(value) for value in expected}
    if not expected_set:
        raise ValueError(f"{sample_name}: channel_numbers must not be empty")
    unexpected = observed_set - expected_set
    if unexpected:
        raise ValueError(
            f"{sample_name}: ROOT contains unconfigured channelNumber(s): "
            f"{sorted(unexpected)}"
        )
