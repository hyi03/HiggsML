import itertools
import pytest
from higgsml.inference.reporting import (main_comparison,coverage_summary,paired_coverage_error,
                                    fit_diagnostics,exact_shapley,feature_combination_comparison,
                                    feature_combination_summary, mass_input_comparison,
                                    mass_input_summary)
from higgsml.errors import ResearchStateError


def test_all_seeds_required_no_best_seed_selection():
    rows=[{"seed":s,"candidate_id":c,"layer":"T1","mu":1,"expectation_kind":"model_self_asimov","width68":w,"status":"valid"} for s in range(42,47) for c,w in [("M4",2.),("M5",1.8)]]
    assert main_comparison(rows)["median_relative_improvement"]==pytest.approx(.1)
    assert main_comparison(rows[:-1])["median_relative_improvement"] is None


def test_coverage_and_paired_error_retain_failures():
    rows=[{"status":"valid","lower":0,"upper":2}]*3+[{"status":"fit_failed"}]
    report=coverage_summary(rows,mu=1)
    assert report["coverage"] is None and report["failed_fits"]==1
    assert report["failure_rate"]==.25
    assert report["success_and_coverage_fraction"]==.75
    assert paired_coverage_error(rows,rows,mu=1,pairing_id="physical")["status"]=="coverage_incomplete"
    assert paired_coverage_error(rows[:3],rows[:3],mu=1,pairing_id="physical")["standard_error"]==0
    diagnostics=fit_diagnostics([{"status":"valid","muhat":1.1,"width":2.,"lower_at_boundary":False}],mu=1)
    assert diagnostics["mean_width"]==diagnostics["median_width"]==2.
    assert diagnostics["failure_rate"]==0


def test_exact_shapley_efficiency_and_interaction_no_empty_fallback():
    values={"".join(s): -10+sum("ABCD".index(g)+1 for g in s)+ (2 if "A" in s and "B" in s else 0) for k in range(5) for s in itertools.combinations("ABCD",k)}
    result=exact_shapley(values,family_id="physical_cdf_T1",seed=42)
    assert result["contributions"]==pytest.approx({"A":2,"B":3,"C":3,"D":4})
    assert result["efficiency_residual"]==pytest.approx(0)
    del values[""]
    with pytest.raises(ResearchStateError): exact_shapley(values,family_id="physical_cdf_T1",seed=42)


def test_complete_feature_combination_comparison_requires_all_fifteen_and_baseline():
    widths={"" : 10.0}
    widths.update({"".join(subset):10.0-sum("ABCD".index(group)+1 for group in subset)*.1
                   for size in range(1,5) for subset in itertools.combinations("ABCD",size)})
    results={}
    for subset,width in widths.items():
        key="M0c:42" if not subset else f"M3:42:groups={subset}"
        candidate="M0c" if not subset else "M3"
        results[key]={"status":"valid","seed":42,"asimov":{"candidate_id":candidate,"layer":"T1",
            "expectation_kind":"model_self_asimov","results":[{"mu":1.0,"intervals":[{"status":"valid","width":width}]}]}}
    report=feature_combination_comparison(results,seed=42,family_id="engineered19_raw_T1")
    assert report["status"]=="valid" and len(report["nonempty_combinations"])==15
    assert report["baseline"]["subset"]=="" and report["shapley"]["status"]=="valid"
    del results["M3:42:groups=AB"]
    incomplete=feature_combination_comparison(results,seed=42,family_id="engineered19_raw_T1")
    assert incomplete["status"]=="feature_combination_incomplete"
    assert incomplete["failures"]==[{"subset":"AB","candidate_key":"M3:42:groups=AB","reason":"missing_result"}]


def test_five_seed_feature_summary_uses_paired_medians_and_retains_shapley():
    comparisons=[]
    for seed in range(42,47):
        baseline=10.+(seed-42)
        rows=[]
        for size in range(1,5):
            for groups in itertools.combinations("ABCD",size):
                subset="".join(groups)
                improvement=.02 if subset=="AB" else .01/(1+len(subset))
                width=baseline*(1-improvement)
                rows.append({"subset":subset,"candidate_key":f"M3:{seed}:groups={subset}",
                             "width68":width,"relative_improvement_vs_empty":improvement})
        values={"":-baseline,**{row["subset"]:-row["width68"] for row in rows}}
        comparisons.append({"status":"valid","seed":seed,
                            "nonempty_combinations":rows,
                            "shapley":exact_shapley(values,family_id="engineered19_raw_T1",seed=seed)})
    summary=feature_combination_summary(comparisons)
    assert summary["status"]=="valid"
    assert summary["best_combination"]["subset"]=="AB"
    assert summary["best_combination"]["median_relative_improvement_vs_empty"]==pytest.approx(.02)
    assert set(summary["shapley"]["groups"])==set("ABCD")
    assert len(summary["shapley"]["interactions"])==24
    incomplete=feature_combination_summary(comparisons[:-1])
    assert incomplete["status"]=="feature_combination_summary_incomplete"
    assert incomplete["best_combination"] is None
    assert {failure["seed"] for failure in incomplete["failures"]}=={46}


def _inference(seed, candidate, width):
    return {"status":"valid", "seed":seed, "asimov":{"candidate_id":candidate, "layer":"T1",
        "expectation_kind":"model_self_asimov", "results":[{"mu":1, "intervals":[{"status":"valid", "width":width}]}]}}


def test_mass_input_comparison_requires_all_pairs_slices_and_seeds():
    comparisons = []
    for seed in range(42, 47):
        results = {f"M0c:{seed}": _inference(seed, "M0c", 10.)}
        models = {f"M0c:{seed}": {"validation_absolute_weight_auc": .7}}
        support = {"0":{"row_count":2,"sum_absolute_weight":2.,"effective_count":2.},
                   "1":{"row_count":2,"sum_absolute_weight":2.,"effective_count":2.}}
        for size in range(1, 5):
            for groups in itertools.combinations("ABCD", size):
                subset = "".join(groups); on = f"M3:{seed}:groups={subset}"; off = on + ":m4l=off"
                results[on] = _inference(seed, "M3", 8.); results[off] = _inference(seed, "M3", 10.)
                models[on] = {"validation_absolute_weight_auc": .8,
                              "validation_mass_slice_auc":[{"slice_index":0,"mass_low":105.,"mass_high":110.,"status":"valid","auc":.75,"class_support":support}]}
                models[off] = {"validation_absolute_weight_auc": .7,
                               "validation_mass_slice_auc":[{"slice_index":0,"mass_low":105.,"mass_high":110.,"status":"valid","auc":.70,"class_support":support}]}
        comparison = mass_input_comparison(results, models, seed=seed)
        assert comparison['status'] == 'valid' and len(comparison['pairs']) == 15
        assert comparison['pairs'][0]['relative_w68_improvement_from_m4l'] == pytest.approx(.2)
        comparisons.append(comparison)
    summary = mass_input_summary(comparisons)
    assert summary['status'] == 'valid' and len(summary['combinations']) == 15
    assert len(summary['mass_slices']) == 15
    comparisons[0]['pairs'][0]['mass_slices'][0]['status'] = 'incomplete'
    comparisons[0]['status'] = 'mass_input_comparison_incomplete'
    assert mass_input_summary(comparisons)['status'] == 'mass_input_summary_incomplete'
