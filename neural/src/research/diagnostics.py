"""Auxiliary fixed-template diagnostics, separate from physical T0/T1 intervals."""
import numpy as np
from scipy.optimize import brentq

from .errors import ResearchError
from .protocol import DIAGNOSTICS


def signed_mu_fit(template, observations, contract):
    """Fit a signed signal coefficient with fixed nominal templates only.

    The derivative of the Poisson negative log likelihood is monotone on the
    positive-rate domain. No negative sample is submitted to pyhf and no rate
    is clipped. Nuisances are fixed, never silently profiled as if this were T1.
    """
    if contract != DIAGNOSTICS['signed_mu']:
        raise ResearchError('Unsupported signed-mu diagnostic contract')
    if template.get('status') != 'valid':
        raise ResearchError('Signed-mu diagnostic requires a valid template')
    active = np.asarray(template['active_bins'])
    if active.ndim != 1 or not len(active) or active.dtype.kind not in 'iu' or len(set(active)) != len(active) or (active < 0).any():
        raise ResearchError('Invalid active diagnostic bins')
    n = np.asarray(observations, float)
    if n.shape != active.shape or not np.isfinite(n).all() or (n < 0).any():
        raise ResearchError('Invalid diagnostic observations')
    signal, background = np.zeros(len(active)), np.zeros(len(active))
    for sample in template['samples']:
        rates = np.asarray(sample['yield'], float)
        if rates.ndim != 1 or (active >= len(rates)).any() or not np.isfinite(rates).all() or (rates < 0).any():
            raise ResearchError('Invalid diagnostic template rates')
        if sample['is_signal']:
            signal += rates[active]
        else:
            background += rates[active]
    metadata = dict(kind=contract['kind'], layer='T0_fixed_template_diagnostic',
                    nuisance_policy=contract['nuisance_policy'],
                    mapping_id=template.get('mapping_id'), candidate_id=template.get('candidate_id'),
                    interval_calibration='not_applicable_point_estimate_only')
    if not np.isfinite(signal).all() or not np.isfinite(background).all():
        raise ResearchError('Nonfinite aggregated diagnostic rates')
    if not (signal > 0).any() or (background <= 0).any():
        return {**metadata, 'status':'signed_domain_unavailable', 'muhat':None,
                'reason':'Requires signal sensitivity and strictly positive background in every active bin'}
    physical_lower = float(np.max(-background[signal > 0] / signal[signal > 0]))
    lo = max(contract['mu_bounds'][0], physical_lower * contract['positive_domain_fraction'])
    hi = contract['mu_bounds'][1]
    if not np.isfinite(lo) or not lo < 0 < hi:
        return {**metadata, 'status':'signed_domain_unavailable', 'muhat':None}

    def derivative(mu):
        rates = background + mu * signal
        if not np.isfinite(rates).all() or (rates <= 0).any():
            raise ValueError('Nonpositive diagnostic Poisson expectation')
        value = float(np.sum(signal * (1. - n / rates)))
        if not np.isfinite(value):
            raise ValueError('Nonfinite diagnostic likelihood derivative')
        return value

    try:
        left, right = derivative(lo), derivative(hi)
        boundary = 'lower' if left >= 0 else ('upper' if right <= 0 else None)
        estimate = lo if boundary == 'lower' else (hi if boundary == 'upper' else float(brentq(derivative, lo, hi, xtol=1e-10)))
        return {**metadata, 'status':'search_bound_reached' if boundary else 'valid',
                'muhat':estimate, 'constrained_fixed_template_muhat':max(0., estimate),
                'search_bounds':[lo, hi], 'search_boundary':boundary,
                'minimum_expected_rate':float(np.min(background + estimate * signal)),
                'interpretation':'Signed fixed-template point estimate; neither a T1 fit nor a calibrated interval'}
    except (ValueError, RuntimeError, FloatingPointError) as exc:
        return {**metadata, 'status':'fit_failed', 'muhat':None, 'reason':str(exc)}


def signed_mu_summary(fits):
    valid = [r['muhat'] for r in fits if r.get('status') == 'valid']
    return dict(status='valid' if len(valid) == len(fits) and fits else 'diagnostics_incomplete',
                budget=len(fits), valid_fits=len(valid),
                nonvalid_fits=len(fits)-len(valid),
                signed_mean_valid_fits=float(np.mean(valid)) if valid else None,
                signed_mean_standard_error=float(np.std(valid, ddof=1)/np.sqrt(len(valid))) if len(valid)>1 else None,
                scope='pure-background fixed-template diagnostic; boundary-limited fits remain in budget')
