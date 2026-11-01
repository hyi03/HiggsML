"""Independent T2 registration, parent access, preparation and unit recovery."""
import os
from pathlib import Path
import platform
from time import perf_counter
import uuid

import numpy as np
from tqdm.auto import tqdm

from higgsml.artifacts import digest_json, read_json
from higgsml.errors import ResearchError, ResearchStateError
from higgsml.inference.population_history import history_scope
from higgsml.resources import ordered_map
from higgsml.draft_v2 import data, validation_registry as artifacts
from higgsml.draft_v2.validation_execution import numeric_threads, _interval
from higgsml.draft_v2.validation_statistics import toy_summary
from higgsml.draft_v2.workflow import _evaluation_lock
from higgsml.draft_v2 import t2_statistics as statistics
from higgsml.draft_v2.t2_protocol import EXPECTED, KEYS, outer_draw, stream, units, validate_protocol


def registration_value(source, root):
    value = dict(schema_version='h4l-draft-v2-t2-registration-v1', source=source['identity'],
        output_root=str(Path(root).resolve()), protocol_sha256=digest_json(EXPECTED),
        budget=EXPECTED['budget'], units=units(), qualification=EXPECTED['qualification'])
    return {**value, 'registration_id': digest_json(value)}


def access_template(root, registration):
    source = registration['source']
    return dict(schema_version='h4l-draft-v2-t2-access-v1', status='pending', decision='pending',
        dataset=EXPECTED['dataset'], source_population='all_mc', source_kind=source['source_kind'], independent=False,
        registration_id=registration['registration_id'], protocol_sha256=digest_json(EXPECTED),
        source_freeze_id=source['freeze_id'], prepared_artifact_id=source['prepared_artifact_id'],
        population_id=source['population_id'], budget=EXPECTED['budget'],
        history_sha256=digest_json(artifacts.history(root, registration['registration_id'])), reviewed_by='', reviewed_at='')


def plan(source_run, root, protocol):
    validate_protocol(protocol)
    source_run, root = artifacts.safe_roots(source_run, root)
    source = artifacts.load_source(source_run, metadata_only=True)
    registration = registration_value(source, root)
    return dict(mode='plan_only', registration=registration, access_review_template=access_template(root, registration),
        existing_units_unverified={name: [str(p) for p in [root/'units'/name, *sorted((root/'units').glob(name+'-retry-*'))]
                                         if os.path.lexists(p)] for name in units()},
        payloads_opened=False, access_requirements=['new T2 plan-bound receipt; v1 bootstrap receipt is insufficient',
            'durable claim before events hash/read/score', 'fixed evaluation halves are disjoint but not independent confirmation'])


def register(source_run, root, protocol, *, continuation=False):
    validate_protocol(protocol)
    source_run, root = artifacts.safe_roots(source_run, root)
    source = artifacts.load_source(source_run)
    registration = registration_value(source, root)
    if (root/'register').exists():
        if not continuation:
            raise ResearchError('T2 registration exists; use --continue')
        old = artifacts.load(root, 'register', 't2-register', protocol)
        if old.read_json('registration.json') != registration:
            raise ResearchError('T2 registration source or budget mismatch')
        return old
    if root.exists():
        raise ResearchError('T2 registration requires a fresh sibling directory')
    with artifacts.new_run(root, 'register', 't2-register', protocol, source['handles']) as run:
        run.write_json('registration.json', registration)
        run.write_json('base-protocol.json', source['protocol'])
        run.write_json('access-review.pending.json', access_template(root, registration))
    return artifacts.load(root, 'register', 't2-register', protocol)


def bound(source_run, root, protocol):
    validate_protocol(protocol)
    source_run, root = artifacts.safe_roots(source_run, root)
    registered = artifacts.load(root, 'register', 't2-register', protocol)
    source = artifacts.load_source(source_run)
    registration = registration_value(source, root)
    if registered.read_json('registration.json') != registration or registered.read_json('base-protocol.json') != source['protocol']:
        raise ResearchError('T2 source, protocol or budget binding changed')
    return registered, registration, source


def access_binding(registered, registration):
    source = registration['source']
    return dict(registration_id=registration['registration_id'], freeze_artifact_id=registered.manifest['artifact_id'],
        source_freeze_artifact_id=source['freeze_artifact_id'], prepared_artifact_id=source['prepared_artifact_id'],
        population_id=source['population_id'], source_kind=source['source_kind'], dataset=EXPECTED['dataset'],
        source_population='all_mc', stage='draft-v2-t2', budget=EXPECTED['budget'], protocol_sha256=digest_json(EXPECTED))


def authorize(root, registered, registration, path):
    if path is None:
        raise ResearchError('T2 preparation requires a new reviewed T2 access receipt')
    review = read_json(Path(path))
    expected = access_template(root, registration)
    from jsonschema import Draft202012Validator
    schema = Path(__file__).resolve().parents[3]/'config/schemas/h4l_draft_v2_t2_access.schema.json'
    try:
        Draft202012Validator(read_json(schema)).validate(review)
    except Exception as error:
        raise ResearchError('Invalid T2 access schema') from error
    if (set(review) != set(expected) or review.get('status') != 'approved'
            or review.get('decision') != 'allow_exploratory_t2'
            or any(not isinstance(review.get(k), str) or not review[k].strip() for k in ('reviewed_by', 'reviewed_at'))
            or any(review[k] != v for k, v in expected.items() if k not in {'status', 'decision', 'reviewed_by', 'reviewed_at'})):
        raise ResearchError('T2 access receipt is pending, stale or not bound to this budget')
    binding = access_binding(registered, registration)
    directory = Path(artifacts.history(root, registration['registration_id'])['roots'][0])/'.h4l-draft-v2-t2-claims'
    path = directory/(registration['registration_id']+'.json')
    artifacts.atomic_claim(path, {'binding': binding}, reuse=True)
    return dict(review=review, claim=dict(path=str(path), binding=binding))


def validate_access(root, registered, registration, access):
    """Recheck durable provenance without invalidating cached work on later access."""
    source, review = registration['source'], access['review']
    from jsonschema import Draft202012Validator
    schema = Path(__file__).resolve().parents[3]/'config/schemas/h4l_draft_v2_t2_access.schema.json'
    if not Draft202012Validator(read_json(schema)).is_valid(review):
        raise ResearchError('Invalid saved T2 access receipt')
    expected = dict(status='approved', decision='allow_exploratory_t2', independent=False,
        registration_id=registration['registration_id'], protocol_sha256=digest_json(EXPECTED),
        source_freeze_id=source['freeze_id'], prepared_artifact_id=source['prepared_artifact_id'],
        population_id=source['population_id'], budget=EXPECTED['budget'], source_kind=source['source_kind'],
        dataset=EXPECTED['dataset'], source_population='all_mc')
    if (any(review.get(k) != v for k, v in expected.items())
            or any(not review.get(k, '').strip() for k in ('reviewed_by', 'reviewed_at'))):
        raise ResearchError('T2 preflight access provenance mismatch')
    path = Path(history_scope(Path(root).parent)['roots'][0])/'.h4l-draft-v2-t2-claims'/(registration['registration_id']+'.json')
    local = Path(root)/'claims/preflight.json'
    for claim in (path, local):
        artifacts._safe_path(claim)
    binding = access_binding(registered, registration)
    if (access['claim'] != dict(path=str(path), binding=binding)
            or read_json(path) != {'binding': binding}
            or read_json(local) != {'registration_id': registration['registration_id']}):
        raise ResearchError('T2 preflight durable claim mismatch')


def scientific_preflight_id(value):
    return digest_json({k: v for k, v in value.items() if k not in {'timing', 'preflight_id'}})


def validate_preflight(value, registration):
    source = registration['source']
    if (value.get('schema_version') != 'h4l-draft-v2-t2-preflight-v1'
            or value.get('preflight_id') != scientific_preflight_id(value)
            or set(value.get('cells', {})) != set(units()) or value.get('generated_toys') != 0):
        raise ResearchError('T2 preflight seal or unit budget mismatch')
    identity = value['source_identity']
    if any(identity.get(k) != source[k] for k in ('freeze_id', 'population_id', 'model_ids')):
        raise ResearchError('T2 preflight source changed')
    if set(identity.get('fold_parents', {})) != {'0', '1'}:
        raise ResearchError('Missing T2 crossfit parent')
    for parent in identity['fold_parents'].values():
        if (parent.get('groups', 0) <= 0 or parent.get('rows', 0) < parent['groups']
                or parent.get('assignment_probability') != .5 or parent.get('effective_sampling_probability') != .1
                or len(parent.get('groups_sha256', '')) != 64):
            raise ResearchError('Invalid T2 parent identity/normalization')
    if set(value.get('draws', {})) != {str(i) for i in range(20)} or set(value.get('thresholds', {})) != {str(i) for i in range(20)}:
        raise ResearchError('Missing T2 outer draw or mapping')
    for outer in range(20):
        draw = value['draws'][str(outer)]
        if (draw['groups'] != value['draws']['0']['groups']
                or draw != outer_draw(source['freeze_id'], outer, draw['groups'])[1]):
            raise ResearchError('T2 outer draw changed')
        if set(value['thresholds'][str(outer)]) != set(KEYS)-{'inclusive'}:
            raise ResearchError('Missing T2 calibration candidate')
    for name, spec in units().items():
        cell = value['cells'][name]
        if (cell.get('specification') != spec
                or cell.get('cell_id') != digest_json({k: v for k, v in cell.items() if k != 'cell_id'})):
            raise ResearchError('T2 cell seal/specification mismatch')
        mapping = cell['mapping']
        expected = (dict(status='valid', threshold=None) if spec['key'] == 'inclusive'
                    else value['thresholds'][str(spec['outer'])][spec['key']])
        if mapping != expected:
            raise ResearchError('T2 folds do not share the registered outer mapping')
        if mapping['status'] == 'valid' and spec['key'] != 'inclusive':
            if mapping.get('threshold') is None or not np.isfinite(mapping['threshold']) or not 0 <= mapping['threshold'] <= 1:
                raise ResearchError('Invalid recalibrated threshold')
        for field in ('fit_template', 'mother_template'):
            template = cell.get(field)
            if template is not None and 'candidate_id' in template:
                if template['candidate_id'] != spec['key']:
                    raise ResearchError('T2 template candidate mismatch')
                expected_mapping = digest_json(dict(source_freeze=source['freeze_id'],
                    model_id=None if spec['key'] == 'inclusive' else source['model_ids'][spec['key']],
                    threshold=mapping['threshold'], protocol_sha256=digest_json(EXPECTED)))
                if template.get('mapping_id') != expected_mapping:
                    raise ResearchError('T2 template threshold binding mismatch')
        status, failure_phase, rates = mapping['status'], None, None
        if status != 'valid':
            failure_phase = 'threshold_estimation'
            if cell.get('fit_template') is not None or cell.get('mother_template') is not None:
                raise ResearchError('Failed T2 threshold cannot define parent templates')
        else:
            for phase, field in [('fit_template', 'fit_template'), ('mother', 'mother_template')]:
                try:
                    current = statistics._independent_rates(cell[field], spec['mu'])
                    if phase == 'mother':
                        rates = current
                except ResearchStateError as error:
                    status, failure_phase = error.status, phase
                    break
        if (cell['status'] != status or cell.get('failure_phase') != failure_phase
                or cell.get('mother_rates') != rates):
            raise ResearchError('T2 support terminal or mother rate mismatch')
        if status not in {'valid', 'insufficient_statistics', 'template_stat_model_unvalidated'}:
            raise ResearchError('Unknown T2 support terminal')
    for name, spec in units().items():
        other_name = name.replace(f"-fold{spec['template_fold']}-", f"-fold{spec['mother_fold']}-")
        if value['cells'][name].get('fit_template') != value['cells'][other_name].get('mother_template'):
            raise ResearchError('T2 parent exchange does not preserve the same threshold/categories')


def _find(root, stem, read):
    valid, invalid = [], []
    for path in [Path(root)/stem, *sorted(Path(root).glob(stem+'-retry-*'))]:
        if os.path.lexists(path):
            try:
                valid.append(read(path))
            except (ResearchError, KeyError, TypeError, ValueError) as error:
                invalid.append(dict(path=str(path), reason=str(error)))
    if len(valid) > 1:
        raise ResearchError('Multiple valid T2 terminals for one planned unit')
    return (valid[0] if valid else None), invalid


def find_preflight(root, protocol, registration):
    def read(path):
        loaded = artifacts.load(root, path.name, 't2-preflight', protocol)
        if loaded.read_json('binding.json') != {'registration_id': registration['registration_id']}:
            raise ResearchError('T2 preflight belongs to another registration')
        value = loaded.read_json('preflight.json')
        validate_preflight(value, registration)
        registered = artifacts.load(root, 'register', 't2-register', protocol)
        validate_access(root, registered, registration, loaded.read_json('access.json'))
        if loaded.manifest['upstreams'] != [dict(artifact_id=registered.manifest['artifact_id'],
                                                stage=registered.manifest['stage'], path=str(registered.path))]:
            raise ResearchError('T2 preflight belongs to another registration')
        return loaded, value
    return _find(root, 'preflight', read)


def prepare(source_run, root, protocol, *, access_review=None, continuation=False, unit=None, retry_failed=False):
    if (unit is not None and unit != 'preflight') or (retry_failed and unit != 'preflight'):
        raise ResearchError('Preflight recovery requires --unit preflight --retry-failed')
    registered, registration, source = bound(source_run, root, protocol)
    root = Path(root)
    with _evaluation_lock(root), numeric_threads():
        prior, invalid = find_preflight(root, protocol, registration)
        if prior:
            if retry_failed or not continuation:
                raise ResearchError('Completed T2 preflight cannot be replaced; use --continue')
            return prior
        claimed = (root/'claims/preflight.json').exists()
        if (claimed or invalid) and not retry_failed:
            raise ResearchError('Interrupted/corrupt T2 preflight requires --unit preflight --retry-failed')
        if retry_failed and not (claimed or invalid):
            raise ResearchError('No prior T2 preflight evidence to recover')
        access = authorize(root, registered, registration, access_review)
        artifacts.atomic_claim(root/'claims/preflight.json', {'registration_id': registration['registration_id']}, reuse=retry_failed)
        started = perf_counter()
        prepared = source['prepared']
        frame = data.read_events(prepared.file('events.jsonl'), source['protocol'], roles=('validation', 'evaluation'),
                                 freeze=source['frozen'], prepared_id=source['identity']['prepared_artifact_id'])
        if frame.attrs['population_id'] != source['identity']['population_id'] or frame.attrs['source_kind'] != source['identity']['source_kind']:
            raise ResearchError('T2 event population mismatch')
        loading_seconds = perf_counter()-started
        value = statistics.prepare_cells(frame.loc[frame.role == 'validation'], frame.loc[frame.role == 'evaluation'],
            source['models'], source['protocol'], source['identity']['freeze_id'], source['identity']['population_id'])
        value['preflight_id'] = scientific_preflight_id(value)
        value['timing'].update(loading_seconds=loading_seconds, worker_threads=1, platform=platform.platform())
        validate_preflight(value, registration)
        name = 'preflight-retry-'+uuid.uuid4().hex if retry_failed else 'preflight'
        with artifacts.new_run(root, name, 't2-preflight', protocol, [registered]) as run:
            run.write_json('binding.json', {'registration_id': registration['registration_id']})
            run.write_json('access.json', access)
            run.write_json('preflight.json', value)
            run.write_json('recovery.json', dict(retry=retry_failed, preserved_invalid=invalid))
        return artifacts.load(root, name, 't2-preflight', protocol), value


def unit_binding(registration, preflight, unit):
    return dict(registration_id=registration['registration_id'], preflight_id=preflight['preflight_id'],
                unit=unit, specification=units()[unit], cell_id=preflight['cells'][unit]['cell_id'])


def validate_result(value, registration, preflight, unit):
    spec = units()[unit]
    cell = preflight['cells'][unit]
    if (value.get('schema_version') != 'h4l-draft-v2-t2-cell-v1' or value.get('specification') != spec
            or value.get('cell_id') != cell['cell_id'] or value.get('count') != 100
            or len(value.get('results', [])) != 100 or value.get('threshold') != cell['mapping']['threshold']
            or value.get('failure_phase') != cell['failure_phase']
            or value.get('expectation_kind') != 'crossfit_parent_t2' or value.get('paired_coverage') is not False):
        raise ResearchError('T2 unit input, result kind or inner budget mismatch')
    for i, row in enumerate(value['results']):
        if row.get('toy') != i:
            raise ResearchError('Missing/duplicate T2 inner Toy')
        for kind, field in [('main', 'main_stream'), ('auxiliary', 'auxiliary_stream')]:
            if row.get(field) != stream(registration['source']['freeze_id'], kind, spec['key'], spec['template_fold'], spec['outer'], spec['mu'], i)[1]:
                raise ResearchError('T2 inner stream mismatch')
        _interval(row['interval'])
        if cell['status'] == 'valid':
            observed = np.asarray(row.get('observation', []), float)
            # T1 has one shapesys auxiliary per active process/bin plus main bins.
            template = cell['fit_template']
            n_main = len(template['active_bins'])
            expected_size = n_main*(len(template['samples'])+1)
            if observed.shape != (expected_size,) or not np.isfinite(observed).all() or (observed < 0).any():
                raise ResearchError('Missing/invalid T2 generated observations')
        elif 'observation' in row or row['interval']['status'] != cell['status']:
            raise ResearchError('Unsupported T2 cell generated observations or lost failure budget')
    if (value.get('generated_toys') != (100 if cell['status'] == 'valid' else 0)
            or value.get('summary') != toy_summary([r['interval'] for r in value['results']], spec['mu'])):
        raise ResearchError('T2 failure denominator or summary mismatch')


def inventory(root, protocol, registered, registration, preflight, unit):
    def read(path):
        loaded = artifacts.load(root, str(path.relative_to(Path(root))), 't2-unit', protocol)
        binding = unit_binding(registration, preflight, unit)
        artifacts._safe_path(Path(root)/'claims'/(unit+'.json'))
        if loaded.read_json('binding.json') != binding or read_json(Path(root)/'claims'/(unit+'.json')) != binding:
            raise ResearchError('T2 unit claim/input binding mismatch')
        if loaded.manifest['upstreams'] != [dict(artifact_id=registered.manifest['artifact_id'],
                                                stage=registered.manifest['stage'], path=str(registered.path))]:
            raise ResearchError('T2 unit belongs to another registration')
        result = loaded.read_json('result.json')
        validate_result(result, registration, preflight, unit)
        return loaded, result
    return _find(root, 'units/'+unit, read)


def execute(source_run, root, protocol, *, access_review=None, continuation=False, unit=None, retry_failed=False, workers=1, progress=True):
    if type(workers) is not int or workers not in range(1, 5) or (unit is not None and unit not in units()):
        raise ResearchError('Invalid T2 workers or unit')
    if retry_failed and unit is None:
        raise ResearchError('T2 recovery requires explicit --unit --retry-failed')
    started = perf_counter()
    registered, registration, source = bound(source_run, root, protocol)
    preflight_run, preflight = prepare(source_run, root, protocol, continuation=True, access_review=access_review)
    root = Path(root)
    with _evaluation_lock(root), numeric_threads():
        pending, reused = [], []
        for name in ([unit] if unit else units()):
            prior, invalid = inventory(root, protocol, registered, registration, preflight, name)
            claimed = (root/'claims'/(name+'.json')).exists()
            if prior:
                if retry_failed or not continuation:
                    raise ResearchError('Completed T2 unit, including numerical failures, cannot be replaced; use --continue')
                reused.append(name)
            else:
                if (claimed or invalid) and not retry_failed:
                    raise ResearchError(f'Interrupted/corrupt T2 unit {name}; use --unit {name} --retry-failed')
                if retry_failed and not (claimed or invalid):
                    raise ResearchError('T2 retry requires previous unit evidence')
                pending.append(name)
        if not pending:
            return dict(execution_status='complete', reused_units=reused, new_units=[], qualification=EXPECTED['qualification'])
        base_protocol, freeze_id = source['protocol'], source['identity']['freeze_id']
        def work(cell):
            return statistics.fit_cell(cell, base_protocol, freeze_id)
        def tasks():
            for name in pending:
                artifacts.atomic_claim(root/'claims'/(name+'.json'), unit_binding(registration, preflight, name), reuse=retry_failed)
                yield preflight['cells'][name]
        paths, publication_seconds = [], 0.
        execution = 'thread' if os.name == 'nt' else 'process'
        with tqdm(total=len(pending), desc='T2 cells', unit='cell', disable=not progress) as bar:
            for name, result in zip(pending, ordered_map(work, tasks(), workers=workers, worker_threads=1, execution=execution), strict=True):
                validate_result(result, registration, preflight, name)
                target = 'units/'+name+('-retry-'+uuid.uuid4().hex if retry_failed else '')
                before = perf_counter()
                with artifacts.new_run(root, target, 't2-unit', protocol, [registered]) as run:
                    run.write_json('binding.json', unit_binding(registration, preflight, name))
                    run.write_json('result.json', result)
                    run.write_json('attempt.json', dict(retry=retry_failed, workers=workers, worker_threads=1,
                        platform=platform.platform(), execution=execution, preflight_artifact_id=preflight_run.manifest['artifact_id'],
                        preserved_invalid=inventory(root, protocol, registered, registration, preflight, name)[1]))
                publication_seconds += perf_counter()-before
                paths.append(str(root/target))
                bar.update()
        with artifacts.new_run(root, 'timing/'+uuid.uuid4().hex, 't2-timing', protocol, [registered]) as run:
            run.write_json('timing.json', dict(elapsed_seconds=perf_counter()-started,
                serialization_and_publication_seconds=publication_seconds, workers=workers, worker_threads=1,
                platform=platform.platform(), execution=execution, units=paths, clock='perf_counter'))
        return dict(execution_status='complete', reused_units=reused, new_units=paths, qualification=EXPECTED['qualification'])
