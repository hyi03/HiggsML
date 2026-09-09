"""Complete-seed comparisons and exact, non-imputed group attribution."""
from __future__ import annotations

import itertools
import math
import numpy as np
from scipy.stats import norm

from .errors import ResearchError, ResearchStateError


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
    return {"status":"valid" if len(valid)==n else "coverage_incomplete","budget":n,"valid_fits":len(valid),"failed_fits":n-len(valid),"covered":covered,"coverage":p if len(valid)==n else None,"success_and_coverage_fraction":p,"wilson_interval_success_and_coverage":[center-half,center+half],"binomial_standard_error":math.sqrt(p*(1-p)/n),"interpretation":"failed fits are reported; success-and-coverage is not conditional coverage"}


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
    return {"status":"valid" if len(valid)==len(intervals) else "diagnostics_incomplete","budget":len(intervals),"valid_fits":len(valid),"failed_fits":len(intervals)-len(valid),"bias_valid_fits":float(offsets.mean()) if len(valid) else None,"bias_standard_error":float(offsets.std(ddof=1)/np.sqrt(len(valid))) if len(valid)>1 else None,"pull_mean":float(pulls.mean()) if len(valid) else None,"pull_std":float(pulls.std(ddof=1)) if len(valid)>1 else None,"pull_definition":"(muhat-mu)/(interval_width/2); descriptive, not Gaussian at boundaries","lower_boundary_count":sum(bool(r.get("lower_at_boundary")) for r in valid)}


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


def build_report(candidate_statuses, *, primary_records=(), environment=None, results=None):
    if not candidate_statuses:
        raise ResearchError("Report must enumerate planned candidate states")
    return {"status":"software_report","scope":"MC-only educational/technical research","candidate_statuses":dict(candidate_statuses),"primary_comparison":main_comparison(primary_records),"environment":environment or {"repository_authority_validation":"not_run","scientific_numerical_validation":"not_run"},"results":results or {},"scientific_results_obtained":False,"future_R_experiments":"require_separate_registration"}
