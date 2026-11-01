"""Conditional bootstrap and model-self kernels; no artifact writes or access."""
from dataclasses import dataclass
from time import perf_counter

import numpy as np
import pandas as pd

from higgsml.artifacts import digest_json
from higgsml.errors import ResearchError, ResearchStateError
from higgsml.inference.likelihood import build_model, profile_interval
from higgsml.inference.reporting import coverage_summary, fit_diagnostics
from higgsml.inference.stress import auxiliary_sampler
from higgsml.inference.templates import _build_role_templates
from higgsml.draft_v2 import training
from higgsml.draft_v2.reporting import summarize
from higgsml.draft_v2.validation_protocol import EXPECTED, MODES, stream
from higgsml.draft_v2.workflow import _t1_contract


class GroupMoments:
    """Dense two-bin group contributions with multiplicity-linear covariance.

    Occupancy counts *copies* of observed groups, including zero signed sums.
    Absolute/positive/negative sums are row sums, not absolute group sums.
    """
    def __init__(self, codes, bins, weights, n_groups, n_bins):
        index = np.asarray(codes, int) * n_bins + np.asarray(bins, int)
        shape = (n_groups, n_bins)
        def accumulate(values):
            return np.bincount(index, weights=values, minlength=n_groups*n_bins).reshape(shape)
        weights = np.asarray(weights, float)
        self.u = accumulate(weights)
        self.absolute = accumulate(np.abs(weights))
        self.positive = accumulate(np.maximum(weights, 0))
        self.negative = accumulate(np.minimum(weights, 0))
        self.occupancy = accumulate(np.ones(len(weights))) > 0

    def weighted(self, multiplicity):
        m = np.asarray(multiplicity)
        if (m.shape != (len(self.u),) or not np.isfinite(m).all()
                or (m < 0).any() or (m != np.floor(m)).any()):
            raise ResearchError('Invalid group multiplicity')
        return Moments((m @ self.u, self.u.T @ (m[:, None] * self.u),
                        m @ self.absolute, m @ self.positive, m @ self.negative,
                        m @ self.occupancy))


@dataclass
class Moments:
    values: tuple

    def moments(self):
        return self.values


@dataclass
class MedianCache:
    scores: np.ndarray
    weights: np.ndarray
    codes: np.ndarray

    @classmethod
    def create(cls, scores, weights, codes):
        order = np.argsort(scores, kind='stable')
        return cls(np.asarray(scores)[order], np.abs(np.asarray(weights, float))[order],
                   np.asarray(codes)[order])

    def threshold(self, multiplicity):
        weights = self.weights * np.asarray(multiplicity)[self.codes]
        # Ignore zero-multiplicity rows even at a zero cumulative plateau.
        selected = weights > 0
        total = weights.sum()
        if not np.isfinite(total) or total <= 0:
            raise ResearchStateError('No resampled validation background weight', status='insufficient_statistics')
        scores, weights = self.scores[selected], weights[selected]
        return float(scores[np.searchsorted(np.cumsum(weights), total/2, side='left')])


def group_index(frame):
    groups = sorted(frame.event_group_id.unique(), key=str)
    codes = frame.event_group_id.map({g: i for i, g in enumerate(groups)}).to_numpy(int)
    return groups, codes


def draw(freeze_id, role, replica, n_groups):
    if n_groups < 1:
        raise ResearchError('Bootstrap requires nonempty role groups')
    rng, seal = stream(freeze_id, EXPECTED['bootstrap']['seed'], 'bootstrap', role, replica)
    return rng.multinomial(n_groups, np.full(n_groups, 1/n_groups)), seal


def process_moments(frame, codes, categories, n_groups, n_bins):
    result = {}
    column = 'process' if 'process' in frame else 'label'
    for process, indices in frame.groupby(column, sort=True).indices.items():
        result[process] = (bool(frame.label.iloc[indices[0]]), GroupMoments(
            codes[indices], categories[indices], frame.yield_weight.to_numpy(float)[indices], n_groups, n_bins))
    return result


def build_cache(validation, evaluation, models, protocol, freeze_id, population_id):
    """One call-local score cache; its identity never substitutes for a receipt."""
    started = perf_counter()
    vg, vc = group_index(validation)
    eg, ec = group_index(evaluation)
    if set(vg) & set(eg) or set(validation.role) != {'validation'} or set(evaluation.role) != {'evaluation'}:
        raise ResearchError('Bootstrap role isolation violated')
    scores, medians, fixed = {}, {}, {}
    background = validation.label.to_numpy() == 0
    for key, model in models.items():
        scores[key] = training.predict(model, evaluation, protocol)
        values = training.predict(model, validation, protocol)
        medians[key] = MedianCache.create(values[background], validation.physical_weight.to_numpy()[background], vc[background])
    scoring_seconds = perf_counter() - started
    minimal = evaluation[['dataset', 'label', 'role', 'event_group_id', 'yield_weight', 'm4l']].copy()
    if 'process' in evaluation:
        minimal['process'] = evaluation.process.to_numpy()
    for key, model in models.items():
        category = (scores[key] >= model['threshold']).astype(int)
        fixed[key] = process_moments(minimal, ec, category, len(eg), 2)
    fixed['inclusive'] = process_moments(minimal, ec, np.zeros(len(evaluation), int), len(eg), 1)
    return dict(frame=minimal, scores=scores, medians=medians, fixed=fixed,
                evaluation_groups=eg, evaluation_codes=ec, validation_groups=vg,
                identity=dict(freeze_id=freeze_id, population_id=population_id,
                              model_ids={k: m['model_id'] for k, m in models.items()}),
                scoring_seconds=scoring_seconds,
                cache_build_seconds=perf_counter()-started-scoring_seconds)


def infer_moments(frame, categories, statistics, multiplicity, protocol, key, mapping):
    started = perf_counter()
    template_seconds, fit_seconds = 0., 0.
    template = None
    try:
        template = _build_role_templates(frame.assign(category=categories),
            mass_edges=protocol['templates']['mass_edges'], mapping_id=mapping, candidate_id=key,
            categories=(0,) if key == 'inclusive' else (0, 1), thresholds=protocol['templates'],
            expected_role='evaluation',
            _statistics={p: (signal, stats.weighted(multiplicity)) for p, (signal, stats) in statistics.items()})
        template_seconds = perf_counter()-started
        if template['status'] != 'valid':
            return dict(status=template['status'], template=template), template_seconds, fit_seconds
        started = perf_counter()
        model, _ = build_model(template, layer='T1', t1_validation=_t1_contract(protocol), mu_max=20.)
        parameters = model.config.suggested_init()
        parameters[model.config.poi_index] = 1.
        interval = profile_interval(model, model.expected_data(parameters), confidence=.68)
        return dict(status=interval['status'], interval=interval, template=template), template_seconds, perf_counter()-started
    except ResearchStateError as error:
        if error.status.startswith('dependency_'):
            raise
        result = dict(status=error.status, reason=str(error))
        if template is not None:
            result['template'] = template
        return result, template_seconds, perf_counter()-started


def bootstrap_replica(cache, models, protocol, replica):
    freeze_id = cache['identity']['freeze_id']
    evaluation, es = draw(freeze_id, 'evaluation', replica, len(cache['evaluation_groups']))
    validation, vs = draw(freeze_id, 'validation', replica, len(cache['validation_groups']))
    frame = cache['frame']
    timing = dict(template_seconds=0., fit_seconds=0.)
    def infer(key, categories, stats):
        result, templates, fits = infer_moments(frame, categories, stats, evaluation, protocol, key,
            freeze_id if key == 'inclusive' else models[key]['model_id'])
        timing['template_seconds'] += templates
        timing['fit_seconds'] += fits
        return result
    reference = infer('inclusive', np.zeros(len(frame), int), cache['fixed']['inclusive'])
    results = {mode: {'inclusive': reference} for mode in MODES}
    thresholds = {}
    for key, model in models.items():
        category = (cache['scores'][key] >= model['threshold']).astype(int)
        results[MODES[0]][key] = infer(key, category, cache['fixed'][key])
        try:
            threshold = cache['medians'][key].threshold(validation)
            thresholds[key] = threshold
            category = (cache['scores'][key] >= threshold).astype(int)
            started = perf_counter()
            stats = process_moments(frame, cache['evaluation_codes'], category, len(evaluation), 2)
            timing['template_seconds'] += perf_counter()-started
            results[MODES[1]][key] = infer(key, category, stats)
        except ResearchStateError as error:
            thresholds[key] = None
            results[MODES[1]][key] = dict(status=error.status, reason=str(error))
    return dict(replica=replica, results=results, thresholds=thresholds,
        contrasts={mode: summarize(rows)['contrasts'] for mode, rows in results.items()},
        draws={role: dict(stream=seal, multiplicity_sha256=digest_json(counts.tolist()),
                         groups=len(counts), total=int(counts.sum()))
               for role, counts, seal in [('evaluation', evaluation, es), ('validation', validation, vs)]},
        timing=timing, cache_identity=cache['identity'])


def toy_observation(model, expected, sampler, freeze_id, key, mu, index):
    rng, seal = stream(freeze_id, EXPECTED['toys']['seed'], 'model-self', key, mu, index)
    data = np.r_[rng.poisson(expected[:model.config.nmaindata]), sampler(rng, policy='regenerated')]
    return data, seal


def toy_summary(intervals, mu):
    n = len(intervals)
    return {**coverage_summary(intervals, mu=mu), 'diagnostics': fit_diagnostics(intervals, mu=mu),
        'missing_upper_count': sum(r.get('status') == 'interval_unbounded' for r in intervals),
        'missing_upper_rate': sum(r.get('status') == 'interval_unbounded' for r in intervals)/n,
        'fit_failure_rate': sum(r.get('status') == 'fit_failed' for r in intervals)/n,
        'mle_lower_boundary_rate': sum(r.get('muhat') is not None and r['muhat'] <= 1e-6 for r in intervals)/n,
        'mle_upper_boundary_rate': sum(r.get('muhat') is not None and r['muhat'] >= 20-1e-6 for r in intervals)/n,
        'interval_lower_boundary_rate': sum(bool(r.get('lower_at_boundary')) for r in intervals)/n,
        'boundary_rate_denominator': 'all_planned_toys; unavailable estimates contribute no boundary hit'}


def model_self_cell(template, protocol, freeze_id, key, mu, *, count=500):
    """The private count argument supports small synthetic kernel tests only."""
    started = perf_counter()
    rows = []
    try:
        model, metadata = build_model(template, layer='T1', t1_validation=_t1_contract(protocol), mu_max=20.)
        parameters = model.config.suggested_init()
        parameters[model.config.poi_index] = mu
        expected = np.asarray(model.expected_data(parameters), float)
        if not np.isfinite(expected).all() or (expected < 0).any():
            raise ResearchStateError('Invalid model expectation', status='insufficient_statistics')
        sampler = auxiliary_sampler(model, parameters)
    except ResearchStateError as error:
        if error.status.startswith('dependency_'):
            raise
        rows = [dict(toy=i, stream=stream(freeze_id, EXPECTED['toys']['seed'], 'model-self', key, mu, i)[1],
                     interval=dict(status=error.status, reason=str(error))) for i in range(count)]
        metadata = {}
    setup_seconds = perf_counter()-started
    generation_seconds, fit_seconds = 0., 0.
    if not rows:
        for i in range(count):
            started = perf_counter()
            observation, seal = toy_observation(model, expected, sampler, freeze_id, key, mu, i)
            generation_seconds += perf_counter()-started
            started = perf_counter()
            interval = profile_interval(model, observation, confidence=.68)
            fit_seconds += perf_counter()-started
            rows.append(dict(toy=i, stream=seal, observation=observation.tolist(), interval=interval))
    intervals = [r['interval'] for r in rows]
    return dict(key=key, mu=mu, count=count, results=rows, summary=toy_summary(intervals, mu),
                model_metadata=metadata, expectation_kind='model_self', auxiliary_generation='regenerated',
                paired=False, timing=dict(model_setup_seconds=setup_seconds, generation_seconds=generation_seconds, fit_seconds=fit_seconds))
