import importlib.util
import numpy as np
import pandas as pd
import pytest
from scipy.optimize import brentq
from scipy.stats import chi2
from src.research.inference import build_model,profile_interval,run_asimov,run_toys,paired_event_toys,stress_weights,run_t2_procedure
from src.research.errors import ResearchError,ResearchStateError


def single_bin():
    return {"status":"valid","active_bins":[0],"mapping_id":"m","candidate_id":"M4","samples":[{"name":"s","is_signal":True,"yield":[10.],"variance":[1.],"covariance":[[1.]]},{"name":"b","is_signal":False,"yield":[20.],"variance":[2.],"covariance":[[2.]]}]}


@pytest.mark.skipif(importlib.util.find_spec("pyhf") is None,reason="optional pinned pyhf unavailable")
def test_single_bin_analytic_profile_and_asimov():
    model,_=build_model(single_bin())
    r=profile_interval(model,[30.])
    target=chi2.ppf(.68,1)
    def equation(mu):
        rate=mu*10+20
        return 2*(rate-30+30*np.log(30/rate))-target
    assert r["muhat"]==pytest.approx(1,abs=1e-5)
    assert r["lower"]==pytest.approx(brentq(equation,0,1),abs=1e-5)
    assert r["upper"]==pytest.approx(brentq(equation,1,5),abs=1e-5)
    assert [r["mu"] for r in run_asimov(single_bin())["results"]]==[0,1,2]
    with pytest.raises(ResearchStateError,match="T1 requires"):
        build_model(single_bin(),layer="T1")
    assert profile_interval(model,[20.])["lower"]==0


@pytest.mark.skipif(importlib.util.find_spec("pyhf") is None,reason="optional pinned pyhf unavailable")
def test_t1_tau_auxiliary_and_finite_search_bounds():
    evidence={"status":"validated","evidence_id":"synthetic-single-bin-only","correlation":"independent_process_bins","auxiliary":"poisson_tau_gamma","modifier":"shapesys","pyhf_version":"0.7.6"}
    model,_=build_model(single_bin(),layer="T1",t1_validation=evidence)
    assert sorted(model.config.auxdata)==pytest.approx([100.,200.])
    assert profile_interval(model,model.expected_data(model.config.suggested_init()))["muhat"]==pytest.approx(1,abs=1e-4)
    bounded,_=build_model(single_bin(),mu_max=1.1)
    assert profile_interval(bounded,[30.])["status"]=="interval_unbounded"
    for auxiliary in ("fixed","regenerated"):
        toys=run_toys(single_bin(),count=2,layer="T1",t1_validation=evidence,auxiliary_generation=auxiliary)
        assert toys["count"]==2 and toys["auxiliary_generation"]==auxiliary


def test_joint_physical_pairing_and_negative_rejection():
    f=pd.DataFrame({"role":["assessment"]*4,"event_group_id":["a","b","c","d"],"label":[0,0,1,1],"m4l":[106.]*4,"yield_weight":[2.,3.,4.,5.],"left":[0,1,0,1],"right":[1,0,1,0]})
    paired=paired_event_toys(f,category_columns={"a":"left","b":"right"},mass_edges=[105,110],mu=1,count=20,seed=42,mother_id="physical")
    assert np.array_equal(np.array(paired["observations"]["a"])[:,::-1],paired["observations"]["b"])
    f.loc[0,"yield_weight"]=-100
    with pytest.raises(ResearchStateError): paired_event_toys(f,category_columns={"a":"left"},mass_edges=[105,110],mu=1,count=2,seed=1,mother_id="physical")


def test_shape_and_normalization_stress_separate():
    f=pd.DataFrame({"label":[0,0,1],"m4l":[105,140,120],"yield_weight":[10.,20.,5.],"reference_score":[0.,1.,.5]})
    assert stress_weights(f,kind="mass",direction=1,reference_mapping_id="common")[:2].sum()==pytest.approx(30)
    assert stress_weights(f,kind="normalization",direction=1,reference_mapping_id="common")[:2].sum()==pytest.approx(33)


def test_t2_same_mapping_both_mothers_and_budget():
    base=pd.DataFrame({"event_group_id":["a","b"],"yield_weight":[1.,2.],"physical_weight":[1.,2.]})
    seen=[]
    def apply(mapping,frame):
        seen.append((mapping["mapping_id"],frame.role.iloc[0])); return frame
    result=run_t2_procedure(base.assign(role="calibration"),base.assign(role="template",event_group_id=["c","d"]),base.assign(role="assessment",event_group_id=["e","f"]),fit_mapping=lambda f:{"mapping_id":"replica"},apply_mapping=apply,evaluate=lambda t,m,mp,n,s:{"status":"valid","n":n},outer_replicas=3,inner_toys=2,seed=42,model_id="frozen",mother_id="frozen")
    assert result["status"]=="valid"
    assert seen==[("replica","template"),("replica","assessment")]*3


def test_t2_bootstrap_retains_draw_multiplicity_for_group_variance():
    base=pd.DataFrame(dict(event_group_id=['a','b'],yield_weight=[1.,1.],physical_weight=[1.,1.]))
    seen=[]
    def fit(frame):
        seen.append((frame.physical_weight.pow(2)/frame.bootstrap_multiplicity).sum())
        assert np.array_equal(frame.physical_weight,frame.bootstrap_multiplicity)
        return {'mapping_id':'m'}
    result=run_t2_procedure(base.assign(role='calibration'),base.assign(role='template',event_group_id=['c','d']),base.assign(role='assessment',event_group_id=['e','f']),fit_mapping=fit,apply_mapping=lambda m,f:f,evaluate=lambda *a:dict(status='valid'),outer_replicas=3,inner_toys=1,seed=42,model_id='m',mother_id='mother')
    assert seen==[2.,2.,2.]
    assert sum(result['replicas'][0]['bootstrap_group_multiplicities'].values())==2
