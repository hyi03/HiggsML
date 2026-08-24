from pathlib import Path

import pytest

from src.decorrelation_training_run import (
    approved_decorrelation_artifacts,
    load_decorrelation_config,
)


def test_production_config_freezes_every_approved_decision():
    config = load_decorrelation_config(
        Path("config/decorrelation_training_drop_top4.yaml")
    )

    assert config.input_run == "runs/full-baseline-363490-2026-08-11-r2"
    assert config.input_manifest_sha256 == (
        "10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8"
    )
    assert config.input_mc_sha256 == (
        "1c5d6a3f9a750a5eb9965241dd8947d70e790cf949a36f8fa6ec1bfd058f378e"
    )
    assert config.coefficients == (0.0, 0.5, 1.0, 2.0, 3.0)
    assert config.auc_floor == 0.80
    assert config.ks_limit == 0.10
    assert config.require_signal_efficiency_above_background is True
    assert set(config.artifacts_no_selection) == approved_decorrelation_artifacts(
        selected=False
    )
    assert set(config.artifacts_selected) == approved_decorrelation_artifacts(
        selected=True
    )


def test_config_rejects_changed_coefficient(tmp_path):
    source = Path("config/decorrelation_training_drop_top4.yaml").read_text()
    changed = tmp_path / "changed.yaml"
    changed.write_text(source.replace("  - 3.0\n", "  - 4.0\n"))

    with pytest.raises(ValueError, match="frozen decision"):
        load_decorrelation_config(changed)
