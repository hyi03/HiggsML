"""Frozen conditional CDFs with variance-weighted nonnegative signed fits."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .errors import ResearchError, ResearchStateError
from .discriminants import digest, _validate_frame
from .protocol import protocol_dict


def _state(message, status='insufficient_statistics'):
    raise ResearchStateError(message, status=status)


def constrained_distribution(yields, variances):
    """Solve min sum((z-y)^2/v), z>=0, sum(z)=sum(y).

    Zero-variance bins are structural zeros. This weighted simplex projection
    records its adjustment and objective; it does not clip and renormalize y.
    """
    y, v = np.asarray(yields,float), np.asarray(variances,float)
    if y.shape != v.shape or not np.isfinite(y).all() or not np.isfinite(v).all() or (v < 0).any():
        raise ResearchError('invalid signed histogram moments')
    total = y.sum()
    if total <= 0:
        _state('nonpositive signed normalization', 'nonpositive_calibration_yield')
    if np.any((v == 0) & (y != 0)):
        raise ResearchError('nonzero yield has zero variance')
    active = v > 0
    z = np.zeros_like(y)
    for _ in range(len(y)+1):
        if not active.any():
            _state('no feasible probability support')
        lagrange = (y[active].sum() - total) / v[active].sum()
        proposed = y[active] - lagrange * v[active]
        if (proposed >= 0).all():
            z[active] = proposed
            break
        active[np.flatnonzero(active)[proposed < 0]] = False
    correction = z-y
    return dict(probabilities=(z/total).tolist(), raw_yields=y.tolist(), variances=v.tolist(),
                fitted_yields=z.tolist(), correction=correction.tolist(),
                correction_chi2=float(np.sum(correction[v>0]**2/v[v>0])), total_yield=float(total),
                algorithm='variance-weighted-nonnegative-fixed-total-projection-v1')


def _background(frame, scores):
    _validate_frame(frame, ['calibration'], ['m4l'])
    values = np.asarray(scores,float)
    if values.shape != (len(frame),) or not np.isfinite(values).all():
        raise ResearchError('score alignment invalid')
    mask = frame.label.to_numpy() == 0
    if not mask.any():
        _state('no calibration background')
    return frame.loc[mask].reset_index(drop=True), values[mask]


def _moments(frame, scores, edges, target):
    weights = frame.physical_weight.to_numpy(float)
    if target == 'absolute':
        weights = np.abs(weights)
    bins = np.minimum(np.searchsorted(edges, scores, side='right')-1,len(edges)-2)
    identities = pd.DataFrame(dict(group=frame.event_group_id.to_numpy(),bin=bins))
    if not identities.empty and identities.groupby('group').bin.nunique().max() > 1:
        _state('same physical event group occupies multiple CDF score bins; covariance fit unvalidated',
               'template_stat_model_unvalidated')
    grouped = pd.DataFrame(dict(group=frame.event_group_id.to_numpy(),bin=bins,w=weights)).groupby(['group','bin']).w.sum()
    y = np.zeros(len(edges)-1)
    v = np.zeros_like(y)
    multiplicity = (frame.groupby('event_group_id').bootstrap_multiplicity.first().to_dict()
                    if 'bootstrap_multiplicity' in frame else {})
    for (group, b), w in grouped.items():
        y[b] += w
        v[b] += w*w / multiplicity.get(group,1)
    group_weights = pd.Series(weights).groupby(frame.event_group_id).sum()
    variance = float(sum(w*w / multiplicity.get(group,1) for group,w in group_weights.items()))
    total = float(weights.sum())
    neff = total*total/variance if variance > 0 else 0.
    cancellation = total / np.abs(weights).sum() if np.abs(weights).sum() else 0.
    return y,v,neff,cancellation


def fit_calibration(frame, scores, protocol, target='physical', model_id=None):
    protocol = protocol_dict(protocol)
    if target in {'abs','absolute_weight'}:
        target = 'absolute'
    if target not in {'physical','absolute'} or not model_id:
        raise ResearchError('calibration target/model binding missing')
    bg, score = _background(frame,scores)
    if protocol.get('dataset', bg.dataset.iloc[0]) != bg.dataset.iloc[0]:
        raise ResearchError('calibration protocol dataset mismatch')
    cfg = protocol['calibration']
    strategies = dict(interpolation='linear-bin-cdf_mass-centers',ties='same-score-same-cdf',
                      tails='score-clamp_mass-reject',merge_order='leftmost-failing-right-else-left')
    if any(cfg.get(k,v) != v for k,v in strategies.items()):
        raise ResearchError('unsupported frozen CDF strategy')
    mass_edges, score_edges = np.asarray(cfg['mass_edges'],float), np.asarray(cfg['score_edges'],float)
    if any(e.ndim != 1 or len(e)<2 or not np.isfinite(e).all() or (np.diff(e)<=0).any() for e in (mass_edges,score_edges)):
        raise ResearchError('invalid calibration grid')
    if ((bg.m4l < mass_edges[0]) | (bg.m4l > mass_edges[-1])).any():
        _state('calibration mass outside support','outside_calibration_support')
    if ((score < score_edges[0]) | (score > score_edges[-1])).any():
        raise ResearchError('calibration scores outside declared score grid')
    minimum, ratio = float(cfg['min_effective_count']),float(cfg['min_cancellation_ratio'])
    if minimum <= 0 or not 0 < ratio <= 1:
        raise ResearchError('invalid calibration support thresholds')
    intervals = [[float(a),float(b)] for a,b in zip(mass_edges[:-1],mass_edges[1:])]
    merges = []
    while True:
        fitted, failing = [], None
        for i,(lo,hi) in enumerate(intervals):
            mask = (bg.m4l.to_numpy() >= lo) & ((bg.m4l.to_numpy() < hi) | ((hi == mass_edges[-1]) & (bg.m4l.to_numpy() == hi)))
            part = bg.loc[mask].reset_index(drop=True)
            y,v,neff,cancel = _moments(part,score[mask],score_edges,target)
            if y.sum() <= 0 or neff < minimum or cancel < ratio:
                failing = i
                break
            fitted.append(dict(interval=[lo,hi],center=(lo+hi)/2,effective_count=neff,cancellation_ratio=cancel,
                               **constrained_distribution(y,v)))
        if failing is None:
            break
        if len(intervals)==1:
            _state('calibration support fails after deterministic adjacent merges', 'nonpositive_calibration_yield' if y.sum()<=0 else 'insufficient_statistics')
        left = failing if failing < len(intervals)-1 else failing-1
        merges.append([*intervals[left],*intervals[left+1]])
        intervals[left:left+2] = [[intervals[left][0],intervals[left+1][1]]]
    final_mass_bin=np.searchsorted([bounds[1] for bounds in intervals[:-1]],bg.m4l.to_numpy(),side='right')
    if pd.DataFrame(dict(group=bg.event_group_id,bin=final_mass_bin)).groupby('group').bin.nunique().max()>1:
        _state('physical event group crosses fitted mass slices; covariance unvalidated', 'template_stat_model_unvalidated')
    result = dict(schema_version='research-cdf-v1',model_id=model_id,protocol_id=digest(protocol),
        dataset=str(bg.dataset.iloc[0]),target=target,source_role='calibration_background',
        calibration_group_ids=sorted(set(bg.event_group_id.astype(str))),mass_support=[mass_edges[0],mass_edges[-1]],
        score_edges=score_edges.tolist(),slices=fitted,merges=merges,**strategies,
        limitations=['finite histogram plateaus; not guaranteed invertible','event groups crossing fitted score bins or mass slices rejected'],status='calibrated')
    result['mapping_id'] = digest(result)
    return result


def apply_calibration(mapping, masses, scores, *, model_id=None):
    if not model_id or model_id != mapping.get('model_id'):
        raise ResearchError('CDF/model binding mismatch')
    if digest({k:v for k,v in mapping.items() if k!='mapping_id'}) != mapping.get('mapping_id'):
        raise ResearchError('CDF content digest mismatch')
    m,t = np.asarray(masses,float),np.asarray(scores,float)
    if m.shape != t.shape or m.ndim != 1 or not np.isfinite(m).all() or not np.isfinite(t).all():
        raise ResearchError('invalid CDF inputs')
    if ((m < mapping['mass_support'][0]) | (m > mapping['mass_support'][1])).any():
        _state('mass outside frozen CDF support','outside_calibration_support')
    centers = np.array([s['center'] for s in mapping['slices']])
    cdfs = np.array([np.interp(t,mapping['score_edges'],np.r_[0,np.cumsum(s['probabilities'])],left=0,right=1) for s in mapping['slices']])
    # Same-score ties always receive the same value at a given mass, including endpoints.
    return np.array([np.interp(m[i],centers,cdfs[:,i]) for i in range(len(m))])


def fit_thresholds(frame, scores, protocol, *, model_id, mapping_id):
    """Physical-yield median from calibration background only, ties stay together."""
    protocol = protocol_dict(protocol)
    if not model_id or not mapping_id:
        raise ResearchError('threshold identity binding missing')
    bg,t = _background(frame,scores)
    edges = np.asarray(protocol['calibration']['score_edges'],float)
    if (t < edges[0]).any() or (t > edges[-1]).any():
        raise ResearchError('threshold scores outside registered grid')
    y,v,neff,cancel = _moments(bg,t,edges,'physical')
    cfg=protocol['calibration']
    if neff < cfg['min_effective_count'] or cancel < cfg['min_cancellation_ratio']:
        _state('threshold calibration has insufficient support')
    fit=constrained_distribution(y,v)
    cumulative=np.cumsum(fit['probabilities'])
    k=int(np.searchsorted(cumulative,.5))
    before=0. if k==0 else cumulative[k-1]
    threshold=edges[k]+(edges[k+1]-edges[k])*(.5-before)/fit['probabilities'][k]
    result=dict(model_id=model_id,mapping_id=mapping_id,thresholds=[float(threshold)],source_role='calibration_background',
                ties='higher-category-at-threshold',distribution_fit=fit,protocol_id=digest(protocol))
    result['threshold_id']=digest(result)
    return result


def assign_categories(thresholds,scores,*,model_id,mapping_id):
    if thresholds['model_id']!=model_id or thresholds['mapping_id']!=mapping_id or digest({k:v for k,v in thresholds.items() if k!='threshold_id'})!=thresholds['threshold_id']:
        raise ResearchError('threshold/model/mapping binding mismatch')
    scores=np.asarray(scores,float)
    if not np.isfinite(scores).all():
        raise ResearchError('nonfinite category scores')
    return np.searchsorted(thresholds['thresholds'],scores,side='right')


def bootstrap_calibration(frame, seed):
    """Multinomial group resampling; every source row shares its group's draw."""
    _validate_frame(frame,['calibration'],['m4l'])
    groups=np.array(sorted(frame.event_group_id.astype(str).unique()))
    counts=np.random.default_rng(seed).multinomial(len(groups),np.full(len(groups),1/len(groups)))
    multiplicity=dict(zip(groups,counts))
    out=frame.copy()
    out['bootstrap_multiplicity']=out.event_group_id.astype(str).map(multiplicity)
    out=out.loc[out.bootstrap_multiplicity>0].copy()
    for column in ('physical_weight','yield_weight'):
        if column in out:
            out[column]=out[column]*out.bootstrap_multiplicity
    return out.reset_index(drop=True)
