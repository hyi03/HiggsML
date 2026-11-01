"""Report-only evidence scope and support diagnostics from bound aggregates."""
from collections import Counter

from higgsml.draft_v2.validation_protocol import EXPECTED, KEYS, MODES, units
from higgsml.draft_v2.validation_thresholds import SUPPORT_FAILURES

REPLICAS = EXPECTED['bootstrap']['replicas']


def evidence_scope(evidence, replicas, toys, thresholds):
    """Describe this report's evidence, never infer the state of another run."""
    def stage(stage_name, valid, planned):
        names = units(stage_name)
        counts = Counter(evidence[name]['status'] for name in names)
        complete = counts['complete'] == len(names)
        return dict(execution_status='complete' if complete else 'incomplete',
            planned_units=len(names), completed_units=counts['complete'],
            missing_units=counts['missing'], corrupt_units=counts['corrupt'],
            numerical_status='complete' if complete and valid == planned else 'incomplete',
            valid_results=valid, planned_results=planned, required_for_core_completion=True)
    covered = {}
    for mode in MODES:
        valid = sum(value['results'][mode][key]['status'] == 'valid'
                    for value in replicas.values() for key in KEYS)
        covered[mode] = {**stage('bootstrap', valid, REPLICAS*len(KEYS)),
            'result_kind': 'paired_finite_mc_width_stability_conditional_on_fixed_checkpoints'}
    covered['threshold-diagnostics'] = {
        **stage('bootstrap', sum(row['available'] for row in thresholds), REPLICAS*(len(KEYS)-1)),
        'result_kind': 'threshold_estimates_including_downstream_support_or_fit_failures',
        'shares_units_with': 'paired bootstrap; no additional fits or draws'}
    covered['model-self'] = {
        **stage('model-self', sum(value['summary']['valid_fits'] for value in toys.values()),
                len(units('model-self'))*EXPECTED['toys']['count']),
        'result_kind': 'coverage_under_each_nominal_models_own_truth'}
    return dict(schema_version='h4l-draft-v2-evidence-scope-v1', covered=covered,
        assessment=dict(implementation_status='not_implemented_in_draft_v2',
            evidence_status='not_evaluated_in_this_workflow', independent_reference_coverage='unvalidated',
            required_for_core_completion=False,
            reason='Deferred: mother population and independence scope need a separate design.'),
        t2=dict(implementation_status='available_as_separate_workflow',
            evidence_status='not_included_in_this_report', execution_status='not_assessed_by_this_report',
            required_for_core_completion=False,
            reason='An explicitly bound T2 report is required; no sibling-run discovery or completion inference.'),
        interpretation='Core execution completion does not imply independent-reference or selection-aware coverage. '
            'A separately registered T2 run still requires every unit in its own budget. '
            'The two bootstrap modes share units and an inclusive reference; their result counts are not extra fits.')


def template_support_rows(value, key):
    """Copy stored process/bin moments, including unsupported and signed bins."""
    template = value.get('template', {})
    categories, edges = template.get('categories', []), template.get('mass_edges', [])
    n_mass = len(edges)-1
    rows = []
    if n_mass < 1:
        return rows
    for sample in template.get('samples', []):
        for b in range(len(categories)*n_mass):
            def item(field):
                values = sample.get(field, [])
                return values[b] if b < len(values) else None
            row = dict(key=key, process=sample['name'], is_signal=sample['is_signal'],
                category=categories[b//n_mass], mass_bin=b % n_mass, bin=b,
                mass_lower=edges[b % n_mass], mass_upper=edges[b % n_mass+1],
                result_status=value['status'], template_status=template['status'], bin_status=item('bin_status'),
                group_count=item('group_count'), signed_yield=item('yield'), variance=item('variance'),
                neff_signed=item('neff_signed'), rho=item('rho'))
            row['moments_available'] = all(row[k] is not None for k in ('group_count', 'signed_yield', 'variance'))
            rows.append(row)
    return rows


def sample_support(nominal, replicas, evidence):
    """Keep missing terminals, failed calibration, support and fit outcomes separate."""
    summaries, failures = [], []
    for mode in MODES:
        for key in KEYS:
            states, reasons = Counter(), Counter()
            assessed = passed = support_failed = threshold_failed = valid = fit_failed = available_templates = 0
            neff_values, rho_values = [], []
            for i in range(REPLICAS):
                execution = evidence[f'bootstrap-{i:04d}']['status']
                states[execution] += 1
                if execution != 'complete':
                    continue  # No invented scientific outcome for missing/corrupt artifacts.
                replica = replicas[i]
                result = replica['results'][mode][key]
                template = result.get('template', {})
                phase, issues = None, []
                if mode == 'refitted-threshold' and key != 'inclusive' and replica['thresholds'][key] is None:
                    threshold_failed += 1
                    phase = 'threshold_estimation'
                    issues = [dict(status='threshold_estimation_failed')]
                else:
                    rows = template_support_rows(result, key)
                    available_templates += bool(rows)
                    neff_values.extend(r['neff_signed'] for r in rows if r['neff_signed'] is not None)
                    rho_values.extend(r['rho'] for r in rows if r['rho'] is not None)
                    if result['status'] in SUPPORT_FAILURES or template.get('status') in SUPPORT_FAILURES:
                        assessed += 1
                        support_failed += 1
                        phase = 'template_support'
                        issues = template.get('issues', []) or [dict(status=result['status'])]
                    elif template.get('status') == 'valid':
                        assessed += 1
                        passed += 1
                        if result['status'] != 'valid':
                            fit_failed += 1
                            phase = 'interval_inference'
                            issues = [dict(status=result['status'])]
                    else:
                        phase = 'support_not_available'
                        issues = [dict(status='support_diagnostics_unavailable')]
                valid += result['status'] == 'valid'
                if phase is not None:
                    # Each reason counts a replica once even if several bins fail it.
                    reasons.update(set(f"{phase}:{issue['status']}" for issue in issues))
                    for issue in issues:
                        failures.append(dict(mode=mode, key=key, replica=i, phase=phase,
                            result_status=result['status'], reason_code=issue['status'],
                            process=issue.get('process'), bin=issue.get('bin'), reason=result.get('reason')))
            complete = states['complete'] == REPLICAS
            summaries.append(dict(mode=mode, key=key, planned_replicas=REPLICAS,
                execution_status='complete' if complete else 'incomplete', completed_replicas=states['complete'],
                missing_replicas=states['missing'], corrupt_replicas=states['corrupt'],
                valid_interval_replicas=valid, threshold_estimation_failures=threshold_failed,
                support_assessed_replicas=assessed, support_passed_replicas=passed, support_failures=support_failed,
                support_unavailable_replicas=states['complete']-assessed-threshold_failed,
                interval_failures_after_support=fit_failed, available_template_replicas=available_templates,
                support_failure_rate=support_failed/REPLICAS if complete and assessed+threshold_failed == REPLICAS else None,
                threshold_failure_rate=threshold_failed/REPLICAS if complete else None,
                observed_min_neff_signed=min(neff_values) if neff_values else None,
                observed_min_rho=min(rho_values) if rho_values else None,
                failure_reason_replica_counts=dict(sorted(reasons.items()))))
    return dict(schema_version='h4l-draft-v2-sample-support-v1',
        nominal=[row for key in KEYS for row in template_support_rows(nominal[key], key)],
        bootstrap=summaries, failure_details=failures,
        interpretation='Stored nominal process/category moments and observed bootstrap support diagnostics only. '
            'Group counts are per bin, not totals of distinct groups across bins or candidates; bootstrap counts include copies. '
            'Observed minima include unsupported templates and are descriptive even for incomplete runs. '
            'Failure rates use all 200 planned replicas and are withheld if terminals or support outcomes are unavailable. '
            'No two-fold support estimate or T2 result is inferred from nominal moments. '
            'The shared inclusive reference appears in both modes but is not independent evidence.')


def csv_tables(support):
    tables = [
        ('nominal-support.csv', 'nominal', ['key', 'process', 'is_signal', 'category', 'mass_bin', 'bin',
            'mass_lower', 'mass_upper', 'result_status', 'template_status', 'bin_status', 'group_count',
            'signed_yield', 'variance', 'neff_signed', 'rho', 'moments_available']),
        ('bootstrap-support-summary.csv', 'bootstrap', ['mode', 'key', 'execution_status', 'planned_replicas',
            'completed_replicas', 'missing_replicas', 'corrupt_replicas', 'valid_interval_replicas',
            'threshold_estimation_failures', 'support_assessed_replicas', 'support_passed_replicas',
            'support_failures', 'support_unavailable_replicas', 'interval_failures_after_support',
            'available_template_replicas', 'support_failure_rate', 'threshold_failure_rate',
            'observed_min_neff_signed', 'observed_min_rho']),
        ('bootstrap-support-failures.csv', 'failure_details', ['mode', 'key', 'replica', 'phase',
            'result_status', 'reason_code', 'process', 'bin', 'reason'])]
    for name, source, columns in tables:
        yield name, columns, [[row[column] for column in columns] for row in support[source]]


def evidence_markdown(scope, support):
    lines = ['## Evidence scope', '',
        '| Evidence | Execution | Valid results / planned | Numerical completeness |',
        '|---|---|---:|---|']
    for name, row in scope['covered'].items():
        lines.append(f"| {name} | {row['execution_status']} | {row['valid_results']}/{row['planned_results']} | {row['numerical_status']} |")
    lines.extend(['', 'Assessment Toys are not evaluated in this workflow; independent-reference coverage remains unvalidated.',
        'T2 is available as a separate workflow and is not included or assessed by this report.',
        scope['interpretation'], '', '## Sample support', '', support['interpretation'], '',
        '| Nominal candidate | Process | Category | Mass bin | Physical groups | Signed N_eff | rho | Bin status |',
        '|---|---|---|---:|---:|---:|---:|---|'])
    def display(value):
        return 'unavailable' if value is None else (f'{value:.6g}' if isinstance(value, float) else str(value))
    for row in support['nominal']:
        lines.append('| '+' | '.join(display(row[k]) for k in
            ('key', 'process', 'category', 'mass_bin', 'group_count', 'neff_signed', 'rho', 'bin_status'))+' |')
    lines.extend(['', '| Bootstrap mode | Candidate | Completed / planned | Valid intervals | Threshold failures | Support failures | Interval failures after support | Missing / corrupt |',
        '|---|---|---:|---:|---:|---:|---:|---:|'])
    for row in support['bootstrap']:
        lines.append(f"| {row['mode']} | {row['key']} | {row['completed_replicas']}/{row['planned_replicas']} | "
            f"{row['valid_interval_replicas']} | {row['threshold_estimation_failures']} | {row['support_failures']} | "
            f"{row['interval_failures_after_support']} | {row['missing_replicas']}/{row['corrupt_replicas']} |")
    lines.extend(['', 'See nominal-support.csv for signed yields and variances, bootstrap-support-summary.csv for assessed counts '
        'and rates, and bootstrap-support-failures.csv for preserved reason codes. '
        'A support pass is not a valid interval or a coverage qualification.', ''])
    return '\n'.join(lines)
