from __future__ import annotations

import numpy as np
import pandas as pd

from src.training.dataset import FEATURE_COLUMNS, INPUT_COLUMNS


def synthetic_development_frame(*, validation_shift: float = 0.0) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    entry = 0
    for split, shift in (("train", 0.0), ("validation", validation_shift)):
        for label in (0, 1):
            masses = [107.5 + 5.0 * index for index in range(11)] if label == 0 else [125.0] * 11
            for local_index, mass in enumerate(masses):
                values = {
                    feature: float(local_index + feature_index / 10.0 + shift + 0.75 * label)
                    for feature_index, feature in enumerate(FEATURE_COLUMNS)
                }
                row: dict[str, object] = {
                    "lep3_pt": float(local_index + 3.0 + shift),
                    "lep4_pt": float(local_index + 4.0 + shift),
                    "mZ1": 91.0,
                    "mZ2": 25.0,
                    **values,
                    "m4l": mass,
                    "label": label,
                    "split": split,
                    "physical_weight": -2.0 if entry == 0 else 1.0 + local_index / 10.0,
                    "train_weight": 1.0,
                    "source_sample": "zz_363490" if label == 0 else "higgs_345060",
                    "source_entry": entry,
                    "runNumber": 1000 + entry,
                    "eventNumber": 2000 + entry,
                    "channelNumber": 363490 if label == 0 else 345060,
                }
                rows.append(row)
                entry += 1
    return pd.DataFrame(rows, columns=INPUT_COLUMNS)
