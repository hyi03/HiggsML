"""Synthetic nested T2 software tests; no controlled-MC supplemental runs."""
from copy import deepcopy
import csv
import json
from pathlib import Path

import numpy as np
import pytest

from higgsml.artifacts import LoadedRun, digest_json, read_json, sha256_file
from higgsml.errors import ResearchError
from higgsml.resources import ordered_map
from higgsml.draft_v2 import data, t2_statistics as statistics, t2_workflow as workflow, t2_reporting as reporting
from higgsml.draft_v2.t2_protocol import EXPECTED, DEFAULT_PROTOCOL, KEYS, fold_for_group, units, outer_draw, stream, load_protocol
from higgsml.draft_v2.validation_execution import numeric_threads
from higgsml.draft_v2.validation_statistics import toy_summary
from test_draft_v2 import synthetic_frame, frozen_base, protocol
from test_draft_v2_validation import source_base, source, forbid_events


@pytest.fixture
def synthetic_preflight(monkeypatch, protocol):
    frame = data.assign_roles(synthetic_frame(6000), protocol)
    models = {key: dict(model_id='synthetic-'+key, threshold=.5) for key in KEYS if key != 'inclusive'}
    calls = []
    def predict(model, population, protocol):
        calls.append(model['model_id'])
        return np.linspace(.05, .95, len(population), dtype=np.float32)
    monkeypatch.setattr(statistics.build_cache.__globals__['training'], 'predict', predict)
    value = statistics.prepare_cells(frame.loc[frame.role == 'validation'], frame.loc[frame.role == 'evaluation'],
                                     models, protocol, 'synthetic-freeze', 'synthetic-population')
    value['preflight_id'] = workflow.scientific_preflight_id(value)
    registration = dict(source=dict(freeze_id='synthetic-freeze', population_id='synthetic-population',
                                   model_ids={key: model['model_id'] for key, model in models.items()}))
    return value, frame, models, calls, registration


def approve(root, registered, tmp_path):
    value = workflow.access_template(root, registered.read_json('registration.json'))
    value.update(status='approved', decision='allow_exploratory_t2', reviewed_by='synthetic test only', reviewed_at='synthetic test')
    path = tmp_path/'t2-review.json'
    path.write_text(json.dumps(value))
    return path


def test_t2_contract_and_stream_isolation():
    assert load_protocol() == EXPECTED and len(units()) == 640
    assert sum(s['count'] for s in units().values()) == 64000
    changed = deepcopy(EXPECTED)
    changed['outer']['count'] = 2
    with pytest.raises(ResearchError):
        workflow.validate_protocol(changed)
    groups = ['physical-'+str(i) for i in range(1000)]
    assert {fold_for_group(g) for g in groups} == {0, 1}
    assert [fold_for_group(g) for g in groups] == list(reversed([fold_for_group(g) for g in reversed(groups)]))
    counts, identity = outer_draw('freeze', 0, 1000)
    assert counts.sum() == 1000 and identity['total'] == 1000
    assert stream('freeze', 'main', 'ABCD:42', 0, 0, 1, 0)[1] != stream('freeze', 'main', 'ABCD:42', 1, 0, 1, 0)[1]
    assert stream('freeze', 'main', 'ABCD:42', 0, 0, 1, 0)[1] != stream('freeze', 'auxiliary', 'ABCD:42', 0, 0, 1, 0)[1]
    assert stream('freeze', 'main', 'ABCD:42', 0, 0, 1, 0)[1] != stream('freeze', 'main', 'BCD:42', 0, 0, 1, 0)[1]


def test_fixed_parent_exchange_and_probability_normalization(synthetic_preflight):
    value, frame, models, calls, registration = synthetic_preflight
    workflow.validate_preflight(value, registration)
    assert len(calls) == 30 and value['generated_toys'] == 0
    assert all(model['threshold'] == .5 for model in models.values())
    evaluation = frame.loc[frame.role == 'evaluation']
    for fold in (0, 1):
        cell = value['cells'][f't2-inclusive-fold{fold}-outer00']
        parent = evaluation.loc[evaluation.event_group_id.map(fold_for_group) == fold]
        assert value['source_identity']['fold_parents'][str(fold)]['groups'] == parent.event_group_id.nunique()
        for sample in cell['fit_template']['samples']:
            expected = (parent.loc[parent.label == int(sample['name']), 'physical_weight']/.1).sum()
            np.testing.assert_allclose(sample['yield'][0], expected, rtol=1e-12)
        other = value['cells'][f't2-inclusive-fold{1-fold}-outer00']
        assert cell['fit_template'] == other['mother_template']
    for outer in range(20):
        a = value['cells'][f't2-ABCD-42-fold0-outer{outer:02d}']
        b = value['cells'][f't2-ABCD-42-fold1-outer{outer:02d}']
        assert a['mapping'] == b['mapping'] == value['thresholds'][str(outer)]['ABCD:42']
        assert a['fit_template'] == b['mother_template']
    assert len({value['thresholds'][str(i)]['ABCD:42']['threshold'] for i in range(20)}) > 1
    # The generating parent is not silently replaced by the fitted template.
    cell = value['cells']['t2-inclusive-fold0-outer00']
    assert cell['mother_rates'] != statistics._independent_rates(cell['fit_template'], 1)


def test_preflight_identity_and_budget_tamper(synthetic_preflight):
    value, _, _, _, registration = synthetic_preflight
    for transform in ('missing_cell', 'threshold', 'normalization', 'parent_exchange', 'false_failure', 'draw_population'):
        changed = deepcopy(value)
        if transform == 'missing_cell':
            changed['cells'].pop(next(iter(changed['cells'])))
        elif transform == 'threshold':
            changed['cells']['t2-ABCD-42-fold0-outer00']['mapping'] = dict(status='valid', threshold=.1)
        elif transform == 'normalization':
            changed['source_identity']['fold_parents']['0']['effective_sampling_probability'] = .2
        elif transform == 'parent_exchange':
            changed['cells']['t2-ABCD-42-fold0-outer00']['mother_template'] = changed['cells']['t2-ABCD-42-fold0-outer00']['fit_template']
        elif transform == 'false_failure':
            changed['cells']['t2-ABCD-42-fold0-outer00'].update(status='insufficient_statistics', failure_phase='mother')
        else:
            changed['draws']['1'] = outer_draw('synthetic-freeze', 1, changed['draws']['0']['groups']+1)[1]
        for cell in changed['cells'].values():
            cell['cell_id'] = digest_json({k: v for k, v in cell.items() if k != 'cell_id'})
        changed['preflight_id'] = workflow.scientific_preflight_id(changed)
        with pytest.raises(ResearchError):
            workflow.validate_preflight(changed, registration)


def test_unsupported_cell_retains_full_inner_budget(synthetic_preflight, protocol):
    value, _, _, _, _ = synthetic_preflight
    cell = deepcopy(value['cells']['t2-ABCD-42-fold0-outer00'])
    cell.update(status='insufficient_statistics', failure_phase='mother', reason='synthetic negative parent rate')
    result = statistics.fit_cell(cell, protocol, 'synthetic-freeze')
    assert result['count'] == 100 and len(result['results']) == 100 and result['generated_toys'] == 0
    assert result['summary']['failure_rate'] == 1 and result['summary']['conditional_coverage'] is None
    assert result['summary']['success_and_coverage_fraction'] == 0
    assert all('observation' not in row and row['main_stream'] for row in result['results'])


def test_t2_serial_parallel_equivalence(synthetic_preflight, protocol):
    value, _, _, _, _ = synthetic_preflight
    cells = [value['cells'][f't2-inclusive-fold{fold}-outer00'] for fold in (0, 1)]
    def run(cell):
        return statistics.fit_cell(cell, protocol, 'synthetic-freeze', count=3)
    with numeric_threads():
        serial = list(ordered_map(run, cells, workers=1))
        parallel = list(ordered_map(run, cells, workers=2))
    for a, b in zip(serial, parallel):
        for left, right in zip(a['results'], b['results']):
            assert left['main_stream'] == right['main_stream'] and left['auxiliary_stream'] == right['auxiliary_stream']
            assert left['observation'] == right['observation']
            assert left['interval']['status'] == right['interval']['status']
            if left['interval']['status'] == 'valid':
                np.testing.assert_allclose(left['interval']['width'], right['interval']['width'], rtol=1e-7, atol=1e-7)


def test_t2_main_and_auxiliary_distributions(synthetic_preflight, protocol, monkeypatch):
    value, _, _, _, _ = synthetic_preflight
    cell = deepcopy(value['cells']['t2-ABCD-42-fold0-outer00'])
    # Deliberately distinct synthetic parent rates isolate the generator wiring.
    cell['mother_rates'] = [7., 13.]
    monkeypatch.setattr(statistics, 'profile_interval', lambda *a, **k: {'status': 'fit_failed', 'confidence': .68})
    result = statistics.fit_cell(cell, protocol, 'synthetic-freeze', count=3000)
    observed = np.asarray([r['observation'] for r in result['results']])
    model, _ = statistics.build_model(cell['fit_template'], layer='T1', t1_validation=statistics._t1_contract(protocol))
    parameters = model.config.suggested_init()
    parameters[model.config.poi_index] = 1.
    expected = np.r_[cell['mother_rates'], np.asarray(model.expected_data(parameters))[model.config.nmaindata:]]
    assert not np.allclose(expected[:2], model.expected_data(parameters)[:2])
    np.testing.assert_array_less(np.abs(observed.mean(axis=0)-expected), 6*np.sqrt(expected/len(observed)))
    np.testing.assert_array_less(np.abs(observed.var(axis=0)-expected), 6*np.sqrt((expected+2*expected**2)/len(observed)))


def test_outer_aggregation_is_not_pooled_inner_binomial():
    results = {}
    for name, spec in units().items():
        covered = 100 if spec['template_fold'] == spec['outer'] % 2 else 0
        results[name] = dict(summary=dict(valid_fits=100, covered=covered,
            diagnostics=dict(valid_fits=100, mean_width=2., bias_valid_fits=0.)))
    rows = reporting.aggregate(results)
    assert all(r['success_and_coverage_fraction'] == .5 and r['outer_cluster_standard_error'] == 0 for r in rows)
    assert all(r['planned_toys'] == 4000 and len(r['outer_replicas']) == 20 for r in rows)
    assert not any('wilson' in key for r in rows for key in r)
    results['t2-ABCD-42-fold0-outer00']['summary'].update(valid_fits=0, covered=0,
        diagnostics=dict(valid_fits=0, mean_width=None, bias_valid_fits=None))
    failed = reporting.aggregate(results)[0]
    assert failed['failure_rate'] == 100/4000 and failed['coverage'] is None
    assert failed['success_and_coverage_fraction'] == 1900/4000
    assert failed['conditional_coverage_valid_fits'] == 1900/3900
    del results['t2-ABCD-42-fold1-outer19']
    missing = reporting.aggregate(results)[0]
    assert missing['success_and_coverage_fraction'] is None and missing['outer_cluster_standard_error'] is None


def test_plan_registration_never_open_events(source, tmp_path, monkeypatch):
    root = tmp_path/'t2'
    forbid_events(monkeypatch)
    guarded_file = LoadedRun.file
    with monkeypatch.context() as metadata:
        def metadata_only(self, name):
            assert name not in {'events.jsonl', 'model.json', 'results.json', 'summary.json'}
            return guarded_file(self, name)
        metadata.setattr(LoadedRun, 'file', metadata_only)
        value = workflow.plan(source, root, EXPECTED)
    assert not root.exists() and value['payloads_opened'] is False
    assert value['registration']['budget']['planned_fits'] == 64000
    registered = workflow.register(source, root, EXPECTED)
    assert workflow.register(source, root, EXPECTED, continuation=True).manifest == registered.manifest
    with pytest.raises(ResearchError):
        workflow.prepare(source, root, EXPECTED, access_review=root/'register/access-review.pending.json')
    assert not (root/'claims/preflight.json').exists()
    review = approve(root, registered, tmp_path)
    history = tmp_path/'.h4l-draft-v2-t2-claims/other.json'
    history.parent.mkdir(exist_ok=True)
    history.write_text(json.dumps({'binding': {'population_id': 'previously-accessed-population'}}))
    with pytest.raises(ResearchError, match='stale'):
        workflow.prepare(source, root, EXPECTED, access_review=review)
    assert not (root/'claims/preflight.json').exists()


def test_public_preflight_units_recovery_and_report(source, tmp_path, monkeypatch):
    before = {str(p.relative_to(source)): sha256_file(p) for p in source.rglob('*') if p.is_file()}
    root = tmp_path/'t2'
    registered = workflow.register(source, root, EXPECTED)
    registration = registered.read_json('registration.json')
    review = approve(root, registered, tmp_path)
    original = LoadedRun.file
    original_reader = data.read_events
    def check_access(self, name):
        if name == 'events.jsonl':
            assert (root/'claims/preflight.json').exists()
            assert list((tmp_path/'.h4l-draft-v2-t2-claims').glob('*.json'))
        return original(self, name)
    monkeypatch.setattr(LoadedRun, 'file', check_access)
    preflight_run, prepared = workflow.prepare(source, root, EXPECTED, access_review=review)
    assert len(prepared['cells']) == 640 and prepared['generated_toys'] == 0
    assert prepared['cells']['t2-inclusive-fold0-outer00']['status'] == 'valid'
    claim = root/'claims/preflight.json'
    claim_bytes = claim.read_bytes()
    claim.unlink()
    assert workflow.find_preflight(root, EXPECTED, registration)[0] is None
    claim.write_bytes(claim_bytes)
    global_claim = Path(preflight_run.read_json('access.json')['claim']['path'])
    global_bytes = global_claim.read_bytes()
    global_claim.unlink()
    assert workflow.find_preflight(root, EXPECTED, registration)[0] is None
    global_claim.write_bytes(global_bytes)
    forbid_events(monkeypatch)
    monkeypatch.setattr(statistics, 'profile_interval', lambda *a, **k: {'status': 'fit_failed', 'confidence': .68})
    name = 't2-inclusive-fold0-outer00'
    workflow.execute(source, root, EXPECTED, unit=name, progress=False)
    terminal, invalid = workflow.inventory(root, EXPECTED, registered, registration, prepared, name)
    assert not invalid and terminal[1]['summary']['budget'] == 100
    original_result = deepcopy(terminal[1])
    assert workflow.execute(source, root, EXPECTED, unit=name, continuation=True, progress=False)['new_units'] == []
    with pytest.raises(ResearchError, match='cannot be replaced'):
        workflow.execute(source, root, EXPECTED, unit=name, retry_failed=True, progress=False)
    shortened = deepcopy(terminal[1]); shortened['results'].pop()
    with pytest.raises(ResearchError, match='budget'):
        workflow.validate_result(shortened, registration, prepared, name)
    path = terminal[0].path/'result.json'
    path.write_text('{}')
    with pytest.raises(ResearchError, match='Interrupted/corrupt'):
        workflow.execute(source, root, EXPECTED, unit=name, continuation=True, progress=False)
    workflow.execute(source, root, EXPECTED, unit=name, retry_failed=True, progress=False)
    recovered, invalid = workflow.inventory(root, EXPECTED, registered, registration, prepared, name)
    assert invalid and path.read_text() == '{}'
    original_result.pop('timing'); recovered[1].pop('timing')
    assert recovered[1] == original_result
    # Rebuild damaged preflight with the same scientific identity and reuse units.
    preflight_path = preflight_run.path/'preflight.json'
    preflight_path.write_text('{}')
    with pytest.raises(ResearchError, match='Interrupted/corrupt'):
        workflow.execute(source, root, EXPECTED, unit=name, continuation=True, progress=False)
    with monkeypatch.context() as recover:
        recover.setattr(LoadedRun, 'file', check_access)
        recover.setattr(data, 'read_events', original_reader)
        fresh_review = approve(root, registered, tmp_path)
        _, fresh_preflight = workflow.prepare(source, root, EXPECTED, unit='preflight', retry_failed=True,
                                               access_review=fresh_review)
    assert fresh_preflight['preflight_id'] == prepared['preflight_id'] and preflight_path.read_text() == '{}'
    assert workflow.execute(source, root, EXPECTED, unit=name, continuation=True, progress=False)['new_units'] == []
    report = reporting.report(source, root, EXPECTED)
    summary = report.read_json('summary.json')
    assert summary['completed_units'] == 1 and summary['execution_status'] == 'incomplete'
    assert summary['qualification']['independent'] is False
    with report.file('cells.csv').open() as output:
        rows = list(csv.DictReader(output))
    assert len(rows) == 640 and sum(r['execution_status'] == 'missing' for r in rows) == 639
    assert reporting.report(source, root, EXPECTED, continuation=True).manifest == report.manifest
    assert before == {str(p.relative_to(source)): sha256_file(p) for p in source.rglob('*') if p.is_file()}


def test_negative_and_correlated_mother_support(synthetic_preflight):
    value, _, _, _, _ = synthetic_preflight
    template = deepcopy(value['cells']['t2-ABCD-42-fold0-outer00']['mother_template'])
    template['samples'][0]['yield'][0] = -1
    with pytest.raises(ResearchError, match='Nonpositive'):
        statistics._independent_rates(template, 1)
    template = deepcopy(value['cells']['t2-ABCD-42-fold0-outer00']['mother_template'])
    template['samples'][0]['covariance'][0][1] = .1
    with pytest.raises(ResearchError, match='cross-category'):
        statistics._independent_rates(template, 1)


def test_t2_schema_and_pending_example():
    from jsonschema import Draft202012Validator
    root = Path(__file__).resolve().parents[2]
    Draft202012Validator(read_json(root/'config/schemas/h4l_draft_v2_t2_v1.schema.json')).validate(EXPECTED)
    pending = read_json(root/'config/examples/h4l_draft_v2_t2_access.pending.json')
    Draft202012Validator(read_json(root/'config/schemas/h4l_draft_v2_t2_access.schema.json')).validate(pending)
    assert pending['status'] == 'pending'
