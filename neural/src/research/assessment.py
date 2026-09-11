"""Frozen assessment with paired physical pseudo-observations across methods."""
from copy import deepcopy
import hashlib

import numpy as np
import pandas as pd

from .artifacts import digest_json
from .calibration import apply_calibration, assign_categories, fit_calibration, fit_thresholds
from .discriminants import predict_discriminant
from .errors import ResearchError, ResearchStateError
from .inference import build_model, paired_event_toys, profile_interval, profile_intervals, run_asimov, run_t2_procedure, stress_weights
from .protocol import protocol_dict
from .resources import ordered_map
from .diagnostics import signed_mu_fit, signed_mu_summary
from .reporting import coverage_summary, fit_diagnostics, paired_coverage_error
from .templates import build_templates
from .stress import build_stress_templates,build_stress_model,sample_auxiliary,auxiliary_sampler,validate_stress_contract


def _scores(bundle, frame):
    if bundle.get("model") is not None:
        return predict_discriminant(bundle["model"], frame)
    lookup = {r["event_id"]: r["me_score"] for r in bundle["me_scores"]}
    if any(i not in lookup for i in frame.event_id):
        raise ResearchError("ME scores do not cover frozen assessment events")
    return np.array([lookup[i] for i in frame.event_id], float)


def categorize_bundle(bundle, frame):
    scores = _scores(bundle, frame)
    if bundle.get("mapping") is not None:
        scores = apply_calibration(bundle["mapping"], frame.m4l.to_numpy(), scores, model_id=bundle["model_id"])
    result = frame.copy()
    result["category"] = assign_categories(bundle["thresholds"], scores,
        model_id=bundle["model_id"], mapping_id=bundle["mapping_id"])
    return result


def _joint_mother(grid, bundles, mother, protocol, categorize):
    if mother.empty or set(mother.role) != {"assessment"} or set(mother.dataset) != {protocol["dataset"]}:
        raise ResearchError("identified nonempty assessment mother required")
    if not mother.label.isin([0, 1]).all() or not np.isfinite(mother[["m4l", "yield_weight"]].to_numpy(float)).all():
        raise ResearchError("invalid assessment label/rates")
    if mother.event_group_id.isna().any() or (mother.groupby("event_group_id").label.nunique() > 1).any():
        raise ResearchError("assessment event group spans processes")
    edges = np.array(grid["mass_edges"], float)
    if edges.ndim != 1 or len(edges) < 2 or not np.isfinite(edges).all() or not (np.diff(edges) > 0).all():
        raise ResearchError("invalid frozen assessment mass grid")
    if (mother.m4l < edges[0]).any() or (mother.m4l >= edges[-1]).any():
        raise ResearchError("assessment outside frozen half-open support")
    keys = sorted(grid["templates"])
    if "M0" not in keys or set(bundles) != set(keys) - {"M0"}:
        raise ResearchError("all frozen methods plus M0 are required for joint pairing")
    n = len(edges) - 1
    mass_bin = np.searchsorted(edges, mother.m4l, side="right") - 1
    work = mother.copy()
    columns, joint = {}, []
    for index, key in enumerate(keys):
        template = grid["templates"][key]
        allowed_categories = ([0], [0, 1]) if key == "M0" else ([0, 1],)
        if template["mass_edges"] != edges.tolist() or template.get("categories") not in allowed_categories:
            raise ResearchError("candidate template grid/category contract differs")
        if key != "M0" and template["mapping_id"] != bundles[key]["mapping_id"]:
            raise ResearchError("assessment mapping differs from frozen template")
        mapped = mother.assign(category=0) if key == "M0" else categorize(bundles[key], mother.copy())
        if not mapped.index.equals(mother.index) or len(mapped) != len(mother):
            raise ResearchError("categorization changed assessment event order")
        if "event_id" in mother and not mapped.event_id.equals(mother.event_id):
            raise ResearchError("categorization changed assessment identity")
        if not mapped.category.isin([0, 1]).all():
            raise ResearchError("assessment category must be 0 or 1")
        column = f"_assessment_category_{index}"
        columns[key] = column
        work[column] = mapped.category.to_numpy(int)
        joint.append(mass_bin + n * work[column].to_numpy())
    cells, inverse = np.unique(np.column_stack(joint), axis=0, return_inverse=True)
    if pd.DataFrame({"group": work.event_group_id.to_numpy(), "cell": inverse}).groupby("group").cell.nunique().max() > 1:
        raise ResearchStateError("one physical event spans joint observation cells; event covariance is unvalidated", status="template_stat_model_unvalidated")
    # A positive S+B cancellation cannot repair an invalid negative process rate.
    rates = {}
    for label in (0, 1):
        sums = np.bincount(inverse, weights=work.yield_weight.to_numpy() * (work.label.to_numpy() == label), minlength=len(cells))
        if not np.isfinite(sums).all() or (sums < 0).any() or sums.sum() <= 0:
            raise ResearchStateError("assessment joint process rates are not nonnegative with positive support", status="insufficient_statistics")
        rates[label] = sums
    for j, key in enumerate(keys):
        active = grid["templates"][key]["active_bins"]
        if len(set(active)) != len(active) or any(type(i) is not int or not 0 <= i < 2 * n for i in active):
            raise ResearchError("invalid template active-bin map")
        unsupported = ~np.isin(cells[:, j], active)
        if any(np.any(v[unsupported] > 0) for v in rates.values()):
            raise ResearchStateError("positive assessment support lies in a template structural-zero bin", status="unsupported_assessment_support")
    return work, columns, (cells,inverse)


def infer_assessment(grid, bundles, mother, protocol, *, layer, t1_validation, mu, count,
                     seed, prepared_id, freeze_id, categorize=None, stress_responses=None,stress_direction=0, workers=1, worker_threads=1):
    """Return per-candidate results using one shared joint-cell Poisson draw.

    Root verifies the immutable freeze artifact before granting mother access.
    This service binds those artifact identities and never adapts the mass grid.
    """
    p = protocol_dict(protocol)
    cfg = p["inference"]
    if not prepared_id or not freeze_id or grid.get("status") != "valid":
        raise ResearchError("frozen valid grid and prepared/freeze identities required")
    if type(count) is not int or not 1 <= count <= cfg["toy_count"] or not cfg["mu_bounds"][0] <= mu <= cfg["mu_bounds"][1]:
        raise ResearchError("assessment exceeds frozen injection/toy budget")
    policy = cfg["auxiliary_generation"]
    if policy not in {"fixed", "regenerated"}:
        raise ResearchError("unsupported auxiliary generation policy")
    levels = cfg["confidence_levels"]
    if levels != [.68, .95]:
        raise ResearchError("unsupported frozen confidence levels")
    work, columns, joint_cells = _joint_mother(grid, bundles, mother, p, categorize or categorize_bundle)
    mother_id = digest_json({"prepared_id": prepared_id, "freeze_id": freeze_id,
                            "rows": mother[["event_group_id", "label", "m4l", "yield_weight"]].to_dict("records")})
    paired = paired_event_toys(work, category_columns=columns, mass_edges=grid["mass_edges"],
                              mu=mu, count=count, seed=seed, mother_id=mother_id, _joint_cells=joint_cells)
    pairing_id = digest_json({"mother": mother_id, "grid": grid["mass_edges"], "seed": seed,
                             "mu": mu, "count": count, "observations": paired["observations"]})
    results = {}
    for key, template in sorted(grid["templates"].items()):
        try:
            model, metadata = (build_stress_model(template,stress_responses[key],protocol=p,layer=layer,t1_validation=t1_validation,mu_max=cfg['mu_bounds'][1])
                               if stress_responses is not None else
                               build_model(template, layer=layer, t1_validation=t1_validation, mu_max=cfg["mu_bounds"][1]))
            pars = model.config.suggested_init()
            pars[model.config.poi_index] = float(mu)
            if stress_responses is not None:
                if stress_direction not in {-1,1}:
                    raise ResearchError('modeled stress needs a registered nuisance endpoint')
                pars[model.config.par_map[metadata['stress_nuisance']]['slice']]=[float(stress_direction)]
            # Candidate-specific streams leave the shared physical observations intact.
            stream = int.from_bytes(hashlib.sha256(f"aux:{seed}:{key}".encode()).digest()[:8], "big")
            rng = np.random.default_rng(stream)
            observations = np.asarray(paired["observations"][key], int)
            active = template["active_bins"]
            inactive = sorted(set(range(observations.shape[1])) - set(active))
            if inactive and observations[:, inactive].any():
                raise ResearchStateError("positive observations outside active template support", status="unsupported_assessment_support")
            draw_auxiliary = auxiliary_sampler(model,pars)
            normal_layout = [(name,model.config.param_set(name).n_parameters) for name in model.config.auxdata_order
                             if model.config.param_set(name).pdf_type=='normal']
            def tasks():
                for i, observation in enumerate(observations):
                    shared={}
                    for name,n_parameters in normal_layout:
                        common_seed=int.from_bytes(hashlib.sha256(f'shared-normal:{seed}:{name}:{i}'.encode()).digest()[:8],'big')
                        shared[name]=np.random.default_rng(common_seed).normal(size=n_parameters)
                    aux = draw_auxiliary(rng,policy=policy,shared_normals=shared)
                    data = np.r_[observation[active], aux]
                    yield i, observation, aux, data
            def fit(task):
                i, observation, aux, data = task
                row = {"toy": i, "observations": observation.tolist(), "auxiliary": aux.tolist(),
                       "intervals": profile_intervals(model, data, levels)}
                if mu == 0 and 'diagnostics' in p:
                    row['signed_mu_diagnostic'] = (
                        signed_mu_fit(template, observation[active], p['diagnostics']['signed_mu'])
                        if stress_responses is None else
                        {'status':'not_supported_modeled_stress', 'muhat':None,
                         'reason':'Signed diagnostic fixes nominal templates; no stress/T1 nuisance profiling'})
                return row
            toys = list(ordered_map(fit, tasks(), workers=workers, worker_threads=worker_threads))
            if stress_responses is None:
                asimov = run_asimov(template, protocol=p, layer=layer, t1_validation=t1_validation, injections=[mu], _built_model=(model,metadata))
            else:
                expected=np.asarray(model.expected_data(pars),float)
                intervals=profile_intervals(model,expected,levels)
                nominal_pars=list(pars)
                nominal_pars[model.config.par_map[metadata['stress_nuisance']]['slice']]=[0.]
                nominal_expected=np.asarray(model.expected_data(nominal_pars),float)
                nominal_intervals=profile_intervals(model,nominal_expected,levels)
                asimov={**metadata,'status':'valid' if all(v['status']=='valid' for v in intervals+nominal_intervals) else 'inference_incomplete',
                    'expectation_kind':'modeled_artificial_stress_self_asimov',
                    'nuisance_truth':float(stress_direction),'results':[{'mu':float(mu),'intervals':intervals}],
                    'nominal_nuisance_asimov':{'nuisance_truth':0.,'mu':float(mu),
                        'status':'valid' if all(v['status']=='valid' for v in nominal_intervals) else 'inference_incomplete',
                        'intervals':nominal_intervals}}
            valid = all(r["status"] == "valid" for toy in toys for r in toy["intervals"])
            result = {"status": "valid" if valid and asimov["status"] == "valid" else "inference_incomplete",
                      "seed": template.get("seed"), "asimov": asimov,
                      "toys": {**metadata, "status": "valid" if valid else "inference_incomplete", "results": toys,
                               "mu": mu, "count": count, "seed": seed, "expectation_kind": "assessment", "mother_id": mother_id,
                               "freeze_id": freeze_id, "paired": True, "pairing_id": pairing_id,
                               "pairing": paired["pairing"], "auxiliary_generation": policy,
                               'nuisance_truth':float(stress_direction) if stress_responses is not None else None},
                      "coverage": {}, "diagnostics": {}}
            for index, level in enumerate(levels):
                intervals = [r["intervals"][index] for r in toys]
                result["coverage"][str(level)] = coverage_summary(intervals, mu=mu)
                result["diagnostics"][str(level)] = fit_diagnostics(intervals, mu=mu)
            if mu == 0 and 'diagnostics' in p:
                result['diagnostics']['signed_mu'] = signed_mu_summary([t['signed_mu_diagnostic'] for t in toys])
            results[key] = result
        except ResearchStateError as exc:
            results[key] = {"status": exc.status, "reason": str(exc)}
    if count >= 2 and "toys" in results["M0"]:
        for key, result in results.items():
            if "toys" in result:
                result["paired_coverage_vs_M0"] = {str(level): paired_coverage_error(
                    [r["intervals"][i] for r in result["toys"]["results"]],
                    [r["intervals"][i] for r in results["M0"]["toys"]["results"]], mu=mu, pairing_id=pairing_id)
                    for i, level in enumerate(levels)}
    return results


def run_assessment_t2(grid, bundles, calibration, template, mother, protocol, *, layer,
                      t1_validation, mu, seed, prepared_id, freeze_id, workers=1, worker_threads=1):
    """Refit mappings/thresholds jointly; transform both populations on frozen bins."""
    p = protocol_dict(protocol)
    cfg = p["inference"]
    if grid.get("status") != "valid" or not prepared_id or not freeze_id:
        raise ResearchError("T2 requires a frozen valid G1 grid and artifact identities")

    # Only raw model/ME scores are invariant to bootstrap weights. Cache these
    # for the exact three populations in this call, never mappings/thresholds.
    score_cache = {}
    cache_bytes = 0
    for key, bundle in sorted(bundles.items()):
        size = sum(8*len(f)+f.event_id.memory_usage(index=False,deep=True) for f in (calibration,template,mother))
        if cache_bytes + size > 64*1024*1024:
            break
        tables = []
        try:
            for population in (calibration,template,mother):
                if population.event_id.duplicated().any():
                    raise ResearchError('T2 score cache requires unique event identities')
                tables.append(pd.Series(_scores(bundle,population), index=population.event_id))
        except ResearchError:
            # Preserve the original per-replica error timing and seed consumption.
            continue
        score_cache[key] = pd.concat(tables)
        if score_cache[key].index.duplicated().any():
            raise ResearchError('T2 event identities cross populations')
        cache_bytes += score_cache[key].memory_usage(index=True,deep=True)

    def raw_scores(key, bundle, frame):
        if key not in score_cache:
            return _scores(bundle,frame)
        return score_cache[key].loc[frame.event_id].to_numpy()

    def fit_mapping(bootstrap):
        fitted = {}
        for key, original in sorted(bundles.items()):
            bundle = deepcopy(original)
            scores = raw_scores(key, bundle, bootstrap)
            mapping = None
            if bundle.get("mapping") is not None:
                mapping = fit_calibration(bootstrap, scores, p, target=bundle["mapping"]["target"], model_id=bundle["model_id"])
                scores = apply_calibration(mapping, bootstrap.m4l.to_numpy(), scores, model_id=bundle["model_id"])
            mapping_id = mapping["mapping_id"] if mapping else "raw:" + bundle["model_id"]
            thresholds = fit_thresholds(bootstrap, scores, p, model_id=bundle["model_id"], mapping_id=mapping_id)
            bundle.update(mapping=mapping, mapping_id=mapping_id, thresholds=thresholds)
            fitted[key] = bundle
        return {"bundles": fitted, "mapping_id": digest_json(fitted)}

    def apply_mapping(mapping, frame):
        result = frame.copy()
        for i, (key, bundle) in enumerate(sorted(mapping["bundles"].items())):
            scores = raw_scores(key,bundle,frame)
            if bundle.get('mapping') is not None:
                scores = apply_calibration(bundle['mapping'],frame.m4l.to_numpy(),scores,model_id=bundle['model_id'])
            result[f"_t2_category_{i}"] = assign_categories(bundle['thresholds'],scores,
                model_id=bundle['model_id'],mapping_id=bundle['mapping_id'])
        return result

    def evaluate(mapped_template, mapped_mother, mapping, inner_toys, inner_seed):
        fitted, templates = mapping["bundles"], {}
        category_lookup = {key: f"_t2_category_{i}" for i, key in enumerate(sorted(fitted))}
        for key, original in grid["templates"].items():
            source = mapped_template.assign(category=0 if key == "M0" else mapped_template[category_lookup[key]])
            built = build_templates(source, mass_edges=grid["mass_edges"], mapping_id=fitted[key]["mapping_id"] if key != "M0" else original["mapping_id"],
                                    candidate_id=original["candidate_id"], thresholds=p["templates"], categories=(0,) if key == "M0" else (0, 1))
            built["seed"] = original.get("seed")
            if built["status"] != "valid":
                raise ResearchStateError("T2 template support fails on frozen grid", status="insufficient_statistics")
            templates[key] = built
        bundle_keys = {id(bundle): key for key,bundle in fitted.items()}
        def categorize(bundle, frame):
            key = bundle_keys[id(bundle)]
            return frame.assign(category=frame[category_lookup[key]])
        result = infer_assessment({"status": "valid", "mass_edges": grid["mass_edges"], "templates": templates}, fitted,
            mapped_mother, p, layer=layer, t1_validation=t1_validation, mu=mu, count=inner_toys, seed=inner_seed,
            prepared_id=prepared_id, freeze_id=freeze_id, categorize=categorize)
        return {"status": "valid" if all(r["status"] == "valid" for r in result.values()) else "inference_incomplete", "candidates": result}

    return run_t2_procedure(calibration, template, mother, fit_mapping=fit_mapping, apply_mapping=apply_mapping,
        evaluate=evaluate, outer_replicas=cfg["outer_replicas"], inner_toys=cfg["inner_toys"], seed=seed,
        workers=workers, worker_threads=worker_threads,
        model_id=digest_json({k: b["model_id"] for k,b in bundles.items()}), mother_id=digest_json({"prepared_id":prepared_id,"freeze_id":freeze_id}))


def run_assessment_stress(grid, bundles, mother, protocol, *, layer, t1_validation, mu,
                          count, seed, prepared_id, freeze_id, kind, direction,
                          mode="omitted", reference_candidate=None,template_frame=None,workers=1,worker_threads=1):
    """Frozen artificial mother variation shared by every candidate likelihood.

    Modeled fits derive response templates on the fixed template population;
    both modes use the same frozen reference coordinate for mother variation.
    """
    if mode not in {'modeled','omitted'}:
        raise ResearchError("unknown stress fit mode")
    stress_contract=validate_stress_contract(protocol)
    if direction not in stress_contract['allowed_directions']:
        raise ResearchError('stress direction outside frozen contract')
    if mode=='modeled' and (template_frame is None or template_frame.empty or set(template_frame.role)!={'template'}):
        raise ResearchStateError('modeled stress requires its bound template population',status='stress_model_unvalidated')
    varied = mother.copy()
    if kind in {"score", "correlation"}:
        reference_candidate=reference_candidate or stress_contract['reference_candidate']
        if reference_candidate != stress_contract['reference_candidate']:
            raise ResearchError('stress reference candidate differs from frozen protocol')
        if reference_candidate not in bundles:
            raise ResearchError("score/correlation stress requires one frozen reference candidate")
        bundle = bundles[reference_candidate]
        scores = _scores(bundle, mother)
        if bundle.get("mapping") is not None:
            scores = apply_calibration(bundle["mapping"], mother.m4l.to_numpy(), scores, model_id=bundle["model_id"])
        varied["reference_score"] = scores
        reference_id = digest_json({"model_id":bundle["model_id"],"mapping_id":bundle["mapping_id"]})
    else:
        reference_id = digest_json({"freeze_id":freeze_id,"coordinate":kind})
    varied["yield_weight"] = stress_weights(varied,kind=kind,direction=direction,reference_mapping_id=reference_id)
    responses=None
    if mode=='modeled':
        source=template_frame.copy()
        if set(source.event_group_id)&set(mother.event_group_id):
            raise ResearchError('stress template and assessment groups overlap')
        if kind in {'score','correlation'}:
            scores=_scores(bundle,source)
            if bundle.get('mapping') is not None:
                scores=apply_calibration(bundle['mapping'],source.m4l.to_numpy(),scores,model_id=bundle['model_id'])
            source['reference_score']=scores
        responses={}
        for key,template in grid['templates'].items():
            mapped=source.assign(category=0) if key=='M0' else categorize_bundle(bundles[key],source)
            responses[key]=build_stress_templates(mapped,template,kind=kind,reference_mapping_id=reference_id,
                                                 protocol=protocol,thresholds=protocol_dict(protocol)['templates'])
    results = infer_assessment(grid,bundles,varied,protocol,layer=layer,t1_validation=t1_validation,
        mu=mu,count=count,seed=seed,prepared_id=prepared_id,freeze_id=freeze_id,
        stress_responses=responses,stress_direction=direction,workers=workers,worker_threads=worker_threads)
    scenario = {"kind":kind,"direction":direction,"mode":mode,"reference_candidate":reference_candidate,
                "reference_mapping_id":reference_id,"source":"artificial_pressure_not_physics_systematic",
                'modeled_response_ids':{key:value['stress_id'] for key,value in responses.items()} if responses is not None else None}
    for key,result in results.items():
        result["stress"] = scenario
        if responses is not None:
            result['stress_response']=responses[key]
        if "toys" in result:
            result["toys"]["expectation_kind"] = 'assessment_with_modeled_artificial_stress' if mode=='modeled' else "mismatch"
    return results
