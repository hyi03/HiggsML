from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.config import (
    ANGULAR19,
    load_preprocessing_protocol,
    load_preprocessing_run_config,
    load_xgboost_protocol,
)


def test_checked_in_protocols_are_strict_and_complete() -> None:
    preprocessing = load_preprocessing_protocol("config/preprocessing_protocol_v1.yaml")
    training = load_xgboost_protocol("config/xgboost_protocol_v1.yaml")
    assert preprocessing.model_features == ANGULAR19
    assert training.features == ANGULAR19
    assert training.candidate == {
        "learning_rate": 0.05,
        "max_depth": 3,
        "min_child_weight": 5.0,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 2.0,
    }
    assert training.common == {
        "n_estimators": 1000,
        "early_stopping_rounds": 50,
        "random_seed": 42,
        "n_jobs": 1,
        "tree_method": "hist",
        "folds": 5,
    }
    assert training.working_points == {
        "loose": 0.5,
        "medium": 0.2,
        "tight": 0.1,
    }
    assert training.qualification == {
        "minimum_weighted_oof_auc": 0.8,
        "maximum_background_ks": 0.1,
        "require_signal_efficiency_above_background": True,
    }
    raw = preprocessing.raw
    assert raw["samples"] == {
        "higgs": {
            "channel_numbers": [345060],
            "label": 1,
            "input_profile": "release22",
            "tree_name": "analysis",
            "momentum_unit": "GeV",
        },
        "zz": {
            "channel_numbers": [363490],
            "label": 0,
            "input_profile": "open_data_2020",
            "tree_name": "mini",
            "momentum_unit": "MeV",
            "normalization": {
                "source": "official_metadata",
                "xsec_pb": 1.2564,
                "k_factor": 1.0,
                "filter_efficiency": 1.0,
                "sum_of_weights": 7538705.808,
            },
        },
    }
    assert raw["weighting"] == {
        "physical_weight": "signed_mc_normalization",
        "training_weight": "per_class_normalized_absolute_physical_weight",
    }
    assert raw["identity"] == {
        "fields": ["channelNumber", "eventNumber"],
        "integer_only": True,
    }
    assert raw["splitting"] == {
        "algorithm": "blake2b_64_big_endian_modulo",
        "payload": "{channelNumber}:{eventNumber}",
        "digest_size_bytes": 8,
        "modulo": 10,
        "train_buckets": [0, 1, 2, 3, 4, 5],
        "validation_buckets": [6, 7],
        "test_buckets": [8, 9],
        "train_fraction": 0.6,
        "validation_fraction": 0.2,
        "test_fraction": 0.2,
    }


@pytest.mark.parametrize(
    "text, message",
    [
        ("schema_version: '9.9'\n", "schema_version"),
        ("schema_version: '1.0'\nunknown: true\n", "unknown"),
        ("schema_version: '1.0'\nschema_version: '1.0'\n", "duplicate"),
        ("schema_version: 1.0\n", "schema_version"),
        ("schema_version: '1.0'\nchunk_size_events: .nan\n", "finite"),
    ],
)
def test_run_config_fails_closed(tmp_path: Path, text: str, message: str) -> None:
    path = tmp_path / "run.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_preprocessing_run_config(path)


@pytest.mark.parametrize(
    "updates, message",
    [
        ({"chunk_size_events": None}, "chunk_size_events"),
        ({"chunk_size_events": True}, "chunk_size_events"),
        ({"chunk_size_events": 1.5}, "positive integer"),
        ({"chunk_size_events": 0}, "positive integer"),
        ({"higgs_root": ""}, "higgs_root"),
        ({"zz_root": None}, "zz_root"),
    ],
)
def test_run_config_rejects_invalid_required_values(
    tmp_path: Path, updates: dict[str, object], message: str
) -> None:
    raw = {
        "schema_version": "1.0",
        "higgs_root": "higgs.root",
        "zz_root": "zz.root",
        "chunk_size_events": 10,
    }
    raw.update(updates)
    path = tmp_path / "run.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_preprocessing_run_config(path)


def test_checked_in_run_example_loads() -> None:
    config = load_preprocessing_run_config("config/preprocessing_run.example.yaml")
    assert config.higgs_root == Path("data/raw/higgs.root")
    assert config.zz_root == Path("data/raw/zz_363490.root")
    assert config.chunk_size_events == 50000


def _write_variant(tmp_path: Path, name: str, raw: dict[str, object]) -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda raw: raw["samples"]["higgs"].update({"mystery": 1}), "unknown"),
        (lambda raw: raw["samples"]["higgs"].update({"channel_numbers": [345061]}), "345060"),
        (lambda raw: raw["selection"].update({"electron_max_abs_eta": float("nan")}), "finite"),
        (lambda raw: raw.pop("selection"), "selection"),
        (lambda raw: raw["splitting"].update({"train_fraction": 0.9}), "sum to 1"),
        (lambda raw: raw["features"].update({"base14": ["wrong"]}), "base14"),
        (lambda raw: raw.update({"forbidden_features": []}), "forbidden"),
    ],
)
def test_preprocessing_protocol_fails_closed(
    tmp_path: Path, mutation, message: str
) -> None:
    raw = yaml.safe_load(Path("config/preprocessing_protocol_v1.yaml").read_text(encoding="utf-8"))
    mutation(raw)
    with pytest.raises(ValueError, match=message):
        load_preprocessing_protocol(_write_variant(tmp_path, "preprocess.yaml", raw))


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda raw: raw["candidate"].update({"mystery_knob": 7}), "unknown"),
        (lambda raw: raw["candidate"].pop("reg_lambda"), "exactly"),
        (lambda raw: raw["candidate"].update({"subsample": True}), "numeric"),
        (lambda raw: raw["common"].update({"random_seed": "42"}), "integer"),
        (lambda raw: raw["common"].update({"n_estimators": 1000.5}), "integer"),
        (lambda raw: raw["working_points"].pop("tight"), "exactly"),
        (lambda raw: raw["working_points"].update({"loose": "0.5"}), "numeric"),
        (lambda raw: raw["working_points"].update({"loose": 0.05, "tight": 0.9}), "ordered"),
        (lambda raw: raw["qualification"].update({"minimum_weighted_oof_auc": 4.0}), "between 0 and 1"),
    ],
)
def test_xgboost_protocol_fails_closed(tmp_path: Path, mutation, message: str) -> None:
    raw = yaml.safe_load(Path("config/xgboost_protocol_v1.yaml").read_text(encoding="utf-8"))
    mutation(raw)
    with pytest.raises(ValueError, match=message):
        load_xgboost_protocol(_write_variant(tmp_path, "xgboost.yaml", raw))
