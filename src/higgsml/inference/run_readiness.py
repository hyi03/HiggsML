"""Read-only orchestration checks, separate from scientific qualification."""
from pathlib import Path

from higgsml.artifacts import digest_json, read_json, read_run
from higgsml.errors import ResearchError
from higgsml.inference.population_history import audit_population_history, _safe_path


def metadata_manifest(path, *, stage, protocol):
    """Validate a manifest seal without hashing/decoding its scientific files."""
    path = Path(path)
    _safe_path(path)
    value = read_json(path / 'manifest.json')
    if (not isinstance(value, dict) or value.get('artifact_id') != digest_json(
            {k: v for k, v in value.items() if k != 'artifact_id'})
            or value.get('stage') != stage or value.get('status') != 'complete'
            or value.get('dataset') != protocol['dataset']
            or value.get('protocol_sha256') != digest_json(protocol)):
        raise ResearchError(f'invalid preflight manifest binding: {path}')
    return value


def preflight(runs_root, name, method, protocol):
    root = Path(runs_root)
    prepared = root / f'h4l-prepare-{name}' / 'prepare'
    off = root / f'h4l-off-{name}'
    registered = off / 'register/registration.json'
    if registered.exists():
        _safe_path(registered)
        if read_json(registered).get('threshold_method', 'median-v1') != method:
            raise ResearchError('threshold method conflicts with existing registration')
    manifest = (metadata_manifest(prepared, stage='prepare', protocol=protocol)
                if (prepared / 'manifest.json').exists() else None)
    if manifest is not None and not manifest.get('population_id'):
        raise ResearchError('prepared manifest has no population identity')
    frozen = (metadata_manifest(off / 'freeze', stage='attribution-v3-freeze', protocol=protocol)
              if (off / 'freeze/manifest.json').exists() else None)
    history = audit_population_history(root,
        population_id=manifest['population_id'] if manifest else None,
        prepared_id=manifest['artifact_id'] if manifest else None)
    blockers = []
    access = 'pending_prepare_identity'
    if manifest:
        access = 'no_access_found_in_declared_roots'
        if history['matches']:
            freeze_id = frozen['artifact_id'] if frozen else None
            conflict = any(not freeze_id or item['claim'].get('binding', item['claim']).get(
                'freeze_artifact_id') != freeze_id for item in history['matches'])
            if conflict:
                access = 'blocked_used_population'
                blockers.append('population has prior access under another or unknown freeze')
            else:
                access = 'same_freeze_resume_requires_bound_access_review'
    return {'threshold_method': method, 'access_status': access, 'access_blockers': blockers,
            'prepared_artifact_id': manifest['artifact_id'] if manifest else None,
            'population_id': manifest['population_id'] if manifest else None,
            'freeze_artifact_id': frozen['artifact_id'] if frozen else None,
            'history_audit': history, 'protocol_sha256': digest_json(protocol),
            'scientific_qualification': 'unvalidated_exploratory_only',
            'weight_definition': 'existing_mcWeight_effective_xsec_no_new_scale_factors',
            'interval_definition': 'existing_asymptotic_T0_T1_not_independently_validated',
            'reuse': 'existing directories require child-stage binding validation',
            'event_payloads_read': False}


def execution_summary(report):
    from higgsml.inference.marginal_workflow import matrix, unit_name
    expected = {unit_name(unit): unit for unit in matrix()}
    entries = report.get('evaluation_units')
    if not isinstance(entries, dict) or set(entries) != set(expected):
        raise ResearchError('report does not contain the complete registered matrix')
    terminal = valid = 0
    for name, unit in expected.items():
        entry = entries[name]
        if not isinstance(entry, dict) or any(entry.get(k) != v for k, v in unit.items()):
            raise ResearchError('report unit identity mismatch: ' + name)
        done = entry.get('value') is not None and entry.get('status') not in {
            None, 'not_run', 'invalid_or_consumed_output', 'blocked_consumed_budget'}
        terminal += int(done)
        valid += int(done and entry['status'] == 'valid')
    complete = terminal == len(expected) and report.get('nominal_asimov') is not None
    return {'execution_status': 'complete' if complete else 'incomplete',
            'planned_units': len(expected), 'terminal_units': terminal, 'valid_units': valid,
            'scientific_status': 'valid' if complete and valid == len(expected)
                and report.get('aggregate_status') == 'valid' else 'incomplete',
            'scientific_qualification': 'unvalidated_exploratory_only'}


def verify_completion(off_root, protocol):
    """Find a verified report bound to current terminal IDs, including resume snapshots."""
    from higgsml.inference.marginal_workflow import matrix, unit_name, validate_plan
    off = Path(off_root)
    plan_run = read_run(off / 'evaluation-plan', dataset=protocol['dataset'], protocol=protocol,
                        stages=('attribution-v3-evaluation-plan',))
    plan = plan_run.read_json('evaluation-plan.json')
    validate_plan(plan, protocol)
    frozen = metadata_manifest(off / 'freeze', stage='attribution-v3-freeze', protocol=protocol)
    if plan['inputs']['freeze_artifact_id'] != frozen['artifact_id']:
        raise ResearchError('completion plan/freeze mismatch')
    evaluation = off / 'evaluation'
    current_ids = set()
    terminals = {}
    for unit in matrix():
        path = evaluation / unit_name(unit)
        stage = 'attribution-v3-mc-bootstrap' if unit['stage'] == 'mc-bootstrap' else 'marginal-block-evaluation'
        item = read_run(path, dataset=protocol['dataset'], protocol=protocol, stages=(stage,))
        filename = 'evaluation.json' if unit['stage'] == 'mc-bootstrap' else 'seed-evaluation.json'
        terminal = item.read_json(filename)
        binding = terminal if unit['stage'] == 'mc-bootstrap' else terminal.get('binding', {})
        if binding.get('evaluation_plan_id') != plan['evaluation_plan_id']:
            raise ResearchError('terminal belongs to a different evaluation plan')
        if unit['stage'] != 'mc-bootstrap' and (
                binding.get('specification_id') != plan['specification_id']
                or binding.get('freeze_artifact_id') != frozen['artifact_id']
                or any(binding.get(k) != v for k, v in unit.items())):
            raise ResearchError('terminal identity differs from the registered matrix')
        terminals[unit_name(unit)] = terminal
        current_ids.add(item.manifest['artifact_id'])
    candidates = [evaluation / 'report', *sorted(evaluation.glob('report-resume-*'))]
    problems = []
    for path in candidates:
        if not path.is_dir():
            continue
        try:
            item = read_run(path, dataset=protocol['dataset'], protocol=protocol,
                            stages=('attribution-v3-report',))
            value = item.read_json('report.json')
            if value.get('evaluation_plan') != plan:
                raise ResearchError('report belongs to a different evaluation plan')
            upstream_ids = {u['artifact_id'] for u in item.manifest['upstreams']}
            if not current_ids.issubset(upstream_ids) or frozen['artifact_id'] not in upstream_ids:
                raise ResearchError('report does not bind current terminal artifacts')
            summary = execution_summary(value)
            if any(value['evaluation_units'][name]['value'] != terminal
                   or value['evaluation_units'][name]['status'] != terminal.get(
                       'scientific_status', terminal.get('status'))
                   for name, terminal in terminals.items()):
                raise ResearchError('report value differs from bound terminal')
            if summary['execution_status'] != 'complete':
                raise ResearchError('report has incomplete execution')
            item.file('report.md')
            return {**summary, 'report_path': str(path / 'report.md')}
        except ResearchError as error:
            problems.append(str(error))
    raise ResearchError('no complete current report: ' + '; '.join(problems))


def verify_stage_b(off_root, protocol):
    from higgsml.inference.marginal_workflow import validate_plan
    off = Path(off_root)
    plan_run = read_run(off / 'evaluation-plan', dataset=protocol['dataset'], protocol=protocol,
                        stages=('attribution-v3-evaluation-plan',))
    plan = plan_run.read_json('evaluation-plan.json')
    validate_plan(plan, protocol)
    for directory, key, stage in [('register', 'registration_artifact_id', 'register'),
                                  ('nominal', 'template_artifact_id', 'nominal'),
                                  ('freeze', 'freeze_artifact_id', 'freeze'),
                                  ('asimov', 'asimov_artifact_id', 'asimov')]:
        manifest = metadata_manifest(off / directory, stage='attribution-v3-' + stage, protocol=protocol)
        if manifest['artifact_id'] != plan['inputs'][key]:
            raise ResearchError('Stage B plan/input identity mismatch: ' + directory)
    report = read_run(off / 'report-B', dataset=protocol['dataset'], protocol=protocol,
                      stages=('attribution-v3-report',))
    value = report.read_json('report.json')
    if value.get('evaluation_plan') != plan or value.get('nominal_asimov') is None:
        raise ResearchError('Stage B report is not bound to the completed plan')
    report.file('report.md')
    return {'execution_status': 'stage_b_complete', 'evaluation_started': False,
            'report_path': str(off / 'report-B/report.md'),
            'scientific_qualification': 'unvalidated_exploratory_only'}
