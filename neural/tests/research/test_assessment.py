import copy
import numpy as np
import pandas as pd
import pytest

from src.research.assessment import infer_assessment, run_assessment_t2, run_assessment_stress
from src.research.errors import ResearchStateError
from src.research.protocol import load_protocol
from src.research.templates import build_templates
from src.research.calibration import fit_thresholds


def population(role):
    return pd.DataFrame([dict(dataset="atlas2020_4lep", role=role, event_group_id=f"{role}:{i}", event_id=f"{role}:{i}",
        label=i%2, m4l=125., yield_weight=1., physical_weight=1., category=int(i>=40), score=(i//2+.5)/40)
        for i in range(80)])


def fixture():
    p=load_protocol().to_dict()
    p["templates"].update(min_neff_signed=2.)
    p["calibration"]["min_effective_count"]=2.
    p["inference"].update(toy_count=2,outer_replicas=1,inner_toys=1)
    frame=population("template")
    t=build_templates(frame,mass_edges=[105.,140.],mapping_id="map",candidate_id="M3",thresholds=p["templates"])
    m0=build_templates(frame.assign(category=0),mass_edges=[105.,140.],mapping_id="mass",candidate_id="M0",thresholds=p["templates"],categories=(0,))
    return p,{"status":"valid","mass_edges":[105.,140.],"templates":{"A":t,"B":copy.deepcopy(t),"M0":m0}}, {"A":{"mapping_id":"map"},"B":{"mapping_id":"map"}}


def categorize(bundle,frame):
    return frame


def test_actual_pyhf_assessment_toys_share_observations_and_mass_projection():
    pytest.importorskip('pyhf')
    p,grid,bundles=fixture()
    result=infer_assessment(grid,bundles,population("assessment"),p,layer="T0",t1_validation=None,
        mu=1.,count=2,seed=42,prepared_id="prepared",freeze_id="frozen",categorize=categorize)
    a,b,m=[result[k]["toys"] for k in ("A","B","M0")]
    assert a["paired"] and a["pairing_id"]==b["pairing_id"]==m["pairing_id"]
    for x,y,z in zip(a["results"],b["results"],m["results"]):
        assert x["observations"]==y["observations"]
        assert sum(x["observations"])==z["observations"][0]
    assert result["A"]["coverage"]["0.68"]["budget"]==2
    assert result["A"]["diagnostics"]["0.68"]["budget"]==2


def test_positive_mother_in_inactive_template_bin_is_not_discarded():
    p,grid,bundles=fixture()
    grid["templates"]["A"]["active_bins"]=[0]
    with pytest.raises(ResearchStateError,match="structural-zero"):
        infer_assessment(grid,bundles,population("assessment"),p,layer="T0",t1_validation=None,
            mu=1.,count=1,seed=42,prepared_id="p",freeze_id="f",categorize=categorize)


def test_negative_process_joint_rate_rejected_even_if_total_positive():
    p,grid,bundles=fixture()
    mother=population("assessment")
    mother.loc[mother.label==1,"yield_weight"]=-.1
    with pytest.raises(ResearchStateError,match="joint process"):
        infer_assessment(grid,bundles,mother,p,layer="T0",t1_validation=None,
            mu=1.,count=1,seed=42,prepared_id="p",freeze_id="f",categorize=categorize)


def test_correlated_technical_rows_not_sampled_as_independent_cells():
    p,grid,bundles=fixture()
    mother=population("assessment")
    mother.loc[40,"event_group_id"]=mother.loc[0,"event_group_id"]
    with pytest.raises(ResearchStateError,match="physical event spans"):
        infer_assessment(grid,bundles,mother,p,layer="T0",t1_validation=None,
            mu=1.,count=1,seed=42,prepared_id="p",freeze_id="f",categorize=categorize)


def test_t2_actual_mapping_template_and_mother_on_frozen_grid():
    pytest.importorskip('pyhf')
    p,grid,_=fixture()
    grid["templates"].pop("B")
    cal,source,mother=[population(r) for r in ("calibration","template","assessment")]
    scores=[dict(event_id=r.event_id,me_score=r.score) for f in (cal,source,mother) for r in f.itertuples()]
    thresholds=fit_thresholds(cal,cal.score,p,model_id="model",mapping_id="raw:model")
    bundle={"model":None,"model_id":"model","me_scores":scores,"mapping":None,"mapping_id":"raw:model","thresholds":thresholds}
    grid["templates"]["A"]["mapping_id"]="raw:model"
    result=run_assessment_t2(grid,{"A":bundle},cal,source,mother,p,layer="T0",t1_validation=None,
        mu=1.,seed=42,prepared_id="prepared",freeze_id="freeze")
    assert result["outer_replicas"]==1
    assert "candidates" in result["replicas"][0]["result"]
    toy=result["replicas"][0]["result"]["candidates"]["A"]["toys"]
    assert toy["expectation_kind"]=="assessment" and toy["paired"]


def test_t1_auxiliary_policy_and_artificial_stress():
    pytest.importorskip('pyhf')
    p,grid,bundles=fixture()
    grid["templates"].pop("B")
    bundles.pop("B")
    mother=population("assessment")
    evidence=dict(status="validated",evidence_id="synthetic-only",correlation="independent_process_bins",
                  auxiliary="poisson_tau_gamma",modifier="shapesys",pyhf_version="0.7.6")
    p["inference"]["auxiliary_generation"]="fixed"
    fixed=infer_assessment(grid,bundles,mother,p,layer="T1",t1_validation=evidence,mu=1.,count=1,
        seed=42,prepared_id="p",freeze_id="f",categorize=categorize)
    p["inference"]["auxiliary_generation"]="regenerated"
    regen=infer_assessment(grid,bundles,mother,p,layer="T1",t1_validation=evidence,mu=1.,count=1,
        seed=42,prepared_id="p",freeze_id="f",categorize=categorize)
    assert fixed["A"]["toys"]["results"][0]["auxiliary"] != regen["A"]["toys"]["results"][0]["auxiliary"]
    assert fixed["A"]["toys"]["results"][0]["observations"] == regen["A"]["toys"]["results"][0]["observations"]
    with pytest.raises(ResearchStateError,match="modeled stress"):
        run_assessment_stress(grid,bundles,mother,p,layer="T0",t1_validation=None,mu=1.,count=1,
            seed=42,prepared_id="p",freeze_id="f",kind="normalization",direction=1,mode="modeled")
    cal=population("calibration")
    bundle=dict(model=None,model_id="m",mapping=None,mapping_id="raw:m",
                me_scores=[dict(event_id=r.event_id,me_score=r.score) for r in mother.itertuples()],
                thresholds=fit_thresholds(cal,cal.score,p,model_id="m",mapping_id="raw:m"))
    grid["templates"]["A"]["mapping_id"]="raw:m"
    result=run_assessment_stress(grid,{"A":bundle},mother,p,layer="T0",t1_validation=None,mu=1.,count=1,
        seed=42,prepared_id="p",freeze_id="f",kind="normalization",direction=1)
    assert result["A"]["toys"]["expectation_kind"]=="mismatch"
    assert result["A"]["stress"]["source"]=="artificial_pressure_not_physics_systematic"
