from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

import src.preprocessing.authority as authority
from src.config import load_preprocess_protocol
from src.preprocessing.authority import (
    AuthorityGateError,
    compare_tables,
    require_authority_platform,
    run_authority_gate,
)


NEURAL = Path(__file__).resolve().parents[2]
REPOSITORY = NEURAL.parent


def test_old_mixed_golden_is_not_used():
    protocol=load_preprocess_protocol(NEURAL/"config/preprocess_protocol_v2.yaml",dataset="atlas2020_4lep")
    assert "golden" not in protocol.raw


def test_no_reference_refuses_instead_of_self_certifying(tmp_path,monkeypatch):
    monkeypatch.setattr(authority,"require_authority_platform",lambda:None)
    with pytest.raises(AuthorityGateError,match="no independently registered reference"):
        run_authority_gate(repository_root=REPOSITORY,new_run_dir=tmp_path/"new",
                           evidence_path=tmp_path/"evidence.json",dataset="atlas2020_4lep")
    assert not (tmp_path/"evidence.json").exists()


def test_authority_platform_refuses_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.preprocessing.authority.platform.system", lambda: "Windows")
    monkeypatch.setattr("src.preprocessing.authority.platform.machine", lambda: "AMD64")

    with pytest.raises(AuthorityGateError, match="authoritative_gate_not_run"):
        require_authority_platform()


def test_table_comparator_uses_exact_structure_and_approved_float_tolerance(
    tmp_path: Path,
) -> None:
    protocol = load_preprocess_protocol(NEURAL / "config/preprocess_protocol_v2.yaml", dataset="atlas2020_4lep")
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
