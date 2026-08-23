"""Pure fixed-bin diagnostics and training-multiplier mathematics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from .features import FEATURES
from .full_training_evaluation import build_working_points, zz_mass_diagnostics
from .full_training_model import (
    ModelSelectionResult,
    _validate_policy as _validate_training_policy,
    cross_validate_candidates,
    final_tree_count,
    fit_final_model,
    score_model,
)
from .full_training_policy import (
    CandidateSpec,
    TrainingPolicy,
    validate_development_frame,
    validate_mc_frame,
)


_FIXED_EDGES = tuple(float(value) for value in range(105, 161, 5))
_WORKING_POINT_TARGETS = (("loose", 0.50), ("medium", 0.20), ("tight", 0.10))
_FROZEN_COMMON_PARAMETER_ITEMS = (
    ("n_estimators", 1000),
    ("learning_rate", 0.05),
    ("subsample", 0.8),
    ("colsample_bytree", 0.8),
    ("reg_alpha", 0.1),
    ("reg_lambda", 2.0),
    ("objective", "binary:logistic"),
    ("eval_metric", "auc"),
    ("early_stopping_rounds", 50),
    ("tree_method", "hist"),
)
_FROZEN_CANDIDATES = (
    CandidateSpec("depth2_child20", 2, 20.0),
    CandidateSpec("depth2_child5", 2, 5.0),
    CandidateSpec("depth3_child20", 3, 20.0),
    CandidateSpec("depth3_child5", 3, 5.0),
    CandidateSpec("depth4_child20", 4, 20.0),
    CandidateSpec("depth4_child5", 4, 5.0),
)
_FULL14_FEATURES = tuple(FEATURES)
_DROP_TOP4_FEATURES = (
    "lep1_pt", "lep2_pt", "lep1_eta", "lep2_eta", "lep3_eta",
    "lep4_eta", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
)


@dataclass(frozen=True)
class ReweightingPolicy:
    mass_bin_edges: tuple[float, ...]
    minimum_effective_count: float
    epsilon_floor: float
    damping: float
    round_factor_bounds: tuple[float, float]
    cumulative_bounds: tuple[float, float]
    maximum_corrections: int
    auc_floor: float
    ks_limit: float


@dataclass(frozen=True)
class IterationEvidence:
    iteration: int
    cumulative_multipliers: Mapping[str, float]
    candidate_name: str
    final_tree_count: int
    weighted_oof_auc: float
    working_points: Mapping[str, Mapping[str, object]]
    zz_ks_distances: Mapping[str, float]
    signal_efficiencies: Mapping[str, float]
    achieved_zz_efficiencies: Mapping[str, float]
    bin_efficiencies: pd.DataFrame
    eligible: bool
    eligibility_reasons: tuple[str, ...]


@dataclass(frozen=True)
class ReweightingStudyOutcome:
    status: str
    iterations: tuple[IterationEvidence, ...]
    selected_iteration: int | None
    selected_oof_scores: pd.DataFrame | None
    model: Any | None
    test_scores: pd.DataFrame | None
    test_metrics: Mapping[str, object] | None
    fixed_bin_statistics: pd.DataFrame | None = None


def approved_reweighting_features(
    value: object,
    approved: tuple[tuple[str, ...], ...] = (
        _FULL14_FEATURES,
        _DROP_TOP4_FEATURES,
    ),
) -> tuple[str, ...]:
    """Return one of the two immutable, predeclared training profiles."""
    if (
        type(value) is not tuple
        or not all(type(item) is str for item in value)
        or not any(value == item for item in approved)
    ):
        raise ValueError("features must equal an approved reweighting profile")
    return tuple(value)


class _ReadOnlyIndexer:
    def __init__(self, frame: pd.DataFrame, name: str) -> None:
        self._frame = frame
        self._name = name

    def __getitem__(self, key: object) -> object:
        detached = pd.DataFrame(self._frame.copy(deep=True))
        return _detached_read(getattr(detached, self._name)[key])

    def __setitem__(self, key: object, value: object) -> None:
        raise TypeError("published evidence is read-only")


class _ReadOnlyDataFrame(pd.DataFrame):
    """A pandas-compatible publication snapshot that rejects in-place edits."""

    @property
    def _constructor(self):
        return _ReadOnlyDataFrame

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"index", "columns"} and hasattr(self, "_mgr"):
            raise TypeError("published evidence is read-only")
        super().__setattr__(name, value)

    @property
    def columns(self) -> pd.Index:
        return _immutable_axis(super().columns)

    @property
    def index(self) -> pd.Index:
        return _immutable_axis(super().index)

    @property
    def loc(self) -> _ReadOnlyIndexer:
        return _ReadOnlyIndexer(self, "loc")

    @property
    def iloc(self) -> _ReadOnlyIndexer:
        return _ReadOnlyIndexer(self, "iloc")

    @property
    def at(self) -> _ReadOnlyIndexer:
        return _ReadOnlyIndexer(self, "at")

    @property
    def iat(self) -> _ReadOnlyIndexer:
        return _ReadOnlyIndexer(self, "iat")

    @property
    def values(self) -> np.ndarray:
        output = super().values
        output.setflags(write=False)
        return output

    def to_numpy(self, *args: object, **kwargs: object) -> np.ndarray:
        output = super().to_numpy(*args, **kwargs)
        output.setflags(write=False)
        return output

    def __getitem__(self, key: object) -> object:
        return _detached_read(super().__getitem__(key))

    def items(self):
        for name, values in super().items():
            yield name, values.copy(deep=True)

    def __setitem__(self, key: object, value: object) -> None:
        raise TypeError("published evidence is read-only")

    def __delitem__(self, key: object) -> None:
        raise TypeError("published evidence is read-only")

    def insert(self, *args: object, **kwargs: object) -> None:
        raise TypeError("published evidence is read-only")

    def pop(self, item: object) -> object:
        raise TypeError("published evidence is read-only")

    def update(self, *args: object, **kwargs: object) -> None:
        raise TypeError("published evidence is read-only")

    def _update_inplace(self, result: object, verify_is_copy: bool = True) -> None:
        raise TypeError("published evidence is read-only")


def run_mass_bin_reweighting_study(
    frame: pd.DataFrame,
    training_policy: TrainingPolicy,
    reweighting_policy: ReweightingPolicy,
    *,
    features: tuple[str, ...] = _FULL14_FEATURES,
    model_factory=None,
) -> ReweightingStudyOutcome:
    """Run the sealed development study and, at most once, its test terminal."""
    captured_training = _captured_training_policy(training_policy)
    captured_reweighting = _captured_reweighting_policy(reweighting_policy)
    captured_features = approved_reweighting_features(features)
    if not isinstance(frame, pd.DataFrame):
        raise ValueError("frame must be a DataFrame")
    if "split" not in frame.columns:
        raise ValueError("missing required columns: ['split']")

    development_mask = frame["split"].isin(("train", "validation"))
    development = frame.loc[development_mask].copy(deep=True)
    validate_development_frame(development)
    try:
        fixed_bin_statistics = _summarize_zz_bins(
            _validated_development_zz(development),
            captured_reweighting,
            enforce_minimum=False,
        )
    except ValueError as error:
        if "mass bin" not in str(error):
            raise
        return _empty_study_outcome("insufficient_bin_statistics")
    if (fixed_bin_statistics["effective_count"] < captured_reweighting.minimum_effective_count).any():
        return _empty_study_outcome(
            "insufficient_bin_statistics", fixed_bin_statistics
        )

    current = pd.Series(
        1.0,
        index=pd.Index(_mass_bin_names_for_policy(captured_reweighting), name="mass_bin"),
        name="cumulative_multiplier",
        dtype=float,
    )
    evidence: list[IterationEvidence] = []
    selected: ModelSelectionResult | None = None
    selected_oof: pd.DataFrame | None = None
    selected_row_multipliers: pd.Series | None = None

    for iteration in range(captured_reweighting.maximum_corrections + 1):
        row_multipliers = _development_training_multipliers(development, current)
        selection = cross_validate_candidates(
            development,
            captured_training,
            model_factory=model_factory,
            training_weight_multipliers=row_multipliers,
            features=captured_features,
        )
        oof = _oof_score_frame(development, selection)
        points = build_working_points(oof, captured_training.working_points)
        weighted_auc = float(
            roc_auc_score(
                oof["label"],
                oof["oof_score"],
                sample_weight=np.abs(oof["physical_weight"].to_numpy(dtype=float)),
            )
        )
        diagnostics = zz_mass_diagnostics(
            oof, "oof_score", points, captured_training
        )
        ks_distances = {
            name: diagnostics["working_points"][name][
                "inclusive_to_selected_ks_distance"
            ]
            for name in _working_point_names()
        }
        signal_efficiencies = {
            name: float(points[name]["signal_efficiency"])
            for name in _working_point_names()
        }
        achieved_zz_efficiencies = {
            name: float(points[name]["achieved_background_efficiency"])
            for name in _working_point_names()
        }
        bin_efficiencies = compute_bin_efficiencies(
            oof, points, captured_reweighting
        )
        reasons = _eligibility_reasons(
            weighted_auc=weighted_auc,
            zz_ks_distances=ks_distances,
            signal_efficiencies=signal_efficiencies,
            achieved_zz_efficiencies=achieved_zz_efficiencies,
            policy=captured_reweighting,
        )
        evidence.append(
            IterationEvidence(
                iteration=iteration,
                cumulative_multipliers=_frozen_mapping(current.to_dict()),
                candidate_name=selection.selected.candidate.name,
                final_tree_count=final_tree_count(selection.selected),
                weighted_oof_auc=weighted_auc,
                working_points=_frozen_mapping(points),
                zz_ks_distances=_frozen_mapping(ks_distances),
                signal_efficiencies=_frozen_mapping(signal_efficiencies),
                achieved_zz_efficiencies=_frozen_mapping(
                    achieved_zz_efficiencies
                ),
                bin_efficiencies=_read_only_frame(bin_efficiencies),
                eligible=not reasons,
                eligibility_reasons=reasons,
            )
        )
        if not reasons:
            selected = selection
            selected_oof = oof.copy(deep=True)
            selected_row_multipliers = row_multipliers.copy(deep=True)
            break
        if iteration < captured_reweighting.maximum_corrections:
            current = update_cumulative_multipliers(
                bin_efficiencies, current, captured_reweighting
            )

    if selected is None or selected_oof is None or selected_row_multipliers is None:
        return ReweightingStudyOutcome(
            status="no_eligible_iteration",
            iterations=tuple(evidence),
            selected_iteration=None,
            selected_oof_scores=None,
            model=None,
            test_scores=None,
            test_metrics=None,
            fixed_bin_statistics=_read_only_frame(fixed_bin_statistics),
        )

    selected_iteration = evidence[-1].iteration
    validate_mc_frame(frame)
    full_multipliers = pd.Series(1.0, index=frame.index, dtype=float)
    full_multipliers.loc[development.index] = selected_row_multipliers
    model = fit_final_model(
        frame,
        selected,
        captured_training,
        model_factory=model_factory,
        training_weight_multipliers=full_multipliers,
        features=captured_features,
    )
    test = frame.loc[frame["split"] == "test"].copy(deep=True)
    scored_test = _test_score_frame(
        test, score_model(model, test, features=captured_features)
    )
    terminal, test_metrics = _test_terminal(
        scored_test,
        evidence[-1].working_points,
        captured_training,
        captured_reweighting,
    )
    return ReweightingStudyOutcome(
        status=terminal,
        iterations=tuple(evidence),
        selected_iteration=selected_iteration,
        selected_oof_scores=_read_only_frame(selected_oof),
        model=model,
        test_scores=_read_only_frame(scored_test),
        test_metrics=test_metrics,
        fixed_bin_statistics=_read_only_frame(fixed_bin_statistics),
    )


def summarize_development_zz_bins(
    development: pd.DataFrame, policy: ReweightingPolicy
) -> pd.DataFrame:
    """Return fixed-bin, absolute-physical-weight ZZ statistics for development."""
    _validate_policy(policy)
    zz = _validated_development_zz(development)
    return _summarize_zz_bins(zz, policy)


def compute_bin_efficiencies(
    oof: pd.DataFrame,
    working_points: Mapping[str, Mapping[str, object]],
    policy: ReweightingPolicy,
) -> pd.DataFrame:
    """Calculate fixed-bin ZZ efficiencies from OOF scores and physical weights."""
    _validate_policy(policy)
    zz = _validated_development_zz(oof)
    score_column = _score_column(zz)
    points = _validated_working_points(working_points)
    summary = _summarize_zz_bins(zz, policy)
    bin_names = tuple(summary.index)
    assignments = _mass_bin_names(zz["m4l"].to_numpy(dtype=float))
    scores = zz[score_column].to_numpy(dtype=float)
    weights = np.abs(zz["physical_weight"].to_numpy(dtype=float))

    rows: list[dict[str, float | str]] = []
    for mass_bin in bin_names:
        in_bin = assignments == mass_bin
        denominator = float(weights[in_bin].sum())
        effective_count = float(summary.loc[mass_bin, "effective_count"])
        for name in _working_point_names():
            numerator = float(weights[in_bin & (scores > points[name])].sum())
            efficiency = float(numerator / denominator)
            rows.append(
                {
                    "mass_bin": mass_bin,
                    "working_point": name,
                    "numerator": numerator,
                    "denominator": denominator,
                    "efficiency": efficiency,
                    "effective_count": effective_count,
                    "standard_error": float(
                        np.sqrt(efficiency * (1.0 - efficiency) / effective_count)
                    ),
                }
            )
    return pd.DataFrame(rows).set_index(["mass_bin", "working_point"])


def update_cumulative_multipliers(
    efficiencies: pd.DataFrame,
    current: pd.Series,
    policy: ReweightingPolicy,
) -> pd.Series:
    """Apply the frozen damped geometric per-bin update to multipliers."""
    _validate_policy(policy)
    values = _validated_efficiencies(efficiencies)
    current_values = _validated_current_multipliers(current)
    lower_round, upper_round = policy.round_factor_bounds
    lower_cumulative, upper_cumulative = policy.cumulative_bounds
    specifications = _working_point_specs()
    names = tuple(name for name, _ in specifications)
    targets = np.asarray([target for _, target in specifications], dtype=float)
    updated: list[float] = []
    for mass_bin in _mass_bin_names_for_policy(policy):
        observed = np.asarray(
            [values.loc[(mass_bin, point)] for point in names], dtype=float
        )
        factor = float(
            np.exp(
                policy.damping
                / len(names)
                * np.log(
                    (observed + policy.epsilon_floor)
                    / (targets + policy.epsilon_floor)
                ).sum()
            )
        )
        factor = float(np.clip(factor, lower_round, upper_round))
        updated.append(
            float(
                np.clip(
                    current_values.loc[mass_bin] * factor,
                    lower_cumulative,
                    upper_cumulative,
                )
            )
        )
    output = pd.Series(
        updated,
        index=pd.Index(_mass_bin_names_for_policy(policy), name="mass_bin"),
        name="cumulative_multiplier",
        dtype=float,
    )
    if not np.isfinite(output.to_numpy()).all() or (output <= 0.0).any():
        raise ValueError("updated multipliers must be finite and strictly positive")
    return output.copy()


def _validate_policy(policy: ReweightingPolicy) -> None:
    if not isinstance(policy, ReweightingPolicy):
        raise TypeError("policy must be a ReweightingPolicy")
    if not isinstance(policy.mass_bin_edges, tuple) or policy.mass_bin_edges != _fixed_edges():
        raise ValueError("mass_bin_edges must equal the frozen 105:5:160 edges")
    _require_exact_float(policy.minimum_effective_count, 100.0, "minimum_effective_count")
    _require_exact_float(policy.epsilon_floor, 1e-6, "epsilon_floor")
    _require_exact_float(policy.damping, 0.5, "damping")
    _require_exact_pair(policy.round_factor_bounds, (0.5, 2.0), "round_factor_bounds")
    _require_exact_pair(policy.cumulative_bounds, (0.2, 5.0), "cumulative_bounds")
    if isinstance(policy.maximum_corrections, bool) or policy.maximum_corrections != 5:
        raise ValueError("maximum_corrections must equal 5")
    _require_exact_float(policy.auc_floor, 0.80, "auc_floor")
    _require_exact_float(policy.ks_limit, 0.10, "ks_limit")


def _require_exact_float(value: object, expected: float, name: str) -> None:
    if isinstance(value, bool):
        raise ValueError(f"{name} must equal {expected}")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must equal {expected}") from error
    if not np.isfinite(numeric) or numeric != expected:
        raise ValueError(f"{name} must equal {expected}")


def _require_exact_pair(value: object, expected: tuple[float, float], name: str) -> None:
    if not isinstance(value, tuple) or len(value) != 2:
        raise ValueError(f"{name} must equal {expected}")
    for actual, target in zip(value, expected):
        _require_exact_float(actual, target, name)


def _validated_development_zz(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"split", "label", "m4l", "physical_weight"}
    if not isinstance(frame, pd.DataFrame):
        raise ValueError("development rows must be a DataFrame")
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    if frame.empty:
        raise ValueError("development rows must be non-empty")
    if not frame["split"].isin({"train", "validation"}).all():
        raise ValueError("rows must use development splits only")
    if not frame["label"].isin({0, 1}).all():
        raise ValueError("labels must be 0 or 1")
    try:
        numeric = frame[["m4l", "physical_weight"]].to_numpy(dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError("masses and physical weights must be numeric") from error
    if not np.isfinite(numeric).all():
        raise ValueError("masses and physical weights must be finite")
    masses = numeric[:, 0]
    edges = _fixed_edges()
    if (masses < edges[0]).any() or (masses > edges[-1]).any():
        raise ValueError("masses must be within the configured mass range")
    zz = frame.loc[frame["label"] == 0].copy()
    if zz.empty:
        raise ValueError("development rows must contain ZZ label-0 events")
    return zz


def _summarize_zz_bins(
    zz: pd.DataFrame, policy: ReweightingPolicy, *, enforce_minimum: bool = True
) -> pd.DataFrame:
    names = _mass_bin_names_for_policy(policy)
    assignments = _mass_bin_names(zz["m4l"].to_numpy(dtype=float))
    physical = zz["physical_weight"].to_numpy(dtype=float)
    rows: list[dict[str, float | int | str]] = []
    for mass_bin, lower, upper in zip(names, policy.mass_bin_edges, policy.mass_bin_edges[1:]):
        weights = physical[assignments == mass_bin]
        absolute_sum = float(np.abs(weights).sum())
        squared_sum = float(np.square(weights).sum())
        if not np.isfinite(absolute_sum) or not np.isfinite(squared_sum):
            raise ValueError(f"mass bin {mass_bin} must have positive absolute physical-weight sum")
        effective_count = (
            0.0 if squared_sum == 0.0 else float(absolute_sum**2 / squared_sum)
        )
        if enforce_minimum and absolute_sum <= 0.0:
            raise ValueError(f"mass bin {mass_bin} must have positive absolute physical-weight sum")
        if not np.isfinite(effective_count) or (
            enforce_minimum and effective_count < policy.minimum_effective_count
        ):
            raise ValueError(f"mass bin {mass_bin} fails the minimum effective count")
        rows.append(
            {
                "mass_bin": mass_bin,
                "lower_edge": float(lower),
                "upper_edge": float(upper),
                "raw_count": int(weights.size),
                "absolute_weight_sum": absolute_sum,
                "squared_weight_sum": squared_sum,
                "effective_count": effective_count,
            }
        )
    return pd.DataFrame(rows).set_index("mass_bin")


def _score_column(frame: pd.DataFrame) -> str:
    available = [name for name in ("score", "oof_score") if name in frame.columns]
    if len(available) != 1:
        raise ValueError("OOF rows must contain exactly one score column")
    try:
        values = frame[available[0]].to_numpy(dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError("OOF scores must be finite") from error
    if not np.isfinite(values).all():
        raise ValueError("OOF scores must be finite")
    return available[0]


def _validated_working_points(
    working_points: Mapping[str, Mapping[str, object]],
) -> dict[str, float]:
    names = _working_point_names()
    if not isinstance(working_points, Mapping) or set(working_points) != set(names):
        raise ValueError("working-point keys must be exactly loose, medium, and tight")
    if tuple(working_points) != names:
        raise ValueError("working-point order must be loose, medium, and tight")
    thresholds: dict[str, float] = {}
    for name, target in _working_point_specs():
        point = working_points[name]
        if (
            not isinstance(point, Mapping)
            or "threshold" not in point
            or "target_background_efficiency" not in point
        ):
            raise ValueError(
                f"working point {name} must contain threshold and target_background_efficiency"
            )
        try:
            threshold = float(point["threshold"])
            point_target = float(point["target_background_efficiency"])
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"working point {name} must contain finite threshold and target_background_efficiency"
            ) from error
        if not np.isfinite(threshold):
            raise ValueError(f"working point {name} must contain a finite threshold")
        if not np.isfinite(point_target) or point_target != target:
            raise ValueError(
                f"working point {name} target_background_efficiency must equal {target}"
            )
        thresholds[name] = threshold
    if any(first > second for first, second in zip(thresholds.values(), list(thresholds.values())[1:])):
        raise ValueError("working-point thresholds must be monotonic")
    return thresholds


def _validated_efficiencies(efficiencies: pd.DataFrame) -> pd.Series:
    if not isinstance(efficiencies, pd.DataFrame) or "efficiency" not in efficiencies.columns:
        raise ValueError("efficiencies must be a DataFrame with an efficiency column")
    if not isinstance(efficiencies.index, pd.MultiIndex) or efficiencies.index.nlevels != 2:
        raise ValueError("efficiencies must use a mass-bin and working-point MultiIndex")
    expected = pd.MultiIndex.from_product(
        [_mass_bin_names_for_policy_from_fixed_edges(), _working_point_names()],
        names=["mass_bin", "working_point"],
    )
    if not efficiencies.index.is_unique or set(efficiencies.index) != set(expected):
        raise ValueError("efficiencies must contain every fixed bin and working point exactly once")
    try:
        result = efficiencies["efficiency"].astype(float)
    except (TypeError, ValueError) as error:
        raise ValueError("efficiencies must be finite between zero and one") from error
    result = result.reindex(expected)
    if not np.isfinite(result.to_numpy()).all() or (result < 0.0).any() or (result > 1.0).any():
        raise ValueError("efficiencies must be finite between zero and one")
    return result


def _validated_current_multipliers(current: pd.Series) -> pd.Series:
    names = _mass_bin_names_for_policy_from_fixed_edges()
    if not isinstance(current, pd.Series):
        raise TypeError("current multipliers must be a pandas Series")
    if not current.index.is_unique or set(current.index) != set(names):
        raise ValueError("current multipliers must contain every fixed mass bin exactly once")
    try:
        values = current.astype(float).reindex(names)
    except (TypeError, ValueError) as error:
        raise ValueError("current multipliers must be finite and strictly positive") from error
    if not np.isfinite(values.to_numpy()).all() or (values <= 0.0).any():
        raise ValueError("current multipliers must be finite and strictly positive")
    return values.copy()


def _mass_bin_names(masses: np.ndarray) -> np.ndarray:
    edges = _fixed_edges()
    indices = np.searchsorted(np.asarray(edges), masses, side="right") - 1
    indices[masses == edges[-1]] = len(edges) - 2
    names = np.asarray(_mass_bin_names_for_policy_from_fixed_edges(), dtype=object)
    return names[indices]


def _mass_bin_names_for_policy(policy: ReweightingPolicy) -> tuple[str, ...]:
    return _mass_bin_names_for_policy_from_fixed_edges()


def _mass_bin_names_for_policy_from_fixed_edges() -> tuple[str, ...]:
    edges = _fixed_edges()
    return tuple(
        f"[{int(lower)},{int(upper)}{']' if upper == edges[-1] else ')'}"
        for lower, upper in zip(edges, edges[1:])
    )


def _fixed_edges(edges: tuple[float, ...] = _FIXED_EDGES) -> tuple[float, ...]:
    """Return the import-time captured frozen bin definition."""
    return edges


def _working_point_specs(
    specs: tuple[tuple[str, float], ...] = _WORKING_POINT_TARGETS,
) -> tuple[tuple[str, float], ...]:
    """Return the import-time captured immutable frozen target definition."""
    return specs


def _working_point_names() -> tuple[str, ...]:
    return tuple(name for name, _ in _working_point_specs())


def _model_features(features: tuple[str, ...] = tuple(FEATURES)) -> tuple[str, ...]:
    """Return the import-time captured full feature tuple."""
    return features


def _exact_candidates(
    candidates: object, expected: tuple[CandidateSpec, ...]
) -> bool:
    if not isinstance(candidates, tuple) or len(candidates) != len(expected):
        return False
    return all(
        isinstance(actual, CandidateSpec)
        and actual.name == target.name
        and type(actual.max_depth) is int
        and actual.max_depth == target.max_depth
        and type(actual.min_child_weight) is float
        and actual.min_child_weight == target.min_child_weight
        for actual, target in zip(candidates, expected, strict=True)
    )


def _exact_mapping_items(
    mapping: object, expected: tuple[tuple[str, object], ...]
) -> bool:
    if not isinstance(mapping, Mapping) or tuple(mapping) != tuple(
        name for name, _ in expected
    ):
        return False
    return all(
        type(mapping[name]) is type(value) and mapping[name] == value
        for name, value in expected
    )


def _require_frozen_training_policy(
    policy: TrainingPolicy,
    structural_validator=_validate_training_policy,
    candidate_validator=_exact_candidates,
    mapping_validator=_exact_mapping_items,
    frozen_candidates: tuple[CandidateSpec, ...] = _FROZEN_CANDIDATES,
    frozen_common: tuple[tuple[str, object], ...] = _FROZEN_COMMON_PARAMETER_ITEMS,
    frozen_working_points: tuple[tuple[str, float], ...] = _WORKING_POINT_TARGETS,
    frozen_mass_bins: tuple[float, ...] = _FIXED_EDGES,
) -> None:
    message = "training policy must equal the frozen training policy"
    try:
        structural_validator(policy)
    except (TypeError, ValueError) as error:
        raise ValueError(message) from error
    if (
        type(policy.folds) is not int
        or policy.folds != 5
        or type(policy.random_seed) is not int
        or policy.random_seed != 42
        or type(policy.n_jobs) is not int
        or policy.n_jobs != 4
        or not candidate_validator(policy.candidates, frozen_candidates)
        or not mapping_validator(policy.common_parameters, frozen_common)
        or not mapping_validator(policy.working_points, frozen_working_points)
        or type(policy.auc_gap_limit) is not float
        or policy.auc_gap_limit != 0.05
        or type(policy.ks_distance_limit) is not float
        or policy.ks_distance_limit != 0.10
        or tuple(policy.mass_bins_gev) != frozen_mass_bins
        or any(type(value) is not float for value in policy.mass_bins_gev)
    ):
        raise ValueError(message)


def _captured_training_policy(
    policy: TrainingPolicy,
    validator=_require_frozen_training_policy,
) -> TrainingPolicy:
    if not isinstance(policy, TrainingPolicy):
        raise TypeError("training_policy must be a TrainingPolicy")
    validator(policy)
    captured = TrainingPolicy(
        folds=policy.folds,
        random_seed=policy.random_seed,
        n_jobs=policy.n_jobs,
        common_parameters=MappingProxyType(dict(policy.common_parameters)),
        candidates=tuple(policy.candidates),
        working_points=MappingProxyType(dict(policy.working_points)),
        auc_gap_limit=float(policy.auc_gap_limit),
        ks_distance_limit=float(policy.ks_distance_limit),
        mass_bins_gev=tuple(policy.mass_bins_gev),
    )
    validator(captured)
    return captured


def _captured_reweighting_policy(policy: ReweightingPolicy) -> ReweightingPolicy:
    _validate_policy(policy)
    captured = ReweightingPolicy(
        mass_bin_edges=tuple(policy.mass_bin_edges),
        minimum_effective_count=float(policy.minimum_effective_count),
        epsilon_floor=float(policy.epsilon_floor),
        damping=float(policy.damping),
        round_factor_bounds=tuple(policy.round_factor_bounds),
        cumulative_bounds=tuple(policy.cumulative_bounds),
        maximum_corrections=policy.maximum_corrections,
        auc_floor=float(policy.auc_floor),
        ks_limit=float(policy.ks_limit),
    )
    _validate_policy(captured)
    return captured


def _empty_study_outcome(
    status: str, fixed_bin_statistics: pd.DataFrame | None = None
) -> ReweightingStudyOutcome:
    return ReweightingStudyOutcome(
        status=status,
        iterations=(),
        selected_iteration=None,
        selected_oof_scores=None,
        model=None,
        test_scores=None,
        test_metrics=None,
        fixed_bin_statistics=(
            None
            if fixed_bin_statistics is None
            else _read_only_frame(fixed_bin_statistics)
        ),
    )


def _development_training_multipliers(
    development: pd.DataFrame, cumulative: pd.Series
) -> pd.Series:
    labels = development["label"].to_numpy(dtype=int)
    values = np.ones(len(development), dtype=float)
    background = labels == 0
    assignments = _mass_bin_names(
        development.loc[background, "m4l"].to_numpy(dtype=float)
    )
    values[background] = cumulative.loc[assignments].to_numpy(dtype=float)
    return pd.Series(values, index=development.index, dtype=float)


def _oof_score_frame(
    development: pd.DataFrame, selection: ModelSelectionResult
) -> pd.DataFrame:
    columns = [
        "eventNumber",
        "channelNumber",
        "split",
        "label",
        "physical_weight",
        "m4l",
    ]
    output = development.loc[:, columns].copy(deep=True)
    output["oof_score"] = selection.oof_scores.loc[output.index].to_numpy(dtype=float)
    return output


def _test_score_frame(test: pd.DataFrame, scores: np.ndarray) -> pd.DataFrame:
    columns = [
        "eventNumber",
        "channelNumber",
        "split",
        "label",
        "physical_weight",
        "m4l",
    ]
    output = test.loc[:, columns].copy(deep=True)
    output["score"] = np.asarray(scores, dtype=float)
    return output


def _eligibility_reasons(
    *,
    weighted_auc: float,
    zz_ks_distances: Mapping[str, object],
    signal_efficiencies: Mapping[str, float],
    achieved_zz_efficiencies: Mapping[str, float],
    policy: ReweightingPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not np.isfinite(weighted_auc) or weighted_auc < policy.auc_floor:
        reasons.append("weighted_auc_below_floor")
    for name in _working_point_names():
        distance = zz_ks_distances[name]
        if distance is None or not np.isfinite(float(distance)):
            reasons.append(f"{name}_zz_ks_unavailable")
        elif float(distance) > policy.ks_limit:
            reasons.append(f"{name}_zz_ks_above_limit")
    for name in _working_point_names():
        if not (
            float(signal_efficiencies[name])
            > float(achieved_zz_efficiencies[name])
        ):
            reasons.append(f"{name}_signal_efficiency_not_strictly_greater")
    return tuple(reasons)


def _test_terminal(
    scored_test: pd.DataFrame,
    frozen_points: Mapping[str, Mapping[str, object]],
    training_policy: TrainingPolicy,
    reweighting_policy: ReweightingPolicy,
) -> tuple[str, Mapping[str, object]]:
    labels = scored_test["label"].to_numpy(dtype=int)
    scores = scored_test["score"].to_numpy(dtype=float)
    physical = scored_test["physical_weight"].to_numpy(dtype=float)
    absolute = np.abs(physical)
    weighted_auc = float(
        roc_auc_score(labels, scores, sample_weight=absolute)
    )
    diagnostics = zz_mass_diagnostics(
        scored_test, "score", frozen_points, training_policy
    )
    points: dict[str, dict[str, float]] = {}
    ks_distances: dict[str, object] = {}
    signal_efficiencies: dict[str, float] = {}
    achieved_zz_efficiencies: dict[str, float] = {}
    for name in _working_point_names():
        threshold = float(frozen_points[name]["threshold"])
        selected = scores >= threshold
        signal_efficiency = _absolute_efficiency(
            selected, labels == 1, absolute
        )
        background_efficiency = _absolute_efficiency(
            selected, labels == 0, absolute
        )
        distance = diagnostics["working_points"][name][
            "inclusive_to_selected_ks_distance"
        ]
        points[name] = {
            "threshold": threshold,
            "target_background_efficiency": float(
                frozen_points[name]["target_background_efficiency"]
            ),
            "achieved_background_efficiency": background_efficiency,
            "signal_efficiency": signal_efficiency,
        }
        ks_distances[name] = distance
        signal_efficiencies[name] = signal_efficiency
        achieved_zz_efficiencies[name] = background_efficiency
    reasons = _eligibility_reasons(
        weighted_auc=weighted_auc,
        zz_ks_distances=ks_distances,
        signal_efficiencies=signal_efficiencies,
        achieved_zz_efficiencies=achieved_zz_efficiencies,
        policy=reweighting_policy,
    )
    metrics = _frozen_mapping(
        {
            "weighted_auc": weighted_auc,
            "working_points": points,
            "zz_ks_distances": ks_distances,
            "signal_efficiencies": signal_efficiencies,
            "achieved_zz_efficiencies": achieved_zz_efficiencies,
            "eligibility_reasons": reasons,
        }
    )
    terminal = (
        "eligible_iteration_test_reproduced"
        if not reasons
        else "test_nonreproduction"
    )
    return terminal, metrics


def _absolute_efficiency(
    selected: np.ndarray, class_mask: np.ndarray, absolute_weights: np.ndarray
) -> float:
    denominator = float(absolute_weights[class_mask].sum())
    if denominator <= 0.0:
        raise ValueError("each test class must have positive absolute weight")
    return float(absolute_weights[selected & class_mask].sum() / denominator)


def _frozen_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    frozen: dict[str, object] = {}
    for name, nested in value.items():
        if isinstance(nested, Mapping):
            frozen[name] = _frozen_mapping(nested)
        elif isinstance(nested, list):
            frozen[name] = tuple(nested)
        elif isinstance(nested, tuple):
            frozen[name] = tuple(nested)
        else:
            frozen[name] = nested
    return MappingProxyType(frozen)


def _read_only_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return _ReadOnlyDataFrame(frame.copy(deep=True))


def _detached_read(value: object) -> object:
    if isinstance(value, (pd.DataFrame, pd.Series)):
        return value.copy(deep=True)
    return value


def _immutable_axis(axis: pd.Index) -> pd.Index:
    if isinstance(axis, pd.MultiIndex):
        detached: pd.Index = pd.MultiIndex.from_tuples(
            tuple(axis), names=tuple(axis.names)
        )
    else:
        detached = axis.copy(deep=True)
        values = detached.values
        if not isinstance(values, np.ndarray):
            detached = pd.Index(
                np.asarray(tuple(axis), dtype=object),
                dtype=object,
                name=axis.name,
                tupleize_cols=False,
            )
    detached.values.setflags(write=False)
    return detached
