"""Complete-seed comparisons and exact, non-imputed group attribution."""
from __future__ import annotations

import itertools
import math
import numpy as np
from scipy.stats import norm

from higgsml.errors import ResearchError, ResearchStateError


def main_comparison(records):
    """Records: seed,candidate_id,layer,mu,expectation_kind,width68,status."""
    rows, failures = [], []
    for seed in range(42,47):
        pair = {}
        for candidate in ("M4","M5"):
            selected = [r for r in records if r.get("seed")==seed and r.get("candidate_id")==candidate and r.get("layer")=="T1" and r.get("mu")==1 and r.get("expectation_kind")=="model_self_asimov"]
            if len(selected)!=1 or selected[0].get("status")!="valid" or not np.isfinite(selected[0].get("width68",np.nan)) or selected[0]["width68"]<=0:
                failures.append({"seed":seed,"candidate_id":candidate,"status":"missing_or_invalid_primary_result"})
            else:
                pair[candidate]=float(selected[0]["width68"])
        if len(pair)==2:
            rows.append({"seed":seed,"M4_width68":pair["M4"],"M5_width68":pair["M5"],"relative_improvement":1-pair["M5"]/pair["M4"]})
    return {"status":"valid" if not failures else "primary_comparison_incomplete","paired_seeds":rows,"failures":failures,"median_relative_improvement":float(np.median([r["relative_improvement"] for r in rows])) if not failures else None,"summary_rule":"all_five_paired_seeds_42_through_46_no_failed_seed_deletion"}


def coverage_summary(intervals, *, mu, confidence=.95):
    """Wilson interval and binomial SE; failures remain in the declared budget."""
    n = len(intervals)
    valid = [r for r in intervals if r.get("status")=="valid" and r.get("lower") is not None and r.get("upper") is not None]
    covered = sum(r["lower"]<=mu<=r["upper"] for r in valid)
    if not n:
        raise ResearchError("Coverage needs a positive declared toy budget")
    p=covered/n; z=float(norm.ppf((1+confidence)/2)); denom=1+z*z/n
    center=(p+z*z/(2*n))/denom; half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denom
    return {"status":"valid" if len(valid)==n else "coverage_incomplete","budget":n,"valid_fits":len(valid),"failed_fits":n-len(valid),"failure_rate":(n-len(valid))/n,"covered":covered,"coverage":p if len(valid)==n else None,"success_and_coverage_fraction":p,"wilson_interval_success_and_coverage":[center-half,center+half],"binomial_standard_error":math.sqrt(p*(1-p)/n),"interpretation":"failed fits are reported; success-and-coverage is not conditional coverage"}


def paired_coverage_error(left, right, *, mu, pairing_id):
    if not pairing_id or len(left)!=len(right) or len(left)<2:
        raise ResearchError("Paired coverage needs common physical toys and at least two pairs")
    if any(r.get("status")!="valid" for r in list(left)+list(right)):
        return {"status":"coverage_incomplete","difference":None,"standard_error":None,"pairing_id":pairing_id}
    delta=np.asarray([int(a["lower"]<=mu<=a["upper"])-int(b["lower"]<=mu<=b["upper"]) for a,b in zip(left,right)],float)
    return {"status":"valid","difference":float(delta.mean()),"standard_error":float(delta.std(ddof=1)/np.sqrt(len(delta))),"pairing_id":pairing_id,"pairs":len(delta)}


def fit_diagnostics(intervals, *, mu):
    """Bias and interval-scaled pulls are descriptive, including boundary flags."""
    if not intervals:
        raise ResearchError("Diagnostics require declared fits")
    valid=[r for r in intervals if r.get("status")=="valid" and r.get("width",0)>0 and np.isfinite(r.get("muhat",np.nan))]
    offsets=np.asarray([r["muhat"]-mu for r in valid],float)
    pulls=np.asarray([(r["muhat"]-mu)/(r["width"]/2) for r in valid],float)
    widths=np.asarray([r["width"] for r in valid],float)
    return {"status":"valid" if len(valid)==len(intervals) else "diagnostics_incomplete","budget":len(intervals),"valid_fits":len(valid),"failed_fits":len(intervals)-len(valid),"failure_rate":(len(intervals)-len(valid))/len(intervals),"bias_valid_fits":float(offsets.mean()) if len(valid) else None,"bias_standard_error":float(offsets.std(ddof=1)/np.sqrt(len(valid))) if len(valid)>1 else None,"pull_mean":float(pulls.mean()) if len(valid) else None,"pull_std":float(pulls.std(ddof=1)) if len(valid)>1 else None,"pull_definition":"(muhat-mu)/(interval_width/2); descriptive, not Gaussian at boundaries","mean_width":float(widths.mean()) if len(widths) else None,"median_width":float(np.median(widths)) if len(widths) else None,"width_q16":float(np.quantile(widths,.16)) if len(widths) else None,"width_q84":float(np.quantile(widths,.84)) if len(widths) else None,"lower_boundary_count":sum(bool(r.get("lower_at_boundary")) for r in valid)}


def exact_shapley(values, *, family_id, seed, groups=("A","B","C","D")):
    """values maps subset strings (empty string included) to same-family v=-W68."""
    if not family_id or len(groups)!=4 or len(set(groups))!=4:
        raise ResearchError("Exact attribution requires a named four-group family")
    expected={"".join(s) for k in range(5) for s in itertools.combinations(groups,k)}
    if set(values)!=expected or any(v is None or not np.isfinite(v) for v in values.values()):
        raise ResearchStateError("All 16 same-family values, including a valid empty-set CDF, are required",status="shapley_unavailable")
    def key(subset): return "".join(g for g in groups if g in subset)
    phi={}
    for group in groups:
        others=[g for g in groups if g!=group]; contribution=0.
        for k in range(4):
            for subset in itertools.combinations(others,k):
                weight=math.factorial(k)*math.factorial(3-k)/math.factorial(4)
                contribution+=weight*(values[key((*subset,group))]-values[key(subset)])
        phi[group]=float(contribution)
    interactions=[]
    for a,b in itertools.combinations(groups,2):
        others=[g for g in groups if g not in (a,b)]
        for k in range(3):
            for subset in itertools.combinations(others,k):
                interactions.append({"pair":a+b,"conditioning_subset":key(subset),"second_difference":float(values[key((*subset,a,b))]-values[key((*subset,a))]-values[key((*subset,b))]+values[key(subset)])})
    residual=sum(phi.values())-(values[key(groups)]-values[""])
    if not np.isclose(residual,0,atol=1e-10,rtol=1e-10):
        raise ResearchError("Shapley efficiency failed")
    return {"status":"valid","family_id":family_id,"seed":seed,"value_function":"negative_mu_interval_width","unit":"mu_interval_width","contributions":phi,"efficiency_residual":residual,"interactions":interactions}


def feature_combination_comparison(results, *, seed, family_id="engineered19_raw_T1"):
    """Build a complete single-seed comparison for all nonempty A/B/C/D subsets."""
    groups=("A","B","C","D")
    subsets=["".join(value) for size in range(5) for value in itertools.combinations(groups,size)]
    expected={subset:(f"M0c:{seed}" if not subset else f"M3:{seed}:groups={subset}") for subset in subsets}
    widths={}; failures=[]; rows=[]
    for subset,candidate_key in expected.items():
        result=results.get(candidate_key)
        if result is None:
            failures.append({"subset":subset,"candidate_key":candidate_key,"reason":"missing_result"})
            continue
        asimov=result.get("asimov",{})
        injections=[item for item in asimov.get("results",[]) if item.get("mu")==1]
        interval=injections[0].get("intervals",[{}])[0] if len(injections)==1 and injections[0].get("intervals") else {}
        expected_candidate="M0c" if not subset else "M3"
        valid=(result.get("status")=="valid" and result.get("seed")==seed and
               asimov.get("candidate_id")==expected_candidate and asimov.get("layer")=="T1" and
               asimov.get("expectation_kind")=="model_self_asimov" and len(injections)==1 and
               interval.get("status")=="valid" and np.isfinite(interval.get("width",np.nan)) and interval.get("width",0)>0)
        if not valid:
            failures.append({"subset":subset,"candidate_key":candidate_key,"reason":"invalid_or_incomparable_result"})
            continue
        width=float(interval["width"]); widths[subset]=width
        rows.append({"subset":subset,"candidate_key":candidate_key,"width68":width})
    if failures:
        return {"status":"feature_combination_incomplete","family_id":family_id,"seed":seed,
                "expected_nonempty_combinations":15,"expected_total_with_baseline":16,
                "failures":failures,"available_subsets":sorted(widths,key=lambda value:(len(value),value))}
    baseline=next(row for row in rows if row["subset"]=="")
    nonempty=[row for row in rows if row["subset"]]
    for row in nonempty:
        row["relative_improvement_vs_empty"]=1-row["width68"]/baseline["width68"]
    nonempty.sort(key=lambda row:(row["width68"],len(row["subset"]),row["subset"]))
    values={subset:-width for subset,width in widths.items()}
    return {"status":"valid","family_id":family_id,"seed":seed,
            "comparison_contract":"same_population_common_grid_T1_mu1_model_self_asimov",
            "expected_nonempty_combinations":15,"expected_total_with_baseline":16,
            "baseline":baseline,"nonempty_combinations":nonempty,
            "shapley":exact_shapley(values,family_id=family_id,seed=seed)}


def feature_combination_summary(comparisons, *, expected_seeds=range(42, 47)):
    """Aggregate complete per-seed comparisons without dropping failed seeds."""
    expected_seeds = list(expected_seeds)
    by_seed = {}
    failures = []
    for comparison in comparisons:
        seed = comparison.get("seed")
        if seed in by_seed:
            failures.append({"seed":seed,"reason":"duplicate_comparison"})
        else:
            by_seed[seed] = comparison
    for seed in expected_seeds:
        comparison = by_seed.get(seed)
        if comparison is None:
            failures.append({"seed":seed,"reason":"missing_comparison"})
        elif comparison.get("status") != "valid":
            failures.append({"seed":seed,"reason":"invalid_comparison",
                             "status":comparison.get("status")})
    unexpected = sorted(seed for seed in by_seed if seed not in expected_seeds)
    failures.extend({"seed":seed,"reason":"unexpected_comparison"} for seed in unexpected)
    if failures:
        return {
            "status":"feature_combination_summary_incomplete",
            "summary_rule":"all_five_paired_seeds_42_through_46_no_failed_seed_deletion",
            "expected_seeds":expected_seeds,
            "available_seeds":sorted(seed for seed in by_seed if isinstance(seed, int)),
            "failures":failures,
            "best_combination":None,
        }

    subsets = ["".join(value) for size in range(1, 5)
               for value in itertools.combinations(("A","B","C","D"), size)]
    rows_by_seed = {
        seed:{row["subset"]:row for row in by_seed[seed]["nonempty_combinations"]}
        for seed in expected_seeds
    }
    combinations = []
    for subset in subsets:
        per_seed = [{"seed":seed,
                     "width68":float(rows_by_seed[seed][subset]["width68"]),
                     "relative_improvement_vs_empty":float(
                         rows_by_seed[seed][subset]["relative_improvement_vs_empty"])}
                    for seed in expected_seeds]
        widths = [row["width68"] for row in per_seed]
        improvements = [row["relative_improvement_vs_empty"] for row in per_seed]
        combinations.append({
            "subset":subset,
            "per_seed":per_seed,
            "median_width68":float(np.median(widths)),
            "min_width68":float(min(widths)),
            "max_width68":float(max(widths)),
            "median_relative_improvement_vs_empty":float(np.median(improvements)),
            "min_relative_improvement_vs_empty":float(min(improvements)),
            "max_relative_improvement_vs_empty":float(max(improvements)),
        })
    ranked = sorted(
        combinations,
        key=lambda row:(-row["median_relative_improvement_vs_empty"],
                        row["median_width68"],len(row["subset"]),row["subset"]),
    )

    shapley_groups = {}
    for group in ("A","B","C","D"):
        per_seed = [{"seed":seed,
                     "contribution":float(by_seed[seed]["shapley"]["contributions"][group])}
                    for seed in expected_seeds]
        values = [row["contribution"] for row in per_seed]
        shapley_groups[group] = {
            "per_seed":per_seed,
            "median_contribution":float(np.median(values)),
            "min_contribution":float(min(values)),
            "max_contribution":float(max(values)),
        }

    interaction_keys = [
        (row["pair"], row["conditioning_subset"])
        for row in by_seed[expected_seeds[0]]["shapley"]["interactions"]
    ]
    interactions = []
    for pair, conditioning_subset in interaction_keys:
        per_seed = []
        for seed in expected_seeds:
            matches = [row for row in by_seed[seed]["shapley"]["interactions"]
                       if row["pair"] == pair and row["conditioning_subset"] == conditioning_subset]
            if len(matches) != 1:
                raise ResearchError("Shapley interaction keys differ across seeds")
            per_seed.append({"seed":seed,"second_difference":float(matches[0]["second_difference"])})
        values = [row["second_difference"] for row in per_seed]
        interactions.append({
            "pair":pair,
            "conditioning_subset":conditioning_subset,
            "per_seed":per_seed,
            "median_second_difference":float(np.median(values)),
            "min_second_difference":float(min(values)),
            "max_second_difference":float(max(values)),
        })

    best = ranked[0]
    return {
        "status":"valid",
        "summary_rule":"paired_seed_median_42_through_46_no_failed_seed_deletion",
        "seeds":expected_seeds,
        "value_function":"negative_mu_interval_width",
        "unit":"mu_interval_width",
        "combinations":combinations,
        "best_combination":{
            "subset":best["subset"],
            "median_width68":best["median_width68"],
            "median_relative_improvement_vs_empty":best["median_relative_improvement_vs_empty"],
        },
        "shapley":{"groups":shapley_groups,"interactions":interactions},
    }


def _t1_width(result, *, seed, candidate):
    if result is None:
        return None
    asimov = result.get("asimov", {})
    injections = [item for item in asimov.get("results", []) if item.get("mu") == 1]
    interval = injections[0].get("intervals", [{}])[0] if len(injections) == 1 else {}
    if not (result.get("status") == "valid" and result.get("seed") == seed
            and asimov.get("candidate_id") == candidate and asimov.get("layer") == "T1"
            and asimov.get("expectation_kind") == "model_self_asimov"
            and interval.get("status") == "valid"
            and np.isfinite(interval.get("width", np.nan)) and interval.get("width", 0) > 0):
        return None
    return float(interval["width"])


def mass_input_comparison(results, models, *, seed,
                          family_id="engineered19_raw_T1_m4l_on_off"):
    """Pair every grouped M3 model with and without explicit m4l."""
    subsets = ["".join(value) for size in range(1, 5)
               for value in itertools.combinations(("A", "B", "C", "D"), size)]
    baseline_key = f"M0c:{seed}"
    baseline_model = models.get(baseline_key)
    baseline_width = _t1_width(results.get(baseline_key), seed=seed, candidate="M0c")
    baseline_auc = baseline_model.get("validation_absolute_weight_auc") if baseline_model else None
    baseline_valid_auc = np.isfinite(baseline_auc if baseline_auc is not None else np.nan)
    baseline = {"candidate_key": baseline_key, "validation_absolute_weight_auc": baseline_auc if baseline_valid_auc else None,
                "width68": baseline_width,
                "status": "valid" if baseline_model is not None and baseline_width is not None
                and baseline_valid_auc else "incomplete"}
    rows, failures = [], []
    for subset in subsets:
        on_key = f"M3:{seed}:groups={subset}"
        off_key = on_key + ":m4l=off"
        on_model, off_model = models.get(on_key), models.get(off_key)
        on_width = _t1_width(results.get(on_key), seed=seed, candidate="M3")
        off_width = _t1_width(results.get(off_key), seed=seed, candidate="M3")
        auc_on = on_model.get("validation_absolute_weight_auc") if on_model else None
        auc_off = off_model.get("validation_absolute_weight_auc") if off_model else None
        auc_valid = (np.isfinite(auc_on if auc_on is not None else np.nan)
                     and np.isfinite(auc_off if auc_off is not None else np.nan))
        slices = []
        on_slices = on_model.get("validation_mass_slice_auc", []) if on_model else []
        off_slices = off_model.get("validation_mass_slice_auc", []) if off_model else []
        slice_complete = len(on_slices) == len(off_slices) > 0
        if slice_complete:
            for left, right in zip(on_slices, off_slices):
                matching = (left.get("slice_index"), left.get("mass_low"), left.get("mass_high")) == (
                    right.get("slice_index"), right.get("mass_low"), right.get("mass_high"))
                valid = (matching and left.get("status") == right.get("status") == "valid"
                         and np.isfinite(left.get("auc", np.nan)) and np.isfinite(right.get("auc", np.nan)))
                support = left.get("class_support") if left.get("class_support") == right.get("class_support") else None
                slices.append({"slice_index": left.get("slice_index"), "mass_low": left.get("mass_low"),
                               "mass_high": left.get("mass_high"), "status": "valid" if valid else "incomplete",
                               "auc_on": left.get("auc") if valid else None,
                               "auc_off": right.get("auc") if valid else None,
                               "delta_auc_on_minus_off": left["auc"] - right["auc"] if valid else None,
                               "class_support": support})
                slice_complete &= valid
        complete = (on_model is not None and off_model is not None and on_width is not None
                    and off_width is not None and auc_valid and slice_complete)
        row = {"subset": subset, "seed": seed, "on_candidate_key": on_key,
               "off_candidate_key": off_key, "status": "valid" if complete else "incomplete",
               "auc_on": auc_on if auc_valid else None, "auc_off": auc_off if auc_valid else None,
               "delta_auc_on_minus_off": auc_on - auc_off if auc_valid else None,
               "width68_on": on_width, "width68_off": off_width,
               "delta_width68_on_minus_off": on_width - off_width if on_width is not None and off_width is not None else None,
               "relative_w68_improvement_from_m4l": 1 - on_width / off_width if on_width is not None and off_width else None,
               "mass_slices": slices}
        rows.append(row)
        if not complete:
            failures.append({"subset": subset, "reason": "missing_or_invalid_paired_model_metric"})
    if baseline["status"] != "valid":
        failures.append({"subset": "m4l-only", "reason": "missing_or_invalid_mass_only_baseline"})
    return {"status": "valid" if not failures else "mass_input_comparison_incomplete",
            "family_id": family_id, "seed": seed, "mass_only_baseline": baseline,
            "pairs": rows, "failures": failures,
            "summary_rule": "all_15_pairs_and_all_registered_mass_slices_required"}


def mass_input_summary(comparisons, *, expected_seeds=range(42, 47)):
    expected_seeds = list(expected_seeds)
    by_seed = {row.get("seed"): row for row in comparisons}
    failures = [{"seed": seed, "reason": "missing_or_invalid_comparison"}
                for seed in expected_seeds if by_seed.get(seed, {}).get("status") != "valid"]
    if len(by_seed) != len(comparisons):
        failures.append({"reason": "duplicate_seed"})
    if failures:
        return {"status": "mass_input_summary_incomplete", "expected_seeds": expected_seeds,
                "failures": failures, "combinations": []}
    rows, slice_rows = [], []
    for subset in [row["subset"] for row in by_seed[expected_seeds[0]]["pairs"]]:
        paired = [next(row for row in by_seed[seed]["pairs"] if row["subset"] == subset)
                  for seed in expected_seeds]
        auc = [row["delta_auc_on_minus_off"] for row in paired]
        width = [row["delta_width68_on_minus_off"] for row in paired]
        relative = [row["relative_w68_improvement_from_m4l"] for row in paired]
        rows.append({"subset": subset, "status": "valid",
                     "median_delta_auc_on_minus_off": float(np.median(auc)),
                     "min_delta_auc_on_minus_off": min(auc), "max_delta_auc_on_minus_off": max(auc),
                     "median_delta_width68_on_minus_off": float(np.median(width)),
                     "min_delta_width68_on_minus_off": min(width), "max_delta_width68_on_minus_off": max(width),
                     "median_relative_w68_improvement_from_m4l": float(np.median(relative)),
                     "min_relative_w68_improvement_from_m4l": min(relative),
                     "max_relative_w68_improvement_from_m4l": max(relative)})
        for slice_index in range(len(paired[0]["mass_slices"])):
            slices = [row["mass_slices"][slice_index] for row in paired]
            if any(row.get("status") != "valid" for row in slices):
                raise ResearchError("valid mass-input comparison contains invalid mass slice")
            deltas = [row["delta_auc_on_minus_off"] for row in slices]
            slice_rows.append({"subset": subset, "slice_index": slice_index,
                               "mass_low": slices[0]["mass_low"], "mass_high": slices[0]["mass_high"],
                               "status": "valid", "median_delta_auc_on_minus_off": float(np.median(deltas)),
                               "min_delta_auc_on_minus_off": min(deltas),
                               "max_delta_auc_on_minus_off": max(deltas)})
    return {"status": "valid", "seeds": expected_seeds,
            "summary_rule": "all_five_paired_seeds_no_failure_deletion", "combinations": rows,
            "mass_slices": slice_rows}


def build_report(candidate_statuses, *, primary_records=(), environment=None, results=None,
                 feature_comparisons=(), mass_input_comparisons=()):
    if not candidate_statuses:
        raise ResearchError("Report must enumerate planned candidate states")
    feature_comparisons = list(feature_comparisons)
    mass_input_comparisons = list(mass_input_comparisons)
    return {"status":"software_report","scope":"MC-only educational/technical research","candidate_statuses":dict(candidate_statuses),"primary_comparison":main_comparison(primary_records),"feature_combination_comparisons":feature_comparisons,"feature_combination_summary":feature_combination_summary(feature_comparisons),"mass_input_comparisons":mass_input_comparisons,"mass_input_summary":mass_input_summary(mass_input_comparisons),"environment":environment or {"repository_authority_validation":"not_run","scientific_numerical_validation":"not_run"},"results":results or {},"scientific_results_obtained":False,"future_R_experiments":"require_separate_registration"}


def write_learning_curves(models, path):
    """Plot bound histories without rescoring any event or choosing a checkpoint."""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib import colormaps
    if not models or any('history_contract' not in m for m in models):
        raise ResearchError('Detailed learning curves unavailable for historical artifacts')
    figure = Figure(figsize=(14, 9), constrained_layout=True)
    FigureCanvasAgg(figure)
    axes = figure.subplots(2, 3).ravel()
    fields = ['classification_loss', 'adversary_loss', 'effective_lambda', 'validation_absolute_weight_auc']
    for model_index, model in enumerate(models):
        rows = model['history']
        epochs = [r['epoch'] for r in rows]
        label = f"{model['candidate']} seed={model['seed']} lambda={model['target_lambda']:g}"
        for axis, field in zip(axes, fields):
            axis.plot(epochs, [np.nan if r[field] is None else r[field] for r in rows], label=label)
            axis.set_title(field.replace('_', ' '), fontsize=10)
        axes[4].plot(epochs, [r['diagnostics']['absolute_weight_mass_ks'] for r in rows], label=label)
        for k in range(len(rows[0]['diagnostics']['mass_bin_acceptance'])):
            axes[5].plot(epochs, [r['diagnostics']['mass_bin_acceptance'][k] for r in rows], alpha=.7,
                         color=colormaps['tab20'](k), linestyle='--' if model_index else '-',
                         label=f'bin {k+1}' if not model_index else '_nolegend_')
        for axis in axes:
            axis.axvline(model['selected_epoch'], color=f'C{model_index}', linestyle=':', alpha=.5)
    axes[4].set_title('Validation background mass KS', fontsize=10)
    axes[5].set_title('Background acceptance by mass bin\nsolid=first model, dashed=second model', fontsize=10)
    axes[5].legend(fontsize=6, ncol=4, loc='lower center')
    adversarial = any(m['candidate'] in {'M6','M3-fixed200'} for m in models)
    if all(all(r['adversary_loss'] is None for r in m['history']) for m in models):
        axes[1].text(.5,.5,'No adversary for this model',ha='center',transform=axes[1].transAxes)
    for axis in axes:
        if adversarial:
            axis.axvspan(1, 5, color='gray', alpha=.12)
            axis.axvspan(5, 15, color='orange', alpha=.10)
        axis.set_xlim(1, max(r['epoch'] for m in models for r in m['history']))
        axis.set_xlabel('Epoch')
    axes[0].legend(fontsize=7)
    phase = 'gray=warm-up, orange=ramp, ' if adversarial else ''
    figure.suptitle(f'Training diagnostics: {phase}dotted=selected checkpoint\n'
                   'Train-median working point recomputed each epoch; fixed train mass bins. No convergence claim.')
    figure.savefig(path, dpi=130)
