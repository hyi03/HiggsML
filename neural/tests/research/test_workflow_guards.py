import json
import pandas as pd
import pytest

from src.cli.research import build_parser
from src.research.artifacts import ResearchRun, read_run, digest_json
from src.research.errors import ResearchError, ResearchStateError
from src.research.protocol import load_protocol, DEFAULT_PATH
from src.research.workflow import execute, _claim_assessment, _require_unopened, _p0_audit, _require_g0, _population_id
from src.research.discriminants import train_discriminant


def invoke(tmp_path, command, name, *extra):
    args=build_parser().parse_args([command,'--dataset','atlas2020_4lep','--protocol',str(DEFAULT_PATH),
        '--run-dir',str(tmp_path/name),*map(str,extra)])
    execute(args,allowed_root=tmp_path)
    return read_run(tmp_path/name,dataset='atlas2020_4lep',protocol=load_protocol().to_dict(),allow_terminal=True)


def test_durable_claim_refuses_redesign_and_requires_explicit_same_freeze_repeat(tmp_path):
    p=load_protocol().to_dict()
    _claim_assessment(tmp_path,'population',p,'frozen')
    with pytest.raises(ResearchStateError): _require_unopened(tmp_path,'population',p)
    with pytest.raises(ResearchStateError): _claim_assessment(tmp_path,'population',p,'frozen')
    with pytest.raises(ResearchStateError): _claim_assessment(tmp_path,'population',p,'another',repeat=True)
    _claim_assessment(tmp_path,'population',p,'frozen',repeat=True)


def test_controlled_mc_requires_bound_p0_synthetic_does_not(tmp_path):
    p=load_protocol().to_dict(); frame=pd.DataFrame(); frame.attrs.update(source_kind='controlled_mc',source_evidence={'source':'registered'})
    audit={'status':'passed','physics_sources_validated':False}
    checked,evidence=_p0_audit(frame,p,audit,None)
    assert not checked['physics_sources_validated']
    with ResearchRun(tmp_path/'prepare',allowed_root=tmp_path,stage='prepare',dataset=p['dataset'],protocol=p) as run:
        run.manifest['source_kind']='controlled_mc'; run.write_json('audit.json',checked)
    prepared=read_run(tmp_path/'prepare',dataset=p['dataset'],protocol=p)
    with pytest.raises(ResearchStateError,match='P0'): _require_g0(prepared)
    validation={'status':'validated','dataset':p['dataset'],'protocol_sha256':digest_json(p),
        'source_evidence_sha256':digest_json(frame.attrs['source_evidence']),'evidence_id':'independent-fixture',
        'independent_reference':'synthetic-test-only','physical_definitions':{k:'bound-ref' for k in ('processes','units','four_vectors','pairing','weights','selection')}}
    path=tmp_path/'p0.json'; path.write_text(json.dumps(validation))
    assert _p0_audit(frame,p,audit,path)[0]['physics_sources_validated']
    validation['source_evidence_sha256']='wrong'; path.write_text(json.dumps(validation))
    with pytest.raises(ResearchError): _p0_audit(frame,p,audit,path)
    frame.attrs['source_kind']='synthetic'
    assert _p0_audit(frame,p,audit,None)[0]['scope']=='synthetic_software_validation'


def test_report_keeps_terminal_context_and_records_multiple_scopes(tmp_path):
    p=load_protocol().to_dict()
    with ResearchRun(tmp_path/'failed',allowed_root=tmp_path,stage='train',dataset=p['dataset'],protocol=p,
        context={'prepared_artifact_id':'source','candidate_key':'M6:42:lambda=0.1'}) as run:
        raise ResearchStateError('synthetic failure',status='training_failed')
    for index,mu in enumerate((0.,1.)):
        with ResearchRun(tmp_path/f'infer{index}',allowed_root=tmp_path,stage='infer',dataset=p['dataset'],protocol=p,
            context={'prepared_artifact_id':'source','inference_scope':{'mu':mu,'layer':'T0','expectation_kind':'model_self'}}) as run:
            run.write_json('inference.json',{'M0':{'status':'valid'}})
    report=invoke(tmp_path,'report','report','--result-run',tmp_path/'failed','--result-run',tmp_path/'infer0','--result-run',tmp_path/'infer1').read_json('report.json')
    assert report['candidate_statuses']['M6:42:lambda=0.1']=='training_failed'
    assert len(report['results'])==2 and len(report['terminal_runs'])==1
    with pytest.raises(ResearchError,match='Duplicate'):
        invoke(tmp_path,'report','duplicate','--result-run',tmp_path/'infer0','--result-run',tmp_path/'infer0')


def test_report_publishes_complete_feature_combination_comparison(tmp_path):
    import itertools
    p=load_protocol().to_dict(); results={}
    for size in range(5):
        for groups in itertools.combinations('ABCD',size):
            subset=''.join(groups); key='M0c:42' if not subset else f'M3:42:groups={subset}'
            candidate='M0c' if not subset else 'M3'; width=10.-.1*sum('ABCD'.index(g)+1 for g in groups)
            results[key]={'status':'valid','seed':42,'asimov':{'candidate_id':candidate,'layer':'T1',
                'expectation_kind':'model_self_asimov','results':[{'mu':1.,'intervals':[{'status':'valid','width':width}]}]}}
    scope={'mu':1.,'layer':'T1','expectation_kind':'model_self','procedure':'fixed','seed':42,
           'comparison_cohort_id':'synthetic-common-cohort'}
    with ResearchRun(tmp_path/'infer-groups',allowed_root=tmp_path,stage='infer',dataset=p['dataset'],protocol=p,
        context={'prepared_artifact_id':'source','inference_scope':scope}) as run:
        run.write_json('inference.json',results)
    report=invoke(tmp_path,'report','group-report','--result-run',tmp_path/'infer-groups').read_json('report.json')
    comparison=report['feature_combination_comparisons'][0]
    assert comparison['status']=='valid' and len(comparison['nonempty_combinations'])==15
    assert comparison['source_artifact_id']


def test_one_common_inference_publishes_five_seed_combinations_and_primary(tmp_path):
    import itertools
    p=load_protocol().to_dict(); results={}
    for seed in range(42,47):
        for size in range(5):
            for groups in itertools.combinations('ABCD',size):
                subset=''.join(groups); key=f'M0c:{seed}' if not subset else f'M3:{seed}:groups={subset}'
                candidate='M0c' if not subset else 'M3'; width=10.-.1*sum('ABCD'.index(g)+1 for g in groups)
                results[key]={'status':'valid','seed':seed,'asimov':{'candidate_id':candidate,'layer':'T1',
                    'expectation_kind':'model_self_asimov','results':[{'mu':1.,'intervals':[{'status':'valid','width':width}]}]}}
        for candidate,width in [('M4',2.),('M5',1.8)]:
            results[f'{candidate}:{seed}']={'status':'valid','seed':seed,'asimov':{
                'candidate_id':candidate,'layer':'T1','expectation_kind':'model_self_asimov',
                'results':[{'mu':1.,'intervals':[{'status':'valid','width':width}]}]}}
    scope={'mu':1.,'layer':'T1','expectation_kind':'model_self','procedure':'fixed','seed':42,
           'comparison_cohort_id':'one-common-cohort'}
    with ResearchRun(tmp_path/'infer-all',allowed_root=tmp_path,stage='infer',dataset=p['dataset'],protocol=p,
        context={'prepared_artifact_id':'source','inference_scope':scope}) as run:
        run.write_json('inference.json',results)
    report=invoke(tmp_path,'report','all-report','--result-run',tmp_path/'infer-all').read_json('report.json')
    assert [item['seed'] for item in report['feature_combination_comparisons']]==list(range(42,47))
    assert report['feature_combination_summary']['status']=='valid'
    assert report['primary_comparison']['status']=='valid'
    assert report['primary_comparison']['median_relative_improvement']==pytest.approx(.1)
    assert report['primary_comparison_cohort_id']=='one-common-cohort'


def test_report_rejects_mixed_populations_and_input_errors_keep_context(tmp_path):
    p=load_protocol().to_dict()
    for name in ('a','b'):
        with pytest.raises(ResearchError):
            with ResearchRun(tmp_path/name,allowed_root=tmp_path,stage='train',dataset=p['dataset'],protocol=p,
                context={'prepared_artifact_id':name,'candidate_key':'M3:42'}):
                raise ResearchError('invalid input')
    failed=read_run(tmp_path/'a',dataset=p['dataset'],protocol=p,allow_terminal=True)
    assert failed.manifest['context']['candidate_key']=='M3:42'
    with pytest.raises(ResearchError,match='populations'):
        invoke(tmp_path,'report','mixed','--result-run',tmp_path/'a','--result-run',tmp_path/'b')


def test_m6_rejects_unregistered_lambda_before_frame_access():
    for strength in (0.,.3,1.):
        with pytest.raises(ResearchError,match='registered'):
            train_discriminant(pd.DataFrame(),load_protocol(),candidate='M6',target_lambda=strength)


def test_claim_precedes_payload_decode_and_failed_opening_blocks_training(tmp_path,monkeypatch):
    p=load_protocol().to_dict()
    with ResearchRun(tmp_path/'prepared',allowed_root=tmp_path,stage='prepare',dataset=p['dataset'],protocol=p) as run:
        run.manifest['source_kind']='synthetic'
        run.write_json('audit.json',{'status':'passed','physics_sources_validated':False})
        (run.path/'events.jsonl').write_text('payload intentionally unreadable')
        run.register_file('events.jsonl')
    prepared=read_run(tmp_path/'prepared',dataset=p['dataset'],protocol=p)
    with ResearchRun(tmp_path/'templates',allowed_root=tmp_path,stage='templates',dataset=p['dataset'],protocol=p,upstreams=[prepared]) as run:
        run.write_json('templates.json',{'status':'valid','templates':{},'mass_edges':[105,140]})
        run.write_json('t1-validation.json',None)
        run.write_json('calibrations.json',{})
    templates=read_run(tmp_path/'templates',dataset=p['dataset'],protocol=p)
    with ResearchRun(tmp_path/'freeze',allowed_root=tmp_path,stage='freeze',dataset=p['dataset'],protocol=p,upstreams=[prepared,templates]) as run:
        run.write_json('freeze.json',{'status':'frozen','template_artifact_ids':[templates.manifest['artifact_id']]})
    def decode(*args,**kwargs):
        with pytest.raises(ResearchStateError): _require_unopened(tmp_path,prepared.manifest['artifact_id'],p)
        raise ResearchError('injected decode failure')
    monkeypatch.setattr('src.research.workflow.load_research_data',decode)
    with pytest.raises(ResearchError,match='decode failure'):
        invoke(tmp_path,'infer','opening','--input-run',prepared.path,'--template-run',templates.path,
            '--freeze-run',tmp_path/'freeze','--expectation-kind','assessment','--toys','1')
    blocked=invoke(tmp_path,'train','blocked','--input-run',prepared.path,'--candidate','M3')
    assert blocked.manifest['status']=='assessment_already_started'
    assert blocked.manifest['context']['candidate_key']=='M3:42'


def test_identity_population_ignores_headers_order_and_never_decodes_payload(tmp_path):
    p=load_protocol().to_dict()
    envelope=lambda group: json.dumps({'event_group_id':group,'label':0,'split':'development','dataset':p['dataset'],'role':'assessment'})
    for name,groups in [('a',['one','two']),('b',['two','one'])]:
        path=tmp_path/(name+'.jsonl')
        path.write_text(json.dumps({'changed_metadata':name})+'\n'+''.join(envelope(g)+'\tINVALID UNOPENED PAYLOAD\n' for g in groups))
    stable=_population_id(tmp_path/'a.jsonl',p['dataset'])
    assert stable==_population_id(tmp_path/'b.jsonl',p['dataset'])
    _claim_assessment(tmp_path,'first-preparation',p,'freeze',population_id=stable)
    with pytest.raises(ResearchStateError):
        _require_unopened(tmp_path,_population_id(tmp_path/'b.jsonl',p['dataset']),p)


def test_primary_report_rejects_method_specific_grid_or_t1_cohorts(tmp_path):
    p=load_protocol().to_dict()
    for candidate,cohort in [('M4','grid-a'),('M5','grid-b')]:
        scope={'mu':1.,'layer':'T1','expectation_kind':'model_self','comparison_cohort_id':cohort}
        with ResearchRun(tmp_path/candidate,allowed_root=tmp_path,stage='infer',dataset=p['dataset'],protocol=p,
            context={'prepared_artifact_id':'same-population','inference_scope':scope}) as run:
            run.write_json('inference.json',{candidate+':42':{'status':'valid','seed':42,'asimov':{
                'candidate_id':candidate,'layer':'T1','expectation_kind':'model_self_asimov',
                'results':[{'mu':1.,'intervals':[{'status':'valid','width':1.}]}]}}})
    with pytest.raises(ResearchError,match='cohorts'):
        invoke(tmp_path,'report','mixed-grid','--result-run',tmp_path/'M4','--result-run',tmp_path/'M5')


def test_absolute_bridge_requires_matching_passed_g1_before_payload(tmp_path, monkeypatch):
    p=load_protocol().to_dict()
    with ResearchRun(tmp_path/'prepared',allowed_root=tmp_path,stage='prepare',dataset=p['dataset'],protocol=p) as run:
        run.manifest['source_kind']='synthetic'
        run.write_json('audit.json',{'status':'passed'})
        (run.path/'events.jsonl').write_text('never decode before G1')
        run.register_file('events.jsonl')
    prepared=read_run(tmp_path/'prepared',dataset=p['dataset'],protocol=p)
    with ResearchRun(tmp_path/'model',allowed_root=tmp_path,stage='train',dataset=p['dataset'],protocol=p,upstreams=[prepared]) as run:
        run.write_json('model.json',{'candidate':'M3','seed':42})
    for name, state, parents in [('blocked','blocked',[prepared]),('wrong','passed',[]),('passed','passed',[prepared])]:
        with ResearchRun(tmp_path/name,allowed_root=tmp_path,stage='templates',dataset=p['dataset'],protocol=p,upstreams=parents) as run:
            run.write_json('g1.json',{'status':state})
    def payload(*a,**kw):
        raise ResearchError('matching G1 allowed payload access')
    monkeypatch.setattr('src.research.workflow.load_research_data',payload)
    extra=['--input-run',prepared.path,'--model-run',tmp_path/'model','--transform','absolute']
    assert invoke(tmp_path,'calibrate','no-gate',*extra).manifest['status']=='g1_not_passed'
    assert invoke(tmp_path,'calibrate','bad-gate',*extra,'--gate-run',tmp_path/'blocked').manifest['status']=='g1_not_passed'
    with pytest.raises(ResearchError,match='different prepared'):
        invoke(tmp_path,'calibrate','other-gate',*extra,'--gate-run',tmp_path/'wrong')
    with pytest.raises(ResearchError,match='allowed payload'):
        invoke(tmp_path,'calibrate','good-gate',*extra,'--gate-run',tmp_path/'passed')
    with pytest.raises(ResearchError,match='prepared --input-run'):
        invoke(tmp_path,'calibrate','missing-input','--transform','absolute','--gate-run',tmp_path/'passed')


def test_report_binds_paired_curves_and_does_not_substitute_another_seed(tmp_path, monkeypatch):
    p=load_protocol().to_dict()
    plotted=[]
    def plot(models,path):
        plotted.append([(m['candidate'],m['seed']) for m in models])
        path.write_bytes(b'synthetic plot receipt')
    monkeypatch.setattr('src.research.workflow.write_learning_curves',plot)
    for name,candidate,seed in [('adv','M6',42),('other','M3-fixed200',43),('control','M3-fixed200',42)]:
        with ResearchRun(tmp_path/name,allowed_root=tmp_path,stage='train',dataset=p['dataset'],protocol=p,
            context={'prepared_artifact_id':'same-source'}) as run:
            run.write_json('model.json',{'candidate':candidate,'seed':seed,'target_lambda':.1 if candidate=='M6' else 0.,
                'groups':None,'model_id':name,'history_contract':{},'status':'trained'})
    missing=invoke(tmp_path,'report','missing','--result-run',tmp_path/'adv','--result-run',tmp_path/'other')
    assert not plotted
    assert missing.read_json('report.json')['learning_curves'][0]['status']=='paired_control_missing_or_ambiguous'
    report=invoke(tmp_path,'report','paired','--result-run',tmp_path/'adv','--result-run',tmp_path/'control')
    assert plotted==[[('M3-fixed200',42),('M6',42)]]
    curve=report.read_json('report.json')['learning_curves'][0]
    assert report.file(curve['file']).read_bytes()==b'synthetic plot receipt'
    assert curve['control_model_id']=='control'
