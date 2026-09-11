"""Application stages. Scientific computations live in the research modules."""
from __future__ import annotations

from pathlib import Path
from copy import deepcopy
import json
import os
import shutil
import sys
import time
import numpy as np
import pandas as pd

from .artifacts import ResearchRun, LoadedRun, read_run, read_json, digest_json
from .errors import ResearchError, ResearchStateError
from .protocol import load_protocol
from .data import (load_research_data, write_research_data, export_research_data,
                   audit_g0, finalize_prepare_metrics)
from .discriminants import train_discriminant, predict_discriminant
from .calibration import fit_calibration, apply_calibration, fit_thresholds, assign_categories
from .matrix_element import export_me_inputs, import_me_results
from .templates import common_mass_grid, gate_g1
from .inference import run_asimov, run_toys, build_model
from .resources import load_resources
from .reporting import (build_report, coverage_summary,
                        feature_combination_comparison, write_learning_curves)


def _required(args, name):
    value = getattr(args, name, None)
    if value is None or value == []:
        raise ResearchError(f"{args.command} requires --{name.replace('_', '-')}")
    return value


def _same_data(upstream, prepared):
    if not any(u['artifact_id'] == prepared.manifest['artifact_id'] for u in upstream.manifest['upstreams']):
        raise ResearchError("upstream belongs to a different prepared event population")


def _require_expansion_gate(gate_run, prepared):
    if prepared is None:
        raise ResearchError('Candidate expansion requires a prepared --input-run')
    if gate_run is None:
        raise ResearchStateError('Candidate expansion requires a passed G1 run', status='g1_not_passed')
    _same_data(gate_run, prepared)
    if gate_run.read_json('g1.json')['status'] != 'passed':
        raise ResearchStateError('G1 did not pass', status='g1_not_passed')


def _candidate_key(model):
    key = f"{model['candidate']}:{model['seed']}"
    if model['candidate'] == 'M6':
        key += f":lambda={model['target_lambda']:g}"
    if model.get('groups') is not None:
        key += ':groups=' + ''.join(model['groups'])
    return key


def _score(bundle, frame):
    if bundle.get('model') is not None:
        scores = predict_discriminant(bundle['model'], frame)
    else:
        indexed = {r['event_id']: r['me_score'] for r in bundle['me_scores']}
        if any(i not in indexed for i in frame.event_id):
            raise ResearchError('ME scores do not cover the requested event population')
        scores = np.array([indexed[i] for i in frame.event_id], float)
    if bundle['mapping'] is not None:
        scores = apply_calibration(bundle['mapping'], frame.m4l.to_numpy(), scores, model_id=bundle['model_id'])
    return scores


def _categorize(bundle, frame):
    result = frame.copy()
    result['category'] = assign_categories(bundle['thresholds'], _score(bundle, frame),
                                           model_id=bundle['model_id'], mapping_id=bundle['mapping_id'])
    return result


def _validation(path, protocol):
    if not path:
        return None
    value = read_json(Path(path))
    if value.get('protocol_sha256') != digest_json(protocol):
        raise ResearchError('T1 validation evidence belongs to another protocol')
    return value


def _me_binding(evidence):
    """Population-independent identity of a verified external discriminant."""
    inputs,reference=evidence['inputs'],evidence['reference']
    binding={key:inputs[key] for key in ('dataset','backend','process','units','ordering','probability_definition','protocol_digest')}
    binding.update(adapter_sha256=reference['adapter_sha256'],reference_sha256=digest_json(reference))
    return {**binding,'binding_id':digest_json(binding)}


def _supplement_me_bundles(bundles, supplemental_runs, prepared, mother_ids):
    """Add score availability after opening; never replace frozen transformations."""
    merged=deepcopy(bundles)
    me_keys=[key for key,bundle in merged.items() if bundle.get('model') is None]
    used=set()
    supplements={}
    for item in supplemental_runs:
        _same_data(item,prepared)
        evidence=item.read_json('me-evidence.json')
        binding=_me_binding(evidence)
        if evidence.get('me_binding')!=binding:
            raise ResearchError('Supplemental ME semantic binding is missing or inconsistent')
        supplements.setdefault(digest_json(binding),[]).append((item,binding,item.read_json('me-scores.json'),
                            {row['event_id']:row['input_digest'] for row in evidence['inputs']['events']}))
    for key in me_keys:
        bundle=merged[key]
        if not bundle.get('me_binding'):
            raise ResearchError('Frozen ME bundle lacks semantic discriminant binding')
        original={row['event_id']:row for row in bundle['me_scores']}
        input_digests=dict(bundle.get('me_event_input_digests',{}))
        for item,binding,rows,digests in supplements.get(digest_json(bundle['me_binding']),[]):
            if binding!=bundle['me_binding']:
                continue
            used.add(item.manifest['artifact_id'])
            for row in rows:
                event_id=row['event_id']
                if event_id in original:
                    if row!=original[event_id] or input_digests.get(event_id)!=digests.get(event_id):
                        raise ResearchError('Supplemental ME changes a previously frozen scored event')
                elif event_id in mother_ids:
                    original[event_id]=row
                    input_digests[event_id]=digests[event_id]
                else:
                    raise ResearchError('Supplemental ME contains events outside frozen and assessment populations')
        if not set(mother_ids)<=set(original):
            raise ResearchError('Missing exact assessment ME coverage for frozen '+key)
        bundle['me_scores']=list(original.values())
        bundle['me_event_input_digests']=input_digests
    if any(item.manifest['artifact_id'] not in used for item in supplemental_runs):
        raise ResearchError('Supplemental ME adapter/reference/backend/process differs from every frozen discriminant')
    return merged


def _frozen_stress_reference(frozen,bundles,protocol,requested=None):
    registered=protocol['stress']['reference_candidate']
    reference=frozen.get('stress_reference')
    if not reference or reference.get('candidate_key')!=registered or (requested is not None and requested!=registered):
        raise ResearchError('Stress reference differs from the pre-assessment frozen candidate')
    bundle=bundles.get(registered)
    if not bundle or reference!={'candidate_key':registered,'model_id':bundle['model_id'],'mapping_id':bundle['mapping_id']}:
        raise ResearchError('Frozen stress model/mapping identity mismatch')
    return registered


def _claim_path(root, prepared_id, protocol):
    return Path(root) / '.research-claims' / (digest_json({'prepared':prepared_id,'protocol':digest_json(protocol)}) + '.json')


def _population_id(path, dataset):
    """Hash physical identity envelopes only, including unopened assessment."""
    identities=set()
    with Path(path).open(encoding='utf-8') as stream:
        next(stream)
        for line in stream:
            envelope=line.split('\t',1)[0]
            identity=json.loads(envelope)
            if identity.get('dataset')!=dataset or identity.get('split')!='development' or not identity.get('event_group_id'):
                raise ResearchError('Invalid population identity envelope')
            identities.add((identity['event_group_id'],identity['label'],identity['split'],identity['dataset']))
    if not identities:
        raise ResearchError('Empty population identity')
    return digest_json({'dataset':dataset,'physical_groups':sorted(identities)})


def _require_unopened(root, prepared_id, protocol):
    if _claim_path(root, prepared_id, protocol).exists():
        raise ResearchStateError('Assessment already claimed; redesign requires a new protocol and independent validation', status='assessment_already_started')


def _claim_assessment(root, prepared_id, protocol, freeze_id, *, repeat=False, population_id=None):
    """An exclusive durable claim precedes even the first assessment payload decode."""
    path = _claim_path(root, population_id or prepared_id, protocol)
    if path.parent.is_symlink():
        raise ResearchError('Assessment claim directory cannot be a symlink')
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {'prepared_artifact_id':prepared_id,'protocol_sha256':digest_json(protocol),
             'population_id':population_id or prepared_id,'freeze_artifact_id':freeze_id,'budgets':protocol['inference']}
    try:
        with path.open('x',encoding='utf-8') as stream:
            stream.write(json.dumps(value,sort_keys=True,allow_nan=False))
            stream.flush(); os.fsync(stream.fileno())
    except FileExistsError:
        if path.is_symlink() or not repeat or read_json(path) != value:
            raise ResearchStateError('Existing assessment claim requires the same freeze and explicit repeat authorization',status='assessment_already_started')
    return value


def _p0_audit(frame, protocol, audit, evidence_path):
    result = dict(audit)
    kind = frame.attrs.get('source_kind')
    result['source_kind'] = kind
    if kind == 'synthetic':
        result['scope'] = 'synthetic_software_validation'
        return result, None
    if kind != 'controlled_mc':
        raise ResearchError('Unknown scientific source kind')
    if not evidence_path:
        result['physics_sources_validated'] = False
        result['scientific_gate'] = 'p0_source_validation_missing'
        return result, None
    evidence = read_json(Path(evidence_path))
    expected = {'status':'validated','dataset':protocol['dataset'],'protocol_sha256':digest_json(protocol),
                'source_evidence_sha256':digest_json(frame.attrs.get('source_evidence',{}))}
    definitions = evidence.get('physical_definitions',{})
    if any(evidence.get(k)!=v for k,v in expected.items()) or not evidence.get('evidence_id') or not evidence.get('independent_reference') or not all(definitions.get(k) for k in ('processes','units','four_vectors','pairing','weights','selection')):
        raise ResearchError('P0 evidence lacks bound independent source/physical-definition validation')
    result.update(physics_sources_validated=True,p0_evidence_id=evidence['evidence_id'],scope='bound_mc_source_and_statistics')
    return result,evidence


def _require_g0(prepared):
    if prepared is None:
        raise ResearchError('G0 requires a prepared input run')
    audit = prepared.read_json('audit.json')
    if audit['status'] != 'passed':
        raise ResearchStateError('G0 did not pass',status='insufficient_statistics')
    if prepared.manifest.get('source_kind') != 'synthetic' and audit.get('physics_sources_validated') is not True:
        raise ResearchStateError('Controlled MC requires independent bound P0 physical source validation',status='p0_source_validation_missing')


def expected_candidates():
    result = {'M0': 'not_run', 'M1': 'not_run', 'M1c': 'not_run', 'L1:42': 'not_run'}
    for seed in range(42, 47):
        for name in ('M0c', 'M2', 'M3', 'M3-fixed200', 'M4', 'M5', 'M5-abs'):
            result[f'{name}:{seed}'] = 'not_run'
        for strength in (.05, .1, .2, .5):
            result[f'M6:{seed}:lambda={strength:g}'] = 'not_run'
    return result


def execute(args, *, allowed_root=None):
    resources = load_resources(getattr(args,'resources',None))
    parallel = {k:resources[k] for k in ('workers','worker_threads')}
    protocol = load_protocol(args.protocol, dataset=args.dataset).to_dict()
    cfg=protocol['inference']
    if cfg['pyhf_version']!='0.7.6' or cfg['confidence_levels']!=[.68,.95] or cfg['mu_bounds'][0]!=0 or cfg['template_modifier']!='shapesys' or cfg['template_correlation']!='independent_process_bins' or protocol['templates']['score_categories']!=2:
        raise ResearchError('Unsupported frozen inference contract; do not silently ignore protocol choices')
    if cfg['template_min_effective_count']!=protocol['templates']['min_neff_signed'] or cfg['template_min_cancellation_ratio']!=protocol['templates']['min_rho']:
        raise ResearchError('Template and inference statistical thresholds disagree')
    stage = args.command
    diagnostic_limit = getattr(args, 'diagnostic_entries_per_file', None)
    show_prepare_metrics = getattr(args, 'show_prepare_metrics', False)
    show_prepare_progress = getattr(args, 'show_prepare_progress', False)
    if diagnostic_limit is not None:
        if stage != 'prepare' or not args.input_manifest:
            raise ResearchError('--diagnostic-entries-per-file requires prepare --input-manifest')
        if diagnostic_limit < 1:
            raise ResearchError('--diagnostic-entries-per-file must be positive')
    if show_prepare_metrics and (stage != 'prepare' or not args.input_manifest):
        raise ResearchError('--show-prepare-metrics requires prepare --input-manifest')
    if show_prepare_progress and (stage != 'prepare' or not args.input_manifest):
        raise ResearchError('--show-prepare-progress requires prepare --input-manifest')
    upstreams = []
    root_metrics = None

    def upstream(path, stages=None, terminal=False):
        value = read_run(path, dataset=args.dataset, protocol=protocol, stages=stages, allow_terminal=terminal)
        upstreams.append(value)
        return value

    prepared = None
    if args.input_run:
        prepared = upstream(args.input_run, ('prepare',))
    model_run = upstream(args.model_run, ('train','me-import')) if args.model_run else None
    calibration_runs = [upstream(p, ('calibrate',)) for p in args.calibration_run]
    template_run = upstream(args.template_run, ('templates',)) if args.template_run else None
    gate_run = upstream(args.gate_run, ('templates',)) if args.gate_run else None
    freeze_run = upstream(args.freeze_run, ('freeze',)) if args.freeze_run else None
    assessment_me_runs=[upstream(path,('me-import',)) for path in getattr(args,'assessment_me_run',[])]
    result_runs = [upstream(p, terminal=True) for p in args.result_run]
    root = Path(allowed_root) if allowed_root else Path.cwd() / 'runs'
    population = prepared.manifest['artifact_id'] if prepared else None
    if population is None and template_run:
        population = template_run.manifest.get('context',{}).get('prepared_artifact_id')
    context = {'prepared_artifact_id':population,'candidate_key':None,
               'population_id':prepared.manifest.get('population_id') if prepared else (template_run.manifest.get('context',{}).get('population_id') if template_run else None),
               'source_kind':prepared.manifest.get('source_kind') if prepared else (template_run.manifest.get('context',{}).get('source_kind') if template_run else None),
               'inference_scope':{'mu':args.mu,'layer':args.layer,'expectation_kind':args.expectation_kind,
                                  'seed':args.seed,'toys':args.toys,'procedure':getattr(args,'procedure','fixed'),
                                  'stress_kind':getattr(args,'stress_kind',None) if getattr(args,'procedure','fixed')=='stress' else None,
                                  'stress_direction':getattr(args,'stress_direction',None) if getattr(args,'procedure','fixed')=='stress' else None,
                                  'stress_mode':getattr(args,'stress_mode',None) if getattr(args,'procedure','fixed')=='stress' else None,
                                  'reference_candidate':getattr(args,'reference_candidate',None) if getattr(args,'procedure','fixed')=='stress' else None}}
    if template_run is not None:
        bound_grid=template_run.read_json('templates.json')
        bound_evidence=template_run.read_json('t1-validation.json')
        cohort={'prepared_artifact_id':population,'mass_edges':bound_grid['mass_edges'],
                'template_rules':protocol['templates'],'inference_rules':protocol['inference'],
                't1_validation':bound_evidence,'protocol_sha256':digest_json(protocol)}
        context['inference_scope'].update(template_artifact_id=template_run.manifest['artifact_id'],
                                          comparison_cohort_id=digest_json(cohort),comparison_cohort=cohort)
    if stage == 'train':
        context['candidate_key'] = _candidate_key({'candidate':args.candidate,'seed':args.seed,
            'target_lambda':args.strength,'groups':list(args.groups) if args.groups is not None else None})
    elif stage == 'calibrate' and model_run:
        if model_run.manifest['stage']=='train':
            source_model=model_run.read_json('model.json')
            key=_candidate_key(source_model); original=source_model['candidate']
        else:
            key=original='M1'
        derived=original if args.transform=='raw' else ({'M2':'M4','M3':'M5','M1':'M1c','L1':'L1'}.get(original,original+'-cdf'))
        if args.transform=='absolute': derived='M5-abs'
        context['candidate_key']=key.replace(original,derived,1)
    with ResearchRun(args.run_dir, allowed_root=root, stage=stage, dataset=args.dataset,
                     protocol=protocol, upstreams=upstreams, seed=args.seed, context=context) as run:
        stage_started, stage_cpu = time.perf_counter(), time.process_time()
        run.manifest['resources'] = resources
        run.manifest['performance_implementation'] = 'research-refactor-v1'
        if assessment_me_runs and (stage!='infer' or args.expectation_kind!='assessment'):
            raise ResearchError('Supplemental ME runs are only used for frozen assessment inference')
        if prepared is not None and stage in ('train','calibrate','templates','freeze'):
            _require_unopened(root,prepared.manifest.get('population_id',prepared.manifest['artifact_id']),protocol)
            _require_g0(prepared)
        def events(*, assessment=False):
            if prepared is None:
                raise ResearchError(f'{stage} requires --input-run from prepare')
            frozen = None
            if assessment:
                if freeze_run is None:
                    raise ResearchError('assessment requires --freeze-run')
                _same_data(freeze_run, prepared)
                frozen = freeze_run.read_json('freeze.json')
                if template_run and template_run.manifest['artifact_id'] not in frozen['template_artifact_ids']:
                    raise ResearchError('template is absent from frozen analysis')
                cfg=protocol['inference']
                if stage=='infer' and (args.seed!=cfg['toy_seed'] or args.mu not in cfg['injections'] or args.toys<0 or args.toys>cfg['toy_count']):
                    raise ResearchError('Assessment injection, seed or count exceeds the frozen budget')
                _claim_assessment(root,prepared.manifest['artifact_id'],protocol,freeze_run.manifest['artifact_id'],repeat=getattr(args,'repeat_assessment',False),population_id=prepared.manifest.get('population_id'))
            return load_research_data(prepared.file('events.jsonl'), args.dataset, protocol,
                                      allow_assessment=assessment, assessment_freeze=frozen)

        if stage in ('prepare','audit'):
            if args.events:
                frame = load_research_data(args.events, args.dataset, protocol)
                if stage == 'prepare':
                    shutil.copyfile(args.events, run.path / 'events.jsonl')
                    run.register_file('events.jsonl')
            elif args.input_manifest:
                if stage == 'audit':
                    source = read_json(Path(args.input_manifest))
                    if source.get('dataset') != args.dataset or source.get('mc_only') is not True:
                        raise ResearchError('input audit requires an identified MC manifest')
                    run.write_json('input-evidence.json', source)
                    run.write_json('audit.json', {'status':'metadata_recorded', 'G0':'not_run',
                        'physical_definitions': source.get('physics', {}),
                        'missing_evidence': ['independent_physics_sources', 'development_support_audit'],
                        'test_features_read': False})
                    return {'status':'complete','run_dir':str(args.run_dir)}
                root_metrics = {'diagnostic_entries_per_file': diagnostic_limit}
                run.manifest['root_prepare_metrics'] = root_metrics
                frame = export_research_data(args.input_manifest, _required(args, 'profile'), protocol,
                                             max_entries=resources['root_max_entries'], metrics=root_metrics,
                                             diagnostic_entries_per_file=diagnostic_limit,
                                             root_threads=resources['root_threads'],
                                             show_prepare_metrics=show_prepare_metrics,
                                             show_prepare_progress=show_prepare_progress)
                write_started = time.perf_counter()
                receipt = write_research_data(frame, run.path / 'events.jsonl', protocol)
                frame.attrs['population_id'] = receipt.population_id
                root_metrics['write_and_digest_seconds'] = time.perf_counter()-write_started
                registration_started = time.perf_counter()
                run.register_streamed_file('events.jsonl', sha256=receipt.sha256,
                                           size_bytes=receipt.size_bytes)
                root_metrics['artifact_registration_seconds'] = time.perf_counter()-registration_started
                artifact_started = time.perf_counter()
                run.write_json('input-evidence.json', read_json(Path(args.input_manifest)))
                root_metrics['artifact_metadata_seconds'] = time.perf_counter()-artifact_started
            else:
                frame = events()
            audit_started = time.perf_counter() if root_metrics is not None else None
            audit = audit_g0(frame, protocol)
            if root_metrics is not None:
                root_metrics['g0_seconds'] = time.perf_counter()-audit_started
            p0_started = time.perf_counter() if root_metrics is not None else None
            audit,p0 = _p0_audit(frame,protocol,audit,getattr(args,'p0_validation',None))
            if root_metrics is not None:
                root_metrics['p0_seconds'] = time.perf_counter()-p0_started
            artifact_started = time.perf_counter() if root_metrics is not None else None
            run.write_json('audit.json', audit)
            if p0 is not None:
                run.write_json('p0-validation.json',p0)
            if root_metrics is not None:
                root_metrics['artifact_metadata_seconds'] += time.perf_counter()-artifact_started
            run.manifest['source_kind'] = frame.attrs.get('source_kind')
            if stage=='prepare':
                # A caller-owned source may change between parsing and copying.
                # Keep the original identity verification on the published copy.
                run.manifest['population_id']=(_population_id(run.path/'events.jsonl',args.dataset)
                    if args.events else frame.attrs['population_id'])
                run.manifest['source_evidence_sha256']=digest_json(frame.attrs.get('source_evidence',{}))
            if stage == 'prepare' and args.events is None and args.input_manifest is None:
                raise ResearchError('prepare requires --events or --input-manifest')

        elif stage == 'train':
            _require_g0(prepared)
            frame = events()
            minimal = args.seed == 42 and args.candidate in ('M0c','M2','M3') and args.groups is None
            if not minimal:
                _require_expansion_gate(gate_run, prepared)
            model = train_discriminant(frame.loc[frame.role.isin(['train','validation'])].copy(), protocol,
                                       candidate=args.candidate, seed=args.seed, target_lambda=args.strength,
                                       groups=list(args.groups) if args.groups is not None else None)
            run.write_json('model.json', model)
            if 'history_contract' in model:
                write_learning_curves([model], run.path/'learning-curves.png')
                run.register_file('learning-curves.png')

        elif stage == 'me-export':
            frame = events(assessment=bool(freeze_run))
            configuration = read_json(Path(_required(args,'backend_config')))
            result = export_me_inputs(frame, protocol, configuration['backend'], configuration['process'])
            run.write_json('me-input.json', result)
            run.write_json('data-origin.json', {'artifact_id':prepared.manifest['artifact_id']})

        elif stage == 'me-import':
            export_run = upstream(_required(args,'export_run'), ('me-export',))
            run.manifest['upstreams'].append({'artifact_id':export_run.manifest['artifact_id'],
                                             'stage':'me-export','path':str(export_run.path)})
            if prepared is None:
                raise ResearchError('ME import requires its prepared --input-run')
            _same_data(export_run, prepared)
            inputs = export_run.read_json('me-input.json')
            reference = read_json(Path(args.reference)) if args.reference else None
            result = import_me_results(inputs, read_json(Path(_required(args,'results'))), reference, protocol)
            run.write_json('me-scores.json', result.to_dict(orient='records'))
            evidence={'reference':reference,'inputs':inputs,
                'model_id':digest_json({'input_digest':inputs['input_digest'],'reference':reference})}
            evidence['me_binding']=_me_binding(evidence)
            run.write_json('me-evidence.json',evidence)

        elif stage == 'calibrate':
            if args.transform == 'absolute':
                _require_expansion_gate(gate_run, prepared)
            frame = events()
            if model_run is None:
                raise ResearchError('calibrate requires --model-run')
            _same_data(model_run, prepared)
            calibration = frame.loc[frame.role == 'calibration'].copy()
            if model_run.manifest['stage'] == 'train':
                model = model_run.read_json('model.json')
                bundle = {'model':model, 'model_id':model['model_id'], 'candidate_id':model['candidate'],
                          'seed':model['seed'], 'key':_candidate_key(model)}
                scores = predict_discriminant(model, calibration)
            else:
                evidence = model_run.read_json('me-evidence.json')
                bundle = {'model':None,'model_id':evidence['model_id'],'candidate_id':'M1','seed':None,
                          'key':'M1','me_scores':model_run.read_json('me-scores.json'),
                          'me_binding':evidence['me_binding'],
                          'me_event_input_digests':{row['event_id']:row['input_digest'] for row in evidence['inputs']['events']}}
                scores = _score({**bundle,'mapping':None}, calibration)
            mapping = None
            if args.transform != 'raw':
                mapping = fit_calibration(calibration, scores, protocol, target=args.transform, model_id=bundle['model_id'])
                scores = apply_calibration(mapping, calibration.m4l.to_numpy(), scores, model_id=bundle['model_id'])
                original = bundle['candidate_id']
                derived = {'M2':'M4','M3':'M5','M1':'M1c','L1':'L1'}.get(original)
                if args.transform == 'absolute':
                    if original != 'M3':
                        raise ResearchError('absolute-weight bridge requires the same frozen M3')
                    derived = 'M5-abs'
                if derived is None and not bundle.get('model',{}).get('groups'):
                    # CDF mass-only is needed for same-family empty-set attribution.
                    derived = original + '-cdf'
                bundle['candidate_id'] = derived or original + '-cdf'
                bundle['key'] = bundle['key'].replace(original, bundle['candidate_id'], 1)
            mapping_id = mapping['mapping_id'] if mapping else 'raw:' + bundle['model_id']
            thresholds = fit_thresholds(calibration, scores, protocol, model_id=bundle['model_id'], mapping_id=mapping_id)
            bundle.update(mapping=mapping, mapping_id=mapping_id, thresholds=thresholds,
                          transform=args.transform, status='calibrated')
            run.write_json('calibration.json', bundle)

        elif stage == 'templates':
            frame = events()
            if not calibration_runs:
                raise ResearchError('templates requires --calibration-run (repeat for all common methods)')
            source = frame.loc[frame.role == 'template'].copy()
            candidates, bundles = {}, {}
            for item in calibration_runs:
                _same_data(item, prepared)
                bundle = item.read_json('calibration.json')
                key = bundle['key']
                if key in bundles:
                    raise ResearchError('duplicate candidate in common template construction')
                candidates[key] = _categorize(bundle, source)
                bundles[key] = bundle
            candidates['M0'] = source.assign(category=0)
            cfg = protocol['templates']
            grid = common_mass_grid(candidates, mass_edges=cfg['mass_edges'], thresholds=cfg)
            for key, value in grid['templates'].items():
                bundle = bundles.get(key)
                value['mapping_id'] = bundle['mapping_id'] if bundle else 'mass-only:' + prepared.manifest['artifact_id']
                value['candidate_id'] = bundle['candidate_id'] if bundle else 'M0'
                value['seed'] = bundle['seed'] if bundle else None
                value['prepared_artifact_id'] = prepared.manifest['artifact_id']
                value['luminosity_pb'] = protocol['luminosity_pb']
            evidence = _validation(args.t1_validation, protocol)
            g1 = gate_g1({k:'valid' for k in bundles}, grid['templates'], evidence)
            required_minimum = {'M0c:42','M2:42','M3:42','M4:42','M5:42'}
            if not required_minimum <= set(bundles):
                g1 = {'status':'g1_incomplete','reasons':['minimal_candidate_matrix_missing'],
                      'missing':sorted(required_minimum-set(bundles))}
            run.write_json('templates.json', grid)
            run.write_json('calibrations.json', bundles)
            run.write_json('g1.json', g1)
            run.write_json('t1-validation.json', evidence)

        elif stage == 'freeze':
            if prepared is None or template_run is None:
                raise ResearchError('freeze requires --input-run and --template-run')
            _same_data(template_run, prepared)
            if template_run.read_json('g1.json')['status'] != 'passed':
                raise ResearchStateError('Cannot freeze before G1 passes', status='g1_not_passed')
            statuses = expected_candidates()
            if args.candidate_ledger:
                supplied = read_json(Path(args.candidate_ledger))
                if supplied.get('protocol_sha256') != digest_json(protocol):
                    raise ResearchError('candidate ledger protocol mismatch')
                declared = supplied.get('candidates',{})
                permitted = {'blocked_missing_reference','insufficient_statistics','training_failed','fit_failed'}
                if set(declared)-set(statuses) or any(v not in permitted for v in declared.values()):
                    raise ResearchError('ledger can only declare explicit terminal candidate states')
                statuses.update(declared)
                run.write_json('candidate-ledger.json', supplied)
            templates = deepcopy(bound_grid)['templates']
            for key, value in templates.items():
                if key in statuses:
                    statuses[key] = 'complete' if value['status']=='valid' else value['status']
            if any(v=='not_run' for v in statuses.values()):
                raise ResearchStateError('Full planned candidate states must be recorded before assessment',
                                         status='candidate_matrix_incomplete')
            reference_key=protocol['stress']['reference_candidate']
            reference_bundle=template_run.read_json('calibrations.json').get(reference_key)
            if not reference_bundle or templates.get(reference_key,{}).get('status')!='valid':
                raise ResearchStateError('Registered stress reference candidate must be usable before freezing',status='stress_reference_unavailable')
            frozen = {'status':'frozen','protocol_sha256':digest_json(protocol),
                      'evidence_id':digest_json(statuses),'candidate_states':statuses,
                      'template_artifact_ids':[template_run.manifest['artifact_id']],
                      'mass_edges':deepcopy(bound_grid)['mass_edges'],
                      'stress_reference':{'candidate_key':reference_key,'model_id':reference_bundle['model_id'],
                                          'mapping_id':reference_bundle['mapping_id']}}
            run.write_json('freeze.json', frozen)

        elif stage == 'infer':
            if template_run is None:
                raise ResearchError('infer requires --template-run')
            cfg=protocol['inference']
            if not 0 <= args.toys <= cfg['toy_count'] or args.mu not in cfg['injections']:
                raise ResearchError('Inference injection or count outside frozen pilot budget')
            grid=deepcopy(bound_grid)
            evidence=deepcopy(bound_evidence)
            procedure=getattr(args,'procedure','fixed')
            if procedure!='fixed' and args.expectation_kind!='assessment':
                raise ResearchError('T2/stress require frozen assessment generation')
            if procedure=='t2' and (args.toys!=0 or args.layer!='T1'):
                raise ResearchError('T2 uses registered outer/inner budgets and T1; leave --toys at zero')
            if args.expectation_kind=='assessment' and procedure!='t2' and args.toys<1:
                raise ResearchError('Assessment requires a positive toy budget before opening')
            if args.expectation_kind=='assessment':
                bundles=template_run.read_json('calibrations.json')
                if procedure=='stress':
                    if freeze_run is None:
                        raise ResearchError('Stress requires a pre-assessment freeze')
                    args.reference_candidate=_frozen_stress_reference(freeze_run.read_json('freeze.json'),bundles,protocol,args.reference_candidate)
                    run.manifest['context']['inference_scope']['reference_candidate']=args.reference_candidate
                frame=events(assessment=True)
                mother=frame.loc[frame.role=='assessment'].copy()
                bundles=_supplement_me_bundles(bundles,assessment_me_runs,prepared,set(mother.event_id))
                if assessment_me_runs:
                    run.write_json('assessment-me-binding.json',{'supplement_artifact_ids':[item.manifest['artifact_id'] for item in assessment_me_runs],
                        'frozen_models':{key:{'model_id':bundle['model_id'],'mapping_id':bundle['mapping_id'],'me_binding':bundle['me_binding']}
                                         for key,bundle in bundles.items() if bundle.get('model') is None}})
                from .assessment import infer_assessment, run_assessment_t2
                shared=dict(layer=args.layer,t1_validation=evidence,mu=args.mu,seed=args.seed,
                            prepared_id=prepared.manifest['artifact_id'],freeze_id=freeze_run.manifest['artifact_id'],**parallel)
                if procedure=='t2':
                    procedure_result=run_assessment_t2(grid,bundles,frame.loc[frame.role=='calibration'].copy(),
                        frame.loc[frame.role=='template'].copy(),mother,protocol,**shared)
                    run.write_json('procedure.json',procedure_result)
                    results={}
                elif procedure=='stress':
                    from .assessment import run_assessment_stress
                    results=run_assessment_stress(grid,bundles,mother,protocol,count=args.toys,
                        kind=args.stress_kind,direction=args.stress_direction,mode=args.stress_mode,
                        reference_candidate=args.reference_candidate,template_frame=frame.loc[frame.role=='template'].copy(),**shared)
                else:
                    results=infer_assessment(grid,bundles,mother,protocol,count=args.toys,**shared)
            else:
                results={}
                for key,template in grid['templates'].items():
                    try:
                        built_model=build_model(template,layer=args.layer,t1_validation=evidence,mu_max=cfg['mu_bounds'][1])
                        asimov=run_asimov(template,protocol=protocol,layer=args.layer,t1_validation=evidence,injections=[args.mu],_built_model=built_model)
                        result={'status':asimov['status'],'asimov':asimov,'seed':template.get('seed')}
                        if args.toys:
                            toys=run_toys(template,mu=args.mu,count=args.toys,seed=args.seed,layer=args.layer,
                                t1_validation=evidence,auxiliary_generation=cfg['auxiliary_generation'],mu_max=cfg['mu_bounds'][1],
                                signed_diagnostic=protocol.get('diagnostics',{}).get('signed_mu'),_built_model=built_model,**parallel)
                            result['toys']=toys
                            result['coverage']={str(cl):coverage_summary([r['intervals'][i] for r in toys['results']],mu=args.mu)
                                                for i,cl in enumerate((.68,.95))}
                            if toys['status']!='valid': result['status']=toys['status']
                        results[key]=result
                    except ResearchStateError as error:
                        results[key]={'status':error.status,'reason':str(error)}
            run.write_json('inference.json',results)

        elif stage == 'report':
            if not result_runs:
                raise ResearchError('report requires one or more --result-run')
            statuses, primary, records = expected_candidates(), [], {}
            training_models = {}
            state_history={}; source_ids=set(); unknown_population=False; terminal_runs=[]; procedures={}; primary_cohorts=set()
            feature_comparisons=[]
            def record_state(key,status,artifact_id):
                state_history.setdefault(key,[]).append({'status':status,'artifact_id':artifact_id})
                unique={entry['status'] for entry in state_history[key]}
                statuses[key]=next(iter(unique)) if len(unique)==1 else 'multiple_recorded_states'
            for item in result_runs:
                manifest=item.manifest; item_context=manifest.get('context',{})
                source=item_context.get('prepared_artifact_id')
                if source: source_ids.add(source)
                else: unknown_population=True
                if len(source_ids)>1 or (source_ids and unknown_population):
                    raise ResearchError('Reports cannot mix prepared event populations or unbound source identity')
                candidate=item_context.get('candidate_key')
                if manifest['status']!='complete':
                    terminal_runs.append({'artifact_id':manifest['artifact_id'],'stage':manifest['stage'],
                        'candidate_key':candidate,'status':manifest['status'],'reason':manifest.get('reason')})
                    if candidate: record_state(candidate,manifest['status'],manifest['artifact_id'])
                    continue
                if manifest['stage']=='freeze':
                    for key,status in item.read_json('freeze.json')['candidate_states'].items():
                        record_state(key,status,manifest['artifact_id'])
                elif manifest['stage']=='train':
                    model=item.read_json('model.json')
                    training_models[model['model_id']] = model
                    record_state(_candidate_key(model),model['status'],manifest['artifact_id'])
                elif manifest['stage']=='calibrate':
                    bundle=item.read_json('calibration.json')
                    record_state(bundle['key'],bundle['status'],manifest['artifact_id'])
                elif manifest['stage']=='templates':
                    for key,value in item.read_json('templates.json')['templates'].items():
                        record_state(key,value['status'],manifest['artifact_id'])
                elif manifest['stage']=='infer':
                    scope=item_context.get('inference_scope',{})
                    inference_results=item.read_json('inference.json')
                    if 'procedure.json' in manifest['files']:
                        procedure_key=digest_json({'population':source,'scope':scope})
                        if procedure_key in procedures:
                            raise ResearchError('Duplicate procedure scope; no run selection allowed')
                        procedures[procedure_key]=item.read_json('procedure.json')
                    combination_seeds=sorted({result.get('seed') for key,result in inference_results.items()
                                              if ':groups=' in key and isinstance(result.get('seed'),int)})
                    for feature_seed in combination_seeds:
                        comparison=feature_combination_comparison(inference_results,seed=feature_seed,
                            family_id='engineered19_raw_T1')
                        comparison.update(source_artifact_id=manifest['artifact_id'],
                                          comparison_cohort_id=scope.get('comparison_cohort_id'))
                        feature_comparisons.append(comparison)
                    for key,result in inference_results.items():
                        scoped_key=key+'|'+digest_json({'population':source,'scope':scope})
                        if scoped_key in records:
                            raise ResearchError('Duplicate candidate inference scope; reports never choose the best run')
                        records[scoped_key]={'candidate_key':key,'scope':scope,'result':result,'artifact_id':manifest['artifact_id']}
                        record_state(key,result['status'],manifest['artifact_id'])
                        if scope.get('expectation_kind')!='model_self' or scope.get('procedure','fixed')!='fixed':
                            continue
                        for injection in result.get('asimov',{}).get('results',[]):
                            interval=injection['intervals'][0]
                            if result['asimov'].get('candidate_id') in ('M4','M5') and result['asimov'].get('layer')=='T1' and injection['mu']==1:
                                cohort_id=scope.get('comparison_cohort_id')
                                if not cohort_id:
                                    raise ResearchError('Primary comparison lacks bound common-grid/T1 cohort identity')
                                primary_cohorts.add(cohort_id)
                                if len(primary_cohorts)>1:
                                    raise ResearchError('Primary comparison cannot mix common-grid or T1 validation cohorts')
                            primary.append({'candidate_id':result['asimov']['candidate_id'],'seed':result['seed'],
                                'layer':result['asimov']['layer'],'mu':injection['mu'],
                                'expectation_kind':result['asimov']['expectation_kind'],
                                'status':interval['status'],'width68':interval.get('width')})
            report=build_report(statuses,primary_records=primary,results=records,
                                feature_comparisons=feature_comparisons)
            curves = []
            for model in training_models.values():
                if model['candidate'] != 'M6' or 'history_contract' not in model:
                    continue
                controls = [m for m in training_models.values() if m['candidate']=='M3-fixed200'
                            and m['seed']==model['seed'] and m.get('groups')==model.get('groups')
                            and 'history_contract' in m]
                if len(controls) != 1:
                    curves.append({'model_id':model['model_id'],'status':'paired_control_missing_or_ambiguous'})
                    continue
                filename=f'learning-pair-{model["model_id"]}.png'
                write_learning_curves([controls[0], model], run.path/filename)
                run.register_file(filename)
                curves.append({'model_id':model['model_id'],'control_model_id':controls[0]['model_id'],
                               'status':'complete','file':filename})
            report['learning_curves'] = curves
            report.update(candidate_state_history=state_history,terminal_runs=terminal_runs,procedures=procedures,
                          prepared_artifact_id=next(iter(source_ids)) if source_ids else None,
                          primary_comparison_cohort_id=next(iter(primary_cohorts)) if primary_cohorts else None)
            run.write_json('report.json', report)
            lines = ['# H4l research software report','','MC-only educational/technical demo.',
                     '',f"Primary M5/M4 comparison: {report['primary_comparison']['status']}",
                     '',f"Feature combination summary: {report['feature_combination_summary']['status']}",
                     '', '| Candidate | Status |','|---|---|']
            lines += [f'| {k} | {v} |' for k,v in statuses.items()]
            combination_summary=report['feature_combination_summary']
            if combination_summary['status']=='valid':
                seeds=combination_summary['seeds']
                lines += ['', '## Feature-combination results', '',
                          '| Subset | ' + ' | '.join(f's{seed} W68 / improvement' for seed in seeds) +
                          ' | Median W68 | Median improvement vs M0c |',
                          '|---|' + '|'.join('---:' for _ in seeds) + '|---:|---:|']
                for row in combination_summary['combinations']:
                    values=' | '.join(f"{item['width68']:.6g} / "
                                      f"{item['relative_improvement_vs_empty']:.4%}"
                                      for item in row['per_seed'])
                    lines.append(f"| {row['subset']} | {values} | {row['median_width68']:.6g} | "
                                 f"{row['median_relative_improvement_vs_empty']:.4%} |")
                best=combination_summary['best_combination']
                lines += ['',f"Best combination by paired-seed median improvement: **{best['subset']}** "
                          f"({best['median_relative_improvement_vs_empty']:.4%}; median W68 "
                          f"{best['median_width68']:.6g}).",
                          '', '## Group-level Shapley contributions', '',
                          '| Group | ' + ' | '.join(f's{seed}' for seed in seeds) + ' | Median | Range |',
                          '|---|' + '|'.join('---:' for _ in seeds) + '|---:|---:|']
                for group,row in combination_summary['shapley']['groups'].items():
                    values=' | '.join(f"{item['contribution']:.6g}" for item in row['per_seed'])
                    lines.append(f"| {group} | {values} | {row['median_contribution']:.6g} | "
                                 f"[{row['min_contribution']:.6g}, {row['max_contribution']:.6g}] |")
                interactions=combination_summary['shapley']['interactions']
                strongest_positive=max(interactions,key=lambda row:row['median_second_difference'])
                strongest_negative=min(interactions,key=lambda row:row['median_second_difference'])
                lines += ['', 'Strongest median positive interaction: '
                          f"{strongest_positive['pair']} conditioned on "
                          f"{strongest_positive['conditioning_subset'] or 'empty'} = "
                          f"{strongest_positive['median_second_difference']:.6g}.",
                          'Strongest median negative interaction: '
                          f"{strongest_negative['pair']} conditioned on "
                          f"{strongest_negative['conditioning_subset'] or 'empty'} = "
                          f"{strongest_negative['median_second_difference']:.6g}."]
            primary_comparison=report['primary_comparison']
            if primary_comparison['paired_seeds']:
                lines += ['', '## Primary M5/M4 comparison', '',
                          '| Seed | M4 W68 | M5 W68 | Relative improvement |',
                          '|---:|---:|---:|---:|']
                lines += [f"| {row['seed']} | {row['M4_width68']:.6g} | {row['M5_width68']:.6g} | "
                          f"{row['relative_improvement']:.4%} |"
                          for row in primary_comparison['paired_seeds']]
                if primary_comparison['median_relative_improvement'] is not None:
                    lines += ['',f"Five-seed median relative improvement: "
                              f"{primary_comparison['median_relative_improvement']:.4%}."]
            for curve in curves:
                if curve['status']=='complete':
                    lines += ['', f'![Paired training diagnostics]({curve["file"]})']
            lines += ['', 'Repository ARM64 authority: not_run.',
                      'Scientific numerical validation and external robustness require independent evidence.']
            (run.path/'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
            run.register_file('report.md')
        else:
            raise ResearchError('unknown research stage')
        if template_run is not None:
            template_run.file('templates.json')
            template_run.file('t1-validation.json')
        stage_wall = time.perf_counter()-stage_started
        run.manifest['performance'] = {'wall_seconds':stage_wall,
                                       'cpu_seconds':time.process_time()-stage_cpu}
        if root_metrics is not None:
            root_metrics['wall_seconds'] = stage_wall
            finalize_prepare_metrics(root_metrics)
            diagnosis = root_metrics['diagnosis']
            if show_prepare_metrics:
                print(
                    "[h4l prepare] diagnosis="
                    f"{diagnosis['classification']} dominant={diagnosis['dominant_phase']} "
                    f"average_span={root_metrics['average_span_length']} "
                    f"throughput={root_metrics['throughput_entries_per_second']:.1f} entries/s "
                    f"peak_rss={root_metrics.get('peak_rss_bytes')}",
                    file=sys.stderr,
                    flush=True,
                )
        if diagnostic_limit is not None:
            raise ResearchStateError(
                'Fixed-workload prepare diagnosis completed; this run is not a training input',
                status='diagnostic_complete',
            )
    result = {'status':run.status,'run_dir':str(args.run_dir),
              'publication_seconds':run.publication_seconds}
    if root_metrics is not None:
        returned_metrics = deepcopy(root_metrics)
        returned_metrics['publication_seconds'] = run.publication_seconds
        returned_metrics['wall_seconds'] += run.publication_seconds
        finalize_prepare_metrics(returned_metrics)
        result['prepare_diagnostics'] = returned_metrics
    return result
