"""Registered off-family contracts, using synthetic values only."""
import itertools

import numpy as np
import pandas as pd
import pytest

from higgsml.errors import ResearchError
from higgsml.inference.attribution import (
    FAMILY, SUBSETS, SEEDS, candidate_key, summarize, seed_interval,
    make_empty_model, empty_bundle, validate_bundle, structural_evidence,
)
from higgsml.modeling.discriminants import predict_discriminant
from higgsml.inference.templates import build_templates, common_mass_grid
from higgsml.protocol import load_protocol


def values():
    return [{"candidate_key": candidate_key(s, g), "seed": s, "subset": g,
             "family_id": FAMILY, "cohort_id": "bound-cohort", "status": "valid",
             "width68": 10 - len(g) + (s-42)*len(g)/10,
             "auc": .5 + len(g)/20, "auc_role": "validation",
             "auc_measure": "absolute_physical_weight", "model_id": f"model-{s}-{g}",
             "auc_model_id": f"model-{s}-{g}"}
            for s in SEEDS for g in SUBSETS]


def test_off_reuse_accepts_only_legacy_repository_validation_metadata(tmp_path):
    from copy import deepcopy

    from higgsml.artifacts import ResearchRun, digest_json, read_run
    from higgsml.inference.attribution_workflow import (
        _load_reusable, _validate_reusable_bundle,
    )

    current = load_protocol().to_dict()
    legacy = deepcopy(current)
    legacy['validation']['repository_authority_validation'] = 'not_run'
    with ResearchRun(tmp_path/'legacy', allowed_root=tmp_path, stage='prepare',
                     dataset=current['dataset'], protocol=legacy) as run:
        run.write_json('payload.json', {'status':'synthetic'})

    # The repository-wide reader remains strict.
    with pytest.raises(ResearchError, match='protocol mismatch'):
        read_run(tmp_path/'legacy', dataset=current['dataset'], protocol=current)

    loaded, binding = _load_reusable(tmp_path/'legacy', current, 'prepare')
    assert loaded.read_json('payload.json') == {'status':'synthetic'}
    assert binding == {
        'mode':'normalized_legacy_validation_metadata',
        'source_protocol_sha256':digest_json(legacy),
        'current_protocol_sha256':digest_json(current),
        'source_protocol_path':str((tmp_path/'legacy'/'protocol.json').resolve()),
        'removed_metadata':{
            'validation.repository_authority_validation':'not_run',
        },
    }
    legacy_model = make_empty_model(legacy, '1'*64, 42)
    legacy_bundle = empty_bundle(legacy_model, legacy)
    _validate_reusable_bundle(legacy_bundle, current, '1'*64)

    scientific_change = deepcopy(legacy)
    scientific_change['templates']['mass_edges'][0] += 1
    with ResearchRun(tmp_path/'changed', allowed_root=tmp_path, stage='prepare',
                     dataset=current['dataset'], protocol=scientific_change):
        pass
    with pytest.raises(ResearchError, match='protocol mismatch'):
        _load_reusable(tmp_path/'changed', current, 'prepare')
    forced, forced_binding = _load_reusable(
        tmp_path/'changed', current, 'prepare', force=True)
    assert forced.manifest['protocol_sha256'] == digest_json(scientific_change)
    assert forced_binding['mode'] == 'forced_protocol_mismatch_debug'
    forced_model = make_empty_model(scientific_change, '1'*64, 42)
    _validate_reusable_bundle(
        empty_bundle(forced_model, scientific_change), current, '1'*64,
        source_protocol=scientific_change, force=True)

    unsupported_metadata = deepcopy(current)
    unsupported_metadata['validation']['repository_authority_validation'] = 'validated'
    with ResearchRun(tmp_path/'unsupported', allowed_root=tmp_path, stage='prepare',
                     dataset=current['dataset'], protocol=unsupported_metadata):
        pass
    with pytest.raises(ResearchError, match='protocol mismatch'):
        _load_reusable(tmp_path/'unsupported', current, 'prepare')


def test_exact_complete_summary_and_pairing():
    result = summarize(values())
    assert result["status"] == "valid"
    assert len(result["pairwise_comparisons"]) == 105
    assert len(result["interactions"]) == 24
    assert len(result["auc_width_relationship"]["observations"]) == 75
    assert result["seed_resampling"]["count"] == 3125
    for row in result["per_seed"]:
        assert sum(row["contributions"].values()) == pytest.approx(4 - (row["seed"]-42)*.4)
    assert result["compact_vs_full"]["selection_status"] == "exploration_selected_pending_frozen_validation"
    assert result == summarize(values())


def test_seed_interval_is_exact_linear_enumeration():
    a = np.array([0., 1., 3., 9., 10.])
    medians = [np.median(a[list(i)]) for i in itertools.product(range(5), repeat=5)]
    assert seed_interval(a)["interval95"] == np.quantile(medians, [.025, .975], method="linear").tolist()


def test_median_is_not_moved_inside_shapley_and_ties_are_statistical():
    rows=values()
    rng=np.random.default_rng(18)
    for row in rows:
        if row['subset']: row['width68']=float(rng.uniform(1,9))
    result=summarize(rows)
    from higgsml.inference.reporting import exact_shapley
    medians={g:-float(np.median([r['width68'] for r in rows if r['subset']==g])) for g in SUBSETS}
    wrong=exact_shapley(medians,family_id=FAMILY,seed=42)['contributions']
    assert any(abs(r['median']-wrong[r['group']])>1e-5 for r in result['contributions'])
    tied=values()
    for row in tied: row['width68']=10. if not row['subset'] else 5.
    result=summarize(tied)
    assert all(r['per_seed_rank']==[8.]*5 and r['first_place_count']==5 for r in result['ranking_stability'])
    assert all(r['strict_win_count']==0 and r['tie_count']==5 for r in result['pairwise_comparisons'])


def test_failed_toys_retain_both_coverage_views():
    from higgsml.inference.reporting import coverage_summary
    result=coverage_summary([{'status':'valid','lower':0,'upper':2},{'status':'fit_failed'}],mu=1)
    assert result['conditional_coverage']==1
    assert result['success_and_coverage_fraction']==.5
    assert result['failure_rate']==.5
    assert result['wilson_interval_conditional_coverage'] is not None
    assert result['wilson_interval_success_and_coverage'] is not None


def test_full_mc_budget_failures_preserve_draws_and_raw_family(monkeypatch):
    from higgsml.inference import bootstrap
    from higgsml.inference.attribution import candidate_keys
    p=load_protocol().to_dict()
    bundles={k:{'key':k,'candidate_id':'M3','model':{},'model_id':k,'mapping_id':k,
                'mapping':None,'transform':'raw','seed':42} for k in candidate_keys()}
    grid={'templates':{k:{} for k in bundles},'mass_edges':[105.,140.],'family_id':FAMILY}
    frame=lambda role: pd.DataFrame([{'role':role,'event_group_id':f'{role}-{i}','label':i%2,
                                      'dataset':p['dataset'],'m4l':120.,'physical_weight':(-1. if i==0 else 2.),
                                      'yield_weight':(-1. if i==0 else 2.)} for i in range(8)])
    from higgsml.errors import ResearchStateError
    def unsupported(*a,**kw): raise ResearchStateError('frozen support failed',status='insufficient_statistics')
    monkeypatch.setattr(bootstrap,'predict_discriminant',lambda m,f:np.full(len(f),.5))
    monkeypatch.setattr(bootstrap,'fit_thresholds',unsupported)
    completed=[]
    result=bootstrap.mass_off_mc_bootstrap(
        grid,bundles,frame('calibration'),frame('template'),p,t1_validation={},
        progress=lambda:completed.append(None))
    assert result['planned_replicas']==200 and result['failed_replicas']==200
    assert len(completed)==16000
    assert all(len(r['candidate_states'])==80 for r in result['replicas'])
    for row in result['replicas']:
        assert sum(row['calibration_group_multiplicities'].values())==8
        assert sum(row['template_group_multiplicities'].values())==8
    assert result['uncertainty']['contributions']==[]


def test_replica_bundle_copies_only_mutable_calibration_state():
    from higgsml.inference.bootstrap import _replica_bundle

    model = object()
    source = {'model':model,'mapping':{'slices':[{'probabilities':[.25]}]},
              'thresholds':{'thresholds':[.5]},'metadata':{'shared':True}}
    replica = _replica_bundle(source)
    replica['mapping']['slices'][0]['probabilities'][0] = .75
    replica['thresholds']['thresholds'][0] = .6

    assert replica['model'] is model
    assert replica['metadata'] is source['metadata']
    assert replica['mapping'] is not source['mapping']
    assert replica['thresholds'] is not source['thresholds']
    assert source['mapping']['slices'][0]['probabilities'] == [.25]
    assert source['thresholds']['thresholds'] == [.5]


def test_mc_bootstrap_workers_preserve_draws_order_and_failures(monkeypatch):
    from higgsml.inference import bootstrap
    from higgsml.inference.attribution import BUDGETS, candidate_keys
    from higgsml.errors import ResearchStateError

    monkeypatch.setitem(BUDGETS['mc_bootstrap'], 'replicas', 2)
    p=load_protocol().to_dict()
    bundles={k:{'key':k,'candidate_id':'M3','model':{},'model_id':k,'mapping_id':k,
                'mapping':None,'transform':'raw','seed':42} for k in candidate_keys()}
    grid={'templates':{k:{} for k in bundles},'mass_edges':[105.,140.],'family_id':FAMILY}
    frame=lambda role: pd.DataFrame([{'role':role,'event_group_id':f'{role}-{i}','label':i%2,
                                      'dataset':p['dataset'],'m4l':120.,'physical_weight':1.,
                                      'yield_weight':1.} for i in range(4)])
    def unsupported(*a,**kw):
        raise ResearchStateError('frozen support failed',status='insufficient_statistics')
    monkeypatch.setattr(bootstrap,'predict_discriminant',lambda m,f:np.full(len(f),.5))
    monkeypatch.setattr(bootstrap,'fit_thresholds',unsupported)
    args=(grid,bundles,frame('calibration'),frame('template'),p)
    serial_progress=[]
    parallel_progress=[]
    serial=bootstrap.mass_off_mc_bootstrap(
        *args,t1_validation={},progress=lambda:serial_progress.append(None))
    parallel=bootstrap.mass_off_mc_bootstrap(
        *args,t1_validation={},workers=2,progress=lambda:parallel_progress.append(None))
    assert parallel==serial
    assert len(serial_progress)==len(parallel_progress)==160


def test_access_review_missing_fails_before_any_payload(monkeypatch):
    from higgsml.inference.attribution_workflow import _assessment_frame
    from higgsml.errors import ResearchStateError
    with pytest.raises(ResearchStateError,match='missing'):
        _assessment_frame(None,None,None,None,None,'assessment-mu1')


def test_joint_off_family_uses_physical_cells_and_rejects_negative_process_support():
    from higgsml.inference.assessment import _joint_mother
    p=load_protocol().to_dict()
    frame=pd.DataFrame([{'dataset':p['dataset'],'role':'assessment','event_group_id':str(i),'event_id':str(i),
                         'm4l':120.,'label':i%2,'yield_weight':1.,'category':(i//2)%2} for i in range(160)])
    bundles={candidate_key(s,g):{'mapping_id':candidate_key(s,g),'empty':not g} for s in SEEDS for g in SUBSETS}
    templates={k:{'mass_edges':[105.,140.],'categories':[0,1],'mapping_id':k,
                  'active_bins':[1] if b['empty'] else [0,1]} for k,b in bundles.items()}
    grid={'family_id':FAMILY,'templates':templates,'mass_edges':[105.,140.]}
    categorize=lambda b,f:f.assign(category=1 if b['empty'] else f.category)
    _,columns,(cells,inverse)=_joint_mother(grid,bundles,frame,p,categorize)
    assert len(columns)==80 and len(cells)==2 and len(inverse)==160
    frame.loc[frame.label==0,'yield_weight']=-1.
    with pytest.raises(ResearchError,match='nonnegative'):
        _joint_mother(grid,bundles,frame,p,categorize)


def test_t2_mapping_and_failed_outer_budget_are_retained():
    from higgsml.inference.likelihood import run_t2_procedure
    base=lambda role:pd.DataFrame([dict(role=role,event_group_id=f'{role}-{i}',physical_weight=1.,yield_weight=1.) for i in range(10)])
    count=[0]
    def fit(frame):
        count[0]+=1
        if count[0]==1:
            from higgsml.errors import ResearchStateError
            raise ResearchStateError('support',status='insufficient_statistics')
        return {'mapping_id':str(count[0]),'bundles':{'empty':{'model_id':'constant','mapping_id':'raw:constant',
                                                           'mapping':None,'thresholds':{'thresholds':[.5]}}}}
    def apply(mapping,frame): return frame.assign(mapping=mapping['mapping_id'])
    def evaluate(template,mother,mapping,budget,seed):
        assert set(template.mapping)==set(mother.mapping)=={mapping['mapping_id']}
        assert budget==100
        return {'status':'valid'}
    result=run_t2_procedure(base('calibration'),base('template'),base('assessment'),fit_mapping=fit,
                           apply_mapping=apply,evaluate=evaluate,outer_replicas=20,inner_toys=100,seed=42,
                           model_id='fixed',mother_id='fixed-parent',record_mappings=True)
    assert len(result['replicas'])==20
    assert result['replicas'][0]['status']=='insufficient_statistics'
    assert all(row['planned_inner_toys']==100 for row in result['replicas'])
    assert all(row['mappings']['empty']['thresholds']['thresholds']==[.5] for row in result['replicas'][1:])


@pytest.mark.parametrize("change", ["missing", "cohort", "auc_role", "auc_model", "duplicate", "nonfinite"])
def test_incomplete_never_imputed(change):
    rows = values()
    if change == "missing": rows.pop()
    if change == "cohort": rows[0]["cohort_id"] = "other"
    if change == "auc_role": rows[-1]["auc_role"] = "assessment"
    if change == "auc_model": rows[-1]["auc_model_id"] = "wrong"
    if change == "duplicate": rows.append(rows[-1])
    if change == "nonfinite": rows[-1]["width68"] = None
    result = summarize(rows)
    assert result["status"] == "incomplete"
    assert result["ranking_stability"] is None


def test_null_model_structural_grid_and_likelihood_equivalence():
    p = load_protocol().to_dict()
    model = make_empty_model(p, "a"*64, 42)
    frame = pd.DataFrame([dict(dataset=p["dataset"], role="template", event_group_id=f"{y}-{i}",
                               label=y, m4l=110., physical_weight=1., yield_weight=1.)
                          for y in (0,1) for i in range(30)])
    assert np.array_equal(predict_discriminant(model, frame), np.full(len(frame), .5))
    assert model["ordered_inputs"] == [] and model["state_dict"] == {}
    bundle = empty_bundle(model, p)
    validate_bundle(bundle, p, "a"*64)
    edge = [105.,140.]
    evidence = structural_evidence(bundle, frame, edge)
    zero = build_templates(frame.assign(category=1), mass_edges=edge, mapping_id=bundle["mapping_id"],
                           candidate_id="M0off", structural_zero_evidence=evidence)
    mass = build_templates(frame.assign(category=0), mass_edges=edge, mapping_id="mass", candidate_id="M0", categories=(0,))
    assert zero["status"] == "valid" and zero["active_bins"] == [1]
    for left,right in zip(zero["samples"],mass["samples"]):
        assert [left["yield"][i] for i in zero["active_bins"]] == right["yield"]
        assert [left["variance"][i] for i in zero["active_bins"]] == right["variance"]
    grid = common_mass_grid({"M0off:42": frame.assign(category=1)}, mass_edges=[105.,120.,140.],
                            thresholds=p["templates"],
                            structural_zero_bundles={"M0off:42": bundle})
    assert grid["status"] == "valid"
    with pytest.raises(ResearchError):
        build_templates(frame.assign(category=0), mass_edges=edge, mapping_id=bundle["mapping_id"],
                        candidate_id="M0off", structural_zero_evidence=evidence)
    model["score"] = .6
    with pytest.raises(ResearchError): predict_discriminant(model, frame)


def test_rank_of_medians_is_separate_from_median_rank():
    from scipy.stats import rankdata
    rows=values()
    rng=np.random.default_rng(18)
    for row in rows:
        if row['subset']: row['width68']=float(rng.uniform(1,9))
    ranking=summarize(rows)['ranking_stability']
    expected=rankdata([r['width68']['median'] for r in ranking],method='average')
    assert [r['rank_of_median_width68'] for r in ranking]==expected.tolist()
    assert any(r['rank_of_median_width68']!=r['median_rank'] for r in ranking)


@pytest.mark.parametrize('change',['family','budget','mu','stage','plan','inputs','upstream','missing'])
def test_evaluation_manifest_rejects_unbound_cells(change):
    from copy import deepcopy
    from types import SimpleNamespace
    from higgsml.artifacts import digest_json
    from higgsml.inference.attribution import BUDGETS
    from higgsml.inference.attribution_workflow import validate_evaluation_manifest
    plan={'inputs':{str(i):str(i)*64 for i in range(1,6)}}
    context={'family_id':FAMILY,'mu':1,'budgets':deepcopy(BUDGETS),
             'evaluation_plan_id':digest_json(plan),'evaluation_inputs':deepcopy(plan['inputs'])}
    manifest={'stage':'attribution-t2','context':context,'upstreams':[{'artifact_id':v} for v in plan['inputs'].values()]}
    item=SimpleNamespace(manifest=manifest)
    assert validate_evaluation_manifest(item,plan)==('t2',1)
    if change=='family': context['family_id']='wrong'
    if change=='budget': context['budgets']['toys']['count']=499
    if change=='mu': context['mu']=0
    if change=='stage': manifest['stage']='t2'
    if change=='plan': context['evaluation_plan_id']='0'*64
    if change=='inputs': context['evaluation_inputs']['1']='0'*64
    if change=='upstream': manifest['upstreams'].pop()
    if change=='missing': manifest.pop('context')
    with pytest.raises(ResearchError,match='mismatch'): validate_evaluation_manifest(item,plan)


def test_p0_applicability_validates_semantics_after_resigning(tmp_path):
    from copy import deepcopy
    from higgsml.artifacts import digest_json,sha256_file
    from higgsml.inference.evidence import validate_off_p0
    path=tmp_path/'reference.txt'; path.write_text('synthetic numerical reference fixture',encoding='utf-8')
    names=['processes','units','four_vectors','pairing','weights','selection']
    expected={'dataset':'atlas2020_4lep','protocol_sha256':'1'*64,'prepared_artifact_id':'2'*64,
              'freeze_artifact_id':'3'*64,'template_artifact_id':'4'*64,'source_evidence_sha256':'5'*64}
    value={**expected,'schema_version':'h4l-off-p0-applicability-v1','status':'validated','independent':True,
           'statistical_model':'signed_mc_T1_independent_process_bins_poisson_tau_gamma',
           'reference':{'producer':'synthetic test','reference_id':'fixture','independence_basis':'test only',
                        'files':[{'path':path.name,'sha256':sha256_file(path),'size_bytes':path.stat().st_size}]},
           'physical_definitions':{n:{'description':'fixture '+n,'reference_files':[path.name]} for n in names},
           'numerical_comparisons':[{'definition':n,'quantity':n,'unit':'test','expected':1.,'actual':1.,
                                    'atol':0.,'rtol':0.,'reference_path':path.name} for n in names]}
    def sign(v): v['package_id']=digest_json({k:x for k,x in v.items() if k!='package_id'}); return v
    validate_off_p0(sign(value),expected=expected,package_root=tmp_path)
    for change in ('null','comparisons','dataset','scope','tolerance','reference','coverage'):
        bad=deepcopy(value)
        if change=='null': bad['physical_definitions']['weights']=None
        if change=='comparisons': bad['numerical_comparisons']=[None]*6
        if change=='dataset': bad['dataset']='wrong'
        if change=='scope': bad['statistical_model']='T0'
        if change=='tolerance': bad['numerical_comparisons'][0]['actual']=2.
        if change=='reference': bad['physical_definitions']['weights']['reference_files']=['missing']
        if change=='coverage': bad['numerical_comparisons']=[bad['numerical_comparisons'][0]]*6
        with pytest.raises(ResearchError): validate_off_p0(sign(bad),expected=expected,package_root=tmp_path)


def test_access_gate_validates_before_claim_and_decodes_only_once(monkeypatch,tmp_path):
    import json
    from types import SimpleNamespace
    from higgsml.artifacts import digest_json,sha256_file
    from higgsml.inference import evidence,attribution_workflow as workflow
    p=load_protocol().to_dict()
    prepared_path=tmp_path/'old'/'prepare'; prepared_path.mkdir(parents=True)
    (prepared_path/'p0-validation.json').write_text('{}',encoding='utf-8')
    prepared=SimpleNamespace(path=prepared_path,manifest={'artifact_id':'1'*64},
                             file=lambda n:prepared_path/n,read_json=lambda n:p)
    frozen=SimpleNamespace(manifest={'artifact_id':'2'*64},read_json=lambda n:{'template_artifact_id':'3'*64})
    overlay={'population_id':'4'*64}
    receipts={}
    for name in ('p0','t1'):
        path=tmp_path/(name+'.json'); path.write_text('{}',encoding='utf-8')
        receipts[name+'_reference']={'path':path.name,'sha256':sha256_file(path),'size_bytes':path.stat().st_size}
    review={'schema_version':'h4l-off-assessment-access-v1','status':'validated','independent':True,
            'prepared_artifact_id':'1'*64,'freeze_artifact_id':'2'*64,'population_id':'4'*64,
            'protocol_sha256':digest_json(p),'reviewer':'synthetic fixture',
            'history_review':'unused_independent_assessment_population','role_isolation':'physical_groups_verified_disjoint',**receipts}
    path=tmp_path/'access.json'; path.write_text(json.dumps(review),encoding='utf-8')
    decoded=[]
    def load(*a,**kw):
        assert kw['allow_assessment'] is True
        assert (tmp_path/'.research-claims'/('off-cells-'+'2'*64)/'assessment-mu1.json').is_file()
        decoded.append(True)
        return 'synthetic frame'
    monkeypatch.setattr(workflow,'load_research_data',load)
    def invalid(*a,**kw): raise ResearchError('forged applicability')
    monkeypatch.setattr(evidence,'validate_off_p0',invalid)
    with pytest.raises(ResearchError,match='forged'):
        workflow._assessment_frame(prepared,overlay,frozen,p,path,'assessment-mu1')
    assert not decoded and not (tmp_path/'.research-claims').exists()
    # Numerical validation is covered above; this fixture isolates durable claim ordering.
    monkeypatch.setattr(evidence,'validate_off_p0',lambda *a,**kw:None)
    monkeypatch.setattr(evidence,'validate_evidence_package',lambda *a,**kw:{'status':'validated','evidence_type':'signed_mc_t1','prepared_artifact_id':'1'*64})
    assert workflow._assessment_frame(prepared,overlay,frozen,p,path,'assessment-mu1')=='synthetic frame'
    with pytest.raises(ResearchError,match='budget already consumed'):
        workflow._assessment_frame(prepared,overlay,frozen,p,path,'assessment-mu1')
    assert decoded==[True]


def test_model_self_joint_generation_and_process_marginals(monkeypatch,tmp_path):
    from copy import deepcopy
    from higgsml.inference import assessment
    p=load_protocol().to_dict()
    frame=pd.DataFrame([dict(dataset=p['dataset'],role='template',event_group_id=str(i),event_id=str(i),
                             process='signal' if i%2 else 'background',label=i%2,m4l=120.,
                             physical_weight=1.,yield_weight=1.,category=(i//2)%2) for i in range(120)])
    bundles={candidate_key(s,g):{'mapping_id':candidate_key(s,g),'empty':not g} for s in SEEDS for g in SUBSETS}
    categorize=lambda b,f:f.assign(category=1 if b['empty'] else f.category)
    templates={}
    for k,b in bundles.items():
        t=build_templates(frame,mass_edges=[105.,140.],mapping_id=k,candidate_id='M3',thresholds=p['templates'])
        if b['empty']:
            for sample in t['samples']:
                for name in ('yield','variance'): sample[name]=[0.,sum(sample[name])]
            t['active_bins']=[1]
        templates[k]=t
    grid={'family_id':FAMILY,'status':'valid','templates':templates,'mass_edges':[105.,140.]}
    # Keep real joint generation, model construction and projection; stub costly interval optimizers only.
    monkeypatch.setattr(assessment,'profile_intervals',lambda *a,**kw:[{'status':'valid','lower':0.,'upper':2.,'width':2.,'muhat':1.}]*2)
    monkeypatch.setattr(assessment,'run_asimov',lambda *a,**kw:{'status':'valid'})
    completed=[]
    result=assessment.infer_assessment(grid,bundles,frame,p,layer='T0',t1_validation=None,mu=1,count=2,
                                     seed=42,prepared_id='p',freeze_id='f',categorize=categorize,parent_role='template',
                                     progress=lambda:completed.append(None))
    assert len(result)==80 and all(r['status']=='valid' and r['toys']['paired'] for r in result.values())
    assert len(completed)==160
    totals=[sum(r['toys']['results'][0]['observations']) for r in result.values()]
    assert len(set(totals))==1
    # Exercise the actual stage dispatcher, with real joint service and a reduced test-only fit count.
    import json
    from types import SimpleNamespace
    from higgsml.inference import attribution_workflow as workflow
    evidence=dict(status='validated',evidence_id='synthetic-only',correlation='independent_process_bins',
                  auxiliary='poisson_tau_gamma',modifier='shapesys',pyhf_version='0.7.6')
    upstreams=[SimpleNamespace(manifest={'artifact_id':str(i)*64},read_json=lambda n:evidence,file=lambda n:tmp_path/n) for i in range(1,6)]
    registered,prepared,nominal,frozen,asimov=upstreams
    asimov.manifest['upstreams']=[{'artifact_id':x.manifest['artifact_id']} for x in (registered,nominal,frozen)]
    plan=workflow.evaluation_plan(p,*upstreams)
    plan_path=tmp_path/'plan.json'; plan_path.write_text(json.dumps(plan),encoding='utf-8')
    monkeypatch.setattr(workflow,'load_frozen',lambda *a,**kw:(registered,{'qualification':{}},prepared,nominal,grid,bundles,frozen))
    monkeypatch.setattr(workflow,'_load',lambda *a:asimov)
    monkeypatch.setattr(workflow,'load_research_data',lambda *a,**kw:frame)
    monkeypatch.setattr(workflow,'categorize_bundle',categorize)
    monkeypatch.setattr(assessment,'categorize_bundle',categorize)
    original=assessment.infer_assessment
    def short_inference(*a,**kw):
        assert kw['count']==500 and kw['parent_role']=='template'
        kw['count']=2
        return original(*a,**kw)
    monkeypatch.setattr(assessment,'infer_assessment',short_inference)
    written={}
    class Output:
        def __init__(self,*a,**kw): self.manifest={'artifact_id':'6'*64,'context':kw['context']}; self.status='complete'
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def write_json(self,name,value): written[name]=value
    monkeypatch.setattr(workflow,'ResearchRun',Output)
    workflow.evaluate(None,None,None,p,tmp_path/'out',tmp_path,stage='model-self',mu=1,
                      evaluation_plan_path=plan_path,result_path='asimov')
    assert written['evaluation.json']['pairing']=='shared_joint_physical_cells'
    assert written['evaluation-plan.json']==plan
    assert all(v['toys']['expectation_kind']=='model_self' for v in written['evaluation.json']['candidates'].values())
    wrong=deepcopy(grid); wrong['templates'][candidate_key(42,'A')]['samples'][0]['yield'][0]+=1
    with pytest.raises(ResearchError,match='marginal'):
        assessment._joint_mother(wrong,bundles,frame,p,categorize,parent_role='template')
    negative=frame.copy(); negative.loc[0,'process']='negative_background'; negative.loc[0,'yield_weight']=-.1
    assert negative.loc[negative.label==0,'yield_weight'].sum()>0
    with pytest.raises(ResearchError,match='nonnegative'):
        assessment._joint_mother(grid,bundles,negative,p,categorize,parent_role='template')
    # A marginal mismatch must select the registered unpaired model-self fallback.
    monkeypatch.setattr(workflow,'load_frozen',lambda *a,**kw:(registered,{'qualification':{}},prepared,nominal,wrong,bundles,frozen))
    from higgsml.inference import likelihood
    def marginal(*a,**kw):
        assert kw['count']==500
        return {'status':'valid','paired':False,'results':[]}
    monkeypatch.setattr(likelihood,'run_toys',marginal)
    workflow.evaluate(None,None,None,p,tmp_path/'fallback',tmp_path,stage='model-self',mu=1,
                      evaluation_plan_path=plan_path,result_path='asimov')
    assert written['evaluation.json']['pairing']=='unavailable'
    assert 'marginal' in written['evaluation.json']['pairing_reason']
