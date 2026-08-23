from __future__ import annotations

import math
import inspect
from collections import Counter
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import numpy as np
import pandas as pd
import pytest

import src.mass_bin_reweighting as mass_bin_reweighting
from src.features import FEATURES
from src.full_training_policy import CandidateSpec, load_training_policy
from src.mass_bin_reweighting import (
    ReweightingPolicy,
    compute_bin_efficiencies,
    summarize_development_zz_bins,
    update_cumulative_multipliers,
)


EDGES = tuple(float(value) for value in range(105, 161, 5))
BIN_NAMES = tuple(
    f"[{int(lower)},{int(upper)}{']' if upper == 160 else ')'}"
    for lower, upper in zip(EDGES, EDGES[1:])
)
TARGETS = {"loose": 0.50, "medium": 0.20, "tight": 0.10}
DROP_TOP4 = (
    "lep1_pt", "lep2_pt", "lep1_eta", "lep2_eta", "lep3_eta",
    "lep4_eta", "pt4l", "deltaR_Z1", "deltaR_Z2", "deltaPhi_ZZ",
)


@pytest.fixture
def policy() -> ReweightingPolicy:
    return ReweightingPolicy(
        mass_bin_edges=EDGES,
        minimum_effective_count=100.0,
        epsilon_floor=1e-6,
        damping=0.5,
        round_factor_bounds=(0.5, 2.0),
        cumulative_bounds=(0.2, 5.0),
        maximum_corrections=5,
        auc_floor=0.80,
        ks_limit=0.10,
    )


def _development_zz(weights_by_bin: dict[str, list[float]] | None = None) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for index, (lower, upper) in enumerate(zip(EDGES, EDGES[1:])):
        weights = (weights_by_bin or {}).get(BIN_NAMES[index], [1.0] * 100)
        mass = upper if upper == 160 else lower
        rows.extend(
            {
                "split": "train" if row % 2 == 0 else "validation",
                "label": 0,
                "m4l": mass,
                "physical_weight": weight,
            }
            for row, weight in enumerate(weights)
        )
    return pd.DataFrame(rows)


def _working_points() -> dict[str, dict[str, float]]:
    return {
        name: {"threshold": threshold, "target_background_efficiency": TARGETS[name]}
        for name, threshold in {"loose": 0.2, "medium": 0.5, "tight": 0.8}.items()
    }


def _study_frame(
    iteration_modes: tuple[str, ...], *, test_reproduces: bool = True
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    event_number = 1

    def append_row(
        *, label: int, mass: float, split: str, scores: tuple[float, ...], test_score: float
    ) -> None:
        nonlocal event_number
        features = {feature: 0.4 for feature in FEATURES}
        for iteration, score in enumerate(scores):
            features[FEATURES[iteration]] = score
        features[FEATURES[6]] = test_score
        if split == "test":
            features["lep1_pt"] = test_score
        rows.append(
            {
                **features,
                "m4l": mass,
                "eventNumber": event_number,
                "channelNumber": 345060 if label else 363490,
                "split": split,
                "label": label,
                "physical_weight": -1.0 if event_number % 17 == 0 else 1.0,
            }
        )
        event_number += 1

    for bin_index, (lower, upper) in enumerate(zip(EDGES, EDGES[1:])):
        for rank in range(100):
            planned = []
            for mode in iteration_modes:
                if mode == "flat":
                    planned.append(0.05 + 0.008 * rank)
                elif mode == "sculpted":
                    planned.append(
                        0.80 + 0.001 * rank
                        if bin_index == 0
                        else 0.05 + 0.004 * rank
                    )
                else:
                    raise AssertionError(f"unknown mode {mode}")
            append_row(
                label=0,
                mass=(lower + upper) / 2.0,
                split="validation" if rank % 3 == 0 else "train",
                scores=tuple(planned),
                test_score=0.5,
            )
    for rank in range(220):
        append_row(
            label=1,
            mass=125.0,
            split="validation" if rank % 3 == 0 else "train",
            scores=tuple(0.95 for _ in iteration_modes),
            test_score=0.5,
        )

    for lower, upper in zip(EDGES, EDGES[1:]):
        for rank in range(50):
            append_row(
                label=0,
                mass=(lower + upper) / 2.0,
                split="test",
                scores=tuple(0.4 for _ in iteration_modes),
                test_score=(0.05 + 0.016 * rank) if test_reproduces else 0.95,
            )
    for _ in range(110):
        append_row(
            label=1,
            mass=125.0,
            split="test",
            scores=tuple(0.95 for _ in iteration_modes),
            test_score=0.95 if test_reproduces else 0.05,
        )
    return pd.DataFrame(rows)


class _StudyClassifier:
    def __init__(self, owner: "_StudyFactory", ordinal: int, parameters: dict[str, object]):
        self.owner = owner
        self.ordinal = ordinal
        self.parameters = parameters
        self.best_iteration = 3
        self._record: dict[str, object] | None = None

    def fit(
        self,
        x: pd.DataFrame,
        y: pd.Series,
        *,
        sample_weight: np.ndarray,
        eval_set=None,
        sample_weight_eval_set=None,
        verbose=None,
    ) -> "_StudyClassifier":
        is_final = eval_set is None
        record = {
            "is_final": is_final,
            "parameters": dict(self.parameters),
            "fit_columns": tuple(x.columns),
            "fit_indices": x.index.copy(),
            "sample_weight": np.asarray(sample_weight).copy(),
            "evaluation_weights": None
            if sample_weight_eval_set is None
            else np.asarray(sample_weight_eval_set[0]).copy(),
            "predict_calls": [],
            "predict_columns": [],
        }
        self.owner.records.append(record)
        self._record = record
        if self.owner.on_first_fit is not None and len(self.owner.records) == 1:
            self.owner.on_first_fit()
        return self

    def predict_proba(self, x: pd.DataFrame) -> np.ndarray:
        assert self._record is not None
        self._record["predict_calls"].append(x.index.copy())
        self._record["predict_columns"].append(tuple(x.columns))
        if self._record["is_final"]:
            score = x["lep1_pt"].to_numpy(dtype=float)
        else:
            iteration = self.ordinal // 30
            score = x[FEATURES[iteration]].to_numpy(dtype=float)
        return np.column_stack([1.0 - score, score])


class _StudyFactory:
    def __init__(self, on_first_fit=None):
        self.created = 0
        self.records: list[dict[str, object]] = []
        self.on_first_fit = on_first_fit

    def __call__(self, **parameters: object) -> _StudyClassifier:
        classifier = _StudyClassifier(self, self.created, dict(parameters))
        self.created += 1
        return classifier


@pytest.fixture
def training_policy():
    return load_training_policy(Path("config/full_training.yaml"))


def _oof_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for bin_index, (lower, upper) in enumerate(zip(EDGES, EDGES[1:])):
        mass = upper if upper == 160 else lower
        for score, count in ((0.1, 10), (0.3, 20), (0.6, 30), (0.9, 40)):
            for _ in range(count):
                rows.append(
                    {
                        "label": 0,
                        "split": "train" if len(rows) % 2 == 0 else "validation",
                        "m4l": mass,
                        "score": score,
                        "physical_weight": 1.0,
                        "rogue_weight": 1000.0 if bin_index == 0 else 1.0,
                    }
                )
    return pd.DataFrame(rows)


def test_summary_assigns_fixed_half_open_bins_and_includes_160_endpoint(policy):
    """Changing the final endpoint or a half-open boundary misplaces ZZ events."""
    development = _development_zz()
    before = development.copy(deep=True)

    summary = summarize_development_zz_bins(development, policy)

    assert tuple(summary.index) == BIN_NAMES
    assert summary.index.name == "mass_bin"
    assert summary["lower_edge"].tolist() == list(EDGES[:-1])
    assert summary["upper_edge"].tolist() == list(EDGES[1:])
    assert summary["raw_count"].tolist() == [100] * 11
    assert summary["effective_count"].tolist() == pytest.approx([100.0] * 11)
    pd.testing.assert_frame_equal(development, before)


@pytest.mark.parametrize(
    ("transform", "message"),
    [
        (lambda frame: frame.assign(m4l=104.999), "configured mass range"),
        (lambda frame: frame.assign(m4l=160.001), "configured mass range"),
        (lambda frame: frame.assign(m4l=np.nan), "finite"),
        (lambda frame: frame.drop(columns="label"), "missing required columns"),
        (lambda frame: frame.drop(columns="physical_weight"), "missing required columns"),
        (lambda frame: frame.assign(split="test"), "development"),
    ],
)
def test_summary_rejects_invalid_development_inputs(policy, transform, message):
    """Accepting invalid masses or held-out rows invalidates fixed-bin evidence."""
    with pytest.raises(ValueError, match=message):
        summarize_development_zz_bins(transform(_development_zz()), policy)


@pytest.mark.parametrize(
    "edges",
    [
        (105.0, 110.0, 115.0, 120.0, 125.0, 130.0, 135.0, 140.0, 145.0, 150.0, 155.0, 155.0),
        (105.0, 110.0, 115.0, 120.0, 125.0, 130.0, 135.0, 140.0, 145.0, 150.0, 155.0, 165.0),
    ],
)
def test_summary_rejects_edges_other_than_the_frozen_eleven_bins(policy, edges):
    """Permitting a changed edge would allow result-driven binning."""
    changed = ReweightingPolicy(
        **{**policy.__dict__, "mass_bin_edges": edges}
    )
    with pytest.raises(ValueError, match="mass_bin_edges"):
        summarize_development_zz_bins(_development_zz(), changed)


def test_summary_uses_absolute_weight_effective_count_and_exact_minimum(policy):
    """Using raw counts or signed sums would let statistically weak bins pass."""
    nearly_one = 0.0
    target = 99.999
    # (99 + x)^2 / (99 + x^2) = target; choose the root near one.
    nearly_one = (198.0 + math.sqrt(198.0**2 - 4.0 * (target - 1.0) * (99.0 * target - 9801.0))) / (2.0 * (target - 1.0))
    weights = {BIN_NAMES[0]: [1.0] * 99 + [nearly_one]}
    below = _development_zz(weights)

    with pytest.raises(ValueError, match="minimum effective count"):
        summarize_development_zz_bins(below, policy)

    summary = summarize_development_zz_bins(_development_zz(), policy)
    assert summary.loc[BIN_NAMES[0], "effective_count"] == pytest.approx(100.0)
    assert summary.loc[BIN_NAMES[0], "absolute_weight_sum"] == pytest.approx(100.0)


def test_compute_bin_efficiencies_uses_original_absolute_physical_weights(policy):
    """Using a fitting or auxiliary weight column changes the published efficiencies."""
    oof = _oof_rows()
    before = oof.copy(deep=True)

    efficiencies = compute_bin_efficiencies(oof, _working_points(), policy)

    assert list(efficiencies.index.names) == ["mass_bin", "working_point"]
    assert tuple(efficiencies.index.get_level_values("mass_bin").unique()) == BIN_NAMES
    assert tuple(efficiencies.index.get_level_values("working_point").unique()) == tuple(TARGETS)
    loose = efficiencies.loc[(BIN_NAMES[0], "loose")]
    medium = efficiencies.loc[(BIN_NAMES[0], "medium")]
    tight = efficiencies.loc[(BIN_NAMES[0], "tight")]
    assert loose[["numerator", "denominator", "efficiency"]].tolist() == pytest.approx([90.0, 100.0, 0.9])
    assert medium[["numerator", "denominator", "efficiency"]].tolist() == pytest.approx([70.0, 100.0, 0.7])
    assert tight[["numerator", "denominator", "efficiency"]].tolist() == pytest.approx([40.0, 100.0, 0.4])
    assert loose["effective_count"] == pytest.approx(100.0)
    assert loose["standard_error"] == pytest.approx(math.sqrt(0.9 * 0.1 / 100.0))
    pd.testing.assert_frame_equal(oof, before)


@pytest.mark.parametrize(
    "points",
    [
        {"loose": {"threshold": 0.2}, "medium": {"threshold": 0.5}},
        {**_working_points(), "unexpected": {"threshold": 0.9}},
    ],
)
def test_compute_bin_efficiencies_requires_exact_working_point_keys(policy, points):
    """Missing or extra cuts make the frozen geometric mean undefined."""
    with pytest.raises(ValueError, match="working-point keys"):
        compute_bin_efficiencies(_oof_rows(), points, policy)


@pytest.mark.parametrize(
    ("points", "message"),
    [
        (
            {
                **_working_points(),
                "loose": {"threshold": 0.2},
            },
            "target_background_efficiency",
        ),
        (
            {
                **_working_points(),
                "medium": {"threshold": 0.5, "target_background_efficiency": 0.50},
            },
            "target_background_efficiency",
        ),
        (
            dict(reversed(tuple(_working_points().items()))),
            "working-point order",
        ),
        (
            {
                "loose": {"threshold": 0.8, "target_background_efficiency": 0.50},
                "medium": {"threshold": 0.5, "target_background_efficiency": 0.20},
                "tight": {"threshold": 0.2, "target_background_efficiency": 0.10},
            },
            "monotonic",
        ),
    ],
)
def test_compute_bin_efficiencies_rejects_nonfrozen_working_point_metadata_before_calculation(
    policy, points, message
):
    """Changed targets or cut order would make the diagnostic non-predeclared."""
    with pytest.raises(ValueError, match=message):
        compute_bin_efficiencies(_oof_rows(), points, policy)


def test_compute_bin_efficiencies_rejects_nonfinite_scores(policy):
    """A NaN score must not silently change selected bin weight."""
    oof = _oof_rows()
    oof.loc[oof.index[0], "score"] = np.inf
    with pytest.raises(ValueError, match="finite"):
        compute_bin_efficiencies(oof, _working_points(), policy)


def test_update_cumulative_multipliers_uses_exact_damped_geometric_formula(policy):
    """Reversing the ratio would lower an over-selected bin's next multiplier."""
    efficiencies = pd.DataFrame(
        [
            {"mass_bin": mass_bin, "working_point": point, "efficiency": efficiency}
            for mass_bin, values in {
                BIN_NAMES[0]: (0.75, 0.30, 0.15),
                **{name: (0.50, 0.20, 0.10) for name in BIN_NAMES[1:]},
            }.items()
            for point, efficiency in zip(TARGETS, values)
        ]
    ).set_index(["mass_bin", "working_point"])
    current = pd.Series(1.0, index=list(reversed(BIN_NAMES)), name="cumulative_multiplier")

    updated = update_cumulative_multipliers(efficiencies.iloc[::-1], current, policy)

    expected_round = math.exp(
        0.5
        / 3.0
        * sum(math.log((observed + 1e-6) / (target + 1e-6)) for observed, target in zip((0.75, 0.30, 0.15), TARGETS.values()))
    )
    assert tuple(updated.index) == BIN_NAMES
    assert updated.name == "cumulative_multiplier"
    assert updated.loc[BIN_NAMES[0]] == pytest.approx(expected_round)
    assert updated.loc[BIN_NAMES[1]] == pytest.approx(1.0)
    assert np.isfinite(updated.to_numpy()).all()
    assert (updated > 0.0).all()


def test_update_uses_captured_frozen_targets_after_module_global_rebinding(policy, monkeypatch):
    """Rebinding a module target map must not change the next multiplier."""
    efficiencies = pd.DataFrame(
        [
            {"mass_bin": mass_bin, "working_point": point, "efficiency": efficiency}
            for mass_bin, values in {
                BIN_NAMES[0]: (0.75, 0.30, 0.15),
                **{name: (0.50, 0.20, 0.10) for name in BIN_NAMES[1:]},
            }.items()
            for point, efficiency in zip(TARGETS, values)
        ]
    ).set_index(["mass_bin", "working_point"])
    monkeypatch.setattr(
        mass_bin_reweighting,
        "_WORKING_POINT_TARGETS",
        {"loose": 0.99, "medium": 0.98, "tight": 0.97},
    )

    updated = update_cumulative_multipliers(
        efficiencies, pd.Series(1.0, index=BIN_NAMES), policy
    )

    expected = math.exp(
        0.5
        / 3.0
        * sum(
            math.log((observed + 1e-6) / (target + 1e-6))
            for observed, target in zip((0.75, 0.30, 0.15), (0.50, 0.20, 0.10))
        )
    )
    assert updated.loc[BIN_NAMES[0]] == pytest.approx(expected)


def test_update_cumulative_multipliers_decreases_underselected_and_clips_each_stage(policy):
    """Omitting round or cumulative clipping permits unbounded corrections."""
    efficiencies = pd.DataFrame(
        [
            {"mass_bin": mass_bin, "working_point": point, "efficiency": efficiency}
            for mass_bin, values in {
                BIN_NAMES[0]: (0.0, 0.0, 0.0),
                BIN_NAMES[1]: (1.0, 1.0, 1.0),
                BIN_NAMES[2]: (0.25, 0.10, 0.05),
                BIN_NAMES[3]: (0.0, 0.0, 0.0),
                BIN_NAMES[4]: (1.0, 1.0, 1.0),
                **{name: (0.50, 0.20, 0.10) for name in BIN_NAMES[5:]},
            }.items()
            for point, efficiency in zip(TARGETS, values)
        ]
    ).set_index(["mass_bin", "working_point"])
    current = pd.Series(1.0, index=BIN_NAMES)
    current.loc[BIN_NAMES[3]] = 0.2
    current.loc[BIN_NAMES[4]] = 5.0

    updated = update_cumulative_multipliers(efficiencies, current, policy)

    assert updated.loc[BIN_NAMES[0]] == pytest.approx(0.5)
    assert updated.loc[BIN_NAMES[1]] == pytest.approx(2.0)
    assert 0.5 < updated.loc[BIN_NAMES[2]] < 1.0
    assert updated.loc[BIN_NAMES[3]] == pytest.approx(0.2)
    assert updated.loc[BIN_NAMES[4]] == pytest.approx(5.0)


def test_study_refits_all_candidates_and_applies_the_exact_first_update(
    policy, training_policy
):
    """Skipping a candidate or changing the Task 2 update changes iteration one."""
    frame = _study_frame(("sculpted", "flat"))
    before = frame.copy(deep=True)
    factory = _StudyFactory()

    outcome = mass_bin_reweighting.run_mass_bin_reweighting_study(
        frame, training_policy, policy, model_factory=factory
    )

    assert outcome.selected_iteration == 1
    assert [evidence.iteration for evidence in outcome.iterations] == [0, 1]
    assert tuple(outcome.iterations[0].cumulative_multipliers.values()) == pytest.approx(
        [1.0] * 11
    )
    expected = update_cumulative_multipliers(
        outcome.iterations[0].bin_efficiencies,
        pd.Series(1.0, index=BIN_NAMES),
        policy,
    )
    assert dict(outcome.iterations[1].cumulative_multipliers) == pytest.approx(
        expected.to_dict()
    )
    cv_records = [record for record in factory.records if not record["is_final"]]
    assert len(cv_records) == 2 * 6 * 5
    assert Counter(
        (
            record["parameters"]["max_depth"],
            record["parameters"]["min_child_weight"],
        )
        for record in cv_records
    ) == Counter(
        {
            (depth, child): 10
            for depth in (2, 3, 4)
            for child in (5, 20)
        }
    )
    assert all(record["fit_columns"] == tuple(FEATURES) for record in factory.records)
    assert all("m4l" not in record["fit_columns"] for record in factory.records)
    with pytest.raises(TypeError):
        outcome.iterations[0].working_points["loose"]["threshold"] = -1.0
    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize("features", [DROP_TOP4, tuple(FEATURES)])
def test_study_passes_only_approved_features_to_every_fit_and_predict(features):
    """Using a broader or reordered profile would invalidate the sealed study."""
    factory = _StudyFactory()
    outcome = mass_bin_reweighting.run_mass_bin_reweighting_study(
        _study_frame(("flat",)),
        load_training_policy("config/full_training.yaml"),
        ReweightingPolicy(
            mass_bin_edges=EDGES,
            minimum_effective_count=100.0,
            epsilon_floor=1e-6,
            damping=0.5,
            round_factor_bounds=(0.5, 2.0),
            cumulative_bounds=(0.2, 5.0),
            maximum_corrections=5,
            auc_floor=0.80,
            ks_limit=0.10,
        ),
        features=features,
        model_factory=factory,
    )

    assert outcome.status == "eligible_iteration_test_reproduced"
    assert factory.records
    assert all(record["fit_columns"] == features for record in factory.records)
    assert all(
        columns == features
        for record in factory.records
        for columns in record["predict_columns"]
    )


@pytest.mark.parametrize(
    "features",
    [
        tuple(FEATURES[1:]),
        tuple(FEATURES) + ("unexpected_feature",),
        tuple(reversed(DROP_TOP4)),
        DROP_TOP4 + (DROP_TOP4[0],),
        list(DROP_TOP4),
        DROP_TOP4 + ("m4l",),
        *(
            DROP_TOP4[:index] + (feature,) + DROP_TOP4[index:]
            for index, feature in enumerate(
                ("lep3_pt", "lep4_pt", "deltaPhi_Z1", "deltaPhi_Z2")
            )
        ),
        tuple(FEATURES[::2]),
        tuple(FEATURES[:10]),
    ],
)
def test_approved_features_reject_noncanonical_profiles(features):
    """Any profile other than the two literal approvals must be rejected."""
    with pytest.raises(ValueError, match="approved reweighting profile"):
        mass_bin_reweighting.approved_reweighting_features(features)


def test_feature_profile_rebinding_is_rejected_before_split_or_model_access(
    policy, training_policy, monkeypatch
):
    """A rebound public feature profile must not change the entry-time approvals."""
    class SplitAccessTrap(pd.DataFrame):
        @property
        def _constructor(self):
            return SplitAccessTrap

        def __getitem__(self, key):
            if key == "split":
                pytest.fail("rebound feature profile reached frame split access")
            return super().__getitem__(key)

    monkeypatch.setattr(
        mass_bin_reweighting, "FEATURES", ("altered_feature_profile",)
    )

    with pytest.raises(ValueError, match="approved reweighting profile"):
        mass_bin_reweighting.run_mass_bin_reweighting_study(
            SplitAccessTrap(_study_frame(("flat",))),
            training_policy,
            policy,
            features=mass_bin_reweighting.FEATURES,
            model_factory=lambda **parameters: pytest.fail(
                "rebound feature profile reached model factory"
            ),
        )


def test_feature_profile_spoofing_subclass_is_rejected_before_split_or_factory(
    policy, training_policy
):
    """A tuple subclass must not spoof approval with custom equality."""
    class Spoof(tuple):
        def __eq__(self, other):
            return True

    class SplitAccessTrap(pd.DataFrame):
        @property
        def _constructor(self):
            return SplitAccessTrap

        def __getitem__(self, key):
            if key == "split":
                pytest.fail("spoofed feature profile reached frame split access")
            return super().__getitem__(key)

    with pytest.raises(ValueError, match="approved reweighting profile"):
        mass_bin_reweighting.run_mass_bin_reweighting_study(
            SplitAccessTrap(_study_frame(("flat",))),
            training_policy,
            policy,
            features=Spoof(("m4l",)),
            model_factory=lambda **parameters: pytest.fail(
                "spoofed feature profile reached model factory"
            ),
        )


def test_feature_profile_str_subclasses_are_rejected_before_split_or_factory(
    policy, training_policy
):
    """String subclasses in a built-in tuple must not spoof canonical names."""
    class SpoofStr(str):
        def __eq__(self, other):
            return True

    class SplitAccessTrap(pd.DataFrame):
        @property
        def _constructor(self):
            return SplitAccessTrap

        def __getitem__(self, key):
            if key == "split":
                pytest.fail("spoofed string features reached frame split access")
            return super().__getitem__(key)

    spoofed = tuple(
        SpoofStr(name)
        for name in (
            "m4l", "lep3_pt", "lep4_pt", "mZ1", "mZ2",
            "eventNumber", "channelNumber", "physical_weight", "split", "label",
        )
    )
    assert type(spoofed) is tuple

    with pytest.raises(ValueError, match="approved reweighting profile"):
        mass_bin_reweighting.run_mass_bin_reweighting_study(
            SplitAccessTrap(_study_frame(("flat",))),
            training_policy,
            policy,
            features=spoofed,
            model_factory=lambda **parameters: pytest.fail(
                "spoofed string features reached model factory"
            ),
        )


@pytest.mark.parametrize(
    ("modes", "expected_iterations", "expected_selected"),
    [
        (("flat",), [0], 0),
        (("sculpted", "sculpted", "flat"), [0, 1, 2], 2),
    ],
)
def test_study_stops_at_the_first_eligible_iteration(
    policy, training_policy, modes, expected_iterations, expected_selected
):
    """Continuing after eligibility would make later OOF evidence influence selection."""
    factory = _StudyFactory()

    outcome = mass_bin_reweighting.run_mass_bin_reweighting_study(
        _study_frame(modes), training_policy, policy, model_factory=factory
    )

    assert [item.iteration for item in outcome.iterations] == expected_iterations
    assert outcome.selected_iteration == expected_selected
    assert len([record for record in factory.records if record["is_final"]]) == 1


def test_eligibility_boundaries_pass_auc_and_ks_but_require_strict_signal_gain(policy):
    """Using strict AUC/KS or non-strict signal comparison changes the frozen gate."""
    equal_reasons = mass_bin_reweighting._eligibility_reasons(
        weighted_auc=0.80,
        zz_ks_distances={name: 0.10 for name in TARGETS},
        signal_efficiencies={name: TARGETS[name] for name in TARGETS},
        achieved_zz_efficiencies=dict(TARGETS),
        policy=policy,
    )
    passing_reasons = mass_bin_reweighting._eligibility_reasons(
        weighted_auc=0.80,
        zz_ks_distances={name: 0.10 for name in TARGETS},
        signal_efficiencies={name: TARGETS[name] + 1e-12 for name in TARGETS},
        achieved_zz_efficiencies=dict(TARGETS),
        policy=policy,
    )

    assert equal_reasons == tuple(
        f"{name}_signal_efficiency_not_strictly_greater" for name in TARGETS
    )
    assert passing_reasons == ()


def _poison_test_analysis_columns(frame: pd.DataFrame) -> pd.DataFrame:
    poisoned = frame.copy(deep=True)
    test_rows = poisoned["split"] == "test"
    poisoned.loc[test_rows, [name for name in poisoned.columns if name != "split"]] = np.nan
    return poisoned


def test_no_eligible_iteration_never_validates_or_scores_poisoned_test(
    policy, training_policy, monkeypatch
):
    """Opening test after six failed iterations would make NaN test values observable."""
    factory = _StudyFactory()
    monkeypatch.setattr(
        mass_bin_reweighting,
        "validate_mc_frame",
        lambda frame: pytest.fail("complete-frame validation opened test"),
    )

    outcome = mass_bin_reweighting.run_mass_bin_reweighting_study(
        _poison_test_analysis_columns(_study_frame(("sculpted",) * 6)),
        training_policy,
        policy,
        model_factory=factory,
    )

    assert outcome.status == "no_eligible_iteration"
    assert len(outcome.iterations) == 6
    assert outcome.selected_iteration is None
    assert outcome.selected_oof_scores is None
    assert outcome.model is None
    assert outcome.test_scores is None
    assert outcome.test_metrics is None
    assert not any(record["is_final"] for record in factory.records)


def test_insufficient_statistics_returns_before_any_model_or_test_access(
    policy, training_policy, monkeypatch
):
    """A weak fixed bin must stop before factory construction or test validation."""
    frame = _study_frame(("flat",))
    weak_row = frame.index[
        (frame["split"] != "test")
        & (frame["label"] == 0)
        & (frame["m4l"] == 107.5)
    ][0]
    frame = _poison_test_analysis_columns(frame.drop(index=weak_row))
    factory = _StudyFactory()
    monkeypatch.setattr(
        mass_bin_reweighting,
        "validate_mc_frame",
        lambda frame: pytest.fail("complete-frame validation opened test"),
    )

    outcome = mass_bin_reweighting.run_mass_bin_reweighting_study(
        frame, training_policy, policy, model_factory=factory
    )

    assert outcome.status == "insufficient_bin_statistics"
    assert outcome.iterations == ()
    assert outcome.selected_iteration is None
    assert outcome.model is None
    assert outcome.test_scores is None
    assert outcome.test_metrics is None
    assert factory.created == 0


def test_empty_fixed_bin_preserves_all_effective_count_gate_evidence(
    policy, training_policy
):
    frame = _study_frame(("flat",))
    frame = frame.loc[
        ~(
            frame["split"].ne("test")
            & frame["label"].eq(0)
            & frame["m4l"].eq(107.5)
        )
    ]

    outcome = mass_bin_reweighting.run_mass_bin_reweighting_study(
        frame, training_policy, policy, model_factory=_StudyFactory()
    )

    assert outcome.status == "insufficient_bin_statistics"
    assert tuple(outcome.fixed_bin_statistics.index) == BIN_NAMES
    assert outcome.fixed_bin_statistics.loc[BIN_NAMES[0], "effective_count"] == 0.0


def test_eligible_study_fits_once_scores_test_once_and_uses_oof_frozen_thresholds(
    policy, training_policy
):
    """A refit retry or test-derived cut would violate the one-time terminal."""
    factory = _StudyFactory()

    outcome = mass_bin_reweighting.run_mass_bin_reweighting_study(
        _study_frame(("flat",)), training_policy, policy, model_factory=factory
    )

    final_records = [record for record in factory.records if record["is_final"]]
    assert len(final_records) == 1
    assert len(final_records[0]["predict_calls"]) == 1
    assert set(outcome.test_scores.index) == set(final_records[0]["predict_calls"][0])
    assert outcome.status == "eligible_iteration_test_reproduced"
    assert outcome.selected_iteration == 0
    assert len(outcome.iterations) == 1
    assert {
        name: point["threshold"]
        for name, point in outcome.test_metrics["working_points"].items()
    } == {
        name: point["threshold"]
        for name, point in outcome.iterations[0].working_points.items()
    }


def test_published_iteration_and_score_frames_are_read_only(policy, training_policy):
    """A caller mutation must not rewrite frozen development or test evidence."""
    outcome = mass_bin_reweighting.run_mass_bin_reweighting_study(
        _study_frame(("flat",)),
        training_policy,
        policy,
        model_factory=_StudyFactory(),
    )

    for published in (
        outcome.iterations[0].bin_efficiencies,
        outcome.selected_oof_scores,
        outcome.test_scores,
    ):
        first_value = published.iloc[0, 0]
        with pytest.raises(TypeError, match="read-only"):
            published.iloc[0, 0] = -999.0
        with pytest.raises(TypeError, match="read-only"):
            published["injected"] = 1.0
        with pytest.raises(TypeError, match="read-only"):
            published.columns = [f"changed_{index}" for index in range(len(published.columns))]
        with pytest.raises(TypeError, match="read-only"):
            published.index = pd.RangeIndex(len(published))
        iloc_column = published.iloc[:, 0]
        named_column = published[published.columns[0]]
        assert not np.shares_memory(iloc_column.to_numpy(), published.to_numpy())
        assert not np.shares_memory(named_column.to_numpy(), published.to_numpy())
        iloc_column.iloc[0] = -999.0
        named_column.iloc[0] = -999.0
        assert published.iloc[0, 0] == first_value


def test_published_frames_close_axis_and_indexer_mutation_bypasses(
    policy, training_policy
):
    """Exposed pandas axes or indexer internals must not rewrite evidence."""
    outcome = mass_bin_reweighting.run_mass_bin_reweighting_study(
        _study_frame(("flat",)),
        training_policy,
        policy,
        model_factory=_StudyFactory(),
    )

    for published in (
        outcome.iterations[0].bin_efficiencies,
        outcome.selected_oof_scores,
        outcome.test_scores,
    ):
        with pytest.raises(TypeError, match="read-only"):
            published.loc[published.index[0], published.columns[0]] = -999.0
        with pytest.raises(TypeError, match="read-only"):
            published.iloc[0, 0] = -999.0
        with pytest.raises(TypeError, match="read-only"):
            published.at[published.index[0], published.columns[0]] = -999.0
        with pytest.raises(TypeError, match="read-only"):
            published.iat[0, 0] = -999.0
        with pytest.raises(AttributeError):
            published.iloc._setitem_with_indexer((0, 0), -999.0, name="iloc")
        with pytest.raises(ValueError, match="read-only"):
            published.columns.values[0] = "mutated"
        with pytest.raises(ValueError, match="read-only"):
            published.index.values[0] = "mutated"


def _invalid_training_policies(training_policy):
    common = dict(training_policy.common_parameters)
    changed_common_policies = tuple(
        replace(
            training_policy,
            common_parameters=MappingProxyType(
                {
                    **common,
                    name: (
                        value + 1
                        if type(value) is int
                        else value + 0.01
                        if type(value) is float
                        else f"{value}_changed"
                    ),
                }
            ),
        )
        for name, value in common.items()
    )
    missing_common_policies = tuple(
        replace(
            training_policy,
            common_parameters=MappingProxyType(
                {other: value for other, value in common.items() if other != name}
            ),
        )
        for name in common
    )
    extra_common = {**common, "unexpected": 1}
    reordered_common = dict(reversed(tuple(common.items())))
    candidates = training_policy.candidates
    return (
        replace(training_policy, folds=4),
        replace(training_policy, random_seed=7),
        replace(training_policy, n_jobs=1),
        replace(training_policy, candidates=tuple(reversed(candidates))),
        replace(
            training_policy,
            candidates=(CandidateSpec("depth99_child0", 99, 0.01), *candidates[1:]),
        ),
        *changed_common_policies,
        *missing_common_policies,
        replace(training_policy, common_parameters=MappingProxyType(extra_common)),
        replace(training_policy, common_parameters=MappingProxyType(reordered_common)),
        replace(
            training_policy,
            working_points=MappingProxyType(
                {"loose": 0.51, "medium": 0.20, "tight": 0.10}
            ),
        ),
        replace(
            training_policy,
            working_points=MappingProxyType(
                {"tight": 0.10, "medium": 0.20, "loose": 0.50}
            ),
        ),
        replace(training_policy, auc_gap_limit=0.06),
        replace(training_policy, ks_distance_limit=0.11),
        replace(training_policy, mass_bins_gev=tuple(reversed(training_policy.mass_bins_gev))),
    )


def test_study_rejects_every_noncanonical_training_policy_before_frame_access(
    policy, training_policy
):
    """Caller policy substitution must fail before development or test is observed."""
    class SplitAccessTrap(pd.DataFrame):
        @property
        def _constructor(self):
            return SplitAccessTrap

        def __getitem__(self, key):
            if key == "split":
                pytest.fail("invalid policy reached frame split access")
            return super().__getitem__(key)

    trapped = SplitAccessTrap(_study_frame(("flat",)))

    for changed in _invalid_training_policies(training_policy):
        with pytest.raises(ValueError, match="frozen training policy"):
            mass_bin_reweighting.run_mass_bin_reweighting_study(
                trapped,
                changed,
                policy,
                model_factory=lambda **parameters: pytest.fail(
                    "invalid policy reached model factory"
                ),
            )


def test_study_rejects_policy_matching_rebound_reference_globals_before_frame_access(
    policy, training_policy, monkeypatch
):
    """Rebinding policy-reference globals must not redefine the sealed study."""
    class SplitAccessTrap(pd.DataFrame):
        @property
        def _constructor(self):
            return SplitAccessTrap

        def __getitem__(self, key):
            if key == "split":
                pytest.fail("rebound references reached frame split access")
            return super().__getitem__(key)

    arbitrary_candidates = tuple(
        CandidateSpec(f"arbitrary_{index}", 90 + index, 0.01 + index)
        for index in range(6)
    )
    arbitrary_common = tuple(
        (
            name,
            0.99 if name == "learning_rate" else value,
        )
        for name, value in training_policy.common_parameters.items()
    )
    monkeypatch.setattr(
        mass_bin_reweighting, "_FROZEN_CANDIDATES", arbitrary_candidates
    )
    monkeypatch.setattr(
        mass_bin_reweighting,
        "_FROZEN_COMMON_PARAMETER_ITEMS",
        arbitrary_common,
    )
    substituted = replace(
        training_policy,
        candidates=arbitrary_candidates,
        common_parameters=MappingProxyType(dict(arbitrary_common)),
    )

    with pytest.raises(ValueError, match="frozen training policy"):
        mass_bin_reweighting.run_mass_bin_reweighting_study(
            SplitAccessTrap(_study_frame(("flat",))),
            substituted,
            policy,
            model_factory=lambda **parameters: pytest.fail(
                "rebound references reached model factory"
            ),
        )


def test_study_signature_has_no_result_or_gate_injection_paths(policy, training_policy):
    """An extra public override could substitute selection for internally derived evidence."""
    operation = mass_bin_reweighting.run_mass_bin_reweighting_study
    signature = inspect.signature(operation)

    assert tuple(signature.parameters) == (
        "frame",
        "training_policy",
        "reweighting_policy",
        "features",
        "model_factory",
    )
    assert signature.parameters["features"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["model_factory"].kind is inspect.Parameter.KEYWORD_ONLY
    for forbidden in (
        "selected_iteration",
        "thresholds",
        "development_result",
        "multipliers",
        "auc_floor",
        "ks_limit",
    ):
        with pytest.raises(TypeError):
            operation(
                _study_frame(("flat",)),
                training_policy,
                policy,
                **{forbidden: object()},
            )


def test_study_uses_entry_captured_policy_after_module_constant_rebinding(
    policy, training_policy, monkeypatch
):
    """Consulting rebound module constants mid-study would alter or abort selection."""
    def rebind_constants() -> None:
        monkeypatch.setattr(mass_bin_reweighting, "_FIXED_EDGES", (0.0, 1.0))
        monkeypatch.setattr(
            mass_bin_reweighting,
            "_WORKING_POINT_TARGETS",
            (("loose", 0.99), ("medium", 0.98), ("tight", 0.97)),
        )

    outcome = mass_bin_reweighting.run_mass_bin_reweighting_study(
        _study_frame(("flat",)),
        training_policy,
        policy,
        model_factory=_StudyFactory(on_first_fit=rebind_constants),
    )

    assert outcome.status == "eligible_iteration_test_reproduced"
    assert tuple(outcome.iterations[0].cumulative_multipliers) == BIN_NAMES
    assert tuple(outcome.iterations[0].working_points) == tuple(TARGETS)


def _selection_fingerprint(outcome) -> tuple[object, ...]:
    selected = outcome.iterations[outcome.selected_iteration]
    return (
        outcome.selected_iteration,
        selected.candidate_name,
        selected.final_tree_count,
        tuple(selected.cumulative_multipliers.items()),
        tuple(
            (name, point["threshold"]) for name, point in selected.working_points.items()
        ),
    )


def test_test_evidence_changes_only_test_terminal_and_metrics(policy, training_policy):
    """Test labels or scores must never feed back into the frozen development choice."""
    reproduced = mass_bin_reweighting.run_mass_bin_reweighting_study(
        _study_frame(("flat",), test_reproduces=True),
        training_policy,
        policy,
        model_factory=_StudyFactory(),
    )
    failed = mass_bin_reweighting.run_mass_bin_reweighting_study(
        _study_frame(("flat",), test_reproduces=False),
        training_policy,
        policy,
        model_factory=_StudyFactory(),
    )

    assert reproduced.status == "eligible_iteration_test_reproduced"
    assert failed.status == "test_nonreproduction"
    assert _selection_fingerprint(reproduced) == _selection_fingerprint(failed)
    assert reproduced.test_metrics["weighted_auc"] == pytest.approx(1.0)
    assert failed.test_metrics["weighted_auc"] == pytest.approx(0.0)
    pd.testing.assert_frame_equal(
        reproduced.iterations[0].bin_efficiencies,
        failed.iterations[0].bin_efficiencies,
    )
