"""Synthetic numerical checks; no measured physical-systematic interpretation."""
from copy import deepcopy
import numpy as np
import pandas as pd
import pytest
from scipy.special import gammaln

from src.research.errors import ResearchError,ResearchStateError
from src.research.protocol import load_protocol
from src.research.templates import build_templates
from src.research.stress import build_stress_templates,build_stress_model,sample_auxiliary
from src.research.inference import build_model,profile_interval
from src.research.assessment import run_assessment_stress
from src.research.calibration import fit_thresholds


def events(role='template'):
    return pd.DataFrame([dict(dataset='atlas2020_4lep',role=role,event_group_id=f'{role}-{label}-{i}',
        event_id=f'{role}-{label}-{i}',label=label,m4l=106.+i%4*8.,yield_weight=(.5 if label else 1.),
        physical_weight=1.,category=i%2,reference_score=(i+.5)/48,score=(i+.5)/48)
        for label in (0,1) for i in range(48)])


def fixture(kind='normalization',categories=(0,1)):
    p=load_protocol().to_dict()
    f=events()
    if categories==(0,):
        f['category']=0
    t=build_templates(f,mass_edges=[105,140],mapping_id='m',candidate_id='M3',categories=categories,thresholds=p['templates'])
    r=build_stress_templates(f,t,kind=kind,reference_mapping_id='common-reference',protocol=p)
    return p,f,t,r


def evidence():
    return dict(status='validated',evidence_id='synthetic-single-bin-test-only',correlation='independent_process_bins',
        auxiliary='poisson_tau_gamma',modifier='shapesys',pyhf_version='0.7.6')


def test_normalization_normal_constraint_matches_closed_form_likelihood():
    pytest.importorskip('pyhf')
    p,f,t,r=fixture(categories=(0,))
    model,meta=build_stress_model(t,r,protocol=p)
    pars=model.config.suggested_init()
    nuisance=model.config.par_map[meta['stress_nuisance']]['slice']
    for theta in (-1.,0.,1.):
        pars[nuisance]=[theta]
        # Signal=24, background=48; normsys endpoints are exactly +/-10%.
        rate=24+48*(1+.1*theta)
        observation=72.
        aux=-.7  # a negative normal observation is valid
        data=np.array([observation,aux])
        expected_nll=2*(rate-observation*np.log(rate)+gammaln(observation+1)+.5*(aux-theta)**2+.5*np.log(2*np.pi))
        assert float(np.asarray(-2*model.logpdf(pars,data)).reshape(-1)[0])==pytest.approx(expected_nll,abs=1e-8)
    pars[nuisance]=[1.]
    interval=profile_interval(model,model.expected_data(pars))
    assert interval['muhat']==pytest.approx(1.,abs=2e-4)
    negative_aux=profile_interval(model,np.array([72.,-.7]))
    assert negative_aux['status']=='valid'
    with pytest.raises(ResearchError):
        profile_interval(model,[-1.,-.7])


def test_auxiliary_moments_dispatch_normal_and_poisson():
    pytest.importorskip('pyhf')
    p,f,t,r=fixture(categories=(0,))
    model,meta=build_stress_model(t,r,protocol=p,layer='T1',t1_validation=evidence())
    pars=model.config.suggested_init()
    pars[model.config.par_map[meta['stress_nuisance']]['slice']]=[-1.]
    expected=np.asarray(model.expected_auxdata(pars))
    rng=np.random.default_rng(491)
    draws=np.asarray([sample_auxiliary(model,pars,rng) for _ in range(16000)])
    offset=0
    for name in model.config.auxdata_order:
        param=model.config.param_set(name)
        n=param.n_parameters
        column=draws[:,offset:offset+n]
        assert np.allclose(column.mean(axis=0),expected[offset:offset+n],atol=.15)
        variance=np.ones(n) if param.pdf_type=='normal' else expected[offset:offset+n]
        assert np.allclose(column.var(axis=0),variance,rtol=.045,atol=.04)
        if param.pdf_type=='normal':
            assert (column<0).any() and not np.array_equal(column,column.astype(int))
        else:
            assert np.array_equal(column,column.astype(int))
        offset+=n
    assert np.array_equal(sample_auxiliary(model,pars,rng,policy='fixed'),expected)
    values=expected.copy()
    offset=0
    for name in model.config.auxdata_order:
        param=model.config.param_set(name)
        if param.pdf_type=='poisson':
            values[offset]=-1
            break
        offset+=param.n_parameters
    with pytest.raises(ResearchError,match='Poisson'):
        profile_interval(model,np.r_[model.expected_actualdata(pars),values])


def test_shape_histosys_endpoints_preserve_yield_and_t1_refuses_changed_variance():
    pytest.importorskip('pyhf')
    p,f,t,r=fixture('mass')
    model,meta=build_stress_model(t,r,protocol=p)
    assert meta['stress_modifier']=='histosys'
    for direction,key in ((-1.,'down'),(1.,'up')):
        assert sum(r[key]['samples'][0]['yield'])==pytest.approx(sum(t['samples'][0]['yield']))
        pars=model.config.suggested_init()
        pars[model.config.par_map[meta['stress_nuisance']]['slice']]=[direction]
        assert model.expected_actualdata(pars)==pytest.approx(np.sum([s['yield'] for s in r[key]['samples']],axis=0))
    with pytest.raises(ResearchStateError,match='relative MC variance') as exc:
        build_stress_model(t,r,protocol=p,layer='T1',t1_validation=evidence())
    assert exc.value.status=='template_stat_model_unvalidated'


def test_stress_contract_and_source_are_frozen():
    p,f,t,r=fixture()
    bad=deepcopy(p)
    bad['stress']['amplitude']=.2
    with pytest.raises(ResearchError,match='versioned'):
        build_stress_model(t,r,protocol=bad)
    with pytest.raises(ResearchError,match='support thresholds'):
        build_stress_templates(f,t,kind='normalization',reference_mapping_id='r',protocol=p,thresholds={'min_neff_signed':1})
    with pytest.raises(ResearchError,match='template role'):
        build_stress_templates(f.assign(role='assessment'),t,kind='normalization',reference_mapping_id='r',protocol=p)
    changed=f.copy();changed.loc[0,'yield_weight']*=2
    with pytest.raises(ResearchError,match='nominal moments'):
        build_stress_templates(changed,t,kind='normalization',reference_mapping_id='r',protocol=p)
    with pytest.raises(ResearchError,match='reference candidate'):
        run_assessment_stress({}, {},events('assessment'),p,layer='T0',t1_validation=None,
            mu=1.,count=1,seed=42,prepared_id='p',freeze_id='f',kind='score',direction=1,
            reference_candidate='assessment-picked-candidate')


def test_modeled_assessment_shares_artificial_auxiliary_and_records_truth():
    pytest.importorskip('pyhf')
    p=load_protocol().to_dict()
    p['inference']['toy_count']=2
    source,mother,cal=[events(role) for role in ('template','assessment','calibration')]
    threshold=fit_thresholds(cal,cal.score,p,model_id='model',mapping_id='raw:model')
    from src.research.calibration import assign_categories
    source['category']=assign_categories(threshold,source.score,model_id='model',mapping_id='raw:model')
    scores=[dict(event_id=row.event_id,me_score=row.score) for f in (source,mother) for row in f.itertuples()]
    bundle=dict(model=None,model_id='model',me_scores=scores,mapping=None,mapping_id='raw:model',thresholds=threshold)
    nominal=build_templates(source,mass_edges=[105,140],mapping_id='raw:model',candidate_id='M3',thresholds=p['templates'])
    mass=build_templates(source.assign(category=0),mass_edges=[105,140],mapping_id='mass',candidate_id='M0',categories=(0,),thresholds=p['templates'])
    grid=dict(status='valid',mass_edges=[105,140],templates={'A':nominal,'B':deepcopy(nominal),'M0':mass})
    result=run_assessment_stress(grid,{'A':bundle,'B':deepcopy(bundle)},mother,p,layer='T0',t1_validation=None,
        mu=1.,count=2,seed=42,prepared_id='prepared',freeze_id='frozen',kind='normalization',direction=-1,
        mode='modeled',template_frame=source)
    for candidate in result.values():
        assert candidate['toys']['expectation_kind']=='assessment_with_modeled_artificial_stress'
        assert candidate['asimov']['nuisance_truth']==-1
        assert candidate['asimov']['nominal_nuisance_asimov']['nuisance_truth']==0
        assert candidate['stress']['source']=='artificial_pressure_not_physics_systematic'
        assert candidate['stress_response']['up']['samples'][0]['variance']
    for i in range(2):
        assert result['A']['toys']['results'][i]['auxiliary']==result['B']['toys']['results'][i]['auxiliary']==result['M0']['toys']['results'][i]['auxiliary']
