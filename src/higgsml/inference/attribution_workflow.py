"""Immutable off-only analysis stages, reusing the H4l domain services."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np

from higgsml.artifacts import ResearchRun, read_run, read_json, digest_json, sha256_file
from higgsml.errors import ResearchError, ResearchStateError
from higgsml.data import load_research_data
from higgsml.modeling.discriminants import digest, predict_discriminant
from higgsml.inference.attribution import (FAMILY, SEEDS, SUBSETS, BUDGETS, candidate_key, candidate_keys,
    make_empty_model, empty_bundle, validate_bundle, structural_evidence, summarize)
from higgsml.inference.assessment import categorize_bundle
from higgsml.inference.templates import common_mass_grid, gate_g1, build_templates
from higgsml.inference.likelihood import run_asimov, build_model


def analysis_definition():
    value=read_json(Path(__file__).resolve().parents[3]/'config/protocols/feature_attribution_mass_off_v1.json')
    if value.get('family_id')!=FAMILY or value.get('candidate_keys')!=candidate_keys() or value.get('budgets')!=BUDGETS:
        raise ResearchError('analysis definition differs from implemented version')
    return value


def _load(path, protocol, *stages):
    return read_run(path, dataset=protocol['dataset'], protocol=protocol, stages=stages or None)


def _load_reusable(path, protocol, *stages, force=False):
    """Load a source run, allowing one non-scientific legacy metadata removal."""
    try:
        run = _load(path, protocol, *stages)
        return run, {
            'mode': 'exact',
            'source_protocol_sha256': run.manifest['protocol_sha256'],
            'current_protocol_sha256': digest_json(protocol),
            'source_protocol_path': str(run.file('protocol.json')),
        }
    except ResearchError as error:
        if str(error) != 'research artifact protocol mismatch':
            raise
        source_protocol = read_json(Path(path)/'protocol.json')
        normalized = deepcopy(source_protocol)
        validation = normalized.get('validation')
        compatible = (isinstance(validation, dict)
                      and validation.pop('repository_authority_validation', None) == 'not_run'
                      and normalized == protocol)
        if source_protocol.get('dataset') != protocol.get('dataset'):
            raise ResearchError('forced protocol reuse cannot change dataset')
        if not compatible and not force:
            raise error
        # Re-run the complete immutable-run validation against the original
        # snapshot. This keeps manifest, receipt, status and stage checks strict.
        run = read_run(path, dataset=protocol['dataset'], protocol=source_protocol,
                       stages=stages or None)
        return run, {
            'mode': ('normalized_legacy_validation_metadata' if compatible
                     else 'forced_protocol_mismatch_debug'),
            'source_protocol_sha256': digest_json(source_protocol),
            'current_protocol_sha256': digest_json(protocol),
            'source_protocol_path': str(run.file('protocol.json')),
            **({'removed_metadata': {
                'validation.repository_authority_validation': 'not_run',
            }} if compatible else {
                'warning': 'debug_only_protocol_consistency_bypassed',
            }),
        }


def _validate_reusable_bundle(bundle, protocol, prepared_id, *, source_protocol=None, force=False):
    """Validate a bundle against its exact current or accepted legacy protocol."""
    legacy_protocol = deepcopy(protocol)
    legacy_protocol.setdefault('validation', {})['repository_authority_validation'] = 'not_run'
    model_protocol_id = bundle.get('model', {}).get('protocol_id')
    threshold_protocol_id = bundle.get('thresholds', {}).get('protocol_id')
    candidates = [source_protocol] if source_protocol is not None else [protocol]
    if source_protocol is None and legacy_protocol != protocol:
        candidates.append(legacy_protocol)
    if source_protocol is not None and not force:
        normalized = deepcopy(source_protocol)
        validation = normalized.get('validation')
        if source_protocol != protocol and (not isinstance(validation, dict)
                or validation.pop('repository_authority_validation', None) != 'not_run'
                or normalized != protocol):
            raise ResearchError('off-family bundle protocol is not reusable')
    matches = [candidate for candidate in candidates
               if model_protocol_id == digest(candidate)
               and threshold_protocol_id == digest(candidate)]
    if len(matches) != 1:
        raise ResearchError('off-family bundle protocol is not reusable')
    validate_bundle(bundle, matches[0], prepared_id)


def audit_sources(source_root, prepared, protocol, *, force=False):
    """Only declared train/calibration artifacts and safe metadata; never scan events."""
    rows, bundles, upstreams, bundle_protocols = [], {}, [], {}
    source_root = Path(source_root).resolve()
    for seed in SEEDS:
        for subset in SUBSETS[1:]:
            key = candidate_key(seed, subset)
            name = f'groups-{subset}-m4l-off'
            row = {'candidate_key':key, 'status':'reuse_blocked', 'files':[]}
            try:
                train, train_protocol = _load_reusable(
                    source_root/f'seed{seed}'/'train'/name, protocol, 'train', force=force)
                calibrated, calibrated_protocol = _load_reusable(
                    source_root/f'seed{seed}'/'calibrate'/name, protocol, 'calibrate', force=force)
                for item in (train, calibrated):
                    context = item.manifest.get('context',{})
                    if (context.get('candidate_key') != key
                            or context.get('prepared_artifact_id') != prepared.manifest['artifact_id']
                            or context.get('population_id') != prepared.manifest.get('population_id')
                            or not any(u['artifact_id'] == prepared.manifest['artifact_id'] for u in item.manifest['upstreams'])):
                        raise ResearchError('reuse prepared/population/candidate binding mismatch')
                    for filename in ('manifest.json',*item.manifest['files']):
                        path = item.path/filename
                        if filename != 'manifest.json': item.file(filename)
                        row['files'].append({'path':str(path),'sha256':sha256_file(path),
                                             'size_bytes':path.stat().st_size,'mtime_ns':path.stat().st_mtime_ns})
                model = train.read_json('model.json')
                bundle = calibrated.read_json('calibration.json')
                source_protocol = calibrated.read_json('protocol.json')
                if train.read_json('protocol.json') != source_protocol:
                    raise ResearchError('train/calibration protocol snapshot mismatch')
                _validate_reusable_bundle(
                    bundle, protocol, prepared.manifest['artifact_id'],
                    source_protocol=source_protocol, force=force)
                if bundle['model'] != model or not any(u['artifact_id'] == train.manifest['artifact_id'] for u in calibrated.manifest['upstreams']):
                    raise ResearchError('calibration does not reuse bound checkpoint')
                selected = [r for r in model['history'] if r['epoch'] == model['selected_epoch']]
                if (len(selected) != 1 or selected[0]['validation_absolute_weight_auc'] != model['validation_absolute_weight_auc']
                        or not np.isfinite(model['validation_absolute_weight_auc'])):
                    raise ResearchError('selected-checkpoint validation AUC binding mismatch')
                row.update(status='reusable_exploratory',train_path=str(train.path),calibration_path=str(calibrated.path),
                           train_id=train.manifest['artifact_id'],calibration_id=calibrated.manifest['artifact_id'],
                           model_id=model['model_id'],diagnostics='recorded' if 'history_contract' in model else 'historical_detailed_history_missing')
                row['protocol_bindings'] = {
                    'train': train_protocol,
                    'calibration': calibrated_protocol,
                }
                bundles[key] = bundle
                bundle_protocols[key] = source_protocol
                upstreams.extend((train,calibrated))
            except (ResearchError, KeyError, TypeError, ValueError) as error:
                row['reason'] = str(error)
            rows.append(row)
    return rows, bundles, upstreams, bundle_protocols


def _unchanged(rows):
    for row in rows:
        for receipt in row['files']:
            path = Path(receipt['path'])
            if (not path.is_file() or path.stat().st_size != receipt['size_bytes']
                    or path.stat().st_mtime_ns != receipt['mtime_ns'] or sha256_file(path) != receipt['sha256']):
                raise ResearchError('immutable source changed: '+str(path))


def _qualification(prepared, t1, protocol, accepted_protocol_sha256, *, force=False):
    p0 = prepared.read_json('p0-validation.json') if 'p0-validation.json' in prepared.manifest['files'] else {}
    automated = [name for name,value in (('p0',p0),('t1',t1 or {}))
                 if 'automated' in str(value.get('independent_reference','')).lower()]
    # A free-form reference string is never a reviewed numerical evidence package.
    if force:
        return {'software_contract':'forced_debug_unverified', 'independent_reference':'pending',
                'automated_materials':automated,
                'assessment_access':'pending_independent_history_and_reference_review',
                'allowed_conclusions':'debug_only_no_scientific_conclusions',
                'missing':['protocol_consistency_bypassed','independent_P0_physical_definitions',
                           'signed_MC_T1_applicability_reference','assessment_history_review']}
    return {'software_contract':'valid' if t1 and t1.get('protocol_sha256') in accepted_protocol_sha256 else 'pending',
            'independent_reference':'pending', 'automated_materials':automated,
            'assessment_access':'pending_independent_history_and_reference_review',
            'allowed_conclusions':'exploratory_MC_model_self_only',
            'missing':['independent_P0_physical_definitions','signed_MC_T1_applicability_reference','assessment_history_review']}


def register(source_root, prepared_path, protocol, output, allowed_root, t1_path, *, force=False):
    prepared, prepared_protocol = _load_reusable(
        prepared_path, protocol, 'prepare', force=force)
    accepted_protocol_sha256 = {
        digest_json(protocol), prepared_protocol['source_protocol_sha256'],
    }
    t1 = read_json(Path(t1_path)) if t1_path else None
    if t1 and ((not force and t1.get('protocol_sha256') not in accepted_protocol_sha256)
               or t1.get('dataset') != protocol['dataset']):
        raise ResearchError('T1 reference binding mismatch')
    rows,bundles,upstreams,_ = audit_sources(
        source_root, prepared, protocol, force=force)
    # Inspect the original population's claim directory, not this new output root.
    claims_root = prepared.path.parents[1]/'.research-claims'
    claims = []
    if claims_root.exists():
        if claims_root.is_symlink(): raise ResearchError('unsafe historical claim directory')
        for path in sorted(claims_root.glob('*.json')):
            claim = read_json(path)
            if claim.get('population_id') == prepared.manifest.get('population_id') or claim.get('prepared_artifact_id') == prepared.manifest['artifact_id']:
                claims.append({'path':str(path),'sha256':sha256_file(path),'claim':claim})
    overlay = {'schema_version':'h4l-mass-off-registration-v1','protocol_id':'feature_attribution_mass_off_v1',
               'analysis_definition_sha256':digest_json(analysis_definition()),
               'family_id':FAMILY,'protocol_sha256':digest_json(protocol),'dataset':protocol['dataset'],
               'prepared_artifact_id':prepared.manifest['artifact_id'],'prepared_path':str(prepared.path),
               'population_id':prepared.manifest.get('population_id'),'source_root':str(Path(source_root).resolve()),
               'registration_status':'exploratory_posthoc','candidate_keys':candidate_keys(),'budgets':deepcopy(BUDGETS),
               'value_function':'-W68','estimator':'per_seed_then_median',
               'seed_resampling':'3125_ordered_joint_vectors_linear_quantiles',
               'pairing_rule':'joint_process_cells_nonnegative_with_exact_marginals_else_unavailable',
               'historical_claims':claims,
               'qualification':_qualification(
                   prepared,t1,protocol,accepted_protocol_sha256,force=force)}
    overlay['registration_id'] = digest_json(overlay)
    with ResearchRun(output,allowed_root=allowed_root,stage='attribution-register',dataset=protocol['dataset'],
                     protocol=protocol,upstreams=[prepared,*upstreams],
                     context={'forced_protocol_mismatch_debug':force}) as run:
        run.write_json('registration.json',overlay)
        run.write_json('reuse-audit.json',{
            'rows':rows, 'assessment_payload_read':False,
            'prepared_protocol_binding':prepared_protocol,
            'forced_protocol_mismatch_debug':force,
        })
        run.write_json('t1-validation.json',t1)
        if len(bundles) != 75:
            raise ResearchStateError('incomplete reusable off family',status='reuse_blocked')
    return _result(run,output)


def load_registration(path, protocol, *, force=False):
    run = _load(path,protocol,'attribution-register')
    forced = run.manifest.get('context',{}).get('forced_protocol_mismatch_debug') is True
    if forced and not force:
        raise ResearchError('forced debug registration requires --force')
    overlay = run.read_json('registration.json')
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError
    try:
        schema=read_json(Path(__file__).resolve().parents[3]/'config/schemas/h4l_mass_off_registration.schema.json')
        Draft202012Validator(schema).validate(overlay)
    except ValidationError as error:
        raise ResearchError('invalid registration schema: '+error.message) from error
    if (overlay.get('registration_id') != digest_json({k:v for k,v in overlay.items() if k!='registration_id'})
            or overlay.get('analysis_definition_sha256')!=digest_json(analysis_definition())
            or overlay.get('family_id') != FAMILY or overlay.get('budgets') != BUDGETS
            or overlay.get('candidate_keys') != candidate_keys() or overlay.get('protocol_sha256') != digest_json(protocol)
            or overlay.get('registration_status') != 'exploratory_posthoc'):
        raise ResearchError('invalid off-only registration')
    if (overlay.get('value_function')!='-W68' or overlay.get('estimator')!='per_seed_then_median'
            or overlay.get('pairing_rule')!='joint_process_cells_nonnegative_with_exact_marginals_else_unavailable'):
        raise ResearchError('unsupported attribution estimand/pairing rule')
    prepared, _ = _load_reusable(
        overlay['prepared_path'],protocol,'prepare',force=force)
    if prepared.manifest['artifact_id'] != overlay['prepared_artifact_id'] or prepared.manifest.get('population_id') != overlay['population_id']:
        raise ResearchError('registration prepared identity mismatch')
    _unchanged(run.read_json('reuse-audit.json')['rows'])
    return run,overlay,prepared


def _result(run, output):
    return {'status':run.status,'run_dir':str(output),'artifact_id':run.manifest.get('artifact_id')}


def nominal(registration_path, protocol, output, allowed_root, *, force=False):
    registered,overlay,prepared = load_registration(registration_path,protocol,force=force)
    rows,bundles,_,bundle_protocols = audit_sources(
        overlay['source_root'],prepared,protocol,force=force)
    if len(bundles) != 75: raise ResearchError('off-only reuse audit no longer complete')
    t1 = registered.read_json('t1-validation.json')
    with ResearchRun(output,allowed_root=allowed_root,stage='attribution-nominal',dataset=protocol['dataset'],
                     protocol=protocol,upstreams=[registered,prepared],
                     context={'family_id':FAMILY,'registration_id':overlay['registration_id'],
                              'forced_protocol_mismatch_debug':force}) as run:
        frame = load_research_data(
            prepared.file('events.jsonl'), protocol['dataset'], protocol,
            provenance_protocol=prepared.read_json('protocol.json'),
            force_protocol_mismatch=force)
        for seed in SEEDS:
            key = candidate_key(seed,'')
            bundles[key] = empty_bundle(
                make_empty_model(protocol,prepared.manifest['artifact_id'],seed),protocol)
            bundle_protocols[key] = protocol
        validation=frame.loc[frame.role=='validation']
        support={str(label):float(np.abs(validation.loc[validation.label==label,'physical_weight']).sum()) for label in (0,1)}
        run.write_json('empty-validation.json',{'status':'valid' if all(v>0 for v in support.values()) else 'unavailable',
                                               'auc':.5 if all(v>0 for v in support.values()) else None,
                                               'role':'validation','measure':'absolute_physical_weight','class_support':support})
        template = frame.loc[frame.role=='template'].copy()
        candidates = {key:categorize_bundle(bundle,template) for key,bundle in bundles.items()}
        empty = {key:bundle for key,bundle in bundles.items() if bundle['candidate_id']=='M0off'}
        grid = common_mass_grid(candidates,mass_edges=protocol['templates']['mass_edges'],
                                thresholds=protocol['templates'],structural_zero_bundles=empty)
        grid['family_id'] = FAMILY
        for key,value in grid['templates'].items():
            bundle = bundles[key]
            value.update(mapping_id=bundle['mapping_id'],candidate_id=bundle['candidate_id'],seed=bundle['seed'],
                         prepared_artifact_id=prepared.manifest['artifact_id'],family_id=FAMILY)
        g1 = gate_g1({k:'valid' for k in bundles},grid['templates'],t1)
        if set(grid['templates']) != set(candidate_keys()): raise ResearchError('G1 missing registered identity')
        run.write_json('templates.json',grid)
        run.write_json('calibrations.json',bundles)
        run.write_json('bundle-protocols.json',bundle_protocols)
        run.write_json('g1.json',{**g1,'family_id':FAMILY,'qualification':overlay['qualification']})
        run.write_json('t1-validation.json',t1)
        if g1['status'] != 'passed': raise ResearchStateError('off-only G1 failed',status='g1_not_passed')
        # Check the actual active-bin likelihood, not merely the constant score.
        mass = build_templates(template.assign(category=0),mass_edges=grid['mass_edges'],mapping_id='mass',
                               candidate_id='M0',categories=(0,),thresholds=protocol['templates'])
        _, mass_meta = build_model(mass,layer='T1',t1_validation=t1)
        for key in empty:
            _, metadata = build_model(grid['templates'][key],layer='T1',t1_validation=t1)
            if metadata['model_spec'] != mass_meta['model_spec']:
                raise ResearchError('M0off likelihood differs from same-grid no-category baseline')
        run.write_json('empty-likelihood-equivalence.json',{'status':'valid','identities':list(empty),
                        'mass_model_spec':mass_meta['model_spec'],'same_grid':grid['mass_edges']})
        run.write_json('qualification.json',overlay['qualification'])
        _unchanged(rows)
    return _result(run,output)


def load_nominal(path, registered, overlay, protocol, *, force=False):
    nominal_run = _load(path,protocol,'attribution-nominal')
    if not any(u['artifact_id']==registered.manifest['artifact_id'] for u in nominal_run.manifest['upstreams']):
        raise ResearchError('nominal registration mismatch')
    grid,bundles = nominal_run.read_json('templates.json'),nominal_run.read_json('calibrations.json')
    bundle_protocols = (nominal_run.read_json('bundle-protocols.json')
                        if 'bundle-protocols.json' in nominal_run.manifest['files'] else {})
    if grid.get('family_id')!=FAMILY or set(grid['templates'])!=set(candidate_keys()) or set(bundles)!=set(candidate_keys()):
        raise ResearchError('off-only nominal family mismatch')
    for key,bundle in bundles.items():
        _validate_reusable_bundle(
            bundle,protocol,overlay['prepared_artifact_id'],
            source_protocol=bundle_protocols.get(key),force=force)
        if bundle['key']!=key or grid['templates'][key]['mapping_id']!=bundle['mapping_id']:
            raise ResearchError('nominal mapping mismatch')
    if nominal_run.read_json('g1.json')['status']!='passed': raise ResearchError('nominal G1 did not pass')
    return nominal_run,grid,bundles


def freeze(registration_path, nominal_path, protocol, output, allowed_root, *, force=False):
    registered,overlay,prepared = load_registration(registration_path,protocol,force=force)
    nominal_run,grid,bundles = load_nominal(
        nominal_path,registered,overlay,protocol,force=force)
    value = {'status':'frozen','family_id':FAMILY,'protocol_sha256':digest_json(protocol),
             'registration_id':overlay['registration_id'],'prepared_artifact_id':prepared.manifest['artifact_id'],
             'template_artifact_id':nominal_run.manifest['artifact_id'],'mass_edges':grid['mass_edges'],
             'candidate_keys':candidate_keys(),'budgets':overlay['budgets'],
             'definition_digest':digest_json({'registration':overlay['registration_id'],'budgets':overlay['budgets']}),
             'mapping_ids':{k:digest_json(b) for k,b in bundles.items()},
             'assessment_access':'pending_independent_history_and_reference_review'}
    value['evidence_id'] = digest_json(value)
    with ResearchRun(output,allowed_root=allowed_root,stage='attribution-freeze',dataset=protocol['dataset'],
                     protocol=protocol,upstreams=[registered,prepared,nominal_run],
                     context={'forced_protocol_mismatch_debug':force}) as run:
        run.write_json('freeze.json',value)
    return _result(run,output)


def load_frozen(registration_path, nominal_path, freeze_path, protocol, *, force=False):
    registered,overlay,prepared = load_registration(registration_path,protocol,force=force)
    nominal_run,grid,bundles = load_nominal(
        nominal_path,registered,overlay,protocol,force=force)
    frozen_run = _load(freeze_path,protocol,'attribution-freeze')
    frozen = frozen_run.read_json('freeze.json')
    if (frozen.get('evidence_id')!=digest_json({k:v for k,v in frozen.items() if k!='evidence_id'})
            or frozen.get('registration_id')!=overlay['registration_id']
            or frozen.get('template_artifact_id')!=nominal_run.manifest['artifact_id']
            or frozen.get('prepared_artifact_id')!=prepared.manifest['artifact_id']
            or frozen.get('candidate_keys')!=candidate_keys() or frozen.get('budgets')!=BUDGETS
            or frozen.get('mass_edges')!=grid['mass_edges']
            or frozen.get('mapping_ids')!={k:digest_json(b) for k,b in bundles.items()}):
        raise ResearchError('off-only freeze binding mismatch')
    return registered,overlay,prepared,nominal_run,grid,bundles,frozen_run


def asimov_records(grid,bundles,protocol,t1,cohort):
    records,results = [],{}
    for seed in SEEDS:
        for subset in SUBSETS:
            key = candidate_key(seed,subset)
            model = bundles[key]['model']
            row = {'candidate_key':key,'seed':seed,'subset':subset,'family_id':FAMILY,'cohort_id':cohort,
                   'model_id':model['model_id'],'auc_model_id':model['model_id'],'auc_role':'validation',
                   'auc_measure':'absolute_physical_weight','auc':model.get('validation_absolute_weight_auc'),
                   'status':'fit_failed','width68':None}
            try:
                result = run_asimov(grid['templates'][key],protocol=protocol,layer='T1',t1_validation=t1,injections=[1.])
                interval = result['results'][0]['intervals'][0]
                row.update(status=interval['status'],width68=interval.get('width'))
                results[key] = result
            except ResearchError as error:
                row.update(status=error.status,reason=str(error))
            records.append(row)
    return records,results


def asimov(registration_path,nominal_path,freeze_path,protocol,output,allowed_root,*,force=False):
    registered,overlay,prepared,nominal_run,grid,bundles,frozen_run = load_frozen(
        registration_path,nominal_path,freeze_path,protocol,force=force)
    with ResearchRun(output,allowed_root=allowed_root,stage='attribution-asimov',dataset=protocol['dataset'],
                     protocol=protocol,upstreams=[registered,nominal_run,frozen_run],
                     context={'forced_protocol_mismatch_debug':force}) as run:
        records,results = asimov_records(grid,bundles,protocol,nominal_run.read_json('t1-validation.json'),nominal_run.manifest['artifact_id'])
        summary = summarize(records)
        run.write_json('inference.json',results)
        run.write_json('summary.json',summary)
        run.write_json('qualification.json',overlay['qualification'])
        if summary['status']!='valid': raise ResearchStateError('off-only Asimov incomplete',status='inference_incomplete')
    return _result(run,output)


def _assessment_frame(prepared,overlay,frozen_run,protocol,access_review,cell,*,force=False):
    """Verify independent evidence and consume one durable cell before decoding."""
    import os
    from higgsml.inference.evidence import validate_evidence_package, validate_off_p0
    if not access_review:
        raise ResearchStateError('independent P0/T1 and history/access review missing',status='assessment_qualification_pending')
    path=Path(access_review).resolve()
    review=read_json(path)
    if review.get('review_mode')=='single_researcher_self_review':
        from higgsml.inference.self_review import validate_self_review_access
        validate_self_review_access(review,path.parent)
        if (review['prepared_artifact_id']!=prepared.manifest['artifact_id']
                or review['population_id']!=overlay['population_id']
                or review['protocol_sha256']!=digest_json(protocol)
                or review['freeze_artifact_id']!=frozen_run.manifest['artifact_id']):
            raise ResearchError('single-researcher assessment access binding mismatch')
    else:
        _validate_independent_access_review(review,path,prepared,overlay,frozen_run,protocol)
    # Shared original root prevents a new output directory from clearing history.
    from higgsml.workflow import _claim_assessment
    root=prepared.path.parents[1]
    for dirname in ('.research-claims','.h4l-mass-off-v2-claims','.h4l-mass-off-v3-claims','.h4l-population-access'):
        old_claim=root/dirname
        if old_claim.is_symlink():
            raise ResearchError('unsafe historical claim directory')
        if old_claim.exists():
            for file in old_claim.glob('*.json'):
                if file.is_symlink():
                    raise ResearchError('unsafe historical claim receipt')
                receipt=read_json(file)
                previous=receipt.get('binding',receipt)
                if previous.get('stage')=='model-self':
                    continue
                if previous.get('population_id')==overlay['population_id'] and previous.get('freeze_artifact_id')!=frozen_run.manifest['artifact_id']:
                    raise ResearchStateError('population previously used under another freeze',status='assessment_already_started')
    _claim_assessment(root,prepared.manifest['artifact_id'],protocol,frozen_run.manifest['artifact_id'],
                      population_id=overlay['population_id'],repeat=True)
    cells=root/'.research-claims'/('off-cells-'+frozen_run.manifest['artifact_id'])
    if cells.is_symlink(): raise ResearchError('unsafe assessment budget ledger')
    cells.mkdir(exist_ok=True)
    cell_path=cells/(cell+'.json')
    try:
        with cell_path.open('x',encoding='utf-8') as stream:
            stream.write(__import__('json').dumps({'cell':cell,'freeze_id':frozen_run.manifest['artifact_id'],
                                                'access_review_sha256':sha256_file(path),'budgets':BUDGETS,
                                                'review_mode':review.get('review_mode','independent_validated')}))
            stream.flush(); os.fsync(stream.fileno())
    except FileExistsError as error:
        raise ResearchStateError('assessment cell budget already consumed; reuse published output',status='assessment_already_started') from error
    return load_research_data(
        prepared.file('events.jsonl'), protocol['dataset'], protocol,
        allow_assessment=True, assessment_freeze=frozen_run.read_json('freeze.json'),
        provenance_protocol=prepared.read_json('protocol.json'),
        force_protocol_mismatch=force)


def _validate_independent_access_review(review,path,prepared,overlay,frozen_run,protocol):
    from higgsml.inference.evidence import validate_evidence_package, validate_off_p0
    expected={'schema_version','status','prepared_artifact_id','population_id','protocol_sha256','freeze_artifact_id',
              'independent','reviewer','history_review','p0_reference','t1_reference','role_isolation'}
    if (set(review)!=expected or review['schema_version']!='h4l-off-assessment-access-v1'
            or review['status']!='validated' or review['independent'] is not True
            or not review['reviewer'] or 'automat' in review['reviewer'].lower()
            or review['prepared_artifact_id']!=prepared.manifest['artifact_id']
            or review['population_id']!=overlay['population_id'] or review['protocol_sha256']!=digest_json(protocol)
            or review['freeze_artifact_id']!=frozen_run.manifest['artifact_id']
            or review['role_isolation']!='physical_groups_verified_disjoint'
            or review['history_review']!='unused_independent_assessment_population'):
        raise ResearchError('invalid independent assessment access review')
    for field in ('p0_reference','t1_reference'):
        receipt=review[field]
        if not isinstance(receipt,dict) or set(receipt)!={'path','sha256','size_bytes'}:
            raise ResearchError('independent reference needs file receipt')
        reference=(path.parent/receipt['path']).resolve()
        if (Path(receipt['path']).is_absolute() or not reference.is_relative_to(path.parent)
                or not reference.is_file() or reference.is_symlink() or reference.stat().st_size!=receipt['size_bytes']
                or sha256_file(reference)!=receipt['sha256']):
            raise ResearchError('independent reference receipt mismatch')
        package=read_json(reference)
        if field=='t1_reference':
            verified=validate_evidence_package(package,dataset=protocol['dataset'],protocol_sha256=digest_json(protocol),package_root=reference.parent)
            if verified['status']!='validated' or verified['evidence_type']!='signed_mc_t1' or verified['prepared_artifact_id']!=prepared.manifest['artifact_id']:
                raise ResearchError('T1 independent numerical evidence out of scope')
        else:
            validate_off_p0(package,package_root=reference.parent,expected={
                'dataset':protocol['dataset'],'protocol_sha256':digest_json(protocol),
                'prepared_artifact_id':prepared.manifest['artifact_id'],
                'freeze_artifact_id':frozen_run.manifest['artifact_id'],
                'template_artifact_id':frozen_run.read_json('freeze.json')['template_artifact_id'],
                'source_evidence_sha256':sha256_file(prepared.file('p0-validation.json'))})


def evaluation_plan(protocol, registered, prepared, nominal_run, frozen_run, result_run):
    return {'schema_version':'h4l-mass-off-evaluation-plan-v1','dataset':protocol['dataset'],
            'family_id':FAMILY,'protocol_sha256':digest_json(protocol),'registration_status':'exploratory_posthoc',
            'candidate_keys':candidate_keys(),'budgets':deepcopy(BUDGETS),
            'inputs':dict(zip(('registration_artifact_id','prepared_artifact_id','template_artifact_id',
                              'freeze_artifact_id','asimov_artifact_id'),
                             (r.manifest['artifact_id'] for r in (registered,prepared,nominal_run,frozen_run,result_run))))}


def validate_evaluation_manifest(item, plan):
    context=item.manifest.get('context',{})
    stage=item.manifest.get('stage','').removeprefix('attribution-')
    mu=context.get('mu')
    if (item.manifest.get('stage')!='attribution-'+stage
            or stage not in {'mc-bootstrap','model-self','assessment','t2'}
            or type(mu) is not int or mu not in (0,1,2) or (stage in {'mc-bootstrap','t2'} and mu!=1)
            or context.get('family_id')!=FAMILY or context.get('budgets')!=BUDGETS
            or context.get('evaluation_plan_id')!=digest_json(plan)
            or context.get('evaluation_inputs')!=plan['inputs']
            or not set(plan['inputs'].values()) <= {u['artifact_id'] for u in item.manifest['upstreams']}):
        raise ResearchError('evaluation plan/family/cohort/budget/cell mismatch')
    return stage,mu


def evaluate(registration_path,nominal_path,freeze_path,protocol,output,allowed_root,*,stage,mu=1,access_review=None,
             evaluation_plan_path=None,result_path=None,force=False,workers=1,worker_threads=1,progress=None):
    from higgsml.inference.bootstrap import mass_off_mc_bootstrap
    from higgsml.inference.assessment import infer_assessment,run_assessment_t2,_joint_mother
    from higgsml.inference.likelihood import run_toys
    from higgsml.inference.reporting import coverage_summary,fit_diagnostics
    registered,overlay,prepared,nominal_run,grid,bundles,frozen_run=load_frozen(
        registration_path,nominal_path,freeze_path,protocol,force=force)
    if not evaluation_plan_path or not result_path:
        raise ResearchError('evaluation requires bound --evaluation-plan and --result-run')
    result_run=_load(result_path,protocol,'attribution-asimov')
    plan=evaluation_plan(protocol,registered,prepared,nominal_run,frozen_run,result_run)
    if read_json(Path(evaluation_plan_path))!=plan:
        raise ResearchError('evaluation plan differs from bound manifests')
    if not {registered.manifest['artifact_id'],nominal_run.manifest['artifact_id'],frozen_run.manifest['artifact_id']} <= {u['artifact_id'] for u in result_run.manifest['upstreams']}:
        raise ResearchError('Asimov evaluation cohort mismatch')
    if stage not in {'mc-bootstrap','model-self','assessment','t2'} or mu not in (0,1,2) or (stage in {'mc-bootstrap','t2'} and mu!=1):
        raise ResearchError('evaluation outside registered stage/injection')
    t1=nominal_run.read_json('t1-validation.json')
    access_mode=(read_json(Path(access_review)).get('review_mode','independent_validated')
                 if stage in {'assessment','t2'} and access_review else None)
    with ResearchRun(output,allowed_root=allowed_root,stage='attribution-'+stage,dataset=protocol['dataset'],protocol=protocol,
                     upstreams=[registered,prepared,nominal_run,frozen_run,result_run],
                     context={'family_id':FAMILY,'mu':mu,'budgets':BUDGETS,
                              'evaluation_plan_id':digest_json(plan),'evaluation_inputs':plan['inputs'],
                              'forced_protocol_mismatch_debug':force,
                              'assessment_access_mode':access_mode}) as run:
        run.write_json('evaluation-plan.json',plan)
        if stage in {'assessment','t2'}:
            frame=_assessment_frame(
                prepared,overlay,frozen_run,protocol,access_review,f'{stage}-mu{mu}',force=force)
            run.write_json('access-review.json',read_json(Path(access_review)))
        else:
            frame=load_research_data(
                prepared.file('events.jsonl'), protocol['dataset'], protocol,
                provenance_protocol=prepared.read_json('protocol.json'),
                force_protocol_mismatch=force)
        calibration=frame.loc[frame.role=='calibration'].copy()
        template=frame.loc[frame.role=='template'].copy()
        if stage=='mc-bootstrap':
            result=mass_off_mc_bootstrap(grid,bundles,calibration,template,protocol,t1_validation=t1,
                                         workers=workers,worker_threads=worker_threads,progress=progress)
        elif stage=='t2':
            result=run_assessment_t2(grid,bundles,calibration,template,frame.loc[frame.role=='assessment'].copy(),protocol,
                                    layer='T1',t1_validation=t1,mu=1,seed=BUDGETS['t2']['seed'],
                                    prepared_id=prepared.manifest['artifact_id'],freeze_id=frozen_run.manifest['artifact_id'],
                                    workers=workers,worker_threads=worker_threads,progress=progress)
            result['independent_unit']='20_outer_calibration_replicas_not_2000_unconditional_toys'
        else:
            role='template' if stage=='model-self' else 'assessment'
            mother=frame.loc[frame.role==role].copy()
            fallback=None
            if stage=='model-self':
                try:
                    _joint_mother(grid,bundles,mother,protocol,categorize_bundle,parent_role='template')
                except ResearchStateError as error:
                    fallback=str(error)
            if fallback is None:
                candidates=infer_assessment(grid,bundles,mother,protocol,layer='T1',t1_validation=t1,mu=mu,
                                            count=BUDGETS['toys']['count'],seed=BUDGETS['toys']['seed'],
                                            prepared_id=prepared.manifest['artifact_id'],freeze_id=frozen_run.manifest['artifact_id'],
                                            parent_role=role,workers=workers,worker_threads=worker_threads,progress=progress)
            else:
                candidates={}
                for index,(key,artifact) in enumerate(sorted(grid['templates'].items())):
                    try:
                        toys=run_toys(artifact,mu=mu,count=BUDGETS['toys']['count'],seed=BUDGETS['toys']['seed']+index,
                                      layer='T1',t1_validation=t1,auxiliary_generation=protocol['inference']['auxiliary_generation'],
                                      progress=progress)
                        candidates[key]={'status':toys['status'],'toys':toys,'coverage':{},'diagnostics':{}}
                        for i,level in enumerate((.68,.95)):
                            intervals=[r['intervals'][i] for r in toys['results']]
                            candidates[key]['coverage'][str(level)]=coverage_summary(intervals,mu=mu)
                            candidates[key]['diagnostics'][str(level)]=fit_diagnostics(intervals,mu=mu)
                    except ResearchError as error:
                        candidates[key]={'status':error.status,'reason':str(error),'planned_toys':BUDGETS['toys']['count']}
            for value in candidates.values():
                value['parent_role']=role
                value['expectation_kind']='model_self_closure' if role=='template' else 'frozen_assessment_parent'
                value['planned_toys']=BUDGETS['toys']['count']
                if role=='template' and 'toys' in value:
                    value['toys']['expectation_kind']='model_self'
            result={'status':'valid' if all(v['status']=='valid' for v in candidates.values()) else 'inference_incomplete',
                    'mu':mu,'planned_toys_per_candidate':BUDGETS['toys']['count'],'candidates':candidates,
                    'pairing':'unavailable' if fallback else 'shared_joint_physical_cells','pairing_reason':fallback,
                    'parent_role':role,'interpretation':'pilot_no_unregistered_pass_threshold'}
        result.update(evaluation_plan_id=digest_json(plan),evaluation_inputs=plan['inputs'],family_id=FAMILY)
        run.write_json('evaluation.json',result)
        run.write_json('qualification.json',overlay['qualification'])
        # Individual fit/replica failures are completed budget accounting, not fatal orchestration errors.
    return _result(run,output)


def report(registration_path,nominal_path,freeze_path,protocol,output,allowed_root,*,result_path,evaluation_paths=(),force=False):
    from higgsml.inference.report_exports import publish_mass_off_exports
    registered,overlay,prepared,nominal_run,grid,bundles,frozen_run=load_frozen(
        registration_path,nominal_path,freeze_path,protocol,force=force)
    result_run=_load(result_path,protocol,'attribution-asimov')
    required={registered.manifest['artifact_id'],nominal_run.manifest['artifact_id'],frozen_run.manifest['artifact_id']}
    if not required <= {u['artifact_id'] for u in result_run.manifest['upstreams']}:
        raise ResearchError('Asimov report cohort mismatch')
    summary=result_run.read_json('summary.json')
    if summary['status']!='valid': raise ResearchError('failed Asimov is not a successful report input')
    plan=evaluation_plan(protocol,registered,prepared,nominal_run,frozen_run,result_run)
    layers={'mc-bootstrap':{'status':'not_run'},'model-self':{},'assessment':{},'t2':{'status':'not_run'},
            'external_reference':{'status':'pending'}}
    for name in ('model-self','assessment'):
        layers[name]={str(mu):{'status':'not_run'} for mu in (0,1,2)}
    evaluations=[]
    access_modes=set()
    seen=set()
    for path in evaluation_paths:
        item=_load(path,protocol)
        if not required <= {u['artifact_id'] for u in item.manifest['upstreams']}:
            raise ResearchError('evaluation report cohort mismatch')
        stage,mu=validate_evaluation_manifest(item,plan)
        if item.read_json('evaluation-plan.json')!=plan: raise ResearchError('evaluation plan snapshot mismatch')
        if (stage,mu) in seen: raise ResearchError('duplicate evaluation budget cell')
        seen.add((stage,mu))
        value=item.read_json('evaluation.json')
        if (value.get('evaluation_plan_id')!=digest_json(plan) or value.get('evaluation_inputs')!=plan['inputs']
                or value.get('family_id')!=FAMILY):
            raise ResearchError('evaluation payload cohort mismatch')
        if stage in {'model-self','assessment'}: layers[stage][str(mu)]=value
        else: layers[stage]=value
        evaluations.append(item)
        if item.manifest.get('context',{}).get('assessment_access_mode'):
            access_modes.add(item.manifest['context']['assessment_access_mode'])
    with ResearchRun(output,allowed_root=allowed_root,stage='attribution-report',dataset=protocol['dataset'],protocol=protocol,
                     upstreams=[registered,nominal_run,frozen_run,result_run,*evaluations],
                     context={'forced_protocol_mismatch_debug':force,
                              'assessment_access_modes':sorted(access_modes)}) as run:
        result={'schema_version':'h4l-mass-off-report-v1','family_id':FAMILY,
                'mass_off_feature_comparisons':summary['per_seed'],'mass_off_feature_summary':summary,
                'mass_off_pairwise_comparisons':summary['pairwise_comparisons'],'evidence_layers':layers,
                'qualification':overlay['qualification'],'budgets':BUDGETS,'registration_status':overlay['registration_status'],
                'evaluation_plan':plan,'evaluation_plan_id':digest_json(plan),
                'forced_protocol_mismatch_debug':force,
                'assessment_access_modes':sorted(access_modes),
                'independent_validation':('independent_validated' in access_modes
                                          and 'single_researcher_self_review' not in access_modes)}
        run.write_json('evaluation-plan.json',plan)
        run.write_json('report.json',result)
        publish_mass_off_exports(run,result)
        _unchanged(registered.read_json('reuse-audit.json')['rows'])
    return _result(run,output)
