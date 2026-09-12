"""Pinned pyhf likelihood, bounded profile intervals and explicit toy sources."""
from __future__ import annotations

import importlib
import numpy as np
from scipy.optimize import brentq
from scipy.stats import chi2

from .errors import ResearchError, ResearchStateError
from .diagnostics import signed_mu_fit, signed_mu_summary
from .resources import ordered_map


def _is_sample_efficiency_payload(value):
    if isinstance(value, dict):
        if (value.get("schema_version") in {"research-discriminant-v2", "h4l-experiment-lineage-v1"}
                or "experiment_lineage" in value):
            return True
        return any(_is_sample_efficiency_payload(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_is_sample_efficiency_payload(item) for item in value)
    return False


def reject_sample_efficiency_assessment(*values):
    if any(_is_sample_efficiency_payload(value) for value in values):
        raise ResearchError("sample-efficiency assessment and mismatch paths are not enabled in M3",
                            status="training_subset_binding_mismatch")


def require_pyhf():
    try:
        pyhf = importlib.import_module("pyhf")
    except ImportError as exc:
        raise ResearchStateError("Install the optional research pyhf environment", status="dependency_missing") from exc
    if pyhf.__version__ != "0.7.6":
        raise ResearchStateError("Research requires pyhf 0.7.6", status="dependency_version_mismatch")
    pyhf.set_backend("numpy", precision="64b")
    return pyhf


def build_model(template, *, layer="T0", t1_validation=None, mu_max=20.):
    pyhf = require_pyhf()
    if layer not in {"T0", "T1"} or not np.isfinite(mu_max) or mu_max <= 0:
        raise ResearchError("Invalid error layer or signal-strength bound")
    if template.get("status") != "valid":
        raise ResearchStateError("Template is not statistically usable", status="insufficient_statistics")
    if layer == "T1":
        contract = {"status": "validated", "correlation": "independent_process_bins", "auxiliary": "poisson_tau_gamma", "modifier": "shapesys", "pyhf_version": "0.7.6"}
        if not t1_validation or not t1_validation.get("evidence_id") or any(t1_validation.get(k) != v for k,v in contract.items()):
            raise ResearchStateError("T1 requires independent numerical validation and exact modifier contract", status="template_stat_model_unvalidated")
    active = template["active_bins"]
    if not active:
        raise ResearchStateError("All bins are structural zeros", status="insufficient_statistics")
    samples = []
    for s in template["samples"]:
        y = np.asarray(s["yield"], float)[active]
        var = np.asarray(s["variance"], float)[active]
        if not np.isfinite(y).all() or (y < 0).any() or not np.isfinite(var).all() or (var < 0).any():
            raise ResearchError("Invalid signed template rates or variances")
        modifiers = [{"name": "mu", "type": "normfactor", "data": None}] if s["is_signal"] else []
        if layer == "T1":
            cov = np.asarray(s["covariance"], float)[np.ix_(active,active)]
            if not np.allclose(cov, np.diag(np.diag(cov)), rtol=0, atol=1e-12):
                raise ResearchStateError("Event-group cross-bin covariance violates shapesys independence", status="template_stat_model_unvalidated")
            modifiers.append({"name": "mcstat_" + s["name"], "type": "shapesys", "data": np.sqrt(var).tolist()})
        samples.append({"name": s["name"], "data": y.tolist(), "modifiers": modifiers})
    specification = {"channels": [{"name": "mass_categories", "samples": samples}], "parameters": [{"name": "mu", "bounds": [[0.,float(mu_max)]], "inits": [1.]}]}
    model = pyhf.Model(specification, poi_name="mu")
    return model, {"layer": layer, "pyhf_version": "0.7.6", "mapping_id": template["mapping_id"], "candidate_id": template["candidate_id"], "model_spec": specification, "auxiliary_constraint": "poisson_tau_gamma" if layer == "T1" else "none"}


def profile_interval(model, data, confidence=.68):
    """Compatibility wrapper for one confidence level."""
    return profile_intervals(model, data, [confidence])[0]


def profile_intervals(model, data, levels=(.68, .95)):
    """One unconditional fit per observation; independent interval failures."""
    pyhf = require_pyhf()
    levels = tuple(levels)
    if not levels or any(not 0 < confidence < 1 for confidence in levels):
        raise ResearchError("Confidence must lie between zero and one")
    data = np.asarray(data, float)
    if data.shape != (model.config.nmaindata + model.config.nauxdata,) or not np.isfinite(data).all() or (data[:model.config.nmaindata] < 0).any():
        raise ResearchError("Invalid likelihood observations")
    offset=model.config.nmaindata
    for name in model.config.auxdata_order:
        parameter=model.config.param_set(name)
        values=data[offset:offset+parameter.n_parameters]
        if parameter.pdf_type=='poisson' and (values<0).any():
            raise ResearchError('Negative Poisson auxiliary observation')
        if parameter.pdf_type not in {'poisson','normal'}:
            raise ResearchStateError('Unsupported auxiliary distribution',status='stress_model_unvalidated')
        offset+=parameter.n_parameters
    try:
        best, objective = pyhf.infer.mle.fit(data, model, return_fitted_val=True)
        muhat = float(best[model.config.poi_index]); minimum = float(np.asarray(objective).reshape(-1)[0])
        lo, hi = model.config.suggested_bounds()[model.config.poi_index]
    except Exception as exc:
        return [{"status": "fit_failed", "confidence": level, "error": str(exc)} for level in levels]
    return [_profile_from_fit(pyhf, model, data, level, muhat, minimum, lo, hi) for level in levels]


def _profile_from_fit(pyhf, model, data, confidence, muhat, minimum, lo, hi):
    try:
        target = float(chi2.ppf(confidence, 1))
        def residual(mu):
            _, nll = pyhf.infer.mle.fixed_poi_fit(float(mu), data, model, return_fitted_val=True)
            q = float(np.asarray(nll).reshape(-1)[0]) - minimum
            if not np.isfinite(q):
                raise ValueError("Nonfinite profile objective")
            return q - target
        lower = float(lo) if residual(lo) <= 0 else float(brentq(residual, lo, muhat, xtol=1e-7))
        upper = float(brentq(residual, muhat, hi, xtol=1e-7)) if residual(hi) >= 0 else None
        return {"status": "valid" if upper is not None else "interval_unbounded", "muhat": muhat, "confidence": confidence, "lower": lower, "upper": upper, "width": upper-lower if upper is not None else None, "lower_at_boundary": lower == lo, "upper_search_bound": hi, "construction": "bounded_profile_likelihood_chi2_1dof"}
    except Exception as exc:
        return {"status": "fit_failed", "confidence": confidence, "error": str(exc)}


def run_asimov(template, *, protocol=None, layer="T0", t1_validation=None, injections=(0.,1.,2.), mu_max=20.,
               experiment_lineage=None, _built_model=None):
    if _is_sample_efficiency_payload(template) and experiment_lineage is None:
        raise ResearchError("sample-efficiency Asimov inference requires trusted lineage",
                            status="training_subset_binding_mismatch")
    if experiment_lineage is not None:
        from .templates import require_template_lineage
        require_template_lineage(template, experiment_lineage)
    if protocol is not None:
        config = (protocol if isinstance(protocol, dict) else protocol.to_dict()).get("inference", {})
        mu_max = config.get("mu_bounds", [0.,20.])[1]
    model, metadata = _built_model or build_model(template, layer=layer, t1_validation=t1_validation, mu_max=mu_max)
    results = []
    for mu in injections:
        if not 0 <= mu <= mu_max:
            raise ResearchError("Injection outside frozen mu bounds")
        pars = model.config.suggested_init(); pars[model.config.poi_index] = float(mu)
        data = np.asarray(model.expected_data(pars), float)
        results.append({"mu": float(mu), "intervals": profile_intervals(model, data)})
    output = {**metadata, "status": "valid" if all(i["status"] == "valid" for r in results for i in r["intervals"]) else "inference_incomplete", "expectation_kind": "model_self_asimov", "results": results}
    if experiment_lineage is not None:
        from .artifacts import digest_json
        from .sample_efficiency_lineage import bind_experiment_lineage
        output = bind_experiment_lineage(output, experiment_lineage)
        output["result_id"] = digest_json(output)
    return output


def run_toys(template, *, mu=1., count=500, seed=42, layer="T0", t1_validation=None,
             auxiliary_generation="regenerated", expectation_kind="model_self", mother_rates=None,
             mother_id=None, mu_max=20., signed_diagnostic=None, workers=1, worker_threads=1, _built_model=None):
    reject_sample_efficiency_assessment(template)
    if expectation_kind not in {"model_self", "assessment", "mismatch"} or auxiliary_generation not in {"fixed", "regenerated"}:
        raise ResearchError("Explicit supported toy source and auxiliary policy required")
    if int(count) != count or count < 1 or not 0 <= mu <= mu_max:
        raise ResearchError("Invalid frozen toy budget or injection")
    model, metadata = _built_model or build_model(template, layer=layer,t1_validation=t1_validation,mu_max=mu_max)
    pars = model.config.suggested_init(); pars[model.config.poi_index] = float(mu)
    expected = np.asarray(model.expected_data(pars), float)
    if expectation_kind != "model_self":
        if not mother_id or mother_rates is None:
            raise ResearchError("Independent/varied toy generation requires identified mother rates")
        rates = np.asarray(mother_rates, float)
        if rates.shape != (model.config.nmaindata,) or not np.isfinite(rates).all() or (rates < 0).any():
            raise ResearchError("Mother rates must be finite nonnegative physical rates")
        expected[:model.config.nmaindata] = rates
    elif mother_rates is not None:
        raise ResearchError("Model-self generation may not silently use another mother")
    rng = np.random.default_rng(seed)
    def tasks():
        for index in range(int(count)):
            data = expected.copy()
            data[:model.config.nmaindata] = rng.poisson(expected[:model.config.nmaindata])
            if auxiliary_generation == "regenerated":
                data[model.config.nmaindata:] = rng.poisson(expected[model.config.nmaindata:])
            yield index, data
    def fit(task):
        index, data = task
        row = {"toy": index, "intervals": profile_intervals(model, data)}
        if signed_diagnostic is not None and mu == 0:
            row['signed_mu_diagnostic'] = signed_mu_fit(template, data[:model.config.nmaindata], signed_diagnostic)
        return row
    results = list(ordered_map(fit, tasks(), workers=workers, worker_threads=worker_threads))
    output = {**metadata,"status": "valid" if all(i["status"] == "valid" for r in results for i in r["intervals"]) else "inference_incomplete", "mu": mu,"seed": seed,"count":count,"expectation_kind":expectation_kind,"mother_id":mother_id,"auxiliary_generation":auxiliary_generation,"paired":False,"results":results}
    if signed_diagnostic is not None and mu == 0:
        output['signed_mu_diagnostic'] = signed_mu_summary([r['signed_mu_diagnostic'] for r in results])
    return output


def paired_event_toys(frame, *, category_columns, mass_edges, mu, count, seed, mother_id, _joint_cells=None):
    """Draw joint-bin Poisson counts once and project into each candidate.

    Signed rows are aggregated into physical joint cells first; a negative
    physical cell is rejected, never sampled as a negative Poisson intensity.
    """
    if not mother_id or set(frame.role) != {"assessment"}:
        raise ResearchError("Paired mothers require identified assessment events")
    edges = np.asarray(mass_edges,float)
    if len(edges)<2 or not (np.diff(edges)>0).all() or mu<0 or count<1:
        raise ResearchError("Invalid paired-toy support or budget")
    if (frame.m4l<edges[0]).any() or (frame.m4l>edges[-1]).any():
        raise ResearchError("Mother outside mass support")
    n = len(edges)-1
    bins = np.minimum(np.searchsorted(edges,frame.m4l,side="right")-1,n-1)
    columns = sorted(category_columns)
    joint = np.column_stack([bins+n*frame[category_columns[c]].to_numpy(int) for c in columns])
    if any(not frame[category_columns[c]].isin([0,1]).all() for c in columns):
        raise ResearchError("Paired categories must be zero or one")
    rates = frame.yield_weight.to_numpy(float) * np.where(frame.label.to_numpy()==1, mu, 1.)
    if _joint_cells is None:
        cells, inverse = np.unique(joint,axis=0,return_inverse=True)
    else:
        cells, inverse = _joint_cells
        if not np.array_equal(cells[inverse],joint):
            raise ResearchError('Joint-cell cache does not match event/category order')
    sums = np.bincount(inverse,weights=rates,minlength=len(cells))
    if not np.isfinite(sums).all() or (sums<0).any():
        raise ResearchStateError("Joint physical mother has negative rates",status="insufficient_statistics")
    # Sparse integer projection bounds scratch memory by occupied joint cells.
    from scipy.sparse import csr_matrix
    projections = [csr_matrix((np.ones(len(cells), dtype=np.int64),
                              (np.arange(len(cells)), cells[:, j])), shape=(len(cells), 2*n))
                   for j in range(len(columns))]
    rng = np.random.default_rng(seed)
    observations = {c: [] for c in columns}
    chunk = max(1, (8 * 1024 * 1024) // max(8*len(cells), 1))
    for start in range(0, count, chunk):
        draws = rng.poisson(sums, size=(min(chunk, count-start), len(cells)))
        for c, projection in zip(columns, projections):
            observations[c].extend(np.asarray(draws @ projection).tolist())

    return {"status":"valid","paired":True,"pairing":"shared_joint_physical_event_cells","mother_id":mother_id,"observations":observations,"seed":seed,"mu":mu}


def stress_weights(frame, *, kind, direction, reference_score_column="reference_score", reference_mapping_id):
    if not reference_mapping_id or kind not in {"normalization","mass","score","correlation"} or direction not in {-1,1}:
        raise ResearchError("Stress scenario must use a frozen common reference")
    weights = frame.yield_weight.to_numpy(float).copy(); background = frame.label.to_numpy()==0
    x = (frame.m4l.to_numpy(float)-122.5)/17.5
    if kind in {"score","correlation"}:
        z = 2*frame[reference_score_column].to_numpy(float)-1
        if not np.isfinite(z).all() or (np.abs(z)>1).any():
            raise ResearchError("Frozen reference scores must be in [0,1]")
    coordinate = np.ones(len(frame)) if kind=="normalization" else (x if kind=="mass" else (z if kind=="score" else x*z))
    varied = weights.copy(); varied[background] *= 1 + .1*direction*coordinate[background]
    if kind != "normalization":
        if weights[background].sum() <= 0 or varied[background].sum() <= 0:
            raise ResearchStateError("Shape stress has invalid signed normalization",status="insufficient_statistics")
        varied[background] *= weights[background].sum()/varied[background].sum()
    return varied


def run_t2_procedure(calibration, template, mother, *, fit_mapping, apply_mapping, evaluate,
                     outer_replicas, inner_toys, seed, model_id, mother_id, workers=1, worker_threads=1):
    """Bounded paired group-bootstrap; callbacks retain scientific binding checks."""
    if not model_id or not mother_id or min(outer_replicas,inner_toys)<1:
        raise ResearchError("T2 requires frozen identities and positive budgets")
    if set(calibration.role)!={"calibration"} or set(template.role)!={"template"} or set(mother.role)!={"assessment"}:
        raise ResearchError("T2 role isolation violated")
    identity_sets=[set(f.event_group_id) for f in (calibration,template,mother)]
    if any(identity_sets[i] & identity_sets[j] for i in range(3) for j in range(i+1,3)):
        raise ResearchError("Physical event groups overlap between T2 roles")
    groups = sorted(calibration.event_group_id.unique()); rng=np.random.default_rng(seed); replicas=[]
    if not groups:
        raise ResearchStateError("Empty calibration",status="insufficient_statistics")
    group_index = {group: i for i,group in enumerate(groups)}
    codes = calibration.event_group_id.map(group_index).to_numpy(int)
    probabilities = np.full(len(groups),1/len(groups))
    def tasks():
        for replica in range(outer_replicas):
            multiplicity = rng.multinomial(len(groups), probabilities)
            bootstrap = calibration.copy(); factor = multiplicity[codes]
            bootstrap["bootstrap_multiplicity"] = factor
            for column in ("physical_weight","yield_weight"):
                if column in bootstrap:
                    bootstrap[column] *= factor
            bootstrap = bootstrap.loc[factor>0].copy()
            row = {"replica": replica, "bootstrap_group_multiplicities": dict(zip(map(str,groups),map(int,multiplicity)))}
            try:
                mapping = fit_mapping(bootstrap)
                mapped_template = apply_mapping(mapping,template.copy())
                mapped_mother = apply_mapping(mapping,mother.copy())
                # Failures above MUST NOT consume this draw (legacy random stream).
                inner_seed = int(rng.integers(0,2**31))
                yield row, (mapped_template,mapped_mother,mapping,inner_toys,inner_seed)
            except ResearchError as exc:
                row.update(status=exc.status,error=str(exc))
                yield row, None
    def finish(task):
        row, arguments = task
        if arguments is None:
            return row
        try:
            result = evaluate(*arguments)
            row.update(mapping_id=arguments[2]['mapping_id'],result=result,
                       status=result.get('status','unknown'),inner_seed=arguments[-1])
        except ResearchError as exc:
            row.update(status=exc.status,error=str(exc))
        return row
    replicas = list(ordered_map(finish, tasks(), workers=workers, worker_threads=worker_threads))
    return {"status":"valid" if all(r["status"]=="valid" for r in replicas) else "inference_incomplete","layer":"T2-procedure","model_id":model_id,"mother_id":mother_id,"randomization":"calibration_physical_group_bootstrap_and_inner_pseudodata","fixed":"trained_model_template_and_assessment_mother_events","outer_replicas":outer_replicas,"inner_toys":inner_toys,"seed":seed,"replicas":replicas}
