"""Synthetic aggregate fixtures: no events, fits or physics validation."""
import csv
import importlib.util
import io
import itertools
import json
from pathlib import Path

import pytest

from higgsml.artifacts import digest_json
from higgsml._manifest import canonical_json_bytes


def collector():
    path = Path(__file__).resolve().parents[2] / 'paper/scripts/collect_evidence.py'
    spec = importlib.util.spec_from_file_location('paper_collector', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def publish(path, stage, payloads, upstreams=()):
    import hashlib
    path.mkdir(parents=True)
    manifest = {'schema_version': 'research-run-v1', 'stage': stage,
                'status': 'complete', 'dataset': 'atlas2020_4lep',
                'protocol_sha256': digest_json({'luminosity_pb': 10000}),
                'software': {'git_commit': stage}, 'files': {}, 'upstreams': list(upstreams)}
    payloads = {'protocol.json': {'luminosity_pb': 10000}, **payloads}
    for name, value in payloads.items():
        raw = value.encode() if isinstance(value, str) else canonical_json_bytes(value)
        (path / name).write_bytes(raw)
        manifest['files'][name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw)}
    manifest['artifact_id'] = digest_json(manifest)
    (path / 'manifest.json').write_bytes(canonical_json_bytes(manifest))
    return {'artifact_id': manifest['artifact_id'], 'path': str(path), 'stage': stage}


def csv_text(rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0]))
    writer.writeheader(); writer.writerows(rows)
    return out.getvalue()


def fixture_report(tmp_path, *, bootstrap=None, independent=None):
    subsets = [''.join(s) for n in range(5) for s in itertools.combinations('ABCD', n)]
    prep = publish(tmp_path / 'named-prepare', 'prepare', {'audit.json': {'status': 'passed'}})
    reg = publish(tmp_path / 'register', 'attribution-v3-register', {}, [prep])
    nominal = publish(tmp_path / 'nominal', 'attribution-v3-nominal', {}, [reg, prep])
    freeze = publish(tmp_path / 'freeze', 'attribution-v3-freeze', {'freeze.json': {
        'mass_edges': [105, 140], 'prepared_artifact_id': prep['artifact_id'],
        'registration_artifact_id': reg['artifact_id'], 'template_artifact_id': nominal['artifact_id'],
        'protocol_sha256': digest_json({'luminosity_pb': 10000})}}, [reg, nominal])
    rows, inference = [], {}
    for seed in range(42, 47):
        for subset in subsets:
            key = f'M3:{seed}:groups={subset}:m4l=off'
            width = 2 - .1 * len(subset)
            rows.append(dict(seed=seed, subset=subset, candidate_key=key, width68=width,
                             status='valid', value_source='nominal_asimov', auc=.6 if subset else '',
                             auc_role='validation', auc_measure='absolute_physical_weight',
                             model_id=key, auc_model_id=key, cohort_id=nominal['artifact_id'], family_id='family'))
            inference[key] = {'layer': 'T1', 'model_spec': {}, 'results': [{'mu': 1, 'intervals': [{'confidence': .68, 'width': width}]}]}
    asimov = publish(tmp_path / 'asimov', 'attribution-v3-asimov', {
        'inference.json': inference, 'summary.json': {'auc_width_relationship': {}}}, [reg, nominal, freeze])
    interactions = []
    for pair in itertools.combinations('ABCD', 2):
        for subset in subsets:
            if not set(pair) & set(subset):
                interactions.append(dict(pair=json.dumps(pair), conditioning_subset=subset, per_seed=json.dumps([0]*5), median=0))
    pairs = []
    for left, right in itertools.combinations(subsets[1:], 2):
        a, b = 2-.1*len(left), 2-.1*len(right)
        pairs.append(dict(left=left, right=right,
            delta_width68_left_minus_right=json.dumps({'median': a-b, 'per_seed': [a-b]*5}),
            relative_improvement_left_vs_right=json.dumps({'median': 1-a/b, 'per_seed': [1-a/b]*5})))
    upstreams = [reg, nominal, freeze, asimov]
    payloads = {
        'mass_off_feature_metrics.csv': csv_text(rows),
        'mass_off_feature_attribution.csv': csv_text([dict(group=g, median=.1, per_seed=json.dumps([.1]*5)) for g in 'ABCD']),
        'mass_off_feature_interactions.csv': csv_text(interactions),
        'mass_off_pairwise_comparisons.csv': csv_text(pairs),
        'evaluation_completeness.csv': csv_text([dict(stage='mc-bootstrap', status=bootstrap or 'not_run')]),
        'five_seed_descriptive_diagnostics.csv': csv_text([dict(status='not_run')]),
        'report.json': {'aggregate_status': 'incomplete', 'primary_claim_eligible': False, 'qualification': {}},
    }
    if bootstrap:
        upstreams.append(publish(tmp_path/'bootstrap', 'attribution-v3-mc-bootstrap', {
            'evaluation.json': {'status': bootstrap, 'planned_replicas': 200, 'valid_replicas': 200 if bootstrap=='valid' else 161}}, [freeze]))
        payloads['mc_bootstrap_uncertainty.csv'] = csv_text([dict(interval68='[1,2]' if bootstrap=='valid' else '', interval95='[0,3]' if bootstrap=='valid' else '')])
    if independent is not None:
        upstreams.append(publish(tmp_path/'access', 'attribution-v3-access-review', {
            'validated-off-assessment-access.json': {'independent': independent, 'freeze_artifact_id': freeze['artifact_id']}}, [freeze]))
    publish(tmp_path/'report', 'attribution-v3-report', payloads, upstreams)
    return tmp_path/'report'


@pytest.mark.parametrize('bootstrap,independent', [(None,None), ('bootstrap_incomplete',False), ('valid',True)])
def test_report_export_uses_bound_named_prepare_and_real_states(tmp_path, bootstrap, independent):
    report = fixture_report(tmp_path, bootstrap=bootstrap, independent=independent)
    snapshot, provenance = collector().collect(report)
    assert len(snapshot['records']) == 80
    assert snapshot['bootstrap']['status'] == (bootstrap or 'not_run')
    assert snapshot['access_independent'] is independent
    assert bool(snapshot['bootstrap_intervals']) == bool(bootstrap)
    assert snapshot['qualification']['confirmatory_eligibility'] is False
    assert provenance['execution_revisions']['report'] == 'attribution-v3-report'
    assert provenance['execution_revisions']['asimov'] == 'attribution-v3-asimov'


def test_report_export_rejects_missing_or_changed_bound_inputs(tmp_path):
    report = fixture_report(tmp_path)
    (tmp_path/'named-prepare/audit.json').write_text('{}')
    with pytest.raises(ValueError, match='mismatch'):
        collector().collect(report)
    (tmp_path/'named-prepare/audit.json').unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        collector().collect(report)


def test_report_export_relocates_without_rewriting_manifests(tmp_path):
    report = fixture_report(tmp_path/'original')
    raw = (report/'manifest.json').read_bytes()
    archived = tmp_path/'archive'
    (tmp_path/'original').rename(archived)
    snapshot, provenance = collector().collect(archived/'report', path_maps=[(tmp_path/'original', archived)])
    assert snapshot['prepared_audit']['status'] == 'passed'
    assert (archived/'report/manifest.json').read_bytes() == raw
    assert provenance['path_maps']


def test_report_export_rejects_upstream_identity_substitution(tmp_path):
    report = fixture_report(tmp_path)
    path = tmp_path/'freeze/manifest.json'
    manifest = json.loads(path.read_text())
    manifest['software']['git_commit'] = 'replacement'
    manifest.pop('artifact_id'); manifest['artifact_id'] = digest_json(manifest)
    path.write_bytes(canonical_json_bytes(manifest))
    with pytest.raises(ValueError, match='identity'):
        collector().collect(report)


def test_explicit_archived_access_is_bound_to_selected_freeze(tmp_path):
    report = fixture_report(tmp_path)
    freeze = json.loads((tmp_path/'freeze/manifest.json').read_text())
    ref = {'path': str(tmp_path/'freeze'), 'stage': freeze['stage'], 'artifact_id': freeze['artifact_id']}
    access = publish(tmp_path/'separate-access', 'attribution-v3-access-review', {
        'validated-off-assessment-access.json': {'independent': False}}, [ref])
    data, _ = collector().collect(report, access_review=access)
    assert data['access_independent'] is False
    access['artifact_id'] = '0'*64
    with pytest.raises(ValueError, match='identity'):
        collector().collect(report, access_review=access)


def test_selected_snapshot_rejects_changed_data_or_provenance(tmp_path):
    import hashlib
    spec = importlib.util.spec_from_file_location('paper_snapshot',
        Path(__file__).resolve().parents[2]/'paper/scripts/paper_snapshot.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    raw = b'{"report_artifact_id":"chosen","records":[]}'
    digest = hashlib.sha256(raw).hexdigest()
    provenance = json.dumps({'report_artifact_id':'chosen','snapshot_sha256':digest}).encode()
    selected = {'report_artifact_id':'chosen','snapshot_sha256':digest,
                'provenance_sha256':hashlib.sha256(provenance).hexdigest()}
    (tmp_path/'results.json').write_bytes(raw)
    (tmp_path/'provenance.json').write_bytes(provenance)
    (tmp_path/'selected.json').write_text(json.dumps(selected))
    assert module.load_snapshot(tmp_path, selection=tmp_path/'selected.json')['records'] == []
    (tmp_path/'results.json').write_bytes(raw+b' ')
    with pytest.raises(ValueError, match='hash mismatch'):
        module.load_snapshot(tmp_path, selection=tmp_path/'selected.json')
    with pytest.raises(ValueError, match='hash mismatch'):
        module.load_snapshot(tmp_path, selection=tmp_path/'selected.json', refreshed=True)
    (tmp_path/'results.json').write_bytes(raw)
    (tmp_path/'provenance.json').write_bytes(provenance+b' ')
    with pytest.raises(ValueError, match='hash mismatch'):
        module.load_snapshot(tmp_path, selection=tmp_path/'selected.json')
    assert module.load_snapshot(tmp_path, selection=tmp_path/'selected.json', refreshed=True)['records'] == []


def reseal(path, filename, value):
    import hashlib
    manifest = json.loads((path/'manifest.json').read_text())
    raw = value.encode() if isinstance(value, str) else canonical_json_bytes(value)
    (path/filename).write_bytes(raw)
    manifest['files'][filename] = {'sha256':hashlib.sha256(raw).hexdigest(),'size_bytes':len(raw)}
    manifest.pop('artifact_id'); manifest['artifact_id'] = digest_json(manifest)
    (path/'manifest.json').write_bytes(canonical_json_bytes(manifest))


def test_export_preserves_failed_unpublished_bootstrap_without_inventing_intervals(tmp_path):
    report = fixture_report(tmp_path)
    reseal(report, 'evaluation_completeness.csv', csv_text([{'stage':'mc-bootstrap','status':'invalid_or_consumed_output'}]))
    snapshot, _ = collector().collect(report)
    assert snapshot['bootstrap']['status'] == 'invalid_or_consumed_output'
    assert snapshot['bootstrap_intervals'] == []


def test_export_rejects_protocol_content_inconsistent_with_sealed_digest(tmp_path):
    report = fixture_report(tmp_path)
    reseal(report, 'protocol.json', {'luminosity_pb':20000})
    with pytest.raises(ValueError, match='[Pp]rotocol'):
        collector().collect(report)
