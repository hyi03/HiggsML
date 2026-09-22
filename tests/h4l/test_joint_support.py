"""Independent synthetic expectations for the joint selector contract."""
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from higgsml.errors import ResearchError
from higgsml.modeling.joint_support import (analysis_contract, bootstrap_counts, method_contract,
    select_joint_threshold, support_records)
from higgsml.modeling.calibration import assign_categories, fit_thresholds
from higgsml.protocol import load_protocol


def population(role, n=100):
    scores = np.tile(np.linspace(.01, .99, n), 2)
    frame = pd.DataFrame(dict(role=role, dataset='atlas2020_4lep', m4l=125.,
        event_group_id=[f'{role}:{i}' for i in range(2*n)], label=np.repeat([0,1],n),
        physical_weight=1., yield_weight=5., process=np.repeat(['b','s'],n)))
    return frame, scores


def select(c=None, t=None):
    p = load_protocol().to_dict()
    c = population('calibration') if c is None else c
    t = population('template') if t is None else t
    return select_joint_threshold(*c, *t, p, method_contract(),
        dict(model_id='model', mapping_id='raw:model', candidate_key='M3:42:groups=A:m4l=off', seed=42),
        dict(analysis_contract_digest=analysis_contract(p)['analysis_contract_digest'],
             prepared_artifact_id='prepared', population_id='population', source_artifact_id='source'),
        dict(stage='synthetic_test'))


def test_median_and_record_identity():
    result = select()
    assert result['status'] == 'valid'
    assert result['selected_quantile_numerator'] == 10
    assert result['selected_threshold'] == pytest.approx(.5)
    assert len(result['candidates']) == 19
    c,s = population('calibration')
    median = fit_thresholds(c,s,load_protocol(),model_id='model',mapping_id='raw:model')
    assert result['thresholds'] == median['thresholds']
    assert result['threshold_id'] != median['threshold_id']
    assert assign_categories(result,[.49,result['selected_threshold'],result['selected_threshold'],.51],model_id='model',mapping_id='raw:model').tolist() == [0,1,1,1]


def test_template_selects_different_cut_and_no_fallback():
    t,s = population('template')
    # Only 10 signal groups below .5, 25 below .55: median fails, q=.55 passes.
    s[100:] = np.r_[np.full(10,.25),np.full(15,.525),np.full(75,.75)]
    result = select(t=(t,s))
    assert result['selected_quantile_numerator'] == 11
    assert not result['candidates'][9]['feasible']
    s[100:] = .75
    result = select(t=(t,s))
    assert result['status'] == 'no_feasible_joint_threshold'
    assert result['thresholds'] == []
    assert len(result['candidates']) == 19


def test_group_first_signed_multiplicity_hand_calculation():
    frame = pd.DataFrame(dict(event_group_id=['a','a','b'], process='b',
        physical_weight=[6.,-2.,3.], bootstrap_multiplicity=[2,2,3]))
    # Two copies of group (3,-1), three copies of group (1): y=7, v=11, abs=11.
    records = support_records(frame,np.array([.1,.1,.1]),.5,'physical_weight','process')
    low,high = records
    assert low['y'] == 7 and low['variance'] == 11 and low['sum_abs_weight'] == 11
    assert low['neff_signed'] == pytest.approx(49/11)
    assert low['rho'] == pytest.approx(7/11)
    assert low['group_occupancy'] == 5
    assert high['neff_signed'] is None and 'empty_category' in high['reasons']


def test_process_role_and_score_rejections():
    t,s = population('template')
    t.loc[t.label==1,'process']='other'
    with pytest.raises(ResearchError,match='role/process'):
        select(t=(t,s))
    t,s = population('template');s[0]=np.nan
    with pytest.raises(ResearchError,match='support mismatch'):
        select(t=(t,s))
    t,s = population('template');t['role']='assessment'
    with pytest.raises(ResearchError,match='forbidden'):
        select(t=(t,s))


def test_projection_cross_bin_group_failure_preserved():
    c,s = population('calibration')
    c.loc[90,'event_group_id'] = c.loc[0,'event_group_id']
    result = select(c=(c,s))
    assert result['status'] == 'template_stat_model_unvalidated'
    assert result['candidates'] == []


def test_bootstrap_and_toy_rng_isolation():
    from higgsml.inference.marginal_coupling import canonical_seed_blocks, cell_stream
    groups = np.array([str(i) for i in range(100)])
    contract = analysis_contract(load_protocol())['analysis_contract_digest']
    a = bootstrap_counts(groups,contract,0,'calibration')
    assert np.array_equal(a,bootstrap_counts(groups,contract,0,'calibration'))
    assert not np.array_equal(a,bootstrap_counts(groups,contract,0,'template'))
    assert not np.array_equal(a,np.random.default_rng(42001).multinomial(100,np.full(100,.01)))
    assert not np.array_equal(a,np.random.default_rng(20260922).multinomial(100,np.full(100,.01)))
    block = canonical_seed_blocks()[0]
    kwargs = dict(stage='model-self',mu=1,outer_index=None,toy_index=0,process='b',mass_bin=0,kind='total',toy_base_seed=42)
    assert cell_stream(block=block,**kwargs)['seed'] != cell_stream(block=replace(block,analysis_contract_digest=contract),**kwargs)['seed']
    assert block.rng_contract_digest != replace(block,analysis_contract_digest=contract).rng_contract_digest


def test_support_grid_matches_independent_two_bin_group_moments():
    from higgsml.modeling.joint_support import support_grid
    frame = pd.DataFrame(dict(event_group_id=['a','a','b','c','c','d'],process='b',
        physical_weight=[6.,-2.,3.,-1.,4.,2.],bootstrap_multiplicity=[2,2,3,1,1,2]))
    scores = np.array([.1,.6,.3,.2,.8,.7])
    cuts = [.2,.5,.5,.7]
    grid = support_grid(frame,scores,cuts,'physical_weight','process')
    for cut,rows in zip(cuts,grid):
        expected = support_records(frame,scores,cut,'physical_weight','process')
        for row,reference in zip(rows,expected):
            assert row == reference


def test_joint_schema_and_content_binding():
    from higgsml.modeling.joint_support import validate_threshold
    p = load_protocol().to_dict()
    record = select()
    validate_threshold(record,p)
    record['draw_identity']['stage'] = 'other_draw'
    with pytest.raises(ResearchError,match='record binding'):
        validate_threshold(record,p)


def test_joint_bootstrap_paired_roles_and_parallel_failure_identity(monkeypatch):
    from higgsml.inference import bootstrap
    from higgsml.inference.attribution import BUDGETS, candidate_keys
    from higgsml.modeling import joint_support
    from higgsml.errors import ResearchStateError
    p=load_protocol().to_dict()
    contract=analysis_contract(p)['analysis_contract_digest']
    monkeypatch.setitem(BUDGETS['mc_bootstrap'],'replicas',2)
    bundles={key:dict(model_id=key,mapping_id='raw:'+key,model={},transform='raw',mapping=None,
        key=key,seed=42,candidate_id='M3',thresholds={'analysis_contract_digest':contract}) for key in candidate_keys()}
    grid=dict(mass_edges=[105,140],templates={key:{} for key in bundles},analysis_contract_digest=contract)
    c,_=population('calibration');t,_=population('template')
    calls=[]
    def refit(bundle,calibration,template,protocol,*,draw_identity):
        assert set(calibration.role)=={'calibration'} and set(template.role)=={'template'}
        assert set(calibration.event_group_id).isdisjoint(template.event_group_id)
        assert set(calibration.physical_weight)=={1.} and set(template.yield_weight)=={5.}
        calls.append(draw_identity['replica'])
        error=ResearchStateError('no cut',status='no_feasible_joint_threshold')
        error.threshold_record={'status':error.status,'candidates':list(range(19))}
        raise error
    monkeypatch.setattr(joint_support,'refit_bundle',refit)
    serial=bootstrap.mass_off_mc_bootstrap(grid,bundles,c,t,p,t1_validation={})
    assert len(calls)==160
    parallel=bootstrap.mass_off_mc_bootstrap(grid,bundles,c,t,p,t1_validation={},workers=2)
    assert serial==parallel
    assert serial['status']=='bootstrap_incomplete' and serial['valid_replicas']==0
    assert serial['planned_replicas']==2 and serial['failed_replicas']==2
    assert serial['selection_diagnostics']['failed_selections']==160
    for row in serial['replicas']:
        assert len(row['candidate_states'])==80
        assert len(row['counts_digests'])==2


def test_equal_distance_uses_integer_lower_quantile(monkeypatch):
    from higgsml.modeling import joint_support
    original=joint_support.support_grid
    def support(*args):
        rows=original(*args)
        for k,items in enumerate(rows,1):
            for item in items:
                item['status']='valid' if k in (9,11) else 'insufficient_statistics'
        return rows
    monkeypatch.setattr(joint_support,'support_grid',support)
    assert select()['selected_quantile_numerator']==9


def test_method_configuration_conflict_is_not_silently_overridden(monkeypatch):
    import json
    from pathlib import Path
    original=Path.read_text
    def altered(path,*args,**kwargs):
        text=original(path,*args,**kwargs)
        if path.name=='h4l_off_joint_support_v1.json':
            value=json.loads(text);value['min_neff_signed']=19
            return json.dumps(value)
        return text
    monkeypatch.setattr(Path,'read_text',altered)
    with pytest.raises(ResearchError,match='configuration differs'):
        method_contract()


def test_t2_refits_calibration_against_fixed_template(monkeypatch):
    from higgsml.inference import assessment
    from higgsml.inference.attribution import FAMILY
    p = load_protocol().to_dict()
    c,cs = population('calibration');t,ts = population('template');m,ms = population('assessment')
    for frame,scores in ((c,cs),(t,ts),(m,ms)):
        frame['event_id'] = frame.event_group_id
        frame['_score'] = scores
    record = select()
    key = record['candidate_key']
    bundle = dict(model={},model_id='model',mapping_id='raw:model',key=key,seed=42,
                  candidate_id='M3',transform='raw',mapping=None,thresholds=record)
    grid = dict(status='valid',family_id=FAMILY,mass_edges=[105,140],templates={key:{}},
                analysis_contract_digest=record['analysis_contract_digest'])
    monkeypatch.setattr(assessment,'_scores',lambda b,f:f._score.to_numpy())
    def procedure(calibration,template,mother,**kwargs):
        assert template is t and mother is m
        draw = calibration.copy()
        # Change only C. Its group counts and weights must enter selection.
        draw['bootstrap_multiplicity'] = np.where(draw._score < .5,2,1)
        draw.physical_weight *= draw.bootstrap_multiplicity
        draw.yield_weight *= draw.bootstrap_multiplicity
        mapping = kwargs['fit_mapping'](draw)
        chosen = mapping['bundles'][key]['thresholds']
        assert chosen['draw_identity']['stage'] == 't2_outer'
        assert chosen['role_bindings']['template'] == record['role_bindings']['template']
        assert chosen['role_bindings']['calibration'] != record['role_bindings']['calibration']
        mapped_t = kwargs['apply_mapping'](mapping,template)
        mapped_m = kwargs['apply_mapping'](mapping,mother)
        cut = chosen['selected_threshold']
        assert np.array_equal(mapped_t._t2_category_0, ts >= cut)
        assert np.array_equal(mapped_m._t2_category_0, ms >= cut)
        return {'status':'synthetic_callbacks_checked'}
    monkeypatch.setattr(assessment,'run_t2_procedure',procedure)
    assert assessment.run_assessment_t2(grid,{key:bundle},c,t,m,p,layer='T1',t1_validation={},
        mu=1,seed=42,prepared_id='prepared',freeze_id='freeze')['status']=='synthetic_callbacks_checked'


def test_no_feasible_t2_outer_preserves_all_inner_budget():
    from higgsml.errors import ResearchStateError
    from higgsml.inference.likelihood import run_t2_procedure
    def fail(frame):
        error = ResearchStateError('no cut',status='no_feasible_joint_threshold')
        error.threshold_record = {'status':error.status,'candidates':list(range(19))}
        raise error
    def forbidden(*args):
        pytest.fail('failed selection must not generate inner toys')
    result = run_t2_procedure(population('calibration')[0],population('template')[0],population('assessment')[0],
        fit_mapping=fail,apply_mapping=forbidden,evaluate=forbidden,preflight=forbidden,
        outer_replicas=20,inner_toys=100,seed=42,model_id='model',mother_id='mother',record_mappings=True,
        inner_seed_factory=lambda i:i+1)
    assert result['status']=='no_feasible_joint_threshold'
    assert result['generated_physical_toys']==0
    assert len(result['replicas'])==20
    assert all(r['planned_inner_toys']==100 and len(r['threshold_record']['candidates'])==19 for r in result['replicas'])


def test_new_nominal_artifact_rebuild_and_cross_method_rejection(tmp_path,monkeypatch):
    from higgsml.artifacts import ResearchRun, read_run
    from higgsml.inference import marginal_workflow as workflow, attribution_workflow as legacy, assessment
    from higgsml.inference.attribution import SEEDS, SUBSETS, candidate_key
    from higgsml.modeling.discriminants import digest
    from higgsml.modeling.representations import representation_features
    from higgsml.modeling import joint_support
    p = load_protocol().to_dict()
    root = tmp_path/'runs';root.mkdir()
    def artifact(name,stage,files):
        with ResearchRun(root/name,allowed_root=root,stage=stage,dataset=p['dataset'],protocol=p) as run:
            for filename,value in files.items():
                run.write_json(filename,value)
        return read_run(root/name,dataset=p['dataset'],protocol=p)
    t1 = dict(status='validated',correlation='independent_process_bins',auxiliary='poisson_tau_gamma',
              modifier='shapesys',pyhf_version='0.7.6',evidence_id='synthetic-only')
    prepared = artifact('prepare','prepare',{'events.jsonl':{}})
    prepared.manifest['population_id']='synthetic-population'
    original = artifact('source-register','attribution-register',{'t1-validation.json':t1})
    overlay = dict(source_root=str(root/'models'),prepared_artifact_id=prepared.manifest['artifact_id'],
                   population_id='synthetic-population',registration_id='synthetic-registration',qualification={})
    monkeypatch.setattr(legacy,'load_registration',lambda *a,**k:(original,overlay,prepared))
    c,cs=population('calibration');t,ts=population('template');v,vs=population('validation')
    c['_score']=cs;t['_score']=ts;v['_score']=vs
    frame=pd.concat([c,t,v],ignore_index=True)
    monkeypatch.setattr(legacy,'load_research_data',lambda *a,**k:frame.copy())
    def predict(model,frame):
        return np.full(len(frame),.5) if model['candidate']=='M0off' else frame._score.to_numpy()
    monkeypatch.setattr(joint_support,'predict_discriminant',predict)
    monkeypatch.setattr(assessment,'predict_discriminant',predict)
    bundles={}
    for seed in SEEDS:
        for subset in SUBSETS[1:]:
            key=candidate_key(seed,subset)
            model=dict(candidate='M3',seed=seed,groups=list(subset),mass_input='off',
                ordered_inputs=list(representation_features('engineered19',groups=list(subset),mass_input='off')),
                protocol_id=digest(p),dataset=p['dataset'])
            model['model_id']=digest(model)
            mapping='raw:'+model['model_id']
            bundles[key]=dict(model=model,model_id=model['model_id'],mapping_id=mapping,mapping=None,
                candidate_id='M3',seed=seed,key=key,transform='raw',status='calibrated',
                thresholds=fit_thresholds(c,cs,p,model_id=model['model_id'],mapping_id=mapping))
    monkeypatch.setattr(legacy,'audit_sources',lambda *a,**k:([],deepcopy(bundles),[],{key:p for key in bundles}))
    workflow.register(overlay['source_root'],prepared.path,p,root/'register',root,
        source_registration=original.path,threshold_method='joint-support-v1')
    registration=workflow.load_registration(root/'register',p)[1]
    assert registration['registration_status']=='exploratory_posthoc'
    # A completed joint source from interrupted publication may be reused only
    # after checking the same method/input identities; it is never overwritten.
    bindings=dict(analysis_contract_digest=registration['analysis_contract_digest'],
        prepared_artifact_id=prepared.manifest['artifact_id'],population_id='synthetic-population',
        source_artifact_id=original.manifest['artifact_id'])
    legacy.nominal(original.path,p,root/'source-nominal',root,joint_bindings=bindings)
    source_id=read_run(root/'source-nominal',dataset=p['dataset'],protocol=p).manifest['artifact_id']
    workflow.nominal(root/'register',p,root/'nominal',root)
    assert read_run(root/'source-nominal',dataset=p['dataset'],protocol=p).manifest['artifact_id']==source_id
    loaded=workflow.load_nominal(root/'register',root/'nominal',p)
    grid,built=loaded[-2:]
    assert grid['mass_edges']==[105,140]
    assert grid['analysis_contract_digest']==registration['analysis_contract_digest']
    assert len(built)==80
    assert all(b['thresholds'].get('selected_quantile_numerator')==10 for b in built.values() if b['candidate_id']!='M0off')
    assert loaded[4].read_json('empty-likelihood-equivalence.json')['status']=='valid'
    assert all(b['thresholds']['threshold_id']!=bundles[key]['thresholds']['threshold_id'] for key,b in built.items() if key in bundles)
    workflow.report(root/'register',root/'nominal',p,root/'report',root)
    report=read_run(root/'report',dataset=p['dataset'],protocol=p).read_json('report.json')
    assert report['execution_status']=='incomplete'
    assert report['selection_aware_coverage']=='unvalidated' and not report['primary_claim_eligible']
    assert report['nominal_selection']['selected_quantile_counts']['10']==75
    assert len(report['evaluation_units'])==36
    with pytest.raises(ResearchError,match='fresh rebuilt'):
        workflow.nominal(root/'register',p,root/'other-nominal',root,source_nominal=root/'source-nominal')
    workflow.register(overlay['source_root'],prepared.path,p,root/'median-register',root,
        source_registration=original.path)
    with pytest.raises(ResearchError,match='threshold method'):
        workflow.nominal(root/'median-register',p,root/'bad-median-nominal',root)
    assert not (root/'bad-median-nominal').exists()
    with pytest.raises(ResearchError,match='threshold method'):
        workflow.load_nominal(root/'median-register',root/'nominal',p)
