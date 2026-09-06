"""Descriptive development-only statistics; never used to change qualification."""
import numpy as np


def development_statistics(frame, folds):
    if not frame["split"].isin(["train", "validation"]).all():
        raise ValueError("statistics require development rows")

    def summarize(rows):
        weights = rows["physical_weight"].to_numpy(dtype=np.float64)
        absolute = float(np.abs(weights).sum())
        squares = float(np.square(weights).sum())
        return {"rows": len(rows), "negative_weight_rows": int((weights < 0).sum()),
                "sum_abs_weight": absolute, "sum_squared_weight": squares,
                "effective_rows": absolute * absolute / squares if squares > 0 else None}

    return {
        "scope": "development_only",
        "classes": {str(label): summarize(frame.loc[frame.label == label]) for label in (0, 1)},
        "folds": {str(fold): {str(label): summarize(frame.loc[(folds == fold) & (frame.label == label)])
                              for label in (0, 1)} for fold in range(5)},
        "background_mass_bins": [summarize(frame.loc[(frame.label == 0) &
            (frame.m4l >= low) & (frame.m4l < low + 5)]) for low in range(105, 160, 5)],
    }
