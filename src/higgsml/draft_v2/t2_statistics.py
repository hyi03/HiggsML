"""Nested conditional T2: shared outer recalibration, disjoint fixed parents."""
from time import perf_counter

import numpy as np

from higgsml.artifacts import digest_json
from higgsml.errors import ResearchError, ResearchStateError
from higgsml.inference.templates import _build_role_templates
from higgsml.inference.likelihood import build_model, profile_interval
from higgsml.inference.stress import auxiliary_sampler
from higgsml.draft_v2.validation_statistics import build_cache, toy_summary
from higgsml.draft_v2.workflow import _t1_contract
from higgsml.draft_v2.t2_protocol import EXPECTED, fold_for_group, outer_draw, stream, units


def _independent_rates(template, mu):
    if template['status'] != 'valid':
        raise ResearchStateError('T2 parent fails the frozen support checks', status='insufficient_statistics')
    rates = np.zeros(len(template['active_bins']), float)
    for sample in template['samples']:
        covariance = np.asarray(sample['covariance'], float)
        if not np.allclose(covariance, np.diag(np.diag(covariance)), rtol=0, atol=1e-12):
            raise ResearchStateError('T2 parent cross-category physical groups are unsupported',
                                     status='template_stat_model_unvalidated')
        y = np.asarray(sample['yield'], float)[template['active_bins']]
        if not np.isfinite(y).all() or (y <= 0).any():
            raise ResearchStateError('Nonpositive T2 parent rates', status='insufficient_statistics')
        rates += y*(mu if sample['is_signal'] else 1.)
    return rates.tolist()


def prepare_cells(validation, evaluation, models, protocol, freeze_id, population_id):
    """Score once per role; build all outer mappings/support before any Toy.

    Each evaluation group belongs to one fixed half. Parent weights use the
    assignment probability, never their observed class totals or fold sizes.
    """
    started = perf_counter()
    cache = build_cache(validation, evaluation, models, protocol, freeze_id, population_id)
    folds = np.asarray([fold_for_group(g) for g in cache['frame'].event_group_id], int)
    parents = {}
    parent_receipts = {}
    for fold in (0, 1):
        selected = folds == fold
        parent = cache['frame'].loc[selected].copy()
        if parent.empty:
            raise ResearchError('Empty deterministic T2 evaluation fold; no repartitioning allowed')
        parent['yield_weight'] = parent.yield_weight / EXPECTED['folds']['probability']
        parents[fold] = parent
        groups = sorted(parent.event_group_id.unique())
        parent_receipts[str(fold)] = dict(groups=len(groups), rows=len(parent),
            groups_sha256=digest_json(groups), assignment_probability=.5, effective_sampling_probability=.1)
    if set(parents[0].event_group_id) & set(parents[1].event_group_id):
        raise ResearchError('T2 template and mother event groups overlap')
    identity = {**cache['identity'], 'fold_parents': parent_receipts,
                'validation_groups_sha256': digest_json(cache['validation_groups'])}
    maps, draws, thresholds = {}, {}, {}
    for outer in range(EXPECTED['outer']['count']):
        counts, draws[str(outer)] = outer_draw(freeze_id, outer, len(cache['validation_groups']))
        for key in models:
            try:
                threshold = cache['medians'][key].threshold(counts)
                maps[(outer, key)] = dict(status='valid', threshold=threshold)
            except ResearchStateError as error:
                maps[(outer, key)] = dict(status=error.status, threshold=None, reason=str(error))
        thresholds[str(outer)] = {key: maps[(outer, key)] for key in models}
    templates = {}
    def parent_template(fold, key, threshold):
        cache_key = (fold, key, threshold)
        if cache_key not in templates:
            category = (np.zeros(len(parents[fold]), int) if key == 'inclusive'
                        else (cache['scores'][key][folds == fold] >= threshold).astype(int))
            mapping = digest_json(dict(source_freeze=freeze_id, model_id=None if key == 'inclusive' else models[key]['model_id'],
                                       threshold=threshold, protocol_sha256=digest_json(EXPECTED)))
            try:
                templates[cache_key] = _build_role_templates(parents[fold].assign(category=category),
                    mass_edges=protocol['templates']['mass_edges'], mapping_id=mapping, candidate_id=key,
                    categories=(0,) if key == 'inclusive' else (0, 1), thresholds=protocol['templates'], expected_role='evaluation')
            except ResearchStateError as error:
                templates[cache_key] = dict(status=error.status, reason=str(error))
        return templates[cache_key]
    cells = {}
    for name, spec in units().items():
        key, outer, fold = spec['key'], spec['outer'], spec['template_fold']
        mapping = dict(status='valid', threshold=None) if key == 'inclusive' else maps[(outer, key)]
        cell = dict(specification=spec, mapping=mapping, status=mapping['status'], failure_phase=None)
        if mapping['status'] != 'valid':
            cell['failure_phase'] = 'threshold_estimation'
        else:
            cell['fit_template'] = parent_template(fold, key, mapping['threshold'])
            cell['mother_template'] = parent_template(1-fold, key, mapping['threshold'])
            for phase, template in [('fit_template', cell['fit_template']), ('mother', cell['mother_template'])]:
                try:
                    rates = _independent_rates(template, spec['mu'])
                    if phase == 'mother':
                        cell['mother_rates'] = rates
                except ResearchStateError as error:
                    cell.update(status=error.status, reason=str(error), failure_phase=phase)
                    break
        cell['cell_id'] = digest_json(cell)
        cells[name] = cell
    return dict(schema_version='h4l-draft-v2-t2-preflight-v1', source_identity=identity,
        draws=draws, thresholds=thresholds, cells=cells,
        timing=dict(scoring_seconds=cache['scoring_seconds'], total_seconds=perf_counter()-started),
        generated_toys=0, support_policy='individual_failed_cells_retain_all_100_planned_slots_no_rescue')


def fit_cell(cell, protocol, freeze_id, *, count=100):
    """Private count override is only for synthetic kernel tests, never artifacts."""
    started = perf_counter()
    spec = cell['specification']
    identity = (spec['key'], spec['template_fold'], spec['outer'], spec['mu'])
    rows, setup_failure = [], None
    if cell['status'] != 'valid':
        setup_failure = dict(status=cell['status'], reason=cell.get('reason', cell['mapping'].get('reason', 'T2 preflight failed')))
    else:
        # Preflight has already checked scientific support. Unexpected model
        # setup/dependency failures leave an interrupted claim for explicit retry.
        model, _ = build_model(cell['fit_template'], layer='T1', t1_validation=_t1_contract(protocol), mu_max=20.)
        pars = model.config.suggested_init()
        pars[model.config.poi_index] = spec['mu']
        sampler = auxiliary_sampler(model, pars)
        rates = np.asarray(cell['mother_rates'], float)
        if len(rates) != model.config.nmaindata or not np.isfinite(rates).all() or (rates < 0).any():
            raise ResearchError('T2 mother rates do not match the fitted bins')
    setup_seconds = perf_counter()-started
    generation_seconds, fit_seconds = 0., 0.
    for i in range(count):
        main_rng, main_seal = stream(freeze_id, 'main', *identity, i)
        aux_rng, aux_seal = stream(freeze_id, 'auxiliary', *identity, i)
        row = dict(toy=i, main_stream=main_seal, auxiliary_stream=aux_seal)
        if setup_failure is not None:
            row['interval'] = dict(setup_failure)
        else:
            started = perf_counter()
            observation = np.r_[main_rng.poisson(rates), sampler(aux_rng, policy='regenerated')]
            generation_seconds += perf_counter()-started
            started = perf_counter()
            row.update(observation=observation.tolist(), interval=profile_interval(model, observation, confidence=.68))
            fit_seconds += perf_counter()-started
        rows.append(row)
    return dict(schema_version='h4l-draft-v2-t2-cell-v1', specification=spec, count=count,
        cell_id=cell['cell_id'], threshold=cell['mapping']['threshold'], failure_phase=cell['failure_phase'],
        expectation_kind='crossfit_parent_t2', paired_coverage=False, results=rows,
        generated_toys=sum('observation' in r for r in rows), summary=toy_summary([r['interval'] for r in rows], spec['mu']),
        timing=dict(model_setup_seconds=setup_seconds, generation_seconds=generation_seconds, fit_seconds=fit_seconds))
