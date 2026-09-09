import itertools
import pytest
from src.research.reporting import main_comparison,coverage_summary,paired_coverage_error,exact_shapley
from src.research.errors import ResearchStateError


def test_all_seeds_required_no_best_seed_selection():
    rows=[{"seed":s,"candidate_id":c,"layer":"T1","mu":1,"expectation_kind":"model_self_asimov","width68":w,"status":"valid"} for s in range(42,47) for c,w in [("M4",2.),("M5",1.8)]]
    assert main_comparison(rows)["median_relative_improvement"]==pytest.approx(.1)
    assert main_comparison(rows[:-1])["median_relative_improvement"] is None


def test_coverage_and_paired_error_retain_failures():
    rows=[{"status":"valid","lower":0,"upper":2}]*3+[{"status":"fit_failed"}]
    report=coverage_summary(rows,mu=1)
    assert report["coverage"] is None and report["failed_fits"]==1
    assert report["success_and_coverage_fraction"]==.75
    assert paired_coverage_error(rows,rows,mu=1,pairing_id="physical")["status"]=="coverage_incomplete"
    assert paired_coverage_error(rows[:3],rows[:3],mu=1,pairing_id="physical")["standard_error"]==0


def test_exact_shapley_efficiency_and_interaction_no_empty_fallback():
    values={"".join(s): -10+sum("ABCD".index(g)+1 for g in s)+ (2 if "A" in s and "B" in s else 0) for k in range(5) for s in itertools.combinations("ABCD",k)}
    result=exact_shapley(values,family_id="physical_cdf_T1",seed=42)
    assert result["contributions"]==pytest.approx({"A":2,"B":3,"C":3,"D":4})
    assert result["efficiency_residual"]==pytest.approx(0)
    del values[""]
    with pytest.raises(ResearchStateError): exact_shapley(values,family_id="physical_cdf_T1",seed=42)
