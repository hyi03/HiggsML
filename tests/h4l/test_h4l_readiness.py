"""One-command preflight must be read-only and never mistake a stop for completion."""
import importlib.util
import json
from pathlib import Path

import pytest

from higgsml.artifacts import digest_json
from higgsml.protocol import load_protocol


def wrapper(tmp_path, monkeypatch):
    path = Path(__file__).parents[2] / 'scripts/h4l_all.py'
    spec = importlib.util.spec_from_file_location('readiness_wrapper', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'RUNS_ROOT', tmp_path / 'runs')
    return module


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def prepared(tmp_path):
    value = {'stage': 'prepare', 'status': 'complete', 'dataset': 'atlas2020_4lep',
             'population_id': 'a' * 64, 'protocol_sha256': digest_json(load_protocol().to_dict())}
    write(tmp_path / 'runs/h4l-prepare-new/prepare/manifest.json',
          {**value, 'artifact_id': digest_json(value)})


def test_plan_only_never_invokes_work_or_creates_run_root(tmp_path, monkeypatch, capsys):
    module = wrapper(tmp_path, monkeypatch)
    monkeypatch.setattr(module, '_invoke', lambda *_: pytest.fail('plan invoked a child'))
    args = module._parser().parse_args(['--run-name', 'new', '--plan-only',
                                      '--threshold-method', 'joint-support-v1'])
    module._run(args)
    plan = json.loads(capsys.readouterr().out)
    assert plan['threshold_method'] == 'joint-support-v1'
    assert plan['access_status'] == 'pending_prepare_identity'
    assert plan['scientific_qualification'] == 'unvalidated_exploratory_only'
    assert not (tmp_path / 'runs').exists()


def test_archive_history_blocks_before_prepare_or_training(tmp_path, monkeypatch):
    module = wrapper(tmp_path, monkeypatch)
    prepared(tmp_path)
    write(tmp_path / 'config/h4l_history_roots.json', {
        'schema_version': 'h4l-history-roots-v1',
        'roots': [{'path': 'runs', 'required': False}, {'path': 'archive', 'required': True}],
    })
    write(tmp_path / 'archive/.h4l-population-access/old.json',
          {'population_id': 'a' * 64, 'freeze_artifact_id': 'b' * 64})
    monkeypatch.setattr(module, '_invoke', lambda *_: pytest.fail('blocked run invoked work'))
    with pytest.raises(module.WorkflowError) as error:
        module._run(module._parser().parse_args(['--run-name', 'new']))
    assert error.value.exit_code == 5


def test_existing_joint_registration_rejects_implicit_median_before_work(tmp_path, monkeypatch):
    module = wrapper(tmp_path, monkeypatch)
    write(tmp_path / 'runs/h4l-off-new/register/registration.json',
          {'threshold_method': 'joint-support-v1'})
    monkeypatch.setattr(module, '_invoke', lambda *_: pytest.fail('method conflict started work'))
    with pytest.raises(module.WorkflowError, match='threshold'):
        module._run(module._parser().parse_args(['--run-name', 'new']))


def test_support_stop_returns_blocked_not_success(tmp_path, monkeypatch):
    module = wrapper(tmp_path, monkeypatch)
    prepared(tmp_path)
    monkeypatch.setattr(module, '_invoke', lambda *_: None)
    monkeypatch.setattr('sys.argv', ['h4l_all.py', '--run-name', 'new'])
    assert module.main() == 5


def test_zero_child_exit_without_final_report_is_incomplete(tmp_path, monkeypatch):
    module = wrapper(tmp_path, monkeypatch)
    prepared(tmp_path)
    write(tmp_path / 'runs/h4l-off-new/evaluation-plan/evaluation-plan.json', {})
    review = tmp_path / 'review.json'
    write(review, {'schema_version': 'h4l-off-assessment-access-v3'})
    monkeypatch.setattr(module, '_invoke', lambda *_: None)
    monkeypatch.setattr('sys.argv', ['h4l_all.py', '--run-name', 'new', '--access-review', str(review)])
    assert module.main() == 6


def test_name_escape_rejected_before_invoking_children(tmp_path, monkeypatch):
    module = wrapper(tmp_path, monkeypatch)
    monkeypatch.setattr(module, '_invoke', lambda *_: pytest.fail('unsafe name invoked work'))
    with pytest.raises(module.WorkflowError):
        module._run(module._parser().parse_args(['--run-name', '../escape']))


def test_stage_b_only_does_not_claim_complete_from_plan_file_presence(tmp_path, monkeypatch):
    module = wrapper(tmp_path, monkeypatch)
    prepared(tmp_path)
    write(tmp_path / 'runs/h4l-off-new/evaluation-plan/evaluation-plan.json', {})
    monkeypatch.setattr(module, '_invoke', lambda *_: None)
    monkeypatch.setattr('sys.argv', ['h4l_all.py', '--run-name', 'new', '--stage-b-only'])
    assert module.main() == 6
