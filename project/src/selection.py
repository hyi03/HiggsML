from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Literal, Mapping, Sequence

import numpy as np

from .reconstruction import (
    FourLeptonCandidate,
    normalize_leptons,
    reconstruct_candidate,
)


SELECTION_STAGES = (
    "read",
    "exactly_four_leptons",
    "allowed_lepton_types",
    "lepton_pt",
    "lepton_eta",
    "zero_charge",
    "valid_sfos_pairing",
    "all_sfos_mass",
    "z1_mass_window",
    "z2_mass_window",
    "m4l_analysis_window",
    "selected",
)

ENHANCED_SELECTION_STAGES = (
    "read",
    "trigger",
    "allowed_lepton_types",
    "tight_identification",
    "track_isolation",
    "calorimeter_isolation",
    "transverse_impact_parameter",
    "longitudinal_impact_parameter",
    "exactly_four_good_leptons",
    "trigger_match",
    "lepton_pt",
    "lepton_eta",
    "zero_charge",
    "valid_sfos_pairing",
    "all_sfos_mass",
    "z1_mass_window",
    "z2_mass_window",
    "m4l_analysis_window",
    "selected",
)


def _finite_nonnegative(value: Any, field: str) -> float:
    number = float(value)
    if not isfinite(number) or number < 0:
        raise ValueError(f"{field} must be finite and non-negative")
    return number


def _finite_positive(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite positive number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite positive number") from exc
    if not isfinite(number) or number <= 0:
        raise ValueError(f"{field} must be a finite positive number")
    return number


def _required_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be boolean")
    return value


def _window(value: Any, field: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{field} must contain [lower, upper]")
    lower = _finite_nonnegative(value[0], f"{field}[0]")
    upper = _finite_nonnegative(value[1], f"{field}[1]")
    if lower >= upper:
        raise ValueError(f"{field} lower bound must be below upper bound")
    return lower, upper


@dataclass(frozen=True)
class SlidingZ2Config:
    low_m4l_gev: float
    high_m4l_gev: float
    low_min_gev: float
    high_min_gev: float


@dataclass(frozen=True)
class LeptonQualityConfig:
    enabled: bool
    require_event_trigger: bool
    require_trigger_match: bool
    require_tight_id: bool
    track_isolation_max: float
    calo_isolation_max: float
    electron_d0sig_max: float
    muon_d0sig_max: float
    z0_sintheta_max_mm: float

    @classmethod
    def disabled(cls) -> "LeptonQualityConfig":
        return cls(False, False, False, False, 0.0, 0.0, 0.0, 0.0, 0.0)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LeptonQualityConfig":
        enabled = _required_bool(value["enabled"], "lepton_quality.enabled")
        config = cls(
            enabled=enabled,
            require_event_trigger=_required_bool(
                value["require_event_trigger"],
                "lepton_quality.require_event_trigger",
            ),
            require_trigger_match=_required_bool(
                value["require_trigger_match"],
                "lepton_quality.require_trigger_match",
            ),
            require_tight_id=_required_bool(
                value["require_tight_id"], "lepton_quality.require_tight_id"
            ),
            track_isolation_max=_finite_positive(
                value["track_isolation_max"], "lepton_quality.track_isolation_max"
            ),
            calo_isolation_max=_finite_positive(
                value["calo_isolation_max"], "lepton_quality.calo_isolation_max"
            ),
            electron_d0sig_max=_finite_positive(
                value["electron_d0sig_max"], "lepton_quality.electron_d0sig_max"
            ),
            muon_d0sig_max=_finite_positive(
                value["muon_d0sig_max"], "lepton_quality.muon_d0sig_max"
            ),
            z0_sintheta_max_mm=_finite_positive(
                value["z0_sintheta_max_mm"],
                "lepton_quality.z0_sintheta_max_mm",
            ),
        )
        if config.track_isolation_max >= 1:
            raise ValueError("lepton_quality.track_isolation_max must be below 1")
        if config.calo_isolation_max >= 1:
            raise ValueError("lepton_quality.calo_isolation_max must be below 1")
        return config


@dataclass(frozen=True)
class SelectionConfig:
    require_exactly_four_leptons: bool
    allowed_lepton_types: tuple[int, ...]
    lepton_pt_thresholds_gev: tuple[float, float, float, float]
    electron_max_abs_eta: float
    muon_max_abs_eta: float
    require_zero_charge: bool
    min_all_sfos_mass_gev: float
    z1_mass_window_gev: tuple[float, float]
    z2_min_mode: Literal["fixed", "sliding"]
    z2_fixed_min_gev: float
    z2_max_gev: float
    z2_sliding: SlidingZ2Config
    m4l_window_gev: tuple[float, float]
    lepton_quality: LeptonQualityConfig

    @property
    def stages(self) -> tuple[str, ...]:
        return ENHANCED_SELECTION_STAGES if self.lepton_quality.enabled else SELECTION_STAGES

    @property
    def required_canonical_branches(self) -> tuple[str, ...]:
        quality = self.lepton_quality
        if not quality.enabled:
            return ()
        branches: list[str] = []
        if quality.require_event_trigger:
            branches.extend(("trigE", "trigM"))
        if quality.require_trigger_match:
            branches.append("lep_isTrigMatched")
        if quality.require_tight_id:
            branches.append("lep_isTightID")
        branches.extend(
            ("lep_track_iso", "lep_calo_iso", "lep_d0sig", "lep_z0")
        )
        return tuple(branches)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SelectionConfig":
        require_exactly_four = value["require_exactly_four_leptons"]
        if require_exactly_four is not True:
            raise ValueError("require_exactly_four_leptons must be true")

        allowed = tuple(abs(int(item)) for item in value["allowed_lepton_types"])
        if not allowed or not set(allowed) <= {11, 13}:
            raise ValueError("allowed_lepton_types may contain only 11 and 13")

        raw_pt = value["lepton_pt_thresholds_gev"]
        if not isinstance(raw_pt, (list, tuple)) or len(raw_pt) != 4:
            raise ValueError("lepton_pt_thresholds_gev must contain four values")
        pt = tuple(
            _finite_nonnegative(item, f"lepton_pt_thresholds_gev[{index}]")
            for index, item in enumerate(raw_pt)
        )
        if any(first < second for first, second in zip(pt, pt[1:])):
            raise ValueError("lepton_pt_thresholds_gev must be descending")

        z2_value = value["z2_mass"]
        mode = z2_value["min_mode"]
        if mode not in {"fixed", "sliding"}:
            raise ValueError("z2_mass.min_mode must be fixed or sliding")
        fixed_min = _finite_nonnegative(
            z2_value["fixed_min_gev"], "z2_mass.fixed_min_gev"
        )
        z2_max = _finite_nonnegative(z2_value["max_gev"], "z2_mass.max_gev")
        if fixed_min >= z2_max:
            raise ValueError("z2_mass.fixed_min_gev must be below z2_mass.max_gev")

        sliding_value = z2_value["sliding"]
        low_m4l = _finite_nonnegative(
            sliding_value["low_m4l_gev"], "z2_mass.sliding.low_m4l_gev"
        )
        high_m4l = _finite_nonnegative(
            sliding_value["high_m4l_gev"], "z2_mass.sliding.high_m4l_gev"
        )
        if low_m4l >= high_m4l:
            raise ValueError(
                "z2_mass.sliding.high_m4l_gev must exceed low_m4l_gev"
            )
        low_min = _finite_nonnegative(
            sliding_value["low_min_gev"], "z2_mass.sliding.low_min_gev"
        )
        high_min = _finite_nonnegative(
            sliding_value["high_min_gev"], "z2_mass.sliding.high_min_gev"
        )
        if low_min > high_min:
            raise ValueError("z2_mass.sliding lower limits must be non-decreasing")
        if high_min >= z2_max:
            raise ValueError("z2_mass.sliding.high_min_gev must be below max_gev")

        return cls(
            require_exactly_four_leptons=True,
            allowed_lepton_types=allowed,
            lepton_pt_thresholds_gev=pt,
            electron_max_abs_eta=_finite_nonnegative(
                value["electron_max_abs_eta"], "electron_max_abs_eta"
            ),
            muon_max_abs_eta=_finite_nonnegative(
                value["muon_max_abs_eta"], "muon_max_abs_eta"
            ),
            require_zero_charge=bool(value["require_zero_charge"]),
            min_all_sfos_mass_gev=_finite_nonnegative(
                value["min_all_sfos_mass_gev"], "min_all_sfos_mass_gev"
            ),
            z1_mass_window_gev=_window(
                value["z1_mass_window_gev"], "z1_mass_window_gev"
            ),
            z2_min_mode=mode,
            z2_fixed_min_gev=fixed_min,
            z2_max_gev=z2_max,
            z2_sliding=SlidingZ2Config(
                low_m4l_gev=low_m4l,
                high_m4l_gev=high_m4l,
                low_min_gev=low_min,
                high_min_gev=high_min,
            ),
            m4l_window_gev=_window(value["m4l_window_gev"], "m4l_window_gev"),
            lepton_quality=(
                LeptonQualityConfig.from_mapping(value["lepton_quality"])
                if "lepton_quality" in value
                else LeptonQualityConfig.disabled()
            ),
        )


def z2_min_mass_gev(m4l: float, config: SelectionConfig) -> float:
    if config.z2_min_mode == "fixed":
        return config.z2_fixed_min_gev

    sliding = config.z2_sliding
    if m4l <= sliding.low_m4l_gev:
        return sliding.low_min_gev
    if m4l >= sliding.high_m4l_gev:
        return sliding.high_min_gev
    fraction = (m4l - sliding.low_m4l_gev) / (
        sliding.high_m4l_gev - sliding.low_m4l_gev
    )
    return sliding.low_min_gev + fraction * (
        sliding.high_min_gev - sliding.low_min_gev
    )


@dataclass(frozen=True)
class SelectionResult:
    accepted: bool
    passed_stages: tuple[str, ...]
    failed_stage: str | None
    candidate: FourLeptonCandidate | None


class CutflowAccumulator:
    def __init__(
        self,
        *,
        sample_name: str,
        is_data: bool,
        stages: Sequence[str] = SELECTION_STAGES,
    ):
        self.sample_name = str(sample_name)
        self.is_data = bool(is_data)
        self.stages = tuple(stages)
        if not self.stages or self.stages[0] != "read" or len(set(self.stages)) != len(self.stages):
            raise ValueError("cutflow stages must be unique and begin with read")
        self._counts = {stage: 0 for stage in self.stages}
        self._signed = {stage: 0.0 for stage in self.stages}
        self._absolute = {stage: 0.0 for stage in self.stages}

    def _validated_weight(self, physical_weight: float | None) -> float | None:
        if self.is_data:
            if physical_weight is not None:
                raise ValueError("data physical weight must be omitted")
            return None
        if physical_weight is None or not isfinite(float(physical_weight)):
            raise ValueError("MC physical weight must be finite")
        return float(physical_weight)

    def _increment(self, stage: str, physical_weight: float | None) -> None:
        self._counts[stage] += 1
        if physical_weight is not None:
            self._signed[stage] += physical_weight
            self._absolute[stage] += abs(physical_weight)

    def record_read(self, physical_weight: float | None = None) -> None:
        weight = self._validated_weight(physical_weight)
        self._increment("read", weight)

    def record_selection(
        self,
        result: SelectionResult,
        physical_weight: float | None = None,
    ) -> None:
        weight = self._validated_weight(physical_weight)
        expected = self.stages[1 : 1 + len(result.passed_stages)]
        if result.passed_stages != expected:
            raise ValueError("selection stages must be an ordered prefix")
        for stage in result.passed_stages:
            self._increment(stage, weight)

    def to_dict(self) -> dict[str, Any]:
        read_count = self._counts["read"]
        stages: dict[str, Any] = {}
        previous_count = read_count
        for index, stage in enumerate(self.stages):
            count = self._counts[stage]
            if index == 0:
                efficiency_previous = 1.0 if count else 0.0
            else:
                efficiency_previous = count / previous_count if previous_count else 0.0
            entry: dict[str, Any] = {
                "count": count,
                "efficiency_previous": efficiency_previous,
                "efficiency_read": count / read_count if read_count else 0.0,
            }
            if not self.is_data:
                entry["signed_weighted_yield"] = self._signed[stage]
                entry["absolute_weighted_yield"] = self._absolute[stage]
            stages[stage] = entry
            previous_count = count
        return {
            "sample_name": self.sample_name,
            "kind": "data" if self.is_data else "mc",
            "stages": stages,
        }


def _failed(
    stage: str,
    passed: list[str],
    candidate: FourLeptonCandidate | None = None,
) -> SelectionResult:
    return SelectionResult(False, tuple(passed), stage, candidate)


def select_event(
    event: Mapping[str, Any],
    config: SelectionConfig,
    momentum_unit: str,
) -> SelectionResult:
    if str(momentum_unit).lower() not in {"mev", "gev"}:
        raise ValueError(f"unsupported momentum unit: {momentum_unit}")
    if config.lepton_quality.enabled:
        return _select_enhanced_event(event, config, momentum_unit)
    passed: list[str] = []
    fields = (
        "lep_pt",
        "lep_eta",
        "lep_phi",
        "lep_e",
        "lep_charge",
        "lep_type",
    )
    try:
        lengths = [len(event[field]) for field in fields]
        lepton_count = int(event["lep_n"])
    except (KeyError, TypeError, ValueError):
        return _failed("exactly_four_leptons", passed)
    if lepton_count != 4 or lengths != [4] * len(fields):
        return _failed("exactly_four_leptons", passed)
    passed.append("exactly_four_leptons")

    try:
        normalized = normalize_leptons(event, momentum_unit)
    except (TypeError, ValueError):
        return _failed("allowed_lepton_types", passed)

    return _finish_selection(normalized, config, passed)


def _finish_selection(
    normalized,
    config: SelectionConfig,
    passed: list[str],
) -> SelectionResult:
    if "allowed_lepton_types" not in passed:
        if not all(
            abs(int(flavour)) in config.allowed_lepton_types
            for flavour in normalized.flavour
        ):
            return _failed("allowed_lepton_types", passed)
        passed.append("allowed_lepton_types")

    if not np.isfinite(normalized.pt).all() or any(
        value < threshold
        for value, threshold in zip(
            normalized.pt, config.lepton_pt_thresholds_gev
        )
    ):
        return _failed("lepton_pt", passed)
    passed.append("lepton_pt")

    eta_valid = np.isfinite(normalized.eta).all() and all(
        abs(float(eta))
        < (
            config.electron_max_abs_eta
            if abs(int(flavour)) == 11
            else config.muon_max_abs_eta
        )
        for eta, flavour in zip(normalized.eta, normalized.flavour)
    )
    if not eta_valid:
        return _failed("lepton_eta", passed)
    passed.append("lepton_eta")

    if config.require_zero_charge and int(normalized.charge.sum()) != 0:
        return _failed("zero_charge", passed)
    passed.append("zero_charge")

    if not np.isfinite(normalized.phi).all() or not np.isfinite(
        normalized.energy
    ).all():
        return _failed("valid_sfos_pairing", passed)
    candidate = reconstruct_candidate(normalized)
    if candidate is None:
        return _failed("valid_sfos_pairing", passed)
    passed.append("valid_sfos_pairing")

    if not candidate.all_sfos_masses or not all(
        isfinite(mass) and mass > config.min_all_sfos_mass_gev
        for mass in candidate.all_sfos_masses
    ):
        return _failed("all_sfos_mass", passed, candidate)
    passed.append("all_sfos_mass")

    z1_min, z1_max = config.z1_mass_window_gev
    if not z1_min < candidate.z1.mass < z1_max:
        return _failed("z1_mass_window", passed, candidate)
    passed.append("z1_mass_window")

    z2_min = z2_min_mass_gev(candidate.four_lepton.mass, config)
    if not z2_min < candidate.z2.mass < config.z2_max_gev:
        return _failed("z2_mass_window", passed, candidate)
    passed.append("z2_mass_window")

    m4l_min, m4l_max = config.m4l_window_gev
    if not m4l_min <= candidate.four_lepton.mass < m4l_max:
        return _failed("m4l_analysis_window", passed, candidate)
    passed.extend(("m4l_analysis_window", "selected"))
    return SelectionResult(True, tuple(passed), None, candidate)


def _has_required_lengths(
    event: Mapping[str, Any], fields: Sequence[str], lepton_count: int
) -> bool:
    try:
        return all(len(event[field]) == lepton_count for field in fields)
    except (KeyError, TypeError):
        return False


def _at_least_four(indices: list[int], stage: str, passed: list[str]) -> SelectionResult | None:
    if len(indices) < 4:
        return _failed(stage, passed)
    passed.append(stage)
    return None


def _numeric(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _select_enhanced_event(
    event: Mapping[str, Any], config: SelectionConfig, momentum_unit: str
) -> SelectionResult:
    quality = config.lepton_quality
    passed: list[str] = []

    if quality.require_event_trigger:
        try:
            trigger_passed = bool(event["trigE"]) or bool(event["trigM"])
        except KeyError:
            trigger_passed = False
        if not trigger_passed:
            return _failed("trigger", passed)
    passed.append("trigger")

    kinematic_fields = (
        "lep_pt", "lep_eta", "lep_phi", "lep_e", "lep_charge", "lep_type"
    )
    quality_fields = ["lep_track_iso", "lep_calo_iso", "lep_d0sig", "lep_z0"]
    if quality.require_tight_id:
        quality_fields.append("lep_isTightID")
    if quality.require_trigger_match:
        quality_fields.append("lep_isTrigMatched")
    try:
        lepton_count = int(event["lep_n"])
    except (KeyError, TypeError, ValueError):
        return _failed("allowed_lepton_types", passed)
    if lepton_count < 0 or not _has_required_lengths(
        event, (*kinematic_fields, *quality_fields), lepton_count
    ):
        return _failed("allowed_lepton_types", passed)

    indices = list(range(lepton_count))
    try:
        indices = [
            index
            for index in indices
            if abs(int(event["lep_type"][index])) in config.allowed_lepton_types
        ]
    except (TypeError, ValueError):
        indices = []
    failed = _at_least_four(indices, "allowed_lepton_types", passed)
    if failed is not None:
        return failed

    if quality.require_tight_id:
        indices = [index for index in indices if bool(event["lep_isTightID"][index])]
    failed = _at_least_four(indices, "tight_identification", passed)
    if failed is not None:
        return failed

    track_indices: list[int] = []
    for index in indices:
        pt = _numeric(event["lep_pt"][index])
        track_iso = _numeric(event["lep_track_iso"][index])
        if pt is None or track_iso is None or pt <= 0:
            continue
        track_ratio = track_iso / pt
        if isfinite(track_ratio) and track_ratio < quality.track_isolation_max:
            track_indices.append(index)
    indices = track_indices
    failed = _at_least_four(indices, "track_isolation", passed)
    if failed is not None:
        return failed

    calo_indices: list[int] = []
    for index in indices:
        pt = _numeric(event["lep_pt"][index])
        calo_iso = _numeric(event["lep_calo_iso"][index])
        if pt is None or calo_iso is None or pt <= 0:
            continue
        calo_ratio = calo_iso / pt
        if isfinite(calo_ratio) and calo_ratio < quality.calo_isolation_max:
            calo_indices.append(index)
    indices = calo_indices
    failed = _at_least_four(indices, "calorimeter_isolation", passed)
    if failed is not None:
        return failed

    d0_indices: list[int] = []
    for index in indices:
        d0sig = _numeric(event["lep_d0sig"][index])
        try:
            flavour = abs(int(event["lep_type"][index]))
        except (TypeError, ValueError):
            continue
        limit = quality.electron_d0sig_max if flavour == 11 else quality.muon_d0sig_max
        if d0sig is not None and abs(d0sig) < limit:
            d0_indices.append(index)
    indices = d0_indices
    failed = _at_least_four(indices, "transverse_impact_parameter", passed)
    if failed is not None:
        return failed

    z0_indices: list[int] = []
    for index in indices:
        z0 = _numeric(event["lep_z0"][index])
        eta = _numeric(event["lep_eta"][index])
        if z0 is None or eta is None:
            continue
        sin_theta = 1.0 / np.cosh(eta)
        if isfinite(sin_theta) and abs(z0 * sin_theta) < quality.z0_sintheta_max_mm:
            z0_indices.append(index)
    indices = z0_indices
    failed = _at_least_four(indices, "longitudinal_impact_parameter", passed)
    if failed is not None:
        return failed

    if len(indices) != 4:
        return _failed("exactly_four_good_leptons", passed)
    passed.append("exactly_four_good_leptons")

    if quality.require_trigger_match and not any(
        bool(event["lep_isTrigMatched"][index]) for index in indices
    ):
        return _failed("trigger_match", passed)
    passed.append("trigger_match")

    selected_event = {
        field: [event[field][index] for index in indices]
        for field in kinematic_fields
    }
    selected_event["lep_n"] = 4
    try:
        normalized = normalize_leptons(selected_event, momentum_unit)
    except (TypeError, ValueError):
        return _failed("lepton_pt", passed)
    return _finish_selection(normalized, config, passed)
