"""Synthetic supplemental software tests; never open controlled-MC payload."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
from time import perf_counter

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import brentq
from scipy.stats import chi2

from higgsml.artifacts import LoadedRun, digest_json, read_json
from higgsml.draft_v2 import data, workflow
from higgsml.draft_v2 import validation_registry as registry
from higgsml.draft_v2 import validation_execution as execution
from higgsml.draft_v2 import validation_reporting as reporting
from higgsml.draft_v2 import validation_statistics as stats
from higgsml.draft_v2.validation_protocol import EXPECTED, MODES, KEYS, units, stream, load_protocol, DEFAULT_PROTOCOL
from higgsml.errors import ResearchError
from higgsml.inference.statistics import GroupBinStatistics
from higgsml.inference.likelihood import build_model, profile_interval
from higgsml.inference.stress import auxiliary_sampler
from higgsml.resources import ordered_map
from test_draft_v2 import frozen_base, protocol, synthetic_frame


@pytest.fixture(scope='module')
def source_base(frozen_base, protocol):
    root, _, review, _, _ = frozen_base
    with execution.numeric_threads():
        workflow.evaluate(root, protocol, access_review=review)
    workflow.report(root, protocol)
    return root


@pytest.fixture
def source(source_base, tmp_path):
    root = tmp_path/'nominal'
    shutil.copytree(source_base, root)
    return root


def approve(root, registration, tmp_path):
    value = registry.access_template(root, registration)
    value.update(status='approved', decision='allow_exploratory_supplement',
                 reviewed_by='synthetic software test', reviewed_at='synthetic test only')
    path = tmp_path/'review.json'
    path.write_text(json.dumps(value))
    return path


def test_fixed_contract_streams():
    assert load_protocol(DEFAULT_PROTOCOL) == EXPECTED
    assert len(units('bootstrap')) == 200 and len(units('model-self')) == 48
    assert len(KEYS) == 16
    changed = deepcopy(EXPECTED)
    changed['toys']['count'] = 2
    with pytest.raises(ResearchError):
        registry.validate_protocol(changed)
    a, a_seal = stats.draw('freeze', 'evaluation', 3, 100)
    b, b_seal = stats.draw('freeze', 'validation', 3, 100)
    assert a.sum() == 100 and b.sum() == 100
    assert a_seal != b_seal and not np.array_equal(a, b)
    np.testing.assert_array_equal(a, stats.draw('freeze', 'evaluation', 3, 100)[0])
    assert stream('f', 42, 'model-self', 'ABCD:42', 0, 0)[1] != stream('f', 42, 'model-self', 'BCD:42', 0, 0)[1]


def test_multiplicity_moments_match_explicit_group_copies():
    codes = np.array([0, 0, 0, 1, 2, 2, 3, 3])
    bins = np.array([0, 0, 1, 0, 0, 1, 1, 1])
    weights = np.array([2., -2., 3., -1., 7., -.5, 2., -2.])
    multiplicity = np.array([3, 0, 2, 1])
    optimized = stats.GroupMoments(codes, bins, weights, 4, 2).weighted(multiplicity).moments()
    groups, copied_bins, copied_weights = [], [], []
    for g, count in enumerate(multiplicity):
        for copy in range(count):
            indices = np.flatnonzero(codes == g)
            groups.extend([f'{g}-{copy}']*len(indices))
            copied_bins.extend(bins[indices])
            copied_weights.extend(weights[indices])
    reference = GroupBinStatistics(groups, copied_bins, copied_weights, 2).moments()
    for left, right in zip(optimized, reference):
        np.testing.assert_allclose(left, right, atol=1e-12, rtol=1e-12)
    assert optimized[1][0, 1] != 0
    wrong = stats.GroupMoments(codes, bins, weights*multiplicity[codes], 4, 2).weighted(np.ones(4)).moments()
    assert not np.allclose(wrong[1], optimized[1])
    with pytest.raises(ResearchError):
        stats.GroupMoments(codes, bins, weights, 4, 2).weighted([1, -1, 0, 1])


def test_median_ties_and_zero_multiplicity():
    scores = np.array([.2, .4, .4, .9], dtype=np.float32)
    cache = stats.MedianCache.create(scores, [-1, 2, 1, 1], [0, 1, 2, 3])
    assert cache.threshold([0, 1, 1, 0]) == float(scores[1])
    accepted = scores >= cache.threshold([1, 1, 1, 1])
    assert accepted.tolist() == [False, True, True, True]
    from higgsml.draft_v2.training import weighted_median
    assert cache.threshold([2, 0, 3, 1]) == weighted_median(np.repeat(scores, [2, 0, 3, 1]), np.repeat([1, 2, 1, 1], [2, 0, 3, 1]))
    with pytest.raises(ResearchError):
        cache.threshold([0, 0, 0, 0])


def interval(width, muhat=1.):
    return dict(status='valid', lower=0., upper=width, width=width, muhat=muhat,
                confidence=.68, lower_at_boundary=True)


def test_differences_then_median_and_incomplete_percentiles():
    nominal = {k: dict(status='valid', interval=interval(1.)) for k in KEYS}
    for key, width in zip(['ABCD:42', 'ABCD:43', 'ABCD:44', 'BCD:42', 'BCD:43', 'BCD:44'], [1, 10, 11, 9, 10, 12]):
        nominal[key]['interval'] = interval(width)
    contrasts = workflow.summarize(nominal)['contrasts']
    assert contrasts[0]['median_difference'] == 1
    replicas = {i: dict(contrasts={mode: contrasts for mode in MODES}) for i in range(200)}
    summary = reporting.summarize_bootstrap(replicas, nominal)
    assert summary[0]['percentile_16_84'] == [1., 1.]
    del replicas[199]
    assert reporting.summarize_bootstrap(replicas, nominal)[0]['percentile_16_84'] is None
    replicas[199] = dict(contrasts={mode: deepcopy(contrasts) for mode in MODES})
    replicas[199]['contrasts'][MODES[0]][0]['median_difference'] = None
    assert reporting.summarize_bootstrap(replicas, nominal)[0]['valid'] == 199


def test_coverage_failure_denominators():
    rows = [interval(2), dict(status='fit_failed'), dict(status='interval_unbounded', upper=None), interval(.5)]
    summary = stats.toy_summary(rows, 1)
    assert summary['budget'] == 4 and summary['valid_fits'] == 2
    assert summary['success_and_coverage_fraction'] == .25
    assert summary['conditional_coverage'] == .5 and summary['coverage'] is None
    assert summary['fit_failure_rate'] == .25 and summary['missing_upper_rate'] == .25
    np.testing.assert_allclose(summary['wilson_interval_success_and_coverage'], [.04558726, .69935816], atol=1e-7)


def test_poisson_reference_and_zero_boundary():
    import pyhf
    model = pyhf.Model({'channels': [{'name': 'count', 'samples': [
        {'name': 's', 'data': [2.], 'modifiers': [{'name': 'mu', 'type': 'normfactor', 'data': None}]},
        {'name': 'b', 'data': [1.], 'modifiers': []}]}],
        'parameters': [{'name': 'mu', 'bounds': [[0., 20.]], 'inits': [1.]}]})
    for count in (0., 1., 4., 8.):
        value = profile_interval(model, [count], confidence=.68)
        muhat = max(0., (count-1)/2)
        minimum = 2*muhat+1
        def q(mu):
            mean = 2*mu+1
            return 2*(mean-minimum-(count*np.log(mean/minimum) if count else 0))-chi2.ppf(.68, 1)
        upper = brentq(q, muhat, 20.)
        lower = 0. if q(0) <= 0 else brentq(q, 0, muhat)
        assert value['status'] == 'valid'
        np.testing.assert_allclose([value['lower'], value['upper']], [lower, upper], atol=1e-5)
    assert profile_interval(model, [0.])['lower_at_boundary']
    assert profile_interval(model, [100.])['status'] == 'interval_unbounded'


def template(protocol):
    frame = data.assign_roles(synthetic_frame(4000), protocol)
    evaluation = frame.loc[frame.role == 'evaluation'].assign(category=0)
    return workflow._infer(evaluation, protocol, 'inclusive', 'synthetic-freeze', inclusive=True)['template']


def test_toy_generation_main_and_auxiliary_moments(protocol):
    model, _ = build_model(template(protocol), layer='T1', t1_validation=workflow._t1_contract(protocol))
    pars = model.config.suggested_init()
    expected = np.asarray(model.expected_data(pars))
    sampler = auxiliary_sampler(model, pars)
    samples = np.asarray([stats.toy_observation(model, expected, sampler, 'f', 'inclusive', 1, i)[0] for i in range(12000)])
    np.testing.assert_allclose(samples.mean(axis=0), expected, atol=.5, rtol=.02)
    np.testing.assert_allclose(samples.var(axis=0), expected, atol=.6, rtol=.05)


def test_parallel_cell_equivalence(protocol):
    value = template(protocol)
    def fit(mu):
        return stats.model_self_cell(value, protocol, 'synthetic-freeze', 'inclusive', mu, count=3)
    with execution.numeric_threads():
        serial = list(ordered_map(fit, [0, 1], workers=1))
        parallel = list(ordered_map(fit, [0, 1], workers=2))
    for a, b in zip(serial, parallel):
        for left, right in zip(a['results'], b['results']):
            assert left['stream'] == right['stream'] and left['observation'] == right['observation']
            assert left['interval']['status'] == right['interval']['status']
            if left['interval']['status'] == 'valid':
                np.testing.assert_allclose(left['interval']['width'], right['interval']['width'], atol=1e-7, rtol=1e-7)


def forbid_events(monkeypatch):
    original = LoadedRun.file
    def guarded(self, name):
        assert name != 'events.jsonl', 'unexpected event hashing/opening'
        return original(self, name)
    monkeypatch.setattr(LoadedRun, 'file', guarded)
    monkeypatch.setattr(data, 'read_events', lambda *a, **k: pytest.fail('event payload opened'))


def test_plan_registration_and_source_bindings(source, tmp_path, monkeypatch):
    forbid_events(monkeypatch)
    root = tmp_path/'supplement'
    planned = registry.plan(source, root, EXPECTED)
    assert not root.exists() and planned['payloads_opened'] is False
    registered = registry.register(source, root, EXPECTED)
    assert registered.read_json('registration.json')['budget']['model_self_fits'] == 24000
    assert registry.register(source, root, EXPECTED, continuation=True).manifest == registered.manifest
    registry.bound_registration(source, root, EXPECTED)
    model_path = source/'train/ABCD-42/model.json'
    model_path.write_text('{}')
    with pytest.raises(ResearchError):
        registry.bound_registration(source, root, EXPECTED)


def test_stale_access_denied_before_payload(source, tmp_path, monkeypatch):
    root = tmp_path/'supplement'
    registered = registry.register(source, root, EXPECTED)
    registration = registered.read_json('registration.json')
    review = approve(root, registration, tmp_path)
    value = read_json(review)
    value['budget']['paired_replicas'] = 1
    review.write_text(json.dumps(value))
    forbid_events(monkeypatch)
    with pytest.raises(ResearchError, match='incorrectly bound'):
        execution.execute(source, root, EXPECTED, 'bootstrap', unit='bootstrap-0000', access_review=review, progress=False)
    assert not (root/'claims').exists()


def test_bootstrap_cache_pairing_support_and_recovery(source, tmp_path, monkeypatch, protocol):
    from higgsml.artifacts import sha256_file
    snapshot = {str(p.relative_to(source)): sha256_file(p) for p in source.rglob('*') if p.is_file()}
    root = tmp_path/'supplement'
    registered = registry.register(source, root, EXPECTED)
    registration = registered.read_json('registration.json')
    review = approve(root, registration, tmp_path)
    calls = []
    original = stats.training.predict
    def predict(*args):
        calls.append(args[0]['model_id'])
        return original(*args)
    monkeypatch.setattr(stats.training, 'predict', predict)
    result = execution.execute(source, root, EXPECTED, 'bootstrap', unit='bootstrap-0000', access_review=review, progress=False)
    assert len(calls) == 30
    loaded, value = execution.inventory(root, EXPECTED, registration, 'bootstrap-0000', registered)[0]
    assert value['results'][MODES[0]]['inclusive'] == value['results'][MODES[1]]['inclusive']
    assert value['cache_identity']['model_ids'] == registration['source']['model_ids']
    original_result = deepcopy(value)
    result_file = loaded.path/'result.json'
    before = result_file.read_bytes()
    reused = execution.execute(source, root, EXPECTED, 'bootstrap', unit='bootstrap-0000', continuation=True, progress=False)
    assert reused['new_units'] == [] and result_file.read_bytes() == before
    with pytest.raises(ResearchError, match='cannot be replaced'):
        execution.execute(source, root, EXPECTED, 'bootstrap', unit='bootstrap-0000', retry_failed=True, progress=False)
    result_file.write_text('{}')
    with pytest.raises(ResearchError, match='interrupted or corrupt'):
        execution.execute(source, root, EXPECTED, 'bootstrap', unit='bootstrap-0000', continuation=True, progress=False)
    execution.execute(source, root, EXPECTED, 'bootstrap', unit='bootstrap-0000', retry_failed=True, access_review=review, progress=False)
    recovered, invalid = execution.inventory(root, EXPECTED, registration, 'bootstrap-0000', registered)
    assert invalid and result_file.read_text() == '{}'
    original_result.pop('timing')
    recovered[1].pop('timing')
    assert original_result == recovered[1]
    audit = registry.history(root, 'some-other-registration')
    assert any(m['claim'].get('binding', {}).get('stage') == 'draft-v2-validation-bootstrap' for m in audit['matches'])
    assert snapshot == {str(p.relative_to(source)): sha256_file(p) for p in source.rglob('*') if p.is_file()}


def test_model_self_no_payload_and_full_budget_terminal(source, tmp_path, monkeypatch):
    root = tmp_path/'supplement'
    registered = registry.register(source, root, EXPECTED)
    registration = registered.read_json('registration.json')
    forbid_events(monkeypatch)
    # An injected numerical optimizer failure tests all 500 denominator slots,
    # without presenting this software fixture as a successful coverage run.
    monkeypatch.setattr(stats, 'profile_interval', lambda *a, **k: {'status': 'fit_failed', 'confidence': .68})
    execution.execute(source, root, EXPECTED, 'model-self', unit='model-self-inclusive-mu0', progress=False)
    terminal, invalid = execution.inventory(root, EXPECTED, registration, 'model-self-inclusive-mu0', registered)
    assert not invalid and terminal[1]['summary']['budget'] == 500
    assert terminal[1]['summary']['success_and_coverage_fraction'] == 0
    with pytest.raises(ResearchError, match='cannot be replaced'):
        execution.execute(source, root, EXPECTED, 'model-self', unit='model-self-inclusive-mu0', retry_failed=True, progress=False)
    changed = deepcopy(terminal[1])
    changed['results'].pop()
    with pytest.raises(ResearchError, match='budget'):
        execution.validate_result(changed, registration, 'model-self-inclusive-mu0')
    report = reporting.report(source, root, EXPECTED)
    summary = report.read_json('summary.json')
    assert summary['completed_units'] == 1 and summary['execution_status'] == 'incomplete'
    import csv
    with report.file('coverage.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 48 and sum(r['execution_status'] == 'missing' for r in rows) == 47
    assert all(r['budget'] == '500' for r in rows)
    assert all(r['percentile_16_84'] is None for r in summary['contrasts'])
    assert summary['qualification']['selection_aware_coverage'] == 'unvalidated'
    assert reporting.report(source, root, EXPECTED, continuation=True).manifest == report.manifest


def test_cross_category_covariance_is_not_dropped(protocol):
    n = 80
    frame = pd.DataFrame(dict(dataset=['atlas2020_4lep']*(2*n), label=np.repeat([0, 1], n),
        role='evaluation', event_group_id=[f'{label}-{i//2}' for label in (0, 1) for i in range(n)],
        yield_weight=.1, m4l=120.))
    groups, codes = stats.group_index(frame)
    categories = np.tile([0, 1], n)
    moments = stats.process_moments(frame, codes, categories, len(groups), 2)
    value, _, _ = stats.infer_moments(frame, categories, moments, np.ones(len(groups)), protocol, 'ABCD:42', 'f')
    assert value['status'] == 'template_stat_model_unvalidated'


def test_bootstrap_parallel_draws_and_shared_reference(protocol, monkeypatch):
    frame = data.assign_roles(synthetic_frame(4000), protocol)
    validation = frame.loc[frame.role == 'validation']
    evaluation = frame.loc[frame.role == 'evaluation']
    models = {k: dict(model_id='model-'+k, threshold=.5) for k in KEYS if k != 'inclusive'}
    def synthetic_prediction(model, rows, contract):
        return (np.arange(len(rows)) % 7 / 7).astype(np.float32)
    monkeypatch.setattr(stats.training, 'predict', synthetic_prediction)
    cache = stats.build_cache(validation, evaluation, models, protocol, 'f', 'p')
    # The same snapshot is transported to workers; no inference in subprocesses.
    def replica(i):
        return stats.bootstrap_replica(cache, models, protocol, i)
    with execution.numeric_threads():
        serial = list(ordered_map(replica, [0, 1], workers=1))
        parallel = list(ordered_map(replica, [0, 1], workers=2))
    for a, b in zip(serial, parallel):
        assert a['draws'] == b['draws'] and a['thresholds'] == b['thresholds']
        for mode in MODES:
            for key in KEYS:
                left, right = a['results'][mode][key], b['results'][mode][key]
                assert left['status'] == right['status']
                if left['status'] == 'valid':
                    np.testing.assert_allclose(left['interval']['width'], right['interval']['width'], atol=1e-7, rtol=1e-7)
    original = stats.infer_moments
    calls = []
    def counted(*args):
        calls.append(args[5])
        return original(*args)
    monkeypatch.setattr(stats, 'infer_moments', counted)
    with execution.numeric_threads():
        replica(2)
    assert len(calls) == 31 and calls.count('inclusive') == 1


def test_interruption_claim_and_resume_budget(source, tmp_path, monkeypatch):
    root = tmp_path/'supplement'
    registered = registry.register(source, root, EXPECTED)
    registration = registered.read_json('registration.json')
    name = 'model-self-inclusive-mu1'
    original = execution.model_self_cell
    def interrupted(*args, **kwargs):
        raise RuntimeError('synthetic injected worker interruption')
    monkeypatch.setattr(execution, 'model_self_cell', interrupted)
    with pytest.raises(RuntimeError, match='interruption'):
        execution.execute(source, root, EXPECTED, 'model-self', unit=name, progress=False)
    claim = (root/'claims'/(name+'.json')).read_bytes()
    with pytest.raises(ResearchError, match='explicit|interrupted'):
        execution.execute(source, root, EXPECTED, 'model-self', unit=name, continuation=True, progress=False)
    monkeypatch.setattr(execution, 'model_self_cell', original)
    monkeypatch.setattr(stats, 'profile_interval', lambda *a, **kw: {'status': 'fit_failed', 'confidence': .68})
    execution.execute(source, root, EXPECTED, 'model-self', unit=name, retry_failed=True, progress=False)
    terminal, invalid = execution.inventory(root, EXPECTED, registration, name, registered)
    assert terminal[1]['count'] == 500 and not invalid
    assert (root/'claims'/(name+'.json')).read_bytes() == claim
    assert '-retry-' in terminal[0].path.name
    for row in terminal[1]['results']:
        assert row['stream'] == stream(registration['source']['freeze_id'], 42, 'model-self', 'inclusive', 1, row['toy'])[1]


def test_cross_registration_and_missing_model_are_detected(source, tmp_path, monkeypatch):
    left, right = tmp_path/'left', tmp_path/'right'
    l = registry.register(source, left, EXPECTED)
    r = registry.register(source, right, EXPECTED)
    monkeypatch.setattr(stats, 'profile_interval', lambda *a, **kw: {'status': 'fit_failed', 'confidence': .68})
    unit = 'model-self-inclusive-mu2'
    execution.execute(source, left, EXPECTED, 'model-self', unit=unit, progress=False)
    shutil.copytree(left/'units', right/'units')
    shutil.copytree(left/'claims', right/'claims')
    registration = r.read_json('registration.json')
    terminal, invalid = execution.inventory(right, EXPECTED, registration, unit, r)
    assert terminal is None and invalid
    source_bundle = registry.load_source(source)
    summary, ids = reporting.collect(right, EXPECTED, r, registration, source_bundle['nominal'], source_bundle['models'])
    assert not ids and summary['evidence'][unit]['status'] == 'corrupt'
    shutil.rmtree(source/'train/ABCD-42')
    with pytest.raises(ResearchError):
        registry.bound_registration(source, left, EXPECTED)


def test_supplemental_schema_and_pending_example():
    from jsonschema import Draft202012Validator
    root = Path(__file__).resolve().parents[2]
    Draft202012Validator(read_json(root/'config/schemas/h4l_draft_v2_validation_v1.schema.json')).validate(EXPECTED)
    example = read_json(root/'config/examples/h4l_draft_v2_validation_access.pending.json')
    Draft202012Validator(read_json(root/'config/schemas/h4l_draft_v2_validation_access.schema.json')).validate(example)
    assert example['status'] == 'pending'
