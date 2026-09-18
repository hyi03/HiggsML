"""Frozen assessment with paired physical pseudo-observations across methods."""
from copy import deepcopy
import hashlib

import numpy as np
import pandas as pd

from higgsml.artifacts import digest_json
from higgsml.modeling.calibration import apply_calibration, assign_categories, fit_calibration, fit_thresholds
from higgsml.modeling.discriminants import predict_discriminant
from higgsml.errors import ResearchError, ResearchStateError
from higgsml.inference.likelihood import (build_model, paired_event_toys, profile_interval, profile_intervals,
                        reject_sample_efficiency_assessment, run_asimov, run_t2_procedure, stress_weights)
from higgsml.protocol import protocol_dict
from higgsml.resources import ordered_map
from higgsml.inference.diagnostics import signed_mu_fit, signed_mu_summary
from higgsml.inference.reporting import coverage_summary, fit_diagnostics, paired_coverage_error
from higgsml.inference.templates import build_templates
from higgsml.inference.stress import build_stress_templates,build_stress_model,sample_auxiliary,auxiliary_sampler,validate_stress_contract


def _scores(bundle, frame):
    reject_sample_efficiency_assessment(bundle)
    if bundle.get("model") is not None:
        return predict_discriminant(bundle["model"], frame)
    lookup = {r["event_id"]: r["me_score"] for r in bundle["me_scores"]}
    if any(i not in lookup for i in frame.event_id):
        raise ResearchError("ME scores do not cover frozen assessment events")
    return np.array([lookup[i] for i in frame.event_id], float)


def categorize_bundle(bundle, frame):
    reject_sample_efficiency_assessment(bundle)
    scores = _scores(bundle, frame)
    if bundle.get("mapping") is not None:
        scores = apply_calibration(bundle["mapping"], frame.m4l.to_numpy(), scores, model_id=bundle["model_id"])
    result = frame.copy()
    result["category"] = assign_categories(bundle["thresholds"], scores,
        model_id=bundle["model_id"], mapping_id=bundle["mapping_id"])
    return result


def _joint_mother(grid, bundles, mother, protocol, categorize, *, parent_role='assessment', seed_block=None):
    reject_sample_efficiency_assessment(grid, bundles)
    required = {'role','dataset','label','m4l','yield_weight','event_group_id'}
    if not required <= set(mother):
        raise ResearchError('assessment parent lacks identity/numeric columns')
    if (parent_role not in {'assessment','template'}
            or (not mother.empty and (set(mother.role) != {parent_role} or set(mother.dataset) != {protocol['dataset']}))
            or (seed_block is None and mother.empty)):
        raise ResearchError("identified nonempty assessment mother required")
    if (not set(mother.label) <= {0, 1} or (seed_block is None and set(mother.label) != {0,1})
            or not np.isfinite(mother[["m4l", "yield_weight"]].to_numpy(float)).all()):
        raise ResearchError("invalid assessment label/rates")
    process_column = 'process' if 'process' in mother else 'label'
    if mother[process_column].isna().any() or mother.event_group_id.isna().any() or (mother.groupby("event_group_id")[process_column].nunique() > 1).any():
        raise ResearchError("assessment event group spans processes")
    edges = np.array(grid["mass_edges"], float)
    if edges.ndim != 1 or len(edges) < 2 or not np.isfinite(edges).all() or not (np.diff(edges) > 0).all():
        raise ResearchError("invalid frozen assessment mass grid")
    if (mother.m4l < edges[0]).any() or (mother.m4l >= edges[-1]).any():
        raise ResearchError("assessment outside frozen half-open support")
    keys = sorted(grid["templates"]) if seed_block is None else list(seed_block.candidate_keys)
    from higgsml.inference.attribution import FAMILY, candidate_keys
    off_family = grid.get('family_id') == FAMILY
    if parent_role!='assessment' and not off_family:
        raise ResearchError('template-parent joint generation requires the registered off family')
    if off_family and seed_block is None and (set(keys)!=set(candidate_keys()) or set(bundles)!=set(keys)):
        raise ResearchError('joint off family requires all 80 identities')
    if off_family and seed_block is not None and (set(keys) != set(seed_block.candidate_keys)
            or set(bundles) != set(keys) or set(grid["templates"]) != set(keys)):
        raise ResearchError('seed block inputs must contain its exact 16 identities')
    if not off_family and ("M0" not in keys or set(bundles) != set(keys) - {"M0"}):
        raise ResearchError("all frozen methods plus M0 are required for joint pairing")
    if seed_block is not None:
        expected_sets = [{str(sample['name']) for sample in grid['templates'][key]['samples']} for key in keys]
        if any(processes != expected_sets[0] for processes in expected_sets):
            raise ResearchError('nominal candidate process identities differ')
        observed = set(mother[process_column].astype(str))
        if observed - expected_sets[0]:
            raise ResearchError('assessment has unregistered process identities')
        if mother.empty or set(mother.label) != {0,1} or expected_sets[0] - observed:
            error = ResearchStateError('assessment parent lacks expected process support', status='insufficient_statistics')
            error.joint_support = {'summary': {'seed':seed_block.seed,'block_id':seed_block.block_id,
                'qualification':'insufficient_statistics','failures':['missing_positive_process_support'],
                'expected_processes':sorted(expected_sets[0]),'observed_processes':sorted(observed),
                'missing_processes':sorted(expected_sets[0]-observed),'row_count':len(mother)},'cells':[]}
            raise error
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
    from higgsml.inference.marginal_coupling import is_marginal, diagnose_marginal_support
    if is_marginal(seed_block):
        roles = {str(sample['name']): 'signal' if sample['is_signal'] else 'background'
                 for sample in grid['templates'][keys[0]]['samples']}
        expected = {} if parent_role == 'template' else None
        for key in keys:
            samples = grid['templates'][key]['samples']
            if {str(v['name']): 'signal' if v['is_signal'] else 'background' for v in samples} != roles:
                raise ResearchError('candidate process role maps disagree')
            if expected is not None:
                for sample in samples:
                    for k in (0,1):
                        for b in range(n):
                            expected[(key,str(sample['name']),b,k)] = sample['yield'][k*n+b]
        support = diagnose_marginal_support(work,block=seed_block,category_columns=columns,
            mass_edges=edges,role_map=roles,expected_marginals=expected)
        if support['summary']['qualification'] != 'valid':
            error=ResearchStateError('marginal support insufficient',status='insufficient_statistics')
            error.joint_support=support
            raise error
        for cell in support['cells']:
            if cell['signed_sum']>0 and cell['mass_bin']+n*cell['category'] not in grid['templates'][cell['candidate_id']]['active_bins']:
                raise ResearchStateError('positive marginal outside template support',status='unsupported_assessment_support')
        return work, columns, None, support
    cells, inverse = np.unique(np.column_stack(joint), axis=0, return_inverse=True)
    if pd.DataFrame({"group": work.event_group_id.to_numpy(), "cell": inverse}).groupby("group").cell.nunique().max() > 1:
        raise ResearchStateError("one physical event spans joint observation cells; event covariance is unvalidated", status="template_stat_model_unvalidated")
    support = None
    if seed_block is not None:
        from higgsml.inference.joint_support import diagnose_joint_support
        support = diagnose_joint_support(
            work.assign(physical_weight=work.yield_weight), block=seed_block,
            category_columns=columns, mass_edges=edges, process_column=process_column)
        if support["summary"]["qualification"] != "valid":
            error = ResearchStateError("seed block joint support is insufficient",
                                       status="insufficient_statistics")
            error.joint_support = support
            raise error
    # A positive S+B cancellation cannot repair an invalid negative process rate.
    rates = {}
    for process, indices in work.groupby(process_column, sort=True).indices.items():
        rows = work.iloc[indices]
        if rows.label.nunique() != 1:
            raise ResearchError('a physical process cannot mix signal and background')
        sums = np.bincount(inverse[indices], weights=rows.yield_weight.to_numpy(), minlength=len(cells))
        if not np.isfinite(sums).all() or (sums < 0).any() or sums.sum() <= 0:
            raise ResearchStateError("assessment joint process rates are not nonnegative with positive support", status="insufficient_statistics")
        rates[str(process)] = sums
    for j, key in enumerate(keys):
        active = grid["templates"][key]["active_bins"]
        if len(set(active)) != len(active) or any(type(i) is not int or not 0 <= i < 2 * n for i in active):
            raise ResearchError("invalid template active-bin map")
        unsupported = ~np.isin(cells[:, j], active)
        if any(np.any(v[unsupported] > 0) for v in rates.values()):
            raise ResearchStateError("positive assessment support lies in a template structural-zero bin", status="unsupported_assessment_support")
        if parent_role == 'template':
            samples = {sample['name']: sample for sample in grid['templates'][key]['samples']}
            if set(samples) != set(rates):
                raise ResearchError('joint process identities differ from nominal marginals')
            for process, values in rates.items():
                marginal = np.bincount(cells[:, j], weights=values, minlength=2*n)
                signal = bool(work.loc[work[process_column].astype(str)==process,'label'].iloc[0])
                if samples[process]['is_signal']!=signal or not np.allclose(marginal, samples[process]['yield'], rtol=1e-10, atol=1e-10):
                    if seed_block is None:
                        raise ResearchStateError('joint process marginal differs from nominal template',status='insufficient_statistics')
                    raise ResearchError('joint process marginal differs from nominal template')
    result = (work, columns, (cells,inverse))
    return (*result, support) if seed_block is not None else result


def infer_assessment(grid, bundles, mother, protocol, *, layer, t1_validation, mu, count,
                     seed, prepared_id, freeze_id, categorize=None, stress_responses=None,stress_direction=0, workers=1, worker_threads=1,
                     parent_role='assessment', progress=None, seed_block=None,
                     physical_stream_id=None, auxiliary_streams=None, coupling_context=None, preflight_support=None):
    """Return per-candidate results using one shared joint-cell Poisson draw.

    Root verifies the immutable freeze artifact before granting mother access.
    This service binds those artifact identities and never adapts the mass grid.
    """
    reject_sample_efficiency_assessment(grid, bundles)
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
    joint = preflight_support or _joint_mother(grid, bundles, mother, p, categorize or categorize_bundle,
                          parent_role=parent_role, seed_block=seed_block)
    work, columns, joint_cells = joint[:3]
    joint_support = joint[3] if seed_block is not None else None
    mother_id = digest_json({"prepared_id": prepared_id, "freeze_id": freeze_id,
                            "rows": mother[["event_group_id", "label", "m4l", "yield_weight"]].to_dict("records")})
    from higgsml.inference.marginal_coupling import is_marginal, marginal_toys, METADATA
    marginal = is_marginal(seed_block)
    if marginal:
        if coupling_context is None:
            raise ResearchError('v3 coupling requires bound stream context')
        paired = marginal_toys(joint_support,block=seed_block,mass_edges=grid['mass_edges'],
            mu=mu,count=count,**coupling_context)
    else:
        paired = paired_event_toys(work, category_columns=columns, mass_edges=grid["mass_edges"],
                                  mu=mu, count=count, seed=seed, mother_id=mother_id, _joint_cells=joint_cells,
                                  parent_role=parent_role)
    pairing_id = digest_json({"mother": mother_id, "grid": grid["mass_edges"], "seed": seed,
                             "mu": mu, "count": count, "observations": paired["observations"]})
    expected_states = {"insufficient_statistics", "unsupported_assessment_support",
                       "template_stat_model_unvalidated", "inference_incomplete", "fit_failed"}
    def evaluate_candidate(task):
        key, template = task
        attempted_toys = completed_toys = 0
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
            auxiliary_stream = None if auxiliary_streams is None else auxiliary_streams[key]
            stream = (int.from_bytes(hashlib.sha256(f"aux:{seed}:{key}".encode()).digest()[:8], "big")
                      if auxiliary_stream is None else auxiliary_stream["seed"])
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
                        normal_root = seed if seed_block is None else stream
                        common_seed=int.from_bytes(hashlib.sha256(f'shared-normal:{normal_root}:{name}:{i}'.encode()).digest()[:8],'big')
                        shared[name]=np.random.default_rng(common_seed).normal(size=n_parameters)
                    aux = draw_auxiliary(rng,policy=policy,shared_normals=shared)
                    data = np.r_[observation[active], aux]
                    yield i, observation, aux, data
            def fit(task):
                nonlocal attempted_toys, completed_toys
                i, observation, aux, data = task
                row = {"toy": i, "observations": observation.tolist(), "auxiliary": aux.tolist()}
                attempted_toys += 1
                try:
                    row["intervals"] = profile_intervals(model, data, levels)
                    completed_toys += 1
                except ResearchStateError as exc:
                    if seed_block is None or exc.status not in expected_states:
                        raise
                    row.update(status=exc.status, reason=str(exc), intervals=[])
                if mu == 0 and 'diagnostics' in p:
                    row['signed_mu_diagnostic'] = (
                        signed_mu_fit(template, observation[active], p['diagnostics']['signed_mu'])
                        if stress_responses is None else
                        {'status':'not_supported_modeled_stress', 'muhat':None,
                         'reason':'Signed diagnostic fixes nominal templates; no stress/T1 nuisance profiling'})
                return row
            toys = []
            for toy_task in tasks():
                toys.append(fit(toy_task))
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
            valid = all(len(toy["intervals"]) == len(levels)
                        and all(r["status"] == "valid" for r in toy["intervals"]) for toy in toys)
            result = {"status": "valid" if valid and asimov["status"] == "valid" else "inference_incomplete",
                      "seed": template.get("seed"), "asimov": asimov,
                      "toys": {**metadata, "status": "valid" if valid else "inference_incomplete", "results": toys,
                               "mu": mu, "count": count, "seed": seed,
                               "expectation_kind": "model_self" if parent_role == "template" else "assessment", "mother_id": mother_id,
                               "freeze_id": freeze_id, "paired": True, "pairing_id": pairing_id,
                               "pairing": paired["pairing"], "auxiliary_generation": policy,
                               "physical_stream_id": physical_stream_id,
                               "auxiliary_stream_id": None if auxiliary_stream is None else auxiliary_stream["stream_id"],
                               'nuisance_truth':float(stress_direction) if stress_responses is not None else None},
                      "coverage": {}, "diagnostics": {}}
            for index, level in enumerate(levels):
                intervals = [r["intervals"][index] if len(r["intervals"]) > index
                             else {"status": r.get("status", "fit_failed"), "lower": None, "upper": None}
                             for r in toys]
                result["coverage"][str(level)] = coverage_summary(intervals, mu=mu)
                result["diagnostics"][str(level)] = fit_diagnostics(intervals, mu=mu)
            if mu == 0 and 'diagnostics' in p:
                result['diagnostics']['signed_mu'] = signed_mu_summary([t['signed_mu_diagnostic'] for t in toys])
            return key, result, attempted_toys, completed_toys
        except ResearchStateError as exc:
            if seed_block is not None and exc.status not in expected_states:
                raise
            return key, {"status": exc.status, "reason": str(exc)}, attempted_toys, completed_toys

    results = {}
    candidate_tasks = sorted(grid["templates"].items())
    attempts = {}
    for key, result, attempted_toys, completed_toys in ordered_map(
            evaluate_candidate, candidate_tasks, workers=workers, worker_threads=worker_threads):
        results[key] = result
        attempts[key] = (attempted_toys, completed_toys)
        if progress is not None:
            for _ in range(completed_toys):
                progress()
    if count >= 2 and "toys" in results.get("M0",{}):
        for key, result in results.items():
            if "toys" in result:
                result["paired_coverage_vs_M0"] = {str(level): paired_coverage_error(
                    [r["intervals"][i] for r in result["toys"]["results"]],
                    [r["intervals"][i] for r in results["M0"]["toys"]["results"]], mu=mu, pairing_id=pairing_id)
                    for i, level in enumerate(levels)}
        for network_seed in range(42, 47):
            left_key, right_key = f"M5:{network_seed}", f"M4:{network_seed}"
            if all(key in results and "toys" in results[key] for key in (left_key, right_key)):
                results[left_key]["paired_coverage_vs_M4"] = {str(level): paired_coverage_error(
                    [row["intervals"][index] for row in results[left_key]["toys"]["results"]],
                    [row["intervals"][index] for row in results[right_key]["toys"]["results"]],
                    mu=mu, pairing_id=pairing_id) for index, level in enumerate(levels)}
    if grid.get('family_id') == 'engineered19_raw_T1_m4l_off_attribution_v1':
        from higgsml.inference.attribution import SEEDS, SUBSETS, candidate_key
        import itertools
        for network_seed in SEEDS:
            for left,right in itertools.combinations(SUBSETS[1:],2):
                lk,rk=candidate_key(network_seed,left),candidate_key(network_seed,right)
                if all('toys' in results.get(key,{}) and
                       all(len(row.get('intervals', [])) == len(levels)
                           for row in results[key]['toys']['results']) for key in (lk,rk)):
                    results[lk].setdefault('paired_coverage',{})[rk] = {
                        str(level):paired_coverage_error(
                            [r['intervals'][i] for r in results[lk]['toys']['results']],
                            [r['intervals'][i] for r in results[rk]['toys']['results']],mu=mu,pairing_id=pairing_id)
                        for i,level in enumerate(levels)}
    if seed_block is not None:
        for key, result in results.items():
            toys = result.get("toys", {}).get("results", [])
            result["attempted_fits"], result["completed_fits"] = attempts[key]
            result["valid_fits"] = sum(len(row.get("intervals", [])) == len(levels)
                                       and all(v.get("status") == "valid" for v in row["intervals"])
                                       for row in toys)
            result["missing_fit_indexes"] = sorted(set(range(count)) - {
                r.get("toy") for r in toys if len(r.get("intervals", [])) == len(levels)})
            result["joint_support"] = joint_support["summary"]
            if marginal:
                result.update(METADATA)
                result['coupling_receipt'] = paired['coupling_receipt']
                for comparisons in result.get('paired_coverage', {}).values():
                    for value in comparisons.values():
                        value.update(METADATA)
    return results


def run_assessment_t2(grid, bundles, calibration, template, mother, protocol, *, layer,
                      t1_validation, mu, seed, prepared_id, freeze_id, workers=1, worker_threads=1,
                      progress=None, seed_block=None, outer_multiplicities=None):
    """Refit mappings/thresholds jointly; transform both populations on frozen bins."""
    reject_sample_efficiency_assessment(grid, bundles)
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
            thresholds = (bundle['thresholds'] if bundle.get('candidate_id')=='M0off' else
                          fit_thresholds(bootstrap, scores, p, model_id=bundle["model_id"], mapping_id=mapping_id))
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

    def evaluate(mapped_template, mapped_mother, mapping, inner_toys, inner_seed, *, preflight=False):
        fitted, templates = mapping["bundles"], {}
        category_lookup = {key: f"_t2_category_{i}" for i, key in enumerate(sorted(fitted))}
        for key, original in ({} if "_v3_preflight" in mapping else grid["templates"]).items():
            legacy_m0 = key == "M0" and key not in fitted
            source = mapped_template.assign(category=0 if legacy_m0 else mapped_template[category_lookup[key]])
            structural = None
            if original['candidate_id']=='M0off':
                from higgsml.inference.attribution import structural_evidence
                structural=structural_evidence(fitted[key],source,grid['mass_edges'])
            built = build_templates(source, mass_edges=grid["mass_edges"], mapping_id=original["mapping_id"] if legacy_m0 else fitted[key]["mapping_id"],
                                    candidate_id=original["candidate_id"], thresholds=p["templates"], categories=(0,) if legacy_m0 else tuple(original["categories"]),
                                    structural_zero_evidence=structural)
            built["seed"] = original.get("seed")
            if built["status"] != "valid":
                raise ResearchStateError("T2 template support fails on frozen grid", status="insufficient_statistics")
            templates[key] = built
        bundle_keys = {id(bundle): key for key,bundle in fitted.items()}
        def categorize(bundle, frame):
            key = bundle_keys[id(bundle)]
            return frame.assign(category=frame[category_lookup[key]])
        stream = inner_streams_by_seed.get(inner_seed)
        auxiliary_streams = None
        if seed_block is not None:
            from higgsml.inference.seed_blocks import stream_identity
            auxiliary_streams = {
                key: stream_identity(contract_digest=seed_block.pairing_contract_digest,
                    stage="t2", mu=mu, training_seed=seed_block.seed,
                    outer_index=stream["outer_index"], stream_kind="candidate_auxiliary",
                    candidate_if_auxiliary=key, toy_base_seed=seed)
                for key in seed_block.candidate_keys}
        from higgsml.inference.marginal_coupling import is_marginal
        context = None
        saved = None
        if is_marginal(seed_block):
            context = dict(stage='t2',toy_base_seed=seed,outer_index=stream['outer_index'])
            if '_v3_preflight' in mapping:
                templates,saved = mapping['_v3_preflight']
            else:
                current = {'status':'valid','mass_edges':grid['mass_edges'],'templates':templates,'family_id':grid.get('family_id')}
                saved = _joint_mother(current,fitted,mapped_mother,p,categorize,seed_block=seed_block)
                mapping['_v3_preflight'] = (templates,saved)
            if preflight:
                return {'support':saved[3]['summary'],
                        'templates_digest':digest_json(templates),
                        'marginals_digest':digest_json(saved[3])}
        result = infer_assessment({"status": "valid", "mass_edges": grid["mass_edges"], "templates": templates, 'family_id':grid.get('family_id')}, fitted,
            mapped_mother, p, layer=layer, t1_validation=t1_validation, mu=mu, count=inner_toys, seed=inner_seed,
            prepared_id=prepared_id, freeze_id=freeze_id, categorize=categorize, progress=progress,
            seed_block=seed_block, physical_stream_id=None if stream is None else stream["stream_id"],
            auxiliary_streams=auxiliary_streams,coupling_context=context,preflight_support=saved)
        return {"status": "valid" if all(r["status"] == "valid" for r in result.values()) else "inference_incomplete", "candidates": result}

    inner_seed_factory = None
    inner_streams_by_seed = {}
    if seed_block is not None:
        from higgsml.inference.seed_blocks import stream_identity
        def inner_seed_factory(outer):
            stream = stream_identity(contract_digest=seed_block.pairing_contract_digest,
                stage="t2", mu=mu, training_seed=seed_block.seed, outer_index=outer,
                stream_kind="inner_physical_poisson", toy_base_seed=seed)
            inner_streams_by_seed[stream["seed"]] = stream
            return stream["seed"]
    from higgsml.inference.marginal_coupling import is_marginal
    preflight = (lambda *args: evaluate(*args, preflight=True)) if is_marginal(seed_block) else None
    return run_t2_procedure(calibration, template, mother, preflight=preflight, fit_mapping=fit_mapping, apply_mapping=apply_mapping,
        evaluate=evaluate, outer_replicas=cfg["outer_replicas"], inner_toys=cfg["inner_toys"], seed=seed,
        workers=workers, worker_threads=worker_threads,
        record_mappings=grid.get('family_id')=='engineered19_raw_T1_m4l_off_attribution_v1',
        outer_multiplicities=outer_multiplicities, inner_seed_factory=inner_seed_factory,
        model_id=digest_json({k: b["model_id"] for k,b in bundles.items()}), mother_id=digest_json({"prepared_id":prepared_id,"freeze_id":freeze_id}))


def run_assessment_stress(grid, bundles, mother, protocol, *, layer, t1_validation, mu,
                          count, seed, prepared_id, freeze_id, kind, direction,
                          mode="omitted", reference_candidate=None,template_frame=None,workers=1,worker_threads=1):
    """Frozen artificial mother variation shared by every candidate likelihood.

    Modeled fits derive response templates on the fixed template population;
    both modes use the same frozen reference coordinate for mother variation.
    """
    reject_sample_efficiency_assessment(grid, bundles)
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
