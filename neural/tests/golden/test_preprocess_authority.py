from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from src.config import load_preprocess_protocol
from src.preprocessing.authority import (
    AuthorityGateError,
    compare_tables,
    require_authority_platform,
)


NEURAL = Path(__file__).resolve().parents[2]
REPOSITORY = NEURAL.parent


def test_authority_contract_is_pinned() -> None:
    protocol = load_preprocess_protocol(NEURAL / "config/preprocess_protocol_v1.yaml")
    golden = protocol.raw["golden"]

    assert golden["authoritative_platform"] == "osx-arm64"
    assert golden["table_sha256"] == (
        "bc31f4e65ccecc0a1962648cfe240b67d8ecc6df8eda2478b3f46c93d2f34f09"
    )
    assert golden["identity_manifest_sha256"] == (
        "74ebc01ee452bf2f6a7a792d14ed1a62eefefffc6bb090a498fb76abe20273a0"
    )
    assert golden["baseline_manifest_sha256"] == (
        "10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8"
    )
    assert golden["expected_counts"]["total"]["selected"] == 199104
    assert golden["expected_legacy_duplicates"] == {"groups": 2, "rows": 4}
    assert golden["float_rtol"] == golden["float_atol"] == 1e-12
    assert golden["structural_exact"] is True


def test_external_r3_table_hash_when_available() -> None:
    protocol = load_preprocess_protocol(NEURAL / "config/preprocess_protocol_v1.yaml")
    golden = protocol.raw["golden"]
    path = REPOSITORY / golden["table_path"]
    if not path.exists():
        pytest.skip("authoritative_gate_not_run: external r3-ARM64 table is absent")

    assert hashlib.sha256(path.read_bytes()).hexdigest() == golden["table_sha256"]


def test_authority_platform_refuses_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.preprocessing.authority.platform.system", lambda: "Windows")
    monkeypatch.setattr("src.preprocessing.authority.platform.machine", lambda: "AMD64")

    with pytest.raises(AuthorityGateError, match="authoritative_gate_not_run"):
        require_authority_platform()


def test_table_comparator_uses_exact_structure_and_approved_float_tolerance(
    tmp_path: Path,
) -> None:
    protocol = load_preprocess_protocol(NEURAL / "config/preprocess_protocol_v1.yaml")
    row = {name: 1.0 for name in protocol.output_columns}
    row.update(
        label=1, source_entry=0, runNumber=284500, eventNumber=1,
        channelNumber=345060, split="train", source_sample="higgs_345060",
    )
    golden_row = dict(row)
    golden_row["mZ1"] += 9.66e-13
    new_path, golden_path = tmp_path / "new.csv.gz", tmp_path / "golden.csv.gz"
    pd.DataFrame([row], columns=protocol.output_columns).to_csv(
        new_path, index=False, compression="gzip"
    )
    legacy_columns = list(protocol.output_columns) + [
        "mcWeight", "xsec", "kfac", "filteff", "sum_of_weights"
    ]
    pd.DataFrame([{**golden_row, **{name: 1.0 for name in legacy_columns[-5:]}}],
                 columns=legacy_columns).to_csv(golden_path, index=False, compression="gzip")

    assert compare_tables(
        new_path, golden_path, protocol.output_columns,
        rtol=1e-12, atol=1e-12,
    ) == 1

    changed = pd.read_csv(golden_path)
    changed.loc[0, "eventNumber"] = 2
    changed.to_csv(golden_path, index=False, compression="gzip")
    with pytest.raises(AuthorityGateError, match="exact integer"):
        compare_tables(
            new_path, golden_path, protocol.output_columns,
            rtol=1e-12, atol=1e-12,
        )
