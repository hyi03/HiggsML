import pytest

from higgsml.errors import ResearchError


def report():
    units = {'mc-bootstrap-mu1': {'stage': 'mc-bootstrap', 'mu': 1, 'training_seed': None,
                                'status': 'valid', 'value': {'status': 'valid'}}}
    for stage, mus in [('model-self', [0, 1, 2]), ('assessment', [0, 1, 2]), ('t2', [1])]:
        for mu in mus:
            for seed in [42, 43, 44, 45, 46]:
                units[f'{stage}-mu{mu}-seed{seed}'] = {
                    'stage': stage, 'mu': mu, 'training_seed': seed,
                    'status': 'valid', 'value': {'scientific_status': 'valid'}}
    return {'evaluation_units': units, 'aggregate_status': 'valid', 'nominal_asimov': {'status': 'valid'}}


def test_missing_unit_cannot_pass_complete_even_if_aggregate_says_valid():
    from higgsml.inference.run_readiness import execution_summary
    value = report()
    del value['evaluation_units']['t2-mu1-seed46']
    with pytest.raises(ResearchError, match='matrix'):
        execution_summary(value)


def test_all_terminal_failures_are_execution_complete_but_not_scientific_success():
    from higgsml.inference.run_readiness import execution_summary
    value = report()
    value['aggregate_status'] = 'incomplete'
    value['evaluation_units']['t2-mu1-seed46']['status'] = 'insufficient_statistics'
    summary = execution_summary(value)
    assert summary['execution_status'] == 'complete'
    assert summary['terminal_units'] == summary['planned_units'] == 36
    assert summary['valid_units'] == 35
    assert summary['scientific_status'] == 'incomplete'
    assert summary['scientific_qualification'] == 'unvalidated_exploratory_only'


def test_consumed_unpublished_unit_is_incomplete():
    from higgsml.inference.run_readiness import execution_summary
    value = report()
    value['evaluation_units']['t2-mu1-seed46'].update(status='blocked_consumed_budget', value=None)
    summary = execution_summary(value)
    assert summary['execution_status'] == 'incomplete'
    assert summary['terminal_units'] == 35


def test_foreign_unit_identity_is_rejected():
    from higgsml.inference.run_readiness import execution_summary
    value = report()
    value['evaluation_units']['t2-mu1-seed46']['training_seed'] = 42
    with pytest.raises(ResearchError, match='identity'):
        execution_summary(value)


def completion_fixture(tmp_path, monkeypatch):
    """Real sealed files; scientific plan construction is tested in marginal_workflow."""
    from higgsml.artifacts import digest_json
    from higgsml._manifest import canonical_json_bytes
    from higgsml.inference import marginal_workflow
    import hashlib
    protocol = {'dataset': 'synthetic'}
    monkeypatch.setattr(marginal_workflow, 'validate_plan', lambda *args: None)

    def artifact(path, stage, files, upstreams=()):
        path.mkdir(parents=True)
        if stage == 'attribution-v3-report':
            files = {'report.md': 'synthetic report', **files}
        receipts = {}
        for name, value in {'protocol.json': protocol, **files}.items():
            data = canonical_json_bytes(value)
            (path / name).write_bytes(data)
            receipts[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'size_bytes': len(data)}
        manifest = {'schema_version': 'research-run-v1', 'stage': stage,
                    'status': 'complete', 'dataset': 'synthetic', 'protocol_sha256': digest_json(protocol),
                    'files': receipts, 'upstreams': [{'artifact_id': x} for x in upstreams]}
        manifest['artifact_id'] = digest_json(manifest)
        (path / 'manifest.json').write_bytes(canonical_json_bytes(manifest))
        return manifest['artifact_id']

    freeze = artifact(tmp_path / 'freeze', 'attribution-v3-freeze', {})
    plan = {'inputs': {'freeze_artifact_id': freeze}, 'evaluation_plan_id': 'plan', 'specification_id': 'spec'}
    artifact(tmp_path / 'evaluation-plan', 'attribution-v3-evaluation-plan', {'evaluation-plan.json': plan})
    value = report()
    value['evaluation_plan'] = plan
    ids = [freeze]
    for name, entry in value['evaluation_units'].items():
        if entry['stage'] == 'mc-bootstrap':
            filename, stage = 'evaluation.json', 'attribution-v3-mc-bootstrap'
            payload = {'evaluation_plan_id': 'plan', 'status': 'valid'}
        else:
            filename, stage = 'seed-evaluation.json', 'marginal-block-evaluation'
            payload = {'binding': {'evaluation_plan_id': 'plan', 'specification_id': 'spec',
                'freeze_artifact_id': freeze, **{k: entry[k] for k in ('stage', 'mu', 'training_seed')}},
                'scientific_status': 'valid'}
        entry['value'] = payload
        # Identity includes a unique path marker like actual unit-specific payloads.
        ids.append(artifact(tmp_path / 'evaluation' / name, stage, {filename: payload}))
    return protocol, value, ids, artifact


def test_completion_uses_current_resume_report_not_stale_original(tmp_path, monkeypatch):
    from copy import deepcopy
    from higgsml.inference.run_readiness import verify_completion
    protocol, value, ids, artifact = completion_fixture(tmp_path, monkeypatch)
    stale = deepcopy(value)
    stale['evaluation_units']['t2-mu1-seed46']['value'] = None
    artifact(tmp_path / 'evaluation/report', 'attribution-v3-report', {'report.json': stale}, ids[:-1])
    artifact(tmp_path / 'evaluation/report-resume-current', 'attribution-v3-report', {'report.json': value}, ids)
    result = verify_completion(tmp_path, protocol)
    assert result['execution_status'] == 'complete'
    assert result['report_path'].endswith('report-resume-current\\report.md') or result['report_path'].endswith('report-resume-current/report.md')


def test_completion_rejects_modified_terminal_payload(tmp_path, monkeypatch):
    from higgsml.inference.run_readiness import verify_completion
    protocol, value, ids, artifact = completion_fixture(tmp_path, monkeypatch)
    artifact(tmp_path / 'evaluation/report', 'attribution-v3-report', {'report.json': value}, ids)
    (tmp_path / 'evaluation/t2-mu1-seed46/seed-evaluation.json').write_text('{}')
    with pytest.raises(ResearchError, match='digest'):
        verify_completion(tmp_path, protocol)


def test_completion_rejects_report_value_not_matching_bound_terminal(tmp_path, monkeypatch):
    from higgsml.inference.run_readiness import verify_completion
    protocol, value, ids, artifact = completion_fixture(tmp_path, monkeypatch)
    value['evaluation_units']['t2-mu1-seed46']['value']['invented'] = True
    artifact(tmp_path / 'evaluation/report', 'attribution-v3-report', {'report.json': value}, ids)
    with pytest.raises(ResearchError, match='terminal'):
        verify_completion(tmp_path, protocol)


def test_completion_rejects_missing_readable_report(tmp_path, monkeypatch):
    from higgsml.inference.run_readiness import verify_completion
    protocol, value, ids, artifact = completion_fixture(tmp_path, monkeypatch)
    artifact(tmp_path / 'evaluation/report', 'attribution-v3-report', {'report.json': value}, ids)
    (tmp_path / 'evaluation/report/report.md').unlink()
    with pytest.raises(ResearchError, match='report.md'):
        verify_completion(tmp_path, protocol)


def test_stage_b_verifies_bound_plan_inputs_and_report(tmp_path, monkeypatch):
    from higgsml.inference.run_readiness import verify_stage_b
    protocol, _, _, artifact = completion_fixture(tmp_path / 'fixture', monkeypatch)
    inputs = {}
    for name, key in [('register', 'registration_artifact_id'), ('nominal', 'template_artifact_id'),
                      ('freeze', 'freeze_artifact_id'), ('asimov', 'asimov_artifact_id')]:
        inputs[key] = artifact(tmp_path / name, 'attribution-v3-' + name, {})
    plan = {'inputs': inputs}
    artifact(tmp_path / 'evaluation-plan', 'attribution-v3-evaluation-plan', {'evaluation-plan.json': plan})
    artifact(tmp_path / 'report-B', 'attribution-v3-report',
             {'report.json': {'evaluation_plan': plan, 'nominal_asimov': {'status': 'valid'}}})
    assert verify_stage_b(tmp_path, protocol)['execution_status'] == 'stage_b_complete'
    (tmp_path / 'report-B/report.md').write_text('modified')
    with pytest.raises(ResearchError, match='digest'):
        verify_stage_b(tmp_path, protocol)
