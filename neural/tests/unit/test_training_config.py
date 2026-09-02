from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest
import yaml

from src.config import InputBindingError
from src.training.config import BASE_SEED, FEATURES, TARGET_LAMBDAS, load_training_protocol


PROJECT = Path(__file__).resolve().parents[2]
PROTOCOL = PROJECT / "config/adversarial_mlp_protocol_v1.yaml"


def test_checked_in_training_protocol_is_sealed_and_hashed() -> None:
    protocol = load_training_protocol(PROTOCOL)

    assert protocol.protocol_id == "adversarial-mlp-protocol-v1"
    assert protocol.sha256 == __import__("hashlib").sha256(PROTOCOL.read_bytes()).hexdigest()
    assert len(protocol.features) == 15
    assert protocol.target_lambdas == (0.0, 0.05, 0.1, 0.2, 0.5)
    assert protocol.base_seed == BASE_SEED == protocol.raw["determinism"]["base_seed"]
    assert protocol.features == FEATURES
    assert protocol.target_lambdas == TARGET_LAMBDAS
    assert protocol.warmup_epochs == protocol.raw["schedule"]["warmup_epochs"]
    assert protocol.ramp_epochs == protocol.raw["schedule"]["ramp_epochs"]
    assert protocol.fold_count == 5
    assert protocol.working_points == (("loose", 0.5), ("medium", 0.2), ("tight", 0.1))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("features", 0), "m4l"),
        (("input_columns", 0), "m4l"),
        (("forbidden_features", 0), "lep1_pt"),
        (("classifier", "dropout"), 0.2),
        (("adversary", "bins"), 10),
        (("gradient_reversal", "backward"), "identity"),
        (("losses", "physical_weight_transform"), "signed"),
        (("optimization", "learning_rate"), 0.01),
        (("schedule", "warmup_epochs"), 4),
        (("early_stopping", "patience"), 19),
        (("checkpoint", "fields"), []),
        (("result", "summary_fields"), []),
        (("folding", "algorithm"), "blake2b"),
        (("working_points", "medium"), 0.25),
        (("qualification", "auc_minimum"), 0.79),
        (("final_fit", "seed"), 43),
        (("development_artifacts", "eligible_only_paths"), []),
    ],
)
def test_training_protocol_rejects_frozen_value_drift(
    tmp_path: Path, path: tuple[object, ...], value: object
) -> None:
    raw = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    changed = copy.deepcopy(raw)
    target = changed
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    destination = tmp_path / "changed.yaml"
    destination.write_text(yaml.safe_dump(changed, sort_keys=False), encoding="utf-8")

    with pytest.raises(InputBindingError, match="sealed adversarial MLP protocol"):
        load_training_protocol(destination)


def test_training_protocol_rejects_missing_extra_and_duplicate_keys(tmp_path: Path) -> None:
    raw = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    raw.pop("checkpoint")
    missing = tmp_path / "missing.yaml"
    missing.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(InputBindingError):
        load_training_protocol(missing)

    raw = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    raw["unexpected"] = True
    extra = tmp_path / "extra.yaml"
    extra.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(InputBindingError):
        load_training_protocol(extra)

    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text(PROTOCOL.read_text(encoding="utf-8") + "\nprotocol_id: hidden\n", encoding="utf-8")
    with pytest.raises(InputBindingError, match="duplicate YAML key"):
        load_training_protocol(duplicate)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), 1.0),
        (("classifier", "parameter_count"), True),
        (("classifier", "dropout"), 1),
        (("losses", "bin_balance_rtol"), 0),
    ],
)
def test_training_protocol_rejects_scalar_type_drift(
    tmp_path: Path, path: tuple[object, ...], value: object
) -> None:
    raw = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    target = raw
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    changed = tmp_path / "type-drift.yaml"
    changed.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(InputBindingError, match="sealed adversarial MLP protocol"):
        load_training_protocol(changed)


def test_training_protocol_rejects_mapping_and_list_reordering(tmp_path: Path) -> None:
    raw = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    reordered_mapping = copy.deepcopy(raw)
    classifier = reordered_mapping["classifier"]
    reordered_mapping["classifier"] = {
        key: classifier[key] for key in reversed(tuple(classifier))
    }
    mapping_path = tmp_path / "mapping-reordered.yaml"
    mapping_path.write_text(yaml.safe_dump(reordered_mapping, sort_keys=False), encoding="utf-8")

    reordered_list = copy.deepcopy(raw)
    reordered_list["features"][0], reordered_list["features"][1] = (
        reordered_list["features"][1],
        reordered_list["features"][0],
    )
    list_path = tmp_path / "list-reordered.yaml"
    list_path.write_text(yaml.safe_dump(reordered_list, sort_keys=False), encoding="utf-8")

    with pytest.raises(InputBindingError, match="sealed adversarial MLP protocol"):
        load_training_protocol(mapping_path)
    with pytest.raises(InputBindingError, match="sealed adversarial MLP protocol"):
        load_training_protocol(list_path)


def test_comment_only_change_preserves_semantics_but_changes_byte_hash(tmp_path: Path) -> None:
    changed = tmp_path / "comment-only.yaml"
    changed.write_bytes(PROTOCOL.read_bytes() + b"\n# audit-only comment\n")

    protocol = load_training_protocol(changed)

    assert protocol.raw == load_training_protocol(PROTOCOL).raw
    assert protocol.sha256 == hashlib.sha256(changed.read_bytes()).hexdigest()
    assert protocol.sha256 != hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
