"""Archived access must remain visible without opening scientific payloads."""
import json
from types import SimpleNamespace

import pytest

from higgsml.errors import ResearchError, ResearchStateError
from higgsml.inference import marginal_workflow as workflow
from higgsml.inference import population_history


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def roots(tmp_path):
    current = tmp_path / 'runs'
    archive = tmp_path / 'archive'
    current.mkdir()
    archive.mkdir()
    write(tmp_path / 'config/h4l_history_roots.json', {
        'schema_version': 'h4l-history-roots-v1',
        'roots': [{'path': 'runs', 'required': False}, {'path': 'archive', 'required': True}],
    })
    return current, archive


def test_archived_claim_is_visible_from_new_prepare_root(tmp_path):
    current, archive = roots(tmp_path)
    claim = archive / '.h4l-mass-off-v3-claims/cell-old.json'
    write(claim, {'binding': {'population_id': 'population', 'freeze_artifact_id': 'old',
                             'stage': 'assessment'}})
    prepared = SimpleNamespace(path=current / 'new/prepare',
                               manifest={'population_id': 'population', 'artifact_id': 'prepared'})
    history = workflow.source_history(prepared)
    assert len(history) == 1
    assert history[0]['path'] == str(claim.resolve())
    assert not (current / 'new').exists()


def test_archived_population_blocks_new_claim_before_creating_ledger(tmp_path):
    current, archive = roots(tmp_path)
    write(archive / '.h4l-population-access/old.json',
          {'population_id': 'population', 'freeze_artifact_id': 'old'})
    with pytest.raises(ResearchStateError, match='previously used'):
        population_history.claim_population(current, 'population', 'new')
    assert not (current / '.h4l-population-access').exists()


def test_required_archive_cannot_silently_disappear(tmp_path):
    current, archive = roots(tmp_path)
    archive.rmdir()
    prepared = SimpleNamespace(path=current / 'new/prepare',
                               manifest={'population_id': 'population', 'artifact_id': 'prepared'})
    with pytest.raises(ResearchError, match='history root'):
        workflow.source_history(prepared)


def test_malformed_historical_claim_fails_closed(tmp_path):
    current, archive = roots(tmp_path)
    write(archive / '.research-claims/broken.json', {'binding': {}})
    prepared = SimpleNamespace(path=current / 'new/prepare',
                               manifest={'population_id': 'population', 'artifact_id': 'prepared'})
    with pytest.raises(ResearchError, match='history'):
        workflow.source_history(prepared)


def test_model_self_does_not_consume_population(tmp_path):
    current, archive = roots(tmp_path)
    write(archive / '.h4l-mass-off-v3-claims/model.json',
          {'binding': {'population_id': 'population', 'freeze_artifact_id': 'old',
                       'stage': 'model-self'}})
    population_history.claim_population(current, 'population', 'new')
    assert len(list((current / '.h4l-population-access').glob('*.json'))) == 1


def test_same_freeze_can_resume_across_registered_roots(tmp_path):
    current, archive = roots(tmp_path)
    write(archive / '.h4l-population-access/old.json',
          {'population_id': 'population', 'freeze_artifact_id': 'same'})
    population_history.claim_population(current, 'population', 'same')


def test_registered_roots_share_one_atomic_population_reservation(tmp_path):
    current, archive = roots(tmp_path)
    population_history.claim_population(archive, 'population', 'first')
    assert len(list((current / '.h4l-population-access').glob('*.json'))) == 1
    assert not (archive / '.h4l-population-access').exists()
    with pytest.raises(ResearchStateError):
        population_history.claim_population(current, 'population', 'second')
