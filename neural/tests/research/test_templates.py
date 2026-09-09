import numpy as np
import pandas as pd
import pytest
from src.research.templates import build_templates, common_mass_grid, gate_g1
from src.research.errors import ResearchError


def sample():
    return pd.DataFrame([{"dataset":"synthetic","label":label,"role":"template","event_group_id":f"{label}-{i}","yield_weight":1.,"m4l":106.+i%2*2,"category":i%2} for label in (0,1) for i in range(8)])


def test_group_covariance_not_row_independent():
    frame=sample(); frame.loc[1,"event_group_id"]=frame.loc[0,"event_group_id"]
    t=build_templates(frame,mass_edges=[105,110],mapping_id="m",candidate_id="M4",thresholds={"min_neff_signed":1})
    assert t["samples"][0]["covariance"][0][1]==1
    assert t["samples"][0]["variance"]==[4.,4.]
    duplicate=pd.concat([frame,frame],ignore_index=True)
    doubled=build_templates(duplicate,mass_edges=[105,110],mapping_id="m",candidate_id="M4",thresholds={"min_neff_signed":1})
    assert doubled["samples"][0]["variance"]==[16.,16.]


def test_role_negative_and_structural_zero():
    frame=sample(); frame["role"]="assessment"
    with pytest.raises(ResearchError): build_templates(frame,mass_edges=[105,110],mapping_id="m",candidate_id="M4")
    frame["role"]="template"; frame.loc[frame.label==0,"yield_weight"]=-1
    result=build_templates(frame,mass_edges=[105,110,115],mapping_id="m",candidate_id="M4")
    assert result["status"]=="insufficient_statistics"
    assert result["samples"][0]["bin_status"]==["nonpositive_yield","insufficient_statistics","nonpositive_yield","insufficient_statistics"]


def test_shared_grid_and_gate():
    f=sample()
    result=common_mass_grid({"M4":f,"M5":f},mass_edges=[105,107,110],thresholds={"min_neff_signed":4})
    assert result["mass_edges"]==[105,110]  # finite empty process bins require common merging
    with pytest.raises(ResearchError): common_mass_grid({"M4":f},mass_edges=[105,110],thresholds={},assessment_started=True)
    assert gate_g1({"M4":"valid"},result["templates"],{"status":"unvalidated"})["status"]=="blocked"


def test_finite_empty_bins_not_structural_without_bound_evidence():
    f=pd.DataFrame([dict(dataset='synthetic',role='template',label=k,event_group_id=f'{k}-{i}',yield_weight=1.,m4l=106.,category=k) for k in [0,1] for i in range(30)])
    args=dict(mass_edges=[105,110,115],mapping_id='m',candidate_id='M4')
    t=build_templates(f,**args)
    assert t['status']=='insufficient_statistics'
    assert t['active_bins']==[0,1,2,3]
    evidence=dict(status='validated',evidence_id='synthetic-support-only',mapping_id='m',mass_edges=[105,110,115],categories=[0,1],bins_by_process={'0':[1,2,3],'1':[0,1,3]})
    proven=build_templates(f,**args,structural_zero_evidence=evidence)
    assert proven['status']=='valid' and proven['active_bins']==[0,2]
    evidence['mapping_id']='wrong'
    with pytest.raises(ResearchError,match='Structural-zero'):
        build_templates(f,**args,structural_zero_evidence=evidence)


def test_mass_only_declares_one_category_and_g1_checks_actual_covariance():
    f=sample()
    grid=common_mass_grid({'M0':f.assign(category=0),'M4':f},mass_edges=[105,110],thresholds={'min_neff_signed':1})
    assert grid['templates']['M0']['categories']==[0]
    f.loc[1,'event_group_id']=f.loc[0,'event_group_id']
    t=build_templates(f,mass_edges=[105,110],mapping_id='m',candidate_id='M4',thresholds={'min_neff_signed':1})
    assert t['status']=='valid'
    evidence=dict(status='validated',evidence_id='synthetic-only',correlation='independent_process_bins',auxiliary='poisson_tau_gamma',modifier='shapesys',pyhf_version='0.7.6')
    assert gate_g1({'M4':'valid'},{'M4':t},evidence)['status']=='blocked'
