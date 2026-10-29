"""Immutable draft-v2 stages, explicit exploratory access and complete lineage."""
import os
import sys
from contextlib import contextmanager
from pathlib import Path
import uuid

import pandas as pd
from tqdm.auto import tqdm

from higgsml.artifacts import ResearchRun, digest_json, read_json, read_run
from higgsml.dataset_binding import dataset_context
from higgsml.errors import ResearchError, ResearchStateError
from higgsml.inference.likelihood import build_model, profile_interval
from higgsml.inference.population_history import audit_population_history
from higgsml.inference.templates import _build_role_templates
from higgsml.protocol import canonical
from higgsml.qualification import contract_qualification
from higgsml.draft_v2 import data, training
from higgsml.draft_v2.protocol import CANDIDATES, SEEDS, QUALIFICATION, candidate_key, candidate_keys
from higgsml.draft_v2.protocol import DEFAULT_PROTOCOL
from higgsml.draft_v2.reporting import export_report, mass_spectra, summarize


def _load(root, stage, protocol, *, name=None):
    loaded = read_run(Path(root) / (name or stage), dataset=protocol['dataset'], protocol=protocol,
                      stages=(f'draft-v2-{stage}',))
    for filename in loaded.manifest['files']:
        loaded.file(filename)
    return loaded


def _run(root, name, stage, protocol, upstreams=()):
    return ResearchRun(Path(root) / name, allowed_root=root, stage=f'draft-v2-{stage}',
                       dataset=protocol['dataset'], protocol=protocol, upstreams=list(upstreams),
                       context={'qualification': QUALIFICATION, 'source_population': 'all_mc'})


def _existing(root, name, stage, protocol, continuation):
    if not os.path.lexists(Path(root) / name):
        return None
    if not continuation:
        raise ResearchError(f'Published stage exists: {name}; use --continue to validate and reuse it')
    # Unlike old orchestration, never quarantine and recompute a new scientific
    # choice automatically. Invalid evidence remains exactly where it was.
    return _load(root, stage, protocol, name=name)


def _prepared(root, protocol):
    loaded = _load(root, 'prepare', protocol)
    metadata = loaded.read_json('population.json')
    if (metadata.get('schema_version') != 'h4l-draft-v2-population-v1'
            or metadata.get('source_kind') not in {'synthetic', 'controlled_mc'}
            or metadata.get('dataset_snapshot') != dataset_context(protocol['dataset']).snapshot()
            or metadata.get('historical_test_included') is not True
            or metadata.get('qualification') != QUALIFICATION):
        raise ResearchError('Invalid prepared population binding')
    return loaded, metadata


def prepare(root, protocol, *, receipt=None, synthetic_events=None, continuation=False, progress=True):
    if (receipt is None) == (synthetic_events is None):
        raise ResearchError('Provide exactly one MC acquisition receipt or labelled synthetic fixture')
    source = Path(receipt if receipt is not None else synthetic_events).resolve()
    source_binding = dict(source_path=str(source), source_sha256=digest_json(read_json(source)),
                          source_kind='controlled_mc' if receipt is not None else 'synthetic')
    prior = _existing(root, 'prepare', 'prepare', protocol, continuation)
    if prior is not None:
        if prior.read_json('source.json') != source_binding:
            raise ResearchError('Prepare continuation source changed')
        _prepared(root, protocol)
        return prior
    with _run(root, 'prepare', 'prepare', protocol) as run:
        run.write_json('source.json', source_binding)
        if receipt is not None:
            manifest = data.root_manifest(receipt, protocol)
            manifest_path = run.write_json('root-input.json', manifest)
            frame = data.reconstruct(manifest_path, protocol, progress=progress)
        else:
            fixture = read_json(source)
            if (set(fixture) != {'schema_version', 'dataset', 'source_kind', 'events'}
                    or fixture['schema_version'] != 'h4l-draft-v2-synthetic-v1'
                    or fixture['dataset'] != protocol['dataset'] or fixture['source_kind'] != 'synthetic'):
                raise ResearchError('Only explicitly labelled draft-v2 synthetic events are accepted')
            frame = data.assign_roles(pd.DataFrame(fixture['events']), protocol)
            frame.attrs.update(source_kind='synthetic', source_evidence={'fixture_sha256': source_binding['source_sha256']})
        population_id = data.write_events(frame, run.path / 'events.jsonl', protocol)
        run.register_file('events.jsonl')
        # Deliberately no evaluation-value audit, plots or support-based tuning.
        run.write_json('population.json', dict(schema_version='h4l-draft-v2-population-v1',
            population_id=population_id, source_kind=frame.attrs['source_kind'],
            dataset_snapshot=dataset_context(protocol['dataset']).snapshot(),
            source_evidence=frame.attrs.get('source_evidence', {}),
            historical_test_included=True, qualification=QUALIFICATION))
    return _load(root, 'prepare', protocol)


def _check_model(loaded, prepared, metadata, protocol, subset, seed):
    state = loaded.read_json('training-state.json')
    if (state.get('key') != candidate_key(subset, seed)
            or state.get('prepared_artifact_id') != prepared.manifest['artifact_id']):
        raise ResearchError('Training-stage binding mismatch')
    if state['status'] != 'trained':
        return None
    model = loaded.read_json('model.json')
    training.validate_model(model, protocol, subset=subset, seed=seed,
                            prepared_id=prepared.manifest['artifact_id'])
    if model['source_kind'] != metadata['source_kind']:
        raise ResearchError('Synthetic/MC model lineage mismatch')
    return model


def train(root, protocol, *, continuation=False, progress=True):
    prepared, metadata = _prepared(root, protocol)
    frame = None
    stages = []
    with tqdm(total=len(candidate_keys()), desc='Training units', unit='model',
              disable=not progress, file=sys.stderr) as model_progress:
        for subset, seed in [(s, k) for s in CANDIDATES for k in SEEDS]:
            key, name = candidate_key(subset, seed), f'train/{subset}-{seed}'
            prior = _existing(root, name, 'train', protocol, continuation)
            if prior is not None:
                _check_model(prior, prepared, metadata, protocol, subset, seed)
                stages.append(prior)
                model_progress.set_postfix(unit=key, status='reused', refresh=False)
                model_progress.update()
                continue
            if frame is None:
                frame = data.read_events(prepared.file('events.jsonl'), protocol)
                if frame.attrs['population_id'] != metadata['population_id']:
                    raise ResearchError('Prepared population digest mismatch')
            if progress:
                tqdm.write(f'TRAIN draft-v2 {key}', file=sys.stderr)
            with _run(root, name, 'train', protocol, [prepared]) as run:
                state = dict(key=key, prepared_artifact_id=prepared.manifest['artifact_id'], status='trained')
                try:
                    model = training.train(frame, protocol, subset, seed, prepared.manifest['artifact_id'],
                                           progress=progress)
                    run.write_json('model.json', model)
                except ResearchStateError as error:
                    state.update(status=error.status, reason=str(error))
                run.write_json('training-state.json', state)
            stages.append(_load(root, 'train', protocol, name=name))
            model_progress.set_postfix(unit=key, status=state['status'], refresh=False)
            model_progress.update()
    return stages


def history(root, protocol, *, freeze_artifact_id=None):
    audit = audit_population_history(Path(root).parent)
    # A whole-MC study overlaps the source release of any historical development
    # study. Do not use unequal selected-population hashes as non-overlap proof.
    matches = []
    for item in audit['matches']:
        binding = item['claim'].get('binding', item['claim'])
        if binding.get('freeze_artifact_id') != freeze_artifact_id or freeze_artifact_id is None:
            matches.append(item)
    return {**audit, 'matches': matches, 'dataset': protocol['dataset'],
            'overlap_policy': 'all_declared_claims_conservatively_potentially_overlap_all_mc',
            'historical_test_included': True, 'independence_established': False}


def freeze(root, protocol, *, continuation=False):
    prepared, metadata = _prepared(root, protocol)
    models, upstreams = {}, [prepared]
    for subset in CANDIDATES:
        for seed in SEEDS:
            loaded = _load(root, 'train', protocol, name=f'train/{subset}-{seed}')
            model = _check_model(loaded, prepared, metadata, protocol, subset, seed)
            if model is None:
                raise ResearchError('All fifteen trained models are required before evaluation')
            models[candidate_key(subset, seed)] = dict(artifact_id=loaded.manifest['artifact_id'],
                                                      model_id=model['model_id'], threshold=model['threshold'])
            upstreams.append(loaded)
    prior = _existing(root, 'freeze', 'freeze', protocol, continuation)
    if prior is not None:
        frozen = prior.read_json('freeze.json')
        if frozen.get('models') != models or frozen.get('prepared_artifact_id') != prepared.manifest['artifact_id']:
            raise ResearchError('Freeze continuation bindings changed')
        _validate_freeze(prior, prepared, protocol)
        return prior
    value = dict(schema_version='h4l-draft-v2-freeze-v1', status='frozen',
        protocol_sha256=digest_json(protocol), prepared_artifact_id=prepared.manifest['artifact_id'],
        population_id=metadata['population_id'], source_kind=metadata['source_kind'], models=models,
        qualification=QUALIFICATION, report_contract=dict(candidates=list(CANDIDATES), seeds=list(SEEDS),
            contrasts='within_seed_reduced_minus_ABCD_then_median', inclusive='one_shared_count',
            spectra=protocol['spectra']), history=history(root, protocol))
    value['freeze_id'] = digest_json(value)
    with _run(root, 'freeze', 'freeze', protocol, upstreams) as run:
        run.write_json('freeze.json', value)
        # A pending example is useful for a real reviewer, never authorization.
        run.write_json('access-review.pending.json', access_template(root, protocol, prepared, metadata, value))
    return _load(root, 'freeze', protocol)


def _validate_freeze(loaded, prepared, protocol):
    value = loaded.read_json('freeze.json')
    if (value.get('schema_version') != 'h4l-draft-v2-freeze-v1' or value.get('status') != 'frozen'
            or value.get('protocol_sha256') != digest_json(protocol)
            or value.get('prepared_artifact_id') != prepared.manifest['artifact_id']
            or value.get('qualification') != QUALIFICATION or set(value.get('models', {})) != set(candidate_keys())
            or value.get('freeze_id') != digest_json({k: v for k, v in value.items() if k != 'freeze_id'})):
        raise ResearchError('Draft-v2 freeze seal/binding mismatch')
    metadata = prepared.read_json('population.json')
    if value.get('population_id') != metadata['population_id'] or value.get('source_kind') != metadata['source_kind']:
        raise ResearchError('Freeze source/population mismatch')
    expected_report = dict(candidates=list(CANDIDATES), seeds=list(SEEDS),
        contrasts='within_seed_reduced_minus_ABCD_then_median', inclusive='one_shared_count', spectra=protocol['spectra'])
    if value.get('report_contract') != expected_report:
        raise ResearchError('Frozen report rules changed')
    for subset in CANDIDATES:
        for seed in SEEDS:
            trained = _load(loaded.path.parent, 'train', protocol, name=f'train/{subset}-{seed}')
            model = _check_model(trained, prepared, metadata, protocol, subset, seed)
            if model is None or value['models'][candidate_key(subset, seed)] != dict(
                    artifact_id=trained.manifest['artifact_id'], model_id=model['model_id'], threshold=model['threshold']):
                raise ResearchError('Frozen model/threshold binding mismatch')
    return value


def access_template(root, protocol, prepared, metadata, frozen):
    return dict(schema_version='h4l-draft-v2-access-v1', status='pending', decision='pending',
        dataset=protocol['dataset'], source_population='all_mc', source_kind=metadata['source_kind'],
        historical_test_included=True, independent=False,
        protocol_sha256=digest_json(protocol), prepared_artifact_id=prepared.manifest['artifact_id'],
        freeze_id=frozen['freeze_id'], history_sha256=digest_json(history(root, protocol)),
        reviewed_by='', reviewed_at='')


def _review(root, protocol, prepared, metadata, frozen, freeze_run, review_path):
    if review_path is None:
        raise ResearchError('Evaluation requires an explicit reviewed draft-v2 access receipt')
    review = read_json(Path(review_path))
    from jsonschema import Draft202012Validator
    try:
        Draft202012Validator(read_json(DEFAULT_PROTOCOL.parent.parent /
            'schemas/h4l_draft_v2_access.schema.json')).validate(review)
    except Exception as error:
        raise ResearchError('Invalid draft-v2 access receipt schema') from error
    expected = access_template(root, protocol, prepared, metadata, frozen)
    expected['history_sha256'] = digest_json(history(root, protocol, freeze_artifact_id=freeze_run.manifest['artifact_id']))
    if (set(review) != set(expected) or review.get('status') != 'approved'
            or review.get('decision') != 'allow_exploratory_reuse'
            or not isinstance(review.get('reviewed_by'), str) or not review['reviewed_by'].strip()
            or not isinstance(review.get('reviewed_at'), str) or not review['reviewed_at'].strip()
            or any(review.get(k) != v for k, v in expected.items()
                   if k not in {'status', 'decision', 'reviewed_by', 'reviewed_at'})):
        raise ResearchError('Access review is pending, stale or not bound to this freeze/source/history')
    return review


def _claim(root, protocol, prepared, frozen_run, frozen, *, retry):
    audit = history(root, protocol, freeze_artifact_id=frozen_run.manifest['artifact_id'])
    directory = Path(audit['roots'][0]) / '.h4l-draft-v2-claims'
    if directory.is_symlink() or directory.is_junction():
        raise ResearchError('Unsafe claim directory')
    directory.mkdir(parents=True, exist_ok=True)
    binding = dict(population_id=frozen['population_id'], prepared_artifact_id=prepared.manifest['artifact_id'],
        freeze_artifact_id=frozen_run.manifest['artifact_id'], freeze_id=frozen['freeze_id'],
        dataset=protocol['dataset'], source_population='all_mc', source_kind=frozen['source_kind'],
        stage='draft-v2-evaluation')
    path = directory / (digest_json(binding) + '.json')
    if path.exists():
        if read_json(path) != {'binding': binding} or not retry:
            raise ResearchError('Claimed evaluation requires explicit --retry-failed under the same freeze')
    else:
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as error:
            raise ResearchError('Concurrent evaluation claim; retry requires explicit authorization') from error
        with os.fdopen(fd, 'wb') as stream:
            stream.write(canonical({'binding': binding}))
            stream.flush()
            os.fsync(stream.fileno())
    return {'path': str(path), 'binding': binding, 'retry': bool(retry)}


def _t1_contract(protocol):
    return dict(schema_version='h4l-t1-validation-v2', status='contract_checked',
        dataset=protocol['dataset'], protocol_sha256=digest_json(protocol),
        evidence_id='draft-v2-software-T1-' + digest_json(protocol), independent_reference=None,
        correlation='independent_process_bins', auxiliary='poisson_tau_gamma', modifier='shapesys', pyhf_version='0.7.6',
        validation_summary={'reviewed_by': 'draft-v2-versioned-software-contract',
                            'reviewed_at': 'bound-protocol', 'numerical_tests': []},
        qualification=contract_qualification(True))


def _infer(frame, protocol, key, mapping_id, *, inclusive=False):
    try:
        template = _build_role_templates(frame, mass_edges=protocol['templates']['mass_edges'],
            mapping_id=mapping_id, candidate_id=key, categories=(0,) if inclusive else (0, 1),
            thresholds=protocol['templates'], expected_role='evaluation')
    except ResearchStateError as error:
        return dict(status=error.status, reason=str(error))
    if template['status'] != 'valid':
        return dict(status=template['status'], template=template)
    try:
        model, model_metadata = build_model(template, layer='T1', t1_validation=_t1_contract(protocol), mu_max=20.)
        parameters = model.config.suggested_init()
        parameters[model.config.poi_index] = 1.
        interval = profile_interval(model, model.expected_data(parameters), confidence=.68)
        return dict(status=interval['status'], interval=interval, template=template,
                    model_metadata=model_metadata, expectation_kind='model_self_asimov')
    except ResearchStateError as error:
        return dict(status=error.status, reason=str(error), template=template)


def _evaluation(root, protocol, freeze_run, *, name='evaluate'):
    loaded = _load(root, 'evaluate', protocol, name=name)
    binding = loaded.read_json('binding.json')
    frozen = freeze_run.read_json('freeze.json')
    expected = dict(freeze_artifact_id=freeze_run.manifest['artifact_id'],
        prepared_artifact_id=frozen['prepared_artifact_id'], freeze_id=frozen['freeze_id'],
        population_id=frozen['population_id'], source_kind=frozen['source_kind'])
    if binding != expected:
        raise ResearchError('Evaluation freeze changed')
    results = loaded.read_json('results.json')
    if summarize(results) != loaded.read_json('summary.json'):
        raise ResearchError('Evaluation summary differs from complete result states')
    review = loaded.read_json('access-review.json')
    if (review.get('freeze_id') != frozen['freeze_id'] or review.get('status') != 'approved'
            or review.get('source_kind') != frozen['source_kind'] or review.get('independent') is not False
            or review.get('decision') != 'allow_exploratory_reuse'):
        raise ResearchError('Evaluation access receipt mismatch')
    if set(loaded.read_json('spectra.json')) != {'ABCD:42', 'BCD:42'}:
        raise ResearchError('Missing planned mass diagnostics')
    for key, result in results.items():
        if 'template' in result:
            mapping = frozen['freeze_id'] if key == 'inclusive' else frozen['models'][key]['model_id']
            if result['template'].get('mapping_id') != mapping or result['template'].get('candidate_id') != key:
                raise ResearchError('Evaluation mapping/model identity mismatch')
    return loaded


@contextmanager
def _evaluation_lock(root):
    """OS-released lock also serializes explicit retries after a process crash."""
    path = Path(root) / '.evaluation.lock'
    if not Path(root).is_dir() or path.is_symlink():
        raise ResearchError('Evaluation requires a safe prepared workflow root')
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    acquired = False
    try:
        if os.fstat(fd).st_size == 0:
            os.write(fd, b'0')
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as error:
            raise ResearchError('Another evaluation attempt is active for this workflow') from error
        yield
    finally:
        if acquired:
            if os.name == 'nt':
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def evaluate(root, protocol, *, access_review=None, continuation=False, retry_failed=False):
    with _evaluation_lock(root):
        return _evaluate(root, protocol, access_review=access_review,
                         continuation=continuation, retry_failed=retry_failed)


def _evaluate(root, protocol, *, access_review=None, continuation=False, retry_failed=False):
    prepared, metadata = _prepared(root, protocol)
    frozen_run = _load(root, 'freeze', protocol)
    frozen = _validate_freeze(frozen_run, prepared, protocol)
    models, upstreams = {}, [prepared, frozen_run]
    for subset in CANDIDATES:
        for seed in SEEDS:
            key = candidate_key(subset, seed)
            loaded = _load(root, 'train', protocol, name=f'train/{subset}-{seed}')
            model = _check_model(loaded, prepared, metadata, protocol, subset, seed)
            if model is None or frozen['models'][key] != dict(artifact_id=loaded.manifest['artifact_id'],
                    model_id=model['model_id'], threshold=model['threshold']):
                raise ResearchError('Evaluation model differs from frozen choice')
            models[key] = model
            upstreams.append(loaded)
    if continuation and not retry_failed:
        # Accept only a fully validated terminal. Never replace a numerical
        # failure with another attempt merely because its outcome is unfavourable.
        candidates = [Path(root)/'evaluate', *sorted(Path(root).glob('evaluate-retry-*'), reverse=True)]
        invalid = None
        for path in candidates:
            if path.exists():
                try:
                    return _evaluation(root, protocol, frozen_run, name=path.name)
                except ResearchError as error:
                    invalid = error
        if invalid is not None:
            raise ResearchError('Existing evaluation evidence is invalid; preserve it and use explicit --retry-failed') from invalid
    if retry_failed:
        for path in [Path(root)/'evaluate', *Path(root).glob('evaluate-retry-*')]:
            if path.exists():
                try:
                    _evaluation(root, protocol, frozen_run, name=path.name)
                except ResearchError:
                    continue
                raise ResearchError('Completed evaluation cannot be rerun, including scientific failures')
    review = _review(root, protocol, prepared, metadata, frozen, frozen_run, access_review)
    claim = _claim(root, protocol, prepared, frozen_run, frozen, retry=retry_failed)
    name = 'evaluate-retry-' + uuid.uuid4().hex if retry_failed else 'evaluate'
    with _run(root, name, 'evaluate', protocol, upstreams) as run:
        run.write_json('binding.json', dict(freeze_artifact_id=frozen_run.manifest['artifact_id'],
            prepared_artifact_id=prepared.manifest['artifact_id'], freeze_id=frozen['freeze_id'],
            population_id=frozen['population_id'], source_kind=metadata['source_kind']))
        run.write_json('access-review.json', review)
        run.write_json('access-claim.json', claim)
        frame = data.read_events(prepared.file('events.jsonl'), protocol, evaluation=True,
                                 freeze=frozen, prepared_id=prepared.manifest['artifact_id'])
        if frame.attrs['population_id'] != frozen['population_id']:
            raise ResearchError('Frozen evaluation population changed')
        results = {'inclusive': _infer(frame.assign(category=0), protocol, 'inclusive', frozen['freeze_id'], inclusive=True)}
        spectra = {}
        for key, model in models.items():
            print(f'EVALUATE draft-v2 {key}', flush=True)
            scores = training.predict(model, frame, protocol)
            accepted = scores >= model['threshold']
            try:
                results[key] = _infer(frame.assign(category=accepted.astype(int)), protocol, key, model['model_id'])
            except ResearchStateError as error:
                results[key] = dict(status=error.status, reason=str(error))
            if key in {candidate_key(s, protocol['spectra']['seed']) for s in protocol['spectra']['candidates']}:
                spectra[key] = {process: mass_spectra(frame.loc[frame.label == label],
                    accepted[frame.label.to_numpy() == label], protocol['spectra']['mass_edges'])
                    for process, label in (('signal', 1), ('background', 0))}
        run.write_json('results.json', results)
        run.write_json('spectra.json', spectra)
        run.write_json('summary.json', summarize(results))
    return _evaluation(root, protocol, frozen_run, name=name)


def report(root, protocol, *, evaluation_run=None, continuation=False):
    prepared, metadata = _prepared(root, protocol)
    frozen_run = _load(root, 'freeze', protocol)
    _validate_freeze(frozen_run, prepared, protocol)
    name = Path(evaluation_run).name if evaluation_run is not None else 'evaluate'
    if evaluation_run is not None and Path(evaluation_run).absolute().parent != Path(root).absolute():
        raise ResearchError('Evaluation report source must belong to this workflow root')
    evaluation = _evaluation(root, protocol, frozen_run, name=name)
    summary = summarize(evaluation.read_json('results.json'))
    binding = dict(evaluation_artifact_id=evaluation.manifest['artifact_id'],
                   freeze_artifact_id=frozen_run.manifest['artifact_id'],
                   prepared_artifact_id=prepared.manifest['artifact_id'], source_kind=metadata['source_kind'])
    prior = _existing(root, 'report', 'report', protocol, continuation)
    if prior is not None:
        if prior.read_json('binding.json') != binding or prior.read_json('summary.json') != summary:
            raise ResearchError('Report continuation bindings changed')
        return prior
    with _run(root, 'report', 'report', protocol, [evaluation, frozen_run, prepared]) as run:
        run.write_json('binding.json', binding)
        run.write_json('summary.json', summary)
        run.write_json('results.json', evaluation.read_json('results.json'))
        spectra = evaluation.read_json('spectra.json')
        run.write_json('spectra.json', spectra)
        export_report(run, summary, spectra, source_kind=metadata['source_kind'])
    return _load(root, 'report', protocol)
