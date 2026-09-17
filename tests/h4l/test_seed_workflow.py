"""Synthetic workflow tests: access barriers, acyclic freeze, durable failures."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from higgsml.artifacts import ResearchRun, read_run, digest_json
from higgsml.data import assign_roles, write_research_data
from higgsml.errors import ResearchError, ResearchStateError
from higgsml.inference import seed_workflow as w
from higgsml.inference.attribution import SUBSETS, SEEDS, FAMILY, candidate_key
from higgsml.modeling.representations import ENGINEERED19
from higgsml.protocol import load_protocol


def _run(root, name, protocol, files, stage=None):
    with ResearchRun(root/name, allowed_root=root, stage=stage or 'fixture',
                     dataset=protocol['dataset'], protocol=protocol) as run:
        for filename,value in files.items(): run.write_json(filename,value)
    return read_run(root/name,dataset=protocol['dataset'],protocol=protocol)


def _fixture(tmp_path,monkeypatch,negative=False):
    protocol=load_protocol().to_dict()
    root=tmp_path/'runs'; root.mkdir()
    prepared=root/'prepare-root'/'prepare'
    prepared.parent.mkdir()
    rows=[]
    for i in range(1000):
        row=dict.fromkeys(ENGINEERED19,1.)
        row.update(event_id=f's:{i}',source_row_id=f's:{i}',event_group_id=f'synthetic:{i}',
                   split='development',dataset=protocol['dataset'],label=i%2,physical_weight=1.,m4l=125.,y4l=0.)
        rows.append(row)
    frame=assign_roles(pd.DataFrame(rows),protocol)
    frame.attrs['source_kind']='synthetic'
    if negative:
        indices=frame.index[(frame.role=='template') & (frame.label==0)]
        frame.loc[indices,'physical_weight']=-1.
        frame.loc[indices,'yield_weight']=-1./frame.loc[indices,'sampling_probability']
    with ResearchRun(prepared,allowed_root=root,stage='prepare',dataset=protocol['dataset'],protocol=protocol) as run:
        path=run.path/'events.jsonl'
        write_research_data(frame,path,protocol)
        lines=path.read_text().splitlines()
        for i in range(1,len(lines)):
            identity,payload=lines[i].split('\t',1)
            if json.loads(identity)['role']=='assessment': lines[i]=identity+'\tPOISON NEVER DECODE'
        path.write_text('\n'.join(lines)+'\n')
        run.register_file('events.jsonl')
    prep=read_run(prepared,dataset=protocol['dataset'],protocol=protocol)
    # Population metadata is supplied by actual prepare; the synthetic fixture binds one identity.
    prep.manifest['population_id']='synthetic-population'
    bundles={k:{'model_id':'model:'+k,'key':k} for k in w.candidate_keys()}
    template=frame.loc[frame.role=='template']
    samples=[{'name':str(label),'yield':[float(template.loc[template.label==label,'yield_weight'].sum())],
              'is_signal':bool(label)} for label in (0,1)]
    grid={'mass_edges':[105.,140.],'templates':{k:{'categories':[1], 'samples':samples} for k in bundles}}
    registered=_run(root,'register',protocol,{'registration.json':{}},'attribution-v2-register')
    nominal=_run(root,'nominal',protocol,{},'attribution-v2-nominal')
    source=_run(root,'source-nominal',protocol,{'t1-validation.json':{}},'attribution-nominal')
    values=(registered,{'qualification':{'independent_reference':'pending'},'population_id':'synthetic-population'},
            prep,nominal,source,grid,bundles)
    monkeypatch.setattr(w,'load_nominal',lambda *a,**k:values)
    import higgsml.inference.assessment as assessment
    monkeypatch.setattr(assessment,'categorize_bundle',lambda b,f:f.assign(category=1))
    return root,protocol,values


def _gated(root,p):
    w.support_check(root/'register',root/'nominal',p,root/'support-j0',root)
    w.support_check(root/'register',root/'nominal',p,root/'support-j1',root,gate='J1',j0_path=root/'support-j0')
    w.specification(root/'register',root/'nominal',p,root/'evaluation-spec',root,
                    j0_path=root/'support-j0',j1_path=root/'support-j1')
    w.freeze(root/'register',root/'nominal',p,root/'freeze',root,specification_path=root/'evaluation-spec')


def _summary():
    return w.summarize([{'candidate_key':candidate_key(seed,subset),'seed':seed,'subset':subset,'family_id':FAMILY,
        'cohort_id':'synthetic','status':'valid','width68':10-len(subset)+(seed-42)*len(subset)*.01,
        'auc':.5+len(subset)*.01,'auc_role':'validation','auc_measure':'absolute_physical_weight',
        'model_id':candidate_key(seed,subset),'auc_model_id':candidate_key(seed,subset)}
        for seed in SEEDS for subset in SUBSETS])


def _planned(root,p,monkeypatch):
    _gated(root,p)
    summary=_summary()
    monkeypatch.setattr(w.legacy,'asimov_records',lambda *a,**k:(summary['records'],{}))
    w.asimov(root/'register',root/'nominal',root/'freeze',p,root/'asimov',root)
    w.evaluation_plan(root/'register',root/'nominal',root/'freeze',root/'asimov',p,root/'evaluation-plan',root)
    return root/'evaluation-plan'/'evaluation-plan.json'


def test_poisoned_assessment_j0_j1_acyclic_spec_and_freeze(tmp_path,monkeypatch):
    root,p,values=_fixture(tmp_path,monkeypatch)
    _gated(root,p)
    for name in ('support-j0','support-j1'):
        gate=w.read_json(root/name/'joint-support-summary.json')
        assert gate['status']=='passed' and gate['assessment_payload_read'] is False
    spec=w.read_json(root/'evaluation-spec'/'evaluation-spec.json')
    assert len(spec['matrix'])==36
    assert not (root/'.h4l-mass-off-v2-claims').exists()
    for key in ('freeze_artifact_id','evaluation_plan_id','asimov_artifact_id'):
        modified={**spec,key:'cycle'}; modified.pop('specification_id')
        with pytest.raises(ResearchError):
            w.validate_specification(w._seal(modified,'specification_id'),p)


def test_gate_failure_publishes_report_without_freeze(tmp_path,monkeypatch):
    root,p,_=_fixture(tmp_path,monkeypatch,negative=True)
    w.support_check(root/'register',root/'nominal',p,root/'support-j0',root)
    with pytest.raises(ResearchStateError,match='J0 failed'):
        w.support_check(root/'register',root/'nominal',p,root/'support-j1',root,gate='J1',j0_path=root/'support-j0')
    w.report(root/'register',root/'nominal',p,root/'report',root,j0_path=root/'support-j0')
    result=w.read_json(root/'report'/'report.json')
    assert result['aggregate_status']=='incomplete' and result['nominal_asimov'] is None
    assert len(result['evaluation_units'])==36 and not (root/'freeze').exists()


def test_terminal_failure_other_seeds_continue_and_no_replay(tmp_path,monkeypatch):
    root,p,values=_fixture(tmp_path,monkeypatch)
    plan_path=_planned(root,p,monkeypatch)
    import higgsml.inference.seed_evaluation as evaluator
    from higgsml.inference.seed_evaluation import _failure_envelope
    calls=[]
    def scientific_failure(*a,**kw):
        calls.append(kw['block'].seed)
        return _failure_envelope(stage='model-self',block=kw['block'],planned=500,
            status='insufficient_statistics',reason='synthetic negative support',stream={})
    monkeypatch.setattr(evaluator,'evaluate_seed_block',scientific_failure)
    outputs=[]
    for seed in (42,43):
        output=root/f'model-self-mu1-seed{seed}'; outputs.append(output)
        kwargs=dict(stage='model-self',mu=1,training_seed=seed,evaluation_plan_path=plan_path,result_path=root/'asimov')
        w.evaluate(root/'register',root/'nominal',root/'freeze',p,output,root,**kwargs)
        w.evaluate(root/'register',root/'nominal',root/'freeze',p,output,root,**kwargs)
    assert calls==[42,43]
    assert w.source_history(values[2])==[]  # Template claims are not assessment access.
    w.report(root/'register',root/'nominal',p,root/'report',root,freeze_path=root/'freeze',
             result_path=root/'asimov',evaluation_plan_path=plan_path,evaluation_paths=outputs)
    report=w.read_json(root/'report'/'report.json')
    assert report['nominal_asimov']['status']=='valid'
    assert len(report['nominal_asimov']['pairwise_comparisons'])==105
    assert report['seed_layers']['model-self-mu1']['status']=='incomplete_seed_vector'
    damaged=outputs[0]/'seed-evaluation.json'; damaged.write_text('{}')
    with pytest.raises(ResearchStateError,match='recomputation prohibited'):
        w.evaluate(root/'register',root/'nominal',root/'freeze',p,outputs[0],root,
            stage='model-self',mu=1,training_seed=42,evaluation_plan_path=plan_path,result_path=root/'asimov')
    assert damaged.read_text()=='{}' and calls==[42,43]


def test_cli_plan_only_does_not_read_payload_or_claim(tmp_path,monkeypatch,capsys):
    from higgsml.cli_attribution import main
    monkeypatch.setattr(w,'_frame',lambda *a,**k:pytest.fail('numeric decode'))
    assert main(['support-check','--evaluation-version','v2','--plan-only','--run-dir',str(tmp_path/'unused')])==0
    value=json.loads(capsys.readouterr().out)
    assert value['unit_count_including_report']==37 and value['claims_consumed'] is False
    assert not (tmp_path/'unused').exists()


def test_old_artifact_rejected_and_plan_semantics_changed(tmp_path,monkeypatch):
    root,p,_=_fixture(tmp_path,monkeypatch)
    old=_run(root,'old-freeze',p,{},'attribution-freeze')
    with pytest.raises(ResearchError,match='stage'):
        w.load_frozen(root/'register',root/'nominal',old.path,p)
    plan_path=_planned(root,p,monkeypatch)
    plan=w.read_json(plan_path)
    plan['matrix']=plan['matrix'][:-1]; plan.pop('evaluation_plan_id')
    with pytest.raises(ResearchError,match='plan'):
        w.validate_plan(w._seal(plan,'evaluation_plan_id'),p)


def test_history_cannot_be_cleared_by_new_output(tmp_path,monkeypatch):
    root,p,values=_fixture(tmp_path,monkeypatch)
    prepared=values[2]
    ledger=root/'.research-claims'; ledger.mkdir()
    (ledger/'history.json').write_text(json.dumps({'population_id':'synthetic-population',
        'freeze_artifact_id':'historical-freeze','prepared_artifact_id':w._id(prepared)}))
    assert len(w.source_history(prepared))==1
    with pytest.raises(ResearchStateError,match='eligible source'):
        w._access(prepared,None,{}, {},p,None)
    assert not (root/'new-v2-output').exists()
    original=root/'review.json'; original.write_text(json.dumps({'independent':True}))
    spec={'specification_id':'1'*64,'blocks':[b.as_dict() for b in w.canonical_seed_blocks()]}; plan={'evaluation_plan_id':'2'*64}
    receipt=w._seal({'schema_version':'h4l-off-assessment-access-v2','specification_id':spec['specification_id'],
        'evaluation_plan_id':plan['evaluation_plan_id'],'blocks':spec['blocks'],'review_mode':'independent_validated','independent':True,
        'source_history':w.source_history(prepared),
        'source_review':{'path':str(original),'sha256':w.sha256_file(original)}},'access_id')
    access=root/'v2-review.json'; access.write_text(json.dumps(receipt))
    monkeypatch.setattr(w.legacy,'_validate_independent_access_review',lambda *a:None)
    with pytest.raises(ResearchStateError,match='historically opened'):
        w._access(prepared,SimpleNamespace(manifest={'artifact_id':'new-freeze'}),spec,plan,p,access)
    assert not (root/'.h4l-mass-off-v2-claims').exists()


def test_metadata_manifest_upstream_mismatch_without_payload(tmp_path,monkeypatch):
    root,p,_=_fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(w,'_frame',lambda *a,**k:pytest.fail('metadata decoded payload'))
    with pytest.raises(ResearchError,match='upstream mismatch'):
        w.metadata_plan(p,registration_path=root/'register',nominal_path=root/'nominal')
    value=w.metadata_plan(p,registration_path=root/'missing')
    assert value['status']=='unresolved' and value['unresolved'][0]['reason']=='manifest_missing'


def test_compatibility_audit_binds_weight_grid_and_model_semantics(tmp_path,monkeypatch):
    root,p,values=_fixture(tmp_path,monkeypatch)
    nominal,grid,bundles,prepared=values[4],values[5],values[6],values[2]
    original=w._semantics(nominal,grid,bundles,prepared,p)
    changed=deepcopy(p); changed['roles']['template']=.3
    assert w._semantics(nominal,grid,bundles,prepared,changed)!=original
    changed_grid=deepcopy(grid); changed_grid['mass_edges'][0]=104.
    assert w._semantics(nominal,changed_grid,bundles,prepared,p)!=original
    changed_bundle=deepcopy(bundles); changed_bundle[next(iter(bundles))]['model_id']='changed'
    assert w._semantics(nominal,grid,changed_bundle,prepared,p)!=original


def test_workflow_t2_passes_shared_group_bound_outer_plan(tmp_path,monkeypatch):
    root,p,values=_fixture(tmp_path,monkeypatch)
    plan_path=_planned(root,p,monkeypatch)
    import higgsml.inference.seed_evaluation as evaluator
    saved_frame=w._frame
    monkeypatch.setattr(w,'_frame',lambda prepared,protocol,**kw:saved_frame(prepared,protocol))
    monkeypatch.setattr(w,'_access',lambda *a,**kw:{'synthetic_access_test_only':True})
    outer_plans=[]
    def t2(*a,**kw):
        outer=kw['outer_multiplicities']; outer_plans.append(outer)
        assert len(outer['multiplicities'])==20 and outer['groups']
        assert outer['multiplicity_plan_digest']==digest_json(outer['multiplicities'])
        terminal=evaluator._failure_envelope(stage='t2',block=kw['block'],planned=2000,
            status='insufficient_statistics',reason='synthetic screening failure',stream={})
        terminal.update(planned_outer=20,planned_inner_per_outer=100,outer_records=[])
        return terminal
    monkeypatch.setattr(evaluator,'evaluate_seed_t2',t2)
    for seed in (42,43):
        w.evaluate(root/'register',root/'nominal',root/'freeze',p,root/f't2-mu1-seed{seed}',root,
            stage='t2',mu=1,training_seed=seed,evaluation_plan_path=plan_path,result_path=root/'asimov')
    assert outer_plans[0]==outer_plans[1]


def test_script_matrix_and_immutable_report_resume(tmp_path,monkeypatch,capsys):
    import importlib.util
    script=Path(__file__).resolve().parents[2]/'scripts'/'h4l_evaluate.py'
    spec=importlib.util.spec_from_file_location('evaluate_v2_test',script)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    monkeypatch.setattr(module,'RUNS_ROOT',tmp_path)
    monkeypatch.setattr(w,'validate_plan',lambda *a:None)
    commands=[]; reports=[]
    monkeypatch.setattr(module,'_invoke_with_progress',lambda command,**kw:commands.append(command))
    def report(*args,**kw):
        target=args[3]; target.mkdir(); reports.append(target)
        assert len(kw['evaluation_paths'])==36
    monkeypatch.setattr(w,'report',report)
    monkeypatch.setattr(w,'_load',lambda *a:SimpleNamespace(read_json=lambda name:{'evaluation_plan':{}}))
    args=module._parser().parse_args(['--evaluation-version','v2','--plan',str(tmp_path/'plan'),
        '--registration-run',str(tmp_path/'register'),'--prepared-run',str(tmp_path/'prepared'),
        '--template-run',str(tmp_path/'nominal'),'--freeze-run',str(tmp_path/'freeze'),
        '--result-run',str(tmp_path/'asimov'),'--output-root',str(tmp_path/'evaluation'),'--no-progress'])
    module._run_mass_off_v2(args,{}, {})
    args.continue_run=True
    module._run_mass_off_v2(args,{}, {})
    evidence=tmp_path/'evaluation'/'assessment-mu1-seed42'; evidence.mkdir()
    (evidence/'seed-evaluation.json').write_text('{"new":"evidence"}')
    module._run_mass_off_v2(args,{}, {})
    module._run_mass_off_v2(args,{}, {})
    assert len(commands)==144 and len(reports)==3
    assert reports[0].name=='report' and reports[1].name.startswith('report-resume-')
    assert reports[1]!=reports[2]
    assert str(reports[2]/'report.md') in capsys.readouterr().out


def test_descriptive_diagnostics_require_five_valid_seeds_and_keep_t2_outer_units():
    entries={w.unit_name(u):{**u,'status':'not_run','value':None} for u in w.matrix()}
    for seed in range(42,47):
        key=candidate_key(seed,'A')
        cov={'status':'valid','conditional_coverage':.6+(seed-42)*.05,
             'success_and_coverage_fraction':.6+(seed-42)*.05,'failure_rate':0.}
        entries[f'assessment-mu1-seed{seed}'].update(status='valid',value={'candidate_results':[
            {'candidate_id':key,'result':{'coverage':{'0.68':cov}}}]})
        entries[f't2-mu1-seed{seed}'].update(status='valid',value={'outer_records':[
            {'replica':outer,'result':{'candidates':{key:{'coverage':{'0.68':cov}}}}} for outer in range(20)]})
    rows,aggregates=w.descriptive_seed_diagnostics(entries)
    selected=lambda stage:[r for r in aggregates if r['stage']==stage and r['mu']==1 and r['subset']=='A'
                           and r['confidence_level']==.68 and r['metric']=='conditional_coverage'][0]
    assert selected('assessment')['median']==pytest.approx(.7)
    assert selected('t2')['median']==pytest.approx(.7)
    assert selected('t2')['experimental_unit']=='20_outer_calibration_replicas'
    t2=next(r for r in rows if r['stage']=='t2' and r['subset']=='A' and r['confidence_level']==.68)
    assert len(t2['outer_records'])==20
    entries['assessment-mu1-seed46']['status']='inference_incomplete'
    # An unrelated coalition's failure cannot erase this coalition's complete diagnostic.
    _,still_complete=w.descriptive_seed_diagnostics(entries)
    assert next(r for r in still_complete if r['stage']=='assessment' and r['mu']==1 and r['subset']=='A'
                and r['confidence_level']==.68 and r['metric']=='conditional_coverage')['median']==pytest.approx(.7)
    entries['assessment-mu1-seed46']['value']['candidate_results'][0]['result']['coverage']['0.68']['status']='coverage_incomplete'
    entries['t2-mu1-seed46']['value']['outer_records'].pop()
    rows,aggregates=w.descriptive_seed_diagnostics(entries)
    assert selected('assessment')['median'] is None and selected('assessment')['per_seed'][-1]['value']==pytest.approx(.8)
    assert selected('t2')['median'] is None


def test_failed_gate_continuation_reuses_only_bound_report(tmp_path,monkeypatch,capsys):
    import importlib.util
    import higgsml.artifacts as artifacts
    script=Path(__file__).resolve().parents[2]/'scripts'/'h4l_off_run.py'
    spec=importlib.util.spec_from_file_location('off_v2_gate_test',script)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    monkeypatch.setattr(module,'RUNS_ROOT',tmp_path)
    root=tmp_path/'h4l-off-fixture'
    for name in ('register','nominal','support-j0','gate-failure-report'): (root/name).mkdir(parents=True)
    gate={'gate':'J0','status':'failed'}
    (root/'support-j0'/'joint-support-summary.json').write_text(json.dumps(gate))
    monkeypatch.setattr(artifacts,'read_run',lambda *a,**k:None)
    monkeypatch.setattr(module,'_invoke',lambda *a,**k:pytest.fail('already published stage rerun'))
    stored={'support':[gate],'evaluation_plan':None}
    monkeypatch.setattr(w,'_load',lambda *a:SimpleNamespace(read_json=lambda name:stored))
    monkeypatch.setattr(w,'load_nominal',lambda *a:(object(),None,None,object()))
    checked=[]
    monkeypatch.setattr(w,'_validate_gate',lambda *a:checked.append(a[0]))
    monkeypatch.setattr(w,'report',lambda *a,**k:pytest.fail('existing gate report overwritten'))
    args=module._parser().parse_args(['--evaluation-version','v2','--source-run-name','fixture',
                                     '--run-name','fixture','--stage-b','--continue'])
    module._run_v2(args); module._run_v2(args)
    assert checked==[gate,gate] and 'gate-failure-report' in capsys.readouterr().out
    stored['support']=[]
    with pytest.raises(module.WorkflowError,match='bind'):
        module._run_v2(args)
