from __future__ import annotations

import pytest

from scripts.higgsml import _feature_toggle, _parser, main


def test_train_cli_collects_feature_and_grid_overrides():
    args = _parser().parse_args(
        [
            "train",
            "--input",
            "mc.csv.gz",
            "--output-dir",
            "run",
            "--feature",
            "lep4_pt=off",
            "--max-depth",
            "2",
            "--max-depth",
            "3",
            "--learning-rate",
            "0.05",
        ]
    )

    assert args.command == "train"
    assert args.feature == [("lep4_pt", False)]
    assert args.max_depth == [2, 3]
    assert args.learning_rate == [0.05]
    assert args.show_progress is True


def test_train_cli_can_disable_progress():
    args = _parser().parse_args(
        [
            "train",
            "--input",
            "mc.csv.gz",
            "--output-dir",
            "run",
            "--no-progress",
        ]
    )

    assert args.show_progress is False


@pytest.mark.parametrize("value", ["lep1_pt", "=off", "lep1_pt=yes"])
def test_feature_cli_requires_name_on_off(value):
    with pytest.raises(Exception):
        _feature_toggle(value)


def test_train_main_resolves_cli_precedence_and_dispatches(monkeypatch, tmp_path):
    import scripts.higgsml as cli

    calls = []
    monkeypatch.setattr(
        cli,
        "run_training",
        lambda **kwargs: calls.append(kwargs) or tmp_path / "out",
    )

    assert (
        main(
            [
                "train",
                "--input",
                "mc.csv.gz",
                "--output-dir",
                str(tmp_path / "out"),
                "--config",
                "config/experiment_training.yaml",
                "--feature",
                "lep4_pt=off",
                "--max-depth",
                "2",
                "--max-depth",
                "3",
                "--min-child-weight",
                "5",
                "--min-child-weight",
                "20",
                "--n-estimators",
                "12",
                "--no-progress",
            ]
        )
        == 0
    )

    config = calls[0]["config"]
    assert "lep4_pt" not in config.features
    assert config.n_estimators == 12
    assert len(config.candidates()) == 4
    assert calls[0]["cli_overrides"]["grid"]["max_depth"] == [2, 3]
    assert calls[0]["show_progress"] is False


@pytest.mark.parametrize(
    ("command", "runner_name"),
    [("predict", "run_prediction"), ("evaluate-test", "run_test_evaluation")],
)
def test_scoring_subcommands_dispatch_without_training(
    command, runner_name, monkeypatch, tmp_path
):
    import scripts.higgsml as cli

    calls = []
    monkeypatch.setattr(
        cli, runner_name, lambda **kwargs: calls.append(kwargs) or tmp_path / "out"
    )

    assert main(
        [
            command,
            "--input",
            "events.csv.gz",
            "--model-dir",
            "model",
            "--output-dir",
            str(tmp_path / "out"),
        ]
    ) == 0
    assert calls[0]["input_path"] == "events.csv.gz"
    assert calls[0]["model_dir"] == "model"
