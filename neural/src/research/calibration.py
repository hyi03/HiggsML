"""Frozen conditional CDFs with variance-weighted nonnegative signed fits."""
from __future__ import annotations

from dataclasses import dataclass
import json
import numpy as np
import pandas as pd

from .errors import ResearchError, ResearchStateError
from .discriminants import digest, _validate_frame
from .protocol import canonical, protocol_dict


_RAW_CALIBRATION_TOKEN = object()


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
    grouped = pd.DataFrame(dict(group=frame.event_group_id.to_numpy(),bin=bins,w=weights)).groupby(['group','bin']).w.sum()
    if grouped.index.get_level_values('group').duplicated().any():
        _state('same physical event group occupies multiple CDF score bins; covariance fit unvalidated',
               'template_stat_model_unvalidated')
    y = np.zeros(len(edges)-1)
    v = np.zeros_like(y)
    multiplicity = (frame.groupby('event_group_id').bootstrap_multiplicity.first().to_dict()
                    if 'bootstrap_multiplicity' in frame else {})
    for (group, b), w in grouped.items():
        y[b] += w
        v[b] += w*w / multiplicity.get(group,1)
    variance = float(sum(w*w / multiplicity.get(group,1) for (group,b),w in grouped.items()))
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
    mass_bins = np.minimum(np.searchsorted(mass_edges, bg.m4l.to_numpy(), side='right')-1, len(mass_edges)-2)
    members = [np.flatnonzero(mass_bins == i) for i in range(len(intervals))]
    moments = {}
    merges = []
    while True:
        fitted, failing = [], None
        for i,(lo,hi) in enumerate(intervals):
            key = (lo, hi)
            if key not in moments:
                indices = members[i]
                part = bg.iloc[indices].reset_index(drop=True)
                moments[key] = _moments(part,score[indices],score_edges,target)
            y,v,neff,cancel = moments[key]
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
        members[left:left+2] = [np.sort(np.concatenate(members[left:left+2]))]
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
    output = np.empty_like(m)
    # Bound scratch storage independently of the total event count.
    chunk_size = max(1, (8 * 1024 * 1024) // (8 * len(centers)))
    curves = [np.r_[0,np.cumsum(s['probabilities'])] for s in mapping['slices']]
    for start in range(0, len(m), chunk_size):
        stop = min(start + chunk_size, len(m))
        cdfs = np.array([np.interp(t[start:stop],mapping['score_edges'],curve,left=0,right=1) for curve in curves])
        masses = m[start:stop]
        right = np.clip(np.searchsorted(centers, masses, side='right'), 1, max(1,len(centers)-1))
        if len(centers) == 1:
            output[start:stop] = cdfs[0]
            continue
        left = right-1
        rows = np.arange(stop-start)
        low, high = cdfs[left,rows], cdfs[right,rows]
        result = low + (high-low)/(centers[right]-centers[left])*(masses-centers[left])
        result = np.where(masses <= centers[0], cdfs[0], result)
        output[start:stop] = np.where(masses >= centers[-1], cdfs[-1], result)
    return np.clip(output, 0., 1.)


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


@dataclass(frozen=True, init=False)
class RawCalibrationBundle:
    payload: bytes
    _capability: object

    def __init__(self, raw, *, _token=None):
        if _token is not _RAW_CALIBRATION_TOKEN:
            raise ResearchError("raw calibration must come from its verified builder",
                                status="training_subset_binding_mismatch")
        object.__setattr__(self, "payload", canonical(raw))
        object.__setattr__(self, "_capability", _RAW_CALIBRATION_TOKEN)

    def to_dict(self):
        return json.loads(self.payload)

    def __getitem__(self, key):
        return self.to_dict()[key]

    def get(self, key, default=None):
        return self.to_dict().get(key, default)


def require_raw_calibration_bundle(bundle, loaded):
    from .sample_efficiency_lineage import require_experiment_lineage
    from .sample_efficiency_training import require_loaded_subset_discriminant

    loaded = require_loaded_subset_discriminant(loaded)
    if (not isinstance(bundle, RawCalibrationBundle)
            or getattr(bundle, "_capability", None) is not _RAW_CALIBRATION_TOKEN):
        raise ResearchError("verified raw calibration bundle is required",
                            status="training_subset_binding_mismatch")
    raw = bundle.to_dict()
    expected = {"model", "model_id", "candidate_id", "seed", "key", "mapping", "mapping_id",
                "thresholds", "transform", "status", "experiment_lineage", "calibration_id"}
    if set(raw) != expected:
        raise ResearchError("invalid raw calibration schema", status="training_subset_binding_mismatch")
    require_experiment_lineage(raw, loaded.lineage)
    content = {key: value for key, value in raw.items() if key != "calibration_id"}
    thresholds = raw.get("thresholds")
    threshold_content = ({key: value for key, value in thresholds.items() if key != "threshold_id"}
                         if type(thresholds) is dict else None)
    if (raw["calibration_id"] != digest(content) or raw["model"] != loaded.model
            or raw["model_id"] != loaded.model["model_id"]
            or raw["candidate_id"] != loaded.model["candidate"]
            or raw["seed"] != loaded.model["seed"] or raw["key"] != loaded.model["experiment_cell_id"]
            or raw["mapping"] is not None or raw["mapping_id"] != "raw:" + loaded.model["model_id"]
            or raw["transform"] != "raw" or raw["status"] != "calibrated"
            or threshold_content is None or thresholds.get("threshold_id") != digest(threshold_content)
            or thresholds.get("model_id") != raw["model_id"]
            or thresholds.get("mapping_id") != raw["mapping_id"]):
        raise ResearchError("raw calibration binding mismatch", status="training_subset_binding_mismatch")
    return bundle


def build_raw_calibration_bundle(prepared, loaded, protocol, *, transform="raw"):
    """Build the M3 raw bundle; sample-efficiency CDF paths remain closed."""
    from .sample_efficiency_training import load_bound_prepared_role, predict_subset_discriminant
    from .sample_efficiency_lineage import bind_experiment_lineage

    if transform != "raw":
        raise ResearchError("sample-efficiency calibration supports bound raw models only",
                            status="training_subset_binding_mismatch")
    frame = load_bound_prepared_role(prepared, loaded, protocol, "calibration")
    scores = predict_subset_discriminant(loaded, frame)
    model = loaded.model
    mapping_id = "raw:" + model["model_id"]
    thresholds = fit_thresholds(frame, scores, protocol, model_id=model["model_id"], mapping_id=mapping_id)
    payload = {"model": model, "model_id": model["model_id"], "candidate_id": model["candidate"],
               "seed": model["seed"], "key": model["experiment_cell_id"], "mapping": None,
               "mapping_id": mapping_id, "thresholds": thresholds, "transform": "raw", "status": "calibrated"}
    payload = bind_experiment_lineage(payload, loaded.lineage)
    payload["calibration_id"] = digest(payload)
    bundle = RawCalibrationBundle(payload, _token=_RAW_CALIBRATION_TOKEN)
    return require_raw_calibration_bundle(bundle, loaded)
