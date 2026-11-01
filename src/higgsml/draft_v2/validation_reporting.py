"""Failure-preserving supplemental summaries, independent of manuscript assets."""
import csv
from pathlib import Path
import uuid

import numpy as np

from higgsml.errors import ResearchError
from higgsml.draft_v2.protocol import QUALIFICATION
from higgsml.draft_v2.reporting import summarize
from higgsml.draft_v2.validation_thresholds import threshold_diagnostics
from higgsml.draft_v2.validation_evidence import evidence_scope, sample_support, csv_tables, evidence_markdown
from higgsml.draft_v2.validation_protocol import KEYS, MODES, units
from higgsml.draft_v2 import validation_registry as registry
from higgsml.draft_v2.validation_execution import inventory
from higgsml.draft_v2.workflow import _evaluation_lock


def summarize_bootstrap(replicas, nominal):
    nominal_contrasts = summarize(nominal)['contrasts']
    rows = []
    for mode in MODES:
        for j, nominal_contrast in enumerate(nominal_contrasts):
            values = [replicas[i]['contrasts'][mode][j]['median_difference'] if i in replicas else None for i in range(200)]
            complete = all(v is not None and np.isfinite(v) for v in values)
            baseline = nominal_contrast['median_difference']
            rows.append(dict(mode=mode, removed_group=nominal_contrast['removed_group'], planned=200,
                valid=sum(v is not None for v in values), status='complete' if complete else 'incomplete',
                nominal_difference=baseline,
                percentile_16_84=np.quantile(values, [.16, .84], method='linear').tolist() if complete else None,
                percentile_2_5_97_5=np.quantile(values, [.025, .975], method='linear').tolist() if complete else None,
                direction_flip_frequency=float(np.mean(np.asarray(values)*baseline < 0))
                    if complete and baseline is not None and baseline != 0 else None,
                direction_rule='strict sign opposite to nominal; zero is not a flip; zero nominal is undefined',
                values=values))
    return rows


def collect(root, protocol, registered, registration, nominal, models):
    terminals, evidence, replicas, toys, numerical = {}, {}, {}, {}, True
    for unit, spec in units().items():
        terminal, invalid = inventory(root, protocol, registration, unit, registered)
        if terminal is None:
            evidence[unit] = dict(status='corrupt' if invalid else 'missing', preserved_invalid=invalid)
            numerical = False
            continue
        loaded, result = terminal
        terminals[unit] = loaded.manifest['artifact_id']
        evidence[unit] = dict(status='complete', path=str(loaded.path), artifact_id=loaded.manifest['artifact_id'],
                              preserved_invalid=invalid)
        if spec['stage'] == 'bootstrap':
            replicas[spec['replica']] = result
            numerical &= all(r['status'] == 'valid' for rows in result['results'].values() for r in rows.values())
        else:
            toys[unit] = result
            numerical &= result['summary']['valid_fits'] == 500
    thresholds = threshold_diagnostics(replicas, nominal, models)
    summary = dict(schema_version='h4l-draft-v2-validation-report-v1',
        registration_id=registration['registration_id'], source_kind=registration['source']['source_kind'],
        execution_status='complete' if len(terminals) == len(units()) else 'incomplete',
        numerical_status='complete' if numerical else 'incomplete', qualification=QUALIFICATION,
        completed_units=len(terminals), planned_units=len(units()), evidence=evidence,
        contrasts=summarize_bootstrap(replicas, nominal), thresholds=thresholds,
        evidence_scope=evidence_scope(evidence, replicas, toys, thresholds),
        sample_support=sample_support(nominal, replicas, evidence),
        model_self={u: {k: v for k, v in value.items() if k != 'results'} for u, value in toys.items()},
        interpretation='Exploratory posthoc fixed-checkpoint diagnostics. Bootstrap percentile ranges are conditional '
            'on selected networks. Model-self coverage uses each nominal model as its own truth; '
            'no paired coverage comparison, calibration, independent physics validation or selection-aware coverage.',
        budgets=dict(bootstrap_replicas=200, model_self_cells=48, toys_per_cell=500,
                     bootstrap_interval_groups=6200, model_self_fits=24000))
    return summary, terminals


def export(run, summary):
    def write_csv(name, columns, rows):
        with (run.path/name).open('x', encoding='utf-8', newline='') as output:
            writer = csv.writer(output, lineterminator='\n')
            writer.writerow(['source_kind', *columns])
            writer.writerows([[summary['source_kind'], *r] for r in rows])
        run.register_file(name)
    for name, columns, rows in csv_tables(summary['sample_support']):
        write_csv(name, columns, rows)
    write_csv('bootstrap-contrasts.csv', ['mode', 'removed_group', 'replica', 'median_difference'],
        [[r['mode'], r['removed_group'], i, v] for r in summary['contrasts'] for i, v in enumerate(r['values'])])
    write_csv('thresholds.csv', ['mode', 'model', 'replica', 'nominal_threshold', 'threshold',
        'threshold_delta', 'threshold_changed', 'status', 'fixed_status', 'threshold_estimation_failed', 'support_failed'],
        [['refitted-threshold', r['key'], v['replica'], r['nominal_threshold'], v['threshold'],
          v['threshold_delta'], v['threshold_changed'], v['status'], v['fixed_status'],
          v['threshold_estimation_failed'], v['support_failed']]
         for r in summary['thresholds'] for v in r['rows']])
    write_csv('category-yield-changes.csv', ['mode', 'model', 'replica', 'process', 'category', 'change_from_nominal'],
        [['refitted-threshold', r['key'], v['replica'], p, c, delta]
         for r in summary['thresholds'] for v in r['rows']
         for p, changes in (v['category_yield_change'] or {}).items() for c, delta in enumerate(changes)])
    # Include missing comparisons as empty values; never silently export only
    # the successful/support-passing subset of the planned replicas.
    paired_rows = []
    for record in summary['thresholds']:
        processes = sorted({p for row in record['rows'] for p in (row['paired_category_yield_change'] or {})})
        for row in record['rows']:
            changes = row['paired_category_yield_change'] or {}
            for process in processes:
                for category in (0, 1):
                    values = changes.get(process)
                    paired_rows.append(['refitted-minus-fixed', record['key'], row['replica'], process, category,
                        values[category] if values is not None else None, row['fixed_status'], row['status']])
    write_csv('paired-category-yield-changes.csv', ['comparison', 'model', 'replica', 'process', 'category',
        'signed_yield_change_same_evaluation_draw', 'fixed_status', 'refitted_status'], paired_rows)
    write_csv('bootstrap-summary.csv', ['mode', 'removed_group', 'status', 'planned', 'valid',
        'q16', 'q84', 'q2_5', 'q97_5', 'direction_flip_frequency'],
        [[r['mode'], r['removed_group'], r['status'], r['planned'], r['valid'],
          *(r['percentile_16_84'] or [None, None]), *(r['percentile_2_5_97_5'] or [None, None]),
          r['direction_flip_frequency']] for r in summary['contrasts']])
    write_csv('threshold-summary.csv', ['mode', 'model', 'planned', 'observed_replicas', 'available',
        'threshold_status', 'nominal_threshold', 'changed_replicas', 'threshold_changed_fraction',
        'lower_threshold_replicas', 'higher_threshold_replicas', 'median_threshold_delta',
        'delta_q2_5', 'delta_q16', 'delta_q84', 'delta_q97_5', 'threshold_estimation_failures',
        'threshold_estimation_failure_rate', 'support_assessed_replicas', 'support_failures', 'support_failure_rate',
        'q2_5', 'q16', 'q84', 'q97_5', 'paired_yield_available'],
        [['refitted-threshold', r['key'], r['planned'], r['observed_replicas'], r['available'],
          r['threshold_status'], r['nominal_threshold'], r['changed_replicas'], r['threshold_changed_fraction'],
          r['lower_threshold_replicas'], r['higher_threshold_replicas'], r['median_threshold_delta'],
          *(r['threshold_delta_percentile_2_5_16_84_97_5'] or [None]*4), r['threshold_estimation_failures'],
          r['threshold_estimation_failure_rate'], r['support_assessed_replicas'], r['support_failures'], r['support_failure_rate'],
          *(r['percentile_2_5_16_84_97_5'] or [None]*4), r['paired_yield_available']]
         for r in summary['thresholds']])
    coverage_rows = []
    for unit, spec in units('model-self').items():
        result = summary['model_self'].get(unit)
        value = result['summary'] if result is not None else {}
        diagnostics = value.get('diagnostics', {})
        coverage_rows.append(['model-self', spec['key'], spec['mu'], summary['evidence'][unit]['status'],
            500, value.get('valid_fits'), value.get('success_and_coverage_fraction'),
            *(value.get('wilson_interval_success_and_coverage') or [None, None]),
            value.get('conditional_coverage'), *(value.get('wilson_interval_conditional_coverage') or [None, None]),
            diagnostics.get('bias_valid_fits'), diagnostics.get('mean_width'), value.get('failure_rate'),
            value.get('fit_failure_rate'), value.get('missing_upper_rate'),
            value.get('mle_lower_boundary_rate'), value.get('mle_upper_boundary_rate'),
            value.get('interval_lower_boundary_rate')])
    write_csv('coverage.csv', ['mode', 'model', 'mu', 'execution_status', 'budget', 'valid_fits',
        'success_and_coverage', 'wilson_success_lower', 'wilson_success_upper', 'conditional_coverage',
        'wilson_conditional_lower', 'wilson_conditional_upper', 'bias_valid_fits', 'mean_width',
        'all_failure_rate', 'fit_failure_rate', 'missing_upper_rate', 'mle_lower_boundary_rate',
        'mle_upper_boundary_rate', 'interval_lower_boundary_rate'], coverage_rows)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figures = []
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    for axis, group in zip(axes.flat, 'ABCD'):
        for row in summary['contrasts']:
            if row['removed_group'] != group:
                continue
            if row['status'] == 'complete':
                axis.hist(row['values'], bins=20, alpha=.5, label=row['mode'])
            else:
                axis.plot([], [], label=f"{row['mode']}: incomplete ({row['valid']}/200)")
        axis.axvline(0, color='black', linewidth=.8)
        axis.set(title=f'Remove {group}', xlabel='Median within-seed reduced minus ABCD W68', ylabel='Replicas')
        axis.legend(fontsize=7)
    figures.append(('bootstrap-differences', fig))
    fig, axes = plt.subplots(5, 3, figsize=(12, 12))
    for axis, row in zip(axes.flat, summary['thresholds']):
        values = [v['threshold'] for v in row['rows'] if v['threshold'] is not None]
        if values:
            axis.hist(values, bins=15)
        axis.axvline(row['nominal_threshold'], color='black', linestyle='--')
        axis.set(title=f"{row['key']}: {row['available']}/200", xlabel='Refitted threshold')
    figures.append(('refitted-thresholds', fig))
    fig, axes = plt.subplots(5, 3, figsize=(12, 12))
    for axis, row in zip(axes.flat, summary['thresholds']):
        values = [v['threshold_delta'] for v in row['rows'] if v['threshold_delta'] is not None]
        if values:
            axis.hist(values, bins=15)
        axis.axvline(0, color='black', linestyle='--')
        axis.set(title=f"{row['key']}: {row['available']}/200", xlabel='Refitted minus nominal threshold', ylabel='Replicas')
    figures.append(('threshold-shifts', fig))
    fig, axes = plt.subplots(1, 3, figsize=(15, 6), sharey=True)
    for axis, mu in zip(axes, (0, 1, 2)):
        for j, key in enumerate(KEYS):
            rows = [v for v in summary['model_self'].values() if v['key'] == key and v['mu'] == mu]
            if not rows:
                axis.text(.03, j, 'missing unit', fontsize=7, color='grey', va='center')
                continue
            value = rows[0]['summary']
            if value['valid_fits'] < 500:
                axis.text(.03, j, f"{value['valid_fits']}/500 valid", fontsize=7, color='grey', va='center')
            for offset, field, bounds, marker in [(-.12, 'success_and_coverage_fraction', 'wilson_interval_success_and_coverage', 'o'),
                     (.12, 'conditional_coverage', 'wilson_interval_conditional_coverage', 'x')]:
                if value[field] is not None:
                    p, (lo, hi) = value[field], value[bounds]
                    axis.errorbar(p, j+offset, xerr=[[max(0., p-lo)], [max(0., hi-p)]], fmt=marker, color='C0' if offset < 0 else 'C1')
        axis.axvline(.68, color='black', linestyle='--')
        axis.set(title=f'Model-self mu={mu}', xlim=(-.02, 1.02), ylim=(-.6, len(KEYS)-.4), xlabel='Coverage; 95% Wilson intervals', yticks=range(len(KEYS)), yticklabels=KEYS)
    figures.append(('model-self-coverage', fig))
    for name, fig in figures:
        fig.suptitle(f"{summary['source_kind']}: exploratory, non-independent, fixed checkpoints\n"
                     'Coverage: circles=success and coverage; crosses=conditional on valid fits' if name == 'model-self-coverage'
                     else f"{summary['source_kind']}: exploratory, non-independent, fixed checkpoints")
        fig.tight_layout()
        for extension in ('png', 'pdf'):
            filename = name+'.'+extension
            fig.savefig(run.path/filename)
            run.register_file(filename)
        plt.close(fig)
    text = ('# Draft-v2 supplemental evaluation\n\n'+summary['interpretation']+'\n\n'
            f"Source: {summary['source_kind']}. Execution: {summary['execution_status']}. "
            f"Numerical completeness: {summary['numerical_status']}.\n\n"
            'Qualification: exploratory_posthoc; independent=false; selection_aware_coverage=unvalidated.\n\n'
            'Missing units and failed outcomes remain visible. Numerical completeness does not certify coverage. '
            'No official ATLAS/CMS result, Higgs discovery or physics measurement.\n\n'
            'Threshold diagnostics condition on fixed checkpoints. threshold-shifts plots refitted minus nominal cuts; '
            'paired-category-yield-changes.csv subtracts fixed from refitted cuts on the same evaluation draw. '
            'category-yield-changes.csv instead subtracts nominal yields and also includes evaluation resampling. '
            'Threshold-estimation failures and downstream support failures have separate counts. '
            'Formal threshold summaries require all 200 estimates; histograms label available estimates.\n\n'
            + evidence_markdown(summary['evidence_scope'], summary['sample_support']))
    (run.path/'report.md').write_text(text, encoding='utf-8')
    run.register_file('report.md')


def report(source_run, root, protocol, *, continuation=False):
    registered, registration, source = registry.bound_registration(source_run, root, protocol)
    root = Path(root)
    with _evaluation_lock(root):
        summary, terminal_ids = collect(root, protocol, registered, registration, source['nominal'], source['models'])
        binding = dict(registration_id=registration['registration_id'], terminal_artifacts=terminal_ids)
        reports = [root/'report', *sorted(root.glob('report-resume-*'))]
        for path in reports:
            if path.exists():
                if not continuation:
                    raise ResearchError('Report already exists; use --continue')
                try:
                    prior = registry.load(root, path.name, 'report', protocol)
                    if prior.read_json('binding.json') == binding and prior.read_json('summary.json') == summary:
                        return prior
                except ResearchError:
                    pass  # Preserve invalid report; a new aggregate may describe it separately.
        name = 'report' if not (root/'report').exists() else 'report-resume-'+uuid.uuid4().hex
        with registry.new_run(root, name, 'report', protocol, [registered]) as run:
            run.write_json('binding.json', binding)
            run.write_json('summary.json', summary)
            export(run, summary)
        return registry.load(root, name, 'report', protocol)
