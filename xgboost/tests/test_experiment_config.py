from __future__ import annotations

from pathlib import Path

import pytest

from src.angular5 import ANGULAR5_FEATURES
from src.experiment_config import (
    BASE14_PROFILE,
    ExperimentOverrides,
    load_experiment_config,
    resolve_enabled_features,
)
from src.features import FEATURES


def test_feature_profiles_are_ordered_and_default_to_all_enabled():
    base = resolve_enabled_features("base14", {})
    angular = resolve_enabled_features("angular19", {})

    assert base == tuple(FEATURES) == BASE14_PROFILE
    assert angular == (*tuple(FEATURES), *tuple(ANGULAR5_FEATURES))


def test_feature_overrides_preserve_profile_order_and_reject_conflicts():
    selected = resolve_enabled_features(
        "base14", {"lep4_pt": False, "lep1_pt": True}
    )
    assert selected == tuple(name for name in FEATURES if name != "lep4_pt")

    with pytest.raises(ValueError, match="conflicting"):
        resolve_enabled_features("base14", [("lep1_pt", True), ("lep1_pt", False)])


@pytest.mark.parametrize("name", ["m4l", "physical_weight", "not_a_feature"])
def test_feature_overrides_reject_forbidden_or_unknown_names(name):
    with pytest.raises(ValueError, match="feature"):
        resolve_enabled_features("base14", [(name, True)])


def test_feature_overrides_reject_empty_selection():
    with pytest.raises(ValueError, match="at least one"):
        resolve_enabled_features(
            "base14", [(name, False) for name in FEATURES]
        )


def test_config_precedence_and_repeated_grid_values(tmp_path: Path):
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text(
        """
schema_version: "1.0"
feature_profile: base14
features:
  lep4_pt: false
training:
  n_estimators: 20
  learning_rate: [0.1]
  max_depth: [2, 4]
  min_child_weight: [5]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = load_experiment_config(
        config_path,
        ExperimentOverrides(
            feature_profile="angular19",
            feature_toggles=(("cos_theta_star", False),),
            grid={"max_depth": (3,), "learning_rate": (0.05, 0.02)},
            scalars={"n_estimators": 12},
        ),
    )

    assert config.feature_profile == "angular19"
    assert "lep4_pt" not in config.features
    assert "cos_theta_star" not in config.features
    assert config.n_estimators == 12
    assert config.grid["max_depth"] == (3,)
    assert config.grid["learning_rate"] == (0.05, 0.02)
    assert len(config.candidates()) == 2


def test_unknown_config_keys_fail_closed(tmp_path: Path):
    config_path = tmp_path / "bad.yaml"
    config_path.write_text('schema_version: "1.0"\nunknown: true\n', encoding="utf-8")

    with pytest.raises(ValueError, match="unknown experiment config keys"):
        load_experiment_config(config_path)


def test_cli_feature_toggle_overrides_yaml_toggle(tmp_path: Path):
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text(
        'schema_version: "1.0"\nfeatures:\n  lep4_pt: false\n',
        encoding="utf-8",
    )

    config = load_experiment_config(
        config_path,
        ExperimentOverrides(feature_toggles=(("lep4_pt", True),)),
    )

    assert config.features == tuple(FEATURES)


def test_config_rejects_single_development_fold():
    with pytest.raises(ValueError, match="at least 2"):
        load_experiment_config(
            None, ExperimentOverrides(scalars={"folds": 1})
        )
