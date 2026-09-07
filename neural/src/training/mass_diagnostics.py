"""Descriptive all-range diagnostics; no thresholds or candidates are fitted here."""
import numpy as np

from src.training.inclusive import MassBinning
from src.training.qualification import weighted_ks_distance


def weight_summary(frame):
    weights = frame.physical_weight.to_numpy(dtype=np.float64)
    absolute = float(np.abs(weights).sum())
    squares = float(np.square(weights).sum())
    return {"rows": len(frame), "negative_weight_rows": int((weights < 0).sum()),
            "sum_abs_weight": absolute, "sum_squared_weight": squares,
            "effective_rows": absolute * absolute / squares if squares > 0 else None}


def bin_statistics(frame, binning):
    indices = binning.indices(frame.m4l)
    return [{"bin_index": index, "classes": {
        str(label): weight_summary(frame.loc[(indices == index) & (frame.label == label)])
        for label in (0, 1)}} for index in range(11)]


def mass_diagnostics(frame, binning: MassBinning, points):
    indices = binning.indices(frame.m4l)
    background = frame.label.to_numpy() == 0
    weights = np.abs(frame.physical_weight.to_numpy(dtype=np.float64))
    total = weights[background].sum()
    result = {"scope": "all_selected", "binning": binning.to_dict(),
              "statistics": bin_statistics(frame, binning), "working_points": {}}
    for name, point in points.items():
        selected = frame.score.to_numpy() >= point["threshold"]
        selected_total = weights[background & selected].sum()
        rows = []
        for index in range(11):
            mask = indices == index
            bg = mask & background
            chosen = bg & selected
            reasons = {}

            def ratio(numerator, denominator, field):
                if denominator <= 0:
                    reasons[field] = "zero_absolute_weight_denominator"
                    return None
                return float(numerator / denominator)

            row = {"bin_index": index}
            for label, field in ((0, "background_efficiency"), (1, "signal_efficiency")):
                subset = mask & (frame.label.to_numpy() == label)
                row[field] = ratio(weights[subset & selected].sum(), weights[subset].sum(), field)
            row["background_fraction_before"] = ratio(weights[bg].sum(), total, "background_fraction_before")
            row["background_fraction_after"] = ratio(weights[chosen].sum(), selected_total, "background_fraction_after")
            if weights[bg].sum() <= 0 or weights[chosen].sum() <= 0:
                row["local_mass_ks"] = None
                reasons["local_mass_ks"] = "empty_effective_background_before_or_after"
            else:
                row["local_mass_ks"] = weighted_ks_distance(frame.m4l[bg], frame.m4l[chosen], weights[bg], weights[chosen])
            row["selected_background_statistics"] = weight_summary(frame.loc[chosen])
            row["unavailable_reasons"] = reasons
            rows.append(row)
        result["working_points"][name] = {"threshold": float(point["threshold"]), "bins": rows}
    return result
