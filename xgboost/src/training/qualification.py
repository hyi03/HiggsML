"""Qualification gate for eligible-only final-model publication."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from .evaluation import OOF_COLUMNS


def _oof_integrity(
    oof_frame: pd.DataFrame, expected_development: pd.DataFrame | None
) -> bool:
    try:
        if tuple(oof_frame.columns) != OOF_COLUMNS or oof_frame.empty:
            return False
        if not oof_frame.index.is_unique:
            return False
        if oof_frame.duplicated(["channelNumber", "eventNumber"]).any():
            return False
        if set(oof_frame["split"]) != {"train", "validation"}:
            return False
        if set(oof_frame["label"]) != {0, 1}:
            return False
        numeric = oof_frame.loc[
            :, [name for name in OOF_COLUMNS if name != "split"]
        ].to_numpy(dtype=float)
        if not np.isfinite(numeric).all():
            return False
        if expected_development is not None:
            expected = expected_development.loc[:, ["channelNumber", "eventNumber"]]
            actual = oof_frame.loc[:, ["channelNumber", "eventNumber"]]
            if len(actual) != len(expected):
                return False
            expected_ids = set(map(tuple, expected.to_numpy()))
            actual_ids = set(map(tuple, actual.to_numpy()))
            if actual_ids != expected_ids:
                return False
    except (KeyError, TypeError, ValueError):
        return False
    return True


def qualify(
    oof_frame: pd.DataFrame,
    weighted_auc: float,
    working_points: Mapping[str, Mapping[str, object]],
    background_ks: Mapping[str, float | None],
    policy: Mapping[str, float | bool],
    *,
    expected_development: pd.DataFrame | None = None,
) -> dict[str, object]:
    minimum_auc = float(policy["minimum_weighted_oof_auc"])
    maximum_ks = float(policy["maximum_background_ks"])
    require_efficiency = policy["require_signal_efficiency_above_background"]
    if not isinstance(require_efficiency, bool):
        raise ValueError("qualification efficiency policy must be boolean")
    names = ("loose", "medium", "tight")
    if tuple(working_points) != names or tuple(background_ks) != names:
        raise ValueError("qualification requires loose, medium, tight evidence")
    auc_ok = bool(np.isfinite(weighted_auc) and weighted_auc >= minimum_auc)
    ks_ok = all(
        value is not None and np.isfinite(value) and value <= maximum_ks
        for value in background_ks.values()
    )
    efficiency_ok = all(
        float(working_points[name]["signal_efficiency"])
        > float(working_points[name]["achieved_background_efficiency"])
        for name in names
    ) if require_efficiency else True
    checks = {
        "weighted_oof_auc": auc_ok,
        "background_mass_ks": ks_ok,
        "signal_efficiency_above_background": efficiency_ok,
        "oof_complete_finite_unique": _oof_integrity(
            oof_frame, expected_development
        ),
    }
    eligible = all(checks.values())
    return {
        "schema_version": "1.0",
        "status": "eligible" if eligible else "no_eligible_candidate",
        "eligible": eligible,
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "thresholds": {
            "minimum_weighted_oof_auc": minimum_auc,
            "maximum_background_ks": maximum_ks,
            "require_signal_efficiency_above_background": require_efficiency,
        },
        "observed": {
            "weighted_oof_auc": float(weighted_auc),
            "background_mass_ks": dict(background_ks),
        },
    }
