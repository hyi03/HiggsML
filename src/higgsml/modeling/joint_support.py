"""Versioned calibration/template joint threshold selection for raw off models."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json

import numpy as np

from higgsml.artifacts import digest_json
from higgsml.errors import ResearchError, ResearchStateError
from higgsml.protocol import canonical, protocol_dict
from higgsml.modeling.calibration import _background, _moments, constrained_distribution
from higgsml.modeling.discriminants import _validate_frame, digest, predict_discriminant
from higgsml.inference.statistics import GroupBinStatistics

METHOD = 'h4l-off-joint-support-v1'
QUALIFICATION = dict(selection_aware_coverage='unvalidated',
                     registration_status='exploratory_posthoc', primary_claim_eligible=False)


def method_contract():
    value = json.loads((Path(__file__).parents[3] / 'config/protocols/h4l_off_joint_support_v1.json').read_text(encoding='utf-8'))
    implemented = dict(method_id=METHOD, quantile_numerators=list(range(1,20)), quantile_denominator=20,
        selection_order='abs(k-10),k', weights={'calibration':'physical_weight','template':'yield_weight'},
        min_rho=.2, min_neff_signed=20, mass_edges=[105,140], failure_policy='no_feasible_joint_threshold',
        rng_policy='h4l-off-joint-support-rng-v1')
    if value != implemented:
        raise ResearchError('method configuration differs from implemented joint-support-v1 contract')
    return value


def validate_threshold(record, protocol):
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError
    schema = json.loads((Path(__file__).parents[3] / 'config/schemas/h4l_joint_support_threshold.schema.json').read_text(encoding='utf-8'))
    try:
        Draft202012Validator(schema).validate(record)
    except ValidationError as error:
        raise ResearchError('invalid joint threshold schema') from error
    content = {k:v for k,v in record.items() if k not in {'threshold_id', 'record_digest'}}
    if (digest(content) != record['record_digest']
            or digest({k:v for k,v in record.items() if k != 'threshold_id'}) != record['threshold_id']
            or record['protocol_id'] != digest(protocol)
            or record['analysis_contract_digest'] != analysis_contract(protocol)['analysis_contract_digest']
            or record['input_bindings']['analysis_contract_digest'] != record['analysis_contract_digest']):
        raise ResearchError('joint threshold record binding mismatch')
    if record['status'] == 'valid':
        rows = record['candidates']
        if [r['quantile_numerator'] for r in rows] != list(range(1,20)):
            raise ResearchError('joint threshold quantile grid mismatch')
        feasible = [r for r in rows if r['feasible']]
        selected = min(feasible, key=lambda r:(abs(r['quantile_numerator']-10),r['quantile_numerator'])) if feasible else None
        if (selected is None or record['selected_quantile_numerator'] != selected['quantile_numerator']
                or record['thresholds'] != [selected['threshold']]
                or record['selected_threshold'] != selected['threshold']):
            raise ResearchError('joint threshold selection mismatch')
    return record


def analysis_contract(protocol):
    from higgsml.inference.attribution import BUDGETS
    from higgsml.inference.attribution_workflow import analysis_definition
    from higgsml.inference.marginal_coupling import pairing_contract
    body = dict(method_contract=method_contract(), source_core_protocol_digest=digest(protocol_dict(protocol)),
                candidate_definition=analysis_definition(), pairing_contract=pairing_contract(), budgets=BUDGETS)
    return {**body, 'analysis_contract_digest': digest_json(body)}


def method_fields(protocol, method='median-v1'):
    if method == 'median-v1':
        return {}
    if method != 'joint-support-v1':
        raise ResearchError('unknown threshold method')
    contract = analysis_contract(protocol)
    return dict(threshold_method=method, analysis_contract=contract,
                analysis_contract_digest=contract['analysis_contract_digest'],
                source_core_protocol_digest=contract['source_core_protocol_digest'])


def selection_diagnostics(records):
    """Selection/support summaries, distinct from inference success rates."""
    records = list(records)
    counts = {str(k):0 for k in range(1,20)}
    margins = {'neff_signed':[], 'rho':[]}
    failures = 0
    for record in records:
        if record.get('selector_bypassed'):
            continue
        if record.get('status') != 'valid':
            failures += 1
            continue
        k = record['selected_quantile_numerator']
        counts[str(k)] += 1
        selected = record['candidates'][k-1]
        for rows in selected['support'].values():
            for row in rows:
                margins['neff_signed'].append(row['neff_signed']-20)
                margins['rho'].append(row['rho']-.2)
    total = sum(counts.values()) + failures
    return dict(selected_quantile_counts=counts, failed_selections=failures, attempted_selections=total,
                failure_fraction=failures/total if total else None,
                minimum_selected_margin={k:min(v) if v else None for k,v in margins.items()})


def bootstrap_counts(groups, contract_digest, replica, role):
    if role not in {'calibration', 'template'} or not groups.size or not contract_digest:
        raise ResearchError('invalid joint bootstrap identity')
    payload = ['h4l-off-joint-support-rng-v1', contract_digest, 'mc_bootstrap', 42001, replica, role]
    seed = int.from_bytes(sha256(canonical(payload)).digest(), 'big')
    counts = np.random.Generator(np.random.PCG64(seed)).multinomial(len(groups), np.full(len(groups), 1/len(groups)))
    return counts


def _validate_inputs(frame, scores, role, protocol):
    _validate_frame(frame, [role], ['m4l', method_contract()['weights'][role]])
    scores = np.asarray(scores, float)
    edges = protocol['calibration']['score_edges']
    if (scores.shape != (len(frame),) or not np.isfinite(scores).all()
            or ((scores < edges[0]) | (scores > edges[-1])).any()
            or frame.dataset.iloc[0] != protocol['dataset']
            or frame.event_group_id.isna().any()
            or ((frame.m4l < 105) | (frame.m4l >= 140)).any()):
        raise ResearchError('joint selector input identity or support mismatch')
    if 'bootstrap_multiplicity' in frame:
        m = frame.bootstrap_multiplicity.to_numpy(float)
        if (not np.isfinite(m).all() or (m < 1).any() or (m != np.floor(m)).any()
                or frame.groupby('event_group_id').bootstrap_multiplicity.nunique().gt(1).any()):
            raise ResearchError('invalid group multiplicity')
    source = 'process' if 'process' in frame else 'label'
    if frame[source].isna().any() or frame.groupby('event_group_id')[source].nunique().gt(1).any():
        raise ResearchError('invalid physical process identity')
    identities = {}
    for name, part in frame.groupby(source):
        labels = set(part.label)
        if len(labels) != 1:
            raise ResearchError('ambiguous process signal identity')
        identities[str(name)] = int(next(iter(labels)))
    return scores, source, identities


def support_records(frame, scores, threshold, weight, source):
    """Group first; compressed bootstrap weights already contain multiplicity."""
    records = []
    for process in sorted(frame[source].astype(str).unique()):
        mask = frame[source].astype(str).to_numpy() == process
        part = frame.loc[mask]
        bins = (scores[mask] >= threshold).astype(int)
        weights = part[weight].to_numpy(float)
        stats = GroupBinStatistics(part.event_group_id, bins, weights, 2)
        y, covariance, absolute, _, _, occupancy = stats.moments()
        variance = np.diag(covariance)
        if 'bootstrap_multiplicity' in part:
            mult = part.groupby('event_group_id', sort=True).bootstrap_multiplicity.first().to_numpy(float)
            variance = np.asarray(stats.matrix.power(2).multiply((1/mult)[:, None]).sum(axis=0)).ravel()
            occupancy = np.asarray(stats.occupancy.multiply(mult[:, None]).sum(axis=0)).ravel()
        for b in range(2):
            rho = float(abs(y[b])/absolute[b]) if absolute[b] > 0 else None
            neff = float(y[b]**2/variance[b]) if variance[b] > 0 else None
            failures = [name for name, passed in (
                ('empty_category', occupancy[b] > 0), ('nonpositive_yield', y[b] > 0),
                ('nonpositive_variance', variance[b] > 0), ('low_rho', rho is not None and rho >= .2),
                ('low_neff_signed', neff is not None and neff >= 20)) if not passed]
            records.append(dict(process=process, category=b, y=float(y[b]), variance=float(variance[b]),
                                sum_abs_weight=float(absolute[b]), group_occupancy=int(occupancy[b]),
                                rho=rho, neff_signed=neff, status='valid' if not failures else 'insufficient_statistics',
                                reasons=failures))
    return records


def support_grid(frame, scores, cuts, weight, source):
    """Prepare group moments once for a draw, retaining same-group covariance.

    Disjoint intervals are accumulated before taking each low/high group sum.
    This is equivalent to separate two-bin GroupBinStatistics calls, including
    groups spanning score intervals and compressed independent bootstrap copies.
    """
    output = [[] for _ in cuts]
    for process in sorted(frame[source].astype(str).unique()):
        mask = frame[source].astype(str).to_numpy() == process
        part = frame.loc[mask]
        bins = np.searchsorted(cuts, scores[mask], side='right')
        weights = part[weight].to_numpy(float)
        stats = GroupBinStatistics(part.event_group_id, bins, weights, len(cuts)+1)
        group_sums = stats.matrix.toarray()
        low = np.cumsum(group_sums, axis=1)[:, :-1]
        high = group_sums.sum(axis=1)[:, None] - low
        occupied = stats.occupancy.toarray()
        low_occupied = np.cumsum(occupied, axis=1)[:, :-1] > 0
        high_occupied = (occupied.sum(axis=1)[:, None] - np.cumsum(occupied, axis=1)[:, :-1]) > 0
        mult = (part.groupby('event_group_id', sort=True).bootstrap_multiplicity.first().to_numpy(float)
                if 'bootstrap_multiplicity' in part else np.ones(stats.n_groups))
        absolute_low = np.cumsum(stats.row_sums[0])[:-1]
        absolute_high = stats.row_sums[0].sum() - absolute_low
        for b, group_y, occupancy, absolute in ((0, low, low_occupied, absolute_low),
                                               (1, high, high_occupied, absolute_high)):
            yields = group_y.sum(axis=0)
            variances = (group_y**2/mult[:, None]).sum(axis=0)
            counts = (occupancy * mult[:, None]).sum(axis=0)
            for i, (y, v, a, n) in enumerate(zip(yields, variances, absolute, counts)):
                rho = float(abs(y)/a) if a > 0 else None
                neff = float(y*y/v) if v > 0 else None
                failures = [name for name, passed in (
                    ('empty_category', n > 0), ('nonpositive_yield', y > 0), ('nonpositive_variance', v > 0),
                    ('low_rho', rho is not None and rho >= .2), ('low_neff_signed', neff is not None and neff >= 20)) if not passed]
                output[i].append(dict(process=process, category=b, y=float(y), variance=float(v),
                    sum_abs_weight=float(a), group_occupancy=int(n), rho=rho, neff_signed=neff,
                    status='valid' if not failures else 'insufficient_statistics', reasons=failures))
    return output


def select_joint_threshold(calibration_frame, calibration_scores, template_frame, template_scores,
                           core_protocol, method_contract, model_identity, input_bindings, draw_identity):
    protocol = protocol_dict(core_protocol)
    if method_contract != globals()['method_contract']():
        raise ResearchError('joint method contract mismatch')
    expected = analysis_contract(protocol)['analysis_contract_digest']
    if (not model_identity.get('model_id') or model_identity.get('mapping_id') != 'raw:' + model_identity['model_id']
            or not model_identity.get('candidate_key') or model_identity.get('seed') not in range(42, 47)
            or input_bindings.get('analysis_contract_digest') != expected
            or not all(input_bindings.get(k) for k in ('prepared_artifact_id', 'population_id', 'source_artifact_id'))
            or not draw_identity.get('stage')):
        raise ResearchError('joint selector identity binding missing or mismatched')
    c, cs, ci = _validate_inputs(calibration_frame, calibration_scores, 'calibration', protocol)
    t, ts, ti = _validate_inputs(template_frame, template_scores, 'template', protocol)
    if (cs != ts or ci != ti or set(ci.values()) != {0, 1}
            or set(calibration_frame.event_group_id.astype(str)) & set(template_frame.event_group_id.astype(str))):
        raise ResearchError('joint selector role/process identity mismatch')
    result = dict(schema_version='h4l-joint-support-threshold-v1', method_id=METHOD,
                  **model_identity, protocol_id=digest(protocol), analysis_contract_digest=expected,
                  source_role='calibration_template_joint', input_bindings=deepcopy(input_bindings),
                  draw_identity=deepcopy(draw_identity), process_identity_source='label_legacy' if cs == 'label' else 'process',
                  ties='higher-category-at-threshold', candidates=[], thresholds=[], selected_quantile_numerator=None,
                  selected_threshold=None, status='no_feasible_joint_threshold', reason='no_feasible_joint_threshold')
    result['role_bindings'] = {}
    for role, frame in (('calibration', calibration_frame), ('template', template_frame)):
        mult = frame.groupby('event_group_id').bootstrap_multiplicity.first().to_dict() if 'bootstrap_multiplicity' in frame else {g: 1 for g in frame.event_group_id.unique()}
        result['role_bindings'][role] = dict(groups_digest=digest_json(sorted(map(str, mult))),
            multiplicities_digest=digest_json({str(k): int(v) for k, v in sorted(mult.items())}))
    try:
        bg, scores = _background(calibration_frame, c)
        edges = np.asarray(protocol['calibration']['score_edges'], float)
        y, v, neff, rho = _moments(bg, scores, edges, 'physical')
        if neff < protocol['calibration']['min_effective_count'] or rho < protocol['calibration']['min_cancellation_ratio']:
            raise ResearchStateError('threshold calibration has insufficient support', status='insufficient_statistics')
        fit = constrained_distribution(y, v)
        result['distribution_fit'] = fit
        cumulative = np.cumsum(fit['probabilities'])
        cuts = []
        for k in range(1, 20):
            q = k/20
            b = int(np.searchsorted(cumulative, q))
            before = cumulative[b-1] if b else 0.
            threshold = float(edges[b] + (edges[b+1]-edges[b])*(q-before)/fit['probabilities'][b])
            cuts.append(threshold)
        c_support = support_grid(calibration_frame, c, cuts, 'physical_weight', cs)
        t_support = support_grid(template_frame, t, cuts, 'yield_weight', ts)
        for k, threshold in enumerate(cuts, 1):
            support = dict(calibration=c_support[k-1], template=t_support[k-1])
            feasible = all(r['status'] == 'valid' for rows in support.values() for r in rows)
            result['candidates'].append(dict(quantile_numerator=k, quantile_denominator=20,
                                            threshold=threshold, feasible=feasible, support=support))
        feasible = [row for row in result['candidates'] if row['feasible']]
        if feasible:
            selected = min(feasible, key=lambda r: (abs(r['quantile_numerator']-10), r['quantile_numerator']))
            result.update(status='valid', reason='nearest_median_integer_key_lower_q_tiebreak',
                          selected_quantile_numerator=selected['quantile_numerator'],
                          selected_threshold=selected['threshold'], thresholds=[selected['threshold']])
    except ResearchStateError as error:
        result.update(status=error.status, reason=str(error))
    result['record_digest'] = digest(result)
    result['threshold_id'] = digest(result)
    return result


def refit_bundle(bundle, calibration, template, protocol, *, draw_identity, calibration_scores=None, template_scores=None):
    """All nominal/bootstrap/T2 callers share this selector and identity contract."""
    old = bundle['thresholds']
    if old.get('method_id') != METHOD:
        raise ResearchError('joint refit requires a joint-bound bundle')
    if bundle['candidate_id'] == 'M0off':
        return old
    record = select_joint_threshold(calibration,
        predict_discriminant(bundle['model'], calibration) if calibration_scores is None else calibration_scores,
        template, predict_discriminant(bundle['model'], template) if template_scores is None else template_scores,
        protocol, method_contract(), dict(model_id=bundle['model_id'], mapping_id=bundle['mapping_id'],
            candidate_key=bundle['key'], seed=bundle['seed']), old['input_bindings'], draw_identity)
    if record['status'] != 'valid':
        error = ResearchStateError(record['reason'], status=record['status'])
        error.threshold_record = record
        raise error
    return record
