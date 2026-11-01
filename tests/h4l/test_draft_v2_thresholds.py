"""Synthetic fixed-model threshold diagnostics; no controlled-MC execution."""
from copy import deepcopy
import csv

import numpy as np
import pandas as pd

from higgsml.draft_v2 import validation_statistics as statistics
from higgsml.draft_v2 import validation_reporting as reporting
from higgsml.draft_v2.protocol import load_protocol, DEFAULT_PROTOCOL
from higgsml.draft_v2.validation_protocol import KEYS, MODES, units
from higgsml.draft_v2.validation_thresholds import threshold_diagnostics, yield_difference


def result(background, signal, status='valid'):
    return dict(status=status, interval=dict(status='valid', width=2.), template=dict(samples=[
        dict(name='background', **{'yield': background}), dict(name='signal', **{'yield': signal})]))


def diagnostic_fixture():
    nominal = {key: result([20., 30.], [10., 20.]) for key in KEYS}
    models = {key: dict(threshold=.5) for key in KEYS if key != 'inclusive'}
    replicas = {i: dict(thresholds={key: (.4 if i % 2 else .6) for key in models}, results={
        'fixed-threshold': {key: result([23., 37.], [12., 24.]) for key in KEYS},
        'refitted-threshold': {key: result([19., 41.], [15., 21.]) for key in KEYS}}) for i in range(200)}
    return replicas, nominal, models


def test_threshold_changes_and_paired_signed_redistribution():
    replicas, nominal, models = diagnostic_fixture()
    before = deepcopy((replicas, nominal, models))
    rows = threshold_diagnostics(replicas, nominal, models)
    assert len(rows) == 15 and before == (replicas, nominal, models)
    value = rows[0]
    assert value['threshold_status'] == 'complete' and value['threshold_changed_fraction'] == 1
    assert value['higher_threshold_replicas'] == value['lower_threshold_replicas'] == 100
    assert value['median_threshold_delta'] == 0
    np.testing.assert_allclose(value['threshold_delta_percentile_2_5_16_84_97_5'], [-.1, -.1, .1, .1])
    observation = value['rows'][0]
    assert observation['category_yield_change']['background'] == [-1., 11.]
    assert observation['paired_category_yield_change']['background'] == [-4., 4.]
    assert observation['paired_category_yield_change']['signal'] == [3., -3.]
    assert all(sum(v) == 0 for v in observation['paired_category_yield_change'].values())
    assert value['paired_yield_available'] == 200


def test_unchanged_threshold_and_failures_not_silently_dropped():
    replicas, nominal, models = diagnostic_fixture()
    key = 'ABCD:42'
    replicas[0]['thresholds'][key] = .5
    replicas[0]['results']['refitted-threshold'][key] = deepcopy(replicas[0]['results']['fixed-threshold'][key])
    replicas[1]['results']['refitted-threshold'][key]['status'] = 'fit_failed'
    replicas[2]['results']['refitted-threshold'][key]['status'] = 'template_stat_model_unvalidated'
    value = threshold_diagnostics(replicas, nominal, models)[0]
    assert value['available'] == 200 and value['threshold_changed_fraction'] == 199/200
    assert value['support_failures'] == 1 and value['support_failure_rate'] == 1/200
    assert value['threshold_estimation_failures'] == 0
    assert value['rows'][0]['paired_category_yield_change']['background'] == [0., 0.]
    assert value['rows'][1]['paired_category_yield_change'] is not None
    assert value['rows'][2]['paired_category_yield_change'] is not None
    # A failed median is not an evaluated template-support failure.
    replicas[3]['thresholds'][key] = None
    replicas[3]['results']['refitted-threshold'][key] = dict(status='insufficient_statistics')
    value = threshold_diagnostics(replicas, nominal, models)[0]
    assert value['available'] == value['support_assessed_replicas'] == 199 and value['observed_replicas'] == 200
    assert value['threshold_estimation_failure_rate'] == 1/200
    assert value['support_failure_rate'] == 1/200
    assert value['rows'][3]['support_failed'] is None
    assert value['threshold_delta_percentile_2_5_16_84_97_5'] is None
    assert value['threshold_changed_fraction'] is None and value['median_threshold_delta'] is None
    del replicas[199]
    value = threshold_diagnostics(replicas, nominal, models)[0]
    assert value['support_failure_rate'] is None and value['threshold_estimation_failure_rate'] is None
    assert value['rows'][199]['status'] == 'missing' and value['rows'][199]['threshold_changed'] is None


def test_signed_yields_and_missing_template_are_retained():
    left, right = result([-.5, 5.5], [1., 3.]), result([1., 4.], [2., 2.])
    assert yield_difference(left, right)['background'] == [-1.5, 1.5]
    assert yield_difference(left, {'status': 'fit_failed'}) is None
    right['template']['samples'].pop()
    assert yield_difference(left, right) is None  # No partial-process success summary.


def test_bootstrap_reestimates_validation_only_without_model_mutation(monkeypatch):
    protocol = load_protocol(DEFAULT_PROTOCOL)
    validation = pd.DataFrame(dict(event_group_id=['v0', 'v1', 'v2', 'v3'], label=0,
        physical_weight=[-1., 1., 1., 1.], role='validation', score=[.1, .5, .5, .9]))
    evaluation = pd.DataFrame(dict(event_group_id=['e0', 'e1', 'e2', 'e3'], label=[0, 1, 0, 1],
        yield_weight=[1., 2., -.25, 1.], role='evaluation', score=[.1, .5, .9, .95],
        dataset='atlas2020_4lep', m4l=120.))
    models = {key: dict(threshold=.5, model_id='synthetic-'+key) for key in KEYS if key != 'inclusive'}
    before = deepcopy(models)
    monkeypatch.setattr(statistics.training, 'predict', lambda model, frame, protocol: frame.score.to_numpy(np.float32))
    cache = statistics.build_cache(validation, evaluation, models, protocol, 'synthetic-f', 'synthetic-p')
    calls = []
    def draw(freeze, role, replica, count):
        calls.append(role)
        return np.array([0, 0, 0, 4] if role == 'validation' else [1, 1, 1, 1]), 'synthetic-'+role
    monkeypatch.setattr(statistics, 'draw', draw)
    value = statistics.bootstrap_replica(cache, models, protocol, 0)
    assert models == before and calls == ['evaluation', 'validation']
    assert all(t == float(np.float32(.9)) for t in value['thresholds'].values())
    key = 'ABCD:42'
    refitted, fixed = (value['results'][mode][key] for mode in ('refitted-threshold', 'fixed-threshold'))
    # score == threshold remains high; the score .5 signal row moves low.
    difference = yield_difference(refitted, fixed)
    assert difference['1'] == [2., -2.]
    assert difference['0'] == [0., 0.]
    assert value['results'][MODES[0]]['inclusive'] == value['results'][MODES[1]]['inclusive']
    # Altering evaluation yields cannot alter validation-derived thresholds.
    evaluation['yield_weight'] *= 10
    other = statistics.build_cache(validation, evaluation, models, protocol, 'synthetic-f', 'synthetic-p')
    assert statistics.bootstrap_replica(other, models, protocol, 0)['thresholds'] == value['thresholds']
    monkeypatch.setattr(statistics, 'draw', lambda *args: (np.ones(4, int), 'synthetic-unchanged'))
    unchanged = statistics.bootstrap_replica(other, models, protocol, 0)
    assert unchanged['thresholds'][key] == models[key]['threshold']
    assert yield_difference(unchanged['results'][MODES[1]][key], unchanged['results'][MODES[0]][key]) == {'0': [0., 0.], '1': [0., 0.]}
    assert models == before


def test_threshold_csv_and_figures_include_missing_pairs(tmp_path):
    replicas, nominal, models = diagnostic_fixture()
    del replicas[199]
    summary = dict(source_kind='synthetic', execution_status='incomplete', numerical_status='incomplete',
        interpretation='Synthetic reporting fixture only; no statistical qualification.',
        contrasts=reporting.summarize_bootstrap({}, nominal), thresholds=threshold_diagnostics(replicas, nominal, models),
        model_self={}, evidence={unit: {'status': 'missing'} for unit in units()})
    class Export:
        path = tmp_path
        def register_file(self, name):
            assert (self.path/name).is_file()
    reporting.export(Export(), summary)
    with (tmp_path/'paired-category-yield-changes.csv').open() as output:
        rows = list(csv.DictReader(output))
    assert len(rows) == 15*200*2*2
    missing = [r for r in rows if r['replica'] == '199']
    assert len(missing) == 60 and all(r['signed_yield_change_same_evaluation_draw'] == '' for r in missing)
    assert all(r['refitted_status'] == 'missing' for r in missing)
    with (tmp_path/'threshold-summary.csv').open() as output:
        rows = list(csv.DictReader(output))
    assert len(rows) == 15 and all(r['threshold_status'] == 'incomplete' for r in rows)
    assert all(r['delta_q16'] == '' and r['threshold_changed_fraction'] == '' for r in rows)
    assert (tmp_path/'threshold-shifts.png').stat().st_size > 0
    assert (tmp_path/'threshold-shifts.pdf').stat().st_size > 0
