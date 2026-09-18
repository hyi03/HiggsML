"""Synthetic probability/identity proofs, not controlled-MC qualification."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
import pytest
from higgsml.errors import ResearchError
from higgsml.inference.marginal_coupling import (
    canonical_seed_blocks, diagnose_marginal_support, marginal_toys, cell_stream,
    ROLE_MAP, close, pairing_contract)


def fixture():
    block=canonical_seed_blocks()[0]
    rows=[]
    columns={key:f'c{i}' for i,key in enumerate(block.candidate_keys)}
    for label in (0,1):
        for b in (0,1):
            for i in range(4):
                row=dict(event_id=f'{label}:{b}:{i}',source_row_id=str(i),event_group_id=f'{label}:{b}:{i}',
                         label=label,m4l=110.+15*b,yield_weight=2.)
                row.update({col:1 if key.startswith('M0off:') else int(i<(j%3)+1)
                            for j,(key,col) in enumerate(columns.items())})
                rows.append(row)
    return block,pd.DataFrame(rows),columns


def support():
    b,f,c=fixture()
    return b,diagnose_marginal_support(f,block=b,category_columns=c,mass_edges=[105,120,140])


def draw(b,s,**kw):
    return marginal_toys(s,block=b,mass_edges=[105,120,140],mu=1,count=12000,
                         stage='model-self',toy_base_seed=42,**kw)


def test_poisson_marginals_independent_bins_and_monotone_common_totals():
    b,s=support(); result=draw(b,s)
    baseline=np.asarray(result['observations'][b.candidate_keys[0]])
    for key,values in result['observations'].items():
        values=np.asarray(values)
        assert np.array_equal(values[:,:2]+values[:,2:],(baseline[:,:2]+baseline[:,2:]))
        expected=np.zeros(4)
        for cell in s['cells']:
            if cell['candidate_id']==key:
                expected[cell['mass_bin']+2*cell['category']]+=cell['signed_sum']
        assert np.all(np.abs(values.mean(axis=0)-expected)<.45)
        assert np.all(np.abs(values.var(axis=0)-expected)<1.4)
    x=np.asarray(result['observations'][b.candidate_keys[1]])
    covariance=np.cov(x.T)
    assert np.max(np.abs(covariance-np.diag(np.diag(covariance))))<1.1
    independent=draw(b,s,independent_allocation=True)
    for values in independent['observations'].values():
        values=np.asarray(values)
        assert np.array_equal(values[:,:2]+values[:,2:],(baseline[:,:2]+baseline[:,2:]))


def test_streams_permutation_parallel_and_negative_rejection():
    b,f,c=fixture()
    s=diagnose_marginal_support(f,block=b,category_columns=c,mass_edges=[105,120,140])
    shuffled=diagnose_marginal_support(f.sample(frac=1,random_state=3),block=b,
        category_columns=dict(reversed(list(c.items()))),mass_edges=[105,120,140])
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda v:draw(b,v),[s,shuffled]))
    assert results[0]['observations']==results[1]['observations']
    f.loc[0,'yield_weight']=-3
    # One candidate separates this negative event from positive support.
    col=c[b.candidate_keys[1]]; f[col]=0; f.loc[0,col]=1
    bad=diagnose_marginal_support(f,block=b,category_columns=c,mass_edges=[105,120,140])
    assert 'negative_marginal_rate' in bad['summary']['failures']
    assert bad['summary']['identity_qualification']=='label_level_legacy'


def test_role_mapping_numeric_boundaries_and_stream_identity():
    b,f,c=fixture()
    with pytest.raises(ResearchError,match='role map'):
        diagnose_marginal_support(f,block=b,category_columns=c,mass_edges=[105,120,140],role_map={'0':'signal','1':'background'})
    assert close(1+1.9e-10,1) and not close(1+2.1e-10,1)
    assert close(.9e-10,0) and not close(1.1e-10,0)
    ids=set()
    for process in ('0','1'):
        for mass_bin in (0,1):
            for toy in (0,1):
                for kind in ('physical_total_poisson','shared_category_uniform','candidate_auxiliary'):
                    ids.add(cell_stream(block=b,stage='model-self',mu=1,outer_index=None,
                        toy_index=toy,process=process,mass_bin=mass_bin,kind=kind,toy_base_seed=42)['stream_id'])
    assert len(ids)==24
    assert pairing_contract()['physical_event_pairing'] is False


def test_physical_process_negative_hidden_by_label():
    b,f,c=fixture()
    f['process']=np.where(f.label==1,'signal',np.where(f.source_row_id=='0','bad','good'))
    f.loc[f.process=='bad','yield_weight']=-.1
    for column in c.values():
        f[column]=1
    roles={'signal':'signal','bad':'background','good':'background'}
    actual=diagnose_marginal_support(f,block=b,category_columns=c,mass_edges=[105,120,140],role_map=roles)
    assert actual['summary']['qualification']=='insufficient_statistics'
    legacy=diagnose_marginal_support(f.drop(columns='process'),block=b,category_columns=c,mass_edges=[105,120,140])
    assert legacy['summary']['qualification']=='valid'
    assert legacy['summary']['limitations']


@pytest.mark.parametrize('failure_status',['insufficient_statistics','unsupported_assessment_support'])
def test_t2_late_preflight_failure_generates_no_inner_toys(failure_status):
    from higgsml.inference.likelihood import run_t2_procedure
    from higgsml.errors import ResearchStateError
    frames=[pd.DataFrame({'event_group_id':[role+'1',role+'2'],'role':[role]*2,
                          'yield_weight':[1.,1.]}) for role in ('calibration','template','assessment')]
    calls=[]; mappings=[]
    def mapping(frame):
        index=len(mappings); mappings.append(index)
        return {'mapping_id':str(index)}
    def preflight(*args):
        if args[2]['mapping_id']=='2':
            raise ResearchStateError('later outer unsupported',status=failure_status)
        return {'qualification':'valid'}
    result=run_t2_procedure(*frames,fit_mapping=mapping,apply_mapping=lambda m,f:f,
        evaluate=lambda *args:calls.append(args),preflight=preflight,
        outer_replicas=4,inner_toys=3,seed=1,model_id='model',mother_id='mother')
    assert len(result['replicas'])==4 and mappings==[0,1,2,3]
    assert not calls and result['generated_physical_toys']==0
    assert result['replicas'][2]['preflight_status']==failure_status
    assert result['status']==failure_status and result['preflight_failure_statuses']==[failure_status]
    assert all(r['generated_inner_toys']==0 for r in result['replicas'])


def test_inference_v3_uses_marginals_and_emits_conditional_receipts(monkeypatch):
    from types import SimpleNamespace
    from higgsml.inference import assessment as a
    from higgsml.inference.attribution import FAMILY
    from higgsml.protocol import load_protocol
    block,frame,columns=fixture()
    protocol=load_protocol().to_dict()
    frame=frame.assign(role='template',dataset=protocol['dataset'])
    supported=diagnose_marginal_support(frame,block=block,category_columns=columns,mass_edges=[105,120,140])
    templates={}; bundles={}
    for key in block.candidate_keys:
        samples=[]
        for p in ('0','1'):
            values=[next(r['rates'][k] for r in supported['marginals'] if r['candidate_id']==key and r['process']==p and r['mass_bin']==b)
                    for k in (0,1) for b in (0,1)]
            samples.append({'name':p,'is_signal':p=='1','yield':values})
        templates[key]={'mapping_id':'map','mass_edges':[105,120,140],'categories':[0,1],
                        'samples':samples,'active_bins':[2,3] if key.startswith('M0off:') else [0,1,2,3]}
        bundles[key]={'mapping_id':'map','key':key}
    model=SimpleNamespace(config=SimpleNamespace(suggested_init=lambda:[1.],poi_index=0,auxdata_order=[]))
    monkeypatch.setattr(a,'build_model',lambda *args,**kw:(model,{}))
    monkeypatch.setattr(a,'auxiliary_sampler',lambda *args:lambda *args,**kw:np.array([]))
    monkeypatch.setattr(a,'profile_intervals',lambda *args:[{'status':'valid','lower':.5,'upper':1.5,'muhat':1.}]*2)
    monkeypatch.setattr(a,'run_asimov',lambda *args,**kw:{'status':'valid'})
    result=a.infer_assessment({'status':'valid','mass_edges':[105,120,140],'templates':templates,'family_id':FAMILY},
        bundles,frame,protocol,layer='T0',t1_validation=None,mu=1,count=2,seed=42,prepared_id='p',freeze_id='f',
        seed_block=block,parent_role='template',coupling_context={'stage':'model-self','toy_base_seed':42},
        categorize=lambda bundle,f:f.assign(category=f[columns[bundle['key']]]))
    assert len(result)==16
    for row in result.values():
        assert row['physical_event_pairing'] is False and row['attempted_fits']==2
        assert row['toys']['pairing']=='marginal_common_total_monotone_crn'
        assert row['coupling_receipt']['identity_qualification']=='label_level_legacy'


def test_zero_injection_and_bound_support_receipt():
    from copy import deepcopy
    b,s=support()
    zero=marginal_toys(s,block=b,mass_edges=[105,120,140],mu=0,count=300,
                       stage='model-self',toy_base_seed=42)
    for cell in zero['coupling_receipt']['cells']:
        if cell['process']=='1':
            assert cell['injected_rate']==0
    changed=deepcopy(s);changed['totals'][0]['rate']+=1
    with pytest.raises(ResearchError,match='receipt binding'):
        marginal_toys(changed,block=b,mass_edges=[105,120,140],mu=1,count=1,
                       stage='model-self',toy_base_seed=42)
    b,frame,columns=fixture()
    with pytest.raises(ResearchError,match='role map'):
        diagnose_marginal_support(frame,block=b,category_columns=columns,mass_edges=[105,120,140],role_map={})


def test_zero_parent_bin_has_explicit_null_theta_marker():
    block,frame,columns=fixture()
    frame=frame[frame.m4l<120]
    s=diagnose_marginal_support(frame,block=block,category_columns=columns,mass_edges=[105,120,140])
    result=marginal_toys(s,block=block,mass_edges=[105,120,140],mu=1,count=2,stage='model-self',toy_base_seed=42)
    for cell in result['coupling_receipt']['cells']:
        if cell['mass_bin']==1:
            assert cell['zero_total'] is True and cell['zero_injected_total'] is True
            assert all(v is None for v in cell['theta'].values())
