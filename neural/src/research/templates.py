"""Signed, physical-event-group templates on a common frozen mass grid."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .errors import ResearchError, ResearchStateError


def build_templates(frame, *, mass_edges, mapping_id, candidate_id,
                    category_column="category", categories=(0, 1), thresholds=None,
                    structural_zero_evidence=None):
    thresholds = thresholds or {}
    minimum = float(thresholds.get("min_neff_signed", thresholds.get("min_effective_count", 20)))
    rho_min = float(thresholds.get("min_rho", thresholds.get("min_cancellation_ratio", .2)))
    required = {"dataset", "label", "role", "event_group_id", "yield_weight", "m4l", category_column}
    if not required <= set(frame.columns) or frame.empty:
        raise ResearchError("Template input is empty or lacks required columns")
    if set(frame.role) != {"template"} or frame.dataset.nunique() != 1:
        raise ResearchError("Templates require one dataset and template role exclusively")
    if not mapping_id or not candidate_id:
        raise ResearchError("Mapping and candidate identities are required")
    edges = np.asarray(mass_edges, dtype=float)
    if edges.ndim != 1 or len(edges) < 2 or not np.isfinite(edges).all() or not (np.diff(edges) > 0).all():
        raise ResearchError("Invalid mass grid")
    if not categories or len(set(categories)) != len(categories):
        raise ResearchError("Category contract must be nonempty and unique")
    if not np.isfinite(minimum) or minimum <= 0 or not np.isfinite(rho_min) or not 0 < rho_min <= 1:
        raise ResearchError("Invalid frozen template support thresholds")
    structural = {}
    if structural_zero_evidence is not None:
        evidence = structural_zero_evidence
        if (not isinstance(evidence, dict) or evidence.get("status") != "validated"
                or not evidence.get("evidence_id") or evidence.get("mapping_id") != mapping_id
                or evidence.get("mass_edges") != edges.tolist()
                or evidence.get("categories") != list(categories)
                or not isinstance(evidence.get("bins_by_process"), dict)):
            raise ResearchError("Structural-zero evidence must bind the frozen mapping and grid")
        structural = evidence["bins_by_process"]
        if any(not isinstance(indices,list) or any(type(i) is not int or not 0 <= i < (len(edges)-1)*len(categories) for i in indices) for indices in structural.values()):
            raise ResearchError("Invalid structural-zero support indices")
    values = frame[["m4l", "yield_weight"]].to_numpy(float)
    if not np.isfinite(values).all() or not frame[category_column].isin(categories).all():
        raise ResearchError("Nonfinite input or unknown category")
    if (frame.m4l < edges[0]).any() or (frame.m4l > edges[-1]).any():
        raise ResearchError("Mass outside frozen template support")
    if not frame.label.isin([0, 1]).all():
        raise ResearchError("Labels must be signal=1/background=0")
    process_column = "process" if "process" in frame else "label"
    if frame.event_group_id.isna().any() or (frame.groupby("event_group_id")[process_column].nunique() > 1).any():
        raise ResearchError("Physical groups require one process; cross-process covariance needs a separate model")
    n_mass = len(edges) - 1
    category_index = {v: i for i, v in enumerate(categories)}
    mass_bin = np.minimum(np.searchsorted(edges, frame.m4l, side="right") - 1, n_mass - 1)
    bins = np.asarray([category_index[v] for v in frame[category_column]]) * n_mass + mass_bin
    work = frame.copy()
    work["_bin"] = bins
    samples, issues = [], []
    for process, rows in work.groupby(process_column, sort=True):
        if rows.label.nunique() != 1:
            raise ResearchError("A process cannot mix signal and background")
        matrix = rows.pivot_table(index="event_group_id", columns="_bin", values="yield_weight", aggfunc="sum", fill_value=0).reindex(columns=range(n_mass * len(categories)), fill_value=0).to_numpy(float)
        yields = matrix.sum(axis=0)
        covariance = matrix.T @ matrix
        variance = np.diag(covariance)
        absolute = rows.assign(_abs=rows.yield_weight.abs()).groupby("_bin")._abs.sum().reindex(range(len(yields)), fill_value=0).to_numpy()
        counts = rows.groupby("_bin").event_group_id.nunique().reindex(range(len(yields)), fill_value=0).to_numpy()
        positive = rows.assign(_pos=rows.yield_weight.clip(lower=0)).groupby("_bin")._pos.sum().reindex(range(len(yields)), fill_value=0).to_numpy()
        negative = rows.assign(_neg=rows.yield_weight.clip(upper=0)).groupby("_bin")._neg.sum().reindex(range(len(yields)), fill_value=0).to_numpy()
        states, neff, rho = [], [], []
        for i, (y, v, a, count) in enumerate(zip(yields, variance, absolute, counts)):
            n = float(y*y/v) if v > 0 else None
            r = float(abs(y)/a) if a > 0 else None
            is_structural = i in structural.get(str(process), [])
            if is_structural and count != 0:
                raise ResearchError("Observed events contradict frozen structural-zero support")
            state = ("structural_zero" if is_structural else "insufficient_statistics") if count == 0 else ("nonpositive_yield" if y <= 0 else ("zero_variance" if v <= 0 else ("strong_cancellation" if r < rho_min else ("insufficient_statistics" if n < minimum else "valid"))))
            states.append(state); neff.append(n); rho.append(r)
            if state not in {"valid", "structural_zero"}:
                issues.append({"process": str(process), "bin": i, "status": state})
        samples.append({"name": str(process), "is_signal": bool(rows.label.iloc[0]), "yield": yields.tolist(), "variance": variance.tolist(), "covariance": covariance.tolist(), "sum_abs_weight": absolute.tolist(), "sum_positive_weight": positive.tolist(), "sum_negative_weight": negative.tolist(), "group_count": counts.tolist(), "neff_signed": neff, "neff_abs": [float(a*a/v) if v > 0 else None for a,v in zip(absolute,variance)], "rho": rho, "bin_status": states})
    if not any(s["is_signal"] for s in samples) or not any(not s["is_signal"] for s in samples):
        raise ResearchStateError("Missing effective signal or background", status="insufficient_statistics")
    active = [i for i in range(n_mass * len(categories)) if any(s["bin_status"][i] != "structural_zero" for s in samples)]
    return {"status": "valid" if not issues else "insufficient_statistics", "dataset": str(frame.dataset.iloc[0]), "role": "template", "candidate_id": candidate_id, "mapping_id": mapping_id, "mass_edges": edges.tolist(), "categories": list(categories), "active_bins": active, "samples": samples, "issues": issues, "structural_zero_evidence": structural_zero_evidence, "variance_convention": "sum_outer_products_of_group_bin_signed_weights"}


def common_mass_grid(candidate_frames, *, mass_edges, thresholds, assessment_started=False):
    """Remove the right edge of the leftmost failing mass bin for every candidate."""
    if assessment_started:
        raise ResearchError("Mass-grid selection is forbidden after assessment starts")
    if not candidate_frames:
        raise ResearchError("At least one candidate required")
    edges, history = list(mass_edges), []
    while True:
        artifacts = {name: build_templates(frame, mass_edges=edges, mapping_id=name, candidate_id=name, thresholds=thresholds, categories=(0,) if name == "M0" else (0,1)) for name, frame in sorted(candidate_frames.items())}
        bad = [issue["bin"] % (len(edges)-1) for t in artifacts.values() for issue in t["issues"]]
        if not bad or len(edges) == 2:
            return {"status": "valid" if not bad else "insufficient_statistics", "mass_edges": edges, "merge_history": history, "templates": artifacts}
        index = min(min(bad)+1, len(edges)-2)
        history.append({"removed_edge": edges[index], "reason": "leftmost_failing_mass_bin_shared_across_candidates"})
        del edges[index]


def gate_g1(calibration_statuses, templates, t1_validation):
    reasons = []
    if not calibration_statuses or any(s not in {"valid", "validated"} for s in calibration_statuses.values()):
        reasons.append("calibration_unvalidated")
    if not templates or any(t.get("status") != "valid" for t in templates.values()):
        reasons.append("insufficient_statistics")
    # Expansion requires this actual template's covariance to satisfy shapesys,
    # not merely a validation marker for some independent numerical example.
    for template in templates.values():
        try:
            active = np.asarray(template["active_bins"],dtype=int)
            if active.ndim != 1 or not len(active) or len(set(active)) != len(active):
                raise ValueError("invalid active bins")
            for sample in template["samples"]:
                covariance = np.asarray(sample["covariance"],float)
                variance = np.asarray(sample["variance"],float)
                rates = np.asarray(sample["yield"],float)
                if (covariance.shape != (len(rates),len(rates)) or variance.shape != rates.shape
                        or (active < 0).any() or (active >= len(rates)).any()
                        or not np.isfinite(covariance).all() or not np.isfinite(variance).all()
                        or not np.isfinite(rates).all() or (rates < 0).any() or (variance < 0).any()
                        or not np.allclose(np.diag(covariance),variance,rtol=0,atol=1e-12)):
                    raise ValueError("invalid template moments")
                cov = covariance[np.ix_(active,active)]
                if not np.allclose(cov,np.diag(np.diag(cov)),rtol=0,atol=1e-12):
                    raise ValueError("unsupported group covariance")
        except (KeyError,ValueError,TypeError,IndexError):
            if "template_stat_model_unvalidated" not in reasons:
                reasons.append("template_stat_model_unvalidated")
    contract = {"status": "validated", "correlation": "independent_process_bins", "auxiliary": "poisson_tau_gamma", "modifier": "shapesys", "pyhf_version": "0.7.6"}
    if not t1_validation or not t1_validation.get("evidence_id") or any(t1_validation.get(k) != v for k,v in contract.items()):
        reasons.append("template_stat_model_unvalidated")
    return {"status": "passed" if not reasons else "blocked", "reasons": reasons, "allowed_roles": ["calibration", "template"], "assessment_used": False}
