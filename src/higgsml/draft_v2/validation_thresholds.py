"""Fixed-checkpoint threshold diagnostics derived from paired bootstrap units.

No events, model inference, refits or source mutations occur in this module.
Yield changes against the same evaluation draw isolate category redistribution
from the additional validation draw; changes against nominal also contain
finite-evaluation-MC variation. Neither is a retraining uncertainty estimate.
"""
import numpy as np

from higgsml.draft_v2.validation_protocol import EXPECTED, KEYS

SUPPORT_FAILURES = frozenset({'insufficient_statistics', 'template_stat_model_unvalidated',
                             'nonpositive_yield', 'strong_cancellation', 'zero_variance'})
REPLICAS = EXPECTED['bootstrap']['replicas']
QUANTILES = [.025, .16, .84, .975]


def yield_difference(left, right):
    """Retain signed template yields even when support or fitting fails."""
    left = {s['name']: np.asarray(s['yield'], float) for s in left.get('template', {}).get('samples', [])}
    right = {s['name']: np.asarray(s['yield'], float) for s in right.get('template', {}).get('samples', [])}
    if not left or left.keys() != right.keys():
        return None
    if any(left[p].shape != right[p].shape or not np.isfinite(left[p]).all()
           or not np.isfinite(right[p]).all() for p in left):
        return None
    return {p: (left[p]-right[p]).tolist() for p in sorted(left)}


def threshold_diagnostics(replicas, nominal, models):
    result = []
    for key in KEYS:
        if key == 'inclusive':
            continue
        nominal_threshold = models[key]['threshold']
        rows = []
        for i in range(REPLICAS):
            replica = replicas.get(i)
            row = dict(replica=i, threshold=None, threshold_delta=None, threshold_changed=None,
                       status='missing', fixed_status='missing', threshold_estimation_failed=None,
                       support_failed=None, category_yield_change=None, paired_category_yield_change=None)
            if replica is not None:
                value = replica['results']['refitted-threshold'][key]
                fixed = replica['results']['fixed-threshold'][key]
                threshold = replica['thresholds'][key]
                estimated = threshold is not None
                row.update(threshold=threshold, status=value['status'], fixed_status=fixed['status'],
                    threshold_delta=float(threshold-nominal_threshold) if estimated else None,
                    threshold_changed=bool(threshold != nominal_threshold) if estimated else None,
                    threshold_estimation_failed=not estimated,
                    support_failed=(value['status'] in SUPPORT_FAILURES) if estimated else None,
                    category_yield_change=yield_difference(value, nominal[key]),
                    paired_category_yield_change=yield_difference(value, fixed))
            rows.append(row)
        observed = sum(r['status'] != 'missing' for r in rows)
        values = [r['threshold'] for r in rows if r['threshold'] is not None]
        deltas = [r['threshold_delta'] for r in rows if r['threshold_delta'] is not None]
        complete = len(values) == REPLICAS
        failures = sum(r['support_failed'] is True for r in rows)
        estimation_failures = sum(r['threshold_estimation_failed'] is True for r in rows)
        changed = sum(r['threshold_changed'] is True for r in rows)
        result.append(dict(key=key, nominal_threshold=nominal_threshold, rows=rows,
            diagnostic_version='paired-threshold-diagnostics-v1',
            available=len(values), planned=REPLICAS, observed_replicas=observed,
            threshold_status='complete' if complete else 'incomplete',
            threshold_estimation_failures=estimation_failures,
            threshold_estimation_failure_rate=estimation_failures/REPLICAS if observed == REPLICAS else None,
            changed_replicas=changed, threshold_changed_fraction=changed/REPLICAS if complete else None,
            lower_threshold_replicas=sum(v < 0 for v in deltas), higher_threshold_replicas=sum(v > 0 for v in deltas),
            median_threshold_delta=float(np.median(deltas)) if complete else None,
            threshold_delta_percentile_2_5_16_84_97_5=np.quantile(deltas, QUANTILES, method='linear').tolist() if complete else None,
            support_assessed_replicas=len(values),
            support_failures=failures, support_failure_rate=failures/REPLICAS if observed == REPLICAS else None,
            observed_support_failure_fraction=failures/observed if observed else None,
            percentile_2_5_16_84_97_5=np.quantile(values, QUANTILES, method='linear').tolist() if complete else None,
            paired_yield_available=sum(r['paired_category_yield_change'] is not None for r in rows),
            distribution_scope='all available thresholds, including fit/support failures; missing thresholds retained',
            changed_rule='exact difference between empirical score thresholds; no tolerance or retuning',
            yield_change_definitions={
                'category_yield_change': 'refitted-threshold replica minus nominal; includes evaluation resampling',
                'paired_category_yield_change': 'refitted minus fixed threshold on the same evaluation draw; signed redistribution'},
            failure_rate_denominator='all planned replicas, only published when every terminal is present; threshold-estimation failures reported separately'))
    return result
