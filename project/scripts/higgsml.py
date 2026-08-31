from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from src.experiment_config import (
    GRID_PARAMETERS,
    SCALAR_PARAMETERS,
    ExperimentOverrides,
    load_experiment_config,
)
from src.experiment_runner import run_prediction, run_test_evaluation, run_training


def _feature_toggle(value: str) -> tuple[str, bool]:
    name, separator, state = value.partition("=")
    if not separator or not name or state.lower() not in {"on", "off"}:
        raise argparse.ArgumentTypeError("feature must use NAME=on or NAME=off")
    return name, state.lower() == "on"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.higgsml",
        description="Run configurable HiggsML XGBoost experiments",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    train = subcommands.add_parser(
        "train", help="select parameters on development data and fit a fixed model"
    )
    train.add_argument("--input", required=True)
    train.add_argument("--output-dir", required=True)
    train.add_argument("--config", default="config/experiment_training.yaml")
    train.add_argument("--feature-profile", choices=("base14", "angular19"))
    train.add_argument("--feature", action="append", type=_feature_toggle, default=[])
    train.add_argument("--overwrite", action="store_true")
    for name in GRID_PARAMETERS:
        option = f"--{name.replace('_', '-')}"
        value_type = int if name == "max_depth" else float
        train.add_argument(option, dest=name, action="append", type=value_type)
    for name in SCALAR_PARAMETERS:
        option = f"--{name.replace('_', '-')}"
        value_type = str if name == "tree_method" else int
        train.add_argument(option, dest=name, type=value_type)

    for name, help_text in (
        ("predict", "score unlabeled or non-test data with a fixed model"),
        ("evaluate-test", "evaluate a fixed model on split=test exactly as recorded"),
    ):
        command = subcommands.add_parser(name, help=help_text)
        command.add_argument("--input", required=True)
        command.add_argument("--model-dir", required=True)
        command.add_argument("--output-dir", required=True)
        command.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    if args.command == "train":
        grid = {
            name: tuple(getattr(args, name))
            for name in GRID_PARAMETERS
            if getattr(args, name) is not None
        }
        scalars = {
            name: getattr(args, name)
            for name in SCALAR_PARAMETERS
            if getattr(args, name) is not None
        }
        config = load_experiment_config(
            args.config,
            ExperimentOverrides(
                feature_profile=args.feature_profile,
                feature_toggles=tuple(args.feature),
                grid=grid,
                scalars=scalars,
            ),
        )
        cli_overrides = {
            "feature_profile": args.feature_profile,
            "features": [
                f"{name}={'on' if enabled else 'off'}"
                for name, enabled in args.feature
            ],
            "grid": {name: list(values) for name, values in grid.items()},
            "scalars": scalars,
        }
        destination = run_training(
            input_path=args.input,
            output_dir=args.output_dir,
            config=config,
            overwrite=args.overwrite,
            project_root=project_root,
            cli_overrides=cli_overrides,
        )
    elif args.command == "predict":
        destination = run_prediction(
            input_path=args.input,
            model_dir=args.model_dir,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
            project_root=project_root,
        )
    else:
        destination = run_test_evaluation(
            input_path=args.input,
            model_dir=args.model_dir,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
            project_root=project_root,
        )
    print(f"{args.command} complete; outputs written to {destination.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
