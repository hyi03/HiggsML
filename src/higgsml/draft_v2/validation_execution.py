"""Bounded execution with immutable paired units, claims and explicit recovery."""
from contextlib import contextmanager
from pathlib import Path
import os
import platform
import sys
from time import perf_counter
import uuid

import numpy as np
from tqdm.auto import tqdm

from higgsml.artifacts import digest_json, read_json
from higgsml.errors import ResearchError
from higgsml.resources import ordered_map
from higgsml.draft_v2 import data
from higgsml.draft_v2.workflow import _evaluation_lock
from higgsml.draft_v2.reporting import summarize
from higgsml.draft_v2 import validation_registry as registry
from higgsml.draft_v2.validation_protocol import KEYS, MODES, EXPECTED, stream, units
from higgsml.draft_v2.validation_statistics import build_cache, bootstrap_replica, model_self_cell, toy_summary


def unit_binding(registration, unit):
    specification = units().get(unit)
    if specification is None:
        raise ResearchError('Unknown supplemental unit')
    return dict(registration_id=registration['registration_id'], unit=unit,
                specification=specification, protocol_sha256=digest_json(EXPECTED),
                source_freeze_id=registration['source']['freeze_id'])


def _interval(record):
    if not isinstance(record, dict) or record.get('status') not in {
            'valid', 'fit_failed', 'interval_unbounded', 'insufficient_statistics', 'template_stat_model_unvalidated'}:
        raise ResearchError('Missing or unknown numerical terminal state')
    if record['status'] == 'valid':
        values = [record.get(k) for k in ('lower', 'upper', 'width', 'muhat')]
        if (any(v is None or not np.isfinite(v) for v in values) or record.get('confidence') != .68
                or not 0 <= values[0] <= values[1] <= 20 or values[2] <= 0
                or not np.isclose(values[2], values[1]-values[0], atol=1e-9, rtol=1e-9)
                or not 0 <= values[3] <= 20):
            raise ResearchError('Invalid finite 68% interval')


def validate_result(result, registration, unit):
    """Validate full budgets and identities; no shortened test artifacts accepted."""
    spec = units()[unit]
    freeze_id = registration['source']['freeze_id']
    if spec['stage'] == 'model-self':
        if (result.get('key') != spec['key'] or result.get('mu') != spec['mu']
                or result.get('count') != 500 or len(result.get('results', [])) != 500
                or result.get('expectation_kind') != 'model_self' or result.get('paired') is not False
                or result.get('auxiliary_generation') != 'regenerated'):
            raise ResearchError('Toy unit candidate/injection/budget mismatch')
        for i, row in enumerate(result['results']):
            if row.get('toy') != i:
                raise ResearchError('Missing or duplicate Toy index')
            _interval(row['interval'])
            expected = stream(freeze_id, EXPECTED['toys']['seed'], 'model-self', spec['key'], spec['mu'], i)[1]
            if row.get('stream') != expected:
                raise ResearchError('Toy stream mismatch')
            if 'observation' in row:
                observed = np.asarray(row['observation'], float)
                if observed.ndim != 1 or not len(observed) or not np.isfinite(observed).all() or (observed < 0).any():
                    raise ResearchError('Toy observation mismatch')
            elif row['interval']['status'] in {'valid', 'fit_failed', 'interval_unbounded'}:
                raise ResearchError('Missing generated Toy observations')
        if result['summary'] != toy_summary([r['interval'] for r in result['results']], spec['mu']):
            raise ResearchError('Toy summary does not match planned outcomes')
        return
    if result.get('replica') != spec['replica'] or set(result.get('results', {})) != set(MODES):
        raise ResearchError('Paired bootstrap replica/mode mismatch')
    identity = result.get('cache_identity', {})
    if (identity.get('freeze_id') != freeze_id or identity.get('population_id') != registration['source']['population_id']
            or set(identity.get('model_ids', {})) != set(KEYS)-{'inclusive'}):
        raise ResearchError('Bootstrap score-cache binding mismatch')
    if identity.get('model_ids') != registration['source']['model_ids']:
        raise ResearchError('Bootstrap model identities changed')
    for role in ('validation', 'evaluation'):
        record = result['draws'][role]
        expected = stream(freeze_id, EXPECTED['bootstrap']['seed'], 'bootstrap', role, spec['replica'])[1]
        if record.get('stream') != expected or record.get('groups', 0) <= 0 or record.get('total') != record['groups']:
            raise ResearchError('Bootstrap draw stream or group count mismatch')
        from higgsml.draft_v2.validation_statistics import draw
        counts, _ = draw(freeze_id, role, spec['replica'], record['groups'])
        if record.get('multiplicity_sha256') != digest_json(counts.tolist()):
            raise ResearchError('Bootstrap multiplicities changed')
    if set(result.get('thresholds', {})) != set(KEYS)-{'inclusive'}:
        raise ResearchError('Missing threshold diagnostics')
    if any(t is not None and (not np.isfinite(t) or not 0 <= t <= 1) for t in result['thresholds'].values()):
        raise ResearchError('Invalid threshold diagnostic')
    for mode in MODES:
        rows = result['results'][mode]
        if set(rows) != set(KEYS) or result['contrasts'][mode] != summarize(rows)['contrasts']:
            raise ResearchError('Bootstrap candidate/contrast coverage mismatch')
        for key, row in rows.items():
            if not isinstance(row, dict) or row.get('status') not in {
                    'valid', 'fit_failed', 'interval_unbounded', 'insufficient_statistics',
                    'template_stat_model_unvalidated'}:
                raise ResearchError('Unknown bootstrap scientific terminal')
            if 'interval' in row:
                _interval(row['interval'])
                if row['interval']['status'] != row['status']:
                    raise ResearchError('Bootstrap interval status mismatch')
            if row.get('status') == 'valid' and (row.get('template', {}).get('status') != 'valid' or 'interval' not in row):
                raise ResearchError('Valid bootstrap result lacks supported template/interval')
            if 'template' in row:
                template = row['template']
                mapping = freeze_id if key == 'inclusive' else registration['source']['model_ids'][key]
                if template.get('candidate_id') != key or template.get('mapping_id') != mapping:
                    raise ResearchError('Bootstrap template identity mismatch')
    if result['results'][MODES[0]]['inclusive'] != result['results'][MODES[1]]['inclusive']:
        raise ResearchError('Inclusive reference was not shared across modes')


def read_unit(path, root, protocol, registration, unit, registered):
    loaded = registry.load(root, str(path.relative_to(Path(root))), units()[unit]['stage'], protocol)
    expected = unit_binding(registration, unit)
    if (loaded.read_json('binding.json') != expected
            or loaded.manifest['upstreams'] != [dict(artifact_id=registered.manifest['artifact_id'],
                stage=registered.manifest['stage'], path=str(registered.path))]):
        raise ResearchError('Unit registration or upstream mismatch')
    registry._safe_path(Path(root)/'claims'/(unit+'.json'))
    claim = read_json(Path(root)/'claims'/(unit+'.json'))
    if claim != expected:
        raise ResearchError('Unit claim mismatch')
    result = loaded.read_json('result.json')
    validate_result(result, registration, unit)
    if units()[unit]['stage'] == 'bootstrap':
        access = loaded.read_json('access.json')
        if (access['review'].get('registration_id') != registration['registration_id']
                or access['review'].get('status') != 'approved'
                or access['review'].get('decision') != 'allow_exploratory_supplement'
                or access['claim']['binding'].get('registration_id') != registration['registration_id']):
            raise ResearchError('Bootstrap access provenance mismatch')
    return loaded, result


def inventory(root, protocol, registration, unit, registered):
    root = Path(root)
    paths = [root/'units'/unit, *sorted((root/'units').glob(unit+'-retry-*'))]
    valid, invalid = [], []
    for path in paths:
        if os.path.lexists(path):
            try:
                valid.append(read_unit(path, root, protocol, registration, unit, registered))
            except (ResearchError, KeyError, TypeError, ValueError) as error:
                invalid.append(dict(path=str(path), reason=str(error)))
    if len(valid) > 1:
        raise ResearchError('Multiple complete terminals for one planned unit')
    return (valid[0] if valid else None), invalid


@contextmanager
def numeric_threads():
    import torch
    try:
        from threadpoolctl import threadpool_limits
    except ImportError as error:
        raise ResearchError("Supplemental numerical execution requires threadpoolctl; install the parallel extra") from error
    previous = torch.get_num_threads()
    try:
        torch.set_num_threads(1)
        with threadpool_limits(limits=1):
            yield
    finally:
        torch.set_num_threads(previous)


def execute(source_run, root, protocol, stage, *, continuation=False, unit=None,
            retry_failed=False, workers=1, access_review=None, progress=True):
    if stage not in {'bootstrap', 'model-self'} or type(workers) is not int or workers not in range(1, 5):
        raise ResearchError('Invalid stage or workers (expected 1 through 4)')
    selected = units(stage)
    if unit is not None:
        if unit not in selected:
            raise ResearchError('Unit does not belong to requested stage')
        selected = {unit: selected[unit]}
    if retry_failed and unit is None:
        raise ResearchError('Recovery requires explicit --unit and --retry-failed')
    started = perf_counter()
    registered, registration, source = registry.bound_registration(source_run, root, protocol)
    source_binding_seconds = perf_counter()-started
    root = Path(root)
    with _evaluation_lock(root), numeric_threads():
        pending, reused = [], []
        for name in selected:
            terminal, invalid = inventory(root, protocol, registration, name, registered)
            claimed = (root/'claims'/(name+'.json')).exists()
            if terminal:
                if retry_failed or not continuation:
                    raise ResearchError('Complete units, including numerical failures, cannot be replaced; use --continue')
                reused.append(name)
            else:
                if (claimed or invalid) and not retry_failed:
                    raise ResearchError(f'{name} interrupted or corrupt; use --unit {name} --retry-failed')
                if retry_failed and not (claimed or invalid):
                    raise ResearchError('Explicit recovery requires previous unit evidence')
                pending.append(name)
        if not pending:
            return dict(execution_status='complete', completed_units=reused, new_units=[], qualification=EXPECTED['qualification'])
        access = registry.authorize(root, registered, registration, access_review) if stage == 'bootstrap' else None
        loading_started = perf_counter()
        if stage == 'bootstrap':
            prepared = source['prepared']
            frame = data.read_events(prepared.file('events.jsonl'), source['protocol'],
                roles=('validation', 'evaluation'), freeze=source['frozen'], prepared_id=prepared.manifest['artifact_id'])
            if (frame.attrs['population_id'] != source['identity']['population_id']
                    or frame.attrs['source_kind'] != source['identity']['source_kind']):
                raise ResearchError('Supplemental event population mismatch')
            loading_seconds = perf_counter()-loading_started
            cache = build_cache(frame.loc[frame.role == 'validation'], frame.loc[frame.role == 'evaluation'],
                source['models'], source['protocol'], source['frozen']['freeze_id'], frame.attrs['population_id'])
            def work(name):
                return bootstrap_replica(cache, source['models'], source['protocol'], units()[name]['replica'])
        else:
            loading_seconds = perf_counter()-loading_started
            cache = {}
            def work(name):
                spec = units()[name]
                return model_self_cell(source['nominal'][spec['key']].get('template', {'status': 'unavailable'}),
                    source['protocol'], source['frozen']['freeze_id'], spec['key'], spec['mu'])
        def claimed_tasks():
            for name in pending:
                registry.atomic_claim(root/'claims'/(name+'.json'), unit_binding(registration, name), reuse=retry_failed)
                yield name
        paths, publication_seconds, serialization_seconds = [], 0., 0.
        execution = 'thread' if os.name == 'nt' else 'process'
        with tqdm(total=len(pending), desc=stage, unit='unit', disable=not progress, file=sys.stderr) as bar:
            results = ordered_map(work, claimed_tasks(), workers=workers, worker_threads=1, execution=execution)
            for name, result in zip(pending, results):
                validate_result(result, registration, name)
                suffix = '-retry-'+uuid.uuid4().hex if retry_failed else ''
                target = 'units/'+name+suffix
                publishing_started = perf_counter()
                with registry.new_run(root, target, stage, protocol, [registered]) as run:
                    run.write_json('binding.json', unit_binding(registration, name))
                    run.write_json('result.json', result)
                    if access is not None:
                        run.write_json('access.json', access)
                    run.write_json('attempt.json', dict(retry=retry_failed, workers=workers, execution=execution,
                        worker_threads=1, platform=platform.platform(), previous_evidence=inventory(
                            root, protocol, registration, name, registered)[1]))
                publication_seconds += run.publication_seconds
                serialization_seconds += perf_counter()-publishing_started
                paths.append(str(root/target))
                bar.update()
        timing = dict(elapsed_seconds=perf_counter()-started, source_binding_seconds=source_binding_seconds, loading_seconds=loading_seconds,
            scoring_seconds=cache.get('scoring_seconds', 0.), cache_build_seconds=cache.get('cache_build_seconds', 0.),
            transaction_publication_seconds=publication_seconds,
            serialization_and_publication_seconds=serialization_seconds, workers=workers, worker_threads=1, platform=platform.platform(),
            execution=execution, units=paths, clock='perf_counter',
            worker_timing_note='Template/model setup and fit durations are recorded per unit; worker sums are not wall time.')
        with registry.new_run(root, 'timing/'+uuid.uuid4().hex, 'timing', protocol, [registered]) as run:
            run.write_json('timing.json', timing)
        return dict(execution_status='complete', completed_units=[*reused, *pending], new_units=paths,
                    qualification=EXPECTED['qualification'], timing=timing)
