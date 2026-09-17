"""Pure signed-MC support diagnostics for within-seed joint observations."""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
import pandas as pd

from higgsml.errors import ResearchError
from higgsml.inference.attribution import SEEDS
from higgsml.inference.seed_blocks import (
    SeedBlockSpec, pairing_contract, stream_identity, validate_seed_blocks,
)

PROJECTION_RTOL = 1e-10
PROJECTION_ATOL = 1e-10
J1_REPLICAS = 200


def _finite_number(value) -> bool:
    return type(value) in (int, float, np.integer, np.floating) and math.isfinite(float(value))


def _effective(numerator, denominator):
    return None if denominator <= 0 else float(numerator * numerator / denominator)


def diagnose_joint_support(parent: pd.DataFrame, *, block: SeedBlockSpec,
                           category_columns: dict[str, str], mass_edges,
                           expected_marginals: dict | None = None,
                           process_column: str | None = None,
                           expected_processes: set | None = None,
                           structural_zeros: set[tuple] | None = None) -> dict:
    """Aggregate signed rates, reject split groups, and verify every marginal."""
    required = {"event_group_id", "m4l", "yield_weight", *category_columns.values()}
    missing = required - set(parent.columns)
    if missing or set(category_columns) != set(block.candidate_keys):
        raise ResearchError("joint support input or candidate identity mismatch")
    source = process_column or ("process" if "process" in parent else "label")
    if source not in parent:
        raise ResearchError("joint support requires process or legacy label identity")
    if parent.event_group_id.isna().any():
        raise ResearchError("null physical event group identity")
    edges = np.asarray(mass_edges, float)
    if edges.ndim != 1 or len(edges) < 2 or not np.isfinite(edges).all() or np.any(np.diff(edges) <= 0):
        raise ResearchError("invalid common mass grid")
    work = parent.copy()
    weights = work["yield_weight"].to_numpy(float)
    if not np.isfinite(weights).all():
        raise ResearchError("non-finite yield weight")
    work["_mass_bin"] = np.searchsorted(edges, work["m4l"].to_numpy(float), side="right") - 1
    if ((work._mass_bin < 0) | (work._mass_bin >= len(edges) - 1)).any():
        raise ResearchError("event outside common mass grid")
    columns = [category_columns[key] for key in block.candidate_keys]
    for column in columns:
        if work[column].isna().any():
            raise ResearchError("missing joint category")
    work["_pattern"] = list(map(tuple, work[columns].to_numpy().tolist()))
    group_keys = [source, "_mass_bin", "_pattern"]
    inconsistent_process = (source != "label" and "label" in work
                            and work.groupby(source, sort=False).label.nunique(dropna=False).gt(1).any())
    if (inconsistent_process
            or work.groupby("event_group_id", sort=False)[group_keys].nunique(dropna=False).gt(1).any().any()):
        return {"summary": {"seed": block.seed, "block_id": block.block_id,
                            "process_identity_source": process_column or ("process" if source == "process" else "label_legacy"),
                            "processes": [], "cell_count": 0, "support_mismatch_count": 0,
                            "maximum_projection_error": 0.0,
                            "qualification": "template_stat_model_unvalidated",
                            "failures": ["process_label_or_group_cell_inconsistency"]},
                "cells": [], "projection": {}}

    cells = []
    direct = defaultdict(float)
    projection = defaultdict(float)
    for process, mass_bin, weight, pattern in work[[source, "_mass_bin", "yield_weight", "_pattern"]].itertuples(index=False, name=None):
        weight = float(weight)
        for index, key in enumerate(block.candidate_keys):
            direct[(key, process, mass_bin, pattern[index])] += weight
    processes = sorted(work[source].unique().tolist(), key=str)
    observation_cells = sorted(set(zip(work._mass_bin, work._pattern)), key=lambda item: (item[0], repr(item[1])))
    grouped = {(process, mass_bin, pattern): frame for (process, mass_bin, pattern), frame
               in work.groupby(group_keys, sort=False, dropna=False)}
    for process in processes:
      for mass_bin, pattern in observation_cells:
        frame = grouped.get((process, mass_bin, pattern), work.iloc[0:0])
        w = frame.yield_weight.to_numpy(float)
        group_sums = frame.groupby("event_group_id", sort=False).yield_weight.sum().to_numpy(float)
        signed = float(w.sum()); absolute = float(np.abs(w).sum())
        sumw2 = float(np.square(group_sums).sum())
        zero_key = (process, int(mass_bin), tuple(pattern))
        zero_class = ("structural_zero" if signed == 0 and zero_key in (structural_zeros or set())
                      else "no_events" if len(frame) == 0
                      else "accidental_cancellation" if signed == 0 else None)
        cell = {"process": str(process), "mass_bin": int(mass_bin), "pattern": list(pattern),
                "row_count": int(len(frame)), "group_occupancy": int(frame.event_group_id.nunique()),
                "signed_sum": signed, "absolute_sum": absolute,
                "positive_sum": float(w[w > 0].sum()), "negative_sum": float(w[w < 0].sum()),
                "group_sumw2": sumw2, "rho": None if absolute == 0 else signed / absolute,
                "signed_effective_count": _effective(signed, sumw2),
                "absolute_effective_count": _effective(absolute, sumw2),
                "zero_class": zero_class}
        cells.append(cell)
        for index, key in enumerate(block.candidate_keys):
            projection[(key, process, int(mass_bin), pattern[index])] += signed

    keys = set(direct) | set(projection)
    errors = {key: abs(direct.get(key, 0.0) - projection.get(key, 0.0)) for key in keys}
    reference = direct if expected_marginals is None else expected_marginals
    expected_keys = set(reference) | set(projection)
    mismatches = [key for key in expected_keys if not np.isclose(
        projection.get(key, 0.0), reference.get(key, 0.0), rtol=PROJECTION_RTOL, atol=PROJECTION_ATOL)]
    by_process = []
    for process, frame in work.groupby(source, sort=True):
        process_cells = [c for c in cells if c["process"] == str(process)]
        by_process.append({"process": str(process), "total_yield": float(frame.yield_weight.sum()),
                           "cell_count": len(process_cells),
                           "negative_rate_cells": sum(c["signed_sum"] < 0 for c in process_cells),
                           "zero_rate_cells": sum(c["signed_sum"] == 0 for c in process_cells),
                           "singleton_cells": sum(c["group_occupancy"] == 1 for c in process_cells),
                           "minimum_rate": min((c["signed_sum"] for c in process_cells), default=None)})
    observed_processes = set(work[source].unique())
    required_processes = observed_processes if expected_processes is None else set(expected_processes)
    failures = []
    if any(row["negative_rate_cells"] for row in by_process): failures.append("negative_process_rate")
    if (required_processes - observed_processes or not required_processes
            or any(row["total_yield"] <= 0 for row in by_process)):
        failures.append("missing_positive_process_support")
    if mismatches: failures.append("projection_mismatch")
    qualification = ("binding_error" if "projection_mismatch" in failures else
                     "valid" if not failures else "insufficient_statistics")
    summary = {"seed": block.seed, "block_id": block.block_id,
               "process_identity_source": process_column or ("process" if source == "process" else "label_legacy"),
               "processes": by_process, "cell_count": len(cells),
               "support_mismatch_count": len(mismatches),
               "maximum_projection_error": max(errors.values(), default=0.0),
               "qualification": qualification,
               "failures": failures}
    return {"summary": summary, "cells": cells,
            "projection": {str(key): value for key, value in projection.items()}}


def _validate_gate_inputs(seed_inputs: dict[int, dict], contract_digest: str | None = None) -> None:
    if set(seed_inputs) != set(SEEDS):
        raise ResearchError("support gate requires canonical seeds 42--46")
    blocks = []
    grids = []
    for seed, arguments in seed_inputs.items():
        block = arguments.get("block")
        if not isinstance(block, SeedBlockSpec) or seed != block.seed:
            raise ResearchError("support gate seed/block binding mismatch")
        blocks.append(block)
        try:
            grids.append(tuple(float(edge) for edge in arguments["mass_edges"]))
        except (KeyError, TypeError, ValueError) as error:
            raise ResearchError("support gate requires a common mass grid") from error
    validate_seed_blocks(blocks)
    if len(set(grids)) != 1:
        raise ResearchError("support gate seed blocks must share one nominal mass grid")
    if contract_digest is not None and contract_digest != pairing_contract()["contract_digest"]:
        raise ResearchError("support gate pairing contract mismatch")


def run_j0(seed_inputs: dict[int, dict]) -> dict:
    _validate_gate_inputs(seed_inputs)
    results = {str(seed): diagnose_joint_support(**arguments) for seed, arguments in sorted(seed_inputs.items())}
    passed = len(results) == 5 and all(r["summary"]["qualification"] == "valid" for r in results.values())
    return {"gate": "J0", "status": "passed" if passed else "failed", "seeds": results,
            "projection_tolerance": {"rtol": PROJECTION_RTOL, "atol": PROJECTION_ATOL}}


def bernoulli_group_thinning(frame: pd.DataFrame, *, q: float, stream: dict) -> tuple[pd.DataFrame, dict]:
    if not _finite_number(q) or q <= 0 or q > 1:
        raise ResearchError("screening_design_unavailable")
    groups = sorted(frame.event_group_id.unique().tolist(), key=str)
    if q == 1:
        selected = set(groups); design = "degenerate_q1_all_groups"
    else:
        rng = np.random.default_rng(stream["seed"])
        selected = {group for group, keep in zip(groups, rng.random(len(groups)) < q) if keep}
        design = "group_bernoulli_thinning"
    thinned = frame[frame.event_group_id.isin(selected)].copy()
    thinned["yield_weight"] = thinned.yield_weight / q
    return thinned, {"q": q, "design": design, "groups_total": len(groups),
                     "groups_selected": len(selected), "stream_id": stream["stream_id"],
                     "stream": stream}


def run_j1(parent: pd.DataFrame, *, block_inputs: dict[int, dict], q: float,
           contract_digest: str, replicas: int = J1_REPLICAS, toy_base_seed: int = 42001) -> dict:
    if replicas != J1_REPLICAS:
        raise ResearchError("J1 requires the registered 200-replica budget")
    _validate_gate_inputs(block_inputs, contract_digest)
    declared_sources = {arguments.get("process_column") for arguments in block_inputs.values()}
    if len(declared_sources) != 1:
        raise ResearchError("J1 seed blocks must use one process identity source")
    declared_source = declared_sources.pop()
    process_source = declared_source or ("process" if "process" in parent else "label")
    if process_source not in parent:
        raise ResearchError("J1 parent lacks declared process identity source")
    expected_processes = set(parent[process_source].unique())
    records = []
    for replica in range(replicas):
        shared = stream_identity(contract_digest=contract_digest, stage="support-j1", mu=0,
                                 training_seed=42, outer_index=None, stream_kind="physical_group_thinning",
                                 replica_index=replica, toy_base_seed=toy_base_seed)
        sample, selection = bernoulli_group_thinning(parent, q=q, stream=shared)
        seeds = {}
        failure_diagnostics = {}
        for seed, arguments in sorted(block_inputs.items()):
            diagnostic = diagnose_joint_support(sample, expected_processes=expected_processes, **arguments)
            seeds[str(seed)] = diagnostic["summary"]
            if diagnostic["summary"]["qualification"] != "valid":
                failure_diagnostics[str(seed)] = diagnostic
        records.append({"replica_index": replica, "selection": selection, "seeds": seeds,
                        "failure_diagnostics": failure_diagnostics})
    failures = {str(seed): sum(record["seeds"][str(seed)]["qualification"] != "valid" for record in records)
                for seed in sorted(block_inputs)}
    passed = len(failures) == 5 and all(count == 0 for count in failures.values())
    seeds = {seed: {"replicas": replicas, "support_failures": count,
                    "qualification": "valid" if count == 0 else "insufficient_statistics"}
             for seed, count in failures.items()}
    return {"gate": "J1", "status": "passed" if passed else "failed", "replicas": replicas,
            "policy": "engineering_screen_not_scientific_validation", "required_failures_per_seed": 0,
            "toy_base_seed": toy_base_seed, "seeds": seeds,
            "failures_by_seed": failures, "records": records}
