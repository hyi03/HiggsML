import copy
import numpy as np
import pandas as pd
import pytest

from src.research.calibration import (constrained_distribution,fit_calibration,apply_calibration,
    fit_thresholds,assign_categories,bootstrap_calibration)
from src.research.errors import ResearchError,ResearchStateError
from src.research.protocol import load_protocol


def frame(n=280):
    return pd.DataFrame(dict(m4l=np.repeat(np.arange(107.5,140,5),n//7),label=0,
       role='calibration',dataset='atlas2020_4lep',physical_weight=1.,yield_weight=2.,
       event_group_id=[str(i) for i in range(n)]))


def test_signed_constrained_fit_uses_variance_not_clip():
    fit=constrained_distribution([-1,4,2],[1,4,1])
    assert fit['fitted_yields']==pytest.approx([0,3.2,1.8])
    assert sum(fit['probabilities'])==pytest.approx(1)
    assert fit['correction_chi2']>0
    assert fit['fitted_yields']!=[0,4,2]
    with pytest.raises(ResearchStateError,match='nonpositive'):
        constrained_distribution([-1,1],[1,1])


def test_uniform_cdf_interpolation_ties_tails_and_model_binding():
    data=frame()
    scores=np.tile((np.arange(40)+.5)/40,7)
    mapping=fit_calibration(data,scores,load_protocol(),model_id='model')
    got=apply_calibration(mapping,[105,125,140,120,120],[-2,.5,2,.3,.3],model_id='model')
    assert got==pytest.approx([0,.5,1,.3,.3])
    assert len(mapping['slices'])==7
    with pytest.raises(ResearchError,match='binding'):
        apply_calibration(mapping,[120],[.5],model_id='wrong')
    with pytest.raises(ResearchStateError) as exc:
        apply_calibration(mapping,[100],[.5],model_id='model')
    assert exc.value.status=='outside_calibration_support'
    broken=copy.deepcopy(mapping)
    broken['slices'][0]['probabilities'][0]=.9
    with pytest.raises(ResearchError,match='digest'):
        apply_calibration(broken,[120],[.5],model_id='model')


def test_negative_bridge_and_deterministic_support_merges():
    data=frame(140)
    scores=np.tile((np.arange(20)+.5)/20,7)
    data.loc[0,'physical_weight']=-.5
    physical=fit_calibration(data,scores,load_protocol(),model_id='m')
    absolute=fit_calibration(data,scores,load_protocol(),target='absolute',model_id='m')
    assert physical['mapping_id']!=absolute['mapping_id']
    assert physical['merges'][0]==[105,110,110,115]
    assert physical==fit_calibration(data,scores,load_protocol(),model_id='m')
    data.physical_weight=-1.
    with pytest.raises(ResearchStateError) as exc:
        fit_calibration(data,scores,load_protocol(),model_id='m')
    assert exc.value.status=='nonpositive_calibration_yield'


def test_role_isolation_thresholds_and_plateau():
    data=frame()
    scores=np.full(len(data),.5)
    mapping=fit_calibration(data,scores,load_protocol(),model_id='m')
    cdf=apply_calibration(mapping,data.m4l,scores,model_id='m')
    assert len(set(cdf))==1
    thresholds=fit_thresholds(data,cdf,load_protocol(),model_id='m',mapping_id=mapping['mapping_id'])
    categories=assign_categories(thresholds,cdf,model_id='m',mapping_id=mapping['mapping_id'])
    assert len(set(categories))==1  # never invent identity-based splits for ties
    data.loc[0,'role']='assessment'
    with pytest.raises(ResearchError,match='role'):
        fit_calibration(data,scores,load_protocol(),model_id='m')


def test_bootstrap_preserves_group_pairing():
    data=frame()
    data.loc[1,'event_group_id']=data.loc[0,'event_group_id']
    a=bootstrap_calibration(data,42)
    b=bootstrap_calibration(data,42)
    pd.testing.assert_frame_equal(a,b)
    assert a.groupby('event_group_id').bootstrap_multiplicity.nunique().max()==1
    assert np.all(a.yield_weight==2*a.physical_weight)


def test_group_covariance_is_refused_instead_of_diagonalized():
    data=frame()
    scores=np.tile((np.arange(40)+.5)/40,7)
    data.loc[8,'event_group_id']=data.loc[0,'event_group_id']
    with pytest.raises(ResearchStateError) as exc:
        fit_calibration(data,scores,load_protocol(),model_id='m')
    assert exc.value.status=='template_stat_model_unvalidated'
    data=frame()
    data.loc[40,'event_group_id']=data.loc[0,'event_group_id']
    with pytest.raises(ResearchStateError) as exc:
        fit_calibration(data,scores,load_protocol(),model_id='m')
    assert exc.value.status=='template_stat_model_unvalidated'
