from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.features import FEATURES
from src.plots import save_data_mass_plots, save_evaluation_plots
from src.split import event_split
from src.train import train_xgboost


def generate(size: int, label: int, rng: np.random.Generator) -> pd.DataFrame:
    signal = label == 1
    frame = pd.DataFrame(
        {
            "lep1_pt": rng.gamma(5.0 if signal else 4.3, 7.0, size),
            "lep2_pt": rng.gamma(4.2 if signal else 3.6, 6.0, size),
            "lep3_pt": rng.gamma(3.1, 4.2, size),
            "lep4_pt": rng.gamma(2.6, 3.8, size),
            "lep1_eta": rng.normal(0, 0.95 if signal else 1.2, size),
            "lep2_eta": rng.normal(0, 1.0 if signal else 1.25, size),
            "lep3_eta": rng.normal(0, 1.15, size),
            "lep4_eta": rng.normal(0, 1.2, size),
            "mZ1": rng.normal(90.4 if signal else 88.0, 5.5 if signal else 9.0, size),
            "mZ2": rng.normal(29.0 if signal else 38.0, 8.0 if signal else 14.0, size),
            "pt4l": rng.gamma(2.5 if signal else 1.8, 14.0, size),
            "deltaR_Z1": rng.normal(1.55 if signal else 2.0, 0.45, size),
            "deltaR_Z2": rng.normal(1.1 if signal else 1.65, 0.4, size),
            "deltaPhi_ZZ": rng.beta(2.3 if signal else 1.4, 1.8, size) * np.pi,
        }
    )
    # m4l is generated independently of classifier inputs to demonstrate no leakage.
    frame["m4l"] = (
        rng.normal(125.1, 1.7, size)
        if signal
        else 105 + rng.exponential(18.0, size)
    )
    frame["m4l"] = frame["m4l"].clip(105, 160)
    frame["label"] = label
    frame["physical_weight"] = 0.03 if signal else 0.12
    frame["train_weight"] = 1.0
    offset = label * 10_000_000
    frame["eventNumber"] = np.arange(size) + offset
    frame["channelNumber"] = 900001 if signal else 900002
    frame["split"] = [
        event_split(event, channel)
        for event, channel in zip(frame["eventNumber"], frame["channelNumber"])
    ]
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the demo with synthetic events")
    parser.add_argument("--events-per-class", type=int, default=4000)
    args = parser.parse_args()
    rng = np.random.default_rng(42)
    frame = pd.concat(
        [
            generate(args.events_per_class, 1, rng),
            generate(args.events_per_class, 0, rng),
        ],
        ignore_index=True,
    )
    assert set(FEATURES).issubset(frame.columns)
    output = Path("outputs")
    output.mkdir(exist_ok=True)
    model, evaluated, metrics = train_xgboost(frame, output)
    save_evaluation_plots(evaluated, model, output)
    scored = frame.copy()
    scored["xgb_score"] = model.predict_proba(scored[FEATURES])[:, 1]
    save_data_mass_plots(scored, metrics["best_threshold"], output)
    print(f"synthetic demo complete; outputs written to {output.resolve()}")


if __name__ == "__main__":
    main()
