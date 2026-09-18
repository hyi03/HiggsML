"""Default marginal workflow state and durable population access safety."""
import pytest
from higgsml.errors import ResearchError, ResearchStateError
from higgsml.inference import marginal_evaluation_state as state
from higgsml.inference.marginal_coupling import canonical_seed_blocks,pairing_contract,METADATA
from higgsml.protocol import load_protocol


def binding(freeze):
    return state.SeedEvaluationBinding('population',freeze,'spec','plan',
        pairing_contract()['contract_digest'],
        'assessment',1,42,canonical_seed_blocks()[0].candidate_keys,
        {'receipt':'review'},{'planned_toys_per_candidate':2},{'stream_id':'stream'})


def test_consumed_population_cannot_change_freeze(tmp_path):
    state.claim_seed_evaluation(claims_root=tmp_path,output_dir=tmp_path/'one',binding=binding('freeze1'))
    with pytest.raises(ResearchStateError,match='previously used'):
        state.claim_seed_evaluation(claims_root=tmp_path,output_dir=tmp_path/'two',binding=binding('freeze2'))


def test_failure_terminal_resumes(tmp_path):
    b=binding('freeze')
    output=tmp_path/'cell'
    state.claim_seed_evaluation(claims_root=tmp_path,output_dir=output,binding=b)
    terminal={**METADATA,'execution_status':'complete','scientific_status':'insufficient_statistics',
        'qualification':{'status':'insufficient_statistics'},'joint_support':{},'marginal_support':{},'coupling_receipts':[],
        'planned_toys_per_candidate':2,'generated_physical_toys':0,
        'candidate_results':[{'candidate_id':c,'attempted_fits':0,'completed_fits':0,'valid_fits':0} for c in b.candidate_ids]}
    protocol=load_protocol().to_dict()
    state.publish_seed_evaluation_terminal(output_dir=output,allowed_root=tmp_path,claims_root=tmp_path,
        dataset=protocol['dataset'],protocol=protocol,binding=b,terminal=terminal)
    assert state.resolve_seed_evaluation(output_dir=output,claims_root=tmp_path,
        dataset=protocol['dataset'],protocol=protocol,binding=b)=='skip_terminal'


def test_default_schema_owns_real_blocks_and_rejects_joint_contract():
    import json
    from pathlib import Path
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError
    from higgsml.inference.seed_blocks import pairing_contract as joint
    schema=json.loads((Path(__file__).parents[2]/'config/schemas/h4l_mass_off_marginal_blocks.schema.json').read_text())
    value={**pairing_contract(),'blocks':[b.as_dict() for b in canonical_seed_blocks()]}
    Draft202012Validator(schema).validate(value)
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate({**value,'contract_id':joint()['contract_id']})


def test_full_wrapper_requires_access_before_work(monkeypatch):
    import importlib.util
    from pathlib import Path
    path=Path(__file__).parents[2]/'scripts/h4l_off_run.py'
    spec=importlib.util.spec_from_file_location('default_access_guard',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'_invoke',lambda *a,**k:pytest.fail('work started before access precondition'))
    args=module._parser().parse_args(['--source-run-name','fixture','--run-name','new'])
    with pytest.raises(module.WorkflowError,match='requires --access-review'):
        module._run(args)


def test_terminal_schema_requires_support_and_conditional_metadata():
    import json
    from pathlib import Path
    from jsonschema import Draft202012Validator
    schema=json.loads((Path(__file__).parents[2]/'config/schemas/h4l_mass_off_marginal_block_evaluation.schema.json').read_text())
    from jsonschema.exceptions import ValidationError
    validator=Draft202012Validator(schema)
    b=binding('freeze')
    value={**METADATA,'schema_version':state.TERMINAL_SCHEMA,'cell_id':b.cell_id,
        'claim_id':'0'*64,'terminal_id':'0'*64,'binding':b.value(),
        'execution_status':'complete','scientific_status':'insufficient_statistics',
        'qualification':{'status':'insufficient_statistics'},'joint_support':{},
        'marginal_support':{},'coupling_receipts':[],
        'planned_toys_per_candidate':2,'generated_physical_toys':0,
        'candidate_results':[{'candidate_id':c,'attempted_fits':0,'completed_fits':0,'valid_fits':0} for c in b.candidate_ids]}
    validator.validate(value)
    for field in ('marginal_support','coupling_receipts','physical_event_pairing','uncertainty_scope'):
        changed=dict(value);changed.pop(field)
        with pytest.raises(ValidationError):
            validator.validate(changed)
    with pytest.raises(ValidationError):
        validator.validate({**value,'physical_event_pairing':True})


def test_concurrent_claims_cannot_use_different_freezes(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    barrier=Barrier(2)
    # Force both readers to finish their historical scan before either reserves.
    def checked(*args): barrier.wait(timeout=10)
    monkeypatch.setattr(state,'_check_v1_population_history',checked)
    def claim(freeze):
        try:
            state.claim_seed_evaluation(claims_root=tmp_path,output_dir=tmp_path/freeze,binding=binding(freeze))
            return 'claimed'
        except ResearchError:
            return 'blocked'
    with ThreadPoolExecutor(2) as pool:
        result=list(pool.map(claim,['one','two']))
    assert sorted(result)==['blocked','claimed']


def test_invalid_legacy_directory_does_not_reserve_population(tmp_path):
    from higgsml.workflow import _claim_assessment
    (tmp_path/'.research-claims').write_text('not a directory')
    with pytest.raises((ResearchError,FileExistsError)):
        _claim_assessment(tmp_path,'prepared',load_protocol().to_dict(),'freeze',population_id='population')
    assert not (tmp_path/'.h4l-population-access').exists()
