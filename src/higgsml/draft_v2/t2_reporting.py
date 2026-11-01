"""Outer-cluster T2 summaries; inner Toys are not independent recalibrations."""
import csv
from pathlib import Path
import uuid

import numpy as np

from higgsml.errors import ResearchError
from higgsml.draft_v2.t2_protocol import EXPECTED, KEYS, units
from higgsml.draft_v2 import t2_workflow as workflow
from higgsml.draft_v2 import validation_registry as artifacts
from higgsml.draft_v2.workflow import _evaluation_lock


def aggregate(results):
    """Average the two folds within each shared outer draw before summarizing."""
    candidates = []
    for key in KEYS:
        outer_rows, known = [], []
        for outer in range(20):
            cells = [results.get(name) for name, spec in units().items() if spec['key'] == key and spec['outer'] == outer]
            present = [v for v in cells if v is not None]
            known.extend(present)
            complete = len(present) == 2
            valid = sum(v['summary']['valid_fits'] for v in present)
            covered = sum(v['summary']['covered'] for v in present)
            outer_rows.append(dict(outer=outer, completed_folds=len(present), planned_toys=200,
                valid_fits=valid, covered=covered,
                success_and_coverage_fraction=covered/200 if complete else None,
                conditional_coverage=covered/valid if complete and valid else None,
                coverage=covered/200 if complete and valid == 200 else None))
        complete = len(known) == 40
        valid = sum(v['summary']['valid_fits'] for v in known)
        covered = sum(v['summary']['covered'] for v in known)
        fractions = [r['success_and_coverage_fraction'] for r in outer_rows]
        width_sum = sum((v['summary']['diagnostics']['mean_width'] or 0)*v['summary']['diagnostics']['valid_fits'] for v in known)
        bias_sum = sum((v['summary']['diagnostics']['bias_valid_fits'] or 0)*v['summary']['diagnostics']['valid_fits'] for v in known)
        candidates.append(dict(key=key, status='complete' if complete else 'incomplete', completed_cells=len(known),
            planned_cells=40, planned_toys=4000, completed_toy_slots=100*len(known), valid_fits=valid, covered=covered,
            numerical_status='complete' if complete and valid == 4000 else 'incomplete',
            coverage=covered/4000 if complete and valid == 4000 else None,
            success_and_coverage_fraction=float(np.mean(fractions)) if complete else None,
            conditional_coverage_valid_fits=covered/valid if complete and valid else None,
            failure_rate=(4000-valid)/4000 if complete else None,
            outer_cluster_standard_error=float(np.std(fractions, ddof=1)/np.sqrt(20)) if complete else None,
            outer_fraction_percentiles_16_84=np.quantile(fractions, [.16, .84]).tolist() if complete else None,
            mean_width_valid_fits=width_sum/valid if complete and valid else None,
            bias_valid_fits=bias_sum/valid if complete and valid else None,
            outer_replicas=outer_rows,
            uncertainty_note='SE uses 20 outer fold-averaged success-and-coverage fractions conditional on fixed parents; '
                'percentiles describe outer variation, not confidence intervals. No pooled-inner Wilson interval.'))
    return candidates


def collect(root, protocol, registered, registration):
    preflight_terminal, preflight_invalid = workflow.find_preflight(root, protocol, registration)
    preflight = preflight_terminal[1] if preflight_terminal else None
    evidence, values, terminal_ids = {}, {}, {}
    for name, spec in units().items():
        prior, invalid = workflow.inventory(root, protocol, registered, registration, preflight, name) if preflight else (None, [])
        if prior is None:
            evidence[name] = dict(status='corrupt' if invalid else 'missing', preserved_invalid=invalid)
        else:
            loaded, result = prior
            values[name] = result
            terminal_ids[name] = loaded.manifest['artifact_id']
            evidence[name] = dict(status='complete', artifact_id=loaded.manifest['artifact_id'], path=str(loaded.path), preserved_invalid=invalid)
    summary = dict(schema_version='h4l-draft-v2-t2-report-v1', registration_id=registration['registration_id'],
        source_kind=registration['source']['source_kind'], qualification=EXPECTED['qualification'],
        execution_status='complete' if len(values) == 640 else 'incomplete',
        numerical_status='complete' if len(values) == 640 and all(v['summary']['valid_fits'] == 100 for v in values.values()) else 'incomplete',
        planned_units=640, completed_units=len(values), budget=EXPECTED['budget'],
        preflight_status='complete' if preflight else ('corrupt' if preflight_invalid else 'missing'),
        preserved_preflight_failures=preflight_invalid, preflight_id=preflight['preflight_id'] if preflight else None,
        source_identity=preflight['source_identity'] if preflight else registration['source'],
        thresholds=preflight['thresholds'] if preflight else {}, evidence=evidence,
        cells={name: {k: v for k, v in value.items() if k != 'results'} for name, value in values.items()},
        candidates=aggregate(values),
        interpretation='Fixed-checkpoint T2 with 20 validation bootstraps, two fixed disjoint evaluation parents '
            'and 100 independent inner Toys per candidate/fold/outer. Parents exchange roles across folds; '
            'folds and training seeds are not independent datasets. No retraining or whole-selection coverage. '
            'Coverage is exploratory conditional calibration/parent-mismatch evidence, not physical validation.')
    return summary, dict(registration_id=registration['registration_id'], preflight_id=summary['preflight_id'], terminal_artifacts=terminal_ids)


def export(run, summary):
    def csv_file(name, fields, rows):
        with (run.path/name).open('x', encoding='utf-8', newline='') as output:
            writer = csv.writer(output, lineterminator='\n')
            writer.writerow(['source_kind', *fields])
            writer.writerows([[summary['source_kind'], *r] for r in rows])
        run.register_file(name)
    rows = []
    for name, spec in units().items():
        cell = summary['cells'].get(name, {})
        value = cell.get('summary', {})
        diagnostics = value.get('diagnostics', {})
        rows.append([name, spec['key'], spec['template_fold'], spec['mother_fold'], spec['outer'], 1, 100,
            summary['evidence'][name]['status'], cell.get('threshold'), cell.get('failure_phase'), cell.get('generated_toys'),
            value.get('valid_fits'), value.get('success_and_coverage_fraction'), value.get('conditional_coverage'),
            *(value.get('wilson_interval_success_and_coverage') or [None, None]),
            *(value.get('wilson_interval_conditional_coverage') or [None, None]), value.get('failure_rate'),
            value.get('missing_upper_rate'), value.get('mle_lower_boundary_rate'), value.get('mle_upper_boundary_rate'),
            diagnostics.get('bias_valid_fits'), diagnostics.get('mean_width')])
    csv_file('cells.csv', ['unit', 'candidate', 'template_fold', 'mother_fold', 'outer', 'mu', 'planned_inner',
        'execution_status', 'threshold', 'failure_phase', 'generated_toys', 'valid_fits', 'success_and_coverage',
        'conditional_coverage', 'wilson_success_lower', 'wilson_success_upper', 'wilson_conditional_lower',
        'wilson_conditional_upper', 'failure_rate', 'missing_upper_rate', 'mle_lower_boundary_rate',
        'mle_upper_boundary_rate', 'bias_valid_fits', 'mean_width_valid_fits'], rows)
    csv_file('outer-clusters.csv', ['candidate', 'outer', 'completed_folds', 'planned_toys', 'valid_fits',
        'covered', 'success_and_coverage', 'conditional_coverage'],
        [[v['key'], r['outer'], r['completed_folds'], r['planned_toys'], r['valid_fits'], r['covered'],
          r['success_and_coverage_fraction'], r['conditional_coverage']] for v in summary['candidates'] for r in v['outer_replicas']])
    csv_file('coverage.csv', ['candidate', 'execution_status', 'numerical_status', 'planned_toys', 'completed_toy_slots',
        'valid_fits', 'success_and_coverage', 'conditional_coverage', 'failure_rate', 'outer_cluster_standard_error',
        'bias_valid_fits', 'mean_width_valid_fits'],
        [[v['key'], v['status'], v['numerical_status'], v['planned_toys'], v['completed_toy_slots'], v['valid_fits'],
          v['success_and_coverage_fraction'], v['conditional_coverage_valid_fits'], v['failure_rate'],
          v['outer_cluster_standard_error'], v['bias_valid_fits'], v['mean_width_valid_fits']] for v in summary['candidates']])
    csv_file('thresholds.csv', ['outer', 'candidate', 'status', 'threshold'],
        [[i, key, value['status'], value['threshold']] for i, values in summary['thresholds'].items() for key, value in values.items()])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axis = plt.subplots(figsize=(10, 7))
    for i, value in enumerate(summary['candidates']):
        if value['status'] != 'complete':
            axis.text(.03, i, f"incomplete: {value['completed_cells']}/40 cells", color='grey', fontsize=8, va='center')
        else:
            axis.errorbar(value['success_and_coverage_fraction'], i-.12, xerr=value['outer_cluster_standard_error'], fmt='o', color='C0')
            if value['conditional_coverage_valid_fits'] is not None:
                axis.plot(value['conditional_coverage_valid_fits'], i+.12, 'x', color='C1')
    axis.axvline(.68, color='black', linestyle='--')
    axis.set(xlim=(-.02, 1.02), ylim=(-.6, len(KEYS)-.4), yticks=range(len(KEYS)), yticklabels=KEYS,
        xlabel='Success and coverage (circle, outer-cluster SE); conditional coverage (cross)',
        title=f"{summary['source_kind']}: exploratory fixed-checkpoint T2, mu=1\n20 outer clusters; two shared-parent folds, not independent datasets")
    fig.tight_layout()
    for extension in ('png', 'pdf'):
        name = 't2-coverage.'+extension
        fig.savefig(run.path/name)
        run.register_file(name)
    plt.close(fig)
    (run.path/'report.md').write_text('# Draft-v2 nested T2 report\n\n'+summary['interpretation']+'\n\n'+
        f"Execution: {summary['execution_status']}; numerical completeness: {summary['numerical_status']}.\n\n"+
        'Per-cell Wilson intervals condition on one mapping and two fixed parents. Aggregate error bars use 20 outer '
        'clusters, not 4000 independent recalibrations. Failure slots stay in planned denominators. No ATLAS/CMS '
        'result, Higgs discovery or physics measurement. Qualification remains exploratory_posthoc, independent=false, '
        'selection_aware_coverage=unvalidated.\n', encoding='utf-8')
    run.register_file('report.md')


def report(source_run, root, protocol, *, continuation=False):
    registered, registration, _ = workflow.bound(source_run, root, protocol)
    root = Path(root)
    with _evaluation_lock(root):
        summary, binding = collect(root, protocol, registered, registration)
        for path in [root/'report', *sorted(root.glob('report-resume-*'))]:
            if path.exists():
                if not continuation:
                    raise ResearchError('T2 report exists; use --continue')
                try:
                    loaded = artifacts.load(root, path.name, 't2-report', protocol)
                    if loaded.read_json('binding.json') == binding and loaded.read_json('summary.json') == summary:
                        return loaded
                except ResearchError:
                    pass
        name = 'report' if not (root/'report').exists() else 'report-resume-'+uuid.uuid4().hex
        with artifacts.new_run(root, name, 't2-report', protocol, [registered]) as run:
            run.write_json('binding.json', binding)
            run.write_json('summary.json', summary)
            export(run, summary)
        return artifacts.load(root, name, 't2-report', protocol)
