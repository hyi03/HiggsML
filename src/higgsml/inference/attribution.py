"""Registered raw mass-off family: identities, zero information and paired estimands."""
from __future__ import annotations

import itertools
from copy import deepcopy

import numpy as np
from scipy.stats import rankdata

from higgsml.artifacts import digest_json
from higgsml.errors import ResearchError
from higgsml.modeling.discriminants import digest, make_empty_model, validate_empty_model
from higgsml.modeling.representations import representation_features
from higgsml.inference.reporting import exact_shapley

FAMILY = "engineered19_raw_T1_m4l_off_attribution_v1"
SEEDS = tuple(range(42, 47))
SUBSETS = tuple("".join(g) for size in range(5) for g in itertools.combinations("ABCD", size))
SEED_DRAWS = np.asarray(list(itertools.product(range(5), repeat=5)))
BUDGETS = {"mc_bootstrap": {"replicas": 200, "seed": 42001},
           "toys": {"injections": [0, 1, 2], "count": 500, "seed": 42},
           "t2": {"mu": 1, "outer_replicas": 20, "inner_toys": 100, "seed": 42}}


def candidate_key(seed, subset):
    if type(seed) is not int or seed not in SEEDS or subset not in SUBSETS:
        raise ResearchError("unregistered mass-off identity")
    return f"M3:{seed}:groups={subset}:m4l=off" if subset else f"M0off:{seed}"


def candidate_keys():
    return [candidate_key(seed, subset) for seed in SEEDS for subset in SUBSETS]


def empty_bundle(model, protocol):
    validate_empty_model(model)
    mapping = "raw:" + model["model_id"]
    threshold = {"model_id": model["model_id"], "mapping_id": mapping, "thresholds": [.5],
                 "source_role": "registered_constant_no_fit", "ties": "higher-category-at-threshold",
                 "protocol_id": digest(protocol)}
    threshold["threshold_id"] = digest(threshold)
    return {"model": model, "model_id": model["model_id"], "candidate_id": "M0off",
            "seed": model["seed"], "key": candidate_key(model["seed"], ""), "mapping": None,
            "mapping_id": mapping, "thresholds": threshold, "transform": "raw", "status": "calibrated"}


def validate_bundle(bundle, protocol, prepared_id):
    from higgsml.modeling.calibration import assign_categories
    try:
        model = bundle["model"]
        if model["candidate"] == "M0off":
            validate_empty_model(model)
            if model["prepared_artifact_id"] != prepared_id or bundle != empty_bundle(model, protocol):
                raise ResearchError("M0off prepared/bundle binding mismatch")
            subset = ""
        else:
            subset = "".join(model["groups"])
            if (model["candidate"] != "M3" or subset not in SUBSETS[1:]
                    or model.get("mass_input") != "off"
                    or model["ordered_inputs"] != list(representation_features("engineered19", groups=list(subset), mass_input="off"))
                    or model["model_id"] != digest({k:v for k,v in model.items() if k != "model_id"})):
                raise ResearchError("invalid off-family model")
        if (model["protocol_id"] != digest(protocol) or model["dataset"] != protocol["dataset"]
                or bundle["key"] != candidate_key(model["seed"], subset) or bundle["seed"] != model["seed"]
                or bundle["candidate_id"] != model["candidate"] or bundle["model_id"] != model["model_id"]
                or bundle["mapping"] is not None or bundle["transform"] != "raw"
                or bundle["status"] != "calibrated" or bundle["mapping_id"] != "raw:" + model["model_id"]
                or bundle["thresholds"]["protocol_id"] != digest(protocol)):
            raise ResearchError("off-family raw bundle binding mismatch")
        assign_categories(bundle["thresholds"], [.5], model_id=model["model_id"], mapping_id=bundle["mapping_id"])
    except (KeyError, TypeError, ValueError) as error:
        raise ResearchError("malformed off-family bundle") from error


def structural_evidence(bundle, frame, edges):
    validate_empty_model(bundle["model"])
    if (bundle["thresholds"]["thresholds"] != [.5] or bundle["mapping"] is not None
            or bundle['model_id']!=bundle['model']['model_id'] or bundle['mapping_id']!='raw:'+bundle['model_id']
            or bundle['thresholds']['model_id']!=bundle['model_id'] or bundle['thresholds']['mapping_id']!=bundle['mapping_id']
            or bundle['thresholds']['threshold_id']!=digest({k:v for k,v in bundle['thresholds'].items() if k!='threshold_id'})):
        raise ResearchError("M0off structural-zero mapping changed")
    processes = frame["process"] if "process" in frame else frame.label
    evidence = {"status": "validated", "mapping_id": bundle["mapping_id"], "mass_edges": list(edges),
                "categories": [0,1], "bins_by_process": {str(p): list(range(len(edges)-1)) for p in sorted(processes.unique())},
                "basis": "registered_constant_score_0.5_ties_to_category_1",
                "model_id": bundle["model_id"], "threshold_id": bundle["thresholds"]["threshold_id"]}
    return {**evidence, "evidence_id": digest_json(evidence)}


def seed_interval(values):
    a = np.asarray(values, float)
    if a.shape != (5,) or not np.isfinite(a).all():
        raise ResearchError("seed interval requires five finite paired values")
    medians = np.median(a[SEED_DRAWS], axis=1)
    return {"per_seed": a.tolist(), "median": float(np.median(a)),
            "interval68": np.quantile(medians, [.16,.84], method="linear").tolist(),
            "interval95": np.quantile(medians, [.025,.975], method="linear").tolist()}


def _correlation(x, y):
    if np.ptp(x) == 0 or np.ptp(y) == 0:
        return {"status": "unavailable", "reason": "constant_input", "pearson": None, "spearman": None}
    return {"status": "valid", "pearson": float(np.corrcoef(x,y)[0,1]),
            "spearman": float(np.corrcoef(rankdata(x, method="average"),rankdata(y, method="average"))[0,1])}


def summarize(records, *, require_auc=True):
    """Reject incomplete cohorts; compute per-seed estimands before their medians."""
    output = {"status": "incomplete", "family_id": FAMILY, "records": deepcopy(records),
              "ranking_stability": None, "pairwise_comparisons": None, "interactions": None,
              "contributions": None, "auc_width_relationship": None, "failures": []}
    indexed = {}
    for row in records:
        key = row.get("candidate_key")
        if key in indexed:
            output["failures"].append("duplicate_identity")
        indexed[key] = row
    if set(indexed) != set(candidate_keys()):
        output["failures"].append("incomplete_candidate_matrix")
    if len({r.get("cohort_id") for r in records}) != 1 or any(not r.get("cohort_id") for r in records):
        output["failures"].append("mixed_or_missing_cohort")
    for seed in SEEDS:
        for subset in SUBSETS:
            row = indexed.get(candidate_key(seed, subset), {})
            width = row.get("width68")
            valid = (row.get("family_id") == FAMILY and row.get("seed") == seed and row.get("subset") == subset
                     and row.get("status") == "valid" and type(width) in (int,float) and np.isfinite(width) and width > 0)
            if require_auc and subset:
                auc = row.get("auc")
                valid &= (type(auc) in (int,float) and np.isfinite(auc) and 0 <= auc <= 1
                          and row.get("auc_role") == "validation" and row.get("auc_measure") == "absolute_physical_weight"
                          and bool(row.get("model_id")) and row.get("auc_model_id") == row.get("model_id"))
            if not valid:
                output["failures"].append(candidate_key(seed,subset))
    if output["failures"]:
        return output
    widths = np.asarray([[indexed[candidate_key(s,g)]["width68"] for g in SUBSETS] for s in SEEDS])
    # Empty identities are pairing labels; they must never acquire seed variability.
    if not np.allclose(widths[:,0], widths[0,0], rtol=0, atol=1e-10):
        output["failures"].append("empty_baseline_seed_mismatch")
        return output
    per_seed = [exact_shapley(dict(zip(SUBSETS,-widths[i])), family_id=FAMILY, seed=s) for i,s in enumerate(SEEDS)]
    contributions = [{"group": g, **seed_interval([r["contributions"][g] for r in per_seed])} for g in "ABCD"]
    interactions = [{"pair": row["pair"], "conditioning_subset": row["conditioning_subset"],
                     **seed_interval([r["interactions"][i]["second_difference"] for r in per_seed])}
                    for i,row in enumerate(per_seed[0]["interactions"])]
    pairs = []
    for i,j in itertools.combinations(range(1,16),2):
        left,right = widths[:,i],widths[:,j]
        pairs.append({"left": SUBSETS[i], "right": SUBSETS[j],
                      "delta_width68_left_minus_right": seed_interval(left-right),
                      "relative_improvement_left_vs_right": seed_interval(1-left/right),
                      "strict_win_count": int(sum(left < right)), "tie_count": int(sum(left == right)),
                      "interval_scope": "per_pair_not_simultaneous"})
    ranks = np.asarray([rankdata(row[1:],method="average") for row in widths])
    medians = np.median(widths[:,1:],axis=0)
    median_width_ranks = rankdata(medians, method='average')
    # Every statistic uses these same joint seed draws, including ranking uncertainty.
    resampled_medians = np.median(widths[SEED_DRAWS,1:],axis=1)
    resampled_ranks = rankdata(resampled_medians,axis=1,method="average")
    ranking = [{"subset": g, "width68": seed_interval(widths[:,i+1]),
                "min_width68": float(min(widths[:,i+1])), "max_width68": float(max(widths[:,i+1])),
                "per_seed_rank": ranks[:,i].tolist(), "median_rank": float(np.median(ranks[:,i])),
                "rank_of_median_width68": float(median_width_ranks[i]),
                "best_rank": float(min(ranks[:,i])), "worst_rank": float(max(ranks[:,i])),
                "first_place_count": int(sum(widths[:,i+1] == widths[:,1:].min(axis=1))),
                "bootstrap_rank_interval95": np.quantile(resampled_ranks[:,i],[.025,.975],method="linear").tolist()}
               for i,g in enumerate(SUBSETS[1:])]
    ranking.sort(key=lambda r:(r["width68"]["median"],len(r["subset"]),r["subset"]))
    display = {str(s): sorted(SUBSETS[1:],key=lambda g:(indexed[candidate_key(s,g)]["width68"],len(g),g)) for s in SEEDS}
    ties = {str(s): [[SUBSETS[i+1] for i,v in enumerate(widths[k,1:]) if v == w]
                     for w in sorted(set(widths[k,1:])) if sum(widths[k,1:] == w)>1] for k,s in enumerate(SEEDS)}
    auc_result = {"status": "not_requested"}
    if require_auc:
        auc = np.asarray([[indexed[candidate_key(s,g)]["auc"] for g in SUBSETS[1:]] for s in SEEDS])
        auc_result = {"status": "descriptive", "observations": [indexed[candidate_key(s,g)] for s in SEEDS for g in SUBSETS[1:]],
                      "per_seed": [{"seed":s, **_correlation(auc[i],widths[i,1:])} for i,s in enumerate(SEEDS)],
                      "candidate_medians": _correlation(np.median(auc,axis=0),medians)}
    output.update(status="valid", per_seed=per_seed, contributions=contributions, interactions=interactions,
                  pairwise_comparisons=pairs, ranking_stability=ranking, display_order=display, tied_groups=ties,
                  auc_width_relationship=auc_result,
                  compact_vs_full={"selection_status":"exploration_selected_pending_frozen_validation",
                                   "comparisons":[r for r in pairs if r["left"] in {"BC","AC"} and r["right"] == "ABCD"]},
                  seed_resampling={"count":3125,"unit":"complete_joint_seed_vector","quantile_method":"linear",
                                   "interpretation":"training_seed_stability_conditional_on_current_MC"})
    return output
