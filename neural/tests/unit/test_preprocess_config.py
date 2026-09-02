from __future__ import annotations

from pathlib import Path
import copy

import pytest
import yaml

from src.config import InputBindingError, load_preprocess_protocol, load_preprocess_run_config


PROJECT = Path(__file__).resolve().parents[2]


def test_checked_in_protocol_freezes_scientific_contract() -> None:
    protocol = load_preprocess_protocol(PROJECT / "config/preprocess_protocol_v1.yaml")

    assert protocol.protocol_id == "higgsml-preprocess-v1"
    assert tuple(protocol.samples) == ("higgs", "zz")
    assert protocol.samples["higgs"].tree_name == "analysis"
    assert protocol.samples["zz"].tree_name == "mini"
    assert protocol.samples["zz"].dsid == 363490
    assert protocol.samples["higgs"].expected_entry_count == 419943
    assert protocol.selection["m4l_window_gev"] == [105.0, 160.0]
    assert protocol.output_columns[-5:] == (
        "source_sample", "source_entry", "runNumber", "eventNumber", "channelNumber"
    )
    assert protocol.float_rtol == protocol.float_atol == 1e-12
    assert protocol.raw["selection"]["z2_min_mode"] == "fixed"
    assert protocol.raw["split"]["test_buckets"] == [8, 9]
    assert protocol.raw["serialization"]["gzip_mtime"] == 0


def test_run_config_accepts_only_paths_and_chunk_size(tmp_path: Path) -> None:
    path = tmp_path / "run.yaml"
    path.write_text(
        "schema_version: '1.0'\n"
        "samples:\n  higgs: {path: /inputs/higgs.root}\n"
        "  zz: {path: /inputs/zz_363490.root}\n"
        "resources: {chunk_size_events: 17}\n",
        encoding="utf-8",
    )

    config = load_preprocess_run_config(path)

    assert config.chunk_size_events == 17
    assert tuple(config.sample_paths) == ("higgs", "zz")


@pytest.mark.parametrize(
    "extra",
    [
        "data: {path: /inputs/data.root}",
        "zz700600: {path: /inputs/zz.root}",
    ],
)
def test_run_config_rejects_unknown_sample(tmp_path: Path, extra: str) -> None:
    path = tmp_path / "run.yaml"
    path.write_text(
        "schema_version: '1.0'\n"
        "samples:\n  higgs: {path: /inputs/higgs.root}\n"
        "  zz: {path: /inputs/zz_363490.root}\n"
        f"  {extra}\nresources: {{chunk_size_events: 17}}\n",
        encoding="utf-8",
    )

    with pytest.raises(InputBindingError, match="samples"):
        load_preprocess_run_config(path)


def test_duplicate_yaml_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "run.yaml"
    path.write_text(
        "schema_version: '1.0'\nschema_version: '1.0'\n"
        "samples:\n  higgs: {path: a}\n  zz: {path: b}\n"
        "resources: {chunk_size_events: 1}\n",
        encoding="utf-8",
    )

    with pytest.raises(InputBindingError, match="duplicate"):
        load_preprocess_run_config(path)


def test_protocol_rejects_changed_scientific_rule(tmp_path: Path) -> None:
    source = PROJECT / "config/preprocess_protocol_v1.yaml"
    changed = tmp_path / "protocol.yaml"
    changed.write_text(
        source.read_text(encoding="utf-8").replace(
            "m4l_window_gev: [105.0, 160.0]", "m4l_window_gev: [104.0, 160.0]"
        ),
        encoding="utf-8",
    )

    with pytest.raises(InputBindingError, match="selection protocol changed"):
        load_preprocess_protocol(changed)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("luminosity_pb",), 5000.0, "luminosity"),
        (("output_columns", 8), "mZ2", "output columns"),
        (("samples", "zz", "normalization", "xsec_pb"), 9.9, "sample binding"),
        (("samples", "higgs", "branches", "lep_track_iso"), "lep_topoetcone20", "sample binding"),
        (("split", "modulo"), 100, "split protocol"),
        (("serialization", "float_format"), ".12g", "serialization protocol"),
        (("golden", "table_path"), "wrong.csv.gz", "golden authority"),
    ],
)
def test_protocol_rejects_any_frozen_contract_drift(
    tmp_path: Path, path: tuple[object, ...], value: object, message: str
) -> None:
    raw = yaml.safe_load(
        (PROJECT / "config/preprocess_protocol_v1.yaml").read_text(encoding="utf-8")
    )
    changed = copy.deepcopy(raw)
    target = changed
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    destination = tmp_path / "protocol.yaml"
    destination.write_text(yaml.safe_dump(changed, sort_keys=False), encoding="utf-8")

    with pytest.raises(InputBindingError, match=message):
        load_preprocess_protocol(destination)
