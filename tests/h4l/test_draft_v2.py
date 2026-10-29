"""Synthetic software checks only; no controlled-MC payload or scientific runs."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd
import pytest
import torch

from higgsml.artifacts import digest_json, read_json
from higgsml.cli_draft_v2 import main, plan
from higgsml.data import assign_roles as old_assign_roles
from higgsml.draft_v2 import data, training, workflow
from higgsml.draft_v2.protocol import DEFAULT_PROTOCOL, CANDIDATES, SEEDS, candidate_keys, load_protocol, validate_protocol
from higgsml.draft_v2.reporting import mass_spectra, summarize
from higgsml.errors import ResearchError
from higgsml.inference.likelihood import build_model, profile_interval
from higgsml.inference.templates import build_templates
from higgsml.modeling.discriminants import predict_discriminant
from higgsml.modeling.representations import ENGINEERED19
from higgsml.protocol import load_protocol as old_protocol


def synthetic_frame(size=1200):
    rng = np.random.default_rng(812)
    frame = pd.DataFrame(rng.normal(size=(size, len(ENGINEERED19))), columns=ENGINEERED19)
    frame['event_id'] = [f'synthetic-row:{i}' for i in range(size)]
    frame['source_row_id'] = frame.event_id
    frame['event_group_id'] = [f'synthetic-group:{i}' for i in range(size)]
    frame['split'], frame['dataset'] = 'exploratory', 'atlas2020_4lep'
    frame['label'] = np.arange(size) % 2
    frame['physical_weight'] = np.where(frame.label == 1, .04, .08)
    frame.loc[np.arange(size) % 31 == 0, 'physical_weight'] *= -.1
    frame['m4l'] = rng.uniform(105, 140, size)
    return frame


@pytest.fixture(scope='module')
def protocol():
    return load_protocol(DEFAULT_PROTOCOL)


@pytest.fixture(scope='module')
def frozen_base(tmp_path_factory, protocol):
    base = tmp_path_factory.mktemp('draft-v2-synthetic')
    source = base / 'synthetic.json'
    source.write_text(json.dumps(dict(schema_version='h4l-draft-v2-synthetic-v1', dataset=protocol['dataset'],
        source_kind='synthetic', events=synthetic_frame().to_dict('records'))), encoding='utf-8')
    root = base / 'study'
    prepared = workflow.prepare(root, protocol, synthetic_events=source)
    threads = torch.get_num_threads()
    try:
        torch.set_num_threads(1)
        trained = workflow.train(root, protocol)
    finally:
        torch.set_num_threads(threads)
    assert len(trained) == 15
    frozen = workflow.freeze(root, protocol)
    pending = frozen.read_json('access-review.pending.json')
    review = {**pending, 'status': 'approved', 'decision': 'allow_exploratory_reuse',
              'reviewed_by': 'synthetic-test-fixture-only', 'reviewed_at': 'synthetic-test'}
    review_path = base / 'synthetic-review.json'
    review_path.write_text(json.dumps(review), encoding='utf-8')
    return root, source, review_path, prepared, frozen


@pytest.fixture
def frozen_study(frozen_base, tmp_path, protocol):
    original, source, _, _, _ = frozen_base
    root = tmp_path / 'study'
    shutil.copytree(original, root)
    prepared, metadata = workflow._prepared(root, protocol)
    frozen = workflow._load(root, 'freeze', protocol)
    review = workflow.access_template(root, protocol, prepared, metadata, frozen.read_json('freeze.json'))
    review.update(status='approved', decision='allow_exploratory_reuse',
                  reviewed_by='synthetic-test-fixture-only', reviewed_at='synthetic-test')
    review_path = tmp_path / 'synthetic-review.json'
    review_path.write_text(json.dumps(review), encoding='utf-8')
    return root, source, review_path, prepared, frozen


def test_protocol_rejects_shortcuts_and_legacy(protocol):
    for key, value in [('seeds', [42]), ('source_population', 'development'),
                       ('roles', {'train': .5, 'validation': .2, 'evaluation': .3}),
                       ('mass_input', 'on')]:
        changed = {**protocol, key: value}
        with pytest.raises(ResearchError):
            validate_protocol(changed)
    changed = deepcopy(protocol)
    changed['training']['max_epochs'] = 2
    with pytest.raises(ResearchError):
        validate_protocol(changed)
    with pytest.raises(ResearchError):
        validate_protocol(old_protocol().to_dict())


def test_three_roles_group_identity_and_normalization(protocol):
    raw = synthetic_frame()
    repeated = raw.iloc[[0]].copy()
    repeated['event_id'], repeated['source_row_id'] = 'another-row', 'another-row'
    frame = data.assign_roles(pd.concat([raw, repeated], ignore_index=True), protocol)
    shuffled = data.assign_roles(raw.sample(frac=1), protocol)
    assert shuffled.set_index('event_id').role.to_dict() == frame.iloc[:-1].set_index('event_id').role.to_dict()
    assert frame.groupby('event_group_id').role.nunique().max() == 1
    assert set(frame.role) == {'train', 'validation', 'evaluation'}
    assert np.allclose(frame.loc[frame.role == 'evaluation'].yield_weight,
                       frame.loc[frame.role == 'evaluation'].physical_weight / .2)
    with pytest.raises(ResearchError, match='unassigned'):
        data.assign_roles(frame, protocol)
    with pytest.raises(ResearchError):
        old_assign_roles(raw, old_protocol())


def test_learner_refuses_wrong_source_and_cross_role_groups(protocol):
    frame = data.assign_roles(synthetic_frame(), protocol)
    frame = frame.loc[frame.role.isin(['train', 'validation'])].copy()
    frame.attrs['source_kind'] = 'synthetic'
    wrong = frame.copy()
    wrong['dataset'] = 'atlas2025_exactly4lep'
    with pytest.raises(ResearchError, match='provenance'):
        training.train(wrong, protocol, 'ABCD', 42, 'a'*64)
    duplicate = frame.iloc[[0]].copy()
    duplicate['role'] = 'validation' if duplicate.role.iloc[0] == 'train' else 'train'
    crossed = pd.concat([frame, duplicate], ignore_index=True)
    crossed.attrs['source_kind'] = 'synthetic'
    with pytest.raises(ResearchError, match='crosses roles'):
        training.train(crossed, protocol, 'ABCD', 42, 'a'*64)


def test_identity_first_poison_and_freeze_guard(tmp_path, protocol):
    frame = data.assign_roles(synthetic_frame(), protocol)
    frame.attrs['source_kind'] = 'synthetic'
    path = tmp_path / 'events.jsonl'
    data.write_events(frame, path, protocol)
    lines = path.read_text().splitlines()
    for i in range(1, len(lines)):
        envelope, payload = lines[i].split('\t', 1)
        if json.loads(envelope)['role'] == 'evaluation':
            lines[i] = envelope + '\tTHIS MUST NEVER BE JSON DECODED BEFORE FREEZE'
    path.write_text('\n'.join(lines) + '\n')
    assert set(data.read_events(path, protocol).role) == {'train', 'validation'}
    with pytest.raises(ResearchError, match='freeze'):
        data.read_events(path, protocol, evaluation=True)
    for i in range(1, len(lines)):
        envelope, payload = lines[i].split('\t', 1)
        identity = json.loads(envelope)
        if identity['role'] == 'evaluation':
            identity['role'] = 'train'
            lines[i] = json.dumps(identity) + '\t' + payload
            break
    path.write_text('\n'.join(lines) + '\n')
    with pytest.raises(ResearchError, match='before payload'):
        data.read_events(path, protocol)


@pytest.mark.parametrize('scores,weights,expected', [([.1, .2, .9], [1, 2, 1], .2),
    ([.1, .1, .9], [1, 1, 2], .1), ([.1, .2, .9], [0, 1, 1], .2), ([.4, .4], [1, 1], .4)])
def test_empirical_median_ties(scores, weights, expected):
    assert training.weighted_median(scores, weights) == expected


@pytest.mark.parametrize('scores,weights', [([], []), ([.1], [0]), ([.1], [-1]),
    ([np.nan], [1]), ([.1], [np.inf]), ([2.], [1]), ([.1, .2], [1])])
def test_invalid_median(scores, weights):
    with pytest.raises(ResearchError):
        training.weighted_median(scores, weights)


def test_training_dimensions_scaler_auc_and_frozen_threshold(frozen_study, protocol):
    root, source, review, prepared, frozen = frozen_study
    frame = data.read_events(prepared.file('events.jsonl'), protocol)
    fitting, valid = frame.loc[frame.role == 'train'], frame.loc[frame.role == 'validation']
    for subset, dimension in zip(CANDIDATES, [19, 11, 15, 17, 14]):
        loaded = workflow._load(root, 'train', protocol, name=f'train/{subset}-42')
        model = loaded.read_json('model.json')
        assert model['architecture'] == [dimension, 64, 64, 32, 1]
        assert 'm4l' not in model['ordered_inputs']
        assert np.allclose(model['scaler']['mean'], fitting[model['ordered_inputs']].mean())
        assert model['scaler']['source_role'] == 'train'
        selected = model['history'][model['selected_epoch'] - 1]
        assert model['validation_absolute_weight_auc'] == selected['validation_absolute_weight_auc']
        background = valid.loc[valid.label == 0]
        scores = training.predict(model, background, protocol)
        # CPU float32 GEMM can differ in its last bits with a different batch
        # shape/thread count. This is a numerical replay tolerance, not a cut.
        assert model['threshold'] == pytest.approx(
            training.weighted_median(scores, np.abs(background.physical_weight)), abs=1e-6)
        # Old APIs still reject the new model family instead of accepting it
        # through a broadly relaxed public role check.
        with pytest.raises(ResearchError, match='schema'):
            predict_discriminant(model, valid)
    assert len(frozen.read_json('freeze.json')['models']) == 15


def test_shortened_model_history_cannot_be_promoted(frozen_study, protocol):
    root, _, _, _, _ = frozen_study
    model = workflow._load(root, 'train', protocol, name='train/ABCD-42').read_json('model.json')
    model['history'] = model['history'][:2]
    model['model_id'] = digest_json({k: v for k, v in model.items() if k != 'model_id'})
    with pytest.raises(ResearchError, match='checkpoint history'):
        training.validate_model(model, protocol)


def test_grouped_spectra_covariance_signed_bins_and_boundaries():
    frame = pd.DataFrame(dict(m4l=[105., 105., 139.99], event_group_id=['a', 'a', 'b'],
                              yield_weight=[3., -1., -1.]))
    result = mass_spectra(frame, [True, True, False], [105., 110., 140.])
    assert result['yields'] == [2., -1., 2., 0.]
    assert result['covariance'][0][0] == 4.
    assert result['covariance'][0][2] == 4.
    assert result['low_support'][1]
    frame.loc[2, 'm4l'] = 140.
    with pytest.raises(ResearchError, match='half-open'):
        mass_spectra(frame, [True, True, False], [105., 110., 140.])


def test_retention_and_normalized_shapes_share_event_covariance():
    frame = pd.DataFrame(dict(m4l=[106.]*40+[126.]*40,
        event_group_id=[f'g{i}' for i in range(80)], yield_weight=[1.]*80))
    selected = np.arange(80) % 2 == 0
    result = mass_spectra(frame, selected, [105., 120., 140.])
    assert result['retention'] == .5
    assert result['retention_error'] == pytest.approx(np.sqrt(.25/80))
    assert result['normalization_status'] == 'valid_signed_shape'
    assert result['fractions'] == [.5, .5, .5, .5]
    assert np.asarray(result['shape_covariance'])[:2, 2:].sum() == pytest.approx(0, abs=1e-15)


def test_support_cross_category_covariance_and_missing_upper_crossing(protocol):
    frame = pd.DataFrame(dict(role=['evaluation']*4, dataset=[protocol['dataset']]*4,
        m4l=[125.]*4, event_group_id=['s', 's', 'b', 'b'], label=[1, 1, 0, 0],
        yield_weight=[1., 1., 1., 1.], category=[0, 1, 0, 1]))
    result = workflow._infer(frame, protocol, 'x', 'f')
    assert result['status'] == 'insufficient_statistics'
    with pytest.raises(ResearchError, match='template role'):
        build_templates(frame, mass_edges=[105, 140], candidate_id='x', mapping_id='f')
    # Distinct groups provide sufficient diagonal support; a repeated group
    # crossing categories remains incompatible with shapesys independence.
    rows = []
    for label in (0, 1):
        for i in range(30):
            for category in (0, 1):
                rows.append(dict(role='evaluation', dataset=protocol['dataset'], m4l=125.,
                    event_group_id=f'{label}:{i}', label=label, yield_weight=.1, category=category))
    result = workflow._infer(pd.DataFrame(rows), protocol, 'x', 'f')
    assert result['status'] == 'template_stat_model_unvalidated'
    template = {'status': 'valid', 'active_bins': [0], 'mapping_id': 'm', 'candidate_id': 'x'}
    template['samples'] = [dict(name='s', is_signal=True, **{'yield': [10.]}, variance=[1.], covariance=[[1.]]),
                           dict(name='b', is_signal=False, **{'yield': [20.]}, variance=[2.], covariance=[[2.]])]
    model, _ = build_model(template, mu_max=1.1)
    assert profile_interval(model, [30.])['status'] == 'interval_unbounded'
    assert profile_interval(model, [20.])['lower'] == 0.


def test_within_seed_contrasts_not_difference_of_medians():
    results = {key: dict(status='valid', interval={'width': 1.}) for key in [*candidate_keys(), 'inclusive']}
    for seed, full, reduced in zip(SEEDS, [1, 10, 20], [8, 11, 19]):
        results[f'ABCD:{seed}']['interval']['width'] = full
        results[f'BCD:{seed}']['interval']['width'] = reduced
    summary = summarize(results)
    assert summary['contrasts'][0]['differences'] == [7., 1., -1.]
    assert summary['contrasts'][0]['median_difference'] == 1.
    results['BCD:43'] = {'status': 'insufficient_statistics'}
    assert summarize(results)['rows'][1]['median'] is None
    assert summarize(results)['contrasts'][0]['median_difference'] is None


def test_plan_only_is_metadata_only_without_writes(tmp_path, protocol, monkeypatch):
    root = tmp_path / 'no-output'
    monkeypatch.setattr(data, 'read_events', lambda *a, **kw: pytest.fail('event reader opened'))
    monkeypatch.setattr(workflow, 'prepare', lambda *a, **kw: pytest.fail('stage launched'))
    assert main(['prepare', '--protocol', str(DEFAULT_PROTOCOL), '--run-root', str(root), '--plan-only']) == 0
    assert plan(root, protocol, ['prepare'])['prepared_identity'] == 'pending_prepare_identity'
    assert not root.exists()


def test_pending_and_stale_access_rejected_before_payload(frozen_study, protocol, monkeypatch):
    root, source, review, prepared, frozen = frozen_study
    monkeypatch.setattr(data, 'read_events', lambda *a, **kw: pytest.fail('evaluation opened'))
    with pytest.raises(ResearchError, match='explicit reviewed'):
        workflow.evaluate(root, protocol)
    with pytest.raises(ResearchError, match='pending'):
        workflow.evaluate(root, protocol, access_review=frozen.path / 'access-review.pending.json')
    directory = root.parent / '.research-claims'
    directory.mkdir()
    (directory / 'new-foreign-access.json').write_text(json.dumps(
        {'population_id': 'other-selected-population', 'freeze_artifact_id': 'other-freeze'}))
    with pytest.raises(ResearchError, match='stale'):
        workflow.evaluate(root, protocol, access_review=review)


def test_interrupted_evaluation_requires_explicit_retry_and_preserves_failure(frozen_study, protocol, monkeypatch):
    root, source, review, prepared, frozen = frozen_study
    def interrupted(*args, **kwargs):
        raise RuntimeError('synthetic interruption after durable claim')
    with monkeypatch.context() as patch:
        patch.setattr(data, 'read_events', interrupted)
        with pytest.raises(RuntimeError, match='synthetic interruption'):
            workflow.evaluate(root, protocol, access_review=review)
    failure = root / 'evaluate'
    assert (failure / 'failure.json').is_file()
    assert read_json(failure / 'manifest.json')['status'] == 'internal_error'
    failure_bytes = (failure / 'manifest.json').read_bytes()
    with pytest.raises(ResearchError, match='retry-failed'):
        workflow.evaluate(root, protocol, access_review=review, continuation=True)
    previous = torch.get_num_threads()
    try:
        torch.set_num_threads(1)
        recovered = workflow.evaluate(root, protocol, access_review=review, retry_failed=True)
    finally:
        torch.set_num_threads(previous)
    assert recovered.path.name.startswith('evaluate-retry-')
    assert recovered.read_json('access-claim.json')['retry']
    report = workflow.report(root, protocol, evaluation_run=recovered.path)
    assert report.read_json('binding.json')['evaluation_artifact_id'] == recovered.manifest['artifact_id']
    assert (failure / 'manifest.json').read_bytes() == failure_bytes


def test_full_synthetic_workflow_and_validated_continuation(frozen_study, protocol):
    root, source, review, prepared, frozen = frozen_study
    previous = torch.get_num_threads()
    try:
        torch.set_num_threads(1)
        evaluation = workflow.evaluate(root, protocol, access_review=review, continuation=True)
        report = workflow.report(root, protocol, evaluation_run=evaluation.path)
    finally:
        torch.set_num_threads(previous)
    summary = report.read_json('summary.json')
    assert summary['scientific_status'] == 'complete'
    assert len(report.read_json('results.json')) == 16
    assert len(summary['rows']) == 5 and len(summary['contrasts']) == 4
    assert report.read_json('binding.json')['source_kind'] == 'synthetic'
    assert report.file('mass-yields.png').is_file()
    assert report.file('mass-shapes.pdf').is_file()
    assert report.file('yield-summary.csv').read_text().count('\n') == 9
    assert 'Source kind: **synthetic**' in report.file('report.md').read_text()
    assert report.file('widths.csv').read_text().startswith('source_kind,')
    assert workflow.prepare(root, protocol, synthetic_events=source, continuation=True).manifest == prepared.manifest
    assert workflow.freeze(root, protocol, continuation=True).manifest == frozen.manifest
    assert workflow.evaluate(root, protocol, continuation=True).manifest == evaluation.manifest
    assert workflow.report(root, protocol, evaluation_run=evaluation.path, continuation=True).manifest == report.manifest
    with pytest.raises(ResearchError, match='Completed evaluation'):
        workflow.evaluate(root, protocol, access_review=review, retry_failed=True)


def test_tamper_and_missing_model_block_without_payload(frozen_study, protocol, monkeypatch):
    root, source, review, prepared, frozen = frozen_study
    monkeypatch.setattr(data, 'read_events', lambda *a, **kw: pytest.fail('evaluation opened'))
    model = root / 'train/ABCD-42/model.json'
    saved = model.read_bytes()
    try:
        model.write_text('{}')
        with pytest.raises(ResearchError, match='digest mismatch'):
            workflow.evaluate(root, protocol, access_review=review)
    finally:
        model.write_bytes(saved)
    try:
        model.unlink()
        with pytest.raises(ResearchError, match='artifact file'):
            workflow.evaluate(root, protocol, access_review=review)
    finally:
        model.write_bytes(saved)


def test_history_overlap_does_not_depend_on_population_hash(tmp_path, protocol):
    root = tmp_path / 'study'
    directory = tmp_path / '.research-claims'
    directory.mkdir()
    (directory / 'old.json').write_text(json.dumps({'population_id': 'old-development-population',
                                                  'freeze_artifact_id': 'old-freeze'}))
    history = workflow.history(root, protocol)
    assert len(history['matches']) == 1
    assert history['historical_test_included'] and not history['independence_established']


def test_durable_claim_requires_explicit_same_freeze_retry(tmp_path, protocol):
    root = tmp_path / 'study'
    root.mkdir()
    class Prepared:
        manifest = {'artifact_id': 'p'}
    class Frozen:
        manifest = {'artifact_id': 'f'}
    frozen = {'population_id': 'population', 'freeze_id': 'freeze-seal', 'source_kind': 'synthetic'}
    first = workflow._claim(root, protocol, Prepared(), Frozen(), frozen, retry=False)
    with pytest.raises(ResearchError, match='retry-failed'):
        workflow._claim(root, protocol, Prepared(), Frozen(), frozen, retry=False)
    retry = workflow._claim(root, protocol, Prepared(), Frozen(), frozen, retry=True)
    assert retry['path'] == first['path'] and retry['retry']


def test_later_legacy_population_sees_controlled_all_mc_access(tmp_path):
    from higgsml.inference.population_history import audit_population_history, claim_population
    directory = tmp_path / '.h4l-draft-v2-claims'
    directory.mkdir()
    path = directory / 'access.json'
    claim = {'binding': dict(population_id='different-all-mc-population', prepared_artifact_id='new-prepared',
        freeze_artifact_id='new-freeze', dataset='atlas2020_4lep', source_population='all_mc', source_kind='synthetic')}
    path.write_text(json.dumps(claim))
    assert not audit_population_history(tmp_path, population_id='historical-development')['matches']
    claim['binding']['source_kind'] = 'controlled_mc'
    path.write_text(json.dumps(claim))
    assert len(audit_population_history(tmp_path, population_id='historical-development')['matches']) == 1
    with pytest.raises(ResearchError, match='previously used'):
        claim_population(tmp_path, 'historical-development', 'another-freeze')


def test_concurrent_evaluation_lock_is_released(tmp_path):
    with workflow._evaluation_lock(tmp_path):
        with pytest.raises(ResearchError, match='active'):
            with workflow._evaluation_lock(tmp_path):
                pytest.fail('A concurrent evaluator acquired the lock')
    with workflow._evaluation_lock(tmp_path):
        pass


def test_wrapper_plan_never_launches_or_writes(tmp_path, monkeypatch, capsys):
    import importlib.util
    wrapper = Path(__file__).resolve().parents[2] / 'scripts/h4l_draft_v2.py'
    spec = importlib.util.spec_from_file_location('draft_v2_wrapper_test', wrapper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(workflow, 'prepare', lambda *a, **kw: pytest.fail('wrapper launched prepare'))
    assert module.main(['--run-name', 'plan', '--plan-only']) == 0
    assert json.loads(capsys.readouterr().out)['mode'] == 'plan_only'
    assert not (tmp_path / 'runs').exists()
