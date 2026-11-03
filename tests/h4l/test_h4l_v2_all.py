"""Integrated orchestration checks; no controlled-MC or production fits."""
import importlib.util
import json
from pathlib import Path

import pytest

from higgsml.errors import ResearchError


@pytest.fixture
def wrapper(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / 'scripts/h4l_v2_all.py'
    spec = importlib.util.spec_from_file_location('h4l_v2_all_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'PROJECT_ROOT', tmp_path)
    return module


def last_json(capsys):
    return json.loads(capsys.readouterr().out.splitlines()[-1])


def fake_stages(wrapper, monkeypatch, *, failure=None, incomplete=None):
    calls = []
    evaluation = wrapper.PROJECT_ROOT / 'runs/h4l-draft-v2-draft001/evaluate-retry-selected'

    def execute(family):
        def invoke(args, protocol):
            key = f'{family}:{args.stage}'
            calls.append((key, args))
            if key == failure:
                raise ResearchError('Review is missing or stale')
            if key == 'nominal:report':
                assert args.evaluation_run == evaluation
            result = dict(execution_status='complete', path=str(
                evaluation if key == 'nominal:evaluate' else args.run_root / (args.stage + '-resume-selected')))
            if key == incomplete:
                result['scientific_status' if family == 'nominal' else 'numerical_status'] = 'incomplete'
            return result
        return invoke

    for family in ('nominal', 'validation', 't2'):
        monkeypatch.setattr(getattr(wrapper, family), 'execute', execute(family))
    return calls


def test_fresh_plan_no_stage_execution_or_output(wrapper, monkeypatch, capsys):
    for family in ('nominal', 'validation', 't2'):
        monkeypatch.setattr(getattr(wrapper, family), 'execute',
                            lambda *a: pytest.fail('Plan executed a stage'))
    assert wrapper.main(['--plan-only', '--with-t2']) == 0
    value = last_json(capsys)
    assert len(value['stages']) == 13
    assert value['extensions']['t2']['identity_status'] == 'pending_nominal_report'
    assert value['extensions']['validation']['payloads_opened'] is False
    assert not (wrapper.PROJECT_ROOT / 'runs').exists()
    assert value['commands'][0][-2:] == ['--dataset-receipt', str(
        wrapper.PROJECT_ROOT / 'data/raw/atlas2020_4lep/dataset_receipt.json')]
    assert value['qualification']['primary_claim_eligible'] is False


def test_default_complete_core_and_argument_routing(wrapper, monkeypatch, capsys):
    import torch
    previous = torch.get_num_threads()
    calls = fake_stages(wrapper, monkeypatch)
    assert wrapper.main(['--continue', '--workers', '2', '--no-progress',
                         '--nominal-access-review', 'nominal.json',
                         '--validation-access-review', 'validation.json']) == 0
    assert [k for k, _ in calls] == ['nominal:prepare', 'nominal:train', 'nominal:freeze',
        'nominal:evaluate', 'nominal:report', 'validation:register', 'validation:bootstrap',
        'validation:model-self', 'validation:report']
    assert all(a.continuation and a.no_progress and not a.retry_failed for _, a in calls)
    assert calls[3][1].access_review == Path('nominal.json')
    assert calls[6][1].access_review == Path('validation.json')
    assert calls[6][1].workers == 2
    result = last_json(capsys)
    assert result['reports']['validation'].endswith('report-resume-selected')
    assert 't2' not in result['reports']
    assert torch.get_num_threads() == previous


@pytest.mark.parametrize('through,count', [('freeze', 3), ('nominal', 5), ('validation-register', 6),
    ('validation', 9), ('t2-register', 10), ('t2-prepare', 11), ('t2', 13)])
def test_stage_boundaries(wrapper, monkeypatch, capsys, through, count):
    calls = fake_stages(wrapper, monkeypatch)
    assert wrapper.main(['--through', through, '--with-t2', '--no-progress']) == 0
    assert len(calls) == count
    result = last_json(capsys)
    if through == 'freeze':
        assert result['numerical_status'] == 'not_evaluated'


@pytest.mark.parametrize('failure,count,pending', [
    ('nominal:evaluate', 4, 'freeze/access-review.pending.json'),
    ('validation:bootstrap', 7, 'register/access-review.pending.json'),
    ('t2:prepare', 11, 'register/access-review.pending.json')])
def test_access_failure_stops_downstream_and_restores_threads(wrapper, monkeypatch, capsys, failure, count, pending):
    import torch
    previous = torch.get_num_threads()
    calls = fake_stages(wrapper, monkeypatch, failure=failure)
    assert wrapper.main(['--with-t2', '--no-progress']) == 3
    assert len(calls) == count
    result = last_json(capsys)
    assert result['execution_status'] == 'blocked'
    assert result['stopped_at'] == failure
    assert Path(result['pending_access_review']).as_posix().endswith(pending)
    assert torch.get_num_threads() == previous


def test_failed_training_never_freezes(wrapper, monkeypatch, capsys):
    calls = fake_stages(wrapper, monkeypatch, incomplete='nominal:train')
    assert wrapper.main(['--no-progress']) == 6
    assert len(calls) == 2
    assert last_json(capsys)['stopped_at'] == 'nominal:train'


@pytest.mark.parametrize('incomplete', ['nominal:report', 'validation:report', 't2:report'])
def test_numerical_failure_is_retained_without_skipping_reports(wrapper, monkeypatch, capsys, incomplete):
    calls = fake_stages(wrapper, monkeypatch, incomplete=incomplete)
    assert wrapper.main(['--with-t2', '--no-progress']) == 6
    assert len(calls) == 13
    result = last_json(capsys)
    assert result['execution_status'] == 'complete'
    assert result['numerical_status'] == 'incomplete'


def test_plan_existing_source_delegates_metadata_validation(wrapper, monkeypatch, capsys):
    root = wrapper.PROJECT_ROOT / 'runs/h4l-draft-v2-draft001/report'
    root.mkdir(parents=True)
    from higgsml.artifacts import digest_json
    protocol = wrapper.nominal_protocol.load_protocol(wrapper.nominal_protocol.DEFAULT_PROTOCOL)
    (root / 'manifest.json').write_text(json.dumps({'protocol_sha256': digest_json(protocol)}), encoding='utf-8')
    seen = []
    def metadata(args, protocol):
        assert args.plan_only
        seen.append(args.stage)
        return dict(payloads_opened=False)
    monkeypatch.setattr(wrapper.validation, 'execute', metadata)
    monkeypatch.setattr(wrapper.nominal, 'execute', lambda *a: pytest.fail('Nominal execution'))
    assert wrapper.main(['--plan-only']) == 0
    assert seen == ['report']
    assert last_json(capsys)['extensions']['validation']['payloads_opened'] is False


@pytest.mark.parametrize('args', [['--through', 't2'], ['--run-name', '../bad']])
def test_invalid_arguments_fail_before_any_stage(wrapper, monkeypatch, capsys, args):
    calls = fake_stages(wrapper, monkeypatch)
    assert wrapper.main(args) == 3
    assert calls == []


def test_synthetic_source_forwarded_in_plan(wrapper, capsys):
    assert wrapper.main(['--plan-only', '--synthetic-events', 'fixture.json', '--continue']) == 0
    value = last_json(capsys)
    assert value['commands'][0][-3:] == ['--synthetic-events', 'fixture.json', '--continue']
    assert value['nominal']['commands'] == value['commands'][:5]
