"""Regression tests for the independent final review, entirely synthetic."""
import copy
import json
from pathlib import Path

import pytest
import torch

from src.cli.research import build_parser
from src.research.artifacts import ResearchRun, read_run, digest_json
from src.research.errors import ResearchError
from src.research.protocol import load_protocol, DEFAULT_PATH
from src.research.matrix_element import _digest
from src.research.workflow import execute, expected_candidates, _me_binding, _supplement_me_bundles, _frozen_stress_reference, _require_unopened


def stage(tmp_path, command, name, *extra):
    args=build_parser().parse_args([command,'--dataset','atlas2020_4lep','--protocol',str(DEFAULT_PATH),
        '--run-dir',str(tmp_path/name),*map(str,extra)])
    execute(args,allowed_root=tmp_path)
    return read_run(tmp_path/name,dataset='atlas2020_4lep',protocol=load_protocol().to_dict(),allow_terminal=True)


def test_unexpected_exception_retains_manifest_receipt_context_and_reporting(tmp_path):
    p=load_protocol().to_dict()
    original=RuntimeError('injected numerical library failure')
    with pytest.raises(RuntimeError) as caught:
        with ResearchRun(tmp_path/'failed',allowed_root=tmp_path,stage='train',dataset=p['dataset'],protocol=p,
            context={'prepared_artifact_id':'synthetic','candidate_key':'M3:42'}):
            raise original
    assert caught.value is original
    failed=read_run(tmp_path/'failed',dataset=p['dataset'],protocol=p,allow_terminal=True)
    assert failed.manifest['status']=='internal_error' and failed.manifest['exit_code']==70
    assert json.loads((failed.path/'failure.json').read_text())['exit_code']==70
    report=stage(tmp_path,'report','report','--result-run',failed.path).read_json('report.json')
    assert report['candidate_statuses']['M3:42']=='internal_error'


def test_frozen_stress_default_and_post_feedback_reference_refusal():
    p=load_protocol().to_dict()
    bundles={'M3:42':{'model_id':'raw-model','mapping_id':'raw-map'},'M5:42':{'model_id':'raw-model','mapping_id':'cdf-map'}}
    frozen={'stress_reference':{'candidate_key':'M3:42','model_id':'raw-model','mapping_id':'raw-map'}}
    assert _frozen_stress_reference(frozen,bundles,p)=='M3:42'
    with pytest.raises(ResearchError,match='pre-assessment'):
        _frozen_stress_reference(frozen,bundles,p,'M5:42')
    bundles['M3:42']['mapping_id']='changed'
    with pytest.raises(ResearchError,match='identity'):
        _frozen_stress_reference(frozen,bundles,p)


def _external_output(inputs):
    rows=[]
    for event in inputs['events']:
        score=.1+.8*((int(event['event_id'].split(':')[-1])//2)%20)/19
        rows.append({'event_id':event['event_id'],'input_digest':event['input_digest'],'p_signal':score,'p_background':1-score})
    return {**{k:inputs[k] for k in ('backend','process','units','probability_definition','input_digest')},
            'schema_version':'h4l-me-output-v1','adapter_sha256':'a'*64,'events':rows}


def _reference(inputs):
    independent={'synthetic_reference':True}
    return {**{k:inputs[k] for k in ('backend','process','units','probability_definition')},
            'status':'validated','evidence_id':'synthetic-test-only','adapter_sha256':'a'*64,
            'checks':[{'event_input':independent,'input_digest':_digest(independent),'adapter_sha256':'a'*64,
                       'expected':[.5,.5],'actual':[.5,.5]}]}


def test_frozen_m1_m1c_cli_supplemental_assessment_lifecycle(tmp_path):
    pytest.importorskip('pyhf', reason='frozen numerical lifecycle uses the optional research environment')
    from test_workflow import synthetic_four_leptons
    from src.research.data import write_research_data
    p=load_protocol().to_dict(); old_threads=torch.get_num_threads(); torch.set_num_threads(1)
    try:
        frame=synthetic_four_leptons()
        source=tmp_path/'source.jsonl'; write_research_data(frame,source,p)
        prepared=stage(tmp_path,'prepare','prepared','--events',source)
        configuration={'backend':{'name':'synthetic-external','version':'1','configuration_sha256':'c'*64},
                       'process':{'signal':'synthetic-s','background':'synthetic-b','pdf':'off','approximation':'test-only'}}
        config_path=tmp_path/'backend.json'; config_path.write_text(json.dumps(configuration))
        exported=stage(tmp_path,'me-export','me-before','--input-run',prepared.path,'--backend-config',config_path)
        inputs=exported.read_json('me-input.json')
        assessment_ids=set(frame.loc[frame.role=='assessment','event_id'])
        assert not assessment_ids & {row['event_id'] for row in inputs['events']}
        output_path=tmp_path/'output.json'; output_path.write_text(json.dumps(_external_output(inputs)))
        reference_path=tmp_path/'reference.json'; reference_path.write_text(json.dumps(_reference(inputs)))
        imported=stage(tmp_path,'me-import','me-import-before','--input-run',prepared.path,'--export-run',exported.path,
                       '--results',output_path,'--reference',reference_path)
        calibration_args=[]
        for candidate in ('M0c','M2','M3'):
            trained=stage(tmp_path,'train',candidate,'--input-run',prepared.path,'--candidate',candidate)
            for transform in (('raw',) if candidate=='M0c' else ('raw','physical')):
                calibration=stage(tmp_path,'calibrate',candidate+'-'+transform,'--input-run',prepared.path,
                    '--model-run',trained.path,'--transform',transform)
                calibration_args.extend(['--calibration-run',str(calibration.path)])
        for transform in ('raw','physical'):
            calibration=stage(tmp_path,'calibrate','ME-'+transform,'--input-run',prepared.path,'--model-run',imported.path,'--transform',transform)
            assert calibration.read_json('calibration.json')['me_binding']==imported.read_json('me-evidence.json')['me_binding']
            calibration_args.extend(['--calibration-run',str(calibration.path)])
        evidence={'status':'validated','evidence_id':'synthetic-effective-count-fixture-only','correlation':'independent_process_bins',
            'auxiliary':'poisson_tau_gamma','modifier':'shapesys','pyhf_version':'0.7.6','protocol_sha256':digest_json(p)}
        evidence_path=tmp_path/'t1.json'; evidence_path.write_text(json.dumps(evidence))
        templates=stage(tmp_path,'templates','templates','--input-run',prepared.path,*calibration_args,'--t1-validation',evidence_path)
        assert templates.read_json('g1.json')['status']=='passed'
        ledger={'protocol_sha256':digest_json(p),'candidates':{key:'training_failed' for key in expected_candidates()}}
        ledger_path=tmp_path/'ledger.json'; ledger_path.write_text(json.dumps(ledger))
        frozen=stage(tmp_path,'freeze','freeze','--input-run',prepared.path,'--template-run',templates.path,'--candidate-ledger',ledger_path)
        assert frozen.read_json('freeze.json')['stress_reference']['candidate_key']=='M3:42'
        with pytest.raises(ResearchError,match='pre-assessment'):
            stage(tmp_path,'infer','wrong-stress-reference','--input-run',prepared.path,'--template-run',templates.path,
                  '--freeze-run',frozen.path,'--expectation-kind','assessment','--procedure','stress','--stress-kind','score',
                  '--reference-candidate','M1c','--toys','1')
        # Rejection happened before assessment opening or external score access.
        _require_unopened(tmp_path,prepared.manifest['population_id'],p)
        after_export=stage(tmp_path,'me-export','me-after','--input-run',prepared.path,'--freeze-run',frozen.path,'--backend-config',config_path)
        after_inputs=after_export.read_json('me-input.json')
        assert assessment_ids <= {row['event_id'] for row in after_inputs['events']}
        after_output=tmp_path/'after-output.json'; after_output.write_text(json.dumps(_external_output(after_inputs)))
        supplemental=stage(tmp_path,'me-import','me-import-after','--input-run',prepared.path,'--export-run',after_export.path,
            '--results',after_output,'--reference',reference_path)
        assert supplemental.read_json('me-evidence.json')['model_id']!=imported.read_json('me-evidence.json')['model_id']
        original_bundles=templates.read_json('calibrations.json')
        with pytest.raises(ResearchError,match='coverage'):
            _supplement_me_bundles(original_bundles,[],prepared,assessment_ids)
        merged=_supplement_me_bundles(original_bundles,[supplemental],prepared,assessment_ids)
        for key in ('M1','M1c'):
            assert merged[key]['model_id']==original_bundles[key]['model_id']
            assert merged[key]['mapping_id']==original_bundles[key]['mapping_id']
            assert merged[key]['thresholds']==original_bundles[key]['thresholds']
        result=stage(tmp_path,'infer','assessment','--input-run',prepared.path,'--template-run',templates.path,'--freeze-run',frozen.path,
            '--expectation-kind','assessment','--toys','1','--assessment-me-run',supplemental.path,'--repeat-assessment')
        results=result.read_json('inference.json')
        assert results['M1']['toys']['paired'] and results['M1c']['toys']['paired']
        assert results['M1']['toys']['pairing_id']==results['M1c']['toys']['pairing_id']
        # Verified supplement mutations with newly hashed artifacts cannot cross semantic bindings.
        for mutation in ('adapter','reference','process','overlap'):
            changed=copy.deepcopy(supplemental.read_json('me-evidence.json')); rows=copy.deepcopy(supplemental.read_json('me-scores.json'))
            if mutation=='adapter': changed['reference']['adapter_sha256']='b'*64
            elif mutation=='reference': changed['reference']['evidence_id']='another-reference'
            elif mutation=='process': changed['inputs']['process']['signal']='another-process'
            else: rows[0]['p_signal']+=.01
            changed['me_binding']=_me_binding(changed)
            with ResearchRun(tmp_path/mutation,allowed_root=tmp_path,stage='me-import',dataset=p['dataset'],protocol=p,upstreams=[prepared]) as run:
                run.write_json('me-evidence.json',changed); run.write_json('me-scores.json',rows)
            bad=read_run(tmp_path/mutation,dataset=p['dataset'],protocol=p)
            with pytest.raises(ResearchError): _supplement_me_bundles(original_bundles,[bad],prepared,assessment_ids)
    finally:
        torch.set_num_threads(old_threads)
