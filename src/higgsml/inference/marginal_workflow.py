"""Explicit v3 orchestration; original candidate artifacts retain their identities."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

from higgsml.artifacts import ResearchRun, read_run, read_json, digest_json, sha256_file
from higgsml.errors import ResearchError, ResearchStateError
from higgsml.data import load_research_data
from higgsml.inference import attribution_workflow as legacy
from higgsml.inference.attribution import FAMILY, BUDGETS, candidate_keys, summarize
from higgsml.inference.marginal_coupling import canonical_seed_blocks, pairing_contract, METADATA
from higgsml.inference.seed_blocks import stream_identity
from higgsml.inference.seed_schema import validate_workflow_document, _SCHEMAS


def matrix():
    return ([{'stage': 'mc-bootstrap', 'mu': 1, 'training_seed': None}]
            + [{'stage': stage, 'mu': mu, 'training_seed': block.seed}
               for stage in ('model-self', 'assessment') for mu in (0, 1, 2)
               for block in canonical_seed_blocks()]
            + [{'stage': 't2', 'mu': 1, 'training_seed': block.seed}
               for block in canonical_seed_blocks()])


def unit_name(unit):
    return f"{unit['stage']}-mu{unit['mu']}" + (f"-seed{unit['training_seed']}" if unit['training_seed'] else '')


def screening_policy(protocol):
    return {'policy': 'engineering_screen_not_scientific_validation', 'replicas': 200,
            'required_failures_per_seed': 0, 'sampling': 'group_bernoulli_thinning',
            'q_thin': protocol['roles']['assessment'] / protocol['roles']['template'],
            'seed': 42001, 'projection_rtol': 1e-10, 'projection_atol': 1e-10}


def _definition_digests(protocol):
    definition = legacy.analysis_definition()
    return {'candidate_definition_digest': digest_json({k:v for k,v in definition.items() if 'pairing' not in k}),
            'original_definition_digest': digest_json(definition),
            'evaluation_definition_digest': digest_json({'pairing_contract': pairing_contract(),
                'budgets': BUDGETS, 'matrix': matrix(), 'screening_policy': screening_policy(protocol)})}


def _seal(value, field):
    return {**value, field: digest_json(value)}


def _check_seal(value, field):
    if field != 'artifact_id':
        validate_workflow_document(value)
    if value.get(field) != digest_json({k: v for k, v in value.items() if k != field}):
        raise ResearchError(f'v3 {field} digest mismatch')


def _publish(output, allowed_root, protocol, stage, files, upstreams=()):
    with ResearchRun(output, allowed_root=allowed_root, stage='attribution-v3-' + stage,
                     dataset=protocol['dataset'], protocol=protocol, upstreams=list(upstreams)) as run:
        for name, value in files.items():
            if isinstance(value,dict) and value.get('schema_version') in _SCHEMAS:
                validate_workflow_document(value)
            run.write_json(name, value)
    return legacy._result(run, output)


def _load(path, protocol, stage):
    return read_run(path, dataset=protocol['dataset'], protocol=protocol,
                    stages=('attribution-v3-' + stage,))


def metadata_plan(protocol, *, stage=None, registration_path=None, nominal_path=None,
                  specification_path=None, freeze_path=None, result_path=None, plan_path=None,
                  prepared_path=None, j0_path=None, j1_path=None):
    """Validate safe manifests and DAG fields without opening any scientific payload."""
    paths = {'registration_artifact_id': (registration_path, 'register'),
             'template_artifact_id': (nominal_path, 'nominal'),
             'specification_artifact_id': (specification_path, 'evaluation-spec'),
             'freeze_artifact_id': (freeze_path, 'freeze'),
             'asimov_artifact_id': (result_path, 'asimov'),
             'prepared_artifact_id': (prepared_path, 'prepare'),
             'j0_artifact_id': (j0_path, 'support-j0'), 'j1_artifact_id': (j1_path, 'support-j1')}
    plan = read_json(Path(plan_path)) if plan_path else None
    if plan is not None:
        validate_plan(plan, protocol)
    manifests, unresolved = {}, []
    for key, (path, expected_stage) in paths.items():
        if not path:
            if plan and key in plan['inputs']:
                unresolved.append({'input': key, 'reason': 'path_not_supplied'})
            continue
        manifest_path = Path(path) / 'manifest.json'
        if not manifest_path.is_file():
            unresolved.append({'input': key, 'reason': 'manifest_missing'})
            continue
        manifest = read_json(manifest_path)
        expected = 'prepare' if expected_stage == 'prepare' else 'attribution-v3-' + expected_stage
        _check_seal(manifest, 'artifact_id')
        if (manifest.get('stage') != expected or manifest.get('status') != 'complete'
                or manifest.get('protocol_sha256') != digest_json(protocol)
                or manifest.get('dataset') != protocol['dataset']):
            raise ResearchError('v3 plan metadata stage/protocol/status mismatch: ' + key)
        if plan and key in plan['inputs'] and manifest['artifact_id'] != plan['inputs'][key]:
            raise ResearchError('v3 plan metadata identity mismatch: ' + key)
        manifests[key] = manifest
    dependencies = {'template_artifact_id': ['registration_artifact_id'],
                    'specification_artifact_id': ['registration_artifact_id', 'template_artifact_id', 'j0_artifact_id', 'j1_artifact_id'],
                    'freeze_artifact_id': ['registration_artifact_id', 'template_artifact_id', 'specification_artifact_id'],
                    'asimov_artifact_id': ['registration_artifact_id', 'template_artifact_id', 'freeze_artifact_id'],
                    'j1_artifact_id': ['j0_artifact_id']}
    for key, parents in dependencies.items():
        if key in manifests:
            actual = {item['artifact_id'] for item in manifests[key]['upstreams']}
            if any(manifests[parent]['artifact_id'] not in actual for parent in parents if parent in manifests):
                raise ResearchError('v3 plan metadata upstream mismatch: ' + key)
    if specification_path and 'specification_artifact_id' in manifests:
        spec = read_json(Path(specification_path) / 'evaluation-spec.json')
        validate_specification(spec, protocol)
        if plan and plan['specification'] != spec:
            raise ResearchError('v3 plan/specification mismatch')
    if freeze_path and 'freeze_artifact_id' in manifests:
        frozen = read_json(Path(freeze_path) / 'freeze.json')
        _check_seal(frozen, 'evidence_id')
        if plan and frozen['specification_id'] != plan['specification_id']:
            raise ResearchError('v3 plan/freeze specification mismatch')
    if not manifests and not unresolved:
        unresolved.append({'input': stage or 'workflow', 'reason': 'no_bound_inputs_supplied'})
    return {'status': 'unresolved' if unresolved else 'metadata_bound_payload_and_access_checks_pending',
            'unresolved': unresolved, 'validated_manifests': {k: v['artifact_id'] for k, v in manifests.items()},
            'assessment_payload_read': False, 'claims_consumed': False, 'matrix': matrix(),
            'unit_count_including_report': 37, 'upstream_payload_validation': 'deferred'}


def _id(run):
    return run.manifest['artifact_id']


def source_history(prepared):
    """Read identity receipts only, anchored to the original prepared lineage."""
    root = prepared.path.parents[1]
    found = []
    for directory in (root / '.research-claims', root / '.h4l-mass-off-v2-claims', root / '.h4l-mass-off-v3-claims', root / '.h4l-population-access'):
        if directory.is_symlink():
            raise ResearchError('unsafe source history directory')
        if directory.exists():
            for path in sorted(directory.glob('*.json')):
                if path.is_symlink():
                    raise ResearchError('unsafe source history receipt')
                value = read_json(path)
                binding = value.get('binding', value)
                if (binding.get('population_id') == prepared.manifest.get('population_id')
                        or binding.get('prepared_artifact_id') == _id(prepared)):
                    if binding.get('stage') == 'model-self':
                        continue
                    found.append({'path': str(path.resolve()), 'sha256': sha256_file(path), 'claim': value})
    return found


def register(source_root, prepared_path, protocol, output, allowed_root, t1_path=None, *,
             source_registration=None, force=False):
    if force:
        raise ResearchError('v3 compatibility requires exact audited semantics; --force is not an adapter')
    # Reuse the existing complete 75-model audit and deterministic empty definitions.
    source = Path(source_registration) if source_registration else Path(output).parent / 'source-register'
    if not source_registration and not source.exists():
        legacy.register(source_root, prepared_path, protocol, source, allowed_root, t1_path)
    original, overlay, prepared = legacy.load_registration(source, protocol)
    if Path(prepared_path).resolve() != prepared.path.resolve():
        raise ResearchError('v3 source registration prepared binding mismatch')
    if source_root and Path(source_root).resolve() != Path(overlay['source_root']).resolve():
        raise ResearchError('v3 source registration model root mismatch')
    value = _seal({'schema_version': 'h4l-mass-off-registration-v3', 'family_id': FAMILY,
        **_definition_digests(protocol),
        'source_registration_path': str(original.path), 'source_registration_id': _id(original),
        'prepared_artifact_id': _id(prepared), 'population_id': overlay['population_id'],
        'protocol_sha256': digest_json(protocol), 'candidate_keys': candidate_keys(),
        'pairing_contract': pairing_contract(), 'blocks': [b.as_dict() for b in canonical_seed_blocks()],
        'budgets': deepcopy(BUDGETS), 'source_history': source_history(prepared),
        'qualification': overlay['qualification'], 'registration_status': 'exploratory_v3',
        'assessment_payload_read': False}, 'registration_id')
    return _publish(output, allowed_root, protocol, 'register', {'registration.json': value}, [original, prepared])


def load_registration(path, protocol):
    registered = _load(path, protocol, 'register')
    value = registered.read_json('registration.json')
    _check_seal(value, 'registration_id')
    original, overlay, prepared = legacy.load_registration(value['source_registration_path'], protocol)
    if (value.get('schema_version') != 'h4l-mass-off-registration-v3'
            or value['source_registration_id'] != _id(original)
            or value['prepared_artifact_id'] != _id(prepared)
            or value['population_id'] != overlay['population_id']
            or value['protocol_sha256'] != digest_json(protocol)
            or value['candidate_keys'] != candidate_keys() or value['budgets'] != BUDGETS
            or value['pairing_contract'] != pairing_contract()
            or any(value.get(k) != v for k,v in _definition_digests(protocol).items())
            or value['blocks'] != [b.as_dict() for b in canonical_seed_blocks()]):
        raise ResearchError('v3 registration binding mismatch')
    return registered, value, original, overlay, prepared


def _semantics(nominal_run, grid, bundles, prepared, protocol):
    return {'protocol_sha256': digest_json(protocol), 'source_nominal_id': _id(nominal_run),
            'prepared_artifact_id': _id(prepared), 'population_id': prepared.manifest['population_id'],
            'mass_edges': grid['mass_edges'], 'templates_digest': digest_json(grid),
            'bundles_digest': digest_json(bundles), 'candidate_keys': candidate_keys(),
            'model_ids': {k: b['model_id'] for k, b in bundles.items()},
            'mapping_digests': {k: digest_json(b) for k, b in bundles.items()},
            'weight_semantics': 'signed_physical_yield_with_original_role_inclusion_probability',
            'development_probability': protocol['development_probability'], 'roles': protocol['roles'],
            'value_function': '-W68', 'estimator': 'per_seed_then_median'}


def nominal(registration_path, protocol, output, allowed_root, *, source_nominal=None):
    registered, value, original, overlay, prepared = load_registration(registration_path, protocol)
    source = Path(source_nominal) if source_nominal else Path(output).parent / 'source-nominal'
    if not source_nominal and not source.exists():
        legacy.nominal(original.path, protocol, source, allowed_root)
    source_run, grid, bundles = legacy.load_nominal(source, original, overlay, protocol)
    adapter = _seal({'schema_version': 'h4l-mass-off-compatibility-audit-v3',
        'status': 'compatible', 'registration_id': _id(registered), 'source_path': str(source_run.path),
        'semantics': _semantics(source_run, grid, bundles, prepared, protocol),
        'source_history': source_history(prepared), 'original_artifacts_relabelled': False}, 'adapter_id')
    return _publish(output, allowed_root, protocol, 'nominal', {'compatibility-audit.json': adapter},
                    [registered, source_run, prepared])


def load_nominal(registration_path, nominal_path, protocol):
    registered, value, original, overlay, prepared = load_registration(registration_path, protocol)
    adapter_run = _load(nominal_path, protocol, 'nominal')
    adapter = adapter_run.read_json('compatibility-audit.json')
    _check_seal(adapter, 'adapter_id')
    nominal_run, grid, bundles = legacy.load_nominal(adapter['source_path'], original, overlay, protocol)
    if (adapter['registration_id'] != _id(registered) or adapter['status'] != 'compatible'
            or adapter['semantics'] != _semantics(nominal_run, grid, bundles, prepared, protocol)):
        raise ResearchError('v3 nominal compatibility semantics changed')
    return registered, value, prepared, adapter_run, nominal_run, grid, bundles


def _frame(prepared, protocol, *, frozen=None):
    return load_research_data(prepared.file('events.jsonl'), protocol['dataset'], protocol,
        allow_assessment=frozen is not None, assessment_freeze=frozen,
        provenance_protocol=prepared.read_json('protocol.json'))


def _support_inputs(parent, grid, bundles, *, nominal_parent):
    from higgsml.inference.assessment import categorize_bundle
    parent = parent.copy()
    inputs = {}
    for block in canonical_seed_blocks():
        columns, expected = {}, {}
        for key in block.candidate_keys:
            column = 'category:' + key
            parent[column] = categorize_bundle(bundles[key], parent)['category'].to_numpy()
            columns[key] = column
            if nominal_parent:
                artifact = grid['templates'][key]
                for sample in artifact['samples']:
                    process = sample['name'] if 'process' in parent else int(sample['name'])
                    for category_index, category in enumerate(artifact['categories']):
                        for mass_bin in range(len(grid['mass_edges']) - 1):
                            expected[(key, process, mass_bin, category)] = sample['yield'][
                                category_index * (len(grid['mass_edges']) - 1) + mass_bin]
        inputs[block.seed] = {'block': block, 'category_columns': columns, 'mass_edges': grid['mass_edges']}
        samples=grid['templates'][block.candidate_keys[0]]['samples']
        roles={str(v['name']):'signal' if v['is_signal'] else 'background' for v in samples}
        if len(roles)!=len(samples) or any(
                {str(v['name']):'signal' if v['is_signal'] else 'background' for v in grid['templates'][key]['samples']} != roles
                for key in block.candidate_keys):
            raise ResearchError('candidate process role maps disagree')
        inputs[block.seed]['role_map']=roles
        if nominal_parent:
            inputs[block.seed]['expected_marginals'] = expected
    return parent, inputs


def _historical_access(prepared, protocol, freeze_path, access_path):
    frozen = legacy._load(freeze_path, protocol, 'attribution-freeze')
    value = frozen.read_json('freeze.json')
    if value.get('prepared_artifact_id') != _id(prepared):
        raise ResearchError('posthoc historical freeze prepared mismatch')
    review_path = Path(access_path).resolve()
    review = read_json(review_path)
    if review.get('review_mode') == 'single_researcher_self_review':
        from higgsml.inference.self_review import validate_self_review_access
        validate_self_review_access(review, review_path.parent)
        if review.get('freeze_artifact_id') != _id(frozen) or review.get('prepared_artifact_id') != _id(prepared):
            raise ResearchError('posthoc historical self-review binding mismatch')
    else:
        legacy._validate_independent_access_review(review, review_path, prepared,
            {'population_id': prepared.manifest['population_id']}, frozen, protocol)
    history = source_history(prepared)
    if not any(h['claim'].get('freeze_artifact_id') == _id(frozen) for h in history):
        raise ResearchError('posthoc support requires existing original population access claim')
    cells = prepared.path.parents[1] / '.research-claims' / ('off-cells-' + _id(frozen))
    if cells.is_symlink() or not cells.is_dir() or not any(
            read_json(p).get('access_review_sha256') == sha256_file(review_path)
            and read_json(p).get('freeze_id') == _id(frozen) for p in cells.glob('*.json')):
        raise ResearchError('posthoc support requires original budget/access receipt')
    return frozen, value, review


def support_check(registration_path, nominal_path, protocol, output, allowed_root, *, gate='J0',
                  j0_path=None, purpose='pre_freeze_support', historical_freeze=None, access_review=None):
    from higgsml.inference.marginal_support import run_j0, run_j1
    registered, value, prepared, adapter, nominal_run, grid, bundles = load_nominal(registration_path, nominal_path, protocol)
    upstreams = [registered, adapter]
    frozen = None
    if purpose == 'posthoc_support_diagnostic':
        if gate != 'J0' or not historical_freeze or not access_review:
            raise ResearchError('posthoc support requires historical freeze/access and J0 only')
        historical, frozen, review = _historical_access(prepared, protocol, historical_freeze, access_review)
        legacy.load_frozen(value['source_registration_path'], nominal_run.path, historical_freeze, protocol)
        if frozen.get('template_artifact_id') != _id(nominal_run):
            raise ResearchError('posthoc support must use original frozen nominal artifact')
        upstreams.append(historical)
    elif purpose != 'pre_freeze_support':
        raise ResearchError('unregistered support purpose')
    if gate == 'J1':
        if not j0_path:
            raise ResearchError('J1 requires completed J0')
        j0_run = _load(j0_path, protocol, 'support-j0')
        j0 = j0_run.read_json('marginal-support-summary.json')
        _validate_gate(j0, registered, adapter, protocol, 'J0')
        if j0['status'] != 'passed':
            raise ResearchStateError('J0 failed; J1 is not permitted', status='insufficient_statistics')
        upstreams.append(j0_run)
    frame = _frame(prepared, protocol, frozen=frozen)
    role = 'assessment' if frozen else 'template'
    parent, inputs = _support_inputs(frame.loc[frame.role == role], grid, bundles, nominal_parent=not frozen)
    if gate == 'J0':
        result = run_j0({seed: {'parent': parent, **arguments} for seed, arguments in inputs.items()})
    elif gate == 'J1':
        for arguments in inputs.values():
            arguments.pop('expected_marginals', None)
        policy = screening_policy(protocol)
        if not 0 < policy['q_thin'] <= 1:
            result = {'gate': 'J1', 'status': 'screening_design_unavailable', 'seeds': {}, 'records': []}
        else:
            result = run_j1(parent, block_inputs=inputs, q_thin=policy['q_thin'],
                            contract_digest=pairing_contract()['contract_digest'])
    else:
        raise ResearchError('support gate must be J0 or J1')
    if any(s.get('summary', s).get('qualification') == 'binding_error' for s in result['seeds'].values()):
        raise ResearchError('joint projection differs from frozen nominal template')
    result.update(schema_version='h4l-marginal-support-workflow-v1', registration_artifact_id=_id(registered),
        nominal_artifact_id=_id(adapter), policy=screening_policy(protocol), purpose=purpose,
        screening_policy_digest=digest_json(screening_policy(protocol)),
        parent_source={'prepared_artifact_id': _id(prepared), 'population_id': prepared.manifest['population_id'],
                       'role': role, 'source_path': str(prepared.path), 'source_nominal_artifact_id': _id(nominal_run)},
        assessment_payload_read=frozen is not None,
        evidence_scope='posthoc_diagnostic_after_assessment_failure' if frozen else 'engineering_screen_not_scientific_validation')
    with ResearchRun(output, allowed_root=allowed_root, stage='attribution-v3-support-' + gate.lower(),
                     dataset=protocol['dataset'], protocol=protocol, upstreams=upstreams) as run:
        validate_workflow_document(result)
        run.write_json('marginal-support-summary.json', result)
        if gate == 'J0':
            with (run.path / 'marginal-rates.jsonl').open('x', encoding='utf-8') as stream:
                for seed, diagnostic in result['seeds'].items():
                    for cell in diagnostic['cells']:
                        stream.write(json.dumps({'seed': int(seed), **cell}, allow_nan=False) + '\n')
            run.register_file('marginal-rates.jsonl')
    return legacy._result(run, output)


def _validate_gate(gate, registered, nominal_run, protocol, name):
    validate_workflow_document(gate)
    if (gate.get('gate') != name or gate.get('registration_artifact_id') != _id(registered)
            or gate.get('nominal_artifact_id') != _id(nominal_run)
            or gate.get('policy') != screening_policy(protocol)
            or gate.get('screening_policy_digest') != digest_json(screening_policy(protocol))
            or gate.get('purpose') != 'pre_freeze_support' or gate.get('assessment_payload_read') is not False):
        raise ResearchError('support gate binding/purpose mismatch')
    if gate['status'] == 'passed':
        seeds = gate.get('seeds', {})
        if set(seeds) != {str(seed) for seed in range(42,47)}:
            raise ResearchError('passed gate requires all five seeds')
        if name == 'J0' and any(r['summary'].get('qualification') != 'valid' for r in seeds.values()):
            raise ResearchError('passed J0 includes unqualified seed')
        if name == 'J1' and (gate.get('replicas') != 200 or len(gate.get('records',[])) != 200
                or any(r.get('support_failures') != 0 or r.get('replicas') != 200 for r in seeds.values())
                or any(r['seeds'][seed]['qualification'] != 'valid' for r in gate['records'] for seed in seeds)):
            raise ResearchError('passed J1 differs from fixed 0/200 screening contract')


def specification(registration_path, nominal_path, protocol, output, allowed_root, *, j0_path, j1_path):
    registered, value, prepared, adapter, nominal_run, grid, bundles = load_nominal(registration_path, nominal_path, protocol)
    gates = [_load(j0_path, protocol, 'support-j0'), _load(j1_path, protocol, 'support-j1')]
    for name, gate in zip(('J0', 'J1'), gates):
        checked = gate.read_json('marginal-support-summary.json')
        _validate_gate(checked, registered, adapter, protocol, name)
        if checked['status'] != 'passed':
            raise ResearchStateError('support qualification failed; freeze blocked', status='insufficient_statistics')
    if _id(gates[0]) not in {u['artifact_id'] for u in gates[1].manifest['upstreams']}:
        raise ResearchError('J1 does not bind the qualified J0')
    spec = _seal({'schema_version': 'h4l-mass-off-evaluation-spec-v3',
        'registration_artifact_id': _id(registered), 'nominal_artifact_id': _id(adapter),
        'prepared_artifact_id': _id(prepared), 'population_id': value['population_id'],
        'protocol_sha256': digest_json(protocol), 'candidate_keys': candidate_keys(),
        'blocks': [b.as_dict() for b in canonical_seed_blocks()], 'pairing_contract': pairing_contract(),
        'budgets': deepcopy(BUDGETS), 'matrix': matrix(), 'screening_policy': screening_policy(protocol),
        'gate_artifact_ids': list(map(_id, gates)),
        'support_qualification': gates[0].read_json('marginal-support-summary.json')['seeds']['42']['summary']['identity_qualification'],
        'source_history': source_history(prepared),
        'rng': {'algorithm': 'sha256-full-256-PCG64', 'version': 'h4l-marginal-stream-v1'},
        'semantics': _semantics(nominal_run, grid, bundles, prepared, protocol),
        'evidence_scope': 'MC_only_exploratory_within_seed'}, 'specification_id')
    return _publish(output, allowed_root, protocol, 'evaluation-spec', {'evaluation-spec.json': spec},
                    [registered, adapter, *gates])


def validate_specification(spec, protocol):
    _check_seal(spec, 'specification_id')
    if (spec.get('schema_version') != 'h4l-mass-off-evaluation-spec-v3'
            or any(key in spec for key in ('freeze_artifact_id', 'evaluation_plan_id', 'asimov_artifact_id'))
            or spec.get('protocol_sha256') != digest_json(protocol) or spec.get('matrix') != matrix()
            or spec.get('candidate_keys') != candidate_keys() or spec.get('budgets') != BUDGETS
            or spec.get('pairing_contract') != pairing_contract()
            or spec.get('blocks') != [b.as_dict() for b in canonical_seed_blocks()]
            or spec.get('screening_policy') != screening_policy(protocol)):
        raise ResearchError('invalid v3 specification or cyclic dependency')


def freeze(registration_path, nominal_path, protocol, output, allowed_root, *, specification_path):
    registered, value, prepared, adapter, nominal_run, grid, bundles = load_nominal(registration_path, nominal_path, protocol)
    spec_run = _load(specification_path, protocol, 'evaluation-spec')
    spec = spec_run.read_json('evaluation-spec.json')
    validate_specification(spec, protocol)
    if (spec['registration_artifact_id'] != _id(registered) or spec['nominal_artifact_id'] != _id(adapter)
            or spec['semantics'] != _semantics(nominal_run, grid, bundles, prepared, protocol)):
        raise ResearchError('freeze specification source mismatch')
    frozen = _seal({'schema_version': 'h4l-mass-off-freeze-v3', 'status': 'frozen',
        'protocol_sha256': digest_json(protocol), 'specification_id': spec['specification_id'],
        'specification_path': str(spec_run.path), 'specification_artifact_id': _id(spec_run),
        'registration_artifact_id': _id(registered), 'template_artifact_id': _id(adapter),
        'prepared_artifact_id': _id(prepared), 'mass_edges': grid['mass_edges'],
        'assessment_access': 'pending_independent_history_and_reference_review'}, 'evidence_id')
    return _publish(output, allowed_root, protocol, 'freeze', {'freeze.json': frozen}, [registered, adapter, spec_run])


def load_frozen(registration_path, nominal_path, freeze_path, protocol):
    values = load_nominal(registration_path, nominal_path, protocol)
    registered, value, prepared, adapter, nominal_run, grid, bundles = values
    frozen_run = _load(freeze_path, protocol, 'freeze')
    frozen = frozen_run.read_json('freeze.json')
    _check_seal(frozen, 'evidence_id')
    spec_run = _load(frozen['specification_path'], protocol, 'evaluation-spec')
    spec = spec_run.read_json('evaluation-spec.json')
    validate_specification(spec, protocol)
    if (frozen['specification_id'] != spec['specification_id'] or frozen['specification_artifact_id'] != _id(spec_run)
            or frozen['registration_artifact_id'] != _id(registered) or frozen['template_artifact_id'] != _id(adapter)
            or frozen['prepared_artifact_id'] != _id(prepared) or frozen['protocol_sha256'] != digest_json(protocol)
            or frozen['mass_edges'] != grid['mass_edges'] or frozen['status'] != 'frozen'
            or spec['semantics'] != _semantics(nominal_run, grid, bundles, prepared, protocol)):
        raise ResearchError('v3 frozen cohort mismatch')
    return (*values, frozen_run, spec)


def asimov(registration_path, nominal_path, freeze_path, protocol, output, allowed_root):
    registered, value, prepared, adapter, nominal_run, grid, bundles, frozen_run, spec = load_frozen(
        registration_path, nominal_path, freeze_path, protocol)
    records, results = legacy.asimov_records(grid, bundles, protocol,
        nominal_run.read_json('t1-validation.json'), _id(adapter))
    summary = summarize(records)
    return _publish(output, allowed_root, protocol, 'asimov', {
        'summary.json': summary, 'inference.json': results,
        'binding.json': {'specification_id': spec['specification_id'], 'freeze_artifact_id': _id(frozen_run),
                         'value_source': 'nominal_asimov', 'source_nominal_artifact_id': _id(nominal_run)}},
        [registered, adapter, frozen_run])


def evaluation_plan(registration_path, nominal_path, freeze_path, result_path, protocol, output, allowed_root):
    registered, value, prepared, adapter, nominal_run, grid, bundles, frozen_run, spec = load_frozen(
        registration_path, nominal_path, freeze_path, protocol)
    result = _load(result_path, protocol, 'asimov')
    binding = result.read_json('binding.json')
    if binding['specification_id'] != spec['specification_id'] or binding['freeze_artifact_id'] != _id(frozen_run):
        raise ResearchError('Asimov/specification binding mismatch')
    plan = _seal({'schema_version': 'h4l-mass-off-evaluation-plan-v3', 'specification': spec,
        'specification_id': spec['specification_id'], 'pairing_scope': 'within_seed', 'cross_seed_pairing': 'none',
        'inputs': {'registration_artifact_id': _id(registered), 'prepared_artifact_id': _id(prepared),
                   'template_artifact_id': _id(adapter), 'freeze_artifact_id': _id(frozen_run), 'asimov_artifact_id': _id(result)},
        'matrix': matrix(), 'scientific_unit_count': 36, 'unit_count_including_report': 37}, 'evaluation_plan_id')
    return _publish(output, allowed_root, protocol, 'evaluation-plan', {'evaluation-plan.json': plan},
                    [registered, adapter, frozen_run, result])


def validate_plan(plan, protocol):
    _check_seal(plan, 'evaluation_plan_id')
    validate_specification(plan['specification'], protocol)
    if (plan.get('schema_version') != 'h4l-mass-off-evaluation-plan-v3'
            or plan['specification_id'] != plan['specification']['specification_id']
            or plan.get('matrix') != matrix() or plan.get('unit_count_including_report') != 37
            or plan.get('pairing_scope') != 'within_seed' or plan.get('cross_seed_pairing') != 'none'):
        raise ResearchError('invalid v3 evaluation plan')


def _bound_plan(path, protocol, registered, prepared, adapter, frozen_run, spec, result_path):
    plan = read_json(Path(path))
    validate_plan(plan, protocol)
    result = _load(result_path, protocol, 'asimov')
    expected = {'registration_artifact_id': _id(registered), 'prepared_artifact_id': _id(prepared),
                'template_artifact_id': _id(adapter), 'freeze_artifact_id': _id(frozen_run), 'asimov_artifact_id': _id(result)}
    if plan['inputs'] != expected or plan['specification'] != spec:
        raise ResearchError('v3 evaluation plan differs from bound inputs')
    result_binding = result.read_json('binding.json')
    if result_binding.get('specification_id') != spec['specification_id'] or result_binding.get('freeze_artifact_id') != _id(frozen_run):
        raise ResearchError('v3 Asimov binding differs from frozen specification')
    return plan, result


def _access(prepared, frozen_run, spec, plan, protocol, access_path):
    if not access_path:
        raise ResearchStateError('v3 assessment requires reviewed eligible source',
                                 status='blocked_missing_eligible_assessment_source')
    path = Path(access_path).resolve()
    receipt = read_json(path)
    _check_seal(receipt, 'access_id')
    if (receipt.get('schema_version') != 'h4l-off-assessment-access-v3'
            or receipt.get('specification_id') != spec['specification_id']
            or receipt.get('evaluation_plan_id') != plan['evaluation_plan_id']
            or receipt.get('blocks') != spec['blocks']):
        raise ResearchError('v3 access receipt binding mismatch')
    original_path = Path(receipt['source_review']['path'])
    if sha256_file(original_path) != receipt['source_review']['sha256']:
        raise ResearchError('v3 source review changed')
    original = read_json(original_path)
    expected_mode = original.get('review_mode', 'independent_validated')
    expected_independence = original.get('independent') is True and expected_mode != 'single_researcher_self_review'
    if receipt.get('review_mode') != expected_mode or receipt.get('independent') is not expected_independence:
        raise ResearchError('v3 access receipt cannot upgrade source review qualification')
    if original.get('review_mode') == 'single_researcher_self_review':
        from higgsml.inference.self_review import validate_self_review_access
        validate_self_review_access(original, original_path.parent)
        for key, expected in {'prepared_artifact_id': _id(prepared), 'population_id': prepared.manifest['population_id'],
                              'protocol_sha256': digest_json(protocol), 'freeze_artifact_id': _id(frozen_run)}.items():
            if original.get(key) != expected:
                raise ResearchError('v3 self-review source binding mismatch')
    else:
        legacy._validate_independent_access_review(original, original_path, prepared,
            {'population_id': prepared.manifest['population_id']}, frozen_run, protocol)
    for history in source_history(prepared):
        previous = history['claim'].get('binding', history['claim'])
        if previous.get('freeze_artifact_id') != _id(frozen_run):
            raise ResearchStateError('historically opened population cannot become fresh v3 source',
                                     status='blocked_missing_eligible_assessment_source')
    return receipt


def validate_access(registration_path, nominal_path, freeze_path, result_path, protocol, *,
                    evaluation_plan_path, access_review):
    """Validate the complete assessment access binding without consuming a claim."""
    registered, value, prepared, adapter, nominal_run, grid, bundles, frozen_run, spec = load_frozen(
        registration_path, nominal_path, freeze_path, protocol)
    plan, result = _bound_plan(evaluation_plan_path, protocol, registered, prepared, adapter,
                               frozen_run, spec, result_path)
    return _access(prepared, frozen_run, spec, plan, protocol, access_review)


def access_adapter(registration_path, nominal_path, freeze_path, protocol, output, allowed_root, *,
                   evaluation_plan_path, result_path, access_review):
    registered, value, prepared, adapter, nominal_run, grid, bundles, frozen_run, spec = load_frozen(
        registration_path, nominal_path, freeze_path, protocol)
    plan, result = _bound_plan(evaluation_plan_path, protocol, registered, prepared, adapter, frozen_run, spec, result_path)
    original = Path(access_review).resolve()
    review = read_json(original)
    receipt = _seal({'schema_version': 'h4l-off-assessment-access-v3',
        'specification_id': spec['specification_id'], 'evaluation_plan_id': plan['evaluation_plan_id'],
        'blocks': spec['blocks'], 'source_review': {'path': str(original), 'sha256': sha256_file(original)},
        'review_mode': review.get('review_mode', 'independent_validated'),
        'independent': review.get('independent') is True and review.get('review_mode') != 'single_researcher_self_review',
        'source_history': source_history(prepared)}, 'access_id')
    # Validate before publication without creating any access claims.
    # Validation accepts a value to avoid creating a transient published receipt.
    _validate_access_source(receipt, original, prepared, frozen_run, spec, plan, protocol)
    return _publish(output, allowed_root, protocol, 'access-review', {'validated-off-assessment-access.json': receipt},
                    [registered, frozen_run, result])


def _validate_access_source(receipt, original, prepared, frozen_run, spec, plan, protocol):
    review = read_json(original)
    if review.get('review_mode') == 'single_researcher_self_review':
        from higgsml.inference.self_review import validate_self_review_access
        validate_self_review_access(review, original.parent)
        if (review.get('freeze_artifact_id') != _id(frozen_run) or review.get('prepared_artifact_id') != _id(prepared)
                or review.get('population_id') != prepared.manifest['population_id']
                or review.get('protocol_sha256') != digest_json(protocol)):
            raise ResearchError('v3 self-review source binding mismatch')
    else:
        legacy._validate_independent_access_review(review, original, prepared,
            {'population_id': prepared.manifest['population_id']}, frozen_run, protocol)
    if source_history(prepared):
        raise ResearchStateError('new access requires unused eligible source', status='blocked_missing_eligible_assessment_source')


def evaluation_binding(prepared, frozen_run, spec, plan, *, stage, mu, training_seed, access_receipt):
    from higgsml.inference.marginal_evaluation_state import SeedEvaluationBinding
    block = next((b for b in canonical_seed_blocks() if b.seed == training_seed), None)
    if block is None or {'stage': stage, 'mu': mu, 'training_seed': training_seed} not in matrix():
        raise ResearchError('unregistered v3 block evaluation')
    budget = ({'planned_outer': BUDGETS['t2']['outer_replicas'], 'planned_inner_per_outer': BUDGETS['t2']['inner_toys']}
              if stage == 't2' else {'planned_toys_per_candidate': BUDGETS['toys']['count']})
    rng = stream_identity(contract_digest=block.pairing_contract_digest, stage=stage, mu=mu,
        training_seed=training_seed, outer_index=None, stream_kind='physical_poisson', toy_base_seed=BUDGETS['toys']['seed'])
    return block, SeedEvaluationBinding(prepared.manifest['population_id'], _id(frozen_run),
        spec['specification_id'], plan['evaluation_plan_id'], pairing_contract()['contract_digest'],
        stage, mu, training_seed, block.candidate_keys, access_receipt, budget, rng)


def evaluate(registration_path, nominal_path, freeze_path, protocol, output, allowed_root, *, stage, mu=1,
             training_seed=None, access_review=None, evaluation_plan_path=None, result_path=None,
             workers=1, worker_threads=1, progress=None, retry_failed=False):
    from higgsml.inference.seed_evaluation import evaluate_seed_block, evaluate_seed_t2, make_t2_outer_multiplicities
    from higgsml.inference.marginal_evaluation_state import (resolve_seed_evaluation, claim_seed_evaluation,
        publish_seed_evaluation_terminal, recover_seed_evaluation_publication,
        record_seed_evaluation_recomputation)
    registered, value, prepared, adapter, nominal_run, grid, bundles, frozen_run, spec = load_frozen(
        registration_path, nominal_path, freeze_path, protocol)
    plan, result = _bound_plan(evaluation_plan_path, protocol, registered, prepared, adapter, frozen_run, spec, result_path)
    if stage == 'mc-bootstrap':
        if training_seed is not None or mu != 1:
            raise ResearchError('MC bootstrap uses complete 80-identity family at mu=1')
        if Path(output).exists():
            existing = _load(output, protocol, 'mc-bootstrap')
            if existing.read_json('evaluation.json')['evaluation_plan_id'] != plan['evaluation_plan_id']:
                raise ResearchError('existing MC bootstrap binding mismatch')
            return {'status': 'complete', 'run_dir': str(output), 'artifact_id': _id(existing)}
        from higgsml.inference.bootstrap import mass_off_mc_bootstrap
        frame = _frame(prepared, protocol)
        answer = mass_off_mc_bootstrap(grid, bundles, frame.loc[frame.role == 'calibration'].copy(),
            frame.loc[frame.role == 'template'].copy(), protocol, t1_validation=nominal_run.read_json('t1-validation.json'),
            workers=workers, worker_threads=worker_threads, progress=progress)
        answer.update(evaluation_plan_id=plan['evaluation_plan_id'], value_source='mc_bootstrap_replica')
        return _publish(output, allowed_root, protocol, 'mc-bootstrap', {'evaluation.json': answer},
                        [registered, adapter, frozen_run, result])
    receipt = (_access(prepared, frozen_run, spec, plan, protocol, access_review) if stage in {'assessment', 't2'}
               else {'review_mode': 'template_only_no_assessment_access', 'specification_id': spec['specification_id']})
    block, binding = evaluation_binding(prepared, frozen_run, spec, plan, stage=stage, mu=mu,
                                        training_seed=training_seed, access_receipt=receipt)
    common = dict(output_dir=output, claims_root=prepared.path.parents[1], dataset=protocol['dataset'],
                  protocol=protocol, binding=binding)
    action = resolve_seed_evaluation(**common, retry_failed=retry_failed)
    if action == 'blocked_consumed_budget':
        raise ResearchStateError('claimed evaluation output missing or damaged; recomputation prohibited',
                                 status='blocked_consumed_budget')
    if action == 'recover_publication':
        item = recover_seed_evaluation_publication(**common, allowed_root=allowed_root)
        return {'status': 'complete', 'run_dir': str(output), 'artifact_id': _id(item)}
    if action == 'skip_terminal':
        return {'status': 'complete', 'run_dir': str(output), 'resolution': action}
    recomputation = None
    if action == 'run':
        claim_seed_evaluation(claims_root=common['claims_root'], output_dir=output, binding=binding)
    elif action == 'retry_failed':
        recomputation = record_seed_evaluation_recomputation(
            claims_root=common['claims_root'], output_dir=output, binding=binding)
    # The durable claim above precedes all assessment numeric decoding.
    frame = _frame(prepared, protocol, frozen=frozen_run.read_json('freeze.json') if stage in {'assessment', 't2'} else None)
    options = dict(block=block, mu=mu, toy_base_seed=BUDGETS['toys']['seed'], layer='T1',
        t1_validation=nominal_run.read_json('t1-validation.json'), prepared_id=_id(prepared), freeze_id=_id(frozen_run),
        workers=workers, worker_threads=worker_threads, progress=progress)
    if stage == 't2':
        calibration = frame.loc[frame.role == 'calibration'].copy()
        outer = make_t2_outer_multiplicities(calibration, contract_digest=block.pairing_contract_digest,
            outer_replicas=BUDGETS['t2']['outer_replicas'], toy_base_seed=BUDGETS['t2']['seed'])
        configured = deepcopy(protocol)
        configured['inference'].update(outer_replicas=BUDGETS['t2']['outer_replicas'], inner_toys=BUDGETS['t2']['inner_toys'])
        terminal = evaluate_seed_t2(grid, bundles, calibration, frame.loc[frame.role == 'template'].copy(),
            frame.loc[frame.role == 'assessment'].copy(), configured, outer_multiplicities=outer, **options)
    else:
        role = 'template' if stage == 'model-self' else 'assessment'
        terminal = evaluate_seed_block(grid, bundles, frame.loc[frame.role == role].copy(), protocol,
            stage=stage, count=BUDGETS['toys']['count'], **options)
    item = publish_seed_evaluation_terminal(**common, allowed_root=allowed_root, terminal=terminal,
        upstreams=(registered, adapter, frozen_run, result), recomputation=recomputation)
    return {'status': 'complete', 'scientific_status': terminal['scientific_status'], 'run_dir': str(output), 'artifact_id': _id(item)}


def descriptive_seed_diagnostics(entries):
    """Coverage/failure descriptions only; no Toy value function or paired seed indexes."""
    import math
    from statistics import median
    from higgsml.inference.attribution import SUBSETS, candidate_key
    metrics = ('conditional_coverage','success_and_coverage_fraction','failure_rate')
    rows, aggregates = [], []
    for stage in ('model-self','assessment','t2'):
      for mu in ((1,) if stage == 't2' else (0,1,2)):
        for subset in SUBSETS:
          for level in ('.68','.95'):
            level = str(float(level))
            vector = []
            for seed in range(42,47):
                unit = entries[unit_name({'stage':stage,'mu':mu,'training_seed':seed})]
                value = unit.get('value') or {}
                key = candidate_key(seed,subset)
                outer_values = []
                if stage == 't2':
                    for outer in value.get('outer_records',[]):
                        cov = outer.get('result',{}).get('candidates',{}).get(key,{}).get('coverage',{}).get(level,{})
                        outer_values.append({'outer_index':outer.get('replica'),'status':cov.get('status','not_run'),
                                             **{metric:cov.get(metric) for metric in metrics}})
                    complete = len(outer_values)==20 and all(r['status']=='valid' for r in outer_values)
                    coverage = {metric: sum(r[metric] for r in outer_values)/20
                        if complete and all(isinstance(r[metric],(int,float)) and math.isfinite(r[metric]) for r in outer_values)
                        else None for metric in metrics}
                    status = 'valid' if complete else unit['status'] if unit['status']!='valid' else 'inference_incomplete'
                else:
                    candidate = next((r for r in value.get('candidate_results',[]) if r['candidate_id']==key),{})
                    coverage = dict(candidate.get('result',{}).get('coverage',{}).get(level,{}))
                    planned = value.get('planned_toys_per_candidate',0)
                    if candidate and planned and 'valid_fits' in candidate:
                        coverage.setdefault('failure_rate',(planned-candidate['valid_fits'])/planned)
                        if candidate['valid_fits']==0:
                            coverage.setdefault('success_and_coverage_fraction',0.)
                    status = 'valid' if coverage.get('status')=='valid' else unit['status'] if unit['status']!='valid' else 'inference_incomplete'
                row = {'stage':stage,'mu':mu,'subset':subset,'training_seed':seed,'confidence_level':float(level),
                       'status':status,**{metric:coverage.get(metric) for metric in metrics},
                       'value_source':'paired_toy_descriptive_diagnostic',
                       'experimental_unit':'20_outer_calibration_replicas' if stage=='t2' else 'within_seed_crn_toy',
                       'outer_records':outer_values}
                rows.append(row); vector.append(row)
            for metric in metrics:
                valid = all(r['status']=='valid' and isinstance(r[metric],(int,float)) and math.isfinite(r[metric]) for r in vector)
                aggregates.append({'stage':stage,'mu':mu,'subset':subset,'confidence_level':float(level),'metric':metric,
                    'status':'valid' if valid else 'incomplete_seed_vector',
                    'median':float(median(r[metric] for r in vector)) if valid else None,
                    'per_seed':[{'seed':r['training_seed'],'status':r['status'],'value':r[metric]} for r in vector],
                    'scope':'descriptive_training_seed_stability_conditional_on_shared_MC',
                    'experimental_unit':'20_outer_calibration_replicas' if stage=='t2' else 'within_seed_crn_toy'})
    return rows, aggregates


def report(registration_path, nominal_path, protocol, output, allowed_root, *, freeze_path=None,
           result_path=None, evaluation_plan_path=None, evaluation_paths=(), j0_path=None, j1_path=None):
    """Missing blocks remain explicit; valid Asimov evidence survives Toy failures."""
    from higgsml.inference.report_exports import _write_csv
    registered, value, prepared, adapter, nominal_run, grid, bundles = load_nominal(registration_path, nominal_path, protocol)
    upstreams = [registered, adapter]
    summary, plan = None, None
    if freeze_path:
        *_, frozen_run, spec = load_frozen(registration_path, nominal_path, freeze_path, protocol)
        plan, result = _bound_plan(evaluation_plan_path, protocol, registered, prepared, adapter, frozen_run, spec, result_path)
        summary = result.read_json('summary.json')
        upstreams.extend([frozen_run, result])
    entries = {unit_name(u): {**u, 'status': 'not_run', 'value': None} for u in matrix()}
    for path in evaluation_paths:
        path = Path(path)
        if path.name not in entries:
            raise ResearchError('unregistered evaluation report unit')
        if entries[path.name]['status'] != 'not_run':
            raise ResearchError('duplicate evaluation report unit')
        unit = entries[path.name]
        if not path.exists():
            continue
        try:
            if unit['stage'] == 'mc-bootstrap':
                item = _load(path, protocol, 'mc-bootstrap')
                answer = item.read_json('evaluation.json')
                if answer['evaluation_plan_id'] != plan['evaluation_plan_id']:
                    raise ResearchError('bootstrap report binding mismatch')
                status = answer['status']
            else:
                from higgsml.inference.marginal_evaluation_state import SeedEvaluationBinding, read_seed_evaluation_terminal
                provisional = read_run(path, dataset=protocol['dataset'], protocol=protocol, stages=('marginal-block-evaluation',))
                answer = provisional.read_json('seed-evaluation.json')
                bound = answer['binding']
                bound['candidate_ids'] = tuple(bound['candidate_ids'])
                binding = SeedEvaluationBinding(**bound)
                if (binding.evaluation_plan_id != plan['evaluation_plan_id'] or binding.specification_id != plan['specification_id']
                        or (binding.stage, binding.mu, binding.training_seed) != (unit['stage'], unit['mu'], unit['training_seed'])):
                    raise ResearchError('seed report binding mismatch')
                item, answer = read_seed_evaluation_terminal(output_dir=path, claims_root=prepared.path.parents[1],
                    dataset=protocol['dataset'], protocol=protocol, binding=binding)
                status = answer['scientific_status']
            unit.update(status=status, value=answer)
            upstreams.append(item)
        except ResearchError as error:
            unit.update(status='invalid_or_consumed_output', reason=str(error))
    # A consumed but unpublished cell stays visible even when no output exists.
    claims = prepared.path.parents[1] / '.h4l-mass-off-v3-claims'
    if plan and claims.exists():
        for claim_path in claims.glob('cell-*.json'):
            claim = read_json(claim_path)
            binding = claim.get('binding', {})
            if binding.get('evaluation_plan_id') == plan['evaluation_plan_id']:
                matched = next((u for u in entries.values() if (u['stage'],u['mu'],u['training_seed']) ==
                    (binding.get('stage'),binding.get('mu'),binding.get('training_seed'))), None)
                if matched and matched['status'] == 'not_run':
                    matched['status'] = 'blocked_consumed_budget'
    rows = []
    candidate_rows = []
    for unit in entries.values():
        row = {k: v for k, v in unit.items() if k != 'value'}
        evaluated = unit['value'] or {}
        results = evaluated.get('candidate_results', [])
        row.update(planned_toys_per_candidate=evaluated.get('planned_toys_per_candidate'),
                   generated_physical_toys=evaluated.get('generated_physical_toys', 0),
                   attempted_fits=sum(r['attempted_fits'] for r in results),
                   completed_fits=sum(r['completed_fits'] for r in results),
                   valid_fits=sum(r['valid_fits'] for r in results))
        if unit['stage'] != 'mc-bootstrap':
            planned = 2000 if unit['stage'] == 't2' else 500
            row['planned_toys_per_candidate'] = planned
            by_key = {r['candidate_id']: r for r in results}
            block = next(b for b in canonical_seed_blocks() if b.seed == unit['training_seed'])
            for key in block.candidate_keys:
                candidate_rows.append({'stage': unit['stage'], 'mu': unit['mu'], 'training_seed': block.seed,
                    'value_source': 'paired_toy_diagnostic', 'planned_toys_per_candidate': planned,
                    **by_key.get(key, {'candidate_id':key,'status':unit['status'],
                        'attempted_fits':0,'completed_fits':0,'valid_fits':0})})
        rows.append(row)
    diagnostic_rows, diagnostic_aggregates = descriptive_seed_diagnostics(entries)
    layers = {}
    for stage in ('model-self', 'assessment', 't2'):
        for mu in ((1,) if stage == 't2' else (0, 1, 2)):
            selected = [r for r in rows if r['stage'] == stage and r['mu'] == mu]
            layers[f'{stage}-mu{mu}'] = {'status': 'valid' if all(r['status'] == 'valid' for r in selected)
                else 'incomplete_seed_vector', 'valid_seeds': sum(r['status'] == 'valid' for r in selected),
                'required_seeds': 5, 'aggregate': [r for r in diagnostic_aggregates if r['stage']==stage and r['mu']==mu],
                'value_source': 'paired_toy_descriptive_diagnostic'}
    supports = []
    for gate_path, gate_name in ((j0_path, 'J0'), (j1_path, 'J1')):
        if gate_path and Path(gate_path).exists():
            gate_run = _load(gate_path, protocol, 'support-' + gate_name.lower())
            gate = gate_run.read_json('marginal-support-summary.json')
            _validate_gate(gate, registered, adapter, protocol, gate_name)
            supports.append(gate)
            upstreams.append(gate_run)
    complete = plan is not None and summary and summary['status'] == 'valid' and all(r['status'] == 'valid' for r in rows)
    historical_other_freeze = any(
        h['claim'].get('binding',h['claim']).get('freeze_artifact_id') != (_id(frozen_run) if plan else None)
        for h in source_history(prepared))
    answer = {'schema_version': 'h4l-mass-off-report-v3', **METADATA, 'family_id': FAMILY,
        'aggregate_status': 'valid' if complete else 'incomplete', 'pairing_scope': 'within_seed', 'cross_seed_pairing': 'none',
        'nominal_asimov': summary, 'value_source': 'nominal_asimov', 'seed_layers': layers,
        'seed_descriptive_diagnostics':diagnostic_rows,'five_seed_descriptive_diagnostics':diagnostic_aggregates,
        'evaluation_units': entries, 'support': supports, 'evaluation_plan': plan,
        'qualification': value['qualification'], 'independent_validation': False,
        'identity_qualification': spec['support_qualification'] if plan else ('physical_process' if any(
            s.get('summary',s).get('identity_qualification')=='physical_process'
            for g in supports for s in g['seeds'].values()) else 'label_level_legacy'),
        'assessment_source_status': 'blocked_missing_eligible_assessment_source' if historical_other_freeze else 'pending_access_review',
        'seed_interval_scope': 'training_seed_stability_conditional_on_shared_MC_not_independence',
        'missing_semantics': 'missing seed never replaced; all 5 required; no cross-seed Toy-index pairing'}
    with ResearchRun(output, allowed_root=allowed_root, stage='attribution-v3-report', dataset=protocol['dataset'],
                     protocol=protocol, upstreams=upstreams) as run:
        for table in (rows,candidate_rows,diagnostic_rows,diagnostic_aggregates):
            for row in table:
                row.update(METADATA)
        run.write_json('report.json', answer)
        tables = {'seed_block_status.csv': rows, 'evaluation_completeness.csv': rows,
            'seed_descriptive_diagnostics.csv':diagnostic_rows,
            'five_seed_descriptive_diagnostics.csv':diagnostic_aggregates,
            'candidate_fit_status.csv': candidate_rows,
            'marginal_support.csv': [{'gate': gate['gate'], 'seed': seed, **record.get('summary', record)}
                                  for gate in supports for seed, record in gate['seeds'].items()]}
        if summary:
            for name, key in [('mass_off_feature_metrics.csv', 'records'), ('mass_off_feature_attribution.csv', 'contributions'),
                              ('mass_off_feature_interactions.csv', 'interactions'), ('mass_off_pairwise_comparisons.csv', 'pairwise_comparisons')]:
                tables[name] = [{**r, 'value_source': 'nominal_asimov'} for r in (summary.get(key) or [])]
        bootstrap = entries['mc-bootstrap-mu1']['value']
        if bootstrap:
            tables['mc_bootstrap_uncertainty.csv'] = [
                {'estimand':kind,'value_source':'mc_bootstrap_replica','status':bootstrap['status'],**record}
                for kind,records in bootstrap.get('uncertainty',{}).items() for record in records]
        dictionary = {}
        for name, table in tables.items():
            fields = list(dict.fromkeys(k for row in table for k in row)) or ['status']
            _write_csv(run, name, table, fields)
            dictionary[name] = {'fields': fields, 'rows': len(table), 'numeric_precision': 'full_float_serialization',
                                'missing': 'null or empty; never imputed', 'seed_aggregation': 'requires_5_of_5'}
        run.write_json('data_dictionary.json', dictionary)
        run.write_json('provenance.json', {'upstreams': run.manifest['upstreams'], 'plan': plan,
            'source_nominal_artifact_id': _id(nominal_run), 'source_history': source_history(prepared), 'budgets': BUDGETS})
        lines = ['# Within-seed MC-only evaluation', '', 'Aggregate status: ' + answer['aggregate_status'], '',
                 'Artificial marginal CRN coupling: physical_event_pairing=false. Paired errors are conditional diagnostics only; sensitivity is pending. Five seeds share MC. Independent validation remains pending.', '',
                 '| Stage | mu | Training seed | Scientific status |', '|---|---:|---:|---|']
        lines += [f"| {r['stage']} | {r['mu']} | {r['training_seed']} | {r['status']} |" for r in rows]
        (run.path / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        run.register_file('report.md')
    return legacy._result(run, output)
