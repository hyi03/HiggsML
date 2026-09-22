"""Paired fixed-network MC bootstrap for the registered M5/M4 endpoint."""
from __future__ import annotations

from copy import deepcopy

import numpy as np
import pandas as pd

from higgsml.artifacts import digest_json
from higgsml.errors import ResearchError, ResearchStateError
from higgsml.inference.likelihood import build_model, run_asimov
from higgsml.inference.templates import build_templates
from higgsml.modeling.calibration import apply_calibration, assign_categories, fit_calibration, fit_thresholds
from higgsml.modeling.discriminants import predict_discriminant
from higgsml.resources import ordered_map


def _replica_bundle(bundle):
    """Detach replica-local calibration state without copying the trained model."""
    value = dict(bundle)
    for field in ("mapping", "thresholds"):
        if field in value:
            value[field] = deepcopy(value[field])
    return value


def mass_off_mc_bootstrap(grid, bundles, calibration, template, protocol, *, t1_validation,
                          workers=1, worker_threads=1, progress=None):
    """Full registered event-group reconstruction; failed replicas are not replaced."""
    from higgsml.inference.attribution import BUDGETS, FAMILY, candidate_keys, structural_evidence, summarize
    from higgsml.inference.attribution_workflow import asimov_records
    from higgsml.inference.assessment import categorize_bundle
    if set(bundles) != set(candidate_keys()) or set(grid['templates']) != set(candidate_keys()):
        raise ResearchError('MC bootstrap requires the complete off family')
    if (set(calibration.role) != {'calibration'} or set(template.role) != {'template'}
            or set(calibration.event_group_id) & set(template.event_group_id)):
        raise ResearchError('MC bootstrap role/group isolation failed')
    from higgsml.modeling.joint_support import bootstrap_counts, refit_bundle, QUALIFICATION, selection_diagnostics
    contract_digest = grid.get('analysis_contract_digest')
    if any(b.get('thresholds',{}).get('analysis_contract_digest') != contract_digest for b in bundles.values()):
        raise ResearchError('bootstrap mixed threshold methods')
    budget = BUDGETS['mc_bootstrap']
    rng = np.random.default_rng(budget['seed'])
    calibration_groups = np.asarray(sorted(calibration.event_group_id.astype(str).unique()))
    template_groups = np.asarray(sorted(template.event_group_id.astype(str).unique()))
    if not len(calibration_groups) or not len(template_groups):
        raise ResearchError('bootstrap role has no physical event groups')

    def tasks():
        for index in range(budget['replicas']):
            yield (index,
                   bootstrap_counts(calibration_groups, contract_digest, index, 'calibration') if contract_digest else rng.multinomial(len(calibration_groups), np.full(len(calibration_groups), 1 / len(calibration_groups))),
                   bootstrap_counts(template_groups, contract_digest, index, 'template') if contract_digest else rng.multinomial(len(template_groups), np.full(len(template_groups), 1 / len(template_groups))))

    def finish(task):
        index, calibration_counts, template_counts = task
        row = {'replica':index,'status':'bootstrap_incomplete','candidate_states':{}}
        completed_candidates = 0
        try:
            c,cm = _resample_groups_from_counts(calibration,calibration_groups,calibration_counts,f'c{index}')
            t,tm = _resample_groups_from_counts(template,template_groups,template_counts,f't{index}')
            row.update(calibration_group_multiplicities=cm,template_group_multiplicities=tm,mappings={})
            if contract_digest:
                row['counts_digests'] = {'calibration':digest_json(cm),'template':digest_json(tm)}
            fitted,built = {},{}
            for key,bundle in bundles.items():
                try:
                    value = _replica_bundle(bundle)
                    if value['transform'] != 'raw' or value['mapping'] is not None:
                        raise ResearchError('off bootstrap must retain raw mapping')
                    if contract_digest:
                        value['thresholds'] = refit_bundle(value,c,t,protocol,draw_identity={'stage':'mc_bootstrap','replica':index})
                    elif value['candidate_id'] != 'M0off':
                        value['thresholds'] = fit_thresholds(c,predict_discriminant(value['model'],c),protocol,
                                                            model_id=value['model_id'],mapping_id=value['mapping_id'])
                    frame = categorize_bundle(value,t)
                    structural = structural_evidence(value,frame,grid['mass_edges']) if value['candidate_id']=='M0off' else None
                    artifact = build_templates(frame,mass_edges=grid['mass_edges'],mapping_id=value['mapping_id'],
                                               candidate_id=value['candidate_id'],thresholds=protocol['templates'],
                                               structural_zero_evidence=structural)
                    artifact['seed'] = value['seed']
                    row['candidate_states'][key] = artifact['status']
                    row['mappings'][key] = {'mapping_id':value['mapping_id'],'thresholds':value['thresholds']}
                    if artifact['status']=='valid': fitted[key],built[key] = value,artifact
                except ResearchError as error:
                    if contract_digest and not isinstance(error, ResearchStateError):
                        raise
                    row['candidate_states'][key] = {'status':error.status,'reason':str(error),
                        **({'threshold_record':error.threshold_record} if hasattr(error,'threshold_record') else {})}
                completed_candidates += 1
            if set(built)==set(candidate_keys()):
                records,results = asimov_records({'templates':built},fitted,protocol,t1_validation,f'replica:{index}')
                summary = summarize(records,require_auc=False)
                row.update(status=summary['status'],summary=summary,inference=results)
        except ResearchError as error:
            if contract_digest and not isinstance(error, ResearchStateError):
                raise
            row.update(status=error.status,reason=str(error))
        return row, completed_candidates

    replicas = []
    for row, completed_candidates in ordered_map(
            finish, tasks(), workers=workers, worker_threads=worker_threads):
        replicas.append(row)
        if progress is not None:
            for _ in range(completed_candidates):
                progress()
    valid = [r for r in replicas if r['status']=='valid']
    complete = len(valid)==budget['replicas']
    def intervals(values):
        return {'interval68':np.quantile(values,[.16,.84],method='linear').tolist() if complete else None,
                'interval95':np.quantile(values,[.025,.975],method='linear').tolist() if complete else None}
    uncertainty = {'contributions':[], 'interactions':[], 'pairwise':[], 'ranking':[]}
    if valid:
        for field,target in (('contributions','contributions'),('interactions','interactions')):
            for i,entry in enumerate(valid[0]['summary'][field]):
                identity = {k:v for k,v in entry.items() if k in {'group','pair','conditioning_subset'}}
                uncertainty[target].append({**identity,**intervals([r['summary'][field][i]['median'] for r in valid])})
        for i,entry in enumerate(valid[0]['summary']['pairwise_comparisons']):
            uncertainty['pairwise'].append({'left':entry['left'],'right':entry['right'],
                **{field:intervals([r['summary']['pairwise_comparisons'][i][field]['median'] for r in valid])
                   for field in ('delta_width68_left_minus_right','relative_improvement_left_vs_right')}})
        for subset in (r['subset'] for r in valid[0]['summary']['ranking_stability']):
            uncertainty['ranking'].append({'subset':subset,'estimand':'rank_of_five_seed_median_width68',**intervals([
                next(x['rank_of_median_width68'] for x in r['summary']['ranking_stability'] if x['subset']==subset) for r in valid])})
    return {**({'analysis_contract_digest':contract_digest, **QUALIFICATION,
             'selection_diagnostics':selection_diagnostics([
                 m['thresholds'] for r in replicas for m in r.get('mappings',{}).values()] + [
                 state['threshold_record'] for r in replicas for state in r['candidate_states'].values()
                 if isinstance(state,dict) and 'threshold_record' in state]),
             'numpy_version':np.__version__, 'group_digests':{
                 'calibration':digest_json(calibration_groups.tolist()), 'template':digest_json(template_groups.tolist())}} if contract_digest else {}),
            'family_id':FAMILY,'status':'valid' if complete else 'bootstrap_incomplete',
            'planned_replicas':budget['replicas'],'valid_replicas':len(valid),'failed_replicas':budget['replicas']-len(valid),
            'seed':budget['seed'],'mass_grid':grid['mass_edges'],'replicas':replicas,'uncertainty':uncertainty,
            'interval_scope':'event_MC_only_fixed_network_not_total_uncertainty',
            'successful_replica_interpretation':'conditional_diagnostic_only' if not complete else ('exploratory_percentile_spread_selection_aware_coverage_unvalidated' if contract_digest else 'registered_percentile')}


def _resample_groups(frame, rng, label):
    groups = np.asarray(sorted(frame.event_group_id.astype(str).unique()))
    if not len(groups):
        raise ResearchError("bootstrap role has no physical event groups")
    counts = rng.multinomial(len(groups), np.full(len(groups), 1 / len(groups)))
    return _resample_groups_from_counts(frame, groups, counts, label)


def _resample_groups_from_counts(frame, groups, counts, label):
    parts = []
    by_group = {str(key): value for key, value in frame.groupby(frame.event_group_id.astype(str), sort=False)}
    for group, count in zip(groups, counts):
        source = by_group[group]
        for copy_index in range(int(count)):
            part = source.copy()
            part["event_group_id"] = f"{label}:{group}:{copy_index}"
            parts.append(part)
    if not parts:
        raise ResearchStateError("bootstrap draw is empty", status="insufficient_statistics")
    return pd.concat(parts, ignore_index=True), {str(group): int(count) for group, count in zip(groups, counts)}


def primary_mc_bootstrap(grid, bundles, calibration, template, protocol, *, replicas, seed, t1_validation):
    if type(replicas) is not int or replicas < 1 or type(seed) is not int:
        raise ResearchError("MC bootstrap requires explicit positive replicas and integer seed")
    expected = {f"M{candidate}:{network_seed}" for candidate in (4, 5) for network_seed in range(42, 47)}
    if not expected <= set(bundles) or not expected <= set(grid.get("templates", {})):
        raise ResearchError("MC bootstrap requires all five paired M4/M5 models")
    if set(calibration.role) != {"calibration"} or set(template.role) != {"template"}:
        raise ResearchError("MC bootstrap roles are not isolated")
    if set(calibration.event_group_id) & set(template.event_group_id):
        raise ResearchError("calibration and template bootstrap groups overlap")
    rng = np.random.default_rng(seed)
    output = []
    for replica in range(replicas):
        try:
            calibration_draw, calibration_counts = _resample_groups(calibration, rng, f"c{replica}")
            template_draw, template_counts = _resample_groups(template, rng, f"t{replica}")
            widths = {}
            mappings = {}
            for key in sorted(expected):
                original = bundles[key]
                if original.get("transform") != "physical" or original.get("model") is None:
                    raise ResearchError("M4/M5 bootstrap requires physical-CDF neural bundles")
                bundle = _replica_bundle(original)
                raw_calibration_scores = predict_discriminant(bundle["model"], calibration_draw)
                mapping = fit_calibration(calibration_draw, raw_calibration_scores, protocol,
                                          target="physical", model_id=bundle["model_id"])
                calibrated = apply_calibration(mapping, calibration_draw.m4l.to_numpy(),
                                               raw_calibration_scores, model_id=bundle["model_id"])
                thresholds = fit_thresholds(calibration_draw, calibrated, protocol,
                                            model_id=bundle["model_id"], mapping_id=mapping["mapping_id"])
                raw_template_scores = predict_discriminant(bundle["model"], template_draw)
                template_scores = apply_calibration(mapping, template_draw.m4l.to_numpy(),
                                                    raw_template_scores, model_id=bundle["model_id"])
                categorized = template_draw.assign(category=assign_categories(
                    thresholds, template_scores, model_id=bundle["model_id"], mapping_id=mapping["mapping_id"]))
                built = build_templates(categorized, mass_edges=grid["mass_edges"],
                                        mapping_id=mapping["mapping_id"], candidate_id=key.split(":", 1)[0],
                                        thresholds=protocol["templates"], categories=(0, 1))
                if built["status"] != "valid":
                    raise ResearchStateError("bootstrap template fails frozen support", status="insufficient_statistics")
                built["seed"] = int(key.rsplit(":", 1)[1])
                built_model = build_model(built, layer="T1", t1_validation=t1_validation,
                                          mu_max=protocol["inference"]["mu_bounds"][1])
                asimov = run_asimov(built, protocol=protocol, layer="T1", t1_validation=t1_validation,
                                    injections=[1.0], _built_model=built_model)
                interval = asimov["results"][0]["intervals"][0]
                if interval.get("status") != "valid" or interval.get("width", 0) <= 0:
                    raise ResearchStateError("bootstrap interval is unavailable", status="fit_failed")
                widths[key] = float(interval["width"])
                mappings[key] = mapping["mapping_id"]
            paired = []
            for network_seed in range(42, 47):
                left, right = widths[f"M4:{network_seed}"], widths[f"M5:{network_seed}"]
                paired.append({"seed": network_seed, "M4_width68": left, "M5_width68": right,
                               "relative_improvement": 1 - right / left})
            output.append({"replica": replica, "status": "valid", "paired_seeds": paired,
                           "median_relative_improvement": float(np.median([row["relative_improvement"] for row in paired])),
                           "mapping_ids": mappings, "calibration_group_multiplicities": calibration_counts,
                           "template_group_multiplicities": template_counts})
        except ResearchStateError as error:
            output.append({"replica": replica, "status": error.status, "reason": str(error)})
    valid = [row for row in output if row["status"] == "valid"]
    values = np.asarray([row["median_relative_improvement"] for row in valid], float)
    complete = len(valid) == replicas
    summary = {"status": "valid" if complete else "bootstrap_incomplete", "planned_replicas": replicas,
               "valid_replicas": len(valid), "failed_replicas": replicas - len(valid),
               "interval_definition": "percentile_fixed_network_calibration_and_template_group_bootstrap",
               "median": float(np.median(values)) if len(values) else None,
               "interval68": np.quantile(values, [.16, .84]).tolist() if complete else None,
               "interval95": np.quantile(values, [.025, .975]).tolist() if complete else None}
    result = {"schema_version": "h4l-primary-mc-bootstrap-v1", "status": summary["status"],
              "seed": seed, "fixed": "trained_networks_train_and_validation_roles",
              "randomized": "paired_calibration_and_template_physical_event_groups",
              "mass_grid": list(grid["mass_edges"]), "replicas": output, "summary": summary}
    result["bootstrap_id"] = digest_json(result)
    return result
