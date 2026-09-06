from pathlib import Path
import json

import pytest

from src.config import InputBindingError
from src.dataset_binding import dataset_context, validate_frame_identity
from src.training.development_reader import read_development_input
from src.training.development import execute_development
from src.training.test_opening import execute_test_opening
from src.training.dataset import build_validated_fold, validate_development_frame
from tests.development_fixtures import write_synthetic_preprocess_run
from tests.integration.test_development_run import _install_fast_pipeline, PROTOCOL


@pytest.mark.parametrize("dataset", ["atlas2020_4lep", "atlas2025_exactly4lep"])
def test_development_never_opens_test_partition(tmp_path, monkeypatch, dataset):
    root = tmp_path / "runs"
    run, _ = write_synthetic_preprocess_run(root, dataset=dataset)
    original = Path.open

    def guarded(path, *args, **kwargs):
        assert path.name != "test_events.csv.gz", "development accessed test file"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    loaded = read_development_input(run, dataset=dataset, allowed_root=root, protocol_sha256="a" * 64)
    assert loaded.held_out_test_rows == 6
    assert loaded.development.dataset_binding == dataset_context(dataset).snapshot()


@pytest.mark.parametrize("field,value", [("source_sample", "zz_700600"), ("label", 1),
                                       ("source_file_id", "another-file"), ("channelNumber", 700600),
                                       ("event_group_id", "changed")])
def test_frame_member_identity_cannot_be_relabelled(tmp_path, field, value):
    root = tmp_path / "runs"
    _, frame = write_synthetic_preprocess_run(root)
    frame = frame.loc[frame.split != "test"].copy()
    index = frame.loc[frame.label == 0].index[0]
    frame.loc[index, field] = value
    with pytest.raises(InputBindingError):
        validate_frame_identity(frame, dataset_context("atlas2020_4lep").snapshot())


def test_wrong_dataset_refuses_before_numeric_decode(tmp_path, monkeypatch):
    root = tmp_path / "runs"
    run, _ = write_synthetic_preprocess_run(root)
    monkeypatch.setattr("src.training.development_reader._decode_development_rows",
                        lambda *a: pytest.fail("mismatch must fail before features"))
    with pytest.raises(InputBindingError, match="dataset binding mismatch"):
        read_development_input(run, dataset="atlas2025_exactly4lep", allowed_root=root, protocol_sha256="a" * 64)


def test_unsealed_preprocess_protocol_refuses_before_decode(tmp_path, monkeypatch):
    root = tmp_path / "runs"
    run, _ = write_synthetic_preprocess_run(root)
    path = run / "artifacts/manifest.json"
    manifest = json.loads(path.read_bytes())
    manifest["configuration"]["protocol_sha256"] = "f" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr("src.training.development_reader._decode_development_rows",
                        lambda *a: pytest.fail("unsealed protocol must fail before features"))
    with pytest.raises(InputBindingError, match="manifest binding changed"):
        read_development_input(run, dataset="atlas2020_4lep", allowed_root=root, protocol_sha256="a" * 64)


def test_debug_flag_accepts_unsealed_preprocess_protocol_without_filename_rules(tmp_path):
    root = tmp_path / "runs"
    run, _ = write_synthetic_preprocess_run(root)
    path = run / "artifacts/manifest.json"
    manifest = json.loads(path.read_bytes())
    manifest["protocol_id"] = "local-preprocess-experiment"
    manifest["configuration"]["protocol_path"] = "config/arbitrary-name.yaml"
    manifest["configuration"]["protocol_sha256"] = "debug-protocol-without-sha"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    from src.training.development_reader import _read_manifest
    loaded, _ = _read_manifest(run, debug=True)
    assert loaded["protocol_id"] == "local-preprocess-experiment"


def test_model_dataset_mismatch_refuses_before_claim(tmp_path, monkeypatch):
    root = tmp_path / "runs"
    pre, _ = write_synthetic_preprocess_run(root)
    _install_fast_pipeline(monkeypatch, eligible_lambda=0.05)
    development = root / "development"
    execute_development(dataset="atlas2020_4lep", input_run=pre, protocol_path=PROTOCOL,
                        run_dir=development, allowed_root=root)
    with pytest.raises(InputBindingError, match="dataset binding mismatch"):
        execute_test_opening(dataset="atlas2025_exactly4lep", development_run=development,
            run_dir=root / "wrong-test", allowed_root=root, authorization_reference="DATASET-TEST")
    assert not (development / "state").exists()


def test_test_partition_tampering_is_checked_only_after_claim(tmp_path, monkeypatch):
    from src.config import TestOpeningFailure
    root = tmp_path / "runs"
    pre, _ = write_synthetic_preprocess_run(root)
    _install_fast_pipeline(monkeypatch, eligible_lambda=0.05)
    dev = root / "development"
    execute_development(dataset="atlas2020_4lep", input_run=pre, protocol_path=PROTOCOL,
                        run_dir=dev, allowed_root=root)
    test = pre / "processed/test_events.csv.gz"
    test.write_bytes(test.read_bytes() + b"changed")
    with pytest.raises(TestOpeningFailure) as failure:
        execute_test_opening(dataset="atlas2020_4lep", development_run=dev,
            run_dir=root / "test", allowed_root=root, authorization_reference="DATASET-TEST")
    assert failure.value.exit_code == 3
    state = json.loads((dev / "state/test_opening.json").read_bytes())
    assert state["terminal_receipt"] is True
    assert state["dataset_binding"]["dataset_name"] == "atlas2020_4lep"


def test_physical_group_overlap_rejected_even_with_distinct_source_rows(tmp_path):
    import numpy as np
    root = tmp_path / "runs"
    pre, _ = write_synthetic_preprocess_run(root)
    loaded = read_development_input(pre, dataset="atlas2020_4lep", allowed_root=root, protocol_sha256="a" * 64)
    frame = loaded.development.frame
    frame.loc[1, "event_group_id"] = frame.loc[0, "event_group_id"]
    # Bypass input validation to exercise the fold defense independently.
    development = validate_development_frame(frame, protocol_sha256="a" * 64)
    with pytest.raises(InputBindingError, match="physical group overlap"):
        build_validated_fold(development, np.array([0]), np.arange(1, len(frame)), fold_index=0)
