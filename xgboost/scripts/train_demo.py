from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from src.plots import save_evaluation_plots
from src.train import train_xgboost


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate the XGBoost demo")
    parser.add_argument("--config", default="config/demo.yaml")
    parser.add_argument("--input", default="data/processed/mc_events.csv.gz")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    frame = pd.read_csv(args.input)
    model, evaluated, metrics = train_xgboost(frame, "outputs", config.get("training"))
    save_evaluation_plots(evaluated, model, "outputs")
    print(
        f"test weighted AUC={metrics['test_auc']:.3f}; "
        f"validation-selected threshold={metrics['best_threshold']:.2f}; "
        f"test ZA={metrics['asimov_significance']:.3f}; "
        f"overfitting warning={metrics['overfitting_warning']}"
    )


if __name__ == "__main__":
    main()
