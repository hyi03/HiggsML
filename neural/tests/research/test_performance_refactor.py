"""Independent expectations for access, moments, random streams and failures."""
import copy
import time
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.research import inference
from src.research.calibration import _moments, apply_calibration, fit_calibration
from src.research.data import development_spans, iter_development_events, iter_records
from src.research.discriminants import digest
from src.research.errors import ResearchError, ResearchStateError
from src.research.resources import ordered_map, load_resources
from src.research.statistics import GroupBinStatistics, mass_merge_projection
from src.research.templates import build_templates, common_mass_grid


@pytest.mark.parametrize('mask', [[], [True]*11, [False]*11, [True,False]*5,
                                 [True,False,True,True,True,False,True]])
def test_spans_and_payload_request_boundary(mask):
    import awkward as ak
    calls = []
    class Tree:
        def arrays(self, names, *, entry_start, entry_stop, library):
            assert names == ['payload'] and library == 'ak'
            assert all(mask[entry_start:entry_stop])
            assert 0 < entry_stop-entry_start <= 3
            calls.append((entry_start,entry_stop))
            return ak.Array({'payload':[[i] for i in range(entry_start,entry_stop)]})
    identities = {'event':np.arange(len(mask)), 'channel':np.ones(len(mask),int)}
    result = list(iter_development_events(Tree(), {'eventNumber':'event','channelNumber':'channel','x':'payload'},identities,mask,3))
    assert [entry for entry,event in result] == list(np.flatnonzero(mask))
    assert all(event == {'eventNumber':i,'channelNumber':1,'x':[i]} for i,event in result)
    assert calls == list(development_spans(mask,3))


def test_sparse_merge_covariance_and_zero_weight_occupancy():
    # Group a crosses two bins; group b cancels in bin 0 but still occupies it.
    groups = ['a','a','b','b','b','c']
    bins = [0,1,0,0,1,2]
    weights = [3.,4.,2.,-2.,1.,-2.]
    stats = GroupBinStatistics(groups,bins,weights,3)
    y,cov,absolute,positive,negative,counts = stats.moments()
    assert y.tolist() == [3.,5.,-2.]
    assert cov.tolist() == [[9.,12.,0.],[12.,17.,0.],[0.,0.,4.]]
    assert counts.tolist() == [2,2,1]
    stats.merge(mass_merge_projection(3,1,0))
    y,cov,absolute,positive,negative,counts = stats.moments()
    assert y.tolist() == [8.,-2.]
    assert np.diag(cov).tolist() == [50.,4.]  # 9+17+2*12
    assert counts.tolist() == [2,1]  # union, not sum
    assert absolute.tolist() == [12.,2.]


def test_common_grid_matches_independent_rebuild_each_round():
    rng = np.random.default_rng(91)
    f = pd.DataFrame(dict(dataset='synthetic',role='template',label=np.repeat([0,1],90),
                         event_group_id=[f'g{i//2}' for i in range(180)],
                         m4l=rng.integers(0,10,180)+105.5,category=rng.integers(0,2,180),
                         yield_weight=rng.choice([-.25,1.,2.],180)))
    candidates = {'M0':f.assign(category=0),'A':f,'B':f.assign(category=1-f.category)}
    edges = list(range(105,116)); history=[]
    thresholds = {'min_neff_signed':8,'min_rho':.2}
    while True:
        templates = {key:build_templates(frame,mass_edges=edges,mapping_id=key,candidate_id=key,
                    thresholds=thresholds,categories=(0,) if key=='M0' else (0,1)) for key,frame in sorted(candidates.items())}
        bad = [issue['bin']%(len(edges)-1) for t in templates.values() for issue in t['issues']]
        if not bad or len(edges)==2:
            break
        i=min(min(bad)+1,len(edges)-2)
        history.append({'removed_edge':edges[i],'reason':'leftmost_failing_mass_bin_shared_across_candidates'})
        del edges[i]
    result=common_mass_grid(candidates,mass_edges=list(range(105,116)),thresholds=thresholds)
    assert result['merge_history']==history and result['mass_edges']==edges
    assert result['templates']==templates


def test_calibration_multiplicity_and_merge_rechecks_score_conflict():
    f=pd.DataFrame(dict(event_group_id=['a','a','b'],physical_weight=[6.,-2.,3.],bootstrap_multiplicity=[2,2,1]))
    y,v,n,r=_moments(f,[.2,.2,.7],[0,.5,1],'physical')
    assert y.tolist()==[4.,3.] and v.tolist()==[8.,9.]
    assert n==pytest.approx(49/17) and r==pytest.approx(7/11)
    p={'calibration':{'mass_edges':[105,110,115], 'score_edges':[0,.5,1],
        'min_effective_count':10,'min_cancellation_ratio':.2}}
    f=pd.DataFrame(dict(event_group_id=['a','a'],physical_weight=1.,dataset='synthetic',
                        role='calibration',label=0,m4l=[106.,111.]))
    with pytest.raises(ResearchStateError,match='multiple CDF score bins'):
        fit_calibration(f,[.2,.7],p,model_id='m')


@pytest.mark.parametrize('slices', [1,3])
def test_vector_interpolation_matches_scalar_numpy(slices):
    rng=np.random.default_rng(0)
    mapping={'model_id':'m','mass_support':[0.,10.],'score_edges':[0.,.5,1.],
             'slices':[{'center':c,'probabilities':[v,1-v]} for c,v in zip([2.,5.,8.][:slices],[.1,.7,.4])]}
    mapping['mapping_id']=digest(mapping)
    masses=np.r_[0.,2.,5.,8.,10.,rng.uniform(0,10,10000)]
    scores=rng.uniform(-1,2,len(masses))
    curves=np.array([np.interp(scores,mapping['score_edges'],np.r_[0,np.cumsum(s['probabilities'])]) for s in mapping['slices']])
    expected=[np.interp(m,[s['center'] for s in mapping['slices']],curves[:,i]) for i,m in enumerate(masses)]
    np.testing.assert_allclose(apply_calibration(mapping,masses,scores,model_id='m'),expected,rtol=0,atol=1e-15)


def test_profile_shared_fit_and_independent_interval_failure(monkeypatch):
    calls=[]
    mle=SimpleNamespace(fit=lambda *a,**k:(calls.append('fit') or (np.array([1.]),0.)))
    model=SimpleNamespace(config=SimpleNamespace(nmaindata=1,nauxdata=0,auxdata_order=[],poi_index=0,suggested_bounds=lambda:[(0,20)]))
    monkeypatch.setattr(inference,'require_pyhf',lambda:SimpleNamespace(infer=SimpleNamespace(mle=mle)))
    def fixed(mu,*args,**kwargs):
        return None,np.array([(mu-1)**2])
    mle.fixed_poi_fit=fixed
    original=inference.brentq
    def root(function,*args,**kwargs):
        if function(1) > -2:
            raise ValueError('one level only')
        return original(function,*args,**kwargs)
    monkeypatch.setattr(inference,'brentq',root)
    results=inference.profile_intervals(model,[1.])
    assert calls==['fit']
    assert [r['status'] for r in results]==['fit_failed','valid']
    def fail(*args,**kwargs):
        raise ValueError('unconditional failure')
    mle.fit=fail
    assert [r['status'] for r in inference.profile_intervals(model,[1.])]==['fit_failed']*2


def _delayed(value):
    time.sleep(.02*(3-value))
    return value*value


def _broken(value):
    if value==1:
        raise RuntimeError('worker failure')
    return value


def test_ordered_process_execution_and_exception_cleanup():
    assert list(ordered_map(_delayed,range(3),workers=2))==[0,1,4]
    with pytest.raises(RuntimeError,match='worker failure'):
        list(ordered_map(_broken,range(3),workers=2))
    assert list(ordered_map(abs,[-1,-2],workers=2))==[1,2]


def test_t2_workers_preserve_conditional_rng_and_failure_records():
    base=pd.DataFrame(dict(event_group_id=['a','b','c'],physical_weight=[1.,2.,3.],yield_weight=[1.,2.,3.]))
    def fit(frame):
        if 'a' not in set(frame.event_group_id):
            raise ResearchStateError('synthetic sparse replica',status='insufficient_statistics')
        return {'mapping_id':str(frame.physical_weight.sum())}
    def evaluate(t,m,mapping,n,seed):
        return {'status':'valid','draw':np.random.default_rng(seed).poisson(2.,n).tolist()}
    args=dict(fit_mapping=fit,apply_mapping=lambda mp,f:f,evaluate=evaluate,outer_replicas=8,
              inner_toys=2,seed=42,model_id='m',mother_id='mother')
    frames=[base.assign(role=r,event_group_id=[r+g for g in base.event_group_id]) for r in ('template','assessment')]
    # Calibration group names intentionally remain a/b/c.
    a=inference.run_t2_procedure(base.assign(role='calibration'),*frames,**args)
    b=inference.run_t2_procedure(base.assign(role='calibration'),*frames,**args,workers=2)
    assert a==b
    assert any(r['status']=='insufficient_statistics' for r in a['replicas'])
    rng=np.random.default_rng(42)
    for row in a['replicas']:
        counts=rng.multinomial(3,[1/3]*3)
        assert list(row['bootstrap_group_multiplicities'].values())==counts.tolist()
        if counts[0]>0:
            assert row['inner_seed']==int(rng.integers(0,2**31))


def test_toy_workers_equal_serial():
    from tests.research.test_inference import single_bin
    a=inference.run_toys(single_bin(),count=3)
    b=inference.run_toys(single_bin(),count=3,workers=2)
    assert a==b


def test_assessment_worker_pairing_and_auxiliary_equal_serial():
    from tests.research.test_assessment import fixture, population, categorize
    from src.research.assessment import infer_assessment
    p,grid,bundles=fixture()
    args=dict(layer='T0',t1_validation=None,mu=1.,count=2,seed=42,
              prepared_id='p',freeze_id='f',categorize=categorize)
    a=infer_assessment(grid,bundles,population('assessment'),p,**args)
    b=infer_assessment(grid,bundles,population('assessment'),p,**args,workers=2)
    assert a==b


def test_streamed_population_digest_and_multichunk_roundtrip(tmp_path):
    from tests.research.test_data import frame_for_roles
    from src.research.data import write_research_data,load_research_data
    from src.research.protocol import load_protocol
    from src.research.workflow import _population_id
    frame=frame_for_roles()
    # Technical replicas have unique row IDs, preserving each physical group.
    frame=pd.concat([frame.assign(event_id=frame.event_id+f'-{i}',source_row_id=frame.source_row_id+f'-{i}') for i in range(12)],ignore_index=True)
    path=tmp_path/'data.jsonl'
    population=write_research_data(frame,path,load_protocol())
    loaded=load_research_data(path,'atlas2020_4lep',load_protocol())
    assert loaded.attrs['population_id']==population==_population_id(path,'atlas2020_4lep')
    expected=frame.loc[frame.role!='assessment'].reset_index(drop=True)
    from src.research.data import IDENTITY
    columns=sorted(IDENTITY)+sorted(set(frame)-set(IDENTITY))
    assert list(loaded.columns)==columns
    pd.testing.assert_frame_equal(loaded,expected[columns])


def test_cached_auxiliary_layout_preserves_all_draws():
    from tests.research.test_inference import single_bin
    from src.research.stress import auxiliary_sampler,sample_auxiliary
    evidence=dict(status='validated',evidence_id='synthetic',correlation='independent_process_bins',
                  auxiliary='poisson_tau_gamma',modifier='shapesys',pyhf_version='0.7.6')
    model,_=inference.build_model(single_bin(),layer='T1',t1_validation=evidence)
    pars=model.config.suggested_init()
    cached=auxiliary_sampler(model,pars)
    left,right=np.random.default_rng(17),np.random.default_rng(17)
    for _ in range(10):
        np.testing.assert_array_equal(cached(left),sample_auxiliary(model,pars,right))
    assert left.integers(100000)==right.integers(100000)


def test_resource_and_row_scalar_contract(tmp_path):
    path=tmp_path/'resources.json'
    path.write_text('{"workers":true}')
    with pytest.raises(ResearchError):
        load_resources(path)
    frame=pd.DataFrame({'int':pd.Series([1,2],dtype='int64'),'float':[.1,.2],'list':[[1],[2]],'bool':[True,False]})
    frame['object_number']=pd.Series([np.int64(3),pd.NA],dtype=object)
    frame['nullable']=pd.Series([1,None],dtype='Int64')
    assert list(iter_records(frame))==frame.to_dict('records')
