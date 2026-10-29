"""Complete conditional ablations and grouped, correlated mass diagnostics."""
import csv

import numpy as np

from higgsml.errors import ResearchError
from higgsml.inference.statistics import GroupBinStatistics
from higgsml.draft_v2.protocol import CANDIDATES, SEEDS, QUALIFICATION, candidate_key


def summarize(results):
    expected = {candidate_key(s, k) for s in CANDIDATES for k in SEEDS} | {'inclusive'}
    if set(results) != expected:
        raise ResearchError("Report requires all fifteen candidate states and the shared reference")

    def width(key):
        row = results[key]
        value = row.get('interval', {}).get('width')
        return float(value) if row['status'] == 'valid' and value is not None and np.isfinite(value) else None

    rows = []
    for subset in CANDIDATES:
        values = [width(candidate_key(subset, seed)) for seed in SEEDS]
        rows.append(dict(subset=subset, widths=values,
            statuses=[results[candidate_key(subset, seed)]['status'] for seed in SEEDS],
            median=float(np.median(values)) if None not in values else None))
    contrasts = []
    for group, reduced in zip('ABCD', ('BCD', 'ACD', 'ABD', 'ABC')):
        values = []
        for seed in SEEDS:
            left, right = width(candidate_key(reduced, seed)), width(candidate_key('ABCD', seed))
            values.append(left - right if left is not None and right is not None else None)
        contrasts.append(dict(removed_group=group, reduced=reduced, differences=values,
                             median_difference=float(np.median(values)) if None not in values else None))
    return dict(schema_version='h4l-draft-v2-report-v1', qualification=QUALIFICATION,
        seeds=list(SEEDS), rows=rows, contrasts=contrasts,
        inclusive_width=width('inclusive'), inclusive_status=results['inclusive']['status'],
        scientific_status='complete' if all(r['status'] == 'valid' for r in results.values()) else 'incomplete',
        interpretation='Nominal model-self intervals; seed spreads are not confidence intervals. '
                       'No independent coverage, finite-MC width-difference uncertainty or confirmed precision gain.')


def mass_spectra(frame, accepted, edges):
    mass = frame.m4l.to_numpy(float)
    accepted = np.asarray(accepted, bool)
    edges = np.asarray(edges, float)
    if (len(accepted) != len(frame) or not np.isfinite(mass).all()
            or not ((mass >= edges[0]) & (mass < edges[-1])).all()):
        raise ResearchError("Invalid spectrum selection or half-open mass support")
    bins = np.searchsorted(edges, mass, side='right') - 1
    weights, groups = frame.yield_weight.to_numpy(float), frame.event_group_id.to_numpy()
    n = len(edges) - 1
    statistics = GroupBinStatistics(np.r_[groups, groups[accepted]],
        np.r_[bins, bins[accepted] + n], np.r_[weights, weights[accepted]], 2 * n)
    y, covariance, absolute, positive, negative, occupancy = statistics.moments()
    variance = np.diag(covariance)
    neff = np.divide(y*y, variance, out=np.zeros_like(y), where=variance > 0)
    rho = np.divide(np.abs(y), absolute, out=np.zeros_like(y), where=absolute > 0)
    low_support = (occupancy == 0) | (y <= 0) | (variance <= 0) | (neff < 20) | (rho < .2)
    projection = np.zeros((2, 2 * n))
    projection[0, :n], projection[1, n:] = 1., 1.
    totals, total_covariance = projection @ y, projection @ covariance @ projection.T
    total_absolute = projection @ absolute
    total_neff = np.divide(totals**2, np.diag(total_covariance), out=np.zeros(2),
                           where=np.diag(total_covariance) > 0)
    total_rho = np.divide(np.abs(totals), total_absolute, out=np.zeros(2), where=total_absolute > 0)
    normalization_valid = bool(np.all(totals > 0) and np.all(total_neff >= 20) and np.all(total_rho >= .2))
    fractions, shape_covariance = None, None
    if normalization_valid:
        jacobian = np.zeros((2*n, 2*n))
        fractions = np.empty(2*n)
        for offset in (0, n):
            part = y[offset:offset+n]
            total = float(part.sum())
            fractions[offset:offset+n] = part / total
            jacobian[offset:offset+n, offset:offset+n] = np.eye(n)/total - part[:, None]/total**2
        shape_covariance = jacobian @ covariance @ jacobian.T
    retention, retention_error = None, None
    if totals[0] > 0:
        retention = float(totals[1] / totals[0])
        gradient = np.array([-totals[1] / totals[0]**2, 1. / totals[0]])
        retention_error = float(np.sqrt(max(0., gradient @ total_covariance @ gradient)))
    return dict(mass_edges=edges.tolist(), yields=y.tolist(), covariance=covariance.tolist(),
        fractions=fractions.tolist() if fractions is not None else None,
        shape_covariance=shape_covariance.tolist() if shape_covariance is not None else None,
        normalization_status='valid_signed_shape' if normalization_valid else 'unsupported_signed_normalization',
        absolute=absolute.tolist(), positive=positive.tolist(), negative=negative.tolist(),
        group_count=occupancy.tolist(), neff_signed=neff.tolist(), rho=rho.tolist(),
        low_support=low_support.tolist(), totals=totals.tolist(), total_covariance=total_covariance.tolist(),
        retention=retention, retention_error=retention_error,
        uncertainty_scope='Grouped MC moments at fixed trained networks and thresholds; no retraining or coverage calibration')


def export_report(run, summary, spectra, *, source_kind):
    """Write publication-independent aggregates, CSV tables and diagnostic figures."""
    def write_csv(name, fields, rows):
        with (run.path / name).open('x', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream, lineterminator='\n')
            writer.writerow(['source_kind', *fields])
            writer.writerows([[source_kind, *row] for row in rows])
        run.register_file(name)

    write_csv('widths.csv', ['subset', 'seed42', 'seed43', 'seed44', 'median', 'statuses'],
        [[r['subset'], *r['widths'], r['median'], ';'.join(r['statuses'])] for r in summary['rows']])
    write_csv('inclusive-reference.csv', ['W68', 'status'],
              [[summary['inclusive_width'], summary['inclusive_status']]])
    write_csv('contrasts.csv', ['removed_group', 'seed42', 'seed43', 'seed44', 'median_difference'],
        [[r['removed_group'], *r['differences'], r['median_difference']] for r in summary['contrasts']])
    lines = ['# Draft-v2 exploratory technical report', '', f'Source kind: **{source_kind}**.', '', summary['interpretation'], '',
             'Controlled MC or labelled synthetic software evidence only. No official ATLAS/CMS result, '
             'Higgs discovery or physics measurement.', '',
             '| Model | Seed 42 W68 | Seed 43 W68 | Seed 44 W68 | Median |',
             '|---|---:|---:|---:|---:|']
    def display(value):
        return 'incomplete' if value is None else f'{value:.6g}'
    for row in summary['rows']:
        lines.append('| ' + ' | '.join([row['subset'], *map(display, row['widths']), display(row['median'])]) + ' |')
    lines += ['', f"Shared inclusive-count W68: {display(summary['inclusive_width'])}.", '',
              '| Removed group | Seed 42 delta W | Seed 43 delta W | Seed 44 delta W | Median difference |',
              '|---|---:|---:|---:|---:|']
    for row in summary['contrasts']:
        lines.append('| ' + ' | '.join([row['removed_group'], *map(display, row['differences']),
                                        display(row['median_difference'])]) + ' |')
    lines += ['', 'See results.json for every failure and support record.']
    (run.path / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    run.register_file('report.md')
    spectrum_rows, totals_rows = [], []
    for key, processes in spectra.items():
        for process, record in processes.items():
            edges = record['mass_edges']
            n = len(edges) - 1
            for category_index, category in enumerate(('before', 'high')):
                totals_rows.append([key, process, category, record['totals'][category_index],
                    np.sqrt(record['total_covariance'][category_index][category_index]),
                    record['retention'], record['retention_error'], record['normalization_status']])
                for i in range(n):
                    j = i + category_index*n
                    spectrum_rows.append([key, process, category, edges[i], edges[i+1], record['yields'][j],
                        np.sqrt(record['covariance'][j][j]), record['low_support'][j]])
    write_csv('mass-bins.csv', ['model', 'process', 'category', 'mass_low', 'mass_high', 'signed_yield', 'error', 'low_support'], spectrum_rows)
    write_csv('yield-summary.csv', ['model', 'process', 'category', 'signed_yield', 'error', 'retention', 'retention_error', 'normalization_status'], totals_rows)
    if not spectra:
        return
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for shape in (False, True):
        fig, axes = plt.subplots(len(spectra), 2, figsize=(11, 4*len(spectra)),
                                 squeeze=False, sharex=True, sharey='col')
        for row_index, (key, processes) in enumerate(spectra.items()):
            for column, process in enumerate(('signal', 'background')):
                ax, record = axes[row_index, column], processes[process]
                edges = np.asarray(record['mass_edges'])
                n = len(edges)-1
                values = record['fractions'] if shape else record['yields']
                cov = record['shape_covariance'] if shape else record['covariance']
                if values is None:
                    ax.text(.5, .5, 'Unsupported signed normalization', ha='center', transform=ax.transAxes)
                else:
                    for offset, label in ((0, 'Baseline'), (n, 'High score')):
                        ax.errorbar((edges[:-1]+edges[1:])/2, values[offset:offset+n],
                            yerr=np.sqrt(np.maximum(0, np.diag(cov)[offset:offset+n])), marker='o', label=label)
                    for i in range(n):
                        if record['low_support'][i] or record['low_support'][i+n]:
                            ax.axvspan(edges[i], edges[i+1], color='grey', alpha=.12)
                    ax.legend()
                ax.axhline(0, color='black', lw=.5)
                ax.set(title=f'{key}, {process}', xlabel='Four-lepton mass [GeV]',
                       ylabel='Signed normalized bin content' if shape else 'Expected signed yield at 10 fb$^{-1}$')
        label = 'synthetic software diagnostic' if source_kind == 'synthetic' else 'controlled MC exploratory diagnostic'
        fig.suptitle(f'Draft-v2 {label}\nFixed-network grouped MC errors; shaded bins have limited support')
        fig.tight_layout()
        stem = 'mass-shapes' if shape else 'mass-yields'
        for extension in ('png', 'pdf'):
            name = f'{stem}.{extension}'
            fig.savefig(run.path / name)
            run.register_file(name)
        plt.close(fig)
