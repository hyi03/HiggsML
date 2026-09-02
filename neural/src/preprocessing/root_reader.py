from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import awkward as ak
import uproot

from src.config import InputBindingError, SampleProtocol


def iter_events(
    path: str | Path,
    sample: SampleProtocol,
    chunk_size_events: int,
    *,
    verify_entry_count: bool = True,
) -> Iterator[dict[str, Any]]:
    source = Path(path)
    try:
        with uproot.open(source) as root:
            tree = root[sample.tree_name]
            physical = tuple(sample.branches.values())
            available = {str(name) for name in tree.keys()}
            missing = set(physical) - available
            if missing:
                raise InputBindingError(
                    f"missing ROOT branches for {sample.source_sample}: {sorted(missing)}"
                )
            if "source_entry" in available:
                raise InputBindingError("source_entry must be generated, not read from ROOT")
            extra = available - set(physical)
            if extra:
                raise InputBindingError(
                    f"undeclared ROOT branches for {sample.source_sample}: {sorted(extra)}"
                )
            source_entry = 0
            for arrays in tree.iterate(
                expressions=list(physical), step_size=chunk_size_events, library="ak"
            ):
                length = len(arrays)
                for offset in range(length):
                    event = {
                        canonical: ak.to_list(arrays[branch][offset])
                        for canonical, branch in sample.branches.items()
                    }
                    event["source_entry"] = source_entry + offset
                    yield event
                source_entry += length
            if verify_entry_count and source_entry != sample.expected_entry_count:
                raise InputBindingError(
                    f"entry count mismatch for {sample.source_sample}: "
                    f"{source_entry} != {sample.expected_entry_count}"
                )
    except InputBindingError:
        raise
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise InputBindingError(f"ROOT schema/read failure for {sample.source_sample}") from error
