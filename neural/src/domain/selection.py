from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

import numpy as np

from src.config import InputBindingError

from .reconstruction import FourLeptonCandidate, normalize_leptons, reconstruct_candidate


STAGES = (
    "read", "trigger", "allowed_lepton_types", "tight_identification",
    "track_isolation", "calorimeter_isolation", "transverse_impact_parameter",
    "longitudinal_impact_parameter", "exactly_four_good_leptons", "trigger_match",
    "lepton_pt", "lepton_eta", "zero_charge", "valid_sfos_pairing", "all_sfos_mass",
    "z1_mass_window", "z2_mass_window", "m4l_analysis_window", "selected",
)


@dataclass(frozen=True)
class SelectionConfig:
    pt_thresholds: tuple[float, float, float, float]
    electron_eta: float
    muon_eta: float
    track_iso: float
    calo_iso: float
    electron_d0: float
    muon_d0: float
    z0_sintheta: float
    min_sfos_mass: float
    z1_window: tuple[float, float]
    z2_window: tuple[float, float]
    m4l_window: tuple[float, float]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SelectionConfig":
        return cls(
            tuple(float(item) for item in value["lepton_pt_thresholds_gev"]),
            float(value["electron_max_abs_eta"]), float(value["muon_max_abs_eta"]),
            float(value["track_isolation_max"]), float(value["calo_isolation_max"]),
            float(value["electron_d0sig_max"]), float(value["muon_d0sig_max"]),
            float(value["z0_sintheta_max_mm"]), float(value["min_all_sfos_mass_gev"]),
            tuple(map(float, value["z1_mass_window_gev"])),
            tuple(map(float, value["z2_mass_window_gev"])),
            tuple(map(float, value["m4l_window_gev"])),
        )

@dataclass(frozen=True)
class SelectionResult:
    accepted: bool
    passed_stages: tuple[str, ...]
    failed_stage: str | None
    candidate: FourLeptonCandidate | None = None


def _fail(stage: str, passed: list[str], candidate: FourLeptonCandidate | None = None) -> SelectionResult:
    return SelectionResult(False, tuple(passed), stage, candidate)


def _number(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise InputBindingError(f"{field} must be numeric") from error
    if not isfinite(number):
        raise InputBindingError(f"{field} must be finite")
    return number


def _validate_event_schema(event: Mapping[str, Any], required: tuple[str, ...]) -> int:
    try:
        raw_count = event["lep_n"]
        if isinstance(raw_count, bool) or int(raw_count) != raw_count:
            raise ValueError
        count = int(raw_count)
        if count < 0 or any(len(event[name]) != count for name in required):
            raise ValueError
    except (KeyError, TypeError, ValueError) as error:
        raise InputBindingError("lepton arrays do not match lep_n") from error
    numeric_fields = (
        "lep_pt", "lep_eta", "lep_phi", "lep_e", "lep_charge", "lep_type",
        "lep_track_iso", "lep_calo_iso", "lep_d0sig", "lep_z0",
    )
    for field in numeric_fields:
        for value in event[field]:
            _number(value, field)
    return count


def select_event(event: Mapping[str, Any], config: SelectionConfig, momentum_unit: str) -> SelectionResult:
    passed: list[str] = []
    if not (bool(event.get("trigE", False)) or bool(event.get("trigM", False))):
        return _fail("trigger", passed)
    passed.append("trigger")
    required = (
        "lep_pt", "lep_eta", "lep_phi", "lep_e", "lep_charge", "lep_type",
        "lep_isTightID", "lep_track_iso", "lep_calo_iso", "lep_d0sig", "lep_z0",
        "lep_isTrigMatched",
    )
    count = _validate_event_schema(event, required)
    indices = [index for index in range(count) if abs(int(event["lep_type"][index])) in {11, 13}]
    if len(indices) < 4:
        return _fail("allowed_lepton_types", passed)
    passed.append("allowed_lepton_types")
    indices = [index for index in indices if bool(event["lep_isTightID"][index])]
    if len(indices) < 4:
        return _fail("tight_identification", passed)
    passed.append("tight_identification")
    for stage, field, limit in (
        ("track_isolation", "lep_track_iso", config.track_iso),
        ("calorimeter_isolation", "lep_calo_iso", config.calo_iso),
    ):
        kept = []
        for index in indices:
            pt, isolation = _number(event["lep_pt"][index], "lep_pt"), _number(event[field][index], field)
            if pt > 0 and isolation / pt < limit:
                kept.append(index)
        indices = kept
        if len(indices) < 4:
            return _fail(stage, passed)
        passed.append(stage)
    kept = []
    for index in indices:
        value = _number(event["lep_d0sig"][index], "lep_d0sig")
        limit = config.electron_d0 if abs(int(event["lep_type"][index])) == 11 else config.muon_d0
        if abs(value) < limit:
            kept.append(index)
    indices = kept
    if len(indices) < 4:
        return _fail("transverse_impact_parameter", passed)
    passed.append("transverse_impact_parameter")
    kept = []
    for index in indices:
        z0 = _number(event["lep_z0"][index], "lep_z0")
        eta = _number(event["lep_eta"][index], "lep_eta")
        if abs(z0 / np.cosh(eta)) < config.z0_sintheta:
            kept.append(index)
    indices = kept
    if len(indices) < 4:
        return _fail("longitudinal_impact_parameter", passed)
    passed.append("longitudinal_impact_parameter")
    if len(indices) != 4:
        return _fail("exactly_four_good_leptons", passed)
    passed.append("exactly_four_good_leptons")
    if not any(bool(event["lep_isTrigMatched"][index]) for index in indices):
        return _fail("trigger_match", passed)
    passed.append("trigger_match")
    selected = {name: [event[name][index] for index in indices] for name in required[:6]}
    selected["lep_n"] = 4
    try:
        normalized = normalize_leptons(selected, momentum_unit)
    except (TypeError, ValueError) as error:
        raise InputBindingError("invalid normalized lepton values") from error
    if any(value < threshold for value, threshold in zip(normalized.pt, config.pt_thresholds)):
        return _fail("lepton_pt", passed)
    passed.append("lepton_pt")
    if not all(abs(float(eta)) < (config.electron_eta if abs(int(flavour)) == 11 else config.muon_eta)
                   for eta, flavour in zip(normalized.eta, normalized.flavour)):
        return _fail("lepton_eta", passed)
    passed.append("lepton_eta")
    if int(normalized.charge.sum()) != 0:
        return _fail("zero_charge", passed)
    passed.append("zero_charge")
    candidate = reconstruct_candidate(normalized)
    if candidate is None:
        return _fail("valid_sfos_pairing", passed)
    passed.append("valid_sfos_pairing")
    if not candidate.all_sfos_masses or not all(mass > config.min_sfos_mass for mass in candidate.all_sfos_masses):
        return _fail("all_sfos_mass", passed, candidate)
    passed.append("all_sfos_mass")
    if not config.z1_window[0] < candidate.z1.mass < config.z1_window[1]:
        return _fail("z1_mass_window", passed, candidate)
    passed.append("z1_mass_window")
    if not config.z2_window[0] < candidate.z2.mass < config.z2_window[1]:
        return _fail("z2_mass_window", passed, candidate)
    passed.append("z2_mass_window")
    if not config.m4l_window[0] <= candidate.four_lepton.mass < config.m4l_window[1]:
        return _fail("m4l_analysis_window", passed, candidate)
    passed.extend(("m4l_analysis_window", "selected"))
    return SelectionResult(True, tuple(passed), None, candidate)


class CutflowAccumulator:
    def __init__(self, sample_name: str) -> None:
        self.sample_name = sample_name
        self.counts = {stage: 0 for stage in STAGES}
        self.signed = {stage: 0.0 for stage in STAGES}
        self.absolute = {stage: 0.0 for stage in STAGES}

    def record(self, result: SelectionResult | None, weight: float) -> None:
        stages = ("read",) if result is None else result.passed_stages
        for stage in stages:
            self.counts[stage] += 1
            self.signed[stage] += weight
            self.absolute[stage] += abs(weight)

    def to_dict(self) -> dict:
        read = self.counts["read"]
        previous = read
        stages = {}
        for index, stage in enumerate(STAGES):
            count = self.counts[stage]
            stages[stage] = {
                "count": count,
                "efficiency_previous": (1.0 if count else 0.0) if index == 0 else (count / previous if previous else 0.0),
                "efficiency_read": count / read if read else 0.0,
                "signed_weighted_yield": self.signed[stage],
                "absolute_weighted_yield": self.absolute[stage],
            }
            previous = count
        return {"kind": "mc", "read_count": read, "selected_count": self.counts["selected"], "stages": stages}
