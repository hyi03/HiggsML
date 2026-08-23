from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from xgboost import XGBClassifier

from src.features import FEATURES
from src.plots import save_data_mass_plots


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply the fixed model to real data")
    parser.add_argument("--input", default="data/processed/data_events.csv.gz")
    parser.add_argument("--model", default="outputs/xgboost_demo.json")
    parser.add_argument("--metrics", default="outputs/metrics.json")
    args = parser.parse_args()

    data = pd.read_csv(args.input)
    model = XGBClassifier()
    model.load_model(args.model)
    data["xgb_score"] = model.predict_proba(data[FEATURES])[:, 1]
    metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8"))
    threshold = float(metrics["best_threshold"])
    data.to_csv("outputs/data_with_xgb_score.csv.gz", index=False)
    save_data_mass_plots(data, threshold, "outputs")
    print(f"scored {len(data)} unlabeled data events; threshold={threshold:.2f}")


if __name__ == "__main__":
    main()

