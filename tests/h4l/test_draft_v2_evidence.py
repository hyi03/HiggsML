"""Synthetic aggregate-only reporting tests; no MC access or new inference."""
from copy import deepcopy
import csv

from higgsml.draft_v2 import validation_evidence as diagnostics
from higgsml.draft_v2 import validation_reporting as reporting
from higgsml.draft_v2.validation_protocol import KEYS, MODES, units, EXPECTED
from higgsml.draft_v2.validation_thresholds import threshold_diagnostics


def fixture():
    nominal = {}
    for key in KEYS:
        bins = 1 if key == 'inclusive' else 2
        samples = [dict(name=name, is_signal=signal, group_count=[140]*bins, neff_signed=[100.]*bins,
            rho=[.8]*bins, variance=[4.]*bins, bin_status=['valid']*bins,
            **{'yield': [20.]*bins}) for name, signal in [('background', False), ('signal', True)]]
        nominal[key] = dict(status='valid', interval=dict(status='valid', width=2.),
            template=dict(status='valid', samples=samples, categories=list(range(bins)), mass_edges=[105., 140.],
                          active_bins=list(range(bins)), issues=[]))
    models = {key: dict(threshold=.5) for key in KEYS if key != 'inclusive'}
    replicas = {i: dict(thresholds={key: .5 for key in models},
        results={mode: deepcopy(nominal) for mode in MODES}) for i in range(200)}
    evidence = {name: dict(status='complete' if spec['stage'] == 'bootstrap' else 'missing')
                for name, spec in units().items()}
    return nominal, models, replicas, evidence


def test_nominal_moments_are_copied_without_reweighting_or_half_sample_estimates():
    nominal, _, replicas, evidence = fixture()
    sample = nominal['ABCD:42']['template']['samples'][0]
    sample.update(group_count=[37, 103], neff_signed=[3.5, 51.25], rho=[.11, .75],
                  bin_status=['nonpositive_yield', 'valid'], **{'yield': [-.5, 17.]})
    before = deepcopy(nominal)
    result = diagnostics.sample_support(nominal, replicas, evidence)
    row = result['nominal'][0]
    assert len(result['nominal']) == 62
    assert (row['group_count'], row['neff_signed'], row['rho'], row['signed_yield']) == (37, 3.5, .11, -.5)
    assert row['bin_status'] == 'nonpositive_yield'
    assert result['nominal'][1]['neff_signed'] == 51.25
    assert before == nominal and 'No two-fold support estimate' in result['interpretation']
    sample['neff_signed'][0] = None
    assert diagnostics.sample_support(nominal, {}, {u: {'status': 'missing'} for u in units()})['nominal'][0]['neff_signed'] is None


def test_failure_phases_missing_and_corrupt_are_distinct():
    nominal, _, replicas, evidence = fixture()
    key, mode = 'ABCD:42', 'refitted-threshold'
    bad = replicas[0]['results'][mode][key]
    bad['status'] = bad['template']['status'] = 'insufficient_statistics'
    bad['template']['samples'][0]['neff_signed'][0] = 2.
    bad['template']['issues'] = [dict(process='background', bin=i, status=reason)
        for i, reason in [(0, 'nonpositive_yield'), (1, 'nonpositive_yield'), (1, 'strong_cancellation')]]
    replicas[1]['results'][mode][key]['status'] = 'template_stat_model_unvalidated'
    replicas[2]['thresholds'][key] = None
    replicas[2]['results'][mode][key] = dict(status='insufficient_statistics')
    replicas[3]['results'][mode][key]['status'] = 'fit_failed'
    replicas[4]['results'][mode][key]['status'] = 'interval_unbounded'
    for i, status in [(198, 'missing'), (199, 'corrupt')]:
        del replicas[i]
        evidence[f'bootstrap-{i:04d}']['status'] = status
    result = diagnostics.sample_support(nominal, replicas, evidence)
    row = next(r for r in result['bootstrap'] if r['mode'] == mode and r['key'] == key)
    assert row['completed_replicas'] == 198 and row['valid_interval_replicas'] == 193
    assert row['missing_replicas'] == row['corrupt_replicas'] == row['threshold_estimation_failures'] == 1
    assert row['support_assessed_replicas'] == 197 and row['support_passed_replicas'] == 195
    assert row['support_failures'] == row['interval_failures_after_support'] == 2
    assert row['observed_min_neff_signed'] == 2 and row['support_failure_rate'] is None
    assert row['failure_reason_replica_counts']['template_support:nonpositive_yield'] == 1
    assert not any(r['replica'] in {198, 199} for r in result['failure_details'])
    assert {r['phase'] for r in result['failure_details']} == {'threshold_estimation', 'template_support', 'interval_inference'}


def test_failure_rates_need_complete_budget_and_known_support():
    nominal, _, replicas, evidence = fixture()
    key, mode = 'ABCD:42', MODES[0]
    replicas[0]['results'][mode][key] = dict(status='insufficient_statistics', reason='Missing process')
    row = diagnostics.sample_support(nominal, replicas, evidence)['bootstrap'][0]
    assert row['support_failures'] == 1 and row['support_failure_rate'] == 1/200
    assert row['available_template_replicas'] == 199 and row['support_assessed_replicas'] == 200
    replicas[1]['results'][mode][key] = dict(status='fit_failed')
    row = diagnostics.sample_support(nominal, replicas, evidence)['bootstrap'][0]
    assert row['support_unavailable_replicas'] == 1 and row['support_failure_rate'] is None


def test_scope_complete_core_does_not_promote_optional_evidence():
    nominal, models, replicas, evidence = fixture()
    toys = {u: dict(summary=dict(valid_fits=500)) for u in units('model-self')}
    for u in toys:
        evidence[u]['status'] = 'complete'
    rows = threshold_diagnostics(replicas, nominal, models)
    scope = diagnostics.evidence_scope(evidence, replicas, toys, rows)
    assert all(r['execution_status'] == r['numerical_status'] == 'complete' for r in scope['covered'].values())
    assert scope['assessment']['independent_reference_coverage'] == 'unvalidated'
    assert scope['t2']['execution_status'] == 'not_assessed_by_this_report'
    assert not scope['assessment']['required_for_core_completion'] and not scope['t2']['required_for_core_completion']
    toys[next(iter(toys))]['summary']['valid_fits'] = 499
    scope = diagnostics.evidence_scope(evidence, replicas, toys, rows)
    assert scope['covered']['model-self']['execution_status'] == 'complete'
    assert scope['covered']['model-self']['numerical_status'] == 'incomplete'
    assert scope['covered']['model-self']['valid_results'] == 23999


def test_collector_uses_only_verified_aggregate_inventory(monkeypatch):
    nominal, models, replicas, _ = fixture()
    # Existing T2 units are deliberately outside this inventory's namespace.
    calls = []
    class Loaded:
        path = 'synthetic-unit'
        manifest = {'artifact_id': 'synthetic-bound-artifact'}
    def inventory(root, protocol, registration, unit, registered):
        calls.append(unit)
        if unit == 'bootstrap-0000':
            value = replicas[0]
            value['contrasts'] = {mode: reporting.summarize(nominal)['contrasts'] for mode in MODES}
            return (Loaded(), value), []
        return None, [dict(reason='synthetic corrupt unit')] if unit == 'bootstrap-0001' else []
    monkeypatch.setattr(reporting, 'inventory', inventory)
    summary, _ = reporting.collect('unused', EXPECTED, None,
        dict(registration_id='synthetic', source={'source_kind': 'synthetic'}), nominal, models)
    assert calls == list(units()) and summary['execution_status'] == 'incomplete'
    row = summary['sample_support']['bootstrap'][0]
    assert row['completed_replicas'] == 1 and row['corrupt_replicas'] == 1 and row['missing_replicas'] == 198
    scope = summary['evidence_scope']['covered']['fixed-threshold']
    assert scope['valid_results'] == 16 and scope['planned_results'] == 3200


def test_support_csv_preserves_missing_numbers_and_failure_reasons(tmp_path):
    nominal, models, replicas, evidence = fixture()
    nominal['ABCD:42']['template']['samples'][0]['rho'][0] = None
    replicas[0]['results'][MODES[0]]['ABCD:42']['status'] = 'interval_unbounded'
    evidence['bootstrap-0199']['status'] = 'missing'
    del replicas[199]
    support = diagnostics.sample_support(nominal, replicas, evidence)
    for name, columns, rows in diagnostics.csv_tables(support):
        with (tmp_path/name).open('w', newline='') as output:
            writer = csv.writer(output, lineterminator='\n')
            writer.writerow(columns)
            writer.writerows(rows)
    with (tmp_path/'nominal-support.csv').open() as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 62 and rows[0]['rho'] == '' and rows[0]['group_count'] == '140'
    with (tmp_path/'bootstrap-support-summary.csv').open() as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 32 and all(r['support_failure_rate'] == '' for r in rows)
    with (tmp_path/'bootstrap-support-failures.csv').open() as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 1 and rows[0]['reason_code'] == 'interval_unbounded'
    scope = diagnostics.evidence_scope(evidence, replicas, {}, threshold_diagnostics(replicas, nominal, models))
    markdown = diagnostics.evidence_markdown(scope, support)
    assert 'Assessment Toys are not evaluated' in markdown and 'T2 is available as a separate workflow' in markdown
    assert 'Missing / corrupt' in markdown and 'unavailable' in markdown
